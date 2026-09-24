#!/usr/bin/env python3
"""build_wrapped.py — portrait (1080x1920) irl.coop stack recap from stats.json.
Cover → per-pillar (time + tokens + made/hard) → artifact grid → wrap.
Deterministic; rendered to MP4 by HyperFrames.
"""
import json
import html as _h
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATS = ROOT / "stats.json"
OUT = ROOT / "render" / "index.html"
PAL = ["#0d1426", "#172038", "#233043", "#1c1233", "#0c2b26", "#30200f",
       "#1d1030", "#2a1a1f", "#122337", "#0b0e18"]


def esc(s):
    return _h.escape(str(s or "")[:160])


def build(cards):
    frag, tl = [], []
    durs = [c.get("d", 2.1) for c in cards]
    starts = []
    a = 0.0
    for dd in durs:
        starts.append(a)
        a += dd
    for i, c in enumerate(cards):
        st, dur = starts[i], durs[i]
        bg = PAL[i % len(PAL)]
        kick = c.get("kick", "")
        if c["kind"] == "grid":
            cells = ""
            for j, src in enumerate(c.get("items", [])):
                cells += f'<div class="g" id="g{i}_{j}"><img src="{esc(src)}"></div>'
            body = f'<div class="title">{esc(c["title"])}</div><div class="rows grid">{cells}</div>'
        else:
            big = c.get("big", "")
            body = f'<div class="big">{esc(big)}</div>'
            if c.get("sub"):
                body += f'<div class="sub">{esc(c["sub"])}</div>'
            if c.get("foot"):
                body += f'<div class="foot">{esc(c["foot"])}</div>'
        frag.append(
            f'<div class="clip slide" id="sn{i}" data-start="{st:.2f}" data-duration="{dur:.2f}" '
            f'data-track-index="{i}" style="background:{bg}"><div class="kick">{esc(kick)}</div>{body}</div>'
        )
        tl.append(f'tl.set("#sn{i}",{{autoAlpha:0}});')
        tl.append(f'tl.set("#sn{i}",{{autoAlpha:1}},{st:.2f});')
        tl.append(f'tl.set("#sn{i}",{{autoAlpha:0}},{st + dur:.2f});')
        if c["kind"] == "grid":
            for j in range(len(c.get("items", []))):
                tl.append(f'tl.fromTo("#g{i}_{j}",{{opacity:0,scale:0.94}},'
                          f'{{opacity:1,scale:1,duration:0.3,ease:"power2.out"}},{st + 0.15 + j * 0.08:.2f});')
        elif c["kind"] == "stat":
            tl.append(f'tl.fromTo("#sn{i} .big",{{opacity:0,y:30}},'
                      f'{{opacity:1,y:0,duration:0.32,ease:"power2.out"}},{st + 0.1:.2f});')
            tl.append(f'tl.fromTo("#sn{i} .sub",{{opacity:0}},{{opacity:1,duration:0.3}},{st + 0.55:.2f});')
            tl.append(f'tl.fromTo("#sn{i} .foot",{{opacity:0}},{{opacity:1,duration:0.3}},{st + 0.95:.2f});')
        else:
            tl.append(f'tl.fromTo("#sn{i} .big",{{opacity:0,y:30}},'
                      f'{{opacity:1,y:0,duration:0.4,ease:"power2.out"}},{st + 0.1:.2f});')

    tljs = "\n".join(tl)
    frag_html = "\n".join(frag)
    total = a
    html = (
        "<!doctype html><html><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=1080,height=1920\">"
        "<link href=\"https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&display=swap\" rel=\"stylesheet\">"
        "<script src=\"https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js\"></script>"
        "<style>"
        "body{margin:0;overflow:hidden;width:1080px;height:1920px;background:#05070d;"
        "font-family:'Space Grotesk',sans-serif;color:#f4f7fc}"
        ".slide{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;"
        "padding:120px 92px;opacity:0}"
        ".kick{font-size:26px;letter-spacing:.32em;text-transform:uppercase;color:#8fa2c2;margin-bottom:46px}"
        ".big{font-size:150px;font-weight:700;letter-spacing:-.04em;line-height:1;max-width:17ch}"
        ".sub{font-size:40px;margin-top:30px;color:#d9e6f6}"
        ".foot{font-size:30px;margin-top:64px;color:#9fb2cd;line-height:1.4}"
        ".title{font-size:52px;font-weight:700;margin-bottom:24px}"
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:26px}"
        ".g{opacity:0;scale:.94}"
        ".g img{width:100%;height:auto;border-radius:10px;border:1px solid rgba(255,255,255,.14)}"
        "</style></head><body>"
        f"<div id=\"root\" data-composition-id=\"main\" data-start=\"0\" "
        f"data-duration=\"{total:.1f}\" data-width=\"1080\" data-height=\"1920\">{frag_html}</div>"
        "<script>window.__timelines=window.__timelines||{};const tl=gsap.timeline({paused:true});\n"
        + tljs +
        "\nwindow.__timelines['main']=tl; tl.seek(0);</script></body></html>"
    )
    OUT.write_text(html)
    print(f"wrote {OUT} · {len(cards)} slides · {total:.1f}s")


if __name__ == "__main__":
    stats = json.loads(STATS.read_text())
    arts = [f"art/art{j}.png" for j in range(min(8, len(stats.get("artifacts") or [])))]
    verts = stats.get("vertical", [])

    cards = [
        dict(kind="cover", kick="THE ROOT STACK", big="irl.coop",
             sub="sovereign infra, told in layers",
             foot="keycloak · traefik · redis · postgres · stalwart · temporal", d=2.6),
    ]
    for v in verts:
        has = (v.get("hours") or 0) > 0 or (v.get("tokens", "0") != "0")
        cards.append(dict(
            kind="stat", kick=f"PILLAR · {v['name'].upper()}",
            big=v["comp"],
            sub=f"≈ {v['hours']} h  ·  {v['tokens']} tok" if has else "",
            foot=f"made — {v['done']}\nthe hard — {v['chal']}", d=2.3))
    cards += [
        dict(kind="cover", kick="THE HEART", big="what got built",
             sub="the docs, arrayed", d=1.6),
        dict(kind="grid", kick="THE ARTIFACTS", title="the docs · arrayed",
             items=arts, d=3.2),
        dict(kind="end", kick="THE WRAP", big="irl.coop",
             sub="the stack stays yours", foot="made with the loop", d=2.2),
    ]
    build(cards)