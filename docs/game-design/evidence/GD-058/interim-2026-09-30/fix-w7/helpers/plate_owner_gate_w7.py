"""Волна 7 (fix-w7): гейт «плашка у своей фигуры» и статус атаки Medusa по трассам хоста.

Переиспользует helpers/plate_owner_proximity.py акта (прямоугольный зазор bbox плашки к bbox фигур, 1920x1080),
только корень — fix-w7/packaged. Плюс из той же трассы: последняя строка `HUD plate content fighter=f-0-hero`
(статус должен быть RANGED — Medusa дальний боец, scraped attack=range) и строка `PLATE ... placement= bound=`.
Только чтение трасс. Запуск из корня репо:
  python docs/game-design/evidence/GD-058/interim-2026-09-30/fix-w7/helpers/plate_owner_gate_w7.py [packaged-root]
Код выхода 0 — все прогоны: ближайшая фигура = владелец и статус RANGED; иначе 1.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "helpers"))
import plate_owner_proximity as pop  # noqa: E402

ROOT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, "..", "packaged")


def main():
    pop.ROOT = ROOT
    os.makedirs(os.path.join(ROOT, "analysis"), exist_ok=True)
    pop.main()  # writes ROOT/analysis/plate-owner-proximity.json
    path = os.path.join(ROOT, "analysis", "plate-owner-proximity.json")
    data = json.load(open(path, encoding="utf-8"))
    ok = True
    for row in data["runs"]:
        trace = os.path.join(ROOT, row["run"], "phase2-client-host.trace.log")
        content, placement = None, None
        with open(trace, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.search(r"HUD plate content fighter=f-0-hero .*?statuses=(.*?) teamSlot=", line)
                if m:
                    content = m.group(1).strip()
                m = re.search(r"\bPLATE fighter=f-0-hero .*?placement=(\S+) ring=(-?\d+) gap=(\d+) .*?bound=(\d)", line)
                if m:
                    placement = {"placement": m.group(1), "ring": int(m.group(2)), "gap": int(m.group(3)),
                                 "bound": m.group(4) == "1"}
        row["medusaPlateStatuses"] = content
        row["medusaRanged"] = bool(content) and "RANGED" in content.split("|")[-1]
        row["clientPlacement"] = placement
        row["pass"] = bool(row["nearestIsOwner"] and row["medusaRanged"])
        ok = ok and row["pass"]
        print(f"{row['run']}: nearestIsOwner={row['nearestIsOwner']} statuses={content!r} placement={placement}")
    data["note"] = ("волна 7: rect gap плашка->bbox фигур (хост 1920x1080) + статус плашки Medusa; "
                    "pass = ближайшая фигура — владелец и RANGED")
    data["pass"] = ok and len(data["runs"]) > 0
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("PASS" if data["pass"] else "FAIL")
    return 0 if data["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
