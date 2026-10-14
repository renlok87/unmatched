#!/usr/bin/env python3
"""Полнота регистрации героя в коде и конфигах (RB-04): одна таблица «герой × место регистрации», код 1 при пропуске.

    python tools/art/registration_check.py                       # каждый герой Specs() (S08HeroesV2.cpp)
    python tools/art/registration_check.py --heroes Angel,Achilles [--json] [--repo <checkout>]

Зачем: пропуск строки регистрации не падает, а тихо откатывает героя — legacy-фигура (нет Specs), молчащий выпад
(HitType по умолчанию BLUNT, банка CMB-LUNGE-BLUNT нет), `missing` трассы CUE, ассетов нет в паке (нет cook).
Места — references/new-character-registration.md §3–§5 скилла 3d-model-pipeline. Читает файлы как текст (C++,
INI, JSON, Python через ast — модули не импортируются), ничего не меняет и не запускает UE.

Пункты (колонки):
  specs     строка Specs() в S08HeroesV2.cpp (FighterName, Key, Stage, …)
  audio     S08AudioBank: CharacterKey(FighterName) = AUDIO_KEY (порядок подстрок), явная строка HitType,
            банки CMB-LUNGE-<тип> и CMB-HIT-<тип> в S08AudioBankData.inl, тип = HIT_TYPE заявки
  cue       cue-table.json CUE-011 / CUE-013 clip.sequence_by_fighter[<Key>] = AM_<Key>_HitReact / _DeathSettle,
            .uasset в Content
  cook      DefaultGame.ini +DirectoriesToAlwaysCook для /Game/PipelineCandidates/<Key>/{<Stage>,Rig,H2Anim}
  names     S08FighterNames.json: hero.en / sidekick.en = FighterName (нумерованный помощник — по contentKey
            реестра); только помощник (OWNER_HERO_SLUG) — SKIP: формат держит одного помощника на героя
  de010     tools/art/de010/de010.py HEROES: Stage и кадр контакта = Specs(), спека есть, ue_hero = Key,
            контакт среди key_frames LungeAttack, та же спека, что у clip_manifest для LungeAttack
  de011     tools/art/de011/de011.py CAPTURE_LOOKS[<Key>] ∈ {P1, P2}
  manifest  clip_manifest.py CHARS / H2ANIM (/ H2ANIM_CLIP): спека каждого из 4 клипов и FBX
            <run_dir>/export/AM_<Key>_<Clip>.fbx есть; персонаж в enum схемы; 4 записи <PRE>-<Clip> в манифесте
  sheet     tools/art/anim/clip_review_sheet.py HEROES[<Key>]: персонаж, префикс = CHARS, Idle = Specs() ± 0,01 с,
            4 карточки есть в anim.csv
  rig       rig-contract.json: characters[<Character>] (asset_id), applies_to, sockets_v2 Weapon.bone_by_character
  bench     unreal/Unmatched/Config/Bench/S08Bench{Marmoreal,Sarpedon}-<Key>.json (benchVariant, доска, имя бойца);
            SKIP, если боец уже стоит в канонических фикстурах (MVP)
  registry  docs/art-pipeline/asset-registry.json: запись ASSET_ID, статус не ниже «технически импортировано»

Персонаж (CHARACTER), ASSET_ID, AUDIO_KEY, HIT_TYPE и слаги берутся из заявки art/pipeline-candidates/*/asset-card.yaml
(поле KEY), иначе из спеки de010 и clip_review_sheet (у MVP заявок нет); AUDIO_KEY по умолчанию — CHARACTER
заглавными. Код выхода: 0 — всё PASS/SKIP, 1 — есть FAIL, 2 — ошибка входа (нет файла Specs и т. п.).
Запуск: шаг 7b скилла (после регистрации, до упаковки) и перед safe-integrate.
"""
from __future__ import annotations

import argparse
import ast
import csv
import io
import json
import operator
import re
import sys
from pathlib import Path

