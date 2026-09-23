# 0007 — Deterministic safety & approval boundaries (D7)

Status: **accepted** · Owner: Robbie · Date: 2026-09-22
Depends: D2, D6. Blocks D8/D9 auto-routing.
Decision: **G0 (human approval for all v1)**, spend guardrail default **$30/mo, $5/session** (adjustable).

## Decision statement

**What deterministic safety and approval boundaries are mandatory before any
routing or automated action is considered?**

## Context

The workbench (D2) proposes model-per-task recommendations; D5 surfaces them
in-session. Routing becomes *automated action* the moment the system applies a
recommendation without you (e.g. switching model/provider). D7 defines the
**hard, deterministic gates** around any such action. These are not model
judgments: they are pass/fail rules that run first and always.

## The mandatory gate set (HARD_CONSTRAINT — applies at every level, forever)

The following are non-negotiable and independent of any scoring:

1. **No silent application.** No routing/action happens without either your
   explicit approval **or** a previously accepted, deterministic, allowlisted
   rule. Nothing is auto-applied to a task class beyond this.
2. **Never touch these via the workbench:** provider credentials, publish
   state, permissions, roles, production/external services, or a non-trivial
   infra change. These are always human-only outside this workflow.
3. **Spend guardrail.** A hard monthly (and per-session) spend bound is set by
   Robbie; a task model choice that would exceed the bound is a hard-stop
   recommendation, never a bypass. Route recommendations can only *reduce*
   spend within the bound, never raise it.
4. **Change is reversible & instant.** Only actions one config-command can undo
   (e.g. model/provider switch) are eligible for auto-application. Anything
   stateful/long-lived is human-only.
5. **Allowlist, exhaustively.** The set of (task class, model) pairs eligible for
   any auto-route is a closed, declared list — approved once, audited. Everything
   else defaults to *human approval*.
6. **Local-only & content-free.** Routing uses the local D4 task ledger; no
   content egress. (D3.)
7. **Audit trail.** Every applied decision (auto or approved) is appended,
   content-free, to the task ledger: task id/class, from-model → to-model,
   time, cost delta, who-approved/rule-id.
8. **Deterministic first.** A model's score may *recommend*; it may never
   *authorize*. A recommendation that a hard constraint rejects must not be
   applied under any circumstance.

These gates apply to **every** option below; the CHOICE is only *how much* of
the boundary is automated in v1.

## Options (how far automation goes, within the gates)

| id | Policy | v1 behavior | Eligibility |
|----|--------|-------------|-------------|
| G0 | Human approval only | workbench recommends; a user must approve in-session (D5) every application | no auto-apply |
| G1 | Allowlist auto | deterministic, low-risk (task, model) pairs (e.g. title draft → cheap/local) may auto-apply; all else human | auto allowed only for the declared allowlist, under cap |
| G2 | Budget-aware auto | like G1 plus automatic shift-to-cheaper once spend exceeds a declared band | broader auto |
| G3 | Full auto | no approval for most actions | rejected (violates gates 1–8) |

## Why the rubric cannot decide this (important)

Applying the stable rubric gives G1 4.10 · G0 3.95 · G2 3.70 · G3 3.05. G1
"wins" only because it scores higher on time-to-value/leverage. **That is not
the arbiter here**: the rubric has no "safety" axis, and a security gate is
meant to be decided by the deterministic constraints, not by the score. This is
the exact case the operating rules mean by "never let a model score override
security, privacy, budget, or human-approval rules." So D7 is decided by the
gate set + a value judgment from you, not the 4.10.

## Jev-style question set (D7, in types)

```ts
import type { DecisionQuestion } from "./decision-primitives";

const d7: DecisionQuestion[] = [
  // HARD_CONSTRAINTS — deterministic pass/fail gates, never a model judgment.
  { primitive: "HARD_CONSTRAINT", stem: "No routing action is applied without explicit human approval or a previously accepted, declared allowlist rule.", pass: true },
  { primitive: "HARD_CONSTRAINT", stem: "The workbench never touches credentials, publishing, permissions, infra, or external services.", pass: true },
  { primitive: "HARD_CONSTRAINT", stem: "A hard monthly/per-session spend cap is enforced; a recommendation exceeding it is blocked.", pass: true },
  { primitive: "HARD_CONSTRAINT", stem: "Only one-command reversible actions (model/provider switch) are auto-eligible; stateful changes are human-only.", pass: true },
  { primitive: "HARD_CONSTRAINT", stem: "Auto-route is allowed ONLY for a closed, declared (task-class, model) allowlist; everything else is human approval.", pass: true },
  { primitive: "HARD_CONSTRAINT", stem: "Routing uses the local content-free D4 ledger; no content egress.", pass: true },
  { primitive: "HARD_CONSTRAINT", stem: "Every applied decision is audit-logged content-free; a model score never authorizes, only recommends.", pass: true },

  // CHOICE — level of automation permitted inside the gates.
  { primitive: "CHOICE", stem: "Select the v1 automation level within the gate set.", optionIds: ["G0", "G1", "G2", "G3"] },

  // NOUL — bet to test before ever opening auto-route.
  { primitive: "NOUL", proposition: "After the D6 paired-bench, the allowlisted low-risk class reaches quality-parity with the incumbent.", prevalence: 0.5 },

  // ESCALATE — a value/risk judgment, not scoreable.
  { primitive: "ESCALATE", stem: "Approve G0 (human-approval for all v1) and accept that G1 unlocks only after D6+D9 evidence?", why: "The rubric cannot weigh safety; only your risk tolerance can." },
];
```

## Recommendation

For **v1: adopt G0 — all routing is a recommendation + human approval**.
Adopt the full gate set (1–8) now. When D6 demonstrates ≥ quality-parity AND
D9 thresholds are met for the allowlisted class(es), unlock **G1** for exactly
that closed allowlist — nothing else. G2 is deferred; G3 is rejected.

Rationale: v1 has no evidence that routing is safe; auto-apply before evidence
is the whole hazard D7 exists to prevent. G0 is the smallest safe step and is
fully consistent with the measured-evidence goal.

## Human decision required (ESCALATE)

- Choose the v1 level: **G0 (recommended)** vs unlocking G1 and immediately.
- Set the **hard spend cap** (monthly, per-session) the gate set enforces.
- Accept that **G1 allowedlist will only open after D6+D9 evidence**, not now.

## Implementation consequences

- The workbench ships an "approve (y/n) + revert" action in-session (D5).
- A deterministic `gatekeeper` module evaluates each recommendation against
  gates 1–8 including the allowlist and spend cap — returning pass/fail — before
  anything is applied. No recommendation bypasses it.
- Audit rows are appended to the D4 ledger.

## Validation

- **Revert drill:** a simulated model-switch is applied then reverted in ≥1s
  without side effects.
- **Cap test**: a recommendation that would exceed the spend cap is blocked —
  verified by an automated check.
- **Audit test**: every apply (fetch or allow) creates a content-free row in
  the ledger; greppable; no content columns present.

## Revisit

- Re-open the G0→G1 gate only when: D6 quality-parity is measured, D9 thresholds
  pass, and the allowlist + audit are in place. That is the *only* trigger.