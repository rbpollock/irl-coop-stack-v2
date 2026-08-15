import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";
import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";
import { makeS3Client } from "./s3-client";

// --- Unified file panel (Phase 1: the docs bucket + virtual folders).
// World-doc rule: the panel is a PROJECTION. Object truth stays in the
// source buckets; the only store of record this module owns is the per-user
// virtual-folder registry (pointers, never blobs). Sharing = variant-B
// relay tokens (short-lived, one-object, derived secret).

const MINIO_ENDPOINT = process.env.MINIO_ENDPOINT ?? "172.17.0.1:9000";
const MINIO_ACCESS = process.env.MINIO_ACCESS_KEY ?? "docs-s3";
const MINIO_SECRET = process.env.MINIO_SECRET_KEY ?? process.env.MINIO_DOCS_S3 ?? "minioadmin123";
const DOCS_BUCKET = process.env.MINIO_DOCS_BUCKET ?? "docs";
const FILES_SIG = process.env.FILES_SIG ?? process.env.DOCS_SIG ?? "";
const SHARE_TTL_SECONDS = 24 * 60 * 60; // 24h share links

const s3 = makeS3Client({ endpoint: MINIO_ENDPOINT, accessKey: MINIO_ACCESS, secretKey: MINIO_SECRET });

// --- Virtual folder registry (dev-grade JSON store, mirror of profile-store).
interface Folder {
  id: string;
  name: string;
  parent: string | null;
  createdAt: string;
}
interface FolderMember {
  folderId: string;
  source: string; // "docs" | "plane" | "stalwart" | "matrix"
  key: string;    // object key WITHOUT the bucket prefix (docs/<sub>/<name> → <name>)
}
interface FolderStore {
  folders: Folder[];
  members: FolderMember[];
}

const STORE_PATH = process.env.COOP_FOLDERS_STORE ?? path.join(process.cwd(), "data", "folders.json");

function loadStore(): Record<string, FolderStore> {
  try {
    return JSON.parse(fs.readFileSync(STORE_PATH, "utf8")) as Record<string, FolderStore>;
  } catch {
    return {};
  }
}
function saveStore(store: Record<string, FolderStore>): void {
  fs.mkdirSync(path.dirname(STORE_PATH), { recursive: true });
  fs.writeFileSync(STORE_PATH, JSON.stringify(store, null, 2));
}
function storeFor(sub: string): FolderStore {
  const store = loadStore();
  store[sub] ??= { folders: [], members: [] };
  return store[sub];
}

interface DocObject {
  name: string;
  size: number;
  modified: string;
}

// --- Sanitize an object key for the docs source. Preserves spaces + unicode
// (MinIO keys allow them; the docs editor's stricter [a-zA-Z0-9._-] whitelist
// is an OnlyOffice constraint, not the panel's). Strips control chars and "|"
// (the share-token delimiter) and drops "." / ".." segments so a hostile name
// can't escape the docs/<sub>/ prefix.
function safeKey(raw: string): string {
  return raw
    .split("/")
    .map((seg) => seg.replace(/[\u0000-\u001f\u007f|]/g, "").trim())
    .filter((seg) => seg !== "" && seg !== "." && seg !== "..")
    .join("/")
    .slice(0, 1024);
}

// --- List the user's objects in the docs bucket (docs/<sub>/ prefix) with
// real size + modified (ListObjectsV2 triple-walk, same as docs.ts).
async function listDocsObjects(sub: string): Promise<DocObject[]> {
  const resp = await s3.list(DOCS_BUCKET, `docs/${sub}/`);
  if (!resp.ok) return [];
  const xml = await resp.text();
  const prefix = `docs/${sub}/`;
  const keyRe = /<Key>([^<]+)<\/Key>/g;
  const sizeRe = /<Size>(\d+)<\/Size>/g;
  const modRe = /<LastModified>([^<]+)<\/LastModified>/g;
  const keys: string[] = [];
  const sizes: string[] = [];
  const mods: string[] = [];
  let m: RegExpExecArray | null;
  while ((m = keyRe.exec(xml)) !== null) keys.push(m[1]);
  while ((m = sizeRe.exec(xml)) !== null) sizes.push(m[1]);
  while ((m = modRe.exec(xml)) !== null) mods.push(m[1]);
  const out: DocObject[] = [];
  keys.forEach((k, i) => {
    if (!k.startsWith(prefix) || k.endsWith("/")) return;
    out.push({
      name: k.slice(prefix.length),
      size: Number(sizes[i] ?? 0),
      modified: mods[i] ?? "",
    });
  });
  out.sort((a, b) => (b.modified > a.modified ? 1 : -1));
  return out;
}

