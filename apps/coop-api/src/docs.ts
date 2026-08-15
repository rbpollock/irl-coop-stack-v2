import * as crypto from "node:crypto";
import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";
import { OOXML_TEMPLATES } from "./ooxml-templates";

// --- Docs host: MinIO-backed document store + OnlyOffice editor configs.
// The coop JWT is the SSO boundary; MinIO creds never reach the browser.
// Editor URLs are JWT-signed with the shared ONLYOFFICE_JWT_SECRET (the
// DocumentServer verifies them; JWT_ENABLED=true on the container).

const MINIO_ENDPOINT = process.env.MINIO_ENDPOINT ?? "172.17.0.1:9000";
// Derived-key creds (out/<instance>/secrets.env): docs-s3 user + onlyoffice.jwt
const MINIO_ACCESS = process.env.MINIO_ACCESS_KEY ?? "docs-s3";
const MINIO_SECRET = process.env.MINIO_SECRET_KEY ?? process.env.MINIO_DOCS_S3 ?? "minioadmin123";
const MINIO_BUCKET = process.env.MINIO_DOCS_BUCKET ?? "docs";
const ONLYOFFICE_PUBLIC_URL = process.env.ONLYOFFICE_PUBLIC_URL ?? "https://office.irl.coop";
const OO_JWT_SECRET = process.env.ONLYOFFICE_JWT_SECRET ?? process.env.ONLYOFFICE_JWT ?? "onlyoffice-dev-secret";
const OO_JWT_HEADER = "Authorization";
// Short-lived content relay tokens (variant B): HMAC(sub|name|expiry) with
// the derived docs.sig secret. The editor fetches content server-side, so
// the URL itself must carry auth that expires and is bound to ONE object.
const DOCS_SIG = process.env.DOCS_SIG ?? "";
const DOCS_TOKEN_TTL_SECONDS = 15 * 60; // 15 min: covers editor open + reload

const HOST = `${MINIO_ENDPOINT}`;
const SCHEME = MINIO_ENDPOINT.startsWith("localhost") || MINIO_ENDPOINT.startsWith("172.") ? "http" : "https";

function hmac(key: Buffer, data: string): Buffer {
  return crypto.createHmac("sha256", key).update(data).digest();
}

function sha256(data: string): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

/** SigV4 signing for S3 REST calls (AWS SDK not in the tree — hand-rolled). */
function s3Headers(method: string, path: string, query = "", body?: Buffer | string): Record<string, string> {
  const now = new Date();
  const amz = now.toISOString().replace(/[:-]|\.\d{3}/g, "");
  const date = amz.slice(0, 8);
  // Hash the RAW bytes (Buffer) — stringifying binary payloads corrupts the
  // hash and MinIO rejects the signature (502 on every PUT).
  const payloadHash = body ? sha256(body as any) : sha256("");
  const headers: Record<string, string> = {
    host: HOST,
    "x-amz-content-sha256": payloadHash,
    "x-amz-date": amz,
  };
  const signed = Object.keys(headers).sort().join(";");
  const canonicalQuery = query.replace(/^[?]/, "");
  const canonical =
    `${method}\n${path}\n${canonicalQuery}\n` +
    Object.keys(headers).sort().map((k) => `${k}:${headers[k]}\n`).join("") +
    `\n${signed}\n${payloadHash}`;
  const scope = `${date}/us-east-1/s3/aws4_request`;
  const stringToSign = `AWS4-HMAC-SHA256\n${amz}\n${scope}\n${sha256(canonical)}`;
  const kDate = hmac(Buffer.from(`AWS4${MINIO_SECRET}`), date);
  const kRegion = hmac(kDate, "us-east-1");
  const kService = hmac(kRegion, "s3");
  const kSigning = hmac(kService, "aws4_request");
  const signature = crypto.createHmac("sha256", kSigning).update(stringToSign).digest("hex");
  headers.authorization =
    `AWS4-HMAC-SHA256 Credential=${MINIO_ACCESS}/${scope}, SignedHeaders=${signed}, Signature=${signature}`;
  return headers;
}

