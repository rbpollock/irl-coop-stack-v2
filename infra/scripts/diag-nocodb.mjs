// Diagnostic: log into NocoDB as e2e-test and dump (a) console/page errors and
// (b) the full list of bases + tables the user can see — to find the "numerous
// errors" and the incomplete world-doc surface.
import { chromium } from "playwright"

const BASE = "https://irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const password = process.env.E2E_PASSWORD ?? ""

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()

const consoleLogs = []
const pageErrors = []
const badResponses = []

page.on("console", (m) => {
  if (m.type() === "error" || m.type() === "warning") consoleLogs.push(`[${m.type()}] ${m.text()}`)
})
page.on("pageerror", (e) => pageErrors.push(String(e)))
page.on("response", (r) => {
  if (r.status() >= 400) badResponses.push(`${r.status()} ${r.request().method()} ${r.request().url()}`)
})

try {
  await page.goto(`${BASE}/en/sign-in`, { waitUntil: "domcontentloaded", timeout: 30000 })
  await page.click("text=Sign in with a passkey")
  await page.waitForSelector("#username", { timeout: 30000 })
  await page.fill("#username", USER)
  await page.fill("#password", password)
  await page.click("input[type=submit]")
  await page.waitForURL(`${BASE}/**`, { timeout: 30000 })

  // now load NocoDB, capturing everything
  await page.goto("https://nocodb.irl.coop/", { waitUntil: "networkidle", timeout: 60000 })
  const token = await page.evaluate(() => JSON.parse(localStorage.getItem("nocodb-gui-v2")).token)

  const data = await page.evaluate(async ({ token }) => {
    async function api(path) {
      const res = await fetch(path, { headers: { "xc-auth": token } })
      let json = {}
      try { json = await res.json() } catch {}
      return { status: res.status, json }
    }

    // list bases
    const bases = await api("/api/v2/meta/bases")
    const out = { bases: [] }
    const baseList = bases.json.list || bases.json || []
    for (const b of baseList) {
      const entry = { id: b.id, title: b.title, type: b.type, tables: [] }
      // list tables in this base
      const tables = await api(`/api/v2/meta/bases/${b.id}/tables`)
      const tl = tables.json.list || (Array.isArray(tables.json) ? tables.json : [])
      entry.tables = tl.map((t) => ({ id: t.id, title: t.title, type: t.type }))
      out.bases.push(entry)
    }
    // also grab the workspaces probe the frontend uses
    out.workspaces = (await api("/api/v1/workspaces")).status
    return out
  }, { token })

  console.log("=== BASES + TABLES ===")
  console.log(JSON.stringify(data, null, 2))
  console.log("=== CONSOLE (error/warning) ===")
  console.log(consoleLogs.slice(0, 40).join("\n") || "(none)")
  console.log("=== PAGE ERRORS ===")
  console.log(pageErrors.slice(0, 20).join("\n") || "(none)")
  console.log("=== 4xx/5xx RESPONSES ===")
  console.log([...new Set(badResponses)].slice(0, 40).join("\n") || "(none)")
} catch (e) {
  console.error("ERR", e.message)
  console.error("=== console so far ===")
  console.error(consoleLogs.slice(0, 30).join("\n"))
  console.error("=== 4xx/5xx so far ===")
  console.error([...new Set(badResponses)].slice(0, 30).join("\n"))
  process.exit(1)
} finally {
  await browser.close()
}
