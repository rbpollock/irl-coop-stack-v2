# The coop's own accounts, verified from the coop's own number

**Goal (Robbie, Sep 2026).** Stand up irl.coop and have it register its own **Instagram** and
**YouTube** accounts, verifying from **its own DID phone number**.

**And the point of the platform (Robbie, same day).** *"The point of the platform is to help
groups run accounts."* irl.coop is **group #0** — the first user of a capability every group
gets. So the deliverable is not one org's Instagram account: it is that **any group can hold and
operate its own accounts**, and irl.coop proves it by doing it first.

That reframing matters, because it changes what has to be built. The interesting artefact is not
an account — it is the machinery by which a *collective* holds one.

## Where things actually stand (verified, not assumed)

| Piece | State |
|---|---|
| DIDs as a modelled resource | **yes** — `telephony_resources.resource_type` includes `'did'`, provisioned via `coop_provision_telephony_resource` (operator-only) |
| a DID the coop actually holds | **no** — the table has 6 `extension` rows and **zero `did` rows** |
| SMS ingress (receive a text programmatically) | **built, Sep 2026** — endpoint + table + RLS; the GATEWAY is still absent (no app spec, no container) |
| SMS storage / code extraction | **built, Sep 2026** — `phone_message`, code extraction, group-scoped RLS |
| the ingress mechanism, designed | **yes** — `android-mini-services-client.md`: *"TextBee is an open-source Android SMS gateway: a foreground service that exposes an HTTP API and webhooks for send/receive"*, and it names **"two-factor codes"** as a use case, routed through the event bus like every other channel |

So the coop currently **has no number and no way to receive a text**. That — not the account
creation — is the thing standing in the way, and it is entirely buildable.

## The split

### 1. The coop owns a DID — buildable
Ordinary telephony work: acquire a number, land it on the coop's own carrier relationship
(the `did-inventory-forecasting.md` model; the DID carrier is **Telnyx**, one number per group),
provision it as a `did` resource, and point its calls at the coop's voice stack. No platform's
terms are involved yet.

### 2. Texts to that number land in the stack — buildable, and the valuable primitive
TextBee (SIM in an Android device, webhook out) → `POST /api/v1/internal/sms/inbound`
(derived bearer, the same shape as `STALWART_WEBHOOK` / `HI_EVENTS_WEBHOOK`) → a `phone_message`
table with RLS → **extract the code** → surface it. Emit `sms.received` on the event bus so
notifications, digests and the dashboard all consume it via the existing lane.

This is generic on purpose: any service that texts a verification code — a bank, the tax
authority, a platform, a future carrier — lands in the same place, scoped to whoever is seated
to see it. That is worth building regardless of Instagram.

### 3. Platform account creation — **do not automate this**

Not a moral objection; three engineering facts, in order of how much they cost:

- **Their terms prohibit automated account creation.** Instagram and Google both forbid
  creating accounts by automated means. That is a contract term the coop would be breaching
  with its own infrastructure — a bad first move for an organisation whose pitch is
  legitimacy and verifiability.
- **Their anti-bot systems specifically target it** (device fingerprinting, behavioural
  signals, IP and number reputation). The expected outcome of an automated attempt is not
  "account created" but "signup blocked".
- **The attempt can taint the DID — which is the asset.** A number that gets flagged during
  an automated signup is a number that may never verify anything again, for any service. So
  the automation risks destroying the reusable resource in exchange for a likely failure. This
  is the decisive argument, and it is purely practical.

And the deeper question is **ownership, which the number does not solve**: platform accounts
are tied to a *person*. A brand account still has a human owner, transfers are restricted, and
business verification (ads, monetisation, a verified badge) wants entity documents. That is the
same **operating-entity gap** already recorded in `money-in-and-out.md` — the second time it
blocks a goal, which is itself a signal about sequencing.

### So the honest shape of the goal

The group **owns the number and the code path**; **one member completes each signup at the
console** with the code displayed from the group's own number, and the resulting credential goes
straight into the group's vault. Two minutes per platform, once — a *guided, group-owned act*
rather than a member's personal account standing in for an organisation.
Everything except the literal "no human touched it" — and the resulting account is one the coop
can account for, created in a session a human consented to, instead of one that appeared from a
flagged bulk signup and might be removed without notice.

