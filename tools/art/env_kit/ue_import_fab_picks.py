"""ENV-MAPS P5c track F: duplicate the picked AI-allowed Fab meshes into /Game/EnvKit/Fab/ with night materials.

Source of truth: art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/fab-picks.json
(schema unmatched.env-fab-picks/1: 'meshes' = pack mesh -> /Game/EnvKit/Fab/<Map>/SM_EnvFab_<Name> with its pack bounds,
LOD0 triangles and material slots; 'materials' = the night materials). The layouts reference only the duplicates
(art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/p5c_layout_props.py, tools/art/env_kit/layout_check.py
check 11). Licences / packs: docs/art-pipeline/CREDITS-fab.md (Fab Standard 'Personal'; ENV-U13 local use only).

What the UE run does (never inside a pack folder - every write path must start with /Game/EnvKit/Fab/; the packs are
only loaded, never saved):
  wrap      /Game/EnvKit/Fab/Shared/M_EnvFab_<X>: EditorAssetLibrary.duplicate_asset of a pack material that has no colour
            parameter (StylizedForest leaves / bush, Flowers_Pots M_jug1); its BaseColor input gets one Custom node
            'EnvFabNight' (HLSL_NIGHT: lerp(luma, rgb, NightSaturation) x NightValue; scalar parameters NightValue /
            NightSaturation, defaults 1 = the pack look), then 'EnvFabNightTint' (x vector parameter NightTint, default
            (1, 1, 1); P5c tune: the hue term for the sakura under the warm lamps). A material with 'use material attributes' is not wrapped
            (reported; its night MI then only gets the parameters the pack material has).
  instance  MI_EnvFab_<X> (MaterialInstanceConstant): parent = a wrap above or a pack MI / material; the scalar / vector
            parameters of the pick (night muting, wind 0, Fantasy_Forest position hue off, wet rock); 'twoSided' sets
            the base property override TwoSided (the one-sided vine cards).
  mesh      SM_EnvFab_<Name>: EditorAssetLibrary.duplicate_asset of the pack mesh (geometry, LODs, pivot unchanged); every
            slot with a 'night' material gets that MI (matched by slot name), trunk / bark slots keep the pack material.
            After the run the bounds are compared with the pick's bboxMin / bboxMax (1 % / 0.5 uu) and the LOD0 triangles
            with 'tris'.
Idempotent: every asset carries the metadata tag EnvFabSpec = sha256 of its pick entry (+ tool version); an asset whose
tag matches is left alone, otherwise only the differing properties are written (a wrap is never rebuilt from scratch:
an existing 'EnvFabNight' node is kept; a wrap of envfab-1 only gets the tint node). An asset at a target path that this tool did not create (no EnvFabSource tag /
another source) is reported and not overwritten. The DefaultGame.ini cook of /Game/EnvKit follows the hard references of
the duplicates into the pack folders (no pack folder is added to the cook).

Report: 'ENVFAB-IMPORT-REPORT {json}', 'ENVFAB-IMPORT-RESULT ok|failed', written to <project>/Saved/EnvKit/
ue-import-fab-report.json (or --report).

Run (the editor must be CLOSED - UnrealEditor-Cmd holds the project; GPU lock not needed: -nullrhi):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/env_kit/ue_import_fab_picks.py" -unattended -nosplash -nullrhi
Pre-check without UE (plain Python: the pick file, the pack sources on disk, the layouts' Fab references, the scout
catalog when present):
  python -B tools/art/env_kit/ue_import_fab_picks.py --check [--layouts DIR] [--catalog FILE] [--require-packs]
Options (UE): --names SakuraTwisted,OakDark  --picks <json>  --report <json>  --dry-run (plan only)

Status: предложено - technically imported only after the integrate stage ran this script and the trace lines of
S08EnvLayout show the meshes; художественная приёмка - решение пользователя.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only; --check runs in plain Python
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PICKS = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/fab-picks.json"
P5C_SCRIPT = PICKS.parent / "p5c_layout_props.py"
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
CONTENT = REPO / "unreal/Unmatched/Content"
SCOUT_CATALOG = Path("C:/tmp/envmaps-research/p5c/scout/catalog.json")
SCHEMA = "unmatched.env-fab-picks/1"
TOOL_VERSION = "envfab-2"  # envfab-2 (P5c tune): NightTint after EnvFabNight
FAB_ROOT = "/Game/EnvKit/Fab/"
MAPS = ("Marmoreal", "Sarpedon")
DEST_MESH_RE = re.compile(r"^/Game/EnvKit/Fab/(Marmoreal|Sarpedon)/SM_EnvFab_([A-Za-z0-9]+)$")
DEST_MAT_RE = re.compile(r"^/Game/EnvKit/Fab/(Marmoreal|Sarpedon|Shared)/(M|MI)_EnvFab_([A-Za-z0-9]+)$")
PACKAGE_RE = re.compile(r"^/Game/[A-Za-z0-9_]+(/[A-Za-z0-9_ .-]+)+$")
NOAI_ROOTS = ("Megaplant_Library", "StyleHex_Studio")  # ENV-U14: never here (the user's variant overlay only)
TAG_SPEC = "EnvFabSpec"
TAG_SOURCE = "EnvFabSource"
NIGHT_NODE = "EnvFabNight"
# BaseColor -> lerp(luma, rgb, Sat) x Val (Rec. 709 luma of the linear colour; Sat = Val = 1 is the identity)
HLSL_NIGHT = ("float l = dot(C, float3(0.2126, 0.7152, 0.0722));\n"
              "return lerp(float3(l, l, l), C, Sat) * Val;\n")
NIGHT_PINS = ("C", "Sat", "Val")
# P5c tune: a colour multiply after EnvFabNight (vector parameter NightTint, default (1, 1, 1) = identity) - the pack
# pink leaves read salmon / orange under the warm lamps of Marmoreal and no hue term existed. A separate Custom node, so
# a wrap built by tool version envfab-1 is upgraded in place (EnvFabNight kept, the tint node inserted after it).
TINT_NODE = "EnvFabNightTint"
HLSL_TINT = "return C * Tint.rgb;\n"
TINT_PINS = ("C", "Tint")
BOUNDS_TOL = 0.01  # of the size per axis (and >= 0.5 uu)


# ------------------------------------------------------------------------------------------------ pick file
def load_picks(path: Path = PICKS) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pack_of(path: str) -> str:
    parts = path.split("/")
    return parts[2] if len(parts) > 2 and parts[1] == "Game" else ""


def spec_sha(entry: dict) -> str:
    """sha256 of one pick entry (sorted JSON) + the tool version: the EnvFabSpec metadata tag."""
    return hashlib.sha256((TOOL_VERSION + json.dumps(entry, sort_keys=True)).encode("utf-8")).hexdigest()


def material_path(data: dict, ref: str) -> str:
    """A material reference of the pick file: a key of 'materials' (-> its dest) or a package path."""
    return data["materials"][ref]["dest"] if ref in data.get("materials", {}) else ref


def validate_picks(data: dict) -> list[str]:
    """Structure, paths, packs (AI-allowed only, no NoAI), references - the rules the UE run relies on."""
    err = []
    if data.get("schema") != SCHEMA:
        err.append(f"schema {data.get('schema')!r} != {SCHEMA}")
    allowed = set(data.get("aiAllowedPacks", []))
    if allowed & set(NOAI_ROOTS):
        err.append(f"aiAllowedPacks lists a NoAI pack {sorted(allowed & set(NOAI_ROOTS))}")
    mats, meshes = data.get("materials", {}), data.get("meshes", {})
    if not isinstance(mats, dict) or not isinstance(meshes, dict) or not meshes:
        return err + ["materials / meshes missing"]

    def source_ok(tag: str, path: str) -> None:
        pk = pack_of(path)
        if pk in NOAI_ROOTS:
            err.append(f"{tag}: {path} is a NoAI pack asset (ENV-U14: UserVariant overlay only)")
        elif pk not in allowed:
            err.append(f"{tag}: {path} is not in an AI-allowed pack {sorted(allowed)}")
        elif not PACKAGE_RE.match(path):
            err.append(f"{tag}: {path!r} is not a package path")

    dests = set()
    for key, m in mats.items():
        tag = f"material {key}"
        dest = m.get("dest", "")
        mm = DEST_MAT_RE.match(dest)
        if not mm or dest.rsplit("/", 1)[-1] != key:
            err.append(f"{tag}: dest {dest!r} is not /Game/EnvKit/Fab/<Map|Shared>/{key}")
        if dest in dests:
            err.append(f"{tag}: dest {dest} used twice")
        dests.add(dest)
        kind = m.get("kind")
        if kind == "wrap":
            if not key.startswith("M_EnvFab_"):
                err.append(f"{tag}: a wrap is a material M_EnvFab_*")
            source_ok(tag, m.get("source", ""))
        elif kind == "instance":
            if not key.startswith("MI_EnvFab_"):
                err.append(f"{tag}: an instance is MI_EnvFab_*")
            parent = m.get("parent", "")
            if parent in mats:
                if mats[parent].get("kind") != "wrap":
                    err.append(f"{tag}: parent {parent} is not a wrap")
            else:
                source_ok(tag, parent)
            for k, v in m.get("scalar", {}).items():
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    err.append(f"{tag}: scalar {k} is not a number")
            for k, v in m.get("vector", {}).items():
                if not (isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) for x in v)):
                    err.append(f"{tag}: vector {k} is not [r, g, b, a]")
            if "twoSided" in m and not isinstance(m["twoSided"], bool):
                err.append(f"{tag}: twoSided is not a bool")
        else:
            err.append(f"{tag}: kind {kind!r} is not wrap / instance")
    used = set()
    for name, e in meshes.items():
        tag = f"mesh {name}"
        dm = DEST_MESH_RE.match(e.get("dest", ""))
        if not dm or dm.group(2) != name or dm.group(1) != e.get("map"):
            err.append(f"{tag}: dest {e.get('dest')!r} is not /Game/EnvKit/Fab/{e.get('map')}/SM_EnvFab_{name}")
        if e.get("dest") in dests:
            err.append(f"{tag}: dest {e.get('dest')} used twice")
        dests.add(e.get("dest"))
        source_ok(tag, e.get("source", ""))
        if e.get("pack") != pack_of(e.get("source", "")):
            err.append(f"{tag}: pack {e.get('pack')!r} != the source's folder {pack_of(e.get('source', ''))!r}")
        lo, hi = e.get("bboxMin"), e.get("bboxMax")
        if not (isinstance(lo, list) and isinstance(hi, list) and len(lo) == len(hi) == 3
                and all(b >= a for a, b in zip(lo, hi))):
            err.append(f"{tag}: bboxMin / bboxMax")
        if not (isinstance(e.get("tris"), int) and e["tris"] > 0):
            err.append(f"{tag}: tris")
        sr = e.get("scaleRange")
        if not (isinstance(sr, list) and len(sr) == 2 and 0 < sr[0] < sr[1] <= 3.0):
            err.append(f"{tag}: scaleRange")
        if e.get("base") is not None and not (isinstance(e["base"], list) and len(e["base"]) == 4
                                              and e["base"][0] < e["base"][2] and e["base"][1] < e["base"][3]):
            err.append(f"{tag}: base must be [x0, y0, x1, y1] or null")
        slots = e.get("slots", [])
        if not slots:
            err.append(f"{tag}: no slots")
        if len({s.get("slot") for s in slots}) != len(slots):
            err.append(f"{tag}: duplicate slot names")
        for s in slots:
            source_ok(f"{tag} slot {s.get('slot')}", s.get("source", ""))
            night = s.get("night")
            if night is None:
                continue
            used.add(night)
            if night not in mats or mats[night].get("kind") != "instance":
                err.append(f"{tag} slot {s.get('slot')}: night {night!r} is not an instance of 'materials'")
                continue
            # the night MI must descend from the slot's own pack material (directly or through its wrap)
            parent = mats[night]["parent"]
            root = mats[parent]["source"] if parent in mats else parent
            if root != s.get("source"):
                err.append(f"{tag} slot {s.get('slot')}: night {night} descends from {root}, not {s.get('source')}")
    unused = {k for k, m in mats.items() if m.get("kind") == "instance"} - used
    if unused:
        err.append(f"night instances used by no slot: {sorted(unused)}")
    wraps_used = {mats[k]["parent"] for k in used if k in mats}
    for k, m in mats.items():
        if m.get("kind") == "wrap" and k not in wraps_used:
            err.append(f"wrap {k} is the parent of no night instance")
    return err


def content_file(path: str) -> Path:
    """The .uasset of a /Game/ package in this checkout's Content folder."""
    return CONTENT / (path[len("/Game/"):] + ".uasset")


