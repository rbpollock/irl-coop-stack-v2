import { pool } from "../db";
import { getUserProfile } from "../keycloak-admin";
import { sendMail } from "../mailer";

// System-level outbox operations. These call SECURITY DEFINER functions owned
// by coop_rls (BYPASSRLS), so the sweep sees ALL rows regardless of the coop
// role's RLS scoping — the sweep is a system consumer, not a user.

export async function sweepUndelivered(limit = 100): Promise<string[]> {
  const { rows } = await pool.query(
    `SELECT coop_sweep_undelivered($1) AS id`,
    [limit],
  );
  return rows.map((r) => r.id);
}

export async function markDelivered(eventId: string): Promise<void> {
  await pool.query(`SELECT coop_mark_event_delivered($1)`, [eventId]);
}

// --- Digest lane (batched delivery of unanswered notifications) ---

export type DigestCandidate = {
  user_sub: string;
  event_id: string;
  source: string;
  type: string;
  payload: Record<string, unknown>;
  occurred_at: string;
  group_id: string;
};

// System-level collect (BYPASSRLS): every group member's unanswered, undigested
// events older than the window. Sender-scoped today (group == personal group).
export async function collectDigestCandidates(olderThan: string): Promise<DigestCandidate[]> {
  const { rows } = await pool.query(
    `SELECT user_sub, event_id, source, type, payload, occurred_at, group_id
       FROM coop_collect_digest_candidates($1::interval)`,
    [olderThan],
  );
  return rows as DigestCandidate[];
}

export async function markDigested(userSub: string, eventId: string): Promise<void> {
  await pool.query(`SELECT coop_mark_digested($1, $2)`, [userSub, eventId]);
}

export async function userEmail(sub: string): Promise<string> {
  try {
    const profile = await getUserProfile(sub);
    return profile.email ?? "";
  } catch (err) {
    // A 404 means the sub is stale (deleted user / test artifact) — not a
    // transient failure. Return "" so the caller marks it digested and moves
    // on; anything else is transient and should retry.
    if ((err as Error).message.includes("404")) return "";
    throw err;
  }
}

export async function sendDigestEmail(
  to: string,
  subject: string,
  text: string,
  html: string,
): Promise<void> {
  await sendMail({ to, subject, text, html });
}
