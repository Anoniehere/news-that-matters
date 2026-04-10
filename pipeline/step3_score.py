"""
Step 3: Trend Scoring

Assigns a trend_score to each cluster from Step 2 using two signals:

  trend_score = 0.70 × repetition_score + 0.30 × social_score

  repetition_score — log-normalised article count across clusters
  social_score     — pytrends (Google Trends) → feed-diversity fallback

Social signal resolution order (ADR-014):
  1. pytrends: Google Trends 4-day US interest score [0–1]
     Works in open-internet production. Returns 400 on some corporate nets
     due to Google's 2024 auth change in their undocumented Trends API.
  2. feed_diversity: fraction of our 5 RSS feeds that covered this cluster
     Completely offline, deterministic, highly reproducible.
     A story in Economy + US Politics + Top Stories simultaneously IS trending.

Weights: repetition 70%, social 30%  (ADR-003, ADR-010)
Top 7 clusters are ranked; top 5 flagged for_llm=True for M3 enrichment.

Usage:
    python -m pipeline.step3_score
    python pipeline/step3_score.py
"""
import json
import logging
import math
import os
import re
import ssl
import time
from datetime import datetime
from pathlib import Path

from models.schemas import (
    Cluster,
    ClusterResult,
    FetchResult,
    ScoredCluster,
    TrendResult,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# ---------------------------------------------------------------------------
# Config — all weights / constants in one place (AGENTS.md rule)
# ---------------------------------------------------------------------------
WEIGHT_REP     = 0.70   # ADR-003, ADR-010
WEIGHT_SOCIAL  = 0.30
TOP_N_TOTAL    = 7      # buffer passed through pipeline
TOP_N_LLM      = 5      # flagged for_llm=True → step4_enrich
TOTAL_FEEDS    = 5      # US Top Stories, Technology, Economy, US Politics, AI & Science
PYTRENDS_SLEEP = 2.0    # seconds between pytrends calls (exit criterion)

INPUT_PATH  = Path("output/clusters.json")
OUTPUT_PATH = Path("output/ranked_clusters.json")

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "have",
    "has", "had", "do", "does", "did", "to", "of", "in", "on", "at",
    "by", "for", "with", "as", "from", "and", "or", "but", "not", "it",
    "its", "this", "that", "says", "said", "new", "one", "two", "after",
    "amid", "could", "would", "will", "may", "can", "how", "why", "what",
    "who", "when", "where", "breaking", "watch", "live", "update",
    "report", "following", "latest", "top", "here", "now",
}


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

def _extract_search_term(cluster: Cluster, max_words: int = 4) -> str:
    """
    Extract a concise search term from the cluster's headline article.
    Strips source attribution, removes stop words, prefers proper nouns.
    """
    title = cluster.headline_article.title

    # Strip source name appended after separators like " - Reuters"
    for sep in (" - ", " | ", " — ", " – ", " : "):
        if sep in title:
            title = title[: title.rfind(sep)].strip()
            break

    # Remove leading news tags: "BREAKING:", "WATCH:", "UPDATE:" etc.
    title = re.sub(r"^[A-Z]{2,}[:\s]+", "", title).strip()

    # Remove trailing punctuation
    title = re.sub(r"[?.!]+$", "", title).strip()

    words = title.split()

    # Prefer capitalised terms (proper nouns) — they make better queries
    proper = [w for w in words if w and w[0].isupper() and w.lower() not in STOP_WORDS]
    if len(proper) >= 2:
        return " ".join(proper[:max_words])

    # Fall back to any non-stop words
    meaningful = [w for w in words if w.lower() not in STOP_WORDS and len(w) > 2]
    if meaningful:
        return " ".join(meaningful[:max_words])

    # Last resort: first N words of the stripped title
    return " ".join(words[:max_words])


# ---------------------------------------------------------------------------
# Repetition score — 70% weight
# ---------------------------------------------------------------------------

def _repetition_score(cluster: Cluster, all_clusters: list[Cluster]) -> float:
    """
    Log-normalised cluster size relative to the largest cluster.
    max cluster always = 1.0; smaller clusters get proportional scores.
    Log scale prevents a single huge cluster from swamping everything.
    """
    sizes = [c.size for c in all_clusters]
    max_size = max(sizes)
    if max_size <= 1:
        return 0.5
    score = math.log(cluster.size + 1) / math.log(max_size + 1)
    return round(min(1.0, max(0.0, score)), 4)


# ---------------------------------------------------------------------------
# Social score — 30% weight, two-tier
# ---------------------------------------------------------------------------

def _feed_diversity_score(cluster: Cluster) -> float:
    """
    Fraction of our RSS feeds that contributed to this cluster.
    Range: 0.0 (one feed) → 1.0 (all 5 feeds).
    Formula: (unique_feeds - 1) / (TOTAL_FEEDS - 1) so single-feed = 0.0.
    """
    unique_feeds = len({a.feed_name for a in cluster.articles})
    if TOTAL_FEEDS <= 1:
        return 0.5
    score = (unique_feeds - 1) / (TOTAL_FEEDS - 1)
    return round(min(1.0, max(0.0, score)), 4)


