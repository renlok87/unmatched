"""ENV-MAPS P7 (ENV-U15) concept paste, track A: import the concept-paste textures and meshes into UE (out of git).

Sources (checked by sha256 before anything is imported; a mismatching / missing file is never imported):
  textures  <derived>/<map>/T_<Name>_Concept<Key>.png   tools/art/concept_paste/cp_bake.py, OUT of git (ENV-U3 / U7:
            painted over a render of the original map); manifest.<map>.json (git) holds their sha256
  meshes    art/pipeline-candidates/ASSET-ENV-CONCEPT-PASTE-001/20261001-p7/export/*.fbx (git, UM_FBX_v1, headless
            Blender: cp_proxies.py / blender_cp_assets.py); reports/build-report.json holds their sha256
Targets (the asset names of S08ArtBoardProfiles.json conceptPaste and of EnvLayouts/<map>.concept.layout.json):
  /Game/EnvMaps/<Name>/ConceptPaste/T_<Name>_ConceptPlateA   plate A (centre, x2 detail) RGBA, sRGB, BC7, mips, clamp
  /Game/EnvMaps/<Name>/ConceptPaste/T_<Name>_ConceptPlateB   plate B (outskirts) RGBA (A = matte x cut), sRGB, BC7, clamp
  /Game/EnvMaps/<Name>/ConceptPaste/T_<Name>_ConceptSea      sea layer RGB, sRGB, BC7, clamp
  /Game/EnvMaps/<Name>/ConceptPaste/T_<Name>_ConceptWater    (Sarpedon) flow masks R waterfall / G bay surf / B sea,
                                                             linear, TC_Masks, clamp
  /Game/EnvMaps/<Name>/ConceptPaste/SM_<Name>_ConceptSheet   the relief depth sheet (board space, pivot = map centre),
                                                             Nanite off, no collision; slot -> M_ConceptPaste when it
                                                             exists (tools/art/concept_paste/ue_concept_material.py)
  /Game/EnvKit/ConceptPaste/SM_EnvCP_LanternHead             the hanging lantern (slot -> /Game/EnvKit/Sarpedon/
                                                             MI_Env_LanternPost: same UVs as the post)
  /Game/EnvKit/ConceptPaste/SM_EnvCP_BannerCloth             the hanging banner cloth (slot -> MI_Env_Banner, two-sided)
/Game/EnvMaps and /Game/EnvKit are cooked by DirectoriesToAlwaysCook (never under /Game/EnvMaps/Data). The material and
the per-map MI are track B's (ue_concept_material.py); the board actor binds the textures from the profile block.

Idempotent: an asset whose metadata tag EnvMapsConceptSha256 equals the source sha256 and whose settings match is left
alone (--force re-imports). A JSON report is printed ('CONCEPT-PASTE-IMPORT-REPORT {...}', 'CONCEPT-PASTE-IMPORT-RESULT
ok|failed') and written to <project>/Saved/EnvMaps/concept-paste-import-report.json (or --report).

Run (the editor must be CLOSED; never inside a GPU-measurement window; UnrealEditor-Cmd holds the project):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/concept_paste/ue_import_concept_paste.py --maps sarpedon,marmoreal"
      -unattended -nosplash -nullrhi
Pre-check without UE (plain Python: presence + sha256 of every source, the kit MIs the details need are listed):
  python -B tools/art/concept_paste/ue_import_concept_paste.py --check
Options: --maps a,b  --derived <dir with <map>/T_*.png>  --report <json>  --force  --no-details
Derived directory order: --derived, env UM_CONCEPT_PASTE_DERIVED, <repo>/scraped-data/derived/concept-paste, the main
checkout's scraped-data/derived/concept-paste.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only; --check runs in plain Python
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None
if u is not None and not hasattr(u, "EditorAssetLibrary"):  # the repo's unreal/ folder as a namespace package
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAIN_CHECKOUT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
MAPS = {"marmoreal": "Marmoreal", "sarpedon": "Sarpedon"}
RUN = REPO / "art" / "pipeline-candidates" / "ASSET-ENV-CONCEPT-PASTE-001" / "20261001-p7"
BUILD_REPORT = RUN / "reports" / "build-report.json"
ENVMAPS_ROOT = "/Game/EnvMaps"
KIT_ROOT = "/Game/EnvKit"
FOLDER = ENVMAPS_ROOT + "/{name}/ConceptPaste"
DETAIL_FOLDER = KIT_ROOT + "/ConceptPaste"
MATERIAL = ENVMAPS_ROOT + "/ConceptPaste/M_ConceptPaste"
SHA_TAG = "EnvMapsConceptSha256"
DETAILS = {  # mesh -> the MI its slots take (same UVs as the source prop)
    "SM_EnvCP_LanternHead": DETAIL_FOLDER + "/MI_EnvCP_LanternHead",
    "SM_EnvCP_BannerCloth": KIT_ROOT + "/Sarpedon/MI_Env_Banner",
}
# P7 tune: the concept's lanterns are lit panes (C0 crops: the kit glass at x7.6 reads as a dark frame with a spark);
# a child of the kit MI (same M_EnvProp emissive window of tools/art/env_kit/env_prop_look.py) with a wider window and a
# stronger glass glow. name -> (parent, scalar overrides, vector overrides)
DETAIL_MIS = {
    DETAIL_FOLDER + "/MI_EnvCP_LanternHead": (
        KIT_ROOT + "/Sarpedon/MI_Env_LanternPost",
        {"EmissiveIntensity": 8.0},
        {"EmissiveWindow": (42.0, 16.0, 0.22, 0.5, 0.0), "EmissiveColor": (1.0, 0.42, 0.1, 1.0)},
    ),
}
DETAIL_MI_TAG = "EnvMapsConceptDetailMi"
DETAIL_MI_VERSION = "3"
LINEAR_KEYS = ("Water",)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).as_posix()


def derived_root(arg: str | None) -> Path:
    for cand in (arg, os.environ.get("UM_CONCEPT_PASTE_DERIVED")):
        if cand:
            return Path(cand)
    local = REPO / "scraped-data" / "derived" / "concept-paste"
    return local if local.is_dir() else MAIN_CHECKOUT / "scraped-data" / "derived" / "concept-paste"


def load_manifest(key: str) -> dict:
    path = HERE / f"manifest.{key}.json"
    m = json.loads(path.read_text(encoding="utf-8"))
    if m.get("schema") != "unmatched.concept-paste.derived/1" or m.get("map") != key:
        raise RuntimeError(f"{path}: not the concept-paste manifest of {key}")
    return m


def texture_asset(key: str, file_name: str) -> str:
    return f"{FOLDER.format(name=MAPS[key])}/{Path(file_name).stem}"


def mesh_asset(name: str) -> str:
    if name in DETAILS:
        return f"{DETAIL_FOLDER}/{name}"
    for key, n in MAPS.items():
        if name.startswith(f"SM_{n}_Concept"):
            return f"{FOLDER.format(name=n)}/{name}"
    raise KeyError(name)


def plan(keys: list[str], root: Path, details: bool = True) -> dict:
    """sha256 of every source against the manifests / the build report (plain Python)."""
    out = {"maps": {}, "meshes": {}, "ok": True}
    rep = json.loads(BUILD_REPORT.read_text(encoding="utf-8")) if BUILD_REPORT.is_file() else None
    exports = {e["name"]: e for e in (rep or {}).get("exports", [])}
    if rep is None:
        out["ok"] = False
        out["errors"] = [f"{rel(BUILD_REPORT)} missing (cp_proxies.py build)"]
    for key in keys:
        entry = {"name": MAPS[key], "textures": {}, "ok": True}
        try:
            man = load_manifest(key)
        except (OSError, RuntimeError) as exc:
            entry.update(ok=False, error=str(exc))
            out["maps"][key] = entry
            out["ok"] = False
            continue
        entry["materialContract"] = man.get("materialContract")
        for tkey, o in man["outputs"].items():
            src = root / key / o["file"]
            item = {"key": tkey, "source": src.as_posix(), "sha256Manifest": o["sha256"], "size": o["size"],
                    "channels": o["channels"], "asset": texture_asset(key, o["file"]),
                    "linear": tkey in LINEAR_KEYS}
            if not src.is_file():
                item.update(verified=False, error="source missing (run cp_bake.py bake)")
            else:
                got = sha256_file(src)
                item.update(sha256=got, verified=got == o["sha256"])
                if got != o["sha256"]:
                    item["error"] = "sha256 differs from the manifest"
            entry["ok"] = entry["ok"] and item["verified"]
            entry["textures"][tkey] = item
        sheet = f"SM_{MAPS[key]}_ConceptSheet"
        entry["sheet"] = sheet
        out["maps"][key] = entry
        out["ok"] = out["ok"] and entry["ok"]
        if sheet not in exports:
            out["ok"] = False
            entry["ok"] = False
            entry["error"] = f"{sheet} not in the build report"
        else:
            out["meshes"][sheet] = None
    names = list(out["meshes"]) + (list(DETAILS) if details else [])
    for name in names:
        e = exports.get(name)
        item = {"asset": mesh_asset(name), "mi": DETAILS.get(name, MATERIAL)}
        if e is None:
            item.update(verified=False, error="not in the build report")
        else:
            src = REPO / e["fbx"]
            item.update(source=src.as_posix(), sha256Report=e["sha256"], triangles=e["triangles"],
                        boundsUU=e["boundsUeLocalUU"], checks=all(e["checks"].values()))
            if not src.is_file():
                item.update(verified=False, error="FBX missing")
            else:
                got = sha256_file(src)
                item.update(sha256=got, verified=got == e["sha256"] and item["checks"])
                if not item["verified"]:
                    item["error"] = "sha256 differs from the build report" if got != e["sha256"] else "build checks failed"
        out["meshes"][name] = item
        out["ok"] = out["ok"] and item["verified"]
    return out


# ---------------------------------------------------------------------------------------------------- UE side
def texture_settings(linear: bool) -> dict:
    tcs, mips, grp = u.TextureCompressionSettings, u.TextureMipGenSettings, u.TextureGroup
    wanted = ({"compression_settings": tcs.TC_MASKS, "srgb": False} if linear
              else {"compression_settings": tcs.TC_BC7, "srgb": True})
    wanted.update({"mip_gen_settings": mips.TMGS_FROM_TEXTURE_GROUP, "lod_group": grp.TEXTUREGROUP_WORLD,
                   "never_stream": False, "address_x": u.TextureAddress.TA_CLAMP,
                   "address_y": u.TextureAddress.TA_CLAMP})
    return wanted


def settings_match(obj, wanted: dict) -> bool:
    return all(obj.get_editor_property(k) == v for k, v in wanted.items())


def describe_texture(t) -> dict:
    return {"srgb": bool(t.get_editor_property("srgb")), "compression": str(t.get_editor_property("compression_settings")),
            "address": [str(t.get_editor_property("address_x")), str(t.get_editor_property("address_y"))],
            "sizeX": int(t.blueprint_get_size_x()), "sizeY": int(t.blueprint_get_size_y())}


def import_texture(item: dict, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    path = item["asset"]
    wanted = texture_settings(item["linear"])
    tex = u.load_asset(path) if eal.does_asset_exist(path) else None
    if tex is not None and not force and eal.get_metadata_tag(tex, SHA_TAG) == item["sha256"] and settings_match(tex, wanted):
        return {"action": "unchanged", **describe_texture(tex)}
    action = "reimported" if tex is not None else "imported"
    folder, leaf = path.rsplit("/", 1)
    task = u.AssetImportTask()
    task.filename = item["source"]
    task.destination_path = folder
    task.destination_name = leaf
    task.automated = True
    task.replace_existing = True
    task.save = False
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = u.load_asset(path)
    if tex is None or not isinstance(tex, u.Texture2D):
        raise RuntimeError(f"import of {item['source']} did not produce the texture {path}")
    for k, v in wanted.items():  # compression first (dict order), then sRGB, mips, group, address
        tex.set_editor_property(k, v)
    eal.set_metadata_tag(tex, SHA_TAG, item["sha256"])
    if not eal.save_loaded_asset(tex, False):
        raise RuntimeError(f"could not save {path}")
    if not settings_match(tex, wanted):
        raise RuntimeError(f"{path}: settings did not stick: {describe_texture(tex)}")
    got = describe_texture(tex)
    if [got["sizeX"], got["sizeY"]] != list(item["size"]):
        raise RuntimeError(f"{path}: size {got['sizeX']}x{got['sizeY']} != {item['size']} (LOD group clamp?)")
    return {"action": action, **got}


def kit():
    sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
    import ue_import_env_kit as K  # noqa: E402  (import_mesh / sm_api / setp: the kit's FBX route)
    return K


def import_mesh(name: str, item: dict, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    K = kit()
    path = item["asset"]
    mesh = u.load_asset(path) if eal.does_asset_exist(path) else None
    action = "unchanged"
    res = {}
    if mesh is None or force or eal.get_metadata_tag(mesh, SHA_TAG) != item["sha256"]:
        action = "reimported" if mesh is not None else "imported"
        res = K.import_mesh({"abs": item["source"], "path": rel(Path(item["source"]))}, path, 1.0)
        mesh = u.load_asset(path)
        if mesh is None or not isinstance(mesh, u.StaticMesh):
            raise RuntimeError(f"import of {item['source']} did not produce the static mesh {path}")
        eal.set_metadata_tag(mesh, SHA_TAG, item["sha256"])
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
            changes.append("collision trace simple-as-complex (no collision)")
    except Exception as exc:  # noqa: BLE001 - optional hardening
        changes.append(f"collision trace flag not set ({type(exc).__name__}: {exc})")
    mi_path = item["mi"]
    mi = u.load_asset(mi_path) if eal.does_asset_exist(mi_path) else None
    slots = len(mesh.get_editor_property("static_materials"))
    if mi is None:
        changes.append(f"slots left as imported: {mi_path} missing" +
                       (" (track B: ue_concept_material.py)" if mi_path == MATERIAL else " (run ue_import_env_kit.py)"))
    else:
        for i in range(slots):
            cur = mesh.get_material(i)
            if cur is None or cur.get_path_name() != mi.get_path_name():
                mesh.set_material(i, mi)
                changes.append(f"slot {i} -> {mi.get_name()}")
    if changes or action != "unchanged":
        if not eal.save_loaded_asset(mesh, False):
            raise RuntimeError(f"could not save {path}")
    box = mesh.get_bounding_box()
    got = [round(box.min.x, 2), round(box.min.y, 2), round(box.min.z, 2), round(box.max.x, 2), round(box.max.y, 2),
           round(box.max.z, 2)]
    want = item["boundsUU"]["min"] + item["boundsUU"]["max"]
    err = max(abs(a - b) for a, b in zip(got, want))
    if err > 0.5:
        raise RuntimeError(f"{path}: bounds {got} differ from the build report {want} by {err:.2f} uu (import scale?)")
    return {"action": action, **res, "changes": changes, "slots": slots, "boundsUU": got, "boundsErrUU": round(err, 3),
            "mi": mi_path if mi is not None else None}


def ensure_detail_mis(force: bool) -> dict:
    """MI_EnvCP_* children of the kit MIs (DETAIL_MIS); idempotent via a version tag."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    out = {}
    for path, (parent_path, scalars, vectors) in DETAIL_MIS.items():
        parent = u.load_asset(parent_path) if eal.does_asset_exist(parent_path) else None
        if parent is None:
            out[path] = {"action": "skipped", "error": f"{parent_path} missing (run ue_import_env_kit.py)"}
            continue
        mi = u.load_asset(path) if eal.does_asset_exist(path) else None
        if mi is not None and not force and eal.get_metadata_tag(mi, DETAIL_MI_TAG) == DETAIL_MI_VERSION:
            out[path] = {"action": "unchanged"}
            continue
        action = "updated" if mi is not None else "created"
        if mi is None:
            folder, name = path.rsplit("/", 1)
            mi = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.MaterialInstanceConstant,
                                                                     u.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, parent)
        for k, v in scalars.items():
            mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
        for k, v in vectors.items():
            mel.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(*[float(x) for x in v[:4]]))
        eal.set_metadata_tag(mi, DETAIL_MI_TAG, DETAIL_MI_VERSION)
        if not eal.save_loaded_asset(mi, False):
            raise RuntimeError(f"could not save {path}")
        out[path] = {"action": action, "parent": parent_path, "scalars": scalars,
                     "vectors": {k: list(v[:4]) for k, v in vectors.items()}}
    return out


