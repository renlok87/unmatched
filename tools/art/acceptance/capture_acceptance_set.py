#!/usr/bin/env python3
"""Кадры приёмки модели (этап 4 скилла 3d-model-pipeline, DECISIONS Р-6.1).

    python tools/art/acceptance/capture_acceptance_set.py --fbx <SK_*.fbx> --textures <dir> --out <evidence>/frames \
        [--key <Key>] [--sheet <sheet-<key>.png>] [--side-view left|right] [--measure <measure-report.json>] \
        [--allow-no-tone] [--blender <exe>] [--base <SM_*_Base.fbx> | --no-base] [--previous <frames dir> | none] \
        [--asset-card <asset-card.yaml>] [--attack-bone <кость> | none] [--rules auto|1|2]

Правила v2 (--rules auto: профиль H2 прогона с profile_version ≥ 2 или ASSET_ID заявки вне MVP и пилота; проверочный
прогон Beowulf 2026-10-14): задние грани отсекаются, как в UE (C22: крышка, видимая только изнанкой, на кадре — дыра);
панель кисти close-hands снимается с ракурса наибольшей видимости, если с ракурса по умолчанию её закрывает деталь на
предплечье (C30: щит); uv-layout.png и uv_islands — без внутренней копии оболочки rig.cloth_shell и её мостов (C36).
frames.json#rules — что включено и откуда. У профилей v1 кадры и frames.json прежние.

Вход: отгружаемый скелетный FBX (UM_FBX_v1, `HANDBOOK §2.2`) и каталог его текстур. Из каталога берутся BC, N
(DirectX, `HANDBOOK §2.4`) и ORM: `*_BC.png` / `*_2K_BC.png` / `*_BC_2K.png` (последнее — раскладка форков Arthur и
Merlin), то же для `_N` (не `_N_OpenGL`) и `_ORM`; при нескольких кандидатах — 2K (рантайм-набор героя), при `--key` —
только `T_<Key>_*`. Подставка: `--base`, иначе соседний `SM_<имя SK без SK_>_Base.fbx` в каталоге FBX (атлас общий),
`--no-base` — без неё. Лист концепта `--sheet` копируется в `frames/sheet.png` не больше 1200 px по длинной стороне (свотчи и виды —
по соседнему `checks-report.json`, если есть). Тон классов — `--measure`, иначе `<run>/reports/measure-report.json`
рядом с `<run>/export/` FBX, если есть → `frames/tone.json` (`_tone.py`). У героя (есть арматура) без measure-report
съёмка — код 1; `--allow-no-tone` — только ассет старше `ld_measure` (форки Arthur/Merlin/Harpy, калибровка).

Выход (`--out`), имена фиксированы:
  turn-000.jpg … turn-315.jpg   8 ракурсов через 45 deg, орто, возвышение 0; 000 = спереди, 090 = левый бок фигуры
                                (сторона .L), 180 = сзади, 270 = правый бок; текстуры BC+N+ORM (EEVEE, AgX)
  close-head.jpg                крупно голова (вершины группы head; нет — верх 22 % роста)
  close-weapon.jpg              крупно хват: голова кости weapon.L|R + кисть той же стороны (нет кости — верх фигуры)
  close-hands.jpg               при арматуре: две панели — hand.R слева, hand.L справа
  close-torso.jpg               при арматуре: корпус (вершины группы spine)
  close-head-back.jpg           при арматуре: голова со спины (az 205)
  close-torso-back.jpg          при арматуре: спина, задняя сторона плеч, колчан, верх плаща (az 200)
  close-legs.jpg                при арматуре: ноги и низ одежды (hips, leg_*, foot.*) спереди-справа (az 340)
  close-legs-back.jpg           при арматуре: то же со спины (az 160)
  close-base.jpg                подставка сверху-сбоку (без подставки — нижние 22 % модели)
  wire-front.jpg, wire-34.jpg, wire-back.jpg
                                сетка треугольников на глине: спереди, 3/4 сверху (az 45, el 15) и сзади (az 180)
  uv-layout.png                 UV0 атласа поверх затемнённого BC: рисуется 1600 px (покрытие считается на нём), файл —
                                не больше 1200 px по длинной стороне, PNG с палитрой 256 цветов
  pose-01.jpg … pose-04.jpg     только при арматуре: позы из тестов tools/tripo-pipeline/anim/rig_deform_probe.py
  pose-03b.jpg                  поза pose-03 со второго ракурса (где оружие и голова разведены сильнее всего)
  pose-04b.jpg                  при арматуре: поза pose-04 со второго ракурса — азимут (шаг 30°, не ближе 60° к az 70
                                pose-04), где таз и поднятое бедро видны лучше всего (F77: у Achilles их закрывал щит)
  pose-05.jpg                   при арматуре: рука оружия (без оружия — атакующая, иначе правая) вперёд (плечо X −70°,
                                предплечье X −20°), со спины 3/4 этой стороны (R az 225, L az 135); рамка — верх фигуры
                                от тазобедренного сустава, оружие не в рамке (F129: кромка проймы плаща за подмышкой)
  close-attack.jpg              только при кости атаки (WEAPON_HAND none заявки → WEAPON_SOCKET_BONE, или --attack-bone):
                                две панели 600x1200 по группе этой кости — бок и спина 3/4 (F74: когти/кисть без оружия)
  sheet.png                     копия --sheet, не больше 1200 px по длинной стороне (оригинал — frames.json#sheet.source)
  compare-front.jpg, compare-side.jpg, compare-back.jpg
                                вид листа | turn-000 / turn-090|270 (--side-view) / turn-180 в одном росте фигуры
                                (верх фигуры и низ подставки совпадают), направляющие через 10 % роста; если у листа
                                есть checks-report.json с видами; не больше 1200 px по длинной стороне (виды листа
                                берутся из оригинала листа, не из sheet.png)
  tone.json                     тон классов против концепта (если есть measure-report.json)
  frames.json                   schema unmatched.acceptance-frames/1: входы с sha256, accepted_object (SK, SM и 2K-карты
                                для карточки), камеры, позы, pose_checks, лист, проверки, changed_vs_previous, roles
                                (файл → что на нём смотреть; у каждого кадра frames[].role), attack
Новые кадры пилота 2026-10-14 (pose-04b, pose-05, close-attack) — добавочные: имена прежних не менялись, validate_card.py
их не требует (старые карточки без них проходят); pose-05 обрезан намеренно (проверка края кадра его не касается).
Кость атаки: --attack-bone (none — не снимать), иначе asset-card.yaml ассета (--asset-card, по умолчанию ближайший
asset-card.yaml вверх от --fbx): WEAPON_HAND none и WEAPON_SOCKET_BONE не null → эта кость. У героя с оружием
close-attack не снимается (хват — close-weapon), если кость не задана флагом.
Кадры приёмщика — не больше 1200 px по длинной стороне (HANDBOOK §8; RC-22/F97: приёмщик Sol получает все файлы
frames.json#files картинками, лишние мегабайты — переподключения WebSocket): JPEG 1200 px, качество 92; sheet.png и
uv-layout.png остаются PNG (имена требует validate_card.py). Blender — headless (`-b --factory-startup`), процесс
завершается сам.
Повторный цикл (F151, RC-19): `--previous <каталог frames прежнего цикла>`; без флага — сам, если `--out` лежит в
`<YYYYMMDD>-r<N>/frames` и рядом есть `<дата>-r<N-1>/frames/frames.json` (N ≥ 2); `--previous none` — не сравнивать.
Каждый кадр сравнивается попиксельно с одноимённым кадром прежнего цикла → frames.json#changed_vs_previous (кадр →
max/mean разницы, число пикселей выше шума, рамка, changed). Это вход запускающего (какие кадры смотрит второй
приёмщик), а не основание балла.
Код выхода: 0 — все кадры есть и автопроверки прошли; 1 — ошибка входа, Blender или проверки кадров.
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
BLENDER_SCRIPT = HERE / "_blender_capture.py"
PROBE_SOURCE = REPO / "tools" / "tripo-pipeline" / "anim" / "rig_deform_probe.py"
DEFAULT_BLENDER = os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
SIZE, QUALITY, UV_SIZE = 1200, 92, 1600
# Кадр приёмщика не больше 1200 px по длинной стороне (HANDBOOK §8 «JPEG 1200 px q92»; RC-22/F97, пилот 2026-10-13:
# лист 2000 px, uv-layout 1600×1776 и compare 1376 px — PNG по 1,8–3,1 МБ на каждую приёмку Sol). Раньше — 2000.
REVIEW_PX = 1200
MAX_REVIEW_PX = 2000  # предел наборов до 2026-10-14 (Read уменьшает картинку больше 2000 px); новые — REVIEW_PX
UV_FOOTER_MAX = 400  # подпись под атласом UV_SIZE (до уменьшения)
BG = (72, 72, 72)  # нейтральный тёмно-серый фон кадров (решение скилла)
# Сравнение с прежним циклом (F151, RC-19). Пиксель изменён, если разница какого-либо канала больше NOISE_LEVEL из
# 255; кадр изменён, если таких пикселей не меньше NOISE_MIN_PX. Основание: Achilles r2 → r3 (правка только весов,
# тот же рендер) — 29 кадров из 30 с разницей канала ≤ 7 и 0 пикселей > 8, pose-02 — 6267 пикселей > 16;
# r1 → r2 (крышки ворота) — wire-front 14 пикселей > 16.
NOISE_LEVEL, NOISE_MIN_PX = 12, 4
CYCLE_DIR = re.compile(r"^(\d{8})-r(\d+)$")
TURNS = ["turn-%03d.jpg" % a for a in range(0, 360, 45)]
FIXED = TURNS + ["close-head.jpg", "close-weapon.jpg", "close-base.jpg", "wire-front.jpg", "wire-34.jpg",
                 "wire-back.jpg"]
RIG_ONLY = (["close-hands.jpg", "close-torso.jpg", "close-head-back.jpg", "close-torso-back.jpg", "close-legs.jpg",
             "close-legs-back.jpg"] + ["pose-%02d.jpg" % i for i in range(1, 5)] + ["pose-03b.jpg"])
# Добавочные кадры пилота 2026-10-14 (F77, F129) — при арматуре; close-attack (F74) — при кости атаки. validate_card.py
# их не требует: карточки наборов до 2026-10-14 остаются валидными.
RIG_EXTRA = ["pose-04b.jpg", "pose-05.jpg"]
ATTACK_FRAME = "close-attack.jpg"
CROPPED = {"pose-05.jpg"}  # обрезан намеренно (верх фигуры): проверка «фигура касается края» не применяется
PANELS = {"close-hands-": ("close-hands.jpg", "две панели 600x1200: hand.R слева, hand.L справа"),
          "close-attack-": ("close-attack.jpg", "две панели 600x1200: бок слева, спина 3/4 справа")}
# Что смотреть на кадре (frames.json#roles и frames[].role): вход запускающего и приёмщика, не основание балла
ROLES = {
    **{t: "поворот %s°: силуэт, пропорции, палитра против листа" % t[5:8] for t in TURNS},
    "close-head.jpg": "голова 3/4 спереди: лицо, волосы, головной убор",
    "close-head-back.jpg": "голова со спины: затылок, волосы/змеи сзади",
    "close-weapon.jpg": "хват оружия: кисть и рукоять (без кости оружия — верх фигуры)",
    "close-hands.jpg": "обе кисти 3/4 спереди (hand.R | hand.L): пальцы, когти, наручи",
    "close-torso.jpg": "корпус 3/4 спереди: доспех, ткань, стыки плеч",
    "close-torso-back.jpg": "спина: задняя сторона плеч, колчан, верх плаща",
    "close-legs.jpg": "ноги и низ одежды 3/4 спереди",
    "close-legs-back.jpg": "ноги и низ одежды со спины",
    "close-base.jpg": "подставка со стопами: края, просвет, контакт",
    "wire-front.jpg": "сетка спереди: плотность и потоки",
    "wire-34.jpg": "сетка 3/4 сверху",
    "wire-back.jpg": "сетка сзади: спина, затылок, плащ",
    "uv-layout.png": "развёртка UV0 поверх BC: острова, покрытие",
    "pose-01.jpg": "поза: левая рука поднята, предплечье согнуто — плечо, локоть, стык с корпусом",
    "pose-02.jpg": "поза: правая рука поднята — плечо, подмышка",
    "pose-03.jpg": "поза: наклон корпуса и поворот головы — шея, талия, оружие у головы",
    "pose-03b.jpg": "pose-03 со второго ракурса: оружие и голова разведены",
    "pose-04.jpg": "поза: левое бедро поднято — таз, юбка/подол",
    "pose-04b.jpg": "pose-04 со второго ракурса: таз, поднятое бедро и юбка/подол без заслона (F77)",
    "pose-05.jpg": "рука оружия вперёд, спина 3/4: пройма плаща, подмышка, задняя сторона плеча (F129)",
    ATTACK_FRAME: "атакующая конечность без оружия, бок и спина 3/4: когти/кисть целиком (F74)",
    "sheet.png": "лист концепта (эталон S)",
    "compare-front.jpg": "лист | turn-000 в одном росте",
    "compare-side.jpg": "лист | боковой turn в одном росте",
    "compare-back.jpg": "лист | turn-180 в одном росте",
    "tone.json": "тон классов против концепта, потолок T",
    "frames.json": "манифест набора",
}
CARD_KEY = re.compile(r"^(?P<k>[A-Z_]+):\s*(?P<v>\"[^\"]*\"|[^#\n]*?)\s*(#.*)?$", re.MULTILINE)
COMPARE = {"front": "compare-front.jpg", "side": "compare-side.jpg", "back": "compare-back.jpg"}
STALE = re.compile(r"(turn-\d{3}|close-[a-z]+(-[a-z]+)?|wire-\w+|pose-\d{2}b?|compare-[a-z]+)\.jpg|uv-layout\.png"
                   r"|sheet\.png|frames\.json|tone\.json")
# accepted_object карточки модели: SK, SM и 2K-карты (acceptance-and-blender.md §2.1); Edge у форков — EdgeMask
ACCEPTED_MAPS = [("BC", ("_BC",)), ("N", ("_N",)), ("ORM", ("_ORM",)), ("MatID", ("_MatID",)),
                 ("Edge", ("_Edge", "_EdgeMask")), ("TeamAccent", ("_TeamAccent",))]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_rel(p: Path) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def kebab(key: str) -> str:
    """UE-ключ PascalCase -> content-key kebab: KingArthur -> king-arthur, Medusa -> medusa."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", key).replace("_", "-").lower()


