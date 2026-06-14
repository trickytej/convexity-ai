import Link from "next/link";
import { getEpisodes, getShows } from "@/lib/api";
import { fmtDate, fmtDuration } from "@/lib/format";
import { Badge, SourceBadge } from "@/components/ui";
import TranscribeButton from "@/components/TranscribeButton";

export const dynamic = "force-dynamic";

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  transcribed: { label: "Transcribed", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  acquired:    { label: "Downloaded",  cls: "bg-blue-50 text-blue-700 ring-blue-200" },
  discovered:  { label: "Discovered",  cls: "bg-zinc-100 text-zinc-500 ring-zinc-200" },
  failed:      { label: "Failed",      cls: "bg-rose-50 text-rose-600 ring-rose-200" },
};

export default async function EpisodesPage({
  searchParams,
}: {
  searchParams: Promise<{ show?: string }>;
}) {
  const { show } = await searchParams;
  // When a specific show is selected, show ALL discovered episodes (not just transcribed)
  const [shows, list] = await Promise.all([
    getShows(),
    getEpisodes({ show, limit: 200, all: !!show }),
  ]);
  const withTranscripts = shows.filter((s) => s.transcribed > 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Insights</h1>
        <p className="mt-1 text-zinc-500">
          {show ? `${list.total} episodes` : `${list.total} transcribed episodes`}
        </p>
      </div>

      {/* Show filter pills */}
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
            {s.name}
            <span className={`ml-1.5 ${show === s.slug ? "opacity-70" : "opacity-50"}`}>
              {s.transcribed}
            </span>
          </Link>
        ))}
      </div>

      {/* Episode list */}
      <div className="divide-y divide-zinc-200 overflow-hidden rounded-xl border border-zinc-200 bg-white">
        {list.episodes.length === 0 && (
          <p className="px-4 py-8 text-center text-zinc-500">
            {show
              ? "No episodes discovered yet. Use the Refresh button on the Podcasts page."
              : "No transcribed episodes yet."}
          </p>
        )}
        {list.episodes.map((e) => {
          const isTranscribed = e.status === "transcribed" || (!e.status && !!e.source);
          const statusInfo = STATUS_BADGE[e.status ?? (e.source ? "transcribed" : "discovered")];

          return (
            <div key={e.id} className="flex items-center justify-between gap-4 px-4 py-3">
              <div className="min-w-0 flex-1">
                {isTranscribed ? (
                  <Link href={`/episode/${e.id}`} className="hover:text-indigo-700 transition-colors">
                    <p className="truncate font-medium">{e.title}</p>
                  </Link>
                ) : (
                  <p className="truncate font-medium text-zinc-500">{e.title}</p>
                )}
                <p className="mt-0.5 text-sm text-zinc-500">
                  {e.show_slug} · {fmtDate(e.published_at)} · {fmtDuration(e.duration_seconds)}
                  {e.guests && e.guests.length > 0 ? ` · ${e.guests.join(", ")}` : ""}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {isTranscribed && e.nugget_count > 0 && (
                  <Badge tone="indigo">{e.nugget_count} nuggets</Badge>
                )}
                {isTranscribed && <SourceBadge source={e.source} />}
                {!isTranscribed && statusInfo && (
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${statusInfo.cls}`}>
                    {statusInfo.label}
                  </span>
                )}
                {!isTranscribed && (
                  <TranscribeButton episodeId={e.id} initialStatus={e.status} />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
