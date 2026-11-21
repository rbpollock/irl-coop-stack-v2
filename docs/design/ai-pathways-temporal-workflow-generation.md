## 
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

## 1.x Workflow Composition — Workflows Calling Workflows

A workflow is not limited to activities. It can call other workflows as
**child workflows** or **sub-workflows**. This enables composition: small,
versioned, reusable workflows that groups assemble into larger processes.

### Child workflow example

```yaml
# workflows/proposals/grant-application.yaml
name: grant-application
version: 1.0.0
steps:
  - name: draft-proposal
    workflow: draft-proposal          # ← calls another workflow
    inputs:
      funder: "{{inputs.funder_id}}"
      amount: "{{inputs.amount}}"
    output: proposal_doc

  - name: internal-review
    workflow: group-review            # ← calls workflow with group-local policy
    inputs:
      doc: "{{steps.draft-proposal.output}}"
      required_approvals: "{{group_settings.workflow_policy.approve.threshold}}"
    output: approved_proposal

  - name: submit-to-funder
    activity: safe.transfer
    to: "{{inputs.funder_address}}"
    amount: "{{inputs.matching_amount}}"
    condition: "{{steps.internal-review.output.approved}}"

  - name: notify-board-on-failure
    workflow: board-notification      # ← reusable notification workflow
    inputs:
      subject: "Grant application failed"
      body: "Funder: {{inputs.funder_id}}, Step: {{failure.step}}"
    condition: "{{failure}}"
```

### Sub-workflow orchestration (saga pattern)

A parent workflow runs multiple child workflows and compensates if any fail.

```yaml
# workflows/proposals/budget-allocation.yaml
name: budget-allocation
version: 1.0.0
steps:
  - name: allocate-line-items
    parallel:                          # ← fan-out to multiple child workflows
      - workflow: allocate-line-item
        inputs: { category: "soil", amount: 5000 }
      - workflow: allocate-line-item
        inputs: { category: "water", amount: 3000 }
      - workflow: allocate-line-item
        inputs: { category: "labor", amount: 12000 }
    output: allocations
    on_failure:
      compensate:
        - workflow: reverse-allocation
          inputs: "{{steps.allocate-line-items.output}}"

  - name: notify-accountants
    workflow: notification-broadcast
    inputs:
      channels: ["#finance", "#ops"]
      message: "Budget allocated: ${{steps.allocate-line-items.output}}"
```

**Why compose workflows instead of activities?**

| | Activities | Child Workflows |
|---|---|---|
| **Granularity** | Single operation (DB query, API call) | Multi-step process with its own state |
| **Versioning** | Tied to worker deployment | Independent version per workflow |
| **Governance** | All activities run under parent policy | Child workflow enforces its own group policy |
| **Retry** | Single retry policy | Child can have its own retry, timeout, rollback |
| **Audit** | Logged as parent execution step | Full independent audit log + parent reference |
| **Forkability** | Cannot be reused across groups | Child workflow can be blessed as canonical |

### Cross-group workflow calls

A workflow in **Group A** can call a child workflow defined in **Group B**.
This is the federation use case:

```yaml
# detroit-soil workflow
trigger:
  type: event
  event_type: soil_survey.complete
steps:
  - name: request-peer-review
    workflow: portland-water/peer-review    # ← cross-group call
    inputs:
      survey_id: "{{inputs.survey_id}}"
      scopes: ["soil_moisture", "ph_level"]
    federation:
      trust_required: A2
      timeout: 7d
      fallback:
        workflow: notify-board
        message: "Peer review from Portland timed out"
```

**How it works:**
1. Detroit's Temporal worker sees `workflow: portland-water/peer-review`
2. It looks up Portland's node address in `group_federations`
3. Sends a `HandoffEnvelope` to Portland's federation gateway
4. Portland's Temporal worker executes the child workflow under Portland's policy
5. Result returns via the federation gateway, signed by both Safes
6. Detroit's parent workflow continues with the signed result

**Governance note:** The child workflow runs under **Portland's** group policy,
not Detroit's. If Portland requires Safe approval for `peer-review` workflows,
Detroit's parent workflow waits until Portland's Safe votes.

### The workflow registry enables composition

```typescript
// coop-api/src/workflows/registry.ts
export async function resolveWorkflow(
  name: string,
  callerGroup: string
): Promise<WorkflowRegistration> {
  // 1. Check local registry
  const local = await db.query(
    "SELECT * FROM workflow_registry WHERE name = $1 AND group_id = $2",
    [name, callerGroup]
  );
  if (local.rows.length) return local.rows[0];

  // 2. Check for cross-group reference (group/name syntax)
  const [targetGroup, targetName] = name.split("/");
  if (targetGroup && targetName) {
    // Verify federation link exists
    const fed = await db.query(
      "SELECT * FROM group_federations WHERE home_group_id = $1 AND foreign_group_id = $2",
      [callerGroup, targetGroup]
    );
    if (!fed.rows.length) throw new Error(`No federation link to ${targetGroup}`);

    // Fetch workflow spec from foreign node (or local cache)
    return await fetchForeignWorkflow(targetGroup, targetName);
  }

  // 3. Check canonical registry (on-chain)
  const canonical = await CoopRegistry.workflows(name);
  if (canonical && !canonical.revoked) return canonical;

  throw new Error(`Workflow ${name} not found`);
}
```

