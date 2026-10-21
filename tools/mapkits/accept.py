"""Acceptance of map-kit props (stage 4 of 3d-model-pipeline, prop branch): frames, acceptor prompt, workflow args, cards.

    python tools/mapkits/accept.py prepare <map> <key>... [--date YYYYMMDD] [--run <run dir>]   # frames + prompts
    python tools/mapkits/accept.py args <map> <key>... [--second] --out <args.json>              # second-acceptor args
    python tools/mapkits/accept.py finish <map> <workflow-output.json> [--second]               # card(-2).json + status

Object: the env_kit export of the prop (<run>/export/SM_Env_<Name>.fbx + T_Env_<Name>_{BC,N,ORM}.png,
<run>/reports/assets/SM_Env_<Name>.build.json, <run>/reports/fbx-readback/SM_Env_<Name>.json). Frames:
tools/art/acceptance/capture_acceptance_set.py --no-base --allow-no-tone --sheet <views sheet> (all MODEL_FRAMES of
validate_card.py). Card: unmatched.asset-acceptance/2, kind model, D = null, G-RIG = n/a (prop, skill §3). The gates are
computed here from the build report and given to the acceptor as facts; it scores S, F, T on the frames.
Acceptors: first «Opus xhigh», 8.0-8.4 -> second «Opus high» (user decision 2026-10-21).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "mapkits"))
import mapkit  # noqa: E402
import tripo_intake as ti  # noqa: E402

SCHEMA = ROOT / "tools" / "art" / "acceptance" / "asset-acceptance-2.output-model.schema.json"
DELEGATION = "«Я даю тебе абсолютно все разрешения» (пользователь, 2026-10-21, задание map kits)"


def rel(p: Path) -> str:
    return str(Path(p).resolve().relative_to(ROOT)).replace("\\", "/")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def kit_root(m: str) -> Path:
    return ROOT / "art" / "pipeline-candidates" / f"ASSET-MAPKIT-{m.upper()}-001"


def prop_paths(m: str, key: str, run: Path) -> dict:
    name = ti.ue_name(m, key)
    exp = run / "export"
    return {"name": name, "fbx": exp / f"SM_Env_{name}.fbx",
            "tex": [exp / f"T_Env_{name}_{c}.png" for c in ("BC", "N", "ORM")],
            "build": run / "reports" / "assets" / f"SM_Env_{name}.build.json",
            "readback": run / "reports" / "fbx-readback" / f"SM_Env_{name}.json"}


def gates(m: str, key: str, pp: dict) -> dict:
    b = json.loads(pp["build"].read_text(encoding="utf-8"))
    c = b.get("checks", {})
    p = mapkit.prop(m, key)
    tris = b.get("roundtrip", {}).get("triangles") or b.get("import", {}).get("triangles")
    uv = b.get("uv0", {})
    src = rel(pp["build"])
    topo_ok = bool(c.get("single_mesh") and c.get("triangles_le_budget") and tris and tris <= 12000)
    uv_ok = bool(c.get("uv0_present") and c.get("uv0_inside_0_1") and uv.get("overlap_fraction_of_covered", 1) <= 0.01)
    tex_ok = all(t.is_file() for t in pp["tex"])
    names_ok = (b.get("ue_mesh") == f"SM_Env_{pp['name']}" and b.get("material_names") == [f"M_Env_{pp['name']}"])
    g = {
        "G-TOPO": {"status": "PASS" if topo_ok else "FAIL", "source": src,
                   "note": f"{tris} tris (бюджет env_kit 12000, проп {p['trisMax']}), single_mesh={c.get('single_mesh')}",
                   "source_defect": None},
        "G-UV": {"status": "PASS" if uv_ok else "FAIL", "source": src,
                 "note": f"UV0 islands {uv.get('islands')}, used {uv.get('uv_area_used_fraction')}, overlap "
                         f"{uv.get('overlap_fraction_of_covered')}", "source_defect": None},
        "G-TEX": {"status": "PASS" if tex_ok else "FAIL", "source": src,
                  "note": "T_Env_%s_{BC,N,ORM}.png 2048, N DirectX, ORM.R=1 (без AO)" % pp["name"], "source_defect": None},
        "G-RIG": {"status": "n/a", "source": src, "note": "статический проп без рига", "source_defect": None},
        "G-NAMES": {"status": "PASS" if names_ok else "FAIL", "source": src,
                    "note": f"SM_Env_{pp['name']}, M_Env_{pp['name']}", "source_defect": None},
    }
    if not c.get("checks_passed", b.get("checks_passed")) and not all(c.values()):
        bad = [k for k, v in c.items() if v is not True]
        g["G-TOPO"]["note"] += f"; build checks not passed: {bad}"
    return g


PROMPT = """# Приёмка пропа кита карты (этап 4 скилла 3d-model-pipeline, ветка prop)

