import { FastifyInstance } from "fastify";
import { withIdentity } from "./db";
import { verifyBearer } from "./verify-jwt";

export default async function vaultRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get("/api/v1/groups/:id/vault/secrets", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;

    const rows = await withIdentity(claims.sub, async (client) => {
      const { rows } = await client.query(
        `SELECT id, key_name, created_at, updated_at FROM group_vault_secrets WHERE group_id = $1 ORDER BY created_at DESC`,
        [groupId],
      );
      return rows;
    });
    return reply.send(rows ?? []);
  });

  fastify.post("/api/v1/groups/:id/vault/secrets", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const body = (request.body ?? {}) as Record<string, any>;
    const keyName = typeof body.key_name === "string" ? body.key_name.trim() : "";
    const secretValue = typeof body.secret_value === "string" ? body.secret_value : "";

    if (!keyName || !secretValue) {
      return reply.code(400).send({ error: "key_name and secret_value are required" });
    }

    const stored = await withIdentity(claims.sub, async (client) => {
      const { rows } = await client.query(
        `INSERT INTO group_vault_secrets (group_id, key_name, ciphertext, updated_at)
         VALUES ($1, $2, pgp_sym_encrypt($3, current_setting('app.vault_master_key', true)), now())
         ON CONFLICT (group_id, key_name)
         DO UPDATE SET ciphertext = pgp_sym_encrypt($3, current_setting('app.vault_master_key', true)), updated_at = now()
         RETURNING id, key_name, updated_at`,
        [groupId, keyName, secretValue],
      );
      return rows[0];
    });

    if (!stored) {
      return reply.code(403).send({ error: "permission denied or group not found" });
    }

    return reply.code(201).send(stored);
  });
}