### Version compatibility in composition

When a parent workflow calls a child workflow, version compatibility is checked:

```yaml
# Parent specifies acceptable child versions
steps:
  - name: draft-proposal
    workflow: draft-proposal
    version_constraint: ">=1.0.0 <2.0.0"   # semantic version range
    inputs: ...
```

If the child workflow's current version is outside the range, the parent
either:
- **Fails** (default — parent must be updated)
- **Falls back** to the last compatible version (if still registered)
- **Prompts** the group via the dashboard: "Child workflow version mismatch. Update parent?"

### The Workflow Studio visualizes composition

```
[Workflow Studio — "Grant Application"]

┌──────────────┐      ┌─────────────────┐      ┌─────────────────┐
│ draft-proposal│─────▶│  group-review   │─────▶│ safe.transfer   │
│   (child)     │      │    (child)      │      │   (activity)    │
└──────────────┘      └─────────────────┘      └─────────────────┘
       │                                               │
       │  [click to expand]                            │
       ▼                                               ▼
┌──────────────┐                              ┌─────────────────┐
│ draft-doc    │                              │ notify-board    │
│ review-loop  │                              │   (child)       │
│ finalize     │                              │   on failure    │
└──────────────┘                              └─────────────────┘

[+] Add child workflow  [→] Expand/collapse  [🔒] Version constraint
```

Double-clicking a child workflow node expands it inline to show its own steps.
Double-clicking again collapses it. Version constraints appear as badges on
child nodes.



## 2. Multi-Party, Real-Time Generation

Workflows are not typed by one person at a terminal. They emerge from
**collaborative work** — a group chat, a video call, a shared document, or a
Plane task — and the AI assists in real time.

### 2.1 Source: Group Chat (Matrix)

In a Matrix room, a member says:

> alice: "We need to automate the monthly membership renewal. Send a reminder,
> wait 30 days, then mark them active or lapsed."

The coop bot (Hermes) listens and replies with a draft spec:

```
hermes-bot: Draft workflow spec from this conversation:
  Name: annual-membership-renewal
  Trigger: cron (1st of month)
  Steps:
    1. fetch-member
    2. send-reminder (bus.publish membership.reminder)
    3. sleep 30d
    4. check-renewal
    5. mark-active OR mark-lapsed + notify-board
  Idempotency key: membership-renewal:{member_id}:{YYYY-MM}

Reply with:
  "@hermes lgtm" to freeze this draft
  "@hermes add step ..." to extend it
  "@hermes remove step 3" to cut it
```

Bob replies:

> bob: "@hermes add step: if member responds during the wait, finish early."

Hermes updates the draft inline. The conversation *is* the requirements
document. When three unique members reply with "@hermes lgtm", the draft is
frozen and enters the validation pipeline.

**Audit artifact:** The frozen spec includes a `provenance` block:

```yaml
provenance:
  source_type: matrix_chat
  room_id: "!abc123:matrix.irl.coop"
  event_ids: ["$evt1", "$evt2", "$evt3", "$evt4"]
  participants: ["@alice:irl.coop", "@bob:irl.coop", "@carol:irl.coop"]
  frozen_at: "2026-11-20T15:30:00Z"
```

The Pathways run references these event IDs. Anyone can re-read the chat and
see exactly who said what.

---

### 2.2 Source: Video Call (LiveKit)

During a group video call, the AI transcribes the conversation and extracts
action items. The call moderator toggles on "workflow capture mode."

```
[livekit-ai-transcript]

Robbie (14:32): "We should have something that watches the soil sensors.
If moisture drops below 20%, send an alert to the farm channel."

Jessica (14:35): "And if it stays low for more than 2 hours, trigger the
irrigation valve."

Robbie (14:37): "Yes, but only if the valve was not already triggered in
the last 6 hours."

---

Hermes captures this and posts to the call chat:

Draft workflow: soil-moisture-irrigation
  Trigger: sensor.reading (moisture < 20%)
  Steps:
    1. bus.publish alert to #farm
    2. wait 2h
    3. check valve-status (dedup: 6h window)
    4. trigger valve if not recently triggered

Participants: Robbie, Jessica
Vote to freeze: [ ] Robbie [ ] Jessica
```

Both attendees click the checkbox in the call UI. The spec is frozen. The
audio transcript is archived as the provenance record.

**Audit artifact:**

```yaml
provenance:
  source_type: livekit_call
  room: "detroit-soil-farm-call-2026-11-20"
  transcript_hash: "sha256:abc..."
  participants: ["robbie@detroit.coop", "jessica@detroit.coop"]
  frozen_at: "2026-11-20T14:40:00Z"
```

---

