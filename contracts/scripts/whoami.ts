import { ethers } from "hardhat";

/** Who is paying for this deploy, and can they? Prints the address (never the key). */
async function main() {
  const signers = await ethers.getSigners();
  if (!signers.length) {
    console.log("NO SIGNER — set PRIVATE_KEY (the wrapper reads it from a 0600 file)");
    process.exitCode = 1;
    return;
  }
  const [s] = signers;
  const bal = await ethers.provider.getBalance(s.address);
  console.log(`deployer: ${s.address}`);
  console.log(`balance : ${bal.toString()} wei`);
  if (bal === 0n) {
    console.log("REFUSING: that account has no gas money — fund it from a faucet first");
    process.exitCode = 1;
  }
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
