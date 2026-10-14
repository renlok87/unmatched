"""Шаг 7a (после доработки модели, F145): переимпортировать носитель превью клипов Rig/SK_<Key> из нового SK_<Key>_H2.fbx на СУЩЕСТВУЮЩИЙ скелет.

Зачем: `h2anim_ue.py skeleton` ничего не делает, если скелет уже есть (canonical_skeleton.py), и после доработки
модели носитель остаётся со старой геометрией — `h2anim_ue.py frames/measure` позируют старый меш (Leshen r3: ворона
на предплечье сдвинута на 4,25 см). Импорт как в canonical_skeleton.py (legacy FbxFactory, без материалов, текстур,
анимаций и physics asset, ImportNormals, масштаб 1,0, Nanite выкл.) + options.skeleton = канонический скелет +
replace_existing. Сохраняется только носитель; отчёт сравнивает опорную позу скелета до и после (должна совпасть).
Пилот 2026-10-14: evidence/stage7a-20261014/tasks/refresh_carrier.py у Leshen и Achilles.

    python tools/art/material_library/ue_lock.py --step "refresh carrier <Key>" -- \
        python tools/tripo-pipeline/ue7a/refresh_carrier.py --key Achilles \
        --spec <asset-dir>/build-profiles/achilles-h2anim-r3.json --out <h2anim run>/reports/ue-carrier-refresh.json
    … --fbx <SK_<Key>_H2.fbx>        # вместо --spec: FBX явно (по умолчанию target.sk_fbx спеки)
    … --dry-run                       # план, без редактора

Один файл — две роли (хост / задача редактора через ue_py/_run.py, __name__ == "__ue_task__"). Код выхода хоста:
0 — переимпорт, скелет тот же и опорная поза совпала, 1 — нет, 2 — ошибка входа.
"""
import json
import sys


