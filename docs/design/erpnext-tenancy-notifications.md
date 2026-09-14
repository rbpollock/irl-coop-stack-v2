# ERPNext Tenancy & Notifications — Design

Status: design · Sep 2026 · Author: Robbie + Hermes.
Applies to: ERPNext v16 (frappe v16.34.x) on the shared Citus Postgres,
`accounting.irl.coop` (site `erp`), SSO via the fleet gateway (Social Login Key
`irlcoop` → coop-api `erpnext` client).
Builds on: formbricks-group-mapping (group → app-tenant mapping pattern),
event-bus-and-group-shapes (notification bus), provisioning.ts (JIT provisioning
brain), private-treasury-guards-ledgers (ledger layering: ERPNext = operational
records; Pools/Accounting apps = treasury truth — declared boundary).

## 1. The model in one paragraph

Every member manages their OWN accounting in ERPNext; members of coop groups can
switch into that group's books. ERPNext's accounting tenant is the **Company**
(not "Team" — that doctype is collaboration-only), and switching tenants is the
native **company switcher** in the desk navbar. So: each member's self-group →
their personal ERPNext Company (provisioned at first use); each coop group that
**opts into accounting** → one ERPNext Company named after the group, provisioned
on demand; members of that group get a User Permission row to it and switch in.
Provisioning is driven from coop-api (ERPNext is not behind an oauth2-proxy gate,
so no x-forwarded-groups — the coop side is the source of truth), using an
ERPNext integration identity. ERPNext stays a STOCK image — no custom build.

## 2. Tenant mapping (settled)

| Coop concept | ERPNext object | When |
|---|---|---|
| Member (self-group, `kind=personal`) | `User` (SSO login; no password) + personal `Company` | **First login sync (now)** |
| Coop group seat (`kind=coop`) | `Company` (group name verbatim) + `User Permission` rows for its members | **On demand** — when a group opts into accounting |
| Roles: `owner`/`member`/`agent` | `Accounts User` floor; group `owner` additionally `Accounts Manager` (company-scoped) | mapped at sync |
| Switch group | ERPNext company switcher (native) | — |

Decided (Robbie, Sep 2026): personal Company for every member now; group
Companies created only when a group opts in. Naming: personal
`"<full name> — personal"`; group Companies named after the group verbatim.

### Abbreviation scheme (ERPNext requires a unique `abbreviation`)

- Personal: first 5 alphanumerics of the FIRST name, uppercased — `ROBER`; on
  collision append the last-initial digit (`ROBER2`).
- Group: slug-derived — `slug.replace(/[^a-z0-9]/gi,'').slice(0,5).toUpperCase()`;
  on collision append a digit. (abbreviation max length to verify: 5 chars — ERPNext
  validates; adjust scheme if longer allowed.)

### Defaults for every Company created

`default_currency: USD`, `country: US` (changeable per group later),
`chart_of_accounts: Standard`, `date_of_creation` = today, `is_group: 0`? (single
entity — no parent), `enable_perpetual_inventory: 0` (not running stock for v0).

## 3. Provisioning mechanism (coop-side, idempotent)

Integration identity: ERPNext user **`Coop Sync`** (`coop-sync@irl.coop`),
System Manager role, password = derived secret (`erpnext.sync`), created once by
bootstrap. coop-api calls the ERPNext REST API with it
(`https://accounting.irl.coop/api/resource/…`). Least-priv alternative later:
a scoped role with create rights on User/Company/User Permission only.

Reconcile on **member login** (extension of `provisionOnSignIn`, wrapped in
try/catch — provisioning failure never blocks login):

1. `User` exists (email match) — SSO auto-creates at first ERPNext login anyway;
   ensure `enabled` + first_name from the coop profile.
2. Personal `Company "<name> — personal"` exists (or create with CoA).
3. **User Permission** rows for the personal company (allow) — so a fresh user
   sees exactly their own books, never the whole company list.
4. Group Companies: only those with an opt-in flag set (see §5); when present,
   ensure User Permission rows for each seat.
5. Group `owner` → additionally `Accounts Manager` **scoped via User Permission
   to that Company** (verify: role + User Permission combination, not global
   Accounts Manager).

Drift: a Temporal reconcile (daily, or on group-membership events) re-runs the
same sync for changed seats, mirroring `provisionGroups`' "coop roles = source of
truth, overwrite drift".

## 4. Group opt-in ("enable accounting for this group")

A coop group opts in via the dashboard/groups API → coop-api records
`groups.enable_erp_accounting = true` (+ default currency) → a one-shot
provisioner creates the group Company + User Permissions for existing seats →
future seat changes (add/remove member) update the User Permission set. Members
see the group in the ERPNext company switcher once permissioned. Opt-out:
disable flag (books frozen? decide later: archive vs delete — prefer archive).

### 4.1 Subgroup relationships (parent/child companies — design, not built)

Structure: the group graph's `subgroup-of` edges map onto ERPNext's native
company tree — child group Company gets `parent_company = <nearest ancestor
group with accounting>`, `is_group: 1` on parents with children. ERPNext's
Consolidated Financial Statement rolls children into the parent (native
roll-up, incl. multi-currency conversion). Companies stay one-per-group —
subgroups are expressed as the company TREE, never by merging groups into one
company with cost-centers (that would dissolve the per-group isolation).

Visibility is governance, not graph: `subgroup-of` = namespace/infra sharing;
financial transparency is a SEPARATE declared right on the child edge
(reporting right, from the relationship-registry "set of rights" model).
Defaults:

