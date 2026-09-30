import { ethers } from "hardhat";
import { deploySafeSuite, createGroupSafe } from "./safe-deploy-lib";

// The identity coop-api's SAFE_BACKEND_SIGNER_KEY points at (hardhat node
// Account #0), so this replicates POST /api/safe/sovereign's signer exactly.
const BACKEND_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";

/**
 * Verified to mirror the new coop-api /api/safe/sovereign route's signing path:
 * a backend EOA (hardhat #0, the dev backend key) owns a 1-of-1 Safe, then we
 * execute ONE Safe execTransaction whose inner call is
 * swapOwner(SENTINEL_OWNERS, backend, passkeyOwner), signing the EIP-712
 * safeTxHash with the backend EOA (r||s||v 65-byte Safe owner sig) — exactly as
 * POST /api/safe/sovereign does. Asserts the owner set flips to the passkey.
 */
async function main() {
  const provider = ethers.provider;
  const backendSigner = new ethers.Wallet(BACKEND_KEY, provider);
  const backendAddr = backendSigner.address;
  const SENTINEL = "0x0000000000000000000000000000000000000001";

  // 1. Local Safe layer + a stub-backed PasskeyOwner (the EIP-1271 owner).
  const suite = await deploySafeSuite();
  const safe = await createGroupSafe(suite, [backendSigner.address], 1);
  const safeAddr = await safe.getAddress();
  const stub = await (await ethers.getContractFactory("StubVerifier")).deploy();
  await stub.waitForDeployment();
  // PasskeyOwner constructor = (x, y, verifier) — use an arbitrary P-256 point; the
  // route only cares that the Safe's ownership transfers, not that it ever signs.
  const passkeyOwner = await (await ethers.getContractFactory("PasskeyOwner")).deploy(
    1n, 2n, await stub.getAddress()
  );
  await passkeyOwner.waitForDeployment();
  const passkeyAddr = await passkeyOwner.getAddress();

  console.log("safe:", safeAddr, "owner[0]:", (await safe.getOwners())[0]);

  // 2. Build the inner swapOwner and sign it as Safe's sole EOA OWNER.
  const inner = safe.interface.encodeFunctionData("swapOwner", [
    SENTINEL, backendAddr, passkeyAddr,
  ]);
  const oper = 0, safeTxGas = 0n, baseGas = 0n, gasPrice = 0n;
  const gasToken = ethers.ZeroAddress, refundReceiver = ethers.ZeroAddress;
  const nonce = await safe.nonce();
  const safeTxHash = await safe.getTransactionHash(
    safeAddr, 0n, inner, oper, safeTxGas, baseGas, gasPrice, gasToken, refundReceiver, nonce
  );

  const sig = backendSigner.signingKey.sign(ethers.getBytes(safeTxHash));
  const backendSig = ethers.concat([
    ethers.zeroPadValue(sig.r, 32),
    ethers.zeroPadValue(sig.s, 32),
    ethers.toBeHex(sig.v),
  ]);

  // dry-run first (the route's staticCall)
  await safe.execTransaction.staticCall(
    safeAddr, 0n, inner, oper, safeTxGas, baseGas, gasPrice, gasToken, refundReceiver, backendSig
  );
  console.log("dry-run OK (would not revert)");

  const receipt = await (await safe.execTransaction(
    safeAddr, 0n, inner, oper, safeTxGas, baseGas, gasPrice, gasToken, refundReceiver, backendSig
  )).wait();

  const after = await safe.getOwners();
  console.log("tx:", receipt!.hash, "| owners after:", after);
  if (after.length !== 1 || after[0].toLowerCase() !== passkeyAddr.toLowerCase()) {
    throw new Error("FAIL: owner set did not become the passkey owner");
  }
  console.log("PASS: probe the backend renounced; Safe now owned by", passkeyAddr);
}

main().catch((e) => { console.error(e); process.exit(1); });