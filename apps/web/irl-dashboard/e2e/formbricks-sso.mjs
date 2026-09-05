#!/usr/bin/env node
// E2E: Formbricks gate-SSO — dashboard passkey login → forms.irl.coop →
// gate (coop-api SSO) → x-forwarded-email → auto-login → /environments.
// The redirect chain (gate → coop-api authorize → gate callback → formbricks
// gate-sso) is multi-hop, so we navigate and then let it settle.
import { chromium } from "playwright"

const BASE = process.env.E2E_BASE_URL ?? "https://irl.coop"
const FORMS = process.env.E2E_FORMS_URL ?? "https://forms.irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const PASSWORD = process.env.E2E_PASSWORD ?? ""

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()
const cdp = await context.newCDPSession(page)
await cdp.send("WebAuthn.enable", { enableUI: false })
await cdp.send("WebAuthn.addVirtualAuthenticator", {
  options: {
    protocol: "ctap2",
    transport: "internal",
    hasResidentKey: true,
    hasUserVerification: true,
    isUserVerified: true,
    automaticPresenceSimulation: true,
  },
})

const describe = async (label) => {
  const url = page.url()
  const body = await page.evaluate(() => document.body.innerText.slice(0, 160))
  console.log(`${label} URL:`, url.slice(0, 120))
  console.log(`${label} BODY:`, JSON.stringify(body.replace(/\s+/g, " ").trim()))
  return { url, body }
}

try {
  // 1. dashboard passkey login
  await page.goto(`${BASE}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey")
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("input[type=submit]")
  try {
    await page.waitForSelector("input[type=submit]", { timeout: 15000 })
    await page.click("input[type=submit]")
  } catch {}
  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })
  console.log("dashboard logged in:", page.url().slice(0, 80))

  // 2. forms.irl.coop root → gate SSO → auto-login
  await page.goto(`${FORMS}/`, { waitUntil: "domcontentloaded", timeout: 60000 })
  await page.waitForTimeout(15000)
  const root = await describe("ROOT")

  // 3. if root didn't land us in the app, hit the auth-protected route directly
  let env = null
  if (!/environments|workspaces|projects/i.test(root.url)) {
    await page.goto(`${FORMS}/environments`, { waitUntil: "domcontentloaded", timeout: 60000 })
    await page.waitForTimeout(12000)
    env = await describe("ENVIRONMENTS")
  }

  const finalUrl = env?.url ?? root.url
  const ok = /environments|workspaces|projects/i.test(finalUrl) && !/auth\/login|oauth2\/callback/i.test(finalUrl)
  console.log("AUTO-LOGIN OK:", ok ? "YES" : "NO")
  await page.screenshot({ path: "/tmp/formbricks-sso.png", fullPage: false }).catch(() => {})
  console.log("(screenshot: /tmp/formbricks-sso.png)")
} catch (err) {
  console.log("ERROR:", err.message)
  await page.screenshot({ path: "/tmp/formbricks-sso-fail.png", fullPage: true }).catch(() => {})
  console.log("(fail screenshot: /tmp/formbricks-sso-fail.png)")
} finally {
  await browser.close()
}
