# irl.coop Community OS - Master Architecture Plan
**Version:** 4.0 (Base-Native ZK-AA Evolutionary Shard Node)
**Constraint:** 4GB RAM + 32GB Swap
**Target System:** Sovereign Shard Node

---

## 1. Executive Summary

The v4 stack moves away from legacy multi-chain "Double Privacy" architectures (Secret Network + Namada + Cosmos) and hardware-dependent Trusted Execution Environments (TEEs) which create state-level hardware backdoors. 

It establishes a unified, secure, and highly performant **EVM-native cryptographic stack on Base Mainnet** on Day 1. The design balances frictionless Web2-style onboarding with absolute, mathematical **State-Level Sovereignty** by integrating:
*   **ERC-4337 Account Abstraction (User Safes):** Deployed gaslessly and managed locally on-chain.
*   **Passkey Biometrics (W3C WebAuthn):** Hardware-secured keys for daily, instant approvals.
*   **Modular Session Keys & Spending Limits:** Eliminating guardian interaction for everyday actions.
*   **ZK-Shielded UTXO Pool (Railgun Model):** Enforcing "Private at Rest" balances and anonymous transfers.
*   **DAO-Routed Batch Deposits:** Breaking public ledger links.
*   **Provisional Peer.xyz Escrow On-Ramp:** A P2P fiat-to-shielded-crypto tunnel utilizing Venmo, CashApp, and PayPal.

---

## 2. Low-Level Core Feature Specifications

### A. Evolutionary Authentication & Onboarding Pipeline
To eliminate user friction while retaining non-negotiable sovereignty, user Safes execute a deterministic, modular upgrade path as they transition from casual participation to high-value sovereign vault operations.

```
STAGE 1: Convenience-First Onboarding             STAGE 2: Sovereign Promotion
(Setup & Low-Value Operations)                     (Sovereign Vault & High-Value Actions)

+-----------------------------+               +-----------------------------+
|    Individual User Safe     |               |    Individual User Safe     |
|                             |               |                             |
|  - Threshold: 1-of-2        |               |  - Threshold: 2-of-3        |
|  - Key A: User Biometric    |               |  - Key A: User Biometric    |
|            (Passkey)        |  (Threshold   |            (Passkey)        |
|  - Key B: irl.coop Backend  |   Upgrade)    |  - Key B: Social Guardians  |
|            (OAuth Signer)   | ------------> |            (Coop Members)   |
|                             |               |  - Key C: irl.coop DAO      |
|  * Authenticate instantly   |               |            (Emergency Only) |
|    with Google OAuth to     |               |                             |
|    sponsor gas & low-value  |               |  * Centralized Backend key  |
|    transactions.            |               |    is COMPLETELY REVOKED.   |
+-----------------------------+               +-----------------------------+
```

*   **Stage 1 (Convenience-First):** The user registers instantly via Google/Apple OAuth + local biometric scan. The system deploys an ERC-4337 Safe with a 1-of-2 signing threshold. `Key A` is the user's biometric Passkey (stored locally in their device's Secure Enclave). `Key B` is the `irl.coop` Backend Signer. This enables rapid, gas-sponsored Web2 setup.
*   **Stage 2 (Sovereign Promotion):** To activate full privacy features and secure larger assets, the Safe executes a transaction that **completely deletes** the backend `Key B` from the contract's approved owners list. It adds 3 trusted cooperative members as **Social Guardians** and upgrades its threshold to **2-of-3** (requiring Passkey + Guardians or the decentralized DAO backstop for high-risk recoveries).

---

### B. Frictionless Spending & Session Keys
To prevent social and operational friction, coop members are never asked to verify a user's daily transactions.
*   **Path A: Daily Actions (Passkey-Only):** Controlled by a Safe Spending-Limit/Session Key module. Any transfer under a daily threshold (e.g., $500/day) or any direct interaction with the `irl.coop` ZK-Shielded Pool is executed instantly via the user's local biometric Passkey. No other signers are notified.
*   **Path B: High-Value & Recovery (Interactive Safeguard):** Outlier transfers exceeding the daily spending limit or critical key rotation requests escalate to the full 2-of-3 multi-sig threshold, requiring co-signatures from the designated Social Guardians.

