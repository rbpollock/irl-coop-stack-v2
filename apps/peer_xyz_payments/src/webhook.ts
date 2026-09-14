import type { IntentStatus } from "./rail";

// Translating a provider webhook into the coop's vocabulary.
//
// The payload is UNTRUSTED input: a webhook is an HTTP request from outside. So this maps a
// small, explicit set of event types and refuses to guess about the rest — an unrecognised
// event produces no state change rather than an assumed one.
//
// Note what the provider sends that the coop actually cares about: not just fulfilment, but
// REFUNDS and CHARGEBACKS. The money doc's section 10 has a T+130 settlement window for
// exactly this reason, and a `receipt` entry means "funds arrived", not "funds are final".

/** What the provider's event types translate to. Anything absent is deliberately inert. */
const EVENT_STATUS: Record<string, IntentStatus | null> = {
  PAYMENT_SETTLED: "settled",
  ORDER_FULFILLED: "settled",
  ORDER_CANCELLED: "cancelled",
  PAYMENT_CANCELLED: "cancelled",
  PAYMENT_EXPIRED: "cancelled",
  PAYMENT_FAILED: "failed",
  PAYMENT_BRIDGE_FAILED: "failed",
  // Reversal family. A settled payment can be taken back, and the coop must be able to say so.
  PAYMENT_CHARGEBACKED: "reversed",
  ORDER_CHARGEBACKED: "reversed",
  ORDER_PARTIALLY_CHARGEBACKED: "reversed",
  REFUND_COMPLETED: "reversed",
  REFUND_PENDING: "reversed",
  // Informational: the order exists / a bridge is moving / a refund is in flight. No status
  // change, because inventing one would be a lie about where the money is.
  ORDER_CREATED: null,
  PAYMENT_CREATED: null,
  PAYMENT_BRIDGE_PENDING: null,
  PAYMENT_BRIDGE_SUBMITTED: null,
  PAYMENT_BRIDGE_COMPLETED: null,
  // ORDER_RESIZED changes the amount mid-flight. Deliberately NOT handled yet: it needs a
  // decision about whether the coop accepts a changed amount, and pretending it is fulfilment
  // would be worse than ignoring it. Recorded as an open item.
};

export interface TranslatedWebhook {
  eventId: string;
  eventType: string;
  providerRef: string | null;
  /** null = no state change (informational, or an event type we do not act on) */
  status: IntentStatus | null;
  received: number | null;
  note: string;
}

export function translateWebhook(payload: unknown): TranslatedWebhook {
  const p = (payload ?? {}) as {
    id?: string;
    type?: string;
    data?: { order?: Record<string, unknown> | null; payment?: Record<string, unknown> | null; resize?: Record<string, unknown> | null };
  };
  const type = String(p.type ?? "");
  const order = p.data?.order ?? null;
  const providerRef = (order?.id as string | undefined) ?? null;
  const eventId = String(p.id ?? "");

  const status = type in EVENT_STATUS ? EVENT_STATUS[type] : null;

  // "received" is derived, not taken on faith: requested - remaining is what actually landed.
  let received: number | null = null;
  if (order) {
    const requested = Number(order.requestedUsdcAmount ?? NaN);
    const remaining = Number(order.remainingUsdcAmount ?? NaN);
    if (Number.isFinite(requested) && Number.isFinite(remaining)) received = requested - remaining;
  }

  // A settled order that still shows a remainder is PARTIAL, whatever the event name says.
  let finalStatus = status;
  if (finalStatus === "settled" && received !== null && order) {
    const requested = Number(order.requestedUsdcAmount ?? NaN);
    if (Number.isFinite(requested) && received < requested) finalStatus = "partial";
  }

  return {
    eventId,
    eventType: type,
    providerRef,
    status: finalStatus,
    received,
    note:
      finalStatus === null
        ? `no state change for ${type || "unknown event"}`
        : `${type} -> ${finalStatus}`,
  };
}


/**
 * Verify a Peer webhook signature — their documented scheme, not one we invented.
 *
 *   X-Webhook-Timestamp, X-Webhook-Signature  ->  HMAC-SHA256(secret, `${timestamp}.${rawBody}`)
 *
 * Both details are load-bearing:
 *   - the RAW body must be used, byte for byte: re-serialising the JSON changes the bytes and
 *     the signature will never match (a classic and silent failure);
 *   - the timestamp window rejects a replayed delivery.
 *
 * Note their retry policy: a delivery is attempted up to 7 times and every attempt carries the
 * SAME X-Webhook-Id with a FRESH timestamp and signature. So a valid signature says "Peer sent
 * this", and the id is what makes a retry idempotent — two different checks, both required.
 */
export function verifySignature(
  rawBody: string,
  timestamp: string | undefined,
  signature: string | undefined,
  secret: string,
  maxSkewSeconds = 300,
): { ok: boolean; reason?: string } {
  if (!secret) return { ok: false, reason: "no webhook secret configured" };
  if (!timestamp || !signature) {
    return { ok: false, reason: "missing X-Webhook-Timestamp or X-Webhook-Signature" };
  }
  const ts = Number(timestamp);
  if (!Number.isFinite(ts)) return { ok: false, reason: "timestamp is not a number" };
  const skew = Math.abs(Math.floor(Date.now() / 1000) - ts);
  if (skew > maxSkewSeconds) {
    return { ok: false, reason: `timestamp outside the ${maxSkewSeconds}s window (skew ${skew}s)` };
  }
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const crypto = require("node:crypto");
  const expected = crypto.createHmac("sha256", secret).update(`${timestamp}.${rawBody}`).digest("hex");
  const a = Buffer.from(expected, "utf8");
  const b = Buffer.from(String(signature).trim().toLowerCase(), "utf8");
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
    return { ok: false, reason: "signature mismatch" };
  }
  return { ok: true };
}
