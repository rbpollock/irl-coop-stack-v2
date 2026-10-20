import { expect } from "chai";
import { ethers } from "hardhat";
import { createHash, generateKeyPairSync, sign as cryptoSign } from "node:crypto";
import { deploySafeSuite, createGroupSafe, Operation } from "../scripts/safe-deploy-lib";

/**
 * B-11 — "A member's Safe is passkey-owned AT CREATION."
 *
 * Contrast with SafeOwnershipPasskey.ts, which proves the *handover* (a backend-
 * owned Safe later swaps to a passkey). That is exactly the window B-11 removes:
 * here the Safe is BORN with the member's PasskeyOwner as its sole owner, and the
 * deployer (a plain EOA that pays the gas) is NEVER an owner.
 *
 * This is the contract-side acceptance criterion for B-11:
 *   C1 — the created Safe's owner set is [passkeyOwner]; the deployer is not an owner.
 *   C2 — a passkey-signed operation EXECUTES through a non-owner sponsor (so the
 *        platform can pay gas without holding any authority).
 *   C3 — without the passkey signature, the same sponsor cannot move funds.
 */

/** Decode a base64url JWK coordinate (x/y) into a bigint. */
function b64urlToBigInt(b64url: string): bigint {
  let b64 = b64url.replace(/-/g, "+").replace(/_/g, "/");
  while (b64.length % 4 !== 0) b64 += "=";
  const raw = Buffer.from(b64, "base64");
  return BigInt("0x" + (raw.length === 0 ? "00" : raw.toString("hex")));
}

