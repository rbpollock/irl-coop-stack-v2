import { Pool, PoolClient } from "pg";
import { createHash } from "node:crypto";

// coop-api ↔ Citus `irlcoop` — the group projection store (Layer 2). The
// on-chain Safe (Layer 1) holds the truth; these tables are a rebuildable
// projection apps read (group, membership seats, resource scopes).
// Replaces the JSON-file profile store as coop-api's first real database.
// Password comes from the generator-emitted secrets.env (POSTGRES_COOP,
// derived from ${SECRET:postgres.coop}); the other params default to the local
// Citus coordinator. COOP_DB_PASSWORD is a hand-set .env override if ever needed.
const pool = new Pool({
  host: process.env.COOP_DB_HOST ?? "172.17.0.1",
  port: Number(process.env.COOP_DB_PORT ?? 5432),
  user: process.env.COOP_DB_USER ?? "coop",
  password: process.env.COOP_DB_PASSWORD ?? process.env.POSTGRES_COOP ?? "",
  database: process.env.COOP_DB_NAME ?? "irlcoop",
  max: 5,
});

// Least-privilege operator pool for platform-admin promotion/demotion. Connects
// as `coop_ops` (LOGIN, EXECUTE-only on the two promotion functions — no table
// grants, not superuser) so the app's main `coop` pool can never self-promote.
// The password is the derived secret ${SECRET:coop.ops} (env COOP_OPS).
const opsPool = new Pool({
  host: process.env.COOP_DB_HOST ?? "172.17.0.1",
  port: Number(process.env.COOP_DB_PORT ?? 5432),
  user: "coop_ops",
  password: process.env.COOP_OPS ?? "",
  database: process.env.COOP_DB_NAME ?? "irlcoop",
  max: 1,
});

