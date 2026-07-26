import { Wallet } from "ethers";
import * as crypto from "crypto";

// ============================================================================
// 1. ECDSA MOCK SIGNER (Standard Ethereum / Web2 Auth Bridge Helper)
// ============================================================================
export interface ECDSASigner {
  address: string;
  signMessage: (message: string) => Promise<string>;
}

export function createECDSASigner(privateKey?: string): ECDSASigner {
  const wallet = privateKey ? new Wallet(privateKey) : Wallet.createRandom();
  return {
    address: wallet.address,
    signMessage: async (msg: string) => wallet.signMessage(msg),
  };
}

// ============================================================================
// 2. WEBAUTHN / SECP256R1 MOCK SIGNER (Biometric Secure Enclave Simulator)
// ============================================================================
export interface WebAuthnKeyPair {
  publicKey: {
    x: string; // Hex P-256 x coordinate
    y: string; // Hex P-256 y coordinate
  };
  credentialId: string;
  signChallenge: (challengeHex: string) => {
    r: string; // Signature component R
    s: string; // Signature component S
    authenticatorDataHex: string;
    clientDataJSON: string;
  };
}

export function generateWebAuthnKeyPair(): WebAuthnKeyPair {
  // Generate native EC P-256 (prime256v1) keypair
  const ec = crypto.generateKeyPairSync("ec", {
    namedCurve: "prime256v1",
    publicKeyEncoding: { type: "spki", format: "pem" },
    privateKeyEncoding: { type: "pkcs8", format: "pem" },
  });

  // Extract public key coordinates x, y from SPKI DER encoding
  const pubKeyObject = crypto.createPublicKey(ec.publicKey);
  const pubKeyBuffer = pubKeyObject.export({ type: "spki", format: "der" });
  
  // The P-256 uncompressed public key coordinates are located at the end of the DER SPKI structure
  // For prime256v1, standard SPKI DER wraps a 65-byte uncompressed public key (0x04 + 32-byte X + 32-byte Y) at offset 26
  const xOffset = pubKeyBuffer.length - 64;
  const x = pubKeyBuffer.subarray(xOffset, xOffset + 32).toString("hex");
  const y = pubKeyBuffer.subarray(xOffset + 32).toString("hex");

  const credentialId = crypto.randomBytes(32).toString("hex");

  return {
    publicKey: { x: "0x" + x, y: "0x" + y },
    credentialId,
    signChallenge: (challengeHex: string) => {
      const challengeBuffer = Buffer.from(challengeHex.replace(/^0x/, ""), "hex");

      // Mock W3C clientDataJSON and authenticatorData
      const clientDataJSON = JSON.stringify({
        type: "webauthn.get",
        challenge: challengeBuffer.toString("base64url"),
        origin: "https://app.irl.coop",
        crossOrigin: false,
      });

      const clientDataJSONHash = crypto.createHash("sha256").update(clientDataJSON).digest();
      const authenticatorData = crypto.randomBytes(37); // Standard 37-byte AuthData
      
      // Compute the signature payload: Keccak256(authenticatorData + sha256(clientDataJSON))
      const signaturePayload = Buffer.concat([authenticatorData, clientDataJSONHash]);

      // Sign the payload using P-256 ECDSA
      const sign = crypto.createSign("sha256");
      sign.update(signaturePayload);
      const derSignature = sign.sign(ec.privateKey);

      // Parse DER signature to extract R and S (using basic DER asn1 offsets)
      // DER Format: 0x30 + length + 0x02 + length_r + R + 0x02 + length_s + S
      const rLength = derSignature[3];
      const rOffset = 4;
      let rBuffer = derSignature.subarray(rOffset, rOffset + rLength);
      
      // Trim zero-padding if present due to ASN1 integer sign-bit rules
      if (rBuffer[0] === 0x00) rBuffer = rBuffer.subarray(1);

      const sOffset = rOffset + rLength + 2;
      const sLength = derSignature[sOffset - 1];
      let sBuffer = derSignature.subarray(sOffset, sOffset + sLength);
      if (sBuffer[0] === 0x00) sBuffer = sBuffer.subarray(1);

      return {
        r: "0x" + rBuffer.toString("hex").padStart(64, "0"),
        s: "0x" + sBuffer.toString("hex").padStart(64, "0"),
        authenticatorDataHex: "0x" + authenticatorData.toString("hex"),
        clientDataJSON,
      };
    },
  };
}
