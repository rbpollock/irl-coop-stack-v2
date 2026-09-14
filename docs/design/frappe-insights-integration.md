# Frappe Insights — opening the stack and/or ERPNext (intent)

**Intent (Robbie, Sep 2026).** Modify **Frappe Insights** so it integrates with the irl.coop
stack and/or with **ERPNext**. Recorded, deliberately not built. This note exists so the intent
is not lost and so the *first* build step is the cheap one rather than an accidental fork.

**Decisions (Robbie, Sep 2026).** **Same Frappe site** as ERPNext; the scope is **accounting
AND the coop ledger** — both, not either; and **row-level ledger data is in scope**, so the
per-member role mapping below is the accepted mechanism rather than an aggregates-only view.

**Status: not built.** No Insights app, route, OIDC client, or data source exists today.

## Why this is unusually cheap here

| Fact | Consequence |
|---|---|
| Insights is a **Frappe app** (`bench get-app insights`) | it installs onto the bench that is **already running** |
| ERPNext is **Frappe v16** (stock `frappe/erpnext:v16.34.2`), already deployed | same framework, same bench, **no second runtime to learn** |
| ERPNext's site DB is the **shared Citus Postgres** (`172.17.0.1:5432`) — validated by spike, no MariaDB | Insights and ERPNext read from the *same Postgres server* |
| ERPNext already carries a **Frappe Custom Social Login Key** against the fleet gateway (`api.irl.coop`) | Insights inherits SSO from the bench rather than growing another login |

So the "and/or ERPNext" leg is not an integration project at all: on one bench, Insights reads
ERPNext's own doctypes (accounting, stock, CRM) with Frappe's own permission model. No ETL, no
connector, no second identity.

## The leg that is actually interesting — and the one that carries a hazard

Frappe Insights takes **Postgres / MySQL / CSV** as data sources. The coop's own store *is*
Postgres, so Insights can point at `irlcoop` directly: dashboards over `tier2_entry`,
`dues_policy` / `dues_waiver`, groups, contributions. That is the reason to want it — **reporting
over the coop's own ledger**, not another accounting chart.

**But a BI tool with a direct connection bypasses RLS, and that is the hazard to design around
before anything is built.** The coop's row security depends on a *session* variable:

```
policies read  sub = coop_current_sub()  -- set per request via withIdentity():
                                          -- set_config('app.sub', $1, true)
```

A BI connection never sets `app.sub`, and the two ways that can go are both wrong:

- **fail-closed:** a role that *is* subject to RLS sees **nothing** (`coop_current_sub()` is null),
  which silently produces empty reports that look like "no data" rather than "no access";
- **fail-open:** hand it a bypassing role (the operator/`coop_ops`-style credential, or a
  superuser) and it sees **every group's rows** — waivers, payment attribution, contribution
  detail. That is the exact disclosure the ledger's privacy rule exists to prevent
  (`dues_waiver` visibility is `sub = coop_current_sub() OR coop_has_grant(group_id,'dues.bookkeep')`).

### The connection CAN respect RLS — the database has to be the one enforcing it

The earlier version of this note said "aggregates only, no rows." That was the answer *without an
identity*: a shared credential has no member attached, so row-level data is unscopeable. Robbie's
question — *can't the connection itself respect RLS?* — has a better answer, and it is worth the
work.

**First, the fact that rules out the easy path.** Insights can apply Frappe's own permissions
("Apply User Permissions"), but its documentation is explicit: *only for **site** data sources,
**not external databases***. And the coop ledger is an external database to the Frappe site:

| | database | to the Frappe site |
|---|---|---|
| ERPNext site (Frappe v16) | `erpnext` | the site DB — Frappe permissions apply |
| the coop ledger | `irlcoop` | **external** — Frappe permissions do NOT apply |

Same Citus server, different database. So for the ledger leg **Insights' permission layer cannot
be the enforcement point**, and neither can "the tool promises to filter" — a tool-side identity
is forgeable and a pooled connection with a sticky `app.sub` leaks across members.

**The mechanism that does work — proposed here, NOT deployed (`coop_role_sub` does not exist and
`coop_current_sub()` still reads only `app.sub`): make a per-member database ROLE be the identity.** Today the
coop's identity comes from exactly one place:

```sql
CREATE OR REPLACE FUNCTION coop_current_sub() RETURNS text LANGUAGE sql STABLE AS $function$
  SELECT NULLIF(current_setting('app.sub', true), '')::text
$function$;
```

Every policy in the system (and all ~40 `coop_*` helpers) calls that one function. So adding a
role→sub mapping scopes **every existing policy at once, with no policy rewrites**:

