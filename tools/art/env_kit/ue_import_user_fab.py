"""ENV-MAPS P5c UserVariant: derived /Game/EnvKit/UserFab/ assets of the two NoAI packs for the user's layout variant.

ENV-U14 NoAI rule (docs/game-design/decisions/2026-09-30-env-original-maps-decisions.md, 2026-10-01 ~14:00): the packs
Megaplant_Library (Megaplants: Yoshino Cherry) and StyleHex_Studio (FREE Stylized Rocks Pack) are handled ONLY as asset
paths and UE technical data (class, bounds, triangles, dependencies, plugins, trace lines). This tool never opens,
exports, renders or reads a texture / thumbnail / frame of them - it wires asset paths into materials and meshes and
measures geometry (bounds, triangle counts). Their derivatives are placed only by the variant overlays
Config/ArtBoards/EnvLayouts/<map>.user.layout.json (-EnvLayoutVariant=user), never by <map>.layout.json.

Source of truth: art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/user-fab.json
(schema unmatched.env-user-fab/1). What the UE run writes (only below /Game/EnvKit/UserFab/; the packs are only loaded):
  master    M_UserFab_Tree: a small opaque DefaultLit material made here (MaterialEditingLibrary): texture parameter
            BaseColorMap (rgb) x vector Tint -> Custom 'UserFabNight' (lerp(luma, rgb, NightSaturation) x NightValue)
            -> BaseColor; scalar Roughness / Specular. No normal map. Why: the Megaplants MIs have their parent in the
            experimental ProceduralVegetationEditor plugin content (/ProceduralVegetationEditor/.../MA_Foliage_Trees);
            without that plugin they load parent-less (default material) - Unmatched enables no new plugin for them.
  instance  MI_UserFab_*: child of the master (texture parameters = pack textures by path) or of a pack MI (StyleHex:
            static switch 'Use Color Tint?' on + vector 'Color Tint' - the pack master multiplies its base colour texture
            by it only behind that switch, read from the T3D text of M_Environment_Basic); 'twoSided' sets the base
            property override (the blossom).
  duplicate SM_UserFab_<Name>: EditorAssetLibrary.duplicate_asset of a StyleHex static mesh; slot materials -> night MIs.
  bake      SM_UserFab_Yoshino<X>: a STATIC mesh baked from a Yoshino tree skeletal mesh (Tree_Yoshino_Cherry_01_<X>,
            a skeletal Nanite assembly that needs r.Nanite.Foliage / r.Nanite.AllowAssemblies + DynamicWind to draw):
            the base mesh in its reference pose (GeometryScript copy_mesh_from_skeletal_mesh) + every assembly node
            (the twig part at its Local transform, read from the T3D text export of the asset - the Nodes array is not
            exposed to Python) using the static twig meshes of the pack (Twig_Yoshino_Cherry_0N = the same geometry as
            SKM_Twig_*) at their Nanite fallback LOD (RenderData LOD0; SourceModel + simplify when unavailable),
            simplified further when the sum exceeds maxTris; Nanite on. Material ids 0 = bark, 1 = blossom (the
            parts' MaterialRemap (0, 1)). No plugin needed at runtime; GeometryScripting is mounted for this commandlet
            only (-EnablePlugins=GeometryScripting), the asset does not depend on it.
Idempotent: every asset carries UserFabSpec = sha256(tool version + its spec entry); a matching asset is left alone.
A bake is updated in place (copy_mesh_to_static_mesh) when its spec changes. An asset at a target path that this tool
did not create (no UserFabSource tag / another source) is reported and never overwritten.

Report: 'USERFAB-IMPORT-REPORT {json}', 'USERFAB-IMPORT-RESULT ok|failed'; <project>/Saved/EnvKit/ue-import-user-fab-report.json
(measured bounds / triangles / trunk base box per mesh - copy them into user-fab.json 'measured' with --adopt-report).

Run (editor CLOSED, package lock; -nullrhi, no GPU lock):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/env_kit/ue_import_user_fab.py" -unattended -nosplash -nullrhi -EnablePlugins=GeometryScripting
Pre-check without UE:
  python -B tools/art/env_kit/ue_import_user_fab.py --check [--require-packs]
  python -B tools/art/env_kit/ue_import_user_fab.py --adopt-report <report.json>   # writes the measured values

Status: предложено / технически импортировано after this run; художественная оценка - только пользователь
(агенты кадры с NoAI-ассетами не смотрят).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SPEC = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/user-fab.json"
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
CONTENT = REPO / "unreal/Unmatched/Content"
SCHEMA = "unmatched.env-user-fab/1"
TOOL_VERSION = "userfab-1"
ROOT = "/Game/EnvKit/UserFab/"
NOAI_ROOTS = ("Megaplant_Library", "StyleHex_Studio")
MAPS = ("Marmoreal", "Sarpedon")
DEST_MESH_RE = re.compile(r"^/Game/EnvKit/UserFab/(Marmoreal|Sarpedon)/SM_UserFab_([A-Za-z0-9]+)$")
DEST_MAT_RE = re.compile(r"^/Game/EnvKit/UserFab/(Marmoreal|Sarpedon|Shared)/(M|MI)_UserFab_([A-Za-z0-9]+)$")
PACKAGE_RE = re.compile(r"^/Game/[A-Za-z0-9_]+(/[A-Za-z0-9_ .-]+)+$")
TAG_SPEC = "UserFabSpec"
TAG_SOURCE = "UserFabSource"
NIGHT_NODE = "UserFabNight"
HLSL_NIGHT = ("float l = dot(C, float3(0.2126, 0.7152, 0.0722));\n"
              "return lerp(float3(l, l, l), C, Sat) * Val;\n")
MASTER_TEXTURES = ("BaseColorMap",)
MASTER_SCALARS = {"NightValue": 1.0, "NightSaturation": 1.0, "Roughness": 0.8, "Specular": 0.35}
MASTER_VECTORS = {"Tint": (1.0, 1.0, 1.0, 1.0)}
BOUNDS_TOL = 0.01
NODE_RE = re.compile(r"\(PartIndex=(\d+)(?:,TransformSpace=(\w+))?,Transform=\(Rotation=\(X=([-\d.eE+]+),Y=([-\d.eE+]+),"
                     r"Z=([-\d.eE+]+),W=([-\d.eE+]+)\),Translation=\(X=([-\d.eE+]+),Y=([-\d.eE+]+),Z=([-\d.eE+]+)\),"
                     r"Scale3D=\(X=([-\d.eE+]+),Y=([-\d.eE+]+),Z=([-\d.eE+]+)\)\)")
PART_RE = re.compile(r'MeshObjectPath="([^"]+)"(?:,MaterialRemap=\(([\d,]*)\))?')


# ------------------------------------------------------------------------------------------------ spec (plain Python)
def load_spec(path: Path = SPEC) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pack_of(path: str) -> str:
    parts = path.split("/")
    return parts[2] if len(parts) > 2 and parts[1] == "Game" else ""


def spec_sha(entry: dict) -> str:
    """sha256 of the tool version + one spec entry without its 'measured' block (measuring never forces a rebuild)."""
    e = {k: v for k, v in entry.items() if k != "measured"}
    return hashlib.sha256((TOOL_VERSION + json.dumps(e, sort_keys=True)).encode("utf-8")).hexdigest()


def material_path(data: dict, ref: str) -> str:
    return data["materials"][ref]["dest"] if ref in data.get("materials", {}) else ref


def parse_assembly_t3d(text: str) -> tuple[list[dict], list[dict]]:
    """(parts, nodes) of the NaniteAssemblyData in a T3D export of a skeletal mesh: parts = [{path, remap}], nodes =
    [{part, space, quat (x, y, z, w), loc, scale}]."""
    m = re.search(r"NaniteAssemblyData=\(Parts=\((.*?)\)\),Nodes=\(", text, re.S)
    parts = []
    if m:
        for pm in PART_RE.finditer(m.group(1)):
            remap = [int(x) for x in pm.group(2).split(",") if x] if pm.group(2) else []
            parts.append({"path": pm.group(1), "remap": remap})
    nodes = []
    for nm in NODE_RE.finditer(text):  # every 'PartIndex=' must parse (see assembly_node_count)
        g = nm.groups()
        nodes.append({"part": int(g[0]), "space": g[1] or "Local", "quat": [float(x) for x in g[2:6]],
                      "loc": [float(x) for x in g[6:9]], "scale": [float(x) for x in g[9:12]]})
    return parts, nodes


def static_twin(skm_path: str) -> str:
    """/Game/.../Instances/SKM_Twig_Yoshino_Cherry_01.SKM_Twig_Yoshino_Cherry_01 -> /Game/.../Instances/Twig_Yoshino_Cherry_01
    (the pack's static mesh with the same geometry and pivot)."""
    pkg = skm_path.split(".")[0]
    folder, leaf = pkg.rsplit("/", 1)
    return f"{folder}/{leaf[len('SKM_'):]}" if leaf.startswith("SKM_") else pkg


def validate_spec(data: dict) -> list[str]:
    err = []
    if data.get("schema") != SCHEMA:
        err.append(f"schema {data.get('schema')!r} != {SCHEMA}")
    if sorted(data.get("noAiPacks", [])) != sorted(NOAI_ROOTS):
        err.append(f"noAiPacks must be {list(NOAI_ROOTS)}")
    mats, meshes = data.get("materials", {}), data.get("meshes", {})
    if not isinstance(mats, dict) or not isinstance(meshes, dict) or not meshes:
        return err + ["materials / meshes missing"]

    def source_ok(tag: str, path: str) -> None:
        if pack_of(path) not in NOAI_ROOTS:
            err.append(f"{tag}: {path} is not in a NoAI pack {list(NOAI_ROOTS)} (AI-allowed packs: ue_import_fab_picks.py)")
        elif not PACKAGE_RE.match(path):
            err.append(f"{tag}: {path!r} is not a package path")

    dests = set()
    for key, m in mats.items():
        tag = f"material {key}"
        dest = m.get("dest", "")
        if not DEST_MAT_RE.match(dest) or dest.rsplit("/", 1)[-1] != key:
            err.append(f"{tag}: dest {dest!r} is not {ROOT}<Map|Shared>/{key}")
        if dest in dests:
            err.append(f"{tag}: dest {dest} used twice")
        dests.add(dest)
        kind = m.get("kind")
        if kind == "master":
            if not key.startswith("M_UserFab_"):
                err.append(f"{tag}: a master is M_UserFab_*")
        elif kind == "instance":
            if not key.startswith("MI_UserFab_"):
                err.append(f"{tag}: an instance is MI_UserFab_*")
            parent = m.get("parent", "")
            if parent in mats:
                if mats[parent].get("kind") != "master":
                    err.append(f"{tag}: parent {parent} is not a master")
                for t in m.get("textures", {}):
                    if t not in MASTER_TEXTURES:
                        err.append(f"{tag}: texture parameter {t!r} is not on the master {list(MASTER_TEXTURES)}")
                for k in m.get("scalar", {}):
                    if k not in MASTER_SCALARS:
                        err.append(f"{tag}: scalar {k!r} is not on the master")
                for k in m.get("vector", {}):
                    if k not in MASTER_VECTORS:
                        err.append(f"{tag}: vector {k!r} is not on the master")
            else:
                source_ok(tag, parent)
            for t, p in m.get("textures", {}).items():
                source_ok(f"{tag} texture {t}", p)
            for k, v in m.get("scalar", {}).items():
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    err.append(f"{tag}: scalar {k} is not a number")
            for k, v in m.get("vector", {}).items():
                if not (isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) for x in v)):
                    err.append(f"{tag}: vector {k} is not [r, g, b, a]")
            for k, v in m.get("switch", {}).items():
                if not isinstance(v, bool):
                    err.append(f"{tag}: static switch {k} is not a bool")
            if "twoSided" in m and not isinstance(m["twoSided"], bool):
                err.append(f"{tag}: twoSided is not a bool")
        else:
            err.append(f"{tag}: kind {kind!r} is not master / instance")
    used = set()
    for name, e in meshes.items():
        tag = f"mesh {name}"
        dm = DEST_MESH_RE.match(e.get("dest", ""))
        if not dm or dm.group(2) != name or dm.group(1) != e.get("map"):
            err.append(f"{tag}: dest {e.get('dest')!r} is not {ROOT}{e.get('map')}/SM_UserFab_{name}")
        if e.get("dest") in dests:
            err.append(f"{tag}: dest {e.get('dest')} used twice")
        dests.add(e.get("dest"))
        source_ok(tag, e.get("source", ""))
        kind = e.get("kind")
        if kind not in ("bake", "duplicate"):
            err.append(f"{tag}: kind {kind!r} is not bake / duplicate")
        if kind == "bake":
            mt = e.get("maxTris")
            if not (isinstance(mt, int) and 20000 <= mt <= 2000000):
                err.append(f"{tag}: maxTris must be an int in 20000..2000000")
        sr = e.get("scaleRange")
        if not (isinstance(sr, list) and len(sr) == 2 and 0 < sr[0] < sr[1] <= 3.0):
            err.append(f"{tag}: scaleRange")
        slots = e.get("slots", [])
        if not slots:
            err.append(f"{tag}: no slots")
        for s in slots:
            mat = s.get("material")
            if mat not in mats or mats[mat].get("kind") != "instance":
                err.append(f"{tag} slot {s.get('index', s.get('slot'))}: material {mat!r} is not an instance of 'materials'")
            else:
                used.add(mat)
            if kind == "bake" and not isinstance(s.get("index"), int):
                err.append(f"{tag}: bake slots are by material index")
            if kind == "duplicate" and not isinstance(s.get("slot"), str):
                err.append(f"{tag}: duplicate slots are by slot name")
        ms = e.get("measured")
        if ms is not None:
            lo, hi = ms.get("bboxMin"), ms.get("bboxMax")
            if not (isinstance(lo, list) and isinstance(hi, list) and len(lo) == len(hi) == 3
                    and all(b > a for a, b in zip(lo, hi))):
                err.append(f"{tag}: measured bboxMin / bboxMax")
            if not (isinstance(ms.get("tris"), int) and ms["tris"] > 0):
                err.append(f"{tag}: measured tris")
            b = ms.get("base")
            if b is not None and not (isinstance(b, list) and len(b) == 4 and b[0] < b[2] and b[1] < b[3]):
                err.append(f"{tag}: measured base must be [x0, y0, x1, y1] or null")
    unused = {k for k, m in mats.items() if m.get("kind") == "instance"} - used
    if unused:
        err.append(f"instances used by no mesh slot: {sorted(unused)}")
    for k, m in mats.items():
        if m.get("kind") == "master" and not any(x.get("parent") == k for x in mats.values()):
            err.append(f"master {k} is the parent of no instance")
    return err


