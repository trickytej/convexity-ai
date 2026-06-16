import { getNewsletter } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { NewsletterNugget, StockMention } from "@/lib/api";
import Link from "next/link";

export const dynamic = "force-dynamic";

const STANCE_STYLE: Record<string, { dot: string; label: string; text: string }> = {
  bullish:  { dot: "bg-emerald-400", label: "Bullish",  text: "text-emerald-400" },
  bearish:  { dot: "bg-amber-400",   label: "Bearish",  text: "text-amber-400"   },
  neutral:  { dot: "bg-zinc-500",    label: "Neutral",  text: "text-zinc-500"    },
  owned:    { dot: "bg-emerald-500", label: "Owned",    text: "text-emerald-400" },
  mentioned:{ dot: "bg-zinc-600",    label: "Mentioned",text: "text-zinc-600"    },
};

function StanceDot({ stance }: { stance: string }) {
  const s = STANCE_STYLE[stance] ?? STANCE_STYLE.neutral;
  return <span className={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${s.dot}`} />;
}

function SecuritiesRow({
  stock,
  nuggets,
}: {
  stock: StockMention;
  nuggets: NewsletterNugget[];
}) {
  const s = STANCE_STYLE[stock.stance] ?? STANCE_STYLE.neutral;

  return (
    <div className="grid grid-cols-[5rem_14rem_1fr] gap-x-6 gap-y-1 py-5 items-start border-b border-white/[0.05]">
      {/* ticker */}
      <div className="pt-0.5">
        <span className="font-[family-name:var(--font-mono)] text-sm font-medium text-zinc-300">
          {stock.tickers.length > 0 ? stock.tickers[0] : "—"}
        </span>
        {stock.tickers.length > 1 && (
          <span className="block font-[family-name:var(--font-mono)] text-[11px] text-zinc-600">
            {stock.tickers.slice(1).join(" ")}
          </span>
        )}
      </div>

      {/* company + stance */}
      <div className="flex items-start gap-2 pt-0.5">
        <StanceDot stance={stock.stance} />
        <div>
          <p className="text-sm font-medium text-zinc-100">{stock.company}</p>
          <p className={`text-[11px] font-medium ${s.text}`}>{s.label}</p>
        </div>
      </div>

      {/* nugget claims */}
      <div className="space-y-2.5">
        {nuggets.length > 0 ? (
          nuggets.map((n) => {
            const href = `/episode/${n.episode_id}${n.start_ms != null ? `#t-${n.start_ms}` : ""}`;
            return (
              <div key={n.id} className="flex items-start gap-2">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-zinc-600" />
                <p className="text-sm leading-snug text-zinc-300">
                  {n.claim}
                  <Link
                    href={href}
                    className="ml-2 text-[11px] text-[#00d4ff]/60 hover:text-[#00d4ff] transition-colors"
                  >
                    →
                  </Link>
                </p>
              </div>
            );
          })
        ) : stock.summary ? (
          <p className="text-sm leading-snug text-zinc-400">{stock.summary}</p>
        ) : null}
      </div>
    </div>
  );
}

export default async function SecuritiesPage() {
  const newsletter = await getNewsletter({});
  const { lead, good_to_know, stock_readthrough, from_date, to_date } = newsletter;
  const allNuggets = [...lead, ...good_to_know];

  // group nuggets by company name
  const nuggetsByCompany: Record<string, NewsletterNugget[]> = {};
  for (const n of allNuggets) {
    for (const company of n.companies ?? []) {
      if (!nuggetsByCompany[company]) nuggetsByCompany[company] = [];
      nuggetsByCompany[company].push(n);
    }
  }

  const coveredCompanies = new Set(stock_readthrough.map((s) => s.company));
  const uncoveredCompanies = Object.keys(nuggetsByCompany).filter(
    (c) => !coveredCompanies.has(c),
  );

  const isEmpty = stock_readthrough.length === 0 && uncoveredCompanies.length === 0;

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
        {stock_readthrough.length} securities classified by sentiment across curated nuggets.
      </p>

      {/* column headers */}
      {!isEmpty && (
        <div className="mt-10 grid grid-cols-[5rem_14rem_1fr] gap-x-6 border-b border-white/[0.08] pb-2 text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-600">
          <span>Ticker</span>
          <span>Company</span>
          <span>Insights</span>
        </div>
      )}

      {isEmpty && (
        <p className="mt-14 rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 px-4 py-10 text-center text-zinc-500">
          No securities data yet — mark nuggets as kept in the{" "}
          <Link href="/episodes" className="text-[#00d4ff]">
            Episodes
          </Link>{" "}
          tab first.
        </p>
      )}

      {/* main stock read-through */}
      {stock_readthrough.length > 0 && (
        <div>
          {stock_readthrough.map((stock) => (
            <SecuritiesRow
              key={stock.company}
              stock={stock}
              nuggets={nuggetsByCompany[stock.company] ?? []}
            />
          ))}
        </div>
      )}

      {/* companies mentioned in nuggets but not in readthrough */}
      {uncoveredCompanies.length > 0 && (
        <div className="mt-2">
          {uncoveredCompanies.map((company) => (
            <SecuritiesRow
              key={company}
              stock={{
                company,
                tickers: [],
                mention_count: nuggetsByCompany[company].length,
                nugget_ids: nuggetsByCompany[company].map((n) => n.id),
                stance: "mentioned",
                summary: "",
                source_episode_id: null,
                source_start_ms: null,
              }}
              nuggets={nuggetsByCompany[company]}
            />
          ))}
        </div>
      )}
    </div>
  );
}
