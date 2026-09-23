"""irl.coop — cost-model animations, charts 1-5.

Scripted animations of the cost model's five charts, rendered with matplotlib
(no cairo/pango, no sudo, chart-native). Every number on screen is read from
`infra/scripts/cost-model.py --json` at render time — the single source — so the
animation can never drift from the verified model.

Render one chart:
    uv run --with matplotlib python docs/design/cost-model-animation.py 1
Render all five:
    uv run --with matplotlib python docs/design/cost-model-animation.py

Output: docs/design/video/cost-model-*.mp4
"""

import json
import math
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation

REPO = Path(__file__).resolve().parent.parent.parent
VIDEO = Path(__file__).resolve().parent / "video"

# Palette (matches video-charts-storyboard.html)
BG = "#1C1C1C"
GRID = "#3A3A40"
COMM = "#8A8A96"          # commercial (dim)
NODE = "#7C8CFF"          # irl.coop node (accent)
TEXT = "#E7E7EA"
DIM = "#9A9AA6"
ACCENT = "#7C8CFF"


def load_model() -> dict:
    out = subprocess.run(
        ["python3", "infra/scripts/cost-model.py", "--json"],
        capture_output=True, text=True, cwd=REPO, check=True,
    )
    return json.loads(out.stdout)


def fmt(v: float) -> str:
    return f"${v:,.2f}" if v < 1000 else f"${v:,.0f}"


def ramp(f, a, b):
    return max(0.0, min(1.0, (f - a) / max(1, b - a)))


def new_fig(title, figsize=(12.8, 7.2)):
    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.tick_params(colors=TEXT, labelsize=12)
    ax.set_title(title, color=TEXT, fontsize=16, pad=16, loc="left")
    ax.grid(True, axis="y", color=GRID, linewidth=0.8, alpha=0.5)
    ax.set_axisbelow(True)
    return fig, ax


def stamp(ax, m):
    dates = sorted({r["verified_on"] for r in m["scale_model"]["scale_rates"]})
    return ax.text(0.015, 0.02,
                   f"Source: irl.coop cost model · prices verified {dates[-1]} · every figure read from cost-model.py --json",
                   transform=ax.transAxes, color=DIM, fontsize=8.5, va="bottom")


def save(fig, update, name, frames=180, fps=24, seconds=None):
    if seconds:
        frames = int(seconds * fps)
    anim = animation.FuncAnimation(fig, update, frames=frames, interval=1000 / fps, blit=False)
    out = VIDEO / f"cost-model-{name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    anim.save(str(out), writer=animation.FFMpegWriter(fps=fps, bitrate=2400))
    print(f"WROTE {out} ({frames/fps:.1f}s)")


# ---------------------------------------------------------------- chart 1

