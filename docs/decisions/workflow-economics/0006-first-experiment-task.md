# 0006 — First low-risk experiment task class (D6)

Status: **accepted** · Owner: Robbie · Date: 2026-09-22
Depends: D4 (task ledger), D5 (in-session surface).

## Decision statement

**Which one low-risk task class is the first candidate for a measured
local/cheaper model experiment?**

## Context

The workbench routes tasks to models based on evidence. Before touching any
higher-blast-radius task, pick ONE class that is low-risk (no state changes),
high-frequency, easily verifiable, and where a local/cheaper model plausibly
meets the quality bar. Running the experiment gauges the whole loop: measure →
compare → decision → routing intent. Findings also seed the D8 router's first
task label.

## Non-negotiable

1. No auto-route; output is reviewed by the user (D7 gates any apply).
2. Content stays local; uses past Hermes records + candidate model only for the
   test, output is on-screen/decision card.
3. Reversible & measurable: paired run with a written comparison of the same
   past tasks.

## Options

| id | Task class (examples) | Risk profile |
|----|------------------------|--------------|
| Oa | Commit/title/changelog/message drafts | Output is discarded text; never edits; easy to check |
| Ob | Code snippet explanation/summarization | Reads files; checkable; medium |
| Oc | Diff/code review comment summarization | Reads diffs; medium |
| Od | Web research summarization | Higher token; error-prone if summarize wrongly |
| Oe | Test-writing scaffolding | Wrong tests worse than none; high blast if accepted blindly |

## Evidence

| # | Claim | Source | Conf |
|---|-------|--------|------|
| e1 | Short-text gen is already a real, observable task (`task='title_generation'` rows) | `session_model_usage` live rows | high |
| e2 | It is high-volume + uses little input/output per unit → a clean comparator | token figures in state.db | high |
| e3 | Output is trivially reversible (text you can discard, not apply) | task shape (a.k.a. draft) | high |
| e4 | A low-risk class is the de-risker: proves quality bar before routing | D2/D7 reasoning | med |

## Assumptions / unknowns

- A local cheap model hits adequate bar for these drafts (to measure). Medium.
- Volume exists enough to get a sign-out sample within 2 weeks (depends on
  usage; aux-task rows are there).

## Weights (stable) & scores (0–5)

| Crt | Oa | Ob | Oc | Od | Oe |
|---|---|---|---|---|---|
| work_leverage | 4 A/h | 4 A/m | 3 A/m | 3 A/m | 3 A/m |
| cost_impact | 4 A | 3 A | 3 A | 4 A | 2 |
| quality_pres | 4 A/h | 3 A/m | 3 A/m | 3 A/m | 2 A/m |
| local_privacy | 4 E | 5 E | 5 E | 5 E | 5 E |
| reversibility | 5 E | 5 E | 4 A | 3 A | 3 A |
| complexity | 5 E | 4 A | 4 A | 3 A | 3 A |
| time_to_value | 5 E/h | 4 A/m | 4 A/h | 3 A | 3 A |
| observability | 5 E | 4 E | 4 E | 4 E | 4 E |
| extensibility | 4 A | 4 A | 4 A | 3 | 3 |

**Weighted**: Oa 4.50 · Ob 4.05 · Oc 3.70 · Od 3.45 · Oe 3.10.

## Recommendation

Accept **Oa: commit/title/changelog/message drafts** as the first measured
local/cheaper-model experiment. Cheap, high volume, trivially reversible, and
it validates the whole workbench loop on a task Hermes already does
(`title_generation`), before any bigger blast area. Use paired past tasks:
run the same input through the current model and the candidate local/cheaper
one, then compare accept/reject + cost + latency (D9 threshold).

Note: the raw spend saved by re-routing titles is small; the **real value is
preparing the measurement/routing harness** safely.

## Implementation consequences

- Extend the local workbench for a "paired-bench" mode on a sampled basket of
  past `title_generation`/draft records.
- Surface a comparison decision card in-session (D5).

## Validation

- ≥20 sample tasks; ≥80% of output judged acceptable (or equal to incumbent).
- Deterministic: results in a reproducible JSON + report table; ≥2 week window.
- Compare price + latency, show savings and quality trade per example.

## Revisit

- After ~2 weeks, revisit whether the harness should move to the next class
  (Oa → Ob) for the routing map.