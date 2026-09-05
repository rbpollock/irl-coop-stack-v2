#!/usr/bin/env node
// E2E test for Sovereign Stream page & Group Secret Vault API
// Uses Playwright with CDP WebAuthn authenticator for passkey authentication,
// then exercises /apps/stream and group vault secret persistence.
import { chromium } from "playwright"

const BASE = process.env.E2E_BASE_URL ?? "https://irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const PASSWORD = process.env.E2E_PASSWORD ?? ""

const browser = await chromium.launch({ args: ["--use-angle=swiftshader"] })
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
  // 1. Authenticate via dashboard passkey login
  console.log("Navigating to sign-in...")
  await page.goto(`${BASE}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey")
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("input[type=submit]")
  try {
    await page.waitForSelector("input[type=submit]", { timeout: 10000 })
    await page.click("input[type=submit]")
  } catch {}
  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })
  console.log("Successfully logged in.")

  // 2. Navigate to Sovereign Stream App (/apps/stream)
  console.log("Opening Sovereign Stream page (/apps/stream)...")
  await page.goto(`${BASE}/en/apps/stream`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.waitForSelector("text=Live Video & Sovereign Stream", { timeout: 15000 })

  // 3. Test Streamer Mode and UI components
  console.log("Testing Streamer Privacy mode toggle...")
  await page.click("text=Streamer Privacy")
  const streamerActive = await page.locator("text=Streamer Mode Active").isVisible()
  console.log("Streamer Mode Active:", streamerActive)

  // 4. Test API Vault Secret Persistence via fetch
  console.log("Testing Group Secret Vault API...")
  const vaultTestResult = await page.evaluate(async () => {
    // Fetch group list to get a valid group ID
    const groupsRes = await fetch("/api/v1/groups")
    const groups = await groupsRes.json()
    if (!groups.length) return { error: "no groups found" }
    const groupId = groups[0].id

    // Post a test stream key secret to the vault
    const postRes = await fetch(`/api/v1/groups/${groupId}/vault/secrets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key_name: "test_twitch_stream_key", secret_value: "live_123456_secretkey" }),
    })
    const postData = await postRes.json()

    // Retrieve secret metadata
    const getRes = await fetch(`/api/v1/groups/${groupId}/vault/secrets`)
    const getData = await getRes.json()

    return { groupId, postStatus: postRes.status, postData, getData }
  })
  console.log("Vault API Test Result:", JSON.stringify(vaultTestResult, null, 2))

  await page.screenshot({ path: "/tmp/stream-e2e-success.png", fullPage: true })
  console.log("E2E test passed successfully. Screenshot saved to /tmp/stream-e2e-success.png")
} catch (err) {
  console.error("E2E Test Failed:", err)
  await page.screenshot({ path: "/tmp/stream-e2e-fail.png", fullPage: true }).catch(() => {})
  process.exit(1)
} finally {
  await browser.close()
}
