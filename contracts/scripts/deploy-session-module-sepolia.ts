import { ethers } from "hardhat";
import { deploySafeSuite, createGroupSafe, execSafeTx } from "../scripts/safe-deploy-lib";

const SENTINEL_MODULES = "0x0000000000000000000000000000000000000001";

async function main() {
  const [member] = await ethers.getSigners();
  const bot = ethers.Wallet.createRandom().connect(ethers.provider);
  const attacker = ethers.Wallet.createRandom().connect(ethers.provider);
  console.log("deployer:", member.address);
  console.log("session bot:", bot.address);
  console.log("attacker:", attacker.address);
  // Fund bot + attacker with a tiny bit of Sepolia ETH so they can send tx
  await (await member.sendTransaction({ to: bot.address, value: ethers.parseEther("0.00005") })).wait();
  await (await member.sendTransaction({ to: attacker.address, value: ethers.parseEther("0.00005") })).wait();
  console.log("funded bot & attacker");

  // 1️⃣ Deploy Safe suite + create a 1-of-2 group Safe (member + coMember)
  const suite = await deploySafeSuite();
  const coMember = ethers.Wallet.createRandom().connect(ethers.provider);
  const safe = await createGroupSafe(suite, [member.address, coMember.address], 1);
  const safeAddr = await safe.getAddress();
  console.log("group Safe:", safeAddr);

  // 2️⃣ Deposit some Sepolia ETH into the Safe
  const fundTx = await member.sendTransaction({ to: safeAddr, value: ethers.parseEther("0.0001") });
  await fundTx.wait();
  console.log("funded Safe with 0.0001 Sepolia ETH");

  // 3️⃣ Deploy the hardened SessionKeyModule (B-12), bound to this Safe
  const Module = await ethers.getContractFactory("SessionKeyModule");
  const module = await Module.deploy(safeAddr);
  await module.waitForDeployment();
  const moduleAddr = await module.getAddress();
  console.log("SessionKeyModule deployed:", moduleAddr);

  // 4️⃣ Enable the module on the Safe (governance — Safe owner tx)
  const enableData = safe.interface.encodeFunctionData("enableModule", [moduleAddr]);
  await execSafeTx(safe, [member], { to: safeAddr, data: enableData });
  console.log("module enabled on Safe");
  console.log("  isModuleEnabled:", await safe.isModuleEnabled(moduleAddr));

  // 5️⃣ Bind the session key (bot) with a daily budget + 1-hour expiry (governance tx)
  const validUntil = BigInt(Math.floor(Date.now() / 1000) + 3600);
  const dailyLimit = ethers.parseEther("10");
  const bindData = module.interface.encodeFunctionData("enableSessionKey", [bot.address, dailyLimit, validUntil]);
  await execSafeTx(safe, [member], { to: moduleAddr, data: bindData });
  const cfg = await module.config();
  console.log("session key bound:", cfg.sessionKey, "budget:", cfg.dailyLimit.toString(), "expires:", cfg.validUntil.toString());

  // 6️⃣ Try to spend BEFORE arming the allow-list → MUST revert
  try {
    await module.connect(bot).executeSpend(member.address, ethers.parseEther("0.001"), "0x", 0);
    console.error("❌ FAIL: spend succeeded before arming allow-list");
    process.exitCode = 1;
    return;
  } catch (e: any) {
    const data = (e.data || "").toLowerCase();
    if (data.includes("9d24f5f9") || data.includes("5c54305e") || e.message?.includes("reverted")) {
      console.log("✅ spend correctly DENIED before arm (default-deny)");
    } else {
      console.error("❌ FAIL: unexpected revert:", e.message, e.data);
      process.exitCode = 1;
      return;
    }
  }

  // 7️⃣ Arm the allow-list + whitelist the member address for native transfers
  const armData = module.interface.encodeFunctionData("setListEnabled", [true]);
  await execSafeTx(safe, [member], { to: moduleAddr, data: armData });

  const authData = module.interface.encodeFunctionData("authorize", [member.address, "0x00000000", true]);
  await execSafeTx(safe, [member], { to: moduleAddr, data: authData });
  console.log("allow-list armed and member whitelisted");

  // 8️⃣ Bot spends within budget → must succeed
  const beforeBal = await ethers.provider.getBalance(safeAddr);
  const spendAmount = ethers.parseEther("0.0005");
  const spendTx = await module.connect(bot).executeSpend(member.address, spendAmount, "0x", 0);
  await spendTx.wait();
  const afterBal = await ethers.provider.getBalance(safeAddr);
  console.log("✅ bot spend succeeded; Safe lost", (beforeBal - afterBal).toString(), "wei");

  // 9️⃣ Bot tries delegatecall → MUST revert (BadOperation)
  try {
    await module.connect(bot).executeSpend(member.address, 0, "0x12345678", 1);
    console.error("❌ FAIL: delegatecall was accepted");
    process.exitCode = 1;
    return;
  } catch (e: any) {
    const data = (e.data || "").toLowerCase();
    if (data.includes("1c3a0f27") || data.includes("9d24f5f9") || e.message?.includes("reverted")) {
      console.log("✅ delegatecall correctly refused");
    } else {
      console.error("❌ FAIL: unexpected revert:", e.message, e.data);
      process.exitCode = 1;
      return;
    }
  }

  // 🔟 Attacker (not the session key) tries → MUST revert
  try {
    await module.connect(attacker).executeSpend(member.address, ethers.parseEther("0.0001"), "0x", 0);
    console.error("❌ FAIL: attacker spend succeeded");
    process.exitCode = 1;
    return;
  } catch (e: any) {
    const data = (e.data || "").toLowerCase();
    if (data.includes("5c54305e") || data.includes("9d24f5f9") || e.message?.includes("reverted")) {
      console.log("✅ attacker correctly refused (wrong key)");
    } else {
      console.error("❌ FAIL: unexpected revert:", e.message, e.data);
      process.exitCode = 1;
      return;
    }
  }

  console.log("\n🟢 All B-12 Sepolia smoke checks passed");
  console.log("   module:", moduleAddr);
  console.log("   safe:   ", safeAddr);
  console.log("   Write these into networks.json for the next step.");
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
