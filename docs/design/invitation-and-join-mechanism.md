# Invitation mechanism — design

Status: design (direction being set) · 2026-10-13 · Robbie + Hermes.
Supersedes the *design-by-suggestion* reading of `onboarding-flow.md` Step 5/7 — the invite
was designed on paper but is **unbuilt in code** (self-verified 2026-10-13, see §3). This
documents the mechanism that 1.1's recruitment depends on, and every group after the coop.

---

## 1. Why this is load-bearing, not cosmetic

Phase 1.1 cannot recruit without it. `POST /api/v1/groups/:id/members` (groups.ts:253) seats a
person **who is already a member account** (by `sub`), or a group. There is no path from "a
person who is not in the federation" to "a seated member of the coop group." A returning
operator cannot on-ramp the second and third owner. So the coop group stays stuck at 1-of-1 —
not because nobody wants in, but because there is no door.

And it is not coop-specific: **every group in the federation needs the same two directions.**
Build it once, instance #1 is the coop (§0 of `group-operated-stack.md`).

## 2. What membership means (the reconciliation)

- **D-13:** signup ≠ membership. The moment you sign in you are a *person* (a personal group,
  a Safe), not a member of any named group.
- **§4.3 (a)** of `group-operated-stack.md`: a signin creates a seat; *joining a group is an
  explicit* request. Recommended (a) was accepted.
- **Place of the invitation:** an owner inviting someone IS the acceptance gate. It does not
  bypass §4.3 — it *is* the "accepted request" for that person. Dispatch: a stranger who
  arrives with an invite is not a walk-in; a walk-in who asks to join still has to be
  accepted. Both directions end in the same one row:

  ```
  invites:   owner ──offer──▶ person, person redeems ──▶ seat (roles offered by the owner)
  requests:  person ──asks──▶ owner, owner accepts   ──▶ seat (roles the owner chooses)
  ```

  Symmetric, deliberate, and both are revocable up to the moment of acceptance.

### 2.1 Ownership IS membership — the covenant

"Member" is a loaded word. Membership means **you are on the Safe.** A role is not on top of
membership; a role is a quality of the member. The group's Safe (owner set + threshold) is the
register of who the group is.

There are exactly two member states, and deliberately no third class: **member** (on the
Safe) and **not‑yet‑member**. A person who is not on the Safe is not a class of member at any
point, for any duration.

A non‑member holds **scoped, temporary, revocable access** — a grant for one specific verb
(fill this form, open this doc, claim a slot, join a call). That is a *permission*, not a
status: zero Safe input, exists for the moment it is used, and rides on an invite token or an
open permit. This is where the group's weak ties connect (a bridge is a scoped exchange, not a
crowd), and it is the open door — without installing a ladder or a second rank.

Becoming a **member** is only a deliberate admission event (an invite that grants Safe
ownership, or a Safe admit) — the commitment anchor that makes a co‑op real rather than nominal.

Groups may add their *own* recognition of a recurring non‑member (a "contributor" label with
their own norms) if they wish — welcomed, never mandated by the platform. The platform ships.
**member-or-not plus scoped non‑member access**; it will not force a class grid.

