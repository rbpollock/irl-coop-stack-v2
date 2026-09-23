# 0002 — V1 primary goal (D2)

Status: **accepted** · Owner: Robbie · Date: 2026-09-22
Depends on: D1 (boundary) — resolved direction is the local workbench on Hermes data (O4-leaning).

## Decision statement

**What should version one of the workflow-economics effort optimize first: an
observability report, direct cost reduction, task-quality improvement, local
model up-take, or a decision/routing workbench used via local inference?**

## Context & current workflow

- Workload: TS/React/Next.js, infra, Docker/self-host, debugging, planning,
  research, agent runs on Hermes (local DeepSeek-style models + paid/hosted
  where materially better).
- Goal: better outcomes, lower cost/drag, local-first/privacy, measured.
- Phase-0 finding: Hermes already persists per-model token/cost/task data
  locally (`state.db.session_model_usage`) and has an `InsightsEngine` +
  `/insights`. So "see the cost" is largely already done; the strategic gap is
  **turning that data into a routing/decision**, not another report.

## Non-negotiable constraints

1. Local-first; no prompts/secrets/source/tool-output leave the host.
2. v1 does **recommendations, not autonomous switching.** No routing acts on
   model/provider/spend until D7 hard gates are accepted.
3. Deterministic first; hard constraints beat model scoring.
4. Extends Hermes built-ins (insights) rather than duplicating them.
5. Reversible + measurable.

## Options

| id | Option | v1 focus |
|----|--------|----------|
| O0 | Observability | richest cost/task report (largely exists today) |
| O1 | Direct cost cut | timer to lower spend fastest |
| O2 | Quality first | improve outputs in/quality before cost |
| O3 | Local up-take | push harder any use of local/self-hosted models |
| O4 | Routing workbench | use local inference on real Hermes data to decide which model runs which task, with recommendation outputs (not auto-execution) |

## Evidence

| # | Claim | Source | Conf |
|---|-------|--------|------|
| e1 | Cost/token data already persisted; a report surface exists | `session_usage`, `agent/insights.py`, `/insights` | high |
| e2 | Cost attribution is a bottleneck (provider estimate wrong for Telnyx/DeepSeek; `actual_cost_usd=0`) | live rows | high |
| e3 | Offer to extend / reuse existing insight is accepted (Robbie Q3) | this thread | high |
| e4 | Routing by model/task is an intended goal (Robbie Q2) | this thread | high |

## Assumptions / unknowns

- Routing value is unmeasured. True worth of per-task model choice depends on
  D3/D6 runs, not estimates. Medium confidence.
- Local inference quality (classifier for task→model) is enough for v1 helpful
  decision. Medium/Low confidence → test in the workbench, don't assume.
- Cost savings from routing are real but quantify after D9 threshold run.

## Deterministic gates before any auto-routing (grants D7 feeds)

- No model/provider switch without explicit approval. Workbench outputs a
  **decision card** (recommended model per task, with why), user applies it.
- Any automated route (lanes) requires D7 acceptance (deterministic boundary on
  task/class/mode; approval rule unchanged).

## Weights (sum 1.0)

| Criterion | w |
|---|---|
| workflow_leverage | .15 |
| cost_impact | .10 |
| quality_preservation | .15 |
| local_first | .10 |
| reversibility | .20 |
| complexity | .05 |
| time_to_value | .10 |
| observability | .05 |
| extensibility | .10 |

## Scored comparison (0–5; conf bracketed)

| Criterion | O0 | O1 | O2 | O3 | O4 |
|---|---|---|---|---|---|
| work_leverage | 3 A/m | 3 A/m | 4 A/m | 3 A/m | 5 A/m |
| cost_impact | 1 A/m | 4 A/m | 1 A/m | 3 A/m | 3 A/m |
| quality_pres | 3 A/m | 3 A/m | 4 A/m | 3 A/m | 4 A/m |
| local_first | 3 E/h | 4 E/h | 4 E/h | 5 E/h | 4 E/h |
| reversibility | 4 E/h | 4 E/h | 4 E/h | 4 E/h | 4 E/h |
| complexity | 4 A/m | 4 A/m | 4 A/m | 4 A/m | 2 A/l |
| time_to_value | 4 A/m | 4 A/m | 4 A/m | 3 A/m | 3 A/m |
| observability | 4 E/h | 4 E/h | 3 A/m | 3 A/m | 4 A/m |
| extensibility | 3 A/m | 2 A/m | 3 A/m | 3 A/m | 4 A/m |

**Weighted totals (direction only ⚠):** O4 3.85 · O2 3.55 · O1 3.50 · O3 3.45 · O0 3.20.

O4 lead depends on low-confidence `complexity`/`time_to_value`. So treat O4 as
the recommended test, not a settled win.

## Recommendation

Adopt **O4 — a local decision/routing workbench** as v1 primary goal, framed as:
**read Hermes insights → local inference → decision cards** recommending which
model to route each task, never auto-executing. Pair it with D1-boundary O4
(workbench on top of Hermes' data; no heavy plugin in v1). Extend-insights
poses the cheap read half; the workbench is the think half. Any actual routing
only comes after D7.

## Human decision required (D2's real ask)

Authorize:** yes/no** — v1 primary goal = local decision/routing workbench
(O4), with cost reduction as the measured *consequence* rather than the
bench-to-find, and auto-route deferred until D7 gates pass.

## Implementation consequences (accepted)

- Build: a local module that reads Hermes persisted insights + corrected cost,
  feeds a local inference classifier (task→model recommendation), and emits
  decision cards as Markdown/JSON. Reuses Hermes existing analytics; no plugin
  yet, no changes to core. Reversible: nothing in core, local CLI.