SCHEMA = "unmatched.registration-check/1"
REPO_DEFAULT = Path(__file__).resolve().parents[2]
CLIPS = ("Idle", "LungeAttack", "HitReact", "DeathSettle")
ITEMS = ("specs", "audio", "cue", "cook", "names", "de010", "de011", "manifest", "sheet", "rig", "bench", "registry")
CUE_CLIPS = {"CUE-011": "HitReact", "CUE-013": "DeathSettle"}
MAPS = ("Marmoreal", "Sarpedon")
UE_STATUSES = ("технически импортировано", "художественно принято")
UE_STAGES = ("ue-editor-import", "ue-editor-frames", "live-packaged-probe")
PATHS = {
    "specs": "unreal/Unmatched/Source/Unmatched/S08/S08HeroesV2.cpp",
    "audio": "unreal/Unmatched/Source/Unmatched/S08/S08AudioBank.cpp",
    "audio_data": "unreal/Unmatched/Source/Unmatched/S08/S08AudioBankData.inl",
    "cue": "docs/unreal/contracts/cue-dispatcher/cue-table.json",
    "ini": "unreal/Unmatched/Config/DefaultGame.ini",
    "names": "unreal/Unmatched/Config/Cards/S08FighterNames.json",
    "de010": "tools/art/de010/de010.py",
    "de011": "tools/art/de011/de011.py",
    "manifest_py": "tools/tripo-pipeline/anim/clip_manifest.py",
    "manifest_schema": "docs/art-pipeline/animation-library/clip-manifest.schema.json",
    "manifest_json": "docs/art-pipeline/animation-library/clip-manifest.json",
    "sheet": "tools/art/anim/clip_review_sheet.py",
    "anim_csv": "docs/game-design/visual/06-tasks/anim.csv",
    "rig": "docs/art-pipeline/rig/rig-contract.json",
    "bench": "unreal/Unmatched/Config/Bench",
    "registry": "docs/art-pipeline/asset-registry.json",
    "content": "unreal/Unmatched/Content",
    "candidates": "art/pipeline-candidates",
}


class InputError(Exception):
    """Нет обязательного файла или он не разбирается → код 2."""


