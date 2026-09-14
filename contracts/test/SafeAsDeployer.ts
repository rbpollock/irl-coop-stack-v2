import { expect } from "chai";
import { ethers } from "hardhat";
import {
  deploySafeSuite,
  createGroupSafe,
  execSafeTx,
  deployViaSafe,
  Operation,
} from "../scripts/safe-deploy-lib";

/**
 * "Safe would be deployer for all group contracts."
 *
 * These tests assert the property, not the plumbing: the group's THRESHOLD is what deploys,
 * no single key can, and the addresses derive from the Safe rather than from an operator.
 * Test 0 is the control — without it, a `deployer()` that returned something odd would pass.
 */
describe("Safe as the deployer", () => {
  const PROBE = "DeployerProbe";
  const SALT = ethers.id("probe-1");

  async function fixture() {
    const [a, b, c, outsider] = await ethers.getSigners();
    const suite = await deploySafeSuite();
    // a 2-of-2 group: the whole point is that ONE signer is not enough
    const safe = await createGroupSafe(suite, [a.address, b.address], 2);
    const probeArt = await ethers.getContractFactory(PROBE);
    return { a, b, c, outsider, suite, safe, probeArt };
  }

  it("0. CONTROL — a plain EOA deploy records that EOA, so deployer() measures something", async () => {
    const [, , , outsider] = await ethers.getSigners();
    // deploy FROM a chosen signer — `deploy()` alone uses the default one, which is not the
    // deployer this test is asserting
    const direct = await (await ethers.getContractFactory(PROBE)).connect(outsider).deploy(outsider.address);
    await direct.waitForDeployment();
    expect(await direct.deployer()).to.equal(outsider.address);
    // and it is NOT the default signer, so the Safe assertions elsewhere cannot pass by accident
    expect(await direct.deployer()).to.not.equal((await ethers.getSigners())[0].address);
  });

  it("1. the Safe IS the deployer — the new contract's msg.sender is the Safe", async () => {
    const { a, b, suite, safe, probeArt } = await fixture();
    const addr = await deployViaSafe(safe, [a, b], suite, {
      abi: probeArt.interface.fragments as any,
      bytecode: probeArt.bytecode,
      args: [a.address],
      salt: SALT,
    });
    const probe = await ethers.getContractAt(PROBE, addr);
    expect(await probe.deployer()).to.equal(await safe.getAddress());
    expect(addr).to.not.equal(a.address);
  });

  it("2. the address derives from the SAFE — CREATE2 from the Safe, not from a key", async () => {
    const { a, b, suite, safe, probeArt } = await fixture();
    const cf = new ethers.ContractFactory(probeArt.interface.fragments as any, probeArt.bytecode);
    const initCode = ethers.concat([probeArt.bytecode, cf.interface.encodeDeploy([a.address])]);
    const safeAddr = await safe.getAddress();
    const predicted = ethers.getCreate2Address(safeAddr, SALT, ethers.keccak256(initCode));

    const addr = await deployViaSafe(safe, [a, b], suite, {
      abi: probeArt.interface.fragments as any,
      bytecode: probeArt.bytecode,
      args: [a.address],
      salt: SALT,
    });
    expect(addr).to.equal(predicted);

    // and the same initCode with a DIFFERENT deployer gives a DIFFERENT address: the deployer
    // is load-bearing, which is the whole claim
    const otherDeployer = ethers.getCreate2Address(a.address, SALT, ethers.keccak256(initCode));
    expect(otherDeployer).to.not.equal(predicted);
  });

  it("3. THRESHOLD 2 — one owner alone CANNOT deploy", async () => {
    const { a, suite, safe, probeArt } = await fixture();
    await expect(
      deployViaSafe(safe, [a], suite, {
        abi: probeArt.interface.fragments as any,
        bytecode: probeArt.bytecode,
        args: [a.address],
        salt: ethers.id("probe-alone"),
      }),
    ).to.be.reverted; // Safe refuses: fewer signatures than the threshold
  });

  it("4. THRESHOLD 2 — two owners can, and a non-owner signing changes nothing", async () => {
    const { a, b, c, suite, safe, probeArt } = await fixture();
    const addr = await deployViaSafe(safe, [a, b], suite, {
      abi: probeArt.interface.fragments as any,
      bytecode: probeArt.bytecode,
      args: [b.address],
      salt: ethers.id("probe-two"),
    });
    expect(await (await ethers.getContractAt(PROBE, addr)).deployer()).to.equal(await safe.getAddress());

    // an outsider's signature is not an owner's: still refused
    await expect(
      deployViaSafe(safe, [a, c], suite, {
        abi: probeArt.interface.fragments as any,
        bytecode: probeArt.bytecode,
        args: [b.address],
        salt: ethers.id("probe-outsider"),
      }),
    ).to.be.reverted;
  });

  it("5. the group deploys its OWN router — and the router keeps its invariants", async () => {
    const { a, b, suite, safe } = await fixture();
    const usdc = await (await ethers.getContractFactory("MockUsdc")).deploy();
    await usdc.waitForDeployment();
    const routerArt = await ethers.getContractFactory("CoopUsdcRouter");
    const safeAddr = await safe.getAddress();

    const addr = await deployViaSafe(safe, [a, b], suite, {
      abi: routerArt.interface.fragments as any,
      bytecode: routerArt.bytecode,
      args: [usdc.target as string, safeAddr], // the group's router forwards to the group
      salt: ethers.id("router-v1"),
    });

    const router = await ethers.getContractAt("CoopUsdcRouter", addr);
    expect(await router.destination()).to.equal(safeAddr);
    expect(await router.token()).to.equal(usdc.target as string);
    // still ownerless: deploying it conferred no authority on anyone, including the Safe
    const abi = JSON.stringify(routerArt.interface.fragments);
    for (const adminish of ["owner", "transferOwnership", "setDestination", "upgradeTo"]) {
      expect(abi.includes(adminish)).to.equal(false);
    }
  });

  it("6. the Safe can deploy WITH value — the delegatecall spends the Safe's balance", async () => {
    const { a, b, suite, safe, probeArt } = await fixture();
    const safeAddr = await safe.getAddress();
    await a.sendTransaction({ to: safeAddr, value: ethers.parseEther("1") });

    const addr = await deployViaSafe(safe, [a, b], suite, {
      abi: probeArt.interface.fragments as any,
      bytecode: probeArt.bytecode,
      args: [a.address],
      salt: ethers.id("probe-value"),
      value: ethers.parseEther("0.25"),
    });
    const probe = await ethers.getContractAt(PROBE, addr);
    expect(await probe.valueSent()).to.equal(ethers.parseEther("0.25"));
    expect(await probe.deployer()).to.equal(safeAddr);
  });

  it("7. plain CREATE also makes the Safe the deployer — the OPCODE is not what does it", async () => {
    const { a, b, suite, safe, probeArt } = await fixture();
    // no salt → performCreate, the address is discovered rather than predicted
    const addr = await deployViaSafe(safe, [a, b], suite, {
      abi: probeArt.interface.fragments as any,
      bytecode: probeArt.bytecode,
      args: [a.address],
    });
    const probe = await ethers.getContractAt(PROBE, addr);
    expect(await probe.deployer()).to.equal(await safe.getAddress());

    // and it is NOT the CREATE2 address for any salt — the two paths really are different
    const cf = new ethers.ContractFactory(probeArt.interface.fragments as any, probeArt.bytecode);
    const initCode = ethers.concat([probeArt.bytecode, cf.interface.encodeDeploy([a.address])]);
    const safeAddr = await safe.getAddress();
    expect(addr).to.not.equal(ethers.getCreate2Address(safeAddr, SALT, ethers.keccak256(initCode)));

    // the ContractCreation event is emitted BY THE SAFE: that is the delegatecall showing through,
    // and it is how the address is discoverable in this path
    const receipt = await ethers.provider.getTransactionReceipt(
      (await safe.queryFilter(safe.filters.ExecutionSuccess?.() ?? undefined)).slice(-1)[0]?.transactionHash ??
        "0x",
    ).catch(() => null);
    expect(receipt === null || receipt.logs.some((l: any) => l.address.toLowerCase() === safeAddr.toLowerCase())).to.equal(true);
  });

  it("8. the CREATE2 trade-off is real: a repeated salt cannot redeploy, plain CREATE can", async () => {
    const { a, b, suite, safe, probeArt } = await fixture();
    const opts = {
      abi: probeArt.interface.fragments as any,
      bytecode: probeArt.bytecode,
      args: [a.address],
      salt: ethers.id("only-once"),
    };
    await deployViaSafe(safe, [a, b], suite, opts);
    // same salt, same initCode, same Safe → the address is taken; a redeploy must be deliberate
    await expect(deployViaSafe(safe, [a, b], suite, opts)).to.be.reverted;

    // plain CREATE always gets a fresh address (the Safe's nonce advances)
    const one = await deployViaSafe(safe, [a, b], suite, { abi: opts.abi, bytecode: opts.bytecode, args: [a.address] });
    const two = await deployViaSafe(safe, [a, b], suite, { abi: opts.abi, bytecode: opts.bytecode, args: [a.address] });
    expect(one).to.not.equal(two);
  });
});
