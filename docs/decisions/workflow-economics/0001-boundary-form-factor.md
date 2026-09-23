# 0001 — Boundary / form factor (D1)

Status: **proposed** (needs human decision)
Date: 2026-09-22 · Owner: Robbie

## Decision statement (one bounded question)

Which implementation form should carry the workflow-economics deliverable —
a **repo-local CLI/analysis tool**, a **Hermes observer plugin**,
a **standalone local service**, or a **combination** — knowing that Hermes
already persists per-model cost/token usage locally and surfaces it through an
`InsightsEngine`?

## Deadline / revisit trigger

Decide before any implementation (Phase 1 begins accepted). Revisit D1 if the
Hermes plugin API contract changes materially (new hook payloads, manifest v2,
streaming hooks) **or** when a measured outcome requires capturing event-time
data that the local usage table cannot hold (see unknowns).

## Context and current workflow

- Host tool: Hermes Agent. Local + self-hosted inference (DeepSeek-style
  coding models), plus paid/hosted models where materially better. Work load:
  TypeScript/React/Next.js, infra, Docker/self-host, debugging, planning,
  research, tool-using agent runs.
- Goal (pre-decision): better outcomes, lower friction/st. cost, strong
  local/privacy, a workflow that improves through measured evidence.
- Initial hypothesis: a Hermes **plugin** may observe cost/quality and guide
  model/task routing. This is **not yet confirmed**; a passive telemetry tool
  or a decision workbench may be better. D1 exists to test that hypothesis.

## Key discovery facts (Phase 0, verified)

- **Cost/token data is already local and persisted** in `~/.hermes/state.db`
  table `session_model_usage`, written per API call
  (`hermes_state.py:9055`, `9149`); columns include tokens, cache tokens,
  reasoning tokens, `estimated_cost_usd`, `actual_cost_usd`, `task`, model,
  provider, times. `task` distinguishes aux calls
  (`title_generation`, `background_review`, `compression`, …) from the main
  loop (`''`).
- **An ordering viewer already exists**: `InsightsEngine`
  (`agent/insights.py`) + `/insights` slash command (`cli.py:14224`) and the
  dashboard usage block. So the "report" we might build is at least partially
  bundled already.
- **Cost attribution is unreliable today** (measured). Live rows from the
  Telnyx/DeepSeek route show `estimated_cost_usd` at absurd magnitudes
  (191,516 / 360,516 / 4,372,866 for single sessions) with `actual_cost_usd =
  0`. `cost_status='estimated'`, `cost_source='provider_models_api'`. Real
  "cost reduced" reports need corrected token×price math, not provider
  estimates.
- **Content is only ever needed in later; phase-1 economics needs no prompts**
  (see D4). So the tool does not need content access, only structural metrics.
- A Hermes plugin is the **officially sanctioned carrier for standalone
  observability** (`~/.hermes/plugins/<name>/plugin.yaml` + `__init__.py`,
  `register(ctx)`; AGENTS.md §Plugins; RFC "plugin-architecture-lessons").
  But plugins run in-process and cost has to obey timeouts and stay off the
  hot path (RFC lesson 4).

## Non-negotiable constraints

1. Local-only by default; never ship prompts, source, secrets, or private tool
   output. Only opt-in, explicit exports.
2. Observational first: no autonomous change to model config, spending, creds,
   publishing, permissions, production, or external services (D7 gates route
   later).
3. Deterministic first — hard constraints beat any model judgment.
4. Never modifies core; keep prompt-cache stability; no blocking hot path
   (Hermes ground rules + RFC).
5. Reversible & measurable: any implementation ships with a validation plan.

## Options

| id | Option | One-line |
|----|--------|----------|
| O0 | Do nothing | rely on bundled `/insights` as-is |
| O1 | Repo-local CLI/analysis tool | read-only script reuses `session_model_usage` + corrected cost + tasks; Markdown/JSON outputs; no plugin, no daemon |
| O2 | Hermes observer plugin | `~/.hermes/plugins/wirte?/` hooks capture event-time metrics (latency, routing), register a `hermes workflow-econ` subcommand |
| O3 | Standalone local service | long-running watcher/daemon producing reports/dashboard from `state.db` |
| O4 | Combination | start with O1 for evidence; add a **tiny** observer hook later, only for metrics DB reads cannot cover; Delay duplicating `/insights`. |

## Evidence (source files + measurements)

