"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/insights",    label: "Home",       match: (p: string) => p === "/insights" || p === "/preview" },
  { href: "/securities",  label: "Securities", match: (p: string) => p.startsWith("/securities") },
  { href: "/hub",         label: "Hub",        match: (p: string) => p.startsWith("/hub") },
  { href: "/",            label: "Podcasts",   match: (p: string) => p === "/" || p.startsWith("/?") },
  { href: "/newsletters", label: "Newsletter", match: (p: string) => p.startsWith("/newsletters") },
  { href: "/newsletter",  label: "Report",     match: (p: string) => p === "/newsletter" },
];

export default function SiteHeader() {
  const pathname = usePathname() ?? "/";

  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#0a0a0c]/85 backdrop-blur print:hidden">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-[15px] font-medium tracking-tight text-zinc-100 [font-family:var(--font-display)]"
        >
          <span className="inline-block h-3 w-3 rounded-sm bg-[#00d4ff]" />
          ConvexityAI<span className="px-0.5 text-zinc-600">/</span>
          <span className="font-light text-zinc-400">Research</span>
        </Link>
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
