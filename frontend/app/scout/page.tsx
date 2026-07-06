"use client";

import dynamic from "next/dynamic";
import Script from "next/script";
import { useState, useEffect, useCallback, useRef } from "react";
import { getScoutAppearances, reprocessPendingScout, ingestScoutAppearance, processEpisode, getEpisodeStatus, type ScoutAppearance } from "@/lib/api";

const NeonSphere = dynamic(() => import("@/components/NeonSphere"), { ssr: false });

// ─── watchlist data ───────────────────────────────────────────────────────────

type Person   = { name: string; role: string };
type Company  = { name: string; ticker?: string; people?: Person[] };
type Category = { label: string; companies: Company[] };

const WATCHLIST_DEFAULT: Category[] = [
  {
    label: "Privates",
    companies: [
      { name: "Anthropic",  people: [{ name: "Dario Amodei",    role: "CEO & Co-founder" },    { name: "Daniela Amodei", role: "President & Co-founder" }, { name: "Tom Brown",   role: "Co-founder" }, { name: "Chris Olah", role: "Co-founder & Research Scientist" }] },
      { name: "OpenAI",     people: [{ name: "Sam Altman",      role: "CEO" },                 { name: "Greg Brockman",  role: "Co-founder & President" }, { name: "Jakub Pachocki", role: "Chief Scientist" }, { name: "Brad Lightcap", role: "COO" }] },
      { name: "xAI",        people: [{ name: "Elon Musk",       role: "Founder & CEO" }] },
      { name: "Databricks", people: [{ name: "Ali Ghodsi",      role: "CEO & Co-founder" },    { name: "Ion Stoica",     role: "Co-founder & Executive Chairman" }, { name: "Matei Zaharia", role: "Co-founder & CTO" }] },
      { name: "Stripe",     people: [{ name: "Patrick Collison", role: "CEO & Co-founder" },   { name: "John Collison",  role: "President & Co-founder" }] },
      { name: "Anduril",    people: [{ name: "Palmer Luckey",   role: "Founder" },             { name: "Brian Schimpf",  role: "CEO & Co-founder" }] },
      { name: "Figure",     people: [{ name: "Brett Adcock",    role: "CEO & Founder" }] },
      { name: "Perplexity", people: [{ name: "Aravind Srinivas", role: "CEO & Co-founder" }] },
      { name: "Sierra",     people: [{ name: "Bret Taylor",     role: "CEO & Co-founder" },    { name: "Clay Bavor",     role: "Co-founder" }] },
      { name: "Crusoe",     people: [{ name: "Chase Lochmiller", role: "CEO & Co-founder" }] },
      { name: "Groq",       people: [{ name: "Jonathan Ross",   role: "CEO & Founder" }] },
      { name: "Cohere",     people: [{ name: "Aidan Gomez",     role: "CEO & Co-founder" },    { name: "Nick Frosst",    role: "Co-founder" }] },
      { name: "Mistral",    people: [{ name: "Arthur Mensch",   role: "CEO & Co-founder" },    { name: "Guillaume Lample", role: "Co-founder" }] },
      { name: "Scale AI",   people: [{ name: "Alexandr Wang",   role: "CEO & Founder" }] },
      { name: "Waymo",      people: [{ name: "Dmitri Dolgov",   role: "CEO & Co-founder" },    { name: "Tekedra Mawakana", role: "Co-CEO" }] },
      { name: "SpaceX",     people: [{ name: "Gwynne Shotwell", role: "President & COO" }] },
    ],
  },
  {
    label: "Semiconductors",
    companies: [
      { name: "Nvidia",             ticker: "NVDA",      people: [{ name: "Jensen Huang",       role: "CEO & Co-founder" }, { name: "Colette Kress",       role: "CFO" },                  { name: "Bill Dally",         role: "Chief Scientist" }] },
      { name: "TSMC",               ticker: "TSM",       people: [{ name: "C.C. Wei",           role: "CEO" },              { name: "Morris Chang",        role: "Founder" }] },
      { name: "Broadcom",           ticker: "AVGO",      people: [{ name: "Hock Tan",           role: "CEO" },              { name: "Kirsten Spears",      role: "CFO" }] },
      { name: "Micron",             ticker: "MU",        people: [{ name: "Sanjay Mehrotra",    role: "CEO" }] },
      { name: "AMD",                ticker: "AMD",       people: [{ name: "Lisa Su",            role: "CEO" },              { name: "Mark Papermaster",    role: "CTO" }] },
      { name: "ASML",               ticker: "ASML",      people: [{ name: "Christophe Fouquet", role: "CEO" },              { name: "Roger Dassen",        role: "CFO" }] },
      { name: "Intel",              ticker: "INTC",      people: [{ name: "Lip-Bu Tan",         role: "CEO" }] },
      { name: "ARM",                ticker: "ARM",       people: [{ name: "Rene Haas",          role: "CEO" }] },
      { name: "Lam Research",       ticker: "LRCX",      people: [{ name: "Tim Archer",         role: "CEO" }] },
      { name: "Applied Materials",  ticker: "AMAT",      people: [{ name: "Gary Dickerson",     role: "CEO" }] },
      { name: "KLA",                ticker: "KLAC",      people: [{ name: "Rick Wallace",       role: "CEO" }] },
      { name: "Texas Instruments",  ticker: "TXN",       people: [{ name: "Haviv Ilan",         role: "CEO" }] },
      { name: "Marvell",            ticker: "MRVL",      people: [{ name: "Matt Murphy",        role: "CEO" }] },
      { name: "Qualcomm",           ticker: "QCOM",      people: [{ name: "Cristiano Amon",     role: "CEO" }] },
      { name: "Analog Devices",     ticker: "ADI",       people: [{ name: "Vincent Roche",      role: "CEO" }] },
      { name: "Cadence",            ticker: "CDNS",      people: [{ name: "Anirudh Devgan",     role: "CEO" }] },
      { name: "Synopsys",           ticker: "SNPS",      people: [{ name: "Sassine Ghazi",      role: "CEO" }] },
      { name: "NXP",                ticker: "NXPI",      people: [{ name: "Kurt Sievers",       role: "CEO" }] },
      { name: "Mobileye",           ticker: "MBLY",      people: [{ name: "Amnon Shashua",      role: "CEO & Founder" }] },
      { name: "Lattice Semiconductor", ticker: "LSCC",   people: [{ name: "Ford Tamer",         role: "CEO" }] },
    ],
  },
  {
    label: "Mag 7",
    companies: [
      { name: "Apple",     ticker: "AAPL",  people: [{ name: "Tim Cook",          role: "CEO" },              { name: "Jeff Williams",       role: "COO" },                  { name: "Luca Maestri",       role: "CFO" }] },
      { name: "Alphabet",  ticker: "GOOGL", people: [{ name: "Sundar Pichai",     role: "CEO" },              { name: "Demis Hassabis",      role: "CEO Google DeepMind & Co-founder" }, { name: "Ruth Porat", role: "President & CFO" }, { name: "Sergey Brin", role: "Co-founder" }, { name: "Larry Page", role: "Co-founder" }] },
      { name: "Microsoft", ticker: "MSFT",  people: [{ name: "Satya Nadella",     role: "CEO" },              { name: "Brad Smith",          role: "President & Vice Chair" }, { name: "Kevin Scott", role: "CTO & EVP AI" }] },
      { name: "Amazon",    ticker: "AMZN",  people: [{ name: "Andy Jassy",        role: "CEO" },              { name: "Jeff Bezos",          role: "Founder & Executive Chairman" }, { name: "Matt Garman", role: "CEO Amazon Web Services" }] },
      { name: "Meta",      ticker: "META",  people: [{ name: "Mark Zuckerberg",   role: "CEO & Co-founder" }, { name: "Yann LeCun",          role: "Chief AI Scientist" },    { name: "Andrew Bosworth", role: "CTO" }] },
      { name: "Tesla",     ticker: "TSLA",  people: [{ name: "Elon Musk",         role: "CEO & Co-founder" }, { name: "Vaibhav Taneja",      role: "CFO" }] },
      { name: "Nvidia",    ticker: "NVDA",  people: [{ name: "Jensen Huang",      role: "CEO & Co-founder" }, { name: "Colette Kress",       role: "CFO" }] },
    ],
  },
  {
    label: "Software",
    companies: [
      { name: "Oracle",             ticker: "ORCL", people: [{ name: "Larry Ellison",    role: "Founder & CTO" },    { name: "Safra Catz",         role: "CEO" }] },
      { name: "Palantir",           ticker: "PLTR", people: [{ name: "Alex Karp",        role: "CEO & Co-founder" }, { name: "Peter Thiel",        role: "Co-founder" }] },
      { name: "Cisco",              ticker: "CSCO", people: [{ name: "Chuck Robbins",    role: "CEO" }] },
      { name: "SAP",                ticker: "SAP",  people: [{ name: "Christian Klein",  role: "CEO" }] },
      { name: "Salesforce",         ticker: "CRM",  people: [{ name: "Marc Benioff",     role: "CEO & Founder" }] },
      { name: "IBM",                ticker: "IBM",  people: [{ name: "Arvind Krishna",   role: "CEO" }] },
      { name: "AppLovin",           ticker: "APP",  people: [{ name: "Adam Foroughi",    role: "CEO & Co-founder" }] },
      { name: "ServiceNow",         ticker: "NOW",  people: [{ name: "Bill McDermott",   role: "CEO" }] },
      { name: "Intuit",             ticker: "INTU", people: [{ name: "Sasan Goodarzi",   role: "CEO" }] },
      { name: "Adobe",              ticker: "ADBE", people: [{ name: "Shantanu Narayen", role: "CEO" }] },
      { name: "Shopify",            ticker: "SHOP", people: [{ name: "Tobi Lütke",       role: "CEO & Founder" },    { name: "Harley Finkelstein", role: "President" }] },
      { name: "Palo Alto Networks", ticker: "PANW", people: [{ name: "Nikesh Arora",     role: "CEO" }] },
      { name: "CrowdStrike",        ticker: "CRWD", people: [{ name: "George Kurtz",     role: "CEO & Co-founder" }] },
      { name: "Snowflake",          ticker: "SNOW", people: [{ name: "Sridhar Ramaswamy", role: "CEO" }] },
      { name: "Fortinet",           ticker: "FTNT", people: [{ name: "Ken Xie",          role: "CEO & Founder" }] },
      { name: "Workday",            ticker: "WDAY", people: [{ name: "Carl Eschenbach",  role: "CEO" }] },
      { name: "Datadog",            ticker: "DDOG", people: [{ name: "Olivier Pomel",    role: "CEO & Co-founder" }] },
      { name: "MongoDB",            ticker: "MDB",  people: [{ name: "Dev Ittycheria",   role: "CEO" }] },
      { name: "Cloudflare",         ticker: "NET",  people: [{ name: "Matthew Prince",   role: "CEO & Co-founder" }, { name: "Michelle Zatlyn",    role: "President & COO & Co-founder" }] },
      { name: "Confluent",          ticker: "CFLT", people: [{ name: "Jay Kreps",        role: "CEO & Co-founder" }] },
      { name: "HashiCorp",                          people: [{ name: "Armon Dadgar",      role: "Co-founder & CTO" }, { name: "Mitchell Hashimoto", role: "Co-founder" }] },
    ],
  },
  {
    label: "Internet",
    companies: [
      { name: "Netflix",          ticker: "NFLX", people: [{ name: "Ted Sarandos",    role: "Co-CEO" },              { name: "Greg Peters",      role: "Co-CEO" },               { name: "Reed Hastings",    role: "Co-founder & Executive Chairman" }] },
      { name: "Uber",             ticker: "UBER", people: [{ name: "Dara Khosrowshahi", role: "CEO" },              { name: "Travis Kalanick",  role: "Co-founder" }] },
      { name: "Booking Holdings", ticker: "BKNG", people: [{ name: "Glenn Fogel",      role: "CEO" }] },
      { name: "Spotify",          ticker: "SPOT", people: [{ name: "Daniel Ek",        role: "CEO & Co-founder" }] },
      { name: "MercadoLibre",     ticker: "MELI", people: [{ name: "Marcos Galperin",  role: "CEO & Founder" }] },
      { name: "DoorDash",         ticker: "DASH", people: [{ name: "Tony Xu",          role: "CEO & Co-founder" }] },
      { name: "Sea Ltd",          ticker: "SE",   people: [{ name: "Forrest Li",       role: "CEO & Founder" }] },
      { name: "Airbnb",           ticker: "ABNB", people: [{ name: "Brian Chesky",     role: "CEO & Co-founder" },    { name: "Joe Gebbia",       role: "Co-founder" },           { name: "Nathan Blecharczyk", role: "Co-founder & Chief Strategy Officer" }] },
      { name: "PayPal",           ticker: "PYPL", people: [{ name: "Alex Chriss",      role: "CEO" },                 { name: "Peter Thiel",      role: "Co-founder" }] },
      { name: "Coupang",          ticker: "CPNG", people: [{ name: "Bom Kim",          role: "CEO & Founder" }] },
      { name: "Block",            ticker: "XYZ",  people: [{ name: "Jack Dorsey",      role: "CEO & Founder" }] },
      { name: "Roblox",           ticker: "RBLX", people: [{ name: "David Baszucki",   role: "CEO & Founder" }] },
      { name: "Robinhood",        ticker: "HOOD", people: [{ name: "Vlad Tenev",       role: "CEO & Co-founder" },    { name: "Baiju Bhatt",      role: "Co-founder" }] },
      { name: "Reddit",           ticker: "RDDT", people: [{ name: "Steve Huffman",    role: "CEO & Co-founder" }] },
      { name: "Pinterest",        ticker: "PINS", people: [{ name: "Bill Ready",       role: "CEO" },                 { name: "Ben Silbermann",   role: "Co-founder & Executive Chairman" }] },
      { name: "Lyft",             ticker: "LYFT", people: [{ name: "David Risher",     role: "CEO" }] },
      { name: "Instacart",        ticker: "CART", people: [{ name: "Fidji Simo",       role: "CEO" }] },
      { name: "Duolingo",         ticker: "DUOL", people: [{ name: "Luis von Ahn",     role: "CEO & Co-founder" }] },
    ],
  },
];

