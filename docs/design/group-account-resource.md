# The account resource — and the group operations that move custody

**Status: design (scoped, v1-in-scope, not built).** The durable identity that holds accounts is
*not* "a group" in the membership sense — it is **"a thing that outlives any single person."** A coop
is one such thing; **an individual planning a will is another.** The account resource is *one surface*
that group *operations* act on — it is not the whole story, and it is not a "key solution." It sits
inside a wider suite of **group operations** (dissolve, absorb, devolve, delegate, succeed, merge, and
ones still being discovered) that move custody of *everything* a group holds — accounts, funds, DIDs,
seats, spaces, publishing — not just credentials.

## The one insight that collapses the scope

The "group" in "group-account resource" was never really *group* — it was **"a durable identity whose
holdings survive the departure or dissolution of whoever set them up."** The stack already models this:
`groups` has a `kind` (`coop` | `personal`), and a **personal group is a user's own identity**
(`created_by` → one per `sub`, enforced at the DB level, `docs/design/telephony.md`). So an individual
is *already* a group of kind `personal`, and a will is therefore the *same* class of thing as a group
dissolving — a custody transition, not a second kind of thing.

**The primitive is not the account; it is the group operation.** An operation (`dissolve`, `absorb`,
`devolve`, `delegate`, `succeed`, `merge`…) moves custody of a *surface*. The account resource records
what an operation did to *accounts*; the same operation, run against the treasury or the DID inventory,
moves *those* instead. So the account resource is a ledger of one operation class's effects — never the
owner of the logic.

## What the resource IS (schema shape)

One table, owned by `groups`. Reuses the `grants`/`roles` model and the vault; introduces `anchor`
(custody state) and a reference to the operation that last changed it.

```
accounts
  id            uuid PK
  group_id      uuid NOT NULL REFERENCES groups(id) ON DELETE CASCADE
  platform      text NOT NULL            -- 'instagram', 'youtube', 'google', 'domain', 'aws', ...
  handle        text (nullable)          -- @handle, domain, or null
  kind          text                     -- 'social' | 'email' | 'domain' | 'service' | 'payment' | ...
  verifying_did text (nullable)          -- the number that verified it (telephony_resources 'did')
  anchor        text NOT NULL DEFAULT 'member-number'
                CHECK (anchor IN ('group-passkey','group-email','member-number','orphaned'))
  anchor_member text (nullable)          -- the sub of the person, when anchor='member-number'
  status        text NOT NULL DEFAULT 'provisioning'
                CHECK (status IN ('provisioning','active','rotating','orphaned','retired'))
  created_at / updated_at timestamptz
```

The **anchor** is the load-bearing field — *the* thing that says whether a departure or dissolution can
strand this credential — and it carries the custody rules from
`coop-accounts-and-phone-verification.md` §"credential custody":

- `provisioning` is the only status allowed while `anchor = 'member-number'` (or no passkey exists).
- `active` requires `anchor IN ('group-passkey','group-email')`.
- `orphaned` is the explicit, logged state after a re-home fails or is waived (never a silent fall).

The group-passkey lives in the **vault** (member-split, quorum-held); the resource records *which
anchor is active*, not the secret. The reason a group can move an account to another identity at all is
that the account is anchored to a **transferable key, not a person** — but this is an enabling property,
not the point. The point is the operations below.

### Role mapping (who may act, platform-side)

Not the coop's invention — mirrors the platform's own multi-user model (Meta business roles, YouTube
brand-account managers, Google account managers):

```
account_roles
  account_id  uuid REFERENCES accounts(id) ON DELETE CASCADE
  sub         text (nullable)   -- nullable = a machine credential (API key), not a person
  platform_role text            -- 'owner','admin','contributor', ...
  granted_by  text
  granted_at / revoked_at timestamptz
```

