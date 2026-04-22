"""
app/db.py — SQLite persistence layer for News That Matters.

Stores the latest enriched Brief as JSON. One row is always current
(is_current=1). New briefs flip the flag atomically to prevent serving
a partial or stale result during writes.

Also stores pipeline_runs for the logs & traces dashboard.

Public API:
    init_db()                    — create tables if not exists
    save_brief(brief, duration)  — persist + flip is_current atomically
    load_current_brief()         — returns (Brief, meta) or (None, None)
    log_pipeline_run(...)        — append a run record to pipeline_runs
    get_recent_runs(limit)       — last N run rows as list[dict]
"""
from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from models.schemas import Brief

log = logging.getLogger(__name__)

DB_PATH = Path("news_that_matters.db")   # relative to CWD (project root)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS briefs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    payload             TEXT    NOT NULL,
    pipeline_duration_s REAL    NOT NULL DEFAULT 0,
    is_current          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT    NOT NULL
);
"""

_CREATE_IDX = """
CREATE INDEX IF NOT EXISTS idx_briefs_current ON briefs (is_current);
"""

_CREATE_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at       TEXT    NOT NULL,
    finished_at      TEXT    NOT NULL,
    duration_s       REAL    NOT NULL DEFAULT 0,
    status           TEXT    NOT NULL,
    articles_fetched INTEGER NOT NULL DEFAULT 0,
    clusters_found   INTEGER NOT NULL DEFAULT 0,
    events_enriched  INTEGER NOT NULL DEFAULT 0,
    step_timings     TEXT    NOT NULL DEFAULT '{}',
    error_message    TEXT
);
"""

_CREATE_RUNS_IDX = """
CREATE INDEX IF NOT EXISTS idx_runs_started ON pipeline_runs (started_at DESC);
"""


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    """Yield an autocommitting WAL-mode connection."""
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL;")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """Create tables and indexes if they don't exist."""
    with _conn() as con:
        con.execute(_CREATE_TABLE)
        con.execute(_CREATE_IDX)
        con.execute(_CREATE_RUNS_TABLE)
        con.execute(_CREATE_RUNS_IDX)
    log.info("DB: initialised at %s", DB_PATH.resolve())


def save_brief(brief: Brief, duration_s: float = 0.0) -> None:
    """
    Persist a new brief and atomically mark it as current.
    Previous rows have is_current cleared first to prevent a window
    where no current brief exists.
    """
    payload = brief.model_dump_json()
    now = datetime.now(timezone.utc).isoformat()

    with _conn() as con:
        con.execute("UPDATE briefs SET is_current = 0")
        con.execute(
            "INSERT INTO briefs (payload, pipeline_duration_s, is_current, created_at)"
            " VALUES (?, ?, 1, ?)",
            (payload, duration_s, now),
        )
    log.info("DB: brief saved (%.1fs pipeline, %d events)", duration_s, len(brief.events))


def load_current_brief() -> tuple[Brief, dict] | tuple[None, None]:
    """
    Load the current brief and its metadata.

    Returns:
        (brief, meta) where meta = {pipeline_duration_s, created_at, is_stale}
        (None, None)  if the table is empty
    """
    with _conn() as con:
        row = con.execute(
            "SELECT payload, pipeline_duration_s, created_at"
            " FROM briefs WHERE is_current = 1 LIMIT 1"
        ).fetchone()

    if not row:
        return None, None

    payload, duration_s, created_at_str = row
    brief = Brief.model_validate_json(payload)

    # Stale = pipeline hasn't run in > 90 min (1.5× scheduled interval)
    created_at = datetime.fromisoformat(created_at_str)
    age_s = (datetime.now(timezone.utc) - created_at).total_seconds()
    is_stale = age_s > 90 * 60

    brief.is_stale = is_stale
    meta = {
        "pipeline_duration_s": duration_s,
        "created_at": created_at_str,
        "is_stale": is_stale,
        "age_minutes": round(age_s / 60, 1),
    }
    return brief, meta


def has_brief() -> bool:
    """True if at least one brief is in the DB."""
    with _conn() as con:
        count = con.execute(
            "SELECT COUNT(*) FROM briefs WHERE is_current = 1"
        ).fetchone()[0]
    return count > 0


def log_pipeline_run(
    *,
    started_at: str,
    finished_at: str,
    duration_s: float,
    status: str,
    articles_fetched: int = 0,
    clusters_found: int = 0,
    events_enriched: int = 0,
    step_timings: dict | None = None,
    error_message: str | None = None,
) -> None:
    """
    Append one pipeline run record to pipeline_runs.

    status: 'success' | 'quota_blocked' | 'error'
    step_timings: {"fetch": s, "cluster": s, "score": s, "enrich": s}
    """
    with _conn() as con:
        con.execute(
            """
            INSERT INTO pipeline_runs
                (started_at, finished_at, duration_s, status,
                 articles_fetched, clusters_found, events_enriched,
                 step_timings, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_at, finished_at, duration_s, status,
                articles_fetched, clusters_found, events_enriched,
                json.dumps(step_timings or {}), error_message,
            ),
        )
    log.info("DB: run logged — status=%s  %.1fs", status, duration_s)


def get_recent_runs(limit: int = 30) -> list[dict]:
    """Return the last `limit` pipeline runs, newest first."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT id, started_at, finished_at, duration_s, status,
                   articles_fetched, clusters_found, events_enriched,
                   step_timings, error_message
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id":               r[0],
            "started_at":       r[1],
            "finished_at":      r[2],
            "duration_s":       r[3],
            "status":           r[4],
            "articles_fetched": r[5],
            "clusters_found":   r[6],
            "events_enriched":  r[7],
            "step_timings":     json.loads(r[8]),
            "error_message":    r[9],
        }
        for r in rows
    ]
