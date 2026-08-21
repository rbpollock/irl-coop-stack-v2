// Shared client for the coop-api group surface (/api/v1/groups). Mirrors the
// inline-fetch pattern already used across the dashboard (webmail, group-wallet):
// the NextAuth session's access token rides as a Bearer header to
// NEXT_PUBLIC_COOP_API_URL.
export type GroupPrivacy = "open" | "members" | "hidden"
export type MemberVisibility = "role-only" | "alias" | "canonical"

export type Group = {
  id: string
  safe_address: string | null
  name: string
  description: string | null
  privacy: GroupPrivacy
  kind?: string | null
  created_at: string
  roles?: string[]
  alias?: string | null
  visibility?: MemberVisibility | null
}

export type Member = {
  sub: string
  roles: string[]
  alias: string | null
  visibility: MemberVisibility
  created_at?: string
}

export type Resource = {
  app: string
  resource_key: string
  scoped_by: string
  scoped_at: string
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

export function listGroups(token: string) {
  return api<Group[]>("/api/v1/groups", token)
}

export function createGroup(
  token: string,
  body: { name: string; privacy: GroupPrivacy }
) {
  return api<Group & { tx_hash?: string }>("/api/v1/groups", token, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function updateGroup(
  token: string,
  id: string,
  body: { name?: string; description?: string; privacy?: GroupPrivacy }
) {
  return api<Group>(`/api/v1/groups/${id}`, token, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

export function listMembers(token: string, id: string) {
  return api<Member[]>(`/api/v1/groups/${id}/members`, token)
}

export function inviteMember(
  token: string,
  id: string,
  body: {
    sub: string
    roles: string[]
    alias?: string
    visibility?: MemberVisibility
  }
) {
  return api<Member>(`/api/v1/groups/${id}/members`, token, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function listResources(token: string, id: string) {
  return api<Resource[]>(`/api/v1/groups/${id}/resources`, token)
}

export function scopeResource(
  token: string,
  id: string,
  body: { app: string; resource_key: string }
) {
  return api<Resource>(`/api/v1/groups/${id}/resources`, token, {
    method: "POST",
    body: JSON.stringify(body),
  })
}