def chart_divergence(m, dur=18.5):
    sc = m["scale_model"]["scenarios"]
    commercial = [m["commercial_total_monthly"], sc[0]["commercial_monthly"], sc[1]["commercial_monthly"]]
    node = [m["irl_total_monthly"], sc[0]["node"]["total"], sc[1]["node"]["total"]]
    ratio = commercial[2] / node[2]

    fig, ax = new_fig("Renting tools vs sharing one machine — the gap   (log $, per month)")
    ax.set_yscale("log"); ax.set_ylim(100, 2_500_000); ax.set_xlim(-0.4, 2.4)
    ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["40 members", f"{sc[0]['participants']:,}", f"{sc[1]['participants']:,}"])
    ax.set_yticks([100, 1_000, 10_000, 100_000, 1_000_000]); ax.set_yticklabels(["$100", "$1k", "$10k", "$100k", "$1M"])

    N = 120
    dense_x = [2 * i / (N - 1) for i in range(N)]
    dc, dn = [], []
    for x in dense_x:
        seg = min(int(x), 1); t = x - seg
        lo, hi = math.log10(commercial[seg]), math.log10(commercial[seg + 1]); dc.append(10 ** (lo + (hi - lo) * t))
        lo, hi = math.log10(node[seg]), math.log10(node[seg + 1]); dn.append(10 ** (lo + (hi - lo) * t))

    cl, = ax.plot([], [], color=COMM, lw=3.0); nl, = ax.plot([], [], color=NODE, lw=3.6)
    cds = [ax.plot([], [], "o", color=COMM, ms=8)[0] for _ in range(3)]
    nds = [ax.plot([], [], "o", color=NODE, ms=9)[0] for _ in range(3)]
    clabs = [ax.text(x, commercial[i] * 10 ** 0.13, fmt(commercial[i]), color=COMM, fontsize=10.5, ha="center", va="bottom") for i, x in enumerate([0, 1, 2])]
    nlabs = [ax.text(x, node[i] * 10 ** -0.13, fmt(node[i]), color=NODE, fontsize=10.5, ha="center", va="top") for i, x in enumerate([0, 1, 2])]
    gap = ax.plot([2, 2], [node[2], commercial[2]], ls="--", color=TEXT, lw=1.5, alpha=0.0)[0]
    gt = ax.text(2, math.sqrt(node[2] * commercial[2]), f"  {ratio:.0f}×", color=ACCENT, fontsize=16, va="center", fontweight="bold", alpha=0.0)
    src = stamp(ax, m)
    for i, x in enumerate([0, 1, 2]):
        cds[i].set_data([x], [commercial[i]]); nds[i].set_data([x], [node[i]])

    def update(f):
        ax.title.set_alpha(ramp(f, 0, 24))
        k = int(ramp(f, 28, 98) * N)
        cl.set_data(dense_x[:k], dc[:k]); nl.set_data(dense_x[:k], dn[:k])
        for d in cds + nds: d.set_alpha(ramp(f, 105, 135))
        for lab in clabs + nlabs: lab.set_alpha(ramp(f, 105, 135))
        gap.set_alpha(ramp(f, 142, 164)); gt.set_alpha(ramp(f, 142, 164))
        src.set_alpha(ramp(f, 165, 185))
        return [cl, nl, gap, gt, src]

    save(fig, update, "divergence")
    print(f"  gap {ratio:.1f}x")


# ---------------------------------------------------------------- chart 2

def chart_wall(m):
    sc = m["scale_model"]["scenarios"]
    bar_total = sc[1]["participants"]  # 50,000 — the movement's ceiling
    ceilings = [c for c in m["scale_model"]["ceilings"] if c.get("max_users")]

    fig, ax = new_fig("The wall — prices end at a few hundred people   (participants, linear)")
    ax.set_xlim(0, bar_total * 1.06); ax.set_ylim(0, 10)
    ax.set_yticks([]); ax.set_yticklabels([])
    ax.set_xlabel("participants", color=TEXT, fontsize=12)
    ax.grid(False)
    for s in ax.spines.values(): s.set_color(GRID)
    ax.spines["left"].set_visible(False); ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)

    # the movement bar
    full = ax.barh(4.5, 0.0, height=0.6, color=GRID, alpha=0.7)[0]
    ax.text(bar_total * 0.5, 5.1, "the movement at 10,000+", color=DIM, fontsize=11, ha="center", va="bottom")

    marks = []
    mlabels = []
    ypos = [7.8, 6.6, 5.4, 4.2][:len(ceilings)]
    for i, c in enumerate(ceilings):
        x = c["max_users"]
        marks.append(ax.plot([], [], "|", color=NODE, ms=16, lw=3.5)[0])
        mlabels.append(ax.text(x, ypos[i], f"{c['vendor']} · {x}", color=NODE, fontsize=10.5, ha="left", va="center"))
    bracket = ax.annotate("self-serve menu ends here →", xy=(500, 3.2), xytext=(1400, 2.2),
                          color=ACCENT, fontsize=12, fontweight="bold",
                          arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.6))
    bracket.set_alpha(0.0)
    src = stamp(ax, m)

    def update(f):
        ax.title.set_alpha(ramp(f, 0, 22))
        full.set_width(bar_total * ramp(f, 22, 70))
        for i, c in enumerate(ceilings):
            mline = marks[i]
            mline.set_data([c["max_users"]], [ypos[i] - 0.2])
            mline.set_alpha(ramp(f, 75, 105))
            mlabels[i].set_alpha(ramp(f, 75, 105))
        bracket.set_alpha(ramp(f, 115, 145))
        src.set_alpha(ramp(f, 155, 175))
        return [full, bracket, src]

    save(fig, update, "wall")


# ---------------------------------------------------------------- chart 3