// Idempotent schema — coop-api self-provisions its projection tables on boot.
// gen_random_uuid() is built into Postgres 13+ (Citus is 16), no extension.
const DDL = `
CREATE TABLE IF NOT EXISTS groups (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  safe_address text,
  name        text NOT NULL,
  slug        text,
  description text,
  privacy     text NOT NULL DEFAULT 'members' CHECK (privacy IN ('open','members','hidden')),
  kind        text NOT NULL DEFAULT 'coop' CHECK (kind IN ('coop','personal')),
  created_by  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- Canonical group slug ({slug}.irl.coop → group). Nullable: a personal group
-- (kind='personal') has no public subdomain — it is addressed by its member
-- identity, not a name. Unique among the named groups that DO carry one.
ALTER TABLE groups ADD COLUMN IF NOT EXISTS slug text;
CREATE UNIQUE INDEX IF NOT EXISTS groups_slug_uniq
  ON groups (slug) WHERE slug IS NOT NULL;


-- A user's OWN group (groups.kind='personal', created_by=sub, seated by
-- coop_ensure_personal_group) is their telephony identity — enforce one per sub
-- at the DB level so no race can mint a second. The extension-identity binding
-- (docs/design/telephony.md) rests on it. kind here is only the own-group
-- marker, not a telephony distinction.
CREATE UNIQUE INDEX IF NOT EXISTS groups_personal_created_by_uniq
  ON groups (created_by) WHERE kind = 'personal';

CREATE TABLE IF NOT EXISTS group_members (
  group_id    uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  sub         text,
  roles       text[] NOT NULL DEFAULT '{}',
  alias       text,
  visibility  text NOT NULL DEFAULT 'canonical' CHECK (visibility IN ('role-only','alias','canonical')),
  holder_kind text NOT NULL DEFAULT 'person' CHECK (holder_kind IN ('person','group')),
  holder_safe text,
  holder_key  text GENERATED ALWAYS AS (COALESCE(holder_safe, sub)) STORED,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Seat holders are Safes (D-16 — docs/design/seat-holder-is-a-safe.md). A group
-- seat has no person, so the person cannot be the uniqueness key — the holder is.
-- The primary key is deliberately NOT (group_id, sub); the table is a projection
-- whose identity is the holder. Applied to existing databases by the ALTER block
-- below (CREATE TABLE IF NOT EXISTS is a no-op once the table exists).
ALTER TABLE group_members ADD COLUMN IF NOT EXISTS holder_kind text NOT NULL DEFAULT 'person';
ALTER TABLE group_members ADD COLUMN IF NOT EXISTS holder_safe text;
-- ORDER MATTERS: sub is implicitly NOT NULL while it is part of the primary key,
-- so the key must be dropped BEFORE the NOT NULL can be relaxed.
-- (No backticks in this block: the DDL is a JS template literal.)
ALTER TABLE group_members DROP CONSTRAINT IF EXISTS group_members_pkey;
ALTER TABLE group_members ALTER COLUMN sub DROP NOT NULL;
ALTER TABLE group_members ADD COLUMN IF NOT EXISTS holder_key text
  GENERATED ALWAYS AS (COALESCE(holder_safe, sub)) STORED;
CREATE UNIQUE INDEX IF NOT EXISTS group_members_holder_uniq
  ON group_members (group_id, holder_key);

CREATE TABLE IF NOT EXISTS resource_scopes (
  group_id     uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  app          text NOT NULL,
  resource_key text NOT NULL,
  scoped_by    text NOT NULL,
  scoped_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (group_id, app, resource_key)
);

-- The event store: raw, typed events (the bus's source of truth). 'source'
-- is the changeable app (matrix, email, ...), NOT part of any id — the stable
-- domain lives in the Redis channel (irl:communication:events) and the 'type'
-- is the source's own event kind. 'group_id' is the RLS scope (a sender's
-- personal group today; room-to-group via resource_scopes later).
CREATE TABLE IF NOT EXISTS events (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id        uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  source          text NOT NULL,
  source_event_id text,
  type            text NOT NULL,
  payload         jsonb NOT NULL DEFAULT '{}',
  occurred_at     timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS events_dedup_idx ON events (source, source_event_id) WHERE source_event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS events_group_time_idx ON events (group_id, occurred_at DESC);

-- Delivery outbox marker (option A): NULL = not yet claimed by the delivery
-- sweep. The Temporal deliverySweep workflow claims undelivered events and
-- stamps delivered_at once a delivery channel (Stalwart/Matrix/...) accepts
-- them. Idempotent; the event store itself is the durable buffer.
ALTER TABLE events ADD COLUMN IF NOT EXISTS delivered_at timestamptz;
CREATE INDEX IF NOT EXISTS events_undelivered_idx ON events (occurred_at) WHERE delivered_at IS NULL;

-- Read-state: which notifications a user has read or cleared. User-scoped
-- (NOT group-scoped) — a notification is personal to the recipient, so the
-- key is (user_sub, event_id). "Unanswered" (for the unread badge AND the
-- digest) = no row, or a row with both read_at and cleared_at still NULL.
CREATE TABLE IF NOT EXISTS notification_reads (
  user_sub   text NOT NULL,
  event_id   uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  read_at    timestamptz,
  cleared_at timestamptz,
  PRIMARY KEY (user_sub, event_id)
);
CREATE INDEX IF NOT EXISTS notification_reads_sub_idx ON notification_reads (user_sub);

-- Digest outbox marker: which (user, event) pairs have already been folded
-- into a digest email, so a re-run doesn't re-send them. Mirrors delivered_at
-- but for the batched digest lane rather than the per-event lane.
CREATE TABLE IF NOT EXISTS notification_digests (
  user_sub text NOT NULL,
  event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  sent_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_sub, event_id)
);
CREATE INDEX IF NOT EXISTS notification_digests_sub_idx ON notification_digests (user_sub);

-- The coop member profile (display name / avatar / onboarded flags) — identity
-- (sub, email) lives in Keycloak; this table is the coop-side projection. RLS
-- (profiles_all) is applied in infra/compose/storage/scripts/coop_rls.sql.
CREATE TABLE IF NOT EXISTS profiles (
  sub          text PRIMARY KEY,
  email        text,
  display_name text,
  avatar       text,
  preferences  jsonb NOT NULL DEFAULT '{}',
  onboarded    boolean NOT NULL DEFAULT false,
  onboarded_at timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
-- Additive column for profiles created before preferences existed.
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS preferences jsonb NOT NULL DEFAULT '{}';
-- The member's free-text "how do you want to help your community" answer — the
-- offers side of the needs/offers matching (docs/design/weavers.md). Free-text
-- now; structured tags when matching lands.
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS offerings text;

-- The member's AI-assistant memory — durable, explicit facts the assistant has
-- remembered or the member has saved. User-scoped (NOT group-scoped): the memory
-- is personal to the member. RLS (member_memory_all) is applied in coop_rls.sql.
-- 'source' = 'assistant' (harness-proposed, member-confirmed) or 'member' (saved
-- directly). 'kind' is a free-form tag (fact/decision/group/preference) the
-- surface uses to group.
CREATE TABLE IF NOT EXISTS member_memory (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sub        text NOT NULL,
  fact       text NOT NULL,
  source     text NOT NULL DEFAULT 'member' CHECK (source IN ('member','assistant')),
  kind       text NOT NULL DEFAULT 'fact',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS member_memory_sub_idx ON member_memory (sub, created_at DESC);

-- Roles as bundles of grants (the delegation model made concrete). A role is a
-- named set of grants (capabilities); group_members.roles holds role NAMES that
-- resolve through roles/role_grants. Builtin roles (owner/member) are seeded in
-- SEED below; new roles are additive. Catalog tables are platform definitions,
-- not group-scoped — no RLS (operator-write is gated at the app layer).
CREATE TABLE IF NOT EXISTS grants (
  name        text PRIMARY KEY,
  description text
);

CREATE TABLE IF NOT EXISTS roles (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL UNIQUE,
  description text,
  builtin     boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS role_grants (
  role_id    uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  grant_name text NOT NULL REFERENCES grants(name) ON DELETE CASCADE,
  PRIMARY KEY (role_id, grant_name)
);

-- Decisions (proposals + votes) — the off-chain layer of Safe-governed voting
-- (irl-coop-group.md §6). A proposal carries a title, options, a quorum %, a
-- deadline and an optional Safe transaction payload; members vote (EIP-1271
-- signature captured here), coop-api aggregates + tallies. On-chain execution +
-- ConfidentialVoting.sol (Semaphore) private tallying are the next layer.
CREATE TABLE IF NOT EXISTS proposals (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id     uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  nonce        int NOT NULL,
  title        text NOT NULL,
  description  text,
  options      jsonb NOT NULL DEFAULT '[]',
  quorum_pct   int NOT NULL DEFAULT 50,
  deadline     timestamptz,
  payload      jsonb,
  proposer_sub text NOT NULL,
  status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open','passed','failed','executed')),
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS proposals_nonce_idx ON proposals (group_id, nonce);

CREATE TABLE IF NOT EXISTS votes (
  proposal_id uuid NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
  sub         text NOT NULL,
  choice      text NOT NULL,
  signature   text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (proposal_id, sub)
);
CREATE INDEX IF NOT EXISTS votes_proposal_idx ON votes (proposal_id);

-- Telephony: reusable templates (platform catalog), per-group instances, and
-- the concrete FreeSWITCH objects. RLS (in coop_rls.sql) scopes the two
-- group-scoped tables; templates are operator-written catalog.
CREATE TABLE IF NOT EXISTS telephony_templates (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL UNIQUE,
  kind        text NOT NULL,
  description text,
  resources   jsonb NOT NULL DEFAULT '[]',
  created_by  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS group_telephony (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id    uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  template_id uuid NOT NULL REFERENCES telephony_templates(id),
  name        text NOT NULL,
  config      jsonb NOT NULL DEFAULT '{}',
  status      text NOT NULL DEFAULT 'provisioning' CHECK (status IN ('provisioning','active','error','disabled')),
  created_by  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS telephony_resources (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id           uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  group_telephony_id uuid REFERENCES group_telephony(id) ON DELETE SET NULL,
  resource_type      text NOT NULL CHECK (resource_type IN ('extension','voicemail','conference','queue','ring_group','ivr','did','trunk')),
  external_ref       text NOT NULL,
  config             jsonb NOT NULL DEFAULT '{}',
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (group_id, resource_type, external_ref)
);

-- Geo (sovereign maps): tracks (paths), markers (points), waypoints (tour stops).
-- PostGIS geometry (SRID 4326) holds precise shape; the geohash column is the coarse
-- plaintext cell for "near" queries — the privacy/queryability split (precise
-- geometry is client-encryptable for private records later; geohash stays
-- indexable). Offline-first fields: owner_id (device-shard affinity), deleted_at
-- (tombstone — never hard-delete), updated_at (LWW merge key; HLC layered later).
-- Plain tables today (matches the stack); distributed by owner_id when Citus
-- scales to device-hosted shards.

CREATE TABLE IF NOT EXISTS tracks (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id      uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  owner_id      text NOT NULL,
  kind          text NOT NULL DEFAULT 'trail' CHECK (kind IN ('trail','route','tour')),
  title         text,
  description   text,
  category      text,
  tags          text[] NOT NULL DEFAULT '{}',
  geometry      geometry(LineString, 4326),
  geohash       text,
  timestamps    timestamptz[],
  visibility    text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','contact','group','federated','public')),
  review_status text NOT NULL DEFAULT 'draft' CHECK (review_status IN ('draft','submitted','approved','rejected')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);

CREATE TABLE IF NOT EXISTS markers (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id    uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  owner_id    text NOT NULL,
  source      text NOT NULL DEFAULT 'pin',
  title       text,
  url         text,
  category    text,
  tags        text[] NOT NULL DEFAULT '{}',
  point       geometry(Point, 4326),
  geohash     text,
  visibility  text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','contact','group','federated','public')),
  occurs_at   timestamptz,
  expires_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  deleted_at  timestamptz
);

-- waypoints denormalize group_id/owner_id so their RLS + future shard affinity
-- match the parent track without a join.
CREATE TABLE IF NOT EXISTS waypoints (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  track_id    uuid NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
  group_id    uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  owner_id    text NOT NULL,
  seq         int NOT NULL,
  point       geometry(Point, 4326),
  geohash     text,
  title       text,
  description text,
  media       jsonb NOT NULL DEFAULT '[]',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  deleted_at  timestamptz,
  UNIQUE (track_id, seq)
);

-- "near" queries hit the coarse geohash; precise spatial queries hit the geometry
-- GiST index (built only for public/federated rows — private geometry is
-- client-encrypted later and never server-indexable).
CREATE INDEX IF NOT EXISTS tracks_group_idx ON tracks (group_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS tracks_geom_gix ON tracks USING GIST (geometry) WHERE visibility IN ('federated','public');
CREATE INDEX IF NOT EXISTS markers_group_idx ON markers (group_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS markers_geohash_idx ON markers (geohash) WHERE deleted_at IS NULL AND geohash IS NOT NULL;
CREATE INDEX IF NOT EXISTS markers_geom_gix ON markers USING GIST (point) WHERE visibility IN ('federated','public');
CREATE INDEX IF NOT EXISTS waypoints_track_idx ON waypoints (track_id) WHERE deleted_at IS NULL;

-- Tier-2 contribution ledger (docs/design/tier2-entry-model.md): the off-chain,
-- hash-chained, counter-signed record of labour, swaps, in-kind and custody that
-- feeds the entitlement table — and therefore Tier-1 distributions. Sharded by
-- group_id; each group has its own chain and writes are serialised per group
-- (appendTier2Entry). Integrity comes from the counter-signatures plus the period
-- root anchored on-chain, NOT from this table's host: an operator can drop data,
-- but cannot alter it (docs/design/sharded-ledgers-and-anchors.md §3).
--
-- entry_id IS the sha256 of the canonical signed body, so an id cannot be minted
-- independently of the content it names — and editing content invalidates the id
-- every counterparty already holds. Content immutability is cryptographic.
-- period is derived from recorded_at, never from happened_at: a period root is
-- anchored (immutable), so a backdated entry could otherwise alter a published
-- tree. happened_at is a claim by the parties; late marks an out-of-window one.
CREATE TABLE IF NOT EXISTS tier2_entry (
  entry_id        text PRIMARY KEY,
  group_id        uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  seq             bigint NOT NULL,
  prev            text,
  period          date NOT NULL,
  kind            text NOT NULL CHECK (kind IN ('hours','swap','custody','receipt','in_kind','incident','correction')),
  subject         uuid NOT NULL,
  subject_kind    text NOT NULL DEFAULT 'seat' CHECK (subject_kind IN ('seat','asset','scope')),
  counterparty    uuid,
  scope           text,
  quantity        numeric,
  unit            text,
  happened_at     timestamptz,
  recorded_at     timestamptz NOT NULL,
  late            boolean NOT NULL DEFAULT false,
  payload         jsonb,
  refs            text[] NOT NULL DEFAULT '{}',
  state           text NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed','countersigned','ratified','rejected','superseded','expired')),
  basis           text NOT NULL DEFAULT 'machine-only' CHECK (basis IN ('attested','machine-only')),
  threshold       jsonb NOT NULL DEFAULT '{}',
  idempotency_key text NOT NULL,
  anchor_id       uuid,
  created_by      text NOT NULL,
  UNIQUE (group_id, seq),
  UNIQUE (group_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS tier2_entry_group_period_idx ON tier2_entry (group_id, period);
CREATE INDEX IF NOT EXISTS tier2_entry_group_state_idx ON tier2_entry (group_id, state);

-- Signatures. group_id is denormalized so the RLS policy matches the waypoint
-- pattern (a policy cannot reach group_id through entry_id cheaply). authority
-- names WHAT GRANTED the power — a role-grant id, a session-key id, a decision id —
-- and carries that authority's validity window, because the check is "was the
-- authority valid at signed_at", not "is it valid now": revoking a key must not
-- invalidate the entries it legitimately signed (tier2-entry-model.md §3).
CREATE TABLE IF NOT EXISTS tier2_signature (
  entry_id   text NOT NULL REFERENCES tier2_entry(entry_id) ON DELETE CASCADE,
  group_id   uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  signer     uuid NOT NULL,
  class      text NOT NULL CHECK (class IN ('role-holder','scoped-key','group-vote')),
  authority  text NOT NULL,
  valid_from timestamptz NOT NULL,
  valid_to   timestamptz,
  signed_at  timestamptz NOT NULL,
  sig        text NOT NULL,
  PRIMARY KEY (entry_id, signer)
);
CREATE INDEX IF NOT EXISTS tier2_signature_group_idx ON tier2_signature (group_id, signed_at DESC);

-- Idempotent widening of the class CHECK: the table shipped without 'member', and
-- CREATE TABLE IF NOT EXISTS would never add it. Safe at any row count because ADD
-- CONSTRAINT validates existing rows, and every existing row uses one of the three. (No
-- backticks anywhere in a template literal — one would close it and break the module; that
-- is exactly what this comment did on the first attempt, caught by the DDL extractor's own
-- guard before the server ever restarted onto it.)
ALTER TABLE tier2_signature DROP CONSTRAINT IF EXISTS tier2_signature_class_check;
ALTER TABLE tier2_signature ADD CONSTRAINT tier2_signature_class_check
  CHECK (class IN ('role-holder','scoped-key','group-vote','member'));

-- ONE anchor stream for every family that wants a periodic root — the Tier-2
-- ledger, the custody chain, coverage proofs (sharded-ledgers-and-anchors.md §5).
-- Batched by family so a verifier knows which tree a root came from, and so we pay
-- one set of anchor transactions instead of three. UNIQUE(family, scope_id, period)
-- makes a second root for the same period IMPOSSIBLE rather than merely visible:
-- a conflicting anchor is an alarm, and the first writer wins. group_id IS NULL for
-- federation-wide roots. chain records where it landed — dev-stage Hardhat roots
-- are scaffolding and are redeployed (money-in-and-out.md §8).
CREATE TABLE IF NOT EXISTS anchors (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  family      text NOT NULL CHECK (family IN ('tier2','custody','coverage')),
  group_id    uuid REFERENCES groups(id) ON DELETE CASCADE,
  scope_id    text NOT NULL,
  period      date NOT NULL,
  root        text NOT NULL,
  leaf_count  int NOT NULL,
  chain       text,
  tx_hash     text,
  anchored_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (family, scope_id, period)
);
CREATE INDEX IF NOT EXISTS anchors_group_idx ON anchors (group_id, period DESC);

-- Dues (docs/design/tier2-entry-model.md §5.1, §5.3). A policy is a TABLE, not a
-- language: obligations are a flat list and "any" is the only connective. That shape is
-- enforced at write time by validateDuesPolicy (dues.ts), which refuses a policy that
-- nests, negates, or does arithmetic between modes — so the convolution cannot get in.
--
-- Policies are VERSIONED and append-only. A change is a NEW version, and a period is
-- judged against the version that was active then, so a later change cannot retroactively
-- re-judge an already-decided period. Adopting one requires a decision: decided_by points
-- at the proposal. A general rule needs a vote (a treasurer who can edit the policy can
-- change what everyone owes); only a specific waiver may be granted by a role.
-- payment_intent — a payment in the COOP's vocabulary, not a vendor's.
--
-- rail names which implementation handled it and provider_ref is the vendor's id, but the
-- status vocabulary is ours (pending/partial/settled/cancelled/failed) and provider_payload
-- is the ONLY place vendor detail lives. That split is what lets a provider be swapped, or a
-- second one run in parallel, without a migration or an edit to core logic.
--
-- destination is recorded per intent and received_amount exists because a P2P rail can
-- settle PARTIALLY: "the money arrived" is not boolean.
CREATE TABLE IF NOT EXISTS payment_intent (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id        uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  payer_sub       text NOT NULL,
  rail            text NOT NULL,
  provider_ref    text,
  amount          numeric(18,6) NOT NULL CHECK (amount > 0),
  currency        text NOT NULL DEFAULT 'USDC',
  destination     text NOT NULL,
  status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','partial','settled','cancelled','failed')),
  received_amount numeric(18,6),
  pay_url         text,
  provider_payload jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  settled_at      timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS payment_intent_ref_uniq
  ON payment_intent (rail, provider_ref) WHERE provider_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS payment_intent_group_idx ON payment_intent (group_id, created_at DESC);
CREATE INDEX IF NOT EXISTS payment_intent_payer_idx ON payment_intent (payer_sub, created_at DESC);
-- rail_event — what the provider told us, and the dedupe that makes its retries harmless.
-- Written only through coop_rails_settle (SECURITY DEFINER): a webhook is untrusted input,
-- so the event log is not something an application role gets to write directly.
CREATE TABLE IF NOT EXISTS rail_event (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rail         text NOT NULL,
  event_id     text NOT NULL,
  event_type   text NOT NULL,
  provider_ref text,
  status       text NOT NULL,
  received     numeric(18,6),
  intent_id    uuid REFERENCES payment_intent(id) ON DELETE SET NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (rail, event_id)
);
-- An informational event (order created, a bridge moving) carries no status: it is evidence
-- that a VERIFIED delivery arrived, not a claim about where the money is.
ALTER TABLE rail_event ALTER COLUMN status DROP NOT NULL; -- rail_event_status_nullable
-- A CHECK of the form status IN (...) does NOT reject NULL (NULL IN (...) is NULL, not
-- FALSE), so the CHECK as written allowed a null status on an intent. Say it explicitly.
-- written allowed a null status on an intent. Say it explicitly.
ALTER TABLE payment_intent DROP CONSTRAINT IF EXISTS payment_intent_status_check;
ALTER TABLE payment_intent ADD CONSTRAINT payment_intent_status_check
  CHECK (status IS NOT NULL AND status IN ('pending','partial','settled','cancelled','failed','reversed'));
-- phone_message — SMS that ARRIVED at a number the coop controls.
--
-- This is the spine of group-owned accounts: a verification code has to land somewhere the
-- group's people can see it, or the account is hostage to one member's handset. The number
-- maps to a group through telephony_resources (resource_type 'did'), so the gateway never has
-- to say which group a text belongs to.
--
-- The RAW BODY is always kept and the extracted code is a CONVENIENCE, never an authority: a
-- wrong guess must never lose the truth. external_id is the gateway's own message id, and
-- together with the number it makes a gateway retry harmless (NULL external_id cannot collide,
-- which is the honest behaviour when a gateway sends none).
CREATE TABLE IF NOT EXISTS phone_message (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id     uuid REFERENCES groups(id) ON DELETE SET NULL,
  number_e164  text NOT NULL,
  peer_e164    text,
  body         text NOT NULL,
  code         text,
  code_kind    text,
  external_id  text,
  received_at  timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz,
  UNIQUE (number_e164, external_id)
);
CREATE INDEX IF NOT EXISTS phone_message_group_idx ON phone_message (group_id, received_at DESC);
CREATE INDEX IF NOT EXISTS rail_event_ref_idx ON rail_event (rail, provider_ref);
-- A settled payment can be taken back. The CHECK is widened idempotently, like the
-- signature class before it: CREATE TABLE IF NOT EXISTS can never add a constraint.
ALTER TABLE payment_intent DROP CONSTRAINT IF EXISTS payment_intent_status_check;
ALTER TABLE payment_intent ADD CONSTRAINT payment_intent_status_check
  CHECK (status IS NOT NULL AND status IN ('pending','partial','settled','cancelled','failed','reversed'));
CREATE TABLE IF NOT EXISTS dues_policy (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id    uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  version     int NOT NULL,
  cadence     text NOT NULL CHECK (cadence IN ('weekly','monthly','quarterly','seasonal','annual')),
  grace_days  int NOT NULL DEFAULT 0,
  obligations jsonb NOT NULL,
  waiver      jsonb NOT NULL DEFAULT '{}'::jsonb,
  status      text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','superseded')),
  decided_by  uuid REFERENCES proposals(id) ON DELETE SET NULL,
  created_by  text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (group_id, version)
);
-- ONE active policy per group, enforced by the database rather than by convention.
CREATE UNIQUE INDEX IF NOT EXISTS dues_policy_one_active ON dues_policy (group_id) WHERE status = 'active';

-- A waiver: one member, one period, one obligation. Granted by a vote or by a bounded
-- role grant; the RLS policy below makes it readable ONLY by the member and by holders
-- of the bookkeeping grant — never by the group at large, because "this member was
-- waived" is exactly the mode leak §5.1 forbids. The group may see the COUNT.
CREATE TABLE IF NOT EXISTS dues_waiver (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id       uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  sub            text NOT NULL,
  period         date NOT NULL,
  obligation     text NOT NULL,
  granted_by     text NOT NULL CHECK (granted_by IN ('vote','role')),
  authority      text NOT NULL,
  granted_by_sub text NOT NULL,
  note           text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (group_id, sub, period, obligation)
);
`;

