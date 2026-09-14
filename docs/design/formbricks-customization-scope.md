# Formbricks customization scope — how deep does an irl.coop skin go?

Status: scope/spike · Sep 2026 · Author: Robbie + Hermes.
Question answered: *how much of Formbricks can be made to look like irl.coop, and
what does each change cost?* (Pinned version: formbricks 5.4.0, commit
`286958e36464663489bfbc73d87abbd0f573825f`, image `irlcoop/formbricks-gate-sso:5.4.0`.)

## 0. TL;DR — three levers, cheapest first

| Lever | What it reaches | Cost | Rebuild? |
|---|---|---|---|
| **A. Styling tokens** (no code) | surveys + workspace defaults: colors, fonts, radii, buttons, inputs, progress, cards, dark mode, background, logo, card arrangement/width | minutes, data-only | **no** |
| **A2. Per-survey CSS + copy** (no code) | arbitrary CSS via `Survey.customHeadScripts`; all strings via locale override | minutes, data-only | **no** |
| **B. Light AGPL patch** (our fork) | the app chrome: login page, dashboard shell/header/sidebar, footer + CTA link, brand assets, emails | 1 patch + ~20–40 min image build | yes |
| **C. Structural fork** | routes, layouts, brand-new modules | weeks; diverges per upgrade | yes (painful) |

Recommendation: exhaust **A/A2** first (that's most of the visible surface for members
answering surveys), use **B** only for the chrome members see when they're *inside*
Formbricks, and avoid **C** in v1.

## 1. Lever A — the styling token set (no code)

Stored as JSON, workspace-wide defaults + per-survey overrides:

- `Workspace.styling` (jsonb) — the group's default survey look
- `Survey.styling` (jsonb) — per-survey override (`overwriteThemeStyling`)
- `Workspace.logo` (jsonb: `{url, bgColor}`), plus `Workspace.config`

The token schema (`packages/types/styling.ts`, `ZBaseStyling` + `ZSurveyStyling`)
covers ~45 knobs:

- **Colors (each light/dark):** `brandColor`, `accentBgColor`, `accentBgColorSelected`,
  `footerLinkColor`, `buttonBgColor`, `buttonTextColor`, `inputBgColor`,
  `inputBorderColor`, `inputTextColor`, `optionBgColor`, `optionLabelColor`,
  `optionBorderColor`, `elementHeadlineColor`, `elementDescriptionColor`,
  `elementUpperLabelColor`, `progressTrackBgColor`, `progressIndicatorBgColor`,
  `cardBackgroundColor`, `cardBorderColor`, `highlightBorderColor`
- **Type:** `fontFamily`, `elementHeadlineFontSize/Weight`,
  `elementDescriptionFontSize/Weight`, `elementUpperLabelFontSize/Weight`,
  `buttonFontSize/Weight`, `inputFontSize`, `optionFontSize`
- **Shape & size:** `roundness`, `buttonBorderRadius`, `inputBorderRadius`,
  `optionBorderRadius`, `buttonHeight`, `buttonPaddingX/Y`, `inputHeight`,
  `inputPaddingX/Y`, `inputShadow`, `optionPaddingX/Y`
- **Layout:** `cardArrangement` (link: `casual|straight|simple|cardless`),
  `cardWidth` (`narrow|default|wide`), `progressTrackHeight`, `isDarkModeEnabled`
- **Background:** `background {bg, bgType: animation|color|image|upload, brightness}`
- **Logo:** `logo {url, bgColor}` (workspace-level)

**A2 — the open-ended bit:** `Survey.customHeadScripts` + `customHeadScriptsMode`
lets a survey inject its own CSS/JS on the survey page (community feature). That is
the escape hatch for anything the token set can't express (custom webfont loading,
signature flourishes, irl.coop-specific components) **without forking**.

## 2. Lever B — the light AGPL patch (our fork)

Files we may touch (AGPL, community tree) and what each buys:

