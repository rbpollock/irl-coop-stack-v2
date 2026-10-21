import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";
import { withIdentity } from "./db";
import { ensurePersonalSafe } from "./provisioning";

// ---------------------------------------------------------------------------
// B-11 — the member's passkey, registered as the key that will OWN their Safe.
//
// Today the passkey is only a Keycloak login credential; the Safe is owned by the
// platform backend key. This route closes that split: the browser's WebAuthn
// registration ceremony hands us the credential's P-256 public key, we store it
// against the caller's sub, and the Safe-creation path (next increment) deploys a
// `PasskeyOwner` bound to it and creates the Safe owned by it from block zero.
//
// Stored coordinates are the P-256 x/y as hex strings (0x-prefixed or bare).
// ---------------------------------------------------------------------------

const HEX = /^(0x)?[0-9a-fA-F]+$/;

export default async function passkeyRoutes(fastify: FastifyInstance): Promise<void> {
  // Register (or rotate) the caller's passkey credential.
  fastify.post("/api/v1/me/passkey", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    const body = (request.body ?? {}) as Record<string, unknown>;
    const credentialId = typeof body.credential_id === "string" ? body.credential_id.trim() : "";
    const xRaw = typeof body.x === "string" ? body.x.trim() : "";
    const yRaw = typeof body.y === "string" ? body.y.trim() : "";
    if (!credentialId || !HEX.test(xRaw) || !HEX.test(yRaw)) {
      return reply
        .code(400)
        .send({ error: "credential_id, x, y required (P-256 public key coords as hex)" });
    }
    const x = xRaw.startsWith("0x") ? xRaw : "0x" + xRaw;
    const y = yRaw.startsWith("0x") ? yRaw : "0x" + yRaw;

    await withIdentity(claims.sub, (client) =>
      client.query(
        `INSERT INTO member_passkey (credential_id, sub, pub_x, pub_y)
           VALUES ($1, $2, $3, $4)
         ON CONFLICT (credential_id) DO UPDATE
           SET pub_x = EXCLUDED.pub_x, pub_y = EXCLUDED.pub_y, revoked_at = NULL
           WHERE member_passkey.sub = $2`,
        [credentialId, claims.sub, x, y],
      ),
    );

    // B-11: the Safe is created passkey-owned the moment a key exists to own it.
    // Best-effort — registering the credential must succeed even if the chain is down.
    const safeAddress = await ensurePersonalSafe(claims.sub).catch(() => null);
    return reply.code(201).send({
      registered: true,
      credential_id: credentialId,
      safe_address: safeAddress,
    });
  });

  // The caller's registered passkeys (never another member's — RLS + explicit sub).
  fastify.get("/api/v1/me/passkey", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const rows = await withIdentity(claims.sub, (client) =>
      client.query(
        `SELECT credential_id, owner_address, created_at
           FROM member_passkey
          WHERE sub = $1 AND revoked_at IS NULL
          ORDER BY created_at DESC`,
        [claims.sub],
      ),
    );
    return reply.send({ passkeys: rows.rows });
  });
}