# 📋 News That Matters — Architecture Decision Record
> Every significant technical or product decision is logged here with context and rationale.
> Before changing an accepted decision, add a new ADR — don't delete the old one.
> Format: ADR-NNN | Date | Status: Proposed → Accepted | Deprecated | Superseded by ADR-NNN
>
> **When to update this file:**
> Log a new ADR DURING the session the moment a significant decision is made.
> Do not wait until the end of the session. If it is not logged here, it will be re-litigated.
> A decision is significant if it: changes architecture, drops or adds a dependency,
> changes a weight/threshold/limit, or makes a trade-off with future consequences.

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

**Superseded by:** ADR-010 (Reddit dropped), ADR-016 (persona replaces pytrends), ADR-019 (two-pass selection)

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
News That Matters is a standalone consumer app, not a Walmart internal tool.

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

**Superseded by:** ADR-019 (rep-only pre-filter; step4 handles final selection via persona score)

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

**Neural model resolution order (step2_cluster.py):**
  1. ~/.cache/news-that-matters/models/all-MiniLM-L6-v2 (local, assembled by download_model.py)
  2. HuggingFace Hub download (production / open internet)
  3. TF-IDF fallback (if both above fail)

**Download approach on Walmart network (ADR-013 addendum):**
  The HuggingFace Python client (httpx) times out on large files through the Walmart proxy.
  Root cause: XetHub CDN (where model weights live) closes the httpx connection before
  the 87MB download completes. curl is unaffected.
  Solution: scripts/download_model.py uses curl for the binary blob (--max-time 300)
  and direct CDN for small text files. Model assembles to ~/.cache/news-that-matters/models/.

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

## ADR-015 — LLM Provider switched from Groq to Google Gemini 2.5-flash

**Date:** 2026-04-08
**Status:** ✅ Accepted
**Decider:** Code Puppy (technical) | Astha (confirmed)

**Context:**
Groq API (`api.groq.com`) returns 407 PROXY AUTH REQUIRED on Walmart Eagle WiFi and VPN.
The Walmart corporate proxy only allows Google-domain traffic without authentication.
Groq was the original M3 LLM provider (ADR-004). Running from hotspot every session
is not sustainable for a dev machine on Walmart network.

**Decision:**
Switch primary LLM provider to Google Gemini 2.5-flash via `google-genai` SDK.
`generativelanguage.googleapis.com` is a Google domain — proxy-whitelisted and confirmed
reachable from Walmart network. Groq remains available via `LLM_PROVIDER=groq` for
off-network use (home, production server).

**Provider config:**
- Env var: `LLM_PROVIDER=gemini` (default) | `groq` (off-network)
- Gemini key: `GEMINI_API_KEY` in `.env` (from aistudio.google.com, free)
- Proxy: `HTTPS_PROXY=http://sysproxy.wal-mart.com:8080` in `.env`
- Model: `gemini-2.5-flash` (best free-tier model available as of 2026-04-08)

**Latency impact:**
- Groq: ~5-6s per event (200+ tok/s, off-network only)
- Gemini 2.5-flash: ~10-11s per event (on Walmart network, proxy overhead included)
- Total pipeline latency: 44s end-to-end — well within 5-minute NFR
- Latency exit criterion updated from <8s to <15s per event

**Rationale:**
- Only sustainable option on Walmart network without VPN tricks or hotspot
- Gemini 2.5-flash quality is excellent — structured output, all guardrails pass
- Free tier is generous enough for MVP dev + demo usage
- `LLM_PROVIDER` env var keeps the switch non-breaking for off-network environments

**Consequences:**
- `GEMINI_API_KEY` required in `.env` on Walmart machines
- `google-genai` added to dependencies
- Production server (Railway/Render) can use either provider — set via env var
- ADR-004 (Groq) is superseded for on-network use; still valid for off-network

**Superseded by:** — (open)

---

## ADR-014 — Social Signal Fallback: feed_diversity (SUPERSEDED)

**Date:** 2026-04-09
**Status:** ↩️ Superseded by ADR-019
**Decider:** Code Puppy (technical) | Astha (confirmed)

**Context:**
pytrends 4.9.x returns HTTP 400 due to Google's 2024 auth change. feed_diversity
(unique feeds per cluster / total feeds) was introduced as a deterministic offline fallback.

**Decision:**
feed_diversity as 30% weight in step3 pre-filter. Superseded when we discovered this
still produces biased selection — a high-coverage niche story could rank above a
personally-relevant but editorially-narrow story.

**Superseded by:** ADR-019 (rep-only pre-filter; persona score applied in step4 Pass 1)


---

## ADR-016 — Persona Relevance Scoring Replaces pytrends/feed_diversity 30% Slot

**Date:** 2026-04-14
**Status:** ✅ Accepted
**Decider:** Code Puppy (technical) | Astha (confirmed)

**Context:**
The 30% "social signal" slot in the trend score was occupied by pytrends (broken, HTTP 400)
then feed_diversity (offline, but blind to audience relevance). Both measured editorial breadth,
not whether the SV professional persona actually cares about the story.

**Decision:**
Replace the 30% slot permanently with `persona_score`:
- `PERSONA_WEIGHTS` dict maps each of 13 sectors to SV-professional relevance (0.0–1.0)
- `persona_score = weighted_sum(sector_weight × llm_confidence) / max_possible`
- Final: `signal_score = 0.70 × rep_score + 0.30 × persona_score`
- Applied in step4 after LLM returns `sectors_impacted`

