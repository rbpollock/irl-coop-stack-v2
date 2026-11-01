import { existsSync } from "node:fs"
import { readFile } from "node:fs/promises"
import path from "node:path"

import { getDesignDoc } from "@/lib/design-docs"

/**
 * Serve a raw design-doc artifact by its RAG `document_name` (the file name
 * with its extension), e.g. `irl-coop-architecture.html`. This is the target of
 * a docs-search result when the document is NOT a markdown file registered in
 * design-docs.json — the markdown renderer at /design/[slug] only knows .md
 * docs, so an .html (or other) doc would otherwise 404.
 *
 * Routing precedent: /design/[slug] renders *markdown*; /design/raw/[slug]
 * serves the raw markdown of a *registered* doc. This route stands apart
 * because its slug is a file name with an extension and it must render actual
 * files, not json-registered docs.
 */

function contentTypeFor(file: string): string {
  const ext = path.extname(file).toLowerCase()
  switch (ext) {
    case ".html":
    case ".htm":
      return "text/html; charset=utf-8"
    case ".md":
    case ".markdown":
      return "text/markdown; charset=utf-8"
    case ".json":
      return "application/json; charset=utf-8"
    case ".txt":
      return "text/plain; charset=utf-8"
    case ".csv":
      return "text/csv; charset=utf-8"
    case ".png":
      return "image/png"
    case ".jpg":
    case ".jpeg":
      return "image/jpeg"
    case ".gif":
      return "image/gif"
    case ".svg":
      return "image/svg+xml"
    case ".pdf":
      return "application/pdf"
    case ".mp4":
      return "video/mp4"
    default:
      return "application/octet-stream"
  }
}

function resolveDir(): string | null {
  const candidates = [
    path.resolve(process.cwd(), "docs/design"),
    path.resolve(process.cwd(), "../../../docs/design"),
  ]
  return candidates.find((c) => existsSync(c)) ?? null
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const p = await params
  const raw = Array.isArray(p?.path) ? p.path.join("/") : (p?.path ?? "")
  if (!raw) return new Response("Not found", { status: 404 })
  // Guard against path traversal: only the basename is used to look up the file.
  const base = path.basename(raw)
  const dir = resolveDir()
  if (!dir || !base || base === "." || base === "..") {
    return new Response("Not found", { status: 404 })
  }

  // A registered markdown design doc renders best through the existing page —
  // redirect so the /design/[slug] renderer (sticky nav + anchors) is used.
  const mdSlug = base.replace(/\.md$/i, "")
  if (mdSlug !== base) {
    const doc = getDesignDoc(mdSlug)
    if (doc) {
      return Response.redirect(
        new URL(`/design/${doc.slug}`, _request.url),
        307
      )
    }
  }

  // Otherwise serve the raw file with a content type matching its extension.
  const file = path.join(dir, base)
  if (!existsSync(file)) return new Response("Not found", { status: 404 })
  const body = await readFile(file)
  return new Response(new Uint8Array(body), {
    headers: { "Content-Type": contentTypeFor(base) },
  })
}
