"""irl.coop — V6 value-flow diagram (a co-op vs a platform, where value goes).

CONCEPTUAL diagram, not data-driven. It answers "where does the value go?":
  LEFT  — a co-op: members → dues → treasury → node+steward → back to members.
          A LOOP: value returns to the people who produced it.
  RIGHT  — a platform: members → subscriptions → vendor → shareholders.
          A LINE: value exits to shareholders.

This is the V6 motion graphic. Rendered with matplotlib.animation (no cairo /
pango / TeX), fully scripted, dark palette.

Render:
    uv run --with matplotlib python docs/design/value-flow-diagram.py

Output: docs/design/video/value-flow-diagram.mp4
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pathlib import Path

OUT = Path(__file__).resolve().parent / "video" / "value-flow-diagram.mp4"

BG = "#1C1C1C"
TEXT = "#E7E7EA"
DIM = "#9A9AA6"
ACCENT = "#7C8CFF"
LOOP = "#4C8C4C"    # green — value that returns
LEAVE = "#C98A6A"   # orange — value that leaves


def ramp(v, a, b):
    return max(0.0, min(1.0, (v - a) / max(1, b - a)))


def box(ax, x, y, w, h, fc):
    return ax.add_patch(plt.Rectangle((x - w / 2, y - h / 2), w, h, fc=fc, ec=TEXT, lw=1.2, alpha=0.0))


def main():
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)

    # ---- panel headers
    ax.text(25, 57.5, "A CO-OP", color=TEXT, fontsize=16, ha="center", fontweight="bold")
    ax.text(25, 54.5, "value CIRCULATES", color=LOOP, fontsize=11, ha="center")
    ax.text(74, 57.5, "A PLATFORM", color=TEXT, fontsize=16, ha="center", fontweight="bold")
    ax.text(74, 54.5, "value EXITS", color=LEAVE, fontsize=11, ha="center")

    # ---- LEFT: four co-op nodes arranged on a diamond cycle
    lpos = {
        "members":        (12, 20),
        "dues":           (25, 34),
        "treasury":       (38, 20),
        "node+steward":   (25, 6),
    }
    lb = {name: box(ax, x, y, 20, 10.5, "#2a2a30") for name, (x, y) in lpos.items()}

    # cycle edges (member→dues→treasury→node→members)
    loop_segs = [
        (lpos["members"], lpos["dues"]),
        (lpos["dues"], lpos["treasury"]),
        (lpos["treasury"], lpos["node+steward"]),
        (lpos["node+steward"], lpos["members"]),
    ]
    loop_edges = [ax.plot([], [], color=LOOP, lw=2.6, zorder=2)[0] for _ in loop_segs]

    # node name labels *inside* the boxes
    for name, (x, y) in lpos.items():
        lab = name.replace("+", "\n+").replace("node", "node").replace("steward", "steward")
        ax.text(x, y, lab, color=TEXT, fontsize=9, ha="center", va="center")

    # ---- RIGHT: three stacked boxes on an up-arrow (a line that exits)
    rx = 74
    rpos = {
        "members":        (rx, 20),
        "1 vendor":       (rx, 34),
        "shareholders":   (rx, 48),
    }
    rb = {name: box(ax, x, y, 22, 11, "#2a2a30") for name, (x, y) in rpos.items()}
    line = ax.plot([], [], color=LEAVE, lw=2.8, zorder=2)[0]
    # the value dot travelling up the platform
    travel_y = [rpos["members"][1], rpos["1 vendor"][1], rpos["shareholders"][1]]
    dot = ax.plot([], [], "o", color=LEAVE, ms=8, visible=False, zorder=3)[0]

    for name, (x, y) in rpos.items():
        ax.text(x, y, name, color=TEXT, fontsize=9, ha="center", va="center")

    # ---- bottom captions
    ax.text(25, 30, "the money comes back\nround to the people who made it", color=LOOP, fontsize=9.5, ha="center")
    ax.text(74, 8, "the money climbs out\nand exits to shareholders", color=LEAVE, fontsize=9.5, ha="center")

    src = ax.text(1, 1, "irl.coop — the value-flow diagram (V6)   ·  concept, not a number", color=DIM, fontsize=8.5, ha="left", va="bottom")

    TOTAL, FPS = 200, 24
    seg_length = 30

    def update(f):
        # LEFT
        a1 = ramp(f, 6, 26)
        for b in lb.values():
            b.set_alpha(a1)
        # loop edges draw in order
        for i, (edge, (p1, p2)) in enumerate(zip(loop_edges, loop_segs)):
            seg = ramp(f, 30 + i * 7, 52 + i * 7)
            px_, py_ = p1[0] + (p2[0] - p1[0]) * seg, p1[1] + (p2[1] - p1[1]) * seg
            edge.set_data([p1[0], px_], [p1[1], py_])
            edge.set_alpha(a1)
        # RIGHT
        a2 = ramp(f, 45, 72)
        for b in rb.values():
            b.set_alpha(a2)
        # the line + the dot climbing it
        lp = ramp(f, 75, 105)
        line.set_data([rx, rx], [rpos["members"][1], rpos["members"][1] + (48 - 20) * lp])
        dot.set_xdata([rx]); dot.set_ydata([20 + (48 - 20) * lp]); dot.set_visible(lp > 0.02)
        src.set_alpha(ramp(f, 120, 135))
        return list(loop_edges) + [line, dot] + list(lb.values()) + list(rb.values()) + [src]

    anim = animation.FuncAnimation(fig, update, frames=TOTAL, interval=1000 / FPS, blit=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    anim.save(str(OUT), writer=animation.FFMpegWriter(fps=FPS, bitrate=2400))
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    main()