Composability: a working group is a Safe, so its members are its key-holders; the co-op is the
parent Safe. **"Authority" is by which Safe(s) you hold and what their thresholds say** — D-16 (a
seat's holder is a Safe) applied to membership.

## 3. What exists today (verified in code, 2026-10-13)

- `onboarding.ts` — captures `displayName`/`avatar`/`offerings` into the profile. **Creates
  no membership.**
- `POST /api/v1/groups/:id/members` (groups.ts:253) — owner adds a seat by `sub` or a held
  group's `safe_address`. Only for an identity that already exists. **No email, no token.**
- No `invitations`/`join_requests` table anywhere in `src/db.ts`; no invite route; the only
  "invite" strings in the codebase are Matrix room invites and a fake postiz field.
- `onboarding-flow.md` designs the UI (Step 5 "Who are your people?", Step 7 "Invite your
  people") but is a prototype; nothing behind it.

So: **intended, unbuilt.** This doc is the build.

## 4. Data model

Two tables, FORCE RLS (the existing pattern), both seeded and written only through the
system path.

### `invitations` — an offer a group owner makes

| column | meaning |
|---|---|
| `id` | uuid |
| `group_id` | the group being joined |
| `email` | canonical identity to be offered (lowercased) — REQUIRED in v0 |
| `roles` | assignable on redemption, but only from the set granted to the inviter role in group/role config (a plain `member-invite` → `member`; an admin-capable role → admin too) |
| `alias`, `visibility` | invitee seat prefill |
| `status` | `open · accepted · declined · revoked · expired` |
| `expires_at` | default 14 days; forever requires an explicit choice |
| `created_by` / `created_at` | audit |
| `redeemed_sub` / `redeemed_at` | who accepted, when (immutable once set) |
| `nonce` | random; the primary key of redemption (below) |
| `action_kind` | what the invitee is asked to DO on redemption: `form · doc · schedule · donate · call/broadcast` — optional, defaults to a plain land |
| `action_target` | JSON: `{ type, id_or_slug, uri? }` pointing at the specific action (a form, a shared doc, a booking type, a donation object, a call room) |

Unique on `(group_id, email, status='open')` — you cannot double-issue the same standing offer.

**Who can invite — a granted capability, not just an owner.** Creating an invitation (and
seating via it) requires `isOwner(group)` *or* the invitee-side `invite` capability in that
group's role model (`coop_has_grant(group, role, 'member_invite')`, the same
`grants`/`role_grants` machine `members` already use). This is why an invite is a single row
in the existing grants model: **the power to invite is itself a grant** a group can bestow on
a role and revoke, exactly like any other capability — it is not silently attached to
"owner" only.

**An invite can assign a role — but WHICH roles an inviter may assign is declared on the
inviter's OWN role, not derived from what the inviter personally holds.** The capability
is a "may assign: {...}" set in the group's role config. A plain `member-invite` grant
assigns `member`; a role carrying `admin`/`treasurer` assignment may invite-and-assign
those too. Escalation control therefore sits on the group's role graph / consent surface —
the place the group actually decides — a deliberate agreement, not a per-person cap. The
same grant machine (`grants`/`role_grants` + `coop_has_grant`) backs it. Safe-owner / 2-of-3
custody is a SEPARATE plane ruled by the Safe's own threshold: an invitation never grants
Safe custody, no matter what role it assigns.

### `join_requests` — the unbidden offer of a person

|group_id, sub, status (`pending` → `accepted\|declined`), requested_at, decided_by/at| A member or visitor asks; owners accept or decline. Same landing row semantics.

Both FTs collated by `(group_id /* owner views */)` and by `LOWER(email) / sub` (the invitee's
inbox). Status is the only mutable input; `redeemed_*`/`created_*` are immutably written.

## 5. Token & identity binding (the security posture)

The invite link carries a **signed, not secret, token**, so there is nothing to scan in a DB
and nothing that can be regenerated by guessing:

- token = `HMAC-SHA256(payload)` with a derived key `INVITE_SIGNING_SECRET` (added to the
  coop-api app spec, generated from the seed master via the existing `${SECRET:…}` path).
- payload = `inv:<id>:<email>:<exp>` at acceptance we re-check status `open`, re-check expiry,
  and **verify the caller's canonical email against the LIVE Keycloak profile** (the same
  "mint from live profile" invariant that fixed the broker-email leak) — a holder of a link
  cannot claim an invitation for an email they do not control, even if the link is leaked.
- A leaked/circulated link is *expired or revoked*, not scarier: only the identity it names
  can redeem it, and it is single-use.

email delivery: an invite is materialized as a row in the existing `events` outbox (source →
bus → notify lane), so delivery intentionally uses the same lane as everything else — no new
mail path in v0; an email to the invitee is just another notification template.

## 5b. Channels — one token, any door

The invite is **one signed token**; the channel is how that token gets to a person, not a
different kind of invite. You can send the same token over several doors at once, and no
door carries a stronger or weaker permission than the token itself. Revocation, expiry and
single-use apply to the token, not to any one door.

| Door | The token as… | When it's the right one |
|---|---|---|
| **HTTP link** | the base URL every other door is built on | general; the body of email/SMS; anywhere |
| **QR code** | the link rendered to a scannable image | a real room — a meeting, a door, a workshop poster; someone scans it from their phone |
| **Email** | the linked URL in an outbox notification | async, remote — the default on-ramp |
| **SMS** | the same URL via the outbound SMS lane | a person who's phone-first; an invite handed at a bar |
| (later) | Matrix room invite · a print form | reuse existing room/seat mechanics |

