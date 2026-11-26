
# irl.coop Design Documents — Table of Contents

Last updated: 2026-11-20  
Total documents: ~151  

Click any link to jump to that design document. Status keywords: `design` = spec/decision record, `plan` = execution plan, `research` = options explored, `audit` = review/assessment.

---

## Architecture & System Foundation

| Document | Status | Summary |
|---|---|---|
| [irl-coop-overview.md](irl-coop-overview.md) | design | High-level overview of the platform and its goals |
| [system-map.md](system-map.md) | checkpoint | How the system is put together |
| [stack-catalog.md](stack-catalog.md) | inventory | Complete inventory of all declared apps |
| [infra-management-monitoring.md](infra-management-monitoring.md) | design | How the stack is declared, brought up, tracked, and watched |
| [infrastructure-bringup.md](infrastructure-bringup.md) | operational | Reproducible cold-host bring-up, 9-command one-shot |
| [group-operated-stack.md](group-operated-stack.md) | design | Operating the stack from within; successorship is a group |
| [devops-and-maintenance.md](devops-and-maintenance.md) | design | Build, extend, maintain the infrastructure |
| [planned-additions.md](planned-additions.md) | plan | Apps and services evaluated for future integration |

---

## Group Primitive — The Core Model

| Document | Status | Summary |
|---|---|---|
| [irl-coop-group.md](irl-coop-group.md) | design | Safe-as-the-Co-op, invite-on-first-signin, roles, voting, Matrix channels |
| [group-shape-and-lifecycle.md](group-shape-and-lifecycle.md) | draft | The group as a moving shape, not a fixed type |
| [group-shape-scenarios.md](group-shape-scenarios.md) | notes | Scenario notes companion to group shapes |
| [group-scoping.md](group-scoping.md) | implemented | Group-scoping and privacy tiers spec |
| [group-home.md](group-home.md) | design | One graph, three axes — the group home screen |
| [group-ui-todo.md](group-ui-todo.md) | todo | Build checklist for the group home surface |
| [group-who-picker.md](group-who-picker.md) | design | The group-aware "who" picker primitive |
| [seat-holder-is-a-safe.md](seat-holder-is-a-safe.md) | spec | D-16 implementation: a seat holder IS a Safe |
| [group-account-resource.md](group-account-resource.md) | design | The account resource and group custody operations |
| [group-secret-vault.md](group-secret-vault.md) | design | Group Secret Vault design note |

---

## Identity, Auth & Federation

| Document | Status | Summary |
|---|---|---|
| [identity-sovereignty-and-fedid.md](identity-sovereignty-and-fedid.md) | design | Digital Identity Sovereignty + Federation (FedID) |
| [account-and-key-model.md](account-and-key-model.md) | discussion | Account & Key Model design note |
| [chain-agnostic-identity.md](chain-agnostic-identity.md) | design | Corrects an EVM assumption in the identifier layer |
| [cross-chain-action.md](cross-chain-action.md) | design | One authority, many places to act |
| [multi-chain-accounts.md](multi-chain-accounts.md) | design | How a group manages multi-chain accounts |
| [chain-risk-and-portability.md](chain-risk-and-portability.md) | design | Structural dependency on Base L2, portability plan |
| [keycloak-citus-federation.md](keycloak-citus-federation.md) | design | 3-layer federation: Keycloak OIDC / Safe-signed Pathways / Citus RLS |
| [federation-transition-plan.md](federation-transition-plan.md) | planning | Phased migration from one node to many — all service areas |
| [global-node-architecture.md](global-node-architecture.md) | design | Mastodon-not-Slack: many identical nodes, DHT discovery, Safe trust |
| [federation-encryption-and-access.md](federation-encryption-and-access.md) | design | Federation encryption and operator access control |
| [event-bus-and-group-shapes.md](event-bus-and-group-shapes.md) | design | Five-axis event bus and group shape taxonomy |
| [invitation-and-join-mechanism.md](invitation-and-join-mechanism.md) | design | How people are invited and join a group |
| [onboarding-flow.md](onboarding-flow.md) | design | Step-by-step new member onboarding |
| [cooperative-onboarding-kit.md](cooperative-onboarding-kit.md) | design | Facilitator's instrument for onboarding |

