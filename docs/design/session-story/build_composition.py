#!/usr/bin/env python3
"""build_composition.py — turn the Jev-scored storyboard into a HyperFrames HTML
composition (render skill pipeline).

Deterministic, no fetches, no noise.
"""
import json
import html as _h
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "storyboard.json"
OUT = ROOT / "render" / "index.html"
W, H = 1920, 1080
DUR = 9.0
ACTS = [
    ("Act I · Setup", "#6ab6ff"),
    ("Act II · Central tension", "#ffd06a"),
    ("Act III · Resolution", "#8fd6a6"),
]


def esc(s):
    return _h.escape(str(s or "")[:56])


def main():
    data = json.loads(SRC.read_text())
    beats = data.get("beats", [])
    days = data.get("days", 45)
    total = len(beats)
    ordered = sorted(beats, key=lambda b: (b.get("date", ""), b.get("title", "")))

    clips, tl = [], []
    for i, b in enumerate(ordered):
        act = str(b.get("act", "III")).replace("Act ", "").strip()
        ab = {"I": 0, "II": 1, "III": 2}[act if act in {"I", "II", "III"} else "III"]
        color = ACTS[ab][1]
        mag = b.get("magnitude", 0) or 0
        r = min(24, max(4, 6 + mag / 3e6))
        conf = min(1.0, b.get("confidence", 0.5))
        story = bool(b.get("story"))
        op = round(0.25 + 0.62 * conf, 2) if story else 0.16
        x = 190 + (i + 0.5) / max(1, total) * (W - 390)
        y = 360 + (i % 4) * 86
        ts = round(1.1 + i * 6.4 / max(1, total), 3)
        clips.append(
            f'<div class="clip dot" id="d{i}" style="left:{x:.0f}px;top:{y:.0f}px;'
            f'width:{2*r:.0f}px;height:{2*r:.0f}px;background:{color};opacity:{op}"></div>'
        )
        tl.append(f'tl.fromTo("#d{i}",{{scale:0,opacity:0}},{{scale:1,opacity:{op},duration:0.4}},{ts});')
        if story:
            clips.append(
                f'<div class="clip cap" id="c{i}" style="left:{x:.0f}px;top:{y-20:.0f}px">'
                f'{esc(b["title"])}<span class="act_ey">{esc(b["act"])}</span></div>')
            tl.append(f'tl.fromTo("#c{i}",{{opacity:0}},{{opacity:1,duration:0.4}},{round(ts+0.2,3)});')

    act_cards = ""
    for ab, (title, color) in enumerate(ACTS):
        st = 1.5 + ab * 2.3
        tag = ["a0", "a1", "a2"][ab]
        act_cards += (f'<div class="clip act" id="{tag}" data-start="{st:.1f}" data-duration="2.0" '
                      f'data-track-index="{ab+1}" style="color:{color};opacity:0">{esc(title)}</div>')
        tl.append(f'tl.fromTo("#{tag}",{{opacity:0}},{{opacity:1,duration:0.5}},{st});')

    toks = sum((b.get("magnitude", 0) or 0) for b in beats)
    hunks = "".join(clips)
    tlj = "\n".join(tl)

    html = (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"UTF-8\">\n"
        "<meta name=\"viewport\" content=\"width=1920, height=1080\">\n"
        "<script src=\"https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js\"></script>\n"
        "<style>\n"
        "*{margin:0;padding:0;box-sizing:border-box}\n"
        "html,body{width:1920px;height:1080px;overflow:hidden;background:#0a0c12;\n"
        " font-family:Inter,ui-sans-serif,system-ui,sans-serif}\n"
        "#root{position:absolute;inset:0}\n"
        ".clip{position:absolute;will-change:opacity,transform}\n"
        ".dot{border-radius:50%;border:1px solid rgba(255,255,255,.5)}\n"
        ".cap{color:#e6eaf1;font-size:16px;white-space:nowrap;pointer-events:none}\n"
        ".cap .act_ey{color:#8fa3b8;font-size:12px;margin-left:10px}\n"
        ".act{top:170px;left:90px;font-size:46px;font-weight:700;letter-spacing:-.01em}\n"
        "</style>\n</head>\n<body>\n"
        f"<div id=\"root\" data-composition-id=\"main\" data-start=\"0\" data-duration=\"{DUR}\" "
        f"data-width=\"1920\" data-height=\"1080\">\n"
        f"<h1 id=\"hd\" class=\"clip\" data-start=\"0.2\" data-duration=\"8.6\" data-track-index=\"0\" "
        f"style=\"top:66px;left:90px;font-size:56px;font-weight:700;color:#eef2f7;opacity:0\">"
        f"{total} sessions · {days} days</h1>\n"
        f"{act_cards}\n{hunks}\n"
        f"<div class=\"clip\" id=\"ft\" data-start=\"7.3\" data-duration=\"1.8\" data-track-index=\"9\" "
        f"style=\"left:90px;bottom:70px;color:#7f93ab;font-size:24px;opacity:0\">"
        f"{toks:,} model tokens · size &prop; work, glow &prop; Jev confidence</div>\n"
        f"</div>\n<script>\n"
        f"const tl = gsap.timeline({{paused:true}});\n"
        f"tl.fromTo(\"#hd\",{{opacity:0,y:16}},{{opacity:1,y:0,duration:0.7}},0.2);\n{tlj}\n"
        f"tl.fromTo(\"#ft\",{{opacity:0}},{{opacity:1,duration:0.4}},7.4);\n"
        f"window.__timelines = window.__timelines || {{}};\n"
        f"window.__timelines[\"main\"] = tl;\ntl.seek(0);\n"
        "</script>\n</body></html>\n"
    )
    OUT.write_text(html)
    print(f"wrote {OUT} ({total} beats, {toks:,} tokens)")


if __name__ == "__main__":
    main()