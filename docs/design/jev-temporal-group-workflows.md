# Decision Engine on Temporal — scope (tightened)

Status: design / spec (phase-1 slice) · Sep 2026 · Owner: Robbie
Prev doc (superseded, too broad): `jev-temporal-group-workflows.md`
Grounds: Open-Jev `{state, questions}` workflow cases + `policy_fixture_*`.

## Goal (one sentence)
Give irl.coop groups a low-code way to author small Temporal workflows whose
"what do I do next" is a **scoped decision**, scored by Jev (or a deterministic
oracle in phase 1) at each decision point.

## Scope — ONE vertical slice first (no breadth)
Do **one** workflow end-to-end before generalizing:

> **Member onboarding.** A new member is added to group G. A workflow grants
> that member the group's knowledge areas + a matrix room, and decides whether
> it can auto-route or must be queued for an admin's approval.

Everything else (digests, dues approval, escalations, invoice-style policy,
cross-group synthesis, RAG-fed state) is **explicitly out of this slice** — listed
in Out-of-scope below so it does not leak in.

## In scope
- A builder UI emits a JSON workflow spec (one workflow on the slice).
- A Temporal workflow iterating that spec, calling a decision point for the
  grant step.
- The **decision head**: phase-1 = deterministic `policy_fixture_*` oracle (no
  model), phase-2 = local Open-Jev 2B/9B behind the same interface.
- The **human gate** (review/deny) for intangible/irreversible.
- Audit to the group ledger (content-free).

## Out of scope (this slice)
- Generic multi-case runner, digests, approvals (CMS), security-incident
  playbooks, invoice D&C.
- Heavy JSON with RAG/full-context; a Jev server fleet; any auto-apply of
  money/publish/creds/delete.
- Cross-group data to the head; storing prompt/content.

## The decision request (this slice, at the grant step)
```json
{ "state": { "group_id": "g", "member": "u", "roles": ["member"],
             "areas": [{"id":"a1","visibility":"group"}],
             "room": "room:g_main" },
  "questions": {
    "grant_area_a1": { "type": "noul", "instructions": "Does membership authorize? grants (RLS scope), default deny." },
    "open_room_plus": { "type": "noul", "instructions": "Also invite to the room?" },
    "queue_admin":     { "type": "noul", "instructions": "Require an admin to review before applying?" }
  }
}
```
- Oracle (phase 1) → deterministic probs (e.g. `grant 0.0` if no group grant, etc.).
- Jev (phase 2) → calibrated probs, `selectActions` above `τ=0.6`; `0.5` abstains;
  an empty selection = HOLD/review.
- The head **never** executes; the workflow maps chosen actions through the
  **gate**: reversible → auto-apply + audit; irreversible → queue for admin.

## Minimal machine
```
Builder (UI) → spec JSON → Temporal workflow
        at the grant step  ─ decision head (oracle→Jev)
                               │ probs (typed)
                       ├ thresholds → auto-apply (reversible) + audit
                       └ else      → queue for admin (human gate), audit
```
Reuses: Temporal worker (already live), Citus/RLS for the scoped facts,
Keycloak for identity. No new model infra for phase 1.

## Phase plan
1. **Oracle-first.** Wish: the builder can emit the onboarding spec and the
   oracle makes the grant/queue decisions deterministically. Acceptance: the
   gate + audit + handler wired; no model in the critical path.
2. **Swap the head.** Give the same request to a single Jev-2B local infer
   (oracle reserved as `.→0.5` fallback). Acceptance: exact same interface,
   the log shows both, and the finite D-series measures per-action acceptance
   before any auto-route class goes live without a human.
3. **Generalize** to other workflows only after (2) holds on the first class.

## Acceptance for the slice
- Oracle path: (a) the UI→spec compiles, (b) a grant and a "queue for admin"
  case both route correctly, (c) ledger rows record state-hash + probs + chosen
  action + gate outcome, content-free.
- Model path: the same runs on Jev; per-action acceptance measured stated in a
  review (no unsupported claim), false-negative recall reported (not just
  accuracy).

## Evidence / source shapes
- `Open-Hex examples/workflows/invoice_processing.json` + `docs/workflows.md`
  (per-action Noul scores; threshold; `0.5` abstains; `policy_fixture_oracle`).
- `docs/community-workflow-v3.md` (approval: permit/deny/review as the gate
  contract).
- The irl stack already runs Temporal (worker: outbox + digests + proven lane).

## Deferred (write later, when slice 1 is green)
- Digest delivery (which items to whom), invoice/dues approvals, security
  playbook dispositions, and multi-workflow builder library.