import path from "node:path";
import dotenv from "dotenv";
import Fastify from "fastify";

// The rail service. Deliberately its own app:
//   - a provider's SDK (and its native dependency tree) never enters the member-facing API;
//   - a provider being taken down, blocked, or shipping a broken build kills ONE container;
//   - swapping providers is a new app behind the same neutral contract, not an edit to core.
//
// It is STATELESS with respect to the coop: coop-api owns the intent record, this service
// only translates between the neutral contract and the provider's SDK.

dotenv.config();
dotenv.config({ path: path.resolve(__dirname, "../../../infra/out/dev/secrets.env") });

import { PeerRail, type PaymentRail } from "./rail";
import { translateWebhook } from "./webhook";

const PORT = Number(process.env.PEER_XYZ_PAYMENTS_PORT ?? 3010);
const TOKEN = process.env.RAIL_AUTH_TOKEN ?? "";
// The provider posts webhooks to us. The types expose no signature scheme, so authenticity
// comes from a CUSTOM HEADER carrying a derived secret — configured on the provider side as a
// customHeaders entry. Without it the endpoint is unauthenticated, so it fails closed.
const WEBHOOK_SECRET = process.env.PEER_PAY_WEBHOOK_SECRET ?? "";
const COOP_API = process.env.COOP_API_URL ?? "http://127.0.0.1:3001";

// One entry today. The contract is what allows a second, so a rail can be added — or run in
// parallel — without touching coop-api.
const RAILS: Record<string, PaymentRail> = { peer: new PeerRail() };

const fastify = Fastify({ logger: false });

/** Bearer auth, the same derived-secret shape the other app -> coop-api integrations use. */
function authed(header: string | undefined): boolean {
  if (!TOKEN) return false;
  const m = /^Bearer\s+(.+)$/.exec(header ?? "");
  return !!m && m[1] === TOKEN;
}

fastify.get("/health", async () => ({ ok: true, rails: Object.keys(RAILS) }));

fastify.addHook("onRequest", async (request, reply) => {
  if (request.url === "/health") return;
  if (request.url.startsWith("/webhooks/")) {
    // provider-facing: its own secret, its own header
    const presented = String(request.headers["x-webhook-secret"] ?? "");
    if (!WEBHOOK_SECRET || presented !== WEBHOOK_SECRET) {
      return reply.code(401).send({ error: "invalid webhook secret" });
    }
    return;
  }
  if (!authed(request.headers.authorization)) reply.code(401).send({ error: "invalid rail token" });
});

// The provider tells us what happened. This is the ONLY way settlement is learned — the SDK
// has no order lookup (see rail.ts capabilities), so without this the coop must ask a human.
//
// Translate here, forward neutrally: coop-api never sees a provider payload, so the provider's
// vocabulary and its event names stay behind the seam.
fastify.post("/webhooks/peer", async (request, reply) => {
  const t = translateWebhook(request.body);
  if (!t.eventId) return reply.code(400).send({ error: "not a webhook payload (no event id)" });
  if (!t.providerRef || t.status === null) {
    // Acknowledge and do nothing. Peer retries on failure, and a 500 on an event we simply do
    // not act on would look like an outage to them.
    return reply.send({ ok: true, ignored: true, event: t.eventType, note: t.note });
  }
  try {
    const res = await fetch(`${COOP_API}/api/v1/internal/rails/settlement`, {
      method: "POST",
      headers: { "content-type": "application/json", authorization: `Bearer ${TOKEN}` },
      body: JSON.stringify({
        rail: "peer",
        provider_ref: t.providerRef,
        status: t.status,
        received: t.received,
        event_id: t.eventId,
        event_type: t.eventType,
      }),
      signal: AbortSignal.timeout(20000),
    });
    const body = await res.json().catch(() => null);
    if (res.status >= 500) return reply.code(500).send({ error: "coop-api could not record it, so the provider should retry" });
    return reply.send({ ok: true, forwarded: t.status, dup: (body as { dup?: boolean })?.dup ?? false });
  } catch (err) {
    // 500 so the PROVIDER retries: losing a settlement notice silently is the failure mode
    // worth being loud about.
    return reply.code(500).send({ error: `could not reach coop-api: ${(err as Error).message}` });
  }
});

