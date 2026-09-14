import type { FastifyInstance } from "fastify";
import { createHash } from "node:crypto";
import { verifyBearer } from "./verify-jwt";
import { withIdentity, countersignTier2Entry, isAttestingClass, type Tier2SignatureClass } from "./db";
import {
  CONTRIBUTION_KINDS,
  CONTRIBUTION_SOURCES,
  assertContributionPayload,
  recordContribution,
  type ContributionPayload,
  type ContributionSource,
} from "./tier2-contributions";

// The member-facing write path for the participation ledger (tier2-entry-model.md §3.2, §5.6).
//
// Two verbs, and the split between them is the whole point:
//
//   POST .../contributions            "I did this"      -> a `proposed` entry, self-asserted
//   POST .../entries/:id/countersign  "I saw this"      -> an ATTESTATION
//
// A self-logged entry carries a `member` signature and therefore basis `machine-only` — which
// means, by §6, that it can NEVER affect a Tier-1 outcome until a role holder or a vote touches
// it. Logging your own hours does not create a claim on money; it creates a claim someone else
// has to see.
//
// A note on what a signature IS here: the request is authenticated by a bearer token, so `sig`
// is a hash of that token — a SESSION MARKER. It attributes the entry to a session, it does not
// prove the body. Verifiable signatures (EIP-191 over the canonical body, which `tier2EntryBody`
// already emits) are the follow-on, and nothing Tier-1-eligible depends on the weaker version
// because the basis is machine-only.

const sessionMarker = (authHeader: string | undefined): string =>
  "session:" + createHash("sha256").update(authHeader ?? "").digest("hex").slice(0, 32);

async function isMember(client: any, groupId: string): Promise<boolean> {
  const r = await client.query("SELECT coop_is_member($1) AS m", [groupId]);
  return r.rows[0]?.m === true;
}
async function hasGrant(client: any, groupId: string, grant: string): Promise<boolean> {
  const r = await client.query("SELECT coop_has_grant($1,$2) AS g", [groupId, grant]);
  return r.rows[0]?.g === true;
}

