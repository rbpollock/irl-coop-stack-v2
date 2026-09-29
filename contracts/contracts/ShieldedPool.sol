// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IShieldedPoolVerifier
 * @notice The pluggable proof-check seam. P1 ships a NO-OP verifier (architecture
 *         exercised, no crypto yet); P2 replaces it with a real Groth16/PLONK
 *         verifier. The pool only ever calls verifySpend() — it does not know or
 *         care which proving system backs it, so the pool contract does not change
 *         when the crypto lands.
 *
 * Off-chain model (plan §8): on a spend, a permissionless relayer verifies the
 * Groth16 proof off-chain and submits only a nullifier + new root + command to the
 * pool. The pool enforces the invariants that MUST be on-chain — nullifier
 * uniqueness and root state — and accepts a "verified" command only if the verifier
 * admits it. A NoopVerifier (P1) admits everything; that is correct ONLY until P2
 * wires the real verifier, and the plan pages say so. The no-op is the deliberate
 * P1 state so the pool + commit-on-chain spine is built and tested before the
 * cryptography exists.
 */
interface IShieldedPoolVerifier {
    /// @return true iff the proof attests conservation + existence against the root.
    function verifySpend(
        bytes32 oldRoot,
        bytes32[] calldata newCommitments,
        bytes32[] calldata inputNullifiers,
        bytes calldata proof
    ) external view returns (bool);
}

/**
 * @title NoopVerifier
 * @notice Accepts every proof. P1 ONLY. Replaced by the real Groth16 verifier at
 *         P2. Marked NOOP so no one mistakes this for production and it is never
 *         deployed past the local-node/P1 gate.
 */
contract NoopVerifier is IShieldedPoolVerifier {
    bool public constant isNOOP = true;

    function verifySpend(
        bytes32,
        bytes32[] calldata,
        bytes32[] calldata,
        bytes calldata
    ) external pure override returns (bool) {
        return true; // NO-OP — real proof check arrives with P2
    }
}

/**
 * @title RejectingVerifier
 * @notice ALWAYS returns false. Used by the P1 integration test to prove the seam
 *         is real: a proof-checker that rejects must make the pool revert. This is
 *         a test fixture, not a deployable verifier — it never admits a proof.
 */
contract RejectingVerifier is IShieldedPoolVerifier {
    bool public constant isNOOP = false;

    function verifySpend(
        bytes32,
        bytes32[] calldata,
        bytes32[] calldata,
        bytes calldata
    ) external pure override returns (bool) {
        return false; // always reject — proves the pool refuses unverified input
    }
}

/// Minimal ERC20 surface; the repo ships no OpenZeppelin in contracts/, so we
/// avoid the dependency and only call what a USDC token guarantees.
interface IERC20Minimal {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address who) external view returns (uint256);
}

/**
 * @title ShieldedPool
 * @notice A minimal, self-contained shielded UTXO pool: commitment tree + nullifier
 *         set + USDC in/out + pluggable proof verification. REPLACES
 *         ShieldedPoolMock as the P1 artifact. Same API shape where practical so the
 *         mock's callers tests find-and-replace. Holds NO redeemable balance — only
 *         commitments (a note is a value in this pool's ledger, not a token it holds
 *         on behalf of a user). No OpenZeppelin; fixed-depth keccak Merkle tree.
 *
 * PLAN (§1a §8):
 *   - commitments: fixed-depth (32) keccak256 Merkle tree. The ROOT is the on-chain
 *     state; the pool never stores a user balance or a holder address publicly.
 *   - nullifier set: spend/redeem revert if already spent (no double-spend).
 *   - authorization: NOT in-circuit (all-Safe, §1a). The spend takes a verifier
 *     proof only; Safe-mandate/authorization is settled off-chain/dictated.
 *   - USDC in/out. The off-chain verify + commit-on-chain seam (§8).
 */
