# 0004 — Data storage depth (D4)

Status: **accepted** · Owner: Robbie · Date: 2026-09-22
Depends: D3 (observe metadata only).

## Decision statement

**How deep should the v1 workbench store the observed data — lean local
metadata only, opt-in redacted summaries, or richer local task records?**

## Context

D3 says: observe **structural metadata only**. Content (prompts, outputs,
tool args) is rejected for v1. So D4 asks about the **depth and shape of the
*metadata** we keep — enough to back a per-task model routing recommendation
with evidence, while staying content-free.

D0 shows the raw axis is coarse (`task=''` main loop vs aux task names). The
workbench's routing value depends on turning that into **task buckets** with
corrected cost and token/quality signals. That's D4's trade.

## Non-negotiable

1. Content-free store: no prompts, source, secrets, raw tool I/O in v1.
2. Local-only write; no export unless you authorize a specific metering.
3. Deterministic + reversible: schema is additive; storable data is describable
   budgets (nothing that reveals prompt content).

## Options

| id | Option | What stored |
|----|--------|-------------|
| M0 | Metadata only (thin) | re-reads `session_model_usage` live; stores nothing new; every report recomputes |
| M1 | Opt-in redacted summaries | cached per-turn aggregate rows (tokens/cost/task) with a redaction pass (like Langfuse `sanitized`); more crossing privacy floor |
| M2 | Rich local task records | local table: task bucket (id/name/user-labeled), model, provider, input/output/cache/reasoning tokens, corrected cost, cache fraction, first/last timestamps, per-(task,model) |

## Evidence

| # | Claim | Source | Conf |
|---|-------|--------|------|
| e1 | Raw meta is coarse on task/dimension in the source store | `session_model_usage` live rows, main loop `task=''` | high |
| e2 | Hermes already computes /aggregates usage (`InsightsEngine`) | `agent/insights.py` | high |
| e3 | Routing needs a task-level ledger with corrected cost to make per-task model choices | D2 routing goal; D3 signal analysis | medium |
| e4 | Redaction is extra machinery we don't need if we store no content | M1 requires a machine; M0/M2 do not | medium |

## Assumptions / unknowns

- Route quality ≈ task-bucket quality (M2) — the tighter the task labels, the
  better the rec. Medium confidence.
- Real cost-corrected usable unit-price is buildable today. Medium.

## Weighted (stable rubric, sum 1.0) — 0–5

| Crt | M0 | M1 | M2 |
|---|---|---|---|
| work_leverage | 3 A | 3 A | 5 A |
| cost_impact | 3 A | 3 A | 5 A |
| quality_pres | 4 A | 4 A | 5 A |
| local/privacy | 5 E | 3 A | 4 E |
| reversibility | 5 E | 4 A | 4 A |
| complexity | 5 E | 3 A | 3 A |
| time_to_value | 3 A | 4 A | 4 A |
| observability | 4 A | 4 A | 5 A |
| extensibility | 3 A | 4 A | 5 A |

**Weighted totals**: M2 4.65 · M0 3.85 · M1 3.60.

M2 (rich local task records) leads because D4's task-centred shape is what
routing actually consumes — and it stays content-free/local/privacy-safe,
unlike M1 which adds a redaction machine for no gain.

## Recommendation

Accept **M2 — rich local task records**: a content-free local ledger keyed by
task bucket, storing (task id/name + user labels), model, provider, token split,
corrected cost, cache fraction, timing — per (task, model). Drop M1 (no content
→ no redaction step). Ship it as an additive local table inside the workbench,
content-free.

## Privacy / security / operational

- M2 keeps content out by construction; a content-free schema is a hard-part of
  the review.
- No network egress; the "store" is a local file/sqlite the user owns.
- Storage is governable — user can truncate/prune partial month rows.

## Implementation consequences

- Define `wf_task_metric` rows (id/name/label, model, provider, provider
  mode, input/output/cache/reasoning, corrected_cost_usd, cache_fraction,
  first_seen,last_seen). Content columns prohibited in schema.
- Feeds D6/D8: the (task, model) × metrics table is the feature set for the
  router classifier.

## Validation

- From 2–3 weeks of Hermes history, build M2 bucket + corrected cost. Sanity:
  thousand-row table reproducible, tasks mergable (unit), no content column
  present in schema; user tasks bucket merges/rechecks.

## Revisit

- Re-open M1 only if a future content-based quality/audit feature (post-D8)
  requires stored context; that's a separate opt-in path, not v1.