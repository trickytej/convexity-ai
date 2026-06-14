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

// --- per-episode digest (TMTB-style) ---

export interface DigestSource {
  nugget_id: number;
  episode_id: number;
  start_ms?: number | null;
  speaker_name?: string | null;
}

export interface DigestPoint {
  text: string;
  quote?: string | null;
  sources: DigestSource[];
}

export interface DigestTheme {
  headline: string;
  takeaway: string;
  points: DigestPoint[];
}

export interface DigestStock {
  company: string;
  stance: string;
  summary: string;
  sources: DigestSource[];
}

export interface EpisodeDigest {
  episode_id: number;
  title: string;
  show_slug: string;
  nugget_count: number;
  generated_at?: string;
  themes: DigestTheme[];
  stocks: DigestStock[];
}

export function getEpisodeDigest(id: number | string): Promise<EpisodeDigest | null> {
  return getJSON<EpisodeDigest | null>(`/api/episodes/${id}/digest`);
}

export async function generateEpisodeDigest(id: number | string): Promise<EpisodeDigest> {
  const res = await fetch(`${API_BASE}/api/episodes/${id}/digest`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`digest generation failed: ${res.status}`);
  }
  return (await res.json()) as EpisodeDigest;
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

// --- Layer 2: curation ---------------------------------------------------

export interface Curation {
  decision: "unreviewed" | "kept" | "killed";
  curator_rank: 1 | 2 | 3 | null;
  contradicts_consensus: boolean;
  note: string | null;
  updated_at: string | null;
}

export interface NuggetWithCuration {
  id: number;
  episode_id: number;
  type: string;
  claim: string;
  quote: string | null;
  speaker_name: string | null;
  start_ms: number | null;
  end_ms: number | null;
  entities: { companies?: string[]; people?: string[]; tickers?: string[] } | null;
  sectors: string[];
  primary_sector: string | null;
  scores: Record<string, number> | null;
  signal_score: number;
  quote_verified: boolean;
  triage: string;
  suggested_rank: 1 | 2 | 3;
  curation: Curation;
}

export interface CurationStats {
  total: number;
  reviewed: number;
  kept: number;
  killed: number;
}

export interface CurationPatch {
  decision?: "unreviewed" | "kept" | "killed";
  curator_rank?: 1 | 2 | 3 | null;
  contradicts_consensus?: boolean;
  note?: string;
}

export function getEpisodeNuggets(id: number | string): Promise<NuggetWithCuration[]> {
  return getJSON<NuggetWithCuration[]>(`/api/episodes/${id}/nuggets`);
}

export function getNuggetCurationStats(id: number | string): Promise<CurationStats> {
  return getJSON<CurationStats>(`/api/episodes/${id}/nuggets/stats`);
}

export async function patchCuration(nuggetId: number, patch: CurationPatch): Promise<Curation> {
  const res = await fetch(`${API_BASE}/api/nuggets/${nuggetId}/curation`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) throw new Error(`curation patch failed: ${res.status}`);
  return (await res.json()) as Curation;
}

// --- Layer 2: newsletter -------------------------------------------------

export interface NewsletterNugget {
  id: number;
  episode_id: number;
  show_slug: string;
  episode_title: string;
  episode_published_at: string | null;
  type: string;
  claim: string;
  quote: string | null;
  speaker_name: string | null;
  start_ms: number | null;
  sectors: string[];
  primary_sector: string | null;
  tickers: string[];
  curator_rank: 1 | 2 | 3 | null;
  contradicts_consensus: boolean;
  curation_note: string | null;
}

export interface StockMention {
  company: string;
  tickers: string[];
  mention_count: number;
  nugget_ids: number[];
  stance: string;
  summary: string;
  source_episode_id: number | null;
  source_start_ms: number | null;
}

export interface Newsletter {
  from_date: string | null;
  to_date: string | null;
  episode_count: number;
  kept_count: number;
  lead: NewsletterNugget[];
  good_to_know: NewsletterNugget[];
  stock_readthrough: StockMention[];
  markdown: string;
}

export interface ImportResult {
  slug: string;
  name: string;
  episode_count: number;
  created: boolean;
}

export interface ImportEpisodeResult {
  episode_id: number;
  title: string;
  show_slug: string;
  created: boolean;
}

export async function importEpisode(url: string, title?: string): Promise<ImportEpisodeResult> {
  const res = await fetch(`${API_BASE}/api/episodes/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, title: title ?? "" }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Import failed: ${res.status}`);
  }
  return (await res.json()) as ImportEpisodeResult;
}

export async function importPodcast(url: string): Promise<ImportResult> {
  const res = await fetch(`${API_BASE}/api/shows/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Import failed: ${res.status}`);
  }
  return (await res.json()) as ImportResult;
}

export function getNewsletter(params: {
  from?: string;
  to?: string;
  show?: string;
  episode_ids?: number[];
}): Promise<Newsletter> {
  const q = new URLSearchParams();
  if (params.from) q.set("from", params.from);
  if (params.to) q.set("to", params.to);
  if (params.show) q.set("show", params.show);
  (params.episode_ids ?? []).forEach((id) => q.append("episode_ids", String(id)));
  return getJSON<Newsletter>(`/api/newsletter?${q.toString()}`);
}
