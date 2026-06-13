"use client";

import { useState } from "react";
import type { EpisodeDigest, Segment } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import TranscriptView from "@/components/TranscriptView";
import { DigestView } from "@/components/DigestView";
import { GenerateEpisodeDigestButton } from "@/components/GenerateEpisodeDigestButton";

export function EpisodeTabs({
  episodeId,
  segments,
  speakers,
  digest,
}: {
  episodeId: number;
  segments: Segment[];
  speakers: string[];
  digest: EpisodeDigest | null;
}) {
  const [tab, setTab] = useState<"digest" | "transcript">(digest ? "digest" : "transcript");

  const tabCls = (active: boolean) =>
    `-mb-px border-b-2 pb-2 ${
      active ? "border-indigo-600 text-zinc-900" : "border-transparent text-zinc-500 hover:text-zinc-800"
    }`;

  return (
    <div>
      <div className="mb-5 flex gap-5 border-b border-zinc-200 text-sm font-medium">
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
      </div>

      {tab === "transcript" && <TranscriptView segments={segments} speakers={speakers} />}

      {tab === "digest" &&
        (digest ? (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-zinc-400">
                Synthesized from {digest.nugget_count} insights
                {digest.generated_at ? ` · ${fmtDate(digest.generated_at)}` : ""}
              </p>
              <GenerateEpisodeDigestButton episodeId={episodeId} label="Regenerate" />
            </div>
            <DigestView digest={digest} />
          </div>
        ) : (
          <div className="space-y-4 py-10 text-center">
            <p className="mx-auto max-w-md text-zinc-600">
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
