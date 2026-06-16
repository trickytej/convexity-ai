"use client";

import { useCallback, useRef, useState } from "react";
import type { CurationPatch, NuggetWithCuration } from "@/lib/api";
import { patchCuration } from "@/lib/api";
import { Badge } from "@/components/ui";

function fmtMs(ms: number | null | undefined): string {
  if (!ms) return "";
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
    : `${m}:${String(sec).padStart(2, "0")}`;
}

export function NuggetReviewCard({
  nugget,
  episodeId,
}: {
  nugget: NuggetWithCuration;
  episodeId: number;
}) {
  const [curation, setCuration] = useState(nugget.curation);
  const [saving, setSaving] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const save = useCallback(
    (patch: CurationPatch) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        setSaving(true);
        try {
          const updated = await patchCuration(nugget.id, patch);
          setCuration(updated);
        } finally {
          setSaving(false);
        }
      }, 400);
    },
    [nugget.id],
  );

  const decision = curation.decision;
  const isKept = decision === "kept";
  const isKilled = decision === "killed";

  const tickers = nugget.entities?.tickers ?? [];
  const companies = nugget.entities?.companies ?? [];

  const cardBg = isKept
    ? "bg-emerald-500/[0.07] border-emerald-500/30"
    : isKilled
      ? "bg-white/[0.02] border-white/[0.06] opacity-60"
      : "bg-[#0b0c10]/75 border-white/[0.08]";

  return (
    <div className={`rounded-lg border p-4 space-y-3 transition-colors ${cardBg}`}>
      {/* Header row */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="zinc">{nugget.type.replace("_", " ")}</Badge>
          {nugget.primary_sector && <Badge tone="indigo">{nugget.primary_sector}</Badge>}
          {tickers.map((t) => (
            <Badge key={t} tone="amber">{t}</Badge>
          ))}
          {nugget.quote_verified && <Badge tone="green">verified</Badge>}
          <span className="text-xs text-zinc-500 self-center">
            signal {nugget.signal_score.toFixed(2)} · suggest rank {nugget.suggested_rank}
          </span>
        </div>
        {saving && <span className="text-xs text-zinc-500">saving…</span>}
      </div>

      {/* Claim */}
      <p className="text-sm font-medium text-zinc-100">{nugget.claim}</p>

      {/* Quote */}
      {nugget.quote && (
        <blockquote className="border-l-2 border-[#e53e3e]/40 pl-3 text-sm text-zinc-400 italic">
          {nugget.quote}
          {nugget.speaker_name && (
            <span className="not-italic text-zinc-500"> — {nugget.speaker_name}</span>
          )}
          {nugget.start_ms != null && (
            <a
              href={`/episode/${episodeId}?t=${nugget.start_ms}`}
              className="ml-2 text-xs text-[#e53e3e] hover:text-[#f56565] not-italic"
            >
              {fmtMs(nugget.start_ms)} ↗
            </a>
          )}
        </blockquote>
      )}

      {/* Companies */}
      {companies.length > 0 && (
        <p className="text-xs text-zinc-500">{companies.join(", ")}</p>
      )}

      {/* Controls row */}
      <div className="flex flex-wrap items-center gap-3 pt-1">
        {/* Keep / Kill toggle */}
        <div className="flex rounded-md overflow-hidden border border-white/15 text-xs font-medium">
          <button
            type="button"
            onClick={() => {
              const next = isKept ? "unreviewed" : "kept";
              setCuration((c) => ({ ...c, decision: next }));
              save({ decision: next });
            }}
            className={`px-3 py-1.5 transition-colors ${
              isKept ? "bg-emerald-500 text-[#05140e]" : "bg-white/[0.04] text-zinc-300 hover:bg-emerald-500/10 hover:text-emerald-300"
            }`}
          >
            ✓ Keep
          </button>
          <button
            type="button"
            onClick={() => {
              const next = isKilled ? "unreviewed" : "killed";
              setCuration((c) => ({ ...c, decision: next }));
              save({ decision: next });
            }}
            className={`px-3 py-1.5 border-l border-white/15 transition-colors ${
              isKilled ? "bg-zinc-600 text-white" : "bg-white/[0.04] text-zinc-300 hover:bg-white/[0.08]"
            }`}
          >
            ✕ Kill
          </button>
        </div>

        {/* Rank selector */}
        <div className="flex items-center gap-1 text-xs">
          <span className="text-zinc-500">Rank:</span>
          {([1, 2, 3] as const).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => {
                const next = curation.curator_rank === r ? null : r;
                setCuration((c) => ({ ...c, curator_rank: next }));
                save({ curator_rank: next ?? undefined });
              }}
              className={`w-6 h-6 rounded-full text-xs font-semibold transition-colors ${
                curation.curator_rank === r
                  ? "bg-[#e53e3e] text-[#ffffff]"
                  : "bg-white/[0.06] text-zinc-400 hover:bg-[#e53e3e]/15 hover:text-[#e53e3e]"
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        {/* Contradicts consensus */}
        <label className="flex items-center gap-1.5 text-xs text-zinc-400 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={curation.contradicts_consensus}
            onChange={(e) => {
              const v = e.target.checked;
              setCuration((c) => ({ ...c, contradicts_consensus: v }));
              save({ contradicts_consensus: v });
            }}
            className="rounded accent-[#e53e3e]"
          />
          contradicts consensus
        </label>
      </div>

      {/* Note */}
      <textarea
        rows={2}
        placeholder="Why it matters (curator note)…"
        defaultValue={curation.note ?? ""}
        onChange={(e) => {
          save({ note: e.target.value });
        }}
        className="w-full rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-[#e53e3e]/40 resize-none"
      />
    </div>
  );
}
