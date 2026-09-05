#!/usr/bin/env node
// E2E: Element integration through the dashboard /apps/chat iframe.
//
// Logs in with a passkey (same deterministic WebAuthn flow as farm-flow),
// opens the dashboard's Video & Chat page, then reports the iframe's real
// geometry + the viewport so the "looks weird" layout bug is diagnosable
// without a human eyeball: src, bounding box, header height, scroll overflow.
import { chromium } from "playwright"

const BASE = process.env.E2E_BASE_URL ?? "https://irl.coop"
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
const consoleErrors = []
const pageErrors = []
page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text())
})
page.on("pageerror", (err) => pageErrors.push(String(err)))
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
  // --- 1. passkey login ---
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

  // --- 2. /apps/chat + the Element iframe ---
  await page.goto(`${BASE}/en/apps/chat`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.waitForTimeout(15000) // Element SSO + shell load

  const viewport = page.viewportSize()
  console.log(`  (viewport: ${JSON.stringify(viewport)})`)

  const diag = await page.evaluate(() => {
    const f = document.querySelector("iframe")
    if (!f) return { iframe: null }
    const r = f.getBoundingClientRect()
    return {
      src: f.src,
      box: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
      clientH: document.documentElement.clientHeight,
      scrollH: document.documentElement.scrollHeight,
      bodyScrollH: document.body.scrollHeight,
      // find the header + content heights
      header: (() => {
        const h = document.querySelector("header")
        return h ? Math.round(h.getBoundingClientRect().height) : null
      })(),
    }
  })
  console.log(`  (iframe diag: ${JSON.stringify(diag, null, 2)})`)

  check("dashboard /apps/chat iframes Cinny", diag.src?.startsWith("https://cinny.irl.coop") ?? false, String(diag.src))
  if (diag.iframe) {
    // The iframe should roughly fill the viewport height (minus header) — a
    // mismatch here is the "looks weird" (too short / overflowing).
    const expectedH = (viewport?.height ?? 800) - (diag.header ?? 0)
    const fills = Math.abs(diag.box.h - expectedH) < 60
    console.log(`  (expected iframe height ~${expectedH}, got ${diag.box.h})`)
    check("iframe fills the content height", fills, `expected ~${expectedH}, got ${diag.box.h}`)
    check("no vertical scroll overflow", diag.scrollH <= (viewport?.height ?? 800) + 2, `scrollH=${diag.scrollH} vs viewport ${viewport?.height}`)
  }

  await page.screenshot({ path: "/tmp/chat-e2e.png", fullPage: false }).catch(() => {})
  console.log("  (screenshot: /tmp/chat-e2e.png)")
  const visible = await page.evaluate(() => document.body.innerText.slice(0, 500))
  console.log(`  (page text: ${JSON.stringify(visible)})`)
  console.log(`  (console errors: ${JSON.stringify(consoleErrors.slice(0, 10))})`)
  console.log(`  (page errors: ${JSON.stringify(pageErrors.slice(0, 10))})`)
} catch (err) {
  failed++
  console.log(`  FAIL  harness error: ${err.message}`)
  await page.screenshot({ path: "/tmp/chat-e2e-fail.png", fullPage: true }).catch(() => {})
} finally {
  await browser.close()
}

console.log(`\n${passed}/${passed + failed} E2E checks passed`)
process.exit(failed === 0 ? 0 : 1)
