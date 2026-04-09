#!/usr/bin/env python3
"""
M1 Smoke Test — validates exit criteria for RSS Fetch + Clustering.

Exit criteria (all must pass):
  ✓ ≥ 20 articles fetched across feeds
  ✓ ≥ 3 distinct clusters produced
  ✓ All articles have published_at within last 4 days
  ✓ output/clusters.json validates against ClusterResult schema
  ✓ Runtime ≤ 60 seconds

Usage:
    python scripts/test_m1.py
"""
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure project root is on path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.step1_fetch import fetch_all_feeds
from pipeline.step2_cluster import embed_articles, retry_with_looser_eps
from models.schemas import ClusterResult, FetchResult

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SEP  = "─" * 55


def check(label: str, condition: bool, detail: str = "") -> bool:
    icon = PASS if condition else FAIL
    line = f"  {icon}  {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    return condition


def main() -> None:
    print(f"\n⚡ Signal Brief — M1 Smoke Test")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(SEP)

    start = time.time()

    # ── Step 1: Fetch ──────────────────────────────────────────────────────
    print("\n📡 Step 1: RSS Fetch\n")
    fetch_result: FetchResult = fetch_all_feeds(max_age_days=4)

    for feed_name, count in fetch_result.feed_counts.items():
        print(f"   {feed_name:<25} {count:>3} articles")

    print()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=4)
    stale = [a for a in fetch_result.articles if a.published_at < cutoff]

    c1 = check("≥ 20 articles fetched", fetch_result.total_count >= 20,
               f"{fetch_result.total_count} fetched")
    c2 = check("All articles within 4 days", len(stale) == 0,
               f"{len(stale)} stale articles found")
    c3 = check("All articles have titles",
               all(bool(a.title) for a in fetch_result.articles))

    # Save step 1 output
    out1 = Path("output/articles.json")
    out1.parent.mkdir(exist_ok=True)
    out1.write_text(fetch_result.model_dump_json(indent=2))
    print(f"\n   💾 Saved → {out1}")

    # ── Step 2: Cluster ────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("\n🧩 Step 2: Embedding + Clustering\n")

    embeddings, recommended_eps = embed_articles(fetch_result.articles)
    cluster_result = retry_with_looser_eps(fetch_result.articles, embeddings, base_eps=recommended_eps)

    print(f"\n   Clusters found:    {cluster_result.total_clusters}")
    print(f"   Singleton articles: {len(cluster_result.singletons)}")
    print(f"   Total articles:    {cluster_result.total_articles}")

    if cluster_result.clusters:
        print("\n   Top clusters by size:")
        for i, c in enumerate(cluster_result.clusters[:5], 1):
            print(f"   {i}. [{c.size} articles] {c.headline_article.title[:60]}")
            for art in c.articles[1:]:
                print(f"            └─ {art.title[:55]}")

    c4 = check("≥ 3 clusters produced", cluster_result.total_clusters >= 3,
               f"{cluster_result.total_clusters} clusters")

    # Save step 2 output
    out2 = Path("output/clusters.json")
    out2.write_text(cluster_result.model_dump_json(indent=2))
    print(f"\n   💾 Saved → {out2}")

    # ── Schema validation ──────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("\n🔍 Schema Validation\n")

    try:
        ClusterResult.model_validate_json(out2.read_text())
        c5 = check("clusters.json validates against ClusterResult schema", True)
    except Exception as exc:
        c5 = check("clusters.json validates against ClusterResult schema", False, str(exc))

    # ── Runtime check ──────────────────────────────────────────────────────
    elapsed = time.time() - start
    c6 = check(f"Runtime ≤ 60 seconds", elapsed <= 60, f"{elapsed:.1f}s elapsed")

    # ── Summary ────────────────────────────────────────────────────────────
    all_passed = all([c1, c2, c3, c4, c5, c6])
    print(f"\n{SEP}")
    if all_passed:
        print(f"\n🎉  M1 COMPLETE — all exit criteria passed in {elapsed:.1f}s")
        print(f"    → Ready to start M2 (trend scoring)\n")
    else:
        print(f"\n⚠️   M1 INCOMPLETE — some criteria failed (see above)")
        print(f"    → Fix failures before moving to M2\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
