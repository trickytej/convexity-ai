"use client";

import { useState } from "react";
import { setTriage, type TriageValue } from "@/lib/api";

export function TriageControls({ id, initial }: { id: number; initial: string }) {
  const [state, setState] = useState<TriageValue>((initial as TriageValue) || "pending");
  const [busy, setBusy] = useState(false);

  async function apply(choice: TriageValue) {
    const next: TriageValue = state === choice ? "pending" : choice; // click again to clear
    const prev = state;
    setState(next);
    setBusy(true);
    try {
      await setTriage(id, next);
    } catch {
      setState(prev); // revert on failure
    } finally {
      setBusy(false);
    }
  }

  const base = "rounded px-2 py-0.5 text-xs font-medium ring-1 ring-inset transition disabled:opacity-50";
  return (
    <div className="flex gap-1">
      <button
        type="button"
        disabled={busy}
        onClick={() => apply("relevant")}
        className={
          state === "relevant"
            ? `${base} bg-[#00d4ff] text-[#001a26] ring-[#00d4ff]`
            : `${base} bg-white/[0.04] text-zinc-400 ring-white/10 hover:bg-white/[0.08] hover:text-zinc-200`
        }
      >
        ★ Relevant
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={() => apply("not_relevant")}
        className={
          state === "not_relevant"
            ? `${base} bg-rose-500 text-white ring-rose-500`
            : `${base} bg-white/[0.04] text-zinc-400 ring-white/10 hover:bg-white/[0.08] hover:text-zinc-200`
        }
      >
        ✕ Not
      </button>
    </div>
  );
}
