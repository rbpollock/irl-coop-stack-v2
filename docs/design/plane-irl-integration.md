# Plane + irl.coop Integration Design

**Vision:** Each Plane workspace is owned by ONE irl.coop group.  
**Key Rule:** Projects may belong to MULTIPLE groups (many-to-many), so group membership does not equal workspace membership. A group can participate in a project without owning the workspace.

**Result:** Invite intents are governed by the group that owns the workspace, while access to projects is governed by the group that owns the workspace *and* any other groups attached to the project.

---

## 1. Entity Mapping

### 1.1 New Tables in coop-api DB

```sql
-- Workspace ownership (1:1 with a group)
CREATE TABLE plane_workspaces (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_slug TEXT NOT NULL UNIQUE,
    group_id UUID NOT NULL REFERENCES groups(id),
    plane_instance_url TEXT NOT NULL DEFAULT 'https://plane.irl.coop',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Project many-to-many with groups
CREATE TABLE plane_projects (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID NOT NULL,            -- Plane's project UUID
    workspace_slug TEXT NOT NULL REFERENCES plane_workspaces(workspace_slug),
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, workspace_slug)
);

CREATE TABLE plane_project_groups (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES plane_projects(project_id),
    group_id UUID NOT NULL REFERENCES groups(id),
    added_by UUID REFERENCES users(id),
    added_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, group_id)
);

-- Invite intents
CREATE TABLE plane_invite_intents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES plane_projects(project_id),
    inviter_user_id UUID NOT NULL REFERENCES users(id),
    invitee_email TEXT NOT NULL,
    role INTEGER NOT NULL DEFAULT 5,     -- Plane role: 5=Guest, 15=Member, 20=Admin
    status TEXT NOT NULL DEFAULT 'pending',
        -- pending, approved, rejected, auto_approved, completed, failed
    safe_tx_hash TEXT,                   -- if governed via Safe
    rejection_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    plane_member_id UUID                 -- filled on completion
);
```

### 1.2 Ownership Rules

| Entity | Owner | Governance |
|---|---|---|
| Workspace | One group (workspace owner) | Steward threshold on that group |
| Project | Many groups via `plane_project_groups` | Workspace owner approves new project; other groups join by mutual action |
| Invite | The workspace owner group | Intent flow: inviter → group threshold → execution |
| Member addition | The workspace owner group | Same as invite for external users; direct add for workspace members |

### 1.3 Invariants

- A workspace MUST have exactly one owning group.
- A project MUST belong to at least its workspace's owning group (enforced by trigger).
- An invite intent MUST be approved by the workspace owning group before Plane API is called.
- A user who can prove membership in ANY of a project's linked groups MAY be invited without governance, if the workspace owner group policy allows auto-approve for cross-group members.

---

## 2. Invite Intent Flow

### 2.1 Happy Path

```
[User] clicks "Add member" in Plane project members page
   |
   v
[coop-api] POST /v1/plane/invites/create
   - Validates inviter has badge on workspace owner group
   - Creates plane_invite_intent row (status=pending)
   - Emits event: membership:plane:invite_intent_created
   |
   v
[event bus] Deliver to group pathway runner
   |
   v
[Group governance] Evaluate intent
   - If threshold == 1 OR inviter is steward → auto_approve
   - Otherwise → Safe tx OR proposal vote
   |
   v
[coop-api webhook] Intent approved
   - Calls Plane REST API: POST /workspaces/{slug}/projects/{id}/members/
   - Updates plane_invite_intent → status=completed
   - Emits event: membership:plane:member_added
   |
   v
[Plane] Member appears in project
   [coop-ui] Notifies inviter + invitee
```

### 2.2 Auto-Approve Rules

```typescript
type AutoApprovePolicy = 'steward_only' | 'threshold_one' | 'never';

function shouldAutoApprove(intent, policy): {
    autoApprove: boolean;
    effectiveRole: number;  -- may be downgraded
    requiredThreshold: number;
} {
    // Base case: Admin always requires threshold vote
    if (intent.role === 20) {
        return { autoApprove: false, effectiveRole: 20, requiredThreshold: 2 };
    }

    // External emails always require governance
    if (intent.invitee_is_external) {
        return { autoApprove: false, effectiveRole: intent.role, requiredThreshold: 2 };
    }

    // Cross-group members: auto-approve but cap at Member
    if (intent.invitee_in_participating_group) {
        const role = Math.min(intent.role, 15);  -- cap at Member
        return { autoApprove: true, effectiveRole: role, requiredThreshold: 1 };
    }

    // Policy-based for remaining cases
    if (policy === 'threshold_one') {
        return { autoApprove: true, effectiveRole: intent.role, requiredThreshold: 1 };
    }
    if (policy === 'steward_only') {
        const isSteward = checkBadge(intent.inviter_user_id, intent.owner_group_id, 'steward');
        return { autoApprove: isSteward, effectiveRole: intent.role, requiredThreshold: isSteward ? 1 : 2 };
    }
    return { autoApprove: false, effectiveRole: intent.role, requiredThreshold: 2 };
}
```