def check_sources_on_disk(data: dict) -> tuple[list[str], int]:
    """Every pack source (mesh, slot material, wrap source, MI parent) as a .uasset file (existence only - nothing is
    opened); returns (missing, found)."""
    paths = set()
    for e in data["meshes"].values():
        paths.add(e["source"])
        paths.update(s["source"] for s in e["slots"])
    for m in data["materials"].values():
        if m["kind"] == "wrap":
            paths.add(m["source"])
        elif m["parent"] not in data["materials"]:
            paths.add(m["parent"])
    missing = sorted(p for p in paths if not content_file(p).is_file())
    return missing, len(paths) - len(missing)


def check_catalog(data: dict, catalog: Path) -> list[str]:
    """The pick entries against the scout's UE 5.8 inventory (bounds 0.01 uu, LOD0 triangles, slot order / sources)."""
    cat = json.loads(Path(catalog).read_text(encoding="utf-8"))
    sm = {}
    for p in cat.get("packs", {}).values():
        for s in p.get("staticMeshes", []):
            sm[s["path"].split(".")[0]] = s
    err = []
    for name, e in data["meshes"].items():
        s = sm.get(e["source"])
        if s is None:
            err.append(f"mesh {name}: {e['source']} not in the scout catalog")
            continue
        for k in ("bboxMin", "bboxMax"):
            if any(abs(a - b) > 0.01 for a, b in zip(e[k], s[k])):
                err.append(f"mesh {name}: {k} {e[k]} != catalog {s[k]}")
        if e["tris"] != s["trisLOD0"]:
            err.append(f"mesh {name}: tris {e['tris']} != catalog {s['trisLOD0']}")
        got = [(m["slot"], m["path"].split(".")[0]) for m in s["materials"]]
        want = [(x["slot"], x["source"]) for x in sorted(e["slots"], key=lambda x: x["index"])]
        if got != want:
            err.append(f"mesh {name}: slots {want} != catalog {got}")
    return err


