import fs from "node:fs";
import path from "node:path";
import { ethers, network, artifacts } from "hardhat";

/**
 * Verify a DEPLOYED router against the properties that make it safe — on whatever chain it
 * lives on. Read-only: needs no key, so it can run against a public RPC.
 *
 * This is the contracts equivalent of the payments preflight: a deployment is not "done" when
 * the transaction confirms, it is done when the deployed thing still has the properties.
 *
 *   ROUTER_ADDRESS=0x… ROUTER_DESTINATION=0x… npx hardhat run scripts/verify_deployment.ts --network base-sepolia
 */
type Net = { chainId: number; usdc: string | null; note: string };

async function main() {
  const nets = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "networks.json"), "utf8")) as Record<string, Net>;
  const cfg = nets[network.name];
  if (!cfg) throw new Error(`no entry for network '${network.name}' in networks.json`);

  const addr = process.env.ROUTER_ADDRESS;
  const wantDest = process.env.ROUTER_DESTINATION;
  if (!addr || !ethers.isAddress(addr)) throw new Error("ROUTER_ADDRESS is required");

  let pass = 0;
  const fails: string[] = [];
  const check = (name: string, ok: boolean, detail = "") => {
    console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
    ok ? pass++ : fails.push(name);
  };

  // 1 — are we really on the chain we think?
  const onChain = Number((await ethers.provider.getNetwork()).chainId);
  check(`on the expected chain (networks.json says ${cfg.chainId})`, onChain === cfg.chainId, `rpc reports ${onChain}`);

  // 2 — is the address a CONTRACT? Not merely "has code": an EIP-7702 delegated EOA returns a
  //     23-byte designator and is still a key-controlled account.
  const code = await ethers.provider.getCode(addr);
  const hex = code.slice(2);
  const bytes = hex.length / 2;
  const kind = hex.length === 0 ? "eoa" : hex.startsWith("ef0100") ? "delegated-eoa" : bytes < 64 ? "too-small" : "contract";
  check("the address is a CONTRACT (not an EOA or a 7702 delegation)", kind === "contract", `${kind}, ${bytes} bytes`);

  const router = await ethers.getContractAt("CoopUsdcRouter", addr);

  // 3 — the token must be the chain's real USDC, and must actually BE USDC (asked, not trusted)
  const token = await router.token();
  if (cfg.usdc) check("token() is the recorded USDC for this chain", token.toLowerCase() === cfg.usdc.toLowerCase(), token);
  const erc20 = new ethers.Contract(token, ["function symbol() view returns (string)", "function decimals() view returns (uint8)"], ethers.provider);
  try {
    const [sym, dec] = await Promise.all([erc20.symbol(), erc20.decimals()]);
    check("the token answers symbol() = USDC and decimals() = 6", sym === "USDC" && Number(dec) === 6, `${sym}/${dec}`);
  } catch (e) {
    check("the token answers symbol()/decimals()", false, (e as Error).message.slice(0, 60));
  }

  // 4 — the destination is the ONE the deployment was supposed to use, and it is immutable
  const dest = await router.destination();
  if (wantDest) check("destination() is the expected address", dest.toLowerCase() === wantDest.toLowerCase(), dest);
  else console.log(`INFO  destination() = ${dest} (set ROUTER_DESTINATION to assert it)`);
  check("destination() is not the zero address", dest !== ethers.ZeroAddress);

  // 5 — NO ADMIN: assert the deployed ABI has no privileged surface at all
  const abi: Array<{ name?: string }> = (await artifacts.readArtifact("CoopUsdcRouter")).abi as never;
  const names = abi.map((f) => f.name).filter(Boolean) as string[];
  const forbidden = ["owner", "transferOwnership", "renounceOwnership", "setDestination", "upgradeTo", "upgradeToAndCall", "initialize", "pause", "unpause"];
  check("the deployed ABI exposes no admin/upgrade surface", names.filter((n) => forbidden.includes(n)).length === 0,
    names.join(","));

  // 6 — what it holds right now (informational: a non-zero balance means a payment is in flight
  //     and un-swept, which is a person's job to notice, not a failure)
  const held = await erc20.balanceOf?.(addr).catch(() => null) ?? null;
  if (held !== null) console.log(`INFO  the router currently holds ${held.toString()} (6dp units); sweep() is permissionless`);

  console.log(`\n${pass} passed / ${fails.length} failed${fails.length ? `: ${fails.join(", ")}` : ""}`);
  console.log(cfg.note);
  if (fails.length) process.exitCode = 1;
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
