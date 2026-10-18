import { redirect } from "next/navigation";

// Moved: /research/podcasts. Query strings (show, from, to) carry over.
export default async function Moved({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  const q = new URLSearchParams(await searchParams).toString();
  redirect(q ? `/research/podcasts?${q}` : "/research/podcasts");
}
