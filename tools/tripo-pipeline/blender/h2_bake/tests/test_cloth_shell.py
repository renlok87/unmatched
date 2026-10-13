"""Decision П3-3 (Achilles pilot 2026-10-13): opt-in `rig.cloth_shell` — the listed single-sheet cloth parts become a thin
closed shell in the rig stage (st_rig.add_cloth_shell). A profile without the key takes the old code path.

Plain Python: profile accessor and validation. Blender headless (skipped without Blender 5.2): the shell on a toy sheet,
and the Medusa rig stage re-run from the local H2 work files (skipped when they are not on this machine: work/ is not
in git) with byte-identical FBX against the committed rig report.
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q"""

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = HERE.parents[4]
sys.path.insert(0, str(PKG.parent))

from h2_bake import profile as PR  # noqa: E402

MEDUSA = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"
MEDUSA_RUN = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake"
BLENDER = os.environ.get("H2_BAKE_BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@pytest.fixture()
def medusa():
    return json.loads(MEDUSA.read_text(encoding="utf-8"))


def body_part(p):
    return next(n for n, c in sorted(p["parts"].items()) if c["mesh"] == "body")


# ------------------------------------------------------------------ plain Python
def test_profiles_without_the_key_are_unchanged(medusa):
    assert "cloth_shell" not in medusa["rig"]
    assert PR.cloth_shell(medusa) is None
    assert PR.cloth_shell_problems(medusa) == []
    assert PR.validate(medusa) == []


def test_valid_cloth_shell(medusa):
    p = copy.deepcopy(medusa)
    p["rig"]["cloth_shell"] = {"parts": [body_part(p)], "offset_mm": 0.3}
    assert PR.validate(p) == []
    assert PR.cloth_shell(p)["parts"] == [body_part(p)]


@pytest.mark.parametrize("cfg, message", [
    ({"parts": [], "offset_mm": 0.3}, "non-empty list"),
    ({"offset_mm": 0.3}, "non-empty list"),
    ({"parts": ["tripo_part_99"], "offset_mm": 0.3}, "unknown part"),
    ({"parts": ["BASE"], "offset_mm": 0.3}, "is the base"),
    ({"parts": ["BODY", "BODY"], "offset_mm": 0.3}, "duplicates"),
    ({"parts": ["BODY"], "offset_mm": 0}, "offset_mm"),
    ({"parts": ["BODY"], "offset_mm": 2.5}, "offset_mm"),
    ({"parts": ["BODY"]}, "offset_mm"),
])
def test_invalid_cloth_shell(medusa, cfg, message):
    p = copy.deepcopy(medusa)
    base = next(n for n, c in p["parts"].items() if c["mesh"] == "base")
    cfg = json.loads(json.dumps(cfg).replace("BASE", base).replace("BODY", body_part(p)))
    p["rig"]["cloth_shell"] = cfg
    problems = PR.validate(p)
    assert any(message in s for s in problems), problems


# ------------------------------------------------------------------ Blender: the shell on a toy sheet
TOY = r'''
import json, sys
from pathlib import Path
import bmesh, bpy
import numpy as np
from mathutils import Vector
sys.path.insert(0, sys.argv[sys.argv.index("--") + 1])
out = Path(sys.argv[sys.argv.index("--") + 2])
from h2_bake import st_rig
bpy.ops.wm.read_factory_settings(use_empty=True)
# an open sheet: a 6 x 4 grid bent into a half cylinder (normals out), one extra cap face, two vertex groups, UV
bm = bmesh.new()
nx, nz = 6, 4
vs = {}
for i in range(nx + 1):
    a = np.pi * i / nx
    for k in range(nz + 1):
        vs[i, k] = bm.verts.new((float(np.cos(a)) * 0.05, float(np.sin(a)) * 0.05, 0.02 * k))
uv = bm.loops.layers.uv.new("UVMap")
cap = bm.faces.layers.int.new("h2_cap")
for i in range(nx):
    for k in range(nz):
        f = bm.faces.new([vs[i, k], vs[i, k + 1], vs[i + 1, k + 1], vs[i + 1, k]])
        for l in f.loops:
            ii, kk = next(key for key, v in vs.items() if v == l.vert)
            l[uv].uv = (ii / nx, kk / nz)
c0 = bm.verts.new((0.0, 0.0, 0.0)); c1 = bm.verts.new((0.01, 0.0, 0.0)); c2 = bm.verts.new((0.0, 0.0, 0.01))
fc = bm.faces.new([c0, c1, c2])
fc[cap] = 1
bm.normal_update()
for f in bm.faces:  # outward (away from the cylinder axis) like the orientation stage leaves a part
    if f[cap] == 0 and f.normal.dot(Vector((f.calc_center_median().x, f.calc_center_median().y, 0))) < 0:
        f.normal_flip()
me = bpy.data.meshes.new("toy")
bm.to_mesh(me)
bm.free()
obj = bpy.data.objects.new("LP_toy", me)
bpy.context.scene.collection.objects.link(obj)
ga, gb = obj.vertex_groups.new(name="spine"), obj.vertex_groups.new(name="hips")
for v in me.vertices:
    ga.add([v.index], 0.25 + 0.5 * (v.co.z / 0.08), "REPLACE")
    gb.add([v.index], 0.75 - 0.5 * (v.co.z / 0.08), "REPLACE")
before = {"verts": [tuple(v.co) for v in me.vertices], "polys": [list(p.vertices) for p in me.polygons],
          "normals": [tuple(p.normal) for p in me.polygons],
          "uv": [tuple(me.uv_layers[0].data[li].uv) for p in me.polygons for li in p.loop_indices],
          "weights": [{g.group: g.weight for g in v.groups} for v in me.vertices]}
rep = st_rig.add_cloth_shell(obj, 0.0003)
me = obj.data
capv = [0] * len(me.polygons)
me.attributes["h2_cap"].data.foreach_get("value", capv)
bm = bmesh.new()
bm.from_mesh(me)
edge_faces = sorted({len([f for f in e.link_faces if capv[f.index] == 0]) for e in bm.edges if not all(capv[f.index] for f in e.link_faces)})
bm.free()
after = {"verts": [tuple(v.co) for v in me.vertices], "polys": [list(p.vertices) for p in me.polygons],
         "normals": [tuple(p.normal) for p in me.polygons],
         "uv": [[tuple(me.uv_layers[0].data[li].uv) for li in p.loop_indices] for p in me.polygons],
         "weights": [{g.group: g.weight for g in v.groups} for v in me.vertices], "cap": capv,
         "smooth": [p.use_smooth for p in me.polygons], "real_faces_per_edge": edge_faces}
out.write_text(json.dumps({"before": before, "after": after, "report": rep}), encoding="utf-8")
'''


def run_blender(script_text, args, tmp_path, timeout=600):
    script = tmp_path / "script.py"
    script.write_text(script_text, encoding="utf-8")
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(script), "--"]
                       + [str(a) for a in args], capture_output=True, text=True, timeout=timeout, creationflags=FLAGS)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    return r


