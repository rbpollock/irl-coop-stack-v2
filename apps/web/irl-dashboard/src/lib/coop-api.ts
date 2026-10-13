// Shared client for the coop-api surface.
//
// Why this exists: the NextAuth session carries the coop JWT, which is a
// SHORT-LIVED (1h) token refreshed server-side by the `jwt` callback in
// configs/next-auth.ts whenever the NextAuth session is READ. A tab that has
// been open past the token's life keeps its in-memory copy and every call 401s
// with `invalid_token` until the page re-reads the session — the failure was
// silent and looked like the page's fault.
//
// Two defences, used together:
//   1. SessionProvider refetches the session on an interval (and on window
//      focus), so the token is refreshed and propagated to every useSession()
//      consumer well before it expires.
//   2. coopFetch re-reads the session and retries ONCE on a 401, so a request
//      that slipped through the interval still recovers instead of surfacing
//      "invalid_token" to the user.

import { getSession } from "next-auth/react"

export const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

/**
 * Re-read the NextAuth session. Server-side this runs the `jwt` callback,
 * which exchanges the long-lived `coop_session` cookie for a fresh coop JWT.
 * Returns the (possibly new) access token.
 */
export async function refreshAccessToken(): Promise<string | undefined> {
  // Client-only: getSession() hits /api/auth/session through the browser.
  // On the server the caller's token is already whatever the request carried.
  if (typeof window === "undefined") return undefined
  try {
    const session = await getSession()
    return (session as { accessToken?: string } | null)?.accessToken
  } catch {
    return undefined
  }
}

/**
 * fetch() against coop-api with the session bearer token, retrying once with a
 * freshly-refreshed token if the first attempt is rejected with a 401.
 */
export async function coopFetch(
  path: string,
  token: string | undefined,
  init?: RequestInit
): Promise<Response> {
  const url = `${COOP_API_URL}${path}`

  const send = (t?: string) => {
    const headers = new Headers(init?.headers)
    // Only claim a content type when there IS a body — a GET carrying
    // application/json triggers a CORS preflight for nothing, and the SSE
    // stream must not look like a JSON request. The session token is applied
    // LAST so it always wins over a caller's own (possibly stale) header.
    if (init?.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json")
    }
    if (t) headers.set("Authorization", `Bearer ${t}`)
    return fetch(url, { ...init, headers })
  }

  const res = await send(token)
  if (res.status !== 401) return res

  const fresh = await refreshAccessToken()
  if (!fresh || fresh === token) return res
  return send(fresh)
}

/**
 * coopFetch + JSON decoding + the shared error shape the call sites throw on
 * (the server answers `{ error: "..." }`, which the UI renders directly).
 */
export async function coopJson<T>(
  path: string,
  token: string | undefined,
  init?: RequestInit
): Promise<T> {
  const res = await coopFetch(path, token, init)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err = new Error(
      (body as { error?: string })?.error ?? `Request failed (${res.status})`
    ) as Error & { status?: number }
    // Callers branch on the status (403 "not a member" vs 404 vs 503), so it
    // rides along on the error rather than being flattened into the message.
    err.status = res.status
    throw err
  }
  return res.json() as Promise<T>
}