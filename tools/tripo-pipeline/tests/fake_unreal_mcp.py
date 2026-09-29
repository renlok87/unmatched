"""Test double for C:/Users/ren/.claude/mcp-servers/clients/unreal_mcp.py (live UnrealEditor).

Usage like the real client:  fake_unreal_mcp.py call <toolset> <tool> '<json args>'
State (the "editor content browser") lives in the JSON file named by FAKE_UE_STATE.

Import onto an existing asset name behaves like the real UE 5.8 MCP import_file
(measured 2026-09-28): the call fails with "import_asset: <name> at <folder> already
exists". FAKE_UE_ON_EXISTING=number switches to the "<name>_1" behaviour of other
importers, which the pipeline must survive as well.

Supports the passthrough (T3) calls, the skeletal-candidate (T4) calls and the static-candidate
(T2.1 stage 3) calls (mesh data from reports/fbx-readback.json next to the candidate FBX):
TextureTools, MaterialTools, MaterialInstanceTools, ObjectTools get/set_properties,
SkeletalMeshTools (bones, sockets, slots, bounds), StaticMeshTools, LogsToolset.
Mesh data comes from the run's reports next to the imported FBX
(reports/export-report.json for passthrough, reports/build-report.json for candidates).

Env:
  FAKE_UE_STATE        path to the state JSON (required)
  FAKE_UE_LOG          append one line per tool call (short tool name)
  FAKE_UE_QUALIFIED    "1": only fully qualified tool names are accepted
  FAKE_UE_TRIS_DELTA   integer added to static triangle counts (to fail a contract)
  FAKE_UE_FAIL_TOOL    tool (short name) that returns isError
  FAKE_UE_ON_EXISTING  "refuse" (default, real UE 5.8 MCP) or "number"
  FAKE_UE_ARMATURE_NODE  name of the extra bone 0 (default SKEL_Test)
  FAKE_UE_RETURN_SIDE_PRODUCTS  "1": import_file also returns the materials it created (default: only the
                       mesh and its skeleton, like the real UE 5.8 MCP, measured 2026-09-28)
  FAKE_UE_IMPORT_CONVEX  simple collision elements a static import creates (default 1, like Interchange)
  FAKE_UE_SK_TRIS_DELTA  integer added to the skeletal LOD triangles of the editor-Python measurement (0.7.0)
"""

import json
import re
import math
import os
import struct
import sys
from pathlib import Path


def load():
    path = Path(os.environ["FAKE_UE_STATE"])
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    state.setdefault("assets", {})
    state.setdefault("props", {})
    state.setdefault("log", [])
    return state


def save(state):
    Path(os.environ["FAKE_UE_STATE"]).write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")


CONSOLE_SNAPSHOT = ('window "Unmatched" [pos=0,0 size=100,100] [ref=w1]\n  text "Cmd" [pos=1,90 size=20,10] [ref=x1]\n'
                    '  textbox [pos=22,90 size=60,10] [ref=t7]\n')


NORMAL_METHODS = {"FBXNIM_COMPUTE_NORMALS": "FBXNIM_ComputeNormals", "FBXNIM_IMPORT_NORMALS": "FBXNIM_ImportNormals",
                  "FBXNIM_IMPORT_NORMALS_AND_TANGENTS": "FBXNIM_ImportNormalsAndTangents"}


