export const dynamic = "force-dynamic";
export const maxDuration = 60;

const BASE = process.env.API_PROXY_ORIGIN || "";

type Ctx = { params: Promise<{ path: string[] }> };

async function proxy(req: Request, ctx: Ctx): Promise<Response> {
  const { path } = await ctx.params;
  const incoming = new URL(req.url);
  const target = `${BASE}/api/v1/${path.map(encodeURIComponent).join("/")}${incoming.search}`;

  const headers = new Headers();
  for (const h of ["x-api-key", "content-type", "accept", "last-event-id"]) {
    const v = req.headers.get(h);
    if (v) headers.set(h, v);
  }

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: req.method === "GET" || req.method === "HEAD" ? undefined : req.body,
    // @ts-expect-error duplex is valid at runtime for streaming bodies
    duplex: "half",
    cache: "no-store",
  });

  const out = new Headers();
  for (const h of ["content-type", "cache-control", "x-accel-buffering"]) {
    const v = upstream.headers.get(h);
    if (v) out.set(h, v);
  }
  if (!out.has("cache-control")) out.set("cache-control", "no-store");

  return new Response(upstream.body, { status: upstream.status, headers: out });
}

export const GET = proxy;
export const POST = proxy;
