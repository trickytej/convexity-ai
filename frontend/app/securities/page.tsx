import { getNewsletter } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { NewsletterNugget } from "@/lib/api";
import Link from "next/link";
import SecuritiesTable from "@/components/SecuritiesTable";
import DateRangeFilter from "@/components/DateRangeFilter";

export const dynamic = "force-dynamic";

function defaultFrom() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}
function defaultTo() {
  return new Date().toISOString().slice(0, 10);
}

export default async function SecuritiesPage({
  searchParams,
}: {
  searchParams?: Promise<{ from?: string; to?: string }>;
}) {
  const params = await searchParams;
  const since = params?.from || defaultFrom();
  const until = params?.to || defaultTo();

  const newsletter = await getNewsletter({ from: since, to: until });
  const { lead, good_to_know, stock_readthrough, from_date, to_date } = newsletter;
  const allNuggets = [...lead, ...good_to_know];

  // group nuggets by company
  const nuggetsByCompany: Record<string, NewsletterNugget[]> = {};
  for (const n of allNuggets) {
    for (const company of n.companies ?? []) {
      if (!nuggetsByCompany[company]) nuggetsByCompany[company] = [];
      nuggetsByCompany[company].push(n);
    }
  }

  // companies mentioned in nuggets but missing from stock_readthrough
  const coveredCompanies = new Set(stock_readthrough.map((s) => s.company));
  const uncoveredCompanies = Object.keys(nuggetsByCompany).filter(
    (c) => !coveredCompanies.has(c),
  );

  // merge into one list
  const allStocks = [
    ...stock_readthrough,
    ...uncoveredCompanies.map((company) => ({
      company,
      tickers: [] as string[],
      mention_count: nuggetsByCompany[company].length,
      nugget_ids: nuggetsByCompany[company].map((n) => n.id),
      stance: "mentioned",
      summary: "",
      source_episode_id: null as null,
      source_start_ms: null as null,
    })),
  ];

  const isEmpty = allStocks.length === 0;

  return (
    <div>
      {/* masthead */}
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">Securities</span>
        {(from_date || to_date) && (
          <>
            <span className="text-zinc-700">•</span>
            <span className="text-zinc-500">
              {fmtDate(from_date)} – {fmtDate(to_date)}
            </span>
          </>
        )}
      </p>

      <h1 className="mt-5 max-w-3xl text-5xl font-light leading-[1.04] tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-6xl">
        Stock <span className="text-[#00d4ff]">read-through</span> from kept insights.
      </h1>

      <p className="mt-5 max-w-2xl text-[15px] leading-relaxed text-zinc-400">
        {allStocks.length} securities classified by sentiment across curated nuggets.
      </p>

      <div className="mt-7">
        <DateRangeFilter basePath="/securities" initialFrom={since} initialTo={until} />
      </div>

      <div className="mt-10">
        {isEmpty ? (
          <p className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 px-4 py-10 text-center text-zinc-500">
            No securities data yet — mark nuggets as kept in the{" "}
            <Link href="/episodes" className="text-[#00d4ff]">
              Episodes
            </Link>{" "}
            tab first.
          </p>
        ) : (
          <SecuritiesTable stocks={allStocks} nuggetsByCompany={nuggetsByCompany} />
        )}
      </div>
    </div>
  );
}
