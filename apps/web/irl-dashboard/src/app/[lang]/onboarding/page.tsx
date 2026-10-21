"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useSession } from "next-auth/react"

import type { LocaleType } from "@/types"

import { buttonVariants } from "@/components/ui/button"
import { coopJson } from "@/lib/coop-api"
import { registerPasskey } from "@/lib/passkey"

// Seed prompts for "how do you want to help your community" — the offers side
// of the needs/offers matching (docs/design/weavers.md). Free-text, tappable.
const OFFER_EXAMPLES = [
  "I'm an artist",
  "I drive",
  "I'm a musician who works for tips",
  "I help people organize and prettify things",
  "I'm an interior designer",
  "I'm a marketing guru",
  "I'm a good photographer",
  "I'm a good videographer",
]

// Two steps: your profile, then your key. The passkey is not just for signing in —
// it is the key that OWNS your account (B-11), so this is where the account is
// created, owned by you. Neither step is a wall: skipping the key still lets you in
// (you simply have no account yet to hold anything).
export default function OnboardingPage() {
  const { data: session, status } = useSession()
  const params = useParams()
  const lang = params.lang as LocaleType
  const router = useRouter()

  const [phase, setPhase] = useState<"profile" | "passkey">("profile")
  const [displayName, setDisplayName] = useState("")
  const [avatar, setAvatar] = useState("")
  const [offerings, setOfferings] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [safeAddress, setSafeAddress] = useState<string | null>(null)

  const token = session?.accessToken

  // Session hydrates after first render — prefill once it arrives.
  useEffect(() => {
    if (session?.user?.name && !displayName) setDisplayName(session.user.name)
    if (session?.user?.avatar && !avatar) setAvatar(session.user.avatar)
  }, [session, displayName, avatar])

  if (status === "loading" || status === "unauthenticated") return null

  const enter = () => router.replace("/" + lang + "/dashboards/analytics")

  async function saveProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!token || !displayName.trim()) return
    setSaving(true)
    setError(null)
    try {
      await coopJson("/api/auth/onboarding", token, {
        method: "POST",
        body: JSON.stringify({
          displayName: displayName.trim(),
          avatar: avatar.trim() || null,
          offerings: offerings.trim() || null,
        }),
      })
      setPhase("passkey")
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save profile")
    } finally {
      setSaving(false)
    }
  }

  async function createKey() {
    setSaving(true)
    setError(null)
    try {
      const res = await registerPasskey(
        token,
        displayName.trim(),
        session?.user?.email ?? "member@irl.coop",
      )
      setSafeAddress(res.safe_address)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not set up your passkey")
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-4">
      {phase === "profile" ? (
        <form
          onSubmit={saveProfile}
          className="w-full max-w-md rounded-xl border bg-card p-8 shadow-sm"
        >
          <h1 className="text-2xl font-bold">Welcome to irl.coop</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            One more step — set up your cooperative profile.
          </p>

          <label className="mt-6 block text-sm font-medium" htmlFor="displayName">
            Display name
          </label>
          <input
            id="displayName"
            className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="How should members see you?"
            required
          />

          <label className="mt-4 block text-sm font-medium" htmlFor="avatar">
            Avatar URL <span className="text-muted-foreground">(optional)</span>
          </label>
          <input
            id="avatar"
            className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            value={avatar}
            onChange={(e) => setAvatar(e.target.value)}
            placeholder="https://…"
          />

          <label className="mt-4 block text-sm font-medium" htmlFor="offerings">
            How do you want to help your community?
          </label>
          <textarea
            id="offerings"
            className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            value={offerings}
            onChange={(e) => setOfferings(e.target.value)}
            placeholder="What can you offer? (artist, driver, musician, organizer…)"
            rows={3}
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {OFFER_EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => setOfferings(ex)}
                className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground transition hover:border-ring hover:text-foreground"
              >
                {ex}
              </button>
            ))}
          </div>

          {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

          <button
            type="submit"
            disabled={saving || !displayName.trim()}
            className={buttonVariants({ className: "mt-6 w-full" })}
          >
            {saving ? "Saving…" : "Continue"}
          </button>
        </form>
      ) : (
        <section className="w-full max-w-md rounded-xl border bg-card p-8 shadow-sm">
          <h1 className="text-2xl font-bold">Now your key</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Your passkey is the key to your account. It signs you in, and it owns
            your account — nobody else holds a copy, including us.
          </p>

          {safeAddress ? (
            <div className="mt-4 rounded border border-emerald-300/30 bg-emerald-500/5 p-3 text-sm text-emerald-800">
              <p className="font-semibold">Your account is ready.</p>
              <code className="mt-1 block break-all font-mono text-xs">
                {safeAddress}
              </code>
            </div>
          ) : null}

          {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

          <div className="mt-6 flex flex-col gap-2">
            {safeAddress ? (
              <button
                type="button"
                onClick={enter}
                className={buttonVariants({ className: "w-full" })}
              >
                Enter
              </button>
            ) : (
              <>
                <button
                  type="button"
                  onClick={createKey}
                  disabled={saving}
                  className={buttonVariants({ className: "w-full" })}
                >
                  {saving ? "Waiting for your device…" : "Create a passkey"}
                </button>
                <button
                  type="button"
                  onClick={enter}
                  className={buttonVariants({ variant: "ghost", className: "w-full" })}
                >
                  Skip for now
                </button>
                <p className="text-xs text-muted-foreground">
                  You can set one up later. Until you do, there is no account here
                  to hold anything.
                </p>
              </>
            )}
          </div>
        </section>
      )}
    </main>
  )
}
