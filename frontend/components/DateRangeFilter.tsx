"use client";

import { useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";

/** Compact From/To filter that reloads the current page with ?from=&to= —
 * the same range convention the Insights (home) tab uses. */
export default function DateRangeFilter({
  basePath,
  initialFrom,
  initialTo,
  auto = false,
}: {
  basePath: string;
  initialFrom: string;
  initialTo: string;
  /** Reload as soon as a date changes (no Apply button), keeping other params. */
  auto?: boolean;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [from, setFrom] = useState(initialFrom);
  const [to, setTo] = useState(initialTo);
  const [isPending, startTransition] = useTransition();

  function apply(f = from, t = to) {
    const params = new URLSearchParams(auto ? searchParams.toString() : "");
    if (f) params.set("from", f);
    if (t) params.set("to", t);
    startTransition(() => router.push(`${basePath}?${params.toString()}`));
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label className="text-[11px] uppercase tracking-widest text-zinc-600">From</label>
        <input
          type="date"
          value={from}
          max={to}
          onChange={(e) => {
            setFrom(e.target.value);
            if (auto && e.target.value) apply(e.target.value, to);
          }}
          className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[13px] text-zinc-300 outline-none focus:border-[#00d4ff]/40 focus:ring-1 focus:ring-[#00d4ff]/20 [color-scheme:dark]"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-[11px] uppercase tracking-widest text-zinc-600">To</label>
        <input
          type="date"
          value={to}
          min={from}
          onChange={(e) => {
            setTo(e.target.value);
            if (auto && e.target.value) apply(from, e.target.value);
          }}
          className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[13px] text-zinc-300 outline-none focus:border-[#00d4ff]/40 focus:ring-1 focus:ring-[#00d4ff]/20 [color-scheme:dark]"
        />
      </div>
      {auto ? (
        isPending && <span className="pb-1.5 text-[13px] text-zinc-500">Loading…</span>
      ) : (
        <button
          onClick={() => apply()}
          disabled={isPending}
          className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-1.5 text-[13px] text-zinc-300 transition hover:border-[#00d4ff]/30 hover:text-zinc-100 disabled:opacity-40"
        >
          {isPending ? "Loading…" : "Apply"}
        </button>
      )}
    </div>
  );
}
