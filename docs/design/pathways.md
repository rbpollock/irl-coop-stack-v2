# Pathways — Design Doc Index

Cross-references to "pathways" across the irl.coop design docs.

---

## What Pathways Is

Pathways is an **agentic orchestration DSL and specification** for building portable, attestable, cross-group workflows. It is not a single app or service — it is a **catalogue of independent collaborations**: channels, repositories, and counterparty relationships that share a common grammar (pathway templates, patterns, terms, and Shared Domain Graphs) while keeping their own data sovereign.

The core artifact is the **PathwayRun**: an execution instance of a reusable **pathway template** that records provenance at every step. A run can span tools, agents, and groups without merging data into a central store. Instead, it emits typed **HandoffBus** envelopes at trust boundaries and anchors lineage through **Aqua** attestations.

Key traits:
- **Template-driven** — a pathway is a declarable, versioned script for multi-step work (e.g. "Customer Onboarding", "Spec Revision", "Quarterly Reimbursement").
- **Attestable** — every run, template, and revision can carry an AquaTree hash attestation signed by a DID, so lineage is verifiable offline.
- **Autonomy-banded** — a `gate_profile` assigns an autonomy band (A0 instant → A3 cross-boundary) that decides whether a step blocks for human approval or proceeds automatically.
- **Handoff-aware** — when a run crosses a trust boundary (a "seam"), it passes a typed `HandoffEnvelope` instead of free-form messages, preventing the bus from degrading into chat.
- **Federated** — groups discover and adopt templates through **Pathways Trusted Peering (PTP)**, not through a centralized catalog. Attribution and lineage travel with reuse; stripping origin is a non-delegable act.

The canonical specification (RIS 1.2.0) and architecture live in the upstream `djat_x_pathways` repository. irl.coop pins to 1.2.0 and treats its integration design as a **practice profile** — a domain binding that maps Pathways primitives to the irl.coop event bus, Safe treasury, and five-axis governance shape.

---

## Why Pathways Benefits irl.coop

irl.coop is built on the idea that **groups are autonomous, not users**. A group is a Safe contract with its own treasury, roles, and rules. Pathways makes that autonomy *portable* and *provable*:

1. **Workflows that survive the group**
   A PathwayRun is not locked inside a single group’s database. It carries its own identity (`pr_<hex>`), provenance hypergraph, and Aqua attestation. If a group pauses or forks, the run history remains verifiable and reusable by anyone who holds the attestation.

2. **Governance at the speed of work**
   Because every mutating step emits an intent and respects a `gate_profile`, the same approval machinery (A0–A3 bands, steward review, Safe threshold signing) governs *routine* work the same way it governs *extraordinary* proposals. No special cases.

3. **Cross-group coordination without a platform owner**
   A pathway can hand off from one group to another — for example, a local chapter requesting funds from a regional pool — without either group giving up custody. The `HandoffEnvelope` carries the request; the receiving group’s governance decides. Pathways has no central kill switch (the §12.6 Sovereignty Invariant), so groups remain sovereign even if the upstream spec stewards change direction.

4. **Composable across the stack**
   Pathways sits on top of the event bus, Plane issues, ERPNext records, and Safe transactions. A single template can span CRM, task tracking, accounting, and treasury — but each system only sees the typed intents it understands. The five-axis bus becomes the seam layer, not the bottleneck.

---

## Referencing Documents

