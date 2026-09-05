# Formbricks ↔ irl.coop group mapping

Status: design · Sep 2026 · Builds on irl-coop-group.md (the group primitive, seats,
roles) and the Formbricks gate-SSO build (formbricks-gate-sso skill reference).

## 1. The two models, side by side

**Formbricks v5.4.0 tenant model** (Prisma `main.prisma`):

```
Organization  (top tenant: billing, whitelabel, AI tools)
├── Workspace   (where surveys live — holds Projects/Surveys)
│   └── Project  (a survey environment)
└── Team        (RBAC unit — a named group of users)
    ├── TeamUser     (teamId, userId, role: admin|contributor)
    └── WorkspaceTeam (teamId, workspaceId, permission: read|readwrite)
```

**irl.coop group** (irl-coop-group.md): a group Safe with **seats** — the universal
membership primitive `{sub, alias, roles[], visibility, matrixId, joinedAt}`. Roles:
`founder / admin / member / inviter / observer`. "The group is the primitive, not the
user."

## 2. The mapping

```
coop (irl.coop)        → 1 Organization  ("irl.coop")
coop group             → 1 Team          (name = group name, keyed by group slug)
coop group             → 1 Workspace     (the group's survey workspace — group-private)
group seat (member)    → TeamUser        (role mapped, see §3)
team → its workspace   → WorkspaceTeam    (permission from role)
```

Key decisions this embodies:

1. **Group → Team, not Organization.** One coop Organization, N teams (one per
   group). Mapping to Organization would create N billing/whitelabel tenants;
   the Team layer is the right RBAC granularity and is exactly what the
   `AUTH_SSO_DEFAULT_TEAM_ID` SSO default expects.
2. **Group → Team AND Workspace (group-private surveys).** Each group gets its own
   survey workspace, reachable only by that group's team via `WorkspaceTeam`. This
   is the "group-aware" scoping Robbie wants — a group's surveys are invisible to
   other groups. (Alternative: a shared coop workspace with per-survey ACLs — more
   complex, rejected for v1.)
3. **Deterministic + idempotent**, mirroring the group model's own principle. Team
   and Workspace are keyed by the group slug; provisioning is a convergent function
   run on every gate-SSO (same as `ensureGroupSeat`).

## 3. Role mapping

Actual coop group roles today: `owner`, `member`, `agent` (the richer
`founder`/`admin`/`inviter`/`observer` taxonomy in irl-coop-group.md is planned,
not yet in the seat index). `platform-admin` / `telephony-admin` are
platform-scoped (on the personal seat), not group roles — ignored here.

| coop role | TeamUser role | WorkspaceTeam permission | OrganizationRole |
|---|---|---|---|
| `owner` (or future `founder`) | `admin` | `manage` | `owner` |
| (future `admin`) | `admin` | `manage` | `manager` |
| `member` / `agent` | `contributor` | `readWrite` | `member` |
| (future `observer`) | `contributor` | `read` | `member` |

`agent` collapses to `contributor`/`readWrite` for v1 (no finer Formbricks
permission). The richer tiers (observer read-only, founder-vs-admin) activate
when the seat index gains those role names.

## 4. Provisioning flow (gate-SSO)

Today the gate-SSO route (`apps/web/app/api/auth/gate-sso/route.ts`) only
find-or-creates the **user** by `x-forwarded-email`. The group mapping extends it:

1. Resolve the member's coop groups (see §5).
2. For each group: find-or-create `Team` (keyed by slug) + its `Workspace` +
   the `WorkspaceTeam` link.
3. Upsert `TeamUser` (role from §3).
4. Redirect into the member's **default group** team (or the group they clicked
   through from, via a `callbackUrl` hint).

Idempotent — rerunning on every login converges (matches invite-on-first-signin).

## 5. How gate-SSO learns the member's groups (the mechanism)

Two options; **A is preferred**:

- **A — id_token `groups` claim + oauth2-proxy header.** coop-api mints a `groups`
  claim (array of `{slug, name, roles[]}`) into the id_token for the
  `formbricks-gate` OIDC client; oauth2-proxy forwards it with
  `--oidc-groups-claim=groups --pass-user-headers` → `x-forwarded-groups` JSON.
  gate-SSO reads that header. No extra HTTP hop; the group info rides the existing
  JWT. (The comment at auth.ts:197 already anticipates `--oidc-groups-claim`.)
- **B — gate-SSO calls coop-api.** A `GET /api/v1/me/groups` (or a service-token
  internal endpoint) keyed by the forwarded email. Simpler to wire, but adds a
  server-to-server hop + a coop-api auth path for the Formbricks container.

## 6. What exists vs what's new

| Piece | Status |
|---|---|
| Formbricks Team/TeamUser/WorkspaceTeam schema | ✅ exists (v5.4.0) |
| gate-SSO user find-or-create by email | ✅ exists |
| coop-api group seats + roles (`/api/v1/groups`, `/api/v1/me`) | ✅ exists |
| `groups` claim in the id_token (JSON `{slug,name,roles}[]`) | ✅ built + verified (2026-09-02) |
| oauth2-proxy `--oidc-groups-claim=groups` header forwarding | ✅ built + deployed |
| gate-SSO team/workspace/TeamUser provisioning | ✅ built + verified (owner→admin/manage/owner) |
| gate-SSO `?group=` → workspace redirect (clickthrough) | ✅ built + verified (slug→`/workspaces/<id>`) |
| Dashboard per-group nav submenu (`useGroups` + sidebar) | ✅ built (compiled clean) |
| In-app group switch | ✅ native — the workspace switcher lists each group's workspace |

## 7. Settled decisions (Robbie, Sep 2026)

1. **Workspace scoping** → group-private workspace per group. Each group gets its own
   survey workspace reachable only by its team (cross-group invisibility).
2. **Default landing** → clickthrough. The dashboard nav link carries a `?group=<slug>`
   hint; gate-SSO drops the member into the group they clicked through from.
3. **Direction** → both ways, staged. **First: group → team** (coop group drives the
   Formbricks team; provisioning on SSO). **Later (more involved): team → group** — a
   Formbricks "create team" action that mints a coop group (Safe + seats + Matrix
   provisioning via coop-api), the reverse provisioning flow.
4. **Role drift** → coop roles are the source of truth. Every SSO overwrites TeamUser
   role + WorkspaceTeam permission from the coop seat roles (the group model's
   two-layer rule: coop is truth, Formbricks is a projection).
