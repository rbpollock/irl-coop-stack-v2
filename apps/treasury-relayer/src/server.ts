import fs from "node:fs";
import path from "node:path";
import Fastify from "fastify";

// The treasury relayer — OFF-CHAIN proof gate for the shielded pool.
//
// It is a standalone internal app (mirror of peer_xyz_payments' rail shape):
//  - coop-api (the member-facing API) never holds the proving key or the ceremony
//    verification key; the relayer is the only process that runs the Groth16
//    pairing check.
//  - swapping / hardening the proof stack is isolated to this one process.
//
// RELAYER MODEL (plan §8/¥10): a permission-permissive relayer verifies the proof
// off-chain and submits a SEAL to the pool — the pool only records the nullifier +
// the committed Poseidon root. This service is that relayer; it intentionally has
// NO pool write just yet (the pool is on a local hardhat for P1), so for now it
// VERIFIES and emits the relay decision. The pool-wire step is gated on a deploy.

import { verifyRelay, type RelayParams, type RelayOutcome } from "./verify";

const PORT = Number(process.env.RELAYER_PORT ?? 3020);
const KEY_PATH = process.env.ZK_KEY_DIR
  ? path.join(process.env.ZK_KEY_DIR, "spend_vk.json")
  : "/mnt/storage/zk/keys/spend_vk.json";

const fastify = Fastify({ logger: false });

// Load the verification key once at startup. A missing key means the relayer is
// not provisioned — fail loudly; the cooper has not run the ceremony.
let vk: unknown;
try {
  vk = JSON.parse(fs.readFileSync(KEY_PATH, "utf8"));
} catch (e) {
  console.error(`[treasury-relayer] cannot load spend_vk.json at ${KEY_PATH}:`, (e as Error).message);
  process.exit(1);
}

fastify.get("/health", async () => ({
  ok: true,
  vk_loaded: !!vk,
  vk_path: KEY_PATH,
}));

// The proof-gate endpoint. Anyone may call it (it is permissionless-by-design):
// a forged or malformed proof returns 4xx; only a real spend past the pairing
// check returns the relay payload. The pool's own nullifier+root set is the
// second / on-chain gate.
fastify.post("/relay", async (request, reply) => {
  const body = (request.body ?? {}) as Record<string, unknown>;
  const root = body.root as string;
  const outputCommitment = body.outputCommitment as string;
  const inputNullifier = body.inputNullifier as string;
  const proof = body.proof as RelayParams["proof"];

  if (!root || !outputCommitment || !inputNullifier || !proof) {
    return reply.code(400).send({ ok: false, error: "root, outputCommitment, inputNullifier and proof are required" });
  }
  // Validate the proof SHAPE before calling the (expensive, strict) verifier:
  // a malformed proof is a 400, not a 500. The snarkjs Groth16 proof wire form
  // is [..., 1] per group: pi_a[3], pi_b[3] (each of its 2 rows a [x,y]),
  // pi_c[3].
  const pA = Array.isArray(proof.pi_a) && proof.pi_a.length > 2;
  const pB = Array.isArray(proof.pi_b) && proof.pi_b.length > 2 &&
    Array.isArray(proof.pi_b[0]) && proof.pi_b[0].length > 1 &&
    Array.isArray(proof.pi_b[1]) && proof.pi_b[1].length > 1;
  const pC = Array.isArray(proof.pi_c) && proof.pi_c.length > 2;
  if (!pA || !pB || !pC) {
    return reply.code(400).send({ ok: false, error: "malformed proof (expected snarkjs wire form: pi_a*, pi_b[2][2], pi_c*)" });
  }

  const p: RelayParams = { root, outputCommitment, inputNullifier, proof };
  let r: RelayOutcome;
  try {
    r = await verifyRelay(vk, p);
  } catch (err) {
    // Structural failure in the verifier (not a rejected proof) — surface as 400
    // so a bad proof is never treated as server trouble.
    return reply.code(400).send({ ok: false, error: `proof rejected: ${(err as Error).message}` });
  }
  if (!r.ok) {
    return reply.code(400).send({ ok: false, error: r.reason ?? "proof rejected" });
  }

  // The relay is valid. What cooper/relay does with it next (call the pool's
  // spend(nullifier, outputCommitment, amount, newRoot, proof)) is wired later —
  // the pool is on the local hardhat chain; this is the crypto gate only.
  return reply.send({
    ok: true,
    relay: {
      root,
      outputCommitment,
      inputNullifier,
    },
    note: "proof verified off-chain; ready to submit to the pool seam",
  });
});

fastify.listen({ port: PORT, host: "0.0.0.0" })
  .then(() => console.log(`[treasury-relayer] listening on :${PORT}`))
  .catch((err) => {
    console.error("[treasury-relayer] failed to start:", err);
    process.exit(1);
  });