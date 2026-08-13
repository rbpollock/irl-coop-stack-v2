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
  // --- 1. passkey login: the full-kit sign-in → the passkey provider ---
  // (the NextAuth's OWN authorize carries the state + csrf; a direct
  // gateway authorize bypasses them and the OAuth callback fails)
  await page.goto(`${BASE}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey")

  // the Keycloak login page (the browser-passkey copy): username + password.
  // The password is the SECONDARY mechanism here (Google for real members);
  // once enrolled, the passkey ceremony replaces this leg.
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("input[type=submit]")

  // first login: the WebAuthn registration page (the required action) — the
  // virtual authenticator creates the credential on the click
  try {
    await page.waitForSelector("input[type=submit]", { timeout: 15000 })
    await page.click("input[type=submit]")
    console.log("  (enrolled a fresh passkey via the registration ceremony)")
  } catch {
    /* already enrolled — the session proceeds */
  }

  // the ceremony completes → the gateway callback → the dashboard session
  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })
  const cookies = await context.cookies(`${BASE}/`)
  console.log(`  (cookies: ${cookies.map((c) => c.name).join(",") || "none"} | url: ${page.url()})`)
  check("passkey login lands on the dashboard", page.url().startsWith(BASE) && !page.url().includes("sign-in"))
  check("session cookie set", cookies.some((c) => c.name.includes("session-token")))
  await page.waitForSelector("text=Browser runners", { timeout: 20000 })
  check("browser runners panel on the home page", true)

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
  // create a document — the response promise first, the trigger + the
  // dropdown selection AFTER (Promise.all would block on the response and
  // the selection never runs)
  const respPromise = page.waitForResponse(
    (r) => r.url().includes("/api/v1/docs/new") && r.request().method() === "POST",
  )
  await page.click("button:has-text('New')")
  // the menu is a custom div of plain buttons (not Radix — no keyboard
  // nav); scope to the open menu's container and pick "Document"
  await page.click("div.absolute.right-0.top-full button:has-text('Document')")
  const resp = await respPromise
  const docName = (await resp.json()).name
  check("document created", !!docName, docName)

  // back to the list, then move the doc into the folder (the pointer-only
  // membership — the files API lives on the coop-api origin and wants the
  // Bearer JWT, which the page exposes via its session endpoint)
  await page.click("text=Back to documents")
  const token = await page.evaluate(async () => {
    const res = await fetch("/api/auth/session")
    const s = await res.json()
    return s?.accessToken ?? ""
  })
  const filesRes = await fetch(`${COOP_API}/api/v1/files`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  const { folders } = await filesRes.json()
  const folder = folders.find((f) => f.name === "E2E Passkey Folder")
  check("folder found via the API", !!folder)
  const moveRes = await fetch(`${COOP_API}/api/v1/files/folders/${folder.id}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ source: "docs", key: docName }),
  })
  check("doc moved into the folder", moveRes.ok, moveRes.status)

  // remove from folder (cleanup; the folder stays for inspection)
  const removeRes = await fetch(
    `${COOP_API}/api/v1/files/folders/${folder.id}/members?source=docs&key=${encodeURIComponent(docName)}`,
    { method: "DELETE", headers: { Authorization: `Bearer ${token}` } },
  )
  check("doc removed from folder", removeRes.ok, removeRes.status)
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
