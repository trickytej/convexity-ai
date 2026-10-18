"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { Brain, BrainSecurity, Position, QuestionStatus, SourceClass } from "@/lib/api";
import { getBrain, setPosition } from "@/lib/api";
import { SOURCE_LABEL } from "@/lib/signals";

const REFRESH_MS = 60_000;

const ORB: Record<QuestionStatus, string> = {
  green: "bg-emerald-400 shadow-[0_0_18px_4px] shadow-emerald-400/50",
  yellow: "bg-amber-300 shadow-[0_0_18px_4px] shadow-amber-300/40",
  red: "bg-rose-500 shadow-[0_0_18px_4px] shadow-rose-500/50",
  none: "bg-zinc-700",
};
const RING: Record<QuestionStatus, string> = {
  green: "border-emerald-400/40",
  yellow: "border-amber-300/40",
  red: "border-rose-500/40",
  none: "border-white/[0.06]",
};
const WORD: Record<QuestionStatus, string> = { green: "Supporting", yellow: "Mixed", red: "Contradicting", none: "Quiet" };

function ago(iso: string | null | undefined): string {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return `${Math.round(s / 86400)}d`;
}

function pct(x: number | null | undefined): string {
  if (x == null) return "—";
  if (x >= 2) return `${(x + 1).toFixed(1)}×`;
  return `${x >= 0 ? "+" : ""}${Math.round(x * 100)}%`;
}

/** Signal velocity → heat (dim for decelerating, cyan steady, amber/red hot). */
function heat(acc: number | null): string {
  if (acc == null) return "border-white/[0.08] bg-white/[0.02] text-zinc-400";
  if (acc >= 1) return "border-orange-400/50 bg-orange-500/[0.12] text-orange-200 shadow-[0_0_24px] shadow-orange-500/20";
  if (acc >= 0.25) return "border-amber-300/40 bg-amber-400/[0.08] text-amber-100";
  if (acc > -0.25) return "border-[#00d4ff]/25 bg-[#00d4ff]/[0.05] text-cyan-100";
  return "border-white/[0.06] bg-white/[0.015] text-zinc-500";
}

function Orb({ status, pulse }: { status: QuestionStatus; pulse?: boolean }) {
  return (
    <span className="relative inline-flex h-3.5 w-3.5 shrink-0">
      {pulse && <span className={`absolute inset-0 animate-ping rounded-full opacity-60 ${ORB[status].split(" ")[0]}`} />}
      <span className={`relative inline-block h-3.5 w-3.5 rounded-full ${ORB[status]}`} />
    </span>
  );
}

function ClassBar({ cls, v }: { cls: SourceClass; v: { supports: number; contradicts: number } }) {
  const total = v.supports + v.contradicts;
  return (
    <div className="w-20">
      <div className="flex justify-between text-[9px] uppercase tracking-[0.14em] text-zinc-600">
        <span>{SOURCE_LABEL[cls]}</span>
        <span className="tabular-nums">{total || "—"}</span>
      </div>
      <div className="mt-1 flex h-1.5 overflow-hidden rounded-full bg-white/[0.05]">
        {total > 0 && (
          <>
            <span className="bg-emerald-400/80" style={{ width: `${(v.supports / total) * 100}%` }} />
            <span className="bg-rose-500/80" style={{ width: `${(v.contradicts / total) * 100}%` }} />
          </>
        )}
      </div>
    </div>
  );
}