| # | Fact | Evidence | Confidence |
|---|------|----------|------------|
| E1 | Usage persisted per-call (tokens, cache, reasoning, est/actual cost, task, model) | `hermes_state.py:9055,9149`; live `SELECT` on `session_model_usage` (state.db) | high |
| E2 | Ordering/aggregation + a report surface exist | `agent/insights.py`, `cli.py:14224` `/insights`, `web_server.py:15764` | high |
| E3 | Cost estimates are unreliable on some routes; real cost = 0 auth | live rows (Telnyx/DeepSeek) show absurd `estimated_cost_usd`, `cost_status='estimated'`, `actual_cost_usd=0` | high |
| E4 | Plugins are the sanctioned standalone-host for observability, but in-process; observe → fail-open, guard → fail-closed; need timeout budgets | AGENTS.md §3, `plugins/observability/langfuse` (existing), RFC 2026-07-plugin-architecture + `#64161` | high |
| E5 | A plugin may not be necessary to meet v1: the persistence + insights already cover "see cost/token by task" | E1+E2 | medium |

## Assumptions & unknowns

- **Task-targeted leverage is unknown.** Main-loop rows have `task=''`, so you
  can't attribute cost to "debugging X" vs "writing tests" from the table
  alone. Labeling a task may need (a) user-given session labels, (b) a model
  classifier (D8), or (c) done best-effort later.
- **Correct pricing model is buildable today.** Assume the current price
  (`provider_models_api` estimate) is replaceable from the model's published
  price cards with tested token math. Medium confidence.
- **Real savings magnitudes are unmeasured.** Until D3/D6 are run, the size of
  the "reduce / reuse / wrong-model" opportunities is guessed, not measured.
- **Future routing appetite is unknown** (you may never want auto-routing).

## Criteria & weights (sum ≈ 1.00)

| Criterion | Weight | Notes |
|---|---|---|
| workflow_leverage | 0.15 | outcomes/effort saved per session |
| cost_impact | 0.10 | effect on real total spend |
| quality_preservation | 0.15 | keep/don't degrade output quality |
| local_first | 0.10 | local / near privacy |
| reversibility | 0.20 | easy to undo/stop/regret-free |
| complexity | 0.05 | 5 = simplest to build & keep |
| time_to_value | 0.10 | weeks to first usable signal |
| observability | 0.05 | can we actually see cost/quality/effort |
| extensibility | 0.10 | capacity to grow toward routing / decision support |

## Scored comparison (0–5; evidence-E / assumption-A; conf high/med/low)

Low-confidence cells count in the weighted total **but the total is a
direction, not a verdict** — see caveat below.

| Criterion | w | O0 | O1 | O2 | O3 | O4 |
|---|---|---|---|---|---|---|
| workflow_leverage | .15 | 2 A/m | 3 A/m | 4 A/m | 2 A/m | 4 A/m |
| cost_impact | .10 | 1 A/m | 2 A/m | 2 A/l | 1 A/l | 2 A/m |
| quality_preservation | .15 | 5 E/h | 5 A/h | 4 A/m | 5 A/h | 4 A/m |
| local_first | .10 | 5 E/h | 5 E/h | 4 A/h | 5 E/h | 4 A/h |
| context reversibility | .20 | 5 E/h | 5 E/h | 4 A/m | 3 A/m | 4 A/m |
| complexity | .05 | 5 E/h | 4 A/m | 3 A/m | 4 A/m | 3 A/m |
| time_to_value | .10 | 5 E/h | 4 A/m | 3 A/m | 2 A/m | 4 A/m |
| observability | .05 | 3 E/m | 4 E/h | 4 A/m | 4 E/h | 5 A/m |
| extensibility | .10 | 0 A/l | 4 A/m | 4 A/m | 2 A/l | 5 A/m |

**Weighted totals (direction only ⚠):** O1 4.10 · O4 3.80 · O0 3.55 · O2 3.45 · O3 3.20.

Caveat: the two axes that most differented O1/O4/O2 — `cost_impact`
and `extensibility` — carry **low/medium** confidence, and O1 vs O4 are within
0.35. So these totals do not decide D1; they pick the option to test.

## Risk, reversibility, privacy, security, operations

- **O1 (tool):** least risk, most reversible (degenerate). No runtime coupling.
  Privacy: pure local. Security: read-only plus decision-doc writes; no side
  effect. Fails to capture event-time metrics.
- **O2 (plugin):** in-process risk surface (instance alive + hot path). Fail-
  open; needs timeout budgets and a hook-write-up-drift test (RFC lesson 3).
  Higher privacy cargo: a plugin is code that loads into Hermes; keep it
  tiny. This is the only path that can later act (routing).
- **O3 (service):** extra supervision/reverse; a permanent daemon is the
  least reversible. Does not unlock anything O1 doesn't.
- **O4 (combination):** two moving pieces (tool + a small plugin later); still
  low overall, but pay the ecosystem.
