# The resource model — what a group holds, uses, or schedules

Status: design · 2026-10-04 · Robbie + Hermes.
Answers *"we have no working model for resources and their varying types."*
Companions: `scoped-availability.md` §9.1 (a declaration's subject may be a **resource**) ·
`custody-chain-and-contest-kit.md` (the transfer leg) · `declared-binding-registry.md` (the commitment
leg) · `tier2-entry-model.md` §5.3 (the obligation shape) · `group-shape-scenarios.md` (the scenarios
that need it) · `adversary-models-and-sector-fit.md` (attestation vs assertion).

## 0. The gap, stated precisely

The stack carries record families for **things happening** — the `anchors` table holds a root per
`family`, and `custody` is already one — and it has **no registry for the things themselves**.

The custody chain says so itself: `asset` is *"a commitment, not a label"* (§1.1), so the chain can
prove *"something moved, and both parties agreed"* while never identifying what. So today the stack can
prove a transfer of an **unidentified thing**, and cannot answer the simplest question a group asks:
*what do we have, where is it, who is answerable for it, and what does it need?*

And `scoped-availability.md` §9.1 now needs the same missing subject — a declaration whose subject is a
resource currently **points at nothing**.

> **A resource is a *subject*; availability and custody are *events about* subjects. We built the
> events. The subjects for things are missing.**

## 0.1 Where resources already live — the registry is smaller than it looks

**Corrected 2026-10-04.** §0 says "no registry exists". That is true of *coop-api*, and **false of the
stack**. Two apps are already resource registries for their own domains, and the connection pattern
already exists:

- **LiteFarm** (`farm.irl.coop`) *is* the farm's registry — fields, crops, animals, inputs, tasks — and
  it is **already mapped**: `farm.farm_id ↔ groups.id`, written as a `resource_scopes` row
  (`app='litefarm'`, `resource_key=farm_id`), with `userFarm ↔ group_members`. *"Access control stays
  LiteFarm's — we don't re-express 60 models in RLS"* (`litefarm-integration.md` §2).
- **ERPNext** (`accounting.irl.coop`) holds the **inventory** domain, and its tenant is the **Company**
  (`group → Company`; members → `User Permission` rows, provisioned from coop-api). But
  **`enable_perpetual_inventory: 0` at v0** — stock is deliberately off, so ERPNext is *not* the coop's
  stock registry today (`erpnext-tenancy-notifications.md` §2).
- **Plane** is where the tool-library scenario already puts the *maintenance schedule*; **NocoDB** is
  where it puts the *inventory + checkout log* (`group-shape-scenarios.md` §2).

**So the connection is not a new model — it is the established one:** map the app's own tenant boundary
onto a group, write a `resource_scopes` row, **keep access the app's, keep identity and membership the
coop's.** *"Strip the binding and it's an independent group."*

**What this document is actually for, narrowed:**

| Resource class | Where it already lives | This doc's role |
|---|---|---|
| Farm resources | **LiteFarm** today, **moving central** — `central-resource-store.md` | the subject + the disclosure layer, whichever store holds them |
| A group's tools / stock | a **NocoDB base** now (the scenario's own answer), or ERPNext stock later | **not** the registry — the disclosure + binding layer over it |
| Maintenance | **Plane** (schedule) + an obligation | the obligation shape, tagged by the resource |
| A member's personal tool, a hall, a depot window, a route | **no app home** | **this model** — the only case that needs it |

**The one question that gates anything: for each resource class, which system already holds it?** Answer
it per class, lazily, when that class is built (§6). Its general form, across every domain and sector:
**`where-facts-live.md`**.

## 1. Not a type taxonomy — axes

A type list (tool / land / structure / route) is the losing version of a problem this repo already
solved once — the group-shape doctrine: *"each scenario is a shape that selects a subset of primitives
+ a role vocabulary; none is a new category"* (`group-shape-scenarios.md` §"What this means"). A
resource is therefore a **row + axes**, and the test of the model is that every varied thing below lands
on it **without inventing a type**.

**The one existing precedent, and its limit.** `telephony_resources` is
`(group_id, resource_type, external_ref, config)` with `resource_type` a **closed CHECK**
(`extension|voicemail|conference|queue|ring_group|ivr|did|trunk`). That is defensible there *because a
vendor's set is fixed*. It is the wrong shape for physical things, whose set is open-ended — hence axes,
and hence an open `type` label that never gates behaviour.

## 2. The axes

