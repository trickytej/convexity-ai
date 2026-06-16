"use client";

import { useState } from "react";
import type { NuggetWithCuration } from "@/lib/api";
import { NuggetReviewCard } from "@/components/NuggetReviewCard";

export function ReviewTab({
  episodeId,
  nuggets,
}: {
  episodeId: number;
  nuggets: NuggetWithCuration[];
}) {
  const [keptOnly, setKeptOnly] = useState(false);

  const total = nuggets.length;
  const reviewed = nuggets.filter((n) => n.curation.decision !== "unreviewed").length;
  const kept = nuggets.filter((n) => n.curation.decision === "kept").length;

  const visible = keptOnly
    ? nuggets.filter((n) => n.curation.decision === "kept")
    : nuggets;

  return (
    <div className="space-y-4">
      {/* Progress bar + filter */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm text-zinc-400">
            <span className="font-semibold text-emerald-300">{kept} kept</span>
            {" / "}
            <span className="font-semibold text-zinc-200">{reviewed} reviewed</span>
            {" of "}
            {total}
          </p>
          <div className="h-1.5 w-48 rounded-full bg-white/10">
            <div
              className="h-1.5 rounded-full bg-[#00d4ff] transition-all"
              style={{ width: total > 0 ? `${(reviewed / total) * 100}%` : "0%" }}
            />
          </div>
        </div>

        <label className="flex items-center gap-2 text-sm text-zinc-400 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={keptOnly}
            onChange={(e) => setKeptOnly(e.target.checked)}
            className="rounded accent-[#00d4ff]"
          />
          Show kept only
        </label>
      </div>

      {/* Nugget cards */}
      {visible.length === 0 ? (
        <p className="py-10 text-center text-sm text-zinc-500">
          {keptOnly ? "No kept nuggets yet." : "No nuggets for this episode."}
        </p>
      ) : (
        <div className="space-y-3">
          {visible.map((n) => (
            <NuggetReviewCard key={n.id} nugget={n} episodeId={episodeId} />
          ))}
        </div>
      )}
    </div>
  );
}
