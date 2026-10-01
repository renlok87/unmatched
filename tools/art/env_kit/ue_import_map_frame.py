"""ENV-MAPS P5 track C (concept review gap 9, full): import the heavy modular map frame ASSET-MAP-FRAME-002 into UE.

Source: the headless-Blender run of lane K, art/pipeline-candidates/ASSET-MAP-FRAME-002/20261001-frame-v1
(scripts/frame_build.py; docs/game-design/evidence/ENV-MAPS/p5k-blender-assets-2026-10-01/README.md, handoff item 2):
  export/SM_MapFrame002_{Corner,SegA,SegB,SegMid}.fbx  UM_FBX_v1 (centimetres = uu, UnitScaleFactor 1.0); pivot on the
                                      inner map edge / inner map corner at the play plane (z 0), wood z -10 .. +12.4,
                                      two material slots M_MapFrame002_Wood (UV0 tiles T_old_wood, grain along V) and
                                      M_MapFrame002_Iron (SegA / SegB have no iron faces)
  export/T_MapFrame002_Iron_{BC,N,ORM}.png  1K tiling iron (CC0 Metal038 + Metal017 rust): BC sRGB, N DirectX, ORM linear
  reports/frame-layout.json           the 20 instances (S08BoardArt.cpp S08MapFrame002Layout mirrors frame_layout.py)
Targets (S08BoardArt.h S08MapSurfaceSpec::Frame002*; /Game/EnvMaps is always cooked, Content/ is out of git):
  /Game/EnvMaps/Frame/SM_MapFrame002_<Module>   legacy FbxFactory (ue_import_env_kit.import_mesh): import_uniform_scale
                                                1.0, normals imported, no FBX materials / textures, no collision (simple
                                                shapes removed + CTF_UseSimpleAsComplex), Nanite off; slot by NAME:
                                                M_MapFrame002_Wood -> /Game/EnvMaps/M_MapFrameWood (the board actor puts
                                                the profile's frameWood MID on it at runtime), M_MapFrame002_Iron ->
                                                MI_MapFrame002_Iron
  /Game/EnvMaps/Frame/T_MapFrame002_Iron_{BC,N,ORM}  BC sRGB TC_Default, N TC_Normalmap flip_green false, ORM TC_Masks
                                                linear; address Wrap (tiling UVs)
  /Game/EnvMaps/Frame/MI_MapFrame002_Iron       child of /Game/EnvKit/Shared/M_EnvProp (env_prop_look.py) with the three
                                                textures and the iron look of reports/frame-iron-look.json: brighter,
                                                cooler, smoother than the Blender preview so the iron separates from the
                                                darker frame wood (p5k open issue: BC ~0.25 sRGB metal on dark wood)
M_MapFrameWood is built by tools/art/map_surface/ue_import_map_surface.py (build_frame_wood) and M_EnvProp by
ue_import_env_kit.py (build_env_master); this script calls both builders (idempotent: version tags) so the order does
not matter.

Checks before any import: every source exists and its sha256 equals the run's reports (build-report.json exports[].sha256,
textures-report.json outputs.*.sha256); a mismatch is never imported. After the import: per mesh bounds equal the build's
boundsUeLocalUU (+-0.5 uu), triangles within 1 % of the build, Nanite off, no simple collision, the wood slot on
M_MapFrameWood and the iron slot (when present) on the MI, nothing foreign / numbered in the folder. Idempotent (metadata
tag EnvKitSourceSha256). Report: 'MAPFRAME-IMPORT-REPORT {...}', 'MAPFRAME-IMPORT-RESULT ok|failed', written to
<project>/Saved/EnvMaps/map-frame-import-report.json (or --report).

Run (the editor must be CLOSED; one UE process at a time; UBT / commandlets under C:/tmp/unmatched-package.lock):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/env_kit/ue_import_map_frame.py" -unattended -nosplash -nullrhi
Pre-check without UE (plain Python: sources + sha256, layout cross-check, iron-vs-wood separation of the look):
  python -B tools/art/env_kit/ue_import_map_frame.py --check
Options: --run <run dir>  --look <json>  --report <json>  --force (re-import all)
Status: предложено (technically importable; artistically accepted only by the user).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "art" / "map_surface"))
import env_prop_look as look_lib  # noqa: E402  (M_EnvProp parameters + numpy mirror; plain Python)
import ue_import_env_kit as K  # noqa: E402  (FBX / mesh helpers, M_EnvProp builder; imports `unreal` inside UE)

u = K.u
RUN_DEFAULT = REPO / "art" / "pipeline-candidates" / "ASSET-MAP-FRAME-002" / "20261001-frame-v1"
LOOK_DEFAULT = RUN_DEFAULT / "reports" / "frame-iron-look.json"
WOOD_PNG = REPO / "art" / "imagegen" / "mvp-v1" / "materials" / "export" / "T_old_wood_D_1024.png"  # = T_old_wood_D_1024
FOLDER = "/Game/EnvMaps/Frame"
MODULES = ("Corner", "SegA", "SegB", "SegMid")
MESH = {m: f"SM_MapFrame002_{m}" for m in MODULES}
TEX = "T_MapFrame002_Iron"
TEXTURE_KEYS = ("BC", "N", "ORM")
MI = "MI_MapFrame002_Iron"
LOOK_PROP = "MapFrame002Iron"
WOOD_SLOT = "M_MapFrame002_Wood"
IRON_SLOT = "M_MapFrame002_Iron"
WOOD_MATERIAL = "/Game/EnvMaps/M_MapFrameWood"
ENV_MASTER = look_lib.MASTER_PATH
SHA_TAG = "EnvKitSourceSha256"
SCALE_TAG = "EnvKitImportScale"
ASSETS = {**{f"mesh:{m}": f"{FOLDER}/{MESH[m]}" for m in MODULES}, "mi": f"{FOLDER}/{MI}",
          **{f"tex:{k}": f"{FOLDER}/{TEX}_{k}" for k in TEXTURE_KEYS}}
BOUNDS_TOL_UU = 0.5
TRIS_TOL = 0.01
# The P4 profile frameWood values (S08ArtBoardProfiles.json: valueScaleSrgb 0.7, saturation 0.75) = M_MapFrameWood.
FRAME_WOOD = {"valueScaleSrgb": 0.7, "saturation": 0.75}
# Separation the iron look must reach against the graded frame wood (texture space, see iron_separation()).
SEPARATION_TARGETS = {"minLumaRatio": 2.5, "minDeltaLstar": 12.0, "maxIronSaturation": 0.15, "maxRoughnessMean": 0.7}


def rel(path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split(path: str) -> tuple[str, str]:
    folder, leaf = path.rsplit("/", 1)
    return folder, leaf


# ------------------------------------------------------------------------------------------------ plain Python
def load_look(path: Path = LOOK_DEFAULT) -> dict:
    data = look_lib.load_look(path)  # schema / master / ranges (env_prop_look.validate_look)
    if LOOK_PROP not in data["props"]:
        raise ValueError(f"{path}: props.{LOOK_PROP} missing")
    return data


def iron_params(look: dict) -> dict:
    return look_lib.mi_params(look, LOOK_PROP)


def iron_separation(look: dict | None, run: Path = RUN_DEFAULT, size: int = 256) -> dict:
    """Texture-space separation of the iron (BC through the M_EnvProp look, the numpy mirror) from the frame wood
    (T_old_wood_D through M_MapFrameWood's grade at the P4 profile values). look None = the neutral M_EnvProp (the
    Blender preview look). Not a render: linear luma ratio, CIE L* difference, mean HSV saturation of the iron, mean
    roughness after the RoughnessMin/Max remap of ORM.G. Under the night key light the frame reads as two dark
    materials when the ratio is ~1.5 and the iron is as rough as the wood (p5k)."""
    import numpy as np
    from PIL import Image

    def load(path: Path):
        return np.asarray(Image.open(path).convert("RGB").resize((size, size), Image.BOX), dtype=np.float64) / 255.0

    luma_w = np.array([0.2126, 0.7152, 0.0722])
    wood = look_lib.srgb_to_linear(load(WOOD_PNG))
    wl = wood @ luma_w
    v_lin = FRAME_WOOD["valueScaleSrgb"] ** 2.2
    wood_g = np.maximum(wl[..., None] + (wood - wl[..., None]) * FRAME_WOOD["saturation"], 0.0) * v_lin
    params = iron_params(look) if look else {"scalar": dict(look_lib.SCALAR_DEFAULTS),
                                              "vector": {k: tuple(v) for k, v in look_lib.VECTOR_DEFAULTS.items()}}
    iron_bc = load(run / "export" / f"{TEX}_BC.png")
    res = look_lib.apply_look(iron_bc, params)
    iron = res["linear"]
    orm = load(run / "export" / f"{TEX}_ORM.png")
    s = params["scalar"]
    rough = s["RoughnessMin"] + (s["RoughnessMax"] - s["RoughnessMin"]) * orm[..., 1]

    def lstar(y: float) -> float:
        return 116.0 * (y ** (1.0 / 3.0)) - 16.0 if y > 0.008856 else 903.3 * y

    iy, wy = float((iron @ luma_w).mean()), float((wood_g @ luma_w).mean())
    ihsv = look_lib.rgb_to_hsv(look_lib.linear_to_srgb(iron))
    whsv = look_lib.rgb_to_hsv(look_lib.linear_to_srgb(wood_g))
    out = {"ironLumaLinear": round(iy, 5), "woodLumaLinear": round(wy, 5), "lumaRatio": round(iy / wy, 3),
           "deltaLstar": round(lstar(iy) - lstar(wy), 2), "ironSaturation": round(float(ihsv[..., 1].mean()), 4),
           "woodSaturation": round(float(whsv[..., 1].mean()), 4), "ironRoughnessMean": round(float(rough.mean()), 4),
           "ironMetallicMean": round(float(orm[..., 2].mean()), 4)}
    t = SEPARATION_TARGETS
    out["targets"] = dict(t)
    out["ok"] = (out["lumaRatio"] >= t["minLumaRatio"] and out["deltaLstar"] >= t["minDeltaLstar"]
                 and out["ironSaturation"] <= t["maxIronSaturation"] and out["ironRoughnessMean"] <= t["maxRoughnessMean"])
    return out


def build_entry(build: dict, name: str) -> dict:
    for e in build.get("exports") or []:
        if e.get("name") == name:
            return e
    return {}


def plan(run: Path, look_path: Path) -> dict:
    out = {"run": rel(run), "assets": ASSETS, "sources": {}, "ok": True, "reports": {}, "expected": {}}
    reports = {}
    for name in ("build-report.json", "textures-report.json", "frame-layout.json"):
        path = run / "reports" / name
        try:
            reports[name] = json.loads(path.read_text(encoding="utf-8"))
            out["reports"][name] = {"path": rel(path), "sha256": sha256_file(path)}
        except (OSError, ValueError) as exc:
            out["reports"][name] = {"path": rel(path), "error": f"unreadable: {exc}"}
            out["ok"] = False
    build, tex = reports.get("build-report.json", {}), reports.get("textures-report.json", {})
    if build.get("checks_passed") is not True:
        out["ok"] = False
        out["error"] = "the build report is missing or has failing checks"
    files, want = {}, {}
    for m in MODULES:
        e = build_entry(build, MESH[m])
        files[f"fbx:{m}"] = run / "export" / f"{MESH[m]}.fbx"
        want[f"fbx:{m}"] = e.get("sha256")
        out["expected"][m] = {"boundsUeUU": e.get("boundsUeLocalUU"), "triangles": e.get("triangles"),
                              "slots": (e.get("roundtrip") or {}).get("material_slots"),
                              "iron": bool((e.get("trianglesByPart") or {}).get("strap"))}
    for k in TEXTURE_KEYS:
        files[f"tex:{k}"] = run / "export" / f"{TEX}_{k}.png"
        want[f"tex:{k}"] = ((tex.get("outputs") or {}).get(k) or {}).get("sha256")
    for key, path in files.items():
        item = {"path": rel(path), "abs": str(path)}
        if not path.is_file():
            item["status"] = "missing"
            out["ok"] = False
        else:
            got = sha256_file(path)
            item.update(sha256=got, bytes=path.stat().st_size)
            if not want.get(key):
                item["status"] = "unverified"
                out["ok"] = False  # always built with its reports: no report = not this run's file
            elif got == want[key]:
                item["status"] = "verified"
            else:
                item.update(status="mismatch", expected=want[key], error="sha256 differs from the run's report")
                out["ok"] = False
        out["sources"][key] = item
    layout = reports.get("frame-layout.json") or {}
    out["layout"] = layout_summary(layout)
    if not out["layout"]["ok"]:
        out["ok"] = False
    try:
        look = load_look(look_path)
        out["look"] = {"path": rel(look_path), "sha256": sha256_file(look_path), "params": iron_params(look)}
    except (OSError, ValueError, KeyError) as exc:
        out["look"] = {"path": rel(look_path), "error": str(exc)}
        out["ok"] = False
    return out


def layout_summary(layout: dict) -> dict:
    """The committed frame-layout.json: 20 instances (4 corners + 5 + 5 + 3 + 3 segments = 4 A + 8 B + 4 Mid, the Mid in
    the middle of every side), exact fit, every scale 1 within 1e-6. The C++ S08MapFrame002Layout is checked against
    this file by the automation test Unmatched.S08.BoardArt.MapFrameLayout."""
    inst = layout.get("instances") or []
    counts: dict = {}
    for i in inst:
        counts[i.get("module")] = counts.get(i.get("module"), 0) + 1
    sides = layout.get("sides") or {}
    ok = (len(inst) == 20 and counts == {"Corner": 4, "A": 4, "B": 8, "Mid": 4} and layout.get("exactFit") is True
          and all(abs(float(i.get("scaleX", 0)) - 1.0) < 1e-6 for i in inst)
          and [sides.get(s, {}).get("segments") for s in ("near", "far", "east", "west")] == [5, 5, 3, 3])
    return {"instances": len(inst), "modules": counts, "exactFit": layout.get("exactFit"), "ok": ok,
            "mapHalfUU": layout.get("mapHalfUU"), "frameHalfUU": layout.get("frameHalfUU")}


# ------------------------------------------------------------------------------------------------ UE side
def texture_wanted(key: str) -> dict:
    wanted = K.texture_settings(key, "directx")
    wanted.update({"address_x": u.TextureAddress.TA_WRAP, "address_y": u.TextureAddress.TA_WRAP})
    return wanted


def import_texture(src: dict, asset: str, key: str, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    wanted = texture_wanted(key)
    texture = u.load_asset(asset) if eal.does_asset_exist(asset) else None
    if (texture is not None and not force and eal.get_metadata_tag(texture, SHA_TAG) == src["sha256"]
            and K.settings_match(texture, wanted)):
        return {"action": "unchanged", **K.describe_texture(texture)}
    action = "reimported" if texture is not None else "imported"
    if texture is None or force or eal.get_metadata_tag(texture, SHA_TAG) != src["sha256"]:
        folder, leaf = split(asset)
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
    eal.set_metadata_tag(texture, SHA_TAG, src["sha256"])
    if not eal.save_loaded_asset(texture, False):
        raise RuntimeError(f"could not save {asset}")
    if not K.settings_match(texture, wanted):
        raise RuntimeError(f"{asset}: settings did not stick: {K.describe_texture(texture)}")
    return {"action": action, **K.describe_texture(texture)}


def ensure_iron_instance(master, textures: dict, params: dict) -> dict:
    """MI_MapFrame002_Iron: child of M_EnvProp, the three textures + every look parameter (complete, comparable)."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = ASSETS["mi"]
    mi = u.load_asset(path) if eal.does_asset_exist(path) else None
    action = "updated"
    if mi is None:
        folder, leaf = split(path)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(leaf, folder, u.MaterialInstanceConstant,
                                                                 u.MaterialInstanceConstantFactoryNew())
        action = "created"
    if mi is None:
        raise RuntimeError(f"could not create {path}")

    def rgba(c) -> tuple:
        return tuple(round(float(getattr(c, k)), 5) for k in ("r", "g", "b", "a"))

    def current() -> dict:
        parent = mi.get_editor_property("parent")
        state = {"parent": parent.get_path_name() if parent else None}
        for key, param in look_lib.TEX_PARAMS.items():
            bound = mel.get_material_instance_texture_parameter_value(mi, param)
            state[param] = bound.get_path_name() if bound else None
        for name in params["vector"]:
            state["v:" + name] = rgba(mel.get_material_instance_vector_parameter_value(mi, name))
        for name in params["scalar"]:
            state["s:" + name] = round(float(mel.get_material_instance_scalar_parameter_value(mi, name)), 5)
        return state

    want = {"parent": master.get_path_name()}
    want.update({param: textures[key].get_path_name() for key, param in look_lib.TEX_PARAMS.items()})
    want.update({"v:" + k: tuple(round(float(x), 5) for x in v) for k, v in params["vector"].items()})
    want.update({"s:" + k: round(float(v), 5) for k, v in params["scalar"].items()})
    if action == "updated" and current() == want:
        return {"action": "unchanged", "path": path}
    mel.set_material_instance_parent(mi, master)
    for key, param in look_lib.TEX_PARAMS.items():
        mel.set_material_instance_texture_parameter_value(mi, param, textures[key])
    for name, v in params["vector"].items():
        mel.set_material_instance_vector_parameter_value(mi, name, u.LinearColor(*[float(x) for x in v]))
    for name, v in params["scalar"].items():
        mel.set_material_instance_scalar_parameter_value(mi, name, float(v))
    mel.update_material_instance(mi)
    if not eal.save_loaded_asset(mi, False):
        raise RuntimeError(f"could not save {path}")
    got = current()
    if got != want:
        diff = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
        raise RuntimeError(f"{path}: parameters did not bind (got, want): {diff}")
    return {"action": action, "path": path, "parent": master.get_path_name()}


