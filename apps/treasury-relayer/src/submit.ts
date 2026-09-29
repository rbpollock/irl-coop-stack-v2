import { AbiCoder, Contract, JsonRpcProvider, Wallet } from "ethers";

import type { G16Proof } from "./verify";

/**
 * The pool-submit seam — the last hop of the off-chain relay model.
 *
 * A valid (already off-chain VERIFIED) relay drives the pool's spend:
 *   pool.spend(inputNullifier, outputCommitment, amountOut, newRoot, proof)
 * The pool then: seals the inputNullifier, adopts newRoot as the Poseidon root.
 *
 * Payload: addresses + RPC come from the env; the proof was already accepted by
 * the relayer's /relay gate before this is called (the gate is the crypto
 * authoritative; this seam is the on-chain commit).
 *
 * The pool ABI (ShieldedPool).
 */
const POOL_ABI = [
  "function spend(bytes32 inputNullifier, bytes32 outputCommitment, uint256 amountOut, uint256 newRoot, bytes calldata proof) external",
  "function spent(bytes32 n) external view returns (bool)",
  "function getRoot() external view returns (uint256)",
];

export interface SubmitArgs {
  rpcUrl: string;
  poolAddress: string;
  signerPk: string; // the local-cadence dev account
  inputNullifier: string; // decimal string (the value from public.json; pool wants bytes32)
  outputCommitment: string; // decimal string
  amountOut: bigint;
  newRoot: bigint;
  uint256ProofHex: string; // the proof pre-encoded as ABI bytes
}

export interface SubmitResult {
  txHash: string;
  sealed: boolean;
  root: bigint;
}

export async function submitSpend(args: SubmitArgs): Promise<SubmitResult> {
  const provider = new JsonRpcProvider(args.rpcUrl);
  const signer = new Wallet(args.signerPk, provider);
  const pool = new Contract(args.poolAddress, POOL_ABI, signer);

  // decimal (public.json) -> padded bytes32 hex for the pool's bytes32 args.
  const inputNullifier = toBeHex(args.inputNullifier);
  const outputComm = toBeHex(args.outputCommitment);
  const tx = await pool.spend(
    inputNullifier,
    outputComm,
    args.amountOut,
    args.newRoot,
    args.uint256ProofHex,
  );
  const rc = await tx.wait();
  if (!rc || rc.status !== 1) throw new Error("pool spend reverted");

  const sealed = await pool.spent(inputNullifier);
  const root = BigInt(await pool.getRoot());
  return { txHash: tx.hash, sealed, root };
}

/** decimal string (bigint) -> 32-byte 0x-padded hex, as the contract bytes32. */
function toBeHex(dec: string): string {
  const n = BigInt(dec);
  const hex = n.toString(16).padStart(64, "0");
  return `0x${hex}`;
}

/** Pack a Groth16 proof (snarkjs) into the pool's `bytes` calldata (A, B, C). */
export function encodeProof(p: G16Proof): string {
  const a = [p.pi_a[0], p.pi_a[1]];
  const b = [[p.pi_b[0][0], p.pi_b[0][1]], [p.pi_b[1][0], p.pi_b[1][1]]];
  const c = [p.pi_c[0], p.pi_c[1]];
  return new AbiCoder().encode(["uint256[2]", "uint256[2][2]", "uint256[2]"], [a, b, c]);
}