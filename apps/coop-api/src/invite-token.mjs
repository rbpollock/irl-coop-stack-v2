// invite-token.mjs — signed, single-use invitation token (slice-1 core).
//
// An invitation carries a SHORT signed URL token, not a stored secret. The signature
// binds the invite id + canonical email + expiry under a derived secret
// (INVITE_SIGNING_SECRET). Nothing in the payload is secret — the security is that
// only the immutable identity owning that email can redeem a token against the live
// profile, and the row is single-use + revocable server-side.
//
// Format: `v1.<payloadB64url>.<sig>` where payload = `id|email|expEpoch`.

import { createHmac, timingSafeEqual } from "node:crypto";

const PREFIX = "v1";

function mac(secret, data) {
  return createHmac("sha256", secret).update(data).digest();
}
function b64url(buf) {
  return buf
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/** signInvite({id, email, exp}, secret) -> signed token string. */
export function signInvite(p, secret) {
  if (!secret || secret.length < 24)
    throw new Error("INVITE_SIGNING_SECRET must be at least 24 chars");
  const body = [p.id, String(p.email || "").toLowerCase(), String(p.exp || 0)].join("|");
  const sig = b64url(mac(secret, PREFIX + "\u0000" + body));
  return `${PREFIX}.${b64url(Buffer.from(body, "utf8"))}.${sig}`;
}

/** verify(token, secret) -> {id, email, exp} | null. Rejects bad sig or expired. */
export function verifyInvite(token, secret) {
  const parts = String(token || "").split(".");
  if (parts.length !== 3 || parts[0] !== PREFIX) return null;
  let body;
  try {
    body = Buffer.from(parts[1], "base64url").toString("utf8");
  } catch {
    return null;
  }
  const expect = b64url(mac(secret, PREFIX + "\u0000" + body));
  const got = parts[2];
  if (!expect || expect.length !== got.length) return null;
  if (!timingSafeEqual(Buffer.from(expect), Buffer.from(got))) return null;
  const [id, email, expS] = body.split("|");
  if (!id || !email) return null;
  const exp = Number(expS || 0);
  if (exp && exp < Math.floor(Date.now() / 1000)) return null; // expired
  return { id, email, exp };
}