# ------------------------------------------------------------------------------------------------ разбор исходников
_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _literal(node, env: dict):
    """ast-узел → значение: литералы, арифметика, имена из env, вызов Name(...) → кортеж аргументов (NamedTuple)."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Tuple):
        return tuple(_literal(e, env) for e in node.elts)
    if isinstance(node, ast.List):
        return [_literal(e, env) for e in node.elts]
    if isinstance(node, ast.Dict):
        return {_literal(k, env): _literal(v, env) for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_literal(node.left, env), _literal(node.right, env))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_literal(node.operand, env)
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
        return tuple(_literal(a, env) for a in node.args)
    raise ValueError(ast.dump(node)[:80])


def module_constants(text: str, names) -> dict:
    """Значения констант модуля без импорта: X = …, X[k] = …, X.update/append/extend(…), X += […]."""
    env: dict = {}
    for node in ast.parse(text).body:
        try:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if node.value is None:
                    continue
                for t in targets:
                    if isinstance(t, ast.Name) and t.id in names:
                        env[t.id] = _literal(node.value, env)
                    elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id in env:
                        env[t.value.id][_literal(t.slice, env)] = _literal(node.value, env)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id in env:
                env[node.target.id] = env[node.target.id] + _literal(node.value, env)
            elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                  and isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name)
                  and node.value.func.value.id in env):
                obj, meth = env[node.value.func.value.id], node.value.func.attr
                args = [_literal(a, env) for a in node.value.args]
                if meth in ("update", "append", "extend") and hasattr(obj, meth):
                    getattr(obj, meth)(*args)
        except (ValueError, KeyError, TypeError):
            continue
    return env


def _strip_cpp_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def _cpp_number(expr: str) -> float:
    expr = re.sub(r"(\d(?:\.\d*)?(?:[eE][-+]?\d+)?)[fF]\b", r"\1", expr.strip())
    return float(_literal(ast.parse(expr, mode="eval").body, {}))


_SPEC_RE = re.compile(
    r"\{\s*TEXT\(\"([^\"]*)\"\)\s*,\s*TEXT\(\"([^\"]*)\"\)\s*,\s*TEXT\(\"([^\"]*)\"\)\s*,\s*(true|false)\s*,"
    r"\s*([^,{}]+),\s*([^,{}]+),\s*([^,{}]+),\s*([^,{}]+),\s*([^,{}]+),\s*([^,{}]+),\s*(\d+)\s*\}")


def parse_specs(text: str) -> list[dict]:
    """Строки таблицы Specs() (S08HeroesV2.cpp): 11 полей FHeroSpec."""
    m = re.search(r"Specs\(\)\s*\{(.*?)return\s+Table\s*;", text, re.S)
    if not m:
        raise InputError("S08HeroesV2.cpp: не найдена таблица Specs() (… return Table;)")
    out = []
    for g in _SPEC_RE.findall(_strip_cpp_comments(m.group(1))):
        out.append({"fighter": g[0], "key": g[1], "stage": g[2], "hero": g[3] == "true",
                    "budget_uu": _cpp_number(g[4]), "min_uu": _cpp_number(g[5]), "max_uu": _cpp_number(g[6]),
                    "figure_top_uu": _cpp_number(g[7]), "bounds_top_uu": _cpp_number(g[8]),
                    "idle_s": _cpp_number(g[9]), "contact_frame": int(g[10])})
    if not out:
        raise InputError("S08HeroesV2.cpp: в Specs() нет ни одной строки FHeroSpec")
    return out


def _cpp_function_body(text: str, name: str) -> str:
    m = re.search(re.escape(name) + r"\s*\([^)]*\)\s*(?:const\s*)?\{", text)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[m.end():i - 1]


def parse_audio(text: str) -> dict:
    """CharacterKey: [(подстрока, без учёта регистра, ключ)] по порядку; HitType: {ключ: тип} и тип по умолчанию."""
    ck = _strip_cpp_comments(_cpp_function_body(text, "S08AudioBank::CharacterKey"))
    ht = _strip_cpp_comments(_cpp_function_body(text, "S08AudioBank::HitType"))
    rules = [(n, bool(ic), k) for n, ic, k in re.findall(
        r"Name\.Contains\(\s*TEXT\(\"([^\"]*)\"\)\s*(,\s*ESearchCase::IgnoreCase)?\s*\)\s*\)\s*return\s+TEXT\(\"([^\"]*)\"\)",
        ck)]
    hit = dict(re.findall(r"Key\s*==\s*TEXT\(\"([^\"]*)\"\)\s*\)\s*return\s+TEXT\(\"([^\"]*)\"\)", ht))
    plain = re.findall(r"(?:^|;|\})\s*return\s+TEXT\(\"([^\"]*)\"\)\s*;", ht)
    return {"rules": rules, "hit": hit, "hit_default": plain[-1] if plain else None}


def character_key(rules: list, fighter: str) -> tuple[str, str | None]:
    """Эмуляция S08AudioBank::CharacterKey: первая подходящая подстрока → (ключ, подстрока); нет — ("", None)."""
    for needle, ignore_case, key in rules:
        hay, nd = (fighter.lower(), needle.lower()) if ignore_case else (fighter, needle)
        if nd in hay:
            return key, needle
    return "", None


def parse_cook_dirs(ini_text: str) -> list[str]:
    out = []
    for line in ini_text.splitlines():
        s = line.strip()
        if s.startswith((";", "#")):
            continue
        m = re.match(r"\+DirectoriesToAlwaysCook\s*=\s*\(\s*Path\s*=\s*\"([^\"]+)\"\s*\)", s)
        if m:
            out.append(m.group(1).rstrip("/"))
    return out


def card_fields(text: str) -> dict:
    """Верхнеуровневые скаляры asset-card.yaml (строки «NAME: значение» с нулевым отступом)."""
    out = {}
    for m in re.finditer(r"^([A-Z][A-Z0-9_]*):[ \t]*(.*)$", text, re.M):
        v = m.group(2).strip()
        if v.startswith('"'):
            end = v.find('"', 1)
            while end > 0 and v[end - 1] == "\\":
                end = v.find('"', end + 1)
            v = v[1:end] if end > 0 else v.strip('"')
        else:
            v = re.sub(r"\s+#.*$", "", v).strip()
        if v in ("null", "~"):
            v = None
        out.setdefault(m.group(1), v)
    return out


# ------------------------------------------------------------------------------------------------------- данные
class Repo:
    """Ленивое чтение файлов чекаута (каждый файл — один раз)."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._cache: dict = {}

    def path(self, key_or_rel: str) -> Path:
        return self.root / PATHS.get(key_or_rel, key_or_rel)

    def text(self, key: str) -> str | None:
        if ("t", key) not in self._cache:
            p = self.path(key)
            self._cache[("t", key)] = p.read_text(encoding="utf-8-sig") if p.is_file() else None
        return self._cache[("t", key)]

    def json(self, key: str):
        if ("j", key) not in self._cache:
            t = self.text(key)
            try:
                self._cache[("j", key)] = json.loads(t) if t is not None else None
            except ValueError as exc:
                raise InputError(f"{PATHS.get(key, key)}: не JSON ({exc})") from exc
        return self._cache[("j", key)]

    def consts(self, key: str, names) -> dict:
        t = self.text(key)
        return module_constants(t, set(names)) if t is not None else {}

    def cards(self) -> dict:
        """KEY заявки → (путь заявки, поля)."""
        if "cards" not in self._cache:
            res = {}
            base = self.path("candidates")
            for p in sorted(base.glob("*/asset-card.yaml")) if base.is_dir() else []:
                try:
                    f = card_fields(p.read_text(encoding="utf-8-sig"))
                except OSError:
                    continue
                if f.get("KEY"):
                    res.setdefault(f["KEY"], (p, f))
            self._cache["cards"] = res
        return self._cache["cards"]


def _clip_spec_path(manifest: dict, character: str, clip: str) -> str | None:
    over = manifest.get("H2ANIM_CLIP") or {}
    return over.get((character, clip)) or (manifest.get("H2ANIM") or {}).get(character)


