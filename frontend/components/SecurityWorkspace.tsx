"use client";

import Link from "next/link";
import { useMemo, useRef, useState } from "react";
import type { FeedHit, FinModel, HitDecision, SourceClass } from "@/lib/api";
import { decideHit } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { SOURCE_LABEL } from "@/lib/signals";
import FinModelSheet, { type CellTone, type SheetHighlight } from "@/components/FinModelSheet";

type View = "signals" | "review" | "kept" | "all";

const VIEWS: { id: View; label: string }[] = [
  { id: "signals", label: "Signals" },
  { id: "review", label: "To review" },
  { id: "kept", label: "Kept" },
  { id: "all", label: "Everything" },
];

const PAGE = 25;

const DIRECTION_CLS: Record<string, string> = {
  supports: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25",
  contradicts: "bg-rose-500/10 text-rose-300 ring-rose-500/25",
  unclear: "bg-amber-400/10 text-amber-300 ring-amber-400/25",
};

const TONE_TEXT: Record<CellTone, string> = {
  green: "text-emerald-300",
  yellow: "text-amber-300",
  red: "text-rose-300",
};

/** How a development moves its model line: green = up, red = down,
 * yellow = relevant but mixed / direction unclear. */
function toneFor(h: FeedHit): CellTone | null {
  if (!h.impact) return null;
  return h.direction === "unclear" ? "yellow" : h.impact.direction === "up" ? "green" : "red";
}

const SHOW_LABEL: Record<string, string> = { research: "Your research", "sec-filings": "SEC filing", x: "X" };

function byline(h: FeedHit): string {
  const who = h.nugget.speaker_name && h.nugget.speaker_name.toLowerCase() !== "unknown" ? `${h.nugget.speaker_name} · ` : "";
  const date = h.nugget.published_at ? ` · ${fmtDate(h.nugget.published_at)}` : "";
  return `${who}${SHOW_LABEL[h.nugget.show_slug] ?? h.nugget.show_slug}${date}`;
}

function hitSourceHref(h: FeedHit): string | null {
  if (h.nugget.tweet_url) return h.nugget.tweet_url;
  return null;
}

