import type { BriefHit, QuestionStatus } from "@/lib/api";
import HitCard from "@/components/HitCard";

const STATUS: Record<QuestionStatus, { cls: string; label: string }> = {
  green: { cls: "bg-emerald-400 shadow-[0_0_8px] shadow-emerald-400/60", label: "Evidence supports" },
  yellow: { cls: "bg-amber-400 shadow-[0_0_8px] shadow-amber-400/50", label: "Mixed evidence" },
  red: { cls: "bg-rose-500 shadow-[0_0_8px] shadow-rose-500/60", label: "Evidence contradicts" },
  none: { cls: "bg-zinc-700", label: "No signals in the last 30 days" },
};

export function StatusDot({ status }: { status: QuestionStatus }) {
  const s = STATUS[status];
  return <span title={s.label} className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${s.cls}`} />;
}

/** A question's hits: signals up front, reference matches folded away below. */
export function HitList({ hits, sourceLinks }: { hits: BriefHit[]; sourceLinks: boolean }) {
  const signals = hits.filter((h) => h.tier === "signal");
  const refs = hits.filter((h) => h.tier !== "signal");
  return (
    <div className="mt-3 space-y-2.5">
      {signals.map((h) => (
        <HitCard key={h.hit_id} h={h} sourceLinks={sourceLinks} />
      ))}
      {refs.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer list-none text-[12px] text-zinc-600 transition hover:text-zinc-400 [&::-webkit-details-marker]:hidden">
            <span className="group-open:hidden">▸</span>
            <span className="hidden group-open:inline">▾</span> {refs.length} reference
            {refs.length === 1 ? "" : "s"}
            <span className="ml-1 text-zinc-700">— related, but not strong enough to count</span>
          </summary>
          <div className="mt-2.5 space-y-2.5">
            {refs.map((h) => (
              <HitCard key={h.hit_id} h={h} sourceLinks={sourceLinks} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
