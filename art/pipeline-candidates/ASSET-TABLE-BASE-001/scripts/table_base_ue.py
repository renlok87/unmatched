"""ASSET-TABLE-BASE-001, UE stage through the LIVE UnrealEditor (Unreal MCP 127.0.0.1:8123; UE_MCP_URL not set).

    python art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/table_base_ue.py import|measure|scene [--run <dir>]

Every step runs under the shared editor lock C:/tmp/ue-editor.lock (tools/art/material_library/ue_lock.py, owner
"table-base"); the scene step does spawn + frames + clean-up + level restore inside ONE lock.

  import   /Game/PipelineCandidates/TableBase/<run>/{Textures,Materials,Meshes}: deletes only the assets this script
           planned there (anything else -> refuse), imports T_TableBase_{BC,N,ORM} (BC sRGB TC_Default; N linear
           TC_Normalmap, no green flip - the PNG is already DirectX; ORM linear TC_Masks), MI_TableBase_Candidate on
           /Game/UM/Materials/M_UM_Figure (the decor route of the barrel W4-B run; /Game/S05/M_DioramaMaster has no
           texture parameters), SM_TableBase (no importer materials/textures, collision removed), saves that folder.
  measure  read-back of mesh / textures / MI (ue-measure.json).
  scene    the P1.7 control level /Game/ArtTests/P17ControlScene/L_P17ControlScene (Cobble light, fixed EV100 1.3
           volume): refuses when the open level is dirty; loads it (NOT saved afterwards), spawns the tray at the board
           origin with the yaw of the ART005 board actor, frames with the UpdateBoardCamera model (FOV 35 horizontal,
           pitch -55, yaw -90, location = focus + (0, D cos55, D sin55)): K1 D 1931 focus (0,0,0), zoom-out 0.65x
           D 2971, follow-selection on the near row at 1.2x D 1609 (focus = cell (2,5) + 28 uu) and a 5x seam
           close-up; each also without the tray (A/B); destroys the temporary actors and loads the previous level.
Outputs in <run>/ue/ (reports) and <run>/preview/ue-*.png (1920x1080, centred 16:9 crop of CaptureViewport).
"""
import argparse
import base64
import hashlib
import io
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "tripo-pipeline" / "review"))
sys.path.insert(0, str(REPO / "tools" / "art" / "material_library"))
from ue_live import Ue  # noqa: E402
from ue_lock import ue_lock  # noqa: E402

OWNER = "table-base"
RUN_DEFAULT = REPO / "art/pipeline-candidates/ASSET-TABLE-BASE-001/20260928-table-base-tripo-h31"
TASK = HERE / "table_base_ue_task.py"
CS_TASK = REPO / "tools/tripo-pipeline/review/ue_py/control_scene_ue.py"
MASTER = "/Game/UM/Materials/M_UM_Figure"
LEVEL = "/Game/ArtTests/P17ControlScene/L_P17ControlScene"
FOV, PITCH, YAW = 35.0, -55.0, -90.0
K1, FOCUS_Z = 1931.0, 28.0
L_CAMERA = "TableBase board camera FOV35 - temporary"
L_TRAY = "TableBase tray - temporary"
NOANN = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0, "classFilter": None, "maxLabels": 0}
SHOW_FLAGS_OFF = ("Grid", "BillboardSprites", "Volumes")


def folder_of(run):
    return "/Game/PipelineCandidates/TableBase/" + run.name


def plan(run):
    f = folder_of(run)
    return {"texture:BC": f + "/Textures/T_TableBase_BC", "texture:N": f + "/Textures/T_TableBase_N",
            "texture:ORM": f + "/Textures/T_TableBase_ORM", "instance": f + "/Materials/MI_TableBase_Candidate",
            "static": f + "/Meshes/SM_TableBase"}


def objref(pkg):
    return {"refPath": "%s.%s" % (pkg, pkg.rsplit("/", 1)[-1])}


def pkg_of(ref):
    if isinstance(ref, dict):
        ref = ref.get("refPath", "")
    ref = str(ref)
    if "'" in ref:
        ref = ref.split("'")[1]
    return ref.split(".")[0]


def listing(ue, folder):
    return sorted(pkg_of(a) for a in (ue.call("asset", "find_assets", {"folder_path": folder, "name": "", "recursive": True}) or []))