export default async function tier2Routes(fastify: FastifyInstance): Promise<void> {
  // Log work. Self by default; on another member's behalf with tier2.attest.
  fastify.post("/api/v1/groups/:id/contributions", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const b = (request.body ?? {}) as Record<string, any>;
    const marker = sessionMarker(request.headers.authorization);

    const kind = String(b.kind ?? "");
    if (!(CONTRIBUTION_KINDS as readonly string[]).includes(kind)) {
      return reply.code(400).send({ error: `kind must be one of ${CONTRIBUTION_KINDS.join("|")}` });
    }
    const source = String(b.source ?? "manual");
    if (!(CONTRIBUTION_SOURCES as readonly string[]).includes(source)) {
      return reply.code(400).send({ error: `source must be one of ${CONTRIBUTION_SOURCES.join("|")}` });
    }
    // The idempotency key is `<source>:<source_event_id>`. A UI should generate the id when the
    // form OPENS, not on submit — otherwise a retry of the same submit double-logs the hours.
    const sourceEventId = String(b.source_event_id ?? "") || `manual-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

    const sub = String(b.sub ?? claims.sub);
    const forOther = sub !== claims.sub;

    return withIdentity(claims.sub, async (client) => {
      if (!(await isMember(client, groupId))) return reply.code(403).send({ error: "not a group member" });

      // Recording work someone else did is an ORGANIZER act, not a member act. It is also the
      // clipboard case from coop-work-signup-checkoff.md.
      if (forOther && !(await hasGrant(client, groupId, "tier2.attest"))) {
        return reply.code(403).send({ error: "tier2.attest required to log work on another member's behalf" });
      }

      const payload: ContributionPayload = {
        sub,
        kind: kind as any,
        subject: b.subject ? String(b.subject) : undefined,
        quantity: typeof b.quantity === "number" ? b.quantity : undefined,
        unit: b.unit ? String(b.unit) : undefined,
        happened_at: b.happened_at ? String(b.happened_at) : undefined,
        refs: Array.isArray(b.refs) ? b.refs.map(String).slice(0, 20) : undefined,
        note: b.note ? String(b.note).slice(0, 500) : undefined,
      };
      try {
        assertContributionPayload(payload);
      } catch (err) {
        return reply.code(400).send({ error: (err as Error).message });
      }

      // An organizer may confirm in the same breath (the work-signup doc's organizer-confirm
      // mode). Allowed precisely because the counter-signer is NOT the beneficiary.
      const wantCountersign = b.countersign === true;
      if (wantCountersign && !forOther) {
        return reply.code(400).send({
          error: "a counter-signature must come from someone other than the beneficiary — log your own work and let someone else confirm it",
        });
      }
      const sig = {
        signer: claims.sub, class: "member" as Tier2SignatureClass,
        authority: `session:${claims.sub}`, validFrom: new Date(), validTo: null,
        signedAt: new Date(), sig: marker,
      };
      const countersig = wantCountersign
        ? { signer: claims.sub, class: "role-holder" as Tier2SignatureClass, authority: "tier2.attest",
            validFrom: new Date(), validTo: null, signedAt: new Date(), sig: marker }
        : null;

      try {
        const r = await recordContribution(client, {
          groupId, source: source as ContributionSource, sourceEventId, payload,
          signature: sig, countersignature: countersig,
        });
        return {
          ...r,
          basis: countersig && isAttestingClass(countersig.class) ? "attested" : "machine-only",
          note: countersig
            ? "confirmed by an organizer in the same request"
            : "self-asserted: usable for display, and NOT eligible for a Tier-1 outcome until a role holder or a vote attests it",
        };
      } catch (err) {
        return reply.code(409).send({ error: (err as Error).message });
      }
    });
  });

  // Attest an entry: "I saw this happen", or the group accepting it by vote.
  fastify.post("/api/v1/groups/:id/entries/:entryId/countersign", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const { id: groupId, entryId } = request.params as any;
    const b = (request.body ?? {}) as Record<string, any>;
    const decisionId = b.decision_id ? String(b.decision_id) : null;
    const marker = sessionMarker(request.headers.authorization);

    return withIdentity(claims.sub, async (client) => {
      if (!(await isMember(client, groupId))) return reply.code(403).send({ error: "not a group member" });

      // Two authority paths, per §3.2: a role holder witnessing, or the group by quorum.
      let cls: Tier2SignatureClass = "role-holder";
      let authority = "tier2.attest";
      if (decisionId) {
        const d = await client.query("SELECT group_id, status FROM proposals WHERE id = $1", [decisionId]);
        if (!d.rowCount) return reply.code(404).send({ error: "decision not found" });
        if (d.rows[0].group_id !== groupId) return reply.code(400).send({ error: "decision belongs to another group" });
        if (d.rows[0].status !== "passed") {
          return reply.code(409).send({ error: `decision is "${d.rows[0].status}", not passed` });
        }
        cls = "group-vote";
        authority = decisionId;
      } else if (!(await hasGrant(client, groupId, "tier2.attest"))) {
        return reply.code(403).send({
          error: "tier2.attest required to attest — or pass a passed decision_id for the group to attest by vote",
        });
      }

      try {
        const r = await countersignTier2Entry(client, entryId, groupId, {
          signer: claims.sub, class: cls, authority,
          validFrom: new Date(), validTo: null, signedAt: new Date(), sig: marker,
        });
        return { ...r, entry_id: entryId, attested_by: cls };
      } catch (err) {
        return reply.code(409).send({ error: (err as Error).message });
      }
    });
  });

  // Read entries. Yours by default; `?pending=1` needs tier2.attest, since it is other people's
  // unattested claims — which the group may see (§9 open question 3's instinct: hide nothing
  // WITHIN a group; the restriction is on Tier-1 eligibility, not visibility).
  fastify.get("/api/v1/groups/:id/entries", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const pending = ((request.query as any)?.pending ?? "") === "1";

    return withIdentity(claims.sub, async (client) => {
      if (!(await isMember(client, groupId))) return reply.code(403).send({ error: "not a group member" });
      if (pending && !(await hasGrant(client, groupId, "tier2.attest"))) {
        return reply.code(403).send({ error: "tier2.attest required to list the group's pending entries" });
      }
      const r = await client.query(
        `SELECT e.entry_id, e.seq, e.period, e.kind, e.subject, e.quantity, e.unit,
                e.happened_at, e.recorded_at, e.state, e.basis, e.created_by,
                (SELECT count(*)::int FROM tier2_signature s WHERE s.entry_id = e.entry_id) AS signatures
           FROM tier2_entry e
          WHERE e.group_id = $1
            AND ($2::bool OR e.created_by = $3)
            AND ($2::bool = false OR e.state = 'proposed')
          ORDER BY e.seq DESC
          LIMIT 100`,
        [groupId, pending, claims.sub],
      );
      return {
        entries: r.rows,
        note: "an entry's basis is machine-only until someone other than the beneficiary attests it; only ratified/attested entries can reach a Tier-1 outcome",
      };
    });
  });
}
