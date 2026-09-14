import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";
import { withIdentity, pool } from "./db";
import { emitContributionEvent } from "./tier2-contributions";

// Payment rails, from the coop's side.
//
// coop-api holds the CONTRACT and the POLICY; the rail service (apps/peer_xyz_payments) holds
// the provider. Nothing vendor-specific appears here — no SDK, no provider status vocabulary,
// no provider field names. Swapping providers means pointing RAIL_* at a different app; a swap
// never touches this file.
//
// What lives here and nowhere else:
//   - WHERE money goes (PAYMENTS_DESTINATION). The rail executes; it does not decide.
//   - The coop's status vocabulary. The provider's stays behind the rail.
//   - The refusal to use a rail that intermediates funds.

/** The coop's vocabulary. The rail maps the provider's onto this. */
export type IntentStatus = "pending" | "partial" | "settled" | "cancelled" | "failed" | "unknown";

interface RailCapabilities {
  rail: string;
  directToDestination: boolean;
  chains: string[];
  currency: string;
  canObserve: boolean;
  observeUnavailableReason?: string;
}

function railConfig() {
  const url = process.env.RAIL_URL ?? "";
  const token = process.env.RAIL_AUTH_TOKEN ?? "";
  if (!url) throw new Error("payments: RAIL_URL is not set");
  if (!token) throw new Error("payments: RAIL_AUTH_TOKEN is not set");
  return { url: url.replace(/\/$/, ""), token };
}

/** The coop's payment policy. Refused if unset — never defaulted to anything. */
function policy() {
  const destination = (process.env.PAYMENTS_DESTINATION ?? "").trim();
  const chainId = (process.env.PAYMENTS_CHAIN_ID ?? "").trim();
  const currency = (process.env.PAYMENTS_CURRENCY ?? "USDC").trim();
  if (!/^0x[0-9a-fA-F]{40}$/.test(destination)) {
    throw new Error("payments: PAYMENTS_DESTINATION is missing or not an address — refusing to create a payment rather than let a rail fall back to a provider default");
  }
  if (!chainId) throw new Error("payments: PAYMENTS_CHAIN_ID is not set");
  return { destination, chainId, currency };
}

async function railFetch(path: string, init?: RequestInit): Promise<{ status: number; body: unknown }> {
  const c = railConfig();
  const res = await fetch(`${c.url}${path}`, {
    ...init,
    headers: { "content-type": "application/json", authorization: `Bearer ${c.token}`, ...(init?.headers ?? {}) },
    signal: AbortSignal.timeout(25000),
  });
  return { status: res.status, body: await res.json().catch(() => null) };
}

/** Capabilities, and the one check that matters: a rail that intermediates is refused. */
export async function railCapabilities(): Promise<RailCapabilities[]> {
  const { status, body } = await railFetch("/rails");
  if (status !== 200) throw new Error(`payments: the rail service is not answering (HTTP ${status})`);
  const rails = ((body as { rails?: RailCapabilities[] })?.rails ?? []);
  return rails.filter((r) => {
    if (!r.directToDestination) {
      // Not a warning. The platform never intermediates member funds, so a custodying rail is
      // unusable by construction rather than by policy.
      console.error(`[payments] rail ${r.rail} is NOT direct-to-destination — refused`);
      return false;
    }
    return true;
  });
}

export interface CreateIntentResult {
  intentId: string;
  rail: string;
  status: IntentStatus;
  payUrl: string;
  destination: string;
}

