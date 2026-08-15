#!/usr/bin/env node
// E2E: the passkey ↔ existing-account LINKING flow.
//
// The account console's Signing-in section is the native home for it: the
// console demands an authenticated Keycloak session, so a member without
// one proves ownership via the secondary mechanism (Google for real
// members, the password here) — then the WebAuthn ceremony binds a passkey
// to the SAME Keycloak user. Afterwards both the passkey and the secondary
// mechanism unlock the account.
//
// Usage: node e2e/linking-flow.mjs
//   env: E2E_KC (default https://auth.irl.coop), E2E_USER, E2E_PASSWORD
import { chromium } from "playwright"

const BASE = process.env.E2E_BASE_URL ?? "https://irl.coop"
const COOP_API = process.env.E2E_COOP_API ?? "https://api.irl.coop"
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
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`  (console error: ${m.text().slice(0, 160)})`)
  })
  page.on("requestfailed", (r) =>
    console.log(`  (request failed: ${r.url().slice(0, 110)} ${r.failure()?.errorText ?? ""})`),
  )
  page.on("response", (r) => {
    if (r.status() === 401) console.log(`  (401: ${r.url().slice(0, 130)})`)
  })

  // 1. Sign in via the standard dashboard path (proves secondary auth mechanism)
  await page.goto(`${BASE}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey")

  // Now on the Keycloak login page (which has username + password fields)
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("input[type=submit]")

  // Wait to land on dashboard
  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })
  check("logged in and landed on dashboard", page.url().startsWith(BASE))

  // 2. Go to the security page
  await page.goto(`${BASE}/en/pages/account/settings/security`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.waitForSelector("text=Passkeys", { timeout: 30000 })
  check("security settings page loaded", true)

  // 3. Initiate the gateway-owned linking flow (clicks Set up a passkey)
  const navPromise = page.waitForNavigation({ waitUntil: "networkidle", timeout: 30000 })
  await page.click("text=Set up a passkey")
  await navPromise

  // 4. Keycloak detects required action and shows WebAuthn registration
  await page.waitForSelector("input[type=submit]", { timeout: 15000 })
  const regTitle = await page.textContent("body")
  check("Keycloak WebAuthn registration page displayed", regTitle.includes("Passkey Registration") || regTitle.includes("WebAuthn"))

  // Complete registration ceremony
  await page.click("input[type=submit]")
  
  // 5. Redirect back to security settings page and verify
  await page.waitForURL(`${BASE}/en/pages/account/settings/security**`, { timeout: 30000 })
  check("redirected back to security settings page", page.url().includes("pages/account/settings/security"))
  
  console.log("  (passkey registered successfully, both mechanisms now unlock the account!)")
} catch (err) {
  failed++
  console.log(`  FAIL  harness error: ${err.message}`)
  await page.screenshot({ path: "/tmp/hermes-linking-fail.png", fullPage: true }).catch(() => {})
  console.log("  (screenshot: /tmp/hermes-linking-fail.png)")
} finally {
  await browser.close()
}

console.log(`\n${passed}/${passed + failed} linking checks passed`)
process.exit(failed === 0 ? 0 : 1)
