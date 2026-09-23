import { chromium } from 'playwright'
import { env } from './lib.mjs'

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()

const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text().slice(0, 300)) })
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + String(e).slice(0, 400)))
page.on('response', async (r) => {
  if (r.status() >= 400 && !r.url().includes('socket.io')) {
    let body = ''
    try { body = (await r.text()).slice(0, 500) } catch {}
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

// Open the shared "Coop" base
await page.click('.nc-base-node:has-text("Coop")', { timeout: 15000 })
await page.waitForTimeout(9000)
console.log('URL:', page.url())

// list table side nodes
const tables = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('[data-testid^="nc-tbl-side-node-"]'))
    .map(e => e.getAttribute('data-testid').replace('nc-tbl-side-node-','')).slice(0, 40)
})
console.log('COOP TABLES:', JSON.stringify(tables))

// click the first table if present
if (tables.length > 0) {
  const first = tables[0]
  await page.click(`[data-testid="nc-tbl-side-node-${first}"]`, { timeout: 15000 })
  await page.waitForTimeout(8000)
  console.log('URL after clicking', first, ':', page.url())
}

console.log('\n=== ERRORS ===')
console.log(errors.slice(0, 40).join('\n') || '(none)')

await browser.close()
