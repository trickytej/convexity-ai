import { NextResponse } from "next/server";
import { auth } from "@/auth";

// Session gate (Next 16 "proxy" convention, formerly middleware). Public pages
// render for everyone; everything else requires a signed-in user. For signed-in
// requests the user's id is injected as X-User-Id, which lib/api.ts and the
// /api catch-all forward to the backend. Any client-supplied X-User-Id is
// stripped first so the browser can never choose its identity.

export const config = {
  // Gate everything except Next's static assets.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|robots.txt).*)"],
};

const PUBLIC_PATHS = ["/", "/about", "/signin", "/privacy", "/terms"];

// Curator-only pages. Podcasts, newsletters, Scout and episode pages are
// browsable by everyone, with their editing controls admin-gated in-page.
const ADMIN_PREFIXES = ["/newsletter", "/library", "/report", "/preview"];

const startsWithSegment = (path: string, prefix: string) =>
  path === prefix || path.startsWith(`${prefix}/`);

export const proxy = auth((req) => {
  const { pathname, search } = req.nextUrl;
  const headers = new Headers(req.headers);
  headers.delete("x-user-id");

  if (pathname.startsWith("/api/auth/")) return NextResponse.next({ request: { headers } });

  const user = req.auth?.user;
  if (!user?.id) {
    if (PUBLIC_PATHS.includes(pathname)) return NextResponse.next({ request: { headers } });
    if (pathname.startsWith("/api/")) {
      return NextResponse.json({ detail: "sign in required" }, { status: 401 });
    }
    const url = new URL("/signin", req.nextUrl.origin);
    url.searchParams.set("callbackUrl", `${pathname}${search}`);
    return NextResponse.redirect(url);
  }

  if (!user.isAdmin && ADMIN_PREFIXES.some((p) => startsWithSegment(pathname, p))) {
    return NextResponse.redirect(new URL("/model", req.nextUrl.origin));
  }

  headers.set("x-user-id", user.id);
  return NextResponse.next({ request: { headers } });
});
