// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title DeployerProbe
/// @notice Records who deployed it, so a test can prove a deployment was made BY the group's
/// Safe rather than by an operator key. Test-only; carries no authority.
contract DeployerProbe {
    address public immutable deployer;
    uint256 public immutable valueSent;
    address public immutable arg;

    constructor(address arg_) payable {
        deployer = msg.sender;
        valueSent = msg.value;
        arg = arg_;
    }
}