const SEED = `
-- Grants (additive; unknown grants are simply not yet consumed).
INSERT INTO grants (name, description) VALUES
  ('group.manage', 'Rename, retarget, or delete the group'),
  ('group.members.manage', 'Invite, seat, or remove members and set their roles'),
  ('resource.scope', 'Scope an app resource to the group'),
  ('telephony.admin', 'Provision and manage the group telephony; read all call records'),
  ('telephony.agent', 'Serve as a queue agent'),
  ('telephony.caller', 'Make and receive calls on group/personal extensions'),
  ('telephony.records.read', 'Read the group call records and voicemail'),
  ('telephony.device.provision', 'Provision/rotate a member device; the secret never passes through the grant-holder'),
  ('telephony.platform.admin', 'Administer the shared FreeSWITCH platform (FusionPBX ops UI)'),
  ('storage.platform.admin', 'Administer the shared MinIO object store (console)'),
  ('media.stream.view', 'Watch coop live streams'),
  ('media.stream.broadcast', 'Broadcast live streams for the group'),
  ('dues.bookkeep', 'Record dues waivers, see the waiver count, and read dues status for the group'),
  ('dues.policy.write', 'Draft a dues policy (adopting one still requires a decision)'),
  ('tier2.attest', 'Counter-sign a contribution as a witness/organizer (an attestation), and record work on another member''s behalf')
ON CONFLICT (name) DO NOTHING;

-- Builtin roles.
INSERT INTO roles (name, description, builtin) VALUES
  ('owner', 'Full control of the group', true),
  ('member', 'Default member: call and read records', true),
  ('agent', 'Queue agent', true),
  ('telephony-admin', 'Telephony administration', true),
  ('platform-admin', 'Shared platform administration (FusionPBX ops UI)', true),
  ('treasurer', 'Dues and bookkeeping: drafts the policy, records waivers, sees counts', true)
ON CONFLICT (name) DO NOTHING;

-- Role -> grant bundles.
INSERT INTO role_grants (role_id, grant_name)
SELECT r.id, g.name
FROM roles r
JOIN grants g ON (
     (r.name = 'owner' AND g.name IN ('group.manage','group.members.manage','resource.scope','telephony.admin','telephony.agent','telephony.caller','telephony.records.read','media.stream.view','media.stream.broadcast'))
  OR (r.name = 'member' AND g.name IN ('resource.scope','telephony.caller','telephony.records.read','media.stream.view'))
  OR (r.name = 'agent' AND g.name IN ('telephony.agent','telephony.caller'))
  OR (r.name = 'telephony-admin' AND g.name IN ('telephony.admin','telephony.caller','telephony.records.read'))
  OR (r.name = 'platform-admin' AND g.name IN ('telephony.platform.admin','storage.platform.admin'))
  OR (r.name = 'treasurer' AND g.name IN ('dues.bookkeep','dues.policy.write','tier2.attest'))
  OR (r.name = 'owner' AND g.name IN ('tier2.attest'))
  -- an owner is not automatically a bookkeeper: seeing WHICH mode satisfied another
  -- member's dues is a distinct power from running the group (tier2-entry-model.md §5.1)
  OR (r.name = 'owner' AND g.name IN ('dues.bookkeep','dues.policy.write'))
)
ON CONFLICT (role_id, grant_name) DO NOTHING;

-- Default telephony templates (operator-authored catalog). Every group gets an
-- extension (its number) + a ring group (fan-out to members); kind is not a
-- telephony distinction.
INSERT INTO telephony_templates (name, kind, description, resources) VALUES
  ('Member', 'member', 'Own group: extension + ring group + voicemail',
   '[{"type":"extension","name":"extension","config":{"voicemail":true}},{"type":"ring_group","name":"ring","config":{}},{"type":"voicemail","name":"voicemail","config":{}}]'::jsonb),
  ('Support team', 'support', 'Group extension + ring group + queue + IVR + voicemail',
   '[{"type":"extension","name":"extension","config":{}},{"type":"ring_group","name":"ring","config":{}},{"type":"queue","name":"queue","config":{"strategy":"ring-all","agents_role":"agent"}},{"type":"ivr","name":"menu","config":{"greeting":"welcome"}},{"type":"voicemail","name":"voicemail","config":{}}]'::jsonb),
  ('Board room', 'conference', 'Group extension + ring group + conference room',
   '[{"type":"extension","name":"extension","config":{}},{"type":"ring_group","name":"ring","config":{}},{"type":"conference","name":"room","config":{"pin":true,"recording":true}}]'::jsonb)
ON CONFLICT (name) DO NOTHING;
`;

