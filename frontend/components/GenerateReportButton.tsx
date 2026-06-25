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
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      await generateReport({ days, since, until });
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
      {error && <span className="text-sm text-rose-400">{error}</span>}
    </div>
  );
}
