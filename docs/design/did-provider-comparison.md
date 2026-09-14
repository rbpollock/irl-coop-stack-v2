# DID + SMS providers, compared for cost and "unlimited"

**Question (Robbie, Sep 2026):** which DID provider is best, on cost and unlimited usage?
**Prices below are list rates checked 2026-09-13, with sources.** Negotiated and volume rates differ;
treat every figure as a dated observation, not a commitment.

## First: the finding that decides it

**A wholesale DID cannot verify an Instagram or YouTube account.** Instagram runs a **carrier /
line-type lookup (HLR) at the moment the number is typed, before any SMS is sent** — numbers that
come back `VOIP`, `FIXED_VOIP` or `NON-GEOGRAPHIC` are rejected outright ("invalid phone number" /
"number not eligible"), and a rejected number can be flagged for later reuse. Numbers from Twilio,
Telnyx, VoIP.ms and Callcentric are all **VoIP-class** however real they look on a bill.

**A real cellular (SIM) number passes**, because at the network level it *is* a mobile number. That is
what the TextBee path in `android-mini-services-client.md` already implies — an Android device with a
SIM — and it is also, by a wide margin, the **only genuinely "unlimited" option that exists** here.

So the comparison splits by purpose, and no single provider wins all three.

## Prices (list, 2026-09-13)

| provider | DID / mo | SMS to enable | SMS per message | voice in | voice out | "unlimited"? |
|---|---|---|---|---|---|---|
| **Telnyx** | **$1.00** (volume: $0.79 → $0.25 at 50+ numbers) | **+$0.10/mo** | **$0.004** + carrier passthrough | $0.0032/min | $0.005/min | no per-DID unlimited; per-minute, no channel fee claimed |
| **Twilio** | $1.15 local · $2.00 toll-free | included | $0.0083 + carrier | $0.0085/min | $0.0140/min | no |
| **VoIP.ms** | $1.10 (from $0.85) | included | $0.0075 | $0.009/min | $0.01/min | **$4.25–4.95/mo per DID unlimited INBOUND** |
| **Callcentric** | Personal Unlimited **$5.95** · Office Unlimited **$8.95** · Service Provider Unlimited **$19.95** | SMS Access Plan $1 (Basic) / $2 (Pro) | $0.010 / $0.008 | **$0.00/min** | separate per-minute plans | **yes — flat per-number, $0.00/min, unlimited channels** (SP tier: 1,600 rate centers, IVR/call-centre/resale explicitly allowed) |
| **Prepaid SIM** (e.g. Tello) | n/a — a SIM | n/a | plan-included | n/a | n/a | **yes — $8/mo unlimited talk + text** (0 GB data; the device lives on WiFi) |

**Emergency calling** (E911) is extra nearly everywhere: Telnyx $1.50/mo per number, VoIP.ms $1.50/mo
plus $1.50 activation.

**A2P SMS registration (10DLC) applies to API-based sending to US numbers** and is a *separate* cost
from the number: sole-proprietor brand **$4–24.50 one-time + $2/mo per campaign** (no EIN or entity
needed); registered-business brand **$39–71.91 one-time + $10/mo per campaign** (entity required).
Vetting takes 1–3 days, up to 15 with some providers. A campaign can hold at most 43 DIDs on VoIP.ms;
one mobile number can register at most 3 sole-proprietor brands.

## What this means for the coop — three purposes, three answers

**1. Group account verification and ongoing 2FA → a SIM, and only a SIM.**
$8/mo unlimited talk+text, a real mobile number, and it keeps working for the account's 2FA years
later. This is also where the scaling limit becomes physical rather than financial: **N groups need N
SIMs in N (or dual-SIM) devices**, because a number can only verify accounts for one group. Rentable
SIM-backed verification numbers exist, but a one-time rented code cannot answer a 2FA prompt in 2028 —
and a number you do not hold is a number you can lose the account with. Ops cost is hardware and
SIM management, not API spend.

