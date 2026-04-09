# 📋 Signal Brief — Architecture Decision Record
> Every significant technical or product decision is logged here with context and rationale.
> Before changing an accepted decision, add a new ADR — don't delete the old one.
> Format: ADR-NNN | Date | Status: Proposed → Accepted | Deprecated | Superseded by ADR-NNN

---

## ADR-001 — Delivery Surface: Mobile App

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Astha (PM)

**Context:**
Multiple surfaces considered: Web App, Mobile App, Email Digest, Slack Bot, API-only.

**Decision:**
Build a native mobile app (iOS + Android via React Native / Expo).

**Rationale:**
- Primary user behavior is mobile-first (morning routine, commute)
- Native feel for pull-to-refresh, in-app browser, OS share sheet
- Expo handles cross-platform without maintaining two codebases

**Consequences:**
- Requires TestFlight (iOS) + APK distribution for testing
- No web fallback in MVP — purely mobile
- Expo SDK version must be pinned and upgraded deliberately

---

## ADR-002 — Caching Strategy: Background Pipeline + SQLite Cache

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Code Puppy (technical) | Astha (confirmed)

**Context:**
User selected "real-time on every page load." The full pipeline (fetch → cluster → score → 5× LLM calls) takes 45–90 seconds minimum. NFR requires <1s load time.

**Decision:**
Run pipeline as a background job (APScheduler, every 60 minutes).
API always serves from SQLite cache. Users see "last updated X min ago."
Pull-to-refresh queues an async refresh but immediately returns cached data.

**Rationale:**
- <1s load time is only achievable via cache
- This is how every news app works (Google News, Flipboard, Morning Brew)
- Hourly refresh is acceptable given the 4-day article window

**Consequences:**
- News can be up to ~60 minutes stale (acceptable)
- Must implement stale fallback (serve last good brief if pipeline fails)
- Must show `last_refreshed_at` and `is_stale` in API response
- `APScheduler max_instances=1` prevents overlapping runs

---

## ADR-003 — Social Signal Proxy: Google Trends + Reddit (not X/LinkedIn)

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Astha (PM)

**Context:**
Original spec required Reddit (15%) + X/Twitter (15%) + LinkedIn (15%) as social signals.
- X (Twitter) API Basic tier: $100/month minimum
- LinkedIn: no public content search API (partner program only, application required)

**Decision:**
- Reddit: keep via PRAW official API (free, 100 req/min)
- Google Trends (pytrends): replace X + LinkedIn as single proxy signal
- Redistribute weights: Reddit 22.5%, Google Trends 22.5% (from 15% + 15% + 15%)

**Revised weights:**
| Signal | Weight | Source |
|--------|--------|--------|
| Repetition | 55% | Article count in cluster |
| Reddit | 22.5% | PRAW — upvotes + comments, top 5 posts |
| Google Trends | 22.5% | pytrends — 7-day normalised interest |

**Rationale:**
- Google Trends is a reasonable proxy for X/LinkedIn trending (correlated with public discourse)
- Budget constraint: MVP must be near-zero cost
- Weights redistributed equally to keep sum = 100%

**Consequences:**
- Google Trends topic keyword quality directly affects score accuracy
- Must add 2s sleep between pytrends calls to avoid throttling
- X + LinkedIn can be added in V2 with proper budget allocation

**Superseded by:** —

---

## ADR-004 — LLM Provider: Groq API (llama-3.3-70b-versatile)

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Code Puppy (recommended) | Astha (confirmed "best free option")

**Context:**
User asked for "best free LLM." Candidates evaluated:
- OpenAI GPT-4o: free tier limited, production use requires payment
- Anthropic Claude: no meaningful free tier for production workloads
- Google Gemini Flash: free tier (1M tokens/day), moderate speed
- Groq API: free tier, llama-3.3-70b-versatile, 200+ tokens/second
- Ollama (local): free but requires local GPU; not suitable for server deployment

**Decision:**
Groq API with `llama-3.3-70b-versatile`.
Fallback: Google Gemini Flash free tier if Groq rate-limits.

**Rationale:**
- Groq free tier: 14,400 requests/day — pipeline uses ~120/day (24 runs × 5 events), well within limit
- Speed: 200+ tok/s means <8s per enrichment call (meets NFR)
- Quality: llama-3.3-70b is competitive with GPT-4o on structured tasks at temperature 0.3
- Zero cost for MVP traffic levels

**Consequences:**
- Groq free tier has context limits; each LLM call must stay under 4096 input tokens
- Must implement fallback to Gemini Flash if `groq.RateLimitError` raised
- API key stored in `.env` as `GROQ_API_KEY`
- If project scales: evaluate Groq paid tier vs. OpenAI batch API

---

## ADR-005 — Persona Strategy: Hardcoded Silicon Valley Archetype

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Astha (PM)

**Context:**
Options considered:
a) User onboarding form (role, industry, interests)
b) Infer from behavior over time
c) Hardcode Silicon Valley professional archetype
d) Preset personas (Investor, Engineer, Founder, PM)