async function s3(method: string, path: string, query = "", body?: Buffer): Promise<Response> {
  const hdrs = s3Headers(method, path, query, body);
  const url = `${SCHEME}://${HOST}${path}${query}`;
  const resp = await fetch(url, {
    method,
    headers: { ...hdrs, "content-type": body ? "application/octet-stream" : undefined } as any,
    body: body ? new Uint8Array(body) : undefined,
  });
  if (!resp.ok) {
    const txt = await resp.text().catch(() => "");
    console.error(`[docs] s3 ${method} ${url} -> ${resp.status}: ${txt.slice(0, 600)}`);
  }
  return resp;
}

/** Sign a payload as an HS256 JWT with the shared OnlyOffice secret
 * (header.payload.signature — the DocumentServer's JWT verifier expects
 * exactly this shape). */
function signJwt(payload: Record<string, unknown>): string {
  const enc = (o: object) => Buffer.from(JSON.stringify(o)).toString("base64url");
  const header = enc({ alg: "HS256", typ: "JWT" });
  const body = enc(payload);
  const sig = crypto.createHmac("sha256", OO_JWT_SECRET).update(`${header}.${body}`).digest("base64url");
  return `${header}.${body}.${sig}`;
}

/** Mint a short-lived content relay token: base64url(sub|name|expiry|hmac).
 * The HMAC is over sub|name|expiry with the derived docs.sig secret, so the
 * token is bound to ONE object and dies after TTL — the editor can fetch the
 * document server-side without a coop JWT, but a captured URL is inert. */
function mintContentToken(sub: string, name: string): string {
  const expiry = Math.floor(Date.now() / 1000) + DOCS_TOKEN_TTL_SECONDS;
  const payload = `${sub}|${name}|${expiry}`;
  const sig = crypto.createHmac("sha256", DOCS_SIG).update(payload).digest("base64url");
  return Buffer.from(payload).toString("base64url") + "." + sig;
}

/** Verify a content relay token. Returns { sub, name } or null. Rejects on:
 * bad shape, HMAC mismatch, expired, or DOCS_SIG unset (fail closed). */
function verifyContentToken(token: string): { sub: string; name: string } | null {
  if (!DOCS_SIG) return null;
  const dot = token.indexOf(".");
  if (dot <= 0) return null;
  const payloadB64 = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const expected = crypto.createHmac("sha256", DOCS_SIG).update(
    Buffer.from(payloadB64, "base64url").toString()
  ).digest("base64url");
  const a = Buffer.from(sig);
  const b = Buffer.from(expected);
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
  const [sub, name, expiryStr] = Buffer.from(payloadB64, "base64url").toString().split("|");
  const expiry = Number(expiryStr);
  if (!sub || !name || !Number.isFinite(expiry) || expiry < Math.floor(Date.now() / 1000)) return null;
  return { sub, name };
}

