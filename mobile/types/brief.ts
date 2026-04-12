/**
 * types/brief.ts — TypeScript types mirroring the FastAPI /brief response.
 * Keep in sync with models/schemas.py — they are the same shape.
 */

export interface SourceArticle {
  title: string;
  url: string;
  source_name: string;
  published_at: string;   // ISO datetime string
  body_snippet: string;
  feed_name: string;
}

export interface SectorImpact {
  name: string;
  confidence: number;     // 0.0–1.0
}

export interface EnrichedEvent {
  rank: number;
  trend_score: number;
  trend_insight: string;   // why the score is this number — computed from real metrics
  event_heading: string;
  summary: string;
  why_it_matters: string;
  sectors_impacted: SectorImpact[];
  timeline_context: string;
  source_articles: SourceArticle[];
  signal_source: string;
  enriched_at: string;
}

export interface Brief {
  events: EnrichedEvent[];
  generated_at: string;
  pipeline_version: string;
  is_stale: boolean;
}

export interface BriefMeta {
  pipeline_duration_s: number;
  created_at: string;
  is_stale: boolean;
  age_minutes: number;
}

export interface BriefResponse {
  brief: Brief;
  meta: BriefMeta;
}
