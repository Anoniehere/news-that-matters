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
▶ ACTIVE MILESTONE:  M7 — Deploy + QA
  Start date:        2026-04-12
  Target complete:   Day 10 (2-week sprint plan)
  Blocking anything: nothing — this is the finish line

M6 completed:
  - ArticleItem.tsx: article row, expo-web-browser tap, 44pt tap targets, a11y
  - DateGroupHeader.tsx: sticky ─── Today / Yesterday / Apr 8 ─── divider
  - ArticleListScreen.tsx: SectionList, date-group logic, share button (RN Share API),
    trend_insight pill, sticky disclaimer footer, empty state, back nav
  - Expo web build: zero errors, 815KB bundle, bundled in 2.4s ✅
  - All M6 exit criteria met ✅

M5 completed:
  - mobile/ scaffold: package.json, tsconfig, app.json, babel.config.js
  - theme/colors.ts: full PRD §8.2 token map + sectorColors() + trendColor()
  - theme/spacing.ts + theme/typography.ts: all design tokens
  - types/brief.ts: TypeScript types matching FastAPI /brief response
  - services/api.ts: fetchBrief() + formatAge() + formatRelativeDate()
  - components/TrendBar.tsx: animated 0→score%, 600ms ease-out, color thresholds
  - components/SectorTag.tsx: colour-coded chips, emoji per sector, PRD §8.2 colours
  - components/EventCard.tsx: full PRD §8.6 card (accent bar, trend, heading, summary, why, tags, footer)
  - screens/HomeScreen.tsx: FlatList + pull-to-refresh + ActivityIndicator + error state
  - screens/ArticleListScreen.tsx: M6 placeholder (back nav works)
  - App.tsx: NavigationContainer + font loading (PlusJakartaSans + Inter)
  - Web bundle: 560 modules, 5.2s, zero errors ✅
  - npm install: 603 packages, 0 vulns ✅
  - API + web preview running together on same machine ✅
  - Proxy issue: npm proxy configured via sysproxy.wal-mart.com:8080 ✅
  - No Xcode/Android Studio: verified via Expo web browser preview

M6 next steps:
  1. Replace ArticleListScreen placeholder with full implementation
  2. ArticleItem.tsx — single article row (title, source, date, external link)
  3. DateGroupHeader.tsx — date section headers (Today / Yesterday / Mar 15)
  4. Articles sorted newest→oldest, grouped by calendar day
  5. Tap article → expo-web-browser in-app sheet
  6. Share button → native Share API
  7. Sticky disclaimer footer
  8. Back navigation + swipe gesture (already wired via native stack)
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
| M1 | RSS Fetch + Cluster | ✅ Done | Day 1 | 2026-04-09 | 2026-04-09 |
| M2 | Trend Scoring (rep + pytrends) | ✅ Done | Day 2 | 2026-04-09 | 2026-04-09 |
| M3 | LLM Enrichment | ✅ Done | Days 3–4 | 2026-04-09 | 2026-04-08 |
| M4 | API + Cache + Scheduler | ✅ Done | Day 5 | 2026-04-10 | 2026-04-10 |
| M5 | Mobile Home Screen | ✅ Done | Days 6-7 | 2026-04-11 | 2026-04-11 |
| M6 | Article List Screen | ✅ Done | Day 8 | 2026-04-12 | 2026-04-12 |
| M7 | Deploy + QA | 🔄 In progress | Days 9–10 | 2026-04-12 | — |

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

**Target:** Days 20–22 | **Status:** ✅ Done

### Exit Criteria
- [x] `mobile/screens/ArticleListScreen.tsx` — full article list per PRD §8.8
- [x] `mobile/components/ArticleItem.tsx` — single article row
- [x] `mobile/components/DateGroupHeader.tsx` — date section headers
- [x] Tap EventCard → navigate to ArticleListScreen for that event
- [x] Articles listed newest → oldest, grouped by calendar day
- [x] Relative timestamps correct ("2 hours ago", "Yesterday", date string)
- [x] Tap article → opens in `expo-web-browser` (in-app sheet)
- [x] Share button → native share sheet with heading + source count
- [x] Sticky disclaimer footer always visible
- [x] Back navigation works (← and swipe gesture)
- [x] All items labelled for screen reader

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
► ACTIVE:  M7 — Deploy + QA. Day 9 of 10.

Context (as of 2026-04-14):
  M6 done. All mobile screens built. Full app works end-to-end in Expo web.
  API live on localhost:8001 (app.main:app, port 8001).
  Scoring overhauled — persona weights live, 12 feeds, partial brief safety net.
  PRD v1.3 written with consolidated intelligence logic in §5.1.

Pipeline current state:
  - step1_fetch.py  : 12 feeds, _GEO_KEYWORDS expanded
  - step2_cluster.py: MiniLM-L6-v2 + TF-IDF fallback, DBSCAN
  - step3_score.py  : rep 70% + feed_diversity 30%, TOTAL_FEEDS=12
  - step4_enrich.py : Gemini Flash primary / Groq fallback, PERSONA_WEIGHTS,
                      per-cluster try/except safety net, persona rescore
  - app/main.py     : FastAPI, SQLite cache, APScheduler 60min
  - prototype-v2.html: light mode swipe card UI — NOT yet merged into web/index.html

M7 Tasks:
  1. Switch API_BASE in mobile/services/api.ts to production URL
  2. Deploy FastAPI to Render/Railway/Fly.io (HTTPS, always-on, env vars)
  3. 50-run LLM red-team (hallucination + financial advice check)
  4. WCAG 2.2 AA contrast verification (all text + UI components)
  5. E2E flow: home loads → tap card → article list → tap article → browser
  6. Expo Go QR code for physical device testing
  7. is_stale banner appears if pipeline down > 2 hours

Optional (V1.1 scope):
  - Merge prototype-v2.html light-mode design into web/index.html
  - Re-sort brief events by final_signal_score (currently ordered by step3 rank)

Done when:
  - Production API URL works from real device (not localhost)
  - 50 LLM runs: 0 financial advice outputs, 0 flagged hallucinations
  - All text passes 4.5:1 contrast (WCAG AA)
  - Full E2E navigation works on real device via Expo Go
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
| 2026-04-09 | **TF-IDF fallback for embeddings (HF DNS blocked on Walmart net)** | ADR-013 | Auto-fallback; prod uses neural |
| 2026-04-09 | **pytrends 400 + external APIs blocked; feed_diversity fallback** | ADR-014 | Offline, deterministic, works on Walmart net |
| 2026-04-14 | **LLM provider switched: Gemini Flash primary, Groq fallback** | ADR-015 | `LLM_PROVIDER` env var toggles; 3 retries per cluster |
| 2026-04-14 | **pytrends 30% slot replaced by persona relevance scoring** | ADR-016 | `PERSONA_WEIGHTS` dict in `step4_enrich.py`; scores now ~0.91–0.97 range instead of 2-band collapse |
| 2026-04-14 | **Google News feeds expanded 5 → 12** | ADR-017 | 7 SV-persona feeds added; `TOTAL_FEEDS=12`; feed_diversity denominator updated |
| 2026-04-14 | **Partial brief safety net** | ADR-018 | Per-cluster try/except in step4; partial brief written on LLM failure instead of crash |
| 2026-04-14 | **PRD v1.3: §5.1 rewritten as consolidated intelligence logic** | — | Single source of truth for pipeline logic; §4 and §11 updated to match reality |

---

## Decisions Made This Session

*(Move to DECISIONS.md if decision is permanent. Use this for session-level notes.)*

---

*Last updated: 2026-04-14 | Next update due: End of M7 session*
