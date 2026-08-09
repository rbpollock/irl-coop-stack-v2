// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SessionKeyModule
 * @notice Manages session keys and daily spending limits for frictionless Path A transactions.
 */
contract SessionKeyModule {
    struct SessionConfig {
        address sessionKey;
        uint256 dailyLimit;
        uint256 spentToday;
        uint256 lastResetDay;
    }
    
    mapping(address => SessionConfig) public safeSessions;

    event SessionKeyEnabled(address indexed safe, address sessionKey, uint256 dailyLimit);
    event SpendRecorded(address indexed safe, uint256 amount, uint256 remainingLimit);

    modifier onlySafe() {
        // In a production environment, this asserts msg.sender is the Safe proxy
        _;
    }

    /**
     * @notice Enables a session key with a specific daily limit
     */
    function enableSessionKey(address _key, uint256 _dailyLimit) external onlySafe {
        safeSessions[msg.sender] = SessionConfig({
            sessionKey: _key,
            dailyLimit: _dailyLimit,
            spentToday: 0,
            lastResetDay: block.timestamp / 1 days
        });
        emit SessionKeyEnabled(msg.sender, _key, _dailyLimit);
    }

    /**
     * @notice Checks if a spend is authorized and records it
     * @dev Called by the Safe proxy during transaction validation
     */
    function checkAndRecordSpend(address safe, uint256 amount) external {
        SessionConfig storage config = safeSessions[safe];
        require(config.sessionKey != address(0), "No active session key");

        uint256 currentDay = block.timestamp / 1 days;
        if (config.lastResetDay < currentDay) {
            config.spentToday = 0;
            config.lastResetDay = currentDay;
        }

        require(config.spentToday + amount <= config.dailyLimit, "Daily spending limit exceeded");
        config.spentToday += amount;

        emit SpendRecorded(safe, amount, config.dailyLimit - config.spentToday);
    }
    
    /**
     * @notice Fetch remaining limit for a given safe
     */
    function getRemainingLimit(address safe) external view returns (uint256) {
        SessionConfig memory config = safeSessions[safe];
        uint256 currentDay = block.timestamp / 1 days;
        if (config.lastResetDay < currentDay) {
            return config.dailyLimit;
        }
        return config.dailyLimit - config.spentToday;
    }
}