**Decision:**
Hardcode the Silicon Valley professional persona for all MVP users.
Preset personas (option d) targeted for V2.

**Rationale:**
- No auth = no user state = can't personalize per user
- Target market is narrow and homogeneous enough for a single archetype
- Reduces complexity; validate the core value prop before adding personalization

**Consequences:**
- Persona prompt must be stored as a config constant (not hardcoded in logic)
- Changing persona wording = log a new ADR
- V2 will require user accounts or device-level preferences

**Current persona prompt** (see `CONTEXT.md` or `PRD.md §3.1`):
> "This user is a Silicon Valley professional who values concise, signal-rich information.
> They care about: tech industry trends, US policy impact on tech, investment signals,
> startup ecosystem dynamics, AI developments, and macroeconomic shifts.
> They have ~90 seconds to absorb this event. Tailor explanations accordingly."

---

## ADR-006 — Authentication: None (Fully Anonymous MVP)

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Astha (PM)

**Context:**
Options: No auth | Optional login | Required login.

**Decision:**
No authentication in MVP. Fully public, anonymous access.

**Rationale:**
- Auth adds significant complexity (token management, refresh flows, onboarding)
- No personalization in MVP = no reason for users to log in
- Faster to PMF validation with zero onboarding friction
- No PII risk (nothing to protect)

**Consequences:**
- Cannot collect per-user analytics
- Success metrics must be derived from server logs (pipeline health) + opt-in anonymous pings
- Adding auth in V2 is a medium-complexity change (API + mobile both need updates)

---

## ADR-007 — Pipeline Article Cap: All Articles in API, 3 Displayed in UI

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Code Puppy (technical) | Astha (confirmed)

**Context:**
Original spec: "cap to 3 articles" per event. But the Article List screen (M6) needs
articles sorted by recency in date groups — which could be more than 3.

**Decision:**
- API returns ALL articles in the cluster (no cap)
- Article List screen displays ALL of them, sorted newest → oldest, grouped by date
- Original "3 article" cap is retired

**Rationale:**
- The Article List screen's entire purpose is showing sources — capping at 3 defeats this
- API caps create coupling between backend and frontend display logic (violation of separation)
- More data in API = more flexibility; UI controls its own display

**Consequences:**
- API response may be larger for events with many articles (acceptable; JSON is small)
- `display_order` field on Article model is no longer needed — remove it
- Article List screen must handle gracefully if a cluster has only 1–2 articles

---

## ADR-008 — Home Screen UX: Full Content on Card (No Tap-to-Expand)

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Astha (PM)

**Context:**
Original spec had event cards as collapsed items that expanded or tapped into a detail screen
showing summary + why it matters + sectors + articles.

**Decision:**
All AI-generated content (heading, full summary, full "why it matters", sector tags) is
visible on the home screen card itself. Tapping a card navigates to the Article List screen
(source articles only — sorted by recency).

**Rationale:**
- Reduces cognitive load: primary insight is immediately visible, no extra taps
- The Article List screen becomes a clean "go deeper" action, not the main content delivery
- Matches the user's 90-second consumption pattern — they get everything in the scroll

**Consequences:**
- EventCard component is content-rich (not a teaser)
- No "Event Detail" screen needed — replaced by the simpler "Article List" screen
- Card height will vary (summary length varies); FlatList must handle variable height

---

## ADR-009 — Design Language: Custom, Not Walmart/Enterprise UI

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Astha (PM)

**Context:**
Signal Brief is a standalone consumer app, not a Walmart internal tool.

**Decision:**
Use a bespoke modern design system. Reference aesthetics: Perplexity AI, Linear, Reflect, Arc.
Design system is fully specified in `PRD.md §8`.

**Key design tokens (never change without updating PRD §8):**
- Primary bg (dark): `#09090B`
- Accent: `#818CF8` (Indigo 400)
- Success/trend-high: `#34D399` (Emerald 400)
- Fonts: Plus Jakarta Sans (display), Inter (body), Geist Mono (data)

**Consequences:**
- WCAG 2.2 Level AA accessibility still required (contrast, tap targets, labels)
- Must source fonts via `@expo-google-fonts` — not system fonts
- Sector tag color map is canonical (see `PRD.md §8.2`) — never deviate



## ADR-010 — Drop Reddit PRAW for MVP; Reweight to Repetition 70% / Google Trends 30%

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Astha (PM) — 2-week sprint feasibility decision

**Context:**
Feasibility analysis (FEASIBILITY.md) showed Reddit PRAW integration costs ~1.5 days:
OAuth app setup, credential management, query normalization, and rate-limit handling.
Reddit only contributed 22.5% of the trend signal. The 2-week sprint target requires
eliminating the highest-cost / lowest-value items.

**Decision:**
Remove Reddit PRAW from MVP entirely.
Revise trend score weights: repetition 70%, Google Trends 30%.
Reddit re-added in V1.1 as an enhancement.

**Previous weights:**
- Repetition 55%, Reddit 22.5%, Google Trends 22.5%

