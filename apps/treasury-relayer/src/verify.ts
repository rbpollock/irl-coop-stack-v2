import * as snarkjs from "snarkjs";

/**
 * The treasury relayer's crypto gate — the ONLY way a spend reaches the pool.
 *
 * Operating model (plan §8 / §10): a permissionless relayer checks the Groth16
 * proof OFF-CHAIN; the pool only seals the nullifier + adopts the committed
 * Poseidon root. This module IS that gate.
 *
 * It verifies all and only these:
 *   1. the Groth16 proof is valid against the ceremony's spend verification key;
 *   2. the proof's PUBLIC SIGNALS equal the caller's anchors, in the circuit's
 *      EXACT order [outputCommitment, root, nullifierHash]:
 *         public[0] == outputCommitment
 *         public[1] == root
 *         public[2] == inputNullifier
 *
 * (snarkjs ships no TS types; the proof/signals stay as loose structural types
 * and are validated against the verification key at runtime by snarkjs.groth16.)
 */

/** Groth16 proof: a,b,c over the BN254 scalar field (snarkjs shape). */
export type G16Proof = {
  pi_a: string[];
  pi_b: string[];
  pi_c: string[];
  protocol: string;
  curve: string;
};

/** The caller's claimed anchors — cross-checked against the proof's public signals. */
export interface RelayParams {
  /** The merkle root the spent note lived under (== the pool's current root). */
  root: string;
  /** The fresh note commitment (public signal[0]). */
  outputCommitment: string;
  /** The spent note's nullifier (public signal[2]). */
  inputNullifier: string;
  proof: G16Proof;
}

export interface RelayOutcome {
  ok: boolean;
  reason?: string;
}

/** snarkjs's groth16.verify — untyped at the call site. */
type VerifyFn = (
  vk: unknown,
  publicSignals: string[],
  proof: unknown,
) => Promise<boolean>;

export async function verifyRelay(
  vk: unknown,
  p: RelayParams,
): Promise<RelayOutcome> {
  // public-signal order [outputCommitment, root, inputNullifier] — matches the
  // circuit:  comp main { public [root, nullifierHash] } emits outputs first.
  const publicSignals: string[] = [
    p.outputCommitment,
    p.root,
    p.inputNullifier,
  ];
  const verify = (snarkjs as unknown as { groth16: { verify: VerifyFn } })
    .groth16.verify;
  const ok = await verify(vk, publicSignals, p.proof);
  if (!ok) return { ok: false, reason: "groth16 pairing did not hold" };
  return { ok: true };
}