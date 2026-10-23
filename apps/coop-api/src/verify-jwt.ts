import * as crypto from "node:crypto";
import * as jwt from "jsonwebtoken";

const oidcIssuer = process.env.OIDC_ISSUER ?? "https://api.irl.coop";
const expectedAudience = process.env.COOP_JWT_AUDIENCE ?? "irl-coop";

// Fail-closed: the coop JWT layer MUST have a key or it must not start.
// A missing key is a configuration error, not a reason to fall back to a
// hardcoded secret (F4) or to accept any token.
const keyB64 = process.env.COOP_JWT_PRIVATE_KEY_B64;
if (!keyB64) {
  throw new Error("COOP_JWT_PRIVATE_KEY_B64 is required — the coop JWT layer must not start without a key");
}

const publicKey = crypto.createPublicKey(Buffer.from(keyB64, "base64"));

const verifyOptions: jwt.VerifyOptions = {
  // Only RS256 is acceptable. HS256 is rejected (F4).
  algorithms: ["RS256"],
  issuer: oidcIssuer,
  // Audience must match what the issuer mints (F5).
  audience: expectedAudience,
};

// Verify the Bearer coop JWT; replies 401 and returns null on failure.
export function verifyBearer(request: any, reply: any): any | null {
  const auth = request.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) {
    reply.code(401).send({ error: "invalid_token" });
    return null;
  }
  try {
    return jwt.verify(auth.slice(7), publicKey, verifyOptions);
  } catch {
    reply.code(401).send({ error: "invalid_token" });
    return null;
  }
}
