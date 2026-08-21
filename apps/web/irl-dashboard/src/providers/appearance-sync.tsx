"use client"

import { useEffect, useRef, useState } from "react"
import { useSession } from "next-auth/react"

import { radii, themes } from "@/configs/themes"
import { useSettings } from "@/hooks/use-settings"
import type { ModeType, RadiusType, ThemeType } from "@/types"

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "http://localhost:3001"

// Syncs the dashboard's appearance settings (theme/mode/radius) with the
// shared coop-api profile, so "one identity, every app" carries the chosen
// accent color to webmail and every other surface. The `settings` cookie stays
// the local cache; coop-api is the source of truth. Mounted inside the
// NextAuth session provider (so useSession is available) and the settings
// provider (so useSettings is available) — renders nothing.
export function AppearanceSync() {
  const { data: session } = useSession()
  const { settings, updateSettings } = useSettings()
  const token = session?.accessToken
  const pulled = useRef(false)
  const pushed = useRef("")
  // Push only AFTER the initial pull, so the stale cookie value can't clobber
  // the server value (which webmail may already be reading).
  const [ready, setReady] = useState(false)

  // Pull once on first authenticated load — coop-api wins over the cookie.
  useEffect(() => {
    if (!token || pulled.current) return
    pulled.current = true
    ;(async () => {
      try {
        const res = await fetch(`${COOP_API_URL}/api/v1/profile`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok) return
        const profile = (await res.json()) as {
          preferences?: Record<string, unknown>
        }
        const prefs = profile.preferences ?? {}
        if (typeof prefs !== "object") return
        const next = { ...settings }
        let changed = false
        if (typeof prefs.theme === "string" && prefs.theme in themes) {
          next.theme = prefs.theme as ThemeType
          changed = true
        }
        if (
          typeof prefs.mode === "string" &&
          (prefs.mode === "light" || prefs.mode === "dark" || prefs.mode === "system")
        ) {
          next.mode = prefs.mode as ModeType
          changed = true
        }
        if (typeof prefs.radius === "number" && radii.includes(prefs.radius as RadiusType)) {
          next.radius = prefs.radius as RadiusType
          changed = true
        }
        if (changed) updateSettings(next)
      } catch {
        /* offline / unauthenticated — the cookie stays authoritative */
      } finally {
        setReady(true)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  // Push on change (fire-and-forget). Gated on `ready` so the initial cookie
  // value is never pushed over the server value before the pull lands.
  useEffect(() => {
    if (!token || !ready) return
    const key = `${settings.theme}|${settings.mode}|${settings.radius}`
    if (key === pushed.current) return
    pushed.current = key
    fetch(`${COOP_API_URL}/api/v1/profile/preferences`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        theme: settings.theme,
        mode: settings.mode,
        radius: settings.radius,
      }),
    }).catch(() => {})
  }, [token, ready, settings.theme, settings.mode, settings.radius])

  return null
}
