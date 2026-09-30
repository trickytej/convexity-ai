import Link from "next/link";

export const metadata = { title: "About — ConvexityAI" };

const PIPELINE = [
  {
    step: "Listen",
    text: "Podcasts, investment newsletters, and X are ingested continuously, transcribed, speaker-mapped, and corrected so nothing said off the record of a filing gets lost.",
  },
  {
    step: "Distill",
    text: "Every hour of audio and page of text is reduced to discrete, sourced insights, scored for novelty, conviction, and materiality.",
  },
  {
    step: "Weigh",
    text: "Each new insight is weighed against the questions that actually decide your positions.",
  },
  {
    step: "Surface",
    text: "You wake up to a Brief: what happened, which thesis it touches, and why it matters.",
  },
];

export default function AboutPage() {
  return (
    <div>
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">About</span>
      </p>

      <h1 className="mt-5 max-w-3xl text-5xl font-light leading-[1.04] tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-6xl">
        Research is abundant.
        <br />
        <span className="text-[#00d4ff]">Judgement is rare.</span>
      </h1>

      <div className="mt-8 max-w-2xl space-y-5 text-[15px] leading-relaxed text-zinc-400">
        <p>
          For most securities, four or five questions decide the outcome. Analysts spend
          hours crafting the theses, but the evidence that answers those questions is
          scattered across X, newsletters, podcasts, or broker reports.
        </p>
        <p>
          ConvexityAI is built on a simple premise: do the thinking up front, and let the
          machine do the listening. It reads the flow so you don&apos;t have to, and tells
          you when something touches a question you care about. That frees your time to
          focus on finding differentiated insight and exercising judgement.
        </p>
      </div>

      {/* how it works */}
      <p className="mt-14 flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]/50" />
        <span className="text-zinc-500">How it works</span>
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {PIPELINE.map((p, i) => (
          <div
            key={p.step}
            className="rounded-2xl border border-[#00d4ff]/[0.18] bg-[#0d1a2e]/85 p-6"
          >
            <div className="flex items-baseline gap-3">
              <span className="rounded-[5px] border border-[#00d4ff]/40 px-1.5 py-1 font-[family-name:var(--font-mono)] text-[11px] leading-none text-[#00d4ff]">
                0{i + 1}
              </span>
              <h2 className="text-lg font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
                {p.step}
              </h2>
            </div>
            <p className="mt-3 text-[13px] leading-relaxed text-zinc-300">{p.text}</p>
          </div>
        ))}
      </div>

      {/* substack */}
      <p className="mt-14 flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]/50" />
        <span className="text-zinc-500">The writing</span>
      </p>

      <a
        href="https://crossoverconvexity.substack.com"
        target="_blank"
        rel="noopener noreferrer"
        className="group mt-5 flex flex-col rounded-2xl border border-[#00d4ff]/[0.18] bg-[#0d1a2e]/85 p-6 transition hover:border-[#00d4ff]/45 hover:bg-[#102038]/90 sm:max-w-xl"
      >
        <h2 className="text-xl font-light tracking-tight text-zinc-50 transition [font-family:var(--font-display)] group-hover:text-[#00d4ff]">
          Crossover Convexity
        </h2>
        <p className="mt-2 text-[13px] leading-relaxed text-zinc-300">
          The ideas behind this platform, in long form analysis, published on Substack.
        </p>
        <span className="mt-4 text-[12px] font-medium text-zinc-400 transition group-hover:text-[#00d4ff]">
          crossoverconvexity.substack.com ↗
        </span>
      </a>

      <p className="mt-14 border-t border-white/[0.06] pt-6 text-[12px] text-zinc-600">
        Built by{" "}
        <Link href="/theses" className="text-zinc-500 transition hover:text-[#00d4ff]">
          an investor
        </Link>
        , for the way investors actually work.
      </p>
    </div>
  );
}
