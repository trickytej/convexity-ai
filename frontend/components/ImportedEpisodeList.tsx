"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Episode } from "@/lib/api";
import { deleteEpisode } from "@/lib/api";
import { fmtDate, fmtDuration } from "@/lib/format";
import { Badge, SourceBadge } from "@/components/ui";
import TranscribeButton from "@/components/TranscribeButton";
import RenameEpisodeTitle from "@/components/RenameEpisodeTitle";

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  transcribed: { label: "Transcribed", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  acquired:    { label: "Downloaded",  cls: "bg-blue-50 text-blue-700 ring-blue-200" },
  discovered:  { label: "Discovered",  cls: "bg-zinc-100 text-zinc-500 ring-zinc-200" },
  failed:      { label: "Failed",      cls: "bg-rose-50 text-rose-600 ring-rose-200" },
};

function DeleteEpisodeButton({ episodeId, onDeleted }: { episodeId: number; onDeleted: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    setDeleting(true);
    try {
      await deleteEpisode(episodeId);
      onDeleted();
    } catch {
      setDeleting(false);
      setConfirming(false);
    }
  }

  if (confirming) {
    return (
      <div className="flex items-center gap-2" onClick={(e) => e.preventDefault()}>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="text-xs text-rose-500 hover:text-rose-700 disabled:opacity-50 transition-opacity"
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
        <span className="text-zinc-300">·</span>
        <button
          onClick={(e) => { e.preventDefault(); setConfirming(false); }}
          className="text-xs text-zinc-400 hover:text-zinc-700 transition-opacity"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={(e) => { e.preventDefault(); setConfirming(true); }}
      title="Delete episode"
      className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-300 hover:text-rose-500"
    >
      <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
        <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/>
        <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/>
      </svg>
    </button>
  );
}

export default function ImportedEpisodeList({ initialEpisodes }: { initialEpisodes: Episode[] }) {
  const router = useRouter();
  const [episodes, setEpisodes] = useState(initialEpisodes);

  function removeEpisode(id: number) {
    setEpisodes((prev) => prev.filter((e) => e.id !== id));
  }

  if (episodes.length === 0) {
    return (
      <div className="divide-y divide-zinc-200 overflow-hidden rounded-xl border border-zinc-200 bg-white">
        <p className="px-4 py-8 text-center text-zinc-500">No imported episodes yet.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-zinc-200 overflow-hidden rounded-xl border border-zinc-200 bg-white">
      {episodes.map((e) => {
        const isTranscribed = e.status === "transcribed" || (!e.status && !!e.source);
        const statusInfo = STATUS_BADGE[e.status ?? (e.source ? "transcribed" : "discovered")];

        return (
          <div key={e.id} className="group flex items-center justify-between gap-4 px-4 py-3">
            <div className="min-w-0 flex-1">
              <RenameEpisodeTitle
                episodeId={e.id}
                title={e.title}
                href={isTranscribed ? `/episode/${e.id}` : undefined}
              />
              <p className="mt-0.5 text-sm text-zinc-500">
                {fmtDate(e.published_at)} · {fmtDuration(e.duration_seconds)}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {isTranscribed && e.nugget_count > 0 && (
                <Badge tone="indigo">{e.nugget_count} nuggets</Badge>
              )}
              {isTranscribed && <SourceBadge source={e.source} />}
              {!isTranscribed && statusInfo && (
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${statusInfo.cls}`}>
                  {statusInfo.label}
                </span>
              )}
              {!isTranscribed && (
                <TranscribeButton episodeId={e.id} initialStatus={e.status} />
              )}
              <DeleteEpisodeButton episodeId={e.id} onDeleted={() => removeEpisode(e.id)} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
