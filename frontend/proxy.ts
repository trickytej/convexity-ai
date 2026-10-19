import { NextResponse } from "next/server";
import { auth } from "@/auth";

// Session gate (Next 16 "proxy" convention, formerly middleware). For signed-in
// requests the user's id is injected as X-User-Id, which lib/api.ts and the
// /api catch-all forward to the backend. Signed-out visitors browse a read-only
// demo: they get X-Guest: 1 instead (the backend shows them the house account
// and refuses anything but reads). Client-supplied X-User-Id / X-Guest are
// stripped first so the browser can never choose its identity.

export const config = {
  // Gate everything except Next's static assets.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|robots.txt).*)"],
};

const PUBLIC_PATHS = ["/", "/about", "/pro", "/signin", "/privacy", "/terms"];

// Curator-only pages. Podcasts, newsletters, Scout and episode pages are
// browsable by everyone, with their editing controls admin-gated in-page.
const ADMIN_PREFIXES = ["/newsletter", "/library", "/report", "/preview"];

const startsWithSegment = (path: string, prefix: string) =>
  path === prefix || path.startsWith(`${prefix}/`);

export const proxy = auth((req) => {
  const { pathname, search } = req.nextUrl;
  const headers = new Headers(req.headers);
  headers.delete("x-user-id");
  headers.delete("x-guest");

  if (pathname.startsWith("/api/auth/")) return NextResponse.next({ request: { headers } });

  const user = req.auth?.user;
  if (!user?.id) {
    if (PUBLIC_PATHS.includes(pathname)) return NextResponse.next({ request: { headers } });
    if (pathname.startsWith("/api/")) {
      if (req.method !== "GET" && req.method !== "HEAD") {
        return NextResponse.json({ detail: "sign in required", guest: true }, { status: 401 });
      }
    } else if (ADMIN_PREFIXES.some((p) => startsWithSegment(pathname, p))) {
      const url = new URL("/signin", req.nextUrl.origin);
      url.searchParams.set("callbackUrl", `${pathname}${search}`);
      return NextResponse.redirect(url);
    }
    headers.set("x-guest", "1");
    return NextResponse.next({ request: { headers } });
  }

  if (!user.isAdmin && ADMIN_PREFIXES.some((p) => startsWithSegment(pathname, p))) {
    return NextResponse.redirect(new URL("/model", req.nextUrl.origin));
  }

  headers.set("x-user-id", user.id);
  return NextResponse.next({ request: { headers } });
});
