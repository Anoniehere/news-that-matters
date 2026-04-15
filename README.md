# News That Matters 📡

> *The top 5 high-impact news events today — scored by AI, explained for you.*

A full-stack AI news intelligence app built from scratch to explore every layer of modern AI product development — from RSS ingestion and semantic clustering to LLM enrichment, FastAPI delivery, and a swipe-card mobile UI.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_2.5_Flash-LLM-4285F4?style=flat&logo=google&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-cache-003B57?style=flat&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green?style=flat)

---

## What it does

Every hour, an AI pipeline scans 12 RSS feeds, clusters ~200 articles by semantic similarity, scores each cluster by editorial coverage **and** relevance to a Silicon Valley professional, then asks Gemini to write a headline, a 2-sentence summary, and a personalised *"why this matters to your work"* explanation for the top 5.

Open the app. Swipe through 5 cards. Each card shows:
- **AI Signal Score** — a `0–10` score derived from `0.70 × coverage + 0.30 × persona match`
- **Coverage %** and **Persona match %** — the two AI inputs, visible to the user
- **What Happened** — 2-sentence summary
- **✦ Why It Matters** — personalised impact, written by Gemini for a tech professional
- **Sources** — every article the AI read to produce this card

---

## The AI Pipeline

```
12 RSS feeds (Google News topics)
       │
       ▼
┌─────────────────────────────┐
│  step1_fetch.py             │  Concurrent fetch, dedup by URL,
│  ~200 articles/day          │  strip HTML, filter to 24h window
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  step2_cluster.py           │  sentence-transformers MiniLM-L6-v2
│  ~30 clusters               │  → cosine similarity → DBSCAN
│                             │  TF-IDF fallback (zero downloads)
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  step3_score.py             │  log-normalised repetition score
│  Top 15 candidates          │  (coverage breadth as signal)
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  step4_enrich.py — Pass 1   │  1 batch Gemini call → sector tags
│                             │  → persona_score for all 15
│                             │  → re-rank: 0.70×rep + 0.30×persona
│                             │  → select correct top 5
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  step4_enrich.py — Pass 2   │  5 individual Gemini calls
│  Top 5 enriched events      │  → heading + summary + why_it_matters
│                             │  → structured output via Pydantic
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  SQLite cache               │  API always reads from cache (<500ms)
│  APScheduler (hourly)       │  Pipeline never called in request path
└──────────────┬──────────────┘
               │
               ▼
         FastAPI /brief
               │
               ▼
      Swipe-card UI (web/)
```

**Why two-pass LLM?** A naive approach calls Gemini 5 times to enrich the top 5 stories by coverage alone — but coverage rank ≠ relevance rank. Pass 1 is a single cheap batch call that adds the persona dimension before selection. The right 5 stories are now enriched in Pass 2. Total: 6 LLM calls instead of 5, but with meaningfully better story selection.

---

## AI Concepts Demonstrated

| Concept | Where |
|---------|-------|
| **Semantic embeddings** | `sentence-transformers/all-MiniLM-L6-v2` for article similarity |
| **Unsupervised clustering** | DBSCAN on cosine distance matrix (`step2_cluster.py`) |
| **TF-IDF fallback** | Graceful degradation when neural model unavailable (`ADR-013`) |
| **Prompt engineering** | Persona-targeted prompts with structured Pydantic output (`step4_enrich.py`) |
| **Two-pass LLM architecture** | Cheap batch select → expensive individual enrich (cost + quality) |
| **Weighted scoring formula** | `0.70 × rep_score + 0.30 × persona_score` with explicit rationale |
| **Production AI resilience** | 3-tier Gemini model fallback chain + daily quota manager (`quota_manager.py`) |
| **Structured LLM output** | Pydantic schema validation on every Gemini response |
| **Stale-safe UI** | Static fallback brief ships in the HTML — app never shows a blank screen |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **AI / LLM** | Google Gemini 2.5 Flash (primary), Gemini 1.5 Flash, Gemini 1.5 Flash-8B |
| **Embeddings** | `sentence-transformers` all-MiniLM-L6-v2 · TF-IDF fallback |
| **Clustering** | scikit-learn DBSCAN + cosine similarity |
| **Backend** | FastAPI · SQLite · APScheduler · Pydantic |
| **Frontend** | Vanilla JS · CSS · Inter + Plus Jakarta Sans |
| **Serving** | FastAPI `StaticFiles` · `FileResponse` |
| **Data** | Google News RSS (12 feeds) · feedparser |

---

## Running Locally

```bash
# 1. Clone and enter
git clone https://github.com/YOUR_USERNAME/news-that-matters.git
cd news-that-matters

# 2. Create virtualenv and install deps
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Add your Gemini API key
echo "GEMINI_API_KEY=your_key_here" > .env
# Free key → https://aistudio.google.com/app/apikey

# 4. Start the server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# 5. Open
open http://localhost:8001      # macOS
# Or just visit http://localhost:8001 in any browser
```

On first boot the pipeline runs automatically — takes ~30 seconds to fetch, cluster, and enrich. After that the brief refreshes hourly in the background.

**No Gemini key?** The app ships with a built-in static brief and works offline. You'll see a "Showing sample brief" banner.

---

## Architecture Decisions

25 Architecture Decision Records live in [`DECISIONS.md`](DECISIONS.md) — including why DBSCAN over k-means, why rep+persona over pytrends, why two-pass LLM, and why TF-IDF as fallback. Written in the style of a production engineering team.

---

## Why I Built This

I wanted to build something that touched every layer of an AI product end-to-end: data ingestion, ML clustering, prompt engineering, LLM cost optimisation, API design, and UI/UX — not just an LLM wrapper.

The scoring formula (`0.70 × editorial coverage + 0.30 × persona relevance`) is the core product decision. The two numbers are visible on every card so the AI's reasoning is never a black box.

---

## Project Status

✅ Pipeline — fetch, cluster, score, enrich  
✅ API — FastAPI + SQLite cache + hourly scheduler  
✅ UI — swipe cards, AI score hero, breakdown sheet, sources  
🔜 Deployment — Railway / Render (next milestone)  
🔜 Persona selector — choose your professional context  
🔜 PWA manifest — home screen install  

---

## License

MIT — see [`LICENSE`](LICENSE) if one exists, otherwise free to use and learn from.
