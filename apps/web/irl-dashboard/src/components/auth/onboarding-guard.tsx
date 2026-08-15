"use client"

import { useEffect, useRef } from "react"
import { usePathname, useRouter } from "next/navigation"
import { useSession } from "next-auth/react"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "http://localhost:3001"

/**
 * Redirects authenticated users who haven't completed coop onboarding to
 * /[lang]/onboarding. Runs once per session token (memoized by user id + token
 * suffix) and only on non-onboarding pages.
 */
export function OnboardingGuard() {
  const { data: session, status } = useSession()
  const pathname = usePathname()
  const router = useRouter()
  const checked = useRef<string | null>(null)

  useEffect(() => {
    if (status !== "authenticated" || !session?.accessToken) return
    if (pathname.includes("/onboarding")) return

    const key = `${session.user?.id}:${session.accessToken.slice(-8)}`
    if (checked.current === key) return
    checked.current = key

    fetch(`${COOP_API_URL}/api/auth/onboarding/status`, {
      headers: { Authorization: `Bearer ${session.accessToken}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && !data.onboarded) {
          const locale = pathname.split("/")[1] ?? "en"
          router.replace(`/${locale}/onboarding`)
        }
      })
      .catch(() => {
        /* coop-api down: let the dashboard render; onboarding re-checks next session */
      })
  }, [status, session, pathname, router])

  return null
}
