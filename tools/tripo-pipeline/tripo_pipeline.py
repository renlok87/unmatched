#!/usr/bin/env python3
"""tripo-pipeline: local, resumable, idempotent pipeline scaffold for Tripo results.

This tool NEVER talks to Tripo (no Studio automation, no API client, no network
imports at all). It registers Tripo results that already exist on disk, runs
local stages (Blender headless for import/export) and keeps a run manifest with
hashes, tool versions, costs and a stage journal. Documentation (Russian):
docs/art-pipeline/PIPELINE.md.

Commands:
  init               create/confirm a run directory and its config
  register-source    register an existing Tripo result from a source-spec JSON
  preflight          check tools, paths and hashes (also stage 0 of `run`)
  import             Blender: read the primary GLB into work/<basename>.blend
  verify             check the import against GLB structure and spec expectations
  export             Blender: deterministic FBX (preset UM_FBX_v1) + round-trip re-import check
                     (profile passthrough)
  atlas              Python/Pillow: pack part textures into BC/N/ORM atlas (profile skeletal-candidate);
                     profile options: atlas.exclude_parts, atlas.normal_renormalise, team_color.mask (TeamMask)
  build              Blender: skeletal candidate + separate base from a build profile, deterministic
                     FBX with the profile's preset (UM_FBX_v1: face -Y -> +X), round-trip and
                     reference checks (profile skeletal-candidate). The algorithm is chosen and
                     parameterised by the profile (build.flow: whole-figure = Medusa T4, seated-parts =
                     heroes: weapon split/parts/none, normalised or parametric base, closure caps,
                     per-face orientation vote, heat/rigid/wing/axis weights, anatomy, sockets);
                     library blender/candidate_build/, no per-asset builder scripts
  adopt              pin an externally built static prop candidate (FBX + BC/N/ORM, e.g. from
                     blender/static_prop_candidate.py) against its candidate/read-back reports
                     (profile static-candidate); copies nothing. Profile skeletal-adopt: pin an externally
                     built skeletal candidate (the H2 bake of a hero: SK + base FBX, 2K BC/N/ORM/TeamMask) against
                     the bake's own reports and normalise them for ue-import (skeletal_adopt.py); copies nothing
  ue-import          UE (only --backend mcp): import into /Game/PipelineCandidates/... without
                     duplicates and measure the import contracts
  run                all stages of the run's profile (skips up-to-date stages):
                       passthrough:        preflight -> import -> verify -> export [-> ue-import]
                       skeletal-candidate: preflight -> import -> verify -> atlas -> build [-> ue-import]
                       static-candidate:   preflight -> adopt [-> ue-import]
                       skeletal-adopt:     preflight -> adopt [-> ue-import]  (ue-import = the skeletal-candidate
                                           import on the adopted files: UM master MIs, legacy FbxFactory, sockets)
  resume             continue an interrupted run from the first unfinished stage
  status             print the manifest summary
  snapshot           hash every run file (proof of "no duplicates" between runs)
  prepare-generation dry-run package of generation inputs; never submits; refuses inputs + mode +
                     service that were already generated (any model label) unless
                     --allow-duplicate --duplicate-reason "..."

Backends (--backend, default headless):
  headless  Blender stages in a fresh `blender -b` process; UE stage refused
  mcp       Blender stages in the running Blender GUI through blender_mcp.py
            (addon socket 127.0.0.1:9876, execute_code, isolated temp scenes);
            UE stage in the running UnrealEditor through unreal_mcp.py
            (127.0.0.1:8123/mcp: AssetTools / StaticMeshTools / SkeletalMeshTools).
  MCP traffic goes through those external client scripts (subprocess); this
  file itself has no network code and never contacts Tripo.

FBX axes: every FBX this tool writes follows the verified preset UM_FBX_v1
(blender/_tools/presets/UM_FBX_v1.json, ART-001 PASS; 04-blender-production.md §1/§1.1):
authored front -Y is rotated to +X before export, so UE shows the front along +X.

Statuses written by this tool are only "measured" / "technically imported"; it
never marks anything as art-accepted and declares no budgets.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

TOOL_NAME = "tripo-pipeline"
TOOL_VERSION = "0.8.0"  # 0.8.0 (W5c): skeletal-adopt ue.target_skeleton (mesh onto a canonical hero skeleton)
# 0.7.0 (W5c): profile skeletal-adopt (H2 bakes into UE)
RUN_SCHEMA = "unmatched.tripo-pipeline.run/1"
SPEC_SCHEMA = "unmatched.tripo-pipeline.source-spec/1"
REQUEST_SCHEMA = "unmatched.tripo-pipeline.generation-request/1"
BUILD_PROFILE_SCHEMA = "unmatched.tripo-pipeline.build-profile/1"
VERIFY_LOGIC_VERSION = "verify/1"
PREFLIGHT_LOGIC_VERSION = "preflight/4"
UE_IMPORT_LOGIC_VERSION = "ue-import/2"
UE_CANDIDATE_LOGIC_VERSION = "ue-candidate/7"  # /4: socket bones use the UE bone name ('.' -> '_');
# /6: a vertex-mask base is imported with its vertex colours by editor Python;
# /7 (0.6.0, W4-B): both meshes through UE_PY_IMPORT_FBX (explicit legacy FbxFactory + FbxImportUI, normal import
# method ImportNormals, Nanite off), material route "um-master" (MI of M_UM_Figure / M_UM_BaseMarker, hex team colours
# through FLinearColor::FromSRGBColor), checks nanite == false, normal method, factory, parent material
UE_NORMAL_IMPORT_METHOD = "FBXNIM_IMPORT_NORMALS"  # UM_FBX_v1 writes normals, no tangent layer (use_tspace off)
UE_PY_IMPORT_FBX = r'''"""tripo-pipeline ue-import: FBX import with an explicit legacy FbxFactory (run inside the live editor).

Why not MCP import_file (engine gate memo, importer topic; W4-B): MCP StaticMeshTools/SkeletalMeshTools.import_file
build an FbxImportUI but take no normal import method (the skeletal default is ComputeNormals, while the production
ArtPreview Medusa was imported with its FBX normals) and no vertex-colour option (a vertex-mask base lost its mask,
T3.1). AssetTools only switches to Interchange when a task has no factory (AssetTools.cpp), so the explicit FbxFactory
also pins the legacy importer independently of Interchange.FeatureFlags.Import.FBX. Nothing global is changed: the
options live on this task's FbxImportUI only (changing a class default dirtied 47 packages in T3.1).
args: {"kind": "static" | "skeletal", "folder_path", "asset_name", "source_file", "import_materials",
       "import_textures", "combine_meshes", "vertex_colors": "replace" | "ignore", "normal_import_method",
       "skeleton": null | "/Game/.../SK_Hero_Skeleton.SK_Hero_Skeleton", "out"}
skeleton (0.8.0, profile skeletal-adopt ue.target_skeleton): the skeletal mesh is imported onto that existing
(canonical) skeleton instead of creating <asset>_Skeleton next to it; the skeleton is read back and reported and
is never listed as imported (the run does not own it).
"""
import json
import sys

import unreal as u

a = json.load(open(sys.argv[-1], encoding="utf-8"))
res = {"kind": a["kind"], "factory": "FbxFactory", "normal_import_method": a["normal_import_method"],
       "vertex_colors": a.get("vertex_colors", "ignore")}


def setp(obj, name, value):
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:  # noqa: BLE001 - optional property (engine version)
        return False


try:
    if u.EditorAssetLibrary.does_asset_exist("%s/%s" % (a["folder_path"], a["asset_name"])):
        raise RuntimeError("import_asset: %s at %s already exists" % (a["asset_name"], a["folder_path"]))
    skeletal = a["kind"] == "skeletal"
    kind = u.FBXImportType.FBXIT_SKELETAL_MESH if skeletal else u.FBXImportType.FBXIT_STATIC_MESH
    o = u.FbxImportUI()
    o.set_editor_property("automated_import_should_detect_type", False)
    o.set_editor_property("import_mesh", True)
    o.set_editor_property("import_as_skeletal", skeletal)
    o.set_editor_property("mesh_type_to_import", kind)
    o.set_editor_property("original_import_type", kind)
    o.set_editor_property("import_materials", bool(a["import_materials"]))
    o.set_editor_property("import_textures", bool(a["import_textures"]))
    o.set_editor_property("import_animations", False)
    method = getattr(u.FBXNormalImportMethod, a["normal_import_method"])
    if skeletal:
        o.set_editor_property("create_physics_asset", False)
        if a.get("skeleton"):
            target_skel = u.load_asset(a["skeleton"])
            if target_skel is None or not isinstance(target_skel, u.Skeleton):
                raise RuntimeError("target skeleton not found: %s" % a["skeleton"])
            o.set_editor_property("skeleton", target_skel)
        d = o.get_editor_property("skeletal_mesh_import_data")
        setp(d, "import_morph_targets", False)
    else:
        d = o.get_editor_property("static_mesh_import_data")
        d.set_editor_property("combine_meshes", bool(a.get("combine_meshes", True)))
        d.set_editor_property("vertex_color_import_option", u.VertexColorImportOption.REPLACE
                              if a.get("vertex_colors") == "replace" else u.VertexColorImportOption.IGNORE)
        if a.get("generate_lightmap_uvs") is not None:
            # 0.9.0: a base with an authored UV1 (M_UM_Figure_v2 detail in metres) must not get UV1 overwritten
            res["generate_lightmap_uvs_set"] = setp(d, "generate_lightmap_u_vs", bool(a["generate_lightmap_uvs"]))
    d.set_editor_property("normal_import_method", method)
    d.set_editor_property("import_uniform_scale", 1.0)
    res["build_nanite_option_set_false"] = setp(d, "build_nanite", False)
    t = u.AssetImportTask()
    t.set_editor_property("filename", a["source_file"])
    t.set_editor_property("destination_path", a["folder_path"])
    t.set_editor_property("destination_name", a["asset_name"])
    t.set_editor_property("replace_existing", False)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", False)
    t.set_editor_property("factory", u.FbxFactory())
    t.set_editor_property("options", o)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    res["imported"] = [str(x) for x in t.get_editor_property("imported_object_paths")]
    if not res["imported"]:
        raise RuntimeError("the import produced no assets")
    asset = u.load_asset("%s/%s" % (a["folder_path"], a["asset_name"]))
    aid = asset.get_editor_property("asset_import_data") if asset else None
    res["asset_import_data_class"] = aid.get_class().get_name() if aid else None
    if aid is not None:
        nim = aid.get_editor_property("normal_import_method")
        res["normal_import_method_read_back"] = getattr(nim, "name", str(nim))
    if not skeletal and asset is not None:
        try:  # 0.9.0: UV channels of LOD0 and the lightmap-UV build setting, read back
            sms = u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
            res["uv_channels_lod0"] = int(sms.get_num_uv_channels(asset, 0))
            bs = sms.get_lod_build_settings(asset, 0)
            res["build_generate_lightmap_uvs"] = bool(bs.get_editor_property("generate_lightmap_u_vs"))
        except Exception as exc:  # noqa: BLE001 - measurement only
            res["uv_read_back_error"] = str(exc)
    if skeletal and asset is not None:
        # the skeleton created next to the mesh is part of the import (MCP import_file also returned it)
        skel = asset.get_editor_property("skeleton")
        if skel is not None:
            res["skeleton_read_back"] = skel.get_path_name()
            if not a.get("skeleton"):
                res["imported"].append(skel.get_path_name())
except Exception as exc:  # noqa: BLE001 - reported to the CLI
    res["error"] = "%s: %s" % (type(exc).__name__, exc)
with open(a["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(res, indent=1, sort_keys=True) + "\n")
'''
UE_PY_LAUNCHER = r'''"""tripo-pipeline editor-Python launcher: proves to the CLI that the typed command started, then runs
the target script with the same arguments (McpUnreal.editor_python)."""
import runpy
import sys

with open(r"@STARTED@", "w", encoding="utf-8") as handle:
    handle.write("started\n")
sys.argv = [r"@TARGET@"] + sys.argv[1:]
runpy.run_path(r"@TARGET@", run_name="__main__")
'''
UE_STATIC_LOGIC_VERSION = "ue-static-candidate/2"  # /2 (0.6.0): checks nanite == false, normal import method, master
ADOPT_LOGIC_VERSION = "adopt/1"
# skeletal-adopt (0.7.0): ue-import of an adopted skeletal candidate = exec_ue_candidate on the adopt report's views,
# plus the skeletal LOD/triangle measurement in the editor (UE_PY_MEASURE_SKELETAL)
UE_SKELETAL_ADOPT_LOGIC_VERSION = "ue-skeletal-adopt/1"
UE_PY_MEASURE_SKELETAL = r'''"""tripo-pipeline ue-import: skeletal mesh measurement (run inside the live editor).

