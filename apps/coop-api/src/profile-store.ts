import * as fs from "node:fs";
import * as path from "node:path";

export interface CoopProfile {
  sub: string;
  email: string | null;
  displayName: string | null;
  avatar: string | null;
  onboarded: boolean;
  onboardedAt: string | null;
  createdAt: string;
  updatedAt: string;
}

// JSON-file-backed store for coop member profiles. Dev-grade: swap for
// Postgres when coop-api gets a real database (see README).
const STORE_PATH =
  process.env.COOP_PROFILE_STORE ?? path.join(process.cwd(), "data", "profiles.json");

function load(): Record<string, CoopProfile> {
  try {
    return JSON.parse(fs.readFileSync(STORE_PATH, "utf8")) as Record<string, CoopProfile>;
  } catch {
    return {};
  }
}

function save(store: Record<string, CoopProfile>): void {
  fs.mkdirSync(path.dirname(STORE_PATH), { recursive: true });
  fs.writeFileSync(STORE_PATH, JSON.stringify(store, null, 2));
}

export function getProfile(sub: string): CoopProfile | undefined {
  return load()[sub];
}

export function upsertProfile(
  sub: string,
  patch: { email?: string | null; displayName?: string | null; avatar?: string | null }
): CoopProfile {
  const store = load();
  const now = new Date().toISOString();
  const existing = store[sub];
  const next: CoopProfile = {
    sub,
    email: patch.email !== undefined ? patch.email : existing?.email ?? null,
    displayName: patch.displayName !== undefined ? patch.displayName : existing?.displayName ?? null,
    avatar: patch.avatar !== undefined ? patch.avatar : existing?.avatar ?? null,
    onboarded: true,
    onboardedAt: existing?.onboardedAt ?? now,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now,
  };
  store[sub] = next;
  save(store);
  return next;
}
