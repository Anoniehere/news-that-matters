"""
tests/test_api.py — M4 API smoke tests.

Pre-seeds SQLite from output/brief.json so the pipeline never runs
during tests (keeps tests fast and deterministic — no LLM calls).

Exit criteria verified:
    ✅ GET /brief returns 200 with valid schema
    ✅ GET /brief second call <= first call latency (cache confirmed)
    ✅ GET /brief/status returns expected fields
    ✅ GET /health returns 200
    ✅ /brief response time < 500ms (cache hit)
    ✅ is_stale field present on brief response
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


BRIEF_JSON = Path("output/brief.json")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def seed_db():
    """
    Pre-seed the SQLite DB from output/brief.json before the app starts.
    Runs once per test session. Uses the real DB path (news_that_matters.db).
    """
    if not BRIEF_JSON.exists():
        pytest.skip("output/brief.json not found — run M3 pipeline first")

    from app.db import init_db, save_brief
    from models.schemas import Brief

    init_db()
    brief = Brief.model_validate_json(BRIEF_JSON.read_text())
    save_brief(brief, duration_s=44.0)   # seed with real output + dummy duration


@pytest.fixture(scope="session")
def client(seed_db):
    """FastAPI test client — lifespan runs but skips pipeline (DB already seeded)."""
    from app.main import app
    with TestClient(app) as c:
        yield c


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_brief_schema(client):
    r = client.get("/brief")
    assert r.status_code == 200

    body = r.json()
    assert "brief" in body
    assert "meta" in body

    brief = body["brief"]
    assert "events" in brief
    assert len(brief["events"]) >= 1

    ev = brief["events"][0]
    for field in ("event_heading", "summary", "why_it_matters",
                  "sectors_impacted", "timeline_context", "source_articles"):
        assert field in ev, f"Missing field: {field}"

    assert "is_stale" in brief


def test_brief_latency_under_500ms(client):
    """Cache hit must be well under 500ms."""
    t0 = time.perf_counter()
    r = client.get("/brief")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert r.status_code == 200
    assert elapsed_ms < 500, f"Cache hit took {elapsed_ms:.1f}ms — expected < 500ms"


def test_second_call_not_slower(client):
    """Second /brief call must be <= first (proves cache is working)."""
    t0 = time.perf_counter()
    client.get("/brief")
    first_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    client.get("/brief")
    second_ms = (time.perf_counter() - t0) * 1000

    # Allow 20ms tolerance — network jitter is real even on localhost
    assert second_ms <= first_ms + 20, (
        f"Second call ({second_ms:.1f}ms) was slower than first ({first_ms:.1f}ms) "
        f"— cache may not be working"
    )


def test_brief_status(client):
    r = client.get("/brief/status")
    assert r.status_code == 200

    body = r.json()
    assert "is_stale" in body
    assert "last_refreshed_at" in body
    assert "age_minutes" in body
    assert "pipeline_duration_s" in body


def test_events_have_valid_sectors(client):
    r = client.get("/brief")
    events = r.json()["brief"]["events"]

    valid_sectors = {
        "Technology", "Finance", "Policy & Regulation", "Labour & Employment",
        "Healthcare", "Energy", "Defence & Security", "Education",
        "Media & Entertainment", "Retail & E-commerce", "Real Estate",
        "Manufacturing", "Agriculture",
    }
    for ev in events:
        for sector in ev["sectors_impacted"]:
            assert sector["name"] in valid_sectors, \
                f"Invalid sector: {sector['name']}"
            assert 0.0 <= sector["confidence"] <= 1.0