---

## Data & Storage

| Document | Status | Summary |
|---|---|---|
| [sharded-ledgers-and-anchors.md](sharded-ledgers-and-anchors.md) | design | Sharded ledgers with a single anchor stream |
| [private-treasury-guards-ledgers.md](private-treasury-guards-ledgers.md) | spec | ZK Treasury, guards, and ledger design |
| [private-treasury-implementation-plan.md](private-treasury-implementation-plan.md) | plan | Implementation and test plan for shielded treasury |
| [where-facts-live.md](where-facts-live.md) | design | The fact-kind split: raw, interpreted, normative statements |
| [resource-model.md](resource-model.md) | design | What a group holds, uses, or schedules |
| [world-doc-and-contacts.md](world-doc-and-contacts.md) | spec | World-Doc & Group-Aware Contact Model |
| [world-doc-virtual-workspace.md](world-doc-virtual-workspace.md) | draft | Virtual workspace + NocoDB integration spec |
| [knowledge-aggregation.md](knowledge-aggregation.md) | design | The world-doc of knowledge — public, group, private tiers |
| [innovative-postgres-sync.md](innovative-postgres-sync.md) | research | pglogical, Electric SQL, PowerSync, CRDT hybrid options |
| [central-resource-store.md](central-resource-store.md) | direction | Farm app → real-world resource store |

---

## Treasury, Payments & Economy

| Document | Status | Summary |
|---|---|---|
| [money-in-and-out.md](money-in-and-out.md) | gap map | Complete flow: card in → USDC in Safe → payouts |
| [payment-stub-and-handoff.md](payment-stub-and-handoff.md) | design | The payment seam — a stub rail and checkout handoff |
| [payout-capability.md](payout-capability.md) | design | Recognised work to money a member can spend |
| [fundraising-programmable-transfers.md](fundraising-programmable-transfers.md) | design | Fundraising dashboard + programmable transfer automation |
| [treasury-ui-and-note-secret.md](treasury-ui-and-note-secret.md) | design | Treasury on-screen: note vault, split, and privacy |
| [mainnet-deploy.md](mainnet-deploy.md) | runbook | Contracts on Base mainnet deployment plan |
| [transfer-authority.md](transfer-authority.md) | design | Transfer authority state machine and edge registry |
| [declared-binding-registry.md](declared-binding-registry.md) | spec | Finalized spec for binding registry |
| [external-bindings-resilience.md](external-bindings-resilience.md) | design | Making resource_scopes and DIDs survivable |

---

## Privacy, ZK & Security

| Document | Status | Summary |
|---|---|---|
| [zk-membership-graph-proofs.md](zk-membership-graph-proofs.md) | feasibility | Provable-but-private group graph |
| [privacy-first-graphs-and-finance.md](privacy-first-graphs-and-finance.md) | design | Privacy-first relationship graphs and finance |
| [proven-zk-options.md](proven-zk-options.md) | research | ZK options investigated and tradeoffs |
| [p2-build-plan.md](p2-build-plan.md) | design | Shielded treasury circuit family and test plan |
| [p2-stack-integration.md](p2-stack-integration.md) | design | How the proving layer slots into the stack |
| [groth16-ceremony.md](groth16-ceremony.md) | design | Trusted setup — launch honesty, member attestation, rotation |
| [security-review.md](security-review.md) | audit | Adversarial security review (model-generated) |
| [whole-system-adversarial-review.md](whole-system-adversarial-review.md) | audit | Whole-system adversarial review |
| [security-review-open-questions.md](security-review-open-questions.md) | audit | Verdicts and open questions from security review |
| [risk-register.md](risk-register.md) | register | Known risks and mitigations |
| [custody-and-agent-keys.md](custody-and-agent-keys.md) | design | Custody and agent keys — a holistic fix |
| [custody-chain-and-contest-kit.md](custody-chain-and-contest-kit.md) | design | Custody chain and the contest kit |
| [delegation-and-session-keys.md](delegation-and-session-keys.md) | design | Delegation, Session Keys & Temporal Automation |
| [regenerative-vision-note.md](regenerative-vision-note.md) | draft | Regenerative Score as a ZK-Metric |