---

### C. Role-Based Access Control (RBAC) Architecture
Since hardware-based TEEs (such as AMD SEV or Intel SGX) are bypassed to prevent state-level microcode backdoors, we implement on-chain, mathematically pure RBAC using Merkle Trees:
1.  The main cooperative registry contract (`CoopRegistry.sol`) maintains a state variable: `bytes32 public memberMerkleRoot` representing the list of active members.
2.  To perform member-only actions, the user's web app generates a Merkle Proof locally in their browser.
3.  On-chain smart contracts verify this proof permissionlessly using the registered Merkle Root to grant instant execution rights.

---

### D. Funding, Batch-Shielding, & Provisional Peer.xyz Escrow
To prevent on-chain analysis from linking a user's real-world identity or physical payment accounts to their private shielded holdings, we implement a **Sovereign Liquidity Router** combined with a provisional fiat on-ramp using **peer.xyz**:

```
      [ WEB2 PAYMENT RAILS ]
 (PayPal / Venmo / Cash App / Wise)
              │
              │ 1. User sends Cash to P2P Counterparty.
              ▼
   [ PEER.XYZ ESCROW CONTRACT ]
              │
              │ 2. Escrow releases crypto on-chain.
              │    Destination is targeted to the irl.coop DAO.
              ▼
    [ irl.coop DAO BATCH ROUTER ]
              │
              │ 3. Buffer and pool incoming tokens publicly.
              │ 4. Shuffle & submit consolidated batch.
              ▼
      [ ZK-SHIELDED POOL ]
              │
              │ 5. Cryptographically mints private UTXOs
              │    directly to User's private "0zk" address.
```

1.  **Peer.xyz Escrow (Provisional):** When a user funds their account with fiat (Venmo, PayPal, CashApp), Peer matches them with a P2P counterparty and locks the corresponding USDC in an escrow smart contract on Base. The user sends Web2 cash to the counterparty, and the escrow releases the USDC.
2.  **DAO Batch Router:** To prevent a public link between the Peer transaction and the user's wallet, the Peer escrow destination is targeted directly to `CoopBatchRouter.sol` (the DAO router).
3.  **The Shielding Shuffle:** The router aggregates incoming funds from multiple users over a clearing epoch (e.g., 12 hours) and submits a single consolidated batch deposit to the **ZK-Shielded Pool (UTXO contract)**.
4.  **ZK UTXO Minting:** The pool contract mints private, encrypted UTXO notes directly to the users' private "0zk" addresses. The cryptographic connection between the user's public identity and their private resting assets is completely broken.

---

### E. Group Creation (Cooperative Shards)
Users can spin up localized, independent sub-cooperatives (e.g., "Swim Buddies") as isolated cryptographic shards on-chain:
1.  The user specifies the sub-group's parameters (Group Name, Members, Initial Admins) in the portal.
2.  The `CoopShardFactory.sol` contract deploys a deterministic Safe proxy via `CREATE2`.
3.  The factory binds local helper contracts (`LocalRegistry.sol` for sub-group member Merkle Roots and `ConfidentialVoting.sol` for anonymous tallying) as modular extensions to the Safe.
4.  The sub-cooperative operates with complete local sovereignty, structurally isolated from the parent `irl.coop` systems.

---

## 3. Sovereign Shard Infrastructure Layer (Memory Constraint Tuning)

The entire stack is tuned to run comfortably within your target **4GB RAM / 32GB Swap** hardware profile, orchestrated via `docker-compose.yml`.

