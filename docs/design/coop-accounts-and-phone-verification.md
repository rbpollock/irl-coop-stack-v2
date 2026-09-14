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
| SMS ingress (receive a text programmatically) | **no** — no inbound endpoint, no app spec, no container |
| SMS storage / code extraction | **no** — no `phone_message`-like table exists |
| the ingress mechanism, designed | **yes** — `android-mini-services-client.md`: *"TextBee is an open-source Android SMS gateway: a foreground service that exposes an HTTP API and webhooks for send/receive"*, and it names **"two-factor codes"** as a use case, routed through the event bus like every other channel |

So the coop currently **has no number and no way to receive a text**. That — not the account
creation — is the thing standing in the way, and it is entirely buildable.

## The split

### 1. The coop owns a DID — buildable
Ordinary telephony work: acquire a number, land it on the coop's own carrier relationship
(the `did-inventory-forecasting.md` model; the carrier relationship is settled as *aggregate*),
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
capability**: to let N groups run accounts, the coop needs N numbers, each with a phone or a
carrier API behind it to receive its texts.

## What I would build first

1. **The SMS ingress** (`/api/v1/internal/sms/inbound` + `phone_message` + RLS + `sms.received`
   on the bus). Buildable now, useful for every future service, and it is the piece the goal is
   actually missing.
2. **Code extraction + surface**: pull a 4–8 digit code out of the body, store it with a TTL,
   and show it where the person doing the signup can read it (dashboard tile / API).
3. **The DID**, when a carrier is chosen, provisioned as a `did` resource and pointed at the
   voice stack.

## Non-goals

- No automated signup against Instagram, Google, or anything else.
- No browser automation or fingerprint work to get past their detection.
- Not a reason to put the coop's accounts under a member's personal identity without deciding
  that on purpose: **who owns these accounts is a decision**, and it is the same entity
  question as payments.

## Open decisions

1. **The DID's carrier** — the aggregator model is settled; which carrier is not.
2. **Who owns the eventual accounts** — the coop cannot hold them as itself until it legally
   exists, so this is either "a named member, deliberately" or "wait for the entity".
3. **Ingress shape** — TextBee on a device (cheap, no carrier API) vs a carrier SMS API
   (cleaner, recurring cost). The design names TextBee first.
4. **Scoping** — a `phone_message` row is among the most sensitive things the coop could store
   (codes and personal messages). Who may read it: the member whose seat it concerns, a
   bookkeeper-style grant, or an operator for shared numbers.
