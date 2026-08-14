// Shared harness for the journey suite. Runs inside irlcoop/browser-runner
// (Node 18+, Playwright). API journeys use fetch against coop-api; NocoDB
// journeys reuse a single browser context + the passkey SSO flow.
//
// Credentials arrive via env (derived on the host by journeys.sh — the
// browser-runner image has no master.key): E2E_USER, E2E_PASSWORD.

export const env = {
  api: process.env.COOP_API_URL ?? "https://api.irl.coop",
  nocodb: process.env.NOCODB_URL ?? "https://nocodb.irl.coop",
  web: process.env.WEB_URL ?? "https://irl.coop",
  user: process.env.E2E_USER ?? "e2e-test@irl.coop",
  password: process.env.E2E_PASSWORD ?? "",
}

// --- results accumulator ----------------------------------------------------

export function makeCtx() {
  const results = []
  return {
    results,
    check(name, ok, detail = "") {
      results.push({ name, ok: !!ok, detail: detail === undefined ? "" : String(detail) })
    },
    skip(name, detail = "") {
      results.push({ name, ok: true, skip: true, detail: String(detail) })
    },
    // fetch against coop-api; token -> Authorization Bearer, body -> JSON.
    async api(method, path, { token, body } = {}) {
      const res = await fetch(env.api + path, {
        method,
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      })
      let json = null
      try { json = await res.json() } catch { /* non-JSON */ }
      return { status: res.status, json }
    },
  }
}

// Password direct-grant via coop-api (zero redirect, no Keycloak page) → coop
// JWT. Returns the access_token, or null on failure.
export async function login(ctx, username = env.user, password = env.password) {
  const r = await ctx.api("POST", "/api/auth/login", { body: { username, password } })
  return r.json?.access_token ?? null
}

// --- browser / NocoDB -------------------------------------------------------

// Passkey SSO: web sign-in -> Keycloak WebAuthn passwordless form -> NocoDB.
// Returns { page, token } where token is the NocoDB xc-auth value.
export async function loginNocodb(browser) {
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto(`${env.web}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey")
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", env.user)
  await page.fill("#password", env.password)
  await page.click("input[type=submit]")
  await page.waitForURL(`${env.web}/**`, { timeout: 30000 })
  await page.goto(env.nocodb + "/", { waitUntil: "domcontentloaded", timeout: 45000 })
  await page.waitForTimeout(8000)
  const token = await page.evaluate(() => {
    const raw = localStorage.getItem("nocodb-gui-v2")
    return raw ? JSON.parse(raw).token : null
  })
  return { context, page, token }
}