def identity(repo: Repo, key: str, spec_row: dict | None, consts: dict) -> dict:
    """Кто этот герой: персонаж, ASSET_ID, ключ звука, тип удара, слаги — из заявки, спеки de010, листа клипов."""
    card_path, card = repo.cards().get(key, (None, {}))
    de010_row = next((r for r in consts["de010"].get("HEROES", []) if r and r[0] == key), None)
    de010_spec = None
    if de010_row and len(de010_row) > 2:
        de010_spec = _load_json_rel(repo, PATHS["candidates"] + "/" + de010_row[2])
    sheet_row = (consts["sheet"].get("HEROES") or {}).get(key)
    character = card.get("CHARACTER") or (de010_spec or {}).get("character") or (sheet_row[0] if sheet_row else None)
    chars = consts["manifest"].get("CHARS") or {}
    asset_id = (card.get("ASSET_ID") or (de010_spec or {}).get("asset_id")
                or (chars.get(character, (None, None))[1] if character else None))
    fighter = spec_row["fighter"] if spec_row else card.get("FIGHTER_NAME")
    return {"key": key, "fighter": fighter, "stage": spec_row["stage"] if spec_row else None,
            "character": character, "asset_id": asset_id,
            "audio_key": card.get("AUDIO_KEY") or (character.upper() if character else None),
            "hit_type": card.get("HIT_TYPE"), "slug": card.get("HERO_SLUG"), "owner_slug": card.get("OWNER_HERO_SLUG"),
            "game_role": card.get("GAME_ROLE") or ((("hero" if spec_row["hero"] else "sidekick")) if spec_row else None),
            "card": card_path.relative_to(repo.root).as_posix() if card_path else None,
            "de010_row": de010_row, "de010_spec": de010_spec, "sheet_row": sheet_row}


def _load_json_rel(repo: Repo, rel: str):
    p = repo.root / rel
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except ValueError:
        return None


# ------------------------------------------------------------------------------------------------------ проверки
def _res(status: str, msgs=None) -> dict:
    return {"status": status, "messages": list(msgs or [])}


def _verdict(fails: list, ok_msgs=None) -> dict:
    return _res("FAIL", fails) if fails else _res("PASS", ok_msgs)


def check_specs(ident, spec_row) -> dict:
    if spec_row is None:
        return _res("FAIL", [f"нет строки Specs() с Key {ident['key']!r} ({PATHS['specs']}, Р7-3): в игре legacy-фигура"])
    f = []
    if not spec_row["min_uu"] <= spec_row["budget_uu"] <= spec_row["max_uu"]:
        f.append(f"MinUU ≤ BudgetUU ≤ MaxUU нарушено: {spec_row['min_uu']} / {spec_row['budget_uu']} / {spec_row['max_uu']}")
    if spec_row["bounds_top_uu"] + 0.01 < spec_row["figure_top_uu"]:
        f.append(f"BoundsTopUU {spec_row['bounds_top_uu']} ниже FigureTopUU {spec_row['figure_top_uu']}")
    return _verdict(f, [f"{spec_row['fighter']!r} {spec_row['stage']}, Idle {spec_row['idle_s']:.4g} с, "
                        f"контакт к.{spec_row['contact_frame']}"])


def check_audio(repo: Repo, ident) -> dict:
    text = repo.text("audio")
    if text is None:
        return _res("FAIL", [f"нет {PATHS['audio']}"])
    a = parse_audio(text)
    banks = set(re.findall(r"S08_AUDIO_BANK\(\s*TEXT\(\"([^\"]+)\"\)", repo.text("audio_data") or ""))
    fighter, want = ident["fighter"], ident["audio_key"]
    if not fighter:
        return _res("FAIL", ["нет имени бойца (ни Specs(), ни FIGHTER_NAME заявки) — CharacterKey не проверить"])
    got, needle = character_key(a["rules"], fighter)
    f = []
    if not got:
        f.append(f"CharacterKey({fighter!r}) = \"\" — нет строки Name.Contains (Р7-5): звук героя пуст")
    elif want and got != want:
        f.append(f"CharacterKey({fighter!r}) = {got!r} (подстрока {needle!r} стоит выше), ожидается {want!r}")
    key = got or want
    typ = a["hit"].get(key) if key else None
    if typ is None:
        f.append(f"HitType({key!r}): нет явной строки, по умолчанию {a['hit_default']!r} (Р7-5)")
        typ = a["hit_default"]
    if ident["hit_type"] and typ != ident["hit_type"]:
        f.append(f"HitType({key!r}) = {typ!r}, в заявке HIT_TYPE {ident['hit_type']!r}")
    for bank in (f"CMB-LUNGE-{typ}", f"CMB-HIT-{typ}"):
        if bank not in banks:
            f.append(f"банка {bank} нет в S08AudioBankData.inl: " + ("выпад молчит" if "LUNGE" in bank else "удар молчит"))
    return _verdict(f, [f"{fighter!r} → {got}, удар {typ}"])


