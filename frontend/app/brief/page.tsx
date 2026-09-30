import Link from "next/link";
import type { BriefHit } from "@/lib/api";
import { getBrief } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { Badge } from "@/components/ui";

export const dynamic = "force-dynamic";

const WINDOWS = [
  { days: 1, label: "24h" },
  { days: 3, label: "3d" },
  { days: 7, label: "7d" },
];

const DIRECTION_CLS: Record<string, string> = {
  supports: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25",
  contradicts: "bg-rose-500/10 text-rose-300 ring-rose-500/25",
  unclear: "bg-white/[0.06] text-zinc-400 ring-white/10",
};

function hitSourceHref(h: BriefHit): string {
  if (h.nugget.tweet_url) return h.nugget.tweet_url;
  const t = h.nugget.start_ms != null ? `#t-${h.nugget.start_ms}` : "";
  return `/episode/${h.nugget.episode_id}${t}`;
}

function HitCard({ h }: { h: BriefHit }) {
  const external = !!h.nugget.tweet_url;
  const quote = (h.nugget.quote || "").trim();
  return (
    <div className="rounded-xl border border-white/[0.06] bg-[#0b0c10]/80 p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${DIRECTION_CLS[h.direction] ?? DIRECTION_CLS.unclear}`}
        >
          {h.direction}
        </span>
        <span className="font-[family-name:var(--font-mono)] text-[11px] text-zinc-600">
          {Math.round(h.relevance * 100)}%
        </span>
        <span className="ml-auto text-[11px] text-zinc-600">
          {h.nugget.speaker_name ? `${h.nugget.speaker_name} · ` : ""}
          {h.nugget.show_slug}
          {h.nugget.published_at ? ` · ${fmtDate(h.nugget.published_at)}` : ""}
        </span>
      </div>
      {h.why && <p className="mb-2 text-[13px] leading-relaxed text-[#00d4ff]/90">{h.why}</p>}
      <p className="text-[14px] leading-relaxed text-zinc-200">{h.nugget.claim}</p>
      {quote && quote !== h.nugget.claim && (
        <p className="mt-2 border-l-2 border-white/10 pl-3 text-[12px] leading-relaxed text-zinc-500">
          “{quote.length > 320 ? quote.slice(0, 320) + "…" : quote}”
        </p>
      )}
      <div className="mt-3">
        <Link
          href={hitSourceHref(h)}
          target={external ? "_blank" : undefined}
          rel={external ? "noopener noreferrer" : undefined}
          className="text-[11px] text-zinc-600 transition hover:text-[#00d4ff]"
        >
          {external ? "View post on X ↗" : "In context →"}
        </Link>
      </div>
    </div>
  );
}

export default async function BriefPage({
  searchParams,
}: {
  searchParams?: Promise<{ days?: string }>;
}) {
  const params = await searchParams;
  const days = Math.max(1, Math.min(30, Number(params?.days) || 1));
  const brief = await getBrief({ days });
  const totalHits = brief.companies.reduce((s, c) => s + c.hit_count, 0);

  return (
    <div>
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">Brief</span>
      </p>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
          What moved <span className="text-[#00d4ff]">your questions</span>
        </h1>
        <Link
          href="/theses"
          className="rounded-full border border-white/[0.1] px-3.5 py-1.5 text-[12px] font-medium text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff]"
        >
          Edit theses
        </Link>
      </div>

      <div className="mt-6 flex items-center gap-2">
        {WINDOWS.map((w) => (
          <Link
            key={w.days}
            href={`/brief?days=${w.days}`}
            className={`rounded-full border px-3 py-1 text-[12px] transition ${
              days === w.days
                ? "border-[#00d4ff]/40 bg-[#00d4ff]/8 text-[#00d4ff]"
                : "border-white/[0.06] text-zinc-500 hover:border-white/[0.14] hover:text-zinc-300"
            }`}
          >
            {w.label}
          </Link>
        ))}
        <span className="ml-3 font-[family-name:var(--font-mono)] text-xs tabular-nums text-zinc-600">
          {totalHits} development{totalHits === 1 ? "" : "s"}
        </span>
      </div>

      {brief.companies.length === 0 && (
        <div className="mt-14 max-w-xl">
          <p className="text-[15px] leading-relaxed text-zinc-400">
            Nothing new touched your thesis questions in this window.
          </p>
          <p className="mt-3 text-[13px] leading-relaxed text-zinc-600">
            No theses yet? Define the 4–5 questions that matter for each company you
            follow on the{" "}
            <Link href="/theses" className="text-[#00d4ff] transition hover:text-[#33ddff]">
              theses page
            </Link>
            , and every new podcast insight, newsletter, and X post gets weighed
            against them automatically.
          </p>
        </div>
      )}

      <div className="mt-10 space-y-12">
        {brief.companies.map((c) => (
          <section
            key={c.company}
            id={`company-${c.company.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
            className="scroll-mt-20"
          >
            <div className="mb-5 flex items-baseline gap-3 border-b border-white/[0.08] pb-3">
              <h2 className="text-2xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
                {c.company}
              </h2>
              {c.ticker && (
                <span className="font-[family-name:var(--font-mono)] text-xs text-zinc-500">
                  {c.ticker}
                </span>
              )}
              <span className="ml-auto">
                <Badge tone="indigo">
                  {c.hit_count} hit{c.hit_count === 1 ? "" : "s"}
                </Badge>
              </span>
            </div>
            <div className="space-y-8">
              {c.questions.map((q) => (
                <div key={q.question_id}>
                  <p className="text-[15px] font-medium leading-snug text-zinc-200">
                    {q.question}
                  </p>
                  {q.note && (
                    <p className="mt-1 text-[12px] leading-relaxed text-zinc-600">{q.note}</p>
                  )}
                  <div className="mt-3 space-y-2.5">
                    {q.hits.map((h, i) => (
                      <HitCard key={`${q.question_id}-${h.nugget.id}-${i}`} h={h} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
