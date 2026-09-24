#!/usr/bin/env python3
"""gen_pricing.py — cost-vs-scale chart (SVG) for the recap.
Commercial per-seat line vs irl.coop shared member-run cost, 1..3000 seats.
Estimate; irl.coop cost is shared across members (never dumped on one user).
"""
import json, os, math

OUT = os.path.dirname(os.path.abspath(__file__))
SVG = os.path.join(OUT, "render", "art", "pricing.svg")

# --- model (labeled estimates) ---
# Commercial = ONE seat of EACH tool irl.coop replaces, public list, non-nonprofit:
#   Workspace 14 + Slack 8.75 + Zoom 13.33 + phone 26 + Asana 13.49 + Airtable 20 +
#   Typeform 8 + Cal.com 12 + CRM 25 + Drive 12 + Mailchimp 10 + Eventbrite 10 + Notion 10
COMM_PER_SEAT_MO = 182.57    # per person, per month — the whole stack rented
IRL_BASE_MO = 40.0           # shared member-run baseline (hardware+storage)
IRL_PER_SEAT_MO = 1.0        # marginal, shared — NOT per-seat licensing
YEAR = 12
YMAX = 500000

def comm(seats): return seats * COMM_PER_SEAT_MO * YEAR
def irl(seats):  return (IRL_BASE_MO + seats * IRL_PER_SEAT_MO) * YEAR

# --- geometry ---
W, H = 1000, 620
L, R, T, B = 120, 940, 110, 520
XMAX = 3000

def X(s): return L + (R - L) * (s ** 0.5) / (XMAX ** 0.5)     # sqrt so low end is visible
def Y(v): return B - (B - T) * min(v, YMAX) / YMAX

def path(fn):
    pts = []
    s = 1
    while s <= XMAX:
        pts.append(f"{X(s):.1f},{Y(fn(s)):.1f}")
        s += max(1, int(s * 0.03))
    pts.append(f"{X(XMAX):.1f},{Y(fn(XMAX)):.1f}")
    return "M" + " L".join(pts)

marks = [(1, "you"), (8, "small"), (40, "med"), (400, "neighborhood"), (3000, "civic")]

rows = []
for s, lab in marks:
    c, i = comm(s), irl(s)
    # anchor the end labels inward so they never run off the right edge
    anch = "end" if s == 3000 else ("start" if s == 1 else "middle")
    rows.append(f'<circle cx="{X(s):.0f}" cy="{Y(c):.0f}" r="8" fill="#ff6b6b"/>'
                f'<circle cx="{X(s):.0f}" cy="{Y(i):.0f}" r="8" fill="#5eead4"/>'
                f'<text x="{X(s):.0f}" y="{B+42}" fill="#c3d2e8" font-size="24" '
                f'font-family="Inter,sans-serif" text-anchor="{anch}">{lab}</text>')

# big end-value callouts (the key numbers), placed clear of the axis + tick labels
def money(v):
    return f"${v/1_000_000:.1f}M" if v >= 1_000_000 else f"${v/1000:.0f}k"
k_comm, k_irl = comm(3000), irl(3000)
callout = (
    f'<text x="{R}" y="{Y(k_comm)-30:.0f}" fill="#ff6b6b" font-size="58" font-weight="800" '
    f'font-family="Inter,sans-serif" text-anchor="end">{money(k_comm)}/yr</text>'
    f'<text x="{R}" y="{Y(k_irl)-30:.0f}" fill="#5eead4" font-size="58" font-weight="800" '
    f'font-family="Inter,sans-serif" text-anchor="end">{money(k_irl)}/yr</text>')

grid = []
for v in range(0, YMAX + 1, 60000):
    grid.append(f'<line x1="{L}" y1="{Y(v):.0f}" x2="{R}" y2="{Y(v):.0f}" stroke="#1e2a3d"/>'
                f'<text x="{L-14}" y="{Y(v)+9:.0f}" fill="#8ea3c2" font-size="26" '
                f'font-family="Inter,sans-serif" text-anchor="end">${v//1000}k</text>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<rect width="{W}" height="{H}" fill="none"/>
<text x="{L}" y="58" fill="#eef3fb" font-size="42" font-weight="700" font-family="Inter,sans-serif">what a group stops renting, per year</text>
{''.join(grid)}
<path d="{path(comm)}" fill="none" stroke="#ff6b6b" stroke-width="5" stroke-linecap="round"/>
<path d="{path(irl)}" fill="none" stroke="#5eead4" stroke-width="5" stroke-linecap="round"/>
{''.join(rows)}
{callout}
<text x="{L}" y="{B+96}" fill="#8ea3c2" font-size="26" font-family="Inter,sans-serif">estimate · one seat of each tool irl.coop replaces (~$183/mo) · shared across members, never one user · labor unpriced</text>
</svg>'''

os.makedirs(os.path.dirname(SVG), exist_ok=True)
open(SVG, "w").write(svg)
print("wrote", SVG)
print(json.dumps([[lab, s, int(comm(s)), int(irl(s))] for s, lab in marks]))