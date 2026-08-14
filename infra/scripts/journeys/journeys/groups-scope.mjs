// Journey: "A member sees and manages their groups" — RLS-scoped read, the
// auto-provisioned personal group, owner edits, and the owner gate on writes.
import { login } from "../lib.mjs"

export const name = "groups-scope"
export const description = "A member sees their groups (RLS-scoped) and manages what they own"

export async function run(ctx) {
  const token = await login(ctx)
  if (!token) {
    ctx.check("login for groups journey", false, "no token")
    return
  }

  // RLS-scoped read: only what this identity may see.
  const list = await ctx.api("GET", "/api/v1/groups", { token })
  const groups = Array.isArray(list.json) ? list.json : []
  ctx.check("GET /groups returns a list (200)", list.status === 200 && groups.length >= 1, `status=${list.status} n=${groups.length}`)

  // "the user is their own group" — a personal group is auto-provisioned.
  const personal = groups.filter((g) => g.kind === "personal")
  ctx.check("personal group is auto-provisioned", personal.length >= 1, `n=${personal.length}`)

  // Every visible row carries the projection shape (id + safe_address).
  ctx.check(
    "group rows carry id + safe_address",
    groups.length > 0 && groups.every((g) => g.id && "safe_address" in g),
    "",
  )

  // Privacy is a sane, constrained value.
  ctx.check("group privacy is a valid value", groups.every((g) => ["open", "members", "hidden"].includes(g.privacy)), "")

  // Owner edit: PATCH a group this identity owns, then restore.
  const owned = groups.find((g) => (g.roles ?? []).includes("owner"))
  if (owned) {
    const before = owned.description ?? null
    const target = "journey-test-" + Date.now()
    const up = await ctx.api("PATCH", `/api/v1/groups/${owned.id}`, { token, body: { description: target } })
    const changed = up.status === 200 && up.json?.description === target
    ctx.check("owner can PATCH their group", changed, `status=${up.status}`)
    await ctx.api("PATCH", `/api/v1/groups/${owned.id}`, { token, body: { description: before ?? "" } })
  } else {
    ctx.check("owner can PATCH their group", false, "no owned group in scope")
  }

  // Owner gate: a group the caller does NOT own is forbidden (403).
  const foreign = await ctx.api("PATCH", "/api/v1/groups/00000000-0000-0000-0000-000000000000", {
    token,
    body: { description: "x" },
  })
  ctx.check("non-owned group PATCH is forbidden (403)", foreign.status === 403, `status=${foreign.status}`)
}
