# OPERATIONS-INVENTORY.md — accounts, providers, and dependencies

Status: checkpoint inventory · 2026-09-29.
**No credentials appear in this document, and none should ever be added to it.**
Where a credential exists, only its *storage location by reference* is recorded.
Where a fact was not established, the entry says **Unknown** — do not guess.

> **Recovery procedure status: UNTESTED for every item below.** No owner or successor
> has ever performed a recovery. Treat every "Recovery" cell as an intention.

## 1. Identity of the project

| Item | Detail |
|---|---|
| Project | irl.coop — sovereign cooperation platform |
| Source repository | one repository, remote on a **personal** GitHub account (not an organization) |
| Default branch | `main` |
| Releases / tags | none |
| Authors | one |
| Package registries used | public npm registry for dependencies; **the custom first-party images are not published anywhere** (see §6) |
| CI/CD | GitHub Actions; **one** workflow, covering the dashboard build only. No CI for the API, contracts, or infrastructure |

## 2. Domains and DNS

| Item | Detail |
|---|---|
| Primary domain | `irl.coop` |
| Subdomains in use | identity, app, mail, api, database-tool, object storage, events, farm, and per-group wildcards — all covered by a wildcard certificate |
| DNS provider | named registrar/DNS provider (Gandi), **owner-held personal account** |
| Renewal dates | **Unknown** — not established at the checkpoint |
| Credential location | the provider API key is held in the encrypted repository vault (by reference; do not print) |
| Recovery status | **Untested.** No second account holder, no registrar lock review, no transfer arrangement |

**Hibernation action:** record the domain's expiry date and confirm the account has a
working, monitored recovery email that will still exist in two years.

## 3. Hosting and environments

| Item | Detail |
|---|---|
| Environments | **one** — a single self-hosted machine ("the host"). No staging, no cloud, no failover |
| Second machine | an older edge host on the same LAN, retired; its tailnet route is down |
| Hosting provider | none — self-hosted on owner-controlled hardware |
| Network path | domestic/residential connection with port forwarding; **one** static address and **one** router in the path |
| Hardware inventory | **Unknown** — no written record of disks, CPU, RAM, or spares |
| Recovery status | **Untested.** If the host fails, there is no documented rebuild, no spare, and no image to restore (§6) |

## 4. Data stores

| Store | Detail | Backup |
|---|---|---|
| Relational database | one shared instance; holds the platform projection plus several apps' own databases and roles | **NONE** |
| Cache / pub-sub | one shared instance; keys prefixed per service | n/a (ephemeral) |
| Object storage | one instance; separate buckets for documents, mail, chat media, and project attachments | **NONE** |
| Geospatial data | a large basemap file (roughly 10 GB) held **only** on the host | **NONE** |
| Chain state | none in production; a local development node only | n/a |
| Keycloak | its own database on the shared instance | **NONE** |

**This section is the single largest risk in the project.** `RISKS.md` R-07.

## 5. Notifications, mail, telephony

| Item | Detail |
|---|---|
| Mail server | self-hosted; mailboxes, DKIM, and an internal directory |
| Mail delivery | direct; DNS records for mail authentication are live at the DNS provider |
| Mail authentication posture | SPF and DKIM live; DMARC published but **not enforcing** (D-26) |
| Telephony platform | self-hosted switch (FreeSWITCH/FusionPBX) — running |
| Carrier / DID provider | a commercial carrier (Telnyx) — **owner-held account**; **no number is currently held and no gateway is deployed** |
| Account owner | owner, personal account |
| Recovery status | **Untested.** No record of the carrier account's recovery email or payment method |

## 6. First-party build artifacts (no registry)

Every custom image built for this stack — the custom database-tool bundle, the farm
fork, the event-ticketing gate, the chat clients, the telephony builds, the search
stack, the browser test runner — is built **on the host** and **never pushed to any
registry**. There are thirteen build directories under the infrastructure build tree.