def content_file(path: str) -> Path:
    return CONTENT / (path.split(".")[0][len("/Game/"):] + ".uasset")


def check_sources_on_disk(data: dict) -> tuple[list[str], int]:
    """Every pack source as a .uasset file (existence only - nothing is opened)."""
    paths = set()
    for e in data["meshes"].values():
        paths.add(e["source"])
    for m in data["materials"].values():
        if m.get("kind") == "instance":
            if m["parent"] not in data["materials"]:
                paths.add(m["parent"])
            paths.update(m.get("textures", {}).values())
    missing = sorted(p for p in paths if not content_file(p).is_file())
    return missing, len(paths) - len(missing)


def check_layouts(data: dict, layout_dir: Path) -> tuple[list[str], dict]:
    """Main layouts: no UserFab / NoAI path. Overlays (<map>.user.layout.json): every mesh a planned UserFab dest of the
    same map or a non-NoAI path; no raw NoAI pack path."""
    err, used = [], {}
    planned = {e["dest"]: e for e in data["meshes"].values()}
    for key in ("marmoreal", "sarpedon"):
        f = Path(layout_dir) / f"{key}.layout.json"
        if f.is_file():
            text = f.read_text(encoding="utf-8")
            for marker in NOAI_ROOTS + (ROOT,):
                if marker in text:
                    err.append(f"{f.name}: contains {marker!r} - NoAI derivatives only in the user overlay (ENV-U14)")
        o = Path(layout_dir) / f"{key}.user.layout.json"
        if not o.is_file():
            continue
        ov = json.loads(o.read_text(encoding="utf-8"))
        for op in ("replace", "add"):
            for p in ov.get("props", {}).get(op, []):
                mesh = p.get("mesh")
                if mesh is None:
                    continue
                if pack_of(mesh) in NOAI_ROOTS:
                    err.append(f"{o.name} {p.get('id')}: raw NoAI pack path {mesh} - place the {ROOT} derivative "
                               f"(it is the cooked copy)")
                elif mesh.startswith(ROOT):
                    e = planned.get(mesh)
                    if e is None:
                        err.append(f"{o.name} {p.get('id')}: {mesh} is not a planned mesh of {SPEC.name}")
                    elif e["map"].lower() != key:
                        err.append(f"{o.name} {p.get('id')}: {mesh} belongs to {e['map']}")
                    else:
                        used.setdefault(key, []).append(p.get("id"))
    return err, used


