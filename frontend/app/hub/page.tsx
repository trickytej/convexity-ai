import { getNewsletter } from "@/lib/api";
import type { NewsletterNugget } from "@/lib/api";
import { getSeries } from "@/lib/moves";
import MovesPanel from "@/components/MovesPanel";
import Link from "next/link";

export const dynamic = "force-dynamic";

// ─── ticker registry ─────────────────────────────────────────────────────────

const TICKERS = [
  { symbol: "MU",   name: "Micron Technology" },
  { symbol: "NVDA", name: "Nvidia" },
  { symbol: "AMD",  name: "AMD" },
  { symbol: "INTC", name: "Intel" },
  { symbol: "TSM",  name: "TSMC" },
];

// ─── FMP types ───────────────────────────────────────────────────────────────

interface FmpQuote {
  price: number;
  changesPercentage: number;
  marketCap: number;
  eps: number;
  pe: number;
}

interface FmpIncomeStatement {
  date: string;
  revenue: number;
  grossProfit: number;
  operatingIncome: number;
  netIncome: number;
  eps: number;
  epsdiluted: number;
}

interface FmpAnalystEstimate {
  date: string;
  estimatedRevenueAvg: number;
  estimatedEpsAvg: number;
  estimatedNetIncomeAvg: number;
}

// ─── FMP helpers ─────────────────────────────────────────────────────────────

const FMP_BASE = "https://financialmodelingprep.com/api/v3";

