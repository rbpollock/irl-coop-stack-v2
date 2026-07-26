import { expect } from "chai";
import { ethers } from "hardhat";

describe("CoopBatchRouter", function () {
  async function deployFixture() {
    const CoopRegistry = await ethers.getContractFactory("CoopRegistry");
    const registry = await CoopRegistry.deploy();
    
    const CoopBatchRouter = await ethers.getContractFactory("CoopBatchRouter");
    const router = await CoopBatchRouter.deploy(await registry.getAddress());
    
    return { registry, router };
  }

  it("Should route deposit", async () => {
    const { router } = await deployFixture();
    const amount = ethers.parseEther("0.1");
    
    // Simple execution check for now
    await expect(router.routeDeposit({ value: amount }))
      .to.not.be.reverted;
  });
});
