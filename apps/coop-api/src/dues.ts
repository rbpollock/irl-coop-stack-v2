import type { FastifyInstance } from "fastify";
import type { PoolClient } from "pg";
import { verifyBearer } from "./verify-jwt";
import { withIdentity } from "./db";
import { createHash } from "node:crypto";

// Dues — a PROJECTION, not an entry (docs/design/tier2-entry-model.md §5.1, §5.3).
//
// "Dues satisfied" is not a fact to record; it is a predicate computed over records
// that live in different tiers. Storing a boolean would create a second source of truth
// that eventually disagrees with the first. So this module computes, per obligation:
//
//   money          -> Tier 1 (UNAVAILABLE today: the treasury is unbuilt)
//   participation  -> Tier 2 `hours` / `swap` entries
//   in_kind        -> Tier 2 `in_kind` entries
//   stewardship    -> a role grant (holding the role IS the contribution)
//   coverage       -> a coverage proof (UNAVAILABLE today)
//   waiver         -> a decision or a bounded role grant
//
// Two rules carry the whole design:
//
//   1. THE POLICY IS A TABLE, NOT A LANGUAGE (§5.3). Obligations are a flat list and
//      "any" is the only connective. `validateDuesPolicy` refuses anything else at the
//      edge, so the convolution cannot accumulate: if a case does not fit the table, it
//      becomes a DECISION ("the group waived it"), not another rule.
//
//   2. A MODE WE CANNOT CHECK IS NEVER "NOT SATISFIED". An unevaluable mode reports
//      `unavailable` and the obligation is `undetermined` — never `false`. Reporting an
//      uncheckable obligation as unmet would tell a member they owe something on the
//      strength of a system that cannot see, which is the exact failure a money-boolean
//      would have produced.

export const DUES_CADENCES = ["weekly", "monthly", "quarterly", "seasonal", "annual"] as const;
export const DUES_MODES = ["money", "participation", "stewardship", "in_kind", "coverage", "waiver"] as const;
export const DUES_UNITS = ["hours", "items", "kg", "each"] as const;

export type DuesCadence = (typeof DUES_CADENCES)[number];
export type DuesMode = (typeof DUES_MODES)[number];

export interface DuesModeSpec {
  /** money / in_kind: a numeric threshold in the mode's own unit. */
  min?: number;
  min_hours?: number;
  /** in_kind counts RECORDED ENTRIES, not a valued equivalent: without a value oracle,
   *  valuing a crate of tomatoes would be an invented number (§5.3 rule 2). */
  min_entries?: number;
  /** stewardship: holding any of these roles satisfies the obligation. */
  roles?: string[];
  /** coverage: the minimum coverage level, from a fixed vocabulary. */
  min_level?: "covers_self" | "subsidizer";
  unit?: (typeof DUES_UNITS)[number];
}

export interface DuesObligation {
  id: string;
  cadence: DuesCadence;
  satisfied_if: "any";
  modes: Partial<Record<DuesMode, DuesModeSpec>>;
}

export interface DuesPolicy {
  version: number;
  grace_days: number;
  obligations: DuesObligation[];
  waiver: { by: Array<"vote" | "role">; max_periods?: number };
}

/** A policy that asks to nest, negate, or convert between modes. */
export class DuesPolicyError extends Error {}

// Words that mean "this is a rules engine" rather than "this is a table".
const NESTING = ["and", "or", "not", "all", "none", "if", "unless", "when", "rules", "expression", "where", "condition"];
const ARITHMETIC = ["equivalent", "equivalence", "conversion", "convert", "exchange", "rate", "prorate", "proration", "offset", "credit_toward", "credit_towards", "counts_toward", "partial"];
const CONCESSIONS = ["proration", "carry_over", "carryover", "rollover", "bands", "tiers", "hardship", "partial_credit", "deferral"];

/**
 * Validate and normalize a policy. Throws DuesPolicyError with the reason.
 *
 * This is where "a table, not a language" is enforced, so the rules are deliberately
 * strict and the messages name the violation rather than just refusing.
 */
