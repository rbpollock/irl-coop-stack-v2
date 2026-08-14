// Journey: "An anonymous visitor is walled off" — no identity, no data. Every
// auth-gated surface rejects a missing/bad token, and NocoDB's external source
// returns nothing without a session.
import { env } from "../lib.mjs"

export const name = "anonymous"
export const description = "An anonymous visitor is walled off (no identity, no data)"

export async function run(ctx) {
  // coop-api groups: no token → 401.
  const noToken = await ctx.api("GET", "/api/v1/groups")
  ctx.check("GET /groups without a token is rejected (401)", noToken.status === 401, `status=${noToken.status}`)

  // coop-api groups: garbage token → 401.
  const badToken = await ctx.api("GET", "/api/v1/groups", { token: "not-a-jwt" })
  ctx.check("GET /groups with a bad token is rejected (401)", badToken.status === 401, `status=${badToken.status}`)

  // coop-api group create: unauthenticated → 401 (no Safe deploy happens).
  const noAuthCreate = await ctx.api("POST", "/api/v1/groups", { body: { name: "anonymous" } })
  ctx.check("POST /groups without a token is rejected (401)", noAuthCreate.status === 401, `status=${noAuthCreate.status}`)

  // NocoDB external source: no xc-auth → the records endpoint refuses/empties.
  const nc = await fetch(`${env.nocodb}/api/v2/tables/mpi01cdb2jofe2r/records`)
  ctx.check("NocoDB records without a session are not readable", nc.status !== 200, `status=${nc.status}`)
}
