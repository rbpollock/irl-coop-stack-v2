import type { FastifyInstance } from "fastify";
import * as https from "node:https";
import { verifyBearer } from "./verify-jwt";
import { issueCodeForUser } from "./auth";

// Member-facing chat gateway — mints a Matrix access token for the authed
// member (coop-api is the OIDC issuer, so it drives the Synapse SSO flow
// server-side) and proxies the room list for the room-scoped dashboard widget.
// See docs/design/matrix-chat-and-notifications.md.

const SYNAPSE_BASE = process.env.MATRIX_BASE_URL ?? "https://matrix.irl.coop";
const COOP_API_BASE = process.env.COOP_API_BASE_URL ?? "https://api.irl.coop";

type RawResp = { status: number; location: string; body: string; setCookie: string };

// Raw GET that does NOT follow redirects — Node's fetch({redirect:"manual"})
// returns an opaque response with no headers, so we read Location/Set-Cookie
// ourselves.
function rawGet(url: string, headers?: Record<string, string>): Promise<RawResp> {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers }, (res) => {
      let body = "";
      res.on("data", (c) => (body += c));
      res.on("end", () =>
        resolve({
          status: res.statusCode ?? 0,
          location: String(res.headers.location ?? ""),
          body,
          setCookie: String(res.headers["set-cookie"] ?? ""),
        })
      );
    });
    req.on("error", reject);
    req.setTimeout(15000, () => req.destroy(new Error("timeout")));
  });
}

function queryParam(location: string, key: string): string | null {
  try {
    return new URL(location, SYNAPSE_BASE).searchParams.get(key);
  } catch {
    return null;
  }
}

async function mintMatrixAccessToken(sub: string, email: string): Promise<string> {
  const redirectUrl = `${COOP_API_BASE}/_matrix/login/callback`;

  // 1. Synapse SSO redirect -> the `state` it will expect back, plus the
  //    client-session cookie the callback needs.
  const sso = await rawGet(
    `${SYNAPSE_BASE}/_matrix/client/v3/login/sso/redirect?redirectUrl=${encodeURIComponent(redirectUrl)}`
  );
  const state = queryParam(sso.location, "state");
  if (!state) throw new Error(`synapse sso redirect returned no state (status ${sso.status})`);
  const nonce = queryParam(sso.location, "nonce") ?? undefined;
  const cookie = sso.setCookie.split(";")[0]; // first cookie: name=value

  // 2. Issue the OIDC code directly (no browser bounce) — carrying the nonce
  //    so Synapse's id_token validation (validate_nonce) passes.
  const code = await issueCodeForUser(
    sub,
    email,
    "matrix",
    `${SYNAPSE_BASE}/_synapse/client/oidc/callback`,
    state,
    nonce
  );

  // 3. Complete the callback (forwarding the client-session cookie).
  const cb = await rawGet(
    `${SYNAPSE_BASE}/_synapse/client/oidc/callback?code=${code}&state=${encodeURIComponent(state)}`,
    cookie ? { Cookie: cookie } : {}
  );
  let loginToken = queryParam(cb.location, "loginToken");
  if (!loginToken) {
    // Synapse may render a "Continue" confirmation page (200) rather than a
    // 302 — the login token is embedded in the continue link.
    const m = /loginToken=([A-Za-z0-9._-]+)/.exec(cb.body);
    loginToken = m ? m[1] : null;
  }
  if (!loginToken) {
    throw new Error(
      `synapse callback failed (status ${cb.status}): ${cb.body.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").slice(0, 600)}`
    );
  }

  // 4. Exchange the login token for the access token.
  const login = await fetch(`${SYNAPSE_BASE}/_matrix/client/v3/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "m.login.token", token: loginToken }),
  });
  const body: any = await login.json();
  if (!body.access_token) throw new Error("login token exchange failed");
  return body.access_token;
}

export default async function chatRoutes(fastify: FastifyInstance): Promise<void> {
  // The member's joined rooms (id + name) for the room-scoped chat widget.
  fastify.get("/api/v1/chat/rooms", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;

    try {
      const token = await mintMatrixAccessToken(claims.sub, claims.email ?? "");

      const joined: any = await fetch(`${SYNAPSE_BASE}/_matrix/client/v3/joined_rooms`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then((r) => r.json());

      const rooms = [];
      for (const roomId of joined.joined_rooms ?? []) {
        let name: string | null = null;
        try {
          const n = await fetch(
            `${SYNAPSE_BASE}/_matrix/client/v3/rooms/${encodeURIComponent(roomId)}/state/m.room.name`,
            { headers: { Authorization: `Bearer ${token}` } }
          );
          if (n.ok) name = ((await n.json()) as any).name ?? null;
        } catch {
          /* room name is best-effort */
        }
        rooms.push({ id: roomId, name: name ?? roomId });
      }

      return reply.send({ rooms });
    } catch (err) {
      request.log.error({ err: (err as Error).message }, "chat rooms failed");
      return reply.code(502).send({ error: "chat_rooms_failed" });
    }
  });
}
