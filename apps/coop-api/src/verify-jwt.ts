import * as crypto from "node:crypto";
import * as jwt from "jsonwebtoken";

const jwtSecret = process.env.JWT_SECRET ?? "local-development-secret-irl-coop-v4";
const oidcIssuer = process.env.OIDC_ISSUER ?? "https://api.irl.coop";

// The coop JWT is RS256 (signed by the private key derived from
// COOP_JWT_PRIVATE_KEY_B64); verify with the matching public key.
const keyB64 = process.env.COOP_JWT_PRIVATE_KEY_B64 ?? "";
const publicKey = keyB64
  ? crypto.createPublicKey(Buffer.from(keyB64, "base64"))
  : null;

// Verify the Bearer coop JWT; replies 401 and returns null on failure.
// The irl-dashboard holds this JWT (minted at the OAuth token exchange) in its
// NextAuth session — sub is the Keycloak user id.
export function verifyBearer(request: any, reply: any): any | null {
  const auth = request.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) {
    reply.code(401).send({ error: "invalid_token" });
    return null;
  }
  try {
    if (publicKey) {
      return jwt.verify(auth.slice(7), publicKey, {
        algorithms: ["RS256"],
        issuer: oidcIssuer,
      });
    }
    return jwt.verify(auth.slice(7), jwtSecret);
  } catch {
    reply.code(401).send({ error: "invalid_token" });
    return null;
  }
}