export default async function docsRoutes(fastify: FastifyInstance): Promise<void> {
  // List the caller's documents (docs/<sub>/ prefix) with metadata for
  // "recent" sorting: name, size (bytes), modified (ISO).
  fastify.get("/api/v1/docs", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const prefix = `docs/${claims.sub}/`;
    const resp = await s3("GET", `/${MINIO_BUCKET}`, `?list-type=2&prefix=${encodeURIComponent(prefix)}`);
    if (!resp.ok) return reply.code(502).send({ error: "storage_unavailable" });
    const xml = await resp.text();
    // Parse <Key>, <Size>, <LastModified> triples (ListObjectsV2).
    const docs: { name: string; size: number; modified: string }[] = [];
    const keyRe = /<Key>([^<]+)<\/Key>/g;
    const sizeRe = /<Size>(\d+)<\/Size>/g;
    const modRe = /<LastModified>([^<]+)<\/LastModified>/g;
    const keys: string[] = [];
    let m: RegExpExecArray | null;
    while ((m = keyRe.exec(xml)) !== null) keys.push(m[1]);
    const sizes: string[] = [];
    while ((m = sizeRe.exec(xml)) !== null) sizes.push(m[1]);
    const mods: string[] = [];
    while ((m = modRe.exec(xml)) !== null) mods.push(m[1]);
    keys.forEach((k, i) => {
      if (!k.startsWith(prefix) || k.endsWith("/")) return;
      docs.push({
        name: k.slice(prefix.length),
        size: Number(sizes[i] ?? 0),
        modified: mods[i] ?? "",
      });
    });
    docs.sort((a, b) => (b.modified > a.modified ? 1 : -1));
    return reply.send({ documents: docs });
  });

  // Create a blank document from an embedded OOXML template. type ∈
  // {docx, xlsx, pptx}; the file lands in the caller's docs/<sub>/ prefix
  // and the frontend opens the editor on it immediately.
  fastify.post("/api/v1/docs/new", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const body = (request.body ?? {}) as Record<string, string>;
    const type = (body.type ?? "docx").replace(/[^a-z]/g, "").toLowerCase();
    const template = OOXML_TEMPLATES[type];
    if (!template) return reply.code(400).send({ error: "unsupported_type", supported: ["docx", "xlsx", "pptx"] });
    const title = (body.name ?? `Untitled.${type}`).replace(/[^a-zA-Z0-9._-]/g, "").slice(0, 80);
    const safe = title.toLowerCase().endsWith(`.${type}`) ? title : `${title}.${type}`;
    const resp = await s3("PUT", `/${MINIO_BUCKET}/docs/${claims.sub}/${safe}`, "", Buffer.from(template, "base64"));
    if (!resp.ok) return reply.code(502).send({ error: "storage_unavailable" });
    return reply.code(201).send({ name: safe, type });
  });

  // Mint an OnlyOffice editor config for a document (JWT-signed).
  // The document's content URL is served back through coop-api (the editor
  // fetches it server-side — its only credentials are the JWT we sign).
  fastify.get("/api/v1/docs/:name/editor", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const name = (request.params as any).name as string;
    const safe = name.replace(/[^a-zA-Z0-9._-]/g, "");
    if (!safe) return reply.code(400).send({ error: "invalid_name" });

    const key = `docs/${claims.sub}/${safe}`;
    const now = Math.floor(Date.now() / 1000);
    // documentType by extension: word / spreadsheet / presentation / pdf —
    // previously only .docx→text and EVERYTHING else→spreadsheet (a .pptx
    // opened in the spreadsheet editor — wrong tool).
    const ext = safe.split(".").pop()?.toLowerCase() ?? "docx";
    const documentType =
      ["docx", "odt", "txt", "rtf", "html", "mht", "epub", "pdf"].includes(ext)
        ? "text"
        : ["xlsx", "ods", "csv"].includes(ext)
          ? "spreadsheet"
          : ["pptx", "odp"].includes(ext)
            ? "presentation"
            : "text";
    // One relay token per editor-open: bound to (sub, name), 15-min TTL.
    // Both the content URL (the editor fetches server-side) and the save
    // callback (OnlyOffice POSTs server-side carrying NO coop JWT) auth via
    // this token — the callbackUrl query string is the only credential the
    // DocumentServer can present, so it must be self-authing.
    const relayToken = mintContentToken(claims.sub, safe);
    const config: Record<string, unknown> = {
      type: "desktop",
      documentType,
      document: {
        // Short-lived relay token (variant B): bound to this user + file,
        // expires in 15 min. The editor fetches this server-side.
        url: `${process.env.COOP_API_BASE_URL ?? "https://api.irl.coop"}/api/v1/docs/${encodeURIComponent(safe)}/content?token=${encodeURIComponent(relayToken)}`,
        title: safe,
        fileType: safe.split(".").pop() ?? "docx",
        key: crypto.createHash("md5").update(key).digest("hex"),
        permissions: { edit: true, download: true, print: true },
      },
      editorConfig: {
        callbackUrl: `${process.env.COOP_API_BASE_URL ?? "https://api.irl.coop"}/api/v1/docs/${encodeURIComponent(safe)}/save?token=${encodeURIComponent(relayToken)}`,
        user: { id: claims.sub, name: claims.email ?? claims.sub },
        // autosave:false → Strict co-editing mode: the manual Save button and
        // Save-as menu item appear. forcesave:true → clicking Save fires a
        // forcesave callback immediately (else the file only compiles when
        // every user closes the doc + ~10s).
        customization: { autosave: false, compactHeader: false, forcesave: true },
      },
    };
    // The full config is signed as an HS256 JWT — the DocumentServer
    // rejects unsigned editor configs when JWT is enabled.
    config.token = signJwt(config);
    return reply.send(config);
  });

  // Document content (the editor fetches this URL server-side). Auth = the
  // short-lived relay token (variant B) — no bare sub, no bearer needed.
  fastify.get("/api/v1/docs/:name/content", async (request, reply) => {
    const q = request.query as Record<string, string>;
    const name = (request.params as any).name as string;
    const safe = name.replace(/[^a-zA-Z0-9._-]/g, "");
    if (!safe) return reply.code(400).send({ error: "invalid_name" });
    const tok = q.token ?? "";
    const authed = verifyContentToken(tok);
    // The token must be bound to THIS filename (no cross-file fetch).
    if (!authed || authed.name !== safe) return reply.code(403).send({ error: "invalid_or_expired_token" });
    const resp = await s3("GET", `/${MINIO_BUCKET}/docs/${authed.sub}/${safe}`);
    if (!resp.ok) return reply.code(404).send({ error: "not_found" });
    const buf = Buffer.from(await resp.arrayBuffer());
    reply.header("content-type", resp.headers.get("content-type") ?? "application/octet-stream");
    reply.header("content-disposition", `inline; filename="${safe}"`);
    return reply.send(buf);
  });

  // Editor save callback (OnlyOffice POSTs the edited file here). OnlyOffice
  // is server-to-server — it carries NO coop JWT, only its own JWT in the
  // body `token` field. Auth is the relay token minted into the callbackUrl
  // query string (same variant-B pattern as the content endpoint): it encodes
  // sub|name and expires, so a captured callback URL is inert.
  fastify.post("/api/v1/docs/:name/save", async (request, reply) => {
    const q = request.query as Record<string, string>;
    const name = (request.params as any).name as string;
    const safe = name.replace(/[^a-zA-Z0-9._-]/g, "");
    if (!safe) return reply.code(400).send({ error: "invalid_name" });
    const authed = verifyContentToken(q.token ?? "");
    // The token must be bound to THIS filename (no cross-file save).
    if (!authed || authed.name !== safe) return reply.code(403).send({ error: "invalid_or_expired_token" });
    const body = request.body as any;
    const url = body?.url as string | undefined;
    // Status notifications (open/close) carry no url — just acknowledge.
    if (!url) return reply.send({ error: 0 });
    const file = await fetch(url);
    if (!file.ok) return reply.send({ error: 1 });
    const buf = Buffer.from(await file.arrayBuffer());
    const resp = await s3("PUT", `/${MINIO_BUCKET}/docs/${authed.sub}/${safe}`, "", buf);
    if (!resp.ok) return reply.send({ error: 1 });
    return reply.send({ error: 0 });
  });

  // Upload a document (raw body).
  fastify.put("/api/v1/docs/:name", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const name = (request.params as any).name as string;
    const safe = name.replace(/[^a-zA-Z0-9._-]/g, "");
    if (!safe) return reply.code(400).send({ error: "invalid_name" });
    // body is the raw Buffer (octet-stream parser registered in server.ts).
    // NOTE: `.buffer` on a Buffer is the BACKING ArrayBuffer (Node shared
    // pool — often larger than the data); never Buffer.from() it. Use the
    // Buffer itself.
    const raw = request.body as any;
    const buf = Buffer.isBuffer(raw) ? raw : raw?.buffer ? Buffer.from(raw.buffer) : null;
    if (!buf) return reply.code(400).send({ error: "empty_body" });
    const resp = await s3("PUT", `/${MINIO_BUCKET}/docs/${claims.sub}/${safe}`, "", Buffer.from(buf));
    if (!resp.ok) return reply.code(502).send({ error: "storage_unavailable" });
    return reply.send({ ok: true, name: safe });
  });
}
