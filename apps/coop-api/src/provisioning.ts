import { ethers } from "ethers";
import { withIdentity } from "./db";
import { deploySafe } from "./safe";
import { ensurePersonalTelephony } from "./telephony";
import { ensureErpPersonalTenancy } from "./erpnext-provision";

// ---------------------------------------------------------------------------
// Invite-on-first-signin provisioning (docs/design/irl-coop-group.md §3).
// Every sign-in converges the same way, so this runs idempotently on each
// fresh Keycloak authentication (the OAuth callback + the password login):
//
//   1. ensurePersonalSafe(sub) — deploy the personal account Safe with a
//      deterministic sub-derived salt (predictable address, no storage of the
//      sub->address mapping) and stamp safe_address on the personal group.
//   2. provisionMatrix(sub, email) — register the member's Matrix account via
//      the appservice AS API (Bearer as_token + ?user_id=) and auto-join the
//      coop's default rooms, creating them if missing (deterministic aliases).
//
// Both are convergent: running them on a later sign-in is a no-op. Failures
// are logged, never thrown — sign-in must not break because a provisioner is
// down (the next sign-in retries).
// ---------------------------------------------------------------------------

const SYNAPSE_BASE = process.env.MATRIX_BASE_URL ?? "https://matrix.irl.coop";
const SERVER_NAME = process.env.MATRIX_SERVER_NAME ?? "matrix.irl.coop";
const AS_TOKEN = process.env.MATRIX_AS_TOKEN ?? "";

// The coop's default rooms, deterministic aliases (irl-coop-group.md §5.1).
const COOP_ROOMS = [
  { alias: "irl-coop-general", name: "General" },
  { alias: "irl-coop-governance", name: "Governance" },
  { alias: "irl-coop-treasury", name: "Treasury" },
] as const;

function safeEnv(): { factory: string; singleton: string; backendKey: string } | null {
  const factory = process.env.SAFE_PROXY_FACTORY_ADDRESS ?? "";
  const singleton = process.env.SAFE_SINGLETON_ADDRESS ?? "";
  const backendKey = process.env.SAFE_BACKEND_SIGNER_KEY ?? "";
  return factory && singleton && backendKey ? { factory, singleton, backendKey } : null;
}

// Deterministic personal-Safe salt: keccak256("personal:" + sub). Stable for a
// given identity, independent of any stored secret — the account Safe address
// is predictable pre-deploy and survives a master.key rotation.
function personalSalt(sub: string): bigint {
  return BigInt(ethers.keccak256(ethers.toUtf8Bytes(`personal:${sub}`)));
}

// Deploy the personal account Safe and stamp its address on the personal group.
// Idempotent: if the group already carries a safe_address, return it untouched.
export async function ensurePersonalSafe(sub: string): Promise<string | null> {
  const env = safeEnv();
  if (!env) return null;

  try {
    // Read the personal group's current Safe address (inside the RLS identity
    // so coop_ensure_personal_group provisions it for the right sub).
    const current = await withIdentity(sub, async (client) => {
      await client.query("SELECT coop_ensure_personal_group()");
      const r = await client.query(
        `SELECT id, safe_address FROM groups WHERE kind = 'personal' AND created_by = $1 LIMIT 1`,
        [sub],
      );
      return r.rows[0] as { id: string; safe_address: string | null } | undefined;
    });
    if (!current) return null;
    if (current.safe_address) return current.safe_address;

    // Deploy on-chain (outside the transaction — no open tx across RPC).
    const provider = new ethers.JsonRpcProvider(process.env.RPC_URL ?? "http://127.0.0.1:8545");
    const signer = new ethers.Wallet(env.backendKey, provider);
    const { safeAddress } = await deploySafe(
      signer,
      { factory: env.factory, singleton: env.singleton, saltNonce: personalSalt(sub) },
      [signer.address],
      1,
    );

    // Stamp the address (owner seat makes coop_is_owner pass under RLS).
    await withIdentity(sub, async (client) => {
      await client.query(
        `UPDATE groups SET safe_address = $1 WHERE id = $2 AND kind = 'personal' AND safe_address IS NULL`,
        [safeAddress, current.id],
      );
    });
    return safeAddress;
  } catch (err) {
    console.error(`[provisioning] personal Safe failed for ${sub.slice(0, 8)}: ${(err as Error).message}`);
    return null;
  }
}

