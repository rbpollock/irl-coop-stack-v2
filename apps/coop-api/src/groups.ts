import type { FastifyInstance } from "fastify";
import { randomBytes } from "node:crypto";
import { ethers } from "ethers";
import type { PoolClient } from "pg";
import { verifyBearer } from "./verify-jwt";
import { verifySessionRequest, sessionFromRequest } from "./auth";
import { deploySafe } from "./safe";
import { withIdentity, pool } from "./db";
import { slugify, isValidSlug, RESERVED_SLUGS } from "./slug";

// ---------------------------------------------------------------------------
// Groups = Safes (Layer-2 projection). A group IS a Safe: "create a group"
// wraps the existing Safe deployment (safe.ts) and records a projection row.
// Row-level security lives in Postgres (infra/compose/storage/scripts/coop_rls.sql):
// every request runs in a transaction with `app.sub` set (withIdentity), and RLS
// filters groups/members/scopes to what that sub may see. Members are seats
// (sub + roles + alias + visibility).
// ---------------------------------------------------------------------------

const PRIVACY = ["open", "members", "hidden"] as const;
const VISIBILITY = ["role-only", "alias", "canonical"] as const;

function safeEnv(): { factory: string; singleton: string; backendKey: string } | null {
  const factory = process.env.SAFE_PROXY_FACTORY_ADDRESS ?? "";
  const singleton = process.env.SAFE_SINGLETON_ADDRESS ?? "";
  const backendKey = process.env.SAFE_BACKEND_SIGNER_KEY ?? "";
  return factory && singleton && backendKey ? { factory, singleton, backendKey } : null;
}

// Groups get a UNIQUE salt (random), unlike the personal account Safe whose
// salt is deterministic (sub-derived) so its address is predictable pre-deploy.
function freshSalt(): bigint {
  return BigInt("0x" + randomBytes(32).toString("hex"));
}

async function isOwner(client: PoolClient, groupId: string, sub: string): Promise<boolean> {
  const r = await client.query(
    `SELECT 1 FROM group_members WHERE group_id = $1 AND sub = $2 AND 'owner' = ANY(roles)`,
    [groupId, sub],
  );
  return (r.rowCount ?? 0) > 0;
}

async function isMember(client: PoolClient, groupId: string, sub: string): Promise<boolean> {
  const r = await client.query(
    `SELECT 1 FROM group_members WHERE group_id = $1 AND sub = $2`,
    [groupId, sub],
  );
  return (r.rowCount ?? 0) > 0;
}

// Privacy-blind slug occupancy: whether ANY group holds this slug, regardless
// of privacy tier (a members/hidden group's slug is still un-takeable). Runs
// through the SECURITY DEFINER coop_slug_taken (BYPASSRLS), not an RLS read.
async function slugTaken(slug: string): Promise<boolean> {
  const r = await pool.query<{ coop_slug_taken: boolean }>(
    "SELECT coop_slug_taken($1)",
    [slug],
  );
  return r.rows[0]?.coop_slug_taken ?? false;
}

