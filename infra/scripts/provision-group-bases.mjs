// B1: provision one NocoDB base per collective group. Each base is a live external
// source over its per-group schema (grp_<hex>), searchPath [schema, public] so the
// narrowed views resolve first and the RLS helpers resolve from public.
//
//   docker run --rm -v <this>:/app/provision.mjs -w /app \
//     -e E2E_USER=... -e E2E_PASSWORD=... -e COOP_DB_PASSWORD=... \
//     -e GROUPS_JSON='[...]' irlcoop/browser-runner node provision.mjs
import { chromium } from "playwright"

const BASE = "https://irl.coop"
const USER = process.env.E2E_USER ?? "e2e-test@irl.coop"
const password = process.env.E2E_PASSWORD ?? ""
const groups = JSON.parse(process.env.GROUPS_JSON ?? "[]")
const db = {
  host: process.env.COOP_DB_HOST ?? "postgres",
  port: process.env.COOP_DB_PORT ?? "5432",
  user: process.env.COOP_DB_USER ?? "coop",
  password: process.env.COOP_DB_PASSWORD ?? "",
  database: process.env.COOP_DB_NAME ?? "irlcoop",
}

// NocoDB base-title validator allows letters, numbers, spaces, hyphens, underscores,
// periods, parentheses, ampersands, commas, apostrophes. Group names are user-chosen
// (em-dash, "!!", etc.), so sanitize to that set. Fall back to the slug if empty.
function sanitizeTitle(name, slug) {
  const cleaned = String(name ?? "")
    .replace(/[^A-Za-z0-9 \-_.()&,']/g, " ")
    .replace(/\s+/g, " ")
    .trim()
  return cleaned || slug || "Group"
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

  const result = await page.evaluate(async ({ token, db, groups }) => {
    const sanitizeTitle = (name, slug) => {
      const cleaned = String(name ?? "")
        .replace(/[^A-Za-z0-9 \-_.()&,']/g, " ")
        .replace(/\s+/g, " ")
        .trim()
      return cleaned || slug || "Group"
    }
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

    const bases = (await api("GET", "/api/v2/meta/bases")).json.list || []
    const out = []
    for (const g of groups) {
      const title = sanitizeTitle(g.name, g.slug)
      const existing = bases.find((b) => b.title === title)
      if (existing) {
        out.push({ group: g.name, title, status: "exists", baseId: existing.id })
        continue
      }
      const c = await api("POST", "/api/v2/meta/bases", {
        title,
        fk_workspace_id: "ws-default",
        external: true,
        sources: [
          {
            type: "pg",
            alias: g.schema,
            config: { client: "pg", connection: db, searchPath: [g.schema, "public"] },
            inflection_column: "camelize",
            inflection_table: "camelize",
          },
        ],
      })
      out.push({ group: g.name, status: c.status, baseId: c.json?.id, err: c.json?._raw ?? c.json?.message })
      await sleep(2500) // let introspection settle between creates
    }
    return out
  }, { token, db, groups })

  console.log(JSON.stringify(result, null, 2))
} catch (e) {
  console.error("ERR", e.message)
  process.exit(1)
} finally {
  await browser.close()
}
