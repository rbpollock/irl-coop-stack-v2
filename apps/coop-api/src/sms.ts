import type { FastifyInstance } from "fastify";
import { verifyBearer } from "./verify-jwt";
import { withIdentity, pool } from "./db";

// SMS that ARRIVES at a number the coop controls — the spine of group-owned accounts.
//
// A group that runs an account needs its verification codes to land somewhere its people can
// see, or the account is hostage to one member's handset. So this module does three things:
// accept a text from a gateway, pull the code out of it, and let the owning group's members
// read it.
//
// Two deliberate limits, both load-bearing:
//
//   1. The extraction is a CONVENIENCE, never an authority. The raw body is always stored, so a
//      wrong guess cannot lose the truth, and nothing may treat `code` as authoritative.
//   2. No bus event in this slice. The delivery lane is TYPE-AGNOSTIC — it claims everything
//      that is not `contribution.%` — so emitting `sms.received` today would mean one email
//      attempt per text. Which types may notify, and over which channel, is a decision (a code
//      wants a targeted push to the member mid-signup, not a broadcast), so it is recorded
//      rather than inherited.

/** Known senders, so a surface can say WHICH code this is, and so a signup flow can filter.
 *  A hint from the message text — never a claim about who really sent it. */
const SERVICE_HINTS: Array<[string, string]> = [
  ["instagram", "instagram"],
  ["facebook", "facebook"],
  ["meta", "facebook"],
  ["whatsapp", "whatsapp"],
  ["youtube", "youtube"],
  ["google", "google"],
  ["apple", "apple"],
  ["microsoft", "microsoft"],
  ["paypal", "paypal"],
  ["wise", "wise"],
  ["venmo", "venmo"],
];

// Keyword-adjacent wins: "your code is 123456", "OTP: 123456".
const NEAR_KEYWORD = /(?:code|otp|pin|passcode|token|verification)[^0-9]{0,14}(\d{4,8})\b/i;
// Google sends a letter-prefixed code ("G-123456"), which a bare-digit rule cannot see.
const LETTER_PREFIXED = /\b([A-Z])[- ]?(\d{5,8})\b/;

/** How long a code is assumed useful. A DEFAULT, not a platform claim: the providers differ. */
const CODE_TTL_MS = 10 * 60 * 1000;

export function extractCode(body: string): { code: string | null; kind: string; how: string } {
  const text = String(body ?? "");
  const lower = text.toLowerCase();
  const kind = SERVICE_HINTS.find(([needle]) => lower.includes(needle))?.[1] ?? "unknown";

  const near = NEAR_KEYWORD.exec(text);
  if (near) return { code: near[1], kind, how: "keyword-adjacent" };

  const pref = LETTER_PREFIXED.exec(text);
  if (pref) return { code: `${pref[1]}-${pref[2]}`, kind, how: "letter-prefixed" };

  // A standalone 4-8 digit run. \b keeps a 10-digit phone number from matching, and this is the
  // case that most needs the raw body kept, because it is the guess most likely to be wrong.
  const all = text.match(/\b\d{4,8}\b/g);
  if (all && all.length) return { code: all[all.length - 1], kind, how: "last standalone run" };

  return { code: null, kind, how: "none found" };
}