**Rationale:**
- Directly measures what we care about: "does this story matter to the audience?"
- Deterministic and tunable (just edit `PERSONA_WEIGHTS` dict)
- No external API dependency; uses sector output the LLM already produces
- Fixes the 2-band score collapse (all events scoring ~0.91 or ~0.97)

**Consequences:**
- `PERSONA_WEIGHTS` is the single source of truth — change weights to retune ranking
- Scores now differentiate meaningfully across events
- Step 3 must pass clusters to step 4 *before* final ranking can happen

**Superseded by:** ADR-019 extended this to Pass 1 (batch tagging before selection)

---

## ADR-017 — Google News Feeds Expanded from 5 to 12

**Date:** 2026-04-14
**Status:** ✅ Accepted
**Decider:** Code Puppy (recommended) | Astha (confirmed)

**Context:**
The original 5 feeds (US Top Stories, World, Business, Technology, Science) were
insufficient for SV-professional coverage. Key topics like AI chip export controls,
India/Gulf geopolitics, and Africa/Global South were underrepresented.

**Decision:**
Add 7 SV-persona-targeted feeds:
- AI & Chip Export Controls, US-China & Trade Wars, Dollar & Global Finance
- Global Conflict & Security, Energy & Critical Minerals, Tech Regulation & Antitrust
- India & Gulf Relations, Africa & Global South, Cyber & Espionage

Total feeds: 12. All are Google News RSS (no auth required, proxy-accessible).

**Rationale:**
- Better topic coverage = better cluster quality
- Still no auth dependency, fully offline-capable
- Direct alignment with SV persona interests per ADR-005

**Consequences:**
- `step1_fetch.py` updated with new feed list
- Total articles fetched: ~270 (up from ~80–100)
- Clustering quality improves significantly

**Superseded by:** —

---

## ADR-018 — Partial Brief Safety Net: Per-Cluster try/except in step4

**Date:** 2026-04-14
**Status:** ✅ Accepted
**Decider:** Code Puppy (technical) | Astha (confirmed)

**Context:**
If one LLM call fails (rate limit, validation error, network blip), the entire `enrich_clusters()`
function would crash with no output — a total pipeline failure.

**Decision:**
Wrap each individual cluster enrichment in a `try/except RuntimeError` block.
On failure: log the error, skip that cluster, and continue to the next.
A partial brief (e.g. 4 events instead of 5) is served rather than nothing.

**Rationale:**
- Partial > none: users see something, stale fallback fires only when all 5 fail
- LLM failures are transient; the next scheduled run usually succeeds
- Clean logs make debugging easy without blocking progress

**Consequences:**
- Brief may have 1–4 events on failure days (acceptable; API documents min as 1)
- LLM failure rate in practice: ~5% of individual cluster calls

**Superseded by:** —

---

## ADR-019 — Two-Pass LLM Scoring: Rep-Only Pre-Filter + Batch Sector-Tag Pass 1

**Date:** 2026-04-15
**Status:** ✅ Accepted
**Decider:** Code Puppy (technical) | Astha (confirmed)

**Context:**
ADR-016 correctly moved persona scoring to step4, but the selection bias remained:
step3 still used rep_score + feed_diversity to pick which clusters went to the LLM.
A story could be highly persona-relevant but editorially narrow (1 feed only) and
never reach step4. The wrong 5 stories were being fully enriched.

**Decision:**
Two-pass architecture:

**Step 3 (pre-filter only):**
- Rank by `rep_score` alone (no feed_diversity, no social signal)
- Pass top 15 candidates to step4 (was 7)
- All 15 flagged `for_llm=True`

**Step 4 Pass 1 (cheap batch sector tagging):**
- Single LLM call with all 15 headlines + snippets
- Returns sector tags + confidence for each
- Compute `persona_score` for each candidate
- Re-rank: `combined = 0.70 × rep + 0.30 × persona`
- Select top 5 by combined score

**Step 4 Pass 2 (full enrichment):**
- 5 individual LLM calls on correctly-selected stories
- Full heading + summary + why_it_matters + sectors
- Final score recomputed with Pass 2 sectors (more context → more accurate)

**Total LLM calls:** 1 batch + 5 full = 6 (vs 5 before, but correct 5 selected)

**Rationale:**
- Eliminates selection bias: persona relevance gates inclusion, not just final score
- Batch sector-tag is cheap (1 call, classification-only, temp=0.2)
- 15 candidates gives a wide enough pool that the right 5 always reach Pass 2
- Architecturally clean: each pass has one job (select vs enrich)

**Consequences:**
- `step3_score.py`: removed `social_score`, `search_term`, `feed_diversity` — dead code deleted
- `step4_enrich.py`: added `_batch_sector_tag()`, `_select_top_n()`, `SECTOR_TAG_PROMPT`, `TOP_N_FINAL=5`
- `schemas.py`: `ScoredCluster` drops `social_score` + `search_term`; `signal_source` now `reputation`→`persona`
- `test_m2.py` rewritten; M2 smoke test: ✅ 9/9 checks in 43.2s
- Slightly higher total latency (~+10s for batch call); still well within 5-min NFR

**Superseded by:** —

---

*Last updated: 2026-04-15 | 19 decisions recorded*
