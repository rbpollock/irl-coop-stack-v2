import { generateWebAuthnKeyPair, createECDSASigner } from "./mock_signers";
import * as assert from "assert";
import * as crypto from "crypto";

function testSigners() {
  console.log("Starting mock signers unit tests...");

  // 1. Test standard ECDSA Signer
  const ecdsa = createECDSASigner();
  console.log(`- Created ECDSA signer with address: ${ecdsa.address}`);
  assert.ok(ecdsa.address.startsWith("0x"));
  assert.strictEqual(ecdsa.address.length, 42);

  // 2. Test biometric WebAuthn Signer
  const webauthn = generateWebAuthnKeyPair();
  console.log(`- Generated WebAuthn keypair. PublicKey coordinates:`);
  console.log(`  X: ${webauthn.publicKey.x}`);
  console.log(`  Y: ${webauthn.publicKey.y}`);
  
  assert.ok(webauthn.publicKey.x.startsWith("0x"));
  assert.strictEqual(webauthn.publicKey.x.length, 66); // 0x + 64 hex characters
  assert.ok(webauthn.publicKey.y.startsWith("0x"));
  assert.strictEqual(webauthn.publicKey.y.length, 66);

  const challenge = crypto.randomBytes(32).toString("hex");
  const signature = webauthn.signChallenge(challenge);

  console.log(`- WebAuthn signature generated successfully:`);
  console.log(`  R: ${signature.r}`);
  console.log(`  S: ${signature.s}`);

  assert.ok(signature.r.startsWith("0x"));
  assert.strictEqual(signature.r.length, 66);
  assert.ok(signature.s.startsWith("0x"));
  assert.strictEqual(signature.s.length, 66);

  console.log("\nAll mock signers tests passed successfully! [PASS]");
}

testSigners();
