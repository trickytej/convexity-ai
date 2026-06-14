"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { Newsletter, NewsletterNugget, Show, StockMention } from "@/lib/api";
import { getNewsletter, getShows } from "@/lib/api";

const STANCE: Record<string, { label: string; cls: string }> = {
  owned:     { label: "Owned",     cls: "bg-emerald-600 text-white" },
  bullish:   { label: "Bullish",   cls: "bg-blue-600 text-white" },
  bearish:   { label: "Bearish",   cls: "bg-rose-600 text-white" },
  mentioned: { label: "Mentioned", cls: "bg-zinc-200 text-zinc-700" },
};

function GripHandle(props: React.HTMLAttributes<SVGSVGElement>) {
  return (
    <svg width="12" height="16" viewBox="0 0 12 16" fill="currentColor" {...props}>
      <circle cx="4" cy="3"  r="1.4" />
      <circle cx="8" cy="3"  r="1.4" />
      <circle cx="4" cy="8"  r="1.4" />
      <circle cx="8" cy="8"  r="1.4" />
      <circle cx="4" cy="13" r="1.4" />
      <circle cx="8" cy="13" r="1.4" />
    </svg>
  );
}

function SortableNuggetItem({ n }: { n: NewsletterNugget }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: n.id });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`group flex items-start gap-2 py-4 border-b border-zinc-100 last:border-0 ${
        isDragging ? "opacity-50 z-50 relative" : ""
      }`}
    >
      <button
        {...attributes}
        {...listeners}
        tabIndex={-1}
        aria-label="Drag to reorder"
        className="mt-1 shrink-0 cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 transition-opacity text-zinc-300 hover:text-zinc-500 touch-none print:hidden"
      >
        <GripHandle />
      </button>
      <div className="flex-1 space-y-2">
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
    </div>
  );
}

