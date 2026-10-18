"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/research/podcasts", label: "Podcasts", match: (p: string) => p.startsWith("/research/podcasts") },
  { href: "/research/newsletters", label: "Newsletters", match: (p: string) => p.startsWith("/research/newsletters") },
  { href: "/research", label: "Your research", match: (p: string) => p === "/research" },
];

/** Sub-navigation for the Research hub: own research, then the shared corpus. */
export default function ResearchTabs() {
  const pathname = usePathname() ?? "/research";
  return (
    <nav className="mb-10 flex flex-wrap gap-3 border-b border-white/[0.06] pb-4">
      {TABS.map((t) => (
        <Link
          key={t.href}
          href={t.href}
          className={`rounded-full border px-5 py-2.5 text-[15px] font-medium text-white transition ${
            t.match(pathname)
              ? "border-[#00d4ff] bg-[#00d4ff]/30 shadow-[0_0_18px_rgba(0,212,255,0.35)]"
              : "border-[#00d4ff]/50 bg-[#00d4ff]/10 hover:border-[#00d4ff] hover:bg-[#00d4ff]/20"
          }`}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
