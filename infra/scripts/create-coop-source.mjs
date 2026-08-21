// Create + keep in sync the shared "Coop" NocoDB base as a LIVE external source
// over the irlcoop projection (groups / group_members / resource_scopes / events /
// notification_reads / notification_digests). Idempotent: find-or-create the base,
// then run a meta-diff sync so tables added to the DB AFTER first creation are
// introspected too. Runs inside the browser-runner image (Playwright provides the
// Gate-SSO token + gate cookie).
//
//   docker run --rm -v <this file>:/app/create.mjs -w /app \
//     -e E2E_USER=... -e E2E_PASSWORD=... -e COOP_DB_HOST=postgres \
//     -e COOP_DB_PORT=5432 -e COOP_DB_USER=coop -e COOP_DB_PASSWORD=... \
//     -e COOP_DB_NAME=irlcoop irlcoop/browser-runner node create.mjs
import { chromium } from "playwright"

const BASE = "https://irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const password = process.env.E2E_PASSWORD ?? ""
const db = {
  host: process.env.COOP_DB_HOST ?? "postgres",
  port: process.env.COOP_DB_PORT ?? "5432",
  user: process.env.COOP_DB_USER ?? "coop",
  password: process.env.COOP_DB_PASSWORD ?? "",
  database: process.env.COOP_DB_NAME ?? "irlcoop",
}

// The complete projection surface — every table the coop-api self-provisions.
const EXPECTED = ["groups", "group_members", "resource_scopes", "events", "notification_reads", "notification_digests"]

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

  const result = await page.evaluate(async ({ token, db, EXPECTED }) => {
    async function api(method, path, body) {
      const res = await fetch(path, {
        method,
        headers: { "Content-Type": "application/json", "xc-auth": token },
        body: body ? JSON.stringify(body) : undefined,
      })
      const text = await res.text()
      let json
      try { json = JSON.parse(text) } catch { json = { _raw: text.slice(0, 400) } }
      return { status: res.status, json }
    }
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

    // 1. find-or-create the Coop base
    const bases = (await api("GET", "/api/v2/meta/bases")).json.list || []
    let base = bases.find((b) => b.title === "Coop")
    let created = false
    if (!base) {
      const c = await api("POST", "/api/v2/meta/bases", {
        title: "Coop",
        fk_workspace_id: "ws-default",
        external: true,
        sources: [
          {
            type: "pg",
            alias: "irlcoop",
            config: { client: "pg", connection: db, searchPath: ["public"] },
            inflection_column: "camelize",
            inflection_table: "camelize",
          },
        ],
      })
      base = c.json
      created = true
      await sleep(3000) // let the initial introspection finish
    }
    const baseId = base.id

    // 2. resolve the source id
    const sources = (await api("GET", `/api/v2/meta/bases/${baseId}/sources`)).json.list || []
    const sourceId = sources[0]?.id

    // 3. sync metadata (adds any tables created since last introspection)
    let sync = null
    if (sourceId) {
      sync = await api("POST", `/api/v2/meta/bases/${baseId}/meta-diff/${sourceId}`)
    }

    // 4. poll for the complete table set
    let tables = []
    for (let i = 0; i < 20; i++) {
      await sleep(2000)
      const t = await api("GET", `/api/v2/meta/bases/${baseId}/tables`)
      tables = t.json.list || []
      const names = tables.map((x) => x.title?.toLowerCase?.() ?? "")
      const missing = EXPECTED.filter((e) => !names.includes(e) && !tables.some((x) => (x.table_name || "").toLowerCase() === e))
      if (missing.length === 0) break
    }

    return {
      created,
      baseId,
      sourceId,
      syncStatus: sync?.status,
      tables: tables.map((t) => ({ title: t.title, table_name: t.table_name, type: t.type })),
    }
  }, { token, db, EXPECTED })

  console.log(JSON.stringify(result, null, 2))
} catch (e) {
  console.error("ERR", e.message)
  process.exit(1)
} finally {
  await browser.close()
}
