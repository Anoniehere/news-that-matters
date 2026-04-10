"""
pipeline/run_pipeline.py — chains M1 → M2 → M3 in memory.

Called by the APScheduler job in app/scheduler.py so the full pipeline
runs in the background without touching disk (no JSON file hop).

Public API: run_full_pipeline() -> Brief
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import Brief
from pipeline.step1_fetch import fetch_all_feeds
from pipeline.step2_cluster import embed_articles, retry_with_looser_eps
from pipeline.step3_score import score_clusters
from pipeline.step4_enrich import enrich_clusters

log = logging.getLogger(__name__)

EPS_BASE = 0.65   # DBSCAN epsilon — must match step2_cluster default


def run_full_pipeline() -> tuple[Brief, float]:
    """
    Run the complete M1→M2→M3 pipeline in memory.

    Returns:
        brief       — enriched Brief object ready for the API
        duration_s  — wall-clock seconds for the full run
    """
    t0 = time.time()

    log.info("Pipeline ▶ Step 1 — fetching articles…")
    fetch = fetch_all_feeds()

    log.info("Pipeline ▶ Step 2 — embedding + clustering…")
    embeddings, eps = embed_articles(fetch.articles)
    clusters = retry_with_looser_eps(fetch.articles, embeddings, base_eps=eps)

    log.info("Pipeline ▶ Step 3 — trend scoring…")
    trend = score_clusters(clusters)

    log.info("Pipeline ▶ Step 4 — LLM enrichment…")
    brief = enrich_clusters(trend)

    duration_s = time.time() - t0
    log.info(
        "Pipeline ✓ complete in %.1fs — %d events enriched",
        duration_s, len(brief.events),
    )
    return brief, duration_s
