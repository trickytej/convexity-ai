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
      <Link href="/episodes" className="text-sm text-[#1ec997] transition hover:text-[#34d6a8]">
        ← All episodes
      </Link>

      <header className="space-y-3">
        <h1 className="text-3xl font-light leading-tight tracking-tight text-zinc-50 [font-family:var(--font-display)]">
          {e.title}
        </h1>
        <p className="text-zinc-400">
          <span className="font-[family-name:var(--font-mono)] text-zinc-300">{e.show_slug}</span> ·{" "}
          {fmtDate(e.published_at)} · {fmtDuration(e.duration_seconds)}
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
              className="text-sm text-[#1ec997] transition hover:text-[#34d6a8]"
            >
              source ↗
            </a>
          )}
          {e.audio_url && (
            <a
              href={e.audio_url}
              target="_blank"
              rel="noreferrer"
              className="text-sm text-[#1ec997] transition hover:text-[#34d6a8]"
            >
              audio ↗
            </a>
          )}
        </div>
      </header>

      <div className="rounded-2xl border border-white/[0.08] bg-[#0b0c10]/70 p-5 backdrop-blur-md sm:p-7">
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
