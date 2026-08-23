# Group Secret Vault — Design Note

Status: design (discussion). Author: Robbie + Hermes, Aug 2026.
Builds on: [account-and-key-model.md](account-and-key-model.md) (Layer 2 "the keys",
gap #4), [delegation-and-session-keys.md](delegation-and-session-keys.md) (§2 secret
domains, §5 session-key bridge, §6 delivery key), [group-scoping.md](group-scoping.md)
(projection tables + RLS).

## 1. The problem in one paragraph

Groups hold secrets that no single party — and especially not the backend — may
read alone: per-tenant service credentials (a Postiz/Plane/Stalwart OAuth app
secret or API key), webhook tokens, salt backups, delivery-key material. Today
there is nowhere to put them: `master.key` only derives *platform* keys, the
ansible vault holds *deployment-time* platform secrets, and coop-api has no
per-group secret store. This note specifies the **group secret vault**: a
Safe-anchored, threshold-encrypted store where ciphertext sits anywhere but
decryption requires a quorum of member-held shares.

## 2. Settled principles (do not relitigate)

1. **No single party decrypts alone.** Not the backend, not any one member. The
   backend may *censor* (liveness) — never *steal* (confidentiality).
2. **Quorum = governance.** The threshold is the group's own authority, so
   "k members collude" is not an attack; it is the group acting. The design only
   forbids *fewer than k* parties from succeeding.
3. **Shares are member-held, not server-held.** coop-api stores ciphertext and
   *encrypted* shares; the decryption capability lives on member devices.
4. **Recovery never depends on the backend.** A quorum of members must always
   suffice to unlock; the backend assists, never blocks, never steals.
5. **Members never see keys.** Share handling is invisible (passkey-driven),
   like everything else in the Safe-as-everything model.
6. **Secrets are used, not read.** A released secret is injected into the
   consuming service for a single purpose and then zeroized — it is never a
   value a human or log holds onto.
7. **Granted keys are first-class holders.** A share — or the right to trigger
   an unlock — may be held by an ERC-7715 *granted* key (interactive session,
   delivery, or agent), not only a member owner key. The grant's scope, expiry,
   and the Safe's revocation apply to vault access exactly as to any delegated
   capability.

## 3. What it stores (scope)

- **Env / service-to-service secrets** — the OAuth app client-id/secret pairs and
  API keys that a group's *own* service instances use (Postiz per-group apps,
  a group's webhook token, a group's OnlyOffice/Mailgun/Stripe key). This is the
  category the Postiz-integration keys fall into (scoping deferred — §11).
- **Salt backups** — a group's `saltNonce`/recovery material, so a group account
  can be re-derived by quorum even if the original device is lost.
- **Delivery-key / agent-key private material** — the custodial halves described
  in delegation-and-session-keys.md §6.

Explicitly *out of scope* (unchanged): platform secrets (`master.key`, the
`postiz` Keycloak client secret, MinIO root) — those stay in the derived-key +
ansible-vault tiers (§9). Member-facing app passwords are the zero-credential
model's fallback, never stored here.

## 4. Trust model

| Actor | Capability | Why |
|---|---|---|
| backend alone | none | holds ciphertext + *encrypted* shares; no share is decryptable without a member key |
| any 1 member | none | one share < k |
| backend + (k−1) members | none | backend contributes zero shares |
| k members | decrypt | the group acting (governance threshold) — correct |
| backend, censoring | block an unlock | liveness loss, visible, survivable via alternate coordination |

Granted-key effect: a custodial granted key (e.g. a coop-api-held delivery key)
that also holds a share counts as one coop-api-reachable share — so "backend +
(k−1) members" becomes "backend + (k−2) members + 1 custodial share" = k. This
is why custodial granted shares are an explicit decision (§13.2), default off in
v1.

Honest limit (from account-and-key-model.md): *k parties who all collude cannot
be stopped by math* — choose k and the holders so that set is the group's
legitimate authority, not a hidden backdoor.

## 5. Crypto shape (v1 — pure crypto, no ceremony)

Shamir Secret Sharing (SSS) over the secret itself, shares individually
encrypted to **holder keys** (member owner keys OR granted keys — §5.1):

1. A group owner obtains plaintext `S` (e.g. the Facebook app secret they minted
   on the Facebook developer console).