| Document | Relevant Lines | Context |
|----------|---------------|---------|
| [pathways-integration.md](./pathways-integration.md) | Entire doc | Full Pathways × irl.coop integration spec: sovereignty invariant, escrow, insurance primitives, and practice profile binding. |
| [ai-pathways-temporal-workflow-generation.md](./ai-pathways-temporal-workflow-generation.md) | Entire doc | AI-assisted, Pathways-aware Temporal workflow generation with automated validation, version pinning, and group-local governance. |
| [pathways-aqua-app-marketplace.md](./pathways-aqua-app-marketplace.md) | Entire doc | Pathways + Aqua attestations for app-marketplace governance: versioned, signed, auditable workflows. |
| [keycloak-citus-federation.md](./keycloak-citus-federation.md) | 21, 71 | Uses Pathways `HandoffEnvelope` as the cross-trust-boundary message format in three-layer federation. |
| [federation-transition-plan.md](./federation-transition-plan.md) | 30, 220, 473 | Lists `HandoffEnvelope` as cross-node message format and defines establishment flow as an A3 Pathways run. |
| [global-node-architecture.md](./global-node-architecture.md) | 23, 25, 139 | Pathway runs replace ActivityPub follows/replies for cross-instance batch transfers and resource sharing. |
| [sealed-accord-weaving.md](./sealed-accord-weaving.md) | 228 | Uses Pathways orchestration alongside Aqua attestations and Lit Chipotle confidential execution. |
| [trainable_mediator_skills.md](./trainable_mediator_skills.md) | 10, 125 | References Pathways Cooperative Governance, mutual-respect edges, and pathway pluralism in mediation. |
| [plane-irl-integration.md](./plane-irl-integration.md) | 92, 216 | Group pathway runner integration and `pathway: intake-review` event on the five-axis bus. |
| [e2e-test-plans.md](./e2e-test-plans.md) | 1, 4, 92–137 | E2E test suite covering pathway launch, step blocking by intent, A0/A3 autonomy bands, and pathway-to-Plane handoffs. |

---

## Other Integration Areas (Imagined)

Pathways is intentionally thin orchestration on top of existing group resources. Here are other parts of the stack where pathway templates could land:

| Target System | Imagined Pathway | Why It Fits |
|---------------|-----------------|-------------|
| **ERPNext** | "Quarterly Reimbursement" — collect receipts → create Purchase Invoice → queue Safe payout | ERP already holds cost centers and approvals; pathways bridge the gap to on-chain treasury. |
| **Matrix / Element** | "Member Onboarding" — intake form → background check (A1) → Matrix invite → grant `coop_member` cert | The chat layer is where coordination happens; pathways can automate the trust ramp. |
| **Telnyx / Telephony** | "Hotline Escalation" — SMS intake → classify intent → auto-reply (A0) or page steward (A3) | Per-group DIDs and SIM identity mean pathways can treat a phone number as a first-class trigger. |
| **Postiz** | "Campaign Approval" — draft post → steward review (A1) → schedule → cross-post to group Mastodon/X | Social outreach currently lives outside governance; a pathway would put it on the bus. |
| **Safe / ZK Badge** | "Regenerative Score Payout" — oracle feed → compute score → mint ZK badge → trigger streaming payment | Ties the 5-axis shape system and ZK proofs to recurring, rule-based treasury actions. |
| **Needs & Offers (Weaving)** | "Mutual-Aid Loop" — publish need → match offer → confirm handoff → close loop on map + treasury | The "loops" noun is a natural fit for a pathway template: linear steps that close a social contract. |

*None of these are built yet. They are sketches for where pathways could extend governance into daily group operations without centralizing control.*

---

## Key Concepts

- **Pathway** — a declarable, versioned template for multi-step agentic/orchestrated work
- **PathwayRun** — a single execution instance with its own identity (`pr_<hex>`) and provenance hypergraph
- **HandoffEnvelope** — typed shape used when a run crosses a trust boundary (seam)
- **Aqua attestation** — hash-tree proof of template/run lineage, verifiable offline
- **Gate profile / Autonomy bands** — A0 (instant) through A3 (cross-boundary) determine whether a step blocks for approval
- **Pathways Trusted Peering (PTP)** — protocol for two peers to exchange template improvements without handing over private material
- **Practice profile** — domain-specific binding that maps Pathways primitives to a target stack (e.g. irl.coop event bus + Safe)
