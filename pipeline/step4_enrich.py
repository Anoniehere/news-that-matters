"""
pipeline/step4_enrich.py — M3: LLM Enrichment

For each of the top-5 trend-scored clusters, calls an LLM to produce:
event_heading, summary, why_it_matters, sectors_impacted, timeline_context.

Provider selection (LLM_PROVIDER env var):
  gemini  — Google Gemini Flash (default; works on Walmart network via googleapis.com)
  groq    — Groq llama-3.3-70b-versatile (faster; blocked on Walmart proxy)

Guardrails:
  - No financial advice (system prompt + post-validation check)
  - Source-grounded only (model instructed to use provided articles)
  - Temperature 0.3 (factuality over creativity — AGENTS.md hard rule)
  - Pydantic schema validation; retries up to MAX_RETRIES on failure

Usage:
    python pipeline/step4_enrich.py           # reads ranked_clusters.json
    python pipeline/step4_enrich.py --dry-run # skips LLM; validates schema only

Output: output/brief.json  (validates against Brief schema)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.schemas import (
    Article, Brief, EnrichedEvent, ScoredCluster,
    SectorImpact, TrendResult,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MAX_RETRIES      = 2
LLM_TEMPERATURE  = 0.3          # AGENTS.md hard rule — never raise above 0.5
GROQ_MODEL       = "llama-3.3-70b-versatile"
GEMINI_MODEL     = "gemini-2.5-flash"
OUTPUT_PATH      = Path("output/brief.json")

VALID_SECTORS = [
    "Technology", "Finance", "Policy & Regulation", "Labour & Employment",
    "Healthcare", "Energy", "Defence & Security", "Education",
    "Media & Entertainment", "Retail & E-commerce", "Real Estate",
    "Manufacturing", "Agriculture",
]

FINANCIAL_ADVICE_PHRASES = [
    "buy", "sell", "invest in", "short", "long position",
    "price target", "stock pick", "you should purchase",
]

# ---------------------------------------------------------------------------
# Persona relevance scoring (Option 1 — replaces dead pytrends 30% weight)
#
# Weights reflect what a Silicon Valley professional (PM / founder / investor)
# actually cares about in a geopolitical brief. Sector names must match
# VALID_SECTORS exactly. Anything not listed defaults to 0.2 (low relevance).
# Tuning: raise a weight if that sector keeps producing under-ranked stories;
# lower it if stories feel noisy. Single source of truth — change here only.
# ---------------------------------------------------------------------------

PERSONA_WEIGHTS: dict[str, float] = {
    "Technology":          0.90,   # AI, chips, export controls — core domain
    "Finance":             0.80,   # dollar, rates, investment flows
    "Policy & Regulation": 0.75,   # antitrust, data privacy, AI governance
    "Energy":              0.60,   # supply chain, data centre costs
    "Defence & Security":  0.45,   # relevant but not daily-driver for SV
    "Labour & Employment": 0.40,   # visa policy, H-1B affects talent pipeline
    "Manufacturing":       0.35,   # semiconductor fabs, hardware supply chain
    "Agriculture":         0.15,   # low relevance for SV persona
    "Healthcare":          0.20,
    "Education":           0.20,
    "Media & Entertainment":   0.25,
    "Retail & E-commerce":     0.30,
    "Real Estate":             0.15,
}


def _persona_score(sectors: list[SectorImpact]) -> float:
    """
    Compute audience-relevance score [0.0–1.0] for the SV professional persona.
    Replaces the dead pytrends 30% weight in the final trend_score.

    Formula: weighted sum of (sector_weight × llm_confidence), normalised.
    Cap at 1.0; floor at 0.15 so even low-relevance events aren’t zeroed out.
    """
    if not sectors:
        return 0.15
    raw = sum(
        PERSONA_WEIGHTS.get(s.name, 0.20) * s.confidence
        for s in sectors
    )
    # Normalise against the max possible score (all top sectors at confidence=1)
    max_possible = sum(sorted(PERSONA_WEIGHTS.values(), reverse=True)[:len(sectors)])
    normalised = raw / max_possible if max_possible > 0 else raw
    return round(min(1.0, max(0.15, normalised)), 4)

SYSTEM_PROMPT = """You are a senior geopolitical intelligence analyst writing for busy Silicon Valley
professionals aged 28–45 — product managers, startup founders, and early-stage investors.
They are smart, time-pressed, and value signal over noise. They need to understand how
global power dynamics, trade conflicts, and national security events affect their work.

SCOPE: You analyse GEOPOLITICAL events only — international relations, diplomatic moves,
trade wars and sanctions, military conflicts, great-power competition, foreign policy
decisions with US or global impact. If a cluster of articles is not geo-political, skip it.

