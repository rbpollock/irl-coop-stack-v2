import { expect } from "chai";
import { ethers } from "hardhat";

describe("CoopRegistry", function () {
  async function deployFixture() {
    const CoopRegistry = await ethers.getContractFactory("CoopRegistry");
    const registry = await CoopRegistry.deploy();
    return { registry };
  }

  it("Should revert if join fee is insufficient", async () => {
    const { registry } = await deployFixture();
    const leaf = ethers.keccak256(ethers.toUtf8Bytes("member-1"));
    // Hardhat Chai Matchers should handle 'revertedWith'
    await expect(registry.joinGroup(leaf, { value: ethers.parseEther("0.01") }))
      .to.be.reverted;
  });

  it("Should only allow owner to revoke member", async () => {
    const { registry } = await deployFixture();
    const [_, notOwner] = await ethers.getSigners();
    await expect(registry.connect(notOwner).revokeMember(123))
      .to.be.reverted;
  });
});
