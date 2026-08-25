// Server-to-server groups lookup for the Keycloak `groups` protocol mapper.
//
// Keycloak's built-in `groups` scope maps its own group model — but the coop
// group model lives in coop-api, not Keycloak. The CoopGroupsMapper (Keycloak
// SPI JAR) calls this endpoint on token mint, authenticated with the shared
// KEYCLOAK_GROUPS_TOKEN, and emits the result as the OIDC `groups` claim.
// coop-api stays the source of truth; Keycloak fetches live (Path A).
//
// `groups` = the user's RELATED GROUPS (the functional group concept, NOT
// permissions): their own 1-of-1 group plus every group they hold a seat in —
// identified by group id (uuid). Emitted as a list of strings.
import type { FastifyInstance } from "fastify";
import { getRelatedGroups } from "./db";

const TOKEN = process.env.KEYCLOAK_GROUPS_TOKEN ?? "";

export default async function internalRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get("/api/internal/groups", async (request, reply) => {
    const auth = request.headers.authorization ?? "";
    if (!TOKEN || auth !== `Bearer ${TOKEN}`) {
      return reply.code(401).send({ error: "unauthorized" });
    }
    const sub = (request.query as Record<string, string | undefined>).sub;
    if (!sub) {
      return reply.code(400).send({ error: "sub required" });
    }
    try {
      const groups = await getRelatedGroups(sub);
      return { groups };
    } catch (err) {
      request.log.error({ err }, "groups lookup failed");
      return reply.code(500).send({ error: "lookup failed" });
    }
  });
}
