#!/usr/bin/env python3
"""Render the closing slide for the 'Goodbye Group Gouging' video.

Ties the whole argument together: what's built, what's the step, and the honest
'what's next' — matching the intro-video-series honesty rules (no claims about
unbuilt features; a pilot invite, not an anthem).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path(__file__).resolve().parent / "video" / "closing-slide.png"

BG = "#1C1C1C"
TEXT = "#E7E7EA"
DIM = "#9A9AA6"
ACCENT = "#7C8CFF"


def main():
    fig = plt.figure(figsize=(12.8, 7.2), dpi=150)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    lines = [
        ("Cooperation is priced. A group shouldn't pay rent on its own tools.", TEXT, True),
        ("", None, False),
        ("Goodbye group gouging.", ACCENT, True),
        ("", None, False),
        ("It's a pilot. One node, one co-op, real numbers.", DIM, False),
        ("Bring us a group with a task to get done this season.", DIM, False),
        ("irl.coop", TEXT, True),
    ]
    y = 0.86
    for text, color, bold in lines:
        if text:
            ax.text(0.5, y, text, color=color, fontsize=20 if bold and text.startswith("Goodbye") else 16,
                    ha="center", va="center", fontweight="bold" if bold else "normal")
        y -= 0.11

    fig.savefig(OUT, facecolor=BG)
    print(f"WROTE {OUT}")


if __name__ == "__main__":
    main()