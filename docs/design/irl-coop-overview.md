# irl.coop — Overview

Status: design · 2026-10-04 · Robbie + Hermes.
This document replaces any prior overview. It is the entry point for the entire design corpus.

irl.coop is a cooperative that runs infrastructure for its own members and for member groups. The
platform is a self-hosted stack of about thirty-eight open-source apps behind a single Traefik edge,
sitting on shared Postgres and self-managed TLS, and every account — person or group — is the same
primitive: a Safe smart contract holding keys only its owner controls. The stack is open-source, the
deployment is the coop's, and there is no venture capital, no acquisition, and no data mining. It is
a single design across five pillars, each described as one chapter below.

The first pillar is [digital identity sovereignty and federation](#1-digital-identity-sovereignty--federation-fedid). Every person owns their
identity cryptographically — a key, not a username — and can move and recover it without asking
permission. Groups of these identities can interoperate without a central authority, so two co-ops on
irl.coop can share members, resources, and money, and a member of one group can prove membership to
another without revealing anything else. *(See [`account-and-key-model.md`](/docs/design/account-and-key-model) and
[`declared-binding-registry.md`](/docs/design/declared-binding-registry).)*

The second pillar is [privacy-first relationship graphs and finance](#2-privacy-first-relationship-graphs-and-finance). The platform holds
the data that records who is in which group, but that data is privately scoped by default — to
the individual for their own memberships, and to the other members of the same group. The public
web sees only what the disclosure dial chooses to project, never the underlying membership. The
same is true of who owes whom, who paid for what, and who knows whom: nothing is published unless
the people involved choose to reveal it. Relationship graphs and financial records are
encrypted, compartmentalized, and shared only within the scope the member chooses, with a granularity
dial that defaults to the least revealing option. *(See [`scoped-availability.md`](/docs/design/scoped-availability) and
[`where-facts-live.md`](/docs/design/where-facts-live).)*

The third pillar is [the Weave](#3-dynamic-interrelated-groups--the-weave), which is the name for how dynamic, interrelated groups
form, merge, split, sponsor each other, and share resources. A weave is a network of groups
connected by declared relationships — not friendship links, but signed bindings that confer actual
rights such as `member-of`, `subgroup-of`, `federated-with`, and `sponsored-by`. *(See
[`group-shape-scenarios.md`](/docs/design/group-shape-scenarios) and [`resource-model.md`](/docs/design/resource-model).)*

The fourth pillar is [the platform cooperative itself](#4-the-infrastructure-as-a-platform-cooperative): the legal and governance wrapper
around the infrastructure. Members elect stewards, the stewards are term-limited and accountable to
the group, and the platform owns its own code and deployment. The coop's own governance decides
which apps join the vetted set, how money moves, and which external co-ops may federate. *(See
[`system-map.md`](/docs/design/system-map), [`risk-register.md`](/docs/design/risk-register), and
[`site-plugins-and-embeds.md`](/docs/design/site-plugins-and-embeds).)*

The fifth pillar is [how the stack itself is built, extended, and maintained](#5-how-the-stack-is-built-extended-and-maintained). It is
declarative, generated, and verifiable: every change is a commit, every commit is a deploy, and a
small set of shared primitives composes the rest. A standing rule — *where facts live* — keeps
thirty-eight apps from becoming thirty-eight architectures: there are seven fact kinds, exactly one
of which is delegated to an app, and a new domain may add content but never a new kind of home.
*(See [`where-facts-live.md`](/docs/design/where-facts-live) and [`app-admission-audit.md`](/docs/design/app-admission-audit).)*

Read the pillars in order if you want the whole picture. Read only the pillar that names your
concern if you do not. The §6 corpus table introduces every design doc with one line, §7 is a
live-vs-designed-vs-blocked matrix for an at-a-glance honest state, and §8 names what is still not
yet true.

---

## 1. Digital identity sovereignty + federation (FedID)

### 1.1 The idea, plain

Every person owns their own identity. Not a username on someone else's server. A cryptographic
identity — a Safe smart contract, controlled by keys only they hold — that they can move, recover,
or abandon without asking permission.

Federation means groups of these identities can interoperate without a central authority. Two
co-ops on irl.coop can share members, resources, and money. A member of one group can prove
membership to another without revealing anything else.

### 1.2 What already works

- **Passkey-based onboarding** → your identity is a cryptographic key, not a password.
- **Safe-as-everything** → every account (person or group) is a Safe smart contract. Same
  CREATE2 factory, same address derivation, same recovery path.
- **Keycloak as broker, not root** → Google signs you in, but the coop holds your session. You
  can add other brokers later (phone, email, hardware key) without re-registering.
- **Fleet identity** → one cookie (`coop_session`) reaches every app through oauth2-proxy gates.
  No second login.

### 1.3 What is designed, not built

- **Group-to-group federation** → seat transfer across groups, cross-group visibility rules,
  intergroup treasuries. See `group-model-technical-overview.html`, `declared-binding-registry.md`.
- **FedID protocols** → W3C DID, DIF Sidetree, or similar as a published identity format. The
  Safe address is already a persistent identifier; the protocol work is making it *interoperable
  with external systems*.

### 1.4 What is still an open question

- How does a member prove group membership to an *external* service (e.g., a union website, a
  government portal)? The stack can produce an EIP-1271 signature today; standardizing that into
  a VC (verifiable credential) is a design decision, not code.

---

## 2. Privacy-first relationship graphs and finance

### 2.1 The idea, plain

The platform knows who is in which group. It does **not** know who owes whom, who paid for what,
or who is related to whom — unless those people choose to reveal it.

Relationship graphs (who knows whom, who trusts whom) are sensitive. Financial records are more
sensitive. Both are encrypted, compartmentalized, and shared only within the scope the member
chooses.

### 2.2 What already works

- **RLS at the database** → every query is scoped to `app.sub`; no cross-member reads.
- **Tier-2 ledger** → contribution records (hours worked, shifts covered) are hash-chained and
  counter-signed, but the *content* is encrypted. The chain proves tamper-evidence; the content
  is private. See `tier2-entry-model.md`.
- **Zero-knowledge proofs** → Groth16 ceremony complete (`contracts/zk/README.md`). Spend proofs
  verify without revealing balances. The `contribution` and `availability` circuits extend this
  same pattern to time and commitments.
- **Disclosure dial** → every piece of member data carries a granularity setting (count / bucket
  / exact). The default is the least revealing option. See `scoped-availability.md` §4.

### 2.3 What is designed, not built

- **Scoped availability as a record** → a member's availability is a hash-chained entry with
  scope, budget, and slots. The privacy model is set: a scope sees its own slots, the world sees a
  count, nobody sees the calendar. See `scoped-availability.md`.
- **Availability proofs** → proving "I committed 3 hours this week" without revealing when. The
  circuit is a new instance of the proven `contribution` shape; the ceremony is the blocker.
  See `scoped-availability.md` §6.
- **Resources as subjects** → a real-world asset (a drill, a hall, a depot window, a route) is a
  *subject* of events. Availability and custody are *events about* subjects; the subject registry
  itself is **axes, not a type taxonomy**. Tools, land, structures, maintenance and routes each
  land on the axes. People are never resources. See `resource-model.md`.
- **Central resource store** → farm data decoupled from the farm app. Each fact has exactly one
  home: coop-api holds the subject + disclosure + authority + availability; ERPNext holds the
  operational/accounting facts (stock, valuation, maintenance visits); a `declared_binding` plus a
  marker joins them. One home per fact — which is the real fix for `RISKS.md` R-10.
  See `central-resource-store.md`.
- **Shielded treasury** → private notes, commitments, nullifiers. Design complete;
  implementation at P2 (verifier deployed, pending `setVerifier` wiring). See
  `private-treasury-guards-ledgers.md`.
- **Custody chain** → for physical goods (food, tools, seeds), an append-only signed log that
  proves transfers without revealing the network. See `custody-chain-and-contest-kit.md`.
- **Needs/offers matching** → the `match.*` event family is designed; the board is a mockup.
  Privacy: you see matches in your sector, not the whole catalogue.

### 2.4 What is still an open question

- **Money is designed, not flowing.** The payment rail is sandbox-verified; `payment_intent` has
  4 rows, all failed; the live preflight reads **2 of 6 gates green**, and the destination is
  *a delegated EOA and the merchant's own default wallet* — not the router. Seven prerequisites
  sit between today and live money: a LIVE merchant account, the vault secrets, a funded `0600`
  deployer key, the coop's Safe address on Base, `PAYMENTS_ENTITY`, and a backup. The full stub-vs-
  spike design, the no-op-fallback hedge for the router ABI, and the live preflight reading live
  in `payment-stub-and-handoff.md`.

---

## 3. Dynamic interrelated groups — the Weave

### 3.1 The idea, plain

Groups are not isolated. They form, merge, split, sponsor each other, and share resources. A food
coop and a tool library might share members. A farming coalition might spawn a child group for
seasonal labor. A city-wide federation might coordinate ten neighborhood groups.

This interrelated structure needs a name, a model, and a UI that makes it visible without making
it a surveillance map.

### 3.2 The name: **the Weave**

A weave is a network of groups connected by declared relationships. Each relationship is a
**binding** — a signed, anchorable record of what one group says about another.

Relationships are not friendship links. They confer actual rights:
- `member-of` → I have a seat in that group.
- `subgroup-of` → my parent group's governance reaches me.
- `federated-with` → we share a sector tag and can see each other's scoped availability.
- `sponsored-by` → they vouched for my sector tag (e.g., "this group is certified organic").

### 3.3 What already works

- **Groups ARE Safes** → every group is the same primitive as every account. A child group is
  just a Safe deployed by its parent's Safe. See `irl-coop-group.md` §2.1.
- **Seat model** → `group_members` table with roles, visibility, and `joinedAt`. One row = one
  membership edge.
- **Sector tags** → a sector is a **tag on groups**, optionally attested by the irl.coop group.
  A sector is a filter on the weave, not a wall. The attestation is the same object as
  elsewhere — a counter-signature from conferred authority. See `scoped-availability.md` §1,
  `declared-binding-registry.md` §R5.
- **Resource scopes** → `resource_scopes { group_id, app, resource_key }` links a group to its
  tenant in every app. See `group-shape-scenarios.md` §2.
- **Composition, not inheritance** → a farm, a tool library, a makerspace are full groups that
  happen to use a particular app. Strip the binding and the group stands alone. See
  `litefarm-integration.md` §2, `group-shape-scenarios.md`.

### 3.4 What is designed, not built

- **The weave graph API** → `GET /api/v1/weave/:group_id` returns the group's declared
  relationships, scoped by what the caller may see. Public = only `federated-with` and `sponsored`
  tags. Member = full graph.
- **Visual weave navigator** → `react-force-graph-2d` ONLY (per the UI doctrine). Zoom = focus
  on one group and its immediate neighbors. No global "see all groups" view.
- **Rights-set inheritance** → a child group inherits its parent's `member-of` edges, filtered
  by scope. See `group-model-technical-overview.html` §7.
- **Resources across the weave** → a group's resources (a depot window, a route, a hall) are
  scoped to the group, with disclosure rules inherited from the availability model. A resource
  is never a person: people participate via availability + credential tags. See
  `resource-model.md` §3.4.

### 3.5 What is still an open question

- **How many relationships before the UI breaks?** If a group has 100 `federated-with` edges,
  the force-graph is noise. The answer is **clustering by sector** — groups in the same sector
  collapse into a node until you zoom in. Not yet designed.

---

## 4. The infrastructure as a platform cooperative

### 4.1 The idea, plain

irl.coop is not a SaaS company. It is a **cooperative that runs infrastructure** — for its own
members, for member groups, and for allied organizations. The platform itself has a governance
model: member-owned, democratically controlled, surplus returned to members.

The infrastructure stays under member control. No venture capital, no acquisition, no data
mining. The code is open-source; the deployment is the coop's.

### 4.2 What already works

- **Self-hosted stack** → 38 apps, one Traefik edge, shared Citus Postgres, self-managed TLS.
  See `SYSTEM-MAP.md`, `RISKS.md`.
- **Cost model** → member dues + group infrastructure contributions cover hosting + stewardship.
  $73/mo base + $4.50/mo per group in the current model. See `cost-model.md`.
- **No platform lock-in** → every app can be stripped out (`resource_scopes` row deleted =
  independent). The `declared-binding-registry.md` §R6 marker ensures rebuildability.
- **Open-source licensing** → the dashboard is MIT; the ZK circuits are GPL-3; the coop's own
  code is whatever the group decides.

### 4.3 What is designed, not built

- **Governance of the platform itself** → the irl.coop group (as a Safe) votes on:
  - infrastructure spending (hosting upgrades, new nodes)
  - app admission to the vetted set
  - steward compensation and rotation
  - federation partnerships (which external co-ops may join)
- **Steward rotation** → the technical steward role is elected, term-limited, and accountable
  to the group. The Safe threshold enforces this: a steward alone cannot spend treasury funds.
- **Plugins for other people's platforms** → Squarespace, Wix and WordPress. WordPress gets the
  full treatment (a version-controlled plugin, server-side PHP, the recipe already exists in
  `assets/wordpress/`); Wix gets a partial treatment via Velo; Squarespace gets a widget only —
  Code Injection on Business+. **The site never takes the card**; it does catalogue → cart →
  handoff to the coop's own checkout. See `site-plugins-and-embeds.md`.
- **The vetted operational set** → the small set of apps cleared through the admission bar that
  sector profiles may name as defaults. The bar is documented in `where-facts-live.md` §4.1 and
  `app-admission-bar.md` (in the apps skill). Most apps clear 2–3 of 5; the gap is concentrated in
  the back half — *marker* and *reconciler* — which is the highest-leverage work outstanding.

### 4.4 What is still an open question

- **Legal entity** → in which jurisdiction is the platform cooperative incorporated? This decides
  tax, liability, and regulatory exposure. The `PAYMENTS_ENTITY` field (`payments.ts`) exists
  precisely because this is undecided.

---

## 5. How the stack is built, extended, and maintained

### 5.1 The idea, plain

The stack is **declarative, generated, and verifiable**. You describe what you want in YAML; the
generator produces Docker Compose; the reconciler checks that reality matches the declaration.

Changes are **small, reversible, and traceable**. No hand-editing generated files. No
snowflake servers. Every change is a commit, every commit is a deploy.

### 5.2 What already works

- **Generator** (`infra/build/generator.py`) → YAML → `out/dev/compose/`. Idempotent;
  `rmtree`s `out/` each run so generated files are never hand-edited.
- **Stack report** (`infra/scripts/stack-report.py`) → declared vs running containers, status
  per service.
- **Journey suite** → 29/30 browser-automated tests verify end-to-end flows (SSO, group
  creation, file upload, etc.). See `infra/scripts/journeys/`.
- **Reconcilers** → DNS enumeration for mail, `provisionOnSignIn` for ERPNext, `stack-report`
  for drift. See `app-admission-bar.md` §4.

### 5.3 The rule: where facts live

The stack's standing rule: there are **seven fact kinds**, and **exactly one** — operational
records — is delegated to an app. The coop owns the other six. Identity, authority, disclosure,
availability, money and proofs never live inside an app's permission model. A new domain adds
content; it never adds a new kind of home. Architecture stays at three roles — coop, operational
app, treasury — no matter how many domains arrive. Sectors ship **profiles** (defaults: which
resource axes matter, which obligation templates, which operational app), not architecture.

This is the rule that keeps 38 apps from becoming 38 architectures. See `where-facts-live.md`.

### 5.4 The admission bar (where the rule gets measured)

An app joins the **vetted operational set** only when it clears all of:

| Gate | What it means |
|---|---|
| **Mapping** | tenant ↔ group via `resource_scopes` |
| **Gate** | fleet SSO reaches the app (oauth2-proxy or native OIDC) |
| **Event leg** | the app produces typed events on the bus (or, for a site, consumes state) |
| **Marker** | the app carries an immutable `group_id` in its own fields |
| **Reconciler** | a job repairs drift by enumerating from the authoritative side |

The current standing: **no app clears all five**. The gap concentrates in *marker* and
*reconciler* — the back half — which is what `declared-binding-registry.md` §3 lists as a
**"Now"** item and what's not verifiably built yet. **Mail is the reference implementation** —
its binding is discoverable because the marker lives in DNS, and its reconciler enumerates DNS
rather than Stalwart. The current snapshot is in `app-admission-audit.md` (dated, doc-derived,
not a live verification).

### 5.5 What is designed, not built

- **Seam drills** → periodic tests that swap a provider (e.g., mail from Stalwart to something
  else) and verify continuity. Never run. See `provider-seams.md`.
- **Dev/prod parity** → today dev and prod are the same instance with different env vars. True
  prod isolation (separate instance, separate vault) is designed but not funded.
- **Observability** → metrics, alerting, SLOs. The Temporal worker reports health; Prometheus
  is not deployed.

### 5.6 What is still an open question

- **Who operates the stack?** Currently Robbie is the sole steward. The platform cooperative
  governance model says members elect stewards, but the election mechanism is designed, not
  implemented. See §4.3.

---

## 6. The design corpus — how to read it

This section introduces every design doc by one-line purpose. New docs introduced in October
2026 are **bolded**; everything else predates this session.

| Doc | Read if you want to understand |
|---|---|
| **`scoped-availability.md`** | A member's time as a hash-chained, scope-partitioned record. The rule, the granularity dial, the proof-first sequencing — the substrate of every "who's available to do what" question in the stack |
| **`resource-model.md`** | What a *resource* is when there is no registry for things. Axes (location kind, engagement, contention, custodian, obligations, provenance, disclosure), not a type taxonomy. Where each of tools, land, structures, maintenance and routes lands. Why people are never resources |
| **`central-resource-store.md`** | Decoupling farm data from the farm app. Split-by-fact (coop-api = subject + disclosure; ERPNext = operational facts), one home per fact, the cheap reversible Agriculture test, what happens to LiteFarm |
| **`where-facts-live.md`** | The seven fact kinds; exactly one delegated to an app; the two five-second tests; the invariant that a new domain may add content but never a new kind of home; sectors as profiles |
| **`app-admission-audit.md`** | A dated snapshot: ten apps scored against the admission bar. Most clear 2–3 of 5; the gap is concentrated in marker + reconciler; mail is the reference implementation |
| **`crm-under-fact-kinds.md`** | The CRM question under the fact-kind split. A CRM is kind 5 only; identity and visibility are ours. Recommends ERPNext-native and narrows Twenty's role to a kind-5 UI |
| **`site-plugins-and-embeds.md`** | Squarespace, Wix and WordPress plugins that surface coop features via coop-api. What each platform actually allows, why the surface is a projection that owns no facts, the bar applied to a site (with the event leg inverted and a DNS marker), the third-party-cookie constraint, and the checkout-handoff pattern |
| **`payment-stub-and-handoff.md`** | The payment seam: stub vs spike. The seam exists; the acceptance test exists. A stub rail unblocks all ecommerce product work; the spike has phases. Live preflight reads 2/6 green; the destination is a delegated EOA and the merchant's own default wallet. The router ABI question (delivery method, fallback hedge) is §9 |
| `irl-coop-group.md` | the group primitive: Safe, invite-on-first-signin, roles, voting |
| `account-and-key-model.md` | passkeys, session keys, Safe architecture |
| `private-treasury-guards-ledgers.md` | shielded notes, nullifiers, tiers, the treasury |
| `tier2-entry-model.md` | contribution ledger, counter-signatures, authority classes |
| `sharded-ledgers-and-anchors.md` | how entries shard across nodes, one anchor stream |
| `declared-binding-registry.md` | the commitment object: a unified table for relationships, resources, telephony; authority classes; per-group roots; the marker rule (R6) that makes bindings rebuildable |
| `custody-chain-and-contest-kit.md` | physical goods tracking, chain of custody |
| `event-bus-and-group-shapes.md` | group shapes, the event bus, provisioning |
| `group-shape-scenarios.md` | ten scenarios reduced to a small set of shared primitives; the capability matrix |
| `group-model-technical-overview.html` | the group primitive, seat model, rights-set inheritance, the visual weave |
| `adversary-models-and-sector-fit.md` | threat models, footprint, confidentiality floors |
| `money-in-and-out.md` | every money flow, what exists, what blocks it |
| `provider-seams.md` | how the coop-api talks to providers without learning their names |
| `coop-launch-and-roadmap-handoff.md` | (parked) founding the coop itself |

---

## 7. What is live vs designed vs blocked

| Layer | Live | Designed | Blocked |
|---|---|---|---|
| **Identity** | Passkey + Safe + Keycloak + fleet SSO | FedID protocols, cross-group proof | — |
| **Privacy** | RLS, seat visibility, encrypted T2 content, **the scoped-availability model**, **the seven fact kinds** | ZK proofs (P2 ceremony done, pending wiring), shielded treasury, **availability proofs (circuit shape decided; ceremony blocks)** | — |
| **Weave** | Groups are Safes, seat model, sector tags, **resource model + central-store direction** | Weave graph API, visual navigator, rights-set inheritance | — |
| **Cooperative** | Self-hosted, cost model, open-source, **the admission bar + audit**, **site-plugins story** | Platform governance, steward rotation, legal entity | Legal entity |
| **CRM / relationships** | ERPNext-native tenant + User Permissions, **D-22 closed as ERPNext-native** | Twenty as a possible kind-5 UI; triggered by a real gap | — |
| **DevOps** | Generator, stack report, journey suite, reconcilers (partial) | Seam drills, prod isolation, observability, **the marker + reconciler work outstanding** | Funding |
| **Money** | — | Payment contract, rail, router, **stub-vs-spike design** | Merchant account, vault secrets, deployer key, `PAYMENTS_ENTITY`, backup; **destination is currently wrong** |

---

## 8. Honest limits

- **The stack is running, not launched.** 38 apps, most operational, but no group is using it
  for real work yet.
- **Money is designed, not flowing.** `payment_intent` has 4 rows, all failed. The router is
  un-deployed on mainnet. The live preflight reads **2 of 6 gates green** and the destination is
  a delegated EOA and the merchant's own default wallet — not the router. Seven prerequisites sit
  between today and live money. See `payment-stub-and-handoff.md`.
- **The coop itself is not yet a group on the platform.** irl.coop is a design, a Safe
  narrative, not a deployed group with members voting. See `coop-launch-and-roadmap-handoff.md`.
- **Availability is not yet a record.** The `availability_entry` table does not exist. The proof
  architecture exists but depends on the record.
- **No app clears the full admission bar.** The audit found 2–3 of 5 typically, with the gap in
  marker + reconciler. See `app-admission-audit.md`.
- **The weave is conceptual.** No `weave` API, no force-graph navigator, no cross-group
  matching beyond the designed event shape.
- **D-22 answered, not built.** Twenty is parked; ERPNext is the CRM. The recommendation is
  closed but the work to make it real (a kind-5 surface, projection, the bar) is not.
- **Site work is unblocked for everything except money.** Catalogue, cart, checkout **handoff**
  (the site never takes the card), bookings, events, chat/meetings/feeds — all buildable
  today. Paid halves (tickets, paid bookings, the storefront) wait on the same single dependency
  (the coop's payment path) and unlock together.

---

## Cross-references

- `design-docs.json` — the registry of all 85 design docs, with status and category.
- `landing-page-claims-audit.md` — every claim on the public site, classified as shipped /
  stated / designed / aspirational.
- `REALITY.md` — per-capability honest status.
- `RISKS.md` — R-07 (backup), R-10 (data isolation), R-11 (custody), and the rest.
