import fs from "node:fs"
import path from "node:path"

// Server-only: reads the design docs from the repo root at build/dev time.
// Do not import from a client component.

export type DocStatus = "design" | "live" | "vision" | "note"

export type DesignDoc = {
  slug: string
  title: string
  category: string
  status: DocStatus
  description: string
  file: string
}

export type DesignCategory = {
  name: string
  docs: DesignDoc[]
}

const DOCS: DesignDoc[] = [
  {
    slug: "tier2-entry-model",
    title: "The Tier-2 Entry Model",
    category: "Privacy & adversaries",
    status: "design",
    description:
      "The buildable spec for the contribution ledger: record shape, the entry kinds with their signers, counter-signature authority references, the state machine, write-time invariants, and the input_root that makes the T1/T2 boundary auditable.",
    file: "tier2-entry-model.md",
  },
  {
    slug: "sharded-ledgers-and-anchors",
    title: "Sharded Ledgers & One Anchor Stream",
    category: "Privacy & adversaries",
    status: "design",
    description:
      "How ordered log entries shard across nodes: shard by group, per-group chains, per-group period roots in one federation root anchored once per period, a three-level inclusion proof, and why the anchor is what makes distributed custody safe at all.",
    file: "sharded-ledgers-and-anchors.md",
  },
  {
    slug: "money-in-and-out",
    title: "Money In and Money Out",
    category: "Working notes",
    status: "note",
    description:
      "The money map: every in-flow and out-flow with who holds it at each step and what blocks it. Complete design, zero implementation — and the first blocker is a decision (the chain choice). Includes the BYO-rails v0 shortcut and the not-a-money-transmitter invariant.",
    file: "money-in-and-out.md",
  },
  {
    slug: "idea-to-useful",
    title: "From an Idea to Something Useful",
    category: "Working notes",
    status: "note",
    description:
      "Gap analysis of the first flow: the onboarding design has a shape-picker pivot that is unbuilt, the recipes declare their tools but nothing consumes them, and the CTA asks for a commitment the FAQ says isn't needed.",
    file: "idea-to-useful.md",
  },
  {
    slug: "coop-readiness-probe",
    title: "Coop-Readiness Probe",
    category: "Working notes",
    status: "note",
    description:
      "How to meet the bug list privately before any member does: read-only passes, synthetic members, severity tiers, and the claims registry as the test plan. Built to be run, not to be impressive.",
    file: "coop-readiness-probe.md",
  },
  {
    slug: "coop-launch-and-roadmap-handoff",
    title: "Coop Launch & Roadmap Handoff (parked)",
    category: "Working notes",
    status: "note",
    description:
      "PARKED wish list: start the coop itself, hand it infrastructure control, and map roadmap development to a Plane project owned by an irl.coop group. The only item that answers the universal 'platform steward' adversary — and it depends on the non-custodial vault fix.",
    file: "coop-launch-and-roadmap-handoff.md",
  },
  {
    slug: "landing-page-claims-audit",
    title: "Landing Page Claims Audit",
    category: "Strategy & narrative",
    status: "design",
    description:
      "All 35 user-visible claims on the landing page classified against the code — what is shipped, overstated, designed, or false — with the order to fix them. Machine-readable registry in claims.data.json.",
    file: "landing-page-claims-audit.md",
  },
  {
    slug: "chilling-effect-and-the-story",
    title: "The Chilling Effect & How to Tell the Story",
    category: "Strategy & narrative",
    status: "design",
    description:
      "The thesis (the fear is information, not a confession), the self-censorship loop, the fear→mitigation→limit table, and the honest comparison against WhatsApp/Discord/Signal/SMS.",
    file: "chilling-effect-and-the-story.md",
  },
  {
    slug: "interactive-arguments-and-the-cta",
    title: "Interactive Arguments & the Call to Action",
    category: "Strategy & narrative",
    status: "design",
    description:
      "Turning the argument documents into interactive tools on the landing page: the CTA ladder, where Formbricks fits, and the claims registry that stops the page drifting ahead of the product.",
    file: "interactive-arguments-and-the-cta.md",
  },
  {
    slug: "intro-video-series",
    title: "The Intro Video Series",
    category: "Strategy & narrative",
    status: "design",
    description:
      "One master film + cuts, produced in reverse order of ambition: proof first, money second, education last — with beat sheets for V0–V11.",
    file: "intro-video-series.md",
  },
  {
    slug: "adversary-models-and-sector-fit",
    title: "Adversary Models & Sector Fit",
    category: "Privacy & adversaries",
    status: "design",
    description:
      "Who the adversaries are — internal and external — the two universal classes, group modes and footprint legibility, and what each sector can and cannot be protected from.",
    file: "adversary-models-and-sector-fit.md",
  },
  {
    slug: "federation-encryption-and-access",
    title: "Federation, Encryption & Operator Access",
    category: "Privacy & adversaries",
    status: "design",
    description:
      "What a node operator can and cannot do: envelope encryption, erasure-coded sharding, canaries, the client-integrity problem, and the one claim that survives.",
    file: "federation-encryption-and-access.md",
  },
  {
    slug: "custody-chain-and-contest-kit",
    title: "Custody Chain & the Contest Kit",
    category: "Privacy & adversaries",
    status: "design",
    description:
      "Counter-signed, hash-chained records of custody for physical goods — publicly verifiable and privately readable, so a group can prove its own account when accused.",
    file: "custody-chain-and-contest-kit.md",
  },
  {
    slug: "cost-model",
    title: "What This Costs, Side by Side",
    category: "Cost & economics",
    status: "live",
    description:
      "Generated from docs/design/cost-model.data.json: the per-seat, mid-tier and at-scale comparisons, the federation, and the storage measurement — every price sourced and dated.",
    file: "cost-model.md",
  },
  {
    slug: "event-bus-and-group-shapes",
    title: "Event Bus & Group Shapes",
    category: "Groups & governance",
    status: "design",
    description:
      "The event/notification bus, group shapes, provisioning, proofs, and the commons economy.",
    file: "event-bus-and-group-shapes.md",
  },
  {
    slug: "irl-coop-group",
    title: "The irl.coop Group",
    category: "Groups & governance",
    status: "design",
    description:
      "Safe-as-the-co-op: seats, roles, voting, and auto-provisioned Matrix channels.",
    file: "irl-coop-group.md",
  },
  {
    slug: "group-scoping",
    title: "Group Data Scoping",
    category: "Groups & governance",
    status: "design",
    description:
      "Per-group data scoping: row-level security and per-user views across shared stores.",
    file: "group-scoping.md",
  },
  {
    slug: "knowledge-aggregation",
    title: "Knowledge Aggregation",
    category: "Groups & governance",
    status: "design",
    description:
      "The world-doc of knowledge: public + connected-group + direct-grant knowledge areas behind one aggregated query — three visibility tiers (public/group/private), and the RAG-side + provisioning pieces.",
    file: "knowledge-aggregation.md",
  },
  {
    slug: "matrix-chat-and-notifications",
    title: "Matrix Chat & Notifications",
    category: "Groups & governance",
    status: "live",
    description:
      "Per-room Element embeds and the Matrix appservice feeding the event bus — no native client, no key escrow, no homeserver changes.",
    file: "matrix-chat-and-notifications.md",
  },
  {
    slug: "account-and-key-model",
    title: "Accounts & Keys",
    category: "Identity & accounts",
    status: "design",
    description: "Safe-as-account, passkey onboarding, key custody, and recovery.",
    file: "account-and-key-model.md",
  },
  {
    slug: "delegation-and-session-keys",
    title: "Delegation, Session Keys & Temporal",
    category: "Identity & accounts",
    status: "design",
    description:
      "ERC-4337/7715 delegation: scoped revocable session keys for Temporal automation and agents — no bypass, user secrets only.",
    file: "delegation-and-session-keys.md",
  },
  {
    slug: "group-secret-vault",
    title: "Group Secret Vault",
    category: "Identity & accounts",
    status: "design",
    description:
      "The threshold-encrypted, Safe-anchored store for per-group env secrets and salt backups — quorum-gated, member-held shares.",
    file: "group-secret-vault.md",
  },
  {
    slug: "onboarding-flow",
    title: "Onboarding Flow",
    category: "Identity & accounts",
    status: "design",
    description:
      "First-run onboarding: what a member needs to know and set up — the flow, voice, and visual system.",
    file: "onboarding-flow.md",
  },
  {
    slug: "private-treasury-guards-ledgers",
    title: "Private ZK Treasury, Guards & Ledgers",
    category: "Economy & treasury",
    status: "design",
    description:
      "The shielded treasury: notes, commitments, nullifiers, guards, and the ledger taxonomy.",
    file: "private-treasury-guards-ledgers.md",
  },
  {
    slug: "published-items-as-groups",
    title: "Published Items as Groups",
    category: "Economy & treasury",
    status: "design",
    description:
      "Every published work is a group: an encrypted file with minted session/viewing keys (rent, lend, re-lend, sell), owner/contributor/funder tiers, supply control, and a project-to-group ceremony.",
    file: "published-items-as-groups.md",
  },
  {
    slug: "regenerative-vision-note",
    title: "Regenerative Score (Vision)",
    category: "Economy & treasury",
    status: "vision",
    description:
      "The regenerative score as a zero-knowledge metric — the founding vision.",
    file: "regenerative-vision-note.md",
  },
  {
    slug: "needs-offers-matching",
    title: "Needs & Offers Matching",
    category: "Economy & treasury",
    status: "design",
    description:
      "Multi-party trade chains: post needs/offers, discover A→B→C→…→A cycles, and track each leg through a declared/actual/drift reconciler to settlement and arbitration.",
    file: "needs-offers-matching.md",
  },
  {
    slug: "match-proposing",
    title: "Match Proposing — anyone can weave",
    category: "Economy & treasury",
    status: "design",
    description:
      "Proposing a match is an action, not a role: any member may propose a matched-by edge, gated by a per-proposal bond and a decaying match-quality zk-badge — the trust floor and arbitration path for weaving.",
    file: "match-proposing.md",
  },
  {
    slug: "world-doc-and-contacts",
    title: "World-Doc & Contacts",
    category: "Dashboard & world-doc",
    status: "design",
    description:
      "Seats and contacts: the universal membership primitive and privacy tiers.",
    file: "world-doc-and-contacts.md",
  },
  {
    slug: "world-doc-virtual-workspace",
    title: "World-Doc Virtual Workspace",
    category: "Dashboard & world-doc",
    status: "design",
    description: "The world-doc as each member's personal projection of the co-op.",
    file: "world-doc-virtual-workspace.md",
  },
  {
    slug: "files-panel",
    title: "Files Panel",
    category: "Apps & files",
    status: "live",
    description: "Files and folders: storage, shares, and the virtual-folder registry.",
    file: "files-panel.md",
  },
  {
    slug: "local-ai-chat",
    title: "Local AI Chat",
    category: "Apps & files",
    status: "design",
    description:
      "The coop's memory-stateful assistant: a harness of memory → retrieval → generation → memory, with an explicit per-member private memory, Chrome's on-device Prompt API for generation, and grounded cited answers.",
    file: "local-ai-chat.md",
  },
  {
    slug: "infra-management-monitoring",
    title: "Infrastructure Management & Monitoring",
    category: "Infrastructure",
    status: "live",
    description: "How the stack is declared, brought up, tracked, and watched.",
    file: "infra-management-monitoring.md",
  },
  {
    slug: "browser-management",
    title: "Browser Management",
    category: "Infrastructure",
    status: "live",
    description: "Fleet browser automation on Temporal — the Playwright runner fleet.",
    file: "browser-management.md",
  },
  {
    slug: "android-mini-services-client",
    title: "Android Mini-Services Client",
    category: "Infrastructure",
    status: "design",
    description:
      "The phone as a group node: SMS relay, offline files, a data shard, and offline maps over a Tailscale mesh — infrastructure held by members, not VPSes.",
    file: "android-mini-services-client.md",
  },
  {
    slug: "mautic-calcom-mcp-inference",
    title: "Stack Additions — Mautic, Cal.com, MCP, Edge Inference",
    category: "Infrastructure",
    status: "design",
    description:
      "Intent: Mautic (marketing automation) + Cal.com (scheduling/booking) apps, an MCP server + knowledgebase as the scoped AI gateway, and client-side inference calling the MCP tools — inference at the edge, acting through the coop.",
    file: "mautic-calcom-mcp-inference.md",
  },
  {
    slug: "handoff-2026-08-13",
    title: "Session Handoff (2026-08-13)",
    category: "Working notes",
    status: "note",
    description: "Working session handoff: state, blockers, and pending decisions.",
    file: "handoff-2026-08-13.md",
  },
  {
    slug: "coop-work-signup-checkoff",
    title: "Cooperative work — signup, printable task sheet, check-off",
    category: "Groups & governance",
    status: "design",
    description:
      "Sign up for concrete work items, print a one-page sheet for the clipboard, and check items off — each check-off emits the contribution event the Tier-2 ledger consumes.",
    file: "coop-work-signup-checkoff.md",
  },
  {
    slug: "zk-membership-graph-proofs",
    title: "ZK-Metric & Membership Proofs",
    category: "Privacy & adversaries",
    status: "design",
    description:
      "Provable-but-private membership and metrics: prove you belong, or that you showed up, without revealing which group or how much.",
    file: "zk-membership-graph-proofs.md",
  },
  {
    slug: "group-shape-scenarios",
    title: "Group-Shape Scenario Notes",
    category: "Groups & governance",
    status: "note",
    description:
      "Worked examples of the group-shape axes across real kinds of group. Companion to the group-model design.",
    file: "group-shape-scenarios.md",
  },
  {
    slug: "group-shapes-event-bus-proofs-economy",
    title: "Digest — Group Shapes, Event Bus, Proofs & Economy",
    category: "Groups & governance",
    status: "note",
    description:
      "A consolidated digest of the group model: shapes, the event/notification bus, proofs, and the commons economy.",
    file: "digest-group-shapes-event-bus-proofs-economy.md",
  },
  {
    slug: "track-b-template-reference",
    title: "Track B template reference",
    category: "Apps & files",
    status: "design",
    description:
      "The anatomy of a Webstudio template (thaiman-clone) as the reference for integration-first templates.",
    file: "track-b-template-reference.md",
  },
  {
    slug: "integration-first-templates",
    title: "Integration-first templates (Track B)",
    category: "Groups & governance",
    status: "design",
    description:
      "Templates that wire a group's apps together, not just a page: the shape a group starts from.",
    file: "integration-first-templates.md",
  },
  {
    slug: "marketplace-template-strategy",
    title: "Marketplace template strategy",
    category: "Groups & governance",
    status: "design",
    description:
      "Where templates come from, under what licensing, and how they reach a group — the settled licensing gate.",
    file: "marketplace-template-strategy.md",
  },
  {
    slug: "group-app-integrations",
    title: "Group app integrations (SSO wishlist)",
    category: "Apps & files",
    status: "note",
    description:
      "The SSO/app-integration wishlist recorded per app.",
    file: "group-app-integrations.md",
  },
  {
    slug: "weavers",
    title: "Weavers — matching needs to offers across parties",
    category: "Groups & governance",
    status: "note",
    description:
      "Matching needs to offers across parties. Superseded and kept for reference.",
    file: "weavers.md",
  },
  {
    slug: "cooperation-survey-templates",
    title: "Cooperation Starter Pack — survey templates",
    category: "Strategy & narrative",
    status: "design",
    description:
      "Survey templates a group can run to find out where its own cooperation is thin.",
    file: "cooperation-survey-templates.md",
  },
  {
    slug: "survey-0-is-cooperation-for-you",
    title: "Survey 0 — \"Is cooperation for you?\"",
    category: "Strategy & narrative",
    status: "design",
    description:
      "The instrument specification for the first cooperation survey: the intake that measures where a group actually stands.",
    file: "survey-0-is-cooperation-for-you.md",
  },
  {
    slug: "formbricks-group-mapping",
    title: "Formbricks ↔ irl.coop group mapping",
    category: "Apps & files",
    status: "design",
    description:
      "How a Formbricks workspace maps to an irl.coop group, and what that means for who sees a response.",
    file: "formbricks-group-mapping.md",
  },
  {
    slug: "formbricks-customization-scope",
    title: "Formbricks customization scope",
    category: "Apps & files",
    status: "design",
    description:
      "How deep an irl.coop fork of Formbricks should go — a scope decision, not a build log.",
    file: "formbricks-customization-scope.md",
  },
  {
    slug: "postiz-group-awareness",
    title: "Postiz Group-Awareness",
    category: "Apps & files",
    status: "live",
    description:
      "The Postiz fork and sync workflow that projects opted-in groups into Postiz orgs and membership. Built and verified.",
    file: "postiz-group-awareness.md",
  },
  {
    slug: "litefarm-integration",
    title: "LiteFarm integration (irl.coop)",
    category: "Apps & files",
    status: "design",
    description:
      "The farm leg: LiteFarm tasks, fields and crops as the source for field work — the domain data already exists there.",
    file: "litefarm-integration.md",
  },
  {
    slug: "erpnext-tenancy-notifications",
    title: "ERPNext Tenancy & Notifications",
    category: "Apps & files",
    status: "design",
    description:
      "Multi-tenant ERPNext for the coop: how tenancy is scoped and how its notifications reach members.",
    file: "erpnext-tenancy-notifications.md",
  },
  {
    slug: "sovereign-maps-tracks",
    title: "Sovereign maps & tracks (OpenMapServer)",
    category: "Apps & files",
    status: "design",
    description:
      "Tracks, markers and waypoints on the coop's own basemap — with the precise/coarse split that keeps a map queryable without publishing exactly where someone was.",
    file: "sovereign-maps-tracks.md",
  },
  {
    slug: "webstudio-identity-and-group-routing",
    title: "Webstudio identity & group routing",
    category: "Apps & files",
    status: "design",
    description:
      "How a published site knows which group it belongs to and resolves {groupname}.irl.coop. Routing implemented; identity in progress.",
    file: "webstudio-identity-and-group-routing.md",
  },
  {
    slug: "telephony",
    title: "Telephony (FreeSWITCH + FusionPBX)",
    category: "Infrastructure",
    status: "design",
    description:
      "The coop's softswitch: extensions, ring groups, queues, IVR and voicemail, per group and per member.",
    file: "telephony.md",
  },
  {
    slug: "telephony-trunking",
    title: "Telephony trunking & group caller-ID",
    category: "Infrastructure",
    status: "design",
    description:
      "The Telnyx trunk and per-group DIDs, and how caller-ID is chosen on the way out.",
    file: "telephony-trunking.md",
  },
  {
    slug: "telephony-privacy",
    title: "Telephony privacy — split identity",
    category: "Privacy & adversaries",
    status: "design",
    description:
      "Splitting identity at the switch, and demoting the softswitch so it is not the trust anchor for a call.",
    file: "telephony-privacy.md",
  },
  {
    slug: "did-inventory-forecasting",
    title: "DID inventory — forecast-driven number provisioning",
    category: "Infrastructure",
    status: "design",
    description:
      "A model for how many numbers to hold and when to provision them, rather than buying one per group on demand.",
    file: "did-inventory-forecasting.md",
  },
  {
    slug: "resolver-v2-and-qa",
    title: "Resolver v2 & built-in QA",
    category: "Identity & accounts",
    status: "design",
    description:
      "The second take on resolving a person across apps, plus the QA that keeps it honest.",
    file: "resolver-v2-and-qa.md",
  },
  {
    slug: "frappe-insights-integration",
    title: "Frappe Insights — opening the stack and/or ERPNext",
    category: "Apps & files",
    status: "design",
    description:
      "Intent (not built): run Frappe Insights on the existing ERPNext bench, report over the coop ledger, and the RLS hazard that decides how it may connect.",
    file: "frappe-insights-integration.md",
  },
  {
    slug: "coop-accounts-and-phone-verification",
    title: "The coop's own accounts, verified from the coop's own number",
    category: "Identity & accounts",
    status: "design",
    description:
      "Goal (not built): the coop owns a DID and receives its verification texts; the signup itself stays a human step, and why automating it would burn the number.",
    file: "coop-accounts-and-phone-verification.md",
  },
]

