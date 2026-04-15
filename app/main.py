"""
app/main.py — FastAPI application for News That Matters.

Endpoints:
    GET /brief         — returns the current enriched brief (< 500ms cache hit)
    GET /brief/status  — pipeline health: last run time, is_stale, next run

On startup:
    1. init_db()                   — create tables if missing
    2. If DB empty → seed with one pipeline run (blocks until done)
    3. Start background scheduler (hourly refresh)

On shutdown:
    Scheduler stopped gracefully.

NFR compliance (ADR-002):
    - API ALWAYS serves from SQLite cache — pipeline never called in request handler
    - is_stale=True when pipeline is overdue (> 90 min since last run)
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)


# ── Lifespan ────────────────────────────────────────────────────────────────

# Module-level reference to the running scheduler — set in lifespan
_scheduler = None


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, seed if empty, start scheduler. Shutdown: stop scheduler."""
    global _scheduler
    from app.db import has_brief, init_db
    from app.scheduler import build_scheduler, run_pipeline_job

    init_db()

    if not has_brief():
        log.info("DB empty — running initial pipeline (this takes ~45s)…")
        run_pipeline_job()   # blocking on first boot; keeps API from serving 503

    _scheduler = build_scheduler()
    _scheduler.start()
    log.info("News That Matters API ✓ ready")

    yield   # API is serving

    log.info("Shutting down scheduler…")
    _scheduler.shutdown(wait=False)
    _scheduler = None


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="News That Matters API",
    version="1.0.0",
    description="AI-powered trending news intelligence for Silicon Valley professionals.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # mobile app connects from Expo Go — open CORS for MVP
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Project root — one level above app/
_ROOT = Path(__file__).parent.parent

# Serve the frontend and prototype over HTTP (eliminates file:// CORS edge-cases)
app.mount("/web",    StaticFiles(directory=str(_ROOT / "web")),    name="web")
app.mount("/output", StaticFiles(directory=str(_ROOT / "output")), name="output")


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
def serve_ui() -> FileResponse:
    """Serve the main swipe-card UI."""
    return FileResponse(str(_ROOT / "web" / "index.html"))


@app.get("/prototype", include_in_schema=False)
def serve_prototype() -> FileResponse:
    """Serve the light-mode prototype over HTTP (not file://)."""
    return FileResponse(str(_ROOT / "output" / "prototype-v2.html"))

@app.get("/brief")
def get_brief() -> dict[str, Any]:
    """
    Returns the latest enriched brief from SQLite cache.
    Never calls the pipeline — always < 500ms.

    Quota-aware: if Gemini daily quota is exhausted, the response includes
    `quota_exhausted=True`, `last_refreshed_at`, and `next_refresh_at` so
    the frontend can display a non-breaking "Last updated" indicator.
    The events array is always present — UX never breaks.
    """
    from app.db import load_current_brief
    from pipeline.quota_manager import is_quota_exhausted, get_next_refresh_at

    brief, meta = load_current_brief()
    if brief is None:
        raise HTTPException(
            status_code=503,
            detail="Brief not yet available — pipeline is running. Retry in ~60s.",
        )

    quota_hit      = is_quota_exhausted()
    next_refresh   = get_next_refresh_at()
    last_refreshed = meta["created_at"]   # ISO string from DB

    # Attach quota metadata to brief before serialising
    brief.quota_exhausted    = quota_hit
    brief.last_refreshed_at  = datetime.fromisoformat(last_refreshed)
    brief.next_refresh_at    = next_refresh

    return {
        "brief": brief.model_dump(mode="json"),
        "meta": {
            **meta,
            "quota_exhausted":  quota_hit,
            "next_refresh_at":  next_refresh.isoformat() if next_refresh else None,
            "last_refreshed_at": last_refreshed,
        },
    }


@app.get("/brief/status")
def get_status() -> dict[str, Any]:
    """
    Pipeline health endpoint.
    Returns last run time, staleness, age, and next scheduled run.
    """
    from app.db import load_current_brief

    _, meta = load_current_brief()
    if meta is None:
        return {
            "status": "initialising",
            "is_stale": True,
            "message": "Pipeline has not completed its first run yet.",
        }

    next_run: str | None = None
    if _scheduler is not None:
        job = _scheduler.get_job("pipeline")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()

    return {
        "status": "stale" if meta["is_stale"] else "fresh",
        "is_stale": meta["is_stale"],
        "last_refreshed_at": meta["created_at"],
        "age_minutes": meta["age_minutes"],
        "pipeline_duration_s": meta["pipeline_duration_s"],
        "next_run_at": next_run,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Lightweight liveness check for Railway/Render health probes."""
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}