def run_check(args) -> int:
    data = load_spec(Path(args.spec))
    errors = validate_spec(data)
    warnings = []
    if not errors:
        missing, found = check_sources_on_disk(data)
        if missing:
            (errors if args.require_packs else warnings).append(
                f"{len(missing)} NoAI pack sources missing in {CONTENT.as_posix()} (gitignored packs): {missing[:4]}")
        lerr, used = check_layouts(data, Path(args.layouts))
        errors += lerr
        unmeasured = sorted(n for n, e in data["meshes"].items() if not e.get("measured"))
        if unmeasured:
            warnings.append(f"meshes without measured bounds (run the UE import, then --adopt-report): {unmeasured}")
    else:
        found, used = 0, {}
    report = {"schema": "unmatched.env-user-fab-check/1", "spec": Path(args.spec).name,
              "materials": len(data.get("materials", {})), "meshes": len(data.get("meshes", {})),
              "packSourcesFound": found, "overlayProps": used, "errors": errors, "warnings": warnings}
    print("USERFAB-CHECK " + json.dumps(report, ensure_ascii=False))
    for w in warnings:
        print("  WARN  " + w)
    for e in errors:
        print("  ERROR " + e)
    print(f"USERFAB-CHECK {'ok' if not errors else 'failed'}")
    return 0 if not errors else 1