function StockRow({ s }: { s: StockMention }) {
  const stance = STANCE[s.stance] ?? STANCE.mentioned;
  const href = s.source_episode_id != null
    ? `/episode/${s.source_episode_id}${s.source_start_ms != null ? `#t-${s.source_start_ms}` : ""}`
    : null;
  return (
    <div className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3 break-inside-avoid">
      <span className="w-36 shrink-0 font-medium text-zinc-900">{s.company}</span>
      <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${stance.cls}`}>
        {stance.label}
      </span>
      <span className="flex-1 text-sm text-zinc-600">
        {s.summary}
        {href && (
          <Link href={href} className="ml-1 text-indigo-500 hover:text-indigo-700 print:hidden">
            ↗
          </Link>
        )}
      </span>
    </div>
  );
}

function SortableSection({
  title,
  items,
  onReorder,
}: {
  title: string;
  items: NewsletterNugget[];
  onReorder: (next: NewsletterNugget[]) => void;
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } })
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIdx = items.findIndex((n) => n.id === active.id);
      const newIdx = items.findIndex((n) => n.id === over.id);
      onReorder(arrayMove(items, oldIdx, newIdx));
    }
  }

  return (
    <section className="p-6 space-y-2">
      <h2 className="text-base font-semibold text-zinc-900">{title}</h2>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={items.map((n) => n.id)} strategy={verticalListSortingStrategy}>
          {items.map((n) => (
            <SortableNuggetItem key={n.id} n={n} />
          ))}
        </SortableContext>
      </DndContext>
    </section>
  );
}

export default function NewsletterPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [selectedShow, setSelectedShow] = useState<string | null>(null);
  const [newsletter, setNewsletter] = useState<Newsletter | null>(null);
  const [lead, setLead] = useState<NewsletterNugget[]>([]);
  const [g2k, setG2k] = useState<NewsletterNugget[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMarkdown, setShowMarkdown] = useState(false);

  useEffect(() => {
    getShows().then((all) => setShows(all.filter((s) => s.active && s.transcribed > 0)));
  }, []);

  useEffect(() => {
    if (newsletter) {
      setLead(newsletter.lead);
      setG2k(newsletter.good_to_know);
    }
  }, [newsletter]);

  async function generate(show: string) {
    setLoading(true);
    setError(null);
    setNewsletter(null);
    setShowMarkdown(false);
    try {
      const result = await getNewsletter({ show });
      setNewsletter(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate newsletter");
    } finally {
      setLoading(false);
    }
  }

  function selectShow(slug: string) {
    setSelectedShow(slug);
    generate(slug);
  }

  const selectedShowName = shows.find((s) => s.slug === selectedShow)?.name ?? selectedShow;

  return (
    <div className="space-y-6">
      <div className="print:hidden">
        <h1 className="text-2xl font-semibold tracking-tight">Newsletter</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Select a podcast to render its kept insights as a distributable digest.
        </p>
      </div>

      {/* Podcast selector */}
      <div className="print:hidden flex flex-wrap gap-2">
        {shows.map((s) => (
          <button
            key={s.slug}
            type="button"
            onClick={() => selectShow(s.slug)}
            disabled={loading}
            className={`rounded-full px-3 py-1.5 text-sm ring-1 ring-inset transition disabled:opacity-50 ${
              selectedShow === s.slug
                ? "bg-indigo-600 text-white ring-indigo-600"
                : "bg-white text-zinc-700 ring-zinc-200 hover:bg-zinc-50"
            }`}
          >
            {s.name}
          </button>
        ))}
      </div>

      {loading && (
        <p className="text-sm text-zinc-500 animate-pulse">Building newsletter…</p>
      )}

      {error && (
        <p className="print:hidden text-sm text-rose-600 rounded-lg border border-rose-200 bg-rose-50 p-3">
          {error}
        </p>
      )}

      {newsletter && !loading && (
        <div className="space-y-6">
          {/* Stats row */}
          <div className="flex flex-wrap gap-3 text-sm text-zinc-600">
            <span className="font-semibold text-zinc-900">{selectedShowName}</span>
            <span>·</span>
            <span>{newsletter.episode_count} episode{newsletter.episode_count !== 1 ? "s" : ""}</span>
            <span>·</span>
            <span className="font-semibold text-emerald-600">{newsletter.kept_count} kept</span>
            <span>·</span>
            <span>{lead.length} relevant, {g2k.length} good to know</span>
          </div>

          {/* Tab bar + Export PDF */}
          <div className="print:hidden flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowMarkdown(false)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                !showMarkdown ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
              }`}
            >
              Preview
            </button>
            <button
              type="button"
              onClick={() => setShowMarkdown(true)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                showMarkdown ? "bg-zinc-900 text-white" : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200"
              }`}
            >
              Markdown
            </button>
            <div className="ml-auto">
              <button
                type="button"
                onClick={() => window.print()}
                className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors"
              >
                Export PDF
              </button>
            </div>
          </div>

          {/* Markdown view */}
          <div className={`${showMarkdown ? "" : "hidden"} print:hidden relative`}>
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

          {/* Preview — always in DOM so Export PDF works from any tab */}
          <div className={showMarkdown ? "hidden print:block" : ""}>
            <div className="space-y-10">
              <div className="rounded-xl border border-zinc-200 bg-white divide-y divide-zinc-100">
                {lead.length > 0 && (
                  <SortableSection title="Relevant Nuggets" items={lead} onReorder={setLead} />
                )}
                {g2k.length > 0 && (
                  <SortableSection title="Good to Know" items={g2k} onReorder={setG2k} />
                )}
                {newsletter.kept_count === 0 && (
                  <div className="p-10 text-center text-sm text-zinc-500">
                    No kept nuggets for this podcast.{" "}
                    <Link href="/episodes" className="text-indigo-600 hover:underline print:hidden">
                      Review episodes →
                    </Link>
                  </div>
                )}
              </div>

              {newsletter.stock_readthrough.length > 0 && (
                <div className="break-before-avoid">
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
          </div>
        </div>
      )}
    </div>
  );
}