Once the accounts exist, **publishing is legitimately automatable** through the platforms'
official APIs — and the stack already runs **Postiz** (live) for exactly that. So the durable
answer to "the coop posting to its own accounts" is Postiz + real accounts, not a bot that
creates them.

## What a group needs to RUN an account (the real requirement)

Derived from the group's side, not the platform's. Each line is a capability, and the last column
is whether it exists:

| the group needs | why | state |
|---|---|---|
| **a number it controls** | signup, and every future 2FA or recovery text | modelled (`did`), none held |
| **its codes to land somewhere its people can see** | otherwise the account is hostage to one member's phone | designed (TextBee → bus), not built |
| **a home for the credentials** | an org's account secret is exactly a *group secret* | **already in the vault's designed scope** — "Postiz per-group apps, a group's webhook token" |
| **people to act on it WITHOUT sharing a password** | shared credentials are unaccountable and un-revocable | **use the PLATFORM's own role model** (Meta business roles, YouTube brand-account managers), and track the mapping in the coop's grants model |
| **the account to outlive any member** | a departing member must lose access while the group keeps the account | not modelled |
| **governed publishing** | "the group posted" must mean something | Postiz — live, per-group |

**The insight worth keeping:** after setup, the group should not share a login at all. Meta and
YouTube both have first-class multi-user models (business roles, brand-account managers). A group
is better served by *using those* and having the coop record **which member holds which platform
role, since when, granted by whom** — because that is revocable, auditable, and survives
departures, whereas a shared password is none of those things. The credential is then needed only
for API publishing, which is a machine act and belongs in the vault.

So the missing concept is a **group-owned account as a first-class resource**: which platform,
which handle, which number verifies it, where its credential lives, who holds which role on it,
and its lifecycle (created → active → rotated → retired). Nothing models that today.

## Consequence: per-group numbers become load-bearing

A number cannot be reused across groups for verification — platforms block a number that has
already verified an account, so one shared number serves exactly one signup. That turns
`did-inventory-forecasting.md` from a forecast exercise into a **direct dependency of this
capability**: to let N groups run accounts, the coop needs N numbers, each with a phone at a coop node
behind it to receive its texts — the settled node shape, next section.

## The settled shape (Sep 2026) — the coop node

How a group holds its number, decided after working through the alternatives (wholesale DIDs are
VoIP-class and fail Instagram's line-type check at entry; SIM banks / GSM gateways are the detected
SIM-box fraud signature; a eSIM-in-a-VM does not exist because a carrier only provisions to a secure
element). Each line carries a reason.

| decision | what | why |
|---|---|---|
| **device** | cheap, carrier-unlocked Android | the cheapest thing the network classifies as a real mobile line |
| **app** | the coop's own app on the device, with TextBee **integrated** (not a side-loaded third party) | one app is both the phone's brain and the SMS relay; the node is coop-run |
| **where it lives** | a **nearby coop node** — coop infrastructure, physically distributed | custody moves off a member's person and onto the coop |
| **calls in** | forward to the **Telnyx number assigned to that group** | a Telnyx DID terminates in FreeSWITCH (already wired); per-group DID keeps routing unambiguous |
| **calls out** | through the group's Telnyx number | one outward identity, PBX-side |
| **texts out** | TextBee or the Telnyx number | both available for different jobs |

**The inversion that removes the single point.** The SIM in the node is a **radio, not the
identity**. The **Telnyx number is the identity**, and it is coop-held. A node's phone can be lost,
stolen, or its keeper can vanish, and the group is unharmed: drop another SIM in, forward it to the
same Telnyx number, done. This is the same move as Safe-as-deployer and the member-split vault —
custody by the group/coop, not by whoever is physically near the key material.

**Node keeper is caretaker, not owner.** Whoever runs the node holds a phone, not the number; they
can be rotated or replaced without the number moving. The control surface (Telnyx account, port and
forward authority) lives with the group/coop, so a hostile or absent keeper cannot hold the group's
identity hostage.

**Two numbers, two roles — and the premise is human call traffic, not verification.**