### 2.3 Source: Shared Document (NocoDB / Webstudio)

A group collaboratively edits a spec document in ONLYOFFICE. The
document has a special "workflow spec" block type that validates against the
schema registry as people type.

```
[Shared doc: "Detroit Soil — Irrigation Automation"]

Robbie edits:
  trigger: sensor.reading < 20%

Jessica edits:
  steps:
    - alert #farm
    - wait 2h
    - trigger valve (dedup 6h)

The document shows:
  [✓] Schema valid
  [✓] Activities found in catalog
  [⚠] No rollback defined for valve trigger

Carol comments: "Add rollback: close valve if moisture recovers?"

Jessica adds:
  contingency:
    rollback:
      - activity: valve.close if sensor.reading > 40%
```

When all three participants click "Propose for Approval," the document state
is snapshotted as the spec.

**Audit artifact:**

```yaml
provenance:
  source_type: shared_document
  doc_id: "oo-doc-47/irrigation-spec"
  version: 12
  editors: ["robbie", "jessica", "carol"]
  comments: ["c-1", "c-2", "c-3"]
  frozen_at: "2026-11-20T16:15:00Z"
```

---



### 2.4 Source: Form Submission (Formbricks / NocoDB Form / Web Form)

A group publishes a form: "Propose a new workflow." Members fill in fields
that map directly to the workflow spec schema.

```
[Form: "Propose a Workflow" — hosted at forms.detroit.irl.coop]

Workflow name: ____________
What triggers it? [ ] Cron  [ ] Event  [ ] Manual
Describe the steps: (long text)
What data does it need? (key-value pairs)
What happens if it fails? (long text)
How long should it wait? (duration)
Who should be notified? (group roles)

---

Submission by: robbie@detroit.coop
Submitted at: 2026-11-20 10:00 EST
```

The form backend (Formbricks or NocoDB) posts the submission to the workflow
draft API. Hermes parses the free-text "Describe the steps" into structured
YAML, then asks clarifying questions via reply email or Matrix DM.

```
hermes-bot: Draft from your form submission "Irrigation Alert":
  Trigger: sensor.reading (moisture < threshold)
  Steps:
    1. alert #farm-channel
    2. wait 2 hours
  Clarifying questions:
    - What is the moisture threshold? (you said "low" — is that 20%?)
    - Should the workflow trigger more than once per day?
    - What happens if the sensor goes offline?

Reply to this message to refine the draft.
```

The form submitter (and any named co-authors) can reply to refine. When the
submitter clicks "Looks good — freeze it" in the form response UI, the spec
is frozen.

**Form vs. Shared Doc distinction:**
| | Shared Doc (ONLYOFFICE) | Form (Formbricks / NocoDB Form) |
|---|---|---|
| **Participants** | Multiple editors, real-time | Single submitter + named co-authors |
| **AI role** | Drafts in real time as people type | Parses free-text after submission, asks async questions |
| **Freeze** | All editors click "Propose" | Submitter confirms in form UI |
| **Best for** | Complex, negotiated workflows | Structured, templated proposals |
| **Audit** | Document version + comments | Form submission ID + reply thread |

**Audit artifact:**

```yaml
provenance:
  source_type: form_submission
  form_id: "formbricks-detroit/workflow-proposal"
  submission_id: "sub_abc123"
  submitter: "robbie@detroit.coop"
  co_authors: ["jessica@detroit.coop"]
  clarifications: [2, 3, 5]  # form reply IDs
  frozen_at: "2026-11-20T15:30:00Z"
```

### 2.5 Source: Plane Task

A Plane task is created with the label `workflow-proposal`. The task
description and comments become the spec source.

```
[Plane task #1847: "Auto-renew membership workflow"]

Description (Robbie):
  "When a member's renewal date approaches, send them a reminder email.
  Wait 30 days. If renewed, mark active. If not, mark lapsed and notify
  board."

Comment (Jessica):
  "What if they respond on day 5 with a question? We should finish the
  workflow early if they renew."

Comment (Robbie):
  "Good catch. Add an early-exit condition."

Comment (Carol):
  "Also, don't send reminders to members who already renewed in the last
  7 days. That's annoying."

---

Hermes watches Plane tasks with `workflow-proposal` label. When all assignees
(marked as "approval required") add the comment "lgtm", the spec is assembled
from the task + comments and frozen.

**Audit artifact:**

```yaml
provenance:
  source_type: plane_task
  task_id: "detroit-soil/1847"
  comments_included: [1, 2, 3, 4, 5]
  approvers: ["robbie", "jessica", "carol"]
  frozen_at: "2026-11-20T17:00:00Z"