**Consequence:** if the host is lost, these images are lost. Only the build *recipes*
remain, and several depend on fork branches or pinned upstream versions that may no
longer build in two years. `RISKS.md` R-16.

**Hibernation action:** export the images to an off-host location, or verify each
rebuild path end-to-end. This is a prerequisite to any meaningful restore.

## 7. Secrets

| Item | Detail |
|---|---|
| Scheme | most secrets are **derived** from a single 32-byte master key via HKDF; specs reference them symbolically |
| Master key | a single file outside version control, mode `0600`. **The single point of compromise for the whole stack** |
| External secrets | held in an **encrypted ansible vault committed to the repository** (ciphertext); the vault password is itself derived from the master key |
| TLS material | wildcard certificate and ACME state outside version control; renewal is automated with a window guard |
| Third-party credentials | carrier API key, Google brokering secret, and others — location is the vault; **a full list was not enumerated at this checkpoint** |
| In version control | only `.env.example` files. No secret was found tracked |
| Recovery status | **Untested.** No rotation drill has ever been performed |

**Hibernation action (highest priority):** place an offline copy of the master key and
the vault password somewhere that survives the host **and** survives the owner being
unreachable. Without them, nothing derived can be recovered.

## 8. Third-party services and account owners

| Service | Role | Account owner | Billing owner | Recovery |
|---|---|---|---|---|
| Registrar / DNS | domain and DNS | owner (personal) | owner | Untested |
| Carrier (telephony) | DIDs and messaging | owner (personal) | owner | Untested |
| Google (identity brokering) | upstream sign-in for members | owner (personal) | none known | **Unknown** — whether a second admin exists was not established |
| Payment provider (ticketing) | ticket payments | owner | owner | **Not configured** — no keys set, no payments possible |
| Model / AI providers | local inference stack | owner | owner | **Unknown** |
| Blockchain RPC / indexer | **none exists** — no indexer dependency anywhere in the tree, and no production chain-log reader | n/a | n/a | D-21 **is** decided (Base `8453`). But there is no single chain config: `RPC_URL` is not declared in `apps/coop-api.yaml` and four modules default to `http://127.0.0.1:8545` (`safe.ts`, `groups.ts`, `provisioning.ts`, `server.ts`) while `payments.ts` defaults to Base mainnet. The Safe addresses/keys are still Hardhat-local |
| Code hosting | repository | owner (personal) | n/a | **Untested** |

**Every account is held by one person, personally.** There is no organization, no second
admin on any account, and no fiscal sponsor or legal entity (`RISKS.md` R-01, R-03).

## 9. Recovery contact and escrow

| Item | Detail |
|---|---|
| Named successor | **NONE** |
| Recovery contact | **NONE** |
| Escrow arrangement | **NONE** |
| Owner's stated intention | "anyone from a like-minded technology collective or a new-economy coalition… maybe" — explicitly not a commitment |

**This is D-29 and `RISKS.md` R-01.** If the owner is unreachable for two years, no
person is currently identified who could or should continue the project. Nothing in
this repository changes that; only a human decision does.

## 10. Verification record

| Item | Value |
|---|---|
| Last verified date | 2026-09-29 (for the items actually examined in this pass) |
| Verified by | repository inspection, configuration inspection, and read-only host inspection |
| Not verified in this pass | domain expiry dates; hardware inventory; Google account administrators; carrier account details; the complete list of third-party credentials; whether any billing account has a backup payment method |
| Recovery procedures executed | **none, ever** |

## 11. The five actions that matter most

1. **Offline copy of the master key and vault password** (§7) — without these, a lost
   host is unrecoverable.
2. **A verified data backup and restore** (§4) — none exists today.
3. **Export the first-party images off-host** (§6) — otherwise they are gone.
4. **Name a successor, however informal** (§9) — the only item no amount of engineering
   can fix.
5. **Write down the domain and account renewal dates** (§2, §8) — the cheapest way to
   avoid losing the project to an expired card.