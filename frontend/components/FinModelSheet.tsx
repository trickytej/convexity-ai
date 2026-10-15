"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { FinColumn, FinModel, FinRow } from "@/lib/api";
import { importModel, putModelNumbers } from "@/lib/api";
import { fmtDate } from "@/lib/format";

export type CellTone = "green" | "yellow" | "red";
/** Cells to light up for a selected development (row id + column ids). */
export type SheetHighlight = { row: string; cols: string[]; tone: CellTone } | null;

const TONE: Record<CellTone, string> = {
  green: "!bg-emerald-200 outline outline-2 -outline-offset-2 outline-emerald-600",
  yellow: "!bg-amber-200 outline outline-2 -outline-offset-2 outline-amber-500",
  red: "!bg-rose-200 outline outline-2 -outline-offset-2 outline-rose-600",
};

const LABEL_COL_PX = 240;
const DATA_COL_PX = 96; // fits "1,325,695" and "-12.3%" with padding

function fmt(v: number | null | undefined, kind: FinRow["fmt"]): string {
  if (v == null || !Number.isFinite(v)) return "";
  switch (kind) {
    case "pct":
      return `${(v * 100).toFixed(1)}%`;
    case "eps":
      return v.toFixed(2);
    case "x":
      return `${v.toFixed(1)}x`;
    default:
      return Math.round(v).toLocaleString("en-US");
  }
}

/** Driver input: percentages typed as %, everything else as-is; empty resets. */
function DriverCell({
  value,
  kind,
  overridden,
  onCommit,
}: {
  value: number | null;
  kind: FinRow["fmt"];
  overridden: boolean;
  onCommit: (v: number | null) => void;
}) {
  const shown = value == null ? "" : kind === "pct" ? (value * 100).toFixed(1) : kind === "eps" ? value.toFixed(2) : String(Math.round(value));
  const [draft, setDraft] = useState(shown);
  const [focused, setFocused] = useState(false);
  return (
    <input
      value={focused ? draft : kind === "pct" && shown ? `${shown}%` : shown}
      inputMode="decimal"
      title={overridden ? "Your number — clear to reset to the base model" : "Base model driver — type to override"}
      onFocus={() => {
        setDraft(shown);
        setFocused(true);
      }}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        setFocused(false);
        if (draft === shown) return;
        const n = parseFloat(draft.replace(/[,%]/g, ""));
        onCommit(Number.isFinite(n) ? (kind === "pct" ? n / 100 : n) : null);
      }}
      onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
      className={`w-full bg-transparent text-right tabular-nums outline-none focus:bg-white ${
        overridden ? "font-semibold text-blue-700" : "text-blue-600"
      }`}
    />
  );
}

function NumberField({
  label,
  value,
  placeholder,
  onCommit,
}: {
  label: string;
  value: number | null;
  placeholder: string;
  onCommit: (v: number | null) => void;
}) {
  const [draft, setDraft] = useState(value == null ? "" : String(value));
  useEffect(() => setDraft(value == null ? "" : String(+value.toFixed(2))), [value]);
  return (
    <label className="flex items-center gap-2 text-[12px] text-zinc-400">
      {label}
      <input
        value={draft}
        placeholder={placeholder}
        inputMode="decimal"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          const n = parseFloat(draft);
          const next = Number.isFinite(n) ? n : null;
          if (next !== value) onCommit(next);
        }}
        onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
        className="w-20 rounded-md border border-white/[0.1] bg-[#0b0c10] px-2 py-1 text-right font-[family-name:var(--font-mono)] text-[12px] text-zinc-100 outline-none focus:border-[#00d4ff]/40"
      />
    </label>
  );
}

function ImportButton({ securityKey, label }: { securityKey: string; label: string }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <span className="inline-flex items-center gap-2">
      <input
        ref={input}
        type="file"
        accept=".xlsx,.xlsm"
        hidden
        onChange={async (e) => {
          const f = e.target.files?.[0];
          if (!f) return;
          setBusy(true);
          setError("");
          try {
            await importModel(securityKey, f);
            router.refresh();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Import failed");
          } finally {
            setBusy(false);
            if (input.current) input.current.value = "";
          }
        }}
      />
      <button
        onClick={() => input.current?.click()}
        disabled={busy}
        className="rounded-full border border-white/[0.12] px-3 py-1 text-[12px] text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff] disabled:opacity-50"
      >
        {busy ? "Importing…" : label}
      </button>
      {error && <span className="text-[12px] text-rose-400">{error}</span>}
    </span>
  );
}