def _find_cue(table, cue_id):
    for c in (table.get("cues") or []) if isinstance(table, dict) else []:
        if isinstance(c, dict) and c.get("id") == cue_id:
            return c
    return None


def _soft_to_uasset(content: Path, soft: str) -> Path:
    return content / (soft[len("/Game/"):].rsplit(".", 1)[0] + ".uasset")


def check_cue(repo: Repo, ident) -> dict:
    table = repo.json("cue")
    if table is None:
        return _res("FAIL", [f"нет {PATHS['cue']}"])
    key = ident["key"]
    folder = ((ident["de010_spec"] or {}).get("ue") or {}).get("clips_folder") or f"/Game/PipelineCandidates/{key}/H2Anim"
    content = repo.path("content")
    f = []
    for cue_id, clip in CUE_CLIPS.items():
        cue = _find_cue(table, cue_id)
        seq = ((cue or {}).get("clip") or {}).get("sequence_by_fighter") or {}
        want = f"{folder}/AM_{key}_{clip}.AM_{key}_{clip}"
        got = seq.get(key)
        if got is None:
            near = [k for k in seq if k.lower() == key.lower() or key.lower() in k.lower()]
            f.append(f"{cue_id} sequence_by_fighter: нет ключа {key!r}" + (f" (есть {near})" if near else "")
                     + " (Р7-6): трасса даст missing")
        elif got != want:
            f.append(f"{cue_id}[{key}] = {got!r}, ожидается {want!r}")
        elif content.is_dir() and not _soft_to_uasset(content, got).is_file():
            f.append(f"{cue_id}[{key}]: нет {_soft_to_uasset(content, got).relative_to(repo.root).as_posix()} "
                     "(validate-table упадёт)")
    return _verdict(f, ["CUE-011, CUE-013"])


def check_cook(repo: Repo, ident) -> dict:
    text = repo.text("ini")
    if text is None:
        return _res("FAIL", [f"нет {PATHS['ini']}"])
    dirs = parse_cook_dirs(text)
    key, stage = ident["key"], ident["stage"] or "H2LD"
    need = [f"/Game/PipelineCandidates/{key}/{sub}" for sub in (stage, "Rig", "H2Anim")]
    miss = [n for n in need if not any(n == d or n.startswith(d + "/") for d in dirs)]
    return _verdict([f"нет +DirectoriesToAlwaysCook=(Path=\"{n}\") (Р7-7): ассетов не будет в паке" for n in miss],
                    [", ".join(need)])


def _registry_entry(repo: Repo, asset_id):
    reg = repo.json("registry")
    for a in (reg or {}).get("assets", []) if isinstance(reg, dict) else []:
        if a.get("id") == asset_id:
            return a
    return None


def check_names(repo: Repo, ident) -> dict:
    data = repo.json("names")
    if data is None:
        return _res("FAIL", [f"нет {PATHS['names']}"])
    heroes = data.get("heroes") or {}
    if not ident["fighter"]:
        return _res("FAIL", ["нет имени бойца (ни Specs(), ни FIGHTER_NAME заявки)"])
    fighter = ident["fighter"].lower()
    hits = []
    for slug, e in heroes.items():
        for role in ("hero", "sidekick"):
            r = e.get(role) or {}
            if isinstance(r, dict) and str(r.get("en", "")).lower() == fighter and fighter:
                hits.append((slug, role, r))
    if hits:
        slug, role, r = hits[0]
        f = []
        if not r.get("ru"):
            f.append(f"{slug}.{role}: нет русского имени")
        if role == "hero" and ident["slug"] and slug != ident["slug"]:
            f.append(f"запись под слагом {slug!r}, в заявке HERO_SLUG {ident['slug']!r}")
        return _verdict(f, [f"{slug}.{role} = {r.get('ru')!r}"])
    if ident["owner_slug"]:
        return _res("SKIP", [f"только помощник героя {ident['owner_slug']!r}: формат держит одного помощника на героя, "
                             "табличка — серверное имя (Р7-8)"])
    entry = _registry_entry(repo, ident["asset_id"]) or {}
    m = re.match(r"^(.+?)-sidekick-", entry.get("contentKey") or "")
    if m and ((heroes.get(m.group(1)) or {}).get("sidekick") or {}).get("numbered"):
        return _res("PASS", [f"нумерованный помощник {m.group(1)!r} (hud.plate)"])
    return _res("FAIL", [f"нет записи с hero.en/sidekick.en = {ident['fighter']!r} (Р7-8): табличка — серверное имя"])