// --- Share tokens (variant B generalized): payload = source|key|expiry.
function mintShareToken(source: string, key: string): string {
  const expiry = Math.floor(Date.now() / 1000) + SHARE_TTL_SECONDS;
  const payload = `${source}|${key}|${expiry}`;
  const sig = crypto.createHmac("sha256", FILES_SIG).update(payload).digest("base64url");
  return Buffer.from(payload).toString("base64url") + "." + sig;
}
function verifyShareToken(token: string): { source: string; key: string } | null {
  if (!FILES_SIG) return null;
  const dot = token.indexOf(".");
  if (dot <= 0) return null;
  const payloadB64 = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const expected = crypto
    .createHmac("sha256", FILES_SIG)
    .update(Buffer.from(payloadB64, "base64url").toString())
    .digest("base64url");
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  const [source, key, expiryStr] = Buffer.from(payloadB64, "base64url").toString().split("|");
  const expiry = Number(expiryStr);
  if (!source || !key || !Number.isFinite(expiry) || expiry < Math.floor(Date.now() / 1000)) return null;
  return { source, key };
}

export default async function filesRoutes(fastify: FastifyInstance): Promise<void> {
  // --- Aggregated listing: folders + docs-bucket objects (seat-scoped).
  fastify.get("/api/v1/files", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const store = storeFor(claims.sub);
    const docs = await listDocsObjects(claims.sub);
    return reply.send({
      folders: store.folders,
      members: store.members,
      sources: {
        docs: docs.map((o) => ({ name: o.name, size: o.size, modified: o.modified })),
        // Phase 2+: stalwart attachments, matrix media, plane (metadata joins)
      },
    });
  });

  // --- Folder CRUD (virtual — pointers only).
  fastify.post("/api/v1/files/folders", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const body = (request.body ?? {}) as Record<string, any>;
    const name = typeof body.name === "string" ? body.name.trim().slice(0, 80) : "";
    if (!name) return reply.code(400).send({ error: "name is required" });
    const store = storeFor(claims.sub);
    const folder: Folder = {
      id: crypto.randomUUID(),
      name,
      parent: typeof body.parent === "string" ? body.parent : null,
      createdAt: new Date().toISOString(),
    };
    store.folders.push(folder);
    const all = loadStore();
    all[claims.sub] = store;
    saveStore(all);
    return reply.code(201).send({ folder });
  });

  fastify.delete("/api/v1/files/folders/:id", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const id = (request.params as any).id as string;
    const store = storeFor(claims.sub);
    store.folders = store.folders.filter((f) => f.id !== id);
    store.members = store.members.filter((m) => m.folderId !== id);
    const all = loadStore();
    all[claims.sub] = store;
    saveStore(all);
    return reply.send({ ok: true });
  });

  // --- Move a folder (change its parent) — nesting support. Guarded against
  // self-nesting and cycles so a folder can't become its own ancestor.
  fastify.patch("/api/v1/files/folders/:id", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const id = (request.params as any).id as string;
    const body = (request.body ?? {}) as Record<string, any>;
    const store = storeFor(claims.sub);
    const folder = store.folders.find((f) => f.id === id);
    if (!folder) return reply.code(404).send({ error: "folder_not_found" });
    const parent = typeof body.parent === "string" ? body.parent : null;
    if (parent === id) return reply.code(400).send({ error: "cannot_nest_in_self" });
    if (parent && !store.folders.some((f) => f.id === parent)) {
      return reply.code(404).send({ error: "parent_not_found" });
    }
    // Reject if `parent` is a descendant of the folder being moved.
    let cur = parent ? store.folders.find((f) => f.id === parent) : undefined;
    while (cur && cur.parent) {
      if (cur.parent === id) return reply.code(400).send({ error: "cannot_nest_in_descendant" });
      const next = store.folders.find((f) => f.id === cur!.parent);
      cur = next;
    }
    folder.parent = parent;
    const all = loadStore();
    all[claims.sub] = store;
    saveStore(all);
    return reply.send({ ok: true });
  });

  // --- Add an object to a folder (pointer update — the object stays put).
  fastify.post("/api/v1/files/folders/:id/members", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const id = (request.params as any).id as string;
    const body = (request.body ?? {}) as Record<string, any>;
    const key = typeof body.key === "string" ? body.key : "";
    const source = typeof body.source === "string" ? body.source : "docs";
    if (!key) return reply.code(400).send({ error: "key is required" });
    const store = storeFor(claims.sub);
    if (!store.folders.some((f) => f.id === id)) {
      return reply.code(404).send({ error: "folder not found" });
    }
    // normalize docs keys: strip the docs/<sub>/ prefix so pointers are stable
    let norm = key;
    if (source === "docs") {
      const prefix = `docs/${claims.sub}/`;
      if (norm.startsWith(prefix)) norm = norm.slice(prefix.length);
    }
    if (store.members.some((m) => m.folderId === id && m.key === norm && m.source === source)) {
      return reply.send({ ok: true, already: true });
    }
    store.members.push({ folderId: id, source, key: norm });
    const all = loadStore();
    all[claims.sub] = store;
    saveStore(all);
    return reply.code(201).send({ ok: true });
  });

  // --- Remove an object from a folder (pointer only — the object stays put).
  fastify.delete("/api/v1/files/folders/:id/members", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const id = (request.params as any).id as string;
    const q = request.query as Record<string, string>;
    const key = typeof q.key === "string" ? q.key : "";
    const source = typeof q.source === "string" ? q.source : "docs";
    if (!key) return reply.code(400).send({ error: "key is required" });
    const store = storeFor(claims.sub);
    store.members = store.members.filter(
      (m) => !(m.folderId === id && m.key === key && m.source === source),
    );
    const all = loadStore();
    all[claims.sub] = store;
    saveStore(all);
    return reply.send({ ok: true });
  });

  // --- Upload via multipart FormData (the FileManager's fileUploadConfig
  // sends the file under the "file" field to a fixed URL). Filename comes
  // from the file part, not the URL.
  fastify.post("/api/v1/files/docs", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const file = await request.file();
    if (!file) return reply.code(400).send({ error: "no_file" });
    const name = safeKey(file.filename);
    if (!name) return reply.code(400).send({ error: "invalid_key" });
    const buf = await file.toBuffer();
    if (!buf || buf.length === 0) return reply.code(400).send({ error: "empty_body" });
    const objectKey = `docs/${claims.sub}/${name}`;
    const resp = await s3.putObject(DOCS_BUCKET, objectKey, Buffer.from(buf));
    if (!resp.ok) return reply.code(502).send({ error: "storage_unavailable" });
    return reply.send({ name, size: buf.length });
  });

  // --- Upload an object (raw body) to the caller's docs prefix. Names keep
  // their spaces/unicode; only traversal + control chars are stripped.
  fastify.put("/api/v1/files/docs/:key", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const key = safeKey((request.params as any).key as string);
    if (!key) return reply.code(400).send({ error: "invalid_key" });
    const raw = request.body as any;
    const buf = Buffer.isBuffer(raw) ? raw : raw?.buffer ? Buffer.from(raw.buffer) : null;
    if (!buf || buf.length === 0) return reply.code(400).send({ error: "empty_body" });
    const objectKey = `docs/${claims.sub}/${key}`;
    const resp = await s3.putObject(DOCS_BUCKET, objectKey, Buffer.from(buf));
    if (!resp.ok) return reply.code(502).send({ error: "storage_unavailable" });
    return reply.send({ ok: true, name: key });
  });

  // --- Delete an object (docs source). Object truth goes away and any folder
  // pointers to it are dropped, so folders never show a dangling key.
  fastify.delete("/api/v1/files/docs/:key", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const key = safeKey((request.params as any).key as string);
    if (!key) return reply.code(400).send({ error: "invalid_key" });
    const objectKey = `docs/${claims.sub}/${key}`;
    const resp = await s3.deleteObject(DOCS_BUCKET, objectKey);
    if (!resp.ok) return reply.code(404).send({ error: "not_found" });
    const store = storeFor(claims.sub);
    store.members = store.members.filter((m) => !(m.source === "docs" && m.key === key));
    const all = loadStore();
    all[claims.sub] = store;
    saveStore(all);
    return reply.send({ ok: true });
  });

  // --- Rename an object (docs source). S3 has no rename — server-side copy
  // to the new key, then delete the old one. Folder pointers to the old name
  // are rewritten so virtual folders follow the rename.
  fastify.post("/api/v1/files/docs/:key/rename", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const key = safeKey((request.params as any).key as string);
    if (!key) return reply.code(400).send({ error: "invalid_key" });
    const body = (request.body ?? {}) as Record<string, any>;
    const to = safeKey(typeof body.to === "string" ? body.to : "");
    if (!to) return reply.code(400).send({ error: "to is required" });
    const srcKey = `docs/${claims.sub}/${key}`;
    const dstKey = `docs/${claims.sub}/${to}`;
    if (srcKey === dstKey) return reply.send({ ok: true, name: to });
    // Don't clobber an existing object at the destination.
    const dstHead = await s3.raw(
      "HEAD",
      `/${DOCS_BUCKET}/${dstKey.split("/").map(encodeURIComponent).join("/")}`
    );
    if (dstHead.ok) return reply.code(409).send({ error: "target_exists" });
    const copied = await s3.copyObject(DOCS_BUCKET, srcKey, dstKey);
    if (!copied.ok) return reply.code(404).send({ error: "not_found" });
    const del = await s3.deleteObject(DOCS_BUCKET, srcKey);
    if (!del.ok) {
      // Copy succeeded but source delete failed — the rename is half-applied.
      // Surface it loudly rather than silently leaving a duplicate.
      console.error(`[files] rename: copied to ${dstKey} but failed to delete ${srcKey} (${del.status})`);
      return reply.code(502).send({ error: "rename_partial" });
    }
    // Rewrite folder pointers so virtual folders follow the rename.
    const store = storeFor(claims.sub);
    let changed = false;
    for (const m of store.members) {
      if (m.source === "docs" && m.key === key) {
        m.key = to;
        changed = true;
      }
    }
    if (changed) {
      const all = loadStore();
      all[claims.sub] = store;
      saveStore(all);
    }
    return reply.send({ ok: true, name: to });
  });

  // --- Download an object (docs source) with an attachment disposition.
  // Bearer or relay token, same auth as /content — but "download", not inline.
  fastify.get("/api/v1/files/docs/:key/download", async (request, reply) => {
    const key = safeKey((request.params as any).key as string);
    if (!key) return reply.code(400).send({ error: "invalid_key" });
    const q = request.query as Record<string, string>;
    let objectKey = "";
    if (q.token) {
      const authed = verifyShareToken(q.token);
      if (!authed || authed.source !== "docs" || !authed.key.endsWith(key)) {
        return reply.code(403).send({ error: "invalid_or_expired_token" });
      }
      objectKey = authed.key;
    } else {
      const claims = verifyBearer(request, reply);
      if (!claims) return;
      objectKey = `docs/${claims.sub}/${key}`;
    }
    const resp = await s3.getObject(DOCS_BUCKET, objectKey);
    if (!resp.ok) return reply.code(404).send({ error: "not_found" });
    const buf = Buffer.from(await resp.arrayBuffer());
    const name = objectKey.split("/").pop() ?? key;
    reply.header("content-type", resp.headers.get("content-type") ?? "application/octet-stream");
    reply.header("content-disposition", `attachment; filename="${name}"`);
    return reply.send(buf);
  });

  // --- Share: mint a variant-B relay token for one object.
  fastify.post("/api/v1/files/:source/:key/share", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const source = (request.params as any).source as string;
    const keyParam = (request.params as any).key as string;
    const key = safeKey(keyParam);
    if (!key) return reply.code(400).send({ error: "invalid_key" });
    if (source !== "docs") {
      return reply.code(501).send({ error: "source_not_joined" }); // Phase 2+
    }
    // Authorization: the *** must be the caller's (docs/<sub>/ prefix).
    const objectKey = `docs/${claims.sub}/${key}`;
    // HEAD via the client's key encoding (slashes stay as separators —
    // encodeURIComponent on the whole key would break the path).
    const head = await s3.raw("HEAD", `/${DOCS_BUCKET}/${objectKey.split("/").map(encodeURIComponent).join("/")}`);
    if (!head.ok) return reply.code(404).send({ error: "not_found" });
    const token = mintShareToken(source, objectKey);
    return reply.send({
      url: `${process.env.COOP_API_BASE_URL ?? "https://api.irl.coop"}/api/v1/files/s/${encodeURIComponent(token)}`,
      expiresIn: SHARE_TTL_SECONDS,
    });
  });

  // --- Shared-object stream (no bearer — the token IS the auth).
  fastify.get("/api/v1/files/s/:token", async (request, reply) => {
    const tok = (request.params as any).token as string;
    const authed = verifyShareToken(tok);
    if (!authed) return reply.code(403).send({ error: "invalid_or_expired_token" });
    if (authed.source !== "docs") return reply.code(404).send({ error: "not_found" });
    const resp = await s3.getObject(DOCS_BUCKET, authed.key);
    if (!resp.ok) return reply.code(404).send({ error: "not_found" });
    const buf = Buffer.from(await resp.arrayBuffer());
    const name = authed.key.split("/").pop() ?? "file";
    reply.header("content-type", resp.headers.get("content-type") ?? "application/octet-stream");
    reply.header("content-disposition", `inline; filename="${name}"`);
    return reply.send(buf);
  });

  // --- Content stream (bearer or relay token — the docs editor's pattern).
  fastify.get("/api/v1/files/:source/:key/content", async (request, reply) => {
    const source = (request.params as any).source as string;
    const keyParam = (request.params as any).key as string;
    const key = safeKey(keyParam);
    if (!key) return reply.code(400).send({ error: "invalid_key" });
    if (source !== "docs") return reply.code(404).send({ error: "not_found" });
    // token in query (editor-style) OR bearer (dashboard-style)
    const q = request.query as Record<string, string>;
    let objectKey = "";
    if (q.token) {
      const authed = verifyShareToken(q.token);
      if (!authed || authed.source !== "docs" || !authed.key.endsWith(key)) {
        return reply.code(403).send({ error: "invalid_or_expired_token" });
      }
      objectKey = authed.key;
    } else {
      const claims = verifyBearer(request, reply);
      if (!claims) return;
      objectKey = `docs/${claims.sub}/${key}`;
    }
    const resp = await s3.getObject(DOCS_BUCKET, objectKey);
    if (!resp.ok) return reply.code(404).send({ error: "not_found" });
    const buf = Buffer.from(await resp.arrayBuffer());
    reply.header("content-type", resp.headers.get("content-type") ?? "application/octet-stream");
    reply.header("content-disposition", `inline; filename="${key}"`);
    return reply.send(buf);
  });
}