Design rules:

- **The QR is a short URL, not a long token.** QR encoding decays with length; a scannable-at-arm's-length code needs a short `/invite/<slug>` redirect whose real check happens on
  redemption against the signed token — the signing secret is the persistent side, and the
  scanned code is just a pointer to it. An ultra-long token is exactly what breaks a QR at arm's length — so the short URL is the point.
- **SMS is outbound-only in v0.** An invite SMS is a *notify*: it rides the same events→bus→notify
  lane as the email outbox, with a `channel: sms` variant, and has **no** relationship to the
  inbound SMS spine (`phone_message`, system-write, deliberately not bus-published). Nobody can
  mint an invite over SMS — only an owner places one — and there is no inbound invite path
  from arbitrary numbers. (A QR-anchored reply is a later, explicit slice.)
- **Fire-and-mark delivery.** The outbox records which door(s) were raised for what; only the
  token state + expiry govern redemption. Sending on a second door never resets the token clock,
  and a failed delivery is a log line, not a weaker token to fall back on.

Adds to the routes list below:

    GET   /api/v1/invitations/:id/qr   (owner)    QR SVG/PNG of the short link

## 5c. The verb — an invite can be an action

The minimal invite is "come sit in the room." The powerful one is **"come and do a thing."**
*An invitation that works names the thing:* fill this form, claim a slot, donate to this
project, come meet us on a call. An invite optionally carries an `action`; when it does,
redemption lands the invitee AT the action, and the seat in the group is offered as the
second step, alongside.

| kind | what they are asked to do | `action_target` points at |
|---|---|---|
| `form` | fill it | a form (e.g. an intake/feedback form) |
| `doc` | open / read / contribute | a shared document (OnlyOffice / files share) |
| `schedule` | claim a booking or appointment | a booking/availability base |
| `donate` | support a treasury project | a donation object / project scope |
| `attend` | join a live call | a LiveKit room / Element-call link |
| `broadcast` | attend a webinar | one-to-many session — flagged apart, see note |

Two halves of one admit: doing the action can require **no membership** (a form is not
member-only by nature), while *taking the seat* remains a separate deliberate step — the
same redeemed token opens both. The invite becomes a directed on-ramp: *do this thing, and
here is the room you are joining.*

**Webinar (`broadcast`) is a flagged open, not a v0 verb.** Real-time one-to-one/many call
already exists (LiveKit + element-call) so `attend` is easy. *broadcast one-presenter-to-many*
with a public watch link, slides, recording, and chat is a different integration that does
not exist. It is booked into §10 (an open, not a default) so the model is not capped on an
unbuilt type; `form / doc / schedule / donate / attend` are the v0 verbs.

Note on `invite` as a role: the ability to invite is **itself grantable** (a role on the
group holds it, wired through the existing grants/role_grants + `coop_has_grant` machine) —
so an invite can only be issued by an owner or a member whose roles include the
`invite`/`member_invite` capability, and only ever *to* roles the inviter holds. This is the
mechanism that keeps a growing group self-limiting, not dependent on owners.

## 6. Routes


```
POST   /api/v1/groups/:id/invitations          (owner)        create offer → returns token/link
GET    /api/v1/invitations/me                  (auth)         list open offers/requests for me
POST   /api/v1/invitations/:id/accept         (auth)         bind + create seat, single-use
POST   /api/v1/invitations/:id/decline        (auth)         mark declined
DELETE /api/v1/groups/:id/invitations/:id     (owner)        revoke while open
POST   /api/v1/groups/:id/join-requests       (auth)         ask to join (a person)
GET    /api/v1/groups/:id/join-requests       (owner)        inbox
POST   /api/v1/join-requests/:id/accept       (owner)        seat the person with chosen roles
POST   /api/v1/join-requests/:id/decline      (owner)
GET    /api/v1/invitations/:id/qr             (owner)        QR render (SVG/PNG) of the short link
```

Mutations go through a system-write function (the existing SECURITY DEFINER pattern, as the
SMS `phone_message` row uses) so FORCE RLS is never bypassed by app-side logic; the owner
check uses the existing `isOwner`.