def adopt_report(args) -> int:
    """Copies the UE report's measured bounds / triangles / base boxes into the spec ('measured' blocks only)."""
    data = load_spec(Path(args.spec))
    rep = json.loads(Path(args.adopt_report).read_text(encoding="utf-8"))
    n = 0
    for r in rep.get("meshes", []):
        e = data["meshes"].get(r.get("name"))
        if e is None or r.get("problems"):
            continue
        ms = {"bboxMin": r["boundsMin"], "bboxMax": r["boundsMax"], "tris": r["tris"], "base": r.get("base")}
        if r.get("parts") is not None:
            ms["parts"] = r["parts"]
        if e.get("measured") != ms:
            e["measured"] = ms
            n += 1
    Path(args.spec).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"USERFAB-ADOPT {n} mesh(es) updated in {Path(args.spec).name}")
    return 0


# ------------------------------------------------------------------------------------------------ UE side
def _guard(path: str) -> None:
    if not path.startswith(ROOT):
        raise RuntimeError(f"refusing to write {path}: only {ROOT}* is written (the pack folders stay pristine)")


def _tag(asset, key: str, value: str) -> None:
    u.EditorAssetLibrary.set_metadata_tag(asset, key, value)


def _save(asset, path: str) -> None:
    _guard(path)
    if not u.EditorAssetLibrary.save_loaded_asset(asset, False):
        raise RuntimeError(f"could not save {path}")


def _owned(asset, source: str, path: str) -> None:
    if u.EditorAssetLibrary.get_metadata_tag(asset, TAG_SOURCE) != source:
        raise RuntimeError(f"{path} exists but was not made by this tool from {source} - not overwritten")


def ensure_master(key: str, m: dict) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = m["dest"]
    _guard(path)
    want = spec_sha(m)
    source = "userfab:master"
    if eal.does_asset_exist(path):
        mat = u.load_asset(path)
        _owned(mat, source, path)
        if eal.get_metadata_tag(mat, TAG_SPEC) == want:
            return {"key": key, "action": "unchanged", "path": path}
        mel.delete_all_material_expressions(mat)
        action = "rebuilt"
    else:
        folder, leaf = path.rsplit("/", 1)
        mat = u.AssetToolsHelpers.get_asset_tools().create_asset(leaf, folder, u.Material, u.MaterialFactoryNew())
        if mat is None:
            raise RuntimeError(f"could not create {path}")
        _tag(mat, TAG_SOURCE, source)
        action = "created"
    mat.set_editor_property("blend_mode", u.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    mat.set_editor_property("two_sided", False)
    tex = mel.create_material_expression(mat, u.MaterialExpressionTextureSampleParameter2D, -1100, -200)
    tex.set_editor_property("parameter_name", "BaseColorMap")
    tex.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_COLOR)
    default_tex = u.load_asset("/Engine/EngineResources/DefaultTexture")
    if default_tex is not None:
        tex.set_editor_property("texture", default_tex)
    tint = mel.create_material_expression(mat, u.MaterialExpressionVectorParameter, -1100, 100)
    tint.set_editor_property("parameter_name", "Tint")
    tint.set_editor_property("default_value", u.LinearColor(*MASTER_VECTORS["Tint"]))
    mul = mel.create_material_expression(mat, u.MaterialExpressionMultiply, -800, -100)
    if not (mel.connect_material_expressions(tex, "RGB", mul, "A") and mel.connect_material_expressions(tint, "", mul, "B")):
        raise RuntimeError(f"{path}: could not wire BaseColorMap x Tint")
    night = mel.create_material_expression(mat, u.MaterialExpressionCustom, -500, -100)
    night.set_editor_property("description", NIGHT_NODE)
    night.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT3)
    pins = []
    for pin in ("C", "Sat", "Val"):
        ci = u.CustomInput()
        ci.set_editor_property("input_name", pin)
        pins.append(ci)
    night.set_editor_property("inputs", pins)
    night.set_editor_property("code", HLSL_NIGHT)
    params = {}
    for i, (pname, default) in enumerate(MASTER_SCALARS.items()):
        sp = mel.create_material_expression(mat, u.MaterialExpressionScalarParameter, -800, 150 + 80 * i)
        sp.set_editor_property("parameter_name", pname)
        sp.set_editor_property("default_value", float(default))
        params[pname] = sp
    for src, pin in ((mul, "C"), (params["NightSaturation"], "Sat"), (params["NightValue"], "Val")):
        if not mel.connect_material_expressions(src, "", night, pin):
            raise RuntimeError(f"{path}: could not connect -> {NIGHT_NODE}.{pin}")
    ok = (mel.connect_material_property(night, "", u.MaterialProperty.MP_BASE_COLOR)
          and mel.connect_material_property(params["Roughness"], "", u.MaterialProperty.MP_ROUGHNESS)
          and mel.connect_material_property(params["Specular"], "", u.MaterialProperty.MP_SPECULAR))
    if not ok:
        raise RuntimeError(f"{path}: could not connect the material outputs")
    mel.recompile_material(mat)
    have = {str(n) for n in mel.get_scalar_parameter_names(mat)}
    if not set(MASTER_SCALARS) <= have:
        raise RuntimeError(f"{path}: scalar parameters missing after compile ({sorted(have)})")
    _tag(mat, TAG_SPEC, want)
    _save(mat, path)
    return {"key": key, "action": action, "path": path}


