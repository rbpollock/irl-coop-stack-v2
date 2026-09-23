// Client for the coop-api dues surface (/api/v1/groups/:id/dues/*). Mirrors the
// group client's inline-fetch pattern: the NextAuth session's access token rides as a
// Bearer header to NEXT_PUBLIC_COOP_API_URL.
//
// Note what this client deliberately does NOT have: any function that returns another
// member's dues. The API exposes a member's own status, and a COUNT for the group — so
// a roster of "who paid and who worked instead" cannot be fetched even by accident.
export const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

export type ModeResult = "met" | "not-met" | "unavailable"
export type ModeOutcome = { mode: string; result: ModeResult; detail?: string }

export type ObligationOutcome = {
  id: string
  satisfied: boolean
  /** No available mode could decide it. NOT the same as unmet, and never rendered as if it were. */
  undetermined: boolean
  /** Present only on your OWN dues: a member's modes are their own business. */
  via?: string
  modes: Array<ModeOutcome | { result: ModeResult }>
}

export type MyDues = {
  policy_version: number
  periods: Array<{ obligation: string; start: string; end: string }>
  obligations: ObligationOutcome[]
  satisfied: boolean
  undetermined: boolean
  statement: {
    member: string
    policy_version: number
    period_start: string
    period_end: string
    satisfied: boolean
    undetermined: boolean
    obligations_satisfied: number
    obligations_total: number
    signed: boolean
  }
  can_bookkeep: boolean
  note?: string
}

export type DuesPolicyView = {
  active: {
    version: number
    cadence: string
    grace_days: number
    status: string
    decided_by: string | null
    created_at: string
  } | null
  drafts: Array<{ version: number; created_at: string }>
  history: Array<{
    version: number
    status: string
    decided_by: string | null
    created_at: string
  }>
}

export type DuesSummary = {
  policy_version: number
  period: { start: string; end: string }
  waivers: Array<{ obligation: string; n: number }>
  waivers_total: number
  note: string
}

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
    const body = (await res.json().catch(() => ({}))) as { error?: string }
    const err = new Error(body?.error ?? `Request failed (${res.status})`)
    ;(err as Error & { status?: number }).status = res.status
    throw err
  }
  return res.json() as Promise<T>
}

export type Group = {
  id: string
  name: string
  privacy: string
  kind?: string | null
  /** present when you hold a seat — the signal that dues (which need membership) apply */
  roles?: string[]
}

/** The group list lives in the groups client under another route segment; re-declaring the
 *  one call here keeps this client free of a cross-route import. */
export function listMyGroups(token: string) {
  return api<Group[]>("/api/v1/groups", token)
}

export function getMyDues(token: string, groupId: string) {
  return api<MyDues>(`/api/v1/groups/${groupId}/dues/me`, token)
}

export function getDuesPolicy(token: string, groupId: string) {
  return api<DuesPolicyView>(`/api/v1/groups/${groupId}/dues/policy`, token)
}

export function getDuesSummary(token: string, groupId: string) {
  return api<DuesSummary>(`/api/v1/groups/${groupId}/dues/summary`, token)
}

/** Draft a policy. Validated server-side; the response names the violation if refused. */
export function draftDuesPolicy(
  token: string,
  groupId: string,
  policy: unknown
) {
  return api<{ version: number; status: string; next: string }>(
    `/api/v1/groups/${groupId}/dues/policy`,
    token,
    { method: "PUT", body: JSON.stringify(policy) }
  )
}

/** Adopt a draft. Requires a decision that PASSED — a policy change is a vote, not a click. */
export function adoptDuesPolicy(
  token: string,
  groupId: string,
  version: number,
  decisionId: string
) {
  return api<{ version: number; status: string; changed: boolean }>(
    `/api/v1/groups/${groupId}/dues/policy/${version}/adopt`,
    token,
    { method: "POST", body: JSON.stringify({ decision_id: decisionId }) }
  )
}

export function grantWaiver(
  token: string,
  groupId: string,
  body: { sub: string; obligation: string; period?: string; note?: string }
) {
  return api<{ ok: boolean; bound: string }>(
    `/api/v1/groups/${groupId}/dues/waiver`,
    token,
    { method: "POST", body: JSON.stringify(body) }
  )
}
