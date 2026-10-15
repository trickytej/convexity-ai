"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Driver, QuestionStatus } from "@/lib/api";
import { draftTheses, putCompanyTheses } from "@/lib/api";
import { DRIVER_OPTIONS, driverLabel } from "@/lib/signals";
import { StatusDot } from "@/components/signals";

type EditableQuestion = {
  id?: number;
  question: string;
  note: string;
  drivers: Driver[];
  draft?: boolean;
  status?: QuestionStatus;
  signals?: number;
};

const driverKey = (d: Driver) => `${d.line}:${d.year ?? ""}`;

function DriverPicker({ drivers, onChange }: { drivers: Driver[]; onChange: (d: Driver[]) => void }) {
  const taken = new Set(drivers.map(driverKey));
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-[11px] text-zinc-600">Moves:</span>
      {drivers.map((d) => (
        <button
          key={driverKey(d)}
          onClick={() => onChange(drivers.filter((x) => driverKey(x) !== driverKey(d)))}
          title="Remove"
          className="rounded-full bg-[#00d4ff]/[0.08] px-2 py-0.5 text-[11px] text-[#00d4ff]/90 ring-1 ring-inset ring-[#00d4ff]/20 transition hover:text-rose-300 hover:ring-rose-500/30"
        >
          {driverLabel(d)} ×
        </button>
      ))}
      <select
        value=""
        onChange={(e) => {
          const d = DRIVER_OPTIONS.find((o) => driverKey(o) === e.target.value);
          if (d) onChange([...drivers, d]);
        }}
        className="rounded-full border border-white/[0.08] bg-transparent px-2 py-0.5 text-[11px] text-zinc-500 outline-none focus:border-[#00d4ff]/40"
      >
        <option value="">+ model line</option>
        {DRIVER_OPTIONS.filter((o) => !taken.has(driverKey(o))).map((o) => (
          <option key={driverKey(o)} value={driverKey(o)}>
            {driverLabel(o)}
          </option>
        ))}
      </select>
    </div>
  );
}

