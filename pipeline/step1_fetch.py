"""
Step 1: Fetch articles from Google News RSS feeds.

Runs 5 feeds concurrently, deduplicates by URL, filters to last N days,
and strips HTML from snippets. Output saved to output/articles.json.

Usage:
    python -m pipeline.step1_fetch
    python pipeline/step1_fetch.py
"""
import html
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

import ssl

import feedparser

from models.schemas import Article, FetchResult

# Walmart corporate proxy uses its own CA — Python's bundled certifi doesn't have it.
# Disabling verification is acceptable for RSS (public, non-sensitive data).
ssl._create_default_https_context = ssl._create_unverified_context

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feed configuration — 12 geo-politics feeds covering the domains that
# matter most to Silicon Valley professionals. Feed diversity across these
# 12 is used as the social-signal proxy in step3_score.py.
# All feeds use Google News RSS search (proxy-whitelisted on Walmart network).
# ---------------------------------------------------------------------------

FEEDS: list[dict[str, str]] = [
    # ── Core geopolitics (original 5) ────────────────────────────────────
    {
        "name": "US Geopolitics & Diplomacy",
        "url": (
            "https://news.google.com/rss/search"
            "?q=US+foreign+policy+diplomacy+sanctions+geopolitics+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "US-China & Trade Wars",
        "url": (
            "https://news.google.com/rss/search"
            "?q=US+China+trade+war+tariffs+Taiwan+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "Global Conflict & Security",
        "url": (
            "https://news.google.com/rss/search"
            "?q=war+conflict+Russia+Ukraine+NATO+Israel+Middle+East+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "International Trade & Sanctions",
        "url": (
            "https://news.google.com/rss/search"
            "?q=tariff+trade+deal+sanctions+WTO+G7+G20+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "US National Security",
        "url": (
            "https://news.google.com/rss/search"
            "?q=national+security+Pentagon+State+Department+defense+intelligence+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    # ── Silicon Valley persona feeds (new 7) ─────────────────────────────
    {
        "name": "AI & Chip Export Controls",
        "url": (
            "https://news.google.com/rss/search"
            "?q=AI+semiconductor+chip+export+controls+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "Dollar & Global Finance",
        "url": (
            "https://news.google.com/rss/search"
            "?q=dollar+Federal+Reserve+central+bank+currency+geopolitics+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "Energy & Critical Minerals",
        "url": (
            "https://news.google.com/rss/search"
            "?q=oil+energy+OPEC+lithium+cobalt+critical+minerals+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "India & Gulf Relations",
        "url": (
            "https://news.google.com/rss/search"
            "?q=India+Gulf+Modi+diplomacy+Middle+East+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "Cyber & Espionage",
        "url": (
            "https://news.google.com/rss/search"
            "?q=cyberattack+espionage+hack+state-sponsored+signals+intelligence+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "Africa & Global South",
        "url": (
            "https://news.google.com/rss/search"
            "?q=Africa+China+Global+South+Belt+Road+Initiative+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "Tech Regulation & Antitrust",
        "url": (
            "https://news.google.com/rss/search"
            "?q=antitrust+big+tech+regulation+EU+FTC+data+privacy+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
]

# ---------------------------------------------------------------------------
# Geo-politics relevance guardrail
# Any article that matches ZERO of these keywords is dropped before clustering.
# Prevents non-geo-political stories (sports, entertainment, pure tech) from
# contaminating the feed — the RSS feeds can still surface off-topic results.
# ---------------------------------------------------------------------------

_GEO_KEYWORDS: frozenset[str] = frozenset({
    # Diplomacy & institutions
    "diplomacy", "diplomatic", "foreign policy", "bilateral", "multilateral",
    "treaty", "alliance", "united nations", "embassy", "consul",
    "nato", "g7", "g20", "wto", "imf", "world bank", "un ",
    # Trade & economic coercion
    "tariff", "trade ", "trade deal", "sanction", "embargo", "export ban",
    "import", "supply chain", "protectionism", "trade deficit", "trade surplus",
    # Countries / regions with geopolitical salience
    "china", "russia", "ukraine", "iran", "israel", "taiwan", "north korea",
    "middle east", "europe", "eu ", "india", "pakistan", "saudi",
    "britain", "uk ", "japan", "south korea", "australia", "mexico",
    "iran", "turkey", "venezuela", "cuba", "africa", "gulf", "opec",
    # Conflict & security
    "war", "conflict", "military", "troops", "armed forces", "missile",
    "nuclear", "intelligence", "cia", "pentagon", "defense", "deterrence",
    "national security", "state department", "geopolit",
    "cyberattack", "cyber attack", "espionage", "hack", "state-sponsored",
    # US executive / international decisions
    "white house", "president", "administration", "executive order",
    "secretary of state", "national security council", "foreign minister",
    # Strategic competition
    "superpower", "great power", "hegemony", "sphere of influence",
    "cold war", "proxy", "coercion", "influence operation",
    "belt and road", "global south",
    # Tech & finance with geopolitical dimension (new feeds)
    "semiconductor", "chip", "export control", "ai regulation",
    "federal reserve", "central bank", "currency", "dollar",
    "lithium", "cobalt", "critical mineral", "rare earth",
    "antitrust", "ftc", "data privacy", "data sovereignty",
})


def _is_geopolitical(article: "Article") -> bool:
    """Return True if article text contains at least one geo-politics keyword.

    Operates on title + body_snippet (already lowercase-safe via simple .lower()).
    This is a fast O(k) keyword scan — no LLM needed at fetch time.
    """
    haystack = (article.title + " " + (article.body_snippet or "")).lower()
    return any(kw in haystack for kw in _GEO_KEYWORDS)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw: str) -> str:
    """Remove HTML tags and decode entities."""
    text = _HTML_TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    return " ".join(text.split())  # collapse whitespace


def _parse_published(entry: feedparser.FeedParserDict) -> datetime | None:
    """Convert feedparser's struct_time to a UTC-aware datetime."""
    if not entry.get("published_parsed"):
        return None
    try:
        ts = time.mktime(entry.published_parsed)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _source_name(entry: feedparser.FeedParserDict) -> str:
    """Safely extract the publisher name from a feed entry."""
    src = entry.get("source", {})
    if isinstance(src, dict):
        return src.get("title", "Unknown")
    return getattr(src, "title", "Unknown")


def fetch_feed(feed: dict[str, str], max_age_days: int = 4) -> list[Article]:
    """Fetch one RSS feed and return filtered, cleaned Article objects."""
    name, url = feed["name"], feed["url"]
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max_age_days)

    try:
        parsed = feedparser.parse(url)
    except Exception as exc:
        log.warning("Step 1: Failed to fetch '%s' — %s", name, exc)
        return []

    if parsed.bozo and not parsed.entries:
        log.warning("Step 1: Feed '%s' returned no entries (bozo=%s)", name, parsed.bozo_exception)
        return []

    articles: list[Article] = []
    for entry in parsed.entries:
        published_at = _parse_published(entry)
        if published_at is None or published_at < cutoff:
            continue

        title = entry.get("title", "").strip()
        if not title:
            continue

        raw_summary = entry.get("summary", "") or entry.get("description", "")
        snippet = _strip_html(raw_summary)
        if len(snippet) < 20:
            snippet = title  # fallback — title is still meaningful for embedding

        articles.append(Article(
            title=title,
            url=entry.get("link", ""),
            source_name=_source_name(entry),
            published_at=published_at,
            body_snippet=snippet[:500],  # cap; no article has useful signal beyond 500 chars from RSS
            feed_name=name,
        ))

    log.info("Step 1: '%s' → %d articles (within %d days)", name, len(articles), max_age_days)
    return articles


def fetch_all_feeds(max_age_days: int = 4) -> FetchResult:
    """Fetch all feeds concurrently, deduplicate by URL + title, return FetchResult."""
    all_articles: list[Article] = []
    feed_counts: dict[str, int] = {}
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()  # catch verbatim press releases published across many sources

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(fetch_feed, f, max_age_days): f["name"] for f in FEEDS}
        for future in as_completed(futures):
            feed_name = futures[future]
            try:
                articles = future.result()
            except Exception as exc:
                log.error("Step 1: Unexpected error for '%s' — %s", feed_name, exc)
                articles = []

            unique: list[Article] = []
            for a in articles:
                # normalise title for dedup: lower + strip punctuation/source suffix
                title_key = a.title.split(" - ")[0].lower().strip()
                if (
                    a.url
                    and a.url not in seen_urls
                    and title_key not in seen_titles
                    and _is_geopolitical(a)   # ← geo-politics guardrail
                ):
                    seen_urls.add(a.url)
                    seen_titles.add(title_key)
                    unique.append(a)

            all_articles.extend(unique)
            feed_counts[feed_name] = len(unique)
            log.info("Step 1: '%s' → %d geo-political articles (deduped)", feed_name, len(unique))

    log.info("Step 1: Total unique articles fetched: %d", len(all_articles))
    return FetchResult(
        articles=all_articles,
        total_count=len(all_articles),
        feed_counts=feed_counts,
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    output_path = Path("output/articles.json")
    output_path.parent.mkdir(exist_ok=True)

    log.info("Step 1: Starting RSS fetch across %d feeds…", len(FEEDS))
    result = fetch_all_feeds(max_age_days=4)

    if result.total_count == 0:
        log.error("Step 1: No articles fetched. Check network / feed URLs.")
        sys.exit(1)

    output_path.write_text(result.model_dump_json(indent=2))
    log.info("Step 1: Saved %d articles → %s", result.total_count, output_path)
    for feed_name, count in result.feed_counts.items():
        log.info("  %-20s %d articles", feed_name, count)


if __name__ == "__main__":
    main()
