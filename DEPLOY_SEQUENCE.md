# irl.coop Community OS - Deployment and Verification Sequence

This sequence document governs the step-by-step assembly, testing, and fault-tolerant verification of the `irl.coop-v2` stack. It ensures that every cryptographic, database, and container layer is fully validated before the next is built.

---

## 1. Directory Structure

The `irl-coop-stack-v2` workspace is organized into a monorepo structure:

```
irl-coop-stack-v2/
├── MASTER_PLAN.md             # Core architecture blueprint
├── DEPLOY_SEQUENCE.md         # This execution and verification runbook
├── package.json               # Top-level workspace manager
├── apps/
│   ├── web/                   # Next.js Frontend Portal (Passkey & Client-Side ZK)
│   └── coop-api/              # Node.js API Gateway (AA Paymaster & Relayer)
├── contracts/                 # EVM Contracts (Safe Modules, Merkle Registry, Batcher)
│   ├── src/
│   └── test/
├── docker/                    # Shard Node Host Infrastructure
│   ├── docker-compose.yml     # Self-contained local emulator stack
│   ├── postgres/              # Citus DB configuration & migrations
│   └── geth/                  # Local Geth private chain configuration
└── scripts/                   # Integration and verification test suites
    └── validate_system.ts     # The automated end-to-end testing harness
```

---

## 2. Step-by-Step Execution Sequence

### Phase 1: Local Simulation & Hardhat Environment
*   [ ] **1.1 Project Initialization:** Configures Node workspaces, TypeScript, and install essential tooling (Hardhat, Ethers, Zama's `fhevmjs`).
*   [ ] **1.2 Create Mock Signers:** Write browser-level simulation scripts to test local TPM Secp256r1 keys and WebAuthn signatures in memory.
*   [ ] **1.3 Automated Hardhat Test suite:** Configure contracts testing framework.

### Phase 2: Core Account Abstraction Solidity Development
*   [ ] **2.1 Passkey Module (`WebAuthn256r1Verifier.sol`):** Direct on-chain verification of biometric signatures.
*   [ ] **2.2 Revocable Multi-Sig Contract (`SovereignSafe.sol`):** Implement the Stage 1 to Stage 2 evolutionary key promotion and social recovery mechanisms.
*   [ ] **2.3 Spending Limit Module (`SafeSessionKeys.sol`):** Allow instant Passkey-only transactions under daily caps.

### Phase 3: Privacy, Routing & Group Sharding
*   [ ] **3.1 Merkle State Registries (`CoopRegistry.sol`):** High-performance O(1) group updates with revocation mappings.
*   [ ] **3.2 Sovereign Batch Router (`CoopBatchRouter.sol`):** Deposit buffers and consolidated batch-shielding endpoints.
*   [ ] **3.3 Cooperative Factory (`CoopShardFactory.sol`):** Deterministic, zero-leak group shard deployment.

### Phase 4: Shard Emulator (Docker-Compose Deployment)
*   [ ] **4.1 Postgres / Citus Schema Migration:** Configure database tables for sharded local state tracking.
*   [ ] **4.2 Private Geth Private Chain Setup:** Spin up a private local Ethereum L2 simulation inside docker.
*   [ ] **4.3 Write end-to-end automated validation runner:** Code the master validation harness `validate_system.ts`.

---

## 3. The "Self-Healing" Verification Standards

To progress from one phase to the next, you must execute the automated verification command and achieve a **100% pass rate**:

*   **Contracts Verification:**
    ```bash
    npm run test:contracts
    ```
*   **System Integration Verification:**
    ```bash
    npm run system:validate
    ```

If any connection, transaction, or database write fails, the script will output a rich debugging log with an exit code of `1`. Correct the mismatch before writing additional business logic.
