import * as fs from "node:fs";
import * as path from "node:path";
import { withIdentity } from "./db";

export interface CoopProfile {
  sub: string;
  email: string | null;
  displayName: string | null;
  avatar: string | null;
  offerings: string | null;
  onboarded: boolean;
  onboardedAt: string | null;
  preferences: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

// Postgres-backed coop member profile. Identity (sub/email) lives in Keycloak;
// this table is the coop-side projection (display name, avatar, onboarded flags).
// RLS (profiles_all in infra/compose/storage/scripts/coop_rls.sql) scopes each
// row to its sub — enforcement in Postgres, not the app. Reads/writes go through
// withIdentity() so `app.sub` is set and the policy passes.

interface ProfileRow {
  sub: string;
  email: string | null;
  display_name: string | null;
  avatar: string | null;
  offerings: string | null;
  onboarded: boolean;
  onboarded_at: Date | null;
  preferences: Record<string, unknown>;
  created_at: Date;
  updated_at: Date;
}

function toProfile(r: ProfileRow): CoopProfile {
  return {
    sub: r.sub,
    email: r.email,
    displayName: r.display_name,
    avatar: r.avatar,
    offerings: r.offerings ?? null,
    onboarded: r.onboarded,
    onboardedAt: r.onboarded_at ? r.onboarded_at.toISOString() : null,
    preferences: r.preferences ?? {},
    createdAt: r.created_at.toISOString(),
    updatedAt: r.updated_at.toISOString(),
  };
}

export async function getProfile(sub: string): Promise<CoopProfile | undefined> {
  return withIdentity(sub, async (client) => {
    const r = await client.query("SELECT * FROM profiles WHERE sub = $1", [sub]);
    return r.rows[0] ? toProfile(r.rows[0] as ProfileRow) : undefined;
  });
}

export async function upsertProfile(
  sub: string,
  patch: { email?: string | null; displayName?: string | null; avatar?: string | null; offerings?: string | null; preferences?: Record<string, unknown> },
): Promise<CoopProfile> {
  const now = new Date().toISOString();
  // Merge semantics mirror the retired JSON store: a field is only overwritten
  // when the patch provides it (undefined = keep existing; explicit null = clear).
  const existing = await getProfile(sub);
  const next: CoopProfile = {
    sub,
    email: patch.email !== undefined ? patch.email : existing?.email ?? null,
    displayName: patch.displayName !== undefined ? patch.displayName : existing?.displayName ?? null,
    avatar: patch.avatar !== undefined ? patch.avatar : existing?.avatar ?? null,
    offerings: patch.offerings !== undefined ? patch.offerings : existing?.offerings ?? null,
    preferences: patch.preferences !== undefined ? patch.preferences : existing?.preferences ?? {},
    onboarded: true,
    onboardedAt: existing?.onboardedAt ?? now,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  };
  await withIdentity(sub, async (client) => {
    await client.query(
      `INSERT INTO profiles (sub, email, display_name, avatar, offerings, preferences, onboarded, onboarded_at, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, $6::jsonb, true, $7, $8, $9)
       ON CONFLICT (sub) DO UPDATE SET
         email = EXCLUDED.email,
         display_name = EXCLUDED.display_name,
         avatar = EXCLUDED.avatar,
         offerings = EXCLUDED.offerings,
         preferences = EXCLUDED.preferences,
         onboarded = true,
         onboarded_at = EXCLUDED.onboarded_at,
         updated_at = EXCLUDED.updated_at`,
      [next.sub, next.email, next.displayName, next.avatar, next.offerings, JSON.stringify(next.preferences), next.onboardedAt, next.createdAt, next.updatedAt],
    );
  });
  return next;
}

// One-time migration from the retired JSON-file store (data/profiles.json).
// Idempotent: subs already present in Postgres are left untouched. Runs
// best-effort on boot; once migrated the JSON file is inert. Legacy
// created_at/onboarded_at are re-stamped at migration time (dev-grade).
export async function migrateProfilesFromJson(): Promise<number> {
  const storePath = process.env.COOP_PROFILE_STORE ?? path.join(process.cwd(), "data", "profiles.json");
  let legacy: Record<string, CoopProfile> = {};
  try {
    legacy = JSON.parse(fs.readFileSync(storePath, "utf8")) as Record<string, CoopProfile>;
  } catch {
    return 0; // no legacy file — nothing to migrate
  }
  let migrated = 0;
  for (const [sub, p] of Object.entries(legacy)) {
    const existing = await getProfile(sub);
    if (existing) continue;
    await upsertProfile(sub, { email: p.email, displayName: p.displayName, avatar: p.avatar });
    migrated += 1;
  }
  return migrated;
}
