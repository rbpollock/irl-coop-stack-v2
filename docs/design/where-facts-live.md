# Where facts live — the fact-kind split

Status: design · 2026-10-04 · Robbie + Hermes.
Answers *"I like split-by-fact, but I can see this getting complex across domains and sectors."*
The general form of `central-resource-store.md` §1. Companions: `resource-model.md` ·
`declared-binding-registry.md` · `scoped-availability.md` · `erpnext-tenancy-notifications.md` (the
declared treasury boundary) · `RISKS.md` R-10 · `custody-chain-and-contest-kit.md` (*"the platform offers
profiles, not one posture"*).

## 0. The worry — and why it is correct

Applied **per domain**, split-by-fact fragments at a higher level: every sector asks *"which app holds
this?"* and answers differently. That is R-10 with more copies — the same problem one storey up.

So the split must not be a per-domain decision. It is **a per-fact-kind** decision, made **once**.

## 1. The seven fact kinds — and they already exist

The split is not a new invention. It is already how this stack works; it was simply never named:

| # | Fact kind | Home | Already there |
|---|---|---|---|
| 1 | **Identity & membership** | **coop** | `groups`, seats, Safe-wallet holders |
| 2 | **Authority & commitment** | **coop** | roles, `proposals`/`votes`, `declared_binding`, session keys |
| 3 | **Disclosure & visibility** | **coop** | RLS, `SECURITY DEFINER` projections, the scope + granularity dial |
| 4 | **Availability & scheduling** | **coop** | the availability design; resource slots |
| 5 | **Operational records** | **the app** | crop cycles, catch landings, appointments, stock moves, service visits, documents, rooms |
| 6 | **Money & treasury truth** | **the ledger — never the operational app** | Safe, pools, the rail (the declared boundary) |
| 7 | **Proofs & anchors** | **coop** | the `anchors` families (`tier2`, `custody`, `coverage`, `bindings`…) |

> **Exactly one kind — operational records — is delegated to an app.** That single fact is why the
> complexity is bounded: six kinds have one permanent home, and the seventh is a *setting*.

## 2. The two tests — five seconds, not a design session

1. **Which kind is this fact?** If it is 1–4, 6 or 7 → **coop**, no discussion.
2. **Only for kind 5 — which tool is the work done in?** The app the work happens *in* owns its records.
   If there is no such tool, coop holds a minimal row (the app-less case: a drill, a hall, a route).

**The invariant that keeps it from fragmenting: a new domain may add *content*, never a new *kind of
home*.** The architecture stays at **three roles** — coop · operational app · treasury — no matter how
many domains or sectors arrive. Domains add doctypes and profiles; they do not add layers.

## 3. Sectors carry **profiles**, not architecture

A sector is a **tag on groups** (already decided, optionally attested). A sector ships a **profile**:
defaults, not code. This is where *"the platform offers profiles, not one posture"* becomes real.

| Sector | Resource axes of interest | Obligation templates | Default operational app |
|---|---|---|---|
| food | checkout, access-window | compost, market | a NocoDB base |
| agriculture | areal, movable | soil test, irrigation | ERPNext + the Agriculture doctypes |
| civic | access-window | meeting, rotation | Plane |
| *(new)* | pick from the axes | pick from the templates | **or none** |

**A sector's facts still land on the same seven kinds.** A sector never gets its own store — and a new
sector costs a profile, not a design session.

## 4. What complexity remains — honestly

- **N integrations for N apps.** Each app needs a tenant↔group mapping, a gate, an event leg, a marker
  and a reconciler. Split-by-fact does **not** remove that work. What it removes is a *second, deeper*
  copy of the model — the one that makes "who may see this" unanswerable.
- **The app count is itself the lever.** 38 apps are declared; each is an integration and a drift
  surface. The scalable position is a **small vetted set** for operational records, plus optional extras
  a group chooses — not a growing catalogue.
- **Split-by-fact cannot fix a badly chosen app.** It decides *where* a fact lands, never whether the
  tool is right for the work. A wrong tool still lands the fact in a bad home.

### 4.1 The admission bar — gate, event leg, marker, reconciler

An app joins the **vetted operational set** only when all four exist. That is the bar any "add an app"
has to clear, and it is what stops app count from becoming architecture count.

**Precondition — the mapping.** The app's own tenant boundary maps 1:1 onto a group, written as a
`resource_scopes` row (fact kinds 1 + 2 — it *is* the binding). Without it the four have nothing to
point at.

| Requirement | What it must do | The proven precedent in this stack |
|---|---|---|
| **Gate** | the fleet identity reaches the app: an oauth2-proxy gate (**unique `--cookie-name`**) or native OIDC; Gate-SSO auto-login where the app has no OIDC; `restart: unless-stopped`, because OIDC discovery has **no retry** | `nocodb-gate`, `webstudio-gate`, `litefarm-gate`; Hi.Events' public/gated split |
| **Event leg** | the app's work produces (and can consume) **typed events on the bus**, so the coop can notify, match and derive | the Matrix appservice → `events`; LiteFarm as a bus source; the delivery outbox + `deliverySweep` |
| **Marker** | a value in **the app's own field** (name / description / label) carrying the immutable `group_id`, so the binding is **discoverable and rebuildable from the authoritative side** | Plane / NocoDB / Matrix name+description; the DID's carrier-side label; the Gandi TXT for mail |
| **Reconciler** | a job that **enumerates from the authoritative side** and repairs drift | the mailbox reconciler enumerates **DNS**, not Stalwart; `provisionOnSignIn` reconciles ERPNext on login; `stack-report` declared-vs-running |

**Why the marker is not optional:** *"ours is rebuildable, so a marker stored only with us dies with
us"* (`declared-binding-registry.md` §R6). **Why the reconciler is not optional:** the authoritative side
is the side that survives us.

**And a sector profile may only name a default app from the vetted set** — otherwise a profile smuggles
an unvetted app into every group in that sector.

**The honest current state:** most apps clear two or three of the four, not four. That is the *useful*
output of the bar — it turns "should we standardise on this app?" into a four-line checklist with visible
gaps, per app. An app that clears none can still run; it simply **cannot be authoritative for anything
the coop must answer** (who may see it, who committed to it, what happened).

**What the bar does not do:** it never makes a wrong tool right (§4). It decides integration and
authority, not fit.

**Measured, not asserted:** `app-admission-audit.md` scores ten apps against this bar (2026-10-04). No app
clears all four; the gap concentrates in *marker* and *reconciler*.

## 5. Consequences

- **A new domain or sector: no design session.** Name the facts → they land on the seven kinds → pick a
  profile (or nothing).
- **A new app may only ever hold kind 5.** It cannot become the authority for identity, visibility,
  money or proofs. That is the line that keeps app count from becoming architecture count.
- **An app that holds several kinds today is a migration target, not a model.** LiteFarm holds identity
  *and* records: pull kinds 1–4 out, keep 5 (§`central-resource-store.md`).

## 6. Decisions

1. Does this become a **standing stack rule** (alongside the RLS and derived-secret rules), or stay a
   design note? *(Recommendation: a standing rule — it is what stops 38 apps becoming 38 architectures.)*
2. **Sector profiles** — build them as seed data now, or wait until the second sector needs one?
   *(Recommendation: wait; the first profile is cheap to write when a real sector asks.)*
3. **Name the vetted operational set** explicitly, or leave it implicit?
   *(Recommendation: name it — NocoDB base, Plane, ERPNext, docs/MinIO, Matrix — so "add an app" has a
   visible bar to clear.)*

## Cross-references

- `central-resource-store.md` §1 — the resource-shaped instance of this rule.
- `resource-model.md` §0.1 — "which system already holds it", answered generally here.
- `declared-binding-registry.md` — kind 2's object; the marker rule (R6) that connects a coop binding to
  an app's own field.
- `scoped-availability.md` §4 — the dial that makes kind 3 ours and not the app's.
- `erpnext-tenancy-notifications.md` — kind 6's boundary, already declared.
- `RISKS.md` R-10 — the duplication problem this rule exists to prevent.