MCP SkeletalMeshTools has no triangle count: LOD triangles are read through GeometryScript
(copy_mesh_from_skeletal_mesh into a transient DynamicMesh; nothing is created or saved).
args: {"mesh": "/Game/.../SK_X.SK_X", "lods": <LOD count from MCP>, "out"}
"""
import json
import sys

import unreal as u

a = json.load(open(sys.argv[-1], encoding="utf-8"))
res = {"mesh": a["mesh"], "triangles": [], "vertices": []}
try:
    mesh = u.load_asset(a["mesh"])
    if mesh is None:
        raise RuntimeError("asset not found: %s" % a["mesh"])
    for lod in range(max(1, int(a.get("lods") or 1))):
        dm = u.DynamicMesh()
        read = u.GeometryScriptMeshReadLOD()
        read.set_editor_property("lod_index", lod)
        _dm, outcome = u.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
            mesh, dm, u.GeometryScriptCopyMeshFromAssetOptions(), read)
        if "SUCCESS" not in str(outcome):
            raise RuntimeError("LOD %d: %s" % (lod, outcome))
        res["triangles"].append(int(u.GeometryScript_MeshQueries.get_num_triangle_i_ds(dm)))
        res["vertices"].append(int(u.GeometryScript_MeshQueries.get_vertex_count(dm)))
        try:  # 0.9.0: UV sets of the LOD (M_UM_Figure_v2 reads UV1 in metres)
            res.setdefault("uv_sets", []).append(int(u.GeometryScript_MeshQueries.get_num_uv_sets(dm)))
        except Exception as exc:  # noqa: BLE001 - measurement only
            res["uv_sets_error"] = str(exc)
    res["method"] = "GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh + get_num_triangle_i_ds"
except Exception as exc:  # noqa: BLE001 - reported to the CLI
    res["error"] = "%s: %s" % (type(exc).__name__, exc)
with open(a["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(res, indent=1, sort_keys=True) + "\n")
'''

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_CONFLICT = 3
EXIT_LOCKED = 4
EXIT_NEEDS_RESUME = 5
EXIT_INTERRUPTED = 75

TOOL_DIR = Path(__file__).resolve().parent
BLENDER_SCRIPTS = {
    "import": TOOL_DIR / "blender" / "import_source.py",
    "export": TOOL_DIR / "blender" / "export_fbx.py",
    "build": TOOL_DIR / "blender" / "build_candidate.py",
    "ao_bake": TOOL_DIR / "blender" / "bake_ao.py",  # atlas sub-step (atlas.ao_bake), always headless
}
ATLAS_SCRIPT = TOOL_DIR / "candidate" / "atlas.py"
BUILD_LIBRARY = TOOL_DIR / "blender" / "candidate_build"  # the build stage's library (loaded by build_candidate.py)
DEFAULT_FBX_PRESET = "blender/_tools/presets/UM_FBX_v1.json"  # repo-relative; ART-001 PASS 2026-09-27
FBX_PRESET_NAME = "UM_FBX_v1"
FBX_PRESET_KEYS = ("name", "axis_forward", "axis_up", "export_space_rotation_z_degrees", "temporary_data_scale",
                   "patch_fbx_unit_scale_to", "apply_unit_scale", "apply_scale_options", "use_triangles",
                   "mesh_smooth_type", "add_leaf_bones", "primary_bone_axis", "secondary_bone_axis", "path_mode")
DEFAULT_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
DEFAULT_UE_ROOT = "C:/Program Files/Epic Games/UE_5.8"
DEFAULT_MCP_CLIENTS = Path("C:/Users/ren/.claude/mcp-servers/clients")
BACKENDS = ("headless", "mcp")
PASSTHROUGH = "passthrough"
CANDIDATE = "skeletal-candidate"
STATIC = "static-candidate"
SKELETAL_ADOPT = "skeletal-adopt"  # 0.7.0: an externally built skeletal candidate (H2 bake), see skeletal_adopt.py
PROFILES = (PASSTHROUGH, CANDIDATE, STATIC, SKELETAL_ADOPT)
BUILD_PROFILE_KINDS = (CANDIDATE, STATIC, SKELETAL_ADOPT)  # profiles that read --build-profile
SKELETAL_KINDS = (CANDIDATE, SKELETAL_ADOPT)  # profiles whose ue-import is exec_ue_candidate
STAGES = ("preflight", "import", "verify", "export")  # passthrough profile (T3)
CANDIDATE_STAGES = ("preflight", "import", "verify", "atlas", "build")
# static-candidate: the candidate FBX/BC/N/ORM were built outside this tool (static_prop_candidate.py);
# `adopt` pins their bytes against the candidate report before the UE stage imports them.
STATIC_STAGES = ("preflight", "adopt")
SKELETAL_ADOPT_STAGES = ("preflight", "adopt")  # skeletal-adopt: adopt pins the H2 bake (skeletal_adopt.py)
UE_STAGE = "ue-import"
ALL_STAGES = STAGES + (UE_STAGE,)
KNOWN_STAGES = ("preflight", "import", "verify", "export", "atlas", "build", "adopt", UE_STAGE)
UE_ALLOWED_ROOT = "/Game/PipelineCandidates/"
UE_TOOLSETS = {
    "asset": "editor_toolset.toolsets.asset.AssetTools",
    "static": "editor_toolset.toolsets.static_mesh.StaticMeshTools",
    "skeletal": "editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools",
    "texture": "editor_toolset.toolsets.texture.TextureTools",
    "material": "editor_toolset.toolsets.material.MaterialTools",
    "instance": "editor_toolset.toolsets.material_instance.MaterialInstanceTools",
    "object": "editor_toolset.toolsets.object.ObjectTools",
    "logs": "EditorToolset.LogsToolset",
    "slate": "SlateInspectorToolset.SlateInspectorToolset",
}
ATLAS_TIMEOUT_S = 600
DEFAULT_UE_DIMENSION_TOLERANCE = 0.01  # fraction of the Blender-measured size
SERVICES = {"tripo-studio": "studio-credits", "tripo-api": "api-credits"}
GENERATION_MODES = ("multi-view", "single-image", "text")
MAX_TRIPO_IMAGE_BYTES = 20_000_000
DEFAULT_TRIANGLE_LOSS_TOLERANCE = 0.001  # fraction; Blender's glTF importer may drop degenerate tris
BLENDER_TIMEOUT_S = 1800

STATUS_LEGEND = {
    "proposed": "предложено — план или норматив без проверки",
    "measured": "измерено — число получено инструментом из файла",
    "technically_imported": "технически импортировано — файл прочитан/записан без ошибок, контракты проверены",
    "art_accepted": "художественно принято — только решением арт-трека; этот инструмент его не ставит",
}


class PipelineError(Exception):
    def __init__(self, message: str, code: int = EXIT_FAILED):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------- utils

def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(data) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_json(data) -> str:
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()


def dump_json(data) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-%d" % os.getpid())
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:  # Windows: a reader (AV, indexer) briefly holds the file
            time.sleep(0.05 * (attempt + 1))
    os.replace(tmp, path)


def rel_posix(path: Path, base: Path) -> str:
    return Path(os.path.relpath(path, base)).as_posix()


def is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied => process exists
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# --------------------------------------------------------------- file inspectors

def inspect_glb(path: Path) -> dict:
    """Stdlib-only structural read of a binary glTF (JSON chunk only)."""
    with open(path, "rb") as handle:
        header = handle.read(20)
        if len(header) < 20:
            raise PipelineError("GLB too short: %s" % path)
        magic, version, _length = struct.unpack_from("<4sII", header, 0)
        chunk_length, chunk_type = struct.unpack_from("<I4s", header, 12)
        if magic != b"glTF" or chunk_type != b"JSON":
            raise PipelineError("not a binary glTF: %s" % path)
        doc = json.loads(handle.read(chunk_length).decode("utf-8"))
    accessors = doc.get("accessors", [])
    meshes = []
    modes = set()
    for mesh in doc.get("meshes", []):
        tris = 0
        for prim in mesh.get("primitives", []):
            mode = prim.get("mode", 4)
            modes.add(mode)
            if "indices" in prim:
                count = accessors[prim["indices"]]["count"]
            else:
                count = accessors[prim["attributes"]["POSITION"]]["count"]
            if mode == 4:
                tris += count // 3
        meshes.append({"name": mesh.get("name"), "triangles": tris})
    return {
        "format": "glb",
        "gltf_version": version,
        "generator": doc.get("asset", {}).get("generator"),
        "mesh_count": len(meshes),
        "triangles": sum(m["triangles"] for m in meshes),
        "materials": len(doc.get("materials", [])),
        "images": len(doc.get("images", [])),
        "skins": len(doc.get("skins", [])),
        "animations": len(doc.get("animations", [])),
        "primitive_modes": sorted(modes),
        "meshes": sorted(meshes, key=lambda m: str(m["name"])),
    }


def inspect_png(path: Path) -> dict:
    with open(path, "rb") as handle:
        head = handle.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return {"format": "unknown"}
    width, height, depth, color = struct.unpack(">IIBB", head[16:26])
    return {"format": "png", "pixels": [width, height], "bit_depth": depth, "color_type": color}


def inspect_jpeg(path: Path) -> dict:
    with open(path, "rb") as handle:
        data = handle.read(1 << 20)
    if data[:2] != b"\xff\xd8":
        return {"format": "unknown"}
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return {"format": "jpeg", "pixels": [width, height]}
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg
    return {"format": "jpeg", "pixels": None}


def inspect_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".glb":
        return inspect_glb(path)
    if suffix == ".png":
        return inspect_png(path)
    if suffix in (".jpg", ".jpeg"):
        return inspect_jpeg(path)
    return {"format": suffix.lstrip(".") or "unknown"}


# ------------------------------------------------------------------------ context

class Context:
    def __init__(self, run_dir: Path, repo_root: Path, blender: str | None, interrupt_at: str | None = None,
                 backend: str | None = None, blender_mcp_client: str | None = None,
                 unreal_mcp_client: str | None = None):
        self.run_dir = run_dir.resolve()
        self.repo_root = repo_root.resolve()
        self.interrupt_at = interrupt_at
        self.manifest_path = self.run_dir / "manifest.json"
        self.journal_path = self.run_dir / "journal.jsonl"
        self.lock_path = self.run_dir / "run.lock"
        self.staging_root = self.run_dir / ".staging"
        self.backend = backend or os.environ.get("TRIPO_PIPELINE_BACKEND") or "headless"
        if self.backend not in BACKENDS:
            raise PipelineError("--backend must be one of %s" % (BACKENDS,), EXIT_USAGE)
        env_cmd = os.environ.get("TRIPO_PIPELINE_BLENDER_CMD")
        if env_cmd:
            self.blender_cmd = json.loads(env_cmd)
        else:
            self.blender_cmd = [blender or os.environ.get("TRIPO_PIPELINE_BLENDER") or DEFAULT_BLENDER]
        self.blender_mcp_cmd = client_command("TRIPO_PIPELINE_BLENDER_MCP_CMD", blender_mcp_client,
                                              DEFAULT_MCP_CLIENTS / "blender_mcp.py")
        self.unreal_mcp_cmd = client_command("TRIPO_PIPELINE_UNREAL_MCP_CMD", unreal_mcp_client,
                                             DEFAULT_MCP_CLIENTS / "unreal_mcp.py")
        if self.backend == "mcp":
            self.blender = McpBlender(self.blender_mcp_cmd)
        else:
            self.blender = HeadlessBlender(self.blender_cmd)
        self._unreal = None
        self.manifest = None
        self._manifest_text = None
        self._locked = False

    # -- manifest
    def load(self) -> dict:
        if not self.manifest_path.exists():
            raise PipelineError("run is not initialised (no manifest.json): %s; use init" % self.run_dir, EXIT_USAGE)
        self._manifest_text = self.manifest_path.read_text(encoding="utf-8")
        self.manifest = json.loads(self._manifest_text)
        if self.manifest.get("schema") != RUN_SCHEMA:
            raise PipelineError("unsupported manifest schema: %s" % self.manifest.get("schema"))
        return self.manifest

    def save(self) -> bool:
        """Write the manifest only if its content changed. Returns True when written."""
        text = dump_json(self.manifest)
        if text == self._manifest_text:
            return False
        atomic_write_text(self.manifest_path, text)
        self._manifest_text = text
        return True

    def journal(self, event: str, **fields) -> None:
        record = {"ts": now_iso(), "pid": os.getpid(), "event": event}
        record.update(fields)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with open(self.journal_path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    # -- lock
    def acquire_lock(self, command: str) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"pid": os.getpid(), "command": command, "started_at": now_iso(),
                              "host": platform.node()})
        for _ in range(2):
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    held = json.loads(self.lock_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    held = {"pid": -1}
                if pid_alive(int(held.get("pid", -1))) and int(held.get("pid", -1)) != os.getpid():
                    raise PipelineError("run is locked by live pid %s (%s)" % (held.get("pid"), held.get("command")),
                                        EXIT_LOCKED)
                self.journal("stale_lock_recovered", previous=held, command=command)
                os.remove(self.lock_path)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            self._locked = True
            return
        raise PipelineError("could not acquire run lock", EXIT_LOCKED)

    def release_lock(self) -> None:
        try:
            self.staging_root.rmdir()  # only succeeds when empty
        except OSError:
            pass
        if self._locked and self.lock_path.exists():
            os.remove(self.lock_path)
        self._locked = False

    # -- paths
    def repo_path(self, rel: str) -> Path:
        return (self.repo_root / rel).resolve()

    def run_path(self, rel: str) -> Path:
        return (self.run_dir / rel).resolve()

    # -- tools
    def blender_version(self) -> str:
        return self.blender.version()

    def unreal(self) -> "McpUnreal":
        if self.backend != "mcp":
            raise PipelineError("stage ue-import needs --backend mcp (live UnrealEditor via unreal_mcp.py). "
                                "Headless UE import is not part of this scaffold: UnrealEditor-Cmd must not "
                                "run on the project while the user's editor has it open.", EXIT_USAGE)
        if self._unreal is None:
            self._unreal = McpUnreal(self.unreal_mcp_cmd)
        return self._unreal


def _no_window() -> dict:
    if os.name == "nt":
        return {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    return {}


def client_command(env_name: str, override: str | None, default: Path) -> list:
    env_cmd = os.environ.get(env_name)
    if env_cmd:
        return json.loads(env_cmd)
    return [sys.executable, str(Path(override) if override else default)]


def client_script(cmd: list) -> Path:
    """The .py client inside an MCP client command line (last *.py argument)."""
    return Path(next((c for c in reversed(cmd) if str(c).lower().endswith(".py")), cmd[-1]))


# ---------------------------------------------------------------------- backends

class HeadlessBlender:
    """Fresh `blender -b` process per stage (isolation mode "process")."""

    kind = "headless"
    isolation = "process"

    def __init__(self, cmd: list):
        self.cmd = cmd
        self._version = None

    def describe(self) -> dict:
        return {"backend": self.kind, "isolation": self.isolation, "command": [Path(c).name for c in self.cmd]}

    def version(self) -> str:
        if self._version is None:
            try:
                proc = subprocess.run(self.cmd + ["--version"], capture_output=True, timeout=120, **_no_window())
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise PipelineError("Blender is not runnable (%s): %s" % (self.cmd, exc))
            text = proc.stdout.decode("utf-8", "replace")
            match = re.search(r"Blender\s+(\S+(?:\s+LTS)?)", text)
            if proc.returncode != 0 or not match:
                raise PipelineError("cannot parse Blender version from: %r" % text[:200])
            self._version = match.group(1)
        return self._version

    def run_stage(self, stage: str, params_path: Path, staging: Path) -> tuple:
        cmd = self.cmd + ["-b", "--factory-startup", "--python-exit-code", "1",
                          "--python", str(BLENDER_SCRIPTS[stage]), "--", str(params_path)]
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=BLENDER_TIMEOUT_S, **_no_window())
            return proc.returncode, proc.stdout.decode("utf-8", "replace")
        except subprocess.TimeoutExpired as exc:
            return -1, (exc.stdout or b"").decode("utf-8", "replace") + "\n[tripo-pipeline] TIMEOUT\n"


def run_client(cmd: list, args: list, timeout: int, what: str) -> dict:
    """Run an MCP CLI client (blender_mcp.py / unreal_mcp.py) and parse its JSON stdout."""
    try:
        proc = subprocess.run(cmd + args, capture_output=True, timeout=timeout, **_no_window())
    except (FileNotFoundError, PermissionError) as exc:
        raise PipelineError("%s client not runnable (%s): %s" % (what, cmd, exc))
    except subprocess.TimeoutExpired:
        raise PipelineError("%s client timed out after %ss: %s" % (what, timeout, args[:2]))
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    try:
        data = json.loads(out) if out.strip() else None
    except ValueError:
        data = None
    if data is None:
        raise PipelineError("%s client gave no JSON (exit %s): %s" % (what, proc.returncode,
                                                                     (err or out).strip()[-600:]))
    return {"exit": proc.returncode, "response": data, "stderr": err}


class McpBlender:
    """Running Blender GUI through blender_mcp.py (isolation mode "live").

    The stage script is sent verbatim via execute_code with two injected globals
    (params path, isolation mode). The scripts never reset, open or save the
    user's file; they work in temporary scenes and delete what they created.
    """

    kind = "mcp"
    isolation = "live"

    def __init__(self, cmd: list):
        self.cmd = cmd
        self._version = None

    def describe(self) -> dict:
        return {"backend": self.kind, "isolation": self.isolation, "client": client_script(self.cmd).name,
                "endpoint": "127.0.0.1:9876 (blender-mcp addon)"}

    def version(self) -> str:
        if self._version is None:
            code = "print('TRIPO_PIPELINE_BLENDER_VERSION', bpy.app.version_string)"
            res = run_client(self.cmd, ["exec-str", code], 120, "blender-mcp")["response"]
            text = ((res.get("result") or {}).get("result") or "") if isinstance(res, dict) else ""
            match = re.search(r"TRIPO_PIPELINE_BLENDER_VERSION\s+(\S+(?:\s+LTS)?)", text)
            if not isinstance(res, dict) or res.get("status") == "error" or not match:
                raise PipelineError("live Blender (MCP) did not report its version: %s"
                                    % json.dumps(res, ensure_ascii=False)[:400])
            self._version = match.group(1)
        return self._version

    def run_stage(self, stage: str, params_path: Path, staging: Path) -> tuple:
        header = ("# tripo-pipeline %s: stage %s via blender-mcp execute_code\n"
                  "TRIPO_PIPELINE_PARAMS = %r\nTRIPO_PIPELINE_ISOLATION = \"live\"\n"
                  % (TOOL_VERSION, stage, str(params_path)))
        wrapper = staging / ("%s.mcp.py" % stage)
        wrapper.write_text(header + BLENDER_SCRIPTS[stage].read_text(encoding="utf-8"), encoding="utf-8")
        try:
            call = run_client(self.cmd, ["exec", str(wrapper)], BLENDER_TIMEOUT_S, "blender-mcp")
        except PipelineError as exc:
            return -1, "[tripo-pipeline] %s\n" % exc
        res = call["response"]
        stdout = ((res.get("result") or {}).get("result") or "") if isinstance(res, dict) else ""
        text = "[tripo-pipeline] blender-mcp exec %s (client exit %s)\n%s\n[response]\n%s\n" % (
            wrapper.name, call["exit"], stdout, json.dumps(res, ensure_ascii=False, indent=1)[:20000])
        failed = call["exit"] != 0 or not isinstance(res, dict) or res.get("status") == "error"
        return (1 if failed else 0), text


class McpUnreal:
    """Running UnrealEditor through unreal_mcp.py (ModelContextProtocol plugin, call_tool)."""

    def __init__(self, cmd: list):
        self.cmd = cmd
        self.calls = []
        self.tool_name_style = None  # "short" or "qualified", detected on first call

    def describe(self) -> dict:
        return {"backend": "mcp", "client": client_script(self.cmd).name, "endpoint": "127.0.0.1:8123/mcp"}

    def _once(self, toolset: str, tool: str, args: dict):
        call = run_client(self.cmd, ["call", toolset, tool, json.dumps(args, ensure_ascii=False)], 900,
                          "unreal-mcp")
        res = call["response"] or {}
        if res.get("error"):
            return False, json.dumps(res["error"], ensure_ascii=False)
        result = res.get("result") or {}
        texts = [c.get("text", "") for c in result.get("content", []) if isinstance(c, dict)]
        if result.get("isError") or call["exit"] != 0:
            return False, " ".join(texts) or json.dumps(res, ensure_ascii=False)[:600]
        payload = result.get("structuredContent")
        if payload is None:
            try:
                payload = json.loads(texts[0]) if texts else {}
            except ValueError:
                payload = {"text": texts[0]}
        return True, payload

    def editor_python(self, script: Path, args_path: Path, out: Path, timeout: int = 600) -> dict:
        """Run a Python file in the live editor: `py "<launcher>" <args>` typed into the editor console (the "Cmd" box)
        through SlateInspectorToolset, as review/ue_live.py does. The script writes `out` itself.

        The launcher (UE_PY_LAUNCHER) first writes `<out>.started`, then runs the script. SlateInspector's Type only
        warns ("Could not focus widget for typing") while another application holds the keyboard focus, and the
        Slate tree is empty while the editor window is not on the current desktop (both measured 2026-09-29 with a
        parallel session on the same desktop); the editor log does not prove a start either (a typed `py` command that
        ran had no `Cmd:` line). So: no started file within the grace time -> the command is typed again (at most 5
        times); a started command is never typed twice."""
        started = Path(str(out) + ".started")
        for stale in (out, started):
            if stale.exists():
                stale.unlink()
        launcher = script.with_name(script.stem + ".launch.py")
        launcher.write_text(UE_PY_LAUNCHER.replace("@STARTED@", started.as_posix()).replace("@TARGET@", script.as_posix()),
                            encoding="utf-8", newline="\n")
        command = 'py "%s" %s' % (launcher.as_posix(), args_path.as_posix())
        grace = float(os.environ.get("TRIPO_PIPELINE_CONSOLE_GRACE_S", "20"))
        for attempt in range(5):
            m = None
            for _ in range(24):
                snap = self.call("slate", "Snapshot", {"ref": "", "maxDepth": 60, "bIncludeSourceLocations": False})
                text = snap if isinstance(snap, str) else json.dumps(snap)
                i = text.find('text "Cmd"')
                m = re.search(r"textbox [^\n]*\[ref=(\w+)\]", text[i:i + 600]) if i >= 0 else None
                if m:
                    break
                time.sleep(5)
            if not m:
                raise PipelineError("editor console (Cmd box) not found through SlateInspector")
            self.call("slate", "Type", {"ref": m.group(1), "submit": True, "text": command})
            deadline = time.time() + grace
            while time.time() < deadline and not (started.exists() or out.exists()):
                time.sleep(0.25)
            if started.exists() or out.exists():
                break
            self.calls.append({"editor_python_retype": script.name, "attempt": attempt + 1})
        else:
            raise PipelineError("the editor console did not start %s after 5 attempts (focus)" % script.name)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if out.exists():
                time.sleep(0.3)
                try:
                    return json.loads(out.read_text(encoding="utf-8"))
                except ValueError:
                    pass
            time.sleep(0.5)
        raise PipelineError("editor python %s wrote no %s within %ss" % (script.name, out.name, timeout))

    def call(self, toolset_key: str, tool: str, args: dict):
        toolset = UE_TOOLSETS[toolset_key]
        styles = [self.tool_name_style] if self.tool_name_style else ["short", "qualified"]
        error = None
        for style in styles:
            name = tool if style == "short" else "%s.%s" % (toolset, tool)
            ok, payload = self._once(toolset, name, args)
            self.calls.append({"toolset": toolset, "tool": name, "args": args, "ok": ok,
                               "result": payload if ok else None, "error": None if ok else payload})
            if ok:
                self.tool_name_style = style
                return payload.get("returnValue") if isinstance(payload, dict) else payload
            error = payload
            if not re.search(r"not found|unknown tool|no tool|invalid tool", str(payload), re.I):
                break
        raise PipelineError("UE MCP %s.%s failed: %s" % (toolset, tool, str(error)[:600]))


# ------------------------------------------------------------------ source specs

def validate_spec(spec: dict) -> None:
    def fail(msg):
        raise PipelineError("source spec invalid: " + msg, EXIT_USAGE)

    if spec.get("schema") != SPEC_SCHEMA:
        fail("schema must be %s" % SPEC_SCHEMA)
    for key in ("source_id", "asset_id", "service", "task_id", "operations", "files"):
        if not spec.get(key):
            fail("missing %s" % key)
    if spec["service"] not in SERVICES:
        fail("service must be one of %s (Studio and API are tracked separately)" % sorted(SERVICES))
    unit = SERVICES[spec["service"]]
    gen = spec.get("generation")
    if gen is not None:
        mode = gen.get("mode")
        if mode == "batch":
            fail("'batch' is several independent tasks; register each Tripo task as its own source")
        if mode not in GENERATION_MODES:
            fail("generation.mode must be one of %s" % (GENERATION_MODES,))
        views = {k: v for k, v in (gen.get("views") or {}).items() if v}
        if mode == "multi-view" and len(views) < 2:
            fail("multi-view means one model from >=2 views of the same object")
        if mode != "multi-view" and len(views) > 1:
            fail("several views given for mode %s" % mode)
    for op in spec["operations"]:
        if not op.get("op"):
            fail("operation without 'op'")
        credits = op.get("credits") or {}
        if credits and credits.get("unit") != unit:
            fail("operation %s: credits.unit must be %s for %s (never mix Studio credits, API credits and USD)"
                 % (op["op"], unit, spec["service"]))
    roles = [f.get("role") for f in spec["files"]]
    if len(roles) != len(set(roles)) or not all(roles):
        fail("file roles must be unique and non-empty")


def build_source_record(ctx: Context, spec: dict) -> dict:
    files = []
    for entry in spec["files"]:
        path = ctx.repo_path(entry["path"])
        if not path.is_file():
            raise PipelineError("source file missing: %s" % entry["path"])
        if is_within(path, ctx.run_dir):
            raise PipelineError("Tripo originals must live outside the run directory: %s" % entry["path"])
        digest = sha256_file(path)
        size = path.stat().st_size
        expected = entry.get("expected_sha256")
        if expected and expected != digest:
            raise PipelineError("hash mismatch for %s: evidence %s, file %s" % (entry["path"], expected, digest))
        if entry.get("expected_bytes") is not None and entry["expected_bytes"] != size:
            raise PipelineError("size mismatch for %s: evidence %s, file %s" % (entry["path"], entry["expected_bytes"], size))
        record = {
            "role": entry["role"],
            "path": Path(entry["path"]).as_posix(),
            "sha256": digest,
            "bytes": size,
            "hash_check": "matches_evidence" if expected else "measured_at_registration_no_evidence_hash",
            "structure": inspect_file(path),
        }
        for key in ("produced_by", "origin"):
            if entry.get(key):
                record[key] = entry[key]
        files.append(record)
    evidence = []
    for rel in spec.get("evidence", []):
        path = ctx.repo_path(rel)
        if not path.is_file():
            raise PipelineError("evidence file missing: %s" % rel)
        evidence.append({"path": Path(rel).as_posix(), "sha256": sha256_file(path)})
    inputs = []
    for view, item in sorted(((spec.get("generation") or {}).get("views") or {}).items()):
        if not item:
            continue
        path = ctx.repo_path(item["path"])
        present = path.is_file()
        measured = sha256_file(path) if present else None
        if present and item.get("sha256") and measured != item["sha256"]:
            raise PipelineError("generation input %s changed since the Tripo task: %s" % (view, item["path"]))
        inputs.append({"view": view, "path": Path(item["path"]).as_posix(), "sha256": item.get("sha256"),
                       "present": present})
    credits_by_unit = {}
    for op in spec["operations"]:
        credits = op.get("credits") or {}
        if credits.get("observed_debit") is not None:
            credits_by_unit[credits["unit"]] = credits_by_unit.get(credits["unit"], 0) + credits["observed_debit"]
    return {
        "spec_sha256": sha256_json(spec),
        "spec": spec,
        "files": sorted(files, key=lambda f: f["role"]),
        "evidence": evidence,
        "generation_inputs": inputs,
        "historical_credits_observed": credits_by_unit,
        "registered_by": "%s %s" % (TOOL_NAME, TOOL_VERSION),
    }


def source_file(manifest: dict, source_id: str, role: str) -> dict:
    source = manifest["sources"].get(source_id)
    if not source:
        raise PipelineError("source %s is not registered" % source_id, EXIT_USAGE)
    for entry in source["files"]:
        if entry["role"] == role:
            return entry
    raise PipelineError("source %s has no file with role %s" % (source_id, role), EXIT_USAGE)


# ---------------------------------------------------------------------- profiles

def run_profile(manifest: dict) -> str:
    return manifest["config"].get("profile", PASSTHROUGH)


def base_stages(manifest: dict) -> tuple:
    return {CANDIDATE: CANDIDATE_STAGES, STATIC: STATIC_STAGES,
            SKELETAL_ADOPT: SKELETAL_ADOPT_STAGES}.get(run_profile(manifest), STAGES)


def stage_order(manifest: dict) -> tuple:
    return base_stages(manifest) + (UE_STAGE,)


def load_build_profile(ctx: "Context") -> tuple:
    rel = ctx.manifest["config"].get("build_profile")
    if not rel:
        raise PipelineError("run has no build profile (init --profile %s --build-profile ...)"
                            % "|".join(BUILD_PROFILE_KINDS), EXIT_USAGE)
    path = ctx.repo_path(rel)
    if not path.is_file():
        raise PipelineError("build profile missing: %s" % rel)
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("schema") != BUILD_PROFILE_SCHEMA:
        raise PipelineError("build profile schema must be %s: %s" % (BUILD_PROFILE_SCHEMA, rel), EXIT_USAGE)
    if profile.get("asset_id") != ctx.manifest["asset_id"]:
        raise PipelineError("build profile asset %s != run asset %s" % (profile.get("asset_id"), ctx.manifest["asset_id"]),
                            EXIT_USAGE)
    return profile, path


_PROFILE_SCHEMA = {}


def profile_schema():
    """blender/candidate_build/profile_schema.py (stdlib only; shared with the Blender build stage)."""
    if "module" not in _PROFILE_SCHEMA:
        import importlib.util
        path = BUILD_LIBRARY / "profile_schema.py"
        spec = importlib.util.spec_from_file_location("tripo_pipeline_profile_schema", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _PROFILE_SCHEMA["module"] = module
    return _PROFILE_SCHEMA["module"]


def build_library_hashes() -> dict:
    """SHA-256 of every module of the build library (part of the build fingerprint)."""
    return {p.name: sha256_file(p) for p in sorted(BUILD_LIBRARY.glob("*.py"))}


def build_reference_file(ctx: "Context", profile: dict):
    """The registered reference GLB of orientation.per_face_reference (None when the profile has none)."""
    ref = (profile.get("orientation") or {}).get("per_face_reference")
    if not ref:
        return None
    return source_file(ctx.manifest, ref["source_id"], ref["role"])


def profile_reference_hashes(ctx: "Context", profile: dict, keys) -> dict:
    """SHA-256 of the read-only reference files a profile compares against (None if absent)."""
    out = {}
    for rel in keys:
        path = ctx.repo_path(rel)
        out[rel] = sha256_file(path) if path.is_file() else None
    return out


def candidate_export_rels(profile: dict) -> dict:
    return {"skeletal": "export/%s" % profile["exports"]["skeletal_fbx"],
            "base": "export/%s" % profile["exports"]["base_fbx"]}


def fbx_preset(ctx: "Context") -> dict:
    """The FBX preset of this run: build profile `fbx_preset` (skeletal-candidate) or UM_FBX_v1 (passthrough).

    Returns {"rel", "path", "sha256", "name", "rotation_z"}; raises when missing or not UM_FBX_v1-shaped.
    """
    if run_profile(ctx.manifest) in BUILD_PROFILE_KINDS:
        profile, _ = load_build_profile(ctx)
        rel = profile.get("fbx_preset")
        if not rel:
            raise PipelineError("build profile %s has no fbx_preset; since tool 0.4.0 every candidate FBX follows "
                                "%s (04-blender-production.md §1.1, ART-001)" % (ctx.manifest["config"]["build_profile"],
                                                                                 DEFAULT_FBX_PRESET), EXIT_USAGE)
    else:
        rel = DEFAULT_FBX_PRESET
    path = ctx.repo_path(rel)
    if not path.is_file():
        raise PipelineError("FBX preset missing: %s" % rel)
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in FBX_PRESET_KEYS if k not in data]
    if missing:
        raise PipelineError("FBX preset %s lacks %s" % (rel, missing))
    return {"rel": Path(rel).as_posix(), "path": path, "sha256": sha256_file(path), "name": data["name"],
            "rotation_z": data["export_space_rotation_z_degrees"], "use_triangles": data["use_triangles"]}


# ------------------------------------------------------------------------ stages

class StageResult:
    def __init__(self, outputs: dict, summary: dict, passed: bool, error: str | None = None):
        self.outputs = outputs  # final relpath -> staging Path
        self.summary = summary
        self.passed = passed
        self.error = error


def run_blender(ctx: Context, stage: str, params: dict, staging: Path, marker: str) -> None:
    params_path = staging / "params.json"
    params_path.write_text(dump_json(params), encoding="utf-8")
    log_path = staging / ("%s.log" % stage)
    code, text = ctx.blender.run_stage(stage, params_path, staging)
    log_path.write_text(text, encoding="utf-8")
    # Blender can exit 0 after a Python error; require the marker and no traceback.
    if code != 0 or marker not in text or re.search(r"Traceback|Error: script failed", text):
        raise PipelineError("Blender stage %s failed (%s backend, exit %s); see %s"
                            % (stage, ctx.backend, code, log_path))


def blend_rel(manifest: dict) -> str:
    return "work/%s.blend" % manifest["config"]["export_basename"]


def fbx_rel(manifest: dict) -> str:
    return "export/%s.fbx" % manifest["config"]["export_basename"]


def stage_output_sha(manifest: dict, stage: str, rel: str) -> str | None:
    rec = manifest["stages"].get(stage) or {}
    out = (rec.get("outputs") or {}).get(rel)
    return out["sha256"] if out else None


_ATLAS_DEPS = {}


def atlas_python_deps() -> dict:
    """Pillow/numpy of the Python that runs the atlas stage (checked in a subprocess; this tool stays stdlib-only)."""
    if not _ATLAS_DEPS:
        code = ("import json, platform, PIL, numpy; print(json.dumps({'python': platform.python_version(), "
                "'pillow': PIL.__version__, 'numpy': numpy.__version__}))")
        try:
            proc = subprocess.run([sys.executable, "-c", code], capture_output=True, timeout=120, **_no_window())
            data = json.loads(proc.stdout.decode("utf-8").strip() or "{}")
            _ATLAS_DEPS.update(data, ok=proc.returncode == 0 and bool(data))
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            _ATLAS_DEPS.update(ok=False, error=str(exc))
    return dict(_ATLAS_DEPS)


def fp_preflight(ctx: Context) -> dict:
    m = ctx.manifest
    try:
        blender = ctx.blender_version()
    except PipelineError:
        blender = None  # reported as a failed check by exec_preflight
    return {
        "logic": PREFLIGHT_LOGIC_VERSION,
        "tool": TOOL_VERSION,
        "blender": blender,
        "backend": ctx.backend,
        "scripts": dict({k: sha256_file(v) for k, v in sorted(BLENDER_SCRIPTS.items())},
                        **{"build_library/" + k: v for k, v in build_library_hashes().items()}),
        "sources": {sid: {f["role"]: f["sha256"] for f in s["files"]} for sid, s in sorted(m["sources"].items())},
        "config": m["config"],
    }


def fp_import(ctx: Context) -> dict:
    m = ctx.manifest
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    return {"script": sha256_file(BLENDER_SCRIPTS["import"]), "blender": ctx.blender_version(),
            "backend": ctx.backend, "source_sha256": primary["sha256"], "blend": blend_rel(m)}


def fp_verify(ctx: Context) -> dict:
    m = ctx.manifest
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    spec = m["sources"][m["config"]["primary_source"]]["spec"]
    return {"logic": VERIFY_LOGIC_VERSION, "source_sha256": primary["sha256"],
            "import_report": stage_output_sha(m, "import", "reports/import-report.json"),
            "expectations": (spec.get("expectations") or {}).get(m["config"]["primary_role"]),
            "tolerance": m["config"]["triangle_loss_tolerance"]}


def fp_export(ctx: Context) -> dict:
    m = ctx.manifest
    preset = fbx_preset(ctx)
    return {"script": sha256_file(BLENDER_SCRIPTS["export"]), "blender": ctx.blender_version(),
            "backend": ctx.backend, "blend": stage_output_sha(m, "import", blend_rel(m)),
            "verify_report": stage_output_sha(m, "verify", "reports/verify-report.json"),
            "fbx": fbx_rel(m), "fbx_preset": {"path": preset["rel"], "sha256": preset["sha256"]}}


def exec_preflight(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    checks = {}

    def check(name, passed, **detail):
        checks[name] = dict(passed=bool(passed), **detail)

    check("python_version", sys.version_info >= (3, 10), measured=platform.python_version().rsplit(".", 1)[0])
    check("backend_known", ctx.backend in BACKENDS, measured=ctx.blender.describe())
    if ctx.backend == "mcp":
        check("blender_mcp_client_present", client_script(ctx.blender_mcp_cmd).is_file(),
              measured=client_script(ctx.blender_mcp_cmd).name)
    try:
        version = ctx.blender_version()
        check("blender_runnable", True, measured=version, backend=ctx.backend)
    except PipelineError as exc:
        check("blender_runnable", False, error=str(exc), backend=ctx.backend)
    ue_cfg = m["config"].get("ue")
    if ue_cfg:
        checks["ue_stage_runnable_with_backend"] = {
            "passed": True, "required": False, "measured": ctx.backend == "mcp",
            "note": "informational; ue-import runs only with --backend mcp (live editor via unreal_mcp.py)"}
        check("ue_folder_is_pipeline_candidate", ue_cfg["folder"].startswith(UE_ALLOWED_ROOT),
              measured=ue_cfg["folder"])
        if ctx.backend == "mcp":
            check("unreal_mcp_client_present", client_script(ctx.unreal_mcp_cmd).is_file(),
                  measured=client_script(ctx.unreal_mcp_cmd).name)
    checks["profile"] = {"passed": True, "required": False, "measured": run_profile(m)}
    if run_profile(m) == CANDIDATE:
        try:
            profile, ppath = load_build_profile(ctx)
            check("build_profile_valid", True, measured={"path": m["config"]["build_profile"],
                                                         "id": profile["profile_id"], "sha256": sha256_file(ppath)})
            check("build_profile_role_is_primary", profile["source_role"] == m["config"]["primary_role"],
                  measured=profile["source_role"], expected=m["config"]["primary_role"])
            problems = profile_schema().validate(profile)
            check("build_profile_schema", not problems, measured={"flow": profile_schema().flow_of(profile),
                                                                  "problems": problems},
                  note="blender/candidate_build/profile_schema.py (the build stage validates the same way)")
            ref = (profile.get("orientation") or {}).get("per_face_reference")
            if ref:
                try:
                    ref_file = build_reference_file(ctx, profile)
                    check("build_reference_source_registered", True,
                          measured="%s:%s %s" % (ref["source_id"], ref["role"], ref_file["path"]))
                except PipelineError as exc:
                    check("build_reference_source_registered", False, error=str(exc),
                          note="orientation.per_face_reference names a source that register-source must add first")
        except PipelineError as exc:
            check("build_profile_valid", False, error=str(exc))
        check("build_library_present", (BUILD_LIBRARY / "__init__.py").is_file() and BLENDER_SCRIPTS["build"].is_file(),
              measured={"library": build_library_hashes()})
        deps = atlas_python_deps()
        check("atlas_python_deps", deps.get("ok"), measured=deps)
    elif run_profile(m) == STATIC:
        try:
            profile, ppath = load_build_profile(ctx)
            check("build_profile_valid", profile.get("kind") == STATIC,
                  measured={"path": m["config"]["build_profile"], "id": profile["profile_id"],
                            "kind": profile.get("kind"), "sha256": sha256_file(ppath)}, expected={"kind": STATIC})
            check("build_profile_role_is_primary", profile["source_role"] == m["config"]["primary_role"],
                  measured=profile["source_role"], expected=m["config"]["primary_role"])
            missing = [rel for rel in static_candidate_files(profile).values() if not ctx.repo_path(rel).is_file()]
            check("static_candidate_files_present", not missing, missing=missing)
        except (PipelineError, KeyError) as exc:
            check("build_profile_valid", False, error=str(exc))
        check("candidate_scripts_present", ATLAS_SCRIPT.is_file() and BLENDER_SCRIPTS["build"].is_file(),
              scripts={"atlas": sha256_file(ATLAS_SCRIPT) if ATLAS_SCRIPT.is_file() else None})
    elif run_profile(m) == SKELETAL_ADOPT:
        try:
            profile, ppath = load_build_profile(ctx)
            check("build_profile_valid", profile.get("kind") == SKELETAL_ADOPT,
                  measured={"path": m["config"]["build_profile"], "id": profile["profile_id"],
                            "kind": profile.get("kind"), "sha256": sha256_file(ppath)}, expected={"kind": SKELETAL_ADOPT})
            check("build_profile_role_is_primary", profile["source_role"] == m["config"]["primary_role"],
                  measured=profile["source_role"], expected=m["config"]["primary_role"])
            sa = skeletal_adopt()
            sa.pointers(profile)  # the bake's report format is known
            missing = [rel for rel in sa.candidate_files(profile).values() if not ctx.repo_path(rel).is_file()]
            check("skeletal_candidate_files_present", not missing, missing=missing)
        except (PipelineError, KeyError) as exc:
            check("build_profile_valid", False, error=str(exc))
        except Exception as exc:  # noqa: BLE001 - skeletal_adopt.AdoptError (unknown report format)
            check("build_profile_valid", False, error="%s: %s" % (type(exc).__name__, exc))
        module = TOOL_DIR / "skeletal_adopt.py"
        check("skeletal_adopt_module_present", module.is_file(), measured=sha256_file(module) if module.is_file() else None)
    try:
        preset = fbx_preset(ctx)
        check("fbx_preset_is_um_fbx_v1", preset["name"] == FBX_PRESET_NAME and float(preset["rotation_z"]) == 90.0
              and preset["use_triangles"] is True,
              measured={k: preset[k] for k in ("rel", "sha256", "name", "rotation_z", "use_triangles")},
              expected={"name": FBX_PRESET_NAME, "rotation_z": 90.0, "use_triangles": True},
              note="axes standard 04-blender-production.md §1 (authored -Y -> UE +X), verified by ART-001")
    except PipelineError as exc:
        check("fbx_preset_is_um_fbx_v1", False, error=str(exc))
    ue_cmd = Path(os.environ.get("TRIPO_PIPELINE_UE_ROOT", DEFAULT_UE_ROOT)) / "Engine/Binaries/Win64/UnrealEditor-Cmd.exe"
    checks["unreal_editor_cmd_present"] = {"passed": True, "required": False, "measured": ue_cmd.is_file(),
                                           "note": "informational; this scaffold never launches UnrealEditor-Cmd"}
    check("repo_root_is_git_checkout", (ctx.repo_root / ".git").exists())
    check("blender_stage_scripts_present", all(p.is_file() for p in BLENDER_SCRIPTS.values()),
          scripts={k: sha256_file(v) if v.is_file() else None for k, v in sorted(BLENDER_SCRIPTS.items())})
    check("sources_registered", bool(m["sources"]), measured=sorted(m["sources"]))
    try:
        source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
        check("primary_source_registered", True, measured="%s:%s" % (m["config"]["primary_source"], m["config"]["primary_role"]))
    except PipelineError as exc:
        check("primary_source_registered", False, error=str(exc))
    unchanged, missing, changed, inside = [], [], [], []
    for sid, src in sorted(m["sources"].items()):
        for entry in src["files"]:
            path = ctx.repo_path(entry["path"])
            tag = "%s:%s" % (sid, entry["role"])
            if not path.is_file():
                missing.append(tag)
            elif sha256_file(path) != entry["sha256"]:
                changed.append(tag)
            else:
                unchanged.append(tag)
            if is_within(path, ctx.run_dir):
                inside.append(tag)
    check("source_files_present", not missing, missing=missing)
    check("source_files_unchanged_since_registration", not changed and not missing, changed=changed,
          verified=len(unchanged))
    check("originals_outside_run_dir", not inside, offenders=inside)
    own = Path(__file__).read_text(encoding="utf-8")
    net = re.findall(r"^\s*(?:import|from)\s+(urllib|http|socket|requests|ssl|ftplib|asyncio)\b", own, re.M)
    check("tool_has_no_network_imports", not net, measured=sorted(set(net)))
    passed = all(c["passed"] for c in checks.values())
    report = {"stage": "preflight", "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
              "backend": ctx.backend, "checks": checks, "passed": passed,
              "network": {"tripo_calls": 0, "paid_tasks_created": 0}}
    out = staging / "preflight.json"
    out.write_text(dump_json(report), encoding="utf-8")
    try:
        usage = shutil.disk_usage(ctx.run_dir)
        ctx.journal("preflight_disk", free_gb=round(usage.free / 1e9, 1))
    except OSError:
        pass
    failed = sorted(k for k, c in checks.items() if not c["passed"])
    return StageResult({"reports/preflight.json": out},
                       {"passed": passed, "failed_checks": failed, "sources_verified": len(unchanged)},
                       passed, None if passed else "preflight failed: %s" % ", ".join(failed))


def exec_import(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    source = ctx.repo_path(primary["path"])
    if sha256_file(source) != primary["sha256"]:
        raise PipelineError("primary source changed since registration: %s" % primary["path"])
    blend = staging / "work.blend"
    report = staging / "import-report.json"
    run_blender(ctx, "import", {"source": str(source), "blend_out": str(blend), "report_out": str(report)},
                staging, "TRIPO_PIPELINE_STAGE_OK import")
    data = json.loads(report.read_text(encoding="utf-8"))
    if data["source"]["sha256"] != primary["sha256"]:
        raise PipelineError("import report refers to a different source hash")
    return StageResult({blend_rel(m): blend, "reports/import-report.json": report},
                       {"mesh_count": data["mesh_count"], "triangles_total": data["triangles_total"],
                        "materials": data["material_count"], "images": data["image_count"]}, True)


def exec_verify(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    sid, role = m["config"]["primary_source"], m["config"]["primary_role"]
    primary = source_file(m, sid, role)
    spec = m["sources"][sid]["spec"]
    expect = (spec.get("expectations") or {}).get(role) or {}
    imp = json.loads(ctx.run_path("reports/import-report.json").read_text(encoding="utf-8"))
    source_path = ctx.repo_path(primary["path"])
    glb = inspect_glb(source_path)
    checks, warnings = {}, []

    def check(name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    check("source_unchanged", sha256_file(source_path) == primary["sha256"], primary["sha256"])
    check("import_report_matches_source", imp["source"]["sha256"] == primary["sha256"], imp["source"]["sha256"])
    for key, measured in (("glb_mesh_count", glb["mesh_count"]), ("glb_triangles", glb["triangles"]),
                          ("glb_materials", glb["materials"]), ("glb_images", glb["images"]),
                          ("glb_skins", glb["skins"])):
        if key in expect:
            check("evidence_" + key, measured == expect[key], measured, expect[key],
                  "expected value copied from Tripo evidence JSON")
    check("blender_mesh_count_equals_glb", imp["mesh_count"] == glb["mesh_count"], imp["mesh_count"], glb["mesh_count"])
    lost = glb["triangles"] - imp["triangles_total"]
    tolerance = m["config"]["triangle_loss_tolerance"]
    per_mesh = {mesh["name"]: mesh["triangles"] for mesh in glb["meshes"]}
    deltas = {e["name"]: e["triangles"] - per_mesh.get(e["name"], 0) for e in imp["meshes"]
              if e["name"] in per_mesh and e["triangles"] != per_mesh[e["name"]]}
    check("blender_triangle_loss_within_tolerance",
          0 <= lost <= glb["triangles"] * tolerance,
          {"glb": glb["triangles"], "blender": imp["triangles_total"], "lost": lost, "per_mesh_delta": deltas},
          "<= %.3f%% of GLB triangles" % (tolerance * 100),
          "Blender glTF importer can drop degenerate/duplicate triangles; listed per mesh")
    if lost:
        warnings.append("Blender imported %d fewer triangles than the GLB declares: %s" % (lost, deltas))
    no_uv = [e["name"] for e in imp["meshes"] if not e["uv_layers"]]
    check("uv0_on_every_mesh", not no_uv, {"meshes_without_uv": no_uv})
    expected_arm = expect.get("armatures", 0)
    check("armatures_as_expected", imp["armatures"] == expected_arm, imp["armatures"], expected_arm)
    dims = imp["bounds"]["dimensions"]
    check("bounds_non_degenerate", all(d > 0 for d in dims), dims)
    diag = {e["name"]: e["diagnostic_weld_1e-7"] for e in imp["meshes"]}
    open_meshes = sorted(n for n, d in diag.items() if d["boundary_edges"] or d["non_manifold_edges"])
    if open_meshes:
        warnings.append("open/non-manifold edges after diagnostic weld in %d mesh(es); informational" % len(open_meshes))
    passed = all(c["passed"] for c in checks.values())
    report = {
        "stage": "verify",
        "logic": VERIFY_LOGIC_VERSION,
        "status": "measured" if passed else "failed",
        "source": {"source_id": sid, "role": role, "path": primary["path"], "sha256": primary["sha256"]},
        "glb_structure": {k: glb[k] for k in ("generator", "mesh_count", "triangles", "materials", "images",
                                              "skins", "animations", "primitive_modes")},
        "checks": checks,
        "passed": passed,
        "warnings": warnings,
        "diagnostics": {"bounds_source_units": imp["bounds"], "weld_1e-7_per_mesh": diag,
                        "degenerate_faces_total": sum(e["degenerate_faces"] for e in imp["meshes"])},
        "not_checked": [
            "budgets: numbers are measured only; budgets stay proposals until GD-058 is decided",
            "art acceptance, silhouette, lighting: art track",
            "rig, sockets, animation, UE import: later candidate stages",
        ],
    }
    out = staging / "verify-report.json"
    out.write_text(dump_json(report), encoding="utf-8")
    failed = sorted(k for k, c in checks.items() if not c["passed"])
    return StageResult({"reports/verify-report.json": out},
                       {"passed": passed, "failed_checks": failed, "warnings": len(warnings)},
                       passed, None if passed else "verify failed: %s" % ", ".join(failed))


def exec_export(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    blend = ctx.run_path(blend_rel(m))
    fbx = staging / Path(fbx_rel(m)).name  # same file name as the final export (FBX stores it)
    report = staging / "export-report.json"
    run_blender(ctx, "export", {"blend": str(blend), "fbx_out": str(fbx), "report_out": str(report),
                                "fbx_preset": str(fbx_preset(ctx)["path"])},
                staging, "TRIPO_PIPELINE_STAGE_OK export")
    data = json.loads(report.read_text(encoding="utf-8"))
    return StageResult({fbx_rel(m): fbx, "reports/export-report.json": report},
                       {"passed": data["passed"], "fbx_sha256": sha256_file(fbx), "fbx_bytes": fbx.stat().st_size,
                        "roundtrip_triangles": data["roundtrip_reimport"]["triangles_total"]},
                       data["passed"], None if data["passed"] else "export round-trip failed")


# ------------------------------------------------- skeletal-candidate: atlas, build

def fp_atlas(ctx: Context) -> dict:
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    refs = (profile["atlas"].get("reference_textures") or {}).values()
    deps = atlas_python_deps()
    fp = {"script": sha256_file(ATLAS_SCRIPT), "deps": {k: deps.get(k) for k in ("python", "pillow", "numpy")},
          "source_sha256": primary["sha256"], "profile_sha256": sha256_file(ppath),
          "references": profile_reference_hashes(ctx, profile, sorted(refs))}
    if profile["atlas"].get("ao_bake"):
        # 0.6.0: the AO bake is part of the atlas stage (headless Blender; its script and version decide the bytes).
        # It applies the build's orientation fixes with the build library's code (orientation, weld, flip, ray-escape
        # measure; W4-B review fix) and, for orientation.per_face_reference, reads the registered reference GLB
        ref_glb = build_reference_file(ctx, profile)
        fp["ao_bake"] = {"script": sha256_file(BLENDER_SCRIPTS["ao_bake"]),
                         "library": {k: v for k, v in build_library_hashes().items() if k in AO_BAKE_LIBRARY},
                         "reference_glb_sha256": ref_glb["sha256"] if ref_glb else None,
                         "blender": HeadlessBlender(ctx.blender_cmd).version()}
    return fp


# build-library modules the AO bake imports (their bytes are part of the atlas fingerprint)
AO_BAKE_LIBRARY = ("__init__.py", "core.py", "measure.py", "mesh_ops.py", "orientation.py")


def ao_bake_params(profile: dict) -> dict:
    """atlas.ao_bake -> bake_ao.py params (everything but paths). Parts = the atlas parts (all mesh nodes of the GLB
    minus atlas.exclude_parts); occluders_excluded = meshes.drop_parts unless the profile names its own list;
    flip_parts = the whole-part entries of orientation.expected_inside_out_parts (the build flips them);
    per_face_reference = orientation.per_face_reference with the build's weld distance and seat numbers (flow
    seated-parts only: the build applies it there, on the welded part in the seat frame)."""
    cfg = profile["atlas"]["ao_bake"]
    drops = (profile.get("meshes") or {}).get("drop_parts") or {}
    ocfg = profile.get("orientation") or {}
    inside_out = ocfg.get("expected_inside_out_parts") or []
    out = {"samples": int(cfg.get("samples", 128)), "distance_rel": float(cfg.get("distance_rel", 0.08)),
           "margin_px": int(cfg.get("margin_px", 8)), "seed": int(cfg.get("seed", 0)),
           "exclude_parts": sorted(profile["atlas"].get("exclude_parts") or {}),
           "occluders_excluded": sorted(cfg["occluders_excluded"] if "occluders_excluded" in cfg else drops),
           "flip_parts": sorted(p for p in inside_out if re.fullmatch(r"tripo_part_\d+", p)),
           "per_face_reference": None}
    ref = ocfg.get("per_face_reference")
    if ref:
        flow = (profile.get("build") or {}).get("flow")
        if flow != "seated-parts":
            raise PipelineError("atlas.ao_bake with orientation.per_face_reference needs build.flow seated-parts "
                                "(found %r): the bake repeats that flow's per-face fix" % flow, EXIT_USAGE)
        base = profile["meshes"]["base"]
        out["per_face_reference"] = {
            "parts": list(ref["parts"]), "max_reference_distance_m": ref["max_reference_distance_m"],
            "smoothing_lambda": ref["smoothing_lambda"], "smoothing_max_sweeps": ref["smoothing_max_sweeps"],
            "weld_distance_m": profile["weld"]["distance_m"],
            "seat": {"base_part": base["part"] if base["mode"] == "normalise-part" else base["source_part"],
                     "top_part": profile["scale"]["top_part"], "figure_height_m": profile["scale"]["figure_height_m"],
                     "base_height_m": base["footprint_m"][2]}}
    return out


def run_ao_bake(ctx: Context, profile: dict, source: Path, staging: Path) -> dict:
    """Headless Blender Cycles AO per atlas part (blender/bake_ao.py). Always a separate process, also under
    --backend mcp: it produces bytes and must not touch the live session."""
    out_dir = staging / "ao"
    report = staging / "ao-bake-report.json"
    params = dict(ao_bake_params(profile), source=str(source), out_dir=str(out_dir), report_out=str(report),
                  lib_dir=str(BLENDER_SCRIPTS["ao_bake"].parent))
    if params["per_face_reference"]:
        ref_glb = build_reference_file(ctx, profile)
        ref_path = ctx.repo_path(ref_glb["path"])
        if not ref_path.is_file() or sha256_file(ref_path) != ref_glb["sha256"]:
            raise PipelineError("reference GLB of orientation.per_face_reference missing or changed since "
                                "registration: %s" % ref_glb["path"])
        params["per_face_reference"] = dict(params["per_face_reference"], reference_glb=str(ref_path))
    params_path = staging / "ao-params.json"
    params_path.write_text(dump_json(params), encoding="utf-8")
    code, text = HeadlessBlender(ctx.blender_cmd).run_stage("ao_bake", params_path, staging)
    (staging / "ao_bake.log").write_text(text, encoding="utf-8")
    if code != 0 or "TRIPO_PIPELINE_STAGE_OK ao_bake" not in text:
        raise PipelineError("AO bake failed (exit %s); see %s" % (code, staging / "ao_bake.log"))
    data = json.loads(report.read_text(encoding="utf-8"))
    for part, info in data["parts"].items():
        if sha256_file(out_dir / info["file"]) != info["sha256"]:
            raise PipelineError("AO bake report hash mismatch for %s" % part)
    return {"dir": str(out_dir), "report": str(report)}


def exec_atlas(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    source = ctx.repo_path(primary["path"])
    if sha256_file(source) != primary["sha256"]:
        raise PipelineError("primary source changed since registration: %s" % primary["path"])
    out_dir = staging / "textures"
    report = staging / "atlas-report.json"
    params = {"source": str(source), "profile": str(ppath), "out_dir": str(out_dir), "report_out": str(report),
              "repo_root": str(ctx.repo_root)}
    ao = run_ao_bake(ctx, profile, source, staging) if profile["atlas"].get("ao_bake") else None
    if ao:
        params["ao"] = ao
    params_path = staging / "params.json"
    params_path.write_text(dump_json(params), encoding="utf-8")
    log_path = staging / "atlas.log"
    try:
        proc = subprocess.run([sys.executable, str(ATLAS_SCRIPT), str(params_path)], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=ATLAS_TIMEOUT_S, **_no_window())
        code, text = proc.returncode, proc.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as exc:
        code, text = -1, (exc.stdout or b"").decode("utf-8", "replace") + "\n[tripo-pipeline] TIMEOUT\n"
    log_path.write_text(text, encoding="utf-8")
    if code != 0 or "TRIPO_PIPELINE_STAGE_OK atlas" not in text or "Traceback" in text:
        raise PipelineError("atlas stage failed (exit %s); see %s" % (code, log_path))
    data = json.loads(report.read_text(encoding="utf-8"))
    outputs = {"reports/atlas-report.json": report}
    if ao:
        outputs["reports/ao-bake-report.json"] = Path(ao["report"])
    for key, info in sorted(data["files"].items()):
        path = out_dir / info["file"]
        if sha256_file(path) != info["sha256"]:
            raise PipelineError("atlas report hash mismatch for %s" % info["file"])
        outputs["textures/%s" % info["file"]] = path
    refs = {k: v.get("bytes_identical") for k, v in (data.get("reference_comparison") or {}).items()}
    return StageResult(outputs, {"passed": data["passed"], "files": {k: v["sha256"][:12] for k, v in data["files"].items()},
                                 "reference_bytes_identical": refs},
                       data["passed"], None if data["passed"] else "atlas checks failed")


def candidate_blend_rel(manifest: dict) -> str:
    return "work/%s-candidate.blend" % manifest["config"]["export_basename"]


def fp_build(ctx: Context) -> dict:
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    atlas_outputs = (m["stages"].get("atlas") or {}).get("outputs") or {}
    ref = profile.get("reference") or {}
    ref_glb = build_reference_file(ctx, profile)
    return {"script": sha256_file(BLENDER_SCRIPTS["build"]), "library": build_library_hashes(),
            "blender": ctx.blender_version(), "backend": ctx.backend,
            "source_sha256": primary["sha256"], "profile_sha256": sha256_file(ppath),
            "reference_glb_sha256": ref_glb["sha256"] if ref_glb else None,
            "atlas_outputs": {k: v["sha256"] for k, v in sorted(atlas_outputs.items())},
            "references": profile_reference_hashes(ctx, profile, sorted(v for k, v in ref.items()
                                                                        if k in ("skeletal_fbx", "base_fbx"))),
            "exports": candidate_export_rels(profile), "blend": candidate_blend_rel(m),
            "fbx_preset": {k: v for k, v in fbx_preset(ctx).items() if k in ("rel", "sha256")}}


def exec_build(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    source = ctx.repo_path(primary["path"])
    if sha256_file(source) != primary["sha256"]:
        raise PipelineError("primary source changed since registration: %s" % primary["path"])
    atlas_rec = m["stages"].get("atlas") or {}
    for rel, info in (atlas_rec.get("outputs") or {}).items():
        path = ctx.run_path(rel)
        if not path.is_file() or sha256_file(path) != info["sha256"]:
            raise PipelineError("atlas output missing or changed since the atlas stage: %s" % rel)
    rels = candidate_export_rels(profile)
    sk = staging / Path(rels["skeletal"]).name  # same file name as the final export
    base = staging / Path(rels["base"]).name
    blend = staging / "work.blend"
    report = staging / "build-report.json"
    problems = profile_schema().validate(profile)
    if problems:
        raise PipelineError("build profile invalid (%s): %s" % (m["config"]["build_profile"], "; ".join(problems)))
    params = {"source": str(source), "profile": str(ppath), "atlas_report": str(ctx.run_path("reports/atlas-report.json")),
              "textures_dir": str(ctx.run_path("textures")), "repo_root": str(ctx.repo_root),
              "blend_out": str(blend), "sk_fbx_out": str(sk), "base_fbx_out": str(base), "report_out": str(report),
              "fbx_preset": str(fbx_preset(ctx)["path"]), "lib_dir": str(BLENDER_SCRIPTS["build"].parent)}
    ref_glb = build_reference_file(ctx, profile)
    if ref_glb:
        ref_path = ctx.repo_path(ref_glb["path"])
        if not ref_path.is_file() or sha256_file(ref_path) != ref_glb["sha256"]:
            raise PipelineError("reference GLB of orientation.per_face_reference missing or changed since "
                                "registration: %s" % ref_glb["path"])
        params["reference_glb"] = str(ref_path)
    run_blender(ctx, "build", params, staging, "TRIPO_PIPELINE_STAGE_OK build")
    data = json.loads(report.read_text(encoding="utf-8"))
    for key, path in (("skeletal", sk), ("base", base)):
        if sha256_file(path) != data["exports"][key]["sha256"]:
            raise PipelineError("build report hash mismatch for %s" % path.name)
    failed = sorted(k for k, c in data["checks"].items() if not c["passed"])
    return StageResult({rels["skeletal"]: sk, rels["base"]: base, candidate_blend_rel(m): blend,
                        "reports/build-report.json": report},
                       {"passed": data["passed"], "failed_checks": failed,
                        "flow": data.get("flow"),
                        "skeletal_fbx_sha256": data["exports"]["skeletal"]["sha256"],
                        "base_fbx_sha256": data["exports"]["base"]["sha256"],
                        "flipped_parts": data["orientation"]["flipped_parts"],
                        "export_front_axis": ((data.get("axes") or {}).get("export_frame") or {}).get("front_axis")
                        or (data.get("axes") or {}).get("export_front_axis"),
                        "figure_top_m": (data.get("figure") or {}).get("figure_top_m"),
                        "skeletal_top_m": (data.get("figure") or {}).get("skeletal_top_m"),
                        "live_name_collisions": data.get("live_name_collisions")},
                       data["passed"], None if data["passed"] else "build checks failed: %s" % ", ".join(failed))


# ----------------------------------------------------------------- UE (MCP only)

def ue_safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def ue_package(ref) -> str:
    """'/Game/A/B.B', "StaticMesh'/Game/A/B.B'", {'refPath': ...} -> '/Game/A/B'."""
    if isinstance(ref, dict):
        ref = ref.get("refPath", "")
    ref = str(ref).strip()
    quoted = re.search(r"'(/[^']+)'", ref)
    if quoted:
        ref = quoted.group(1)
    return ref.split(":")[0].split(".")[0]


def ue_object_path(package: str) -> str:
    return "%s.%s" % (package, package.rsplit("/", 1)[-1])


def default_ue_folder(manifest: dict) -> str:
    parts = manifest["asset_id"].split("-")
    short = parts[1].title() if len(parts) >= 3 else ue_safe(manifest["asset_id"])
    return "%s%s/%s" % (UE_ALLOWED_ROOT, ue_safe(short), ue_safe(manifest["run_id"]))


def ue_listing(ue, folder: str) -> list:
    found = ue.call("asset", "find_assets", {"folder_path": folder, "name": "", "recursive": True}) or []
    return sorted(ue_package(a) for a in found)


def ue_plan(ctx: Context) -> dict:
    m = ctx.manifest
    cfg = m["config"].get("ue")
    if not cfg:
        raise PipelineError("UE stage is not configured; run `ue-import` once with --ue-folder", EXIT_USAGE)
    folder = cfg["folder"].rstrip("/")
    if not (folder + "/").startswith(UE_ALLOWED_ROOT) or ".." in folder:
        raise PipelineError("UE folder must be inside %s (never /Game/ART004 or /Game/ArtPreview): %s"
                            % (UE_ALLOWED_ROOT, folder), EXIT_USAGE)
    if run_profile(m) == STATIC:
        profile, _ = load_build_profile(ctx)
        u = profile["ue"]
        names = {"static": "%s/Meshes/%s" % (folder, u["static_asset"]),
                 "material": "%s/Materials/%s" % (folder, u["material"]),
                 "instance": "%s/Materials/%s" % (folder, u["instance"])}
        for key, tex in u["textures"].items():
            names["texture:" + key] = "%s/Textures/%s" % (folder, tex["asset"])
        return {"folder": folder, "name": u["static_asset"], "kind": STATIC, "primary": names["static"],
                "names": names, "profile": profile}
    if run_profile(m) in SKELETAL_KINDS:
        profile, _ = load_build_profile(ctx)
        u = profile["ue"]
        names = {"skeletal": "%s/Meshes/%s" % (folder, u["skeletal_asset"]),
                 "skeleton": "%s/Meshes/%s_Skeleton" % (folder, u["skeletal_asset"]),
                 "base": "%s/Meshes/%s" % (folder, u["base_asset"])}
        target_skeleton = target_skeleton_of(u, folder)
        if target_skeleton:
            # 0.8.0: the mesh goes onto an existing canonical skeleton outside the run folder; the run never creates,
            # owns or deletes a Skeleton asset
            del names["skeleton"]
        if material_route(u) == "um-master":
            # 0.6.0 (W4-B): one MI per asset for the figure (parent M_UM_Figure) and one for the base (parent
            # M_UM_BaseMarker), team MIs as their children; no own Material in the run folder
            names["figure_instance"] = "%s/Materials/%s" % (folder, u["figure_instance"])
            names["base_instance"] = "%s/Materials/%s" % (folder, u["base_instance"])
            for team in u["teams"]:
                for part in ("figure", "base"):
                    names["team:%s:%s" % (part, team)] = "%s/Materials/%s" % (
                        folder, u["team_instances"][part].format(team=team))
            for extra in u.get("extra_instances") or []:
                # LD-merlin-ue: further MIs under the figure/base MI (neutral = no dye, debug views of M_UM_Figure_v2)
                names["extra:" + extra["asset"]] = "%s/Materials/%s" % (folder, extra["asset"])
        else:
            names["material"] = "%s/Materials/%s" % (folder, u["material"])
            if u.get("base_material_mode", "atlas-instance") == "vertex-mask":
                names["base_material"] = "%s/Materials/%s" % (folder, u["base_material"])
            for name in u["instances"]:
                names["instance:" + name] = "%s/Materials/%s" % (folder, name)
        if run_profile(m) == SKELETAL_ADOPT:
            # every texture of the adopted candidate is pinned by adopt (candidate.textures)
            atlas_files = {k: {"file": v} for k, v in profile["candidate"]["textures"].items()}
            atlas_files.update({k: {"file": v["path"]} for k, v in
                                (profile["candidate"].get("library_inputs") or {}).items()})
        else:
            atlas_path = ctx.run_path("reports/atlas-report.json")
            atlas_files = json.loads(atlas_path.read_text(encoding="utf-8"))["files"] if atlas_path.is_file() else {}
        for key, tex in u["textures"].items():
            if tex.get("optional") and tex["file_key"] not in atlas_files:
                continue  # optional input the atlas stage did not produce (e.g. no team_color.mask)
            names["texture:" + key] = "%s/Textures/%s" % (folder, tex["asset"])
        return {"folder": folder, "name": u["skeletal_asset"], "kind": "skeletal", "primary": names["skeletal"],
                "names": names, "profile": profile, "target_skeleton": target_skeleton}
    export_report = json.loads(ctx.run_path("reports/export-report.json").read_text(encoding="utf-8"))
    kind = "skeletal" if export_report["roundtrip_reimport"]["armatures"] else "static"
    name = cfg.get("asset_name") or "%s_%s" % ("SK" if kind == "skeletal" else "SM",
                                               ue_safe(m["config"]["export_basename"]))
    return {"folder": folder, "name": name, "kind": kind, "primary": "%s/%s" % (folder, name),
            "export_report": export_report}


def target_skeleton_of(u: dict, folder: str):
    """ue.target_skeleton of a skeletal-adopt profile (0.8.0): the canonical skeleton of the hero, e.g.
    /Game/PipelineCandidates/<Hero>/Rig/SK_<Hero>_Skeleton. It must lie under UE_ALLOWED_ROOT and OUTSIDE the run
    folder (the run deletes and re-creates everything in its folder; a shared skeleton must survive a reimport)."""
    path = u.get("target_skeleton")
    if not path:
        return None
    path = ue_package(path)
    if not (path + "/").startswith(UE_ALLOWED_ROOT) or ".." in path:
        raise PipelineError("ue.target_skeleton must be inside %s: %s" % (UE_ALLOWED_ROOT, path), EXIT_USAGE)
    if (path + "/").startswith(folder.rstrip("/") + "/"):
        raise PipelineError("ue.target_skeleton must lie outside the run folder %s (the run deletes its folder "
                            "content on reimport): %s" % (folder, path), EXIT_USAGE)
    return path


def fp_ue_import(ctx: Context) -> dict:
    m = ctx.manifest
    if run_profile(m) == STATIC:
        _, ppath = load_build_profile(ctx)
        return {"logic": UE_STATIC_LOGIC_VERSION, "backend": ctx.backend, "ue": m["config"].get("ue"),
                "profile_sha256": sha256_file(ppath),
                "adopt_report": stage_output_sha(m, "adopt", "reports/adopt-report.json")}
    if run_profile(m) == SKELETAL_ADOPT:
        _, ppath = load_build_profile(ctx)
        return {"logic": UE_SKELETAL_ADOPT_LOGIC_VERSION, "candidate_logic": UE_CANDIDATE_LOGIC_VERSION,
                "backend": ctx.backend, "ue": m["config"].get("ue"), "profile_sha256": sha256_file(ppath),
                "adopt_report": stage_output_sha(m, "adopt", "reports/adopt-report.json")}
    if run_profile(m) == CANDIDATE:
        profile, ppath = load_build_profile(ctx)
        outs = {}
        for stage in ("atlas", "build"):
            outs.update({k: v["sha256"] for k, v in ((m["stages"].get(stage) or {}).get("outputs") or {}).items()
                         if not k.startswith("work/")})
        return {"logic": UE_CANDIDATE_LOGIC_VERSION, "backend": ctx.backend, "ue": m["config"].get("ue"),
                "profile_sha256": sha256_file(ppath), "inputs": dict(sorted(outs.items()))}
    return {"logic": UE_IMPORT_LOGIC_VERSION, "backend": ctx.backend, "ue": m["config"].get("ue"),
            "fbx": stage_output_sha(m, "export", fbx_rel(m)),
            "export_report": stage_output_sha(m, "export", "reports/export-report.json")}


def probe_ue_import(ctx: Context, rec: dict) -> bool:
    """A completed UE stage is only up to date if the editor still has exactly our assets."""
    ue = ctx.unreal()
    plan = ue_plan(ctx)
    owned = sorted(rec.get("ue_owned_assets") or [])
    listing = ue_listing(ue, plan["folder"])
    intact = bool(ue.call("asset", "exists", {"path": plan["primary"]})) and listing == owned
    if not intact:
        ctx.journal("ue_probe_mismatch", expected=owned, found=listing)
    return intact


def within(measured, expected, tolerance) -> bool:
    return expected is not None and measured is not None and abs(measured - expected) <= abs(expected) * tolerance


UE_TEAM_COLOR_MODES = ("multiply", "mask", "none")  # skeletal-candidate atlas material (ue.team_color_mode)
UE_BASE_MATERIAL_MODES = ("atlas-instance", "vertex-mask")  # base material (ue.base_material_mode)
UE_MATERIAL_ROUTES = ("own-material", "um-master")  # ue.material_route (0.6.0; absent = own-material)


def material_route(u: dict) -> str:
    route = u.get("material_route", "own-material")
    if route not in UE_MATERIAL_ROUTES:
        raise PipelineError("ue.material_route must be one of %s" % (UE_MATERIAL_ROUTES,), EXIT_USAGE)
    return route


def um_masters():
    """tools/tripo-pipeline/um_masters.py (spec, graphs, FromSRGBColor); imported on use."""
    import um_masters as module
    return module


def team_linear(value) -> list:
    """Profile team colour ('#RRGGBB' sRGB or {"linear": [...]}) -> linear RGBA (FLinearColor::FromSRGBColor)."""
    try:
        return um_masters().colour_value(value)
    except ValueError as exc:
        raise PipelineError(str(exc), EXIT_USAGE)


def um_master_instances(ue, u, names, textures, tex_path, team_mode, base_mode, track) -> dict:
    """Route um-master: MI of the figure (parent M_UM_Figure: BC/N/ORM + TeamMask per team_color_mode + scalar
    knobs), MI of the base (parent M_UM_BaseMarker: atlas textures or flat colour, band/pip parameters) and one team MI
    per team under each (TeamColor = FromSRGBColor(hex)). Nothing is built in the run folder but these MIs."""
    um = um_masters()
    spec, _ = um.load_spec(TOOL_DIR.parents[1])
    masters = u.get("masters") or {}
    fig_master = masters.get("figure") or um.master_path(spec, "figure")
    base_master = masters.get("base") or um.master_path(spec, "base_marker")
    for m in (fig_master, base_master):
        if not ue.call("asset", "exists", {"path": m}):
            raise PipelineError("master %s is missing: build it first (python tools/tripo-pipeline/um_masters.py "
                                "--backend mcp build --report ...)" % m)
    plan = {"figure_master": fig_master, "base_master": base_master, "instances": {}}

    def create(key, parent_pkg):
        pkg = names[key]
        track(ue.call("instance", "create", {"folder_path": pkg.rsplit("/", 1)[0], "asset_name": pkg.rsplit("/", 1)[1],
                                             "parent": ue_obj(parent_pkg)}))
        plan["instances"][key] = {"asset": pkg, "parent": parent_pkg, "textures": {}, "scalars": {}, "vectors": {},
                                  "switches": {}}
        return ue_obj(pkg)

    def set_tex(key, name, tex_pkg):
        ue.call("instance", "set_texture_parameter", {"instance": ue_obj(names[key]), "name": name,
                                                      "value": {"refPath": ue_object_path(tex_pkg)}})
        plan["instances"][key]["textures"][name] = tex_pkg

    def set_scalar(key, name, value):
        ue.call("instance", "set_scalar_parameter", {"instance": ue_obj(names[key]), "name": name, "value": float(value)})
        plan["instances"][key]["scalars"][name] = float(value)

    def set_vector(key, name, lin):
        ue.call("instance", "set_vector_parameter", {"instance": ue_obj(names[key]), "name": name,
                                                     "value": dict(zip("rgba", lin))})
        plan["instances"][key]["vectors"][name] = [round(v, 6) for v in lin]

    tex_pkg = {k: names["texture:" + k] for k in textures}
    # figure
    create("figure_instance", fig_master)
    for key, pname in (("BC", "BaseColorTexture"), ("N", "NormalTexture"), ("ORM", "ORMTexture")):
        set_tex("figure_instance", pname, tex_pkg[key])
    mask_tex = {"multiply": um.texture_path(spec, "TeamMask"), "none": um.texture_path(spec, "TeamMaskNone")}.get(team_mode)
    if team_mode == "mask":
        if "TeamMask" not in textures:
            raise PipelineError("ue.team_color_mode mask needs the TeamMask texture (team_color.mask of the atlas stage "
                                "and ue.textures.TeamMask)")
        mask_tex = tex_pkg["TeamMask"]
    set_tex("figure_instance", "TeamMaskTexture", mask_tex)
    for name, value in sorted((u.get("figure_parameters") or {}).items()):
        set_scalar("figure_instance", name, value)
    # LD-merlin-ue (M_UM_Figure_v2): extra texture parameters of the figure MI (MatIDTexture, MatLUT, EdgeMaskTexture ->
    # profile texture keys) and static switches (UseUV1Metres)
    for pname, key in sorted((u.get("figure_textures") or {}).items()):
        set_tex("figure_instance", pname, tex_pkg[key])
    for name, value in sorted((u.get("figure_static_switches") or {}).items()):
        ue.call("instance", "set_static_switch_parameter", {"instance": ue_obj(names["figure_instance"]), "name": name,
                                                            "value": bool(value)})
        plan["instances"]["figure_instance"]["switches"][name] = bool(value)
    # base
    bcfg = u.get("base_marker") or {}
    create("base_instance", base_master)
    if bcfg.get("textures", base_mode != "vertex-mask"):
        for key, pname in (("BC", "BaseColorTexture"), ("N", "NormalTexture"), ("ORM", "ORMTexture")):
            set_tex("base_instance", pname, tex_pkg[key])
    for name, value in sorted((bcfg.get("parameters") or {}).items()):
        set_scalar("base_instance", name, value)
    for name, value in sorted((bcfg.get("vectors") or {}).items()):
        set_vector("base_instance", name, team_linear(value))
    # teams
    for team, colour in sorted(u["teams"].items()):
        lin = team_linear(colour)
        for part, parent_key in (("figure", "figure_instance"), ("base", "base_instance")):
            key = "team:%s:%s" % (part, team)
            create(key, names[parent_key])
            set_vector(key, "TeamColor", lin)
            plan["instances"][key]["team_hex"] = colour if isinstance(colour, str) else None
    for extra in u.get("extra_instances") or []:
        key = "extra:" + extra["asset"]
        create(key, names[extra.get("parent", "figure_instance")])
        for pname, tkey in sorted((extra.get("textures") or {}).items()):
            set_tex(key, pname, tex_pkg[tkey])
        for name, value in sorted((extra.get("scalars") or {}).items()):
            set_scalar(key, name, value)
        for name, value in sorted((extra.get("vectors") or {}).items()):
            set_vector(key, name, team_linear(value))
    return plan


def um_master_checks(ue, u, names, um_plan, getp, check, measured) -> None:
    """Checks of the um-master route: masters current (parameters of the spec present, Opaque, one-sided, no WPO),
    each MI's parent, texture, scalar and vector values read back from the editor."""
    um = um_masters()
    spec, _ = um.load_spec(TOOL_DIR.parents[1])
    masters = {}
    for role, pkg in (("figure", um_plan["figure_master"]), ("base_marker", um_plan["base_master"])):
        params = ue.call("instance", "list_parameters", {"material": ue_obj(pkg)}) or []
        have = sorted(p.get("name") for p in params if isinstance(p, dict))
        want = sorted(um.expected_parameters(spec, role))
        props = getp(ue_obj(pkg), ["BlendMode", "TwoSided", "ShadingModel"])
        wpo = (ue.call("material", "get_property_input", {"material": ue_obj(pkg),
                                                          "material_property": "MP_WorldPositionOffset"}) or {})
        wpo_ref = wpo.get("expression")
        wpo_ref = wpo_ref.get("refPath") if isinstance(wpo_ref, dict) else wpo_ref
        masters[role] = {"asset": pkg, "missing_parameters": [p for p in want if p not in have],
                         "properties": props, "wpo": None if wpo_ref in (None, "", "None") else wpo_ref,
                         "graph_signature_planned": um.graph_signature(spec, role)}
        masters[role]["ok"] = (not masters[role]["missing_parameters"] and props.get("BlendMode") == "BLEND_Opaque"
                               and props.get("TwoSided") is False and masters[role]["wpo"] is None)
    measured["um_masters"] = masters
    check("um_masters_current", all(m["ok"] for m in masters.values()), masters,
          note="parameters of art/um-materials/um-masters.json present, Opaque, one-sided, no World Position Offset "
               "(graph node by node: um_masters.py verify)")
    inst = {}
    for key, want in sorted(um_plan["instances"].items()):
        ref = ue_obj(want["asset"])
        parent = getp(ref, ["Parent"]).get("Parent")
        parent = parent.get("refPath") if isinstance(parent, dict) else parent
        got = {"parent": ue_package(parent or ""), "textures": {}, "scalars": {}, "vectors": {}, "switches": {}}
        for name in want["textures"]:
            got["textures"][name] = ue_package(ue.call("instance", "get_texture_parameter",
                                                       {"instance": ref, "name": name}) or "")
        for name in want["scalars"]:
            got["scalars"][name] = round(float(ue.call("instance", "get_scalar_parameter",
                                                       {"instance": ref, "name": name}) or 0.0), 5)
        for name in want["vectors"]:
            v = ue.call("instance", "get_vector_parameter", {"instance": ref, "name": name}) or {}
            got["vectors"][name] = [round(float(v.get(k, -1)), 6) for k in "rgba"]
        for name in want.get("switches") or {}:
            got["switches"][name] = bool(ue.call("instance", "get_static_switch_parameter",
                                                 {"instance": ref, "name": name}))
        ok = (got["parent"] == want["parent"]
              and all(got["textures"][n] == ue_package(t) for n, t in want["textures"].items())
              and all(abs(got["scalars"][n] - v) < 1e-4 for n, v in want["scalars"].items())
              and all(max(abs(a - b) for a, b in zip(got["vectors"][n], v)) < 1e-4 for n, v in want["vectors"].items())
              and all(got["switches"][n] == v for n, v in (want.get("switches") or {}).items()))
        inst[key] = {"planned": want, "read_back": got, "ok": ok}
    measured["um_instances"] = inst
    check("um_instances_parent_textures_values", all(i["ok"] for i in inst.values()),
          {k: {"ok": v["ok"], "parent": v["read_back"]["parent"]} for k, v in inst.items()},
          note="figure MI -> %s, base MI -> %s, team MIs -> their asset MI; TeamColor = FLinearColor::FromSRGBColor of "
               "the profile hex (AD-OPEN-39 rule), +-1e-4" % (um_plan["figure_master"], um_plan["base_master"]))


