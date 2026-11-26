# irl.coop Local Election Fundraising — An Alternative to ActBlue

**Status:** Design document — aspirational; ready for pilot scope review  
**Scope:** A sovereign, hyperlocal donation pipeline for local elections (school board, city council, county office) built on irl.coop Group Safes, USDC rails, and voluntary federation.  
**Owner:** irl.coop product design  

---

## 1. Core Problem

ActBlue solves national-scale Democratic fundraising, but it is a **centralized, for-profit platform** with opaque fees, little local control, and no structural support for non-partisan or hyperlocal races.  

Local races (especially school board) need:
- **Low per-donation cost** — many $5–$50 contributions, not $500 events.
- **Transparent custody** — donors see exactly where funds sit and how they move.
- **Community control** — the campaign is a group, not a vendor account.
- **Cross-campaign solidarity** — a donor to one school-board race can opt-in to support a neighboring race without re-entering payment details.
- **Minimal compliance overhead** — automatic receipt, aggregation reports, and disbursement traceability.

irl.coop already has the primitives: Group Safes (ERC-4337), card-to-USDC rails, per-group SMS identity, and the event bus. This design wires them into a **local-election donation layer**.

---

## 2. Guiding Principles

1. **Campaign = Group.** Every candidate or slate is an irl.coop group with its own Safe. No platform-level commingling.
2. **Donor = Member.** A donor need not be a full voting member, but they hold a read-only or donor-level membership seat that emits a ZK-badge.
3. **Federation, not aggregation.** Neighboring groups can mirror donation pages or pool ad-buy funds via cross-group intents, but ownership stays atomic.
4. **USDC-native, card-accepting.** The donor sees dollars; the Safe receives USDC on Polygon or Base. The candidate cashes out to a local bank via an off-ramp (bridge to a community bank or CU).
5. **Compliance as code.** Disbursement rules are Safe guards: signatures from both campaign treasurer and a compliance steward are required once cumulative receipts hit reportable thresholds.

---

## 3. Architecture

### 3.1 Stack Mapping

| Layer | irl.coop Primitive | Election Role |
|-------|-------------------|---------------|
| Identity | Keycloak realm `irl.coop` + cert chain | Donor login, treasurer auth |
| Funds | Group Safe (ERC-4337) + USDC | Campaign treasury |
| Inbound | `peer_xyz_payments` (card → USDC) | Donation processor |
| Outreach | Per-group SMS via Telnyx + Matrix | Text-to-donate, volunteer coordination |
| Governance | Event bus `intents` + `safe_events` | Disbursement approvals, slate pooling |
| Reputation | ZK-badge bond + regenerative score | Verified-local-donor badge, public matching |
| Reporting | NocoDB/ERPNext | FEC/state filing aggregation |