def ensure_instance(key: str, m: dict, data: dict) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = m["dest"]
    _guard(path)
    parent_path = material_path(data, m["parent"])
    parent = u.load_asset(parent_path)
    if parent is None:
        raise RuntimeError(f"{path}: parent {parent_path} missing")
    mi = u.load_asset(path) if eal.does_asset_exist(path) else None
    action = "updated"
    if mi is None:
        folder, leaf = path.rsplit("/", 1)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(leaf, folder, u.MaterialInstanceConstant,
                                                                 u.MaterialInstanceConstantFactoryNew())
        if mi is None:
            raise RuntimeError(f"could not create {path}")
        _tag(mi, TAG_SOURCE, parent_path)
        action = "created"
    else:
        _owned(mi, parent_path, path)
    want = spec_sha(m)
    if action == "updated" and eal.get_metadata_tag(mi, TAG_SPEC) == want:
        return {"key": key, "action": "unchanged", "path": path}
    mel.set_material_instance_parent(mi, parent)
    have_s = {str(n) for n in mel.get_scalar_parameter_names(parent)}
    have_v = {str(n) for n in mel.get_vector_parameter_names(parent)}
    have_t = {str(n) for n in mel.get_texture_parameter_names(parent)}
    skipped, before = [], {}
    for k, v in m.get("scalar", {}).items():
        if k in have_s:
            mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
        else:
            skipped.append(k)
    for k, v in m.get("vector", {}).items():
        if k in have_v:
            cur = mel.get_material_instance_vector_parameter_value(parent, k) if isinstance(parent, u.MaterialInstance) else None
            if cur is not None:
                before[k] = [round(cur.r, 4), round(cur.g, 4), round(cur.b, 4), round(cur.a, 4)]
            mel.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(*[float(x) for x in v]))
        else:
            skipped.append(k)
    have_sw = {str(n) for n in mel.get_static_switch_parameter_names(parent)}
    for k, v in m.get("switch", {}).items():
        if k in have_sw:
            mel.set_material_instance_static_switch_parameter_value(mi, k, bool(v))
        else:
            skipped.append(k)
    for k, tp in m.get("textures", {}).items():
        t = u.load_asset(tp)
        if t is None:
            raise RuntimeError(f"{path}: texture {tp} missing")
        if k in have_t:
            mel.set_material_instance_texture_parameter_value(mi, k, t)
        else:
            skipped.append(k)
    if "twoSided" in m:
        ov = mi.get_editor_property("base_property_overrides")
        ov.set_editor_property("override_two_sided", True)
        ov.set_editor_property("two_sided", bool(m["twoSided"]))
        mi.set_editor_property("base_property_overrides", ov)
    mel.update_material_instance(mi)
    _tag(mi, TAG_SPEC, want)
    _save(mi, path)
    out = {"key": key, "action": action, "path": path, "parent": parent_path}
    if before:
        out["parentVectors"] = before  # technical parameter values of the pack MI (numbers only)
    if skipped:
        out["warning"] = f"parameters not on the parent (not set): {skipped}"
    return out


def _bounds(mesh) -> tuple[list, list]:
    bb = mesh.get_bounding_box()
    return ([round(bb.min.x, 2), round(bb.min.y, 2), round(bb.min.z, 2)],
            [round(bb.max.x, 2), round(bb.max.y, 2), round(bb.max.z, 2)])


def _set_slots(mesh, e: dict, data: dict) -> list:
    changed = []
    slots = list(mesh.get_editor_property("static_materials"))
    by_name = {str(s.get_editor_property("material_slot_name")): i for i, s in enumerate(slots)}
    for s in e["slots"]:
        idx = s["index"] if "index" in s else by_name.get(s["slot"])
        if idx is None or idx >= len(slots):
            raise RuntimeError(f"{e['dest']}: slot {s} missing (slots {sorted(by_name)})")
        target = material_path(data, s["material"])
        mat = u.load_asset(target)
        if mat is None:
            raise RuntimeError(f"{e['dest']}: material {target} missing")
        cur = slots[idx].get_editor_property("material_interface")
        if cur is None or cur.get_path_name().split(".")[0] != target:
            mesh.set_material(idx, mat)
            changed.append(idx)
    return changed


