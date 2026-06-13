import Link from "next/link";
import type { DigestSource, EpisodeDigest } from "@/lib/api";

function srcHref(s: DigestSource): string {
  return `/episode/${s.episode_id}${s.start_ms != null ? `#t-${s.start_ms}` : ""}`;
}

const STANCE: Record<string, { label: string; cls: string }> = {
  owned: { label: "Owned", cls: "bg-emerald-600 text-white" },
  bullish: { label: "Bullish", cls: "bg-blue-600 text-white" },
  bearish: { label: "Bearish", cls: "bg-rose-600 text-white" },
  mentioned: { label: "Mentioned", cls: "bg-zinc-200 text-zinc-700" },
};

function SourceChips({ sources }: { sources: DigestSource[] }) {
  if (!sources.length) return null;
  return (
    <span className="ml-1.5 inline-flex flex-wrap gap-1 align-baseline">
      {sources.map((s) => (
        <Link
          key={s.nugget_id}
          href={srcHref(s)}
          title={s.speaker_name ?? "source"}
          className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-500 ring-1 ring-inset ring-zinc-200 hover:bg-zinc-200 hover:text-zinc-700"
        >
          ↗
        </Link>
      ))}
    </span>
  );
}

export function DigestView({ digest }: { digest: EpisodeDigest }) {
  return (
    <div className="space-y-10">
      <div className="space-y-7">
        {digest.themes.map((t, i) => (
          <section key={i}>
            <h3 className="text-lg font-semibold tracking-tight">{t.headline}</h3>
            {t.takeaway && <p className="mt-1 text-sm italic text-indigo-700">{t.takeaway}</p>}
            <ul className="mt-3 space-y-3">
              {t.points.map((p, j) => (
                <li key={j} className="text-[15px] leading-relaxed text-zinc-800">
                  <span className="mr-1.5 text-indigo-400">•</span>
                  {p.text}
                  <SourceChips sources={p.sources} />
                  {p.quote && (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-xs text-zinc-400 hover:text-zinc-600">
                        quote
                      </summary>
                      <blockquote className="mt-1 border-l-2 border-zinc-200 pl-3 text-sm italic text-zinc-500">
                        “{p.quote}”
                      </blockquote>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      {digest.stocks.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Stock read-through
          </h3>
          <div className="divide-y divide-zinc-100 overflow-hidden rounded-xl border border-zinc-200 bg-white">
            {digest.stocks.map((s, i) => {
              const stance = STANCE[s.stance] ?? STANCE.mentioned;
              return (
                <div key={i} className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3">
                  <span className="w-36 shrink-0 font-medium text-zinc-900">{s.company}</span>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${stance.cls}`}
                  >
                    {stance.label}
                  </span>
                  <span className="flex-1 text-sm text-zinc-600">
                    {s.summary}
                    {s.sources.length > 0 && (
                      <Link
                        href={srcHref(s.sources[0])}
                        className="ml-1 text-indigo-500 hover:text-indigo-700"
                      >
                        ↗
                      </Link>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
