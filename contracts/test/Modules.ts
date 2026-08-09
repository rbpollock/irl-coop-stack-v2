import { expect } from "chai";
import { ethers } from "hardhat";

describe("Core AA Smart Contract Modules", function () {
  describe("PasskeyValidator", function () {
    it("Should deploy and exist", async function () {
      const PasskeyValidator = await ethers.getContractFactory("PasskeyValidator");
      const validator = await PasskeyValidator.deploy();
      expect(await validator.getAddress()).to.be.properAddress;
    });
  });

  describe("SovereignEvolutionModule", function () {
    let evolutionModule: any;
    let safeSigner: any;
    let backendSigner: any;
    let guardianA: any;
    let guardianB: any;

    beforeEach(async function () {
      const signers = await ethers.getSigners();
      safeSigner = signers[0]; // Simulating the Safe proxy calling the module
      backendSigner = signers[1];
      guardianA = signers[2];
      guardianB = signers[3];

      const EvolutionModule = await ethers.getContractFactory("SovereignEvolutionModule");
      evolutionModule = await EvolutionModule.deploy();
    });

    it("Should initialize a safe at Stage 1", async function () {
      await evolutionModule.connect(safeSigner).initializeSafe(backendSigner.address);
      const config = await evolutionModule.getSafeConfig(safeSigner.address);
      
      expect(config[0]).to.equal(0n); // Stage1_Convenience
      expect(config[1]).to.equal(backendSigner.address);
      expect(config[2].length).to.equal(0);
    });

    it("Should promote a safe to Stage 2 and revoke backend signer", async function () {
      await evolutionModule.connect(safeSigner).initializeSafe(backendSigner.address);
      
      const guardians = [guardianA.address, guardianB.address];
      
      const tx = await evolutionModule.connect(safeSigner).promoteToSovereign(guardians);
      await tx.wait();

      const config = await evolutionModule.getSafeConfig(safeSigner.address);
      
      expect(config[0]).to.equal(1n); // Stage2_Sovereign
      expect(config[1]).to.equal(ethers.ZeroAddress); // Backend revoked
      expect(config[2].length).to.equal(2);
      expect(config[2][0]).to.equal(guardianA.address);
      expect(config[2][1]).to.equal(guardianB.address);
    });

    it("Should revert if promoting without enough guardians", async function () {
      await evolutionModule.connect(safeSigner).initializeSafe(backendSigner.address);
      
      const guardians = [guardianA.address]; // Only 1
      
      await expect(
        evolutionModule.connect(safeSigner).promoteToSovereign(guardians)
      ).to.be.revertedWith("Requires at least 2 guardians");
    });
  });

  describe("SessionKeyModule", function () {
    let sessionModule: any;
    let safeSigner: any;
    let sessionKeySigner: any;

    beforeEach(async function () {
      const signers = await ethers.getSigners();
      safeSigner = signers[0];
      sessionKeySigner = signers[1];

      const SessionKeyModule = await ethers.getContractFactory("SessionKeyModule");
      sessionModule = await SessionKeyModule.deploy();
    });

    it("Should enable a session key and allow spending within limits", async function () {
      const dailyLimit = ethers.parseEther("500"); // 500 units
      await sessionModule.connect(safeSigner).enableSessionKey(sessionKeySigner.address, dailyLimit);
      
      let remaining = await sessionModule.getRemainingLimit(safeSigner.address);
      expect(remaining).to.equal(dailyLimit);

      // Record a spend
      const spendAmount = ethers.parseEther("100");
      await sessionModule.checkAndRecordSpend(safeSigner.address, spendAmount);

      remaining = await sessionModule.getRemainingLimit(safeSigner.address);
      expect(remaining).to.equal(ethers.parseEther("400"));
    });

    it("Should reject spending that exceeds daily limits", async function () {
      const dailyLimit = ethers.parseEther("100");
      await sessionModule.connect(safeSigner).enableSessionKey(sessionKeySigner.address, dailyLimit);
      
      const overSpend = ethers.parseEther("150");
      await expect(
        sessionModule.checkAndRecordSpend(safeSigner.address, overSpend)
      ).to.be.revertedWith("Daily spending limit exceeded");
    });
  });
});
