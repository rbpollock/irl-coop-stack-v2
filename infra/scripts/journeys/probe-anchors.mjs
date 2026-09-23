import { chromium } from 'playwright'
import { env } from './lib.mjs'

const browser = await chromium.launch()
const context = await browser.newContext()
const page = await context.newPage()

const errors = []
page.on('console', (m) => { if (m.type() === 'error') errors.push('CONSOLE: ' + m.text().slice(0, 200)) })
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

// Dump ALL anchors with hrefs
const anchors = await page.evaluate(() => {
  return Array.from(document.querySelectorAll('a[href]')).map(a => ({
    t: (a.textContent || '').trim().slice(0, 40),
    h: a.getAttribute('href')
  })).filter(x => x.h && (x.h.includes('base') || x.h.includes('table') || x.h.includes('nc') || x.h.includes('dashboard')))
})
console.log('ANCHORS:', JSON.stringify(anchors.slice(0, 40), null, 1))

await browser.close()
