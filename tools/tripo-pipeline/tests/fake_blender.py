"""Test double for Blender, used via TRIPO_PIPELINE_BLENDER_CMD (headless backend)
and, with ``--mcp``, as a fake blender_mcp.py client (TRIPO_PIPELINE_BLENDER_MCP_CMD).

Mimics the command line and outputs of blender/import_source.py and
blender/export_fbx.py without Blender. Like real Blender, the .blend it writes
is NOT byte-deterministic (random nonce), while the FBX is deterministic.

Env:
  FAKE_BLENDER_LOG    append one line per stage invocation ("import"/"export",
                      prefixed "mcp:" for the MCP client mode)
  FAKE_BLENDER_FAIL   stage name that should crash with a traceback
  FAKE_BLENDER_SLEEP  seconds to sleep inside a stage (for kill tests)
  FAKE_BLENDER_MCP_DOWN  "1": the MCP client behaves like a refused socket
"""

import hashlib
import io
import json
import math
import os
import re
import struct
import sys
import time
import uuid
from contextlib import redirect_stdout
from pathlib import Path


def glb_meshes(path):
    data = Path(path).read_bytes()
    length = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20 + length])
    out = []
    for mesh in doc["meshes"]:
        tris = sum(doc["accessors"][p["indices"]]["count"] // 3 for p in mesh["primitives"])
        out.append((mesh["name"], tris))
    return out, len(doc.get("materials", [])), len(doc.get("images", []))


def log_call(tag):
    if os.environ.get("FAKE_BLENDER_LOG"):
        with open(os.environ["FAKE_BLENDER_LOG"], "a", encoding="utf-8") as handle:
            handle.write(tag + "\n")


def run_stage(stage, params, isolation):
    """Returns (exit_code, stdout)."""
    if os.environ.get("FAKE_BLENDER_SLEEP"):
        time.sleep(float(os.environ["FAKE_BLENDER_SLEEP"]))
    if os.environ.get("FAKE_BLENDER_FAIL") == stage:
        return 1, "Traceback (most recent call last):\nRuntimeError: fake failure\n"
    if stage == "import":
        source = params["source"]
        digest = hashlib.sha256(Path(source).read_bytes()).hexdigest()
        meshes, materials, images = glb_meshes(source)
        Path(params["blend_out"]).write_text("source=%s\nnonce=%s\n" % (digest, uuid.uuid4().hex), encoding="utf-8")
        report = {
            "stage": "import", "blender": "9.9.9 (fake)", "source": {"file": Path(source).name, "sha256": digest},
            "mesh_count": len(meshes), "triangles_total": sum(t for _, t in meshes),
            "material_count": materials, "image_count": images, "armatures": 0, "actions": 0,
            "bounds": {"min": [0, 0, 0], "max": [1, 1, 1], "dimensions": [1, 1, 1]},
            "meshes": [{"name": n, "triangles": t, "uv_layers": ["UVMap"], "degenerate_faces": 0,
                        "diagnostic_weld_1e-7": {"vertices": 3, "boundary_edges": 0, "non_manifold_edges": 0}}
                       for n, t in meshes],
            "images": [],
        }
        Path(params["report_out"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0, "TRIPO_PIPELINE_STAGE_OK import %d isolation=%s\n" % (len(meshes), isolation)
    if stage == "build":
        return fake_build(params, isolation)
    if not params.get("fbx_preset") or not Path(params["fbx_preset"]).is_file():
        return 1, "Traceback (most recent call last):\nRuntimeError: params.fbx_preset is required\n"
    lines = Path(params["blend"]).read_text(encoding="utf-8").splitlines()
    fbx = Path(params["fbx_out"])
    fbx.write_bytes(b"FAKEFBX\0" + lines[0].encode("utf-8"))
    preset = json.loads(Path(params["fbx_preset"]).read_text(encoding="utf-8"))
    report = {"stage": "export", "passed": True, "fbx": {"sha256": hashlib.sha256(fbx.read_bytes()).hexdigest(),
                                                           "settings": {"preset": {"name": preset["name"]}}},
              "roundtrip_reimport": {"triangles_total": 15, "material_count": 2, "armatures": 0},
              "expected_ue_dimensions_uu_at_import_scale_1": [100.0, 50.0, 200.0], "checks": {}}
    Path(params["report_out"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0, "TRIPO_PIPELINE_STAGE_OK export isolation=%s\n" % isolation


def rotate_xy(x, y, theta):
    c, s = round(math.cos(math.radians(theta)), 9), round(math.sin(math.radians(theta)), 9)
    return c * x - s * y, s * x + c * y


def rotated(bounds, theta):
    pts = [rotate_xy(x, y, theta) for x in (bounds["min"][0], bounds["max"][0])
           for y in (bounds["min"][1], bounds["max"][1])]
    return {"min": [round(min(p[0] for p in pts), 3), round(min(p[1] for p in pts), 3), bounds["min"][2]],
            "max": [round(max(p[0] for p in pts), 3), round(max(p[1] for p in pts), 3), bounds["max"][2]]}


def ue_predicted(bounds):
    lo, hi = bounds["min"], bounds["max"]
    return {"min": [lo[0], round(-hi[1], 3), lo[2]], "max": [hi[0], round(-lo[1], 3), hi[2]]}


def axis_of(vec):
    return {(1, 0): "+X", (-1, 0): "-X", (0, 1): "+Y", (0, -1): "-Y"}[(round(vec[0]), round(vec[1]))]


def fake_build(params, isolation):
    """Mimics blender/build_candidate.py: deterministic FBX bytes from source + atlas + profile."""
    profile = json.loads(Path(params["profile"]).read_text(encoding="utf-8"))
    atlas = json.loads(Path(params["atlas_report"]).read_text(encoding="utf-8"))
    source = hashlib.sha256(Path(params["source"]).read_bytes()).hexdigest()
    if not params.get("fbx_preset") or not Path(params["fbx_preset"]).is_file():
        return 1, "Traceback (most recent call last):\nRuntimeError: params.fbx_preset is required\n"
    preset = json.loads(Path(params["fbx_preset"]).read_text(encoding="utf-8"))
    theta = float(preset["export_space_rotation_z_degrees"])
    seed = (source + json.dumps(atlas["files"], sort_keys=True) + json.dumps(profile, sort_keys=True)
            + json.dumps(preset, sort_keys=True))
    sk, base = Path(params["sk_fbx_out"]), Path(params["base_fbx_out"])
    sk.write_bytes(b"FAKESKFBX\0" + hashlib.sha256(seed.encode()).hexdigest().encode())
    base.write_bytes(b"FAKEBASEFBX\0" + source.encode())
    Path(params["blend_out"]).write_text("nonce=%s\n" % uuid.uuid4().hex, encoding="utf-8")
    m = profile["meshes"]
    tris = profile["expectations"]["triangles"]
    fail = os.environ.get("FAKE_BUILD_FAIL_CHECK")
    flow = (profile.get("build") or {}).get("flow", "whole-figure")
    weapon = m.get("bow") if flow == "whole-figure" else m.get("weapon")
    slots = ["M_Atlas", "M_Face"][:profile["expectations"]["skeletal_material_slots"]]
    checks = {"roundtrip_material_slots": {"passed": True, "measured": {"skeletal_unique": slots}},
              "orientation_all_parts_outward_after_fix": {"passed": fail != "orientation", "measured": {}}}
    fx, fy, fz = [v * 100 for v in m["base"]["footprint_m"]]
    h = profile["scale"]["figure_height_m"] * 100
    # seated flow: a weapon reaches 5 uu above the figure top (the height check must use the figure top)
    top = h + 5.0 if (flow == "seated-parts" and weapon) else h
    authored = {"min": [-13.0, -11.4, 3.8], "max": [15.7, 9.7, top]}
    base_authored = {"min": [-fx / 2, -fy / 2, 0.0], "max": [fx / 2, fy / 2, fz]}
    sockets = []
    for i, sock in enumerate(profile.get("sockets") or []):
        predicted = [0.25 * i, -4.0 - i, 0.05]
        loc = sock.get("location_uu")
        sockets.append({"name": sock["name"], "bone": sock["bone"], "offset_blender_bone_local_uu": [0.25 * i, 4.0 + i, 0.05],
                        "offset_ue_bone_local_uu_predicted": predicted, "target_ue_component_uu": [1.0, 2.0, 40.0 + i],
                        "location_uu_for_ue": list(loc) if isinstance(loc, list) else predicted})
    skeletal_meshes = {m["body"]["object"]: {"triangles": tris[m["body"]["object"]]}}
    if weapon:
        skeletal_meshes[weapon["object"]] = {"triangles": tris[weapon["object"]]}
    report = {
        "stage": "build", "flow": flow, "passed": all(c["passed"] for c in checks.values()), "checks": checks,
        "fake_params_seen": {k: (Path(v).name if k in ("lib_dir", "reference_glb") else True) for k, v in sorted(params.items())},
        "figure": {"top_part": profile["scale"].get("top_part"), "figure_height_m": profile["scale"]["figure_height_m"],
                   "figure_top_m": h / 100.0, "skeletal_top_m": top / 100.0},
        "sockets": sockets,
        "exports": {"skeletal": {"file": sk.name, "sha256": hashlib.sha256(sk.read_bytes()).hexdigest()},
                    "base": {"file": base.name, "sha256": hashlib.sha256(base.read_bytes()).hexdigest()},
                    "settings": {"preset": {"name": preset["name"]}, "export_space_rotation_z_degrees": theta,
                                 "use_triangles": preset["use_triangles"]}},
        "orientation": {"flipped_parts": profile["orientation"]["expected_inside_out_parts"]},
        "meshes_pre_export_m": {m["base"]["object"]: {"triangles": tris[m["base"]["object"]],
                                                      "near_degenerate_triangles": 1,
                                                      "near_degenerate_area_cm2_below": 1e-4}},
        "expected_ue_bounds_uu_at_import_scale_1": {
            "skeletal_blender_axes": authored,
            "base_blender_axes": base_authored,
            "export_rotation_z_degrees": theta,
            "skeletal_export_frame": rotated(authored, theta),
            "skeletal_ue_predicted": ue_predicted(rotated(authored, theta)),
            "base_ue_predicted": ue_predicted(rotated(base_authored, theta))},
        "axes": {"face_mean_normal": [0.0, -0.4, 0.05], "bow_centroid_m": [0.1, -0.06, 0.3],
                 "export_frame": {"front_axis": axis_of(rotate_xy(0, -1, theta)),
                                  "bow_side_axis": axis_of(rotate_xy(1, 0, theta))}},
        "roundtrip": {"skeletal": {
            "bones": {b[0]: {"parent": b[1]} for b in profile["armature"]["bones"]},
            "meshes": skeletal_meshes}},
    }
    Path(params["report_out"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["passed"]:
        return 1, "Traceback (most recent call last):\nRuntimeError: build checks failed\n"
    return 0, "TRIPO_PIPELINE_STAGE_OK build isolation=%s\n" % isolation


def headless_main(argv):
    if "--version" in argv:
        print("Blender 9.9.9 (fake)")
        return 0
    script = Path(argv[argv.index("--python") + 1]).name
    params = json.loads(Path(argv[argv.index("--") + 1]).read_text(encoding="utf-8"))
    stage = {"import_source.py": "import", "export_fbx.py": "export", "build_candidate.py": "build"}[script]
    log_call(stage)
    code, out = run_stage(stage, params, "process")
    sys.stdout.write(out)
    return code


def mcp_main(argv):
    """Same contract as C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py."""
    if os.environ.get("FAKE_BLENDER_MCP_DOWN") == "1":
        sys.stderr.write("ConnectionRefusedError: [WinError 10061]\n")
        return 1
    op = argv[0]
    if op == "exec-str":
        buf = io.StringIO()
        with redirect_stdout(buf):
            exec(argv[1], {"bpy": FakeBpy})
        res = {"status": "success", "result": {"executed": True, "result": buf.getvalue()}}
    elif op == "exec":
        code = Path(argv[1]).read_text(encoding="utf-8")
        params_path = re.search(r"^TRIPO_PIPELINE_PARAMS = (.+)$", code, re.M).group(1)
        isolation = re.search(r'^TRIPO_PIPELINE_ISOLATION = "(\w+)"$', code, re.M).group(1)
        stage = re.search(r"stage (\w+) via blender-mcp", code).group(1)
        params = json.loads(Path(eval(params_path)).read_text(encoding="utf-8"))
        log_call("mcp:" + stage)
        rc, out = run_stage(stage, params, isolation)
        if rc:
            res = {"status": "error", "message": json.dumps({"exception_type": "RuntimeError", "traceback": out})}
        else:
            res = {"status": "success", "result": {"executed": True, "result": out}}
    else:
        return 2
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res.get("status") != "error" else 1


class FakeBpy:
    class app:
        version_string = "9.9.9 LTS"


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--mcp":
        sys.exit(mcp_main(args[1:]))
    sys.exit(headless_main(args))
