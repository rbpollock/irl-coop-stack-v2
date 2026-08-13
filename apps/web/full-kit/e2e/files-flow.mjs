#!/usr/bin/env node
// E2E: passkey login + the files-panel flow (virtual folder manager).
//
// Why passkeys: the interactive Google leg is the one flaky, unscriptable
// part of the fleet login. A WebAuthn ceremony driven by a CDP virtual
// authenticator is deterministic — one instant approval, no Google page.
// This is also the crypto-native login the fleet vision wants.
//
// Prereqs (one-time, see docs/design/files-panel.md §passkey-testing):
//   - Keycloak realm has the webauthn-passwordless browser flow (see
//     /tmp/hermes-kc-webauthn-config.py) and e2e-test carries the
//     webauthn-register-passwordless required action.
// Usage: node e2e/files-flow.mjs   (env: E2E_USER, default e2e-test@irl.coop)
import { chromium } from "playwright"

const BASE = process.env.E2E_BASE_URL ?? "https://irl.coop"
const COOP_API = process.env.E2E_COOP_API ?? "https://api.irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"

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
  // --- 1. passkey login: the fleet authorize WITHOUT the Google hint ---
  const authorize =
    `${COOP_API}/api/auth/authorize?client_id=nextauth` +
    `&redirect_uri=${encodeURIComponent(`${BASE}/api/auth/callback/coop-api`)}` +
    "&response_type=code&scope=openid%20profile%20email&state=e2e"
  await page.goto(authorize, { waitUntil: "domcontentloaded", timeout: 30000 })

  // the Keycloak passwordless form (username only — no Google, no password)
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.click("input[type=submit]")

  // first login: the WebAuthn registration page (the required action) — the
  // virtual authenticator creates the credential on the click
  try {
    await page.waitForSelector("#register-webauth-passwordless", { timeout: 15000 })
    await page.click("#register-webauth-passwordless input[type=submit]")
    console.log("  (enrolled a fresh passkey via the registration ceremony)")
  } catch {
    /* already enrolled — the authenticate ceremony runs instead */
  }

  // the ceremony completes → the gateway callback → the dashboard session
  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })
  check("passkey login lands on the dashboard", page.url().startsWith(BASE))
  check("session cookie set", (await context.cookies(`${BASE}/`)).some((c) => c.name === "session-token"))

  // --- 2. the files flow ---
  await page.goto(`${BASE}/en/apps/docs`, { waitUntil: "domcontentloaded" })
  await page.waitForSelector("text=My folders", { timeout: 20000 })

  // create a folder
  await page.click("text=New folder")
  await page.fill("input[placeholder='Folder name']", "E2E Passkey Folder")
  await page.click("text=Create")
  await page.waitForSelector("text=E2E Passkey Folder", { timeout: 10000 })
  check("folder created in the panel", true)

  // create a document (captures the name from the API response)
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/v1/docs/new") && r.request().method() === "POST"),
    page.click("button:has-text('New')"),
  ])
  await page.click("text=Document")
  const docName = (await resp.json()).name
  check("document created", !!docName, docName)

  // back to the list, then move the doc into the folder
  await page.click("text=Back to documents")
  await page.waitForSelector(`text=${docName}`, { timeout: 10000 })
  const row = page.locator("li", { hasText: docName }).first()
  await row.hover()
  await row.locator("button[title='Move to folder']").click()
  await page.click("text=E2E Passkey Folder")
  await page.waitForSelector("text=E2E Passkey Folder", { timeout: 10000 })
  const folderCard = page.locator("div.rounded-lg.border", { hasText: "E2E Passkey Folder" }).first()
  await folderCard.waitFor({ timeout: 10000 })
  check("doc moved into the folder", (await folderCard.textContent()).includes(docName))

  // remove from folder + delete the folder (cleanup)
  await folderCard.hover()
  await folderCard.locator("button[title='Remove from folder']").click()
  await page.waitForTimeout(1200)
  const afterRemove = await folderCard.textContent()
  check("doc removed from folder", !afterRemove.includes(docName))
  console.log("  (folder left in place for inspection — delete via the API or UI)")
} catch (err) {
  failed++
  console.log(`  FAIL  harness error: ${err.message}`)
  await page.screenshot({ path: "/tmp/hermes-e2e-fail.png", fullPage: true }).catch(() => {})
  console.log("  (screenshot: /tmp/hermes-e2e-fail.png)")
} finally {
  await browser.close()
}

console.log(`\n${passed}/${passed + failed} E2E checks passed`)
process.exit(failed === 0 ? 0 : 1)
