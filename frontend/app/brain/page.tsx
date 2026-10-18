import { redirect } from "next/navigation";

// Moved: /cio. Query strings (show, from, to) carry over.
export default async function Moved({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  const q = new URLSearchParams(await searchParams).toString();
  redirect(q ? `/cio?${q}` : "/cio");
}