def layout_refs(layouts: dict) -> list[tuple[str, str, str]]:
    """(map, prop id, mesh) of every Fab / pack mesh a layout references."""
    out = []
    for key, lay in layouts.items():
        for p in lay.get("props", []):
            mesh = p.get("mesh", "")
            if mesh.startswith(FAB_ROOT) or pack_of(mesh) not in ("", "EnvKit"):
                out.append((key, p.get("id", "?"), mesh))
    return out


def check_layout_refs(data: dict, layouts: dict) -> list[str]:
    planned = {e["dest"]: e for e in data["meshes"].values()}
    err = []
    for key, pid, mesh in layout_refs(layouts):
        if pack_of(mesh) in NOAI_ROOTS:
            err.append(f"{key} {pid}: NoAI pack mesh {mesh} in the main layout (ENV-U14)")
        elif not mesh.startswith(FAB_ROOT):
            err.append(f"{key} {pid}: pack mesh {mesh} placed directly - use its /Game/EnvKit/Fab duplicate")
        elif mesh not in planned:
            err.append(f"{key} {pid}: {mesh} is not a planned duplicate of {PICKS.name}")
        elif planned[mesh]["map"].lower() != key:
            err.append(f"{key} {pid}: {mesh} belongs to the {planned[mesh]['map']} folder")
    return err