export default async function smsRoutes(fastify: FastifyInstance): Promise<void> {
  // INGEST — the gateway posts here. Authenticated with a derived bearer secret, the same shape
  // every other service -> coop-api integration uses (STALWART_WEBHOOK, HI_EVENTS_WEBHOOK).
  //
  // The gateway never says which group a text belongs to: the NUMBER maps to a group through
  // telephony_resources, so a number the coop has not provisioned cannot be attributed by a
  // caller claiming it.
  fastify.post("/api/v1/internal/sms/inbound", async (request, reply) => {
    const expected = process.env.SMS_WEBHOOK_TOKEN ?? "";
    const presented = String(request.headers.authorization ?? "");
    if (!expected || presented !== `Bearer ${expected}`) {
      // Distinguish "this server has no token configured" from "wrong token": the first is a
      // deployment fault and reads identically to an attacker's mistake without this field.
      return reply.code(401).send({
        error: "invalid sms token",
        server_token_configured: Boolean(expected),
      });
    }

    const b = (request.body ?? {}) as Record<string, unknown>;
    const number = typeof b.to === "string" ? b.to.trim() : "";
    const body = typeof b.body === "string" ? b.body : "";
    if (!number || !body) return reply.code(400).send({ error: "required: to, body" });

    const peer = typeof b.from === "string" ? b.from : null;
    const externalId = typeof b.external_id === "string" && b.external_id ? b.external_id : null;
    const { code, kind, how } = extractCode(body);
    const expiresAt = code ? new Date(Date.now() + CODE_TTL_MS).toISOString() : null;

    const { rows } = await pool.query("SELECT * FROM coop_ingest_sms($1,$2,$3,$4,$5,$6,$7)", [
      number,
      peer,
      body,
      externalId,
      code,
      kind,
      expiresAt,
    ]);
    const row = rows[0] as { id: string | null; group_id: string | null; duplicate: boolean } | undefined;

    // The CODE IS NOT ECHOED. The caller is a gateway device; it has no business holding a
    // verification code, and echoing one would put it in the gateway's logs.
    return reply.send({
      ok: true,
      recorded: !!row?.id,
      duplicate: !!row?.duplicate,
      group_scoped: row?.group_id != null,
      code_found: code !== null,
      extraction: how,
    });
  });

  // READ — the owning group's messages. A member may see them: the account is the GROUP's, and
  // the group's people are who the codes are for. RLS enforces this in Postgres; the membership
  // check here only produces a clean 403 instead of an empty list.
  fastify.get("/api/v1/groups/:id/sms", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    const groupId = (request.params as { id: string }).id;
    const q = (request.query ?? {}) as { limit?: string; kind?: string };
    const limit = Math.min(Math.max(Number(q.limit ?? 20) || 20, 1), 100);

    const rows = await withIdentity(claims.sub, async (client) => {
      const isMember = await client.query<{ ok: boolean }>("SELECT coop_is_member($1) AS ok", [groupId]);
      if (!isMember.rows[0]?.ok) return null;
      const res = await client.query(
        `SELECT id, peer_e164, body, code, code_kind, received_at, expires_at,
                (expires_at IS NOT NULL AND expires_at < now()) AS expired
           FROM phone_message
          WHERE group_id = $1 AND ($2::text IS NULL OR code_kind = $2)
          ORDER BY received_at DESC LIMIT $3`,
        [groupId, q.kind ?? null, limit],
      );
      return res.rows;
    });

    if (rows === null) return reply.code(403).send({ error: "not a member of this group" });
    return reply.send({ messages: rows });
  });

  // The primitive a signup flow calls: the newest code that has not expired. One call, no
  // scanning, and the expiry is stated rather than assumed.
  fastify.get("/api/v1/groups/:id/sms/code", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    const groupId = (request.params as { id: string }).id;
    const q = (request.query ?? {}) as { kind?: string };

    const row = await withIdentity(claims.sub, async (client) => {
      const isMember = await client.query<{ ok: boolean }>("SELECT coop_is_member($1) AS ok", [groupId]);
      if (!isMember.rows[0]?.ok) return null;
      const res = await client.query(
        `SELECT code, code_kind, received_at, expires_at
           FROM phone_message
          WHERE group_id = $1 AND code IS NOT NULL
            AND (expires_at IS NULL OR expires_at > now())
            AND ($2::text IS NULL OR code_kind = $2)
          ORDER BY received_at DESC LIMIT 1`,
        [groupId, q.kind ?? null],
      );
      return res.rows[0] ?? false;
    });

    if (row === null) return reply.code(403).send({ error: "not a member of this group" });
    if (row === false) {
      return reply.send({ code: null, note: "no unexpired code for this group" });
    }
    return reply.send(row);
  });
}