def ue_import_fbx(ue, staging: Path, key: str, args: dict) -> dict:
    """Run UE_PY_IMPORT_FBX in the live editor for one mesh (see its docstring); raises on an editor-side error."""
    script = staging / "ue_import_fbx.py"
    if not script.exists():
        script.write_text(UE_PY_IMPORT_FBX, encoding="utf-8", newline="\n")
    args_path, out_path = staging / ("ue_import_%s.args.json" % key), staging / ("ue_import_%s.out.json" % key)
    args_path.write_text(json.dumps(dict(args, out=out_path.as_posix()), indent=1), encoding="utf-8")
    res = ue.editor_python(script, args_path, out_path)
    ue.calls.append({"editor_python": script.name, "args": args, "result": res})
    if res.get("error"):
        raise PipelineError("%s import failed in the editor: %s" % (key, res["error"]))
    return res


def ue_editor_measure(ue, staging: Path, key: str, source: str, args: dict) -> dict:
    """Run a read-only editor-Python measurement (e.g. UE_PY_MEASURE_SKELETAL); the result dict carries "error" on an
    editor-side failure instead of raising (a measurement never blocks the import itself)."""
    script = staging / ("ue_measure_%s.py" % key)
    script.write_text(source, encoding="utf-8", newline="\n")
    args_path, out_path = staging / ("ue_measure_%s.args.json" % key), staging / ("ue_measure_%s.out.json" % key)
    args_path.write_text(json.dumps(dict(args, out=out_path.as_posix()), indent=1), encoding="utf-8")
    try:
        res = ue.editor_python(script, args_path, out_path)
    except PipelineError as exc:
        res = {"error": str(exc)}
    ue.calls.append({"editor_python": script.name, "args": args, "result": res})
    return res


