// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@safe-global/safe-contracts/contracts/Safe.sol";
import "@safe-global/safe-contracts/contracts/proxies/SafeProxyFactory.sol";
// Safe's audited deployment library. Imported (not used) so its artifact exists: it is
// DELEGATECALLed by a Safe transaction, which is what makes the SAFE the deployer.
import "@safe-global/safe-contracts/contracts/libraries/CreateCall.sol";
