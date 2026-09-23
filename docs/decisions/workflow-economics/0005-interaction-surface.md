# 0005 — Smallest report / interaction surface (D5)

Status: **accepted** · Owner: Robbie · Date: 2026-09-22
Depends: D1 (direction O4 workbench), D2 (routing workbench accepted), D4 (rich local task records).

## Decision statement

**What is the smallest report/interaction surface for the workbench in v1 — a
Hermes in-session tool, a Hermes CLI subcommand, a dashboard/desktop UI, or a
generated Markdown report?**

## Context

- The workbench reads the local task ledger (D4 M2) and local inference; in v1
  it **emits decision cards** (recommended model per task + why) — no auto-route
  (D7 gates).
- Robbie states he's **in the interactive Hermes UI often**. That is the key
  context: surface must be callable in-session, not require shelling out or
  opening a browser.
- Hermes already exposes an analogous in-session surface: `/insights` slash
  command. The workbench surface can mirror that pattern.

## Non-negotiable

1. Local-only; no content exported; decision card is metadata-derived.
2. v1 = recommendations only (no auto `model`/provider changes).
3. Surface is additive/reversible (nothing in core).

## Options

| id | Option | Interaction |
|----|--------|------------|
| Sa | Hermes in-session tool | a tool callable in chat (mirrors `/insights`); returns a decision card as text; optionally appends card to a repo Markdown record |
| Sb | Hermes CLI subcommand | `hermes wf-econ <report|decision>` — must leave the session |
| Sc | Dashboard/desktop tab | a dashboard widget (like the achievements tab); leave chat |
| Sd | Generated Markdown only | a repo file written by a cron/tool; read outside session |
| Se | Deferred / no surface | workbench is internal only, no UX in v1 |

## Evidence

| # | Claim | Source | Conf |
|---|-------|--------|------|
| e1 | Robbie is in the interactive UI often | this thread (explicit) | high |
| e2 | Hermes already has an in-session surface pattern (`/insights`) | `cli.py:14224` | high |
| e3 | A Markdown decision record is already the workspace's convention | `docs/decisions/...`, README | high |
| e4 | Dashboard/tab is a larger build (Electron/web) | achievements requires a dashboard tab; heavier | medium |

## Weights (stable) & scores (0–5, confidence implied)

| Crt | Sa | Sb | Sc | Sd | Se |
|---|---|---|---|---|---|
| work_leverage | 4 A/h | 3 A/m | 3 A/m | 2 A/m | 2 A |
| cost_impact | 3 A | 3 A | 2 A | 2 A | 2 A |
| quality_pres | 4 A | 3 A | 3 A | 3 A | 3 A |
| local_first | 4 E | 4 E | 4 E | 5 E | 5 E |
| reversibility | 4 E | 4 E | 3 A | 5 E | 5 E |
| complexity | 4 A | 4 A | 2 A | 5 E | 5 E |
| time_to_value | 4 A | 3 A | 2 A | 5 | 2 |
| observability | 4 A | 3 A | 4 A | 2 | 3 |
| extensibility | 4 A | 3 A | 4 A | 3 | 3 |

**Weighted totals**: Sa 3.85 · S(markdown) 3.60 · Sb 3.35 · Se 3.35 · Sc 3.25.

Sa (in-session tool) leads — the surface matches where Robbie already works.
Markdown alone is a cheap record but isn't interactive; a dashboard is heavy.

## Recommendation

Accept **Sa — a Hermes in-session tool** (callable in the interactive UI) as
the primary surface, with a **secondary Markdown append** so each decision card
also lands in `docs/decisions/workflow-economics/` as a durable record (D-series
records already live there). Nothing besides: no CLI subcommand, no dashboard in
v1.

- How: a Hermes tool/slash surface that runs the local workbench and returns:
  per-task recommended model + why (corrected cost, cache, quality proxy), i.e.
  a decision card. User reviews and applies; workbench never auto-applies (D7).

## Human decision required

- Approve Sa as the surface (plus Markdown record queue) — i.e. the workbench is
  directly usable inside Hermes, not a shell tool. Recommendation yes.

## Implementation consequences

- Extend the local workbench + a thin command wrapper same family as `/insights`.
- Write the card also to a Markdown file (option-current-cards) using the D4 ledger.

## Validation

- In-session produce a decision card from 2–3 weeks; 5 sessions sanity-check the
  recommended task→model against manual judgment; reviewers see the Markdown
  record appended.

## Revisit

- If evidence/ada shows a dashboard gives more value than in-chat, revisit.