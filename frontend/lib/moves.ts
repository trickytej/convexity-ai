// Price series + detected moves + AI attribution, served by research-digest's own
// API under /api/moves (the market-moves engine is vendored into the backend).

import { apiFetch } from "@/lib/api";

export interface MoveBar {
  time: number; // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface Move {
  direction: string; // "up" | "down"
  start_time: number;
  end_time: number;
  start_price: number;
  end_price: number;
  pct_change: number; // fraction, e.g. 0.16 = +16%
  n_bars: number;
  confirmed: boolean;
  max_adverse_pct: number;
}

export interface MoveSeries {
  symbol: string;
  timeframe: string;
  bars: MoveBar[];
  moves: Move[];
}

export interface MoveHeadline {
  published?: string | null;
  publisher?: string | null;
  title?: string | null;
  url?: string | null;
  timing?: string | null;
}

export interface MoveInsight {
  symbol: string;
  timeframe: string;
  start_time: number;
  end_time: number;
  direction: string;
  pct_change: number;
  horizon: string;
  scope: string;
  summary: string;
  confidence: string;
  no_clear_catalyst: boolean;
  headlines: MoveHeadline[];
  model: string;
  generated_at: string;
  cached: boolean;
}

export interface SeriesOpts {
  timeframe?: string;
  threshold?: number;
  mode?: string;
  days?: number; // lookback window
}

/** Server-side fetch of a symbol's price series + detected moves. Returns null on any failure. */
export async function getSeries(symbol: string, opts: SeriesOpts = {}): Promise<MoveSeries | null> {
  const q = new URLSearchParams({
    symbol,
    timeframe: opts.timeframe ?? "day",
    threshold: String(opts.threshold ?? 0.07),
    mode: opts.mode ?? "swings",
  });
  if (opts.days) {
    const start = new Date(Date.now() - opts.days * 86_400_000).toISOString().slice(0, 10);
    q.set("start", start);
  }
  try {
    const res = await apiFetch(`/api/moves/series?${q.toString()}`);
    if (!res.ok) return null;
    return (await res.json()) as MoveSeries;
  } catch {
    return null;
  }
}