export function validateDuesPolicy(raw: unknown): DuesPolicy {
  const p = raw as Record<string, any>;
  if (!p || typeof p !== "object") throw new DuesPolicyError("policy must be an object");

  const unknownTop = Object.keys(p).filter(
    (k) => !["version", "grace_days", "obligations", "waiver", "cadence"].includes(k),
  );
  for (const k of unknownTop) {
    if (CONCESSIONS.includes(k)) {
      throw new DuesPolicyError(
        `unknown key "${k}": grace_days is the ONLY concession knob (§5.3 rule 3) — express anything else as another obligation`);
    }
    throw new DuesPolicyError(`unknown key "${k}"`);
  }

  const cadence = String(p.cadence ?? "monthly");
  if (!(DUES_CADENCES as readonly string[]).includes(cadence)) {
    throw new DuesPolicyError(`cadence "${cadence}" is not in the bounded vocabulary: ${DUES_CADENCES.join("|")}`);
  }

  const graceDays = Number(p.grace_days ?? 0);
  if (!Number.isInteger(graceDays) || graceDays < 0 || graceDays > 90) {
    throw new DuesPolicyError("grace_days must be an integer 0..90");
  }

  if (!Array.isArray(p.obligations) || p.obligations.length === 0) {
    throw new DuesPolicyError("obligations must be a non-empty array (a group needing 'pay AND work' writes TWO obligations)");
  }

  const obligations: DuesObligation[] = p.obligations.map((o: any, i: number) => {
    if (!o || typeof o !== "object") throw new DuesPolicyError(`obligations[${i}] must be an object`);
    for (const k of Object.keys(o)) {
      if (NESTING.includes(k)) {
        throw new DuesPolicyError(
          `obligations[${i}]."${k}": a policy that nests is a rules engine — needing AND means TWO obligations (§5.3 rule 1)`);
      }
      if (!["id", "cadence", "satisfied_if", "modes"].includes(k)) {
        throw new DuesPolicyError(`obligations[${i}]."${k}" is not allowed`);
      }
    }
    const id = String(o.id ?? "");
    if (!/^[a-z0-9_-]{1,32}$/.test(id)) throw new DuesPolicyError(`obligations[${i}].id must be a short slug`);

    const sat = o.satisfied_if ?? "any";
    if (sat !== "any") {
      throw new DuesPolicyError(`obligations[${i}].satisfied_if must be "any" — the only connective (§5.3)`);
    }
    const oCadence = String(o.cadence ?? cadence);
    if (!(DUES_CADENCES as readonly string[]).includes(oCadence)) {
      throw new DuesPolicyError(`obligations[${i}].cadence "${oCadence}" is not in the bounded vocabulary`);
    }
    if (!o.modes || typeof o.modes !== "object" || !Object.keys(o.modes).length) {
      throw new DuesPolicyError(`obligations[${i}].modes must be a non-empty object`);
    }
    for (const [mode, spec] of Object.entries(o.modes as Record<string, any>)) {
      if (!(DUES_MODES as readonly string[]).includes(mode)) {
        throw new DuesPolicyError(`obligations[${i}].modes."${mode}" is not a known mode: ${DUES_MODES.join("|")}`);
      }
      for (const k of Object.keys(spec ?? {})) {
        if (ARITHMETIC.includes(k)) {
          throw new DuesPolicyError(
            `obligations[${i}].modes.${mode}."${k}": no arithmetic between modes — that is an exchange-rate table the group must maintain and keep honest (§5.3 rule 2)`);
        }
        if (!["min", "min_hours", "min_entries", "roles", "min_level", "unit"].includes(k)) {
          throw new DuesPolicyError(`obligations[${i}].modes.${mode}."${k}" is not allowed`);
        }
      }
      for (const numKey of ["min", "min_hours", "min_entries"]) {
        if (spec?.[numKey] !== undefined) {
          const n = Number(spec[numKey]);
          if (!Number.isFinite(n) || n < 0) {
            throw new DuesPolicyError(`obligations[${i}].modes.${mode}.${numKey} must be a number >= 0`);
          }
        }
      }
      if (spec?.unit !== undefined && !(DUES_UNITS as readonly string[]).includes(String(spec.unit))) {
        throw new DuesPolicyError(`obligations[${i}].modes.${mode}.unit is not in the bounded vocabulary: ${DUES_UNITS.join("|")}`);
      }
      if (spec?.roles !== undefined && (!Array.isArray(spec.roles) || !spec.roles.length)) {
        throw new DuesPolicyError(`obligations[${i}].modes.${mode}.roles must be a non-empty array`);
      }
    }
    return { id, cadence: oCadence as DuesCadence, satisfied_if: "any", modes: o.modes };
  });

  const ids = obligations.map((o) => o.id);
  if (new Set(ids).size !== ids.length) throw new DuesPolicyError("obligation ids must be unique");

  const w = (p.waiver ?? {}) as Record<string, any>;
  const by = Array.isArray(w.by) ? w.by.map(String) : ["vote"];
  for (const b of by) {
    if (b !== "vote" && b !== "role") throw new DuesPolicyError(`waiver.by entries must be "vote" or "role", got "${b}"`);
  }
  if (by.includes("role") && (w.max_periods === undefined || Number(w.max_periods) < 1)) {
    // a role-granted waiver without a bound is a standing power (§5.2)
    throw new DuesPolicyError("waiver.max_periods is REQUIRED when a role may grant waivers — otherwise the role can waive indefinitely");
  }

  return {
    version: Number(p.version ?? 1),
    grace_days: graceDays,
    obligations,
    waiver: { by: by as Array<"vote" | "role">, max_periods: w.max_periods === undefined ? undefined : Number(w.max_periods) },
  };
}