def chart_three_ways(m):
    """'Three ways to buy it' — rebuilt as a build-up, not a bar chart.

    Why the old version was unclear:
      - three disjoint horizontal bars gave no mechanism, so it read as 'look,
        three costs' instead of the actual point: SAME work, priced three ways.
      - a linear axis with $2,319 → $77.50 was dominated by the leftmost total,
        and no breakdown explained WHY the per-seat stack is large.

    Rebuild as three VERTICAL columns, built up live:
      - per-seat stack = stacked from its sub-lines (the 6 organizer tools + 3
        member tools), so you SEE it's nine per-person line items, each multiplied
        by headcount.
      - per-org mid-tier = stacked from its 7 subscriptions.
      - node         = one thin shared bar.
      The y-axis is capped so the node bar stays visible next to the columns;
      the landing tag names the real point: 'same work, three ways to pay'.
    """
    std = m["tiers"]["standard"]
    # per-seat stack: each row is already a per-seat line (seats × price)
    per_seat_segs = [r.get("monthly", 0) for r in std.get("rows", []) if r.get("monthly")]
    mid_items = [it.get("price", 0) for it in m["mid_tier"].get("items", []) or [] if it.get("price")]
    node_val = m["irl_running_monthly"]

    totals = [sum(per_seat_segs), sum(mid_items), node_val]
    top = max(totals)
    hi = top * 2.5   # cap so the tiny node column is a visible sliver, not a dot

    fig, ax = new_fig("Three ways to get your tools — at 40 members   ($/month)")
    ax.set_ylim(0, hi)
    ax.set_xlim(-0.6, 2.75)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["pay per person\n(9+ subscriptions)", "bundle into one\n(growing becomes\nunaffordable)", "own it together\n(lowest cost)"], fontsize=9)
    ax.tick_params(axis="y", labelsize=11)
    ax.grid(False)
    ax.set_ylabel("$/month", color=TEXT, fontsize=12)
    # y $ axis visible + a faint $77.50 reference line
    ax.axhline(node_val, color=NODE, lw=1.0, alpha=0.4, ls=":")
    ax.text(2.62, node_val, fmt(node_val), color=NODE, fontsize=9, ha="left", va="bottom")

    seg_cols = [COMM, COMM, NODE]
    rects = []       # (patch, target_height, bottom_of_that_seg)
    for ci, segs in enumerate((per_seat_segs, mid_items, [node_val])):
        y = 0.0
        for s in segs:
            r = plt.Rectangle((ci - 0.32, y), 0.64, 0.0, color=seg_cols[ci], alpha=0.92, lw=0)
            ax.add_patch(r)
            rects.append((r, s, y))
            y += s

    tot_labs = [ax.text(x, totals[i] * 1.06, "", color=TEXT, fontsize=15, ha="center", va="bottom", fontweight="bold") for i, x in enumerate([0, 1, 2])]
    seg_hint = ax.text(2.6, hi * 0.97, "per person: 9+ subscriptions\none bundle: growing unaffordable\nshare it: the lowest cost", color=DIM, fontsize=9.5, ha="right", va="top", linespacing=1.5)
    seg_hint.set_alpha(0.0)
    tag = ax.text(0.0, hi * 0.12, "OWN it together, almost free", color=ACCENT, fontsize=15, ha="left", va="bottom", fontweight="bold", alpha=0.0)
    tag.set_position((-0.5, hi * 0.12))
    src = stamp(ax, m)

    def update(f):
        ax.title.set_alpha(ramp(f, 0, 20))
        g = ramp(f, 22, 78)
        # per column, grow each segment jointly from the column base, re-stacked
        for x in range(3):
            frac = g if x < 2 else max(0.0, (g - 0.35) / 0.4)  # node bar waits, then catches up
            col_rects = [p for p in rects if abs(p[0].get_x() - (x - 0.32)) < 1e-6]
            prev = 0.0
            for (r, s, y0) in col_rects:
                r.set_y(prev)
                r.set_height(s * frac)
                prev += s * frac
        for lab, tot in zip(tot_labs, totals):
            lab.set_text(fmt(tot) if ramp(f, 90, 116) > 0.99 else "")
            lab.set_alpha(ramp(f, 90, 116))
        seg_hint.set_alpha(ramp(f, 100, 122))
        tag.set_alpha(ramp(f, 130, 156))
        src.set_alpha(ramp(f, 162, 184))
        return [p[0] for p in rects] + tot_labs + [seg_hint, tag, src]

    save(fig, update, "three-ways")
    print("  " + "  ".join(f"{n}: {fmt(v)}" for n, v in zip(("per-seat", "per-org", "node"), totals)))


