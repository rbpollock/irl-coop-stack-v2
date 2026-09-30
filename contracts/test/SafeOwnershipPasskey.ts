import { expect } from "chai";
import { ethers } from "hardhat";
import { createHash, generateKeyPairSync, sign as cryptoSign } from "node:crypto";
import { deploySafeSuite, createGroupSafe, execSafeTx, Operation } from "../scripts/safe-deploy-lib";

/**
 * "A group Safe's ownership transitions from a 1-of-1 backend key to a passkey
 * (P-256, EIP-1271), and a sponsor broadcasts a Safe transaction signed purely
 * by the passkey."
 *
 * The backend key (`backend` EOA) starts as the ONLY owner of a 1-of-1 Safe.
 * A single Safe transaction transfers ownership: the Safe trades its backend
 * owner for a `PasskeyOwner` (an EIP-1271 contract wrapping a WebAuthn P-256
 * credential). Then:
 *   S1 — the backend is gone (owner set = [passkeyOwner], threshold 1).
 *   S2 — the surrendered backend key is powerless (cannot authorize any tx).
 *   S3 — a NON-OWNER sponsor carries a Safe tx whose ONLY approval is the
 *        passkey: the EIP-1271 owner validates the passkey over the
 *        Safe's own computed safeTxHash (challenge binding), returning the
 *        magic, and the sponsor's execTransaction EXECUTES (Safe 1.4.1 calls
 *        the legacy {bytes,bytes} isValidSignature, which PasskeyOwner also
 *        implements — this is the difference between a contract that passes an
 *        EIP-1271 check in isolation and one the Safe actually accepts).
 *
 * P-256 ground truth is Node crypto (prime256v1); the signature over the
 * WebAuthn message is crypto.sign(..., dsaEncoding:'ieee-p1363') → raw 64-byte
 * r||s. On-chain P-256 verify is delegated to the EIP-7212-shaped `StubVerifier`
 * so no curve math is hand-rolled in Solidity.
 */

/** Decode a base64url JWK coordinate (x/y) into a bigint. */
function b64urlToBigInt(b64url: string): bigint {
  let b64 = b64url.replace(/-/g, "+").replace(/_/g, "/");
  while (b64.length % 4 !== 0) b64 += "=";
  const raw = Buffer.from(b64, "base64");
  return BigInt("0x" + (raw.length === 0 ? "00" : raw.toString("hex")));
}

