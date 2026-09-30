// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title PasskeyOwner
 * @notice A Safe owner whose term is a WebAuthn passkey (P-256/secp256r1),
 *         made Safe-native through EIP-1271.
 *
 * Safe owner sets hold ECDSA addresses (secp256k1); a passkey is P-256 and
 * cannot be one. So the Safe's owner set holds THIS contract's address, and
 * the Safe validates the owner by calling back into this contract.
 *
 * Two selector surfaces, both implemented:
 *   - `isValidSignature(bytes32, bytes)` — the EIP-1271 standard form (magic
 *     0x1626ba7e), for any caller that checks the bytes32 form.
 *   - `isValidSignature(bytes, bytes)`  — the LEGACY SAFE form. Safe 1.4.1's
 *     `checkNSignatures` (v==0 contract-owner path, Safe.sol:315) calls
 *     `ISignatureValidator(owner).isValidSignature(data, contractSignature)`
 *     where its `data` is the full EIP-712 SafeTx preimage (bytes) and it
 *     expects the legacy magic 0x20c13b0b. Without this overload a passkey
 *     owner passes a standalone EIP-1271 check but is rejected by the Safe at
 *     dispatch — the two are different ABI selectors and Safe uses only the
 *     legacy one. We hash `data` to the Safe txHash and validate that.
 *
 * The actual P-256 (secp256r1) math is DELEGATED to a VERIFIER address:
 *   - default `0x000…0100` = the EIP-7212 precompile (Base),
 *   - the deployer may point it elsewhere (a test stub). The contract's job is
 *     the plumbing: decode the WebAuthn auth, enforce challenge-binding, and
 *     wrap it for the Safe — NOT the curve arithmetic (never hand-rolled here).
 *
 * CHALLENGE-BINDING: the clientDataJSON that was actually signed must physically
 * contain the challenge (`hash`), else the signature is replayable from an
 * earlier ceremony. The precompile proves "this key signed this message";
 * binding proves "this message is this Safe operation".
 */
contract PasskeyOwner {
    bytes4 internal constant MAGIC_VALUE = 0x1626ba7e; // standard EIP-1271
    bytes4 internal constant SAFE_MAGIC_VALUE = 0x20c13b0b; // Safe's legacy form
    bytes4 internal constant INVALID = 0xffffffff;

    address public immutable verifier;
    uint256 public immutable pubKeyX;
    uint256 public immutable pubKeyY;

    constructor(uint256 _pubKeyX, uint256 _pubKeyY, address _verifier) {
        pubKeyX = _pubKeyX;
        pubKeyY = _pubKeyY;
        verifier = _verifier == address(0) ? address(0x0000000000000000000000000000000000000100) : _verifier;
    }

    /// Standard EIP-1271: {bytes32, bytes}.
    function isValidSignature(bytes32 hash, bytes calldata signature)
        external
        view
        returns (bytes4)
    {
        return _verify(hash, signature) ? MAGIC_VALUE : INVALID;
    }

    /// Safe legacy dispatch: {bytes, bytes}. `data` is the Safe EIP-712 preimage;
    /// its keccak is the Safe transaction hash `dataHash` the passkey must sign.
    function isValidSignature(bytes calldata data, bytes calldata signature)
        external
        view
        returns (bytes4)
    {
        return _verify(keccak256(data), signature) ? SAFE_MAGIC_VALUE : INVALID;
    }

    function _verify(bytes32 hash, bytes memory signature) internal view returns (bool) {
        (bytes memory authenticatorData, bytes memory clientDataJSON, uint256 r, uint256 s) =
            abi.decode(signature, (bytes, bytes, uint256, uint256));

        // 1. Challenge binding: the signed clientDataJSON must contain `hash`.
        if (!contains(clientDataJSON, abi.encodePacked(hash))) return false;

        // 2. WebAuthn message to verify: SHA256(authenticatorData || SHA256(clientDataJSON)).
        bytes32 messageHash = sha256(abi.encodePacked(authenticatorData, sha256(clientDataJSON)));

        // 3. Delegate P-256 math to the verifier (EIP-7212 precompile).
        (bool ok, bytes memory ret) = verifier.staticcall(
            abi.encodeWithSignature("verify(uint256,uint256,uint256,uint256,bytes32)",
                                    r, s, pubKeyX, pubKeyY, messageHash)
        );
        return ok && ret.length >= 32 && abi.decode(ret, (uint256)) == 1;
    }

    /** Byte-substring search — the clientData envelope is JSON and large. */
    function contains(bytes memory haystack, bytes memory needle) internal pure returns (bool) {
        if (needle.length == 0) return true;
        if (needle.length > haystack.length) return false;
        uint256 max = haystack.length - needle.length;
        for (uint256 i = 0; i <= max; i++) {
            bool all = true;
            for (uint256 j = 0; j < needle.length; j++) {
                if (haystack[i + j] != needle[j]) { all = false; break; }
            }
            if (all) return true;
        }
        return false;
    }
}

interface ISignatureValidator {
    function isValidSignature(bytes memory, bytes memory) external view returns (bytes4);
}