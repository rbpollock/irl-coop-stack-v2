#!/usr/bin/env node
// E2E: passkey login, then capture the gated irl.coop surfaces as screenshots
// for the session-story recap (needs/offers, calls, dashboard). Mirror of
// cinny-call-check / user-journey auth. Env: E2E_BASE_URL, E2E_USER, E2E_PASSWORD.
import { chromium } from "playwright"
import { mkdirSync } from "node:fs"

const BASE = process.env.E2E_BASE_URL ?? "https://irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const PASSWORD = process.env.E2E_PASSWORD ?? ""
const OUT = process.env.E2E_OUT_DIR ?? "/tmp/e2e_caps"

const targets = [
  ["needs-effers", "/en/dashboards/needs-offers"],
  ["calls", "/en/apps/calls"],
  ["dashboard", "/en"],
  ["design", "/en/design"],
]

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1080, height: 1600 } })
const page = await context.newPage()
const cdp = await context.newCDPSession(page)
await cdp.send("WebAuthn.enable", { enableUI: false })
await cdp.send("WebAuthn.addVirtualAuthenticator", {
  options: {
    protocol: "ctap2", transport: "internal", hasResidentKey: true,
    hasUserVerification: true, isUserVerified: true,
    automaticPresenceSimulation: true,
  },
})

mkdirSync(OUT, { recursive: true })
try {
  // passkey login into the fleet
  await page.goto(`${BASE}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey").catch(() => {})
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("input[type=submit]")
  try { await page.waitForSelector("input[type=submit]", { timeout: 15000 }); await page.click("input[type=submit]") } catch {}
  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })

  for (const [name, path] of targets) {
    await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 45000 })
    await page.waitForTimeout(4000)
    const file = `${OUT}/${name}.png`
    await page.screenshot({ path: file })
    console.log(`captured ${name} -> ${file} (url ${page.url().slice(0, 60)})`)
  }
} catch (err) {
  console.error("E2E error:", err.message)
  await page.screenshot({ path: `${OUT}/fail.png`, fullPage: true }).catch(() => {})
} finally {
  await browser.close()
}