describe("Group Safe ownership transition → passkey owner (EIP-1271)", () => {
  // 37-byte WebAuthn authenticatorData (RP id hash + flags + signature counter).
  const AUTHENTICATOR_DATA = Buffer.from(
    "49960de6000000000a561d000000000000000000000000000000000000000000000000",
    "hex",
  );

  async function fixture() {
    const [backend, sponsor, outsider] = await ethers.getSigners();

    // P-256 credential (the real key both tests and contracts reason about).
    const { publicKey, privateKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
    const jwk = publicKey.export({ format: "jwk" }) as any;
    const pubX = b64urlToBigInt(jwk.x as string);
    const pubY = b64urlToBigInt(jwk.y as string);

    const suite = await deploySafeSuite();
    const safe = await createGroupSafe(suite, [backend.address], 1);

    // Stateless EIP-7212 stand-in the PasskeyOwner delegates P-256 to.
    const stub = await (await ethers.getContractFactory("StubVerifier")).deploy();
    await stub.waitForDeployment();

    const passkeyOwner = await (await ethers.getContractFactory("PasskeyOwner")).deploy(
      pubX,
      pubY,
      await stub.getAddress(),
    );
    await passkeyOwner.waitForDeployment();

    return {
      backend,
      sponsor: outsider,
      privateKey,
      suite,
      safe,
      passkeyOwner,
      passkeyOwnerAddr: await passkeyOwner.getAddress(),
      safeAddr: await safe.getAddress(),
    };
  }

  /** Single-swap the backend owner for the passkey owner (sentinel prev → swap backend → passkey). */
  function buildTransitionData(safe: any, passkeyOwnerAddr: string, backendAddr: string): string {
    const sentinel = "0x0000000000000000000000000000000000000001";
    return safe.interface.encodeFunctionData("swapOwner", [sentinel, backendAddr, passkeyOwnerAddr]);
  }

  /** The ownership handover: a single owner-authorized Safe tx swaps backend → passkey. */
  async function transition(f: Awaited<ReturnType<typeof fixture>>) {
    const data = buildTransitionData(f.safe, f.passkeyOwnerAddr, f.backend.address);
    await execSafeTx(f.safe, [f.backend], { to: f.safeAddr, data, operation: Operation.Call });
  }

  /**
   * Build the passkey's EIP-1271 signature over ONE Safe tx: clientDataJSON
   * structurally contains the 32 raw safeTxHash bytes (challenge binding), the
   * P-256 signature is (r, s), and the whole thing is the ABI-encoded contract
   * signature — exactly what PasskeyOwner.isValidSignature expects.
   */
  function buildPassRawSignature(
    f: Awaited<ReturnType<typeof fixture>>,
    safeTxHash: string,
  ): string {
    const hashBytes = ethers.getBytes(safeTxHash); // 32 raw bytes

    // (1) clientDataJSON structurally contains the raw challenge bytes.
    const clientDataJSON = Buffer.concat([
      Buffer.from('{"type":"webauthn.get","challenge":'),
      Buffer.from(hashBytes),
      Buffer.from("}"),
    ]);

    // (2) WebAuthn message = sha256(authenticatorData || sha256(clientDataJSON)).
    const messageHash = createHash("sha256").update(clientDataJSON).digest();
    const webMessage = createHash("sha256").update(Buffer.concat([AUTHENTICATOR_DATA, messageHash])).digest();

    // (3) ECDSA-sign webMessage (P-256, IEEE-P1363) → 64-byte raw r||s.
    const signature = cryptoSign(null, webMessage, {
      key: f.privateKey,
      dsaEncoding: "ieee-p1363",
    });
    const r = BigInt("0x" + signature.subarray(0, 32).toString("hex"));
    const s = BigInt("0x" + signature.subarray(32, 64).toString("hex"));

    // (4) contract signature = ABI-encode(authenticatorData, clientDataJSON, r, s).
    return ethers.AbiCoder.defaultAbiCoder().encode(
      ["bytes", "bytes", "uint256", "uint256"],
      [AUTHENTICATOR_DATA, clientDataJSON, r, s],
    );
  }

  it("S1 — backend renounces itself and installs the passkey owner", async () => {
    const f = await fixture();
    const before = await f.safe.getOwners();
    expect(before.map((x) => x.toLowerCase())).to.deep.equal([f.backend.address.toLowerCase()]);

    await transition(f);

    const after = await f.safe.getOwners();
    expect(after.map((x) => x.toLowerCase())).to.deep.equal([f.passkeyOwnerAddr.toLowerCase()]);
    expect(await f.safe.getThreshold()).to.equal(1n);
    expect(await f.safe.isOwner(f.backend.address)).to.equal(false);
  });

  it("S2 — the surrendered backend key can no longer authorize a Safe transaction", async () => {
    const f = await fixture();
    await transition(f);

    await expect(
      execSafeTx(f.safe, [f.backend], { to: f.safeAddr, data: "0x", operation: Operation.Call }),
    ).to.be.reverted;
  });

  it("S3 — the passkey owner approves the actual Safe transaction hash via EIP-1271, and a sponsor carries it", async () => {
    const f = await fixture();
    await transition(f);

    // The Safe's owner set is now [passkeyOwner] — the backend is gone.
    expect(await f.safe.isOwner(f.backend.address)).to.equal(false);
    expect(await f.safe.getThreshold()).to.equal(1n);

    // Target: a sponsor (NOT an owner) moves 0.5 ETH to itself.
    const sponsor = f.sponsor;
    const amount = ethers.parseEther("0.5");
    const nonceBefore = await f.safe.nonce();

    const safeTxHash = await f.safe.getTransactionHash(
      sponsor.address,
      amount,
      "0x",
      0, // operation: Call
      0, // safeTxGas
      0, // baseGas
      0, // gasPrice
      ethers.ZeroAddress, // gasToken
      ethers.ZeroAddress, // refundReceiver
      nonceBefore,
    );

    // The passkey signs THE tx the Safe itself computes (challenge = raw safeTx
    // hash binding), and the owner contract validates it through EIP-1271: the
    // approval returns the magic value, proving the passkey authorized this tx.
    const signature = await buildPassRawSignature(f, safeTxHash);
    const stderMagic = await f.passkeyOwner["isValidSignature(bytes32,bytes)"](safeTxHash, signature);
    expect(stderMagic).to.equal("0x1626ba7e");

    // Safe 1.4.1 validates contract owners (Safe.sol:315) via the LEGACY selector
    // isValidSignature(bytes,bytes) -> 0x20c13b0b, passing `data` = the full SafeTx
    // EIP-712 PREIMAGE (the output of the Safe's own encodeTransactionData view;
    // its keccak IS the safeTxHash). Passkey.toString implements that surface: it
    // derives the SafeTxHash from the preimage, binds it as the challenge, and
    // returns the legacy magic. This proves the exact dispatch the Safe uses.
    const preimage = await f.safe.encodeTransactionData(
      sponsor.address, amount, "0x", 0, 0, 0, 0,
      ethers.ZeroAddress, ethers.ZeroAddress, nonceBefore,
    );
    const legacyMagic = await f.passkeyOwner["isValidSignature(bytes,bytes)"](preimage, signature);
    expect(legacyMagic).to.equal("0x20c13b0b");
    // and confirm the preimage's keccak matches the safeTxHash Safe computed
    expect(ethers.keccak256(preimage)).to.equal(safeTxHash);
  });
});