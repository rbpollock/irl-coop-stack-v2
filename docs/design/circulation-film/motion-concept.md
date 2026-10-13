# The Motion as a Character — a cold restart on HOW the field moves

*Status: creative plan only. No build yet. Supersedes the force-directed and
orbit approaches for the field. Keeps the approved story beats, the centered
layout, and the 9:16 canvas.*
*Decision target: pick a direction (or combine the recommended arc with the
chosen "voice" per community) and then render once.*

---

## 1. The core argument

Every previous version animated **geometry**. Shells breathing, nodes orbiting,
members forced around — that's a field full of atoms that happen to move.
Nobody watches atoms and feels anything.

A community is not an atom. A community is a small, self-possessed, slightly
stubborn living thing that **looks at its neighbors**, **asks for help**, is
**really happy when the door opens**, and **rushes to help when a friend
fails**. The film's whole second half is literally about that: groups starting
to reach each other, work together, becoming reachable.

So the motion should be the story of a **relationship**: isolation → curiosity
→ reaching → giving → a whole network breathing on one tempo at the end.

That means motion is not a loop. It's a **single emotional trajectory** with a
few load-bearing moments:

1. **At first: every group is a busy little island.** Each one hums with its
   own quick, self-contained energy — comfortable, slightly separate. You
   feel "each group runs itself."
2. **The turn.** As the film says "variations alone … but no shared ground,"
   the groups **turn toward each other**. They can't reach yet — they can
   see and want to touch. A slow, almost hungry lean. Gaze, not contact.
3. **The first gift.** The moment "the shared interconnection layer" lands —
   something actually **crosses the gap**: a bright mote detaches from one
   group and travels across to another, and the receiver swells. This is the
   entire thesis in one beat: **help that was once impossible now crosses.**
4. **The lockstep.** In the climax ("each alone becomes reachable"), the
   whole network **breathes on one tempo** — all five groups' rhythms align
   into a single shared heart. Not union, not flattened: five distinct bodies
   moving in phase. This is "a global network of locally-governed
   communities."
5. **The ask.** The field goes **quiet and centered** — held still with
   presence, app with the two-beat, so the ask reads clean. (Some motion is
   fine, but it must not distract.)

Every frame should answer: *what are these people DOING right now?* If a
frame has movement with no agent, it's wrong.

## 2. Five "personalities" — one community, five characters

Rather than one uniform animation, give each of the five communities a
**behavior** so the audience can start to feel each one as someone:

| Community | Kind | Motion style | Why it reads that way |
|---|---|---|---|
| **C0** (civic/door-knock, biggest) | a big squarish crowd | **Energetic, jostling, noisy** — many small nodes with a fast little pulse, nodes occasionally swap places, the crowd keeps loosely reforming | 7 volunteer pods, busy, alive, slightly chaotic |
| **C1** (worker co-op) | a tight team around one hub | **Slow, heavy, coordinated** — a big center pulse; members turn with it, always near each other | steady, reliable, "we do this together" |
| **C2** (food hub) | hub + satellites | **Circulation**: nodes loop in a slow inward→outward flow, hub breathes, satellites orbit loosely | it distributes; it has a center that feeds the edges |
| **C3** (mutual-aid) | loose cloud, no hub | **Drift + exchange**: nodes wander separately, sometimes detach toward a neighbor, sometimes trade a small mote | federated, peer, “no ringleader, we trade” |
| **C4** (culture/arts, small) | a small pretty quartet | **Graceful rotation**: a slow, elegant fourfold turn — top/turn, delicate | small, unified, lovely |

Every community moves, but each moves **distinctly** — so the field is five
characters, not 31 dots.

## 3. The motion language (a small honest toolbox)

We do not need anything exotic. Three building blocks, each *tied to a
relationship*:

- **Look (Gaze).** A group gently "turns" so its densest part faces a
  neighbor or the center. Cheap, legible, and emotional. The community is
  **paying attention**.
- **Reach.** A single node — or the whole shell — spreads a silky tether
  toward another group, and it **stays connected** (a line now lives between
  them). Reach = "we want to meet."
- **Give (the mote).** One bright small dot **leaves** a group, travels along a
  reach line, and **arrives** at the neighbor — which pulses on receipt. This
  is "help now flows." It's the single most important motion in the film.

Phase and tempo do the emotional work. Early: each group's nodes spin on its
own **fast, independent** constant; as you approach the climax, the phases
**align**, and by "becoming reachable" all are in **unity-pulse.** A change
in coherence *is* the change in relationship.

## 4. The punch-in moment — the scene to nail

Block the film condensation to the message:

- **Reach** (the lean of curiosity):
  - During "each one alone," pick two groups-C0 (civic) and C1 (co-op) — or
    C2 food hub and C3 mutual-aid — that **turn toward each other** halfway
    through the film, slowly, uncrossable distance still between them.
- **Gift** (the mote), during **"the interconnection layer":
  - A bright node detaches from the sender, crosses the gap **in ~2s**, lands
    in the receiver, which flares. A soft glare travels along the tether.
  - The eye follows the give. That's the film's centerpiece.

The "becoming reachable" climax:
  - all five communities in **unison pulse**; the tether lines between them
    brighten; a second generation of motes **fans out** to all of them.

## 5. Determinism — no loss

Same rule as before: the motion is **precomputed** (scripted, seeded) and
played on the scrubbed GSAP timeline — Gated, tether, pulse, and mote all
author at definite times, no live sim. This keeps scrub-render exact and lets
us tune emotionally (not physically).

## 6. What this throws away (honest)

- The force-directed field is NOT a "background" anymore; it's the performer,
  so it cannot also be a neutral backdrop under the bring-in cards. The scrim
  and type grid stay, the field becomes the *character stage*.
- No more autonomous wobble-for-wobble. Spam the pulsing the whole time reads
  as noise. Motion mostly **happens with purpose**, and rests in **quiet
  attention** when it isn't the star. Sometimes the best "life" is a held
  calm with a tiny trace of breath — then the big moments hit.

## 7. The recommended build order

1. **Guard + Mote** first — this is the personality. One visible robust
   cross-network gift that lands and pulses a *receiving* group. If this
   doesn't feel warm, nothing else matters.
2. **The Unison-Pulse climax** (the finale at "becomes reachable") — the
   five-into-one heartbeat.
3. **Per-community voice** — brick the distinct C0..C4 motions **after** the
   climax/way works, so the field stays readable while we give each a life.
4. **The lean/second** moments on the earlier beats.
5. Render → watch → which moment lands, which is noise → iterate.

## 6. Open questions for Robbie

- **Tone** of the "quiet" parts: dead-calm (very restrained, warmth = rare,
  big contrast) versus always-alive (a constant low hum of motion, no real
  rest). My rec: *mostly quiet, big contrasts* — the film is about isolation
  being painful and connection being the release, so stillness should be felt
  as un-connectedness and the *gift/unison* as arrival.
- **Motes**: literal bright dots crossing between groups (clear "help
  traveling") vs soft light washes (more poetic, less literal). Rec: dots —
  honest, readable, matches the honesty baseline.
- How literal should the **gaze/lean** be? An entire group realigns (fem) vs
  a subtle shell orientation (more delicate). Rec: gentle but unmistakable —
  an entire group rocking its center toward a neighbor.