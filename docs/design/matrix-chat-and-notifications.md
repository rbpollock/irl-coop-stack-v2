# Matrix chat & notifications

How the coop's Matrix chat surfaces in the dashboard and feeds the event bus —
without building a native Matrix client, without key escrow, and without
modifying the homeserver.

Status: designed + built (2026-08-16). See `event-bus-and-group-shapes.md` for
the bus this plugs into.

## Decision

Two independent pieces, deliberately small:

1. **Embed portions of Element, not the whole app.** The dashboard embeds a
   *specific room* (`element.irl.coop/#/room/<roomId>`, Element's embed/compact
   mode) rather than the full Element shell. The room timeline + composer render
   in the widget; Element keeps the E2EE keys and the homeserver session.
2. **coop-api runs as a Matrix *appservice*** — an invisible, read-only
   metadata observer that Synapse pushes every event to in real time. coop-api
   fans the metadata into the Redis notification bus; Temporal does delivery.

## Why not the alternatives

| route | rejected because |
|---|---|
| native Matrix client (`matrix-js-sdk` + crypto) | heavy: crypto store, key backup, token lifecycle, sync loop — and E2EE keys in the browser reimplement Element |
| full Element iframe | no chrome control, login page on first open, can't scope to a room |
| key escrow (gateway decrypts) | the gateway can read every chat — contradicts "privacy default / anonymization owned by source" |
| Synapse in-process module | fights the declarative "don't touch the stock homeserver" stance |

## The appservice (coop-api)

Synapse's first-class extension mechanism (what bridges/bots use). An HTTP
service registered by a YAML file, to which Synapse pushes transactions:

```
homeserver.yaml:  app_service_config_files: ["/data/coop-api-registration.yaml"]
registration.yaml: url, as_token, hs_token, sender_localpart=coop-api,
                   namespaces{users,rooms,aliases}, rate_limited: false
Synapse POST /_matrix/app/v1/transactions/{txnId} -> coop-api (Bearer hs_token)
```

Key properties:

- **Real-time push, no polling, no per-member client tokens.** coop-api uses its
  own `hs_token` (HS→AS push auth; `as_token` is the AS→HS direction, unused so
  far) — it does not hold any member's session.
- **Metadata-only by construction.** For E2EE rooms Synapse delivers event
  *metadata* (sender, room, type, timestamp, and the `m.mentions` field the
  sender's client declares in plaintext) and only *ciphertext* for the body. The
  gateway can therefore emit new-message / unread / mention notifications
  **without ever reading content**.
- **Invisible.** The `@coop-api` sender never joins rooms or sends, so it appears
  in no member list, timeline, or presence graph. Visibility is the *opt-in
  signal* (below).

### Pipeline

```
Synapse event
  -> appservice transaction push -> coop-api /transactions (verify hs_token)
  -> filter to relevant types, normalize {source:"matrix", type, room, sender, ts, mention}
  -> Redis PUBLISH irl:communication:events   (domain firehose; source is metadata, not the channel)
  -> Postgres events table (coop_ingest_event, sender's personal group, RLS)
  -> renderer -> irl:notify:{sub}            (per-user fan-out, later)
  -> Temporal workflow (group-configurable delivery)
  -> dashboard badge/toast
```

## Opt-in bot member (future phase)

The same registration is the home for the "gateway bot" that can read content
for always-on triggers (moderation, keyword alerts, digest). It becomes a room
member **only when the group admits it** — so its presence in the member list is
exactly the legible signal that the room opted into gateway content access.
Until then it stays a pure metadata observer.

## Trust boundaries

- **Default**: gateway sees metadata only; message content stays end-to-end
  encrypted between members (keys never leave the browser).
- **Opt-in**: a group may admit the bot for content-level triggers; that is a
  per-room governance decision, not a global gateway default.

## Secrets (declarative, derived)

- `matrix.as-token`, `matrix.hs-token` — derived from `master.key`, declared in
  `apps/matrix.yaml` as `${SECRET:...}`, injected as container env and emitted
  into `out/dev/secrets.env` for coop-api. The registration template carries
  `${SYNAPSE_AS_TOKEN}`/`${SYNAPSE_HS_TOKEN}` placeholders, rendered by the
  `synapse-s3` entrypoint alongside `homeserver.yaml` — no secret baked in any
  generated file.

## Status

- Built: appservice registration (declarative), coop-api `/transactions` →
  `irl:communication:events` firehose, the Postgres event store (`events`
  table + `coop_ingest_event` + group-aware RLS), room-scoped chat widget,
  room-list API (`/api/v1/chat/rooms`).
- Later: the renderer (event → notification, per-user `irl:notify:{sub}`
  fan-out), SSE stream, dashboard badge wiring, the opt-in bot, per-room
  unread sync, and room→group scoping (`group-scoping.md` §7 — events currently
  land in the sender's personal group until a room is scoped to its group).