def pick_texture(tdir: Path, suffix: str, key: str | None) -> Path:
    """Карта `suffix` (`_BC`, `_N`, `_ORM`) в каталоге: имена `*<suffix>.png`, `*_2K<suffix>.png` (генерический
    look-dev, HANDBOOK §2.3) и `*<suffix>_2K.png` / `*<suffix>_4K.png` (форки Arthur/Merlin). `_N_OpenGL` не берётся.
    Из нескольких — 2K; 4K-мастер — только если 2K нет."""
    pat = re.compile(r"^.+%s(_[24]K)?$" % re.escape(suffix))
    cands = [p for p in sorted(tdir.glob("*.png")) if pat.match(p.stem)]
    if key:
        cands = [p for p in cands if p.name.startswith("T_%s_" % key)]
    if not cands:
        raise SystemExit("нет текстуры *%s.png в %s%s" % (suffix, tdir, " для T_%s_*" % key if key else ""))
    two_k = [p for p in cands if "_2K_" in p.name or p.stem.endswith("_2K")]
    not_4k = [p for p in cands if not p.stem.endswith("_4K")]
    pool = two_k or not_4k or cands
    if len(pool) > 1:
        raise SystemExit("неоднозначно *%s.png в %s: %s (укажите --key)" % (suffix, tdir, [p.name for p in pool]))
    return pool[0]


