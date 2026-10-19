"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOutAction } from "@/app/actions";

type NavItem = { href: string; label: string; match: (p: string) => boolean };

const USER_NAV: NavItem[] = [
  { href: "/", label: "Home", match: (p) => p === "/" },
  { href: "/cio", label: "CIO", match: (p) => p.startsWith("/cio") },
  { href: "/model", label: "Model", match: (p) => p.startsWith("/model") },
  { href: "/research", label: "Research", match: (p) => p.startsWith("/research") || p.startsWith("/episode/") },
  { href: "/scout", label: "Scout", match: (p) => p.startsWith("/scout") },
  { href: "/developers", label: "API", match: (p) => p.startsWith("/developers") },
  { href: "/brief", label: "Brief", match: (p) => p.startsWith("/brief") },
];

const PRO: NavItem = { href: "/pro", label: "Pro", match: (p) => p.startsWith("/pro") };
const ABOUT: NavItem = { href: "/about", label: "About", match: (p) => p.startsWith("/about") };

export type HeaderUser = { name?: string | null; email?: string | null; image?: string | null; isAdmin: boolean };

export default function SiteHeader({ user }: { user: HeaderUser | null }) {
  const pathname = usePathname() ?? "/";
  const nav = [...USER_NAV, PRO, ABOUT];
  const initial = (user?.name || user?.email || "?").trim().charAt(0).toUpperCase();

  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#0a0a0c]/85 backdrop-blur print:hidden">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-6 px-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-[15px] font-medium tracking-tight text-zinc-100 [font-family:var(--font-display)]"
        >
          <span className="inline-block h-3 w-3 rounded-sm bg-[#00d4ff]" />
          ConvexityAI
        </Link>
        <div className="flex items-center gap-6 sm:gap-7">
          <nav className="flex gap-6 text-sm sm:gap-7">
            {nav.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={n.match(pathname) ? "text-[#00d4ff]" : "text-zinc-400 transition hover:text-zinc-100"}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          {user ? (
            <details className="relative">
              <summary
                title={user.email ?? undefined}
                className="flex h-7 w-7 cursor-pointer list-none items-center justify-center overflow-hidden rounded-full border border-white/[0.12] bg-white/[0.04] text-[12px] font-medium text-zinc-300 [&::-webkit-details-marker]:hidden"
              >
                {user.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={user.image} alt="" className="h-full w-full object-cover" />
                ) : (
                  initial
                )}
              </summary>
              <div className="absolute right-0 mt-2 w-56 rounded-xl border border-white/[0.08] bg-[#0b0c10] p-3 shadow-xl">
                <p className="truncate text-[13px] text-zinc-200">{user.name || user.email}</p>
                {user.name && <p className="truncate text-[11px] text-zinc-600">{user.email}</p>}
                {user.isAdmin && (
                  <p className="mt-1 text-[10px] font-medium uppercase tracking-[0.18em] text-[#00d4ff]/70">Admin</p>
                )}
                <form action={signOutAction} className="mt-3 border-t border-white/[0.06] pt-2">
                  <button type="submit" className="text-[12px] text-zinc-400 transition hover:text-rose-300">
                    Sign out
                  </button>
                </form>
              </div>
            </details>
          ) : (
            <Link
              href="/signin"
              className="rounded-full border border-white/[0.12] px-3.5 py-1 text-[13px] text-zinc-300 transition hover:border-[#00d4ff]/40 hover:text-[#00d4ff]"
            >
              Sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