async function fmpFetch<T>(path: string, key: string): Promise<T | null> {
  try {
    const res = await fetch(`${FMP_BASE}${path}&apikey=${key}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ─── formatting ──────────────────────────────────────────────────────────────

const fmtB  = (n: number | null | undefined) => n == null ? "—" : `$${(n / 1e9).toFixed(2)}B`;
const fmtPct = (n: number | null | undefined) => n == null ? "—" : `${(n * 100).toFixed(1)}%`;
const fmtEps = (n: number | null | undefined) => n == null ? "—" : `$${n.toFixed(2)}`;
const fmtDelta = (n: number | null | undefined) =>
  n == null ? "—" : `${n >= 0 ? "+" : ""}${(n * 100).toFixed(1)}%`;

function pctChange(curr: number | null | undefined, prev: number | null | undefined): number | null {
  if (curr == null || prev == null || prev === 0) return null;
  return curr / prev - 1;
}

function fmtPeriod(date: string): string {
  const d = new Date(date);
  const yr = String(d.getFullYear()).slice(2);
  const mo = d.getMonth() + 1;
  let q = 2;
  if (mo >= 3 && mo <= 5) q = 3;
  else if (mo >= 6 && mo <= 8) q = 4;
  else if (mo >= 9 && mo <= 11) q = 1;
  return `FQ${q}'${yr}`;
}

// ─── sub-components ──────────────────────────────────────────────────────────

function TickerBar({ active }: { active?: string }) {
  return (
    <div className="flex flex-wrap gap-2">
      {TICKERS.map(({ symbol }) => {
        const isActive = symbol === active;
        return (
          <Link
            key={symbol}
            href={`/hub?ticker=${symbol}`}
            className={`rounded-lg border px-4 py-2 font-[family-name:var(--font-mono)] text-sm font-medium transition ${
              isActive
                ? "border-[#00d4ff] bg-[#00d4ff]/10 text-[#00d4ff]"
                : "border-white/[0.1] text-zinc-400 hover:border-white/20 hover:text-zinc-100"
            }`}
          >
            {symbol}
          </Link>
        );
      })}
    </div>
  );
}

function ModelCell({
  value,
  highlight = false,
  dim = false,
  isEst = false,
}: {
  value: string;
  highlight?: boolean;
  dim?: boolean;
  isEst?: boolean;
}) {
  return (
    <td
      className={`py-3 pr-8 text-right font-[family-name:var(--font-mono)] text-sm tabular-nums ${
        highlight
          ? "text-[#00d4ff]"
          : dim
            ? "text-zinc-600"
            : isEst
              ? "text-zinc-300"
              : "text-zinc-100"
      }`}
    >
      {value}
    </td>
  );
}

function SectionDivider({ label }: { label: string }) {
  return (
    <tr>
      <td
        colSpan={99}
        className="border-t border-white/[0.06] pb-1 pt-5 text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-600"
      >
        {label}
      </td>
    </tr>
  );
}

function NuggetCard({ n }: { n: NewsletterNugget }) {
  const href = `/episode/${n.episode_id}${n.start_ms != null ? `#t-${n.start_ms}` : ""}`;
  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/70 px-5 py-4">
      <p className="text-sm leading-snug text-zinc-200">{n.claim}</p>
      {n.quote && (
        <p className="mt-2 border-l-2 border-[#00d4ff]/30 pl-3 text-xs italic leading-relaxed text-zinc-400">
          {n.quote}
        </p>
      )}
      <p className="mt-3 text-[11px] text-zinc-600">
        {n.show_slug}&nbsp;·&nbsp;{n.episode_title}
        <Link href={href} className="ml-2 text-[#00d4ff]/50 hover:text-[#00d4ff]">→</Link>
      </p>
    </div>
  );
}

// ─── MU model (only shown when MU is selected) ───────────────────────────────

async function MuModel() {
  const fmpKey = process.env.FMP_API_KEY;

  const newsletter = await getNewsletter({}).catch(() => null);
  const muNuggets: NewsletterNugget[] = newsletter
    ? [...newsletter.lead, ...newsletter.good_to_know].filter((n) =>
        [...(n.companies ?? []), ...(n.tickers ?? [])].some((s) => /micron|MU\b/i.test(s)),
      )
    : [];

  let quote: FmpQuote | null = null;
  let actuals: FmpIncomeStatement[] = [];
  let estimates: FmpAnalystEstimate[] = [];

  if (fmpKey) {
    const [quoteData, incomeData, estimateData] = await Promise.all([
      fmpFetch<FmpQuote[]>(`/quote/MU?`, fmpKey),
      fmpFetch<FmpIncomeStatement[]>(`/income-statement/MU?period=quarter&limit=8&`, fmpKey),
      fmpFetch<FmpAnalystEstimate[]>(`/analyst-estimates/MU?period=quarter&limit=4&`, fmpKey),
    ]);
    quote = quoteData?.[0] ?? null;
    actuals = incomeData ?? [];
    estimates = estimateData ?? [];
  }

  const hist = actuals.slice(0, 3).reverse();
  const fwdEst = estimates[0] ?? null;

  // FQ4'25 company guidance (public as of Jun 2025)
  const guidance = { revenue: 10.7e9, eps: 3.0 };

  // Price-implied EPS at 15×
  const priceImpliedEps = quote ? quote.price / 15 : null;

  const hasLive = hist.length > 0;

  // Static fallback actuals (FQ1–FQ3 FY25)
  const fallback = [
    { label: "FQ1'25", revenue: 8.71e9, grossProfit: 3.66e9, operatingIncome: 2.05e9, netIncome: 1.87e9, epsdiluted: 1.79 },
    { label: "FQ2'25", revenue: 8.05e9, grossProfit: 2.99e9, operatingIncome: 1.47e9, netIncome: 1.58e9, epsdiluted: 1.56 },
    { label: "FQ3'25", revenue: 9.04e9, grossProfit: 3.98e9, operatingIncome: 2.28e9, netIncome: 1.97e9, epsdiluted: 1.91 },
  ];

  const histRows = hasLive ? hist : fallback;

  // qoq / yoy revenue deltas, aligned to histRows
  const qoqDeltas = hasLive
    ? hist.map((r, i) => pctChange(r.revenue, i === 0 ? actuals[3]?.revenue : hist[i - 1].revenue))
    : fallback.map((r, i) => pctChange(r.revenue, i === 0 ? null : fallback[i - 1].revenue));
  const yoyDeltas = hasLive
    ? hist.map((r, i) => pctChange(r.revenue, actuals[6 - i]?.revenue))
    : fallback.map(() => null);

  return (
    <div className="space-y-10">
      {/* header */}
      <div className="flex flex-wrap items-end gap-6">
        <div>
          <h1 className="text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
            <span className="text-[#00d4ff]">MU</span>
            <span className="ml-3 text-zinc-400">/ Micron Technology</span>
          </h1>
          <p className="mt-2 text-[15px] text-zinc-500">Revenue → EPS walk</p>
        </div>

        {quote && (
          <div className="ml-auto text-right">
            <p className="text-3xl font-light tracking-tight text-zinc-50 [font-family:var(--font-mono)]">
              ${quote.price.toFixed(2)}
            </p>
            <p
              className={`mt-0.5 text-sm font-medium ${
                quote.changesPercentage >= 0 ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {quote.changesPercentage >= 0 ? "+" : ""}
              {quote.changesPercentage.toFixed(2)}%
              <span className="ml-1.5 font-normal text-zinc-600">today</span>
            </p>
          </div>
        )}
      </div>

      {/* model table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-white/[0.08]">
              <th className="w-44 py-3 pr-8 text-left text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-600" />
              {hasLive
                ? hist.map((q) => (
                    <th key={q.date} className="py-3 pr-8 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-500">
                      {fmtPeriod(q.date)}<span className="ml-1 text-zinc-700">(A)</span>
                    </th>
                  ))
                : fallback.map((f) => (
                    <th key={f.label} className="py-3 pr-8 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-600">
                      {f.label}<span className="ml-1 text-zinc-700">(A)</span>
                    </th>
                  ))}
              <th className="py-3 pr-8 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-[#00d4ff]/70">
                FQ4&apos;25E
                <span className="ml-1 block text-[9px] normal-case tracking-normal text-[#00d4ff]/40">Guide</span>
              </th>
              <th className="py-3 pr-8 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-400">
                {fwdEst ? fmtPeriod(fwdEst.date) : "FQ4'25E"}
                <span className="ml-1 block text-[9px] normal-case tracking-normal text-zinc-600">Consensus</span>
              </th>
              <th className="py-3 pr-8 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-400">
                Price-impl
                <span className="ml-1 block text-[9px] normal-case tracking-normal text-zinc-600">@ 15×</span>
              </th>
            </tr>
          </thead>

          <tbody>
            <SectionDivider label="Revenue" />
            <tr className="border-b border-white/[0.04]">
              <td className="py-3 pr-8 text-sm text-zinc-400">Revenue</td>
              {(hasLive ? hist : fallback).map((r, i) => (
                <ModelCell key={i} value={fmtB("revenue" in r ? r.revenue : (r as typeof fallback[0]).revenue)} />
              ))}
              <ModelCell value={fmtB(guidance.revenue)} highlight />
              <ModelCell value={fwdEst ? fmtB(fwdEst.estimatedRevenueAvg) : "—"} isEst />
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-3 pr-8 text-xs text-zinc-600">qoq</td>
              {qoqDeltas.map((d, i) => (
                <ModelCell key={i} value={fmtDelta(d)} dim />
              ))}
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-3 pr-8 text-xs text-zinc-600">yoy</td>
              {yoyDeltas.map((d, i) => (
                <ModelCell key={i} value={fmtDelta(d)} dim />
              ))}
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
            </tr>

            <SectionDivider label="Profitability" />
            <tr className="border-b border-white/[0.04]">
              <td className="py-3 pr-8 text-sm text-zinc-400">Gross Profit</td>
              {(hasLive ? hist : fallback).map((r, i) => (
                <ModelCell key={i} value={fmtB(r.grossProfit)} />
              ))}
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-3 pr-8 text-xs text-zinc-600">GPM %</td>
              {(hasLive ? hist : fallback).map((r, i) => (
                <ModelCell
                  key={i}
                  value={r.revenue ? fmtPct(r.grossProfit / r.revenue) : "—"}
                  dim
                />
              ))}
              <ModelCell value="~48%+" highlight />
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-3 pr-8 text-sm text-zinc-400">Operating Profit</td>
              {(hasLive ? hist : fallback).map((r, i) => (
                <ModelCell key={i} value={fmtB(r.operatingIncome)} />
              ))}
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-3 pr-8 text-xs text-zinc-600">OPM %</td>
              {(hasLive ? hist : fallback).map((r, i) => (
                <ModelCell
                  key={i}
                  value={r.revenue ? fmtPct(r.operatingIncome / r.revenue) : "—"}
                  dim
                />
              ))}
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-3 pr-8 text-sm text-zinc-400">Net Income</td>
              {(hasLive ? hist : fallback).map((r, i) => (
                <ModelCell key={i} value={fmtB(r.netIncome)} />
              ))}
              <ModelCell value="—" dim />
              <ModelCell value={fwdEst ? fmtB(fwdEst.estimatedNetIncomeAvg) : "—"} isEst />
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-3 pr-8 text-xs text-zinc-600">NPM %</td>
              {(hasLive ? hist : fallback).map((r, i) => (
                <ModelCell
                  key={i}
                  value={r.revenue ? fmtPct(r.netIncome / r.revenue) : "—"}
                  dim
                />
              ))}
              <ModelCell value="—" dim />
              <ModelCell
                value={fwdEst ? fmtPct(fwdEst.estimatedNetIncomeAvg / fwdEst.estimatedRevenueAvg) : "—"}
                dim
              />
              <ModelCell value="—" dim />
            </tr>

            <SectionDivider label="Per Share" />
            <tr>
              <td className="py-3 pr-8 text-sm font-medium text-zinc-200">EPS (diluted)</td>
              {(hasLive ? hist : fallback).map((r, i) => (
                <ModelCell key={i} value={fmtEps("date" in r ? (r.epsdiluted ?? r.eps) : r.epsdiluted)} />
              ))}
              <ModelCell value={fmtEps(guidance.eps)} highlight />
              <ModelCell value={fwdEst ? fmtEps(fwdEst.estimatedEpsAvg) : "—"} isEst />
              <ModelCell value={priceImpliedEps ? fmtEps(priceImpliedEps) : "—"} highlight={!!priceImpliedEps} />
            </tr>
          </tbody>
        </table>

        <p className="mt-3 text-[11px] text-zinc-600">
          (A) = actuals&ensp;·&ensp;Guide = company guidance (hardcoded FQ4 FY25)&ensp;·&ensp;Price-impl = live price ÷ 15×
          {quote ? `&ensp;·&ensp;Live: $${quote.price.toFixed(2)}` : ""}
        </p>
      </div>

      {/* valuation chips */}
      {quote && (
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            { label: "Market cap",   value: `$${(quote.marketCap / 1e9).toFixed(1)}B` },
            { label: "Trailing P/E", value: quote.pe ? `${quote.pe.toFixed(1)}×` : "—" },
            { label: "Trailing EPS", value: quote.eps ? fmtEps(quote.eps) : "—" },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 px-5 py-4">
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-600">{label}</p>
              <p className="mt-1.5 text-2xl font-light tracking-tight text-zinc-100 [font-family:var(--font-mono)]">
                {value}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* related nuggets */}
      <div>
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]" />
          <span className="text-[#00d4ff]">MU insights from your library</span>
        </p>
        {muNuggets.length === 0 ? (
          <p className="mt-5 text-sm text-zinc-600">
            No kept nuggets mentioning Micron yet — mark relevant ones in the{" "}
            <Link href="/podcasts" className="text-[#00d4ff]">Episodes</Link> tab.
          </p>
        ) : (
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {muNuggets.slice(0, 8).map((n) => (
              <NuggetCard key={n.id} n={n} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

export default async function HubPage({
  searchParams,
}: {
  searchParams: Promise<{ ticker?: string }>;
}) {
  const { ticker } = await searchParams;
  const series = ticker ? await getSeries(ticker, { days: 730, threshold: 0.07 }) : null;
  const meta = TICKERS.find((t) => t.symbol === ticker);

  return (
    <div className="space-y-8">
      {/* ticker bar — always visible */}
      <div>
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]" />
          <span className="text-[#00d4ff]">Hub</span>
        </p>
        <div className="mt-5">
          <TickerBar active={ticker} />
        </div>
      </div>

      {!ticker ? (
        <div className="flex min-h-[55vh] flex-col items-center justify-center text-center">
          <p className="text-2xl font-light tracking-tight text-zinc-600 [font-family:var(--font-display)]">
            Select a security to begin
          </p>
          <p className="mt-3 text-sm text-zinc-700">
            Choose a ticker above to load the financial model and market‑moving events.
          </p>
        </div>
      ) : (
        <div className="space-y-12">
          {ticker === "MU" ? (
            <MuModel />
          ) : (
            <div className="flex flex-wrap items-end gap-6">
              <h1 className="text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
                <span className="text-[#00d4ff]">{ticker}</span>
                {meta && <span className="ml-3 text-zinc-400">/ {meta.name}</span>}
              </h1>
            </div>
          )}
          <MovesPanel series={series} symbol={ticker} />
        </div>
      )}
    </div>
  );
}
