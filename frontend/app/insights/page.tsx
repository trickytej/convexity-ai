import Link from "next/link";
import { getNewsletter, getEpisodes } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import type { NewsletterNugget, StockMention } from "@/lib/api";
import { Badge } from "@/components/ui";
import RefreshFeedsButton from "@/components/RefreshFeedsButton";
import EpisodeWorkflowPanel from "@/components/EpisodeWorkflowPanel";

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

const TYPE_LABEL: Record<string, string> = { contrarian: "take" };

function typeLabel(t: string) {
  return TYPE_LABEL[t] ?? t.replace(/_/g, " ");
}

function KeptNuggetCard({ n }: { n: NewsletterNugget }) {
  const href = `/episode/${n.episode_id}${n.start_ms != null ? `#t-${n.start_ms}` : ""}`;
  return (
    <div className="group rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 p-4 transition hover:border-[#00d4ff]/30 hover:bg-[#0e1016]/85">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge tone={TYPE_TONE[n.type] ?? "zinc"}>{typeLabel(n.type)}</Badge>
        {n.curator_rank != null && (
          <Badge tone="amber">{"★".repeat(n.curator_rank)}</Badge>
        )}
        {(n.companies ?? []).slice(0, 3).map((c) => (
          <span
            key={c}
            className="rounded-full border border-[#00d4ff]/25 px-2 py-0.5 text-[11px] font-medium text-[#00d4ff]/80"
          >
            {c}
          </span>
        ))}
      </div>

      <p className="text-[15px] font-medium leading-snug text-zinc-100">{n.claim}</p>

      {n.quote && (
        <blockquote className="mt-2 border-l-2 border-[#00d4ff]/40 pl-3 text-sm italic leading-relaxed text-zinc-500">
          "{n.quote}"
        </blockquote>
      )}

      {n.curation_note && (
        <p className="mt-2 text-xs italic text-[#00d4ff]/70">{n.curation_note}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-500">
        <span className="min-w-0 truncate">
          {n.speaker_name ? (
            <span className="font-medium text-zinc-300">{n.speaker_name}</span>
          ) : null}
          {" · "}
          <span className="font-[family-name:var(--font-mono)]">{n.show_slug}</span>
          {" · "}
          {fmtDate(n.episode_published_at)}
        </span>
        <Link href={href} className="shrink-0 font-medium text-[#00d4ff] transition hover:text-[#33ddff]">
          in context →
        </Link>
      </div>
    </div>
  );
}

const STANCE_TONE: Record<string, "green" | "amber" | "zinc"> = {
  bullish: "green",
  bearish: "amber",
  neutral: "zinc",
};

function StockCard({ s }: { s: StockMention }) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 p-4 transition hover:border-[#00d4ff]/30 hover:bg-[#0e1016]/85">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-zinc-100">{s.company}</span>
        {s.tickers.length > 0 && (
          <span className="font-[family-name:var(--font-mono)] text-xs text-zinc-500">
            {s.tickers.join(" · ")}
          </span>
        )}
        <Badge tone={STANCE_TONE[s.stance] ?? "zinc"}>{s.stance}</Badge>
        <span className="ml-auto font-[family-name:var(--font-mono)] text-xs text-zinc-600">
          {s.mention_count} mention{s.mention_count !== 1 ? "s" : ""}
        </span>
      </div>
      <p className="text-sm leading-relaxed text-zinc-400">{s.summary}</p>
    </div>
  );
}

function SectionHeader({
  index,
  title,
  count,
}: {
  index: string;
  title: string;
  count: number;
}) {
  return (
    <div className="mb-6 flex items-baseline justify-between border-b border-white/[0.08] pb-4">
      <div className="flex items-baseline gap-3">
        <span className="rounded-[5px] border border-[#00d4ff]/40 px-1.5 py-1 font-[family-name:var(--font-mono)] text-[11px] leading-none text-[#00d4ff]">
          {index}
        </span>
        <h2 className="text-2xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
          {title}
        </h2>
      </div>
      <span className="font-[family-name:var(--font-mono)] text-xs tabular-nums text-zinc-500">
        {count}
      </span>
    </div>
  );
}

function defaultFrom() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}
function defaultTo() {
  return new Date().toISOString().slice(0, 10);
}

export default async function InsightsPage({
  searchParams,
}: {
  searchParams?: Promise<{ from?: string; to?: string }>;
}) {
  const params = await searchParams;
  const since = params?.from || defaultFrom();
  const until = params?.to || defaultTo();

  const [newsletter, episodeList] = await Promise.all([
    getNewsletter({ from: since, to: until }),
    getEpisodes({ since, until, limit: 200, all: true }),
  ]);
  const trackedEpisodes = episodeList.episodes.filter(e => e.show_slug !== "scout");
  const { lead, good_to_know, stock_readthrough, kept_count } =
    newsletter;

  return (
    <div>
      {/* masthead */}
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">Insights</span>
      </p>

      <h1 className="mt-5 max-w-3xl text-5xl font-light leading-[1.04] tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-6xl">
        Uncover narratives. Sharpen theses.<br /><span className="text-[#00d4ff]">Real time.</span>
      </h1>

      <p className="mt-4 max-w-2xl text-xl font-light text-zinc-300">
        Structured realtime insights integrated with your research.
      </p>

      {/* refresh feeds */}
      <div className="mt-12">
        <RefreshFeedsButton />
      </div>

      {/* episode list for date range */}
      <section className="mt-12 scroll-mt-20">
        <div className="mb-6 flex items-baseline justify-between border-b border-white/[0.08] pb-4">
          <div className="flex items-baseline gap-3">
            <span className="rounded-[5px] border border-[#00d4ff]/40 px-1.5 py-1 font-[family-name:var(--font-mono)] text-[11px] leading-none text-[#00d4ff]">
              00
            </span>
            <h2 className="text-2xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
              Episodes
            </h2>
          </div>
          <span className="font-[family-name:var(--font-mono)] text-xs tabular-nums text-zinc-500">
            {trackedEpisodes.length}
          </span>
        </div>
        <EpisodeWorkflowPanel
          episodes={trackedEpisodes}
          since={since}
          until={until}
        />
      </section>

      {/* lead */}
      {lead.length > 0 && (
        <section className="mt-14 scroll-mt-20">
          <SectionHeader index="01" title="Top Picks" count={lead.length} />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {lead.map((n) => (
              <KeptNuggetCard key={n.id} n={n} />
            ))}
          </div>
        </section>
      )}

      {/* good to know */}
      {good_to_know.length > 0 && (
        <section className="mt-16 scroll-mt-20">
          <SectionHeader index="02" title="Relevant Insights" count={good_to_know.length} />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {good_to_know.map((n) => (
              <KeptNuggetCard key={n.id} n={n} />
            ))}
          </div>
        </section>
      )}

      {/* stock read-through */}
      {stock_readthrough.length > 0 && (
        <section className="mt-16 scroll-mt-20">
          <SectionHeader index="03" title="Stock Read-Through" count={stock_readthrough.length} />
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {stock_readthrough.map((s) => (
              <StockCard key={s.company} s={s} />
            ))}
          </div>
        </section>
      )}

      {/* empty state */}
      {kept_count === 0 && (
        <p className="mt-14 rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 px-4 py-10 text-center text-zinc-500">
          No kept insights yet — review nuggets in the{" "}
          <Link href="/episodes" className="text-[#00d4ff]">
            Episodes
          </Link>{" "}
          tab and mark what matters.
        </p>
      )}
    </div>
  );
}