def import_contract_checks(ue, imports, sk, base, getp, check, measured, vertex_mask_base=False) -> None:
    """Engine gate memo §1 item 5 (W4-B): legacy FbxFactory, the normal import method and Nanite off, read back."""
    contract = {}
    for key, mesh, kind in (("skeletal", sk, "skeletal"), ("base", base, "static")):
        res = imports.get(key) or {}
        aid = getp(mesh, ["AssetImportData"]).get("AssetImportData")
        aid = aid if isinstance(aid, dict) else {"refPath": aid}
        read = getp(aid, ["NormalImportMethod", "VertexColorImportOption"]) if aid.get("refPath") else {}
        if kind == "static":
            nanite = ue.call("static", "is_nanite_enabled", {"mesh": mesh})
        else:
            ns = getp(mesh, ["NaniteSettings"]).get("NaniteSettings")
            nanite = (ns or {}).get("bEnabled") if isinstance(ns, dict) else ns
        contract[key] = {"factory": res.get("factory"), "asset_import_data_class": res.get("asset_import_data_class"),
                         "asset_import_data": aid.get("refPath"),
                         "normal_import_method": read.get("NormalImportMethod"),
                         "vertex_color_import_option": read.get("VertexColorImportOption"),
                         "nanite_enabled": nanite}
    measured["import_contract"] = contract
    want_method = {"FBXNIM_IMPORT_NORMALS": "FBXNIM_ImportNormals"}.get(UE_NORMAL_IMPORT_METHOD, UE_NORMAL_IMPORT_METHOD)
    check("import_legacy_fbx_factory", all(c["factory"] == "FbxFactory" and str(c["asset_import_data_class"] or "")
                                           .startswith("Fbx") for c in contract.values()), contract,
          {"factory": "FbxFactory", "asset_import_data_class": "Fbx*ImportData"},
          "explicit task.factory = FbxFactory: AssetTools does not route to Interchange (memo, importer topic)")
    check("normal_import_method", all(c["normal_import_method"] == want_method for c in contract.values()),
          {k: c["normal_import_method"] for k, c in contract.items()}, want_method,
          "UM_FBX_v1 FBX carry normals, no tangents (use_tspace off): ImportNormals + MikkTSpace tangents in UE")
    check("nanite_disabled", all(c["nanite_enabled"] in (False, None) for c in contract.values()) and
          contract["base"]["nanite_enabled"] is False, {k: c["nanite_enabled"] for k, c in contract.items()}, False,
          "nanite == false (engine gate: Nanite not enabled, D-07); skeletal read from NaniteSettings.bEnabled")
    if vertex_mask_base:
        vc = contract["base"]["vertex_color_import_option"]
        check("base_vertex_colors_imported_for_mask", vc == "VCIO_Replace" or vc == "Replace", vc, "Replace",
              "the vertex-mask base material reads the base's vertex colours (AssetImportData of the base)")
IMPORTER_SIDE_PRODUCT_CLASSES = ("Material", "MaterialInstanceConstant", "Texture2D")
UE_DELETE_RANK = {"MaterialInstanceConstant": 0, "SkeletalMesh": 1, "StaticMesh": 1, "PhysicsAsset": 1,
                  "Skeleton": 2, "Material": 3, "Texture2D": 4}


def ue_delete_owned(ue, assets, folder=None, keep=()) -> list:
    """Delete this run's previous assets, referencers first (UE 5.8 MCP `delete` force-deletes and
    nulls references, so the order only avoids transient dangling references).

    0.8.0: with `folder`, only assets inside that folder are deleted, and never an asset in `keep` (the canonical
    target skeleton of a skeletal-adopt profile), even if an older manifest listed it as owned."""
    ranked = []
    if folder is not None:
        root = folder.rstrip("/") + "/"
        assets = [a for a in assets if a.startswith(root)]
    keep = set(keep)
    assets = [a for a in assets if a not in keep]
    for asset in assets:
        try:
            cls = str(ue.call("asset", "get_asset_class", {"asset_path": asset})).rsplit(".", 1)[-1]
        except PipelineError:
            cls = "?"
        ranked.append((UE_DELETE_RANK.get(cls, 1), asset))
    deleted = []
    for _rank, asset in sorted(ranked):
        if not ue.call("asset", "delete", {"path": asset}):
            raise PipelineError("UE refused to delete our previous asset %s" % asset)
        deleted.append(asset)
    return deleted


