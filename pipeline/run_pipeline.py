"""
pipeline/run_pipeline.py — chains M1 → M2 → M3 in memory.

Called by the APScheduler job in app/scheduler.py so the full pipeline
runs in the background without touching disk (no JSON file hop).

Quota-aware:
  - Checks quota_state.json before running — skips LLM entirely if exhausted
    and midnight PT hasn't passed yet.
  - Returns QuotaExhaustedResult when quota is blocking (caller serves cache).
  - Clears quota state after a successful full enrichment.

Public API:
    run_full_pipeline() -> PipelineResult
    PipelineResult.brief        — the Brief (may be None if quota exhausted)
    PipelineResult.quota_blocked — True = quota exhausted, serve cached brief
    PipelineResult.duration_s   — wall-clock seconds
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import Brief
from pipeline.quota_manager import is_quota_exhausted, get_next_refresh_at

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    brief: Brief | None
    quota_blocked: bool
    duration_s: float


def run_full_pipeline() -> PipelineResult:
    """
    Run the complete M1→M2→M3 pipeline in memory.

    Short-circuits immediately if quota_state.json says all Gemini tiers
    are exhausted and the reset time hasn't passed — saves article fetching
    and embedding time (steps 1+2+3 still take ~45s even without LLM calls).

    Returns a PipelineResult:
        .quota_blocked = True   → caller should serve cached DB brief
        .quota_blocked = False  → .brief contains fresh enriched data
    """
    t0 = time.time()

    # ── Quota gate: don't even run if we know quota is exhausted ─────────────
    if is_quota_exhausted():
        next_refresh = get_next_refresh_at()
        next_str = next_refresh.strftime("%H:%M UTC") if next_refresh else "tonight"
        log.info(
            "Pipeline skipped — Gemini quota exhausted. "
            "Serving cached brief. Quota resets at %s.", next_str
        )
        return PipelineResult(brief=None, quota_blocked=True, duration_s=0.0)

    # ── Full pipeline run ─────────────────────────────────────────────────────
    from pipeline.step1_fetch import fetch_all_feeds
    from pipeline.step2_cluster import embed_articles, retry_with_looser_eps
    from pipeline.step3_score import score_clusters
    from pipeline.step4_enrich import enrich_clusters

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

    # Quota got exhausted during this run (enrich returned empty brief)
    if not brief.events and is_quota_exhausted():
        log.warning(
            "Pipeline: quota exhausted mid-run after %.1fs — "
            "returning quota_blocked so scheduler keeps cached brief.", duration_s
        )
        return PipelineResult(brief=None, quota_blocked=True, duration_s=duration_s)

    log.info(
        "Pipeline ✓ complete in %.1fs — %d events enriched",
        duration_s, len(brief.events),
    )
    return PipelineResult(brief=brief, quota_blocked=False, duration_s=duration_s)
