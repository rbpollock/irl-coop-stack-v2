import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";
import { withIdentity } from "./db";

// Decisions — the off-chain layer of Safe-governed voting (irl-coop-group.md §6).
// A proposal carries title, options, a quorum %, a deadline and an optional Safe
// transaction payload; members vote (EIP-1271 signature captured here), coop-api
// aggregates + tallies. On-chain execution + ConfidentialVoting.sol (Semaphore)
// private tallying are the next layer (specced, mocked in Phase 3). The "group
// apps" connect flow (postiz opt-in without owner) rides this: propose → quorum
// → execute the resource_scopes write.

type Proposal = {
  id: string;
  nonce: number;
  title: string;
  description: string | null;
  options: string[];
  quorum_pct: number;
  deadline: string | null;
  payload: unknown;
  proposer_sub: string;
  status: string;
  created_at: string;
};

export default async function decisionRoutes(fastify: FastifyInstance): Promise<void> {
  // Propose a decision (any member).
  fastify.post("/api/v1/groups/:id/decisions", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const body = (request.body ?? {}) as Record<string, any>;
    const title = typeof body.title === "string" ? body.title.trim().slice(0, 200) : "";
    const options = Array.isArray(body.options) ? body.options.map(String).slice(0, 20) : [];
    const quorumPct =
      typeof body.quorum_pct === "number" && body.quorum_pct > 0 && body.quorum_pct <= 100
        ? Math.round(body.quorum_pct)
        : 50;
    const deadline = typeof body.deadline === "string" ? body.deadline : null;
    const payload = body.payload ?? null;
    if (!title) return reply.code(400).send({ error: "title is required" });
    if (options.length === 0) return reply.code(400).send({ error: "options are required" });

    const result = await withIdentity(claims.sub, async (client) => {
      const m = await client.query(
        `SELECT 1 FROM group_members WHERE group_id = $1 AND sub = $2`,
        [groupId, claims.sub],
      );
      if ((m.rowCount ?? 0) === 0) return { forbidden: true };
      const { rows } = await client.query(
        `INSERT INTO proposals (group_id, nonce, title, description, options, quorum_pct, deadline, payload, proposer_sub)
         VALUES ($1, (SELECT COALESCE(MAX(nonce), 0) + 1 FROM proposals WHERE group_id = $1), $2, $3, $4::jsonb, $5, $6, $7::jsonb, $8)
         RETURNING id, nonce, title, description, options, quorum_pct, deadline, payload, proposer_sub, status, created_at`,
        [
          groupId,
          title,
          (body.description ?? null) as string | null,
          JSON.stringify(options),
          quorumPct,
          deadline,
          payload ? JSON.stringify(payload) : null,
          claims.sub,
        ],
      );
      return rows[0];
    });
    if ((result as any)?.forbidden) return reply.code(403).send({ error: "not a group member" });
    return reply.code(201).send(result);
  });

  // List the group's decisions (member).
  fastify.get("/api/v1/groups/:id/decisions", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const rows = await withIdentity(claims.sub, async (client) => {
      const m = await client.query(
        `SELECT 1 FROM group_members WHERE group_id = $1 AND sub = $2`,
        [groupId, claims.sub],
      );
      if ((m.rowCount ?? 0) === 0) return null;
      const { rows } = await client.query(
        `SELECT p.id, p.nonce, p.title, p.description, p.options, p.quorum_pct, p.deadline,
                p.payload, p.proposer_sub, p.status, p.created_at,
                (SELECT count(*)::int FROM votes v WHERE v.proposal_id = p.id) AS vote_count
         FROM proposals p WHERE p.group_id = $1 ORDER BY p.created_at DESC`,
        [groupId],
      );
      return rows;
    });
    if (rows === null) return reply.code(403).send({ error: "not a group member" });
    return reply.send(rows);
  });

  // Cast a vote (member; EIP-1271 signature captured, verified on-chain later).
  fastify.post("/api/v1/groups/:id/decisions/:vid/vote", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const vid = (request.params as any).vid;
    const body = (request.body ?? {}) as Record<string, any>;
    const choice = typeof body.choice === "string" ? body.choice : "";
    const signature = typeof body.signature === "string" ? body.signature : null;
    if (!choice) return reply.code(400).send({ error: "choice is required" });

    const result = await withIdentity(claims.sub, async (client) => {
      const m = await client.query(
        `SELECT 1 FROM group_members WHERE group_id = $1 AND sub = $2`,
        [groupId, claims.sub],
      );
      if ((m.rowCount ?? 0) === 0) return { forbidden: true };
      const p = await client.query(
        `SELECT status, deadline FROM proposals WHERE id = $1 AND group_id = $2`,
        [vid, groupId],
      );
      if ((p.rowCount ?? 0) === 0) return { not_found: true };
      const status: string = p.rows[0].status;
      const deadline: string | null = p.rows[0].deadline;
      if (status !== "open") return { closed: true, status };
      if (deadline && new Date(deadline) < new Date()) return { closed: true, status: "expired" };
      await client.query(
        `INSERT INTO votes (proposal_id, sub, choice, signature) VALUES ($1, $2, $3, $4)
         ON CONFLICT (proposal_id, sub) DO UPDATE SET choice = EXCLUDED.choice, signature = EXCLUDED.signature`,
        [vid, claims.sub, choice, signature],
      );
      return { ok: true };
    });
    if ((result as any)?.forbidden) return reply.code(403).send({ error: "not a group member" });
    if ((result as any)?.not_found) return reply.code(404).send({ error: "proposal not found" });
    if ((result as any)?.closed) return reply.code(409).send({ error: `proposal is ${(result as any).status}` });
    return reply.code(201).send({ proposal_id: vid, sub: claims.sub, choice });
  });

  // Tally a decision (member). Lazily converges open proposals to passed/failed.
  fastify.get("/api/v1/groups/:id/decisions/:vid", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const vid = (request.params as any).vid;
    const result = await withIdentity(claims.sub, async (client) => {
      const m = await client.query(
        `SELECT 1 FROM group_members WHERE group_id = $1 AND sub = $2`,
        [groupId, claims.sub],
      );
      if ((m.rowCount ?? 0) === 0) return { forbidden: true };
      const p = await client.query(
        `SELECT id, nonce, title, description, options, quorum_pct, deadline, payload, proposer_sub, status, created_at
         FROM proposals WHERE id = $1 AND group_id = $2`,
        [vid, groupId],
      );
      if ((p.rowCount ?? 0) === 0) return { not_found: true };
      const counts = await client.query(
        `SELECT choice, count(*)::int AS n FROM votes WHERE proposal_id = $1 GROUP BY choice ORDER BY choice`,
        [vid],
      );
      const total = await client.query(
        `SELECT count(*)::int AS n FROM group_members WHERE group_id = $1`,
        [groupId],
      );
      const proposal = p.rows[0] as Proposal;
      const tally: Record<string, number> = {};
      let voteCount = 0;
      for (const r of counts.rows) {
        tally[r.choice] = r.n;
        voteCount += r.n;
      }
      const memberCount = total.rows[0].n;
      const quorumMet = memberCount > 0 && (voteCount / memberCount) * 100 >= proposal.quorum_pct;
      const deadlinePassed = proposal.deadline ? new Date(proposal.deadline) < new Date() : false;

      // Lazy convergence: an open proposal settles once quorum is met, or fails
      // once its deadline lapses without quorum.
      let status = proposal.status;
      if (status === "open") {
        if (quorumMet) {
          status = "passed";
        } else if (deadlinePassed) {
          status = "failed";
        }
        if (status !== "open") {
          await client.query(`UPDATE proposals SET status = $2 WHERE id = $1`, [vid, status]);
        }
      }

      return {
        ...proposal,
        status,
        tally,
        vote_count: voteCount,
        member_count: memberCount,
        quorum_met: quorumMet,
      };
    });
    if ((result as any)?.forbidden) return reply.code(403).send({ error: "not a group member" });
    if ((result as any)?.not_found) return reply.code(404).send({ error: "proposal not found" });
    return reply.send(result);
  });
}
