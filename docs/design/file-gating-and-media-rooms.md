# File gating & media rooms — sharing, gated playback, and the side-channel

Status: design only — no UI exists today · Sep 2026 · Extends `files-panel.md`
(projection rule, variant-B share tokens), `group-scoping.md` (seats,
`visibility: open|members|hidden`, zk-badge membership proofs),
`group-home.md` (the group surface), `matrix-chat-and-notifications.md`
(the chat lane), and `world-doc-and-contacts.md` (seats).

## 1. The gap

Today a file exists, and a *link* can be minted for it — but there is no
surface that makes sharing a **place**. Three concrete shortcomings drove
this spec:

1. **No UI for sharing.** `POST /api/v1/files/:source/:key/share` exists;
   the only way to use it is to run a script (as happened with the recap
   MP4 — a hand-rolled mint, then a 300-character signed URL that broke on
   paste). Sharing must be a button with a picker, not a curl.
2. **No gating.** A relay token is all-or-nothing: anyone with the URL can
   fetch, regardless of seat. There is no "members of this group only"
   token, and no expiry/revocation UI.
3. **No context.** A shared video today is a bare file. What people
   actually want is **the thing plus the conversation about it** — a player
   with the group's chat beside it — which is the "watch party / media
   room" shape. Nothing in the tree covers this.

## 2. Principles

1. **A share is a grant, not a URL.** The artifact is an *access grant*
   (who, what, which group, how long, what they may do). URLs are one
   rendering of a grant; the embedded player is another; an API fetch is a
   third. Never let the URL be the truth.
2. **The source app still authorizes.** Unchanged from `files-panel.md`
   §1.2: coop-api asks the owning source (docs/stalwart/synapse/plane)
   "can this seat see this?" and only then mints anything. No ACLs in
   MinIO, ever.
3. **Gating is seat-aware, including hidden groups.** `visibility:
   open|members|hidden` decides who may be enumerated. For `hidden`
   groups the grant is proven, not listed — the zk-badge path
   (`group-scoping.md` §) — so a gated link does not leak membership.
4. **Revocable by construction.** Short TTLs plus a grant id in the
   registry: "revoke" flips a row, it does not chase URLs.
