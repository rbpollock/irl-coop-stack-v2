// Create the shared "Coop" base as a LIVE external source over the irlcoop
// projection (groups / group_members / resource_scopes). Runs inside the
// browser-runner image (Playwright provides the Gate-SSO token + gate cookie).
// The Postgres connection config is read from env (set by the .sh wrapper) so
// the password never touches disk or the command line.
//
//   docker run --rm -v /tmp:/tmp -v <this file>:/app/create.mjs -w /app \
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

  const result = await page.evaluate(async ({ token, db }) => {
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

    // find-or-create the Coop base as an external pg source over irlcoop
    const bases = (await api("GET", "/api/v2/meta/bases")).json.list || []
    const existing = bases.find((b) => b.title === "Coop")
    if (existing) {
      const srcs = (await api("GET", `/api/v2/meta/bases/${existing.id}/sources`)).json.list || []
      return { baseId: existing.id, status: "exists", sources: srcs.map((s) => s.id) }
    }
    const created = await api("POST", "/api/v2/meta/bases", {
      title: "Coop",
      fk_workspace_id: "ws-default",
      external: true,
      sources: [
        {
          type: "pg",
          alias: "irlcoop",
          config: {
            client: "pg",
            connection: db,
            searchPath: ["public"],
          },
          inflection_column: "camelize",
          inflection_table: "camelize",
        },
      ],
    })
    return { status: created.status, json: created.json }
  }, { token, db })

  console.log(JSON.stringify(result, null, 2))
} catch (e) {
  console.error("ERR", e.message)
  process.exit(1)
} finally {
  await browser.close()
}
