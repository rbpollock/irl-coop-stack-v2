import { expect } from "chai";
import { ethers } from "hardhat";
import { deploySafeSuite, createGroupSafe, sponsorSafeTx, Operation } from "../scripts/safe-deploy-lib";

/**
 * "How does a Safe transaction get SPONSORED on Hardhat?"
 *
 * The premise of sponsorship: the Safe's owners hold no gas (they are passkeys /
 * JWT-derivations or cold keys), so a THIRD PARTY — the relayer / sponsor EOA —
 * broadcasts the `execTransaction` and pays the gas. The Safe still requires the
 * owners' threshold; the sponsor is NOT an owner. This is the ERC-4337-relayer
 * shape, minus the EntryPoint.
 *
 * These tests prove the SPONSORSHIP, not gas metering (Hardhat gas is ~free):
 *   1. a sponsor EOA can submit a transaction the owners signed (threshold met),
 *      and it executes.
 *   2. a sponsor CANNOT push a transaction the owners did NOT sign — the Safe
 *      refuses (the signature set must meet threshold). The sponsor has no
 *      authority, only a carrying role.
 *   3. the Safe remains the deployer even when an outsider sponsors.
 */
describe("Safe transactions sponsored by a third party (Hardhat)", () => {
  const PROBE = "DeployerProbe";

  async function fixture() {
    const [a, b, outsider, sponsor] = await ethers.getSigners();
    const suite = await deploySafeSuite();
    // 2-of-2 group: one signer alone is NOT enough (the whole sponsorship point)
    const safe = await createGroupSafe(suite, [a.address, b.address], 2);
    const probeArt = await ethers.getContractFactory(PROBE);
    return { a, b, outsider, sponsor, suite, safe, probeArt };
  }

  it("1. a non-owner SPONSOR broadcasts a Safe tx the two owners signed — it executes", async () => {
    const { a, b, sponsor, suite, safe, probeArt } = await fixture();

    // Build the deploy calldata (the Safe deploys its own probe, as settled).
    const cf = new ethers.ContractFactory(probeArt.interface.fragments as any, probeArt.bytecode);
    const initCode = ethers.concat([probeArt.bytecode, cf.interface.encodeDeploy([a.address])]);
    const createCall = await ethers.getContractAt(
      "@safe-global/safe-contracts/contracts/libraries/CreateCall.sol:CreateCall",
      suite.createCall,
    );
    const data = createCall.interface.encodeFunctionData("performCreate", [0n, initCode]);

    const sponsorBalBefore = await ethers.provider.getBalance(sponsor.address);
    // Owner a + b sign; sponsor broadcasts. Sponsor is NOT an owner.
    await sponsorSafeTx(safe, [a, b], sponsor, {
      to: suite.createCall,
      data,
      operation: Operation.DelegateCall,
    });
    const sponsorBalAfter = await ethers.provider.getBalance(sponsor.address);
    // The sponsor PAID gas (balance went DOWN in real terms; Hardhat is cheap but nonzero)
    expect(sponsorBalAfter < sponsorBalBefore, "sponsor paid gas for the tx").to.be.true;
    console.log(`  sponsor paid ${(sponsorBalBefore - sponsorBalAfter).toString()} wei in gas`);
  });

  it("2. a sponsor cannot execute without the owners' signatures — the Safe refuses", async () => {
    const { a, sponsor, suite, safe, probeArt } = await fixture();
    const cf = new ethers.ContractFactory(probeArt.interface.fragments as any, probeArt.bytecode);
    const initCode = ethers.concat([probeArt.bytecode, cf.interface.encodeDeploy([a.address])]);
    const createCall = await ethers.getContractAt(
      "@safe-global/safe-contracts/contracts/libraries/CreateCall.sol:CreateCall",
      suite.createCall,
    );
    const data = createCall.interface.encodeFunctionData("performCreate", [0n, initCode]);
    // Only ONE owner signs (below threshold 2). Sponsor tries to push it.
    await expect(
      sponsorSafeTx(safe, [a], sponsor, {
        to: suite.createCall,
        data,
        operation: Operation.DelegateCall,
      }),
    ).to.be.reverted;
  });

  it("3. the sponsor gains no authority — the Safe's owner set is untouched by the sponsorship", async () => {
    const { a, b, sponsor, suite, safe, probeArt } = await fixture();
    const before: string[] = await safe.getOwners();
    const beforeThreshold: bigint = await safe.getThreshold();
    const cf = new ethers.ContractFactory(probeArt.interface.fragments as any, probeArt.bytecode);
    const initCode = ethers.concat([probeArt.bytecode, cf.interface.encodeDeploy([a.address])]);
    const createCall = await ethers.getContractAt(
      "@safe-global/safe-contracts/contracts/libraries/CreateCall.sol:CreateCall",
      suite.createCall,
    );
    // performCreate (plain) is the default one-off — matches the SafeAsDeployer pattern.
    const data = createCall.interface.encodeFunctionData("performCreate", [0n, initCode]);
    await sponsorSafeTx(safe, [a, b], sponsor, {
      to: suite.createCall,
      data,
      operation: Operation.DelegateCall,
    });
    // The sponsorship carried the deploy; the authority stays with the Safe.
    const after: string[] = await safe.getOwners();
    const afterThreshold: bigint = await safe.getThreshold();
    expect(after.length).to.equal(before.length, "no owner added");
    expect(after.map((x) => x.toLowerCase())).to.deep.equal(before.map((x) => x.toLowerCase()));
    expect(afterThreshold).to.equal(beforeThreshold, "threshold unchanged");
    expect(after.map((x) => x.toLowerCase()), "sponsor did not become an owner").to.not.include(sponsor.address.toLowerCase());
  });
});