```

---

### 2.5 The Freeze Mechanism

No matter the source, the spec is **frozen** when:

| Source | Freeze trigger |
|---|---|
| Matrix chat | 3 unique members reply "@hermes lgtm" to the draft |
| LiveKit call | All participants click "Approve draft" in call UI |
| Shared doc (ONLYOFFICE) | All editors click "Propose for Approval" |
| Form submission | Submitter confirms in form UI after AI clarification |
| Plane task | All task assignees comment "lgtm" |
| Any source + A2/A3 | Workflow is auto-frozen after a Pathways gate-profile check |

Once frozen, the spec gets a `provenance` block and enters the validation
pipeline. The original conversation/document/task remains visible and
unchanged — it is the audit trail.

---

### 2.6 AI Generation from Conversation Context

The AI does not just transcribe. It:

1. **Extracts intent** from natural language: "send them a reminder" → `bus.publish membership.reminder`
2. **Identifies gaps**: If no timeout is mentioned, asks "How long should we wait?"
3. **Suggests idempotency**: "Should this run once per member per month? Yes → `membership-renewal:{id}:{YYYY-MM}`"
4. **Proposes contingency**: "What if the member cancels during the wait?"
5. **Validates against schema**: Rejects `activity: send_email` if no `send_email` activity exists in the catalog

The AI is a **facilitator**, not an author. It drafts, questions, and validates.
The humans decide.

---


### 2.6 Source: Dashboard Web UI (irl-coop Workflow Studio)

The irl-dashboard includes a dedicated **Workflow Studio** surface—a visual,
node-based workflow builder where group members can create, edit, preview,
and manage workflows without leaving the browser.

```
[irl.coop dashboard → "Workflows" tab → "New Workflow"]

┌──────────────────────────────────────────────────────────────┐
│  Workflow Studio                              [Share] [Run]  │
│                                                              │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐         │
│  │  Trigger │─────▶│  Step 1  │─────▶│  Step 2  │         │
│  │  (cron)  │      │ fetch    │      │ notify   │         │
│  └──────────┘      │ member   │      │ board    │         │
│                    └──────────┘      └──────────┘         │
│                         │                                    │
│                         ▼                                    │
│                    ┌──────────┐                             │
│                    │  Step 3  │                             │
│                    │  wait    │                             │
│                    │  30d     │                             │
│                    └──────────┘                             │
│                                                              │
│  [+] Add step  [✓] Validate  [💾] Save draft  [🚀] Propose  │
│                                                              │
│  Collaborators: robbie ● jessica ○ carol ○                 │
│  Group scope: detroit-soil (✓)  portland-water ( )          │
└──────────────────────────────────────────────────────────────┘
```

#### Visual builder features

| Feature | What it does |
|---|---|
| **Node palette** | Drag-and-drop activities from the catalog (db.query, bus.publish, sleep, conditional) |
| **Schema validation live** | Red borders on invalid connections; green check when valid |
| **Collaborative cursors** | Multiple group members edit the same workflow graph in real time (like Figma) |
| **AI assist panel** | Side panel where members type natural language; AI suggests node additions |
| **Group scope selector** | Choose which groups can trigger this workflow (default: creator group only) |
| **Version diff** | Compare v1.2 vs v1.3 side by side before proposing |
| **Test run** | Dry-run against sandbox data without registering to Temporal |
| **History view** | See all past executions, which step failed, what data flowed through |
| **Rollback trigger** | One-click "Rollback last execution" with confirmation Safe vote |
| **Revoke** | One-click "Revoke workflow" — blocks all future triggers |

#### Freeze from the dashboard

When the workflow is ready, the creator clicks **"Propose for Approval."**
This opens a side panel:

```
Propose "annual-membership-renewal" v1.0.0

  [Review spec YAML] [Review generated TS] [View tests]

  Required approvers (2 of 3 app-stewards):
    [ ] Alice  [ ] Bob  [ ] Carol

  [Cancel]                            [Send for Approval →]
```

The Pathways run starts automatically. As stewards vote, the dashboard shows
real-time status: "Waiting for Alice and Bob." Once threshold is reached,
the workflow is registered on-chain and deployed to Temporal.

**Dashboard Web UI vs. other sources:**

| | Dashboard Web UI | Matrix Chat | LiveKit Call | ONLYOFFICE Doc | Form | Plane Task |
|---|---|---|---|---|---|---|
| **Real-time collab** | Yes (cursors) | Yes (messages) | Yes (transcript) | Yes (editing) | No (async) | No (async) |
| **Visual builder** | Yes (nodes) | No (text) | No (text) | No (text) | No (form fields) | No (text) |
| **AI assist** | Side panel, live | Bot replies | Transcript extraction | Inline suggestions | Post-submission parsing | Comment parsing |
| **Group scope** | Explicit selector | Implicit (room) | Implicit (call) | Implicit (doc share) | Form config | Implicit (project) |
| **Best for** | Complex, visual workflows | Quick ideas | Meeting outcomes | Negotiated specs | Templated proposals | Task-driven work |
| **Freeze trigger** | Creator clicks "Propose" | 3x lgtm | All approve | All editors propose | Submitter confirms | All assignees lgtm |

**Audit artifact:**

```yaml
provenance:
  source_type: dashboard_web_ui
  session_id: "ws-20261120-abc123"
  creator: "robbie@detroit.coop"
  collaborators: ["jessica@detroit.coop"]  # real-time edits
  group_scope: ["detroit-soil"]
  frozen_at: "2026-11-20T18:00:00Z"
  canvas_snapshot_cid: "QmCanvas..."  # screenshot or graph JSON at freeze time
