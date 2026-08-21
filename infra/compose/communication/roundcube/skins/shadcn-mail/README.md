# shadcn-mail skin

Roundcube skin that applies the irl.coop dashboard's Tailwind/shadcn design
tokens (`apps/web/irl-dashboard/src/app/globals.css`, the `:root`/`.dark` blocks)
onto the stock **Elastic** skin — additively, so Elastic stays the rollback target.

- `meta.json` — `"extends": "elastic"`; templates/JS/images fall back to Elastic.
- `styles/colors.less` — the token mapping (shadcn `hsl()` values → Elastic's `@color-*` vars).
- `styles/styles.min.css` + `embed.min.css` + `print.min.css` — compiled output; rebuild with `build.sh`.
- `templates/includes/layout.html` — copied from Elastic so the skin's CSS `<link>`
  resolves against **this** skin. Roundcube sets `base_path` to the skin that owns the
  current template; without this copy, `styles.min.css` resolves to Elastic's (the
  `<link href="/styles/styles.css">` lives in Elastic's `layout.html`).

## Toggle / rollback

The skin is selected via `ROUNDCUBEMAIL_SKIN` in `infra/instances/dev/apps/roundcube.yaml`.
**Rollback = set it back to `elastic` + recreate the container.** Verified both directions.

## Build

```
bash skins/shadcn-mail/build.sh   # recompiles the .min.css files (needs `less`, via npx)
```

The `colors.less` source of truth is `apps/web/irl-dashboard/src/app/globals.css` — re-map
there, then re-run `build.sh` and rebuild the `irlcoop/roundcube-oidc:1.6` image.
