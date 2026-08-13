import { Pool } from "pg";

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
  safe_address text NOT NULL,
  name        text NOT NULL,
  description text,
  privacy     text NOT NULL DEFAULT 'members' CHECK (privacy IN ('open','members','hidden')),
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
`;

export async function initDb(): Promise<void> {
  await pool.query(DDL);
}

export { pool };
