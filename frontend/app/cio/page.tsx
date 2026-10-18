import { getBrain } from "@/lib/api";
import CioBrain from "@/components/CioBrain";

export const dynamic = "force-dynamic";
export const metadata = { title: "CIO — ConvexityAI" };

export default async function CioPage() {
  return <CioBrain initial={await getBrain()} />;
}
