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
