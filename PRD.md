# 📰 Signal Brief — Product Requirements Document
**Version:** 1.1 | **Status:** Implementation Ready | **Date:** 2026-04-08
**Author:** PM Session w/ Code Puppy 🐶
**Changelog v1.1:** Milestone-based delivery plan; updated home screen UX (full event cards);
new article timeline screen; added Section 8 — UX & Frontend Design Specs.

---

## 0. TL;DR

> Signal Brief is a mobile app that cuts through news noise for Silicon Valley professionals.
> Every time you open it, you see the **top 5 high-impact trending news events** — with
> AI-generated summaries, causal explanations, and sector-impact analysis — all on the card.
> Tap any card to dive into the source articles, sorted by recency.
> No login. No noise. Just signal.

---

## 1. Product Vision

| Field          | Detail |
|---------------|--------|
| Product Name  | Signal Brief |
| Tagline       | *"The news that actually matters to you — explained."* |
| Platform      | Mobile App — iOS + Android (React Native / Expo) |
| Target Users  | Working professionals, 28–45, US Silicon Valley |
| Business Model | Focus on PMF first; monetization TBD |
| MVP Timeline  | **10 days / 7 milestones** (2-week sprint — see §13 + FEASIBILITY.md) |

---

## 2. Problem Statement

Working professionals in Silicon Valley face three compounding problems:

1. **Overload** — 10,000+ articles published daily; no time to filter
2. **Fragmentation** — same story across 20 outlets, zero synthesis
3. **Shallow coverage** — headlines without causality; "what happened" without "so what"

Existing solutions (Apple News, Flipboard, Morning Brew) solve discovery but not understanding.
There is no product that gives you **trend signal + causal depth + sector impact** in one view.

---

## 3. Target Users

### 3.1 Primary Persona — "Alex, the Silicon Valley Professional"

| Attribute | Detail |
|-----------|--------|
| Age | 28–45 |
| Location | San Francisco Bay Area |
| Role | PM / Engineer / Founder / VC / Designer / Exec |
| Goal | Stay knowledgeable, sound informed, spot opportunities |
| Pain point | No time. Needs insight, not articles. |
| Morning routine | Coffee + phone. Opens 3–4 apps. Closes without reading. |

**AI Persona Prompt Anchor** (hardcoded — no user config in MVP):
> *"This user is a Silicon Valley professional who values concise, signal-rich information.
> They care about: tech industry trends, US policy impact on tech, investment signals,
> startup ecosystem dynamics, AI developments, and macroeconomic shifts.
> They have ~90 seconds to absorb this event. Tailor explanations accordingly."*

### 3.2 Secondary Persona — "Early Investor / Curious Learner"
- Overlaps heavily with primary; same hardcoded persona handles both.
- Deferred: persona customization is a V2 feature.

---

## 4. Resolved Spec Decisions

| Decision Point | Resolution |
|----------------|------------|
| Top 3 vs Top 5 | ✅ **Show top 5** to users. Pipeline computes top 7 as internal buffer. |
| Real-time vs <10s | ✅ **Background cache** refreshes every hour. User sees cached results in <1s. "Last updated X min ago" shown. Pull-to-refresh triggers async re-run. |
| Social signals (X/LinkedIn) | ✅ **Google Trends** as proxy for trend velocity. Reddit via official API (free). X and LinkedIn deferred to V2. |
| Persona system | ✅ **Hardcoded Silicon Valley archetype** for MVP. Preset personas in V2. |
| Authentication | ✅ **No auth in MVP.** Fully anonymous. No PII collected. |
| LLM Provider | ✅ **Groq API** (free tier) with `llama-3.3-70b-versatile`. Fallback: Google Gemini Flash free tier. |
| Home screen UX | ✅ **Full event content on card** (heading + summary + why it matters + sector tags). |
| Click-through UX | ✅ **Tap card → article list screen** showing source articles sorted by recency (newest first), grouped by date. |

---

## 5. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                  MOBILE APP (React Native)               │
│  Home: 5 event cards (full content visible on card)     │
│  Article List: sorted by recency, grouped by date       │
└──────────────────────┬──────────────────────────────────┘
                       │ REST — GET /brief
┌──────────────────────▼──────────────────────────────────┐
│                  FASTAPI BACKEND                         │
│   Serves latest cached brief. 99% of calls hit cache.  │
└──────────────────────┬──────────────────────────────────┘
                       │ reads from