```

## 3. Governance Model — Group-Local by Default, On-Chain for Federation

The audit trail and governance settings for workflows are **group-local** by
default. They live in Postgres under group RLS. On-chain records are used
only when a workflow is meant to be shared, forked, or trusted across groups.

### 3.1 Group Settings for Workflow Governance

Every group configures its own workflow policy in `group_settings`:

```sql
CREATE TABLE group_settings (
  group_id          uuid PRIMARY KEY REFERENCES groups(id),
  workflow_policy   jsonb NOT NULL DEFAULT '{
    "propose": ["member"],
    "freeze_threshold": {"type": "count", "value": 2},
    "approve": {"type": "safe", "safe_role": "workflow-custodians"},
    "max_risk_tier": 2,
    "require_idempotency_test": true,
    "require_contingency_plan": true,
    "on_chain_for": ["canonical", "cross_group"]
  }'::jsonb
);
```

**Policy fields:**

| Field | Meaning | Example values |
|---|---|---|
| `propose` | Who can propose a workflow | `"member"`, `"steward"`, `"role:organiser"` |
| `freeze_threshold` | How many approvals to freeze a draft | `count: 2`, `count: 3`, `majority` |
| `approve` | Who gives final approval | `safe: "workflow-custodians"`, `threshold: 3`, `any_admin` |
| `max_risk_tier` | Highest allowed risk tier without escalation | `1`, `2`, or `3` |
| `require_idempotency_test` | Must pass simulation before approval | `true` / `false` |
| `require_contingency_plan` | Must define rollback/fallback | `true` / `false` |
| `on_chain_for` | Which workflow types go on-chain | `["canonical"]`, `["canonical", "cross_group"]`, `[]` |

A small mutual-aid group might set: any two members can freeze, one admin
approves, nothing goes on-chain. A federation hub might set: stewards freeze,
Safe threshold approves, canonical workflows go on-chain.

**RLS enforcement:**

```sql
CREATE POLICY group_settings_read ON group_settings
FOR SELECT USING (group_id = coop_current_group());

CREATE POLICY group_settings_write ON group_settings
FOR UPDATE USING (
  group_id = coop_current_group()
  AND coop_current_safe_role() IN ('admin', 'governance')
);
```

Only members of the group can read or change its workflow policy.

---

### 3.2 Audit Trail in Postgres (Group-Local)

Every workflow action is recorded in the group-local audit trail. This is the
**primary source of truth** for day-to-day governance.

```sql
CREATE TABLE workflow_audit_log (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id        uuid NOT NULL REFERENCES groups(id),
  workflow_name   text NOT NULL,
  workflow_version text NOT NULL,
  event_type      text CHECK (event_type IN (
    'draft_created', 'draft_frozen', 'validation_passed', 'validation_failed',
    'approval_requested', 'approval_granted', 'approval_denied', 'revoked',
    'deployed', 'execution_started', 'execution_completed', 'execution_failed',
    'rollback_triggered', 'forked_from'
  )),
  actor_id        uuid REFERENCES users(id),      -- who did it
  actor_safe      text,                            -- Safe role if applicable
  payload         jsonb,                           -- event details
  provenance      jsonb,                           -- conversation/doc/call artifact
  created_at      timestamptz DEFAULT now(),
  UNIQUE (group_id, workflow_name, workflow_version, event_type, created_at)
);

-- RLS: members can only see their own group's audit log
CREATE POLICY workflow_audit_read ON workflow_audit_log
FOR SELECT USING (group_id = coop_current_group());

