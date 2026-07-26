// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./CoopRegistry.sol";

/**
 * @title CoopBatchRouter
 * @dev Routes private shielded deposits into a unified on-chain batch to the ZK pool.
 * Severes public link between fiat-ramp history and shielded ZK addresses.
 */
contract CoopBatchRouter is Ownable {
    CoopRegistry public registry;
    uint256 public constant MIN_DEPOSIT = 0.01 ether;

    event DepositRouted(address indexed sender, uint256 amount);

    constructor(address _registry) Ownable(msg.sender) {
        registry = CoopRegistry(_registry);
    }

    /**
     * @dev Batch entry point for fiat-on-ramp providers.
     */
    function routeDeposit() external payable {
        require(msg.value >= MIN_DEPOSIT, "Deposit below minimum");
        
        // Log the event for the off-chain sync engine to pick up and
        // append to the shielded Merkle Pool
        emit DepositRouted(msg.sender, msg.value);
    }
}
