# 🐶 Signal Brief — AI Agent Instructions
> This file tells the AI coding assistant HOW to work on this project.
> Read `CONTEXT.md` first for the what. This file is the how.

---

## Session Start Checklist

Every session, before writing code:

1. Read `CONTEXT.md` — understand current state + active milestone
2. Read `PROGRESS.md` — know exactly what's done and what's next
3. Read `DECISIONS.md` — don't re-litigate solved problems
4. Read the relevant PRD section for the active milestone
5. Explore existing files before modifying anything

---

## Session End Checklist

Every session, before closing:

1. **`DECISIONS.md`** — log any new ADR made during this session.
   Any trade-off, dropped dependency, changed weight, or architectural choice = new ADR.
   Do this now — not next session.
2. **`PROGRESS.md`** — update milestone status, check off completed exit criteria,
   and write the "Next Session: Start Here" block.
3. **Commit** — `docs(progress): update M[N] status — [what was done]`.
   Never end a session without committing updated docs.

---

## Code Conventions

### Python (backend + pipeline)

```
Style       : PEP 8; Black formatter; 88 char line limit
Types       : Full type hints everywhere. No bare `dict` or `list`.
Models      : Pydantic v2 for all data shapes (schemas.py is the truth)
Imports     : stdlib → third-party → local (isort order)
Docstrings  : One-line for functions < 10 lines. Full for anything complex.
Error handling: Explicit try/except; never bare `except:`; always log errors
Logging     : `logging` stdlib; structured messages: "Step N: [action] — [result]"
No globals  : Pass config/clients via dependency injection or function args
```

**File size rule:** Keep files under 300 lines. Split by responsibility, not by line count.
If `step1_fetch.py` naturally fits in 80 lines — great. Don't pad it.

### TypeScript / React Native (mobile)

```
Style       : Prettier defaults; 2-space indent; single quotes
Components  : Functional only; no class components
State       : useState + useEffect for local; no Redux for MVP
Types       : Strict TypeScript; no `any`; define interfaces in types/
Naming      : PascalCase components; camelCase functions/vars; SCREAMING_SNAKE for constants
Styles      : StyleSheet.create() only; no inline style objects
Accessibility: Every touchable element gets accessibilityLabel + accessibilityRole
```

**Component rule:** One component per file. If a component needs 3+ sub-components,
extract them. If a file grows past 200 lines, it's doing too much.

---

## Architecture Rules (enforce these strictly)

| Rule | Why |
|------|-----|
| Pipeline NEVER called from API request handler | Would break the <1s NFR |
| API ALWAYS serves from SQLite cache | Cache is the contract; pipeline is background |
| Pydantic validates ALL LLM output | Never trust raw LLM strings |
| Articles sorted by `published_at DESC` at DB level | Not in application code |
| Trend score weights are constants in a config file | Never magic numbers in logic |
| LLM temperature NEVER above 0.5 | Factuality over creativity |
| `is_current = True` flipped atomically | Prevents serving partial brief |

---

## Testing Conventions

### Backend
- Unit test each pipeline step independently with fixture data
- Fixture data lives in `tests/fixtures/` — real sample RSS XML + cluster JSON
- Never call real external APIs in unit tests — mock PRAW, pytrends, Groq
- API smoke tests (`tests/test_api.py`) MAY call the running local server
- Test file mirrors source: `pipeline/step1_fetch.py` → `tests/test_step1_fetch.py`

```bash
# Run unit tests only
pytest tests/ -v -m "not integration"

# Run integration tests (needs real API keys)
pytest tests/ -v -m integration

# Run a single test file
pytest tests/test_step1_fetch.py -v
```

### Mobile
- Component tests: React Native Testing Library
- E2E: Detox (added in M7)
- Snapshot tests: only for leaf components (tags, bars); never full screens

---

## Milestone-by-Milestone Working Guide

### M1 — Working on `pipeline/step1_fetch.py` and `step2_cluster.py`