def check_de010(repo: Repo, ident, spec_row, consts) -> dict:
    row = ident["de010_row"]
    if row is None:
        return _res("FAIL", [f"нет строки HEROES с ключом {ident['key']!r} в {PATHS['de010']} (Р7-1): нет notify Contact "
                             "и MIC растворения"])
    f = []
    _key, stage, prof, contact = (tuple(row) + (None,) * 4)[:4]
    if spec_row and stage != spec_row["stage"]:
        f.append(f"Stage {stage!r} != Specs() {spec_row['stage']!r}")
    if spec_row and contact != spec_row["contact_frame"]:
        f.append(f"кадр контакта {contact} != Specs() {spec_row['contact_frame']}")
    spec = ident["de010_spec"]
    rel = f"{PATHS['candidates']}/{prof}"
    if spec is None:
        f.append(f"нет спеки {rel}")
        return _res("FAIL", f)
    if spec.get("ue_hero") != ident["key"]:
        f.append(f"спека {rel}: ue_hero {spec.get('ue_hero')!r} != {ident['key']!r}")
    if ident["character"] and spec.get("character") != ident["character"]:
        f.append(f"спека {rel}: character {spec.get('character')!r} != {ident['character']!r}")
    lunge = (spec.get("clips") or {}).get("LungeAttack") or {}
    if spec.get("fps") != 24 or lunge.get("frames") != 14 or contact not in (lunge.get("key_frames") or []):
        f.append(f"спека {rel}: fps {spec.get('fps')}, кадров {lunge.get('frames')}, key_frames "
                 f"{lunge.get('key_frames')} — de010 apply откажет (контакт {contact})")
    if ident["character"]:
        want = _clip_spec_path(consts["manifest"], ident["character"], "LungeAttack")
        if want and want != rel:
            f.append(f"de010 смотрит в {rel}, clip_manifest (LungeAttack) — в {want}")
    return _verdict(f, [f"{stage}, к.{contact}, {Path(prof).name}"])


def check_de011(ident, consts) -> dict:
    looks = consts["de011"].get("CAPTURE_LOOKS") or {}
    look = looks.get(ident["key"])
    if look not in ("P1", "P2"):
        return _res("FAIL", [f"CAPTURE_LOOKS[{ident['key']!r}] = {look!r} в {PATHS['de011']} (Р7-2): "
                             "de011 capture упадёт с KeyError"])
    return _res("PASS", [look])


def check_manifest(repo: Repo, ident, consts) -> dict:
    m, char = consts["manifest"], ident["character"]
    if not char:
        return _res("FAIL", ["персонаж (CHARACTER) не определён: нет заявки, строки de010 и HEROES листа клипов"])
    f = []
    chars = m.get("CHARS") or {}
    if char not in chars:
        f.append(f"CHARS[{char!r}] нет в {PATHS['manifest_py']} (Р6-1)")
    elif ident["asset_id"] and chars[char][1] != ident["asset_id"]:
        f.append(f"CHARS[{char!r}] = {chars[char][1]!r}, ожидается {ident['asset_id']!r}")
    if char not in (m.get("H2ANIM") or {}):
        f.append(f"H2ANIM[{char!r}] нет (Р6-1)")
        return _res("FAIL", f)
    for clip in CLIPS:
        rel = _clip_spec_path(m, char, clip)
        spec = _load_json_rel(repo, rel)
        if spec is None:
            f.append(f"{clip}: нет спеки {rel}")
            continue
        if clip not in (spec.get("clips") or {}):
            f.append(f"{clip}: в спеке {rel} нет клипа")
            continue
        if spec.get("ue_hero") != ident["key"]:
            f.append(f"{clip}: ue_hero спеки {spec.get('ue_hero')!r} != {ident['key']!r}")
        fbx = f"{spec.get('run_dir')}/export/AM_{spec.get('ue_hero')}_{clip}.fbx"
        if not (repo.root / fbx).is_file():
            f.append(f"{clip}: нет FBX {fbx}")
    schema = repo.json("manifest_schema") or {}
    enum = ((((schema.get("$defs") or {}).get("clip") or {}).get("properties") or {}).get("character") or {}).get("enum")
    if enum is not None and char not in enum:
        f.append(f"{char!r} нет в enum character схемы манифеста (Р6-2)")
    if char in chars:
        pre = chars[char][0]
        ids = {c.get("id") for c in (repo.json("manifest_json") or {}).get("clips", []) if c.get("role") == "production"}
        miss = [f"{pre}-{c}" for c in CLIPS if f"{pre}-{c}" not in ids]
        if miss:
            f.append(f"в clip-manifest.json нет записей {miss} (clip_manifest.py build)")
    return _verdict(f, [f"{char}: 4 клипа, спеки и FBX на месте"])