`sub` nullable is the *machine* lane (API tokens / publishing creds, the vault's per-group keys). A
person-role and a machine-role are different rows with different revocation semantics.

## The group operations (the real primitive — v1, not deferred)

Custody of a group-held surface can move three ways — **up/sideways**, **down**, or **across a
person's own life** — and every hop is one of these operations, authorized at the *departing holder's
own threshold while still healthy*, never by the recipient declaring itself. Six named here; the suite
is open and still being discovered.

### Dissolve
The holding identity ends. Its custody moves to a **receiving identity**. Two directions, two
authorization shapes:

- **Up / sideways** — a group dissolves into its vertical, its federation, or a peer group. The
  departing party still *outlives* the decision, so its own threshold authorizes the handoff.
- **Down** — a container dissolves and devolves to its constituents. Here the departing party *is* the
  set of recipients, so the **membership ratifies at its threshold** what each will now hold. A faction
  cannot devolve to itself by declaring the container dissolved.

### Absorb
The complement of dissolve: a receiving identity takes on the custody of a dissolving one. **Push, not
pull** — the dissolving party authorizes its own absorption; the recipient never claims it unilaterally.
(A stronger/adjacent group cannot "absorb" a peer by declaring that peer dissolved.)

### Devolve
Downward handoff along the containment chain — vertical → group → member-persona — *without* the
holding identity ending. The container releases a slice of custody to a constituent while continuing to
exist. Authorized by whoever held it at the healthy moment.

### Delegate
The reversible middle of the ladder: a holder (person or group) grants *partial, revocable* authority to
an agent for a bounded scope or time — because they are **incapacitated, incarcerated, missing, or
off-grid**, not dead. This is the platform's native "account manager / legacy contact / inactive-account
manager" mechanism; **lean on the platform's where it exists, and record in the coop that it was
configured** (part of `anchor` health), rather than reimplementing it.

### Succeed
The terminal, irreversible transfer — death (a person) or full dissolution (a group). Full custody moves
to the named successor identity/identities, at the highest authority level. This is the *easy* end of the
ladder, precisely because it is the only state that is both verifiable **and** irreversible.

### Merge
Two identities become one *without* either dissolving-in-abandonment — a combination, not an absorption.
Custody is pooled, roles are mapped, and the merged identity's account surface is the union. The
departure-then-absorb shape (dissolve into) is a special case; merge reserves the case where both sides
*want* the combination and each ratifies it.

### The ladder underneath all of them

Every departure-state a holder can enter — **missing, incapacitated, incarcerated, absent, dead** — maps
onto one of the above, with three properties each:

- **grant** — how much authority moves (read-only → agent → full), *not* a boolean;
- **evidence** — what proves the state, and it must **not be self-declared** (a booking/court record, a
  clinician's letter/guardianship order, a death record, or — for *missing* — the absence of a signal
  plus a delay, which is the one state with no positive document and the most abuse-prone);
- **reversibility** — the person might return (incarceration, incapacity, missing all do; only death
  does not), so the grant must be revocable wherever return is possible.

## Custody invariant

- **The anchor must move off the person *before* the point of no return.** A will — or a dissolved
  group — whose accounts still ride a dead/absent person's number is de facto lost, whatever any
  operation table says. "Group-passkey + recovery email the successor *can reach*" is not hardening;
  it is the only thing that makes any of the above enforceable at all.
- **The operation itself needs an anchor.** Who may *execute* a dissolve/succeed/delegate (declare the
  death, trigger the devolution) is itself a group-held authority with a threshold — never a named
  individual's unilateral power, never the recipient declaring the state of another. Otherwise "the
  person who declares me dead gains everything" is a new single point, at every scale.

## Ownership vs. control

The "credential is the group's / number is the member's" split applies at every scale. The *account* is
the durable identity's holding (movable by the operations above); the *number* is the person's (dies
with them, or is ported by whoever holds its KYC). Departure and dissolution are the moments that split
becomes fatal if it was never resolved — which is precisely why the anchor must be group-held *while the
holder is still healthy*.

## Candidate operations (not canon — the suite's open complement)

These are *candidates* the six named operations imply but don't yet cover. They are thinking, not a
frozen schema; which are real falls out of actually resisting the frictions they name, not from this
list. **Freeze and contest are flagged as arguably load-bearing, not optional.**

- **Restore / revoke-delegation** — the mirror of `delegate`, and the act its "reversible" property
  *requires*. A returned (or recovered) holder takes their authority back, at threshold. Not a new
  operation so much as the un-tripped half of delegate — but it needs a name because "the grant is
  revocable" needs a committed act to actually revoke it.
- **Freeze / suspend** — *load-bearing*. Neither transfer nor end: custody pauses for a bounded window
  on a trigger (missing, hostile-but-unsettled, disputed). The honest "hold still" state between "they
  are gone" and "we have decided where it goes." The brake that lets every other operation be *rushed
  toward* safely, because it can be stopped.
- **Split / partition** — the inverse of `merge`. One identity divides into two or more, and its
  surfaces are partitioned among them (an org that outgrows itself; a federation that splits along
  genuine lines). `devolve` hands to *existing* constituents; `split` *creates* them and divides the
  estate across them.
- **Escrow / hold-in-trust** — custody moves to a neutral party (a steward, the coop itself) pending
  resolution, rather than to any interested identity. Distinct from `absorb` (no one *gains* it) and
  from `freeze` (a named holder *holds* it, protected from the parties in conflict).
- **Attest / witness** — the act that *feeds* every other operation's `evidence` field. Who declares
  "missing / dead / incapacitated / absent," with what proof, witnessed by whom, at what threshold.
  Right now "evidence must not be self-declared" is an invariant with no operation behind it; `attest`
  is that operation — the death-record / booking-record / clinician-letter as a first-class group act.
- **Ratify / confirm** — where the *receiving* side's consent becomes explicit rather than implicit.
  Two-actor operations are asymmetric (push-not-pull); `ratify` is the post-hoc or pre-authorization
  seal that makes the receiving side a party rather than a paper recipient.
- **Contest / challenge** — *load-bearing*. Any operation can be contested within a window (a dissolve
  that was a power grab, a merge that was coerced), and the contest **freezes** execution until
  adjudicated. The tripwire that makes the whole suite honest: without a path to undo a wrongly-taken
  operation, every "threshold prevents abuse" claim is unfalsifiable. The group form of an appeal.

**Why freeze and contest are the two that matter most:** together they make the other operations safe
to *run*. Freeze is the answer to "the trigger may be premature" (missing, disputed, hostile) — you
must be able to stop custody from moving while you decide whether it should. Contest is the answer to
"thresholds can be wrong or coerced" — you must be able to *un-execute* a mistaken operation. The rest
round the model out; these two are what keep it from being a set of irreversible moves with no brakes
and no undo — the exact fragility this whole design has been resisting.

## Open questions

1. **The trigger mechanism** — how a dissolve/succeed/delegate is *executed*: witnessed event,
   social-recovery threshold, dead-man's-switch, coop-governed vote? The mechanism (not just the
   operation type) is undecided.
2. **The full operation suite** — six are named and seven are candidates (restore, freeze, split,
   escrow, attest, ratify, contest); the list is **explicitly open**, Robbie is still discovering more,
   and which candidates are *real* (vs. thinking) is unresolved. Do not freeze the taxonomy.
3. **Platform legacies first** — enumerate which platforms offer their *own* legacy / inactive-account /
   delegation feature, and lean on those (legally recognized) before reimplementing.
4. **The anchor-of-the-anchor for a one-person group** — a `personal` group of one has no quorum; what
   is the corresponding threshold for a *single* person's authority model that still survives death?
   (The sharpest open difference between the personal and coop cases.)

## Interface note (deferred)

The group page redesign is **paused** until this resource exists, per Robbie: think it through before
mocking up. When it lands, the "Accounts" panel reads from `accounts` + `account_roles`, and the health
strip is "anchor status per account." No mockup until the data model — now including the operation
model above — is agreed.
