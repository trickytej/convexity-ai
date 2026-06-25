"use client";

import { useState, useCallback, useRef } from "react";
import Link from "next/link";
import type { Episode, NuggetWithCuration, Newsletter, NewsletterNugget, StockMention } from "@/lib/api";
import { getEpisodeNuggets, getNewsletter } from "@/lib/api";
import { fmtDate, fmtDuration } from "@/lib/format";
import { Badge } from "@/components/ui";
import TranscribeButton from "@/components/TranscribeButton";
import { NuggetReviewCard } from "@/components/NuggetReviewCard";

function PencilIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="currentColor">
      <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325z"/>
    </svg>
  );
}

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  transcribed: { label: "Transcribed", cls: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25" },
  acquired:    { label: "Downloaded",  cls: "bg-sky-500/10 text-sky-300 ring-sky-500/25" },
  discovered:  { label: "Discovered",  cls: "bg-white/[0.05] text-zinc-400 ring-white/10" },
  failed:      { label: "Failed",      cls: "bg-rose-500/10 text-rose-300 ring-rose-500/25" },
};

function EpisodeRow({
  episode,
  isOpen,
  isSelected,
  onToggleOpen,
  onToggleSelect,
}: {
  episode: Episode;
  isOpen: boolean;
  isSelected: boolean;
  onToggleOpen: () => void;
  onToggleSelect: () => void;
}) {
  const [nuggets, setNuggets] = useState<NuggetWithCuration[] | null>(null);
  const [loadingNuggets, setLoadingNuggets] = useState(false);

  const isTranscribed = episode.status === "transcribed" || (!episode.status && !!episode.source);
  const statusInfo = STATUS_BADGE[episode.status ?? (episode.source ? "transcribed" : "discovered")];

  const handleToggleOpen = useCallback(async () => {
    if (!isTranscribed) return;
    if (!isOpen && nuggets === null) {
      setLoadingNuggets(true);
      try {
        const data = await getEpisodeNuggets(episode.id);
        setNuggets(data);
      } finally {
        setLoadingNuggets(false);
      }
    }
    onToggleOpen();
  }, [isTranscribed, isOpen, nuggets, episode.id, onToggleOpen]);

  return (
    <div className="border-b border-white/[0.06] last:border-b-0">
      <div className="flex items-center gap-3 px-4 py-3.5 transition hover:bg-white/[0.02]">
        {/* checkbox for report selection (transcribed only) */}
        {isTranscribed ? (
          <input
            type="checkbox"
            checked={isSelected}
            onChange={onToggleSelect}
            className="h-4 w-4 shrink-0 rounded accent-[#00d4ff]"
            title="Select for report"
          />
        ) : (
          <div className="h-4 w-4 shrink-0" />
        )}

        <div className="min-w-0 flex-1">
          {isTranscribed ? (
            <button
              type="button"
              onClick={handleToggleOpen}
              className="w-full text-left"
            >
              <p className="truncate font-medium text-zinc-100 transition hover:text-[#00d4ff]">
                {isOpen ? "▾" : "▸"} {episode.title}
              </p>
            </button>
          ) : (
            <p className="truncate font-medium text-zinc-500">{episode.title}</p>
          )}
          <p className="mt-0.5 text-sm text-zinc-500">
            <span className="font-[family-name:var(--font-mono)] text-zinc-400">{episode.show_slug}</span>
            {" · "}{fmtDate(episode.published_at)}
            {episode.duration_seconds ? ` · ${fmtDuration(episode.duration_seconds)}` : ""}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {isTranscribed && episode.nugget_count > 0 && (
            <Badge tone="indigo">{episode.nugget_count} nuggets</Badge>
          )}
          {!isTranscribed && statusInfo && (
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${statusInfo.cls}`}>
              {statusInfo.label}
            </span>
          )}
          {isTranscribed ? (
            <Link
              href={`/episode/${episode.id}`}
              className="text-xs text-[#00d4ff] transition hover:text-[#33ddff]"
            >
              full page →
            </Link>
          ) : (
            <TranscribeButton episodeId={episode.id} initialStatus={episode.status} />
          )}
        </div>
      </div>

      {/* Inline nugget curation */}
      {isOpen && isTranscribed && (
        <div className="border-t border-white/[0.06] bg-white/[0.01] px-4 py-4">
          {loadingNuggets && (
            <p className="py-4 text-center text-sm text-zinc-500">Loading nuggets…</p>
          )}
          {!loadingNuggets && nuggets !== null && nuggets.length === 0 && (
            <p className="py-4 text-center text-sm text-zinc-500">
              No nuggets yet — try generating insights from the{" "}
              <Link href={`/episode/${episode.id}`} className="text-[#00d4ff]">episode page</Link>.
            </p>
          )}
          {!loadingNuggets && nuggets !== null && nuggets.length > 0 && (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {nuggets.map((n) => (
                <NuggetReviewCard key={n.id} nugget={n} episodeId={episode.id} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const STANCE_STYLE: Record<string, { label: string; cls: string }> = {
  owned:     { label: "Owned",     cls: "bg-emerald-600 text-white" },
  bullish:   { label: "Bullish",   cls: "bg-blue-600 text-white" },
  bearish:   { label: "Bearish",   cls: "bg-rose-600 text-white" },
  mentioned: { label: "Mentioned", cls: "bg-zinc-200 text-zinc-700" },
};

function NuggetRow({ n }: { n: NewsletterNugget }) {
  const [claim, setClaim] = useState(n.claim);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(n.claim);
  const taRef = useRef<HTMLTextAreaElement>(null);

  function startEdit() {
    setDraft(claim);
    setEditing(true);
    setTimeout(() => taRef.current?.focus(), 0);
  }

  function commit() {
    setClaim(draft.trim() || claim);
    setEditing(false);
  }

  return (
    <div className="group py-4 border-b border-zinc-100 last:border-0">
      {editing ? (
        <textarea
          ref={taRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Escape") { setEditing(false); return; }
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); commit(); }
          }}
          rows={2}
          className="w-full resize-none rounded border border-indigo-300 bg-indigo-50 px-2 py-1 text-sm font-medium text-zinc-900 focus:outline-none focus:ring-1 focus:ring-indigo-400"
        />
      ) : (
        <div className="flex items-start gap-1.5">
          <p className="flex-1 text-sm font-medium text-zinc-900">{claim}</p>
          <button
            type="button"
            onClick={startEdit}
            title="Edit"
            className="mt-0.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 text-zinc-400 hover:text-indigo-600"
          >
            <PencilIcon />
          </button>
        </div>
      )}
      {n.quote && (
        <blockquote className="mt-2 border-l-2 border-indigo-300 pl-3 text-sm italic text-zinc-600">
          {n.quote}
          {n.speaker_name && (
            <span className="not-italic text-zinc-500"> — {n.speaker_name}</span>
          )}
        </blockquote>
      )}
      {n.curation_note && (
        <p className="mt-1.5 text-xs italic text-zinc-500">{n.curation_note}</p>
      )}
      <p className="mt-1.5 text-xs text-zinc-400">
        {n.show_slug} · {n.episode_title}
      </p>
    </div>
  );
}

function ReportDisplay({ newsletter }: { newsletter: Newsletter }) {
  const { lead, good_to_know, stock_readthrough, episode_count, kept_count } = newsletter;

  if (kept_count === 0) {
    return (
      <div className="mt-6 rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 px-5 py-8 text-center">
        <p className="text-sm text-zinc-500">No kept nuggets in this date range.</p>
        <p className="mt-1 text-xs text-zinc-600">
          Review and keep insights from the episodes above first.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-[#00d4ff]">
          {episode_count} episode{episode_count !== 1 ? "s" : ""} · {kept_count} kept
        </p>
        <Link href="/newsletter" className="text-xs text-[#00d4ff] hover:text-[#33ddff]">
          Full newsletter →
        </Link>
      </div>

      <div className="divide-y divide-zinc-100 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-xl shadow-black/20">
        {lead.length > 0 && (
          <section className="px-6 py-5">
            <h2 className="mb-1 text-base font-semibold text-zinc-900">Relevant Nuggets</h2>
            {lead.map((n) => <NuggetRow key={n.id} n={n} />)}
          </section>
        )}

        {good_to_know.length > 0 && (
          <section className="px-6 py-5">
            <h2 className="mb-1 text-base font-semibold text-zinc-900">Relevant Insights</h2>
            {good_to_know.map((n) => <NuggetRow key={n.id} n={n} />)}
          </section>
        )}

        {stock_readthrough.length > 0 && (
          <section className="px-6 py-5">
            <h2 className="mb-3 text-base font-semibold text-zinc-900">Stock Read-Through</h2>
            <div className="divide-y divide-zinc-100">
              {stock_readthrough.map((s: StockMention) => {
                const stance = STANCE_STYLE[s.stance] ?? STANCE_STYLE.mentioned;
                return (
                  <div key={s.company} className="flex flex-wrap items-start gap-x-3 gap-y-1 py-3 first:pt-0 last:pb-0">
                    <span className="w-32 shrink-0 text-sm font-medium text-zinc-900">{s.company}</span>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${stance.cls}`}>
                      {stance.label}
                    </span>
                    <span className="flex-1 text-sm text-zinc-600">{s.summary}</span>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

export default function EpisodeWorkflowPanel({
  episodes,
  since,
  until,
}: {
  episodes: Episode[];
  since: string;
  until: string;
}) {
  const [openIds, setOpenIds] = useState<Set<number>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [episodesOpen, setEpisodesOpen] = useState(true);
  const [reportOpen, setReportOpen] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [report, setReport] = useState<Newsletter | null>(null);

  function toggleOpen(id: number) {
    setOpenIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleGenerateReport() {
    setGenerating(true);
    setGenError(null);
    setReport(null);
    try {
      const result = await getNewsletter({ from: since, to: until });
      setReport(result);
      setReportOpen(true);
    } catch (e) {
      setGenError(e instanceof Error ? e.message : "generation failed");
    } finally {
      setGenerating(false);
    }
  }

  const transcribed = episodes.filter(
    (e) => e.status === "transcribed" || (!e.status && !!e.source),
  );

  if (episodes.length === 0) {
    return (
      <p className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 px-4 py-10 text-center text-sm text-zinc-500">
        No episodes found for this date range. Try refreshing feeds above.
      </p>
    );
  }

  return (
    <div>
      {/* Episodes section */}
      <div className="mb-2 flex items-center justify-between">
        <p className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.24em] text-[#00d4ff]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]" />
          Episodes
        </p>
        <button
          type="button"
          onClick={() => setEpisodesOpen((o) => !o)}
          className="text-base text-zinc-500 transition-colors hover:text-zinc-200"
        >
          {episodesOpen ? "▴" : "▾"}
        </button>
      </div>
      {episodesOpen && (
        <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-[#0b0c10]/60">
          {episodes.map((e) => (
            <EpisodeRow
              key={e.id}
              episode={e}
              isOpen={openIds.has(e.id)}
              isSelected={selectedIds.has(e.id)}
              onToggleOpen={() => toggleOpen(e.id)}
              onToggleSelect={() => toggleSelect(e.id)}
            />
          ))}
        </div>
      )}

      {/* Report section */}
      {transcribed.length > 0 && (
        <>
          <div className="mt-6 mb-2 flex items-center justify-between">
            <p className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.24em] text-[#00d4ff]">
              <span className="inline-block h-px w-8 bg-[#00d4ff]" />
              Report
            </p>
            <button
              type="button"
              onClick={() => setReportOpen((o) => !o)}
              className="text-base text-zinc-500 transition-colors hover:text-zinc-200"
            >
              {reportOpen ? "▴" : "▾"}
            </button>
          </div>
        {reportOpen && (
        <div className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 px-5 py-4">
          <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
            <span className="inline-block h-px w-8 bg-[#00d4ff]" />
            <span className="text-[#00d4ff]">Generate Report</span>
          </p>
          <p className="mt-2 text-sm text-zinc-400">
            Build a report from kept nuggets in this date range ({since} – {until}).
          </p>
          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={handleGenerateReport}
              disabled={generating}
              className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ${
                generating
                  ? "bg-[#00d4ff]/10 text-[#00d4ff] cursor-not-allowed"
                  : "bg-[#00d4ff] text-[#001a26] hover:bg-[#00d4ff]/90"
              }`}
            >
              {generating && (
                <svg className="animate-spin" width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 3a5 5 0 1 0 4.546 2.914.5.5 0 0 1 .908-.417A6 6 0 1 1 8 2z"/>
                  <path d="M8 4.466V.534a.25.25 0 0 1 .41-.192l2.36 1.966c.12.1.12.284 0 .384L8.41 4.658A.25.25 0 0 1 8 4.466"/>
                </svg>
              )}
              {generating ? "Building…" : "Generate Report"}
            </button>
            {genError && <p className="text-sm text-rose-400">{genError}</p>}
          </div>

          {report && <ReportDisplay newsletter={report} />}
        </div>
        )}
        </>
      )}
    </div>
  );
}