export async function initDb(): Promise<void> {
  await pool.query(DDL);
  await pool.query(SEED);
}

// Run a request's queries inside a transaction with the caller's identity set
// as `app.sub` — Postgres row-level security then filters every table the
// transaction touches. `SET LOCAL` is transaction-scoped, so the pooled
// connection reverts cleanly on commit/rollback and no identity leaks between
// requests.
export async function withIdentity<T>(
  sub: string,
  fn: (client: PoolClient) => Promise<T>,
): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    // set_config(..., is_local=true) == SET LOCAL, but parameterizable (SET
    // does not accept $1). Transaction-scoped, so the pooled connection reverts.
    await client.query("SELECT set_config('app.sub', $1, true)", [sub]);
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK").catch(() => {});
    throw err;
  } finally {
    client.release();
  }
}

export { pool };

// Resolve a member's roles (seat role names) and grants (role names -> grant
// capabilities) across ALL their seats — the union used for the OIDC `roles`
// and `grants` claims. Runs inside withIdentity(sub) so RLS lets the member
// read their own seats (coop_can_view_group resolves membership via app.sub);
// the roles/role_grants/grants catalog tables are not RLS-scoped. Grants
// resolve only for KNOWN roles (role_grants); an unknown role name in a seat
// contributes no grants (additive model).
export async function getRolesAndGrants(
  sub: string,
): Promise<{ roles: string[]; grants: string[] }> {
  return withIdentity(sub, async (client) => {
    // DIRECT SEATS ONLY. Do NOT repoint these at coop_my_seats(): capability grants
    // must not flow through a group seat, or every member of a member co-op would
    // inherit the collective's roles. Visibility traverses; authority does not.
    // (docs/design/seat-holder-is-a-safe.md §4.2)
    const rolesRes = await client.query<{ name: string }>(
      `SELECT DISTINCT unnest(roles) AS name FROM group_members WHERE sub = $1`,
      [sub],
    );
    const grantsRes = await client.query<{ name: string }>(
      `SELECT DISTINCT g.name
         FROM group_members gm
         JOIN roles      r  ON r.name = ANY(gm.roles)
         JOIN role_grants rg ON rg.role_id = r.id
         JOIN grants     g  ON g.name = rg.grant_name
        WHERE gm.sub = $1`,
      [sub],
    );
    return {
      roles: rolesRes.rows.map((r) => r.name),
      grants: grantsRes.rows.map((r) => r.name),
    };
  });
}

