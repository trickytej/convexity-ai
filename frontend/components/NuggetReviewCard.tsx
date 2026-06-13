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
    ? "bg-emerald-50 border-emerald-200"
    : isKilled
      ? "bg-zinc-50 border-zinc-200 opacity-60"
      : "bg-white border-zinc-200";

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
          <span className="text-xs text-zinc-400 self-center">
            signal {nugget.signal_score.toFixed(2)} · suggest rank {nugget.suggested_rank}
          </span>
        </div>
        {saving && <span className="text-xs text-zinc-400">saving…</span>}
      </div>

      {/* Claim */}
      <p className="text-sm font-medium text-zinc-900">{nugget.claim}</p>

      {/* Quote */}
      {nugget.quote && (
        <blockquote className="border-l-2 border-zinc-300 pl-3 text-sm text-zinc-600 italic">
          {nugget.quote}
          {nugget.speaker_name && (
            <span className="not-italic text-zinc-500"> — {nugget.speaker_name}</span>
          )}
          {nugget.start_ms != null && (
            <a
              href={`/episode/${episodeId}?t=${nugget.start_ms}`}
              className="ml-2 text-xs text-indigo-500 hover:text-indigo-700 not-italic"
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
        <div className="flex rounded-md overflow-hidden border border-zinc-300 text-xs font-medium">
          <button
            type="button"
            onClick={() => {
              const next = isKept ? "unreviewed" : "kept";
              setCuration((c) => ({ ...c, decision: next }));
              save({ decision: next });
            }}
            className={`px-3 py-1.5 transition-colors ${
              isKept ? "bg-emerald-500 text-white" : "bg-white text-zinc-700 hover:bg-emerald-50"
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
            className={`px-3 py-1.5 border-l border-zinc-300 transition-colors ${
              isKilled ? "bg-zinc-500 text-white" : "bg-white text-zinc-700 hover:bg-zinc-100"
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
                  ? "bg-indigo-600 text-white"
                  : "bg-zinc-100 text-zinc-600 hover:bg-indigo-100"
              }`}
            >
              {r}
            </button>
          ))}
        </div>

        {/* Contradicts consensus */}
        <label className="flex items-center gap-1.5 text-xs text-zinc-600 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={curation.contradicts_consensus}
            onChange={(e) => {
              const v = e.target.checked;
              setCuration((c) => ({ ...c, contradicts_consensus: v }));
              save({ contradicts_consensus: v });
            }}
            className="rounded"
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
        className="w-full rounded-md border border-zinc-200 px-3 py-1.5 text-xs text-zinc-700 placeholder-zinc-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 resize-none"
      />
    </div>
  );
}
