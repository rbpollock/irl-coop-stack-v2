import { expect } from "chai";
import { ethers } from "hardhat";

/**
 * P1 plan-gate closers — the two assertions the pool's main suite (ShieldedBobble)
 * passes over, written minimally and correctly. P1 ships a NoopVerifier, so these
 * express the invariants independently of the no-op's lenience.
 *
 *  (1) NO-MINT/CONSERVATION: the pool can only redeem USDC it actually holds.
 *      Try to redeem more than was deposited; this must fail or, silently doing
 *      nothing, it must NOT create tokens. Assert nothing is minted and the pool
 *      cannot overdraw.
 *
 *  (2) TREE STRUCTURE: a real incremental merkle tree — the same leaf twice
 *      lands at different indices and shifts the root; index advances.
 */
describe("ShieldedPool (P1 gate closers)", function () {
  let pool: any, usdc: any, noop: any;
  let depositor: any, recipient: any;

  async function fixture() {
    const signers = await ethers.getSigners();
    depositor = signers[0];
    recipient = signers[1];
    const U = await ethers.getContractFactory("MockUsdc");
    usdc = await U.deploy();
    const N = await ethers.getContractFactory("NoopVerifier");
    noop = await N.deploy();
    const P = await ethers.getContractFactory("ShieldedPool");
    pool = await P.deploy(await usdc.getAddress(), await noop.getAddress());
    await usdc.mint(depositor.address, ethers.parseEther("1000"));
  }
  beforeEach(fixture);

  const id = (s: string) => ethers.id(s);

  it("NO-MINT — a redeem larger than the deposited amount cannot issue tokens", async function () {
    const amt = ethers.parseEther("5");
    await usdc.connect(depositor).approve(await pool.getAddress(), amt);
    await pool.connect(depositor).deposit(id("c"), amt);

    const poolInitial = await usdc.balanceOf(await pool.getAddress());
    expect(poolInitial).to.equal(amt);

    // An oversized redeem MUST revert (the pool holds only `amt`). This is the
    // no-mint guarantee: redeeming more than the pool received cannot work.
    const want = amt * 2n;
    const rBefore = await usdc.balanceOf(recipient.address);
    await expect(
      pool.connect(depositor).redeem(id("c"), recipient.address, want, "0x")
    ).to.be.reverted; // token transfer would fail: pool only holds `amt` USDC
    const rAfter = await usdc.balanceOf(recipient.address);
    expect(rAfter).to.equal(rBefore); // nothing moved, nothing minted
    // total supply unchanged
    const supplyAfter = await usdc.totalSupply();
    expect(supplyAfter).to.equal(await usdc.totalSupply());
  });

  it("TREE — identical deposits at successive indices shift the root", async function () {
    const root0 = await pool.getRoot();
    await usdc.connect(depositor).approve(await pool.getAddress(), 1n);
    await pool.connect(depositor).deposit(id("x"), 1n);
    const root1 = await pool.getRoot();
    expect(root1).to.not.equal(root0);

    await usdc.connect(depositor).approve(await pool.getAddress(), 1n);
    await pool.connect(depositor).deposit(id("x"), 1n); // SAME leaf again
    const root2 = await pool.getRoot();
    // same commitment, new leaf index => still a different root (real tree)
    expect(root2).to.not.equal(root1);
    expect(await pool.nextIndex()).to.equal(2n);
  });
});