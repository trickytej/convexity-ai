import Link from "next/link";
import type { DigestSource, EpisodeDigest } from "@/lib/api";

function srcHref(s: DigestSource): string {
  return `/episode/${s.episode_id}${s.start_ms != null ? `#t-${s.start_ms}` : ""}`;
}

const STANCE: Record<string, { label: string; cls: string }> = {
  owned: { label: "Owned", cls: "bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-500/25" },
  bullish: { label: "Bullish", cls: "bg-sky-500/15 text-sky-300 ring-1 ring-inset ring-sky-500/25" },
  bearish: { label: "Bearish", cls: "bg-rose-500/15 text-rose-300 ring-1 ring-inset ring-rose-500/25" },
  mentioned: { label: "Mentioned", cls: "bg-white/[0.06] text-zinc-300 ring-1 ring-inset ring-white/10" },
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
          className="rounded bg-white/[0.06] px-1.5 py-0.5 text-xs text-zinc-400 ring-1 ring-inset ring-white/10 transition hover:bg-white/10 hover:text-[#e53e3e]"
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
            <h3 className="text-lg font-medium tracking-tight text-zinc-50 [font-family:var(--font-display)]">{t.headline}</h3>
            {t.takeaway && <p className="mt-1 text-sm italic text-[#e53e3e]">{t.takeaway}</p>}
            <ul className="mt-3 space-y-3">
              {t.points.map((p, j) => (
                <li key={j} className="text-[15px] leading-relaxed text-zinc-300">
                  <span className="mr-1.5 text-[#e53e3e]/70">•</span>
                  {p.text}
                  <SourceChips sources={p.sources} />
                  {p.quote && (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-xs text-zinc-500 hover:text-zinc-300">
                        quote
                      </summary>
                      <blockquote className="mt-1 border-l-2 border-[#e53e3e]/40 pl-3 text-sm italic text-zinc-500">
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
          <h3 className="mb-3 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.2em] text-[#e53e3e]">
            <span className="inline-block h-px w-6 bg-[#e53e3e]" />
            Stock read-through
          </h3>
          <div className="divide-y divide-white/[0.06] overflow-hidden rounded-xl border border-white/[0.08] bg-[#0b0c10]/60">
            {digest.stocks.map((s, i) => {
              const stance = STANCE[s.stance] ?? STANCE.mentioned;
              return (
                <div key={i} className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3">
                  <span className="w-36 shrink-0 font-medium text-zinc-100">{s.company}</span>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${stance.cls}`}
                  >
                    {stance.label}
                  </span>
                  <span className="flex-1 text-sm text-zinc-400">
                    {s.summary}
                    {s.sources.length > 0 && (
                      <Link
                        href={srcHref(s.sources[0])}
                        className="ml-1 text-[#e53e3e] hover:text-[#f56565]"
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