### The Core Infrastructure
- **Persistence & Coordination:** Postgres/Citus (Database), Redis (Queue/Cache), Minio (S3 Storage).
- **Asynchronous State-Flow:** Temporal.io (Durable workflow engine for ZK-syncs).
- **Communication Layer:** Matrix (Synapse), Jitsi (RTC), Element (UI), Stalwart (Email Server), Asterisk/FreeSWITCH + FusionPBX (VOIP).

### Modular Coop OS Components (Forked/Containerized)
- **Governance & Docs:** CryptPad (Zero-knowledge collaboration).
- **RSVP & Events:** Hi.Events (Ticket/RSVP engine).
- **Feedback & ZK-Surveys:** Formbricks (Typeform-style ZK-forms).
- **Project/Tasks:** OpenProject.
- **Scheduling:** Cal.com.
- **Web Presence:** Webstudio (Visual site builder).
- **Social Distribution:** Postiz (Fediverse distribution).
- **Data/Dashboards:** NocoDB (Spreadsheet-like DB interface).

| Service | Architecture Role | Language/Implementation | RAM footprint | Fork / Submodule Source |
| :--- | :--- | :--- | :--- | :--- |
| **Web App & Portal** | Client-Side ZK & WebAuthn | Next.js / React (Static export) | ~0MB (Browser) | Monorepo Core (`apps/web`) |
| **Coop API Gateway** | ERC-4337 Paymaster & Relayer | Node.js (Rust backend helpers) | ~150MB | Monorepo Core (`apps/coop-api`) |
| **Contracts** | On-chain verification, Safe AA | Solidity (Hardhat/Foundry) | ~0MB (On-chain) | Monorepo Core (`contracts`) |
| **Ticketing Engine** | RSVP & Ticket sales | Hi.Events | ~150MB | `git@github.com:hieventsdev/hi.events.git` |
| **Surveys & Forms** | Anonymous ZK Feedback | Formbricks | ~200MB | `git@github.com:formbricks/formbricks.git` |
| **Sovereign Local Node**| Local RPC & Validation | Geth / Hardhat | ~800MB | Standard Docker Image |
| **Database** | Sharded State Tracking | Citus / PostgreSQL | ~500MB | Standard Docker Image |
| **Reverse Proxy** | Network Routing | Nginx | ~20MB | Standard Docker Image |
| **Cache & Buffers** | Session Cache & Buffers | Redis | ~50MB | Standard Docker Image |

**Total Estimated Server Memory Footprint:** ~1.87GB (Leaving plenty of headroom for OS buffers and local host processes).

---

## 4. Phase-by-Phase Master Implementation Plan

*   [ ] **Phase 1: Local Environment & Mock Signers**
    *   Initialize the hardhat/foundry test suite targeting Base Sepolia.
    *   Develop mock Secp256r1 (WebAuthn) and ECDSA scripts to simulate user biometric device signatures and backend co-signing behavior.
*   [ ] **Phase 2: Core AA Smart Contracts**
    *   Implement the ERC-4337 custom Safe validation modules (Passkey P-256 verifiers, Stage 1 to Stage 2 key revocation, Social Recovery, Session Keys, and Spending Limits).
*   [ ] **Phase 3: The Cryptographic Privacy & Routing Layer**
    *   Build `CoopRegistry.sol` (Merkle Root member registries) and `CoopBatchRouter.sol` (the public-to-private batch clearing system).
    *   Integrate a mockup of the ZK-Shielded UTXO pool (using Semaphore for private voting and a mock Railgun interface for asset shielding).
*   [ ] **Phase 4: Forked Open-Source Integrations**
    *   Setup `docker-compose.yml` to spin up forked submodules for **Hi.Events** (Ticketing) and **Formbricks** (ZK-Feedback) in standalone, sharded configurations.
*   [ ] **Phase 5: Sovereign Shard Node Docker Bundle**
    *   Package all backend services (Postgres, Redis, Nginx, Coop API, and Local Node Geth instance) into a single, optimized Docker-compose configuration tailored for the 4GB RAM host machine.
