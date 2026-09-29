import { ethers } from "hardhat";

/**
 * Deploy the shielded-treasury local-chain fixture: MockUsdc + ShieldedPool
 * (P1 seam, NoopVerifier). Used by the relayer-submit smoke test to drive a
 * real spend against a contract that actually exists.
 *
 * Run:  npx hardhat run scripts/deploy_shield.ts
 */
async function main() {
  const [deployer] = await ethers.getSigners();

  // Mock USDC (6-decimals test token) + mint the deployer a wallet.
  const Usdc = await ethers.getContractFactory("MockUsdc");
  const usdc = await Usdc.deploy();
  await usdc.waitForDeployment();
  await usdc.mint(deployer.address, ethers.parseUnits("1000000", 6));

  // The no-op (P1) verifier — reads any proof. The crypto is checked OFF-chain
  // by the relayer (plan §10); the pool seals the nullifier + root regardless.
  const Noop = await ethers.getContractFactory("NoopVerifier");
  const noop = await Noop.deploy();
  await noop.waitForDeployment();

  const Pool = await ethers.getContractFactory("ShieldedPool");
  const pool = await Pool.deploy(await usdc.getAddress(), await noop.getAddress());
  await pool.waitForDeployment();

  console.log(`USDC         ${await usdc.getAddress()}`);
  console.log(`NoopVerifier ${await noop.getAddress()}`);
  console.log(`ShieldedPool ${await pool.getAddress()}`);
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});