def run_import(p: dict, force: bool) -> bool:
    ok = True
    try:
        p["detailMis"] = ensure_detail_mis(force)
    except Exception as exc:
        p["detailMis"] = {"action": "failed", "error": str(exc)}
        ok = False
    for key, entry in p["maps"].items():
        entry["ue"] = {}
        if not entry["ok"]:
            entry["ue"]["skipped"] = "source verification failed; nothing imported for this map"
            ok = False
            continue
        for tkey, item in entry["textures"].items():
            try:
                entry["ue"][tkey] = import_texture(item, force)
            except Exception as exc:  # report and continue
                entry["ue"][tkey] = {"action": "failed", "error": str(exc)}
                ok = False
    for name, item in p["meshes"].items():
        if not item.get("verified"):
            item["ue"] = {"action": "skipped", "error": item.get("error")}
            ok = False
            continue
        try:
            item["ue"] = import_mesh(name, item, force)
        except Exception as exc:
            item["ue"] = {"action": "failed", "error": str(exc)}
            ok = False
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--maps", default="sarpedon,marmoreal")
    ap.add_argument("--derived", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--check", action="store_true", help="verify the sources only (no UE import)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-details", action="store_true", help="skip the lantern head / banner cloth meshes")
    a = ap.parse_args(argv)
    keys = [k.strip() for k in a.maps.split(",") if k.strip()]
    unknown = [k for k in keys if k not in MAPS]
    if unknown:
        print(f"unknown map key(s) {unknown}; known: {sorted(MAPS)}")
        return 2
    t0 = time.time()
    root = derived_root(a.derived)
    p = plan(keys, root, not a.no_details)
    report = {"schema": "unmatched.concept-paste-ue-import/1", "tool": "tools/art/concept_paste/ue_import_concept_paste.py",
              "mode": "check" if (a.check or u is None) else "import", "derivedRoot": root.as_posix(),
              "buildReport": rel(BUILD_REPORT), "material": MATERIAL, **p}
    ok = p["ok"]
    if report["mode"] == "import":
        ok = run_import(p, a.force) and ok
        report["engine"] = str(u.SystemLibrary.get_engine_version())
    report["ok"] = ok
    report["seconds"] = round(time.time() - t0, 1)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if a.report:
        rp = Path(a.report)
    elif u is not None:
        rp = Path(u.Paths.project_saved_dir()) / "EnvMaps" / "concept-paste-import-report.json"
    else:
        rp = None
    if rp is not None:
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(text + "\n", encoding="utf-8")
        report["reportPath"] = rp.as_posix()
    print("CONCEPT-PASTE-IMPORT-REPORT " + json.dumps(report, ensure_ascii=False))
    print(f"CONCEPT-PASTE-IMPORT-RESULT {'ok' if ok else 'failed'} mode={report['mode']} maps={','.join(keys)}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        raise RuntimeError("concept-paste import failed - see CONCEPT-PASTE-IMPORT-REPORT")