┌──────────────────────▼──────────────────────────────────┐
│              SQLITE CACHE  (TTL = 1 hour)                │
│   Stores: top-5 events + articles + last_updated_at      │
└──────────────────────┬──────────────────────────────────┘
                       │ written by
┌──────────────────────▼──────────────────────────────────┐
│           BACKGROUND PIPELINE  (APScheduler)             │
│   Runs every 60 min. 5 sequential steps (see §5.1).     │
└─────────────────────────────────────────────────────────┘
```

### 5.1 Background Pipeline — Step by Step

```
Step 1: FETCH
  → Google RSS feeds (last 4 days, US-geofenced topics)
  → Feeds: Google News US, Tech, Politics, Business, AI/Science
  → Filter: published_at ≤ 4 days old, English, body_snippet ≥ 100 chars
  → Output: raw_articles[ {title, url, published_at, source, body_snippet} ]

Step 2: CLUSTER
  → Embed: article title + first 2 paragraphs
    (sentence-transformers all-MiniLM-L6-v2, local, zero cost)
  → DBSCAN clustering (eps=0.3, min_samples=2)
  → Each cluster = one "event"
  → Output: clusters[ {articles[], centroid_embedding, cluster_id} ]

Step 3: TREND SCORE
  → Weights (revised — see ADR-003, ADR-010):
    - repetition_score  70%  → cluster article count / total articles (normalised)
    - google_trends     30%  → pytrends 7-day interest score, normalised 0–100
  → trend_score = 0.70*rep + 0.30*gtrends
  → Sort descending; take top 7 (buffer) → pass top 5 to LLM

  NOTE: Reddit (PRAW) deferred to V1.1 (ADR-010: saves 1.5 days in 2-week sprint).
  Original spec also had X + LinkedIn; both dropped (ADR-003: no viable free APIs).

Step 4: LLM ENRICHMENT  (Groq, llama-3.3-70b-versatile, per event)
  → Single structured call per cluster; temperature = 0.3
  → System prompt: "Only use facts from provided articles.
     Do not add information not present in the source material.
     Do not provide investment advice, price targets, or buy/sell signals."
  → Pydantic schema validation; retry up to 2x on schema failure
  → Outputs per event:
     a) event_heading      : str  (≤ 15 words)
     b) summary            : str  (3–4 sentences MAX, facts only, source-grounded)
     c) why_it_matters     : str  (3–4 sentences MAX, Silicon Valley persona)
     d) sectors_impacted   : list[SectorImpact], 1–5 items, desc by confidence
        { sector_name, confidence_score: float 0–1, one_line_reason }
     e) timeline_context   : str  (1–2 lines)

Step 5: ASSEMBLE + CACHE
  → Per event: attach all cluster articles sorted by published_at DESC
    (show all; UI caps display at 3 but API returns all for future use)
  → Write brief to SQLite; set is_current = True; retire previous brief
  → On pipeline failure: retain last good brief; log + flag as stale
```

---

## 6. Data Model

```python
class Brief(BaseModel):
    id: int
    created_at: datetime
    is_current: bool          # only one row True at a time

class Event(BaseModel):
    id: int
    brief_id: int             # FK → Brief
    rank: int                 # 1–5
    event_heading: str
    summary: str
    why_it_matters: str
    timeline_context: str
    trend_score: float
    cluster_article_count: int

class SectorImpact(BaseModel):
    id: int
    event_id: int             # FK → Event
    sector_name: str
    confidence_score: float   # 0.0–1.0
    one_line_reason: str
    display_order: int        # 1 = highest confidence

class Article(BaseModel):
    id: int
    event_id: int             # FK → Event
    title: str
    url: str
    source_name: str
    published_at: datetime    # used for recency sort on Article List screen
