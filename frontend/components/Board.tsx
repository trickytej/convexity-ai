import Link from "next/link";
import type { BoardSecurity, SourceClass } from "@/lib/api";
import { driverLabel, SOURCE_LABEL } from "@/lib/signals";
import { StatusDot } from "@/components/signals";

const COLUMNS: SourceClass[] = ["print", "chatter", "inside"];

function Tally({ supports, contradicts }: { supports: number; contradicts: number }) {
  if (!supports && !contradicts) return <span className="text-zinc-800">—</span>;
  return (
    <span className="font-[family-name:var(--font-mono)] tabular-nums">
      {supports > 0 && <span className="text-emerald-300">{supports}▲</span>}
      {supports > 0 && contradicts > 0 && " "}
      {contradicts > 0 && <span className="text-rose-300">{contradicts}▼</span>}
    </span>
  );
}

/** The CIO board: every followed security's questions with a green / yellow /
 * red status from the last 30 days of signals, split by where the evidence came
 * from — consensus in print, consensus in chatter, and the inside view. */
export default function Board({ securities }: { securities: BoardSecurity[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-left">
        <thead>
          <tr className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-600">
            <th className="pb-3 font-medium">Security · What Matters</th>
            {COLUMNS.map((c) => (
              <th key={c} className="w-24 pb-3 text-right font-medium">
                {SOURCE_LABEL[c]}
              </th>
            ))}
          </tr>
        </thead>
        {securities.map((s) => (
          <tbody key={s.company} className="border-t border-white/[0.08]">
            <tr>
              <td colSpan={4} className="pb-2 pt-5">
                <div className="flex flex-wrap items-center gap-3">
                  <Link
                    href={`/model/${encodeURIComponent(s.key)}`}
                    className="group inline-flex items-baseline gap-2"
                  >
                    <span className="text-lg font-light tracking-tight text-zinc-50 transition [font-family:var(--font-display)] group-hover:text-[#00d4ff]">
                      {s.company}
                    </span>
                    {s.ticker && (
                      <span className="font-[family-name:var(--font-mono)] text-xs text-zinc-500">{s.ticker}</span>
                    )}
                  </Link>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 ring-inset ${
                      s.has_model ? "text-emerald-300 ring-emerald-500/30" : "text-zinc-600 ring-white/10"
                    }`}
                  >
                    {s.has_model ? "Model loaded" : "No model yet"}
                  </span>
                  <Link
                    href={`/model/${encodeURIComponent(s.key)}`}
                    className="ml-auto rounded-full bg-[#00d4ff]/90 px-3.5 py-1 text-[12px] font-semibold text-black transition hover:bg-[#00d4ff]"
                  >
                    Open model →
                  </Link>
                </div>
              </td>
            </tr>
            {s.questions.length === 0 ? (
              <tr>
                <td colSpan={4} className="pb-4 text-[12px]">
                  <Link href={`/model/${encodeURIComponent(s.key)}`} className="text-zinc-600 transition hover:text-[#00d4ff]">
                    Define what matters →
                  </Link>
                </td>
              </tr>
            ) : (
              s.questions.map((q) => (
                <tr key={q.id} className="align-top text-[13px]">
                  <td className="py-1.5 pr-4">
                    <div className="flex items-start gap-2.5">
                      <span className="mt-1.5">
                        <StatusDot status={q.status} />
                      </span>
                      <div>
                        <p className="leading-snug text-zinc-300">{q.question}</p>
                        {q.drivers.length > 0 && (
                          <p className="mt-0.5 text-[11px] text-[#00d4ff]/60">
                            {q.drivers.map(driverLabel).join(" · ")}
                          </p>
                        )}
                      </div>
                    </div>
                  </td>
                  {COLUMNS.map((c) => (
                    <td key={c} className="py-1.5 text-right text-[12px]">
                      <Tally {...q.by_class[c]} />
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        ))}
      </table>
    </div>
  );
}
