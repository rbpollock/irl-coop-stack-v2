"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import { useParams, useRouter } from "next/navigation"
import { FileManager } from "@cubone/react-file-manager"
import "@cubone/react-file-manager/dist/style.css"
import "./file-manager.css"
import type { FileManagerFile } from "@cubone/react-file-manager"

import { ensureLocalizedPathname } from "@/lib/i18n"

// Files — the unified file panel, now driven by @cubone/react-file-manager.
// The component is a client-side path browser: we hand it the whole flattened
// tree (virtual folders + docs-bucket objects) and it filters by path prefix.
// Object truth stays in MinIO; folders are pointers. Every mutation goes
// through coop-api so MinIO credentials never reach the browser.
const COOP_API_URL =
  process.env.NEXT_PUBLIC_COOP_API_URL ?? "https://api.irl.coop"

type Folder = { id: string; name: string; parent: string | null; createdAt: string }
type FolderMember = { folderId: string; source: string; key: string }
type DocMeta = { name: string; size: number; modified: string }

// Extensions the OnlyOffice editor can open (docs.ts documentType mapping).
const DOC_EXTS = new Set([
  "docx", "odt", "txt", "rtf", "html", "mht", "epub", "pdf",
  "xlsx", "ods", "csv", "pptx", "odp",
])

