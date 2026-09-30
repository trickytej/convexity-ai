import Link from "next/link";
import { getBrief, getEpisodes, getScoutAppearances, getShows } from "@/lib/api";

export const dynamic = "force-dynamic";

type Stat = { value: string; label: string } | null;

async function safeStats(): Promise<{
  episodes: Stat;
  newsletters: Stat;
  scout: Stat;
  brief: Stat;
}> {
  const since = new Date(Date.now() - 7 * 86400_000).toISOString().slice(0, 10);
  const [episodes, newsletters, scout, brief] = await Promise.all([
    getEpisodes({ since, limit: 1, all: true })
      .then((r): Stat => ({ value: String(r.total), label: "this week" }))
      .catch((): Stat => null),
    getShows({ format: "newsletter" })
      .then((r): Stat => ({ value: String(r.length), label: "sources" }))
      .catch((): Stat => null),
    getScoutAppearances({ days: 7 })
      .then((r): Stat => ({ value: String(r.length), label: "appearances, 7d" }))
      .catch((): Stat => null),
    getBrief({ days: 1 })
      .then((r): Stat => {
        const hits = r.companies.reduce((s, c) => s + c.hit_count, 0);
        return { value: String(hits), label: "developments, 24h" };
      })
      .catch((): Stat => null),
  ]);
  return { episodes, newsletters, scout, brief };
}

function NavCard({
  href,
  title,
  description,
  stat,
}: {
  href: string;
  title: string;
  description: string;
  stat: Stat;
}) {
  return (
    <Link
      href={href}
      className="group flex flex-col rounded-2xl border border-white/[0.08] bg-[#0b0c10]/75 p-6 transition hover:border-[#00d4ff]/35 hover:bg-[#0e1016]/85"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-xl font-light tracking-tight text-zinc-50 transition [font-family:var(--font-display)] group-hover:text-[#00d4ff]">
          {title}
        </h2>
        {stat && (
          <span className="shrink-0 text-right">
            <span className="font-[family-name:var(--font-mono)] text-lg tabular-nums text-[#00d4ff]">
              {stat.value}
            </span>
            <span className="ml-1.5 text-[11px] text-zinc-600">{stat.label}</span>
          </span>
        )}
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-zinc-500">{description}</p>
      <span className="mt-4 text-[12px] font-medium text-zinc-600 transition group-hover:text-[#00d4ff]">
        Open →
      </span>
    </Link>
  );
}

export default async function HomePage() {
  const stats = await safeStats();

  return (
    <div>
      {/* masthead */}
      <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]" />
        <span className="text-[#00d4ff]">ConvexityAI</span>
      </p>

      <h1 className="mt-5 max-w-3xl text-5xl font-light leading-[1.04] tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-6xl">
        Uncover narratives. Sharpen theses.
        <br />
        <span className="text-[#00d4ff]">Real time.</span>
      </h1>

      <p className="mt-4 max-w-2xl text-xl font-light text-zinc-300">
        A position-aware <span className="text-[#00d4ff]">system of research</span> for
        professional managers.
      </p>

      {/* destinations */}
      <div className="mt-14 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <NavCard
          href="/brief"
          title="Brief"
          description="What moved your thesis questions since yesterday — every new insight weighed against the 4–5 things that matter per stock."
          stat={stats.brief}
        />
        <NavCard
          href="/episodes"
          title="Episodes"
          description="The week's podcast episodes — transcribe, review nuggets, and curate what surfaces downstream."
          stat={stats.episodes}
        />
        <NavCard
          href="/scout"
          title="Scout"
          description="Watchlist executives tracked across podcasts and X — every appearance and post, distilled into insights."
          stat={stats.scout}
        />
        <NavCard
          href="/newsletters"
          title="Newsletters"
          description="Investment newsletters ingested alongside the podcast flow, mined with the same insight extraction."
          stat={stats.newsletters}
        />
      </div>
    </div>
  );
}
