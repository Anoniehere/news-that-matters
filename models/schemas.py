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
    repetition_score: float         # 0.0–1.0  log-normalised article count
    trend_score: float              # step3: =rep_score; step4 overwrites with rep+persona
    trend_insight: str = ""         # human-readable breakdown of how the score was computed
    rank: Optional[int] = None      # assigned after sorting
    for_llm: bool = False           # True for all candidates passed to step 4
    signal_source: str = ""         # "reputation" (step3) → "persona" (step4)


class TrendResult(BaseModel):
    ranked_clusters: list[ScoredCluster]   # top 15, sorted desc by rep_score
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Step 4 output — LLM-enriched events (M3)
# ---------------------------------------------------------------------------

class SectorImpact(BaseModel):
    name: str                              # e.g. "Technology", "Finance"
    confidence: float = Field(ge=0.0, le=1.0)


class EnrichedEvent(BaseModel):
    rank: int                              # inherited from ScoredCluster.rank
    trend_score: float
    trend_insight: str                     # why the score is this number (computed, not LLM)
    event_heading: str                     # ≤ 15 words — the thesis sentence
    summary: str                           # 2 sentences max (~35 words): who, what, key consequence
    why_it_matters: str                    # 1 sentence (~20 words): one concrete SV-professional implication
    sectors_impacted: list[SectorImpact]   # 1–5 items, sorted desc by confidence
    source_articles: list[Article]         # raw cluster articles, newest first (UI caps at 3)
    signal_source: str                     # inherited from ScoredCluster.signal_source
    enriched_at: datetime = Field(default_factory=datetime.utcnow)


class Brief(BaseModel):
    events: list[EnrichedEvent]            # 1–5 events, rank-sorted
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    pipeline_version: str = "1.0"
    is_stale: bool = False                 # M4 sets True if pipeline is overdue
