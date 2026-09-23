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

// Land on the home dashboard
await page.goto(`${env.web}/en`, { waitUntil: 'domcontentloaded', timeout: 45000 })
await page.waitForTimeout(3000)

const body = await page.evaluate(() => document.body.innerText)
const checks = {
  'under active development': /under active development/i.test(body),
  'features subject to change': /features are subject to change/i.test(body),
  'experimental': /experimental/i.test(body),
  'data loss is likely': /data loss is\s+likely/i.test(body),
}
for (const [k, v] of Object.entries(checks)) console.log(`${v ? 'PASS' : 'FAIL'}  ${k}`)

await browser.close()
process.exit(Object.values(checks).every(Boolean) ? 0 : 1)