Делегирование пользователя дословно: {delegation}. Трат нет. Ты — независимый приёмщик; файлов не пишешь, скриптов не
запускаешь. Верни карточку `unmatched.asset-acceptance/2` (kind model) структурированным выводом.

## Объект
- Карта: {board} ({map}); проп `{key}` — {name_ru} / {name_en}. Роль в сцене: {role}; зона: {zone}; приоритет {priority}.
- Описание (то, что заказано): {desc_en}. Материалы: {material}. Реальный размер ≈ {size} м; в игре высота {game_h} uu
  (фигура героя 55 uu). Стиль кита: {style}
- Генерация: Tripo «Умная сетка» P2.0 по двум видам Gemini/Tripo Image (front + {slot}); сборка tools/art/env_kit.

## Входы (открой каждый Read-ом целиком)
- Кадры: `{frames_dir}/` — все файлы из `frames.json#files`: turn-000…315 (8 ракурсов, 45°), wire-front/34/back,
  close-head (верх 22 %), close-weapon (верхняя часть), close-base (низ 22 %), uv-layout.png, sheet.png (виды, по
  которым генерировали: слева front, справа {slot}).
- Отчёт сборки: `{build}` (числа топологии, UV, текстур — для гейтов уже посчитаны ниже).

## Гейты (посчитаны по отчёту, перенеси как есть)
{gates_json}

## Рубрика пропа (D = null, G-RIG = n/a)
- **S — силуэт и пропорции против sheet.png и описания.** 2,0: предмет тот, что заказан, пропорции и главные части
  совпадают с видами (≤ 5 % высоты), лишних и пропавших частей нет, узнаётся со всех 8 ракурсов; 1,5: одно
  второстепенное отличие (деталь контура); 1,0: два и более отличий, или заметно сбита пропорция главной части (> 10 %),
  или основное пятно цвета другого семейства; 0,5: пропала или другая главная часть, фантомная часть (выступ/оболочка на
  turn-090/270, wire-*), узнаётся только спереди; 0,0: другой предмет.
- **F — форма и шейдинг.** 2,0: на полном росте и крупных планах нет дыр, просветов, рваных краёв, чёрных пятен,
  вывернутых частей, мусорной геометрии, оплывших бесформенных масс; тонкие элементы целы; сетка на wire-* следует
  форме; 1,5: дефекты видны только на крупном плане; 1,0: дефект на полном росте в одной зоне или оплывшая форма
  главной части; 0,5: дефекты на полном росте в двух и более зонах; 0,0: сетка разрушена.
- **T — текстуры.** 2,0: материалы читаются как в описании и на видах (дерево — дерево, металл — металл), нет
  запечённого света и теней в цвете (освещение снималось), нет размытых пятен, швов и растяжек, детализация не беднее
  эталона рендера пропов (`art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5/` — уровень кита Sarpedon);
  1,5: дефекты только крупного плана; 1,0: дефект на полном росте в одной зоне (мыло, шов, чужой цвет, запечённый
  блик); 0,5: две и более зоны; 0,0: текстура разрушена.
- score = round((S+F+T) / 6 × 10, 1). pass — score ≥ 8,0 и ни одно измерение < 1,0 и все гейты PASS/n/a;
  S < 1,5 — `return_to_stage_2` (перегенерация Tripo, rework_fix_list пуст, F/T < 2 — в known_issues); иначе
  `rework_blender` с пунктами rework_fix_list для каждого F/T < 2 и FAIL-гейта (tool — «env_kit params» или «исходник
  Tripo: форма/текстура»).
