"use server";

import { MOVES_API_URL, type MoveInsight } from "@/lib/moves";

export interface MoveInsightRequest {
  symbol: string;
  timeframe: string;
  start_time: number;
  end_time: number;
  direction: string;
  pct_change: number;
}

export type MoveInsightResult = MoveInsight | { error: string };

/** Server action: ask market-moves for a grounded attribution of one move (cached server-side). */
export async function getMoveInsight(req: MoveInsightRequest): Promise<MoveInsightResult> {
  try {
    const res = await fetch(`${MOVES_API_URL}/api/insight`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(req),
      cache: "no-store",
    });
    if (!res.ok) {
      const detail = await res
        .json()
        .then((d: { detail?: string }) => d.detail)
        .catch(() => null);
      return { error: detail ?? `attribution failed (${res.status})` };
    }
    return (await res.json()) as MoveInsight;
  } catch (e) {
    return { error: e instanceof Error ? e.message : "request failed" };
  }
}