**New weights:**
- Repetition 70%, Google Trends 30%

**Rationale:**
- Saves 1.5 days — the single biggest time win in the sprint
- Google Trends already captures social discourse signal adequately
- Reddit OAuth adds credential complexity with minimal PMF impact
- Trend scoring with 2 signals is simpler, more maintainable, easier to test

**Consequences:**
- `pipeline/step3_score.py` needs no PRAW dependency
- `.env` has no Reddit credentials for MVP
- Trend scores will be slightly less socially-weighted (acceptable)
- V1.1: Add PRAW back with ADR superseding this one

**Superseded by:** — (open)

---

## ADR-011 — SkeletonCard Deferred; Use ActivityIndicator for Loading State

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Astha (PM) — 2-week sprint feasibility decision

**Context:**
SkeletonCard with shimmer animation (expo-linear-gradient) costs ~1 day to implement
correctly. It's a polish feature, not functional. Loading state is visible for < 500ms
on cached data — nearly imperceptible.

**Decision:**
Replace SkeletonCard with React Native's built-in `ActivityIndicator` (centered spinner).
SkeletonCard added back in V1.1.

**Rationale:**
- Saves 1 day with zero UX regression for the MVP testing audience
- ActivityIndicator is native, matches OS style, requires 3 lines of code
- The EventCard design, content, and all real UX is completely unchanged

**Consequences:**
- `mobile/components/SkeletonCard.tsx` is NOT created in MVP
- HomeScreen uses `ActivityIndicator` for loading state
- V1.1: Add SkeletonCard; replace ActivityIndicator

**Superseded by:** — (open)

---

## ADR-012 — Expo Go Distribution Instead of TestFlight for 2-Week Demo

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Astha (PM) — 2-week sprint feasibility decision

**Context:**
TestFlight submission requires: Apple Developer account ($99/yr), app binary build,
Apple review (1–3 days), tester invitation flow. This is bureaucratic overhead, not
engineering work. Costs ~0.5 day and introduces external dependency (Apple review).

**Decision:**
Deliver 2-week demo via Expo Go QR code (shareable link).
TestFlight / App Store submission happens post-PMF validation.

**Rationale:**
- Expo Go is production-quality for stakeholder demos and early user testing
- Zero Apple dependency; share a QR and anyone with Expo Go can test immediately
- Saves 0.5 day + removes an external blocking dependency

**Consequences:**
- Testers must have Expo Go installed (minor friction)
- App cannot be distributed to non-technical users until TestFlight/App Store
- V1.1: Build production binary + TestFlight when ready to expand testing

**Superseded by:** — (open)

---

## ADR-013 — TF-IDF Fallback for Embeddings on Walmart Network

**Date:** 2026-04-09
**Status:** ✅ Accepted
**Decider:** Code Puppy (auto-detected, confirmed by Astha)

**Context:**
huggingface.co is unreachable on Walmart Eagle WiFi / VPN (DNS blocked).
sentence-transformers all-MiniLM-L6-v2 cannot be downloaded.
Model is not cached from prior runs. Neural embeddings fail at runtime.

**Decision:**
step2_cluster.py implements two-tier embedding with automatic fallback:
  1. Try sentence-transformers neural embeddings (best quality, HF required)
  2. On failure: fall back to TF-IDF (scikit-learn, zero external dependencies)

For production deployment (where HF is reachable): neural embeddings are used.
For development on Walmart network: TF-IDF is used automatically.
No code change required to switch — fallback is detected at runtime.

**TF-IDF Config:**
  - max_features=8000, ngram_range=(1,2), stop_words=english, sublinear_tf=True
  - L2-normalised output; DBSCAN with euclidean metric (= cosine on unit vectors)
  - eps=1.0 base (cosine_sim > 0.5 threshold); auto-retry up to eps*2.0

**Why TF-IDF works for news clustering:**
Same-event news articles share proper nouns (names, tickers, legislation IDs).
These exact vocabulary overlaps are strong TF-IDF signal. In short RSS snippets,
TF-IDF bigrams outperform neural models that shine on longer text.

**Consequences:**
- On Walmart dev machines: TF-IDF runs, no model download needed
- On Railway/Render production: neural embeddings run after model downloads
- V1.1: Add local model caching via $HF_HOME for Walmart devs
- Clustering quality: comparable for news, potentially better on short snippets

**Superseded by:** — (open)

---

## Template for New ADRs

```markdown
## ADR-NNN — [Short Decision Title]

**Date:** YYYY-MM-DD
**Status:** 🔄 Proposed | ✅ Accepted | ❌ Deprecated | ↩️ Superseded by ADR-NNN
**Decider:** [Name / Role]

**Context:**
[What situation or problem prompted this decision?]

**Decision:**
[What was decided, stated plainly.]

**Rationale:**
[Why this option over the alternatives?]

**Consequences:**
[What does this mean for the codebase, timeline, or future decisions?]

**Superseded by:** — (or ADR-NNN)
```

---

*Last updated: 2026-04-08 | 9 decisions recorded*
