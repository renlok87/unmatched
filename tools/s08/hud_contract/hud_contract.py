#!/usr/bin/env python3
"""Проверки правил HUD (docs/unreal/contracts/hud/HUD-RULES.md) без движка.

  python tools/s08/hud_contract/hud_contract.py validate            токены стиля + коды why.* против 02 §4.2
  python tools/s08/hud_contract/hud_contract.py linear              таблица hex sRGB -> linear (как FLinearColor::FromSRGBColor)
  python tools/s08/hud_contract/hud_contract.py check-trace <log> [--width 1920 --height 1080]
                                                                    гейт строк `SHOT widget id=… bbox=… geom=painted`

Только stdlib. Код выхода: 0 — ошибок нет, 1 — есть ошибки.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HUD = REPO / "docs/unreal/contracts/hud"
TOKENS = HUD / "hud-style-tokens.json"
WHY = HUD / "why-reasons.json"
SPEC02 = REPO / "docs/game-design/02-ux-ui-spec.md"
STATUSES = ("предложено", "измерено", "технически импортировано", "художественно принято")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
UI_ID_RE = re.compile(r"\bUI-(?:HUD|SCR)-[A-Z]+(?:-[A-Z]+)*\b")
WHY_02_RE = re.compile(r"`(why\.[a-z.]+)`")
SHOT_RE = re.compile(r"SHOT widget (.*)$")
ARG_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def srgb_to_linear(c8):
    """Кусочная кривая sRGB (IEC 61966-2-1), которой пользуется FLinearColor::FromSRGBColor (таблица sRGBToLinearTable)."""
    c = c8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_to_linear(hexstr):
    h = hexstr.lstrip("#")
    return tuple(round(srgb_to_linear(int(h[i:i + 2], 16)), 4) for i in (0, 2, 4))


def ui_ids_from_02(text):
    return set(UI_ID_RE.findall(text))


def validate_tokens(tokens):
    errors = []
    if tokens.get("schema") != "unmatched.hud-style-tokens/1":
        errors.append("tokens: schema")
    for group in ("colors", "typography", "spacing", "radii", "icons", "motion"):
        if group not in tokens:
            errors.append("tokens: нет группы %s" % group)
            continue
        for name, tok in tokens[group].items():
            if tok.get("status") not in STATUSES:
                errors.append("%s.%s: status" % (group, name))
            if not tok.get("source"):
                errors.append("%s.%s: нет source" % (group, name))
            if group == "colors" and not HEX_RE.match(tok.get("hex", "")):
                errors.append("%s.%s: hex %r" % (group, name, tok.get("hex")))
            if group in ("spacing", "radii", "icons") or (group == "typography" and "px" in tok):
                if not isinstance(tok.get("px"), int) or tok["px"] <= 0:
                    errors.append("%s.%s: px" % (group, name))
    return errors


def validate_why(why, spec02_text):
    errors = []
    keys = [r["key"] for r in why["reasons"]]
    if len(keys) != len(set(keys)):
        errors.append("why: повтор ключей")
    want = set(WHY_02_RE.findall(spec02_text))
    if want and set(keys) != want:
        errors.append("why: ключи не совпадают с 02 §4.2: нет %s, лишние %s" % (sorted(want - set(keys)), sorted(set(keys) - want)))
    for r in why["reasons"]:
        for lang in why["string_table"]["cultures"]:
            if not r.get(lang):
                errors.append("%s: нет текста %s" % (r["key"], lang))
        args = set(r.get("args", []))
        for lang in why["string_table"]["cultures"]:
            used = set(ARG_RE.findall(r.get(lang, "")))
            if used != args:
                errors.append("%s/%s: аргументы %s против %s" % (r["key"], lang, sorted(used), sorted(args)))
    return errors


def parse_shot_widget(line):
    m = SHOT_RE.search(line.rstrip("\r\n"))
    if not m:
        return None
    return dict(w.split("=", 1) for w in m.group(1).split() if "=" in w)


# Словарь арт-слоя HUD (W4-C плашка/иконка, W5b-R тег/число урона): в 02 для них UI-ID нет — предложенный diff
# docs/art-pipeline/proposals/w5br-hud-tag-damage-02.diff.md (UI-HUD-TAG / UI-HUD-DAMAGE); до решения автора
# клиент пишет эти id.
ART_HUD_IDS = {"plate", "plate.marker", "plate.name", "plate.team", "plate.hpbar", "plate.hpfill", "plate.hp",
               "plate.status", "plate.teamshape", "icon", "board.tag", "board.tag.name", "board.tag.hp",
               "board.tag.bar", "board.tag.chip", "board.damage", "board.damage.text"}


def parse_bbox(value):
    """'x,y,w,h' (формат HUD-RULES П4) или '(x0,y0,x1,y1)' (строки арт-слоя) -> (x, y, w, h)."""
    v = value.strip()
    if v.startswith("(") and v.endswith(")"):
        x0, y0, x1, y1 = (float(t) for t in v[1:-1].split(","))
        return x0, y0, x1 - x0, y1 - y0
    x, y, w, h = (float(t) for t in v.split(","))
    return x, y, w, h


def check_widget_trace(lines, known_ids, width=1920, height=1080):
    """Правило 3: гейт по трассе геометрии виджета, не по пикселям. Невидимая часть (visible=0, например
    сравнительный Slate-двойник или скрытая иконка в поздней строке W5b-R) может быть unpainted."""
    errors, seen = [], 0
    ids = set(known_ids) | ART_HUD_IDS
    for n, line in enumerate(lines, 1):
        f = parse_shot_widget(line)
        if f is None:
            continue
        seen += 1
        for k in ("id", "state", "bbox", "geom", "visible"):
            if k not in f:
                errors.append("строка %d: нет поля %s" % (n, k))
        if "id" in f and f["id"] not in ids:
            errors.append("строка %d: неизвестный UI-ID %s" % (n, f["id"]))
        if f.get("visible") == "0":
            continue
        if f.get("geom") != "painted":
            errors.append("строка %d: geom=%s (нужна нарисованная геометрия)" % (n, f.get("geom")))
        try:
            x, y, w, h = parse_bbox(f.get("bbox", ""))
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > width + 0.5 or y + h > height + 0.5:
                errors.append("строка %d: bbox %s вне кадра %dx%d" % (n, f["bbox"], width, height))
        except ValueError:
            errors.append("строка %d: bbox %r" % (n, f.get("bbox")))
    return errors, seen


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sub.add_parser("linear")
    c = sub.add_parser("check-trace")
    c.add_argument("log")
    c.add_argument("--width", type=int, default=1920)
    c.add_argument("--height", type=int, default=1080)
    a = ap.parse_args(argv)
    spec02 = SPEC02.read_text(encoding="utf-8")
    if a.cmd == "validate":
        errors = validate_tokens(load(TOKENS)) + validate_why(load(WHY), spec02)
        for e in errors:
            print("ERROR", e)
        print("HUD_CONTRACT", "PASS" if not errors else "FAIL")
        return 0 if not errors else 1
    if a.cmd == "linear":
        for name, tok in load(TOKENS)["colors"].items():
            print("%-16s %s -> linear %s" % (name, tok["hex"], hex_to_linear(tok["hex"])))
        return 0
    lines = Path(a.log).read_text(encoding="utf-8", errors="replace").splitlines()
    errors, seen = check_widget_trace(lines, ui_ids_from_02(spec02), a.width, a.height)
    for e in errors:
        print("GATE", e)
    print("HUD_TRACE", "PASS" if not errors and seen else "FAIL", "widget_lines", seen)
    return 0 if not errors and seen else 1


if __name__ == "__main__":
    sys.exit(main())