-- RLS: only system processes and approved actors can write
CREATE POLICY workflow_audit_write ON workflow_audit_log
FOR INSERT WITH CHECK (group_id = coop_current_group());
```

**What gets logged:**

| Event | Payload includes | Provenance includes |
|---|---|---|
| `draft_created` | spec YAML, AI prompt | source_type, creator |
| `draft_frozen` | frozen spec hash | event_ids, transcript_hash, doc_version, task_comments |
| `validation_passed` | validator reports | CI run IDs |
| `approval_granted` | voter address, signature | Pathways run ID |
| `deployed` | Temporal namespace, task queue | deployment artifact hash |
| `execution_failed` | error message, step number | execution trace |
| `rollback_triggered` | rollback steps executed | compensation results |

**The audit log is append-only.** There is no UPDATE or DELETE policy. If a
workflow is revoked, a `revoked` event is appended. The full history is always
recoverable.

---

### 3.3 On-Chain Record (Optional, for Federation)

On-chain registration is **not the default**. It is used only when:

1. **Canonical blessing:** The app-stewards subgroup blesses a workflow as
   part of the canonical set (like a canonical app).
2. **Cross-group trust:** A workflow created by Group A is meant to be
   auditable and forkable by Group B without Group B having to trust Group A's
   Postgres server.
3. **Revocation broadcast:** A revoked canonical workflow must be blocked
   network-wide, not just in one group's Postgres.

```solidity
// CoopRegistry.sol — OPTIONAL entries for cross-group workflows
struct WorkflowRegistration {
    bytes20 groupId;           // which group owns this workflow
    bytes20 gitCommit;
    bytes20 approvedBy;        // group Safe or app-stewards Safe
    bytes32 specHash;          // keccak256(yaml spec content)
    bytes32 auditRoot;         // Merkle root of Postgres audit log
    uint8 riskTier;
    uint256 approvedAt;
    bool revoked;
    bool canonical;            // true = blessed by app-stewards
}
mapping(string => WorkflowRegistration) public workflows;
```

**Key differences from earlier drafts:**

| | OLD model | NEW model |
|---|---|---|
| Default | Everything on-chain | Group-local Postgres by default |
| Governance | Global app-stewards Safe | Each group's own policy |
| Audit trail | IPFS provenanceCID only | Postgres append-only log + optional on-chain Merkle root |
| Cross-group trust | Assumed | Explicit opt-in per workflow |
| Revocation | On-chain transaction | Group-local `revoked` event in audit log; on-chain only for canonical |

**The Merkle root (`auditRoot`):** Instead of pinning the entire conversation
to IPFS, the group computes a Merkle root of its Postgres audit log entries
for that workflow and anchors it on-chain. Other groups can request the full
audit log, verify the Merkle root, and trust the history without trusting the
hosting group.

---

### 3.4 Pathways Integration (Group-Local Accountability)

The Pathways run for workflow approval is scoped to the **group**, not the
global app-stewards.

```yaml
# pathways/templates/approve-workflow.yaml (group-local variant)
name: approve-workflow
version: 1.0.0
autonomy: A2
# Gate profile is READ from the group's own policy
gate_profile:
  source: group_settings.workflow_policy
steps:
  - name: verify-provenance
    executor: provenance-checker
    script: |
      assert spec.provenance.participants >= group_settings.workflow_policy.freeze_threshold.value
      assert spec.provenance.frozen_at is not null

  - name: lint-spec
    executor: ci-runner
    script: make lint-workflow-spec SPEC=$spec_path

  - name: static-security-scan
    executor: workflow-security-scanner
    script: scan-workflow-spec $spec_path
    outputs:
      - risk_score

  - name: schema-validation
    executor: schema-validator
    script: validate-workflow-schema $spec_path

  - name: idempotency-simulation
    executor: temporal-test-runner
    script: make test-workflow-idempotency SPEC=$spec_path

  - name: contingency-check
    executor: static-analyzer
    script: make check-contingency SPEC=$spec_path

  - name: group-approval
    executor: safe-vote
    config:
      # The Safe address comes from the group's own workflow-custodians Safe
      safe_address: "${{group_settings.workflow_policy.approve.safe_role}}"
      threshold: 2  # or read from Safe's actual threshold
      proposal: |
        Approve workflow ${{spec.name}} v${{spec.version}}
        Group: ${{group_id}}
        Risk tier: ${{security_scan.risk_score}}
        Audit log: workflow_audit_log/${{group_id}}/${{spec.name}}/${{spec.version}}

  - name: write-audit-record
    executor: db-insert
    script: |
      INSERT INTO workflow_audit_log (group_id, workflow_name, workflow_version,
        event_type, actor_safe, payload, provenance)
      VALUES (${{group_id}}, ${{spec.name}}, ${{spec.version}},
        'approval_granted', 'workflow-custodians', ${{approval_payload}}, ${{spec.provenance}});

  - name: optional-on-chain-anchor
    executor: base-transaction
    condition: |
      group_settings.workflow_policy.on_chain_for.includes(spec.classification)
    script: |
      CoopRegistry.registerWorkflow(
        groupId=group_id,
        name=spec.name,
        version=spec.version,
        specHash=keccak256(yaml_content),
        auditRoot=merkle_root(workflow_audit_log, group_id, spec.name, spec.version)
      )

  - name: register-with-temporal
    executor: temporal-cli
    script: temporal workflow register --spec $spec_path --group ${{group_id}}
```

**Note:** The `optional-on-chain-anchor` step only runs if the group policy
says so. Most groups will skip this entirely.

---

### 3.5 The Provenance Record (Group-Local, Not IPFS)

The provenance of a workflow draft is stored in the Postgres audit log, not
pinned to IPFS by default.

```yaml
# Stored in workflow_audit_log.provenance as JSONB
provenance:
  source_type: matrix_chat
  room_id: "!abc123:matrix.irl.coop"
  event_ids: ["$evt1", "$evt2", "$evt3", "$evt4"]
  participants: ["@alice:irl.coop", "@bob:irl.coop", "@carol:irl.coop"]
  frozen_at: "2026-11-20T15:30:00Z"
  # The actual Matrix events are fetched from the group's Matrix server
  # (not from IPFS). Other groups can request them via federation gateway.
