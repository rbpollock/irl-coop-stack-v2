import type { FastifyInstance } from "fastify";
import * as crypto from "node:crypto";
import * as jwt from "jsonwebtoken";
import { getProfile, type CoopProfile } from "./profile-store";

// ---------------------------------------------------------------------------
// coop-api OAuth bridge: NextAuth <-> coop-api <-> Keycloak (Google broker)
//
// NextAuth treats coop-api as a plain OAuth2 provider:
//   authorize  -> GET  /api/auth/authorize        (302 -> Keycloak)
//   token      -> POST /api/auth/token            (code -> coop-api JWT)
//   userinfo   -> GET  /api/auth/userinfo         (JWT -> profile)
// Keycloak details live ONLY here, never in the Next.js app.
// ---------------------------------------------------------------------------

const env = {
  issuer: process.env.KEYCLOAK_ISSUER ?? "http://localhost:8081/realms/irl-coop",
  kcClientId: process.env.KEYCLOAK_CLIENT_ID ?? "coop-api",
  kcClientSecret: process.env.KEYCLOAK_CLIENT_SECRET ?? "",
  baseUrl: process.env.COOP_API_BASE_URL ?? "http://localhost:3001",
  oauthClientId: process.env.OAUTH_CLIENT_ID ?? "nextauth",
  oauthClientSecret: process.env.OAUTH_CLIENT_SECRET ?? "",
  jwtSecret: process.env.JWT_SECRET ?? "local-development-secret-irl-coop-v4",
};

const KC_AUTH_URL = `${env.issuer}/protocol/openid-connect/auth`;
const KC_TOKEN_URL = `${env.issuer}/protocol/openid-connect/token`;
const KC_JWKS_URL = `${env.issuer}/protocol/openid-connect/certs`;
const KC_CALLBACK = `${env.baseUrl}/api/auth/keycloak/callback`;

// NextAuth callback URIs we are allowed to redirect the browser back to.
// localhost stays for the local dev loop; the canonical form is what the
// public edge (irl.coop) presents.
const ALLOWED_REDIRECTS = new Set([
  "http://localhost:3000/api/auth/callback/coop-api",
  "https://irl.coop/api/auth/callback/coop-api",
]);

// One-time authorization codes: code -> { jwt, redirectUri, state, expiresAt }
const codes = new Map<
  string,
  { jwt: string; redirectUri: string; state: string; expiresAt: number }
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

  const publicKey = crypto.createPublicKey({ key: { kty: key.kty, n: key.n, e: key.e }, format: "jwk" });
  const ok = crypto.verify("RSA-SHA256", Buffer.from(`${h}.${p}`), publicKey, Buffer.from(s, "base64url"));
  if (!ok) throw new Error("id_token signature invalid");

  const payload = JSON.parse(Buffer.from(p, "base64url").toString());
  if (payload.aud !== env.kcClientId) throw new Error("id_token aud mismatch");
  if (payload.iss !== env.issuer) throw new Error("id_token iss mismatch");
  if (payload.exp && payload.exp * 1000 < Date.now()) throw new Error("id_token expired");
  return payload;
}

function mintCoopJwt(claims: Record<string, any>, profile?: CoopProfile): string {
  return jwt.sign(
    {
      sub: claims.sub,
      email: claims.email ?? null,
      // Onboarded coop profile wins over the identity-provider name/avatar.
      name: profile?.displayName ?? claims.name ?? claims.preferred_username ?? null,
      avatar: profile?.avatar ?? claims.picture ?? null,
      status: "ONLINE",
    },
    env.jwtSecret,
    { expiresIn: "1h", issuer: "coop-api", audience: "irl-coop" }
  );
}

