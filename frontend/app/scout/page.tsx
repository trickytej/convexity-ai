import { auth } from "@/auth";
import ScoutView from "@/components/ScoutView";

// Scout watches the shared corpus, so everyone can browse it; only admins can
// change the watchlist, run scans, or curate. Non-admins get the same view with
// every editing control (marked `data-edit`) hidden — the API enforces it too.
export default async function ScoutPage() {
  const isAdmin = !!(await auth())?.user?.isAdmin;
  if (isAdmin) return <ScoutView />;
  return (
    <div className="[&_[data-edit]]:hidden">
      <p className="relative z-[5] mb-6 rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-[12px] text-zinc-500">
        Scout is part of the shared research corpus — browse appearances and posts here; the watchlist is managed by
        ConvexityAI.
      </p>
      <ScoutView />
    </div>
  );
}