def _tris_static(mesh) -> int | None:
    """Source triangles of LOD0 (GeometryScript copy of the SourceModel; the render-data count of a Nanite mesh is its
    fallback)."""
    try:
        dm = u.DynamicMesh()
        opts = u.GeometryScriptCopyMeshFromAssetOptions()
        lod = u.GeometryScriptMeshReadLOD()
        lod.set_editor_property("lod_type", u.GeometryScriptLODType.SOURCE_MODEL)
        r = u.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(mesh, dm, opts, lod, False)
        dm = r[0] if isinstance(r, (tuple, list)) else dm
        return int(u.GeometryScript_MeshQueries.get_num_triangle_i_ds(dm))
    except Exception:  # noqa: BLE001 - optional measurement
        return None


def ensure_duplicate(name: str, e: dict, data: dict) -> dict:
    eal = u.EditorAssetLibrary
    path = e["dest"]
    _guard(path)
    if eal.does_asset_exist(path):
        mesh = u.load_asset(path)
        _owned(mesh, e["source"], path)
        action = "existing"
    else:
        mesh = eal.duplicate_asset(e["source"], path)
        if mesh is None:
            raise RuntimeError(f"could not duplicate {e['source']} -> {path}")
        _tag(mesh, TAG_SOURCE, e["source"])
        action = "duplicated"
    changed = _set_slots(mesh, e, data)
    want = spec_sha(e)
    if changed or eal.get_metadata_tag(mesh, TAG_SPEC) != want:
        _tag(mesh, TAG_SPEC, want)
        _save(mesh, path)
    lo, hi = _bounds(mesh)
    return {"name": name, "action": action, "path": path, "slotsSet": changed, "boundsMin": lo, "boundsMax": hi,
            "tris": _tris_static(mesh), "base": None, "problems": []}


def _copy_skeletal(skm):
    dm = u.DynamicMesh()
    r = u.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(skm, dm, u.GeometryScriptCopyMeshFromAssetOptions(),
                                                                u.GeometryScriptMeshReadLOD())
    return r[0] if isinstance(r, (tuple, list)) else dm


def _copy_static(sm, lod_type):
    dm = u.DynamicMesh()
    lod = u.GeometryScriptMeshReadLOD()
    lod.set_editor_property("lod_type", lod_type)
    lod.set_editor_property("lod_index", 0)
    r = u.GeometryScript_AssetUtils.copy_mesh_from_static_mesh_v2(sm, dm, u.GeometryScriptCopyMeshFromAssetOptions(), lod,
                                                                  False)
    if isinstance(r, (tuple, list)):
        dm, outcome = r[0], (r[1] if len(r) > 1 else None)
        if outcome is not None and "FAIL" in str(outcome).upper():
            raise RuntimeError(f"copy {sm.get_path_name()} {lod_type}: {outcome}")
    return dm


def _ntris(dm) -> int:
    return int(u.GeometryScript_MeshQueries.get_num_triangle_i_ds(dm))


def _simplify(dm, count: int) -> None:
    opts = u.GeometryScriptSimplifyMeshOptions()
    u.GeometryScript_MeshSimplification.apply_simplify_to_triangle_count(dm, int(count), opts)


def _trunk_base(dm, frac: float = 0.06) -> list | None:
    """XY box of the base-mesh vertices in the lowest 'frac' of its height (the trunk foot) - the layout's base
    footprint (layout_check check 5)."""
    r = u.GeometryScript_MeshQueries.get_all_vertex_positions(dm, False)
    items = r if isinstance(r, (tuple, list)) else (r,)
    lst = next((x for x in items if isinstance(x, u.GeometryScriptVectorList)), None)
    if lst is None:
        raise RuntimeError(f"get_all_vertex_positions returned {[type(x).__name__ for x in items]}")
    L = u.GeometryScript_List
    pts = None
    for fn in ("convert_vector_list_to_array", "vector_list_to_array"):
        if hasattr(L, fn):
            rr = getattr(L, fn)(lst)
            pts = list(rr[-1] if isinstance(rr, (tuple, list)) and rr and not isinstance(rr[0], u.Vector) else rr)
            break
    if pts is None:
        pts = [L.get_vector_list_item(lst, i)[0] if isinstance(L.get_vector_list_item(lst, i), tuple)
               else L.get_vector_list_item(lst, i) for i in range(L.get_vector_list_length(lst))]
    if not pts:
        return None
    z0 = min(p.z for p in pts)
    z1 = max(p.z for p in pts)
    lim = z0 + frac * (z1 - z0)
    low = [p for p in pts if p.z <= lim]
    return [round(min(p.x for p in low), 2), round(min(p.y for p in low), 2), round(max(p.x for p in low), 2),
            round(max(p.y for p in low), 2)]


def _material_id_tris(dm) -> dict:
    """Triangles per material id (0 = bark, 1 = blossom) of a dynamic mesh."""
    r = u.GeometryScript_Materials.get_all_triangle_material_i_ds(dm)
    items = r if isinstance(r, (tuple, list)) else (r,)
    lst = next((x for x in items if isinstance(x, u.GeometryScriptIndexList)), None)
    if lst is None:
        return {}
    L = u.GeometryScript_List
    rr = L.convert_index_list_to_array(lst)
    ids = rr[-1] if isinstance(rr, (tuple, list)) and rr and not isinstance(rr[0], int) else rr
    out = {}
    for x in list(ids):
        out[str(int(x))] = out.get(str(int(x)), 0) + 1
    return out


