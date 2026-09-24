#!/usr/bin/env python3
"""build_wrapped.py — irl.coop recap, portrait 1080x1920, humanized voice.
Cover -> six pillars (time+tokens + a plain line) -> real product screenshots
-> wrap. Deterministic; rendered to MP4 by HyperFrames.
"""
import json
import html as _h
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATS = ROOT / "stats.json"
OUT = ROOT / "render" / "index.html"
PAL = ["#0d1526", "#1a2442", "#233043", "#1b122f", "#0f2a24", "#33210f",
       "#1a1232", "#17282f", "#163029", "#0a0d16"]

# human lines, one per vertical
LINE = {
    "identity": "one realm, every door",
    "edge": "routes and a wildcard done well",
    "cache": "fast, shared, tidy",
    "data": "one data store, rows scoped right",
    "mail": "mail under your own roof",
    "workflow": "jobs that survive a jolt",
}
HARD = {
    "identity": "the hard part: keep the broker honest",
    "edge": "certs and live rewrites, by hand",
    "cache": "the spend hides in the cache",
    "data": "the embedding war, settled at 1024",
    "mail": "OIDC on a mail server is fiddly",
    "workflow": "sidecars that fix themselves",
}


def esc(s):
    return _h.escape(str(s or "")[:200])


def build(cards):
    frag, tl = [], []
    durs = [c.get("d", 2.3) for c in cards]
    starts = []
    a = 0.0
    for dd in durs:
        starts.append(a)
        a += dd
    for i, c in enumerate(cards):
        st, dur = starts[i], durs[i]
        bg = PAL[i % len(PAL)]
        if c["kind"] == "grid":
            cells = "".join(
                f'<div class="g" id="g{i}_{j}"><img src="{esc(s)}"></div>' for j, s in enumerate(c["items"]))
            body = f'<div class="cap">{esc(c.get("cap",""))}</div><div class="grid">{cells}</div>'
        elif c["kind"] == "list":
            lis = "".join(f'<div class="li">{esc(x)}</div>' for x in c.get("items", []))
            body = f'<div class="title">{esc(c.get("title",""))}</div><div class="rows">{lis}</div>'
        elif c.get("img"):
            body = f'<div class="showcase"><img src="{esc(c["img"])}"></div>'
        else:
            big = c.get("big", "")
            body = f'<div class="big">{esc(big)}</div>'
            if c.get("sub"):
                body += f'<div class="sub">{esc(c["sub"])}</div>'
            if c.get("foot"):
                body += f'<div class="foot">{esc(c["foot"])}</div>'
        frag.append(
            f'<div class="clip slide" id="sn{i}" data-start="{st:.2f}" data-duration="{dur:.2f}" '
            f'data-track-index="{i}" style="background:{bg}"><div class="kick">{esc(c.get("kick",""))}'
            f'</div>{body}</div>')
        tl.append(f'tl.set("#sn{i}",{{autoAlpha:0}});')
        tl.append(f'tl.set("#sn{i}",{{autoAlpha:1}},{st:.2f});')
        tl.append(f'tl.set("#sn{i}",{{autoAlpha:0}},{st + dur:.2f});')
        if c["kind"] == "grid":
            for j in range(len(c["items"])):
                tl.append(f'tl.fromTo("#g{i}_{j}",{{opacity:0,scale:0.94}},'
                          f'{{opacity:1,scale:1,duration:0.3}},{st + 0.2 + j * 0.09:.2f});')
        else:
            tl.append(f'tl.fromTo("#sn{i} .big",{{opacity:0,y:30}},'
                      f'{{opacity:1,y:0,duration:0.32}},{st + 0.1:.2f});')
            tl.append(f'tl.fromTo("#sn{i} .sub",{{opacity:0}},{{opacity:1,duration:0.3}},{st + 0.5:.2f});')
            tl.append(f'tl.fromTo("#sn{i} .foot",{{opacity:0}},{{opacity:1,duration:0.3}},{st + 0.9:.2f});')

    tljs = "\n".join(tl)
    frag_html = "\n".join(frag)
    html = (
        "<!doctype html><html><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=1080,height=1920\">"
        "<link href=\"https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700;900&display=swap\" rel=\"stylesheet\">"
        "<script src=\"https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js\"></script>"
        "<style>"
        "body{margin:0;overflow:hidden;width:1080px;height:1920px;background:#07090f;"
        "font-family:'Space Grotesk',sans-serif;color:#f4f7fc}"
        ".slide{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;"
        "padding:120px 92px;opacity:0}"
        ".kick{font-size:24px;letter-spacing:.3em;text-transform:uppercase;color:#8fa2c2;margin-bottom:44px}"
        ".big{font-size:150px;font-weight:900;letter-spacing:-.045em;line-height:.98;color:#f4f7fc}"
        ".sub{font-size:42px;margin-top:30px;color:#d9e6f6;line-height:1.25}"
        ".foot{font-size:30px;margin-top:60px;color:#9fb2cd;line-height:1.45}"
        ".cap{font-size:44px;font-weight:700;margin-bottom:30px}"
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}"
        ".g{opacity:0;scale:.94}"
        ".g img{width:100%;height:auto;border-radius:12px;border:1px solid rgba(255,255,255,.12)}"
        ".showcase{display:flex;justify-content:center;align-items:center;margin-top:20px}"
        ".showcase img{width:100%;max-width:940px;height:auto;border-radius:12px}"
        ".title{font-size:60px;font-weight:700;margin-bottom:34px}"
        ".rows{display:flex;flex-direction:column;gap:26px}"
        ".li{font-size:40px;line-height:1.25;color:#eef3fb}"
        ".li:before{content:'';display:inline-block;width:12px;height:12px;border-radius:50%;"
        "background:#5eead4;margin-right:22px;vertical-align:middle}"
        "</style></head><body>"
        f"<div id=\"rp\" data-composition-id=\"main\" data-start=\"0\" "
        f"data-duration=\"{a:.1f}\" data-width=\"1080\" data-height=\"1920\">{frag_html}</div>"
        "<script>window.__timelines=window.__timelines||{};const tl=gsap.timeline({paused:true});\n"
        + tljs +
        "\nwindow.__timelines['main']=tl; tl.seek(0);</script></body></html>"
    )
    OUT.write_text(html)
    print(f"wrote {OUT} · {len(cards)} slides · {a:.1f}s")


