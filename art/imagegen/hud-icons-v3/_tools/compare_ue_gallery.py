#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Галерея UE (-S08IconGallery) против эталона Python: те же значки в те же моменты.

    python art/imagegen/hud-icons-v3/_tools/compare_ue_gallery.py <dir with icon-gallery-<mode>-<t>.png> [--reduced]
        [--size 64] [--out <sheet.png>] [--json <metrics.json>]

Ячейки находятся по цвету панели tag.background в снимке, значок вырезается так же, как его раскладывает
US08IconGalleryWidget (сверху по центру, поле 0,25 стороны), эталон — motion.compose() в момент
t_local = t mod (длина сценария + 400 мс). Метрика — средняя и 99-перцентиль |Δ| по каналам (0..255) в окне
значка; лист — «UE | эталон | |Δ|×4» по каждому значку и моменту.
"""
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import draw_icons as D  # noqa: E402
import icon_motion as M  # noqa: E402
import motion as MO  # noqa: E402

PAUSE_MS = 400.0
PANEL = np.array(D.PANEL[:3])


def cells(img):
    a = np.asarray(img.convert("RGB")).astype(int)
    mask = (np.abs(a - PANEL).sum(-1) <= 3)
    lab, n = ndimage.label(mask)
    boxes = []
    for sl in ndimage.find_objects(lab):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if h > 60 and w > 100:
            boxes.append((sl[0].start, sl[1].start, h, w))
    boxes.sort(key=lambda b: (round(b[0] / 20), b[1]))
    return boxes


def reference(c, icon, reduced, t, size):
    sched, total = M.demo_schedule(c, icon, reduced)
    local = t % (total + PAUSE_MS)
    a = M.Animator(c, icon, reduced)
    for tc, op in sched:
        if tc > local:
            break
        a.play(op, tc)
    pp, vis = a.pose(local)
    return MO.compose(a, pp, size) if vis else None, local


def main():
    args = sys.argv[1:]
    src = args[0]
    reduced = "--reduced" in args
    size = int(args[args.index("--size") + 1]) if "--size" in args else 64
    out = args[args.index("--out") + 1] if "--out" in args else os.path.join(src, "compare.png")
    jout = args[args.index("--json") + 1] if "--json" in args else os.path.join(src, "compare.json")
    c = M.load_contract()
    shots = sorted((int(m.group(1)), f) for f in os.listdir(src) if (m := re.match(r"icon-gallery-\w+-(\d+)\.png$", f)))
    pad = round(0.25 * size)
    rows, metrics = [], {}
    for t, f in shots:
        img = Image.open(os.path.join(src, f)).convert("RGB")
        boxes = cells(img)
        if len(boxes) != len(c["order"]):
            print(f"{f}: found {len(boxes)} cells, expected {len(c['order'])}")
            continue
        for (y, x, h, w), icon in zip(boxes, c["order"]):
            ref, local = reference(c, icon, reduced, t, size)
            wide = c["icons"][icon]["canvas_u"][0] > 32
            iw, ih = (2 * size if wide else size) + 2 * pad, size + 2 * pad
            # US08IconGalleryWidget: icon top padding = pad, horizontally centred; compose() adds pad around the canvas
            x0 = x + (w - (iw - 2 * pad)) // 2 - pad
            y0 = y + pad - pad
            ue = img.crop((x0, y0, x0 + iw, y0 + ih))
            bg = Image.new("RGBA", (iw, ih), tuple(PANEL) + (255,))
            if ref is not None:
                bg.alpha_composite(ref)
            rf = bg.convert("RGB")
            # кромка ячейки: всё, что вне ячейки, в UE — фон листа, в эталоне — панель; сравнение только внутри ячейки
            ue_a = np.asarray(ue).astype(int)
            rf_a = np.asarray(rf).astype(int)
            inside = np.zeros(ue_a.shape[:2], bool)
            iy0, ix0 = max(0, y - y0), max(0, x - x0)
            inside[iy0:min(ih, y + h - y0), ix0:min(iw, x + w - x0)] = True
            d = np.abs(ue_a - rf_a)[inside]
            m = {"mean": round(float(d.mean()), 3), "p99": int(np.percentile(d, 99)), "max": int(d.max()), "local_ms": round(local, 1)}
            metrics.setdefault(icon, {})[str(t)] = m
            rows.append((icon, t, ue, rf, Image.fromarray(np.clip(np.abs(ue_a - rf_a) * 4, 0, 255).astype(np.uint8))))
    with open(jout, "w", encoding="utf-8") as fh:
        json.dump({"src": src, "reduced": reduced, "size": size, "metrics": metrics}, fh, ensure_ascii=False, indent=1)
    worst = sorted(((m["p99"], m["mean"], i, t) for i, v in metrics.items() for t, m in v.items()), reverse=True)[:8]
    allm = [m["mean"] for v in metrics.values() for m in v.values()]
    print(f"pairs={len(allm)} mean|d|={np.mean(allm):.3f} worst p99: {worst}")
    # лист: по 4 момента на значок
    pick = sorted({t for _, t, *_ in rows})
    pick = [pick[i] for i in np.linspace(0, len(pick) - 1, min(4, len(pick))).round().astype(int)]
    by = {(i, t): (u, r, dd) for i, t, u, r, dd in rows}
    cw = max(r[2].width for r in rows) * 3 + 24
    ch = max(r[2].height for r in rows) + 22
    W, H = 220 + len(pick) * cw, 40 + len(c["order"]) * ch
    sheet = Image.new("RGB", (W, H), D.SHEET_BG[:3])
    sheet.paste(D.label(W, 30, f"UE | эталон | |Δ|×4 — {'reduced' if reduced else 'normal'}, {size} px; моменты {pick} мс", 14).convert("RGB"), (0, 4))
    for r, icon in enumerate(c["order"]):
        y = 40 + r * ch
        sheet.paste(D.label(210, 20, icon, 12).convert("RGB"), (4, y + ch // 2 - 10))
        for k, t in enumerate(pick):
            if (icon, t) not in by:
                continue
            u, rf, dd = by[(icon, t)]
            x = 220 + k * cw
            sheet.paste(u, (x, y)); sheet.paste(rf, (x + u.width + 4, y)); sheet.paste(dd, (x + 2 * u.width + 8, y))
            m = metrics[icon][str(t)]
            sheet.paste(D.label(cw, 16, f"t={t} local={m['local_ms']} mean={m['mean']} p99={m['p99']}", 10).convert("RGB"), (x, y + u.height + 2))
    sheet.save(out, optimize=True)
    print(out)


if __name__ == "__main__":
    main()
