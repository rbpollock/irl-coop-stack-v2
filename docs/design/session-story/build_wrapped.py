#!/usr/bin/env python3
"""build_wrapped.py — portrait (1080x1920) 'SessionRolled' deck from stats.json.
Deterministic; no fetch; rendered to MP4 by HyperFrames.
"""
import json
import html as _h
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATS = ROOT / "stats.json"
OUT = ROOT / "render" / "index.html"

PAL = ["#0b1020", "#101e38", "#192545", "#291b4e", "#0f2428", "#28290f",
       "#2a152e", "#152c36", "#0f3a2a", "#080a0f"]


def esc(s):
    return _h.escape(str(s or "")[:130])


def build(cards):
    frag, tl = [], []
    durs = [c.get("d", 2.2 if c.get("kind") in ("cover", "end") else 1.8) for c in cards]
    starts = []
    a = 0.0
    for d in durs:
        starts.append(a)
        a += d
    total = a
    for i, c in enumerate(cards):
        st = starts[i]
        dur = durs[i]
        bg = PAL[i % len(PAL)]
        kick = c.get("kick", "")
        if c["kind"] == "list":
            rows = "".join(f'<div class="li">{esc(x)}</div>' for x in c.get("items", []))
            body = f'<div class="title">{esc(c.get("title", ""))}</div><div class="rows">{rows}</div>'
        elif c["kind"] == "grid":
            cells = ""
            for j, src in enumerate(c.get("items", [])):
                cells += f'<div class="g" id="g{i}_{j}"><img src="{esc(src)}"></div>'
            body = (f'<div class="title">{esc(c.get("title", ""))}</div>'
                    f'<div class="rows grid">{cells}</div>')
        else:
            body = (f'<div class="big">{esc(c.get("big", ""))}</div>'
                    f'<div class="sub">{esc(c.get("sub", ""))}</div>')
            if c.get("foot"):
                body += f'<div class="foot">{esc(c["foot"])}</div>'
        frag.append(
            f'<div class="clip slide" id="sn{i}" data-start="{st:.2f}" data-duration="{dur:.2f}" '
            f'data-track-index="{i}" style="background:{bg}"><div class="kick">{esc(kick)}</div>{body}</div>'
        )
        tl.append(f'tl.set("#sn{i}",{{autoAlpha:0}});')
        tl.append(f'tl.set("#sn{i}",{{autoAlpha:1}},{st:.2f});')
        if i + 1 < len(cards):
            tl.append(f'tl.set("#sn{i}",{{autoAlpha:0}},{st + dur:.2f});')
        if c["kind"] == "grid":
            for j in range(len(c.get("items", []))):
                tl.append(f'tl.fromTo("#g{i}_{j}",{{opacity:0,scale:0.94}},'
                          f'{{opacity:1,scale:1,duration:0.3,ease:"power2.out"}},{st + 0.1 + j * 0.08:.2f});')
        else:
            tl.append(f'tl.fromTo("#sn{i} .big,#sn{i} .rows,#sn{i} .title",'
                      f'{{opacity:0,y:30}},{{opacity:1,y:0,duration:0.32,ease:"power2.out"}},{st + 0.1:.2f});')
        tl.append(f'tl.set("#sn{i}",{{autoAlpha:0}},{st + dur:.2f});')

    tljs = "\n".join(tl)
    frag_html = "\n".join(frag)
    html = (
        "<!doctype html><html><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=1080,height=1920\">"
        "<link href=\"https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&display=swap\" rel=\"stylesheet\">"
        "<script src=\"https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js\"></script>"
        "<style>"
        "body{margin:0;overflow:hidden;width:1080px;height:1920px;background:#070a0f;"
        "font-family:'Space Grotesk',ui-sans-serif,sans-serif;color:#f4f7fc}"
        ".slide{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;"
        "padding:130px 90px;opacity:0}"
        ".kick{font-size:30px;letter-spacing:.34em;text-transform:uppercase;color:#97a9c2;margin-bottom:56px}"
        ".big{font-size:196px;font-weight:700;letter-spacing:-.045em;line-height:1}"
        ".sub{font-size:44px;margin-top:42px;color:#d6e4f4}"
        ".foot{font-size:34px;margin-top:72px;color:#94a7bf}"
        ".title{font-size:54px;font-weight:700;margin-bottom:26px}"
        ".li{font-size:42px;margin:22px 0;color:#eef3fb;line-height:1.25}"
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:26px}"
        ".g{opacity:0;scale:.92}"
        ".g img{width:100%;height:auto;border-radius:10px;border:1px solid rgba(255,255,255,.14)}"
        "</style></head><body>"
        f"<div id=\"root\" data-composition-id=\"main\" data-start=\"0\" "
        f"data-duration=\"{(total):.1f}\" data-width=\"1080\" data-height=\"1920\">{frag_html}</div>"
        "<script>window.__timelines=window.__timelines||{};const tl=gsap.timeline({paused:true});\n"
        + tljs +
        "\nwindow.__timelines['main']=tl; tl.seek(0);</script></body></html>"
    )
    OUT.write_text(html)
    print(f"wrote {OUT} · {len(cards)} slides · {(total):.1f}s")


if __name__ == "__main__":
    stats = json.loads(STATS.read_text())
    arts = [f.split("/")[-1] for f in (stats.get("artifacts") or [])]
    days = stats.get("days", 45)
    cards = [
        dict(kind="cover", kick="YOUR SEASON", big="SessionRolled",
             sub=f"{stats['sessions']} sessions · {days} days", foot="the work, wrapped", d=2.2),
        dict(kind="stat", kick="IN CONVERSATION", big=f"{stats['hours']} h",
             sub="estimated hours back-and-forth", foot=f"across {stats['sessions']} sessions", d=1.8),
        dict(kind="stat", kick="AI TOKENS", big=stats["tokens"],
             sub="through the stack this season", foot="full account", d=1.8),

        # ——— the heart: what got made ———
        dict(kind="cover", kick="THE HEART", big="what got built",
             sub="the fact · not the chatter", foot="made, then shown", d=1.7),
        dict(kind="grid", kick="THE ARTIFACTS", title="the docs · arrayed",
             items=[f"art/art{j}.png" for j in range(min(8, len(arts)))], d=3.0),
        dict(kind="list", kick="THE STACK", title="sovereign infra you hardened",
             items=["rag: local bge · 1024-dim embeddings",
                    "rerank brought back onto the docs search",
                    "docs search now jumps to the exact section",
                    "the isolation / RLS layers"], d=2.6),
        dict(kind="list", kick="THE TOOLS", title="did the work, earned its fuel",
             items=["workbench: corrected-cost decision card",
                    "the D6 paired bench (cheap ∥ strong)",
                    "the jev scene-scorer",
                    "session-story renderer"], d=2.4),
        dict(kind="list", kick="THE DIRECTOR", title="a model that only decided",
             items=["Open-Jev scored the scenes, kept it honest",
                    "no choke — it abstains at 0.5",
                    "recommendation-only, all approvals yours"], d=2.4),

        dict(kind="stat", kick="THE MARATHON", big=f"{stats['longest']['hours']} h",
             sub="longest single thread", foot=stats["longest"]["title"], d=1.8),
        dict(kind="list", kick="THE HARDEST", title="where we pushed back",
             items=stats.get("challenging", [])[:3], d=2.0),
        dict(kind="end", kick="THE WRAP", big="irl.coop",
             sub="45 days in one pass", foot="made with the loop", d=2.2),
    ]
    build(cards)