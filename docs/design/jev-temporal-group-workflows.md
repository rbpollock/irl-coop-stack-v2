# Jev decision-head for group-authored Temporal workflows

Status: design (spec) · Sep 2026 · Owner: Robbie
Drives from: `docs/decisions/workflow-economics/` (D-series) and the Open-Jev
repo (`/tmp/Open-Jev`, e.g. `examples/workflows/*`, `docs/workflows.md`,
`docs/community-workflow-v3.md`).

## The problem this solves

Groups on irl.coop want to build small, autonomous systems that run *for* them
(provisioning, digests, approvals, escalations, onboarding) with a visual
builder UI — without writing Temporal code and without babysittes each step.
The hard part of such workflows is rarely "run a step"; it is **decide at each
step** from local context + local policy, with no single operator watching and
no model free to just do anything.

A Temporal workflow is a natural fit (already live in the stack — the coop-api
worker). What it needs is a small, deterministic **decision head** at each
branch/approval/action point.

## Why a decision head, and why Jev-shaped

The Open-Jev project is exactly this shape, and it's verified in its own corpus:

- A workflow decision is encoded as a request `{state, questions}` where each
  **candidate action is a typed question** (`noul` yes/no, `choice`, `score`).
  Its workflow cases (customer service, invoice processing, security incidents,
  agent-trace observability) model each action as an *independent* Noul with a
  calibrated probability; a deterministic `selectActions` picks actions above a
  threshold, and **probability 0.5 abstains**. Probabilities need not sum to 1 —
  a workflow can select zero, one, or several actions.
- Type signal: it is **non-generative** — it returns probabilities, never
  natural-language text, so no prompt-text generation noise.
- An **offline deterministic oracle** (`policy_fixture_*`) exists for a pure
  synthetic policy — you can test wiring/rules without calling any model.
- The dataset adds policy-heavy blocks: `community-workflow-v3` is exactly
  an **approval** system: `Choice(permit | deny | review)` plus a `Noul`
  (`is this permitted now?`) over a policy + operations log — i.e. a workflow
  whose "yes, and only a human goes beyond review".

That is *the* interface a Temporal worker wants at a decision node.

## Role in the stack

```
[Group UI: low-code spec] --JSON-->> [Temporal workflow code]
                                        at each decision point ↓
                                  [decision head: Jev or the policy-oracle]
                                        returns {action, probability}
                                            ↓  deterministic rule gate
                      approve?  ----------->  (G0) human approval for any
                      no        (irreversible)  irreversible side-effect
                      |                      (money, publish, provision,
                      yes / high conf                    credentials, delete)
                      |                              |
                   route / apply                       queue to approval
```

Wrapping the stack:
- The **builder UI** lets a group draw a workflow (steps + decision points) and
  generates the Temporal workflow (JSON spec) — a "system that runs for them."
- Each **decision point** is a `{state, questions}` request, the state being the
  group-scoped (RLS) facts the workflow already holds (no full content, no
  leaked cross-group data).
- The **decision head** is either (a) the deterministic `policy_fixture_*`
  oracle (pure rule, no model — use to test), or (b) Open-Jev (2B/9B) when a
  case needs learned judgment.

## Workflow decision mechanics

- For a action set `{A1..An}`: `questions = { "A1": noul..., ...}` → each Ai has
  a probability `p(Ai)`.
- Choose: the orchestration deterministic layer selects `Ai` where
  `p(Ai) > τ` (e.g. τ=0.6); `0.5` abstains → treat as "needs human / more info";
  empty selection → HOLD/REVIEW (mirrors invoice "cannot release any payment").
- **Hard rule overlay (from D7/G0):** if the chosen action is irreversible or
  touches money/publish/creds/delete, it never executes on probability alone —
  it goes to an approval gate (permit/deny/review) with a human binding.

## Concrete uses a group can build first

1. **Member onboarding.** New member in group G → decision: which knowledge
   areas + rooms to grant (from membership facts). Jev scores a small set;
   grants are reversible so auto-route; record to ledger.
2. **Moderated digest.** Decide, per member, which queued items to send
   (audience fit). Reversible/observable; auto-send, with a "flag for review"
   option when near-0.5.
3. **Approvals/dues.** Policy-driven permit/deny/review for group actions —
   mirror the Open-Jev `approval/CMS` case: money or irreversible = human gate.
4. **Escalation laptops.** When consent/fraud/docs missing → HOLD/FRAUD-REVIEW
   instead of partial action (mirrors invoice "short pay … denied").

## Data & privacy
- `state` fed to the head is **group-scoped metadata** from the RL-stepped store
  (Citus) — no cross-group content; local CPU; nothing leaves the host.
- The head never authorizes irreversible side-effecting work; the deterministic
  approval layer (human) sits above it. (D7/G0 boundary.)

## Security/operational mechanics
- The decision head runs local: deterministic oracle for wiring; Open-HJev 2B/9B
  on CPU (probe: loads, typo at 1024, ~12s/decision — keep warm, not per-call).
- `select_actions` is deterministic (threshold); the only coin-flip point is the
  head.
- Audit: every decision (state-hash, questions, probs, chosen action, and the
  approval outcome) is appended content-free to the group's evidence ledger.

## What is explicitly not in scope
- Full autonomy over money/creds/publish (human gate always).
- Storing content/prompts; feeding raw cross-group data to the model.
- Swapping Jev for a generic "AI agent" that can generate actions de novo — the
  candidate actions are authored by the workflow, the head scores only within
  that action set.

## Phasing (small, tested)
1. Ship the **oracle path**: a workflow builder emits a Temporal spec where
  decision points call `policy_fixture_*` (no model). Proves wiring + approval
  gate + audit end-to-end.
2. Switch decision-inference to **local Open-Jev** for the highest-confidence
  classes (onboarding/digest), keeping the oracle as fallback when `p≈0.5`.
3. Every test records pro/antecedent, per-action acceptance and reabd a.
4. Separate (here) review pipeline: for anything irreversible, the human-gate
  only, + Jev merely recommends.

## Risks
- Learned accuracy on a class must be measured per action (mirror D9/M3) before
  an auto-route class goes live without a human. `review`/abstent 0.5 is the
  escape.
- Latency/memory of local 2B vs the RAG host CPU — keep warm, batch.
- The policy authored must match real authority (RLS). Wrong policy → confined.

## Evidence (where these shapes come from)
- `Open-Jev/examples/workflows/invoice_processing.json` (action set per item,
   hold/short-route; the `PAY` Noul shows "missing approval is not
   approval").
- `Open-Jev/docs/workflows.md` (independent actions, threshold, 0.5 abstains,
   `policy_fixture_oracle`).
- `Open-Jev/docs/community-workflow-v3.md` (approval permit/deny/review + CMS
   editorial choices).
- irl.coop stack already runs Temporal (worker: outbox + digests + a proven
   lane) — the executor host exists; this adds the decision head to that fabric.