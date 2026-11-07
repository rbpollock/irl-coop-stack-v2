# irl.coop — Overview

Status: design · 2026-10-04 · Robbie + Hermes.
This document replaces any prior overview. It is the entry point for the entire design corpus.
Five pillars. Each pillar names a concept, maps it to built reality, and cites the design doc that
specifies it.

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
- **Disclosure dial** → `scoped-availability.md` §4: every piece of member data carries a
granularity setting (count / bucket / exact). The default is the least revealing option.

### 2.3 What is designed, not built

- **Shielded treasury** → private notes, commitments, nullifiers. Design complete;
implementation at P2 (verifier deployed, pending `setVerifier` wiring). See
`private-treasury-guards-ledgers.md`.
- **Custody chain** → for physical goods (food, tools, seeds), an append-only signed log that
proves transfers without revealing the network. See `custody-chain-and-contest-kit.md`.
- **Needs/offers matching** → the `match.*` event family is designed; the board is a mockup.
Privacy: you see matches in your sector, not the whole catalogue.

### 2.4 What is still an open question

- **Availability proofs** → proving "I committed 3 hours this week" without revealing when.
The circuit is a new instance of the proven `contribution` shape; the ceremony is the blocker.
See `scoped-availability.md` §6.

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
- **Sector tags** → `group.tags`, optionally attested by the irl.coop group. A sector is a
filter on the weave, not a wall. See `scoped-availability.md` §1.
- **Resource scopes** → `resource_scopes { group_id, app, resource_key }` links a group to its
tenant in every app. See `group-shape-scenarios.md` §2.

### 3.4 What is designed, not built

- **The weave graph API** → `GET /api/v1/weave/:group_id` returns the group's declared
relationships, scoped by what the caller may see. Public = only `federated-with` and `sponsored`
tags. Member = full graph.
- **Visual weave navigator** → `react-force-graph-2d` ONLY (per the UI doctrine). Zoom = focus
on one group and its immediate neighbors. No global "see all groups" view.
- **Rights-set inheritance** → a child group inherits its parent's `member-of` edges, filtered
by scope. See `group-model-technical-overview.html` §7.

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
- **Version-controlled plugins** → WordPress plugins mounted read-only from `assets/wordpress/`,
driven by wp-cli. The pattern applies to every platform. See `wordpress.yaml`.

### 5.3 The rule: the admission bar

An app joins the vetted operational set only when it clears four gates:

| Gate | What it means |
|---|---|
| **Mapping** | tenant ↔ group via `resource_scopes` |
| **Identity gate** | fleet SSO reaches the app (oauth2-proxy or native OIDC) |
| **Event leg** | the app produces typed events on the bus |
| **Marker** | the app carries an immutable `group_id` in its own fields |
| **Reconciler** | a job repairs drift by enumerating from the authoritative side |

The bar is documented in `where-facts-live.md` §4.1 and `app-admission-bar.md`. Most apps clear
2–3 of 5; none clears all 5. That gap is the roadmap.

### 5.4 What is designed, not built

- **Seam drills** → periodic tests that swap a provider (e.g., mail from Stalwart to something
else) and verify continuity. Never run. See `provider-seams.md`.
- **Dev/prod parity** → today dev and prod are the same instance with different env vars. True
prod isolation (separate instance, separate vault) is designed but not funded.
- **Observability** → metrics, alerting, SLOs. The Temporal worker reports health; Prometheus
is not deployed.

### 5.5 What is still an open question

- **Who operates the stack?** Currently Robbie is the sole steward. The platform cooperative
governance model says members elect stewards, but the election mechanism is designed, not
implemented. See §4.3.

---

## 6. The design corpus — how to read it

| Doc | Read if you want to understand |
|---|---|
| `irl-coop-group.md` | the group primitive: Safe, invite-on-first-signin, roles, voting |
| `account-and-key-model.md` | passkeys, session keys, Safe architecture |
| `private-treasury-guards-ledgers.md` | shielded notes, nullifiers, tiers, the treasury |
| `tier2-entry-model.md` | contribution ledger, counter-signatures, authority classes |
| `sharded-ledgers-and-anchors.md` | how entries shard across nodes, one anchor stream |
| `scoped-availability.md` | who sees what, when, with what granularity |
| `where-facts-live.md` | the seven fact kinds, the admission bar, sector profiles |
| `event-bus-and-group-shapes.md` | group shapes, the event bus, provisioning |
| `custody-chain-and-contest-kit.md` | physical goods tracking, chain of custody |
| `adversary-models-and-sector-fit.md` | threat models, footprint, confidentiality floors |
| `money-in-and-out.md` | every money flow, what exists, what blocks it |
| `coop-launch-and-roadmap-handoff.md` | (parked) founding the coop itself |

---

## 7. What is live vs designed vs blocked

| Layer | Live | Designed | Blocked |
|---|---|---|---|
| **Identity** | Passkey + Safe + Keycloak + fleet SSO | FedID protocols, cross-group proof | — |
| **Privacy** | RLS, seat visibility, encrypted T2 content | ZK proofs (P2 ceremony done, pending wiring), shielded treasury | — |
| **Weave** | Groups are Safes, seat model, sector tags | Weave graph API, visual navigator, rights-set inheritance | — |
| **Cooperative** | Self-hosted, cost model, open-source | Platform governance, steward rotation, legal entity | Legal entity |
| **DevOps** | Generator, stack report, journey suite, reconcilers (partial) | Seam drills, prod isolation, observability | Funding |

---

## 8. Honest limits

- **The stack is running, not launched.** 38 apps, most operational, but no group is using it
for real work yet.
- **Money is designed, not flowing.** The payment rail is sandboxed; 4 `payment_intent` rows,
all failed. The router is un-deployed on mainnet. See `payment-stub-and-handoff.md`.
- **The coop itself is not yet a group on the platform.** irl.coop is a design, a Safe
narrative, not a deployed group with members voting. See `coop-launch-and-roadmap-handoff.md`.
- **Availability is not yet a record.** The `availability_entry` table does not exist. The
proof architecture exists but depends on the record.
- **The weave is conceptual.** No `weave` API, no force-graph navigator, no cross-group
matching beyond the designed event shape.

---

## Cross-references

- `design-docs.json` — the registry of all 85 design docs, with status and category.
- `landing-page-claims-audit.md` — every claim on the public site, classified as shipped /
stated / designed / aspirational.
- `REALITY.md` — per-capability honest status.
- `RISKS.md` — R-10 (data isolation), R-11 (custody), and the rest.
