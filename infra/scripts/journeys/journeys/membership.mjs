// Journey: "A member onboards a collaborator" — create a group (deploys the
// Safe), seat a member, scope a resource. The create step needs the Safe
// contracts on a live RPC; when absent it degrades to a graceful skip.
import { login } from "../lib.mjs"

export const name = "membership"
export const description = "A member onboards a collaborator: create a group, seat a member, scope a resource"

export async function run(ctx) {
  const token = await login(ctx)
  if (!token) {
    ctx.check("login for membership journey", false, "no token")
    return
  }

  const groupName = "journey-" + Date.now()

  // Create a group (Safe deploy + projection row). 503 = Safe not configured.
  const created = await ctx.api("POST", "/api/v1/groups", { token, body: { name: groupName, privacy: "members" } })
  if (created.status === 503) {
    ctx.skip("create group (Safe deploy)", "safe contracts not configured (503)")
    ctx.skip("seat member + scope resource", "depends on a created group")
    return
  }
  ctx.check("create group returns 201 with safe_address", created.status === 201 && !!created.json?.safe_address, `status=${created.status} safe=${created.json?.safe_address?.slice(0, 10)}…`)

  const gid = created.json?.id
  if (!gid) return
  ctx._createdGroup = gid

  // Seat a member (owner-only write).
  const invitee = "journey-invitee-" + Date.now()
  const inv = await ctx.api("POST", `/api/v1/groups/${gid}/members`, {
    token,
    body: { sub: invitee, roles: ["member"], visibility: "alias", alias: "Test Invitee" },
  })
  ctx.check("owner seats a member (201)", inv.status === 201, `status=${inv.status}`)

  // Scope a resource to the group (member-only write).
  const resourceKey = "journey-item-" + Date.now()
  const sc = await ctx.api("POST", `/api/v1/groups/${gid}/resources`, {
    token,
    body: { app: "journey-app", resource_key: resourceKey },
  })
  ctx.check("member scopes a resource (201)", sc.status === 201, `status=${sc.status}`)

  // Read back the scoped resource.
  const res = await ctx.api("GET", `/api/v1/groups/${gid}/resources`, { token })
  ctx.check("scoped resource is listed", res.status === 200 && Array.isArray(res.json) && res.json.some((r) => r.resource_key === resourceKey), `status=${res.status}`)
}
