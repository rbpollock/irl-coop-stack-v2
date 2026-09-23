"""irl.coop — V11 fear-loop diagram, REBUILT to tell a cohesive story.

Why the old version didn't work:
  - six nodes crammed into a circle at 8px text: a ring of buzzwords.
  - undirected edges looked like a decorative web, not a direction.
  - the caption ("break the loop at the cheapest link") never connected to WHY.

The redesign tells the story the source doc actually makes
(cost-model.data.json -> chilling_effect.the_loop) and now the VO says:

    cooperation costs too much
        -> groups stop writing things down
        -> nothing is provable
        -> no leverage
        -> fragility
        -> more fear        (and it tightens)

We keep the LOOP (the story is that it closes on itself) but draw it as
a staged cause-and-effect with clear direction and ONE emphasized break:
"nothing written down" is the single step a group controls (the cheapest
link) — everything else is just downstream of whether you wrote it down.

Drawn as a left-to-right chain that then arcs back (an actual loop), with
the break highlighted green, and a final caption that says the point in
plain words. Big 10pt+ text, roomy nodes, no clutter.
"""
import math
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pathlib import Path

OUT = Path(__file__).resolve().parent / "video" / "fear-loop-diagram.mp4"

BG = "#1C1C1C"
TEXT = "#E7E7EA"
DIM = "#9A9AA6"
LOOP = "#C17A5C"      # warm — the tightening loop
BREAK = "#4C8C4C"     # green — the break (we control it)
ACCENT = "#7C8CFF"


def ramp(v, a, b):
    return max(0.0, min(1.0, (v - a) / max(1, b - a)))


def main():
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7)

    # A LEFT-TO-RIGHT chain of five stages + a "loop back" arc.
    # Each (label, x, y) — spread wide so each gets room.
    stages = [
        ("cooperation\ncosts too much", 1.2, 3.3, False),
        ("groups stop\nwriting it down", 3.4, 3.3, True),   # the break
        ("nothing is\nprovable", 5.6, 3.3, False),
        ("no leverage,\nfragile", 7.8, 3.3, False),
        ("more fear", 10.0, 3.3, False),
    ]
    node_r = 1.05

    # draw nodes (patches) + labels (big, readable)
    circles, labels = [], []
    for (text, x, y, is_break) in stages:
        fc = "#2a2a30"
        ec = BREAK if is_break else TEXT
        lw = 2.0 if is_break else 1.4
        c = plt.Circle((x, y), node_r, fc=fc, ec=ec, lw=lw, alpha=0.0)
        ax.add_patch(c)
        circles.append(c)
        fs = 9.5
        labels.append(ax.text(x, y, text, color=TEXT, fontsize=fs,
                              ha="center", va="center", alpha=0.0))

    # directional arrows between consecutive stages (left->right)
    edges = []
    for i in range(len(stages) - 1):
        x1, y1 = stages[i][1], stages[i][2]
        x2, y2 = stages[i + 1][1], stages[i + 1][2]
        # shorten so the arrow starts/ends at circle edges
        theta = math.atan2(y2 - y1, x2 - x1)
        sx, sy = x1 + node_r * math.cos(theta), y1 + node_r * math.sin(theta)
        ex, ey = x2 - node_r * math.cos(theta), y2 - node_r * math.sin(theta)
        edges.append((ax.plot([], [], color=LOOP, lw=2.6, alpha=0.0,
                              solid_capstyle="round")[0], (sx, sy, ex, ey)))

    # the "loop back" arc from the last stage to the first, lighter
    back_arc = ax.plot([], [], color=LOOP, lw=1.8, ls="--", alpha=0.0)[0]
    back_end = ax.plot([], [], "o", color=LOOP, ms=6, alpha=0.0)[0]

    # break callout under node 1 (the one we control)
    break_lab = ax.text(3.4, 1.5, "WE BREAK IT HERE", color=BREAK,
                        fontsize=11, ha="center", fontweight="bold", alpha=0.0)
    break_sub = ax.text(3.4, 0.55, "the cheapest link, and the only one\nwe can touch — write it down",
                        color=DIM, fontsize=9, ha="center", alpha=0.0)

    # title + caption (the point, in plain words)
    ax.text(6.5, 6.6, "the cost of coordination, drawn as a loop", color=ACCENT,
            fontsize=13, ha="center", fontweight="bold", alpha=0.0)
    ax.text(6.5, 0.1,
            "expensive cooperation → groups stay silent → nothing provable → fragile → more fear →",
            color=DIM, fontsize=10, ha="center", alpha=0.0)
    ax.text(6.5, 6.35, "(and the loop holds until someone writes it down)", color=DIM,
            fontsize=9, ha="center", alpha=0.0)

    src = ax.text(0.3, 0.05, "irl.coop — the fear loop (V11) · source: chilling_effect.the_loop",
                  color=DIM, fontsize=8.5, ha="left", va="bottom", alpha=0.0)

    TOTAL, FPS = 200, 24

    def update(f):
        # 1) nodes fade in L→R
        for i, c in enumerate(circles):
            c.set_alpha(ramp(f, 10 + i * 8, 18 + i * 8))
        for i, lab in enumerate(labels):
            lab.set_alpha(ramp(f, 10 + i * 8, 18 + i * 8))
        # 2) edges left→right
        for i, (ln, geo) in enumerate(edges):
            seg = ramp(f, 60 + i * 8, 76 + i * 8)
            sx, sy, ex, ey = geo
            ln.set_data([sx, sx + (ex - sx) * seg], [sy, sy + (ey - sy) * seg])
            ln.set_alpha(ramp(f, 55, 70))
        # 3) break callout on node 2 (we control it)
        break_lab.set_alpha(ramp(f, 116, 130))
        break_sub.set_alpha(ramp(f, 124, 138))
        # 4) back arc (last -> first) once the chain is drawn
        ba = ramp(f, 135, 158)
        if ba > 0:
            x0, y0 = 10.0, 3.3
            x1, y1 = 1.2, 3.3
            n = 28
            xs = [x0 + (x1 - x0) * (t / n) for t in range(n)]
            ys = [y0 + (y1 - y0) * (t / n) + 1.9 * math.sin(math.pi * t / n) for t in range(n)]
            k = int(ba * n)
            back_arc.set_data(xs[: k + 1], ys[: k + 1])
            back_arc.set_alpha(ramp(f, 135, 150))
        # 5) footer + source
        src.set_alpha(ramp(f, 172, 188))
        return list(circles) + labels + [e[0] for e in edges] + [back_arc, break_lab, break_sub, src]

    anim = animation.FuncAnimation(fig, update, frames=TOTAL, interval=1000 / FPS, blit=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    anim.save(str(OUT), writer=animation.FFMpegWriter(fps=FPS, bitrate=2400))
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    main()