```sql
-- one row per member role; written only by the owner (coop-api)
CREATE TABLE coop_member_role (
  role_name  name PRIMARY KEY,
  sub        text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);

-- SECURITY DEFINER: the caller never needs SELECT on the mapping
CREATE OR REPLACE FUNCTION coop_role_sub() RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
AS $function$ SELECT sub FROM coop_member_role WHERE role_name = current_user AND revoked_at IS NULL $function$;

-- ROLE WINS. A member role's identity is its mapping, so `SET app.sub = '<someone else>'`
-- cannot impersonate. The app role has no mapping row and falls back to app.sub as before,
-- so coop-api is unaffected.
CREATE OR REPLACE FUNCTION coop_current_sub() RETURNS text LANGUAGE sql STABLE AS $function$
  SELECT COALESCE(coop_role_sub(), NULLIF(current_setting('app.sub', true), ''))::text
$function$;
```

Properties that matter, each of which is the reason for a specific detail above:

- **unforgeable identity** — the role mapping *wins* over the GUC, so `SET app.sub` is not an
  escalation path (any role may set a custom GUC; ignoring it for member roles is the fix);
- **fail-closed by construction** — no mapping and no `app.sub` means `coop_current_sub()` is
  null, and the policies deny;
- **no policy churn** — the single indirection point means this is one function, not forty;
- **revocable and rotatable** — `revoked_at` plus a per-member credential held in the member's
  vault slice, the same "delegation via session keys, never custody" shape used everywhere else;
- **no `SET ROLE` grants** — a member can use only their own role.

Then the BI layer needs that credential **per member**. Two ways, cheapest first:

1. **One data source per member**, restricted to that member by Insights' team/access control
   (`Enable permissions to restrict access…`). Least work; the DB does the enforcing.
2. **A custom Insights data-source type** that authenticates to coop-api as the member and lets
   coop-api set `app.sub` per request — i.e. the *existing* enforcement point is reused, and the
   identity travels per request rather than per connection. More work; works regardless of
   Insights' permission model.

**What this does NOT license**, stated plainly:

- **do not** rely on Insights' Frappe-permission layer for the ledger — it does not apply to an
  external database, and Insights has a documented history of leaking through it regardless
  (issue #919: *restricted users can see data they should not have access to*; PR #1279:
  exploration endpoints could *preview every row of a table that a query over the same table
  would have filtered*);
- **do not** let a pooled BI connection keep a sticky `app.sub` — the identity must be
  transaction-scoped (`SET LOCAL`) or explicitly reset, exactly as `withIdentity()` already does;
- **do not** hand over a bypassing credential (`coop_ops`, a superuser, or `coop_rls`) to make a
  report "work".

For the **accounting** leg the site-DB path is fine — that is company accounting under Frappe's
own model, and it is not the ledger's per-member privacy surface.

## What "modify Insights" could mean — decide this explicitly

"Modify" is ambiguous and the three readings differ by an order of magnitude in cost. Listed
cheapest first:

1. **Declarative install (no fork).** Insights as a Frappe app on the existing bench, plus an app
   spec following the standard recipe (spec → Keycloak/OIDC → Traefik route → regenerate →
   provision client). Uses the bench's existing social-login key, so no new SSO work.
2. **Custom image (the NocoDB / Hi.Events precedent).** Only if Insights needs the gate-SSO
   auto-login the other apps have; that is a bundle-level patch pattern this repo already runs.
3. **Real patches to Insights.** Justified only if group-scoped reporting needs the app itself to
   carry group context — e.g. a coop data-source type that injects `app.sub` per request so
   Frappe's permissions *and* the ledger's RLS both apply. Reach for this last, and only with (1)
   running.

## Open questions (answer before building)

1. **Same site as ERPNext, or a separate Frappe site on the same bench?** Frappe permissions are
   per-site; a separate site isolates reporting but shares the bench's app set. Robbie's recorded
   ERPNext access rule is "any member signs in; tenant permissions gate what they see; their own
   user/self-group is always accessible" — Insights should not weaken that.
2. **Which data is in scope:** ERPNext accounting only, or the coop ledger too? The second drags
   in the RLS hazard above and is where the value is.
3. **Does the one-realm rule hold?** Insights must remain a Keycloak client of the fleet realm;
   it must not grow its own user store. Same for any Frappe-side role mapping: groups are the
   coop's unit, Frappe roles are the app's — the mapping is a decision, not an accident.

## Non-goals

- No second analytics stack, and no second identity.
- Not a reason to relax RLS, and not a place to reintroduce `coop_ops`-style credentials.
- Not a substitute for the coop's own contribution/dues projections — Insights *reads* them.