**2. The coop's own voice estate (FreeSWITCH/FusionPBX, group dial-in, IVR) → Callcentric or VoIP.ms for "unlimited".**
- **Callcentric's Unlimited tiers are the only true flat-rate voice**: $0.00/min, unlimited channels,
  and the Service Provider tier ($19.95/mo + $19.95 setup) is explicitly licensed for IVR, call
  centres and resale. Personal/Office tiers are cheaper ($5.95/$8.95) but capped at 2–3 channels and
  restricted in purpose.
- **VoIP.ms** is the cheapest unlimited *inbound* at $4.25–4.95/mo per DID on top of a $1.10 DID, with
  per-minute outbound ($0.01).
- **Telnyx** is cheapest for *metered* use and the only one of these that owns its network and
  publishes carrier passthrough at cost.

**3. Sending SMS to members at scale → Telnyx, at $0.004/part.**
Cheapest list rate of the four, plus a $0.10/mo capability add-on and +carrier fees. **Callcentric is
disqualified for this entirely** — its own SMS page states *"A2P/Bulk/Commercial Messaging: No"*, plus
no MMS and no international SMS. VoIP.ms caps its API at 100 messages/day, which is a hard ceiling for
anything coop-wide.

**"Unlimited" is a hosted-voice concept, not a wholesale one.** For per-message SMS there is no
unlimited tier anywhere; and for voice, at $0.0032–0.01/min a coop's usage is rounding error, so what
actually scales is the **per-number** charge — which is why the count of numbers a group needs (one per
group, for verification) is the number that matters.

## Consequence for this repo's own numbers

The cost model carries **"3 × $1.50/mo illustrative"** for DIDs. These sourced rates ($1.00–1.15 for
metered, $4.25–5.95 for unlimited-inbound) would replace it — **not changed here**, because a cost-model
edit goes through `cost-model.data.json` and its harness, and the count of numbers is still an open
decision in `did-inventory-forecasting.md`.

## Open decisions

1. **Carrier vs MVNO for group SIMs** — postpaid from a major carrier is reported as the most reliable
   for platform verification; MVNO prepaid (Tello at $8) is mobile-class and much cheaper. Test one of
   each before committing numbers to groups.
2. **Who owns the SIM and the account** — a prepaid SIM in a device the coop holds is the coop's; the
   *account* is still tied to a person (see the ownership section in
   `coop-accounts-and-phone-verification.md`).
3. **10DLC brand per group?** — if a group sends A2P SMS, compliance wants its own brand + campaign,
   which needs entity details. Another argument for keeping per-group messaging on SIMs and reserving
   API SMS for the coop's own notifications.
4. **The gateway** — TextBee is self-hostable, multi-device, and free (REST API + webhook), which fits
   the inbound path built in `apps/coop-api/src/sms.ts`. No app spec exists yet.

## Sources

| what | source | read |
|---|---|---|
| Telnyx numbers, SMS, SIP rates; competitor comparison table | telnyx.com/pricing/numbers, /pricing/messaging, /pricing/elastic-sip | 2026-09-13 |
| Twilio number prices | telphiconsulting.com/blog/twilio-cost-2026, getpricepulse.com | 2026-09-13 |
| VoIP.ms DID, minutes, SMS, unlimited inbound, 10DLC limits | wiki.voip.ms/article/Service_Cost, prospeo.io VoIP.ms pricing | 2026-09-13 |
| Callcentric unlimited tiers + SMS plans + A2P prohibition | callcentric.com/dids/service_provider_unlimited, /office_unlimited, /personal_unlimited, /sms/, /faq/44 | 2026-09-13 |
| 10DLC brand/campaign fees | gohighlevel.com A2P 10DLC guide, bluereacher.com/a2p-10dlc, hexalevel.com, tuco.ai | 2026-09-13 |
| Instagram/Google reject VoIP-class numbers via HLR at entry | smsverifier.com, smscode.gg, pvapins.com, verifypulse.com, cyberyozh.com | 2026-09-13 |
| Tello $8/mo unlimited talk+text; US Mobile | moneysavingpro.com, tello.com/buy/custom_plans, switchninja.app | 2026-09-13 |
| TextBee (self-hosted, multi-device, REST + webhook) | github.com/textbee/textbee, textbee.dev | 2026-09-13 |
