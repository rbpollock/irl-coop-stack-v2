# Group "world-doc" starter template

A self-contained block that turns a Webstudio site into a **group world-doc**:
the group's identity (fetched live from coop-api, scoped by your permissions via
Postgres RLS) plus embedded **Plane** and **NocoDB** panels.

## Files

- `world-doc-embed.html` — the drop-in snippet. It is a full HTML document for
  local preview; the **copy region** is between the `COPY FROM HERE` / `COPY TO
  HERE` markers.

## Install in Webstudio

1. In the builder, insert an **HtmlEmbed** component.
2. Open its Settings and paste the copy region (the `<style>`, the
   `<div id="world-doc">`, and the `<script>`) into the code field.
3. Set the component to **CLIENT-ONLY** (`clientOnly: true`). **Required** — the
   fetch must run in the browser so the `coop_session` cookie is sent.
   (Server-side render has no cookie and would 401.)
4. Publish and open the site at `{group}.irl.coop` while signed in to the coop.

## Config

Set via `data-*` attributes on the `#world-doc` div (or edit the values at the
top of the script):

| Attribute | Default | Meaning |
|---|---|---|
| `data-api` | `https://api.irl.coop` | coop-api base URL |
| `data-plane` | `https://plane.irl.coop/?embed=1` | Plane iframe (add `?embed=1` to hide chrome) |
| `data-nocodb` | `https://nocodb.irl.coop` | NocoDB iframe (or a shared/embedded view URL) |
| `data-group` | (auto) | Hard override for the group slug |

## Behaviour

- If the current hostname's slug matches one of your groups → that group's
  world-doc (name, description, kind/privacy, your roles, Safe treasury
  address) + the Plane and NocoDB panels.
- Otherwise → a **"Your groups"** index (every group you have permissions to).
- Signed out → a "Sign in to irl.coop" prompt (the endpoint 401s without the
  session cookie).

## Verify

- Endpoint contract (live): `GET https://api.irl.coop/api/v1/site/groups`
  returns 401 without a cookie, reflects `Access-Control-Allow-Origin` only for
  `*.irl.coop`, and returns `{id, safe_address, name, description, privacy,
  kind, created_at, roles, alias, visibility}` rows RLS-scoped to the caller.
- Full E2E: view the published site at `{group}.irl.coop` while signed in —
  the header shows your group, and Plane/NocoDB load inside their panels.

## Not yet built (next steps)

- **Per-group Plane/NocoDB scoping** — the panels are generic app embeds today.
  coop-api has `resource_scopes` (`POST /api/v1/groups/:id/resources`, Bearer)
  to record a group's Plane project / NocoDB base, but there is no
  session-auth read surface yet; the widget would fetch the group's scoped
  resources and point the iframes at them.
- **Auto-provisioning** — seeding a Webstudio project + `Domain` row +
  this template when a group is created (design doc: "Group → site
  provisioning").
- **Formbricks panel** — blocked until Formbricks is deployed to the stack.
- **Native `GroupData` SDK component** — the zero-rebuild HtmlEmbed path is the
  recommended first step (see `docs/design/webstudio-identity-and-group-routing.md`);
  graduating to a baked-in component means rebuilding the builder + publisher images.
