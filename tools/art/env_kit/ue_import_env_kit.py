"""ENV-MAPS track C: import the environment kit ASSET-ENV-KIT-001 into UE (/Game/EnvKit/<Map>/, out of git).

Sources: the headless-Blender exports of track A (tools/art/env_kit/run_env_kit.py) under
art/pipeline-candidates/ASSET-ENV-KIT-001/20260930-tripo-h31/export/:
  SM_Env_<Name>.fbx               UM_FBX_v1: centimetres = uu (UnitScaleFactor 1.0), front = +X, pivot base centre,
                                  the target size already applied (build-report "target")
  T_Env_<Name>_{BC,N,ORM}.png     BC sRGB; N DirectX (green already flipped from glTF); ORM linear (R = AO 1, G = rough,
                                  B = metal)
Targets (the fixed UE naming contract of S08EnvLayout.h; the layouts in Config/ArtBoards/EnvLayouts reference the meshes):
  /Game/EnvKit/<Map>/SM_Env_<Name>          legacy FbxFactory (explicit FbxImportUI, as tools/tripo-pipeline
                                            UE_PY_IMPORT_FBX): import_uniform_scale 1.0, normals imported, no materials
                                            / textures from the FBX, no auto collision, Nanite off; afterwards simple
                                            collision removed + CTF_UseSimpleAsComplex (= no collision at all: decor);
                                            every material slot -> MI_Env_<Name>
  /Game/EnvKit/<Map>/T_Env_<Name>_BC        sRGB, TC_Default, TEXTUREGROUP_World
  /Game/EnvKit/<Map>/T_Env_<Name>_N         linear, TC_Normalmap, flip_green false (DirectX), TEXTUREGROUP_WorldNormalMap
  /Game/EnvKit/<Map>/T_Env_<Name>_ORM       linear, TC_Masks, TEXTUREGROUP_World
  /Game/EnvKit/<Map>/MI_Env_<Name>          child of /Game/UM/Materials/M_UM_Figure (the decor route of the table base
                                            ASSET-TABLE-BASE-001 and the W4-B barrel): BaseColorTexture / NormalTexture /
                                            ORMTexture bound, TeamColor white, TeamMaskTexture = T_UM_Mask_Black (no team
                                            colour on the environment); base property override TwoSided on for
                                            TWO_SIDED (Cypress Rope Tree Cherry Urn: inward-wound faces), off otherwise
  Marmoreal: ArcadeBay Portal Cherry PlinthBall LanternPlinth Urn Cypress            (run 20260930-tripo-h31)
             Balustrade HedgeBed                                                   (run 20261001-tripo-h31-p5)
             BackWall_BayDoor BackWall_BayWindows BackWall_Centre                  (ASSET-ENV-M-BACKWALL-001)
  Sarpedon:  FortRuin Tree Hull Cannon Campfire Palisade Rope                      (run 20260930-tripo-h31)
             Barrel CrateStack LanternPost Banner RockOutcrop                       (run 20261001-tripo-h31-p5)
  Every prop is read from its own run (RUN_OF: export/ + reports/build-report.json); --run forces one run for all.
  Shared material sets (MATERIAL_OF): the three back-wall modules share one 2K atlas and one MI -
  T_Env_BackWall_{BC,N,ORM,E} + MI_Env_BackWall (child of M_EnvProp: its EmissiveWindow lights only the window /
  door glow texels; look entry 'BackWall' of the P5 run's env-prop-look.json). T_Env_BackWall_E (linear, TC_Masks)
  is the same glow mask as a texture, imported for a future dedicated master and not bound by M_EnvProp. The back-wall
  build report (schema unmatched.env-m-backwall.build-report/1, Blender lane K) is adapted to env-kit entries
  (exports[] -> fbx sha256, the shared textures, height target = the module height, readback = boundsUeLocalUU); its
  pivot is the back face, not the base centre (bounds x -16 .. +14.8 / +9.3: reported, not a problem).
  /Game/EnvKit/Shared/M_EnvProp             (ENV-MAPS P4 track B) the kit's 'look' master: BC/N/ORM as M_UM_Figure at
                                            its neutral defaults + an HSV-window recolour of the BC and an emissive
                                            window (tools/art/env_kit/env_prop_look.py: HLSL, numpy mirror, --check).
                                            The props of the look file (<run>/scripts/env-prop-look.json: Cherry,
                                            Cypress, Tree, LanternPlinth, Campfire, Portal) get MI_Env_<Name> parented to
                                            M_EnvProp with the look's parameters; every other prop keeps M_UM_Figure.
                                            The committed textures are not changed. --no-look keeps every MI on
                                            M_UM_Figure (the P1b-P3 state).
DefaultGame.ini always cooks /Game/EnvKit (the board actor loads the meshes at runtime by the layout paths).

Checks before any import: every source file exists and its sha256 equals the build report of track A
(<run>/reports/build-report.json, schema unmatched.env-kit.build-report/1: assets[<ID>].fbx / .textures.<K>.sha256);
a mismatching file is never imported (that prop is skipped, the run fails). Without a build report (or an asset missing
from it) the sources are 'unverified': imported unless --require-verified. After the import the mesh bounds are
measured against the target of the report (height / length = max(X, Y) / diameter = max(X, Y); 1 % = ok, <= 10 % =
warning, more = failure; a x100 / x0.01 ratio names the import-scale fix) and against the Blender readback.

Idempotent: a texture / mesh whose metadata tag EnvKitSourceSha256 equals the source sha256 (and EnvKitImportScale the
scale) and whose settings already match is left alone; the MI and the mesh settings (Nanite, collision, slots) are only
written when they differ. Nothing outside the planned 5 assets per prop is deleted or overwritten (foreign assets in a
kit folder are reported). A JSON report is printed ('ENVKIT-IMPORT-REPORT {...}', 'ENVKIT-IMPORT-RESULT ok|failed') and
written to <project>/Saved/EnvKit/ue-import-report.json (or --report).

Run (the editor must be CLOSED - UnrealEditor-Cmd holds the project; never inside a GPU-measurement window):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/env_kit/ue_import_env_kit.py" -unattended -nosplash -nullrhi
Pre-check without UE (plain Python: presence + sha256 against the build report, no import):
  python -B tools/art/env_kit/ue_import_env_kit.py --check
Options: --maps marmoreal,sarpedon  --names Cherry,Hull  --run <run dir>  --report <json>  --force (re-import all)
         --import-scale 1.0  --normal auto|directx|opengl  --require-verified  --look <json> | --no-look
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
if str(HERE) not in sys.path:  # env_prop_look (no numpy needed for the UE side)
    sys.path.insert(0, str(HERE))
import env_prop_look as look_lib  # noqa: E402

RUN_DEFAULT = REPO / "art" / "pipeline-candidates" / "ASSET-ENV-KIT-001" / "20260930-tripo-h31"
RUN_P5 = REPO / "art" / "pipeline-candidates" / "ASSET-ENV-KIT-001" / "20261001-tripo-h31-p5"
RUN_BACKWALL = REPO / "art" / "pipeline-candidates" / "ASSET-ENV-M-BACKWALL-001" / "20261001-backwall-v1"
BACKWALL_SCHEMA = "unmatched.env-m-backwall.build-report/1"
ROOT = "/Game/EnvKit"
MASTER = "/Game/UM/Materials/M_UM_Figure"
MASK_NONE = "/Game/UM/Materials/Textures/T_UM_Mask_Black"
SHA_TAG = "EnvKitSourceSha256"
SCALE_TAG = "EnvKitImportScale"
REPORT_SCHEMA = "unmatched.env-kit.build-report/1"
HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
TEXTURE_KEYS = ("BC", "N", "ORM")
# M_UM_Figure parameters (tools/tripo-pipeline/um_masters.py figure_graph)
PARAMS = {"BC": "BaseColorTexture", "N": "NormalTexture", "ORM": "ORMTexture"}
PARAM_MASK = "TeamMaskTexture"
PARAM_TEAM = "TeamColor"
# Name -> (map folder, kit id, default target (dimension, uu)): the task's proposal; the build report's "target" wins.
KIT = {
    "ArcadeBay": ("Marmoreal", "ENV-M-ARCADE-BAY", ("height", 130.0)),
    "Portal": ("Marmoreal", "ENV-M-PORTAL", ("height", 150.0)),
    "Cherry": ("Marmoreal", "ENV-M-CHERRY", ("height", 180.0)),
    "PlinthBall": ("Marmoreal", "ENV-M-PLINTH-BALL", ("height", 60.0)),
    "LanternPlinth": ("Marmoreal", "ENV-M-LANTERN-PLINTH", ("height", 70.0)),
    "Urn": ("Marmoreal", "ENV-M-URN", ("height", 35.0)),
    "Cypress": ("Marmoreal", "ENV-M-CYPRESS", ("height", 110.0)),
    "FortRuin": ("Sarpedon", "ENV-S-FORT-RUIN", ("height", 110.0)),
    "Tree": ("Sarpedon", "ENV-S-TREE", ("height", 190.0)),
    "Hull": ("Sarpedon", "ENV-S-HULL", ("length", 300.0)),
    "Cannon": ("Sarpedon", "ENV-S-CANNON", ("length", 45.0)),
    "Campfire": ("Sarpedon", "ENV-S-CAMPFIRE", ("diameter", 40.0)),
    "Palisade": ("Sarpedon", "ENV-S-PALISADE", ("height", 70.0)),
    "Rope": ("Sarpedon", "ENV-S-ROPE", ("diameter", 22.0)),
    # P5 (20261001-tripo-h31-p5; ENV-M-CHERRY-V2 is not processed: ENV-U13)
    "Barrel": ("Sarpedon", "ENV-S-BARREL", ("height", 28.0)),
    "CrateStack": ("Sarpedon", "ENV-S-CRATE-STACK", ("height", 45.0)),
    "LanternPost": ("Sarpedon", "ENV-S-LANTERN-POST", ("height", 95.0)),
    "Banner": ("Sarpedon", "ENV-S-BANNER", ("height", 120.0)),
    "RockOutcrop": ("Sarpedon", "ENV-S-ROCK-OUTCROP", ("height", 70.0)),
    "Balustrade": ("Marmoreal", "ENV-M-BALUSTRADE", ("length", 150.0)),
    "HedgeBed": ("Marmoreal", "ENV-M-HEDGE-BED", ("length", 150.0)),
    # Blender lane K (ASSET-ENV-M-BACKWALL-001): three modules on one atlas / one MI (MATERIAL_OF)
    "BackWall_BayDoor": ("Marmoreal", "ENV-M-BACKWALL/Bay_Door", ("height", 235.0)),
    "BackWall_BayWindows": ("Marmoreal", "ENV-M-BACKWALL/Bay_Windows", ("height", 235.0)),
    "BackWall_Centre": ("Marmoreal", "ENV-M-BACKWALL/Centre", ("height", 255.0)),
}
P5_NAMES = ("Barrel", "CrateStack", "LanternPost", "Banner", "RockOutcrop", "Balustrade", "HedgeBed")
BACKWALL_NAMES = ("BackWall_BayDoor", "BackWall_BayWindows", "BackWall_Centre")
# the run (export/ + reports/build-report.json) every prop comes from; the others come from RUN_DEFAULT
RUN_OF = {**{n: RUN_P5 for n in P5_NAMES}, **{n: RUN_BACKWALL for n in BACKWALL_NAMES}}
# props sharing one texture set + MI (T_Env_<set>_*, MI_Env_<set>); the others use their own name
MATERIAL_OF = {n: "BackWall" for n in BACKWALL_NAMES}
TEXTURE_KEYS_OF = {"BackWall": ("BC", "N", "ORM", "E")}
MAPS = {"marmoreal": "Marmoreal", "sarpedon": "Sarpedon"}
SIZE_OK, SIZE_WARN = 0.01, 0.10  # relative error of the target dimension
# Meshes with inward-wound faces (track A build report: Cypress 42.9 %, Rope 13.9 %, Tree 12.8 %, Cherry 10.2 %,
# Urn 4.9 %). M_UM_Figure is one-sided, so their MI overrides TwoSided (P1b review quick fix; the clean fix is a
# rebuild with static_prop_candidate.fix_winding, after which this set can be emptied).
# Keyed by the material set (= the prop name unless MATERIAL_OF says otherwise). P5 (20261001-tripo-h31-p5 build
# report, ray escape: no prop above 0.1 % inward area): Banner - a cloth card, two-sided by design, plus 2 open slits
# (12.2 uu2, rim 79.6 uu along the cloth edge); Balustrade - 5 open holes totalling 91.5 uu2 (largest 58.2 uu2,
# 3.8 uu wide, z 29) that a one-sided material would show as see-through gaps.
TWO_SIDED = {"Cypress", "Rope", "Tree", "Cherry", "Urn", "Banner", "Balustrade"}
# M_EnvProp (P4 track B): the look master; graph rebuilt when ENV_GRAPH_VERSION changes (or --force)
ENV_MASTER = look_lib.MASTER_PATH
ENV_GRAPH_TAG = "EnvPropGraphVersion"
ENV_GRAPH_VERSION = "1"
ENV_DEFAULT_TEX = {"BC": "/Game/UM/Materials/Textures/T_UM_Default_BC",
                   "N": "/Game/UM/Materials/Textures/T_UM_Default_N",
                   "ORM": "/Game/UM/Materials/Textures/T_UM_Default_ORM"}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def folder_of(name: str) -> str:
    return f"{ROOT}/{KIT[name][0]}"


def material_of(name: str) -> str:
    """The texture / MI set of a prop: T_Env_<set>_*, MI_Env_<set> (the prop name unless it shares an atlas)."""
    return MATERIAL_OF.get(name, name)


def texture_keys(name: str) -> tuple:
    return TEXTURE_KEYS_OF.get(material_of(name), TEXTURE_KEYS)


def run_of(name: str) -> Path:
    return RUN_OF.get(name, RUN_DEFAULT)


def asset_paths(name: str) -> dict:
    f = folder_of(name)
    mat = material_of(name)
    out = {"mesh": f"{f}/SM_Env_{name}", "mi": f"{f}/MI_Env_{mat}"}
    out.update({f"tex:{k}": f"{f}/T_Env_{mat}_{k}" for k in texture_keys(name)})
    return out


def adapt_backwall_report(data: dict) -> dict:
    """The Blender lane-K back-wall report (BACKWALL_SCHEMA: exports[] + one shared texture set) as env-kit build-report
    entries keyed by the UE mesh name, so plan_prop / expected_hashes / target_of read it like track A's report."""
    tex = {k: dict(v) for k, v in (data.get("textures") or {}).items() if isinstance(v, dict)}
    for k, v in tex.items():
        v.setdefault("colorspace", "sRGB" if k == "BC" else "linear")
    assets = {}
    for ex in data.get("exports") or []:
        size = ((ex.get("boundsUeLocalUU") or {}).get("size")) or [None, None, None]
        checks = ex.get("checks") or {}
        assets[ex.get("name")] = {
            "ue": {"mesh": ex.get("name"), "material_instance": "MI_Env_BackWall", "folder": "/Game/EnvKit/Marmoreal/"},
            "fbx": {"path": ex.get("fbx"), "sha256": ex.get("sha256"), "bytes": ex.get("bytes")},
            "textures": tex,
            "target": {"dimension": "height", "uu": size[2]} if isinstance(size[2], (int, float)) else None,
            "readback": {"dimensions_uu_ue": {"X_depth_front_back": size[0], "Y_width": size[1], "Z_height": size[2]},
                         "triangles": (ex.get("roundtrip") or {}).get("triangles")},
            "checks_passed": (bool(checks) and all(checks.values())
                              and bool((data.get("checks") or {}).get(ex.get("name")))),
        }
    return {"schema": REPORT_SCHEMA, "adaptedFrom": BACKWALL_SCHEMA, "assets": assets,
            "conventions": {"normal": "DirectX (k_blender.py / static_prop_candidate: green flipped, UM_FBX_v1)"}}


