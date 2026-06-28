import type { NextRequest } from "next/server";
import { apiFetch } from "@/lib/api";

// Same-origin proxy: the browser calls /api/* on the Next origin; this handler
// forwards to the backend and (server-side) attaches the secret API key, so the
// key never reaches the client and there is no cross-origin CORS to manage.

export const dynamic = "force-dynamic";
// Some backend calls (e.g. polling every feed) take longer than the default
// function limit; allow up to 60s so the proxy doesn't 504 mid-request.
export const maxDuration = 60;

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }): Promise<Response> {
  const { path } = await ctx.params;
  const target = `/api/${path.join("/")}${req.nextUrl.search}`;

  const init: RequestInit = { method: req.method };
  if (req.method !== "GET" && req.method !== "HEAD") {
    const body = await req.text();
    if (body) {
      init.body = body;
      const ct = req.headers.get("content-type");
      if (ct) init.headers = { "content-type": ct };
    }
  }

  const res = await apiFetch(target, init);
  const buf = await res.arrayBuffer();
  return new Response(buf, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
};
