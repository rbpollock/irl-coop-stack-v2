// Seed NocoDB with prepopulated bases from the live projection (groups,
// members, resources, projects). Run inside the browser-runner image — the
// Playwright browser provides the Gate-SSO token + _oauth2_proxy cookie that
// the NocoDB API requires. Reads seed data from /tmp/nocodb-seed-data.json
// (see infra/scripts/seed-nocodb-bases.sh for the data-read + base-user link).
//
//   docker run --rm -v /tmp:/tmp -e E2E_USER=e2e-test@irl.coop \
//     -e E2E_PASSWORD=<derived> irlcoop/browser-runner node infra/scripts/seed-nocodb-bases.mjs
import { chromium } from "playwright"
import { readFileSync } from "node:fs"

const BASE = "https://irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const password = process.env.E2E_PASSWORD ?? ""
const data = JSON.parse(readFileSync("/tmp/nocodb-seed-data.json", "utf8"))

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

  const log = await page.evaluate(async ({ token, data }) => {
    const out = []
    async function api(method, path, body) {
      const res = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json", "xc-auth": token },
        body: body ? JSON.stringify(body) : undefined,
      })
      const text = await res.text()
      let json; try { json = JSON.parse(text) } catch { json = { _raw: text.slice(0, 200) } }
      return { status: res.status, json }
    }
    const bases = (await api("GET", "/api/v2/meta/bases")).json.list || []
    async function findOrCreateBase(title) {
      const found = bases.find((b) => b.title === title)
      if (found) return found.id
      return (await api("POST", "/api/v2/meta/bases", { title, fk_workspace_id: "ws-default" })).json.id
    }
    async function findOrCreateTable(baseId, title, columns) {
      const tl = (await api("GET", `/api/v2/meta/bases/${baseId}/tables`)).json.list || []
      const found = tl.find((t) => t.title === title)
      if (found) return found.id
      return (await api("POST", `/api/v2/meta/bases/${baseId}/tables`, {
        title, columns: columns.map((c) => ({ title: c, uidt: "SingleLineText" })),
      })).json.id
    }

    const b1 = await findOrCreateBase("Coop Groups")
    for (const [t, cols, rows] of [
      ["Groups", ["Name", "Safe Address", "Privacy", "Description"], data.groups],
      ["Members", ["Group", "Sub", "Roles", "Alias", "Visibility"], data.members],
      ["Resources", ["Group", "App", "Resource Key"], data.resources],
    ]) {
      const tid = await findOrCreateTable(b1, t, cols)
      const rr = await api("POST", `/api/v2/tables/${tid}/records`, rows)
      out.push(`${t}: ${rows.length} rows -> ${rr.status}`)
    }
    const b2 = await findOrCreateBase("Projects")
    const ptid = await findOrCreateTable(b2, "Projects", ["Name", "Identifier", "Visibility", "Safe Address"])
    const pr = await api("POST", `/api/v2/tables/${ptid}/records`, data.projects)
    out.push(`Projects: ${data.projects.length} rows -> ${pr.status}`)
    out.push(`bases: ${b1}, ${b2}`)
    return out
  }, { token, data })

  console.log(log.join("\n"))
} catch (e) {
  console.error("ERR", e.message)
  process.exit(1)
} finally {
  await browser.close()
}
