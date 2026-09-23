# Platform Views — keep the types, extend the union

Status: design · Sep 2026 · Builds on nocodb-integration.md (the gated-functions line),
webstudio-identity-and-group-routing.md (Webstudio as presentation),
group-home.md (the surface this view system renders), formbricks-group-mapping.md
(surveys), event-bus-and-group-shapes.md (the bus + shapes).

## 0. What this doc is

This is the **view system** underneath the group home — the schema and mechanics by
which a group builds and shows its own surfaces (a facesheet, a treasury dashboard, a
rota, a weave). It is the settled answer to "what do we do about NocoDB's Enterprise
Interfaces feature": **keep the public type model, discard the EE implementation, and
extend the layout union with platform-specific views.**

Three concerns, three owners, one type system:

- **render** — Webstudio (builder + page shell)
- **read** — NocoDB + coop-api, scoped by Postgres RLS (`app.sub`)
- **act** — Temporal workflows

## 1. The adopted type model (what we keep)

The public AGPL repo ships the complete *type* model for interfaces; only the ~50
handlers + builder frontend are private EE. We adopt the types and write our own
handlers — this is the "port against the public contract" path, not a clone.

Kept, as vocabulary:

- **`nocodb-sdk/src/lib/interface/*`** — `pageConfigs.ts` (the config shape per
  layout), `elements.ts` (the widget/element catalogue), `vizFields.ts`,
  `enums.ts`, `copyFromView.ts`. These define *what a view is*: title, layout,
  config, widgets, fields, filters.
- **The 7-layout discriminated union** — `TABLE`, `RECORD_REVIEW`, `DASHBOARD`,
  `FORM`, `OVERVIEW`, `RECORD_DETAIL`, `CUSTOM`. `config`/`published_config` are
  JSON discriminated by `layout`.
- **The data model** — `nc_interfaces` + `nc_interface_pages` (migration
  `nc_202607251200_interfaces`, **already applied** to the live DB), plus
  `PRINCIPAL_ASSIGNMENTS.hierarchy_scope`.

Discarded: the EE handlers (`InterfaceGet/InterfacePost.operations.ts`), the builder
editor, the page shell, the interface-grant ACL. We build our own of each.

## 2. The extended union — platform views

NocoDB's 7 layouts stay as the *generic data* views. The platform views are the
*semantic* ones that know about the coop's primitives — each is a new layout type in
the union, with its own config shape, and its actions are Temporal signals. They fall
straight out of the group-home lenses (§2.2) and pathways (§4):

| layout type | renders | its action (Temporal) |
|---|---|---|
| **weave** | the needs↔offers force-graph | accept a match, post an offer |
| **geography** | the map / the morph | — (pure view; point/route/territory/field) |
| **treasury** | the three ledgers + the split | run the keeper, contribute |
| **governance** | proposals + quorum meters | propose, sign & vote |
| **rota** | coverage schedule + the N:M floor | cover a shift |
| **survey** | an embedded Formbricks survey | submit → group-mapped response |
| **feed** | the "Now" pulse, drawn spatially | — |

Each config shape is a JSON object in the same discriminated-union style as the base
layouts (e.g. `weave` → `{edgeTypes, nodeTypes, filters}`; `geography` →
`{geometryShape, basemap, nodeFilter}`; `rota` → `{coverageConstraint, rotation}`;
`treasury` → `{ledger, entitlementTable}`). Specifying these is open work (§6).

## 3. Three concerns, three owners

The split is clean because each concern already has a home in the stack:

- **Render — Webstudio.** The builder and the published page shell
  (webstudio-identity-and-group-routing.md). A group authors a view; Webstudio lays
  it out; the `GroupData` widget carries the data binding.
- **Read — RLS-scoped.** Data comes from the coop projection, scoped by `app.sub`
  (role-as-identity, proven live). NocoDB `/api/v2` is the table-level read; coop-api's
  session read surface (`/api/v1/site/groups`) is the platform-level read. NocoDB's own
  EE RLS (`nc_rls_policies`) is **not** used — Postgres RLS is authoritative, which is
  the whole point (their EE data-governance model conflicts with ours).
- **Act — Temporal.** A view's action is a Temporal signal, authorized by the caller's
  session key. Three relationships between a view and the platform:

  1. **read** — RLS-scoped data (above).
  2. **act** — a button starts a workflow ("run the keeper", "propose to the governance
     room", "accept this match"). The action is where a pathway becomes an edge.
  3. **reflect** — the view shows workflow state ("keeper ran, split distributed",
     "proposal awaiting 2/5 signatures"). Temporal's durable state reads back into the
     view — which is the "Now" tense of group-home.md §2.3: the pulse *is* workflow
     events.

This is also what makes the temperature model (group-home.md §4) real: **hot verbs =
fast Temporal signals; cold verbs (dissolve, freeze, succeed) = long-running,
timelocked, guarded workflows.** The ceremonial door stops being a UI metaphor and
becomes a durable process.

## 4. Formbricks — the survey view

Formbricks is one more platform view type, not a special case. Its group mapping is
already designed (formbricks-group-mapping.md): a workspace maps to an irl.coop group,
so a survey view is "bind this Formbricks survey to this group, responses scoped by
RLS." Submitting rides the same event bus as every other action (the response is a
typed event, deliverable to the survey's owner group).

## 5. The license line

Settled in nocodb-integration.md §"gated functions line", unchanged here:

- **Adopt the public types** — legal, they're AGPL-public and this is the
  write-against-the-contract path.
- **Never clone the EE handlers/builder** — a reimplementation of the private
  `nocodb-ee` code is a license violation.
- **Never patch the license check to un-gate** — same.
- **Build the *capability* in the coop stack** — a governance workflow, a script
  runner, an audit trail are generic; build those generically (Temporal, the bus, the
  ledger), never as a clone of NocoDB's proprietary feature.

## 6. Open questions

1. **Vendor vs. re-express the types.** The interface type files are AGPL. Adopting the
   *schema* (the shape of a view, the layout union) is the intent; whether we vendor the
   AGPL `.ts` files verbatim or re-express the schema in our own words has a copyleft
   consequence we should resolve before any code lands. Lean: re-express the schema,
   cite the source — keeps the vocabulary, avoids the AGPL reach.
2. **The platform-view config shapes.** Each new layout type needs its config schema
   specified (the §2 sketch is not a spec). Do these live in the SDK-type style, or in
   coop-api as its own `view_types` registry?
3. **The `GroupData` read path.** The native Webstudio SDK component is specced but not
   built. Is it one generic read path for *all* views, or a per-view reader (weave has a
   different fetch than treasury)?
4. **How Temporal state reflects back.** The "reflect" path needs a defined surface:
   does the view poll a workflow-state endpoint, or does workflow state ride the event
   bus as typed events (leaning: the bus — same channel as every other pulse)?
5. **The builder.** Webstudio is the builder, but authoring a `weave` or `rota` view is
   not drag-and-drop the way a text block is. Is the builder Webstudio-native, or does
   each platform view ship as a prebuilt SDK component with a small config form?