export default function SecurityWorkspace({
  securityKey,
  company,
  isAdmin,
  locked = false,
  numbers,
  feed,
  questions,
  whatMatters,
}: {
  securityKey: string;
  company: string;
  isAdmin: boolean;
  locked?: boolean;
  numbers: FinModel | null;
  feed: FeedHit[];
  questions: { id: number; question: string }[];
  /** The What Matters editor, rendered between the model and the feed. */
  whatMatters?: React.ReactNode;
}) {
  const [items, setItems] = useState(feed);
  const [view, setView] = useState<View>("signals");
  const [source, setSource] = useState<SourceClass | "any">("any");
  const [questionId, setQuestionId] = useState<number | "any">("any");
  const [limit, setLimit] = useState(PAGE);
  const [selected, setSelected] = useState<number | null>(null);
  const modelRef = useRef<HTMLDivElement>(null);
  const feedRef = useRef<HTMLDivElement>(null);

  const visible = useMemo(
    () =>
      items.filter(
        (h) =>
          (view === "all" ||
            (view === "signals" && h.tier === "signal") ||
            (view === "review" && h.decision === "pending" && h.tier === "signal") ||
            (view === "kept" && h.decision === "kept")) &&
          (source === "any" || h.source_class === source) &&
          (questionId === "any" || h.question_id === questionId),
      ),
    [items, view, source, questionId],
  );

  const counts = useMemo(() => {
    const c = { print: 0, chatter: 0, inside: 0 } as Record<SourceClass, number>;
    for (const h of items) if (h.tier === "signal") c[h.source_class] += 1;
    return c;
  }, [items]);

  const selectedHit = items.find((h) => h.hit_id === selected) ?? null;
  const selectedTone = selectedHit ? toneFor(selectedHit) : null;
  const cells =
    selectedHit?.impact && numbers
      ? numbers.impact_cells[`${selectedHit.impact.line}:${selectedHit.impact.year ?? ""}`]
      : undefined;
  const highlight: SheetHighlight = cells && selectedTone ? { ...cells, tone: selectedTone } : null;

  function select(h: FeedHit) {
    const next = selected === h.hit_id ? null : h.hit_id;
    setSelected(next);
    if (next) modelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function decide(h: FeedHit, decision: HitDecision) {
    const prev = items;
    setItems((xs) =>
      decision === "dropped" ? xs.filter((x) => x.hit_id !== h.hit_id) : xs.map((x) => (x.hit_id === h.hit_id ? { ...x, decision } : x)),
    );
    try {
      await decideHit(h.hit_id, decision);
    } catch {
      setItems(prev);
    }
  }

  const chip = (active: boolean) =>
    `rounded-full border px-3 py-1 text-[12px] transition ${
      active
        ? "border-[#00d4ff]/40 bg-[#00d4ff]/8 text-[#00d4ff]"
        : "border-white/[0.06] text-zinc-500 hover:border-white/[0.14] hover:text-zinc-300"
    }`;

  return (
    <div>
      {/* ── model ── */}
      <section ref={modelRef} className="mt-10 scroll-mt-20">
        <div className="mb-3 flex flex-wrap items-baseline gap-3">
          <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
            <span className="inline-block h-px w-8 bg-[#00d4ff]/50" />
            <span className="text-zinc-400">Model</span>
          </p>
        </div>
        <FinModelSheet securityKey={securityKey} company={company} initial={numbers} isAdmin={isAdmin} highlight={highlight} locked={locked} />
      </section>

      {whatMatters}

      {/* floating explainer while a development is selected */}
      {selectedHit && (
        <div className="fixed inset-x-0 bottom-4 z-40 mx-auto flex w-[min(720px,calc(100%-2rem))] items-start gap-3 rounded-xl border border-white/[0.12] bg-[#0b0c10]/95 p-3.5 shadow-2xl backdrop-blur">
          <div className="min-w-0 flex-1">
            <p className="text-[12px]">
              {selectedHit.impact ? (
                <>
                  <span className="text-zinc-500">Moves </span>
                  <span className={TONE_TEXT[selectedTone ?? "yellow"]}>
                    {selectedHit.impact.label} {selectedHit.impact.direction === "up" ? "↑" : "↓"}
                    {selectedTone === "yellow" && " (mixed)"}
                  </span>
                  {!cells && <span className="text-zinc-600"> — not in this model&apos;s window</span>}
                </>
              ) : (
                <span className="text-zinc-500">Not tied to a specific model line</span>
              )}
            </p>
            <p className="mt-1 line-clamp-2 text-[13px] text-zinc-300">{selectedHit.nugget.claim}</p>
          </div>
          <button
            onClick={() => feedRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
            className="shrink-0 rounded-full border border-white/[0.12] px-3 py-1 text-[11px] text-zinc-300 hover:text-[#00d4ff]"
          >
            Back to list ↓
          </button>
          <button onClick={() => setSelected(null)} className="shrink-0 px-1 text-[14px] text-zinc-500 hover:text-zinc-200">
            ×
          </button>
        </div>
      )}

      {/* ── nugget feed ── */}
      <section ref={feedRef} className="mt-14 scroll-mt-20 pb-24">
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]/50" />
          <span className="text-zinc-400">Developments · last 90 days</span>
        </p>
        <p className="mt-2 text-[12px] text-zinc-600">
          Click one to see which part of the model it moves.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-2">
          {VIEWS.map((v) => (
            <button key={v.id} onClick={() => { setView(v.id); setLimit(PAGE); }} className={chip(view === v.id)}>
              {v.label}
            </button>
          ))}
          <span className="mx-2 h-4 w-px bg-white/[0.08]" />
          <button onClick={() => setSource("any")} className={chip(source === "any")}>All sources</button>
          {(["print", "chatter", "inside"] as SourceClass[]).map((s) => (
            <button key={s} onClick={() => setSource(s)} className={chip(source === s)}>
              {SOURCE_LABEL[s]} <span className="ml-0.5 text-zinc-600">{counts[s]}</span>
            </button>
          ))}
          {questions.length > 1 && (
            <select
              value={questionId}
              onChange={(e) => setQuestionId(e.target.value === "any" ? "any" : Number(e.target.value))}
              className="max-w-xs rounded-full border border-white/[0.06] bg-[#0a0a0c] px-3 py-1 text-[12px] text-zinc-400 outline-none focus:border-[#00d4ff]/40"
            >
              <option value="any">All questions</option>
              {questions.map((q, i) => (
                <option key={q.id} value={q.id}>
                  Q{i + 1}: {q.question.length > 60 ? q.question.slice(0, 60) + "…" : q.question}
                </option>
              ))}
            </select>
          )}
        </div>

        {visible.length === 0 ? (
          <p className="mt-8 text-[13px] text-zinc-600">
            {items.length === 0 ? "Nothing yet — add questions above to start tracking." : "Nothing matches these filters."}
          </p>
        ) : (
          <ul className="mt-5 space-y-2">
            {visible.slice(0, limit).map((h) => {
              const signal = h.tier === "signal";
              const isSel = selected === h.hit_id;
              const hl = toneFor(h);
              const external = hitSourceHref(h);
              return (
                <li
                  key={h.hit_id}
                  onClick={() => select(h)}
                  className={`cursor-pointer rounded-xl border p-3.5 transition ${
                    isSel
                      ? "border-[#00d4ff]/50 bg-[#00d4ff]/[0.05]"
                      : signal
                        ? "border-white/[0.07] bg-[#0b0c10]/90 hover:border-white/[0.16]"
                        : "border-white/[0.04] bg-[#0b0c10]/50 hover:border-white/[0.12]"
                  }`}
                >
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    {signal ? (
                      <span className={`rounded-full px-2 py-0.5 font-medium ring-1 ring-inset ${DIRECTION_CLS[h.direction]}`}>
                        {h.direction}
                      </span>
                    ) : (
                      <span className="rounded-full px-2 py-0.5 font-medium text-zinc-500 ring-1 ring-inset ring-white/10">reference</span>
                    )}
                    {h.impact && (
                      <span className={`rounded-full bg-white/[0.04] px-2 py-0.5 font-medium ${hl ? TONE_TEXT[hl] : ""}`}>
                        {h.impact.label} {h.impact.direction === "up" ? "↑" : "↓"}
                      </span>
                    )}
                    <span className="text-zinc-500">{SOURCE_LABEL[h.source_class]}</span>
                    {h.decision === "kept" && <span className="text-[#00d4ff]/80">● kept</span>}
                    <span className="ml-auto text-zinc-600">{byline(h)}</span>
                  </div>
                  <p className={`mt-2 text-[14px] leading-relaxed ${signal ? "text-zinc-200" : "text-zinc-400"}`}>{h.nugget.claim}</p>
                  {isSel && h.why && <p className="mt-1.5 text-[13px] leading-relaxed text-[#00d4ff]/90">{h.why}</p>}
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <span className="truncate text-[11px] text-zinc-600">↳ {h.question}</span>
                    <span className="ml-auto flex shrink-0 gap-2" onClick={(e) => e.stopPropagation()}>
                      {external && (
                        <Link href={external} target="_blank" rel="noopener noreferrer" className="px-1 py-1 text-[11px] text-zinc-600 hover:text-[#00d4ff]">
                          Post ↗
                        </Link>
                      )}
                      {h.decision === "kept" ? (
                        <button onClick={() => decide(h, "pending")} className="rounded-full border border-white/[0.1] px-3 py-1 text-[11px] text-zinc-500 hover:text-zinc-300">
                          Un-keep
                        </button>
                      ) : (
                        <>
                          <button onClick={() => decide(h, "dropped")} className="rounded-full border border-white/[0.1] px-3 py-1 text-[11px] text-zinc-500 hover:border-rose-500/40 hover:text-rose-300">
                            Drop
                          </button>
                          <button onClick={() => decide(h, "kept")} className="rounded-full bg-[#00d4ff]/90 px-3 py-1 text-[11px] font-semibold text-black hover:bg-[#00d4ff]">
                            Keep
                          </button>
                        </>
                      )}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {visible.length > limit && (
          <button onClick={() => setLimit((l) => l + PAGE)} className="mt-4 text-[12px] text-zinc-500 hover:text-[#00d4ff]">
            Show more ({visible.length - limit} more)
          </button>
        )}
      </section>
    </div>
  );
}
