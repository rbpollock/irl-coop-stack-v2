# Digital Identity Sovereignty + Federation (FedID)

Status: design · 2026-10-04.

Identity on irl.coop is sovereign: every person and every group owns a cryptographic identity that
cannot be revoked, seized, or locked out by a platform operator. Federation means these identities
interoperate across groups without a central authority.

---

## What already works (live)

| Primitive | How it works | Where to read more |
|---|---|---|
| **Passkey onboarding** | Your first login creates a WebAuthn credential. No password, no recovery email trap. | [`account-and-key-model.md`](/design/account-and-key-model) |
| **Safe-as-everything** | Every account — person or group — is a Safe smart-contract wallet. Same deploy path, same address derivation, same recovery flow. | [`irl-coop-group.md`](/design/irl-coop-group) |
| **Keycloak as broker** | Google (or other IdP) signs you in, but the coop holds your session. You can add brokers later without re-registering. | [`coop-accounts-and-phone-verification.md`](/design/coop-accounts-and-phone-verification) |
| **Fleet identity** | One cookie (`coop_session`) reaches every app through oauth2-proxy gates. No second login inside the stack. | [`member-scoped-app-access.md`](/design/member-scoped-app-access) |
| **Seat model** | One row in `group_members` = one membership edge. Roles, visibility, `joinedAt`. The group is the authority for its own roster. | [`irl-coop-group.md`](/design/irl-coop-group) |

---

## What is designed, not yet built

| Feature | Status | Where to read more |
|---|---|---|
| **Cross-group federation** | Seat transfer, cross-group visibility rules, intergroup treasuries | [`declared-binding-registry.md`](/design/declared-binding-registry) · [`group-model-technical-overview.html`](/design/group-model-technical-overview) |
| **FedID protocols** | W3C DID / DIF Sidetree interop. The Safe address is already a persistent identifier; the work is standardizing it for external systems. | [`chain-agnostic-identity.md`](/design/chain-agnostic-identity) · [`did-provider-comparison.md`](/design/did-provider-comparison) |
| **Cross-chain accounts** | Same identity, multiple chains. | [`multi-chain-accounts.md`](/design/multi-chain-accounts) |
| **ZK membership proofs** | Prove group membership without revealing which group. | [`zk-membership-graph-proofs.md`](/design/zk-membership-graph-proofs) |

---

## Open questions

- **External proof**: How does a member prove group membership to a non-coop service (union website,
  government portal)? We can produce an EIP-1271 signature today; turning that into a standard VC
  is a design decision, not code.

---

## Honest limits

- The federation code exists on paper and in binding specs. No cross-group seat transfer has been
  executed in production.
- Keycloak is the only broker wired today. Phone verification exists but is not the primary path.

See [`irl-coop-overview.md`](/design/irl-coop-overview) for how this pillar fits into the whole platform.
