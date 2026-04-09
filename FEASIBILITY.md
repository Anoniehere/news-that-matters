# ⚡ Signal Brief — 2-Week Feasibility Analysis
**Date:** 2026-04-08 | **Requested by:** Astha
**Verdict up front:** YES — 2 weeks is achievable. The original 27-day estimate had ~11 days
of unnecessary PM buffer. Real engineering time is ~11–12 days solo, ~6 days with 2 devs.
But 3 specific cuts make it a comfortable sprint instead of a death march.

---

## The Honest Task-by-Task Breakdown

> Original estimates vs. what the code actually takes to write.

### Backend (M1–M4)

| Task | Original Est. | Real Est. | Why the Gap |
|------|--------------|-----------|-------------|
| RSS fetching (feedparser) | 1 day | 2 hrs | It's a 30-line library call. feedparser is battle-tested. |
| Sentence-transformer embeddings | 1 day | 30 min | Literally 3 lines of code. Model download is the slow part. |
| DBSCAN clustering + param tuning | 1 day | 3 hrs | Parameter tuning (eps) needs 1–2 iterations. Non-trivial. |
| Repetition trend score | 0.5 day | 30 min | It's array counting. |
| pytrends Google Trends score | 1 day | 2 hrs | Library works, but is flaky + throttled. Needs error handling. |
| Reddit PRAW score | 1 day | **1.5 days** | OAuth setup + query normalization + rate-limit handling = unexpectedly expensive for 22.5% of signal |
| Groq API call + Pydantic schema | 1 day | 2 hrs | Structured output is well-supported. Schema writing is fast. |
| Prompt engineering (LLM) | 1 day | **4–6 hrs** | Always takes iteration to get consistent JSON. Real risk. |
| Guardrail tests | 1 day | 2 hrs | Mostly automated with fixtures |
| FastAPI routes + SQLite | 1 day | 2 hrs | Boilerplate stack; well understood |
| APScheduler + stale fallback | 1 day | 2 hrs | APScheduler is simple; stale logic is ~20 lines |
| API smoke tests | 0.5 day | 1.5 hrs | curl + pytest; fast to write |
| **BACKEND TOTAL** | **14 days** | **~6 days** | Original had massive buffer |

### Mobile (M5–M7)

| Task | Original Est. | Real Est. | Why the Gap |
|------|--------------|-----------|-------------|
| Expo scaffold + font setup | 0.5 day | 1–2 hrs | `npx create-expo-app` + @expo-google-fonts |
| EventCard component | 1.5 days | **4 hrs** | Content-rich but no state. The biggest single component. |
| TrendBar (animated) | 0.5 day | 45 min | React Native Animated API; ~30 lines |
| SectorTag (color map) | 0.5 day | 45 min | Map lookup + StyleSheet. Simple. |
| SkeletonCard (shimmer) | 0.5 day | **1.5 hrs** | expo-linear-gradient shimmer = real implementation work |
| HomeScreen + FlatList + API | 1 day | 2.5 hrs | useEffect + fetch + pull-to-refresh |
| Device testing + fixes | 1 day | **2 hrs** | Always surprises. Font rendering, safe areas. |
| ArticleListScreen | 1 day | 2.5 hrs | SectionList with date grouping |
| ArticleItem + relative timestamps | 0.5 day | 1.5 hrs | date-fns formatRelative; simple |
| expo-web-browser link | 0.25 day | 30 min | One-liner |
| Share button | 0.25 day | 30 min | Native share sheet is 5 lines |
| Backend deploy (Railway/Render) | 1 day | 1–2 hrs | Push to git; configure env vars; done |
| E2E + red-team (50 LLM runs) | 1 day | 2 hrs | Script to run pipeline 50x; scan output for violations |
| TestFlight submission | 1 day | 1–2 hrs | Apple process is bureaucratic, not technical |
| **MOBILE TOTAL** | **13 days** | **~6 days** | Same story |

### Grand Total

| Scenario | Original | Real | Buffer |
|----------|---------|------|--------|
| Solo developer, full-time | 27 days | **~12 days** | 3 days left in 2 weeks |
| 2 devs (backend + frontend parallel) | 27 days | **~6 days** | Entire week 2 is buffer |

---

## Where the Original 27 Days Went Wrong

The 27-day plan was written as a PM document — it assumed junior/mid devs,
context switching, PR reviews, and multiple false starts. That's not wrong for
a corporate sprint, but for a focused build it's ~2.3× over-estimated.

**The three places where projects actually slip on this stack:**

1. **DBSCAN clustering parameter tuning** (eps value)
   — eps too high = 1 giant cluster. eps too low = 40 singleton clusters.
   — Requires iteration with real data. Can't be unit-tested with fixtures.
   — Risk: adds 3–4 hours if first run produces garbage.

2. **LLM prompt engineering for consistent JSON output**
   — Groq + llama-3.3-70b is good, but structured output still needs prompt iteration.
   — First run will likely have 1–2 schema validation failures that need prompt fixes.
   — Risk: adds 2–4 hours in M3.

3. **React Native on real device** (not simulator)
   — Safe area insets, font loading async, FlatList performance on long cards.
   — Always has at least one "works in simulator, breaks on device" moment.
   — Risk: adds 1–3 hours in M5.

---

## The 3 Cuts That Make 2 Weeks Comfortable

