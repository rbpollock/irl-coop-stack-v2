# Event Bus & Group Shapes

Status: design · Aug 2026 · Builds on irl-coop-group.md (Safe-as-coop, seats, roles,
voting), regenerative-vision-note.md (regenerative score), private-treasury-guards-ledgers.md
(treasury), account-and-key-model.md (Safe/keys), infra-management-monitoring.md
(declarative platform).

## 1. The model in one paragraph

Groups are the primitive, and they form a graph: Safe-accounts (nodes) + memberships
(edges). This doc defines the three layers that make that graph *live* instead of a
pile of isolated apps — the **event bus** (how things communicate), **group shapes**
(how a group is structured and provisioned), and the **commons economy** (how shared
infrastructure is funded without coercion). Everything is privacy-by-default: the bus
carries typed events, groups expose themselves only through zero-knowledge proofs, and
payment amounts hide behind coverage proofs.

## 2. The event & notification bus

### 2.1 Sources and channels

Sources *emit* events (votes, matches, alerts, email, chat); channels *deliver* them
(toast, inbox, email, chat, push, a Temporal workflow). Email and chat are both. The bus
is a many-to-many router: any source → any channel, governed by user/group preferences.

### 2.2 The pipeline

```
source → event → notification → channel
```

- **event** — raw, typed, machine-readable: `vote.cast`, `match.found`, `mail.received`.
  Domain-specific, not user-facing.
- **notification** — rendered, user-scoped, localized: title, body, action, urgency.
- **channel** — where it lands.

### 2.3 The event/notification split (why persist events)

Persist raw events as the source of truth; render notifications from them. That is what
makes three things fall out for free: **watches** (a subscription layer over the stream,
not a separate feature), **Temporal** (a workflow is just another channel consuming raw
events), and **future sources** (the offers/asks matcher emits `match.*` with zero bus
changes). Collapsing events → notifications at publish loses all three.

### 2.4 Topology, targeting, auth

- One Redis channel per user: `irl:notify:{sub}`.
- Group targets resolve **server-side**: coop-api looks up members + roles, filters by
  the role allowlist, publishes to each eligible member's channel. The client only ever
  subscribes to its own channel and never does role filtering — role enforcement lives
  where it can't be spoofed.
- Targeting has two modes: **direct** (event names a user/group/role) and **watch**
  (saved predicate over the stream).
- Auth is at the coop-api SSE edge (`GET /api/v1/notifications/stream`, bearer coop JWT);
  the server subscribes to `irl:notify:{jwt.sub}`, so a client can only ever receive its
  own channel. Redis stays on the internal docker net.

### 2.5 Delivery is not the bus's job

The bus decides *who should know*; a group-configurable **Temporal workflow** decides
*what to do about it* (email via Stalwart, post to Matrix). The bus never learns SMTP or
Matrix. Delivery config (which event types route to which channels) lives in Postgres as
group config, read by the workflow at execution time.

### 2.6 Notification shape

```
{ id, user, type, title, body, action:{label, url, method?}, urgency, ts, read }
```

`action` is what makes notifications useful (deep link + optional inline accept/reject),
not decorative. `urgency` maps to channel behavior (high → toast + email; low → inbox
only) — the knob behind the "mail popup toast" and "notification settings" surfaces.

Anonymization is **owned by the source**, never the bus: the form system knows its
anonymity setting and either omits the submitter or marks `anonymous`. The bus renders
what it's given and never strips identity — privacy policy lives where the identity lives.

## 3. Group shapes

A **shape** is the template a group is born from — five axes, four inward and one outward:

- **roles** — the vocabulary, shared between authorization (who can edit the site) and
  notification targeting (who gets notified). Generalizes the founder/admin/member/
  inviter/observer set in irl-coop-group.md: that set is the `irl.coop` group's default
  vocabulary — one shape among many.
- **apps** — what gets provisioned, each with a hook.
- **config** — default delivery/urgency rules.
- **governance** — thresholds, quotas, membership policy. The **meta** axis: it governs
  how the other three (and itself) change, split into **constitutional** (amendment
  rules, quorum, admission/expulsion — hard to change) and **ordinary** (app bundle,
  delivery prefs, role assignments — shift under the constitutional process).
- **proofs** — the outward interface: what the group can reveal about itself without
  exposing internals.

### 3.1 Shape = seed, not cage

All five axes are *initial values* written to the group's Postgres record at provisioning.
After that the group's record is authoritative and the shape is never re-read (except to
show divergence from defaults). A split is a constitutional event producing two new
records seeded from the parent's *current state*, not the original shape.

### 3.2 Composition, not inheritance

Shapes assemble primitives; they don't extend a base. "Men's circle" is a custom
composition (its roles + apps + defaults), not a subclass of "group". Copy-then-modify
means a built-in shape evolving later doesn't silently change existing groups — what you
want for stable, self-governing groups and for succession.

### 3.3 Three lifecycles — and the blueprint commons

- **built-in** — curated, git.
- **custom** — per-group, Postgres.
- **shared** — a group exports its shape to a public library; others adopt/remix.

The library shares **structure** (roles, apps, governance, proof schema), never
**records** (members, votes, metrics) — a blueprint commons, not a data commons.
"Highlighted" becomes community-signaled (adoption + remix count) as well as
curator-picked. Library *hosting* (central vs federated) is a federation question, still
parked; the *export* is group-local.

This yields a disclosure spectrum a group can hold independently per axis:
**proofs-only** (private) ↔ **structure-shared** (library) ↔ **data-public**.

## 4. Provisioning

