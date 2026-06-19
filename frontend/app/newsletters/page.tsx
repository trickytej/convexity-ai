import Link from "next/link";
import { getShows, getEpisodes } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import ImportNewsletter from "@/components/ImportNewsletter";

export const dynamic = "force-dynamic";

export default async function NewslettersPage({
  searchParams,
}: {
  searchParams: Promise<{ show?: string }>;
}) {
  const { show } = await searchParams;

  const [newsletters, list] = await Promise.all([
    getShows({ format: "newsletter" }),
    show
      ? getEpisodes({ show, limit: 100, all: true })
      : Promise.resolve({ total: 0, limit: 100, offset: 0, episodes: [] }),
  ]);

  return (
    <div className="space-y-12">
      {/* ── masthead ── */}
      <div>
        <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
          <span className="inline-block h-px w-8 bg-[#00d4ff]" />
          <span className="text-[#00d4ff]">Sources</span>
        </p>
        <h1 className="mt-4 text-4xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)] sm:text-5xl">
          Newsletters
        </h1>
        <p className="mt-3 text-[15px] text-zinc-400">
          Import newsletters by RSS feed — the same nugget pipeline runs on articles as on
          podcasts.
        </p>
      </div>

      {/* ── import box ── */}
      <ImportNewsletter />

      {/* ── newsletter library grid ── */}
      {newsletters.length > 0 && (
        <div>
          <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
            <span className="inline-block h-px w-8 bg-[#00d4ff]" />
            <span className="text-[#00d4ff]">Library</span>
          </p>
          <h2 className="mt-4 text-2xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
            {newsletters.length} newsletter{newsletters.length !== 1 ? "s" : ""}
          </h2>

          <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {newsletters.map((nl) => (
              <Link
                key={nl.slug}
                href={`/newsletters?show=${nl.slug}`}
                className={`group rounded-xl border px-5 py-4 transition ${
                  show === nl.slug
                    ? "border-[#00d4ff]/30 bg-[#00d4ff]/5"
                    : "border-white/[0.08] bg-[#0b0c10]/60 hover:border-white/[0.14]"
                }`}
              >
                <p className="font-medium text-zinc-100 group-hover:text-[#00d4ff] transition-colors">
                  {nl.name}
                </p>
                <p className="mt-1 text-sm text-zinc-500">
                  {nl.transcribed} article{nl.transcribed !== 1 ? "s" : ""} processed
                  {nl.total > nl.transcribed ? ` · ${nl.total - nl.transcribed} pending` : ""}
                </p>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* ── articles for selected newsletter ── */}
      {show && (
        <div>
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="flex items-center gap-3 text-[11px] font-medium uppercase tracking-[0.24em]">
                <span className="inline-block h-px w-8 bg-[#00d4ff]" />
                <span className="text-[#00d4ff]">Articles</span>
              </p>
              <h2 className="mt-4 text-2xl font-light tracking-tight text-zinc-50 [font-family:var(--font-display)]">
                {list.total} article{list.total !== 1 ? "s" : ""}
              </h2>
            </div>
            <Link
              href="/newsletters"
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              ← All newsletters
            </Link>
          </div>

          <div className="mt-6 divide-y divide-white/[0.06] overflow-hidden rounded-xl border border-white/[0.08] bg-[#0b0c10]/60">
            {list.episodes.length === 0 && (
              <p className="px-4 py-10 text-center text-zinc-500">
                No articles yet — click an episode to process it, or refresh the feed.
              </p>
            )}
            {list.episodes.map((ep) => {
              const isTranscribed = ep.status === "transcribed" || (!ep.status && !!ep.source);
              return (
                <div
                  key={ep.id}
                  className="flex items-center justify-between gap-4 px-4 py-3.5 transition hover:bg-white/[0.02]"
                >
                  <div className="min-w-0 flex-1">
                    {isTranscribed ? (
                      <Link
                        href={`/episode/${ep.id}`}
                        className="transition-colors hover:text-[#00d4ff]"
                      >
                        <p className="truncate font-medium text-zinc-100">{ep.title}</p>
                      </Link>
                    ) : (
                      <p className="truncate font-medium text-zinc-500">{ep.title}</p>
                    )}
                    <p className="mt-0.5 text-sm text-zinc-500">
                      {fmtDate(ep.published_at)}&nbsp;
                      {ep.word_count ? `· ${ep.word_count.toLocaleString()} words` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {isTranscribed && ep.nugget_count > 0 && (
                      <span className="rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs font-medium text-indigo-300 ring-1 ring-inset ring-indigo-500/25">
                        {ep.nugget_count} nuggets
                      </span>
                    )}
                    {ep.status && !isTranscribed && (
                      <span className="rounded-full bg-white/[0.05] px-2.5 py-0.5 text-xs font-medium text-zinc-400 ring-1 ring-inset ring-white/10">
                        {ep.status}
                      </span>
                    )}
                    {ep.episode_url && (
                      <a
                        href={ep.episode_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-zinc-600 hover:text-[#00d4ff] transition-colors"
                      >
                        ↗
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* empty state */}
      {newsletters.length === 0 && (
        <div className="rounded-xl border border-dashed border-white/[0.12] bg-[#0b0c10]/50 px-8 py-16 text-center">
          <p className="text-xl font-light text-zinc-400 [font-family:var(--font-display)]">
            No newsletters yet
          </p>
          <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-zinc-600">
            Add a newsletter RSS feed above. Substack, Beehiiv, and any standard RSS feed
            are supported.
          </p>
        </div>
      )}
    </div>
  );
}
