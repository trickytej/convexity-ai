"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/research", label: "Your research", match: (p: string) => p === "/research" },
  { href: "/research/podcasts", label: "Podcasts", match: (p: string) => p.startsWith("/research/podcasts") },
  { href: "/research/newsletters", label: "Newsletters", match: (p: string) => p.startsWith("/research/newsletters") },
];

/** Sub-navigation for the Research hub: own research, then the shared corpus. */
export default function ResearchTabs() {
  const pathname = usePathname() ?? "/research";
  return (
    <nav className="mb-10 flex flex-wrap gap-2 border-b border-white/[0.06] pb-4">
      {TABS.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          className={`rounded-full border px-3.5 py-1.5 text-[13px] transition ${
            t.match(pathname)
              ? "border-[#00d4ff]/40 bg-[#00d4ff]/10 text-[#00d4ff]"
              : "border-white/[0.06] text-zinc-400 hover:border-white/[0.14] hover:text-zinc-200"
          }`}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
