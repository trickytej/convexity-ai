import { getNewsletter } from "@/lib/api";
import type { NewsletterNugget } from "@/lib/api";
import Link from "next/link";

export const dynamic = "force-dynamic";

// ─── FMP types ──────────────────────────────────────────────────────────────

interface FmpQuote {
  price: number;
  changesPercentage: number;
  change: number;
  marketCap: number;
  eps: number;
  pe: number;
}

interface FmpIncomeStatement {
  date: string;
  period: string;
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
  estimatedEbitdaAvg: number;
}

// ─── FMP fetch helpers ───────────────────────────────────────────────────────

const FMP_BASE = "https://financialmodelingprep.com/api/v3";

async function fmpFetch<T>(path: string, key: string): Promise<T | null> {
  try {
    const res = await fetch(`${FMP_BASE}${path}&apikey=${key}`, {
      next: { revalidate: 300 }, // cache 5 min
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// ─── formatting helpers ──────────────────────────────────────────────────────

function fmtB(n: number | undefined | null): string {
  if (n == null) return "—";
  return `$${(n / 1e9).toFixed(2)}B`;
}

function fmtPct(n: number | undefined | null): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function fmtEps(n: number | undefined | null): string {
  if (n == null) return "—";
  return `$${n.toFixed(2)}`;
}

function fmtPrice(n: number): string {
  return `$${n.toFixed(2)}`;
}

function fmtChg(pct: number): string {
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function fmtPeriod(date: string): string {
  // "2025-02-27" → "FQ2'25"
  const d = new Date(date);
  const yr = String(d.getFullYear()).slice(2);
  const mo = d.getMonth() + 1; // 1-indexed
  // Micron FY: Q1=Sep-Nov, Q2=Dec-Feb, Q3=Mar-May, Q4=Jun-Aug
  let q = 1;
  if (mo >= 3 && mo <= 5) q = 3;
  else if (mo >= 6 && mo <= 8) q = 4;
  else if (mo >= 9 && mo <= 11) q = 1;
  else q = 2;
  return `FQ${q}'${yr}`;
}

// ─── sub-components ──────────────────────────────────────────────────────────

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
      className={`py-2.5 pr-6 text-right font-[family-name:var(--font-mono)] text-sm tabular-nums ${
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

function SectionRow({ label }: { label: string }) {
  return (
    <tr>
      <td
        colSpan={99}
        className="border-t border-white/[0.06] pb-1 pt-4 text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-600"
      >
        {label}
      </td>
    </tr>
  );
}

function NuggetChip({ n }: { n: NewsletterNugget }) {
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
        <Link
          href={href}
          className="ml-2 text-[#00d4ff]/50 transition-colors hover:text-[#00d4ff]"
        >
          →
        </Link>
      </p>
    </div>
  );
}

// ─── page ────────────────────────────────────────────────────────────────────

export default async function HubPage() {
  const fmpKey = process.env.FMP_API_KEY;

  // Always fetch MU nuggets from the local system
  const newsletter = await getNewsletter({}).catch(() => null);
  const muNuggets: NewsletterNugget[] = newsletter
    ? [...newsletter.lead, ...newsletter.good_to_know].filter((n) =>
        [...(n.companies ?? []), ...(n.tickers ?? [])].some((s) =>
          /micron|MU\b/i.test(s),
        ),
      )
    : [];

  // ── FMP data ──
  let quote: FmpQuote | null = null;
  let actuals: FmpIncomeStatement[] = [];
  let estimates: FmpAnalystEstimate[] = [];

  if (fmpKey) {
    const [quoteData, incomeData, estimateData] = await Promise.all([
      fmpFetch<FmpQuote[]>(`/quote/MU?`, fmpKey),
      fmpFetch<FmpIncomeStatement[]>(`/income-statement/MU?period=quarter&limit=6&`, fmpKey),
      fmpFetch<FmpAnalystEstimate[]>(
        `/analyst-estimates/MU?period=quarter&limit=4&`,
        fmpKey,
      ),
    ]);
    quote = quoteData?.[0] ?? null;
    actuals = incomeData ?? [];
    estimates = estimateData ?? [];
  }

  // Latest 3 historical quarters (most recent first from FMP)
  const hist = actuals.slice(0, 3).reverse(); // oldest → newest
  // Next 2 forward quarters from estimates (future-facing)
  const fwdEsts = estimates.slice(0, 2);

  // Price-implied EPS at a 15× multiple
  const priceImpliedEps15 = quote ? quote.price / 15 : null;

  // Guidance hardcoded (FQ4 FY25 — Micron's public guidance as of Jun 2025)
  const guidance = {
    label: "FQ4'25E (Guide)",
    revenue: 10.7e9,
    eps: 3.0,
  };

  const hasModel = hist.length > 0 || fwdEsts.length > 0;

  return (
    <div className="space-y-12">
      {/* ── masthead ── */}
      <div>
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]" />
          <span className="text-[#00d4ff]">Financial Model</span>
        </p>

        <div className="mt-4 flex flex-wrap items-end gap-6">
          <div>
            <h1 className="text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
              <span className="text-[#00d4ff]">MU</span> / Micron Technology
            </h1>
            <p className="mt-2 text-[15px] text-zinc-400">
              Revenue → EPS walk — historical actuals + forward estimates
            </p>
          </div>

          {quote && (
            <div className="mb-1 ml-auto text-right">
              <p className="text-3xl font-light tracking-tight text-zinc-50 [font-family:var(--font-mono)]">
                {fmtPrice(quote.price)}
              </p>
              <p
                className={`mt-0.5 text-sm font-medium ${
                  quote.changesPercentage >= 0 ? "text-emerald-400" : "text-rose-400"
                }`}
              >
                {fmtChg(quote.changesPercentage)}&nbsp;
                <span className="font-normal text-zinc-500">today</span>
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── no FMP key notice ── */}
      {!fmpKey && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-5 py-4 text-sm text-amber-300">
          Add <code className="font-mono text-amber-200">FMP_API_KEY</code> to{" "}
          <code className="font-mono text-amber-200">frontend/.env.local</code> to load live
          financial data from Financial Modeling Prep. Guidance is hardcoded below.
        </div>
      )}

      {/* ── model table ── */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-white/[0.08]">
              <th className="py-2.5 pr-6 text-left text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-600 w-40">
                Metric
              </th>
              {hist.map((q) => (
                <th
                  key={q.date}
                  className="py-2.5 pr-6 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-500"
                >
                  {fmtPeriod(q.date)}
                  <span className="ml-1 text-zinc-700">(A)</span>
                </th>
              ))}
              {!hasModel && (
                <>
                  <th className="py-2.5 pr-6 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-700">
                    FQ1'25 (A)
                  </th>
                  <th className="py-2.5 pr-6 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-700">
                    FQ2'25 (A)
                  </th>
                  <th className="py-2.5 pr-6 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-700">
                    FQ3'25 (A)
                  </th>
                </>
              )}
              <th className="py-2.5 pr-6 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-[#00d4ff]/70">
                {guidance.label}
              </th>
              {fwdEsts.slice(0, 1).map((e) => (
                <th
                  key={e.date}
                  className="py-2.5 pr-6 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-400"
                >
                  {fmtPeriod(e.date)}
                  <span className="ml-1 text-zinc-600">(Cons)</span>
                </th>
              ))}
              {!fwdEsts.length && (
                <th className="py-2.5 pr-6 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-700">
                  FQ4'25E (Cons)
                </th>
              )}
              <th className="py-2.5 pr-6 text-right text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-400">
                Price-impl
                <span className="ml-1 block text-[9px] normal-case tracking-normal text-zinc-600">
                  @ 15×
                </span>
              </th>
            </tr>
          </thead>

          <tbody>
            <SectionRow label="Revenue" />
            <tr className="border-b border-white/[0.04]">
              <td className="py-2.5 pr-6 text-sm text-zinc-400">Revenue</td>
              {hist.map((q) => (
                <ModelCell key={q.date} value={fmtB(q.revenue)} />
              ))}
              {!hasModel && (
                <>
                  <ModelCell value="$8.71B" dim />
                  <ModelCell value="$8.05B" dim />
                  <ModelCell value="$9.04B" dim />
                </>
              )}
              <ModelCell value={fmtB(guidance.revenue)} highlight />
              {fwdEsts.slice(0, 1).map((e) => (
                <ModelCell key={e.date} value={fmtB(e.estimatedRevenueAvg)} isEst />
              ))}
              {!fwdEsts.length && <ModelCell value="—" dim />}
              <ModelCell value="—" dim />
            </tr>

            <SectionRow label="Profitability" />
            <tr className="border-b border-white/[0.04]">
              <td className="py-2.5 pr-6 text-sm text-zinc-400">Gross Profit</td>
              {hist.map((q) => (
                <ModelCell key={q.date} value={fmtB(q.grossProfit)} />
              ))}
              {!hasModel && (
                <>
                  <ModelCell value="$3.66B" dim />
                  <ModelCell value="$2.99B" dim />
                  <ModelCell value="$3.98B" dim />
                </>
              )}
              <ModelCell value="—" dim />
              {fwdEsts.slice(0, 1).map((e) => (
                <ModelCell key={e.date} value="—" dim />
              ))}
              {!fwdEsts.length && <ModelCell value="—" dim />}
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-2.5 pr-6 text-sm text-zinc-400">Gross Margin</td>
              {hist.map((q) => (
                <ModelCell
                  key={q.date}
                  value={q.revenue ? fmtPct(q.grossProfit / q.revenue) : "—"}
                />
              ))}
              {!hasModel && (
                <>
                  <ModelCell value="42.0%" dim />
                  <ModelCell value="37.2%" dim />
                  <ModelCell value="44.1%" dim />
                </>
              )}
              <ModelCell value="~48%+" highlight />
              {fwdEsts.slice(0, 1).map((e) => (
                <ModelCell key={e.date} value="—" dim />
              ))}
              {!fwdEsts.length && <ModelCell value="—" dim />}
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-2.5 pr-6 text-sm text-zinc-400">Operating Income</td>
              {hist.map((q) => (
                <ModelCell key={q.date} value={fmtB(q.operatingIncome)} />
              ))}
              {!hasModel && (
                <>
                  <ModelCell value="$2.05B" dim />
                  <ModelCell value="$1.47B" dim />
                  <ModelCell value="$2.28B" dim />
                </>
              )}
              <ModelCell value="—" dim />
              {fwdEsts.slice(0, 1).map((e) => (
                <ModelCell key={e.date} value="—" dim />
              ))}
              {!fwdEsts.length && <ModelCell value="—" dim />}
              <ModelCell value="—" dim />
            </tr>

            <tr className="border-b border-white/[0.04]">
              <td className="py-2.5 pr-6 text-sm text-zinc-400">Net Income</td>
              {hist.map((q) => (
                <ModelCell key={q.date} value={fmtB(q.netIncome)} />
              ))}
              {!hasModel && (
                <>
                  <ModelCell value="$1.87B" dim />
                  <ModelCell value="$1.58B" dim />
                  <ModelCell value="$1.97B" dim />
                </>
              )}
              <ModelCell value="—" dim />
              {fwdEsts.slice(0, 1).map((e) => (
                <ModelCell key={e.date} value={fmtB(e.estimatedNetIncomeAvg)} isEst />
              ))}
              {!fwdEsts.length && <ModelCell value="—" dim />}
              <ModelCell value="—" dim />
            </tr>

            <SectionRow label="Per Share" />
            <tr>
              <td className="py-2.5 pr-6 text-sm font-medium text-zinc-200">EPS (diluted)</td>
              {hist.map((q) => (
                <ModelCell key={q.date} value={fmtEps(q.epsdiluted ?? q.eps)} />
              ))}
              {!hasModel && (
                <>
                  <ModelCell value="$1.79" dim />
                  <ModelCell value="$1.56" dim />
                  <ModelCell value="$1.91" dim />
                </>
              )}
              <ModelCell value={fmtEps(guidance.eps)} highlight />
              {fwdEsts.slice(0, 1).map((e) => (
                <ModelCell key={e.date} value={fmtEps(e.estimatedEpsAvg)} isEst />
              ))}
              {!fwdEsts.length && <ModelCell value="—" dim />}
              <ModelCell
                value={priceImpliedEps15 ? fmtEps(priceImpliedEps15) : "—"}
                highlight={!!priceImpliedEps15}
              />
            </tr>
          </tbody>
        </table>

        <p className="mt-3 text-[11px] text-zinc-600">
          (A) = reported actuals · (Cons) = street consensus · Guide = company guidance (hardcoded) · Price-impl = current
          price ÷ 15×
          {quote ? ` · Live price: ${fmtPrice(quote.price)}` : ""}
        </p>
      </div>

      {/* ── valuation context ── */}
      {quote && (
        <div className="grid gap-4 sm:grid-cols-3">
          {[
            { label: "Market cap", value: `$${(quote.marketCap / 1e9).toFixed(1)}B` },
            { label: "Trailing P/E", value: quote.pe ? `${quote.pe.toFixed(1)}×` : "—" },
            { label: "Trailing EPS", value: quote.eps ? fmtEps(quote.eps) : "—" },
          ].map(({ label, value }) => (
            <div
              key={label}
              className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 px-5 py-4"
            >
              <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-600">
                {label}
              </p>
              <p className="mt-1.5 text-2xl font-light tracking-tight text-zinc-100 [font-family:var(--font-mono)]">
                {value}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* ── related nuggets ── */}
      <div>
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]" />
          <span className="text-[#00d4ff]">MU insights from your library</span>
        </p>

        {muNuggets.length === 0 ? (
          <p className="mt-6 text-sm text-zinc-600">
            No kept nuggets mentioning Micron yet. Mark relevant nuggets as{" "}
            <Link href="/" className="text-[#00d4ff]">
              kept
            </Link>{" "}
            in the Episodes tab.
          </p>
        ) : (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {muNuggets.slice(0, 8).map((n) => (
              <NuggetChip key={n.id} n={n} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
