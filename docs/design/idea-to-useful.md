# From an idea to something useful — the missing first flow

Status: gap analysis · 2026-09-13 · Robbie + Hermes.
**Robbie's observation: "it's weird to do a probe without these mechanisms/UX in place." Correct, and
it reorders the probe.**

## 0. The gap, stated plainly

**The founding-group journey is designed and its pivot is unbuilt.** `onboarding-flow.md` (Aug 2026)
specifies seven steps — Arrive → You → The idea → **Vertical pick** → **First shape** → Warm questions
→ Consent → Land — with Step 3→4 as the hinge:

> Step 3: *choose what you want to do first* → "seeds an intent → the shape picker filters to it"
> Step 4: *pick a blueprint + name + slug* → group Safe deploy → subdomain + mail domain + Matrix space

That hinge — **"I have an idea" → "here is my group, with the right tools already on"** — is exactly
the mechanism in question, and it exists as prose only. Probing the journey now would produce findings
about the *document*, not the product.

## 1. What already exists (so this is smaller than it looks)

| Piece | State |
|---|---|
| The 7-step flow, copy and all | **Designed** — `onboarding-flow.md` + `onboarding-prototype.html`. Principle 6 is the right one: *"every screen ends with a next step… onboarding never dead-ends in a profile"* |
| Group creation | **Live** — `POST /api/v1/groups`, `GET /api/v1/slugs/:slug/available`, `POST /api/safe/predict` + `/api/safe/deploy` |
| Invite-on-first-signin, per-group Matrix room, resource provisioning | **Live** (`groups.ts`, `provisioning.ts`, `irl-coop-group.md`) |
| **A blueprint catalogue, already written** | The landing page's **11 recipes each declare their tool set** (`tools: ["Project management", "Visual database", "Storage"]`) — that *is* the `apps` axis of a shape, in embryonic form. Plus 17 app cards each with "in a group / groups of groups" behaviour |
| **A proven template pattern in this codebase** | `telephony_templates` (`db.ts:227`): a platform catalog of reusable templates + **per-group instances referencing `template_id`**. That is the exact form a group-blueprint catalog wants — the precedent exists, applied to phone numbers rather than to groups |

## 2. What is missing — the pivot

- **No group shape / blueprint mechanism in `coop-api`.** Searching `apps/coop-api/src` for
  `shape|template|blueprint|recipe|starter` returns only **OOXML document templates** and
  **telephony templates**. Nothing group-level.
- **No path from a recipe to a group.** The recipes declare `tools: [...]`; nothing consumes it. The
  landing page is already a blueprint browser that cannot create anything.
- So Step 3→4 of the flow has no implementation, and **there is no "first useful thing"** defined after
  group creation — the screen after creation is the thing that decides whether a new person's first ten
  minutes produced anything.

## 3. A separate first-30-seconds bug, independent of all of it

The landing page's primary CTA is **"Join the coop"** ("Join in under a minute"), while its own FAQ
says:

> *"Can I just start a group, or do I have to join the coop first?"* → **"Just start. Sign up and your
> group is yours from day one. Joining the coop is optional."**

**The button asks for an organisational commitment; the FAQ promises none is needed.** For a person
with an idea the primary action should be **"Start a group"**, with joining the coop as a later,
deliberate step — which is also what `signup ≠ membership` means, and what the CTA ladder in
`interactive-arguments-and-the-cta.md` §2 already implies. Cheap to fix, and it is the literal
"how does a person with an idea start" question.

## 4. The design question worth deciding (a question, not a verdict)

**`onboarding-flow.md` front-loads the teaching.** Seven screens precede the payoff: arrive, you, the
one idea, vertical, shape, warm questions, consent. Principle 1 says *teach the one idea*; principle 6
says *never dead-end*. Those are in tension for someone who arrived **already holding an idea** — they
want the thing, and the concepts are easier to absorb *inside* a real group, because you can point at
the actual object instead of describing it.

**Proposal (for Robbie to accept or reject): invert it.** Shape first, with a smart default, then teach
in context inside the working group. The teaching content in `onboarding-flow.md` §3 is good — it does
not all need to *precede* the group existing.

`onboarding-flow.md` is a settled doc, so this is a question. It should not be rewritten on the
strength of this note.

## 5. The minimal flow that makes "useful" true

| # | Step | Depends on |
|---|---|---|
| 1 | **Idea → closest recipe/shape (or blank)** — the 11 recipes on the landing page already are the catalogue | a blueprint catalog (§2) |
| 2 | **Name + slug** | ✅ live (`slugs/:slug/available`) |
| 3 | **Group created with the shape's apps on, roles seeded, 1-of-1 control** | creation ✅ live; **the prefill from a shape is the missing piece** |
| 4 | **First useful artifact** — the design's own rule is never dead-end. Candidates that work today: *post a need or offer* (needs-offers is functional, client-side) or *create an event* (live). Pick one and make it the landing state | a decision, not a build |
| 5 | **Invite the first people** | ✅ designed (invite-on-first-signin) |
| 6 | **Only then: coop membership** — the Safe threshold upgrade from 1-of-1 | `irl-coop-group.md`, and item 2 of `coop-launch-and-roadmap-handoff.md` |

## 6. What this changes about the probe

- **Pass 0 is unaffected.** Read-only infrastructure checks test nothing about UX — build it whenever.
- **Pass 1 must wait for the flow.** Steps 3–5 above are what its scripts would exercise; testing them
  before they exist measures the design doc.
- **Order: flow first, then pass 1.** And pass 1 gets easier for it — §5 becomes the script.
- **This shrinks the scary surface.** The flow is designable and buildable without touching the vault,
  the federation, the group modes or the treasury — the parts that carry the risk.

## 7. Do not

- Do not build a blueprint catalog before the shape axes are settled
  (`event-bus-and-group-shapes.md` §3 — roles / apps / config / governance / proofs). The
  `telephony_templates` precedent gives the *form*; the *content* is a governance decision.
- Do not rewrite `onboarding-flow.md` on the strength of §4.
- Do not script probe pass 1 against a flow that only exists on paper.
