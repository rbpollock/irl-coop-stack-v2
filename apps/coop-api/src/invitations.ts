import type { FastifyInstance } from "fastify";
import type { PoolClient } from "pg";
import { randomBytes } from "node:crypto";
import { verifyBearer } from "./verify-jwt";
import { withIdentity } from "./db";
import { signInvite, verifyInvite } from "./invite-token.mjs";

// ---------------------------------------------------------------------------
// Invitations — the "thing passed" (a tie). Owner offers a signed one-time token
// to a canonical email; the invitee redeems it to accept — and if member_offer is
// set, redemption seats them as an owner (the Safe). Single-use + expiry enforced
// in Postgres (coop_invite_redeem). FORCE RLS: cooper row is only creatable/
// readable by the inviter or an owner.
// ---------------------------------------------------------------------------

const DAYS = 14;
function inviteSecret(): string | null {
  return process.env.INVITE_SIGNING_SECRET ?? null;
}

async function isOwner(client: PoolClient, groupId: string, sub: string): Promise<boolean> {
  const r = await client.query(
    `SELECT 1 FROM group_members WHERE group_id = $1 AND sub = $2 AND 'owner' = ANY(roles)`,
    [groupId, sub],
  );
  return (r.rowCount ?? 0) > 0;
}

export default async function invitationRoutes(fastify: FastifyInstance): Promise<void> {
  // Create a tie from this group to a person (by canonical email).
  fastify.post("/api/v1/groups/:id/invitations", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const secret = inviteSecret();
    if (!secret) {
      return reply
        .code(503)
        .send({ error: "INVITE_SIGNING_SECRET not configured — invitations disabled" });
    }
    const groupId = (request.params as any).id;
    const body = (request.body ?? {}) as Record<string, any>;
    const toEmail = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
    if (!toEmail || !toEmail.includes("@")) {
      return reply.code(400).send({ error: "email is required" });
    }
    const memberOffer = body.member_offer === true;
    const roles = Array.isArray(body.roles) ? body.roles.map(String) : ["member"];
    const subject = typeof body.subject === "string" ? body.subject.trim() || null : null;
    const subjectRef = typeof body.subject_ref === "string" ? body.subject_ref.trim() || null : null;
    const expiresAt =
      typeof body.expires_at === "string" && !Number.isNaN(Date.parse(body.expires_at))
        ? new Date(body.expires_at)
        : new Date(Date.now() + DAYS * 24 * 60 * 60 * 1000);

    const outcome = await withIdentity(claims.sub, async (client) => {
      if (!(await isOwner(client, groupId, claims.sub))) return "forbidden" as const;
      const id = randomBytes(16).toString("hex");
      const nonce = randomBytes(16).toString("hex");
      await client.query(
        `INSERT INTO invitations
           (id, group_id, to_email, subject, subject_ref, member_offer, roles, nonce, expires_at, created_by)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
        [id, groupId, toEmail, subject, subjectRef, memberOffer, roles, nonce, expiresAt, claims.sub],
      );
      const token = signInvite({ id, email: toEmail, exp: Math.floor(expiresAt.getTime() / 1000) }, secret);
      return { id, token };
    });

    if (outcome === "forbidden") return reply.code(403).send({ error: "not a group owner" });
    return reply.code(201).send({ group_id: groupId, invitation_id: outcome.id, token: outcome.token });
  });

  // The inviter's open ties under a group (owner list).
  fastify.get("/api/v1/groups/:id/invitations", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const ok = await withIdentity(claims.sub, async (client) => isOwner(client, groupId, claims.sub));
    if (!ok) return reply.code(403).send({ error: "not a group owner" });
    const { rows } = await withIdentity(claims.sub, (client) =>
      client.query(
        `SELECT id, to_email, subject, subject_ref, member_offer, roles, status, expires_at, created_at
           FROM invitations WHERE group_id = $1 AND created_by = $2 ORDER BY created_at DESC`,
        [groupId, claims.sub],
      ),
    );
    return reply.send({ invitations: rows });
  });

  // Redeem a signed token (accept a tie). Email in the token must equal the
  // caller's canonical identity; state transitions happen in Postgres.
  fastify.post("/api/v1/invitations/:id/redeem", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const id = (request.params as any).id;
    const secret = inviteSecret();
    if (!secret) return reply.code(503).send({ error: "INVITE_SIGNING_SECRET not set" });
    const token = String((request.body ?? ({} as any)).token ?? "").trim();
    const good = verifyInvite(token, secret);
    if (!good || good.id !== id || good.email !== String(claims.email ?? "").toLowerCase()) {
      return reply.code(403).send({ error: "token does not name you" });
    }
    const result = await withIdentity(claims.sub, (client) =>
      client.query("SELECT coop_invite_redeem($1::uuid, $2) AS r", [id, claims.sub]),
    );
    const out = result.rows[0]?.out ?? "error";
    if (out === "missing" || out === "not-pending") return reply.code(409).send({ error: out });
    return reply.send({ accepted: out });
  });
}