---

## Infrastructure & Operations

| Document | Status | Summary |
|---|---|---|
| [firewall-gui-options.md](firewall-gui-options.md) | analysis | Analysis of GUI firewall tools for nftables |
| [rdp-security-assessment.md](rdp-security-assessment.md) | assessment | Network security engineer viewpoint on RDP hardening |
| [tailnet-rdp-setup.md](tailnet-rdp-setup.md) | operational guide | Secure remote desktop locked to tailnet |
| [email-deliverability.md](email-deliverability.md) | fix | Why mail lands in spam and how to fix it (DKIM/DMARC/SPF) |
| [nocodb-rebuild-handoff.md](nocodb-rebuild-handoff.md) | handoff | NocoDB rebuild state — 2026-09-16 |
| [nocodb-rebuild-plan.md](nocodb-rebuild-plan.md) | plan | NocoDB rebuild execution plan, A→B→C |
| [handoff-2026-08-13.md](handoff-2026-08-13.md) | handoff | Session handoff — stack live, passkey enabled |
| [coop-readiness-probe.md](coop-readiness-probe.md) | design | Pre-launch readiness checklist |
| [coop-work-signup-checkoff.md](coop-work-signup-checkoff.md) | design | Printable task sheet for cooperative work |
| [coop-launch-and-roadmap-handoff.md](coop-launch-and-roadmap-handoff.md) | wish list | PARKED wish list for launch and roadmap |

---

## Apps & Integrations

| Document | Status | Summary |
|---|---|---|
| [app-marketplace-and-self-hosting.md](app-marketplace-and-self-hosting.md) | design | Canonical vs self-hosted apps, app-stewards governance |
| [pathways-aqua-app-marketplace.md](pathways-aqua-app-marketplace.md) | design | Pathways workflows + Aqua attestation for app governance |
| [app-admission-audit.md](app-admission-audit.md) | audit | App admission audit against the bar |
| [group-app-integrations.md](group-app-integrations.md) | wishlist | SSO wishlist for group app integrations |
| [integration-first-templates.md](integration-first-templates.md) | design | Integration-first templates (Track B) |
| [member-scoped-app-access.md](member-scoped-app-access.md) | design | Plane, NocoDB, ERPNext, Temporal member scoping |
| [resolver-v2-and-qa.md](resolver-v2-and-qa.md) | assessment | Resolver v2 + built-in QA feasibility |
| [platform-views.md](platform-views.md) | design | Keep the types, extend the union |
| [webstudio-identity-and-group-routing.md](webstudio-identity-and-group-routing.md) | design | Webstudio identity + `{groupname}.irl.coop` dynamic routing |
| [litefarm-integration.md](litefarm-integration.md) | design | LiteFarm fork and integration |
| [restreamer-integration.md](restreamer-integration.md) | design | Restreamer app declaration and SSO gate |
| [site-plugins-and-embeds.md](site-plugins-and-embeds.md) | design | Plugins, widgets, and connectors for external platforms |
| [marketplace-template-strategy.md](marketplace-template-strategy.md) | settled | Template sources, licensing, and aesthetic |

---

## NocoDB & Data Surfaces

| Document | Status | Summary |
|---|---|---|
| [nocodb-integration.md](nocodb-integration.md) | design | Goals and per-user identity at the connection layer |
| [nocodb-one-base-per-group.md](nocodb-one-base-per-group.md) | design | Settled architecture: one base per group |
| [sharing-nocodb-interfaces.md](sharing-nocodb-interfaces.md) | design | Ship the shape, re-bind the data |
| [crm-under-fact-kinds.md](crm-under-fact-kinds.md) | design | ERPNext-native vs Twenty for CRM |
| [frappe-insights-integration.md](frappe-insights-integration.md) | intent | Frappe Insights → irl.coop integration |