if __name__ == "__main__":
    stats = json.loads(STATS.read_text())
    verts = stats.get("vertical", [])
    v = {s.get("name"): s for s in verts}
    shots = ["art/needs-effers.png", "art/calls.png", "art/dashboard.png", "art/cinny.png"]

    idn, edg, wf = v.get("identity") or {}, v.get("edge") or {}, v.get("workflow") or {}
    cards = [
        dict(kind="cover", kick="our own stack", big="irl.coop",
             sub="we built the whole thing ourselves",
             foot="identity · edge · mail · data · cache · workflows", d=2.6),

        dict(kind="stat", kick="start with the door", big="one identity",
             sub="everyone logs in through the same realm",
             foot="one sign-in, for every door", d=2.2),

        dict(kind="stat", kick="the part nobody really sees", big="it was hard",
             sub="identity, the edge, and the moves — that was the grind",
             foot="doesn't look like much; a lot happened underneath", d=2.4),

        dict(kind="stat", kick="where the energy really went", big="the spread",
             sub=(f"identity {idn.get('hours',0)}h / {idn.get('tokens','0')} · "
                  f"edge {edg.get('hours',0)}h / {edg.get('tokens','0')} · "
                  f"workflow {wf.get('hours',0)}h / {wf.get('tokens','0')}"),
             foot="the measured spread, no more", d=2.8),

        dict(kind="stat", kick="the ones that stayed quiet", big="cache · data · mail",
             sub="the work still got done, it just didn't shout",
             foot="no headlines, same roof", d=2.4),

        dict(kind="cover", kick="proof, not promise", big="the app lives",
             sub="actual screens", foot="", d=1.7),
        dict(kind="grid", kick="for real", cap="running as you watch",
             items=shots, d=3.6),

        dict(kind="shot", kick="what it costs, at every size", title="",
             sub="", d=4.6, img="art/pricing.svg"),
        dict(kind="list", kick="what's left before launch", title="the road to live",
             items=[
                 "money — a non-custodial vault, then the treasury",
                 "group ops — the group model, coop as first tenant",
                 "calling — the phone rail, a number that's ours",
                 "pen-test the isolation before anyone trusts it",
                 "booking, calendar, contacts, workflow",
             ], d=5.4),

        dict(kind="end", kick="the point", big="irl.coop",
             sub="built together, stays ours", foot="", d=2.3),
    ]
    build(cards)