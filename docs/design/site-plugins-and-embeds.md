# irl.coop on other people's platforms — plugins, widgets, and the connector

Status: design · 2026-10-04 · Robbie + Hermes.
Question: *can we make irl.coop plugins for Squarespace, Wix and WordPress that adapt coop features into
those webviews, using coop-api as the connector?*
Companions: `where-facts-live.md` (§4.1 the bar) · `scoped-availability.md` §3.1 (the anonymous
projection) · `declared-binding-registry.md` §R6 (markers) · `REALITY.md` (share links are relay tokens;
group subdomain `{slug}.irl.coop`) · the `irl-coop-wordpress-sites` skill.

## 0. The short answer

**Yes — with three different ceilings, and it is mostly *one* thing rather than three.** The platform
decides how *much* can be built; what may be built is the same everywhere.

## 1. What each platform actually allows

| Platform | What you can really build | Ceiling |
|---|---|---|
| **WordPress** | a **real plugin** — server-side PHP, secrets, inbound webhooks, shortcodes/blocks, wp-cli. **And it is already done here:** `joni-books` is a version-controlled plugin mounted read-only from the instance tree (`assets/wordpress/<name>` → `wp-content/plugins/`), so wp-admin cannot edit it away | **full** |
| **Wix** | **Velo** — their JS runtime with a *server-side backend*, a secrets store and HTTP functions, plus a real App Market. So a widget **with a server-side leg** | partial — real, but inside Wix's runtime |
| **Squarespace** | **no third-party plugin API at all.** Only **Code Injection / Code blocks** (Business plan+): you paste a `<script>` that mounts a widget. No server-side, no secrets, no inbound webhooks | **widget only** |

So: **one embeddable web component + a copy-paste script tag** is the surface all three can host — and it
is the same pattern as the existing `apps/webstudio/templates/world-doc-embed.html`, generalized to three
more hosts. WordPress then gets the *thicker* treatment because the platform permits it.

## 2. The framing that decides what it may do: it is a projection surface

Under `where-facts-live.md` a website integration holds **no authoritative facts**. It renders *kind 3*
(the disclosure dial, applied) and captures input. Concretely:

| Fact | Owner | On the site |
|---|---|---|
| membership | **ours** (kind 1) | a "join" button creates a **request**, never a seat — *signup ≠ membership*, the standing rule |
| visibility | **ours** (kind 3) | anonymous visitors get the **public projection** only; a member authenticates for more |
| money | **ours** (kind 6) | it shows state. It never takes a card on a group's marketing site |
| operational records | the app (kind 5) | not the website's business at all |

**This is the good news:** a thin widget cannot duplicate the coop's model, so it cannot become R-10 —
provided it stays a projection.

### 2.1 The five features, mapped

| Feature | What it is in this stack today | Status for a site widget |
|---|---|---|
| **Member login** | the fleet identity: `coop_session` (30d) + instant-code authorize; OIDC clients; the gates. The *one-cookie instant path* is still pending a fresh-session browser E2E | **buildable** — popup + short-lived in-memory token (§4.1). It is a **projection of kind 1**: the widget can show "your groups" and nothing more. **Login ≠ joining** (a join is a request) |
| **Comms — chat / meetings / feeds** | **all live**: Matrix (`matrix`/`element`/`call`/`cinny`/`livekit.irl.coop`, federation off); the appservice fans metadata into the bus; **`matrix-chat-gateway` mints a member's Matrix token server-side in coop-api**; LiveKit + `lk-jwt` for meetings; the notification feed (`irl:notify:{sub}`, digests via Temporal) | **the most live of the five.** A widget = mint a short-lived token server-side, then embed or link the room. **Never a token in the page** |
| **Events** | **Hi.Events is live** and already implements the exact split this needs: public events/checkout pages served directly, `/manage` + `/oauth2` through the coop gate | **pluggable now** — embed the public event page and RSVP. *Tickets* are the paid half (below) |
| **Bookings** | `caldiy-scheduling-and-paid-bookings.md` — the scheduler stays a **consumer**, availability is scoped (`scoped-availability.md`), and a booking is a **binding** | **buildable for free bookings** — the widget reads scoped availability (buckets by default) and writes a binding. The engine is headless behind coop-api, so the widget never talks to a scheduler directly |
| **Ecommerce** | the money path: `payment_intent` (**4 rows, all failed**), no route creates a payment, merchant account not live, the rail is internal-only, `PAYMENTS-SETUP.md`'s nine steps outstanding | **blocked only on the money leg — and the site is the wrong place to take the card.** A Wix/Squarespace storefront taking a group's money lands it in an individual's account: no threshold, off the books, outside the Safe — `money-in-and-out.md` §5.2 exactly. So the site does catalogue → cart → **checkout handoff** to the coop's own page; the widget's job ends at the handoff URL. **That work is unblocked by a stub rail** — `payment-stub-and-handoff.md` |

