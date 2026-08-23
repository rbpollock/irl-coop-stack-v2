import { Pool, PoolClient } from "pg";

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

// Idempotent schema — coop-api self-provisions its projection tables on boot.
// gen_random_uuid() is built into Postgres 13+ (Citus is 16), no extension.
const DDL = `
CREATE TABLE IF NOT EXISTS groups (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  safe_address text,
  name        text NOT NULL,
  description text,
  privacy     text NOT NULL DEFAULT 'members' CHECK (privacy IN ('open','members','hidden')),
  kind        text NOT NULL DEFAULT 'coop' CHECK (kind IN ('coop','personal')),
  created_by  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS group_members (
  group_id   uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  sub        text NOT NULL,
  roles      text[] NOT NULL DEFAULT '{}',
  alias      text,
  visibility text NOT NULL DEFAULT 'canonical' CHECK (visibility IN ('role-only','alias','canonical')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (group_id, sub)
);

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
  ('telephony.device.provision', 'Provision/rotate a member device; the secret never passes through the grant-holder')
ON CONFLICT (name) DO NOTHING;

-- Builtin roles.
INSERT INTO roles (name, description, builtin) VALUES
  ('owner', 'Full control of the group', true),
  ('member', 'Default member: call and read records', true),
  ('agent', 'Queue agent', true),
  ('telephony-admin', 'Telephony administration', true)
ON CONFLICT (name) DO NOTHING;

-- Role -> grant bundles.
INSERT INTO role_grants (role_id, grant_name)
SELECT r.id, g.name
FROM roles r
JOIN grants g ON (
     (r.name = 'owner' AND g.name IN ('group.manage','group.members.manage','resource.scope','telephony.admin','telephony.agent','telephony.caller','telephony.records.read'))
  OR (r.name = 'member' AND g.name IN ('resource.scope','telephony.caller','telephony.records.read'))
  OR (r.name = 'agent' AND g.name IN ('telephony.agent','telephony.caller'))
  OR (r.name = 'telephony-admin' AND g.name IN ('telephony.admin','telephony.caller','telephony.records.read'))
)
ON CONFLICT (role_id, grant_name) DO NOTHING;

-- Default telephony templates (operator-authored catalog).
INSERT INTO telephony_templates (name, kind, description, resources) VALUES
  ('Member', 'member', 'Personal extension + voicemail for every member',
   '[{"type":"extension","name":"extension","config":{"count":1,"voicemail":true}}]'::jsonb),
  ('Support team', 'support', 'Queue + IVR + voicemail + ring group',
   '[{"type":"queue","name":"queue","config":{"strategy":"ring-all","agents_role":"agent"}},{"type":"ivr","name":"menu","config":{"greeting":"welcome"}},{"type":"voicemail","name":"voicemail","config":{}},{"type":"ring_group","name":"ring","config":{}}]'::jsonb),
  ('Board room', 'conference', 'Conference room + PIN + recording',
   '[{"type":"conference","name":"room","config":{"pin":true,"recording":true}}]'::jsonb)
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
