# Resolver v2 + built-in QA — feasibility

Status: design assessment. Date: 2026-08-28.

## What the current resolver does

`/tmp/css-resolver/resolve-many.mjs` turns an external template (static HTML, or a
rendered React/Tailwind block) into Webstudio JSX: it loads the page in a real
Chromium, walks the DOM collecting structural sections (`section/article/header/
footer/nav` + card grids), and for each element emits `<ws.element ws:style={css\`…\`}>`
with the element's `getComputedStyle` inlined. The CLI `insert-fragment` converts that
JSX into a native Webstudio instance tree.

## Why it plateaus at ~50% (diagnosed, not guessed)

The full visual QA (884 pages, deepseek-v4-flash-vision-exp verdicts) found the
hand-authored Co-op items 0% broken and the resolver-harvested items 20–93% broken.
Root cause is an **impedance mismatch**: Webstudio's data model is an *instance tree
with inline style tokens + breakpoints*; a template's source is a *stylesheet of CSS
rules resolved through the cascade*. Inlining `getComputedStyle` throws away:

1. **The cascade itself** — only the final computed value survives, so responsive
   behavior, `:hover`/`:focus`, media queries, and specificity are gone. Output is a
   frozen desktop snapshot.
2. **Background context** — a transparent `header`/`nav`/`footer` extracted alone
   loses the page's dark background it was designed to sit on (→ white-on-white
   "blank" sections). *Partially fixed: body-bg fallback when light text.*
3. **CSS variables / semantic tokens** — Flowbite's `bg-neutral-primary-soft` and
   `--color-*` tokens resolve to concrete colors only if the source CSS is loaded;
   when it isn't, components render transparent/invisible. SVG `<defs>`/icons are
   dropped (invalid as body children under Webstudio's HTML validator).
4. **Client-rendered content** — framer-motion `whileInView` count-ups/marquees
   hydrate empty at rest; SSR has the text but React replaces it on mount. Scroll-through
   recovers some; genuinely client-rendered blocks can't be captured without running JS.
5. **Layout capture** — flex/grid child sizing, absolute positioning, and width/height
   are re-derived from the rendered box (px), which overflows or collapses when the
   source used responsive units. *Partially fixed: max-width 100% + overflow-x hidden,
   flex/grid % recovery.*

## Feasibility of an improved resolver

Incremental improvements are cheap and additive, each buying a specific class of pages:

| Improvement | Buys back | Cost |
|---|---|---|
| Capture CSS custom properties (`--var`) + `:root` | semantic-token sources | low |
| Resolve at 3 breakpoints (375/768/1440) → emit Webstudio breakpoints | responsive fidelity | medium |
| Run page JS + wait for hydration before extraction | client-rendered blocks | medium |
| Detect repeatable sub-trees → emit as shared components | template reusability | medium |
| Preserve the source stylesheet + classes (instead of inlining) | cascade, hover, semantic tokens | **high** |

The last row is the real fix but it collides with the model: Webstudio instances don't
carry class names, so "preserve the stylesheet" means either a custom style-token
mapping layer or a fork of the builder to accept classed stylesheets. That is a
**builder fork**, not a resolver change.

**Verdict:** a "comprehensive" resolver can reach ~80% fidelity for simple,
layout-light sources by combining the first four improvements + the QA gate. It will
*not* reach 100% — that means reimplementing the browser's cascade. For high-fidelity
templates, the resolver is the wrong tool: build them **natively** (Webstudio's own
component system), which is the 0%-broken path (the Co-op items prove it).

## Built-in QA process (already built, needs formalizing)

The QA pipeline that found all of this is reusable and should be wired in as a **publish
gate** — nothing gets APPROVED that doesn't pass:

1. **Render the authored build** (`webstudio preview --source session --port <p>`), not
   the source — screenshots of the source show what *should* have happened, not what
   landed.
2. **DOM-metric gate** (objective, free): blank (no text/img/bg), horizontal overflow
   (`scrollWidth > viewport+2`), broken `<img>` (`naturalWidth===0`), zero-size elements.
   Catches blank/collapsed/overflow instantly.
3. **Vision gate** (subjective, ~4s/page): `deepseek-v4-flash-vision-exp` returns a
   `GOOD/MINOR/BROKEN/BLANK/MISSING_IMAGES` verdict per screenshot (downscale to 1024px
   JPEG; `max_tokens: 500` — it's a reasoning model and otherwise returns empty content).
4. **Auto-action:** pages below threshold get `marketplace.include=false` (or the item
   is dropped wholesale if >70% fail); only survivors publish.

All four steps exist as `/tmp/qa-*.py` / `/tmp/css-resolver/qa-*.mjs`. The remaining
work is packaging them into a single `qa-gate` command the authoring flow calls before
publish.

## Recommendation

- **Resolver v2:** pursue the cheap wins (breakpoint capture, CSS-variable capture,
  JS/hydration wait) + the QA gate, and *accept* ~80% as the import ceiling. Use it for
  "seed" material, not the finished product.
- **Quality path:** native templates (Track B) authored in Webstudio directly, with the
  QA gate as a regression check rather than a rescue.
- **Do not** attempt the stylesheet-preservation fork until native templates prove the
  demand for it — it is a large builder-fork effort with a high integration risk.
