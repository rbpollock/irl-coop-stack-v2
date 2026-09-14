// Run only the erpnext-sso journey (fast iteration).
import { chromium } from "playwright"
import { makeCtx } from "./lib.mjs"
import * as erpnext from "./journeys/erpnext-sso.mjs"

const ctx = makeCtx()
const browser = await chromium.launch()
ctx.browser = browser
try {
  await erpnext.run(ctx)
} finally {
  await browser.close().catch(() => {})
}

let failed = 0
let total = 0
console.log(`\n== ${erpnext.name}: ${erpnext.description}`)
for (const r of ctx.results) {
  total++
  if (!r.ok) failed++
  console.log(`  ${r.ok ? "PASS" : "FAIL"} ${r.name}${r.detail ? `  [${r.detail}]` : ""}`)
}
console.log(`SUMMARY: ${total - failed}/${total} passed`)
process.exit(failed ? 1 : 0)
