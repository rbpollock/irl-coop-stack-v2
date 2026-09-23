"""irl.coop — V11 "the mycelia": what strong local ties build (reversed story).

REVERSED from the first pass. The cloud/SaaS is shown FIRST as the extractor:
each local group is held as an isolated point, each with a thin line up to a
distant hub — paying per seat, kept apart. That is the baseline.

The story builds the OTHER way:
   - the isolated points begin to wire together (mycelial edges).
   - the nearer they cluster, the FEWER lines to the hub (extraction fades)
     and the TIGHTER the local web becomes.
   - the endpoint is a dense common-local net: cost shrinks AND capabilities
     you could never have alone appear (the "higher order", drawn as the
     cluster's web now spanning more than any one dot).

So the arc is: scattered + extracted --> wired + free --> stronger together.
Mycelial = a net that can transport nutrients and signal across many units —
that's what a local cluster actually is.
"""
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pathlib import Path

OUT = Path(__file__).resolve().parent / "video" / "fear-cluster-diagram.mp4"
BG = "#1C1C1C"; TEXT = "#E7E7EA"; DIM = "#9A9AA6"
CLOUD = "#C17A5C"     # warm — extraction / the hub
TIES = "#7C8CFF"      # blue — the local mycelial net
GOLD = "#C9A24A"

def ramp(v,a,b): return max(0.0, min(1.0, (v-a)/max(1,b-a)))

def main():
    fig = plt.figure(figsize=(12.8,7.2), dpi=150)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0,0,1,1])
    ax.set_facecolor(BG); ax.axis("off")
    ax.set_xlim(0,13); ax.set_ylim(0,7)

    N = 14
    # scattered start positions (spread out, not touching)
    import random; random.seed(11)
    scatter = []
    for i in range(N):
        ang = -math.pi/2 + i*(2*math.pi)/N
        r = 3.4 + 1.1*math.sin(i*2.7)
        scatter.append((6.5 + r*math.cos(ang)*1.6, 3.5 + r*math.sin(ang)*1.3))
    # final clustered positions (tight)
    cluster = []
    for i in range(N):
        ang = -math.pi/2 + i*(2*math.pi)/N
        r = 1.5 + 0.35*math.sin(i*3)
        cluster.append((4.5 + r*math.cos(ang)*1.5, 3.5 + r*math.sin(ang)*1.25))

    # interp between scatter and cluster over time
    dots = [ax.plot([], [], "o", color=TEXT, ms=6, alpha=0)[0] for _ in range(N)]

    # hub (cloud) — present at start, drawing extraction lines, then fades as ties form
    hubx, huby = 10.8, 3.5
    hub = plt.Rectangle((hubx-1.0, huby-0.7), 2.0, 1.4, fc="#2a2a30", ec=CLOUD, lw=2, alpha=0)
    ax.add_patch(hub)
    hubcap = ax.text(hubx, huby-0.3, "the only tool\naround: distance\nand a bill", color=CLOUD, fontsize=9, ha="center", va="center", alpha=0)
    hub_lines = [ax.plot([], [], color=CLOUD, lw=1.2, alpha=0)[0] for _ in range(N)]   # extraction spokes

    # mycelial local ties (drawn increasingly)
    pairs = []
    for i in range(N):
        for j in range(i+1,N):
            if (i+j+1) % 3 != 0: pairs.append((i,j))
    ties = [ax.plot([], [], color=TIES, lw=1.6, alpha=0)[0] for _ in pairs]

    # captions
    top = ax.text(6.0, 6.45, "distance and a bill keep them from weaving in", color=CLOUD, fontsize=11, ha="center", fontweight="bold", alpha=0)
    mid = ax.text(6.5, 0.6, "the local web grows: trust, talking, safety, support", color=TIES, fontsize=11, ha="center", alpha=0)
    pay = ax.text(6.5, 5.9, "carry what none alone can hold, and no tether to rent", color=GOLD, fontsize=10.5, ha="center", alpha=0)
    src = ax.text(0.3, 0.05, "irl.coop — the web: a company sends a bill · a web holds people", color=DIM, fontsize=8.5, ha="left", va="bottom", alpha=0)

    TOTAL, FPS = 210, 24

    def update(f):
        # 1) dots appear in scatter
        for i,d in enumerate(dots):
            d.set_alpha(ramp(f, 8, 20))
        # 2) hub + extraction spokes
        ek = ramp(f, 14, 40)
        hub.set_alpha(ek); hubcap.set_alpha(ek*0.9)
        for i,ln in enumerate(hub_lines):
            px,py = scatter[i]
            ln.set_alpha(ek * (1.0 - ramp(f, 120, 152)))   # extraction fades as ties form
            ln.set_data([px, px+(hubx-px)],[py, huby])
        top.set_alpha(ramp(f, 16, 30))
        # 3) ties form, dots converge
        tt = ramp(f, 60, 150)
        for i in range(N):
            sx,sy = scatter[i]; cx,cy = cluster[i]
            mx= sx+(cx-sx)*tt; my= sy+(cy-sy)*tt
            dots[i].set_data([mx],[my])
        te = ramp(f, 60, 118)
        for e,(i,j) in enumerate(pairs):
            pi,pj = (cluster[i],cluster[j]) if tt>0.95 else (scatter[i],scatter[j])
            ties[e].set_alpha(te * (0.3+0.7*min(1,(tt)/0.5)) )
            x1,y1=pi; x2,y2=pj
            # use current interpolated pos
            ties[e].set_data([scatter[i][0]+(cluster[i][0]-scatter[i][0])*tt, scatter[j][0]+(cluster[j][0]-scatter[j][0])*tt],
                             [scatter[i][1]+(cluster[i][1]-scatter[i][1])*tt, scatter[j][1]+(cluster[j][1]-scatter[j][1])*tt])
        # 4) payoff captions
        pay.set_alpha(ramp(f, 150, 178))
        src.set_alpha(ramp(f, 178, 198))
        return dots + hub_lines + [hub, hubcap] + list(ties) + [pay, src, top]

    anim = animation.FuncAnimation(fig, update, frames=TOTAL, interval=1000/FPS, blit=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    anim.save(str(OUT), writer=animation.FFMpegWriter(fps=FPS, bitrate=2400))
    print("WROTE", OUT)

if __name__ == "__main__":
    main()