2. **Split (client-side, on the owner's device):** `S` → `n` shares via
   Shamir k-of-n. `k` defaults to the group Safe's owner threshold; `n` = the
   holders designated to carry shares (default: all owners).
3. **Wrap each share:** `enc_share_i = AES-GCM(share_i, key=ECDH(P_owner, P_holder_i))`
   — encrypted to holder i's public key (a member passkey P-256 / Safe owner key
   per EIP-7212, or a granted key's public key). The owner's own share is wrapped
   to their own key.
4. **Store:** only the *encrypted* shares + metadata. The plaintext `S` is never
   persisted anywhere.

Why this holds: coop-api can read every byte it stores, but decrypting `S`
requires k plaintext shares, and every plaintext share is locked behind a holder
private key that lives only on that holder's device/runtime.

### 5.1 Holder keys — members and granted keys alike

A holder is any key the group Safe has authorized to carry a share. Two kinds,
same slot:

- **Member owner key** (passkey P-256) — the default holder.
- **Granted key** (ERC-7715 session/delivery/agent key) — a permitted, scoped,
  revocable key. A delivery key may hold a share so *scheduled* automation can
  participate in an unlock with no human present; an agent key may hold a share
  to act on a narrow purpose. The grant's scope, expiry, and the Safe's
  revocation bind the share: a revoked granted key can no longer contribute,
  even if its wrapped-share bytes leak (revocation is on-chain, and the share is
  inert without a live grant).

Because a granted key's private material may itself be custodial (coop-api holds
the delivery key's private half, encrypted, in the member's own vault slice —
delegation-and-session-keys.md §6), a *custodial delivery share* means coop-api
effectively holds one share's capability. That lowers the backend's distance to
k by one — the precise trade-off captured in §4 and §13.2.

*Future (v3):* envelope encryption (SSS a DEK, DEK encrypts the payload) for bulk
secrets; BLS t-of-n threshold decryption if "no single reassembly point ever" is
required. Not needed for API-key-sized secrets.

## 6. The three ceremonies

**Split (create/rotate)** — owner device generates/imports `S`, SSS-splits,
wraps shares to member keys, uploads. coop-api stores and returns metadata. The
owner's device is the only place `S` ever existed in cleartext at rest (transient).

