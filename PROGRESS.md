# 📊 Signal Brief — Progress Tracker
> Update this file at the END of every session.
> It is the AI's memory between sessions — if it's not here, it didn't happen.

---

## How to Update This File

At the end of each session:
1. Check off completed exit criteria
2. Move milestone status to ✅ / 🔄 / 🔲
3. Fill in "Last Worked On" date
4. Write "Next Session: Start Here" section
5. Log any blockers, surprises, or scope changes
6. Commit: `docs(progress): update M[N] status — [what was done]`

---

## Current Focus

```
▶ ACTIVE MILESTONE:  M1 — RSS Fetch + Article Clustering
  Start date:        Not started
  Target complete:   Day 1  (2-week sprint plan)
  Blocking anything: M2, M3, M4, M5, M6, M7 (all depend on M1)
```

---

## 2-Week Sprint Plan  ← ACTIVE PLAN

> Feasibility analysis in FEASIBILITY.md. 3 scope cuts applied (ADR-010, 011, 012).
> Reddit dropped → weights now: Repetition 70% / Google Trends 30%.
> Skeleton → ActivityIndicator. TestFlight → Expo Go QR.

### Week 1 — Backend (Days 1–5)

| Day | Milestone | Deliverable |
|-----|-----------|-------------|
| 1 | M1 | `step1_fetch.py` + `step2_cluster.py` → `clusters.json` ✓ |
| 2 | M2 | `step3_score.py` (rep + pytrends only) → `ranked_clusters.json` ✓ |
| 3 | M3a | `step4_enrich.py` + `schemas.py` → first `brief.json` |
| 4 | M3b | Prompt iteration + guardrail tests → `brief.json` passing ✓ |
| 5 | M4 | FastAPI + SQLite + scheduler + tests → API live on Railway ✓ |

### Week 2 — Mobile (Days 6–10)

| Day | Milestone | Deliverable |
|-----|-----------|-------------|
| 6 | M5a | Expo scaffold + EventCard + SectorTag + TrendBar |
| 7 | M5b | HomeScreen + FlatList + API integration + loading state ✓ |
| 8 | M6 | ArticleListScreen + ArticleItem + DateGroupHeader + nav ✓ |
| 9 | QA | Device testing + 50-run LLM red-team + contrast check |
| 10 | Bufr | Fix slippage · final API URL · share Expo Go QR 🚀 |

---

## Milestone Status

| # | Milestone | Status | Sprint Day | Started | Completed |
|---|-----------|--------|------------|---------|-----------|
| M1 | RSS Fetch + Cluster | 🔲 Not started | Day 1 | — | — |
| M2 | Trend Scoring (rep + pytrends) | 🔲 Not started | Day 2 | — | — |
| M3 | LLM Enrichment | 🔲 Not started | Days 3–4 | — | — |
| M4 | API + Cache + Scheduler | 🔲 Not started | Day 5 | — | — |
| M5 | Mobile Home Screen | 🔲 Not started | Days 6–7 | — | — |
| M6 | Article List Screen | 🔲 Not started | Day 8 | — | — |
| M7 | Deploy + QA | 🔲 Not started | Days 9–10 | — | — |

**Status legend:** 🔲 Not started | 🔄 In progress | ✅ Done | 🚧 Blocked

---

## M1 — RSS Fetch + Article Clustering

**Target:** Days 1–3 | **Status:** 🔲 Not started

### Exit Criteria
- [ ] `pipeline/step1_fetch.py` — fetches from 5 Google News RSS feeds
- [ ] `pipeline/step2_cluster.py` — embeddings + DBSCAN clustering
- [ ] `scripts/test_m1.py` — smoke test runner
- [ ] ≥ 20 articles fetched across feeds
- [ ] ≥ 3 distinct clusters produced
- [ ] All articles have `published_at` within last 4 days
- [ ] `output/clusters.json` validates against schema
- [ ] Runtime ≤ 60 seconds

