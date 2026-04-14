"""
app/db.py — SQLite persistence layer for News That Matters.

Stores the latest enriched Brief as JSON. One row is always current
(is_current=1). New briefs flip the flag atomically to prevent serving
a partial or stale result during writes.

Public API:
    init_db()                    — create tables if not exists
    save_brief(brief, duration)  — persist + flip is_current atomically
    load_current_brief()         — returns (Brief, meta) or (None, None)
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