/** The period a date falls in, for a cadence. Seasons are indexed from March. */
export function duesPeriodRange(cadence: DuesCadence, at: Date): { start: string; end: string } {
  const y = at.getUTCFullYear();
  const m = at.getUTCMonth(); // 0-11
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const mk = (y2: number, m2: number, d2: number) => new Date(Date.UTC(y2, m2, d2));
  switch (cadence) {
    case "weekly": {
      const dow = (at.getUTCDay() + 6) % 7; // Monday = 0
      const start = mk(y, m, at.getUTCDate() - dow);
      return { start: iso(start), end: iso(mk(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate() + 6)) };
    }
    case "monthly":
      return { start: iso(mk(y, m, 1)), end: iso(mk(y, m + 1, 0)) };
    case "quarterly": {
      const q = Math.floor(m / 3) * 3;
      return { start: iso(mk(y, q, 1)), end: iso(mk(y, q + 3, 0)) };
    }
    case "seasonal": {
      const shifted = (m - 2 + 12) % 12;       // March = 0
      const s = 2 + Math.floor(shifted / 3) * 3; // 2, 5, 8, 11
      const sy = m >= 2 ? y : y - 1;            // Dec-Feb belongs to the winter that began in the prior year
      return { start: iso(mk(sy, s, 1)), end: iso(mk(sy, s + 3, 0)) };
    }
    case "annual":
      return { start: iso(mk(y, 0, 1)), end: iso(mk(y, 11, 31)) };
  }
}

export type ModeResult = "met" | "not-met" | "unavailable";
export interface ModeOutcome {
  mode: DuesMode;
  result: ModeResult;
  detail?: string;
}
/** The redacted view: the OUTCOME only. Naming the mode at all leaks it — "paid" leaks
 *  financial capacity and "participated" leaks that they could not pay. */
export interface RedactedModeOutcome {
  result: ModeResult;
}
export interface ObligationOutcome {
  id: string;
  /** true only when a mode MET it. */
  satisfied: boolean;
  /** true when no available mode could decide it — the honest third state. */
  undetermined: boolean;
  /** which mode satisfied it. OMITTED unless the caller may see it (§5.1 mode hiding). */
  via?: DuesMode;
  modes: Array<ModeOutcome | RedactedModeOutcome>;
}
export interface DuesEvaluation {
  policy_version: number;
  periods: { obligation: string; start: string; end: string }[];
  obligations: ObligationOutcome[];
  satisfied: boolean;
  undetermined: boolean;
}

// The two modes whose source of truth does not exist yet. Reported, never guessed.
const UNAVAILABLE: Partial<Record<DuesMode, string>> = {
  money: "no Tier-1 source: the treasury contract is unbuilt, and a payment is a Tier-1 fact (money-in-and-out.md §5)",
  coverage: "no coverage-proof verifier yet (federation contribution is designed, not built)",
};

async function resolveParticipation(client: PoolClient, groupId: string, sub: string, start: string, end: string, spec: DuesModeSpec) {
  const r = await client.query(
    `SELECT coalesce(sum(quantity), 0)::float AS total, count(*)::int AS n
       FROM tier2_entry
      WHERE group_id = $1 AND created_by = $2
        AND kind IN ('hours','swap')
        AND unit = 'hours'
        AND state IN ('countersigned','ratified')
        AND period >= $3::date AND period <= $4::date`,
    [groupId, sub, start, end],
  );
  const total = r.rows[0].total;
  const need = Number(spec.min_hours ?? 0);
  return need > 0 && total >= need
    ? { result: "met" as ModeResult, detail: `${total}h of ${need}h` }
    : { result: "not-met" as ModeResult, detail: `${total}h of ${need}h` };
}