### Notes
*(Add session notes here as work progresses)*

---

## M2 — Trend Scoring Engine

**Target:** Days 4–6 | **Status:** 🔲 Not started

### Exit Criteria
- [ ] `pipeline/step3_score.py` — repetition + pytrends + Reddit PRAW
- [ ] `output/ranked_clusters.json` — clusters with trend_score, sorted
- [ ] Every cluster has `trend_score` in [0.0, 1.0]
- [ ] Scores reproducible within ±5% on re-run
- [ ] Top 7 clusters identified; top 5 flagged for LLM
- [ ] Reddit API auth works with credentials in `.env`
- [ ] pytrends calls have 2s sleep between queries
- [ ] Runtime ≤ 90 seconds

### Notes
*(Add session notes here as work progresses)*

---

## M3 — LLM Enrichment

**Target:** Days 7–10 | **Status:** 🔲 Not started

### Exit Criteria
- [ ] `pipeline/step4_enrich.py` — Groq API integration
- [ ] `models/schemas.py` — Pydantic models for all LLM output fields
- [ ] `output/brief.json` — full enriched brief (5 events)
- [ ] `tests/test_hallucination_guard.py` — guardrail tests
- [ ] All 5 events have valid heading / summary / why_it_matters / sectors / timeline
- [ ] Pydantic validation passes without retry on ≥ 80% of runs
- [ ] `summary` is 4–8 lines; `why_it_matters` is 4–8 lines
- [ ] `sectors_impacted` has 1–5 items, sorted by confidence desc
- [ ] No financial advice in any output
- [ ] No invented facts in spot-check of 3 events
- [ ] Groq call latency < 8s per event
- [ ] Full M1+M2+M3 pipeline end-to-end ≤ 5 minutes

### Notes
*(Add session notes here as work progresses)*

---

## M4 — Backend API + Cache + Scheduler

**Target:** Days 11–14 | **Status:** 🔲 Not started

### Exit Criteria
- [ ] `app/main.py` — FastAPI app with `/brief` and `/brief/status`
- [ ] `app/db.py` — SQLite schema + ORM layer
- [ ] `app/scheduler.py` — APScheduler hourly job, max_instances=1
- [ ] `tests/test_api.py` — API smoke tests
- [ ] `GET /brief` returns valid JSON in < 500ms (cache hit)
- [ ] `GET /brief/status` returns pipeline health metadata
- [ ] Scheduler fires every 60 min; logs start/end/duration
- [ ] Stale fallback: pipeline error → last brief served with `is_stale: true`
- [ ] Second `/brief` call not slower than first (cache confirmed working)
- [ ] All API smoke tests pass

### Notes
*(Add session notes here as work progresses)*

---

## M5 — Mobile Home Screen

**Target:** Days 15–19 | **Status:** 🔲 Not started

### Exit Criteria
- [ ] `mobile/` — Expo project scaffold
- [ ] `mobile/screens/HomeScreen.tsx` — FlatList of EventCards
- [ ] `mobile/components/EventCard.tsx` — full card per PRD §8.6
- [ ] `mobile/components/TrendBar.tsx` — animated trend bar
- [ ] `mobile/components/SectorTag.tsx` — color-coded sector chips
- [ ] `mobile/components/SkeletonCard.tsx` — loading skeleton
- [ ] 5 event cards render with full content (heading, summary, why it matters, tags)
- [ ] Trend bar animates on mount (600ms); correct color per threshold
- [ ] Sector tags render correct colors per PRD §8.2 color map
- [ ] Pull-to-refresh calls API and updates cards
- [ ] Skeleton shown on first load / error state
- [ ] "Last updated X min ago" subheader is accurate
- [ ] All tap targets ≥ 44pt
- [ ] Fonts (Plus Jakarta Sans, Inter, Geist Mono) render correctly

### Notes
*(Add session notes here as work progresses)*

---

## M6 — Article List Screen

