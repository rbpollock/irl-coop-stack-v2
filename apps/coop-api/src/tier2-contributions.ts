import type { PoolClient } from "pg";
import { appendTier2Entry, type Tier2EntryInput, type Tier2Kind, type Tier2SignatureInput } from "./db";

// Contributions — how WORK becomes a Tier-2 entry (docs/design/tier2-entry-model.md §5.6).
//
// Two paths, one writer:
//
//   human taps "log 3 hours"  ->  recordContribution()  appends AND emits, ONE transaction
//   Plane/LiteFarm/cal.diy    ->  a contribution.* event in the outbox, nothing else
//                                      ↓
//                                 tier2Sweep -> materializeContribution -> appendTier2Entry
//
// Both land on appendTier2Entry, so the ledger's invariants live in exactly one place, and
// the difference is who calls it rather than what it does.
//
// WHY THE HUMAN PATH DOES NOT WAIT FOR THE LANE: the ledger is the system of record, and
// read-your-writes is not negotiable for a member — a queue delay is indistinguishable from
// a failure. The lane may still see that same event later; the idempotency key makes its
// append a no-op, so running it over human-initiated events is safe by construction.

/** The event type the durable lane consumes. The SQL emitter (coop_emit_contribution) hardcodes
 *  the same string — they are the two halves of one interface, so a change must touch both. */
export const CONTRIBUTION_EVENT_TYPE = "contribution.logged";

/** Sources a contribution may name. Bounded: an unbounded source string is how a ledger
 *  stops being able to say where a record came from. */
export const CONTRIBUTION_SOURCES = ["manual", "plane", "litefarm", "caldiy", "stand"] as const;
export type ContributionSource = (typeof CONTRIBUTION_SOURCES)[number];

/** The kinds a MEMBER may log. `incident` and `correction` are ledger kinds but not
 *  contributions — a member does not "contribute" an incident. */
export const CONTRIBUTION_KINDS = ["hours", "swap", "in_kind", "receipt", "custody"] as const;

/** What a producer puts in `events.payload`. `sub` is required because it is also what the
 *  RLS insert policy is checked against — see materializeContribution. */
export interface ContributionPayload {
  sub: string;
  kind: Tier2Kind;
  subject?: string;
  quantity?: number;
  unit?: string;
  happened_at?: string;
  refs?: string[];
  note?: string;
}

export interface ContributionInput {
  groupId: string;
  source: ContributionSource;
  /** the SOURCE's own identifier for the work — the whole basis of the idempotency key */
  sourceEventId: string;
  payload: ContributionPayload;
  /** the proposer's own signature (a scoped key for a machine, the member for a self-log) */
  signature: Tier2SignatureInput;
  /** optional at creation: an organizer-confirm counter-signature, which makes the entry
   *  `attested` instead of `machine-only` */
  countersignature?: Tier2SignatureInput | null;
}

/**
 * THE idempotency key. One definition, used by both paths — a second definition is how two
 * paths start disagreeing about what "the same work" means.
 *
 * `<source>:<source_event_id>` makes a webhook retry structurally harmless: the schema's
 * UNIQUE (group_id, idempotency_key) rejects the duplicate, and appendTier2Entry returns the
 * entry that already exists rather than logging a second hour.
 */
export function contributionIdempotencyKey(source: string, sourceEventId: string): string {
  return `${source}:${sourceEventId}`;
}

/** Map an outbox event to a ledger entry. SHARED by the lane and the human path so the two
 *  cannot drift into producing different entries for the same work. */
export function contributionPayloadToEntry(
  groupId: string,
  source: string,
  sourceEventId: string,
  payload: ContributionPayload,
  signature: Tier2SignatureInput,
  countersignature?: Tier2SignatureInput | null,
): Tier2EntryInput {
  return {
    groupId,
    kind: payload.kind,
    // A personal contribution's subject is the member's own sub: `group_members` has no id
    // column, so the seat's identity in this projection IS (group_id, sub).
    subject: payload.subject ?? payload.sub,
    subjectKind: "seat",
    quantity: payload.quantity ?? null,
    unit: payload.unit ?? null,
    happenedAt: payload.happened_at ? new Date(payload.happened_at) : null,
    payload: payload.note ? { note: payload.note } : null,
    refs: payload.refs ?? [],
    idempotencyKey: contributionIdempotencyKey(source, sourceEventId),
    createdBy: payload.sub,
    signature,
    countersignature: countersignature ?? null,
  };
}

/** Validate a producer's payload. A malformed event is the PRODUCER's bug, so it must be
 *  dead-lettered rather than retried forever — see materializeContribution. */
export function assertContributionPayload(p: unknown): asserts p is ContributionPayload {
  const c = p as ContributionPayload & Record<string, unknown>;
  if (!c || typeof c !== "object") throw new Error("contribution payload must be an object");
  if (typeof c.sub !== "string" || !c.sub) throw new Error("contribution payload needs `sub`");
  if (typeof c.kind !== "string" || !c.kind) throw new Error("contribution payload needs `kind`");

  // JSON has no `undefined`, so a producer that omits an OPTIONAL field typically sends `null`.
  // Treating that as "not a number" dead-lettered the lane over a field that was optional to
  // begin with. Absent is absent, however it is spelled.
  for (const k of ["subject", "quantity", "unit", "happened_at", "note"]) {
    if (c[k] === null) delete c[k];
  }
  if (c.quantity !== undefined && (typeof c.quantity !== "number" || !Number.isFinite(c.quantity))) {
    throw new Error("contribution payload `quantity` must be a number");
  }
}

/**
 * The HUMAN path: append the entry and emit the event in ONE transaction.
 *
 * `client` must already be inside a transaction with `app.sub` set (i.e. from `withIdentity`)
 * — the append is RLS-checked against that identity, and the event row committing with it is
 * what keeps the record independent of the messaging layer's availability.
 */
/**
 * Emit a contribution event WITHOUT appending an entry — for a source that only observes the
 * work (a payment rail confirming funds, an integration's webhook). The Temporal lane
 * materialises the entry, so this path cannot diverge from the human path: both end at
 * appendTier2Entry with the same idempotency key.
 */
export async function emitContributionEvent(
  client: PoolClient,
  args: { groupId: string; source: string; sourceEventId: string; payload: ContributionPayload }
): Promise<string | null> {
  const { rows } = await client.query(
    "SELECT coop_emit_contribution($1, $2, $3, $4::jsonb) AS id",
    [args.groupId, args.source, args.sourceEventId, JSON.stringify(args.payload)]
  );
  return rows[0]?.id ?? null;
}

export async function recordContribution(
  client: PoolClient,
  input: ContributionInput,
): Promise<{ entry_id: string; seq: number; state: string; deduplicated: boolean; event_id: string }> {
  const entry = await appendTier2Entry(
    client,
    contributionPayloadToEntry(
      input.groupId, input.source, input.sourceEventId, input.payload,
      input.signature, input.countersignature,
    ),
  );

  // The event is the INTERFACE (notifications, digests, derived views all consume it), and it
  // commits with the entry so the two can never disagree about whether the work happened.
  //
  // It goes through coop_emit_contribution, NOT a raw INSERT: `events` has no user INSERT policy
  // (ingestion is a system write), so a direct insert fails RLS — and the function additionally
  // refuses a caller who is not a member of the target group, and is itself idempotent on
  // (source, source_event_id).
  const ev = await client.query(
    `SELECT coop_emit_contribution($1,$2,$3,$4::jsonb) AS id`,
    [input.groupId, input.source, input.sourceEventId, JSON.stringify(input.payload)],
  );

  return { ...entry, event_id: ev.rows[0].id };
}
