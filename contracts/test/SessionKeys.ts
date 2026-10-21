import { expect } from "chai";
import { ethers } from "hardhat";
import { deploySafeSuite, createGroupSafe, execSafeTx } from "../scripts/safe-deploy-lib";

/**
 * SessionKeyModule wired to a REAL group Safe (Safe 1.4.1 module pattern), after the
 * B-12 hardening:
 *
 *  - the group Safe is owned by [member, coMember] threshold 1; the SESSION key is
 *    deliberately NOT an owner.
 *  - governance (a Safe tx) enables the module on the Safe and binds the session key
 *    with a budget + expiry — enableSessionKey is callable ONLY BY the Safe.
 *  - the bot drives the Safe via module.executeSpend → Safe.execTransactionFromModule,
 *    which Safe permits ONLY while the module is enabled (GS104).
 *  - the allow-list is DENIED by default; a spend is refused until the owners arm it
 *    and put a target/selector on it. operation is forced to Call. The spend amount is
 *    derived from the calldata, never declared by the caller. A session expires.
 */

const SENTINEL_MODULES = "0x0000000000000000000000000000000000000001";

describe("SessionKeyModule vs a live group Safe (hardened)", () => {
  async function fixture() {
    const [member, coMember, bot, target] = await ethers.getSigners();
    const suite = await deploySafeSuite();
    const safe = await createGroupSafe(suite, [member.address, coMember.address], 1);
    const Module = await ethers.getContractFactory("SessionKeyModule");
    const module = await Module.deploy(await safe.getAddress());
    await module.waitForDeployment();
    return {
      member,
      coMember,
      bot,
      target,
      safe,
      module,
      moduleAddr: await module.getAddress(),
      safeAddr: await safe.getAddress(),
    };
  }

  /** Governance: enable the module on the Safe + bind the session key (budget, expiry). */
  async function setupSession(
    f: Awaited<ReturnType<typeof fixture>>,
    dailyLimit: bigint,
    validUntil = 0n,
  ) {
    const enableData = f.safe.interface.encodeFunctionData("enableModule", [f.moduleAddr]);
    await execSafeTx(f.safe, [f.member], { to: f.safeAddr, data: enableData });
    const setData = f.module.interface.encodeFunctionData("enableSessionKey", [
      f.bot.address,
      dailyLimit,
      validUntil,
    ]);
    await execSafeTx(f.safe, [f.member], { to: f.moduleAddr, data: setData });
  }

  /** Governance: arm the allow-list and whitelist one target/selector. */
  async function arm(f: Awaited<ReturnType<typeof fixture>>, target: string, selector: string) {
    await execSafeTx(f.safe, [f.member], {
      to: f.moduleAddr,
      data: f.module.interface.encodeFunctionData("setListEnabled", [true]),
    });
    await execSafeTx(f.safe, [f.member], {
      to: f.moduleAddr,
      data: f.module.interface.encodeFunctionData("authorize", [target, selector, true]),
    });
  }

  it("the bot gets its budget via the Safe and is NOT an owner", async () => {
    const f = await fixture();
    const daily = ethers.parseEther("500");
    await setupSession(f, daily);

    const cfg = await f.module.config();
    expect(cfg.sessionKey).to.equal(f.bot.address);
    expect(cfg.dailyLimit).to.equal(daily);
    expect(cfg.validUntil).to.equal(0n);
    expect(await f.safe.isModuleEnabled(f.moduleAddr)).to.equal(true);
    expect(await f.safe.isOwner(f.bot.address)).to.equal(false);
    expect(await f.module.getRemainingLimit(f.moduleAddr)).to.equal(daily);
  });

  it("rejects binding the session key unless called BY the Safe (bot cannot self-grant)", async () => {
    const f = await fixture();
    await expect(
      f.module.connect(f.bot).enableSessionKey(f.coMember.address, ethers.parseEther("1"), 0n),
    ).to.be.revertedWithCustomError(f.module, "NotSafe");
  });

  it("is DENIED by default — a spend is refused until the owners arm the allow-list", async () => {
    const f = await fixture();
    await setupSession(f, ethers.parseEther("100"));
    expect(await f.module.listEnabled()).to.equal(false);
    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("50") })).wait();
    await expect(
      f.module.connect(f.bot).executeSpend(f.bot.address, ethers.parseEther("10"), "0x", 0),
    ).to.be.revertedWithCustomError(f.module, "NotAllowed");
  });

  it("a bot spend within budget EXECUTES the Safe and is bounded (native)", async () => {
    const f = await fixture();
    await setupSession(f, ethers.parseEther("100"));
    await arm(f, f.bot.address, ethers.ZeroHash.slice(0, 10)); // whitelist the whole target
    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("100") })).wait();

    const before = await ethers.provider.getBalance(f.safeAddr);
    const spend = ethers.parseEther("40");
    await (await f.module.connect(f.bot).executeSpend(f.bot.address, spend, "0x", 0)).wait();

    const after = await ethers.provider.getBalance(f.safeAddr);
    expect(before - after).to.equal(spend);
    expect(await f.module.getRemainingLimit(f.safeAddr)).to.equal(ethers.parseEther("60"));
  });

  it("a bot spend OVER budget reverts and the Safe is untouched", async () => {
    const f = await fixture();
    await setupSession(f, ethers.parseEther("50"));
    await arm(f, f.bot.address, ethers.ZeroHash.slice(0, 10));
    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("100") })).wait();

    const before = await ethers.provider.getBalance(f.safeAddr);
    await expect(
      f.module.connect(f.bot).executeSpend(f.bot.address, ethers.parseEther("80"), "0x", 0),
    ).to.be.revertedWithCustomError(f.module, "DailyLimitExceeded");
    expect(await ethers.provider.getBalance(f.safeAddr)).to.equal(before);
  });

  it("refuses delegatecall (operation != Call) — the takeover path", async () => {
    const f = await fixture();
    await setupSession(f, ethers.parseEther("100"));
    await arm(f, f.bot.address, ethers.ZeroHash.slice(0, 10));
    await expect(
      f.module.connect(f.bot).executeSpend(f.bot.address, 0n, "0x12345678", 1),
    ).to.be.revertedWithCustomError(f.module, "BadOperation");
  });

  it("refuses an expired session", async () => {
    const f = await fixture();
    const past = BigInt(Math.floor(Date.now() / 1000) - 60);
    await setupSession(f, ethers.parseEther("100"), past);
    await arm(f, f.bot.address, ethers.ZeroHash.slice(0, 10));
    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("10") })).wait();
    await expect(
      f.module.connect(f.bot).executeSpend(f.bot.address, ethers.parseEther("1"), "0x", 0),
    ).to.be.revertedWithCustomError(f.module, "Expired");
  });

  it("an ERC-20 spend is bounded by the CALLDATA amount, not the caller's word", async () => {
    const f = await fixture();
    await setupSession(f, ethers.parseUnits("100", 6)); // 100 USDC/day
    const usdc = await (await ethers.getContractFactory("MockUsdc")).deploy();
    await usdc.waitForDeployment();
    const usdcAddr = await usdc.getAddress();
    await arm(f, usdcAddr, usdc.interface.getFunction("transfer")!.selector);

    await usdc.mint(f.safeAddr, ethers.parseUnits("100", 6));
    const amount = ethers.parseUnits("40", 6);
    const transferData = usdc.interface.encodeFunctionData("transfer", [f.bot.address, amount]);
    await (await f.module.connect(f.bot).executeSpend(usdcAddr, 0n, transferData, 0)).wait();

    expect(await usdc.balanceOf(f.safeAddr)).to.equal(ethers.parseUnits("60", 6));
    expect(await usdc.balanceOf(f.bot.address)).to.equal(amount);
    expect(await f.module.getRemainingLimit(f.safeAddr)).to.equal(ethers.parseUnits("60", 6));
  });

  it("refuses a call whose amount cannot be read (UnboundedCall)", async () => {
    const f = await fixture();
    await setupSession(f, ethers.parseEther("100"));
    const usdc = await (await ethers.getContractFactory("MockUsdc")).deploy();
    await usdc.waitForDeployment();
    const usdcAddr = await usdc.getAddress();
    // Whitelist the WHOLE token (so _allowed passes), then call an unbound method.
    await arm(f, usdcAddr, ethers.ZeroHash.slice(0, 10));
    await expect(
      f.module.connect(f.bot).executeSpend(
        usdcAddr,
        0n,
        usdc.interface.encodeFunctionData("mint", [f.bot.address, 1n]),
        0,
      ),
    ).to.be.revertedWithCustomError(f.module, "UnboundedCall");
  });

  it("arming the list restricts the bot to the whitelisted selector", async () => {
    const f = await fixture();
    await setupSession(f, ethers.parseEther("100"));
    const usdc = await (await ethers.getContractFactory("MockUsdc")).deploy();
    await usdc.waitForDeployment();
    const usdcAddr = await usdc.getAddress();
    await arm(f, usdcAddr, usdc.interface.getFunction("transfer")!.selector);

    // a NON-whitelisted selector on the token is refused
    await expect(
      f.module.connect(f.bot).executeSpend(
        usdcAddr,
        0n,
        usdc.interface.encodeFunctionData("mint", [f.bot.address, 1n]),
        0,
      ),
    ).to.be.revertedWithCustomError(f.module, "NotAllowed");

    // a native transfer to an unlisted address is refused too
    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("5") })).wait();
    await expect(
      f.module.connect(f.bot).executeSpend(f.bot.address, ethers.parseEther("1"), "0x", 0),
    ).to.be.revertedWithCustomError(f.module, "NotAllowed");
  });

  it("disabling the module severs the bot", async () => {
    const f = await fixture();
    await setupSession(f, ethers.parseEther("100"));
    await arm(f, f.bot.address, ethers.ZeroHash.slice(0, 10));

    const disableData = f.safe.interface.encodeFunctionData("disableModule", [
      SENTINEL_MODULES,
      f.moduleAddr,
    ]);
    await execSafeTx(f.safe, [f.member], { to: f.safeAddr, data: disableData });
    expect(await f.safe.isModuleEnabled(f.moduleAddr)).to.equal(false);

    await (await f.bot.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("10") })).wait();
    await expect(
      f.module.connect(f.bot).executeSpend(f.bot.address, ethers.parseEther("5"), "0x", 0),
    ).to.be.revertedWith("GS104");
  });
});