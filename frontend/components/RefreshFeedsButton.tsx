"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { dispatchIngest, pollAllShows, type IngestDispatch } from "@/lib/api";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}
function defaultFrom() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}

export default function RefreshFeedsButton() {
  const router = useRouter();
  const [from, setFrom] = useState(defaultFrom());
  const [to, setTo] = useState(todayISO());
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [result, setResult] = useState<{ new_episodes: number; shows_polled: number } | null>(null);
  const [ingest, setIngest] = useState<IngestDispatch | null>(null);
  const [ingestNote, setIngestNote] = useState<string | null>(null);

  async function handleRefresh() {
    if (status === "loading") return;
    setStatus("loading");
    setResult(null);
    setIngest(null);
    setIngestNote(null);

    // 1) Primary action: kick off download + transcribe + extract in the
    //    background. This is fast (one dispatch call) and does its own polling.
    try {
      const d = await dispatchIngest({ since: from });
      if (d) setIngest(d);
      // no token configured — discovery still runs, silently skip the note
    } catch {
      // background transcription unavailable locally — discovery still runs below
    }

    // 2) Best-effort instant discovery. Never block the refresh on it: polling
    //    every feed can exceed the proxy timeout, and the dispatched run
    //    discovers the same episodes anyway.
    try {
      const data = await pollAllShows();
      setResult(data);
    } catch {
      /* ignored — discovery also happens inside the dispatched run */
    }

    setStatus("done");
    router.push(`/insights?from=${from}&to=${to}`);
  }

  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 px-5 py-4">
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">Refresh Feeds</span>
      </p>
      <p className="mt-2 text-sm text-zinc-400">
        Set a date range and refresh. New episodes are discovered immediately, then
        downloaded and transcribed in the background.
      </p>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-[11px] uppercase tracking-widest text-zinc-500">From</label>
          <input
            type="date"
            value={from}
            max={to}
            onChange={(e) => setFrom(e.target.value)}
            className="rounded-lg border border-white/[0.1] bg-white/[0.04] px-3 py-2 text-sm text-zinc-100 outline-none focus:border-[#00d4ff]/40 focus:ring-1 focus:ring-[#00d4ff]/20 [color-scheme:dark]"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[11px] uppercase tracking-widest text-zinc-500">To</label>
          <input
            type="date"
            value={to}
            min={from}
            onChange={(e) => setTo(e.target.value)}
            className="rounded-lg border border-white/[0.1] bg-white/[0.04] px-3 py-2 text-sm text-zinc-100 outline-none focus:border-[#00d4ff]/40 focus:ring-1 focus:ring-[#00d4ff]/20 [color-scheme:dark]"
          />
        </div>

        <button
          onClick={handleRefresh}
          disabled={status === "loading"}
          className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${
            status === "loading"
              ? "bg-[#00d4ff]/10 text-[#00d4ff] cursor-not-allowed"
              : "bg-[#00d4ff] text-[#001a26] hover:bg-[#00d4ff]/90"
          }`}
        >
          {status === "loading" && (
            <svg className="animate-spin" width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2z"/>
              <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466"/>
            </svg>
          )}
          {status === "loading" ? "Refreshing…" : "Refresh Feeds"}
        </button>

        {status === "done" && result && (
          <span className="text-sm text-zinc-400">
            <span className="text-emerald-400">+{result.new_episodes} new</span>
            {" "}from {result.shows_polled} shows
          </span>
        )}
        {status === "error" && (
          <span className="text-sm text-rose-400">Refresh failed — check the backend</span>
        )}
      </div>

      {(ingest || ingestNote) && (
        <p className="mt-3 text-sm text-zinc-400">
          {ingest ? (
            <>
              <span className="text-[#00d4ff]">
                Transcribing the last {ingest.days} day{ingest.days !== 1 ? "s" : ""} in the background.
              </span>{" "}
              Transcripts and nuggets will appear here over the next few minutes —{" "}
              <a
                href={ingest.run_url}
                target="_blank"
                rel="noreferrer"
                className="text-[#00d4ff] underline-offset-2 hover:underline"
              >
                view run ↗
              </a>
              .
            </>
          ) : (
            <span className="text-amber-300">{ingestNote}</span>
          )}
        </p>
      )}
    </div>
  );
}
