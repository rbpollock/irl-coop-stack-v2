// Plane group-scope journey: browser sign-in (the harness's proven SSO path) →
// Plane zero-click SSO → project list scoped to the member's coop groups.
//
// The discriminator is TestProj1: e2e-test has NO ProjectMember row for it, and
// every project in the workspace is network=0 (private), so the public clause
// can't grant it either. It can ONLY arrive through `coop_group_scope(user)` —
// i.e. because a coop group the member holds a seat in owns it
// (`projects.group_id`). Seeing it in a real browser is the end-to-end proof
// that the group-scoped identity captured at login reaches the project list.
//
// NOTE: the sign-in must go through the web sign-in form (not a bare
// direct-grant fetch): a host-only coop_session on api.irl.coop does NOT carry
// to plane.irl.coop, and Plane's gateway then falls through to Keycloak's
// Google broker and dead-ends in a headless browser.
import { env } from "../lib.mjs"

export const name = "plane-scope"
export const description = "Plane project list scoped to the member's coop groups (group-owned projects visible)"

const PLANE = process.env.PLANE_URL ?? "https://plane.irl.coop"
const WS = process.env.PLANE_WORKSPACE ?? "coop-test"
// The group-owned project the member is NOT a direct member of.
const GROUP_ONLY_PROJECT = process.env.PLANE_GROUP_ONLY_PROJECT ?? "TestProj1"

export async function run(ctx) {
  const browser = ctx.browser
  const context = await browser.newContext()
  const page = await context.newPage()

  // 1) fleet sign-in — the same path the NocoDB journeys use
  await page.goto(`${env.web}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 45000 })
  await page.click("text=Sign in with a passkey")
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", env.user)
  await page.fill("#password", env.password)
  await page.click("input[type=submit]")
  await page.waitForURL(`${env.web}/**`, { timeout: 45000 })
  ctx.check("member signs in at the fleet gateway", page.url().startsWith(env.web), page.url())

  // 2) Plane — sign-in should carry us in (zero-click)
  await page.goto(`${PLANE}/`, { waitUntil: "domcontentloaded", timeout: 60000 })
  await page.waitForTimeout(8000)
  console.log("PLANE URL after load:", page.url())

  // fallback: a sign-in screen with the irl.coop OIDC entry (Playwright
  // selectors only — `:has-text()` is NOT valid inside page.evaluate).
  if (/sign-in|signin|auth\//.test(page.url())) {
    for (const sel of ["text=irl.coop", "text=OIDC", "text=Continue"]) {
      try {
        await page.click(sel, { timeout: 5000 })
        console.log("sign-in fallback clicked:", sel)
        await page.waitForTimeout(9000)
        break
      } catch {
        /* try the next selector */
      }
    }
    console.log("PLANE URL after sign-in:", page.url())
  }

  // 3) the real project list the UI calls — same origin, member session
  await page.goto(`${PLANE}/${WS}/projects/`, { waitUntil: "domcontentloaded", timeout: 60000 })
  await page.waitForTimeout(9000)
  console.log("PROJECTS URL:", page.url())

  const list = await page.evaluate(async (ws) => {
    const r = await fetch(`/api/workspaces/${ws}/projects/`, {
      headers: { Accept: "application/json" },
    })
    let body = null
    try {
      body = await r.json()
    } catch {
      /* non-JSON */
    }
    return { status: r.status, body }
  }, WS)

  const projects = Array.isArray(list.body) ? list.body : list.body?.results ?? []
  const names = projects.map((p) => p.name).sort()
  console.log("PLANE API projects:", JSON.stringify(names))

  ctx.check("Plane API reachable with the member session", list.status === 200, `http ${list.status}`)
  ctx.check(
    `group-owned project visible (${GROUP_ONLY_PROJECT} proves the group clause)`,
    names.includes(GROUP_ONLY_PROJECT),
    names.join(", ") || "none"
  )
  ctx.check("project count matches the group's ownership", names.length >= 5, `${names.length} projects`)

  // 4) and the UI actually renders them (not just the API)
  const dom = await page.evaluate(() => document.body.innerText || "")
  const rendered = names.filter((n) => dom.includes(n))
  ctx.check(
    "projects render in the UI",
    rendered.length >= 3,
    `${rendered.length}/${names.length} rendered`
  )

  await context.close()
}