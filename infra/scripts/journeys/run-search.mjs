// Run only the search journey (for quick iteration). Mirrors run.mjs's browser
// section: one chromium, the search journey gets ctx.browser.
import { chromium } from "playwright"
import { makeCtx } from "./lib.mjs"
import * as search from "./journeys/search.mjs"

const ctx = makeCtx()
const browser = await chromium.launch()
ctx.browser = browser
try {
  await search.run(ctx)
} finally {
  await browser.close().catch(() => {})
}

let failed = 0
let total = 0
console.log(`\n== ${search.name}: ${search.description}`)
for (const r of ctx.results) {
  total++
  if (!r.ok) failed++
  console.log(`  ${r.ok ? "PASS" : "FAIL"} ${r.name}${r.detail ? `  [${r.detail}]` : ""}`)
}
console.log(`SUMMARY: ${total - failed}/${total} passed`)
process.exit(failed ? 1 : 0)
