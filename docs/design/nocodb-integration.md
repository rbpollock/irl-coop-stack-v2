# NocoDB integration — goals, and per-user identity at the connection layer

**Status: design (current-best, grounded in the running system).** NocoDB is the member-facing
spreadsheet over the coop projection. Today it is blank — not from any single failure, but from an
unfinished chain whose last link was never verified. This doc records the target, the settled
principles, and the goals, from the spike + the running image + this session's design work.

## What the spike proved (read-only, 2026-09-14)

| fact | result |
|---|---|
| NocoDB's `pg` driver reaches Citus (`postgres:5432` = `172.21.0.8`, same `storage_default` net) | ✅ |
| `nocodb` role can CONNECT to `irlcoop` / `plane` | ✅ |
| `nocodb` role has **zero** table privileges on `irlcoop` | ✅ (safe, empty) |
| every meaningful `irlcoop` table is `FORCE ROW LEVEL SECURITY` | ✅ the true gate |
| a **plain** view over `groups` (read by the shared role) | ⚠️ **returned all 17 rows — bypasses RLS** (view runs as owner) |
| a **scoped** view (WHERE narrowed to one member's groups) | ✅ returned the correct 3-row slice |

**The security lesson the spike teaches:** a naive `SELECT * FROM t` view *defeats* RLS (it executes
with the owner's privilege). Every projection table/view NocoDB reads must be **explicitly
narrowed** — a bare view is precisely the leak that hands all groups to whoever logs in.

## The current (deployed) architecture — what actually exists

The `nocodb-custom-build` skill records that the image already carries **per-user identity injection**:

- The oauth2-proxy gate (`--pass-user-headers=true`) forwards `X-Forwarded-User` = the Keycloak `sub`.
- A bundle patch (image **2026.08.4**+) wraps queries in an AsyncLocalStorage and issues
  `SELECT set_config('app.sub', '<sub>', false)` before each query, `RESET app.sub` after — so a
  **shared** `coop` role is *impersonated* per-request.
- `create-coop-source.{sh,mjs}` mounts `irlcoop` as a live external pg source; the projection surface
  is `groups`, `group_members`, `resource_scopes`, `events`, `notification_reads`,
  `notification_digests`.

So the projection *design* exists. The open question is whether it was ever **wired and verified**
end-to-end — the "0 sources" observed may mean the source was never created, or lives in
`nc_integrations_v2` (the correct table) rather than the one probed, or was lost to a regenerate.
**First action, before any new build: verify the deployed source/base/identity-injection actually
exist and render per-user rows.** Do not build on an assumption.

## The settled principle this session reached (replaces the injection patch)

The injected-GUC model is fragile (documented foot-guns: pooled-connection leak, spoofable `app.sub`,
a shared role that must be impersonated). The cleaner target:

> **OAuth terminates at the edge (Keycloak → oauth2-proxy). Postgres authenticates the
> already-verified principal via `ident`/`peer` or a client `cert` — never a password. Each member
> *is* their own role at the connection layer, so `current_user` **is** the identity and RLS needs no
> injection. If a tool (NocoDB) can't surface per-request identity to open a per-user connection,
> we patch it to.**

Points that make this correct, each learned this session:

1. **OAuth belongs at the edge, not in Postgres.** Postgres has no native OAuth; the gate already
   does it. The question is only how the *already-verified* identity reaches the DB as *authentication*.
2. **`ident`/`peer` or a client `cert` are the non-password methods.** A `cert` is a *key*, not a
   typed secret — it can be the member's passkey / ECDSA / vault-held key (the custody model already
   settled for the Safe and the vault). No password to leak into NocoDB's plaintext store.
3. **Per-user *role* ≠ per-user *password*.** A role is a cheap name + a `coop_member_role` mapping
   row (`role → sub`); it is authoritative (role wins over any claimed GUC, so `SET app.sub` cannot
   impersonate) and needs no secret. We rejected per-user *passwords* (they'd land plaintext in
   NocoDB) but *kept* per-user *roles*.
4. **`coop_role_sub()`** (proposed in the Frappe/Insights thread, not yet deployed) is the mechanism:
   resolve `current_user` → `sub` via the mapping table, fall back to `app.sub` for the app role, and
   let RLS key off `coop_current_sub()`. With `ident`/`cert` auth, the role *is* the member and the
   fallback barely matters.

The consequence: the identity-injection patch becomes **unnecessary** — a strictly smaller system,
with one real integration seam (can NocoDB open a per-user connection) that we have already decided
to **patch if it cannot**.

## The "gated functions" line (license), settled

NocoDB is AGPL self-hosted; its *enterprise* features (Scripts, Workflows, SSO, audit, RLS) are a
separate commercial product, absent from the OSS build. The running image already stubs the probes so
the OSS frontend doesn't toast. The line that keeps this legal **and** useful:

- **Stub the enterprise probes** (already done) — the OSS frontend must not error.
- **Where a capability is genuinely wanted, implement it yourself against the *public* contract**,
  never by lifting NocoDB Inc.'s private `nocodb-ee` code. (The skill's `interfaces-implementation.md`
  already maps this: the public repo ships the full Interface *type* + *data* model + *frontend
  contract*; only the ~50 EE handlers are private. Port-against-the-contract is legal; copying the
  handlers is not.)
