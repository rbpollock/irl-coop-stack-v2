import { ethers } from "hardhat";
import { execSafeTx } from "./safe-deploy-lib";

const SESSION_ABI = [
  "function config() view returns (tuple(address sessionKey,uint256 dailyLimit,uint256 spentToday,uint256 lastResetDay,uint256 validUntil))",
  "function SAFE() view returns (address)",
  "function listEnabled() view returns (bool)",
  "function whitelistedTargets(address) view returns (bool)",
  "function enableSessionKey(address,uint256,uint256)",
  "function clearSessionKey()",
  "function setListEnabled(bool)",
  "function authorize(address,bytes4,bool)",
  "function executeSpend(address,uint256,bytes,uint8) returns (bool)",
  "function getRemainingLimit(address) view returns (uint256)",
];

const SAFE_ABI = [
  "function getOwners() view returns (address[])",
  "function isModuleEnabled(address) view returns (bool)",
  "function nonce() view returns (uint256)",
  "function execTransaction(address to, uint256 value, bytes data, uint8 operation, uint256 safeTxGas, uint256 baseGas, uint256 gasPrice, address gasToken, address refundReceiver, bytes signatures) payable returns (bool)",
];

const MODULE = "0x3e6F19ffBdFE2dbB4620451bA6C5c79e6B45120B";
const SAFE = "0xb8360999bF11317aA826de551f387B3Ee7f72A6E";

async function main() {
  const [member] = await ethers.getSigners();
  console.log("deployer/owner:", member.address);
  console.log("module:", MODULE);
  console.log("safe:  ", SAFE);

  const safe = new ethers.Contract(SAFE, SAFE_ABI, member);
  const module = new ethers.Contract(MODULE, SESSION_ABI, member);

  console.log("owners:", await safe.getOwners());
  console.log("module enabled?", await safe.isModuleEnabled(MODULE));

  const oldCfg = await module.config();
  console.log("old session:", oldCfg.sessionKey, "budget:", oldCfg.dailyLimit.toString());

  // 1️⃣ Clear the lost session key and rebind to deployer
  await execSafeTx(safe, [member], {
    to: MODULE,
    data: module.interface.encodeFunctionData("clearSessionKey", []),
  });
  console.log("cleared old session key");

  const validUntil = BigInt(Math.floor(Date.now() / 1000) + 3600);
  const dailyLimit = ethers.parseEther("10");
  await execSafeTx(safe, [member], {
    to: MODULE,
    data: module.interface.encodeFunctionData("enableSessionKey", [member.address, dailyLimit, validUntil]),
  });
  const cfg = await module.config();
  console.log("new session:", cfg.sessionKey, "budget:", cfg.dailyLimit.toString(), "expires:", cfg.validUntil.toString());

  // 2️⃣ Ensure list is armed and this target is whitelisted
  const listOn = await module.listEnabled();
  if (!listOn) {
    await execSafeTx(safe, [member], {
      to: MODULE,
      data: module.interface.encodeFunctionData("setListEnabled", [true]),
    });
    console.log("armed list");
  } else {
    console.log("list already armed");
  }
  const wl = await module.whitelistedTargets(member.address);
  if (!wl) {
    await execSafeTx(safe, [member], {
      to: MODULE,
      data: module.interface.encodeFunctionData("authorize", [member.address, "0x00000000", true]),
    });
    console.log("whitelisted deployer target");
  } else {
    console.log("deployer already whitelisted");
  }

  // 3️⃣ Fund the Safe so it can send
  const before = await ethers.provider.getBalance(SAFE);
  if (before < ethers.parseEther("0.0001")) {
    await (await member.sendTransaction({ to: SAFE, value: ethers.parseEther("0.0001") })).wait();
    console.log("refunded Safe");
  }

  // 4️⃣ Execute a spend within budget (deployer IS the session key now)
  const spendAmount = ethers.parseEther("0.00005");
  const spendTx = await module.executeSpend(member.address, spendAmount, "0x", 0);
  await spendTx.wait();
  const after = await ethers.provider.getBalance(SAFE);
  console.log("✅ spend succeeded; Safe lost", (before - after).toString(), "wei");
  console.log("remaining limit:", (await module.getRemainingLimit(SAFE)).toString());

  // 5️⃣ Delegatecall → revert
  try {
    await module.executeSpend(member.address, 0, "0x12345678", 1);
    console.error("❌ FAIL: delegatecall accepted");
    process.exitCode = 1; return;
  } catch (e: any) {
    console.log("✅ delegatecall refused");
  }

  // 6️⃣ Unlisted target → revert
  try {
    await module.executeSpend(ethers.Wallet.createRandom().address, 0, "0x", 0);
    console.error("❌ FAIL: unlisted target accepted");
    process.exitCode = 1; return;
  } catch (e: any) {
    console.log("✅ unlisted target refused");
  }

  // 7️⃣ Over-budget → revert
  try {
    await module.executeSpend(member.address, ethers.parseEther("999"), "0x", 0);
    console.error("❌ FAIL: over-budget accepted");
    process.exitCode = 1; return;
  } catch (e: any) {
    console.log("✅ over-budget refused");
  }

  console.log("\n🟢 B-12 Sepolia smoke: all checks passed on live contract");
}

main().catch((e) => { console.error(e); process.exitCode = 1; });