**Test command:**
```bash
python scripts/test_m1.py
# Should print: cluster count, article count per cluster, date range
```
**Done when:** `output/clusters.json` validates against this shape:
```json
{
  "clusters": [
    {
      "cluster_id": 0,
      "articles": [
        { "title": "...", "url": "...", "published_at": "...", "source": "...", "body_snippet": "..." }
      ]
    }
  ],
  "total_articles": 42,
  "generated_at": "2026-04-08T18:00:00Z"
}
```

### M2 — Working on `pipeline/step3_score.py`

**Test command:**
```bash
python pipeline/step3_score.py
# Should print: ranked clusters with trend_score, top 7 highlighted
```
**Watch out for:** pytrends rate limiting. Add `time.sleep(2)` between calls.
PRAW needs a Reddit app credential — check `DECISIONS.md` for env var names.

### M3 — Working on `pipeline/step4_enrich.py`

**Test command:**
```bash
python pipeline/step4_enrich.py
# Should pretty-print the full 5-event brief
```
**Guardrail test:**
```bash
pytest tests/test_hallucination_guard.py -v
# Checks: no financial advice, no invented entities, schema valid
```
**Groq API key:** stored in `.env` as `GROQ_API_KEY`. Never hardcode.

### M4 — Working on `app/`

**Test command:**
```bash
uvicorn app.main:app --reload &
python tests/test_api.py
# Should: GET /brief returns 200, schema valid, second call faster
```
**Verify cache is working:**
```bash
time curl -s localhost:8000/brief > /dev/null  # first call
time curl -s localhost:8000/brief > /dev/null  # second call — must be faster
```

### M5 — Working on `mobile/`

**Run:**
```bash
cd mobile && npx expo start
# Scan QR in Expo Go
```
**Check on device:** cards render, trend bar animates, sector tags show correct colors.

### M6 — Working on `mobile/screens/ArticleListScreen.tsx`

**Verify manually:**
- Tap card → navigate to article list
- Articles are newest → oldest (check timestamps)
- Date group headers appear for different days
- Tapping article opens browser (not in-app view)

---

## Anti-Patterns — Never Do These

```
❌ Don't call the LLM more than once per event per pipeline run
❌ Don't store user data, IPs, device IDs, or any PII
❌ Don't make external API calls inside synchronous request handlers
❌ Don't catch and silently swallow exceptions — always log
❌ Don't hardcode API keys — use .env + python-dotenv
❌ Don't truncate articles in the API response (UI truncates, not API)
❌ Don't use `any` type in TypeScript
❌ Don't write components longer than 200 lines — split them
❌ Don't change LLM temperature above 0.5
❌ Don't add features not in the current milestone scope — log to PROGRESS.md backlog
```

---

## Environment Variables

```bash
# .env (never commit this file)
GROQ_API_KEY=gsk_...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=signal-brief/1.0 by /u/yourusername
DATABASE_URL=sqlite:///./signal_brief.db
PIPELINE_INTERVAL_MINUTES=60
LOG_LEVEL=INFO
```

---

## Git Conventions

```
Branch naming : feature/m1-rss-fetch | fix/cluster-empty-result | chore/deps-update
Commit format : type(scope): description
  Types: feat | fix | test | docs | chore | refactor
  Examples:
    feat(pipeline): add RSS fetch for 5 Google News feeds
    fix(cluster): handle edge case when fewer than 2 articles in feed
    test(api): add smoke test for stale cache fallback
    docs(progress): update M1 exit criteria to done

Never force-push. Commit after each exit criterion is met. Roll forward, not back.
```

---

## When You're Stuck

1. **LLM output doesn't match schema** → Check temperature (must be ≤ 0.3); add `json_object` response format to Groq call; increase retry count to 3
2. **pytrends returns empty** → Topic keyword too specific; try a shorter 2-word phrase; add try/except and default score to 0.0
3. **DBSCAN produces 1 giant cluster** → eps too large; reduce to 0.2 and re-test; ensure embeddings are L2-normalized
4. **Expo can't reach API** → Check API host is `0.0.0.0` not `127.0.0.1`; check device is on same WiFi
5. **Pipeline takes > 5 min** → Profile step by step; LLM calls usually the bottleneck; check Groq response latency

---

*Last updated: 2026-04-08 | Read alongside CONTEXT.md every session*
