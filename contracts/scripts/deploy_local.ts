import { ethers } from "hardhat";

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying contracts with account:", deployer.address);

  // 1. Deploy Safe Singleton
  const Safe = await ethers.getContractFactory("@safe-global/safe-contracts/contracts/Safe.sol:Safe");
  const safeSingleton = await Safe.deploy();
  await safeSingleton.waitForDeployment();
  console.log("Safe Singleton deployed to:", await safeSingleton.getAddress());

  // 2. Deploy Safe Proxy Factory
  const SafeProxyFactory = await ethers.getContractFactory("@safe-global/safe-contracts/contracts/proxies/SafeProxyFactory.sol:SafeProxyFactory");
  const proxyFactory = await SafeProxyFactory.deploy();
  await proxyFactory.waitForDeployment();
  console.log("SafeProxyFactory deployed to:", await proxyFactory.getAddress());

  // 3. Deploy IRL Coop Modules
  const PasskeyValidator = await ethers.getContractFactory("PasskeyValidator");
  const passkeyValidator = await PasskeyValidator.deploy();
  await passkeyValidator.waitForDeployment();
  console.log("PasskeyValidator deployed to:", await passkeyValidator.getAddress());

  const SovereignEvolutionModule = await ethers.getContractFactory("SovereignEvolutionModule");
  const evolutionModule = await SovereignEvolutionModule.deploy();
  await evolutionModule.waitForDeployment();
  console.log("SovereignEvolutionModule deployed to:", await evolutionModule.getAddress());

  const SessionKeyModule = await ethers.getContractFactory("SessionKeyModule");
  const sessionKeyModule = await SessionKeyModule.deploy();
  await sessionKeyModule.waitForDeployment();
  console.log("SessionKeyModule deployed to:", await sessionKeyModule.getAddress());
  
  // 4. Print Summary for frontend .env configuration
  console.log("\n=============================================");
  console.log("Add these to your apps/web/.env.local:");
  console.log("NEXT_PUBLIC_SAFE_SINGLETON_ADDRESS=" + await safeSingleton.getAddress());
  console.log("NEXT_PUBLIC_SAFE_PROXY_FACTORY_ADDRESS=" + await proxyFactory.getAddress());
  console.log("NEXT_PUBLIC_PASSKEY_VALIDATOR_ADDRESS=" + await passkeyValidator.getAddress());
  console.log("NEXT_PUBLIC_EVOLUTION_MODULE_ADDRESS=" + await evolutionModule.getAddress());
  console.log("NEXT_PUBLIC_SESSION_KEY_MODULE_ADDRESS=" + await sessionKeyModule.getAddress());
  console.log("=============================================\n");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
