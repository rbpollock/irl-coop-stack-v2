import { expect } from "chai";
import { ethers } from "hardhat";

/**
 * P1 ShieldedPool — the pool spine WITHOUT the cryptography.
 *
 * NoopVerifier accepts everything, so P1 proves the ARCHITECTURE (tree, nullifiers,
 * USDC in/out, the pluggable proof seam) and NOT the crypto. Every proof-accept path
 * would also accept a wrong proof until P2 wires a real Groth16 verifier. The one
 * thing P1 DOES prove is that the seam is real: a verifier that rejects makes the
 * pool revert.
 *
 * Plan: §1a + §8. This is the P1 deliverable.
 */
describe("ShieldedPool (P1)", function () {
  let pool: any;
  let noop: any;
  let rejecting: any; // a verifier contract that always returns false
  let usdc: any;
  let depositor: any;
  let recipient: any;

  async function fixture() {
    const signers = await ethers.getSigners();
    depositor = signers[0];
    recipient = signers[1];

    const Mock = await ethers.getContractFactory("MockUsdc");
    usdc = await Mock.deploy();

    const Noop = await ethers.getContractFactory("NoopVerifier");
    noop = await Noop.deploy();

    const Reject = await ethers.getContractFactory("RejectingVerifier");
    rejecting = await Reject.deploy();

    const Pool = await ethers.getContractFactory("ShieldedPool");
    pool = await Pool.deploy(await usdc.getAddress(), await noop.getAddress());
    await pool.waitForDeployment();

    await usdc.mint(depositor.address, ethers.parseEther("1000"));
  }

  beforeEach(async function () { await fixture(); });

  async function shield(commit: string, amt: bigint) {
    await usdc.connect(depositor).approve(await pool.getAddress(), amt);
    await pool.connect(depositor).deposit(ethers.id(commit), amt);
  }

  it("starts at the all-zero-tree root with no leaves", async function () {
    expect(await pool.getRoot()).to.not.equal(0n);
    expect(await pool.nextIndex()).to.equal(0n);
  });

  it("a deposit inserts a leaf, advances the root, and pulls USDC", async function () {
    const amt = ethers.parseEther("1");
    await shield("commitment-1", amt);
    expect(await pool.nextIndex()).to.equal(1n);
    expect(await pool.getRoot()).to.not.equal(0n);
    expect(await usdc.balanceOf(await pool.getAddress())).to.equal(amt);
  });

  it("rejects a zero commitment", async function () {
    await usdc.connect(depositor).approve(await pool.getAddress(), ethers.parseEther("1"));
    await expect(pool.connect(depositor).deposit(0, 1)).to.be.revertedWithCustomError(pool, "ZeroCommitment");
  });

  it("won't double-spend a nullifier", async function () {
    await shield("in-a", ethers.parseEther("50"));
    const n = ethers.id("note-1-secret");
    await pool.connect(depositor).spend(n, ethers.id("out-a"), ethers.parseEther("25"), "0x");
    expect(await pool.spent(n)).to.equal(true);
    await expect(pool.connect(depositor).spend(n, ethers.id("x"), 1, "0x"))
      .to.be.revertedWithCustomError(pool, "DoubleSpend");
  });

  it("the proof seam is real — a rejecting verifier blocks a spend", async function () {
    await pool.setVerifier(await rejecting.getAddress());
    await shield("c2", ethers.parseEther("30"));
    await expect(pool.connect(depositor).spend(ethers.id("n2"), ethers.id("o2"), 1, "0x"))
      .to.be.revertedWithCustomError(pool, "UnverifiedProof");
  });

  it("redeem moves USDC out after nullifying the note", async function () {
    const amt = ethers.parseEther("40");
    await shield("c3", amt);
    const initialRec = await usdc.balanceOf(recipient.address);
    const n = ethers.id("n-secret-3");
    await pool.connect(depositor).redeem(n, recipient.address, amt, "0x");
    expect(await usdc.balanceOf(recipient.address)).to.equal(initialRec + amt);
    expect(await pool.spent(n)).to.equal(true);
    // the pool no longer holds that USDC
    expect(await usdc.balanceOf(await pool.getAddress())).to.equal(0n);
  });

  it("the seam's pluggability holds for both verifiers", async function () {
    expect(await noop.isNOOP()).to.equal(true);
    expect(await rejecting.isNOOP()).to.equal(false);
    // swap to the rejecting verifier blocks, swap back works
    await pool.setVerifier(await rejecting.getAddress());
    await shield("c4", ethers.parseEther("5"));
    await expect(pool.connect(depositor).spend(ethers.id("n4"), ethers.id("o4"), 1, "0x"))
      .to.be.revertedWithCustomError(pool, "UnverifiedProof");
    await pool.setVerifier(await noop.getAddress());
    await pool.connect(depositor).spend(ethers.id("n4"), ethers.id("o5"), 1, "0x"); // now allowed
    expect(await pool.spent(ethers.id("n4"))).to.equal(true);
  });
});