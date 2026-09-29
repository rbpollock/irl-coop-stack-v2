import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { Contract, JsonRpcProvider, Wallet } from "ethers";

import { verifyRelay, type G16Proof, type RelayParams } from "../src/verify";
import { submitSpend, encodeProof } from "../src/submit";

/**
 * The FULL loop, proven against real ceremony artifacts and the LIVE local chain:
 *
 *   1. read the REAL proof + public signals (ceremony artifacts)
 *   2. verifyRelay must pass (off-chain gate, real snark pairing)
 *   3. submitSpend drives pool.spend(...) on the deployed local ShieldedPool
 *   4. assert: nullifier is sealed + pool root moved to the committed newRoot
 *
 * Requires: hardhat node on 127.0.0.1:8545 with a deployed ShieldedPool
 * (run `npx hardhat run scripts/deploy_shield.ts` first), and the ceremony
 * artifacts in /mnt/storage/zk/keys.
 */

const HOST = "127.0.0.1";
const ZK = process.env.ZK_KEY_DIR ? path.resolve(process.env.ZK_KEY_DIR) : "/mnt/storage/zk/keys";
// When run from apps/treasury-relayer, the pool deploy address is derived by
// reading from the deploy output env (set by the caller). Fall back to a
// deterministic hardhat-account 0 private key for the local chain.
const RPC = process.env.RPC_URL ?? `http://${HOST}:8545`;
const POOL = process.env.POOL_ADDRESS ?? "";
const PK = process.env.HH_KEY ?? "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"; // hardhat#0
const AMOUNT_OUT = 1n; // note amount being spent (the pool carries it on the event)
const NEW_ROOT = 0x1234567890abcdefn; // a relayer-computed Poseidon root (committed on spend)

async function main() {
  // load the real artifacts
  const vkPath = path.join(ZK, "spend_vk.json");
  const pubPath = path.join(ZK, "public.json");
  const profPath = path.join(ZK, "proof.json");
  assert.ok(fs.existsSync(vkPath) && fs.existsSync(pubPath) && fs.existsSync(profPath), "ceremony artifacts missing — run the ceremony first");

  const vk = JSON.parse(fs.readFileSync(vkPath, "utf8"));
  const pub = JSON.parse(fs.readFileSync(pubPath, "utf8")) as string[]; // [outputCommitment, root, nullifierHash]
  const proof = JSON.parse(fs.readFileSync(profPath, "utf8")) as G16Proof;
  const [outputCommitment, root, inputNullifier] = pub;

  // ---- 1. off-chain gate
  const params: RelayParams = { root, outputCommitment, inputNullifier, proof };
  const r = await verifyRelay(vk, params);
  assert.ok(r.ok, `off-chain verify failed: ${r.reason}`);

  // ---- ensure a pool is deployed; use POOL env or deploy fresh
  let poolAddress = POOL;
  if (!poolAddress) {
    const out = execSync("cd ../../contracts && npx hardhat run scripts/deploy_shield.ts --network localhost 2>/dev/null | grep ShieldedPool", { encoding: "utf8" });
    poolAddress = out.trim().split(/\s+/).pop()!;
  }
  assert.ok(poolAddress, "no pool address");

  // ---- 3. submit the spend on the LIVE chain
  const res = await submitSpend({
    rpcUrl: RPC,
    poolAddress,
    signerPk: PK,
    inputNullifier,
    outputCommitment,
    amountOut: AMOUNT_OUT,
    newRoot: NEW_ROOT,
    uint256ProofHex: encodeProof(proof),
  });

  // ---- 4. assertions: sealed + root adopted
  assert.equal(res.sealed, true, "nullifier should be sealed after spend");
  assert.equal(res.root, NEW_ROOT, "pool root should adopt the committed newRoot");

  console.log(`\u2713 FULL LOOP: verified \u2192 submitted \u2192 sealed (tx ${res.txHash})`);
  console.log(`  pool        ${poolAddress}`);
  console.log(`  input null  ${inputNullifier.slice(0, 16)}\u2026`);
  console.log(`  outputComm  ${outputCommitment.slice(0, 16)}\u2026`);
  console.log(`  newRoot     ${NEW_ROOT}`);

  // also confirm the contract helper: spent() is true
  const provider = new JsonRpcProvider(RPC);
  const pool = new Contract(poolAddress, ["function spent(bytes32) view returns (bool)"], provider);
  const inHex = `0x${BigInt(inputNullifier).toString(16).padStart(64, "0")}`;
  assert.equal(await pool.spent(inHex), true, "pool.spent should report the note spent");
}

main().catch((e) => { console.error(e); process.exit(1); });