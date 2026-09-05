# Webstudio identity + `{groupname}.irl.coop` dynamic routing

Status: **design agreed, routing implemented, client widget built (HtmlEmbed starter), native SDK component not built**

## Problem

Webstudio is the AGPL visual builder/viewer layered over NocoDB-as-data. Two
things need to work together:

1. **Identity** — a published group site must show *that group's* data to a
   logged-in coop member, scoped by Postgres RLS (`app.sub`), without leaking
   across groups.
2. **Routing** — each group gets a live site at `{groupname}.irl.coop`, created
   dynamically as groups come and go, without a static route per group.

## Identity — what Webstudio actually does

Published Webstudio sites are **React Router apps**. Resources (data bindings)
are resolved **server-side during SSR**, not in the browser:

- `packages/sdk/src/resource-loader.ts` — `loadResource()` calls
  `customFetch(href, { method, headers })` with **no cookie jar and no
  `credentials`**; the `customFetch` is Node's `fetch`, which has no browser
  cookies.
- The `Resource` schema (`method`/`url`/`searchParams`/`headers`/`body`) only
  allows **static** headers baked at build time — no per-visitor identity.
- Generated pages split `_index.server.tsx` (SSR loader → `getResources()`) from
  `_index.tsx` (client hydration → `useResource()` reads back what the server
  already fetched).

**Consequence:** the visitor's `coop_session` cookie (which lives in the
browser, `.irl.coop`-scoped, `SameSite=Lax`) never reaches a Resource fetch.
Group-scoped data **cannot** ride Webstudio's native Resource system.

## Identity — the design (two layers)

