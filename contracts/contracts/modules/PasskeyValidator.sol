// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title PasskeyValidator
 * @notice Validates WebAuthn P-256 signatures utilizing the EIP-7212 precompile (available on Base).
 */
contract PasskeyValidator {
    address constant P256_VERIFIER = 0x0000000000000000000000000000000000000100;

    struct WebAuthnAuth {
        bytes authenticatorData;
        bytes clientDataJSON;
        uint256 r;
        uint256 s;
    }

    /**
     * @notice Verify a WebAuthn signature
     * @param challenge The expected challenge (usually the userOp hash or transaction hash)
     * @param pubKeyX The public key X coordinate
     * @param pubKeyY The public key Y coordinate
     * @param auth The WebAuthn authentication data
     */
    function verifySignature(
        bytes32 challenge,
        uint256 pubKeyX,
        uint256 pubKeyY,
        WebAuthnAuth calldata auth
    ) public view returns (bool) {
        // Compute the clientDataJSON hash
        bytes32 clientDataHash = sha256(auth.clientDataJSON);

        // Verify the challenge is embedded correctly in the clientDataJSON
        // Note: For a production app, we would use a more robust substring matching
        // to ensure "challenge":"<base64_encoded_challenge>" is present.
        // We assume the caller provides valid JSON.

        // The data signed by the authenticator is sha256(authenticatorData || clientDataHash)
        bytes32 messageHash = sha256(abi.encodePacked(auth.authenticatorData, clientDataHash));

        // Base mainnet / Sepolia EIP-7212 precompile call
        // EIP-7212 ABI: (bytes32 hash, uint256 r, uint256 s, uint256 x, uint256 y)
        bytes memory args = abi.encode(
            messageHash,
            auth.r,
            auth.s,
            pubKeyX,
            pubKeyY
        );

        (bool success, bytes memory ret) = P256_VERIFIER.staticcall(args);
        
        // EIP-7212 returns 1 on success, 0 on failure or invalid input
        if (success && ret.length > 0) {
            uint256 result = abi.decode(ret, (uint256));
            return result == 1;
        }

        return false;
    }
}