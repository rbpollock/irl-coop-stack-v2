// Journey suite runner: executes every journey against the live stack and
// reports a unified pass/fail summary (non-zero exit on any failure).
//
// API journeys (fetch-only) run first; the browser journeys share one NocoDB
// passkey session. Run via journeys.sh (derives credentials + the host-side
// identity-isolation check), or directly inside irlcoop/browser-runner.
import { chromium } from "playwright"
import { makeCtx, loginNocodb } from "./lib.mjs"
import * as signIn from "./journeys/sign-in.mjs"
import * as groupsScope from "./journeys/groups-scope.mjs"
import * as membership from "./journeys/membership.mjs"
import * as anonymous from "./journeys/anonymous.mjs"
import * as nocodbRead from "./journeys/nocodb-read.mjs"
import * as nocodbWrite from "./journeys/nocodb-write.mjs"
import * as nocodbApp from "./journeys/nocodb-app.mjs"
import * as roundcubeMail from "./journeys/roundcube-mail.mjs"

// Order matters: sign-in first (establishes identity), browser last.
const apiJourneys = [signIn, groupsScope, membership, anonymous]
const browserJourneys = [nocodbRead, nocodbWrite, nocodbApp, roundcubeMail]

const runs = [] // [{ journey, ctx }]
let browser = null

try {
  for (const journey of apiJourneys) {
    const ctx = makeCtx()
    await journey.run(ctx)
    runs.push({ journey, ctx })
  }

  browser = await chromium.launch()
  const session = await loginNocodb(browser)
  for (const journey of browserJourneys) {
    const ctx = makeCtx()
    ctx.nocodb = session
    await journey.run(ctx)
    runs.push({ journey, ctx })
  }
} catch (err) {
  console.error("SUITE ERROR:", err?.message ?? err)
} finally {
  if (browser) await browser.close().catch(() => {})
}

let failed = 0
let total = 0
let skipped = 0
for (const { journey, ctx } of runs) {
  console.log(`\n== ${journey.name}: ${journey.description}`)
  for (const r of ctx.results) {
    if (r.skip) {
      skipped++
      console.log(`  - SKIP ${r.name}${r.detail ? `  [${r.detail}]` : ""}`)
    } else {
      total++
      if (!r.ok) failed++
      console.log(`  ${r.ok ? "PASS" : "FAIL"} ${r.name}${r.detail ? `  [${r.detail}]` : ""}`)
    }
  }
}

console.log(`\n${"-".repeat(64)}`)
console.log(`SUMMARY: ${total - failed}/${total} checks passed (${skipped} skipped)`)
process.exit(failed ? 1 : 0)
