"use client";

import { useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { Show } from "@/lib/api";

type UpdatedShow = { slug: string; name: string; newCount: number };

async function pollOne(slug: string): Promise<{ new: number }> {
  const res = await apiFetch(`/api/shows/${slug}/poll`, { method: "POST" });
  if (!res.ok) throw new Error(`poll failed: ${res.status}`);
  return res.json();
}

export default function RefreshFeedsButton() {
  const [status, setStatus] = useState<"idle" | "loading" | "done">("idle");
  const [totalNew, setTotalNew] = useState(0);
  const [updated, setUpdated] = useState<UpdatedShow[]>([]);
  const [error, setError] = useState(false);

  async function handleRefresh() {
    setStatus("loading");
    setUpdated([]);
    setTotalNew(0);
    setError(false);
    try {
      const res = await apiFetch("/api/shows");
      const shows: Show[] = await res.json();
      const active = shows.filter((s) => s.active);

      const results = await Promise.allSettled(active.map((s) => pollOne(s.slug)));

      const found: UpdatedShow[] = [];
      let total = 0;
      results.forEach((r, i) => {
        if (r.status === "fulfilled" && r.value.new > 0) {
          total += r.value.new;
          found.push({ slug: active[i].slug, name: active[i].name, newCount: r.value.new });
        }
      });

      setTotalNew(total);
      setUpdated(found);
      setStatus("done");
    } catch {
      setError(true);
      setStatus("done");
    }
  }

  return (
    <div className="flex flex-col gap-3">
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

        {status === "done" && !error && (
          <span className="text-sm text-zinc-400">
            {totalNew > 0
              ? `Found ${totalNew} new episode${totalNew !== 1 ? "s" : ""} across ${updated.length} show${updated.length !== 1 ? "s" : ""}`
              : "All feeds up to date"}
          </span>
        )}
        {error && <span className="text-sm text-rose-400">Error checking feeds</span>}
      </div>

      {updated.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {updated.map((s) => (
            <Link
              key={s.slug}
              href={`/episodes?show=${s.slug}`}
              className="flex items-center gap-1.5 rounded-full border border-[#00d4ff]/25 px-3 py-1 text-xs font-medium text-[#00d4ff]/80 transition hover:border-[#00d4ff]/60 hover:text-[#00d4ff]"
            >
              {s.name}
              <span className="rounded-full bg-[#00d4ff]/15 px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[10px]">
                +{s.newCount}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