def slot_names(mesh) -> list:
    return [str(m.get_editor_property("material_slot_name")) for m in mesh.get_editor_property("static_materials")]


def slot_plan(names: list) -> dict:
    """World-free: slot index -> 'wood' | 'iron' by name (M_MapFrame002_Wood / _Iron, UE may append a suffix); without
    a wood name slot 0 is the wood (and a second slot the iron) - reported as 'fallback'."""
    plan_ = {}
    for i, n in enumerate(names):
        if n.startswith(WOOD_SLOT):
            plan_[i] = "wood"
        elif n.startswith(IRON_SLOT):
            plan_[i] = "iron"
    fallback = False
    if "wood" not in plan_.values():
        fallback = True
        plan_ = {0: "wood"} if names else {}
        if len(names) > 1:
            plan_[1] = "iron"
    return {"slots": plan_, "fallback": fallback}


def ensure_mesh_settings(mesh, wood, iron) -> dict:
    """Nanite off, no collision (as ue_import_env_kit.ensure_mesh_settings), slots by name -> wood / iron."""
    sms = K.sm_api()
    changes = []
    nanite = mesh.get_editor_property("nanite_settings")
    if nanite.get_editor_property("enabled"):
        nanite.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", nanite)
        changes.append("nanite off")
    if sms.get_simple_collision_count(mesh) > 0:
        sms.remove_collisions(mesh)
        changes.append("simple collision removed")
    try:
        body = mesh.get_editor_property("body_setup")
        flag = u.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX
        if body is not None and body.get_editor_property("collision_trace_flag") != flag:
            body.set_editor_property("collision_trace_flag", flag)
            changes.append("collision trace simple-as-complex (no complex collision)")
    except Exception as exc:  # noqa: BLE001 - optional hardening
        changes.append(f"collision trace flag not set ({type(exc).__name__}: {exc})")
    names = slot_names(mesh)
    sp = slot_plan(names)
    for index, kind in sp["slots"].items():
        target = wood if kind == "wood" else iron
        current = mesh.get_material(index)
        if current is None or current.get_path_name() != target.get_path_name():
            mesh.set_material(index, target)
            changes.append(f"slot {index} {names[index]} -> {target.get_name()}")
    return {"changes": changes, "slotNames": names, "slotPlan": {str(k): v for k, v in sp["slots"].items()},
            "slotFallback": sp["fallback"]}


