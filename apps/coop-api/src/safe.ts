import type { FastifyInstance } from "fastify";
import { ethers } from "ethers";
import { verifyBearer } from "./verify-jwt";

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

function parseSaltNonce(raw: unknown): bigint {
  if (typeof raw !== "string" || !raw) throw new Error("saltNonce is required");
  const n = BigInt(raw);
  if (n < 1n || n > 2n ** 256n - 1n) throw new Error("saltNonce out of range");
  return n;
}

export default async function safeRoutes(fastify: FastifyInstance): Promise<void> {
  const env = {
    rpcUrl: process.env.RPC_URL ?? "http://127.0.0.1:8545",
    factory: process.env.SAFE_PROXY_FACTORY_ADDRESS ?? "",
    singleton: process.env.SAFE_SINGLETON_ADDRESS ?? "",
    backendKey: process.env.SAFE_BACKEND_SIGNER_KEY ?? "",
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
}
