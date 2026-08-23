// Postiz SSO journey — generic OIDC -> Keycloak -> Postiz (full first-login loop).
//
// Click "Sign in with OAuth" -> Keycloak login -> redirect back with code ->
// Postiz exchanges it. New identity -> registration form (Company only) ->
// /auth/register auto-logs-in and redirects to the app (/launches?onboarding).
// Run INSIDE irlcoop/browser-runner.
import { chromium } from "playwright"

const POSTIZ = process.env.POSTIZ_URL ?? "https://postiz.irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const PASS = process.env.E2E_PASSWORD ?? ""
const COMPANY = "e2e-coop"

const results = []
const check = (name, ok, detail = "") =>
  results.push({ name, ok: !!ok, detail: String(detail) })
const log = (...a) => console.log(...a)

async function clickOauth(page) {
  let clicked = false
  if (await page.locator('img[alt="genericOauth"]').count()) {
    await page.locator('img[alt="genericOauth"]').click()
    clicked = true
  } else {
    try {
      await page.getByText("Sign in with", { exact: false }).first().click()
      clicked = true
    } catch {}
  }
  return clicked
}

let browser
try {
  browser = await chromium.launch()
  const ctx = await browser.newContext()
  const page = await ctx.newPage()

  // 1. Postiz login page -> click OAuth
  await page.goto(`${POSTIZ}/auth/login`, { waitUntil: "domcontentloaded", timeout: 45000 })
  await page.waitForTimeout(2500)
  check("oauth button clicked", await clickOauth(page))

  // 2. Keycloak login form (browser-passkey: username + password)
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", PASS)
  await page.click("input[type=submit]")
  log("[keycloak] filled credentials")

  // 3. Redirect back to Postiz with code + provider=GENERIC
  await page.waitForURL((u) => u.hostname.includes("postiz"), { timeout: 45000 })
  check("code exchange returned to postiz", /code=.*provider=GENERIC/.test(page.url()), page.url())

  // 4. Code exchange -> either registration form (new identity) or auto-login
  //    (existing user: backend sets the httpOnly `auth` cookie + reload:true).
  const hasCompany = await page
    .waitForSelector('input[name="company"]', { timeout: 10000 })
    .then(() => true)
    .catch(() => false)

  if (hasCompany) {
    await page.fill('input[name="company"]', COMPANY)
    log("[register] filling company =", COMPANY)
    await page.click('button[type="submit"]')
  } else {
    log("[login] existing user — backend set auth cookie, awaiting reload")
  }

  // 5. Auto-login -> app (not /auth)
  await page.waitForURL((u) => !/\/auth/.test(u.pathname), { timeout: 30000 })
  const finalUrl = page.url()
  const title = await page.title()
  await page.waitForTimeout(2000)

  const cookies = await ctx.cookies()
  const auth = cookies.find((c) => c.name === "auth")
  const body = await page.evaluate(() => document.body.innerText.slice(0, 300))
  log("[final] url =", finalUrl)
  log("[final] title =", title)
  log("[final] text =", body.replace(/\s+/g, " ").slice(0, 200))
  log("[cookies]", cookies.map((c) => c.name).join(","), "| auth:", auth ? `${auth.value.slice(0, 14)}…` : "NONE")

  check("registration logged in (auth cookie)", !!auth, auth ? "auth cookie present" : "none")
  check("landed in app (off /auth)", !/\/auth/.test(finalUrl), finalUrl)
} catch (err) {
  check("journey error", false, err?.message ?? String(err))
  console.error("ERROR:", err?.message ?? err)
} finally {
  if (browser) await browser.close().catch(() => {})
}

let failed = 0
for (const r of results) {
  console.log(`  ${r.ok ? "PASS" : "FAIL"} ${r.name}${r.detail ? `  [${r.detail}]` : ""}`)
  if (!r.ok) failed++
}
console.log(`SUMMARY: ${results.length - failed}/${results.length} checks passed`)
process.exit(failed ? 1 : 0)
