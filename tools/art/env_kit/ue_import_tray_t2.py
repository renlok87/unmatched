"""ENV-MAPS track TRAY (ENV-U10): import the shared rocky tray SM_TableBase_T2 into UE (out of git, like the env kit).

Source: the headless-Blender run art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2 (tray_t2_run.py):
  export/SM_TableBase_T2.fbx          UM_FBX_v1 (centimetres = uu, UnitScaleFactor 1.0); pivot XY = the centre of the
                                      flat top (1560 x 940 at Z -3), Z = 0 = the board play plane; long side = UE X
  export/T_TableBase_T2_{BC,N,ORM}    TILING 2K textures (CC0 Rock058 toned to the T1 skirt; UV0 is a world box
                                      projection, 180 uu per repeat): BC sRGB, N DirectX, ORM linear (R AO, G rough, B 0)
Targets (S08Diorama.h T2MeshPath / T2MaterialPath; DefaultGame.ini always cooks the folder):
  /Game/PipelineCandidates/TableBase/T2/SM_TableBase_T2      legacy FbxFactory, import_uniform_scale 1.0, normals
                                                              imported, no materials / textures from the FBX, no
                                                              collision (decor; the board keeps the click surfaces),
                                                              Nanite off, the one slot -> MI_TableBase_T2
  /Game/PipelineCandidates/TableBase/T2/T_TableBase_T2_BC    sRGB TC_Default, address Wrap (tiling UVs)
  /Game/PipelineCandidates/TableBase/T2/T_TableBase_T2_N     linear TC_Normalmap, flip_green false (DirectX), Wrap
  /Game/PipelineCandidates/TableBase/T2/T_TableBase_T2_ORM   linear TC_Masks, Wrap
  /Game/PipelineCandidates/TableBase/T2/MI_TableBase_T2      child of /Game/UM/Materials/M_UM_Figure (the decor route
                                                              of T1 MI_TableBase_Candidate and the env kit): the three
                                                              textures, TeamColor white, TeamMask T_UM_Mask_Black,
                                                              one-sided
Helpers come from ue_import_env_kit.py (same FBX options, mesh settings, master check, metadata tags), so the tray is
imported exactly like the kit props. Checks before any import: the four sources exist and their sha256 equal the run's
reports (build-report.json export.sha256, textures-report.json outputs.*.sha256); a mismatch is never imported. After
the import: bounds equal the Blender build (geometry.boundsUeUU, +-0.5 uu), triangles within 1 % of the build (UE drops
degenerate triangles), Nanite off, no simple collision, the slot on the MI, nothing foreign / numbered in the folder.
Idempotent (metadata tag EnvKitSourceSha256 per asset). Report: 'TRAYT2-IMPORT-REPORT {...}', 'TRAYT2-IMPORT-RESULT
ok|failed', written to <project>/Saved/TableBaseT2/ue-import-report.json (or --report).

Run (the editor must be CLOSED; one UE process at a time in this workflow):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/env_kit/ue_import_tray_t2.py" -unattended -nosplash -nullrhi
Pre-check without UE (plain Python: presence + sha256, no import):
  python -B tools/art/env_kit/ue_import_tray_t2.py --check
Options: --run <run dir>  --report <json>  --force (re-import all)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ue_import_env_kit as K  # noqa: E402  (shared FBX / mesh / MI helpers; imports `unreal` when inside UE)

u = K.u
REPO = K.REPO
RUN_DEFAULT = REPO / "art" / "pipeline-candidates" / "ASSET-TABLE-BASE-001" / "20261001-tray-t2"
FOLDER = "/Game/PipelineCandidates/TableBase/T2"
MESH = "SM_TableBase_T2"
MI = "MI_TableBase_T2"
TEX = "T_TableBase_T2"
ASSETS = {"mesh": f"{FOLDER}/{MESH}", "mi": f"{FOLDER}/{MI}",
          **{f"tex:{k}": f"{FOLDER}/{TEX}_{k}" for k in K.TEXTURE_KEYS}}
BOUNDS_TOL_UU = 0.5
TRIS_TOL = 0.01


def plan(run: Path) -> dict:
    out = {"run": K.rel(run), "assets": ASSETS, "sources": {}, "ok": True, "verified": True, "reports": {}}
    reports = {}
    for name in ("build-report.json", "textures-report.json"):
        path = run / "reports" / name
        try:
            reports[name] = json.loads(path.read_text(encoding="utf-8"))
            out["reports"][name] = {"path": K.rel(path), "sha256": K.sha256_file(path),
                                    "checksPassed": reports[name].get("checks_passed")}
        except (OSError, ValueError) as exc:
            out["reports"][name] = {"path": K.rel(path), "error": f"unreadable: {exc}"}
            out["ok"] = False
    build, tex = reports.get("build-report.json", {}), reports.get("textures-report.json", {})
    want = {"fbx": (build.get("export") or {}).get("sha256")}
    want.update({k: ((tex.get("outputs") or {}).get(k) or {}).get("sha256") for k in K.TEXTURE_KEYS})
    files = {"fbx": run / "export" / f"{MESH}.fbx", **{k: run / "export" / f"{TEX}_{k}.png" for k in K.TEXTURE_KEYS}}
    for key, path in files.items():
        item = {"path": K.rel(path), "abs": str(path)}
        if not path.is_file():
            item["status"] = "missing"
            out["ok"] = False
        else:
            got = K.sha256_file(path)
            item.update(sha256=got, bytes=path.stat().st_size)
            if not want.get(key):
                item["status"] = "unverified"
                out["verified"] = False
                out["ok"] = False  # the tray is always built with its reports: no report = not this run's file
            elif got == want[key]:
                item["status"] = "verified"
            else:
                item.update(status="mismatch", expected=want[key], error="sha256 differs from the run's report")
                out["ok"] = False
        out["sources"][key] = item
    geo = build.get("geometry") or {}
    out["expected"] = {"boundsUeUU": geo.get("boundsUeUU"), "triangles": geo.get("triangles"),
                       "flatTop": geo.get("flatTop"), "checksPassed": build.get("checks_passed")}
    if build.get("checks_passed") is False:
        out["ok"] = False
        out["error"] = "the build report has failing checks"
    return out


# ------------------------------------------------------------------------------------------------ UE side
def texture_wanted(key: str) -> dict:
    wanted = K.texture_settings(key, "directx")
    wanted.update({"address_x": u.TextureAddress.TA_WRAP, "address_y": u.TextureAddress.TA_WRAP})
    return wanted


def import_texture(src: dict, asset: str, key: str, force: bool) -> dict:
    """ue_import_env_kit.import_texture + Wrap addressing (the T2 UVs tile)."""
    eal = u.EditorAssetLibrary
    wanted = texture_wanted(key)
    texture = u.load_asset(asset) if eal.does_asset_exist(asset) else None
    if (texture is not None and not force and eal.get_metadata_tag(texture, K.SHA_TAG) == src["sha256"]
            and K.settings_match(texture, wanted)):
        return {"action": "unchanged", **K.describe_texture(texture)}
    action = "reimported" if texture is not None else "imported"
    if texture is None or force or eal.get_metadata_tag(texture, K.SHA_TAG) != src["sha256"]:
        folder, leaf = K.split(asset)
        task = u.AssetImportTask()
        task.filename = src["abs"]
        task.destination_path = folder
        task.destination_name = leaf
        task.automated = True
        task.replace_existing = True
        task.save = False
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = u.load_asset(asset)
    else:
        action = "settings"
    if texture is None or not isinstance(texture, u.Texture2D):
        raise RuntimeError(f"import of {src['path']} did not produce the texture {asset}")
    for prop, value in wanted.items():
        texture.set_editor_property(prop, value)
    eal.set_metadata_tag(texture, K.SHA_TAG, src["sha256"])
    if not eal.save_loaded_asset(texture, False):
        raise RuntimeError(f"could not save {asset}")
    if not K.settings_match(texture, wanted):
        raise RuntimeError(f"{asset}: settings did not stick: {K.describe_texture(texture)}")
    return {"action": action, **K.describe_texture(texture),
            "address": [str(texture.get_editor_property("address_x")), str(texture.get_editor_property("address_y"))]}


def ensure_instance(master, textures: dict, mask) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = ASSETS["mi"]
    mi = u.load_asset(path) if eal.does_asset_exist(path) else None
    action = "updated"
    if mi is None:
        folder, leaf = K.split(path)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(leaf, folder, u.MaterialInstanceConstant,
                                                                 u.MaterialInstanceConstantFactoryNew())
        action = "created"
    if mi is None:
        raise RuntimeError(f"could not create {path}")
    white = u.LinearColor(1.0, 1.0, 1.0, 1.0)

    def rgba(c) -> tuple:
        return tuple(round(float(getattr(c, k)), 5) for k in ("r", "g", "b", "a"))

    def current() -> dict:
        parent = mi.get_editor_property("parent")
        state = {"parent": parent.get_path_name() if parent else None,
                 K.PARAM_TEAM: rgba(mel.get_material_instance_vector_parameter_value(mi, K.PARAM_TEAM))}
        for key, param in K.PARAMS.items():
            bound = mel.get_material_instance_texture_parameter_value(mi, param)
            state[param] = bound.get_path_name() if bound else None
        if mask is not None:
            bound = mel.get_material_instance_texture_parameter_value(mi, K.PARAM_MASK)
            state[K.PARAM_MASK] = bound.get_path_name() if bound else None
        return state

    want = {"parent": master.get_path_name(), K.PARAM_TEAM: rgba(white)}
    want.update({param: textures[key].get_path_name() for key, param in K.PARAMS.items()})
    if mask is not None:
        want[K.PARAM_MASK] = mask.get_path_name()
    if action == "updated" and current() == want:
        return {"action": "unchanged", "path": path, "params": {k: str(v) for k, v in want.items()}}
    mel.set_material_instance_parent(mi, master)
    for key, param in K.PARAMS.items():
        mel.set_material_instance_texture_parameter_value(mi, param, textures[key])
    if mask is not None:
        mel.set_material_instance_texture_parameter_value(mi, K.PARAM_MASK, mask)
    mel.set_material_instance_vector_parameter_value(mi, K.PARAM_TEAM, white)
    mel.update_material_instance(mi)
    if not eal.save_loaded_asset(mi, False):
        raise RuntimeError(f"could not save {path}")
    got = current()
    if got != want:
        raise RuntimeError(f"{path}: parameters did not bind: {got}")
    return {"action": action, "path": path, "params": {k: str(v) for k, v in want.items()}}


def measure(mesh, expected: dict) -> dict:
    sms = K.sm_api()
    box = mesh.get_bounding_box()
    mn, mx = box.min, box.max
    out = {"boundsMin": [round(mn.x, 3), round(mn.y, 3), round(mn.z, 3)],
           "boundsMax": [round(mx.x, 3), round(mx.y, 3), round(mx.z, 3)],
           "sizeUU": [round(mx.x - mn.x, 3), round(mx.y - mn.y, 3), round(mx.z - mn.z, 3)],
           "nanite": bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")),
           "simpleCollision": int(sms.get_simple_collision_count(mesh)),
           "slots": [mesh.get_material(i).get_path_name() if mesh.get_material(i) else None
                     for i in range(len(mesh.get_editor_property("static_materials")))]}
    try:
        out["trianglesLod0"] = int(mesh.get_num_triangles(0))
    except Exception:  # noqa: BLE001 - not exposed in every engine version
        out["trianglesLod0"] = None
    try:
        out["verticesLod0"] = int(sms.get_number_verts(mesh, 0))
    except Exception as exc:  # noqa: BLE001 - measurement only
        out["verticesLod0"] = f"n/a ({exc})"
    out.update(compare(out, expected))
    return out


def compare(measured: dict, expected: dict) -> dict:
    """World-free (also exercised by --check): bounds against the Blender build, triangle drift."""
    res = {}
    b = expected.get("boundsUeUU") or {}
    if b.get("min") and b.get("max"):
        delta = [round(measured["boundsMin"][i] - b["min"][i], 3) for i in range(3)] + \
                [round(measured["boundsMax"][i] - b["max"][i], 3) for i in range(3)]
        res["bounds"] = {"blenderMin": b["min"], "blenderMax": b["max"], "deltaUU": delta,
                         "ok": all(abs(d) <= BOUNDS_TOL_UU for d in delta)}
    t = expected.get("triangles")
    if t and isinstance(measured.get("trianglesLod0"), int):
        drift = abs(measured["trianglesLod0"] - t) / t
        res["triangles"] = {"blender": t, "ue": measured["trianglesLod0"], "drift": round(drift, 5),
                            "ok": drift <= TRIS_TOL}
    return res


def run_import(p: dict, force: bool) -> tuple[dict, bool]:
    eal = u.EditorAssetLibrary
    result: dict = {}
    master = u.load_asset(K.MASTER)
    if master is None:
        return {"error": f"master {K.MASTER} missing (tools/tripo-pipeline/um_masters.py builds it)"}, False
    result["master"] = K.check_master(master)
    if result["master"]["missing"]:
        return result, False
    mask = u.load_asset(K.MASK_NONE) if eal.does_asset_exist(K.MASK_NONE) else None
    result["teamMask"] = K.MASK_NONE if mask is not None else "missing (TeamColor white keeps BC unchanged anyway)"
    before = K.folder_listing(FOLDER) if eal.does_directory_exist(FOLDER) else []
    ok = True
    try:
        textures = {}
        result["textures"] = {}
        for key in K.TEXTURE_KEYS:
            result["textures"][key] = import_texture(p["sources"][key], ASSETS[f"tex:{key}"], key, force)
            textures[key] = u.load_asset(ASSETS[f"tex:{key}"])
        result["materialInstance"] = ensure_instance(master, textures, mask)
        mi = u.load_asset(ASSETS["mi"])
        fbx = p["sources"]["fbx"]
        mesh = u.load_asset(ASSETS["mesh"]) if eal.does_asset_exist(ASSETS["mesh"]) else None
        if (mesh is not None and not force and eal.get_metadata_tag(mesh, K.SHA_TAG) == fbx["sha256"]
                and eal.get_metadata_tag(mesh, K.SCALE_TAG) == "1"):
            result["mesh"] = {"action": "unchanged"}
        else:
            result["mesh"] = dict(K.import_mesh(fbx, ASSETS["mesh"], 1.0),
                                  action="reimported" if mesh is not None else "imported")
            mesh = u.load_asset(ASSETS["mesh"])
            if mesh is None or not isinstance(mesh, u.StaticMesh):
                raise RuntimeError(f"{ASSETS['mesh']} is not a static mesh after the import")
            eal.set_metadata_tag(mesh, K.SHA_TAG, fbx["sha256"])
            eal.set_metadata_tag(mesh, K.SCALE_TAG, "1")
        settings = K.ensure_mesh_settings(mesh, mi)
        result["mesh"]["settingsChanged"] = settings["changes"]
        if settings["changes"] or result["mesh"]["action"] != "unchanged":
            if not eal.save_loaded_asset(mesh, False):
                raise RuntimeError(f"could not save {ASSETS['mesh']}")
        m = result["measure"] = measure(mesh, p["expected"])
        problems = []
        if m["nanite"]:
            problems.append("nanite still on")
        if m["simpleCollision"]:
            problems.append("simple collision left")
        if not m["slots"] or any(s != mi.get_path_name() for s in m["slots"]):
            problems.append("material slots not on the MI")
        if not (m.get("bounds") or {}).get("ok"):
            problems.append(f"bounds differ from the Blender build: {m.get('bounds')}")
        if (m.get("triangles") or {}).get("ok") is False:
            problems.append(f"triangles differ from the build by > {TRIS_TOL:.0%}: {m.get('triangles')}")
        result["problems"] = problems
        ok = not problems
    except Exception as exc:  # report it
        result["error"] = f"{type(exc).__name__}: {exc}"
        ok = False
    after = K.folder_listing(FOLDER) if eal.does_directory_exist(FOLDER) else []
    planned = set(ASSETS.values())
    result["folder"] = {"path": FOLDER, "before": before, "after": after,
                        "foreign": [a for a in after if a not in planned],
                        "numberedDuplicates": [a for a in after if re.search(r"_\d+$", a)],
                        "missing": sorted(planned - set(after))}
    ok = ok and not result["folder"]["missing"] and not result["folder"]["numberedDuplicates"]
    return result, ok


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--run", default=str(RUN_DEFAULT))
    ap.add_argument("--report", default=None)
    ap.add_argument("--check", action="store_true", help="verify the sources only (no UE import)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    started = time.time()
    p = plan(Path(a.run).resolve())
    out = {"schema": "unmatched.table-base-t2-ue-import/1", "tool": "tools/art/env_kit/ue_import_tray_t2.py",
           "mode": "check" if (a.check or u is None) else "import", "folder": FOLDER, "master": K.MASTER,
           "importScale": 1.0, "normalConvention": "directx", "plan": p}
    ok = p["ok"]
    if out["mode"] == "import" and ok:
        out["ue"], import_ok = run_import(p, a.force)
        out["engine"] = str(u.SystemLibrary.get_engine_version())
        ok = ok and import_ok
    out["ok"] = ok
    out["seconds"] = round(time.time() - started, 1)
    text = json.dumps(out, ensure_ascii=False, indent=1, default=str)
    if a.report:
        path = Path(a.report)
    elif u is not None:
        path = Path(u.Paths.project_saved_dir()) / "TableBaseT2" / "ue-import-report.json"
    else:
        path = None
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        out["reportPath"] = str(path)
    counts: dict = {}
    for item in p["sources"].values():
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print("TRAYT2-IMPORT-REPORT " + json.dumps(out, ensure_ascii=False, default=str))
    print(f"TRAYT2-IMPORT-RESULT {'ok' if ok else 'failed'} mode={out['mode']} sources={json.dumps(counts, sort_keys=True)}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        raise RuntimeError("TRAYT2 import failed - see TRAYT2-IMPORT-REPORT")
