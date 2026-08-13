# The Files Panel — unified file viewer + virtual folder manager

Status: Phase 1 built — backend verified 15/15 live + panel UI (folders,
share, editor) shipped 2026-08-12 · Aug 2026 · Extends
world-doc-and-contacts.md (projection rule, seats), irl-coop-group.md (group
file sharing), and the docs host (docs-host-onlyoffice.md). Builds on the
single-storage backbone: all four sources now live on the coop MinIO
(`docs`, `stalwart`, `matrix-media`, `plane` buckets).

## 1. Principles

1. **One view, many sources.** The Files panel is a per-user projection over every source bucket on the coop MinIO. It shows pointers with real names, never raw keys, and never copies blobs.
2. **The source app is the authority.** Plane decides who sees plane attachments; stalwart decides who reads a mailbox; `docs/<sub>/` scopes OnlyOffice files; synapse scopes media. The panel asks each source "what can this seat see?" and only shows what comes back. No duplicated ACLs in MinIO.
3. **Virtual folders, not real moves.** MinIO has prefixes, not folders — and renaming source-app keys breaks their references. Folders are a registry (per-user/group JSON in coop-api, like the profile store) mapping folder id → list of object pointers. "Move" = pointer update.
4. **Sharing = signed links (variant B).** A share is a short-lived relay token (the docs `mintContentToken` pattern, generalized) minted by coop-api only after the source app's authorization passes. Expiry, one-object binding, derived secret.
5. **Rebuildable.** The panel is a projection: list sources, join metadata, apply the folder registry, render. Nothing the panel "knows" is a store of record except the folder registry itself (which is user-owned organization, not truth).

## 2. What the panel shows (per seat)

```
Files
├── 📁 My folders            (virtual, from the registry)
│   ├── 📁 Budget 2026       → pointers: docs/<sub>/budget.xlsx, plane attachment 3f2a...
│   └── 📁 Farm coalition    → pointers: docs/<sub>/coop-agreement.docx, matrix media a1...
├── 📄 Documents (OnlyOffice)  → docs bucket, names = keys
├── 📎 Mail attachments        → stalwart bucket, names from the message store (JMAP/registry join)
├── 🖼 Chat media              → matrix-media bucket, names from synapse DB
└── 📋 Project attachments    → plane bucket, names from plane DB (via plane API)
```

Each entry: name, source, type icon, size, modified, owner. Actions per source: view/download always; edit if the source supports it (docs → OnlyOffice editor; others open in their app).

## 3. The metadata join (the real work)

| Source | Object location | Filename source | Join path |
|---|---|---|---|
| OnlyOffice | `docs/<sub>/<name>` | the key IS the name | none (direct) |
| Mail | `stalwart/<blob-id>` | stalwart message store (MIME filename) | stalwart registry API / JMAP with the coop JWT |
| Matrix | `matrix-media/<hash>` | synapse media store DB | synapse admin API / media endpoint |
| Plane | `plane/uploads/<uuid>/<name-uuid>` | plane DB (attachment → issue → original name) | plane API with the coop JWT |

The panel fetches each source's listing through coop-api, which joins the metadata per source. Phase 1 = docs only (direct); phases 2-3 add the joins.

## 4. Virtual folder registry (coop-api)

```json
// data/folders.json — keyed by sub (same dev-grade store as profiles.json)
{
  "sub-123": {
    "folders": [
      { "id": "fld-1", "name": "Budget 2026", "parent": null, "createdAt": "..." }
    ],
    "members": [
      { "folderId": "fld-1", "source": "docs", "key": "budget.xlsx" },
      { "folderId": "fld-1", "source": "plane", "key": "uploads/3f2a/8b4f.jpg" }
    ]
  }
}
```

- Folders are per-user by default; group folders (shared with a group seat) come with the group layer (irl-coop-group.md §5).
- Move = update `members[].folderId`. Delete folder = remove folder + its members (pointers only — objects untouched).
- The registry is the ONLY store of record the panel owns; everything else is projection.

## 5. Sharing (variant B generalized)

`POST /api/v1/files/:source/:key/share` → after source authorization, mint a relay token:
`base64url(source|bucket|key|sub|expiry) . HMAC(payload, files.sig)` — derived secret `files.sig`.
`GET /api/v1/files/s/:token` → verify + stream from the owning bucket.
Expiry default 24h; scoped to ONE object; revocable by not re-issuing (short TTLs).

Group shares ride the seat model: a member of a group with `visibility: members` on a folder can view its contents; hidden groups keep the zk-proof tier (provable access, not enumerable).

## 6. API surface (coop-api, coop JWT)

```
GET    /api/v1/files                        → aggregated listing (all sources, seat-filtered)
POST   /api/v1/files/folders                → { name, parent? } create folder
POST   /api/v1/files/folders/:id/members    → { source, key } add object to folder
DELETE /api/v1/files/folders/:id            → remove folder (pointers only)
POST   /api/v1/files/:source/:key/share     → mint share token (variant B)
GET    /api/v1/files/s/:token               → stream shared object (no bearer)
GET    /api/v1/files/:source/:key/content   → stream (relay token or bearer)
```

## 7. Build sequence

1. **Phase 1 (now)**: Files panel over the docs bucket — folders registry, listing, download, share (variant B), file-type icons. The current docs page becomes the panel's Documents section; the OnlyOffice editor stays as the opener.
2. **Phase 2**: mail attachments + chat media joins (stalwart registry + synapse admin API).
3. **Phase 3**: plane join via plane API.
4. **Phase 4**: group folders + group shares (rides the seat model from irl-coop-group.md).

## 8. Open decisions (Robbie)

1. Folder registry home: coop-api JSON store (dev-grade, now) vs a Citus table (when coop-api gets a real DB). Recommend: JSON now, migrate later — the shape is already table-ready.
2. Share link UX: copy-to-clipboard token URL (simple) vs a share dialog with expiry picker (nicer). Recommend: simple first.
3. Cross-source "move into folder": should moving a docs file into a folder also move its S3 object (so the docs editor sees it there), or is the folder purely virtual (object stays at `docs/<sub>/`, folder points at it)? Recommend: purely virtual — moving objects breaks the docs editor's key-based lookups. Folders organize, they don't relocate.