- **Never turn a stub into a reproduction of the paid feature.** A stub returns `{list: []}` to stop
  the toast; a reimplementation of "Scripts" that executes the EE logic would be a license violation.
  Build the *capability* in the coop stack (a governance workflow, a script runner, an audit trail are
  generic), not as a clone of NocoDB's proprietary code.

## Goals (the deliverable, in order)

1. **Verify the deployed projection actually works** — confirm the `irlcoop` source exists in
   `nc_integrations_v2`, the "Coop" base exists and renders, and per-user RLS read returns *their*
   rows for a real member (the `verify-coop-rls` script). This is the stop-the-bleeding step; it tells
   us whether the integration is "lost state" (repair) or "never finished" (build).
2. **Replace the injected-GUC model with role-as-identity** — deploy `coop_member_role` +
   `coop_role_sub()`, add `ident`/`cert` to the NocoDB source path, and patch NocoDB to open a
   per-user connection if it can't. This removes the injection patch and its foot-guns.
3. **Expose the group projection as RLS-scoped views (explicitly narrowed)** — per-group, per-role —
   so the "most useful tool in the suite" is literal: a member opens "Databases" and sees *their*
   filter of the ledger, dues, contacts, resources — never a bare table, never another group's rows.
4. **The group-aware "who" picker is the sharing surface** — "share this base to @group.treasurer" is
   a view-over-a-role, the identical mechanism as goals 2–3, so NocoDB is the *first consumer* of the
   picker designed in `group-who-picker.md`.
5. **Port one genuinely-useful gated capability (public-contract-only)** — likely "Interfaces"
   (builder over the public type model), because it turns "view rows" into "build a facesheet the
   group actually uses." Explicitly *not* Scripts/Workflows-as-EE-clone.

## Non-goals

- No reproduction of NocoDB Inc.'s enterprise code (Scripts/Workflows/audit/SSO as EE reimplementations).
- No bare `SELECT * FROM t` projection views (the RLS-defeating trap the spike proved).
- No per-user Postgres *passwords* stored in NocoDB (the plaintext leak).

## Open questions

1. **Can NocoDB open a per-user connection** (per-request identity → distinct `current_user`), or must
   it be patched? This is the one real seam; spike it before committing to the role-as-identity target.
2. **`ident` vs `cert`** — does the gate→Postgres path sit on one host (so `peer`/`ident` is free), or
   does it need a per-member client cert (key-held, passkey-compatible)? The custody answer points at
   `cert`, but `ident` is simpler if co-located.
3. **Is the deployed projection lost or just unverified?** — resolve before rebuilding.
