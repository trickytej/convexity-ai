import Link from "next/link";
import { notFound } from "next/navigation";
import { auth } from "@/auth";
import { getBoard, getSecurityModel } from "@/lib/api";
import FollowToggle from "@/components/FollowToggle";
import WhatMattersPanel from "@/components/WhatMattersPanel";
import SecurityWorkspace from "@/components/SecurityWorkspace";

export const dynamic = "force-dynamic";

function SectionLabel({ children, count }: { children: React.ReactNode; count?: number }) {
  return (
    <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
      <span className="inline-block h-px w-8 bg-[#00d4ff]/50" />
      <span className="text-zinc-400">{children}</span>
      {count != null && (
        <span className="font-[family-name:var(--font-mono)] text-[11px] normal-case tracking-normal text-zinc-600">
          {count}
        </span>
      )}
    </p>
  );
}

// One security: What Matters → 3-year model → the developments behind it.
export default async function SecurityPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  let model;
  try {
    model = await getSecurityModel(decodeURIComponent(key));
  } catch {
    notFound();
  }
  const [session, board] = await Promise.all([auth(), getBoard().catch(() => ({ securities: [] }))]);

  return (
    <div>
      {/* switch between followed securities without leaving the Model tab */}
      <nav className="flex flex-wrap items-center gap-2">
        <Link href="/model" className="mr-2 text-[12px] text-zinc-600 transition hover:text-[#00d4ff]">
          ← All securities
        </Link>
        {board.securities.map((s) => {
          const active = s.company === model.company;
          return (
            <Link
              key={s.company}
              href={`/model/${encodeURIComponent(s.key)}`}
              className={`rounded-full border px-3 py-1 text-[12px] transition ${
                active
                  ? "border-[#00d4ff]/40 bg-[#00d4ff]/10 text-[#00d4ff]"
                  : "border-white/[0.08] text-zinc-400 hover:border-white/[0.18] hover:text-zinc-200"
              }`}
            >
              {s.ticker ?? s.company}
            </Link>
          );
        })}
      </nav>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
          {model.company}
          {model.ticker && (
            <span className="ml-3 font-[family-name:var(--font-mono)] text-xl text-[#00d4ff]">{model.ticker}</span>
          )}
        </h1>
        <FollowToggle company={model.company} followed={model.followed} />
      </div>
      {model.category && <p className="mt-2 text-[12px] text-zinc-600">{model.category}</p>}

      {/* ── model → what matters → developments (model + feed share selection state) ── */}
      <SecurityWorkspace
        securityKey={model.key}
        company={model.company}
        isAdmin={!!session?.user?.isAdmin}
        numbers={model.numbers}
        locked={!!model.model_locked}
        feed={model.feed}
        questions={model.questions.map((q) => ({ id: q.id, question: q.question }))}
        whatMatters={
        <section className="mt-14">
          <SectionLabel count={model.questions.length}>What Matters</SectionLabel>
          <p className="mt-3 max-w-2xl text-[13px] leading-relaxed text-zinc-500">
            The 4–5 questions that decide this investment. New podcasts, X posts, filings and
            your own research are weighed against them every day.
          </p>
          <div className="mt-6 max-w-3xl">
            <WhatMattersPanel model={model} isAdmin={!!session?.user?.isAdmin} />
          </div>
        </section>
        }
      />
    </div>
  );
}
