// invite-token.test.mjs — verifies the signed token primitives run (slice-1).
import { signInvite, verifyInvite } from "./invite-token.mjs";
import assert from "node:assert/strict";

const secret = "invite-signing-secret-" + "x".repeat(24);
const future = Math.floor(Date.now() / 1000) + 3600;
const past = Math.floor(Date.now() / 1000) - 10;

// happy path
const t = signInvite({ id: "inv_1", email: "A@B.com", exp: future }, secret);
const got = verifyInvite(t, secret);
assert.ok(got, "should verify");
assert.equal(got.email, "a@b.com", "email normalized lowercase");
assert.equal(got.id, "inv_1");

// tamper
const tampered = t.slice(0, -2) + (t.endsWith("AA") ? "BB" : "AA");
assert.equal(verifyInvite(tampered, secret), null, "tampered token rejected");
// wrong secret
assert.equal(verifyInvite(t, secret + "nope"), null, "wrong secret rejected");
// construct but wrong structure
assert.equal(verifyInvite("garbage", secret), null);
// expired
const exp = signInvite({ id: "inv_2", email: "x@y.co", exp: past }, secret);
assert.equal(verifyInvite(exp, secret), null, "expired rejected");

console.log("invite-token: all assertions passed");