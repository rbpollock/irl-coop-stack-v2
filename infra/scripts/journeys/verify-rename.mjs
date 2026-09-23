import { chromium } from 'playwright'
import { loginNocodb } from './lib.mjs'

const browser = await chromium.launch()
const { context, page } = await loginNocodb(browser)
await page.waitForTimeout(3000)

const info = await page.evaluate(() => {
  const b = document.body.innerText || ''
  return {
    hasMyBase: b.includes('My Base'),
    hasRobertPollock: b.includes('Robert Pollock'),
    hasScratchBase: b.includes('my base') || /\bBase\b/.test(b),
    basesCount: (b.match(/Bases\s*\((\d+)\)/) ?? [])[1] ?? null,
    snippet: b.slice(0, 400),
  }
})
console.log(JSON.stringify(info, null, 1))
await browser.close()
