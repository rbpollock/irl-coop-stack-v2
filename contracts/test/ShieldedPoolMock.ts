import { expect } from "chai";
import { ethers } from "hardhat";

describe("ShieldedPoolMock", function () {
  let pool: any;
  let user: any;

  beforeEach(async function () {
    const signers = await ethers.getSigners();
    user = signers[0];

    const ShieldedPoolMock = await ethers.getContractFactory("ShieldedPoolMock");
    pool = await ShieldedPoolMock.deploy();
  });

  it("Should allow shielding a deposit", async function () {
    const commitment = ethers.id("commitment123");
    const depositAmount = ethers.parseEther("1.0");

    await expect(pool.connect(user).mockShieldDeposit(commitment, { value: depositAmount }))
      .to.emit(pool, "ShieldedMint")
      .withArgs(commitment, depositAmount);

    expect(await pool.totalShieldedAssets()).to.equal(depositAmount);
  });

  it("Should allow unshielding with sufficient balance", async function () {
    const commitment = ethers.id("commitment123");
    const depositAmount = ethers.parseEther("1.0");

    await pool.connect(user).mockShieldDeposit(commitment, { value: depositAmount });

    const nullifier = ethers.id("nullifier123");
    const withdrawAmount = ethers.parseEther("0.5");

    await expect(pool.connect(user).mockUnshieldWithdrawal(nullifier, user.address, withdrawAmount, "0x"))
      .to.emit(pool, "UnshieldedWithdrawal")
      .withArgs(user.address, withdrawAmount);

    expect(await pool.totalShieldedAssets()).to.equal(ethers.parseEther("0.5"));
  });

  it("Should record a private vote and reject double voting", async function () {
    const pollId = 1;
    const voteOption = 2; // e.g., "Yes"
    const nullifierHash = ethers.id("voteNullifier123");

    await expect(pool.connect(user).castPrivateVote(pollId, voteOption, nullifierHash, "0x"))
      .to.emit(pool, "VoteCast")
      .withArgs(pollId, voteOption);

    // Double voting
    await expect(
      pool.connect(user).castPrivateVote(pollId, voteOption, nullifierHash, "0x")
    ).to.be.revertedWith("Vote already cast");
  });
});