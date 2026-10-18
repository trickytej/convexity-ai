import { redirect } from "next/navigation";

// Moved: /developers. Query strings (show, from, to) carry over.
export default async function Moved({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  const q = new URLSearchParams(await searchParams).toString();
  redirect(q ? `/developers?${q}` : "/developers");
}