### 3.2 The Donation Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌─────────────┐
│   Donor     │────▶│  Donation UI │────▶│ peer_xyz_payments│────▶│ Group Safe   │
│  (public)   │     │ (campaign page│     │  card → USDC     │     │ (campaign)   │
└─────────────┘     └──────────────┘     └─────────────────┘     └─────────────┘
       │                                       │                        │
       │                              ┌────────┘                        │
       │                              ▼                                 │
       │                    ┌─────────────────┐                         │
       │                    │  Compliance Bus  │◀────────────────────────┘
       │                    │  `safe_events`   │   (deposit intent)
       │                    └─────────────────┘
       │                              │
       └──────────────────────────────┘
            (email/SMS receipt via Telnyx webhook)
```

**Steps:**
1. Donor visits `campaign-slug.irl.coop/donate` (or clicks a text-to-donate link).
2. UI renders from the campaign group’s NocoDB base — **no shared platform landing page**.
3. Donor enters amount, email/phone, employer/occupation (compliance fields stored encrypted in the group’s Citus shard).
4. `peer_xyz_payments` charges card and mints USDC into the campaign Group Safe.
5. Bus emits `safe_events` deposit with attached compliance payload.
6. Donor receives SMS receipt; campaign treasurer receives Matrix alert.

### 3.3 The Disbursement Flow

Campaigns spend money. Disbursement is a **governed Safe transaction**.

```
┌──────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Treasurer   │───▶│  Intent: payout  │───▶│  Group Safe     │
│  (member)    │    │  to vendor/off-ramp│   │  threshold=2    │
└──────────────┘    └──────────────────┘    └────────┬────────┘
                                                     │
       ┌─────────────────────────────────────────────┘
       │
       ▼
┌──────────────────┐    ┌─────────────────┐    ┌──────────────┐
│ Compliance Steward│───▶│  Safe exec      │───▶│  Vendor /    │
│  (second signer) │    │  (ERC-4337)     │    │  Local bank   │
└──────────────────┘    └─────────────────┘    └──────────────┘
```

- Any spend over a configurable threshold (e.g., $100) requires two signatures.
- The bus `intent` block records the vote.
- Spending to an address not on the campaign’s pre-approved vendor list triggers a time-delay (e.g., 24h) and Matrix notification to all stewards.

---

## 4. Hyperlocal Features

### 4.1 Text-to-Donate via Telnyx

Each campaign group receives a Telnyx DID (or shares a pooled DID with keyword routing).

```
Donor texts "GIVE 25" to +1-XXX-XXX-XXXX
        │
        ▼
┌─────────────────┐
│  webhook hits    │
│  /webhooks/sms   │
└─────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│ 1. Keyword maps to campaign group_id    │
│ 2. Auto-reply with secure checkout link │
│ 3. Donation page pre-fills $25 + phone  │
└─────────────────────────────────────────┘
```

### 4.2 Public Matching via ZK Badge

Municipalities or advocacy allies may offer matching funds. irl.coop can prove:
- Donor lives within district (verified via address attestation, not doxxed).
- Donor has not exceeded per-person limits.

A **ZK-badge** is issued per donation:
```json
{
  "badge_type": "verified_local_donor",
  "district_hash": "0xabc...",
  "amount_range": "10-100",
  "campaign_epoch": 2026,
  "nullifier": "0xdead..."
}
```
The campaign submits an aggregate ZK proof to the matching authority without revealing individual donor identity.

### 4.3 Slate Pooling (Cross-Group Intents)

Neighboring school-board candidates can form a **Slate** — a transient multi-group intent.

```
Slate intent:
  - Group A: donate 20% of overflow to Slate
  - Group B: donate 20% of overflow to Slate
  - Group C: donate 20% of overflow to Slate
  - Threshold: 2 of 3 groups sign
  - Action: Safe CreateCall deploys a joint ad-buy Safe
```

This is **not** a PAC. It is a time-bounded, revocable joint intent with on-chain traceability.

---

## 5. Compliance & Reporting

### 5.1 Data Model (per campaign group)

🔹 `donors` (RLS-protected Citus table)
| Field | Type | Note |
|-------|------|------|
| donor_id | UUID | internal only |
| email_hash | HMAC | for deduplication, not reversible by platform |
| phone | E.164 | for SMS receipts |
| employer | text | compliance |
| occupation | text | compliance |
| district_hash | HMAC | for matching eligibility |
| total_ytd | numeric | running sum per election cycle |

🔹 `donations` (bus-enriched)
| Field | Type |
|-------|------|
| donation_id | UUID |
| safe_tx_hash | bytes |
| amount_usdc | numeric(10,2) |
| timestamp | timestamptz |
| intent_id | UUID (references bus) |

### 5.2 Filing Triggers

- **Daily:** NocoDB view aggregates receipts by employer/occupation buckets.
- **Crossing $1,000:** Automatic Matrix alert to campaign treasurer + compliance steward.
- **Crossing state reporting threshold:** Bus emits `external_cb` to ERPNext, which generates a pre-filled report PDF for the treasurer to file.

### 5.3 Refunds

Refunds are Safe outflows back to donor address (or fiat off-ramp if donor lacks a wallet). Requires treasurer + steward signature and emits `safe_events` refund.

---

## 6. Trust & Risk Model

| Threat | Mitigation |
|--------|------------|
| Treasurer steals funds | Safe threshold >= 2; steward is a non-candidate community member |
| Fake campaign | Group creation requires bond + ZK-badge; platform steward reviews before DID is issued |
| Donor data leak | Compliance data never leaves campaign group shard; platform sees HMAC hashes only |
| Card fraud | Standard `peer_xyz_payments` fraud rules; no crypto-asset custody by platform |
| Regulatory disallowance of crypto | USDC held in campaign Safe is legally a contribution at point of card charge; off-ramp to compliant bank account is campaign’s responsibility |

---

## 7. Pilot Definition (MVP)

1. **One race.** A single school-board or city-council race in a municipality where the candidate already has an irl.coop group.
2. **Card-to-USDC only.** No direct-wallet donations in pilot.
3. **One disbursement pattern.** Vendor list = {local printer, local bank off-ramp}. No slate pooling yet.
4. **Compliance export.** CSV from NocoDB, hand-uploaded to state election site.
5. **Metric:** Time from donor clicking link to USDC arriving in Safe < 30 seconds; total platform fee < 3%.

---

## 8. Open Questions

1. Which off-ramp partner (Bridge, Circle, Coinbase Prime, or a credit-union API) gives the best rail for a hyperlocal campaign needing same-day fiat settlement?
2. Should the platform charge a flat SaaS fee per campaign group, or a percentage of USDC throughput?
3. How do we handle employer/occupation validation without becoming a data honeypot?
4. Does any state election law explicitly treat USDC-in-a-Safe as "in-kind" vs. "cash," and does that change reporting categories?

---

*Last updated: 2026-11-20*
