import Redis from "ioredis";
import type { FastifyInstance } from "fastify";
import { withIdentity } from "./db";
import { verifyBearer } from "./verify-jwt";
import { renderNotification, type Notification } from "./render";

// The live lane of the event bus: Redis fan-out (irl:notify:{sub}) -> SSE ->
// dashboard. Auth is at THIS edge (bearer coop JWT); the server then subscribes
// to the caller's OWN channel, so a client can only ever receive its own
// notifications. Redis stays on the internal docker net.
//
// This lane is deliberately best-effort. The durable lane is the Postgres event
// store + the Temporal deliverySweep (see temporal/); a missed PUBLISH is
// recovered by the poll endpoint below, never lost.
//
// Read-state lives in `notification_reads` (user_sub, event_id, read_at,
// cleared_at). A notification is "answered" once it has a read_at OR a
// cleared_at; "unanswered" feeds both the unread badge and the digest.

const REDIS_URL = process.env.REDIS_URL ?? "redis://172.17.0.1:6379";

let redis: Redis | null = null;
export function getRedis(): Redis {
  if (!redis) redis = new Redis(REDIS_URL, { maxRetriesPerRequest: 1 });
  return redis;
}

export const notifyChannel = (sub: string): string => `irl:notify:${sub}`;

// Server-side fan-out to ONE user's channel. Group/role targeting resolves here
// (where it can't be spoofed) before publishing to each eligible member.
export async function publishToUser(sub: string, n: Notification): Promise<void> {
  try {
    await getRedis().publish(notifyChannel(sub), JSON.stringify(n));
  } catch {
    // fire-and-forget: the event store is the durable copy; poll + SSE replay
    // close the gap, so a missed PUBLISH is not a lost event.
  }
}

async function recentNotifications(sub: string, limit: number): Promise<Notification[]> {
  return withIdentity(sub, async (client) => {
    const { rows } = await client.query(
      `SELECT e.id, e.source, e.type, e.payload, e.occurred_at,
              (nr.read_at IS NOT NULL OR nr.cleared_at IS NOT NULL) AS read
         FROM events e
         LEFT JOIN notification_reads nr
           ON nr.event_id = e.id AND nr.user_sub = $1
        ORDER BY e.occurred_at DESC LIMIT $2`,
      [sub, limit],
    );
    return rows.map((r) => ({ ...renderNotification(r), read: Boolean(r.read) }));
  });
}

export default async function notificationRoutes(fastify: FastifyInstance): Promise<void> {
  // Poll fallback + initial load: recent notifications, RLS-scoped to the caller.
  fastify.get("/api/v1/notifications", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const limit = Math.min(Number((request.query as any)?.limit) || 50, 200);
    return reply.send(await recentNotifications(claims.sub as string, limit));
  });

  // Mark one or more notifications read. Body: { event_ids: string[] }.
  // Read-state is user-scoped (RLS: user_sub = caller), so this can only ever
  // mark the caller's own rows — never another user's.
  fastify.post("/api/v1/notifications/read", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const sub = claims.sub as string;
    const body = (request.body ?? {}) as { event_ids?: unknown };
    const ids = Array.isArray(body.event_ids) ? body.event_ids.filter((x) => typeof x === "string") : [];
    if (ids.length === 0) {
      return reply.code(400).send({ error: "event_ids required" });
    }
    await withIdentity(sub, async (client) => {
      for (const id of ids) {
        await client.query(
          `INSERT INTO notification_reads (user_sub, event_id, read_at)
           VALUES ($1, $2, now())
           ON CONFLICT (user_sub, event_id) DO UPDATE SET read_at = now()`,
          [sub, id],
        );
      }
    });
    return reply.send({ ok: true, read: ids.length });
  });

  // Clear all current notifications (mark every visible event cleared). This is
  // "dismiss all": a snapshot of the caller's events, each stamped cleared_at.
  fastify.post("/api/v1/notifications/clear", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const sub = claims.sub as string;
    const count = await withIdentity(sub, async (client) => {
      const { rows } = await client.query(
        `INSERT INTO notification_reads (user_sub, event_id, cleared_at)
         SELECT $1, e.id, now()
           FROM events e
         ON CONFLICT (user_sub, event_id) DO UPDATE SET cleared_at = now()
         RETURNING 1`,
        [sub],
      );
      return rows.length;
    });
    return reply.send({ ok: true, cleared: count });
  });

  // Live lane (SSE). No replay here — the poll endpoint above is the replay/
  // catch-up; this keeps history vs live cleanly separated on the client.
  fastify.get("/api/v1/notifications/stream", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const sub = claims.sub as string;

    reply.hijack();
    const res = reply.raw;
    // hijack() bypasses Fastify's onSend hooks (incl. the cors plugin), so set
    // the CORS headers this response needs manually (bearer-token auth, no
    // cookies — echoing the request Origin is fine).
    const origin = request.headers.origin;
    if (origin) {
      res.setHeader("Access-Control-Allow-Origin", origin);
      res.setHeader("Vary", "Origin");
    }
    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    });
    res.write("retry: 5000\n\n");

    const subscriber = new Redis(REDIS_URL);
    await subscriber.subscribe(notifyChannel(sub));
    subscriber.on("message", (_channel, msg) => {
      try {
        const n = JSON.parse(msg) as Notification;
        res.write(`data: ${JSON.stringify(n)}\n\n`);
      } catch {
        /* malformed publish — skip */
      }
    });

    const hb = setInterval(() => res.write(": keepalive\n\n"), 15000);
    const cleanup = () => {
      clearInterval(hb);
      subscriber.unsubscribe(notifyChannel(sub)).catch(() => {});
      subscriber.quit().catch(() => {});
      res.end();
    };
    request.raw.on("close", cleanup);
    res.on("error", cleanup);
  });
}
