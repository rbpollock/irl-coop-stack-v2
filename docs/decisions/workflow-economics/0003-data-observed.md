# 0003 — What data can be observed (D3)

Status: **accepted** · Owner: Robbie · Date: 2026-09-22
Depends: D1 (direction = O4 workbench), D2 (decision/routing workbench accepted).

## Decision statement

**From which signals does the v1 workbench draw its routing evidence — local
structural metadata only, plus event-time timing via a small hook, or plus
content/detail (prompts, outputs, tool args)?**

## Context

- V1 goal (D2): a local decision/routing workbench using local inference. It
  needs **enough signal to recommend model-per-task with evidence**, no more.
- Phase-0 finding: cost/token/context is already local and persisted
  (`session_model_usage` in `state.db`, plus `agent/insights.py` + `/insights`).
  Structural signals (task, model, tokens, cache, cost) are available without
  any new capture.
- Routing signal requirement: task→model recommendation needs per-「-task cost
  and token/quality signals. It does **not** need prompts.

## Non-negotiable

1. No prompts, source, secrets, or tool output leave the host (or export) in
   v1.
2. Metadata only by default. Content = later, opt-in, content-free any local.
3. v1 = read-only observer; no auto-routing (D7 gates it).
4. Any hook must be optional, fail-open, timeout-budgeted, non-blocking.

## Options

| id | Option | Signal set |
|----|--------|-----------|
| O0 | Structure/metadata only | persisted tokens, task, model, provider, cache, cost (corrected); from reading the store + `/insights`. No new capture. |
| O1 | + timing-quality via hook | O0 PLUS a small hook capturing timing + per-call latency, later quality/success, still content-free |
| O2 | + content capture | O0 + content (prompts, outputs, tool args/results) for deep quality/audit. |

## Evidence

| # | Claim | Source | Conf |
|---|-------|--------|------|
| e1 | The metadata Hermes persists covers task/model/token/cost | `session_model_usage` in `state.db`; live rows | high |
| e2 | Correcting cost from token×price is possible (wrong `provider` estimate today) | live Telnyx/DeepSeek rows (`estimated_cost_usd` absurd, `actual=0`) | high |
| e3 | Per-call timing/latency is NOT persisted; only available via an observer hook | plugin hook list (post_llm_call/tool_call), observer-only | high |
| e4 | Content is not required for routing decisions in v1 | analysis of the routing signal set above (E: metadata enough) | medium |
| e5 | A hook is optional; /insights already surfaces aggregated | `agent/insights.py`, `/insights` | high |

## Assumptions / unknowns

- Route-needs are satisfiable from metadata (a working assumption). Medium
  confidence — verify in D6 experiment.
- Timeouts/latency add useful routing signal but it's unknown how much. Low
  confidence → defer.
- Content-driven "quality" is out of scope (Robbie's quality axis in D2 is scope-gated in v1).

## Weights (stable rubric, sum 1.0)

work .15 · cost .10 · quality .15 · local .10 · reversible .20 · complex .05 ·
time_to_value .10 · observability .05 · extensibility .10

## Scored (0–5, confidence implied low on assumptions)

| Crt | O0 | O1 | O2 |
|---|---|---|---|
| work | 3 A | 4 A | 4 A |
| cost | 3 A | 3 A | 2 A |
| quality | 4 A | 4 A | 5 A |
| local/privacy | 4 | 3 | 1 |
| reversible | 5 | 3 | 2 |
| complex | 3 | 4 | 2 |
| time_to_value | 4 | 3 | 2 |
| observability | 4 | 5 | 5 |
| extensibility | 3 | 4 | 2 |

**Weighted (running sum, stable weights)**: O0 3.80 · O1 3.50 · O2 2.80.

O0 wins; content (O2) is both least local and lowest reversibility, and the
routing goal doesn't need it.

## Recommendation

**D1 accept O0**: v1 observes **structural metadata only** — the local task, model,
provider, token, cache, corrected cost, and task bucket, read from Hermes leaves
+ `/insights`. **No new hook, no content capture** in v1. Add a hook later only
if routing needs live timing (revisit in D7/D8), with the constraints above.

## Safety / privacy / security

- O0 confines to metadata: highest privacy, no redaction burden.
- Timing hook (O1) later is still content-free; must be opt-in and timeout.
- Content (O2) rejected for v1 — it is a redaction-grade (privacy) and can't
  justify itself vs routing/metadata need.

## Implementation consequences

- Read `session_model_usage` + `_insights` via read; compute corrected cost
  from tokens×price.
- No new capture of content. Nothing leaves the host.

## Validation

- Reproduce the D0 report (tokens, corrected cost, task) from 2–3 weeks of
  history; sanity-match 5 sessions.
- Confirm "routes can be recommended without per prompt content."

## Revisit

Re-open O1 hook when: a timing/quality tie is a bottleneck; or D7/D8 requires
per tool/event in the route signal.