```

**For cross-group verification:** If another group wants to audit this
workflow's history, they request the audit log from the source group via the
federation gateway. The source group returns the log entries + a Merkle proof
that they hash to the on-chain `auditRoot` (if anchored). No IPFS needed for
the common case.

**IPFS is still available as an opt-in backup.** A group can configure:

```yaml
# group_settings.workflow_policy
backup_provenance_to_ipfs: true
```

This pins the provenance artifact to IPFS for redundancy, but the primary
source of truth remains the group-local Postgres + optional on-chain Merkle
root.

---

---

## 5. The Complete Lifecycle (Multi-Party, Group-Local)

| Stage | Actor | Source | Action | Output | Location |
|---|---|---|---|---|---|
| 1. Converse | Group members | Chat / call / doc / form / task / dashboard | Discuss need, AI drafts in real time | Living draft | Conversation surface |
| 2. Freeze | Participants | Same source | Approve draft | Frozen spec + provenance | workflow_audit_log (draft_frozen) |
| 3. Validate | CI pipeline | Frozen spec YAML | Security, schema, idempotency, contingency | Pass/fail report | workflow_audit_log (validation_passed/failed) |
| 4. Review | Group Safe / custodians | Pathways run | Threshold vote per group policy | Approval signature | workflow_audit_log (approval_granted) |
| 5. **Anchor (optional)** | executor | On-chain (if policy says so) | `CoopRegistry.registerWorkflow()` | `auditRoot` + `specHash` | Base L2 (only for canonical/cross-group) |
| 6. Deploy | executor | Temporal CLI | Register workflow type + task queue | Live workflow | Temporal server |
| 7. Trigger | Event bus / cron / user | Any valid trigger | `HandoffEnvelope` to Temporal worker | Workflow execution | Temporal + event bus |
| 8. Monitor | Dashboard | Temporal + event bus | Real-time status, rollback alerts | Live view | Dashboard + workflow_audit_log |
| 9. Revoke | Group Safe / custodians | On-chain or local per policy | `CoopRegistry.revokeWorkflow()` or local `revoked` event | All triggers blocked | workflow_audit_log (+ Base L2 if canonical) |
| 10. Fork | Any group | Request audit log via federation | Copy spec, modify, propose in new group | New workflow lineage | New group's workflow_audit_log |

**Key principle:** The Postgres audit log is the **primary** record. On-chain
is the **optional anchor** for cross-group trust. Groups that never federate
never pay gas.

---

---

## 6. Implementation in the Stack

### New services

```
apps/coop-api/src/workflows/
  proposals/              # Frozen specs awaiting validation
  generated/              # AI-generated TypeScript (auto-committed)
  activities/             # Reusable activity implementations
  tests/                  # Idempotency + contingency tests
  registry.ts             # On-chain registry client

apps/coop-api/src/chat/
  hermes-bot.ts           # Matrix bot that drafts workflows from chat
  freeze-handlers.ts      # "lgtm" / "approve" message handlers

apps/coop-api/src/calls/
  livekit-transcript.ts   # LiveKit transcript → draft workflow
  call-ui-api.ts          # Endpoints for call-UI draft display

apps/coop-api/src/docs/
  doc-workflow-block.ts   # ONLYOFFICE workflow spec block type
  doc-snapshot.ts         # Snapshot doc state at freeze time

apps/coop-api/src/plane/
  task-workflow-label.ts  # Watch Plane tasks with `workflow-proposal` label
  comment-parser.ts       # Extract spec from task description + comments

apps/web/irl-dashboard/src/app/(dashboard-layout)/workflows/
  page.tsx                # Workflow list + management
  studio/page.tsx         # Visual node-based builder
  [id]/page.tsx           # Single workflow detail + history
  [id]/run/page.tsx       # Dry-run against sandbox data
  components/
    WorkflowCanvas.tsx    # React-Flow node graph
    NodePalette.tsx       # Draggable activity nodes
    AIPanel.tsx           # Natural language → node suggestions
    ApprovalPanel.tsx     # Safe vote status, propose button
    ExecutionHistory.tsx  # Past runs, step-level logs
    ScopeSelector.tsx     # Which groups can trigger this workflow

temporal/
  worker.ts               # Verifies HandoffEnvelope before execution
  gateways/               # Pathways HandoffEnvelope → Temporal bridge
```

### New API endpoints

```typescript
// POST /api/workflows/draft/chat
// Body: { room_id, draft_yaml }
// Hermes bot calls this when a draft is ready in Matrix

// POST /api/workflows/draft/call
// Body: { call_room, transcript_segments, draft_yaml }
// LiveKit AI calls this during workflow capture mode

// POST /api/workflows/draft/doc
// Body: { doc_id, version, draft_yaml }
// Called when all editors click "Propose for Approval"

// POST /api/workflows/draft/task
// Body: { task_id, comments, draft_yaml }
// Called when all assignees say "lgtm"

// POST /api/workflows/freeze
// Body: { source_type, source_id, spec_yaml }
// Freezes the draft and starts the validation pipeline

