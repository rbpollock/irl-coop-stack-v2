// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Safe 1.4.1 ModuleManager + OwnerManager surface used here.
interface ISafe {
    function execTransactionFromModule(
        address to,
        uint256 value,
        bytes calldata data,
        uint8 operation
    ) external returns (bool success);
    function enableModule(address module) external;
    function disableModule(address prevModule, address module) external;
    function isModuleEnabled(address module) external view returns (bool);
}

/**
 * @title SessionKeyModule
 * @notice Safe-1.4.1-native module letting a NON-OWNER "session key" drive a
 * group Safe, bounded — the seam for the coop's automation without ever making
 * the bot key a Safe owner.
 *
 * Hardened after an adversarial review (B-12). Changes from the first version,
 * each closing a way to drain the Safe or take it over:
 *   - **Default-deny allow-list.** A spend is REFUSED while the list is off.
 *     Previously "off" meant budget-only, i.e. any target at all.
 *   - **No delegatecall.** `operation` is forced to Call (0); the caller cannot
 *     run arbitrary code in the Safe's context (which would overwrite owners).
 *   - **The spend is DERIVED, not declared.** The cost is read from the calldata
 *     (the final 32-byte word of an ERC-20 transfer/approve/transferFrom) or the
 *     native value. Passing `token=0, value=0` beside an ERC-20 transfer can no
 *     longer spend at zero cost; a call whose amount we cannot read is refused.
 *   - **A session expires.** `validUntil` (0 = none) is set when the key is
 *     enabled; a leaked key stops working when it passes.
 *
 * The module must be ENABLED on the Safe (owner-governed) and drives it via
 * `execTransactionFromModule`, which Safe allows ONLY for an enabled module
 * (GS104). Disabling the module severs all authority instantly.
 */
