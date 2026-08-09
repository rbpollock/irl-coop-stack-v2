// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ShieldedPoolMock
 * @notice Mocks a ZK-Shielded UTXO pool (similar to Railgun) for asset shielding
 *         and Semaphore for private voting.
 */
contract ShieldedPoolMock {
    // ------------------------------------------------------------------------
    // RAILGUN MOCK: Asset Shielding
    // ------------------------------------------------------------------------
    uint256 public totalShieldedAssets;

    event ShieldedMint(bytes32 indexed commitment, uint256 amount);
    event ShieldedTransfer(bytes32 nullifier, bytes32 newCommitment);
    event UnshieldedWithdrawal(address indexed recipient, uint256 amount);

    function mockShieldDeposit(bytes32 commitment) external payable {
        totalShieldedAssets += msg.value;
        emit ShieldedMint(commitment, msg.value);
    }

    function mockUnshieldWithdrawal(
        bytes32 nullifier,
        address payable recipient,
        uint256 amount,
        bytes calldata /* zkProof */
    ) external {
        // Mock checking ZK proof
        require(address(this).balance >= amount, "Insufficient liquidity");
        totalShieldedAssets -= amount;
        recipient.transfer(amount);
        emit UnshieldedWithdrawal(recipient, amount);
    }

    // ------------------------------------------------------------------------
    // SEMAPHORE MOCK: Private Voting
    // ------------------------------------------------------------------------
    mapping(bytes32 => bool) public nullifiers;

    event VoteCast(uint256 indexed pollId, uint256 voteOption);

    function castPrivateVote(
        uint256 pollId,
        uint256 voteOption,
        bytes32 nullifierHash,
        bytes calldata /* zkProof */
    ) external {
        require(!nullifiers[nullifierHash], "Vote already cast");
        nullifiers[nullifierHash] = true;
        
        emit VoteCast(pollId, voteOption);
    }
}