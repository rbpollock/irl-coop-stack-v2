import { ethers } from "hardhat";

/**
 * Deploy contracts BY a group's Safe.
 *
 * Why this shape: a Safe cannot run a CREATE itself, but Safe ships an audited library
 * (`CreateCall`) with `public` functions — and a DELEGATECALL runs them in the Safe's OWN
 * context, so the CREATE opcode executes as the Safe. The new contract's constructor therefore
 * sees `msg.sender == the Safe`, and the address derives from the Safe. That is exactly how
 * Safe's own SafeProxyFactory works, which is why it is worth copying rather than inventing.
 *
 * The consequence that matters: the group's deploy authority is its THRESHOLD, and no single
 * key exists anywhere that can deploy on the group's behalf.
 */

export const Operation = { Call: 0, DelegateCall: 1 } as const;

const SAFE_TX_TYPES = {
  SafeTx: [
    { name: "to", type: "address" },
    { name: "value", type: "uint256" },
    { name: "data", type: "bytes" },
    { name: "operation", type: "uint8" },
    { name: "safeTxGas", type: "uint256" },
    { name: "baseGas", type: "uint256" },
    { name: "gasPrice", type: "uint256" },
    { name: "gasToken", type: "address" },
    { name: "refundReceiver", type: "address" },
    { name: "nonce", type: "uint256" },
  ],
};

const SAFE_ARTIFACT = "@safe-global/safe-contracts/contracts/Safe.sol:Safe";
const FACTORY_ARTIFACT =
  "@safe-global/safe-contracts/contracts/proxies/SafeProxyFactory.sol:SafeProxyFactory";
const CREATECALL_ARTIFACT = "@safe-global/safe-contracts/contracts/libraries/CreateCall.sol:CreateCall";

/** Deploy the Safe singleton + proxy factory + CreateCall (the deployment layer). */
export async function deploySafeSuite() {
  const [singletonF, factoryF, createCallF] = await Promise.all([
    ethers.getContractFactory(SAFE_ARTIFACT),
    ethers.getContractFactory(FACTORY_ARTIFACT),
    ethers.getContractFactory(CREATECALL_ARTIFACT),
  ]);
  const singleton = await singletonF.deploy();
  const factory = await factoryF.deploy();
  const createCall = await createCallF.deploy();
  await Promise.all([singleton.waitForDeployment(), factory.waitForDeployment(), createCall.waitForDeployment()]);
  return {
    singleton: await singleton.getAddress(),
    factory: await factory.getAddress(),
    createCall: await createCall.getAddress(),
    factoryContract: factory,
  };
}

/** Create a group Safe: owners + threshold. This IS the group's authority. */
export async function createGroupSafe(
  suite: Awaited<ReturnType<typeof deploySafeSuite>>,
  owners: string[],
  threshold: number,
) {
  const safeIface = (await ethers.getContractFactory(SAFE_ARTIFACT)).interface;
  const initializer = safeIface.encodeFunctionData("setup", [
    owners,
    threshold,
    ethers.ZeroAddress,
    "0x",
    ethers.ZeroAddress, // fallbackHandler — none
    ethers.ZeroAddress, // paymentToken
    0n, // payment
    ethers.ZeroAddress, // paymentReceiver
  ]);
  const saltNonce = BigInt("0x" + ethers.id("irl-coop-group-safe").slice(2, 18));
  const tx = await suite.factoryContract.createProxyWithNonce(suite.singleton, initializer, saltNonce);
  const receipt = await tx.wait();
  const ev = receipt!.logs
    .map((l: any) => {
      try {
        return suite.factoryContract.interface.parseLog(l);
      } catch {
        return null;
      }
    })
    .find((e: any) => e && e.name === "ProxyCreation");
  const addr = ev.args[0] as string;
  return await ethers.getContractAt(SAFE_ARTIFACT, addr);
}

/**
 * Execute a Safe transaction. Requires `signers` to meet the threshold — pass fewer and the
 * Safe refuses, which is the property the tests rely on.
 */
