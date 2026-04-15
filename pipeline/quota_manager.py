"""
pipeline/quota_manager.py — Gemini daily quota state management.

Tracks whether all Gemini model tiers have hit their daily RPD limit.
Quota resets at midnight Pacific Time — calculated exactly, not guessed.

Public API:
    next_midnight_pt()        → datetime (UTC) of next midnight Pacific Time
    write_quota_exhausted()   → persist quota_state.json; called by step4
    clear_quota_state()       → delete quota_state.json; called after success
    is_quota_exhausted()      → True if quota hit AND midnight hasn't passed yet
    get_next_refresh_at()     → datetime | None; None = quota not exhausted
    get_quota_state()         → full dict | None

State file: output/quota_state.json
{
    "exhausted_at": "2026-04-15T14:32:00Z",
    "next_refresh_at": "2026-04-16T07:00:00Z",   <- midnight PT in UTC
    "models_tried": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
}
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

QUOTA_STATE_PATH = Path("output/quota_state.json")
PT = ZoneInfo("America/Los_Angeles")


def next_midnight_pt() -> datetime:
    """Return the next midnight Pacific Time as a UTC datetime."""
    now_pt = datetime.now(PT)
    # Advance to the next calendar day at 00:00 PT
    next_day_pt = (now_pt + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return next_day_pt.astimezone(timezone.utc)


def write_quota_exhausted(models_tried: list[str]) -> None:
    """
    Persist quota exhaustion state to disk.
    Called by step4_enrich when all Gemini model tiers return DailyQuotaError.
    """
    QUOTA_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "exhausted_at":   datetime.now(timezone.utc).isoformat(),
        "next_refresh_at": next_midnight_pt().isoformat(),
        "models_tried":   models_tried,
    }
    QUOTA_STATE_PATH.write_text(json.dumps(state, indent=2))
    log.warning(
        "Quota state written — all Gemini tiers exhausted. "
        "Next refresh at %s PT.", next_midnight_pt().astimezone(PT).strftime("%H:%M %Z %b %d")
    )


def clear_quota_state() -> None:
    """
    Delete quota state file after a successful pipeline run.
    Called by run_pipeline.py when LLM enrichment succeeds.
    """
    if QUOTA_STATE_PATH.exists():
        QUOTA_STATE_PATH.unlink()
        log.info("Quota state cleared — fresh quota available.")


def get_quota_state() -> dict | None:
    """Return the raw quota state dict, or None if no state file exists."""
    if not QUOTA_STATE_PATH.exists():
        return None
    try:
        return json.loads(QUOTA_STATE_PATH.read_text())
    except Exception as exc:
        log.warning("Corrupt quota_state.json — ignoring. Error: %s", exc)
        return None


def is_quota_exhausted() -> bool:
    """
    True if quota was exhausted today AND midnight PT hasn't passed yet.
    Once midnight passes, quota is considered reset — pipeline should retry.
    """
    state = get_quota_state()
    if state is None:
        return False
    try:
        next_refresh = datetime.fromisoformat(state["next_refresh_at"])
        return datetime.now(timezone.utc) < next_refresh
    except (KeyError, ValueError):
        return False


def get_next_refresh_at() -> datetime | None:
    """
    Return the next refresh datetime (UTC) when quota resets.
    Returns None if quota is not currently exhausted.
    """
    if not is_quota_exhausted():
        return None
    state = get_quota_state()
    if state is None:
        return None
    try:
        return datetime.fromisoformat(state["next_refresh_at"])
    except (KeyError, ValueError):
        return None