def check_sheet(repo: Repo, ident, spec_row, consts) -> dict:
    row = ident["sheet_row"]
    if row is None:
        return _res("FAIL", [f"нет HEROES[{ident['key']!r}] в {PATHS['sheet']} (Р6-4): лист AN-18 героя не построить"])
    f = []
    character, prefix, idle_s, cards = (tuple(row) + (None,) * 4)[:4]
    if ident["character"] and character != ident["character"]:
        f.append(f"персонаж {character!r} != {ident['character']!r}")
    chars = consts["manifest"].get("CHARS") or {}
    if character in chars and prefix != chars[character][0]:
        f.append(f"префикс {prefix!r} != CHARS {chars[character][0]!r}")
    if spec_row and idle_s is not None and abs(float(idle_s) - spec_row["idle_s"]) > 0.01:
        f.append(f"Idle {idle_s:.4g} с != Specs() {spec_row['idle_s']:.4g} с")
    cards = tuple(cards or ())
    if len(cards) != 4:
        f.append(f"карточек {len(cards)}, нужно 4")
    else:
        text = repo.text("anim_csv")
        ids = {r[0] for r in csv.reader(io.StringIO(text))} if text else set()
        miss = [c for c in cards if c not in ids]
        if text and miss:
            f.append(f"карточек {miss} нет в {PATHS['anim_csv']}")
    return _verdict(f, [f"{prefix}, {', '.join(cards)}"])


def check_rig(repo: Repo, ident) -> dict:
    rc = repo.json("rig")
    if rc is None:
        return _res("FAIL", [f"нет {PATHS['rig']}"])
    char, aid = ident["character"], ident["asset_id"]
    if not char:
        return _res("FAIL", ["персонаж (CHARACTER) не определён"])
    skels = rc.get("skeletons") or {}
    name = next((n for n, s in skels.items() if char in (s.get("characters") or {})), None)
    if name is None:
        return _res("FAIL", [f"characters[{char!r}] нет ни в одном скелете rig-contract.json (Р3-1): пробы рига — KeyError"])
    sk, f = skels[name], []
    entry = sk["characters"][char]
    if aid and entry.get("asset_id") != aid:
        f.append(f"characters[{char!r}].asset_id {entry.get('asset_id')!r} != {aid!r}")
    applies = sk.get("applies_to") or []
    if aid and not any(str(x) == aid or str(x).startswith(aid + " ") for x in applies):
        f.append(f"{name}.applies_to: нет {aid!r} (Р3-1)")
    sockets = [s for s in ((rc.get("ue_import") or {}).get("sockets_v2") or []) if "bone_by_character" in s]
    bbc = sockets[0]["bone_by_character"] if sockets else {}
    if char not in bbc:
        f.append(f"ue_import.sockets_v2 Weapon.bone_by_character: нет {char!r} (Р3-1)")
    wb = entry.get("weapon_bone")
    if wb:
        ue_wb = wb.replace(".", "_")
        if entry.get("ue_weapon_bone") != ue_wb:
            f.append(f"ue_weapon_bone {entry.get('ue_weapon_bone')!r} != {ue_wb!r}")
        if char in bbc and bbc[char] != ue_wb:
            f.append(f"bone_by_character[{char!r}] = {bbc[char]!r} != {ue_wb!r}")
    return _verdict(f, [f"{name}: {wb or 'без оружия'}"])


def _fixture_has_fighter(text: str, fighter: str) -> bool:
    pat = r'\\*"name\\*"\s*:\s*\\*"' + re.escape(fighter) + r'\\*"'
    return re.search(pat, text, re.I) is not None


def check_bench(repo: Repo, ident) -> dict:
    bench = repo.path("bench")
    fighter = ident["fighter"]
    if not fighter:
        return _res("FAIL", ["нет имени бойца — вариант фикстуры не проверить"])
    canon = {m: bench / f"S08Bench{m}.json" for m in MAPS}
    if all(p.is_file() and _fixture_has_fighter(p.read_text(encoding="utf-8-sig"), fighter) for p in canon.values()):
        return _res("SKIP", ["боец в канонических фикстурах обеих досок"])
    f = []
    for m in MAPS:
        p = bench / f"S08Bench{m}-{ident['key']}.json"
        rel = p.relative_to(repo.root).as_posix()
        if not p.is_file():
            f.append(f"нет {rel} (Р7-11: env_bench_fixtures.cts --variant {ident['key']})")
            continue
        text = p.read_text(encoding="utf-8-sig")
        try:
            data = json.loads(text)
        except ValueError:
            f.append(f"{rel}: не JSON")
            continue
        var = data.get("benchVariant") or {}
        if var.get("key") != ident["key"]:
            f.append(f"{rel}: benchVariant.key {var.get('key')!r}")
        if fighter not in (var.get("heroName"), var.get("sidekickName")):
            f.append(f"{rel}: benchVariant без бойца {fighter!r} (heroName {var.get('heroName')!r})")
        if canon[m].is_file():
            board = (json.loads(canon[m].read_text(encoding="utf-8-sig")) or {}).get("benchBoardId")
            if board and data.get("benchBoardId") != board:
                f.append(f"{rel}: benchBoardId {data.get('benchBoardId')!r} != {board!r} канонической")
        if not _fixture_has_fighter(text, fighter):
            f.append(f"{rel}: в состоянии нет бойца с name {fighter!r}")
    return _verdict(f, [", ".join(f"S08Bench{m}-{ident['key']}.json" for m in MAPS)])


