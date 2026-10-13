// Focused runner: execute ONE journey by name — fast iteration while building
// a journey, without paying for the whole suite. The full suite stays run.mjs.
//
// Usage (inside irlcoop/browser-runner, from journeys.sh):
//   node journeys/one.mjs plane-scope
import { chromium } from "playwright"
import { makeCtx } from "./lib.mjs"
import * as planeScope from "./journeys/plane-scope.mjs"

const all = { "plane-scope": planeScope }

const wanted = process.argv[2]
const journey = all[wanted]
if (!journey) {
  console.error(`unknown journey: ${wanted ?? "(none)"} — known: ${Object.keys(all).join(", ")}`)
  process.exit(2)
}

const browser = await chromium.launch()
const ctx = makeCtx()
ctx.browser = browser
try {
  await journey.run(ctx)
} catch (err) {
  ctx.check(`${journey.name}: journey threw`, false, String(err?.message ?? err).slice(0, 200))
}

let failed = 0
console.log(`\n== ${journey.name}: ${journey.description}`)
for (const r of ctx.results) {
  if (r.skip) {
    console.log(`  - SKIP ${r.name}`)
  } else {
    if (!r.ok) failed++
    console.log(`  ${r.ok ? "PASS" : "FAIL"} ${r.name}${r.detail ? `  [${r.detail}]` : ""}`)
  }
}

await browser.close()
process.exit(failed ? 1 : 0)