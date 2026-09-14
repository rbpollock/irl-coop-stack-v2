import type { FastifyInstance } from "fastify";
import { getUserByEmail } from "./keycloak-admin";
import { groupMemberSubs, ingestEvent, ingestGroupEvent } from "./events";
import { publishToUser } from "./notifications";
import { renderNotification } from "./render";

// Hi.Events → the coop event bus.
//
// The app auto-provisions a webhook per event (see the irlcoop fork's
// CoopEventBusWebhookProvisioner): every ticketing event in a workspace gets a
// row pointing here, so tickets sold / attendees registered / check-ins land on
// the bus with nobody clicking anything. The workspace decides the TARGET by
// putting it in the URL the app was told to call:
//
//   ?group=<slug>   a group workspace → the GROUP's stream (RLS shows it to every
//                   member; the live lane fans out to each of them)
//   ?owner=<email>  a personal workspace → that member's personal stream
//
// Auth is a bearer derived secret (HI_EVENTS_WEBHOOK), the same shape as the
// Stalwart mail webhook. Identity/privacy is owned by the SOURCE: the app sends
// its resource payload, and this adapter trims it to scalars-and-counts (no
// emails, phones or names) before anything is stored or fanned out.

const TOKEN = process.env.HI_EVENTS_WEBHOOK ?? "";
const EVENTS_URL = process.env.HI_EVENTS_URL ?? "https://events.irl.coop";
const SOURCE = "hi-events";

// Hi.Events' type → the bus type. Unlisted types are accepted and ignored (204),
// so an upstream rename can never turn into a delivery failure.
const TYPE_MAP: Record<string, string> = {
  "order.created": "order.created",
  "order.marked_as_paid": "order.paid",
  "order.refunded": "order.refunded",
  "order.cancelled": "order.cancelled",
  "attendee.created": "attendee.registered",
  "attendee.cancelled": "attendee.cancelled",
  "checkin.created": "checkin.recorded",
  "event.created": "event.created",
};

// Anything that looks like personal data is dropped on the way in.
const PII_KEY = /email|phone|name|address|password|token|secret|stripe|ip_?address/i;

type Resource = Record<string, unknown>;

/** Scalars only, arrays reduced to a count, depth capped — never PII. */
function trim(value: unknown, depth = 0): unknown {
  if (value === null) return null;

  if (Array.isArray(value)) {
    return { count: value.length };
  }

  if (typeof value === "object") {
    if (depth >= 2) return null;
    const out: Record<string, unknown> = {};
    for (const [key, val] of Object.entries(value as Resource)) {
      if (PII_KEY.test(key)) continue;
      const trimmed = trim(val, depth + 1);
      if (trimmed !== null && trimmed !== undefined) out[key] = trimmed;
    }
    return out;
  }

  return typeof value === "string" || typeof value === "number" || typeof value === "boolean"
    ? value
    : null;
}

/** The ids a Temporal workflow can act on — lifted out so they never get trimmed. */
function refsOf(resource: Resource, coop: Resource): Record<string, unknown> {
  const refs: Record<string, unknown> = {};
  for (const key of ["id", "event_id", "order_id", "attendee_id", "checkin_list_id", "organizer_id"]) {
    if (resource[key] !== undefined) refs[key] = resource[key];
  }
  if (coop.event_id !== undefined) refs.event_id = coop.event_id;
  if (coop.account_id !== undefined) refs.account_id = coop.account_id;
  if (coop.webhook_id !== undefined) refs.webhook_id = coop.webhook_id;
  return refs;
}

function countsOf(resource: Resource): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const key of ["order_items", "attendees", "products", "questions_and_answers"]) {
    const v = resource[key];
    if (Array.isArray(v)) counts[key] = v.length;
  }
  return counts;
}

export default async function hiEventsRoutes(fastify: FastifyInstance): Promise<void> {
  fastify.post("/api/v1/webhooks/hi-events", async (request, reply) => {
    const auth = String(request.headers.authorization ?? "");
    const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
    if (!TOKEN || token !== TOKEN) {
      return reply.code(401).send({ error: "invalid_token" });
    }

    const query = (request.query ?? {}) as { group?: string; owner?: string };
    const groupRef = (query.group ?? "").trim();
    const ownerEmail = (query.owner ?? "").trim().toLowerCase();

    if (!groupRef && !ownerEmail) {
      return reply.code(400).send({ error: "group or owner required" });
    }

    const body = (request.body ?? {}) as {
      event_type?: string;
      event_sent_at?: string;
      payload?: Resource;
      coop?: Resource;
    };

    const appType = String(body.event_type ?? "");
    const type = TYPE_MAP[appType];
    if (!type) {
      return reply.code(204).send();
    }

    const resource = (body.payload ?? {}) as Resource;
    const coop = (body.coop ?? {}) as Resource;
    const refs = refsOf(resource, coop);
    const occurredAt = Date.parse(body.event_sent_at ?? "") || Date.now();

    // The event/notification body: counts + refs, never a person.
    const payloadOut = {
      source_type: appType,
      refs,
      counts: countsOf(resource),
      fields: trim(resource) ?? {},
      link: `${EVENTS_URL}/manage/event/${refs.event_id ?? ""}`,
    };

    // Idempotent on (source, source_event_id): the target ref is part of the id
    // because the dedupe index is global per source.
    const target = groupRef ? `group:${groupRef}` : `owner:${ownerEmail}`;
    const recordId = String(refs.id ?? refs.order_id ?? refs.attendee_id ?? "record");
    const sourceEventId = `${target}:${refs.event_id ?? "event"}:${recordId}:${appType}`;

    if (groupRef) {
      const { id, group_id } = await ingestGroupEvent(
        groupRef,
        SOURCE,
        sourceEventId,
        type,
        payloadOut,
        occurredAt,
      );

      if (!id || !group_id) {
        // Unknown group (renamed/slug-less) — say so rather than silently dropping.
        return reply.code(404).send({ error: "group_not_found", group: groupRef });
      }

      // Live lane: every member of the group, resolved server-side.
      const notification = renderNotification({
        id,
        type,
        payload: payloadOut,
        occurred_at: new Date(occurredAt).toISOString(),
      });
      for (const sub of await groupMemberSubs(group_id)) {
        await publishToUser(sub, notification);
      }

      return { id, group_id, type };
    }

    // Personal workspace → that member's own stream (the personal variant
    // resolves/creates their personal group).
    const sub = await getUserByEmail(ownerEmail);
    if (!sub) {
      return reply.code(404).send({ error: "member_not_found", owner: ownerEmail });
    }

    const id = await ingestEvent(sub, SOURCE, sourceEventId, type, payloadOut, occurredAt);
    return { id, sub, type };
  });
}
