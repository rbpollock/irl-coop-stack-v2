# Integration-first templates (Track B)

Status: design. Date: 2026-08-28. Companion: `group-app-integrations.md`
(the SSO wishlist), `marketplace-template-strategy.md` (Track A/B), `resolver-v2-and-qa.md`.

## The one idea

A group's Webstudio site is a **portal, not a brochure**. Every template is a
presentation shell whose sections are built *around* integration slots — the
stack's group-aware apps embedded by the group slug from the `{group}.irl.coop`
host. Marketing copy is the filler between working surfaces, not the point.

This is the answer to the resolver problem too: templates are authored **natively**
(hand-written `<ws.element>` JSX via the CLI, like the Co-op items — 0% broken),
so fidelity is a non-issue and the effort goes into the integrations instead.

## Integration inventory (what a template can actually embed)

| App | Status | Embed mechanism | Template block |
|---|---|---|---|
| Identity / member | live | `GET /api/v1/site/groups` (session auth, `coop_session` cookie, CORS `*.irl.coop`) | header: avatar + name + group |
| Group data | live | same endpoint | "about / members" section |
| Chat | live | Element embed per-room (Matrix) | chat block |
| NocoDB data | live | iframe via Gate-SSO (`x-forwarded-email`) | listings / tables / inventory |
| Plane | live | iframe (zero-click SSO) | projects/roadmap block |
| Webstudio CMS | live | n/a (this is the site itself) | every section |
| Blog | live (Postiz) | iframe | posts feed |
| Forms | pending | Formbricks (enterprise SSO gate) + native `<input>` parser gap | forms block |
| Calendar / availability | not started | — | free/busy block (placeholder) |
| Treasury | spec only | group Safe + private ledger, no custody | balances/ledger (placeholder) |
| Voting / governance | design only | ZK membership proofs + append-only log | proposals/activity (placeholder) |
| Phone-banking | live (switch) / log design-only | SIP/WSS softphone embed | call/directory block |

**Rule:** a block for a *pending* integration ships as a clearly-labelled
placeholder ("calendar coming soon"), never a fake surface. Live integrations are
first-class; placeholders are honest.

## Embedding contract (settling the open question)

iframe + `postMessage` (the Plane/NocoDB pattern) for **apps**, and a credentialed
`fetch` for **data blocks**:

- **Apps** (Plane, NocoDB, Postiz, Element): `<iframe src="https://<app>.irl.coop/<group>">`.
  Auth rides the gate/SSO cookie; the app scopes itself to the group slug. Cheap, isolates
  auth, no shared React state (acceptable — these are whole apps, not widgets).
- **Data blocks** (identity, group info, free/busy, balances): an HtmlEmbed / Custom-Code
  block that does `fetch('/api/v1/site/groups', {credentials:'include'})` and renders.
  Read-only session surface today; writes stay Bearer-only (see `webstudio-self-host` gotcha 8).
- **Chat**: Element's own per-room embed (already has the room-scoped iframe + token flow).

## Vertical templates (seed-not-cage)

Each is a parameterized seed (name/palette/content slots), not a rigid layout. First five:

1. **Group home** — identity header → "what we do" → chat block → upcoming events →
   marketplace listings → treasury snapshot → governance activity. *The default.*
2. **Marketplace / orders** — listings (NocoDB), cart/order state, inventory, member pickup.
3. **Events / calendar** — event grid, free/busy, RSVP, past-event archive.
4. **Governance / decisions** — open proposals, vote (weighted), tamper-evident history.
5. **Member directory** — roster, skills/availability, phone-bank, matrix presence.

Aesthetic split (unchanged): main `irl.coop` = fixaplan editorial (monochrome, dark hero,
light headlines); group templates = friendly / accessible / less-techy / earthy (warm
neutrals, organic shapes, soft shadows, generous whitespace).

## Component strategy

Build a small library of **reusable integration blocks** (identity header, chat embed,
NocoDB iframe, free/busy, proposals list) authored once as native instances, then composed
per vertical. Composition-not-inheritance: federated (group-of-groups) sites compose member
views (directory + aggregated resources) rather than inheriting a parent theme.

## Build order

1. Reference board: fixaplan.com (editorial) + 2–3 modern earthy/community examples as
   *technique* references (adopt layout/animation patterns, lift nothing).
2. The integration block library (identity header, chat, NocoDB iframe, placeholder
   calendar/treasury/voting) — the reusable core.
3. "Group home" as the first vertical (composes the library).
4. QA gate (from `resolver-v2-and-qa.md`) as a regression check before each publish.

## Open items

- Free/busy vs full-title calendar visibility (the privacy dial — `group-app-integrations.md`).
- Writes (treasury/voting) need a Bearer token surface on the published site — revisit when
  those apps exist.
- Whether the embed blocks ship as a first-party Webstudio component (needs a
  builder+publisher image rebuild) or as HtmlEmbed snippets (no rebuild, but copy-paste).