```

---

## 7. API Specification

### `GET /brief`
Returns the latest cached brief.

```json
{
  "last_refreshed_at": "2026-04-08T17:00:00Z",
  "next_refresh_at":   "2026-04-08T18:00:00Z",
  "is_stale": false,
  "events": [
    {
      "rank": 1,
      "event_heading": "Federal AI Oversight Bill Advances in Senate",
      "summary": "...",
      "why_it_matters": "...",
      "timeline_context": "Debate began 3 days ago; Senate vote expected Thursday.",
      "trend_score": 0.94,
      "sectors_impacted": [
        { "sector": "AI / ML",    "confidence": 0.97, "reason": "..." },
        { "sector": "Big Tech",   "confidence": 0.85, "reason": "..." }
      ],
      "articles": [
        {
          "title": "Senate AI Bill Gains Bipartisan Support",
          "url": "https://...",
          "source": "Reuters",
          "published_at": "2026-04-08T12:30:00Z"
        },
        {
          "title": "White House Signals Support for AI Framework",
          "url": "https://...",
          "source": "AP",
          "published_at": "2026-04-07T18:00:00Z"
        }
      ]
    }
  ]
}
```

### `GET /brief/status`
Pipeline health: last run time, next run time, article count, stale flag.

### `POST /brief/refresh` *(internal/admin only)*
Manual pipeline trigger. Rate-limited: 1 call / 30 minutes.

---

## 8. UX & Frontend Design Specifications

> This is a standalone consumer app. Design language is independent —
> no corporate/enterprise UI constraints. Goal: editorial, modern, premium.

---

### 8.1 Design Philosophy

| Principle | Expression |
|-----------|-----------|
| **Clarity first** | Every pixel earns its place. No decorative noise. |
| **Editorial authority** | Typography-led hierarchy; feels like a quality publication |
| **Calm intelligence** | Smart but never anxious. No red dots, urgent badges, or FOMO triggers |
| **Depth on demand** | Full insight visible immediately; sources a tap away |
| **Dark mode primary** | Premium feel; easy on eyes for morning/evening use |

**Closest design references:** Perplexity AI · Linear · Reflect · Arc browser

---

### 8.2 Color System

```
── Dark Mode (default) ─────────────────────────────────────
  --bg-base       : #09090B   ← near-black (Zinc 950)
  --bg-surface    : #18181B   ← card background (Zinc 900)
  --bg-elevated   : #27272A   ← hover / pressed state
  --border-subtle : #3F3F46   ← card borders, dividers
  --text-primary  : #FAFAFA   ← headings, body
  --text-secondary: #A1A1AA   ← labels, metadata
  --text-muted    : #71717A   ← timestamps, fine print

  --accent        : #818CF8   ← Indigo 400  (primary interactive)
  --accent-dim    : #312E81   ← Indigo 900  (tag backgrounds)
  --positive      : #34D399   ← Emerald 400 (trend high, success)
  --warning       : #FBBF24   ← Amber 400   (trend medium)
  --alert         : #F87171   ← Red 400     (trend low, error)

── Light Mode ───────────────────────────────────────────────
  --bg-base       : #F4F4F5
  --bg-surface    : #FFFFFF
  --bg-elevated   : #F4F4F5
  --border-subtle : #E4E4E7
  --text-primary  : #09090B
  --text-secondary: #52525B
  --text-muted    : #A1A1AA
  (accent tokens unchanged)
```

**Sector Tag Color Map** (consistent across all events):

| Sector | Background | Text |
|--------|-----------|------|
| AI / ML | #312E81 | #A5B4FC |
| Big Tech | #082F49 | #38BDF8 |
| Federal Policy | #431407 | #FB923C |
| VC / Startups | #022C22 | #34D399 |
| Semiconductors | #2E1065 | #C4B5FD |
| Consumer Tech | #500724 | #F472B6 |
| Healthcare Tech | #052E16 | #4ADE80 |
| Fintech | #451A03 | #FCD34D |
| Defense / Security | #450A0A | #F87171 |
| Macro / Economy | #18181B | #94A3B8 |

---

### 8.3 Typography

```
Font Stack:
  Display  → "Plus Jakarta Sans"  (weights: 600, 700, 800)
  Body     → "Inter"              (weights: 400, 500)
  Data     → "Geist Mono"         (trend %, scores)

Scale:
  --text-xs   : 11px / 1.4  → timestamps, source names, fine print
  --text-sm   : 13px / 1.5  → sector tag labels, metadata
  --text-base : 15px / 1.6  → body text (summary, why it matters)
  --text-lg   : 17px / 1.4  → card heading
  --text-xl   : 20px / 1.3  → screen title
  --text-2xl  : 24px / 1.2  → article list screen heading

Letter-spacing:
  Labels/caps  → 0.08em (tracking-widest)
  Body         → 0
  Headings     → -0.02em (slightly tight = editorial feel)
```

---

### 8.4 Spacing & Layout

```
Base unit: 4px
  xs:  4px   sm:  8px   md: 12px
  lg: 16px   xl: 24px  2xl: 32px  3xl: 48px

Screen horizontal padding : 16px
Card border radius        : 16px
Tag border radius         : 6px
Card gap (between cards)  : 12px

Safe areas: respect iOS notch + home indicator, Android status bar.
```

---

### 8.5 Motion & Animation

```
Principle: Functional motion only. Nothing decorative.

