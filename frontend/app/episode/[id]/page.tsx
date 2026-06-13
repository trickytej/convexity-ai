import Link from "next/link";
import { notFound } from "next/navigation";
import type { EpisodeDigest, NuggetWithCuration, Transcript } from "@/lib/api";
import { getEpisodeDigest, getEpisodeNuggets, getTranscript } from "@/lib/api";
import { fmtDate, fmtDuration } from "@/lib/format";
import { Badge, SourceBadge } from "@/components/ui";
import { EpisodeTabs } from "@/components/EpisodeTabs";

export const dynamic = "force-dynamic";

export default async function EpisodePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  let data: Transcript | null = null;
  try {
    data = await getTranscript(id);
  } catch {
    data = null;
  }
  if (!data) notFound();

  let digest: EpisodeDigest | null = null;
  try {
    digest = await getEpisodeDigest(id);
  } catch {
    digest = null;
  }

  let nuggets: NuggetWithCuration[] = [];
  try {
    nuggets = await getEpisodeNuggets(id);
  } catch {
    nuggets = [];
  }

  const e = data.episode;

  return (
    <div className="space-y-6">
      <Link href="/episodes" className="text-sm text-indigo-600 hover:text-indigo-800">
        ← All episodes
      </Link>

      <header className="space-y-3">
        <h1 className="text-2xl font-semibold leading-tight tracking-tight">{e.title}</h1>
        <p className="text-zinc-600">
          {e.show_slug} · {fmtDate(e.published_at)} · {fmtDuration(e.duration_seconds)}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge source={data.source} />
          {data.has_diarization && <Badge tone="zinc">diarized</Badge>}
          {data.corrected && <Badge tone="amber">corrected</Badge>}
          {data.word_count ? <Badge tone="zinc">{data.word_count.toLocaleString()} words</Badge> : null}
          {e.nugget_count > 0 && <Badge tone="indigo">{e.nugget_count} nuggets</Badge>}
          {e.episode_url && (
            <a
              href={e.episode_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-indigo-600 hover:text-indigo-800"
            >
              source ↗
            </a>
          )}
          {e.audio_url && (
            <a
              href={e.audio_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-indigo-600 hover:text-indigo-800"
            >
              audio ↗
            </a>
          )}
        </div>
      </header>

      <div className="rounded-xl border border-zinc-200 bg-white p-5 sm:p-7">
        <EpisodeTabs
          episodeId={e.id}
          segments={data.segments}
          speakers={data.speakers}
          digest={digest}
          nuggets={nuggets}
        />
      </div>
    </div>
  );
}
