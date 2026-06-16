"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { generateEpisodeDigest } from "@/lib/api";

export function GenerateEpisodeDigestButton({
  episodeId,
  label = "Generate digest",
}: {
  episodeId: number;
  label?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await generateEpisodeDigest(episodeId);
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
        className="rounded-lg bg-[#e53e3e] px-4 py-2 text-sm font-medium text-[#ffffff] transition hover:bg-[#f56565] disabled:opacity-50"
      >
        {busy ? "Generating… (~a minute)" : label}
      </button>
      {error && <span className="text-sm text-rose-400">{error}</span>}
    </div>
  );
}