**Target:** Days 20–22 | **Status:** 🔲 Not started

### Exit Criteria
- [ ] `mobile/screens/ArticleListScreen.tsx` — full article list per PRD §8.8
- [ ] `mobile/components/ArticleItem.tsx` — single article row
- [ ] `mobile/components/DateGroupHeader.tsx` — date section headers
- [ ] Tap EventCard → navigate to ArticleListScreen for that event
- [ ] Articles listed newest → oldest, grouped by calendar day
- [ ] Relative timestamps correct ("2 hours ago", "Yesterday", date string)
- [ ] Tap article → opens in `expo-web-browser` (in-app sheet)
- [ ] Share button → native share sheet with heading + source count
- [ ] Sticky disclaimer footer always visible
- [ ] Back navigation works (← and swipe gesture)
- [ ] All items labelled for screen reader

### Notes
*(Add session notes here as work progresses)*

---

## M7 — Deploy + QA

**Target:** Days 23–27 | **Status:** 🔲 Not started

### Exit Criteria
- [ ] FastAPI API deployed to Render/Railway/Fly.io (HTTPS, always-on)
- [ ] Mobile app configured to production API URL (not localhost)
- [ ] App loads in < 1s on production API (measured from device)
- [ ] Pipeline runs successfully on server ≥ 3 consecutive times
- [ ] 50-run red-team: 0 financial advice outputs, 0 flagged hallucinations
- [ ] WCAG 2.2 AA contrast verified (dark + light mode)
- [ ] E2E: home loads → tap card → article list → tap article → browser
- [ ] TestFlight build submitted + installable on test device
- [ ] App icon + splash screen render correctly on iOS + Android
- [ ] `is_stale` banner appears if pipeline down > 2 hours

### Notes
*(Add session notes here as work progresses)*

---

## Next Session: Start Here

```
► START M1 — Day 1 of 10.

Setup (do this first — ~45 min):
  1. mkdir pipeline output scripts models tests && touch .env
  2. uv venv && source .venv/bin/activate
  3. uv pip install fastapi uvicorn apscheduler sentence-transformers \
       scikit-learn feedparser pytrends groq pydantic sqlmodel python-dotenv \
       --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/\
externa-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
  4. Add to .env:  GROQ_API_KEY=gsk_...
  5. Get Groq key free at https://console.groq.com (no credit card)

Then build:
  pipeline/step1_fetch.py   ← RSS fetch from 5 Google News feeds
  pipeline/step2_cluster.py ← embeddings + DBSCAN
  scripts/test_m1.py        ← smoke test; outputs output/clusters.json

Done when: python scripts/test_m1.py prints ≥20 articles in ≥3 clusters.
```

---

## Blockers Log

| Date | Blocker | Impact | Resolution |
|------|---------|--------|------------|
| — | None yet | — | — |

---

## Scope Change Log

| Date | Change | ADR | Impact |
|------|--------|-----|--------|
| 2026-04-08 | Article list screen replaces event detail screen | ADR-008 | M6 simplified |
| 2026-04-08 | X + LinkedIn signals dropped; replaced by Google Trends | ADR-003 | Trend weights revised |
| 2026-04-08 | Show top 5 (not top 3) to users | ADR-001 context | Pipeline buffer = top 7 |
| 2026-04-08 | API returns ALL articles; UI controls display | ADR-007 | display_order field removed |
| 2026-04-08 | **Reddit PRAW dropped for MVP** | ADR-010 | Weights → rep 70%, gtrends 30% |
| 2026-04-08 | **SkeletonCard → ActivityIndicator for MVP** | ADR-011 | M5 simpler; polish in V1.1 |
| 2026-04-08 | **TestFlight → Expo Go QR for 2-week demo** | ADR-012 | No Apple review dependency |

---

## Decisions Made This Session

*(Move to DECISIONS.md if decision is permanent. Use this for session-level notes.)*

---

*Last updated: 2026-04-08 | Next update due: End of first coding session*