def main_layouts(layout_dir: Path) -> dict:
    """The two main layouts (<map>.layout.json; never the variant overlays <map>.<name>.layout.json)."""
    out = {}
    for key in ("marmoreal", "sarpedon"):
        f = Path(layout_dir) / f"{key}.layout.json"
        if f.is_file():
            out[key] = json.loads(f.read_text(encoding="utf-8"))
    return out


def p5c_layouts(layouts: dict) -> dict:
    """The layouts after p5c_layout_props.apply (in memory) - checks the references before the integrate stage writes
    them."""
    if not P5C_SCRIPT.is_file():
        return {}
    import importlib.util
    spec = importlib.util.spec_from_file_location("p5c_layout_props", P5C_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {k: mod.apply(k, lay) for k, lay in layouts.items()}


def plan(data: dict, names: list[str] | None = None) -> dict:
    """Ordered UE work: the wraps, the instances (parents first), the meshes (selected by --names: their materials)."""
    meshes = {n: e for n, e in data["meshes"].items() if not names or n in names}
    need = {s["night"] for e in meshes.values() for s in e["slots"] if s.get("night")}
    mats = data["materials"]
    wraps = sorted({mats[k]["parent"] for k in need if mats[k]["parent"] in mats})
    return {"wraps": [(k, mats[k]) for k in wraps], "instances": [(k, mats[k]) for k in sorted(need)],
            "meshes": sorted(meshes.items())}


def run_check(args) -> int:
    data = load_picks(Path(args.picks))
    errors = validate_picks(data)
    warnings = []
    missing, found = check_sources_on_disk(data)
    if missing:
        (errors if args.require_packs else warnings).append(
            f"{len(missing)} pack sources missing in {CONTENT.as_posix()} (gitignored packs; the orchestrator copies "
            f"them): {missing[:6]}{' ...' if len(missing) > 6 else ''}")
    catalog = Path(args.catalog) if args.catalog else SCOUT_CATALOG
    if catalog.is_file():
        errors += check_catalog(data, catalog)
    else:
        warnings.append(f"scout catalog {catalog} absent - bounds / tris not cross-checked")
    lays = main_layouts(Path(args.layouts))
    errors += check_layout_refs(data, lays)
    after = p5c_layouts(lays)
    errors += [f"after p5c_layout_props: {e}" for e in check_layout_refs(data, after)]
    p = plan(data)
    used = {p_["mesh"] for lay in after.values() for p_ in lay.get("props", []) if p_.get("mesh", "").startswith(FAB_ROOT)}
    unused = sorted(e["dest"] for e in data["meshes"].values() if e["dest"] not in used)
    if unused:
        warnings.append(f"planned duplicates no layout places: {unused}")
    report = {"schema": "unmatched.env-fab-check/1", "picks": PICKS.relative_to(REPO).as_posix(),
              "wraps": len(p["wraps"]), "instances": len(p["instances"]), "meshes": len(p["meshes"]),
              "packSourcesFound": found, "packSourcesMissing": len(missing),
              "fabRefs": {k: sum(1 for x in layout_refs({k: v})) for k, v in after.items()},
              "errors": errors, "warnings": warnings}
    print("ENVFAB-CHECK " + json.dumps(report, ensure_ascii=False))
    for w in warnings:
        print("  WARN  " + w)
    for e in errors:
        print("  ERROR " + e)
    print(f"ENVFAB-CHECK {'ok' if not errors else 'failed'}")
    return 0 if not errors else 1


# ------------------------------------------------------------------------------------------------ UE side
def _guard(path: str) -> None:
    if not path.startswith(FAB_ROOT):
        raise RuntimeError(f"refusing to write {path}: only {FAB_ROOT}* is written (the pack folders stay pristine)")


def _tag(asset, key: str, value: str) -> None:
    u.EditorAssetLibrary.set_metadata_tag(asset, key, value)


def _save(asset, path: str) -> None:
    _guard(path)
    if not u.EditorAssetLibrary.save_loaded_asset(asset, False):
        raise RuntimeError(f"could not save {path}")


def _duplicate(source: str, dest: str):
    """dest (a fresh duplicate of source, tagged EnvFabSource) or the existing dest when it is ours."""
    eal = u.EditorAssetLibrary
    _guard(dest)
    if eal.does_asset_exist(dest):
        asset = u.load_asset(dest)
        if eal.get_metadata_tag(asset, TAG_SOURCE) != source:
            raise RuntimeError(f"{dest} exists but was not duplicated from {source} by this tool - not overwritten")
        return asset, "existing"
    if not eal.does_asset_exist(source):
        raise RuntimeError(f"source {source} missing (pack not in this checkout's Content?)")
    asset = eal.duplicate_asset(source, dest)
    if asset is None:
        raise RuntimeError(f"could not duplicate {source} -> {dest}")
    _tag(asset, TAG_SOURCE, source)
    return asset, "duplicated"


def _insert_tint(mat, night, dest: str) -> None:
    """BaseColor <- EnvFabNightTint(C = the EnvFabNight node, Tint = vector parameter NightTint, default (1, 1, 1))."""
    mel = u.MaterialEditingLibrary
    tint = mel.create_material_expression(mat, u.MaterialExpressionCustom, -200, -200)
    tint.set_editor_property("description", TINT_NODE)
    tint.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT3)
    pins = []
    for pin in TINT_PINS:
        ci = u.CustomInput()
        ci.set_editor_property("input_name", pin)
        pins.append(ci)
    tint.set_editor_property("inputs", pins)
    tint.set_editor_property("code", HLSL_TINT)
    vp = mel.create_material_expression(mat, u.MaterialExpressionVectorParameter, -700, 0)
    vp.set_editor_property("parameter_name", "NightTint")
    vp.set_editor_property("default_value", u.LinearColor(1.0, 1.0, 1.0, 1.0))
    for src, pin in ((night, "C"), (vp, "Tint")):
        if not mel.connect_material_expressions(src, "", tint, pin):
            raise RuntimeError(f"{dest}: could not connect {src.get_name()} -> {TINT_NODE}.{pin}")
    if not mel.connect_material_property(tint, "", u.MaterialProperty.MP_BASE_COLOR):
        raise RuntimeError(f"{dest}: could not connect {TINT_NODE} -> BaseColor")