The common case is *not* "the occasional code" — it is **groups fielding real human calls**, on farms,
in community spaces, in mutual-aid circles, and *frequently* — because groups aggregate and can forward
a call to a sub-group or a related group's extension. That inverts which layer is load-bearing:

- **SIM number = identity token, nothing public.** What Instagram texts: one-time verification codes,
  2FA. One call at a time, near-zero traffic, sits in a phone, mobile-class. The SIM leaves the room
  the moment real volume enters it.
- **Telnyx DID = the phone system.** *All* human call traffic lands here — a public number sized with
  **channels** and pointed at FreeSWITCH, where ring groups, queues and dialplan do the work. VoIP-class
  is fine because nothing checks its line type.

Two consequences, each load-bearing:

1. **Every group's public DID needs a channel count sized to its traffic**, not the default. A quiet
   mutual-aid group is 2–4 channels; a hotline is 10+. Channels — not SIMs, not phones — are how
   "many simultaneous calls" is served. The SIM is a single-call identity token and must never be the
   public number for a group that takes realtime inbound calls.
2. **Forwarding is first-class, not an edge case.** A call forwarded into FreeSWITCH can be routed to
   another extension, a ring group, a queue, *another group's extension*, or an outside number,
   recursively. That is the platform's point — a "group-aware telephony core" — and it is a dialplan
   capability, gated by a **cross-group forwarding permission** (a governance question: may any group
   forward into any other, or must that be a grant?).

The only concurrency hazard that actually bites is an **unterminated forwarded call**: one stuck call
holds the SIM busy and silently blocks every later caller. The fix is voicemail/timeout on the DID and
PBX — guaranteed-to-terminate dialplan — never more SIMs.

Both surfaces still land in the one spine (`sms/inbound` → `phone_message`); the roles differ in what
they are *for*, not in how their traffic reaches the platform.

**The honest seams, left open on purpose:**

1. **SMS does not ride the call-forward.** `*72` moves voice; the verification code arrives at the
   node's SIM and must be relayed by the app (TextBee) — a human-timed, one-time event, not
   continuous uptime. That is the one reason the phone must exist at all.
2. **The node is a single point until a node is defined.** "Held at a coop node" is the right
   direction but not yet a specification: what a node is, who is keeper, and how it is replaced is
   *wonky at the start and easier later* (Robbie) — worth writing down before the first node exists,
   not after.
3. **The app is deliberately out of scope here** (huge; its own project). The shape above needs only
   the *interface* of that app (SIM SMS listener → `sms/inbound`, alive-check), not the app itself.

## The SIM inventory reality — no free standing numbers

The telephony *DIDs* are forecast-bought stock (`did-inventory-forecasting.md`). The *verification
SIMs* are not the same kind of asset, and the difference matters:

| what you hold | cost | clock |
|---|---|---|
| **unactivated SIM card** (no number) | $2–10 one-time each | **expires** in months–a year (printed on the kit); after that it is dead plastic |
| **activated SIM, no plan / suspended** | sometimes $0 | number expires if the line sits too long without a plan top-up |
| **activated SIM, on a plan** | ~$10/mo each | keeps working while paid |

So "keep a few SIMs on hand" is honest only as **stocking cheap physical *cards* (a consumable with an
expiry sticker), not pre-provisioned numbers.** The *number* is the scarce, identity-bound, ~$10/mo
thing created **on demand** — there is no drawer of ready-to-go phone numbers that survives idle for
free. The card is a $5 consumable you replace like a battery; the number is minted when a group is
ready and paid for from then on.

**The number is KYC-bound by regulation, and that is not optional.** FCC prepaid rules require a named
responsible party on the account. "No KYC" is not achievable for a *real, mobile-class, reaches-
verification* number. The resolution is not to dodge KYC but to **concentrate it once**: the coop (as
its legal entity) KYC's a single time and holds SIMs for groups, exactly as `did-inventory-forecasting.md`
already settles for the carrier-relationship ("KYC concentrates once … one accountable signer"). This
is the same custody move as the vault and Safe-as-deployer — the number is group/coop-held, never a
per-group member's personal identity. *(Open: whether a SIM held for account-verification needs its own
named signer distinct from the DID account, or rides the same one — a procurement question, not yet
answered.)*

