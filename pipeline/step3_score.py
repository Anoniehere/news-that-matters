"""
Step 3: Trend Scoring — Reputation-Based Pre-Filter

Assigns a trend_score to each cluster from Step 2 using ONE signal:

  trend_score = repetition_score   (log-normalised article count)

This is a PRE-FILTER, not the final score. Step 4 uses a two-pass LLM
architecture to layer persona relevance on top:

  Step 3 (here): rank by coverage breadth → select top 15 candidates
  Step 4 Pass 1:  cheap batch LLM call → sector tags → persona_score
  Step 4 Pass 2:  full enrichment on the correctly-selected top 5
  Final score:    0.70 × rep_score + 0.30 × persona_score

Why not cross-feed scoring here? Editorial breadth and persona relevance measure
different things (editorial consensus vs audience fit). Persona score is
strictly more useful but requires an LLM call, so rep_score alone serves
as the cheap pre-filter that decides which clusters deserve LLM attention.

Top 15 clusters are passed to step 4; step 4 selects the final top 5.

Usage:
    python -m pipeline.step3_score
    python pipeline/step3_score.py
"""
import json
import logging
import math
import os
from datetime import datetime
from pathlib import Path

from models.schemas import (
    Cluster,
    ClusterResult,
    ScoredCluster,
    TrendResult,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TOP_N_CANDIDATES = 15   # passed to step 4 for two-pass LLM scoring

INPUT_PATH  = Path("output/clusters.json")
OUTPUT_PATH = Path("output/ranked_clusters.json")


# ---------------------------------------------------------------------------
# Repetition score — the sole pre-filter signal
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
# Trend insight — human-readable explanation
# ---------------------------------------------------------------------------

def _build_trend_insight(
    cluster: Cluster,
    rep_score: float,
) -> str:
    """
    Plain-English sentence explaining why this cluster ranked here.
    Grounded in real numbers — no LLM, no hallucination.

    Step 4 will overwrite this after persona re-scoring. This version
    explains the pre-filter logic only.
    """
    unique_feeds  = len({a.feed_name for a in cluster.articles})
    article_count = cluster.size
    rep_pct       = int(round(rep_score * 100))

    if rep_pct >= 80:
        rep_label = "very high"
    elif rep_pct >= 55:
        rep_label = "strong"
    elif rep_pct >= 35:
        rep_label = "moderate"
    else:
        rep_label = "low"

    feed_word = "feed" if unique_feeds == 1 else "feeds"
    art_word  = "article" if article_count == 1 else "articles"

    return (
        f"{rep_pct}% coverage score: {rep_label} repetition — "
        f"{article_count} {art_word} across {unique_feeds} {feed_word}. "
        f"Pre-filter only; final score set after persona re-ranking in step 4."
    )


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_clusters(cluster_result: ClusterResult) -> TrendResult:
    """
    Score and rank all clusters by repetition only. Returns TrendResult
    with top-N candidates for step 4's two-pass LLM scoring.

    Singleton promotion: when real clusters < 5, recent singletons are
    wrapped into synthetic single-article clusters and scored honestly
    (lower rep score) to fill the output.
    """
    clusters   = cluster_result.clusters
    singletons = cluster_result.singletons

    if not clusters and not singletons:
        log.warning("Step 3: No clusters or singletons — returning empty TrendResult")
        return TrendResult(ranked_clusters=[])

    log.info("Step 3: Scoring %d clusters by repetition…", len(clusters))

    scored: list[ScoredCluster] = []
    for cluster in clusters:
        rep = _repetition_score(cluster, clusters)
        insight = _build_trend_insight(cluster, rep)

        scored.append(ScoredCluster(
            cluster=cluster,
            repetition_score=rep,
            trend_score=rep,         # step 4 will overwrite with rep+persona
            trend_insight=insight,
            signal_source="reputation",
        ))

        log.info(
            "  cluster #%d [%d arts] rep=%.3f  '%s'",
            cluster.cluster_id, cluster.size, rep,
            cluster.headline_article.title[:50],
        )

    # ── Singleton promotion ────────────────────────────────────────────────
    # If real clusters don't fill 5 slots, promote recent singletons.
    # Each gets a synthetic Cluster with cluster_id < 0.
    # Rep score capped at 0.4 — promoted singletons always rank below
    # genuine multi-article clusters.
    MIN_EVENTS = 5
    if len(scored) < MIN_EVENTS and singletons:
        needed = MIN_EVENTS - len(scored)
        recent = sorted(singletons, key=lambda a: a.published_at, reverse=True)
        log.info(
            "Step 3: Only %d real clusters — promoting up to %d singletons.",
            len(scored), needed,
        )
        for i, art in enumerate(recent[:needed]):
            synth = Cluster(cluster_id=-(i + 1), articles=[art], size=1)
            rep = round(min(0.4, math.log(2) / math.log(max(2, max(
                (c.size for c in clusters), default=1
            ) + 1))), 4)
            insight = _build_trend_insight(synth, rep)
            scored.append(ScoredCluster(
                cluster=synth,
                repetition_score=rep,
                trend_score=rep,
                trend_insight=insight,
                signal_source="singleton",
            ))
            log.info("  promoted singleton: '%s'", art.title[:60])

    # Sort descending, assign rank, flag all candidates for step 4
    scored.sort(key=lambda s: s.trend_score, reverse=True)
    top_n = scored[:TOP_N_CANDIDATES]

    for rank, sc in enumerate(top_n, start=1):
        sc.rank = rank
        sc.for_llm = True   # all candidates go to step 4's two-pass LLM

    log.info(
        "Step 3: %d candidates ranked and passed to step 4 for LLM scoring.",
        len(top_n),
    )
    for sc in top_n:
        log.info(
            "  #%d  rep=%.3f  '%s'",
            sc.rank, sc.trend_score,
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
