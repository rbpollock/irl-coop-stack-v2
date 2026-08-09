import type { FastifyInstance } from "fastify";
import { getProfile, upsertProfile } from "./profile-store";
import { verifyBearer } from "./verify-jwt";

export default async function onboardingRoutes(fastify: FastifyInstance): Promise<void> {
  // Whether the user has completed coop onboarding (mobile frontends reuse this).
  fastify.get("/api/auth/onboarding/status", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const profile = getProfile(claims.sub);
    return reply.send({ onboarded: profile?.onboarded ?? false, profile: profile ?? null });
  });

  // Finalize the coop profile: display name (required), avatar (optional).
  // The result is merged into the JWT on subsequent logins.
  fastify.post("/api/auth/onboarding", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    const body = (request.body ?? {}) as Record<string, any>;
    const displayName =
      typeof body.displayName === "string" && body.displayName.trim()
        ? body.displayName.trim().slice(0, 80)
        : null;
    const avatar =
      typeof body.avatar === "string" && body.avatar.trim() ? body.avatar.trim().slice(0, 500) : null;

    if (!displayName) {
      return reply.code(400).send({ error: "displayName is required" });
    }

    const profile = upsertProfile(claims.sub, {
      email: claims.email ?? null,
      displayName,
      avatar,
    });
    return reply.send({ onboarded: true, profile });
  });
}