contract ShieldedPool {
    // ------------------------------------------------------------------ state
    address public usdc;          // USDC token (Base mainnet USDC at deploy)
    uint256 public constant TREE_DEPTH = 32;
    bool public paused;

    // Merkle tree.
    uint256[TREE_DEPTH] public zeros;     // zero-node hash at each depth
    uint256[TREE_DEPTH] public frontier;  // fill state for incremental insert
    uint256 public root;                  // current root (chain state)
    uint256 public nextIndex;             // leaves inserted so far

    // nullifiers.
    mapping(bytes32 => bool) public nullifiers;

    IShieldedPoolVerifier public verifier;

    // ------------------------------------------------------------------ events
    event ShieldedDeposit(bytes32 indexed commitment, uint256 amount);
    event ShieldedSpend(bytes32 indexed inputNullifier, bytes32 outputCommitment, uint256 issuanceAmount);
    event UnshieldedWithdrawal(address indexed recipient, uint256 amount);
    event RootUpdated(uint256 newRoot);
    event VerifierUpdated(address indexed verifier);

    // ------------------------------------------------------------------ errors
    error Paused();
    error ZeroCommitment();
    error DoubleSpend();
    error TreeFull();
    error UnverifiedProof();

    constructor(address usdcToken_, address verifier_) {
        usdc = usdcToken_;
        verifier = IShieldedPoolVerifier(verifier_);
        _initZeros();
    }

    // ------------------------------------------------------------------ public
    function setVerifier(address v) external {
        // P1 bootstrap auth is open for iteration. Guard / DAO auth by P3 (a spend
        // making a real mint of this pool's USDC must be gated by the Safe guard).
        verifier = IShieldedPoolVerifier(v);
        emit VerifierUpdated(v);
    }

    function pause() external { paused = true; }
    function unpause() external { paused = false; }

    /// A holder deposits USDC to shield a note. The caller's USDC is pulled.
    function deposit(uint256 commitment, uint256 amount) external {
        if (paused) revert Paused();
        if (commitment == 0) revert ZeroCommitment();
        IERC20Minimal(usdc).transferFrom(msg.sender, address(this), amount);
        _insert(uint256(commitment));
        emit ShieldedDeposit(bytes32(commitment), amount);
    }

    /// Spend a note: burn the input nullifier, record an output state.
    ///
    /// RELAYER MODEL (§8, resolved 2026-09-29): the proof is verified OFF-chain by
    /// a permissionless relayer; the pool does not rebuild a merkle tree here. The
    /// relayer supplies `newRoot` — the Poseidon root after the note leaves the tree.
    /// The pool seals the nullifier and adopts `newRoot` as the authoritative root,
    /// anchoring the transition to the PREVIOUS root through the verifier seam.
    ///
    /// (Keccak `_insert` is intentionally NOT called on spend: the on-chain tree was
    /// a P1 storage model; the treasury's truth is the Poseidon root the relayer
    /// commits. Deposit's keccak insertion remains for P1, superseded at P3.)
    function spend(
        bytes32 inputNullifier,
        bytes32 outputCommitment,
        uint256 amount,
        uint256 newRoot,
        bytes calldata proof
    ) external {
        if (paused) revert Paused();
        if (nullifiers[inputNullifier]) revert DoubleSpend();
        // The verifier seam anchors: verifySpend(oldRoot = current root, ...).
        bytes32[] memory ins = new bytes32[](1);
        ins[0] = inputNullifier;
        bytes32[] memory outs = new bytes32[](1);
        outs[0] = outputCommitment;
        if (!verifier.verifySpend(bytes32(root), outs, ins, proof)) revert UnverifiedProof();
        nullifiers[inputNullifier] = true;
        root = newRoot;   // authoritative Poseidon root transition (relayer-committed)
        emit ShieldedSpend(inputNullifier, outputCommitment, amount);
        emit RootUpdated(root);
    }

    /// Unshield: redeem a note for real USDC to `recipient`. Nullifier must be
    /// unspent and the proof pass the seam. RELAYER MODEL: `newRoot` is the
    /// Poseidon root after the note is withdrawn (committed by the relayer).
    /// P1: Noop passes anything, so this MUST NOT be pointed at real USDC until
    /// the relayer/verifier gate is authoritative — see plan §10.
    function redeem(
        bytes32 inputNullifier,
        address recipient,
        uint256 amountOut,
        uint256 newRoot,
        bytes calldata proof
    ) external {
        if (paused) revert Paused();
        if (nullifiers[inputNullifier]) revert DoubleSpend();
        bytes32[] memory ins = new bytes32[](1);
        ins[0] = inputNullifier;
        bytes32[] memory outs = new bytes32[](0);
        if (!verifier.verifySpend(bytes32(root), outs, ins, proof)) revert UnverifiedProof();
        nullifiers[inputNullifier] = true;
        root = newRoot;   // Poseidon root transition (relayer-committed)
        IERC20Minimal(usdc).transfer(recipient, amountOut);
        emit UnshieldedWithdrawal(recipient, amountOut);
        emit RootUpdated(root);
    }

    function spent(bytes32 n) external view returns (bool) { return nullifiers[n]; }
    function getRoot() external view returns (uint256) { return root; }
    function isSpent(bytes32 n) external view returns (bool) { return nullifiers[n]; }

    // ------------------------------------------------------------------ merkle
    function _initZeros() internal {
        uint256 z = uint256(keccak256(abi.encodePacked(bytes32(0), bytes32(0))));
        for (uint256 h = 0; h < TREE_DEPTH; h++) {
            zeros[h] = h == 0
                ? z
                : uint256(keccak256(abi.encodePacked(bytes32(zeros[h-1]), bytes32(zeros[h-1]))));
        }
        root = zeros[TREE_DEPTH - 1];
    }

    // Pure, fixed-depth, deterministic insert. Mirrors the classic Tornado
    // incremental frontier: at depth h, if the leaf at index bits is a left child,
    // write the accumulating node into frontier[h]; if it's a right child, it
    // pairs with what's already in frontier[h]. This is a well-understood pattern.
    function _insert(uint256 commitment) internal {
        if (paused) revert Paused();
        if (nextIndex >= (uint256(1) << TREE_DEPTH)) revert TreeFull();

        uint256 idx = nextIndex;
        uint256 current = commitment;
        for (uint256 h = 0; h < TREE_DEPTH; h++) {
            if ((idx >> h) % 2 == 0) {
                frontier[h] = current;
            } else {
                current = uint256(keccak256(abi.encodePacked(bytes32(frontier[h]), bytes32(current))));
            }
        }
        root = current;
        nextIndex = idx + 1;
        emit RootUpdated(root);
    }
}