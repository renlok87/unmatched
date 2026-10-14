"""Шаг 7a: перезагрузить пакет (по умолчанию M_UM_Figure_v2) в живом редакторе без сохранения и проверить, что грязных пакетов нет.

Зачем: импорт MI (ue-import, ue_hero_lookdev) помечает мастер M_UM_Figure_v2 грязным; сохранять его нельзя (мастер
пересобирают только de010/de011 в 7b), а закрытие редактора с грязным пакетом — вопрос «сохранить?». Пилот
2026-10-14 писал эту задачу трижды (evidence/stage7a-20261014/tasks/discard_master.py у Leshen и Achilles).

    python tools/art/material_library/ue_lock.py --step "discard master <Key>" -- \
        python tools/tripo-pipeline/ue7a/discard_master.py --out $E/stage7a/discard-master.json [--package /Game/…]
    python tools/tripo-pipeline/ue7a/discard_master.py --out x.json --dry-run      # план, без редактора

Один файл — две роли: на хосте разбирает аргументы и шлёт себя в редактор (ue_live.Ue.run_task); в редакторе
(tools/tripo-pipeline/review/ue_py/_run.py, __name__ == "__ue_task__") перезагружает пакет и пишет отчёт
{package, dirty_before, reload_result, dirty_content_after, dirty_maps_after}. Код выхода хоста: 0 — нет грязных
пакетов после перезагрузки, 1 — остались, 2 — ошибка аргументов.
"""
import json
import sys


def _ue_main(args, u):  # выполняется в редакторе
    path = args["package"]
    res = {"package": path}
    asset = u.EditorAssetLibrary.load_asset(path)
    if asset is None:
        raise RuntimeError("no asset %s" % path)
    pkg = asset.get_outermost()
    res["dirty_before"] = bool(pkg.is_dirty()) if hasattr(pkg, "is_dirty") else None
    ok = u.EditorLoadingAndSavingUtils.reload_packages([pkg], u.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
    res["reload_result"] = str(ok)
    res["dirty_content_after"] = [str(p.get_name()) for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    res["dirty_maps_after"] = [str(p.get_name()) for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
    with open(args["out"], "w", encoding="utf-8", newline="\n") as h:
        json.dump(res, h, indent=1)


def main(argv=None) -> int:
    import argparse
    import os

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _ue7a as c

    c.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--out", required=True, help="отчёт JSON")
    ap.add_argument("--package", default=c.MASTER_FIGURE, help="пакет для перезагрузки (M_UM_Figure_v2)")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true", help="напечатать план, редактор не трогать")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if not a.package.startswith("/Game/"):
        print("ERROR: --package должен начинаться с /Game/", file=sys.stderr)
        return 2
    res = c.run_ue_task(os.path.abspath(__file__), a.out, dry_run=a.dry_run, timeout=a.timeout, package=a.package)
    if a.dry_run:
        return 0
    left = (res.get("dirty_content_after") or []) + (res.get("dirty_maps_after") or [])
    print(json.dumps(res, ensure_ascii=False))
    return 1 if left else 0


if __name__ == "__ue_task__":
    _ue_main(ARGS, unreal)  # noqa: F821 - ARGS и unreal подставляет ue_py/_run.py
elif __name__ == "__main__":
    sys.exit(main())