contract SessionKeyModule {
    struct SessionConfig {
        address sessionKey; // EOA that may drive the Safe, within budget
        uint256 dailyLimit; // daily budget (native value or token units)
        uint256 spentToday; // spent this rolling day
        uint256 lastResetDay;
        uint256 validUntil; // unix seconds; 0 = no expiry
    }

    address public immutable SAFE;
    SessionConfig public config;

    // The allow-list. DENIED by default: a spend is refused until the owners arm
    // the list and put at least one target/selector on it.
    bool public listEnabled;
    mapping(address => bool) public whitelistedTargets; // whole-contract permission
    mapping(address => mapping(bytes4 => bool)) public whitelistedSelectors; // per-function

    event SessionKeyEnabled(address indexed safe, address sessionKey, uint256 dailyLimit, uint256 validUntil);
    event SpendRecorded(address indexed safe, uint256 amount, uint256 remainingLimit);
    event ListArmed(address indexed safe, bool armed);
    event WhitelistSet(address indexed safe, address target, bytes4 selector, bool allowed);

    error NotSafe();
    error NotSessionKey();
    error NoSessionKey();
    error DailyLimitExceeded();
    error NotAllowed(); // the list is off, or the target/selector is not on it
    error Expired();
    error BadOperation(); // only Call (0) is accepted
    error UnboundedCall(); // a call whose amount we cannot read from the calldata
    error BadCalldata();

    // ERC-20 selectors whose spender amount is the final word of the argument block.
    bytes4 private constant SEL_TRANSFER = 0xa9059cbb; // transfer(address,uint256)
    bytes4 private constant SEL_APPROVE = 0x095ea7b3; // approve(address,uint256)
    bytes4 private constant SEL_TRANSFER_FROM = 0x23b872dd; // transferFrom(address,address,uint256)

    constructor(address _safe) {
        require(_safe != address(0), "no safe");
        SAFE = _safe;
    }

    modifier onlySafe() {
        if (msg.sender != SAFE) revert NotSafe();
        _;
    }

    /** @dev Arm/disable the allow-list. Owner-governed (safe-only). */
    function setListEnabled(bool _on) external onlySafe {
        listEnabled = _on;
        emit ListArmed(SAFE, _on);
    }

    /**
     * @notice Whitelist a target (whole contract) OR a single selector on it.
     *        selector == 0x00000000 means the whole target is whitelisted.
     */
    function authorize(address _target, bytes4 _selector, bool _allow) external onlySafe {
        require(_target != address(0), "no target");
        if (_selector == bytes4(0)) {
            whitelistedTargets[_target] = _allow;
        } else {
            whitelistedSelectors[_target][_selector] = _allow;
        }
        emit WhitelistSet(SAFE, _target, _selector, _allow);
    }

    /** @dev Grant the session key its budget and expiry. Only callable BY the Safe. */
    function enableSessionKey(address _key, uint256 _dailyLimit, uint256 _validUntil) external onlySafe {
        if (_key == address(0) || _key == SAFE) revert NoSessionKey();
        config = SessionConfig({
            sessionKey: _key,
            dailyLimit: _dailyLimit,
            spentToday: 0,
            lastResetDay: block.timestamp / 1 days,
            validUntil: _validUntil
        });
        emit SessionKeyEnabled(SAFE, _key, _dailyLimit, _validUntil);
    }

    /** @dev Raise/lower the budget after setup (still owner-governed via the Safe). */
    function updateDailyLimit(uint256 _dailyLimit) external onlySafe {
        config.dailyLimit = _dailyLimit;
    }

    /** @dev Revoke the session key entirely. Owner-governed. */
    function clearSessionKey() external onlySafe {
        delete config;
    }

    /**
     * @notice Automation entrypoint — the session key EOA calls this directly.
     * @param target Contract/account the Safe will act on
     * @param value  Native value the Safe will move
     * @param data   Calldata forwarded to target; its amount bounds the spend
     */
    function executeSpend(
        address target,
        uint256 value,
        bytes calldata data,
        uint8 operation
    ) external returns (bool) {
        if (msg.sender != config.sessionKey) revert NotSessionKey();
        if (operation != 0) revert BadOperation(); // no delegatecall, ever
        if (config.validUntil != 0 && block.timestamp > config.validUntil) revert Expired();
        if (!listEnabled) revert NotAllowed(); // default-deny until armed
        if (!_allowed(target, data)) revert NotAllowed();

        _rollDay();

        uint256 cost = _costOf(value, data); // DERIVED from what is actually sent
        if (config.spentToday + cost > config.dailyLimit) revert DailyLimitExceeded();
        config.spentToday += cost;

        bool ok = ISafe(SAFE).execTransactionFromModule(target, value, data, 0);
        if (!ok) revert("safe call reverted");
        emit SpendRecorded(SAFE, cost, config.dailyLimit - config.spentToday);
        return ok;
    }

    /**
     * @dev The amount this call can move, read from the calldata. Unknown calls
     *      are refused rather than trusted, so a caller cannot understate the
     *      cost of an ERC-20 transfer (the old `amountIn` bypass).
     */
    function _costOf(uint256 value, bytes calldata data) internal pure returns (uint256) {
        if (data.length < 4) return value; // plain native transfer
        bytes4 sel = bytes4(data);
        if (sel == SEL_TRANSFER || sel == SEL_APPROVE) {
            if (data.length < 68) revert BadCalldata(); // selector + 2 words
        } else if (sel == SEL_TRANSFER_FROM) {
            if (data.length < 100) revert BadCalldata(); // selector + 3 words
        } else {
            revert UnboundedCall();
        }
        // The amount is the final 32-byte word of the argument block.
        bytes memory tail = data[data.length - 32:data.length];
        uint256 amount;
        assembly {
            amount := mload(add(tail, 0x20))
        }
        return amount;
    }

    /**
     * @notice Whether the call is permitted. A whole-target whitelist passes any
     *         selector; otherwise the exact selector must be whitelisted. A plain
     *         native transfer must name a whitelisted target.
     */
    function _allowed(address _target, bytes calldata _data) internal view returns (bool) {
        if (whitelistedTargets[_target]) return true;
        if (_data.length < 4) return false;
        return whitelistedSelectors[_target][bytes4(_data)];
    }

    function _rollDay() internal {
        uint256 day = block.timestamp / 1 days;
        if (config.lastResetDay < day) {
            config.spentToday = 0;
            config.lastResetDay = day;
        }
    }

    /// @notice Remaining daily budget.
    function getRemainingLimit(address) external view returns (uint256) {
        uint256 day = block.timestamp / 1 days;
        uint256 spent = (config.lastResetDay < day) ? 0 : config.spentToday;
        return config.dailyLimit - spent;
    }
}
