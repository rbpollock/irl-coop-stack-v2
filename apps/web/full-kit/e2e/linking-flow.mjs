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

const KC = process.env.E2E_KC ?? "https://auth.irl.coop"
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
  // 1. the account console — no Keycloak session → the login page
  await page.goto(`${KC}/realms/irl-coop/account/`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.waitForSelector("#username", { timeout: 30000 })
  check("console demands the session (login page)", true)

  // 2. the secondary mechanism: username + password (Google for members)
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("input[type=submit]")

  // the console's Signing-in section: Account security → Signing in
  // (a reload right after the login redirect re-establishes the console's
  // session — its section fetches otherwise 401)
  await page.reload({ waitUntil: "domcontentloaded" })
  await page.click("text=Account security")
  await page.click("text=Signing in")
  await page.waitForSelector("text=Set up a security key", { timeout: 30000 })
  check("Signing-in section shows the passkey setup", true)
  await page.click("text=Set up a security key")

  // 3. the ceremony — the virtual authenticator binds the credential
  await page.waitForSelector("#kc-registration-form input[type=submit], input[type=submit]", { timeout: 15000 })
  await page.click("input[type=submit]")
  await page.waitForTimeout(1500)

  // 4. bound: the section no longer offers a fresh setup (a credential exists)
  const body = await page.textContent("body")
  check("passkey bound to the account", /security key|passkey/i.test(body) && !body.includes("Set up a security key"))
  console.log("  (both mechanisms now unlock the account: the passkey + the secondary)")
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
