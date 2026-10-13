# The central store for real-world resources — farm things out of the farm app

Status: direction · 2026-10-04 · Robbie + Hermes.
Trigger: *"I want to decouple farm things from the farm app and glue it into a more central place like
ERPNext."*
Supersedes the premise of `litefarm-integration.md` (§2 — LiteFarm authoritative for the farm's data).
**Revisits D-20**, whose recorded revisit trigger is precisely *"if the farm pilot uses different
tooling"*.
Companions: `resource-model.md` (what a resource *is*) · `declared-binding-registry.md` (§R6 — where a
marker lives) · `erpnext-tenancy-notifications.md` (Company = tenant; the declared treasury boundary) ·
`RISKS.md` R-10 · `frappe-insights-integration.md` (how a Frappe app joins this bench).

## 0. The direction, and why it is right

Today the **app is authoritative for its domain**: LiteFarm holds the fields, crops and animals; ERPNext
holds the books; NocoDB holds a base — each with its own tenancy. `RISKS.md` R-10 states the cost:
*"Plane, NocoDB, LiteFarm, and ERPNext hold their own copies with bespoke scoping."*

The consequence is not just untidy storage. It is that **there is no single answer to "what does this
group have", and no single answer to "who may see it."** The second is the serious one: the disclosure
model (scope + granularity, `scoped-availability.md` §4) belongs to the coop, and it **cannot be applied
to data that lives inside five apps' own permission systems**.

So this direction is toward the stack's doctrine everywhere else — **the coop holds the record; the app
is a projection** — the same exchange NocoDB member identity, the world-docs and the availability design
already make. Farm things are simply the case that was exempted.

## 1. Three candidate centres — and the honest trade

| Centre | What it buys | What it costs |
|---|---|---|
| **ERPNext** | matured machinery — Item/Stock/Warehouse, Asset, Maintenance Schedule/Visit, Work Order — **plus an Agriculture domain app** (Land Unit, Crop, Crop Cycle). Tenant is the **Company** (= group), already designed | a separate DB with **its own permission model** (so R-10 does not go away by moving); **stock is OFF at v0** (`enable_perpetual_inventory: 0`); an accounting-shaped model; and **every resource-bearing group then needs a Company** — provisioning coupling for a group that just wants to log a borrowed drill |
| **coop-api** | identity, disclosure, authority, availability and the resource model already live here; no coupling; apps become projections | we would build inventory / asset / maintenance machinery that ERPNext already ships |
| **Split by fact type** *(recommended)* | each fact has exactly **one** home | requires saying, per class, which side each fact is on |

**The recommendation — split by fact.** coop-api holds the **subject** (identity + axes), the
**disclosure rules**, the **authority** and the **availability**; ERPNext holds the
**operational/accounting facts** for what a group actually accounts for (stock moves, valuation,
depreciation, maintenance visits). They are joined by a `declared_binding` (`kind='resource'`) plus a
**marker in the externally authoritative system** — the R6 rule in `declared-binding-registry.md`.

This is also the honest fix for R-10: R-10 is a **duplication** problem, not a location problem. Moving
five copies into one app does not fix it; giving each fact one home does.

**The general form of this rule — for every domain, not only resources — is `where-facts-live.md`.**

## 2. What ERPNext already has for this

- **Agriculture domain app** — Land Unit, Crop, Crop Cycle. Its own wiki states the constraint that
  matters: *"There can be many crop cycles on each block, but never overlapping on the same block. This
  can yield information on **block availability** for efficient use."* That is land as a **schedulable
  resource with non-overlap** — our areal + access-window + recurring-obligation row, already built.
- **Asset + Maintenance** — asset register, categories, depreciation, Maintenance Schedule and
  Maintenance Visit. That is the maintenance obligation's machinery (`resource-model.md` §3.5).
- **Item + Warehouse** — things and locations: a depot window is a location; a movable tool is an item
  with a location.
- **Work Order / Job Card** — performance as executed work (a harvest run, a route).
- **A Frappe app platform** — a custom doctype is cheap, and the repo already has the pattern for adding
  an app to *this* bench without a fork (`frappe-insights-integration.md`: `bench get-app`,
  *"declarative install (no fork)"*).

**Caveat to verify, not assume:** whether the Agriculture domain app ships with the deployed v16 or must
be installed separately, and whether its doctypes cover a real pilot's needs (certifications, task
assignment to workers). The test in §4 settles that cheaply.

