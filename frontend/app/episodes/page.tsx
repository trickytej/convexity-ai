import Link from "next/link";
import { getEpisodes, getShows } from "@/lib/api";
import { fmtDate, fmtDuration } from "@/lib/format";
import { Badge, SourceBadge } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function EpisodesPage({
  searchParams,
}: {
  searchParams: Promise<{ show?: string }>;
}) {
  const { show } = await searchParams;
  const [shows, list] = await Promise.all([
    getShows(),
    getEpisodes({ show, limit: 200 }),
  ]);
  const withTranscripts = shows.filter((s) => s.transcribed > 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Episodes</h1>
        <p className="mt-1 text-zinc-600">{list.total} transcribed episodes</p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Link
          href="/episodes"
          className={`rounded-full px-3 py-1 text-sm ring-1 ring-inset transition ${
            !show
              ? "bg-indigo-600 text-white ring-indigo-600"
              : "bg-white text-zinc-700 ring-zinc-200 hover:bg-zinc-50"
          }`}
        >
          All
        </Link>
        {withTranscripts.map((s) => (
          <Link
            key={s.slug}
            href={`/episodes?show=${s.slug}`}
            className={`rounded-full px-3 py-1 text-sm ring-1 ring-inset transition ${
              show === s.slug
                ? "bg-indigo-600 text-white ring-indigo-600"
                : "bg-white text-zinc-700 ring-zinc-200 hover:bg-zinc-50"
            }`}
          >
            {s.slug} <span className="opacity-60">{s.transcribed}</span>
          </Link>
        ))}
      </div>

      <div className="divide-y divide-zinc-200 overflow-hidden rounded-xl border border-zinc-200 bg-white">
        {list.episodes.length === 0 && (
          <p className="px-4 py-8 text-center text-zinc-500">No transcribed episodes yet.</p>
        )}
        {list.episodes.map((e) => (
          <Link
            key={e.id}
            href={`/episode/${e.id}`}
            className="flex items-center justify-between gap-4 px-4 py-3 transition hover:bg-zinc-50"
          >
            <div className="min-w-0">
              <p className="truncate font-medium">{e.title}</p>
              <p className="mt-0.5 text-sm text-zinc-500">
                {e.show_slug} · {fmtDate(e.published_at)} · {fmtDuration(e.duration_seconds)}
                {e.guests && e.guests.length > 0 ? ` · ${e.guests.join(", ")}` : ""}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {e.nugget_count > 0 && <Badge tone="indigo">{e.nugget_count} nuggets</Badge>}
              <SourceBadge source={e.source} />
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
