// Journey: "Search surfaces public groups + docs" — an anonymous guest can search
// public content and results link to their destinations (group pages / design docs).
import { env } from "../lib.mjs"

export const name = "search"
export const description = "Anonymous search finds public groups + docs and links to their destinations"

export async function run(ctx) {
  // 1. Backend: anonymous /mcp is accepted (no 401) and exposes the RAG tools.
  const mcp = await ctx.api("POST", "/mcp", {
    body: { jsonrpc: "2.0", id: 1, method: "tools/list", params: {} },
  })
  ctx.check("anonymous /mcp tools/list is accepted (200)", mcp.status === 200, `status=${mcp.status}`)
  const toolNames = mcp.json?.result?.tools?.map((t) => t.name) ?? []
  ctx.check(
    "anonymous tools expose rag.retrieve_area_contexts",
    toolNames.includes("rag.retrieve_area_contexts"),
    toolNames.join(","),
  )

  // 2. UI: anonymous search on /design in a fresh (cookie-less) context.
  const context = await ctx.browser.newContext()
  const page = await context.newPage()
  try {
    await page.goto(`${env.web}/design`, { waitUntil: "domcontentloaded", timeout: 30000 })
    const hasInput = await page
      .waitForSelector("input[placeholder]", { timeout: 15000 })
      .then(() => true)
      .catch(() => false)
    ctx.check("search box renders on /design", hasInput)
    if (!hasInput) return

    // Group search → a link to a /groups/<slug> page (locale-prefixed).
    await page.fill("input[placeholder]", "food cooperative kitchen market")
    await page.click("button[type=submit]")
    await page.waitForSelector("a[href*='/groups/']", { timeout: 20000 }).catch(() => {})
    const groupLinks = await page.$$eval("a[href*='/groups/']", (els) => els.map((e) => e.getAttribute("href")))
    ctx.check("group search returns a /groups/ link", groupLinks.length > 0, [...new Set(groupLinks)].join(","))

    // Doc search → a treasury passage.
    await page.fill("input[placeholder]", "how does a group Safe treasury work")
    await page.click("button[type=submit]")
    await page.waitForFunction(() => document.body.innerText.includes("treasury"), { timeout: 20000 }).catch(() => {})
    const bodyText = await page.textContent("body")
    ctx.check("doc search returns a treasury passage", bodyText.includes("treasury"))
  } finally {
    await context.close()
  }
}
