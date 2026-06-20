"use client";

import { useState } from "react";
import { getMoveInsight, type MoveInsightResult } from "@/lib/moves-actions";
import type { Move, MoveBar, MoveInsight, MoveSeries } from "@/lib/moves";

const UP = "#34d399"; // emerald-400
const DOWN = "#fb7185"; // rose-400
const ACCENT = "#00d4ff";

function fmtDate(unix: number): string {
  return new Date(unix * 1000).toLocaleDateString(undefined, {
    year: "2-digit",
    month: "short",
    day: "numeric",
  });
}

function fmtPct(frac: number): string {
  return `${frac >= 0 ? "+" : ""}${(frac * 100).toFixed(1)}%`;
}

// ─── chart ───────────────────────────────────────────────────────────────────

function PriceChart({
  bars,
  moves,
  selected,
  onSelect,
}: {
  bars: MoveBar[];
  moves: Move[];
  selected: number | null;
  onSelect: (i: number) => void;
}) {
  const W = 1000;
  const H = 240;
  const padY = 16;
  const n = bars.length;
  const closes = bars.map((b) => b.close);
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;

  const x = (i: number) => (n <= 1 ? 0 : (i / (n - 1)) * W);
  const y = (c: number) => padY + (1 - (c - min) / span) * (H - 2 * padY);

  const idxByTime = new Map(bars.map((b, i) => [b.time, i]));
  const findIdx = (t: number) => {
    const exact = idxByTime.get(t);
    if (exact !== undefined) return exact;
    let best = 0;
    let bd = Infinity;
    for (let i = 0; i < n; i++) {
      const d = Math.abs(bars[i].time - t);
      if (d < bd) {
        bd = d;
        best = i;
      }
    }
    return best;
  };

  const linePath = bars
    .map((b, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(b.close).toFixed(1)}`)
    .join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-56 w-full">
      <path
        d={linePath}
        fill="none"
        stroke={ACCENT}
        strokeOpacity={0.45}
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
      {moves.map((m, mi) => {
        const si = findIdx(m.start_time);
        const ei = findIdx(m.end_time);
        const seg = bars
          .slice(si, ei + 1)
          .map((b, k) => `${k === 0 ? "M" : "L"}${x(si + k).toFixed(1)},${y(b.close).toFixed(1)}`)
          .join(" ");
        const col = m.direction === "up" ? UP : DOWN;
        const isSel = selected === mi;
        return (
          <g key={mi} className="cursor-pointer" onClick={() => onSelect(mi)}>
            {/* wide transparent hit area */}
            <path d={seg} fill="none" stroke="transparent" strokeWidth={14} vectorEffect="non-scaling-stroke" />
            <path
              d={seg}
              fill="none"
              stroke={col}
              strokeOpacity={isSel ? 1 : 0.85}
              strokeWidth={isSel ? 3.5 : 2}
              vectorEffect="non-scaling-stroke"
            />
          </g>
        );
      })}
    </svg>
  );
}

// ─── insight detail ────────────────────────────────────────────────────────────

function ConfidenceBadge({ c }: { c: string }) {
  const tone =
    c === "high"
      ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25"
      : c === "medium"
        ? "bg-amber-500/10 text-amber-300 ring-amber-500/25"
        : "bg-white/[0.06] text-zinc-300 ring-white/10";
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ring-1 ring-inset ${tone}`}>
      {c || "n/a"} confidence
    </span>
  );
}

