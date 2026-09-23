import { chromium } from 'playwright'
import { loginNocodb, env } from './lib.mjs'

const browser = await chromium.launch()
const { context, page, token } = await loginNocodb(browser)

// What base-title text does the develop nc-gui actually render on the bases list?
const info = await page.evaluate(() => {
  const links = [...document.querySelectorAll('a, [class*="base"], [class*="Base"], [class*="card"], [class*="Card"]')]
    .map((el) => el.textContent?.trim())
    .filter((t) => t && /Coop|Food|Civic|Storage/i.test(t))
    .slice(0, 30)
  return { bodyHasCoopGroups: (document.body.innerText || '').includes('Coop Groups'), links }
})
console.log('BODY-HAS-COOP-GROUPS:', info.bodyHasCoopGroups)
console.log('MATCHING-ELEMENTS:', JSON.stringify(info.links, null, 1))

await browser.close()
