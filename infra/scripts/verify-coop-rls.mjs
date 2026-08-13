// Verify per-user RLS scoping through NocoDB: log in as one user and read the
// three projection tables through the external "Coop" source. Row counts must
// reflect the caller's identity (app.sub injected by the 2026.08.4 bundle).
import { chromium } from "playwright"

const BASE = "https://irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const password = process.env.E2E_PASSWORD ?? ""

const MODELS = {
  Groups: "mpi01cdb2jofe2r",
  GroupMembers: "mcnruikf0y0q8j6",
  ResourceScopes: "mkwgndioz3juf8u",
}

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

  const result = await page.evaluate(async ({ token, MODELS }) => {
    async function api(path) {
      const res = await fetch(path, { headers: { "xc-auth": token } })
      let json = {}
      try { json = await res.json() } catch {}
      return { status: res.status, json }
    }
    const out = {}
    for (const [name, modelId] of Object.entries(MODELS)) {
      const r = await api(`/api/v2/tables/${modelId}/records`)
      const list = r.json.list || []
      out[name] = {
        status: r.status,
        count: list.length,
        names: list.slice(0, 6).map((x) => x.Name || x.Group || x.App || x.ResourceKey || Object.keys(x).join(",")),
      }
    }
    return out
  }, { token, MODELS })

  console.log(JSON.stringify(result, null, 2))
} catch (e) {
  console.error("ERR", e.message)
  process.exit(1)
} finally {
  await browser.close()
}
