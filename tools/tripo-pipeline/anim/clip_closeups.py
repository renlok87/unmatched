#!/usr/bin/env python3
"""Крупные планы кадров клипа в Blender для приёмки клипов (этап 6 скилла 3d-model-pipeline) и пара шва цикла Idle.

Пилот 2026-10-14: крупные планы клипов снимали разовые скрипты (C:/tmp/*-anim-*/closeup_probe.py, closeups.py), их
отчёт не записывал центр и размер камеры — r2/r3 нельзя было снять один в один (F146); у Idle приёмщик ни разу не видел
шов цикла, только ключи 0/15/30/45 (F154). Этот инструмент пишет камеру каждого кадра в отчёт и повторяет её по
отчёту прежнего цикла (--shots-from); пара шва — последний кадр N и кадр 0 одной камерой, рядом.

    python tools/tripo-pipeline/anim/clip_closeups.py --spec <ASSET_DIR>/build-profiles/<key>-h2anim.json --clip Idle \
        [--default-shots] [--shots "f:view:centre:size;..."] [--shots-from <прежний отчёт *-closeups.json>] \
        [--seam front,q34 | --no-seam] [--backface-culling on|off] [--out <run>/preview/closeups-blender] [--res 1200] \
        [--blender <exe>]
    python tools/tripo-pipeline/anim/clip_closeups.py --fbx <AM_<Key>_<Clip>.fbx> [--base <SM_*_Base.fbx>] \
        --out <dir> [--label <Key>-<Clip>] [--default-shots --role idle|oneshot|terminal [--side R|L]] ...

Кадр `f:view:centre:size`: f — номер кадра клипа 0..N (0 = rest) или правило: mid (N/2), last (N), armR / armL (кадр
наибольшего поворота плечевой кости arm_upper.<S> от rest — рука вперёд или вверх), gripR / gripL (кадр наибольшего
поворота weapon.<S> в кулаке против rest; нет кости или поворот < 5° — как arm<S>); view — front, back, left, right, q34 (= q34l), q34r,
q34b, q34bl, rback, top34, top, topb (направление от фигуры к камере, оси арматуры: +X — лицо, +Y — левый бок; topb —
сзади сверху); centre — `x,y,z` в см осей арматуры (как `rest_measured` спеки), `@<кость>` (голова кости на этом
кадре) или `fig` (вся фигура на этом кадре); size — ortho-размер кадра в см, `h<доля>` (доля роста фигуры в кадре 0:
h0.33) или у `fig` — `auto`. Разделитель кадров — `;`. Правило кадра и размера Blender переводит в числа; в отчёт идут
числа и правило (frame_rule, size_rule), а --shots-from повторяет числа.

Стандартный список (--default-shots, C43/C45 2026-10-14) — по роли клипа (спека: clips.<Clip>.role, сторона оружия
weapon.side; без спеки — --role/--side), функция default_shots(): со спины 3/4 на кадре наибольшего поворота плеча
каждой руки (срез рукава и кромка под плащом при руке вперёд: Achilles F129, Beowulf C43), ворот и затылок сзади и сзади
сверху (провал ворота Beowulf C61), кулак на кадре наибольшего поворота оружия; плюс вид фигуры по роли (idle — mid,
oneshot — кадр наибольшего поворота плеча, terminal — mid и last с воротом сзади). Со списком по умолчанию включено
отсечение задних граней (--backface-culling on, как в UE): шапка, видимая только изнанкой, в Blender закрывала дыру,
которую UE показывает чёрной (C22, C61). Отсечение пишется в look отчёта и повторяется --shots-from.
--shots-from <отчёт>: те же кадры с теми же числами центра и размера (центр `@кость` и `fig` прежнего цикла
повторяются числом, а не пересчитываются: камера одна и та же, сравниваются кадры r2/r3 один в один).
Шов (F154): с --spec у клипа с role idle — по умолчанию (виды front, q34), иначе --seam <виды>; камера — по всей фигуре
на кадрах 0 и N (или из --shots-from). Пара — `<label>-seam-fNN-f00-<view>.jpg`: слева последний кадр N, справа
кадр 0; при чистом шве они совпадают (Workbench детерминирован: разница пикселей ≈ 0, она пишется в отчёт).

Выход (`--out`, по умолчанию <run>/preview/closeups-blender — его копирует в кадры приёмки
tools/tripo-pipeline/ue7a/prep_acceptance.py, маска `<Key>-<Clip>-*.jpg`):
  <label>-fNN-<view>.jpg         крупные планы, JPEG q92, res × res (1200 по умолчанию: HANDBOOK §8)
  <label>-seam-fNN-f00-<view>.jpg пара шва, две портретные панели res/2 × res
  <label>-closeups.json          schema unmatched.clip-closeups/1: клип и подставка с sha256, Blender, вид (Workbench,
                                 цвета), каждый кадр — кадр клипа, вид, центр (см осей арматуры и м мира), размер,
                                 положение и поворот камеры; шов — камера и разница кадров N и 0
Повтор в тот же --out заменяет файлы этого label (добавить кадры — `--shots-from <отчёт> --shots <ещё>`).
Blender — headless (`-b --factory-startup`), один процесс; ничего не сохраняется в .blend.
Код выхода: 0 — готово; 1 — ошибка входа или Blender.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BLENDER_SCRIPT = HERE / "_clip_closeups_blender.py"
DEFAULT_BLENDER = os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
SCHEMA = "unmatched.clip-closeups/1"
QUALITY, RES = 92, 1200
VIEWS = ("front", "back", "left", "right", "q34", "q34l", "q34r", "q34b", "q34bl", "rback", "top34", "top", "topb")
SEAM_VIEWS = ("front", "q34")
SEAM_LEVEL = 12  # канал > 12 из 255 — пиксель шва отличается (как шум съёмки приёмки, capture_acceptance_set.py)
FRAME_TOKENS = ("mid", "last", "armL", "armR", "gripL", "gripR")
ROLES = ("idle", "oneshot", "terminal")
CLOSE_H = 0.33  # крупный план плеча / ворота — треть роста фигуры (≈ 16 см у фигур D-11, как ручные кадры пилота)
FIST_H = 0.22   # кулак с оружием


def default_shots(role: str, side: str = "R", weapon: bool = True) -> list:
    """Стандартный список кадров клипа по роли (C43/C45): строки `f:view:centre:size`. side — рука оружия (R/L).
    Общее для всех ролей — то, что валидаторы не ловят, а приёмщик видит: со спины 3/4 на кадре наибольшего поворота
    плеча каждой руки (срез рукава, кромка под плащом), ворот и затылок сзади и сзади сверху (провал ворота C61),
    кулак на кадре наибольшего поворота оружия (дыра кулака, C43). По роли — фигура целиком в ключевых кадрах."""
    if role not in ROLES:
        raise ValueError("роль %r: нужна одна из %s" % (role, ", ".join(ROLES)))
    if side not in ("R", "L"):
        raise ValueError("сторона оружия %r: R или L" % side)
    o = "L" if side == "R" else "R"
    back34 = {"R": "q34b", "L": "q34bl"}
    front34 = {"R": "q34r", "L": "q34l"}
    shots = ["arm%s:%s:@arm_upper.%s:h%s" % (side, back34[side], side, CLOSE_H),
             "arm%s:%s:@arm_upper.%s:h%s" % (o, back34[o], o, CLOSE_H),
             "arm%s:back:@head:h%s" % (side, CLOSE_H),
             "arm%s:topb:@head:h%s" % (side, CLOSE_H)]
    if weapon:
        shots.append("grip%s:%s:@hand.%s:h%s" % (side, front34[side], side, FIST_H))
    if role == "idle":
        shots += ["mid:q34:fig:auto", "mid:%s:fig:auto" % back34[side]]
    elif role == "oneshot":
        shots += ["arm%s:q34:fig:auto" % side, "arm%s:%s:fig:auto" % (side, back34[side])]
    else:
        shots += ["mid:%s:fig:auto" % back34[side], "last:q34:fig:auto", "last:%s:fig:auto" % back34[side],
                  "last:back:@head:h%s" % CLOSE_H, "last:topb:@head:h%s" % CLOSE_H,
                  "last:%s:@head:h%s" % (back34[o], CLOSE_H)]
    return shots


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_rel(p) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def parse_shots(text) -> list:
    """`f:view:centre:size;…` (или список таких строк) → [{frame, view, centre, size_cm[, size_h]}]; frame — число или
    правило FRAME_TOKENS, size_h — доля роста (`h0.33`). Ошибка формата — ValueError с причиной."""
    shots = []
    parts = text if isinstance(text, (list, tuple)) else (text or "").split(";")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        bits = part.split(":")
        if len(bits) != 4:
            raise ValueError("кадр %r: нужно f:view:centre:size" % part)
        fr, view, ctr, size = bits
        if fr not in FRAME_TOKENS:
            try:
                fr = int(fr)
            except ValueError:
                raise ValueError("кадр %r: номер кадра или правило %s" % (part, ", ".join(FRAME_TOKENS)))
        if view not in VIEWS:
            raise ValueError("кадр %r: вид %s не из %s" % (part, view, ", ".join(VIEWS)))
        if ctr == "fig":
            centre = {"kind": "fig"}
        elif ctr.startswith("@") and len(ctr) > 1:
            centre = {"kind": "bone", "bone": ctr[1:]}
        else:
            xyz = [float(x) for x in ctr.split(",")]
            if len(xyz) != 3:
                raise ValueError("кадр %r: центр — x,y,z см, @кость или fig" % part)
            centre = {"kind": "arm_cm", "value": xyz}
        size_h = None
        if size == "auto":
            if centre["kind"] != "fig":
                raise ValueError("кадр %r: size auto — только у центра fig" % part)
            size_cm = None
        elif size.startswith("h"):
            size_cm, size_h = None, float(size[1:])
            if not 0 < size_h <= 2:
                raise ValueError("кадр %r: доля роста h — от 0 до 2" % part)
        else:
            size_cm = float(size)
            if size_cm <= 0:
                raise ValueError("кадр %r: размер > 0" % part)
        shot = {"frame": fr, "view": view, "centre": centre, "size_cm": size_cm}
        if size_h is not None:
            shot["size_h"] = size_h
        shots.append(shot)
    return shots


def shots_from_report(rep: dict) -> tuple[list, dict | None, int | None]:
    """Кадры, камера шва и res прежнего отчёта — числами (центр в см осей арматуры, размер в см)."""
    shots = [{"frame": s["frame"], "view": s["view"], "centre": {"kind": "arm_cm", "value": s["centre_arm_cm"]},
              "size_cm": s["size_cm"], "from": s["name"]} for s in rep.get("shots") or []]
    seam = rep.get("seam")
    cams = None
    if seam:
        cams = {v: {"centre_arm_cm": m["centre_arm_cm"], "size_cm": m["size_cm"]} for v, m in seam["views"].items()}
    res = rep.get("res_px")
    return shots, cams, res


def name_shots(label: str, shots: list) -> list:
    """Имена `<label>-fNN-<view>`; повтор кадра и вида с другой камерой — суффикс -b, -c …"""
    seen = {}
    for s in shots:
        base = "%s-f%02d-%s" % (label, s["frame"], s["view"])
        k = seen.get(base, 0)
        seen[base] = k + 1
        s["name"] = base if k == 0 else "%s-%s" % (base, chr(ord("a") + k))
    return shots


def label_files(out: Path, label: str) -> list:
    pat = re.compile(r"^%s-(f\d{2,3}-[a-z0-9]+(-[a-z])?|seam-f\d{2,3}-f00-[a-z0-9]+)\.jpg$|^%s-closeups\.json$"
                     % (re.escape(label), re.escape(label)))
    return [p for p in out.iterdir() if p.is_file() and pat.match(p.name)] if out.is_dir() else []


def to_jpeg(png: Path, jpg: Path) -> list:
    from PIL import Image

    im = Image.open(png).convert("RGB")
    im.save(jpg, "JPEG", quality=QUALITY, subsampling=0, optimize=True)
    return list(im.size)


def seam_pair(last_png: Path, first_png: Path, out_jpg: Path, labels) -> dict:
    """Две портретные панели (кадр N | кадр 0) в один кадр; разница — по исходным PNG (без JPEG)."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    a, b = Image.open(last_png).convert("RGB"), Image.open(first_png).convert("RGB")
    x, y = np.asarray(a, dtype=np.int16), np.asarray(b, dtype=np.int16)
    d = np.abs(x - y)
    m = d.max(axis=2) > SEAM_LEVEL
    n = int(m.sum())
    bbox = None
    if n:
        ys, xs = np.nonzero(m)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    w, h = a.size
    canvas = Image.new("RGB", (2 * w, h))
    canvas.paste(a, (0, 0))
    canvas.paste(b, (w, 0))
    dr = ImageDraw.Draw(canvas)
    dr.line([(w, 0), (w, h)], fill=(170, 170, 170), width=2)
    try:
        font = ImageFont.truetype("arial.ttf", max(14, h // 40))
    except OSError:
        font = ImageFont.load_default()
    for i, t in enumerate(labels):
        dr.text((i * w + 12, 10), t, fill=(240, 240, 240), font=font)
    canvas.save(out_jpg, "JPEG", quality=QUALITY, subsampling=0, optimize=True)
    return {"size_px": list(canvas.size), "max": int(d.max()), "mean": round(float(d.mean()), 5),
            "diff_px": n, "diff_share": round(n / m.size, 6), "diff_bbox_px": bbox, "level": SEAM_LEVEL}


def resolve_inputs(a) -> dict:
    """--spec + --clip или --fbx: клип, подставка, label, out, шов по умолчанию."""
    if a.spec:
        spec_p = Path(a.spec).resolve()
        spec = json.loads(spec_p.read_text(encoding="utf-8"))
        if not a.clip or a.clip not in spec.get("clips", {}):
            raise ValueError("--clip — один из клипов спеки: %s" % ", ".join(spec.get("clips", {})))
        run = REPO / spec["run_dir"]
        fbx = run / "export" / ("AM_%s_%s.fbx" % (spec["ue_hero"], a.clip))
        base = Path(a.base).resolve() if a.base else REPO / spec["target"]["base_fbx"]
        label = a.label or "%s-%s" % (spec["ue_hero"], a.clip)
        out = Path(a.out).resolve() if a.out else run / "preview" / "closeups-blender"
        role = spec["clips"][a.clip].get("role")
        loop = role == "idle" or spec["clips"][a.clip].get("loop") is True
        wpn = spec.get("weapon") or {}
        return {"fbx": fbx, "base": None if a.no_base else base, "label": label, "out": out, "spec": spec_p,
                "clip": a.clip, "role": role, "seam_default": SEAM_VIEWS if loop else (),
                "side": getattr(a, "side", None) or wpn.get("side") or "R", "weapon": bool(wpn.get("bone"))}
    if not a.fbx or not a.out:
        raise ValueError("нужно --spec + --clip или --fbx + --out")
    fbx = Path(a.fbx).resolve()
    stem = fbx.stem[3:] if fbx.stem.startswith("AM_") else fbx.stem
    return {"fbx": fbx, "base": None if a.no_base or not a.base else Path(a.base).resolve(),
            "label": a.label or stem.replace("_", "-"), "out": Path(a.out).resolve(), "spec": None,
            "clip": stem.split("_")[-1], "role": getattr(a, "role", None), "seam_default": (),
            "side": getattr(a, "side", None) or "R", "weapon": True}


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # кириллица в Git Bash/агентах (консоль cp1251)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spec", help="<key>-h2anim.json: клип <run>/export/AM_<Hero>_<Clip>.fbx, подставка target.base_fbx")
    ap.add_argument("--clip", help="имя клипа спеки (Idle, LungeAttack, …)")
    ap.add_argument("--fbx", help="AM_<Key>_<Clip>.fbx без спеки")
    ap.add_argument("--base", help="SM_*_Base.fbx (со --spec — target.base_fbx)")
    ap.add_argument("--no-base", action="store_true")
    ap.add_argument("--out", help="каталог кадров (со --spec — <run>/preview/closeups-blender)")
    ap.add_argument("--label", help="префикс имён (по умолчанию <Hero>-<Clip>)")
    ap.add_argument("--shots", help="f:view:centre:size;… (см. описание)")
    ap.add_argument("--shots-from", help="отчёт *-closeups.json прежнего цикла: те же камеры числами")
    seam = ap.add_mutually_exclusive_group()
    seam.add_argument("--seam", help="виды пары шва через запятую (по умолчанию у Idle спеки — front,q34)")
    seam.add_argument("--no-seam", action="store_true")
    ap.add_argument("--res", type=int, help="сторона кадра, px (по умолчанию 1200 или res прежнего отчёта)")
    ap.add_argument("--default-shots", action="store_true",
                    help="стандартный список кадров по роли клипа (C43/C45; с --shots — добавляется к нему)")
    ap.add_argument("--role", choices=ROLES, help="роль клипа для --default-shots (по умолчанию из спеки)")
    ap.add_argument("--side", choices=("R", "L"), help="рука оружия для --default-shots (по умолчанию weapon.side спеки, R)")
    ap.add_argument("--backface-culling", choices=("on", "off"),
                    help="отсечение задних граней, как в UE (по умолчанию on с --default-shots, иначе как в --shots-from "
                         "или off)")
    ap.add_argument("--blender", default=DEFAULT_BLENDER)
    a = ap.parse_args(argv)
    try:
        inp = resolve_inputs(a)
        shots = parse_shots(a.shots)
        defaults = None
        if a.default_shots:
            role = a.role or inp["role"]
            if role not in ROLES:
                raise ValueError("--default-shots: роль клипа %r не из %s (--role)" % (role, ", ".join(ROLES)))
            defaults = {"role": role, "side": inp["side"], "weapon": inp["weapon"],
                        "list": default_shots(role, inp["side"], inp["weapon"])}
            shots = parse_shots(defaults["list"]) + shots
    except (ValueError, KeyError, OSError) as e:
        print("FAIL: %s" % e, file=sys.stderr)
        return 1
    for k in ("fbx", "base"):
        if inp[k] is not None and not inp[k].is_file():
            print("FAIL: нет файла %s" % inp[k], file=sys.stderr)
            return 1
    if not Path(a.blender).is_file():
        print("FAIL: нет Blender %s (--blender или env BLENDER)" % a.blender, file=sys.stderr)
        return 1
    prev_cams, prev_res, prev_path, prev_cull = None, None, None, None
    if a.shots_from:
        prev_path = Path(a.shots_from).resolve()
        try:
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print("FAIL: --shots-from %s: %s" % (a.shots_from, e), file=sys.stderr)
            return 1
        if prev.get("schema") != SCHEMA:
            print("FAIL: --shots-from %s: не %s" % (a.shots_from, SCHEMA), file=sys.stderr)
            return 1
        prev_shots, prev_cams, prev_res = shots_from_report(prev)
        prev_cull = bool((prev.get("look") or {}).get("backface_culling", False))
        shots = prev_shots + shots
    res = a.res or prev_res or RES
    if a.backface_culling:
        cull = a.backface_culling == "on"
    else:
        cull = True if defaults else bool(prev_cull)  # повтор --shots-from — тот же вид
    seam_views = [] if a.no_seam else ([v.strip() for v in a.seam.split(",") if v.strip()] if a.seam else
                                       (list(prev_cams) if prev_cams else list(inp["seam_default"])))
    bad = [v for v in seam_views if v not in VIEWS]
    if bad:
        print("FAIL: вид шва %s не из %s" % (bad, ", ".join(VIEWS)), file=sys.stderr)
        return 1
    if not shots and not seam_views:
        print("FAIL: нет кадров: --shots, --shots-from, --default-shots или --seam", file=sys.stderr)
        return 1
    out = inp["out"]
    out.mkdir(parents=True, exist_ok=True)
    for p in label_files(out, inp["label"]):  # повтор: прежние кадры этого label не смешиваются с новыми
        if prev_path is None or p.resolve() != prev_path:
            p.unlink()

    work = Path(tempfile.mkdtemp(prefix="clip-closeups-"))
    try:
        # правила кадра (mid, armR …) и размера (h0.33) переводит в числа Blender; там же имена кадров (name_shots)
        cfg = {"clip": str(inp["fbx"]), "base": str(inp["base"]) if inp["base"] else None, "work_dir": str(work),
               "res": res, "label": inp["label"],
               "shots": [{k: s.get(k) for k in ("frame", "view", "centre", "size_cm", "size_h")} for s in shots],
               "look": {"backface_culling": cull},
               "seam": ({"views": seam_views, "camera": {v: c for v, c in (prev_cams or {}).items() if v in seam_views}}
                        if seam_views else None)}
        (work / "cfg.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        cmd = [a.blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(BLENDER_SCRIPT),
               "--", str(work / "cfg.json")]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0 or "CLOSEUPS_OK" not in r.stdout:
            tail = "\n".join((r.stdout + r.stderr).splitlines()[-25:])
            print("FAIL: Blender завершился с кодом %s\n%s" % (r.returncode, tail), file=sys.stderr)
            return 1
        info = json.loads((work / "render.json").read_text(encoding="utf-8"))
        files, shots_out = [], []
        for s, m in zip(shots, info["shots"]):
            jpg = out / (m["name"] + ".jpg")
            m["size_px"] = to_jpeg(work / "raw" / (m["name"] + ".png"), jpg)
            m["file"], m["sha256"] = jpg.name, sha256(jpg)
            if s.get("from"):
                m["repeats"] = s["from"]
            shots_out.append(m)
            files.append(jpg.name)
        seam_out = None
        if info.get("seam"):
            n = info["seam"]["frames"][0]
            seam_out = {"frames": info["seam"]["frames"], "views": {}}
            for v, m in info["seam"]["views"].items():
                jpg = out / ("%s-seam-f%02d-f00-%s.jpg" % (inp["label"], n, v))
                pair = seam_pair(work / "raw" / m["raw"]["f%02d" % n], work / "raw" / m["raw"]["f00"], jpg,
                                 ("f%02d — последний кадр" % n, "f00 — первый кадр"))
                m.pop("raw", None)
                m.update(pair, file=jpg.name, sha256=sha256(jpg))
                seam_out["views"][v] = m
                files.append(jpg.name)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    report = {
        "schema": SCHEMA, "tool": "tools/tripo-pipeline/anim/clip_closeups.py", "label": inp["label"],
        "clip": {"name": inp["clip"], "role": inp["role"], "path": repo_rel(inp["fbx"]), "sha256": sha256(inp["fbx"])},
        "base": {"path": repo_rel(inp["base"]), "sha256": sha256(inp["base"])} if inp["base"] else None,
        "spec": repo_rel(inp["spec"]) if inp["spec"] else None,
        "shots_from": repo_rel(prev_path) if prev_path else None,
        "blender": info["blender"], "frame_range": {"start": info["frame_start"], "end": info["frame_end"],
                                                    "last_frame": info["last_frame"], "fps": info["fps"]},
        "res_px": res, "jpeg_quality": QUALITY, "look": info["look"],
        "axes": "центр — см осей арматуры (+X лицо, +Y левый бок, +Z вверх), как rest_measured спеки; вид — "
                "направление от фигуры к камере",
        "shots": shots_out, "seam": seam_out, "files": sorted(files),
        "repeat": "python tools/tripo-pipeline/anim/clip_closeups.py … --shots-from <этот отчёт> — те же камеры",
        "kind": "диагностика и вход приёмки клипа (§10.3), не K1/K2",
    }
    if defaults:  # только при --default-shots / правилах кадра: прежние отчёты без этих ключей
        report["default_shots"] = {k: defaults[k] for k in ("role", "side", "weapon", "list")}
    if info.get("frame_tokens"):
        report["frame_tokens"] = info["frame_tokens"]
    if info.get("figure_height_f0_m"):
        report["figure_height_f0_m"] = info["figure_height_f0_m"]
    rep_path = out / ("%s-closeups.json" % inp["label"])
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if seam_out:
        for v, m in seam_out["views"].items():
            print("seam %s: f%02d vs f00 max %d, пикселей > %d: %d" % (v, seam_out["frames"][0], m["max"], SEAM_LEVEL,
                                                                    m["diff_px"]))
    print("OK: %d кадров%s -> %s" % (len(shots_out), " + шов %s" % ",".join(seam_out["views"]) if seam_out else "",
                                     repo_rel(rep_path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