// The member's RELATED GROUPS — the functional group concept (NOT permissions).
// Every user IS a 1-of-1 group: their personal group (kind='personal', seated
// as owner) plus every coop group they hold a seat in (admin or otherwise —
// a seat is the relationship). The Keycloak `groups` mapper emits these ids as
// the OIDC `groups` claim. Mirrors the /api/v1/profile membership query.
export async function getRelatedGroups(sub: string): Promise<string[]> {
  return withIdentity(sub, async (client) => {
    await client.query("SELECT coop_ensure_personal_group()");
    const { rows } = await client.query<{ id: string }>(
      `SELECT g.id
         FROM coop_my_seats() ms
         JOIN groups g ON g.id = ms.group_id
        ORDER BY g.created_at ASC`,
    );
    return rows.map((r) => r.id);
  });
}

// The member's coop-group SEATS as {slug, name, roles[]} — the source for the
// OIDC `groups` claim (apps map each group to their own tenant, e.g. Formbricks
// Team). Excludes the 1-of-1 personal seat (kind='personal'): that is the
// self-group, not a coop team. RLS-scoped via withIdentity(sub).
export async function getGroupSeats(
  sub: string,
): Promise<{ slug: string; name: string; roles: string[] }[]> {
  return withIdentity(sub, async (client) => {
    await client.query("SELECT coop_ensure_personal_group()");
    const { rows } = await client.query<{ slug: string; name: string; roles: string[] }>(
      `SELECT COALESCE(g.slug, g.id::text) AS slug, g.name, ms.roles
         FROM coop_my_seats() ms
         JOIN groups g ON g.id = ms.group_id
        WHERE g.kind = 'coop'
        ORDER BY g.created_at ASC`,
    );
    return rows;
  });
}

