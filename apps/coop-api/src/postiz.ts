import { randomUUID } from "node:crypto";
import { Pool, PoolClient } from "pg";
import { getUserProfile } from "./keycloak-admin";

// Postiz DB (shared Citus, database `postiz`). The sync is a system consumer
// projecting groups into Postiz's Organization / UserOrganization / User tables.
// Deterministic link: the group's UUID IS the Postiz Organization id, so the
// resource_scopes row (group_id, 'postiz', group_id) is stable — no placeholder
// → org transition. Only the columns with NO DB default are set explicitly
// (verified against information_schema); Prisma sets the rest client-side.
const postizPool = new Pool({
  host: process.env.POSTIZ_DB_HOST ?? "172.17.0.1",
  port: Number(process.env.POSTIZ_DB_PORT ?? 5432),
  user: process.env.POSTIZ_DB_USER ?? "postiz",
  password: process.env.POSTIZ_DB_PASSWORD ?? process.env.POSTGRES_POSTIZ ?? "",
  database: process.env.POSTIZ_DB_NAME ?? "postiz",
  max: 3,
});

export type PostizSeat = { sub: string; roles: string[]; email: string | null };

// Collapse a seat's roles[] into one Postiz role (highest wins).
const ROLE_PRIORITY: Record<string, number> = {
  observer: 0,
  member: 1,
  inviter: 2,
  admin: 3,
  owner: 4,
};
const POSTIZ_ROLE: Record<string, string> = {
  owner: "SUPERADMIN",
  admin: "ADMIN",
  inviter: "INVITER",
  member: "USER",
  observer: "OBSERVER",
};

export function mapRoles(roles: string[]): string {
  let best = "member";
  let bestP = -1;
  for (const r of roles) {
    const p = ROLE_PRIORITY[r] ?? -1;
    if (p > bestP) {
      bestP = p;
      best = r;
    }
  }
  return POSTIZ_ROLE[best] ?? "USER";
}

async function resolveEmail(sub: string, profileEmail: string | null): Promise<string> {
  if (profileEmail) return profileEmail;
  try {
    const p = await getUserProfile(sub);
    return p.email ?? "";
  } catch (err) {
    if ((err as Error).message.includes("404")) return "";
    throw err; // transient → let Temporal retry
  }
}

async function ensureUser(client: PoolClient, sub: string, email: string): Promise<string> {
  const existing = await client.query(
    `SELECT id FROM "User" WHERE "providerId" = $1 AND "providerName" = 'GENERIC' LIMIT 1`,
    [sub],
  );
  if (existing.rows[0]) return existing.rows[0].id as string;

  const id = randomUUID();
  const created = await client.query(
    `INSERT INTO "User" (id, email, "providerName", "providerId", timezone, "updatedAt")
     VALUES ($1, $2, 'GENERIC', $3, 0, now())
     ON CONFLICT ("email", "providerName")
     DO UPDATE SET "providerId" = EXCLUDED."providerId", "updatedAt" = now()
     RETURNING id`,
    [id, email, sub],
  );
  return created.rows[0].id as string;
}

// Reconcile one group's Postiz org + membership. Convergent + idempotent:
// re-running reaches the same rows, so a missed event self-heals on the next
// sweep. Unseat = disabled=true (preserve history, revoke access).
export async function reconcileGroupPostiz(
  groupId: string,
  name: string,
  seats: PostizSeat[],
): Promise<void> {
  const client = await postizPool.connect();
  try {
    await client.query("BEGIN");

    await client.query(
      `INSERT INTO "Organization" (id, name, "updatedAt")
       VALUES ($1, $2, now())
       ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, "updatedAt" = now()`,
      [groupId, name],
    );

    const activeSubs: string[] = [];
    for (const s of seats) {
      const email = await resolveEmail(s.sub, s.email);
      if (!email) continue; // no canonical address yet → skip (next sweep seats them)
      const userId = await ensureUser(client, s.sub, email);
      activeSubs.push(s.sub);
      await client.query(
        `INSERT INTO "UserOrganization" (id, "userId", "organizationId", role, disabled, "updatedAt")
         VALUES ($1, $2, $3, $4, false, now())
         ON CONFLICT ("userId", "organizationId")
         DO UPDATE SET role = EXCLUDED.role, disabled = false, "updatedAt" = now()`,
        [randomUUID(), userId, groupId, mapRoles(s.roles)],
      );
    }

    // Unseat: disable any UserOrganization whose User is no longer a seat.
    // Empty activeSubs disables every OIDC-linked seat (group has no members).
    await client.query(
      `UPDATE "UserOrganization" uo
       SET disabled = true, "updatedAt" = now()
       WHERE uo."organizationId" = $1
         AND uo."userId" IN (
           SELECT id FROM "User" WHERE "providerId" IS NOT NULL AND "providerId" <> ALL($2::text[])
         )`,
      [groupId, activeSubs],
    );

    await client.query("COMMIT");
  } catch (err) {
    await client.query("ROLLBACK").catch(() => {});
    throw err;
  } finally {
    client.release();
  }
}

// --- Summary (for the dashboard's "Social Media" page) ---
//
// Postiz's analytics API is org-scoped behind its own cookie/JWT, so the
// dashboard reads org-level summaries straight from the Postiz DB (the shared
// Citus). orgId == groupId (the deterministic link), so the caller passes the
// group's UUID straight through.

export type PostizSummary = {
  group_id: string;
  group_name: string;
  org_id: string;
  total_posts: number;
  posts_by_state: { state: string; n: number }[];
  posts_by_day: { day: string; n: number }[];
  integrations: number;
  members: number;
  recent_posts: { id: string; content: string; state: string; created_at: string }[];
};

export async function summarizeOrg(
  groupId: string,
  groupName: string,
  orgId: string,
): Promise<PostizSummary> {
  const client = await postizPool.connect();
  try {
    const byState = await client.query(
      `SELECT state, count(*)::int AS n FROM "Post"
       WHERE "organizationId" = $1 AND "deletedAt" IS NULL GROUP BY state ORDER BY state`,
      [orgId],
    );
    const byDay = await client.query(
      `SELECT date_trunc('day', "createdAt")::date::text AS day, count(*)::int AS n
       FROM "Post" WHERE "organizationId" = $1 AND "deletedAt" IS NULL
         AND "createdAt" > now() - interval '30 days'
       GROUP BY 1 ORDER BY 1`,
      [orgId],
    );
    const integrations = await client.query(
      `SELECT count(*)::int AS n FROM "Integration"
       WHERE "organizationId" = $1 AND "deletedAt" IS NULL`,
      [orgId],
    );
    const members = await client.query(
      `SELECT count(*)::int AS n FROM "UserOrganization"
       WHERE "organizationId" = $1 AND disabled = false`,
      [orgId],
    );
    const recent = await client.query(
      `SELECT id, content, state, "createdAt" FROM "Post"
       WHERE "organizationId" = $1 AND "deletedAt" IS NULL
       ORDER BY "createdAt" DESC LIMIT 5`,
      [orgId],
    );
    const total = byState.rows.reduce((s: number, r: { n: number }) => s + r.n, 0);
    return {
      group_id: groupId,
      group_name: groupName,
      org_id: orgId,
      total_posts: total,
      posts_by_state: byState.rows,
      posts_by_day: byDay.rows,
      integrations: integrations.rows[0].n,
      members: members.rows[0].n,
      recent_posts: recent.rows.map((r) => ({
        id: r.id,
        content: String(r.content ?? "").slice(0, 120),
        state: r.state,
        created_at: r.createdAt,
      })),
    };
  } finally {
    client.release();
  }
}
