import Link from "next/link";
import type { ReportNugget } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { Badge } from "@/components/ui";
import { TriageControls } from "@/components/TriageControls";

const TYPE_TONE: Record<string, "zinc" | "green" | "blue" | "amber" | "indigo"> = {
  thesis: "indigo",
  prediction: "amber",
  data_point: "blue",
  company_move: "green",
  contrarian: "amber",
  mental_model: "zinc",
  watch_item: "zinc",
};

function typeLabel(t: string): string {
  return t.replace(/_/g, " ");
}

export function NuggetCard({ n }: { n: ReportNugget }) {
  const href = `/episode/${n.episode_id}${n.start_ms != null ? `#t-${n.start_ms}` : ""}`;
  return (
    <div className="group rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 p-4 transition hover:border-[#1ec997]/30 hover:bg-[#0e1016]/85">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone={TYPE_TONE[n.type] ?? "zinc"}>{typeLabel(n.type)}</Badge>
          <span className="font-[family-name:var(--font-mono)] text-xs tabular-nums text-zinc-500" title="signal score">
            {n.signal_score.toFixed(2)}
          </span>
          {n.corroboration_shows > 1 && (
            <Badge tone="amber">{n.corroboration_shows} shows</Badge>
          )}
        </div>
        <TriageControls id={n.id} initial={n.triage} />
      </div>

      <p className="text-[15px] font-medium leading-snug text-zinc-100">{n.claim}</p>

      {n.quote && (
        <blockquote className="mt-2 border-l-2 border-[#1ec997]/40 pl-3 text-sm italic leading-relaxed text-zinc-500">
          “{n.quote}”
        </blockquote>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
        <span className="min-w-0 truncate">
          {n.speaker_name ? <span className="font-medium text-zinc-300">{n.speaker_name}</span> : null}
          {" · "}
          <span className="font-[family-name:var(--font-mono)]">{n.show_slug}</span> · {fmtDate(n.published_at)}
          {!n.quote_verified && <span className="text-zinc-600"> · unverified</span>}
        </span>
        <Link href={href} className="shrink-0 font-medium text-[#1ec997] transition hover:text-[#34d6a8]">
          in context →
        </Link>
      </div>
    </div>
  );
}
