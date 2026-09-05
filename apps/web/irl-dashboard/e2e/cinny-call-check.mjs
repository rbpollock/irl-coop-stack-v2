#!/usr/bin/env node
// E2E: check whether Cinny's room header shows the call (voice/video) button.
// Passkey login → open cinny.irl.coop → SSO (Keycloak session auto-completes,
// but the first-time Synapse consent screen needs "Continue") → room list →
// enter a room → inspect the header.
import { chromium } from "playwright"

const BASE = process.env.E2E_BASE_URL ?? "https://irl.coop"
const CINNY = process.env.E2E_CINNY_URL ?? "https://cinny.irl.coop"
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

  // 2. Cinny → SSO → consent (first time) → room list
  await page.goto(`${CINNY}/`, { waitUntil: "domcontentloaded", timeout: 45000 })
  await page.waitForTimeout(12000)

  // consent screen ("Continue to your account") — one-time, dismiss it
  const actionables = await page.evaluate(() =>
    Array.from(document.querySelectorAll("button, input[type=submit], a"))
      .filter((e) => /continue/i.test((e.textContent || e.value || "").slice(0, 40)))
      .map((e) => ({ tag: e.tagName, type: e.getAttribute("type"), text: (e.textContent || e.value || "").trim().slice(0, 30) }))
  )
  console.log("CONSENT ACTIONABLES:", JSON.stringify(actionables))
  if (actionables.length > 0) {
    const form = await page.evaluate(() => {
      const f = document.querySelector("form")
      const link = Array.from(document.querySelectorAll("a")).find((a) => /continue/i.test(a.textContent || ""))
      return {
        formAction: f?.getAttribute("action"),
        formMethod: f?.getAttribute("method"),
        linkHref: link?.getAttribute("href"),
        linkOnclick: link?.getAttribute("onclick"),
      }
    })
    console.log("CONSENT FORM:", JSON.stringify(form))
    if (form.linkHref && form.linkHref !== "#") {
      await page.goto(form.linkHref, { waitUntil: "domcontentloaded", timeout: 30000 })
      console.log("(navigated to consent link href)")
    }
    await page.waitForTimeout(10000)
  }

  console.log("cinny URL:", page.url().slice(0, 100))
  const body = await page.evaluate(() => document.body.innerText.slice(0, 500))
  console.log("BODY HEAD:", JSON.stringify(body))

  // 3. enter a room — click "General" (a known room in the list)
  const room = page.locator("text=General").first()
  if (await room.count() > 0) {
    await room.click()
    await page.waitForTimeout(4000)
    console.log("in-room URL:", page.url().slice(0, 100))
    const diag = await page.evaluate(async () => {
      const wk = await fetch("https://matrix.irl.coop/.well-known/matrix/client")
        .then((r) => r.json())
        .catch(() => null)
      const msc4143 = wk?.["org.matrix.msc4143.rtc_foci"]
      return {
        rtcFoci4143: msc4143 ? msc4143.map((f) => f.livekit_service_url) : null,
        rtcFoci4140: wk?.["org.matrix.msc4140.rtc_foci"] ? "present" : null,
        rtcPeer: "RTCPeerConnection" in window,
      }
    })
    console.log("DISCOVERY DIAG:", JSON.stringify(diag))
    const header = await page.evaluate(() =>
      Array.from(document.querySelectorAll("button[aria-label], button[title], [role='button'][aria-label]"))
        .map((b) => ({ label: b.getAttribute("aria-label") || b.getAttribute("title") || "", text: (b.textContent || "").trim().slice(0, 30) }))
    )
    console.log("HEADER BUTTONS:", JSON.stringify(header.slice(0, 40)))
    const hasCall = header.some((b) => /call|video|voice/i.test(b.label + b.text))
    console.log("CALL BUTTON PRESENT:", hasCall ? "YES" : "NO")
    await page.screenshot({ path: "/tmp/cinny-call-room.png", fullPage: false })
    console.log("(room screenshot: /tmp/cinny-call-room.png)")
  } else {
    console.log("no 'General' room found")
    await page.screenshot({ path: "/tmp/cinny-call-list.png", fullPage: false })
    console.log("(list screenshot: /tmp/cinny-call-list.png)")
  }
} catch (err) {
  console.log("ERROR:", err.message)
  await page.screenshot({ path: "/tmp/cinny-call-fail.png", fullPage: true }).catch(() => {})
  console.log("(fail screenshot: /tmp/cinny-call-fail.png)")
} finally {
  await browser.close()
}