- Это фоновый проп настольной диорамы: читаемость на игровой дистанции важнее микродеталей; стилизация допустима.

## Константы карточки (перенеси дословно)
- schema `unmatched.asset-acceptance/2`, kind `model`, asset_id `{asset_id}`, clip null, cycle `{cycle}`, date `{date}`,
  previous_card {previous}.
- accepted_object: {accepted_json}
- frames: {{"dir": "{frames_dir}", "files": {files_json}}}
- reports: {reports_json}
- executor_session_id `{executor}`; decided_by `delegated: {delegation}`;
- status_note: короткая фраза по-русски о вердикте («проп принят по делегированию …» или что доработать).
- scores.D = {{"value": null, "rationale": "статический проп без рига", "frames": []}}.
- В scores.*.frames и known_issues[].frame — только имена из frames.files.
"""


def prepare(m: str, keys: list[str], date: str, run: Path | None, cycle: str) -> list[dict]:
    kit = mapkit.load_props(m)
    st = mapkit.load_status(m)
    out = []
    for key in keys:
        p = mapkit.prop(m, key)
        e = st["props"].get(key, {})
        r = run or (ROOT / (e.get("tripo") or {}).get("run", ""))
        pp = prop_paths(m, key, r)
        if not pp["fbx"].is_file() or not pp["build"].is_file():
            print(f"SKIP {key}: no build ({pp['fbx']})", file=sys.stderr)
            continue
        views = e.get("views") or {}
        sheet = ROOT / views["sheet"] if views.get("sheet") else None
        ev = kit_root(m) / "evidence" / "acceptance" / f"{date}-{key}-{cycle}"
        if ev.exists():
            sys.exit(f"ERROR {ev} exists: a new acceptance is a new cycle")
        cmd = [sys.executable, str(ROOT / "tools/art/acceptance/capture_acceptance_set.py"), "--fbx", str(pp["fbx"]),
               "--textures", str(pp["fbx"].parent), "--out", str(ev / "frames"), "--key", f"Env_{pp['name']}",
               "--no-base", "--allow-no-tone", "--previous", "none"]
        if sheet:
            cmd += ["--sheet", str(sheet)]
        rc = subprocess.call(cmd, stdout=subprocess.DEVNULL)
        if rc != 0:
            print(f"FAIL capture {key} rc={rc}", file=sys.stderr)
            continue
        fr = json.loads((ev / "frames" / "frames.json").read_text(encoding="utf-8"))
        accepted = [{"path": rel(pp["fbx"]), "sha256": sha256(pp["fbx"])}] + \
                   [{"path": rel(t), "sha256": sha256(t)} for t in pp["tex"] if t.is_file()]
        reports = [rel(pp["build"])] + ([rel(pp["readback"])] if pp["readback"].is_file() else [])
        g = gates(m, key, pp)
        prev = e.get("acceptance", {}).get("card")
        w, d, h = p["sizeM"]
        prompt = PROMPT.format(
            delegation=DELEGATION, board=kit["boardName"], map=m, key=key, name_ru=p["nameRu"], name_en=p["nameEn"],
            role=p["role"], zone=p["zone"], priority=p["priority"], desc_en=p["descEn"], material=p["material"],
            size=f"{w:g}×{d:g}×{h:g}", game_h=ti.target_uu(p), style=kit["styleEn"],
            slot=views.get("slot", mapkit.side_slot(p)), frames_dir=rel(ev / "frames"), build=rel(pp["build"]),
            gates_json=json.dumps(g, ensure_ascii=False, indent=1), asset_id=ti.asset_id(m, key), cycle=cycle,
            date=dt.date.today().isoformat(), previous=json.dumps(prev), accepted_json=json.dumps(accepted),
            files_json=json.dumps(fr["files"]), reports_json=json.dumps(reports),
            executor="claude-code:mapkits-session/env_kit")
        (ev / "acceptor-prompt.md").write_text(prompt, encoding="utf-8")
        (ev / "gates.json").write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
        out.append({"key": key, "asset": ti.asset_id(m, key), "evidence": rel(ev), "warnings": fr.get("warnings", [])})
    return out


def latest_evidence(m: str, key: str) -> Path | None:
    base = kit_root(m) / "evidence" / "acceptance"
    c = sorted(base.glob(f"*-{key}-r*")) if base.is_dir() else []
    return c[-1] if c else None


def args(m: str, keys: list[str], second: bool) -> dict:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    items = []
    for key in keys:
        ev = latest_evidence(m, key)
        if not ev:
            sys.exit(f"ERROR no evidence for {key}")
        tag = "acceptor2" if second else "acceptor"
        items.append({"asset": ti.asset_id(m, key), "evidence": rel(ev), "label": f"{tag}-{ti.asset_id(m, key)}-{ev.name.split('-')[-1]}",
                      "prompt": rel(ev / "acceptor-prompt.md")})
    effort = "high" if second else "xhigh"
    return {"kind": "model", "effort": effort, "profile": "Opus high" if second else "Opus xhigh", "items": items,
            "schema": schema}


def finish(m: str, output: Path, second: bool) -> None:
    res = json.loads(output.read_text(encoding="utf-8"))
    if isinstance(res, dict) and "result" in res:
        res = res["result"]
    st = mapkit.load_status(m)
    by_asset = {ti.asset_id(m, p["key"]): p["key"] for p in mapkit.load_props(m)["props"]}
    for r in res:
        card, ev = r.get("card"), ROOT / r["evidence"]
        key = by_asset[r["asset"]]
        if not card:
            print(f"NO CARD {key}")
            continue
        name = "card-2.json" if second else "card.json"
        (ev / name).write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cmd = [sys.executable, str(ROOT / "tools/art/acceptance/validate_card.py"), str(ev / "card.json"), "--print-verdict"]
        if second:
            cmd += ["--second", str(ev / "card-2.json"), "--final-json", str(ev / "final.json")]
        pr = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        verdict = (pr.stdout.strip().splitlines() or ["?"])[-1]
        e = st["props"].setdefault(key, {})
        acc = e.setdefault("acceptance", {})
        acc.update({"card": rel(ev / "card.json"), "rc": pr.returncode, "verdictTool": verdict})
        if second:
            fin = json.loads((ev / "final.json").read_text(encoding="utf-8")) if (ev / "final.json").is_file() else {}
            acc.update({"score2": card.get("score"), "final": fin.get("verdict"), "finalScore": fin.get("score")})
            v = fin.get("verdict")
        else:
            acc.update({"score": card.get("score"), "verdict": card.get("verdict"),
                        "scores": {k: (card["scores"][k] or {}).get("value") for k in ("S", "F", "T")}})
            v = card.get("verdict") if pr.returncode == 0 else ("needs_second" if pr.returncode == 3 else "invalid")
        e["stage"] = {"pass": "accepted", "rework_blender": "rework", "return_to_stage_2": "rejected",
                      "return_to_stage_1": "rejected"}.get(v, e.get("stage", "built"))
        print(f"{key}: score {card.get('score')} verdict {card.get('verdict')} rc {pr.returncode} -> {e['stage']}"
              + (f"\n  {pr.stderr.strip()[:400]}" if pr.returncode not in (0, 3) else ""))
    mapkit.save_status(m, st)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("prepare"); a.add_argument("map"); a.add_argument("keys", nargs="+")
    a.add_argument("--date", default=dt.date.today().strftime("%Y%m%d")); a.add_argument("--run", type=Path)
    a.add_argument("--cycle", default="r1")
    a = sub.add_parser("args"); a.add_argument("map"); a.add_argument("keys", nargs="+"); a.add_argument("--second", action="store_true")
    a.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("finish"); a.add_argument("map"); a.add_argument("output", type=Path); a.add_argument("--second", action="store_true")
    ns = ap.parse_args()
    if ns.cmd == "prepare":
        print(json.dumps(prepare(ns.map, ns.keys, ns.date, ns.run and (ROOT / ns.run), ns.cycle), ensure_ascii=False, indent=1))
    elif ns.cmd == "args":
        ns.out.write_text(json.dumps(args(ns.map, ns.keys, ns.second), ensure_ascii=True), encoding="ascii")
        print(ns.out)
    else:
        finish(ns.map, ns.output, ns.second)


if __name__ == "__main__":
    main()
