import fs from "node:fs"
import path from "node:path"

// Server-only: the design-docs registry lives in docs/design/design-docs.json
// and is read from disk at request time — NOT a compile-time constant. Adding a
// doc is a JSON edit with no server restart (the dev server never has to
// recompile this module). Do not import from a client component.

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

function resolveDesignDir(): string | null {
  const candidates = [
    path.resolve(process.cwd(), "docs/design"),
    path.resolve(process.cwd(), "../../../docs/design"),
  ]
  return candidates.find((c) => fs.existsSync(c)) ?? null
}

function loadDocs(): DesignDoc[] {
  const dir = resolveDesignDir()
  if (!dir) return []
  const file = path.join(dir, "design-docs.json")
  if (!fs.existsSync(file)) return []
  try {
    return JSON.parse(fs.readFileSync(file, "utf8")) as DesignDoc[]
  } catch {
    return []
  }
}

export function getDesignDocs(): DesignDoc[] {
  return loadDocs()
}

export function getCategories(): DesignCategory[] {
  const byCategory = new Map<string, DesignDoc[]>()
  for (const doc of loadDocs()) {
    const list = byCategory.get(doc.category) ?? []
    list.push(doc)
    byCategory.set(doc.category, list)
  }
  return [...byCategory.entries()].map(([name, docs]) => ({ name, docs }))
}

export function getDesignDoc(slug: string): DesignDoc | undefined {
  return loadDocs().find((d) => d.slug === slug)
}

export function readDesignDoc(slug: string): string | null {
  const doc = getDesignDoc(slug)
  const dir = resolveDesignDir()
  if (!doc || !dir) return null
  const file = path.join(dir, doc.file)
  if (!fs.existsSync(file)) return null
  return fs.readFileSync(file, "utf8")
}
