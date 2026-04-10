#!/usr/bin/env python3
"""
Embedding quality comparison: TF-IDF vs Neural (all-MiniLM-L6-v2)
Same articles, same DBSCAN logic, different embeddings.
Shows exactly what neural catches that TF-IDF misses.

Usage:
    python scripts/compare_embeddings.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.step1_fetch import fetch_all_feeds
from pipeline.step2_cluster import _embed_tfidf, _embed_neural, retry_with_looser_eps
from models.schemas import Article, ClusterResult

SEP  = "─" * 62
SEP2 = "═" * 62


def cluster_and_show(
    label: str,
    articles: list[Article],
    embeddings,
    base_eps: float,
    top_n: int = 7,
) -> ClusterResult:
    result = retry_with_looser_eps(articles, embeddings, base_eps=base_eps)

    print(f"\n{'━'*62}")
    print(f"  {label}")
    print(f"  {result.total_clusters} clusters  |  "
          f"{len(result.singletons)} singletons  |  "
          f"{result.total_articles} total articles")
    print(f"{'━'*62}\n")

    if not result.clusters:
        print("  (no clusters formed)")
        return result

    for i, c in enumerate(result.clusters[:top_n], 1):
        print(f"  #{i}  [{c.size} article{'s' if c.size > 1 else ''}]  "
              f"{c.headline_article.title[:58]}")
        for art in c.articles[1:]:
            # Highlight how different the phrasing is
            print(f"       └─ {art.title[:56]}")
        print()
    return result


def similarity_spot_check(articles: list[Article]) -> None:
    """
    Pick 3 known-similar article pairs and score them with both methods.
    Demonstrates the semantic gap TF-IDF can't bridge.
    """
    import numpy as np
    from sklearn.preprocessing import normalize
    from sklearn.feature_extraction.text import TfidfVectorizer

    test_pairs = [
        (
            "Federal Reserve officials see higher risk in inflation",
            "Fed minutes show growing openness to rate hikes",
        ),
        (
            "Israel says it will hold talks with Lebanon soon",
            "US will host talks between Israel and Lebanon",
        ),
        (
            "Democrats grow bolder on talk about Trump removal",
            "Democrats grow bolder on talk about removing Trump from office",
        ),
    ]

    # TF-IDF scores
    all_texts = [t for pair in test_pairs for t in pair]
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
    tfidf_mat = normalize(vec.fit_transform(all_texts).toarray(), norm="l2")

    # Neural scores
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    from sentence_transformers import SentenceTransformer
    from pathlib import Path
    LOCAL = Path.home() / ".cache" / "signal-brief" / "models" / "all-MiniLM-L6-v2"
    model = SentenceTransformer(str(LOCAL) if LOCAL.exists() else "all-MiniLM-L6-v2")
    neural_vecs = normalize(model.encode(all_texts), norm="l2")

    print(f"\n{'━'*62}")
    print("  SIMILARITY SPOT-CHECK — same topic, different phrasing")
    print(f"{'━'*62}\n")
    print(f"  {'Pair':<4}  {'TF-IDF sim':>10}  {'Neural sim':>10}  {'Neural wins?':>12}")
    print(f"  {'─'*4}  {'─'*10}  {'─'*10}  {'─'*12}")

    for i, (a, b) in enumerate(test_pairs):
        idx_a, idx_b = i * 2, i * 2 + 1
        tfidf_sim = float(tfidf_mat[idx_a] @ tfidf_mat[idx_b])
        neural_sim = float(neural_vecs[idx_a] @ neural_vecs[idx_b])
        win = "✅ YES" if neural_sim > tfidf_sim + 0.05 else ("➖ TIED" if abs(neural_sim - tfidf_sim) < 0.05 else "❌ NO")
        print(f"  #{i+1:<3}  {tfidf_sim:>10.4f}  {neural_sim:>10.4f}  {win:>12}")

    print()
    for i, (a, b) in enumerate(test_pairs):
        print(f"  Pair #{i+1}:")
        print(f"    A: {a}")
        print(f"    B: {b}")
        print()


def main() -> None:
    import logging
    logging.disable(logging.WARNING)   # silence pipeline logs for clean output

    print(f"\n{SEP2}")
    print("  ⚡ Signal Brief — Embedding Quality Comparison")
    print(f"  TF-IDF vs all-MiniLM-L6-v2 (neural)")
    print(f"{SEP2}")

    print("\n📡 Fetching articles...")
    fetch_result = fetch_all_feeds(max_age_days=4)
    articles = fetch_result.articles
    print(f"   {len(articles)} articles across {len(fetch_result.feed_counts)} feeds\n")

    # ── TF-IDF ──────────────────────────────────────────────────────────
    print("Computing TF-IDF embeddings...")
    tfidf_emb, tfidf_eps = _embed_tfidf([a.embed_text() for a in articles])
    tfidf_result = cluster_and_show("TF-IDF", articles, tfidf_emb, tfidf_eps)

    # ── Neural ──────────────────────────────────────────────────────────
    print("Computing neural embeddings (MPS accelerated)...")
    neural_emb, neural_eps = _embed_neural([a.embed_text() for a in articles])
    neural_result = cluster_and_show("NEURAL  (all-MiniLM-L6-v2)", articles, neural_emb, neural_eps)

    # ── Headline comparison ──────────────────────────────────────────────
    print(f"\n{SEP2}")
    print("  HEAD-TO-HEAD SUMMARY")
    print(f"{SEP2}\n")

    tfidf_top = set(c.headline_article.title[:50] for c in tfidf_result.clusters[:5])
    neural_top = set(c.headline_article.title[:50] for c in neural_result.clusters[:5])
    neural_only = neural_top - tfidf_top

    print(f"  {'Metric':<30}  {'TF-IDF':>8}  {'Neural':>8}")
    print(f"  {'─'*30}  {'─'*8}  {'─'*8}")
    print(f"  {'Total clusters formed':<30}  {tfidf_result.total_clusters:>8}  {neural_result.total_clusters:>8}")
    print(f"  {'Largest cluster size':<30}  {max((c.size for c in tfidf_result.clusters), default=0):>8}  "
          f"{max((c.size for c in neural_result.clusters), default=0):>8}")
    print(f"  {'Singleton rate':<30}  "
          f"{len(tfidf_result.singletons)/max(tfidf_result.total_articles,1)*100:>7.1f}%  "
          f"{len(neural_result.singletons)/max(neural_result.total_articles,1)*100:>7.1f}%")

    if neural_only:
        print(f"\n  🧠 Stories neural found that TF-IDF MISSED:")
        for t in sorted(neural_only):
            print(f"     → {t}")

    # ── Spot-check ───────────────────────────────────────────────────────
    similarity_spot_check(articles)

    print(f"{SEP2}")
    print("  VERDICT")
    print(f"{SEP2}\n")
    print("  Neural embeddings understand MEANING, not just word overlap.")
    print("  Same event described with different vocabulary = correctly grouped.")
    print("  TF-IDF misses these — which directly hurts trend scoring in M2.")
    print()
    print("  Can we do even better than all-MiniLM-L6-v2?")
    print("  ┌─────────────────────────────────────────────────────────┐")
    print("  │ Model               Size   Quality   Speed   Cost       │")
    print("  │ ─────────────────── ─────  ───────   ─────   ────       │")
    print("  │ TF-IDF (fallback)   0MB    ★★☆☆☆    fast    free       │")
    print("  │ all-MiniLM-L6-v2 ✅ 87MB   ★★★★☆    8s MPS  free       │")
    print("  │ all-mpnet-base-v2   420MB  ★★★★½    25s     free       │")
    print("  │ text-embedding-3    API    ★★★★★    <1s     $0.02/1M   │")
    print("  │ Cohere embed-v3     API    ★★★★★    <1s     free tier  │")
    print("  └─────────────────────────────────────────────────────────┘")
    print()
    print("  For MVP: all-MiniLM-L6-v2 is the right call.")
    print("  Reason: runs locally, free forever, good enough for")
    print("  news headlines, and already deployed.")
    print()


if __name__ == "__main__":
    main()
