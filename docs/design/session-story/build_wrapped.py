#!/usr/bin/env python3
"""build_wrapped.py — a 'SessionRolled' (Spotify-Wrapped vibe) deck from the
Jev-scored storyboard → HyperFrames render/index.html. Deterministic, no fetch.
"""
import json
import html as _h
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "storyboard.json"
OUT = ROOT / "render" / "index.html"


def esc(s):
    return _h.escape(str(s or "")[:140])


def fmt(n):
    n = int(n or 0)
    if n >= 1_000_000:
        s = f"{n / 1_000_000:.1f}M"
        return s[:-2] if s.endswith(".0M") else s
    return f"{n:,}"


def main():
    data = json.loads(SRC.read_text())
    beats = data.get("beats", [])
    days = data.get("days", 45)
    total = len(beats)
    tok = sum((b.get("magnitude") or 0) for b in beats)
    best = max(beats, key=lambda b: b.get("confidence", 0) or 0)
    biggest = max(beats, key=lambda b: b.get("magnitude", 0) or 0)
    acts = {"I": 0, "II": 0, "III": 0}
    for b in beats:
        a = str(b.get("act", "I")).replace("Act", "").strip()
        acts[a if a in acts else "I"] += 1

    slides = [
        dict(kick="YOUR SEASON", big="SessionRolled",
             tag=f"{total} sessions  ·  {days} days", foot="a workloop by irl.coop",
             bg="#0b1020", c="#f3f6fb", count=0),
        dict(kick="THE STANDOUT", big=f"{int(best.get('confidence',0)*100)}%",
             tag="the one scene that stuck",
             foot=f"{best.get('title','')}  ·  {fmt(best.get('magnitude'))} tok",
             bg="#101e38", c="#6fd2ff", count=0),
        dict(kick="HEAVIEST PUSH", big=fmt(biggest.get("magnitude", 0)),
             tag="model tokens in one session",
             foot=f"{biggest.get('title','')}", bg="#221a3e", c="#d6b0ff", count=0),
        dict(kick="THREE ACTS", big=f"I · {acts['I']}   II · {acts['II']}   III · {acts['III']}",
             tag="setup · tension · resolve", foot="your 45 days in three shapes",
             bg="#0c2b24", c="#a7f2ce", count=0),
        dict(kick="SEASON · IN TOKENS", title="", big="",
             tag="tokens through the stack — almost all cache-warm",
             foot="the work, without the waste", bg="#231426", c="#ffb86b", count=tok),
        dict(kick="THAT'S A WRAP", title="same stack", bottom="a new story",
             tag="made by the loop, for the loop", foot="see irl.coop",
             bg="#080a10", c="#f3f6fb", count=0),
    ]

    frags, tls = [], []
    t = 0.0
    for i, s in enumerate(slides):
        dur = s.get("dur", 1.5)
        start = t
        t += dur + 0.25
        bid = f"n{i}" if s.get("count") else ""
        body = s.get("title") or s.get("big") or ""
        frags.append(
            f'<div class="clip slide" id="sn{i}" data-start="{start:.2f}" data-duration="{dur:.2f}" '
            f'data-track-index="{i}" style="background:{s["bg"]}">'
            f'<div class="k">{esc(s["kick"])}</div>'
            f'<div class="big"{(" id="+bid) if bid else ""}>{esc(body)}</div>'
            f'<div class="tag">{esc(s["tag"])}</div>'
            f'<div class="foot">{esc(s["foot"])}</div></div>'
        )
        tls.append(f'tl.fromTo("#sn{i}",{{autoAlpha:0}},{{autoAlpha:1,duration:0.32}},{start:.2f});')
        tls.append(f'tl.fromTo("#sn{i} .big",{{opacity:0,y:34}},'
                   f'{{opacity:1,y:0,duration:0.55,ease:"power2.out"}},{start + 0.18:.2f});')
        if s.get("count"):
            tls.append(f'var p{i}={{v:0}}; tl.to(p{i},{{v:{int(s["count"])},duration:1.05,ease:"power2.out",'
                       f'onUpdate:function(){{var e=document.getElementById("{bid}");if(e)e.textContent=fmt(p{i}.v);}}}},'
                       f'{start + 0.2:.2f});')
        tls.append(f'tl.to("#sn{i}",{{autoAlpha:0,duration:0.26}},{start + dur:.2f});')

    tljs = "\n".join(tls)
    frag = "\n".join(frags)

    html = (
        "<!doctype html>\n<html lang=\"en\"><head>\n<meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=1920, height=1080\">\n"
        "<link href=\"https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&display=swap\" rel=\"stylesheet\">\n"
        "<script src=\"https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js\"></script>\n"
        "<style>\n"
        "body{margin:0;overflow:hidden;width:1920px;height:1080px;background:#080a10;"
        "font-family:'Space Grotesk',system-ui,sans-serif;color:#f3f6fb}\n"
        ".slide{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;"
        "padding:0 220px;opacity:0}\n"
        ".k{font-size:26px;letter-spacing:.34em;text-transform:uppercase;color:#9fb0c6;margin-bottom:18px}\n"
        ".big{font-size:150px;font-weight:700;letter-spacing:-.03em;line-height:1;max-width:20ch}"
        ".tag{font-size:36px;margin-top:18px;color:#cfe0f2}\n"
        ".foot{font-size:34px;margin-top:54px;color:#fff;opacity:.7}\n"
        "</style>\n</head><body>\n"
        f"<div id=\"root\" data-composition-id=\"main\" data-start=\"0\" data-duration=\"{(t - 0.25):.1f}\" "
        f"data-width=\"1920\" data-height=\"1080\">\n{frag}\n</div>\n<script>\n"
        "function fmt(v){var n=Math.round(v);if(n>=1e6){var s=(n/1e6).toFixed(1);"
        "return s.replace(/\\.0$/,'')+'M'}return n.toLocaleString();}\n"
        "window.__timelines=window.__timelines||{};\n"
        f"const tl=gsap.timeline({{paused:true}});\n{tljs}\n"
        "window.__timelines['main']=tl; tl.seek(0);\n"
        "</script></body></html>\n"
    )
    OUT.write_text(html)
    print(f"wrote {OUT} ({total} sessions · {fmt(tok)} tokens · {(t - 0.25):.1f}s)")


if __name__ == "__main__":
    main()