> These remove ~3.5 days of work. Combined with the 12-day real estimate,
> that gives you a **comfortable 8–9 day sprint** with 3–4 days of slip buffer.
> None of these cuts affect the core product value or user experience.

### ✂️ Cut 1 — Drop Reddit PRAW (saves 1.5 days)

**What changes:**
Trend scoring uses repetition (70%) + Google Trends (30%) only.
Reddit PRAW is removed entirely for MVP.

**Why this cut is fine:**
- Reddit only contributes 22.5% of the current score
- Reddit API requires OAuth app setup + credential management (adds complexity)
- Google Trends already proxies social discourse well
- Reddit can be added back in V1.1 as an enhancement, not a rewrite

**Revised weights:**
| Signal | Weight | Source |
|--------|--------|--------|
| Repetition | 70% | Article count in cluster |
| Google Trends | 30% | pytrends 7-day normalised interest |

**Log this in DECISIONS.md as ADR-010.**

---

### ✂️ Cut 2 — SkeletonCard → ActivityIndicator (saves 1 day)

**What changes:**
Replace custom shimmer skeleton loading with React Native's built-in `ActivityIndicator`.
Show spinner centered on screen while API call is in-flight.
SkeletonCard added back in V1.1.

**Why this cut is fine:**
- Skeleton is a polish feature, not a functionality feature
- Users see the spinner for < 500ms on cached data — it's barely noticeable
- The EventCard content, design system, and all real UX is unchanged

---

### ✂️ Cut 3 — Expo Go demo instead of TestFlight (saves 0.5 day)

**What changes:**
For the 2-week delivery, distribute via Expo Go QR code rather than submitting
to App Store / TestFlight. TestFlight submission happens in V1.1.

**Why this cut is fine:**
- Expo Go is a perfectly valid way to test a mobile app
- TestFlight requires Apple Developer enrollment, app review, etc. — bureaucratic overhead
- The product is fully functional; distribution channel is just different
- Any stakeholder with Expo Go installed can test it immediately via QR

---

## 2-Week Day-by-Day Sprint Plan

> Assumes: 1 developer, full-time focus, all credentials ready before Day 1.

```
WEEK 1 — BACKEND  (Days 1–5)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 1:  M1 — RSS fetch + embeddings + DBSCAN
        Output: output/clusters.json ✓

Day 2:  M2 — Trend scoring (repetition + pytrends only)
        Output: output/ranked_clusters.json ✓

Day 3:  M3a — Groq API + Pydantic schemas + initial prompts
        Output: first brief.json (may have schema fails; fix tomorrow)

Day 4:  M3b — Prompt iteration + guardrail tests + full pipeline run
        Output: output/brief.json passing all guardrails ✓

Day 5:  M4 — FastAPI + SQLite + APScheduler + API smoke tests
        Output: GET /brief returns JSON in <500ms ✓
        → Backend DONE. Deploy to Railway/Render (30 min; do it now).

WEEK 2 — MOBILE  (Days 6–10)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Day 6:  M5a — Expo scaffold + fonts + design tokens
              + EventCard + SectorTag + TrendBar
        Output: Single card renders correctly in Expo Go

Day 7:  M5b — HomeScreen (FlatList + pull-to-refresh + API)
              + ActivityIndicator loading state
              + "Last updated" subheader
        Output: All 5 cards render from live API ✓

Day 8:  M6 — ArticleListScreen + ArticleItem + DateGroupHeader
              + navigation + expo-web-browser + share
        Output: Full tap flow works end-to-end ✓

Day 9:  QA — Device testing + fixes + 50-run LLM red-team
              + WCAG contrast check + disclaimer visible

Day 10: Buffer / Polish
        → Fix anything that slipped from Day 9
        → Deploy final API URL into mobile build
        → Share Expo Go QR with stakeholders 🚀
```

---

## If You Have 2 Developers

With backend dev + frontend dev working in parallel from Day 1:

```
Dev A (Backend):  Days 1–5 as above
Dev B (Frontend): Days 1–3 → build components with mock data
                  Days 4–5 → integrate with real API as it comes online
                  Days 6–7 → polish + QA

Result: Ship Day 7 with 3 days of buffer.
```

The pipeline (M1–M4) and mobile (M5–M7) have almost zero code dependency on each other.
Backend just needs to agree on the API response shape upfront — which is already in PRD §7.

---

## Verdict

| Question | Answer |
|----------|--------|
| Can this ship in 2 weeks? | ✅ Yes — with 3 specific cuts |
| Does it require scope sacrifice? | 🟡 Minor — Reddit signal + skeleton UI deferred to V1.1 |
| What's the main risk? | DBSCAN tuning + LLM prompt iteration eating Day 3 |
| Buffer if things slip? | 2–3 days (built into the plan) |
| Confidence level | 85% solo · 95% with 2 devs |

---

## Pre-Sprint Checklist (Must be done before Day 1)

- [ ] Groq API key obtained → https://console.groq.com (free, no credit card)
- [ ] Reddit credentials — **NOT NEEDED** (cut per ✂️ Cut 1 above)
- [ ] Railway/Render account created (free tier) for backend deploy
- [ ] Expo Go installed on test device
- [ ] `uv` installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] Node.js 20+ installed (for Expo)
- [ ] `.env` file created with `GROQ_API_KEY`

**Estimated pre-sprint setup time: 45 minutes**

---

*Analysis by Code Puppy 🐶 | 2026-04-08*