export default function FilesPage() {
  const { data: session } = useSession()
  const router = useRouter()
  const params = useParams()
  const locale = params.lang as string
  const [folders, setFolders] = useState<Folder[]>([])
  const [members, setMembers] = useState<FolderMember[]>([])
  const [docs, setDocs] = useState<DocMeta[]>([])
  const [loading, setLoading] = useState(true)

  const token = session?.accessToken as string | undefined

  const refresh = useCallback(async () => {
    if (!token) return
    setLoading(true)
    try {
      const res = await fetch(`${COOP_API_URL}/api/v1/files`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error(`list failed (${res.status})`)
      const body = await res.json()
      setFolders(body.folders ?? [])
      setMembers(body.members ?? [])
      setDocs(body.sources?.docs ?? [])
    } catch (err) {
      console.error("[files]", err)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    refresh()
  }, [refresh])

  // The FileManager only marks a row draggable once its checkbox is checked
  // (draggable = checkbox && move). Auto-check on plain left-mousedown so
  // click-to-drag works like a normal file manager. Shift/ctrl (multi-select)
  // and the checkbox itself are left to the package.
  useEffect(() => {
    const onMouseDown = (ev: MouseEvent) => {
      if (ev.button !== 0 || ev.shiftKey || ev.ctrlKey || ev.metaKey) return
      const target = ev.target as HTMLElement | null
      if (!target || !target.closest) return
      if (target.closest('input[type="checkbox"]')) return
      const row = target.closest(".file-item-container")
      if (!row) return
      const cb = row.querySelector<HTMLInputElement>('input[type="checkbox"]')
      if (cb && !cb.checked) cb.click()
    }
    document.addEventListener("mousedown", onMouseDown)
    return () => document.removeEventListener("mousedown", onMouseDown)
  }, [])

  // Resolve each folder's full path (nesting-aware) + a reverse lookup, so a
  // FileManager path (e.g. "/Projects/Coop") maps back to its folder id.
  const folderPathById = useMemo(() => {
    const folderById = new Map(folders.map((f) => [f.id, f]))
    const pathById = new Map<string, string>()
    const resolve = (id: string): string => {
      if (pathById.has(id)) return pathById.get(id)!
      const parts: string[] = []
      const seen = new Set<string>()
      let cur = folderById.get(id)
      while (cur && !seen.has(cur.id)) {
        seen.add(cur.id)
        parts.unshift(cur.name)
        cur = cur.parent ? folderById.get(cur.parent) : undefined
      }
      const p = `/${parts.join("/")}`
      pathById.set(id, p)
      return p
    }
    for (const f of folders) resolve(f.id)
    return pathById
  }, [folders])

  const folderIdByPath = useMemo(() => {
    const m = new Map<string, string>()
    for (const f of folders) m.set(folderPathById.get(f.id) ?? `/${f.name}`, f.id)
    return m
  }, [folders, folderPathById])

  // Flatten the backing store into the FileManager's tree (nesting-aware).
  // Unfiled objects sit at the root; filed ones appear under their folder's
  // full path.
  const tree = useMemo<FileManagerFile[]>(() => {
    const out: FileManagerFile[] = folders.map((f) => ({
      name: f.name,
      isDirectory: true,
      path: folderPathById.get(f.id) ?? `/${f.name}`,
      updatedAt: f.createdAt,
    }))
    for (const d of docs) {
      const ptrs = members.filter((m) => m.source === "docs" && m.key === d.name)
      const base = { name: d.name, isDirectory: false, size: d.size, updatedAt: d.modified }
      if (ptrs.length === 0) {
        out.push({ ...base, path: `/${d.name}` })
      } else {
        for (const p of ptrs) {
          const folderPath = folderPathById.get(p.folderId)
          if (folderPath) out.push({ ...base, path: `${folderPath}/${d.name}` })
        }
      }
    }
    return out
  }, [folders, members, docs, folderPathById])

  if (!session) return null

  function ext(name: string) {
    return name.split(".").pop()?.toLowerCase() ?? ""
  }

  async function download(files: FileManagerFile[]) {
    if (!token) return
    for (const f of files) {
      if (f.isDirectory) continue
      const res = await fetch(
        `${COOP_API_URL}/api/v1/files/docs/${encodeURIComponent(f.name)}/download`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (!res.ok) continue
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = f.name
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    }
  }

  function onFileOpen(file: FileManagerFile) {
    if (file.isDirectory) return
    if (DOC_EXTS.has(ext(file.name))) {
      const path =
        ensureLocalizedPathname("/apps/docs", locale) +
        "?name=" +
        encodeURIComponent(file.name)
      router.push(path)
    } else {
      download([file])
    }
  }

  async function onCreateFolder(name: string, parentFolder?: FileManagerFile) {
    if (!token || !name.trim()) return
    const parentId = parentFolder?.isDirectory
      ? (folderIdByPath.get(parentFolder.path) ?? null)
      : null
    await fetch(`${COOP_API_URL}/api/v1/files/folders`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: name.trim(), parent: parentId }),
    })
    await refresh()
  }

  async function onDelete(files: FileManagerFile[]) {
    if (!token) return
    for (const f of files) {
      if (f.isDirectory) {
        const folderId = folderIdByPath.get(f.path)
        if (folderId) {
          await fetch(`${COOP_API_URL}/api/v1/files/folders/${folderId}`, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${token}` },
          })
        }
      } else {
        await fetch(
          `${COOP_API_URL}/api/v1/files/docs/${encodeURIComponent(f.name)}`,
          { method: "DELETE", headers: { Authorization: `Bearer ${token}` } },
        )
      }
    }
    await refresh()
  }

  async function onRename(file: FileManagerFile, newName: string) {
    if (!token || file.isDirectory || !newName.trim()) return
    await fetch(
      `${COOP_API_URL}/api/v1/files/docs/${encodeURIComponent(file.name)}/rename`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ to: newName.trim() }),
      },
    )
    await refresh()
  }

  // Real move: a file lands in exactly one folder (or root); a folder's parent
  // changes. Moving to root = unfile (drop pointers) / parent null.
  async function onPaste(
    files: FileManagerFile[],
    destFolder: FileManagerFile,
    opType: "copy" | "move",
  ) {
    if (!token || opType !== "move") return
    const destId = destFolder?.isDirectory
      ? (folderIdByPath.get(destFolder.path) ?? null)
      : null
    for (const f of files) {
      if (f.isDirectory) {
        const folderId = folderIdByPath.get(f.path)
        if (!folderId) continue
        await fetch(`${COOP_API_URL}/api/v1/files/folders/${folderId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
          body: JSON.stringify({ parent: destId }),
        })
      } else {
        // single-location: drop existing pointers, then point at the dest
        for (const m of members.filter((m) => m.source === "docs" && m.key === f.name)) {
          await fetch(
            `${COOP_API_URL}/api/v1/files/folders/${m.folderId}/members?key=${encodeURIComponent(f.name)}&source=docs`,
            { method: "DELETE", headers: { Authorization: `Bearer ${token}` } },
          )
        }
        if (destId) {
          await fetch(`${COOP_API_URL}/api/v1/files/folders/${destId}/members`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ source: "docs", key: f.name }),
          })
        }
      }
    }
    await refresh()
  }

  return (
    <div className="h-[calc(100svh-6.82rem)] w-full overflow-hidden">
      <FileManager
        files={tree}
        isLoading={loading}
        height="100%"
        width="100%"
        layout="list"
        primaryColor="hsl(var(--primary))"
        fontFamily="var(--font-lato), sans-serif"
        permissions={{ copy: false }}
        fileUploadConfig={
          token
            ? {
                url: `${COOP_API_URL}/api/v1/files/docs`,
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
              }
            : undefined
        }
        onFileOpen={onFileOpen}
        onCreateFolder={onCreateFolder}
        onDelete={onDelete}
        onRename={onRename}
        onDownload={download}
        onPaste={onPaste}
        onRefresh={refresh}
        onFileUploaded={refresh}
      />
    </div>
  )
}
