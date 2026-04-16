<div align="center" id="top">

<br>

# 📡 News That Matters

**An AI news intelligence engine that scores what's worth your attention — and explains exactly why**

<br>

[![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://aistudio.google.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-gray?style=for-the-badge)](LICENSE)

<br>

<img src="docs/hero.svg" alt="News That Matters — swipe card UI showing AI signal score 9.3/10 for Trump-China tariffs story" width="320">

<br><br>

</div>

---

## The idea

I read a lot of news. I retain almost none of it.

Not because I don't try — I have six apps, two newsletters, and a Slack channel full of links I'll never open. The problem isn't access to information, it's that nothing tells me *which* of the 200 articles published this morning is actually worth stopping for.

Most news apps solve discovery. None of them solve *prioritisation*.

So I built one that does. Every hour it scans 12 news feeds, clusters ~200 articles by topic, scores each cluster using a formula I designed (`0.70 × editorial coverage + 0.30 × relevance to a Silicon Valley professional`), and then asks Gemini to explain the top 5 in plain English — including exactly why each story matters to someone who works in tech.

The score is shown on every card. The inputs that produced it are shown too. The AI's reasoning is never a black box.

---

## How the intelligence is built

This is the part I'm most proud of. Not the UI — the pipeline that decides what you see before you ever open the app.

```mermaid
flowchart TD
    A["🌐 12 RSS Feeds\n#nbsp;Google News · AI, Tech, Finance,\nGeopolitics, Energy & more"] --> B

    B["📥 Fetch & Clean\nstep1_fetch.py\n~200 articles/day · concurrent fetch\ndedup by URL · strip HTML · 24h window"] --> C

    C["🧠 Semantic Clustering\nstep2_cluster.py\nMiniLM-L6-v2 embeddings\ncosine similarity → DBSCAN\nTF-IDF fallback if offline"] --> D

    D["📊 Coverage Scoring\nstep3_score.py\nlog-normalised repetition score\nhow many outlets covered this?\n→ top 15 candidates"] --> E

    E["🤖 Pass 1 — Cheap Batch LLM\nstep4_enrich.py\n1 Gemini call for all 15 clusters\n→ sector tags · persona_score\nwhat would a tech pro care about?"] --> F

    F{"⚖️ Re-rank\n0.70 × coverage\n+ 0.30 × persona\n→ correct top 5"} --> G

    G["✨ Pass 2 — Full Enrichment\nstep4_enrich.py\n5 individual Gemini calls\n→ headline · 2-sentence summary\n→ why it matters to YOU"] --> H

    H["💾 SQLite Cache\nAPI always reads from cache\n< 500ms · never blocks on pipeline\nhourly refresh via APScheduler"] --> I

    I["📱 Swipe-card UI\nAI score hero · coverage + persona bars\n✦ Why It Matters tab · sources sheet"]

    style A fill:#ede9fe,stroke:#7c3aed,color:#111827
    style F fill:#fef3c7,stroke:#d97706,color:#111827
    style I fill:#d1fae5,stroke:#059669,color:#111827
```

The key design decision is the **two-pass LLM architecture**. Most obvious approach: call Gemini 5 times on the top 5 stories by article count. The problem: coverage rank ≠ relevance rank. A story covered by 20 regional newspapers might score higher than a story covered by 8 major tech outlets — but the second story is probably more interesting to a Silicon Valley professional.

Pass 1 is a single cheap batch call that adds the persona dimension *before* selection. The right 5 stories get enriched in Pass 2. Total cost: 6 LLM calls instead of 5 — but the selection is meaningfully better.

---

## The scoring formula

Every card shows a score from 0–10. Here's exactly how it's calculated:

```
Signal Score = 0.70 × Coverage Score + 0.30 × Persona Score

Coverage Score  = log-normalised article count across 12 feeds
                  (how many independent outlets reported this?)

Persona Score   = Gemini's assessment of relevance to a
                  Silicon Valley tech professional
                  (does this materially affect their work, investments, or industry?)
```

These aren't hidden. They're on the card:

> **9.3 / 10** &nbsp;·&nbsp; 📡 8 src &nbsp;·&nbsp; 📰 100% cov &nbsp;·&nbsp; 🎯 76% match

When the AI gives a story a 9.3, you can see *why*: near-total editorial consensus (100% coverage) across sources that a Silicon Valley professional has high reason to care about (76% persona match). The formula is the product.

---

## What you see

### The card

Each of the 5 daily cards is structured around the AI score, not the headline.

<div align="center">
<img src="docs/hero.svg" alt="Score hero showing 9.3/10 CRITICAL with 100% coverage bar and 76% persona match bar" width="320">
</div>

<br>

The gradient changes with rank. The score level (EMERGING → BUILDING → URGENT → CRITICAL) changes with intensity. The two bars show you the two numbers that produced the score.

### The tabs

<div align="center">
<img src="docs/card-tabs.svg" alt="Two tabs: 'What Happened' (neutral pill) and '✦ Why It Matters' (purple accent CTA)" width="390">
</div>

<br>

**What Happened** is commodity — any news app can do this. **✦ Why It Matters** is the product. The tab is purple *even when inactive*, pulling your eye toward the AI's analysis before you've consciously decided to tap. That's not an accident.

### The breakdown

Tap the `↗` chip and a sheet slides up explaining the AI's full reasoning: sector classification, coverage depth, why Gemini rated this story relevant to your professional context.

---

## The decisions that shaped it

<details>
<summary><b>Why show the AI's inputs on the card — not just the score?</b></summary>

<br>

The temptation with any AI-scored product is to show the output and hide the inputs. It feels cleaner. It also feels like magic, which sounds good until users start asking "why is this a 9?" and the answer is "we can't tell you."

I made the opposite call. Every card shows coverage percentage and persona match percentage — the two numbers that produced the score. The formula is printed in the breakdown sheet. Anyone can read it.

The reason isn't ethics-washing. It's trust. If a user sees a 9.3 and doesn't understand why, they'll start second-guessing every score. If they see "100% cov · 76% match" and they know what those mean, they understand the AI's reasoning instantly — and they trust or challenge it from an informed position. That's a better relationship between a user and an AI product.

Transparency by design, not by disclaimer.

</details>

<details>
<summary><b>Why 70/30 — and not 50/50 or 90/10?</b></summary>

<br>

This was the hardest product decision in the whole build.

Pure editorial coverage (100/0) surfaces stories that are everywhere — which often means they're already on everyone's phone. High coverage just means "a lot of outlets reported this," not "this is important to you specifically." The risk is a brief that looks like a slow version of Google News.

Pure persona relevance (0/100) means trusting Gemini to completely override what the media is covering. That introduces LLM bias and misses legitimately important stories that Gemini didn't flag as personally relevant.

70/30 was a deliberate starting point: editorial coverage is the anchor (these things are objectively widely covered), persona relevance is the differentiator (here's why *you* should care). The weighting is visible to users and documented in ADR-022. If I had telemetry, I'd A/B test 60/40 against it.

</details>

<details>
<summary><b>Why two-pass LLM instead of just calling Gemini 5 times?</b></summary>

<br>

The naive approach is: take the top 5 stories by article count, call Gemini once per story, enrich them. Simple, parallel, cheap enough.

The problem I hit: coverage rank and relevance rank don't always agree. Story A might have 40 articles from regional outlets. Story B might have 12 articles from major tech publications. Step 3 ranks Story A higher. But for a Silicon Valley professional, Story B is almost certainly more interesting.

Pass 1 fixes this. It's a single batch LLM call — cheap, fast — that scores all 15 candidate clusters for persona relevance *before* final selection. The re-rank happens at that point. Pass 2 enriches the correctly-selected top 5.

The cost: 1 extra LLM call. The benefit: the right 5 stories in the brief every time. That's not a hard trade-off.

</details>

<details>
<summary><b>Why DBSCAN instead of k-means for clustering?</b></summary>

<br>

k-means requires you to specify k — the number of clusters — upfront. For 200 daily articles, there's no principled way to know whether today's news breaks into 15 clusters or 35. Forcing k = 20 means some stories get merged that shouldn't be, and others get artificially split.

DBSCAN discovers the number of clusters from the data. It groups articles that are within a cosine distance threshold of each other, and marks everything else as noise (one-off articles that don't cluster). For daily news — where the number of distinct stories genuinely varies day to day — that's the right choice.

The TF-IDF fallback exists because `sentence-transformers` requires a network download on first run, and I wanted the pipeline to work even on a machine with no internet access (or restricted Walmart VPN). TF-IDF is surprisingly effective for news clustering because same-event articles share proper nouns — names, tickers, legislation — which are exactly what TF-IDF weights highest.

</details>

<details>
<summary><b>Why does the card end above the fold?</b></summary>

<br>

If a card fills the entire screen, it looks like the whole app. There's no visual signal that there are 4 more stories below it.

Ending the card ~56px above the bottom of the screen lets the lavender gradient background peek through underneath. It's a passive "there's more here" signal that doesn't require onboarding, tooltips, or a "swipe to see more" label. The gap does the work.

This is the kind of detail that doesn't show up in PRDs but makes the difference between an app that feels finished and one that feels like a prototype. Small affordances, compounding effect.

</details>

<details>
<summary><b>Why does the app never show a blank screen?</b></summary>

<br>

The pipeline takes ~30 seconds to run. On first boot, on quota exhaustion, on a network failure — a lot of things can prevent fresh data from arriving.

The app ships with a static brief baked into the HTML. If the API call fails or times out (3-second hard cutoff), the UI falls back to the embedded events and shows a banner. Users see real cards with real content from day one. There's no spinner followed by an error followed by a retry — which is the failure mode of apps that treat the API as a hard dependency.

The brief goes stale eventually — that's fine. An amber "Showing sample brief" banner tells users what they're looking at. The alternative — a blank card stack — would have killed engagement on first open.

</details>

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Google Gemini 2.5 Flash · 1.5 Flash · 1.5 Flash-8B (3-tier fallback) |
| **Embeddings** | `sentence-transformers` all-MiniLM-L6-v2 · TF-IDF fallback |
| **Clustering** | scikit-learn DBSCAN · cosine similarity |
| **Backend** | FastAPI · SQLite · APScheduler · Pydantic |
| **Frontend** | Vanilla JS + CSS · Inter · Plus Jakarta Sans |
| **Data** | Google News RSS (12 feeds) · feedparser |
| **Built with** | Code Puppy (AI dev agent) · Gemini API |

---

## Run it locally

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/news-that-matters.git
cd news-that-matters

# Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Add your Gemini key (free at aistudio.google.com)
echo "GEMINI_API_KEY=your_key_here" > .env

# Run
uvicorn app.main:app --port 8001

# Open
open http://localhost:8001
```

The pipeline runs automatically on first boot (~30 seconds), then hourly in the background. **No key?** The app falls back to a built-in static brief — still fully interactive, just not live data.

---

## Architecture decisions

25 decision records live in [`DECISIONS.md`](DECISIONS.md) — written in the style of a production engineering team. Topics include why DBSCAN over k-means (ADR-013), why TF-IDF as fallback (ADR-013), why the 70/30 formula (ADR-022), the two-pass LLM architecture (ADR-023), and why the timeline feature was cut (ADR-024).

The ADR format forces a discipline I think all AI product decisions should have: *state the context, state the options considered, state what you chose and why.* "We used Gemini" is not an architecture decision. "We use Gemini 2.5 Flash with a 3-tier model fallback chain because X" is.

---

## What I'd do next

**Persona selector** — right now the persona is hardcoded as "Silicon Valley tech professional." The interesting version lets you set your own context — VC investor, founder, policy researcher — and re-scores the same 5 stories through a different lens. The pipeline already supports it; the UI doesn't yet.

**Deployment** — Railway or Render. The whole thing is 6 LLM calls an hour on the free Gemini tier. Running cost: essentially zero.

**A/B test the formula** — 70/30 was a reasoned starting point, not a measured optimum. With telemetry on which stories users actually tap through, I'd run 60/40 and 80/20 variants and let engagement data pick the weight.

**PWA manifest** — this should be installable. The whole app is one HTML file and a FastAPI server. A service worker and a manifest.json away from living on a home screen.

---

<div align="center">

Built by **[Astha Dhawan](https://www.linkedin.com/in/asthadhawan)** · Staff Product Manager at Walmart

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/asthadhawan)
&nbsp;
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/Anoniehere)

<br>

*If this made you think differently about how AI products should reason — a ⭐ goes a long way.*

</div>
