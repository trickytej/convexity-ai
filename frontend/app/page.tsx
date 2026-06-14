import { getShows } from "@/lib/api";
import ShowGrid from "@/components/ShowGrid";
import ImportPodcast from "@/components/ImportPodcast";
import ImportEpisode from "@/components/ImportEpisode";

export const dynamic = "force-dynamic";

export default async function Home() {
  const shows = await getShows();
  const active = shows.filter((s) => s.active);

  return (
    <div className="space-y-8">
      <ShowGrid initialShows={active} />
      <ImportPodcast />
      <ImportEpisode />
    </div>
  );
}
