"""Наложить 2D-проекции костей (из rig_deform_probe.py) на рендеры и собрать лист.

python tools/tripo-pipeline/anim/overlay_bones.py <out_dir> <label>
Пишет <label>-sheet.png: рендеры покоя и тестовых поз с костями (жёлтые
отрезки, голова кости — красная точка). Требует Pillow в системном Python.
"""
import json
import os
import sys

from PIL import Image, ImageDraw


def main():
    out_dir, label = sys.argv[1], sys.argv[2]
    with open(os.path.join(out_dir, f"{label}-bones2d.json"), encoding="utf-8") as f:
        frames = json.load(f)
    tiles = []
    for name, fr in frames.items():
        im = Image.open(os.path.join(out_dir, fr["png"])).convert("RGB")
        d = ImageDraw.Draw(im)
        for s in fr["bones"]:
            d.line([tuple(s["a"]), tuple(s["b"])], fill=(255, 220, 0), width=3)
            x, y = s["a"]
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(230, 30, 30))
        d.rectangle([0, 0, im.width, 34], fill=(0, 0, 0))
        d.text((8, 8), f"{label}: {name}", fill=(255, 255, 255))
        tiles.append(im)
    cols = 4
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), (30, 30, 30))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * w, (i // cols) * h))
    scale = min(1.0, 2400 / sheet.width)
    if scale < 1:
        sheet = sheet.resize((int(sheet.width * scale), int(sheet.height * scale)))
    out = os.path.join(out_dir, f"{label}-sheet.png")
    sheet.save(out)
    print("SHEET_OK", out, sheet.size)


if __name__ == "__main__":
    main()
