"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import type { SecurityCategory } from "@/lib/api";
import { followSecurity, unfollowSecurity } from "@/lib/api";

/** The full security universe by category; click a chip to follow / unfollow. */
export default function FollowPicker({ categories }: { categories: SecurityCategory[] }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return categories;
    return categories
      .map((c) => ({
        ...c,
        companies: c.companies.filter(
          (s) => s.company.toLowerCase().includes(q) || (s.ticker ?? "").toLowerCase().includes(q),
        ),
      }))
      .filter((c) => c.companies.length > 0);
  }, [categories, query]);

  async function toggle(company: string, followed: boolean) {
    setBusy(company);
    setError("");
    try {
      await (followed ? unfollowSecurity(company) : followSecurity(company));
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search company or ticker…"
        className="w-full max-w-sm rounded-lg border border-white/[0.08] bg-[#0b0c10] px-3 py-2 text-[13px] text-zinc-200 outline-none placeholder:text-zinc-700 focus:border-[#00d4ff]/40"
      />
      {error && <p className="mt-3 text-[12px] text-rose-400">{error}</p>}
      <div className="mt-6 space-y-6">
        {filtered.map((cat) => (
          <div key={cat.label}>
            <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-600">{cat.label}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {cat.companies.map((s) => (
                <button
                  key={s.company}
                  disabled={busy === s.company}
                  onClick={() => toggle(s.company, !!s.followed)}
                  className={`rounded-full border px-3 py-1 text-[12px] transition disabled:opacity-50 ${
                    s.followed
                      ? "border-[#00d4ff]/40 bg-[#00d4ff]/10 text-[#00d4ff] hover:border-rose-500/40 hover:text-rose-300"
                      : "border-white/[0.08] text-zinc-400 hover:border-[#00d4ff]/30 hover:text-zinc-200"
                  }`}
                >
                  {s.followed ? "✓ " : "+ "}
                  {s.company}
                  {s.ticker && <span className="ml-1.5 font-[family-name:var(--font-mono)] text-[10px] opacity-60">{s.ticker}</span>}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
