# shadcn-mail skin

Roundcube skin that applies the irl.coop dashboard's Tailwind/shadcn design
tokens (`apps/web/irl-dashboard/src/app/globals.css`, the `:root`/`.dark` blocks)
onto the stock **Elastic** skin — additively, so Elastic stays the rollback target.

## What's in here

- `meta.json` — `"extends": "elastic"`; anything not present here falls back to Elastic.
- `styles/colors.less` — the token mapping (shadcn `hsl()` values → Elastic's `@color-*` vars).
  Elastic's derived `darken/lighten/tint` formulas are kept, so the whole palette
  recomputes from the tokens rather than being hand-repainted.
- `styles/brand.less` — the irl.coop brand layer: self-hosted **Lato** (the dashboard
  font) + a `.font-family()` mixin override that replaces Elastic's Roboto stack.
  Imported last in `styles.less` so LESS's last-definition-wins resolves the override.
- `styles/styles.min.css` + `embed.min.css` + `print.min.css` — compiled output; rebuild with `build.sh`.
- `images/logo.svg` — the "i" badge: a green rounded square (the `--success` / "regenerative"
  hue) with a white lowercase "i" — the compact form of the dashboard's "i + irl.coop" mark,
  sized for Roundcube's narrow taskbar logo slot.
- `fonts/` — self-hosted: Lato (400/700/900) + Elastic's FontAwesome icons + Roboto
  (kept for completeness). No external font CDN.

## Why two templates are copied from Elastic

Roundcube sets `$this->base_path` to the skin that **owns the currently-rendered
template**, and resolves skin-relative asset paths (`src="/…"`, `<link href="/styles/…">`)
against it. A `meta.json`-only child skin therefore resolves its assets to Elastic unless
it provides the templates that reference them:

- `templates/includes/layout.html` — the `<link href="/styles/styles.css">`; without this
  copy `styles.min.css` resolves to Elastic's.
- `templates/includes/menu.html` + `templates/login.html` — the `<roundcube:object
  name="logo" src="/images/logo.svg">`; without these the logo resolves to Elastic's mark.

These are verbatim copies (the logo stays an image asset; no markup rewrite), so Elastic's
JS-wired classes are untouched.

## Toggle / rollback

The skin is selected via `ROUNDCUBEMAIL_SKIN` in `infra/instances/dev/apps/roundcube.yaml`.
**Rollback = set it back to `elastic` + recreate the container.** Verified both directions;
Elastic is byte-identical upstream (never edited in place).

## Build

```
bash skins/shadcn-mail/build.sh   # recompiles the .min.css files (needs `less`, via npx)
```

The token source of truth is `apps/web/irl-dashboard/src/app/globals.css` — re-map in
`styles/colors.less` (colors) or `styles/brand.less` (font/brand), then re-run `build.sh`
and rebuild the `irlcoop/roundcube-oidc:1.6` image (`docker build -t
irlcoop/roundcube-oidc:1.6 infra/compose/communication/roundcube`).

## Test gate

`infra/scripts/journeys/journeys/roundcube-mail.mjs` is the shared gate (OAuth login →
list → compose → folder nav). It passes identically on `elastic` and `shadcn-mail`:
**34/34 checks, 2 skipped** (pre-existing NocoDB known bugs).