def accepted_maps(tdir: Path, key: str | None) -> tuple[list, list]:
    """2K-карты для accepted_object: [(вид, путь)], [недостающие виды]. У пропа обычно только BC/N/ORM."""
    found, missing = [], []
    for kind, suffixes in ACCEPTED_MAPS:
        for suf in suffixes:
            try:
                found.append((kind, pick_texture(tdir, suf, key)))
                break
            except SystemExit:
                continue
        else:
            missing.append(kind)
    return found, missing


def find_base(fbx: Path) -> Path | None:
    stem = fbx.stem[3:] if fbx.stem.startswith("SK_") else fbx.stem
    p = fbx.with_name("SM_%s_Base.fbx" % stem)
    return p if p.exists() else None


def _font(size):
    from PIL import ImageFont

    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def draw_uv_layout(npz_path: Path, bc_path: Path, out_png: Path, meshes_info: dict) -> dict:
    import numpy as np
    from PIL import Image, ImageDraw

    data = np.load(npz_path)
    names = sorted({k.split("__")[0] for k in data.files})
    S = UV_SIZE
    bg = Image.open(bc_path).convert("RGB").resize((S, S), Image.LANCZOS)
    bg = Image.eval(bg, lambda v: int(v * 0.35))
    fill = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    lines = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lines)
    rng = np.random.default_rng(0)
    stats = {}
    for name in names:
        uv = data[name + "__uv"].astype(np.float64)
        px = np.stack([uv[:, 0] * S, (1.0 - uv[:, 1]) * S], axis=1)
        tri = data[name + "__tri"]
        isl = data[name + "__tri_island"]
        n_isl = int(isl.max()) + 1 if len(isl) else 0
        cols = rng.integers(60, 255, size=(max(n_isl, 1), 3))
        for t, i in zip(tri, isl):
            c = cols[i]
            fd.polygon([tuple(px[t[0]]), tuple(px[t[1]]), tuple(px[t[2]])], fill=(int(c[0]), int(c[1]), int(c[2]), 90))
        for t in tri:
            a, b, c = (tuple(px[t[0]]), tuple(px[t[1]]), tuple(px[t[2]]))
            ld.line([a, b, c, a], fill=(255, 255, 255, 55), width=1)
        for a, b in data[name + "__bedge"]:
            ld.line([tuple(px[a]), tuple(px[b])], fill=(255, 214, 0, 255), width=2)
        out_of_unit = int(((uv < -1e-6) | (uv > 1 + 1e-6)).any(axis=1).sum())
        stats[name] = {"triangles": int(len(tri)), "uv_islands": n_isl, "loops_outside_0_1": out_of_unit}
    alpha = np.asarray(fill)[..., 3] > 0
    coverage = float(alpha.mean())
    atlas = bg.convert("RGBA")
    atlas.alpha_composite(fill)
    atlas.alpha_composite(lines)
    font = _font(24)
    legend = ["UV0 atlas (%s), coverage %.1f %%" % (bc_path.name, coverage * 100)]
    legend += ["%s: %d tris, %d islands" % (n, s["triangles"], s["uv_islands"]) for n, s in stats.items()]
    legend += ["yellow = island border, fill colour = island, dim background = BaseColor"]
    footer = min(16 + 32 * len(legend), UV_FOOTER_MAX)  # подпись под атласом, чтобы не закрывать острова
    img = Image.new("RGBA", (S, S + footer), (24, 24, 24, 255))
    img.paste(atlas, (0, 0))
    d = ImageDraw.Draw(img)
    y = S + 10
    for t in legend:
        if y + 28 > S + footer:
            break
        d.text((14, y), t, fill=(255, 255, 255, 255), font=font)
        y += 32
    # покрытие посчитано на UV_SIZE (как раньше); файл приёмщика — не больше REVIEW_PX, палитра 256 цветов (схема, не
    # фото: 1600×1776 RGB весил 3,1 МБ)
    review = fit_long_side(img.convert("RGB"), REVIEW_PX)
    review.quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(out_png, optimize=True)
    return {"size_px": list(review.size), "drawn_px": [S, S + footer], "coverage": round(coverage, 4),
            "meshes": stats}