| Axis | Values | What it decides |
|---|---|---|
| **Identity** | a stable resource id + label | both availability and custody point at it; distinct from the custody chain's `asset` hash |
| **Location kind** | point-fixed · movable · **linear** (route) · **areal** (parcel, range) | which geo primitive, and which disclosure granularity |
| **Engagement** | **checkout** (custody transfers) · **access-window** (use, no custody) · **performance** (a duty over space + time) | three different state machines, on three different legs |
| **Contention** | exclusive · quota · none · territory | whether a reservation is a conflict constraint, a quota, or an agreement |
| **Custodian** | member · group · child group · **external principal** | who is answerable; external = a binding with terms |
| **Obligations** | none · recurring · condition-triggered | the existing obligation shape, tagged by resource |
| **Provenance** | self-declared · attested (`role`/`key`/`vote`) | the sector-tag pattern — a deed or a certificate is not a label |
| **Disclosure** | the scope + granularity dial | the same dial as availability — and a movable tool's location is often a member's home |

## 3. Where the examples land

### 3.1 Tools — movable vs fixed is *a value, not a type*

- **movable** (drill, chainsaw, trailer, van): `engagement = checkout` → the **custody** leg, with a
  checkout → in-use → return → condition state machine; `location = movable`; `contention = exclusive`;
  `obligations = recurring` (`[repair-night]`).
- **fixed** (bolted-down bandsaw, installed pump): `engagement = access-window`; `location = point`.

Same row, different values. And a movable resource's *location* is a privacy matter: *"you can borrow the
drill, pickup arranged"* is not *"123 Main St"* — the dial applies.

### 3.2 Land

- `location =` **areal** — a parcel is geometry, possibly several. PostGIS already holds it: the geo
  tables use `SRID 4326` geometry plus a **geohash column** for coarse "near" queries, described as the
  *"privacy/queryability split (precise geometry is client-encryptable for private records later;
  geohash stays indexable)"*. **That is the granularity dial applied to space** — the same rule as
  `scoped-availability.md` §4.
- `engagement =` **access-window** with *use-rights* (a season, a rotation) — **not** custody: you don't
  take the land home.
- `obligations =` recurring (cover crop, soil test, mow) — exactly the `money/yr | h/mo | [tag]` shape in
  `tier2-entry-model.md` §5.3.
- `provenance =` **attested, and this is where it bites**: a deed, a lease, a certified-organic status.
  An attested *resource* claim is the same object as an attested *sector tag* — one layer, not two.
- `custodian` can be **external** (a leased field): that is `declared_binding` `kind='resource'` with the
  lease as `terms_hash` and a validity window. **The binding exists; the resource it binds does not.**

### 3.3 Structures — barn, hall, shed, a member's garage

- `location =` point or areal; `engagement =` **access-window** (book the room), often *with a key* —
  which is a small custody question riding on an access-window resource.
- `contention =` exclusive; `obligations =` recurring + condition (inspection, repair).
- The tool-library scenario's *"external space booking — a church or a member's home as a bookable
  resource that isn't owned by the group"* is precisely this row with an **external custodian**.

### 3.4 "People + land + skills" — **not a resource; it is a group**

Reject the composite. The composition primitive already exists: **a group, and its child groups**
(rights-set relationships, each with its own Safe and budget — `group-shape-scenarios.md` §2 calls
maintenance *"as a child group … a rights-set relationship, not a flag"*).

And **people are never held**: a person participates through **availability** (`subject = member`) and
**credential tags**, never as a custodial object. That is the project's standing line — delegation is
session keys, not custody; a steward, not a root.

### 3.5 Maintenance needs — not a resource; a resource *state* + an obligation

- **recurring** → the existing obligation shape, with the resource as the tag (`[repair-night]`,
  `[van-service]`).
- **condition-triggered** (the blade when conditions are met) is the harder case: an *observation* event
  that raises an obligation. The custody record already carries `conditions`, so the raw material exists;
  the trigger does not.

### 3.6 A delivery route / delivery area range — **yes, and it proves the model must be axes**

Under the axes it lands cleanly; under any type list it has to be faked:

| Aspect | Value |
|---|---|
| **location** | **linear** (an ordered path) or **areal** (a service region) |
| **engagement** | **performance** — a duty executed across space and time; nobody holds it |
| **contention** | **territory** — two routes may physically overlap; exclusivity is by *agreement* (a binding), not by physics |
| **obligations** | recurring (a weekly run) |
| **disclosure** | **corridor** granularity — the `geolocation` primitive |
| **matching** | bilateral (driver's window ∩ rider's) → the overlap proof, `scoped-availability.md` §6.5 tier 2 |

**And it never enters the custody leg** — nothing is checked out. That is exactly why it breaks a
"tool-or-place" taxonomy: a resource with **no custodian, no single location, and no depletion**.

The geometry is already possible: the `tracks` table (PostGIS + geohash, with `kind` including `route`)
is literally the shape of a route.

