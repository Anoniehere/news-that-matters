"""
app/scheduler.py — APScheduler background pipeline job.

Runs the full M1→M2→M3 pipeline every PIPELINE_INTERVAL_MINUTES minutes.
Results are written to SQLite so the API always serves from cache.

Rules (per AGENTS.md + ADR-002):
  - max_instances=1 — never run two pipeline jobs concurrently
  - On failure: log error, keep serving last good brief (is_stale handles display)
  - Interval configurable via PIPELINE_INTERVAL_MINUTES env var (default: 60)

Public API:
    build_scheduler()  — creates and returns a configured BackgroundScheduler
    run_pipeline_job() — the job function (also callable directly for seeding)
"""
from __future__ import annotations

import logging
import os
import urllib.request

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)


def _keepalive_ping() -> None:
    """Ping /health on Render every 14 min to prevent free-tier sleep.

    Render spins down instances after 15 min of inactivity — this keeps
    the app always warm so visitors never hit the cold-start splash screen.
    Only runs when RENDER_EXTERNAL_URL is set (i.e. on Render, not locally).
    """
    base_url = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
    if not base_url:
        return  # not on Render — skip silently
    try:
        urllib.request.urlopen(f"{base_url}/health", timeout=10)  # noqa: S310
        log.debug("Keepalive ✓ pinged %s/health", base_url)
    except Exception as exc:  # noqa: BLE001
        log.debug("Keepalive ping failed (non-fatal): %s", exc)


def run_pipeline_job() -> None:
    """
    Execute the full pipeline and persist the result.
    Called by APScheduler — must never raise (logs errors instead).

    Quota-aware: if all Gemini tiers are exhausted the job returns early
    without touching the DB, so the last good brief keeps serving.
    """
    from app.db import save_brief
    from pipeline.run_pipeline import run_full_pipeline

    log.info("Scheduler ▶ pipeline job starting…")
    try:
        result = run_full_pipeline()

        if result.quota_blocked:
            log.info(
                "Scheduler: quota exhausted — keeping cached brief in DB. "
                "Pipeline will retry after Gemini quota resets at midnight PT."
            )
            return   # cached brief stays current, no DB write

        save_brief(result.brief, result.duration_s)
        log.info("Scheduler ✓ pipeline job done in %.1fs", result.duration_s)

    except Exception as exc:
        log.error(
            "Scheduler ✗ pipeline job FAILED — last brief stays current. Error: %s",
            exc, exc_info=True,
        )


def build_scheduler() -> BackgroundScheduler:
    """
    Build a BackgroundScheduler with the pipeline job registered.
    Call .start() after building; call .shutdown() on teardown.
    """
    interval_min = int(os.getenv("PIPELINE_INTERVAL_MINUTES", "60"))

    scheduler = BackgroundScheduler(
        job_defaults={"max_instances": 1, "coalesce": True},
        timezone="UTC",
    )
    scheduler.add_job(
        run_pipeline_job,
        trigger=IntervalTrigger(minutes=interval_min, timezone="UTC"),
        id="pipeline",
        name="News That Matters full pipeline",
        replace_existing=True,
    )
    scheduler.add_job(
        _keepalive_ping,
        trigger=IntervalTrigger(minutes=14, timezone="UTC"),
        id="keepalive",
        name="Render keepalive ping",
        replace_existing=True,
    )
    log.info("Scheduler: pipeline every %d min · keepalive every 14 min", interval_min)
    return scheduler
