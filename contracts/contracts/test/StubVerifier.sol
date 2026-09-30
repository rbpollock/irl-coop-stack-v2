// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title StubVerifier
 * @notice TEST-ONLY, STATELESS stand-in for the EIP-7212 precompile (0x100).
 *
 * It must mirror the precompile's contract: a read-only `verify` callable under
 * STATICCALL. PasskeyOwner invokes it via staticcall; if this contract WRITES
 * state, the EVM write-protection panics the staticcall and PasskeyOwner sees
 * ok=false — exactly as if the cryptography were wrong. The real precompile is
 * stateless, so this stub must be too.
 *
 * It does NOT prove curve math (no fake green): it only arbitrates a pre-set
 * `validity` flag so the harness can exercise PasskeyOwner's plumbing in both
 * verdict directions. The REAL P-256 validity is grounded in Node (crypto,
 * prime256v1) in the same test file, and the real chain uses the EIP-7212
 * precompile. The messageHash that was routed is not observable here — the
 * test proves it transitively: Node recomputes the same WebAuthn message
 * compliant with the contract's rule, and the contract derives it from the
 * SAME authenticatorData/clientDataJSON bytes.
 *
 * Never ship this contract.
 */
contract StubVerifier {
    uint256 public validity = 1;

    function verify(uint256, uint256, uint256, uint256, bytes32)
        external
        view
        returns (uint256)
    {
        return validity;
    }

    function setValidity(uint256 v) external {
        validity = v;
    }
}