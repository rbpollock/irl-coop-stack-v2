import { expect } from "chai";
import { ethers } from "hardhat";
import { deploySafeSuite, createGroupSafe, execSafeTx, Operation } from "../scripts/safe-deploy-lib";

/**
 * SessionKeyModule wired to a REAL group Safe (Safe 1.4.1 module pattern):
 *
 *  - the group Safe is owned by [member, coMember] threshold 1; the SESSION key
 *    is deliberately NOT an owner.
 *  - governance (a Safe tx) enables the module ON the Safe and enables the
 *    session key with a daily budget — enableSessionKey is callable ONLY BY the
 *    Safe, so the bot can never widen its own limit.
 *  - the bot then drives the Safe by calling module.executeSpend → the module
 *    calls Safe.execTransactionFromModule, which Safe permits ONLY while the
 *    module is enabled (GS104).
 *  - bounded: native spend counts `value`; ERC-20 spend counts declared
 *    `amountIn`. Disabling the module severs authority instantly.
 */

const SENTINEL_MODULES = "0x0000000000000000000000000000000000000001";

describe("SessionKeyModule vs a live group Safe", () => {
  async function fixture() {
    const [member, coMember, bot, target] = await ethers.getSigners();
    const suite = await deploySafeSuite();
    const safe = await createGroupSafe(suite, [member.address, coMember.address], 1);
    const Module = await ethers.getContractFactory("SessionKeyModule");
    const module = await Module.deploy(await safe.getAddress());
    await module.waitForDeployment();
    return {
      member, coMember, bot, target,
      safe,
      module,
      moduleAddr: await module.getAddress(),
      safeAddr: await safe.getAddress(),
    };
  }

  /** One governance tx set: enable the module on the Safe + bind the bot budget. */
  async function setupSession(f: Awaited<ReturnType<typeof fixture>>, dailyLimit: bigint) {
    const enableData = f.safe.interface.encodeFunctionData("enableModule", [f.moduleAddr]);
    await execSafeTx(f.safe, [f.member], { to: f.safeAddr, data: enableData });
    const setData = f.module.interface.encodeFunctionData("enableSessionKey", [f.bot.address, dailyLimit]);
    await execSafeTx(f.safe, [f.member], { to: f.moduleAddr, data: setData });
  }

  it("the bot gets its budget via the Safe and is NOT an owner", async () => {
    const f = await fixture();
    const daily = ethers.parseEther("500");
    await setupSession(f, daily);

    const cfg = await f.module.config();
    expect(cfg.sessionKey).to.equal(f.bot.address);
    expect(cfg.dailyLimit).to.equal(daily);
    expect(await f.safe.isModuleEnabled(f.moduleAddr)).to.equal(true);
    // the bot holds NO ownership: it cannot raise its own limit, rename owners,
    // or move anything outside the module's budget.
    expect(await f.safe.isOwner(f.bot.address)).to.equal(false);
    expect(await f.module.getRemainingLimit(f.moduleAddr)).to.equal(daily);
  });

  it("rejects binding the session key unless called BY the Safe (bot cannot self-grant)", async () => {
    const f = await fixture();
    await expect(
      f.module.connect(f.bot).enableSessionKey(f.coMember.address, ethers.parseEther("1"))
    ).to.be.revertedWithCustomError(f.module, "NotSafe");
  });

  it("a bot spend within budget EXECUTES the Safe and is bounded (native)", async () => {
    const f = await fixture();
    const daily = ethers.parseEther("100");
    await setupSession(f, daily);

    // Seed the Safe with ETH, then the bot moves 40 to itself via the module.
    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("100") })).wait();

    const before = await ethers.provider.getBalance(f.safeAddr);
    const spend = ethers.parseEther("40");
    const tx = await f.module.connect(f.bot).executeSpend(
      f.bot.address, spend, "0x", Operation.Call, ethers.ZeroAddress, 0n
    );
    await tx.wait();

    const after = await ethers.provider.getBalance(f.safeAddr);
    expect(before - after).to.equal(spend);
    expect(await f.module.getRemainingLimit(f.safeAddr)).to.equal(ethers.parseEther("60"));
  });

  it("a bot spend OVER budget reverts and the Safe is untouched", async () => {
    const f = await fixture();
    const daily = ethers.parseEther("50");
    await setupSession(f, daily);
    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("100") })).wait();

    const before = await ethers.provider.getBalance(f.safeAddr);
    await expect(
      f.module.connect(f.bot).executeSpend(
        f.bot.address, ethers.parseEther("80"), "0x", Operation.Call, ethers.ZeroAddress, 0n
      )
    ).to.be.revertedWithCustomError(f.module, "DailyLimitExceeded");
    expect(await ethers.provider.getBalance(f.safeAddr)).to.equal(before);
  });

  it("disabling the module severs the bot", async () => {
    const f = await fixture();
    const daily = ethers.parseEther("100");
    await setupSession(f, daily);

    // disallow: the Safe disables the module.
    const disableData = f.safe.interface.encodeFunctionData("disableModule", [SENTINEL_MODULES, f.moduleAddr]);
    await execSafeTx(f.safe, [f.member], { to: f.safeAddr, data: disableData });
    expect(await f.safe.isModuleEnabled(f.moduleAddr)).to.equal(false);

    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("10") })).wait();
    await expect(
      f.module.connect(f.bot).executeSpend(
        f.bot.address, ethers.parseEther("5"), "0x", Operation.Call, ethers.ZeroAddress, 0n
      )
    ).to.be.revertedWith("GS104"); // execTransactionFromModule: module no longer enabled
  });

  it("an ERC-20 spend is budgeted by the declared amount (USDC automation)", async () => {
    const f = await fixture();
    const daily = ethers.parseUnits("100", 6); // 100 USDC/day
    await setupSession(f, daily);

    const usdc = await (await ethers.getContractFactory("MockUsdc")).deploy();
    await usdc.waitForDeployment();
    const usdcAddr = await usdc.getAddress();
    const amount = ethers.parseUnits("40", 6);

    // Fund the Safe with USDC, then the bot transfers 40 USDC to itself via the
    // module. The ERC-20 budget is declared as `amountIn` (the module does NOT
    // parse calldata); the bot carries no owner authority.
    await usdc.mint(f.safeAddr, ethers.parseUnits("100", 6));

    const transferData = usdc.interface.encodeFunctionData("transfer", [f.bot.address, amount]);
    const tx = await f.module.connect(f.bot).executeSpend(
      usdcAddr, 0n, transferData, Operation.Call, usdcAddr, amount
    );
    await tx.wait();

    expect(await usdc.balanceOf(f.safeAddr)).to.equal(ethers.parseUnits("60", 6));
    expect(await usdc.balanceOf(f.bot.address)).to.equal(amount);
    expect(await f.module.getRemainingLimit(f.safeAddr)).to.equal(ethers.parseUnits("60", 6));
  });

  it("is default-permissive until the Safe arms the allow-list", async () => {
    const f = await fixture();
    const daily = ethers.parseEther("100");
    await setupSession(f, daily);
    // Off by default — list disabled, no config needed.
    expect(await f.module.listEnabled()).to.equal(false);

    // Any call works (budget-only) while off: spend to an arbitrary target.
    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("50") })).wait();
    await f.module.connect(f.bot).executeSpend(
      f.bot.address, ethers.parseEther("10"), "0x", Operation.Call, ethers.ZeroAddress, 0n
    );
  });

  it("arming the list RESTRICTS the bot to the allow-list (per-target + per-selector)", async () => {
    const f = await fixture();
    const daily = ethers.parseEther("100");
    await setupSession(f, daily);
    const usdc = await (await ethers.getContractFactory("MockUsdc")).deploy();
    const usdcAddr = await usdc.getAddress();

    // Owners arm the list and whitelist ONLY MockUsdc.transfer (not mint).
    await execSafeTx(f.safe, [f.member], {
      to: f.moduleAddr,
      data: f.module.interface.encodeFunctionData("setListEnabled", [true]),
    });
    const transferSel = usdc.interface.getFunction("transfer")!.selector;
    await execSafeTx(f.safe, [f.member], {
      to: f.moduleAddr,
      data: f.module.interface.encodeFunctionData("authorize", [usdcAddr, transferSel, true]),
    });

    // transfer is allowed under the armed list.
    await usdc.mint(f.safeAddr, ethers.parseUnits("100", 6));
    const data = usdc.interface.encodeFunctionData("transfer", [f.bot.address, ethers.parseUnits("10", 6)]);
    await f.module.connect(f.bot).executeSpend(
      usdcAddr, 0n, data, Operation.Call, usdcAddr, ethers.parseUnits("10", 6)
    );

    // mint is NOT whitelisted → blocked with NotAllowed.
    await expect(
      f.module.connect(f.bot).executeSpend(
        usdcAddr, 0n, usdc.interface.encodeFunctionData("mint", [f.bot.address, 1n]),
        Operation.Call, usdcAddr, 0n
      )
    ).to.be.revertedWithCustomError(f.module, "NotAllowed");

    // a plain native transfer (no selector) to an unlisted address still passes
    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("5") })).wait();
    await f.module.connect(f.bot).executeSpend(
      f.bot.address, ethers.parseEther("1"), "0x", Operation.Call, ethers.ZeroAddress, 0n
    );
  });
});