def task(ue, run, op, timeout=600, script=TASK, **kw):
    Path("C:/tmp/table-base-ue").mkdir(parents=True, exist_ok=True)
    out = Path("C:/tmp/table-base-ue/_task.json")  # scratch, outside the repo
    return ue.run_task(str(script), str(out), timeout=timeout, op=op, **kw)


def cmd_import(run, rep):
    names = plan(run)
    folder = folder_of(run)
    with ue_lock("table-base import", owner=OWNER) as lk:
        ue = Ue()
        before = listing(ue, folder)
        foreign = [a for a in before if a not in names.values()]
        if foreign:
            raise SystemExit("UE folder %s holds assets this script did not plan: %s" % (folder, foreign))
        order = [names["static"], names["instance"]] + [names["texture:" + k] for k in ("BC", "N", "ORM")]
        deleted = []
        for a in order:
            if a in before:
                if not ue.call("asset", "delete", {"path": a}):
                    raise SystemExit("UE refused to delete %s" % a)
                deleted.append(a)
        texcfg = {"BC": {"SRGB": True, "CompressionSettings": "TC_Default"},
                  "N": {"SRGB": False, "CompressionSettings": "TC_Normalmap", "bFlipGreenChannel": False},
                  "ORM": {"SRGB": False, "CompressionSettings": "TC_Masks"}}
        for key, props in texcfg.items():
            pkg = names["texture:" + key]
            ue.call("texture", "import_file", {"folder_path": pkg.rsplit("/", 1)[0], "asset_name": pkg.rsplit("/", 1)[1],
                                               "source_file": str(run / "export" / ("T_TableBase_%s.png" % key))})
            ue.call("object", "set_properties", {"instance": objref(pkg), "values": json.dumps(props)})
        inst = names["instance"]
        ue.call("instance", "create", {"folder_path": inst.rsplit("/", 1)[0], "asset_name": inst.rsplit("/", 1)[1],
                                       "parent": objref(MASTER)})
        for key, pname in (("BC", "BaseColorTexture"), ("N", "NormalTexture"), ("ORM", "ORMTexture")):
            ue.call("instance", "set_texture_parameter", {"instance": objref(inst), "name": pname,
                                                          "value": objref(names["texture:" + key])})
        ue.call("instance", "set_vector_parameter", {"instance": objref(inst), "name": "TeamColor",
                                                     "value": {"r": 1, "g": 1, "b": 1, "a": 1}})
        sm = names["static"]
        ue.call("static", "import_file", {"folder_path": sm.rsplit("/", 1)[0], "asset_name": sm.rsplit("/", 1)[1],
                                          "source_file": str(run / "export" / "SM_TableBase.fbx"),
                                          "import_materials": False, "import_textures": False, "combine_meshes": True})
        ue.call("static", "remove_collisions", {"mesh": objref(sm)})
        slots = ue.call("static", "get_material_slots", {"mesh": objref(sm)}) or []
        for slot in slots:
            ue.call("static", "set_material", {"mesh": objref(sm), "slot_name": slot, "material": objref(inst)})
        after = listing(ue, folder)
        saved = ue.call("asset", "save_assets", {"asset_paths": after})
        rep["import"] = {"folder": folder, "lock": lk, "before": before, "deleted_previous": deleted, "after": after,
                         "planned": sorted(names.values()), "assets_exactly_as_planned": after == sorted(names.values()),
                         "numbered_duplicates": [a for a in after if a.rsplit("_", 1)[-1].isdigit()],
                         "material_slots": slots, "saved": saved, "master": MASTER,
                         "master_route": "M_UM_Figure (decor route of the barrel W4-B run); /Game/S05/M_DioramaMaster "
                                         "exposes only Roughness/BaseColor/TeamColor/Emissive, no texture parameters",
                         "texture_settings": texcfg}


def cmd_measure(run, rep):
    names = plan(run)
    with ue_lock("table-base measure", owner=OWNER) as lk:
        ue = Ue()
        res = task(ue, run, "measure", mesh=names["static"], instance=names["instance"],
                   textures={k: names["texture:" + k] for k in ("BC", "N", "ORM")})
        res["lock"] = lk
    rep["measure"] = res


