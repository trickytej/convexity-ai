"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Questrial } from "next/font/google";

const questrial = Questrial({ subsets: ["latin"], weight: "400" });
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
import { getNewsletter, getShows, sendNewsletter } from "@/lib/api";

const STANCE_ORDER = ["bullish", "owned", "mentioned", "bearish"] as const;

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

function PencilIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
      <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325z"/>
    </svg>
  );
}

// ── Nugget item ──────────────────────────────────────────────────────────────

interface NuggetItemProps {
  n: NewsletterNugget;
  onEdit: (value: string) => void;
  onDelete: () => void;
}

function SortableNuggetItem({ n, onEdit, onDelete }: NuggetItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: n.id });

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);

  function startEdit() {
    setDraft(n.claim);
    setEditing(true);
    setTimeout(() => taRef.current?.focus(), 0);
  }

  function commit() {
    onEdit(draft.trim() || n.claim);
    setEditing(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") { setEditing(false); return; }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); commit(); }
  }

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`group flex items-start gap-2 py-4 border-b border-zinc-100 last:border-0 ${
        isDragging ? "opacity-50 z-50 relative" : ""
      }`}
    >
      {/* Drag handle */}
      <button
        {...attributes}
        {...listeners}
        tabIndex={-1}
        aria-label="Drag to reorder"
        className="mt-1 shrink-0 cursor-grab active:cursor-grabbing opacity-0 group-hover:opacity-100 transition-opacity text-zinc-300 hover:text-zinc-500 touch-none print:hidden"
      >
        <GripHandle />
      </button>

      <div className="flex-1 space-y-2 min-w-0">
        {/* Claim — inline editable */}
        {editing ? (
          <textarea
            ref={taRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={handleKeyDown}
            rows={2}
            className="w-full resize-none rounded border border-indigo-300 bg-indigo-50 px-2 py-1 text-sm font-medium text-zinc-900 focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        ) : (
          <div className="flex items-start gap-1.5">
            <p className="text-sm font-medium text-zinc-900 flex-1">{n.claim}</p>
            <button
              type="button"
              onClick={startEdit}
              title="Edit"
              className="print:hidden shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity text-zinc-400 hover:text-indigo-600"
            >
              <PencilIcon />
            </button>
          </div>
        )}

        {/* Quote */}
        {n.quote && (
          <blockquote className="border-l-2 border-indigo-300 pl-3 text-sm text-zinc-600 italic">
            {n.quote}
            {n.speaker_name && (
              <span className="not-italic text-zinc-500"> — {n.speaker_name}</span>
            )}
          </blockquote>
        )}

        {/* Curation note — display only, no editing */}
        {n.curation_note && (
          <p className="text-xs italic text-zinc-500">{n.curation_note}</p>
        )}
      </div>

      {/* Delete */}
      <button
        type="button"
        onClick={onDelete}
        title="Remove nugget"
        className="print:hidden shrink-0 mt-1 opacity-0 group-hover:opacity-100 transition-opacity text-zinc-300 hover:text-rose-500"
      >
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
          <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
        </svg>
      </button>
    </div>
  );
}

// ── Stock row ────────────────────────────────────────────────────────────────

interface StockRowProps {
  s: StockMention;
  onEdit: (field: "summary" | "stance", value: string) => void;
  onDelete: () => void;
}

