import Link from "next/link";
import type { BoardSecurity } from "@/lib/api";
import { StatusDot } from "@/components/signals";

/** Compact picker for the Model tab: one tile per followed security, grouped by
 * sector. Each tile shows one status dot per What Matters question; the
 * questions themselves live on the security's page. */
export default function SecurityGrid({ securities }: { securities: BoardSecurity[] }) {
  const groups = new Map<string, BoardSecurity[]>();
  for (const s of securities) {
    const cat = s.category ?? "Other";
    groups.set(cat, [...(groups.get(cat) ?? []), s]);
  }

  return (
    <div className="space-y-10">
      {[...groups.entries()].map(([cat, secs]) => (
        <section key={cat}>
          <p className="flex items-baseline gap-3 text-[11px] font-semibold uppercase tracking-[0.22em] text-zinc-500">
            {cat}
            <span className="font-[family-name:var(--font-mono)] text-[11px] font-normal tracking-normal text-zinc-700">
              {secs.length}
            </span>
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
            {secs.map((s) => {
              const signals = s.questions.reduce((n, q) => n + q.signals, 0);
              return (
                <Link
                  key={s.key}
                  href={`/model/${encodeURIComponent(s.key)}`}
                  className="group flex flex-col justify-between rounded-xl border border-white/[0.08] bg-[#0b0c10]/70 px-3.5 py-3 transition hover:border-[#00d4ff]/50 hover:bg-[#00d4ff]/[0.04]"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-[family-name:var(--font-mono)] text-[15px] text-zinc-50 transition group-hover:text-[#00d4ff]">
                        {s.ticker ?? s.company}
                      </p>
                      <p className="mt-0.5 truncate text-[12px] text-zinc-500">{s.company}</p>
                    </div>
                    {s.has_model && (
                      <span className="shrink-0 rounded-sm border border-[#00d4ff]/30 px-1 py-px text-[9px] font-medium uppercase tracking-wider text-[#00d4ff]/80">
                        Model
                      </span>
                    )}
                  </div>
                  <div className="mt-3 flex items-center justify-between gap-2">
                    <span className="flex gap-1">
                      {s.questions.map((q) => (
                        <StatusDot key={q.id} status={q.status} />
                      ))}
                    </span>
                    <span className="font-[family-name:var(--font-mono)] text-[10px] text-zinc-600">
                      {signals} signal{signals !== 1 ? "s" : ""}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
