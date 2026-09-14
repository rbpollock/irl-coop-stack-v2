import { pool, withIdentity, appendTier2Entry } from "../db";
import {
  assertContributionPayload,
  contributionPayloadToEntry,
  type ContributionPayload,
} from "../tier2-contributions";
import { getUserProfile } from "../keycloak-admin";
import { sendMail } from "../mailer";
import { reconcileGroupPostiz, type PostizSeat } from "../postiz";

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

// --- Postiz sync lane (groups → Postiz org projection) ---

export type PostizGroup = { groupId: string; name: string };

export async function postizListGroups(): Promise<PostizGroup[]> {
  const { rows } = await pool.query(`SELECT group_id, name FROM coop_postiz_opted_groups()`);
  return rows.map((r) => ({ groupId: r.group_id, name: r.name }));
}

export async function postizReconcileGroup(groupId: string, name: string): Promise<void> {
  const seats = await pool.query(`SELECT sub, roles, email FROM coop_postiz_seats($1)`, [groupId]);
  await reconcileGroupPostiz(groupId, name, seats.rows as PostizSeat[]);
}

// --- Tier-2 lane: work becomes a ledger entry (docs/design/tier2-entry-model.md §5.6) ---
//
// The lane is a CONSUMER, never a second writer: it calls the same appendTier2Entry the human
// path calls, so the chain invariants exist in one place.

export type PendingContribution = { id: string; group_id: string };

export async function sweepContributions(limit = 100): Promise<PendingContribution[]> {
  const { rows } = await pool.query(`SELECT id, group_id FROM coop_sweep_contributions($1)`, [limit]);
  return rows as PendingContribution[];
}

/**
 * Materialise one contribution event into a ledger entry.
 *
 * The append runs under `app.sub = payload.sub` — the member the work is ABOUT. That is not a
 * shortcut: it means the RLS insert policy (`coop_is_member(group_id)`) does the authorization,
 * so a compromised source can only create entries for people who really are in that group, and
 * the entry lands `machine-only`, which can never affect a Tier-1 outcome until a role holder
 * or a vote touches it.
 *
 * FAILURE DISCIPLINE: a transient error (database down) is re-thrown so Temporal retries. A
 * PERMANENT one — a malformed payload, or a sub who is not a member — can never succeed, so the
 * event is dead-lettered (marked delivered, logged loudly) instead of stalling the lane forever.
 * The log IS the dead-letter record today; a table for it is a follow-on.
 */
export async function materializeContribution(
  eventId: string,
): Promise<{ entry_id: string | null; deduplicated: boolean; dead_lettered: boolean }> {
  const { rows } = await pool.query(`SELECT * FROM coop_contribution_event($1)`, [eventId]);
  if (!rows.length) {
    return { entry_id: null, deduplicated: false, dead_lettered: true }; // already consumed, or not a contribution
  }
  const ev = rows[0];

  let payload: ContributionPayload;
  try {
    assertContributionPayload(ev.payload);
    payload = ev.payload as ContributionPayload;
  } catch (err) {
    await markDelivered(eventId);
    console.error(`[tier2] dead-lettered ${eventId}: ${(err as Error).message}`);
    return { entry_id: null, deduplicated: false, dead_lettered: true };
  }

  const sourceEventId = ev.source_event_id ?? String(ev.id);
  // A PROVENANCE MARKER, not a cryptographic signature: there is no key material for a source
  // yet, so `sig` names the producer and the event rather than pretending to prove anything.
  // It becomes verifiable when a source holds a real scoped key (tier2-entry-model.md §3.2),
  // and nothing Tier-1-eligible depends on it in the meantime — the basis stays machine-only.
  const signature = {
    signer: payload.sub,
    class: "scoped-key" as const,
    authority: `source:${ev.source}`,
    validFrom: new Date(0),
    validTo: null,
    signedAt: new Date(),
    sig: `machine:${ev.source}:${eventId}`,
  };

  try {
    const r = await withIdentity(payload.sub, (client) =>
      appendTier2Entry(
        client,
        contributionPayloadToEntry(String(ev.group_id), String(ev.source), sourceEventId, payload, signature),
      ),
    );
    await markDelivered(eventId);
    return { entry_id: r.entry_id, deduplicated: r.deduplicated, dead_lettered: false };
  } catch (err) {
    const msg = (err as Error).message;
    if (/row-level security|violates|duplicate key|not found/i.test(msg)) {
      await markDelivered(eventId);
      console.error(`[tier2] dead-lettered ${eventId}: ${msg}`);
      return { entry_id: null, deduplicated: false, dead_lettered: true };
    }
    throw err; // transient — let Temporal retry
  }
}
