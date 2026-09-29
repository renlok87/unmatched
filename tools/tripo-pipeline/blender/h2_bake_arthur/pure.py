"""bpy-free helpers shared by the Blender stages and the system-python stages of the H2 bake."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BLENDER_EXE = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
STAGE_MARKER = "H2_BAKE_STAGE_OK"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path):
    """Repository-relative posix path (absolute if outside the repository)."""
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def r(value, nd=6):
    return round(float(value), nd)


def rv(values, nd=6):
    return [r(v, nd) for v in values]


def run_paths(run_dir):
    run = Path(run_dir).resolve()
    return {name: run / name for name in ("export", "textures", "reports", "preview", "work", "logs")} | {"run": run}


def repo_path(p):
    return (REPO / p).resolve()
