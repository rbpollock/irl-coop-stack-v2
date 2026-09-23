#!/usr/bin/env python3
"""Render a 'Goodbye Group Gouging' title-card frame for the video assembly."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

OUT = Path(__file__).resolve().parent / "video" / "title-card.png"

BG = "#1C1C1C"
TEXT = "#E7E7EA"
DIM = "#9A9AA6"
ACCENT = "#7C8CFF"

fig = plt.figure(figsize=(12.8, 7.2), dpi=150)
fig.patch.set_facecolor(BG)

ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
ax.text(0.5, 0.72, "Goodbye", color=TEXT, fontsize=68, ha="center", va="center", fontweight="bold")
ax.text(0.5, 0.52, "Group Gouging", color=ACCENT, fontsize=68, ha="center", va="center", fontweight="bold")
ax.text(0.5, 0.30, "the modern co-op runs on a shared node, not a bill that grows with your headcount",
        color=DIM, fontsize=20, ha="center", va="center")
ax.text(0.5, 0.14, "irl.coop", color=TEXT, fontsize=16, ha="center", va="center", fontweight="bold")
ax.text(0.5, 0.08, "from the cost model · prices verified 2026-09-18", color=DIM, fontsize=12, ha="center", va="center")

fig.savefig(OUT, facecolor=BG)
print(f"WROTE {OUT}")