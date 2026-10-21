"""Build the Tripo queue for the next credit window from the map-kit status files and acceptance cards.

    python tools/mapkits/queue.py [--out docs/art-pipeline/map-kits/QUEUE-2026-10-27.md] [--date 2026-10-27]

Every prop that is not accepted gets one line. The route comes from the stage and the card's rework_fix_list tools:
regen (rejected, a never generated prop, or a fix on the Tripo source shape) = 100 generation + 20 texture 4K + 5 PBR;
retexture (only texture fixes on the Tripo source) = 20 + 5; blender (only env_kit / Blender fixes) = 0 credits.
Props whose acceptance is still running (stage built) are listed without a route.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KITS = ROOT / "docs/art-pipeline/map-kits"
MAPS = ("soho", "baskerville-manor", "heorot", "sherwood-forest")
COST = {"regen": 125, "retexture": 25, "blender": 0, "pending": 0}
PRIO = {"P0": 0, "P1": 1, "P2": 2}
# NOTES F20: Smart Mesh at 5000 triangles cannot hold foliage; these need another Tripo route, listed last
FOLIAGE = ("foliage", "flowers")  # matched against the prop material only


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def route(entry: dict) -> tuple[str, str]:
    stage = entry.get("stage")
    acc = entry.get("acceptance") or {}
    if stage in (None, "views", "tripo"):
        if stage == "views":
            return "regen", "не сгенерирован, вид готов в истории Tripo Image"
        return "regen", "не сгенерирован" if stage is None else "сгенерирован, не собран"
    if stage == "built":
        return "pending", "ждёт приёмщика"
    if stage == "rejected":
        return "regen", f"отказ {acc.get('score')}"
    card = ROOT / acc["card"] if acc.get("card") else None
    tools = []
    if card and card.is_file():
        tools = [f.get("tool", "") for f in load(card).get("rework_fix_list", [])]
    text = " ".join(tools)
    note = f"доработка {acc.get('score')}"
    if "форма" in text:
        return "regen", note + ", правка формы исходника"
    if "текстура" in text:
        return "retexture", note + ", правка текстуры"
    return "blender", note + (", " + ", ".join(sorted(set(t for t in tools if t))) if tools else "")


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--out", type=Path, default=KITS / "QUEUE-2026-10-27.md")
    a.add_argument("--date", default="2026-10-27")
    args = a.parse_args()
    rows = []
    for m in MAPS:
        props = load(KITS / m / "props.json")["props"]
        status = load(KITS / m / "status.json")["props"]
        for p in props:
            e = status.get(p["key"], {})
            if e.get("stage") == "accepted":
                continue
            r, note = route(e)
            foliage = any(w in p.get("material", "").lower() for w in FOLIAGE)
            rows.append({"map": m, "key": p["key"], "name": p["nameRu"], "prio": p.get("priority", "P2"),
                         "route": r, "note": note, "foliage": foliage})
    order = {"regen": 0, "retexture": 1, "blender": 2, "pending": 3}
    rows.sort(key=lambda x: (x["foliage"], PRIO.get(x["prio"], 3), order[x["route"]], x["map"], x["key"]))
    total = sum(COST[x["route"]] for x in rows if not x["foliage"])
    total_f = sum(COST[x["route"]] for x in rows if x["foliage"])
    lines = [
        f"# Очередь Tripo Studio на {args.date}",
        "",
        "Собрано `tools/mapkits/queue.py` из `docs/art-pipeline/map-kits/<map>/status.json` и карточек приёмки.",
        "Баланс Studio 21.10 16:57 — 0; кредиты обновятся 27.10. Принятые пропсы в очередь не входят.",
        "",
        "Маршруты и цена: **regen** — заново: картинка Tripo Image (бесплатно) → Smart Mesh 100 → текстура 4K 20 → PBR 5 = 125;",
        "**retexture** — только текстура на том же меше: 4K 20 + PBR 5 = 25; **blender** — правка без кредитов",
        "(env_kit геометрию не чинит — нужен отдельный шаг очистки GLB/Blender); **pending** — ждёт второго приёмщика.",
        "regen с «правкой формы исходника» — верхняя оценка: часть таких правок может закрыть Blender без кредитов.",
        "Порядок 27.10: P0 → P1 → P2 по таблице. У строк «вид готов» картинка уже в истории Tripo Image (F21: искать колесом",
        "мыши), остальным её делают заново бесплатно. Строки blender ждут шага очистки GLB (висящие осколки, нормали) — его в",
        "`tools/mapkits` пока нет, env_kit по политике геометрию не правит.",
        "Листва (F20) идёт в конец: Smart Mesh 5 000 её не держит, для неё нужен другой маршрут (HD Model, бюджет 12 000).",
        "",
        f"Итого без листвы: **{total}** кредитов; листва: {total_f}.",
        "",
        "| # | Приор. | Карта | Проп | Маршрут | Кредиты | Почему |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, x in enumerate(rows, 1):
        name = f"{x['name']} (`{x['key']}`)" + (" — листва" if x["foliage"] else "")
        lines.append(f"| {i} | {x['prio']} | {x['map']} | {name} | {x['route']} | {COST[x['route']]} | {x['note']} |")
    lines += ["", f"Строк: {len(rows)}.", ""]
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(args.out, len(rows), total, total_f)


if __name__ == "__main__":
    main()