## 4. What exists vs what is missing

**Exists, and is reusable:**

- the **event families** on `anchors` (including `custody`) — a resource is what those records are *about*
- the **custody record** shape — counter-signed transfers, encrypted content, `asset` as a commitment
- the **obligation shape** (`money/yr | h/mo | [tag]`) from the Tier-2 entry model
- **authority classes** (`role`/`key`/`vote`), validity-at-signature, append-and-revoke
  (`declared-binding-registry.md`)
- the **disclosure model** — scope + granularity + never-the-complement (`scoped-availability.md` §4)
- **geo** — PostGIS geometry + the geohash split, the `geolocation` circuit, `coverage.pmtiles`

**Missing:**

| # | Missing | Note |
|---|---|---|
| 1 | **the resource registry** (identity + axes) | nothing exists. `resource_scopes` is per-*app* scoping; `telephony_resources` is a closed enum for a vendor's set |
| 2 | **resource state** (condition, service history) | the custody chain records *transfers*, never a *state* |
| 3 | **the checkout / reservation state machine** | 🆕 *not designed* — the capability table's own entry |
| 4 | **the external custodian** | `declared_binding` can bind an external principal to a resource; the resource row it binds is missing |
| 5 | **linear / areal resource semantics** | the geometry exists; nothing treats a route or a range as a schedulable resource |
| 6 | **territory semantics** (overlapping coverage) | contention as agreement, not occupancy |

## 5. How it composes

- **Availability** — a declaration's subject points at a resource row (`subject_kind`/`subject_ref`,
  `scoped-availability.md` §9.5). The resource does **not** duplicate availability semantics.
- **Reservation** — a binding between a person (or group) and a resource slot; inherits the scope rules,
  the granularity dial and the anchoring.
- **Custody** — a checkout writes a custody record; the resource row is the subject that the chain's
  `asset` commitment refers to.
- **Obligations** — maintenance is a recurring or condition-triggered obligation tagged with the resource.
- **Paid bookings** — a booking for a resource (a hall, a van) uses the same outside-pays-a-group seam
  (`caldiy-scheduling-and-paid-bookings.md`).
- **The group** remains the composition primitive — child groups for maintenance, projects, joint
  holdings.

## 6. Decisions

**Only one gates anything: for each resource class, which system already holds it (§0.1)?** Answer it
per class, when that class is built.

**Everything below is deferred and reversible** — decide each at the point of building it, not now:

| # | Decision | Recommendation (for when it comes up) |
|---|---|---|
| 1 | One `resource` table with axes, or a table per engagement mode? | **One table**, axes as columns; the closed-enum precedent is the anti-pattern to avoid |
| 2 | Is `custodian` a principal ref (member / group / external)? | **Yes** — then a church hall is just another principal, not a special case |
| 3 | Does a resource need its own availability row? | **No** — `subject_kind='resource'` on the availability record; one availability model, pointed at |
| 4 | Disclosure default for a movable resource | **Never below "available, pickup arranged"** unless the member opts up — the location is often a home |
| 5 | Geometry — reuse the PostGIS + geohash split, or store a region only? | **Reuse it**; the split is already the dial, applied to space |
| 6 | Territory — exclusive by agreement or by nature? | By **agreement** (a binding); physics only decides occupancy |
| 7 | Which resource claims need attestation? | Deeds, leases, certificates, inspections — **attested**; everything else self-declared, and shown as such |

## 7. Do not

- **Do not model people as resources.** Availability + credential tags; the group is the composition.
- **Do not build a type taxonomy.** Axes and composition — a new physical kind is configuration, not code.
- **Do not make the registry duplicate the chain.** The registry is subjects; the chain is events.
- **Do not disclose a movable resource's location below the dial** — it is often a member's home.
- **Do not render a self-declared resource claim as attested.** A deed is not a label.
- **Do not invent a fourth ledger.** Reuse the family + anchors substrate
  (`custody-chain-and-contest-kit.md` §1).

## Cross-references

- `scoped-availability.md` §9.1 / §9.5 — the subject a declaration points at.
- `custody-chain-and-contest-kit.md` — the transfer leg; `asset` as a commitment, not a label.
- `declared-binding-registry.md` — the commitment leg; `kind='resource'`, authority classes, terms hash.
- `tier2-entry-model.md` §5.3 — the obligation shape maintenance reuses.
- `group-shape-scenarios.md` — the scenarios (tool library, childcare, farmers) and the capability table.
- `adversary-models-and-sector-fit.md` — attested vs asserted; the confidentiality floor.
- `sharded-ledgers-and-anchors.md` — the anchor stream a resource family would join.