// GET /api/workflows/:name/provenance
// Returns: { spec, provenance, on_chain_record, ipfs_content }
```

### New CLI commands

```bash
# Replay a conversation that created a workflow
coop-cli workflow provenance --name annual-membership-renewal

# Fork a workflow from another group
coop-cli workflow fork --from detroit-soil/annual-membership-renewal   --name portland-water/annual-membership-renewal

# Dry-run a workflow against test data
coop-cli workflow simulate --spec workflows/proposals/irrigation.yaml   --input '{"moisture": 15}'
```

---

## 7. Open Questions (Updated)

1. **Conversation privacy vs audit trail:** If a workflow is drafted in a
   private video call, is the transcript retained in group-local Postgres or
   purged after the workflow is approved? The audit log must record *that*
   the conversation happened, but does it need the full transcript?

2. **Who can freeze?** In a Matrix room with 50 members, the freeze threshold
   is a group policy. Should it be configurable per room, or uniform per group?

3. **What if participants disagree?** Alice wants step 3, Bob wants it removed.
   The draft cannot freeze until consensus. Does the AI propose a merged
   version? Does the Pathways run arbitrate?

4. **LiveKit transcript accuracy:** If the AI mishears "20%" as "25%," the
   workflow is wrong. Should critical values be double-checked before freeze?

5. **Forking across groups:** A Portland group forks Detroit's workflow and
   modifies it. Portland requests Detroit's audit log via the federation gateway.
   Can Detroit refuse? Should there be a standard "audit request" protocol?

6. **Audit log retention:** A group produces 1000 workflows per year. The audit
   log grows indefinitely. Should there be a policy to archive old entries to
   MinIO / Glacier? What happens to the on-chain Merkle root if entries are
   pruned?

7. **Form schema drift:** If the form fields change, do previously-submitted
   drafts become invalid? Should the form version be part of the `provenance`?

8. **Dashboard canvas durability:** If a user spends 2 hours building a
   workflow and their browser crashes, is the draft autosaved server-side?

9. **Real-time AI load:** During a 10-person video call, the AI must
   transcribe, extract intent, draft YAML, and validate schema in real time.
   Does this run on-device, on the node, or via an external inference provider?

10. **Group policy enforcement:** What prevents a compromised group admin from
    changing the workflow policy to `approve: any_admin` and quickly blessing a
    malicious workflow? Should policy changes themselves require a higher
    threshold (e.g., main group Safe, not just the workflow-custodians Safe)?

---

---

## Summary

| Dimension | How it is enforced |
|---|---|
| **Multi-party generation** | Chat, call, doc, task — any collaborative surface can spawn a workflow |
| **Real-time AI assist** | AI drafts during conversation, asks clarifying questions, validates schema |
| **Freeze mechanism** | Spec is frozen when participants approve (threshold varies by source) |
| **Provenance** | Conversation artifact pinned to IPFS; referenced in `CoopRegistry` |
| **Security** | Static AST scanner + activity allowlist + RLS policy comparison |
| **Versioning** | Semantic versions + git commit + `CoopRegistry.specHash` + Temporal task queue |
| **Idempotency** | Mandatory `idempotency.key` + `workflowId` pre-hashing + double-trigger tests |
| **Contingency** | Mandatory `on_failure`/`on_timeout` handlers + saga compensations + rollback validation |
| **Accountability** | Pathways run with Safe threshold vote + on-chain registration + `HandoffEnvelope` signatures |
| **Forking** | Any group can fork another group's workflow, with full lineage attribution |

AI facilitates. Humans decide. Pathways records. Validators enforce. Temporal
executes. The group stays in control.
## Summary

| Dimension | How it is enforced |
|---|---|
| **Multi-party generation** | Chat, call, doc, form, task, dashboard — any collaborative surface |
| **Real-time AI assist** | AI drafts during conversation, asks clarifying questions, validates schema |
| **Freeze mechanism** | Spec frozen when participants approve (threshold set in group policy) |
| **Governance** | **Group-local** — each group sets its own propose/approve/threshold policy |
| **Audit trail** | **Postgres** append-only log under group RLS; full history, no deletion |
| **On-chain** | **Optional** — only for canonical or cross-group workflows; Merkle root anchors Postgres log |
| **Provenance** | Conversation artifacts referenced in audit log; fetched from group's own Matrix/File server |
| **Security** | Static AST scanner + activity allowlist + RLS policy comparison |
| **Versioning** | Semantic versions + git commit + `specHash` + Temporal task queue versioning |
| **Idempotency** | Mandatory `idempotency.key` + `workflowId` pre-hashing + double-trigger tests |
| **Contingency** | Mandatory `on_failure`/`on_timeout` handlers + saga compensations + rollback validation |
| **Accountability** | Pathways run with group-local Safe threshold + audit log + optional on-chain anchor |
| **Forking** | Any group can fork another group's workflow by requesting their audit log via federation |

**The core principle:** Groups govern themselves. Their audit trail is theirs.
On-chain is for when they choose to trust other groups.