def fit_long_side(im, px: int = REVIEW_PX):
    """Картинка не больше px по длинной стороне (LANCZOS); меньшая не увеличивается."""
    from PIL import Image

    w, h = im.size
    s = px / max(w, h)
    if s >= 1.0:
        return im
    return im.resize((max(1, round(w * s)), max(1, round(h * s))), Image.LANCZOS)


def compose_panels(left_png: Path, right_png: Path, out_png: Path, labels=("hand.R", "hand.L")) -> None:
    """Две портретные RGBA-панели (w x 2w) -> один квадратный кадр 2w x 2w; подписи панелей вверху слева."""
    from PIL import Image, ImageDraw

    a, b = Image.open(left_png).convert("RGBA"), Image.open(right_png).convert("RGBA")
    w, hgt = a.size
    out = Image.new("RGBA", (w * 2, hgt), (0, 0, 0, 0))
    out.paste(a, (0, 0))
    out.paste(b, (w, 0))
    d = ImageDraw.Draw(out)
    d.line([(w, 0), (w, hgt)], fill=(150, 150, 150, 255), width=2)
    font = _font(26)
    for i, t in enumerate(labels):
        d.text((i * w + 14, 10), t, fill=(235, 235, 235, 255), font=font)
    out.save(out_png)


def copy_sheet(sheet: Path, out_png: Path) -> dict:
    """Лист -> frames/sheet.png не больше REVIEW_PX по длинной стороне (RC-22; раньше — ширина 2000). Остаётся PNG:
    имя sheet.png требует validate_card.py. Оригинал — frames.json#sheet.source (виды compare-* берутся из него)."""
    from PIL import Image

    im = Image.open(sheet)
    w, h = im.size
    if max(w, h) > REVIEW_PX:
        small = fit_long_side(im.convert("RGB"), REVIEW_PX)
        small.save(out_png, optimize=True)
        return {"size_px": list(small.size), "resized_from_px": [w, h]}
    shutil.copyfile(sheet, out_png)
    return {"size_px": [w, h], "resized_from_px": None}