// Promote / demote a member to shared-platform admin. `platform-admin` is the
// platform-scoped role (grants telephony.platform.admin) that the FusionPBX
// oauth2-proxy gate reads; it lives on the member's own 1-of-1 seat. The DB
// functions are SECURITY DEFINER (BYPASSRLS) and idempotent — promotion is
// additive, revocation strips only the one role — and live in coop_rls.sql, so
// promotion is reproducible (survives a storage-pillar reset) and never needs
// ad-hoc SQL. Each call also writes an audit event (source='platform'). The
// functions are locked to the `coop_ops` operator role (REVOKE FROM PUBLIC +
// session_user guard), so these run over a separate least-privilege pool — the
// app's main `coop` pool can never self-promote.
export async function ensurePlatformAdmin(sub: string): Promise<void> {
  await opsPool.query("SELECT coop_ensure_platform_admin($1)", [sub]);
}

export async function revokePlatformAdmin(sub: string): Promise<void> {
  await opsPool.query("SELECT coop_revoke_platform_admin($1)", [sub]);
}

// System-write bridge for telephony resources. Runs the SECURITY DEFINER
// coop_provision_telephony_resource over the least-privilege coop_ops pool
// (the app's `coop` pool can never write telephony_resources — no user policy).
export async function provisionTelephonyResource(
  groupId: string,
  resourceType: string,
  externalRef: string,
  config: Record<string, unknown> = {},
): Promise<void> {
  await opsPool.query(
    "SELECT coop_provision_telephony_resource($1, NULL, $2, $3, $4::jsonb)",
    [groupId, resourceType, externalRef, JSON.stringify(config)],
  );
}

// ---------------------------------------------------------------------------
// Tier-2 contribution ledger (docs/design/tier2-entry-model.md §1–§7).
// Step 1 of the ledger's build order: the append path, with invariants 1–2 —
// serialised per-group writes and idempotency. No treasury contract and no chain
// switch is required for any of this.
// ---------------------------------------------------------------------------

export type Tier2Kind =
  | "hours"
  | "swap"
  | "custody"
  | "receipt"
  | "in_kind"
  | "incident"
  | "correction";

export type Tier2SignatureClass =
  | "role-holder"   // a witness: "I saw this happen"
  | "scoped-key"    // a machine observation, from a capped/expiring source key
  | "group-vote"    // the group acting by quorum
  | "member";       // SELF-ASSERTION: "I did this". Not a witness and not a machine — and
                    // on its own it is not an attestation (see `basis`).

export interface Tier2SignatureInput {
  signer: string;
  class: Tier2SignatureClass;
  /** WHAT GRANTED THIS POWER: a role-grant id, a session-key id, a decision id. */
  authority: string;
  validFrom: Date;
  validTo?: Date | null;
  signedAt: Date;
  sig: string;
}

export interface Tier2EntryInput {
  groupId: string;
  kind: Tier2Kind;
  subject: string;
  subjectKind?: "seat" | "asset" | "scope";
  counterparty?: string | null;
  scope?: string | null;
  quantity?: number | null;
  unit?: string | null;
  /** when the work/event HAPPENED — a claim by the parties, never the chain's order. */
  happenedAt?: Date | null;
  /** set by the caller from the group's policy when happenedAt is out of window. */
  late?: boolean;
  payload?: unknown;
  refs?: string[];
  threshold?: unknown;
  /** a retried submit must not double-log an hour (invariant 2). */
  idempotencyKey: string;
  createdBy: string;
  /** the creator's own signature over the body. */
  signature: Tier2SignatureInput;
  /** an optional counter-signature taken at create time; more may be added later. */
  countersignature?: Tier2SignatureInput | null;
}

/**
 * Canonical JSON: keys sorted, recursion applied. The entry id is a hash of the
 * body, so the serialisation MUST be deterministic across processes and versions —
 * a key-order dependency would mint two ids for one entry.
 */
function canonicalJson(v: unknown): string {
  if (v === undefined || v === null) return "null";
  if (Array.isArray(v)) return `[${v.map(canonicalJson).join(",")}]`;
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    const keys = Object.keys(o)
      .filter((k) => o[k] !== undefined)
      .sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${canonicalJson(o[k])}`).join(",")}}`;
  }
  return JSON.stringify(v);
}

/** The chain body whose hash becomes entry_id. Exported so a verifier can recompute it. */
export function tier2EntryBody(input: {
  groupId: string;
  seq: number | string;
  prev: string | null;
  period: string;
  kind: Tier2Kind;
  subject: string;
  subjectKind: string;
  counterparty: string | null;
  scope: string | null;
  quantity: number | null;
  unit: string | null;
  happenedAt: Date | null;
  recordedAt: Date;
  late: boolean;
  payload: unknown;
  refs: string[];
}): Record<string, unknown> {
  return {
    group_id: input.groupId,
    seq: String(input.seq),
    prev: input.prev,
    period: input.period,
    kind: input.kind,
    subject: input.subject,
    subject_kind: input.subjectKind,
    counterparty: input.counterparty,
    scope: input.scope,
    quantity: input.quantity,
    unit: input.unit,
    happened_at: input.happenedAt ? input.happenedAt.toISOString() : null,
    recorded_at: input.recordedAt.toISOString(),
    late: input.late,
    payload: input.payload ?? null,
    refs: input.refs,
  };
}