const STORAGE_KEY = "scout-watchlist-v3";

function loadWatchlist(): Category[] {
  if (typeof window === "undefined") return WATCHLIST_DEFAULT;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return WATCHLIST_DEFAULT;
    const parsed = JSON.parse(saved) as Category[];
    // Back-fill people from WATCHLIST_DEFAULT for any company that has none saved
    return parsed.map((cat) => {
      const defCat = WATCHLIST_DEFAULT.find((c) => c.label === cat.label);
      return {
        ...cat,
        companies: cat.companies.map((co) => {
          if (co.people && co.people.length > 0) return co;
          const defCo = defCat?.companies.find((c) => c.name === co.name);
          return defCo?.people ? { ...co, people: defCo.people } : co;
        }),
      };
    });
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
  onAddPerson,
  seenPeople,
}: {
  co: Company;
  onDelete: () => void;
  onAddPerson: (person: Person) => void;
  seenPeople: Person[];
}) {
  const [expanded,    setExpanded]    = useState(false);
  const [hovered,     setHovered]     = useState(false);
  const [addingPerson,setAddingPerson]= useState(false);
  const [pName,       setPName]       = useState("");
  const [pRole,       setPRole]       = useState("");
  const nameRef = useRef<HTMLInputElement>(null);
  useEffect(() => { if (addingPerson) nameRef.current?.focus(); }, [addingPerson]);

  // Merge roster people — always pull from WATCHLIST_DEFAULT as the source of truth,
  // then layer in any people stored on co (user additions) and seenPeople from appearances.
  const defaultPeople =
    WATCHLIST_DEFAULT.flatMap((c) => c.companies)
      .find((c) => c.name === co.name)?.people ?? [];
  const savedPeople = co.people ?? [];
  const rosterPeople: Person[] = [...defaultPeople];
  for (const p of savedPeople) {
    if (!rosterPeople.find((r) => r.name === p.name)) rosterPeople.push(p);
  }
  const allPeople: Person[] = [...rosterPeople];
  for (const p of seenPeople) {
    if (!allPeople.find((r) => r.name === p.name)) allPeople.push(p);
  }

  function submitPerson() {
    const n = pName.trim();
    if (!n) return;
    onAddPerson({ name: n, role: pRole.trim() });
    setPName(""); setPRole(""); setAddingPerson(false);
  }

  return (
    <div className="border-b border-white/[0.03] last:border-0">
      {/* row header */}
      <div
        className="group flex cursor-pointer items-center justify-between py-[7px] px-1 -mx-1 rounded transition hover:bg-white/[0.02]"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex min-w-0 items-center gap-2">
          <span className={`text-[9px] transition-transform duration-150 text-zinc-600 ${expanded ? "rotate-90" : ""}`}>▶</span>
          <span className="truncate text-[13px] text-zinc-200">{co.name}</span>
        </div>
        <div className="flex items-center gap-2 ml-2 shrink-0">
          {co.ticker && !hovered && (
            <span className="font-[family-name:var(--font-mono)] text-[10px] text-zinc-700">{co.ticker}</span>
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

      {/* expanded people panel */}
      {expanded && (
        <div className="mb-2 ml-3 rounded-lg border border-[#00d4ff]/10 bg-[#00d4ff]/[0.03] px-3 py-2.5">
          {allPeople.length === 0 ? (
            <p className="text-[11px] text-zinc-700">No people tracked yet</p>
          ) : (
            <div className="space-y-1.5 mb-2">
              {allPeople.map((p) => (
                <div key={p.name} className="flex items-baseline gap-2">
                  <span className="text-[12px] font-medium text-zinc-300">{p.name}</span>
                  {p.role && <span className="text-[11px] text-zinc-600">{p.role}</span>}
                </div>
              ))}
            </div>
          )}

          {addingPerson ? (
            <div className="mt-2 flex flex-col gap-1.5">
              <input
                ref={nameRef}
                value={pName}
                onChange={(e) => setPName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") submitPerson(); if (e.key === "Escape") setAddingPerson(false); }}
                placeholder="Name"
                className="rounded bg-white/[0.04] px-2 py-1 text-[11px] text-zinc-200 outline-none placeholder:text-zinc-700 focus:ring-1 focus:ring-[#00d4ff]/30"
              />
              <input
                value={pRole}
                onChange={(e) => setPRole(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") submitPerson(); if (e.key === "Escape") setAddingPerson(false); }}
                placeholder="Role (e.g. CEO)"
                className="rounded bg-white/[0.04] px-2 py-1 text-[11px] text-zinc-200 outline-none placeholder:text-zinc-700 focus:ring-1 focus:ring-[#00d4ff]/30"
              />
              <div className="flex gap-2">
                <button onClick={submitPerson}       className="text-[11px] text-[#00d4ff] transition hover:text-[#33ddff]">Add</button>
                <button onClick={() => setAddingPerson(false)} className="text-[11px] text-zinc-600 transition hover:text-zinc-400">Cancel</button>
              </div>
            </div>
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); setAddingPerson(true); }}
              className="mt-1 flex items-center gap-1 text-[11px] text-zinc-700 transition hover:text-[#00d4ff]"
            >
              <span className="text-[10px]">+</span> Add person
            </button>
          )}
        </div>
      )}
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
          startPoll(a.episode_id!);
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
  const [scanErrors,    setScanErrors]    = useState<string[]>([]);
  const [filterCompany, setFilterCompany] = useState("");

  // Watchlist state — hydrated from localStorage on mount
  const [watchlist,      setWatchlist]      = useState<Category[]>(WATCHLIST_DEFAULT);
  const [addingTo,       setAddingTo]       = useState<string | null>(null);
  const [watchlistOpen,  setWatchlistOpen]  = useState(false);
  const watchlistRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (watchlistRef.current && !watchlistRef.current.contains(e.target as Node)) {
        setWatchlistOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Date range — default last 7 days, matching the Insights tab default
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 7);
    return d.toISOString().slice(0, 10);
  });
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().slice(0, 10));

  const days = Math.max(1, Math.ceil((Date.now() - new Date(dateFrom).getTime()) / 86400000));

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

  function addPersonToCompany(catLabel: string, coName: string, person: Person) {
    saveWatchlist(
      watchlist.map((cat) =>
        cat.label === catLabel
          ? {
              ...cat,
              companies: cat.companies.map((co) =>
                co.name === coName
                  ? { ...co, people: [...(co.people ?? []), person] }
                  : co
              ),
            }
          : cat
      )
    );
  }

  const total = watchlist.reduce((s, c) => s + c.companies.length, 0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getScoutAppearances({ days });
      setAppearances(data);
    } catch { /* backend may not be running */ }
    finally  { setLoading(false); }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  async function handleRefresh() {
    // Podscan search + transcription now run on a nightly schedule (see
    // .github/workflows/scout.yml); this just reloads what that job has
    // already produced and retries insight extraction for anything left
    // transcribed/failed (fast — no Podscan/AssemblyAI calls).
    setRefreshing(true);
    setLastNew(null);
    setScanErrors([]);
    try {
      const { queued } = await reprocessPendingScout();
      setLastNew(queued);
      await load();
    } catch (err: unknown) {
      setScanErrors([err instanceof Error ? err.message : "Refresh failed"]);
    } finally {
      setRefreshing(false);
    }
  }

  const fromDate = new Date(dateFrom);
  const toDate   = new Date(dateTo + "T23:59:59.999Z");

  const filtered = appearances
    .filter((a) => {
      if (!a.published_at) return true;
      const pub = new Date(a.published_at);
      return pub >= fromDate && pub <= toDate;
    })
    .filter((a) => !filterCompany || a.company === filterCompany);

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
              Listening for <span className="text-[#00d4ff]">Insights</span>.
            </h1>
          </div>

          {/* Refresh */}
          <div className="flex shrink-0 flex-col items-end gap-2 pt-1">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-2 rounded-lg px-4 py-2 text-[13px] font-medium transition disabled:opacity-40 bg-[#00d4ff] text-[#001a26] hover:bg-[#00d4ff]/90"
            >
              <svg
                className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
                viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8"
              >
                <path d="M13.5 8A5.5 5.5 0 1 1 8 2.5" strokeLinecap="round" />
                <path d="M8 1v3.5H4.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {refreshing ? "Refreshing…" : "Refresh"}
            </button>
            {!refreshing && lastNew !== null && scanErrors.length === 0 && (
              <p className="text-[11px] text-[#00d4ff]/60">
                {lastNew > 0 ? `Retrying ${lastNew} pending` : "Up to date"}
              </p>
            )}
            {!refreshing && scanErrors.length > 0 && (
              <p className="max-w-xs text-right text-[11px] text-red-400/80" title={scanErrors.join("\n")}>
                {scanErrors[0]}
              </p>
            )}
          </div>
        </div>

        {/* ── Date range + Watchlist button ── */}
        <div className="mt-6 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-widest text-zinc-600">From</label>
            <input
              type="date"
              value={dateFrom}
              max={dateTo}
              onChange={(e) => setDateFrom(e.target.value)}
              className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[13px] text-zinc-300 outline-none focus:border-[#00d4ff]/40 focus:ring-1 focus:ring-[#00d4ff]/20 [color-scheme:dark]"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[11px] uppercase tracking-widest text-zinc-600">To</label>
            <input
              type="date"
              value={dateTo}
              min={dateFrom}
              onChange={(e) => setDateTo(e.target.value)}
              className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-[13px] text-zinc-300 outline-none focus:border-[#00d4ff]/40 focus:ring-1 focus:ring-[#00d4ff]/20 [color-scheme:dark]"
            />
          </div>

          {/* Watchlist button + dropdown */}
          <div className="relative self-end" ref={watchlistRef}>
            <button
              onClick={() => setWatchlistOpen((v) => !v)}
              className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-[13px] font-medium transition ${
                watchlistOpen
                  ? "border-[#00d4ff]/40 bg-[#00d4ff]/10 text-[#00d4ff]"
                  : "border-white/[0.08] bg-white/[0.03] text-zinc-400 hover:border-[#00d4ff]/30 hover:text-zinc-200"
              }`}
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6">
                <path strokeLinecap="round" d="M2 4h12M2 8h8M2 12h5" />
              </svg>
              Watchlist
              <span className="rounded-full bg-white/[0.07] px-1.5 py-0.5 text-[10px] tabular-nums text-zinc-500">
                {watchlist.reduce((s, c) => s + c.companies.length, 0)}
              </span>
            </button>

            {watchlistOpen && (
              <div className="absolute left-0 top-full z-50 mt-2 w-72 rounded-xl border border-white/[0.08] bg-[#0d0e12] shadow-2xl">
                <div className="max-h-[70vh] overflow-y-auto p-3">
                  {watchlist.map((cat) => (
                    <div key={cat.label} className="mb-3 last:mb-0">
                      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-600">
                        {cat.label} <span className="text-zinc-700">· {cat.companies.length}</span>
                      </p>
                      <div className="space-y-0.5">
                        {cat.companies.map((co) => {
                          const people =
                            WATCHLIST_DEFAULT.flatMap((c) => c.companies)
                              .find((c) => c.name === co.name)?.people ?? co.people ?? [];
                          return (
                            <div key={co.name} className="rounded-lg px-2 py-1.5 transition hover:bg-white/[0.04]">
                              <div className="flex items-center gap-2">
                                <span className="text-[13px] text-zinc-200">{co.name}</span>
                                {co.ticker && (
                                  <span className="font-[family-name:var(--font-mono)] text-[10px] text-zinc-700">{co.ticker}</span>
                                )}
                              </div>
                              {people.length > 0 && (
                                <div className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5">
                                  {people.map((p) => (
                                    <span key={p.name} className="text-[11px] text-zinc-600">{p.name}</span>
                                  ))}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Three-column layout ── */}
        <div className="mt-5 grid grid-cols-[240px_1fr_240px] gap-5">

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
                    <span className="text-[11px] font-semibold uppercase tracking-[0.22em] text-zinc-600">
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
                    {cat.companies.map((co) => {
                      const seenPeople = [
                        ...new Map(
                          appearances
                            .filter((a) => a.company === co.name && a.person_name)
                            .map((a) => [a.person_name, { name: a.person_name!, role: a.person_role ?? "" }])
                        ).values(),
                      ];
                      return (
                        <CompanyRow
                          key={`${cat.label}-${co.name}`}
                          co={co}
                          onDelete={() => deleteCompany(cat.label, co.name)}
                          onAddPerson={(p) => addPersonToCompany(cat.label, co.name, p)}
                          seenPeople={seenPeople}
                        />
                      );
                    })}
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
                  className={`rounded-full border px-2.5 py-0.5 text-[12px] transition ${
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
                    className={`rounded-full border px-2.5 py-0.5 text-[12px] transition ${
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
