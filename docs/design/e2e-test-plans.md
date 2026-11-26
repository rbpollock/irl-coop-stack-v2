# E2E Test Plan: Group Governance + Pathways + Plane Integration

**Harness:** NestJS/Jest in `apps/coop-api/test/`
**Dependencies:** Live Plane CE, ERPNext, Postgres (Citus), Redis bus, Temporal (if pathway worker shipped)
**Isolation:** Each test seeds its own group + workspace + project; cleans up after.

---

## Test Suite 1: Invite Intent Flow

### TS-1.1 Steward auto-approve (threshold=1)
**Pre:** Group G1 exists with threshold=1. Workspace W1 owned by G1. Project P1 in W1. User U1 is steward of G1. Plane PAT available.

**Steps:**
1. POST `/v1/plane/invites/create` as U1, project=P1, invitee="new@irl.coop", role=15
2. Assert response: status=auto_approved, intent_id created
3. Query `plane_invite_intents` — status=completed
4. Query Plane API `/workspaces/{W1}/projects/{P1}/members/` — member exists with role=15

**Expected:** Intent resolves in <3s. Zero human intervention.

### TS-1.2 Threshold vote (threshold=2)
**Pre:** Group G2 with threshold=2. Two stewards: S1, S2. Workspace W2 owned by G2. Project P2.

**Steps:**
1. S1 POST `/v1/plane/invites/create` for P2
2. Assert: status=pending, signatures=[S1]
3. S2 POST `/v1/plane/invites/{id}/approve`
4. Assert: status=approved → executed → completed
5. Plane member exists

**Expected:** Requires both stewards. First creates intent; second triggers execution.

### TS-1.3 Rejection
**Pre:** Group G3, threshold=2. Stewards S3, S4.

**Steps:**
1. S3 creates intent for P3
2. S4 POST `/v1/plane/invites/{id}/reject` with reason="not a member"
3. Assert: status=rejected, reason stored
4. Plane API confirms: no member added

**Expected:** Rejection is immediate and final. Plane untouched.

### TS-1.4 Expiry
**Pre:** Group G4, threshold=2. Intent expiry=2s (test override).

**Steps:**
1. S5 creates intent
2. Wait 3s
3. Query intent — status=rejected (auto)

**Expected:** Auto-rejection on expiry. No orphan intents.

---

## Test Suite 2: Cross-Group Auto-Approve

### TS-2.1 Known member of participating group
**Pre:** G5 owns W5. P5 linked to G5 and G6 (via `plane_project_groups`). Alice is member of G6.

**Steps:**
1. Dave (G5 steward, threshold=2) invites alice@irl.coop to P5
2. coop-api checks: alice@irl.coop → memberships → in G6 → G6 linked to P5
3. Assert: auto_approve=true, no intent created
4. Plane member exists

**Expected:** Cross-group trust rule bypasses governance.

### TS-2.2 Unknown external email
**Pre:** Same setup. Bob is not in any linked group.

**Steps:**
1. Dave invites bob@external.com to P5
2. Assert: status=pending (normal governance, threshold=2)
3. Require both G5 stewards to approve

**Expected:** External emails always go through governance.

### TS-2.3 Member removed from group === removed from project
**Pre:** Alice in G6, in P5. G6 unlinked from P5.

**Steps:**
1. Remove G6 from `plane_project_groups`
2. coop-api sync job: check all P5 members against linked groups
3. Alice's membership: if no linked group includes her → flag for review

**Expected:** Revocation is soft-flag, not hard-delete (to avoid data loss).

---

## Test Suite 3: Pathway + Intent Integration

### TS-3.1 Pathway step blocked by intent
**Pre:** Template "Customer Onboarding" registered. Step 2 = create ERPNext Customer (group-owned).

**Steps:**
1. POST `/v1/pathways/run` with template="Customer Onboarding", inputs={email:"cust@test.com"}
2. Step 1 executes (parse email)
3. Step 2: create Customer for G7 → group-owned → emit intent on bus
4. Pathway worker blocks
5. Steward approves intent
6. Pathway resumes → Step 2 completes → Step 3 (Plane issue)
7. Assert: run status=success, output contains Customer ID and Plane issue ID

**Expected:** Pathway blocks transparently. Resumes after approval.

### TS-3.2 Pathway step with A0 autonomy (instant)
**Pre:** Template registered with autonomy=A0 (assisted).

**Steps:**
1. Run template with A0
2. All steps execute without intents
3. Assert: run completes in <5s

**Expected:** A0 = no governance gating.

### TS-3.3 Pathway step with A3 autonomy (cross-boundary) rejected
**Pre:** Template with A3 step: create issue in Group H's workspace.

**Steps:**
1. Run template → Step creates HandoffEnvelope on `handoffs` channel
2. Group H's ToolGateway receives envelope
3. Group H policy: reject all external issue creation
4. Assert: handoff rejected → pathway step fails → run status=failure

**Expected:** Cross-boundary work respects target group policy.

