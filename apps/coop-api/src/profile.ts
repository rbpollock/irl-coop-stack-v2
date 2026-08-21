import type { FastifyInstance } from "fastify";
import { getProfile } from "./profile-store";
import { verifyBearer } from "./verify-jwt";
import { withIdentity } from "./db";

// Full authenticated member profile: identity (from the coop JWT) + the coop
// profile (profiles table) + membership (RLS-scoped groups, incl. the personal
// Safe). A single aggregate for the dashboard's account/profile page — the
// caller supplies one bearer token and gets everything the profile needs.
export default async function profileRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.get("/api/v1/profile", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    const profile = await getProfile(claims.sub);

    const groups = await withIdentity(claims.sub, async (client) => {
      // "the user is their own group" — ensure the personal Safe exists.
      await client.query("SELECT coop_ensure_personal_group()");
      const { rows } = await client.query(
        `SELECT g.id, g.safe_address, g.name, g.privacy, g.kind, g.created_at,
                gm.roles
         FROM groups g
         LEFT JOIN group_members gm ON gm.group_id = g.id AND gm.sub = coop_current_sub()
         ORDER BY g.created_at ASC`,
      );
      return rows;
    });

    const personal = groups.find((g: any) => g.kind === "personal") ?? null;

    return reply.send({
      sub: claims.sub,
      email: profile?.email ?? claims.email ?? null,
      displayName: profile?.displayName ?? null,
      // Onboarded coop display name wins over the identity-provider name,
      // mirroring the merge in auth.ts mintCoopJwt().
      name: profile?.displayName ?? claims.name ?? null,
      avatar: profile?.avatar ?? claims.avatar ?? null,
      emailVerified: claims.email_verified ?? true,
      status: claims.status ?? "ONLINE",
      onboarded: profile?.onboarded ?? false,
      onboardedAt: profile?.onboardedAt ?? null,
      createdAt: profile?.createdAt ?? null,
      updatedAt: profile?.updatedAt ?? null,
      membership: {
        groupCount: groups.length,
        personalGroup: personal
          ? {
              id: personal.id,
              safe_address: personal.safe_address,
              name: personal.name,
            }
          : null,
        groups: groups.map((g: any) => ({
          id: g.id,
          safe_address: g.safe_address,
          name: g.name,
          privacy: g.privacy,
          kind: g.kind ?? null,
          roles: g.roles ?? [],
        })),
      },
    });
  });
}