# ------------------------------------------------------------------------------------------------ build report (A)
def load_build_report(run: Path) -> dict:
    path = run / "reports" / "build-report.json"
    info = {"path": rel(path), "present": path.is_file()}
    if not info["present"]:
        info["note"] = "absent (track A not finished?): every source is 'unverified'"
        return info
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        info.update(present=False, error=f"unreadable: {exc}")
        return info
    info.update(sha256=hashlib.sha256(raw).hexdigest(), schema=data.get("schema"), data=data)
    if data.get("schema") == BACKWALL_SCHEMA:
        info.update(data=adapt_backwall_report(data), note=f"{BACKWALL_SCHEMA} adapted to env-kit entries")
    elif data.get("schema") != REPORT_SCHEMA:
        info["note"] = f"schema {data.get('schema')!r} != {REPORT_SCHEMA}: generic sha256 scan"
    return info


def _generic_hashes(obj, out: dict) -> None:
    """Any {path|file|name: <file>, sha256: <hex>} or {<file name>: <hex>} anywhere -> out[basename] = {sha...}."""
    if isinstance(obj, dict):
        sha = obj.get("sha256")
        if isinstance(sha, str) and HEX64.match(sha):
            for key in ("path", "file", "name", "filename", "output"):
                value = obj.get(key)
                if isinstance(value, str) and "." in value:
                    out.setdefault(Path(value).name, set()).add(sha.lower())
        for key, value in obj.items():
            if isinstance(key, str) and "." in key and isinstance(value, str) and HEX64.match(value):
                out.setdefault(Path(key).name, set()).add(value.lower())
            _generic_hashes(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _generic_hashes(value, out)


def report_entry(report: dict, name: str) -> dict | None:
    data = report.get("data") or {}
    assets = data.get("assets")
    if isinstance(assets, dict):
        kit_id = KIT[name][1]
        if isinstance(assets.get(kit_id), dict):
            return assets[kit_id]
        for entry in assets.values():  # keyed differently: find by the UE mesh name
            if isinstance(entry, dict) and (entry.get("ue") or {}).get("mesh") == f"SM_Env_{name}":
                return entry
    return None


def expected_hashes(report: dict, name: str) -> tuple[dict, str]:
    """{file name: {sha256...}} for the 4 sources of a prop, and where they came from."""
    entry = report_entry(report, name)
    out: dict = {}
    if entry is not None:
        fbx = entry.get("fbx") or {}
        if isinstance(fbx.get("sha256"), str):
            out.setdefault(Path(fbx.get("path") or f"SM_Env_{name}.fbx").name, set()).add(fbx["sha256"].lower())
        for key, tex in (entry.get("textures") or {}).items():
            if isinstance(tex, dict) and isinstance(tex.get("sha256"), str):
                out.setdefault(Path(tex.get("path") or f"T_Env_{name}_{key}.png").name, set()).add(tex["sha256"].lower())
        return out, "assets[%s]" % KIT[name][1]
    if report.get("data") is not None:
        _generic_hashes(report["data"], out)
        return out, "generic scan"
    return out, "none"


def normal_convention(report: dict, arg: str) -> tuple[str, str]:
    if arg in ("directx", "opengl"):
        return arg, "--normal"
    conv = ((report.get("data") or {}).get("conventions") or {})
    text = " ".join(str(conv.get(k, "")) for k in ("normal",)) + " " + str((conv.get("textures") or {}).get("N", ""))
    low = text.lower()
    if "directx" in low or "flip_green false" in low:
        return "directx", "build-report conventions"
    if "opengl" in low:
        return "opengl", "build-report conventions"
    return "directx", "default (task: normal DX)"


def target_of(report: dict, name: str) -> dict:
    entry = report_entry(report, name) or {}
    t = entry.get("target")
    if isinstance(t, dict) and t.get("dimension") in ("height", "length", "diameter") and isinstance(t.get("uu"), (int, float)):
        return {"dimension": t["dimension"], "uu": float(t["uu"]), "source": "build-report"}
    dim, uu = KIT[name][2]
    return {"dimension": dim, "uu": uu, "source": "default (task proposal)"}


def plan_prop(name: str, run: Path, report: dict) -> dict:
    export = run / "export"
    mat = material_of(name)
    files = {"fbx": export / f"SM_Env_{name}.fbx"}
    files.update({k: export / f"T_Env_{mat}_{k}.png" for k in texture_keys(name)})
    expected, source = expected_hashes(report, name)
    entry = report_entry(report, name) or {}
    plan = {"name": name, "map": KIT[name][0], "id": KIT[name][1], "assets": asset_paths(name), "sources": {},
            "material": mat, "run": rel(run), "hashSource": source, "target": target_of(report, name),
            "ok": True, "verified": True}
    ue = entry.get("ue") or {}
    if ue:
        want_folder = folder_of(name) + "/"
        plan["reportUe"] = {"folder": ue.get("folder"), "mesh": ue.get("mesh"), "mi": ue.get("material_instance"),
                            "matchesContract": ue.get("folder") in (want_folder, folder_of(name)) and
                                               ue.get("mesh") == f"SM_Env_{name}" and
                                               ue.get("material_instance") in (None, f"MI_Env_{mat}")}
    if entry.get("checks_passed") is not None:
        plan["reportChecksPassed"] = bool(entry.get("checks_passed"))
    readback = (entry.get("readback") or {}).get("dimensions_uu_ue")
    if isinstance(readback, dict):
        plan["readbackUU"] = [readback.get("X_depth_front_back"), readback.get("Y_width"), readback.get("Z_height")]
    for key, path in files.items():
        item = {"path": rel(path), "abs": str(path)}
        if not path.is_file():
            item.update(status="missing")
            plan["ok"] = False
        else:
            got = sha256_file(path)
            want = expected.get(path.name, set())
            item.update(sha256=got, bytes=path.stat().st_size)
            if not want:
                item["status"] = "unverified"
                plan["verified"] = False
            elif got in want:
                item["status"] = "verified"
            else:
                item.update(status="mismatch", expected=sorted(want),
                            error="sha256 differs from the build report (re-run track A or fix the report)")
                plan["ok"] = False
        plan["sources"][key] = item
    return plan


# ---------------------------------------------------------------------------------------------------------- UE side
def texture_settings(key: str, convention: str) -> dict:
    tcs, grp, mips = u.TextureCompressionSettings, u.TextureGroup, u.TextureMipGenSettings
    # compression first (it decides what sRGB may be), then sRGB, group, mips
    if key == "BC":
        wanted = {"compression_settings": tcs.TC_DEFAULT, "srgb": True, "lod_group": grp.TEXTUREGROUP_WORLD}
    elif key == "N":
        wanted = {"compression_settings": tcs.TC_NORMALMAP, "srgb": False, "lod_group": grp.TEXTUREGROUP_WORLD_NORMAL_MAP,
                  "flip_green_channel": convention == "opengl"}
    elif key in ("ORM", "E"):  # E: the back wall's glow mask (linear, TC_Masks; not bound by M_EnvProp)
        wanted = {"compression_settings": tcs.TC_MASKS, "srgb": False, "lod_group": grp.TEXTUREGROUP_WORLD}
    else:
        raise KeyError(key)
    wanted.update({"mip_gen_settings": mips.TMGS_FROM_TEXTURE_GROUP, "never_stream": False})
    return wanted


def settings_match(obj, wanted: dict) -> bool:
    return all(obj.get_editor_property(k) == v for k, v in wanted.items())


def describe_texture(texture) -> dict:
    return {"srgb": bool(texture.get_editor_property("srgb")),
            "compression": str(texture.get_editor_property("compression_settings")),
            "lodGroup": str(texture.get_editor_property("lod_group")),
            "flipGreen": bool(texture.get_editor_property("flip_green_channel")),
            "sizeX": int(texture.blueprint_get_size_x()), "sizeY": int(texture.blueprint_get_size_y())}


def split(path: str) -> tuple[str, str]:
    folder, leaf = path.rsplit("/", 1)
    return folder, leaf


def import_texture(src: dict, asset: str, key: str, convention: str, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    wanted = texture_settings(key, convention)
    texture = u.load_asset(asset) if eal.does_asset_exist(asset) else None
    if (texture is not None and not force and eal.get_metadata_tag(texture, SHA_TAG) == src["sha256"]
            and settings_match(texture, wanted)):
        return {"action": "unchanged", **describe_texture(texture)}
    action = "reimported" if texture is not None else "imported"
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
    if texture is None or not isinstance(texture, u.Texture2D):
        raise RuntimeError(f"import of {src['path']} did not produce the texture {asset}")
    for prop, value in wanted.items():
        texture.set_editor_property(prop, value)
    eal.set_metadata_tag(texture, SHA_TAG, src["sha256"])
    if not eal.save_loaded_asset(texture, False):
        raise RuntimeError(f"could not save {asset}")
    if not settings_match(texture, wanted):
        raise RuntimeError(f"{asset}: settings did not stick: {describe_texture(texture)}")
    return {"action": action, **describe_texture(texture)}


def check_master(master) -> dict:
    mel = u.MaterialEditingLibrary
    tex = {str(n) for n in mel.get_texture_parameter_names(master)}
    vec = {str(n) for n in mel.get_vector_parameter_names(master)}
    missing = [p for p in list(PARAMS.values()) + [PARAM_MASK] if p not in tex] + ([PARAM_TEAM] if PARAM_TEAM not in vec else [])
    return {"path": MASTER, "textureParams": sorted(tex), "vectorParams": sorted(vec), "missing": missing}


def build_env_master(force: bool) -> dict:
    """/Game/EnvKit/Shared/M_EnvProp (lit, opaque, one-sided; the MIs override TwoSided like the M_UM_Figure ones):

      BC / N / ORM  TextureSampleParameter2D BaseColorTexture / NormalTexture / ORMTexture (UV0, their own samplers)
      BaseColor     Custom 'EnvPropAlbedo'   (env_prop_look.HLSL_ALBEDO: C = BC.rgb, Win = RegionWindow,
                                              Adj = RegionAdjust, Rest = RestAdjust, Soft = WindowSoft)
      Emissive      Custom 'EnvPropEmissive' (env_prop_look.HLSL_EMISSIVE: C = BC.rgb, Win = EmissiveWindow,
                                              Soft = WindowSoft, Col = EmissiveColor.rgb, Intensity = EmissiveIntensity)
      Normal        lerp((0,0,1), N.rgb, NormalStrength)
      Roughness     lerp(RoughnessMin, RoughnessMax, ORM.g);  Metallic ORM.b;  AO ORM.r
    At the defaults (env_prop_look.VECTOR_DEFAULTS / SCALAR_DEFAULTS) the output equals M_UM_Figure at its neutral
    defaults (BC, N, ORM.G, ORM.B, ORM.R, no emissive)."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    material = u.load_asset(ENV_MASTER) if eal.does_asset_exist(ENV_MASTER) else None
    if material is not None and not force and eal.get_metadata_tag(material, ENV_GRAPH_TAG) == ENV_GRAPH_VERSION:
        return {"action": "unchanged", "path": ENV_MASTER, "graphVersion": ENV_GRAPH_VERSION}
    action = "rebuilt" if material is not None else "created"
    folder, leaf = split(ENV_MASTER)
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(leaf, folder, u.Material, u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {ENV_MASTER}")
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("two_sided", False)
    mel.delete_all_material_expressions(material)
    ypos = [0]

    def expr(cls, x, y=None):
        node = mel.create_material_expression(material, cls, x, ypos[0] if y is None else y)
        if node is None:
            raise RuntimeError(f"could not create {cls}")
        if y is None:
            ypos[0] += 140
        return node

    def connect(src, out, dst, inp):
        if not mel.connect_material_expressions(src, out, dst, inp):
            raise RuntimeError(f"could not connect {src.get_name()}.{out or '<0>'} -> {dst.get_name()}.{inp}")

    def vector(name):
        node = expr(u.MaterialExpressionVectorParameter, -1500)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", u.LinearColor(*look_lib.VECTOR_DEFAULTS[name]))
        return node

    def scalar(name):
        node = expr(u.MaterialExpressionScalarParameter, -1500)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", float(look_lib.SCALAR_DEFAULTS[name]))
        return node

    def custom(desc, out_type, kind, x, y):
        node = expr(u.MaterialExpressionCustom, x, y)
        node.set_editor_property("description", desc)
        node.set_editor_property("output_type", out_type)
        pins = []
        for pin, _ in look_lib.HLSL_INPUTS[kind]:
            ci = u.CustomInput()
            ci.set_editor_property("input_name", pin)
            pins.append(ci)
        node.set_editor_property("inputs", pins)
        node.set_editor_property("code", look_lib.HLSL_ALBEDO if kind == "albedo" else look_lib.HLSL_EMISSIVE)
        return node

    st = u.MaterialSamplerType
    samples = {}
    for i, (key, stype) in enumerate((("BC", st.SAMPLERTYPE_COLOR), ("N", st.SAMPLERTYPE_NORMAL),
                                      ("ORM", st.SAMPLERTYPE_MASKS))):
        node = expr(u.MaterialExpressionTextureSampleParameter2D, -1100, -200 + 320 * i)
        node.set_editor_property("parameter_name", look_lib.TEX_PARAMS[key])
        node.set_editor_property("sampler_type", stype)
        default = u.load_asset(ENV_DEFAULT_TEX[key])
        if default is None:
            raise RuntimeError(f"default texture {ENV_DEFAULT_TEX[key]} missing (tools/tripo-pipeline/um_masters.py)")
        node.set_editor_property("texture", default)  # after the sampler type (AutoSetSampleType keeps them consistent)
        samples[key] = node
    vec = {name: vector(name) for name in look_lib.VECTOR_DEFAULTS}
    sca = {name: scalar(name) for name in look_lib.SCALAR_DEFAULTS}
    cmot = u.CustomMaterialOutputType
    albedo = custom("EnvPropAlbedo", cmot.CMOT_FLOAT3, "albedo", -600, -300)
    connect(samples["BC"], "RGB", albedo, "C")
    for pin, param in (("Win", "RegionWindow"), ("Adj", "RegionAdjust"), ("Rest", "RestAdjust"), ("Soft", "WindowSoft")):
        connect(vec[param], "RGBA", albedo, pin)
    mel.connect_material_property(albedo, "", u.MaterialProperty.MP_BASE_COLOR)
    emissive = custom("EnvPropEmissive", cmot.CMOT_FLOAT3, "emissive", -600, 100)
    connect(samples["BC"], "RGB", emissive, "C")
    connect(vec["EmissiveWindow"], "RGBA", emissive, "Win")
    connect(vec["WindowSoft"], "RGBA", emissive, "Soft")
    connect(vec["EmissiveColor"], "RGB", emissive, "Col")
    connect(sca["EmissiveIntensity"], "", emissive, "Intensity")
    mel.connect_material_property(emissive, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    flat = expr(u.MaterialExpressionConstant3Vector, -600, 420)
    flat.set_editor_property("constant", u.LinearColor(0.0, 0.0, 1.0, 0.0))
    normal = expr(u.MaterialExpressionLinearInterpolate, -350, 420)
    connect(flat, "", normal, "A")
    connect(samples["N"], "RGB", normal, "B")
    connect(sca["NormalStrength"], "", normal, "Alpha")
    mel.connect_material_property(normal, "", u.MaterialProperty.MP_NORMAL)
    rough = expr(u.MaterialExpressionLinearInterpolate, -350, 620)
    connect(sca["RoughnessMin"], "", rough, "A")
    connect(sca["RoughnessMax"], "", rough, "B")
    connect(samples["ORM"], "G", rough, "Alpha")
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(samples["ORM"], "B", u.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(samples["ORM"], "R", u.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.recompile_material(material)
    eal.set_metadata_tag(material, ENV_GRAPH_TAG, ENV_GRAPH_VERSION)
    if not eal.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {ENV_MASTER}")
    params = {"texture": sorted(str(n) for n in mel.get_texture_parameter_names(material)),
              "vector": sorted(str(n) for n in mel.get_vector_parameter_names(material)),
              "scalar": sorted(str(n) for n in mel.get_scalar_parameter_names(material))}
    missing = ([p for p in look_lib.TEX_PARAMS.values() if p not in params["texture"]]
               + [p for p in look_lib.VECTOR_DEFAULTS if p not in params["vector"]]
               + [p for p in look_lib.SCALAR_DEFAULTS if p not in params["scalar"]])
    if missing:
        raise RuntimeError(f"{ENV_MASTER}: parameters missing after the build: {missing}")
    return {"action": action, "path": ENV_MASTER, "graphVersion": ENV_GRAPH_VERSION,
            "expressions": int(mel.get_num_material_expressions(material)), "params": params}


def ensure_instance(name: str, master, textures: dict, mask, look: dict | None = None) -> dict:
    """MI_Env_<name>: child of M_UM_Figure (look None) or of M_EnvProp with the look's parameters
    (look = env_prop_look.mi_params(...); master is then M_EnvProp)."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = asset_paths(name)["mi"]
    mi = u.load_asset(path) if eal.does_asset_exist(path) else None
    action = "updated"
    if mi is None:
        folder, leaf = split(path)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(leaf, folder, u.MaterialInstanceConstant,
                                                                 u.MaterialInstanceConstantFactoryNew())
        action = "created"
    if mi is None:
        raise RuntimeError(f"could not create {path}")
    white = u.LinearColor(1.0, 1.0, 1.0, 1.0)
    two_sided = material_of(name) in TWO_SIDED

    def rgba(c) -> tuple:  # compared as numbers (struct == is not relied upon)
        return tuple(round(float(getattr(c, k)), 5) for k in ("r", "g", "b", "a"))

    def current() -> dict:
        parent = mi.get_editor_property("parent")
        ov = mi.get_editor_property("base_property_overrides")
        state = {"parent": parent.get_path_name() if parent else None,
                 "twoSided": (bool(ov.get_editor_property("override_two_sided")),
                              bool(ov.get_editor_property("two_sided")))}
        for key, param in PARAMS.items():
            bound = mel.get_material_instance_texture_parameter_value(mi, param)
            state[param] = bound.get_path_name() if bound else None
        if look is None:
            state[PARAM_TEAM] = rgba(mel.get_material_instance_vector_parameter_value(mi, PARAM_TEAM))
            if mask is not None:
                bound = mel.get_material_instance_texture_parameter_value(mi, PARAM_MASK)
                state[PARAM_MASK] = bound.get_path_name() if bound else None
        else:
            for pname in look["vector"]:
                state["v:" + pname] = rgba(mel.get_material_instance_vector_parameter_value(mi, pname))
            for pname in look["scalar"]:
                state["s:" + pname] = round(float(mel.get_material_instance_scalar_parameter_value(mi, pname)), 5)
        return state

    want = {"parent": master.get_path_name(), "twoSided": (two_sided, two_sided)}
    want.update({param: textures[key].get_path_name() for key, param in PARAMS.items()})
    if look is None:
        want[PARAM_TEAM] = rgba(white)
        if mask is not None:
            want[PARAM_MASK] = mask.get_path_name()
    else:
        want.update({"v:" + k: tuple(round(float(x), 5) for x in v) for k, v in look["vector"].items()})
        want.update({"s:" + k: round(float(v), 5) for k, v in look["scalar"].items()})
    if action == "updated" and current() == want:
        return {"action": "unchanged", "path": path, "params": {k: str(v) for k, v in want.items()}}
    old_parent = mi.get_editor_property("parent")
    if (old_parent is not None and old_parent.get_path_name() != master.get_path_name()
            and hasattr(mel, "clear_all_material_instance_parameters")):
        mel.clear_all_material_instance_parameters(mi)  # drop the other master's overrides (TeamColor, TeamMask)
    mel.set_material_instance_parent(mi, master)
    for key, param in PARAMS.items():
        mel.set_material_instance_texture_parameter_value(mi, param, textures[key])
    if look is None:
        if mask is not None:
            mel.set_material_instance_texture_parameter_value(mi, PARAM_MASK, mask)
        mel.set_material_instance_vector_parameter_value(mi, PARAM_TEAM, white)
    else:
        for pname, v in look["vector"].items():
            mel.set_material_instance_vector_parameter_value(mi, pname, u.LinearColor(*[float(x) for x in v]))
        for pname, v in look["scalar"].items():
            mel.set_material_instance_scalar_parameter_value(mi, pname, float(v))
    ov = mi.get_editor_property("base_property_overrides")  # a copy: set the fields, then write it back
    ov.set_editor_property("override_two_sided", two_sided)
    ov.set_editor_property("two_sided", two_sided)
    mi.set_editor_property("base_property_overrides", ov)
    mel.update_material_instance(mi)
    if not eal.save_loaded_asset(mi, False):
        raise RuntimeError(f"could not save {path}")
    got = current()
    if got != want:
        diff = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
        raise RuntimeError(f"{path}: parameters did not bind (got, want): {diff}")
    return {"action": action, "path": path, "parent": master.get_path_name(),
            "params": {k: str(v) for k, v in want.items()}}


def setp(obj, prop: str, value) -> bool:
    try:
        obj.set_editor_property(prop, value)
        return True
    except Exception:  # noqa: BLE001 - optional property (engine version)
        return False


def import_mesh(src: dict, asset: str, scale: float) -> dict:
    """Legacy FbxFactory with an explicit FbxImportUI (never Interchange, nothing global changed)."""
    folder, leaf = split(asset)
    o = u.FbxImportUI()
    o.set_editor_property("automated_import_should_detect_type", False)
    o.set_editor_property("import_mesh", True)
    o.set_editor_property("import_as_skeletal", False)
    o.set_editor_property("mesh_type_to_import", u.FBXImportType.FBXIT_STATIC_MESH)
    o.set_editor_property("original_import_type", u.FBXImportType.FBXIT_STATIC_MESH)
    o.set_editor_property("import_materials", False)
    o.set_editor_property("import_textures", False)
    o.set_editor_property("import_animations", False)
    d = o.get_editor_property("static_mesh_import_data")
    d.set_editor_property("combine_meshes", True)
    d.set_editor_property("vertex_color_import_option", u.VertexColorImportOption.IGNORE)
    d.set_editor_property("normal_import_method", u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    d.set_editor_property("import_uniform_scale", float(scale))
    res = {"factory": "FbxFactory", "normalImportMethod": "FBXNIM_IMPORT_NORMALS", "importUniformScale": float(scale),
           "autoGenerateCollisionOff": setp(d, "auto_generate_collision", False),
           "buildNaniteOff": setp(d, "build_nanite", False)}
    t = u.AssetImportTask()
    t.set_editor_property("filename", src["abs"])
    t.set_editor_property("destination_path", folder)
    t.set_editor_property("destination_name", leaf)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", False)
    t.set_editor_property("factory", u.FbxFactory())
    t.set_editor_property("options", o)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    res["imported"] = [str(x) for x in t.get_editor_property("imported_object_paths")]
    if not res["imported"]:
        raise RuntimeError(f"the import of {src['path']} produced no assets")
    return res


def sm_api():
    """StaticMeshEditorSubsystem, or the older static EditorStaticMeshLibrary (same function names) when the subsystem
    is not available in this commandlet."""
    sms = None
    try:
        # -run=pythonscript does not load the StaticMeshEditor module, so its editor subsystem does not exist yet
        # (get_editor_subsystem returns None and the deprecated EditorStaticMeshLibrary answers -1); loading the
        # module creates it (UE 5.8, measured 2026-09-30)
        u.load_module("StaticMeshEditor")
        sms = u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
    except Exception:  # noqa: BLE001 - engine / commandlet dependent
        sms = None
    if sms is None and hasattr(u, "EditorStaticMeshLibrary"):
        sms = u.EditorStaticMeshLibrary
    if sms is None:
        raise RuntimeError("StaticMeshEditorSubsystem unavailable (run inside UnrealEditor-Cmd -run=pythonscript)")
    return sms


def ensure_mesh_settings(mesh, mi) -> dict:
    """Nanite off, no simple collision + CTF_UseSimpleAsComplex (no collision at all), every slot -> MI. Returns the
    changes made (empty = already so)."""
    sms = sm_api()
    changes = []
    nanite = mesh.get_editor_property("nanite_settings")
    if nanite.get_editor_property("enabled"):
        nanite.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", nanite)
        changes.append("nanite off")
    if sms.get_simple_collision_count(mesh) > 0:
        sms.remove_collisions(mesh)
        changes.append("simple collision removed")
    try:  # no simple shapes + simple-as-complex = no collision data at all (the components are NoCollision anyway)
        body = mesh.get_editor_property("body_setup")
        flag = u.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX
        if body is not None and body.get_editor_property("collision_trace_flag") != flag:
            body.set_editor_property("collision_trace_flag", flag)
            changes.append("collision trace simple-as-complex (no complex collision)")
    except Exception as exc:  # noqa: BLE001 - optional hardening; the simple collision is already gone
        changes.append(f"collision trace flag not set ({type(exc).__name__}: {exc})")
    slots = len(mesh.get_editor_property("static_materials"))
    for index in range(slots):
        current = mesh.get_material(index)
        if current is None or current.get_path_name() != mi.get_path_name():
            mesh.set_material(index, mi)
            changes.append(f"slot {index} -> {mi.get_name()}")
    return {"changes": changes, "slots": slots}


def measure_mesh(mesh, plan: dict) -> dict:
    sms = sm_api()
    box = mesh.get_bounding_box()
    mn, mx = box.min, box.max
    size = [round(mx.x - mn.x, 3), round(mx.y - mn.y, 3), round(mx.z - mn.z, 3)]
    out = {"boundsMin": [round(mn.x, 3), round(mn.y, 3), round(mn.z, 3)],
           "boundsMax": [round(mx.x, 3), round(mx.y, 3), round(mx.z, 3)], "sizeUU": size,
           "nanite": bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")),
           "simpleCollision": int(sms.get_simple_collision_count(mesh)),
           "slots": [mesh.get_material(i).get_path_name() if mesh.get_material(i) else None
                     for i in range(len(mesh.get_editor_property("static_materials")))]}
    try:
        body = mesh.get_editor_property("body_setup")
        out["collisionTraceFlag"] = str(body.get_editor_property("collision_trace_flag")) if body else None
    except Exception as exc:  # noqa: BLE001 - measurement only
        out["collisionTraceFlag"] = f"n/a ({exc})"
    try:
        out["verticesLod0"] = int(sms.get_number_verts(mesh, 0))
    except Exception as exc:  # noqa: BLE001 - measurement only
        out["verticesLod0"] = f"n/a ({exc})"
    try:
        out["trianglesLod0"] = int(mesh.get_num_triangles(0))
    except Exception:  # noqa: BLE001 - not exposed in every engine version
        out["trianglesLod0"] = None
    out.update(size_check(size, out["boundsMin"], out["boundsMax"], plan))
    return out


def size_check(size: list, mn: list, mx: list, plan: dict) -> dict:
    """World-free (also used by the plain-Python self-check): target, readback and pivot of measured bounds."""
    t = plan["target"]
    measured = size[2] if t["dimension"] == "height" else max(size[0], size[1])
    ratio = measured / t["uu"] if t["uu"] else 0.0
    err = abs(ratio - 1.0)
    verdict = "ok" if err <= SIZE_OK else ("warning" if err <= SIZE_WARN else "failed")
    out = {"target": dict(t, measured=round(measured, 3), ratio=round(ratio, 5), verdict=verdict)}
    if verdict == "failed":
        for factor in (100.0, 0.01, 2.54, 1 / 2.54):
            if abs(ratio * factor - 1.0) <= SIZE_WARN:
                out["target"]["hint"] = f"re-run with --import-scale {factor:g} (units / UnitScaleFactor mismatch)"
    rb = plan.get("readbackUU")
    if rb and all(isinstance(v, (int, float)) for v in rb):
        delta = [round(size[i] - rb[i], 3) for i in range(3)]
        out["readback"] = {"blenderUU": rb, "deltaUU": delta, "ok": all(abs(d) <= 0.5 for d in delta)}
    centre = [(mn[i] + mx[i]) / 2.0 for i in range(2)]
    out["pivot"] = {"minZ": mn[2], "centreXY": [round(c, 3) for c in centre],
                    "baseCentre": abs(mn[2]) <= 0.5 and all(abs(c) <= 0.5 for c in centre)}
    return out


def folder_listing(folder: str) -> list:
    return sorted(str(p).split(".")[0] for p in u.EditorAssetLibrary.list_assets(folder, recursive=True,
                                                                                  include_folder=False))


def run_import(plans: dict, args, convention: str) -> tuple[dict, bool]:
    eal = u.EditorAssetLibrary
    ok = True
    result: dict = {}
    master = u.load_asset(MASTER)
    if master is None:
        return {"error": f"master {MASTER} missing (tools/tripo-pipeline/um_masters.py builds it)"}, False
    result["master"] = check_master(master)
    if result["master"]["missing"]:
        return result, False
    mask = u.load_asset(MASK_NONE) if eal.does_asset_exist(MASK_NONE) else None
    result["teamMask"] = MASK_NONE if mask is not None else "missing (TeamColor white keeps BC unchanged anyway)"
    env_master = None
    if any(plan.get("look") for plan in plans.values()):
        try:
            result["envMaster"] = build_env_master(args.force)
            env_master = u.load_asset(ENV_MASTER)
        except Exception as exc:  # noqa: BLE001 - the look props fail, the others go on
            result["envMaster"] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
            ok = False
    folders_before = {f: folder_listing(f) for f in sorted({folder_of(n) for n in plans}) if eal.does_directory_exist(f)}
    result["props"] = {}
    shared: dict = {}  # material set -> the prop that imported its textures / MI in this run
    for name, plan in plans.items():
        out: dict = {}
        result["props"][name] = out
        if not plan["ok"] or (args.require_verified and not plan["verified"]):
            out["skipped"] = ("source missing or sha256 mismatch" if not plan["ok"]
                              else "unverified sources and --require-verified")
            ok = False
            continue
        try:
            paths = plan["assets"]
            textures = {}
            mat = plan.get("material", name)
            if mat in shared:  # the shared atlas + MI were already imported / checked for an earlier module
                textures = {key: u.load_asset(paths[f"tex:{key}"]) for key in texture_keys(name)}
                out["textures"] = {"sharedWith": shared[mat]}
                out["materialInstance"] = {"sharedWith": shared[mat], "path": paths["mi"]}
            else:
                out["textures"] = {}
                for key in texture_keys(name):
                    out["textures"][key] = import_texture(plan["sources"][key], paths[f"tex:{key}"], key,
                                                          plan.get("normalConvention", convention), args.force)
                    textures[key] = u.load_asset(paths[f"tex:{key}"])
                if plan.get("look"):
                    if env_master is None:
                        raise RuntimeError(f"{ENV_MASTER} not available (see ue.envMaster)")
                    out["materialInstance"] = ensure_instance(name, env_master, textures, mask, plan["look"])
                else:
                    out["materialInstance"] = ensure_instance(name, master, textures, mask)
                shared[mat] = name
            mi = u.load_asset(paths["mi"])
            fbx = plan["sources"]["fbx"]
            mesh = u.load_asset(paths["mesh"]) if eal.does_asset_exist(paths["mesh"]) else None
            scale_text = f"{args.import_scale:g}"
            if (mesh is not None and not args.force and eal.get_metadata_tag(mesh, SHA_TAG) == fbx["sha256"]
                    and eal.get_metadata_tag(mesh, SCALE_TAG) == scale_text):
                out["mesh"] = {"action": "unchanged"}
            else:
                out["mesh"] = dict(import_mesh(fbx, paths["mesh"], args.import_scale),
                                   action="reimported" if mesh is not None else "imported")
                mesh = u.load_asset(paths["mesh"])
                if mesh is None or not isinstance(mesh, u.StaticMesh):
                    raise RuntimeError(f"{paths['mesh']} is not a static mesh after the import")
                eal.set_metadata_tag(mesh, SHA_TAG, fbx["sha256"])
                eal.set_metadata_tag(mesh, SCALE_TAG, scale_text)
            settings = ensure_mesh_settings(mesh, mi)
            out["mesh"]["settingsChanged"] = settings["changes"]
            if settings["changes"] or out["mesh"]["action"] != "unchanged":
                if not eal.save_loaded_asset(mesh, False):
                    raise RuntimeError(f"could not save {paths['mesh']}")
            out["measure"] = measure_mesh(mesh, plan)
            m = out["measure"]
            problems = []
            if m["nanite"]:
                problems.append("nanite still on")
            if m["simpleCollision"]:
                problems.append("simple collision left")
            if any(s != mi.get_path_name() for s in m["slots"]) or not m["slots"]:
                problems.append("material slots not on the MI")
            if m["target"]["verdict"] == "failed":
                problems.append(f"size {m['target']['measured']} vs target {m['target']['uu']} ({m['target']['dimension']})")
            out["problems"] = problems
            ok = ok and not problems
        except Exception as exc:  # report and continue with the next prop
            out["error"] = f"{type(exc).__name__}: {exc}"
            ok = False
    # every asset the kit contract names (also those of kit names not selected in this run) is not foreign
    planned = {p for n in KIT for p in asset_paths(n).values()}
    result["folders"] = {}
    for folder in sorted({folder_of(n) for n in plans}):
        after = folder_listing(folder) if eal.does_directory_exist(folder) else []
        result["folders"][folder] = {"before": folders_before.get(folder, []), "after": after,
                                     "foreign": [a for a in after if a not in planned],
                                     "numberedDuplicates": [a for a in after if re.search(r"_\d+$", a)]}
    return result, ok


# ---------------------------------------------------------------------------------------------------------- look
def look_names() -> set:
    """Names a look file may use: the material sets (a prop's own name, or the shared set such as BackWall)."""
    return {material_of(n) for n in KIT}


def attach_look(plans: dict, run: Path | None, args) -> tuple[dict, bool]:
    """plans[name]['look'] = the M_EnvProp MI parameters of the prop's material set (env_prop_look.mi_params). The look
    files: --look, else <run>/scripts/env-prop-look.json of `run`, of every planned prop's run (plan['run']) and (without
    --run) of every kit prop's run (RUN_OF) that has one - one entry per material set across the files (a set listed twice fails). A look file that does not
    validate fails the run (nothing half-applied). Returns (report info, ok)."""
    if args.no_look:
        return {"used": False, "note": "--no-look: every MI on M_UM_Figure"}, True
    if args.look:
        paths = [Path(args.look)]
        if not paths[0].is_file():
            return {"used": False, "path": rel(paths[0]), "error": "look file missing"}, False
    else:
        # P5b tune: without --run also every kit prop's own run (RUN_OF), so a partial import (--names BackWall_*) finds
        # the same look files as a full one - the back-wall run has no look file of its own, its 'BackWall' entry is in
        # the P5 run's file (before, such an import put MI_Env_BackWall back on M_UM_Figure)
        runs = ([Path(run)] if run is not None else []) + [REPO / p["run"] for p in plans.values() if p.get("run")]
        if run is None:
            runs += [run_of(n) for n in KIT]
        paths = []
        for r in runs:
            cand = (r / "scripts" / "env-prop-look.json").resolve()
            if cand.is_file() and cand not in paths:
                paths.append(cand)
        if not paths:
            return {"used": False, "paths": [], "note": "no look file: every MI on M_UM_Figure"}, True
    merged, files = {}, []
    for path in paths:
        try:
            data = look_lib.load_look(path)
        except (OSError, ValueError) as exc:
            return {"used": False, "path": rel(path), "error": str(exc)}, False
        unknown = sorted(n for n in data["props"] if n not in look_names())
        if unknown:
            return {"used": False, "path": rel(path), "error": f"unknown kit names {unknown}"}, False
        twice = sorted(n for n in data["props"] if n in merged)
        if twice:
            return {"used": False, "path": rel(path), "error": f"look entries {twice} in two look files"}, False
        for n in data["props"]:
            merged[n] = (data, path)
        files.append({"path": rel(path), "sha256": sha256_file(path), "props": sorted(data["props"])})
    for name, plan in plans.items():
        hit = merged.get(material_of(name))
        if hit is not None:
            plan["look"] = look_lib.mi_params(hit[0], material_of(name))
            plan["lookFile"] = rel(hit[1])
    info = {"used": True, "master": ENV_MASTER, "files": files, "props": sorted(merged),
            "selected": sorted(n for n in plans if material_of(n) in merged)}
    if len(files) == 1:  # the single-file keys of the P4 report
        info.update(path=files[0]["path"], sha256=files[0]["sha256"])
    return info, True


# ---------------------------------------------------------------------------------------------------------- entry
def select(args) -> list:
    names = list(KIT)
    if args.maps:
        maps = {MAPS.get(m.strip().lower(), m.strip()) for m in args.maps.split(",") if m.strip()}
        unknown = maps - set(MAPS.values())
        if unknown:
            raise SystemExit(f"unknown map(s) {sorted(unknown)}; known: {sorted(MAPS)}")
        names = [n for n in names if KIT[n][0] in maps]
    if args.names:
        wanted = [n.strip() for n in args.names.split(",") if n.strip()]
        unknown = [n for n in wanted if n not in KIT]
        if unknown:
            raise SystemExit(f"unknown kit name(s) {unknown}; known: {list(KIT)}")
        names = [n for n in names if n in wanted]
    return names


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--run", default=None,
                        help="force one run directory (export/ + reports/) for every prop; default: RUN_OF per prop")
    parser.add_argument("--maps", default="", help="comma list: marmoreal,sarpedon (default both)")
    parser.add_argument("--names", default="", help="comma list of kit names (ArcadeBay, ..., Rope, Barrel, ...)")
    parser.add_argument("--report", default=None, help="report JSON path")
    parser.add_argument("--check", action="store_true", help="verify sources only (no UE import)")
    parser.add_argument("--force", action="store_true", help="re-import textures and meshes")
    parser.add_argument("--import-scale", type=float, default=1.0, help="FBX import_uniform_scale (UM_FBX_v1: 1.0)")
    parser.add_argument("--normal", choices=("auto", "directx", "opengl"), default="auto")
    parser.add_argument("--require-verified", action="store_true", help="refuse sources the build report does not list")
    parser.add_argument("--look", default=None,
                        help="look file of M_EnvProp (default <run>/scripts/env-prop-look.json, when present)")
    parser.add_argument("--no-look", action="store_true", help="every MI on M_UM_Figure (ignore the look file)")
    args = parser.parse_args(argv)
    started = time.time()
    forced = Path(args.run).resolve() if args.run else None
    names = select(args)
    runs = {name: forced or run_of(name).resolve() for name in names}
    reports = {r: load_build_report(r) for r in dict.fromkeys(runs.values())}
    conventions = {r: normal_convention(rep, args.normal) for r, rep in reports.items()}
    plans = {}
    for name in names:
        plans[name] = plan_prop(name, runs[name], reports[runs[name]])
        plans[name]["normalConvention"] = conventions[runs[name]][0]
    look_info, look_ok = attach_look(plans, forced, args)
    used = sorted({c for c, _ in conventions.values()})
    convention = used[0] if len(used) == 1 else "per-run"
    convention_source = "; ".join(f"{rel(r)}: {c} ({src})" for r, (c, src) in conventions.items())
    out = {"schema": "unmatched.env-kit-ue-import/1", "tool": "tools/art/env_kit/ue_import_env_kit.py",
           "mode": "check" if (args.check or u is None) else "import",
           "run": rel(forced) if forced else "per prop (RUN_OF)", "runs": sorted(rel(r) for r in reports),
           "contentRoot": ROOT, "master": MASTER, "envMaster": ENV_MASTER, "envGraphVersion": ENV_GRAPH_VERSION,
           "look": look_info, "normalConvention": convention, "normalConventionSource": convention_source,
           "importScale": args.import_scale,
           "buildReport": {rel(r): {k: v for k, v in rep.items() if k != "data"} for r, rep in reports.items()},
           "props": plans}
    ok = all(p["ok"] for p in plans.values()) and look_ok
    if args.require_verified:
        ok = ok and all(p["verified"] for p in plans.values())
    if out["mode"] == "import":
        imported, import_ok = run_import(plans, args, used[0] if len(used) == 1 else "directx")
        out["ue"] = imported
        out["engine"] = str(u.SystemLibrary.get_engine_version())
        ok = ok and import_ok
    out["ok"] = ok
    out["seconds"] = round(time.time() - started, 1)
    text = json.dumps(out, ensure_ascii=False, indent=1, default=str)
    if args.report:
        report_path = Path(args.report)
    elif u is not None:
        report_path = Path(u.Paths.project_saved_dir()) / "EnvKit" / "ue-import-report.json"
    else:
        report_path = None
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text + "\n", encoding="utf-8")
        out["reportPath"] = str(report_path)
    counts = {}
    for plan in plans.values():
        for item in plan["sources"].values():
            counts[item["status"]] = counts.get(item["status"], 0) + 1
    print("ENVKIT-IMPORT-REPORT " + json.dumps(out, ensure_ascii=False, default=str))
    print(f"ENVKIT-IMPORT-RESULT {'ok' if ok else 'failed'} mode={out['mode']} props={len(plans)} "
          f"sources={json.dumps(counts, sort_keys=True)} normal={convention} scale={args.import_scale:g}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        # inside UE: an exception makes the pythonscript commandlet log an error (the report says what failed)
        raise RuntimeError("ENVKIT import failed - see ENVKIT-IMPORT-REPORT")
