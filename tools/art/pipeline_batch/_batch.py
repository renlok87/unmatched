"""Общие помощники tools/art/pipeline_batch (клей пакетного режима скилла 3d-model-pipeline): корень репозитория,
скаляры asset-card.yaml, плейсхолдеры {{KEY}} шаблонов скилла, sha256, контейнер GLB и рамки частей по вершинам (F10).

Только стандартная библиотека и numpy (рамки частей); ничего не запускает сам.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ACCEPTANCE = Path(__file__).resolve().parents[1] / "acceptance"
SKILL = Path(".agents/skills/3d-model-pipeline/references/concept-sheet.md")
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def side_models():
    """tools/art/acceptance/side_models.py: профили приёмщиков («Opus xhigh», второй «Opus high»), «Codex/Sol отключён
    2026-10-20», Z-Code снят с приёмки 2026-10-21 (ZCODE_GONE), заглушка полосы Z-Code."""
    if str(ACCEPTANCE) not in sys.path:
        sys.path.insert(0, str(ACCEPTANCE))
    import side_models as sm  # noqa: PLC0415
    return sm


def utf8_env() -> dict:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "MSYS_NO_PATHCONV": "1"}


def asset_id(content_key: str) -> str:
    """content-key (kebab) → ASSET-<KEBAB UPPER>-001 (правило этапа 0)."""
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", content_key or ""):
        raise ValueError(f"content-key должен быть kebab-case: {content_key!r}")
    return f"ASSET-{content_key.upper()}-001"


def scalar(card: str, name: str):
    """Верхнеуровневое поле «NAME: значение» asset-card.yaml; строка в кавычках — как JSON; нет поля — ""."""
    m = re.search(r"^" + re.escape(name) + r":[ \t]*(.*)$", card, re.M)
    v = m.group(1).strip() if m else ""
    if v.startswith('"'):
        end = v.rfind('"')
        try:
            return json.loads(v[:end + 1])
        except ValueError:
            return v.strip('"')
    return re.sub(r"\s+#.*$", "", v).strip()


def fill(template: str, mapping: dict) -> str:
    """{{KEY}} → mapping[KEY]; незнакомый плейсхолдер — KeyError (шаблон и данные разошлись)."""
    def sub(mo):
        k = mo.group(1)
        if k not in mapping:
            raise KeyError(k)
        return str(mapping[k])
    return PLACEHOLDER.sub(sub, template)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path, repo: Path) -> str:
    return Path(path).resolve().relative_to(Path(repo).resolve()).as_posix()


def run(args: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=utf8_env())


# ------------------------------------------------------------------------------------------------------------ GLB
def container_ok(data: bytes) -> bool:
    """Двоичный glTF 2: магия, версия, длина = размер файла, чанки покрывают файл без хвоста."""
    if len(data) < 12:
        return False
    magic, ver, length = struct.unpack_from("<4sII", data, 0)
    off = 12
    while off + 8 <= len(data):
        off += 8 + struct.unpack_from("<I", data, off)[0]
    return magic == b"glTF" and ver == 2 and length == len(data) and off == len(data)


def glb_json(data: bytes) -> tuple[dict, int]:
    """(JSON-чанк, смещение данных BIN-чанка)."""
    n = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20:20 + n]), 20 + n + 8


def part_boxes(data: bytes) -> list:
    """Рамки частей (узлов с мешем) по ВЕРШИНАМ, метры glTF (Y вверх). accessor.min/max не годится: Tripo пишет
    в min[1] DBL_MIN (F10, tripo3d-stages.md §6 п.9). Только POSITION float32 VEC3 (так у Tripo)."""
    import numpy as np

    j, binoff = glb_json(data)
    out = []
    for node in j.get("nodes", []):
        if "mesh" not in node:
            continue
        mesh = j["meshes"][node["mesh"]]
        lo, hi, tris = [1e9] * 3, [-1e9] * 3, 0
        for prim in mesh["primitives"]:
            acc = j["accessors"][prim["attributes"]["POSITION"]]
            if acc.get("componentType", 5126) != 5126 or acc.get("type", "VEC3") != "VEC3":
                raise ValueError(f"POSITION не float32 VEC3 в меше {mesh.get('name')!r}")
            bv = j["bufferViews"][acc["bufferView"]]
            start = binoff + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            stride = bv.get("byteStride", 12)
            count = acc["count"]
            raw = np.frombuffer(data, dtype=np.uint8, count=stride * (count - 1) + 12, offset=start)
            raw = np.concatenate([raw, np.zeros(stride - 12, np.uint8)]) if stride > 12 else raw
            v = raw.reshape(count, stride)[:, :12].copy().view(np.float32).reshape(-1, 3)
            lo = [min(x, float(y)) for x, y in zip(lo, v.min(axis=0))]
            hi = [max(x, float(y)) for x, y in zip(hi, v.max(axis=0))]
            if "indices" in prim:
                tris += j["accessors"][prim["indices"]]["count"] // 3
            else:
                tris += count // 3
        out.append({"node": node.get("name"), "mesh": mesh.get("name"), "tris": tris,
                    "min": [round(x, 4) for x in lo], "max": [round(x, 4) for x in hi]})
    return out


def inspect_glb(path: Path) -> dict:
    """tools/tripo-pipeline/tripo_pipeline.py inspect_glb (меши, треугольники, материалы, картинки, скины)."""
    tp = REPO / "tools" / "tripo-pipeline"
    if str(tp) not in sys.path:
        sys.path.insert(0, str(tp))
    from tripo_pipeline import inspect_glb as _inspect  # noqa: E402

    return _inspect(Path(path))


def skill_block(text: str, heading: str, opener: str = "```text\n", closer: str = "\n```") -> str:
    """Блок кода после заголовка раздела скилла (шаблоны берутся из скилла дословно)."""
    i = text.index(heading)
    a = text.index(opener, i) + len(opener)
    return text[a:text.index(closer, a)]