## Built (Sep 2026) — the spine, and only the spine

`POST /api/v1/internal/sms/inbound`, authenticated with a derived `SMS_WEBHOOK_TOKEN`, records a
message and extracts its code; `GET /api/v1/groups/:id/sms` and `…/sms/code` serve it to members.
Verified 16/16, including: a gateway RETRY is deduped on (number, external_id); an EXPIRED code stops
being offered; the ingest response does **not** echo the code back to the gateway; and RLS holds — a
member of the owning group reads it, a member of no group reads nothing, and the app role with no
identity reads nothing *while the row demonstrably exists*.

Two properties worth keeping:

- **The gateway never says which group a text belongs to.** The NUMBER maps to a group through
  `telephony_resources`, so a caller cannot attribute a message to a group by claiming it. An
  unprovisioned number is still RECORDED, with no group, because a text that arrived is a fact.
- **The extracted code is a convenience, never an authority.** The raw body is always stored, so a
  wrong guess cannot lose the truth, and nothing may treat `code` as authoritative.

**What this does NOT do.** No gateway is deployed (TextBee still has no app spec) and no DID is held,
so nothing can arrive except from a caller holding the token; there is no read UI; and no bus event
is emitted yet — see the decision below.

### Open decision — the notification policy

The delivery lane claims every event whose type is not `contribution.%` and attempts one delivery per
event. Emitting `sms.received` today would therefore mean **one email attempt per text**, on a lane
whose SMTP path is already failing. That is a policy the lane does not express, so the spine does not
emit yet: a verification code wants a **targeted** surface for the person doing the signup, not a
broadcast message per SMS. Decide the policy (which types notify, through which channel) before
wiring SMS to the bus.

## What I would build first

1. **The SMS ingress** — *built, Sep 2026; see above* — (`/api/v1/internal/sms/inbound` + `phone_message` + RLS + `sms.received`
   on the bus). Buildable now, useful for every future service, and it is the piece the goal is
   actually missing.
2. **Code extraction + surface**: pull a 4–8 digit code out of the body, store it with a TTL,
   and show it where the person doing the signup can read it (dashboard tile / API).
3. **The DID** — Telnyx, one per group, provisioned as a `did` resource and pointed at the
   voice stack (carrier now settled; see "the settled shape").

## Open decisions

1. **The DID's carrier — settled: Telnyx**, one number per group, forwarded from the group's SIM. The
   *aggregator* model was always settled; the specific carrier is now named (see "the settled shape").
2. **Who owns the eventual accounts** — the coop cannot hold them as itself until it legally
   exists, so this is either "a named member, deliberately" or "wait for the entity".
3. **Ingress shape** — TextBee on a device (cheap, no carrier API) vs a carrier SMS API
   (cleaner, recurring cost). The design names TextBee first.
4. **Scoping** — a `phone_message` row is among the most sensitive things the coop could store
   (codes and personal messages). Who may read it: the member whose seat it concerns, a
   bookkeeper-style grant, or an operator for shared numbers.
5. **Cross-group forwarding permission** — may any group forward a call into any other group's
   extension, or is that a *grant* (a governance question the telephony layer surfaces; unresolved).
6. **Peak concurrent callers per group** — the number that sizes each public DID's channels and
   decides queue-vs-ring-group; needs a seed value per group-shape before provisioning.
7. **Whether `mod_callcenter` / queue dialplan is present** — "many simultaneous calls" is served by
   FreeSWITCH queues, not by the SIM; confirm the queue/overflow path is wired before a group goes
   hotline.
8. **The SIM's named signer** — whether a verification SIM needs its own KYC'd signer distinct from the
   carrier/DID account, or rides the same one (see "SIM inventory reality").

## Non-goals

- No automated signup against Instagram, Google, or anything else.
- No browser automation or fingerprint work to get past their detection.
- No dodge of the KYC requirement — the number is KYC-bound by regulation; the move is to concentrate
  it once on the coop, not to evade it with burner SIMs (which would be disposable-class and fail
  verification anyway).
- Not a reason to put the coop's accounts under a member's personal identity without deciding
  that on purpose: **who owns these accounts is a decision**, and it is the same entity
  question as payments.