function PositionToggle({ s, onChange }: { s: BrainSecurity; onChange: (p: Position) => void }) {
  const btn = (p: Position, label: string, cls: string) => (
    <button
      onClick={(e) => {
        e.preventDefault();
        onChange(s.position === p ? null : p);
      }}
      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold tracking-wide transition ${
        s.position === p ? cls : "text-zinc-600 hover:text-zinc-300"
      }`}
    >
      {label}
    </button>
  );
  return (
    <span className="inline-flex rounded-md border border-white/[0.08] bg-black/30 p-0.5">
      {btn("long", "LONG", "bg-emerald-500/20 text-emerald-300")}
      {btn("short", "SHORT", "bg-rose-500/20 text-rose-300")}
    </span>
  );
}

function SecurityRow({ s, onPosition }: { s: BrainSecurity; onPosition: (p: Position) => void }) {
  const [open, setOpen] = useState(false);
  const flipped = s.flips.length > 0;
  return (
    <div
      className={`rounded-xl border bg-[#0b0d12]/80 backdrop-blur transition hover:bg-[#0e1118]/90 ${RING[s.display_status]} ${
        flipped ? "ring-1 ring-[#00d4ff]/40" : ""
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3 px-4 py-3">
        <Orb status={s.display_status} pulse={flipped} />
        <Link href={`/model/${encodeURIComponent(s.key)}`} className="min-w-[9rem] group">
          <span className="font-[family-name:var(--font-mono)] text-[15px] font-semibold text-zinc-50 transition group-hover:text-[#00d4ff]">
            {s.ticker ?? s.company}
          </span>
          <span className="ml-2 text-[12px] text-zinc-500">{s.ticker ? s.company : ""}</span>
          <p className="text-[11px] text-zinc-500">
            {WORD[s.display_status]}
            {s.position === "short" && s.status !== "none" ? " (for your short)" : ""} · {s.signals_7d} this week ·{" "}
            {s.signals_30d} in 30d
          </p>
        </Link>
        <PositionToggle s={s} onChange={onPosition} />
        <div className="flex gap-3">
          {(["print", "chatter", "inside"] as SourceClass[]).map((c) => (
            <ClassBar key={c} cls={c} v={s.by_class[c]} />
          ))}
        </div>
        <div className="flex flex-1 flex-wrap justify-end gap-1.5">
          {s.ahead_of_print.slice(0, 2).map((f) => (
            <span
              key={`${f.line}${f.year}`}
              title={f.note}
              className="rounded-full border border-amber-300/40 bg-amber-400/10 px-2 py-0.5 text-[11px] font-medium text-amber-200 shadow-[0_0_14px] shadow-amber-400/20"
            >
              ⚑ {f.label} {f.net > 0 ? "↑" : "↓"}
            </span>
          ))}
          {s.impacts.slice(0, 3).map((i) => (
            <span key={`${i.line}${i.year}`} className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[11px] text-zinc-400">
              {i.label} <span className="text-emerald-300">{i.up}↑</span>
              {i.down > 0 && <span className="ml-0.5 text-rose-300">{i.down}↓</span>}
            </span>
          ))}
        </div>
        <button onClick={() => setOpen((v) => !v)} className="text-[11px] text-zinc-600 hover:text-zinc-300">
          {open ? "▴" : "▾"}
        </button>
      </div>
      {flipped && (
        <div className="border-t border-white/[0.04] px-4 py-1.5 text-[11px] text-[#00d4ff]/80">
          {s.flips.map((f, i) => (
            <span key={i} className="mr-4">
              ↻ {f.from} → {f.to} {ago(f.at)} ago · <span className="text-zinc-500">{f.question}</span>
            </span>
          ))}
        </div>
      )}
      {open && (
        <div className="space-y-1.5 border-t border-white/[0.04] px-4 py-3">
          {s.ahead_of_print.map((f) => (
            <p key={`n${f.line}${f.year}`} className="text-[12px] text-amber-200/90">
              ⚑ {f.note}
            </p>
          ))}
          {s.questions.map((q) => (
            <p key={q.id} className="flex items-start gap-2 text-[12px] text-zinc-300">
              <span className="mt-1">
                <span className={`inline-block h-2 w-2 rounded-full ${ORB[q.status].split(" ")[0]}`} />
              </span>
              {q.question}
            </p>
          ))}
          {!s.questions.length && <p className="text-[12px] text-zinc-600">No questions yet.</p>}
        </div>
      )}
    </div>
  );
}

function Callout({
  label,
  sec,
  tone,
  hint,
}: {
  label: string;
  sec: { company: string; ticker: string | null; key: string } | null;
  tone: "green" | "red";
  hint?: string;
}) {
  const cls =
    tone === "green"
      ? "border-emerald-400/30 bg-emerald-500/[0.06] shadow-[0_0_40px] shadow-emerald-500/10"
      : "border-rose-500/30 bg-rose-500/[0.06] shadow-[0_0_40px] shadow-rose-500/10";
  return (
    <div className={`rounded-2xl border p-4 ${cls}`}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-400">{label}</p>
      {sec ? (
        <Link href={`/model/${encodeURIComponent(sec.key)}`} className="mt-1 block">
          <span className="font-[family-name:var(--font-mono)] text-2xl font-semibold text-zinc-50">{sec.ticker ?? sec.company}</span>
          <span className="ml-2 text-[12px] text-zinc-400">{sec.ticker ? sec.company : ""}</span>
        </Link>
      ) : (
        <p className="mt-1 text-[13px] text-zinc-500">—</p>
      )}
      {hint && <p className="mt-1 text-[11px] text-zinc-500">{hint}</p>}
    </div>
  );
}

export default function CioBrain({ initial }: { initial: Brain }) {
  const [brain, setBrain] = useState(initial);
  const [updated, setUpdated] = useState(new Date());

  const refresh = useCallback(async () => {
    try {
      setBrain(await getBrain({ touch: false }));
      setUpdated(new Date());
    } catch {
      /* keep the last good screen */
    }
  }, []);

  useEffect(() => {
    const t = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(t);
  }, [refresh]);

  async function changePosition(s: BrainSecurity, p: Position) {
    setBrain((b) => ({
      ...b,
      securities: b.securities.map((x) =>
        x.company === s.company
          ? { ...x, position: p, display_status: p === "short" ? ({ green: "red", red: "green" } as Record<string, QuestionStatus>)[x.status] ?? x.status : x.status }
          : x,
      ),
    }));
    await setPosition(s.company, p).catch(refresh);
    refresh();
  }

  const byCategory = brain.securities.reduce<Record<string, BrainSecurity[]>>((acc, s) => {
    (acc[s.category] ||= []).push(s);
    return acc;
  }, {});
  const sectorMeta = Object.fromEntries(brain.sectors.map((s) => [s.category, s]));
  const flags = brain.securities.reduce((n, s) => n + s.ahead_of_print.length, 0);
  const since = brain.since_last_visit;

  return (
    <div className="relative">
      {/* scan-line backdrop */}
      <div className="pointer-events-none fixed inset-0 top-14 z-0 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(0,212,255,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(0,212,255,0.035)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_75%)]" />
        <div className="absolute inset-x-0 h-40 animate-[scan_7s_linear_infinite] bg-gradient-to-b from-transparent via-[#00d4ff]/[0.05] to-transparent" />
      </div>
      <style>{`@keyframes scan { from { transform: translateY(-10rem) } to { transform: translateY(100vh) } }`}</style>

      <div className="relative z-10">
        {/* ── masthead ── */}
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
              <span className="inline-block h-px w-8 bg-[#00d4ff]" />
              <span className="text-[#00d4ff]">CIO</span>
            </p>
            <h1 className="mt-3 text-5xl font-light leading-[1.04] tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-6xl">
              Where the evidence <span className="text-[#00d4ff]">is moving</span>.
            </h1>
            <p className="mt-3 text-[14px] text-zinc-400">
              Consensus in print · consensus in chatter · your inside view — weighed against what decides each position.
            </p>
          </div>
          <div className="text-right">
            <p className="flex items-center justify-end gap-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              Live
            </p>
            <p className="mt-1 font-[family-name:var(--font-mono)] text-[11px] text-zinc-500">
              updated {updated.toLocaleTimeString()} · refreshes every minute
            </p>
            {since.last_visit && (since.new_signals > 0 || since.flips > 0) && (
              <p className="mt-2 inline-block rounded-full border border-[#00d4ff]/30 bg-[#00d4ff]/10 px-3 py-1 text-[12px] text-[#00d4ff]">
                Since your last visit: {since.new_signals} new signal{since.new_signals === 1 ? "" : "s"} · {since.flips} flip
                {since.flips === 1 ? "" : "s"}
              </p>
            )}
          </div>
        </div>

        {/* ── narrative velocity ── */}
        <section className="mt-10">
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">
            Narrative velocity · high-signal chatter this week vs its 4-week run-rate
          </p>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {brain.velocity.slice(0, 12).map((v) => (
              <div key={v.sector} className={`rounded-xl border px-3 py-2.5 transition ${heat(v.acceleration)}`}>
                <p className="truncate text-[12px] font-medium">{v.sector}</p>
                <p className="mt-1 flex items-baseline justify-between font-[family-name:var(--font-mono)]">
                  <span className="text-lg tabular-nums">{v.last7}</span>
                  <span className="text-[11px]">
                    {v.acceleration != null && v.acceleration >= 0 ? "▲" : v.acceleration != null ? "▼" : ""} {pct(v.acceleration)}
                  </span>
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ── callouts ── */}
        <section className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Callout label="Best long" sec={brain.best_long} tone="green" hint="Strongest supporting evidence among your longs" />
          <Callout
            label={brain.best_short ? "Best short" : "Short candidate"}
            sec={brain.best_short ?? brain.short_candidate}
            tone="red"
            hint={brain.best_short ? "Most contradicting evidence on your shorts" : "Weakest evidence among names you follow"}
          />
          <div className="rounded-2xl border border-amber-300/30 bg-amber-400/[0.05] p-4 shadow-[0_0_40px] shadow-amber-400/10">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-400">Ahead of print</p>
            <p className="mt-1 font-[family-name:var(--font-mono)] text-2xl font-semibold text-amber-200">⚑ {flags}</p>
            <p className="mt-1 text-[11px] text-zinc-500">Evidence building on a model line that consensus hasn&apos;t moved on</p>
          </div>
        </section>

        <div className="mt-10 grid grid-cols-1 gap-8 xl:grid-cols-[1fr_22rem]">
          {/* ── board ── */}
          <section className="space-y-8">
            {Object.keys(byCategory).length === 0 && (
              <p className="text-[14px] text-zinc-500">
                Follow securities on the <Link href="/model" className="text-[#00d4ff]">Model</Link> tab to light up the board.
              </p>
            )}
            {Object.entries(byCategory).map(([cat, secs]) => {
              const meta = sectorMeta[cat];
              return (
                <div key={cat}>
                  <div className="mb-3 flex items-center gap-3">
                    {meta && <Orb status={meta.status} />}
                    <h2 className="text-lg font-light tracking-tight text-zinc-100 [font-family:var(--font-display)]">{cat}</h2>
                    {meta && (
                      <span className="font-[family-name:var(--font-mono)] text-[11px] text-zinc-500">
                        {meta.signals_7d} signals this week ·{" "}
                        <span className={meta.acceleration != null && meta.acceleration > 0 ? "text-amber-300" : ""}>
                          {pct(meta.acceleration)} vs run-rate
                        </span>
                      </span>
                    )}
                  </div>
                  <div className="space-y-2">
                    {secs.map((s) => (
                      <SecurityRow key={s.company} s={s} onPosition={(p) => changePosition(s, p)} />
                    ))}
                  </div>
                </div>
              );
            })}
          </section>

          {/* ── signal tape ── */}
          <aside className="xl:sticky xl:top-20 xl:max-h-[calc(100vh-6rem)] xl:overflow-y-auto">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-500">Signal tape</p>
            <ul className="mt-3 space-y-2">
              {brain.tape.map((t) => (
                <li
                  key={t.hit_id}
                  className={`border-l-2 bg-white/[0.015] py-2 pl-3 pr-2 ${
                    t.direction === "supports" ? "border-emerald-400/70" : t.direction === "contradicts" ? "border-rose-500/70" : "border-amber-300/60"
                  }`}
                >
                  <p className="flex items-center gap-2 text-[11px]">
                    <span className="font-[family-name:var(--font-mono)] font-semibold text-zinc-200">{t.ticker ?? t.company}</span>
                    {t.impact && <span className="text-[#00d4ff]/80">{t.impact}</span>}
                    {t.new && <span className="rounded bg-[#00d4ff]/20 px-1 text-[9px] font-bold text-[#00d4ff]">NEW</span>}
                    <span className="ml-auto text-zinc-600">
                      {SOURCE_LABEL[t.source_class]} · {ago(t.published_at)}
                    </span>
                  </p>
                  <p className="mt-1 line-clamp-3 text-[12px] leading-snug text-zinc-300">{t.claim}</p>
                </li>
              ))}
              {!brain.tape.length && <p className="text-[12px] text-zinc-600">No signals in the last 30 days yet.</p>}
            </ul>
          </aside>
        </div>
      </div>
    </div>
  );
}
