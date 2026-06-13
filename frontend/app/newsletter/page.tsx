"use client";

import { useState } from "react";
import Link from "next/link";
import type { Newsletter, NewsletterNugget } from "@/lib/api";
import { getNewsletter } from "@/lib/api";
import { Badge } from "@/components/ui";

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}
function weekAgoStr() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().slice(0, 10);
}

function NuggetLeadItem({ n, idx }: { n: NewsletterNugget; idx: number }) {
  return (
    <div className="space-y-2 py-4 border-b border-zinc-100 last:border-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-bold text-indigo-600">#{idx + 1}</span>
        {n.tickers.map((t) => <Badge key={t} tone="amber">{t}</Badge>)}
        {n.contradicts_consensus && <Badge tone="amber">⚡ contrarian</Badge>}
        <span className="text-xs text-zinc-400">{n.show_slug}</span>
      </div>
      {n.curation_note && (
        <p className="text-sm font-medium text-zinc-800">{n.curation_note}</p>
      )}
      {n.quote && (
        <blockquote className="border-l-2 border-indigo-300 pl-3 text-sm text-zinc-600 italic">
          {n.quote}
          {n.speaker_name && (
            <span className="not-italic text-zinc-500"> — {n.speaker_name}</span>
          )}
        </blockquote>
      )}
      {!n.quote && <p className="text-sm text-zinc-700">{n.claim}</p>}
      {n.start_ms != null && (
        <Link
          href={`/episode/${n.episode_id}?t=${n.start_ms}`}
          className="text-xs text-indigo-500 hover:text-indigo-700"
        >
          In context →
        </Link>
      )}
    </div>
  );
}

function NuggetG2KItem({ n }: { n: NewsletterNugget }) {
  return (
    <li className="text-sm text-zinc-700 space-y-0.5">
      <div className="flex flex-wrap gap-1.5 items-baseline">
        {n.speaker_name && <span className="font-medium">{n.speaker_name}</span>}
        <span className="text-zinc-400 text-xs">· {n.show_slug}</span>
        {n.tickers.map((t) => <Badge key={t} tone="amber">{t}</Badge>)}
      </div>
      {n.curation_note
        ? <p className="text-zinc-600 text-xs">{n.curation_note}</p>
        : <p className="text-zinc-600 text-xs">{n.claim}</p>
      }
    </li>
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
            <span>{newsletter.lead.length} lead, {newsletter.good_to_know.length} good to know</span>
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
            <div className="rounded-xl border border-zinc-200 bg-white divide-y divide-zinc-100">
              {/* Lead section */}
              {newsletter.lead.length > 0 && (
                <section className="p-6 space-y-2">
                  <h2 className="text-base font-semibold text-zinc-900">🔥 Lead</h2>
                  <p className="text-xs text-zinc-400">Rank 1 — must-read insights</p>
                  {newsletter.lead.map((n, i) => (
                    <NuggetLeadItem key={n.id} n={n} idx={i} />
                  ))}
                </section>
              )}

              {/* Good to know */}
              {newsletter.good_to_know.length > 0 && (
                <section className="p-6 space-y-3">
                  <h2 className="text-base font-semibold text-zinc-900">📌 Good to Know</h2>
                  <ul className="space-y-3">
                    {newsletter.good_to_know.map((n) => (
                      <NuggetG2KItem key={n.id} n={n} />
                    ))}
                  </ul>
                </section>
              )}

              {/* Stock readthrough */}
              {newsletter.stock_readthrough.length > 0 && (
                <section className="p-6 space-y-3">
                  <h2 className="text-base font-semibold text-zinc-900">📈 Stock Read-Through</h2>
                  <p className="text-xs text-zinc-400">Companies mentioned in kept insights</p>
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="text-xs text-zinc-500 border-b border-zinc-100">
                          <th className="text-left py-2 pr-6 font-medium">Company</th>
                          <th className="text-left py-2 pr-6 font-medium">Tickers</th>
                          <th className="text-right py-2 font-medium">Mentions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-50">
                        {newsletter.stock_readthrough.map((s) => (
                          <tr key={s.company}>
                            <td className="py-2 pr-6 font-medium text-zinc-800">{s.company}</td>
                            <td className="py-2 pr-6">
                              {s.tickers.length > 0
                                ? s.tickers.map((t) => (
                                    <Badge key={t} tone="amber">{t}</Badge>
                                  ))
                                : <span className="text-zinc-400">—</span>}
                            </td>
                            <td className="py-2 text-right text-zinc-600">{s.mention_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
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
          )}
        </div>
      )}
    </div>
  );
}
