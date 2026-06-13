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
