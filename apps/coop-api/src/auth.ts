import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import * as crypto from "node:crypto";
import * as jwt from "jsonwebtoken";
import { getProfile, type CoopProfile } from "./profile-store";
import { getUserProfile, addUserRequiredAction } from "./keycloak-admin";
import { provisionOnSignIn } from "./provisioning";
import { getRolesAndGrants } from "./db";

// ---------------------------------------------------------------------------
// coop-api as the fleet's OIDC issuer (session-gateway auth)
//
//   discovery -> GET /.well-known/openid-configuration (issuer = OIDC_ISSUER)
//   jwks      -> GET /jwks                              (RS256 signing key)
//   authorize -> GET /api/auth/authorize  (session cookie? -> code NOW, no
//                Keycloak page; else bounce to Keycloak once + set the cookie)
//   token     -> POST /api/auth/token     (code + client_id/secret -> coop JWT)
//   userinfo  -> GET /api/auth/userinfo   (coop JWT -> profile)
//   login     -> POST /api/auth/login     (password direct-grant, zero redirect)
//
// Keycloak details live ONLY here, never in the apps. The fleet apps point
// their OIDC issuer at OIDC_ISSUER and validate the coop JWT via /jwks.
// ---------------------------------------------------------------------------

const sessionTtl = (process.env.COOP_SESSION_TTL ?? "30d") as jwt.SignOptions["expiresIn"];

const env = {
  issuer: process.env.KEYCLOAK_ISSUER ?? "http://localhost:8081/realms/irl-coop",
  kcClientId: process.env.KEYCLOAK_CLIENT_ID ?? "coop-api",
  kcClientSecret: process.env.KEYCLOAK_CLIENT_SECRET ?? "",
  baseUrl: process.env.COOP_API_BASE_URL ?? "http://localhost:3001",
  oidcIssuer: process.env.OIDC_ISSUER ?? "https://api.irl.coop",
  cookieDomain: process.env.COOP_COOKIE_DOMAIN ?? ".irl.coop",
  jwtSecret: process.env.JWT_SECRET ?? "local-development-secret-irl-coop-v4",
};

// RS256 signing keypair for the coop JWT (the fleet validates via /jwks).
const keyB64 = process.env.COOP_JWT_PRIVATE_KEY_B64 ?? "";
const privateKeyPem = keyB64
  ? crypto.createPrivateKey(Buffer.from(keyB64, "base64")).export({ format: "pem", type: "pkcs8" }).toString()
  : crypto.generateKeyPairSync("rsa", { modulusLength: 2048 }).privateKey
      .export({ format: "pem", type: "pkcs8" })
      .toString();
const publicKeyPem = crypto.createPublicKey(privateKeyPem).export({ format: "pem", type: "spki" }).toString();
const publicJwk = crypto.createPublicKey(publicKeyPem).export({ format: "jwk" }) as {
  kty: string;
  n: string;
  e: string;
};
// RFC 7638 thumbprint — the stable kid the fleet sees in the JWKS.
const kid = crypto
  .createHash("sha256")
  .update(JSON.stringify({ kty: publicJwk.kty, n: publicJwk.n, e: publicJwk.e }))
  .digest("base64url");

// Fleet OIDC clients: { client_id: { secret, redirects[] } } from OIDC_CLIENTS.
type OidcClient = { secret: string; redirects: string[] };
const clients: Record<string, OidcClient> = (() => {
  try {
    const raw = JSON.parse(process.env.OIDC_CLIENTS ?? "{}") as Record<string, OidcClient>;
    // A client secret may be an ${ENV_VAR} reference — resolve it against
    // process.env (the generator emits derived secrets into secrets.env,
    // sourced by server.ts) so no secret is hardcoded in .env either.
    for (const c of Object.values(raw)) {
      const m = /^\$\{([A-Z0-9_]+)\}$/.exec(c.secret);
      if (m && process.env[m[1]]) {
        c.secret = process.env[m[1]]!;
      }
    }
    return raw;
  } catch {
    return {};
  }
})();

const KC_AUTH_URL = `${env.issuer}/protocol/openid-connect/auth`;
const KC_TOKEN_URL = `${env.issuer}/protocol/openid-connect/token`;
const KC_JWKS_URL = `${env.issuer}/protocol/openid-connect/certs`;
const KC_CALLBACK = `${env.baseUrl}/api/auth/keycloak/callback`;

