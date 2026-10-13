// Journey: "Stack status reports host processes" — regression lock.
//
// The reconciler's view of the world is `docker ps`, so an app with no container
// was invisible to every status surface. On 2026-10-03 the report read
// "61/61 core services healthy" while https://api.irl.coop had been 502 for four
// days (a mid-edit compile error killed the coop-api dev server and ts-node-dev
// never respawned). This locks the leg that closes that blind spot: the host
// processes must appear, with liveness, in `GET /api/v1/stack/status`.
import { login } from "../lib.mjs"

export const name = "stack-status"
export const description = "Host-process apps appear in stack status with real liveness"

export async function run(ctx) {
  // 1. Auth-gated like every coop-api route — no stack internals to anonymous.
  const anon = await ctx.api("GET", "/api/v1/stack/status")
  ctx.check("anonymous stack status is 401", anon.status === 401, `status=${anon.status}`)

  const token = await login(ctx)
  if (!token) {
    ctx.check("obtained a coop token", false, "login failed")
    return
  }
  const r = await ctx.api("GET", "/api/v1/stack/status", { token })
  ctx.check("authenticated stack status is 200", r.status === 200, `status=${r.status}`)
  if (r.status !== 200) return

  const s = r.json?.summary ?? {}
  const hosts = r.json?.host_apps ?? []

  ctx.check(
    "summary carries the host-app leg",
    ["host_apps", "host_healthy", "core_host_apps", "core_host_healthy", "core_host_problems"]
      .every((k) => typeof s[k] === "number"),
    JSON.stringify({ host_apps: s.host_apps, core_host_apps: s.core_host_apps })
  )

  ctx.check(
    "host_apps[] lists every host process with a port",
    Array.isArray(hosts) && hosts.length >= 5 && hosts.every((h) => h.name && typeof h.port === "number"),
    hosts.map((h) => `${h.name}:${h.port}`).join(" ")
  )

  // 2. coop-api answered THIS request, so reporting it "not answering" would be a
  //    probe bug — not an outage. Guards against a leg that always reads red.
  const self = hosts.find((h) => h.name === "coop-api")
  ctx.check("coop-api is reported healthy (it just answered this request)", self?.healthy === true,
    JSON.stringify(self ?? null))

  // 3. On a live stack every core host app is up. This is the assertion that
  //    would have failed every day of the 2026-09-29 → 10-03 outage.
  ctx.check("0 core host apps down on a live stack", s.core_host_problems === 0,
    JSON.stringify(hosts.filter((h) => !h.healthy).map((h) => `${h.name}:${h.status}`)))
}