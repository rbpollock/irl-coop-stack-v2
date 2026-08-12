import type { FastifyInstance } from "fastify";

import { verifyBearer } from "./verify-jwt";
import { getAdminToken, getUserProfile, setUserCanonicalEmail } from "./keycloak-admin";

const USERNAME_RE = /^[a-z0-9][a-z0-9._-]{1,31}$/;
const RESERVED = new Set([
  "admin", "postmaster", "abuse", "noreply", "no-reply", "webmaster",
  "mailer-daemon", "root", "support", "info", "hostmaster", "dmarc",
]);

export default async function usernameRoutes(fastify: FastifyInstance): Promise<void> {
  // The caller's live canonical identity from Keycloak (the server truth —
  // the NextAuth session email is a login-time snapshot that can lag the
  // claimed @irl.coop address; the webmail gate reads THIS to decide whether
  // the username claim is still needed).
  fastify.get("/api/v1/me", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    try {
      const profile = await getUserProfile(claims.sub);
      return reply.send({ email: profile.email ?? null, sub: claims.sub });
    } catch (err) {
      fastify.log.error({ err: (err as Error).message }, "identity lookup failed");
      return reply.code(502).send({ error: "identity_lookup_failed" });
    }
  });

  // Claim the caller's canonical irl.coop username → their email becomes
  // <username>@irl.coop (the stalwart mailbox self-provisions on first auth
  // via the OIDC directory — the domain irl.coop already exists).
  fastify.post("/api/v1/me/username", async (request, reply) => {
    // The caller authenticates with the coop-api-issued JWT (what the
    // full-kit holds in its NextAuth session); sub is the Keycloak user id.
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    const body = (request.body ?? {}) as Record<string, unknown>;
    const username = typeof body.username === "string" ? body.username.trim().toLowerCase() : "";

    if (!USERNAME_RE.test(username) || RESERVED.has(username)) {
      return reply
        .code(400)
        .send({ error: "invalid_username", detail: "2-32 chars, lowercase letters, digits, . _ -" });
    }

    const email = `${username}@irl.coop`;
    try {
      const adminToken = await getAdminToken();
      const result = await setUserCanonicalEmail(adminToken, claims.sub, email);
      if (result === "taken") {
        return reply.code(409).send({ error: "username_taken", email });
      }
      return reply.send({ email, updated: result === "updated" });
    } catch (err) {
      fastify.log.error({ err: (err as Error).message }, "username claim failed");
      return reply.code(502).send({ error: "provisioning_failed" });
    }
  });
}