const COOKIE_NAME = "coop_session";

// One-time authorization codes: code -> { jwt, clientId, redirectUri, state, nonce, expiresAt }
const codes = new Map<
  string,
  { jwt: string; clientId: string; redirectUri: string; state: string; nonce?: string; expiresAt: number }
>();
const CODE_TTL_MS = 2 * 60 * 1000; // 2 minutes

function safeEqual(a: string, b: string): boolean {
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}

function b64url(input: string): string {
  return Buffer.from(input).toString("base64url");
}

function client(id: string): OidcClient | undefined {
  return clients[id];
}

// Exchange the Keycloak authorization code for tokens (server-to-server).
async function exchangeCodeWithKeycloak(code: string): Promise<any> {
  const params = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    redirect_uri: KC_CALLBACK,
    client_id: env.kcClientId,
    client_secret: env.kcClientSecret,
  });
  const resp = await fetch(KC_TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params,
  });
  if (!resp.ok) {
    throw new Error(`keycloak token exchange failed: ${resp.status} ${await resp.text()}`);
  }
  return resp.json();
}

// Verify the Keycloak ID token: RS256 signature against realm JWKS + aud/iss/exp.
async function verifyIdToken(idToken: string): Promise<any> {
  const parts = idToken.split(".");
  if (parts.length !== 3) throw new Error("malformed id_token");
  const [h, p, s] = parts;
  const header = JSON.parse(Buffer.from(h, "base64url").toString());
  const jwksResp = await fetch(KC_JWKS_URL);
  if (!jwksResp.ok) throw new Error("failed to fetch realm JWKS");
  const jwks = await jwksResp.json();
  const key = jwks.keys.find((k: any) => k.kid === header.kid);
  if (!key) throw new Error("unknown kid in id_token");

  const kcPublic = crypto.createPublicKey({ key: { kty: key.kty, n: key.n, e: key.e }, format: "jwk" });
  const ok = crypto.verify("RSA-SHA256", Buffer.from(`${h}.${p}`), kcPublic, Buffer.from(s, "base64url"));
  if (!ok) throw new Error("id_token signature invalid");

  const payload = JSON.parse(Buffer.from(p, "base64url").toString());
  if (payload.aud !== env.kcClientId) throw new Error("id_token aud mismatch");
  if (payload.iss !== env.issuer) throw new Error("id_token iss mismatch");
  if (payload.exp && payload.exp * 1000 < Date.now()) throw new Error("id_token expired");
  return payload;
}

// The coop JWT — RS256, validated by the fleet via /jwks.
async function mintCoopJwt(
  claims: Record<string, any>,
  profile?: Partial<CoopProfile>,
  ttl: jwt.SignOptions["expiresIn"] = "1h"
): Promise<string> {
  // Resolve the member's roles + grants (union across their seats) for the
  // `roles` and `grants` claims. Best-effort: a lookup failure emits empty
  // claims rather than blocking sign-in (mirrors provisionOnSignIn).
  let roles: string[] = [];
  let grants: string[] = [];
  try {
    ({ roles, grants } = await getRolesAndGrants(claims.sub));
  } catch {
    // sign-in must not fail on a role-lookup error
  }

  // MediaMTX permissions (authJWTClaimKey: mediamtx_permissions) — the claim
  // MediaMTX's JWT auth reads to gate publish/read per path. Coarse first
  // slice: view → read any path, broadcast → publish any path. Per-group path
  // scoping (group → stream path) mirrors telephony's group → extension and is
  // the next slice.
  const mediamtx_permissions: { action: string; path: string }[] = [];
  if (grants.includes("media.stream.view")) mediamtx_permissions.push({ action: "read", path: "" });
  if (grants.includes("media.stream.broadcast")) mediamtx_permissions.push({ action: "publish", path: "" });

  // MinIO console SSO: translate grants into a MinIO `policy` claim (MinIO
  // reads MINIO_IDENTITY_OPENID_CLAIM_NAME, default "policy"). Platform-scoped
  // storage admin → consoleAdmin; everyone else gets none (they can SSO in but
  // have no console capabilities — admin only if granted).
  const policy = grants.includes("storage.platform.admin") ? "consoleAdmin" : null;

  return jwt.sign(
    {
      sub: claims.sub,
      // Live Keycloak profile wins: the canonical @irl.coop email (claimed
      // via /api/v1/me/username) must flow into every fresh JWT — the
      // login-time claims snapshot can lag it (broker idp email).
      email: profile?.email ?? claims.email ?? null,
      // Onboarded coop profile wins over the identity-provider name/avatar.
      name: profile?.displayName ?? claims.name ?? claims.preferred_username ?? null,
      avatar: profile?.avatar ?? claims.picture ?? null,
      // Keycloak asserts this at the broker; the fleet apps (plane) hard-require it.
      email_verified: claims.email_verified ?? true,
      status: "ONLINE",
      // Standard OIDC scope claim — stalwart's OIDC directory requireScopes
      // validates against this; real providers always carry it.
      scope: "openid profile email",
      // Group-model entitlements: role NAMES + resolved grant capabilities
      // (roles -> role_grants -> grants). The fleet gates (oauth2-proxy) read
      // these via --oidc-groups-claim / --allowed-group.
      roles,
      grants,
      mediamtx_permissions,
      policy,
    },
    privateKeyPem,
    {
      algorithm: "RS256",
      expiresIn: ttl,
      issuer: env.oidcIssuer,
      audience: "irl-coop",
      keyid: kid,
    }
  );
}