// AS-API helper: authed with the appservice as_token; the ?user_id= query
// param makes Synapse act as that user (the appservice never joins/sends
// itself — group-scoping.md §7.3).
async function asApi(pathAndQuery: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${SYNAPSE_BASE}${pathAndQuery}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${AS_TOKEN}`,
      ...(init.headers ?? {}),
    },
  });
}

function localpartFromEmail(email: string | null | undefined): string | null {
  if (!email || !email.includes("@")) return null;
  const lp = email.split("@")[0].toLowerCase().replace(/[^a-z0-9._=-]/g, "");
  return lp || null;
}

// Ensure the coop room with `alias` exists; returns its room_id (creating it if
// missing, resolving the alias if it already exists).
async function ensureCoopRoom(alias: string, name: string): Promise<string | null> {
  try {
    // Resolve first — an existing alias means the room is already provisioned.
    const dir = await asApi(`/_matrix/client/v3/directory/room/${encodeURIComponent(`#${alias}:${SERVER_NAME}`)}`);
    if (dir.ok) {
      const body = (await dir.json()) as { room_id?: string };
      if (body.room_id) return body.room_id;
    }

    // Not there — create it (as the coop-api AS, aliased).
    const create = await asApi(
      `/_matrix/client/v3/createRoom?user_id=${encodeURIComponent(`@coop-api:${SERVER_NAME}`)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, room_alias_name: alias, visibility: "private", preset: "private_chat" }),
      },
    );
    if (create.ok) {
      const body = (await create.json()) as { room_id?: string };
      if (body.room_id) return body.room_id;
    }
    const err = await create.json().catch(() => ({}));
    console.error(`[provisioning] createRoom ${alias} failed: ${create.status} ${JSON.stringify(err).slice(0, 300)}`);
    return null;
  } catch (err) {
    console.error(`[provisioning] ensureCoopRoom ${alias} failed: ${(err as Error).message}`);
    return null;
  }
}

// Register the member's Matrix account + auto-join the coop's default rooms.
// Idempotent: an existing user/room/membership is a no-op.
export async function provisionMatrix(sub: string, email: string | null | undefined): Promise<{ userId: string; rooms: string[] } | null> {
  if (!AS_TOKEN) return null;
  const localpart = localpartFromEmail(email);
  if (!localpart) return null;
  const userId = `@${localpart}:${SERVER_NAME}`;

  const joined: string[] = [];
  try {
    // 1. Register (M_USER_IN_USE = already exists — fine).
    const reg = await asApi(
      `/_matrix/client/v3/register?user_id=${encodeURIComponent(userId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "m.login.application_service", username: localpart }),
      },
    );
    if (!reg.ok) {
      const body = await reg.json().catch(() => ({}));
      if ((body as any).errcode !== "M_USER_IN_USE") {
        console.error(`[provisioning] register ${userId} failed: ${reg.status} ${JSON.stringify(body).slice(0, 300)}`);
        return null;
      }
    }

    // 2. Ensure + join each coop room (invite-first: the rooms are
    //    join_rule=invite, so a direct masquerade-join is rejected; the
    //    room creator @coop-api invites the member, then the AS joins them).
    for (const room of COOP_ROOMS) {
      const roomId = await ensureCoopRoom(room.alias, room.name);
      if (!roomId) continue;

      // Invite (as the room creator @coop-api). "already in room" / "already
      // invited" are not errors.
      const invite = await asApi(
        `/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/invite?user_id=${encodeURIComponent(`@coop-api:${SERVER_NAME}`)}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user_id: userId }) },
      );
      if (!invite.ok) {
        const ib = await invite.json().catch(() => ({}));
        const code = (ib as any).errcode ?? "";
        if (code !== "M_FORBIDDEN" && code !== "M_UNKNOWN" && invite.status !== 200 && invite.status !== 403) {
          console.error(`[provisioning] invite ${room.alias} failed: ${invite.status} ${JSON.stringify(ib).slice(0, 300)}`);
          continue;
        }
      }

      const join = await asApi(
        `/_matrix/client/v3/join/${encodeURIComponent(roomId)}?user_id=${encodeURIComponent(userId)}`,
        { method: "POST" },
      );
      if (join.ok) {
        joined.push(roomId);
      } else {
        const body = await join.json().catch(() => ({}));
        console.error(`[provisioning] join ${room.alias} failed: ${join.status} ${JSON.stringify(body).slice(0, 300)}`);
      }
    }
    return { userId, rooms: joined };
  } catch (err) {
    console.error(`[provisioning] provisionMatrix failed for ${sub.slice(0, 8)}: ${(err as Error).message}`);
    return null;
  }
}

// The sign-in hook. Fire-and-forget tolerant: never throws, always best-effort.
export async function provisionOnSignIn(
  sub: string,
  email: string | null | undefined,
  name: string | null | undefined = null,
): Promise<void> {
  await Promise.allSettled([
    ensurePersonalSafe(sub),
    provisionMatrix(sub, email),
    ensurePersonalTelephony(sub),
    ensureErpPersonalTenancy(email, name),
  ]);
}
