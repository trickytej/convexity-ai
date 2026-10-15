"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import type { ImportResult } from "@/lib/api";
import { adminImportHouseQuestions, adminImportModels } from "@/lib/api";

function Results({ rows }: { rows: ImportResult[] }) {
  if (!rows.length) return null;
  return (
    <ul className="mt-3 space-y-1 text-[12px]">
      {rows.map((r, i) => (
        <li key={i} className={r.error || r.ok === false ? "text-rose-400" : "text-zinc-400"}>
          {r.error || r.ok === false ? "✗" : "✓"} {r.file ? `${r.file} → ` : ""}
          {r.company ?? ""}
          {r.questions != null ? ` · ${r.questions} questions` : ""}
          {r.periods != null ? ` · ${r.periods} periods, ${r.segments} segments` : ""}
          {r.error ? ` · ${r.error}` : ""}
        </li>
      ))}
    </ul>
  );
}

/** Admin bulk loads: base models (.xlsx, many at once) and default questions (CSV). */
export default function AdminImports() {
  const router = useRouter();
  const models = useRef<HTMLInputElement>(null);
  const csv = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<"models" | "questions" | null>(null);
  const [results, setResults] = useState<ImportResult[]>([]);
  const [error, setError] = useState("");

  async function run(kind: "models" | "questions", fn: () => Promise<{ results: ImportResult[] }>) {
    setBusy(kind);
    setError("");
    try {
      setResults((await fn()).results);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Import failed");
    } finally {
      setBusy(null);
      if (models.current) models.current.value = "";
      if (csv.current) csv.current.value = "";
    }
  }

  return (
    <section className="mt-16 rounded-2xl border border-dashed border-white/[0.1] p-6">
      <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-amber-400/80">Admin · house content</p>
      <div className="mt-4 flex flex-wrap gap-3">
        <input
          ref={models}
          type="file"
          accept=".xlsx,.xlsm"
          multiple
          hidden
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) run("models", () => adminImportModels(files));
          }}
        />
        <button
          onClick={() => models.current?.click()}
          disabled={!!busy}
          className="rounded-full border border-white/[0.12] px-3.5 py-1.5 text-[12px] text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff] disabled:opacity-50"
        >
          {busy === "models" ? "Importing models…" : "Import models (.xlsx, many at once)"}
        </button>
        <input
          ref={csv}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) run("questions", () => adminImportHouseQuestions(f));
          }}
        />
        <button
          onClick={() => csv.current?.click()}
          disabled={!!busy}
          className="rounded-full border border-white/[0.12] px-3.5 py-1.5 text-[12px] text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff] disabled:opacity-50"
        >
          {busy === "questions" ? "Importing questions…" : "Import default questions (.csv)"}
        </button>
      </div>
      <p className="mt-3 text-[11px] leading-relaxed text-zinc-600">
        Models are matched to securities by ticker. Questions CSV columns: <code>ticker, question, note, drivers</code>{" "}
        — drivers like <code>Y2 Revenue; Y1 Gross margin; Multiple</code>. New followers start from these
        defaults; recent evidence is scored against them in the background.
      </p>
      {error && <p className="mt-3 text-[12px] text-rose-400">{error}</p>}
      <Results rows={results} />
    </section>
  );
}
