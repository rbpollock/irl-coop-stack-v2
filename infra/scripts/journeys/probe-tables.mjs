import { chromium } from 'playwright'
import { env } from './lib.mjs'

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()

const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text().slice(0, 200)) })
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + String(e).slice(0, 250)))
page.on('response', async (r) => {
  if (r.status() >= 400 && !r.url().includes('socket.io')) {
    let body = ''
    try { body = (await r.text()).slice(0, 200) } catch {}
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

// Click e2e-test's OWN personal base "E2E Tester" (13 tables)
await page.click('.nc-base-node:has-text("E2E Tester")', { timeout: 15000 })
await page.waitForTimeout(7000)
console.log('URL:', page.url())

// Dump sidebar text to find table names + their clickable nodes
const sidebar = await page.evaluate(() => {
  const txt = document.body.innerText
  return txt.slice(0, 800)
})
console.log('SIDEBAR/BODY TEXT:\n', sidebar)

await browser.close()