def check_registry(repo: Repo, ident) -> dict:
    if repo.json("registry") is None:
        return _res("FAIL", [f"нет {PATHS['registry']}"])
    aid = ident["asset_id"]
    if not aid:
        return _res("FAIL", ["ASSET_ID не определён"])
    e = _registry_entry(repo, aid)
    if e is None:
        return _res("FAIL", [f"нет записи {aid} в {PATHS['registry']} (этап 0)"])
    f = []
    if e.get("status") not in UE_STATUSES or e.get("stage") not in UE_STAGES:
        f.append(f"{aid}: статус {e.get('status')!r}, стадия {e.get('stage')!r} — реестр не отражает импорт в UE (F161)")
    return _verdict(f, [f"{e.get('status')}, {e.get('stage')}"])


# ------------------------------------------------------------------------------------------------------ сборка
def check_all(repo_root: Path, heroes: list[str] | None = None) -> dict:
    repo = Repo(repo_root)
    spec_text = repo.text("specs")
    if spec_text is None:
        raise InputError(f"нет {PATHS['specs']} в {repo.root}")
    specs = parse_specs(spec_text)
    by_key = {s["key"]: s for s in specs}
    keys = heroes or [s["key"] for s in specs]
    consts = {"de010": repo.consts("de010", {"HEROES"}), "de011": repo.consts("de011", {"CAPTURE_LOOKS"}),
              "manifest": repo.consts("manifest_py", {"CHARS", "H2ANIM", "H2ANIM_CLIP"}),
              "sheet": repo.consts("sheet", {"HEROES"})}
    out = {}
    for key in keys:
        row = by_key.get(key)
        ident = identity(repo, key, row, consts)
        res = {"specs": check_specs(ident, row), "audio": check_audio(repo, ident), "cue": check_cue(repo, ident),
               "cook": check_cook(repo, ident), "names": check_names(repo, ident),
               "de010": check_de010(repo, ident, row, consts), "de011": check_de011(ident, consts),
               "manifest": check_manifest(repo, ident, consts), "sheet": check_sheet(repo, ident, row, consts),
               "rig": check_rig(repo, ident), "bench": check_bench(repo, ident), "registry": check_registry(repo, ident)}
        out[key] = {"identity": {k: v for k, v in ident.items() if k not in ("de010_row", "de010_spec", "sheet_row")},
                    "checks": res}
    counts = {s: sum(r["status"] == s for h in out.values() for r in h["checks"].values()) for s in ("PASS", "SKIP", "FAIL")}
    return {"schema": SCHEMA, "repo": repo.root.as_posix(), "items": list(ITEMS), "heroes": out, "summary": counts,
            "verdict": "FAIL" if counts["FAIL"] else "PASS"}


def render_table(report: dict) -> str:
    heroes = report["heroes"]
    w = max([len("hero")] + [len(k) for k in heroes]) + 1
    cell = {"PASS": "ok", "FAIL": "FAIL", "SKIP": "—"}
    head = "hero".ljust(w) + " ".join(i.ljust(max(len(i), 4)) for i in ITEMS)
    lines = [head, "-" * len(head)]
    for k, h in heroes.items():
        lines.append(k.ljust(w) + " ".join(cell[h["checks"][i]["status"]].ljust(max(len(i), 4)) for i in ITEMS))
    details = []
    for k, h in heroes.items():
        for i in ITEMS:
            r = h["checks"][i]
            if r["status"] != "PASS":
                for m in r["messages"] or [""]:
                    details.append(f"{r['status']:4} {k}.{i}: {m}")
    s = report["summary"]
    lines += [""] + details + ([""] if details else []) + [
        f"{report['verdict']}: героев {len(heroes)}, PASS {s['PASS']} SKIP {s['SKIP']} FAIL {s['FAIL']}"]
    return "\n".join(lines)


def _utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main(argv=None) -> int:
    _utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--heroes", default=None, help="ключи Key через запятую (по умолчанию — все строки Specs())")
    ap.add_argument("--json", action="store_true", help="отчёт JSON в stdout вместо таблицы")
    ap.add_argument("--repo", default=str(REPO_DEFAULT), help="корень чекаута (по умолчанию — этот)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    heroes = [h.strip() for h in args.heroes.split(",") if h.strip()] if args.heroes else None
    if args.heroes is not None and not heroes:
        print("ERROR: --heroes пуст", file=sys.stderr)
        return 2
    try:
        report = check_all(Path(args.repo), heroes)
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=1) if args.json else render_table(report))
    return 1 if report["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