/** Excel-style operating model: quarters, then fiscal years. Yellow cells are
 * drivers in forecast periods — type to override; everything downstream
 * recalculates server-side. */
export default function FinModelSheet({
  securityKey,
  company,
  initial,
  isAdmin,
  highlight = null,
}: {
  securityKey: string;
  company: string;
  initial: FinModel | null;
  isAdmin: boolean;
  highlight?: SheetHighlight;
}) {
  const [m, setM] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const tableRef = useRef<HTMLDivElement>(null);

  useEffect(() => setM(initial), [initial]);

  // Bring the highlighted cell into view.
  useEffect(() => {
    if (!highlight) return;
    const el = tableRef.current?.querySelector(`[data-cell="${highlight.row}@${highlight.cols[0]}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
  }, [highlight]);

  if (!m) {
    return (
      <div className="rounded-2xl border border-dashed border-white/[0.1] p-8 text-center">
        <p className="text-[15px] font-light text-zinc-400 [font-family:var(--font-display)]">
          No model loaded for {company} yet
        </p>
        <p className="mt-2 text-[12px] text-zinc-600">
          The operating model (segment build, P&amp;L, cash flow, valuation) appears once a base model is imported.
        </p>
        {isAdmin && (
          <div className="mt-4">
            <ImportButton securityKey={securityKey} label="Import Canalyst model (.xlsx)" />
          </div>
        )}
      </div>
    );
  }

  const model = m;
  const quarters = model.columns.filter((c) => c.kind === "Q");
  const years = model.columns.filter((c) => c.kind === "FY");
  const editable = new Set(model.editable);

  function currentOverrides(): Record<string, number> {
    const o: Record<string, number> = {};
    for (const s of model.sections)
      for (const r of s.rows)
        if (r.driver)
          for (const pid of r.overridden ?? []) {
            const v = r.values[pid];
            if (v != null) o[`${r.driver}@${pid}`] = v;
          }
    return o;
  }

  async function save(patch: { cell?: [string, number | null]; target_pe?: number | null; price?: number | null; reset?: boolean }) {
    const overrides = patch.reset ? {} : currentOverrides();
    if (patch.cell) {
      const [k, v] = patch.cell;
      if (v == null) delete overrides[k];
      else overrides[k] = v;
    }
    setSaving(true);
    setError("");
    try {
      const next = await putModelNumbers(securityKey, {
        overrides,
        target_pe: "target_pe" in patch ? patch.target_pe ?? null : model.market.target_pe,
        price: "price" in patch ? patch.price ?? null : model.market.price_override,
      });
      setM({ ...next, impacts: model.impacts });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  const tone = (rowId: string, col: string) =>
    highlight && highlight.row === rowId && highlight.cols.includes(col) ? TONE[highlight.tone] : "";

  const headCell = (c: FinColumn, first: boolean) =>
    `px-2 py-1 text-right font-semibold whitespace-nowrap ${first ? "border-l-2 border-l-zinc-400" : ""}`;

  function renderCell(r: FinRow, c: FinColumn, annualOnly: boolean, firstOfBlock: boolean) {
    const isDriver = !!r.driver && editable.has(c.id) && !(annualOnly && c.kind === "Q");
    const overridden = (r.overridden ?? []).includes(c.id);
    const base = `px-2 py-[3px] text-right tabular-nums whitespace-nowrap ${firstOfBlock ? "border-l-2 border-l-zinc-400" : ""} ${
      c.actual ? "" : "bg-sky-50/60"
    }`;
    const text =
      r.style === "margin" ? "text-red-600" : r.style === "sub" ? "text-zinc-500" : "text-zinc-900";
    if (annualOnly && c.kind === "Q") return <td key={c.id} className={base} />;
    return (
      <td
        key={c.id}
        data-cell={`${r.id}@${c.id}`}
        className={`${base} ${isDriver ? "!bg-yellow-100" : ""} ${tone(r.id, c.id)} ${text}`}
      >
        {isDriver ? (
          <DriverCell
            key={`${r.id}@${c.id}:${r.values[c.id]}`}
            value={r.values[c.id]}
            kind={r.fmt}
            overridden={overridden}
            onCommit={(v) => save({ cell: [`${r.driver}@${c.id}`, v] })}
          />
        ) : (
          fmt(r.values[c.id], r.fmt)
        )}
      </td>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-2">
        <span className="text-[12px] text-zinc-500">
          Base: <span className="text-zinc-300">{model.source}</span>
          {model.file ? ` · ${model.file}` : ""}
          {model.imported_at ? ` · ${fmtDate(model.imported_at)}` : ""}
        </span>
        <NumberField label="Target P/E" value={model.market.target_pe} placeholder="x" onCommit={(v) => save({ target_pe: v })} />
        <NumberField label="Price $" value={model.market.price} placeholder="$" onCommit={(v) => save({ price: v })} />
        {model.override_count > 0 && (
          <button onClick={() => save({ reset: true })} className="text-[12px] text-zinc-500 hover:text-rose-300">
            {model.override_count} override{model.override_count === 1 ? "" : "s"} · reset all
          </button>
        )}
        {isAdmin && <ImportButton securityKey={securityKey} label="Replace base model" />}
        {saving && <span className="text-[12px] text-zinc-500">Recalculating…</span>}
        {error && <span className="text-[12px] text-rose-400">{error}</span>}
      </div>

      <div ref={tableRef} className="max-h-[70vh] overflow-auto rounded-lg border border-zinc-300 bg-white shadow-xl">
        {/* Fixed layout: every period column gets the same width. */}
        <table
          className="table-fixed border-collapse font-[family-name:var(--font-mono)] text-[12px] leading-tight"
          style={{ width: LABEL_COL_PX + (quarters.length + years.length) * DATA_COL_PX }}
        >
          <colgroup>
            <col style={{ width: LABEL_COL_PX }} />
            {[...quarters, ...years].map((c) => (
              <col key={c.id} style={{ width: DATA_COL_PX }} />
            ))}
          </colgroup>
          <thead className="sticky top-0 z-10">
            <tr className="bg-[#1f3864] text-white">
              <th className="sticky left-0 z-20 bg-[#1f3864] px-2 py-1 text-left font-semibold">
                Fiscal period
              </th>
              {quarters.map((c, i) => (
                <th key={c.id} className={headCell(c, i === 0)}>{c.label}</th>
              ))}
              {years.map((c, i) => (
                <th key={c.id} className={headCell(c, i === 0)}>{c.label}</th>
              ))}
            </tr>
            <tr className="bg-[#2f5597] text-[11px] text-blue-50">
              <th className="sticky left-0 z-20 bg-[#2f5597] px-2 py-0.5 text-left font-normal">Calendar</th>
              {[...quarters, ...years].map((c, i) => (
                <th key={c.id} className={`px-2 py-0.5 text-right font-normal ${i === 0 || i === quarters.length ? "border-l-2 border-l-zinc-400" : ""}`}>
                  {c.calendar}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {model.sections.map((s) => (
              <SectionRows key={s.id} title={s.title} span={quarters.length + years.length}>
                {s.rows.map((r) => {
                  const labelCls =
                    r.style === "bold" || r.style === "total"
                      ? "font-semibold text-zinc-900"
                      : r.style === "margin"
                        ? "pl-5 text-red-600"
                        : r.style === "sub"
                          ? "pl-5 text-zinc-500"
                          : "pl-2 text-zinc-800";
                  return (
                    <tr key={r.id} className={`border-b border-zinc-100 ${r.style === "total" ? "border-t border-t-zinc-400" : ""}`}>
                      <td
                        title={r.label}
                        className={`sticky left-0 z-[5] overflow-hidden text-ellipsis bg-white px-2 py-[3px] whitespace-nowrap [font-family:var(--font-body)] ${labelCls}`}
                      >
                        {r.label}
                      </td>
                      {quarters.map((c, i) => renderCell(r, c, !!s.annual_only, i === 0))}
                      {years.map((c, i) => renderCell(r, c, !!s.annual_only, i === 0))}
                    </tr>
                  );
                })}
              </SectionRows>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-[11px] leading-relaxed text-zinc-600">
        Shaded columns are estimates. <span className="rounded bg-yellow-100 px-1 text-blue-600">Yellow</span> cells are drivers — type
        to override (bold blue = yours; clear to reset). Revenue, margins, EPS, cash flow and implied value recalculate from them.
      </p>
    </div>
  );
}

function SectionRows({ title, span, children }: { title: string; span: number; children: React.ReactNode }) {
  return (
    <>
      <tr className="bg-[#d9e1f2]">
        <td className="sticky left-0 z-[5] bg-[#d9e1f2] px-2 py-1 text-[11px] font-bold uppercase tracking-wide text-[#1f3864] [font-family:var(--font-body)]">
          {title}
        </td>
        <td colSpan={span} />
      </tr>
      {children}
    </>
  );
}