---

## Matrix, Chat & Communication

| Document | Status | Summary |
|---|---|---|
| [matrix-chat-and-notifications.md](matrix-chat-and-notifications.md) | design | Matrix chat surfaces in the dashboard and event bus |
| [telephony.md](telephony.md) | design | FreeSWITCH + FusionPBX group-aware voice/PSTN |
| [telephony-trunking.md](telephony-trunking.md) | design | Trunking + per-group DIDs + cross-group caller-ID |
| [telephony-privacy.md](telephony-privacy.md) | design | Split identity, demote the switch, member-owned SFUs |
| [did-provider-comparison.md](did-provider-comparison.md) | comparison | Cost and unlimited usage comparison for DID providers |
| [did-inventory-forecasting.md](did-inventory-forecasting.md) | design | Forecast-driven number provisioning |
| [esim-and-remote-sim.md](esim-and-remote-sim.md) | question | eSIMs on virtual devices? |
| [telnyx-sim-to-pbx.md](telnyx-sim-to-pbx.md) | question | Telnyx Wireless SIM → coop PBX |
| [coop-accounts-and-phone-verification.md](coop-accounts-and-phone-verification.md) | goal | irl.coop's own accounts, verified from the coop's own number |
| [email-to-jessica-friday.md](email-to-jessica-friday.md) | draft | Stewardship + co-authoring ask |

---

## Needs, Offers & Matching

| Document | Status | Summary |
|---|---|---|
| [match-proposing.md](match-proposing.md) | design | Anyone can weave, no new role |
| [needs-offers-matching.md](needs-offers-matching.md) | design | Multi-party trade chains with expediting |
| [weavers.md](weavers.md) | design | Matching needs to offers across parties (reference) |
| [sealed-accord-weaving.md](sealed-accord-weaving.md) | design | Sealed negotiation for weaving |
| [the-weave.md](the-weave.md) | design | Dynamic Interrelated Groups |

---

## AI, Inference & Knowledge

| Document | Status | Summary |
|---|---|---|
| [byo-inference-and-group-scoped-agents.md](byo-inference-and-group-scoped-agents.md) | design | BYO inference providers & group-scoped agents |
| [provider-seams.md](provider-seams.md) | design | Decoupling the transactional layer |
| [local-ai-chat.md](local-ai-chat.md) | design | Coop's memory-stateful assistant |
| [mautic-calcom-mcp-inference.md](mautic-calcom-mcp-inference.md) | design | Mautic, Cal.com, MCP knowledgebase, client-side inference |
| [hermes-on-device-assistant.md](hermes-on-device-assistant.md) | design | Native Android shell assistant |
| [android-mini-services-client.md](android-mini-services-client.md) | design | Phone as a group node |
| [browser-management.md](browser-management.md) | design | Managed browser-automation layer for the fleet |

---

## Media, Files & Publishing

| Document | Status | Summary |
|---|---|---|
| [files-panel.md](files-panel.md) | design | Unified file viewer + virtual folder manager |
| [file-gating-and-media-rooms.md](file-gating-and-media-rooms.md) | design | Sharing, gated playback, and the side-channel |
| [published-items-as-groups.md](published-items-as-groups.md) | design | Publishing and DRM |
| [sovereign-maps-tracks.md](sovereign-maps-tracks.md) | design | OpenMapServer for sovereign maps |
| [wordpress-migration-to-wordpress-com.md](wordpress-migration-to-wordpress-com.md) | staging | Joni Schwartz site migration plan |

---

## Workflows, Pathways & Governance