// The merchant's own view, so the COOP can check readiness without holding provider
// credentials or knowing the provider's API. Exposes no secret: environment, onboarding time,
// and the default wallet (which the coop compares its destination against, on purpose).
fastify.get("/merchant", async () => {
  const m = await (RAILS["peer"] as unknown as { merchant: () => Promise<Record<string, unknown>> }).merchant();
  return {
    environment: m.environment ?? "unknown",
    onboardingCompletedAt: (m as { onboardingCompletedAt?: string | null }).onboardingCompletedAt ?? null,
    default_wallet: (m as { v1EvmWalletAddress?: string | null }).v1EvmWalletAddress ?? null,
  };
});

/** Capability declaration — coop-api checks `directToDestination` before trusting a rail. */
fastify.get("/rails", async () => ({ rails: Object.values(RAILS).map((r) => r.capabilities()) }));

fastify.post("/intents", async (request, reply) => {
  const body = (request.body ?? {}) as Record<string, string>;
  const rail = RAILS[body.rail ?? "peer"];
  if (!rail) return reply.code(404).send({ error: `no such rail: ${body.rail}` });
  const caps = rail.capabilities();
  if (!caps.directToDestination) {
    // The seam refuses an intermediating rail rather than documenting that it shouldn't be used.
    return reply.code(400).send({ error: `rail ${caps.rail} is not direct-to-destination; the coop does not intermediate member funds` });
  }
  if (!body.amount || !body.destination || !body.chain_id || !body.currency) {
    return reply.code(400).send({ error: "amount, currency, chain_id and destination are required" });
  }
  try {
    const out = await rail.createIntent({
      amount: String(body.amount),
      currency: String(body.currency),
      chainId: String(body.chain_id),
      destination: String(body.destination),
      reference: String(body.reference ?? ""),
    });
    // SERIALISE EXPLICITLY. Spreading the internal object onto the wire couples the HTTP
    // contract to TypeScript property names — the first version shipped camelCase while
    // coop-api read snake_case, and the seam failed on a 200.
    return reply.send({
      rail: caps.rail,
      provider_ref: out.providerRef,
      pay_url: out.payUrl,
      destination: out.destination,
      expires_at: out.expiresAt ?? null,
    });
  } catch (err) {
    const e = err as Error & { code?: string; quotes?: unknown };
    if (e.code === "NO_QUOTE") {
      // Not an error the caller should retry blindly — there is no counterparty right now.
      return reply.code(409).send({ error: e.message, available: false, quotes: e.quotes ?? null });
    }
    return reply.code(502).send({ error: e.message });
  }
});

fastify.get("/intents/:ref", async (request, reply) => {
  const { ref } = request.params as { ref: string };
  const rail = RAILS[(request.query as { rail?: string })?.rail ?? "peer"];
  if (!rail) return reply.code(404).send({ error: "no such rail" });
  const o = await rail.observeIntent(ref);
  return reply.send({ rail: rail.capabilities().rail, provider_ref: ref, status: o.status, received: o.received ?? null, note: o.note ?? null });
});

fastify.post("/intents/:ref/cancel", async (request, reply) => {
  const { ref } = request.params as { ref: string };
  const rail = RAILS["peer"];
  const c = await rail.cancelIntent(ref);
  return reply.send({ rail: "peer", provider_ref: ref, status: c.status, received: null, note: c.note ?? null });
});

fastify.listen({ port: PORT, host: "0.0.0.0" })
  .then(() => console.log(`[peer_xyz_payments] listening on :${PORT} (rails: ${Object.keys(RAILS).join(", ")})`))
  .catch((err) => { console.error("[peer_xyz_payments] failed to start:", err); process.exit(1); });
