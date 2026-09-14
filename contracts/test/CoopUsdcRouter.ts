import { expect } from "chai";
import { ethers } from "hardhat";

/**
 * The router's whole job is to be the one destination a rail can send to and then get out of
 * the way. These tests assert the PROPERTIES that make that safe — not just that it runs.
 */
describe("CoopUsdcRouter", function () {
  async function fixture() {
    const [deployer, coopSafe, stranger] = await ethers.getSigners();
    const Usdc = await ethers.getContractFactory("MockUsdc");
    const usdc = await Usdc.deploy();
    const Router = await ethers.getContractFactory("CoopUsdcRouter");
    const router = await Router.deploy(await usdc.getAddress(), coopSafe.address);
    await usdc.mint(stranger.address, 1_000_000_000n); // 1000 USDC (6dp)
    await usdc.mint(deployer.address, 1_000_000_000n);
    return { usdc, router, deployer, coopSafe, stranger };
  }
  const ONE = 1_000_000n; // 1 USDC at 6 decimals

  it("a plain ERC-20 transfer lands, and NO code of ours runs (the inherent ERC-20 fact)", async () => {
    const { usdc, router, stranger } = await fixture();
    const routerAddr = await router.getAddress();
    // The rail's transfer is a plain `transfer`: no callback, no event from the router.
    await expect(usdc.connect(stranger).transfer(routerAddr, 5n * ONE)).to.not.emit(router, "DepositNoted");
    expect(await usdc.balanceOf(routerAddr)).to.equal(5n * ONE);
  });

  it("sweep() forwards the WHOLE balance to the immutable destination", async () => {
    const { usdc, router, stranger, coopSafe } = await fixture();
    const routerAddr = await router.getAddress();
    await usdc.connect(stranger).transfer(routerAddr, 5n * ONE);
    await router.sweep();
    expect(await usdc.balanceOf(coopSafe.address)).to.equal(5n * ONE);
    expect(await usdc.balanceOf(routerAddr)).to.equal(0n);
  });

  it("ANYONE can sweep — no keeper to compel, no privileged caller", async () => {
    const { usdc, router, stranger, coopSafe } = await fixture();
    await usdc.connect(stranger).transfer(await router.getAddress(), 3n * ONE);
    // called by a signer with no relationship to the contract
    await expect(router.connect(stranger).sweep()).to.emit(router, "Swept");
    expect(await usdc.balanceOf(coopSafe.address)).to.equal(3n * ONE);
  });

  it("the destination is IMMUTABLE and there is no admin surface at all", async () => {
    const { router, coopSafe } = await fixture();
    expect(await router.destination()).to.equal(coopSafe.address);
    // assert by ABSENCE: no owner, no setters, no upgrade path anywhere in the ABI
    const abi = router.interface.fragments.map((f: any) => f.name).filter(Boolean);
    const forbidden = ["owner", "transferOwnership", "renounceOwnership", "setDestination", "upgradeTo", "upgradeToAndCall", "initialize", "pause", "unpause"];
    expect(abi.filter((n: string) => forbidden.includes(n))).to.deep.equal([]);
    expect(await router.token()).to.not.equal(ethers.ZeroAddress);
  });

  it("sweeping an empty router REVERTS rather than pretending to succeed", async () => {
    const { router } = await fixture();
    await expect(router.sweep()).to.be.revertedWithCustomError(router, "NothingToSweep");
  });

  it("a second sweep cannot double-send", async () => {
    const { usdc, router, stranger } = await fixture();
    await usdc.connect(stranger).transfer(await router.getAddress(), 2n * ONE);
    await router.sweep();
    await expect(router.sweep()).to.be.revertedWithCustomError(router, "NothingToSweep");
  });

  it("deposits accumulate, then one sweep moves everything", async () => {
    const { usdc, router, stranger, deployer, coopSafe } = await fixture();
    const routerAddr = await router.getAddress();
    await usdc.connect(stranger).transfer(routerAddr, 2n * ONE);
    await usdc.connect(deployer).transfer(routerAddr, 3n * ONE);
    await router.sweep();
    expect(await usdc.balanceOf(coopSafe.address)).to.equal(5n * ONE);
  });

  it("native value CANNOT be sent here (no receive/fallback), so ETH cannot be trapped", async () => {
    const { router, stranger } = await fixture();
    await expect(stranger.sendTransaction({ to: await router.getAddress(), value: 1n })).to.be.reverted;
  });

  it("the constructor refuses a zero destination", async () => {
    const { usdc } = await fixture();
    const Router = await ethers.getContractFactory("CoopUsdcRouter");
    await expect(Router.deploy(await usdc.getAddress(), ethers.ZeroAddress)).to.be.revertedWithCustomError(Router, "ZeroAddress");
  });

  it("a stray ERC-20 can only go to the immutable destination, and rescue() refuses the real token", async () => {
    const { usdc, router, coopSafe } = await fixture();
    const Stray = await ethers.getContractFactory("MockUsdc");
    const stray = await Stray.deploy();
    await stray.mint(await router.getAddress(), 7n * ONE);
    await expect(router.rescue(await usdc.getAddress())).to.be.revertedWithCustomError(router, "UseSweep");
    await router.rescue(await stray.getAddress());
    expect(await stray.balanceOf(coopSafe.address)).to.equal(7n * ONE);
    expect(await stray.balanceOf(await router.getAddress())).to.equal(0n);
  });

  it("noteDeposit() records the OBSERVER, never a claimed payer, and moves nothing", async () => {
    const { usdc, router, stranger, deployer } = await fixture();
    const routerAddr = await router.getAddress();
    await usdc.connect(stranger).transfer(routerAddr, 4n * ONE);
    // the depositor is unknowable on-chain, so the event must not pretend to name them
    await expect(router.connect(deployer).noteDeposit())
      .to.emit(router, "DepositNoted")
      .withArgs(deployer.address, 4n * ONE);
    expect(await usdc.balanceOf(routerAddr)).to.equal(4n * ONE);
  });
});