@pytest.mark.skipif(not Path(BLENDER).is_file(), reason="Blender 5.2 not installed")
def test_shell_on_a_toy_sheet(tmp_path):
    import numpy as np

    out = tmp_path / "toy.json"
    run_blender(TOY, [PKG.parent, out], tmp_path)
    d = json.loads(out.read_text(encoding="utf-8"))
    b, a, rep = d["before"], d["after"], d["report"]
    nv0, nf0 = len(b["verts"]), len(b["polys"])
    real = nf0 - 1  # the cap triangle is not copied
    assert rep["faces"] == real and rep["vertices"] == 35 and rep["rim_edges_bridged"] == 20
    assert len(a["polys"]) == nf0 + real + 40 and len(a["verts"]) == nv0 + 35
    assert a["real_faces_per_edge"] == [2]  # closed and manifold: no rim edge left
    # the original mesh is untouched (same vertices, faces, normals, weights)
    assert a["verts"][:nv0] == b["verts"] and a["polys"][:nf0] == b["polys"]
    assert np.allclose(a["normals"][:nf0], b["normals"], atol=1e-6)
    assert a["weights"][:nv0] == b["weights"]
    src_of = {}
    real_idx = [i for i in range(nf0) if a["cap"][i] == 0]
    for j, i in enumerate(real_idx):
        k = nf0 + j
        for vs, vn in zip(reversed(b["polys"][i]), a["polys"][k]):
            src_of[vn] = vs
        assert np.dot(a["normals"][k], b["normals"][i]) < -0.95  # reversed winding: normal inward
        assert a["uv"][k] == list(reversed(a["uv"][i]))  # the same UV0 per corner
        assert a["cap"][k] == 0 and a["smooth"][k] == a["smooth"][i]
    assert len(src_of) == 35
    for vn, vs in src_of.items():
        assert a["weights"][vn] == pytest.approx(b["weights"][vs])  # weights copied exactly
        dist = np.linalg.norm(np.subtract(a["verts"][vn], b["verts"][vs]))
        on_rim = abs(b["verts"][vs][2]) < 1e-6 or abs(b["verts"][vs][2] - 0.08) < 1e-6 or abs(b["verts"][vs][1]) < 1e-6
        if not on_rim:  # a rim vertex moves along the averaged normal of its fewer faces: same length, other direction
            assert np.hypot(*a["verts"][vn][:2]) == pytest.approx(0.05 - 0.0003, abs=2e-6)  # inward, towards the axis
        assert dist == pytest.approx(0.0003, rel=1e-3)
    for k in range(nf0 + real, len(a["polys"]), 2):  # bridges: two triangles (b, a, a') (b, a', b') per rim edge
        t1, t2 = a["polys"][k], a["polys"][k + 1]
        assert [v < nv0 for v in t1] == [True, True, False] and [v < nv0 for v in t2] == [True, False, False]
        assert src_of[t1[2]] == t1[1] and t2[1] == t1[2] and src_of[t2[2]] == t1[0] == t2[0]
        assert a["uv"][k] == [a["uv"][k][0], a["uv"][k][1], a["uv"][k][1]]  # rim colour: UV of the rim corners
        assert a["uv"][k + 1] == [a["uv"][k][0], a["uv"][k][1], a["uv"][k][0]]