---

## Test Suite 4: HandoffEnvelope Validation

### TS-4.1 Valid handoff accepted
**Pre:** G8 and G9 have peering edge. G8 allows `plane:create_issue`. G9 allows receiving from G8.

**Steps:**
1. G8 pathway emits HandoffEnvelope for `plane:create_issue`
2. G9 ToolGateway validates: signature ✓, intent in allowlist ✓, params valid ✓
3. Creates intent on G9 bus → steward approves → issue created

**Expected:** Full round-trip: emit → validate → approve → execute.

### TS-4.2 Expired handoff rejected
**Pre:**Same setup. Handoff envelope with expiry=now-1h.

**Steps:**
1. Emit expired envelope
2. G9 ToolGateway rejects: "expired"
3. No intent created

**Expected:** Expiry is strict.

### TS-4.3 Invalid signature rejected
**Pre:** Same setup. Handoff with corrupted signature.

**Steps:**
1. Emit envelope with bad signature
2. G9 ToolGateway rejects: "invalid attestation"

**Expected:** Signature verification is mandatory.

---

## Test Suite 5: ERPNext + Plane Sync

### TS-5.1 Customer created → Plane issue linked
**Pre:** ERPNext reachable. Plane reachable. coop-api provisioned.

**Steps:**
1. Create ERPNext Customer "Test Co" via coop-api
2. coop-api webhook creates Plane intake issue
3. Query Plane: issue exists with label="customer:test-co-id"
4. Query ERPNext: Customer.custom_plane_issue_id populated

**Expected:** Bidirectional link established.

### TS-5.2 Time logged in ERPNext → visible in Plane
**Pre:** Plane issue exists. ERPNext Task linked.

**Steps:**
1. Log 2h in ERPNext Timesheet against Task
2. coop-api sync job updates Plane issue metadata
3. Query Plane API: issue.extra.time_logged_minutes = 120

**Expected:** Time reporting bridges both systems.

---

## Test Suite 6: Proposal + Timeline

### TS-6.1 Create proposal → vote → outcome → execute
**Pre:** Group G10. Members: M1, M2, M3. Stewards: S10.

**Steps:**
1. S10 creates proposal: "Dissolve workspace W10" (high stakes)
2. 48h timeline starts
3. M1 votes yes, M2 votes yes, M3 votes no
4. After deadline: coop-api counts → 2 yes, 1 no → passed
5. Auto-creates intent with pre_approved=true
6. Executes: Plane workspace archived

**Expected:** Full democratic flow. No steward override.

### TS-6.2 Proposal fails → no intent
**Pre:** Same group.

**Steps:**
1. Proposal: "Remove S10 as steward"
2. Votes: 1 yes, 2 no
3. After deadline: failed
4. No intent created

**Expected:** Failed proposal = dead. No automatic retry.

---

## Test Suite 7: Role Capability Enforcement

### TS-7.1 Steward can invite (role=20)
**Pre:** User with Plane role=20 on project.

**Steps:**
1. User tries invite API
2. coop-api reads user's group badge → steward
3. Invite succeeds (with governance if threshold>1)

**Expected:** Role 20 maps to steward action eligibility.

### TS-7.2 Member cannot invite (role=15)
**Pre:** User with Plane role=15.

**Steps:**
1. User tries invite API
2. coop-api reads badge → contributor (not steward)
3. Returns 403: "contributors may suggest invites, not execute"

**Expected:** Strict role enforcement.

### TS-7.3 Guest cannot invite (role=5)
**Pre:** User with Plane role=5.

**Steps:**
1. User tries invite API
2. Returns 403

**Expected:** Guests have no governance rights.

---

## Test Harness Setup

```typescript
// test/governance.e2e-spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import * as request from 'supertest';
import { AppModule } from './../src/app.module';

describe('Group Governance E2E', () => {
  let app: INestApplication;
  let planePAT: string;
  let testGroup: any;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();
    app = moduleFixture.createNestApplication();
    await app.init();

    // Seed test group with threshold=2
    testGroup = await seedTestGroup({ threshold: 2 });
    planePAT = process.env.PLANE_TEST_PAT;
  });

  afterAll(async () => {
    await cleanupTestData();
    await app.close();
  });

  describe('TS-1.1', () => {
    it('steward auto-approves when threshold=1', async () => {
      // ... implementation
    });
  });

  // ... additional describes
});
```

**Seed helpers needed:**
- `seedTestGroup(opts)` → creates group, 2 stewards, workspace, project
- `seedPlaneWorkspace(group)` → calls Plane API to create workspace
- `cleanupTestData()` → removes all seeded rows (cascade delete)

---

## CI/CD Integration

**Run order:**
1. Unit tests (fast, no services)
2. Integration tests (services in Docker compose)
3. E2E tests (this suite) — only in nightly or on `main` merge

**Test data isolation:** Each test file seeds its own group prefix (`test-suite-{timestamp}`). Cleanup runs even on failure.

---

*Version: 1.0*
