"""
Step 2: Cluster articles by semantic similarity.

Embedding strategy — two-tier with automatic fallback:
  1. sentence-transformers all-MiniLM-L6-v2 (neural, best quality)
     → requires huggingface.co to be reachable OR model cached locally
  2. TF-IDF vectorizer (scikit-learn, zero downloads, always works)
     → fallback when neural model is unavailable

For news clustering, TF-IDF is surprisingly effective because same-event
articles share proper nouns (names, tickers, legislation) — exact vocabulary
overlap IS the signal. See ADR-013 in DECISIONS.md.

Usage:
    python -m pipeline.step2_cluster
    python pipeline/step2_cluster.py
"""
import logging
import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from models.schemas import Article, Cluster, ClusterResult, FetchResult

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

EMBED_MODEL        = "all-MiniLM-L6-v2"
EMBED_MODEL_LOCAL  = Path.home() / ".cache" / "signal-brief" / "models" / "all-MiniLM-L6-v2"
EPS_NEURAL    = 0.65   # starting threshold for neural embeddings on RSS snippets
                       # math: eps=0.65 → cosine_sim > 0.79 on L2-norm vectors
                       # (short RSS titles need looser threshold than full-doc models)
EPS_TFIDF     = 1.00   # TF-IDF on L2-norm: eps=1.0 → cosine_sim > 0.5
                       # math: eps = sqrt(2*(1-cos_sim)) on unit vectors
MIN_SAMPLES   = 2


# ---------------------------------------------------------------------------
# Embedding — two-tier with fallback
# ---------------------------------------------------------------------------

def _embed_neural(texts: list[str]) -> tuple[np.ndarray, float]:
    """
    Return L2-normalised neural embeddings + recommended eps.

    Model resolution order:
      1. Local cache at ~/.cache/signal-brief/models/all-MiniLM-L6-v2
         (assembled by scripts/download_model.py — works on Walmart network)
      2. HuggingFace Hub download (works on open internet / production)
    """
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context

    from sentence_transformers import SentenceTransformer

    if EMBED_MODEL_LOCAL.exists() and (EMBED_MODEL_LOCAL / "model.safetensors").exists():
        model_path = str(EMBED_MODEL_LOCAL)
        log.info("Step 2: Loading neural model from local cache: %s", model_path)
    else:
        model_path = EMBED_MODEL
        log.info("Step 2: Loading neural model from HuggingFace Hub: %s", model_path)

    model = SentenceTransformer(model_path)
    emb = model.encode(texts, batch_size=32, show_progress_bar=False)
    return normalize(emb, norm="l2"), EPS_NEURAL


def _embed_tfidf(texts: list[str]) -> tuple[np.ndarray, float]:
    """Return L2-normalised TF-IDF vectors + recommended eps."""
    vec = TfidfVectorizer(
        max_features=8000,
        stop_words="english",
        ngram_range=(1, 2),   # bigrams capture "Federal Reserve", "Silicon Valley" etc.
        min_df=1,
        sublinear_tf=True,    # log(tf) dampens high-frequency terms
    )
    matrix = vec.fit_transform(texts).toarray()
    return normalize(matrix, norm="l2"), EPS_TFIDF


def embed_articles(articles: list[Article]) -> tuple[np.ndarray, float]:
    """
    Try neural embeddings first; fall back to TF-IDF if model unavailable.
    Returns (embeddings, recommended_eps).
    """
    texts = [a.embed_text() for a in articles]

    log.info("Step 2: Attempting neural embeddings (%s)…", EMBED_MODEL)
    try:
        emb, eps = _embed_neural(texts)
        log.info("Step 2: Neural embeddings OK — shape %s, eps=%.2f", emb.shape, eps)
        return emb, eps
    except Exception as exc:
        log.warning("Step 2: Neural embedding failed (%s). Falling back to TF-IDF.", exc)

    emb, eps = _embed_tfidf(texts)
    log.info("Step 2: TF-IDF embeddings — shape %s, eps=%.2f", emb.shape, eps)
    return emb, eps


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def cluster_articles(
    articles: list[Article],
    embeddings: np.ndarray,
    eps: float,
) -> ClusterResult:
    """
    DBSCAN on L2-normalised vectors. Euclidean distance on unit vectors
    equals cosine distance — no brute-force cosine overhead needed.
    """
    if len(articles) < 2:
        log.warning("Step 2: Too few articles (%d) to cluster.", len(articles))
        return ClusterResult(
            clusters=[], singletons=articles,
            total_articles=len(articles), total_clusters=0,
        )

    db = DBSCAN(eps=eps, min_samples=MIN_SAMPLES, metric="euclidean", n_jobs=-1)
    labels: np.ndarray = db.fit_predict(embeddings)

    unique_labels = set(labels)
    noise_count   = int(np.sum(labels == -1))
    log.info(
        "Step 2: DBSCAN → %d clusters, %d singletons (eps=%.2f, min_samples=%d)",
        len(unique_labels - {-1}), noise_count, eps, MIN_SAMPLES,
    )

    cluster_map: dict[int, list[Article]] = {}
    singletons: list[Article] = []
    for article, label in zip(articles, labels.tolist()):
        if label == -1:
            singletons.append(article)
        else:
            cluster_map.setdefault(int(label), []).append(article)

    clusters: list[Cluster] = []
    for cid, arts in cluster_map.items():
        sorted_arts = sorted(arts, key=lambda a: a.published_at, reverse=True)
        clusters.append(Cluster(cluster_id=cid, articles=sorted_arts, size=len(sorted_arts)))

    clusters.sort(key=lambda c: c.size, reverse=True)

    for i, c in enumerate(clusters[:5], 1):
        log.info("  #%d [%d articles] %s", i, c.size, c.headline_article.title[:70])

    return ClusterResult(
        clusters=clusters,
        singletons=singletons,
        total_articles=len(articles),
        total_clusters=len(clusters),
    )


def retry_with_looser_eps(
    articles: list[Article],
    embeddings: np.ndarray,
    base_eps: float,
) -> ClusterResult:
    """If 0 clusters, retry with progressively looser eps (up to 2× base)."""
    for eps in [base_eps, base_eps * 1.2, base_eps * 1.5, base_eps * 2.0]:
        result = cluster_articles(articles, embeddings, eps=eps)
        if result.total_clusters >= 1:
            return result
        log.warning("Step 2: 0 clusters at eps=%.2f — retrying looser…", eps)

    log.error("Step 2: Could not form any clusters. News may be extremely diverse.")
    return cluster_articles(articles, embeddings, eps=base_eps * 2.0)


def load_articles(path: Path) -> list[Article]:
    if not path.exists():
        log.error("Step 2: %s not found — run step1 first", path)
        sys.exit(1)
    result = FetchResult.model_validate_json(path.read_text())
    log.info("Step 2: Loaded %d articles from %s", len(result.articles), path)
    return result.articles


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    articles_path = Path("output/articles.json")
    output_path   = Path("output/clusters.json")

    articles = load_articles(articles_path)
    embeddings, recommended_eps = embed_articles(articles)
    result = retry_with_looser_eps(articles, embeddings, base_eps=recommended_eps)

    output_path.write_text(result.model_dump_json(indent=2))
    log.info(
        "Step 2: Saved %d clusters + %d singletons → %s",
        result.total_clusters, len(result.singletons), output_path,
    )


if __name__ == "__main__":
    main()
