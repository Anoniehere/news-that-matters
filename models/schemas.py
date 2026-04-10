"""
Pydantic v2 data models — single source of truth for all pipeline data shapes.
Every step reads/writes these. Never use bare dicts between pipeline steps.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Step 1 output — raw fetched articles
# ---------------------------------------------------------------------------

class Article(BaseModel):
    title: str
    url: str
    source_name: str
    published_at: datetime
    body_snippet: str               # HTML-stripped; may be short for RSS feeds
    feed_name: str                  # which named feed this came from

    def embed_text(self) -> str:
        """Combined text used for embedding — title carries more signal."""
        return f"{self.title}. {self.body_snippet}"


class FetchResult(BaseModel):
    articles: list[Article]
    total_count: int
    feed_counts: dict[str, int]     # {feed_name: article_count}
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Step 2 output — clustered articles
# ---------------------------------------------------------------------------

class Cluster(BaseModel):
    cluster_id: int
    articles: list[Article]         # sorted newest → oldest
    size: int

    @property
    def headline_article(self) -> Article:
        """Most recent article — used as cluster representative."""
        return self.articles[0]


class ClusterResult(BaseModel):
    clusters: list[Cluster]         # sorted by size desc; noise excluded
    singletons: list[Article]       # DBSCAN label == -1 (noise)
    total_articles: int
    total_clusters: int
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Step 3 output — trend-scored clusters (added in M2)
# ---------------------------------------------------------------------------

class ScoredCluster(BaseModel):
    cluster: Cluster
    repetition_score: float         # 0.0–1.0  article-count signal
    social_score: float             # 0.0–1.0  pytrends OR feed-diversity fallback
    trend_score: float              # 0.70*rep + 0.30*social
    rank: Optional[int] = None      # assigned after sorting
    for_llm: bool = False           # True for top-5 clusters passed to M3
    search_term: str = ""           # keyword used for social signal query
    signal_source: str = ""         # "pytrends" | "feed_diversity" | "none"


class TrendResult(BaseModel):
    ranked_clusters: list[ScoredCluster]   # top 7, sorted desc by trend_score
    generated_at: datetime = Field(default_factory=datetime.utcnow)
