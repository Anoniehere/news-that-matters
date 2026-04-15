# 📰 News That Matters — Session Context
> Load this file at the start of every AI coding session.
> It is the single source of truth for "where are we and how does this work."

---

## What Is This?

**News That Matters** is a mobile app (iOS + Android) for Silicon Valley professionals (28–45)
that surfaces the **top 5 high-impact US news events** daily — with AI-generated
summaries, causal explanations ("why it matters"), and sector-impact tags.

**Tagline:** *"The news that actually matters to you — explained."*

No login. No social feed. No noise. Pure signal.

---

## Current State

> ⚠️ **This file was regenerated 2026-04-15.** Always update after each session.
> Update `PROGRESS.md` after every session.

| Milestone | Status | Sprint Day |
|-----------|--------|------------|
| M1 — RSS Fetch + Cluster | ✅ Done | Day 1 |
| M2 — Trend Scoring | ✅ Done | Day 2 |
| M3 — LLM Enrichment | 🔄 In progress | Days 3–4 |
| M4 — API + Cache + Scheduler | ✅ Done | Day 5 |
| M5 — Mobile Home Screen | ✅ Done | Days 6–7 |
| M6 — Article List Screen | ✅ Done | Day 8 |
| M7 — Deploy + QA | 🔄 In progress | Days 9–10 |

**Current focus:** M7 Deploy + QA. See `PROGRESS.md` for full task list.

---

## Architecture in 30 Seconds

```
Browser / Mobile App (React Native / Expo)
    ↓ GET /brief
FastAPI Backend  (localhost:8001 dev; Render/Railway prod)
    ├─ GET /             → web/index.html     (light-mode swipe UI — THE only UI)
    ├─ GET /brief        → SQLite cache hit < 500ms
    └─ GET /health
    ↓ reads from
SQLite Cache  (TTL = 1 hour; stale fallback if pipeline fails)
    ↓ written by
Background Pipeline  (APScheduler, every 60 min)
    ├─ Step 1: RSS fetch   (12 Google News feeds, last 4 days)
    ├─ Step 2: Cluster     (MiniLM-L6-v2 + TF-IDF fallback, DBSCAN)
    ├─ Step 3: Pre-filter  (rep_score only → top 15 candidates)
    ├─ Step 4a Pass 1: Batch sector-tag  (1 LLM call, 15 candidates)
    ├─ Step 4b Select:    re-rank 0.70×rep + 0.30×persona → top 5
    ├─ Step 4c Pass 2: Full enrichment   (5 LLM calls, correct top 5)
    └─ Step 5: Write brief to SQLite
         ↓ LLM calls use
Gemini fallback chain:  2.5-flash → 2.0-flash → 1.5-flash
    (all same GEMINI_API_KEY; quota_manager.py tracks daily exhaustion)
```

---

## Tech Stack (locked)

| Layer | Choice | Notes |
|-------|--------|-------|
| Mobile | React Native (Expo SDK 52+) | iOS + Android from one codebase |
| Backend | Python + FastAPI | Async, typed; serves frontend + API |
| Database | SQLite | Cache store only; no user data |
| LLM primary | Gemini 2.5 Flash | `gemini-2.5-flash`; 500 RPD free |
| LLM fallback 1 | Gemini 2.0 Flash | `gemini-2.0-flash`; 1,500 RPD free |
| LLM fallback 2 | Gemini 1.5 Flash | `gemini-1.5-flash`; 1,500 RPD free |
| LLM temp | 0.3 (enrich) / 0.2 (sector-tag) | Never raise above 0.5 |
| Embeddings | sentence-transformers (local) | all-MiniLM-L6-v2, CPU only |
| Clustering | scikit-learn DBSCAN | eps=0.3, min_samples=2 |
| Trend | repetition score only | pytrends + Groq dropped (network blocked) |
| News source | feedparser (Google RSS) | 12 US topic + persona feeds |
| Scheduler | APScheduler | Embedded in FastAPI process |
| Quota mgmt | `pipeline/quota_manager.py` | Persistent state; resets midnight PT |
| Fonts | Plus Jakarta Sans, Inter, Geist Mono | via @expo-google-fonts |

---

## Project File Structure (current — as of 2026-04-15)

