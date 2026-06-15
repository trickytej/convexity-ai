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
          <span className="inline-block h-px w-8 bg-[#1ec997]" />
          <span className="text-[#1ec997]">Sources</span>
        </p>
        <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
          Podcasts
        </h1>
        <p className="mt-3 text-[15px] text-zinc-400">
          {shows.length} shows · {totalTranscribed} episodes transcribed
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {shows.map((s) => (
          <div
            key={s.slug}
            className="group flex flex-col rounded-xl border border-white/[0.08] bg-[#0b0c10]/70 pl-5 pr-5 pt-5 pb-4 transition-all hover:border-[#1ec997]/30 hover:bg-[#0e1016]/85"
            style={{ borderLeft: "3px solid #1ec997" }}
          >
            <Link href={`/episodes?show=${s.slug}`} className="flex-1">
              <h2 className="text-base font-medium leading-snug tracking-tight text-zinc-100 transition-colors group-hover:text-[#1ec997]">
                {s.name}
              </h2>
            </Link>

            <div className="mt-3 flex items-center justify-between">
              <div className="flex items-center gap-1 text-sm text-zinc-500">
                <span className="font-[family-name:var(--font-mono)] font-medium text-zinc-300">{s.transcribed}</span>
                <span>transcribed</span>
              </div>
              <DeleteButton slug={s.slug} onDeleted={() => removeShow(s.slug)} />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
