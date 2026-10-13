import json
u = unreal  # noqa: F821
path = ARGS["package"]  # noqa: F821
res = {"package": path}
asset = u.EditorAssetLibrary.load_asset(path)
pkg = asset.get_outermost()
res["dirty_before"] = bool(pkg.is_dirty()) if hasattr(pkg, "is_dirty") else None
ok = u.EditorLoadingAndSavingUtils.reload_packages([pkg], u.ReloadPackagesInteractionMode.ASSUME_POSITIVE)
res["reload_result"] = str(ok)
dirty_content = [str(p.get_name()) for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
dirty_maps = [str(p.get_name()) for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
res["dirty_content_after"] = dirty_content
res["dirty_maps_after"] = dirty_maps
with open(ARGS["out"], "w", encoding="utf-8") as h:  # noqa: F821
    json.dump(res, h, indent=1)
