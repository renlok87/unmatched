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

from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "hud-table-materials-codex" / "R3"

# name, source, x2 size, x2 margins (l, t, r, b), stretch
KIT = [
    ("T_Hud_TableCard", "hero-card-plate.png", (840, 368), (56, 56, 56, 56), "nine_slice"),
    ("T_Hud_TableStrip", "question-strip.png", (1200, 88), (24, 24, 24, 24), "nine_slice"),
    ("T_Hud_TableSlip", "pile-slip.png", (240, 64), (20, 20, 20, 20), "nine_slice"),
    ("T_Hud_TableDial", "hp-dial.png", (192, 192), (0, 0, 0, 0), "none"),
]


def main():
    margins = {}
    for name, src, size2, m2, stretch in KIT:
        im = Image.open(SRC / src).convert("RGBA")
        for scale, k in (("x2", 1), ("x1", 2)):
            size = (size2[0] // k, size2[1] // k)
            out = HERE / "kit" / scale / f"{name}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            im.resize(size, Image.LANCZOS).save(out)
            m = [v // k for v in m2]
            margins[f"kit/{scale}/{name}.png"] = {"left": m[0], "top": m[1], "right": m[2], "bottom": m[3],
                                                  "stretch": stretch}
    (HERE / "slice-margins.json").write_text(
        json.dumps({"unit": "physical px", "order": ["left", "top", "right", "bottom"], "files": margins},
                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("kit ok", len(margins))


if __name__ == "__main__":
    main()
