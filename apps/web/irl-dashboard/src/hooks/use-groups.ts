"use client"

import { useSession } from "next-auth/react"

export type CoopGroup = { slug: string; name: string; roles: string[] }

// Decode the coop access-token payload client-side (same base64url->atob dance
// as use-has-grant.ts).
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

// The signed-in member's coop groups, decoded from the access token's `groups`
// claim (a JSON string of {slug,name,roles[]} minted by coop-api). Empty while
// the session loads or the token is absent.
export function useGroups(): CoopGroup[] {
  const { data: session } = useSession()
  const token = session?.accessToken as string | undefined
  if (!token) return []
  const claims = decodeJwt<{ groups?: string }>(token)
  if (!claims?.groups) return []
  try {
    const parsed = JSON.parse(claims.groups)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(
        (g: any) =>
          g && typeof g.name === "string" && typeof g.slug === "string"
      )
      .map((g: any) => ({
        slug: g.slug,
        name: g.name,
        roles: Array.isArray(g.roles) ? g.roles.map(String) : [],
      }))
  } catch {
    return []
  }
}
