import json
import unreal as u
maps = [p.get_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
content = [p.get_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
info = {"dirty_maps": maps, "dirty_content": content,
        "pkg_has_set_dirty_flag": hasattr(u.Package, "set_dirty_flag"),
        "pkg_methods": [m for m in dir(u.Package) if "dirty" in m.lower()]}
open("C:/tmp/a1v3/ue_dirty.json", "w").write(json.dumps(info, indent=1))