# ---------------------------------------------------------------- chart 4

def chart_redundancy(m):
    f = m["federation"]
    owned = f["replica_count_independent"] * f["shared_assets_gb"] * f["node_rate_per_gb_month"]
    s3 = f["s3_same_replicas_monthly"]
    fig, ax = new_fig("Keep it safe without a data center — duplicates, pennies   ($/month)")
    names = ["your machine\n(encrypted copies\nstored with you)", "the cloud\n(open book, locks\nyou out later)"]
    vals = [owned, s3]
    cols = [NODE, COMM]
    bars = ax.bar(names, [0.0, 0.0], color=cols, width=0.5)
    labs = [ax.text(i, 0, "", color=TEXT, fontsize=13, ha="center", va="bottom") for i in range(2)]
    ax.set_ylim(0, s3 * 1.6)
    ax.grid(True, axis="y", color=GRID, linewidth=0.8, alpha=0.5)
    src = stamp(ax, m)

    def update(f):
        ax.title.set_alpha(ramp(f, 0, 22))
        g = ramp(f, 25, 85)
        for b, v in zip(bars, vals):
            b.set_height(v * g)
        for lab, v in zip(labs, vals):
            lab.set_text(f"${v:.2f}" if g > 0.9 else "")
            lab.set_y(v * 1.05)
            lab.set_alpha(ramp(f, 90, 120))
        src.set_alpha(ramp(f, 135, 160))
        return list(bars) + labs + [src]

    save(fig, update, "redundancy")
    print(f"  owned ${owned:.2f}  s3 ${s3:.2f}")


# ---------------------------------------------------------------- chart 6

