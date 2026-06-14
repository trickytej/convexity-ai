import Link from "next/link";
import { Questrial } from "next/font/google";
import { getShows } from "@/lib/api";
import ImportPodcast from "@/components/ImportPodcast";
import ImportEpisode from "@/components/ImportEpisode";
import PollButton from "@/components/PollButton";

const questrial = Questrial({ subsets: ["latin"], weight: "400" });

export const dynamic = "force-dynamic";

export default async function Home() {
  const shows = await getShows();
  const active = shows.filter((s) => s.active);
  const totalTranscribed = active.reduce((n, s) => n + s.transcribed, 0);

  return (
    <div className={`${questrial.className} space-y-8`}>
      <header className="space-y-1">
        <h1 className="font-sans text-xl font-semibold tracking-tight">Podcasts</h1>
        <p className="text-zinc-500">
          {active.length} shows · {totalTranscribed} episodes transcribed
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {active.map((s) => (
          <div
            key={s.slug}
            className="group flex flex-col rounded-xl p-5 transition-all"
            style={{ backgroundColor: "rgb(45, 45, 90)" }}
          >
            <Link
              href={`/episodes?show=${s.slug}`}
              className="flex-1"
              style={{ color: "white" }}
            >
              <h2 className="text-lg leading-snug tracking-tight transition-opacity group-hover:opacity-80">
                {s.name}
              </h2>
            </Link>

            <div className="mt-4 flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-sm" style={{ color: "rgba(255,255,255,0.65)" }}>
                <span style={{ color: "white" }}>{s.transcribed}</span>
                <span>transcribed</span>
              </div>
              <PollButton slug={s.slug} dark />
            </div>
          </div>
        ))}
      </div>

      <ImportPodcast />
      <ImportEpisode />
    </div>
  );
}
