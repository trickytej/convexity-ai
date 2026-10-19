"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const QUIET = ["/signin", "/about", "/pro", "/privacy", "/terms"];

/** Signed-out visitors browse a read-only demo (the house account). This shows a
 * slim banner saying so, and a sign-in prompt whenever they try to change
 * something (lib/api.ts fires `convexity:signin-required` on a 401). */
export default function GuestPrompt() {
  const pathname = usePathname() ?? "/";
  const [open, setOpen] = useState(false);
  const callbackUrl = encodeURIComponent(pathname);

  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener("convexity:signin-required", show);
    return () => window.removeEventListener("convexity:signin-required", show);
  }, []);

  const banner = pathname !== "/" && !QUIET.some((p) => pathname.startsWith(p));

  return (
    <>
      {banner && (
        <div className="relative z-20 border-b border-[#00d4ff]/20 bg-[#00d4ff]/[0.06] print:hidden">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-2.5 text-[13px]">
            <p className="text-zinc-300">
              You&apos;re viewing a live demo of ConvexityAI&apos;s house book.{" "}
              <span className="text-zinc-500">Sign in free to follow your own names and write your own questions.</span>
            </p>
            <Link
              href={`/signin?callbackUrl=${callbackUrl}`}
              className="rounded-full bg-[#00d4ff] px-3.5 py-1 text-[12px] font-medium text-[#001a26] transition hover:bg-[#33ddff]"
            >
              Sign in free
            </Link>
          </div>
        </div>
      )}

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-[#00d4ff]/30 bg-[#0b0c10] p-7 text-center shadow-[0_0_40px_rgba(0,212,255,0.15)]"
            onClick={(e) => e.stopPropagation()}
          >
            <p className="text-xl font-light text-zinc-50 [font-family:var(--font-display)]">Make this yours</p>
            <p className="mt-2 text-[14px] leading-relaxed text-zinc-400">
              This is a read-only demo. Sign in free to follow securities, write your own What Matters questions,
              keep or drop evidence, and bring your own research.
            </p>
            <div className="mt-6 flex justify-center gap-3">
              <Link
                href={`/signin?callbackUrl=${callbackUrl}`}
                className="rounded-full bg-[#00d4ff] px-5 py-2 text-[13px] font-medium text-[#001a26] transition hover:bg-[#33ddff]"
              >
                Sign in free
              </Link>
              <button
                onClick={() => setOpen(false)}
                className="rounded-full border border-white/[0.12] px-5 py-2 text-[13px] text-zinc-300 transition hover:border-white/25"
              >
                Keep browsing
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