function EditableStockRow({ s, onEdit, onDelete }: StockRowProps) {
  const stance = STANCE[s.stance] ?? STANCE.mentioned;
  const [editingSummary, setEditingSummary] = useState(false);
  const [draft, setDraft] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);

  function startEditSummary() {
    setDraft(s.summary);
    setEditingSummary(true);
    setTimeout(() => taRef.current?.focus(), 0);
  }

  function commitSummary() {
    onEdit("summary", draft.trim());
    setEditingSummary(false);
  }

  function cycleStance() {
    const idx = STANCE_ORDER.indexOf(s.stance as typeof STANCE_ORDER[number]);
    const next = STANCE_ORDER[(idx + 1) % STANCE_ORDER.length];
    onEdit("stance", next);
  }

  return (
    <div className="group flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3 break-inside-avoid">
      <span className="w-36 shrink-0 font-medium text-zinc-900">{s.company}</span>

      {/* Stance — click to cycle */}
      <button
        type="button"
        onClick={cycleStance}
        title="Click to change stance"
        className={`print:hidden shrink-0 rounded-full px-2 py-0.5 text-xs font-medium transition-opacity hover:opacity-80 ${stance.cls}`}
      >
        {stance.label}
      </button>
      {/* Print-only static badge */}
      <span className={`hidden print:inline-flex shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${stance.cls}`}>
        {stance.label}
      </span>

      {/* Summary — inline editable */}
      <div className="flex flex-1 items-start gap-1.5 min-w-0">
        {editingSummary ? (
          <textarea
            ref={taRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commitSummary}
            onKeyDown={(e) => {
              if (e.key === "Escape") { setEditingSummary(false); return; }
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); commitSummary(); }
            }}
            rows={2}
            className="flex-1 resize-none rounded border border-indigo-300 bg-indigo-50 px-2 py-0.5 text-sm text-zinc-700 focus:outline-none focus:ring-1 focus:ring-indigo-400"
          />
        ) : (
          <>
            <span className="flex-1 text-sm text-zinc-600">{s.summary}</span>
            <button
              type="button"
              onClick={startEditSummary}
              title="Edit summary"
              className="print:hidden shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-zinc-400 hover:text-indigo-600"
            >
              <PencilIcon />
            </button>
          </>
        )}
      </div>

      {/* Delete */}
      <button
        type="button"
        onClick={onDelete}
        title="Remove"
        className="print:hidden shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-zinc-300 hover:text-rose-500"
      >
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
          <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
        </svg>
      </button>
    </div>
  );
}

// ── Sortable section ─────────────────────────────────────────────────────────

