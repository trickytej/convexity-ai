"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { NewsletterNugget, StockMention } from "@/lib/api";

const STORAGE_KEY = "securities:hidden";

const STANCE_STYLE: Record<string, { dot: string; label: string; text: string }> = {
  bullish:  { dot: "bg-emerald-400", label: "Bullish",  text: "text-emerald-400" },
  bearish:  { dot: "bg-amber-400",   label: "Bearish",  text: "text-amber-400"   },
  neutral:  { dot: "bg-zinc-500",    label: "Neutral",  text: "text-zinc-500"    },
  owned:    { dot: "bg-emerald-500", label: "Owned",    text: "text-emerald-400" },
  mentioned:{ dot: "bg-zinc-600",    label: "Mentioned",text: "text-zinc-600"    },
};

function TrashIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor">
      <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z"/>
      <path d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z"/>
    </svg>
  );
}

function SecuritiesRow({
  stock,
  nuggets,
  onDelete,
}: {
  stock: StockMention;
  nuggets: NewsletterNugget[];
  onDelete: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const s = STANCE_STYLE[stock.stance] ?? STANCE_STYLE.neutral;

  return (
    <div className="group grid grid-cols-[5rem_16rem_1fr_auto] gap-x-6 items-start border-b border-white/[0.05] py-5">
      {/* tickers */}
      <div className="flex flex-wrap gap-1 pt-0.5">
        {stock.tickers.length > 0 ? (
          stock.tickers.map((t) => (
            <span
              key={t}
              className="rounded border border-[#00d4ff]/25 px-1.5 py-0.5 font-[family-name:var(--font-mono)] text-[11px] font-medium text-[#00d4ff]/80"
            >
              {t}
            </span>
          ))
        ) : (
          <span className="font-[family-name:var(--font-mono)] text-sm text-zinc-600">—</span>
        )}
      </div>

      {/* company + stance */}
      <div className="flex items-start gap-2 pt-0.5">
        <span className={`mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full ${s.dot}`} />
        <div>
          <p className="text-sm font-medium text-zinc-100">{stock.company}</p>
          <p className={`text-[11px] font-medium ${s.text}`}>{s.label}</p>
        </div>
      </div>

      {/* nugget claims */}
      <div className="space-y-2.5">
        {nuggets.length > 0 ? (
          nuggets.map((n) => {
            const href = `/episode/${n.episode_id}${n.start_ms != null ? `#t-${n.start_ms}` : ""}`;
            return (
              <div key={n.id} className="flex items-start gap-2">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-zinc-600" />
                <p className="text-sm leading-snug text-zinc-300">
                  {n.claim}
                  <Link
                    href={href}
                    className="ml-2 text-[11px] text-[#00d4ff]/60 transition-colors hover:text-[#00d4ff]"
                  >
                    →
                  </Link>
                </p>
              </div>
            );
          })
        ) : stock.summary ? (
          <p className="text-sm leading-snug text-zinc-400">{stock.summary}</p>
        ) : null}
      </div>

      {/* delete */}
      <div className="flex items-center pt-0.5">
        {confirming ? (
          <div className="flex items-center gap-2">
            <button
              onClick={onDelete}
              className="text-xs text-rose-400 hover:text-rose-300 transition-colors"
            >
              Remove
            </button>
            <span className="text-zinc-700">·</span>
            <button
              onClick={() => setConfirming(false)}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            title="Remove from view"
            className="text-zinc-700 opacity-0 transition-all hover:text-rose-400 group-hover:opacity-100"
          >
            <TrashIcon />
          </button>
        )}
      </div>
    </div>
  );
}

export default function SecuritiesTable({
  stocks,
  nuggetsByCompany,
}: {
  stocks: StockMention[];
  nuggetsByCompany: Record<string, NewsletterNugget[]>;
}) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  // load persisted hidden list
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as string[];
      setHidden(new Set(stored));
    } catch {}
  }, []);

  function remove(company: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      next.add(company);
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...next]));
      return next;
    });
  }

  const visible = stocks.filter((s) => !hidden.has(s.company));

  if (visible.length === 0) {
    return (
      <p className="mt-8 text-sm text-zinc-600">
        All securities hidden.{" "}
        <button
          onClick={() => {
            setHidden(new Set());
            localStorage.removeItem(STORAGE_KEY);
          }}
          className="text-[#00d4ff] hover:text-[#33ddff]"
        >
          Restore all
        </button>
      </p>
    );
  }

  return (
    <div>
      <div className="grid grid-cols-[5rem_16rem_1fr_auto] gap-x-6 border-b border-white/[0.08] pb-2 text-[10px] font-medium uppercase tracking-[0.2em] text-zinc-600">
        <span>Ticker</span>
        <span>Company</span>
        <span>Insights</span>
        <span />
      </div>
      {visible.map((stock) => (
        <SecuritiesRow
          key={stock.company}
          stock={stock}
          nuggets={nuggetsByCompany[stock.company] ?? []}
          onDelete={() => remove(stock.company)}
        />
      ))}
      {hidden.size > 0 && (
        <p className="mt-6 text-xs text-zinc-600">
          {hidden.size} hidden.{" "}
          <button
            onClick={() => {
              setHidden(new Set());
              localStorage.removeItem(STORAGE_KEY);
            }}
            className="text-[#00d4ff]/60 hover:text-[#00d4ff]"
          >
            Restore all
          </button>
        </p>
      )}
    </div>
  );
}
