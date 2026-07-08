"use client";

import { useState } from "react";
import Link from "next/link";
import type { Show } from "@/lib/api";
import { deleteShow } from "@/lib/api";

function DeleteButton({ slug, onDeleted }: { slug: string; onDeleted: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    setDeleting(true);
    try {
      await deleteShow(slug);
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
          className="text-xs text-rose-400 hover:text-rose-300 disabled:opacity-50 transition-opacity"
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
        <span className="text-zinc-600">·</span>
        <button
          onClick={(e) => { e.preventDefault(); setConfirming(false); }}
          className="text-xs text-zinc-400 hover:text-zinc-200 transition-opacity"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={(e) => { e.preventDefault(); setConfirming(true); }}
      title="Remove podcast"
      className="opacity-0 group-hover:opacity-100 transition-opacity text-zinc-600 hover:text-rose-400"
    >
      <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
        <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/>
        <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/>
      </svg>
    </button>
  );
}

export default function ShowGrid({ initialShows }: { initialShows: Show[] }) {
  const [shows, setShows] = useState(initialShows);

  function removeShow(slug: string) {
    setShows((prev) => prev.filter((s) => s.slug !== slug));
  }

  const totalTranscribed = shows.reduce((n, s) => n + s.transcribed, 0);

  return (
    <>
      <header>
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]" />
          <span className="text-[#00d4ff]">Sources</span>
        </p>
        <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
          Podcasts
        </h1>
        <p className="mt-3 text-[15px] text-zinc-400">
          {shows.length} shows · {totalTranscribed} episodes transcribed
        </p>
      </header>

      <div>
        <div className="grid grid-cols-[1fr_8rem_auto] gap-x-6 border-b border-white/[0.08] pb-2 text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-600">
          <span>Show</span>
          <span className="text-right">Transcribed</span>
          <span />
        </div>
        {shows.map((s) => (
          <div
            key={s.slug}
            className="group grid grid-cols-[1fr_8rem_auto] items-center gap-x-6 border-b border-white/[0.05] py-4"
          >
            <Link href={`/episodes?show=${s.slug}`}>
              <p className="text-sm font-medium text-zinc-100 transition-colors group-hover:text-[#00d4ff]">
                {s.name}
              </p>
            </Link>
            <span className="text-right font-[family-name:var(--font-mono)] text-sm text-zinc-400">
              {s.transcribed}
            </span>
            <div className="flex w-8 items-center justify-end">
              <DeleteButton slug={s.slug} onDeleted={() => removeShow(s.slug)} />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