- **Security & privacy:** none of O1–O3 export data; O4's later observer hooks
  must stay content-free. No external service is touched in v1.

## Jev-style question set (see decision-primitives.ts for the shared types)

```ts
// Decision's question set, expressed with the shared primitives
// (types in ./decision-primitives.ts). Type-validated shape.

import type { DecisionQuestion, Criterion } from "./decision-primitives";

const d1Questions: DecisionQuestion[] = [
  {
    // HARD_CONSTRAINT — deterministic pass/fail gate, not a model judgment
    primitive: "HARD_CONSTRAINT",
    stem: "The chosen form keeps cost/usage data local; nothing leaves the host in v1.",
    pass: true,
  },
  {
    primitive: "HARD_CONSTRAINT",
    stem: "The chosen form never changes model config, spending, credentials, or permissions.",
    pass: true,
  },
  {
    // NOUL — narrow proposition to bet true, then measure
    primitive: "NOUL",
    proposition:
      "Hermes already persists enough local cost/token/task data that a read-only analysis tool can produce a meaningful v1 economics report with no new plugin hooks.",
  },
  {
    // SCORE — rate candidate forms on the rubric's top axes for v1
    primitive: "SCORE",
    stem: "Rank O0–O4 on the axes that most separate them.",
    options: {
      O0: ["workflow_leverage", "reversibility", "extensibility"],
      O1: ["time_to_value", "reversibility", "observability"],
      O2: ["extensibility", "quality_preservation"],
      O3: ["time_to_value", "reversibility"],
      O4: ["observability", "extensibility"],
    } as Record<string, Criterion[]>,
  },
  {
    // CHOICE — the actual bounded decision
    primitive: "CHOICE",
    stem: "Select the v1 boundary form factor.",
    optionIds: ["O0", "O1", "O2", "O3", "O4"],
  },
  {
    // ESCALATE — needed because the totals are close and the decisive axis is a value trade-off
    primitive: "ESCALATE",
    stem: "Prioritize reversibility (O1) vs extensibility toward routing (O2/O4) in v1?",
    why: "Ties are narrow and the deciding factor is Robbie's preference, not a score.",
  },
];
```

## Recommendation

Run a bounded experiment on **O1 (repo-local CLI/analysis tool)** and (if you
want the option open) plan O4 — a **tiny, optional** observer hook added only
for metrics the persisted table can't hold (latency/task timing), gated behind
evidence and behind D7 safety rules. **Do not build O2 as the first deliverable
or O3 at all in v1.**

So: a **bounded experiment + suggestion**, not a final boundary. The bundled
`/insights` + persisted local usage is enough to build a real v1 report today
(no plugin), and the report—and corrected cost attribution—is the evidence that
later decides when a plugin (O2) earns its in-process cost.

## Human decision required (cannot resolve technically)

1. **Reversibility vs extensibility trade-off.** Reversibility is highest in
   O0/O1 (tool, instant-removable), extensibility toward future routing is
   highest in O2/O4 (plugin/hook). Which priority do you weight for v1? This is
   a value judgment, so I can't pick it from a score.
2. **Do you want "economics only" or "economics + decision workbench"?** The
   plugin is mainly justified if the v1 goal is also a routing/decision surface.
   For pure cost/quality telemetry the plugin is poor choice.
3. Choose the **first measurable success target** (D2) — I can recommend, but it
   holds a preference.

## Implementation consequences (if accepted)

- O1 = a small read-only module under `docs/decisions/workflow-economics/` (or
  a `tools/` dir once approved), reading `state.db::session_model_usage` and
  `InsightsEngine`, computing **corrected cost from tokens × price-card math**
  (not `provider_models_api` errors), outputting Markdown + JSON. No plugin.
- Reuses Hermes persistence; no new schema, no hooks, no daemon.
- A later O2 plugin, only if a metric requirement becomes unmet; then it is
  `~/.hermes/plugins/wf-econ/` with timeout guard + hook test.

## Validation / measurement plan

- Produce a v1 report from **2–3 weeks** of real install history; compare to
  bundled `/insights` (should roughly agree on tokens; should correct cost for
  Telnyx/DeepSeek).
- Metric: report answers "where did cost spend by task–aux — model?" with
  corrected cost + cache-token share. Threshold for "works" = the report builds
  in < 5s, is reproducible, and sanity-matches hand-inspection of 5 sessions.

## Revisit conditions

- If Hermes plugin API contract shifts (new state payloads) → re-open O2.
- If D7/D9 later ask for routing/autonomous action → require moving to O2/O4,
  with the gates from D7 prewritten.
- If corrected cost math proves infeasible (no rock-solid price cards) → the
  whole cost_impact premise weakens; reconsider whether observed improvement is
  meaningful.