# Telephony privacy — split identity, demote the switch, member-owned SFUs

Status: **design** · Aug 2026.
Builds on: [telephony.md](telephony.md) (FreeSWITCH/FusionPBX, extension identity),
[telephony-trunking.md](telephony-trunking.md) (one trunk, per-group caller-ID),
[zk-membership-graph-proofs.md](zk-membership-graph-proofs.md) §8 (derived delivery keys).

## 1. The problem — metadata is the enemy

The current telephony stack hides *content* (SRTP/WebRTC media, coop-issued digest)
and hides *members from the carrier* (one Telnyx trunk = the coop). What it does not
hide is the **call graph**: FreeSWITCH is a softswitch, and a softswitch is a metadata
honeypot — it must see every call record (who-called-whom, when, from what IP, how
long) to route the call.

Worse, that metadata is **identity-linked**: `ensurePersonalTelephony` allocates a
sequential numeric extension (`MAX+1` → 200, 201, 202…), and the resolution chain is
`sub → own group → extension`. The switch's CDR literally reads "201 (Robbie) called
205 (Sarah), from IP X." Enumerable, and permanently linked.

## 2. The split-identity model

Split the **stable dialable identity** (what people see) from the **rotating reachable
address** (what the switch sees) — the stealth-address analog:

- **Dialable handle** — a stable group DID / contact entry. What humans dial.
- **Routing AOR** — an opaque, rotating SIP token `H(sub, rotation_epoch)`, unlinkable
  to the person and re-issued on a schedule so CDR from one epoch cannot be joined to
  the next.

The `token → sub` mapping lives RLS-scoped in the projection (only coop-api + the
member read it); FusionPBX's `v_extensions` stores the token, never a name. The
dialplan resolves `stable-handle → current-token` via a coop-api lookup at call time
(the existing mod_lua `xml_handler` seam — no new plumbing).

## 3. Phase 1 — opaque rotating SIP identities

- Replace numeric `MAX+1` allocation in `ensurePersonalTelephony` with an opaque
  token (random, or derived `H(sub, epoch)`).
- `telephony_resources.external_ref` = the token (it already is the "SIP username").
- Rotation: a Temporal workflow re-issues tokens; a member re-registers silently with
  the fresh token (the browserphone refetches `/api/v1/telephony/sip-config`).
- Result: the switch's CDR is pseudonymous and non-accumulating — it cannot name or
  long-term-profile anyone.

This is a clean, high-value change to code that already exists. Do it first.

## 4. Phase 2 — media off the switch

FreeSWITCH `bypass_media` / re-INVITE so internal WebRTC media flows browser↔browser
through coturn, never hairpinning through FreeSWITCH. The switch relays signaling
only — content is no longer in the platform's hands at all.

## 5. Phase 3 — internal calls leave the switch

Internal coop-to-coop calls become **P2P WebRTC signaled over Matrix** (already E2E).
FreeSWITCH is demoted to a **PSTN gateway only**: it (and Telnyx) touch nothing but
calls that cross to real phone numbers. For internal calls there is no switch logging
a call graph at all.

## 6. Member-owned SFUs — group conferencing without a platform media server

P2P mesh does not scale (O(N²) uploads, ~4–6 participants). The efficient N-to-1-to-N
shape needs an **SFU** — a relay that forwards each participant's single upload to the
others. The privacy properties depend on where it runs and what it can see:

| Shape | Media path | Sees | Scales |
|---|---|---|---|
| **P2P mesh** | participant↔participant | nothing central | poor (≤ ~6) |
| **Platform SFU** | via irl.coop's server | content + metadata (unless E2EE) | good |
| **Member-owned SFU** | via a *peer's* server | metadata only (E2EE) | good |
| **MCU (decode-mix)** | via a mixer | content (decodes) | good, avoid |

The coop shape is the **member-owned SFU with end-to-end encryption**:

- **E2EE SFU** — the SFU forwards SFrame / WebRTC-insertable-stream ciphertext it
  cannot decrypt (W3C Encoded Transform; IETF `draft-ietf-sframe-enc`). It sees RTP
  metadata (who is in the call, packet sizes/timing) but **not content**.
- **Member-owned** — the SFU is a *group resource* running on a peer's hardware (or a
  group-controlled box), not the platform's. The platform's media-plane surveillance
  drops to zero; the only metadata observer is a peer the group itself chooses.
- **Keying** — the conference E2EE key is distributed over the group's Matrix room
  (already E2E), so the SFU host never learns the key either.
- **Tooling** — LiveKit or mediasoup (both ship E2EE via SFrame/insertable streams),
  with coturn for the SFU's NAT traversal. The group's existing media grants
  (`media.stream.view` / `media.stream.broadcast`) gate who may host/join.

**Governance** — "member-owned" is a group decision, not a platform assignment: the
Safe/seat model designates a **media host** (a member with `media.stream.broadcast`
who volunteers hardware), exactly like any other group resource. A host leaving is a
re-provision, not a platform outage.

**Honest limits** — an SFU still sees *metadata* (who is in the call, when, packet
traffic). Member-ownership moves that from "the platform sees it" to "a peer you
choose sees it"; it does not eliminate it. True metadata-hiding for multi-party calls
(onion/mixnet-style SFUs) is research-grade and out of scope.

## 7. Trade-offs (do not hand-wave)

1. **Group features break** under full P2P — ring groups/queues/conferencing need a
   relay. The member-owned SFU is the answer for conferencing; a ring group still
   leaks *membership structure* (the switch sees "these N tokens rung together") and
   is best fan-out P2P.
2. **Background ringing is a privacy leak** — the "linked number" PSTN-forward
   (telephony-trunking.md) forwards to the member's real mobile number, re-linking
   them and exposing the number to the carrier. Must be **opt-in and flagged**.
3. **PSTN can never be metadata-private** — real numbers + carriers + STIR/SHAKEN +
   lawful intercept/e911 are a permanent surveillance surface. The answer is
   *minimize what crosses it* (keep internal calls internal), not hide it.
4. **e911 / legal intercept** — the PSTN gateway cannot disappear; it stays, scoped to
   the minimum.

## 8. Sequencing

1. **Phase 1** (opaque rotating SIP identities) — code exists, high value, low risk.
2. **Phase 2** (media off the switch) — FreeSWITCH config change.
3. **Member-owned SFU spike** — LiveKit/mediasoup + SFrame E2EE on a peer box, keyed
   over Matrix; proves the conferencing path before Phase 3.
4. **Phase 3** (internal calls P2P over Matrix; switch = PSTN only) — last, gated on
   the SFU spike and the group-features/background-ringing trade-offs above.
