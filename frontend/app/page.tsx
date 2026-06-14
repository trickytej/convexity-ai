import Link from "next/link";
import { getShows } from "@/lib/api";
import { TierBadge } from "@/components/ui";
import ImportPodcast from "@/components/ImportPodcast";
import ImportEpisode from "@/components/ImportEpisode";

export const dynamic = "force-dynamic";

export default async function Home() {
  const shows = await getShows();
  const active = shows.filter((s) => s.active);
  const totalTranscribed = active.reduce((n, s) => n + s.transcribed, 0);

  return (
    <div className="space-y-8">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">Podcasts</h1>
        <p className="text-zinc-500">
          {active.length} shows · {totalTranscribed} episodes transcribed
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {active.map((s) => (
          <Link
            key={s.slug}
            href={`/episodes?show=${s.slug}`}
            className="group flex flex-col rounded-xl border border-zinc-200 bg-white p-5 transition-all hover:border-indigo-300 hover:shadow-md"
          >
            {/* Top: name + tier */}
            <div className="flex items-start justify-between gap-3">
              <h2 className="text-base font-semibold leading-snug tracking-tight group-hover:text-indigo-700 transition-colors">
                {s.name}
              </h2>
              <TierBadge tier={s.tier} />
            </div>

            {/* Hosts */}
            {s.hosts.length > 0 && (
              <p className="mt-1.5 text-sm text-zinc-500 leading-snug">
                {s.hosts.join(" · ")}
              </p>
            )}

            {/* Spacer */}
            <div className="flex-1" />

            {/* Stats */}
            <div className="mt-4 flex items-center gap-1.5 text-sm">
              <span className="font-semibold text-zinc-900">{s.transcribed}</span>
              <span className="text-zinc-400">transcribed</span>
              <span className="mx-1 text-zinc-300">·</span>
              <span className="text-zinc-400">{s.total} known</span>
            </div>
          </Link>
        ))}
      </div>

      <ImportPodcast />
      <ImportEpisode />
    </div>
  );
}
