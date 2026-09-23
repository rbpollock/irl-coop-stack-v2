import { chromium } from 'playwright'
import { env } from './lib.mjs'

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()

const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text().slice(0, 250)) })
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + String(e).slice(0, 300)))
page.on('response', (r) => {
  if (r.status() >= 400 && !r.url().includes('socket.io')) errors.push(`${r.status()} ${r.request().method()} ${r.url().replace('https://nocodb.irl.coop','')}`)
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

// Click the "Coop" base card (a real collective base with tables)
await page.click('.nc-base-node:has-text("Coop")', { timeout: 15000 })
await page.waitForTimeout(6000)
console.log('URL AFTER BASE CLICK:', page.url())

// List tables in the sidebar
const tables = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('.nc-table-node, [data-testid*="table"], .nc-tab-item, a[href*="table"]'))
    .map(e => (e.textContent || '').trim()).filter(Boolean).slice(0, 30)
})
console.log('TABLES SEEN:', JSON.stringify(tables))

// Click the first table-like node
const clicked = await page.evaluate(() => {
  const el = document.querySelector('.nc-table-node') || document.querySelector('a[href*="table"]')
  if (!el) return null
  el.click()
  return el.textContent?.trim().slice(0, 30)
})
console.log('CLICKED TABLE:', clicked)
await page.waitForTimeout(6000)
console.log('URL AFTER TABLE CLICK:', page.url())

console.log('\n=== ERRORS ===')
console.log(errors.slice(0, 30).join('\n') || '(none)')

await browser.close()
