"use client";

import { Fragment, useMemo, useState } from "react";
import type { Segment } from "@/lib/api";
import { speakerColor } from "@/lib/colors";
import { fmtTimestamp } from "@/lib/format";

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlight(text: string, query: string) {
  if (!query) return text;
  const parts = text.split(new RegExp(`(${escapeRegExp(query)})`, "ig"));
  return parts.map((part, i) =>
    part.toLowerCase() === query ? (
      <mark key={i} className="rounded bg-[#e53e3e]/30 px-0.5 text-zinc-50">
        {part}
      </mark>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    ),
  );
}

export default function TranscriptView({
  segments,
  speakers,
}: {
  segments: Segment[];
  speakers: string[];
}) {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();
  const filtered = useMemo(
    () => (query ? segments.filter((s) => s.text.toLowerCase().includes(query)) : segments),
    [segments, query],
  );

  return (
    <div>
      <div className="mb-5 flex flex-wrap gap-x-4 gap-y-2">
        {speakers.map((sp) => (
          <span key={sp} className="inline-flex items-center gap-1.5 text-sm">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ backgroundColor: speakerColor(sp, speakers) }}
            />
            <span className="text-zinc-300">{sp}</span>
          </span>
        ))}
      </div>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search this transcript…"
        className="mb-6 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-[#e53e3e]/50 focus:ring-2 focus:ring-[#e53e3e]/20"
      />
      {query && (
        <p className="mb-4 text-sm text-zinc-500">
          {filtered.length} of {segments.length} segments match “{q}”.
        </p>
      )}

      <div className="space-y-5">
        {filtered.map((s) => {
          const color = speakerColor(s.speaker_name, speakers);
          return (
            <div key={s.idx} id={`t-${s.start_ms ?? s.idx}`}>
              <div className="mb-1 flex items-baseline gap-2">
                <span className="text-sm font-semibold" style={{ color }}>
                  {s.speaker_name ?? "Unknown"}
                </span>
                {s.start_ms != null && (
                  <span className="font-[family-name:var(--font-mono)] text-xs tabular-nums text-zinc-500">
                    {fmtTimestamp(s.start_ms)}
                  </span>
                )}
              </div>
              <p
                className="border-l-2 pl-3 text-[15px] leading-relaxed text-zinc-300"
                style={{ borderColor: color }}
              >
                {highlight(s.text, query)}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
