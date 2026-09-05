#!/usr/bin/env node
// E2E: LiteFarm fleet-gate SSO + onboarding (the coop's farm app).
//
// Logs in with a passkey (deterministic — the WebAuthn CDP virtual
// authenticator, same as files-flow), then drives farm.irl.coop through the
// fleet gate and verifies the Gate-SSO auto-login. Captures the landing state
// as a screenshot so the onboarding map glitch is visible.
//
// Usage: node e2e/farm-flow.mjs  (env: E2E_USER, default e2e-test@irl.coop)
import { chromium } from "playwright"

const BASE = process.env.E2E_BASE_URL ?? "https://irl.coop"
const FARM = process.env.E2E_FARM_URL ?? "https://farm.irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const PASSWORD = process.env.E2E_PASSWORD ?? ""

let passed = 0
let failed = 0
const check = (name, cond, detail = "") => {
  if (cond) {
    passed++
    console.log(`  PASS  ${name}`)
  } else {
    failed++
    console.log(`  FAIL  ${name}  ${detail}`)
  }
}

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

try {
  // --- 1. passkey login (dashboard session) ---
  await page.goto(`${BASE}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey")
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("input[type=submit]")
  try {
    await page.waitForSelector("input[type=submit]", { timeout: 15000 })
    await page.click("input[type=submit]")
  } catch {
    /* already enrolled */
  }
  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })
  check("passkey login lands on the dashboard", page.url().startsWith(BASE) && !page.url().includes("sign-in"))

  // --- 2. farm.irl.coop through the fleet gate → Gate-SSO auto-login ---
  await page.goto(`${FARM}/`, { waitUntil: "domcontentloaded", timeout: 45000 })
  // the gate auto-redirects (skip-provider-button) → OIDC → Keycloak → gate
  // callback → webapp auto-login. Give the SPA time to boot + fetch /gate_sso.
  await page.waitForTimeout(12000)
  const url = page.url()
  console.log(`  (farm url: ${url})`)
  const body = await page.evaluate(() => document.body.innerText.slice(0, 400))
  console.log(`  (body head: ${JSON.stringify(body)})`)
  const token = await page.evaluate(() => localStorage.getItem("id_token"))
  check("gate SSO auto-login minted a token", !!token)
  check("landed on the app (not the sign-in page)", url.startsWith(FARM) && !url.includes("/oauth2/") && !url.includes("sign-in"))
  await page.screenshot({ path: "/tmp/farm-e2e-landing.png", fullPage: false }).catch(() => {})
  console.log("  (screenshot: /tmp/farm-e2e-landing.png)")

  // --- 3. dashboard iframe (/apps/farm) ---
  await page.goto(`${BASE}/en/apps/farm`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.waitForTimeout(8000)
  const frameUrl = await page.evaluate(() => {
    const f = document.querySelector("iframe")
    return f ? f.src : null
  })
  check("dashboard /apps/farm iframes the farm", frameUrl?.startsWith(FARM) ?? false, String(frameUrl))
  await page.screenshot({ path: "/tmp/farm-e2e-iframe.png", fullPage: false }).catch(() => {})
  console.log("  (screenshot: /tmp/farm-e2e-iframe.png)")
} catch (err) {
  failed++
  console.log(`  FAIL  harness error: ${err.message}`)
  await page.screenshot({ path: "/tmp/farm-e2e-fail.png", fullPage: true }).catch(() => {})
  console.log("  (screenshot: /tmp/farm-e2e-fail.png)")
} finally {
  await browser.close()
}

console.log(`\n${passed}/${passed + failed} E2E checks passed`)
process.exit(failed === 0 ? 0 : 1)
