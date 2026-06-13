import Link from "next/link";
import { getEpisodes, getShows } from "@/lib/api";
import { fmtDate, fmtDuration } from "@/lib/format";
import { Badge, SourceBadge, TierBadge } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function Home() {
  const [shows, recent] = await Promise.all([getShows(), getEpisodes({ limit: 8 })]);
  const active = shows.filter((s) => s.active);
  const totalTranscribed = shows.reduce((n, s) => n + s.transcribed, 0);

  return (
    <div className="space-y-12">
      <section>
        <h1 className="text-3xl font-semibold tracking-tight">Transcript library</h1>
        <p className="mt-2 max-w-2xl text-zinc-600">
          Diarized, speaker-attributed transcripts across {active.length} shows.{" "}
          <span className="font-medium text-zinc-900">{totalTranscribed}</span> episodes
          transcribed so far.
        </p>
      </section>

      <section>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500">Shows</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {active.map((s) => (
            <Link
              key={s.slug}
              href={`/episodes?show=${s.slug}`}
              className="group rounded-xl border border-zinc-200 bg-white p-4 transition hover:border-indigo-300 hover:shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-medium leading-tight group-hover:text-indigo-700">{s.name}</h3>
                <TierBadge tier={s.tier} />
              </div>
              <p className="mt-1 truncate text-sm text-zinc-500">{s.hosts.join(", ")}</p>
              <p className="mt-3 text-sm text-zinc-600">
                <span className="font-semibold text-zinc-900">{s.transcribed}</span> transcribed
                <span className="text-zinc-400"> / {s.total} known</span>
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500">
            Recent episodes
          </h2>
          <Link href="/episodes" className="text-sm text-indigo-600 hover:text-indigo-800">
            Browse all →
          </Link>
        </div>
        <div className="divide-y divide-zinc-200 overflow-hidden rounded-xl border border-zinc-200 bg-white">
          {recent.episodes.map((e) => (
            <Link
              key={e.id}
              href={`/episode/${e.id}`}
              className="flex items-center justify-between gap-4 px-4 py-3 transition hover:bg-zinc-50"
            >
              <div className="min-w-0">
                <p className="truncate font-medium">{e.title}</p>
                <p className="mt-0.5 text-sm text-zinc-500">
                  {e.show_slug} · {fmtDate(e.published_at)} · {fmtDuration(e.duration_seconds)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {e.nugget_count > 0 && <Badge tone="indigo">{e.nugget_count} nuggets</Badge>}
                <SourceBadge source={e.source} />
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
