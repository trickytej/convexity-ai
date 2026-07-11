const SERVER = typeof window === "undefined";
const BACKEND = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

/**
 * Isomorphic API call.
 * - Server (RSC / route handlers): hit the backend directly and attach the secret
 *   `DIGEST_API_KEY` (never exposed to the browser).
 * - Browser: hit the same-origin Next proxy at `/api/...`, which injects the key
 *   server-side. This keeps the API key out of the client bundle and avoids CORS.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  let url = path;
  if (SERVER) {
    url = `${BACKEND}${path}`;
    const key = process.env.DIGEST_API_KEY;
    if (key) headers.set("x-api-key", key);
  }
  return fetch(url, { cache: "no-store", ...init, headers });
}

/** Backend base URL, for the server-side proxy route only. */
export const API_BASE = BACKEND;

export interface Show {
  slug: string;
  name: string;
  network?: string | null;
  homepage?: string | null;
  hosts: string[];
  tier: string;
  format: string;
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
  status?: string | null;
  error?: string | null;
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
  const res = await apiFetch(path);
  if (!res.ok) {
    throw new Error(`API ${res.status} for ${path}`);
  }
  return (await res.json()) as T;
}

export function getShows(params: { format?: string } = {}): Promise<Show[]> {
  const q = new URLSearchParams();
  if (params.format) q.set("format", params.format);
  const qs = q.toString();
  return getJSON<Show[]>(`/api/shows${qs ? `?${qs}` : ""}`);
}

export function getEpisodes(
  params: { show?: string; days?: number; since?: string; until?: string; all?: boolean; limit?: number; offset?: number } = {},
): Promise<EpisodeList> {
  const q = new URLSearchParams();
  if (params.show) q.set("show", params.show);
  if (params.since) q.set("since", params.since);
  else if (params.days) q.set("days", String(params.days));
  if (params.until) q.set("until", params.until);
  if (params.all) q.set("all", "true");
  q.set("limit", String(params.limit ?? 50));
  q.set("offset", String(params.offset ?? 0));
  return getJSON<EpisodeList>(`/api/episodes?${q.toString()}`);
}

export async function pollAllShows(): Promise<{ shows_polled: number; new_episodes: number }> {
  const res = await apiFetch("/api/shows/poll-all", { method: "POST" });
  if (!res.ok) throw new Error(`poll-all failed: ${res.status}`);
  return res.json();
}

export interface IngestDispatch {
  dispatched: boolean;
  days: number;
  repo: string;
  workflow: string;
  run_url: string;
}

/**
 * Kick off background ingestion (download + transcribe + extract) for everything
 * published since `since`. Runs on a GitHub Actions runner; results stream into
 * the database over the next few minutes. Resolves with `null` when the backend
 * has no dispatch token configured (so callers can fall back to discovery-only).
 */
export async function dispatchIngest(params: {
  since?: string;
  days?: number;
}): Promise<IngestDispatch | null> {
  const res = await apiFetch("/api/ingest/dispatch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (res.status === 503) return null; // not configured — caller decides what to show
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `ingest dispatch failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteEpisode(id: number): Promise<void> {
  const res = await apiFetch(`/api/episodes/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
}

export async function renameEpisode(id: number, title: string): Promise<Episode> {
  const res = await apiFetch(`/api/episodes/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Rename failed: ${res.status}`);
  }
  return (await res.json()) as Episode;
}

export async function deleteShow(slug: string): Promise<void> {
  const res = await apiFetch(`/api/shows/${slug}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
}

export async function pollShow(slug: string): Promise<{ new: number; seen: number; total: number }> {
  const res = await apiFetch(`/api/shows/${slug}/poll`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Poll failed: ${res.status}`);
  }
  return res.json();
}

