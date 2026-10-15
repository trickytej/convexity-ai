import { getBrain } from "@/lib/api";
import CioBrain from "@/components/CioBrain";

export const dynamic = "force-dynamic";
export const metadata = { title: "CIO Brain — ConvexityAI" };

export default async function BrainPage() {
  return <CioBrain initial={await getBrain()} />;
}
