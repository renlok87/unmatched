# -*- coding: utf-8 -*-
"""Повтор метода ART-012 clip-pixel-diff-k3 на K3 набора B (герои v2 + поднос, сборка f8accb3d).
K3 присоединившегося: s09-combat-result (до HitReact первого боя) против s09-damage-combat (внутри HitReact 0,417 с).
Область фигуры = проекция цилиндра r 0..16 uu, z 6..60 uu вокруг бойца камерой SHOT, дилатация 3 px,
без прямоугольников UMG (SHOT widget/panel/damage/icon) обоих кадров. Метрика: средний max|ΔRGB| и доля пикселей с max|ΔRGB| > 24."""
import json, math, re, sys, hashlib
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
ROOT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
sys.path.insert(0, str(ROOT / "tools/art/qa010"))
from qa010lib.trace import parse_trace
from qa010lib.projection import camera_from_shot
EV = ROOT / "docs/game-design/evidence/GD-058/interim-2026-09-30/packaged/k3"
BOX = re.compile(r"\(?\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)\)?")

def rects(shot):
    out = []
    for w in shot.widgets:
        b = w.get("bbox")
        if b and (m := BOX.match(str(b))) and w.get("visible", "1") == "1":
            out.append(tuple(float(v) for v in m.groups()))
    for p in shot.panels:
        if p.get("visible"):
            out.append(p["bbox"])
    for d in shot.damage:
        out.append(d["bbox"])
    if shot.icon is not None and isinstance(shot.icon.value, dict) and shot.icon.value.get("bbox"):
        out.append(shot.icon.value["bbox"])
    return out

def fig_mask(cam, world, size):
    pts = []
    for z in (6.0, 60.0):
        for a in range(0, 360, 15):
            r = 16.0
            p = cam.project((world[0] + r * math.cos(math.radians(a)), world[1] + r * math.sin(math.radians(a)), world[2] + z))
            if p: pts.append((p[0], p[1]))
    if len(pts) < 3:
        return None
    # выпуклая оболочка
    pts = sorted(set(pts))
    def cross(o, a, b): return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], p) <= 0: hi.pop()
        hi.append(p)
    hull = lo[:-1] + hi[:-1]
    im = Image.new("L", size, 0); ImageDraw.Draw(im).polygon(hull, fill=255)
    im = im.filter(ImageFilter.MaxFilter(7))
    return np.asarray(im) > 127

res = {"schema": "unmatched.t5cb2-clip-pixel-diff/1", "status": "измерено (пиксели packaged-live, не приёмка)",
       "method": __doc__.strip().split("\n", 1)[1], "set": "GD-058 interim, набор B (-ArtPreviewHeroesV2 -ArtPreviewDiorama)", "boards": {}}
for bdir in sorted(EV.iterdir()):
    run = next(bdir.glob("combat-*"))
    tr = parse_trace(run / "combat-client-joiner.trace.log")
    text = (run / "combat-client-joiner.trace.log").read_text(encoding="utf-8", errors="replace").splitlines()
    before = tr.find_shot("s09-combat-result.png"); after = tr.find_shot("s09-damage-combat.png")
    ia = np.asarray(Image.open(run / "joiner/s09-combat-result.png").convert("RGB")).astype(np.int16)
    ib = np.asarray(Image.open(run / "joiner/s09-damage-combat.png").convert("RGB")).astype(np.int16)
    h, w = ia.shape[:2]
    excl = np.zeros((h, w), bool)
    for r in rects(before) + rects(after):
        x0, y0, x1, y1 = [int(round(v)) for v in r]
        excl[max(0, y0):max(0, y1), max(0, x0):max(0, x1)] = True
    cam = camera_from_shot(after, 35.0)
    diff = np.abs(ia - ib).max(axis=2)
    # HitReact этого боя: первая строка anim HitReact после запроса combat-result и до запроса damage-combat
    rq = [i for i, l in enumerate(text) if "SHOT request file=s09-combat-result.png" in l or "SHOT request file=s09-damage-combat.png" in l]
    hit = None
    if len(rq) >= 2:
        for l in text[rq[0]:rq[1] + 1]:
            if "ARTPREVIEW anim" in l and "clip=HitReact" in l:
                m = re.search(r"fighter=(\S+).*seq=(-?\d+)", l); hit = {"fighter": m.group(1), "seq": int(m.group(2))}; break
    lunge = None
    for l in text[:rq[1] + 1] if len(rq) >= 2 else []:
        if "ARTPREVIEW anim" in l and "clip=LungeAttack" in l:
            m = re.search(r"fighter=(\S+).*seq=(-?\d+)", l); lunge = {"fighter": m.group(1), "seq": int(m.group(2))}
    figs = {}
    for f in after.fighters:
        if not f.alive: continue
        m = fig_mask(cam, f.world, (w, h))
        if m is None: continue
        m &= ~excl
        n = int(m.sum())
        if n == 0: continue
        d = diff[m]
        figs[f.fighter_id] = {"px": n, "meanAbs": round(float(d.mean()), 2), "shareOver24": round(float((d > 24).mean()), 4)}
    res["boards"][bdir.name] = {"run": str(run.relative_to(ROOT)).replace("\\", "/"),
        "frames": {"before": f"joiner/s09-combat-result.png frame {before.request_frame}", "after": f"joiner/s09-damage-combat.png frame {after.request_frame}"},
        "fighters": figs, "hitReactOfThisCombat": hit, "lastLungeBeforeAfterFrame": lunge}
out = ROOT / "docs/game-design/evidence/GD-058/interim-2026-09-30/packaged/analysis/clip-pixel-diff-k3.json"
out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(res["boards"], ensure_ascii=False, indent=1))
