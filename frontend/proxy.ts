import { NextResponse, type NextRequest } from "next/server";

// HTTP Basic Auth gate (Next 16 "proxy" convention, formerly middleware). When
// SITE_USER + SITE_PASSWORD are set (production), the whole site (pages + the /api
// proxy) requires those credentials. Unset = open (local dev). Server-side calls to
// the backend bypass this (they use the API key), so SSR is unaffected.

export const config = {
  // Gate everything except Next's static assets.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|robots.txt).*)"],
};

export function proxy(req: NextRequest) {
  const user = process.env.SITE_USER;
  const pass = process.env.SITE_PASSWORD;
  if (!user || !pass) return NextResponse.next();

  const auth = req.headers.get("authorization");
  if (auth?.startsWith("Basic ")) {
    try {
      const [u, p] = atob(auth.slice(6)).split(":");
      if (u === user && p === pass) return NextResponse.next();
    } catch {
      // malformed header -> fall through to challenge
    }
  }

  return new NextResponse("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="research-digest", charset="UTF-8"' },
  });
}