def exec_ue_import(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    if run_profile(m) in SKELETAL_KINDS:
        return exec_ue_candidate(ctx, staging)
    if run_profile(m) == STATIC:
        return exec_ue_static_candidate(ctx, staging)
    ue = ctx.unreal()
    cfg = m["config"]["ue"]
    rec = m["stages"][UE_STAGE]
    fbx = ctx.run_path(fbx_rel(m))
    fbx_sha = stage_output_sha(m, "export", fbx_rel(m))
    if not fbx.is_file() or sha256_file(fbx) != fbx_sha:
        raise PipelineError("exported FBX missing or changed since the export stage: %s" % fbx)
    plan = ue_plan(ctx)
    folder, primary, kind = plan["folder"], plan["primary"], plan["kind"]
    roundtrip = plan["export_report"]["roundtrip_reimport"]
    owned = set(rec.get("ue_owned_assets") or [])
    before = ue_listing(ue, folder)
    foreign = [a for a in before if a not in owned]
    if foreign:
        raise PipelineError("UE folder %s holds assets this run did not create: %s; refusing to delete or "
                            "import next to them (use another --ue-folder)" % (folder, foreign[:10]), EXIT_CONFLICT)
    # All ours: remove so the re-import cannot collide (UE 5.8 MCP import_file refuses an existing
    # name; other importers create *_1 duplicates) or leave stale leftovers.
    deleted = ue_delete_owned(ue, before)
    rec["ue_owned_assets"] = []
    ctx.save()
    pre_import = ue_listing(ue, folder)
    args = {"folder_path": folder, "asset_name": plan["name"], "source_file": str(fbx),
            "import_materials": bool(cfg.get("import_materials", True)),
            "import_textures": bool(cfg.get("import_textures", True))}
    if kind == "static":
        args["combine_meshes"] = True
    else:
        args.update(import_animations=False, create_physics_asset=False)
    created = sorted({ue_package(r) for r in (ue.call(kind, "import_file", args) or [])})
    after = ue_listing(ue, folder)
    # Persist ownership immediately: a crash after this point is cleaned up by the next attempt.
    rec["ue_owned_assets"] = sorted(set(after) | set(created))
    ctx.save()
    ctx.journal("ue_assets_owned", assets=rec["ue_owned_assets"], deleted_previous=deleted)

    checks = {}

    def check(name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    check("primary_asset_created", primary in after, primary)
    dupes = [a for a in after if re.fullmatch(re.escape(primary) + r"_\d+", a)]
    check("no_numbered_duplicates", not dupes, dupes)
    # UE 5.8 MCP import_file returns only the mesh (measured live 2026-09-28, T2.1 barrel passthrough);
    # the materials/textures the importer creates next to it are side products of the same call. The
    # folder was empty right before the call, so everything in it now comes from this import.
    side = sorted(set(after) - set(created))
    side_classes = {a: str(ue.call("asset", "get_asset_class", {"asset_path": a})).rsplit(".", 1)[-1] for a in side}
    check("folder_contains_only_this_import",
          not pre_import and set(created) <= set(after) and
          all(c in IMPORTER_SIDE_PRODUCT_CLASSES for c in side_classes.values()),
          {"folder_before_import": pre_import, "returned_by_import": created, "importer_side_products": side_classes},
          note="no stale assets from earlier attempts: folder empty before the call; extra assets are only "
               "importer side products (%s)" % ", ".join(IMPORTER_SIDE_PRODUCT_CLASSES))
    asset_class = ue.call("asset", "get_asset_class", {"asset_path": primary})
    expected_class = "SkeletalMesh" if kind == "skeletal" else "StaticMesh"
    check("asset_class", str(asset_class).rsplit(".", 1)[-1] == expected_class, asset_class, expected_class)
    mesh_ref = {"mesh": {"refPath": ue_object_path(primary)}}
    measured = {"kind": kind}
    slots = ue.call(kind, "get_material_slots", mesh_ref) or []
    measured["material_slots"] = slots
    check("material_slots_equal_blender_materials", len(slots) == roundtrip["material_count"], len(slots),
          roundtrip["material_count"])
    bounds = ue.call(kind, "get_bounds", mesh_ref) or {}
    if "boxExtent" in bounds:
        size = [2.0 * bounds["boxExtent"][k] for k in ("x", "y", "z")]
    else:
        size = [bounds["max"][k] - bounds["min"][k] for k in ("x", "y", "z")] if bounds else None
    measured["bounds"] = bounds
    measured["size_uu"] = [round(v, 3) for v in size] if size else None
    expected_size = plan["export_report"]["expected_ue_dimensions_uu_at_import_scale_1"]
    tol = cfg.get("dimension_tolerance", DEFAULT_UE_DIMENSION_TOLERANCE)
    if size:
        # The export report gives the size per UE axis (UM_FBX_v1 export frame; UE only flips the sign of Y).
        check("dimensions_match_blender_at_import_scale_1", all(within(a, b, tol) for a, b in zip(size, expected_size)),
              measured["size_uu"], expected_size, "tolerance %.1f%%; per axis X, Y, Z (UM_FBX_v1 export frame)"
              % (tol * 100))
    else:
        check("dimensions_match_blender_at_import_scale_1", False, None, expected_size, "no bounds returned")
    if kind == "static":
        tris = ue.call("static", "get_triangle_count", dict(mesh_ref, lod_index=0))
        measured["triangles_lod0"] = tris
        measured["vertices_lod0"] = ue.call("static", "get_vertex_count", dict(mesh_ref, lod_index=0))
        check("triangles_equal_blender_roundtrip", within(tris, roundtrip["triangles_total"],
                                                          m["config"]["triangle_loss_tolerance"]),
              tris, roundtrip["triangles_total"])
    else:
        measured["bones"] = ue.call("skeletal", "get_bone_names", mesh_ref)
        measured["sockets"] = ue.call("skeletal", "get_socket_names", mesh_ref)
        measured["vertices_lod0"] = ue.call("skeletal", "get_vertex_count", dict(mesh_ref, lod_index=0))
    saved = ue.call("asset", "save_assets", {"asset_paths": after})
    check("assets_saved", saved is True or saved == [True] or bool(saved), saved)
    passed = all(c["passed"] for c in checks.values())
    report = {
        "stage": UE_STAGE,
        "logic": UE_IMPORT_LOGIC_VERSION,
        "backend": ue.describe(),
        "status": "technically_imported" if passed else "failed",
        "fbx": {"path": fbx_rel(m), "sha256": fbx_sha},
        "destination": {"folder": folder, "primary_asset": primary, "kind": kind},
        "previous_assets_deleted": deleted,
        "assets": after,
        "import_args": args,
        "measured": measured,
        "checks": checks,
        "passed": passed,
        "tool_name_style": ue.tool_name_style,
        "not_checked": [
            "art acceptance, silhouette, lighting (art track)",
            "budgets: measured numbers are not budgets until GD-058 is decided",
            "BC/N/ORM material contract: this passthrough imports Tripo materials as-is",
            "facing: this passthrough path has not been imported into the live UE yet (T3/T4 ran only the "
            "skeletal-candidate profile live); the per-axis size check relies on the ART-001 axis mapping",
        ],
    }
    out = staging / "ue-import-report.json"
    out.write_text(dump_json(report), encoding="utf-8")
    calls = staging / "ue-mcp-calls.json"
    calls.write_text(dump_json(ue.calls), encoding="utf-8")
    failed = sorted(k for k, c in checks.items() if not c["passed"])
    return StageResult({"reports/ue-import-report.json": out, "reports/ue-mcp-calls.json": calls},
                       {"passed": passed, "failed_checks": failed, "primary_asset": primary, "kind": kind,
                        "assets": len(after)},
                       passed, None if passed else "ue-import failed: %s" % ", ".join(failed))


def ue_obj(package: str) -> dict:
    return {"refPath": ue_object_path(package)}


def ue_bone_name(bone: str) -> str:
    """Blender bone name -> UE bone name: the FBX import turns '.' into '_' (foot.R -> foot_R; measured live on the
    Harpy candidate 2026-09-28: add_socket on "foot.R" failed with 'Bone "foot.R" not found')."""
    return bone.replace(".", "_")


def candidate_socket_plan(profile: dict, build: dict) -> list:
    """Sockets for UE: [{"name", "bone", "ue_bone", "location_uu", "source"}]. `bone` is the profile (Blender) name,
    `ue_bone` the UE name the socket is attached to. Location = profile sockets[].location_uu when given, else the
    build report's UE bone-space prediction (sockets[].location_uu_for_ue: the Blender bone-local target with y
    negated, the UE FBX import mirrors Y)."""
    from_build = {s["name"]: s for s in build.get("sockets") or []}
    plan = []
    for sock in profile["sockets"]:
        loc = sock.get("location_uu")
        if isinstance(loc, list):
            plan.append({"name": sock["name"], "bone": sock["bone"], "ue_bone": ue_bone_name(sock["bone"]),
                         "location_uu": list(loc), "source": "profile"})
            continue
        predicted = from_build.get(sock["name"])
        if not predicted or not isinstance(predicted.get("location_uu_for_ue"), list):
            raise PipelineError("socket %s has no location_uu in the profile and the build report predicts none "
                                "(rebuild with tool >= 0.5.0)" % sock["name"])
        plan.append({"name": sock["name"], "bone": sock["bone"], "ue_bone": ue_bone_name(sock["bone"]),
                     "location_uu": list(predicted["location_uu_for_ue"]),
                     "source": "build prediction", "target_ue_component_uu": predicted.get("target_ue_component_uu"),
                     "offset_blender_bone_local_uu": predicted.get("offset_blender_bone_local_uu")})
    return plan


def ue_minmax(bounds: dict):
    if not bounds:
        return None, None
    if "boxExtent" in bounds:
        o, e = bounds["origin"], bounds["boxExtent"]
        return [o[k] - e[k] for k in "xyz"], [o[k] + e[k] for k in "xyz"]
    return [bounds["min"][k] for k in "xyz"], [bounds["max"][k] for k in "xyz"]


# 2x2 maps of Blender (x, y) onto UE (x, y); z is up in both. Named by where Blender -Y (front) lands.
AXIS_MAPS = [((1, 0), (0, 1)), ((1, 0), (0, -1)), ((-1, 0), (0, 1)), ((-1, 0), (0, -1)),
             ((0, 1), (1, 0)), ((0, 1), (-1, 0)), ((0, -1), (1, 0)), ((0, -1), (-1, 0))]


def map_xy(mat, x, y):
    return (mat[0][0] * x + mat[0][1] * y, mat[1][0] * x + mat[1][1] * y)


def match_axis_map(lo_b, hi_b, lo_u, hi_u, tol):
    """Which axis map turns the Blender bounds (cm) into the UE bounds (uu)?"""
    found = []
    for mat in AXIS_MAPS:
        pts = [map_xy(mat, x, y) for x in (lo_b[0], hi_b[0]) for y in (lo_b[1], hi_b[1])]
        pred_lo = [min(p[0] for p in pts), min(p[1] for p in pts), lo_b[2]]
        pred_hi = [max(p[0] for p in pts), max(p[1] for p in pts), hi_b[2]]
        err = max(max(abs(a - b) for a, b in zip(pred_lo, lo_u)), max(abs(a - b) for a, b in zip(pred_hi, hi_u)))
        if err <= tol:
            front = map_xy(mat, 0, -1)
            axis = {(1, 0): "+X", (-1, 0): "-X", (0, 1): "+Y", (0, -1): "-Y"}[front]
            found.append({"map": "ue(x,y)=(%+dx%+dy, %+dx%+dy)" % (mat[0][0], mat[0][1], mat[1][0], mat[1][1]),
                          "blender_front_minus_y_becomes": axis, "max_error_uu": round(err, 4)})
    return found


AXIS_NAMES = {(1, 0): "+X", (-1, 0): "-X", (0, 1): "+Y", (0, -1): "-Y"}
AXIS_VECTORS = {v: k for k, v in AXIS_NAMES.items()}


def match_xy_map(lo_a, hi_a, lo_b, hi_b, tol):
    """Which of the 8 axis maps turns bounds A (x, y) into bounds B (both UE, z unchanged)?"""
    found = []
    for mat in AXIS_MAPS:
        pts = [map_xy(mat, x, y) for x in (lo_a[0], hi_a[0]) for y in (lo_a[1], hi_a[1])]
        pred_lo = [min(p[0] for p in pts), min(p[1] for p in pts), lo_a[2]]
        pred_hi = [max(p[0] for p in pts), max(p[1] for p in pts), hi_a[2]]
        err = max(max(abs(a - b) for a, b in zip(pred_lo, lo_b)), max(abs(a - b) for a, b in zip(pred_hi, hi_b)))
        if err <= tol:
            found.append({"map": "b(x,y)=(%+dx%+dy, %+dx%+dy)" % (mat[0][0], mat[0][1], mat[1][0], mat[1][1]),
                          "maps_axis": {name: AXIS_NAMES[map_xy(mat, *vec)] for vec, name in AXIS_NAMES.items()},
                          "max_error_uu": round(err, 4)})
    return found


def exec_ue_candidate(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    ue = ctx.unreal()
    rec = m["stages"][UE_STAGE]
    plan = ue_plan(ctx)
    profile, names, folder = plan["profile"], plan["names"], plan["folder"]
    u = profile["ue"]
    adopted = run_profile(m) == SKELETAL_ADOPT
    if adopted:
        # skeletal-adopt (0.7.0): the H2 bake pinned by adopt; its reports normalised into build/atlas views
        build, atlas, inputs, src_paths = adopted_skeletal_inputs(ctx)
    else:
        build = json.loads(ctx.run_path("reports/build-report.json").read_text(encoding="utf-8"))
        atlas = json.loads(ctx.run_path("reports/atlas-report.json").read_text(encoding="utf-8"))
        rels = candidate_export_rels(profile)
        inputs = {}
        for stage in ("atlas", "build"):
            for rel, info in ((m["stages"].get(stage) or {}).get("outputs") or {}).items():
                if rel.startswith("work/"):
                    continue
                path = ctx.run_path(rel)
                if not path.is_file() or sha256_file(path) != info["sha256"]:
                    raise PipelineError("%s output missing or changed since the %s stage: %s" % (stage, stage, rel))
                inputs[rel] = info["sha256"]
        src_paths = {"skeletal": ctx.run_path(rels["skeletal"]), "base": ctx.run_path(rels["base"])}
        src_paths.update({"texture:" + k: ctx.run_path("textures/" + v["file"]) for k, v in atlas["files"].items()})

    target_skeleton = plan.get("target_skeleton")
    if target_skeleton:
        skel_class = None
        if ue.call("asset", "exists", {"path": target_skeleton}):
            skel_class = str(ue.call("asset", "get_asset_class", {"asset_path": target_skeleton})).rsplit(".", 1)[-1]
        if skel_class != "Skeleton":
            raise PipelineError("ue.target_skeleton %s does not exist as a Skeleton (class %s); create the canonical "
                                "skeleton first (review/ue_py/canonical_skeleton.py)" % (target_skeleton, skel_class),
                                EXIT_CONFLICT)
    owned = set(rec.get("ue_owned_assets") or [])
    before = ue_listing(ue, folder)
    foreign = [a for a in before if a not in owned]
    if foreign:
        raise PipelineError("UE folder %s holds assets this run did not create: %s; refusing to delete or "
                            "import next to them (use another --ue-folder)" % (folder, foreign[:10]), EXIT_CONFLICT)
    deleted = ue_delete_owned(ue, before, folder=folder, keep=[target_skeleton] if target_skeleton else [])
    rec["ue_owned_assets"] = []
    ctx.save()
    try:
        log_before = len(ue.call("logs", "GetLogEntries", {"category": "LogFbx", "pattern": "", "maxEntries": 0}) or [])
    except PipelineError:
        log_before = None
    created = []

    def track(result):
        # ownership is persisted at once (0.6.0): a failure half way (e.g. a lost console command, 2026-09-29) leaves
        # only assets the manifest owns, so the next attempt deletes them instead of refusing a "foreign" folder
        items = result if isinstance(result, list) else [result]
        created.extend(ue_package(x) for x in items if x)
        rec["ue_owned_assets"] = sorted(set(created))
        ctx.save()

    def setp(ref, props):
        return ue.call("object", "set_properties", {"instance": ref, "values": json.dumps(props)})

    def getp(ref, props):
        raw = ue.call("object", "get_properties", {"instance": ref, "properties": props})
        return json.loads(raw) if isinstance(raw, str) else raw

    # textures (the DirectX normal and linear ORM are imported from the atlas stage files; an optional texture such
    # as the TeamMask of team_color.mask only when the atlas stage produced it, see ue_plan)
    textures = {k: t for k, t in u["textures"].items() if "texture:" + k in names}
    for key, tcfg in sorted(textures.items()):
        pkg = names["texture:" + key]
        track(ue.call("texture", "import_file", {"folder_path": pkg.rsplit("/", 1)[0], "asset_name": tcfg["asset"],
                                                 "source_file": str(src_paths["texture:" + tcfg["file_key"]])}))
        props = {"SRGB": tcfg["srgb"], "CompressionSettings": tcfg["compression"]}
        if "flip_green" in tcfg:
            props["bFlipGreenChannel"] = tcfg["flip_green"]
        # LD-merlin-ue: further UTexture properties of the profile (Filter, MipGenSettings, NeverStream, ... for the
        # MatID / LUT inputs of M_UM_Figure_v2: point sampled, no mips, never streamed)
        props.update(tcfg.get("properties") or {})
        setp(ue_obj(pkg), props)
    team_mode = u.get("team_color_mode", "multiply")
    base_mode = u.get("base_material_mode", "atlas-instance")
    if team_mode not in UE_TEAM_COLOR_MODES:
        raise PipelineError("ue.team_color_mode must be one of %s" % (UE_TEAM_COLOR_MODES,), EXIT_USAGE)
    if base_mode not in UE_BASE_MATERIAL_MODES:
        raise PipelineError("ue.base_material_mode must be one of %s" % (UE_BASE_MATERIAL_MODES,), EXIT_USAGE)
    route = material_route(u)
    mat = bmat = mat_pkg = None
    wiring, base_wiring, samplers_used, um = {}, {}, {}, None
    tex_path = {k: ue_object_path(names["texture:" + k]) for k in textures}
    if route == "um-master":
        um = um_master_instances(ue, u, names, textures, tex_path, team_mode, base_mode, track)
    else:
        # material: BC [x TeamColor per ue.team_color_mode], DirectX normal, ORM (R AO, G roughness, B metallic)
        mat_pkg = names["material"]
        track(ue.call("material", "create_material", {"folder_path": mat_pkg.rsplit("/", 1)[0], "asset_name": u["material"]}))
        mat = ue_obj(mat_pkg)

        def expr_in(material, cls, x, y, props=None):
            ref = ue.call("material", "add_expression", {"material_or_function": material, "x": x, "y": y,
                                                         "expression_class": {"refPath": "/Script/Engine." + cls}})
            if props:
                setp(ref, props)
            return ref

        def expr(cls, x, y, props=None):
            return expr_in(mat, cls, x, y, props)

        def link(src, out, dst, inp):
            ue.call("material", "connect_expressions", {"from_expression": src, "from_output_name": out,
                                                        "to_expression": dst, "to_input_name": inp})

        bc = expr("MaterialExpressionTextureSampleParameter2D", -800, 0,
                  {"ParameterName": "BaseColorTexture", "Texture": tex_path["BC"], "SamplerType": "SAMPLERTYPE_Color"})
        nrm = expr("MaterialExpressionTextureSampleParameter2D", -800, 420,
                   {"ParameterName": "NormalTexture", "Texture": tex_path["N"], "SamplerType": "SAMPLERTYPE_Normal"})
        orm = expr("MaterialExpressionTextureSampleParameter2D", -800, 680,
                   {"ParameterName": "ORMTexture", "Texture": tex_path["ORM"], "SamplerType": "SAMPLERTYPE_Masks"})
        samplers_used = {"BC": bc, "N": nrm, "ORM": orm}
        if team_mode == "none":
            base_colour = (bc, "RGB")
        else:
            team = expr("MaterialExpressionVectorParameter", -800, 220,
                        {"ParameterName": "TeamColor", "DefaultValue": {"R": 1, "G": 1, "B": 1, "A": 1}})
            mul = expr("MaterialExpressionMultiply", -480, 60)
            link(bc, "RGB", mul, "A")
            link(team, "", mul, "B")
            base_colour = (mul, "")
            if team_mode == "mask":
                if "TeamMask" not in textures:
                    raise PipelineError("ue.team_color_mode mask needs the TeamMask texture (team_color.mask of the atlas "
                                        "stage and ue.textures.TeamMask)")
                mask = expr("MaterialExpressionTextureSampleParameter2D", -800, 900,
                            {"ParameterName": "TeamMaskTexture", "Texture": tex_path["TeamMask"],
                             "SamplerType": "SAMPLERTYPE_LinearGrayscale"})
                samplers_used["TeamMask"] = mask
                lerp = expr("MaterialExpressionLinearInterpolate", -240, 60)
                link(bc, "RGB", lerp, "A")
                link(mul, "", lerp, "B")
                link(mask, "R", lerp, "Alpha")
                base_colour = (lerp, "")
        wiring = {"MP_BaseColor": base_colour, "MP_Normal": (nrm, "RGB"), "MP_AmbientOcclusion": (orm, "R"),
                  "MP_Roughness": (orm, "G"), "MP_Metallic": (orm, "B")}
        for prop, (ref, out) in wiring.items():
            ue.call("material", "connect_to_output", {"expression": ref, "output_name": out, "material_property": prop})
        setp(mat, {"bUsedWithSkeletalMesh": True})
        ue.call("material", "recompile", {"material_or_function": mat})
        # base material (ue.base_material_mode vertex-mask): the parametric base's vertex-colour mask
        # (R team band, G centre pips, B outer pips; pips lit by InstanceIndex 1: G, 2: B, 3: G + B)
        bmat, base_wiring = None, {}
        if base_mode == "vertex-mask":
            bpar = u.get("base_material_parameters") or {}
            bmat_pkg = names["base_material"]
            track(ue.call("material", "create_material", {"folder_path": bmat_pkg.rsplit("/", 1)[0],
                                                          "asset_name": u["base_material"]}))
            bmat = ue_obj(bmat_pkg)

            def bexpr(cls, x, y, props=None):
                return expr_in(bmat, cls, x, y, props)

            def rgba(values):
                return dict(zip("RGBA", list(values) + [1.0] * (4 - len(values))))

            vc = bexpr("MaterialExpressionVertexColor", -1200, 0)
            base_col = bexpr("MaterialExpressionVectorParameter", -1200, 200,
                             {"ParameterName": "BaseColor", "DefaultValue": rgba(bpar.get("BaseColor", [0.03, 0.026, 0.023]))})
            team_b = bexpr("MaterialExpressionVectorParameter", -1200, 400,
                           {"ParameterName": "TeamColor", "DefaultValue": {"R": 1, "G": 1, "B": 1, "A": 1}})
            pip = bexpr("MaterialExpressionVectorParameter", -1200, 600,
                        {"ParameterName": "PipColor", "DefaultValue": rgba(bpar.get("PipColor", [0.78, 0.74, 0.64]))})
            index = bexpr("MaterialExpressionScalarParameter", -1200, 800,
                          {"ParameterName": "InstanceIndex", "DefaultValue": 3.0})
            emissive = bexpr("MaterialExpressionScalarParameter", -1200, 1000,
                             {"ParameterName": "PipEmissive", "DefaultValue": float(bpar.get("PipEmissive", 0.35))})
            # centre pips lit for |Index - 2| > 0.5, outer pips for Index > 1.5 (steep saturated ramps, no If node)
            d2 = bexpr("MaterialExpressionSubtract", -900, 800, {"ConstB": 2.0})
            link(index, "", d2, "A")
            a2 = bexpr("MaterialExpressionAbs", -760, 800)
            link(d2, "", a2, "")
            c_off = bexpr("MaterialExpressionSubtract", -620, 800, {"ConstB": 0.5})
            link(a2, "", c_off, "A")
            c_k = bexpr("MaterialExpressionMultiply", -480, 800, {"ConstB": 1000.0})
            link(c_off, "", c_k, "A")
            centre_on = bexpr("MaterialExpressionSaturate", -340, 800)
            link(c_k, "", centre_on, "")
            o_off = bexpr("MaterialExpressionSubtract", -900, 950, {"ConstB": 1.5})
            link(index, "", o_off, "A")
            o_k = bexpr("MaterialExpressionMultiply", -760, 950, {"ConstB": 1000.0})
            link(o_off, "", o_k, "A")
            outer_on = bexpr("MaterialExpressionSaturate", -620, 950)
            link(o_k, "", outer_on, "")
            g_lit = bexpr("MaterialExpressionMultiply", -200, 700)
            link(vc, "G", g_lit, "A")
            link(centre_on, "", g_lit, "B")
            b_lit = bexpr("MaterialExpressionMultiply", -200, 900)
            link(vc, "B", b_lit, "A")
            link(outer_on, "", b_lit, "B")
            lit_sum = bexpr("MaterialExpressionAdd", -60, 800)
            link(g_lit, "", lit_sum, "A")
            link(b_lit, "", lit_sum, "B")
            lit = bexpr("MaterialExpressionSaturate", 80, 800)
            link(lit_sum, "", lit, "")
            band = bexpr("MaterialExpressionLinearInterpolate", -900, 300)
            link(base_col, "", band, "A")
            link(team_b, "", band, "B")
            link(vc, "R", band, "Alpha")
            colour = bexpr("MaterialExpressionLinearInterpolate", 220, 300)
            link(band, "", colour, "A")
            link(pip, "", colour, "B")
            link(lit, "", colour, "Alpha")
            glow = bexpr("MaterialExpressionMultiply", 220, 600)
            link(pip, "", glow, "A")
            link(lit, "", glow, "B")
            glow_k = bexpr("MaterialExpressionMultiply", 360, 600)
            link(glow, "", glow_k, "A")
            link(emissive, "", glow_k, "B")
            rough = bexpr("MaterialExpressionConstant", 220, 1000, {"R": float(bpar.get("Roughness", 0.6))})
            base_wiring = {"MP_BaseColor": (colour, ""), "MP_EmissiveColor": (glow_k, ""), "MP_Roughness": (rough, "")}
            for prop, (ref, out) in base_wiring.items():
                ue.call("material", "connect_to_output", {"expression": ref, "output_name": out, "material_property": prop})
            ue.call("material", "recompile", {"material_or_function": bmat})
        # team colour instances: children of the atlas material, or of the base material when the team colour lives on
        # the base (vertex-mask); the default instance goes on the base, and on the figure unless it is a base child
        instances_parent_pkg = names["base_material"] if bmat else mat_pkg
        for name, color in sorted(u["instances"].items()):
            pkg = names["instance:" + name]
            track(ue.call("instance", "create", {"folder_path": pkg.rsplit("/", 1)[0], "asset_name": name,
                                                 "parent": bmat or mat}))
            ue.call("instance", "set_vector_parameter", {"instance": ue_obj(pkg), "name": "TeamColor",
                                                         "value": dict(zip("rgba", color))})
    # meshes: editor Python with an explicit legacy FbxFactory (UE_PY_IMPORT_FBX): normal import method pinned, Nanite
    # off, vertex colours only for a vertex-mask base (the MCP import_file takes neither option; T3.1, W4-B)
    sk_pkg, base_pkg = names["skeletal"], names["base"]
    vertex_mask_base = base_mode == "vertex-mask"
    imports = {}
    for key, pkg, asset, kind, vc in (("skeletal", sk_pkg, u["skeletal_asset"], "skeletal", "ignore"),
                                      ("base", base_pkg, u["base_asset"], "static",
                                       "replace" if vertex_mask_base else "ignore")):
        import_args = {
            "kind": kind, "folder_path": pkg.rsplit("/", 1)[0], "asset_name": asset,
            "source_file": str(src_paths[key]), "import_materials": False, "import_textures": False,
            "combine_meshes": True, "vertex_colors": vc, "normal_import_method": UE_NORMAL_IMPORT_METHOD}
        if key == "skeletal" and target_skeleton:
            import_args["skeleton"] = ue_object_path(target_skeleton)
        if key == "base" and u.get("base_generate_lightmap_uvs") is not None:
            import_args["generate_lightmap_uvs"] = bool(u["base_generate_lightmap_uvs"])
        res = ue_import_fbx(ue, staging, key, import_args)
        track([{"refPath": x} for x in res.get("imported") or []
               if not target_skeleton or ue_package(x) != target_skeleton])
        imports[key] = res
    base_vc = None
    if vertex_mask_base:
        base_vc = {"import": "editor Python FbxImportUI (VertexColorImportOption Replace) through the MCP console",
                   "script_sha256": hashlib.sha256(UE_PY_IMPORT_FBX.encode("utf-8")).hexdigest()}
    after = ue_listing(ue, folder)
    rec["ue_owned_assets"] = sorted(set(after) | set(created))
    ctx.save()
    ctx.journal("ue_assets_owned", assets=rec["ue_owned_assets"], deleted_previous=deleted)
    fbx_log = []
    if log_before is not None:
        try:
            entries = ue.call("logs", "GetLogEntries", {"category": "LogFbx", "pattern": "", "maxEntries": 0}) or []
            fbx_log = [re.sub(r"^\[[^\]]*\]\[[^\]]*\]", "", e) for e in entries[log_before:]]
        except PipelineError:
            fbx_log = None
    sk, base = ue_obj(sk_pkg), ue_obj(base_pkg)
    if um:
        # um-master: the figure shows the default team MI of the figure, the base the default team MI of the base
        sk_material_pkg = names["team:figure:" + u["default_team"]]
        default_mi_pkg = names["team:base:" + u["default_team"]]
    else:
        default_mi_pkg = names["instance:" + u["default_instance"]]
        # the figure shows the default team instance, or the atlas material itself when the instances belong to the base
        sk_material_pkg = mat_pkg if bmat else default_mi_pkg
    default_mi = ue_obj(default_mi_pkg)
    sk_slots = ue.call("skeletal", "get_material_slots", {"mesh": sk}) or []
    for slot in sk_slots:
        ue.call("skeletal", "set_material", {"mesh": sk, "slot_name": slot, "material": ue_obj(sk_material_pkg)})
    base_slots = ue.call("static", "get_material_slots", {"mesh": base}) or []
    for slot in base_slots:
        ue.call("static", "set_material", {"mesh": base, "slot_name": slot, "material": default_mi})
    for sock in ue.call("skeletal", "get_socket_names", {"mesh": sk}) or []:
        ue.call("skeletal", "remove_socket", {"mesh": sk, "socket_name": sock})
    planned_sockets = candidate_socket_plan(profile, build)
    for sock in planned_sockets:
        ue.call("skeletal", "add_socket", {"mesh": sk, "socket_name": sock["name"], "bone_name": sock["ue_bone"]})
        x, y, z = sock["location_uu"]
        ue.call("skeletal", "set_socket_transform", {"mesh": sk, "socket_name": sock["name"], "transform": {
            "location": {"x": x, "y": y, "z": z}, "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
            "scale": {"x": 1, "y": 1, "z": 1}}})
    saved = ue.call("asset", "save_assets", {"asset_paths": after})

    # ---------------------------------------------------------------- measurements
    checks, measured, proposals = {}, {}, {}

    def check(name, passed, value=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": value}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    expected_assets = sorted(names.values())
    check("assets_exactly_as_planned", sorted(after) == expected_assets, after, expected_assets,
          "no stale assets, no extra imports")
    dupes = [a for a in after if re.search(r"_\d+$", a) and re.sub(r"_\d+$", "", a) in expected_assets]
    check("no_numbered_duplicates", not dupes, dupes)
    classes = {}
    for key, pkg in sorted(names.items()):
        classes[key] = str(ue.call("asset", "get_asset_class", {"asset_path": pkg})).rsplit(".", 1)[-1]
    want = {"skeletal": "SkeletalMesh", "base": "StaticMesh"}
    if "skeleton" in names:
        want["skeleton"] = "Skeleton"
    if "material" in names:
        want["material"] = "Material"
    if "base_material" in names:
        want["base_material"] = "Material"
    want.update({k: "MaterialInstanceConstant" for k in names if k.startswith(("instance:", "team:", "extra:"))
                 or k in ("figure_instance", "base_instance")})
    want.update({k: "Texture2D" for k in names if k.startswith("texture:")})
    check("asset_classes", classes == want, classes, want)
    tex = {}
    for key, tcfg in sorted(textures.items()):
        ref = ue_obj(names["texture:" + key])
        size = ue.call("texture", "get_size", {"texture": ref}) or {}
        extra_p = tcfg.get("properties") or {}
        props = getp(ref, ["SRGB", "CompressionSettings", "bFlipGreenChannel"] + sorted(extra_p))
        tex[key] = {"size": [size.get("x"), size.get("y")], "properties": props}
        want_p = {"SRGB": tcfg["srgb"], "CompressionSettings": tcfg["compression"]}
        if "flip_green" in tcfg:
            want_p["bFlipGreenChannel"] = tcfg["flip_green"]
        want_p.update(extra_p)
        # LD-merlin-ue: a non-atlas input (the 16 x 16 class LUT) names its own size (ue.textures.<key>.px)
        tex[key]["ok"] = (tex[key]["size"] == (tcfg.get("px") or [atlas["size"]] * 2) and
                          all(props.get(k) == v for k, v in want_p.items()))
    measured["textures"] = tex
    check("textures_size_colour_space_compression", all(t["ok"] for t in tex.values()), tex,
          {k: {"size": [atlas["size"]] * 2, "SRGB": c["srgb"], "CompressionSettings": c["compression"]}
           for k, c in textures.items()})
    if um:
        um_master_checks(ue, u, names, um, getp, check, measured)
    else:
        graph = {}
        for prop, (ref, out) in wiring.items():
            src = ue.call("material", "get_property_input", {"material": mat, "material_property": prop}) or {}
            graph[prop] = {"expression": (src.get("expression") or {}).get("refPath", "").rsplit(":", 1)[-1],
                           "output": src.get("output_name"),
                           "ok": (src.get("expression") or {}).get("refPath") == ref.get("refPath") and
                                 (src.get("output_name") or "") == out}
        samplers = {k: getp(v, ["ParameterName", "Texture", "SamplerType"]) for k, v in sorted(samplers_used.items())}
        mat_props = getp(mat, ["bUsedWithSkeletalMesh", "TwoSided", "BlendMode", "ShadingModel"])
        measured["material"] = {"team_color_mode": team_mode, "outputs": graph, "samplers": samplers, "properties": mat_props}
        check("material_graph_bc_teamcolor_normal_orm", all(g["ok"] for g in graph.values()) and
              mat_props.get("bUsedWithSkeletalMesh") is True and mat_props.get("BlendMode") == "BLEND_Opaque",
              measured["material"], note="BaseColor per ue.team_color_mode %s (%s)" % (team_mode, {
                  "multiply": "BC x TeamColor", "mask": "lerp(BC, BC x TeamColor, TeamMask.R)", "none": "BC"}[team_mode]))
        if bmat:
            bgraph = {}
            for prop, (ref, out) in base_wiring.items():
                src = ue.call("material", "get_property_input", {"material": bmat, "material_property": prop}) or {}
                bgraph[prop] = {"expression": (src.get("expression") or {}).get("refPath", "").rsplit(":", 1)[-1],
                                "output": src.get("output_name"),
                                "ok": (src.get("expression") or {}).get("refPath") == ref.get("refPath") and
                                      (src.get("output_name") or "") == out}
            bprops = getp(bmat, ["BlendMode", "ShadingModel", "TwoSided"])
            measured["base_material"] = {"mode": base_mode, "outputs": bgraph, "properties": bprops,
                                         "parameters": ["BaseColor", "TeamColor", "PipColor", "InstanceIndex", "PipEmissive"]}
            check("base_material_graph_vertex_mask", all(g["ok"] for g in bgraph.values())
                  and bprops.get("BlendMode") in (None, "BLEND_Opaque"), measured["base_material"],
                  note="BaseColor = lerp(lerp(BaseColor, TeamColor, VertexColor.R), PipColor, lit), Emissive = PipColor x "
                       "lit x PipEmissive, lit = saturate(G x [|InstanceIndex - 2| > 0.5] + B x [InstanceIndex > 1.5]) "
                       "(base_parametric.mask; live frames: P17 control scene, stage 3 T3.1)")
            aid = getp(base, ["AssetImportData"]).get("AssetImportData")
            aid = aid if isinstance(aid, dict) else {"refPath": aid}
            base_vc = dict(base_vc or {}, asset_import_option=getp(aid, ["VertexColorImportOption"]).get(
                "VertexColorImportOption") if aid.get("refPath") else None)
            measured["base_vertex_colors"] = base_vc
            check("base_vertex_colors_imported", base_vc.get("asset_import_option") == "Replace", base_vc,
                  {"asset_import_option": "Replace"},
                  "the vertex-mask material needs the base's vertex colours (AssetImportData of the base)")
        inst = {}
        for name, color in sorted(u["instances"].items()):
            ref = ue_obj(names["instance:" + name])
            value = ue.call("instance", "get_vector_parameter", {"instance": ref, "name": "TeamColor"}) or {}
            parent = getp(ref, ["Parent"]).get("Parent")
            parent = parent.get("refPath") if isinstance(parent, dict) else parent
            inst[name] = {"TeamColor": {k: round(float(value.get(k, -1)), 4) for k in "rgba"},
                          "parent": parent, "ok": all(abs(float(value.get(k, -1)) - c) < 1e-3 for k, c in zip("rgba", color))
                          and ue_package(parent or "") == instances_parent_pkg}
        check("team_color_instances", all(i["ok"] for i in inst.values()), inst, {"parent": instances_parent_pkg})

    if target_skeleton:
        read_back = ue_package((imports.get("skeletal") or {}).get("skeleton_read_back") or "")
        measured["target_skeleton"] = {"planned": target_skeleton, "read_back": read_back,
                                       "owned_by_run": target_skeleton in (rec.get("ue_owned_assets") or [])}
        check("skeleton_is_canonical_target", read_back == target_skeleton and
              not measured["target_skeleton"]["owned_by_run"], measured["target_skeleton"], target_skeleton,
              "0.8.0: the mesh is imported onto the existing canonical skeleton (ue.target_skeleton); no "
              "<asset>_Skeleton is created, the skeleton is not owned (a reimport never deletes it)")
    bones = ue.call("skeletal", "get_bone_names", {"mesh": sk}) or []
    want_bones = [b[0].replace(".", "_") for b in profile["armature"]["bones"]]
    extra = [b for b in bones if b not in want_bones]
    parents = {b: ue.call("skeletal", "get_bone_parent", {"mesh": sk, "bone_name": b}) for b in bones}
    want_parent = {b[0].replace(".", "_"): (b[1] or "").replace(".", "_") for b in profile["armature"]["bones"]}
    armature_node = profile["armature"]["object"]
    root = profile["armature"]["bones"][0][0]
    hierarchy_ok = all(parents.get(b) == p for b, p in want_parent.items() if b != root)
    root_parent = parents.get(root)
    measured["skeleton"] = {"bones_in_order": bones, "count": len(bones), "bone0": bones[0] if bones else None,
                            "root_parent": root_parent, "extra_bones": extra}
    check("bones_profile_17_present_with_hierarchy", all(b in bones for b in want_bones) and hierarchy_ok,
          {"profile_bones_found": sum(b in bones for b in want_bones), "hierarchy_ok": hierarchy_ok},
          len(want_bones))
    check("bone0_is_armature_object_node", bones[:1] == [armature_node] and extra == [armature_node]
          and root_parent == armature_node, measured["skeleton"],
          {"bone0": armature_node, "total": len(want_bones) + 1},
          "legacy FBX importer turns the Blender armature object into bone 0 (same as /Game/ART004 and v2 imports); "
          "root motion is read from this bone (ue-pipeline-traps)")
    sk_bounds = ue.call("skeletal", "get_bounds", {"mesh": sk}) or {}
    lo_u, hi_u = ue_minmax(sk_bounds)
    exp_b = build["expected_ue_bounds_uu_at_import_scale_1"]["skeletal_blender_axes"]
    tol = m["config"]["ue"].get("dimension_tolerance") or DEFAULT_UE_DIMENSION_TOLERANCE
    tol_uu = max(0.05, tol)  # absolute uu; bounds are exact copies of the FBX data
    maps = match_axis_map(exp_b["min"], exp_b["max"], lo_u, hi_u, tol_uu) if lo_u else []
    measured["skeletal_bounds_uu"] = {"min": [round(v, 4) for v in lo_u], "max": [round(v, 4) for v in hi_u]} if lo_u else None
    measured["axis_mapping"] = maps
    fronts = sorted({mp["blender_front_minus_y_becomes"] for mp in maps})
    check("skeletal_bounds_match_build_front_unambiguous", len(maps) >= 1 and len(fronts) == 1,
          {"maps": maps, "fronts": fronts},
          note="authored Blender bounds from the build report (cm, front -Y) mapped onto UE bounds, tolerance "
               "%.2f uu. A figure symmetric left/right within the tolerance (Harpy's wings) matches a map and its "
               "mirror; bounds cannot tell them apart, but every matching map must send the front to one axis" % tol_uu)
    front = fronts[0] if len(fronts) == 1 else None
    axes_cfg = profile.get("axes") or {}
    want_front = axes_cfg.get("expected_ue_front")
    check("front_axis_as_fbx_preset", want_front is not None and front == want_front,
          {"authored_front_minus_y_becomes": front}, want_front,
          axes_cfg.get("expected_ue_front_source") or "profile axes.expected_ue_front")
    predicted = build["expected_ue_bounds_uu_at_import_scale_1"].get("skeletal_ue_predicted")
    check("skeletal_bounds_equal_um_fbx_v1_prediction", bool(predicted and lo_u) and
          all(abs(a - b) <= tol_uu for a, b in zip(predicted["min"] + predicted["max"], lo_u + hi_u)),
          measured["skeletal_bounds_uu"], predicted,
          "build report: export-frame bounds mapped as UE (x, -y, z) (ART-001); tolerance %.2f uu" % tol_uu)
    # height by profile: the UE bounds top is the skeletal top of the build (a weapon or a crystal may reach above
    # the figure); the figure top (scale.top_part) is checked against scale.figure_height_m from the build report
    height_uu = profile["scale"]["figure_height_m"] * 100.0
    figure = build.get("figure") or {}
    skeletal_top_uu = exp_b["max"][2]
    figure_top_uu = round(figure["figure_top_m"] * 100.0, 4) if figure.get("figure_top_m") is not None else skeletal_top_uu
    measured["height"] = {"ue_skeletal_top_uu": round(hi_u[2], 4) if hi_u else None,
                          "build_skeletal_top_uu": skeletal_top_uu, "build_figure_top_uu": figure_top_uu,
                          "top_part": figure.get("top_part"), "profile_figure_height_uu": height_uu}
    check("skeletal_top_as_build", hi_u is not None and abs(hi_u[2] - skeletal_top_uu) <= tol_uu,
          measured["height"], skeletal_top_uu,
          "UE bounds top = highest skeletal vertex of the build (body and weapon), tolerance %.2f uu" % tol_uu)
    check("figure_height_as_profile", abs(figure_top_uu - height_uu) <= tol_uu, measured["height"], height_uu,
          "figure top (profile scale.top_part %s; whole-figure flow: the skeletal top) = scale.figure_height_m"
          % figure.get("top_part"))
    ref_cfg = u.get("reference_skeletal_for_axes")
    if isinstance(ref_cfg, str):
        ref_cfg = {"asset": ref_cfg}
    if ref_cfg:
        ref_asset = ref_cfg["asset"]
        try:
            present = bool(ue.call("asset", "exists", {"path": ref_asset}))
            r_lo, r_hi = ue_minmax(ue.call("skeletal", "get_bounds", {"mesh": ue_obj(ref_asset)}) or {}) \
                if present else (None, None)
            relation = match_xy_map(r_lo, r_hi, lo_u, hi_u, tol_uu) if (r_lo and lo_u) else []
            ref_front = ref_cfg.get("ue_front")
            ref_front_in_candidate = [rel["maps_axis"].get(ref_front) for rel in relation] if ref_front else []
            measured["reference"] = {"asset": ref_asset, "present": present,
                                     "min": [round(v, 4) for v in r_lo] if r_lo else None,
                                     "max": [round(v, 4) for v in r_hi] if r_hi else None,
                                     "reference_ue_front": ref_front, "maps_reference_onto_candidate": relation,
                                     "reference_front_lands_on": ref_front_in_candidate}
            check("reference_front_lands_on_candidate_front",
                  present and len(relation) == 1 and ref_front_in_candidate == [want_front], measured["reference"],
                  {"unique_map": True, "reference_front_lands_on": want_front},
                  "read-only get_bounds of %s (same Tripo geometry; its front %s is %s)"
                  % (ref_asset, ref_front, ref_cfg.get("ue_front_status") or "measured"))
        except PipelineError as exc:
            measured["reference"] = {"asset": ref_asset, "error": str(exc)[:300]}
            check("reference_front_lands_on_candidate_front", False, measured["reference"])
    slot_mats = {s: ue_package(ue.call("skeletal", "get_material", {"mesh": sk, "slot_name": s}) or "")
                 for s in sk_slots}
    want_slots = build["checks"]["roundtrip_material_slots"]["measured"]["skeletal_unique"]
    check("skeletal_material_slots", sorted(sk_slots) == sorted(want_slots) and
          all(v == sk_material_pkg for v in slot_mats.values()),
          {"slots": sk_slots, "assigned": slot_mats}, {"slots": want_slots, "material": sk_material_pkg})
    measured["skeletal_lod0"] = {"sections": ue.call("skeletal", "get_section_count", {"mesh": sk, "lod_index": 0}),
                                 "vertices": ue.call("skeletal", "get_vertex_count", {"mesh": sk, "lod_index": 0}),
                                 "lods": ue.call("skeletal", "get_lod_count", {"mesh": sk}),
                                 "triangles": "not measured: SkeletalMeshTools has no triangle count"}
    if u.get("measure_skeletal_triangles"):
        # 0.7.0: triangles per LOD read in the editor (GeometryScript), compared with the build's round trip
        lods = measured["skeletal_lod0"]["lods"]
        tri = ue_editor_measure(ue, staging, "skeletal_triangles", UE_PY_MEASURE_SKELETAL,
                                {"mesh": ue_object_path(sk_pkg), "lods": lods})
        measured["skeletal_lod0"]["triangles"] = (tri.get("triangles") or [None])[0] if not tri.get("error") \
            else "not measured: %s" % tri["error"]
        measured["skeletal_lods"] = tri
        band = skeletal_adopt().expected_skeletal_triangles(build)
        t0 = measured["skeletal_lod0"]["triangles"]
        check("skeletal_triangles_lod0_as_build", isinstance(t0, int) and band["min"] <= t0 <= band["max"],
              t0, band, "Blender round trip %d (%s); UE's mesh build may drop the near-degenerate slivers the build "
                        "counted" % (band["max"], " + ".join(band["meshes"])))
        want_lods = (profile.get("expectations") or {}).get("skeletal_lods")
        if want_lods is not None:
            check("skeletal_lod_count", lods == want_lods and len(tri.get("triangles") or []) == want_lods,
                  {"mcp_get_lod_count": lods, "geometry_script_lods": len(tri.get("triangles") or [])}, want_lods,
                  "the FBX carries LOD0 only; no LODs are generated at import (proposal: LODs are a later decision)")
    sockets = ue.call("skeletal", "get_socket_names", {"mesh": sk}) or []
    sock_detail = {}
    for s in sockets:
        sock_detail[s] = {"bone": ue.call("skeletal", "get_socket_bone", {"mesh": sk, "socket_name": s}),
                          "transform": ue.call("skeletal", "get_socket_transform", {"mesh": sk, "socket_name": s})}
    sock_ok = sockets == [s["name"] for s in planned_sockets] and all(
        sock_detail[s["name"]]["bone"] == s["ue_bone"] and
        all(abs(sock_detail[s["name"]]["transform"]["location"][k] - v) < 1e-4
            for k, v in zip("xyz", s["location_uu"])) for s in planned_sockets)
    measured["sockets_plan"] = planned_sockets
    check("sockets_weapon_head", sock_ok, sock_detail, {s["name"]: s for s in planned_sockets},
          "location per socket: profile location_uu, else the build's UE bone-space prediction "
          "(sockets[].location_uu_for_ue); world placement against target_ue_component_uu needs a live frame")
    base_tris = ue.call("static", "get_triangle_count", {"mesh": base, "lod_index": 0})
    base_bounds = ue.call("static", "get_bounds", {"mesh": base}) or {}
    b_lo, b_hi = ue_minmax(base_bounds)
    fx, fy, fz = [v * 100.0 for v in profile["meshes"]["base"]["footprint_m"]]
    base_name = profile["meshes"]["base"]["object"]
    base_pre = build["meshes_pre_export_m"][base_name]
    want_base_tris = base_pre["triangles"] - base_pre.get("near_degenerate_triangles", 0)
    base_mat = {s: ue_package(ue.call("static", "get_material", {"mesh": base, "slot_name": s}) or "") for s in base_slots}
    measured["base"] = {"triangles_lod0": base_tris, "min": [round(v, 4) for v in b_lo] if b_lo else None,
                        "max": [round(v, 4) for v in b_hi] if b_hi else None, "slots": base_mat,
                        "vertices_lod0": ue.call("static", "get_vertex_count", {"mesh": base, "lod_index": 0})}
    check("base_triangles", base_tris == want_base_tris, base_tris, want_base_tris,
          "Blender %d minus %d near-degenerate slivers (area < %s cm2) that UE's mesh build removes"
          % (base_pre["triangles"], base_pre.get("near_degenerate_triangles", 0),
             base_pre.get("near_degenerate_area_cm2_below")))
    check("base_footprint_pivot", b_lo is not None and
          all(abs(a - b) <= tol_uu for a, b in zip(b_lo + b_hi, [-fx / 2, -fy / 2, 0, fx / 2, fy / 2, fz])),
          measured["base"], {"min": [-fx / 2, -fy / 2, 0], "max": [fx / 2, fy / 2, fz]})
    check("base_material_slot", len(base_slots) == profile["expectations"]["base_material_slots"] and
          all(v == default_mi_pkg for v in base_mat.values()), base_mat, default_mi_pkg)
    import_contract_checks(ue, imports, sk, base, getp, check, measured, vertex_mask_base)
    want_uv = u.get("expect_uv_channels")
    if want_uv is not None:
        # 0.9.0: UV0 atlas + UV1 in metres (M_UM_Figure_v2 UseUV1Metres) survive the import on both meshes
        uv = {"skeletal_lods_uv_sets": (measured.get("skeletal_lods") or {}).get("uv_sets"),
              "skeletal_uv_error": (measured.get("skeletal_lods") or {}).get("uv_sets_error"),
              "base_uv_channels_lod0": (imports.get("base") or {}).get("uv_channels_lod0"),
              "base_build_generate_lightmap_uvs": (imports.get("base") or {}).get("build_generate_lightmap_uvs"),
              "base_uv_error": (imports.get("base") or {}).get("uv_read_back_error")}
        measured["uv_channels"] = uv
        check("uv_channels_as_profile", (uv["skeletal_lods_uv_sets"] or [None])[0] == want_uv and
              uv["base_uv_channels_lod0"] == want_uv and uv["base_build_generate_lightmap_uvs"] is False, uv,
              {"uv_channels": want_uv, "base_generate_lightmap_uvs": False},
              "UV0 atlas + UV1 in metres; the base must not generate lightmap UVs into UV1")
    dirty = {a: ue.call("asset", "is_dirty", {"asset_path": a}) for a in after}
    check("assets_saved", bool(saved) and not any(dirty.values()), {"save_assets": saved, "dirty": dirty})
    measured["fbx_import_log"] = fbx_log

    # comparisons with proposals (never pass/fail the stage; GD-058 is open)
    lim = profile.get("proposed_limits_for_comparison_only") or {}
    sk_tris = sum(build["roundtrip"]["skeletal"]["meshes"][n]["triangles"] for n in build["roundtrip"]["skeletal"]["meshes"])
    all_tris = sk_tris + (base_tris or 0)
    tri_key = next((k for k in ("hero_triangles", "sidekick_triangles") if lim.get(k)), "hero_triangles")
    proposals = {
        "source": lim.get("source"),
        "hero_triangles": {"measured_skeletal": sk_tris, "measured_with_base": all_tris,
                           "proposed": lim.get(tri_key), "proposed_key": tri_key,
                           "within": bool(lim.get(tri_key)) and lim[tri_key][0] <= all_tris <= lim[tri_key][1]},
        "material_slots": {"measured_skeletal": len(sk_slots), "measured_base": len(base_slots),
                           "proposed_max": lim.get("material_slots_max"),
                           "within": len(sk_slots) <= lim.get("material_slots_max", 99)},
        "texture_px": {"measured": atlas["size"], "proposed": lim.get("texture_px")},
        "height_uu": {"measured_figure_top": figure_top_uu, "measured_skeletal_top": round(hi_u[2], 3) if hi_u else None,
                      "proposed": lim.get("height_uu"),
                      "within": lim.get("height_uu", [0, 0])[0] <= figure_top_uu <= lim.get("height_uu", [0, 0])[1]},
        "base_uu": {"measured": [round(fx, 3), round(fy, 3), round(fz, 3)],
                    "proposed_diameter": lim.get("base_diameter_uu"), "proposed_height": lim.get("base_height_uu")},
    }
    passed = all(c["passed"] for c in checks.values())
    report = {
        "stage": UE_STAGE, "logic": UE_SKELETAL_ADOPT_LOGIC_VERSION if adopted else UE_CANDIDATE_LOGIC_VERSION,
        "candidate_logic": UE_CANDIDATE_LOGIC_VERSION, "profile": profile["profile_id"], "kind": run_profile(m),
        "backend": ue.describe(), "status": "technically_imported" if passed else "failed",
        "inputs": dict(sorted(inputs.items())),
        "destination": {"folder": folder, "assets": names},
        "previous_assets_deleted": deleted, "assets": after,
        "measured": measured, "checks": checks, "passed": passed,
        "comparison_with_proposals_not_budgets": proposals,
        "tool_name_style": ue.tool_name_style,
        "not_checked": [
            "art acceptance, silhouette, lighting, K1/K2/K3 with HUD and boardState (art track)",
            "animation clips and deformation (no clips are imported by this stage)",
            ("skeletal triangle count inside UE: measured through GeometryScript (check skeletal_triangles_lod0_as_build)"
             if u.get("measure_skeletal_triangles") else
             "skeletal triangle count inside UE (no MCP tool); Blender round trip is authoritative"),
            "packaged build / cook of the candidate folder",
            "selection collision capsule (04 §3.1 proposal)",
            ("M_UM_* graphs: verified by tools/tripo-pipeline/um_masters.py verify (graph signature, CPD layout); this "
             "stage checks the parents, parameters and texture/colour values of the MIs") if um else
            ("shared master material (04 §1): the candidate keeps its own %s, like the production import; deviation "
             "recorded (route own-material; the um-master route uses M_UM_Figure / M_UM_BaseMarker)" % u["material"]),
        ],
    }
    out = staging / "ue-import-report.json"
    out.write_text(dump_json(report), encoding="utf-8")
    calls = staging / "ue-mcp-calls.json"
    calls.write_text(dump_json(ue.calls), encoding="utf-8")
    failed = sorted(k for k, c in checks.items() if not c["passed"])
    return StageResult({"reports/ue-import-report.json": out, "reports/ue-mcp-calls.json": calls},
                       {"passed": passed, "failed_checks": failed, "primary_asset": plan["primary"],
                        "kind": run_profile(m), "assets": len(after)},
                       passed, None if passed else "ue-import failed: %s" % ", ".join(failed))


# ------------------------------------------------- static-candidate: adopt, ue-import

ADOPT_PRESET_KEYS = ("axis_forward", "axis_up", "export_space_rotation_z_degrees", "temporary_data_scale",
                     "patch_fbx_unit_scale_to", "apply_scale_options", "use_triangles", "mesh_smooth_type",
                     "path_mode")


def static_candidate_files(profile: dict) -> dict:
    """Repo-relative paths of the adopted candidate: fbx, texture:<key>, report, readback."""
    c = profile["candidate"]
    base = c["dir"].rstrip("/")
    files = {"fbx": "%s/%s" % (base, c["fbx"]), "report": "%s/%s" % (base, c["report"]),
             "readback": "%s/%s" % (base, c["readback"])}
    for key, rel in sorted(c["textures"].items()):
        files["texture:" + key] = "%s/%s" % (base, rel)
    return files


def skeletal_adopt():
    """tools/tripo-pipeline/skeletal_adopt.py (profile skeletal-adopt); imported on use."""
    import skeletal_adopt as module
    return module


def fp_adopt(ctx: Context) -> dict:
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    if run_profile(m) == SKELETAL_ADOPT:
        sa = skeletal_adopt()
        files = {key: (sha256_file(ctx.repo_path(rel)) if ctx.repo_path(rel).is_file() else None)
                 for key, rel in sorted(sa.candidate_files(profile).items())}
        return {"logic": sa.ADOPT_SKELETAL_LOGIC_VERSION, "module_sha256": sha256_file(TOOL_DIR / "skeletal_adopt.py"),
                "profile_sha256": sha256_file(ppath), "files": files, "fbx_preset": fbx_preset(ctx)["sha256"]}
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    files = {}
    for key, rel in sorted(static_candidate_files(profile).items()):
        path = ctx.repo_path(rel)
        files[key] = sha256_file(path) if path.is_file() else None
    return {"logic": ADOPT_LOGIC_VERSION, "profile_sha256": sha256_file(ppath), "source_sha256": primary["sha256"],
            "files": files, "fbx_preset": fbx_preset(ctx)["sha256"]}


def exec_adopt(ctx: Context, staging: Path) -> StageResult:
    """Pin the externally built static candidate (FBX + BC/N/ORM) against its own reports.

    Nothing is copied: the report records repo-relative paths and SHA-256; ue-import re-hashes them.
    """
    m = ctx.manifest
    if run_profile(m) == SKELETAL_ADOPT:
        return exec_adopt_skeletal(ctx, staging)
    profile, ppath = load_build_profile(ctx)
    c = profile["candidate"]
    files = static_candidate_files(profile)
    missing = [rel for rel in files.values() if not ctx.repo_path(rel).is_file()]
    if missing:
        raise PipelineError("static candidate files missing: %s" % missing)
    hashes = {key: sha256_file(ctx.repo_path(rel)) for key, rel in sorted(files.items())}
    report = json.loads(ctx.repo_path(files["report"]).read_text(encoding="utf-8"))
    readback = json.loads(ctx.repo_path(files["readback"]).read_text(encoding="utf-8"))
    primary = source_file(m, m["config"]["primary_source"], m["config"]["primary_role"])
    preset = fbx_preset(ctx)
    preset_data = json.loads(preset["path"].read_text(encoding="utf-8"))
    checks = {}

    def check(name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    check("candidate_report_schema", report.get("schema") == c["report_schema"], report.get("schema"),
          c["report_schema"])
    failed_checks = sorted(k for k, v in (report.get("checks") or {}).items() if v is not True)
    check("candidate_report_checks_passed", report.get("checks_passed") is True and not failed_checks,
          {"checks_passed": report.get("checks_passed"), "failed": failed_checks})
    check("candidate_not_claimed_art_accepted", (report.get("claims") or {}).get("art_accepted") is False,
          report.get("claims"))
    check("candidate_built_from_registered_primary_source",
          (report.get("source") or {}).get("sha256") == primary["sha256"],
          (report.get("source") or {}).get("sha256"), primary["sha256"])
    exp = report.get("export") or {}
    check("fbx_bytes_match_candidate_report", hashes["fbx"] == exp.get("sha256"), hashes["fbx"], exp.get("sha256"))
    outs = (report.get("textures") or {}).get("outputs") or {}
    tex_ok = {k: hashes["texture:" + k] == (outs.get(k) or {}).get("sha256") for k in c["textures"]}
    check("texture_bytes_match_candidate_report", all(tex_ok.values()), tex_ok)
    size = (report.get("params") or {}).get("texture_size")
    px = {k: inspect_png(ctx.repo_path(files["texture:" + k])).get("pixels") for k in c["textures"]}
    check("texture_size", all(v == [size, size] for v in px.values()), px, [size, size])
    settings = exp.get("settings") or {}
    diffs = {k: [settings.get(k), preset_data.get(k)] for k in ADOPT_PRESET_KEYS
             if settings.get(k) != preset_data.get(k)}
    conformance = exp.get("um_fbx_v1_conformance") or []
    check("fbx_export_settings_equal_preset", not diffs and bool(conformance) and
          all(i.get("conforms") for i in conformance),
          {"differences": diffs, "preset": preset["rel"], "conformance_rows": len(conformance)},
          note="candidate-report export.settings vs %s" % preset["rel"])
    rt = report.get("roundtrip") or {}
    topo = readback.get("topology_welded_1um") or {}
    check("readback_is_this_fbx", Path(readback.get("fbx", "")).as_posix() == files["fbx"], readback.get("fbx"),
          files["fbx"])
    check("readback_triangles_equal_report", readback.get("triangles") == rt.get("triangles"),
          readback.get("triangles"), rt.get("triangles"))
    check("readback_single_mesh_no_armature",
          readback.get("armatures") == 0 and len(readback.get("mesh_objects") or []) == 1,
          {"armatures": readback.get("armatures"), "mesh_objects": readback.get("mesh_objects")})
    check("readback_closed_manifold", bool(topo) and all(v == 0 for v in topo.values()), topo)
    check("readback_material_slots_equal_report",
          len(readback.get("material_slots") or []) == report.get("material_slots"),
          readback.get("material_slots"), report.get("material_slots"))
    lo, hi = readback.get("bounds_min_uu"), readback.get("bounds_max_uu")
    expected = {
        "triangles": rt.get("triangles"),
        "material_slots": report.get("material_slots"),
        "texture_px": size,
        "size_uu_at_import_scale_1": rt.get("expected_ue_dimensions_uu_at_import_scale_1"),
        # FBX read back in Blender = UM_FBX_v1 export frame; UE shows it as (x, -y, z) (ART-001)
        "ue_bounds_uu_predicted": {"min": [lo[0], -hi[1], lo[2]], "max": [hi[0], -lo[1], hi[2]]} if lo and hi else None,
        "protrusion_axis_export_frame": readback.get("protrusion_axis_blender"),
        "protrusion_direction_deg_from_plus_x": readback.get("protrusion_direction_deg_from_plus_x_ccw"),
    }
    passed = all(v["passed"] for v in checks.values())
    script = report.get("script_sha256_lf")
    out = {"stage": "adopt", "logic": ADOPT_LOGIC_VERSION, "status": "measured" if passed else "failed",
           "profile": {"path": m["config"]["build_profile"], "id": profile["profile_id"], "sha256": sha256_file(ppath)},
           "inputs": {files[k]: v for k, v in sorted(hashes.items())}, "keys": files,
           "expectations_for_ue": expected, "checks": checks, "passed": passed,
           "note": "the candidate is built outside this tool (%s); adopt copies nothing and re-hashes it"
                   % ("static_prop_candidate.py, script sha256 (LF) %s" % script if script else "external script")}
    path = staging / "adopt-report.json"
    path.write_text(dump_json(out), encoding="utf-8")
    failed = sorted(k for k, v in checks.items() if not v["passed"])
    return StageResult({"reports/adopt-report.json": path},
                       {"passed": passed, "failed_checks": failed, "inputs": len(hashes)},
                       passed, None if passed else "adopt failed: %s" % ", ".join(failed))


def exec_adopt_skeletal(ctx: Context, staging: Path) -> StageResult:
    """Profile skeletal-adopt: pin the H2 bake (SK + base FBX, 2K BC/N/ORM/TeamMask) against the bake's own reports and
    write the normalised views ue-import reads (skeletal_adopt.adopt). Copies nothing."""
    m = ctx.manifest
    profile, ppath = load_build_profile(ctx)
    sa = skeletal_adopt()
    preset = fbx_preset(ctx)
    try:
        res = sa.adopt(profile, ctx.repo_path, sha256_file, lambda p: inspect_png(p).get("pixels"),
                       json.loads(preset["path"].read_text(encoding="utf-8")))
    except sa.AdoptError as exc:
        raise PipelineError("adopt: %s" % exc)
    passed = res["passed"]
    out = {"stage": "adopt", "logic": sa.ADOPT_SKELETAL_LOGIC_VERSION, "kind": SKELETAL_ADOPT,
           "status": "measured" if passed else "failed",
           "profile": {"path": m["config"]["build_profile"], "id": profile["profile_id"], "sha256": sha256_file(ppath)},
           "fbx_preset": {"path": preset["rel"], "sha256": preset["sha256"]},
           "bake": res["bake"], "inputs": res["inputs"], "keys": res["keys"], "checks": res["checks"],
           "passed": passed, "views": res["views"],
           "note": "the candidate is built outside this tool (%s, profile %s); adopt copies nothing and re-hashes it; "
                   "views.build / views.atlas are what ue-import reads" % (res["bake"]["report_format"],
                                                                            res["bake"]["profile_id"])}
    path = staging / "adopt-report.json"
    path.write_text(dump_json(out), encoding="utf-8")
    failed = sorted(k for k, v in res["checks"].items() if not v["passed"])
    return StageResult({"reports/adopt-report.json": path},
                       {"passed": passed, "failed_checks": failed, "inputs": len(res["inputs"])},
                       passed, None if passed else "adopt failed: %s" % ", ".join(failed))


def adopted_skeletal_inputs(ctx: Context) -> tuple:
    """(build view, atlas view, inputs {rel: sha}, paths {"skeletal", "base", "texture:<key>": Path}) of an adopted
    skeletal candidate; every pinned file is re-hashed (a file changed since adopt blocks the UE stage)."""
    adopt = json.loads(ctx.run_path("reports/adopt-report.json").read_text(encoding="utf-8"))
    for rel, digest in adopt["inputs"].items():
        path = ctx.repo_path(rel)
        if not path.is_file() or sha256_file(path) != digest:
            raise PipelineError("adopted candidate file missing or changed since adopt: %s" % rel)
    keys = adopt["keys"]
    paths = {"skeletal": ctx.repo_path(keys["fbx:skeletal"]), "base": ctx.repo_path(keys["fbx:base"])}
    paths.update({k: ctx.repo_path(v) for k, v in keys.items() if k.startswith("texture:")})
    return adopt["views"]["build"], adopt["views"]["atlas"], dict(adopt["inputs"]), paths


def exec_ue_static_candidate(ctx: Context, staging: Path) -> StageResult:
    m = ctx.manifest
    ue = ctx.unreal()
    rec = m["stages"][UE_STAGE]
    plan = ue_plan(ctx)
    profile, names, folder = plan["profile"], plan["names"], plan["folder"]
    u = profile["ue"]
    adopt = json.loads(ctx.run_path("reports/adopt-report.json").read_text(encoding="utf-8"))
    for rel, digest in adopt["inputs"].items():
        path = ctx.repo_path(rel)
        if not path.is_file() or sha256_file(path) != digest:
            raise PipelineError("adopted candidate file missing or changed since adopt: %s" % rel)
    files = adopt["keys"]
    exp = adopt["expectations_for_ue"]
    owned = set(rec.get("ue_owned_assets") or [])
    before = ue_listing(ue, folder)
    foreign = [a for a in before if a not in owned]
    if foreign:
        raise PipelineError("UE folder %s holds assets this run did not create: %s; refusing to delete or "
                            "import next to them (use another --ue-folder)" % (folder, foreign[:10]), EXIT_CONFLICT)
    deleted = ue_delete_owned(ue, before)
    rec["ue_owned_assets"] = []
    ctx.save()
    pre_import = ue_listing(ue, folder)
    created = []

    def track(result):
        items = result if isinstance(result, list) else [result]
        created.extend(ue_package(x) for x in items if x)

    def setp(ref, props):
        return ue.call("object", "set_properties", {"instance": ref, "values": json.dumps(props)})

    def getp(ref, props):
        raw = ue.call("object", "get_properties", {"instance": ref, "properties": props})
        return json.loads(raw) if isinstance(raw, str) else (raw or {})

    # textures: BC sRGB, N TC_Normalmap (DirectX, no green flip), ORM linear TC_Masks
    for key, tcfg in sorted(u["textures"].items()):
        pkg = names["texture:" + key]
        track(ue.call("texture", "import_file", {"folder_path": pkg.rsplit("/", 1)[0], "asset_name": tcfg["asset"],
                                                 "source_file": str(ctx.repo_path(files["texture:" + key]))}))
        props = {"SRGB": tcfg["srgb"], "CompressionSettings": tcfg["compression"]}
        if "flip_green" in tcfg:
            props["bFlipGreenChannel"] = tcfg["flip_green"]
        setp(ue_obj(pkg), props)
    tex_path = {k: ue_object_path(names["texture:" + k]) for k in u["textures"]}
    # material route: the shared master when it exists AND exposes the texture parameters, else own material
    master_cfg = u.get("shared_master") or {}
    master = master_cfg.get("asset")
    route = {"shared_master": master, "used": "own_material"}
    if master:
        try:
            present = bool(ue.call("asset", "exists", {"path": master}))
        except PipelineError:
            present = False
        route["shared_master_exists"] = present
        if present:
            params = ue.call("instance", "list_parameters", {"material": ue_obj(master)}) or []
            have = {p.get("name"): p.get("type") for p in params if isinstance(p, dict)}
            route["shared_master_parameters"] = have
            want = master_cfg.get("texture_parameters") or {}
            route["missing_texture_parameters"] = sorted(v for v in want.values() if v not in have)
            if want and not route["missing_texture_parameters"]:
                route["used"] = "shared_master"
    wiring = {}
    mat_pkg = names["material"]
    inst_pkg = names["instance"]
    if route["used"] == "shared_master":
        parent = ue_obj(master)
        route["deviation"] = None
    else:
        if route.get("shared_master_exists"):
            why = "exists but has no texture parameters %s" % route.get("missing_texture_parameters")
        else:
            why = "is absent" if master else "is not configured"
        route["deviation"] = ("shared master %s %s; the candidate keeps its own %s (BC x TeamColor, DirectX "
                              "normal, ORM) as the parent of %s" % (master, why, u["material"], u["instance"]))
        track(ue.call("material", "create_material", {"folder_path": mat_pkg.rsplit("/", 1)[0],
                                                      "asset_name": u["material"]}))
        mat = ue_obj(mat_pkg)

        def expr(cls, x, y, props=None):
            ref = ue.call("material", "add_expression", {"material_or_function": mat, "x": x, "y": y,
                                                         "expression_class": {"refPath": "/Script/Engine." + cls}})
            if props:
                setp(ref, props)
            return ref

        bc = expr("MaterialExpressionTextureSampleParameter2D", -800, 0,
                  {"ParameterName": "BaseColorTexture", "Texture": tex_path["BC"], "SamplerType": "SAMPLERTYPE_Color"})
        team = expr("MaterialExpressionVectorParameter", -800, 220,
                    {"ParameterName": "TeamColor", "DefaultValue": {"R": 1, "G": 1, "B": 1, "A": 1}})
        mul = expr("MaterialExpressionMultiply", -480, 60)
        nrm = expr("MaterialExpressionTextureSampleParameter2D", -800, 420,
                   {"ParameterName": "NormalTexture", "Texture": tex_path["N"], "SamplerType": "SAMPLERTYPE_Normal"})
        orm = expr("MaterialExpressionTextureSampleParameter2D", -800, 680,
                   {"ParameterName": "ORMTexture", "Texture": tex_path["ORM"], "SamplerType": "SAMPLERTYPE_Masks"})
        ue.call("material", "connect_expressions", {"from_expression": bc, "from_output_name": "RGB",
                                                    "to_expression": mul, "to_input_name": "A"})
        ue.call("material", "connect_expressions", {"from_expression": team, "from_output_name": "",
                                                    "to_expression": mul, "to_input_name": "B"})
        wiring = {"MP_BaseColor": (mul, ""), "MP_Normal": (nrm, "RGB"), "MP_AmbientOcclusion": (orm, "R"),
                  "MP_Roughness": (orm, "G"), "MP_Metallic": (orm, "B")}
        for prop, (ref, out) in wiring.items():
            ue.call("material", "connect_to_output", {"expression": ref, "output_name": out, "material_property": prop})
        setp(mat, {"TwoSided": bool(u.get("two_sided", False))})
        ue.call("material", "recompile", {"material_or_function": mat})
        parent = mat
    track(ue.call("instance", "create", {"folder_path": inst_pkg.rsplit("/", 1)[0], "asset_name": u["instance"],
                                         "parent": parent}))
    inst = ue_obj(inst_pkg)
    if route["used"] == "shared_master":
        for key, pname in sorted(master_cfg["texture_parameters"].items()):
            ue.call("instance", "set_texture_parameter", {"instance": inst, "name": pname,
                                                          "value": {"refPath": tex_path[key]}})
    ue.call("instance", "set_vector_parameter", {"instance": inst, "name": "TeamColor",
                                                 "value": dict(zip("rgba", u.get("team_color", [1, 1, 1, 1])))})
    # mesh: no importer materials/textures; collision removed when the profile asks for none
    sm_pkg = names["static"]
    track(ue.call("static", "import_file", {"folder_path": sm_pkg.rsplit("/", 1)[0], "asset_name": u["static_asset"],
                                            "source_file": str(ctx.repo_path(files["fbx"])),
                                            "import_materials": False, "import_textures": False,
                                            "combine_meshes": True}))
    after_import = ue_listing(ue, folder)
    rec["ue_owned_assets"] = sorted(set(after_import) | set(created))
    ctx.save()
    ctx.journal("ue_assets_owned", assets=rec["ue_owned_assets"], deleted_previous=deleted)
    sm = ue_obj(sm_pkg)

    def collision():
        body = (getp(sm, ["BodySetup"]) or {}).get("BodySetup")
        if not body:
            return {"body_setup": None, "elements": {}, "simple_elements": 0}
        data = getp(body if isinstance(body, dict) else {"refPath": body}, ["AggGeom", "CollisionTraceFlag"])
        agg = data.get("AggGeom") or {}
        counts = {k: len(v) for k, v in agg.items() if isinstance(v, list)}
        return {"body_setup": body.get("refPath") if isinstance(body, dict) else body,
                "elements": counts, "simple_elements": sum(counts.values()),
                "collision_trace_flag": data.get("CollisionTraceFlag")}

    collision_after_import = collision()
    if u.get("collision") == "none":
        ue.call("static", "remove_collisions", {"mesh": sm})
    slots = ue.call("static", "get_material_slots", {"mesh": sm}) or []
    for slot in slots:
        ue.call("static", "set_material", {"mesh": sm, "slot_name": slot, "material": inst})
    after = ue_listing(ue, folder)
    rec["ue_owned_assets"] = sorted(set(after) | set(created))
    ctx.save()
    saved = ue.call("asset", "save_assets", {"asset_paths": after})

    # ---------------------------------------------------------------- measurements
    checks, measured = {}, {"material_route": route, "collision_after_import": collision_after_import}

    def check(name, passed, value=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": value}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    planned = {k: v for k, v in names.items() if not (k == "material" and route["used"] == "shared_master")}
    expected_assets = sorted(planned.values())
    check("folder_empty_before_import", not pre_import, pre_import)
    check("assets_exactly_as_planned", sorted(after) == expected_assets, after, expected_assets,
          "no stale assets, no importer side products (import_materials/import_textures false)")
    dupes = [a for a in after if re.search(r"_\d+$", a) and re.sub(r"_\d+$", "", a) in expected_assets]
    check("no_numbered_duplicates", not dupes, dupes)
    classes = {k: str(ue.call("asset", "get_asset_class", {"asset_path": p})).rsplit(".", 1)[-1]
               for k, p in sorted(planned.items())}
    want = {"static": "StaticMesh", "material": "Material", "instance": "MaterialInstanceConstant"}
    want.update({k: "Texture2D" for k in planned if k.startswith("texture:")})
    want = {k: v for k, v in want.items() if k in planned}
    check("asset_classes", classes == want, classes, want)
    tex = {}
    for key, tcfg in sorted(u["textures"].items()):
        ref = ue_obj(names["texture:" + key])
        size = ue.call("texture", "get_size", {"texture": ref}) or {}
        props = getp(ref, ["SRGB", "CompressionSettings", "bFlipGreenChannel"])
        want_p = {"SRGB": tcfg["srgb"], "CompressionSettings": tcfg["compression"]}
        if "flip_green" in tcfg:
            want_p["bFlipGreenChannel"] = tcfg["flip_green"]
        tex[key] = {"size": [size.get("x"), size.get("y")], "properties": props, "expected": want_p,
                    "ok": [size.get("x"), size.get("y")] == [exp["texture_px"]] * 2 and
                    all(props.get(k) == v for k, v in want_p.items())}
    measured["textures"] = tex
    check("textures_size_colour_space_compression", all(t["ok"] for t in tex.values()), tex)
    inst_props = getp(inst, ["Parent", "BasePropertyOverrides"])
    parent_ref = inst_props.get("Parent")
    parent_ref = parent_ref.get("refPath") if isinstance(parent_ref, dict) else parent_ref
    overrides = inst_props.get("BasePropertyOverrides") or {}
    team_value = ue.call("instance", "get_vector_parameter", {"instance": inst, "name": "TeamColor"}) or {}
    team_want = u.get("team_color", [1, 1, 1, 1])
    measured["instance"] = {"parent": parent_ref, "base_property_overrides": overrides,
                            "TeamColor": {k: round(float(team_value.get(k, -1)), 4) for k in "rgba"}}
    two_sided_override = bool(overrides.get("bOverride_TwoSided")) and bool(overrides.get("TwoSided"))
    if route["used"] == "shared_master":
        parent_props = getp(ue_obj(master), ["TwoSided", "BlendMode"])
        tex_params = {k: ue_package(ue.call("instance", "get_texture_parameter", {"instance": inst, "name": p}) or "")
                      for k, p in master_cfg["texture_parameters"].items()}
        measured["instance"]["texture_parameters"] = tex_params
        graph_ok = all(tex_params[k] == names["texture:" + k] for k in tex_params)
    else:
        parent_props = getp(ue_obj(mat_pkg), ["TwoSided", "BlendMode", "ShadingModel"])
        graph = {}
        for prop, (ref, out) in wiring.items():
            src = ue.call("material", "get_property_input",
                          {"material": ue_obj(mat_pkg), "material_property": prop}) or {}
            graph[prop] = {"expression": (src.get("expression") or {}).get("refPath", "").rsplit(":", 1)[-1],
                           "output": src.get("output_name"),
                           "ok": (src.get("expression") or {}).get("refPath") == ref.get("refPath") and
                                 (src.get("output_name") or "") == out}
        measured["material_graph"] = graph
        graph_ok = all(g["ok"] for g in graph.values())
    measured["parent_material"] = parent_props
    check("material_bc_normal_orm_wired", graph_ok, measured.get("material_graph") or
          measured["instance"].get("texture_parameters"))
    check("material_one_sided_opaque", parent_props.get("TwoSided") is bool(u.get("two_sided", False))
          and parent_props.get("BlendMode") == "BLEND_Opaque" and not two_sided_override,
          {"parent": parent_props, "instance_two_sided_override": two_sided_override},
          {"TwoSided": bool(u.get("two_sided", False)), "BlendMode": "BLEND_Opaque"},
          "glTF from Tripo says doubleSided=true; the UE material stays one-sided (prop-barrel-report §5.4)")
    want_parent = ue_package(master) if route["used"] == "shared_master" else mat_pkg
    check("instance_parent_and_neutral_team_color",
          ue_package(parent_ref or "") == want_parent and
          all(abs(float(team_value.get(k, -1)) - c) < 1e-3 for k, c in zip("rgba", team_want)),
          measured["instance"], {"parent": want_parent, "TeamColor": team_want})
    slot_mats = {s: ue_package(ue.call("static", "get_material", {"mesh": sm, "slot_name": s}) or "") for s in slots}
    check("material_slots", len(slots) == exp["material_slots"] and all(v == inst_pkg for v in slot_mats.values()),
          {"slots": slots, "assigned": slot_mats}, {"count": exp["material_slots"], "assigned": inst_pkg})
    tris = ue.call("static", "get_triangle_count", {"mesh": sm, "lod_index": 0})
    measured["lod0"] = {"triangles": tris,
                        "vertices": ue.call("static", "get_vertex_count", {"mesh": sm, "lod_index": 0}),
                        "lods": ue.call("static", "get_lod_count", {"mesh": sm}),
                        "nanite": ue.call("static", "is_nanite_enabled", {"mesh": sm})}
    check("triangles_lod0_equal_candidate", tris == exp["triangles"], tris, exp["triangles"])
    # 0.6.0 (ue-static-candidate/2): import contract read back (engine gate memo §1 item 5)
    check("nanite_disabled", measured["lod0"]["nanite"] is False, measured["lod0"]["nanite"], False,
          "nanite == false (Nanite not enabled; MCP import_file is the legacy FbxFactory without bBuildNanite)")
    aid = getp(sm, ["AssetImportData"]).get("AssetImportData")
    aid = aid if isinstance(aid, dict) else {"refPath": aid}
    nim = getp(aid, ["NormalImportMethod"]).get("NormalImportMethod") if aid.get("refPath") else None
    measured["import_contract"] = {"asset_import_data": aid.get("refPath"), "normal_import_method": nim}
    check("normal_import_method_read_back", nim == "FBXNIM_ImportNormals", measured["import_contract"],
          "FBXNIM_ImportNormals", "MCP StaticMeshTools.import_file takes no normal method: the project default for "
          "static meshes (ImportNormals) is read back and must stay")
    if route["used"] == "shared_master":
        um = um_masters()
        spec, _ = um.load_spec(TOOL_DIR.parents[1])
        role = next((r for r in spec["masters"] if um.master_path(spec, r) == ue_package(master)), None)
        if role:
            want = sorted(um.expected_parameters(spec, role))
            have = sorted((route.get("shared_master_parameters") or {}).keys())
            missing = [p_ for p_ in want if p_ not in have]
            check("shared_master_parameters_current", not missing, {"master": master, "missing": missing},
                  {"parameters": len(want)}, "all parameters of art/um-materials/um-masters.json (%s)" % role)
    lo_u, hi_u = ue_minmax(ue.call("static", "get_bounds", {"mesh": sm}) or {})
    tol = m["config"]["ue"].get("dimension_tolerance") or DEFAULT_UE_DIMENSION_TOLERANCE
    size_uu = [hi_u[i] - lo_u[i] for i in range(3)] if lo_u else None
    measured["bounds_uu"] = {"min": [round(v, 4) for v in lo_u], "max": [round(v, 4) for v in hi_u],
                             "size": [round(v, 4) for v in size_uu]} if lo_u else None
    want_size = exp["size_uu_at_import_scale_1"]
    check("dimensions_match_candidate_at_import_scale_1", bool(size_uu) and
          all(within(a, b, tol) for a, b in zip(size_uu, want_size)), measured["bounds_uu"], want_size,
          "tolerance %.1f%% per axis X, Y, Z; MCP import_file has no import scale (1.0)" % (tol * 100))
    pt = (profile.get("expectations") or {}).get("pivot_tolerance_uu", 0.05)
    pred = exp.get("ue_bounds_uu_predicted")
    check("pivot_base_centre", bool(lo_u) and abs(lo_u[2]) <= pt and abs(lo_u[0] + hi_u[0]) / 2 <= pt and
          abs(lo_u[1] + hi_u[1]) / 2 <= pt, measured["bounds_uu"],
          {"min_z": 0, "centre_xy": [0, 0], "tolerance_uu": pt})
    check("bounds_equal_um_fbx_v1_prediction", bool(pred and lo_u) and
          all(abs(a - b) <= pt for a, b in zip(pred["min"] + pred["max"], lo_u + hi_u)), measured["bounds_uu"], pred,
          "fbx-readback bounds (export frame) as UE (x, -y, z) (ART-001); tolerance %.2f uu" % pt)
    axes = profile.get("axes") or {}
    if axes.get("protrusion_axis_ue") and size_uu:
        longer = "X" if size_uu[0] > size_uu[1] else "Y"
        check("protrusion_axis_by_bounds", longer == axes["protrusion_axis_ue"].lstrip("+-"),
              {"size_x": round(size_uu[0], 4), "size_y": round(size_uu[1], 4), "longer_horizontal_axis": longer},
              axes["protrusion_axis_ue"],
              "axis only (the bung makes that axis longer); the sign (%s) needs a frame" % axes.get("expected_ue_front"))
    coll = collision()
    measured["collision_after_stage"] = coll
    if u.get("collision") == "none":
        check("no_simple_collision", coll["simple_elements"] == 0, coll, 0,
              "UE 5.8 MCP import_file added %s simple element(s); removed with remove_collisions"
              % collision_after_import.get("simple_elements"))
    dirty = {a: ue.call("asset", "is_dirty", {"asset_path": a}) for a in after}
    check("assets_saved", bool(saved) and not any(dirty.values()), {"save_assets": saved, "dirty": dirty})
    passed = all(c["passed"] for c in checks.values())
    report = {
        "stage": UE_STAGE, "logic": UE_STATIC_LOGIC_VERSION, "profile": profile["profile_id"],
        "backend": ue.describe(), "status": "technically_imported" if passed else "failed",
        "inputs": adopt["inputs"], "destination": {"folder": folder, "assets": planned},
        "previous_assets_deleted": deleted, "assets": after, "measured": measured, "checks": checks,
        "passed": passed, "tool_name_style": ue.tool_name_style,
        "deviations": [d for d in [route.get("deviation")] if d],
        "not_checked": [
            "art acceptance, silhouette, lighting, K1/K2/K3 (art track; editor frames are diagnostics only)",
            "front sign of the bung: bounds give the axis only; see the editor frames of the evidence folder",
            "UV seams at mips >= 2 and dark grooves (prop-barrel-report §4.3/§4.4): need K-1/K-2 frames",
            "packaged build / cook of /Game/PipelineCandidates (not in DirectoriesToAlwaysCook)",
        ],
    }
    out = staging / "ue-import-report.json"
    out.write_text(dump_json(report), encoding="utf-8")
    calls = staging / "ue-mcp-calls.json"
    calls.write_text(dump_json(ue.calls), encoding="utf-8")
    failed = sorted(k for k, c in checks.items() if not c["passed"])
    return StageResult({"reports/ue-import-report.json": out, "reports/ue-mcp-calls.json": calls},
                       {"passed": passed, "failed_checks": failed, "primary_asset": plan["primary"],
                        "kind": STATIC, "assets": len(after), "material_route": route["used"]},
                       passed, None if passed else "ue-import failed: %s" % ", ".join(failed))


STAGE_IMPL = {
    "preflight": (fp_preflight, exec_preflight, True),
    "import": (fp_import, exec_import, False),
    "verify": (fp_verify, exec_verify, False),
    "export": (fp_export, exec_export, False),
    "atlas": (fp_atlas, exec_atlas, False),
    "build": (fp_build, exec_build, False),
    "adopt": (fp_adopt, exec_adopt, False),
    UE_STAGE: (fp_ue_import, exec_ue_import, False),
}
STAGE_PROBES = {UE_STAGE: probe_ue_import}
EXPORT_OUTPUT_PREFIX = "export/"


def outputs_intact(ctx: Context, rec: dict) -> bool:
    outputs = rec.get("outputs") or {}
    if not outputs:
        return False
    for rel, info in outputs.items():
        path = ctx.run_path(rel)
        if not path.is_file() or path.stat().st_size != info["bytes"] or sha256_file(path) != info["sha256"]:
            return False
    return True


def promote(ctx: Context, stage: str, result: StageResult) -> tuple:
    """Move staged files into place; identical files are not rewritten (hash dedupe)."""
    recorded, changes = {}, {}
    for rel, staged in sorted(result.outputs.items()):
        final = ctx.run_path(rel)
        digest = sha256_file(staged)
        size = staged.stat().st_size
        if final.is_file() and sha256_file(final) == digest:
            staged.unlink()
            changes[rel] = "unchanged"
        else:
            changes[rel] = "replaced" if final.exists() else "new"
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, final)
        recorded[rel] = {"sha256": digest, "bytes": size}
    log = ctx.staging_root / stage / ("%s.log" % stage)
    if log.is_file():
        (ctx.run_dir / "logs").mkdir(exist_ok=True)
        os.replace(log, ctx.run_dir / "logs" / ("%s.log" % stage))
    return recorded, changes


def register_exports(ctx: Context, stage: str, recorded: dict, fingerprint: str) -> list:
    index = ctx.manifest.setdefault("exports", [])
    added = []
    for rel, info in recorded.items():
        if not rel.startswith(EXPORT_OUTPUT_PREFIX):
            continue
        if any(e["sha256"] == info["sha256"] for e in index):
            continue  # identical bytes already exported once: no duplicate entry
        for entry in index:
            if entry["path"] == rel and not entry.get("superseded_by"):
                entry["superseded_by"] = info["sha256"]
        entry = {"path": rel, "sha256": info["sha256"], "bytes": info["bytes"], "stage": stage,
                 "stage_fingerprint": fingerprint, "written_at": now_iso(),
                 "status": "technically_exported_not_art_accepted"}
        index.append(entry)
        added.append(rel)
    return added


def execute_stage(ctx: Context, name: str, force: bool = False) -> str:
    fp_fn, exec_fn, always = STAGE_IMPL[name]
    m = ctx.manifest
    rec = m["stages"].setdefault(name, {"status": "pending", "attempts": 0})
    fingerprint = sha256_json(fp_fn(ctx))
    up_to_date = (rec.get("status") == "completed" and rec.get("fingerprint") == fingerprint
                  and outputs_intact(ctx, rec))
    if up_to_date and name in STAGE_PROBES and not force:
        up_to_date = STAGE_PROBES[name](ctx, rec)
    if up_to_date and not force and not always:
        ctx.journal("stage_skipped", stage=name, reason="completed; fingerprint and output hashes unchanged",
                    fingerprint=fingerprint)
        return "skipped"
    staging = ctx.staging_root / name
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    if not always:
        rec.update(status="running", started_at=now_iso(), pending_fingerprint=fingerprint,
                   attempts=rec.get("attempts", 0) + 1)
        rec.pop("error", None)
        ctx.save()
    ctx.journal("stage_started", stage=name, fingerprint=fingerprint, forced=force)
    try:
        result = exec_fn(ctx, staging)
    except PipelineError as exc:
        log = staging / ("%s.log" % name)
        if log.is_file():
            (ctx.run_dir / "logs").mkdir(exist_ok=True)
            shutil.copyfile(log, ctx.run_dir / "logs" / ("%s.failed.log" % name))
        rec.update(status="failed", error=str(exc), finished_at=now_iso())
        rec.pop("pending_fingerprint", None)
        ctx.save()
        ctx.journal("stage_failed", stage=name, error=str(exc))
        raise
    if ctx.interrupt_at == name:
        # Diagnostic hook: die after the work, before anything is committed (lock and
        # "running" state are left behind exactly like a crash or a killed process).
        ctx.journal("simulated_interrupt", stage=name)
        sys.stdout.flush()
        os._exit(EXIT_INTERRUPTED)
    recorded, changes = promote(ctx, name, result)
    if always and up_to_date and all(v == "unchanged" for v in changes.values()) and result.passed:
        ctx.journal("stage_revalidated", stage=name, fingerprint=fingerprint, summary=result.summary)
        shutil.rmtree(staging, ignore_errors=True)
        return "revalidated"
    rec.pop("pending_fingerprint", None)
    if not result.passed:
        rec.update(status="failed", error=result.error, finished_at=now_iso(), outputs=recorded,
                   summary=result.summary, fingerprint=None)
        ctx.save()
        ctx.journal("stage_failed", stage=name, error=result.error, outputs=changes)
        shutil.rmtree(staging, ignore_errors=True)
        raise PipelineError(result.error or "%s failed" % name)
    if always:
        rec["attempts"] = rec.get("attempts", 0) + 1
        rec.setdefault("started_at", now_iso())
    rec.update(status="completed", fingerprint=fingerprint, finished_at=now_iso(), outputs=recorded,
               tool_version=TOOL_VERSION, backend=ctx.backend,
               summary=result.summary)
    added = register_exports(ctx, name, recorded, fingerprint)
    ctx.save()
    ctx.journal("stage_completed", stage=name, fingerprint=fingerprint, outputs=changes, exports_added=added)
    shutil.rmtree(staging, ignore_errors=True)
    return "executed"


def interrupted_stages(manifest: dict) -> list:
    return [n for n in KNOWN_STAGES if (manifest["stages"].get(n) or {}).get("status") == "running"]


def active_stages(ctx: Context) -> tuple:
    """Local stages of the run's profile always; the UE stage once configured (it then needs --backend mcp)."""
    return stage_order(ctx.manifest) if ctx.manifest["config"].get("ue") else base_stages(ctx.manifest)


def run_stages(ctx: Context, stages, force=()) -> dict:
    outcome = {}
    for name in stages:
        if name == UE_STAGE and ctx.backend != "mcp":
            ctx.journal("stage_not_run", stage=name, reason="needs --backend mcp")
            outcome[name] = "not-run (needs --backend mcp)"
            continue
        outcome[name] = execute_stage(ctx, name, force=name in force)
    return outcome


def require_upstream(ctx: Context, name: str) -> None:
    order = list(stage_order(ctx.manifest))
    if name not in order:
        raise PipelineError("stage %s is not part of profile %s (stages: %s)"
                            % (name, run_profile(ctx.manifest), ", ".join(order)), EXIT_USAGE)
    for up in order[1:order.index(name)]:
        rec = ctx.manifest["stages"].get(up) or {}
        if rec.get("status") != "completed":
            raise PipelineError("stage %s needs %s completed first (status: %s)" % (name, up, rec.get("status")),
                                EXIT_USAGE)


# ---------------------------------------------------------------------- commands

def new_manifest(args) -> dict:
    manifest = {
        "schema": RUN_SCHEMA,
        "run_id": args.run_id or Path(args.run_dir).resolve().name,
        "asset_id": args.asset_id,
        "created_at": now_iso(),
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION},
        "status_legend": STATUS_LEGEND,
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False,
                   "note": "technical pipeline evidence only"},
        "network": {"tripo_calls": 0, "paid_tasks_created": 0,
                    "policy": "no network code; Tripo results are registered from existing local files"},
        "config": {
            "primary_source": args.primary_source,
            "primary_role": args.primary_role,
            "export_basename": args.export_basename or "%s_%s" % (args.asset_id, args.primary_role),
            "triangle_loss_tolerance": args.triangle_loss_tolerance,
        },
        "sources": {},
        "stages": {},
        "exports": [],
        "generation_requests": [],
    }
    profile = getattr(args, "profile", None) or PASSTHROUGH
    if profile in BUILD_PROFILE_KINDS:
        if not args.build_profile:
            raise PipelineError("--profile %s needs --build-profile <repo-relative JSON>" % profile, EXIT_USAGE)
        manifest["config"]["profile"] = profile
        manifest["config"]["build_profile"] = Path(args.build_profile).as_posix()
    elif getattr(args, "build_profile", None):
        raise PipelineError("--build-profile is only used with --profile %s" % "|".join(BUILD_PROFILE_KINDS),
                            EXIT_USAGE)
    return manifest


def cmd_init(ctx: Context, args) -> int:
    fresh = new_manifest(args)
    if ctx.manifest_path.exists():
        ctx.load()
        existing_cfg = {k: v for k, v in ctx.manifest.get("config", {}).items() if k != "ue"}
        same = ctx.manifest.get("asset_id") == fresh["asset_id"] and existing_cfg == fresh["config"]
        if not same:
            raise PipelineError("run already initialised with a different asset/config; use a new --run-dir",
                                EXIT_CONFLICT)
        ctx.journal("init_noop", reason="already initialised with identical config")
        print("init: already initialised, no change")
        return EXIT_OK
    ctx.manifest, ctx._manifest_text = fresh, None
    ctx.save()
    ctx.journal("init", config=fresh["config"], asset_id=fresh["asset_id"])
    print("init: created %s" % ctx.manifest_path)
    return EXIT_OK


def cmd_register(ctx: Context, args) -> int:
    ctx.load()
    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    validate_spec(spec)
    if spec["asset_id"] != ctx.manifest["asset_id"]:
        raise PipelineError("spec asset %s != run asset %s" % (spec["asset_id"], ctx.manifest["asset_id"]), EXIT_USAGE)
    record = build_source_record(ctx, spec)
    sid = spec["source_id"]
    existing = ctx.manifest["sources"].get(sid)
    if existing:
        volatile = ("registered_at", "registered_by")
        comparable = {k: v for k, v in existing.items() if k not in volatile}
        if canonical(comparable) == canonical({k: v for k, v in record.items() if k not in volatile}):
            ctx.journal("register_noop", source_id=sid, reason="identical spec and file hashes already registered")
            print("register-source: %s already registered with identical content; no change" % sid)
            return EXIT_OK
        raise PipelineError("source %s already registered with different content; refusing to overwrite "
                            "(register under a new source_id or use a new run dir)" % sid, EXIT_CONFLICT)
    record["registered_at"] = now_iso()
    ctx.manifest["sources"][sid] = record
    ctx.save()
    ctx.journal("source_registered", source_id=sid, task_id=spec["task_id"], service=spec["service"],
                files={f["role"]: f["sha256"] for f in record["files"]},
                historical_credits_observed=record["historical_credits_observed"])
    print("register-source: registered %s (%d files, historical spend %s; this command spent 0)"
          % (sid, len(record["files"]), record["historical_credits_observed"]))
    return EXIT_OK


def print_outcome(outcome: dict) -> None:
    for name, state in outcome.items():
        print("  %-9s %s" % (name, state))


def cmd_stage(ctx: Context, args) -> int:
    ctx.load()
    if interrupted_stages(ctx.manifest):
        raise PipelineError("interrupted stage(s) %s; use resume" % interrupted_stages(ctx.manifest), EXIT_NEEDS_RESUME)
    name = args.command
    if name != "preflight":
        require_upstream(ctx, name)
    outcome = {name: execute_stage(ctx, name, force=args.force)}
    print_outcome(outcome)
    return EXIT_OK


def cmd_ue_import(ctx: Context, args) -> int:
    ctx.load()
    ctx.unreal()  # refuses early (before touching the manifest) for --backend headless
    if interrupted_stages(ctx.manifest):
        raise PipelineError("interrupted stage(s) %s; use resume" % interrupted_stages(ctx.manifest), EXIT_NEEDS_RESUME)
    require_upstream(ctx, UE_STAGE)
    wanted = {"folder": (args.ue_folder or "").rstrip("/") or None, "asset_name": args.asset_name,
              "import_materials": not args.no_materials, "import_textures": not args.no_materials,
              "dimension_tolerance": args.dimension_tolerance}
    if run_profile(ctx.manifest) == CANDIDATE:
        # The candidate path never lets the FBX importer create materials/textures: it imports the atlas
        # PNGs and builds its own material. Record the flags that are really used (T4 wrote true here).
        wanted.update(import_materials=False, import_textures=False,
                      import_note="skeletal-candidate: meshes imported with import_materials=false, "
                                  "import_textures=false; textures come from the atlas stage")
    elif run_profile(ctx.manifest) == SKELETAL_ADOPT:
        wanted.update(import_materials=False, import_textures=False,
                      import_note="skeletal-adopt: meshes imported with import_materials=false, "
                                  "import_textures=false; textures are the adopted 2K runtime PNGs")
    elif run_profile(ctx.manifest) == STATIC:
        wanted.update(import_materials=False, import_textures=False,
                      import_note="static-candidate: mesh imported with import_materials=false, "
                                  "import_textures=false; BC/N/ORM are the adopted candidate PNGs")
    cfg = ctx.manifest["config"].get("ue")
    if cfg is None:
        wanted["folder"] = wanted["folder"] or default_ue_folder(ctx.manifest)
        if not (wanted["folder"] + "/").startswith(UE_ALLOWED_ROOT) or ".." in wanted["folder"]:
            raise PipelineError("UE folder must be inside %s (never /Game/ART004 or /Game/ArtPreview): %s"
                                % (UE_ALLOWED_ROOT, wanted["folder"]), EXIT_USAGE)
        ctx.manifest["config"]["ue"] = wanted
        ctx.save()
        ctx.journal("ue_configured", ue=wanted)
    else:
        explicit = {k: v for k, v in wanted.items() if v is not None and k in ("folder", "asset_name")}
        if any(cfg.get(k) != v for k, v in explicit.items()):
            raise PipelineError("UE target already configured as %s; use a new run dir for another target"
                                % {k: cfg.get(k) for k in ("folder", "asset_name")}, EXIT_CONFLICT)
    print_outcome({UE_STAGE: execute_stage(ctx, UE_STAGE, force=args.force)})
    return EXIT_OK


def cmd_run(ctx: Context, args) -> int:
    ctx.load()
    stuck = interrupted_stages(ctx.manifest)
    if stuck:
        raise PipelineError("interrupted stage(s) %s from a previous process; use resume" % stuck, EXIT_NEEDS_RESUME)
    ctx.journal("run_started", force=args.force or [], backend=ctx.backend)
    outcome = run_stages(ctx, active_stages(ctx), force=set(args.force or []))
    ctx.journal("run_finished", outcome=outcome)
    print_outcome(outcome)
    return EXIT_OK


def cmd_resume(ctx: Context, args) -> int:
    ctx.load()
    m = ctx.manifest
    unfinished = [n for n in active_stages(ctx) if (m["stages"].get(n) or {}).get("status") != "completed"]
    for name in interrupted_stages(m):
        rec = m["stages"][name]
        rec.setdefault("interruptions", []).append({"started_at": rec.get("started_at"), "detected_at": now_iso()})
        rec["status"] = "interrupted"
        rec.pop("pending_fingerprint", None)
    shutil.rmtree(ctx.staging_root, ignore_errors=True)
    ctx.save()
    resume_from = unfinished[0] if unfinished else None
    ctx.journal("resume_started", resume_from=resume_from, unfinished=unfinished, backend=ctx.backend)
    print("resume: first unfinished stage = %s" % resume_from)
    outcome = run_stages(ctx, active_stages(ctx))
    ctx.journal("resume_finished", outcome=outcome)
    print_outcome(outcome)
    return EXIT_OK


def cmd_status(ctx: Context, args) -> int:
    m = ctx.load()
    print("run %s  asset %s  created by tool %s  (this tool %s, backend %s)"
          % (m["run_id"], m["asset_id"], m["tool"]["version"], TOOL_VERSION, ctx.backend))
    for sid, src in sorted(m["sources"].items()):
        s = src["spec"]
        print("source %s  task %s  %s  credits(historical) %s" % (sid, s["task_id"], s["service"],
                                                                  src["historical_credits_observed"]))
    print("profile %s%s" % (run_profile(m), "  build profile %s" % m["config"]["build_profile"]
                                 if m["config"].get("build_profile") else ""))
    for name in stage_order(m):
        rec = m["stages"].get(name) or {}
        if name == UE_STAGE and not m["config"].get("ue"):
            continue
        print("stage %-9s %-11s attempts=%s%s" % (name, rec.get("status", "pending"), rec.get("attempts", 0),
                                                 "  by %s/%s" % (rec["tool_version"], rec.get("backend")) if rec.get("tool_version") else ""))
    for e in m.get("exports", []):
        print("export %s %s%s" % (e["path"], e["sha256"][:12], " (superseded)" if e.get("superseded_by") else ""))
    print("network: tripo_calls=%s paid_tasks_created=%s" % (m["network"]["tripo_calls"], m["network"]["paid_tasks_created"]))
    return EXIT_OK


SNAPSHOT_EXCLUDE = {"journal.jsonl", "run.lock"}


def snapshot(run_dir: Path) -> dict:
    files = {}
    for path in sorted(run_dir.rglob("*")):
        rel = rel_posix(path, run_dir)
        if not path.is_file() or rel in SNAPSHOT_EXCLUDE or rel.startswith(".staging/"):
            continue
        st = path.stat()
        files[rel] = {"sha256": sha256_file(path), "bytes": st.st_size, "mtime_ns": st.st_mtime_ns}
    return files


def cmd_snapshot(ctx: Context, args) -> int:
    data = {"run_dir": str(ctx.run_dir), "taken_at": now_iso(), "files": snapshot(ctx.run_dir)}
    text = dump_json(data)
    if args.out:
        out = Path(args.out).resolve()
        if is_within(out, ctx.run_dir):
            raise PipelineError("snapshot --out must be outside the run dir", EXIT_USAGE)
        atomic_write_text(out, text)
        print("snapshot: %d files -> %s" % (len(data["files"]), out))
    else:
        sys.stdout.write(text)
    return EXIT_OK


def cmd_prepare_generation(ctx: Context, args) -> int:
    if not args.dry_run:
        raise PipelineError("submission is not implemented: this scaffold never calls Tripo. "
                            "Re-run with --dry-run to prepare an input package only.", EXIT_USAGE)
    ctx.load()
    if args.service not in SERVICES:
        raise PipelineError("--service must be one of %s" % sorted(SERVICES), EXIT_USAGE)
    if args.mode == "batch":
        raise PipelineError("batch = several independent tasks; prepare one request per task", EXIT_USAGE)
    views = {}
    for item in args.view or []:
        if "=" not in item:
            raise PipelineError("--view expects name=path", EXIT_USAGE)
        view, rel = item.split("=", 1)
        if view in views:
            raise PipelineError("duplicate view %s" % view, EXIT_USAGE)
        views[view] = rel
    if args.mode == "multi-view" and len(views) < 2:
        raise PipelineError("multi-view needs >=2 views of the same object", EXIT_USAGE)
    if args.mode != "multi-view" and len(views) > 1:
        raise PipelineError("only one view for mode %s" % args.mode, EXIT_USAGE)
    reason = (args.duplicate_reason or "").strip()
    if args.allow_duplicate and not reason:
        raise PipelineError("--allow-duplicate needs --duplicate-reason \"...\" (why a second paid task with the "
                            "same inputs is wanted); it is recorded in the package and the journal", EXIT_USAGE)
    if reason and not args.allow_duplicate:
        raise PipelineError("--duplicate-reason is only used together with --allow-duplicate", EXIT_USAGE)
    inputs, problems = {}, []
    for view, rel in sorted(views.items()):
        path = ctx.repo_path(rel)
        if not path.is_file():
            raise PipelineError("input missing: %s" % rel)
        info = inspect_file(path)
        size = path.stat().st_size
        if info.get("format") not in ("png", "jpeg"):
            problems.append("%s: unsupported format %s" % (view, info.get("format")))
        if size > MAX_TRIPO_IMAGE_BYTES:
            problems.append("%s: %d bytes > %d" % (view, size, MAX_TRIPO_IMAGE_BYTES))
        inputs[view] = {"path": Path(rel).as_posix(), "sha256": sha256_file(path), "bytes": size,
                        "pixels": info.get("pixels")}
    core = {"service": args.service, "mode": args.mode, "model_label": args.model_label,
            "views": {v: i["sha256"] for v, i in inputs.items()}}
    key = sha256_json(core)
    # A duplicate is the same input hashes + mode + service. The model label is free UI text
    # ("H3.1" vs "H3.1 - Макс.кач. ..."), so it never decides; it is only reported.
    duplicates = []
    for sid, src in sorted(ctx.manifest["sources"].items()):
        gen = src["spec"].get("generation") or {}
        registered = {v: (i or {}).get("sha256") for v, i in (gen.get("views") or {}).items() if i}
        if registered == core["views"] and gen.get("mode") == args.mode and src["spec"]["service"] == args.service:
            same_model = src["spec"].get("model_version", {}).get("ui_label") == args.model_label
            duplicates.append({"source_id": sid, "task_id": src["spec"]["task_id"], "same_model_label": same_model,
                               "registered_model_label": src["spec"].get("model_version", {}).get("ui_label")})
    if duplicates and not args.allow_duplicate:
        ctx.journal("generation_request_refused_duplicate", key=key, duplicate_of=duplicates)
        raise PipelineError("the same inputs (SHA-256), mode and service were already generated as %s (model label "
                            "is not compared); a new paid task would duplicate it. Only --allow-duplicate "
                            "--duplicate-reason \"...\" bypasses this" % [d["task_id"] for d in duplicates],
                            EXIT_CONFLICT)
    request = {
        "schema": REQUEST_SCHEMA, "request_key": key, "asset_id": ctx.manifest["asset_id"],
        "dry_run": True, "submitted": False, "network_calls": 0, "paid_tasks_created": 0,
        "service": args.service, "mode": args.mode, "model_label": args.model_label, "inputs": inputs,
        "input_problems": problems, "same_inputs_as_registered": duplicates,
        "duplicate_allowed": {"reason": reason, "duplicate_of": [d["task_id"] for d in duplicates]}
        if duplicates else None,
        "cost": {"unit": SERVICES[args.service], "quoted": None,
                 "note": "price is read from the Studio form / API pricing at submission time, not estimated here"},
        "note": "automatic checks only; geometric consistency of views needs a separate manual review",
    }
    rel = "generation-requests/%s.json" % key[:16]
    path = ctx.run_path(rel)
    text = dump_json(request)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        ctx.journal("generation_request_noop", key=key)
        print("prepare-generation: identical dry-run package already exists: %s" % rel)
        return EXIT_OK
    atomic_write_text(path, text)
    reqs = ctx.manifest.setdefault("generation_requests", [])
    if not any(r["request_key"] == key for r in reqs):
        reqs.append({"request_key": key, "path": rel, "sha256": sha256_file(path), "dry_run": True, "submitted": False})
    ctx.save()
    ctx.journal("generation_request_prepared", key=key, path=rel, problems=problems,
                duplicate_allowed=request["duplicate_allowed"])
    print("prepare-generation: dry-run package %s (problems: %d; nothing submitted)" % (rel, len(problems)))
    return EXIT_OK if not problems else EXIT_FAILED


# --------------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tripo_pipeline", description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo-root", default=str(TOOL_DIR.parents[1]))
    parser.add_argument("--blender", default=None, help="Blender executable (default: Blender 5.2 path)")
    parser.add_argument("--backend", choices=BACKENDS, default=None,
                        help="headless: blender -b per stage (default); mcp: live Blender/UE via MCP clients")
    parser.add_argument("--blender-mcp-client", default=None, help="path to blender_mcp.py")
    parser.add_argument("--unreal-mcp-client", default=None, help="path to unreal_mcp.py")
    sub = parser.add_subparsers(dest="command", required=True)

    def with_run(p):
        p.add_argument("--run-dir", required=True)
        return p

    p = with_run(sub.add_parser("init"))
    p.add_argument("--asset-id", required=True)
    p.add_argument("--primary-source", required=True)
    p.add_argument("--primary-role", required=True)
    p.add_argument("--export-basename")
    p.add_argument("--run-id")
    p.add_argument("--triangle-loss-tolerance", type=float, default=DEFAULT_TRIANGLE_LOSS_TOLERANCE)
    p.add_argument("--profile", choices=PROFILES, default=PASSTHROUGH,
                   help="passthrough (T3 static FBX), skeletal-candidate (atlas + build from --build-profile), "
                        "static-candidate (adopt a static prop candidate FBX + BC/N/ORM named by --build-profile) or "
                        "skeletal-adopt (adopt an H2 bake: SK + base FBX + 2K BC/N/ORM/TeamMask, --build-profile)")
    p.add_argument("--build-profile", help="repo-relative build profile JSON (skeletal-candidate, static-candidate, "
                                            "skeletal-adopt)")
    p = with_run(sub.add_parser("register-source"))
    p.add_argument("--spec", required=True)
    for name in [s for s in KNOWN_STAGES if s != UE_STAGE]:
        p = with_run(sub.add_parser(name))
        p.add_argument("--force", action="store_true", help="re-execute even if up to date (output dedupe still applies)")
        p.add_argument("--interrupt-at", choices=KNOWN_STAGES, help=argparse.SUPPRESS)
    p = with_run(sub.add_parser(UE_STAGE))
    p.add_argument("--ue-folder", help="content folder under %s (default: %s<Asset>/<run_id>)"
                   % (UE_ALLOWED_ROOT, UE_ALLOWED_ROOT))
    p.add_argument("--asset-name", default=None)
    p.add_argument("--no-materials", action="store_true")
    p.add_argument("--dimension-tolerance", type=float, default=DEFAULT_UE_DIMENSION_TOLERANCE)
    p.add_argument("--force", action="store_true")
    p.add_argument("--interrupt-at", choices=KNOWN_STAGES, help=argparse.SUPPRESS)
    p = with_run(sub.add_parser("run"))
    p.add_argument("--force", action="append", choices=KNOWN_STAGES)
    p.add_argument("--interrupt-at", choices=KNOWN_STAGES,
                   help="diagnostic: exit 75 after this stage's work, before committing it")
    p = with_run(sub.add_parser("resume"))
    p.add_argument("--interrupt-at", choices=KNOWN_STAGES, help=argparse.SUPPRESS)
    with_run(sub.add_parser("status"))
    p = with_run(sub.add_parser("snapshot"))
    p.add_argument("--out")
    p = with_run(sub.add_parser("prepare-generation"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--service", required=True)
    p.add_argument("--mode", required=True)
    p.add_argument("--model-label", required=True)
    p.add_argument("--view", action="append", help="name=repo-relative path; repeat per view")
    p.add_argument("--allow-duplicate", action="store_true",
                   help="prepare a package even though the same inputs/mode/service were generated (needs a reason)")
    p.add_argument("--duplicate-reason", default=None, help="why a duplicate paid task is wanted (recorded)")
    return parser


COMMANDS = {
    "init": cmd_init, "register-source": cmd_register, "preflight": cmd_stage, "import": cmd_stage,
    "verify": cmd_stage, "export": cmd_stage, "atlas": cmd_stage, "build": cmd_stage, "adopt": cmd_stage,
    UE_STAGE: cmd_ue_import, "run": cmd_run, "resume": cmd_resume, "status": cmd_status,
    "snapshot": cmd_snapshot, "prepare-generation": cmd_prepare_generation,
}
READ_ONLY = {"status", "snapshot"}


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ctx = Context(Path(args.run_dir), Path(args.repo_root), args.blender, getattr(args, "interrupt_at", None),
                      backend=args.backend, blender_mcp_client=args.blender_mcp_client,
                      unreal_mcp_client=args.unreal_mcp_client)
    except PipelineError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code
    try:
        if args.command not in READ_ONLY:
            ctx.acquire_lock(args.command)
        try:
            return COMMANDS[args.command](ctx, args)
        finally:
            ctx.release_lock()
    except PipelineError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
