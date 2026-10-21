"use client"

// Register the member's WebAuthn passkey and hand its P-256 public key to coop-api, so
// the Safe the member gets is owned by THIS key (B-11). One key for signing in and for
// owning your account.

import { coopJson } from "@/lib/coop-api"

function hex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
}

function b64url(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf)
  let s = ""
  for (const b of bytes) s += String.fromCharCode(b)
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
}

/**
 * The public key comes back as an SPKI DER. For an EC (P-256) key it ends with
 * BIT STRING { 00 | 04 | X(32) | Y(32) }, so the uncompressed point is the last
 * 65 bytes and starts with 0x04.
 */
function pointFromSpki(spki: ArrayBuffer): { x: string; y: string } {
  const b = new Uint8Array(spki)
  const tail = b.slice(b.length - 65)
  if (tail[0] !== 0x04) throw new Error("not an uncompressed P-256 point")
  return { x: "0x" + hex(tail.slice(1, 33)), y: "0x" + hex(tail.slice(33, 65)) }
}

export interface PasskeyRegistration {
  registered: boolean
  credential_id: string
  safe_address: string | null
}

/**
 * Run the WebAuthn registration ceremony and record the credential with coop-api.
 * Rejects with a human message when the browser cannot participate.
 */
export async function registerPasskey(
  token: string | undefined,
  displayName: string,
  username: string,
): Promise<PasskeyRegistration> {
  if (!token) throw new Error("You need to be signed in first.")
  if (typeof window === "undefined" || !window.PublicKeyCredential) {
    throw new Error("This browser can't create a passkey.")
  }

  const challenge = crypto.getRandomValues(new Uint8Array(32))
  const userId = crypto.getRandomValues(new Uint8Array(16))

  const credential = (await navigator.credentials.create({
    publicKey: {
      challenge,
      rp: { name: "irl.coop", id: location.hostname },
      user: { id: userId, name: username, displayName },
      pubKeyCredParams: [{ type: "public-key", alg: -7 }], // ES256 / P-256
      authenticatorSelection: { userVerification: "preferred", residentKey: "preferred" },
      attestation: "none",
      timeout: 60_000,
    },
  })) as PublicKeyCredential | null

  if (!credential) throw new Error("Passkey setup was cancelled.")

  const response = credential.response as AuthenticatorAttestationResponse
  const spki =
    typeof response.getPublicKey === "function" ? response.getPublicKey() : null
  if (!spki) {
    throw new Error("This browser doesn't expose the passkey's public key. Try Chrome or Firefox.")
  }
  const { x, y } = pointFromSpki(spki)

  return coopJson<PasskeyRegistration>("/api/v1/me/passkey", token, {
    method: "POST",
    body: JSON.stringify({ credential_id: b64url(credential.rawId), x, y }),
  })
}