// Host → slug: strip port, drop the .irl.coop suffix, take the last remaining
// label. `acme.irl.coop` → `acme`; `events.acme.irl.coop` → `acme`. Anything
// else (webstudio canvas p-*.studio, infra hosts) yields a reserved label or
// nonsense that simply resolves to no group.
function hostToSlug(host: string): string {
  const h = (host ?? "").split(":")[0].toLowerCase().trim();
  return (h.replace(/\.irl\.coop$/, "").split(".").pop() ?? "").toLowerCase();
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

    // Canonical slug: an explicit canonical slug, or derived from the name
    // (lowercase, spaces + special chars stripped). Duplicates are rejected up
    // front (coop_slug_taken) and enforced by groups_slug_uniq as the
    // race-safe backstop — so we check BEFORE deploying the Safe (no orphan).
    let slug: string;
    if (body.slug !== undefined) {
      const s = typeof body.slug === "string" ? body.slug.trim().toLowerCase() : "";
      if (!isValidSlug(s)) {
        return reply.code(400).send({ error: "slug must be lowercase letters/numbers/hyphens and not reserved" });
      }
      slug = s;
    } else {
      slug = slugify(name);
      if (!slug) {
        return reply.code(400).send({ error: "could not derive a slug from the name — provide a slug" });
      }
      if (RESERVED_SLUGS.has(slug)) {
        return reply.code(409).send({ error: "slug is reserved", slug });
      }
    }
    if (await slugTaken(slug)) {
      return reply
        .code(409)
        .send({ error: "slug already taken", slug, suggestion: `${slug}-${Math.floor(1000 + Math.random() * 9000)}` });
    }

    let saltNonce: bigint;
    try {
      saltNonce =
        typeof body.saltNonce === "string" && body.saltNonce
          ? BigInt(body.saltNonce)
          : freshSalt();
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

      const result = await withIdentity(claims.sub, async (client) => {
        const group = await client.query(
          `INSERT INTO groups (safe_address, name, slug, privacy, created_by) VALUES ($1, $2, $3, $4, $5)
           RETURNING id, safe_address, name, slug, description, privacy, created_at`,
          [safeAddress, name, slug, privacy, claims.sub],
        );
        const row = group.rows[0];
        await client.query(
          `INSERT INTO group_members (group_id, sub, roles, visibility) VALUES ($1, $2, $3, 'canonical')`,
          [row.id, claims.sub, ["owner"]],
        );
        return row;
      });

      return reply.code(201).send({ ...result, tx_hash: txHash, seat: { roles: ["owner"] } });
    } catch (err: any) {
      // Race backstop: groups_slug_uniq is authoritative. A concurrent create
      // that wins the slug surfaces here (the Safe was already deployed — an
      // orphan, but the slug is what matters and it is now taken).
      if (err?.code === "23505" && String(err?.constraint ?? "").includes("slug")) {
        return reply
          .code(409)
          .send({ error: "slug already taken", slug, suggestion: `${slug}-${Math.floor(1000 + Math.random() * 9000)}` });
      }
      request.log.error({ err: err.message }, "group deploy failed");
      return reply.code(500).send({ error: err.message });
    }
  });

  // Groups I can see (RLS filters them), with my seat.
  fastify.get("/api/v1/groups", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const rows = await withIdentity(claims.sub, async (client) => {
      // "the user is their own group" — ensure the caller's personal group exists
      await client.query("SELECT coop_ensure_personal_group()");
      const { rows } = await client.query(
        `SELECT g.id, g.safe_address, g.name, g.description, g.privacy, g.kind, g.created_at,
                gm.roles, gm.alias, gm.visibility
         FROM groups g
         LEFT JOIN group_members gm ON gm.group_id = g.id AND gm.sub = coop_current_sub()
         ORDER BY g.created_at DESC`,
      );
      return rows;
    });
    return reply.send(rows);
  });

  // Session-authenticated group read for browser-served surfaces (the published
  // group sites at {groupname}.irl.coop). Same RLS-scoped query as the bearer
  // endpoint, but authenticated by the coop_session cookie instead of a Bearer
  // header (a static site has the cookie, not a token).
  fastify.get("/api/v1/site/groups", async (request, reply) => {
    const claims = verifySessionRequest(request, reply);
    if (!claims) return;
    const rows = await withIdentity(claims.sub, async (client) => {
      await client.query("SELECT coop_ensure_personal_group()");
      const { rows } = await client.query(
        `SELECT g.id, g.safe_address, g.name, g.description, g.privacy, g.kind, g.created_at,
                gm.roles, gm.alias, gm.visibility
         FROM groups g
         LEFT JOIN group_members gm ON gm.group_id = g.id AND gm.sub = coop_current_sub()
         ORDER BY g.created_at DESC`,
      );
      return rows;
    });
    return reply.send(rows);
  });

  // Slug availability — privacy-blind (coop_slug_taken, SECURITY DEFINER) so a
  // members/hidden group's slug is still un-takeable. Unauthenticated: the UI
  // checks while the user types; it reveals only whether the slug is free, never
  // which group holds it.
  fastify.get("/api/v1/slugs/:slug/available", async (request, reply) => {
    const slug = ((request.params as any).slug ?? "").toLowerCase();
    if (!isValidSlug(slug)) return reply.send({ slug, available: false });
    const available = !(await slugTaken(slug));
    return reply.send({ slug, available });
  });

  // Host → group resolver for the published group sites at {slug}.irl.coop.
  // Anonymous callers resolve only `open` groups (the plain pool read is RLS-
  // filtered to privacy='open'); a session cookie additionally resolves groups
  // the caller can view (members/hidden for a member). Accepts ?host= or ?slug=.
  fastify.get("/api/v1/resolve", async (request, reply) => {
    const q = request.query as Record<string, string | undefined>;
    const slug = (q.slug ?? hostToSlug(q.host ?? "")).toLowerCase();
    if (!slug) return reply.code(400).send({ error: "slug or host required" });

    const cols = "id, slug, name, kind, privacy, safe_address";
    const session = sessionFromRequest(request);
    const row = session
      ? await withIdentity(session.sub, async (client) => {
          const { rows } = await client.query(
            `SELECT ${cols} FROM groups WHERE slug = $1`,
            [slug],
          );
          return rows[0] ?? null;
        })
      : ((await pool.query(`SELECT ${cols} FROM groups WHERE slug = $1 AND privacy = 'open'`, [slug])).rows[0] ?? null);

    if (!row) return reply.code(404).send({ error: "no_group" });
    return reply.send(row);
  });

  // Invite / seat a member in a group.
  fastify.post("/api/v1/groups/:id/members", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const body = (request.body ?? {}) as Record<string, any>;
    const sub = typeof body.sub === "string" ? body.sub.trim() : "";
    const roles = Array.isArray(body.roles) ? body.roles.map(String) : [];
    const alias = typeof body.alias === "string" ? body.alias.trim().slice(0, 80) : null;
    const visibility = VISIBILITY.includes(body.visibility) ? body.visibility : "canonical";
    if (!sub) return reply.code(400).send({ error: "sub is required" });

    const ok = await withIdentity(claims.sub, async (client) => {
      if (!(await isOwner(client, groupId, claims.sub))) return false;
      await client.query(
        `INSERT INTO group_members (group_id, sub, roles, alias, visibility)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (group_id, sub)
         DO UPDATE SET roles = EXCLUDED.roles, alias = EXCLUDED.alias, visibility = EXCLUDED.visibility`,
        [groupId, sub, roles, alias, visibility],
      );
      return true;
    });
    if (!ok) return reply.code(403).send({ error: "not a group owner" });
    return reply.code(201).send({ group_id: groupId, sub, roles, alias, visibility });
  });

  // Seat roster — members can see who else is seated. The group management
  // page reads this for the members table (membership is the gate).
  fastify.get("/api/v1/groups/:id/members", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const rows = await withIdentity(claims.sub, async (client) => {
      if (!(await isMember(client, groupId, claims.sub))) return null;
      const { rows } = await client.query(
        `SELECT sub, roles, alias, visibility, created_at
         FROM group_members WHERE group_id = $1 ORDER BY created_at ASC`,
        [groupId],
      );
      return rows;
    });
    if (rows === null) return reply.code(403).send({ error: "not a group member" });
    return reply.send(rows);
  });

  // Scope a resource (an app's item) to a group.
  fastify.post("/api/v1/groups/:id/resources", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const body = (request.body ?? {}) as Record<string, any>;
    const app = typeof body.app === "string" ? body.app.trim() : "";
    const resourceKey = typeof body.resource_key === "string" ? body.resource_key.trim() : "";
    if (!app || !resourceKey) return reply.code(400).send({ error: "app and resource_key are required" });

    const ok = await withIdentity(claims.sub, async (client) => {
      if (!(await isMember(client, groupId, claims.sub))) return false;
      await client.query(
        `INSERT INTO resource_scopes (group_id, app, resource_key, scoped_by)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT (group_id, app, resource_key)
         DO UPDATE SET scoped_by = EXCLUDED.scoped_by, scoped_at = now()`,
        [groupId, app, resourceKey, claims.sub],
      );
      return true;
    });
    if (!ok) return reply.code(403).send({ error: "not a group member" });
    return reply.code(201).send({ group_id: groupId, app, resource_key: resourceKey });
  });

  // Scoped resources (RLS filters to groups I can see).
  fastify.get("/api/v1/groups/:id/resources", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const rows = await withIdentity(claims.sub, async (client) => {
      const { rows } = await client.query(
        `SELECT app, resource_key, scoped_by, scoped_at
         FROM resource_scopes WHERE group_id = $1 ORDER BY scoped_at DESC`,
        [groupId],
      );
      return rows;
    });
    return reply.send(rows);
  });

  // Update group name/description/privacy.
  fastify.patch("/api/v1/groups/:id", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
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
    if (body.slug !== undefined) {
      const s = typeof body.slug === "string" ? body.slug.trim().toLowerCase() : "";
      if (!isValidSlug(s)) {
        return reply.code(400).send({ error: "slug must be lowercase letters/numbers/hyphens and not reserved" });
      }
      if (await slugTaken(s)) {
        return reply.code(409).send({ error: "slug already taken", slug: s });
      }
      sets.push(`slug = $${vals.length + 1}`);
      vals.push(s);
    }
    if (sets.length === 0) return reply.code(400).send({ error: "nothing to update" });

    let row: any = null;
    try {
      row = await withIdentity(claims.sub, async (client) => {
        if (!(await isOwner(client, groupId, claims.sub))) return null;
        vals.push(groupId);
        await client.query(
          `UPDATE groups SET ${sets.join(", ")}, updated_at = now() WHERE id = $${vals.length}`,
          vals,
        );
        const { rows } = await client.query(
          `SELECT id, safe_address, name, slug, description, privacy FROM groups WHERE id = $1`,
          [groupId],
        );
        return rows[0] ?? null;
      });
    } catch (err: any) {
      // Race backstop: a concurrent re-slug that wins surfaces as 23505.
      if (err?.code === "23505" && String(err?.constraint ?? "").includes("slug")) {
        return reply.code(409).send({ error: "slug already taken" });
      }
      throw err;
    }
    if (!row) return reply.code(403).send({ error: "not a group owner" });
    return reply.send(row);
  });
}