- Child books are visible only to the child's own seats — never to ancestors
  by virtue of the graph (irl.coop = steward, not root).
- Parent members receive `User Permission (allow: <child Company>)` ONLY when
  the child's edge terms grant a reporting right (opt-in) or the parent holds a
  reserved-powers co-owner seat on the child (which lands as the same
  permission row through the stronger path).
- Roll-up execution = parent's Accounts Manager + child-granted reporting.
- Review-without-edit maps to a scoped custom ERPNext role (read-only on GL
  Entry / Account / Journal Entry / Financial Statement reports via Permission
  Manager), NOT dumping parent members in as child Accounts Manager.
  Open: full-child-rights vs read-only-reviewer for parent members.

Provisioning sequence (Phase 2, after group opt-in): child opts in → coop-api
walks the graph for ancestor-with-accounting → sets `parent_company`/`is_group`
→ grants parent permission rows per the child's declared reporting right →
roll-up becomes available in the parent. The company↔group + parent index
(already planned for notifications) carries the mapping.

## 5. Notifications (ERPNext → the bus)

ERPNext native **Webhook** doctypes (per-doctype events, POST JSON with the doc)
→ coop-api `POST /api/v1/events/ingest` (shared-token auth) → normalize
(Company → group slug via a company→group index table; doc fields) → Redis
pub/sub `irl:notify:{sub}` + notification rows (existing notifications.ts
store), delivered per member preference. v0 event set (per opted-in group):
Sales Invoice submitted/paid, Payment received, Journal approval requests. Inbound
(bus → ERPNext) deferred.

## 6. Phasing

- **Phase 1 (now):** bootstrap `Coop Sync`; coop-api login-sync creates personal
  User + Company + User Permission; verify company switcher + isolation
  (e2e-test sees only their own company; browser E2E via the journey suite).
- **Phase 2:** group opt-in flag + group Company provisioning + seat-change sync
  + dashboard "Accounting" nav submenu per group (mirrors surveys submenu) →
  `accounting.irl.coop/app` w/ native switch inside.
- **Phase 3:** Webhook → ingest → bus; notification preferences.
- **Phase 4 (later):** Temporal reconcile; scoped integration role; currency/
  locale per group.

## 7. Open questions

1. Strict company visibility: does a User Permission (allow: Company) alone hide
   other companies from the switcher, or is role/permission config needed?
   (verify empirically in Phase 1 — the switcher lists companies from user
   permissions once set; confirm exact v16 behaviour.)
2. Abbreviation max length + collision handling (verify against ERPNext
   validation).
3. ERPNext `User` creation outside SSO first-login: needed, or rely on SSO
   auto-create + post-login sync? (prefer: rely on SSO auto-create; coop-api
   reconciles on the ERPNext login webhook-less flow via next login.)
4. Notification event set + per-group choice of events.
5. Group opt-out semantics (archive vs delete Company).

## 8. Notes / pitfalls (from bring-up, keep current)

- Stock `frappe/erpnext:v16.34.2` image; site created by the one-shot
  configurator (`bench new-site --db-type postgres --db-name erpnext` on the
  shared Citus PG). DB role/password are bench-minted in site_config.json.
- Routing: nginx `FRAPPE_SITE_NAME_HEADER: erp` (server_name + X-Frappe-Site-Name
  proxy header); healthcheck curls with that header.
- nginx listens on 8080 (not 80) inside the container — publish maps 8097:8080.
- SSO: Social Login Key `irlcoop` (Custom provider → coop-api endpoints);
  auto-creates users from userinfo `email` + `name` (get_first_name fallback).
- `sign_ups: "Allow"` (Select, not checkbox) on the Social Login Key.
- e2e-test realm password was reset during bring-up (dev value) — reconcile with
  journeys.sh-derived creds before the journey joins the main suite.
- **PG quirk 1 (fixed, schema shim):** frappe v16 `validate_link_filters` calls
  `json.loads()` on docfield.link_filters — MariaDB returns JSON columns as
  strings, Postgres returns native lists → "Invalid Filters for field Supplier
  Group" on any Company create (US regional fixtures re-validate Supplier).
  Shim: `ALTER TABLE "tabDocField" ALTER COLUMN link_filters TYPE text USING
  link_filters::text`. Re-apply if the column is ever recreated as json
  (migrate). This class of bug (json.loads on a PG json column) can recur —
  watch for it in other PG-only code paths.
- **Company creation via REST** on a fresh site needs: (a) Warehouse Type master
  rows seeded first (Transit/Stores/Raw Materials/Finished Goods/Work In
  Progress/Scrap/Rejected/Packaging — each needs an explicit `name` in the
  payload), (b) `country` is mandatory, (c) the abbreviation field is `abbr`
  (NOT `abbreviation` — ERPNext auto-derives if omitted, e.g. "ET—P").
- **setup wizard:** v16's `is_setup_complete()` reads
  `Installed Application.is_setup_complete` per app (frappe + erpnext), NOT
  System Settings — REST-provisioned sites never ran the wizard, so every user
  was bounced to /desk/setup-wizard until both rows were set to 1.
- System Settings is a single doc: field writes need `frappe.client.save` with
  the current `modified` (timestamp guard) — direct `tabSingles` updates are
  simpler for bootstrap (bypasses validators, needs `clear-cache` after).
- REST provisioning identity: ERPNext user `coop-sync@irl.coop` (System
  Manager, derived password `erpnext.sync`). DocField/DocType reads are
  permission-restricted over REST even for System Manager — use the bench-side
  python path (script copied into the backend container, run with the site
  interpreter) for meta/schema inspection.
