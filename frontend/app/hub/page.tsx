import { redirect } from "next/navigation";

// The Model tab moved to /model (security list) and /model/[key] (one security).
export default async function HubPage({
  searchParams,
}: {
  searchParams: Promise<{ ticker?: string }>;
}) {
  const { ticker } = await searchParams;
  redirect(ticker ? `/model/${encodeURIComponent(ticker)}` : "/model");
}