/** One security's "What Matters" questions: add, edit, remove, AI-draft, save. */
export default function QuestionsEditor({
  company,
  ticker,
  initial,
}: {
  company: string;
  ticker: string | null;
  initial: {
    id: number;
    question: string;
    note: string | null;
    drivers: Driver[];
    status?: QuestionStatus;
    signals?: number;
  }[];
}) {
  const router = useRouter();
  const [questions, setQuestions] = useState<EditableQuestion[]>(
    initial.length
      ? initial.map((q) => ({ ...q, note: q.note ?? "" }))
      : [{ question: "", note: "", drivers: [] }],
  );
  const [dirty, setDirty] = useState(false);
  // Compact read view by default; the full editor opens on demand (or straight
  // away when there are no questions yet).
  const [editing, setEditing] = useState(initial.length === 0);
  const [saving, setSaving] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [savedNote, setSavedNote] = useState("");
  const [error, setError] = useState("");

  function update(next: EditableQuestion[]) {
    setQuestions(next);
    setDirty(true);
    setSavedNote("");
  }

  async function handleDraft() {
    setDrafting(true);
    setError("");
    try {
      const res = await draftTheses(company, ticker);
      const existing = questions.filter((q) => q.question.trim() !== "");
      update([
        ...existing,
        ...res.questions.map((q) => ({
          question: q.question,
          note: q.note ?? "",
          drivers: q.drivers ?? [],
          draft: true,
        })),
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Draft failed");
    } finally {
      setDrafting(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const payload = questions
        .filter((q) => q.question.trim() !== "")
        .map((q) => ({
          id: q.id,
          question: q.question.trim(),
          note: q.note.trim() || null,
          drivers: q.drivers,
        }));
      const res = await putCompanyTheses({ company, ticker, questions: payload });
      const saved = res.companies.find((c) => c.company === company)?.questions ?? [];
      const prior = new Map(questions.filter((q) => q.id).map((q) => [q.id, q]));
      setQuestions(
        saved.map((q) => ({
          id: q.id,
          question: q.question,
          note: q.note ?? "",
          drivers: q.drivers ?? [],
          status: prior.get(q.id)?.status,
          signals: prior.get(q.id)?.signals,
        })),
      );
      setDirty(false);
      setEditing(false);
      setSavedNote(
        saved.length
          ? "Saved. Re-checking the last two days of research against these questions — new hits appear below shortly."
          : "Saved.",
      );
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!editing) {
    return (
      <div>
        <ol className="divide-y divide-white/[0.05] rounded-xl border border-white/[0.06] bg-[#0b0c10]/60">
          {questions.map((q, i) => (
            <li key={q.id ?? i} className="flex items-start gap-3 px-4 py-2.5">
              <span className="mt-1.5">{q.status ? <StatusDot status={q.status} /> : null}</span>
              <span className="mt-px font-[family-name:var(--font-mono)] text-[11px] text-zinc-600">Q{i + 1}</span>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] leading-snug text-zinc-200">{q.question}</p>
                {q.drivers.length > 0 && (
                  <p className="mt-0.5 text-[11px] text-[#00d4ff]/60">{q.drivers.map(driverLabel).join(" · ")}</p>
                )}
              </div>
              {q.signals ? (
                <span className="shrink-0 text-[11px] text-zinc-600">
                  {q.signals} signal{q.signals === 1 ? "" : "s"}
                </span>
              ) : null}
            </li>
          ))}
        </ol>
        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={() => setEditing(true)}
            className="rounded-full border border-white/[0.1] px-3.5 py-1.5 text-[12px] font-medium text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff]"
          >
            Edit questions
          </button>
          {savedNote && <p className="text-[12px] text-zinc-500">{savedNote}</p>}
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="space-y-3">
        {questions.map((q, i) => (
          <div
            key={q.id ?? `new-${i}`}
            className={`rounded-xl border p-4 ${
              q.draft ? "border-[#00d4ff]/25 bg-[#00d4ff]/[0.03]" : "border-white/[0.06] bg-[#0b0c10]/80"
            }`}
          >
            <div className="mb-2 flex items-center gap-2">
              {q.status && <StatusDot status={q.status} />}
              <span className="font-[family-name:var(--font-mono)] text-[11px] text-zinc-600">Q{i + 1}</span>
              {q.signals ? (
                <span className="text-[11px] text-zinc-600">
                  {q.signals} signal{q.signals === 1 ? "" : "s"} · 30d
                </span>
              ) : null}
              {q.draft && (
                <span className="rounded-full bg-[#00d4ff]/10 px-2 py-0.5 text-[10px] font-medium text-[#00d4ff]">
                  AI draft — edit or remove
                </span>
              )}
              <button
                onClick={() => update(questions.filter((_, j) => j !== i))}
                className="ml-auto text-[12px] text-zinc-700 transition hover:text-rose-400"
              >
                Remove
              </button>
            </div>
            <textarea
              value={q.question}
              onChange={(e) =>
                update(questions.map((x, j) => (j === i ? { ...x, question: e.target.value } : x)))
              }
              rows={2}
              placeholder="e.g. Is hyperscaler capex still accelerating?"
              className="w-full resize-none rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[14px] leading-relaxed text-zinc-200 outline-none placeholder:text-zinc-700 focus:border-[#00d4ff]/40"
            />
            <input
              value={q.note}
              onChange={(e) =>
                update(questions.map((x, j) => (j === i ? { ...x, note: e.target.value } : x)))
              }
              placeholder="Why it matters (optional)"
              className="mt-2 w-full rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-1.5 text-[12px] text-zinc-400 outline-none placeholder:text-zinc-700 focus:border-[#00d4ff]/40"
            />
            <DriverPicker
              drivers={q.drivers}
              onChange={(drivers) => update(questions.map((x, j) => (j === i ? { ...x, drivers } : x)))}
            />
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          onClick={() => update([...questions, { question: "", note: "", drivers: [] }])}
          className="rounded-full border border-white/[0.1] px-3.5 py-1.5 text-[12px] font-medium text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff]"
        >
          + Add question
        </button>
        <button
          onClick={handleDraft}
          disabled={drafting}
          className="flex items-center gap-2 rounded-full border border-[#00d4ff]/25 bg-[#00d4ff]/5 px-3.5 py-1.5 text-[12px] font-medium text-[#00d4ff] transition hover:bg-[#00d4ff]/10 disabled:opacity-50"
        >
          {drafting && (
            <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border border-[#00d4ff]/40 border-t-[#00d4ff]" />
          )}
          {drafting ? "Drafting…" : "Draft with AI"}
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          className="ml-auto rounded-full bg-[#00d4ff]/90 px-4 py-1.5 text-[12px] font-semibold text-black transition hover:bg-[#00d4ff] disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
      {drafting && (
        <p className="mt-3 text-[11px] text-zinc-600">
          Reading this company&apos;s recent insights and proposing questions — takes ~30s.
        </p>
      )}
      {savedNote && <p className="mt-3 text-[12px] text-zinc-500">{savedNote}</p>}
      {error && <p className="mt-3 text-[12px] text-rose-400">{error}</p>}
    </div>
  );
}
