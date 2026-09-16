# NocoDB rebuild — execution plan (A → B → C, each gated by a test)

**Status: plan (agreed; execution to be gated step-by-step).** The three discussed changes form a
strict dependency chain. This doc is the tracked plan each execution step points at.

## The three targets

- **A — user-based connection (identity layer).** Per-user Postgres role + `ident`/`peer`/`cert` auth +
  `coop_role_sub()` → `current_user` *is* the identity; patch NocoDB to open a per-user connection if
  it cannot. Removes the injected-`app.sub` patch and its foot-guns.
- **B — the joined, user-specific base (projection).** RLS-scoped views that join across apps; one
  member-facing base where a user sees their slice of groups, membership, dues, contributions,
  resources, events, and plane projects — all under `current_user`.
- **C — UI-building + invitations + permissioning (payoff).** Port the Interface builder against the
  *public* contract; wire the group-"who" picker as the invite/permission surface.

## Why this order (dependencies)

- C depends on B (a permission is "who sees which *view*"; no view → nothing to permission).
- B depends on A (a "user-specific base" is meaningless until "user" is a real connection identity).
- A is independent and smallest; once proven it deletes the entire injection patch.

## The plan (each step = change + test gate)

### Step 0 — verify the deployed projection (READ-ONLY)
Resolve "lost vs never-finished": does the `irlcoop` external source exist in `nc_integrations_v2`?
Does a "Coop" base exist in `nc_bases_v2`? Is the identity-injection marker present in the running
bundle? Is the `coop` role's RLS actually returning per-user rows?
**Gate:** report the factual state; no change. Determines whether Step A is "repair" or "add".

### Step A — user-based connection
1. Deploy `coop_member_role` (role_name → sub) + `coop_role_sub()` + fold into `coop_current_sub()`
   (role wins over `app.sub`; revocable; fail-closed).
2. `pg_hba.conf`: add `ident`/`peer`/`cert` for the NocoDB host (auth method = the settle from Step 0).
3. Patch NocoDB to open a per-user connection (or confirm it can), per the identity-injection seam.
4. **Test A:** member-1's connection sees exactly member-1's rows; member-2's sees member-2's; and a
   `SET app.sub='<someone-else>'` is *ignored* because the role wins. Identity is real, not toggled.

### Step B — the joined, user-specific base
5. Write RLS-scoped views, each *explicitly narrowed* (no bare `SELECT *`) — groups, group_members,
   resource_scopes, dues_policy/waiver, tier2_entry, payment_intent, events, telephony_resources,
   plane projects. Shape only; binding re-lived per user.
6. Create the "Coop" base over these views.
7. **Test B:** one member sees their rows across all joined surfaces; zero other-group rows; zero
   cross-app leak (the narrowed-view rule enforced).

### Step C — UI-building + invitations + permissioning
8. Port the Interface builder against the public contract (`references/interfaces-implementation.md`).
9. Wire the group-"who" picker as invite/permission (share to `@group.role`).
10. **Test C:** member builds an interface, shares to `@group.role`; recipient sees re-bound data
    (ship the shape, re-bind the data), exercised end-to-end.

## Non-negotiable constraints (carried from the design docs)

- No bare `SELECT * FROM t` projection views (RLS-defeating; spike-proven leak).
- No reproduction of NocoDB Inc.'s enterprise code — stub probes, port against public contract only.
- No per-user Postgres *passwords* stored in NocoDB (plaintext leak); per-user *roles* only.
- Each step's test must pass before the next begins; a failed gate stops the chain.

## Rollback posture

Every NocoDB change is a new image tag (base tag untouched); rollback = flip the spec tag + `up -d`.
Schema changes (`coop_member_role`) are additive and revocable (drop the table / remove the mapping).
