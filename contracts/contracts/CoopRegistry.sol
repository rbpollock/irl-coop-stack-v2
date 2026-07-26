// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title CoopRegistry
 * @dev Manages O(1) membership validation via Merkle roots and revocation mappings.
 */
contract CoopRegistry is Ownable {
    // Current state root of the membership Merkle Tree
    bytes32 public shardRoot;

    // Bitmask revocation mapping (O(1) invalidation)
    mapping(uint256 => bool) public revokedLeaves;

    event MembershipUpdated(bytes32 newRoot);
    event MemberRevoked(uint256 leafIndex);

    constructor() Ownable(msg.sender) {}

    /**
     * @dev Join the cooperative (Model A - Permissionless)
     * @param leaf The cryptographic leaf hash of the member
     */
    function joinGroup(bytes32 leaf) external payable {
        // Implementation logic placeholder for fee processing
        require(msg.value >= 0.05 ether, "Insufficient join fee");
        _appendMember(leaf);
    }

    /**
     * @dev Internal Merkle state update (called by batch router)
     */
    function updateShardRoot(bytes32 _newRoot) external onlyOwner {
        shardRoot = _newRoot;
        emit MembershipUpdated(_newRoot);
    }

    /**
     * @dev O(1) revocation
     */
    function revokeMember(uint256 leafIndex) external onlyOwner {
        revokedLeaves[leafIndex] = true;
        emit MemberRevoked(leafIndex);
    }

    function _appendMember(bytes32 leaf) internal {
        // Placeholder for off-chain/on-chain sync logic
    }
}