**Unlock (use)** — bound to a purpose and a request id (nonce) so shares can't
be replayed:
1. A use requires `S` (e.g. Postiz needs the group's Facebook secret).
2. coop-api broadcasts an unlock request `(secret_id, purpose, nonce)` to
   share-holders.
3. Each of k holders approves: their device/runtime decrypts `enc_share_i` with
   the holder key → `share_i`, and submits it (TLS) together with a valid,
   unrevoked grant — a member over their session-key-authenticated channel, a
   granted key with its ERC-7715 grant checked against the Safe.
4. coop-api Lagrange-interpolates k shares → `S` **in memory**, injects it into
   the consuming service for the stated purpose, then zeroizes. (v3 option:
   reassemble client-side so `S` never touches coop-api; see §13 open knobs.)
5. An audit record is written: who, when, what purpose, which nonce (on-chain
   in v2).

**Rotate / membership change** — re-split. A departing member's wrapped share is
dropped; if that drops the live holder count below k, the group re-splits with
the new member set (Shamir has no cheap re-key; re-split is the operation).
This is why "pre-commit at formation" matters: the share-holder set and threshold
are fixed at secret creation and change only through a quorum-gated rotate.

## 7. Data model (Citus `irlcoop`, projection layer, RLS `app.sub`)

```
group_vault_secrets
  id            uuid pk
  group_id      → groups.id
  key_id        text        -- stable handle: postiz.facebook, docs.sig, ...
  algorithm     text        -- 'shamir-aes256' (v1)
  threshold_k   int
  shares_n      int
  purpose       text        -- audit: what this secret is for
  created_by    sub
  created_at, updated_at

group_vault_shares
  secret_id     → group_vault_secrets.id
  holder        text        -- 'sub:<kc sub>' (member) or 'grant:<key id>' (granted key)
  share_index   int
  enc_share     text        -- AES-GCM(share_i, ECDH key), base64
  created_at
```

Ciphertext may "sit anywhere" per the model; for v1 it lives in the projection
registry (already the queryable mirror the apps join). RLS scopes rows to the
group so a member can fetch *their own* wrapped share and nothing else; the
`enc_share` bytes are safe to expose because they're wrapped to member keys.

## 8. API surface (coop-api)

```
POST   /api/v1/groups/:id/vault/secrets                    -- split + store (owner)
GET    /api/v1/groups/:id/vault/secrets                    -- metadata only, never shares/plaintext
GET    /api/v1/groups/:id/vault/secrets/:key_id            -- metadata + MY wrapped share
POST   /api/v1/groups/:id/vault/secrets/:key_id/unlock     -- request unlock (broadcast, returns nonce)
POST   /api/v1/groups/:id/vault/secrets/:key_id/contribute -- submit my share (session-key authed)
POST   /api/v1/groups/:id/vault/secrets/:key_id/rotate     -- re-split (new secret or new holder set)
DELETE /api/v1/groups/:id/vault/secrets/:key_id            -- drop (quorum-gated)
```

`contribute` carries the unlock nonce; coop-api binds shares to that nonce and
refuses shares outside a live unlock. The released plaintext is returned only
to the consuming integration path, never to a caller.

## 9. Three-tier secrets hierarchy (where this sits)

| Tier | Store | Keyable by | Holds |
|---|---|---|---|
| 1 — platform root | `master.key` → HKDF `${SECRET:…}` | the platform | keys WE generate (postgres, minio, jwt) |
| 2 — platform external | ansible vault `${VAULT:…}` | the platform (deploy) | third-party creds the *deployment* needs (`google_client_secret`, one coop-wide Postiz app) |
| 3 — **group** | group secret vault | **group quorum** | per-group service secrets, salt backups, delivery-key material |

Tiers 1–2 are already wired (the `${VAULT:…}` generator hook shipped this
session). Tier 3 is what this note specifies. The tiers are non-overlapping
(delegation-and-session-keys.md §2): platform secrets never enter the group
vault, and group secrets never touch `master.key`/the ansible vault.

## 10. Delegation fit ("the worker is dumb")

The vault's access control *is* the delegation model: a secret is released only
when holder keys — member session keys or granted delivery/agent keys — prove
their authority and the quorum approves. Temporal/workers never read the vault
and never source released secrets into their own env — a released `S` is injected
per-execution into the consuming service, then discarded. A group's delivery key
(delegation §6) is itself a vault entry AND may be a share-holder (§5.1): its
private material is held custodially, its grant scoped, and the Safe remains its
revocation authority.

## 11. Postiz scoping — DECIDED (coop-wide keys)

Postiz integration keys are **coop-wide** (one OAuth app per platform for the
whole irl.coop), so they are **tier-2** material — the ansible vault via the
`${VAULT:…}` generator hook — NOT the group vault. Per-member access tokens are
stored by Postiz per org as usual; only the platform's own app client-id/secret
is a shared secret, and it is platform-authorized. The group vault (tier 3)
stays in scope for genuinely per-group secrets (salt backups, a group's own
service keys), but Postiz does not need it — and no per-tenant credential
injection in the Postiz fork is required.

## 12. Boundary conditions (account-and-key-model.md §boundary, applied)

| Scenario | Response |
|---|---|
| member leaves | drop their wrapped share; re-split if holders < k |
| quorum decay (too few holders alive) | time escalation, not decay: a standing "recovery holder set" (named at formation) + timelock before re-key |
| owner loses their device | their share is wrapped to a *recoverable* member key; recovery = another member re-wraps on a fresh key (never a backend-only path) |
| backend compromise | ciphertext + wrapped shares leak; no plaintext recoverable without k member keys |
| secret leaked | rotate (re-split with a fresh `S`); old shares invalidated by nonce/version bump |

## 13. Open knobs (decide in this order)

1. **k default** — mirror the group Safe's owner threshold, or a separate
   "secret quorum" (default proposal: mirror the Safe threshold).
2. **Granted keys as holders** — may a *granted* key (delivery/agent) carry a
   share, and may that key be custodial (coop-api holds its private half in the
   member's vault slice)? A custodial granted share gives the backend one
   reachable share (still < k, still can't decrypt alone) but lowers the
   live-member bar for scheduled automation. Default proposal: no custodial
   granted shares in v1 (holders are member owner keys only); revisit in v3 when
   delivery/agent keys are live.
3. **Reassembly site** — server-side (simpler, coop-api sees plaintext
   transiently after quorum) vs client-side (S never touches coop-api, harder to
   coordinate). Default proposal: server-side for v1; client-side is the v3
   upgrade.
4. **Share key** — member passkey P-256 (owner key) vs a dedicated vault keypair.
   Default: passkey (no new key, matches EIP-7212).
5. **Ciphertext home** — Citus projection (default) vs MinIO object + pointer.

## 14. Sequencing

- **v1 (pure crypto):** SSS + per-share wrapping + quorum unlock + Citus
  storage + RLS. Proves the primitive end-to-end with no on-chain dependency.
  This is the slice that makes "keys in the group vault" a real place.
- **v2 (on-chain anchoring):** shares encrypted to Safe owner keys; unlock
  requires on-chain `isValidSignature`/EIP-1271 verification against the group
  Safe; unlock/rotate events written on-chain (audit trail).
- **v3 (threshold encryption + automation):** BLS t-of-n (no full-key
  reconstruction), custodial delivery-key share, envelope encryption, client-side
  reassembly — then decide Postiz per-tenant injection.

## 15. What already exists / gaps

Already exists: Safe deploy + modules (`safe.ts`; SessionKeyModule, PasskeyValidator
deployed), `groups`/`group_members`/`resource_scopes` projection (group-scoping.md,
implemented), derived-key + ansible-vault tiers (generator, shipped).

Gaps to build (v1): the two tables (§7), the six routes (§8), client-side
split/wrap (WebCrypto, P-256 ECDH + AES-GCM), server-side interpolate on unlock,
and the audit line. No on-chain work until v2.