export async function createPaymentIntent(args: {
  groupId: string;
  payerSub: string;
  amount: string;
  client: { query: (sql: string, params?: unknown[]) => Promise<{ rows: Record<string, unknown>[] }> };
}): Promise<CreateIntentResult> {
  const pol = policy();
  const amount = Number(args.amount);
  if (!Number.isFinite(amount) || amount <= 0 || amount > 10_000) {
    throw new Error("payments: amount must be a positive number up to 10000");
  }
  const caps = (await railCapabilities())[0];
  if (!caps) throw new Error("payments: no usable rail is configured");
  if (caps.currency !== pol.currency) throw new Error(`payments: rail speaks ${caps.currency}, policy says ${pol.currency}`);
  if (!caps.chains.includes(pol.chainId)) throw new Error(`payments: rail does not support chain ${pol.chainId}`);

  // The row is created FIRST so the intent has a coop-side identity even if the provider call
  // fails; a failed intent is a recorded fact, not a missing one.
  const ins = await args.client.query(
    `INSERT INTO payment_intent (group_id, payer_sub, rail, amount, currency, destination, status)
     VALUES ($1, $2, $3, $4, $5, $6, 'pending')
     RETURNING id`,
    [args.groupId, args.payerSub, caps.rail, args.amount, pol.currency, pol.destination]
  );
  const intentId = (ins.rows[0] as { id: string }).id;

  try {
    const { status, body } = await railFetch("/intents", {
      method: "POST",
      body: JSON.stringify({
        rail: caps.rail,
        amount: args.amount,
        currency: pol.currency,
        chain_id: pol.chainId,
        destination: pol.destination, // the coop's choice, never the request's
        reference: intentId,          // opaque: identifies no member and no group
      }),
    });
    const b = body as { provider_ref?: string; pay_url?: string; error?: string; available?: boolean; quotes?: unknown };
    if (status === 409 && b?.available === false) {
      await args.client.query("UPDATE payment_intent SET status='failed', updated_at=now() WHERE id=$1", [intentId]);
      return { intentId, rail: caps.rail, status: "failed", payUrl: "", destination: pol.destination };
    }
    if (status !== 200 || !b?.provider_ref || !b?.pay_url) {
      await args.client.query("UPDATE payment_intent SET status='failed', updated_at=now() WHERE id=$1", [intentId]);
      throw new Error(b?.error ?? `payments: the rail returned HTTP ${status}`);
    }
    await args.client.query(
      `UPDATE payment_intent SET provider_ref=$2, pay_url=$3, provider_payload=$4::jsonb, updated_at=now() WHERE id=$1`,
      [intentId, b.provider_ref, b.pay_url, JSON.stringify({ destination_confirmed: true })]
    );
    return { intentId, rail: caps.rail, status: "pending", payUrl: b.pay_url, destination: pol.destination };
  } catch (err) {
    await args.client.query("UPDATE payment_intent SET status='failed', updated_at=now() WHERE id=$1", [intentId]).catch(() => {});
    throw err;
  }
}