## 6a. Open permits — the pre‑signed, bounded open door

A group can offer weak‑tie intake without metering each arrival through a threshold vote. A
**permit** = `{ cap, scope (a set of scoped non‑member access grants), subgroup, expires_at }`.
The group can receives it in one threshold act; anyone holding a valid token claims one of `cap`
scoped‑access slots in that subgroup, no further consensus, until it expires or is revoked.
There is no "participant class" — a permit grants access, not a status.

Rules that keep it safe:

- a permit grants only the scopes it names; it is **never** a Safe-owner door, and its
  holders never become members just by holding it — admission to a Safe (ownership) stays a
  named, consented, deliberate event.
- redemption is idempotent and bounded: a server-side counter checks `remaining >= 1`,
  single-use per claimant, safe against races and against a circulating link.
- revocation is immediate: the moment the group revokes the permit, an outstanding claim fails.
- an open permit is cheap precisely because it grants nothing about membership or custody — the
  group is saying "there are up to N people with scoped, revocable access in this subgroup."

This is Granovetter's weak tie made mechanical: the capacity is bounded, so the bridge can grow
a network without the co‑op ever diluting its ownership construct.


## 6b. Payment & the membership covenant (per‑group, never platform‑decided)

What it costs to join (or to be waived) is **the group's own policy**, not the platform's. The
platform provides the rail — a payment that lands in the group's treasury Safe — and honest
defaults. Every group sets its own: amount (zero, nominal, or a deliberate $5k/$100k buy‑in),
form (one‑time buy‑in / recurring membership share), waiver and in‑kind paths, and what happens
to a share on exit. The platform never put in the ceiling.

Two distinguishable notions:

- **entry / buy‑in** — the one‑time seat. In the cooperative shape this is the member share:
  fixed, and usually refundable‑on‑exit (money tied to the member, held by the treasury).
- **dues / recurring** — the steady income that keeps the group running.

The default coop shape is nominal and waivable — *more the lights, present citizenship not
**means* — while a very selective group may place a real buy‑in. Both are the same rail.

The platform's position on "understandability": it is **routing, never custodian, never moving
on the member's behalf**. Joining a Safe with one's own coins is **private-assets-into-private-
vehicle, non-custodial, no intermediary — it is not an AML event**. The only compliance surface
in this stack is the fiat on‑ramp (a card processor's own KYC/AML book, and account‑holder of
that is the group's treasury), never a platform-written file gate for joining a Safe.


## 7. Defaults taken (each reversible; flag, don't wall)

1. **Invite-only for the coop group** to start; the join-request door is OPENED LATER once
   onboarding has a staffed look. (Keeps §4.3 honest and the recursion soft.)
2. **Email is the IDENTITY key**; the door is presentation. Only `email`-keyed human invites
   for v0 (group-to-group and Safe-holder seat-transfer are later, sharing `POST /members`
   holder mechanics) — but that same invite ships by link, QR, email, or SMS. The channel is
   a render, never an identity surface; redemption always re-checks the canonical email.
3. **Expiry 14 days** default; a revoked invite cannot be re-lived except by a fresh one.
4. **Invite doesn't seat anyone automatically** — redemption is the accept; D-13 intact.
5. After redemption the invitee's **first screen is their world with the group seated**, and
   `onboarding-flow.md` Steps 0–7 later re-skin that. v0 ships the mechanism attached to the
   dashboard "invite" button, not a re-designed welcome tour.

## 8. Build slices (order; each independently shippable)

1. **Schema + RLS + system function + token signing** — the tables, the FORCE-RLS wiring, the
   `INVITE_SIGNING_SECRET` derivation, token issue/verify. Nothing user-visible yet.
2. **Owner flow**: create/revoke, list, GET /me — API-level, curl-testable.
3. **Redemption**: accept/decline → seat insert; delivery across the doors — email link now,
   SMS + QR-render next, all via the events outbox/notify lane.
4. **Join-request flow** (reuse Slice 1–3 mechanics).
5. **Dashboard**: "Invite people" button → link; the landing of a redeemed invite; and the
   group-health "1 member → needs-improvement" hint.

Anti-goals: no re-architecting of `group_members`; no new identity system; no redesign of the
whole `onboarding-flow.md` experience; no gate that blocks a stranger without an invite from
*seeing* the platform (they just can't join silently).