5. **Playback is a viewer, not a copy.** The media room streams from the
   owning bucket through coop-api. It never copies blobs into a new
   "shared" store (same rule as the panel's projection).
6. **The side-channel reuses the chat lane.** The conversation beside the
   player is ordinary Matrix history for a room — not a bespoke comment
   table. Anchored comments are an *event type* on that lane.

## 3. The sharing UI

On any file row in the Files panel (and on the group home), a **Share**
action opens a dialog:

```
Share "session-story.mp4"

  Who      ( ) anyone with the link      → token, bearer-free, TTL
           ( ) members of  [group ▾]     → seat-gated grant
           ( ) specific members...        → per-sub grant list

  Expires  [ 24h ▾ ]   24h · 7d · 30d · never (discouraged)

  Actions  [x] view/play   [ ] download   [ ] re-share
           ( ) copy link   ( ) embed in a room   ( ) email

  [ Create grant ]
```

Behavior:

- The dialog mints through the existing endpoint
  (`POST /api/v1/files/:source/:key/share`), extended with
  `audience`, `expiresIn`, and `actions`.
- **Copy link** shows the short form (§4), not a 300-character SigV4 URL.
- **Embed in a room** creates a media room (§5) and posts the artifact as
  its anchor event.
- The grant appears in a **Shared by me** list with a Revoke button.

## 4. Two link shapes, deliberately

The recap incident is the design input: a presigned S3 URL is unshareable
in practice (length, signature fragility, no revocation).

| | **Open link** | **Seat-gated link** |
|---|---|---|
| Who | anyone holding it | members of a named group |
| Token | `base64url(scope\|key\|exp) . HMAC(files.sig)` (one object) | same, plus `group=<id>` and a seat assertion |
| Revoke | not re-issued; short TTL | row flip (grant registry) |
| Leaks | the object if the URL escapes | nothing without a seat |
| Use | send to a friend | inside a group |

**Short path.** `GET /api/v1/files/s/:grantId` — the grant id *is* the URL.
Resolution happens server-side against the grant registry, so the URL stays
short, carries no signature to mangle, and dies when the grant is revoked
or expires. This is the shape the recap should have used from the start.

## 5. Rooms — the call lane, comments, and signatures

A shared file does **not** imply a conversation. Most shares are one-way:
send the thing, the other side reads it. But when a conversation *is*
warranted — a client reviewing a deliverable, a group settling an
agreement — the room should already be there, and it should have the
coop's full communication surface, not a comment box.

So the artifact's room is **cumulative**, and each layer is optional:

```
artifact (a file)
 └── room            (optional — created on "embed in a room")
      ├── chat       Matrix timeline            (reuse: already built)
      ├── call       Element Call — the LIVE room (reuse: already deployed)
      ├── comments   anchored to the artifact   (thin: events, not a store)
      └── decisions  approve / sign / acknowledge (new: see §5.4)
```

### 5.1 The call lane is already ours

Video for a room is **Element Call** — already deployed
(`element-call` + `livekit` + `coturn` + `lk-jwt` in the `communication`
pillar) and already surfaced: Cinny bundles the Element Call widget, and
the dashboard iframes Cinny with `microphone; camera; display-capture`
granted (`apps/chat/_components/chat-iframe.tsx`). So a media room's call
step is not new infrastructure — it is **the same Matrix-call lane we
already run**, addressed at the artifact's room.

That means the room has two live modes and they are siblings, not
variants:

| mode | what it is | status |
|---|---|---|
| **async** | the timeline + anchored comments | reuse (chat lane) |
| **live** | Element Call in the room, screen-share included | reuse (deployed) |

The player sits beside whichever is active. A design review can be "watch
the render, talk over it live, drop a mark at 2:14" without any component
being invented for it — the player is the only new thing.

### 5.2 Comments are events, and skipping them is normal

- A comment posts a `m.room.message` carrying the artifact anchor
  (`irl.coop/artifact`, `irl.coop/media_timestamp` when on the scrubber).
- Timecode marks render on the player's scrubber; clicking one seeks to it.
- **No comment store.** Same reasoning as §2.6: the room's history *is* the
  record, and it is already federatable, searchable, and permissioned.
- A room may be *anchored-only* (no chat), created for approvals, or a
  full chat room as in §5. The layers do not require each other.

### 5.3 Approval — the comment that has a state

For the client-sharing case the useful comment is not "nice work", it is
**"approved"** — a statement with a person, a time, and a consequence.
Model it as a Matrix **state** event (not a message), so it is idempotent
and queryable rather than a scroll-back:

```jsonc
// type: coop.artifact.approval   (room state, keyed by sub)
{
  "artifact": "grt-7f3a",
  "decision": "approved",           // approved | changes_requested | acknowledged
  "note": "the second pass is right",
  "signedAt": "2026-09-24T10:12:00Z",
  "assent": { "method": "session-key", "proof": "…" }
}
```

- Latest state per `(artifact, sub)` wins; the room keeps the history.
- An approval is an **assertion by a seat**, so it rides the seat model —
  and for `hidden` groups it can carry a zk-badge proof instead of a
  plaintext membership claim (§3.3).
- This is where the **Jev decision contract** in
  `jev-temporal-group-workflows.md` lands naturally: `{approved,
  changes_requested, escalate}` with a threshold, an abstain, and a
  deterministic fallback — a client approval and a group disbursement are
  the same shape.

### 5.4 Signatures (the DocuSign-shaped gap) — boundaries first

A real signature is a **legal instrument**, and this stack has a specific
and unusual advantage: the account model already gives every member a
signing identity (§ `delegation-and-session-keys.md` — a Safe plus session
keys), so "who signed" can be a cryptographic fact rather than a
checkbox. But it also has hard limits, and the spec should say so plainly:

**What we can do well:**
- **Assent is provable.** The signer signs the artifact's hash with a
  session key; the proof is verifiable by anyone and bound to that exact
  byte sequence. That is strictly better than a drawn squiggle.
- **The manifest is verifiable.** An "agreement" is an artifact + an
  approvals ledger; the whole thing can be exported and re-verified
  offline, which is exactly the sovereignty story.
- **Timestamps and ordering** come from the room timeline.

**What we should NOT claim:**
- **Not eIDAS/QES/ESIGN-compliant** out of the box. Qualified signatures
  need a certified trust service provider; we are not one, and pretending
  otherwise is a liability, not a feature.
- **Not certified delivery / notarization.** "They saw it" is a
  claim about a browser session, and it is weaker than it sounds.
- **Key custody is the real constraint.** A signature is only as strong as
  the key's protection, and a platform-held key means the platform can
  sign as you — the same problem flagged for the cooperative vault
  (`coop-launch-and-roadmap-handoff.md`). Until the non-custodial vault
  lands, a signature here is **strong receipts, not a deed**.

So the honest shape: build **signing as verifiable assent** (hash +
session-key proof + ledger), position it as *"provable approval inside
your own stack"*, and treat formal/regulated signing as an integration
choice for the groups that need it rather than a claim the coop makes.

### 5.5 The three legitimate shapes, side by side

| I'm sharing a file with… | shape | what's created |
|---|---|---|
| a friend | **open link** (§4) | a grant, no room at all |
| my group, for discussion | **media room** | room + chat + player (+ call on demand) |
| a client, for approval | **anchored room, approvals on** | room + player + `coop.artifact.approval` state |
| a client, for signature | **anchored room + signing** | the above + session-key proof on the artifact hash |

The default is the first: **most shares are links and nothing else.**
Rooms are opt-in, and each layer inside a room is opt-in again.

## 6. Grant registry (the only new store of record)

```json
// data/grants.json — dev-grade, same shape discipline as folders.json/profiles.json
{
  "grt-7f3a": {
    "source": "docs",
    "bucket": "docs",
    "key": "docs/<sub>/session-story.mp4",
    "createdBy": "<sub>",
    "audience": { "kind": "group", "groupId": "grp-9c" },
    "actions": ["view"],
    "createdAt": "2026-09-24T10:00:00Z",
    "expiresAt": "2026-10-01T10:00:00Z",
    "revokedAt": null,
    "roomId": "!media-garden:irl.coop"
  }
}
```

Table-ready (the panel's §8.1 reasoning applies): one row per grant, keyed
by id, with `audience` and `actions` as columns once coop-api has a real DB.

## 7. API surface (extends `files-panel.md` §6)

```
POST   /api/v1/files/:source/:key/share     → { audience, expiresIn, actions } → { grantId, url }
GET    /api/v1/files/s/:grantId             → stream (no bearer; grant decides)
GET    /api/v1/files/grants                 → grants I created (with state)
DELETE /api/v1/files/grants/:grantId        → revoke
POST   /api/v1/files/:source/:key/room      → create/reuse a media room, post anchor
```

Gating on stream:

1. resolve `grantId` → grant row (404 if missing, 410 if revoked/expired)
2. resolve audience → `open` = allow; `group` = check the caller's seat via
   `GET /api/v1/groups` semantics; `members` = per-sub list
3. for `visibility: hidden` groups, accept a zk-badge proof instead of a
   plaintext seat lookup — the stream route must not become a membership
   oracle
5. only then ask the source app for the object, and stream it

## 8. Build sequence

1. **Phase 1 — share dialog + short links.** Extend the share endpoint with
   `audience`/`expiresIn`/`actions`; add the grant registry; add
   `/files/s/:grantId`; ship the dialog with copy-link + expiry picker and
   a *Shared by me* list with revoke. Re-mint the recap MP4 through it —
   the immediate dogfood. **No rooms yet** — this covers the common case
   (a link and nothing else).
2. **Phase 2 — the anchored room (async).** Artifact-anchored rooms over
   the existing Matrix lane: the generic embed player, timestamp marks on
   the scrubber, and the `coop.artifact.approval` state event. This is the
   client-review shape and needs no new infrastructure.
3. **Phase 3 — the call in the room.** Surface Element Call *addressed at
   the artifact's room* from the dashboard (the lane is already deployed
   and already iframed via Cinny). Live review: player + call + marks.
4. **Phase 4 — signing as verifiable assent.** Artifact-hash + session-key
   proof + the ledger, positioned as provable approval (§5.4 boundaries),
   not as a compliance claim.
5. **Phase 5 — group folders & group-scoped grants** (rides the seat model
   in `group-scoping.md`; the `hidden` case needs the zk-badge path live).

## 9. Open decisions (Robbie)

1. **Is an anchored room its own room, or a mode of an existing group
   room?** Own room = clean focus, more rooms to manage. Mode of the group
   room = less sprawl, the chatter interleaves with ordinary talk.
   Recommend: **own room named after the artifact**, linked from the group
   home — focusing on one thing with one conversation is the whole point,
   and a client-facing room must not be the group's backchannel.
2. **Do open links expire by default?** A never-expiring link is
   convenient and is how most people actually share. Recommend: **default
   7d, "never" available but visually discouraged** — a leaked permanent
   link to a members-only file is unrecoverable.
3. **Should the viewer be a page or a panel?** Recommend: **a route**
   (`/apps/rooms/:id`) — it gets a real URL, is linkable, and can host the
   call and the comments at full height.
4. **Download vs view-only for gated grants.** View-only is leakier than
   it sounds (the bytes reach the browser). Recommend: **offer the flag but
   never imply it is DRM** — the gate controls *who*, not *what they do
   after*.
5. **How far do we take signing?** Recommend: **hash + session-key proof
   only, labeled "provable approval"**, with qualified/regulated signatures
   treated as an integration for groups that need them — and revisited once
   the non-custodial vault makes the key genuinely the member's.
6. **Are approvals a state event or a message-with-reactions?** State events
   are queryable and idempotent (latest wins) but are overwritten in place;
   messages keep a visible trail. Recommend: **state event per
   `(artifact, sub)`** (the shape a Jev decision contract needs), with the
   room timeline still showing every change in history.