import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { verifyRelay, type G16Proof } from "../src/verify";

/**
 * The relayer's crypto gate against the REAL ceremony artifacts.
 *
 * Fixtures (written by the ceremony rebuild + the P2-gate proof, in
 * /mnt/storage/zk/keys/):
 *   - spend_vk.json      the verification key (nPublic=3)
 *   - public.json        the REAL spend's public signals [outputCommitment, root, nullifier]
 *   - proof.json         the REAL spend's Groth16 proof (verified OK by snarkjs earlier)
 *
 * A genuine relay passes; a forged proof / swapped anchor is rejected. This is
 * the honesty check that validation, not just ceremony, holds up end to end.
 */
const KEYS = process.env.ZK_KEY_DIR
  ? path.resolve(process.env.ZK_KEY_DIR)
  : "/mnt/storage/zk/keys";

const vk = JSON.parse(fs.readFileSync(path.join(KEYS, "spend_vk.json"), "utf8"));
const pub = JSON.parse(fs.readFileSync(path.join(KEYS, "public.json"), "utf8"));
const proof = JSON.parse(fs.readFileSync(path.join(KEYS, "proof.json"), "utf8")) as G16Proof;

// public.json order: [outputCommitment, root, nullifierHash]
const [outputCommitment, root, inputNullifier] = pub.map(String);

test("a genuine ceremony proof verifies through the relayer", async () => {
  const r = await verifyRelay(vk, { outputCommitment, root, inputNullifier, proof });
  assert.equal(r.ok, true, `expected accept, got: ${r.reason}`);
});

test("a forged proof is rejected", async () => {
  const forged: G16Proof = {
    ...proof,
    pi_a: [proof.pi_a[0], "0"], // tamper with the a-coordinate
  };
  const r = await verifyRelay(vk, { outputCommitment, root, inputNullifier, proof: forged });
  assert.equal(r.ok, false);
});

test("a valid proof with swapped/flipped anchors is rejected (graft check)", async () => {
  // Take the valid proof but claim a DIFFERENT root/nullifier: the anchors must
  // equal the proof's own public signals, so this must be rejected.
  const badNullifier = (BigInt(inputNullifier) + 1n).toString();
  const r = await verifyRelay(vk, {
    outputCommitment,
    root,
    inputNullifier: badNullifier,
    proof,
  });
  assert.equal(r.ok, false);
});

function test(name: string, fn: () => Promise<void>) {
  void fn().then(
    () => console.log(`\u2713 ${name}`),
    (e) => { console.error(`\u2717 ${name}\n  ${(e as Error).message}`); process.exitCode = 1; },
  );
}