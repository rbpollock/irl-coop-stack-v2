import Redis from "ioredis";
import type { FastifyInstance } from "fastify";
import { getUserByEmail } from "./keycloak-admin";
import { ingestEvent } from "./events";

// Matrix appservice — Synapse pushes transaction batches here (event metadata
// for every room event). Auth is the appservice `hs_token` (Bearer), NOT a
// coop JWT. See docs/design/matrix-chat-and-notifications.md.
//
// Each relevant event is fanned two ways:
//   1. Redis `irl:communication:events` — the *domain* firehose. `source` is
//      metadata (the channel name carries no app/source, which churn often).
//   2. The Postgres event store (coop_ingest_event), scoped to the sender's
//      personal group so RLS can filter reads.

const REDIS_URL = process.env.REDIS_URL ?? "redis://172.17.0.1:6379";
const FIREHOSE = "irl:communication:events";

// Persistent room events worth a notification; ephemeral (receipts, typing,
// presence) are dropped.
const RELEVANT = new Set([
  "m.room.message",
  "m.room.encrypted",
  "m.room.member",
  "m.reaction",
  "m.room.name",
  "m.room.topic",
  "m.room.create",
]);

let redis: Redis | null = null;
function getRedis(): Redis {
  if (!redis) redis = new Redis(REDIS_URL, { maxRetriesPerRequest: 1 });
  return redis;
}

type MatrixEvent = {
  type: string;
  event_id?: string;
  sender?: string;
  room_id?: string;
  origin_server_ts?: number;
  content?: Record<string, unknown>;
};

export default async function matrixAppserviceRoutes(
  fastify: FastifyInstance,
): Promise<void> {
  const handle = async (request: any, reply: any) => {
    // Synapse authenticates the HS→AS push with the *hs_token* (not as_token —
    // as_token is for AS→HS API calls). See the appservice spec.
    const hsToken = process.env.MATRIX_HS_TOKEN ?? "";
    const auth = String(request.headers.authorization ?? "");
    const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    if (!hsToken || token !== hsToken) {
      return reply
        .code(401)
        .send({ errcode: "M_FORBIDDEN", error: "invalid hs_token" });
    }

    const body = (request.body ?? {}) as { events?: MatrixEvent[] };
    for (const ev of body.events ?? []) {
      const type = ev.type ?? "";
      if (!RELEVANT.has(type)) continue;

      const sender = ev.sender ?? "";
      const meta = {
        source: "matrix",
        source_event_id: ev.event_id ?? null,
        type,
        room: ev.room_id,
        sender,
        ts: ev.origin_server_ts ?? Date.now(),
        mention: Boolean((ev.content ?? {} as any).mentions),
      };

      // 1. fan out to the domain firehose (source is metadata, not the channel).
      try {
        await getRedis().publish(FIREHOSE, JSON.stringify(meta));
      } catch (err) {
        fastify.log.warn({ err: (err as Error).message }, "redis publish failed");
      }

      // 2. persist (best-effort): sender localpart -> canonical sub -> personal group.
      const localpart = sender.startsWith("@") ? sender.slice(1).split(":")[0] : "";
      if (!localpart) continue;
      try {
        const sub = await getUserByEmail(`${localpart}@irl.coop`);
        if (sub) {
          const id = await ingestEvent(sub, "matrix", ev.event_id ?? null, type, meta, meta.ts);
          if (id) fastify.log.info({ id, type, room: ev.room_id }, "event stored");
        }
      } catch (err) {
        fastify.log.warn({ err: (err as Error).message, sender }, "event ingest failed");
      }
    }

    // Appservice transaction ack — empty JSON object is the spec's success body.
    return reply.send({});
  };

  // Synapse pushes via PUT {url}/_matrix/app/v1/transactions/{txnId} (the spec
  // path). Accept PUT+POST on both spellings for safety.
  for (const url of ["/_matrix/app/v1/transactions/:txnId", "/transactions/:txnId"]) {
    fastify.route({ method: ["PUT", "POST"], url, handler: handle });
  }
}
