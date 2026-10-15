import Link from "next/link";
import { auth } from "@/auth";
import { getBrief } from "@/lib/api";
import { HitList } from "@/components/signals";
import DateRangeFilter from "@/components/DateRangeFilter";
import { Badge } from "@/components/ui";

export const dynamic = "force-dynamic";

const WINDOWS = [
  { days: 1, label: "24h" },
  { days: 3, label: "3d" },
  { days: 7, label: "7d" },
  { days: 30, label: "30d" },
];

const isoDay = (d: Date) => d.toISOString().slice(0, 10);

export default async function BriefPage({
  searchParams,
}: {
  searchParams?: Promise<{ days?: string; from?: string; to?: string }>;
}) {
  const params = await searchParams;
  // A custom From/To range wins over the quick windows; dates are when the
  // source was published.
  const custom = !!(params?.from || params?.to);
  const days = custom ? 0 : Math.max(1, Math.min(365, Number(params?.days) || 7));
  const from = params?.from || isoDay(new Date(Date.now() - (days || 7) * 86_400_000));
  const to = params?.to || isoDay(new Date());
  const [brief, session] = await Promise.all([
    getBrief(custom ? { since: from, until: to, status: "pending" } : { days, status: "pending" }),
    auth(),
  ]);
  const isAdmin = !!session?.user?.isAdmin;
  const totalHits = brief.companies.reduce((s, c) => s + c.hit_count, 0);
  const totalSignals = brief.companies.reduce((s, c) => s + c.signal_count, 0);

  return (
    <div>
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">Brief</span>
      </p>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
          What moved <span className="text-[#00d4ff]">your questions</span>
        </h1>
        <Link
          href="/model"
          className="rounded-full border border-white/[0.1] px-3.5 py-1.5 text-[12px] font-medium text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff]"
        >
          Your securities
        </Link>
      </div>

      <div className="mt-6 flex flex-wrap items-end gap-x-6 gap-y-4">
      <div className="flex items-center gap-2">
        {WINDOWS.map((w) => (
          <Link
            key={w.days}
            href={`/brief?days=${w.days}`}
            className={`rounded-full border px-3 py-1 text-[12px] transition ${
              days === w.days
                ? "border-[#00d4ff]/40 bg-[#00d4ff]/8 text-[#00d4ff]"
                : "border-white/[0.06] text-zinc-500 hover:border-white/[0.14] hover:text-zinc-300"
            }`}
          >
            {w.label}
          </Link>
        ))}
      </div>
      <DateRangeFilter basePath="/brief" initialFrom={from} initialTo={to} />
        <span className="font-[family-name:var(--font-mono)] text-xs tabular-nums text-zinc-600">
          {totalSignals} signal{totalSignals === 1 ? "" : "s"} · {totalHits - totalSignals} reference
        </span>
      </div>

      {brief.companies.length === 0 && (
        <div className="mt-14 max-w-xl">
          <p className="text-[15px] leading-relaxed text-zinc-400">
            Nothing left to review in this window.
          </p>
          <p className="mt-3 text-[13px] leading-relaxed text-zinc-600">
            No questions yet? Pick the securities you follow on the{" "}
            <Link href="/model" className="text-[#00d4ff] transition hover:text-[#33ddff]">
              Model page
            </Link>{" "}
            and write the 4–5 questions that matter for each. Every new podcast
            insight, newsletter, and X post gets weighed against them, and what you
            keep builds each security&apos;s tracker.
          </p>
        </div>
      )}

      <div className="mt-10 space-y-12">
        {brief.companies.map((c) => (
          <section
            key={c.company}
            id={`company-${c.company.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`}
            className="scroll-mt-20"
          >
            <div className="mb-5 flex items-baseline gap-3 border-b border-white/[0.08] pb-3">
              <Link
                href={`/model/${encodeURIComponent(c.ticker || c.company.toLowerCase().replace(/[^a-z0-9]+/g, "-"))}`}
                className="text-2xl font-light tracking-tight text-zinc-50 transition [font-family:var(--font-display)] hover:text-[#00d4ff]"
              >
                {c.company}
              </Link>
              {c.ticker && (
                <span className="font-[family-name:var(--font-mono)] text-xs text-zinc-500">
                  {c.ticker}
                </span>
              )}
              <span className="ml-auto">
                <Badge tone="indigo">
                  {c.signal_count} signal{c.signal_count === 1 ? "" : "s"}
                </Badge>
              </span>
            </div>
            <div className="space-y-8">
              {c.questions.map((q) => (
                <div key={q.question_id}>
                  <p className="text-[15px] font-medium leading-snug text-zinc-200">
                    {q.question}
                  </p>
                  {q.note && (
                    <p className="mt-1 text-[12px] leading-relaxed text-zinc-600">{q.note}</p>
                  )}
                  <HitList hits={q.hits} sourceLinks={isAdmin} />
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
