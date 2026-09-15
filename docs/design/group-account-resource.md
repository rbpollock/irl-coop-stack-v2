# The account resource — group-held credentials, and the will that outlives the individual

**Status: design (scoped, not built).** The durable identity that holds accounts is *not* "a group"
in the membership sense — it is "a thing that outlives any single person." A coop is one such thing;
**an individual planning a will is another.** This doc scopes one primitive that serves both.

## The one insight that collapses the scope

The "group" in "group-account resource" was never really *group* — it was **"a durable identity whose
credentials survive the departure of whoever set them up."** The stack already models this: `groups`
has a `kind` (`coop` | `personal`), and a **personal group is a user's own identity**
(`created_by` → one per `sub`, enforced at the DB level, `docs/design/telephony.md`). So an individual
is *already* a group of kind `personal`.

That means the account resource does **not** need a new holder concept. It hangs off `groups.id`, and
"a person's descendants inherit their accounts" is just **succession on a `personal` group** — a
governance transition (who may act as this identity) rather than a second kind of thing.

The only genuinely new idea the will case introduces is **succession**: a rule that says "these people
gain authority over this identity's credentials at a time triggered by incapacity or death." Everything
else (authority, custody, resignation, revocation) is the same for a coop and a person.

## What the resource IS (schema shape)

One table, owned by `groups`. Nothing here is new column types — it reuses the `grants`/`roles` model
and the vault, and introduces one new concept (`anchor` + `succession`).

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

The **anchor** is the load-bearing field — it is *the* thing that says whether a departing member can
strand this credential — and it reuses the custody rules already written in
`coop-accounts-and-phone-verification.md` §"credential custody":

- `provisioning` is the only status allowed while `anchor = 'member-number'` (or no passkey exists).
- `active` requires `anchor IN ('group-passkey','group-email')`.
- `orphaned` is the explicit, logged state after a re-home fails or is waived (never a silent fall).

The group-passkey itself lives in the **vault** (member-split, quorum-held) — the account resource
records *which anchor is active*, not the secret.

### Role mapping (who may act, platform-side)

Not the coop's invention — it mirrors the platform's own multi-user model (Meta business roles,
YouTube brand-account managers, Google's account managers). One row per grant:

```
account_roles
  account_id  uuid REFERENCES accounts(id) ON DELETE CASCADE
  sub         text (nullable)   -- nullable = a machine credential (API key), not a person
  platform_role text            -- 'owner','admin','contributor', ... platform-specific
  granted_by  text
  granted_at / revoked_at timestamptz
```

`sub` nullable is the *machine* lane: the API-token / server-side credential that does publishing, which
is exactly what the vault's per-group Postiz/API keys already presuppose. A person-role and a
machine-role are different rows with different revocation semantics.

## Succession — the will case, and the only new mechanism

A `personal` group is, by construction, a single living person's identity. The will case is the demand
that its accounts **transition** rather than die with them. Two sub-problems, kept separate because
their triggers and trust are different:

1. **Incapacity** — the person is alive but cannot act. Needs a *delegate* who can be added *now*,
   trusted on a schedule, and removed if recovery happens. (This is the platform's native "account
   manager / legacy contact" feature, e.g. Google's Inactive Account Manager — **use the platform's,
   do not reimplement it**, but the coop records *that it was configured* as part of `anchor` health.)
2. **Death** — the person is gone. Needs a **successor rule**: named beneficiaries + the conditions
   under which they gain authority. Two honest halves, only one of which is a chain problem:

   - **The cooperative half (build it):** the coop records *who* is entitled to inherit *which*
     accounts, and enforces the *transition* under the group's own governance (a defined, witnessed,
     irreversible event). This is `account_succession`:
     ```
     account_succession
       account_id  uuid REFERENCES accounts(id)
       beneficiary uuid     -- a personal group id (the heir's own identity), or a coop group
       role        text     -- what they inherit ('owner' default)
       condition   text     -- 'on-death' | 'on-incapacity' | 'manual'
       created_at / executed_at timestamptz
     ```
   - **The platform half (can NOT be built):** the platform still decides whether a dead person's
     account transfers, and it wants a death certificate / probate / its own legacy process. The coop
     cannot *make* Instagram honor a succession rule — it can only **record the entitlement and hand
     the heir a complete, notarized-ready dossier**: the handle, the anchor state, the recovery paths,
     the role mapping, and the documented intent. The account resource is the *engineering fact* that
     turns "probate nightmare" into "the heir has everything in one place when the platform asks."

That split is the honest line: **the coop enforces the *intent*; the platform enforces the
*transfer*.** The resource makes the first airtight and the second merely a matter of presenting the
right documents — which is the best anyone can do without the platform cooperating.

## Custody invariant (unchanged, restated for the individual)

An individual planning a will is the *same* trap as a group that never hardens — the person set up the
account with their own number, meant to "re-home it later," and later is now a will that nobody can
answer because the number died with them. So:

- **The anchor must move off the person *before* the point of no return.** For a will, "group-passkey
  + recovery email that the *successor* can reach" is not optional hardening — it is the *only* thing
  that makes the succession enforceable at all. An account still anchored to the deceased's personal
  number is de facto lost, whatever any succession table says.
- **The succession rule itself must have an anchor.** Who may *execute* the succession (declare the
  death, trigger the transition) is itself a credential to be group-held — otherwise "the person who
  declares me dead gains everything" is a new single point. The rule is a group decision with a
  threshold, not a named individual's unilateral power.

## Ownership vs. control, restated for individuals

The same "credential is the group's / number is the member's" split applies verbatim to a person: the
*account* is the estate's (part of the durable identity), the *number* is the person's (dies with them,
or is ported by whoever holds the KYC). The will is the moment that split becomes fatal if it was never
resolved — which is precisely why the anchor must be group-held *during life*.

## Open questions

1. **What triggers `succession` execution** — a witnessed death event, a social-recovery threshold, a
   dead-man's-switch, a coop-governed vote? The mechanism (not just "on-death") is undecided.
2. **Is `personal`-group succession in v1, or is the will case a later slice?** The coop/group case has
   a live consumer (group accounts, now); the individual will-case has *moral* weight but no immediate
   user. Scope v1 to `accounts` + `account_roles` + the anchor lifecycle, and treat `account_succession`
   as a designed-but-later table.
3. **Platform legacies first.** Before building any succession hook, enumerate which platforms offer
   their *own* legacy/inactive-account-manager feature — the coop should record and lean on those
   (they're legally recognized), not reimplement them.
4. **The anchor-of-the-anchor** — the group-passkey that anchors an account is itself held by quorum;
   for a *personal* group of one, what is the corresponding quorum? (This is where the will-case
   genuinely differs from a coop — drafting a single-person authority model that still survives death.)

## Interface note (deferred)

The group page redesign is **paused** until this resource exists, per Robbie: think it through before
mocking up. When it lands, the "Accounts" panel reads directly from `accounts` + `account_roles`, and
the health strip is "anchor status per account" — but no mockup until the data model is agreed.
