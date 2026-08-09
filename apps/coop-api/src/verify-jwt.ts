import * as jwt from "jsonwebtoken";

const jwtSecret = process.env.JWT_SECRET ?? "local-development-secret-irl-coop-v4";

// Verify the Bearer coop-api JWT; replies 401 and returns null on failure.
export function verifyBearer(request: any, reply: any): any | null {
  const auth = request.headers.authorization ?? "";
  if (!auth.startsWith("Bearer ")) {
    reply.code(401).send({ error: "invalid_token" });
    return null;
  }
  try {
    return jwt.verify(auth.slice(7), jwtSecret);
  } catch {
    reply.code(401).send({ error: "invalid_token" });
    return null;
  }
}
