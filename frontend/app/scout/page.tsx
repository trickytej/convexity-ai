"use client";

import dynamic from "next/dynamic";
import Script from "next/script";
import { useState, useEffect, useCallback, useRef } from "react";
import { getScoutAppearances, refreshScout, ingestScoutAppearance, processEpisode, getEpisodeStatus, type ScoutAppearance } from "@/lib/api";

const NeonSphere = dynamic(() => import("@/components/NeonSphere"), { ssr: false });

// ─── watchlist data ───────────────────────────────────────────────────────────

type Company  = { name: string; ticker?: string };
type Category = { label: string; companies: Company[] };

const WATCHLIST_DEFAULT: Category[] = [
  {
    label: "Privates",
    companies: [
      { name: "Anthropic"  }, { name: "OpenAI"     }, { name: "Databricks" },
      { name: "Stripe"     }, { name: "Anduril"    }, { name: "Figure"     },
      { name: "Perplexity" }, { name: "Sierra"     }, { name: "Crusoe"     },
      { name: "Groq"       },
    ],
  },
  {
    label: "Semiconductors",
    companies: [
      { name: "Nvidia",            ticker: "NVDA" }, { name: "TSMC",              ticker: "TSM"  },
      { name: "Broadcom",          ticker: "AVGO" }, { name: "Micron",            ticker: "MU"   },
      { name: "AMD",               ticker: "AMD"  }, { name: "ASML",              ticker: "ASML" },
      { name: "Intel",             ticker: "INTC" }, { name: "ARM",               ticker: "ARM"  },
      { name: "Lam Research",      ticker: "LRCX" }, { name: "SK Hynix",          ticker: "000660.KS" },
      { name: "Applied Materials", ticker: "AMAT" }, { name: "KLA",               ticker: "KLAC" },
      { name: "Texas Instruments", ticker: "TXN"  }, { name: "Marvell",           ticker: "MRVL" },
      { name: "Qualcomm",          ticker: "QCOM" }, { name: "Analog Devices",    ticker: "ADI"  },
      { name: "Tokyo Electron",    ticker: "8035.T" }, { name: "Cadence",          ticker: "CDNS" },
      { name: "Synopsys",          ticker: "SNPS" }, { name: "NXP",               ticker: "NXPI" },
    ],
  },
  {
    label: "Mag 7",
    companies: [
      { name: "Apple",     ticker: "AAPL"  }, { name: "Alphabet",  ticker: "GOOGL" },
      { name: "Microsoft", ticker: "MSFT"  }, { name: "Amazon",    ticker: "AMZN"  },
      { name: "Meta",      ticker: "META"  }, { name: "Tesla",     ticker: "TSLA"  },
      { name: "Nvidia",    ticker: "NVDA"  },
    ],
  },
  {
    label: "Software",
    companies: [
      { name: "Oracle",             ticker: "ORCL" }, { name: "Palantir",           ticker: "PLTR" },
      { name: "Cisco",              ticker: "CSCO" }, { name: "SAP",                ticker: "SAP"  },
      { name: "Salesforce",         ticker: "CRM"  }, { name: "IBM",                ticker: "IBM"  },
      { name: "AppLovin",           ticker: "APP"  }, { name: "ServiceNow",         ticker: "NOW"  },
      { name: "Intuit",             ticker: "INTU" }, { name: "Adobe",              ticker: "ADBE" },
      { name: "Shopify",            ticker: "SHOP" }, { name: "Palo Alto Networks", ticker: "PANW" },
      { name: "CrowdStrike",        ticker: "CRWD" }, { name: "Snowflake",          ticker: "SNOW" },
      { name: "Fortinet",           ticker: "FTNT" },
    ],
  },
  {
    label: "Internet",
    companies: [
      { name: "Netflix",          ticker: "NFLX" }, { name: "Uber",             ticker: "UBER" },
      { name: "Booking Holdings", ticker: "BKNG" }, { name: "Spotify",          ticker: "SPOT" },
      { name: "MercadoLibre",     ticker: "MELI" }, { name: "DoorDash",         ticker: "DASH" },
      { name: "Sea Ltd",          ticker: "SE"   }, { name: "Airbnb",           ticker: "ABNB" },
      { name: "PayPal",           ticker: "PYPL" }, { name: "Coupang",          ticker: "CPNG" },
      { name: "Block",            ticker: "XYZ"  }, { name: "Roblox",           ticker: "RBLX" },
      { name: "Robinhood",        ticker: "HOOD" }, { name: "Reddit",           ticker: "RDDT" },
      { name: "Pinterest",        ticker: "PINS" },
    ],
  },
];