async function resolveInKind(client: PoolClient, groupId: string, sub: string, start: string, end: string, spec: DuesModeSpec) {
  const r = await client.query(
    `SELECT count(*)::int AS n FROM tier2_entry
      WHERE group_id = $1 AND created_by = $2 AND kind = 'in_kind'
        AND state IN ('countersigned','ratified')
        AND period >= $3::date AND period <= $4::date`,
    [groupId, sub, start, end],
  );
  const need = Number(spec.min_entries ?? 1);
  return r.rows[0].n >= need
    ? { result: "met" as ModeResult, detail: `${r.rows[0].n} entries` }
    : { result: "not-met" as ModeResult, detail: `${r.rows[0].n} of ${need} entries` };
}

async function resolveStewardship(client: PoolClient, groupId: string, sub: string, spec: DuesModeSpec) {
  const wanted: string[] = (spec.roles ?? []).map(String);
  if (!wanted.length) return { result: "not-met" as ModeResult, detail: "no roles configured" };
  const r = await client.query(
    `SELECT roles FROM group_members WHERE group_id = $1 AND sub = $2`,
    [groupId, sub],
  );
  const held: string[] = r.rows[0]?.roles ?? [];
  const hit = wanted.filter((w) => held.includes(w));
  return hit.length
    ? { result: "met" as ModeResult, detail: `holds ${hit.join(",")}` }
    : { result: "not-met" as ModeResult, detail: `holds none of ${wanted.join(",")}` };
}

async function resolveWaiver(client: PoolClient, groupId: string, sub: string, obligation: string, start: string, end: string) {
  const r = await client.query(
    `SELECT granted_by FROM dues_waiver
      WHERE group_id = $1 AND sub = $2 AND obligation = $3 AND period >= $4::date AND period <= $5::date
      LIMIT 1`,
    [groupId, sub, obligation, start, end],
  );
  return r.rowCount
    ? { result: "met" as ModeResult, detail: `waived (${r.rows[0].granted_by})` }
    : { result: "not-met" as ModeResult, detail: "no waiver" };
}

/**
 * Evaluate a member's dues for the period containing `at`.
 *
 * `reveal` defaults to FALSE and the redaction is REAL: the caller gets satisfied /
 * undetermined per obligation plus the OUTCOME of each mode considered — never the mode
 * name and never an amount. Returning "participation: met (6h of 4h)" would leak the
 * mode completely even with `via` withheld, which is the leak §5.1 forbids. A third
 * party should get `duesStatement` instead, which carries no per-mode data at all.
 */
export async function evaluateDues(
  client: PoolClient,
  groupId: string,
  sub: string,
  policy: DuesPolicy,
  at: Date = new Date(),
  reveal = false,
): Promise<DuesEvaluation> {
  const obligations: ObligationOutcome[] = [];
  const periods: DuesEvaluation["periods"] = [];

  for (const ob of policy.obligations) {
    const { start, end } = duesPeriodRange(ob.cadence, at);
    periods.push({ obligation: ob.id, start, end });
    const modes: ModeOutcome[] = [];
    let via: DuesMode | undefined;

    // Iterate in the FIXED vocabulary order, not key order. A policy's modes are
    // alternatives with no priority, but `via` still has to be deterministic — and jsonb
    // does not preserve insertion order (it sorts keys by length), so storage order would
    // silently decide which satisfying mode gets reported.
    const ordered = (Object.entries(ob.modes) as Array<[DuesMode, DuesModeSpec]>)
      .sort((a, b) => DUES_MODES.indexOf(a[0]) - DUES_MODES.indexOf(b[0]));
    for (const [mode, spec] of ordered) {
      const na = UNAVAILABLE[mode];
      if (na) {
        modes.push({ mode, result: "unavailable", detail: na });
        continue;
      }
      let out: { result: ModeResult; detail?: string };
      switch (mode) {
        case "participation": out = await resolveParticipation(client, groupId, sub, start, end, spec); break;
        case "in_kind":       out = await resolveInKind(client, groupId, sub, start, end, spec); break;
        case "stewardship":   out = await resolveStewardship(client, groupId, sub, spec); break;
        case "waiver":        out = await resolveWaiver(client, groupId, sub, ob.id, start, end); break;
        default:              out = { result: "unavailable", detail: "no resolver" };
      }
      modes.push({ mode, ...out });
      if (out.result === "met" && !via) via = mode;
    }

    const satisfied = modes.some((m) => m.result === "met");
    const undetermined = !satisfied && modes.length > 0 && modes.every((m) => m.result === "unavailable");
    obligations.push({
      id: ob.id,
      satisfied,
      undetermined,
      // `undetermined` is a first-class outcome: if every mode is unevaluable we say so
      // rather than reporting an unmet obligation on the strength of a system that
      // cannot see. When not revealing, the modes collapse to bare outcomes.
      ...(reveal && via ? { via } : {}),
      modes: reveal ? modes : modes.map((m) => ({ result: m.result })),
    });
  }

  return {
    policy_version: policy.version,
    periods,
    obligations,
    satisfied: obligations.every((o) => o.satisfied),
    undetermined: obligations.some((o) => o.undetermined),
  };
}