export async function execSafeTx(
  safe: any,
  signers: any[],
  { to, value = 0n, data = "0x", operation = Operation.Call }: { to: string; value?: bigint; data?: string; operation?: number },
) {
  const nonce = await safe.nonce();
  const domain = {
    chainId: (await ethers.provider.getNetwork()).chainId,
    verifyingContract: await safe.getAddress(),
  };
  const message = {
    to,
    value,
    data,
    operation,
    safeTxGas: 0n,
    baseGas: 0n,
    gasPrice: 0n,
    gasToken: ethers.ZeroAddress,
    refundReceiver: ethers.ZeroAddress,
    nonce,
  };
  const signed: { owner: string; sig: string }[] = [];
  for (const s of signers) {
    signed.push({ owner: await s.getAddress(), sig: await s.signTypedData(domain, SAFE_TX_TYPES, message) });
  }
  // Safe requires signatures ordered by ascending owner address.
  signed.sort((a, b) => (a.owner.toLowerCase() < b.owner.toLowerCase() ? -1 : 1));
  const packed = ethers.concat(signed.map((x) => x.sig));
  const tx = await safe.execTransaction(
    to,
    value,
    data,
    operation,
    0n, // safeTxGas
    0n, // baseGas
    0n, // gasPrice
    ethers.ZeroAddress,
    ethers.ZeroAddress,
    packed,
  );
  return await tx.wait();
}

/**
 * Deploy a contract with the Safe as the deployer (CREATE2, so the address is predictable).
 * Returns the address; the caller should then assert the deployment is what it claims.
 */
/** The address CreateCall reports — emitted from the SAFE, because the call is a delegatecall. */
function createdFrom(receipt: any, emitter: string): string | undefined {
  const iface = new ethers.Interface(["event ContractCreation(address indexed newContract)"]);
  for (const l of receipt.logs) {
    if (String(l.address).toLowerCase() !== emitter.toLowerCase()) continue; // delegatecall: the Safe emits
    try {
      const p = iface.parseLog(l);
      if (p && p.name === "ContractCreation") return p.args[0] as string;
    } catch {
      /* not ours */
    }
  }
  return undefined;
}

/**
 * Deploy a contract with the Safe as the deployer.
 *
 * The DELEGATECALL is what makes the Safe the deployer — the choice of opcode is NOT. Both
 * `performCreate` and `performCreate2` are `public` functions of the same library and both run
 * in the Safe's context, so the new contract's constructor sees the Safe as `msg.sender` either
 * way (asserted in both paths by the tests).
 *
 *   - omit `salt`  → plain CREATE. The address depends on the Safe's nonce and is read back from
 *     the `ContractCreation` event. This is the right default for a one-off group contract.
 *   - pass `salt`  → CREATE2. The address is a pure function of (Safe, salt, initCode), so it can
 *     be computed and checked BEFORE spending gas, and printed in config/UI before deployment.
 *     That is the only reason to prefer it, and it costs something: the address moves if any
 *     constructor argument changes, and repeating a salt reverts — a deliberate redeploy needs a
 *     fresh salt.
 */
export async function deployViaSafe(
  safe: any,
  signers: any[],
  suite: Awaited<ReturnType<typeof deploySafeSuite>>,
  { abi, bytecode, args = [], salt, value = 0n }: { abi: any[]; bytecode: string; args?: any[]; salt?: string; value?: bigint },
) {
  const cf = new ethers.ContractFactory(abi, bytecode);
  const initCode = ethers.concat([bytecode, cf.interface.encodeDeploy(args)]);
  const safeAddr = await safe.getAddress();
  const createCall = await ethers.getContractAt(CREATECALL_ARTIFACT, suite.createCall);

  const deterministic = typeof salt === "string";
  const data = deterministic
    ? createCall.interface.encodeFunctionData("performCreate2", [value, initCode, salt])
    : createCall.interface.encodeFunctionData("performCreate", [value, initCode]);

  const receipt = await execSafeTx(safe, signers, {
    to: suite.createCall,
    data,
    operation: Operation.DelegateCall,
  });

  if (deterministic) {
    const predicted = ethers.getCreate2Address(safeAddr, salt as string, ethers.keccak256(initCode));
    const actual = createdFrom(receipt, safeAddr);
    if (actual && actual.toLowerCase() !== predicted.toLowerCase()) {
      throw new Error(`deployed at ${actual} but CREATE2 predicted ${predicted}`);
    }
    return predicted;
  }
  const discovered = createdFrom(receipt, safeAddr);
  if (!discovered) throw new Error("no ContractCreation event from the Safe — did it really deploy?");
  return discovered;
}
