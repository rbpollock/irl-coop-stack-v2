"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useSession } from "next-auth/react"
import {
  ExternalLink,
  File as FileIcon,
  FilePlus2,
  FileSpreadsheet,
  FileText,
  FileType2,
  Folder,
  FolderOpen,
  FolderPlus,
  Presentation,
  RefreshCw,
  Share2,
  X,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

// Docs — MinIO-backed documents edited in the embedded OnlyOffice editor.
// Auth is the coop JWT (same session as everything else); the editor config
// is minted + JWT-signed by coop-api (onlyoffice verifies the signature).
const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"
const ONLYOFFICE_PUBLIC_URL =
  process.env.NEXT_PUBLIC_ONLYOFFICE_URL ?? "https://office.irl.coop"

type DocMeta = { name: string; size: number; modified: string }

// Virtual folders — pointers only; the objects stay in the source buckets.
type Folder = {
  id: string
  name: string
  parent: string | null
  createdAt: string
}
type FolderMember = { folderId: string; source: string; key: string }
type FilesListing = { folders: Folder[]; members: FolderMember[] }

type EditorConfig = {
  type: string
  documentType: string
  document: { title: string; fileType: string; key: string }
  editorConfig: { user: { name: string }; callbackUrl: string }
  token: string
}

declare global {
  interface Window {
    DocsAPI?: {
      DocEditor: new (id: string, config: Record<string, unknown>) => unknown
    }
  }
}

const TYPE_ICON: Record<string, typeof FileText> = {
  docx: FileText,
  odt: FileText,
  txt: FileText,
  xlsx: FileSpreadsheet,
  ods: FileSpreadsheet,
  csv: FileSpreadsheet,
  pptx: Presentation,
  odp: Presentation,
}

function docIcon(name: string) {
  const ext = name.split(".").pop()?.toLowerCase() ?? ""
  return TYPE_ICON[ext] ?? FileIcon
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fmtWhen(iso: string): string {
  if (!iso) return ""
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  if (diff < 60_000) return "just now"
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return d.toLocaleDateString()
}

export default function DocsPage() {
  const { data: session } = useSession()
  const [docs, setDocs] = useState<DocMeta[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [creating, setCreating] = useState<string | null>(null)
  const [newMenu, setNewMenu] = useState(false)
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [folders, setFolders] = useState<Folder[]>([])
  const [members, setMembers] = useState<FolderMember[]>([])
  const [newFolderOpen, setNewFolderOpen] = useState(false)
  const [newFolderName, setNewFolderName] = useState("")
  const [moveMenu, setMoveMenu] = useState<string | null>(null)
  const [folderBusy, setFolderBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const editorHostRef = useRef<HTMLDivElement>(null)
  const editorRef = useRef<unknown>(null)

  const token = session?.accessToken as string | undefined

  const refresh = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${COOP_API_URL}/api/v1/docs`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error(`list failed (${res.status})`)
      const body = (await res.json()) as { documents: DocMeta[] }
      setDocs(body.documents)
      const filesRes = await fetch(`${COOP_API_URL}/api/v1/files`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (filesRes.ok) {
        const files = (await filesRes.json()) as FilesListing
        setFolders(files.folders)
        setMembers(files.members)
      }
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    refresh()
  }, [refresh])

  async function createDoc(type: "docx" | "xlsx" | "pptx") {
    if (!token) return
    setCreating(type)
    setNewMenu(false)
    setError(null)
    try {
      const res = await fetch(`${COOP_API_URL}/api/v1/docs/new`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ type }),
      })
      if (!res.ok) throw new Error(`create failed (${res.status})`)
      const { name } = (await res.json()) as { name: string }
      await refresh()
      setEditing(name) // open the editor on the fresh blank file
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCreating(null)
    }
  }

  async function shareDoc(name: string) {
    if (!token) return
    setError(null)
    try {
      const res = await fetch(
        `${COOP_API_URL}/api/v1/files/docs/${encodeURIComponent(name)}/share`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      if (!res.ok) throw new Error(`share failed (${res.status})`)
      const { url } = (await res.json()) as { url: string }
      setShareUrl(url)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function createFolder() {
    if (!token || !newFolderName.trim()) return
    setFolderBusy(true)
    setError(null)
    try {
      const res = await fetch(`${COOP_API_URL}/api/v1/files/folders`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ name: newFolderName.trim() }),
      })
      if (!res.ok) throw new Error(`folder create failed (${res.status})`)
      setNewFolderName("")
      setNewFolderOpen(false)
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setFolderBusy(false)
    }
  }

  // Virtual move: a pointer into the folder — the object stays in MinIO.
  async function addToFolder(docName: string, folderId: string) {
    if (!token) return
    setMoveMenu(null)
    setError(null)
    try {
      const res = await fetch(
        `${COOP_API_URL}/api/v1/files/folders/${folderId}/members`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ source: "docs", key: docName }),
        }
      )
      if (!res.ok) throw new Error(`move failed (${res.status})`)
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function removeFromFolder(folderId: string, key: string) {
    if (!token) return
    setError(null)
    try {
      const res = await fetch(
        `${COOP_API_URL}/api/v1/files/folders/${folderId}/members?key=${encodeURIComponent(key)}&source=docs`,
        { method: "DELETE", headers: { Authorization: `Bearer ${token}` } }
      )
      if (!res.ok) throw new Error(`remove failed (${res.status})`)
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function upload(files: FileList | null) {
    if (!token || !files || files.length === 0) return
    setUploading(true)
    setError(null)
    try {
      for (const file of Array.from(files)) {
        const res = await fetch(
          `${COOP_API_URL}/api/v1/docs/${encodeURIComponent(file.name)}`,
          {
            method: "PUT",
            headers: { Authorization: `Bearer ${token}` },
            body: file,
          }
        )
        if (!res.ok)
          throw new Error(`upload ${file.name} failed (${res.status})`)
      }
      await refresh()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  // Destroy the previous editor instance before loading a new document —
  // OnlyOffice's DocsAPI keeps the old iframe alive otherwise.
  useEffect(() => {
    if (editing === null) return
    if (!token) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(
          `${COOP_API_URL}/api/v1/docs/${encodeURIComponent(editing)}/editor`,
          { headers: { Authorization: `Bearer ${token}` } }
        )
        if (!res.ok) throw new Error(`editor config failed (${res.status})`)
        const cfg = (await res.json()) as EditorConfig
        if (cancelled) return
        // Load the OnlyOffice API script lazily, then mount the editor.
        if (!window.DocsAPI) {
          await new Promise<void>((resolve, reject) => {
            const s = document.createElement("script")
            s.src = `${ONLYOFFICE_PUBLIC_URL}/web-apps/apps/api/documents/api.js`
            s.onload = () => resolve()
            s.onerror = () => reject(new Error("failed to load editor api"))
            document.head.appendChild(s)
          })
        }
        if (cancelled) return
        if (!window.DocsAPI || !editorHostRef.current) return
        editorRef.current = new window.DocsAPI.DocEditor(
          editorHostRef.current.id,
          {
            document: cfg.document,
            documentType: cfg.documentType,
            editorConfig: cfg.editorConfig,
            height: "100%",
            type: cfg.type,
            token: cfg.token,
            width: "100%",
          }
        )
      } catch (err) {
        if (!cancelled) setError((err as Error).message)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [editing, token])

  function backToList() {
    try {
      ;(
        editorRef.current as { destroyEditor?: () => void } | null
      )?.destroyEditor?.()
    } catch {
      /* the iframe may already be gone */
    }
    editorRef.current = null
    setEditing(null)
    setShareUrl(null)
  }

  if (!session) return null

  const recent = docs.slice(0, 5)
  const rest = docs.slice(5)

  function DocRow({ doc, showShare }: { doc: DocMeta; showShare?: boolean }) {
    const Icon = docIcon(doc.name)
    return (
      <li
        key={doc.name}
        className="group flex items-center gap-3 rounded-lg border bg-background px-4 py-2.5 text-sm hover:bg-accent"
      >
        <button
          className="flex min-w-0 flex-1 items-center gap-3 text-left"
          onClick={() => setEditing(doc.name)}
        >
          <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="truncate font-medium">{doc.name}</span>
        </button>
        <span className="hidden shrink-0 text-xs text-muted-foreground sm:block">
          {fmtSize(doc.size)} · {fmtWhen(doc.modified)}
        </span>
        {showShare && (
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
            onClick={() => shareDoc(doc.name)}
            title="Share"
          >
            <Share2 className="h-3.5 w-3.5" />
          </Button>
        )}
        {folders.length > 0 && (
          <div className="relative">
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
              onClick={() =>
                setMoveMenu(moveMenu === doc.name ? null : doc.name)
              }
              title="Move to folder"
            >
              <FolderPlus className="h-3.5 w-3.5" />
            </Button>
            {moveMenu === doc.name && (
              <div className="absolute right-0 top-full z-20 mt-1 w-44 rounded-lg border bg-background p-1 shadow-md">
                {folders.map((f) => (
                  <button
                    key={f.id}
                    className="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-xs hover:bg-accent"
                    onClick={() => addToFolder(doc.name, f.id)}
                  >
                    <Folder className="h-3.5 w-3.5 text-amber-600" />
                    <span className="truncate">{f.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </li>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b bg-background px-4 py-2.5">
        <div>
          <h1 className="text-sm font-semibold">Documents</h1>
          <p className="text-xs text-muted-foreground">
            OnlyOffice on the coop — edited inline, stored in MinIO, one
            identity
          </p>
        </div>
        {editing === null ? (
          <div className="flex items-center gap-2">
            <div className="relative">
              <Button
                size="sm"
                onClick={() => setNewMenu((v) => !v)}
                disabled={creating !== null}
              >
                <FilePlus2 className="me-2 h-4 w-4" />
                {creating ? "Creating…" : "New"}
              </Button>
              {newMenu && (
                <div className="absolute right-0 top-full z-20 mt-1 w-48 rounded-lg border bg-background p-1 shadow-md">
                  <button
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
                    onClick={() => createDoc("docx")}
                  >
                    <FileText className="h-4 w-4 text-sky-600" /> Document
                  </button>
                  <button
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
                    onClick={() => createDoc("xlsx")}
                  >
                    <FileSpreadsheet className="h-4 w-4 text-emerald-600" />{" "}
                    Spreadsheet
                  </button>
                  <button
                    className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
                    onClick={() => createDoc("pptx")}
                  >
                    <Presentation className="h-4 w-4 text-orange-600" />{" "}
                    Presentation
                  </button>
                </div>
              )}
            </div>
            <input
              ref={fileRef}
              type="file"
              multiple
              accept=".docx,.xlsx,.pptx,.odt,.ods,.csv,.txt"
              className="hidden"
              onChange={(e) => upload(e.target.files)}
            />
            <Button
              size="sm"
              variant="outline"
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
            >
              <FileType2 className="me-2 h-4 w-4" />
              {uploading ? "Uploading…" : "Upload"}
            </Button>
            <Button size="sm" variant="ghost" onClick={refresh}>
              <RefreshCw className="me-2 h-4 w-4" />
              Refresh
            </Button>
            <Button asChild size="sm" variant="ghost">
              <a href={ONLYOFFICE_PUBLIC_URL} target="_blank" rel="noreferrer">
                <ExternalLink className="me-2 h-4 w-4" />
                OnlyOffice
              </a>
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="outline" onClick={backToList}>
            ← Back to documents
          </Button>
        )}
      </div>

      {error && (
        <div className="border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-xs text-destructive">
          {error}
        </div>
      )}
      {shareUrl && (
        <div className="flex items-center gap-2 border-b bg-muted px-4 py-2 text-xs">
          <Share2 className="h-3.5 w-3.5 shrink-0" />
          <Input readOnly value={shareUrl} className="h-7 text-xs" />
          <Button
            size="sm"
            variant="outline"
            className="h-7 shrink-0"
            onClick={() => {
              navigator.clipboard?.writeText(shareUrl).catch(() => {})
              setShareUrl(null)
            }}
          >
            Copy
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 shrink-0"
            onClick={() => setShareUrl(null)}
          >
            Close
          </Button>
        </div>
      )}

      {editing === null ? (
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-6">
              <section>
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    My folders
                  </h2>
                  {!newFolderOpen && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 text-xs"
                      onClick={() => setNewFolderOpen(true)}
                      disabled={folderBusy}
                    >
                      <FolderPlus className="me-1 h-3.5 w-3.5" /> New folder
                    </Button>
                  )}
                </div>
                {newFolderOpen && (
                  <form
                    className="mb-2 flex items-center gap-2"
                    onSubmit={(e) => {
                      e.preventDefault()
                      createFolder()
                    }}
                  >
                    <Input
                      autoFocus
                      value={newFolderName}
                      onChange={(e) => setNewFolderName(e.target.value)}
                      placeholder="Folder name"
                      className="h-8 text-sm"
                    />
                    <Button
                      size="sm"
                      type="submit"
                      disabled={folderBusy || !newFolderName.trim()}
                    >
                      Create
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      type="button"
                      onClick={() => {
                        setNewFolderOpen(false)
                        setNewFolderName("")
                      }}
                    >
                      Cancel
                    </Button>
                  </form>
                )}
                {folders.length === 0 ? (
                  <p className="mb-4 text-xs text-muted-foreground">
                    Folders are virtual — drop documents into them without
                    moving the stored files.
                  </p>
                ) : (
                  <div className="mb-4 grid gap-2 sm:grid-cols-2">
                    {folders.map((f) => {
                      const fMembers = members.filter(
                        (m) => m.folderId === f.id
                      )
                      return (
                        <div
                          key={f.id}
                          className="rounded-lg border bg-background p-3"
                        >
                          <div className="flex items-center gap-2">
                            <Folder className="h-4 w-4 shrink-0 text-amber-600" />
                            <span className="truncate text-sm font-medium">
                              {f.name}
                            </span>
                            <span className="ml-auto text-xs text-muted-foreground">
                              {fMembers.length}
                            </span>
                          </div>
                          {fMembers.length === 0 ? (
                            <p className="mt-2 text-xs text-muted-foreground">
                              Empty — hover a document and use the folder
                              button.
                            </p>
                          ) : (
                            <ul className="mt-2 flex flex-col gap-1">
                              {fMembers.map((m) => (
                                <li
                                  key={`${f.id}/${m.source}/${m.key}`}
                                  className="group flex items-center gap-2 rounded px-1 py-0.5 text-xs hover:bg-accent"
                                >
                                  {m.source === "docs" ? (
                                    <button
                                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                                      onClick={() => setEditing(m.key)}
                                      title="Open in OnlyOffice"
                                    >
                                      <FileIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                      <span className="truncate">{m.key}</span>
                                    </button>
                                  ) : (
                                    <span className="flex min-w-0 flex-1 items-center gap-2">
                                      <FileIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                                      <span className="truncate">{m.key}</span>
                                      <span className="text-[10px] text-muted-foreground">
                                        {m.source}
                                      </span>
                                    </span>
                                  )}
                                  <button
                                    className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
                                    title="Remove from folder"
                                    onClick={() =>
                                      removeFromFolder(f.id, m.key)
                                    }
                                  >
                                    <X className="h-3 w-3 text-muted-foreground hover:text-destructive" />
                                  </button>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}
              </section>

              {docs.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-16 text-center">
                  <FolderOpen className="h-10 w-10 text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">
                    No documents yet — create a blank one or upload a .docx,
                    .xlsx or .pptx.
                  </p>
                  <div className="flex items-center gap-2">
                    <Button size="sm" onClick={() => createDoc("docx")}>
                      <FilePlus2 className="me-2 h-4 w-4" /> New document
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => fileRef.current?.click()}
                    >
                      Upload
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  {recent.length > 0 && (
                    <section>
                      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Recent
                      </h2>
                      <ul className="flex flex-col gap-1.5">
                        {recent.map((doc) => (
                          <DocRow key={doc.name} doc={doc} showShare />
                        ))}
                      </ul>
                    </section>
                  )}
                  <section>
                    <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      All documents
                    </h2>
                    <ul className="flex flex-col gap-1.5">
                      {rest.map((doc) => (
                        <DocRow key={doc.name} doc={doc} showShare />
                      ))}
                    </ul>
                  </section>
                </>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1">
          <div
            ref={editorHostRef}
            id="onlyoffice-editor"
            className="h-full w-full"
          />
        </div>
      )}
    </div>
  )
}
