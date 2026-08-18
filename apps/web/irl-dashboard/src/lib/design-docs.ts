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
    slug: "private-treasury-guards-ledgers",
    title: "Private ZK Treasury, Guards & Ledgers",
    category: "Economy & treasury",
    status: "design",
    description:
      "The shielded treasury: notes, commitments, nullifiers, guards, and the ledger taxonomy.",
    file: "private-treasury-guards-ledgers.md",
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
    slug: "handoff-2026-08-13",
    title: "Session Handoff (2026-08-13)",
    category: "Working notes",
    status: "note",
    description: "Working session handoff: state, blockers, and pending decisions.",
    file: "handoff-2026-08-13.md",
  },
]

function resolveDesignDir(): string | null {
  const candidates = [
    path.resolve(process.cwd(), "docs/design"),
    path.resolve(process.cwd(), "../../../docs/design"),
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
