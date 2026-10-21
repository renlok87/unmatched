"""pytest tools/mapkits/test_clean_glb.py: clean_glb on a synthetic GLB (body cube + floating chip + flipped face)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clean_glb  # noqa: E402
from level_glb import read_glb, write_glb  # noqa: E402

CUBE_F = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
          (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def cube(lo, size):
    c = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1], [0, 1, 0], [1, 1, 0], [1, 1, 1], [0, 1, 1]], float)
    return c * size + np.asarray(lo, float), np.array(CUBE_F)[:, ::-1]  # CUBE_F lists the faces inward


def outward_normals(v, f):
    n = np.zeros_like(v)
    for t in f:
        a, b, c = v[t]
        n[t] += np.cross(b - a, c - a)
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def make_glb(p: Path, flip_face: int | None = None, bad_normals: bool = False) -> None:
    vb, fb = cube([-0.5, 0, -0.5], 1.0)
    vc, fc = cube([0.3, 1.5, 0.3], 0.02)  # chip floating 0.5 above the body
    v = np.vstack([vb, vc]).astype(np.float32)
    f = np.vstack([fb, fc + 8])
    n = np.vstack([outward_normals(vb, fb), outward_normals(vc, fc)]).astype(np.float32)
    if bad_normals:
        n[:8] *= -1
    if flip_face is not None:
        f[flip_face] = f[flip_face][[0, 2, 1]]
    uv = (v[:, [0, 2]] + 0.5).astype(np.float32)
    img = b"\x89PNG-fake-texture-bytes"
    parts = [img, v.tobytes(), n.tobytes(), uv.tobytes(), f.astype(np.uint32).tobytes()]
    bvs, off, blob = [], 0, b""
    for b in parts:
        blob += b"\0" * ((4 - len(blob) % 4) % 4)
        bvs.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(b)})
        blob += b
    acc = [{"bufferView": 1, "componentType": 5126, "count": len(v), "type": "VEC3",
            "min": v.min(0).tolist(), "max": v.max(0).tolist()},
           {"bufferView": 2, "componentType": 5126, "count": len(v), "type": "VEC3"},
           {"bufferView": 3, "componentType": 5126, "count": len(v), "type": "VEC2"},
           {"bufferView": 4, "componentType": 5125, "count": f.size, "type": "SCALAR"}]
    j = {"asset": {"version": "2.0"}, "accessors": acc, "bufferViews": bvs, "buffers": [{"byteLength": len(blob)}],
         "images": [{"bufferView": 0, "mimeType": "image/png"}],
         "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2}, "indices": 3}]}],
         "nodes": [{"mesh": 0, "rotation": [0, 0, 0.01, 0.99995]}], "scenes": [{"nodes": [0]}], "scene": 0}
    write_glb(p, j, blob)


def test_drops_floating_chip_keeps_textures(tmp_path):
    p = tmp_path / "a.glb"
    make_glb(p)
    dry = clean_glb.clean(p)
    assert [s["shell"] for s in dry["dropped_shells"]] == [1] and dry["applied"] is False
    r = clean_glb.clean(p, apply=True)
    assert r["applied"] and r["dropped_triangles"] == 12 and r["triangles_after"] == 12
    j, binary = read_glb(p)
    assert j["accessors"][3]["count"] == 36 and j["accessors"][0]["count"] == 8
    assert abs(j["accessors"][0]["max"][1] - 1.0) < 1e-6  # chip gone from the bounds
    bv = j["bufferViews"][0]
    assert binary[bv["byteOffset"]:bv["byteOffset"] + bv["byteLength"]] == b"\x89PNG-fake-texture-bytes"
    assert j["nodes"][0]["rotation"] == [0, 0, 0.01, 0.99995]
    assert j["extras"]["mapkitClean"]["dropped_triangles"] == 12
    assert clean_glb.clean(p, apply=True)["note"].startswith("already cleaned")


def test_keep_overrides_rule(tmp_path):
    p = tmp_path / "a.glb"
    make_glb(p)
    assert clean_glb.clean(p, keep={1})["dropped_shells"] == []


def test_flipped_face_turned_outward(tmp_path):
    p = tmp_path / "a.glb"
    make_glb(p, flip_face=4)
    r = clean_glb.clean(p, apply=True, normals=True, keep={1})
    assert r["faces_flipped_inward_to_outward"] == 1
    j, binary, m = clean_glb.load(p)
    v, f = m["attrs"]["POSITION"].astype(float), m["idx"]
    n = m["attrs"]["NORMAL"]
    body = [t for t in f if v[t].max(0)[1] <= 1.0 + 1e-6]
    for t in body:
        a, b, c = v[t]
        fn = np.cross(b - a, c - a)
        assert np.dot(fn, (a + b + c) / 3 - np.array([0, 0.5, 0])) > 0  # every body face points out of the cube
        assert all(np.dot(fn, n[k]) > 0 for k in t)  # corner normals agree with the winding
    assert clean_glb.facing(v, f).tolist().count("inward") == 0


def test_corner_normals_against_winding_negated(tmp_path):
    p = tmp_path / "a.glb"
    make_glb(p, bad_normals=True)
    r = clean_glb.clean(p, apply=True, normals=True, keep={1})
    assert r["faces_flipped_inward_to_outward"] == 0
    assert r["faces_corner_normals_negated_to_match_winding"] == 12


def test_double_adds_reversed_back_layer(tmp_path):
    p = tmp_path / "a.glb"
    make_glb(p)
    r = clean_glb.clean(p, apply=True, double={1}, keep={1})
    assert r["dropped_triangles"] == 0 and r["doubled_triangles"] == 12 and r["triangles_after"] == 36
    j, binary, m = clean_glb.load(p)
    v, f, n = m["attrs"]["POSITION"].astype(float), m["idx"], m["attrs"]["NORMAL"]
    assert len(v) == 24
    for t in f[24:]:  # the back layer of the chip: faces point into the chip, normals agree with the winding
        a, b, c = v[t]
        fn = np.cross(b - a, c - a)
        assert np.dot(fn, (a + b + c) / 3 - v[8:16].mean(0)) < 0
        assert all(np.dot(fn, n[k]) > 0 for k in t)


def test_drop_below_cuts_the_ground_skirt(tmp_path):
    p = tmp_path / "a.glb"
    make_glb(p)
    r = clean_glb.clean(p, apply=True, keep={1}, drop_below=0.05)
    assert r["dropped_triangles_below"] == 2 and r["dropped_triangles"] == 2  # the bottom of the body cube
    assert r["triangles_after"] == 22


def test_orient_makes_card_winding_consistent(tmp_path):
    p = tmp_path / "a.glb"
    make_glb(p, flip_face=2)  # face 2 of the body walks its edges against its neighbours
    r = clean_glb.clean(p, apply=True, keep={1}, orient={0})
    assert r["faces_flipped_to_consistent_winding"] == 1
    _, _, m = clean_glb.load(p)
    v, f = m["attrs"]["POSITION"].astype(float), m["idx"][:12]
    assert clean_glb.orient_flips(f, clean_glb.weld(v), clean_glb.tri_area(v[f])).sum() == 0


def test_renormal_replaces_bad_corner_normals(tmp_path):
    p = tmp_path / "a.glb"
    make_glb(p, bad_normals=True)  # body corner normals all point inward
    r = clean_glb.clean(p, apply=True, keep={1}, renormal={0})
    assert r["faces_renormalled"] == 12
    _, _, m = clean_glb.load(p)
    v, f, n = m["attrs"]["POSITION"].astype(float), m["idx"], m["attrs"]["NORMAL"]
    for t in f[:12]:
        a, b, c = v[t]
        fn = np.cross(b - a, c - a)
        assert all(np.dot(fn, n[k]) > 0.99 * np.linalg.norm(fn) for k in t)  # cube faces: split at 90 deg = flat
