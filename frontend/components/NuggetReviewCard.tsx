"use client";

import { useState } from "react";
import type { Curation, CurationPatch, NuggetWithCuration } from "@/lib/api";
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

function sameCuration(a: Curation, b: Curation): boolean {
  return (
    a.decision === b.decision &&
    a.curator_rank === b.curator_rank &&
    a.contradicts_consensus === b.contradicts_consensus &&
    (a.note ?? "") === (b.note ?? "")
  );
}

export function NuggetReviewCard({
  nugget,
  episodeId,
}: {
  nugget: NuggetWithCuration;
  episodeId: number;
}) {
  // `saved` is the last persisted state; `draft` is the working copy the
  // curator edits. Nothing hits the API until they press Submit.
  const [saved, setSaved] = useState<Curation>(nugget.curation);
  const [draft, setDraft] = useState<Curation>(nugget.curation);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty = !sameCuration(draft, saved);
  const decision = draft.decision;
  const isKept = decision === "kept";
  const isKilled = decision === "killed";

  async function submit() {
    setSaving(true);
    setError(null);
    try {
      const patch: CurationPatch = {
        decision: draft.decision,
        curator_rank: draft.curator_rank,
        contradicts_consensus: draft.contradicts_consensus,
        note: draft.note ?? "",
      };
      const updated = await patchCuration(nugget.id, patch);
      setSaved(updated);
      setDraft(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    } finally {
      setSaving(false);
    }
  }

  function revisit() {
    setDraft(saved);
    setError(null);
  }

  const tickers = nugget.entities?.tickers ?? [];
  const companies = nugget.entities?.companies ?? [];

  const cardBg = isKept
    ? "bg-emerald-500/[0.07] border-emerald-500/30"
    : isKilled
      ? "bg-white/[0.02] border-white/[0.06] opacity-60"
      : "bg-[#0b0c10]/75 border-white/[0.08]";

  return (
    <div
      className={`rounded-lg border p-4 space-y-3 transition-colors ${cardBg} ${
        dirty ? "ring-1 ring-amber-400/40" : ""
      }`}
    >
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
      </div>

      {/* Claim */}
      <p className="text-sm font-medium text-zinc-100">{nugget.claim}</p>

      {/* Quote */}
      {nugget.quote && (
        <blockquote className="border-l-2 border-[#00d4ff]/40 pl-3 text-sm text-zinc-400 italic">
          {nugget.quote}
          {nugget.speaker_name && (
            <span className="not-italic text-zinc-500"> — {nugget.speaker_name}</span>
          )}
          {nugget.start_ms != null && (
            <a
              href={`/episode/${episodeId}?t=${nugget.start_ms}`}
              className="ml-2 text-xs text-[#00d4ff] hover:text-[#33ddff] not-italic"
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
            onClick={() =>
              setDraft((c) => ({
                ...c,
                decision: c.decision === "kept" ? "unreviewed" : "kept",
              }))
            }
            className={`px-3 py-1.5 transition-colors ${
              isKept ? "bg-emerald-500 text-[#05140e]" : "bg-white/[0.04] text-zinc-300 hover:bg-emerald-500/10 hover:text-emerald-300"
            }`}
          >
            ✓ Keep
          </button>
          <button
            type="button"
            onClick={() =>
              setDraft((c) => ({
                ...c,
                decision: c.decision === "killed" ? "unreviewed" : "killed",
              }))
            }
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
              onClick={() =>
                setDraft((c) => ({
                  ...c,
                  curator_rank: c.curator_rank === r ? null : r,
                }))
              }
              className={`w-6 h-6 rounded-full text-xs font-semibold transition-colors ${
                draft.curator_rank === r
                  ? "bg-[#00d4ff] text-[#001a26]"
                  : "bg-white/[0.06] text-zinc-400 hover:bg-[#00d4ff]/15 hover:text-[#00d4ff]"
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
            checked={draft.contradicts_consensus}
            onChange={(e) =>
              setDraft((c) => ({ ...c, contradicts_consensus: e.target.checked }))
            }
            className="rounded accent-[#00d4ff]"
          />
          contradicts consensus
        </label>
      </div>

      {/* Note */}
      <textarea
        rows={2}
        placeholder="Why it matters (curator note)…"
        value={draft.note ?? ""}
        onChange={(e) => setDraft((c) => ({ ...c, note: e.target.value }))}
        className="w-full rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-1 focus:ring-[#00d4ff]/40 resize-none"
      />

      {/* Submit / Revisit */}
      <div className="flex items-center justify-between gap-3 pt-1">
        <span className="text-xs">
          {saving ? (
            <span className="text-zinc-500">saving…</span>
          ) : error ? (
            <span className="text-rose-400">{error}</span>
          ) : dirty ? (
            <span className="text-amber-300">unsaved changes</span>
          ) : saved.updated_at ? (
            <span className="text-zinc-500">saved</span>
          ) : (
            <span className="text-zinc-600">not reviewed</span>
          )}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={revisit}
            disabled={!dirty || saving}
            className="rounded-md border border-white/15 px-3 py-1.5 text-xs font-medium text-zinc-300 transition-colors enabled:hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Revisit
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!dirty || saving}
            className="rounded-md bg-[#00d4ff] px-3 py-1.5 text-xs font-semibold text-[#001a26] transition-colors enabled:hover:bg-[#33ddff] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? "Submitting…" : "Submit"}
          </button>
        </div>
      </div>
    </div>
  );
}