def _pytrends_score(search_term: str) -> float | None:
    """
    Query Google Trends for the search term over the last 4 days (geo=US).
    Returns normalised score [0.0–1.0] or None on any failure.

    None signals the caller to fall back to feed_diversity.
    0.0 is returned only for genuine zero-interest (term found but no searches).
    """
    try:
        ssl._create_default_https_context = ssl._create_unverified_context  # Walmart proxy

        # Import lazily — not all envs have pytrends
        from pytrends.request import TrendReq

        pt = TrendReq(
            hl="en-US",
            tz=360,
            timeout=(8, 25),
            requests_args={"verify": False},
        )
        pt.build_payload(
            kw_list=[search_term],
            cat=0,
            timeframe="now 4-d",
            geo="US",
        )
        df = pt.interest_over_time()

        if df is None or df.empty or search_term not in df.columns:
            log.debug("  pytrends: no data returned for '%s'", search_term)
            return 0.0

        mean_interest = float(df[search_term].mean())
        return round(min(1.0, max(0.0, mean_interest / 100.0)), 4)

    except Exception as exc:
        log.debug("  pytrends failed for '%s': %s", search_term, exc)
        return None   # caller falls back to feed_diversity


def _social_score(
    cluster: Cluster,
    all_clusters: list[Cluster],
    *,
    try_pytrends: bool = True,
) -> tuple[float, str]:
    """
    Return (social_score, signal_source) where signal_source is one of:
      "pytrends"      — Google Trends data used
      "feed_diversity"— cross-feed coverage used (proxy signal)
    """
    if try_pytrends:
        term = _extract_search_term(cluster)
        log.debug("  Querying pytrends for: '%s'", term)
        score = _pytrends_score(term)
        time.sleep(PYTRENDS_SLEEP)   # rate-limit compliance (exit criterion)
        if score is not None:
            return score, "pytrends"
        log.info("  pytrends unavailable — using feed_diversity fallback")

    score = _feed_diversity_score(cluster)
    return score, "feed_diversity"


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_clusters(cluster_result: ClusterResult) -> TrendResult:
    """
    Score and rank all clusters. Returns TrendResult with top-N scored clusters.
    Tries pytrends first; if first call fails, switches all remaining to feed_diversity.
    """
    clusters = cluster_result.clusters
    if not clusters:
        log.warning("Step 3: No clusters to score — returning empty TrendResult")
        return TrendResult(ranked_clusters=[])

    log.info("Step 3: Scoring %d clusters…", len(clusters))

    # Probe pytrends with the first cluster; if it fails switch all to feed_diversity
    probe_term    = _extract_search_term(clusters[0])
    probe_score   = _pytrends_score(probe_term)
    time.sleep(PYTRENDS_SLEEP)
    use_pytrends  = probe_score is not None

    if use_pytrends:
        log.info("Step 3: pytrends is live — using Google Trends for social signal")
    else:
        log.info("Step 3: pytrends unavailable — using feed_diversity for all clusters")

    scored: list[ScoredCluster] = []
    for i, cluster in enumerate(clusters):
        rep = _repetition_score(cluster, clusters)
        term = _extract_search_term(cluster)

        if i == 0 and use_pytrends and probe_score is not None:
            # Reuse the probe result for the first cluster
            soc, src = probe_score, "pytrends"
        else:
            soc, src = _social_score(
                cluster,
                clusters,
                try_pytrends=use_pytrends and i > 0,
            )

        trend = round(WEIGHT_REP * rep + WEIGHT_SOCIAL * soc, 4)

        scored.append(ScoredCluster(
            cluster=cluster,
            repetition_score=rep,
            social_score=soc,
            trend_score=trend,
            search_term=term,
            signal_source=src,
        ))

        log.info(
            "  cluster #%d [%d arts] rep=%.3f soc=%.3f trend=%.3f  '%s'",
            cluster.cluster_id, cluster.size, rep, soc, trend,
            cluster.headline_article.title[:50],
        )

    # Sort descending, assign rank, flag top 5 for LLM
    scored.sort(key=lambda s: s.trend_score, reverse=True)
    top_n = scored[:TOP_N_TOTAL]

    for rank, sc in enumerate(top_n, start=1):
        sc.rank = rank
        sc.for_llm = rank <= TOP_N_LLM

    log.info(
        "Step 3: Top %d clusters ranked. Top %d flagged for LLM enrichment.",
        len(top_n), min(TOP_N_LLM, len(top_n)),
    )
    for sc in top_n:
        llm_flag = "→ LLM" if sc.for_llm else "      "
        log.info(
            "  #%d %s  trend=%.3f  %s",
            sc.rank, llm_flag, sc.trend_score,
            sc.cluster.headline_article.title[:55],
        )

    return TrendResult(ranked_clusters=top_n)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    if not INPUT_PATH.exists():
        log.error("Step 3: %s not found — run step2 first", INPUT_PATH)
        raise SystemExit(1)

    raw = ClusterResult.model_validate_json(INPUT_PATH.read_text())
    log.info("Step 3: Loaded %d clusters from %s", len(raw.clusters), INPUT_PATH)

    result = score_clusters(raw)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(result.model_dump_json(indent=2))
    log.info("Step 3: Wrote %d scored clusters → %s", len(result.ranked_clusters), OUTPUT_PATH)


if __name__ == "__main__":
    main()