def ensure_wrap(key: str, m: dict) -> dict:
    mel = u.MaterialEditingLibrary
    mat, action = _duplicate(m["source"], m["dest"])
    want = spec_sha(m)
    if action == "existing" and u.EditorAssetLibrary.get_metadata_tag(mat, TAG_SPEC) == want:
        return {"key": key, "action": "unchanged", "path": m["dest"]}
    if mat.get_editor_property("use_material_attributes"):
        _tag(mat, TAG_SPEC, want)
        _save(mat, m["dest"])
        return {"key": key, "action": "copied-unwrapped", "path": m["dest"],
                "warning": "material attributes: no BaseColor input to wrap - the night MI gets no NightValue"}
    prop = u.MaterialProperty.MP_BASE_COLOR
    node = mel.get_material_property_input_node(mat, prop)
    if node is not None and isinstance(node, u.MaterialExpressionCustom) and \
            str(node.get_editor_property("description")) == TINT_NODE:
        wrapped = "kept"
    elif node is not None and isinstance(node, u.MaterialExpressionCustom) and \
            str(node.get_editor_property("description")) == NIGHT_NODE:
        _insert_tint(mat, node, m["dest"])
        wrapped = "tint-inserted"
    else:
        out_name = ""
        if hasattr(mel, "get_material_property_input_node_output_name"):
            out_name = str(mel.get_material_property_input_node_output_name(mat, prop) or "")
        custom = mel.create_material_expression(mat, u.MaterialExpressionCustom, -400, -200)
        custom.set_editor_property("description", NIGHT_NODE)
        custom.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT3)
        pins = []
        for pin in NIGHT_PINS:
            ci = u.CustomInput()
            ci.set_editor_property("input_name", pin)
            pins.append(ci)
        custom.set_editor_property("inputs", pins)
        custom.set_editor_property("code", HLSL_NIGHT)
        params = {}
        for i, (pname, pin) in enumerate((("NightSaturation", "Sat"), ("NightValue", "Val"))):
            sp = mel.create_material_expression(mat, u.MaterialExpressionScalarParameter, -700, -120 + 80 * i)
            sp.set_editor_property("parameter_name", pname)
            sp.set_editor_property("default_value", 1.0)
            params[pin] = sp
        if node is None:  # an unconnected BaseColor (= 0): nothing to mute - the wrap keeps the zero constant
            const = mel.create_material_expression(mat, u.MaterialExpressionConstant3Vector, -700, -260)
            const.set_editor_property("constant", u.LinearColor(0.0, 0.0, 0.0, 1.0))
            node, out_name = const, ""
        for src, out, pin in ((node, out_name, "C"), (params["Sat"], "", "Sat"), (params["Val"], "", "Val")):
            if not mel.connect_material_expressions(src, out, custom, pin):
                raise RuntimeError(f"{m['dest']}: could not connect {src.get_name()}.{out or '<0>'} -> {pin}")
        _insert_tint(mat, custom, m["dest"])
        wrapped = "inserted"
    mel.recompile_material(mat)
    scal = {str(n) for n in mel.get_scalar_parameter_names(mat)}
    if not {"NightValue", "NightSaturation"} <= scal:
        raise RuntimeError(f"{m['dest']}: NightValue / NightSaturation missing after the wrap ({sorted(scal)})")
    if "NightTint" not in {str(n) for n in mel.get_vector_parameter_names(mat)}:
        raise RuntimeError(f"{m['dest']}: NightTint missing after the wrap")
    _tag(mat, TAG_SPEC, want)
    _save(mat, m["dest"])
    return {"key": key, "action": action, "node": wrapped, "path": m["dest"]}


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
    elif eal.get_metadata_tag(mi, TAG_SOURCE) != parent_path:
        raise RuntimeError(f"{path} exists but was not created by this tool for {parent_path} - not overwritten")
    want_sha = spec_sha(m)
    if action == "updated" and eal.get_metadata_tag(mi, TAG_SPEC) == want_sha:
        return {"key": key, "action": "unchanged", "path": path}
    have_s = {str(n) for n in mel.get_scalar_parameter_names(parent)}
    have_v = {str(n) for n in mel.get_vector_parameter_names(parent)}
    skipped = [k for k in m.get("scalar", {}) if k not in have_s] + [k for k in m.get("vector", {}) if k not in have_v]
    mel.set_material_instance_parent(mi, parent)
    for k, v in m.get("scalar", {}).items():
        if k in have_s:
            mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, v in m.get("vector", {}).items():
        if k in have_v:
            mel.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(*[float(x) for x in v]))
    if "twoSided" in m:
        ov = mi.get_editor_property("base_property_overrides")
        ov.set_editor_property("override_two_sided", True)
        ov.set_editor_property("two_sided", bool(m["twoSided"]))
        mi.set_editor_property("base_property_overrides", ov)
    mel.update_material_instance(mi)
    _tag(mi, TAG_SPEC, want_sha)
    _save(mi, path)
    out = {"key": key, "action": action, "path": path, "parent": parent_path}
    if skipped:
        out["warning"] = f"parameters not on the parent (not set): {skipped}"
    return out


