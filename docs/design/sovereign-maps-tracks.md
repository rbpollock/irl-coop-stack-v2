# Sovereign maps & tracks (OpenMapServer)

Status: design. Date: 2026-08-29.
Companions: `group-app-integrations.md` (SSO wishlist), `integration-first-templates.md`
(Track B portal blocks), `resolver-v2-and-qa.md` (QA gate).

## Goal

A self-hosted, group-aware, privacy-preserving map + track stack on this host, with
**zero dependency on Google / Apple / Mapbox / any external map source**. "OpenMapServer"
is the umbrella name for our self-hosted OpenStreetMap stack — OSM data + a basemap tile
layer + (later) geocoding + routing, all answering from our own infra.

Hard requirements from Robbie:

- **Coverage**: start with **the US (`us-latest`, full US incl. AK/HI)**; the architecture
  MUST expand to global. Specific near-term additions: **Venezuela, UK, Germany, Nigeria**
  (existing users there).
- **Scope now**: basemap + track display. **Geocoding + routing are designed early** so
  they weave in without rework.
- **Tracking = all of the above**: member activity trails, group delivery/field routes,
  live location, **and user-made "geo-tours"** — a gated-for-review "historical walk"
  through a town with audio, links, and AR overlays.

## Principles

1. **Sovereignty** — every byte (tiles, geocoding, routing, track data) serves from this
   host. No third-party tile CDN, no telemetry, no API keys.
2. **Composable coverage** — geography is a *set of named regions*, each an OSM extract.
   Adding a country = one region entry; never a schema/code change. Planet is the union of
   regions, not a separate mode.
3. **Group-aware** — tracks/tours are scoped to the canonical group slug (host resolver),
   authorized by coop-api session, row-level-secured.
4. **Privacy-first** — location is surveillance-sensitive (same stance as telephony).
   Anonymous basemap (shared, identity-free) vs. authenticated tracks (scoped, minimal
   retention, blur on share, ZK "in-region" attestation).
5. **Licensing-clean** — OSM basemap data is ODbL (attribution + share-alike for the *data*,
   not our tracks); our track/tour content is ours.

## Coverage model (the backbone)

One region definition fans out to three derived artifacts (basemap PMTiles, geocoder
import, routing graph). Declared in the instance tree so it's generator-managed:

```yaml
# infra/instances/dev/geo/regions.yaml  (illustrative)
regions:
  - id: us
    name: "United States (us-latest)"
    bbox: [-172.0, 18.0, -66.0, 72.0]         # full US incl. AK/HI/territories
    extract: geofabrik/us-latest.osm.pbf
    enabled: true
  - id: venezuela
    bbox: [-73.6, 0.6, -59.8, 12.3]
    extract: geofabrik/venezuela-latest.osm.pbf
    enabled: false
  - id: uk
    bbox: [-8.7, 49.8, 1.8, 60.9]
    extract: geofabrik/great-britain-latest.osm.pbf
    enabled: false
  - id: germany
    bbox: [5.8, 47.2, 15.1, 55.1]
    extract: geofabrik/germany-latest.osm.pbf
    enabled: false
  - id: nigeria
    bbox: [2.6, 4.2, 14.7, 13.9]
    extract: geofabrik/nigeria-latest.osm.pbf
    enabled: false
```

- **Basemap**: build a PMTiles extract per region (`pmtiles extract`) → merge into one
  `coverage.pmtiles` via `tile-join`. Serve the merged file from MinIO.
- **Geocoder**: Nominatim `--import` each region's PBF into the same instance (multi-region
  import is supported; planet is the same path with more imports).
- **Router**: Valhalla `valhalla_build_tiles` accepts multiple PBFs into one graph (this is
  why Valhalla is the pick over OSRM — see Routing).

Adding a region later = add one YAML entry + one extract download + rebuild the affected
artifact. Planet = add a `planet` entry (large, ~70GB PBF) — no architecture change.

## Architecture overview

```
group site (Webstudio) ──HtmlEmbed──▶ MapLibre GL JS + PMTiles client
        │  (fetch, coop_session cookie)
        ▼
   coop-api  ──▶ geo routes (tracks/tours/geocode/route)
        │
        ├──▶ Citus irlcoop (+ PostGIS): groups, RLS, tracks/markers
        │                              (+ geocoder/route indexes, later)
        └──▶ MinIO (maps bucket): PMTiles + tour media (audio/AR)
```

