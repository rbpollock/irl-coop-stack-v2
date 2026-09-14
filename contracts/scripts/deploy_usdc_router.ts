import { ethers } from "hardhat";

/**
 * Deploy the USDC router on the LOCAL chain and drive the whole flow on-chain:
 *
 *   mint USDC -> transfer it to the router (exactly what a rail's plain `transfer` does)
 *   -> sweep()  -> assert the destination Safe actually received it
 *
 * The Base deployment uses the same contract; only the token address and the destination
 * differ. On Base the token address must be READ FROM THE CHAIN, never typed from memory.
 */
async function main() {
  const [deployer] = await ethers.getSigners();

  // The destination on the dev chain: a REAL provisioned group Safe (from the tree/DB),
  // passed in so this script never invents one.
  const destination = process.env.ROUTER_DESTINATION;
  if (!destination || !ethers.isAddress(destination)) {
    throw new Error("ROUTER_DESTINATION=<address> is required (use a group Safe, not a placeholder)");
  }

  const tokenAddr = process.env.ROUTER_TOKEN;
  let token: any, tokenNote: string;
  if (tokenAddr) {
    token = await ethers.getContractAt("MockUsdc", tokenAddr);
    tokenNote = `existing token ${tokenAddr}`;
  } else {
    // local only: a USDC-shaped stand-in. On Base this MUST be the real USDC address, read
    // from the chain — hardcoding a token address from memory is how funds go nowhere.
    const T = await ethers.getContractFactory("MockUsdc");
    token = await T.deploy();
    const tokenAddrNow = await token.getAddress();
    await token.waitForDeployment();
    tokenNote = `deployed MockUsdc (LOCAL ONLY) at ${tokenAddrNow}`;
  }

  const R = await ethers.getContractFactory("CoopUsdcRouter");
  const router = await R.deploy(await token.getAddress(), destination);
  const routerAddr = await router.getAddress();
  await router.waitForDeployment();

  console.log("token      :", tokenNote);
  console.log("router     :", routerAddr);
  console.log("destination:", destination, "(immutable, set in the constructor)");
  console.log("token()    :", await router.token());
  console.log("destination():", await router.destination());

  // --- drive it on-chain, the way a rail would ---
  const ONE = 1_000_000n;
  if (!tokenAddr) await token.mint(deployer.address, 10n * ONE);
  const destBefore = await token.balanceOf(destination);
  await (await token.transfer(routerAddr, 5n * ONE)).wait();
  const held = await token.balanceOf(routerAddr);
  console.log("\nafter the rail's plain transfer  -> router holds:", held.toString(), "(no code ran: ERC-20 has no hook)");

  await (await router.sweep()).wait();
  const destAfter = await token.balanceOf(destination);
  console.log("after sweep()                    -> router holds:", (await token.balanceOf(routerAddr)).toString());
  console.log("                                    destination +", (destAfter - destBefore).toString(), "(in 6dp units)");

  if (destAfter - destBefore !== 5n * ONE) throw new Error("destination did not receive the swept amount");
  if ((await token.balanceOf(routerAddr)).toString() !== "0") throw new Error("router still holds funds after sweep");
  console.log("\nOK: the rail's destination can only ever forward to the immutable one.");
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