| Document | Status | Summary |
|---|---|---|
| [ai-pathways-temporal-workflow-generation.md](ai-pathways-temporal-workflow-generation.md) | design | Multi-party, real-time workflow generation (chat/call/doc/form/task/dashboard) with group-local governance, audit trail under RLS, optional on-chain anchoring, and visual Workflow Studio |
| [pathways-integration.md](pathways-integration.md) | design | Pathways × irl.coop integration spec |
| [pathways.md](pathways.md) | index | Cross-reference index and imagined integrations for pathways |
| [jev-temporal-group-workflows.md](jev-temporal-group-workflows.md) | design | Decision Engine on Temporal — scope tightened |
| [tier2-entry-model.md](tier2-entry-model.md) | design | Tier-2 participation and work entry model |
| [capital-campaign-subgroup.md](capital-campaign-subgroup.md) | design | Reusable pattern for non-governor contributors |
| [scoped-availability.md](scoped-availability.md) | design | Member's time, disclosed by audience |
| [trainable_mediator_skills.md](trainable_mediator_skills.md) | framework | Trainable mediator skills for real-time cooperation |

---

## Surveys, Outreach & Narrative

| Document | Status | Summary |
|---|---|---|
| [cooperation-survey-templates.md](cooperation-survey-templates.md) | design | Survey templates for groups forming, running, repairing |
| [survey-0-is-cooperation-for-you.md](survey-0-is-cooperation-for-you.md) | draft | "Is cooperation for you?" instrument spec |
| [landing-page-claims-audit.md](landing-page-claims-audit.md) | audit | Landing page claims — what's true, what's aspirational |
| [goodbye-gouging-vo-script.md](goodbye-gouging-vo-script.md) | draft | "Goodbye Group Gouging" voiceover script |
| [fiscal-sponsorship-pitch-video.md](fiscal-sponsorship-pitch-video.md) | plan | Fiscal-sponsorship pitch video for 501(c)(3) orgs |
| [intro-video-series.md](intro-video-series.md) | proposed | Strategy for intro video series |
| [idea-to-useful.md](idea-to-useful.md) | gap analysis | The missing first flow: idea → useful tool |
| [interactive-arguments-and-the-cta.md](interactive-arguments-and-the-cta.md) | design | Interactive arguments and the call to action |
| [response-connectioning-300-movements.md](response-connectioning-300-movements.md) | draft | Response to "The 300+ Movements to a Fair Economy" |
| [chilling-effect-and-the-story.md](chilling-effect-and-the-story.md) | design | Narrative layer: the chilling effect and storytelling |

---

## Story & End-to-End Walkthroughs

| Document | Status | Summary |
|---|---|---|
| [artist-collective-end-to-end.md](artist-collective-end-to-end.md) | design | End-to-end story traced against code, used as acceptance test |
| [digest-group-shapes-event-bus-proofs-economy.md](digest-group-shapes-event-bus-proofs-economy.md) | faithful extraction | Digest of Group Shapes + Event Bus + Proofs + Economy |
| [base-indexing.md](base-indexing.md) | decision | Platform-level Base indexing approach |
| [cost-model.md](cost-model.md) | live | What this replaces, and what it costs to run |

---

## Adversary Models & Sector Fit

| Document | Status | Summary |
|---|---|---|
| [adversary-models-and-sector-fit.md](adversary-models-and-sector-fit.md) | design | Threat actors, sector fit, platform design implications |
| [coop-launch-and-roadmap-handoff.md](coop-launch-and-roadmap-handoff.md) | wish list | Parked wish list for launch and roadmap |
| [track-b-template-reference.md](track-b-template-reference.md) | audit | Thaiman-clone anatomy — licensing audit |
| [formbricks-customization-scope.md](formbricks-customization-scope.md) | scope | How deep an irl.coop skin goes in Formbricks |
| [formbricks-group-mapping.md](formbricks-group-mapping.md) | design | Formbricks ↔ irl.coop group mapping |
| [postiz-group-awareness.md](postiz-group-awareness.md) | design | Postiz group-awareness fork and sync |
| [erpnext-tenancy-notifications.md](erpnext-tenancy-notifications.md) | design | ERPNext tenancy and notifications design |
|
---

## How to Update This TOC

1. **Add a new doc:** Add a row in the appropriate section above.
2. **Change status:** Edit the status column.
3. **Regenerate automatically:** This file is hand-curated, but you can regenerate from the directory listing:
   ```bash
   ls docs/design/*.md | sort
   ```
4. **New section:** If a new topic area emerges, add a new `##` heading and table.