Components:

| Component | Role | Status |
|---|---|---|
| **PMTiles basemap** | vector tiles in one file, served from MinIO | now |
| **MapLibre GL JS** | client renderer (BSD, no key, no telemetry) | now |
| **shared Citus + PostGIS** | groups + RLS + track/marker geometry (geocoder/route indexes later) | now (tracks), later (geo/route) |
| **coop-api geo routes** | group-aware API (session auth + RLS) | now (tracks), later (geo/route) |
| **Nominatim** | forward + reverse geocoding | designed, later |
| **Valhalla** | routing (A→B, multimodal) | designed, later |

## Basemap (now)

- **PMTiles** (protomaps) — the whole basemap is one file. It needs only HTTP **range
  requests**, which MinIO/S3 already serve, so **there is no tile server**. `maps` bucket
  (public-read) served through the existing `s3api.irl.coop` edge (MinIO :9000).
- **Subdomain** — `maps.irl.coop` is the public surface: a tiny nginx static app (the
  `maps` pillar, host :3009) serving `index.html` + the self-hosted libs
  (`maplibre-gl.js` 5.24.0, `pmtiles.js` 4.5.0, css) + glyphs from a durable dir
  (`/opt/app/storage/geo-data/web/`). Tiles stay on MinIO — the `pmtiles://` source points
  at `s3api.irl.coop/maps/coverage.pmtiles` (the pmtiles client's `Range` fetch is
  cross-origin-safe via the MinIO `MINIO_API_CORS_ALLOW_ORIGIN: "*"`). Zero external
  mapping deps.
- **Glyphs (self-hosted)** — `Noto Sans Regular` + `Noto Sans Bold` SDF glyphs are served
  from `maps.irl.coop/glyphs/{fontstack}/{range}.pbf` (256 ranges × 2 stacks, ~69 MB).
  Source = MapLibre's own demotiles font host — **NOT** `fonts.openmaptiles.org`, which
  serves a single 2.7 KB placeholder for every range (so labels silently never rendered).
  Fetch via `infra/scripts/fetch-maps-web.sh`; the versioned style is
  `infra/scripts/map-embed.html`.
- **Schema** = **OpenMapTiles** (Planetiler's default, 16 layers: `water`, `waterway`,
  `landcover`, `landuse`, `park`, `building`, `transportation`, `transportation_name`,
  `boundary`, `place`, `poi`, `water_name`, `aeroway`, `aerodrome_label`, `mountain_peak`,
  `housenumber`), maxzoom **z14**. NOT shortbread — the real layer names + field lists are in
  the archive's gzip-compressed `vector_layers` metadata (see `/tmp/inspect-pmtiles.py`).
- **Client**: MapLibre GL JS **5.x** (self-hosted `maplibre-gl.js`; 4.7.1 had a custom-protocol
  worker-handoff bug that rendered vector tiles empty — "Unimplemented type: N" — so 5.24.0
  is pinned) + `pmtiles` plugin **4.x** (self-hosted; 3.2.0 works but 4.5.0 is current). No
  API key. The style is our own (earthy palette, no brand watermark) — a produced work,
  attribution-only (`© OpenMapTiles © OpenStreetMap contributors`).
- **CORS**: MinIO does NOT implement the S3 `PutBucketCors` API (returns 501) — cross-origin
  tile fetch is enabled via the server env `MINIO_API_CORS_ALLOW_ORIGIN: "*"` in the minio
  app spec. The pmtiles client's `Range` header is CORS-safelisted (no preflight), so a bare
  ACAO is all it needs; MinIO echoes the request origin + exposes `Content-Range`.
- **Build**: `infra/scripts/build-pmtiles.sh` (Planetiler docker) writes to host scratch
  `/opt/app/storage/geo-data/` — NOT `infra/out/`, which the generator `rmtree`s on every run
  (it deleted a finished 9.9 GB pmtiles once). Sources cached there so re-runs skip the
  12 GB download. Upload to MinIO via `infra/scripts/upload-pmtiles.py`.
- **Footprint**: `us-latest` ≈ **9.9 GB** pmtiles (source extract 12.1 GB); merged with the 4
  named countries ≈ 15–25 GB. Planet basemap ≈ 110 GB (still fits 175G, but deferred).
