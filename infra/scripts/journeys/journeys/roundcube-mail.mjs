// Journey: "A member uses webmail" — Roundcube via the OAuth gateway. The shared
// passkey session already set the coop_session cookie on .irl.coop, so the
// webmail → api.irl.coop/authorize hop resolves to an INSTANT code (no Keycloak
// page) and lands back logged in. Then: list renders, compose opens, folder
// navigation. This is the gate for the shadcn-mail skin — it must pass
// identically on elastic and shadcn-mail.
import { env } from "../lib.mjs"

export const name = "roundcube-mail"
export const description = "A member uses webmail: OAuth login, list, compose, folder navigation"

export async function run(ctx) {
  const page = ctx.nocodb?.page
  if (!page) {
    ctx.check("browser session for webmail", false, "no browser session")
    return
  }

  // 1. OAuth login: the coop_session cookie → instant code → back on webmail.
  await page.goto(env.webmail + "/", { waitUntil: "domcontentloaded", timeout: 45000 })
  await page.waitForURL(/webmail\./, { timeout: 45000 }).catch(() => {})
  await page.waitForTimeout(4000)
  await page.waitForSelector("#messagelist, #mailboxlist", { timeout: 30000 }).catch(() => {})

  const url = page.url()
  const landed = /webmail\./.test(url) && !/(login\/oauth|_task=login|authorize|error)/i.test(url)
  ctx.check("OAuth login lands on the mailbox", landed, url)

  // 2. message list + folder list render
  const list = await page.evaluate(() => ({
    messagelist: !!document.querySelector("#messagelist"),
    mailboxlist: !!document.querySelector("#mailboxlist"),
    compose: /compose/i.test(document.body.innerText || ""),
  }))
  ctx.check("message list + folder list render", list.messagelist && list.mailboxlist, JSON.stringify(list))

  // 3. compose opens (subject field + send button)
  const compose = page.locator("a.compose").first()
  const hasCompose = await compose.count() > 0
  ctx.check("compose button present", hasCompose, hasCompose ? "present" : "missing")
  if (hasCompose) {
    await compose.click().catch(() => {})
    await page.waitForTimeout(4000)
    const c = await page.evaluate(() => ({
      subject: !!document.querySelector("#compose-subject"),
      send: /send/i.test(document.body.innerText || ""),
    }))
    ctx.check("compose form opens (subject + send)", c.subject && c.send, JSON.stringify(c))

    // back to the mailbox for the folder-nav check
    await page.goto(env.webmail + "/?_task=mail", { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {})
    await page.waitForTimeout(3000)
  }

  // 4. folder navigation — click Sent and confirm the mailbox changes
  const sent = page.locator("#mailboxlist a:has-text('Sent')").first()
  const hasSent = await sent.count() > 0
  ctx.check("Sent folder present", hasSent, hasSent ? "present" : "missing")
  if (hasSent) {
    await sent.click().catch(() => {})
    await page.waitForTimeout(4000)
    const nav = /Sent/i.test(page.url())
    ctx.check("folder navigation to Sent", nav, page.url())
  }
}