def chart_crossover(m):
    """Chart 6 — 'It pays for itself at N groups' (the self-sustaining line).

    Two lines on one axis:
      - a FIXED cost line (the node's full running + stewardship cost) drawn as a
        constant horiz line across the whole time axis.
      - a CLIMBING contribution line: groups × $25/mo, drawn left-to-right.

    They cross at groups_to_cover_total (13) — the moment contributions meet cost.
    The drawn point is the crossover the doc names out loud; below it the node
    loses money per month, above it it's self-sustaining.

    Data is ILLUSTRATIVE (revenue_inputs + node placeholders in cost-model.data.json) —
    the emitter watermarks derived numbers, and this chart is marked so it can't
    read as fact.
    """
    fixed = m["irl_total_monthly"]                  # stewardship + running (437.50)
    running = m["node_monthly"]                     # infra only (73.00)
    inflow = m["node_inflow_monthly"]               # member dues already in (145.00)
    contrib = m["revenue_inputs"]["group_monthly"]  # per-group ($25)
    need_total = m["groups_to_cover_total"]         # 13 groups to cover the total
    need_running = m["groups_to_cover_node"]        # 0 — member dues already cover running

    x_max = max(1, int(need_total * 1.7))
    xs = list(range(x_max + 1))
    rev = [x * contrib for x in xs]

    fig, ax = new_fig("One shared machine pays for itself at a dozen groups   ($/month, illustrative)")
    ax.set_ylim(0, max(rev) * 1.18)
    ax.set_xlim(0, x_max)
    ax.set_xlabel("groups contributing", color=TEXT, fontsize=12)
    ax.set_ylabel("$/month", color=TEXT, fontsize=12)
    ax.set_xticks(range(0, x_max + 1, max(1, x_max // 6)))
    ax.grid(True, axis="y", color=GRID, linewidth=0.8, alpha=0.45)

    cost_line = ax.axhline(0.0, color=COMM, lw=2.4)
    running_line = ax.axhline(0.0, color=DIM, lw=1.6, ls=":")
    rev_line, = ax.plot([], [], color=NODE, lw=3.0)
    cross_marker = ax.plot([], [], "o", color=ACCENT, ms=9)[0]
    cross_text = ax.text(0, 0, "", color=ACCENT, fontsize=12, ha="left", va="bottom", fontweight="bold", alpha=0.0)
    tot_lab = ax.text(0, 0, "", color=COMM, fontsize=11, ha="left", va="bottom", alpha=0.0)
    run_lab = ax.text(0, 0, "", color=DIM, fontsize=10, ha="left", va="bottom", alpha=0.0)
    src = stamp(ax, m)

    def update(f):
        ax.title.set_alpha(ramp(f, 0, 18))
        # fixed cost lines appear fully (constants)
        cost_line.set_ydata([fixed, fixed]); cost_line.set_alpha(0.6 + 0.4 * ramp(f, 20, 38))
        running_line.set_ydata([running, running]); running_line.set_alpha(0.35 + 0.35 * ramp(f, 20, 38))
        tot_lab.set_text(fmt(fixed) if ramp(f, 20, 38) > 0.99 else "")
        tot_lab.set_position((1, fixed * 1.03)); tot_lab.set_alpha(ramp(f, 20, 38))
        run_lab.set_text(fmt(running) if ramp(f, 20, 38) > 0.99 else "")
        run_lab.set_position((1, running * 1.03)); run_lab.set_alpha(ramp(f, 20, 38))
        # contribution line grows
        g = ramp(f, 38, 84)
        k = int(g * len(xs))
        rev_line.set_data(xs[: k + 1], rev[: k + 1])
        # catch the crossing once the line passes the fixed cost
        found = None
        for xx in range(1, k + 1):
            if rev[xx] >= fixed and rev[xx - 1] < fixed:
                found = xx
                break
        if found is not None:
            cross_marker.set_data([found], [fixed]); cross_marker.set_alpha(ramp(f, 92, 118))
            cross_text.set_text(f"{found} groups  ")
            cross_text.set_position((found + 0.5, rev[found] * 1.04))
            cross_text.set_alpha(ramp(f, 92, 118))
        # close
        src.set_alpha(ramp(f, 135, 156))
        return [cost_line, running_line, rev_line, cross_marker, cross_text, tot_lab, run_lab, src]

    save(fig, update, "crossover")
    print(f"  node total ${fixed}/mo (running ${running} + stewardship) | need {need_total} groups @${contrib} | running already covered by member dues (${inflow}/mo in)")


def chart_per_participant(m):
    sc = m["scale_model"]["scenarios"]
    groups = [f"{s['participants']:,}" for s in sc]
    comm = [s["commercial_per_participant_year"] for s in sc]
    node = [s["node_per_participant_year"] for s in sc]
    fig, ax = new_fig("Per person, per year — subscriptions vs sharing   (log $)")
    x = [0, 1]
    w = 0.35
    cb = ax.bar([i - w / 2 for i in x], [0.0, 0.0], width=w, color=COMM, label="renting platforms")
    nb = ax.bar([i + w / 2 for i in x], [0.0, 0.0], width=w, color=NODE, label="sharing one machine")
    ax.set_yscale("log"); ax.set_ylim(1, 1000)
    ax.set_xticks(x); ax.set_xticklabels(groups)
    ax.set_ylabel("$ / participant / year", color=TEXT, fontsize=12)
    ax.legend(facecolor=BG, edgecolor=GRID, labelcolor=TEXT)
    clabs = [ax.text(i - w / 2, 0, "", color=COMM, fontsize=11, ha="center", va="bottom") for i in x]
    nlabs = [ax.text(i + w / 2, 0, "", color=NODE, fontsize=11, ha="center", va="bottom") for i in x]
    src = stamp(ax, m)

    def update(f):
        ax.title.set_alpha(ramp(f, 0, 22))
        g = ramp(f, 25, 85)
        for b, v in zip(cb, comm):
            b.set_height(v * g)
        for b, v in zip(nb, node):
            b.set_height(v * g)
        for lab, v in zip(clabs, comm):
            lab.set_text(f"${v:,.0f}" if g > 0.9 else "")
            lab.set_y(v * 1.15); lab.set_alpha(ramp(f, 90, 120))
        for lab, v in zip(nlabs, node):
            lab.set_text(f"${v:,.2f}" if g > 0.9 else "")
            lab.set_y(v * 1.15); lab.set_alpha(ramp(f, 90, 120))
        src.set_alpha(ramp(f, 135, 160))
        return list(cb) + list(nb) + clabs + nlabs + [src]

    save(fig, update, "per-participant")
    print(f"  commercial {[f'${c:,.0f}' for c in comm]}  node {[f'${n:,.2f}' for n in node]}")


CHARTS = {
    "1": chart_divergence,
    "2": chart_wall,
    "3": chart_three_ways,
    "4": chart_redundancy,
    "5": chart_per_participant,
    "6": chart_crossover,
}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    m = load_model()
    if which == "all":
        for fn in CHARTS.values():
            fn(m)
    else:
        CHARTS[which](m)


if __name__ == "__main__":
    main()
