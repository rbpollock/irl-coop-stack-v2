// Verify the WRITE path through NocoDB: log in as e2e-test (owner of "Cold
// Storage Co-op") and PATCH the group's description. If app.sub is injected on
// the write path, the RLS UPDATE policy (coop_is_owner) passes and the row
// changes; otherwise the update is silently filtered (0 rows) or errors.
import { chromium } from "playwright"

const BASE = "https://irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const password = process.env.E2E_PASSWORD ?? ""
const GROUPS = "mpi01cdb2jofe2r"

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

  const result = await page.evaluate(async ({ token, GROUPS }) => {
    const api = async (method, path, body) => {
      const res = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json", "xc-auth": token },
        body: body ? JSON.stringify(body) : undefined,
      })
      let json = {}
      try { json = await res.json() } catch {}
      return { status: res.status, json }
    }
    const read = async () => {
      const r = await api("GET", `/api/v2/tables/${GROUPS}/records`)
      return r.json.list || []
    }
    const rows = await read()
    const cold = rows.find((x) => x.Name === "Cold Storage Co-op")
    if (!cold) return { error: "Cold Storage Co-op not found", rows: rows.length }
    const id = cold.Id
    const before = cold.Description ?? null
    const target = "write-test-" + Date.now()
    const up = await api("PATCH", `/api/v2/tables/${GROUPS}/records`, [{ Id: id, Description: target }])
    const after = (await read()).find((x) => x.Id === id)
    const changed = after && after.Description === target
    // restore
    await api("PATCH", `/api/v2/tables/${GROUPS}/records`, [{ Id: id, Description: before ?? "" }])
    return {
      id,
      before,
      patchStatus: up.status,
      changed,
      writePath: changed ? "WORKS (app.sub injected on write)" : "FAILS (app.sub missing on write path)",
    }
  }, { token, GROUPS })

  console.log(JSON.stringify(result, null, 2))
} catch (e) {
  console.error("ERR", e.message)
  process.exit(1)
} finally {
  await browser.close()
}