STRICT RULES you must follow:
1. Only use facts present in the SOURCE ARTICLES provided. Never invent events, dates,
   people, companies, or statistics.
2. Do NOT give financial advice. Do not suggest buying, selling, or holding any asset.
3. Write in clear, direct prose. No bullet points. No headers inside fields.
4. Tailor "why_it_matters" specifically to a Silicon Valley professional — explain how
   the geopolitical event ripples into tech supply chains, AI export controls, startup
   funding (US-China investment restrictions), talent/visa policy, data sovereignty,
   satellite/telecom competition, or regulatory risk.
5. Return ONLY valid JSON matching the schema below. No extra commentary.
6. LENGTH GUARDRAIL:
   - "summary":        minimum 3 sentences, maximum 5 sentences.
     Cover: what happened, who is involved, when, and the immediate consequence.
     Every sentence must be complete. Do NOT truncate mid-thought.
   - "why_it_matters": minimum 3 sentences, maximum 5 sentences.
     Cover: direct impact on Silicon Valley professionals, second-order effects,
     what to watch for next, and one concrete implication for tech/startup ecosystem.
     Every sentence must be complete. Do NOT truncate mid-thought.
   - "timeline_context": exactly 2 sentences.
     Sentence 1 — ORIGIN: State specifically when and how this story started.
       Use a concrete date, month, or named event (e.g. "This dispute escalated in
       March 2026 when...", "Tensions began after the January G7 summit...").
       Do NOT write "recently", "ongoing", "over the past few months", or any
       vague timeframe. A date or named trigger is required.
     Sentence 2 — WATCHPOINT: Name one specific, concrete thing to watch for next.
       Examples: a vote, a deadline, a summit, a court ruling, a trade negotiation
       round, a sanctions review date, a central bank meeting.
       Do NOT write "future developments", "remains to be seen", "is evolving",
       "will depend on", "the situation may", or any hedge that provides no
       actionable information. A named event or deadline is required.

OUTPUT JSON SCHEMA:
{
  "event_heading":     "<string — the geopolitical thesis in 10-15 words>",
  "summary":           "<string — 3-5 complete sentences. What happened, who, when, consequence.>",
  "why_it_matters":    "<string — 3-5 complete sentences, Silicon Valley geo-political lens.>",
  "sectors_impacted":  [{"name": "<sector>", "confidence": <0.0-1.0>}],
  "timeline_context":  "<2 sentences: sentence 1 = specific origin date/trigger, sentence 2 = named next watchpoint>"
}

Valid sector names (use ONLY these):
""" + ", ".join(VALID_SECTORS)


def _build_user_message(sc: ScoredCluster) -> str:
    """Assemble the article context block for the LLM prompt."""
    lines = [
        f"TREND RANK: #{sc.rank}  |  TREND SCORE: {sc.trend_score:.3f}",
        f"ARTICLE COUNT: {sc.cluster.size}",
        "",
        "SOURCE ARTICLES:",
    ]
    for i, art in enumerate(sc.cluster.articles, 1):
        pub = art.published_at.strftime("%b %d, %Y")
        lines += [
            f"\n[{i}] {art.title}",
            f"    Source: {art.source_name}  |  Published: {pub}",
            f"    {art.body_snippet.strip()}" if art.body_snippet.strip() else "",
        ]
    lines += [
        "",
        "Produce the JSON analysis now.",
    ]
    return "\n".join(lines)


def _validate_llm_dict(raw: dict) -> None:
    """
    Raise ValueError with a clear message if the LLM output is structurally wrong.
    Called before Pydantic so we get actionable error messages on retry.
    """
    required = {"event_heading", "summary", "why_it_matters",
                 "sectors_impacted", "timeline_context"}
    missing = required - raw.keys()
    if missing:
        raise ValueError(f"Missing keys: {missing}")

    for field in ("event_heading", "summary", "why_it_matters", "timeline_context"):
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise ValueError(f"'{field}' must be a non-empty string")

    # Sentence-count guardrail (PRD: summary + why_it_matters → 3-5 sentences each).
    # Count by splitting on sentence-ending punctuation followed by whitespace.
    import re as _re
    _sent_split = _re.compile(r'(?<=[.!?])\s+')
    for field in ("summary", "why_it_matters"):
        sentences = [s for s in _sent_split.split(raw[field].strip()) if s.strip()]
        if len(sentences) < 3:
            raise ValueError(
                f"'{field}' has only {len(sentences)} sentence(s) — minimum is 3. "
                f"LLM truncated. Retrying."
            )
        if len(sentences) > 5:
            # Soft trim to 5 — preserves good content, avoids wasted retry
            log.warning("'%s' has %d sentences — trimming to 5.", field, len(sentences))
            raw[field] = " ".join(sentences[:5])

    # timeline_context guardrails — must be specific, not filler.
    _tl = raw["timeline_context"].strip()
    _tl_lower = _tl.lower()

    # Must have exactly 2 sentences (origin + watchpoint).
    _tl_sentences = [s for s in _sent_split.split(_tl) if s.strip()]
    if len(_tl_sentences) < 2:
        raise ValueError(
            f"'timeline_context' has only {len(_tl_sentences)} sentence(s) — "
            f"must have 2: one origin sentence + one watchpoint sentence. Retrying."
        )
    if len(_tl_sentences) > 2:
        # Soft trim — keep only the 2 most informative sentences
        log.warning("'timeline_context' has %d sentences — trimming to 2.", len(_tl_sentences))
        raw["timeline_context"] = " ".join(_tl_sentences[:2])
        _tl_lower = raw["timeline_context"].lower()

    # Must contain at least one temporal anchor (month name, year, or numeric date).
    import re as _re2
    _temporal_pattern = _re2.compile(
        r'\b(january|february|march|april|may|june|july|august|september|october|'
        r'november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec|'
        r'2024|2025|2026|q1|q2|q3|q4|this week|last week|monday|tuesday|'
        r'wednesday|thursday|friday|saturday|sunday|\d{1,2}/\d{1,2}|'
        r'yesterday|last month|next week|next month)\b',
        _re2.IGNORECASE
    )
    if not _temporal_pattern.search(_tl):
        raise ValueError(
            "'timeline_context' lacks a specific temporal anchor (month, year, or date). "
            "Must state when this story started with a concrete timeframe. Retrying."
        )

    # Must NOT be generic filler — banned pal zero information.
    _tl_banned = [
        "remains to be seen",
        "remains uncertain",
        "future developments",
        "will likely depend",
        "is expected to continue",
        "trajectory and outcome",
        "evolving geopolitical",
        "evolving dynamics",
        "the situation may",
        "ongoing tensions",
        "ongoing critical",
        "continues to evolve",
        "will depend on how",
        "the next steps involve observing",
    ]
    for phrase in _tl_banned:
        if phrase in _tl_lower:
            raise ValueError(
                f"'timeline_context' contains banned filler phrase: '{phrase}'. "
                f"Must name a specific origin event and a concrete watchpoint. Retrying."
            )

    if not isinstance(raw["sectors_impacted"], list) or len(raw["sectors_impacted"]) == 0:
        raise ValueError("sectors_impacted must be a non-empty list")

    for s in raw["sectors_impacted"]:
        if not isinstance(s, dict) or "name" not in s or "confidence" not in s:
            raise ValueError(f"Bad sector entry: {s}")
        if s["name"] not in VALID_SECTORS:
            raise ValueError(f"Unknown sector '{s['name']}' — must be one of {VALID_SECTORS}")
        if not (0.0 <= float(s["confidence"]) <= 1.0):
            raise ValueError(f"confidence out of range: {s['confidence']}")

    if len(raw["sectors_impacted"]) > 5:
        raw["sectors_impacted"] = raw["sectors_impacted"][:5]

    # Financial advice guard
    all_text = " ".join([
        raw["summary"], raw["why_it_matters"], raw["event_heading"]
    ]).lower()
    for phrase in FINANCIAL_ADVICE_PHRASES:
        if phrase in all_text:
            raise ValueError(
                f"Financial advice detected (phrase: '{phrase}'). Regenerating."
            )


def _call_gemini(client, sc: ScoredCluster) -> dict:
    """
    Call Google Gemini Flash with retries. Returns validated raw dict.
    Works on Walmart network — googleapis.com is proxy-whitelisted.
    Uses google-genai SDK (v1+). Raises RuntimeError if all retries exhausted.
    """
    from google.genai import types as genai_types

    user_msg  = _build_user_message(sc)
    last_err: Exception | None = None
    full_prompt = f"{SYSTEM_PROMPT}\n\nUSER REQUEST:\n{user_msg}"

    for attempt in range(1, MAX_RETRIES + 2):
        log.info(f"  LLM call attempt {attempt}/{MAX_RETRIES + 1} — "
                 f"cluster #{sc.rank} ({sc.cluster.size} articles) [Gemini]")
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=LLM_TEMPERATURE,
                    response_mime_type="application/json",
                ),
            )
            raw = json.loads(response.text)
            _validate_llm_dict(raw)
            return raw

        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            log.warning(f"  Attempt {attempt} failed validation: {e}")
            if attempt <= MAX_RETRIES:
                time.sleep(1)
        except Exception as e:
            last_err = e
            log.warning(f"  Attempt {attempt} API error: {e}")
            if attempt <= MAX_RETRIES:
                wait = 5 * attempt   # 5s, then 10s — respect 15 RPM free tier
                log.info(f"  Waiting {wait}s before retry...")
                time.sleep(wait)

    raise RuntimeError(
        f"All {MAX_RETRIES + 1} Gemini attempts failed for cluster #{sc.rank}. "
        f"Last error: {last_err}"
    )


def _call_groq(client, sc: ScoredCluster) -> dict:
    """
    Call Groq with retries. Returns validated raw dict.
    NOTE: blocked on Walmart network — use LLM_PROVIDER=gemini on Walmart WiFi/VPN.
    Raises RuntimeError if all retries exhausted.
    """
    user_msg = _build_user_message(sc)
    last_err: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 2):
        log.info(f"  LLM call attempt {attempt}/{MAX_RETRIES + 1} — "
                 f"cluster #{sc.rank} ({sc.cluster.size} articles) [Groq]")
        try:
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                temperature=LLM_TEMPERATURE,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
            )
            raw_text = resp.choices[0].message.content
            raw = json.loads(raw_text)
            _validate_llm_dict(raw)
            return raw

        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            log.warning(f"  Attempt {attempt} failed: {e}")
            if attempt <= MAX_RETRIES:
                time.sleep(1)

    raise RuntimeError(
        f"All {MAX_RETRIES + 1} Groq attempts failed for cluster #{sc.rank}. "
        f"Last error: {last_err}"
    )


def _make_mock_event(sc: ScoredCluster) -> EnrichedEvent:
    """Dry-run mock — no LLM call. Validates schema only."""
    return EnrichedEvent(
        rank=sc.rank,
        trend_score=sc.trend_score,
        trend_insight=sc.trend_insight,
        event_heading=f"[DRY RUN] {sc.cluster.headline_article.title[:60]}",
        summary=(
            "This is a dry-run summary. No LLM was called. "
            "Add GROQ_API_KEY to .env and run without --dry-run."
        ),
        why_it_matters=(
            "Dry-run mode active. This field would contain persona-tailored "
            "analysis for a Silicon Valley professional."
        ),
        sectors_impacted=[SectorImpact(name="Technology", confidence=0.9)],
        timeline_context="Dry-run. No timeline generated.",
        source_articles=sc.cluster.articles,
        signal_source=sc.signal_source,
    )


def enrich_clusters(
    trend_result: TrendResult,
    dry_run: bool = False,
) -> Brief:
    """
    Core M3 function. Enriches all for_llm=True clusters.
    Returns a validated Brief ready for output/brief.json.
    """
    candidates = [sc for sc in trend_result.ranked_clusters if sc.for_llm]
    _provider_label = "DRY RUN" if dry_run else os.getenv("LLM_PROVIDER", "gemini").upper()
    log.info(f"Step 4: Enriching {len(candidates)} clusters via LLM ({_provider_label})…")

    if not dry_run:
        provider = os.getenv("LLM_PROVIDER", "gemini").lower()

        if provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
                raise EnvironmentError(
                    "\n\n  ❌  GEMINI_API_KEY not set.\n"
                    "  1. Get a free key (works on Walmart network): https://aistudio.google.com/apikey\n"
                    "  2. Open .env and set GEMINI_API_KEY=your_key\n"
                    "  3. Re-run this script\n"
                    "  Or run with --dry-run to validate schema only.\n"
                )
            from google import genai
            proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
            client = genai.Client(api_key=api_key)
            log.info(f"Step 4: Using provider=gemini ({GEMINI_MODEL})"
                     + (f" via proxy {proxy}" if proxy else ""))

        elif provider == "groq":
            api_key = os.getenv("GROQ_API_KEY", "")
            if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
                raise EnvironmentError(
                    "\n\n  ❌  GROQ_API_KEY not set.\n"
                    "  1. Get a free key at https://console.groq.com\n"
                    "  2. Open .env and set GROQ_API_KEY=your_key\n"
                    "  3. NOTE: Groq is blocked on Walmart network — switch to LLM_PROVIDER=gemini\n"
                )
            from groq import Groq
            client = Groq(api_key=api_key)
            log.info(f"Step 4: Using provider=groq ({GROQ_MODEL})")

        else:
            raise EnvironmentError(f"Unknown LLM_PROVIDER='{provider}'. Use 'gemini' or 'groq'.")
    else:
        provider = "dry-run"
        client = None

    events: list[EnrichedEvent] = []
    for sc in candidates:
        t0 = time.time()
        try:
            if dry_run:
                event = _make_mock_event(sc)
            else:
                raw = _call_gemini(client, sc) if provider == "gemini" else _call_groq(client, sc)
                event = EnrichedEvent(
                    rank=sc.rank,
                    trend_score=sc.trend_score,
                    trend_insight=sc.trend_insight,
                    event_heading=raw["event_heading"],
                    summary=raw["summary"],
                    why_it_matters=raw["why_it_matters"],
                    sectors_impacted=[
                        SectorImpact(name=s["name"], confidence=float(s["confidence"]))
                        for s in sorted(
                            raw["sectors_impacted"],
                            key=lambda x: x["confidence"],
                            reverse=True,
                        )
                    ],
                    timeline_context=raw["timeline_context"],
                    source_articles=sc.cluster.articles,
                    signal_source=sc.signal_source,
                )

            # ── Persona score recomputation ────────────────────────────────────
            # Replace the dead 30% social weight with audience relevance.
            # Formula: 0.70 × rep_score (coverage) + 0.30 × persona_score
            p_score   = _persona_score(event.sectors_impacted)
            event.trend_score = round(0.70 * sc.repetition_score + 0.30 * p_score, 4)
            rep_pct   = int(round(sc.repetition_score * 100))
            pers_pct  = int(round(p_score * 100))
            total_pct = int(round(event.trend_score * 100))
            event.trend_insight = (
                f"{total_pct}% signal score: {rep_pct}% coverage (70%) "
                f"+ {pers_pct}% persona relevance (30%). "
                f"Sectors: {', '.join(s.name for s in event.sectors_impacted[:3])}."
            )

            elapsed = time.time() - t0
            log.info(
                f"  #{event.rank} ✓ {elapsed:.1f}s | signal={event.trend_score:.3f} "
                f"(rep={sc.repetition_score:.2f} persona={p_score:.2f}) "
                f"| \"{event.event_heading[:45]}\""
            )
            events.append(event)

        except RuntimeError as exc:
            # A partial brief beats no brief — log and continue.
            log.error(f"  #{sc.rank} ✗ Skipping — all retries exhausted: {exc}")
            continue

    brief = Brief(events=events)
    log.info(f"Step 4: Brief built — {len(events)} events enriched.")
    return brief


def main() -> None:
    parser = argparse.ArgumentParser(description="M3 — LLM Enrichment")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip LLM calls; validate schema only")
    parser.add_argument("--input",  default="output/ranked_clusters.json",
                        help="Path to ranked_clusters.json (default: output/ranked_clusters.json)")
    parser.add_argument("--output", default=str(OUTPUT_PATH),
                        help="Where to write brief.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        log.error(f"Input file not found: {input_path}. Run M1+M2 pipeline first.")
        sys.exit(1)

    trend_result = TrendResult.model_validate_json(input_path.read_text())
    log.info(f"Loaded {len(trend_result.ranked_clusters)} ranked clusters from {input_path}")

    brief = enrich_clusters(trend_result, dry_run=args.dry_run)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(brief.model_dump_json(indent=2))
    log.info(f"Brief written → {out}")

    # Pretty-print to terminal
    print("\n" + "─" * 60)
    print(f"⚡ NEWS THAT MATTERS  —  {datetime.now().strftime('%A, %B %d %Y')}")
    print("─" * 60)
    for ev in brief.events:
        sectors = " · ".join(
            f"{s.name} {int(s.confidence*100)}%" for s in ev.sectors_impacted
        )
        arts = ev.source_articles[:3]
        print(f"\n#{ev.rank}  {ev.event_heading}")
        print(f"   Trend score : {ev.trend_score:.3f}")
        print(f"   Sectors     : {sectors}")
        print(f"\n   SUMMARY")
        print(f"   {ev.summary[:300]}…" if len(ev.summary) > 300 else f"   {ev.summary}")
        print(f"\n   WHY IT MATTERS")
        print(f"   {ev.why_it_matters[:300]}…" if len(ev.why_it_matters) > 300 else f"   {ev.why_it_matters}")
        print(f"\n   TIMELINE")
        print(f"   {ev.timeline_context}")
        print(f"\n   SOURCES ({len(arts)})")
        for a in arts:
            pub = a.published_at.strftime("%b %d")
            print(f"   · [{pub}] {a.title[:55]}  —  {a.source_name}")
        print()
    print("─" * 60)


if __name__ == "__main__":
    main()