/**
 * Which signature classes constitute an ATTESTATION — i.e. an independent account of the work.
 *
 *   role-holder  a witness with a role
 *   group-vote   the group accepting it by quorum
 *
 * NOT `scoped-key` (a machine observation) and NOT `member` (the person speaking about
 * themselves, or a peer doing the same). Defined once, because "anything that is not a
 * scoped-key" silently promoted a member witness to `attested` when the `member` class landed.
 */
export function isAttestingClass(cls: Tier2SignatureClass): boolean {
  return cls === "role-holder" || cls === "group-vote";
}

/** entry_id = sha256(canonical body). Content-addressed: an id cannot be minted
 *  for content that does not match it, and editing content invalidates the id. */
export function tier2EntryId(body: Record<string, unknown>): string {
  return createHash("sha256").update(canonicalJson(body)).digest("hex");
}

const TIER2_PERIOD = (d: Date): string => d.toISOString().slice(0, 10);

function tier2SignatureInsert(client: PoolClient, entryId: string, groupId: string, s: Tier2SignatureInput) {
  return client.query(
    `INSERT INTO tier2_signature (entry_id, group_id, signer, class, authority, valid_from, valid_to, signed_at, sig)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
     ON CONFLICT (entry_id, signer) DO NOTHING`,
    [entryId, groupId, s.signer, s.class, s.authority, s.validFrom, s.validTo ?? null, s.signedAt, s.sig],
  );
}

/**
 * Append an entry to a group's Tier-2 chain.
 *
 * Serialised per group with a transaction-scoped advisory lock (invariant 1), so a
 * losing writer gets a conflict rather than forking the chain. Advisory locks are
 * released on commit/rollback, so a pooled connection never keeps one.
 *
 * Idempotent on (group_id, idempotency_key) (invariant 2): re-submitting the same
 * key returns the entry that already exists instead of logging a second hour.
 *
 * `basis` starts as `machine-only` and only becomes `attested` when a signature
 * other than a scoped key is present. `machine-only` is usable for display but must
 * never affect a Tier-1 outcome until a role holder or a vote touches it (§6).
 */
export async function appendTier2Entry(
  client: PoolClient,
  input: Tier2EntryInput,
): Promise<{ entry_id: string; seq: number; state: string; deduplicated: boolean }> {
  await client.query("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", [
    `tier2:${input.groupId}`,
  ]);

  const existing = await client.query(
    "SELECT entry_id, seq, state FROM tier2_entry WHERE group_id = $1 AND idempotency_key = $2",
    [input.groupId, input.idempotencyKey],
  );
  if (existing.rowCount) {
    const r = existing.rows[0];
    return { entry_id: r.entry_id, seq: Number(r.seq), state: r.state, deduplicated: true };
  }

  const head = await client.query(
    "SELECT entry_id, seq FROM tier2_entry WHERE group_id = $1 ORDER BY seq DESC LIMIT 1",
    [input.groupId],
  );
  const seq = head.rowCount ? Number(head.rows[0].seq) + 1 : 1;
  const prev: string | null = head.rowCount ? head.rows[0].entry_id : null;

  const recordedAt = new Date();
  const subjectKind = input.subjectKind ?? "seat";
  const refs = input.refs ?? [];
  const body = tier2EntryBody({
    groupId: input.groupId,
    seq,
    prev,
    period: TIER2_PERIOD(recordedAt),
    kind: input.kind,
    subject: input.subject,
    subjectKind,
    counterparty: input.counterparty ?? null,
    scope: input.scope ?? null,
    quantity: input.quantity ?? null,
    unit: input.unit ?? null,
    happenedAt: input.happenedAt ?? null,
    recordedAt,
    late: input.late ?? false,
    payload: input.payload ?? null,
    refs,
  });
  const entryId = tier2EntryId(body);

  await client.query(
    `INSERT INTO tier2_entry (
       entry_id, group_id, seq, prev, period, kind, subject, subject_kind, counterparty,
       scope, quantity, unit, happened_at, recorded_at, late, payload, refs,
       state, basis, threshold, idempotency_key, created_by
     ) VALUES (
       $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16::jsonb,$17,$18,$19,$20::jsonb,$21,$22
     )`,
    [
      entryId, input.groupId, seq, prev, TIER2_PERIOD(recordedAt), input.kind, input.subject,
      subjectKind, input.counterparty ?? null, input.scope ?? null, input.quantity ?? null,
      input.unit ?? null, input.happenedAt ?? null, recordedAt, input.late ?? false,
      JSON.stringify(input.payload ?? null), refs,
      input.countersignature ? "countersigned" : "proposed",
      input.countersignature && isAttestingClass(input.countersignature.class) ? "attested" : "machine-only",
      JSON.stringify(input.threshold ?? {}), input.idempotencyKey, input.createdBy,
    ],
  );

  await tier2SignatureInsert(client, entryId, input.groupId, input.signature);
  if (input.countersignature) {
    await tier2SignatureInsert(client, entryId, input.groupId, input.countersignature);
  }

  return {
    entry_id: entryId,
    seq,
    state: input.countersignature ? "countersigned" : "proposed",
    deduplicated: false,
  };
}

/**
 * Add a counter-signature to an existing entry.
 *
 * The cheap half of the no-self-dealing rule (§3.2): a signer may not counter-sign
 * an entry they created. The fuller check — the counter-signer must not be the
 * BENEFICIARY — needs the seat→subject mapping and lives at the app layer, as does
 * threshold evaluation and the ratification transition.
 */
export async function countersignTier2Entry(
  client: PoolClient,
  entryId: string,
  groupId: string,
  signature: Tier2SignatureInput,
): Promise<{ state: string; basis: string }> {
  const row = await client.query(
    "SELECT created_by, state FROM tier2_entry WHERE entry_id = $1 AND group_id = $2 FOR UPDATE",
    [entryId, groupId],
  );
  if (!row.rowCount) throw new Error(`tier2 entry not found: ${entryId}`);
  const { created_by: createdBy, state } = row.rows[0];
  if (state === "ratified" || state === "superseded") {
    throw new Error(`tier2 entry ${entryId} is ${state}; signatures are closed`);
  }
  if (createdBy === signature.signer) {
    throw new Error("tier2: a signer may not counter-sign their own entry");
  }

  await tier2SignatureInsert(client, entryId, groupId, signature);
  const basis = isAttestingClass(signature.class) ? "attested" : "machine-only";
  await client.query(
    "UPDATE tier2_entry SET state = CASE WHEN state = 'proposed' THEN 'countersigned' ELSE state END, basis = CASE WHEN $2 = 'attested' THEN 'attested' ELSE basis END WHERE entry_id = $1",
    [entryId, basis],
  );
  return { state: "countersigned", basis };
}

