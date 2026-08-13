#!/usr/bin/env node
// The fleet's browser-automation execution unit.
//
// The scenario is the first argv (default: files-flow); harness modules in
// /app/e2e are self-contained and own their exit codes. A Temporal
// activity will dispatch this container with a scenario name + env inputs
// and collect the evidence from /tmp (see docs/design/browser-management.md).
const scenario = process.argv[2] ?? "files-flow"
console.log(`[runner] scenario: ${scenario}`)
await import(`/app/e2e/${scenario}.mjs`)