Two declarative layers, same shape:

1. **Platform** (existing): `infra/instances/dev/` → `generator.py` → `out/` — shared
   infra, static.
2. **Group template** (new): per-shape YAML declaring the app bundle — Safe, roles,
   Plane project, DB schema, `info@{name}.irl.coop`, `{name}.irl.coop` site, Matrix
   room, other apps.

The group template maps 1:1 onto a Temporal provisioning workflow: each declared app is
an **activity (hook)**, run in order, idempotent, with compensation on failure.
`group.created` → workflow → provision each → emit `group.<thing>.created` → notify
members as things come online.

**Stored where:** the template (what a group *should* get) → git, versioned. The
provisioned state (what *this* group *actually* got — Safe address, Plane project id, DB
schema, room id) → irl.coop Postgres (the group store). Same "declared vs running" idea
as infra-management-monitoring.md, applied to groups.

**Boundary:** `info@{name}.irl.coop` needs **wildcard MX**, not just wildcard A.
`*.irl.coop` A records already cover the website; MX is a separate record type and
wildcard-MX support at Gandi isn't guaranteed. Fallbacks: single mail domain with
per-group local-parts (`info.menscircle@irl.coop`), or a Stalwart catch-all routed by
recipient domain.

## 5. Hot-pluggable apps

An app is an independent unit: its own compose pillar, its own provisioning hook, its own
edge route + OIDC client. Loose coupling (through the bus + hooks) is what makes an app a
plug-in. To add an app without a rebuild, separate three things that are currently one:

- **catalog** — what apps exist + their hooks/spec → git (versioned code)
- **activation** — is it on, for platform or this group → Postgres (runtime)
- **state** — the running instance → Postgres (runtime)

Add an app = catalog (code) + flip activation (Postgres) + run its hook (Temporal). No
regenerate, no stack-down. Remaining friction is two concrete things, not the
architecture: the traefik edge restart on `dynamic.yml` change (known quirk), and manual
OIDC client provisioning. Deep app-to-app integrations are the coupling tax — those
still force coordinated deploys.

## 6. Proofs (ZK)

### 6.1 Generic core + shape-specific add-ons

A small shared core every shape inherits, plus templatable shape-specific claims. The
core candidates, chosen for **quality network theory** and each required to pass the
inclusion test (provable in ZK **and** hard to game):

| Metric | Signals | The anti-signal it catches |
|---|---|---|
| **flow** | value actually moved (contributions, exchanges) | aspiration without activity |
| **reciprocity** | flow balanced vs extractive | the freeloader |
| **distribution** | flow spread vs hub-concentrated | 100 members, 3 active |
| **persistence** | retention + survival of a node leaving | churn / succession fragility |

These composite into the regenerative score (regenerative-vision-note.md). Honest >
comprehensive: a Sybil-friendly metric defeats the proof entirely, since a ZK proof only
vouches for the claim, never the truth of the data.

### 6.2 Freshness and binding

A proof is a snapshot and must bind a timestamp/block ("as of block N, score ≥ 0.8"), or
a stale proof is indistinguishable from a current one. It binds the claim to the group's
public identity (its Safe address) so it can't be replayed by another group.

### 6.3 Privacy by default

The ZK layer is a third consumer of internal state (alongside notifications and Temporal).
Group internals feed the prover; the prover emits proofs; verifiers check against the
group's public commitment. External parties never touch the internals — a proof is the
only sanctioned leak.

## 7. The commons economy (pay-what-you-want)

Full visibility into cost, "pay what you want" on payment, and a **coverage proof** as
the social signal. This is the anti-freeloader signal for the infrastructure layer —
exactly as reciprocity is for the exchange layer. Two economies, one principle: reveal
good citizenship, not means.

- **Cost is public.** Every group's infrastructure cost is published.
- **Payment is private-but-provable.** The group proves "covered ≥ X%" without revealing
  the amount. That privacy is load-bearing: a subsidizer proves generosity without
  advertising "I have $50k/month of slack" to opportunists.
- **Encourage, not enforce.** The proof is a *positive* credential; its absence is
  *neutral* (non-coverage is inferable, never asserted — no shame flag). Pressure comes
  from the positive signal being valuable, never from shaming. A carrot with no stick.
- **Subsidy gradient.** Free-rider → covers-self → subsidizer, provable as ranges
  ("covered ≥ 100%", "≥ 150%", "subsidized N others"). Groups can cover other groups'
  costs.
- **Single-user groups** are the degenerate case, not a special one: "every account is a
  group of one" means the same schema and threshold apply to an individual and a
  500-member collective.
- **The gamble is testable.** Costs and coverage are both visible, so self-selection
  pressure can be observed — and adjusted if it doesn't materialize.

## 8. Open decisions

1. Role hierarchy: "one of [roles]" vs "≥ a minimum role".
2. Event type namespacing: `vote.*`, `match.*`, `mail.*`, `chat.*` — does it hold?
3. Read state: per-user per-event flags vs a single "last-seen cursor".
4. Render location: source-rendered strings vs bus-side templates (lean bus-side, keyed
   map).
5. Watches: per-user only, or per-group (a group admin's watch notifies the group's
   admins)?
6. Cost-coverage: component of the score + standalone badge? Binary vs bucketed
   disclosure? What exactly is "cost" (per-app/per-resource/total) and how is payment
   recorded private-but-verifiable (commitment + range proof, bound to an accounting
   period)?
7. Generic-core metrics: validate flow/reciprocity/distribution/persistence against
   network theory.
8. Wildcard MX at Gandi for per-group email subdomains.