// ---------------------------------------------------------------------------
// Period trees + anchoring (docs/design/sharded-ledgers-and-anchors.md).
//
// The construction is RFC-6962-style with DOMAIN SEPARATION: leaves hash as
// sha256(0x00 || id) and interior nodes as sha256(0x01 || left || right). Without
// the prefix bytes a promoted interior node and a leaf are both 32 bytes and the
// tree is ambiguous — the classic second-preimage hole. Two bytes close it.
//
// An odd node at a level is PROMOTED to the next level unchanged (no duplication),
// which is safe here precisely because of the domain separation.
//
// The root is the only thing that leaves the node: leaves are entry ids, i.e.
// commitments, never content. Exported so a verifier (or a member device) can
// recompute a tree from ids alone.
// ---------------------------------------------------------------------------

const LEAF_PREFIX = Buffer.from([0x00]);
const NODE_PREFIX = Buffer.from([0x01]);

/** sha256(0x00 || entry_id) — the leaf commitment. */
export function tier2LeafHash(entryId: string): string {
  return createHash("sha256")
    .update(LEAF_PREFIX)
    .update(Buffer.from(entryId.toLowerCase(), "hex"))
    .digest("hex");
}

/** sha256(0x01 || left || right) — an interior node. */
function tier2NodeHash(left: string, right: string): string {
  return createHash("sha256")
    .update(NODE_PREFIX)
    .update(Buffer.from(left, "hex"))
    .update(Buffer.from(right, "hex"))
    .digest("hex");
}

export interface MerkleProofStep {
  sibling: string;
  side: "left" | "right";
}

export interface MerkleTree {
  root: string;
  leaves: string[];
  levels: string[][];
}

/**
 * Build the period tree over a group's entries, IN seq ORDER. Order is part of the
 * commitment: reordering the same entries yields a different root, which is what
 * makes the tree attest a sequence rather than a set.
 */
export function tier2MerkleTree(entryIds: string[]): MerkleTree {
  const leaves = entryIds.map(tier2LeafHash);
  const levels: string[][] = [leaves];
  let cur = leaves;
  while (cur.length > 1) {
    const next: string[] = [];
    for (let i = 0; i < cur.length; i += 2) {
      next.push(i + 1 < cur.length ? tier2NodeHash(cur[i], cur[i + 1]) : cur[i]);
    }
    levels.push(next);
    cur = next;
  }
  return { root: cur[0] ?? "", leaves, levels };
}

/** The inclusion path for one entry: what a selective reveal hands over — this record
 *  and its path to the period root, never the whole chain. */
export function tier2InclusionProof(entryId: string, entryIds: string[]): MerkleProofStep[] | null {
  const target = tier2LeafHash(entryId);
  let idx = entryIds.map(tier2LeafHash).indexOf(target);
  if (idx < 0) return null;

  const proof: MerkleProofStep[] = [];
  let cur = entryIds.map(tier2LeafHash);
  while (cur.length > 1) {
    const next: string[] = [];
    for (let i = 0; i < cur.length; i += 2) {
      if (i + 1 < cur.length) {
        next.push(tier2NodeHash(cur[i], cur[i + 1]));
        if (i === idx) proof.push({ sibling: cur[i + 1], side: "right" });
        else if (i + 1 === idx) proof.push({ sibling: cur[i], side: "left" });
      } else {
        next.push(cur[i]); // promoted — no sibling to record
      }
    }
    idx = Math.floor(idx / 2);
    cur = next;
  }
  return proof;
}

/** Recompute a root from one leaf and its path. A verifier needs only this, the
 *  entry id, and the anchored period root. */
export function tier2VerifyInclusion(
  entryId: string,
  proof: MerkleProofStep[],
  root: string,
): boolean {
  let acc = tier2LeafHash(entryId);
  for (const step of proof) {
    acc = step.side === "left" ? tier2NodeHash(step.sibling, acc) : tier2NodeHash(acc, step.sibling);
  }
  return acc === root.toLowerCase();
}

export interface PeriodRoot {
  root: string;
  leafCount: number;
}

/** Anchor a family's root. `ON CONFLICT DO NOTHING` + a conflict flag: a second,
 *  DIFFERENT root for the same (family, scope, period) is an alarm, not a race. */
async function anchorSlot(
  family: "tier2" | "custody" | "coverage",
  groupId: string | null,
  scopeId: string,
  period: string,
  root: string,
  leafCount: number,
): Promise<{ root: string; leaf_count: number; conflict: boolean }> {
  const r = await opsPool.query(
    "SELECT root, leaf_count, conflict FROM coop_anchor_slot($1,$2,$3,$4,$5,$6)",
    [family, groupId, scopeId, period, root, leafCount],
  );
  return r.rows[0];
}

/**
 * Compute and claim a group's Tier-2 period root.
 *
 * Reads the period's entry IDS through an operator function (the ledger is
 * RLS-scoped and a background anchoring job holds no member identity) and writes
 * the slot through a second operator function. `anchors` has no user write policy
 * at all, so the app role cannot forge or alter a root — only coop_ops can.
 *
 * Returns null when the period has no entries: there is nothing to anchor, and an
 * empty root would be a false attestation.
 */
export async function anchorTier2Period(
  groupId: string,
  period: string,
): Promise<(PeriodRoot & { conflict: boolean }) | null> {
  const ids = await opsPool.query(
    "SELECT entry_id FROM coop_tier2_period_ids($1,$2)",
    [groupId, period],
  );
  const entryIds: string[] = ids.rows.map((r) => r.entry_id);
  if (!entryIds.length) return null;

  const tree = tier2MerkleTree(entryIds);
  const slot = await anchorSlot("tier2", groupId, groupId, period, tree.root, entryIds.length);
  return { root: slot.root, leafCount: slot.leaf_count, conflict: slot.conflict };
}

/**
 * The federation root for a period: one leaf per group that anchored, so a
 * cross-group claim (coverage, cooperativeness) is provable without any group
 * revealing its entries — or even its entry count.
 *
 * The leaf is domain-separated by scope: sha256("tier2|" || scope_id || "|" || root),
 * because a federation leaf commits to a (group, root) PAIR, not to an entry.
 */
export async function anchorTier2Federation(period: string): Promise<(PeriodRoot & { conflict: boolean }) | null> {
  const rows = await opsPool.query(
    "SELECT scope_id, root FROM coop_tier2_roots_for_period($1)",
    [period],
  );
  const roots: Array<{ scope_id: string; root: string }> = rows.rows;
  if (!roots.length) return null;

  const pairs = roots
    .map((r) => ({ key: r.scope_id, leaf: createHash("sha256").update(`tier2|${r.scope_id}|${r.root}`).digest("hex") }))
    .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));

  const tree = tier2MerkleTree(pairs.map((p) => p.leaf));
  const slot = await anchorSlot("tier2", null, "federation", period, tree.root, pairs.length);
  return { root: slot.root, leafCount: slot.leaf_count, conflict: slot.conflict };
}

/** The period a timestamp falls in. Anchoring forces periods to be record-time. */
export function tier2PeriodOf(recordedAt: Date): string {
  return TIER2_PERIOD(recordedAt);
}