Default per workspace owner group:
- `threshold_one` for known irl.coop members (Guest/Member invites)
- `steward_only` for external emails
- **Admin invites always require threshold ≥ 2 regardless of policy**

### 2.3 Rejection Path

```
[Group governance] Rejects intent
   |
   v
[coop-api] Update plane_invite_intent → status=rejected
   - Plane API is NEVER called
   - Rejection reason logged (visible to inviter)
   - Emits event: membership:plane:invite_intent_rejected
   |
   v
[Plane UI] Shows "invite failed" with reason from coop-api
```

### 2.4 Cross-Group Member Auto-Add

If an invitee is already a member of a group linked to the project (via `plane_project_groups`), the intent skips governance and auto-completes — **but role is capped at Member (15):**

```
[coop-api] invitee_email exists in irl.coop
   → Check invitee's group memberships
   → Any overlap with plane_project_groups for this project?
   → YES: auto_approve AT MEMBER (15) → add via Plane API
   → NO: create intent → normal governance
   → REQUESTED ROLE WAS ADMIN (20)?
        → YES: create separate intent for Admin upgrade → threshold vote
        → NO: done
```

This is the **cross-group trust rule:** groups that share a project trust each other's members to access that project. But Admin access (full project control) always requires explicit approval from the workspace-owning group.

**Rationale:** A Guest or Member can only create noise. An Admin can delete the project, remove other members, or expose private data. Admin invites need collective consent.

| Role | Capability | Default Threshold |
|---|---|---|
| Guest (5) | View-only | 1 (steward action) |
| Member (15) | Create/edit issues | 1 (steward action) |
| Admin (20) | Full project control | 2 (threshold vote) |

---

## 3. Feature Gap Strategy

### 3.1 Intake Forms and Email

| Layer | Implementation |
|---|---|
| Public form | Formbricks form → coop-api webhook → creates Plane IntakeIssue via API |
| Email intake | Stalwart inbound rule → script parses email → POST to Plane `/intakes/{id}/issues/` |
| Form mapping | Form fields → Plane issue metadata (labels, priority, state) via config per project |
| Group attribution | Email domain or form field maps to linked group; intake issue gets tagged with group ID |

### 3.2 Workflows and Approvals

**irl.coop replaces Plane's missing workflow engine.**

An "approval" is a group action on the event bus:

```
[intake issue created via form/email]
   |
   v
[event bus] pathway: intake-review
   - Step 1: Group steward notified (Matrix DM)
   - Step 2: Steward approves/rejects via coop-ui
   - Step 3: Approval = Safe tx or threshold vote
   - Step 4: If approved, coop-api calls Plane API:
      PATCH issue state → "In Progress"
      OR POST to cycle/module
   - Step 5: Rejection = Plane issue state → "Cancelled"
```

### 3.3 Customers

| Layer | Implementation |
|---|---|
| Source of truth | ERPNext `Customer`, `Contact`, and `Address` doctypes — these ARE the customer database |
| Link to Plane | `plane_customer_reference` field on `Customer` (custom field) stores the Plane workspace/project mapping |
| UI view | Dashboard widget queries ERPNext REST API (`/api/resource/Customer`) and Plane API, cross-referencing by group |
| Bi-directional sync | coop-api webhook on Plane issue events → ERPNext REST API updates `Customer.plane_activity` custom field |
| Group ownership | Each Customer linked to an ERPNext Company = a group; group membership gates customer access |

**ERPNext setup for this:**
- Add custom fields to `Customer` doctype: `coop_group_id` (link to irl.coop group), `plane_workspace_slug` (data), `plane_priority` (select: Low, Medium, High)
- Add custom fields to `Contact` doctype: `coop_user_id` (data — the blockchain address or email)
- Role mapping: `Sales User` = read customers for their group; `Sales Manager` = manage customers for their group
- Company-per-group: each irl.coop group in ERPNext gets a `Company`, and Customers belong to the Company

