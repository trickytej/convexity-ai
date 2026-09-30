import Link from "next/link";
import { getEpisodes, getShows, isEpisodeProcessed } from "@/lib/api";
import { fmtDate, fmtDuration } from "@/lib/format";
import { Badge, SourceBadge } from "@/components/ui";
import TranscribeButton from "@/components/TranscribeButton";
import PollButton from "@/components/PollButton";
import ImportedEpisodeList from "@/components/ImportedEpisodeList";

export const dynamic = "force-dynamic";

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  transcribed: { label: "Transcribed", cls: "bg-emerald-500/10 text-emerald-300 ring-emerald-500/25" },
  acquired:    { label: "Downloaded",  cls: "bg-sky-500/10 text-sky-300 ring-sky-500/25" },
  discovered:  { label: "Discovered",  cls: "bg-white/[0.05] text-zinc-400 ring-white/10" },
  failed:      { label: "Failed",      cls: "bg-rose-500/10 text-rose-300 ring-rose-500/25" },
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
    <div>
      {/* masthead */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
            <span className="inline-block h-px w-8 bg-[#00d4ff]" />
            <span className="text-[#00d4ff]">Library</span>
          </p>
          <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
            Episodes
          </h1>
          <p className="mt-3 text-[15px] text-zinc-400">
            {show ? `${list.total} episodes` : `${list.total} transcribed episodes`}
          </p>
        </div>
        {show && <PollButton slug={show} />}
      </div>

      {/* Show filter pills */}
      <div className="mt-8 flex flex-wrap gap-2">
        <Link
          href="/episodes"
          className={`rounded-full px-3.5 py-1.5 text-sm transition ${
            !show
              ? "bg-[#00d4ff] font-medium text-[#001a26]"
              : "border border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-100"
          }`}
        >
          All
        </Link>
        {withTranscripts.map((s) => (
          <Link
            key={s.slug}
            href={`/episodes?show=${s.slug}`}
            className={`rounded-full px-3.5 py-1.5 text-sm transition ${
              show === s.slug
                ? "bg-[#00d4ff] font-medium text-[#001a26]"
                : "border border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-100"
            }`}
          >
            {s.name}
            <span className={`ml-1.5 ${show === s.slug ? "opacity-60" : "opacity-50"}`}>
              {s.transcribed}
            </span>
          </Link>
        ))}
      </div>

      {/* Episode list */}
      <div className="mt-8">
        {show === "imported" ? (
          <ImportedEpisodeList initialEpisodes={list.episodes} />
        ) : (
          <div className="divide-y divide-white/[0.06] overflow-hidden rounded-xl border border-white/[0.08] bg-[#0b0c10]/60">
            {list.episodes.length === 0 && (
              <p className="px-4 py-10 text-center text-zinc-500">
                {show
                  ? "No episodes discovered yet. Use the Refresh button above to check for new episodes."
                  : "No transcribed episodes yet."}
              </p>
            )}
            {list.episodes.map((e) => {
              const isTranscribed = isEpisodeProcessed(e);
              const statusInfo = STATUS_BADGE[e.status ?? (e.source ? "transcribed" : "discovered")];

              return (
                <div key={e.id} className="flex items-center justify-between gap-4 px-4 py-3.5 transition hover:bg-white/[0.02]">
                  <div className="min-w-0 flex-1">
                    {isTranscribed ? (
                      <Link href={`/episode/${e.id}`} className="transition-colors hover:text-[#00d4ff]">
                        <p className="truncate font-medium text-zinc-100">{e.title}</p>
                      </Link>
                    ) : (
                      <p className="truncate font-medium text-zinc-500">{e.title}</p>
                    )}
                    <p className="mt-0.5 text-sm text-zinc-500">
                      <span className="font-[family-name:var(--font-mono)] text-zinc-400">{e.show_slug}</span> ·{" "}
                      {fmtDate(e.published_at)} · {fmtDuration(e.duration_seconds)}
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
        )}
      </div>
    </div>
  );
}
