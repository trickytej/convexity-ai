export const API_BASE = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export interface Show {
  slug: string;
  name: string;
  network?: string | null;
  homepage?: string | null;
  hosts: string[];
  tier: string;
  active: boolean;
  total: number;
  transcribed: number;
}

export interface Episode {
  id: number;
  show_slug: string;
  title: string;
  published_at?: string | null;
  duration_seconds?: number | null;
  guests?: string[] | null;
  episode_url?: string | null;
  audio_url?: string | null;
  source?: string | null;
  provider?: string | null;
  word_count?: number | null;
  nugget_count: number;
}

export interface EpisodeList {
  total: number;
  limit: number;
  offset: number;
  episodes: Episode[];
}

export interface Segment {
  idx: number;
  speaker_name?: string | null;
  speaker_label?: string | null;
  start_ms?: number | null;
  end_ms?: number | null;
  text: string;
}

export interface Transcript {
  episode: Episode;
  source: string;
  provider: string;
  has_diarization: boolean;
  corrected: boolean;
  word_count?: number | null;
  speakers: string[];
  segments: Segment[];
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${res.status} for ${path}`);
  }
  return (await res.json()) as T;
}

export function getShows(): Promise<Show[]> {
  return getJSON<Show[]>("/api/shows");
}

export function getEpisodes(
  params: { show?: string; days?: number; limit?: number; offset?: number } = {},
): Promise<EpisodeList> {
  const q = new URLSearchParams();
  if (params.show) q.set("show", params.show);
  if (params.days) q.set("days", String(params.days));
  q.set("limit", String(params.limit ?? 50));
  q.set("offset", String(params.offset ?? 0));
  return getJSON<EpisodeList>(`/api/episodes?${q.toString()}`);
}

export function getTranscript(id: number | string): Promise<Transcript> {
  return getJSON<Transcript>(`/api/episodes/${id}/transcript`);
}

export interface ReportNugget {
  id: number;
  episode_id: number;
  show_slug: string;
  episode_title: string;
  published_at?: string | null;
  type: string;
  claim: string;
  quote?: string | null;
  speaker_name?: string | null;
  start_ms?: number | null;
  signal_score: number;
  quote_verified: boolean;
  triage: string;
  sectors: string[];
  companies: string[];
  corroboration_shows: number;
}

export type TriageValue = "pending" | "relevant" | "not_relevant";

export interface ReportSection {
  sector: string;
  count: number;
  nuggets: ReportNugget[];
}

export interface EntityBuzz {
  name: string;
  shows: string[];
  nugget_count: number;
}

export interface WeeklyReport {
  since?: string | null;
  until: string;
  days: number;
  stats: {
    nuggets: number;
    window_nuggets?: number;
    episodes: number;
    shows: number;
    verified: number;
    by_type: Record<string, number>;
    triage?: Record<string, number>;
  };
  sections: ReportSection[];
  top_entities: EntityBuzz[];
}

export function getInsights(
  days = 7,
  perSectionLimit?: number,
  triage?: string,
): Promise<WeeklyReport> {
  const q = new URLSearchParams({ days: String(days) });
  if (perSectionLimit) q.set("per_section_limit", String(perSectionLimit));
  if (triage) q.set("triage", triage);
  return getJSON<WeeklyReport>(`/api/insights?${q.toString()}`);
}

// --- Step 6: the synthesized weekly report ---

export interface ReportSource {
  nugget_id: number;
  episode_id: number;
  show_slug: string;
  start_ms?: number | null;
  speaker_name?: string | null;
}

export interface ReportBullet {
  text: string;
  sources: ReportSource[];
}

export interface GeneratedSection {
  sector: string;
  count: number;
  headline: string;
  bullets: ReportBullet[];
  watch_items: string[];
}

export interface GeneratedReport {
  week_key: string;
  since?: string | null;
  until: string;
  days: number;
  generated_at: string;
  source_mode: string;
  exec_summary: string;
  sections: GeneratedSection[];
  top_entities: EntityBuzz[];
  stats: Record<string, unknown>;
}

export function getLatestReport(): Promise<GeneratedReport | null> {
  return getJSON<GeneratedReport | null>("/api/report/latest");
}

export async function generateReport(days = 7): Promise<GeneratedReport> {
  const res = await fetch(`${API_BASE}/api/report/generate?days=${days}`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`report generation failed: ${res.status}`);
  }
  return (await res.json()) as GeneratedReport;
}

export async function setTriage(id: number, triage: TriageValue): Promise<void> {
  const res = await fetch(`${API_BASE}/api/nuggets/${id}/triage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ triage }),
  });
  if (!res.ok) {
    throw new Error(`triage failed: ${res.status}`);
  }
}
