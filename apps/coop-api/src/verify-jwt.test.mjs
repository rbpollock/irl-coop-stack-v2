// verify-jwt.test.mjs — B-14: JWT fail-closed + alg pin + audience check.
//
//   Run: npx tsx src/verify-jwt.test.mjs
//   (coop-api has no test runner; these are node assert scripts.)

import * as crypto from "node:crypto";
import jwt from "jsonwebtoken";
import assert from "node:assert/strict";
import { execSync } from "node:child_process";

// -- helpers -----------------------------------------------------------------
function generateKeypair() {
  const kp = crypto.generateKeyPairSync("rsa", { modulusLength: 2048 });
  const privatePem = kp.privateKey.export({ format: "pem", type: "pkcs8" });
  const publicPem = kp.publicKey.export({ format: "pem", type: "spki" });
  const privateB64 = Buffer.from(privatePem).toString("base64");
  return { privatePem: privatePem.toString(), publicPem: publicPem.toString(), privateB64 };
}

function mintToken(overrides = {}) {
  return jwt.sign(
    { sub: "user-1", email: "u@irl.coop", roles: [], grants: [], groups: "[]", ...overrides },
    keypair.privatePem,
    { algorithm: "RS256", issuer: "https://api.irl.coop", audience: "irl-coop", expiresIn: "1h", keyid: "test" }
  );
}

function fakeRequest(token) {
  return { headers: { authorization: token ? `Bearer ${token}` : undefined } };
}
function fakeReply() {
  let code = 0;
  let body = null;
  return {
    code(c) { code = c; return this; },
    send(b) { body = b; },
    _code() { return code; },
    _body() { return body; },
  };
}

// -- setup: set the env var the module will read -----------------------------
const keypair = generateKeypair();
process.env.COOP_JWT_PRIVATE_KEY_B64 = keypair.privateB64;
process.env.OIDC_ISSUER = "https://api.irl.coop";

// Must import AFTER setting the env var.
const { verifyBearer } = await import("./verify-jwt.ts");

// -- tests -------------------------------------------------------------------

// 1. Valid RS256 coop JWT passes.
const good = mintToken();
const reqGood = fakeRequest(good);
const repGood = fakeReply();
const decoded = verifyBearer(reqGood, repGood);
assert.ok(decoded, "valid RS256 coop JWT should decode");
assert.equal(decoded.sub, "user-1", "sub should match");
assert.equal(repGood._code(), 0, "no error for valid token");

// 2. No Bearer header -> 401.
const reqNo = fakeRequest(null);
const repNo = fakeReply();
assert.equal(verifyBearer(reqNo, repNo), null, "missing header returns null");
assert.equal(repNo._code(), 401, "missing header -> 401");

// 3. HS256 token -> 401.
const hs256 = jwt.sign({ sub: "user-1" }, "some-secret", { algorithm: "HS256" });
const reqHs = fakeRequest(hs256);
const repHs = fakeReply();
assert.equal(verifyBearer(reqHs, repHs), null, "HS256 token rejected");
assert.equal(repHs._code(), 401, "HS256 -> 401");

// 4. Wrong audience -> 401.
const badAud = jwt.sign(
  { sub: "user-1" }, keypair.privatePem,
  { algorithm: "RS256", issuer: "https://api.irl.coop", audience: "evil-app", expiresIn: "1h" }
);
const reqAud = fakeRequest(badAud);
const repAud = fakeReply();
assert.equal(verifyBearer(reqAud, repAud), null, "wrong aud rejected");
assert.equal(repAud._code(), 401, "wrong aud -> 401");

// 5. Wrong issuer -> 401.
const badIss = jwt.sign(
  { sub: "user-1" }, keypair.privatePem,
  { algorithm: "RS256", issuer: "https://evil.coop", audience: "irl-coop", expiresIn: "1h" }
);
const reqIss = fakeRequest(badIss);
const repIss = fakeReply();
assert.equal(verifyBearer(reqIss, repIss), null, "wrong iss rejected");
assert.equal(repIss._code(), 401, "wrong iss -> 401");

// 6. Tampered token -> 401.
const tampered = good.slice(0, 10) + "X" + good.slice(11);
const reqTam = fakeRequest(tampered);
const repTam = fakeReply();
assert.equal(verifyBearer(reqTam, repTam), null, "tampered token rejected");
assert.equal(repTam._code(), 401, "tampered -> 401");

// 7. Expired token -> 401.
const expired = jwt.sign(
  { sub: "user-1" }, keypair.privatePem,
  { algorithm: "RS256", issuer: "https://api.irl.coop", audience: "irl-coop", expiresIn: "-1s" }
);
const reqExp = fakeRequest(expired);
const repExp = fakeReply();
assert.equal(verifyBearer(reqExp, repExp), null, "expired token rejected");
assert.equal(repExp._code(), 401, "expired -> 401");

console.log("verify-jwt: all B-14 assertions passed");

// 8. Boot-time check: missing COOP_JWT_PRIVATE_KEY_B64 -> throw.
try {
  execSync(
    `node -e "delete require.cache[require.resolve('./src/verify-jwt.ts')]; require('./src/verify-jwt.ts')"`,
    { encoding: "utf-8", cwd: "/home/service/development/irl-coop-stack-v2/apps/coop-api", env: { ...process.env, COOP_JWT_PRIVATE_KEY_B64: "" } }
  );
  assert.fail("missing key should throw on import");
} catch (e) {
  assert.ok(e.message.includes("COOP_JWT_PRIVATE_KEY_B64 is required"), "boot throws with clear message");
}

console.log("verify-jwt: boot check passed");
