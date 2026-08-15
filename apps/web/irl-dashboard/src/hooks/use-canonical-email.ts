"use client"

import { useEffect, useState } from "react"

import type { Dispatch, SetStateAction } from "react"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "http://localhost:3001"

type CanonicalEmail = string | null | undefined

// The member's live canonical identity from coop-api (the server truth).
// The NextAuth session email is a login-time snapshot that lags a just-
// claimed @irl.coop username — components gating on the canonical identity
// must read THIS, never session.user.email. undefined = lookup in flight,
// null = no canonical email set yet. The setter lets a successful claim
// reflect immediately on the same visit.
export function useCanonicalEmail(
  accessToken?: string | null
): [CanonicalEmail, Dispatch<SetStateAction<CanonicalEmail>>] {
  const [canonicalEmail, setCanonicalEmail] =
    useState<CanonicalEmail>(undefined)

  useEffect(() => {
    if (!accessToken || canonicalEmail !== undefined) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${COOP_API_URL}/api/v1/me`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        })
        if (!res.ok) return
        const me = (await res.json()) as { email: string | null }
        if (!cancelled) setCanonicalEmail(me.email)
      } catch {
        /* keep the fallback — the session email is still a usable hint */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [accessToken, canonicalEmail])

  return [canonicalEmail, setCanonicalEmail]
}
