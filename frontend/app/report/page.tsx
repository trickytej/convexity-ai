import Link from "next/link";
import type { ReportSource } from "@/lib/api";
import { getLatestReport } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { GenerateReportButton } from "@/components/GenerateReportButton";
import { ReportActions } from "@/components/ReportActions";

export const dynamic = "force-dynamic";

function srcHref(s: ReportSource): string {
  return `/episode/${s.episode_id}${s.start_ms != null ? `#t-${s.start_ms}` : ""}`;
}

export default async function ReportPage() {
  const report = await getLatestReport();

  if (!report) {
    return (
      <div className="space-y-5">
        <h1 className="text-2xl font-semibold tracking-tight">Weekly report</h1>
        <p className="max-w-2xl text-zinc-600">
          A synthesized, sector-by-sector digest generated from this week&apos;s insights —
          condensed, with every point linking back to its source quote.
        </p>
        <GenerateReportButton />
        <p className="text-xs text-zinc-400">
          Tip: mark insights “Relevant” on the{" "}
          <Link href="/insights" className="text-indigo-600 hover:text-indigo-800">
            Weekly insights
          </Link>{" "}
          page first to curate what the report covers (otherwise it uses the top insights by
          signal).
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Weekly report</h1>
            <p className="mt-1 text-zinc-600">
              {fmtDate(report.since)} – {fmtDate(report.until)} · {report.week_key}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 print:hidden">
            <ReportActions report={report} />
            <GenerateReportButton label="Regenerate" />
          </div>
        </div>
        <p className="text-xs text-zinc-400">
          Synthesized from{" "}
          {report.source_mode === "relevant"
            ? "your triaged-relevant insights"
            : "the top insights by signal"}{" "}
          · generated {fmtDate(report.generated_at)} · every point links to its source
        </p>
      </header>

      {report.exec_summary && (
        <section className="break-inside-avoid rounded-xl border border-indigo-100 bg-indigo-50/60 p-5">
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-indigo-700">
            Executive summary
          </h2>
          <p className="leading-relaxed text-zinc-800">{report.exec_summary}</p>
        </section>
      )}

      {report.sections.map((s) => (
        <section key={s.sector} className="break-inside-avoid rounded-xl border border-zinc-200 bg-white p-5">
          <h2 className="text-lg font-semibold tracking-tight">{s.sector}</h2>
          <p className="mt-0.5 text-sm font-medium text-zinc-500">{s.headline}</p>

          <ul className="mt-4 space-y-3">
            {s.bullets.map((b, i) => (
              <li key={i} className="text-[15px] leading-relaxed text-zinc-800">
                <span className="mr-1.5 text-indigo-400">•</span>
                {b.text}
                {b.sources.length > 0 && (
                  <span className="ml-1.5 inline-flex flex-wrap gap-1 align-baseline">
                    {b.sources.map((src) => (
                      <Link
                        key={src.nugget_id}
                        href={srcHref(src)}
                        title={`${src.speaker_name ?? ""} · ${src.show_slug}`}
                        className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-500 ring-1 ring-inset ring-zinc-200 hover:bg-zinc-200 hover:text-zinc-700"
                      >
                        {src.show_slug}
                      </Link>
                    ))}
                  </span>
                )}
              </li>
            ))}
          </ul>

          {s.watch_items.length > 0 && (
            <div className="mt-4 border-t border-zinc-100 pt-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Watch</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-zinc-600">
                {s.watch_items.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </section>
      ))}
    </div>
  );
}