def ensure_mesh(name: str, e: dict, data: dict, smes) -> dict:
    eal = u.EditorAssetLibrary
    mesh, action = _duplicate(e["source"], e["dest"])
    want_sha = spec_sha(e)
    changed = []
    slots = list(mesh.get_editor_property("static_materials"))
    by_name = {str(s.get_editor_property("material_slot_name")): i for i, s in enumerate(slots)}
    for s in e["slots"]:
        idx = by_name.get(s["slot"])
        if idx is None:
            raise RuntimeError(f"{e['dest']}: slot {s['slot']!r} missing (slots {sorted(by_name)})")
        target = material_path(data, s["night"]) if s.get("night") else s["source"]
        mat = u.load_asset(target)
        if mat is None:
            raise RuntimeError(f"{e['dest']}: material {target} missing")
        cur = slots[idx].get_editor_property("material_interface")
        if cur is None or cur.get_path_name().split(".")[0] != target:
            mesh.set_material(idx, mat)
            changed.append(s["slot"])
    if changed or eal.get_metadata_tag(mesh, TAG_SPEC) != want_sha:
        _tag(mesh, TAG_SPEC, want_sha)
        _save(mesh, e["dest"])
    bb = mesh.get_bounding_box()
    got_min = [round(bb.min.x, 2), round(bb.min.y, 2), round(bb.min.z, 2)]
    got_max = [round(bb.max.x, 2), round(bb.max.y, 2), round(bb.max.z, 2)]
    bad = []
    for i in range(3):
        size = max(e["bboxMax"][i] - e["bboxMin"][i], 1.0)
        tol = max(BOUNDS_TOL * size, 0.5)
        if abs(got_min[i] - e["bboxMin"][i]) > tol or abs(got_max[i] - e["bboxMax"][i]) > tol:
            bad.append(f"axis {'xyz'[i]}: {got_min[i]}..{got_max[i]} vs {e['bboxMin'][i]}..{e['bboxMax'][i]}")
    tris = None
    for get in (lambda: smes.get_number_triangles(mesh, 0), lambda: mesh.get_num_triangles(0)):
        try:
            tris = int(get())
            break
        except Exception:  # noqa: BLE001 - engine API differences (no subsystem / method): next route, else unknown
            continue
    if tris is not None and tris != e["tris"]:
        bad.append(f"tris {tris} != {e['tris']}")
    return {"name": name, "action": action, "path": e["dest"], "slotsSet": changed, "boundsMin": got_min,
            "boundsMax": got_max, "tris": tris, "problems": bad}


