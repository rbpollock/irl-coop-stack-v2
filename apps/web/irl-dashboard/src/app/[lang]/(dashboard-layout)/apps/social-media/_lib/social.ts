// Client for the coop-api Social Media surface (/api/v1/social) + Decisions
// (for the "propose connect" path). Mirrors the groups lib's inline-fetch
// pattern: the NextAuth access token rides as a Bearer header to
// NEXT_PUBLIC_COOP_API_URL.

export type SocialSummary = {
  group_id: string
  group_name: string
  org_id: string
  total_posts: number
  posts_by_state: { state: string; n: number }[]
  posts_by_day: { day: string; n: number }[]
  integrations: number
  members: number
  recent_posts: {
    id: string
    content: string
    state: string
    created_at: string
  }[]
}

export const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

async function api<T>(
  path: string,
  token: string,
  init?: RequestInit
): Promise<T> {
  const res = await fetch(`${COOP_API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(
      (body as { error?: string })?.error ?? `Request failed (${res.status})`
    )
  }
  return res.json() as Promise<T>
}

export function getSocialSummary(token: string) {
  return api<SocialSummary[]>("/api/v1/social/summary", token)
}

// Propose connecting Postiz to a group the caller cannot connect directly —
// a Decisions proposal (irl-coop-group.md §6) authorizing the resource scope.
export function proposeConnectPostiz(
  token: string,
  groupId: string,
  groupName: string
) {
  return api(`/api/v1/groups/${groupId}/decisions`, token, {
    method: "POST",
    body: JSON.stringify({
      title: `Connect Social Media (Postiz) to ${groupName}`,
      description:
        "Authorize the group to provision a Postiz workspace (org + synced membership).",
      options: ["yes", "no"],
      quorum_pct: 50,
      payload: { app: "postiz", action: "connect", resource_key: groupId },
    }),
  })
}
