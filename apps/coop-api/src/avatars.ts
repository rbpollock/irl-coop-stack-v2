import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";
import { verifySessionRequest } from "./auth";
import { makeS3Client } from "./s3-client";
import { upsertProfile } from "./profile-store";

// --- Member avatars: custom image upload (replaces the self-hosted DiceBear
// default). Stored in the coop MinIO under `avatars/<sub>` in a dedicated
// `profiles` bucket (provisioned by the profiles-minio-init sidecar — not the
// shared docs bucket). Same SigV4 client as files.ts/docs.ts — MinIO creds
// never reach the browser; the coop JWT / coop_session cookie is the SSO
// boundary.

const MINIO_ENDPOINT = process.env.MINIO_ENDPOINT ?? "172.17.0.1:9000";
const MINIO_ACCESS = process.env.MINIO_PROFILES_ACCESS_KEY ?? "profiles-s3";
const MINIO_SECRET =
  process.env.MINIO_PROFILES_SECRET_KEY ?? process.env.MINIO_PROFILES_S3 ?? "minioadmin123";
const PROFILES_BUCKET = process.env.MINIO_PROFILES_BUCKET ?? "profiles";
const COOP_API_BASE_URL = process.env.COOP_API_BASE_URL ?? "https://api.irl.coop";

const s3 = makeS3Client({ endpoint: MINIO_ENDPOINT, accessKey: MINIO_ACCESS, secretKey: MINIO_SECRET });

const MAX_AVATAR_BYTES = 5 * 1024 * 1024; // 5 MB
const ALLOWED_TYPES: Record<string, boolean> = {
  "image/png": true,
  "image/jpeg": true,
  "image/webp": true,
  "image/gif": true,
};

export default async function avatarRoutes(fastify: FastifyInstance): Promise<void> {
  // Replace the member's avatar. Write endpoint → Bearer-only (short-lived
  // token), matching the group/file write convention.
  fastify.put("/api/v1/profile/avatar", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    const file = await request.file();
    if (!file) return reply.code(400).send({ error: "no_file" });

    const mime = (file.mimetype || "").toLowerCase();
    if (!ALLOWED_TYPES[mime]) {
      return reply.code(400).send({ error: "unsupported_image_type", allowed: Object.keys(ALLOWED_TYPES) });
    }

    const buf = await file.toBuffer();
    if (!buf || buf.length === 0) return reply.code(400).send({ error: "empty_body" });
    if (buf.length > MAX_AVATAR_BYTES) return reply.code(413).send({ error: "avatar_too_large" });

    // No extension in the key — the content-type is stored in MinIO metadata
    // and returned verbatim on GET, so the browser renders it correctly.
    const key = `avatars/${claims.sub}`;
    const resp = await s3.putObject(PROFILES_BUCKET, key, Buffer.from(buf), mime);
    if (!resp.ok) return reply.code(502).send({ error: "storage_unavailable" });

    const url = `${COOP_API_BASE_URL}/api/v1/profile/avatar/${claims.sub}`;
    await upsertProfile(claims.sub, { avatar: url });
    return reply.send({ avatar: url });
  });

  // Serve a member's avatar. Read surface → coop_session cookie (the <img>
  // tag can't send an Authorization header, but same-site image loads carry
  // the .irl.coop session cookie). Any authenticated member may read — the
  // DiceBear default is already derivable from a sub, so this is no wider
  // than the existing identity surface.
  fastify.get("/api/v1/profile/avatar/:sub", async (request, reply) => {
    const session = verifySessionRequest(request, reply);
    if (!session) return;

    const sub = (request.params as any).sub as string;
    if (!/^[A-Za-z0-9_-]{8,64}$/.test(sub)) return reply.code(400).send({ error: "invalid_sub" });

    const resp = await s3.getObject(PROFILES_BUCKET, `avatars/${sub}`);
    if (!resp.ok) return reply.code(404).send({ error: "not_found" });

    const buf = Buffer.from(await resp.arrayBuffer());
    reply.header("content-type", resp.headers.get("content-type") ?? "application/octet-stream");
    // Short cache so a replaced avatar propagates quickly; MinIO's ETag makes
    // revalidation cheap in the meantime.
    reply.header("cache-control", "public, max-age=300");
    return reply.send(buf);
  });
}