export default async function paymentRoutes(fastify: FastifyInstance) {
  // What rails exist, and what they can honestly do. `canObserve:false` is surfaced rather
  // than hidden: with no order lookup at the provider, settlement must be confirmed by a
  // person, and the UI needs to say so.
  fastify.get("/api/v1/payments/rails", async (_request, reply) => {
    try {
      const rails = await railCapabilities();
      return reply.send({ rails, destination: (process.env.PAYMENTS_DESTINATION ?? "") || null, chain_id: process.env.PAYMENTS_CHAIN_ID ?? null });
    } catch (err) {
      return reply.code(503).send({ error: (err as Error).message });
    }
  });


  // PREFLIGHT — the gates between here and live money, as a list that can only be green when
  // the work is actually done. Deliberately mixed: what a machine can verify is CHECKED, and
  // what only a person can assert is labelled as an assertion rather than dressed up as a test.
  //
  // This exists because "are we ready for live?" should not be answerable from prose.
  fastify.get("/api/v1/payments/preflight", async (_request, reply) => {
    const gates: Array<{ id: string; ok: boolean; kind: "checked" | "asserted"; detail: string }> = [];
    const dest = (process.env.PAYMENTS_DESTINATION ?? "").trim();
    const chain = (process.env.PAYMENTS_CHAIN_ID ?? "").trim();

    // 1 — the merchant must actually be a live merchant
    let env = "unreachable", onboarded: string | null = null, merchantDefault: string | null = null;
    try {
      const c = railConfig();
      const r = await fetch(`${railConfig().url}/rails`, { headers: { authorization: `Bearer ${c.token}` }, signal: AbortSignal.timeout(8000) });
      const j = (await r.json()) as { rails?: unknown[] };
      env = j.rails?.length ? "reachable" : "none";
      // ask the rail for the merchant's own view
      const m = await fetch(`${railConfig().url}/merchant`, { headers: { authorization: `Bearer ${c.token}` }, signal: AbortSignal.timeout(12000) });
      if (m.ok) {
        const info = (await m.json()) as { environment?: string; onboardingCompletedAt?: string | null; default_wallet?: string | null };
        env = String(info.environment ?? "unknown");
        onboarded = info.onboardingCompletedAt ?? null;
        merchantDefault = info.default_wallet ?? null;
      }
    } catch { env = "unreachable"; }
    gates.push({
      id: "live-merchant", ok: env === "LIVE", kind: "checked",
      detail: `provider environment is ${env}${onboarded ? `, onboarding completed ${onboarded}` : ", onboarding NOT completed"}`,
    });

    // 2 — the destination must be a CONTRACT, not a wallet. A wallet the platform controls
    //     would be the platform holding member money. Checked by asking the chain for code.
    let codeKind = "unchecked", codeBytes = 0, codeErr = "";
    if (/^0x[0-9a-fA-F]{40}$/.test(dest)) {
      try {
        const rpc = process.env.PAYMENTS_RPC_URL ?? "https://mainnet.base.org";
        const r = await fetch(rpc, {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "eth_getCode", params: [dest, "latest"] }),
          signal: AbortSignal.timeout(10000),
        });
        const j = (await r.json()) as { result?: string };
        const hex = (j.result ?? "0x").slice(2);
        codeBytes = hex.length / 2;
        // "code exists" is NOT the same as "this is a contract". An EIP-7702 delegated EOA
        // returns a 23-byte designator (0xef0100 || address) and is still an EOA that a person
        // controls. Treating that as a contract is a false green — it was, until this check.
        if (hex.length === 0) codeKind = "eoa";
        else if (hex.startsWith("ef0100")) codeKind = "delegated-eoa";
        else if (codeBytes < 64) codeKind = "too-small";
        else codeKind = "contract";
      } catch (e) { codeErr = (e as Error).message; }
    }
    gates.push({
      id: "destination-is-a-contract", ok: codeKind === "contract", kind: "checked",
      detail:
        codeKind === "contract" ? `${dest} is a contract (${codeBytes} bytes of code)`
        : codeKind === "eoa" ? `${dest || "(unset)"} has NO code — an EOA. Member money would land in a wallet a person controls.`
        : codeKind === "delegated-eoa" ? `${dest} is an EIP-7702 DELEGATED EOA, not a contract: its ${codeBytes}-byte code is a delegation designator (0xef0100…), and the account is still controlled by a key.`
        : codeKind === "too-small" ? `${dest} has only ${codeBytes} bytes of code — not a router.`
        : `could not read the chain${codeErr ? ` (${codeErr})` : ""}`,
    });

    // 3 — the destination must not be the provider's own default wallet
    gates.push({
      id: "destination-is-not-the-default", ok: !merchantDefault || dest.toLowerCase() !== merchantDefault.toLowerCase(),
      kind: "checked",
      detail: merchantDefault ? (dest.toLowerCase() === merchantDefault.toLowerCase()
        ? `the destination IS the merchant's own wallet (${dest}) — the provider's default`
        : `differs from the merchant's default wallet`) : "merchant default unknown",
    });

    // 4 — the chain must be the coop's chain
    gates.push({ id: "chain-is-base", ok: chain === "8453", kind: "checked", detail: `PAYMENTS_CHAIN_ID=${chain || "(unset)"}` });

    // 5 — settlement must be observable: at least one VERIFIED delivery, ever.
    //     Read through a SECURITY DEFINER count, because rail_event is FORCE RLS with no
    //     policies — a direct count returned 0 while the row existed, i.e. the gate could not
    //     see its own evidence. And a failed read must NOT be reported as "none arrived":
    //     asserting a negative from a failure is the same defect one level up.
    const seen = await pool.query("SELECT coop_rail_event_count()::int AS n").catch(() => null);
    const n = seen ? (seen.rows[0] as { n: number }).n : null;
    gates.push({
      id: "webhook-evidenced",
      ok: n !== null && n > 0,
      kind: "checked",
      detail:
        n === null
          ? "cannot read the event count — the gate cannot answer, which is NOT the same as 'nothing arrived'"
          : n > 0
            ? `${n} verified provider event(s) recorded — a signed delivery has been accepted`
            : "none yet — the webhook is registered but no delivery has arrived",
    });

    // 6 — the legal entity. NOT checkable: no code can know whether a coop legally exists, and
    //     pretending otherwise would be the most dangerous possible false green. An explicit,
    //     dated assertion is the honest form.
    const entity = (process.env.PAYMENTS_ENTITY ?? "").trim();
    gates.push({
      id: "operating-entity", ok: entity.length > 0, kind: "asserted",
      detail: entity
        ? `asserted by configuration: "${entity}" — a human claim, not a verification`
        : "unasserted. Statutory bookkeeping, tax and chargeback obligations land on an entity; set PAYMENTS_ENTITY to the registered name to record the claim deliberately",
    });

    const ready = gates.every((g) => g.ok);
    return reply.send({ ready, gates, markup_cap_percent: 20, destination: dest || null });
  });

  fastify.post("/api/v1/groups/:id/payments/deposit", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const { id: groupId } = request.params as { id: string };
    const body = (request.body ?? {}) as { amount?: string };
    const amount = String(body.amount ?? "").trim();
    if (!amount) return reply.code(400).send({ error: "amount is required" });
    try {
      // The payer is ALWAYS the caller: money attribution is never "on behalf of".
      const out = await withIdentity(claims.sub, async (client) => {
        const m = await client.query("SELECT coop_is_member($1) AS m", [groupId]);
        if (!(m.rows[0] as { m?: boolean })?.m) return null;
        return createPaymentIntent({ groupId, payerSub: claims.sub, amount, client });
      });
      if (!out) return reply.code(403).send({ error: "not a member of this group" });
      return reply.send(out);
    } catch (err) {
      return reply.code(502).send({ error: (err as Error).message });
    }
  });

  // Observe that funds arrived. The provider cannot be asked (see rail capabilities), so this
  // is an operator/participant statement — and a partial amount is first-class.
  // Emits a contribution event; the Temporal lane materialises a receipt entry, and the group
  // attests it through the ordinary countersign route. No second append path.
  fastify.post("/api/v1/groups/:id/payments/:intentId/confirm", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const { id: groupId, intentId } = request.params as { id: string; intentId: string };
    const body = (request.body ?? {}) as { status?: string; received?: string };
    const status = String(body.status ?? "settled");
    if (!["settled", "partial"].includes(status)) {
      return reply.code(400).send({ error: "status must be settled or partial" });
    }
    try {
      const out = await withIdentity(claims.sub, async (client) => {
        const row = await client.query(
          "SELECT id, rail, provider_ref, amount, status, settled_at FROM payment_intent WHERE id = $1 AND group_id = $2",
          [intentId, groupId]
        );
        if (!row.rows.length) return { code: 404 as const };
        const r = row.rows[0] as { rail: string; provider_ref: string | null; amount: string; settled_at: string | null };
        if (r.settled_at) return { code: 409 as const };
        const received = String(body.received ?? r.amount);
        await client.query(
          "UPDATE payment_intent SET status=$2, received_amount=$3, settled_at=now(), updated_at=now() WHERE id=$1",
          [intentId, status, received]
        );
        const eventId = await emitContributionEvent(client, {
          groupId,
          // source + source_event_id form the ledger's idempotency key: no double-credit, ever.
          source: r.rail,
          sourceEventId: r.provider_ref ?? intentId,
          payload: {
            sub: claims.sub,
            kind: "receipt",
            subject: claims.sub,
            quantity: Number(received),
            unit: "USDC",
            happened_at: new Date().toISOString(),
          },
        });
        return { code: 200 as const, intentId, status, received, rail: r.rail, eventId };
      });
      if (out.code === 404) return reply.code(404).send({ error: "no such payment" });
      if (out.code === 409) return reply.code(409).send({ error: "already confirmed" });
      return reply.send(out);
    } catch (err) {
      return reply.code(500).send({ error: (err as Error).message });
    }
  });


  // INTERNAL: the rail reports settlement (and reversals) here. Not a user route — it is
  // authenticated by the rail token the rail service holds, and it is the ONLY way a payment
  // moves without a human, because the provider's SDK cannot be polled.
  fastify.post("/api/v1/internal/rails/settlement", async (request, reply) => {
    const presented = String(request.headers.authorization ?? "");
    if (!process.env.RAIL_AUTH_TOKEN || presented !== `Bearer ${process.env.RAIL_AUTH_TOKEN}`) {
      return reply.code(401).send({ error: "invalid rail token" });
    }
    const b = (request.body ?? {}) as Record<string, unknown>;
    // `provider_ref` and `status` are OPTIONAL: a verified event that carries no state change is
    // still worth recording, because "we accepted a signed delivery" is the evidence that the
    // webhook is wired at all. Absent a status, nothing about an intent is touched.
    const needed = ["rail", "event_id", "event_type"];
    if (needed.some((k) => !b[k])) return reply.code(400).send({ error: `required: ${needed.join(", ")}` });
    const status = b.status == null || b.status === "" ? null : String(b.status);
    if (status && !["pending", "partial", "settled", "cancelled", "failed", "reversed"].includes(status)) {
      return reply.code(400).send({ error: `unknown status: ${status}` });
    }

    // The system write happens inside a SECURITY DEFINER function: a webhook is untrusted
    // input and the intent row is RLS-protected, so it gets a narrow function rather than an
    // exemption. It also dedupes on (rail, event_id), so a provider retry is a no-op.
    const res = await pool.query(
      "SELECT * FROM coop_rails_settle($1, $2, $3, $4, $5, $6)",
      [String(b.rail), b.provider_ref == null ? null : String(b.provider_ref), status, b.received ?? null, String(b.event_id), String(b.event_type)]
    );
    const row = res.rows[0] as { dup: boolean; intent_id: string | null; group_id: string | null; payer_sub: string | null; cur_status: string | null; received: string | null } | undefined;
    if (!row) return reply.code(500).send({ error: "settlement function returned nothing" });
    if (row.dup) return reply.send({ ok: true, dup: true });
    if (!row.intent_id) return reply.code(404).send({ ok: false, error: "no payment intent for that provider reference" });

    // Emit as the PAYER, so RLS admits the entry on its own merits rather than by exemption.
    //
    // Two different idempotency keys, on purpose:
    //   settled  -> keyed by provider_ref, so a second "fulfilled" event (the provider sends
    //               both ORDER_FULFILLED and PAYMENT_SETTLED) cannot log a second receipt.
    //   reversed -> keyed by the reversal EVENT id, because each reversal is its own fact and
    //               two different chargebacks must both be recorded.
    let entryId: string | null = null;
    let refs: string[] = [];
    if (status === "reversed") {
      const orig = await pool.query("SELECT entry_id FROM tier2_entry WHERE idempotency_key = $1", [`${String(b.rail)}:${String(b.provider_ref)}`]);
      if (!orig.rows.length) {
        // A reversal with nothing to reverse: a cancelled order, not a chargeback. Nothing is
        // owed and inventing a correction would create a fact out of nothing.
        console.warn(`[payments] reversal for ${String(b.provider_ref)} but no receipt entry exists`);
        return reply.send({ ok: true, status, correction: null, note: "no receipt to correct" });
      }
      refs = [String((orig.rows[0] as { entry_id: string }).entry_id)];
    }

    // A record-only event changes nothing and must emit NOTHING. Emitting a receipt for an
    // informational event is how a "money arrived" entry gets created out of thin air — and it
    // is exactly what happened when informational events began being forwarded: the lane
    // dead-lettered a receipt whose quantity was null.
    if (status === null) {
      return reply.send({ ok: true, status: row.cur_status, received: row.received, record_only: true });
    }

    await withIdentity(String(row.payer_sub), async (client) => {
      entryId = await emitContributionEvent(client, {
        groupId: String(row.group_id),
        source: String(b.rail),
        sourceEventId: status === "reversed" ? String(b.event_id) : String(b.provider_ref),
        payload:
          status === "reversed"
            ? {
                // A correction, not a deletion: entries are never deleted, and the original
                // receipt stays exactly as it was.
                sub: String(row.payer_sub), kind: "correction", subject: String(row.payer_sub),
                quantity: row.received ? -Math.abs(Number(row.received)) : undefined, unit: "USDC",
                happened_at: new Date().toISOString(), refs,
                note: `reversed by ${String(b.event_type)}`,
              }
            : {
                sub: String(row.payer_sub), kind: "receipt", subject: String(row.payer_sub),
                quantity: row.received ? Number(row.received) : undefined, unit: "USDC",
                happened_at: new Date().toISOString(),
              },
        // No signature: this is the LANE's path, which materialises it as machine-only.
      } as never);
    });

    return reply.send({ ok: true, status: row.cur_status, received: row.received, entry_event: entryId, correction_of: refs[0] ?? null });
  });

  // Neutral statuses only — the provider's vocabulary never reaches a client.
  fastify.get("/api/v1/groups/:id/payments", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const { id: groupId } = request.params as { id: string };
    const rows = await withIdentity(claims.sub, async (client) =>
      client.query(
        `SELECT id, rail, amount, currency, status, received_amount, destination, pay_url, settled_at, created_at
           FROM payment_intent WHERE group_id = $1 ORDER BY created_at DESC LIMIT 50`,
        [groupId]
      )
    );
    return reply.send({ payments: rows.rows });
  });
}