export async function processEpisode(id: number): Promise<{ status: string }> {
  const res = await apiFetch(`/api/episodes/${id}/process`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Process failed: ${res.status}`);
  }
  return res.json();
}

export async function getEpisodeStatus(id: number): Promise<{ status: string; error?: string; nugget_count: number; updated_at?: string | null }> {
  return getJSON(`/api/episodes/${id}/status`);
}

export async function resetEpisode(id: number): Promise<void> {
  const res = await apiFetch(`/api/episodes/${id}/reset`, { method: "POST" });
  if (!res.ok) throw new Error(`reset failed: ${res.status}`);
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

export async function generateReport(params: { days?: number; since?: string; until?: string; include_tweets?: boolean } = {}): Promise<GeneratedReport> {
  const q = new URLSearchParams({ days: String(params.days ?? 7) });
  if (params.since) q.set("since", params.since);
  if (params.until) q.set("until", params.until);
  if (params.include_tweets) q.set("include_tweets", "true");
  const res = await apiFetch(`/api/report/generate?${q.toString()}`, { method: "POST" });
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
  const res = await apiFetch(`/api/episodes/${id}/digest`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`digest generation failed: ${res.status}`);
  }
  return (await res.json()) as EpisodeDigest;
}

export async function setTriage(id: number, triage: TriageValue): Promise<void> {
  const res = await apiFetch(`/api/nuggets/${id}/triage`, {
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
  const res = await apiFetch(`/api/nuggets/${nuggetId}/curation`, {
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
  companies: string[];
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
  const res = await apiFetch(`/api/episodes/import`, {
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
  const res = await apiFetch(`/api/shows/import`, {
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

export async function importNewsletter(url: string): Promise<ImportResult> {
  const res = await apiFetch(`/api/newsletters/import`, {
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

export interface NewsletterSendPayload {
  to: string[];
  subject: string;
  show_name: string;
  lead: Array<{ claim: string; quote: string | null; speaker_name: string | null; curation_note: string | null; show_slug: string }>;
  good_to_know: Array<{ claim: string; quote: string | null; speaker_name: string | null; curation_note: string | null; show_slug: string }>;
  stocks: Array<{ company: string; stance: string; summary: string }>;
}

// ─── Scout ───────────────────────────────────────────────────────────────────

export interface ScoutAppearance {
  id: number;
  company: string;
  person_name: string | null;
  person_role: string | null;
  episode_id: number | null;
  episode_title: string;
  podcast_name: string;
  episode_url: string | null;
  thumbnail: string | null;
  description: string | null;
  published_at: string | null;
  created_at: string;
}

export function getScoutAppearances(params: { company?: string; days?: number } = {}): Promise<ScoutAppearance[]> {
  const q = new URLSearchParams();
  if (params.company) q.set("company", params.company);
  if (params.days)    q.set("days",    String(params.days));
  return getJSON<ScoutAppearance[]>(`/api/scout/appearances?${q.toString()}`);
}

export type ScoutPerson   = { name: string; role: string };
export type ScoutCompany  = { name: string; ticker?: string; people?: ScoutPerson[] };
// `people` holds individuals tracked without a company (the Individuals section).
export type ScoutCategory = { label: string; companies: ScoutCompany[]; people?: ScoutPerson[] };

export async function getScoutWatchlist(): Promise<ScoutCategory[]> {
  const { watchlist } = await getJSON<{ watchlist: ScoutCategory[] }>("/api/scout/watchlist");
  return watchlist;
}

export async function putScoutWatchlist(watchlist: ScoutCategory[]): Promise<void> {
  const res = await apiFetch(`/api/scout/watchlist`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(watchlist),
  });
  if (!res.ok) throw new Error(`watchlist save failed: ${res.status}`);
}

export interface ScoutRefreshKickoff {
  status: "started" | "already_running" | "cooldown";
  reason?: "quota" | "recent_scan";
  last_scan_at?: string;
  retry_at?: string;
}

export async function refreshScout(days = 30, force = false): Promise<ScoutRefreshKickoff> {
  const res = await apiFetch(`/api/scout/refresh?days=${days}${force ? "&force=true" : ""}`, { method: "POST" });
  if (!res.ok) throw new Error(`scout refresh failed: ${res.status}`);
  return res.json();
}

export interface ScoutRefreshStatus {
  status: "idle" | "running" | "done" | "error";
  started_at: string | null;
  finished_at: string | null;
  new: number;
  skipped: number;
  errors: string[];
  roster_size: number;
  processing_done: number;
  processing_total: number;
}

export function getScoutRefreshStatus(): Promise<ScoutRefreshStatus> {
  return getJSON<ScoutRefreshStatus>("/api/scout/refresh/status");
}

export async function reprocessPendingScout(): Promise<{ queued: number }> {
  const res = await apiFetch(`/api/scout/reprocess-pending`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `reprocess-pending failed: ${res.status}`);
  }
  return res.json();
}

export async function ingestScoutAppearance(appearanceId: number): Promise<{ episode_id: number; created: boolean }> {
  const res = await apiFetch(`/api/scout/appearances/${appearanceId}/ingest`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Ingest failed: ${res.status}`);
  }
  return res.json();
}

// ─── Scout: X (Twitter) accounts + tweets ────────────────────────────────────

export interface ScoutXAccounts {
  handles: string[];
  configured: boolean; // X_BEARER_TOKEN present on the backend
}

export function getScoutXAccounts(): Promise<ScoutXAccounts> {
  return getJSON<ScoutXAccounts>("/api/scout/x-accounts");
}

export async function putScoutXAccounts(handles: string[]): Promise<ScoutXAccounts> {
  const res = await apiFetch(`/api/scout/x-accounts`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(handles),
  });
  if (!res.ok) throw new Error(`x-accounts save failed: ${res.status}`);
  return res.json();
}

export async function refreshScoutX(days = 7): Promise<{ status: "started" | "already_running" }> {
  const res = await apiFetch(`/api/scout/refresh-x?days=${days}`, { method: "POST" });
  if (!res.ok) throw new Error(`x refresh failed: ${res.status}`);
  return res.json();
}

export interface ScoutXRefreshStatus {
  status: "idle" | "running" | "done" | "error";
  started_at: string | null;
  finished_at: string | null;
  new: number;
  skipped: number;
  errors: string[];
  handles_synced: number;
}

export function getScoutXRefreshStatus(): Promise<ScoutXRefreshStatus> {
  return getJSON<ScoutXRefreshStatus>("/api/scout/refresh-x/status");
}

export interface ScoutTweet {
  tweet_id: string;
  url: string;
  created_at: string | null;
  metrics: Record<string, number> | null;
  nugget: NuggetWithCuration;
}

export interface ScoutTweetBucket {
  handle: string;
  author_name: string | null;
  episode_id: number;
  tweets: ScoutTweet[];
}

export function getScoutTweets(days = 7): Promise<ScoutTweetBucket[]> {
  return getJSON<ScoutTweetBucket[]>(`/api/scout/tweets?days=${days}`);
}

export async function sendNewsletter(payload: NewsletterSendPayload): Promise<{ sent: number }> {
  const res = await apiFetch(`/api/newsletter/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Send failed: ${res.status}`);
  }
  return (await res.json()) as { sent: number };
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