def compare(measured: dict, expected: dict) -> dict:
    """World-free: bounds against the Blender build (+-0.5 uu), triangle drift (<= 1 %)."""
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


def measure(mesh, expected: dict) -> dict:
    sms = K.sm_api()
    box = mesh.get_bounding_box()
    mn, mx = box.min, box.max
    out = {"boundsMin": [round(mn.x, 3), round(mn.y, 3), round(mn.z, 3)],
           "boundsMax": [round(mx.x, 3), round(mx.y, 3), round(mx.z, 3)],
           "nanite": bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")),
           "simpleCollision": int(sms.get_simple_collision_count(mesh)),
           "slots": [mesh.get_material(i).get_path_name() if mesh.get_material(i) else None
                     for i in range(len(mesh.get_editor_property("static_materials")))]}
    try:
        out["trianglesLod0"] = int(mesh.get_num_triangles(0))
    except Exception:  # noqa: BLE001 - not exposed in every engine version
        out["trianglesLod0"] = None
    out.update(compare(out, expected))
    return out


def ensure_wood_material(force: bool) -> dict:
    import ue_import_map_surface as MS  # tools/art/map_surface (on sys.path)
    return MS.build_frame_wood(force)


def run_import(p: dict, force: bool) -> tuple[dict, bool]:
    eal = u.EditorAssetLibrary
    result: dict = {}
    before = K.folder_listing(FOLDER) if eal.does_directory_exist(FOLDER) else []
    ok = True
    try:
        result["woodMaterial"] = ensure_wood_material(False)
        result["envMaster"] = K.build_env_master(False)
        wood = u.load_asset(WOOD_MATERIAL)
        master = u.load_asset(ENV_MASTER)
        if wood is None or master is None:
            raise RuntimeError(f"materials missing: wood={wood is not None} M_EnvProp={master is not None}")
        textures = {}
        result["textures"] = {}
        for key in TEXTURE_KEYS:
            result["textures"][key] = import_texture(p["sources"][f"tex:{key}"], ASSETS[f"tex:{key}"], key, force)
            textures[key] = u.load_asset(ASSETS[f"tex:{key}"])
        result["materialInstance"] = ensure_iron_instance(master, textures, p["look"]["params"])
        iron = u.load_asset(ASSETS["mi"])
        result["meshes"] = {}
        problems = []
        for m in MODULES:
            src = p["sources"][f"fbx:{m}"]
            asset = ASSETS[f"mesh:{m}"]
            mesh = u.load_asset(asset) if eal.does_asset_exist(asset) else None
            if (mesh is not None and not force and eal.get_metadata_tag(mesh, SHA_TAG) == src["sha256"]
                    and eal.get_metadata_tag(mesh, SCALE_TAG) == "1"):
                entry = {"action": "unchanged"}
            else:
                entry = dict(K.import_mesh(src, asset, 1.0), action="reimported" if mesh is not None else "imported")
                mesh = u.load_asset(asset)
                if mesh is None or not isinstance(mesh, u.StaticMesh):
                    raise RuntimeError(f"{asset} is not a static mesh after the import")
                eal.set_metadata_tag(mesh, SHA_TAG, src["sha256"])
                eal.set_metadata_tag(mesh, SCALE_TAG, "1")
            settings = ensure_mesh_settings(mesh, wood, iron)
            entry["settings"] = settings
            if settings["changes"] or entry["action"] != "unchanged":
                if not eal.save_loaded_asset(mesh, False):
                    raise RuntimeError(f"could not save {asset}")
            meas = entry["measure"] = measure(mesh, p["expected"][m])
            if meas["nanite"]:
                problems.append(f"{m}: nanite still on")
            if meas["simpleCollision"]:
                problems.append(f"{m}: simple collision left")
            if settings["slotFallback"]:
                problems.append(f"{m}: no slot named {WOOD_SLOT} (slots {settings['slotNames']}) - index fallback used")
            if p["expected"][m]["iron"] and "iron" not in settings["slotPlan"].values():
                problems.append(f"{m}: iron faces but no iron slot")
            if not (meas.get("bounds") or {}).get("ok"):
                problems.append(f"{m}: bounds differ from the Blender build: {meas.get('bounds')}")
            if (meas.get("triangles") or {}).get("ok") is False:
                problems.append(f"{m}: triangles differ by > {TRIS_TOL:.0%}: {meas.get('triangles')}")
            result["meshes"][m] = entry
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
    ap.add_argument("--look", default=None, help=f"iron look file (default <run>/reports/{LOOK_DEFAULT.name})")
    ap.add_argument("--report", default=None)
    ap.add_argument("--check", action="store_true", help="verify the sources + measure the iron look only (no UE)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    started = time.time()
    run = Path(a.run).resolve()
    look_path = Path(a.look).resolve() if a.look else run / "reports" / LOOK_DEFAULT.name
    p = plan(run, look_path)
    out = {"schema": "unmatched.map-frame-002-ue-import/1", "tool": "tools/art/env_kit/ue_import_map_frame.py",
           "mode": "check" if (a.check or u is None) else "import", "folder": FOLDER, "woodMaterial": WOOD_MATERIAL,
           "ironMaster": ENV_MASTER, "importScale": 1.0, "normalConvention": "directx", "plan": p}
    ok = p["ok"]
    if out["mode"] == "check" and "params" in p.get("look", {}):
        try:
            look = load_look(look_path)
            out["separation"] = {"look": iron_separation(look, run), "neutral": iron_separation(None, run)}
            ok = ok and out["separation"]["look"]["ok"]
        except ImportError as exc:  # numpy / PIL missing: report, do not fail the source check
            out["separation"] = {"skipped": str(exc)}
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
        path = Path(u.Paths.project_saved_dir()) / "EnvMaps" / "map-frame-import-report.json"
    else:
        path = None
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        out["reportPath"] = str(path)
    counts: dict = {}
    for item in p["sources"].values():
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print("MAPFRAME-IMPORT-REPORT " + json.dumps(out, ensure_ascii=False, default=str))
    print(f"MAPFRAME-IMPORT-RESULT {'ok' if ok else 'failed'} mode={out['mode']} sources={json.dumps(counts, sort_keys=True)}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        raise RuntimeError("MAPFRAME import failed - see MAPFRAME-IMPORT-REPORT")
