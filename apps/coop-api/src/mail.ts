import type { FastifyInstance } from "fastify";
import { getUserByEmail } from "./keycloak-admin";
import { ingestEvent } from "./events";

// Stalwart webhook — mail.received events (message-ingest.ham) into the bus.
// Stalwart POSTs {events:[{id,createdAt,type,data}]} here; auth is a bearer
// token (derived secret, STALWART_WEBHOOK), mirroring the Matrix appservice's
// hs_token pattern. Inbound legitimate mail only — spam (message-ingest.spam)
// is deliberately ignored (no notification for spam).
//
// The recipient `to` resolves to a Keycloak sub via getUserByEmail and the
// event lands in that user's personal group, fanning out to irl:notify:{sub}.
// `to` is an ARRAY in the webhook payload; each recipient gets their own event
// (sourceEventId = messageId::recipient so multi-recipient mail doesn't
// dedup-collide on the shared message id).

const TOKEN = process.env.STALWART_WEBHOOK ?? "";
const DIGEST_FROM = process.env.DIGEST_FROM ?? "notifications@irl.coop";

type WebhookEvent = {
  id?: string;
  createdAt?: string;
  type?: string;
  data?: Record<string, unknown>;
};

// Tolerantly extract email addresses from a value that may be a string, an
// array of strings, or an object carrying an email/address field.
function emailsOf(v: unknown): string[] {
  if (typeof v === "string") {
    const m = /[\w.+-]+@[\w.-]+/.exec(v);
    return m ? [m[0]] : [];
  }
  if (Array.isArray(v)) {
    return v.flatMap(emailsOf);
  }
  if (v && typeof v === "object") {
    const o = v as Record<string, unknown>;
    for (const k of ["email", "address", "value", "name"]) {
      const e = emailsOf(o[k]);
      if (e.length) return e;
    }
  }
  return [];
}

export default async function mailWebhookRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.post("/api/v1/webhooks/stalwart", async (request, reply) => {
    const auth = String(request.headers.authorization ?? "");
    const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    if (!TOKEN || token !== TOKEN) {
      return reply.code(401).send({ error: "invalid_token" });
    }

    const body = (request.body ?? {}) as { events?: WebhookEvent[] };
    let ingested = 0;
    for (const ev of body.events ?? []) {
      if (ev.type !== "message-ingest.ham") continue;
      const d = ev.data ?? {};
      const recipients = emailsOf(d.to);
      const from = emailsOf(d.from)[0] ?? "";
      // The digest's own outbound mail (from notifications@irl.coop) must not
      // loop back into the bus as a fresh notification — skip system senders.
      if (from === DIGEST_FROM) continue;
      const messageId = typeof d.messageId === "string" ? d.messageId : null;
      const occurredAt = Date.parse(ev.createdAt ?? "") || Date.now();
      for (const to of recipients) {
        try {
          const sub = await getUserByEmail(to);
          if (!sub) continue;
          // per-recipient dedup key: the shared message id alone would make a
          // multi-recipient message collide on the (source, source_event_id)
          // unique index and drop all but the first recipient's event.
          const sourceEventId = messageId ? `${messageId}::${to}` : ev.id ?? null;
          const id = await ingestEvent(
            sub,
            "mail",
            sourceEventId,
            "mail.received",
            { from, to, message_id: messageId },
            occurredAt,
          );
          if (id) ingested += 1;
        } catch (err) {
          fastify.log.warn({ err: (err as Error).message, to }, "mail ingest failed");
        }
      }
    }
    return reply.send({ ok: true, ingested });
  });
}
