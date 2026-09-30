# -*- coding: utf-8 -*-
"""Лист «look-dev r2 (5c-B2) против r3 (волна 6) в игре» на K2 2,5× Cobble, хост, те же позиции и камера.
Только наглядность для панели: поза Idle в двух прогонах разная, поэтому это не замер."""
import hashlib, json, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = "C:/Users/ren/WebstormProjects/unmached/unmached/"
NEW = ROOT + "docs/game-design/evidence/GD-058/interim-2026-09-30/packaged/k2-zoom-2.5/cobble-5x6/run-20260930-211942/phase2-board-host-1920x1080.png"
OLD = ROOT + "docs/game-design/evidence/ART-018/long-k2-2026-09-30/k2-zoom-2.5/cobble-5x6/run-20260930-164602/phase2-board-host-1920x1080.png"
CON = ROOT + "art/imagegen/hero-quality-v1/{h}/{h}-front.png"
OUT = ROOT + "docs/game-design/evidence/GD-058/interim-2026-09-30/packaged/analysis/lookdev-r3-vs-r2-k2-2.5.jpg"
# (герой, центр подставки на экране из SHOT fighter, кроп w,h, сдвиг вверх)
FIG = [("medusa", "Medusa f-0-hero (P1)", (960, 601), 260, 300),
       ("harpy", "Harpy f-0-sk0 (P1)", (1343, 601), 300, 300),
       ("king-arthur", "King Arthur f-1-hero (P2)", (960, 944), 260, 240),
       ("merlin", "Merlin f-1-sk0 (P2)", (1373, 944), 260, 240)]
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
new, old = Image.open(NEW).convert("RGB"), Image.open(OLD).convert("RGB")
S = 300
rows = []
for h, label, (cx, cy), w, hh in FIG:
    box = (cx - w // 2, max(0, cy - hh + 40), cx + w // 2, min(985, cy + 40))
    a = old.crop(box); b = new.crop(box)
    c = Image.open(CON.format(h=h)).convert("RGB"); c.thumbnail((S, S))
    rows.append((label, box, a, b, c))
W = 3 * S + 40; H = len(rows) * (S + 26) + 30
sheet = Image.new("RGB", (W, H), (24, 24, 28)); d = ImageDraw.Draw(sheet)
try:
    f = ImageFont.truetype("arial.ttf", 14)
except Exception:
    f = ImageFont.load_default()
d.text((8, 6), "look-dev r2 (5c-B2, ART-018) | r3 (волна 6, набор B) | концепт front — K2 2.5x Cobble, хост; поза Idle разная — не замер", fill=(230, 230, 230), font=f)
y = 30
for label, box, a, b, c in rows:
    for i, im in enumerate((a, b, c)):
        im2 = im.copy(); im2.thumbnail((S, S), Image.NEAREST if i < 2 else Image.LANCZOS)
        sheet.paste(im2, (10 + i * (S + 10), y + 20))
    d.text((10, y + 2), f"{label}  crop {box}", fill=(255, 220, 130), font=f)
    y += S + 26
sheet.save(OUT, quality=92)
print(json.dumps({"out": OUT, "sha256": sha(OUT), "new": {"path": NEW, "sha256": sha(NEW)}, "old": {"path": OLD, "sha256": sha(OLD)},
                  "crops": {r[0]: r[1] for r in rows}}, ensure_ascii=False, indent=1))
