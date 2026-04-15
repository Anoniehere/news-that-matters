#!/usr/bin/env python3
"""
M3 Smoke Test — LLM Enrichment (step4 only)
Validates all M3 exit criteria.

Modes:
  python scripts/test_m3.py              # dry-run, no API key needed
  python scripts/test_m3.py --live       # real two-pass LLM run (GEMINI_API_KEY)
  python scripts/test_m3.py --live --fresh  # force re-fetch+cluster (slow)

Default --live behaviour: loads output/ranked_clusters.json directly (written by M2).
Steps 1-3 are SKIPPED unless --fresh is passed. M2 test already validates those.

Exit criteria (all modes):
  OK Brief validates against Brief schema
  OK 1-5 events present
  OK Every event has: rank, trend_score, event_heading, summary,
       why_it_matters, sectors_impacted, source_articles, signal_source
  OK event_heading <= 20 words
  OK summary: 1-3 sentences
  OK why_it_matters: 1-2 sentences
  OK sectors_impacted: 1-5 items, each in valid set, confidence in [0.0, 1.0]
  OK sectors sorted desc by confidence
  OK source_articles non-empty; each has title, url, published_at
  OK Events sorted ascending by rank

Live-only exit criteria (--live flag):
  OK No financial advice in any output
  OK Avg LLM latency < 15s per event
  OK Total enrichment step <= 3 minutes
  OK brief.json written to disk
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.step4_enrich import enrich_clusters, FINANCIAL_ADVICE_PHRASES, VALID_SECTORS
from models.schemas import Brief, TrendResult

SEP = "─" * 55

FINANCIAL_ADVICE_PHRASES_CHECK = [
    "buy ", "sell ", "invest in", "short ", "long position",
    "price target", "stock pick",
]


def banner(msg: str) -> None:
    print(f"\n{SEP}\n{msg}\n{SEP}")


def check(label: str, passed: bool, detail: str = "") -> bool:
    icon = "✅ PASS" if passed else "❌ FAIL"
    line = f"  {icon}  {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return passed


def count_sentences(text: str) -> int:
    """Rough sentence count — splits on . ! ? endings."""
    return len([s for s in re.split(r"[.!?]+", text) if s.strip()])


def _load_trend_result(fresh: bool) -> TrendResult:
    """
    Load ranked clusters for step4 testing.
    Default: loads output/ranked_clusters.json (fast — M2 already ran this).
    --fresh: re-runs steps 1-3 from scratch (slow, use when feeds need refresh).
    """
    ranked_path = Path("output/ranked_clusters.json")

    if not fresh and ranked_path.exists():
        result = TrendResult.model_validate_json(ranked_path.read_text())
        print(f"  ⚡ Loaded cached ranked_clusters.json "
              f"({len(result.ranked_clusters)} candidates) — skipping steps 1-3")
        return result

    print("  Running steps 1-3 (--fresh or no cached file)…")
    from pipeline.step1_fetch import fetch_all_feeds
    from pipeline.step2_cluster import embed_articles, retry_with_looser_eps
    from pipeline.step3_score import score_clusters

    fetch_result   = fetch_all_feeds(max_age_days=4)
    emb, eps       = embed_articles(fetch_result.articles)
    cluster_result = retry_with_looser_eps(fetch_result.articles, emb, base_eps=eps)
    result         = score_clusters(cluster_result)
    ranked_path.parent.mkdir(parents=True, exist_ok=True)
    ranked_path.write_text(result.model_dump_json(indent=2))
    print(f"  Ranked clusters written -> {ranked_path}")
    return result


def run_dry(failures: list) -> Brief:
    """Dry-run enrichment — no LLM call, schema validation only."""
    banner("Dry-Run Enrichment (no LLM call)")
    ranked_path = Path("output/ranked_clusters.json")
    if ranked_path.exists():
        trend_result = TrendResult.model_validate_json(ranked_path.read_text())
        print(f"  Loaded ranked_clusters.json ({len(trend_result.ranked_clusters)} clusters)")
    else:
        print("  No ranked_clusters.json — running M1+M2 first…")
        trend_result = _load_trend_result(fresh=True)
    return enrich_clusters(trend_result, dry_run=True)


def validate_brief(brief: Brief, live: bool, failures: list) -> None:
    """All exit criteria checks — applies to both dry and live runs."""
    banner("Validating Brief Structure")
    events = brief.events

    # 1. Schema roundtrip
    try:
        Brief.model_validate(brief.model_dump())
        check("Brief validates against Brief schema", True)
    except Exception as exc:
        check("Brief validates against Brief schema", False, str(exc))
        failures.append("schema")

    # 2. Event count
    ok = check("1-5 events present", 1 <= len(events) <= 5, f"{len(events)} events")
    if not ok:
        failures.append("event-count")

    # 3. Sorted ascending by rank
    ranks = [e.rank for e in events]
    ok = check("Events sorted ascending by rank", ranks == sorted(ranks), str(ranks))
    if not ok:
        failures.append("rank-order")

    for ev in events:
        prefix = f"Event #{ev.rank}"

        # 4. Required string fields non-empty
        for field in ("event_heading", "summary", "why_it_matters", "signal_source"):
            val = getattr(ev, field, "")
            ok = check(f"{prefix}: '{field}' non-empty", bool(val and val.strip()),
                       f"{len(val)} chars")
            if not ok:
                failures.append(f"field-{field}-#{ev.rank}")

        # 5. Heading word count
        wc = len(ev.event_heading.split())
        ok = check(f"{prefix}: heading <= 20 words", wc <= 20, f"{wc} words")
        if not ok:
            failures.append(f"heading-length-#{ev.rank}")

        # 6+7. Sentence counts — only meaningful on real LLM output
        if live:
            sc = count_sentences(ev.summary)
            ok = check(f"{prefix}: summary 1-3 sentences", 1 <= sc <= 3,
                       f"~{sc} sentences")
            if not ok:
                failures.append(f"summary-length-#{ev.rank}")

            wc2 = count_sentences(ev.why_it_matters)
            ok = check(f"{prefix}: why_it_matters 1-2 sentences", 1 <= wc2 <= 2,
                       f"~{wc2} sentences")
            if not ok:
                failures.append(f"wim-length-#{ev.rank}")
        else:
            print(f"  SKIP  {prefix}: sentence counts (dry-run mock text)")
            print(f"  SKIP  {prefix}: sentence counts (dry-run mock text)")

        # 8. Sector count
        ok = check(f"{prefix}: 1-5 sectors",
                   1 <= len(ev.sectors_impacted) <= 5, f"{len(ev.sectors_impacted)}")
        if not ok:
            failures.append(f"sector-count-#{ev.rank}")

        # 9. Sector names valid
        invalid = [s.name for s in ev.sectors_impacted if s.name not in VALID_SECTORS]
        ok = check(f"{prefix}: all sector names valid", not invalid,
                   f"invalid: {invalid}" if invalid else "all valid")
        if not ok:
            failures.append(f"sector-names-#{ev.rank}")

        # 10. Sector confidences in range
        bad_conf = [s for s in ev.sectors_impacted if not (0.0 <= s.confidence <= 1.0)]
        ok = check(f"{prefix}: sector confidences in [0.0, 1.0]", not bad_conf,
                   f"{len(bad_conf)} out of range" if bad_conf else "all valid")
        if not ok:
            failures.append(f"sector-conf-#{ev.rank}")

        # 11. Sectors sorted desc
        confs = [s.confidence for s in ev.sectors_impacted]
        ok = check(f"{prefix}: sectors sorted desc by confidence",
                   confs == sorted(confs, reverse=True), str(confs))
        if not ok:
            failures.append(f"sector-sort-#{ev.rank}")

        # 12. Source articles present with required fields
        ok = check(f"{prefix}: source_articles non-empty",
                   len(ev.source_articles) >= 1, f"{len(ev.source_articles)}")
        if not ok:
            failures.append(f"articles-#{ev.rank}")

        for art in ev.source_articles:
            has_fields = all([art.title, art.url, art.published_at])
            ok = check(f"{prefix}: article has title+url+date", has_fields,
                       art.title[:40] if art.title else "MISSING")
            if not ok:
                failures.append(f"article-fields-#{ev.rank}")

    # Financial advice guard (live output only)
    if live:
        banner("Financial Advice Guard")
        for ev in events:
            all_text = " ".join([ev.summary, ev.why_it_matters, ev.event_heading]).lower()
            hits = [p for p in FINANCIAL_ADVICE_PHRASES_CHECK if p in all_text]
            ok = check(f"Event #{ev.rank}: no financial advice", not hits,
                       f"phrases found: {hits}" if hits else "clean")
            if not ok:
                failures.append(f"fin-advice-#{ev.rank}")


def main() -> None:
    parser = argparse.ArgumentParser(description="M3 Smoke Test — step4 LLM enrichment")
    parser.add_argument("--live",  action="store_true",
                        help="Real two-pass LLM calls (needs GEMINI_API_KEY in .env)")
    parser.add_argument("--fresh", action="store_true",
                        help="Force re-run of steps 1-3 (slow; default: use cached ranked_clusters.json)")
    args = parser.parse_args()

    start    = time.time()
    failures: list = []

    mode_label = "LIVE" if args.live else "DRY RUN"
    print(f"\n News That Matters — M3 Smoke Test  ({mode_label})")
    if args.live and not args.fresh:
        print("   Skipping steps 1-3 (using cached ranked_clusters.json). Pass --fresh to re-fetch.")

    if args.live:
        banner("Live — Pass 1 (batch sector-tag) + Pass 2 (full enrichment)")
        trend       = _load_trend_result(fresh=args.fresh)
        llm_start   = time.time()
        brief       = enrich_clusters(trend, dry_run=False)
        llm_elapsed = time.time() - llm_start

        out = Path("output/brief.json")
        out.write_text(brief.model_dump_json(indent=2))
        print(f"\n  brief.json written -> {out}")

        n = max(len(brief.events), 1)
        avg_lat = llm_elapsed / n
        ok = check("Avg LLM latency < 15s per event", avg_lat < 15, f"{avg_lat:.1f}s avg")
        if not ok:
            failures.append("latency")

        ok = check("Enrichment step <= 3 minutes", llm_elapsed <= 180, f"{llm_elapsed:.0f}s")
        if not ok:
            failures.append("enrichment-runtime")
    else:
        brief = run_dry(failures)

    validate_brief(brief, live=args.live, failures=failures)

    total = time.time() - start
    banner("Result")
    if failures:
        print(f"  M3 {mode_label} FAILED — {len(failures)} check(s): {failures}\n")
        sys.exit(1)
    else:
        result_label = "LIVE — all exit criteria passed" if args.live else "DRY RUN — schema valid"
        print(f"  M3 {result_label} in {total:.1f}s")
        if args.live and brief.events:
            print(f"      Top event: \"{brief.events[0].event_heading}\"")
            print(f"      Sectors  : {[s.name for s in brief.events[0].sectors_impacted]}")
        if not args.live:
            print(f"\n  Ready for live run: python scripts/test_m3.py --live")


if __name__ == "__main__":
    main()
