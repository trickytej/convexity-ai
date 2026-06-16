"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Show } from "@/lib/api";

async function pollOne(slug: string): Promise<{ new: number }> {
  const res = await apiFetch(`/api/shows/${slug}/poll`, { method: "POST" });
  if (!res.ok) throw new Error(`poll failed: ${res.status}`);
  return res.json();
}

export default function RefreshFeedsButton() {
  const [status, setStatus] = useState<"idle" | "loading" | "done">("idle");
  const [summary, setSummary] = useState<string | null>(null);

  async function handleRefresh() {
    setStatus("loading");
    setSummary(null);
    try {
      const res = await apiFetch("/api/shows");
      const shows: Show[] = await res.json();
      const active = shows.filter((s) => s.active);

      const results = await Promise.allSettled(active.map((s) => pollOne(s.slug)));

      let totalNew = 0;
      let showsWithNew = 0;
      for (const r of results) {
        if (r.status === "fulfilled" && r.value.new > 0) {
          totalNew += r.value.new;
          showsWithNew++;
        }
      }

      setSummary(
        totalNew > 0
          ? `Found ${totalNew} new episode${totalNew !== 1 ? "s" : ""} across ${showsWithNew} show${showsWithNew !== 1 ? "s" : ""}`
          : "All feeds up to date",
      );
      setStatus("done");
    } catch {
      setSummary("Error checking feeds");
      setStatus("done");
    }
  }

  return (
    <div className="flex items-center gap-4">
      <button
        onClick={handleRefresh}
        disabled={status === "loading"}
        className="flex items-center gap-2 rounded-lg border border-[#00d4ff]/30 px-4 py-2 text-sm font-medium text-[#00d4ff] transition hover:border-[#00d4ff]/60 hover:bg-[#00d4ff]/5 disabled:opacity-50"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="currentColor"
          className={status === "loading" ? "animate-spin" : ""}
        >
          <path
            fillRule="evenodd"
            d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2z"
          />
          <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466" />
        </svg>
        {status === "loading" ? "Checking feeds…" : "Refresh Feeds"}
      </button>
      {summary && (
        <span className="text-sm text-zinc-400">{summary}</span>
      )}
    </div>
  );
}
