# Custody and agent keys: a holistic fix

Status: **design** (a plan; nothing here is built).
Scope: the five defects found in the session/ownership review, one plan that closes them, and
how it makes groups sovereign. Depends on the mainnet deploy (`mainnet-deploy.md`) — all of
this lands on Base.

## What is actually wrong (with the evidence)

1. **Session keys go out unrestricted and never expire.** `SessionKeyModule` ships with the
   allow-list off (`listEnabled` defaults false, line ~69) and `enableSessionKey` sets no
   expiry (lines ~119-128). So a live agent key can spend up to its daily budget *at any
   target*, and it stays valid until someone disables the module.
2. **`SovereignEvolutionModule` is a stub that looks real.** Its `onlySafe` guard is empty
   (lines ~23-26), and it only mutates its own `safeConfigs` mapping — it cannot revoke an
   owner on-chain. Nothing may depend on it, but its name invites exactly that.
3. **The platform key is the owner at creation.** `defaultInitializer()` builds a 1-of-1 Safe
   owned by the backend signer (`safe.ts` ~128-129, ~174). A second route
   (`/api/safe/sovereign`) hands ownership to a passkey owner afterwards. Between creation and
   that call, the platform *is* the wallet.
4. **Signer keys sit in plain env** (`SAFE_BACKEND_SIGNER_KEY`, `SESSION_KEY`), long-lived.
5. **One bespoke module, no modular account** — the passkey/session/recovery logic is custom
   Safe code rather than swappable modules.

## The one decision that gates everything else

**How a Safe gets its owners at creation.**

- Today: the platform key owns it first; a passkey swaps in later.
- Proposed: **the owner set is the member's passkey owner contract(s) from the very first
  block; the platform only pays gas.**

This is the gate because it decides the shape of every other fix. If ownership is passkey-native
at creation:
- the platform never owns anything (defect 3 disappears rather than being repaired),
- the "hand it over" step stops existing, so it cannot be forgotten,
- defect 2's module has no job left and gets deleted.

Rejected alternatives: *deploy-then-handoff* (keeps a platform-owned window and a step to miss);
*platform key as one of N owners* (still a platform co-owner, still custody).

## Target architecture — three roles, cleanly split

- **Owners = member passkeys.** Safe owners are `PasskeyOwner` (EIP-1271) contracts — one per
  member passkey. Threshold: 1-of-1 for a person, **N-of-M for a group** (the threshold *is*
  the governance). These are the only addresses in `getOwners()`.
- **Agents = non-owner session keys** driven through a module that enforces budget, a
  default-closed allow-list, and an expiry, per key.
- **Platform = a gas-only sponsor + relay.** Never an owner, never able to move funds. A
  sponsor EOA sends transactions and is reimbursed; its key is rotatable and vault-held.

## Contracts: new and changed

1. **`PasskeyOwner.sol` (new).** An EIP-1271 owner contract that validates a WebAuthn
   assertion against a P-256 public key. Uses the EIP-7212 precompile where the chain has it
   (Base does), with a pure-Solidity P-256 fallback verifier where it does not. This is the
   owner type the whole model rests on. (There is already a `PasskeyOwner` + validation test in
   the tree; this promotes it to the default owner.)
2. **`SessionKeyModuleV2.sol` (new; replaces v1 semantics).** Several named sessions at once,
   each with: `validUntil` (expiry), a budget (daily and/or total), and an allow-list that is
   **denied by default** — a session is inert until owners arm at least one target/selector.
   Individually revocable, with events. Fixes defect 1.
3. **`SovereignEvolutionModule.sol` — delete.** If the "sovereign stage" idea is wanted, make it
   a **view computed from `getOwners()`** (does the owner set contain a passkey owner?), not a
   stored authority. Fixes defect 2.
4. **`safe.ts` changes.** `defaultInitializer()` is built from the member's passkey owner
   address(es); `/api/safe/deploy` never inserts the backend key into `owners`;
   `/api/safe/sovereign` stays only as a migration path for already-deployed legacy Safes (and
   is removed once none exist). The sponsor key is used to *send*, never to own.
5. **Deploy set grows** by `PasskeyOwner` and `SessionKeyModuleV2` — deployed and recorded in
   `networks.json` (verified) alongside the existing contracts.

Consideration: an alternative substrate is a **modular account** (ERC-7579/6900) where the
passkey, session, and recovery pieces are swappable modules. Recommended: keep **Safe +
modules** for now (battle-tested, already integrated) and treat the modular migration as a
later, optional step; note it, don't block on it.

## Keys, out of the environment

- **Sponsor/deployer key:** vault-held, topped up per launch, never a standing balance.
- **Session keys:** minted per session with a short life; if a relay must sign, the key comes
  from the vault or a scoped signing service, never a standing plaintext env var.
- **Member passkey keys:** never server-side at all. They live on the member's device. That is
  the whole point of the passkey-owned model.
Fixes defect 4.

## Group sovereignty

- A **group is a Safe with N-of-M passkey owners** (its members). The threshold is the group's
  governance; no platform key is in the set.
- **External accounts become group service accounts** (D-45/D-46): DNS, the mail relay, the
  GitHub org, host root — opened by the group, credential group-held, granted and revoked by
  group acts. The current single bootstrap deployer is a temporary stand-in that the group's
  own owners supersede.
- This is the content of **Phase 2 ("the keys come home")** in `group-operated-stack.md`, and it
  is what Phase 1.1 ("the group exists") needs to be true.

## Staged plan (each step reversible)

- **P0 — Session module v2.** Ship `SessionKeyModuleV2` (expiry + allow-list default-closed +
  per-key) with tests. Closes defect 1. Independent of everything else.
- **P1 — Passkey-native creation.** Add `PasskeyOwner` as a real owner type, register passkeys
  at onboarding, and make *new* Safes passkey-owned from creation (`safe.ts` initializer
  change). Closes defects 3 and 4.
- **P2 — Remove the platform owner path.** Delete `SovereignEvolutionModule`; drop the backend
  owner key; keep a gas-only, vault-held sponsor. Closes defect 2 from code.
- **P3 — Modular note (optional).** Evaluate ERC-7579/6900; not urgent. Closes defect 5.
- **P4 — Group sovereignty.** N-of-M passkey Safes and service accounts as a member kind.

Ordering note: P1/P2 land on Base, so the mainnet deploy runbook runs first (or alongside).

## Honest limits

- `PasskeyOwner` leans on the **EIP-7212 precompile**; without it, a pure-Solidity P-256
  verifier is heavier and must be audited. Confirm the precompile on the target chain.
- A session key is still a **bearer key**. Expiry + budget + allow-list shrink the blast radius;
  they do not erase it.
- Removing the platform key from *custody* does not remove the platform from *availability*
  (it still relays gas). That is a separate concentration — record it as one, with a path off.
- This plan fixes the custody and agent-key defects. It is not an audit of the Safe module
  wiring itself.

## Evidence

- `contracts/contracts/modules/SessionKeyModule.sol` — allow-list default off; no expiry.
- `contracts/contracts/modules/SovereignEvolutionModule.sol` — empty `onlySafe`; own-mapping only.
- `apps/coop-api/src/safe.ts` — backend-owned initializer; sovereign handoff route.
- `docs/design/group-operated-stack.md` — Phase 2 (keys come home); Phase 1.1 (group exists).
- `docs/DECISIONS.md` — D-14 (delegation is session keys), D-42, D-45, D-46.