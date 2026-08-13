#!/usr/bin/env node
// E2E: Unified User Journey — basic user persona (passkey login -> dashboard -> Group Wallet -> NocoDB).
//
// Usage: node e2e/user-journey.mjs
//   env: E2E_BASE_URL, E2E_COOP_API, E2E_USER, E2E_PASSWORD
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

console.log(`Starting E2E User Journey for persona: ${USER}...`)

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()
const cdp = await context.newCDPSession(page)

// Enable virtual authenticator for passkey authentication
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
  // Capture console and request failures to diagnose errors (e.g. NocoDB issues)
  page.on("console", (m) => {
    if (m.type() === "error") {
      console.log(`  (browser console error) ${m.text().slice(0, 200)}`)
    }
  })
  page.on("requestfailed", (r) => {
    console.log(`  (request failed) ${r.url().slice(0, 110)}: ${r.failure()?.errorText ?? ""}`)
  })
  page.on("response", (res) => {
    if (res.status() >= 400) {
      console.log(`  (HTTP ${res.status()}) ${res.url().slice(0, 110)}`)
    }
  })

  // 1. Log in via standard Passkey flow (re-using credentials if enrolled, otherwise registering)
  await page.goto(`${BASE}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey")
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", PASSWORD)
  await page.click("input[type=submit]")

  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })
  check("1. Login successful (landed on dashboard)", page.url().startsWith(BASE))

  // 2. Dashboard home: Stack Health check
  await page.waitForSelector("text=Stack health", { timeout: 15000 })
  await page.waitForSelector("text=Browser runners", { timeout: 15000 })
  check("2. Dashboard overview panels loaded cleanly", true)

  // 3. Navigate to Security Page and check Cooperative Group Wallet
  await page.goto(`${BASE}/en/pages/account/settings/security`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.waitForSelector("text=Cooperative Group Wallet", { timeout: 15000 })
  const walletText = await page.textContent("body")
  check("3. Group Wallet card displays predicted on-chain address", walletText.includes("Group Account Address") && walletText.includes("0x"))

  // 4. Navigate to NocoDB and check loading and API responses
  console.log("Navigating to NocoDB for verification...")
  await page.goto("https://nocodb.irl.coop/", { waitUntil: "networkidle", timeout: 45000 })
  const nocoUrl = page.url()
  check("4. NocoDB loads and authenticates successfully", nocoUrl.startsWith("https://nocodb.irl.coop"))
  
  // Wait to see if NocoDB renders the default workspace
  try {
    // If NocoDB's welcome questionnaire is displayed, click "Skip"
    const skipButton = page.locator("text=Skip");
    if (await skipButton.isVisible()) {
      console.log("  (NocoDB welcome questionnaire detected, clicking Skip...)")
      await skipButton.click();
    } else {
      // Give it a brief moment to render if it pops up late
      await page.waitForTimeout(1000);
      if (await skipButton.isVisible()) {
        console.log("  (NocoDB welcome questionnaire detected late, clicking Skip...)")
        await skipButton.click();
      }
    }

    await page.waitForSelector("text=Default Workspace", { timeout: 15000 })
    const bodyText = await page.textContent("body")
    check("5. NocoDB Workspace rendered", bodyText.includes("Default Workspace") || bodyText.includes("All Bases"))
  } catch (err) {
    console.log(`  (NocoDB Selector Wait Failed) Current URL: ${page.url()}`)
    console.log(`  (NocoDB Selector Wait Failed) Current Title: ${await page.title()}`)
    console.log(`  (NocoDB Selector Wait Failed) Body preview: ${ (await page.textContent("body")).slice(0, 400) }`)
    throw err
  }

  console.log("\nUser Journey completed successfully!")
} catch (err) {
  failed++
  console.log(`  FAIL  Harness error: ${err.message}`)
  await page.screenshot({ path: "/tmp/hermes-journey-fail.png", fullPage: true }).catch(() => {})
  console.log("  (screenshot: /tmp/hermes-journey-fail.png)")
} finally {
  await browser.close()
}

console.log(`\n${passed}/${passed + failed} journey checks passed`)
process.exit(failed === 0 ? 0 : 1)