function InsightDetail({ state }: { state: { loading?: boolean; data?: MoveInsight; error?: string } }) {
  if (state.loading) {
    return <p className="mt-3 animate-pulse text-sm text-zinc-500">Attributing the move… (asking the model)</p>;
  }
  if (state.error) {
    return <p className="mt-3 text-sm text-rose-400">Couldn&apos;t attribute this move: {state.error}</p>;
  }
  const d = state.data;
  if (!d) return null;
  return (
    <div className="mt-3 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <ConfidenceBadge c={d.confidence} />
        {d.horizon && <span className="text-[11px] uppercase tracking-wide text-zinc-500">{d.horizon}</span>}
        {d.scope && <span className="text-[11px] uppercase tracking-wide text-zinc-500">· {d.scope}</span>}
        {d.no_clear_catalyst && <span className="text-[11px] text-zinc-500">· no clear catalyst</span>}
      </div>
      <p className="text-sm leading-relaxed text-zinc-200">{d.summary}</p>
      {d.headlines.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-600">Headlines around the move</p>
          {d.headlines.slice(0, 5).map((h, i) => (
            <p key={i} className="text-xs leading-snug text-zinc-400">
              {h.url ? (
                <a href={h.url} target="_blank" rel="noreferrer" className="text-[#00d4ff] hover:text-[#5fe4ff]">
                  {h.title || h.url}
                </a>
              ) : (
                <span>{h.title}</span>
              )}
              {h.publisher && <span className="text-zinc-600"> · {h.publisher}</span>}
              {h.published && <span className="text-zinc-600"> · {h.published.slice(0, 10)}</span>}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── panel ─────────────────────────────────────────────────────────────────────

type InsightState = Record<number, { loading?: boolean; data?: MoveInsight; error?: string }>;

export default function MovesPanel({ series, symbol }: { series: MoveSeries | null; symbol: string }) {
  const [selected, setSelected] = useState<number | null>(null);
  const [insights, setInsights] = useState<InsightState>({});

  if (!series || series.bars.length === 0) {
    return (
      <section>
        <Eyebrow />
        <p className="mt-5 rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 px-5 py-6 text-sm text-zinc-500">
          No price data for {symbol} yet (the market‑moves service may be offline, or this ticker hasn&apos;t been
          ingested). Start it with <code className="font-mono text-zinc-400">moves serve</code> and ingest the symbol.
        </p>
      </section>
    );
  }

  const top = [...series.moves]
    .sort((a, b) => Math.abs(b.pct_change) - Math.abs(a.pct_change))
    .slice(0, 10);
  const last = series.bars[series.bars.length - 1];
  const closes = series.bars.map((b) => b.close);
  const lo = Math.min(...closes);
  const hi = Math.max(...closes);
  const timeframe = series.timeframe;

  async function selectMove(i: number) {
    setSelected((cur) => (cur === i ? null : i));
    if (insights[i]?.data || insights[i]?.loading) return;
    const m = top[i];
    setInsights((s) => ({ ...s, [i]: { loading: true } }));
    const res: MoveInsightResult = await getMoveInsight({
      symbol,
      timeframe,
      start_time: m.start_time,
      end_time: m.end_time,
      direction: m.direction,
      pct_change: m.pct_change,
    });
    setInsights((s) => ({
      ...s,
      [i]: "error" in res ? { error: res.error } : { data: res },
    }));
  }

  return (
    <section>
      <Eyebrow />

      <div className="mt-5 flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm text-zinc-500">
        <span>
          Last <span className="font-[family-name:var(--font-mono)] text-zinc-100">${last.close.toFixed(2)}</span>
        </span>
        <span>
          Range{" "}
          <span className="font-[family-name:var(--font-mono)] text-zinc-300">
            ${lo.toFixed(0)}–${hi.toFixed(0)}
          </span>
        </span>
        <span>
          {series.bars.length} {series.timeframe} bars · {series.moves.length} moves
        </span>
      </div>

      <div className="mt-4 rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 p-4">
        <PriceChart bars={series.bars} moves={top} selected={selected} onSelect={selectMove} />
        <p className="mt-2 flex items-center gap-4 text-[11px] text-zinc-600">
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-3 rounded-sm" style={{ background: UP }} /> up move
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-3 rounded-sm" style={{ background: DOWN }} /> down move
          </span>
          <span>· click a move to explain it</span>
        </p>
      </div>

      <div className="mt-5 divide-y divide-white/[0.06] overflow-hidden rounded-xl border border-white/[0.08] bg-[#0b0c10]/60">
        {top.map((m, i) => {
          const isSel = selected === i;
          const col = m.direction === "up" ? UP : DOWN;
          return (
            <div key={i}>
              <button
                type="button"
                onClick={() => selectMove(i)}
                className="flex w-full items-center gap-4 px-4 py-3 text-left transition hover:bg-white/[0.02]"
              >
                <span className="w-8 font-[family-name:var(--font-mono)] text-base font-semibold tabular-nums" style={{ color: col }}>
                  {m.direction === "up" ? "▲" : "▼"}
                </span>
                <span className="w-24 font-[family-name:var(--font-mono)] text-sm font-semibold tabular-nums" style={{ color: col }}>
                  {fmtPct(m.pct_change)}
                </span>
                <span className="flex-1 text-sm text-zinc-400">
                  {fmtDate(m.start_time)} → {fmtDate(m.end_time)}
                  <span className="ml-2 text-zinc-600">· {m.n_bars} bars</span>
                </span>
                <span className="text-xs text-[#00d4ff]/70">{isSel ? "hide" : "why? →"}</span>
              </button>
              {isSel && (
                <div className="border-t border-white/[0.04] bg-white/[0.01] px-4 pb-4">
                  <InsightDetail state={insights[i] ?? {}} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Eyebrow() {
  return (
    <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
      <span className="inline-block h-px w-8 bg-[#00d4ff]" />
      <span className="text-[#00d4ff]">Price &amp; market‑moving events</span>
    </p>
  );
}
