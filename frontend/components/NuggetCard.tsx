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
    <div className="rounded-xl border border-zinc-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone={TYPE_TONE[n.type] ?? "zinc"}>{typeLabel(n.type)}</Badge>
          <span className="font-mono text-xs text-zinc-400" title="signal score">
            {n.signal_score.toFixed(2)}
          </span>
          {n.corroboration_shows > 1 && (
            <Badge tone="amber">{n.corroboration_shows} shows</Badge>
          )}
        </div>
        <TriageControls id={n.id} initial={n.triage} />
      </div>

      <p className="font-medium leading-snug text-zinc-900">{n.claim}</p>

      {n.quote && (
        <blockquote className="mt-2 border-l-2 border-zinc-200 pl-3 text-sm italic text-zinc-500">
          “{n.quote}”
        </blockquote>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
        <span className="min-w-0 truncate">
          {n.speaker_name ? <span className="font-medium text-zinc-700">{n.speaker_name}</span> : null}
          {" · "}
          {n.show_slug} · {fmtDate(n.published_at)}
          {!n.quote_verified && <span className="text-zinc-400"> · unverified</span>}
        </span>
        <Link href={href} className="shrink-0 font-medium text-indigo-600 hover:text-indigo-800">
          in context →
        </Link>
      </div>
    </div>
  );
}