- **Privacy note**: basemap requests are *anonymous* (no auth → the server learns "someone
  looked at area X", never *who*). Keep tile access logs off; this is the clean boundary.

## Tile caching

PMTiles changes the caching question: there are no discrete tile URLs from a tile server —
MapLibre's `pmtiles` protocol reads arbitrary **byte ranges** of one file straight from
MinIO. So "caching tiles" means caching HTTP range responses, and the layers are, in order:

1. **Browser HTTP cache (primary, free)** — a vector tile at `z/x/y` never changes. Serve
   the basemap PMTiles and the self-hosted libs with `Cache-Control: public,
   max-age=31536000, immutable`; every repeat pan/zoom is served locally, zero server load.
2. **MapLibre's built-in LRU + the pmtiles JS directory cache** — in-session; the tile
   *directory* (a few KB) is fetched once and cached in memory.
3. **Edge / caching reverse proxy** (Traefik or a CDN) in front of the bucket — *optional*;
   only matters for multi-user cold-start locality, and it must honour range requests
   correctly. On a single host MinIO already reads local disk fast, so this is usually
   unnecessary for us.
4. **Service Worker + CacheStorage** — the offline layer (apocalypse model): pre-seed a
   region's tiles so the map keeps working with no network.

**Redis is the wrong tool for tile bytes.** It "works" mechanically but fights the design:
tiles are range-addressed (you'd need a tile server in front to key them `tile:z/x/y`,
which resurrects exactly the server PMTiles deletes), large + immutable (the US pyramid is
GBs of RAM to hold bytes MinIO serves fast from disk, most never touched by any one user),
and have huge cardinality but narrow per-session locality — which an HTTP/browser disk LRU
handles better and cheaper. Redis belongs where the request is *small, hot, mutable*:
geocode results, Valhalla routing responses, rate-limit counters, and a small "nearby active
markers" set — never the tile payloads themselves.

## Tracks & geo-tours (now — the rich part)

### Content model

Two geometry tables cover everything with a location:

```
track (paths — LineString)
  id, group_id (canonical slug), owner_id, kind: trail|route|tour
  geometry: LineString (PostGIS), timestamps: timestamptz[] (trails only)
  title, description
  category: vertical, tags: []          # federation filter axis
  visibility: private|contact|group|federated|public
  review_status: draft|submitted|approved|rejected   (tours only)
  created_at, updated_at

marker (points — Point)
  id, group_id, owner_id, source: pin|plane|nocodb|hievents|booking|…
  point: Point (PostGIS), title, url (deep-link to source app)
  category: vertical, tags: []          # federation filter axis
  visibility: private|contact|group|federated|public
  time?, expires_at?   (bookings/events; TTL for ephemeral shares)
  created_at, updated_at

waypoint (tours/routes)
  track_id, seq, point: Point (PostGIS)
  title, description
  media: [{type: audio|photo|link|model-3d|panorama|ar-anchor, ref: minio-key, ...}]
```

- **marker** unifies the two point sources: user-dropped **pins** (`source: pin`) and
  app-originated **location-bearing records** (LBRs, `source: plane|nocodb|…`). Same
  table, same visibility + RLS, different provenance.
- **track.kind**: `trail` (raw GPS recording), `route` (planned path), `tour` (curated +
  waypoints + review gate).
- **`category`/`tags`** are the **federation filter axis** — the vertical-first taxonomy
  Explore mode filters on. Starter set: `food`, `housing`, `care`, `energy`, `skills`,
  `commerce` (businesses), `event`, `resource` (coop locations / shared assets), `tour`
  (geo-tours), `governance`. It is data, not code — refine freely as verticals firm up.

- **trail** = raw GPS recording (member activity). Private by default.
- **route** = planned path (delivery/field). Group-scoped.
- **tour** = curated route with **waypoints**, each carrying **audio** (a clip),
  **links**, **photos**, and an **AR overlay** (a `model-3d` `.glb` or an `ar-anchor`
  historical-photo). `review_status` drives the gate.

### Review gating (tours)

`draft → submitted → approved|rejected` by a group role (a `tour-moderator` capability in
the group shape). Approved tours flip `visibility=public` (or the group's chosen scope) and
are the only tours the group's public site renders. Rejected returns to `draft` with a
reason. This is the same moderation posture as your governance/facilitation work — who
approves is a *group role*, not a hard-coded admin.

### AR overlays — phased renderer, same content model

The `media.type` enum is fixed up front; the *renderer* evolves:

1. **v1 — in-map overlay**: tap a waypoint → card with audio (Web Audio API), photos,
   links; a `model-3d` renders via `<model-viewer>`.
2. **v2 — WebXR AR**: a `ar-anchor` (image or geo anchor) opens a device-camera overlay
   (three.js / WebXR). No external SDK; mobile-only.

Designing `media.type` now means v2 needs no schema change — it's a new renderer on the
same `ar-anchor`/`model-3d` refs.

## Geocoding (designed early, built later)

- **Nominatim** (single Postgres, no Elasticsearch) — the sovereign default. Import each
  region's PBF (`--import` per region; multi-region supported; planet is more of the same).
- Served as `POST /api/v1/geo/geocode` (address → coord) and `POST /api/v1/geo/reverse`
  (coord → address). Not group-scoped — addresses are public utility — but only callable
  with a session (rate-limited) to avoid being an open proxy.
- **Weave-in point**: geocoding is consumed by *group apps* (e.g. a marketplace listing
  "pickup at this address"), not by the tile/track path. Its region set is the same
  `regions.yaml`, so coverage stays in one place.

## Routing (designed early, built later)

- **Valhalla** over OSRM *because* it merges multiple PBFs into a single graph
  (`valhalla_build_tiles` takes N extracts) — matches the composable-region model exactly;
  OSRM is one graph per region. Valhalla also does multimodal (bike/pedestrian) which the
  coop verticals want.
- Served as `POST /api/v1/geo/route` (A→B + waypoints, profile auto/car/bike/foot).
  Public utility (session + rate-limit), not group-scoped — but *saved* routes are group
  tracks (above).
- **Weave-in point**: route requests hit the same `regions.yaml` graph; a group's delivery
  route = a saved `route` track rendered on the shared basemap.

## Group-aware + privacy

- **Auth**: coop-api session cookie (identical to `/api/v1/site/groups`). The Webstudio
  HtmlEmbed fetches `GET /api/v1/groups/:slug/tracks` and overlays GeoJSON on MapLibre.
  No new auth surface.
- **Scoping**: `track.group_id` = canonical group slug; federated "group-of-groups" maps
  are *compositions* (union of member-group layers), consistent with seeds-not-cages.
- **RLS** — the geo tables live in the shared Citus alongside `groups`/`membership`, so
  the existing `coop_rls` + `app.sub` FORCE-RLS pattern applies directly: a session can
  only read rows whose `group_id` it is a member of. No separate trust boundary.
- **Privacy techniques** (location = surveillance-sensitive):
  - Encrypted at rest (PGCrypto / app-level).
  - **Geohash blur** on share — coarse cells, never raw points.
  - **Ephemeral live-sharing** — consent + expiry, coarse-grained.
  - **Retention** — auto-expire raw trails (configurable per group).
  - **ZK "in-region" attestation** — prove membership in an area without revealing the
    track (ties to hidden-norm proofs / regenerative score).
- **Visibility tiers** (5-tier scope, on `track` and `marker`): `private` (owner) →
  `contact` (a named member/contact) → `group` (members) → `federated`
  (group-of-groups) → `public` (approved tours/pins).
- **Share** — a `share` grant (marker/track/location → contact or group) raises access
  above the baseline tier without rewriting the row: "share this pin with contact X /
  group Y / all members", optional `expires_at` for ephemeral shares. Live-location
  sharing is the same mechanism, TTL'd by default.
- **Explore-by-default** — the map opens in *browse/explore* mode: the basemap plus ALL
  **public** content from **every nearby group** in the federation — businesses, coop
  locations, geo-tours, markers — regardless of which group the viewer belongs to.
  Filterable by **vertical category** + tags (see `category`/`tags`). The viewer's own
  group/private layers reveal as they authenticate. Discovery is federation-wide and
  vertical-first; private content stays behind the session.

### Group visibility policy (each group sets its own ceiling)

Beyond the per-object `visibility` tier, each group declares a **visibility policy**
(part of its group *shape* — the `config`/`governance` axis) that governs how its map
objects are exposed:

```yaml
visibility_policy:
  discoverable: federation | hidden              # does public content surface in federation explore?
  max_visibility: group | federated | public     # ceiling a member may set
  default_visibility: private | group            # default for a new marker/track
  require_approval: [public, federated]          # tiers needing moderator sign-off
```

- **discoverable** — a `hidden` group's public objects never appear in the federation
  explore map (only via direct link/invite); a `federation` group contributes to the
  vertical-first discover feed.
- **max_visibility** — bounds every object's tier: a group capping at `group` stops
  members from broadcasting `public`.
- **default_visibility** — what a new marker/track starts as, so a member dropping a quick
  pin can't accidentally go public.
- **require_approval** — generalizes the tour review gate: any object published at a
  listed tier (or a listed category) needs a moderator before it is visible.

**Resolution order** when rendering: *capability* (may the member act) → *group policy*
(what may this group's objects do) → *object tier / share / review* (this object's
access). Group policy is data on the group shape, editable per group with no code change.

## API surface (coop-api)

```
# tracks / tours (session auth, RLS by group slug)
GET    /api/v1/groups/:slug/tracks          # list (filter by kind/visibility/category)
POST   /api/v1/groups/:slug/tracks          # create trail/route/tour
GET    /api/v1/groups/:slug/tracks/:id      # track + waypoints + media
PUT    /api/v1/groups/:slug/tracks/:id
DELETE /api/v1/groups/:slug/tracks/:id
POST   /api/v1/groups/:slug/tours/:id/submit   # draft -> submitted
POST   /api/v1/groups/:slug/tours/:id/review   # approve|reject (tour-moderator)
GET    /api/v1/groups/:slug/tours              # approved tours only (public site)

# markers / pins (session auth, RLS)
GET    /api/v1/groups/:slug/markers            # list (filter by source/visibility/category)
POST   /api/v1/groups/:slug/markers            # drop a pin
PUT    /api/v1/groups/:slug/markers/:id
DELETE /api/v1/groups/:slug/markers/:id
POST   /api/v1/groups/:slug/markers/:id/share  # share with contact/group (ttl)

# comments (NocoDB-backed; capability-gated)
GET    /api/v1/groups/:slug/markers/:id/comments
POST   /api/v1/groups/:slug/markers/:id/comments

# federation discover (explore mode — public content across all groups)
GET    /api/v1/discover/map                    # public markers/tours near bbox, filter by category

# share the view
POST   /api/v1/groups/:slug/map/link           # encode current view -> short link
POST   /api/v1/groups/:slug/map/render         # current view -> PNG (MinIO), returns link

# live location (consent, ephemeral, coarse)
POST   /api/v1/groups/:slug/live               # share my blurred location (ttl)
GET    /api/v1/groups/:slug/live               # others' shared locations

# geocoding + routing (public utility, session + rate-limit) — designed, built later
POST   /api/v1/geo/geocode
POST   /api/v1/geo/reverse
POST   /api/v1/geo/route
```

## Deployment (declarative pillar)

New `geospatial` pillar in `infra/instances/dev/`:

- **shared Citus + PostGIS** — extend `infra/build/images/postgres-citus/Dockerfile` with
  `postgresql-16-postgis-3` (bump tag → `irlcoop/postgres-citus:12.1-vector-postgis`),
  update `apps/citus.yaml` image, recreate the container (dev downtime OK), then
  `CREATE EXTENSION postgis;` in the `irlcoop` db. Geo tables (`track`/`marker`/`waypoint`)
  live in `irlcoop`, distributed by `group_id` (shard-ready for future Citus workers, incl.
  client-hosted devices reachable via a Tailscale mesh — CGNAT), under the existing
  `coop_rls` + `app.sub` RLS. No separate Postgres.
- **maps bucket** — MinIO `maps` (public-read) for `coverage.pmtiles` + tour media
  (audio/photo/glb). Tour media is *not* public-read when private — serve media through a
  coop-api signed path (`/api/v1/groups/:slug/tours/:id/media/:ref`), not the raw bucket.
- **edge** — `maps.irl.coop` → the `maps` nginx static app (embed + libs + glyphs; the
  `maps` pillar); tiles via `s3api.irl.coop/maps/` (MinIO); `geo.irl.coop` → coop-api geo
  routes (later).
- **geocoder / router** — later services in the same pillar, fed by `regions.yaml`.

## Stack integration

Geo is **cross-cutting, not a silo**: one engine, three embed modes, plus an
aggregation layer every app feeds.

### Three surfaces (one engine)

| Mode | What it is | Used by |
|---|---|---|
| **Browse** | full map surface — explore public tours/pins, my tracks, route planner | dashboard side nav (`/apps/map`, a Next.js route) |
| **Embed** (`?embed=1`) | map + group content inline, chrome hidden | Webstudio group sites, dashboard widgets |
| **Pick** (`?mode=pick`) | "choose a location" → returns lat/lng via `postMessage` | Plane destination, booking location, listing address |

### Side nav

"Maps" joins the nav the way Plane does — a route (`/apps/map`) in the Coop section that
iframes `maps.irl.coop` (see `apps/web/irl-dashboard/src/app/[lang]/(dashboard-layout)/
apps/map/page.tsx`). The nav/user-menu also gets a lightweight **"share my location"**
affordance (the blurred, TTL'd live-share), because location is a recurring action, not an
app you open.

### Webstudio embed (now)

Group sites embed the map as a plain iframe — the map is public (basemap + federation
explore), so no cookie is needed. Drop the HtmlEmbed snippet in
`apps/webstudio/map-embed.html` into any page: an iframe to `https://maps.irl.coop/`
(fills its container, `loading="lazy"`, `allow="fullscreen"`). The group-specific
tracks/markers overlay (credentialed `fetch` with `coop_session`) arrives when the tracks
endpoints land — same iframe, the map reads the session cookie from its own origin.

### Browse/explore as the group default

A group's map surface opens in **explore mode by default**: the basemap + public tours
+ public pins across the federation, with the viewer's own group/private layers revealed
as they authenticate. Members can drop **permission-scoped pins** (5-tier visibility)
and **share** them with contacts/groups (TTL optional).

### Plane — "set a destination"

1. A **Pick-mode embed** in the issue lets the assignee drop a pin (geocode the address
   via `/geo/geocode`) instead of typing coordinates.
2. Plane's **outgoing webhook** fires on issue update → coop-api geocodes the "Location"
   field → writes a **marker** (`source: plane`, deep-link back to the issue).

The group map then shows a **Destinations** layer (every task with a location) and
"route me to all my open destinations" is a one-click saved route.

### Bookings (roadmap)

A booking = a marker **with `time`** (`source: booking`). The calendar gets a **map
view** (pins on a timeline), routing between appointments, and **geofence check-in**
("within arrival radius → mark attended") from the live-location machinery.

### Everything with an address

| App | Integration | Via |
|---|---|---|
| Hi.Events (events) | venue pin + "directions" on the ticket | webhook → marker |
| NocoDB (marketplace) | pickup/delivery location + route | marker (workspaces API) |
| Webstudio (group sites) | geo-tours, member maps, delivery tracking | Embed mode |
| Telephony | field-worker dispatch, "where's my driver" (consent) | live-location |

### Location-bearing records (LBRs) = markers

`marker.source` distinguishes provenance (`pin` = user, `plane|nocodb|hievents|booking`
= app). Every app that has a location registers a marker; the group map renders
**tracks + markers** as one coherent view — "where is everything in my group" in one
place, with routing/geofencing operating over the union.

### Share (view, not just markers)

Three share levels:

- **marker/track** — the existing `share` grant (contact/group, optional TTL).
- **view as link** — a URL encoding the current map state (`?center&zoom&layers&category`
  …), so a filtered, zoomed "here are all the food coops near us" view is one link.
- **view as image** — server-side render of the current view (MapLibre GL Native → PNG)
  to MinIO, returned as a shareable link/attachment. No client screenshot needed.

### Comments + capability gating

- **Comments** — a `comment` table on markers/tours (author, body, created, moderated),
  surfaced + edited through **NocoDB** (the stack's table/records surface), so moderation
  reuses NocoDB's existing UX instead of building a new thread UI.
- **Capability gating** — commenting and federated/public sharing are **gated by
  capabilities**, not free. The gate is metric-agnostic: it works with a group role or a
  flag today, and is designed to accept **ZK-verified credentials** later — a
  **regenerative-score** threshold and a **"dues-paid" badge** (a ZK proof that the member
  pays their irl.coop usage costs). The capability interface is the stable seam; the ZK
  metrics are a separate (roadmap) system that plugs into it. Gating ships with roles now,
  and swaps in ZK badges when they exist. Capability is layer 1 of the three-layer
  resolution — *capability → group visibility policy → object tier* (see Group-aware + privacy).

## Offline-first device sharding ("apocalypse" / state-collapse resilience)

The distributed-storage goal is **survival**: the system keeps working when the
coordinator is down or the network is partitioned. Confirmed model:

- Each **device owns its shard** — records it authors live on the device and are
  **authoritative there**; it reads/writes offline with no coordination.
- The **coordinator tolerates offline shards** — an unreachable device just doesn't
  contribute to distributed reads until it reconnects.
- **Merge-on-reconnect** — offline writes replay through the event bus
  (`irl:notify:{sub}`) and merge deterministically (last-write-wins by hybrid clock).

This changes the schema in ways that must land now (retrofitting = migration):

1. **Time-ordered, client-generated ids** — ULID / UUIDv7 (sortable by time), minted on
   the device, not the server. Server-side UUIDv4 has no ordering for offline merge.
2. **Hybrid-logical-clock `updated_at`** — device-clock + logical counter, so
   last-write-wins resolves across devices with skewed clocks. Plain `now()` is not a
   safe merge key.
3. **Tombstones** (`deleted_at`) — soft delete, never hard delete: a hard-deleted row
   would resurrect on the next merge from an offline replica.
4. **Distribute by `owner_id`, not `group_id`** — the device's shard is self-contained
   (offline reads/writes hit only its own data). Group reads become a coordinator-side
   distributed query across member shards (works when online).
5. **Split geometry (privacy vs queryability)** — PostGIS indexes only plaintext, so:
   - `geohash` (coarse, ~city-block precision, low sensitivity) — plaintext, indexed, for
     "near me" / federation explore.
   - `geometry` (precise) — plaintext for `public`/`federated` records (indexed), and
     **encrypted client-side** for `private`/`group` records (coordinator sees ciphertext;
     precise spatial queries on private data run device-side). Encryption is phase-2
     hardening — the column split is in the schema now so it's not a migration later.
6. **Outbox / event-log** — every change emits an event (the existing Temporal outbox
   pattern) carrying the HLC timestamp + tombstone state, so reconnect = replay.

Privacy note: the coordinator stores ciphertext for private records and cannot decrypt
(device holds the key; group keys via Shamir per the vault design). It still serves
*coarse* "near" queries on the plaintext `geohash` without ever seeing precise
locations. That split is the privacy/optimization boundary.

## Licensing boundary (ODbL)

- OSM basemap **data** is ODbL — requires attribution ("© OpenStreetMap contributors") and
  share-alike *for the data*. Our vector-tile **style** is a produced work (attribution
  only). Our **tracks/tours/media** are ours, unencumbered.
- Consequence: keep the basemap layer separable from our content (which it already is —
  tiles vs GeoJSON overlay), and keep the attribution line on the map control.

## Phasing

1. **Now** — PostGIS in shared Citus + track/marker/waypoint schema + RLS; coop-api
   `groups/:slug/tracks` + `markers` endpoints; `maps` bucket + `us-latest` PMTiles;
   `maps.irl.coop` subdomain + self-hosted Noto glyphs; MapLibre embed (HtmlEmbed) rendering
   tracks/markers on the basemap; dashboard `/apps/map` + Webstudio iframe.
2. **Next** — geo-tours (waypoints + media + review workflow + audio/photo renderer);
   add the 4 named countries as regions.
3. **Then** — Nominatim geocoding; Valhalla routing; AR renderer (model-viewer → WebXR);
   live-location + ZK attestation.

## Settled decisions

- **Routing = Valhalla** (multi-PBF merge, multimodal).
- **Geocoder = Nominatim** (self-contained, no Elasticsearch).
- **AR v1** = in-map overlay + `<model-viewer>`; true WebXR later on the same `media.type`
  schema.
- **Coverage** = start `us-latest` (full US incl. AK/HI); expand to Venezuela / UK /
  Germany / Nigeria, then global, via the region model.
- **Map surface** = the `maps.irl.coop` subdomain (nginx static), a dashboard route
  (`/apps/map`, iframes it), and a Webstudio HtmlEmbed iframe.
- **Plane integration** = location custom-field + outgoing webhook (no fork).
- **Tile cache = browser HTTP cache (`immutable`) + optional edge/CDN; NOT Redis.** Redis
  is reserved for geocode/route/rate-limit (small, hot, mutable) results only.
