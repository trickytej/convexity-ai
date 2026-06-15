"use client";

import { useState } from "react";
import type { EpisodeDigest, NuggetWithCuration, Segment } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import TranscriptView from "@/components/TranscriptView";
import { DigestView } from "@/components/DigestView";
import { GenerateEpisodeDigestButton } from "@/components/GenerateEpisodeDigestButton";
import { ReviewTab } from "@/components/ReviewTab";

export function EpisodeTabs({
  episodeId,
  segments,
  speakers,
  digest,
  nuggets,
}: {
  episodeId: number;
  segments: Segment[];
  speakers: string[];
  digest: EpisodeDigest | null;
  nuggets: NuggetWithCuration[];
}) {
  const [tab, setTab] = useState<"digest" | "transcript" | "review">(
    digest ? "digest" : "transcript",
  );

  const tabCls = (active: boolean) =>
    `-mb-px border-b-2 pb-2 transition ${
      active ? "border-[#1ec997] text-zinc-100" : "border-transparent text-zinc-500 hover:text-zinc-200"
    }`;

  return (
    <div>
      <div className="mb-5 flex gap-5 border-b border-white/[0.08] text-sm font-medium">
        <button type="button" onClick={() => setTab("digest")} className={tabCls(tab === "digest")}>
          Digest
        </button>
        <button
          type="button"
          onClick={() => setTab("transcript")}
          className={tabCls(tab === "transcript")}
        >
          Transcript
        </button>
        <button
          type="button"
          onClick={() => setTab("review")}
          className={tabCls(tab === "review")}
        >
          Review {nuggets.length > 0 && <span className="ml-1 text-xs text-zinc-500">({nuggets.length})</span>}
        </button>
      </div>

      {tab === "transcript" && <TranscriptView segments={segments} speakers={speakers} />}

      {tab === "review" && <ReviewTab episodeId={episodeId} nuggets={nuggets} />}

      {tab === "digest" &&
        (digest ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-zinc-500">
                Synthesized from {digest.nugget_count} insights
                {digest.generated_at ? ` · ${fmtDate(digest.generated_at)}` : ""}
              </p>
              <GenerateEpisodeDigestButton episodeId={episodeId} label="Regenerate" />
            </div>
            <DigestView digest={digest} />
          </div>
        ) : (
          <div className="space-y-4 py-10 text-center">
            <p className="mx-auto max-w-md text-zinc-400">
              No digest yet — generate a TMTB-style summary (themes + stock read-through) from this
              episode&apos;s insights.
            </p>
            <div className="flex justify-center">
              <GenerateEpisodeDigestButton episodeId={episodeId} />
            </div>
          </div>
        ))}
    </div>
  );
}
