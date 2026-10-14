"""Шаг 7a (переимпорт, ue-import-package.md §4.4 п.2): удалить в живом редакторе ассеты прошлого прогона ue-import героя.

Берёт manifest.json прошлого прогона (`stages.ue-import.ue_owned_assets`), оставляет только пути под
/Game/PipelineCandidates/<Key>/<Stage>/ (скелет Rig/, клипы H2Anim/ и общие мастера не трогает), удаляет по порядку
MI → меши → текстуры (длинные пути раньше), затем перечисляет, что осталось в папке (ожидается пусто). Пилот
2026-10-14: evidence/stage7a-20261014/tasks/delete_prev.py у Leshen и Achilles.

    python tools/art/material_library/ue_lock.py --step "delete prev <Key>" -- \
        python tools/tripo-pipeline/ue7a/delete_prev.py --key Achilles --prev-run <asset-dir>/20261014-h2ld-ue-import-r3 \
        [--stage H2LD] [--out <json>]
    python tools/tripo-pipeline/ue7a/delete_prev.py --key Achilles --prev-run <dir> --dry-run   # только план

Код выхода: 0 — удалено и папка пуста, 1 — UE отказал или в папке что-то осталось, 2 — ошибка входа.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ue7a as c  # noqa: E402


def rank(path: str) -> tuple:
    """MI раньше мешей, меши раньше текстур; внутри — длинные пути (дочерние MI) раньше."""
    return (0 if "/Materials/" in path else 1 if "/Meshes/" in path else 2, -len(path), path)


def plan(manifest: dict, key: str, stage: str = "H2LD") -> list[str]:
    root = c.hero_paths(key, stage)["stage"] + "/"
    own = (((manifest.get("stages") or {}).get("ue-import") or {}).get("ue_owned_assets")) or []
    return sorted((a for a in own if isinstance(a, str) and a.startswith(root)), key=rank)


def main(argv=None) -> int:
    c.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--key", required=True, help="KEY героя (Achilles)")
    ap.add_argument("--prev-run", required=True, help="каталог прошлого прогона ue-import (с manifest.json)")
    ap.add_argument("--stage", default="H2LD", help="папка поколения под героем (H2LD)")
    ap.add_argument("--repo", default=str(c.REPO))
    ap.add_argument("--out", default=None, help="отчёт JSON {plan, deleted, left}")
    ap.add_argument("--dry-run", action="store_true", help="только план удаления, редактор не трогать")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    man = c.resolve(a.prev_run, repo) / "manifest.json"
    if not man.is_file():
        print(f"ERROR: нет {man}", file=sys.stderr)
        return 2
    try:
        todo = plan(c.load_json(man), a.key, a.stage)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    folder = c.hero_paths(a.key, a.stage)["stage"]
    rep = {"key": a.key, "folder": folder, "manifest": man.as_posix(), "plan": todo, "deleted": [], "left": None}
    if a.dry_run:
        print(json.dumps({"dry_run": True, **rep}, ensure_ascii=False, indent=1))
        return 0
    sys.path.insert(0, str(c.REVIEW))
    from ue_live import Ue  # noqa: E402

    ue = Ue()
    code = 0
    for asset in todo:
        if not ue.call("asset", "delete", {"path": asset}):
            rep["error"] = f"UE refused to delete {asset}"
            code = 1
            break
        rep["deleted"].append(asset)
        print("deleted", asset)
    rep["left"] = ue.call("asset", "find_assets", {"folder_path": folder, "name": "", "recursive": True})
    if rep["left"]:
        code = 1
    if a.out:
        c.write_json(c.resolve(a.out, repo), rep, indent=1)
    print("left", json.dumps(rep["left"], ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
