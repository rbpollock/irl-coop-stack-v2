# Telnyx Wireless SIM → the coop's PBX

**Question (Robbie, Sep 2026):** can a Telnyx Wireless SIM be pointed at the coop's PBX?
**Answer:** yes — the SIM *and* the SIP trunk are the same vendor, so Telnyx's voice stack is the
meeting point. But the SMS half and the *line type* of the SIM's number are where the plan earns its
keep or falls over. Checked 2026-09-13; sources at the end.

## The two things that meet in the middle

Telnyx is unusual in selling both sides of the handoff on one carrier network:

- **The Wireless SIM** (`/sim_cards`) — eUICC-enabled, an `enable_voice` action assigns a real `+E.164`
  mobile number (a `mobile_phone_number` resource), with SMS/MMS/RCS on the same number and multi-IMSI
  (it can attach as T-Mobile or US Cellular rather than roam).
- **The Elastic SIP trunk** (`SIP Connections` + Outbound Voice Profiles) — the very trunk the coop's
  FreeSWITCH/FusionPBX already terminates VoIP numbers on.

Because both are Telnyx, the SIM's number can be steered through the same Call Control / routing that
a plain DID already uses — so a call or SMS arriving at the SIM's number terminates in the PBX like
any other number the coop owns.

## Two ways to wire it

**1. SIM number → Telnyx voice → PBX (the SIM supplies the number, the PBX supplies the brain).**
Enable voice on the SIM; point the resulting `mobile_phone_number` at a `Mobile Voice Connection`,
whose `connection_id` / webhook / inbound-route knobs carry calls into the existing Telnyx-side
routing and on into FreeSWITCH. The SIM's number then *behaves* like a DID the stack already knows:
IVR, dial-plan, ring groups, all unchanged. This is the least-new-engineering path.

**2. The SIM as a SIP endpoint (the device registers itself).**
The module-side stack (ModemManager + a softphone, or TextBee's app) registers to FreeSWITCH directly
as a SIP client, and the mobile number rides the cellular data path. This makes the *device* first-class
in the PBX, but it is the more fragile of the two — it depends on what the module firmware exposes.

## The SMS half, which is the part the platform actually needs

The verification code Instagram sends does **not** arrive over the voice path — it is an **SMS to the
SIM's number**. Two routes for it:

- **Telnyx Messaging webhook → `apps/coop-api/src/sms.ts`.** Inbound SMS to the SIM's number hits
  Telnyx Messaging, which forwards the message + the source number as a webhook. That is the same shape
  the spine already accepts — `POST /api/v1/internal/sms/inbound`, whose only requirement is the derived
  bearer token. So the SIM's number, like a TextBee device, becomes one more gateway in front of the
  one built path.
- **On-module delivery** to the device's own SMS stack (gammu/ModemManager), then TextBee → the spine.

Either way the code lands in `phone_message` and is served to the owning group's members through the
RLS already in place.

## The discovery that changes the test order

Telnyx's own **Number Lookup API** — the service it sells for *"line type intelligence … mobile,
landline, or VoIP"* — returns `type: "voip"` for a Telnyx-owned number in its own documented example
(`+13129457420 → carrier.name "Telnyx/4", carrier.type "voip", portability.line_type "voip"`). That is
Telnyx's carrier data describing a Telnyx number as **VoIP-class** — the exact class Instagram's
line-type check rejects *before* it sends a code, and the reason the DID comparison chose SIMs over
trunks in the first place.

**The open question is therefore first, not last:** does a *Wireless* SIM's `enable_voice` number
report as `mobile`, or does it inherit the VoIP class of Telnyx's other numbers? A programmable SIM's
MSISDN may chart differently from a trunk number — but it may not, and the whole SIM→PBX plan for
*verification* numbers hangs on it.

**The test that settles it costs $0.0015 plus the SIM:** order one SIM ($1), enable voice, and run
Telnyx's own Number Lookup against the assigned number. `carrier.type` says `mobile` or `voip`. If it
says `mobile`, the SIM path works for verification AND terminates in the PBX — the best of both. If it
says `voip`, the SIM still feeds the PBX for *infrastructure* numbers, but **verification numbers stay
on real phones**, and nothing in this note should be read as having decided otherwise.

## What this does and does not change

| | changes |
|---|---|
| **Infrastructure numbers** (voice, IVR, member notices) | the SIM can carry these into the PBX today — no open question |
| **Verification / 2FA numbers** | still *undecided* until one Number Lookup on the SIM's number |
| **SMS path into the stack** | unchanged — still `sms/inbound`, SIM and TextBee are two gateways to the same spine |
| **the entity catch** | unchanged — a Telnyx account and its numbers belong to whoever signs |

## Open decisions

1. **Run the $3 test** — one SIM, `enable_voice`, one Number Lookup. This is the single cheapest
   experiment that resolves whether SIM-fed PBX numbers can also be verification numbers.
2. **Which PBX wiring** — option 1 (SIM number routed like a DID) is the low-engineering default;
   option 2 (SIP endpoint) only if the module proves it out.
3. **SMS route choice** — Telnyx Messaging webhook vs on-module, decided after the SIM's SMS is proven
   to reach either end.

## Sources

| what | source | read |
|---|---|---|
| Telnyx Wireless: eUICC SIMs, enable_voice → real number, SMS/MMS/RCS, multi-IMSI | developers.telnyx.com/docs/iot-sim (wireless-overview, get-started, mobile-phone-numbers) | 2026-09-13 |
| Elastic SIP trunk = SIP Connections + Outbound Voice Profiles | devdocs.telnyx.com SIP trunking getting-started; support.telnyx.com SIP trunk / connection settings | 2026-09-13 |
| Number Lookup API returns carrier.type "voip" for a Telnyx-owned number | developers.telnyx.com identity/number-lookup (quickstart + schema) | 2026-09-13 |
| Line-type intelligence framing (mobile/landline/VoIP, HLR) | telnyx.com/products/number-lookup | 2026-09-13 |
