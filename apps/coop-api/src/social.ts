import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";
import { withIdentity } from "./db";
import { summarizeOrg } from "./postiz";

// Social Media dashboard summary — for each group the caller is a member of
// that has opted into Postiz (a resource_scopes row app='postiz'), read the
// org-level summary straight from the Postiz DB (posts by state/day,
// integrations, members, recent posts). The group UUID is the Postiz org id.
export default async function socialRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get("/api/v1/social/summary", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    const opted = await withIdentity(claims.sub, async (client) => {
      const { rows } = await client.query(
        `SELECT g.id AS group_id, g.name AS group_name, rs.resource_key AS org_id
         FROM groups g
         JOIN resource_scopes rs ON rs.group_id = g.id AND rs.app = 'postiz'
         WHERE EXISTS (
           SELECT 1 FROM group_members gm WHERE gm.group_id = g.id AND gm.sub = coop_current_sub()
         )
         ORDER BY g.created_at`,
      );
      return rows;
    });

    const summaries = [];
    for (const g of opted) {
      summaries.push(await summarizeOrg(g.group_id, g.group_name, g.org_id));
    }
    return reply.send(summaries);
  });
}
