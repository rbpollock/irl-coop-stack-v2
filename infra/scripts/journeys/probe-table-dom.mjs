import { chromium } from 'playwright'
import { env } from './lib.mjs'

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()

const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text().slice(0, 250)) })
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + String(e).slice(0, 300)))
page.on('response', async (r) => {
  if (r.status() >= 400 && !r.url().includes('socket.io')) {
    let body = ''
    try { body = (await r.text()).slice(0, 300) } catch {}
    errors.push(`${r.status()} ${r.request().method()} ${r.url().replace('https://nocodb.irl.coop','')} :: ${body}`)
  }
})

await page.goto(`${env.web}/en/sign-in`, { waitUntil: 'domcontentloaded', timeout: 30000 })
await page.click('text=Sign in with a passkey')
await page.waitForSelector('#username', { timeout: 30000 })
await page.fill('#username', env.user)
await page.fill('#password', env.password)
await page.click('input[type=submit]')
await page.waitForURL(`${env.web}/**`, { timeout: 30000 })
await page.goto(env.nocodb + '/', { waitUntil: 'domcontentloaded', timeout: 45000 })
await page.waitForTimeout(8000)
await page.click('.nc-base-node:has-text("E2E Tester")', { timeout: 15000 })
await page.waitForTimeout(7000)

// Dump the DOM chain of the "Groups" table node
const chain = await page.evaluate(() => {
  const el = Array.from(document.querySelectorAll('*')).find(e =>
    e.textContent?.trim() === 'Groups' && e.children.length === 0 && e.offsetParent !== null)
  if (!el) return 'NOT FOUND'
  let node = el
  const out = []
  for (let i = 0; i < 10 && node; i++) {
    out.push(`${node.tagName}.${(node.className||'').toString().slice(0,80)} | data-testid=${node.getAttribute('data-testid')||''} | clickable-fns=${typeof node.onclick}`)
    node = node.parentElement
  }
  return out.join('\n  <- ')
})
console.log('GROUPS NODE CHAIN:\n', chain)

await browser.close()