/**
 * The minimal-disclosure statement: what a member can show a third party.
 *
 * It carries a BOOLEAN and counts — never a mode, never an amount. `member` is hashed
 * so the statement itself does not broadcast a sub. `digest` is the canonical form's
 * hash, so a signature by the group's key can attach to exactly this statement later;
 * it is UNSIGNED today and says so, because an unsigned boolean proves nothing to
 * anyone who does not already trust the holder.
 */
export function duesStatement(
  groupId: string,
  sub: string,
  ev: DuesEvaluation,
): {
  group_id: string;
  member: string;
  policy_version: number;
  period_start: string;
  period_end: string;
  satisfied: boolean;
  undetermined: boolean;
  obligations_satisfied: number;
  obligations_total: number;
  signed: boolean;
} {
  const periods = ev.periods.map((p) => p.start).sort();
  return {
    group_id: groupId,
    member: createHash("sha256").update(sub).digest("hex").slice(0, 32),
    policy_version: ev.policy_version,
    period_start: periods[0] ?? "",
    period_end: ev.periods.map((p) => p.end).sort().slice(-1)[0] ?? "",
    satisfied: ev.satisfied,
    undetermined: ev.undetermined,
    obligations_satisfied: ev.obligations.filter((o) => o.satisfied).length,
    obligations_total: ev.obligations.length,
    signed: false,
  };
}

// ---------------------------------------------------------------------------
// Routes. Two authorization rules carry the whole surface:
//
//   * drafting a policy needs `dues.policy.write`; ADOPTING one needs a PASSED
//     DECISION. A role that could activate a policy unilaterally could change what
//     every member owes, which is the capture §5.3.6 forbids.
//   * reading another member's dues needs `dues.bookkeep`. There is no route that
//     returns a roster of dues: the group gets a COUNT, the member gets their own
//     status, and nothing else exists to call.
// ---------------------------------------------------------------------------

async function hasGrant(client: PoolClient, groupId: string, grant: string): Promise<boolean> {
  const r = await client.query("SELECT coop_has_grant($1,$2) AS g", [groupId, grant]);
  return r.rows[0]?.g === true;
}
async function isMember(client: PoolClient, groupId: string): Promise<boolean> {
  const r = await client.query("SELECT coop_is_member($1) AS m", [groupId]);
  return r.rows[0]?.m === true;
}

/** Re-validate a stored policy rather than trusting the row: it proves the table can
 *  only ever hold table-shaped policies, whatever wrote them. */
function policyFromRow(row: any): DuesPolicy {
  return validateDuesPolicy({
    version: row.version, cadence: row.cadence, grace_days: row.grace_days,
    obligations: row.obligations, waiver: row.waiver,
  });
}

