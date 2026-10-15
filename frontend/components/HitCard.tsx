"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { BriefHit, HitDecision } from "@/lib/api";
import { decideHit } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { SOURCE_LABEL } from "@/lib/signals";

const DIRECTION_CLS: Record<string, string> = {
  supports: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25",
  contradicts: "bg-rose-500/10 text-rose-300 ring-rose-500/25",
  unclear: "bg-white/[0.06] text-zinc-400 ring-white/10",
};

function hitSourceHref(h: BriefHit): string {
  if (h.nugget.tweet_url) return h.nugget.tweet_url;
  const t = h.nugget.start_ms != null ? `#t-${h.nugget.start_ms}` : "";
  return `/episode/${h.nugget.episode_id}${t}`;
}

/** One thesis hit. Pending hits get Keep / Drop; kept hits can be un-kept. The
 * card hides optimistically on a decision, then the server data refreshes. */
export default function HitCard({ h, sourceLinks = false }: { h: BriefHit; sourceLinks?: boolean }) {
  const router = useRouter();
  const [hidden, setHidden] = useState(false);
  const [error, setError] = useState("");
  const external = !!h.nugget.tweet_url;
  const quote = (h.nugget.quote || "").trim();

  async function decide(decision: HitDecision) {
    setHidden(true);
    setError("");
    try {
      await decideHit(h.hit_id, decision);
      router.refresh();
    } catch (e) {
      setHidden(false);
      setError(e instanceof Error ? e.message : "Could not save");
    }
  }

  if (hidden) return null;
  const signal = h.tier === "signal";

  return (
    <div
      className={`rounded-xl border p-4 ${
        signal ? "border-white/[0.08] bg-[#0b0c10]/90" : "border-white/[0.04] bg-[#0b0c10]/50"
      }`}
    >
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {signal ? (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${DIRECTION_CLS[h.direction] ?? DIRECTION_CLS.unclear}`}
          >
            {h.direction}
          </span>
        ) : (
          <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium text-zinc-500 ring-1 ring-inset ring-white/10">
            reference
          </span>
        )}
        {h.impact && (
          <span
            title="Model line this moves"
            className="inline-flex items-center rounded-full bg-[#00d4ff]/[0.08] px-2 py-0.5 text-[11px] font-medium text-[#00d4ff]/90 ring-1 ring-inset ring-[#00d4ff]/20"
          >
            {h.impact.label} {h.impact.direction === "up" ? "↑" : "↓"}
          </span>
        )}
        <span className="text-[11px] text-zinc-600">{SOURCE_LABEL[h.source_class]}</span>
        <span
          title="relevance · evidence quality"
          className="font-[family-name:var(--font-mono)] text-[11px] text-zinc-700"
        >
          {Math.round(h.relevance * 100)}%{h.evidence != null ? ` · ev ${Math.round(h.evidence * 100)}` : ""}
        </span>
        <span className="ml-auto text-[11px] text-zinc-600">
          {h.nugget.speaker_name ? `${h.nugget.speaker_name} · ` : ""}
          {h.nugget.show_slug}
          {h.nugget.published_at ? ` · ${fmtDate(h.nugget.published_at)}` : ""}
        </span>
      </div>
      {h.why && <p className="mb-2 text-[13px] leading-relaxed text-[#00d4ff]/90">{h.why}</p>}
      <p className={`text-[14px] leading-relaxed ${signal ? "text-zinc-200" : "text-zinc-400"}`}>
        {h.nugget.claim}
      </p>
      {quote && quote !== h.nugget.claim && (
        <p className="mt-2 border-l-2 border-white/10 pl-3 text-[12px] leading-relaxed text-zinc-500">
          “{quote.length > 320 ? quote.slice(0, 320) + "…" : quote}”
        </p>
      )}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {(external || sourceLinks) && (
          <Link
            href={hitSourceHref(h)}
            target={external ? "_blank" : undefined}
            rel={external ? "noopener noreferrer" : undefined}
            className="text-[11px] text-zinc-600 transition hover:text-[#00d4ff]"
          >
            {external ? "View post on X ↗" : "In context →"}
          </Link>
        )}
        {error && <span className="text-[11px] text-rose-400">{error}</span>}
        <span className="ml-auto flex gap-2">
          {h.decision === "kept" ? (
            <button
              onClick={() => decide("pending")}
              className="rounded-full border border-white/[0.1] px-3 py-1 text-[11px] font-medium text-zinc-500 transition hover:border-white/[0.2] hover:text-zinc-300"
            >
              Un-keep
            </button>
          ) : (
            <>
              <button
                onClick={() => decide("dropped")}
                className="rounded-full border border-white/[0.1] px-3 py-1 text-[11px] font-medium text-zinc-500 transition hover:border-rose-500/40 hover:text-rose-300"
              >
                Drop
              </button>
              <button
                onClick={() => decide("kept")}
                className="rounded-full bg-[#00d4ff]/90 px-3 py-1 text-[11px] font-semibold text-black transition hover:bg-[#00d4ff]"
              >
                Keep
              </button>
            </>
          )}
        </span>
      </div>
    </div>
  );
}
