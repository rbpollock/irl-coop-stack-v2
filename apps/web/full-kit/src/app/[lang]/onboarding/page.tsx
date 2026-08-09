"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useSession } from "next-auth/react"

import { buttonVariants } from "@/components/ui/button"

import type { LocaleType } from "@/types"

const COOP_API_URL = process.env.NEXT_PUBLIC_COOP_API_URL ?? "http://localhost:3001"

export default function OnboardingPage() {
  const { data: session, status } = useSession()
  const params = useParams()
  const lang = params.lang as LocaleType
  const router = useRouter()

  const [displayName, setDisplayName] = useState("")
  const [avatar, setAvatar] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Session hydrates after first render — prefill once it arrives.
  useEffect(() => {
    if (session?.user?.name && !displayName) setDisplayName(session.user.name)
    if (session?.user?.avatar && !avatar) setAvatar(session.user.avatar)
  }, [session, displayName, avatar])

  if (status === "loading") return null
  if (status === "unauthenticated") return null

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!session?.accessToken || !displayName.trim()) return
    setSaving(true)
    setError(null)
    try {
      const res = await fetch(`${COOP_API_URL}/api/auth/onboarding`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.accessToken}`,
        },
        body: JSON.stringify({
          displayName: displayName.trim(),
          avatar: avatar.trim() || null,
        }),
      })
      if (!res.ok) throw new Error(`onboarding failed (${res.status})`)
      router.replace(`/${lang}/dashboards/analytics`)
    } catch (err: any) {
      setError(err.message ?? "Failed to save profile")
    } finally {
      setSaving(false)
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-4">
      <form
        onSubmit={handleSubmit}
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

        {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

        <button
          type="submit"
          disabled={saving || !displayName.trim()}
          className={buttonVariants({ className: "mt-6 w-full" })}
        >
          {saving ? "Saving…" : "Finish setup"}
        </button>
      </form>
    </main>
  )
}