def editor_python(state, text):
    """`py "<script>" <args.json>` typed into the console: only the CLI's FBX import (UE_PY_IMPORT_FBX) is emulated.
    FAKE_UE_EDITOR_PY_DROPS_VC=1: a static import keeps VertexColorImportOption at Ignore (the T3.1 defect);
    FAKE_UE_NORMAL_METHOD: normal import method the fake records instead of the requested one."""
    m = re.match(r'py "([^"]+)" (\S+)$', text)
    if not m:
        return "unsupported console command"
    script, args_path = Path(m.group(1)), Path(m.group(2))
    text = script.read_text(encoding="utf-8")
    if "tripo-pipeline editor-Python launcher" in text:
        # McpUnreal.editor_python types a launcher: it writes the started marker, then runs the target script
        Path(re.search(r'with open\(r"([^"]+)"', text).group(1)).write_text("started\n", encoding="utf-8")
        script = Path(re.search(r'runpy.run_path\(r"([^"]+)"', text).group(1))
    a = json.loads(args_path.read_text(encoding="utf-8"))
    if "skeletal mesh measurement" in script.read_text(encoding="utf-8"):
        # UE_PY_MEASURE_SKELETAL (0.7.0): LOD triangles through GeometryScript; FAKE_UE_SK_TRIS_DELTA shifts them
        mesh = state["assets"].get(a["mesh"].split(".")[0])
        if mesh is None or "tris" not in mesh:
            res = {"mesh": a["mesh"], "error": "RuntimeError: asset not found: %s" % a["mesh"]}
        else:
            tris = mesh["tris"] + int(os.environ.get("FAKE_UE_SK_TRIS_DELTA", "0"))
            res = {"mesh": a["mesh"], "triangles": [tris] * max(1, int(a.get("lods") or 1)),
                   "vertices": [tris // 2] * max(1, int(a.get("lods") or 1)), "method": "fake GeometryScript"}
        Path(a["out"]).write_text(json.dumps(res), encoding="utf-8")
        return None
    res = {"kind": a.get("kind"), "factory": "FbxFactory", "normal_import_method": a.get("normal_import_method")}
    if "FBX import with an explicit legacy FbxFactory" not in script.read_text(encoding="utf-8"):
        res["error"] = "fake editor: unknown script %s" % script.name
    else:
        skeletal = a["kind"] == "skeletal"
        vcio = "Replace" if a.get("vertex_colors") == "replace" else "Ignore"
        if not skeletal and os.environ.get("FAKE_UE_EDITOR_PY_DROPS_VC") == "1":
            vcio = "Ignore"
        toolset = ("editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools" if skeletal
                   else "editor_toolset.toolsets.static_mesh.StaticMeshTools")
        target_skel = pkg(a["skeleton"]) if skeletal and a.get("skeleton") else None
        if target_skel and (state["assets"].get(target_skel) or {}).get("class") != "Skeleton":
            created, error = None, "target skeleton not found: %s" % a["skeleton"]
        else:
            created, error = mesh_import(state, toolset, a, vcio=vcio, target_skeleton=target_skel)
        if error:
            res["error"] = "RuntimeError: %s" % error
        else:
            method = os.environ.get("FAKE_UE_NORMAL_METHOD") or a.get("normal_import_method")
            state["assets"][created[0]]["normal_import_method"] = NORMAL_METHODS.get(method, method)
            state["assets"][created[0]]["import_data_class"] = ("FbxSkeletalMeshImportData" if skeletal
                                                                else "FbxStaticMeshImportData")
            res["imported"] = [obj(p)["refPath"] for p in created]
            if skeletal:
                # 0.8.0: the editor reads the mesh's skeleton back; with a target skeleton nothing new is created
                res["skeleton_read_back"] = obj(state["assets"][created[0]].get("skeleton") or "")["refPath"]
            res["asset_import_data_class"] = state["assets"][created[0]]["import_data_class"]
            res["normal_import_method_read_back"] = method
    Path(a["out"]).write_text(json.dumps(res), encoding="utf-8")
    return None


INPUT_ORDER = {"MaterialExpressionLinearInterpolate": ["A", "B", "Alpha"],
               "MaterialExpressionDesaturation": ["", "Fraction"],
               "MaterialExpressionFresnel": ["ExponentIn", "BaseReflectFractionIn", "Normal"],
               "MaterialExpressionEyeAdaptationInverse": ["LightValueInput", "AlphaInput"]}
OUTPUT0 = {"MaterialExpressionVectorParameter": "RGB", "MaterialExpressionTextureSampleParameter2D": "RGB",
           "MaterialExpressionEyeAdaptationInverse": "EyeAdaptationInverse"}


def pkg(ref):
    if isinstance(ref, dict):
        ref = ref.get("refPath", "")
    return str(ref).split(":")[0].split(".")[0]


def obj(p):
    return {"refPath": "%s.%s" % (p, p.rsplit("/", 1)[-1])}


def reply(value=None, error=None):
    if error:
        res = {"jsonrpc": "2.0", "id": 2, "result": {"isError": True, "content": [{"type": "text", "text": error}]}}
    else:
        res = {"jsonrpc": "2.0", "id": 2,
               "result": {"content": [{"type": "text", "text": json.dumps({"returnValue": value})}]}}
    print(json.dumps(res, indent=1))
    return 1 if error else 0


def png_size(path):
    head = Path(path).read_bytes()[:24]
    return list(struct.unpack(">II", head[16:24])) if head[:8] == b"\x89PNG\r\n\x1a\n" else [0, 0]


def new_asset(state, folder, name, record):
    """Returns (final package, error)."""
    target = "%s/%s" % (folder.rstrip("/"), name)
    if target in state["assets"]:
        if os.environ.get("FAKE_UE_ON_EXISTING", "refuse") != "number":
            return None, "import_asset: %s at %s already exists" % (name, folder.rstrip("/"))
        n = 1
        while "%s_%d" % (target, n) in state["assets"]:
            n += 1
        target = "%s_%d" % (target, n)
    record.setdefault("dirty", True)
    state["assets"][target] = record
    return target, None


def ue_bounds(authored, theta):
    """Authored Blender bounds (cm) -> UE bounds: export rotation about Z, then UE (x, -y, z) (ART-001)."""
    c, s = round(math.cos(math.radians(theta)), 9), round(math.sin(math.radians(theta)), 9)
    pts = [(c * x - s * y, s * x + c * y) for x in (authored["min"][0], authored["max"][0])
           for y in (authored["min"][1], authored["max"][1])]
    xs, ys = [p[0] for p in pts], [-p[1] for p in pts]
    return [min(xs), min(ys), authored["min"][2]], [max(xs), max(ys), authored["max"][2]]


def mesh_import(state, toolset, args, vcio="Ignore", target_skeleton=None):
    fbx = Path(args["source_file"])
    run = fbx.parent.parent
    state["log"].append("LogFbx: Loading FBX Scene from %s" % fbx.as_posix())
    build_path = run / "reports/build-report.json"
    readback_path = run / "reports/fbx-readback.json"
    rig_path = run / "reports/rig-report.json"  # h2_bake_arthur bake (skeletal-adopt, format h2-bake-arthur/1)
    static = "static_mesh" in toolset
    if rig_path.exists() and not build_path.exists():
        # mesh data straight from the bake's FBX read-back (export frame, metres): UE = (x, -y, z) x 100 (ART-001);
        # deliberately NOT through skeletal_adopt_formats (the adopt views must agree with this independent mapping)
        rig = json.loads(rig_path.read_text(encoding="utf-8"))
        is_base = rig["exports"]["base_fbx"]["file"].rsplit("/", 1)[-1] == fbx.name
        meshes = rig["readback"]["base" if is_base else "skeletal"]["meshes"]
        los = [m["bounds_m_fbx_frame"]["min"] for m in meshes.values()]
        his = [m["bounds_m_fbx_frame"]["max"] for m in meshes.values()]
        lo = [min(v[0] for v in los) * 100, -max(v[1] for v in his) * 100, min(v[2] for v in los) * 100]
        hi = [max(v[0] for v in his) * 100, -min(v[1] for v in los) * 100, max(v[2] for v in his) * 100]
        slots = sorted({s for m in meshes.values() for s in m["material_slots"]})
        if is_base:
            record = {"class": "StaticMesh", "slots": slots, "source": str(fbx),
                      "tris": sum(m["triangles"] - m.get("near_degenerate_triangles", 0) for m in meshes.values())
                      + int(os.environ.get("FAKE_UE_TRIS_DELTA", "0")),
                      "bounds": {"min": dict(zip("xyz", lo)), "max": dict(zip("xyz", hi))}}
        else:
            node = os.environ.get("FAKE_UE_ARMATURE_NODE", "SKEL_Test")
            bones = rig["readback"]["skeletal"]["bones"]
            parents = {node: ""}
            for name, info in bones.items():
                parents[name.replace(".", "_")] = (info["parent"] or node).replace(".", "_")
            record = {"class": "SkeletalMesh", "source": str(fbx), "slots": slots,
                      "tris": sum(m["triangles"] for m in meshes.values()),
                      "bones": [node] + [n.replace(".", "_") for n in bones], "parents": parents, "sockets": [],
                      "bounds": {"origin": {k: (lo[i] + hi[i]) / 2 for i, k in enumerate("xyz")},
                                 "boxExtent": {k: (hi[i] - lo[i]) / 2 for i, k in enumerate("xyz")}}}
    elif static and readback_path.exists():
        rb = json.loads(readback_path.read_text(encoding="utf-8"))
        lo, hi = rb["bounds_min_uu"], rb["bounds_max_uu"]
        record = {"class": "StaticMesh", "slots": list(rb["material_slots"]), "source": str(fbx),
                  "tris": rb["triangles"] + int(os.environ.get("FAKE_UE_TRIS_DELTA", "0")),
                  "convex": int(os.environ.get("FAKE_UE_IMPORT_CONVEX", "1")),
                  # export frame shown by UE as (x, -y, z) (ART-001)
                  "bounds": {"min": {"x": lo[0], "y": -hi[1], "z": lo[2]}, "max": {"x": hi[0], "y": -lo[1], "z": hi[2]}}}
    elif build_path.exists() and "skeletal_fbx" in (json.loads(build_path.read_text(encoding="utf-8"))
                                                  .get("exports") or {}):
        # H2 bake report (skeletal-adopt, format h2-bake-rig/1): round-trip bounds in the authored frame (metres)
        build = json.loads(build_path.read_text(encoding="utf-8"))
        rot = float(build["exports"]["settings"].get("export_space_rotation_z_degrees", 0))
        base = fbx.name == Path(build["exports"]["base_fbx"]["path"]).name
        meshes = build["roundtrip"]["base" if base else "skeletal"]["meshes"]
        authored = {"min": [min(m["bounds_m"]["min"][i] for m in meshes.values()) * 100.0 for i in range(3)],
                    "max": [max(m["bounds_m"]["max"][i] for m in meshes.values()) * 100.0 for i in range(3)]}
        lo, hi = ue_bounds(authored, rot)
        slots = sorted({s for m in meshes.values() for s in m["material_slots"]})
        tris = sum(m["triangles"] - (m.get("near_degenerate_triangles") or 0 if base else 0) for m in meshes.values())
        if base:
            record = {"class": "StaticMesh", "slots": slots, "source": str(fbx),
                      "tris": tris + int(os.environ.get("FAKE_UE_TRIS_DELTA", "0")),
                      "bounds": {"min": dict(zip("xyz", lo)), "max": dict(zip("xyz", hi))}}
        else:
            node = os.environ.get("FAKE_UE_ARMATURE_NODE", "SKEL_Test")
            bones = build["roundtrip"]["skeletal"]["bones"]
            parents = {node: ""}
            for name, info in bones.items():
                parents[name.replace(".", "_")] = (info["parent"] or node).replace(".", "_")
            record = {"class": "SkeletalMesh", "source": str(fbx), "slots": slots, "tris": tris,
                      "bones": [node] + [n.replace(".", "_") for n in bones], "parents": parents, "sockets": [],
                      "bounds": {"origin": {k: (lo[i] + hi[i]) / 2 for i, k in enumerate("xyz")},
                                 "boxExtent": {k: (hi[i] - lo[i]) / 2 for i, k in enumerate("xyz")}}}
    elif build_path.exists():
        build = json.loads(build_path.read_text(encoding="utf-8"))
        kind = next(k for k, e in build["exports"].items() if isinstance(e, dict) and e.get("file") == fbx.name)
        if kind == "base":
            base = next(v for k, v in build["meshes_pre_export_m"].items() if k.startswith("SM_"))
            exp = build["expected_ue_bounds_uu_at_import_scale_1"]
            lo, hi = ue_bounds(exp["base_blender_axes"], float(exp.get("export_rotation_z_degrees", 0)))
            b = {"min": lo, "max": hi}
            record = {"class": "StaticMesh", "slots": ["M_Atlas"], "source": str(fbx),
                      "tris": base["triangles"] - base["near_degenerate_triangles"]
                      + int(os.environ.get("FAKE_UE_TRIS_DELTA", "0")),
                      "bounds": {"min": dict(zip("xyz", b["min"])), "max": dict(zip("xyz", b["max"]))}}
        else:
            exp = build["expected_ue_bounds_uu_at_import_scale_1"]
            lo, hi = ue_bounds(exp["skeletal_blender_axes"], float(exp.get("export_rotation_z_degrees", 0)))
            node = os.environ.get("FAKE_UE_ARMATURE_NODE", "SKEL_Test")
            bones = build["roundtrip"]["skeletal"]["bones"]
            parents = {node: ""}
            for name, info in bones.items():
                parents[name.replace(".", "_")] = (info["parent"] or node).replace(".", "_")
            record = {"class": "SkeletalMesh", "source": str(fbx),
                      "slots": build["checks"]["roundtrip_material_slots"]["measured"]["skeletal_unique"],
                      "bones": [node] + [n.replace(".", "_") for n in bones], "parents": parents, "sockets": [],
                      "bounds": {"origin": {k: (lo[i] + hi[i]) / 2 for i, k in enumerate("xyz")},
                                 "boxExtent": {k: (hi[i] - lo[i]) / 2 for i, k in enumerate("xyz")}}}
    else:
        report = json.loads((run / "reports/export-report.json").read_text(encoding="utf-8"))
        rt = report["roundtrip_reimport"]
        x, y, z = report["expected_ue_dimensions_uu_at_import_scale_1"]
        record = {"class": "StaticMesh" if static else "SkeletalMesh",
                  "tris": rt["triangles_total"] + int(os.environ.get("FAKE_UE_TRIS_DELTA", "0")),
                  "slots": ["M_%d" % i for i in range(rt["material_count"])], "source": str(fbx),
                  # the export report already gives the size per UE axis (UM_FBX_v1 export frame)
                  "bounds": {"min": {"x": -x / 2, "y": -y / 2, "z": 0}, "max": {"x": x / 2, "y": y / 2, "z": z}}}
    # MCP import_file uses the project's FbxImportUI defaults: static ImportNormals, skeletal ComputeNormals
    # (BaseEditorPerProjectUserSettings.ini; engine gate memo, importer topic); the CLI editor-Python import overrides
    record["normal_import_method"] = ("FBXNIM_ImportNormals" if record["class"] == "StaticMesh"
                                      else "FBXNIM_ComputeNormals")
    if record["class"] == "StaticMesh":
        # MCP StaticMeshTools.import_file leaves VertexColorImportOption at Ignore (measured live 2026-09-28, T3.1);
        # the editor-Python import of the CLI (UE_PY_IMPORT_FBX) asks for Replace on a vertex-mask base
        record["vcio"] = vcio
    final, error = new_asset(state, args["folder_path"], args["asset_name"], record)
    if error:
        return None, error
    created = [final]
    if record["class"] == "SkeletalMesh" and "bones" in record and target_skeleton:
        record["skeleton"] = target_skeleton  # onto the existing (canonical) skeleton: no <asset>_Skeleton
    elif record["class"] == "SkeletalMesh" and "bones" in record:
        skel, error = new_asset(state, args["folder_path"], args["asset_name"] + "_Skeleton", {"class": "Skeleton"})
        if error:
            return None, error
        record["skeleton"] = skel
        created.append(skel)
    if args.get("import_materials"):
        for slot in record["slots"]:
            mat, error = new_asset(state, args["folder_path"], slot, {"class": "Material"})
            if error:
                return None, error
            created.append(mat)
    return created, None


def main(argv):
    if argv[0] != "call":
        return 2
    toolset, tool, args = argv[1], argv[2], json.loads(argv[3]) if len(argv) > 3 else {}
    if os.environ.get("FAKE_UE_LOG"):
        with open(os.environ["FAKE_UE_LOG"], "a", encoding="utf-8") as handle:
            handle.write(tool.rsplit(".", 1)[-1] + "\n")
    qualified = tool.startswith(toolset + ".")
    if os.environ.get("FAKE_UE_QUALIFIED") == "1" and not qualified:
        return reply(error="Tool '%s' not found in toolset '%s'" % (tool, toolset))
    short = tool.rsplit(".", 1)[-1]
    if os.environ.get("FAKE_UE_FAIL_TOOL") == short:
        return reply(error="simulated failure of %s" % short)
    state = load()
    assets, props = state["assets"], state["props"]

    def done(value=None):
        save(state)
        return reply(value)

    # ---- AssetTools
    if short == "find_assets":
        folder = args["folder_path"].rstrip("/") + "/"
        return reply(sorted(p for p in assets if p.startswith(folder)))
    if short == "exists":
        return reply(pkg(args["path"]) in assets)
    if short == "delete":
        ok = assets.pop(pkg(args["path"]), None) is not None
        return done(ok)
    if short == "get_asset_class":
        if pkg(args["asset_path"]) not in assets:
            return reply(error="asset not found: %s" % args["asset_path"])
        return reply(assets[pkg(args["asset_path"])]["class"])
    if short == "save_assets":
        ok = all(pkg(a) in assets for a in args["asset_paths"])
        for a in args["asset_paths"]:
            if pkg(a) in assets:
                assets[pkg(a)]["dirty"] = False
        return done(ok)
    if short == "is_dirty":
        return reply(bool(assets.get(pkg(args["asset_path"]), {}).get("dirty")))
    # ---- SlateInspectorToolset (editor console)
    if short == "Snapshot":
        return reply(CONSOLE_SNAPSHOT)
    if short == "Type":
        if os.environ.get("FAKE_UE_TYPE_LOSES_FIRST") == "1" and not state.get("type_lost"):
            # like SlateInspector without keyboard focus: the command is silently dropped once
            state["type_lost"] = True
            return done(True)
        state["log"].append("Cmd: " + args["text"])
        error = editor_python(state, args["text"])
        if error:
            return reply(error=error)
        return done(True)
    # ---- LogsToolset
    if short == "GetLogEntries":
        return reply(list(state["log"]))
    # ---- imports
    if short == "import_file" and "texture" in toolset:
        name = args["asset_name"]
        normal = name.endswith("_N")
        record = {"class": "Texture2D", "size": png_size(args["source_file"])}
        final, error = new_asset(state, args["folder_path"], name, record)
        if error:
            return reply(error=error)
        props[final] = {"SRGB": not normal, "CompressionSettings": "TC_Normalmap" if normal else "TC_Default",
                        "bFlipGreenChannel": False}
        return done([obj(final)])
    if short == "import_file":
        created, error = mesh_import(state, toolset, args)
        if error:
            return reply(error=error)
        if os.environ.get("FAKE_UE_RETURN_SIDE_PRODUCTS") != "1":
            created = [p for p in created if assets[p]["class"] != "Material"]
        return done([obj(p) for p in created])
    if short == "get_size":
        x, y = assets[pkg(args["texture"])]["size"]
        return reply({"x": x, "y": y})
    # ---- ObjectTools
    if short == "set_properties":
        key = args["instance"]["refPath"]
        key = pkg(key) if ":" not in key else key
        props.setdefault(key, {}).update(json.loads(args["values"]))
        if pkg(key) in assets:
            assets[pkg(key)]["dirty"] = True
        return done(True)
    if short == "get_properties":
        key = args["instance"]["refPath"]
        if key.endswith(":BodySetup_0"):
            mesh = assets[pkg(key)]
            agg = {"sphereElems": [], "boxElems": [], "sphylElems": [], "convexElems": [{}] * mesh.get("convex", 0)}
            return reply(json.dumps({"AggGeom": agg, "CollisionTraceFlag": "CTF_UseDefault"}))
        if key.endswith("ImportData_0"):
            rec = assets[pkg(key)]
            vals = {"VertexColorImportOption": rec.get("vcio"), "NormalImportMethod": rec.get("normal_import_method")}
            return reply(json.dumps({p: vals.get(p) for p in args["properties"]}))
        key = pkg(key) if ":" not in key else key
        values = dict(props.get(key, {}))
        if "BodySetup" in args["properties"] and assets.get(key, {}).get("class") == "StaticMesh":
            values["BodySetup"] = {"refPath": obj(key)["refPath"] + ":BodySetup_0"}
        if "AssetImportData" in args["properties"] and assets.get(key, {}).get("class") in ("StaticMesh", "SkeletalMesh"):
            cls = assets[key].get("import_data_class") or ("Fbx%sImportData" % assets[key]["class"])
            values["AssetImportData"] = {"refPath": obj(key)["refPath"] + ":%s_0" % cls}
        if "NaniteSettings" in args["properties"] and assets.get(key, {}).get("class") == "SkeletalMesh":
            values["NaniteSettings"] = {"bEnabled": False}
        return reply(json.dumps({p: values.get(p) for p in args["properties"]}))
    # ---- MaterialTools / MaterialInstanceTools
    if short == "create_material":
        final, error = new_asset(state, args["folder_path"], args["asset_name"], {"class": "Material", "outputs": {},
                                                                                   "expressions": 0})
        if error:
            return reply(error=error)
        props[final] = {"bUsedWithSkeletalMesh": False, "TwoSided": False, "BlendMode": "BLEND_Opaque",
                        "ShadingModel": "MSM_DefaultLit"}
        return done(obj(final))
    if short == "add_expression":
        mat = pkg(args["material_or_function"])
        n = assets[mat]["expressions"]
        assets[mat]["expressions"] = n + 1
        cls = args["expression_class"]["refPath"].rsplit(".", 1)[-1]
        ref = "%s:%s_%d" % (obj(mat)["refPath"], cls, n)
        assets[mat].setdefault("graph", []).append(ref)
        props[ref] = {"MaterialExpressionEditorX": args["x"], "MaterialExpressionEditorY": args["y"]}
        return done({"refPath": ref})
    if short == "delete_expression":
        mat = pkg(args["material_or_function"])
        ref = args["expression"]["refPath"]
        assets[mat]["graph"] = [e for e in assets[mat].get("graph", []) if e != ref]
        assets[mat]["links"] = {d: {i: v for i, v in ins.items() if v[0] != ref}
                                for d, ins in assets[mat].get("links", {}).items() if d != ref}
        assets[mat]["outputs"] = {k: v for k, v in assets[mat]["outputs"].items() if v[0] != ref}
        props.pop(ref, None)
        return done(None)
    if short == "get_expressions":
        return reply([{"refPath": e} for e in assets[pkg(args["material_or_function"])].get("graph", [])])
    if short == "connect_expressions":
        dst = args["to_expression"]["refPath"]
        mat = pkg(dst)
        assets[mat].setdefault("links", {}).setdefault(dst, {})[args["to_input_name"]] = [
            args["from_expression"]["refPath"], args["from_output_name"]]
        return done(None)
    if short == "get_expression_inputs":
        dst = args["expression"]["refPath"]
        ins = assets[pkg(dst)].get("links", {}).get(dst, {})
        cls = dst.rsplit(":", 1)[-1].rsplit("_", 1)[0]
        order = INPUT_ORDER.get(cls, ["A", "B", "", "Alpha", "Fraction"])
        first, out = {}, []
        for name in sorted(ins, key=lambda k: order.index(k) if k in order else 99):
            src, o = ins[name]
            # MaterialEditingLibrary.get_input_node_output_name_for_material_expression reports the output of the
            # first input wired from the same source (live UE 5.8, 2026-09-29)
            first.setdefault(src, o or OUTPUT0.get(src.rsplit(":", 1)[-1].rsplit("_", 1)[0], ""))
            out.append({"input_name": name or "None", "expression": {"refPath": src}, "output_name": first[src]})
        return reply(out)
    if short == "recompile":
        return done(None)
    if short == "connect_to_output":
        mat = pkg(args["expression"])
        assets[mat]["outputs"][args["material_property"]] = [args["expression"]["refPath"], args["output_name"]]
        return done(None)
    if short == "get_property_input":
        out = assets[pkg(args["material"])]["outputs"].get(args["material_property"])
        return reply({"output_name": out[1] if out else "", "input_name": "",
                      "expression": {"refPath": out[0]} if out else None})
    if short == "create" and "material_instance" in toolset:
        final, error = new_asset(state, args["folder_path"], args["asset_name"],
                                 {"class": "MaterialInstanceConstant", "vectors": {}})
        if error:
            return reply(error=error)
        props[final] = {"Parent": args["parent"]}
        return done(obj(final))
    if short == "set_vector_parameter":
        assets[pkg(args["instance"])]["vectors"][args["name"]] = args["value"]
        return done(None)
    if short == "get_vector_parameter":
        return reply(assets[pkg(args["instance"])]["vectors"].get(args["name"]))
    if short == "set_texture_parameter":
        assets[pkg(args["instance"])].setdefault("textures", {})[args["name"]] = args["value"]["refPath"]
        return done(None)
    if short == "get_texture_parameter":
        value = assets[pkg(args["instance"])].get("textures", {}).get(args["name"])
        return reply({"refPath": value} if value else None)
    if short == "list_parameters":
        target = assets[pkg(args["material"])]
        if "parameters" in target:
            return reply(target["parameters"])
        kinds = {"MaterialExpressionScalarParameter": "Scalar", "MaterialExpressionVectorParameter": "Vector",
                 "MaterialExpressionTextureSampleParameter2D": "Texture"}
        found = []
        for e in target.get("graph", []):
            cls = e.rsplit(":", 1)[-1].rsplit("_", 1)[0]
            if cls in kinds and props.get(e, {}).get("ParameterName"):
                found.append({"type": kinds[cls], "name": props[e]["ParameterName"]})
        return reply(found)
    if short == "set_scalar_parameter":
        assets[pkg(args["instance"])].setdefault("scalars", {})[args["name"]] = args["value"]
        return done(None)
    if short == "get_scalar_parameter":
        return reply(assets[pkg(args["instance"])].get("scalars", {}).get(args["name"]))
    # ---- mesh queries
    mesh = assets.get(pkg(args.get("mesh", {}).get("refPath", "")))
    if mesh is None:
        return reply(error="Tool '%s' not found or mesh missing" % tool)
    if short == "get_material_slots":
        return reply(mesh["slots"])
    if short == "set_material":
        mesh.setdefault("materials", {})[args["slot_name"]] = pkg(args["material"])
        mesh["dirty"] = True
        return done(True)
    if short == "get_material":
        value = mesh.get("materials", {}).get(args["slot_name"])
        return reply(obj(value) if value else None)
    if short == "get_bounds":
        return reply(mesh["bounds"])
    if short == "get_triangle_count":
        return reply(mesh["tris"])
    if short == "get_vertex_count":
        return reply(mesh.get("tris", 10) * 3)
    if short in ("get_lod_count",):
        return reply(1)
    if short == "is_nanite_enabled":
        return reply(False)
    if short == "remove_collisions":
        mesh["convex"] = 0
        mesh["dirty"] = True
        return done(True)
    if short == "get_section_count":
        return reply(len(mesh["slots"]))
    if short == "get_bone_names":
        return reply(mesh["bones"])
    if short == "get_bone_parent":
        return reply(mesh["parents"].get(args["bone_name"], ""))
    if short == "get_socket_names":
        return reply([s["name"] for s in mesh["sockets"]])
    if short == "add_socket":
        if "bones" in mesh and args["bone_name"] not in mesh["bones"]:
            # live UE 5.8 (Harpy candidate 2026-09-28): 'Bone "foot.R" not found on SK_Harpy_Candidate.'
            return reply(error='Bone "%s" not found on %s.' % (args["bone_name"], pkg(args["mesh"]).rsplit("/", 1)[-1]))
        mesh["sockets"].append({"name": args["socket_name"], "bone": args["bone_name"],
                                "transform": {"location": {"x": 0, "y": 0, "z": 0},
                                              "rotation": {"pitch": 0, "yaw": 0, "roll": 0},
                                              "scale": {"x": 1, "y": 1, "z": 1}}})
        mesh["dirty"] = True
        return done({"refPath": "socket"})
    if short == "remove_socket":
        mesh["sockets"] = [s for s in mesh["sockets"] if s["name"] != args["socket_name"]]
        return done(True)
    sock = next((s for s in mesh.get("sockets", []) if s["name"] == args.get("socket_name")), None)
    if short == "set_socket_transform":
        sock["transform"] = args["transform"]
        return done(None)
    if short == "get_socket_transform":
        return reply(sock["transform"])
    if short == "get_socket_bone":
        return reply(sock["bone"])
    return reply(error="Tool '%s' not found" % tool)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