def run_ue(args) -> int:
    data = load_picks(Path(args.picks))
    errors = validate_picks(data)
    names = [n for n in (args.names or "").split(",") if n] or None
    report = {"schema": "unmatched.env-fab-import/1", "tool": TOOL_VERSION, "picks": str(args.picks),
              "wraps": [], "instances": [], "meshes": [], "errors": list(errors)}
    if not errors:
        p = plan(data, names)
        if args.dry_run:
            report["plan"] = {k: [x[0] for x in v] for k, v in p.items()}
        else:
            try:
                u.load_module("StaticMeshEditor") if hasattr(u, "load_module") else None
            except Exception:  # noqa: BLE001 - optional
                pass
            try:
                smes = u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
            except Exception:  # noqa: BLE001
                smes = None
            for key, m in p["wraps"]:
                try:
                    report["wraps"].append(ensure_wrap(key, m))
                except Exception as ex:  # noqa: BLE001 - reported per asset
                    report["errors"].append(f"wrap {key}: {ex}")
            for key, m in p["instances"]:
                try:
                    report["instances"].append(ensure_instance(key, m, data))
                except Exception as ex:  # noqa: BLE001
                    report["errors"].append(f"instance {key}: {ex}")
            for name, e in p["meshes"]:
                try:
                    r = ensure_mesh(name, e, data, smes)
                    report["meshes"].append(r)
                    report["errors"] += [f"mesh {name}: {x}" for x in r["problems"]]
                except Exception as ex:  # noqa: BLE001
                    report["errors"].append(f"mesh {name}: {ex}")
    ok = not report["errors"]
    text = json.dumps(report, ensure_ascii=False)
    print("ENVFAB-IMPORT-REPORT " + text)
    out = Path(args.report) if args.report else Path(u.Paths.project_saved_dir()) / "EnvKit/ue-import-fab-report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"ENVFAB-IMPORT-RESULT {'ok' if ok else 'failed'}")
    return 0 if ok else 1


def parse(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true", help="plain Python pre-check (no UE)")
    ap.add_argument("--picks", default=str(PICKS))
    ap.add_argument("--layouts", default=str(LAYOUTS))
    ap.add_argument("--catalog", default=None, help=f"scout catalog (default {SCOUT_CATALOG} when present)")
    ap.add_argument("--require-packs", action="store_true", help="--check: missing pack sources are errors")
    ap.add_argument("--names", default=None, help="UE: only these picks (comma list) and their materials")
    ap.add_argument("--report", default=None)
    ap.add_argument("--dry-run", action="store_true", help="UE: plan only")
    args, _ = ap.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    if args.check or u is None:
        return run_check(args)
    return run_ue(args)


if __name__ == "__main__":
    sys.exit(main())
