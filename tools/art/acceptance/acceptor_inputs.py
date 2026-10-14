#!/usr/bin/env python3
"""Выдержка входов приёмщика модели (этап 4 скилла 3d-model-pipeline): `acceptor-inputs.json` для плейсхолдеров
промпта §8.2 (`references/acceptance-and-blender.md`). Пилот 2026-10-13: F152, F147, RA-10, F38, F39, F41/F78, F99.

    python tools/art/acceptance/acceptor_inputs.py --frames $E/frames [--asset-card <asset-card.yaml>] \
        [--previous-card <card.json> | none] [--out $E/acceptor-inputs.json] [--print]

Зачем. Приёмщик читал весь bake-профиль ради четырёх ключей G-NAMES, а с ним — заметки исполнителя (`note`,
`status_note`, `weights_note`, `rig.junctions[].note`, `history`): слова исполнителя доходили до приёмщика (§1 п.3,
F147). Выдержка берёт только машинные ключи:
- G-NAMES: `UE_NAMES`, `FIGURE_HEIGHT_M`, `FIGURE_BOUNDS_TOP_M` заявки; из bake-профиля (путь —
  `<LD>/reports/run-manifest.json#source_profile`) только `meshes`, `materials.atlas`, `exports.fbx_preset`,
  `scale.figure_top_m`; рост без оружия — `ld-fbx-report.json#roundtrip.ld.skeletal.meshes.<Body>.bounds_m.max[2]`
  (решает, как в validate_card.py), оружие и `rig-report.json#checks.unit_scale_1_and_height.measured.skeletal_top_cm`
  (верх всей фигуры, с оружием) — справка;
- отчёт TeamAccent (F38): тот `ld-team-accent-report.json`, чей `outputs` дал принимаемую карту
  `T_<Key>_H2LD_TeamAccent_2K.png` (sha256 из `frames.json#accepted_object`); сначала — в том же look-dev прогоне, затем
  отдельный прогон TeamAccent (`pins` указывают на textures/ этого look-dev), затем любой прогон ассета с тем же sha;
- якоря `ANCHORS_EN` заявки (F39; нет — `ANCHORS`);
- список прежнего цикла (F99): `rework_fix_list` и `known_issues` прежней карточки (при паре — `final.json#source_card`)
  — пункт, кадр и текст прежнего приёмщика, без статуса исполнителя. Прежняя карточка — `--previous-card`, иначе
  `<дата>-r<N-1>/` рядом с `$E` (как `capture_acceptance_set.py --previous`).
Ключи-заметки (`note`, `*_note`, `notes`, `NOTES`, `history`, `comment*`) вырезаются и внутри взятых блоков.
`placeholders` — готовые строки для `{{UE_NAMES}}`, `{{BAKE_PROFILE_KEYS}}`, `{{HEIGHT_RULE}}`, `{{TA_REPORT}}`,
`{{ANCHORS}}`, `{{PREV_FIX_LIST}}`; приёмщик файл не открывает (`acceptor-*`, §2.3 п.1), значения стоят в промпте.
Код выхода: 0 — выдержка записана (предупреждения — в `warnings`); 1 — ошибка входа (нет frames.json, look-dev прогона
или его run-manifest).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCHEMA = "unmatched.acceptor-inputs/1"
HEIGHT_TOL = 0.01  # validate_card.py HEIGHT_TOL: G-NAMES (5) — бюджет роли ± 1 %
PROFILE_KEYS = (("meshes",), ("materials", "atlas"), ("exports", "fbx_preset"), ("scale", "figure_top_m"))
CARD_KEYS = ("UE_NAMES", "FIGURE_HEIGHT_M", "FIGURE_BOUNDS_TOP_M")
NOTE_KEY = re.compile(r"^(note|notes|history|comment|comments)$|_note$|_notes$", re.IGNORECASE)
CYCLE_DIR = re.compile(r"^(\d{8})-r(\d+)$")


class InputError(Exception):
    pass


def repo_rel(p) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_json(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def dig(d, *keys):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def strip_notes(obj):
    """Копия без ключей-заметок исполнителя (note, *_note, notes, history, comment*) на любой глубине."""
    if isinstance(obj, dict):
        return {k: strip_notes(v) for k, v in obj.items() if not NOTE_KEY.search(str(k))}
    if isinstance(obj, list):
        return [strip_notes(v) for v in obj]
    return obj


def load_asset_card(path: Path):
    try:
        import yaml  # noqa: PLC0415
    except ImportError as e:
        raise InputError("нет пакета PyYAML: заявка %s не прочитана" % path) from e
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise InputError("заявка %s — не словарь YAML" % path)
    return data


def look_dev_run(frames_dir: Path, man: dict) -> Path:
    fbx = dig(man, "inputs", "fbx", "path")
    if not fbx:
        raise InputError("frames.json#inputs.fbx.path нет")
    p = REPO / fbx if not Path(fbx).is_absolute() else Path(fbx)
    if p.parent.name != "export":
        raise InputError("FBX кадров %s не в <LD>/export/: выдержка для генерического look-dev H2 (форк — вручную, "
                         "§12.2)" % fbx)
    return p.parent.parent


def find_team_accent(ld: Path, accepted: list) -> dict | None:
    """Отчёт TeamAccent принимаемой карты (F38): outputs.*TeamAccent_2K.png.sha256 = sha256 карты из accepted_object.
    Из нескольких — с passed true, затем тот же look-dev прогон, отдельный прогон с pins на textures/ этого look-dev,
    другой прогон ассета; затем новее по имени. None — у принимаемого объекта нет карты TeamAccent (проп)."""
    ta = next((o for o in accepted or [] if re.search(r"_TeamAccent(_2K)?\.png$", Path(o.get("path", "")).name)), None)
    if ta is None:
        return None
    own = ld / "reports" / "ld-team-accent-report.json"
    others = sorted((p for p in ld.parent.glob("*/reports/ld-team-accent-report.json") if p.parent.parent != ld),
                    key=lambda p: p.parent.parent.name, reverse=True)
    ld_tex = repo_rel(ld / "textures") + "/"
    found = []
    for rank, p in enumerate([own] + others):
        rep = read_json(p) if p.is_file() else None
        if not isinstance(rep, dict):
            continue
        outs = rep.get("outputs") or {}
        hit = next((n for n, o in outs.items()
                    if n.endswith("TeamAccent_2K.png") and isinstance(o, dict) and o.get("sha256") == ta["sha256"]), None)
        if not hit:
            continue
        pins_ld = any(isinstance(v, dict) and str(v.get("path", "")).startswith(ld_tex)
                      for k, v in (rep.get("pins") or {}).items() if k.startswith("lookdev_run"))
        order = 0 if p == own else (1 if pins_ld else 2)
        found.append((rep.get("passed") is not True, order, rank, p, hit, pins_ld))
    if not found:
        return {"report": None, "texture": ta["path"], "texture_sha256": ta["sha256"], "same_run": None,
                "candidates": [], "why": "нет ld-team-accent-report.json, чей outputs дал эту карту (sha256)"}
    found.sort(key=lambda t: t[:3])  # passed, затем тот же прогон / pins этого look-dev / другой, затем новее
    failed, order, _r, p, hit, pins_ld = found[0]
    return {"report": repo_rel(p), "run": repo_rel(p.parent.parent), "texture": ta["path"],
            "texture_sha256": ta["sha256"], "output": hit, "same_run": order == 0, "pins_this_look_dev": pins_ld,
            "report_passed": not failed, "candidates": [repo_rel(t[3]) for t in found],
            "why": ("тот же look-dev прогон" if order == 0 else
                    "отдельный прогон TeamAccent по textures/ этого look-dev" if order == 1 else
                    "другой прогон ассета дал карту с тем же sha256")}


def previous_card_path(frames_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        if explicit.lower() == "none":
            return None
        p = Path(explicit).resolve()
        if not p.is_file():
            raise InputError("нет прежней карточки %s" % explicit)
        return p
    run = frames_dir.parent
    m = CYCLE_DIR.match(run.name)
    if not m or int(m.group(2)) < 2 or not run.parent.is_dir():
        return None
    want = int(m.group(2)) - 1
    prev = sorted(p for p in run.parent.iterdir() if p.is_dir() and CYCLE_DIR.match(p.name)
                  and int(CYCLE_DIR.match(p.name).group(2)) == want and (p / "card.json").is_file())
    if not prev:
        return None
    final = read_json(prev[-1] / "final.json")
    src = (final or {}).get("source_card")
    if src:
        sp = Path(src)
        for cand in (sp, REPO / src, prev[-1] / sp.name):
            if cand.is_file():
                return cand.resolve()
    return (prev[-1] / "card.json").resolve()


def prev_fix_list(card_path: Path | None) -> tuple[list, str | None]:
    """Пункты прежней карточки: rework_fix_list (fix) и known_issues (note прежнего приёмщика) — без tool и статусов."""
    if card_path is None:
        return [], None
    card = read_json(card_path) or {}
    items = []
    for i, x in enumerate(card.get("rework_fix_list") or [], 1):
        items.append({"list": "rework_fix_list", "n": i, "item": x.get("item"), "frame": x.get("frame"),
                      "text": x.get("fix")})
    for i, x in enumerate(card.get("known_issues") or [], 1):
        items.append({"list": "known_issues", "n": i, "item": x.get("item"), "frame": x.get("frame"),
                      "text": x.get("note")})
    return items, card.get("cycle")


def _num(x, nd=5):
    return None if not isinstance(x, (int, float)) else round(float(x), nd)


def height_block(ld: Path, bake: Path | None, profile: dict, card: dict) -> tuple[dict, list]:
    warns = []
    L = read_json(ld / "reports" / "ld-fbx-report.json") or {}
    skel = dig(L, "roundtrip", "ld", "skeletal", "meshes") or {}
    meshes = (profile or {}).get("meshes") if isinstance((profile or {}).get("meshes"), dict) else {}
    body = meshes.get("body") or next((m for m in skel if m.endswith("_Body")), None)
    top = dig(skel, body, "bounds_m", "max") if body else None
    body_top = _num(top[2]) if isinstance(top, list) and len(top) == 3 else None
    if body_top is None:
        warns.append("ld-fbx-report.json#roundtrip.ld.skeletal.meshes.%s.bounds_m.max: нет ключа" % body)
    others = {}
    for m, v in sorted(skel.items()):
        mx = dig(v, "bounds_m", "max")
        if m != body and isinstance(mx, list) and len(mx) == 3:
            others[m] = _num(mx[2])
    rig = read_json(bake / "reports" / "rig-report.json") if bake else None
    sk_top = _num(dig(rig, "checks", "unit_scale_1_and_height", "measured", "skeletal_top_cm"), 3)
    ldr = repo_rel(ld / "reports" / "ld-fbx-report.json")
    blk = {"body_mesh": body,
           "body_top_m": {"source": "%s#roundtrip.ld.skeletal.meshes.%s.bounds_m.max[2]" % (ldr, body),
                          "value": body_top},
           "other_meshes_top_m": others,
           "skeletal_top_cm": {"source": ("%s#checks.unit_scale_1_and_height.measured.skeletal_top_cm"
                                          % repo_rel(bake / "reports" / "rig-report.json")) if bake else None,
                               "value": sk_top,
                               "meaning": "верх всей фигуры с оружием — справка, рост не решает"},
           "FIGURE_HEIGHT_M": card.get("FIGURE_HEIGHT_M"), "FIGURE_BOUNDS_TOP_M": card.get("FIGURE_BOUNDS_TOP_M"),
           "tolerance": HEIGHT_TOL}
    return blk, warns


def height_rule(h: dict) -> str:
    fh, fb = h["FIGURE_HEIGHT_M"], h["FIGURE_BOUNDS_TOP_M"]
    s = ("Рост для G-NAMES п.(5) — верх ТЕЛА без оружия: %s = %s м против FIGURE_HEIGHT_M заявки %s м ± %d %%"
         % (h["body_top_m"]["source"], h["body_top_m"]["value"], fh, round(HEIGHT_TOL * 100)))
    if isinstance(fb, (int, float)) and isinstance(fh, (int, float)) and fb > fh * (1 + HEIGHT_TOL):
        s += ("; верх тела выше бюджета (деталь тела: рога, гребень и т. п.) сверяется с FIGURE_BOUNDS_TOP_M %s м ± %d %%"
              % (fb, round(HEIGHT_TOL * 100)))
    if h["other_meshes_top_m"]:
        s += "; рост не задают другие меши (оружие): " + ", ".join(
            "%s bounds_m.max[2] = %s м" % (m, v) for m, v in h["other_meshes_top_m"].items())
    if h["skeletal_top_cm"]["value"] is not None:
        s += "; %s = %s — верх всей фигуры с оружием, справка" % (h["skeletal_top_cm"]["source"],
                                                                 h["skeletal_top_cm"]["value"])
    return s + "."


def ta_text(ta: dict | None) -> str:
    if ta is None:
        return "TeamAccent: у принимаемого объекта нет карты TeamAccent (проп) — строка G-TEX TeamAccent неприменима."
    if not ta.get("report"):
        return ("TeamAccent: отчёт, давший карту %s (sha256 %s…), не найден — строка G-TEX TeamAccent_2K = FAIL "
                "(нет отчёта)." % (ta["texture"], ta["texture_sha256"][:12]))
    where = ("снят в том же look-dev прогоне" if ta["same_run"] else
             "отдельный прогон TeamAccent %s" % ta["run"])
    return ("TeamAccent %s: %s — для строки G-TEX «TeamAccent_2K» решает этот отчёт (его outputs.%s.sha256 = sha256 "
            "принимаемой карты %s)." % (where, ta["report"], ta["output"], ta["texture"]))


def fix_list_text(items: list, cycle: str | None) -> str:
    if not items:
        return "нет (r1 или у прежней карточки пустые rework_fix_list и known_issues)"
    return "\n".join("- %s %s п.%d · %s · %s — %s" % (cycle or "прежний цикл", x["list"], x["n"], x["item"], x["frame"],
                                                      x["text"]) for x in items)


def build(frames_dir: Path, asset_card: Path | None = None, previous_card: str | None = None) -> dict:
    frames_dir = Path(frames_dir).resolve()
    man = read_json(frames_dir / "frames.json")
    if not isinstance(man, dict):
        raise InputError("нет или не читается %s" % (frames_dir / "frames.json"))
    ld = look_dev_run(frames_dir, man)
    lman = read_json(ld / "reports" / "run-manifest.json")
    if not isinstance(lman, dict):
        raise InputError("нет %s (look-dev прогон без run-manifest: выдержка не строится)"
                         % repo_rel(ld / "reports" / "run-manifest.json"))
    warns = []
    prof_rel = dig(lman, "source_profile", "path")
    profile = read_json(REPO / prof_rel) if prof_rel else None
    if not isinstance(profile, dict):
        warns.append("bake-профиль %s не прочитан (run-manifest#source_profile.path)" % prof_rel)
        profile = {}
    elif dig(lman, "source_profile", "sha256") and sha256(REPO / prof_rel) != lman["source_profile"]["sha256"]:
        warns.append("bake-профиль %s изменён после look-dev (sha256 ≠ run-manifest#source_profile.sha256)" % prof_rel)
    bake_rel = dig(lman, "source_run", "path")
    bake = (REPO / bake_rel) if bake_rel else None
    asset_id = lman.get("asset_id") or ld.parent.name
    ac_path = Path(asset_card).resolve() if asset_card else REPO / "art" / "pipeline-candidates" / asset_id / "asset-card.yaml"
    if not ac_path.is_file():
        raise InputError("нет заявки %s" % repo_rel(ac_path))
    card = load_asset_card(ac_path)
    for k in ("UE_NAMES", "FIGURE_HEIGHT_M"):
        if card.get(k) is None:
            warns.append("в заявке нет %s" % k)
    prof_keys = {".".join(k): strip_notes(dig(profile, *k)) for k in PROFILE_KEYS}
    for k, v in prof_keys.items():
        if v is None:
            warns.append("bake-профиль %s: нет ключа %s" % (prof_rel, k))
    height, hw = height_block(ld, bake, profile, card)
    warns += hw
    ta = find_team_accent(ld, man.get("accepted_object"))
    if ta is not None and not ta.get("report"):
        warns.append("TeamAccent: %s" % ta["why"])
    prev_path = previous_card_path(frames_dir, previous_card)
    items, prev_cycle = prev_fix_list(prev_path)
    anchors = card.get("ANCHORS_EN") or card.get("ANCHORS")
    ue_names = strip_notes(card.get("UE_NAMES"))
    tex_files = sorted(Path(o["path"]).name for o in man.get("accepted_object") or []
                       if Path(o["path"]).suffix.lower() in (".png", ".dds", ".tga"))
    gnames = {"UE_NAMES": ue_names, "FIGURE_HEIGHT_M": card.get("FIGURE_HEIGHT_M"),
              "FIGURE_BOUNDS_TOP_M": card.get("FIGURE_BOUNDS_TOP_M"),
              "texture_files": tex_files,
              "bake_profile": {"path": prof_rel, "sha256": dig(lman, "source_profile", "sha256"), **prof_keys},
              "height": height}
    out = {
        "schema": SCHEMA, "tool": "tools/art/acceptance/acceptor_inputs.py", "asset_id": asset_id,
        "sources": {"frames_json": repo_rel(frames_dir / "frames.json"), "look_dev_run": repo_rel(ld),
                    "bake_run": bake_rel, "asset_card": {"path": repo_rel(ac_path), "sha256": sha256(ac_path)},
                    "previous_card": repo_rel(prev_path) if prev_path else None},
        "g_names": gnames,
        "team_accent": ta,
        "anchors": anchors,
        "prev_fix_list": {"cycle": prev_cycle, "items": items},
        "excluded": "записи исполнителя (ключи note, *_note, notes, history, comment*; заметки заявки) в выдержку не "
                    "входят: §1 п.3, F147, F152",
        "warnings": warns,
    }
    out["placeholders"] = {
        "UE_NAMES": json.dumps(ue_names, ensure_ascii=False) + (
            " (файлы текстур принимаемого объекта: %s)" % ", ".join(tex_files) if tex_files else ""),
        "BAKE_PROFILE_KEYS": json.dumps({k: v for k, v in gnames["bake_profile"].items() if k != "sha256"},
                                        ensure_ascii=False),
        "HEIGHT_RULE": height_rule(height),
        "TA_REPORT": ta_text(ta),
        "ANCHORS": anchors,
        "PREV_FIX_LIST": fix_list_text(items, prev_cycle),
    }
    return strip_notes_top(out)


def strip_notes_top(out: dict) -> dict:
    """Последняя проверка: в выдержке нет ключей-заметок (кроме служебного excluded)."""
    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if NOTE_KEY.search(str(k)):
                    raise AssertionError("ключ-заметка в выдержке: %s.%s" % (path, k))
                walk(v, "%s.%s" % (path, k))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, "%s[%d]" % (path, i))
    walk(out, "$")
    return out


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # кириллица в Git Bash/агентах (консоль cp1251)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--frames", required=True, help="$E/frames (frames.json съёмки capture_acceptance_set.py)")
    ap.add_argument("--asset-card", help="asset-card.yaml (по умолчанию art/pipeline-candidates/<ASSET_ID>/)")
    ap.add_argument("--previous-card", help="карточка прежнего цикла (по умолчанию <дата>-r<N-1>/ рядом с $E; none — "
                                            "без неё)")
    ap.add_argument("--out", help="по умолчанию $E/acceptor-inputs.json (рядом с frames/)")
    ap.add_argument("--print", action="store_true", help="напечатать placeholders")
    a = ap.parse_args(argv)
    frames_dir = Path(a.frames).resolve()
    try:
        data = build(frames_dir, a.asset_card, a.previous_card)
    except InputError as e:
        print("FAIL: %s" % e, file=sys.stderr)
        return 1
    out = Path(a.out).resolve() if a.out else frames_dir.parent / "acceptor-inputs.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for w in data["warnings"]:
        print("WARN: %s" % w, file=sys.stderr)
    if a.print:
        for k, v in data["placeholders"].items():
            print("{{%s}}:\n%s\n" % (k, v))
    print("OK: %s" % repo_rel(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
