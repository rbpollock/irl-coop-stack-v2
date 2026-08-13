import type { FastifyInstance } from "fastify";
import { ethers } from "ethers";
import { verifyBearer } from "./verify-jwt";
import { deploySafe } from "./safe";
import { pool } from "./db";

// ---------------------------------------------------------------------------
// Groups = Safes (Layer-2 projection). A group IS a Safe: "create a group"
// wraps the existing Safe deployment (safe.ts) and records a projection row
// so apps can query members, seats and scoped resources without touching the
// chain. Members are seats (sub + roles + alias + visibility).
// ---------------------------------------------------------------------------

const PRIVACY = ["open", "members", "hidden"] as const;
const VISIBILITY = ["role-only", "alias", "canonical"] as const;

function safeEnv(): { factory: string; singleton: string; backendKey: string } | null {
  const factory = process.env.SAFE_PROXY_FACTORY_ADDRESS ?? "";
  const singleton = process.env.SAFE_SINGLETON_ADDRESS ?? "";
  const backendKey = process.env.SAFE_BACKEND_SIGNER_KEY ?? "";
  return factory && singleton && backendKey ? { factory, singleton, backendKey } : null;
}

// Deterministic, uncorrelatable salt for the member when none is supplied:
// the realm sub is a UUID — strip hyphens and read as hex (same rule the
// dashboard Group Wallet uses to predict the address).
function saltFor(sub: string): bigint {
  const hex = sub.replace(/-/g, "");
  const n = BigInt("0x" + hex);
  return n > 0n ? n : 1n;
}

async function isOwner(groupId: string, sub: string): Promise<boolean> {
  const r = await pool.query(
    `SELECT 1 FROM group_members WHERE group_id = $1 AND sub = $2 AND 'owner' = ANY(roles)`,
    [groupId, sub],
  );
  return (r.rowCount ?? 0) > 0;
}

async function isMember(groupId: string, sub: string): Promise<boolean> {
  const r = await pool.query(
    `SELECT 1 FROM group_members WHERE group_id = $1 AND sub = $2`,
    [groupId, sub],
  );
  return (r.rowCount ?? 0) > 0;
}

