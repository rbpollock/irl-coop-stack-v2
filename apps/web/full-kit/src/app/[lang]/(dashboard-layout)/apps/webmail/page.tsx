"use client"

import { useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import { ExternalLink, Mail } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

// Roundcube webmail — SSO via Keycloak (same realm as the shadboard; the
// iframe relies on the browser's Keycloak session cookie for auto-login).
const WEBMAIL_URL =
  process.env.NEXT_PUBLIC_WEBMAIL_URL ?? "https://webmail.irl.coop"
const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "http://localhost:3001"

// Canonical identity rule: every user's mailbox is <username>@irl.coop,
// decoupled from the login method (Google, web3auth, passkeys, …). Users
// whose canonical email isn't set yet claim a username here — that sets the
// Keycloak email; the stalwart account self-provisions on first webmail auth.
export default function WebmailPage() {
  const { data: session, status } = useSession()
  const [username, setUsername] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [claimed, setClaimed] = useState(false)
  // Live canonical email from coop-api — the server truth. The NextAuth
  // session email is a login-time snapshot that lags a just-claimed
  // username (and a fresh login may not have happened yet), so the gate
  // must not rely on it. null = still loading.
  const [canonicalEmail, setCanonicalEmail] = useState<
    string | null | undefined
  >(undefined)

  const email = session?.user?.email ?? ""
  const needsUsername =
    !claimed &&
    canonicalEmail !== undefined &&
    !!email &&
    !canonicalEmail?.endsWith("@irl.coop")

  // Resolve the canonical identity once the session is ready.
  const accessToken = session?.accessToken
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
        /* keep the gate closed on network errors — webmail is still reachable */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [accessToken, canonicalEmail])

  if (status === "loading") return null
  if (status === "unauthenticated") return null

  async function claimUsername(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!session?.accessToken || !username.trim()) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${COOP_API_URL}/api/v1/me/username`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.accessToken}`,
        },
        body: JSON.stringify({ username: username.trim() }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setError(
          body?.error === "username_taken"
            ? "That username is taken."
            : `Failed (${res.status})`
        )
        return
      }
      // The Keycloak email is set — reflect it immediately so the gate
      // closes on this visit (and on every future one, via /api/v1/me).
      setCanonicalEmail(`${username.trim()}@irl.coop`)
      setClaimed(true)
    } catch (err) {
      setError((err as Error).message ?? "Failed to claim username")
    } finally {
      setSaving(false)
    }
  }

  // Provisioning gate: no canonical @irl.coop address yet → claim one first.
  if (needsUsername) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="w-full max-w-md rounded-lg border bg-background p-6">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
              <Mail className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold">
                Claim your irl.coop username
              </h2>
              <p className="text-xs text-muted-foreground">
                One identity, any login method — your mailbox will be{" "}
                <span className="font-mono">username@irl.coop</span>
              </p>
            </div>
          </div>
          <form onSubmit={claimUsername} className="space-y-3">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="e.g. robert"
                  className="mt-1 font-mono"
                  autoFocus
                />
              </div>
              <span className="pb-2 font-mono text-xs text-muted-foreground">
                @irl.coop
              </span>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
            <Button
              type="submit"
              className="w-full"
              disabled={saving || !username.trim()}
            >
              {saving ? "Claiming…" : "Claim username"}
            </Button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Webmail</h1>
          <p className="text-xs text-muted-foreground">
            Roundcube on stalwart — one irl.coop identity, no separate login
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <a href={WEBMAIL_URL} target="_blank" rel="noreferrer">
            <ExternalLink className="me-2 h-4 w-4" />
            Open full screen
          </a>
        </Button>
      </div>
      <iframe
        src={WEBMAIL_URL}
        title="Webmail"
        className="h-[calc(100svh-12rem)] w-full border-0 bg-white"
        allow="fullscreen"
      />
    </div>
  )
}
