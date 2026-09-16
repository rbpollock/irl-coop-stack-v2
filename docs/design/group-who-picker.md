# The group-aware "who" picker — one shared primitive across every app

**Status: design (current-best model, expected to be tweaked on first real use).** The platform's
group model (groups, subgroups, roles, grants) lives in coop-api. The problem: most apps that ask
"who?" — a doc's collaborators, a project's members, a `@`-mention, a share dialog — are person-scoped
and cannot *show* cooperative structure. A member inviting people to a doc sees a flat list of `sub`
IDs, not "which groups already have access" or "the bakery collective's council."

The fix is **one shared picker**, built once, embedded by every app at its "who" affordance. It is
group-native in *selection*, person-materialized in *enforcement*.

## The one hard line (why this isn't "teaching apps groups")

- **Selection is group-native.** You pick `@food-coop`, `@food-coop.admins`, `@food-coop.bakery` — a
  namespaced path over the group model.
- **Enforcement stays person-materialized.** The picker *resolves* the group to a set of `user_sub`s
  and hands the enforcing app *people* — because OnlyOffice/NocoDB/Plane's permission model is
  per-person, and it stays that way. The picker translates "the group we mean" to "these people";
  it does **not** make an app capable of "the group decided."
- **Authority, where a decision is also needed, stays in coop-api.** If a share/merge/role-change
  needs the group's *threshold* (council approval), that is a `proposals`/`votes` act in coop-api, not a
  checkbox in the share dialog.

## What the picker does (one component, four jobs)

1. **Resolve** a namespaced path — `@group`, `@group.role`, `@group.subgroup`, `@group.subgroup.role` —
   to a member set, transitively through member-groups, **cycle-guarded** (every group is a sub; the
   graph is unrooted and can cycle; a visited-set is correctness, not optimization).
2. **Show existing access holders, grouped by group** — so a document's access list finally renders
   *structure* (the grain-farm's people vs. the legal-aid's people), not a `sub`-ID haystack. This is
   the "who is from what group" fix that Plane (person-scoped) cannot express natively.
3. **Preview reach** — a live head-count and name preview before commit, so `@food-coop` that resolves
   to 200 people is *seen* as 200 people first (the mass-notify footgun, defused by visibility).
4. **Hand off the materialization** — to a dumb app, a person-list; to a group-native app (Plane
   workspace, Matrix space), the group object itself.

## The grammar (relative, not root-relative)

There is no root; **every group is a sub**. So the sequence of dots is a *path through one unrooted,
grant-labeled graph*, and the bare name resolves against the current context:

| address | resolves to |
|---|---|
| `@food-coop` | the whole group, transitively |
| `@food-coop.admins` | the `admins` role inside food-coop |
| `@food-coop.bakery` | the `bakery` subgroup |
| `@food-coop.bakery.admins` | admins *of* the bakery (nested) |
| `@admins` | *my group's* admins when I'm context-switched into one; ambiguous otherwise → disambiguation |

The `.`-path mirrors the existing `namespace.thing` convention (e.g. the `group.manage` grant name) and
is both typeable (autocompletes) and clickable (drills the sub-group tree). The bare name resolves to
the current group when "inside" one — which is the **context-switch** idea, now as the *namespace* of
the address.

## The three-tier map (where each app stands relative to the picker)

| tier | examples | relationship to the picker |
|---|---|---|
| **group-native** (the app *has* the concept) | Matrix (spaces/rooms), FreeSWITCH (DID/extension/ring-group), ERPNext (company/tenant), Plane (workspace), Stalwart (domain/list), Keycloak (realm) | picker feeds the app's *native* object; coop maps group↔object |
| **weakly group-aware** (isolation, no actor) | NocoDB, Webstudio, Hi.Events, Formbricks, LiteFarm, CryptPad, WordPress | picker embedded at the "share/scope" affordance; enforcement stays RLS/OIDC gate |
| **group-blind** (doc/object surfaces) | **OnlyOffice**, MinIO, file/RAG layers | picker embedded; enforcement = the *materialized person-set* it resolves; the app never learns "group" |

The driving example is **OnlyOffice's "invite a collaborator"**: it should natively show groups that
already have access and a group-picker like the one above — because sharing a document *is* group
work, and a member doing it must see cooperative structure, not `sub` IDs. Enforcement remains
per-person; the *usability* is group-native.

## Why operations are expensive (the cost the picker hints at)

When a group **dissolves / merges / splits**, the picker's materializations go stale *everywhere it was
embedded*: the doc still lists the absorbed group, the base still scopes to it, the extension still
rings it. So a group operation is not "update a row" — it is **re-project the changed group onto every
surface** (re-share docs, re-scope bases, re-point extensions, close the ERPNext company). This fan-out
is the *real* reason dissolve/merge/devolve are rare terminal acts, not frequent ones. The picker makes
the fan-out's *extent* visible, which is the first step to automating it.

## What this explicitly is not (yet)

- A bespoke `@`-grammar enforcement layer across 40 apps — Matrix already does spaces/rooms/mentions
  natively; the picker *complements* it for the apps that lack it, it does not replace Matrix.
- A decision mechanism — the picker *reaches*; it never *authorizes*.

## Open / expected-to-tweak

- Whether `@group.role` resolves **down-and-sideways** (full federation traversal) or **containment-down**
  only — the authorization flavor that decides it is unresolved.
- Whether "existing access holders" should be ordered by a relationship signal (recency, grant
  strength) rather than alphabetically — a discover-on-first-use concern.
- The exact embed surface (a web component? a JSON the apps render?) — `scopeResource`/`resource_scopes`
  is the existing engine; the picker is its *input* affordance, not its replacement.