def sheet_info(sheet: Path, key: str | None = None) -> dict:
    """Свотчи и виды листа: из соседнего checks-report.json (check_concept_views.py), если он есть; ключ листа."""
    info = {"source": repo_rel(sheet), "source_sha256": sha256(sheet), "sha256": None, "swatches": None,
            "compare_palette_by": "views", "checks_report": None, "views": {}, "content_key": None, "key_match": None}
    rep = sheet.with_name("checks-report.json")
    if rep.is_file():
        try:
            data = json.loads(rep.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        info["checks_report"] = repo_rel(rep)
        info["swatches"] = len(((data.get("palette") or {}).get("swatches") or [])) or None
        info["content_key"] = data.get("key")
        meas = data.get("measurements") or {}
        for inp in data.get("inputs") or []:
            v = inp.get("view")
            bbox = ((meas.get(v) or {}).get("mask") or {}).get("bbox_px")
            if v and inp.get("path") and bbox:
                info["views"][v] = {"path": inp["path"], "sha256": inp.get("sha256"), "bbox_px": bbox}
    if info["swatches"]:
        info["compare_palette_by"] = "swatches"
    if key:
        want = kebab(key)
        have = info["content_key"] or re.sub(r"^sheet-", "", sheet.stem)
        info["key_match"] = have == want
    return info


def card_scalars(text: str, keys=("WEAPON_HAND", "WEAPON_SOCKET_BONE")) -> dict:
    """Скаляры верхнего уровня asset-card.yaml (первое вхождение ключа в начале строки): строки без кавычек, null → None."""
    out = {}
    for m in CARD_KEY.finditer(text):
        k = m.group("k")
        if k in keys and k not in out:
            v = m.group("v").strip().strip('"')
            out[k] = None if v in ("", "null", "~") else v
    return out


def find_asset_card(start: Path) -> Path | None:
    """Ближайший asset-card.yaml вверх от start (каталог ассета art/pipeline-candidates/<ASSET>/)."""
    for d in [start] + list(start.parents):
        p = d / "asset-card.yaml"
        if p.is_file():
            return p
        if d == REPO:
            break
    return None


def resolve_attack(flag: str | None, card: dict | None) -> tuple[str | None, str | None]:
    """Кость атаки для close-attack (F74) и её источник: --attack-bone (none — не снимать); иначе заявка: WEAPON_HAND
    none и WEAPON_SOCKET_BONE не null. Иначе (None, None)."""
    if flag is not None:
        return (None, "--attack-bone none") if flag.lower() == "none" else (flag, "--attack-bone")
    card = card or {}
    if (card.get("WEAPON_HAND") or "").lower() == "none" and card.get("WEAPON_SOCKET_BONE"):
        return card["WEAPON_SOCKET_BONE"], "asset-card WEAPON_HAND none → WEAPON_SOCKET_BONE"
    return None, None


H2_PROFILE_PY = REPO / "tools" / "tripo-pipeline" / "blender" / "h2_bake" / "profile.py"


def _h2_profile():
    """h2_bake/profile.py (без bpy): SCHEMA, LEGACY_ASSETS, profile_version."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("accept_h2_profile", H2_PROFILE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def detect_rules(fbx: Path, card_text: str | None = None) -> tuple[int | None, str]:
    """Версия правил съёмки (C22, C30, C36: правила v2 — профиль H2 с profile_version ≥ 2): профиль прогона FBX
    (<run>/reports/run-manifest.json → source_profile.path у look-dev, profile.path у bake), иначе ASSET_ID заявки
    (ассеты MVP и пилота — 1, остальные — 2). → (1 | 2 | None, источник)."""
    pr = _h2_profile()
    man = fbx.parent.parent / "reports" / "run-manifest.json"
    if fbx.parent.name == "export" and man.is_file():
        try:
            m = json.loads(man.read_text(encoding="utf-8"))
            rel = (m.get("source_profile") or {}).get("path") or (m.get("profile") or {}).get("path")
            p = Path(rel) if rel and Path(rel).is_absolute() else REPO / (rel or "")
            prof = json.loads(p.read_text(encoding="utf-8")) if rel and p.is_file() else None
        except (OSError, ValueError):
            prof = None
        if isinstance(prof, dict) and prof.get("schema") == pr.SCHEMA:
            return int(pr.profile_version(prof)), "профиль H2 %s (run-manifest.json)" % rel
    if card_text:
        aid = card_scalars(card_text, keys=("ASSET_ID",)).get("ASSET_ID")
        if aid:
            return (1 if aid in pr.LEGACY_ASSETS else pr.NEW_HERO_PROFILE_VERSION), "asset-card ASSET_ID %s" % aid
    return None, "нет профиля H2 и заявки: правила v1"


def find_measure(fbx: Path) -> Path | None:
    """<run>/reports/measure-report.json для FBX в <run>/export/ (генерический look-dev, стадия ld_measure)."""
    p = fbx.parent.parent / "reports" / "measure-report.json"
    return p if fbx.parent.name == "export" and p.is_file() else None


def finish_frame(raw_png: Path, out_jpg: Path) -> dict:
    """RGBA-рендер -> JPEG q92 на ровном нейтральном сером фоне BG; проверки по альфе: доля фигуры, касание краёв,
    рамка фигуры (bbox_px: x0, y0, x1, y1 включительно)."""
    import numpy as np
    from PIL import Image

    im = Image.open(raw_png).convert("RGBA")
    a = np.asarray(im)[..., 3]
    m = a > 8
    flat = Image.new("RGBA", im.size, BG + (255,))
    flat.alpha_composite(im)
    flat.convert("RGB").save(out_jpg, "JPEG", quality=QUALITY, subsampling=0, optimize=True)
    touches = bool(m[0].any() or m[-1].any() or m[:, 0].any() or m[:, -1].any())
    ys, xs = np.nonzero(m)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    return {"size": [im.size[0], im.size[1]], "foreground_share": round(float(m.mean()), 4), "touches_border": touches,
            "bbox_px": bbox}


COMPARE_FIG_PX = 1000   # рост фигуры (верх — низ подставки) на compare-*: как на turn-* (~1000 px)
COMPARE_MARGIN = 100


def compare_frame(view_png: Path, view_bbox, turn_jpg: Path, turn_bbox, out_jpg: Path, labels) -> dict:
    """Вид листа | кадр turn-* в одном росте фигуры: обе фигуры от верха до низа подставки = COMPARE_FIG_PX, низ на
    одной линии, направляющие через 10 % роста (подписи 0 % сверху … 100 % у низа подставки). Готовый кадр — не больше
    REVIEW_PX по длинной стороне (RC-22; раньше — ширина 2000), figure_px — рост фигуры после уменьшения."""
    from PIL import Image, ImageDraw

    panels = []
    for src, bb in ((view_png, view_bbox), (turn_jpg, turn_bbox)):
        im = Image.open(src).convert("RGB")
        x0, y0, x1, y1 = bb
        fh = max(y1 - y0 + 1, 1)
        pad = int(round(0.03 * fh))
        crop = im.crop((max(x0 - pad, 0), y0, min(x1 + 1 + pad, im.size[0]), y1 + 1))
        s = COMPARE_FIG_PX / fh
        panels.append(crop.resize((max(1, round(crop.size[0] * s)), COMPARE_FIG_PX), Image.LANCZOS))
    pw = max(p.size[0] for p in panels) + 80
    W, H = 2 * pw, COMPARE_FIG_PX + 2 * COMPARE_MARGIN
    canvas = Image.new("RGB", (W, H), BG)
    for i, p in enumerate(panels):
        canvas.paste(p, (i * pw + (pw - p.size[0]) // 2, COMPARE_MARGIN))
    d = ImageDraw.Draw(canvas, "RGBA")
    font = _font(22)
    for k in range(11):
        y = COMPARE_MARGIN + round(COMPARE_FIG_PX * k / 10)
        d.line([(0, y), (W, y)], fill=(255, 214, 0, 150 if k in (0, 10) else 80), width=2 if k in (0, 10) else 1)
        d.text((6, y - 24 if k else y + 4), "%d %%" % (k * 10), fill=(255, 214, 0, 220), font=font)
    d.line([(pw, 0), (pw, H)], fill=(170, 170, 170, 255), width=2)
    for i, t in enumerate(labels):
        d.text((i * pw + 70, 12), t, fill=(240, 240, 240, 255), font=_font(28))
    scale = min(1.0, REVIEW_PX / max(W, H))
    if scale < 1.0:
        canvas = canvas.resize((round(W * scale), round(H * scale)), Image.LANCZOS)
    canvas.save(out_jpg, "JPEG", quality=QUALITY, subsampling=0, optimize=True)
    return {"size": list(canvas.size), "figure_px": round(COMPARE_FIG_PX * scale), "labels": list(labels)}


# ---------------------------------------------------------------------- сравнение с прежним циклом (F151, RC-19)

def find_previous(out: Path) -> Path | None:
    """Каталог кадров прежнего цикла: --out = …/<YYYYMMDD>-r<N>/frames (N ≥ 2) → …/<любая дата>-r<N-1>/frames с
    frames.json (несколько дат — последняя по имени). Иначе None."""
    run = out.parent
    m = CYCLE_DIR.match(run.name)
    if not m or int(m.group(2)) < 2 or not run.parent.is_dir():
        return None
    want = int(m.group(2)) - 1
    cands = sorted(p / out.name for p in run.parent.iterdir()
                   if p.is_dir() and CYCLE_DIR.match(p.name) and int(CYCLE_DIR.match(p.name).group(2)) == want
                   and (p / out.name / "frames.json").is_file())
    return cands[-1] if cands else None


def frame_diff(prev: Path, cur: Path, level: int = NOISE_LEVEL, min_px: int = NOISE_MIN_PX) -> dict:
    """Попиксельная разница двух кадров (RGB, 0–255): max и mean по каналам, changed_px — пиксели, где разница
    какого-либо канала больше level, их доля и рамка [x0, y0, x1, y1]; changed — changed_px ≥ min_px. Разный размер —
    changed true, comparable false (кадры не сравнить попиксельно: смотреть оба)."""
    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(prev).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(cur).convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        return {"changed": True, "comparable": False,
                "reason": "размер %dx%d → %dx%d" % (a.shape[1], a.shape[0], b.shape[1], b.shape[0])}
    d = np.abs(a - b)
    m = d.max(axis=2) > level
    n = int(m.sum())
    bbox = None
    if n:
        ys, xs = np.nonzero(m)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    return {"changed": n >= min_px, "comparable": True, "max": int(d.max()), "mean": round(float(d.mean()), 5),
            "changed_px": n, "changed_share": round(n / m.size, 6), "bbox_px": bbox}


def _json_body(p: Path):
    """JSON без блока sources (пути прогонов меняются от цикла к циклу, содержимое — нет)."""
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = {k: v for k, v in data.items() if k != "sources"}
    return data


def changed_vs_previous(prev_dir: Path, out: Path, files: list, fbx_sha: str | None = None,
                        source: str = "--previous") -> dict:
    """Блок frames.json#changed_vs_previous: каждый файл frames.json#files (кроме самого frames.json) против
    одноимённого файла прежнего цикла. Картинки — frame_diff, JSON (tone.json) — содержимое без sources."""
    prev_man = None
    if (prev_dir / "frames.json").is_file():
        try:
            prev_man = json.loads((prev_dir / "frames.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            prev_man = None
    prev_fbx = ((prev_man or {}).get("inputs") or {}).get("fbx") or {}
    per, changed, unchanged, not_comparable = {}, [], [], []
    for name in files:
        if name == "frames.json":
            continue
        cur, old = out / name, prev_dir / name
        if not old.is_file():
            rec = {"changed": True, "comparable": False, "reason": "нет в прежнем цикле"}
        elif name.lower().endswith((".jpg", ".jpeg", ".png")):
            rec = frame_diff(old, cur)
        else:
            try:
                rec = {"changed": _json_body(old) != _json_body(cur), "comparable": True, "kind": "json без sources"}
            except (OSError, ValueError) as e:
                rec = {"changed": True, "comparable": False, "reason": "не читается: %s" % e}
        per[name] = rec
        (changed if rec["changed"] else unchanged).append(name)
        if not rec.get("comparable", True):
            not_comparable.append(name)
    prev_files = (prev_man or {}).get("files") or sorted(p.name for p in prev_dir.iterdir() if p.is_file())
    return {
        "previous": {"dir": repo_rel(prev_dir), "source": source, "frames_json": prev_man is not None,
                     "fbx_sha256": prev_fbx.get("sha256"),
                     "same_fbx": (prev_fbx.get("sha256") == fbx_sha) if prev_fbx.get("sha256") and fbx_sha else None},
        "noise": {"pixel_level": NOISE_LEVEL, "min_pixels": NOISE_MIN_PX,
                  "rule": "пиксель изменён, если разница канала > pixel_level из 255; кадр изменён, если таких "
                          "пикселей ≥ min_pixels; разный размер — изменён (comparable false)"},
        "purpose": "вход запускающего (какие кадры смотрит второй приёмщик и проверка пунктов фикса), не основание "
                   "балла (F151, RC-19)",
        "frames": per, "changed": changed, "unchanged": unchanged, "not_comparable": not_comparable,
        "removed": sorted(set(prev_files) - set(files) - {"frames.json"}),
    }


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # русские сообщения читаемы в Git Bash/агентах (консоль cp1251)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--fbx", required=True, help="SK_<Key>_H2LD.fbx (UM_FBX_v1)")
    ap.add_argument("--textures", required=True, help="каталог текстур (BC, N DirectX, ORM)")
    ap.add_argument("--out", required=True, help="<evidence>/frames")
    ap.add_argument("--key", help="UE-ключ (PascalCase): фильтр текстур T_<Key>_*, сверка ключа листа")
    ap.add_argument("--sheet", help="лист концепта sheet-<key>.png -> frames/sheet.png")
    ap.add_argument("--side-view", choices=["left", "right"],
                    help="SIDE_VIEW заявки: side-вид листа против turn-090 (left) или turn-270 (right)")
    ap.add_argument("--measure", help="measure-report.json look-dev (по умолчанию <run>/reports/ рядом с export/)")
    ap.add_argument("--allow-no-tone", action="store_true",
                    help="герой без measure-report (ассет старше ld_measure: форки, калибровка) — WARN, а не FAIL")
    ap.add_argument("--blender", default=DEFAULT_BLENDER)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--base", help="SM_<Key>_<Stage>_Base.fbx (по умолчанию — соседний файл, если есть)")
    g.add_argument("--no-base", action="store_true", help="без подставки")
    ap.add_argument("--previous", help="каталог frames прежнего цикла для frames.json#changed_vs_previous (F151); "
                                       "по умолчанию — <дата>-r<N-1>/frames рядом с --out; none — не сравнивать")
    ap.add_argument("--asset-card", help="asset-card.yaml ассета (кость атаки для close-attack; по умолчанию — "
                                         "ближайший вверх от --fbx)")
    ap.add_argument("--attack-bone", help="кость атакующей конечности для close-attack (F74), например hand.R; none — "
                                          "не снимать; по умолчанию — WEAPON_SOCKET_BONE заявки при WEAPON_HAND none")
    ap.add_argument("--rules", choices=["auto", "1", "2"], default="auto",
                    help="правила съёмки: 2 — отсечение задних граней (C22), ракурс close-hands по видимости кисти "
                         "(C30), UV без оболочки cloth_shell (C36); auto — по профилю H2 прогона (profile_version) или "
                         "ASSET_ID заявки; 1 — прежние кадры")
    a = ap.parse_args(argv)

    fbx = Path(a.fbx).resolve()
    tdir = Path(a.textures).resolve()
    out = Path(a.out).resolve()
    if not fbx.is_file():
        print("FAIL: нет FBX %s" % fbx, file=sys.stderr)
        return 1
    if not tdir.is_dir():
        print("FAIL: нет каталога текстур %s" % tdir, file=sys.stderr)
        return 1
    if not Path(a.blender).is_file():
        print("FAIL: нет Blender %s (--blender или env BLENDER)" % a.blender, file=sys.stderr)
        return 1
    try:
        tex = {k: pick_texture(tdir, s, a.key) for k, s in (("bc", "_BC"), ("n", "_N"), ("orm", "_ORM"))}
    except SystemExit as e:
        print("FAIL: %s" % e, file=sys.stderr)
        return 1
    base = None if a.no_base else (Path(a.base).resolve() if a.base else find_base(fbx))
    if base is not None and not base.is_file():
        print("FAIL: нет подставки %s" % base, file=sys.stderr)
        return 1
    sheet = Path(a.sheet).resolve() if a.sheet else None
    if sheet is not None and not sheet.is_file():
        print("FAIL: нет листа концепта %s" % sheet, file=sys.stderr)
        return 1
    measure = Path(a.measure).resolve() if a.measure else find_measure(fbx)
    if measure is not None and not measure.is_file():
        print("FAIL: нет measure-report %s" % measure, file=sys.stderr)
        return 1
    previous, previous_source = None, None
    if a.previous and a.previous.lower() != "none":
        previous, previous_source = Path(a.previous).resolve(), "--previous"
        if not previous.is_dir():
            print("FAIL: нет каталога прежнего цикла %s" % previous, file=sys.stderr)
            return 1
        if previous == out:
            print("FAIL: --previous совпадает с --out (повтор в тот же каталог стирает прежние кадры)", file=sys.stderr)
            return 1
    elif not a.previous:
        previous = find_previous(out)
        previous_source = "auto: <дата>-r<N-1>/frames рядом с --out" if previous else None
    card_path = Path(a.asset_card).resolve() if a.asset_card else find_asset_card(fbx.parent)
    if a.asset_card and not card_path.is_file():
        print("FAIL: нет asset-card %s" % card_path, file=sys.stderr)
        return 1
    card_text = card_path.read_text(encoding="utf-8") if card_path is not None else None
    card_vals = card_scalars(card_text) if card_text is not None else {}
    attack_bone, attack_source = resolve_attack(a.attack_bone, card_vals)
    if a.rules == "auto":
        rules, rules_source = detect_rules(fbx, card_text)
    else:
        rules, rules_source = int(a.rules), "--rules %s" % a.rules
    v2 = rules is not None and rules >= 2
    out.mkdir(parents=True, exist_ok=True)
    stale = [p for p in out.iterdir() if STALE.fullmatch(p.name)]
    for p in stale:  # повторный прогон в тот же каталог: старые кадры не должны смешаться с новыми
        p.unlink()

    work = Path(tempfile.mkdtemp(prefix="accept-capture-"))
    try:
        cfg = {"fbx": str(fbx), "base_fbx": str(base) if base else None, "textures": {k: str(v) for k, v in tex.items()},
               "work_dir": str(work), "size": SIZE, "probe_source": str(PROBE_SOURCE),
               "attack_bone": attack_bone, "attack_source": attack_source}
        if v2:  # правила v2 (C22, C30, C36); v1 — прежний cfg и прежние кадры
            cfg.update(rules=rules, backface_culling=True, hand_view="visibility", uv_shell=True)
        (work / "cfg.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        cmd = [a.blender, "-b", "--factory-startup", "--python-exit-code", "1",
               "--python", str(BLENDER_SCRIPT), "--", str(work / "cfg.json")]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=flags)
        if r.returncode != 0 or "CAPTURE_OK" not in r.stdout:
            tail = "\n".join((r.stdout + r.stderr).splitlines()[-25:])
            print("FAIL: Blender завершился с кодом %s\n%s" % (r.returncode, tail), file=sys.stderr)
            return 1
        info = json.loads((work / "capture.json").read_text(encoding="utf-8"))
        uv = draw_uv_layout(work / "uv-data.npz", tex["bc"], out / "uv-layout.png", info["meshes"])
        expected = (FIXED + (RIG_ONLY + RIG_EXTRA if info["armature"] else [])
                    + ([ATTACK_FRAME] if info.get("attack") else []))
        checks, errors = {}, []
        raw_l, raw_r = work / "raw" / "close-hands-L.png", work / "raw" / "close-hands-R.png"
        if raw_l.is_file() and raw_r.is_file():
            compose_panels(raw_r, raw_l, work / "raw" / "close-hands.png")
        raw_s, raw_b = work / "raw" / "close-attack-side.png", work / "raw" / "close-attack-back.png"
        if raw_s.is_file() and raw_b.is_file():
            bone = (info.get("attack") or {}).get("bone", "")
            compose_panels(raw_s, raw_b, work / "raw" / "close-attack.png",
                           labels=("%s: бок" % bone, "%s: спина 3/4" % bone))
        for name in expected:
            raw = work / "raw" / (name[:-4] + ".png")
            if not raw.is_file():
                errors.append("нет кадра %s" % name)
                continue
            checks[name] = finish_frame(raw, out / name)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # frames.json#frames: панели close-hands-R/L и close-attack-side/back склеены в кадры close-hands.jpg и
    # close-attack.jpg (имена = frames.json#files); у каждого кадра role (ROLES)
    frames_meta, panels = [], {}
    for f in info["frames"]:
        pre = next((k for k in PANELS if f["name"].startswith(k)), None)
        if pre:
            panels.setdefault(pre, []).append(dict(f, panel=f["name"][len(pre):-4]))
        else:
            frames_meta.append(dict(f, role=ROLES.get(f["name"])))
    for pre, pl in panels.items():
        name, note = PANELS[pre]
        frames_meta.append({"name": name, "material": "preview", "note": note, "panels": pl, "role": ROLES.get(name)})

    for name, c in checks.items():
        if c["size"] != [SIZE, SIZE]:
            errors.append("%s: размер %s" % (name, c["size"]))
        if c["foreground_share"] < 0.02:
            errors.append("%s: фигура не видна (доля переднего плана %.3f)" % (name, c["foreground_share"]))
        if (name in TURNS or name.startswith(("wire-", "pose-"))) and name not in CROPPED and c["touches_border"]:
            errors.append("%s: фигура касается края кадра (обрезана)" % name)
    if uv["coverage"] < 0.005:
        errors.append("uv-layout.png: покрытие UV %.4f — UV пустые или вырождены" % uv["coverage"])
    elif uv["coverage"] < 0.05:
        info["warnings"].append("uv-layout.png: покрытие UV %.3f < 5 %% (часть общего атласа?)" % uv["coverage"])

    extra = []
    warnings = info["warnings"]
    sheet_meta = None
    compare_meta = {}
    if sheet is not None:
        sheet_meta = sheet_info(sheet, a.key)
        sheet_meta.update(copy_sheet(sheet, out / "sheet.png"))
        sheet_meta["sha256"] = sha256(out / "sheet.png")
        extra.append("sheet.png")
        if sheet_meta["compare_palette_by"] == "views":
            warnings.append("sheet.png: свотчей палитры нет — палитру S сравнивать по видам листа")
        if sheet_meta["key_match"] is False:
            warnings.append("sheet.png: лист %s (ключ %s) не похож на лист ключа %s (%s) — не тот лист или негативный "
                            "контроль калибровки" % (sheet.name, sheet_meta["content_key"], a.key, kebab(a.key)))
        side_turn = {"left": "turn-090.jpg", "right": "turn-270.jpg"}[a.side_view or "left"]
        turn_for = {"front": "turn-000.jpg", "side": side_turn, "back": "turn-180.jpg"}
        if sheet_meta["views"] and not a.side_view and "side" in sheet_meta["views"]:
            warnings.append("нет --side-view: compare-side сравнивает side листа с turn-090 (left)")
        for view, vmeta in sheet_meta["views"].items():
            if view not in COMPARE:
                continue
            vp = REPO / vmeta["path"]
            tb = (checks.get(turn_for[view]) or {}).get("bbox_px")
            if not vp.is_file() or tb is None:
                warnings.append("%s: нет вида листа %s или рамки %s" % (COMPARE[view], vmeta["path"], turn_for[view]))
                continue
            compare_meta[COMPARE[view]] = compare_frame(vp, vmeta["bbox_px"], out / turn_for[view], tb,
                                                        out / COMPARE[view],
                                                        ("лист: %s" % view, turn_for[view][:-4]))
            compare_meta[COMPARE[view]].update({"sheet_view": vmeta["path"], "turn": turn_for[view]})
            extra.append(COMPARE[view])
        if not compare_meta:
            warnings.append("нет checks-report.json с видами рядом с листом: compare-* не сняты, пропорции S — по "
                            "sheet.png на глаз")
    else:
        warnings.append("нет --sheet: frames/sheet.png не скопирован, validate_card потребует лист в frames.files")
    tone = None
    if measure is not None:
        from _tone import tone_table  # noqa: PLC0415
        maps_p = measure.with_name("ld-maps-report.json")
        try:
            maps = json.loads(maps_p.read_text(encoding="utf-8")) if maps_p.is_file() else None
            tone = tone_table(json.loads(measure.read_text(encoding="utf-8")), maps)
        except (OSError, ValueError) as e:
            errors.append("tone: %s" % e)
        if tone is not None:
            tone["sources"] = {"measure_report": repo_rel(measure),
                               "maps_report": repo_rel(maps_p) if maps_p.is_file() else None}
            (out / "tone.json").write_text(json.dumps(tone, ensure_ascii=False, indent=2), encoding="utf-8")
            extra.append("tone.json")
            warnings.extend("tone.json: %s" % w for w in tone["warnings"])
            if tone["framing"] != "concept":
                warnings.append("tone.json: measure-report без блока framing — орто-кадры look-dev по канону Medusa "
                                "1021x1540 (верно только для Medusa); у нового персонажа задать look-dev frame "
                                "(framing.py) и повторить ld_preview/ld_measure")
    elif info["armature"] and not a.allow_no_tone:
        errors.append("герой без measure-report.json: тон основного класса не проверить (tone.json); прогнать стадию "
                      "ld_measure look-dev (HANDBOOK §4.4) или --allow-no-tone для ассета старше ld_measure")
    else:
        warnings.append("нет measure-report.json (прогон старше ld_measure или проп): tone.json не создан, тон T "
                        "по кадрам не снижается")

    fbx_sha = sha256(fbx)
    accepted = [{"path": repo_rel(fbx), "sha256": fbx_sha}]
    if base:
        accepted.append({"path": repo_rel(base), "sha256": sha256(base)})
    maps_found, maps_missing = accepted_maps(tdir, a.key)
    accepted += [{"path": repo_rel(p), "sha256": sha256(p)} for _k, p in maps_found]
    if maps_missing and info["armature"]:
        warnings.append("accepted_object: нет 2K-карт %s в %s" % (", ".join(maps_missing), repo_rel(tdir)))

    files = sorted(expected + ["uv-layout.png", "frames.json"] + extra)
    cvp, cyc = None, CYCLE_DIR.match(out.parent.name)
    if previous is not None:
        cvp = changed_vs_previous(previous, out, files, fbx_sha, previous_source)
    elif a.previous is None and cyc and int(cyc.group(2)) > 1:
        warnings.append("changed_vs_previous: рядом с %s нет кадров цикла r%d (frames/frames.json) — сравнения нет; "
                        "--previous <каталог> задаёт его явно" % (out.parent.name, int(cyc.group(2)) - 1))

    manifest = {
        "schema": "unmatched.acceptance-frames/1",
        "tool": "tools/art/acceptance/capture_acceptance_set.py",
        "inputs": {
            "fbx": {"path": repo_rel(fbx), "sha256": fbx_sha},
            "base_fbx": {"path": repo_rel(base), "sha256": sha256(base)} if base else None,
            "textures": {k: {"path": repo_rel(v), "sha256": sha256(v)} for k, v in tex.items()},
        },
        "accepted_object": accepted,
        "accepted_object_missing_maps": maps_missing,
        "render": {"blender": info["blender"], "engine": info["engine"], "view_transform": info["view_transform"],
                   "size_px": SIZE, "jpeg_quality": QUALITY, "review_max_px": REVIEW_PX,
                   "background_rgb": list(BG), "camera": "ortho",
                   "scene_frame": "UM_FBX_v1 (лицо +X) повёрнут на -90 deg Z: лицо -Y, сторона .L = +X",
                   "azimuth": "0 = спереди, 90 = левый бок фигуры (.L), 180 = сзади, 270 = правый бок",
                   "material": "BC sRGB; N DirectX -> G инвертирован для Blender (OpenGL); ORM: G roughness, "
                               "B metallic, R (AO) не подаётся; свет key/fill/rim вращается с камерой",
                   "shadows": "тени EEVEE от area-света key/fill/rim включены: контактная тень стоп на крышке "
                              "подставки — свет, а не текстура (запечённый AO в BC остаётся на месте и в pose-04, "
                              "где стопа поднята)",
                   "wire": "Wireframe node 1 px на глине 0,55"},
        "bounds_m": info["bounds_m"], "meshes": info["meshes"], "armature": info["armature"],
        "frames": frames_meta + [{"name": "uv-layout.png", **uv, "role": ROLES["uv-layout.png"]}],
        "compare": compare_meta or None,
        "side_view": a.side_view,
        "poses": info["poses"] or "n/a: нет арматуры",
        "pose_source": repo_rel(PROBE_SOURCE),
        "pose_checks": info.get("pose_checks") or {},
        "attack": (dict(info["attack"], asset_card=repo_rel(card_path) if card_path else None)
                   if info.get("attack") else
                   {"bone": None, "requested": attack_bone, "source": attack_source,
                    "asset_card": repo_rel(card_path) if card_path else None,
                    "note": "close-attack не снят: %s" % ("нет кости в арматуре" if attack_bone else
                                                         "нет кости атаки (оружие или WEAPON_HAND не none)")}),
        "sheet": sheet_meta,
        "tone": ({"file": "tone.json", "t_cap": tone["t_cap"], "out_of_tolerance": tone["out_of_tolerance"],
                  "floor_limited": tone["floor_limited"], "family_changed_main": tone["family_changed_main"],
                  "anchor_class": tone["anchor_class"]} if tone else None),
        "checks": checks, "warnings": warnings, "errors": errors,
        "changed_vs_previous": cvp,
        "files": files,
        "roles": {f: ROLES.get(f) for f in files},
    }
    if v2:  # правила v2: что изменилось в кадрах (v1 — frames.json прежний)
        manifest["rules"] = dict(info.get("rules") or {}, source=rules_source,
                                 note="задние грани отсечены, как в UE (крышка, видимая изнанкой, — дыра на кадре); "
                                      "close-hands по видимости кисти; UV без оболочки cloth_shell (C22, C30, C36)")
    (out / "frames.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for w in warnings:
        print("WARN: %s" % w, file=sys.stderr)
    if errors:
        for e in errors:
            print("FAIL: %s" % e, file=sys.stderr)
        return 1
    if cvp is not None:
        print("changed_vs_previous (%s): изменены %s; без изменений %d" % (cvp["previous"]["dir"],
                                                                        ", ".join(cvp["changed"]) or "—",
                                                                        len(cvp["unchanged"])))
    print("OK: %d кадров + uv-layout.png%s -> %s" % (len(expected), "".join(" + " + x for x in extra), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
