import type { FastifyInstance } from "fastify";
import { pool, withIdentity } from "./db";
import { verifyBearer } from "./verify-jwt";
import { publishToUser } from "./notifications";
import { renderNotification } from "./render";

// The event store — raw, typed events as the bus's source of truth. Ingestion
// is a *system* write: the SQL function `coop_ingest_event` (SECURITY
// DEFINER, owned by coop_rls) resolves/creates the sender's personal group and
// inserts the event, bypassing RLS. Reads go through `withIdentity` so RLS
// scopes them to the caller's groups.
//
// On a successful insert we fan the rendered notification out to the sender's
// own channel (irl:notify:{sub}) — the live lane. The durable lane is the
// Temporal deliverySweep (see temporal/), which claims rows by delivered_at.
// Room→recipient targeting (notify the OTHER room members) is the next
// increment and needs the room→group mapping (resource_scopes).

export async function ingestEvent(
  sub: string,
  source: string,
  sourceEventId: string | null,
  type: string,
  payload: Record<string, unknown>,
  occurredAt: number,
): Promise<string | null> {
  const r = await pool.query(
    `SELECT coop_ingest_event($1, $2, $3, $4, $5::jsonb, $6::timestamptz) AS id`,
    [sub, source, sourceEventId, type, JSON.stringify(payload), new Date(occurredAt)],
  );
  const id = r.rows[0]?.id ?? null;

  // Live-lane fan-out (best-effort): the event store above is the durable copy,
  // so a missed PUBLISH is recovered by the poll/SSE replay, never lost.
  if (id) {
    void publishToUser(
      sub,
      renderNotification({
        id,
        type,
        payload,
        occurred_at: new Date(occurredAt).toISOString(),
      }),
    );
  }
  return id;
}

// Group-targeted ingest: the activity belongs to a GROUP (a group workspace's
// ticket sales), not to a person, so it lands on the group's stream — RLS then
// shows it to every member. The slug→group resolution happens inside the
// SECURITY DEFINER function (groups is RLS-forced; a system source is not a
// member). Returns the event id + the resolved group id.
export async function ingestGroupEvent(
  groupRef: string,
  source: string,
  sourceEventId: string | null,
  type: string,
  payload: Record<string, unknown>,
  occurredAt: number,
): Promise<{ id: string | null; group_id: string | null }> {
  const r = await pool.query<{ id: string | null; group_id: string | null }>(
    `SELECT id, group_id FROM coop_ingest_group_event($1, $2, $3, $4, $5::jsonb, $6::timestamptz)`,
    [groupRef, source, sourceEventId, type, JSON.stringify(payload), new Date(occurredAt)],
  );
  return r.rows[0] ?? { id: null, group_id: null };
}

// Group members (system-level read, BYPASSRLS as coop_rls) — the live-lane
// fan-out target list. Targeting resolves server-side, never from the client.
export async function groupMemberSubs(groupId: string): Promise<string[]> {
  const r = await pool.query<{ coop_group_member_subs: string }>(
    `SELECT coop_group_member_subs($1)`,
    [groupId],
  );
  return r.rows.map((row) => row.coop_group_member_subs);
}

export default async function eventRoutes(fastify: FastifyInstance): Promise<void> {
  // The caller's groups' events (RLS filters to what their sub may see).
  fastify.get("/api/v1/events", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const limit = Math.min(Number((request.query as any)?.limit) || 100, 500);
    const rows = await withIdentity(claims.sub, async (client) => {
      const { rows } = await client.query(
        `SELECT id, group_id, source, type, payload, occurred_at
         FROM events ORDER BY occurred_at DESC LIMIT $1`,
        [limit],
      );
      return rows;
    });
    return reply.send(rows);
  });
}
