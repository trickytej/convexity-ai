"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { generateReport } from "@/lib/api";

export function GenerateReportButton({
  days = 7,
  since,
  until,
  label = "Generate report",
}: {
  days?: number;
  since?: string;
  until?: string;
  label?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [includeTweets, setIncludeTweets] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await generateReport({ days, since, until, include_tweets: includeTweets });
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "generation failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={run}
        disabled={busy}
        className="rounded-lg bg-[#00d4ff] px-4 py-2 text-sm font-medium text-[#001a26] transition hover:bg-[#33ddff] disabled:opacity-50"
      >
        {busy ? "Generating… (a minute or two)" : label}
      </button>
      <label
        className="flex cursor-pointer select-none items-center gap-1.5 text-xs text-zinc-400"
        title="Adds a 'From X' section built from the tweets you kept on Scout"
      >
        <input
          type="checkbox"
          checked={includeTweets}
          onChange={(e) => setIncludeTweets(e.target.checked)}
          className="rounded accent-[#00d4ff]"
        />
        Include kept X posts
      </label>
      {error && <span className="text-sm text-rose-400">{error}</span>}
    </div>
  );
}
