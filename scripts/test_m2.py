#!/usr/bin/env python3
"""
M2 Smoke Test — Trend Scoring
Runs the full M1+M2 pipeline and validates all M2 exit criteria.

Exit criteria:
  ✅ pipeline/step3_score.py produces ranked_clusters.json
  ✅ Every cluster has trend_score in [0.0, 1.0]
  ✅ Clusters sorted descending by trend_score
  ✅ top-5 have for_llm=True; positions 6-7 have for_llm=False
  ✅ Each cluster has search_term (non-empty) and signal_source
  ✅ Scores reproducible within ±0.05 on re-run (rep score deterministic)
  ✅ Runtime ≤ 90 seconds total (M1 + M2)
  ✅ ranked_clusters.json validates against TrendResult schema

Usage:
    python scripts/test_m2.py
"""
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.step1_fetch import fetch_all_feeds
from pipeline.step2_cluster import embed_articles, cluster_articles, retry_with_looser_eps
from pipeline.step3_score import score_clusters
from models.schemas import ClusterResult, TrendResult

SEP = "─" * 55

def banner(msg: str) -> None:
    print(f"\n{SEP}\n{msg}\n{SEP}")


def check(label: str, passed: bool, detail: str = "") -> bool:
    icon = "✅ PASS" if passed else "❌ FAIL"
    line = f"  {icon}  {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return passed


def main() -> None:
    start = time.time()
    failures: list[str] = []

    print(f"\n⚡ Signal Brief — M2 Smoke Test")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── M1: Fetch ────────────────────────────────────────────────────────
    banner("📡 Step 1: RSS Fetch")
    fetch_result = fetch_all_feeds(max_age_days=4)
    articles = fetch_result.articles

    ok = check("≥ 20 articles fetched", len(articles) >= 20, f"{len(articles)} fetched")
    if not ok: failures.append("fetch")

    # ── M1: Cluster ──────────────────────────────────────────────────────
    banner("🧩 Step 2: Cluster")
    embeddings, base_eps = embed_articles(articles)
    cluster_result = retry_with_looser_eps(articles, embeddings, base_eps=base_eps)

    ok = check("≥ 3 clusters formed", cluster_result.total_clusters >= 3,
               f"{cluster_result.total_clusters} clusters")
    if not ok: failures.append("clustering")

    # ── M2: Score ────────────────────────────────────────────────────────
    banner("📊 Step 3: Trend Scoring")

    score_start = time.time()
    trend_result = score_clusters(cluster_result)
    score_elapsed = time.time() - score_start

    ranked = trend_result.ranked_clusters
    print(f"\n   Ranked clusters : {len(ranked)}")
    print(f"   Scoring time    : {score_elapsed:.1f}s")
    print()

    for sc in ranked:
        flag = "→ LLM" if sc.for_llm else "      "
        print(f"  #{sc.rank} {flag}  trend={sc.trend_score:.3f}  "
              f"rep={sc.repetition_score:.3f}  soc={sc.social_score:.3f}  "
              f"[{sc.signal_source}]")
        print(f"      {sc.cluster.headline_article.title[:60]}")
        print(f"      search_term: \"{sc.search_term}\"")
        print()

    print(SEP)

    # ── Validate exit criteria ───────────────────────────────────────────
    banner("🔍 Exit Criteria Validation")

    # 1. At least 1 scored cluster
    ok = check("≥ 1 cluster scored", len(ranked) >= 1, f"{len(ranked)} scored")
    if not ok: failures.append("no-scored-clusters")

    # 2. All trend_scores in [0.0, 1.0]
    bad_scores = [sc for sc in ranked if not (0.0 <= sc.trend_score <= 1.0)]
    ok = check("All trend_scores in [0.0, 1.0]", len(bad_scores) == 0,
               f"{len(bad_scores)} out of range" if bad_scores else "all valid")
    if not ok: failures.append("score-range")

    # 3. Sorted descending
    scores = [sc.trend_score for sc in ranked]
    ok = check("Clusters sorted desc by trend_score", scores == sorted(scores, reverse=True),
               str(scores))
    if not ok: failures.append("sort-order")

    # 4. for_llm flags correct
    llm_flagged   = [sc for sc in ranked if sc.for_llm]
    llm_unflagged = [sc for sc in ranked if not sc.for_llm and sc.rank is not None]
    expected_llm  = min(5, len(ranked))
    ok = check(f"Top {expected_llm} have for_llm=True",
               len(llm_flagged) == expected_llm and all(sc.rank <= 5 for sc in llm_flagged),
               f"{len(llm_flagged)} flagged")
    if not ok: failures.append("for_llm-flags")

    # 5. search_term non-empty
    empty_terms = [sc for sc in ranked if not sc.search_term.strip()]
    ok = check("All clusters have non-empty search_term", len(empty_terms) == 0,
               f"{len(empty_terms)} empty" if empty_terms else "all present")
    if not ok: failures.append("search-term")

    # 6. signal_source set
    bad_src = [sc for sc in ranked if sc.signal_source not in ("pytrends", "feed_diversity")]
    ok = check("All clusters have valid signal_source", len(bad_src) == 0,
               f"sources: {set(sc.signal_source for sc in ranked)}")
    if not ok: failures.append("signal-source")

    # 7. Ranks assigned and sequential
    ranks = [sc.rank for sc in ranked]
    ok = check("Ranks assigned 1…N sequentially", ranks == list(range(1, len(ranked)+1)),
               str(ranks))
    if not ok: failures.append("ranks")

    # 8. Schema validates
    OUTPUT_PATH = Path("output/ranked_clusters.json")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(trend_result.model_dump_json(indent=2))
    try:
        TrendResult.model_validate_json(OUTPUT_PATH.read_text())
        ok = check("ranked_clusters.json validates against TrendResult schema", True,
                   str(OUTPUT_PATH))
    except Exception as e:
        ok = check("ranked_clusters.json validates against TrendResult schema", False, str(e))
        failures.append("schema")

    # 9. Runtime
    total_elapsed = time.time() - start
    ok = check("Total runtime ≤ 90 seconds", total_elapsed <= 90,
               f"{total_elapsed:.1f}s elapsed")
    if not ok: failures.append("runtime")

    # 10. Repetition score reproducibility (deterministic — run again, compare)
    print("\n   Checking repetition score reproducibility (2nd run)…")
    result2 = score_clusters(cluster_result)
    rep_diffs = [
        abs(a.repetition_score - b.repetition_score)
        for a, b in zip(ranked, result2.ranked_clusters)
    ]
    max_diff = max(rep_diffs) if rep_diffs else 0.0
    ok = check("rep scores reproducible within ±0.05", max_diff <= 0.05,
               f"max diff={max_diff:.4f}")
    if not ok: failures.append("reproducibility")

    # ── Final verdict ────────────────────────────────────────────────────
    banner("🏁 Result")
    if failures:
        print(f"  ❌  M2 FAILED — {len(failures)} check(s) failed: {failures}\n")
        sys.exit(1)
    else:
        print(f"  🎉  M2 COMPLETE — all exit criteria passed in {total_elapsed:.1f}s")
        print(f"      Signal source: {set(sc.signal_source for sc in ranked)}")
        print(f"      Top event: #{ranked[0].rank} — {ranked[0].cluster.headline_article.title[:55]}")
        print(f"      → Ready to start M3 (LLM enrichment)\n")


if __name__ == "__main__":
    main()