Card press  → scale(0.98) + opacity(0.85), duration 80ms ease-out
Screen enter → slide up 12px + fade in, duration 220ms ease-out
Pull-to-refresh → native spinner, no custom animation
Skeleton shimmer → linear gradient sweep, 1.4s loop
Trend bar fill → width 0→N%, duration 600ms ease-out (on mount)
Sector tags → stagger in 40ms apart from left (on mount)
```

---

### 8.6 Component Specs

#### EventCard

```
┌─────────────────────────────────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │ ← 3px top accent bar
│                                         (gradient)  │   (#818CF8 → #34D399)
│                                                     │
│  ①  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  TRENDING  94%   │ ← rank (mono) + trend bar
│     ████████████████████████░░░░░              ↑   │   bar color: green/amber/red
│                                        Geist Mono  │   based on score threshold
│                                                     │
│  Federal AI Oversight Bill Advances in Senate       │ ← heading
│  — Tech Industry Braces for Impact                  │   Plus Jakarta Sans 700
│                                                     │   17px, --text-primary
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │ ← dashed separator
│                                                     │
│  The Senate Commerce Committee voted 11-2 to       │ ← SUMMARY (full, not truncated)
│  advance the AI Accountability Act, marking         │   Inter 400, 15px
│  the first major federal AI regulation effort.     │   --text-primary
│  Tech companies have 18 months to comply with      │
│  new transparency and audit requirements...        │
│                                                     │
│  WHY IT MATTERS                                    │ ← section label
│  ─────────────────                                  │   11px caps, --accent, tracking+
│  This directly reshapes how AI products are         │ ← WHY IT MATTERS (full)
│  built and monetized in the US. If you're           │   Inter 400, 15px
│  building or investing in AI tooling, the           │   --text-secondary
│  18-month window is your planning horizon.         │
│  Compliance costs will consolidate the market.    │
│                                                     │
│  ┌─────────┐ ┌──────────────┐ ┌────────────┐      │ ← SECTOR TAGS
│  │ 🤖 AI/ML│ │ ⚖️ Fed Policy│ │💼 VC/Start │      │   pill chips, color-coded
│  └─────────┘ └──────────────┘ └────────────┘      │
│                                                     │
│  6 sources  ·  Last: 2 hours ago          →        │ ← footer: article count
└─────────────────────────────────────────────────────┘   + arrow (--accent color)
                                                          tap anywhere → Article List
```

**Card states:**
- Default: `--bg-surface` background, 1px `--border-subtle` border
- Pressed: `--bg-elevated` background, scale 0.98
- Skeleton: animated shimmer over same layout skeleton

---

#### Sector Tag Chip

```
┌───────────────────┐
│  🤖  AI / ML      │   ← emoji icon + label
└───────────────────┘
  bg     : sector color map (dark bg token)
  text   : sector color map (light text token)
  border : 1px solid (text color at 30% opacity)
  radius : 6px
  padding: 4px 10px
  font   : Inter 500, 12px
```

---

#### Trend Bar

```
Track: full width, 4px height, --border-subtle bg, radius 2px
Fill:
  score ≥ 0.75 → --positive  (emerald)
  score ≥ 0.50 → --warning   (amber)
  score < 0.50 → --alert     (red)
Animates from 0 → score% on mount (600ms ease-out)

Score label: Geist Mono, 11px, --text-secondary
  "TRENDING  94%"   (label left, value right, same row as rank)
```

---

### 8.7 Screen 1 — Home Screen

```
STATUS BAR (system)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NAV BAR
  ⚡ Signal Brief                          [settings ⚙]
  Plus Jakarta Sans 800, 20px              icon 24px
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SUBHEADER (sticky below nav)
  Updated 12 min ago  ·  Next refresh in 48 min      🔄
  Inter 400, 12px, --text-muted                  tap=refresh
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCROLLABLE CONTENT  (FlatList, vertical)
  [EventCard rank=1]    ← full card as specced in §8.6
  [EventCard rank=2]
  [EventCard rank=3]
  [EventCard rank=4]
  [EventCard rank=5]

  ── BOTTOM FINE PRINT ──────────────────────────────
  Summaries are AI-generated from linked sources.
  Not financial advice. Signal Brief © 2026
  Inter 400, 11px, --text-muted, center-aligned
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOME INDICATOR (system)
```

**Pull-to-refresh behaviour:**
- User pulls down → native spinner appears
- Shows "Refreshing..." in subheader
- If pipeline is already running: shows cached data + "Refresh queued"
- On complete: subheader updates to "Just updated"
- On error: subheader shows "Using earlier data · Last updated X ago" in --warning

**Skeleton state (first load / no cache):**
- Same card layout, all text replaced by shimmer blocks
- 3 skeleton cards shown (implies loading)
- Subheader: "Fetching today's signal..."

---

### 8.8 Screen 2 — Article List Screen

Accessed by tapping any EventCard. Full-screen modal push.

```
STATUS BAR (system)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NAV BAR
  ←  Sources                            [share ↗]
     Inter 500, 16px (back label)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HEADER BLOCK  (not sticky — scrolls away)
  Federal AI Oversight Bill Advances in Senate         ← event heading
  Plus Jakarta Sans 700, 22px, --text-primary          (same as card)

  6 articles  ·  Most recent 2 hours ago              ← metadata row
  Inter 400, 13px, --text-muted

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ARTICLE LIST  (sorted newest → oldest, grouped by calendar day)

  TODAY — APR 8                                        ← date group header
  ─────────────────────────────                          Inter 500, 11px caps
                                                         --accent color, tracking+

  ┌────────────────────────────────────────────────┐
  │  White House Signals Support for AI Framework  │  ← article title
  │  Inter 500, 15px, --text-primary               │
  │                                                │
  │  AP  ·  2 hours ago                        ↗  │  ← source · time + external icon
  │  Inter 400, 12px, --text-muted                 │    arrow = --accent
  └────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────┐
  │  Tech Giants React to AI Bill Passage          │
  │                                                │
  │  Wall Street Journal  ·  5 hours ago       ↗  │
  └────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────┐
  │  Silicon Valley VCs Weigh In on Regulation     │
  │                                                │
  │  TechCrunch  ·  8 hours ago                ↗  │
  └────────────────────────────────────────────────┘

  APR 7 — YESTERDAY
  ─────────────────────────────

  ┌────────────────────────────────────────────────┐
  │  Senate AI Bill Gains Bipartisan Support        │
  │                                                │
  │  Reuters  ·  Apr 7, 2:30 PM               ↗  │
  └────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────┐
  │  What the AI Accountability Act Actually Says  │
  │                                                │
  │  The Verge  ·  Apr 7, 10:15 AM            ↗  │
  └────────────────────────────────────────────────┘

  APR 6
  ─────────────────────────────

  ┌────────────────────────────────────────────────┐
  │  Senate Commerce Committee Schedules AI Vote   │
  │                                                │
  │  Bloomberg  ·  Apr 6, 4:00 PM             ↗  │
  └────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STICKY FOOTER
  ℹ Summaries are AI-generated. Not financial advice.
  Inter 400, 11px, --text-muted, center, bg=--bg-base
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOME INDICATOR (system)
```

**Article item interaction:**
- Tap → opens URL in in-app browser (`expo-web-browser` / `Linking.openURL`)
- Pressed state: `--bg-elevated` background, 80ms
- Each item: full-width tap target, min 56px height (accessibility)

**Share button behaviour:**
- Taps → native share sheet
- Share text: `"{event_heading}" — {article_count} sources via Signal Brief`

---

### 8.9 Accessibility

| Requirement | Spec |
|-------------|------|
| Contrast ratio | ≥ 4.5:1 for all text (verified against dark + light bg) |
| Tap targets | Minimum 44×44pt (48×48pt preferred) |
| Screen reader | All cards labelled: "Trending event [rank]: [heading]" |
| Article items | Labelled: "[title], [source], [relative time], opens in browser" |
| Sector tags | Aria-label: "Sector: [name]" (emoji is decorative, hidden from SR) |
| Dynamic type | Text scales with system font size; layout reflows gracefully |
| Motion | Respects `prefers-reduced-motion`; disables all animations if set |

---

### 8.10 App Icon & Splash Screen

```
App Icon:
  Shape : rounded square (standard)
  Base  : #09090B (near-black)
  Mark  : "⚡" lightning bolt in gradient (#818CF8 → #34D399)
  Style : flat, no drop shadow, bold

Splash Screen:
  Background : #09090B
  Center mark: same icon mark, 80px
  Tagline    : "signal brief" in Plus Jakarta Sans 600, 14px, --text-muted
  Animation  : fade in 300ms, then app loads behind it
```

---

## 9. Non-Functional Requirements

| Requirement | Target | Implementation Strategy |
|-------------|--------|------------------------|
| App load time | <1s to show content | Serve from SQLite cache; never block on pipeline |
| Pipeline run time | <5 min end-to-end | Parallel RSS fetching; sequential LLM calls acceptable |
| LLM response time | <8s per event | Groq API (200+ tok/s); streaming if needed |
| Uptime | 99% | Cache fallback — if pipeline fails, serve last known good brief |
| No hallucinations | Zero tolerance | Temp 0.3, grounding prompt, schema validation, 2x retry |
| No financial advice | Required | System prompt guardrail + UI disclaimer on every screen |
| Accessibility | WCAG 2.2 Level AA | See §8.9 |
| Cost | Near-zero MVP | Groq free (14,400 req/day), Reddit API free, pytrends free |
| Privacy | No PII | No auth, no tracking, no analytics with PII |

---

## 10. Out of Scope for MVP (V2 Backlog)

| Feature | Reason Deferred |
|---------|----------------|
| X (Twitter) signal | API costs $100+/mo |
| LinkedIn signal | No public search API |
| User accounts / personalization | Adds auth complexity; validate value first |
| Preset personas (Investor, Founder) | Hardcoded persona first |
| Push notifications | Requires push infra + auth |
| Audio briefing (TTS) | Not core to value prop |
| Bookmarks / saved events | Requires persistent storage or auth |
| International news | US-first, validate PMF |
| Monetization | Focus on PMF |
| Light mode | Dark mode ships first; light mode in v1.1 |

---

## 11. Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------| 
| Mobile | React Native (Expo SDK 52+) | Cross-platform iOS + Android; one codebase |
| Fonts | Plus Jakarta Sans, Inter, Geist Mono | Via `@expo-google-fonts`; load async |
| Backend API | Python + FastAPI | Fast, typed, async-ready |
| Database | SQLite (MVP) | Zero-infra; scales fine for a cache store |
| LLM | Groq API — llama-3.3-70b-versatile | Best free-tier speed + quality (200+ tok/s) |
| Embeddings | sentence-transformers (local) | all-MiniLM-L6-v2; free, CPU-only |
| Clustering | scikit-learn DBSCAN | Standard, no API needed |
| Trend proxy | pytrends (Google Trends) | Free, no API key |
| Reddit signals | PRAW (Reddit official API) | Free tier; 100 req/min |
| News fetch | feedparser (Google RSS) | Reliable, no auth |
| Scheduler | APScheduler | Lightweight; embedded in FastAPI process |
| In-app browser | expo-web-browser | Native sheet; no custom browser needed |

---

## 12. Open Questions (Decisions Needed Before Dev Starts)

1. **App name final?** "Signal Brief" proposed — confirm or replace.
2. **Hosting budget?** Free tiers (Render/Railway) have cold-start issues; $5–10/mo recommended for always-on.
3. **RSS feed list?** Need explicit confirmed feeds + paywalled source exclusion list.
4. **Sector taxonomy?** Lock the allowed sector names before M3 (LLM enrichment). Suggested list in §5.1.
5. **Legal/TOS?** "Not financial advice" disclaimer — confirm with legal if shipping publicly.

---

## 13. Delivery Milestones

> **Philosophy:** Each milestone produces a testable, demoable artifact. Nothing ships untested.
> Estimated total: **27 working days (~5.5 weeks)** for a single focused developer.

---

### M1 — RSS Fetch + Article Clustering *(Days 1–3)*

**Goal:** Prove we can gather and group relevant news from the web.

**Deliverables:**
- `pipeline/step1_fetch.py` — RSS ingestion for all 5 Google News feeds
- `pipeline/step2_cluster.py` — sentence-transformer embeddings + DBSCAN clustering
- `scripts/test_m1.py` — smoke test runner
- `output/clusters.json` — sample output artifact

**Exit Criteria (all must pass):**
- [ ] ≥ 20 articles fetched across feeds
- [ ] ≥ 3 distinct clusters produced
- [ ] All articles have `published_at` within last 4 days
- [ ] `clusters.json` validates against expected schema
- [ ] Runtime ≤ 60 seconds on a standard laptop

**Demo:** Run `python scripts/test_m1.py` → prints cluster summary to console.

---

### M2 — Trend Scoring Engine *(Days 4–6)*

**Goal:** Rank clusters by real-world signal so the most relevant events surface first.

**Deliverables:**
- `pipeline/step3_score.py` — repetition + pytrends + Reddit PRAW scoring
- `output/ranked_clusters.json` — clusters with trend_score, sorted descending

**Exit Criteria:**
- [ ] Every cluster has `trend_score` in range [0.0, 1.0]
- [ ] Scores are reproducible within ±5% on re-run (pytrends can drift slightly)
- [ ] Top 7 clusters identified; top 5 flagged for LLM
- [ ] Reddit API auth works with configured credentials
- [ ] pytrends calls have 2s sleep between queries (rate-limit safety)
- [ ] Runtime ≤ 90 seconds

**Demo:** `python pipeline/step3_score.py` → prints ranked event list with scores.

---

### M3 — LLM Enrichment *(Days 7–10)*

**Goal:** Transform raw clusters into human-readable, AI-generated briefs.

**Deliverables:**
- `pipeline/step4_enrich.py` — Groq API integration
- `models/schemas.py` — Pydantic models for all LLM output fields
- `output/brief.json` — full enriched brief (5 events)
- `tests/test_hallucination_guard.py` — prompt guardrail tests

**Exit Criteria:**
- [ ] All 5 events have valid `event_heading`, `summary`, `why_it_matters`, `sectors_impacted`, `timeline_context`
- [ ] Pydantic validation passes without retry on ≥ 80% of runs
- [ ] `summary` is max 4 sentences; `why_it_matters` is max 4 sentences
- [ ] Each event has a `trend_insight` string explaining the score breakdown
- [ ] `sectors_impacted` has 1–5 items, sorted by confidence desc
- [ ] No financial advice language in any output (manual + automated check)
- [ ] No invented facts verifiably absent from source articles (spot-check 3 events)
- [ ] Groq call latency < 8s per event
- [ ] Full pipeline (M1+M2+M3) runs end-to-end ≤ 5 minutes

**Demo:** `python pipeline/step4_enrich.py` → pretty-prints enriched brief to terminal.

---

### M4 — Backend API + Cache + Scheduler *(Days 11–14)*

**Goal:** Wrap the pipeline in a production-ready API that serves cached results instantly.

**Deliverables:**
- `app/main.py` — FastAPI app with `/brief` and `/brief/status` endpoints
- `app/db.py` — SQLite ORM (SQLModel or raw sqlite3)
- `app/scheduler.py` — APScheduler hourly job; `max_instances=1`
- `tests/test_api.py` — curl/Python API smoke tests

**Exit Criteria:**
- [ ] `GET /brief` returns valid JSON in < 500ms (cache hit)
- [ ] `GET /brief/status` returns pipeline health metadata
- [ ] Scheduler fires pipeline every 60 minutes; logs start/end/duration
- [ ] Stale brief fallback: if pipeline errors, last good brief is served with `is_stale: true`
- [ ] Second `/brief` call is not slower than first (cache is working)
- [ ] API smoke tests pass: schema validation, status codes, stale flag behavior

**Demo:** `uvicorn app.main:app --reload` → `curl localhost:8000/brief` returns full JSON.

---

### M5 — Mobile Home Screen *(Days 15–19)*

**Goal:** Users can open the app and see all 5 event cards with full AI-generated content.

**Deliverables:**
- `mobile/` — Expo project scaffold
- `mobile/screens/HomeScreen.tsx` — FlatList of EventCards
- `mobile/components/EventCard.tsx` — full card as per §8.6
- `mobile/components/TrendBar.tsx` — animated trend score bar
- `mobile/components/SectorTag.tsx` — color-coded sector chips
- `mobile/components/SkeletonCard.tsx` — loading skeleton

**Exit Criteria:**
- [ ] App opens in Expo Go; home screen shows 5 event cards
- [ ] Each card shows: heading, summary, why it matters, sector tags, trend score, article count
- [ ] Trend bar animates on mount (600ms); correct color per score threshold
- [ ] Sector tags render with correct color map from §8.2
- [ ] Pull-to-refresh calls API and updates cards
- [ ] Skeleton shown on first load / error state
- [ ] "Last updated X min ago" subheader is correct
- [ ] Tap targets ≥ 44pt (all interactive elements)
- [ ] Fonts (Plus Jakarta Sans, Inter, Geist Mono) render correctly

**Demo:** Open Expo Go on device → scan QR → see live event cards from M4 API.

---

### M6 — Article List Screen *(Days 20–22)*

**Goal:** Tapping a card takes the user to a chronologically-ordered list of source articles.

**Deliverables:**
- `mobile/screens/ArticleListScreen.tsx` — full screen as per §8.8
- `mobile/components/ArticleItem.tsx` — single article row
- `mobile/components/DateGroupHeader.tsx` — "TODAY", "APR 7" section headers

**Exit Criteria:**
- [ ] Tap any EventCard → navigate to ArticleListScreen for that event
- [ ] Articles listed newest → oldest, grouped by calendar day
- [ ] Correct relative timestamps shown ("2 hours ago", "Yesterday", "Apr 6")
- [ ] Tap article → opens URL in `expo-web-browser` (in-app sheet)
- [ ] Share button → native share sheet with event heading + source count
- [ ] Sticky disclaimer footer always visible
- [ ] Back navigation works correctly (← or swipe)
- [ ] Screen is accessible: all items labelled for screen reader

**Demo:** Full end-to-end tap flow: Home → EventCard → ArticleList → tap article → browser.

---

### M7 — Polish, Deploy & QA *(Days 23–27)*

**Goal:** Production-ready. Runs on a real server. QA-tested. Ready for TestFlight distribution.

**Deliverables:**
- Deployed FastAPI API on Render/Railway/Fly.io (always-on)
- `mobile/` configured to point to production API URL
- TestFlight build (iOS) + APK (Android internal test)
- `tests/e2e/` — Playwright or Detox E2E test suite
- QA checklist (signed off)

**Exit Criteria:**
- [ ] API endpoint live and publicly accessible (HTTPS)
- [ ] App loads in < 1s on production API
- [ ] Full pipeline runs successfully on production server ≥ 3 consecutive times
- [ ] 50-run anti-hallucination red-team: 0 financial advice outputs, 0 invented facts flagged
- [ ] Light/dark mode text contrast verified ≥ 4.5:1 (WCAG 2.2 AA)
- [ ] E2E: home screen loads, card tapped, article list shows, article opens in browser
- [ ] TestFlight build submitted and installable on test device
- [ ] App icon + splash screen render correctly on iOS + Android
- [ ] `is_stale` banner appears when pipeline has been down > 2 hours

**Demo:** Production URL + TestFlight link shared with stakeholders.

---

### Milestone Summary Table

| Milestone | Sprint Day | Artifact | Key Test |
|-----------|------------|----------|----------|
| M1 — Fetch + Cluster | Day 1 | `clusters.json` | ≥20 articles, ≥3 clusters |
| M2 — Trend Scoring | Day 2 | `ranked_clusters.json` | Scores in [0,1]; top 7 identified |
| M3 — LLM Enrichment | Days 3–4 | `brief.json` | Schema valid; 0 hallucinations |
| M4 — API + Cache | Day 5 | `/brief` live on Railway | <500ms; stale fallback works |
| M5 — Home Screen | Days 6–7 | Expo Go app | 5 cards render with full content |
| M6 — Article Screen | Day 8 | Full tap flow | Articles sorted by recency |
| M7 — Deploy + QA | Days 9–10 | Expo Go QR + prod URL | E2E passes; 0 financial advice outputs |

---

## 14. Key Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Groq free tier rate limits hit | Low | High | 14,400 req/day; pipeline = 24 runs × 5 calls = 120/day. Safe. Fallback: Gemini Flash free. |
| pytrends throttled by Google | Medium | Medium | 2s sleep between calls; cache query results 1hr per topic |
| Reddit API limits | Low | Medium | Free: 100 req/min; we use ~35/run. Monitor & log. |
| Pipeline overlaps next run | Low | Low | `APScheduler max_instances=1`; log duration; alert if > 4min |
| LLM hallucinates | Medium | High | Temp 0.3 + grounding prompt + schema validation + 2x retry |
| Low-quality RSS articles | Medium | Medium | Filter: ≤4 days, English, ≥100 char body |
| Cache stale > 2 hours | Low | Medium | `is_stale` flag in API; UI banner; alert in server logs |
| Expo SDK breaking changes | Low | Low | Pin SDK version; upgrade deliberately after M7 |

---

## 15. Success Metrics (PMF Indicators)

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Time to first meaningful content | < 1s | Synthetic monitoring from prod URL |
| App opens > 3×/week per tester | > 40% | Optional anonymous open-ping (no PII) |
| "Useful" thumb-up on card | > 70% | Optional in-app micro-rating (V1.1 feature) |
| Pipeline success rate | > 95% | Server logs |
| LLM schema validation failure rate | < 5% | Server logs |
| Article link tap-through rate | > 20% | Optional anonymous event (no PII) |

---

*Signal Brief PRD v1.1 — Code Puppy 🐶 | 2026-04-08*
