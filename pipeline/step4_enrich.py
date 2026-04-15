"""
pipeline/step4_enrich.py — Two-Pass LLM Enrichment

Pass 1 (cheap):  1 batch LLM call → sector tags for all ~15 candidates
                 → persona_score → re-rank → select top 5
Pass 2 (full):   5 individual LLM calls → heading, summary, why_it_matters

This eliminates the selection bias from step 3's rep-only ranking.
Step 3 sends ~15 candidates ranked by editorial coverage (rep_score).
Pass 1 adds the persona dimension ("does an SV professional care?").
Pass 2 enriches only the correctly-selected top 5.

Total LLM cost: 1 cheap batch call + 5 full calls = 6 calls
(vs 5 calls before, but now the right 5 stories are selected).

Provider selection (LLM_PROVIDER env var):
  gemini  — Google Gemini Flash (default)
  groq    — Groq llama-3.3-70b-versatile

Usage:
    python pipeline/step4_enrich.py           # reads ranked_clusters.json
    python pipeline/step4_enrich.py --dry-run # skips LLM; validates schema only

Output: output/brief.json
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
# Persona relevance scoring
#
# Weights reflect what a Silicon Valley professional (PM / founder / investor)
# cares about. Used in both Pass 1 (sector tags → selection) and Pass 2
# (full enrichment → final score). Single source of truth.
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
    Used in both Pass 1 (cheap sector tags) and Pass 2 (full enrichment).

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


# ---------------------------------------------------------------------------
# Pass 1: Cheap batch sector tagging
#
# Single LLM call — all candidate headlines in, sector tags out.
# Used to compute persona_score BEFORE selecting the top 5 for full enrichment.
# This eliminates the selection bias where step 3's rep-only ranking might
# a highly persona-relevant story that had low editorial breadth.
# ---------------------------------------------------------------------------

TOP_N_FINAL = 5   # final events after persona re-ranking

SECTOR_TAG_PROMPT = """You are a geopolitical sector classifier. For each numbered headline below,
identify the 2–3 most relevant sectors from this EXACT list:
""" + ", ".join(VALID_SECTORS) + """

Rules:
1. Use ONLY sector names from the list above. Exact spelling.
2. Assign a confidence score (0.0–1.0) for each sector.
3. Return ONLY valid JSON — no commentary.

