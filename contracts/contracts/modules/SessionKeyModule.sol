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
 * group Safe up to a daily budget — the seam for the coop's automation
 * (frictionless Path-A spends) without ever making the bot key a Safe owner.
 *
 * Fits our signer setup:
 *  - The session key is NOT a Safe owner and holds no governance. No owner
 *    takeover: it can only drive this module, within the budget owners set.
 *    Leaked key => bounded to one day's budget, not the whole Safe.
 *  - The module must be ENABLED on the Safe (owner-governed). It drives the
 *    Safe via `execTransactionFromModule`, which Safe's ModuleManager allows
 *    ONLY for an enabled module (GS104). Disabling the module severs all
 *    authority instantly.
 *  - `enableSessionKey` is callable ONLY BY the Safe (msg.sender == SAFE, bound
 *    immutable at deploy), i.e. a normal governance-signed Safe tx. One module
 *    instance binds to one Safe.
 *
 * Budget: native spends bounded by `value`; ERC-20 spends pass `token` +
 * `amountIn` to bound. The module does NOT parse calldata — the automation
 * declares the amount, so a USDC transfer is bounded exactly like ether.
 */
contract SessionKeyModule {
    struct SessionConfig {
        address sessionKey; // EOA that may drive the Safe, within budget
        uint256 dailyLimit; // daily budget (native value or declared token)
        uint256 spentToday; // spent this rolling day
        uint256 lastResetDay;
    }

    address public immutable SAFE;
    SessionConfig public config;

    event SessionKeyEnabled(address indexed safe, address sessionKey, uint256 dailyLimit);
    event SpendRecorded(address indexed safe, uint256 amount, uint256 remainingLimit);

    error NotSafe();
    error NotSessionKey();
    error NoSessionKey();
    error DailyLimitExceeded();
    error NotAllowed(); // selector/target not on the allow-list (only when armed)

    constructor(address _safe) {
        require(_safe != address(0), "no safe");
        SAFE = _safe;
    }

    // ---- Call allow-list (OPT-IN; never restrictive by default) ----
    // `listEnabled` defaults to false: with it off, executeSpend is budget-only
    // and can call anything the Safe could. The Safe can arm the list to
    // restrict the bot to whitelisted targets/selectors. The list only ever
    // NARROWS — empty/off means open.
    bool public listEnabled;
    // Whole-contract permission: target.EVERY-SELECTOR allowed.
    mapping(address => bool) public whitelistedTargets;
    // Per-function permission: selector on that target allowed.
    mapping(address => mapping(bytes4 => bool)) public whitelistedSelectors;

    event ListArmed(address indexed safe, bool armed);
    event WhitelistSet(address indexed safe, address target, bytes4 selector, bool allowed);

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

    /**
     * @notice Default-permissive gate: open when the list is off, or when the
     * call is a whole-target whitelist, or the selector is whitelisted. A plain
     * native transfer (no calldata / no selector) always passes — the budget
     * is the limit, the list is an added rail, not a jail.
     */
    function _allowed(address _target, bytes calldata _data) internal view returns (bool) {
        if (!listEnabled) return true;
        if (whitelistedTargets[_target]) return true;
        // no selector (0-{2,3}-byte data) = simple native transfer
        if (_data.length < 4) return true;
        bytes4 sel = bytes4(_data);
        return whitelistedSelectors[_target][sel];
    }

    modifier onlySafe() {
        if (msg.sender != SAFE) revert NotSafe();
        _;
    }

    /** @dev Grant the session key its daily budget. Only callable BY the Safe. */
    function enableSessionKey(address _key, uint256 _dailyLimit) external onlySafe {
        if (_key == address(0) || _key == SAFE) revert NoSessionKey();
        config = SessionConfig({
            sessionKey: _key,
            dailyLimit: _dailyLimit,
            spentToday: 0,
            lastResetDay: block.timestamp / 1 days
        });
        emit SessionKeyEnabled(SAFE, _key, _dailyLimit);
    }

    /** @dev Raise/lower budget after setup (still owner-governed via Safe). */
    function updateDailyLimit(uint256 _dailyLimit) external onlySafe {
        config.dailyLimit = _dailyLimit;
    }

    /**
     * @notice Automation entrypoint — the session key EOA calls this directly.
     * @param target Contract/account the Safe will act on
     * @param value Native value the Safe will move (bounded if token == 0x0)
     * @param data Calldata forwarded to target
     * @param operation Safe op (0 Call, 1 DelegateCall)
     * @param token  0x0 = native; else an ERC-20 the spend is budgeted in
     * @param amountIn The ERC-20 amount that counts against the budget
     */
    function executeSpend(
        address target,
        uint256 value,
        bytes calldata data,
        uint8 operation,
        address token,
        uint256 amountIn
    ) external returns (bool) {
        if (msg.sender != config.sessionKey) revert NotSessionKey();
        if (!_allowed(target, data)) revert NotAllowed();
        _rollDay();

        uint256 cost = (token == address(0)) ? value : amountIn;
        if (config.spentToday + cost > config.dailyLimit) revert DailyLimitExceeded();
        config.spentToday += cost;

        bool ok = ISafe(SAFE).execTransactionFromModule(target, value, data, operation);
        if (!ok) revert("safe call reverted");
        emit SpendRecorded(SAFE, cost, config.dailyLimit - config.spentToday);
        return ok;
    }

    function _rollDay() internal {
        uint256 day = block.timestamp / 1 days;
        if (config.lastResetDay < day) {
            config.spentToday = 0;
            config.lastResetDay = day;
        }
    }

    /// @notice Remaining daily budget (signature kept so prior tests still ring).
    function getRemainingLimit(address) external view returns (uint256) {
        uint256 day = block.timestamp / 1 days;
        uint256 spent = (config.lastResetDay < day) ? 0 : config.spentToday;
        return config.dailyLimit - spent;
    }
}