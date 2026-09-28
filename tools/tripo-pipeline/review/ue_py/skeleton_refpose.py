"""UE editor Python task (LIVE editor via review/ue_live.py run_task): read-only reference poses of skeletons.

ARGS: {"out": "<out.json>", "skeletons": ["/Game/.../SK_X_Skeleton", ...]}
Per skeleton: bone names in index order, local and component-space reference transforms
(translation uu, rotation pitch/yaw/roll deg, scale). Loads the assets read-only; saves nothing.
"""
import json

import unreal as u


def xf(t):
    loc, rot, sc = t.translation, t.rotation.rotator(), t.scale3d
    return {"t": [round(loc.x, 4), round(loc.y, 4), round(loc.z, 4)],
            "r": [round(rot.pitch, 3), round(rot.yaw, 3), round(rot.roll, 3)],
            "s": [round(sc.x, 5), round(sc.y, 5), round(sc.z, 5)]}


args = ARGS  # noqa: F821 - injected by ue_py/_run.py
out = {}
for path in args["skeletons"]:
    skel = u.load_asset(path)
    if skel is None:
        out[path] = {"error": "not found"}
        continue
    pose = u.AnimPoseExtensions.get_reference_pose(skel)
    names = [str(n) for n in u.AnimPoseExtensions.get_bone_names(pose)]
    bones = {}
    for n in names:
        bones[n] = {"local": xf(u.AnimPoseExtensions.get_ref_bone_pose(pose, n, u.AnimPoseSpaces.LOCAL)),
                    "component": xf(u.AnimPoseExtensions.get_ref_bone_pose(pose, n, u.AnimPoseSpaces.WORLD))}
    out[path] = {"class": skel.get_class().get_name(), "bones_in_order": names, "bones": bones}
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
u.log("TRIPO_UE_PY_OK skeleton_refpose")
