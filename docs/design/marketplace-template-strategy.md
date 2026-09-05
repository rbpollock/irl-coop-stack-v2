# Marketplace template strategy — sources, licensing, aesthetic

Status: **settled licensing gate + active source plan** (updated 2026-08-27)

## Licensing gate (settled, non-negotiable)

Only **MIT / CC-BY / original-own** sources. Two independent rules, and either
alone is disqualifying:

1. **The code must be permissively licensed** — a repo with *no* license is
   all-rights-reserved and cannot be copied, redistributed, or derived from,
   regardless of how "free" it looks on GitHub.
2. **The design must be original to the source** — MIT covers the *code*, not
   the *design*. A clone/tribute of a specific proprietary site (even one whose
   code is MIT) is a derivative of the original author's creative work, and
   reworking it does not make it ours ("derivative work" rule).

The boundary: **"modern, high-design" is fine; "clone of a named award-winning
site" is not.** TailGrids/Shadcn Space/shadcn-ui are original MIT designs;
`animated-thaiman-clone` (a thaiman.in reimagining, no license) is out — same
as Shadcn Studio (Commons Clause), Webflow, Mobbin, Framer, webstudio.is.

## Source inventory

| Source | License | Status |
|---|---|---|
| HTML5 UP | CC BY 3.0 | **done** — 44 templates, 10 section types + landing pages |
| Start Bootstrap | MIT | **done** — 25 themes |
| Flowbite | MIT | **done** — 42 components, 8 groups |
| TW Elements | MIT | **done (partial)** — 9 live-HTML blocks / 3 items |
| TailGrids | MIT | **planned** — step 3 of the "modern" thrust (React render) |
| Shadcn Space | MIT | **planned** — step 3 of the "modern" thrust (React render) |
| shadcn/ui blocks | MIT | **planned** |
| — *Awwwards-type clones* | — | **NO** (proprietary design, per gate above) |

Attribution: keep the license notice in the item `description`; de-brand
titles (no "HTML5 UP" / vendor prefix), but never strip the license line.

## The "modern Awwwards-style" thrust — BOTH tracks (2026-08-27)

The goal is award-adjacent, animated full-page templates, reached by two
complementary tracks:

### Track A — harvest original MIT sources
TailGrids + Shadcn Space + shadcn/ui blocks, run through the **React-render
pipeline** (render each template to HTML → `resolve-many.mjs` → screenshot →
author as a full-page "Landing pages"-style item). These give the *modern
visual language* (glassmorphism, gradient mesh, scroll-driven animation,
kinetic type) without cloning any named site.

### Track B — original coop-owned templates
Author our own "Awwwards-style" full-page templates from scratch — a
high-design storefront/landing language that is **ours**, not a tribute to a
brand. This is the long-term differentiator: a coop needs its *own* visual
identity, and original templates are clean of every licensing question by
construction.

## Aesthetic direction — two tiers (updated 2026-08-27)

- **Main irl.coop site** (the platform's own face): `fixaplan.com` editorial —
  monochrome, dark hero, big light headlines, magazine-like. Tools generalized
  (no vendor lock-in).
- **Group-created Webstudio templates** (what groups build on): **friendly,
  accessible, less techy, more earthy** — warm natural palette, organic shapes,
  approachable and inviting rather than startup-SaaS or dark dev-tool. Fits the
  cooperative/regenerative framing.
- Use-cases framed as **cooperative recipes/playbooks** rather than generic SaaS
  screens.

## Templates as seeds — verticals and federated (group-of-groups) sites (2026-08-27)

The interesting case: many *similar* groups each build a site from the same
template, and a *group of groups* (federation) builds a site that composes its
members. Two things become explicit:

1. **Template = seed, not cage.** A vertical template (food coop, housing coop,
   childcare, maker space…) is parameterized — group name, palette, content
   slots — and each group instantiates it with its own content. The template is
   the *seed* (initial values, never re-read), matching the group shape's
   "seed, not cage" rule. Templates are organized by vertical, framed as
   cooperative recipes/playbooks.
2. **Federation = composition, not inheritance.** A group-of-groups site does
   NOT inherit a parent theme — it *composes* member views: a member directory
   (each linking to the member's own site), aggregated resources, and a shared
   federation identity alongside per-member identity. This is
   "composition, not inheritance" made concrete at the site layer.

### Identity implication

A visitor to a federation site may be (a) a member of a child group, (b) a
member of the federation directly, or (c) a guest. The `GroupData` widget's RLS
scoping (`app.sub`) becomes hierarchical: a member-group member sees their
group's data on the federation site without seeing sibling groups' private
rows. Extends `group-scoping.md`'s hidden-norm tiers to a composed scope.

### Boundary (parked)

This is the *data/identity/template* model of federation. The **DNS + edge
takedown-resilience** federation architecture (decentralized routing, cert
resilience) is a separate, still-PARKED concern — not addressed here.

## Full-page template pipeline (how a "page" item is authored)

Same as the section pipeline, but the item is `category: pageTemplates` and each
page is one full template (one page = one insertable full-page layout). The
"Landing pages" items from HTML5 UP / Start Bootstrap are the proven pattern;
Track A reuses it against React-rendered sources, Track B authors it against
our own designs.
