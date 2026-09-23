import { FastifyInstance } from "fastify";
import { withIdentity } from "./db";
import { verifyBearer } from "./verify-jwt";

// Matrix Custom Room State / Widget Integration for Livestreams (`m.room.livestream`)
export default async function livestreamStateRoutes(fastify: FastifyInstance): Promise<void> {
  // Set or update live stream state on a group / room mapping
  fastify.post("/api/v1/groups/:id/livestream", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const body = (request.body ?? {}) as Record<string, any>;
    const streamPath = typeof body.stream_path === "string" ? body.stream_path.trim() : "";
    const active = Boolean(body.active);

    if (!streamPath) {
      return reply.code(400).send({ error: "stream_path is required" });
    }

    const updated = await withIdentity(claims.sub, async (client) => {
      // Record active livestream state in resource scopes or a dedicated livestream table
      await client.query(
        `INSERT INTO resource_scopes (group_id, app, resource_key, scoped_by)
         VALUES ($1, 'livestream', $2, $3)
         ON CONFLICT (group_id, app, resource_key)
         DO UPDATE SET scoped_by = EXCLUDED.scoped_by, scoped_at = now()`,
        [groupId, streamPath, claims.sub],
      );
      return { group_id: groupId, stream_path: streamPath, active };
    });

    return reply.code(200).send(updated);
  });
}
