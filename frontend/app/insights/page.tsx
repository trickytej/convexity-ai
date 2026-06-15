import Link from "next/link";
import { getInsights } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { NuggetCard } from "@/components/NuggetCard";

export const dynamic = "force-dynamic";

const PER_SECTION = 15;

function anchorId(sector: string): string {
  return "sec-" + sector.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

const VIEWS = [
  { id: undefined, label: "All" },
  { id: "pending", label: "To review" },
  { id: "relevant", label: "Important" },
] as const;

export default async function InsightsPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string; triage?: string }>;
}) {
  const { days, triage } = await searchParams;
  const window = days ? Math.max(1, parseInt(days, 10) || 7) : 7;
  const view = triage === "pending" || triage === "relevant" ? triage : undefined;
  const report = await getInsights(window, PER_SECTION, view);
  const { stats } = report;
  const triageCounts = (stats.triage ?? {}) as Record<string, number>;
  const maxShows = Math.max(1, ...report.top_entities.map((e) => e.shows.length));

  const qs = (t?: string) => {
    const q = new URLSearchParams();
    if (days) q.set("days", days);
    if (t) q.set("triage", t);
    const s = q.toString();
    return s ? `/insights?${s}` : "/insights";
  };

  const tiles = [
    { label: "Insights", value: stats.nuggets },
    { label: "Episodes", value: stats.episodes },
    { label: "Shows", value: stats.shows },
    { label: "Verified", value: stats.verified },
  ];

  return (
    <div>
      {/* masthead */}
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#1ec997]" />
        <span className="text-[#1ec997]">Weekly Insights</span>
        <span className="text-zinc-700">•</span>
        <span className="text-zinc-500">
          {fmtDate(report.since)} – {fmtDate(report.until)}
        </span>
      </p>
      <h1 className="mt-5 max-w-3xl text-5xl font-light leading-[1.04] tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-6xl">
        What <span className="text-[#1ec997]">moved the conversation</span> this week.
      </h1>
      <p className="mt-5 max-w-2xl text-[15px] leading-relaxed text-zinc-400">
        {stats.nuggets} quote-verified insights, ranked by signal and classified across{" "}
        {report.sections.length} sectors — distilled from {stats.episodes} episodes. Mark what
        matters, then{" "}
        <Link href="/report" className="text-[#1ec997] transition hover:text-[#34d6a8]">
          generate the report
        </Link>
        .
      </p>

      {/* stat row */}
      <div className="mt-12 flex flex-wrap gap-y-6">
        {tiles.map((t, i) => (
          <div key={t.label} className={`pr-10 ${i > 0 ? "border-l border-white/10 pl-10" : ""}`}>
            <div className="font-[family-name:var(--font-mono)] text-4xl font-medium tabular-nums text-[#1ec997]">
              {t.value}
            </div>
            <div className="mt-2 text-[11px] uppercase tracking-[0.18em] text-zinc-500">{t.label}</div>
          </div>
        ))}
      </div>

      {/* triage views */}
      <div className="mt-10 flex flex-wrap items-center gap-2">
        {VIEWS.map((v) => {
          const active = view === v.id;
          const count =
            v.id === "relevant"
              ? triageCounts.relevant ?? 0
              : v.id === "pending"
                ? triageCounts.pending ?? 0
                : undefined;
          return (
            <Link
              key={v.label}
              href={qs(v.id)}
              className={`rounded-full px-3.5 py-1.5 text-sm transition ${
                active
                  ? "bg-[#1ec997] font-medium text-[#06160f]"
                  : "border border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-100"
              }`}
            >
              {v.label}
              {count !== undefined ? <span className="opacity-60"> {count}</span> : null}
            </Link>
          );
        })}
      </div>

      {/* most-discussed screener */}
      {report.top_entities.length > 0 && (
        <div className="mt-12 rounded-2xl border border-white/[0.08] bg-[#0b0c10]/75 p-6 backdrop-blur-md">
          <p className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.2em] text-[#1ec997]">
            <span className="inline-block h-px w-6 bg-[#1ec997]" />
            Signal
            <span className="text-zinc-700">•</span>
            <span className="text-zinc-500">Most discussed across shows</span>
          </p>
          <div className="mt-6 space-y-2.5">
            {report.top_entities.slice(0, 10).map((e) => (
              <div key={e.name} className="flex items-center gap-4" title={e.shows.join(", ")}>
                <span className="w-40 shrink-0 truncate text-sm font-medium text-zinc-200">{e.name}</span>
                <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                  <div
                    className="h-full rounded-full bg-[#1ec997]/70"
                    style={{ width: `${(e.shows.length / maxShows) * 100}%` }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right font-[family-name:var(--font-mono)] text-xs tabular-nums text-zinc-500">
                  {e.shows.length} shows
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* section quick-nav */}
      {report.sections.length > 0 && (
        <nav className="mt-12 flex flex-wrap gap-x-4 gap-y-2 border-y border-white/[0.08] py-3 text-sm">
          {report.sections.map((s) => (
            <a
              key={s.sector}
              href={`#${anchorId(s.sector)}`}
              className="text-zinc-400 transition hover:text-[#1ec997]"
            >
              {s.sector} <span className="text-zinc-600">{s.count}</span>
            </a>
          ))}
        </nav>
      )}

      {/* sections */}
      <div className="mt-14 space-y-16">
        {report.sections.map((section, i) => (
          <section key={section.sector} id={anchorId(section.sector)} className="scroll-mt-20">
            <div className="mb-6 flex items-baseline justify-between border-b border-white/[0.08] pb-4">
              <div className="flex items-baseline gap-3">
                <span className="rounded-[5px] border border-[#1ec997]/40 px-1.5 py-1 font-[family-name:var(--font-mono)] text-[11px] leading-none text-[#1ec997]">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h2 className="text-2xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
                  {section.sector}
                </h2>
              </div>
              <span className="font-[family-name:var(--font-mono)] text-xs tabular-nums text-zinc-500">
                top {section.nuggets.length}
                {section.count > section.nuggets.length ? ` of ${section.count}` : ""}
              </span>
            </div>
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {section.nuggets.map((n) => (
                <NuggetCard key={n.id} n={n} />
              ))}
            </div>
          </section>
        ))}
      </div>

      {report.sections.length === 0 && (
        <p className="mt-14 rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 px-4 py-10 text-center text-zinc-500">
          No insights in this window yet. Run{" "}
          <code className="font-[family-name:var(--font-mono)] text-zinc-300">digest insights</code> first.
        </p>
      )}
    </div>
  );
}