1. **Builder authorization** (who edits a group's site) — *already solved* by
   the oauth2-proxy gate → coop-api OIDC (`webstudio-gate` client). Per-group
   authz is a follow-on (coop-api authorize already knows the caller's groups).

2. **Published-site data** (what a visitor sees) — fetched **client-side**, by
   the browser, so `coop_session` flows:

   - Webstudio renders **static chrome** (layout/nav/copy) via SSR — no
     identity needed.
   - A **`GroupData` widget** fetches the group's data **on the client** with
     `credentials: 'include'`: `GET https://api.irl.coop/api/v1/site/groups`.
   - **Gotcha (found in the code):** coop-api's data endpoints are
     **Bearer-only** (`verifyBearer`), not cookie-auth. The `coop_session`
     cookie *is* a valid coop JWT (same RS256 key, `sub`+`email`) but is only
     consumed by the authorize flow — so a static site (no token store) can't
     use the existing endpoints. Fix: a **session-authenticated read surface**
     (`/api/v1/site/groups`, `verifySessionRequest`) — the browser's cookie is
     the credential, verified directly. Writes stay Bearer-only (short-lived).
   - coop-api injects `app.sub` → **RLS scopes by group** (same injection
     NocoDB uses).
   - `coop_session` is `.irl.coop`-scoped and `SameSite=Lax`, so the
     cross-subdomain fetch (`{groupname}.irl.coop` → `api.irl.coop`) is
     *same-site* and the cookie is sent automatically; coop-api's CORS origin
     callback now allows `*.irl.coop` (verified live).

Net: **Webstudio = presentation; coop-api = identity + RLS; they meet
client-side via the `.irl.coop`-scoped session cookie.**

## The `GroupData` custom SDK component (specced, not built)

A **client-only** Webstudio component (registers in the builder's insert panel
like any other SDK component). Authoring model is the standard
`@webstudio-is/sdk-components-react` / `@webstudio-is/react-sdk` path:

- Props (meta): `groupName` (string), `apiBase` (string, default
  `https://api.irl.coop`), `endpoint` (string, default the group summary).
- Runtime: on mount (`useEffect` + `getInstanceIdFromComponentProps`-keyed
  state), fetch `${apiBase}/api/v1/groups/${groupName}${endpoint}` with
  `credentials: 'include'`; render loading / data / "sign in" states.
- Must be **client-only** (no SSR fetch) so the cookie is present at fetch
  time; Webstudio supports client-only components (SSR renders a placeholder).

This is the reusable building block dropped into every group template; site
authors wire `groupName` to the group slug.

## Dynamic routing — `{groupname}.irl.coop`

Webstudio already has the mechanism: the **publisher** serves published sites
by `Host` header (container port `4001`, `PROXY_PORT`), and each project carries
a **`Domain`** row (default `{projectId}.{PUBLISHER_HOST}` + arbitrary custom
domains). `PUBLISHER_HOST` = the apex `irl.coop`, so the default domain is
`{projectId}.irl.coop`.

Routing design (specific-over-wildcard):

1. Publish the publisher's site port to the host: `3004:4001`.
2. Traefik adds **one fallback router**:
   `HostRegexp(\`^[^.]+[.]irl[.]coop$\`)` → `172.17.0.1:3004` with
   **`priority: 1`**.
   - Single-label wildcard — `mygroup.irl.coop` yes, `irl.coop` (apex) and
     `a.b.irl.coop` no.
   - **Gotcha (verified live):** Traefik v3.5.6 rejects the `Host(\`*.irl.coop\`)`
     glob (`HostSNI … is not a valid hostname`); the `*` glob in `Host()` needs
     Traefik 3.7+. Use `HostRegexp`, and **`priority: 1` is mandatory** — a
     `HostRegexp` rule's default (rule-length) priority would otherwise *beat*
     the specific `Host(\`nocodb.irl.coop\`)` rules.
   - `priority: 1` loses to every specific `Host(\`nocodb.irl.coop\`)` etc.
     (default priority = rule length), so existing apps are untouched.
3. `*.irl.coop` wildcard cert already covers TLS — no new certs.
4. **Group → site provisioning** (the only new orchestration): when a group is
   created, provision a Webstudio project + a `Domain` row for
   `{groupname}.irl.coop` + seed a starter template. Custom-domain
   verification (Webstudio's TXT-record check) is bypassable for
   subdomains of our own apex — either auto-write the `_webstudio.{groupname}`
   TXT via Gandi LiveDNS or mark the row verified in the DB.

Unknown subdomains now fall through to the publisher (404 if no site), which
gives the correct "fallback" behaviour and makes group sites self-service.

## Publish targets — group, project, and bring-your-own domain

Recorded 2026-08-27 (extends the routing above: the two-level scheme is a
refinement; BYOD + the Vercel option + SSO-on-custom-domain are new).

### Target scheme

1. **Group site** — `{groupname}.irl.coop` (the group's default/home site).
2. **Project site** — `{clean-projectname}.{groupname}.irl.coop` (a specific
   Webstudio project under the group's namespace).
3. **Bring-your-own domain (BYOD)** — a member points `theircoop.org` at a
   published project.

The publisher already routes any domain by `Host` header via its `Domain`
rows, so 1 and 2 are only a **Traefik fallback-router widening**: the current
single-label `HostRegexp(\`^[^.]+[.]irl[.]coop$\`)` (priority 1) must also match
two labels (`{project}.{group}.irl.coop`) — e.g.
`HostRegexp(\`^[^.]+([.][^.]+)*[.]irl[.]coop$\`)` (one-or-more labels under the
apex, still excluding `irl.coop`). Specific app routes (`nocodb`, `api`, `auth`,
…) keep winning at their higher default priority. No new TLS — the wildcard
`*.irl.coop` cert already covers every depth.

### Bring-your-own domain

Webstudio already supports custom domains per project (a `Domain` row + TXT
verification). For a subdomain of our own apex the TXT can be auto-written via
Gandi LiveDNS; for a **foreign apex** (`theircoop.org`) the member adds the DNS
record themselves. Open decision: which service orchestrates verification.

**Vercel option (open):** rather than running the publisher for arbitrary
foreign domains, partner with Vercel for **API-based publish + routing** — build
the site in self-hosted Webstudio, ship the static/runtime output to Vercel via
their API, and let Vercel own DNS/TLS/routing for the custom domain. This keeps
the builder + data self-hosted (sovereignty) while delegating the commodity
edge. Trade-off to weigh: a third-party edge for published sites.

### SSO on custom domains — the hard part

`coop_session` is `.irl.coop`-scoped and `SameSite=Lax`, and coop-api's CORS
allowlist is `*.irl.coop`. Both break on a foreign domain (`theircoop.org`):

1. **Cookie** — a cross-site fetch from `theircoop.org` → `api.irl.coop` does
   NOT carry the `SameSite=Lax` `.irl.coop` cookie (different registrable
   domains), so the `GroupData` widget's `credentials:'include'` fetch fails.
2. **CORS** — `api.irl.coop` reflects only `*.irl.coop` origins.

Options to record (not decide):
- **Redirect flow** — the custom-domain site bounces to `auth.irl.coop`, gets a
  short-lived per-domain token, and injects it (OAuth-style, not a shared
  cookie). Most standard; needs a token delivery + refresh story.
- **SameSite=None + explicit origin allowlist** — widen the cookie and CORS to
  the specific custom domains. Weakens the cookie's cross-site posture; each
  BYOD domain must be registered.
- **Embedded identity only** — the custom-domain site carries no session itself;
  identity lives in an `.irl.coop` iframe that talks to the page via
  `postMessage`. Aligns with the iframe-embedding pattern already used for
  Plane/NocoDB.

The Vercel route complicates 1 further (the edge host may not share the
`.irl.coop` cookie at all), which is the strongest argument for a
redirect/token flow rather than cookie tricks.

## Decisions

- **Routing:** specific has priority over wildcard (explicit `priority: 1` on
  the single `*.irl.coop` fallback router).
- **Identity:** a custom SDK component fetches group data client-side through
  coop-api's RLS; no identity proxy, no Webstudio fork.

## Open items / next steps

1. **Client widget** — ~~(a) HtmlEmbed/Custom Code credentialed fetch~~ **done**
   (see `apps/webstudio/templates/world-doc-embed.html`): a self-contained
   HtmlEmbed block (set **client-only**, `clientOnly: true`) that fetches
   `/api/v1/site/groups` with `credentials: 'include'`, auto-detects the group
   slug from the `{group}.irl.coop` host, and renders the group header + Plane
   and NocoDB iframe panels. (b) a baked-in **`GroupData` SDK component**
   remains unbuilt (needs a builder+publisher image rebuild).
2. ~~coop-api session-auth + CORS~~ — **done**: `/api/v1/site/groups`
   (`verifySessionRequest`) + `*.irl.coop` CORS origin callback, verified live
   (401 without cookie; wildcard origin reflected; non-irlcoop origin blocked;
   bearer endpoints + dashboard origin unaffected).
3. Group → Webstudio project/Domain provisioning (which service orchestrates
   it, and how custom-domain verification is satisfied).
4. Per-group builder authorization (gate is identity-only today; needs
   group-membership scoping so a member can only edit their group's site).
5. ~~Verify on the live edge~~ — **done**: `nocodb.irl.coop`/`studio.irl.coop`
   still route to their specific apps (302), an unknown subdomain reaches the
   publisher (`Not found`), the apex is unaffected, and TLS is valid on the
   wildcard (no `-k`).
6. **Two-level routing** — widen the Traefik fallback to
   `{project}.{group}.irl.coop` (see "Publish targets" above), not just
   `{group}.irl.coop`.
7. **BYOD orchestration** — which service verifies a foreign custom domain
   (TXT / Gandi auto-write) and creates the publisher `Domain` row.
8. **SSO on custom domains** — pick a flow (redirect/token vs SameSite=None
   allowlist vs embedded-identity iframe); the `.irl.coop` cookie + CORS do not
   reach foreign domains today.