describe("B-11: a Safe created passkey-owned (no backend-owned window)", () => {
  // 37-byte WebAuthn authenticatorData (RP id hash + flags + signature counter).
  const AUTHENTICATOR_DATA = Buffer.from(
    "49960de6000000000a561d000000000000000000000000000000000000000000000000",
    "hex",
  );

  async function fixture() {
    const [deployer, sponsor, outsider] = await ethers.getSigners();

    // The member's P-256 passkey credential.
    const { publicKey, privateKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
    const jwk = publicKey.export({ format: "jwk" }) as any;
    const pubX = b64urlToBigInt(jwk.x as string);
    const pubY = b64urlToBigInt(jwk.y as string);

    // P-256 verifier stand-in (EIP-7212 shaped) + the member's owner contract.
    const stub = await (await ethers.getContractFactory("StubVerifier")).deploy();
    await stub.waitForDeployment();
    const passkeyOwner = await (await ethers.getContractFactory("PasskeyOwner")).deploy(
      pubX,
      pubY,
      await stub.getAddress(),
    );
    await passkeyOwner.waitForDeployment();
    const passkeyOwnerAddr = await passkeyOwner.getAddress();

    // THE POINT: create the Safe with the PASSKEY as the only owner from block zero.
    // `deployer` sends the tx (and pays gas) but is not in the owner set.
    const suite = await deploySafeSuite();
    const safe = await createGroupSafe(suite, [passkeyOwnerAddr], 1);

    return {
      deployer,
      sponsor,
      outsider,
      privateKey,
      suite,
      safe,
      passkeyOwner,
      passkeyOwnerAddr,
      safeAddr: await safe.getAddress(),
    };
  }

  const passCallbackAddress = (f: any) => f.passkeyOwnerAddr;

  /** The EIP-1271 contract signature for ONE Safe tx (challenge-bound). */
  function buildPassSignature(f: any, safeTxHash: string): string {
    const hashBytes = ethers.getBytes(safeTxHash);
    const clientDataJSON = Buffer.concat([
      Buffer.from('{"type":"webauthn.get","challenge":'),
      Buffer.from(hashBytes),
      Buffer.from("}"),
    ]);
    const messageHash = createHash("sha256").update(clientDataJSON).digest();
    const webMessage = createHash("sha256")
      .update(Buffer.concat([AUTHENTICATOR_DATA, messageHash]))
      .digest();
    const signature = cryptoSign(null, webMessage, { key: f.privateKey, dsaEncoding: "ieee-p1363" });
    const r = BigInt("0x" + signature.subarray(0, 32).toString("hex"));
    const s = BigInt("0x" + signature.subarray(32, 64).toString("hex"));
    return ethers.AbiCoder.defaultAbiCoder().encode(
      ["bytes", "bytes", "uint256", "uint256"],
      [AUTHENTICATOR_DATA, clientDataJSON, r, s],
    );
  }

  /**
   * Safe 1.4.1 contract-owner signature slot (Safe.sol:301-315): 65 bytes =
   * [r(32)=owner address][s(32)=OFFSET within the signature blob to the length
   * word][v(1)=0x00], followed by the length-prefixed contract signature:
   * [len(32)][contractSig]. Safe reads contractSignatureLen at (blob + s) and the
   * signature at (blob + s + 0x20).
   */
  function packContractOwnerSig(ownerAddr: string, contractSig: string): string {
    const len = (contractSig.length - 2) / 2;
    const offset = 65; // the slot itself; the length word starts right after
    return ethers.concat([
      ethers.zeroPadValue(ownerAddr, 32),
      ethers.zeroPadValue(ethers.toBeHex(offset), 32),
      "0x00",
      ethers.zeroPadValue(ethers.toBeHex(len), 32),
      contractSig,
    ]);
  }

  it("C1 — the Safe's owner set is the passkey; the deployer is not an owner", async () => {
    const f = await fixture();
    const owners = (await f.safe.getOwners()).map((x: string) => x.toLowerCase());
    expect(owners).to.deep.equal([f.passkeyOwnerAddr.toLowerCase()]);
    expect(await f.safe.getThreshold()).to.equal(1n);
    // The platform/deployer EOA holds no authority over the member's Safe.
    expect(await f.safe.isOwner(f.deployer.address)).to.equal(false);
    expect(await f.safe.isOwner(f.sponsor.address)).to.equal(false);
  });

  it("C2 — a passkey-signed spend executes through a non-owner sponsor", async () => {
    const f = await fixture();

    // Fund the Safe so there is something to move.
    await f.deployer.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("1") });
    const amount = ethers.parseEther("0.5");
    const nonceBefore = await f.safe.nonce();

    const safeTxHash = await f.safe.getTransactionHash(
      f.sponsor.address, amount, "0x", 0, 0, 0, 0, ethers.ZeroAddress, ethers.ZeroAddress, nonceBefore,
    );
    const contractSig = buildPassSignature(f, safeTxHash);
    const packed = packContractOwnerSig(f.passkeyOwnerAddr, contractSig);

    const before = await ethers.provider.getBalance(f.sponsor.address);
    await f.safe.connect(f.sponsor).execTransaction(
      f.sponsor.address, amount, "0x", 0, 0, 0, 0, ethers.ZeroAddress, ethers.ZeroAddress, packed,
    );
    const after = await ethers.provider.getBalance(f.sponsor.address);
    expect(after).to.be.greaterThan(before); // sponsor received the 0.5 ETH
    expect(await f.safe.nonce()).to.equal(nonceBefore + 1n);
  });

  it("C3 — without the passkey signature the sponsor cannot move funds", async () => {
    const f = await fixture();
    await f.deployer.sendTransaction({ to: f.safeAddr, value: ethers.parseEther("1") });

    // Empty signature blob (or a bogus one) — the passkey owner will not validate.
    const bogus = packContractOwnerSig(f.passkeyOwnerAddr, "0x" + "00".repeat(32));
    await expect(
      f.safe.connect(f.sponsor).execTransaction(
        f.sponsor.address, ethers.parseEther("0.5"), "0x", 0, 0, 0, 0, ethers.ZeroAddress, ethers.ZeroAddress, bogus,
      ),
    ).to.be.reverted;
  });
});