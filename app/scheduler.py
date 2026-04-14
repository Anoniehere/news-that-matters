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

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)


def run_pipeline_job() -> None:
    """
    Execute the full pipeline and persist the result.
    Called by APScheduler — must never raise (logs errors instead).
    """
    # Late imports so scheduler module loads fast at startup
    from app.db import save_brief
    from pipeline.run_pipeline import run_full_pipeline

    log.info("Scheduler ▶ pipeline job starting…")
    try:
        brief, duration_s = run_full_pipeline()
        save_brief(brief, duration_s)
        log.info("Scheduler ✓ pipeline job done in %.1fs", duration_s)
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
    log.info("Scheduler: pipeline job registered — every %d min", interval_min)
    return scheduler