**Why ERPNext for customers:** CRM is a native module. No custom table needed. The `coop-api` provisioning script already creates personal Companies on SSO login (see `apps/coop-api/src/erpnext-provision.ts`). Group-scoped access is via Company + User Permission — Frappe's built-in row-level security.

### 3.4 Nested Pages and Project Templates

**Nested Pages** — Plane CE already supports `parent` on the Page model. Use it.

```
Page tree per project:
  └── Runbook (parent=null)
      └── Onboarding (parent=runbook_id)
          └── Day 1 Access (parent=onboarding_id)
```

**Project Templates** — Plane CE has no template feature. Seed instead:

```typescript
// Template = JSON fixture of states, labels, starter issues, modules
type ProjectTemplate = {
    name: string;
    states: Array<{ name, group, color }>;
    labels: Array<{ name, color }>;
    modules: Array<{ name, description }>;
    issues: Array<{ name, description_html, state, labels, priority }>;
};

// API: POST /v1/plane/templates/apply
//  1. Apply template JSON to project via Plane REST API
//  2. Record template usage in coop-api
```

### 3.5 Time Tracking and Initiatives

**Time Tracking** — Plane CE has estimates (story points) but no time logs. Build alongside:

| What | Where |
|---|---|
| Time log records | ERPNext `Timesheet` doctype + `Timesheet Detail` child items — each row = one time log entry linked to an ERPNext `Task` |
| Task link | Each ERPNext `Task` maps to one Plane issue via custom field `plane_issue_id` (stored on Task) |
| Issue link | Time logged to Plane issue = ERPNext Task linked to that Plane issue |
| Reporting | ERPNext native Project/Time reports, plus coop-ui widget for cross-group views |
| Plane display | coop-ui widget reads `Timesheet` via ERPNext REST API and renders time-spent on the Plane issue card |
| Group ownership | Each ERPNext `Project` (not Plane project) maps to an irl.coop group, gating who can log time |

**Initiatives** — Map to Plane Modules with custom metadata:

```sql
-- In coop-api
CREATE TABLE plane_initiatives (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    module_id UUID NOT NULL,                  -- Plane module UUID
    workspace_slug TEXT NOT NULL,
    goal TEXT,
    target_date DATE,
    linked_group_ids UUID[],                  -- which groups share this initiative
    progress_metric TEXT,                     -- e.g., "issues_closed / issues_total"
    created_at TIMESTAMPTZ DEFAULT now()
);
```

Plane Module = the execution layer.  
`plane_initiatives` = the governance + reporting layer (groups, goals, cross-group view).

**ERPNext setup for this:**
- Add custom fields to ERPNext `Task` doctype: `plane_issue_id` (data) and `plane_workspace_slug` (data). These are the bridge fields.
- Add custom fields to ERPNext `Timesheet Detail` child table: `plane_issue_reference` (data), `coop_group_id` (data) — inherited from the Task.
- Each group gets an ERPNext `Project` (not Plane project) for time tracking, mapped via `coop_group_id` custom field.
- Permission: `Projects User` role → can create Timesheets for Tasks in their group's Project.

**Why ERPNext for time tracking:** It's already running in the stack (`workflow-erpnext-*` containers, v16.34.2 on Postgres). It handles billable vs. non-billable hours, cost rates, and native reports. The integration is a custom field link, not a new database table.

---

## 4. API Surface

### 4.1 coop-api Endpoints

```
POST   /v1/plane/invites/create
       body: { project_id, invitee_email, role }
       → { intent_id, status, auto_approved }

PATCH  /v1/plane/invites/{intent_id}/approve
       body: { approver_safe_tx_hash? }
       → { status, plane_member_id }

PATCH  /v1/plane/invites/{intent_id}/reject
       body: { reason }
       → { status }

GET    /v1/plane/invites?project_id=...&status=...
       → Array<PlaneInviteIntent>

POST   /v1/plane/workspaces
       body: { workspace_slug, group_id, plane_instance_url }
       → { id }

POST   /v1/plane/projects
       body: { project_id, workspace_slug, name }
       → { id }

POST   /v1/plane/projects/{project_id}/groups
       body: { group_id }
       → { id }

DELETE /v1/plane/projects/{project_id}/groups/{group_id}
       → 204

GET    /v1/plane/projects/{project_id}/groups
       → Array<Group>

POST   /v1/plane/templates/apply
       body: { project_id, template_name } | { project_id, template_json }
       → { states_created, labels_created, issues_created }
```