export default async function authRoutes(fastify: FastifyInstance): Promise<void> {
  // Step 1: NextAuth bounces the browser here. We bounce it on to Keycloak,
  // baking NextAuth's state + redirect_uri into OUR state so they survive
  // the round trip through Keycloak untouched.
  fastify.get("/api/auth/authorize", async (request, reply) => {
    const q = request.query as Record<string, string | undefined>;
    const { client_id, redirect_uri, response_type, state, scope } = q;

    if (client_id !== env.oauthClientId || !ALLOWED_REDIRECTS.has(redirect_uri ?? "")) {
      return reply.code(400).send({ error: "invalid_request", error_description: "unknown client or redirect_uri" });
    }
    if (response_type !== "code" || !state) {
      return reply.code(400).send({ error: "invalid_request", error_description: "response_type=code and state are required" });
    }

    const kcState = b64url(JSON.stringify({ n: state, r: redirect_uri }));
    const authorizeUrl =
      `${KC_AUTH_URL}?client_id=${encodeURIComponent(env.kcClientId)}` +
      `&redirect_uri=${encodeURIComponent(KC_CALLBACK)}` +
      `&response_type=code` +
      `&scope=${encodeURIComponent(scope ?? "openid profile email")}` +
      `&state=${encodeURIComponent(kcState)}` +
      `&nonce=${crypto.randomUUID()}`;
    return reply.redirect(authorizeUrl);
  });

  // Step 2: Keycloak (after Google) sends the browser back here with a code.
  fastify.get("/api/auth/keycloak/callback", async (request, reply) => {
    const q = request.query as Record<string, string | undefined>;

    // Un-bake NextAuth's state + redirect_uri.
    let nextState = "";
    let nextRedirect = "";
    try {
      const baked = JSON.parse(Buffer.from(q.state ?? "", "base64url").toString());
      nextState = baked.n ?? "";
      nextRedirect = baked.r ?? "";
    } catch {
      return reply.code(400).send({ error: "invalid_request", error_description: "bad state" });
    }
    if (!ALLOWED_REDIRECTS.has(nextRedirect)) {
      return reply.code(400).send({ error: "invalid_request", error_description: "bad redirect_uri in state" });
    }

    // Keycloak error (e.g. user cancelled) -> hand it back to NextAuth.
    if (q.error) {
      return reply.redirect(`${nextRedirect}?error=${encodeURIComponent(q.error)}&state=${encodeURIComponent(nextState)}`);
    }
    if (!q.code) {
      return reply.redirect(`${nextRedirect}?error=access_denied&state=${encodeURIComponent(nextState)}`);
    }

    try {
      const tokens = await exchangeCodeWithKeycloak(q.code);
      const claims = await verifyIdToken(tokens.id_token);
      const coopJwt = mintCoopJwt(claims, getProfile(claims.sub));

      const code = crypto.randomUUID();
      codes.set(code, { jwt: coopJwt, redirectUri: nextRedirect, state: nextState, expiresAt: Date.now() + CODE_TTL_MS });

      return reply.redirect(`${nextRedirect}?code=${code}&state=${encodeURIComponent(nextState)}`);
    } catch (err: any) {
      request.log.error({ err: err.message }, "keycloak callback failed");
      return reply.redirect(`${nextRedirect}?error=server_error&state=${encodeURIComponent(nextState)}`);
    }
  });

  // Step 3: NextAuth exchanges the one-time code for the coop-api JWT.
  // Accepts client credentials via Basic auth (openid-client default) or form fields.
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
    if (clientId !== env.oauthClientId || !safeEqual(clientSecret, env.oauthClientSecret)) {
      return reply.code(401).send({ error: "invalid_client" });
    }

    const entry = codes.get(body.code ?? "");
    if (!entry || entry.expiresAt < Date.now()) {
      codes.delete(body.code ?? "");
      return reply.code(400).send({ error: "invalid_grant", error_description: "unknown or expired code" });
    }
    if (!ALLOWED_REDIRECTS.has(body.redirect_uri ?? "") || entry.redirectUri !== body.redirect_uri) {
      return reply.code(400).send({ error: "invalid_grant", error_description: "redirect_uri mismatch" });
    }
    if (entry.state !== body.state && body.state) {
      return reply.code(400).send({ error: "invalid_grant", error_description: "state mismatch" });
    }

    codes.delete(body.code ?? ""); // single use
    // openid-client (NextAuth) validates an id_token for code flows, so act
    // like a proper OIDC provider: mint an HS256 id_token signed with the
    // shared NextAuth secret (iss/aud match the provider config in next-auth.ts).
    const access: any = jwt.verify(entry.jwt, env.jwtSecret);
    const now = Math.floor(Date.now() / 1000);
    const idToken = jwt.sign(
      {
        iss: "coop-api",
        sub: access.sub,
        aud: env.oauthClientId,
        email: access.email,
        name: access.name,
        avatar: access.avatar,
        iat: now,
        exp: now + 3600,
      },
      env.oauthClientSecret,
      { algorithm: "HS256" }
    );
    return reply.send({
      access_token: entry.jwt,
      id_token: idToken,
      token_type: "Bearer",
      expires_in: 3600,
    });
  });

  // Step 4: NextAuth fetches the profile with the coop-api JWT.
  fastify.get("/api/auth/userinfo", async (request, reply) => {
    const authHeader = request.headers.authorization ?? "";
    if (!authHeader.startsWith("Bearer ")) {
      return reply.code(401).send({ error: "invalid_token" });
    }
    try {
      const decoded: any = jwt.verify(authHeader.slice(7), env.jwtSecret);
      return reply.send({
        sub: decoded.sub,
        id: decoded.sub,
        email: decoded.email,
        name: decoded.name,
        avatar: decoded.avatar,
        status: decoded.status ?? "ONLINE",
      });
    } catch {
      return reply.code(401).send({ error: "invalid_token" });
    }
  });

  // Diagnostics: show the effective URL chain (redirect-URI matrix self-check).
  fastify.get("/api/auth/config", async () => ({
    oauth: {
      authorize: `${env.baseUrl}/api/auth/authorize`,
      token: `${env.baseUrl}/api/auth/token`,
      userinfo: `${env.baseUrl}/api/auth/userinfo`,
    },
    keycloak: {
      issuer: env.issuer,
      clientId: env.kcClientId,
      callback: KC_CALLBACK,
      jwks: KC_JWKS_URL,
      googleBroker: `${env.issuer}/broker/google/endpoint`,
    },
    allowedRedirects: [...ALLOWED_REDIRECTS],
  }));
}
