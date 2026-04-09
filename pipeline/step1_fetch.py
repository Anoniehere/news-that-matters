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
# Feed configuration — US-focused, topic-diverse
# ---------------------------------------------------------------------------

FEEDS: list[dict[str, str]] = [
    {
        "name": "US Top Stories",
        "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    },
    {
        "name": "Technology",
        "url": (
            "https://news.google.com/rss/search"
            "?q=US+technology+AI+tech+company+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "US Politics",
        "url": (
            "https://news.google.com/rss/search"
            "?q=US+politics+congress+senate+white+house+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "Economy",
        "url": (
            "https://news.google.com/rss/search"
            "?q=US+economy+federal+reserve+inflation+markets+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
    {
        "name": "AI & Science",
        "url": (
            "https://news.google.com/rss/search"
            "?q=artificial+intelligence+AI+machine+learning+when:4d"
            "&hl=en-US&gl=US&ceid=US:en"
        ),
    },
]

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
                if a.url and a.url not in seen_urls and title_key not in seen_titles:
                    seen_urls.add(a.url)
                    seen_titles.add(title_key)
                    unique.append(a)

            all_articles.extend(unique)
            feed_counts[feed_name] = len(unique)

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