| Surface | File (5.4.0) | Buys |
|---|---|---|
| Login page | `apps/web/app/auth/login/**` | "Sign in to irl.coop", warm bg, no Formbricks wordmark |
| Post-survey CTA | `apps/web/modules/survey/link/components/survey-completed-message.tsx` | repoint `formbricks.com?utm…survey_completed` → `irl.coop/signup?intent=formbricks` |
| "Powered by" signature | `packages/surveys/src/components/general/formbricks-branding.tsx` | repoint link (keep the words — see §4) |
| Dashboard chrome | `apps/web/app/(app)/**`, `modules/workspace/**` shell, sidebar/header | coop nav, workspace switcher copy, warm palette |
| App-wide CSS | `apps/web/globals.css` / tailwind theme | irl.coop tokens for the admin UI |
| Brand assets | `apps/web/public/**` (favicon, share images) | irl.coop marks |
| Emails | `apps/web/modules/email/**` | coop voice, no Formbricks marketing |

Cost: one patch (`infra/build/images/formbricks/irlcoop-fork.patch`, same mechanism as
gate-SSO) + a 20–40 min image rebuild + container recreate. No upgrade-divergence risk
beyond the existing patch: these are leaf components, not architecture.

## 3. Lever C — structural fork (avoid in v1)

Layout/routing restructures, new nav models, replacing module architecture. Each
upstream bump re-breaks it, and it buys little: members' *survey* experience (the
part the coops' respondents see) is fully Lever A.

## 4. The EE boundary (do not cross without a licence)

`linkSurveyBranding` / `inAppSurveyBranding` (workspace booleans, both currently
`true`) control *showing/hiding* the signature — that toggle and the white-label
feature are `apps/web/modules/ee/whitelabel/remove-branding/**`, under the
Formbricks EE licence (production needs a paid seat). Rule: **repoint, don't hide**;
never patch `ee/license-check` to un-gate. Implementing our own equivalent is
allowed clean-room — see the `formbricks-gate-sso` skill reference for the rule and
the AGPL §13 source-offer obligation that rides every patch.

## 5. Worked example — irl.coop tokens onto the knobs

From the onboarding design system (`docs/design/onboarding-flow.md` §visual system):

| irl.coop token | Formbricks knob | Value |
|---|---|---|
| primary purple | `brandColor.light` | `#7C3AED` |
| ink / headings | `elementHeadlineColor.light` | `#4C1D95` |
| muted body | `elementDescriptionColor.light` | `#475569` |
| warm background | `background.bg` + `bgType: color` | `#FAF5FF` |
| card | `cardBackgroundColor.light` / `cardBorderColor.light` | `#FFFFFF` / `#E9D5FF` |
| display serif | `fontFamily` | `"Cormorant Garamond", Georgia, serif` |
| humanist sans (body/UI) | app CSS (Lever B) | system humanist stack |
| join-green / success | `progressIndicatorBgColor.light` | `#16A34A` |
| generous radii | `roundness`, `buttonBorderRadius`, `cardBorderRadius` | `12–16px` |
| airy layout | `cardWidth` + `cardArrangement` | `default` + `straight` |

## 6b. Test results — tokens applied live (Sep 2026)

Applied §5 to both workspaces (`Workspace.styling`) and to the scratch survey
`My workspace's Rating Survey` (`Survey.styling` + `overwriteThemeStyling: true`),
then screenshotted `https://surveys.irl.coop/s/<survey-id>` in the browser-runner.

**Verified applied** — live A/B on `https://surveys.irl.coop/s/<survey-id>`
(computed styles read off the page; before = stock, after = tokens):