```
news-that-matters/
├── pipeline/
│   ├── step1_fetch.py        ← M1: RSS ingestion (12 feeds)
│   ├── step2_cluster.py      ← M1: MiniLM-L6-v2 + TF-IDF fallback + DBSCAN
│   ├── step3_score.py        ← M2: rep_score pre-filter → top 15 candidates
│   ├── step4_enrich.py       ← M3: two-pass LLM (Gemini fallback chain)
│   ├── quota_manager.py      ← NEW: persistent quota state, midnight PT reset
│   └── run_pipeline.py       ← NEW: PipelineResult dataclass; quota gate
├── models/
│   └── schemas.py            ← M3: Pydantic models (Brief, EnrichedEvent, ScoredCluster)
├── app/
│   ├── main.py               ← M4: FastAPI; GET /, /prototype, /brief, /health
│   ├── db.py                 ← M4: SQLite ORM
│   └── scheduler.py          ← M4: APScheduler 60min; respects quota_blocked flag
├── web/
│   └── index.html            ← light-mode swipe-card UI (served at /); THE only UI
│   ├── clusters.json
│   ├── ranked_clusters.json
│   ├── brief.json
│   └── quota_state.json      ← runtime: quota exhaustion state (auto-created/deleted)
├── mobile/
│   ├── screens/
│   │   ├── HomeScreen.tsx    ← M5
│   │   └── ArticleListScreen.tsx ← M6
│   └── components/
│       ├── EventCard.tsx     ← M5
│       ├── TrendBar.tsx      ← M5
│       ├── SectorTag.tsx     ← M5
│       ├── ArticleItem.tsx   ← M6
│       └── DateGroupHeader.tsx ← M6
├── scripts/
│   ├── test_m1.py
│   ├── test_m2.py
│   └── test_m3.py
├── tests/
│   └── test_api.py
├── CONTEXT.md            ← YOU ARE HERE
├── AGENTS.md             ← AI session instructions
├── DECISIONS.md          ← Architecture decision log (24 ADRs)
├── PROGRESS.md           ← Milestone tracker (update every session)
├── PRD.md                ← Full product spec
├── .env                  ← GEMINI_API_KEY (never commit)
└── news_that_matters.db  ← SQLite cache (runtime)
```

---

## Key Product Decisions (the non-negotiables)

- **No auth, no PII.** Fully anonymous. Never add user tracking without explicit approval.
- **Pipeline never blocks the API.** Cache serves users; pipeline runs in background.
- **Hardcoded persona** for MVP — Silicon Valley professional archetype (see `PRD.md §3.1`).
- **Top 5 events shown** to users; pipeline computes top 15 as buffer (ADR-019).
- **All articles in API response**, sorted newest → oldest (UI caps display, not the API).
- **Trend weights:** repetition 70%, persona relevance 30%. pytrends + Reddit deferred (ADR-010, ADR-016).
- **LLM temp = 0.3** (enrich) / **0.2** (batch sector-tag). Never raise enrich above 0.5.
- **No financial advice.** Guardrail in system prompt + UI disclaimer. Non-negotiable.
- **Groq is gone** — groq.com is blocked on Walmart network. Do not add it back without testing connectivity.
- **LLM chain = Gemini only** — 2.5-flash → 2.0-flash → 1.5-flash. Single `GEMINI_API_KEY`.
- **Prototype → Primary UI** — `web/index.html` is the light-mode swipe-card UI (ADR-025).
  Dark OLED retired. No `/prototype` route. One UI, one truth.
  Tab switch ("What Happened" / "Why It Matters") is kept.

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
# Start API server  (⚠️ use python -m uvicorn, NOT .venv/bin/uvicorn — shebang is broken)
cd news-that-matters
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --log-level info
# Then open:
#   http://localhost:8001/       ← light-mode swipe-card UI (THE UI)
#   http://localhost:8001/health ← health check

# Run full pipeline manually
.venv/bin/python pipeline/run_pipeline.py

# Run individual pipeline steps
.venv/bin/python pipeline/step1_fetch.py
.venv/bin/python pipeline/step2_cluster.py
.venv/bin/python pipeline/step3_score.py
.venv/bin/python pipeline/step4_enrich.py

# Smoke tests
.venv/bin/python scripts/test_m1.py
.venv/bin/python scripts/test_m2.py
.venv/bin/python scripts/test_m3.py

# API tests
.venv/bin/python -m pytest tests/ -v

# Clear quota state (if quota_state.json blocking runs)
rm -f output/quota_state.json

# Start mobile
cd mobile && npx expo start

# Install Python deps (new machine)
cd news-that-matters && uv venv && source .venv/bin/activate
uv pip install -r requirements.txt \
  --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple \
  --allow-insecure-host pypi.ci.artifacts.walmart.com
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

*Last updated: 2026-04-15 | Version: 2.1*
