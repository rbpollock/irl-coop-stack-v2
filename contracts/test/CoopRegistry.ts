import { expect } from "chai";
import { ethers } from "hardhat";

describe("CoopRegistry", function () {
  async function deployFixture() {
    const CoopRegistry = await ethers.getContractFactory("CoopRegistry");
    const registry = await CoopRegistry.deploy();
    return { registry };
  }

  it("Should allow joining with a fee", async () => {
    const { registry } = await deployFixture();
    const leaf = ethers.keccak256(ethers.toUtf8Bytes("member-1"));
    // Since _appendMember is currently empty, it does not revert. 
    // We expect successful transaction.
    await expect(registry.joinGroup(leaf, { value: ethers.parseEther("0.05") }))
      .to.not.be.reverted;
  });

  it("Should support O(1) revocation", async () => {
    const { registry } = await deployFixture();
    await registry.revokeMember(123);
    expect(await registry.revokedLeaves(123)).to.equal(true);
  });
});
