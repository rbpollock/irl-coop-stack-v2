# Workflow Economics — decision workspace

Guard rail for a Hermes workflow-economics effort: reduce AI-dev cost, improve
outcomes, preserve privacy, and get the workflow better through measured
evidence — not assumptions.

This is a **Jev-style decision process** (a structured *decision aid*, not an
autonomous architect). Everything here is written reasoning: options, evidence,
assumptions, uncertainty, and an explicit recommendation that can be a decision,
a bounded experiment, a deferral, or "needs a human." Nothing here is a model
score overriding security / privacy / budget / approval rules.

## Decision records

One Markdown file per decision: `NNNN-short-decision-name.md`. Every record
carries: status, date/owner, a bounded decision statement, deadline/revisit,
context, non-negotiable constraints, options (incl. "do nothing" and "bounded
experiment"), evidence with source paths, assumptions/unknowns, rubric + weights,
scored comparison with per-score confidence, risk/reversibility/privacy/
security/operations, the Jev question set, recommendation, human decision
required, implementation consequences, validation/measurement plan, and revisit
conditions.

| Record | Status |
|---|---|
| [0001-boundary-form-factor](0001-boundary-form-factor.md) — D1: plugin vs standalone vs combination | proposed (phase 0) |
| [0002-primary-goal](0002-primary-goal.md) — D2: v1 primary goal = local decision/routing workbench | accepted |
| [0003-data-observed](0003-data-observed.md) — D3: observe metadata structure only | accepted |
| [0004-data-storage](0004-data-storage.md) — D4: rich local task records, content-free | accepted |
| [0005-interaction-surface](0005-interaction-surface.md) — D5: in-session Hermes tool (+ Markdown record) | accepted |
| [0006-first-experiment-task](0006-first-experiment-task.md) — D6: first experiment = commit/title/changelog drafts | accepted |
| [0007-safety-gates](0007-safety-gates.md) — D7: deterministic safety/approval boundaries (G0) | accepted |
| [0008-classifier-selection](0008-classifier-selection.md) — D8: router classifier = deterministic + local | proposed |
| Decision map (D1–D9 index + dependencies) | [decision-map.md](decision-map.md) |

## Rubric (stable)

Score each option **0–5** on every axis that applies. Every score cites evidence
or is stated as an assumption, and carries confidence **high / medium / low**.
Do not turn low-confidence estimates into a precise weighted verdict.

| Criterion | Axis meaning |
|---|---|
| workflow leverage | effort saved / outcomes improved per session |
| cost impact | effect on real total spend |
| quality preservation | kept vs degraded output quality |
| local-first / privacy | stays on-host; no external leakage |
| reversibility | easy to stop, undo, or regret-free |
| complexity / maintenance | 5 = simplest to build and keep |
| time-to-value | weeks to first usable signal |
| observability | how well cost/quality/effort can be seen |
| extensibility | can grow toward routing / decision support |

Weights are set per decision in its record. Low-confidence weighted totals are
shown with a caveat, never as authority.

## Decision primitives

`CHOICE` select one option; `SCORE` rate on the rubric; `NOUL` estimate whether
a narrow proposition is true; `HARD_CONSTRAINT` a deterministic pass/fail rule,
never a model judgment; `ESCALATE` needs your decision. Types in
[decision-primitives.ts](decision-primitives.ts).

## Process

1. Phase 0 — discovery only: inspect the Hermes APIs and real plugins, map
   extension points and telemetry access, index decisions/dependencies, draft
   **D1 only**, end with ≤ 5 questions. No code.
2. You accept D1 → proceed one decision at a time. No coding until accepted
   decisions make a small, testable phase-one scope.

## Non-negotiable constraints (apply to every record)

- **Local-only by default.** No source code, prompts, secrets, or private tool
  output leaves your machine unless you explicitly authorize a specific export.
- **Observer, not agent.** Tool is observational first; nothing knowingly
  changes model config, spend limits, provider credentials, publishing state,
  permissions, production systems, or external services.
- **Deterministic first.** Hard constraints and approvals win over any model
  judgment. Routing/automation only after D7-style gates are accepted.
- **Measured.** A change ships with a validation plan; "improvement" is defined
  by agreed thresholds, not feelings.
- **No `infra/out/` artifacts, no secrets** anywhere in the decision tree.