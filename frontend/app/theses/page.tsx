"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  draftTheses, getScoutWatchlist, getTheses, putCompanyTheses,
  type CompanyTheses,
} from "@/lib/api";

type EditableQuestion = { id?: number; question: string; note: string; draft?: boolean };

type WatchCompany = { name: string; ticker?: string };

export default function ThesesPage() {
  const [watchCompanies, setWatchCompanies] = useState<WatchCompany[]>([]);
  const [saved, setSaved] = useState<CompanyTheses[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, EditableQuestion[]>>({});
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getScoutWatchlist(), getTheses()])
      .then(([watchlist, theses]) => {
        const seen = new Set<string>();
        const companies: WatchCompany[] = [];
        for (const cat of watchlist) {
          for (const co of cat.companies) {
            const key = co.name.trim().toLowerCase();
            if (!key || seen.has(key)) continue;
            seen.add(key);
            companies.push({ name: co.name, ticker: co.ticker });
          }
        }
        companies.sort((a, b) => a.name.localeCompare(b.name));
        setWatchCompanies(companies);
        setSaved(theses.companies);
        if (theses.companies.length > 0) setSelected(theses.companies[0].company);
      })
      .catch(() => setError("Could not load — is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  const tickerFor = (company: string): string | undefined =>
    watchCompanies.find((w) => w.name === company)?.ticker ??
    saved.find((s) => s.company === company)?.ticker ??
    undefined;

  const questionsFor = (company: string): EditableQuestion[] => {
    if (edits[company]) return edits[company];
    const block = saved.find((s) => s.company === company);
    return (block?.questions ?? []).map((q) => ({
      id: q.id,
      question: q.question,
      note: q.note ?? "",
    }));
  };

  function updateQuestions(company: string, next: EditableQuestion[]) {
    setEdits((e) => ({ ...e, [company]: next }));
    setDirty((d) => ({ ...d, [company]: true }));
  }

  const thesisCompanies = useMemo(() => {
    const names = new Set(saved.map((s) => s.company));
    Object.keys(edits).forEach((c) => names.add(c));
    return [...names].sort((a, b) => a.localeCompare(b));
  }, [saved, edits]);

  const addable = watchCompanies.filter(
    (w) => !thesisCompanies.some((c) => c.toLowerCase() === w.name.toLowerCase()),
  );

  function addCompany(name: string) {
    if (!name) return;
    setEdits((e) => ({ ...e, [name]: [{ question: "", note: "" }] }));
    setSelected(name);
  }

  async function handleDraft() {
    if (!selected) return;
    setDrafting(true);
    setError("");
    try {
      const { questions } = await draftTheses(selected, tickerFor(selected));
      const existing = questionsFor(selected).filter((q) => q.question.trim() !== "");
      updateQuestions(selected, [
        ...existing,
        ...questions.map((q) => ({ question: q.question, note: q.note ?? "", draft: true })),
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Draft failed");
    } finally {
      setDrafting(false);
    }
  }

  async function handleSave() {
    if (!selected) return;
    setSaving(true);
    setError("");
    try {
      const payload = questionsFor(selected)
        .filter((q) => q.question.trim() !== "")
        .map((q) => ({ id: q.id, question: q.question.trim(), note: q.note.trim() || null }));
      const res = await putCompanyTheses({
        company: selected,
        ticker: tickerFor(selected) ?? null,
        questions: payload,
      });
      setSaved(res.companies);
      setEdits((e) => {
        const next = { ...e };
        delete next[selected];
        return next;
      });
      setDirty((d) => ({ ...d, [selected]: false }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const questions = selected ? questionsFor(selected) : [];

  return (
    <div>
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">What Matters</span>
      </p>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
          The 4–5 questions per <span className="text-[#00d4ff]">stock</span>
        </h1>
        <Link
          href="/brief"
          className="rounded-full border border-white/[0.1] px-3.5 py-1.5 text-[12px] font-medium text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff]"
        >
          View Brief →
        </Link>
      </div>
      <p className="mt-4 max-w-2xl text-[14px] leading-relaxed text-zinc-500">
        Write the key questions that decide each investment. New podcast insights,
        newsletters, and X posts are weighed against them automatically, and anything
        material lands on your morning Brief.
      </p>

      {error && <p className="mt-4 text-[13px] text-rose-400">{error}</p>}
      {loading ? (
        <p className="mt-10 text-sm text-zinc-600">Loading…</p>
      ) : (
        <div className="mt-10 flex flex-col gap-8 md:flex-row">
          {/* company rail */}
          <aside className="w-full shrink-0 md:w-60">
            <div className="space-y-1">
              {thesisCompanies.map((c) => (
                <button
                  key={c}
                  onClick={() => setSelected(c)}
                  className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-[13px] transition ${
                    selected === c
                      ? "bg-[#00d4ff]/10 text-[#00d4ff]"
                      : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200"
                  }`}
                >
                  <span className="truncate">{c}</span>
                  {dirty[c] && <span className="ml-2 text-[10px] text-amber-400">●</span>}
                </button>
              ))}
            </div>
            {addable.length > 0 && (
              <select
                value=""
                onChange={(e) => addCompany(e.target.value)}
                className="mt-4 w-full rounded-lg border border-white/[0.08] bg-[#0b0c10] px-3 py-2 text-[13px] text-zinc-400 outline-none focus:border-[#00d4ff]/40"
              >
                <option value="">+ Add company…</option>
                {addable.map((w) => (
                  <option key={w.name} value={w.name}>
                    {w.name}
                    {w.ticker ? ` (${w.ticker})` : ""}
                  </option>
                ))}
              </select>
            )}
            <p className="mt-2 text-[11px] leading-relaxed text-zinc-700">
              Companies come from the Scout watchlist.
            </p>
          </aside>

          {/* editor */}
          <div className="min-w-0 flex-1">
            {!selected ? (
              <p className="text-[14px] text-zinc-600">
                Pick a company — or add one from the watchlist — to write its questions.
              </p>
            ) : (
              <div>
                <div className="mb-5 flex items-baseline gap-3">
                  <h2 className="text-2xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
                    {selected}
                  </h2>
                  {tickerFor(selected) && (
                    <span className="font-[family-name:var(--font-mono)] text-xs text-zinc-500">
                      {tickerFor(selected)}
                    </span>
                  )}
                </div>

                <div className="space-y-4">
                  {questions.map((q, i) => (
                    <div
                      key={q.id ?? `new-${i}`}
                      className={`rounded-xl border p-4 ${
                        q.draft
                          ? "border-[#00d4ff]/25 bg-[#00d4ff]/[0.03]"
                          : "border-white/[0.06] bg-[#0b0c10]/80"
                      }`}
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <span className="font-[family-name:var(--font-mono)] text-[11px] text-zinc-600">
                          Q{i + 1}
                        </span>
                        {q.draft && (
                          <span className="rounded-full bg-[#00d4ff]/10 px-2 py-0.5 text-[10px] font-medium text-[#00d4ff]">
                            AI draft — edit or remove
                          </span>
                        )}
                        <button
                          onClick={() =>
                            updateQuestions(selected, questions.filter((_, j) => j !== i))
                          }
                          className="ml-auto text-[12px] text-zinc-700 transition hover:text-rose-400"
                        >
                          Remove
                        </button>
                      </div>
                      <textarea
                        value={q.question}
                        onChange={(e) =>
                          updateQuestions(
                            selected,
                            questions.map((x, j) => (j === i ? { ...x, question: e.target.value } : x)),
                          )
                        }
                        rows={2}
                        placeholder="e.g. Is hyperscaler capex still accelerating?"
                        className="w-full resize-none rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[14px] leading-relaxed text-zinc-200 outline-none placeholder:text-zinc-700 focus:border-[#00d4ff]/40"
                      />
                      <input
                        value={q.note}
                        onChange={(e) =>
                          updateQuestions(
                            selected,
                            questions.map((x, j) => (j === i ? { ...x, note: e.target.value } : x)),
                          )
                        }
                        placeholder="Why it matters (optional)"
                        className="mt-2 w-full rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-1.5 text-[12px] text-zinc-400 outline-none placeholder:text-zinc-700 focus:border-[#00d4ff]/40"
                      />
                    </div>
                  ))}
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-3">
                  <button
                    onClick={() =>
                      updateQuestions(selected, [...questions, { question: "", note: "" }])
                    }
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
                    disabled={saving || !dirty[selected]}
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
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