function SortableSection({
  title,
  items,
  onReorder,
  onEdit,
  onDelete,
}: {
  title: string;
  items: NewsletterNugget[];
  onReorder: (next: NewsletterNugget[]) => void;
  onEdit: (id: number, value: string) => void;
  onDelete: (id: number) => void;
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
            <SortableNuggetItem
              key={n.id}
              n={n}
              onEdit={(val) => onEdit(n.id, val)}
              onDelete={() => onDelete(n.id)}
            />
          ))}
        </SortableContext>
      </DndContext>
    </section>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function NewsletterPage() {
  const [shows, setShows] = useState<Show[]>([]);
  const [selectedShow, setSelectedShow] = useState<string | null>(null);
  const [newsletter, setNewsletter] = useState<Newsletter | null>(null);
  const [lead, setLead] = useState<NewsletterNugget[]>([]);
  const [g2k, setG2k] = useState<NewsletterNugget[]>([]);
  const [stocks, setStocks] = useState<StockMention[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showMarkdown, setShowMarkdown] = useState(false);

  // Email panel
  const [showEmail, setShowEmail] = useState(false);
  const [recipients, setRecipients] = useState("");
  const [emailSubject, setEmailSubject] = useState("");
  const [sendStatus, setSendStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [sendMessage, setSendMessage] = useState("");

  useEffect(() => {
    // All active shows, transcribed ones first — untranscribed render greyed
    // out so it's clear why they can't produce a newsletter yet.
    getShows().then((all) =>
      setShows(
        all
          .filter((s) => s.active)
          .sort((a, b) => Number(b.transcribed > 0) - Number(a.transcribed > 0)),
      ),
    );
  }, []);

  useEffect(() => {
    if (newsletter) {
      setLead(newsletter.lead);
      setG2k(newsletter.good_to_know);
      setStocks(newsletter.stock_readthrough);
    }
  }, [newsletter]);

  async function generate(show: string) {
    setLoading(true);
    setError(null);
    setNewsletter(null);
    setShowMarkdown(false);
    setShowEmail(false);
    try {
      setNewsletter(await getNewsletter({ show }));
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

  // Nugget handlers
  function editNugget(id: number, value: string) {
    const patch = (list: NewsletterNugget[]) =>
      list.map((n) => (n.id === id ? { ...n, claim: value } : n));
    setLead(patch);
    setG2k(patch);
  }

  function deleteNugget(id: number) {
    setLead((prev) => prev.filter((n) => n.id !== id));
    setG2k((prev) => prev.filter((n) => n.id !== id));
  }

  // Stock handlers
  function editStock(company: string, field: "summary" | "stance", value: string) {
    setStocks((prev) =>
      prev.map((s) => (s.company === company ? { ...s, [field]: value } : s))
    );
  }

  function deleteStock(company: string) {
    setStocks((prev) => prev.filter((s) => s.company !== company));
  }

  // Email
  function openEmail() {
    const name = shows.find((s) => s.slug === selectedShow)?.name ?? selectedShow ?? "";
    setEmailSubject(`${name} — Podcast Insights`);
    setSendStatus("idle");
    setSendMessage("");
    setShowEmail(true);
  }

  async function handleSend() {
    const toList = recipients.split(/[,\n]+/).map((s) => s.trim()).filter(Boolean);
    if (!toList.length) { setSendMessage("Enter at least one recipient."); return; }
    setSendStatus("sending");
    setSendMessage("");
    const showName = shows.find((s) => s.slug === selectedShow)?.name ?? selectedShow ?? "";
    try {
      const result = await sendNewsletter({
        to: toList,
        subject: emailSubject,
        show_name: showName,
        lead: lead.map(({ claim, quote, speaker_name, curation_note, show_slug }) => ({
          claim, quote, speaker_name, curation_note, show_slug,
        })),
        good_to_know: g2k.map(({ claim, quote, speaker_name, curation_note, show_slug }) => ({
          claim, quote, speaker_name, curation_note, show_slug,
        })),
        stocks: stocks.map(({ company, stance, summary }) => ({ company, stance, summary })),
      });
      setSendStatus("sent");
      setSendMessage(`Sent to ${result.sent} recipient${result.sent !== 1 ? "s" : ""}.`);
    } catch (e) {
      setSendStatus("error");
      setSendMessage(e instanceof Error ? e.message : "Send failed");
    }
  }

  const selectedShowName = shows.find((s) => s.slug === selectedShow)?.name ?? selectedShow;

  return (
    <div className="space-y-6">
      <div className="print:hidden">
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]" />
          <span className="text-[#00d4ff]">Distribute</span>
        </p>
        <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
          Newsletter
        </h1>
        <p className="mt-3 text-[15px] text-zinc-400">
          Select a podcast to render its kept insights as a distributable digest.
        </p>
      </div>

      {/* Podcast selector */}
      <div className="print:hidden flex flex-wrap gap-2">
        {shows.map((s) => {
          const hasTranscripts = s.transcribed > 0;
          return (
            <button
              key={s.slug}
              type="button"
              onClick={() => selectShow(s.slug)}
              disabled={loading || !hasTranscripts}
              title={
                hasTranscripts
                  ? undefined
                  : "No transcripts yet — run the ingest workflow to transcribe episodes first"
              }
              className={`rounded-full px-3.5 py-1.5 text-sm transition ${
                !hasTranscripts
                  ? "cursor-not-allowed border border-white/[0.05] text-zinc-700"
                  : selectedShow === s.slug
                    ? "bg-[#00d4ff] font-medium text-[#001a26]"
                    : "border border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-100"
              } ${loading ? "opacity-50" : ""}`}
            >
              {s.name}
              {!hasTranscripts && (
                <span className="ml-1.5 text-[10px] text-zinc-700">no transcripts yet</span>
              )}
            </button>
          );
        })}
      </div>

      {loading && <p className="text-sm text-zinc-500 animate-pulse">Building newsletter…</p>}

      {error && (
        <p className="print:hidden text-sm text-rose-300 rounded-lg border border-rose-500/25 bg-rose-500/10 p-3">
          {error}
        </p>
      )}

      {newsletter && !loading && (
        <div className="space-y-6">
          {/* Stats */}
          <div className="flex flex-wrap gap-3 text-sm text-zinc-500">
            <span className="font-semibold text-zinc-100">{selectedShowName}</span>
            <span className="text-zinc-700">·</span>
            <span>{newsletter.episode_count} episode{newsletter.episode_count !== 1 ? "s" : ""}</span>
            <span className="text-zinc-700">·</span>
            <span className="font-semibold text-emerald-300">{newsletter.kept_count} kept</span>
            <span className="text-zinc-700">·</span>
            <span>{lead.length} relevant, {g2k.length} good to know</span>
          </div>

          {/* Tab bar + actions */}
          <div className="print:hidden flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowMarkdown(false)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                !showMarkdown ? "bg-[#00d4ff] text-[#001a26]" : "bg-white/[0.06] text-zinc-300 hover:bg-white/10"
              }`}
            >
              Preview
            </button>
            <button
              type="button"
              onClick={() => setShowMarkdown(true)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                showMarkdown ? "bg-[#00d4ff] text-[#001a26]" : "bg-white/[0.06] text-zinc-300 hover:bg-white/10"
              }`}
            >
              Markdown
            </button>
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                onClick={openEmail}
                className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                  showEmail
                    ? "border-[#00d4ff]/40 bg-[#00d4ff] text-[#001a26]"
                    : "border-white/15 bg-white/[0.06] text-zinc-200 hover:bg-white/10"
                }`}
              >
                Send Email
              </button>
              <button
                type="button"
                onClick={() => window.print()}
                className="rounded-lg border border-white/15 bg-white/[0.06] px-3 py-1.5 text-sm font-medium text-zinc-200 transition-colors hover:bg-white/10"
              >
                Export PDF
              </button>
            </div>
          </div>

          {/* Email panel */}
          {showEmail && (
            <div className="print:hidden rounded-xl border border-white/[0.08] bg-[#0b0c10]/75 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-zinc-100">Send to readers</p>
                <button type="button" onClick={() => setShowEmail(false)} className="text-zinc-500 hover:text-zinc-200 text-lg leading-none">×</button>
              </div>
              <input
                type="text"
                value={emailSubject}
                onChange={(e) => setEmailSubject(e.target.value)}
                placeholder="Subject"
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:border-[#00d4ff]/50 focus:outline-none focus:ring-1 focus:ring-[#00d4ff]/30"
              />
              <textarea
                value={recipients}
                onChange={(e) => setRecipients(e.target.value)}
                placeholder="Recipients (comma-separated emails)"
                rows={2}
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm font-mono text-zinc-100 placeholder-zinc-500 focus:border-[#00d4ff]/50 focus:outline-none focus:ring-1 focus:ring-[#00d4ff]/30"
              />
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={sendStatus === "sending"}
                  className="rounded-lg bg-[#00d4ff] px-4 py-2 text-sm font-medium text-[#001a26] hover:bg-[#33ddff] disabled:opacity-50 transition-colors"
                >
                  {sendStatus === "sending" ? "Sending…" : "Send"}
                </button>
                {sendMessage && (
                  <p className={`text-sm ${sendStatus === "error" ? "text-rose-400" : "text-emerald-300"}`}>
                    {sendMessage}
                  </p>
                )}
              </div>
              {sendStatus !== "sent" && (
                <p className="text-xs text-zinc-500">
                  Requires <code className="font-mono text-zinc-400">DIGEST_SMTP_*</code> vars in <code className="font-mono text-zinc-400">.env</code>
                </p>
              )}
            </div>
          )}

          {/* Markdown view */}
          <div className={`${showMarkdown ? "" : "hidden"} print:hidden relative`}>
            <button
              type="button"
              onClick={() => navigator.clipboard.writeText(newsletter.markdown)}
              className="absolute top-3 right-3 rounded-md bg-white/10 px-2 py-1 text-xs text-zinc-200 hover:bg-white/20"
            >
              Copy
            </button>
            <textarea
              readOnly
              value={newsletter.markdown}
              rows={40}
              className="w-full rounded-xl border border-white/10 bg-[#08090c] px-4 py-4 font-mono text-xs text-zinc-200 focus:outline-none"
            />
          </div>

          {/* Preview — always in DOM so Export PDF works from any tab.
              Renders as a light "paper" sheet on the dark canvas; exports cleanly. */}
          <div className={`${questrial.className} ${showMarkdown ? "hidden print:block" : ""}`}>
            <div className="space-y-10">
              <div className="divide-y divide-zinc-100 rounded-xl border border-zinc-200 bg-white text-zinc-900 shadow-2xl shadow-black/30 ring-1 ring-white/10 print:shadow-none print:ring-0">
                {lead.length > 0 && (
                  <SortableSection
                    title="Relevant Nuggets"
                    items={lead}
                    onReorder={setLead}
                    onEdit={editNugget}
                    onDelete={deleteNugget}
                  />
                )}
                {g2k.length > 0 && (
                  <SortableSection
                    title="Relevant Insights"
                    items={g2k}
                    onReorder={setG2k}
                    onEdit={editNugget}
                    onDelete={deleteNugget}
                  />
                )}
                {newsletter.kept_count === 0 && (
                  <div className="p-10 text-center text-sm text-zinc-500">
                    No kept nuggets for this podcast.{" "}
                    <Link href="/episodes" className="text-teal-700 hover:underline print:hidden">
                      Review episodes →
                    </Link>
                  </div>
                )}
              </div>

              {stocks.length > 0 && (
                <div className="break-before-avoid">
                  <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
                    Stock read-through
                  </h3>
                  <div className="divide-y divide-zinc-100 overflow-hidden rounded-xl border border-zinc-200 bg-white text-zinc-900 shadow-2xl shadow-black/30 ring-1 ring-white/10 print:shadow-none print:ring-0">
                    {stocks.map((s) => (
                      <EditableStockRow
                        key={s.company}
                        s={s}
                        onEdit={(field, value) => editStock(s.company, field, value)}
                        onDelete={() => deleteStock(s.company)}
                      />
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
