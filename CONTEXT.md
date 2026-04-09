# ⚡ Signal Brief — Session Context
> Load this file at the start of every AI coding session.
> It is the single source of truth for "where are we and how does this work."

---

## What Is This?

**Signal Brief** is a mobile app (iOS + Android) for Silicon Valley professionals (28–45)
that surfaces the **top 5 high-impact US news events** daily — with AI-generated
summaries, causal explanations ("why it matters"), and sector-impact tags.

**Tagline:** *"The news that actually matters to you — explained."*

No login. No social feed. No noise. Pure signal.

---

## Current State

> ⚠️ **PRE-CODE** — All milestones are unstarted as of 2026-04-08.
> Update `PROGRESS.md` after every session.

| Milestone | Status |
|-----------|--------|
| M1 — RSS Fetch + Cluster | 🔲 Not started |
| M2 — Trend Scoring | 🔲 Not started |
| M3 — LLM Enrichment | 🔲 Not started |
| M4 — API + Cache + Scheduler | 🔲 Not started |
| M5 — Mobile Home Screen | 🔲 Not started |
| M6 — Article List Screen | 🔲 Not started |
| M7 — Deploy + QA | 🔲 Not started |

**Current focus:** → Start M1. See `PROGRESS.md` for exit criteria.

---

## Architecture in 30 Seconds

```
Mobile App (React Native / Expo)
    ↓ GET /brief
FastAPI Backend
    ↓ reads from
SQLite Cache (TTL = 1 hour)
    ↓ written by
Background Pipeline (APScheduler, runs every 60 min)
    ├── Step 1: RSS fetch (Google News feeds, last 4 days)
    ├── Step 2: Cluster articles (sentence-transformers + DBSCAN)
    ├── Step 3: Trend score (repetition 55% + Reddit 22.5% + Google Trends 22.5%)
    ├── Step 4: LLM enrich top 5 (Groq API, llama-3.3-70b-versatile)
    └── Step 5: Write brief to SQLite
```

---

## Tech Stack (locked)

| Layer | Choice | Notes |
|-------|--------|-------|
| Mobile | React Native (Expo SDK 52+) | iOS + Android from one codebase |
| Backend | Python + FastAPI | Async, typed |
| Database | SQLite | Cache store only; no user data |
| LLM | Groq API — llama-3.3-70b-versatile | Free tier; fallback = Gemini Flash |
| Embeddings | sentence-transformers (local) | all-MiniLM-L6-v2, CPU only |
| Clustering | scikit-learn DBSCAN | eps=0.3, min_samples=2 |
| Trend | pytrends + PRAW | Google Trends + Reddit; free |
| News source | feedparser (Google RSS) | 5 US topic feeds |
| Scheduler | APScheduler | Embedded in FastAPI process |
| Fonts | Plus Jakarta Sans, Inter, Geist Mono | via @expo-google-fonts |

---

## Project File Structure (target — builds up as milestones complete)

```
signal-brief/
├── pipeline/
│   ├── step1_fetch.py        ← M1: RSS ingestion
│   ├── step2_cluster.py      ← M1: embeddings + DBSCAN
│   ├── step3_score.py        ← M2: trend scoring
│   └── step4_enrich.py       ← M3: LLM enrichment
├── models/
│   └── schemas.py            ← M3: Pydantic models for all data shapes
├── app/
│   ├── main.py               ← M4: FastAPI app + routes
│   ├── db.py                 ← M4: SQLite ORM
│   └── scheduler.py          ← M4: APScheduler hourly job
├── mobile/
│   ├── screens/
│   │   ├── HomeScreen.tsx    ← M5
│   │   └── ArticleListScreen.tsx ← M6
│   └── components/
│       ├── EventCard.tsx     ← M5
│       ├── TrendBar.tsx      ← M5
│       ├── SectorTag.tsx     ← M5
│       ├── SkeletonCard.tsx  ← M5
│       ├── ArticleItem.tsx   ← M6
│       └── DateGroupHeader.tsx ← M6
├── scripts/
│   └── test_m1.py            ← M1 smoke test
├── tests/
│   ├── test_api.py           ← M4 API tests
│   └── test_hallucination_guard.py ← M3 guardrail tests
├── output/                   ← gitignored; local test artifacts
│   ├── clusters.json
│   ├── ranked_clusters.json
│   └── brief.json
├── CONTEXT.md                ← YOU ARE HERE
├── AGENTS.md                 ← AI session instructions
├── DECISIONS.md              ← Architecture decision log
├── PROGRESS.md               ← Milestone tracker (update every session)
└── PRD.md                    ← Full product spec
```

---

## Key Product Decisions (the non-negotiables)

- **No auth, no PII.** Fully anonymous. Never add user tracking without explicit approval.
- **Pipeline never blocks the API.** Cache serves users; pipeline runs in background.
- **Hardcoded persona** for MVP — Silicon Valley professional archetype (see `PRD.md §3.1`).
- **Top 5 events shown** to users; pipeline computes top 7 as buffer.
- **All articles in API response**, sorted newest → oldest (UI caps display, not the API).
- **Trend weights:** repetition 55%, Reddit 22.5%, Google Trends 22.5%. Do not change without logging in `DECISIONS.md`.
- **LLM temp = 0.3.** Lower is better for factuality. Never raise above 0.5.
- **No financial advice.** Guardrail in system prompt + UI disclaimer. Non-negotiable.

---

## Persona Prompt (used in LLM calls — do not modify without PM approval)

```
This user is a Silicon Valley professional who values concise, signal-rich information.
They care about: tech industry trends, US policy impact on tech, investment signals,
startup ecosystem dynamics, AI developments, and macroeconomic shifts.
They have ~90 seconds to absorb this event. Tailor explanations accordingly.
```

---

## Quick Commands (copy-paste ready)

```bash
# Install Python deps (backend)
cd signal-brief && uv venv && source .venv/bin/activate
uv pip install fastapi uvicorn apscheduler sentence-transformers \
  scikit-learn feedparser praw pytrends groq pydantic sqlmodel \
  --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple \
  --allow-insecure-host pypi.ci.artifacts.walmart.com

# Run a pipeline step (once M1–M3 exist)
python pipeline/step1_fetch.py
python pipeline/step2_cluster.py
python pipeline/step3_score.py
python pipeline/step4_enrich.py

# Run the API server (once M4 exists)
uvicorn app.main:app --reload --port 8000

# Run all tests
python -m pytest tests/ -v

# Start mobile (once M5 exists)
cd mobile && npx expo start
```

---

## Related Docs

| File | Purpose |
|------|---------|
| `PRD.md` | Full product spec, API contracts, UX wireframes, design system |
| `AGENTS.md` | AI coding instructions — conventions, patterns, anti-patterns |
| `DECISIONS.md` | Architecture Decision Record log |
| `PROGRESS.md` | Live milestone tracker — update after every session |

---

*Last updated: 2026-04-08 | Version: 1.0*