| | stock | irl.coop tokens |
|---|---|---|
| button background | `rgb(30,64,175)` (Formbricks blue) | **`rgb(124,58,237)`** (#7C3AED) |
| button radius | `8px` | **`12px`** |
| survey text | `rgb(20,42,114)` | **`rgb(76,29,149)`** (#4C1D95) |
| font | Inter | Inter *(unchanged — see below)* |

**Workspace defaults are the lever that matters:** with tokens on
`Workspace.styling`, *every* survey in that workspace renders skinned with no
per-survey work; the per-survey `Survey.styling` (+`overwriteThemeStyling`) is the
override. Reverting only the survey still showed the full skin — the workspace
default was doing the work.

**Finding — `fontFamily` does nothing in 5.4.0.** `packages/surveys/src/lib/styles.ts`
maps ~45 tokens to `--fb-*` CSS variables but has **no `fontFamily` mapping**, so the
schema field is inert for the renderer. Consequence: lever A alone yields *Formbricks
in irl.coop colours*, not *irl.coop typography*. Fonts therefore need:

- **A2 (`Survey.customHeadScripts`)** — inject `@font-face` + a CSS rule that targets
  the survey content classes, self-hosted from MinIO `public-assets`; or
- **B** — set the app/survey font in the fork's CSS.

Also: the public survey link resolves by **survey id** (`/s/<id>`; lookup is
`where: { id: surveyId }` in `modules/survey/link/lib/data.ts`), not by slug — the
`slug` column only feeds nicer display URLs.

Revert: `update "Survey" set styling = null where id = …; update "Workspace" set styling =
'{"allowStyleOverwrite": true}'::jsonb;` (and clear `slug` to unpublish).

## 6c. A2 test — the serif, with no rebuild (Sep 2026)

Result: **typography is achievable data-only.** Injected via
`Workspace.customHeadScripts` (workspace-level scripts apply to *every* link
survey in that workspace — `docs/surveys/link-surveys/custom-head-scripts.mdx`;
also available per-survey with `customHeadScriptsMode: add|replace`).

What we did:
1. Fetched **Cormorant Garamond 600** (latin subset, SIL OFL-1.1 — self-hosting
   permitted) from Google Fonts and uploaded it to our own bucket:
   `https://s3api.irl.coop/public-assets/fonts/cormorant-garamond-600-latin.woff2`
   (anonymous read; no third-party CDN at runtime).
2. Put a `<style>` block in `Workspace.customHeadScripts`: an `@font-face` for that
   URL plus `h1,h2,h3,h4,[class*=headline] { font-family: "Cormorant Garamond"… !important }`.

Verified on the live survey page (computed styles): `headlineFont` =
`"Cormorant Garamond", Georgia, …`, `document.fonts` contains the family
(`fontLoaded: true`), tokens unchanged (`rgb(124,58,237)` button, `#4C1D95` text).
Options/buttons keep the sans UI face — i.e. serif display + sans UI, the irl.coop split.

Limits to remember: custom head scripts are **link surveys on self-hosted only**
(not app/website surveys, not Formbricks Cloud) — irrelevant here since all our
surveys are link surveys on our own instance.

Revert: `update "Workspace" set "customHeadScripts" = null where name in (…);`

## 6d. Lever B shipped — `irlcoop/formbricks-gate-sso:5.4.0-irl.1` (Sep 2026)

Built and live. Patch: `infra/build/images/formbricks/irlcoop-chrome.patch`
(applied by `build.sh` after the gate-SSO patch; both verified to apply cleanly
against pin `286958e3…`). What it changes:

| File | Change |
|---|---|
| `apps/web/lib/brand-color.ts` | `DEFAULT_BRAND_COLOR` `#1e40af` → `#7C3AED` (this is the stock blue that showed up as the default survey button) |
| `apps/web/modules/ui/globals.css` | `--color-brand*` + `--formbricks-brand` (both themes) → purple family |
| `modules/ui/components/{formbricks-logo,logo}` | teal gradient stops → purple family (`#8B5CF6`/`#A78BFA`) |
| `modules/auth/{login,signup}/page.tsx` | background `#D9F6F4` → `#FAF5FF`; login title/description → irl.coop copy |
| `modules/survey/link/components/survey-completed-message.tsx` | "create your own survey" CTA → `https://irl.coop/signup?intent=formbricks` |
| `packages/surveys/…/formbricks-branding.tsx` | "Powered by Formbricks" → `https://irl.coop` (words kept — attribution stays) |

**Verified after recreate** (container healthy in ~10s):
- CSS vars in the live app: `--color-brand: #7c3aed`, `--formbricks-brand: #7c3aed`; **0** teal hexes left on the page.
- Login page HTML: `#7C3AED` ×8 + `#A78BFA` ×3 in the logo, `#00C4B8/#01E0C6/#00DDD0/#038178` = **0**, copy "Sign in to irl.coop".
- Public survey: `brandLinks: ["https://irl.coop/"]` (attribution link repointed), tokens + self-hosted serif still intact.
- Route gotcha: the app home is **`/workspaces`** in 5.4.0 (the old `/environments` 404s) — auth-protected routes moved.

Rebuild: `bash infra/build/images/formbricks/build.sh` → then
`docker compose -f infra/out/dev/compose/workflow/docker-compose.yml -f …override.yml up -d --force-recreate formbricks`.

Not done (deliberately): the Formbricks wordmark **image** on the survey-completed
panel (`apps/web/modules/survey/link/lib/footerlogo.svg`) keeps its own brand colours
— that is the attribution, and recolouring/hiding it is the EE white-label feature
(§4). Next step if wanted: set the §5 tokens + §6c font script **automatically at
workspace creation** (in the gate-SSO `provisionGroups` path) so every coop group's
workspace is born irl.coop-styled instead of needing a manual apply.

## 6e. Auto-skin at provisioning — shipped & verified (Sep 2026)

Image **`irlcoop/formbricks-gate-sso:5.4.0-irl.3`**. The skin is now applied by the
gate-SSO provisioning loop itself, so no manual SQL is needed per group:

- new module `apps/web/lib/irlcoop-skin.ts` (our file) holds the §5 tokens +
  the §6c font `<style>`; font URL overridable via `IRLCOOP_FONT_URL`.
- `prisma.workspace.upsert` **creates** workspaces with `styling` +
  `customHeadScripts`, and a pre-existing workspace converges on next login when its
  styling is still the app's pristine default (`{allowStyleOverwrite}` only — no
  `brandColor`) or its head scripts are null. An admin's own styling is never
  overwritten.

**Verification (real login, not a simulation):** reset `Cold Storage Co-op`
(`{"allowStyleOverwrite": true}` + null head) → sign in as e2e-test through
`forms.irl.coop` (gate → gate-SSO → provisioning) → re-query: styling
`{"light": "#7C3AED"}`, head scripts present (407 chars, `@font-face` → our MinIO URL).
`My workspace` (already skinned) was untouched.

**Two build lessons (cost two image builds, worth knowing):**
1. `Workspace.styling` is **NOT NULL** in the schema — "unskinned" is the pristine
   default object, not `null`. Detect by keys, never by null.
2. Next's build **type-check rejects** annotating a plain literal as
   `Prisma.InputJsonObject` in a lib module; export a plain literal and cast at the
   Prisma call sites (`as Prisma.InputJsonValue`). Also: never pipe the image build to
   `tail` — it hides the type error and wastes a cycle (log to a file instead).

## 7. Open decisions / next test

0. **LATER (queued by Robbie, Sep 2026): mint a workspace-scoped Formbricks API key into
   the Tier-2 vault** as `formbricks.api_key`, referenced as `${VAULT:formbricks.api_key}`,
   for the Temporal integration (the Formbricks worker will need it to create/sync
   surveys). It is an *external* secret — Formbricks issues it, so it cannot be derived
   from `master.key`; the vault is its documented home. Create it with scope =
   exactly one workspace (v1 rejects org-level keys), and call it at the app address
   (`http://127.0.0.1:3008` host-side / `http://formbricks:3000` in-network) — never
   `forms.` (SSO gate) or `surveys.` (management API 404s).

1. Apply §5 as the **workspace default** on the two existing workspaces
   (`My workspace`, `Cold Storage Co-op`) and to a scratch survey — then screenshot
   the public survey page (`surveys.irl.coop/s/<slug>`) as the Lever-A proof.
2. Decide whether Lever B v1 = login page + footer/CTA only (small, high-signal) or
   the full chrome (login + dashboard + emails).
3. Fonts: self-host Cormorant Garamond + humanist sans through our own MinIO
   `public-assets` bucket (no third-party font CDN) — same pattern as the aronia crop
   image; `customHeadScripts` can `@font-face` it per survey.
4. i18n: decide whether to override strings via locale (fast, keeps upstream files)
   or patch copy in components (slower, more control).
