// Apply group-membership -> base-access grants (emit from sync-base-members.py).
// Idempotent: POST /api/v2/meta/bases/:id/users is rejected with 422 "already
// exists" for existing members and 422 "At least one owner is required" for the
// base's own owner — both are safe no-ops. Runs in browser-runner (gate token).
import { chromium } from "playwright"

const BASE = "https://irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const password = process.env.E2E_PASSWORD ?? ""
const grants = JSON.parse(process.env.GRANTS_JSON ?? "[]")

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()
try {
  await page.goto(`${BASE}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey")
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", password)
  await page.click("input[type=submit]")
  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })
  await page.goto("https://nocodb.irl.coop/", { waitUntil: "networkidle", timeout: 45000 })
  const token = await page.evaluate(() => JSON.parse(localStorage.getItem("nocodb-gui-v2")).token)

  const out = await page.evaluate(async ({ token, grants }) => {
    const api = async (method, path, body) => {
      const res = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json", "xc-auth": token },
        body: body ? JSON.stringify(body) : undefined,
      })
      const t = await res.text()
      let j
      try { j = JSON.parse(t) } catch { j = { _raw: t.slice(0, 300) } }
      return { status: res.status, json: j }
    }
    const results = []
    for (const g of grants) {
      const r = await api("POST", `/api/v2/meta/bases/${g.base_id}/users`, {
        email: g.email,
        roles: g.role,
      })
      results.push({ base: g.base_id, email: g.email, role: g.role, status: r.status })
    }
    return results
  }, { token, grants })

  const ok = out.filter((r) => r.status === 200)
  const skipped = out.filter((r) => r.status !== 200)
  console.log(JSON.stringify({ granted: ok.length, skipped: skipped.length, detail: out }, null, 2))
} catch (e) {
  console.error("ERR", e.message)
  process.exit(1)
} finally {
  await browser.close()
}
