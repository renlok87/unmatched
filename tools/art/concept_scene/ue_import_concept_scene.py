"""ENV-MAPS P8 track B (docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md section 4 P8.2 item 4): import the lit 3D island.

Input = the track interface tools/art/concept_scene/manifest.sarpedon.json (written by track A):
  {"schema": "unmatched.concept-scene/1", "map": "sarpedon",
   "meshes": [{"name": "Island", "fbx": "<repo path>", "ue": "/Game/EnvMaps/Sarpedon/Scene/SM_Env_S_Island", "tris": N,
               "castShadow": true, "lumenGI": true,
               "textures": {"BC": "scraped-data/derived/concept-scene/sarpedon/T_Env_S_Island_BC.png", "N": ..., "ORM": ...},
               "sha256": {"<file>": "<hex>"},
               optional: "mi" (an MI path for every slot; default MI_Env_S_<Name>), "slots" ([MI path | null per slot]),
                         "material" ({"masked": bool, "scalars": {...}, "vectors": {...}}: the baked MI's values)}, ...],
   "projected": {"albedo": "scraped-data/derived/concept-scene/sarpedon/T_Env_S_AlbedoC0.png",
                 "ue": "/Game/EnvMaps/Sarpedon/Scene/T_Env_S_AlbedoC0", "rectC0Px": [x, y, w, h], "sha256": "<hex>"},
   optional "looks": [{"name", "masked", "bc", "scalars", "vectors"}] (MI_EnvScene_Proj_<Look>; ue_scene_material.py),
   "layout": "unreal/Unmatched/Config/ArtBoards/EnvLayouts/sarpedon.scene.layout.json"}
  The sha256 may also sit in a top-level "sha256" map (file -> hex); a mesh's own map wins.
Targets (/Game/EnvMaps: cooked by DirectoriesToAlwaysCook; ENV-U3/U7: textures derived from the concept stay out of git,
the UE assets live in the gitignored Content):
  T_Env_S_<Name>_BC   sRGB, BC7, wrap        T_Env_S_<Name>_N    normal map (TC_Normalmap, DirectX green: no flip), wrap
  T_Env_S_<Name>_ORM  linear masks, wrap     T_Env_S_AlbedoC0    the projected plate: sRGB, BC7, clamp
  SM_Env_S_<Name>     FbxFactory (tools/art/env_kit/ue_import_env_kit.import_mesh: no materials, normals imported,
                      scale 1), Nanite off, no collision, every slot -> MI_Env_S_<Name> (or the manifest's "mi" / "slots")
  M_EnvScene / M_EnvScene_Masked / MPC_EnvScene / the MIs: tools/art/concept_scene/ue_scene_material.py (build_all)
Idempotent: every texture / mesh carries the metadata tag EnvMapsSceneSha256 = its source sha256 (equal + settings ok =
left alone; --force re-imports); MIs by their EnvMapsSceneMi tag.

Run (the editor must be CLOSED; never inside a GPU-measurement window):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/concept_scene/ue_import_concept_scene.py [--force]" -unattended -nosplash -nullrhi
Pre-check without UE (plain Python):
  python -B tools/art/concept_scene/ue_import_concept_scene.py --check [--manifest <json>] [--no-files] [--no-git]
      schema, names, UE paths, triangle budgets (<= 40k per mesh, <= 450k instanced by the scene layout), every source
      present with its sha256, FBX <= 15 MB in git, every concept-derived image gitignored (git check-ignore), the scene
      layout overlay (schema, variant, the manifest meshes it places, castShadow / lumenGI vs the profile's lit3d casters /
      giOff, material overrides = planned MIs), the profile's lit3d.required meshes in the manifest
ENV-MAPS P9 track B:
  * "meshesExistingMaterial" entries (no baked textures: the F2 frame band, the F4 cascade, the banner) are validated like
    the meshes (name, ue, fbx + sha256, tris, castShadow / lumenGI when given) and may give one MI per slot ("slots":
    [MI path | bare MI name | null, ...]; one entry = every slot, as before); an MI under /Game/EnvMaps/Sarpedon/Scene must
    be planned by ue_scene_material.mi_plan (the material-route MI_EnvScene_FrameWood / _FrameIron / _FallsSheet /
    _FallsFoam among them);
  * tools/art/concept_scene/fx-plan.sarpedon.json (track B: the layered brazier / fort fire and the cascade mist, merged by
    track A's scene_layout.py): schema, ids, systems = ue_import_fab_fx.FX_PLAN_SYSTEMS, anchors brazier | fort-pit, tiers;
    with the scene overlay present its merge state ('none' before track A merged it, 'all' after; 'partial' or the P8
    NS_Env_ConceptFire still next to the plan = an error).
Derived directory order: the manifest's paths under the worktree, else the main checkout's (the same repo-relative path).
Report 'CONCEPT-SCENE-IMPORT-REPORT {...}' / 'CONCEPT-SCENE-IMPORT-RESULT ok|failed',
<project>/Saved/EnvMaps/concept-scene-import-report.json (or --report). Status: предложено.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
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
sys.path.insert(0, str(HERE))
import ue_scene_material as SM  # noqa: E402

SCHEMA = "unmatched.concept-scene/1"
MAP_KEY = "sarpedon"
MANIFEST = HERE / f"manifest.{MAP_KEY}.json"
UE_DIR = SM.MAP_ROOT
DERIVED_REL = f"scraped-data/derived/concept-scene/{MAP_KEY}"
LAYOUT_REL = f"unreal/Unmatched/Config/ArtBoards/EnvLayouts/{MAP_KEY}.scene.layout.json"
OVERLAY_SCHEMA = "unmatched.env-layout-overlay/1"
SCENE_VARIANT = "scene"
SHA_TAG = "EnvMapsSceneSha256"
MAX_FBX_MB = 15.0
MAX_MESH_TRIS = 40000
MAX_SCENE_TRIS = 450000
TEXTURE_KEYS = ("BC", "N", "ORM")
FX_PLAN = HERE / f"fx-plan.{MAP_KEY}.json"
FX_PLAN_SCHEMA = "unmatched.concept-scene-fx/1"
FX_ANCHORS = ("brazier", "fort-pit")
FX_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
NAME_RE = re.compile(r"[A-Z][A-Za-z0-9]{0,47}")
HEX_RE = re.compile(r"[0-9a-f]{64}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(rel: str, repo: Path = REPO) -> Path:
    """A repo-relative path in the worktree, else in the main checkout (out-of-git sources live there too)."""
    p = repo / rel
    if p.exists() or repo != REPO:
        return p
    alt = MAIN_CHECKOUT / rel
    return alt if alt.exists() else p


def git_ignored(rel: str, repo: Path = REPO) -> bool | None:
    try:
        r = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", "--no-index", rel], capture_output=True)
    except OSError:
        return None
    return {0: True, 1: False}.get(r.returncode)


def git_tracked(rel: str, repo: Path = REPO) -> bool | None:
    try:
        r = subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", rel], capture_output=True)
    except OSError:
        return None
    return r.returncode == 0


def match_patterns(patterns: list[str], ident: str) -> bool:
    """S08ConceptPaste::MatchProps for one id: exact, or "prefix*"."""
    return any(ident.startswith(p[:-1]) if p.endswith("*") else ident == p for p in patterns)


def lit3d_block(profiles_path: Path | None = None) -> dict:
    return SM.sarpedon_block(json.loads((profiles_path or SM.PROFILES).read_text(encoding="utf-8"))).get("lit3d") or {}


def sha_of(manifest: dict, mesh: dict | None, rel: str) -> str | None:
    if mesh is not None and rel in (mesh.get("sha256") or {}):
        return mesh["sha256"][rel]
    return (manifest.get("sha256") or {}).get(rel)


def validate(manifest: dict, repo: Path = REPO, *, check_files: bool = True, check_git: bool = True,
             lit3d: dict | None = None) -> tuple[dict, list[str]]:
    """Plain-Python contract of the manifest (and the scene layout it names). Returns (report, errors)."""
    errors: list[str] = []
    report: dict = {"meshes": {}, "projected": None, "layout": None}
    lit3d = lit3d if lit3d is not None else lit3d_block()
    if manifest.get("schema") != SCHEMA:
        errors.append(f"schema {manifest.get('schema')!r} is not {SCHEMA}")
    if manifest.get("map") != MAP_KEY:
        errors.append(f"map {manifest.get('map')!r} is not {MAP_KEY}")
    meshes = manifest.get("meshes")
    if not isinstance(meshes, list) or not meshes:
        errors.append("meshes must be a non-empty list")
        meshes = []
    files: list[tuple[str, dict | None, str]] = []  # (rel, mesh, kind)
    names = set()
    by_ue: dict[str, dict] = {}
    for i, m in enumerate(meshes):
        if not isinstance(m, dict):
            errors.append(f"meshes[{i}] is not an object")
            continue
        name = m.get("name", "")
        where = f"mesh {name or i}"
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            errors.append(f"{where}: name must be [A-Z][A-Za-z0-9]* (SM_Env_S_<Name>)")
            continue
        if name in names:
            errors.append(f"{where}: duplicate name")
        names.add(name)
        want_ue = f"{UE_DIR}/SM_Env_S_{name}"
        if m.get("ue") != want_ue:
            errors.append(f"{where}: ue {m.get('ue')!r} is not {want_ue}")
        by_ue[want_ue] = m
        tris = m.get("tris")
        if not isinstance(tris, int) or isinstance(tris, bool) or not 0 < tris <= MAX_MESH_TRIS:
            errors.append(f"{where}: tris {tris!r} must be an integer 1..{MAX_MESH_TRIS}")
        for flag in ("castShadow", "lumenGI"):
            if not isinstance(m.get(flag), bool):
                errors.append(f"{where}: {flag} must be a bool")
        fbx = m.get("fbx")
        if not isinstance(fbx, str) or not fbx.lower().endswith(".fbx") or fbx.startswith("/") or ":" in fbx:
            errors.append(f"{where}: fbx {fbx!r} must be a repo-relative .fbx path")
        else:
            files.append((fbx, m, "fbx"))
        tex = m.get("textures")
        if not isinstance(tex, dict) or "BC" not in tex:
            errors.append(f"{where}: textures needs at least BC (the baked albedo atlas)")
            tex = {}
        for key, rel in tex.items():
            want = f"{DERIVED_REL}/T_Env_S_{name}_{key}"
            if key not in TEXTURE_KEYS:
                errors.append(f"{where}: texture key {key} is not BC | N | ORM")
            elif not isinstance(rel, str) or Path(rel).with_suffix("").as_posix() != want or Path(rel).suffix.lower() not in (".png", ".tga"):
                errors.append(f"{where}: textures.{key} {rel!r} must be {want}.png (out of git, ENV-U3/U7)")
            else:
                files.append((rel, m, "texture"))
        if "mi" in m and (not isinstance(m["mi"], str) or not m["mi"].startswith("/Game/EnvMaps/")):
            errors.append(f"{where}: mi {m.get('mi')!r} must be a /Game/EnvMaps MI path")
        if "slots" in m and (not isinstance(m["slots"], list) or not all(s is None or isinstance(s, str) for s in m["slots"])):
            errors.append(f"{where}: slots must be a list of MI paths / null")
        report["meshes"][name] = {"ue": want_ue, "tris": tris, "castShadow": m.get("castShadow"), "lumenGI": m.get("lumenGI"),
                                  "textures": sorted(tex)}
    # P9: meshes that keep an existing / material-route MI (no baked textures)
    planned_mis = {m["path"] for m in SM.mi_plan(manifest)}
    existing_ue: dict[str, dict] = {}
    for i, m in enumerate(manifest.get("meshesExistingMaterial") or []):
        if not isinstance(m, dict):
            errors.append(f"meshesExistingMaterial[{i}] is not an object")
            continue
        name = m.get("name", "")
        where = f"meshesExistingMaterial {name or i}"
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            errors.append(f"{where}: name must be [A-Z][A-Za-z0-9]* (SM_Env_S_<Name>)")
            continue
        if name in names:
            errors.append(f"{where}: duplicate name")
        names.add(name)
        want_ue = f"{UE_DIR}/SM_Env_S_{name}"
        if m.get("ue") != want_ue:
            errors.append(f"{where}: ue {m.get('ue')!r} is not {want_ue}")
        existing_ue[want_ue] = m  # placed-count only: the P8 caster / GI rules stay with the baked meshes
        fbx = m.get("fbx")
        if not isinstance(fbx, str) or not fbx.lower().endswith(".fbx") or fbx.startswith("/") or ":" in fbx:
            errors.append(f"{where}: fbx {fbx!r} must be a repo-relative .fbx path")
        else:
            files.append((fbx, m, "fbx"))
        tris = m.get("tris")
        if tris is not None and (not isinstance(tris, int) or isinstance(tris, bool) or not 0 < tris <= MAX_MESH_TRIS):
            errors.append(f"{where}: tris {tris!r} must be an integer 1..{MAX_MESH_TRIS}")
        for flag in ("castShadow", "lumenGI"):
            if flag in m and not isinstance(m[flag], bool):
                errors.append(f"{where}: {flag} must be a bool")
        slots = m.get("slots")
        if slots is not None and (not isinstance(slots, list) or not all(x is None or isinstance(x, str) for x in slots)):
            errors.append(f"{where}: slots must be a list of MI paths / names / null")
            slots = []
        mis = [x for x in ([m.get("mi")] + list(slots or [])) if x]
        if not mis:
            errors.append(f"{where}: needs 'mi' or slots[0]")
        for mi in mis:
            full = _full_mi(mi)
            if not full.startswith("/Game/"):
                errors.append(f"{where}: MI {mi!r} is not a /Game/ path")
            elif full.startswith(UE_DIR + "/") and full not in planned_mis:
                errors.append(f"{where}: MI {full} is not planned by ue_scene_material.mi_plan")
        report["meshes"][name] = {"ue": want_ue, "tris": tris, "castShadow": m.get("castShadow"), "lumenGI": m.get("lumenGI"),
                                  "mis": [_full_mi(x) for x in mis], "route": "existing-material"}
    proj = manifest.get("projected")
    if not isinstance(proj, dict):
        errors.append("projected must be an object {albedo, ue, rectC0Px, sha256}")
    else:
        want = f"{DERIVED_REL}/T_Env_S_AlbedoC0"
        albedo = proj.get("albedo")
        if not isinstance(albedo, str) or Path(albedo).with_suffix("").as_posix() != want:
            errors.append(f"projected.albedo {albedo!r} must be {want}.png")
        else:
            files.append((albedo, None, "albedo"))
        if proj.get("ue") != f"{UE_DIR}/T_Env_S_AlbedoC0":
            errors.append(f"projected.ue {proj.get('ue')!r} is not {UE_DIR}/T_Env_S_AlbedoC0")
        rect = proj.get("rectC0Px")
        if not (isinstance(rect, list) and len(rect) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in rect)
                and rect[2] > 0 and rect[3] > 0):
            errors.append(f"projected.rectC0Px {rect!r} must be [x, y, w > 0, h > 0] (C0 / concept px)")
        if not isinstance(proj.get("sha256"), str) or not HEX_RE.fullmatch(proj.get("sha256", "")):
            errors.append("projected.sha256 must be 64 lower-case hex")
        report["projected"] = {"ue": proj.get("ue"), "rectC0Px": rect}
    # every source: its sha256 in the manifest, present and equal; FBX in git <= 15 MB; derived images gitignored
    report["files"] = {}
    for rel, mesh, kind in files:
        sha = (manifest.get("projected") or {}).get("sha256") if kind == "albedo" else sha_of(manifest, mesh, rel)
        item = {"kind": kind}
        if not isinstance(sha, str) or not HEX_RE.fullmatch(sha):
            errors.append(f"{rel}: no sha256 in the manifest")
        if check_files:
            path = resolve(rel, repo)
            if not path.is_file():
                errors.append(f"{rel}: source missing")
                item["present"] = False
            else:
                got = sha256_file(path)
                item.update(present=True, sizeMB=round(path.stat().st_size / 1e6, 3), sha256Ok=got == sha)
                if got != sha:
                    errors.append(f"{rel}: sha256 {got} differs from the manifest")
                if kind == "albedo":
                    try:
                        from PIL import Image  # plain Python only
                        with Image.open(path) as img:
                            item["sizePx"] = list(img.size)
                            if img.size[0] % 4 or img.size[1] % 4:
                                item["note"] = "not a multiple of 4: BC7 pads / may fall back in UE"
                    except Exception:  # noqa: BLE001 - Pillow optional for the check
                        pass
        if check_git:
            if kind == "fbx":
                tracked = git_tracked(rel, repo)
                ignored = git_ignored(rel, repo)
                item.update(tracked=tracked, ignored=ignored)
                size = item.get("sizeMB")
                if size is not None and size > MAX_FBX_MB and not ignored:
                    errors.append(f"{rel}: {size} MB > {MAX_FBX_MB} MB must be out of git (gitignored, sha256 in the manifest)")
            else:
                ignored = git_ignored(rel, repo)
                item["ignored"] = ignored
                if ignored is False:
                    errors.append(f"{rel}: a concept-derived image must be gitignored (ENV-U3/U7)")
        report["files"][rel] = item
    # the scene layout overlay
    layout_rel = manifest.get("layout")
    if layout_rel != LAYOUT_REL:
        errors.append(f"layout {layout_rel!r} is not {LAYOUT_REL}")
    layout_path = repo / LAYOUT_REL
    casters = lit3d.get("casters", [])
    gi_off = lit3d.get("giOff", [])
    if layout_path.is_file():
        lay = json.loads(layout_path.read_text(encoding="utf-8"))
        lerr = []
        if lay.get("schema") != OVERLAY_SCHEMA or lay.get("map") != MAP_KEY or lay.get("variant") != SCENE_VARIANT:
            lerr.append(f"{LAYOUT_REL}: schema / map / variant must be {OVERLAY_SCHEMA} / {MAP_KEY} / {SCENE_VARIANT}")
        for fixed in ("lights", "ground", "tray", "apron"):
            if fixed in lay:
                lerr.append(f"{LAYOUT_REL}: an overlay cannot change '{fixed}' (S08EnvLayout::MergeOverlay)")
        props = lay.get("props") or {}
        entries = list(props.get("add") or []) + list(props.get("replace") or [])
        planned = {m["path"] for m in SM.mi_plan(manifest)}
        placed: dict[str, int] = {}
        instanced = 0
        unknown = set()
        for e in entries:
            mesh_path = (e.get("mesh") or "").split(".")[0]
            pid = e.get("id", "?")
            mm = by_ue.get(mesh_path)
            if mm is not None:
                placed[mm["name"]] = placed.get(mm["name"], 0) + 1
                instanced += int(mm.get("tris") or 0)
                if mm.get("castShadow") and e.get("castShadow") is False and not match_patterns(casters, pid):
                    lerr.append(f"prop {pid}: {mm['name']} casts (manifest) but castShadow false and no lit3d caster pattern")
                if mm.get("lumenGI") is False and not match_patterns(gi_off, pid):
                    lerr.append(f"prop {pid}: {mm['name']} lumenGI false (manifest) needs a lit3d giOff pattern")
            elif mesh_path in existing_ue:
                em = existing_ue[mesh_path]
                placed[em["name"]] = placed.get(em["name"], 0) + 1
                instanced += int(em.get("tris") or 0)
            elif mesh_path:
                unknown.add(mesh_path)
            mats = e.get("material")
            for mat in ([mats] if isinstance(mats, str) else (mats or [])):
                if isinstance(mat, str) and mat.startswith(UE_DIR + "/MI_") and mat.split(".")[0] not in planned:
                    hint = ""
                    leaf = mat.split(".")[0].rsplit("/", 1)[1]
                    if leaf.startswith("MI_EnvScene_Proj_") and leaf[len("MI_EnvScene_Proj_"):] in SM.MATERIAL_NAMES:
                        hint = f" (a material-route MI: use {SM.material_mi_path(leaf[len('MI_EnvScene_Proj_'):])})"
                    lerr.append(f"prop {pid}: material {mat} is not an MI of ue_scene_material.mi_plan{hint}")
        if instanced > MAX_SCENE_TRIS:
            lerr.append(f"instanced manifest triangles {instanced} > {MAX_SCENE_TRIS} (G8)")
        errors.extend(lerr)
        report["layout"] = {"props": len(entries), "placed": placed, "instancedManifestTris": instanced,
                            "otherMeshes": sorted(unknown), "unplaced": sorted(names - set(placed))}
    else:
        report["layout"] = "absent (track A)"
    # the profile's required scene packages are this manifest's (or the master material)
    for path in lit3d.get("required", []):
        if path != SM.MATERIAL_PATH and path not in by_ue:
            errors.append(f"lit3d.required {path} is neither M_EnvScene nor a manifest mesh")
    report["meshCount"] = len(names)
    return report, errors


def fab_fx():
    sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
    import ue_import_fab_fx as FX  # noqa: E402  (FX_SPECS / FX_PLAN_SYSTEMS: plain Python)
    return FX


def validate_fx_plan(plan: dict, layout: dict | None = None) -> tuple[dict, list[str]]:
    """ENV-MAPS P9 fx-plan.sarpedon.json (track B) and, with the scene overlay, its merge state."""
    FX = fab_fx()
    errors: list[str] = []
    report: dict = {"fires": 0, "waterfall": 0}
    if plan.get("schema") != FX_PLAN_SCHEMA or plan.get("map") != MAP_KEY:
        errors.append(f"fx-plan: schema / map must be {FX_PLAN_SCHEMA} / {MAP_KEY}")
    ids: list[str] = []

    def num(v, lo, hi):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= float(v) <= hi

    for section, allowed in (("fires", FX.FX_PLAN_SYSTEMS["fires"]), ("waterfall", FX.FX_PLAN_SYSTEMS["waterfall"])):
        entries = plan.get(section)
        if not isinstance(entries, list) or not entries:
            errors.append(f"fx-plan.{section} must be a non-empty list")
            continue
        for i, e in enumerate(entries):
            where = f"fx-plan.{section}[{i}]"
            if not isinstance(e, dict):
                errors.append(f"{where} is not an object")
                continue
            fid = e.get("id")
            if not isinstance(fid, str) or not FX_ID_RE.fullmatch(fid):
                errors.append(f"{where}: id {fid!r} must be lower-case [a-z0-9-]")
            ids.append(fid)
            system = e.get("system", "")
            leaf = system.rsplit("/", 1)[-1] if isinstance(system, str) else ""
            if system != f"{FX.FX_ROOT}/{leaf}" or leaf not in allowed or FX.spec_by_name(leaf) is None:
                errors.append(f"{where}: system {system!r} must be one of {FX.FX_ROOT}/{allowed}")
            if not num(e.get("scale"), 0.05, FX.MAX_FX_SCALE if hasattr(FX, "MAX_FX_SCALE") else 10.0):
                errors.append(f"{where}: scale {e.get('scale')!r} must be 0.05..10")
            if section == "fires":
                if e.get("anchor") not in FX_ANCHORS:
                    errors.append(f"{where}: anchor {e.get('anchor')!r} must be one of {FX_ANCHORS}")
                off = e.get("offsetUU")
                if not (isinstance(off, list) and len(off) == 3 and all(num(v, -200.0, 200.0) for v in off)):
                    errors.append(f"{where}: offsetUU must be [x, y, z] within +-200 uu")
                if not num(e.get("yawDeg", 0), -360.0, 360.0):
                    errors.append(f"{where}: yawDeg -360..360")
            else:
                tier = e.get("tier")
                if not isinstance(tier, int) or isinstance(tier, bool) or not 1 <= tier <= 4:
                    errors.append(f"{where}: tier {tier!r} must be an integer 1..4")
        report[section] = len(entries) if isinstance(entries, list) else 0
    if len(ids) != len(set(ids)):
        errors.append("fx-plan: duplicate ids")
    anchors = {e.get("anchor") for e in plan.get("fires") or [] if isinstance(e, dict)}
    if not set(FX_ANCHORS) <= anchors:
        errors.append(f"fx-plan: every fire anchor {FX_ANCHORS} needs its layers (got {sorted(a for a in anchors if a)})")
    for anchor in FX_ANCHORS:  # the layered fire: core + tongues + embers + smoke per anchor
        got = {str(e.get("system", "")).rsplit("/", 1)[-1] for e in plan.get("fires") or []
               if isinstance(e, dict) and e.get("anchor") == anchor}
        if anchor in anchors and got != set(FX.FX_PLAN_SYSTEMS["fires"]):
            errors.append(f"fx-plan: {anchor} layers {sorted(got)} != {sorted(FX.FX_PLAN_SYSTEMS['fires'])}")
    # particles of the plan (steady state; the board budget of ue_import_fab_fx is BOARD_PARTICLE_BUDGET)
    est = 0.0
    for e in list(plan.get("fires") or []) + list(plan.get("waterfall") or []):
        leaf = str((e or {}).get("system", "")).rsplit("/", 1)[-1] if isinstance(e, dict) else ""
        if FX.spec_by_name(leaf) is not None:
            est += FX.estimate_particles(leaf)
    report["particlesEstimate"] = round(est, 1)
    if est > FX.BOARD_PARTICLE_BUDGET / 2:
        errors.append(f"fx-plan: ~{est:.0f} particles > half the board budget {FX.BOARD_PARTICLE_BUDGET}")
    if layout is not None:
        fx_add = ((layout.get("fx") or {}).get("add") or [])
        laid = {f.get("id") for f in fx_add if isinstance(f, dict)}
        merged = [i for i in ids if i in laid]
        concept_fire = [f.get("id") for f in fx_add if isinstance(f, dict) and
                        str(f.get("system", "")).endswith("/NS_Env_ConceptFire")]
        state = "all" if ids and len(merged) == len(set(ids)) else ("none" if not merged else "partial")
        report["merged"] = state
        report["conceptFireLeft"] = concept_fire
        if state == "partial":
            missing = sorted(set(ids) - laid)
            report["notMerged"] = missing
            # a waterfall tier the cascade does not have is dropped by the merger (documented): only fires must be complete
            fires_missing = [i for i in missing if i.startswith("fire-")]
            if fires_missing:
                errors.append(f"fx-plan merged partially into the scene overlay: missing fires {fires_missing}")
        if merged and concept_fire:
            errors.append(f"scene overlay keeps the P8 NS_Env_ConceptFire {concept_fire} next to the fx-plan fires")
    return report, errors


# ---------------------------------------------------------------------------------------------------- UE side
def texture_settings(key: str) -> dict:
    tcs, mips, grp, addr = u.TextureCompressionSettings, u.TextureMipGenSettings, u.TextureGroup, u.TextureAddress
    base = {"mip_gen_settings": mips.TMGS_FROM_TEXTURE_GROUP, "never_stream": False}
    if key == "N":
        base.update({"compression_settings": tcs.TC_NORMALMAP, "srgb": False, "flip_green_channel": False,
                     "lod_group": grp.TEXTUREGROUP_WORLD_NORMAL_MAP, "address_x": addr.TA_WRAP, "address_y": addr.TA_WRAP})
    elif key == "ORM":
        base.update({"compression_settings": tcs.TC_MASKS, "srgb": False, "lod_group": grp.TEXTUREGROUP_WORLD,
                     "address_x": addr.TA_WRAP, "address_y": addr.TA_WRAP})
    elif key == "Albedo":
        base.update({"compression_settings": tcs.TC_BC7, "srgb": True, "lod_group": grp.TEXTUREGROUP_WORLD,
                     "address_x": addr.TA_CLAMP, "address_y": addr.TA_CLAMP})
    else:  # BC
        base.update({"compression_settings": tcs.TC_BC7, "srgb": True, "lod_group": grp.TEXTUREGROUP_WORLD,
                     "address_x": addr.TA_WRAP, "address_y": addr.TA_WRAP})
    return base


def import_texture(src: Path, asset: str, key: str, sha: str, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    wanted = texture_settings(key)
    tex = u.load_asset(asset) if eal.does_asset_exist(asset) else None
    if tex is not None and not force and eal.get_metadata_tag(tex, SHA_TAG) == sha and \
            all(tex.get_editor_property(k) == v for k, v in wanted.items()):
        return {"action": "unchanged", "asset": asset}
    action = "reimported" if tex is not None else "imported"
    folder, leaf = asset.rsplit("/", 1)
    task = u.AssetImportTask()
    task.filename = str(src)
    task.destination_path = folder
    task.destination_name = leaf
    task.automated = True
    task.replace_existing = True
    task.save = False
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = u.load_asset(asset)
    if tex is None or not isinstance(tex, u.Texture2D):
        raise RuntimeError(f"import of {src} did not produce the texture {asset}")
    for k, v in wanted.items():  # compression first (dict order), then sRGB / flip, group, address
        tex.set_editor_property(k, v)
    eal.set_metadata_tag(tex, SHA_TAG, sha)
    if not eal.save_loaded_asset(tex, False):
        raise RuntimeError(f"could not save {asset}")
    return {"action": action, "asset": asset, "sizeX": int(tex.blueprint_get_size_x()), "sizeY": int(tex.blueprint_get_size_y()),
            "srgb": bool(tex.get_editor_property("srgb")), "compression": str(tex.get_editor_property("compression_settings"))}


def kit():
    sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
    import ue_import_env_kit as K  # noqa: E402  (import_mesh / ensure_mesh_settings: the kit's FBX route)
    return K


def import_mesh(m: dict, src: Path, sha: str, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    K = kit()
    asset = m["ue"]
    mesh = u.load_asset(asset) if eal.does_asset_exist(asset) else None
    action, res = "unchanged", {}
    if mesh is None or force or eal.get_metadata_tag(mesh, SHA_TAG) != sha:
        action = "reimported" if mesh is not None else "imported"
        res = K.import_mesh({"abs": str(src), "path": m["fbx"]}, asset, 1.0)
        mesh = u.load_asset(asset)
        if mesh is None or not isinstance(mesh, u.StaticMesh):
            raise RuntimeError(f"import of {src} did not produce the static mesh {asset}")
        eal.set_metadata_tag(mesh, SHA_TAG, sha)
    mi_path = m.get("mi") or f"{UE_DIR}/MI_Env_S_{m['name']}"
    mi = u.load_asset(mi_path) if eal.does_asset_exist(mi_path) else None
    if mi is None:
        raise RuntimeError(f"{mi_path} missing (ue_scene_material.build_all runs first)")
    settings = K.ensure_mesh_settings(mesh, mi)  # Nanite off, no collision, every slot -> the MI
    for index, slot_mi in enumerate(m.get("slots") or []):
        if slot_mi and "/" not in slot_mi:  # track A writes bare MI names (MI_Env_S_<Name>) for its own slots
            slot_mi = f"{UE_DIR}/{slot_mi}"
        if slot_mi and index < settings["slots"] and eal.does_asset_exist(slot_mi):
            mesh.set_material(index, u.load_asset(slot_mi))
            settings["changes"].append(f"slot {index} -> {slot_mi.rsplit('/', 1)[1]}")
    if settings["changes"] or action != "unchanged":
        if not eal.save_loaded_asset(mesh, False):
            raise RuntimeError(f"could not save {asset}")
    return {"action": action, **res, **settings, "mi": mi_path}


def _full_mi(mi: str | None) -> str | None:
    """A bare MI name (track A writes MI_Env_S_<Name> / MI_EnvScene_<Name>) -> its MAP_ROOT path."""
    if mi and "/" not in mi:
        return f"{UE_DIR}/{mi}"
    return mi


def run_import(manifest: dict, force: bool) -> dict:
    out: dict = {"textures": {}, "meshes": {}}
    out["materials"] = {"collection": SM.ensure_collection(force)}
    mpc = u.load_asset(SM.MPC_PATH)
    out["materials"]["masters"] = [SM.build_master(SM.MATERIAL_PATH, False, mpc, force),
                                   SM.build_master(SM.MASKED_PATH, True, mpc, force)]
    for m in manifest["meshes"]:
        for key, rel in (m.get("textures") or {}).items():
            out["textures"][rel] = import_texture(resolve(rel), f"{UE_DIR}/{Path(rel).stem}", key,
                                                  sha_of(manifest, m, rel), force)
    proj = manifest["projected"]
    out["textures"][proj["albedo"]] = import_texture(resolve(proj["albedo"]), proj["ue"], "Albedo", proj["sha256"], force)
    out["materials"]["mis"] = [SM.build_mi(item, force) for item in SM.mi_plan(manifest)]
    for m in manifest["meshes"]:
        out["meshes"][m["name"]] = import_mesh(m, resolve(m["fbx"]), sha_of(manifest, m, m["fbx"]), force)
    # meshes that keep an existing material (track A: the vertical banner -> MI_EnvCP_Banner): no baked textures,
    # every slot -> slots[0] (or "mi")
    # P9: several slots -> one MI per slot (the F2 frame band: wood + iron)
    for m in manifest.get("meshesExistingMaterial") or []:
        item = dict(m)
        slots = list(m.get("slots") or [])
        item["mi"] = _full_mi(m.get("mi") or (slots[0] if slots else None))
        if not item["mi"]:
            raise RuntimeError(f"meshesExistingMaterial {m.get('name')}: no 'mi' / slots[0]")
        item["slots"] = slots if len(slots) > 1 else []
        out["meshes"][m["name"]] = import_mesh(item, resolve(m["fbx"]), sha_of(manifest, m, m["fbx"]), force)
    return out


# ---------------------------------------------------------------------------------------------------- entry
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="plain-Python contract checks (no UE)")
    parser.add_argument("--manifest", default=None, help=f"manifest (default {MANIFEST.relative_to(REPO).as_posix()})")
    parser.add_argument("--no-files", action="store_true", help="--check: skip presence / sha256 of the sources")
    parser.add_argument("--no-git", action="store_true", help="--check: skip git check-ignore / ls-files")
    parser.add_argument("--report", default=None, help="report JSON path")
    parser.add_argument("--force", action="store_true", help="re-import even when the sha256 tags are current")
    args = parser.parse_args(argv)
    started = time.time()
    manifest_path = Path(args.manifest) if args.manifest else MANIFEST
    report: dict = {"schema": "unmatched.concept-scene-import/1", "tool": "tools/art/concept_scene/ue_import_concept_scene.py",
                    "manifest": manifest_path.as_posix()}
    ok = True
    if not manifest_path.is_file():
        report["mode"] = "check" if (args.check or u is None) else "import"
        report["errors"] = [f"{manifest_path.as_posix()} missing (track A: tools/art/concept_scene writes it)"]
        ok = False
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        report["check"], errors = validate(manifest, check_files=not args.no_files, check_git=not args.no_git)
        if FX_PLAN.is_file():  # P9: the fx plan (track B) and its merge into the scene overlay (track A)
            layout_path = REPO / LAYOUT_REL
            lay = json.loads(layout_path.read_text(encoding="utf-8")) if layout_path.is_file() else None
            report["fxPlan"], fx_errors = validate_fx_plan(json.loads(FX_PLAN.read_text(encoding="utf-8")), lay)
            errors = errors + fx_errors
        report["errors"] = errors
        ok = not errors
        if args.check or u is None:
            report["mode"] = "check"
        else:
            report["mode"] = "import"
            if ok:
                try:
                    report["import"] = run_import(manifest, args.force)
                except Exception as exc:  # reported; the commandlet logs the failure below
                    report["import"] = {"action": "failed", "error": str(exc)}
                    ok = False
            report["engine"] = str(u.SystemLibrary.get_engine_version())
    report["ok"] = ok
    report["seconds"] = round(time.time() - started, 2)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    report_path = Path(args.report) if args.report else (
        Path(u.Paths.project_saved_dir()) / "EnvMaps" / "concept-scene-import-report.json" if u is not None else None)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text + "\n", encoding="utf-8")
    print("CONCEPT-SCENE-IMPORT-REPORT " + json.dumps(report, ensure_ascii=False))
    print(f"CONCEPT-SCENE-IMPORT-RESULT {'ok' if ok else 'failed'} mode={report['mode']}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        u.log_error(f"ue_import_concept_scene.py failed (code {code}); see the CONCEPT-SCENE-IMPORT-REPORT line")