export default async function groupRoutes(fastify: FastifyInstance): Promise<void> {
  // Deploy the member's Safe + record the group projection in one event.
  fastify.post("/api/v1/groups", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const env = safeEnv();
    if (!env) return reply.code(503).send({ error: "safe contracts not configured" });

    const body = (request.body ?? {}) as Record<string, any>;
    const name = typeof body.name === "string" ? body.name.trim().slice(0, 120) : "";
    const privacy = PRIVACY.includes(body.privacy) ? body.privacy : "members";
    if (!name) return reply.code(400).send({ error: "name is required" });

    let saltNonce: bigint;
    try {
      saltNonce =
        typeof body.saltNonce === "string" && body.saltNonce
          ? BigInt(body.saltNonce)
          : saltFor(claims.sub);
    } catch {
      return reply.code(400).send({ error: "saltNonce out of range" });
    }

    try {
      const provider = new ethers.JsonRpcProvider(process.env.RPC_URL ?? "http://127.0.0.1:8545");
      const signer = new ethers.Wallet(env.backendKey, provider);
      // 1-of-1 backend-signer-owned for now; real owner set (passkey owners,
      // N-of-M) arrives with the account model. The Safe IS the group.
      const { safeAddress, txHash } = await deploySafe(
        signer,
        { factory: env.factory, singleton: env.singleton, saltNonce },
        [signer.address],
        1,
      );

      const group = await pool.query(
        `INSERT INTO groups (safe_address, name, privacy) VALUES ($1, $2, $3)
         RETURNING id, safe_address, name, description, privacy, created_at`,
        [safeAddress, name, privacy],
      );
      const row = group.rows[0];
      await pool.query(
        `INSERT INTO group_members (group_id, sub, roles, visibility) VALUES ($1, $2, $3, 'canonical')`,
        [row.id, claims.sub, ["owner"]],
      );
      return reply.code(201).send({ ...row, tx_hash: txHash, seat: { roles: ["owner"] } });
    } catch (err: any) {
      request.log.error({ err: err.message }, "group deploy failed");
      return reply.code(500).send({ error: err.message });
    }
  });

  // Groups I belong to, with my seat.
  fastify.get("/api/v1/groups", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const { rows } = await pool.query(
      `SELECT g.id, g.safe_address, g.name, g.description, g.privacy, g.created_at,
              gm.roles, gm.alias, gm.visibility
       FROM groups g
       JOIN group_members gm ON gm.group_id = g.id
       WHERE gm.sub = $1
       ORDER BY g.created_at DESC`,
      [claims.sub],
    );
    return reply.send(rows);
  });

  // Invite / seat a member in a group.
  fastify.post("/api/v1/groups/:id/members", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    if (!(await isOwner(groupId, claims.sub)))
      return reply.code(403).send({ error: "not a group owner" });

    const body = (request.body ?? {}) as Record<string, any>;
    const sub = typeof body.sub === "string" ? body.sub.trim() : "";
    const roles = Array.isArray(body.roles) ? body.roles.map(String) : [];
    const alias = typeof body.alias === "string" ? body.alias.trim().slice(0, 80) : null;
    const visibility = VISIBILITY.includes(body.visibility) ? body.visibility : "canonical";
    if (!sub) return reply.code(400).send({ error: "sub is required" });

    await pool.query(
      `INSERT INTO group_members (group_id, sub, roles, alias, visibility)
       VALUES ($1, $2, $3, $4, $5)
       ON CONFLICT (group_id, sub)
       DO UPDATE SET roles = EXCLUDED.roles, alias = EXCLUDED.alias, visibility = EXCLUDED.visibility`,
      [groupId, sub, roles, alias, visibility],
    );
    return reply.code(201).send({ group_id: groupId, sub, roles, alias, visibility });
  });

  // Scope a resource (an app's item) to a group.
  fastify.post("/api/v1/groups/:id/resources", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    if (!(await isMember(groupId, claims.sub)))
      return reply.code(403).send({ error: "not a group member" });

    const body = (request.body ?? {}) as Record<string, any>;
    const app = typeof body.app === "string" ? body.app.trim() : "";
    const resourceKey = typeof body.resource_key === "string" ? body.resource_key.trim() : "";
    if (!app || !resourceKey) return reply.code(400).send({ error: "app and resource_key are required" });

    await pool.query(
      `INSERT INTO resource_scopes (group_id, app, resource_key, scoped_by)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (group_id, app, resource_key)
       DO UPDATE SET scoped_by = EXCLUDED.scoped_by, scoped_at = now()`,
      [groupId, app, resourceKey, claims.sub],
    );
    return reply.code(201).send({ group_id: groupId, app, resource_key: resourceKey });
  });

  // Scoped resources, readable by any group member.
  fastify.get("/api/v1/groups/:id/resources", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    if (!(await isMember(groupId, claims.sub)))
      return reply.code(403).send({ error: "not a group member" });

    const { rows } = await pool.query(
      `SELECT app, resource_key, scoped_by, scoped_at
       FROM resource_scopes WHERE group_id = $1 ORDER BY scoped_at DESC`,
      [groupId],
    );
    return reply.send(rows);
  });

  // Update group name/description/privacy.
  fastify.patch("/api/v1/groups/:id", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    if (!(await isOwner(groupId, claims.sub)))
      return reply.code(403).send({ error: "not a group owner" });

    const body = (request.body ?? {}) as Record<string, any>;
    const sets: string[] = [];
    const vals: any[] = [];
    if (typeof body.name === "string" && body.name.trim()) {
      sets.push(`name = $${vals.length + 1}`);
      vals.push(body.name.trim().slice(0, 120));
    }
    if (typeof body.description === "string") {
      sets.push(`description = $${vals.length + 1}`);
      vals.push(body.description.trim().slice(0, 500));
    }
    if (PRIVACY.includes(body.privacy)) {
      sets.push(`privacy = $${vals.length + 1}`);
      vals.push(body.privacy);
    }
    if (sets.length === 0) return reply.code(400).send({ error: "nothing to update" });

    vals.push(groupId);
    await pool.query(`UPDATE groups SET ${sets.join(", ")}, updated_at = now() WHERE id = $${vals.length}`, vals);
    const { rows } = await pool.query(
      `SELECT id, safe_address, name, description, privacy FROM groups WHERE id = $1`,
      [groupId],
    );
    return reply.send(rows[0]);
  });
}