### 4.2 Event Bus Schema

```typescript
// membership:plane:invite_intent_created
interface PlaneInviteIntentCreated {
    intent_id: UUID;
    project_id: UUID;
    workspace_slug: string;
    workspace_owner_group_id: UUID;
    inviter_user_id: UUID;
    invitee_email: string;
    role: number;
    auto_approve: boolean;  // true if cross-group member or policy says so
}

// membership:plane:invite_intent_approved
interface PlaneInviteIntentApproved {
    intent_id: UUID;
    project_id: UUID;
    approver_type: 'auto' | 'safe_tx' | 'steward_action';
    safe_tx_hash?: string;
}

// membership:plane:invite_intent_rejected
interface PlaneInviteIntentRejected {
    intent_id: UUID;
    project_id: UUID;
    reason: string;
}

// membership:plane:member_added
interface PlaneMemberAdded {
    project_id: UUID;
    user_id: UUID;
    email: string;
    role: number;
    added_by_intent_id: UUID;
}

// membership:plane:project_group_linked
interface PlaneProjectGroupLinked {
    project_id: UUID;
    group_id: UUID;
    linked_by_user_id: UUID;
}
```

---

## 5. UI Integration

### 5.1 Plane Frontend Patches

**`send-project-invitation-modal.tsx`**
- Add email input field alongside the workspace-member dropdown
- If email matches existing workspace member → direct add (current flow)
- If email is external → call coop-api `/v1/plane/invites/create`
- Show pending state: "Invite intent submitted to group governance"
- Poll coop-api for intent status; update UI on completion/rejection

**Project settings members page (`apps/web/.../members/page.tsx`)**
- Add section: "Cross-group access" showing linked groups
- Warn: "Removing group will revoke access for its members"

### 5.2 Full-kit Dashboard Widgets

| Widget | Data Source | Action |
|---|---|---|
| Pending invites | `plane_invite_intents` where status=`pending` | Approve / Reject |
| Cross-group projects | `plane_project_groups` + `groups` | Link / unlink group |
| Initiative progress | `plane_initiatives` + Plane cycles/modules | View |
| Customer list | ERPNext `Customer` / `Contact` | Link to Plane issues |
| Time log entry | ERPNext `Timesheet` / `Timesheet Detail` | Start / stop timer |

---

## 6. Phase Roadmap

### Phase 1: Invite Intents (Foundation)
- [ ] Create SQL schema (`plane_workspaces`, `plane_projects`, `plane_project_groups`, `plane_invite_intents`)
- [ ] Add coop-api endpoints for invite CRUD + approve/reject
- [ ] Wire event bus emissions for invite intents
- [ ] Patch Plane `send-project-invitation-modal.tsx` to call coop-api
- [ ] Build dashboard widget for pending invites
- [ ] Test E2E: invite → governance → Plane member added

### Phase 2: Cross-Group Projects
- [ ] UI for linking groups to projects (full-kit + Plane settings)
- [ ] Auto-approve rule for cross-group members
- [ ] Sync: when group loses project link, check member eligibility
- [ ] Event bus listener for group membership changes → Plane permissions

### Phase 3: Feature Gaps
- [ ] Formbricks → Plane intake bridge
- [ ] Stalwart email → Plane intake receiver
- [ ] Customer sync (ERPNext `Customer` / `Contact` ↔ Plane)
- [ ] Project template seeder
- [ ] Time log widget (ERPNext `Timesheet` + Plane issue link)
- [ ] Initiative wrapper around Plane modules

### Phase 4: Governance Hooks
- [ ] Safe integration for intent approval (tx hash recording)
- [ ] Proposal voting on non-trivial invite intents
- [ ] Threshold policy per workspace owner group

---

## 7. Open Questions

1. **Auto-approve default:** Should all workspace member additions be auto-approved (`threshold_one`), or should external emails always go through governance?
2. **Group link permission:** Who can link a group to a project? Only workspace owner steward, or any group member acting on their group's behalf?
3. **Member revocation:** When a group is unlinked from a project, do we remove its members from the Plane project or just revoke their future access to new resources?
4. **Plane API credentials:** Store Plane PAT in coop-api env, or per-workspace in DB?
5. **Email domain trust:** Should `@irl.coop` emails always auto-approve vs. external domains?

---

*Document version: 1.0*  
*Plane source reference: `/home/service/plane`*  
*irl.coop primitives reference: `init-db/04-coop-primitives.sql`*
