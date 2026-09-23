import { chromium } from 'playwright'
import { env } from './lib.mjs'

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()

await page.goto(`${env.web}/en/sign-in`, { waitUntil: 'domcontentloaded', timeout: 30000 })
await page.click('text=Sign in with a passkey')
await page.waitForSelector('#username', { timeout: 30000 })
await page.fill('#username', env.user)
await page.fill('#password', env.password)
await page.click('input[type=submit]')
await page.waitForURL(`${env.web}/**`, { timeout: 30000 })
await page.goto(env.nocodb + '/', { waitUntil: 'domcontentloaded', timeout: 45000 })
await page.waitForTimeout(8000)

// Find the element containing a known base title, walk up to its clickable card, dump its outerHTML (truncated)
const html = await page.evaluate(() => {
  const el = Array.from(document.querySelectorAll('*')).find(e =>
    e.textContent?.trim() === 'Coop' && e.children.length === 0)
  if (!el) return 'NOT FOUND: Coop'
  // walk up 6 levels to find the card
  let node = el
  let chain = []
  for (let i = 0; i < 8 && node; i++) {
    chain.push(`${node.tagName}.${(node.className||'').toString().slice(0,60)}`)
    node = node.parentElement
  }
  return chain.join('\n  <- ')
})
console.log('COOP CARD CHAIN:\n', html)

await browser.close()
