# Track B template reference — thaiman-clone anatomy (2026-08-27)

Audit of `AnuragaMuruganathan/animated-thaiman-clone` (no license file; README
admits "inspired by thaiman.in"). Finding: the repo cleanly separates a
**generic animation engine + section patterns** from **thaiman-specific
content**. Use the former as a technique reference for the original coop
templates (Track B); do NOT copy the latter.

## What's generic — adopt as technique reference

- **Animation engine** — `animations/` (eases.js, gsap.js, presets.js,
  variants.js), `effects/` (Magnetic, Tilt + glare, useRipple),
  `transitions/` (Appear, motionPresets), `hooks/` (useDrawSVG,
  useGsapContext, useParallax, useScrollReveal, useMousePosition,
  useMediaQuery). None of these reference the brand — they are uncopyrightable
  methods ("stuff found everywhere"). Re-implement freely.
- **Section patterns** — table below. Every one is a stock layout/animation
  pattern (pinned scroll storytelling, infinite marquee, filterable masonry,
  glassmorphism newsletter, 3D-tilt cards, split-text hero).

## What's thaiman-specific — do NOT copy

- `data/content.js` — the entire brand layer: name "Thaiman", wordmark, motto,
  phone/email/Vellore address, the Tamil+English product catalog with INR
  prices, testimonials (real names + cities), recipes, gallery place names,
  farm-journey steps, announcements. This is the actual thaiman.in content.
- **Section order** — `Home.jsx` explicitly mirrors thaiman.in's narrative
  order (hero → categories → popular → seeds → story → homemade → nutrition →
  footer).
- **Palette tokens** — `leaf-dark`/`leaf`/`honey`/`cream`/`charcoal` (earthy
  farm). Generic enough as an idea, but rebuild as our own earthy tokens.

## Section → pattern map

| Section | Generic pattern to build | Note |
|---|---|---|
| HeroSlider | full-bleed 3D hero (Three.js) + rotating slides + split-text + magnetic CTAs + scroll indicator | our 3D subject = coop/community, not honey jars |
| TrustBar | 4-icon USP strip | |
| CategoryStrip | shop-by-category tiles (emoji + gradient) | |
| PopularProducts | tabbed product grid + 3D tilt/glare cards + magnetic add-to-cart | |
| SeedsShowcase | feature highlight + count-up stat + combo cards | |
| FarmJourney | pinned scroll storytelling + self-drawing SVG rail + numbered steps + active counter | flagship pattern |
| BrandStory | 3 pillar cards | |
| HomemadeProducts | product grid | |
| TraditionalNutrition | nutrition CTA | |
| Gallery | filterable masonry + lightbox | |
| Recipes | recipe cards | |
| Testimonials | brand-word marquee + dual opposing review marquees + parallax blobs | |
| Newsletter | glassmorphism + validation shake + success morph | |
| Footer | animated wave + floating shapes | |

## For Track B

Rebuild the generic patterns above as original coop templates with: our own
**earthy/friendly** palette (warm natural tones, organic shapes), coop content
(recipes/playbooks framing), and no brand-specific copy. The animation engine
is a pure technique reference — re-implement, don't lift.
