import Link from "next/link";
import { getBrief, getEpisodes, getScoutAppearances, getShows, getTheses } from "@/lib/api";

export const dynamic = "force-dynamic";

type Stat = { value: string; label: string } | null;

async function safeStats(): Promise<{
  episodes: Stat;
  podcasts: Stat;
  newsletters: Stat;
  scout: Stat;
  brief: Stat;
  model: Stat;
}> {
  const since = new Date(Date.now() - 7 * 86400_000).toISOString().slice(0, 10);
  const [episodes, shows, scout, brief, theses] = await Promise.all([
    getEpisodes({ since, limit: 1, all: true }).catch(() => null),
    getShows().catch(() => null),
    getScoutAppearances({ days: 7 }).catch(() => null),
    getBrief({ days: 1 }).catch(() => null),
    getTheses().catch(() => null),
  ]);
  const podcastShows = shows?.filter((s) => s.format !== "newsletter") ?? null;
  const newsletterShows = shows?.filter((s) => s.format === "newsletter") ?? null;
  return {
    episodes: episodes ? { value: String(episodes.total), label: "this week" } : null,
    podcasts: podcastShows ? { value: String(podcastShows.length), label: "shows" } : null,
    newsletters: newsletterShows ? { value: String(newsletterShows.length), label: "sources" } : null,
    scout: scout ? { value: String(scout.length), label: "appearances, 7d" } : null,
    brief: brief
      ? {
          value: String(brief.companies.reduce((s, c) => s + c.hit_count, 0)),
          label: "developments, 24h",
        }
      : null,
    model: theses ? { value: String(theses.companies.length), label: "with theses" } : null,
  };
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
      className="group flex flex-col rounded-2xl border border-[#00d4ff]/[0.18] bg-[#0d1a2e]/85 p-6 transition hover:border-[#00d4ff]/45 hover:bg-[#102038]/90"
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
            <span className="ml-1.5 text-[11px] text-zinc-400">{stat.label}</span>
          </span>
        )}
      </div>
      <p className="mt-2 flex-1 text-[13px] leading-relaxed text-zinc-200">{description}</p>
      <span className="mt-4 text-[12px] font-medium text-zinc-400 transition group-hover:text-[#00d4ff]">
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

      <p className="mt-3 text-[15px] font-light leading-relaxed text-zinc-500 sm:whitespace-nowrap">
        Convexity parses through the deluge of news flow and flags the information
        that influences <span className="text-[#00d4ff]/80">the theses you&apos;re watching</span>.
      </p>

      {/* destinations */}
      <p className="mt-14 flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
        <span className="inline-block h-px w-8 bg-[#00d4ff]/50" />
        <span className="text-zinc-500">Workspace</span>
      </p>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <NavCard
          href="/brief"
          title="Brief"
          description="Summary of new research that impacts your theses."
          stat={stats.brief}
        />
        <NavCard
          href="/hub"
          title="Model"
          description="Per-security view on how news influences your forecast."
          stat={stats.model}
        />
        <NavCard
          href="/episodes"
          title="Episodes"
          description="Curate and review nuggets from the episodes you track."
          stat={stats.episodes}
        />
        <NavCard
          href="/scout"
          title="Scout"
          description="A watchlist of companies and executives, distilled into insights."
          stat={stats.scout}
        />
        <NavCard
          href="/podcasts"
          title="Podcasts"
          description="Manage tracked feeds, import new podcasts, browse by show."
          stat={stats.podcasts}
        />
        <NavCard
          href="/newsletters"
          title="Newsletters"
          description="Varied sources of news, ingested alongside your positions."
          stat={stats.newsletters}
        />
      </div>

      {/* quiet secondary links */}
      <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-white/[0.06] pt-6 text-[13px]">
        <span className="text-[11px] font-medium uppercase tracking-[0.2em] text-zinc-700">
          More
        </span>
        {[
          { href: "/securities", label: "Securities" },
          { href: "/newsletter", label: "Weekly Report" },
          { href: "/theses", label: "Edit Theses" },
          { href: "/library", label: "Episode Library" },
        ].map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="text-zinc-500 transition hover:text-[#00d4ff]"
          >
            {l.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
