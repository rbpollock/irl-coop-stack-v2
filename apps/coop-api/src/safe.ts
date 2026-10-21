import type { FastifyInstance } from "fastify";
import { ethers } from "ethers";
import { verifyBearer } from "./verify-jwt";
import { PASSKEY_OWNER_ABI, PASSKEY_OWNER_BYTECODE } from "./passkey-artifact";

const SESSION_MODULE_IFACE = new ethers.Interface([
  // SessionKeyModule (contracts/contracts/modules/SessionKeyModule.sol)
  "function executeSpend(address target, uint256 value, bytes data, uint8 operation, address token, uint256 amountIn) returns (bool)",
]);

// ---------------------------------------------------------------------------
// Uncorrelatable Safe provisioning (Option 1: deterministic derivation, no
// storage). Safe proxy addresses are CREATE2-deterministic, so the address is
// derived from user-held material (saltNonce) — coop-api NEVER persists the
// identity → address mapping, and the request logs carry neither (pino logs
// method/url/status only; the salt travels in the request body).
// ---------------------------------------------------------------------------

// SafeProxy creation code as compiled by THIS workspace (safe-contracts 1.4.1-2
// sources, solc 0.8.20, optimizer runs 200). It MUST match the bytecode of the
// SafeProxy the on-chain factory deploys — the npm-published artifact uses
// different compiler settings and produces a different (wrong) address. Re-extract
// from contracts/artifacts after any Safe version or compiler setting change.
export const SAFE_PROXY_CREATION_CODE =
  "0x608060405234801561001057600080fd5b5060405161017238038061017283398101604081905261002f916100b9565b6001600160a01b0381166100945760405162461bcd60e51b815260206004820152602260248201527f496e76616c69642073696e676c65746f6e20616464726573732070726f766964604482015261195960f21b606482015260840160405180910390fd5b600080546001600160a01b0319166001600160a01b03929092169190911790556100e9565b6000602082840312156100cb57600080fd5b81516001600160a01b03811681146100e257600080fd5b9392505050565b607b806100f76000396000f3fe6080604052600080546001600160a01b0316632cf35bc960e11b823501602757808252602082f35b3682833781823684845af490503d82833e806040573d82fd5b503d81f3fea264697066735822122083bc9305af31ec563a6d8764752a4be4dd377f44da000f448e39692f01ea9e7464736f6c63430008140033";

export interface SafeParams {
  factory: string;
  singleton: string;
  initializer: string;
  saltNonce: bigint;
}

// SafeProxyFactory.createProxyWithNonce salt (safe-contracts 1.4.1-2):
//   keccak256(abi.encodePacked(keccak256(initializer), saltNonce))
// NOTE: the initializer (owners/threshold) is part of the salt — changing
// owners changes the predicted address.
function proxySalt(saltNonce: bigint, initializer: string): string {
  return ethers.keccak256(
    ethers.concat([ethers.keccak256(initializer), ethers.zeroPadValue(ethers.toBeHex(saltNonce), 32)])
  );
}

// Predict the Safe proxy address for createProxyWithNonce — pure CREATE2 math,
// no chain state required. Same inputs → same address everywhere, forever.
export function predictSafeAddress({ factory, singleton, initializer, saltNonce }: SafeParams): string {
  const deploymentData = ethers.concat([
    SAFE_PROXY_CREATION_CODE,
    ethers.zeroPadValue(singleton, 32), // abi.encodePacked(creationCode, uint256(uint160(singleton)))
  ]);
  return ethers.getCreate2Address(factory, proxySalt(saltNonce, initializer), ethers.keccak256(deploymentData));
}

// Safe.setup initializer (1-of-N owners for now; passkeys slot in as owners).
export function encodeSafeSetup(owners: string[], threshold: number): string {
  const iface = new ethers.Interface([
    "function setup(address[] owners, uint256 threshold, address to, bytes data, address fallbackHandler, address paymentToken, uint256 payment, address paymentReceiver)",
  ]);
  return iface.encodeFunctionData("setup", [
    owners,
    threshold,
    ethers.ZeroAddress,
    "0x",
    ethers.ZeroAddress,
    ethers.ZeroAddress,
    0,
    ethers.ZeroAddress,
  ]);
}

const FACTORY_IFACE = new ethers.Interface([
  "function createProxyWithNonce(address singleton, bytes initializer, uint256 saltNonce) returns (address proxy)",
]);