def ensure_bake(name: str, e: dict, data: dict) -> dict:
    eal = u.EditorAssetLibrary
    path = e["dest"]
    _guard(path)
    want = spec_sha(e)
    exists = eal.does_asset_exist(path)
    if exists:
        mesh = u.load_asset(path)
        _owned(mesh, e["source"], path)
        if eal.get_metadata_tag(mesh, TAG_SPEC) == want:
            changed = _set_slots(mesh, e, data)
            if changed:
                _save(mesh, path)
            lo, hi = _bounds(mesh)
            meta = json.loads(eal.get_metadata_tag(mesh, "UserFabBake") or "{}")
            return {"name": name, "action": "unchanged", "path": path, "boundsMin": lo, "boundsMax": hi,
                    "tris": meta.get("tris"), "base": meta.get("base"), "parts": meta.get("parts"), "problems": []}
    skm = u.load_asset(e["source"])
    if skm is None:
        raise RuntimeError(f"source {e['source']} missing")
    # assembly nodes from the T3D text export (technical text only)
    t3d = Path(u.Paths.project_saved_dir()) / "EnvKit/UserFab" / f"{name}.t3d"
    t3d.parent.mkdir(parents=True, exist_ok=True)
    task = u.AssetExportTask()
    task.object = skm
    task.filename = str(t3d)
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    task.exporter = u.ObjectExporterT3D()
    if not u.Exporter.run_asset_export_task(task):
        raise RuntimeError(f"{e['source']}: T3D export failed")
    text = t3d.read_text(encoding="utf-8", errors="replace")
    parts, nodes = parse_assembly_t3d(text)
    if not parts or not nodes:
        raise RuntimeError(f"{e['source']}: no Nanite assembly parts / nodes in the T3D export")
    if len(nodes) != text.count("PartIndex="):
        raise RuntimeError(f"{e['source']}: parsed {len(nodes)} of {text.count('PartIndex=')} assembly nodes")
    if any(n["space"] != "Local" for n in nodes):
        raise RuntimeError(f"{e['source']}: bone-relative assembly nodes are not supported by this bake")
    base = _copy_skeletal(skm)
    base_tris = _ntris(base)
    trunk = _trunk_base(base)
    # part meshes: the static twin at its Nanite fallback (render data LOD0), else the source model
    part_meshes, part_info = [], []
    for pi, p in enumerate(parts):
        twin_path = static_twin(p["path"])
        sm = u.load_asset(twin_path)
        if sm is None:
            raise RuntimeError(f"part {pi}: static twin {twin_path} missing")
        src = "renderData"
        try:
            dm = _copy_static(sm, u.GeometryScriptLODType.RENDER_DATA)
            if _ntris(dm) == 0:
                raise RuntimeError("empty")
        except Exception:  # noqa: BLE001 - fall back to the source model
            dm = _copy_static(sm, u.GeometryScriptLODType.SOURCE_MODEL)
            src = "sourceModel"
        if p["remap"] and p["remap"] != list(range(len(p["remap"]))):
            raise RuntimeError(f"part {pi}: MaterialRemap {p['remap']} is not the identity (bark 0, blossom 1)")
        part_meshes.append(dm)
        part_info.append({"part": pi, "twin": twin_path, "lod": src, "tris": _ntris(dm),
                          "nodes": sum(1 for n in nodes if n["part"] == pi)})
    total = base_tris + sum(pi_["tris"] * pi_["nodes"] for pi_ in part_info)
    budget = int(e["maxTris"])
    if total > budget:
        room = max(budget - base_tris, 1000)
        k = room / max(total - base_tris, 1)
        for pi_, dm in zip(part_info, part_meshes):
            target = max(200, int(pi_["tris"] * k))
            _simplify(dm, target)
            pi_["simplifiedTo"] = _ntris(dm)
    merged = base
    for n in nodes:
        t = u.Transform()
        t.set_editor_property("translation", u.Vector(*n["loc"]))
        t.set_editor_property("rotation", u.Quat(*n["quat"]))
        t.set_editor_property("scale3d", u.Vector(*n["scale"]))
        u.GeometryScript_MeshEdits.append_mesh(merged, part_meshes[n["part"]], t, True)
    tris = _ntris(merged)
    per_id = _material_id_tris(merged)
    if len(per_id) < len(e["slots"]):
        raise RuntimeError(f"material ids {per_id} of the bake do not cover the {len(e['slots'])} slots")
    if not exists:
        opts = u.GeometryScriptCreateNewStaticMeshAssetOptions()
        opts.set_editor_property("enable_nanite", bool(e.get("nanite", True)))
        opts.set_editor_property("enable_collision", False)
        opts.set_editor_property("enable_recompute_normals", False)
        opts.set_editor_property("enable_recompute_tangents", True)
        r = u.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(merged, path, opts)
        mesh = r[0] if isinstance(r, (tuple, list)) else r
        if mesh is None:
            raise RuntimeError(f"could not create {path}: {r}")
        _tag(mesh, TAG_SOURCE, e["source"])
        action = "baked"
    else:
        opts = u.GeometryScriptCopyMeshToAssetOptions()
        opts.set_editor_property("enable_recompute_normals", False)
        opts.set_editor_property("enable_recompute_tangents", True)
        opts.set_editor_property("replace_materials", False)
        u.GeometryScript_AssetUtils.copy_mesh_to_static_mesh(merged, mesh, opts, u.GeometryScriptMeshWriteLOD(), False)
        action = "rebaked"
    nslots = len(mesh.get_editor_property("static_materials"))
    if nslots < len(e["slots"]):
        raise RuntimeError(f"{path}: {nslots} material slot(s) after the bake, spec has {len(e['slots'])}")
    _set_slots(mesh, e, data)
    meta = {"tris": tris, "base": trunk, "parts": part_info, "baseTris": base_tris, "nodes": len(nodes),
            "trisPerMaterialId": per_id}
    _tag(mesh, "UserFabBake", json.dumps(meta, separators=(",", ":")))
    _tag(mesh, TAG_SPEC, want)
    _save(mesh, path)
    lo, hi = _bounds(mesh)
    return {"name": name, "action": action, "path": path, "boundsMin": lo, "boundsMax": hi, "tris": tris, "base": trunk,
            "parts": part_info, "nodes": len(nodes), "baseTris": base_tris, "trisPerMaterialId": per_id, "slots": nslots,
            "problems": []}