function resolveDesignDir(): string | null {
  const candidates = [
    path.resolve(process.cwd(), "docs/design"),
    path.resolve(process.cwd(), "../../../docs/design"),
  {
    slug: "did-provider-comparison",
    title: "DID + SMS providers, compared for cost and \"unlimited\"",
    category: "Infrastructure",
    status: "design",
    description:
      "List rates for Telnyx / Twilio / VoIP.ms / Callcentric / prepaid SIM, sourced and dated — and the finding that decides the choice: a wholesale DID cannot verify an Instagram or YouTube account, because the platform runs a line-type lookup before it sends anything.",
    file: "did-provider-comparison.md",
  },
  {
    slug: "esim-and-remote-sim",
    title: "eSIM and remote SIM: can numbers live on virtual devices?",
    category: "Infrastructure",
    status: "design",
    description:
      "The numbers can be virtual and the radio cannot. lpac manages eUICC profiles from Linux over a modem's AT interface; osmo-remsim separates a SIM from its modem — which is also the exact signature carriers detect, so the legitimate route is a REGISTERED gateway on an M2M plan.",
    file: "esim-and-remote-sim.md",
  },
  {
    slug: "telnyx-sim-to-pbx",
    title: "Telnyx Wireless SIM → the coop's PBX",
    category: "Infrastructure",
    status: "design",
    description:
      "The SIM and the SIP trunk are the same vendor, so the SIM's number can terminate in FreeSWITCH like any DID — but the SMS half and the line type of the SIM's number are the open questions, and Telnyx's own Number Lookup calls its numbers VoIP.",
    file: "telnyx-sim-to-pbx.md",
  },
  {
    slug: "group-account-resource",
    title: "The account resource — group-held credentials, and the will that outlives a person",
    category: "Identity & accounts",
    status: "design",
    description:
      "One primitive for group-held accounts and personal succession: the durable identity is not 'a group' but 'a thing that outlives any single person', and a personal group is already modeled. Anchor status, platform role-mapping, and the honest split between what the coop enforces (intent) and what the platform enforces (transfer).",
    file: "group-account-resource.md",
  },
  ]
  return candidates.find((c) => fs.existsSync(c)) ?? null
}

export function getDesignDocs(): DesignDoc[] {
  return DOCS
}

export function getCategories(): DesignCategory[] {
  const byCategory = new Map<string, DesignDoc[]>()
  for (const doc of DOCS) {
    const list = byCategory.get(doc.category) ?? []
    list.push(doc)
    byCategory.set(doc.category, list)
  }
  return [...byCategory.entries()].map(([name, docs]) => ({ name, docs }))
}

export function getDesignDoc(slug: string): DesignDoc | undefined {
  return DOCS.find((d) => d.slug === slug)
}

export function readDesignDoc(slug: string): string | null {
  const doc = getDesignDoc(slug)
  const dir = resolveDesignDir()
  if (!doc || !dir) return null
  const file = path.join(dir, doc.file)
  if (!fs.existsSync(file)) return null
  return fs.readFileSync(file, "utf8")
}
