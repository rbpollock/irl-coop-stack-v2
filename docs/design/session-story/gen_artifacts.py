#!/usr/bin/env python3
"""gen_artifacts.py — draw 'artifact cards' (summaries of the .md docs) as
thumbnail PNGs into render/art/, for the recap grid. Deterministic, local.
"""
import json, re, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
STATS = ROOT / "stats.json"
ART = ROOT / "render" / "art"

_FONT = None
for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
    if Path(cand).exists():
        _FONT = cand
        break


def font(px):
    try:
        return ImageFont.truetype(_FONT, px) if _FONT else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def first_summary(md: Path):
    txt = md.read_text(errors="ignore")
    title = ""
    for ln in txt.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            title = s.lstrip("#").strip()
            break
    body = " ".join(
        s for s in txt.splitlines()
        if s.strip() and not s.lstrip().startswith(("#", "`", "-", "*", ">", "="))
    )
    return (title or md.stem.replace("_", " ").title()), re.sub(r"\s+", " ", body).strip()[:280]


def draw(doc, title, body, out):
    W, H = 560, 760
    img = Image.new("RGB", (W, H), "#12182a")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 126], fill="#273956")
    d.rectangle([0, 126, W, 152], fill="#1e2b44")
    t = title if d.textlength(title, font=font(42)) <= W - 44 else title[:30] + "…"
    d.text((22, 30), t, font=font(40), fill="#ecf2fb")
    d.text((28, 96), doc, font=font(18), fill="#8fa1c0")
    y = 212
    for ln in textwrap.wrap(body, width=50)[:6]:
        d.text((28, y), ln, font=font(16), fill="#c8d3e6")
        y += 42
    img.save(out)


def main():
    stats = json.loads(STATS.read_text())
    repo = ROOT
    while repo != repo.parent and not (repo / ".git").exists():
        repo = repo.parent
    ART.mkdir(parents=True, exist_ok=True)
    made = []
    for i, p in enumerate(stats.get("artifacts", [])):
        pth = repo / p
        if not pth.exists() or pth.suffix.lower() != ".md":
            continue
        title, body = first_summary(pth)
        out = ART / f"art{i}.png"
        draw(pth.stem, title, body, out)
        made.append(str(out))
    print(f"wrote {len(made)} cards:")
    for m in made:
        print("  ", m)


if __name__ == "__main__":
    main()