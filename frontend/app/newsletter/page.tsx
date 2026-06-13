"use client";

import { useState } from "react";
import Link from "next/link";
import type { Newsletter, NewsletterNugget, StockMention } from "@/lib/api";
import { getNewsletter } from "@/lib/api";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}
function weekAgoStr() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}

const STANCE: Record<string, { label: string; cls: string }> = {
  owned:    { label: "Owned",     cls: "bg-emerald-600 text-white" },
  bullish:  { label: "Bullish",   cls: "bg-blue-600 text-white" },
  bearish:  { label: "Bearish",   cls: "bg-rose-600 text-white" },
  mentioned:{ label: "Mentioned", cls: "bg-zinc-200 text-zinc-700" },
};

function StockRow({ s }: { s: StockMention }) {
  const stance = STANCE[s.stance] ?? STANCE.mentioned;
  const href = s.source_episode_id != null
    ? `/episode/${s.source_episode_id}${s.source_start_ms != null ? `#t-${s.source_start_ms}` : ""}`
    : null;
  return (
    <div className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3">
      <span className="w-36 shrink-0 font-medium text-zinc-900">{s.company}</span>
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${stance.cls}`}>
        {stance.label}
      </span>
      <span className="flex-1 text-sm text-zinc-600">
        {s.summary}
        {href && (
          <Link href={href} className="ml-1 text-indigo-500 hover:text-indigo-700">
            ↗
          </Link>
        )}
      </span>
    </div>
  );
}

function NuggetItem({ n }: { n: NewsletterNugget }) {
  return (
    <div className="space-y-2 py-4 border-b border-zinc-100 last:border-0">
      <p className="text-sm font-medium text-zinc-900">{n.claim}</p>
      {n.quote && (
        <blockquote className="border-l-2 border-indigo-300 pl-3 text-sm text-zinc-600 italic">
          {n.quote}
          {n.speaker_name && (
            <span className="not-italic text-zinc-500"> — {n.speaker_name}</span>
          )}
        </blockquote>
      )}
      {n.curation_note && (
        <p className="text-xs italic text-zinc-500">{n.curation_note}</p>
      )}
    </div>
  );
}

export default function NewsletterPage() {
  const [fromDate, setFromDate] = useState(weekAgoStr());
  const [toDate, setToDate] = useState(todayStr());
  const [newsletter, setNewsletter] = useState<Newsletter | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMarkdown, setShowMarkdown] = useState(false);

  async function generate() {
    setLoading(true);
    setError(null);
    setNewsletter(null);
    try {
      const result = await getNewsletter({ from: fromDate, to: toDate });
      setNewsletter(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate newsletter");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Newsletter</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Renders kept insights as a distributable digest.
        </p>
      </div>

      {/* Date range picker */}
      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 bg-white p-4">
        <div className="space-y-1">
          <label className="text-xs font-medium text-zinc-600">From</label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium text-zinc-600">To</label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        </div>
        <button
          type="button"
          onClick={generate}
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "Building…" : "Build newsletter"}
        </button>
      </div>

      {error && (
        <p className="text-sm text-rose-600 rounded-lg border border-rose-200 bg-rose-50 p-3">
          {error}
        </p>
      )}

      {newsletter && (
        <div className="space-y-6">
          {/* Stats row */}
          <div className="flex flex-wrap gap-3 text-sm text-zinc-600">
            <span className="font-semibold text-zinc-900">{fromDate} – {toDate}</span>
            <span>·</span>
            <span>{newsletter.episode_count} episode{newsletter.episode_count !== 1 ? "s" : ""}</span>
            <span>·</span>
            <span className="font-semibold text-emerald-600">{newsletter.kept_count} kept</span>
            <span>·</span>
            <span>{newsletter.lead.length} relevant, {newsletter.good_to_know.length} good to know</span>
          </div>

          {/* Toggle: preview vs markdown */}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShowMarkdown(false)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                !showMarkdown
                  ? "bg-zinc-900 text-white"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
              }`}
            >
              Preview
            </button>
            <button
              type="button"
              onClick={() => setShowMarkdown(true)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                showMarkdown
                  ? "bg-zinc-900 text-white"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
              }`}
            >
              Markdown
            </button>
          </div>

          {showMarkdown ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => navigator.clipboard.writeText(newsletter.markdown)}
                className="absolute top-3 right-3 rounded-md bg-zinc-800 px-2 py-1 text-xs text-white hover:bg-zinc-700"
              >
                Copy
              </button>
              <textarea
                readOnly
                value={newsletter.markdown}
                rows={40}
                className="w-full rounded-xl border border-zinc-200 bg-zinc-950 px-4 py-4 font-mono text-xs text-zinc-100 focus:outline-none"
              />
            </div>
          ) : (
            <div className="space-y-10">
              {/* Nuggets card */}
              <div className="rounded-xl border border-zinc-200 bg-white divide-y divide-zinc-100">
                {newsletter.lead.length > 0 && (
                  <section className="p-6 space-y-2">
                    <h2 className="text-base font-semibold text-zinc-900">Relevant Nuggets</h2>
                    {newsletter.lead.map((n) => (
                      <NuggetItem key={n.id} n={n} />
                    ))}
                  </section>
                )}

                {newsletter.good_to_know.length > 0 && (
                  <section className="p-6 space-y-2">
                    <h2 className="text-base font-semibold text-zinc-900">Good to Know</h2>
                    {newsletter.good_to_know.map((n) => (
                      <NuggetItem key={n.id} n={n} />
                    ))}
                  </section>
                )}

                {newsletter.kept_count === 0 && (
                  <div className="p-10 text-center text-sm text-zinc-500">
                    No kept nuggets in this date range.{" "}
                    <Link href="/episodes" className="text-indigo-600 hover:underline">
                      Review an episode →
                    </Link>
                  </div>
                )}
              </div>

              {/* Stock Read-Through — same structure as DigestView */}
              {newsletter.stock_readthrough.length > 0 && (
                <div>
                  <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                    Stock read-through
                  </h3>
                  <div className="divide-y divide-zinc-100 overflow-hidden rounded-xl border border-zinc-200 bg-white">
                    {newsletter.stock_readthrough.map((s) => (
                      <StockRow key={s.company} s={s} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