const STORAGE_KEY = "scout-watchlist-v1";

function loadWatchlist(): Category[] {
  if (typeof window === "undefined") return WATCHLIST_DEFAULT;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? (JSON.parse(saved) as Category[]) : WATCHLIST_DEFAULT;
  } catch {
    return WATCHLIST_DEFAULT;
  }
}

// ─── helpers ──────────────────────────────────────────────────────────────────

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const days = Math.floor(diff / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7)  return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// ─── watchlist sub-components ─────────────────────────────────────────────────

function CompanyRow({
  co,
  onDelete,
}: {
  co: Company;
  onDelete: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      className="group flex items-center justify-between border-b border-white/[0.03] py-[7px] last:border-0 px-1 -mx-1 rounded transition hover:bg-white/[0.02]"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="flex min-w-0 items-center gap-2">
        <span className="truncate text-[12px] text-zinc-200">{co.name}</span>
      </div>
      <div className="flex items-center gap-2 ml-2 shrink-0">
        {co.ticker && !hovered && (
          <span className="font-[family-name:var(--font-mono)] text-[10px] text-zinc-700">
            {co.ticker}
          </span>
        )}
        {hovered && (
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="rounded px-1 text-[11px] text-zinc-600 transition hover:text-red-400"
            title="Remove"
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}

function AddCompanyRow({
  onAdd,
  onCancel,
}: {
  onAdd: (name: string, ticker: string) => void;
  onCancel: () => void;
}) {
  const [name,   setName]   = useState("");
  const [ticker, setTicker] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); }, []);

  function submit() {
    const n = name.trim();
    if (n) onAdd(n, ticker.trim().toUpperCase());
  }

  return (
    <div className="flex items-center gap-1.5 py-1.5 border-b border-white/[0.03]">
      <input
        ref={ref}
        value={name}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") submit(); if (e.key === "Escape") onCancel(); }}
        placeholder="Company name"
        className="min-w-0 flex-1 rounded bg-white/[0.04] px-2 py-1 text-[11px] text-zinc-200 outline-none placeholder:text-zinc-700 focus:ring-1 focus:ring-[#00d4ff]/30"
      />
      <input
        value={ticker}
        onChange={(e) => setTicker(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") submit(); if (e.key === "Escape") onCancel(); }}
        placeholder="Ticker"
        className="w-14 rounded bg-white/[0.04] px-2 py-1 text-[11px] text-zinc-200 outline-none placeholder:text-zinc-700 focus:ring-1 focus:ring-[#00d4ff]/30"
      />
      <button onClick={submit}   className="text-[11px] text-[#00d4ff] transition hover:text-[#33ddff]">✓</button>
      <button onClick={onCancel} className="text-[11px] text-zinc-600  transition hover:text-zinc-400">✕</button>
    </div>
  );
}

// ─── appearance card ──────────────────────────────────────────────────────────

type TranscribeState =
  | { phase: "idle" }
  | { phase: "ingesting" }
  | { phase: "processing"; episode_id: number }
  | { phase: "done";       episode_id: number; nugget_count: number }
  | { phase: "error";      message: string };

const STATUS_LABEL: Record<string, string> = {
  discovered:         "Queued…",
  acquiring:          "Downloading audio…",
  acquired:           "Transcribing…",
  transcribing:       "Transcribing…",
  transcribed:        "Extracting insights…",
  insights_extracted: "Done",
  failed:             "Failed",
};

function AppearanceCard({ a }: { a: ScoutAppearance }) {
  const [expanded, setExpanded] = useState(false);
  const [txState,  setTxState]  = useState<TranscribeState>(() =>
    a.episode_id ? { phase: "processing", episode_id: a.episode_id } : { phase: "idle" }
  );
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (a.episode_id) {
      getEpisodeStatus(a.episode_id).then((s) => {
        if (s.status === "insights_extracted" || (s.status === "transcribed" && s.nugget_count > 0)) {
          setTxState({ phase: "done", episode_id: a.episode_id!, nugget_count: s.nugget_count });
        } else if (s.status === "failed") {
          setTxState({ phase: "error", message: s.error ?? "Processing failed" });
        } else {
          setTxState({ phase: "processing", episode_id: a.episode_id! });
        }
      }).catch(() => {});
    }
  }, [a.episode_id]);

  function startPoll(episodeId: number) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const s = await getEpisodeStatus(episodeId);
        if (s.status === "insights_extracted" || (s.status === "transcribed" && s.nugget_count > 0)) {
          clearInterval(pollRef.current!);
          setTxState({ phase: "done", episode_id: episodeId, nugget_count: s.nugget_count });
        } else if (s.status === "failed") {
          clearInterval(pollRef.current!);
          setTxState({ phase: "error", message: s.error ?? "Processing failed" });
        }
      } catch { /* ignore */ }
    }, 4000);
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  async function handleTranscribe(e: React.MouseEvent) {
    e.stopPropagation();
    setTxState({ phase: "ingesting" });
    try {
      const { episode_id } = await ingestScoutAppearance(a.id);
      setTxState({ phase: "processing", episode_id });
      await processEpisode(episode_id).catch(() => {});
      startPoll(episode_id);
    } catch (err: unknown) {
      setTxState({ phase: "error", message: err instanceof Error ? err.message : "Failed" });
    }
  }

  return (
    <div
      className="group rounded-xl border border-white/[0.06] bg-[#0b0c10]/80 transition hover:border-white/[0.10] cursor-pointer"
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="flex gap-4 p-5">
        <div className="mt-0.5 w-px shrink-0 self-stretch rounded-full bg-[#00d4ff]/20 group-hover:bg-[#00d4ff]/40 transition" />
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-center gap-2 flex-wrap">
            <span className="rounded-sm bg-[#00d4ff]/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#00d4ff]/70">
              {a.company}
            </span>
            {a.person_name && (
              <>
                <span className="text-zinc-700">·</span>
                <span className="text-[12px] font-medium text-zinc-300">{a.person_name}</span>
                {a.person_role && (
                  <span className="text-[11px] text-zinc-600">{a.person_role}</span>
                )}
              </>
            )}
            <span className="ml-auto shrink-0 text-[11px] text-zinc-600">{relativeTime(a.published_at)}</span>
          </div>
          <p className="text-[14px] font-medium leading-snug text-zinc-200 group-hover:text-white transition">
            {a.episode_title}
          </p>
          <div className="mt-1.5 flex items-center gap-2 text-[11px] text-zinc-600">
            <span>{a.podcast_name}</span>
            {a.published_at && (
              <>
                <span className="text-zinc-800">·</span>
                <span>{fmtDate(a.published_at)}</span>
              </>
            )}
          </div>
        </div>
        <div className={`mt-1 shrink-0 text-zinc-700 transition-transform duration-150 ${expanded ? "rotate-90" : ""}`}>
          ›
        </div>
      </div>

      {expanded && (
        <div className="border-t border-white/[0.05] px-5 pb-5 pt-4" onClick={(e) => e.stopPropagation()}>
          {a.description && (
            <p className="mb-4 text-[12px] leading-relaxed text-zinc-600">{a.description}</p>
          )}
          {a.episode_url && (
            <div className="mb-4">
              <a
                href={a.episode_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11px] text-zinc-600 transition hover:text-[#00d4ff]"
                onClick={(e) => e.stopPropagation()}
              >
                Episode page ↗
              </a>
            </div>
          )}

          <div className="flex items-center gap-3">
            {txState.phase === "idle" && (
              <button
                onClick={handleTranscribe}
                className="flex items-center gap-2 rounded-lg border border-white/[0.1] bg-[#0d0f14] px-3.5 py-1.5 text-[12px] font-medium text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff]"
              >
                <svg className="h-3 w-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 2v4m0 0 2-2m-2 2L6 4M3 10a5 5 0 0 0 10 0" />
                </svg>
                Download & Transcribe
              </button>
            )}
            {txState.phase === "ingesting" && (
              <span className="flex items-center gap-2 text-[12px] text-zinc-500">
                <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border border-zinc-600 border-t-[#00d4ff]" />
                Queuing…
              </span>
            )}
            {txState.phase === "processing" && (
              <span className="flex items-center gap-2 text-[12px] text-zinc-500">
                <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border border-zinc-600 border-t-[#00d4ff]" />
                <EpisodeStatusLabel episode_id={txState.episode_id} />
              </span>
            )}
            {txState.phase === "done" && (
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-[12px] text-emerald-500/80">
                  <svg className="h-3 w-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l3.5 3.5L13 5" />
                  </svg>
                  Transcribed · {txState.nugget_count} nuggets
                </span>
                <a
                  href={`/episode/${txState.episode_id}`}
                  className="rounded-lg border border-[#00d4ff]/30 bg-[#00d4ff]/5 px-3.5 py-1.5 text-[12px] font-medium text-[#00d4ff] transition hover:bg-[#00d4ff]/10"
                  onClick={(e) => e.stopPropagation()}
                >
                  View nuggets →
                </a>
              </div>
            )}
            {txState.phase === "error" && (
              <div className="flex items-center gap-3">
                <span className="text-[12px] text-red-400/70">{txState.message}</span>
                <button onClick={handleTranscribe} className="text-[11px] text-zinc-600 underline hover:text-zinc-400">
                  Retry
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function EpisodeStatusLabel({ episode_id }: { episode_id: number }) {
  const [label, setLabel] = useState("Processing…");
  useEffect(() => {
    const iv = setInterval(async () => {
      try {
        const s = await getEpisodeStatus(episode_id);
        setLabel(STATUS_LABEL[s.status] ?? "Processing…");
      } catch { /* ignore */ }
    }, 4000);
    return () => clearInterval(iv);
  }, [episode_id]);
  return <>{label}</>;
}

// ─── page ─────────────────────────────────────────────────────────────────────

export default function ScoutPage() {
  const [sphereReady,   setSphereReady]   = useState(false);
  const [appearances,   setAppearances]   = useState<ScoutAppearance[]>([]);
  const [loading,       setLoading]       = useState(true);
  const [refreshing,    setRefreshing]    = useState(false);
  const [lastNew,       setLastNew]       = useState<number | null>(null);
  const [filterCompany, setFilterCompany] = useState("");

  // Watchlist state — hydrated from localStorage on mount
  const [watchlist, setWatchlist] = useState<Category[]>(WATCHLIST_DEFAULT);
  const [addingTo,  setAddingTo]  = useState<string | null>(null);

  useEffect(() => { setWatchlist(loadWatchlist()); }, []);

  function saveWatchlist(next: Category[]) {
    setWatchlist(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  function deleteCompany(catLabel: string, name: string) {
    saveWatchlist(
      watchlist.map((cat) =>
        cat.label === catLabel
          ? { ...cat, companies: cat.companies.filter((c) => c.name !== name) }
          : cat
      )
    );
  }

  function addCompany(catLabel: string, name: string, ticker: string) {
    if (!name) return;
    saveWatchlist(
      watchlist.map((cat) =>
        cat.label === catLabel
          ? { ...cat, companies: [...cat.companies, { name, ...(ticker ? { ticker } : {}) }] }
          : cat
      )
    );
    setAddingTo(null);
  }

  const total = watchlist.reduce((s, c) => s + c.companies.length, 0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getScoutAppearances({ days: 90 });
      setAppearances(data);
    } catch { /* backend may not be running */ }
    finally  { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleRefresh() {
    setRefreshing(true);
    setLastNew(null);
    try {
      const res = await refreshScout(7);
      setLastNew(res.new);
      await load();
    } catch { /* ignore */ }
    finally  { setRefreshing(false); }
  }

  const filtered = filterCompany
    ? appearances.filter((a) => a.company === filterCompany)
    : appearances;

  const uniqueCompanies = [...new Set(appearances.map((a) => a.company))].sort();

  return (
    <>
      <Script
        src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
        onReady={() => setSphereReady(true)}
      />

      <div className="fixed inset-0 z-[2] bg-[#0a0a0c]/82" />
      <div className="fixed inset-0 top-14 z-[3]">
        {sphereReady && <NeonSphere />}
      </div>

      <div className="relative z-[4] pt-10">

        {/* ── Masthead ── */}
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
              <span className="inline-block h-px w-8 bg-[#00d4ff]" />
              <span className="text-[#00d4ff]">Scout</span>
            </p>
            <h1 className="mt-3 text-5xl font-light leading-[1.04] tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-6xl">
              On the <span className="text-[#00d4ff]">radar</span>.
            </h1>
            <p className="mt-2.5 text-[13px] text-zinc-600">
              {total} companies · {watchlist.length} sectors · Founders and Management
            </p>
          </div>

          {/* Refresh */}
          <div className="flex shrink-0 flex-col items-end gap-2 pt-1">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-2 rounded-lg border border-white/[0.1] bg-[#0b0c10]/80 px-4 py-2 text-[13px] font-medium text-zinc-300 shadow-sm transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff] disabled:opacity-40"
            >
              <svg
                className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
                viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8"
              >
                <path d="M13.5 8A5.5 5.5 0 1 1 8 2.5" strokeLinecap="round" />
                <path d="M8 1v3.5H4.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {refreshing ? "Scanning…" : "Refresh"}
            </button>
            {lastNew !== null && (
              <p className="text-[11px] text-[#00d4ff]/60">
                {lastNew > 0 ? `+${lastNew} new appearances` : "Up to date"}
              </p>
            )}
          </div>
        </div>

        {/* ── Three-column layout ── */}
        <div className="mt-8 grid grid-cols-[240px_1fr_240px] gap-5">

          {/* ── Companies ── */}
          <div className="rounded-xl border border-white/[0.05] bg-[#0a0a0c]/60 p-4">
            <div className="mb-3 flex items-center justify-between border-b border-white/[0.05] pb-3">
              <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-400">Companies</span>
              <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[10px] tabular-nums text-zinc-600">{total}</span>
            </div>
            <div className="space-y-4">
              {watchlist.map((cat) => (
                <div key={cat.label}>
                  {/* section header with + button */}
                  <div className="flex items-center justify-between pb-2 pt-1">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-600">
                      {cat.label}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] tabular-nums text-zinc-700">{cat.companies.length}</span>
                      <button
                        onClick={() => setAddingTo(addingTo === cat.label ? null : cat.label)}
                        className="flex h-4 w-4 items-center justify-center rounded text-[10px] text-zinc-700 transition hover:bg-white/[0.06] hover:text-zinc-300"
                        title={`Add to ${cat.label}`}
                      >
                        {addingTo === cat.label ? "−" : "+"}
                      </button>
                    </div>
                  </div>

                  {/* add form */}
                  {addingTo === cat.label && (
                    <AddCompanyRow
                      onAdd={(n, t) => addCompany(cat.label, n, t)}
                      onCancel={() => setAddingTo(null)}
                    />
                  )}

                  {/* company rows */}
                  <div>
                    {cat.companies.map((co) => (
                      <CompanyRow
                        key={`${cat.label}-${co.name}`}
                        co={co}
                        onDelete={() => deleteCompany(cat.label, co.name)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* ── Appearances feed ── */}
          <div className="min-w-0">
            {/* company filter pills */}
            {uniqueCompanies.length > 0 && (
              <div className="mb-4 flex flex-wrap gap-1.5">
                <button
                  onClick={() => setFilterCompany("")}
                  className={`rounded-full border px-2.5 py-0.5 text-[11px] transition ${
                    filterCompany === ""
                      ? "border-[#00d4ff]/40 bg-[#00d4ff]/8 text-[#00d4ff]"
                      : "border-white/[0.05] text-zinc-600 hover:border-white/[0.12] hover:text-zinc-400"
                  }`}
                >
                  All
                </button>
                {uniqueCompanies.map((co) => (
                  <button
                    key={co}
                    onClick={() => setFilterCompany(co === filterCompany ? "" : co)}
                    className={`rounded-full border px-2.5 py-0.5 text-[11px] transition ${
                      filterCompany === co
                        ? "border-[#00d4ff]/40 bg-[#00d4ff]/8 text-[#00d4ff]"
                        : "border-white/[0.05] text-zinc-600 hover:border-white/[0.12] hover:text-zinc-400"
                    }`}
                  >
                    {co}
                  </button>
                ))}
              </div>
            )}

            {!loading && (
              <div className="space-y-2.5">
                {filtered.map((a) => (
                  <AppearanceCard key={a.id} a={a} />
                ))}
              </div>
            )}
          </div>

          {/* ── Creators ── */}
          <div className="rounded-xl border border-white/[0.05] bg-[#0a0a0c]/60 p-4">
            <div className="mb-3 flex items-center justify-between border-b border-white/[0.05] pb-3">
              <span className="text-[11px] font-semibold uppercase tracking-[0.2em] text-zinc-400">Creators</span>
              <span className="rounded-full bg-white/[0.04] px-2 py-0.5 text-[10px] text-zinc-600">0</span>
            </div>
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full border border-white/[0.06] bg-white/[0.02]">
                <svg className="h-4 w-4 text-zinc-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                </svg>
              </div>
              <p className="text-[12px] font-medium text-zinc-200">X accounts &amp; sources</p>
              <p className="mt-1 text-[11px] leading-relaxed text-zinc-700">
                Link creator accounts<br />to track here
              </p>
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