// Deploy a Safe proxy via the factory, funded by the backend signer (gas
// sponsorship). Returns the predicted address + tx hash; persists NOTHING.
export async function deploySafe(
  signer: ethers.Signer,
  params: Omit<SafeParams, "initializer">,
  owners: string[],
  threshold: number
): Promise<{ safeAddress: string; txHash: string }> {
  const initializer = encodeSafeSetup(owners, threshold);
  const predicted = predictSafeAddress({ ...params, initializer });
  const tx = await signer.sendTransaction({
    to: params.factory,
    data: FACTORY_IFACE.encodeFunctionData("createProxyWithNonce", [
      params.singleton,
      initializer,
      params.saltNonce,
    ]),
  });
  const receipt = await tx.wait();
  if (!receipt) throw new Error("deploy transaction failed");

  const code = await signer.provider!.getCode(predicted);
  if (code === "0x") throw new Error("predicted address has no code after deploy");
  return { safeAddress: predicted, txHash: receipt.hash };
}

// B-11 — deploy a member's PasskeyOwner: an EIP-1271 Safe owner bound to the member's
// registered WebAuthn P-256 key. The caller (the platform's sponsor EOA) only PAYS for
// this; it is never an owner of the Safe the owner contract is installed on.
export async function deployPasskeyOwner(
  signer: ethers.Signer,
  x: bigint,
  y: bigint,
): Promise<string> {
  const factory = new ethers.ContractFactory(
    PASSKEY_OWNER_ABI as unknown as ethers.InterfaceAbi,
    PASSKEY_OWNER_BYTECODE,
    signer,
  );
  // verifier = ZeroAddress -> the contract's constructor defaults to the EIP-7212
  // precompile (0x…0100), which Base has; a test chain can point it elsewhere.
  const owner = await factory.deploy(x, y, ethers.ZeroAddress);
  await owner.waitForDeployment();
  return await owner.getAddress();
}

function parseSaltNonce(raw: unknown): bigint {
  if (typeof raw !== "string" || !raw) throw new Error("saltNonce is required");
  const n = BigInt(raw);
  if (n < 1n || n > 2n ** 256n - 1n) throw new Error("saltNonce out of range");
  return n;
}

const OWNER_MANAGER_IFACE = new ethers.Interface([
  "function swapOwner(address prevOwner, address oldOwner, address newOwner)",
  "function getOwners() view returns (address[])",
]);
const SAFE_IFACE = new ethers.Interface([
  "function execTransaction(address to, uint256 value, bytes data, uint8 operation, uint256 safeTxGas, uint256 baseGas, uint256 gasPrice, address gasToken, address refundReceiver, bytes signatures)",
]);

