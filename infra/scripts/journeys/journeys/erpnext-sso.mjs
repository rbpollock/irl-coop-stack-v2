// ERPNext SSO journey: direct-grant → coop_session cookie → ERPNext custom
// Social Login Key (irlcoop) → gateway instant code → ERPNext session.
import { makeCtx } from "../lib.mjs"

export const name = "erpnext-sso"
export const description = "ERPNext (accounting.irl.coop) SSO via the fleet gateway irlcoop social login"

export async function run(ctx) {
  const browser = ctx.browser
  const context = await browser.newContext()
  const page = await context.newPage()
  const user = process.env.E2E_USER ?? "e2e-test@irl.coop"
  const password = process.env.E2E_PASSWORD ?? ""

  // 1) direct-grant on the api origin so the coop_session (.irl.coop) cookie
  // lands in this context (the instant path needs it)
  await page.goto("https://api.irl.coop/api/auth/config", {
    waitUntil: "domcontentloaded",
    timeout: 45000,
  })
  const loginStatus = await page.evaluate(
    async ({ u, p }) => {
      const r = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p }),
      })
      return r.status
    },
    { u: user, p: password }
  )
  ctx.check("direct-grant login (coop_session)", loginStatus === 200, `http ${loginStatus}`)

  // 2) ERPNext login page
  await page.goto("https://accounting.irl.coop/login", {
    waitUntil: "domcontentloaded",
    timeout: 45000,
  })
  await page.waitForTimeout(4000)
  const links = await page.evaluate(() =>
    [...document.querySelectorAll("a,button")]
      .map((el) => ({
        tag: el.tagName,
        text: (el.textContent || "").trim().slice(0, 50),
        href: el.href || "",
      }))
      .filter((x) => x.href.includes("oauth") || x.href.includes("authorize") || /irlcoop|social/i.test(x.text))
  )
  console.log("SOCIAL LINKS:", JSON.stringify(links).slice(0, 1200))

  // 3) click the irlcoop social entry
  const clicked = await page.evaluate(() => {
    const sels = [
      "a[href*='oauth2_logins.custom/irlcoop']",
      "a[href*='client_id=erpnext']",
      "a[href*='authorize']",
      "button:has-text('irlcoop')",
      "a:has-text('irlcoop')",
      ".btn-social",
    ]
    for (const s of sels) {
      const el = document.querySelector(s)
      if (el) {
        el.click()
        return s
      }
    }
    return null
  })
  ctx.check("social login link found + clicked", !!clicked, `selector: ${clicked ?? "none"}`)

  // 4) gateway instant code → frappe callback → ERPNext session
  try {
    await page.waitForURL(/accounting\.irl\.coop/, { timeout: 60000 })
  } catch (e) {
    console.log("URL wait:", String(e.message).slice(0, 150))
  }
  await page.waitForTimeout(8000)
  console.log("FINAL URL:", page.url())

  // 5) who does ERPNext think this is? (get_logged_user requires the session
  // cookie — the page has it after the SSO landing on /me)
  const who = await page.evaluate(async () => {
    const r = await fetch("/api/method/frappe.auth.get_logged_user")
    try {
      return await r.json()
    } catch {
      return { raw: (await r.text()).slice(0, 200) }
    }
  })
  console.log("GET_LOGGED_USER:", JSON.stringify(who).slice(0, 300))
  const loggedUser = who?.message
  ctx.check(
    "ERPNext session as the coop user (not Guest)",
    !!loggedUser && loggedUser !== "Guest",
    `user: ${loggedUser ?? "unknown"}`
  )

  await context.close()
}
