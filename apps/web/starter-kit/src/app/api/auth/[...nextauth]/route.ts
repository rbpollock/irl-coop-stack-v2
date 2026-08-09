import NextAuth from "next-auth";
import KeycloakProvider from "next-auth/providers/keycloak";

const handler = NextAuth({
  providers: [
    KeycloakProvider({
      clientId: process.env.KEYCLOAK_ID || "web-app",
      clientSecret: process.env.KEYCLOAK_SECRET || "dummy-secret-for-local",
      issuer: process.env.KEYCLOAK_ISSUER || "http://localhost:8081/realms/irl-coop",
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      if (account) {
        token.accessToken = account.access_token;
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).accessToken = token.accessToken;
      return session;
    },
  },
  secret: process.env.NEXTAUTH_SECRET || "local-development-secret-irl-coop-v4",
});

export { handler as GET, handler as POST };
