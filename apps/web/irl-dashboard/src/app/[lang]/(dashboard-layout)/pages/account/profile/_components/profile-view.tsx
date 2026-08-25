"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { useSession } from "next-auth/react"
import { AlertCircle, RefreshCw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

import { getProfile, type Profile } from "../_lib/profile"
import { ProfileContent } from "./profile-content"
import { ProfileHeader } from "./profile-header"

// Client wrapper for the profile page: fetches the authenticated member's
// real profile (identity + coop profile + membership) and feeds it into the
// existing header/content components. Mirrors the apps/groups page pattern
// (useSession → accessToken → Bearer fetch).
export function ProfileView() {
  const { data: session } = useSession()
  const params = useParams()
  const locale = (params.lang as string) ?? "en"

  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const token = session?.accessToken as string | undefined

  function load() {
    if (!token) return
    setLoading(true)
    setError(null)
    getProfile(token)
      .then(setProfile)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  if (!token) return null

  if (loading) {
    return (
      <div className="container space-y-4 px-0 py-4">
        <Skeleton className="h-44 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (error || !profile) {
    return (
      <div className="container flex flex-col items-center justify-center gap-3 px-0 py-16 text-center">
        <AlertCircle className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          {error ?? "Could not load your profile."}
        </p>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="me-2 h-3.5 w-3.5" />
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="container px-0">
      <ProfileHeader locale={locale} profile={profile} onAvatarChanged={load} />
      <ProfileContent profile={profile} />
    </div>
  )
}
