// Shared client for the coop-api profile aggregate (GET /api/v1/profile).
// Mirrors apps/groups/_lib/groups.ts: the NextAuth session access token rides
// as a Bearer header to NEXT_PUBLIC_COOP_API_URL.

export type GroupPrivacy = "open" | "members" | "hidden"

export type ProfileGroup = {
  id: string
  safe_address: string | null
  name: string
  privacy: GroupPrivacy
  kind: string | null
  roles: string[]
}

export type Profile = {
  sub: string
  email: string | null
  displayName: string | null
  name: string | null
  avatar: string | null
  emailVerified: boolean
  status: string
  onboarded: boolean
  onboardedAt: string | null
  createdAt: string | null
  updatedAt: string | null
  membership: {
    groupCount: number
    personalGroup: {
      id: string
      safe_address: string | null
      name: string
    } | null
    groups: ProfileGroup[]
  }
}

const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

export async function getProfile(token: string): Promise<Profile> {
  const res = await fetch(`${COOP_API_URL}/api/v1/profile`, {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(
      (body as { error?: string })?.error ?? `Request failed (${res.status})`
    )
  }
  return res.json() as Promise<Profile>
}
