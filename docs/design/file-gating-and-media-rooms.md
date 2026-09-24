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

## 5. Media rooms (the side-channel)

A media room is **a Matrix room with an anchor artifact** — not a new app.

```
┌───────────────────────────────┬──────────────────┐
│                               │  #coop-garden    │
│      [ embedded player ]      │                  │
│      session-story.mp4        │  ada: this bit   │
│      ─────────●────── 2:14    │   is great       │
│                               │  ben: @2:14 yes  │
│                               │  ──────────────  │
│                               │  [ message…    ] │
└───────────────────────────────┴──────────────────┘
```

Rules:

1. **The player is generic by content type** — video/audio via a native
   `<video>`; PDF via the existing viewer; office docs open the OnlyOffice
   editor (already built). One embed component, type-dispatched.
2. **The stream is seat-gated.** The player fetches
   `/api/v1/files/s/:grantId`, so playback honors the grant (and its
   expiry) rather than a leaked URL.
3. **The side-chat is the room's normal timeline.** No new message store.
   The room is created (or an existing group room is reused) and the
   artifact is posted as the anchor.
4. **Timestamps are events, not comments.** "This bit" sends a
   `m.room.message` carrying `irl.coop/media_timestamp: 134`; the player
   highlights those marks on the scrubber and clicking one seeks. This
   keeps the whole feature on the chat lane the stack already runs
   (coop-api is already a Matrix appservice — see
   `matrix-chat-and-notifications.md`).
5. **Live rooms are a later step.** Synchronized playback (everyone at the
   same timecode) and voice-over-the-media need LiveKit, which is already
   deployed (`livekit.irl.coop`, `coturn`). Explicitly phase 3 — async
   anchored chat delivers most of the value at none of the complexity.

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
   the immediate dogfood.
2. **Phase 2 — media rooms (async).** Anchor-artifact rooms over the
   existing Matrix lane; the generic embed player; timestamp events on the
   scrubber.
3. **Phase 3 — live rooms.** Synchronized playback + voice over the media
   via LiveKit/coturn.
4. **Phase 4 — group folders & group-scoped grants** (rides the seat model
   already designed in `group-scoping.md`; the `hidden` case needs the
   zk-badge path live).

## 9. Open decisions (Robbie)

1. **Is a media room its own room, or a mode of an existing group room?**
   Own room = clean focus, more rooms to manage. Mode of the group room =
   less sprawl, the chatter interleaves with ordinary talk. Recommend:
   **own room named after the artifact**, linked from the group home —
   focusing on one thing with one conversation is the whole point.
2. **Do open links expire by default?** A never-expiring link is
   convenient and is how most people actually share. Recommend: **default
   7d, "never" available but visually discouraged** — a leaked permanent
   link to a members-only file is unrecoverable.
3. **Should the viewer be a page or a panel?** The embed could be a
   dashboard route (`/apps/rooms/:id`) or a floating panel over the group
   home. Recommend: **a route** — it gets a real URL, is linkable, and can
   host the side-chat at full height.
4. **Download vs view-only for gated grants.** View-only is leakier than
   it sounds (the bytes reach the browser). Recommend: **offer the flag but
   never imply it is DRM** — if a seated member can watch it, they can
   capture it; the gate controls *who*, not *what they do after*.