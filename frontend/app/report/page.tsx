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
      <div>
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]" />
          <span className="text-[#00d4ff]">Weekly Report</span>
        </p>
        <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
          Generate this week&apos;s report
        </h1>
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-zinc-400">
          A synthesized, sector-by-sector digest generated from this week&apos;s insights —
          condensed, with every point linking back to its source quote.
        </p>
        <div className="mt-7">
          <GenerateReportButton />
        </div>
        <p className="mt-4 text-xs text-zinc-500">
          Tip: mark insights “Relevant” on the{" "}
          <Link href="/insights" className="text-[#00d4ff] transition hover:text-[#33ddff]">
            Weekly insights
          </Link>{" "}
          page first to curate what the report covers (otherwise it uses the top insights by
          signal).
        </p>
      </div>
    );
  }

  return (
    <div>
      <header className="print:hidden">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
              <span className="inline-block h-px w-8 bg-[#00d4ff]" />
              <span className="text-[#00d4ff]">Weekly Report</span>
              <span className="text-zinc-700">•</span>
              <span className="text-zinc-500">
                {fmtDate(report.since)} – {fmtDate(report.until)}
              </span>
            </p>
            <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
              {report.week_key}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ReportActions report={report} />
            <GenerateReportButton label="Regenerate" />
          </div>
        </div>
        <p className="mt-3 text-xs text-zinc-500">
          Synthesized from{" "}
          {report.source_mode === "relevant"
            ? "your triaged-relevant insights"
            : "the top insights by signal"}{" "}
          · generated {fmtDate(report.generated_at)} · every point links to its source
        </p>
      </header>

      {/* the deliverable renders as a light sheet — looks premium on the dark canvas and exports cleanly */}
      <article className="mt-8 overflow-hidden rounded-2xl bg-white text-zinc-900 shadow-2xl shadow-black/30 ring-1 ring-white/10 print:mt-0 print:rounded-none print:shadow-none print:ring-0">
        <div className="space-y-8 p-8 sm:p-10">
          <div className="hidden print:block">
            <h1 className="text-2xl font-semibold tracking-tight">Weekly Report — {report.week_key}</h1>
            <p className="mt-1 text-sm text-zinc-500">
              {fmtDate(report.since)} – {fmtDate(report.until)}
            </p>
          </div>

          {report.exec_summary && (
            <section className="break-inside-avoid rounded-xl bg-teal-50 p-5 ring-1 ring-teal-100">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-teal-800">
                Executive summary
              </h2>
              <p className="leading-relaxed text-zinc-800">{report.exec_summary}</p>
            </section>
          )}

          {report.sections.map((s, i) => (
            <section
              key={s.sector}
              className={`break-inside-avoid ${i > 0 ? "border-t border-zinc-200 pt-7" : ""}`}
            >
              <div className="flex items-baseline gap-3">
                <span className="rounded-[5px] bg-teal-50 px-1.5 py-1 font-mono text-[11px] leading-none text-teal-700 ring-1 ring-inset ring-teal-200">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h2 className="text-xl font-semibold tracking-tight text-zinc-900">{s.sector}</h2>
              </div>
              <p className="mt-1.5 text-sm font-medium text-zinc-500">{s.headline}</p>

              <ul className="mt-4 space-y-3">
                {s.bullets.map((b, j) => (
                  <li key={j} className="text-[15px] leading-relaxed text-zinc-800">
                    <span className="mr-1.5 text-teal-500">•</span>
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
                    {s.watch_items.map((w, j) => (
                      <li key={j}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </section>
          ))}
        </div>
      </article>
    </div>
  );
}
