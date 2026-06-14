import Link from "next/link";
import { getShows } from "@/lib/api";
import ImportPodcast from "@/components/ImportPodcast";
import ImportEpisode from "@/components/ImportEpisode";
import DeleteShowButton from "@/components/DeleteShowButton";

export const dynamic = "force-dynamic";

export default async function Home() {
  const shows = await getShows();
  const active = shows.filter((s) => s.active);
  const totalTranscribed = active.reduce((n, s) => n + s.transcribed, 0);

  return (
    <div className="space-y-8">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Podcasts</h1>
        <p className="text-zinc-500">
          {active.length} shows · {totalTranscribed} episodes transcribed
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {active.map((s) => (
          <div
            key={s.slug}
            className="group flex flex-col rounded-xl border border-zinc-200 bg-white pl-5 pr-5 pt-5 pb-4 transition-all hover:border-zinc-300 hover:shadow-sm"
            style={{ borderLeft: "4px solid rgb(45, 45, 90)" }}
          >
            <Link href={`/episodes?show=${s.slug}`} className="flex-1">
              <h2 className="text-base font-semibold leading-snug tracking-tight text-zinc-900 transition-colors group-hover:text-indigo-700">
                {s.name}
              </h2>
            </Link>

            <div className="mt-3 flex items-center justify-between">
              <div className="flex items-center gap-1 text-sm text-zinc-400">
                <span className="font-medium text-zinc-600">{s.transcribed}</span>
                <span>transcribed</span>
              </div>
              <DeleteShowButton slug={s.slug} />
            </div>
          </div>
        ))}
      </div>

      <ImportPodcast />
      <ImportEpisode />
    </div>
  );
}