Output JSON schema (array of objects, one per headline):
[
  {"id": 1, "sectors": [{"name": "Technology", "confidence": 0.9}, ...]},
  {"id": 2, "sectors": [{"name": "Finance", "confidence": 0.7}, ...]},
  ...
]
"""


def _build_sector_tag_message(candidates: list) -> str:
    """Build a numbered headline list for the batch sector tagging prompt."""
    lines = ["HEADLINES TO CLASSIFY:"]
    for i, sc in enumerate(candidates, 1):
        headline = sc.cluster.headline_article.title[:120]
        snippet  = sc.cluster.headline_article.body_snippet[:150].strip()
        lines.append(f"\n[{i}] {headline}")
        if snippet:
            lines.append(f"    {snippet}")
    lines.append("\nClassify all headlines now.")
    return "\n".join(lines)


def _batch_sector_tag(client, provider: str, candidates: list) -> list[list[SectorImpact]]:
    """
    Pass 1: single cheap LLM call to get sector tags for ALL candidates.
    Returns a list of SectorImpact lists, one per candidate (same order).
    On failure, returns empty lists (graceful degradation — rep_score alone decides).
    """
    user_msg = _build_sector_tag_message(candidates)
    full_prompt = f"{SECTOR_TAG_PROMPT}\n\n{user_msg}"

    log.info("Pass 1: Batch sector-tagging %d candidates in a single LLM call…", len(candidates))

    try:
        if provider == "gemini":
            from google.genai import types as genai_types
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=full_prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.2,  # even lower temp for classification
                    response_mime_type="application/json",
                ),
            )
            raw_list = json.loads(response.text)
        else:  # groq
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SECTOR_TAG_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
            )
            raw_list = json.loads(resp.choices[0].message.content)

        # Handle both {"results": [...]} and bare [...] formats
        if isinstance(raw_list, dict):
            raw_list = raw_list.get("results", raw_list.get("headlines", []))

        # Parse into SectorImpact lists, matched by id
        tagged: dict[int, list[SectorImpact]] = {}
        for entry in raw_list:
            eid = entry.get("id", 0)
            sectors = []
            for s in entry.get("sectors", []):
                name = s.get("name", "")
                conf = float(s.get("confidence", 0.5))
                if name in VALID_SECTORS:
                    sectors.append(SectorImpact(name=name, confidence=min(1.0, max(0.0, conf))))
            tagged[eid] = sectors

        # Return in candidate order (1-indexed)
        result = [tagged.get(i + 1, []) for i in range(len(candidates))]
        tagged_count = sum(1 for r in result if r)
        log.info("Pass 1: Got sector tags for %d/%d candidates.", tagged_count, len(candidates))
        return result

    except Exception as exc:
        log.warning("Pass 1: Sector tagging failed (%s). Falling back to rep_score only.", exc)
        return [[] for _ in candidates]


def _select_top_n(candidates: list, sector_tags: list[list[SectorImpact]]) -> list:
    """
    Re-rank candidates using persona_score from Pass 1 sector tags.
    Formula: 0.70 × rep_score + 0.30 × persona_score
    Returns the top TOP_N_FINAL candidates, correctly ranked.
    """
    ranked = []
    for sc, sectors in zip(candidates, sector_tags):
        p_score = _persona_score(sectors) if sectors else 0.15
        combined = round(0.70 * sc.repetition_score + 0.30 * p_score, 4)
        ranked.append((combined, p_score, sc, sectors))

    ranked.sort(key=lambda x: x[0], reverse=True)
    selected = ranked[:TOP_N_FINAL]

    log.info("Pass 1 → Re-ranked. Top %d selected for full enrichment:", len(selected))
    for i, (score, p, sc, _) in enumerate(selected, 1):
        log.info(
            "  #%d  combined=%.3f (rep=%.2f persona=%.2f)  '%s'",
            i, score, sc.repetition_score, p,
            sc.cluster.headline_article.title[:50],
        )

    return selected

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
6. LENGTH GUARDRAILS — obey these strictly:
   - "summary": EXACTLY 2 sentences. Maximum 40 words total.
     Sentence 1: who did what (the core event).
     Sentence 2: the single most important immediate consequence.
     Cut every word that does not add information. Be precise, not comprehensive.
   - "why_it_matters": EXACTLY 1 sentence. Maximum 25 words.
     State ONE concrete, specific implication for a Silicon Valley professional.
     Begin with the impact or action — not with context or background.
     Examples of good form:
       "AI chip export controls tighten further if sanctions re-escalate, freezing orders already in the BIS pipeline."
       "Dollar weakness inflates dollar-denominated cloud and hardware costs for non-US tech firms by roughly 3–5%."
     Do NOT hedge. Do NOT write "may", "could potentially", or "might". Name the specific impact.

OUTPUT JSON SCHEMA:
{
  "event_heading":    "<string — the geopolitical thesis in 10-15 words>",
  "summary":          "<EXACTLY 2 sentences, max 40 words: sentence 1 = who/what, sentence 2 = key consequence>",
  "why_it_matters":   "<EXACTLY 1 sentence, max 25 words: one concrete SV-professional implication>",
  "sectors_impacted": [{"name": "<sector>", "confidence": <0.0-1.0>}]
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
    required = {"event_heading", "summary", "why_it_matters", "sectors_impacted"}
    missing = required - raw.keys()
    if missing:
        raise ValueError(f"Missing keys: {missing}")

    for field in ("event_heading", "summary", "why_it_matters"):
        if not isinstance(raw[field], str) or not raw[field].strip():
            raise ValueError(f"'{field}' must be a non-empty string")

    import re as _re
    _sent_split = _re.compile(r'(?<=[.!?])\s+')

    # summary: exactly 2 sentences — soft trim if over, hard retry if under.
    _sum_sentences = [s for s in _sent_split.split(raw["summary"].strip()) if s.strip()]
    if len(_sum_sentences) < 1:
        raise ValueError("'summary' is empty. Retrying.")
    if len(_sum_sentences) > 2:
        log.warning("'summary' has %d sentences — trimming to 2.", len(_sum_sentences))
        raw["summary"] = " ".join(_sum_sentences[:2])

    # why_it_matters: exactly 1 sentence — soft trim if over.
    _why_sentences = [s for s in _sent_split.split(raw["why_it_matters"].strip()) if s.strip()]
    if len(_why_sentences) < 1:
        raise ValueError("'why_it_matters' is empty. Retrying.")
    if len(_why_sentences) > 1:
        log.warning("'why_it_matters' has %d sentences — trimming to 1.", len(_why_sentences))
        raw["why_it_matters"] = _why_sentences[0]

    # Word-count sanity — soft trim on summary, warn on why.
    _sum_words = raw["summary"].split()
    if len(_sum_words) > 45:
        raw["summary"] = " ".join(_sum_words[:45]).rstrip(",;") + "."
        log.warning("'summary' word count trimmed to 45.")

    _why_words = raw["why_it_matters"].split()
    if len(_why_words) > 30:
        raw["why_it_matters"] = " ".join(_why_words[:30]).rstrip(",;") + "."
        log.warning("'why_it_matters' word count trimmed to 30.")

    if not isinstance(raw["sectors_impacted"], list):
        raise ValueError("sectors_impacted must be a list")

    if len(raw["sectors_impacted"]) == 0:
        # Soft warn — caller will fall back to Pass 1 sector tags
        log.warning("sectors_impacted is empty — will use Pass 1 tags as fallback")
        return  # skip further sector validation; caller handles it

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
                wait = 20 * attempt   # 20s, then 40s — 429 needs a full rate-limit window
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


def _make_mock_event(sc: ScoredCluster, rank: int,
                     pass1_sectors: list[SectorImpact] | None = None) -> EnrichedEvent:
    """Dry-run mock — no LLM call. Validates schema only."""
    sectors = pass1_sectors or [SectorImpact(name="Technology", confidence=0.9)]
    return EnrichedEvent(
        rank=rank,
        trend_score=sc.trend_score,
        trend_insight=sc.trend_insight,
        event_heading=f"[DRY RUN] {sc.cluster.headline_article.title[:60]}",
        summary=(
            "This is a dry-run summary. No LLM was called. "
            "Add GEMINI_API_KEY to .env and run without --dry-run."
        ),
        why_it_matters=(
            "Dry-run mode active. This field would contain persona-tailored "
            "analysis for a Silicon Valley professional."
        ),
        sectors_impacted=sectors,
        source_articles=sc.cluster.articles,
        signal_source="dry-run",
    )


def enrich_clusters(
    trend_result: TrendResult,
    dry_run: bool = False,
) -> Brief:
    """
    Two-pass LLM enrichment pipeline:

      Pass 1 (cheap):  1 batch LLM call → sector tags for all candidates
                       → compute persona_score → re-rank → select top 5
      Pass 2 (full):   5 individual LLM calls → full enrichment
                       (heading, summary, why_it_matters, sectors)

    This eliminates the selection bias where step 3's rep-only ranking
    might gate out a highly persona-relevant story.
    """
    candidates = [sc for sc in trend_result.ranked_clusters if sc.for_llm]
    _provider_label = "DRY RUN" if dry_run else os.getenv("LLM_PROVIDER", "gemini").upper()
    log.info(
        f"Step 4: Two-pass enrichment for {len(candidates)} candidates ({_provider_label})"
    )

    # ── Initialise LLM client ───────────────────────────────────────────────────────
    if not dry_run:
        provider = os.getenv("LLM_PROVIDER", "gemini").lower()
        if provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
                raise EnvironmentError(
                    "\n\n  ❌  GEMINI_API_KEY not set.\n"
                    "  1. Get a free key: https://aistudio.google.com/apikey\n"
                    "  2. Set GEMINI_API_KEY in .env\n"
                    "  Or run with --dry-run to validate schema only.\n"
                )
            from google import genai
            client = genai.Client(api_key=api_key)
            log.info(f"Step 4: Provider=gemini ({GEMINI_MODEL})")
        elif provider == "groq":
            api_key = os.getenv("GROQ_API_KEY", "")
            if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
                raise EnvironmentError(
                    "\n\n  ❌  GROQ_API_KEY not set.\n"
                    "  NOTE: Groq blocked on Walmart network — use LLM_PROVIDER=gemini\n"
                )
            from groq import Groq
            client = Groq(api_key=api_key)
            log.info(f"Step 4: Provider=groq ({GROQ_MODEL})")
        else:
            raise EnvironmentError(f"Unknown LLM_PROVIDER='{provider}'.")
    else:
        provider = "dry-run"
        client = None

    # ── Pass 1: Batch sector tagging + persona re-rank ─────────────────────────
    if dry_run:
        # Dry-run: no LLM call, just take the top 5 by rep_score
        sector_tags = [[SectorImpact(name="Technology", confidence=0.9)]
                       for _ in candidates]
    else:
        sector_tags = _batch_sector_tag(client, provider, candidates)

    selected = _select_top_n(candidates, sector_tags)

    # ── Pass 2: Full enrichment on the correctly-selected top N ────────────
    log.info("Pass 2: Full enrichment on %d events…", len(selected))
    events: list[EnrichedEvent] = []

    for final_rank, (combined_score, p1_persona, sc, p1_sectors) in enumerate(selected, 1):
        t0 = time.time()
        try:
            if dry_run:
                event = _make_mock_event(sc, final_rank, p1_sectors)
            else:
                raw = (
                    _call_gemini(client, sc) if provider == "gemini"
                    else _call_groq(client, sc)
                )
                # Pass 2 sectors; fall back to Pass 1 tags if LLM returned empty
                p2_sectors = [
                    SectorImpact(name=s["name"], confidence=float(s["confidence"]))
                    for s in sorted(
                        raw["sectors_impacted"],
                        key=lambda x: x["confidence"],
                        reverse=True,
                    )
                ] if raw.get("sectors_impacted") else p1_sectors

                if not p2_sectors:
                    log.warning(f"  #{final_rank}: no sectors from Pass 1 or Pass 2 — defaulting to Technology")
                    p2_sectors = [SectorImpact(name="Technology", confidence=0.5)]
                event = EnrichedEvent(
                    rank=final_rank,
                    trend_score=combined_score,
                    trend_insight="",  # set below
                    event_heading=raw["event_heading"],
                    summary=raw["summary"],
                    why_it_matters=raw["why_it_matters"],
                    sectors_impacted=p2_sectors,
                    source_articles=sc.cluster.articles,
                    signal_source="persona",
                )

            # ── Final score: use Pass 2 sectors (more accurate) ─────────────
            p2_score  = _persona_score(event.sectors_impacted)
            event.trend_score = round(
                0.70 * sc.repetition_score + 0.30 * p2_score, 4
            )
            rep_pct   = int(round(sc.repetition_score * 100))
            pers_pct  = int(round(p2_score * 100))
            total_pct = int(round(event.trend_score * 100))
            event.trend_insight = (
                f"{total_pct}% signal score: {rep_pct}% coverage (70%) "
                f"+ {pers_pct}% persona relevance (30%). "
                f"Sectors: {', '.join(s.name for s in event.sectors_impacted[:3])}."
            )

            elapsed = time.time() - t0
            log.info(
                f"  #{event.rank} ✓ {elapsed:.1f}s | signal={event.trend_score:.3f} "
                f"(rep={sc.repetition_score:.2f} persona={p2_score:.2f}) "
                f"| \"{event.event_heading[:45]}\""
            )
            events.append(event)

        except RuntimeError as exc:
            log.error(f"  #{final_rank} ✗ Skipping — all retries exhausted: {exc}")
            continue

        # Small pause between Pass 2 calls to respect Gemini's 15 RPM free tier
        if final_rank < len(selected):
            time.sleep(3)

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
        print(f"\n   SOURCES ({len(arts)})")
        for a in arts:
            pub = a.published_at.strftime("%b %d")
            print(f"   · [{pub}] {a.title[:55]}  —  {a.source_name}")
        print()
    print("─" * 60)


if __name__ == "__main__":
    main()