## 3. What happens to LiteFarm

| Option | What it means | Cost |
|---|---|---|
| **Drop it** | farm truth moves central; no farm app | the farm UX has to be rebuilt (crop planning, worker tasks, certification compliance) |
| **Keep as a UI over a central store** | LiteFarm's models serve a different store | a deep fork — its 60+ Knex models are its own |
| **Keep as an optional, non-authoritative view** | central store wins; LiteFarm reads | a sync engine and two schemas to keep aligned — R-10 in a new dress |
| **Keep only for what nothing else has** | e.g. a mobile field-worker task app, farm maps | scoped, honest, and compatible with central truth |

**Recommendation: decide this last.** Move the *facts* first (§4); LiteFarm's fate follows from what a
real farmer actually misses. D-20 flips from *tentative* on the way, not before.

## 4. The cheap reversible test

Install the **Agriculture domain app** on the existing bench — the Insights pattern, no fork — and model
one real farm:

- one **Land Unit** (a field = an areal resource),
- two **Crop Cycles** on it (non-overlapping),
- **Items** for inputs, one **Asset**, one **Maintenance Schedule**.

If that covers the pilot, the central direction is proven for the cost of an afternoon, and LiteFarm's
role becomes a **UX** question rather than a data question. If it does not, we have learned exactly which
doctypes are missing — which is the useful output either way.

**No migration, no cutover, nothing authoritative changes** until the test is judged.

## 5. Boundaries this must not cross

- **ERPNext = operational records; Pools/Accounting = treasury truth** — the declared boundary already
  cited in `erpnext-tenancy-notifications.md`. Farm facts moving into ERPNext does **not** move money
  truth.
- **One home per fact.** If a field's geometry lives in coop-api (PostGIS + geohash, the dial) and its
  crop cycles live in ERPNext, write that down and never maintain both.
- **No group may be forced to provision an app to have a resource.** The app-less case — a drill, a
  hall, a depot window, a route — stays in coop-api and must not require an ERPNext Company.
- **Disclosure stays ours.** ERPNext's permission model never becomes the thing that decides who may see
  a resource.

## 6. Open questions

1. Does the Agriculture domain app cover the pilot (§4), and does it ship with v16 or install separately?
2. Per class, which facts are coop and which are ERPNext — `resource-model.md`'s one question, now with a
   default answer (split by fact).
3. LiteFarm's fate (§3) — after the test, not before.
4. Does the farm's **land geometry** live in coop-api with crop cycles in ERPNext, or both in ERPNext?
   (The disclosure argument favours geometry staying where the dial lives.)
5. Does a **personal** resource (a drill) ever belong in a personal Company? (Recommendation: **no** — it
   stays app-less, or the casual case pays for the accounting case.)

## Cross-references

- `resource-model.md` — what a resource is; §0.1's "which system already holds it", now answered by default.
- `litefarm-integration.md` — the integration this supersedes as the *authoritative* story; its SSO gate,
  mapping and event legs remain valid for as long as LiteFarm runs.
- `erpnext-tenancy-notifications.md` — Company = tenant; the operational-vs-treasury boundary.
- `declared-binding-registry.md` §R6 — where the marker goes; one contract, family-generic roots.
- `RISKS.md` R-10 — the duplication problem this is meant to fix.
- `frappe-insights-integration.md` — the no-fork way to add a Frappe app to this bench.
- D-20 (`docs/DECISIONS.md`) — tentative; this is its revisit trigger.