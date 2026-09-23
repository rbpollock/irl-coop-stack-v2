import type { NextRequest } from "next/server"

import { getSession } from "@/lib/auth"

// Same-origin proxy to MediaMTX's HLS endpoint. Two reasons it exists:
//   1. CORS — the browser can't hit stream.irl.coop directly without CORS, and
//      the HLS Authorization header would trigger a preflight.
//   2. Auth — MediaMTX's JWT auth expects the viewer's coop JWT as a Bearer
//      header; adding it server-side keeps the token out of the browser.
const MEDIAMTX_UPSTREAM =
  process.env.MEDIAMTX_UPSTREAM ?? "http://localhost:8888"

// MediaMTX's HLS session handshake: the first request 302s with a `cookieCheck`
// cookie (Secure in browsers, but Node's fetch does not enforce that), and the
// follow-up carrying the cookie is the real request. Do the dance server-side
// so the browser just sees one same-origin response per segment.
async function fetchHls(url: string, token: string): Promise<Response> {
  const auth = { Authorization: `Bearer ${token}` }
  let res = await fetch(url, { headers: auth, redirect: "manual" })

  if (res.status === 302) {
    const location = res.headers.get("location")
    const cookies = res.headers.getSetCookie?.() ?? []
    if (location && cookies.length) {
      const target = new URL(location, url).toString()
      const cookie = cookies.map((c) => c.split(";")[0]).join("; ")
      res = await fetch(target, { headers: { ...auth, Cookie: cookie } })
    }
  }

  return res
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
): Promise<Response> {
  const session = await getSession()
  const token = session?.accessToken
  if (!token) {
    return new Response("unauthorized", { status: 401 })
  }

  const { path } = await params
  const search = request.nextUrl.search
  const upstream = `${MEDIAMTX_UPSTREAM}/${path.map(encodeURIComponent).join("/")}${search}`

  const upstreamResponse = await fetchHls(upstream, token)

  // Stream the body back, preserving the media content-type (m3u8 = text, ts
  // = video/mp2t) so hls.js parses it correctly.
  const headers = new Headers()
  const contentType = upstreamResponse.headers.get("content-type")
  headers.set("content-type", contentType ?? "application/octet-stream")
  const cacheControl = upstreamResponse.headers.get("cache-control")
  if (cacheControl) headers.set("cache-control", cacheControl)

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers,
  })
}