function verifyCoopJwt(token: string): any {
  return jwt.verify(token, publicKeyPem, { algorithms: ["RS256"], issuer: env.oidcIssuer });
}

// Server-side OIDC code issuance (no browser). The chat gateway drives the
// Synapse SSO flow programmatically for an already-authed member — `sub` and
// `email` come from the bearer coop JWT, so we mint the code directly instead
// of bouncing through the /authorize redirect.
export async function issueCodeForUser(
  sub: string,
  email: string,
  clientId: string,
  redirectUri: string,
  state: string,
  nonce?: string
): Promise<string> {
  const stored = await getProfile(sub);
  const code = crypto.randomUUID();
  codes.set(code, {
    jwt: await mintCoopJwt({ sub }, { ...stored, email }),
    clientId,
    redirectUri,
    state,
    nonce,
    expiresAt: Date.now() + CODE_TTL_MS,
  });
  return code;
}

function setSessionCookie(reply: FastifyReply, token: string, request: FastifyRequest): void {
  const host = (request.headers.host ?? "").split(":")[0];
  (reply as any).setCookie(COOKIE_NAME, token, {
    httpOnly: true,
    secure: host !== "localhost" && host !== "127.0.0.1",
    sameSite: "lax",
    path: "/",
    // Local dev has no parent domain to share; the fleet shares .irl.coop.
    domain: host === "localhost" || host === "127.0.0.1" ? undefined : env.cookieDomain,
    maxAge: 30 * 24 * 60 * 60, // 30 days
  });
}

function clearSessionCookie(reply: FastifyReply, request: FastifyRequest): void {
  const host = (request.headers.host ?? "").split(":")[0];
  (reply as any).clearCookie(COOKIE_NAME, {
    httpOnly: true,
    secure: host !== "localhost" && host !== "127.0.0.1",
    sameSite: "lax",
    path: "/",
    // Mirror setSessionCookie exactly: the browser only drops the cookie when
    // name + domain + path match what was set (secure context included).
    domain: host === "localhost" || host === "127.0.0.1" ? undefined : env.cookieDomain,
  });
}

function sessionFromRequest(request: FastifyRequest): any | null {
  const token = (request as any).cookies?.[COOKIE_NAME];
  if (!token) return null;
  try {
    return verifyCoopJwt(token);
  } catch {
    return null;
  }
}

// Session-cookie authentication for browser-served surfaces (the published
// group sites at {groupname}.irl.coop): the coop_session cookie IS a coop JWT
// (same RS256 key, sub + email), so we verify it directly instead of requiring
// a Bearer header a static site can't hold. Read-only surfaces use this; write
// endpoints stay Bearer-only (short-lived token).
export function verifySessionRequest(request: FastifyRequest, reply: FastifyReply): any | null {
  const session = sessionFromRequest(request);
  if (!session) {
    reply.code(401).send({ error: "invalid_session" });
    return null;
  }
  return session;
}

