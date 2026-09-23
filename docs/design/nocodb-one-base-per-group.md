# NocoDB — the settled architecture: one base per group; a person *is* a group

**Status: design (settled, supersedes the earlier "coop base" / "user-specific base" framing).**
This is the north star. It is the point where the identity model and the data model become the same
sentence.

## The one principle

> **A base is a group's data surface. Every group — personal *and* collective — has exactly one base.**
> A person's "lens" *is* their personal group's base, which federates-reads across the bases of the
> groups they belong to. "Focus on one group" is switching to that group's base; "build a workflow
> and migrate it to the group" is a governed shape-migration between bases.

A person is a `personal` group (`groups.kind`, one per `sub`, DB-enforced). A cooperative is a group;
a business is a group; a household is a group. **"Is this a coop?" is never asked** — the answer to
every "is X a group?" is yes, and every group has a base.

## What falls out of it

- **"Not everyone will be a coop"** → dissolves. Categories (coop / business / personal) were the
  platform imposing labels. There are only groups, each with a base.
- **"A person tracks their interconnected groups, not 'the coop'"** → their lens *is* their own
  group's base, federating-reads across their member-group bases. No imposed "Coop" base.
- **"Sometimes focus one, sometimes pick, sometimes all"** → a **scope dial** = which group's base
  you are focused on, plus your own base joining across your member-groups. Same as the context-switch.
- **Sharing** → a group base is owned, RLS-scoped, seats granted via the group-"who" picker. NocoDB's
  native model (owned container + members + permissions) holds without change.
- **Experimentation → migration** → build on *your* (personal group's) base, then promote the shape to
  another group's base via a governed operation (proposal + threshold). "Ship the shape, re-bind the
  data" is that migration.

## The three objects (all the same thing; only the owner differs)

| object | it is | owner | governance |
|---|---|---|---|
| personal base | the `personal` group's base | the member | none (private) |
| group base | a collective group's base | the group | threshold (Safe/roles) |
| migration | a shape-promotion | the *source* group | group proposal + vote |

## Identity at the connection layer (unchanged target)

Per-user Postgres role + `ident`/`peer`/`cert` auth → `current_user` *is* the member; `coop_role_sub()`
resolves role → sub; RLS keys off `coop_current_sub()`. The injected-`app.sub` patch becomes
unnecessary. Per-user *role* yes, per-user *password* no (the latter lands plaintext in NocoDB).

## License line (unchanged)

Stub enterprise probes; port only against the public contract; never clone `nocodb-ee` private code.

## Provisioning — one base per group (settled mechanism)

Settled this session (Robbie: "A — but the bases should organize themselves meaningfully; also
provision bases for all existing groups to catch up"). The mechanism:

1. **Per-group Postgres schema** `grp_<slug>` (sanitized slug) for named groups; `grp_personal_<id>`
   for personal groups (no slug). One schema = one group's data surface.
2. **Narrowed views in that schema** — one per group table (`groups`, `group_members`,
   `resource_scopes`, `events`, `dues_policy`, `dues_waiver`, `tier2_entry`, `tier2_signature`,
   `payment_intent`, `telephony_resources`), each `security_invoker = true` AND
   `WHERE group_id = <this group>` (or `id = <this group>` for `groups`). Explicit column lists,
   same shape as the global `*_view` relations. Double-safe: the view narrows to the group, and RLS
   still fires under the member's cert role so a non-member sees zero rows even through the base.
3. **GRANTs** — `USAGE` on the schema + `SELECT` on its views to `coop_member`.
4. **NocoDB base per group** — external source over the group's schema (`searchPath: [<schema>]`),
   same `irlcoop` integration / `coop` connection. Base title = the group's name. The cert dispatch
   in CustomKnex already applies (source database is still `irlcoop`), so member identity flows.
5. **`coop_provision_group_base(uuid)`** — SECURITY DEFINER (owner postgres), idempotent, creates
   the schema + views + grants. Backfill = loop it over every `groups` row.
6. **Personal base = the lens** — a personal group's base is the member's lens; federation across
   member-group bases is **B2** (not yet built), so personal bases look sparse until then.

Pending cleanup (after the new model is proven): retire the old shared "Coop" base and update the
`verify-coop-rls` / journey scripts that still reference it.

## What this supersedes

- The "Coop base" / "Coop Groups" / "Projects" pre-made bases are **dead naming** — the confusing
  surface a member should never see. They are scaffolding, not the model.
- Step B of the rebuild plan is no longer "the joined user-specific base" — it is **"one base per
  group (personal = the lens), federation across member-group bases, governed shape-migration."**
