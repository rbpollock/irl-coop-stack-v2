# Android Mini-Services Client — the phone as a group node

Status: design · Sep 2026 · Builds on world-doc-and-contacts.md (seats, the
world-doc projection), event-bus-and-group-shapes.md (the reconciler,
provisioning), infra-management-monitoring.md (declared-vs-running), and the
maps/telephony stack (MapLibre + PMTiles basemap; FreeSWITCH/FusionPBX).

## 0. The shape in one paragraph

An Android app that turns a member's phone into a small, self-hosted **service
node** for their groups: it relays SMS through the phone's SIM (TextBee),
serves group files from a local S3 store, holds a scoped shard of the group's
data for offline access, and renders the maps server's basemap offline — all
joined over a Tailscale mesh so no public IP and no cloud relay is needed.
The phone does the work, so the coop's core stays independent of big-tech
VPSes: a distributed network where people's own pockets are the
infrastructure.

## 1. Principles

1. **The phone is a node, not a client.** It hosts services (SMS, storage,
   data, maps), not just consumes them. Every member's device is a potential
   volunteer host for their groups.
2. **Offline-first, best-effort.** A phone is flaky — it sleeps, loses signal,
   gets killed by the OS. Every capability must degrade gracefully to a
   read-only cache, and every device is treated as an *unreliable volunteer*,
   never the source of truth.
3. **The group's truth stays shared.** The source of truth is the shared Citus
   store; the phone holds a scoped, disposable shard. A lost phone must never
   be the only copy of anything.
4. **Scoped, not global.** The phone only holds what its owner is seated to
   see — the world-doc projection, filtered by seats and visibility. A phone
   never carries the whole coop's data.
5. **Sovereign connectivity.** Tailscale mesh across CGNAT. No public IP, no
   cloud relay for payloads — devices reach each other directly.

## 2. The components

| service | role | feasibility |
|---|---|---|
| **TextBee** (SMS gateway) | send/receive SMS + webhooks through the phone's SIM | feasible now |
| **MapLibre + PMTiles** | offline basemap + mapping tools (the maps server) | feasible now |
| **Tailscale mesh** | connectivity across CGNAT (phone ↔ node ↔ edge) | feasible now |
| **offline store** (SQLite / PGlite) | scoped cache of group data for offline read | feasible now |
| **local S3** (MinIO-compatible) | redundant/offline file storage for the group | hard — Termux or a native S3 server |
| **Citus shard** (Postgres) | a real shard of the group's database on-device | research — coordination + sync |

## 3. The components, in detail

### TextBee — communications over the SIM
TextBee is an open-source Android SMS gateway: a foreground service that
exposes an HTTP API and webhooks for send/receive. Integrated with the app,
the phone's SIM becomes a group comms channel — SMS for members without data,
two-factor codes, carrier-reachable alerts — routed through the same event bus
as every other channel. It complements, not replaces, the coop's SIP stack:
FreeSWITCH for calls, the phone's SIM for SMS/MMS.

### Local S3 — redundant/offline files
The phone hosts a MinIO-compatible object store holding the group's files
(`resource_scopes`: app = minio, per-bucket). Reads are offline; writes are
best-effort and reconcile to the shared MinIO when the mesh is reachable. This
is the *redundancy* layer — a member's phone is one more copy of the group's
media, in addition to the shared store.

### Offline store + Citus shard — data that travels
Two tiers:
- **Offline store (now).** SQLite or PGlite holding the owner's world-doc
  projection — their seats, the groups' visible records, recent events. Fully
  offline-read capable.
- **Citus shard (research).** A genuine Postgres shard running on-device, so
  the device *serves* a slice of the group's data to other members on the mesh
  rather than just caching for itself. This is the aspirational endgame and the
  least feasible piece — see §5.

### Maps — offline, self-hosted
MapLibre GL Native renders the coop's own PMTiles basemap bundled or prefetched
on-device, with the mapping tools talking to the maps server when online. A
member in the field has the terrain, the pins, and their tracks without a
connection.

## 4. How it maps to the group model

- **Scoping by seats.** The phone's data is exactly the world-doc for its
  owner — `group_members` → `resource_scopes` → per-app projections — filtered
  by seat visibility. Nothing more.
- **Sync is reconciliation, not a new protocol.** The device syncs by the same
  declared-vs-running reconciler the rest of the stack uses: it declares what
  it holds, compares to the shared store, and drifts toward agreement. The
  event bus is the transport; there is no bespoke sync engine.
- **The device is an unreliable peer.** It holds caches and relays, never
  quorum, never the treasury. A dead phone degrades to "that member is
  offline," not "the group lost data."
- **Provisioning is the same shape.** Enabling a phone as a node is a
  `config` axis of the group shape, provisioned by the same Temporal workflow
  that provisions every other app.

## 5. Honest feasibility

- **Real now.** SMS relay (TextBee is mature and already self-hostable), maps
  (MapLibre + PMTiles already runs in LiteFarm), the mesh (Tailscale has
  Android support), offline cache (SQLite/PGlite), notifications.
- **Hard but possible.** A long-running background S3 server (Termux can run
  MinIO, or a native S3-compatible server in the app), and keeping *any*
  long-running server alive against Android's background/battery limits
  (foreground service + battery exemptions).
- **Research.** A true Citus shard on a phone: Citus needs a coordinator and
  quorum; running it on Android and reconciling a flaky mesh of devices with
  the shared cluster is an open distributed-systems problem, not a port.

## 6. Open questions

1. **Background services.** How to keep a long-running S3/DB server alive on
   Android — foreground service, battery-optimization exemptions, Termux vs.
   native — without wrecking the owner's battery?
2. **Sync & conflict.** How does an offline shard reconcile? Last-write-wins
   over the event log? CRDTs for the document-y data? The reconciler needs a
   defined conflict policy.
3. **Honest duty cycle.** A phone can't host a busy group. What's the real
   budget — idle-when-plugged-in, sync-on-wifi-only, a cap on serving?
4. **Lost-device security.** A stolen phone must not leak the group's shard —
   hardware-backed key derivation, at-rest encryption, and a remote wipe path
   that doesn't depend on the phone being reachable.
5. **Carrier quirks.** MMS and short codes behave differently per carrier and
   region; TextBee covers most, but not all.

## 7. Why this matters

This is the sovereign endgame: the coop's infrastructure is a mesh of member
devices, not rented VPSes. SMS, files, data, and maps served from the
community's own pockets — the same way the group's *governance* is held by
members, its *infrastructure* becomes held by members too. A phone is the
smallest unit of that; a desktop or a home server is the same node at a
different scale.
