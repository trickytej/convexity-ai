"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/insights",    label: "Home",        match: (p: string) => p === "/" || p === "/insights" || p === "/preview" },
  { href: "/scout",       label: "Scout",       match: (p: string) => p.startsWith("/scout") },
  { href: "/securities",  label: "Securities",  match: (p: string) => p.startsWith("/securities") },
  { href: "/podcasts",    label: "Podcasts",    match: (p: string) => p === "/podcasts" || p.startsWith("/podcasts?") },
  { href: "/newsletters", label: "Newsletters", match: (p: string) => p.startsWith("/newsletters") },
  { href: "/newsletter",  label: "Report",      match: (p: string) => p === "/newsletter" },
];

export default function SiteHeader() {
  const pathname = usePathname() ?? "/";

  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#0a0a0c]/85 backdrop-blur print:hidden">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <Link
            href="/hub"
            className={`text-[15px] font-medium tracking-tight transition [font-family:var(--font-display)] ${pathname.startsWith("/hub") ? "text-[#00d4ff]" : "text-zinc-400 hover:text-zinc-100"}`}
          >
            Hub
          </Link>
          <span className="text-zinc-700">/</span>
          <Link
            href="/insights"
            className="flex items-center gap-2 text-[15px] font-medium tracking-tight text-zinc-100 [font-family:var(--font-display)]"
          >
            <span className="inline-block h-3 w-3 rounded-sm bg-[#00d4ff]" />
            ConvexityAI<span className="px-0.5 text-zinc-600">/</span>
            <span className="font-light text-zinc-400">Research</span>
          </Link>
        </div>
        <nav className="flex gap-6 text-sm sm:gap-7">
          {NAV.map((n) => {
            const active = n.match(pathname);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={active ? "text-[#00d4ff]" : "text-zinc-400 transition hover:text-zinc-100"}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