export default async function safeRoutes(fastify: FastifyInstance): Promise<void> {
  const env = {
    rpcUrl: process.env.RPC_URL ?? "http://127.0.0.1:8545",
    factory: process.env.SAFE_PROXY_FACTORY_ADDRESS ?? "",
    singleton: process.env.SAFE_SINGLETON_ADDRESS ?? "",
    backendKey: process.env.SAFE_BACKEND_SIGNER_KEY ?? "",
    sessionModule: process.env.SAFE_SESSION_MODULE_ADDRESS ?? "",
    sessionKey: process.env.SESSION_KEY ?? "",
    jwtSecret: process.env.JWT_SECRET ?? "local-development-secret-irl-coop-v4",
  };

  // The default Safe config: owned 1-of-1 by the backend signer. Predict and
  // deploy MUST use the same initializer, or the addresses won't match.
  const defaultInitializer = (): string =>
    encodeSafeSetup([new ethers.Wallet(env.backendKey).address], 1);

  // Pure prediction: no chain call, nothing stored. Clients may compute this
  // locally too — the endpoint is a convenience oracle.
  fastify.post("/api/safe/predict", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    if (!env.factory || !env.singleton || !env.backendKey) {
      return reply.code(503).send({ error: "safe contracts not configured" });
    }
    try {
      const saltNonce = parseSaltNonce((request.body as any)?.saltNonce);
      const safeAddress = predictSafeAddress({
        factory: env.factory,
        singleton: env.singleton,
        initializer: defaultInitializer(),
        saltNonce,
      });
      const provider = new ethers.JsonRpcProvider(env.rpcUrl);
      let deployed = false;
      try {
        const code = await provider.getCode(safeAddress);
        deployed = code !== "0x";
      } catch {
        /* fallback to false on provider/connection error */
      }
      return reply.send({ safeAddress, deployed });
    } catch (err: any) {
      return reply.code(400).send({ error: err.message });
    }
  });

  // Real deployment via the backend signer (gas sponsorship). The address is
  // derived from the caller's saltNonce and is NOT persisted — no mapping
  // between this JWT's identity and the onchain account ever exists server-side.
  const deploy = async (request: any, reply: any) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    if (!env.factory || !env.singleton || !env.backendKey) {
      return reply.code(503).send({ error: "safe contracts not configured" });
    }
    try {
      const saltNonce = parseSaltNonce((request.body as any)?.saltNonce);
      const provider = new ethers.JsonRpcProvider(env.rpcUrl);
      const signer = new ethers.Wallet(env.backendKey, provider);
      const result = await deploySafe(signer, { factory: env.factory, singleton: env.singleton, saltNonce }, [signer.address], 1);
      request.log.info({ chainId: (await provider.getNetwork()).chainId }, "safe deployed");
      return reply.send({ ...result, message: "Safe deployed and initialized successfully" });
    } catch (err: any) {
      request.log.error({ err: err.message }, "safe deploy failed");
      return reply.code(500).send({ error: err.message });
    }
  };
  fastify.post("/api/safe/deploy", deploy);
  fastify.post("/api/onboard", deploy); // legacy alias

  // Sovereign handover: the backend signer, which currently owns the Safe
  // 1-of-1, renounces itself and installs a user-representing owner (e.g. a
  // PasskeyOwner EIP-1271 contract) as the new 1-of-1 owner. This is the
  // production face of the ownership transition proven at the contract level
  // in contracts/test/SafeOwnershipPasskey.ts: one Safe execTransaction ->
  // swapOwner(SENTINEL, backend, passkeyOwner), threshold unchanged (1).
  // The Safe remains deterministic-address and uncorrelatable; coop-api still
  // never persists the identity->address mapping.
  fastify.post("/api/safe/sovereign", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    // B-11: RETIRED. A Safe is now created passkey-owned from block zero
    // (provisioning.ensurePersonalSafe), so there is no backend-owned Safe to hand
    // over. This route can no longer touch ownership — keeping it live would be the
    // very hole it used to be (F1). Legacy backend-owned Safes need an explicit,
    // separate migration; until then this returns 410. The body below is dead code,
    // kept only as the reference for that migration.
    return reply.code(410).send({
      error: "gone",
      detail: "Safe ownership is passkey-native at creation; handover no longer exists",
    });
    if (!env.factory || !env.singleton || !env.backendKey) {
      return reply.code(503).send({ error: "safe contracts not configured" });
    }
    try {
      const { safeAddress, passkeyOwner, saltNonce } = request.body as {
        safeAddress?: unknown;
        passkeyOwner?: unknown;
        saltNonce?: unknown;
      };
      if (typeof safeAddress !== "string" || !ethers.isAddress(safeAddress)) {
        return reply.code(400).send({ error: "safeAddress required" });
      }
      if (typeof passkeyOwner !== "string" || !ethers.isAddress(passkeyOwner)) {
        return reply.code(400).send({ error: "passkeyOwner required (an EIP-1271 owner contract address)" });
      }
      const salt = parseSaltNonce(saltNonce);

      const provider = new ethers.JsonRpcProvider(env.rpcUrl);
      const backendSigner = new ethers.Wallet(env.backendKey, provider);
      const backendAddr = backendSigner.address;
      if (backendAddr.toLowerCase() === passkeyOwner.toLowerCase()) {
        return reply.code(400).send({ error: "passkeyOwner cannot be the backend signer" });
      }

      const safe = new ethers.Contract(safeAddress, OWNER_MANAGER_IFACE, provider);
      // Reject if this Safe isn't actually the backend-owned one we predicted for
      // this caller's salt — otherwise handover would touch someone else's Safe.
      const predicted = predictSafeAddress({
        factory: env.factory,
        singleton: env.singleton,
        initializer: defaultInitializer(),
        saltNonce: salt,
      });
      if (predicted.toLowerCase() !== safeAddress.toLowerCase()) {
        return reply.code(400).send({ error: "safeAddress does not match this saltNonce's predicted Safe" });
      }
      const code = await provider.getCode(safeAddress);
      if (code === "0x") {
        return reply.code(400).send({ error: "safe not deployed on this chain" });
      }

      const owners: string[] = await safe.getOwners();
      if (owners.length !== 1 || owners[0].toLowerCase() !== backendAddr.toLowerCase()) {
        return reply.code(400).send({ error: "Safe is not backend-owned 1-of-1; handover refuses" });
      }

      // The one action the Safe will execute: swapOwner(SENTINEL, backend, passkeyOwner).
      // prevOwner = SENTINEL_OWNERS (0x1) because the backend is the sole owner and
      // therefore the head of the owner linked list.
      const swapCalldata = OWNER_MANAGER_IFACE.encodeFunctionData("swapOwner", [
        "0x0000000000000000000000000000000000000001", // SENTINEL_OWNERS
        backendAddr,
        passkeyOwner,
      ]);

      // Safe 1.4.1 execTransaction — the backend is a plain EOA owner, so the
      // signatures blob is a single 65-byte ECDSA(r,s,v) over the EIP-712
      // safeTxHash, not the contract-owner static slot used for PasskeyOwner.
      const safeContract = new ethers.Contract(safeAddress, SAFE_IFACE, backendSigner);
      const nonce: bigint = await safeContract.nonce();
      const to = safeAddress; // the Safe executes swapOwner on itself
      const data = swapCalldata;
      const operation = 0; // Enum.Operation.Call
      const safeTxGas = 0n;
      const baseGas = 0n;
      const gasPrice = 0n;
      const gasToken = ethers.ZeroAddress;
      const refundReceiver = ethers.ZeroAddress;
      const safeTxHash = await safeContract.getTransactionHash(
        to, 0n, data, operation, safeTxGas, baseGas, gasPrice, gasToken, refundReceiver, nonce
      );

      const sig = backendSigner.signingKey.sign(ethers.getBytes(safeTxHash));
      // Safe 1.4.1 contract-owner reading order for sig: [r | s | v]; EOA sig is
      // compact r,s (32+32) + a final v byte in the legacy recovery-id form.
      const backendSig = ethers.concat([
        ethers.zeroPadValue(sig.r, 32),
        ethers.zeroPadValue(sig.s, 32),
        ethers.toBeHex(sig.v), // 27/28 style
      ]);

      const tx = await safeContract.execTransaction.staticCall(
        to, 0n, data, operation, safeTxGas, baseGas, gasPrice, gasToken, refundReceiver, backendSig
      );
      const receipt = await (await safeContract.execTransaction(
        to, 0n, data, operation, safeTxGas, baseGas, gasPrice, gasToken, refundReceiver, backendSig
      )).wait();
      if (!receipt) throw new Error("sovereign handover transaction failed");

      // Verify: the Safe is now owned 1-of-1 by the passkey owner.
      const newOwners: string[] = await new ethers.Contract(safeAddress, OWNER_MANAGER_IFACE, provider).getOwners();
      if (
        newOwners.length !== 1 ||
        newOwners[0].toLowerCase() !== passkeyOwner.toLowerCase()
      ) {
        return reply.code(500).send({ error: "handover executed but owner set did not change as expected" });
      }
      request.log.info({ chainId: (await provider.getNetwork()).chainId }, "safe handed to sovereign owner");
      return reply.send({
        safeAddress,
        oldOwner: backendAddr,
        newOwner: passkeyOwner,
        txHash: receipt.hash,
        message: "Safe ownership handed to the passkey/EIP-1271 owner; backend renounced",
      });
    } catch (err: any) {
      request.log.error({ err: err.message }, "safe sovereign failed");
      return reply.code(500).send({ error: err.message });
    }
  });

  // Session-key automation (the graph's "hot verb" act). The dashboard draws an
  // edge (accept a match, fund a Move, run-a-keeper) and calls here; the coop
  // signs as the session bot and drives the group Safe's SessionKeyModule, which
  // is a Safe-1.4.1 module enabled on that group Safe (budget + allow-list
  // enforced on-chain in SessionKeyModule, not here — this route only relays and
  // pays gas). Not an owner, cannot rename/steal; only a bounded daily spend.
  fastify.post("/api/safe/session/execute", async (request, reply) => {
    const claims = verifyBearer(request, reply);
    if (!claims) return;
    if (!env.sessionModule || !env.sessionKey) {
      return reply.code(503).send({ error: "safe session module not configured" });
    }
    try {
      const body = request.body as any;
      const target = body?.target;
      const token: string = body?.token ?? ethers.ZeroAddress;
      const amountIn: bigint = ethers.parseUnits(String(body?.amountIn ?? "0"), 6); // default USDC 6dp
      if (typeof target !== "string" || !ethers.isAddress(target)) {
        return reply.code(400).send({ error: "target required" });
      }
      const data: string = body?.data ?? "0x";
      const operation: number = body?.operation ?? 0;
      const value: bigint = ethers.parseEther(String(body?.value ?? "0"));

      const provider = new ethers.JsonRpcProvider(env.rpcUrl);
      const bot = new ethers.Wallet(env.sessionKey, provider);
      const module = new ethers.Contract(env.sessionModule, SESSION_MODULE_IFACE, bot);

      const ok = await module.executeSpend.staticCall(target, value, data, operation, token, amountIn);
      if (!ok) return reply.code(400).send({ error: "module dry-run rejected the spend (budget or allowlist)" });

      const tx = await module.executeSpend(target, value, data, operation, token, amountIn);
      const receipt = await tx.wait();
      request.log.info({ chainId: (await provider.getNetwork()).chainId }, "session spend executed");
      return reply.send({
        txHash: receipt?.hash,
        target,
        value: value.toString(),
        token,
        amountIn: amountIn.toString(),
        message: "session-key Safe spend executed via the group Safe",
      });
    } catch (err: any) {
      request.log.error({ err: err.message }, "safe session execute failed");
      return reply.code(500).send({ error: err.message });
    }
  });
}
