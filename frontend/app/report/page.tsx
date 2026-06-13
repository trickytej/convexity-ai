import Link from "next/link";
import { getReport } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { Badge } from "@/components/ui";
import { NuggetCard } from "@/components/NuggetCard";

export const dynamic = "force-dynamic";

const PER_SECTION = 15;

function anchorId(sector: string): string {
  return "sec-" + sector.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

export default async function ReportPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const { days } = await searchParams;
  const window = days ? Math.max(1, parseInt(days, 10) || 7) : 7;
  const report = await getReport(window, PER_SECTION);
  const { stats } = report;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Weekly report</h1>
        <p className="mt-1 text-zinc-600">
          {fmtDate(report.since)} – {fmtDate(report.until)} · {stats.nuggets} insights from{" "}
          {stats.episodes} episodes across {stats.shows} shows
        </p>
        <p className="mt-1 text-xs text-zinc-400">
          {stats.verified} quote-verified · ranked by signal · every insight links to its source
        </p>
      </header>

      {report.top_entities.length > 0 && (
        <section className="rounded-xl border border-zinc-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Most-discussed companies (across shows)
          </h2>
          <div className="flex flex-wrap gap-2">
            {report.top_entities.map((e) => (
              <span
                key={e.name}
                className="inline-flex items-center gap-1.5 rounded-full bg-zinc-100 px-3 py-1 text-sm ring-1 ring-inset ring-zinc-200"
                title={e.shows.join(", ")}
              >
                <span className="font-medium text-zinc-900">{e.name}</span>
                <span className="text-zinc-500">{e.shows.length} shows</span>
              </span>
            ))}
          </div>
        </section>
      )}

      <nav className="flex flex-wrap gap-2 border-y border-zinc-200 py-3 text-sm">
        {report.sections.map((s) => (
          <a key={s.sector} href={`#${anchorId(s.sector)}`} className="text-indigo-600 hover:text-indigo-800">
            {s.sector} <span className="text-zinc-400">{s.count}</span>
          </a>
        ))}
      </nav>

      {report.sections.map((section) => (
        <section key={section.sector} id={anchorId(section.sector)} className="scroll-mt-20">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="text-lg font-semibold tracking-tight">{section.sector}</h2>
            <span className="text-sm text-zinc-500">
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

      {report.sections.length === 0 && (
        <p className="rounded-xl border border-zinc-200 bg-white px-4 py-8 text-center text-zinc-500">
          No insights in this window yet. Run <code>digest insights</code> first.
        </p>
      )}
    </div>
  );
}