def _ue_main(args, u):  # выполняется в редакторе
    mesh_pkg, skel_pkg = args["mesh"], args["skeleton"]
    if not mesh_pkg.startswith("/Game/PipelineCandidates/") or "/Rig/" not in mesh_pkg:
        raise RuntimeError("refusing a carrier outside /Game/PipelineCandidates/<Hero>/Rig: %s" % mesh_pkg)
    eal, els = u.EditorAssetLibrary, u.EditorLoadingAndSavingUtils

    def dirty():
        return sorted(str(p.get_name()) for p in els.get_dirty_content_packages()) + \
            sorted(str(p.get_name()) for p in els.get_dirty_map_packages())

    def ref_pose(skel):
        pose = u.AnimPoseExtensions.get_reference_pose(skel)
        res = {}
        for n in u.AnimPoseExtensions.get_bone_names(pose):
            t = u.AnimPoseExtensions.get_ref_bone_pose(pose, n, u.AnimPoseSpaces.WORLD).translation
            res[str(n)] = [round(t.x, 4), round(t.y, 4), round(t.z, 4)]
        return res

    def mesh_info(mesh):
        aid = mesh.get_editor_property("asset_import_data")
        b = mesh.get_bounds()
        info = {"source_files": [str(f) for f in (list(aid.extract_filenames()) if aid else [])],
                "bounds_origin": [round(b.origin.x, 3), round(b.origin.y, 3), round(b.origin.z, 3)],
                "bounds_extent": [round(b.box_extent.x, 3), round(b.box_extent.y, 3), round(b.box_extent.z, 3)],
                "skeleton": mesh.get_editor_property("skeleton").get_path_name()}
        try:
            info["source_file_hash"] = [str(x.file_hash) for x in
                                        aid.get_editor_property("source_data").get_editor_property("source_files")]
        except Exception as exc:  # noqa: BLE001 - необязательное чтение
            info["source_file_hash"] = "n/a: %s" % exc
        try:
            info["vertices_lod0"] = int(u.SkeletalMeshEditorSubsystem().get_num_verts(mesh, 0)) \
                if hasattr(u, "SkeletalMeshEditorSubsystem") else None
        except Exception as exc:  # noqa: BLE001
            info["vertices_lod0"] = "n/a: %s" % exc
        return info

    out = {"mesh": mesh_pkg, "skeleton": skel_pkg, "fbx": args["fbx"], "dirty_before": dirty()}
    if not eal.does_asset_exist(skel_pkg) or not eal.does_asset_exist(mesh_pkg):
        raise RuntimeError("carrier or skeleton missing: %s %s" % (mesh_pkg, skel_pkg))
    skel = u.load_asset(skel_pkg)
    out["before"] = mesh_info(u.load_asset(mesh_pkg))
    out["ref_pose_before"] = ref_pose(skel)
    o = u.FbxImportUI()
    for k, v in (("automated_import_should_detect_type", False), ("import_mesh", True), ("import_as_skeletal", True),
                 ("mesh_type_to_import", u.FBXImportType.FBXIT_SKELETAL_MESH),
                 ("original_import_type", u.FBXImportType.FBXIT_SKELETAL_MESH), ("skeleton", skel),
                 ("import_materials", False), ("import_textures", False), ("import_animations", False),
                 ("create_physics_asset", False)):
        o.set_editor_property(k, v)
    d = o.get_editor_property("skeletal_mesh_import_data")
    d.set_editor_property("normal_import_method", u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    d.set_editor_property("import_uniform_scale", 1.0)
    try:
        d.set_editor_property("import_morph_targets", False)
        d.set_editor_property("build_nanite", False)
    except Exception:  # noqa: BLE001 - необязательные свойства
        pass
    folder, name = mesh_pkg.rsplit("/", 1)
    t = u.AssetImportTask()
    for k, v in (("filename", args["fbx"]), ("destination_path", folder), ("destination_name", name),
                 ("replace_existing", True), ("automated", True), ("save", False), ("factory", u.FbxFactory()),
                 ("options", o)):
        t.set_editor_property(k, v)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    out["imported"] = [str(x) for x in t.get_editor_property("imported_object_paths")]
    mesh = u.load_asset(mesh_pkg)
    skel_after = mesh.get_editor_property("skeleton")
    if not skel_after or skel_after.get_path_name().split(".")[0] != skel_pkg:
        raise RuntimeError("carrier re-import changed the skeleton: %s" % (skel_after.get_path_name() if skel_after else None))
    out["after"] = mesh_info(mesh)
    out["ref_pose_after"] = ref_pose(u.load_asset(skel_pkg))
    out["ref_pose_equal"] = out["ref_pose_before"] == out["ref_pose_after"]
    out["dirty_after_import"] = dirty()
    out["saved"] = bool(eal.save_asset(mesh_pkg, only_if_is_dirty=False))
    out["dirty_after_save"] = dirty()
    with open(args["out"], "w", encoding="utf-8", newline="\n") as h:
        json.dump(out, h, indent=1)


def task_args(key: str, fbx_abs: str) -> dict:
    """Аргументы задачи редактора: меш-носитель и скелет героя (h2anim_ue.py skeleton)."""
    import os

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _ue7a as c

    p = c.hero_paths(key)
    return {"fbx": fbx_abs.replace("\\", "/"), "mesh": p["carrier"], "skeleton": p["skeleton"]}


def main(argv=None) -> int:
    import argparse
    import os
    from pathlib import Path

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _ue7a as c

    c.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--key", required=True, help="KEY героя (Achilles)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--spec", help="спека h2anim нового прогона: FBX = target.sk_fbx")
    src.add_argument("--fbx", help="SK_<Key>_H2.fbx нового bake явно")
    ap.add_argument("--out", required=True, help="отчёт JSON (обычно <h2anim run>/reports/ue-carrier-refresh.json)")
    ap.add_argument("--repo", default=str(c.REPO))
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--dry-run", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    try:
        if a.spec:
            spec = c.load_json(c.resolve(a.spec, repo))
            if spec.get("ue_hero") not in (None, a.key):
                raise ValueError(f"спека для героя {spec.get('ue_hero')!r}, а --key {a.key!r}")
            fbx = c.resolve((spec.get("target") or {}).get("sk_fbx") or "", repo)
        else:
            fbx = c.resolve(a.fbx, repo)
        if not fbx.is_file() or fbx.suffix.lower() != ".fbx":
            raise ValueError(f"нет FBX носителя {fbx}")
        args = task_args(a.key, str(fbx.resolve()))
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    res = c.run_ue_task(os.path.abspath(__file__), c.resolve(a.out, repo), dry_run=a.dry_run, timeout=a.timeout, **args)
    if a.dry_run:
        return 0
    ok = res.get("ref_pose_equal") is True and res.get("saved") is True
    print(json.dumps({k: res.get(k) for k in ("mesh", "ref_pose_equal", "saved", "dirty_after_save")}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__ue_task__":
    _ue_main(ARGS, unreal)  # noqa: F821 - ARGS и unreal подставляет ue_py/_run.py
elif __name__ == "__main__":
    sys.exit(main())
