import Link from "next/link";

export const metadata = { title: "Pro — ConvexityAI" };

const INCLUDED = [
  {
    title: "The research corpus, already listened to",
    text: "Podcasts, newsletters, SEC filings and Scout appearances, transcribed and distilled into sourced insights every day. No feeds to manage, no transcription bills.",
  },
  {
    title: "Company models, ready on day one",
    text: "Built-out models for 50 names, with segment builds, margins and consensus, plus our house What Matters questions for each, already matched to the evidence.",
  },
  {
    title: "Zero setup",
    text: "No API keys, no servers, no cron jobs. Sign in with Google and your board is live. Usage is covered by the subscription, within fair-use limits.",
  },
  {
    title: "Your agents, connected",
    text: "Personal API tokens and the MCP server, so Claude and your other tools can read your board, Brief and research directly.",
  },
];

const ANALYST = [
  {
    step: "Predict",
    text: "For every What Matters, the Analyst drafts dated, numeric, falsifiable predictions ahead of each print. Not “margins should improve”, but a range, a period and a confidence.",
  },
  {
    step: "Grade",
    text: "Each prediction is settled against the reported KPI. Every call it makes is kept in a ledger you can audit, so its track record is visible, not claimed.",
  },
  {
    step: "Learn",
    text: "When you keep, reframe or drop a question or a piece of evidence, and say why, that ruling teaches it. It learns from your judgement and from outcomes, never from P&L.",
  },
  {
    step: "Stay honest",
    text: "Everything is point-in-time: it only sees what was known on the day it made the call, so its record can't be flattered by hindsight.",
  },
];

function Eyebrow({ children, dim = false }: { children: React.ReactNode; dim?: boolean }) {
  return (
    <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
      <span className={`inline-block h-px w-8 ${dim ? "bg-[#00d4ff]/50" : "bg-[#00d4ff]"}`} />
      <span className={dim ? "text-zinc-500" : "text-[#00d4ff]"}>{children}</span>
    </p>
  );
}

export default function ProPage() {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-4">
        <Eyebrow>Pro</Eyebrow>
        <span className="rounded-full border border-[#00d4ff]/50 bg-[#00d4ff]/10 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-white shadow-[0_0_14px_rgba(0,212,255,0.25)]">
          Coming soon
        </span>
      </div>

      <h1 className="mt-5 max-w-3xl text-5xl font-light leading-[1.04] tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-6xl">
        An analyst that
        <br />
        <span className="text-[#00d4ff]">learns your judgement.</span>
      </h1>

      <p className="mt-8 max-w-2xl text-[15px] leading-relaxed text-zinc-400">
        ConvexityAI is open source: run it yourself with your own keys, free. Pro is the hosted
        version, with the research already listened to, the models already built, and an Analyst
        that recursively learns with you, makes calls on what matters, and gets better over time.
      </p>

      {/* ── plans ── */}
      <div className="mt-12 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/70 p-6">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-500">Open source</p>
          <p className="mt-3 text-3xl font-light text-zinc-100 [font-family:var(--font-display)]">Free</p>
          <p className="mt-1 text-[13px] text-zinc-500">Self-hosted · bring your own keys</p>
          <ul className="mt-5 space-y-2 text-[14px] text-zinc-400">
            <li>The full app: What Matters, Brief, Model, CIO, Research, Scout</li>
            <li>Your own sources, transcribed with your own API keys</li>
            <li>Your own models and questions</li>
            <li>AGPL-3.0 licensed</li>
          </ul>
        </div>
        <div className="rounded-xl border border-[#00d4ff]/50 bg-[#00d4ff]/[0.06] p-6 shadow-[0_0_24px_rgba(0,212,255,0.12)]">
          <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[#00d4ff]">Pro · hosted</p>
          <p className="mt-3 text-3xl font-light text-zinc-50 [font-family:var(--font-display)]">
            $99<span className="text-base text-zinc-400"> / month</span>
          </p>
          <p className="mt-1 text-[13px] text-zinc-400">Everything in open source, plus</p>
          <ul className="mt-5 space-y-2 text-[14px] text-zinc-200">
            <li>The shared research corpus, distilled daily</li>
            <li>50 built-out company models and house What Matters</li>
            <li>The Analyst: predictions, a graded ledger, and learning from your rulings</li>
            <li>No keys or setup, with fair-use limits</li>
          </ul>
        </div>
      </div>

      {/* ── what's included ── */}
      <div className="mt-14">
        <Eyebrow dim>What Pro includes</Eyebrow>
      </div>
      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {INCLUDED.map((f) => (
          <div key={f.title} className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 p-5">
            <p className="text-[15px] font-medium text-zinc-100">{f.title}</p>
            <p className="mt-2 text-[14px] leading-relaxed text-zinc-400">{f.text}</p>
          </div>
        ))}
      </div>

      {/* ── the analyst ── */}
      <div className="mt-14">
        <Eyebrow dim>The Analyst</Eyebrow>
      </div>
      <h2 className="mt-4 max-w-2xl text-3xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
        Calls you can check, from an agent that <span className="text-[#00d4ff]">learns over time</span>.
      </h2>
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {ANALYST.map((a, i) => (
          <div key={a.step} className="rounded-xl border border-white/[0.08] bg-[#0b0c10]/60 p-5">
            <p className="flex items-baseline gap-3">
              <span className="font-[family-name:var(--font-mono)] text-[12px] text-[#00d4ff]/70">0{i + 1}</span>
              <span className="text-[15px] font-medium text-zinc-100">{a.step}</span>
            </p>
            <p className="mt-2 text-[14px] leading-relaxed text-zinc-400">{a.text}</p>
          </div>
        ))}
      </div>

      <div className="mt-14 rounded-xl border border-white/[0.08] bg-[#0b0c10]/70 px-6 py-8 text-center">
        <p className="text-xl font-light text-zinc-100 [font-family:var(--font-display)]">Pro is coming soon.</p>
        <p className="mx-auto mt-2 max-w-lg text-[14px] text-zinc-500">
          Until then, everything on ConvexityAI is free to use.{" "}
          <Link href="/" className="text-[#00d4ff]/80 underline transition hover:text-[#00d4ff]">
            Back to Home
          </Link>
        </p>
      </div>
    </div>
  );
}
