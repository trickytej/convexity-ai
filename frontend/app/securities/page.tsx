import { getNewsletter } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { NewsletterNugget, StockMention } from "@/lib/api";
import { Badge } from "@/components/ui";
import Link from "next/link";

export const dynamic = "force-dynamic";

const TYPE_TONE: Record<string, "zinc" | "green" | "blue" | "amber" | "indigo"> = {
  thesis: "indigo",
  prediction: "amber",
  data_point: "blue",
  company_move: "green",
  contrarian: "amber",
  mental_model: "zinc",
  watch_item: "zinc",
};

function typeLabel(t: string) {
  const overrides: Record<string, string> = { contrarian: "take" };
  return overrides[t] ?? t.replace(/_/g, " ");
}

const STANCE_STYLE: Record<string, { badge: "green" | "amber" | "zinc"; label: string; bar: string }> = {
  bullish:  { badge: "green", label: "Bullish",  bar: "bg-emerald-500" },
  bearish:  { badge: "amber", label: "Bearish",  bar: "bg-amber-500"   },
  neutral:  { badge: "zinc",  label: "Neutral",  bar: "bg-zinc-500"    },
  owned:    { badge: "green", label: "Owned",    bar: "bg-emerald-600" },
  mentioned:{ badge: "zinc",  label: "Mentioned",bar: "bg-zinc-600"    },
};

function StanceBar({ stance }: { stance: string }) {
  const s = STANCE_STYLE[stance] ?? STANCE_STYLE.neutral;
  return (
    <span className={`inline-block h-3 w-1.5 rounded-full ${s.bar}`} />
  );
}

function NuggetRow({ n }: { n: NewsletterNugget }) {
  const href = `/episode/${n.episode_id}${n.start_ms != null ? `#t-${n.start_ms}` : ""}`;
  return (
    <div className="border-l-2 border-white/[0.08] pl-4 py-1">
      <div className="flex flex-wrap items-center gap-2 mb-1">
        <Badge tone={TYPE_TONE[n.type] ?? "zinc"}>{typeLabel(n.type)}</Badge>
        {n.curator_rank != null && (
          <Badge tone="amber">{"★".repeat(n.curator_rank)}</Badge>
        )}
      </div>
      <p className="text-sm font-medium leading-snug text-zinc-100">{n.claim}</p>
      {n.quote && (
        <blockquote className="mt-1 border-l-2 border-[#00d4ff]/30 pl-3 text-xs italic leading-relaxed text-zinc-500">
          "{n.quote}"
        </blockquote>
      )}
      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
        {n.speaker_name && <span className="font-medium text-zinc-400">{n.speaker_name}</span>}
        <span className="font-[family-name:var(--font-mono)]">{n.show_slug}</span>
        <span>·</span>
        <span>{fmtDate(n.episode_published_at)}</span>
        <Link href={href} className="ml-auto text-[#00d4ff] hover:text-[#33ddff]">
          in context →
        </Link>
      </div>
    </div>
  );
}

function SecurityCard({
  stock,
  nuggets,
}: {
  stock: StockMention;
  nuggets: NewsletterNugget[];
}) {
  const s = STANCE_STYLE[stock.stance] ?? STANCE_STYLE.neutral;

  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 p-5 transition hover:border-[#00d4ff]/20">
      {/* company header */}
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <StanceBar stance={stock.stance} />
          <div>
            <h2 className="text-lg font-semibold text-zinc-50">{stock.company}</h2>
            {stock.tickers.length > 0 && (
              <span className="font-[family-name:var(--font-mono)] text-xs text-zinc-500">
                {stock.tickers.join(" · ")}
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={s.badge}>{s.label}</Badge>
          <span className="font-[family-name:var(--font-mono)] text-xs text-zinc-600">
            {stock.mention_count} mention{stock.mention_count !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* AI summary */}
      {stock.summary && (
        <p className="mb-4 text-sm leading-relaxed text-zinc-400 border-b border-white/[0.06] pb-4">
          {stock.summary}
        </p>
      )}

      {/* nuggets */}
      {nuggets.length > 0 && (
        <div className="space-y-4">
          {nuggets.map((n) => (
            <NuggetRow key={n.id} n={n} />
          ))}
        </div>
      )}
    </div>
  );
}

export default async function SecuritiesPage() {
  const newsletter = await getNewsletter({});
  const { lead, good_to_know, stock_readthrough, from_date, to_date } = newsletter;
  const allNuggets = [...lead, ...good_to_know];

  // Map each stock to its nuggets
  const nuggetsByCompany: Record<string, NewsletterNugget[]> = {};
  for (const n of allNuggets) {
    for (const company of n.companies ?? []) {
      if (!nuggetsByCompany[company]) nuggetsByCompany[company] = [];
      nuggetsByCompany[company].push(n);
    }
  }

  // Stocks without a StockMention entry (mentioned in nuggets but not in readthrough)
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
        {stock_readthrough.length} securities mentioned across curated nuggets — classified by
        overall sentiment.
      </p>

      {/* stance legend */}
      <div className="mt-8 flex flex-wrap gap-4 text-xs text-zinc-500">
        {(["bullish", "bearish", "neutral"] as const).map((stance) => (
          <span key={stance} className="flex items-center gap-1.5">
            <StanceBar stance={stance} />
            {STANCE_STYLE[stance].label}
          </span>
        ))}
      </div>

      {isEmpty && (
        <p className="mt-14 rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 px-4 py-10 text-center text-zinc-500">
          No securities data yet — mark nuggets as kept in the{" "}
          <Link href="/episodes" className="text-[#00d4ff]">
            Episodes
          </Link>{" "}
          tab first.
        </p>
      )}

      {/* stocks with readthrough */}
      {stock_readthrough.length > 0 && (
        <div className="mt-12 space-y-5">
          {stock_readthrough.map((stock) => (
            <SecurityCard
              key={stock.company}
              stock={stock}
              nuggets={nuggetsByCompany[stock.company] ?? []}
            />
          ))}
        </div>
      )}

      {/* nuggets mentioning companies not in readthrough */}
      {uncoveredCompanies.length > 0 && (
        <div className="mt-12 space-y-5">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-600">
            Also mentioned
          </p>
          {uncoveredCompanies.map((company) => (
            <SecurityCard
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
