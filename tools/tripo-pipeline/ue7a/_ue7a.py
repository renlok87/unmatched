"""Общие помощники tools/tripo-pipeline/ue7a (шаги этапа 7a скилла 3d-model-pipeline): пути героя в UE, sha256,
запуск UE-задачи через ue_live.run_task (или план в --dry-run), перенацеливание JSON-шаблона на другого героя,
точечные правки JSON (--set / --set-json), правило LDV-13 для TeamDyeGain/Ceiling.

Только стандартная библиотека; ue_live импортируется лениво — тесты и --dry-run работают без редактора.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
REVIEW = REPO / "tools" / "tripo-pipeline" / "review"
MASTER_FIGURE = "/Game/UM/Materials/v2/M_UM_Figure_v2"
UE_MCP_URL = os.environ.get("UE_MCP_URL", "http://127.0.0.1:8123/mcp")


def utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def hero_paths(key: str, stage: str = "H2LD") -> dict:
    """Пути героя в UE (S08HeroesV2.cpp StageRoot, h2anim_ue.py skeleton/carrier)."""
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", key or ""):
        raise ValueError(f"--key должен быть PascalCase ключом героя (KEY заявки): {key!r}")
    root = f"/Game/PipelineCandidates/{key}"
    return {"root": root, "stage": f"{root}/{stage}", "materials": f"{root}/{stage}/Materials",
            "meshes": f"{root}/{stage}/Meshes", "rig": f"{root}/Rig", "clips": f"{root}/H2Anim",
            "carrier": f"{root}/Rig/SK_{key}", "skeleton": f"{root}/Rig/SK_{key}_Skeleton"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path, repo: Path) -> str:
    return Path(path).resolve().relative_to(Path(repo).resolve()).as_posix()


def resolve(path: str | Path, repo: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else Path(repo) / p


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path: Path, obj, indent: int = 2) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8", newline="\n")


def run_ue_task(script: Path, out: Path, *, dry_run: bool, timeout: int = 600, **args) -> dict:
    """UE-задача в живом редакторе (:8123) через ue_live.Ue.run_task; --dry-run печатает план и ничего не шлёт.
    Запускать под tools/art/material_library/ue_lock.py (один шаг UE за раз)."""
    plan = {"script": Path(script).resolve().as_posix(), "out": Path(out).resolve().as_posix(), "args": args,
            "mcp": UE_MCP_URL, "timeout_s": timeout}
    if dry_run:
        print(json.dumps({"dry_run": True, **plan}, ensure_ascii=False, indent=1))
        return {"dry_run": True, **plan}
    if str(REVIEW) not in sys.path:
        sys.path.insert(0, str(REVIEW))
    from ue_live import Ue  # noqa: E402 - только с живым редактором

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    return Ue().run_task(str(script), str(out), timeout=timeout, **args)


def team_dye(y50: float, y95: float) -> tuple[float, float]:
    """LDV-13 (team-accent.md): TeamDyeGain = 0,8 / Y_p50, TeamDyeCeiling = 0,9 / Y_p95 текселей акцента."""
    if y50 <= 0 or y95 <= 0:
        raise ValueError(f"Y_p50/Y_p95 акцента должны быть > 0: {y50}, {y95}")
    return round(0.8 / y50, 3), round(0.9 / y95, 4)


def retarget(obj, pairs, keep=None):
    """Рекурсивная замена подстрок во всех строках (и ключах словарей) JSON-объекта: pairs = [(old, new), …];
    строки, для которых keep(s) истинно, не трогаются (ссылки на исходного героя в derived_from и т. п.)."""
    def sub(s: str) -> str:
        if keep and keep(s):
            return s
        for old, new in pairs:
            s = old.sub(new.replace("\\", "\\\\"), s) if isinstance(old, re.Pattern) else s.replace(old, new)
        return s

    if isinstance(obj, dict):
        return {sub(k) if isinstance(k, str) else k: retarget(v, pairs, keep) for k, v in obj.items()}
    if isinstance(obj, list):
        return [retarget(v, pairs, keep) for v in obj]
    if isinstance(obj, str):
        return sub(obj)
    return obj


def name_pairs(old_key: str, new_key: str, old_content: str | None = None, new_content: str | None = None,
               old_asset: str | None = None, new_asset: str | None = None) -> list:
    """Замены шаблон → герой: ASSET_ID (как есть), content-key только как префикс «<ck>-» в путях и id
    (не внутри слов: ck «ant» не трогает «important»), Key — не внутри слова и не перед строчной буквой
    («SK_Angel_H2», «/Angel/» — да; «Angels», «evAngel» — нет)."""
    pairs = []
    if old_asset and new_asset:
        pairs.append((old_asset, new_asset))
    if old_content and new_content:
        pairs.append((re.compile(r"(?<![A-Za-z0-9])" + re.escape(old_content) + r"(?=-)"), new_content))
    pairs.append((re.compile(r"(?<![A-Za-z])" + re.escape(old_key) + r"(?![a-z])"), new_key))
    return pairs


def _split_path(path: str) -> list:
    return [int(p) if p.isdigit() else p for p in path.split(".")]


def set_path(obj, path: str, value) -> None:
    """obj[a][b][0][c] = value по пути «a.b.0.c» (промежуточные словари создаются)."""
    parts = _split_path(path)
    cur = obj
    for p in parts[:-1]:
        if isinstance(cur, list):
            cur = cur[p]
        else:
            cur = cur.setdefault(p, {})
    if isinstance(cur, list):
        cur[parts[-1]] = value
    else:
        cur[parts[-1]] = value


def pop_path(obj, path: str) -> None:
    parts = _split_path(path)
    cur = obj
    for p in parts[:-1]:
        cur = cur[p] if isinstance(cur, list) else cur.get(p, {})
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def apply_sets(obj, sets=(), set_jsons=(), drops=()) -> None:
    """--set a.b=text, --set-json a.b=<json>, --drop a.b — по порядку: drop, set, set-json."""
    for d in drops or ():
        pop_path(obj, d)
    for s in sets or ():
        k, _, v = s.partition("=")
        if not _:
            raise ValueError(f"--set ждёт путь=значение: {s!r}")
        set_path(obj, k, v)
    for s in set_jsons or ():
        k, _, v = s.partition("=")
        if not _:
            raise ValueError(f"--set-json ждёт путь=<json>: {s!r}")
        set_path(obj, k, json.loads(v))


def leftovers(obj, needle: str, allow=()) -> list:
    """Строки JSON, где осталось имя героя-шаблона (кроме разрешённых подстрок)."""
    s = json.dumps(obj, ensure_ascii=False, indent=1)
    rx = re.compile(r"(?<![A-Za-z])" + re.escape(needle) + r"(?![a-z])")
    return [ln.strip() for ln in s.splitlines() if rx.search(ln) and not any(a in ln for a in allow)]


def asset_card_fields(asset_dir: Path) -> dict:
    """Верхнеуровневые скаляры asset-card.yaml (KEY, CONTENT_KEY, ASSET_ID, …)."""
    p = Path(asset_dir) / "asset-card.yaml"
    out = {}
    if not p.is_file():
        return out
    for m in re.finditer(r"^([A-Z][A-Z0-9_]*):[ \t]*(.*)$", p.read_text(encoding="utf-8-sig"), re.M):
        v = re.sub(r"\s+#.*$", "", m.group(2).strip()) if not m.group(2).strip().startswith('"') else m.group(2).strip()
        if v.startswith('"'):
            end = v.find('"', 1)
            v = v[1:end] if end > 0 else v.strip('"')
        out.setdefault(m.group(1), None if v in ("null", "~", "") else v)
    return out