# ------------------------------------------------------------------ Blender: Medusa rig stage, byte-identical FBX
@pytest.mark.skipif(not Path(BLENDER).is_file() or not (MEDUSA_RUN / "work" / "lp_uv.blend").is_file(),
                    reason="Blender 5.2 or the local Medusa H2 work files (not in git) are missing")
def test_medusa_rig_stage_is_byte_identical(tmp_path):
    prof = json.loads(MEDUSA.read_text(encoding="utf-8"))
    assert PR.cloth_shell(prof) is None
    run = tmp_path / "run"
    (run / "work").mkdir(parents=True)
    (run / "textures").mkdir()
    shutil.copy2(MEDUSA_RUN / "work" / "lp_uv.blend", run / "work" / "lp_uv.blend")
    bc = "%s_BC.png" % prof["textures"]["prefix"]
    shutil.copy2(MEDUSA_RUN / "textures" / bc, run / "textures" / bc)
    r = subprocess.run([sys.executable, str(PKG / "run_h2_bake.py"), "--profile", str(MEDUSA), "--run-dir", str(run),
                        "--stages", "rig", "--blender", BLENDER], capture_output=True, text=True, timeout=900,
                       creationflags=FLAGS)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    committed = json.loads((MEDUSA_RUN / "reports" / "rig-report.json").read_text(encoding="utf-8"))["exports"]
    for key in ("skeletal_fbx", "base_fbx"):
        name = Path(committed[key]["path"]).name
        assert PR.sha256(run / "export" / name) == committed[key]["sha256"], name
    rep = json.loads((run / "reports" / "rig-report.json").read_text(encoding="utf-8"))
    assert "cloth_shell" not in rep and rep["passed"]
