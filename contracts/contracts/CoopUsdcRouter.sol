// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

/**
 * @title CoopUsdcRouter
 * @notice The address a fiat -> USDC rail sends to, and a ONE-WAY forwarder to a fixed
 *         destination. Deployed once per destination; the destination never changes.
 *
 * NOT a swap router. A rail delivers a plain ERC-20 `transfer`, and USDC has no transfer
 * hook, so NO code of ours runs on arrival — the tokens simply sit here until somebody calls
 * `sweep()`. That is inherent to ERC-20 and cannot be engineered away, so the design does not
 * pretend otherwise. What CAN be guaranteed is that they can only ever go to one place.
 *
 * Each rule below is the inverse of the CoopBatchRouter this supersedes, which had an owner,
 * took native ETH, and accepted value with no way to ever withdraw it.
 *
 *   NO ADMIN            no owner, no setter, no upgrade path. An admin is a party a state can
 *                       compel, and being uncompellable is the point of the whole design.
 *   IMMUTABLE TARGET    fixed at construction. `sweep` cannot be aimed anywhere else, so a
 *                       transient balance is not custody: it is a message in flight with one
 *                       address written on it. This is what keeps "the platform never
 *                       intermediates" true even though tokens rest here between two blocks.
 *   PERMISSIONLESS      anyone may forward; nobody may redirect. No keeper, no operator to
 *                       compel, no privileged caller to lose or to coerce.
 *   NO NATIVE VALUE     no receive/fallback, so ETH cannot be trapped here.
 */
contract CoopUsdcRouter {
    using SafeERC20 for IERC20;

    /// @notice the asset this router forwards (USDC on the deployment's chain)
    IERC20 public immutable token;
    /// @notice the ONE address every sweep goes to. Immutable, by construction.
    address public immutable destination;

    // NOT named `from`: the depositor is UNKNOWABLE here (a plain ERC-20 transfer carries
    // no calldata and USDC has no hook), so a field called `from` would be read as "the
    // payer" by anyone indexing this. The observer is whoever reported it; the payer is
    // known only off-chain, in payment_intent.
    event DepositNoted(address indexed observer, uint256 amount);
    event Swept(address indexed to, uint256 amount);
    event Rescued(address indexed token, address indexed to, uint256 amount);

    error ZeroAddress();
    error NothingToSweep();
    error UseSweep();
    error NothingToRescue();

    constructor(address token_, address destination_) {
        if (token_ == address(0) || destination_ == address(0)) revert ZeroAddress();
        token = IERC20(token_);
        destination = destination_;
    }

    /**
     * @notice Record an observation that a deposit landed. Emits the amount held.
     *
     * The rail will not call this (nothing calls into us — see the contract note), so an
     * off-chain watcher calls it after seeing the transfer, OR simply reads the balance. The
     * event is how the coop learns a payment arrived without asking the provider anything,
     * which matters because this provider's API cannot be polled at all.
     */
    function noteDeposit() external {
        emit DepositNoted(msg.sender, token.balanceOf(address(this)));
    }

    /// @notice Forward the entire balance to the immutable destination. Callable by ANYONE.
    function sweep() external {
        uint256 bal = token.balanceOf(address(this));
        if (bal == 0) revert NothingToSweep();
        token.safeTransfer(destination, bal);
        emit Swept(destination, bal);
    }

    /**
     * @notice Rescue a DIFFERENT ERC-20 sent here by mistake. It can only go to the immutable
     *         destination, so this cannot be used to divert anything anywhere.
     */
    function rescue(address other) external {
        if (other == address(token)) revert UseSweep();
        uint256 bal = IERC20(other).balanceOf(address(this));
        if (bal == 0) revert NothingToRescue();
        IERC20(other).safeTransfer(destination, bal);
        emit Rescued(other, destination, bal);
    }
}