def board_cam(focus, dist):
    p = math.radians(-PITCH)
    return [focus[0], focus[1] + dist * math.cos(p), focus[2] + dist * math.sin(p)], [PITCH, YAW, 0.0]


def grab(ue, xform):
    res = ue.call("app", "CaptureViewport", {"captureTransform": xform, "annotations": NOANN, "bShowUI": False},
                  record=False)
    v = res["value"] if isinstance(res, dict) and "value" in res else res
    img = v["image"] if isinstance(v, dict) and "image" in v else res["images"][0]
    return Image.open(io.BytesIO(base64.b64decode(img["data"]))).convert("RGB")


def shot(ue, run, name, focus, dist, frames, meta, eye_rot=None):
    eye, rot = eye_rot if eye_rot else board_cam(focus, dist)
    task(ue, run, "camera", script=CS_TASK, label=L_CAMERA, location=eye, rotation=rot, fov=FOV)
    xform = {"location": dict(zip("xyz", eye)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
             "scale": {"x": 1, "y": 1, "z": 1}}
    time.sleep(0.6)
    prev, settle = None, []
    for attempt in range(3):
        im = grab(ue, xform)
        if prev is not None:
            settle.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
        prev = im
        if attempt < 2:
            time.sleep(0.6)
    w, h = im.size
    ch = round(w * 9 / 16)
    box = (0, (h - ch) // 2, w, (h - ch) // 2 + ch) if ch <= h else ((w - round(h * 16 / 9)) // 2, 0,
                                                                      (w + round(h * 16 / 9)) // 2, h)
    frame = im.crop(box).resize((1920, 1080), Image.LANCZOS)
    path = run / "preview" / ("ue-%s.png" % name)
    frame.save(path, optimize=False)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    frames[name] = dict(meta, file=path.name, sha256=digest, focus=focus, distance_uu=dist, camera_location=eye,
                        camera_rotation_pyr=rot, viewport_px=[w, h], crop_px=list(box), settle_mean_abs_diff=settle)
    print(" ", path.name, digest[:12], settle, flush=True)
    return path


def cmd_scene(run, rep):
    names = plan(run)
    frames = {}
    sc = {"level": LEVEL, "frames": frames, "camera_model": {
        "fov_horizontal_deg": FOV, "pitch": PITCH, "yaw": YAW, "k1_uu": K1, "focus_offset_z_uu": FOCUS_Z,
        "source": "UpdateBoardCamera (S08FlowGameMode.cpp) as in tools/tripo-pipeline/review/control_scene.py"}}
    rep["scene"] = sc
    with ue_lock("table-base scene: spawn + frames + cleanup + restore", owner=OWNER) as lk:
        sc["lock"] = lk
        ue = Ue()
        state = task(ue, run, "state")
        sc["state_before"] = state
        original = state["current_level"]
        if state["dirty_maps"]:
            raise SystemExit("dirty map packages %s; refusing to switch levels" % state["dirty_maps"])
        if original == LEVEL:
            raise SystemExit("the control level itself is open; open another level first")
        spawned = False
        try:
            ue.call("scene", "load_level", {"level_path": LEVEL})
            sc["loaded"] = ue.call("scene", "get_current_level", record=False)
            board = task(ue, run, "board")
            sc["board_actors"] = board
            main = [a for a in board["actors"] if a["mesh"] and "Board" in a["mesh"]]
            yaw = main[0]["rotation_pyr"][1] if main else 0.0
            sc["board_main_actor"] = main[0] if main else None
            sc["tray_yaw"] = yaw
            # High (sg.* = 2) is the acceptance reference (AGENTS.md, W4-A); the editor runs Epic (3) -> set, restore
            want = {"r.ScreenPercentage": 100}
            want.update({n: 2 for n in ("sg.ViewDistanceQuality", "sg.AntiAliasingQuality", "sg.ShadowQuality",
                                        "sg.GlobalIlluminationQuality", "sg.ReflectionQuality", "sg.PostProcessQuality",
                                        "sg.TextureQuality", "sg.EffectsQuality", "sg.FoliageQuality", "sg.ShadingQuality")})
            cv = task(ue, run, "cvars", set=want)
            sc["cvars_set"] = cv
            for flag in SHOW_FLAGS_OFF:
                ue.console("ShowFlag.%s 0" % flag)
            sp = task(ue, run, "spawn", mesh=names["static"], label=L_TRAY, yaw=yaw, location=[0, 0, 0])
            spawned = True
            sc["tray_actor"] = sp["actor"]
            time.sleep(8.0)
            eye, rot = board_cam([0, 0, 0], K1)
            task(ue, run, "camera", script=CS_TASK, label=L_CAMERA, location=eye, rotation=rot, fov=FOV)
            xform = {"location": dict(zip("xyz", eye)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
                     "scale": {"x": 1, "y": 1, "z": 1}}
            prev, warm = None, []
            for _ in range(20):
                im = grab(ue, xform)
                if prev is not None:
                    d = float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean())
                    warm.append(round(d, 4))
                    if d < 0.02 and len(warm) >= 3:
                        break
                prev = im
                time.sleep(1.5)
            sc["warmup_mean_abs_diff"] = warm
            near = [0.0, 250.0, FOCUS_Z]  # cell (2,5): CellToWorld x = 2*100-200, y = 5*100-250 (near row, +Y)
            shots = [("k1-d1931", [0.0, 0.0, 0.0], K1, "K1 overview (1.0x), focus board centre"),
                     ("zoom065-d2971", [0.0, 0.0, 0.0], K1 / 0.65, "zoom-out limit 0.65x, not K1"),
                     ("follow12-nearrow-d1609", near, K1 / 1.2, "follow-selection 1.2x on the near row cell (2,5), not K1"),
                     ("seam-4x-nearedge-d483", [0.0, 340.0, 0.0], K1 / 4.0,
                      "4x close-up centred just outside the near board edge (y 328): seam board/tray, not K1")]
            for name, focus, dist, role in shots:
                shot(ue, run, name, focus, dist, frames, {"role": role, "tray": True})
            # diagnostics (not the game camera): the near skirt from a low angle and the tray from below
            diag = [("diag-near-skirt-low", [0.0, 1500.0, 40.0], [-5.0, -90.0, 0.0],
                     "diagnostic, not the game camera: near skirt from a low angle (pitch -5)"),
                    ("diag-3q-low", [1100.0, 1300.0, 250.0], [-12.0, -130.0, 0.0],
                     "diagnostic, not the game camera: three-quarter low view of the tray and board")]
            for name, eye, rot, role in diag:
                shot(ue, run, name, None, None, frames, {"role": role, "tray": True}, eye_rot=(eye, rot))
            task(ue, run, "set", script=CS_TASK, changes=[{"label": L_TRAY, "visible": False}])
            for name, focus, dist, role in shots[:3]:
                shot(ue, run, name + "-notray", focus, dist, frames, {"role": role + " - tray hidden (A/B)", "tray": False})
            sc["cvars_restored"] = task(ue, run, "cvars", set={k: v for k, v in cv["previous"].items()})
        finally:
            try:
                if spawned:
                    sc["cleanup"] = task(ue, run, "cleanup", labels=[L_TRAY, L_CAMERA])
                for flag in SHOW_FLAGS_OFF:
                    ue.console("ShowFlag.%s 2" % flag)
            finally:
                ue.call("scene", "load_level", {"level_path": original})
                sc["restored_level"] = ue.call("scene", "get_current_level", record=False)
                sc["state_after"] = task(ue, run, "state")
                sc["control_level_dirty_after"] = LEVEL.rsplit("/", 1)[-1] in sc["state_after"]["dirty_maps"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["import", "measure", "scene"])
    ap.add_argument("--run", default=str(RUN_DEFAULT))
    a = ap.parse_args()
    run = Path(a.run).resolve()
    (run / "ue").mkdir(parents=True, exist_ok=True)
    rpath = run / "ue" / ("ue-%s.json" % a.step)
    rep = {"schema": "unmatched.table-base-ue/1", "step": a.step, "run": run.name,
           "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "mcp": "UE 5.8 ModelContextProtocol 127.0.0.1:8123"}
    try:
        {"import": cmd_import, "measure": cmd_measure, "scene": cmd_scene}[a.step](run, rep)
        rep["ok"] = True
    except BaseException as exc:
        rep["ok"] = False
        rep["error"] = "%s: %s" % (type(exc).__name__, exc)
        raise
    finally:
        rep["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        rpath.write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
        print("wrote", rpath)


if __name__ == "__main__":
    main()
