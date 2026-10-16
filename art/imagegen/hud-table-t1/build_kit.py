"""HUD "Стол" T1 (docs/game-design/hud-redesign/03-CONCEPT.md §5.1, 06 §7): the box-canon skins as a 9-slice kit for
tools/art/hud_skins_import.py --package=art/imagegen/hud-table-t1 --with-hud.

Sources: art/imagegen/hud-table-materials-codex/R3/*.png (Codex ImageGen plates, no text). Output kit/x1, kit/x2 and
slice-margins.json in the contract of the HUD v2 kit (px per file, stretch nine_slice | none). Keys after the import:
  T_Hud_TableCard  -> hud.table.card   (hero card plate: cream die-cut edge + meander band; margins 28 / 56)
  T_Hud_TableStrip -> hud.table.strip  (the one-line prompt / turn strip plate; 12 / 24)
  T_Hud_TableSlip  -> hud.table.slip   (paper slip of a pile count; 10 / 20)
  T_Hud_TableDial  -> hud.table.dial   (health dial, drawn as an image; 96 / 192)
"""
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "hud-table-materials-codex" / "R3"

# name, source, x2 size, x2 margins (l, t, r, b), stretch, gilt rim px at x2 (0 = keep the plate as painted)
KIT = [
    ("T_Hud_TableCard", "hero-card-plate.png", (840, 368), (56, 56, 56, 56), "nine_slice", 7),
    ("T_Hud_TableStrip", "question-strip.png", (1200, 88), (24, 24, 24, 24), "nine_slice", 6),
    ("T_Hud_TableSlip", "pile-slip.png", (240, 64), (20, 20, 20, 20), "nine_slice", 0),
    ("T_Hud_TableDial", "hp-dial.png", (192, 192), (0, 0, 0, 0), "none", 0),
]

# the gilt bevel from the outside in (blind review 2026-10-16: the thick cream die-cut edge read as a mobile casual
# frame): a dark bronze outline, the lit gold, the gold body, a dark inner line; the rest of the old cream band -> navy
GILT = [(74, 54, 26), (232, 196, 120), (212, 170, 92), (186, 142, 70), (158, 118, 56), (116, 84, 38), (44, 34, 22)]
NAVY = (21, 28, 36)


def regild(im, keep):
    """The cream rim (bright pixels between the transparent outside and the dark plate) -> a `keep` px gilt bevel along
    the outer edge, the band's inner part -> the plate's navy. The outer silhouette (and so the 9-slice) stays."""
    if keep <= 0:
        return im
    px = im.load()
    w, h = im.size
    outside = im.getchannel("A").point(lambda a: 255 if a < 128 else 0)
    # a 1 px transparent frame so a rim that touches the file edge still has an outside
    frame = Image.new("L", (w + 2, h + 2), 255)
    frame.paste(outside, (1, 1))
    grown = frame
    dist = {}
    for k in range(1, 40):
        grown = grown.filter(ImageFilter.MaxFilter(3))
        g = grown.crop((1, 1, w + 1, h + 1)).load()
        changed = False
        for y in range(h):
            for x in range(w):
                if (x, y) in dist or g[x, y] == 0:
                    continue
                r, gg, b, a = px[x, y]
                if a < 128:
                    continue
                if (r + gg + b) / 3 < 120:  # reached the dark plate
                    continue
                dist[(x, y)] = k
                changed = True
        if not changed:
            break
    for (x, y), k in dist.items():
        a = px[x, y][3]
        if k <= keep:
            c = GILT[min(len(GILT) - 1, round((k - 1) * (len(GILT) - 1) / max(1, keep - 1)))]
        else:
            c = NAVY
        px[x, y] = (c[0], c[1], c[2], a)
    return im


def main():
    margins = {}
    for name, src, size2, m2, stretch, gilt in KIT:
        im = regild(Image.open(SRC / src).convert("RGBA").resize(size2, Image.LANCZOS), gilt)
        for scale, k in (("x2", 1), ("x1", 2)):
            size = (size2[0] // k, size2[1] // k)
            out = HERE / "kit" / scale / f"{name}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            (im if k == 1 else im.resize(size, Image.LANCZOS)).save(out)
            m = [v // k for v in m2]
            margins[f"kit/{scale}/{name}.png"] = {"left": m[0], "top": m[1], "right": m[2], "bottom": m[3],
                                                  "stretch": stretch}
    (HERE / "slice-margins.json").write_text(
        json.dumps({"unit": "physical px", "order": ["left", "top", "right", "bottom"], "files": margins},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("kit ok", len(margins))


if __name__ == "__main__":
    main()
