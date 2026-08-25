"use client"

import { useSession } from "next-auth/react"

// Decode a JWT payload client-side. The coop access token (session.accessToken)
// is the fleet JWT and carries the `grants` claim — the exact claim the
// oauth2-proxy gates read server-side (--oidc-groups-claim=grants). Decoding
// it here keeps a visible admin affordance from ever out-running the real
// grant. atob handles the base64url alphabet after translating it.
function decodeJwt<T = Record<string, unknown>>(token: string): T | null {
  try {
    const part = token.split(".")[1]
    const b64 = part.replace(/-/g, "+").replace(/_/g, "/")
    const json = decodeURIComponent(
      atob(b64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    )
    return JSON.parse(json) as T
  } catch {
    return null
  }
}

// Whether the signed-in member holds a platform grant (e.g.
// `telephony.platform.admin`). Freshness tracks the 1h access-token refresh;
// a fresh promote/demote appears on the next token renewal (the pbx gate itself
// re-reads grants every --cookie-refresh=5m).
export function useHasGrant(grant: string): boolean {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  if (!token) return false
  const claims = decodeJwt<{ grants?: string[] }>(token)
  return claims?.grants?.includes(grant) ?? false
}