export default async function authRoutes(fastify: FastifyInstance): Promise<void> {
  // ---- OIDC discovery + JWKS (the fleet's issuer surface) ----
  fastify.get("/.well-known/openid-configuration", async () => ({
    issuer: env.oidcIssuer,
    authorization_endpoint: `${env.baseUrl}/api/auth/authorize`,
    token_endpoint: `${env.baseUrl}/api/auth/token`,
    userinfo_endpoint: `${env.baseUrl}/api/auth/userinfo`,
    jwks_uri: `${env.baseUrl}/jwks`,
    response_types_supported: ["code"],
    subject_types_supported: ["public"],
    id_token_signing_alg_values_supported: ["RS256"],
    scopes_supported: ["openid", "profile", "email"],
    grant_types_supported: ["authorization_code", "password"],
  }));

  fastify.get("/jwks", async () => ({
    keys: [
      {
        kid,
        kty: publicJwk.kty,
        use: "sig",
        alg: "RS256",
        n: publicJwk.n,
        e: publicJwk.e,
      },
    ],
  }));

  // ---- global logout: drop the fleet coop_session cookie and return to the
  // dashboard. Reached via the FusionPBX "log out" -> oauth2-proxy /oauth2/sign_out
  // chain (the gate clears its own _oauth2_proxy cookie first, then redirects here).
  fastify.get("/api/auth/logout", async (request, reply) => {
    clearSessionCookie(reply, request);
    return reply.redirect("https://irl.coop/");
  });

  // ---- authorize: session cookie? -> code now (no Keycloak page). ----
  //     No session -> bounce to Keycloak once; the callback sets the cookie.
  fastify.get("/api/auth/authorize", async (request, reply) => {
    const q = request.query as Record<string, string | undefined>;
    const { client_id, redirect_uri, response_type, state, scope, nonce } = q;
    const app = client(client_id ?? "");

    if (!app || !app.redirects.includes(redirect_uri ?? "")) {
      return reply.code(400).send({ error: "invalid_request", error_description: "unknown client or redirect_uri" });
    }
    if (response_type !== "code" || !state) {
      return reply.code(400).send({ error: "invalid_request", error_description: "response_type=code and state are required" });
    }

    // Already authenticated with the coop-api? Issue the code directly.
    const session = sessionFromRequest(request);
    if (session) {
      // A session cookie can outlive its Keycloak user (deletion or a realm
      // wipe/rotation). Treat a stale sub as "not authenticated": drop the
      // cookie and fall through to the Keycloak bounce so sign-in self-heals
      // instead of 500ing every fleet app that re-authorizes.
      try {
        const live = await getUserProfile(session.sub);
        const code = crypto.randomUUID();
        // Re-mint with the LIVE Keycloak email: the session cookie may predate
        // the canonical-email claim, and its claims snapshot would leak the
        // broker email into fleet apps (roundcube → stalwart IMAP). getProfile()
        // is the local onboarding store (name/avatar) — the email authority is
        // the Keycloak admin lookup.
        const stored = await getProfile(session.sub);
        codes.set(code, {
          jwt: await mintCoopJwt(session, { ...stored, email: live.email ?? null }),
          clientId: client_id!,
          redirectUri: redirect_uri!,
          state,
          nonce,
          expiresAt: Date.now() + CODE_TTL_MS,
        });
        return reply.redirect(`${redirect_uri}?code=${code}&state=${encodeURIComponent(state)}`);
      } catch (err) {
        request.log.warn(
          { sub: session.sub, err: (err as Error).message },
          "stale session (sub not in Keycloak); clearing cookie and re-authenticating"
        );
        clearSessionCookie(reply, request);
        // fall through to the Keycloak bounce below
      }
    }

    const kcState = b64url(JSON.stringify({ n: state, r: redirect_uri, c: client_id, o: nonce }));
    // kc_idp_hint=google (default): Keycloak skips its own sign-in page and
    // bounces straight to the Google broker (the realm's only interactive
    // login). An EXPLICIT request param overrides the default: the passkey
    // provider sends kc_idp_hint=passkey → no hint → the Keycloak
    // WebAuthn passwordless form (username + the ceremony).
    const hintParam = (request.query as Record<string, string | undefined>).kc_idp_hint;
    // default = google; the explicit `passkey` value opts out
    const kcHint = hintParam === "passkey" ? undefined : "google";
    const authorizeUrl =
      `${KC_AUTH_URL}?client_id=${encodeURIComponent(env.kcClientId)}` +
      `&redirect_uri=${encodeURIComponent(KC_CALLBACK)}` +
      `&response_type=code` +
      `&scope=${encodeURIComponent(scope ?? "openid profile email")}` +
      `&state=${encodeURIComponent(kcState)}` +
      `&nonce=${crypto.randomUUID()}` +
      (kcHint ? `&kc_idp_hint=${kcHint}` : "");
    return reply.redirect(authorizeUrl);
  });

  // Keycloak (after Google/password) sends the browser back here with a code.
  fastify.get("/api/auth/keycloak/callback", async (request, reply) => {
    const q = request.query as Record<string, string | undefined>;

    let nextState = "";
    let nextRedirect = "";
    let nextClient = "";
    let nextNonce: string | undefined;
    try {
      const baked = JSON.parse(Buffer.from(q.state ?? "", "base64url").toString());
      nextState = baked.n ?? "";
      nextRedirect = baked.r ?? "";
      nextClient = baked.c ?? "";
      nextNonce = baked.o ?? undefined;
    } catch {
      return reply.code(400).send({ error: "invalid_request", error_description: "bad state" });
    }
    const app = client(nextClient);
    if (!app || !app.redirects.includes(nextRedirect)) {
      return reply.code(400).send({ error: "invalid_request", error_description: "bad client/redirect in state" });
    }

    if (q.error) {
      return reply.redirect(`${nextRedirect}?error=${encodeURIComponent(q.error)}&state=${encodeURIComponent(nextState)}`);
    }
    if (!q.code) {
      return reply.redirect(`${nextRedirect}?error=access_denied&state=${encodeURIComponent(nextState)}`);
    }

    try {
      const tokens = await exchangeCodeWithKeycloak(q.code);
      const claims = await verifyIdToken(tokens.id_token);
      // Invite-on-first-signin: deploy the personal Safe + provision Matrix.
      // Best-effort, idempotent — never blocks the sign-in redirect.
      await provisionOnSignIn(claims.sub, claims.email);
      const stored = await getProfile(claims.sub);
      const coopJwt = await mintCoopJwt(claims, stored);

      // The coop session: subsequent authorize calls skip the Keycloak page.
      const sessionJwt = await mintCoopJwt(claims, stored, sessionTtl);
      setSessionCookie(reply, sessionJwt, request);

      const code = crypto.randomUUID();
      codes.set(code, { jwt: coopJwt, clientId: nextClient, redirectUri: nextRedirect, state: nextState, nonce: nextNonce, expiresAt: Date.now() + CODE_TTL_MS });
      return reply.redirect(`${nextRedirect}?code=${code}&state=${encodeURIComponent(nextState)}`);
    } catch (err: any) {
      request.log.error({ err: err.message }, "keycloak callback failed");
      return reply.redirect(`${nextRedirect}?error=server_error&state=${encodeURIComponent(nextState)}`);
    }
  });

  // Code exchange: code + client credentials -> coop JWT (+ id_token for NextAuth).
  fastify.post("/api/auth/token", async (request, reply) => {
    const body = (request.body ?? {}) as Record<string, string>;
    let clientId = body.client_id ?? "";
    let clientSecret = body.client_secret ?? "";

    const authHeader = request.headers.authorization ?? "";
    if (authHeader.startsWith("Basic ")) {
      try {
        const decoded = Buffer.from(authHeader.slice(6), "base64").toString();
        const idx = decoded.indexOf(":");
        if (idx >= 0) {
          clientId = decoded.slice(0, idx);
          clientSecret = decoded.slice(idx + 1);
        }
      } catch {
        /* fall through to form fields */
      }
    }

    if (body.grant_type !== "authorization_code") {
      return reply.code(400).send({ error: "unsupported_grant_type" });
    }
    const app = client(clientId);
    if (!app || !safeEqual(clientSecret, app.secret)) {
      return reply.code(401).send({ error: "invalid_client" });
    }

    const entry = codes.get(body.code ?? "");
    if (!entry || entry.expiresAt < Date.now()) {
      codes.delete(body.code ?? "");
      return reply.code(400).send({ error: "invalid_grant", error_description: "unknown or expired code" });
    }
    if (entry.clientId !== clientId) {
      return reply.code(400).send({ error: "invalid_grant", error_description: "client mismatch" });
    }
    if (!app.redirects.includes(body.redirect_uri ?? "") || entry.redirectUri !== body.redirect_uri) {
      return reply.code(400).send({ error: "invalid_grant", error_description: "redirect_uri mismatch" });
    }
    if (entry.state !== body.state && body.state) {
      return reply.code(400).send({ error: "invalid_grant", error_description: "state mismatch" });
    }

    codes.delete(body.code ?? ""); // single use
    const access: any = jwt.verify(entry.jwt, publicKeyPem, { algorithms: ["RS256"] });
    const now = Math.floor(Date.now() / 1000);
    // id_token: proper OIDC shape for strict consumers (oauth2-proxy, Synapse
    // — they validate iss against the DISCOVERED issuer and the signature via
    // /jwks), HS256/iss:coop-api only for the NextAuth leg (its provider
    // config declares issuer "coop-api" + id_token_signed_response_alg HS256).
    const isNextAuth = clientId === "nextauth";
    const nonce = entry.nonce;
    const idToken = isNextAuth
      ? jwt.sign(
          {
            iss: "coop-api",
            sub: access.sub,
            aud: clientId,
            email: access.email,
            name: access.name,
            avatar: access.avatar,
            roles: access.roles ?? [],
            grants: access.grants ?? [],
            nonce,
            iat: now,
            exp: now + 3600,
          },
          app.secret,
          { algorithm: "HS256" }
        )
      : jwt.sign(
          {
            iss: env.oidcIssuer,
            sub: access.sub,
            aud: clientId,
            azp: clientId,
            email: access.email,
            email_verified: access.email_verified ?? true,
            name: access.name,
            avatar: access.avatar,
            roles: access.roles ?? [],
            grants: access.grants ?? [],
            policy: access.policy ?? null,
            nonce,
            iat: now,
            exp: now + 3600,
          },
          privateKeyPem,
          { algorithm: "RS256", keyid: kid }
        );
    return reply.send({
      access_token: entry.jwt,
      id_token: idToken,
      token_type: "Bearer",
      expires_in: 3600,
    });
  });

  // Profile for the bearer coop JWT.
  fastify.get("/api/auth/userinfo", async (request, reply) => {
    const authHeader = request.headers.authorization ?? "";
    if (!authHeader.startsWith("Bearer ")) {
      return reply.code(401).send({ error: "invalid_token" });
    }
    try {
      const decoded: any = verifyCoopJwt(authHeader.slice(7));
      // Re-resolve roles/grants from the live DB so a promote/demote takes
      // effect on the next gate refresh (oauth2-proxy --cookie-refresh) without
      // a full re-login. Best-effort: fall back to the JWT snapshot on lookup
      // failure so userinfo never 500s on a transient DB blip.
      let roles = decoded.roles ?? [];
      let grants = decoded.grants ?? [];
      try {
        ({ roles, grants } = await getRolesAndGrants(decoded.sub));
      } catch {
        // keep the snapshot
      }
      return reply.send({
        sub: decoded.sub,
        id: decoded.sub,
        email: decoded.email,
        name: decoded.name,
        avatar: decoded.avatar,
        // Plane reads `picture` for the avatar; coop emits `avatar` — expose both.
        picture: decoded.avatar ?? null,
        email_verified: decoded.email_verified ?? true,
        status: decoded.status ?? "ONLINE",
        roles,
        grants,
      });
    } catch {
      return reply.code(401).send({ error: "invalid_token" });
    }
  });

  // Password login: coop-api performs the auth server-side (zero redirect,
  // no Keycloak page). Sets the session cookie for the SSO gateway.
  fastify.post("/api/auth/login", async (request, reply) => {
    const body = (request.body ?? {}) as Record<string, string>;
    const { username, password } = body;
    if (!username || !password) {
      return reply.code(400).send({ error: "invalid_request", error_description: "username and password required" });
    }
    try {
      const params = new URLSearchParams({
        grant_type: "password",
        client_id: env.kcClientId,
        client_secret: env.kcClientSecret,
        username,
        password,
        scope: "openid profile email",
      });
      const resp = await fetch(KC_TOKEN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params,
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        return reply.code(401).send({ error: err.error ?? "invalid_grant", error_description: err.error_description ?? "bad credentials" });
      }
      const tokens = await resp.json();
      const claims = await verifyIdToken(tokens.id_token);
      // Same invite-on-first-signin provisioning as the OAuth callback.
      await provisionOnSignIn(claims.sub, claims.email);
      const stored = await getProfile(claims.sub);
      const coopJwt = await mintCoopJwt(claims, stored);
      setSessionCookie(reply, await mintCoopJwt(claims, stored, sessionTtl), request);
      return reply.send({ access_token: coopJwt, token_type: "Bearer", expires_in: 3600 });
    } catch (err: any) {
      request.log.error({ err: err.message }, "login failed");
      return reply.code(502).send({ error: "server_error" });
    }
  });

  // Diagnostics: the effective URL chain + fleet client registry.
  fastify.get("/api/auth/config", async () => ({
    oidc: {
      issuer: env.oidcIssuer,
      discovery: `${env.baseUrl}/.well-known/openid-configuration`,
      jwks: `${env.baseUrl}/jwks`,
      authorize: `${env.baseUrl}/api/auth/authorize`,
      token: `${env.baseUrl}/api/auth/token`,
      userinfo: `${env.baseUrl}/api/auth/userinfo`,
      login: `${env.baseUrl}/api/auth/login`,
      sessionCookie: COOKIE_NAME,
    },
    keycloak: {
      issuer: env.issuer,
      clientId: env.kcClientId,
      callback: KC_CALLBACK,
      googleBroker: `${env.issuer}/broker/google/endpoint`,
    },
    clients: Object.fromEntries(Object.entries(clients).map(([id, c]) => [id, { redirects: c.redirects }])),
  }));

  // Link a passkey: adds the webauthn required action and redirects to Keycloak
  fastify.get("/api/v1/auth/passkey/link", async (request, reply) => {
    const session = sessionFromRequest(request);
    if (!session) {
      const host = (request.headers.host ?? "").split(":")[0];
      const base = host === "localhost" || host === "127.0.0.1" ? "http://localhost:3000" : "https://irl.coop";
      return reply.redirect(`${base}/en/sign-in`);
    }

    try {
      // 1. Add Keycloak required action directly
      await addUserRequiredAction(session.sub, "webauthn-register-passwordless");
      
      // 2. Build direct redirect to Keycloak authorize URL bypassing silent authorize code-gen
      const host = (request.headers.host ?? "").split(":")[0];
      const base = host === "localhost" || host === "127.0.0.1" ? "http://localhost:3000" : "https://irl.coop";
      const nextRedirect = `${base}/en/pages/account/settings/security`;
      
      const kcState = b64url(JSON.stringify({ 
        n: "link_passkey", 
        r: nextRedirect, 
        c: "nextauth" 
      }));

      // Redirect directly to Keycloak authorize (bypassing Google hint so they can do passkey ceremony)
      const authorizeUrl =
        `${KC_AUTH_URL}?client_id=${encodeURIComponent(env.kcClientId)}` +
        `&redirect_uri=${encodeURIComponent(KC_CALLBACK)}` +
        `&response_type=code` +
        `&scope=${encodeURIComponent("openid profile email")}` +
        `&state=${encodeURIComponent(kcState)}` +
        `&nonce=${crypto.randomUUID()}`;
        
      return reply.redirect(authorizeUrl);
    } catch (err: any) {
      request.log.error({ err: err.message }, "passkey linking initiation failed");
      const host = (request.headers.host ?? "").split(":")[0];
      const base = host === "localhost" || host === "127.0.0.1" ? "http://localhost:3000" : "https://irl.coop";
      return reply.redirect(`${base}/en/pages/account/settings/security?error=linking_failed`);
    }
  });
}