export default async function duesRoutes(fastify: FastifyInstance): Promise<void> {
  // The group's policy: the active version, plus any newer drafts awaiting a decision.
  fastify.get("/api/v1/groups/:id/dues/policy", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    return withIdentity(claims.sub, async (client) => {
      if (!(await isMember(client, groupId))) return reply.code(403).send({ error: "not a group member" });
      const r = await client.query(
        `SELECT version, cadence, grace_days, obligations, waiver, status, decided_by, created_at
           FROM dues_policy WHERE group_id = $1 ORDER BY version DESC`,
        [groupId],
      );
      const active = r.rows.find((x) => x.status === "active") ?? null;
      return {
        active: active ? { ...active, policy: policyFromRow(active) } : null,
        drafts: r.rows.filter((x) => x.status === "draft").map(({ version, created_at }) => ({ version, created_at })),
        history: r.rows.map(({ version, status, decided_by, created_at }) => ({ version, status, decided_by, created_at })),
      };
    });
  });

  // Draft a new version. Never activates: adoption is a separate, decided act.
  fastify.put("/api/v1/groups/:id/dues/policy", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const body = (request.body ?? {}) as Record<string, unknown>;
    let policy: DuesPolicy;
    try {
      policy = validateDuesPolicy(body);
    } catch (err) {
      // the validator's messages are the point: they name the violation
      return reply.code(400).send({ error: (err as Error).message });
    }
    return withIdentity(claims.sub, async (client) => {
      if (!(await hasGrant(client, groupId, "dues.policy.write"))) {
        return reply.code(403).send({ error: "dues.policy.write required" });
      }
      const next = await client.query(
        "SELECT coalesce(max(version), 0) + 1 AS v FROM dues_policy WHERE group_id = $1", [groupId]);
      const version = Number(next.rows[0].v);
      await client.query(
        `INSERT INTO dues_policy (group_id, version, cadence, grace_days, obligations, waiver, status, created_by)
         VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,'draft',$7)`,
        [groupId, version, String((body as any).cadence ?? "monthly"), policy.grace_days,
         JSON.stringify(policy.obligations), JSON.stringify(policy.waiver), claims.sub],
      );
      return { version, status: "draft",
        next: `adopt it with POST /api/v1/groups/${groupId}/dues/policy/${version}/adopt and a passed decision` };
    });
  });

  // Adopt a draft: requires a decision that PASSED in this group.
  fastify.post("/api/v1/groups/:id/dues/policy/:version/adopt", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const { id: groupId, version } = request.params as any;
    const decisionId = String(((request.body ?? {}) as any).decision_id ?? "");
    if (!/^[0-9a-f-]{36}$/i.test(decisionId)) {
      return reply.code(400).send({ error: "decision_id is required: adopting a policy is a vote, not a click" });
    }
    return withIdentity(claims.sub, async (client) => {
      if (!(await hasGrant(client, groupId, "dues.policy.write"))) {
        return reply.code(403).send({ error: "dues.policy.write required" });
      }
      const d = await client.query("SELECT group_id, status FROM proposals WHERE id = $1", [decisionId]);
      if (!d.rowCount) return reply.code(404).send({ error: "decision not found" });
      if (d.rows[0].group_id !== groupId) return reply.code(400).send({ error: "decision belongs to another group" });
      if (d.rows[0].status !== "passed") {
        return reply.code(409).send({ error: `decision is "${d.rows[0].status}", not passed` });
      }
      const draft = await client.query(
        "SELECT version, status FROM dues_policy WHERE group_id = $1 AND version = $2", [groupId, Number(version)]);
      if (!draft.rowCount) return reply.code(404).send({ error: "version not found" });
      if (draft.rows[0].status === "active") return { version: Number(version), status: "active", changed: false };

      // supersede then activate, in one transaction: one active policy per group is also
      // enforced by a partial unique index, so a race cannot leave two
      await client.query("UPDATE dues_policy SET status = 'superseded' WHERE group_id = $1 AND status = 'active'", [groupId]);
      await client.query(
        "UPDATE dues_policy SET status = 'active', decided_by = $2 WHERE group_id = $1 AND version = $3",
        [groupId, decisionId, Number(version)]);
      return { version: Number(version), status: "active", decided_by: decisionId, changed: true };
    });
  });

  // My own dues. `reveal` is TRUE here and only here: a member's own modes are their own.
  fastify.get("/api/v1/groups/:id/dues/me", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    return withIdentity(claims.sub, async (client) => {
      if (!(await isMember(client, groupId))) return reply.code(403).send({ error: "not a group member" });
      const r = await client.query(
        "SELECT * FROM dues_policy WHERE group_id = $1 AND status = 'active' LIMIT 1", [groupId]);
      if (!r.rowCount) return reply.code(404).send({ error: "this group has no active dues policy" });
      const policy = policyFromRow(r.rows[0]);
      const ev = await evaluateDues(client, groupId, claims.sub, policy, new Date(), true);
      const has = await hasGrant(client, groupId, "dues.bookkeep");
      return {
        ...ev,
        policy_version: policy.version,
        // the statement is what a member shows a third party: boolean and counts only
        statement: duesStatement(groupId, claims.sub, ev),
        can_bookkeep: has,
        // the honest reminder, on the payload rather than in a footnote
        note: ev.undetermined
          ? "At least one obligation rests on a mode with no source of truth yet (money: the treasury is unbuilt; coverage: no verifier). It is reported as undetermined, NOT as unmet."
          : undefined,
      };
    });
  });

  // Record a waiver. Bounded and never self-granted.
  fastify.post("/api/v1/groups/:id/dues/waiver", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    const b = (request.body ?? {}) as Record<string, any>;
    const sub = String(b.sub ?? "");
    const obligation = String(b.obligation ?? "");
    if (!sub || !obligation) return reply.code(400).send({ error: "sub and obligation are required" });
    if (sub === claims.sub) {
      return reply.code(403).send({ error: "a waiver may not be self-granted — the vote path exists for exactly this case" });
    }
    return withIdentity(claims.sub, async (client) => {
      if (!(await hasGrant(client, groupId, "dues.bookkeep"))) {
        return reply.code(403).send({ error: "dues.bookkeep required" });
      }
      const pr = await client.query(
        "SELECT * FROM dues_policy WHERE group_id = $1 AND status = 'active' LIMIT 1", [groupId]);
      if (!pr.rowCount) return reply.code(404).send({ error: "this group has no active dues policy" });
      const policy = policyFromRow(pr.rows[0]);
      if (!policy.waiver.by.includes("role")) {
        return reply.code(403).send({ error: "this group's policy grants waivers by vote only" });
      }
      if (!policy.obligations.some((o) => o.id === obligation)) {
        return reply.code(400).send({ error: `no such obligation: ${policy.obligations.map((o) => o.id).join(",")}` });
      }
      // the bound: max_periods distinct periods per member per obligation
      const max = Number(policy.waiver.max_periods ?? 0);
      const used = await client.query(
        `SELECT count(DISTINCT period)::int AS n FROM dues_waiver
          WHERE group_id = $1 AND sub = $2 AND obligation = $3 AND granted_by = 'role'`,
        [groupId, sub, obligation]);
      if (used.rows[0].n >= max) {
        return reply.code(409).send({ error: `role-granted waivers are bounded at ${max} period(s) for this obligation; a vote must extend it` });
      }
      const period = String(b.period ?? new Date().toISOString().slice(0, 10));
      await client.query(
        `INSERT INTO dues_waiver (group_id, sub, period, obligation, granted_by, authority, granted_by_sub, note)
         VALUES ($1,$2,$3,$4,'role',$5,$6,$7)
         ON CONFLICT (group_id, sub, period, obligation) DO NOTHING`,
        [groupId, sub, period, obligation, `role:${claims.sub}`, claims.sub, b.note ? String(b.note).slice(0, 500) : null]);
      return { ok: true, sub, obligation, period, granted_by: "role", bound: `${used.rows[0].n + 1}/${max} periods used` };
    });
  });

  // The group's view: counts, never rows.
  fastify.get("/api/v1/groups/:id/dues/summary", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    const groupId = (request.params as any).id;
    return withIdentity(claims.sub, async (client) => {
      if (!(await isMember(client, groupId))) return reply.code(403).send({ error: "not a group member" });
      const pr = await client.query(
        "SELECT version, cadence FROM dues_policy WHERE group_id = $1 AND status = 'active' LIMIT 1", [groupId]);
      if (!pr.rowCount) return reply.code(404).send({ error: "this group has no active dues policy" });
      const { start, end } = duesPeriodRange(pr.rows[0].cadence as DuesCadence, new Date());
      const counts = await client.query(
        "SELECT obligation, n FROM coop_dues_waiver_counts($1,$2,$3)", [groupId, start, end]);
      return {
        policy_version: pr.rows[0].version,
        period: { start, end },
        // count-only by construction: the function returns no sub, no reason, no period detail
        waivers: counts.rows,
        waivers_total: counts.rows.reduce((a: number, r: any) => a + r.n, 0),
        note: "counts only. Which mode satisfied WHICH member is not exposed by any route; the member sees their own, a bookkeeper may record a waiver they cannot see in a roster.",
      };
    });
  });
}
