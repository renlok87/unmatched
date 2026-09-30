"""Плашка выбранной фигуры: к какой фигуре она ближе на экране (волна 6B, находка слепого зрителя).

Читает из трасс хоста последние строки `SHOT plate` и `SHOT figure` (экранные bbox, 1920x1080)
и считает для плашки прямоугольное расстояние до bbox каждой фигуры. Только чтение трасс, без UE.
Запуск из корня репо: python docs/game-design/evidence/GD-058/interim-2026-09-30/helpers/plate_owner_proximity.py
"""
import glob
import json
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "packaged")
NAMES = {"f-0-hero": "Medusa", "f-0-sk0": "Harpy 1", "f-0-sk1": "Harpy 2", "f-0-sk2": "Harpy 3",
         "f-1-hero": "King Arthur", "f-1-sk0": "Merlin"}
BOX = r"\((\d+),(\d+),(\d+),(\d+)\)"


def rect_gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return round((dx * dx + dy * dy) ** 0.5, 1)


def main():
    rows = []
    patterns = ["k1/*/run-*/phase2-client-host.trace.log", "k1-probe32/*/run-*/phase2-client-host.trace.log",
                "k2-zoom-*/*/run-*/phase2-client-host.trace.log"]
    for pat in patterns:
        for trace in sorted(glob.glob(os.path.join(ROOT, pat))):
            plate, figures = None, {}
            with open(trace, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    m = re.search(r"SHOT plate fighter=(\S+) bbox=" + BOX, line)
                    if m:
                        plate = (m.group(1), tuple(int(v) for v in m.groups()[1:]))
                    m = re.search(r"SHOT figure fighter=(\S+) bbox=" + BOX, line)
                    if m:
                        figures[m.group(1)] = tuple(int(v) for v in m.groups()[1:])
            if not plate:
                continue
            owner, pbox = plate
            gaps = {fid: rect_gap(pbox, fb) for fid, fb in figures.items()}
            nearest = min(gaps, key=gaps.get)
            rows.append({
                "run": os.path.relpath(os.path.dirname(trace), ROOT).replace("\\", "/"),
                "owner": NAMES.get(owner, owner),
                "plateBbox": pbox,
                "gapToOwnerPx": gaps.get(owner),
                "nearestFigure": NAMES.get(nearest, nearest),
                "gapToNearestPx": gaps[nearest],
                "nearestIsOwner": nearest == owner or gaps[nearest] == gaps.get(owner),
                "gapsPx": {NAMES.get(k, k): v for k, v in sorted(gaps.items())},
            })
    out = os.path.join(ROOT, "analysis", "plate-owner-proximity.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"note": "screen-space rect gap plate->figure bbox, host 1920x1080; not a gate", "runs": rows},
                  fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    for r in rows:
        print(f"{r['run']}: owner={r['owner']} gap={r['gapToOwnerPx']} nearest={r['nearestFigure']} "
              f"gap={r['gapToNearestPx']} ok={r['nearestIsOwner']}")


if __name__ == "__main__":
    main()