**The shape of it:** four of the five are *surface + capture + our projection*. Only ecommerce moves money —
it is the one blocked, and a third-party store makes it worse rather than better.

**And the good news in the bad news:** the paid halves of *three* features — event tickets, paid bookings,
the storefront — share **one** dependency, the coop's own payment path. They unlock together, so it is one
thing to finish rather than three.

Suggested order by value per unit of work: **login → feed → chat/meeting → events → free bookings →
money (when the coop path exists)**.

## 3. The bar applied to a site

| Requirement | For a site |
|---|---|
| **mapping** | a `resource_scopes` row per site: `app` = `wordpress` / `squarespace` / `wix`, `resource_key` = the domain or site id |
| **gate** | OIDC — but see §4: this is where the real constraint lives |
| **event leg** | **inverted.** Every other app *produces* events; a site **consumes** state. Its leg is a webhook (or a polled public projection) that re-renders the widget. Worth naming, because it is the mirror image |
| **marker** | **a DNS TXT record on the group's own domain** — reusing the mail pattern *exactly*: the site owner controls DNS, and the reconciler **enumerates DNS**, not the platform. A `<meta>` tag is the weaker fallback |
| **reconciler** | enumerate DNS for sites claiming a group; verify the injected embed still carries its group ref |

Plus one thing no other app needs: a **scoped, origin-bound, revocable embed token** for the public
projection — the same object as the docs **share links ("relay tokens")**, not a credential in a page.
Every privileged call stays server-side in coop-api; the page never holds a secret.

## 4. Constraints that usually kill these projects late

1. **Third-party cookies.** A widget inside an iframe on someone else's domain **cannot rely on a
   cross-site cookie** — Safari blocks it (ITP/CHIPS). So auth must be **popup + short-lived in-memory
   token**, or the widget links out to the group's own `{slug}.irl.coop`. Design for this from the first
   line, not after it fails in Safari.
2. **No secrets in the page.** Anything privileged is server-side; the page gets an embed token only.
3. **Payment.** Do not promise checkout on a Squarespace or Wix page. The money path is blocked anyway
   (`PAYMENTS-SETUP.md`), and a card form on a marketing site is the `money-in-and-out.md` §5.2 mistake
   wearing a different hat.
4. **Platform rules change.** Squarespace/Wix can alter injection and app policy. The widget must
   **degrade to a link**, and fail closed.
5. **Public site, public projection.** The visitor may be anonymous and the site is public — so a member
   view exists only after authentication, never by default.
6. **Live claims must be literally true.** The landing copy is aspirational by design; a widget showing
   *real* coop state is not — what it renders has to be true at the moment it renders.

## 5. What already exists — reuse, do not reinvent

- **The WordPress plugin recipe**, shipped and version-controlled: `assets/wordpress/<name>` mounted
  `:ro` into `wp-content/plugins/`, driven by `wp-cli` inside the container. `joni-books` is the
  precedent, and `assets/wordpress/README.md` records why it must be an ordinary plugin (mu-plugins
  cannot be installed without SFTP).
- **The embed template**: `apps/webstudio/templates/world-doc-embed.html`.
- **The token shape**: share links as relay tokens.
- **The group subdomain** `{slug}.irl.coop` — a **first-party** surface, where the cookie problem in §4.1
  does not exist at all.
- `group-app-projection` — how an app renders group state without owning it.

## 6. Sequencing — first-party before third-party

1. **The group's own `{slug}.irl.coop`** (or a Webstudio site) — first-party, no cookie constraint, and
   it proves the projection.
2. **The WordPress plugin** — the platform permits the most, and the recipe already exists.
3. **The embed widget** for Squarespace/Wix (and anything else) — the thin, universal surface.

Doing it in that order means the widget is a *port* of something already working, rather than a
quadruple build on three platforms whose rules we do not control.

## 7. Decisions

| # | Decision | Recommendation |
|---|---|---|
| 1 | Build the widget first, or the WordPress plugin? | **Widget-*after*-subdomain**: prove the projection on `{slug}.irl.coop` first (first-party), then WordPress, then the injected widget |
| 2 | Embed token — reuse the share-link relay token, or mint a new scoped one? | **Reuse the shape**; add origin allow-list + scope (group, views) + revocation |
| 3 | Marker for a site — DNS TXT, or a `<meta>` tag? | **DNS TXT** — it is enumerable by a reconciler, and it reuses the mail pattern |
| 4 | Does a "join" button ever create a seat? | **Never.** A request; membership stays in coop-api |

## Cross-references

- `where-facts-live.md` §4.1 — the bar; a site clears mapping/gate/marker/reconciler like any app.
- `scoped-availability.md` §3.1 — the anonymous projection the public widget must use.
- `declared-binding-registry.md` §R6 — the DNS marker, already proven by mail.
- `wordpress.yaml` + `assets/wordpress/README.md` — the plugin precedent, in the tree today.
- `REALITY.md` — share links as relay tokens; the group subdomain.
- `irl-coop-wordpress-sites` skill — the operational half, when this is built.