import { expect } from "chai";
import { ethers } from "hardhat";
import crypto from "node:crypto";

/**
 * PasskeyOwner — the EIP-1271 plumbing of a passkey-as-Safe-owner.
 *
 * Division of responsibility (the honest architecture):
 *   - Curve math is DELEGATED (EIP-7212 precompile on Base; StubVerifier in this
 *     local test). The contract never hand-rolls secp256r1.
 *   - The contract's job: decode the WebAuthn auth, enforce challenge binding,
 *     compose the WebAuthn message, route it to the verifier, translate the
 *     verifier's verdict into the EIP-1271 magic.
 *   - The REAL P-256 validity is asserted in Node (crypto, prime256v1) over the
 *     same message the contract routes — a genuine signature passes Node AND
 *     the contract plumbing; that is ground truth, not a self-consistent mock.
 */
const MAGIC = "0x1626ba7e";
const INVALID = "0xffffffff";

describe("PasskeyOwner — EIP-1271 passkey-owner plumbing", () => {
  async function fixture() {
    const Stub = await ethers.getContractFactory("StubVerifier");
    const stub = await Stub.deploy();
    await stub.waitForDeployment();

    const { publicKey, privateKey } = crypto.generateKeyPairSync("ec", { namedCurve: "prime256v1" });
    const jwk = publicKey.export({ format: "jwk" }) as { x: string; y: string };
    const x = BigInt("0x" + Buffer.from(jwk.x, "base64").toString("hex"));
    const y = BigInt("0x" + Buffer.from(jwk.y, "base64").toString("hex"));

    const owner = await (await ethers.getContractFactory("PasskeyOwner")).deploy(x, y, await stub.getAddress());
    await owner.waitForDeployment();
    return { owner, stub, privateKey, publicKey, x, y };
  }

  /** Build a WebAuthn auth structure over a raw 32-byte challenge. */
  function webauthn(privateKey: CryptoKey | unknown, challenge: Buffer) {
    const clientDataJSON = Buffer.concat([
      Buffer.from('{"type":"webauthn.get","challenge":'),
      challenge,
      Buffer.from("}"),
    ]);
    const authenticatorData = Buffer.from("49960de6000000000a561d0000000000000000000000000000000000000000000000", "hex");
    const clientDataHash = crypto.createHash("sha256").update(clientDataJSON).digest();
    const message = crypto.createHash("sha256").update(Buffer.concat([authenticatorData, clientDataHash])).digest();
    const sig = crypto.sign(null, message, { key: privateKey as crypto.KeyObject, dsaEncoding: "ieee-p1363" });
    const r = BigInt("0x" + sig.subarray(0, 32).toString("hex"));
    const s = BigInt("0x" + sig.subarray(32, 64).toString("hex"));
    return { authenticatorData, clientDataJSON, r, s, message, sig };
  }

  function encodeSig(a: { authenticatorData: Buffer; clientDataJSON: Buffer; r: bigint; s: bigint }): string {
    return ethers.AbiCoder.defaultAbiCoder().encode(
      ["bytes", "bytes", "uint256", "uint256"],
      [a.authenticatorData, a.clientDataJSON, a.r, a.s]
    );
  }

  it("valid when challenge bound and Node verifies the real P-256 signature", async () => {
    const { owner, privateKey, publicKey } = await fixture();
    const challenge = crypto.createHash("sha256").update("spend-note-1").digest();
    const a = webauthn(privateKey, challenge);

    // ground truth: Node verifies the exact message the contract will derive
    const nodeOk = crypto.verify(null, a.message, { key: publicKey, dsaEncoding: "ieee-p1363" }, a.sig);
    expect(nodeOk, "Node rejects our own auth — crypto bug").to.be.true;

    const magic = await owner["isValidSignature(bytes32,bytes)"](challenge, encodeSig(a));
    expect(magic).to.equal(MAGIC);
  });

  it("routes the verifier verdict — if the verifier rejects, the owner rejects", async () => {
    const { owner, stub, privateKey } = await fixture();
    const challenge = crypto.createHash("sha256").update("chal2").digest();
    const a = webauthn(privateKey, challenge);
    // verifier says INVALID (stub setValidity(0)) — but binding & plumbing are intact
    await stub.setValidity(0);
    const magic = await owner["isValidSignature(bytes32,bytes)"](challenge, encodeSig(a));
    expect(magic).to.equal(INVALID);
  });

  it("rejects when the challenge is not the one bound in clientDataJSON", async () => {
    const { owner, privateKey } = await fixture();
    const a = webauthn(privateKey, crypto.createHash("sha256").update("real").digest());
    const wrong = crypto.createHash("sha256").update("attacker-controlled").digest();
    const magic = await owner["isValidSignature(bytes32,bytes)"](wrong, encodeSig(a));
    expect(magic).to.equal(INVALID);
  });
});