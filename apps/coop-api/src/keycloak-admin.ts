import * as crypto from "crypto";

// --- coop-api ↔ Keycloak admin REST (the coop-api service account has
//     realm-management/manage-users — the canonical-identity authority) ---

const KC_ISSUER = process.env.KEYCLOAK_ISSUER ?? "http://localhost:8081/realms/irl-coop";
const KC_CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID ?? "coop-api";
const KC_CLIENT_SECRET = process.env.KEYCLOAK_CLIENT_SECRET ?? "";

const realm = KC_ISSUER.split("/realms/").pop() ?? "irl-coop";
const adminBase = KC_ISSUER.replace(`/realms/${realm}`, `/admin/realms/${realm}`);

let cachedAdminToken: { token: string; expiresAt: number } | null = null;

export async function getAdminToken(): Promise<string> {
  if (cachedAdminToken && cachedAdminToken.expiresAt > Date.now() + 30_000) {
    return cachedAdminToken.token;
  }
  const resp = await fetch(`${KC_ISSUER}/protocol/openid-connect/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: KC_CLIENT_ID,
      client_secret: KC_CLIENT_SECRET,
    }),
  });
  if (!resp.ok) throw new Error(`keycloak admin token failed: ${resp.status}`);
  const data = (await resp.json()) as { access_token: string; expires_in: number };
  cachedAdminToken = { token: data.access_token, expiresAt: Date.now() + data.expires_in * 1000 };
  return cachedAdminToken.token;
}

async function admin(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await getAdminToken();
  return fetch(`${adminBase}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });
}

/** Ensure <email> is unused; returns "taken" or "available". */
export async function checkEmailAvailable(email: string): Promise<"available" | "taken"> {
  const resp = await admin(`/users?email=${encodeURIComponent(email)}&exact=true`);
  if (!resp.ok) throw new Error(`keycloak user search failed: ${resp.status}`);
  const users = (await resp.json()) as { id: string }[];
  return users.length > 0 ? "taken" : "available";
}

/**
 * Set the canonical email for the user identified by `sub`.
 * Returns "taken" when the address is owned by another user, "updated" on
 * success, or "unchanged" when the canonical email is already in place.
 */
export async function setUserCanonicalEmail(
  _token: string,
  sub: string,
  email: string,
): Promise<"taken" | "updated" | "unchanged"> {
  // The user's own current email is allowed to equal the target (idempotent re-claim).
  const existing = await admin(`/users?email=${encodeURIComponent(email)}&exact=true`);
  if (!existing.ok) throw new Error(`keycloak user search failed: ${existing.status}`);
  const holders = (await existing.json()) as { id: string }[];
  if (holders.length > 0 && holders[0].id !== sub) return "taken";

  const me = await admin(`/users/${sub}`);
  if (!me.ok) throw new Error(`keycloak user lookup failed: ${me.status}`);
  const profile = (await me.json()) as { email?: string | null };
  if (profile.email === email) return "unchanged";

  // Note: the previous provider address (gmail etc.) stays preserved via the
  // username + federated identity link — the realm drops arbitrary attributes.
  const resp = await admin(`/users/${sub}`, {
    method: "PUT",
    body: JSON.stringify({ email, emailVerified: true }),
  });
  if (!resp.ok) throw new Error(`keycloak email update failed: ${resp.status}`);
  return "updated";
}
