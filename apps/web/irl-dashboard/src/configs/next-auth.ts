import { cookies } from "next/headers"
import { PrismaAdapter } from "@auth/prisma-adapter"

import type { NextAuthOptions } from "next-auth"
import type { Adapter } from "next-auth/adapters"

import { db } from "@/lib/prisma"

// Extend NextAuth's Session, User, and JWT interfaces to include custom properties
declare module "next-auth" {
  interface Session {
    user: {
      id: string
      email: string | null
      name: string
      avatar: string | null
      status: string
    }
    accessToken?: string
  }

  interface User {
    id: string
    email: string | null
    name: string
    avatar: string | null
    status: string
  }
}
declare module "next-auth/jwt" {
  interface JWT {
    id: string
    email: string | null
    name: string
    avatar: string | null
    status: string
    accessToken?: string
  }
}

// The coop JWT is short-lived (1h); the coop_session cookie is the long-lived
// anchor (30d). Near expiry the jwt callback re-runs the OIDC exchange
// server-side (instant code) and swaps in a fresh token.
const COOP_API_URL = process.env.COOP_API_URL ?? "http://localhost:3001"
const COOP_CLIENT_ID = process.env.COOP_API_CLIENT_ID ?? ""
const COOP_CLIENT_SECRET = process.env.COOP_API_CLIENT_SECRET ?? ""
const COOP_CALLBACK_URL = `${process.env.NEXTAUTH_URL ?? "http://localhost:3000"}/api/auth/callback/coop-api`
const REFRESH_BEFORE_MS = 10 * 60 * 1000

function decodeJwtPayload(token: string): { exp?: number } | null {
  try {
    const part = token.split(".")[1]
    return JSON.parse(Buffer.from(part, "base64url").toString()) as {
      exp?: number
    }
  } catch {
    return null
  }
}

async function refreshCoopToken(): Promise<string | null> {
  const cookieStore = await cookies()
  const coopSession = cookieStore.get("coop_session")?.value
  if (!coopSession) return null

  // Gateway authorize with the session cookie -> instant code, no Keycloak.
  const authorize = await fetch(
    `${COOP_API_URL}/api/auth/authorize?client_id=${encodeURIComponent(COOP_CLIENT_ID)}` +
      `&redirect_uri=${encodeURIComponent(COOP_CALLBACK_URL)}&response_type=code` +
      `&scope=openid%20profile%20email&state=refresh`,
    { headers: { Cookie: `coop_session=${coopSession}` }, redirect: "manual" }
  )
  const location = authorize.headers.get("location") ?? ""
  const code = new URL(location).searchParams.get("code")
  if (!code) return null

  const tokenRes = await fetch(`${COOP_API_URL}/api/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      client_id: COOP_CLIENT_ID,
      client_secret: COOP_CLIENT_SECRET,
      redirect_uri: COOP_CALLBACK_URL,
      state: "refresh",
    }),
  })
  if (!tokenRes.ok) return null
  const data = (await tokenRes.json()) as { access_token?: string }
  return data.access_token ?? null
}

export const authOptions: NextAuthOptions = {
  adapter: PrismaAdapter(db) as Adapter,
  providers: [
    {
      id: "coop-api",
      name: "irl.coop",
      type: "oauth",
      issuer: "coop-api",
      clientId: process.env.COOP_API_CLIENT_ID ?? "",
      clientSecret: process.env.COOP_API_CLIENT_SECRET ?? "",
      client: {
        id_token_signed_response_alg: "HS256",
      },
      // Link accounts that share a verified email instead of throwing
      // OAuthAccountNotLinked. Safe: emails arrive verified from Google
      // via Keycloak, so the same person owns the account.
      allowDangerousEmailAccountLinking: true,
      authorization: {
        url: `${process.env.COOP_API_URL ?? "http://localhost:3001"}/api/auth/authorize`,
        params: { scope: "openid profile email" },
      },
      token: `${process.env.COOP_API_URL ?? "http://localhost:3001"}/api/auth/token`,
      userinfo: `${process.env.COOP_API_URL ?? "http://localhost:3001"}/api/auth/userinfo`,
      profile(profile) {
        return {
          id: profile.sub,
          name: profile.name,
          email: profile.email,
          avatar: profile.avatar,
          status: "ONLINE",
        }
      },
    },
    // Passkey login: the same coop-api client, but the authorize carries
    // kc_idp_hint=passkey → the gateway omits the Google hint → Keycloak's
    // WebAuthn passwordless form (username + the ceremony) instead of the
    // Google broker.
    {
      id: "coop-api-passkey",
      name: "irl.coop (passkey)",
      type: "oauth",
      issuer: "coop-api",
      clientId: process.env.COOP_API_CLIENT_ID ?? "",
      clientSecret: process.env.COOP_API_CLIENT_SECRET ?? "",
      client: {
        id_token_signed_response_alg: "HS256",
      },
      allowDangerousEmailAccountLinking: true,
      authorization: {
        url: `${process.env.COOP_API_URL ?? "http://localhost:3001"}/api/auth/authorize`,
        params: { scope: "openid profile email", kc_idp_hint: "passkey" },
      },
      token: `${process.env.COOP_API_URL ?? "http://localhost:3001"}/api/auth/token`,
      userinfo: `${process.env.COOP_API_URL ?? "http://localhost:3001"}/api/auth/userinfo`,
      profile(profile) {
        return {
          id: profile.sub,
          name: profile.name,
          email: profile.email,
          avatar: profile.avatar,
          status: "ONLINE",
        }
      },
    },
  ],
  pages: {
    signIn: "/sign-in",
  },
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60,
  },
  callbacks: {
    async jwt({ token, user, account, profile }) {
      if (user) {
        token.id = user.id
        token.name = user.name
        token.avatar = user.avatar ?? null
        token.email = user.email
        token.status = "ONLINE"
      }

      if (account) {
        token.accessToken = account.access_token
        // coop-api is the identity authority: its profile (incl. the
        // onboarding display name) wins over the DB user on fresh logins.
        const coopProfile = profile as { name?: string; avatar?: string } | null
        if (coopProfile?.name) token.name = coopProfile.name
        if (coopProfile?.avatar) token.avatar = coopProfile.avatar
      }

      // Refresh the coop JWT before it expires — the fleet pattern: session
      // cookie as anchor, renewable short-lived access token.
      if (token.accessToken) {
        const payload = decodeJwtPayload(token.accessToken)
        const expMs = payload?.exp ? payload.exp * 1000 : 0
        if (expMs && expMs - Date.now() < REFRESH_BEFORE_MS) {
          try {
            const fresh = await refreshCoopToken()
            if (fresh) token.accessToken = fresh
          } catch {
            // Keep the stale token — API calls 401 and the user re-logs in.
          }
        }
      }

      return token
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id
        session.user.name = token.name ?? ""
        session.user.avatar = token.avatar
        session.user.email = token.email
        session.user.status = token.status
        session.accessToken = token.accessToken
      }

      return session
    },
    async signIn({ user: _user }) {
      return true
    },
  },
}