FORBIDDEN_DEPS = ("/ProceduralVegetationEditor/", "/Script/ProceduralVegetation", "/Script/DynamicWind",
                  "/Script/GeometryScripting", "/GeometryScripting/", "/Script/PCG")


def dependency_audit(path: str, depth: int = 8) -> dict:
    """Recursive package dependencies of a derived asset: the packs it pulls into the cook and any plugin package the
    runtime would need (FORBIDDEN_DEPS must stay empty - no new plugin)."""
    ar = u.AssetRegistryHelpers.get_asset_registry()
    opts = u.AssetRegistryDependencyOptions(True, True, True, True, True)
    seen, todo = set(), [path]
    while todo and depth >= 0:
        nxt = []
        for pk in todo:
            for d in ar.get_dependencies(pk, opts) or []:
                d = str(d)
                if d not in seen:
                    seen.add(d)
                    nxt.append(d)
        todo, depth = nxt, depth - 1
    roots = sorted({x.split("/")[2] if x.startswith("/Game/") else x.split("/")[1] for x in seen if x.count("/") >= 2})
    return {"packages": len(seen), "roots": roots,
            "forbidden": sorted(x for x in seen if any(x.startswith(f) for f in FORBIDDEN_DEPS))}


def run_ue(args) -> int:
    data = load_spec(Path(args.spec))
    errors = validate_spec(data)
    names = [n for n in (args.names or "").split(",") if n] or None
    report = {"schema": "unmatched.env-user-fab-import/1", "tool": TOOL_VERSION, "spec": str(args.spec),
              "materials": [], "meshes": [], "errors": list(errors),
              "geometryScript": hasattr(u, "GeometryScript_AssetUtils")}
    if not errors and not report["geometryScript"]:
        report["errors"].append("GeometryScripting is not mounted: run with -EnablePlugins=GeometryScripting")
    if not report["errors"]:
        mats = data["materials"]
        meshes = {n: e for n, e in data["meshes"].items() if not names or n in names}
        need = {s["material"] for e in meshes.values() for s in e["slots"]}
        masters = sorted({mats[k]["parent"] for k in need if mats[k]["parent"] in mats})
        for key in masters:
            try:
                report["materials"].append(ensure_master(key, mats[key]))
            except Exception as ex:  # noqa: BLE001 - reported per asset
                report["errors"].append(f"master {key}: {ex}")
        for key in sorted(need):
            try:
                report["materials"].append(ensure_instance(key, mats[key], data))
            except Exception as ex:  # noqa: BLE001
                report["errors"].append(f"instance {key}: {ex}")
        for name, e in sorted(meshes.items()):
            try:
                r = ensure_bake(name, e, data) if e["kind"] == "bake" else ensure_duplicate(name, e, data)
                ms = e.get("measured")
                if ms and r.get("tris"):
                    for i in range(3):
                        size = max(ms["bboxMax"][i] - ms["bboxMin"][i], 1.0)
                        tol = max(BOUNDS_TOL * size, 0.5)
                        if abs(r["boundsMin"][i] - ms["bboxMin"][i]) > tol or abs(r["boundsMax"][i] - ms["bboxMax"][i]) > tol:
                            r["drift"] = f"bounds differ from the spec's measured block (axis {'xyz'[i]}) - --adopt-report"
                r["deps"] = dependency_audit(e["dest"])
                if r["deps"]["forbidden"]:
                    report["errors"].append(f"mesh {name}: depends on plugin packages {r['deps']['forbidden'][:4]}")
                report["meshes"].append(r)
            except Exception as ex:  # noqa: BLE001
                report["errors"].append(f"mesh {name}: {ex}")
    ok = not report["errors"]
    print("USERFAB-IMPORT-REPORT " + json.dumps(report, ensure_ascii=False))
    out = Path(args.report) if args.report else Path(u.Paths.project_saved_dir()) / "EnvKit/ue-import-user-fab-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"USERFAB-IMPORT-RESULT {'ok' if ok else 'failed'}")
    return 0 if ok else 1


def parse(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true", help="plain Python pre-check (no UE)")
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--layouts", default=str(LAYOUTS))
    ap.add_argument("--require-packs", action="store_true", help="--check: missing pack sources are errors")
    ap.add_argument("--adopt-report", default=None, help="plain Python: copy measured values of a UE report into the spec")
    ap.add_argument("--names", default=None, help="UE: only these meshes (comma list) and their materials")
    ap.add_argument("--report", default=None)
    args, _ = ap.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    if args.adopt_report:
        return adopt_report(args)
    if args.check or u is None:
        return run_check(args)
    return run_ue(args)


if __name__ == "__main__":
    sys.exit(main())
