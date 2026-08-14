// Journey: "A member signs in" — SSO through coop-api and a canonical identity.
import { makeCtx, login, env } from "../lib.mjs"

export const name = "sign-in"
export const description = "A member signs in via SSO and gets a canonical identity"

export async function run(ctx) {
  // OIDC discovery (the fleet's issuer surface).
  const discRes = await fetch(`${env.api}/.well-known/openid-configuration`)
  const disc = await discRes.json().catch(() => ({}))
  ctx.check(
    "OIDC discovery exposes issuer + endpoints",
    discRes.ok && disc.issuer === env.api && disc.jwks_uri && disc.token_endpoint && disc.authorization_endpoint,
    `issuer=${disc.issuer}`,
  )

  // JWKS — RS256 signing key with a stable kid.
  const jwksRes = await fetch(`${env.api}/jwks`)
  const jwks = await jwksRes.json().catch(() => ({}))
  const key = jwks.keys?.[0]
  ctx.check(
    "JWKS publishes an RS256 key with a kid",
    jwksRes.ok && key?.alg === "RS256" && !!key?.kid && key?.kty === "RSA",
    `kid=${key?.kid}`,
  )

  // Password direct-grant (zero redirect) → coop access_token.
  const token = await login(ctx)
  ctx.check("password login returns a coop access_token", !!token, token ? "issued" : "none")
  if (token) ctx.token = token

  // userinfo carries the canonical identity.
  const ui = await ctx.api("GET", "/api/auth/userinfo", { token })
  ctx.check(
    "userinfo returns canonical email + sub",
    ui.status === 200 && !!ui.json?.sub && ui.json?.email === env.user,
    `status=${ui.status} email=${ui.json?.email}`,
  )

  // Negative: wrong password is rejected.
  const bad = await login(ctx, env.user, "wrong-" + Date.now())
  ctx.check("wrong password is rejected (no token)", !bad, bad ? "token leaked!" : "rejected")

  // Negative: no token is rejected.
  const noTok = await ctx.api("GET", "/api/auth/userinfo")
  ctx.check("userinfo without a token is rejected (401)", noTok.status === 401, `status=${noTok.status}`)

  return token
}
