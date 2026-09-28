"""Depth companion of the T1.2 part-ID renders idsplit/id-cull-k2-front-d300-<tag>.png (stage 3, T2.3).

The K2 masks of the thresholds.json revision rev1-t23 are the Blender ID renders of each variant
reprojected into packaged-live frames (tools/art/art004_live_k2.py metrics --threshold-set rev1-t23).
The live camera sits 86 (5x) .. 1630 (1x) uu behind the Blender K2 camera on nearly the same line of
sight, so an exact reprojection needs the depth of every rendered pixel. This script casts one ray per
pixel centre of the SAME camera (k2-front-d300 of art004_head_tilt_v3_measure.py V31_VIEWS: perspective,
horizontal FOV 35, 1920x1080, camera (0, -3 cos55, 0.29 + 3 sin55) m looking at (0, 0, 0.29) m) into the
SAME FBX files (sha256 checked against blender-measurements.json inputs_sha256), keeps the first
FRONT-facing hit (the renders use backface culling) and stores its depth along the camera axis in uu.
Consistency with the ID render is part of the output: hit / no-hit per pixel against the render alpha and
body / bow against the blue bow colour.

CPU ray casting only (no Workbench/EEVEE/Cycles render, no GPU token), Blender 5.2, repository root:

  blender --background --factory-startup --python tools/art/art004_k2_id_depth.py -- [--tags v2,v3,v31a]

Writes docs/game-design/evidence/ART-004/k2-id-depth-2026-09-28/ (override: ART004_K2_DEPTH_OUT):
id-depth-k2-front-d300-<tag>.npz (float32 depth_uu over the render's figure bbox + 4 px, NaN = no
front-facing hit; origin_xy; camera) and depth-report.json. Never saves a .blend. Diagnostic geometry,
not an art acceptance.
"""

import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "docs/game-design/evidence/ART-004/head-tilt-v31-probe-2026-09-28"
OUT = Path(os.environ.get("ART004_K2_DEPTH_OUT") or ROOT / "docs/game-design/evidence/ART-004/k2-id-depth-2026-09-28")
ASSET = ROOT / "blender/ASSET-MEDUSA-001"
FBX = {"v2": ASSET / "variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx",
       "v3": ASSET / "variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx",
       "v31a": ASSET / "variants/head-tilt-v31-a/SK_Medusa_HeadTilt_v31a.fbx"}
C55, S55 = math.cos(math.radians(55)), math.sin(math.radians(55))
VIEW = {"name": "k2-front-d300", "camera_m": (0.0, -3 * C55, 0.29 + 3 * S55), "target_m": (0.0, 0.0, 0.29),
        "hfov_deg": 35.0, "resolution": (1920, 1080)}
UU = 100.0
MARGIN = 4
EPS_M = 1e-5


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).resolve().as_posix()


def read_png(path):
    image = bpy.data.images.load(str(path))
    w, h = image.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    image.pixels.foreach_get(buf)
    bpy.data.images.remove(image)
    return np.round(buf.reshape(h, w, 4)[::-1] * 255).astype(np.uint8)


def world_triangles(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    mw = ev.matrix_world
    verts = [mw @ v.co for v in mesh.vertices]
    polys = [tuple(p.vertices) for p in mesh.polygons]
    ev.to_mesh_clear()
    return verts, polys


def camera_basis():
    loc = Vector(VIEW["camera_m"])
    fwd = (Vector(VIEW["target_m"]) - loc).normalized()
    quat = fwd.to_track_quat("-Z", "Y")  # same as look_at() of the measurement script
    m = quat.to_matrix()
    right, up = m @ Vector((1, 0, 0)), m @ Vector((0, 1, 0))
    return loc, fwd, right, up


def depth_for(tag, idsplit):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(FBX[tag]), use_custom_normals=True)
    body, bow = bpy.data.objects["SK_Medusa_Body"], bpy.data.objects["SK_Medusa_Bow"]
    bpy.context.view_layer.update()
    vb, pb = world_triangles(body)
    vw, pw = world_triangles(bow)
    verts = vb + vw
    polys = pb + [tuple(i + len(vb) for i in p) for p in pw]
    n_body = len(pb)
    tree = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    loc, fwd, right, up = camera_basis()
    w, h = VIEW["resolution"]
    f = (w / 2) / math.tan(math.radians(VIEW["hfov_deg"]) / 2)
    alpha = idsplit[..., 3] > 127
    ys, xs = np.nonzero(alpha)
    x0, x1 = max(0, int(xs.min()) - MARGIN), min(w, int(xs.max()) + 1 + MARGIN)
    y0, y1 = max(0, int(ys.min()) - MARGIN), min(h, int(ys.max()) + 1 + MARGIN)
    depth = np.full((y1 - y0, x1 - x0), np.nan, dtype=np.float32)
    is_bow = np.zeros(depth.shape, dtype=bool)
    backface_skips = 0
    for j in range(y0, y1):
        vy = (h / 2 - (j + 0.5)) / f
        for i in range(x0, x1):
            d = (fwd + right * ((i + 0.5 - w / 2) / f) + up * vy).normalized()
            origin = loc.copy()
            for _ in range(16):
                hit, normal, index, dist = tree.ray_cast(origin, d)
                if hit is None:
                    break
                if normal.dot(d) < 0.0:  # front-facing: visible with backface culling
                    depth[j - y0, i - x0] = (hit - loc).dot(fwd) * UU
                    is_bow[j - y0, i - x0] = index >= n_body
                    break
                backface_skips += 1
                origin = hit + d * EPS_M
    hit_mask = ~np.isnan(depth)
    a = alpha[y0:y1, x0:x1]
    blue = (np.abs(idsplit[y0:y1, x0:x1, :3].astype(int) - np.array((0, 0, 255))).sum(axis=2) < 30) & a
    both = hit_mask & a
    stats = {
        "renderAlphaPx": int(a.sum()), "hitPx": int(hit_mask.sum()), "hitAndAlphaPx": int(both.sum()),
        "alphaWithoutHitPx": int((a & ~hit_mask).sum()), "hitWithoutAlphaPx": int((hit_mask & ~a).sum()),
        "alphaAgreement": round(float((hit_mask == a).mean()), 6),
        "bowAgreementOnBothPx": round(float((is_bow[both] == blue[both]).mean()), 6) if both.any() else None,
        "backfaceSkips": backface_skips,
        "depthUu": {"min": round(float(np.nanmin(depth)), 3), "max": round(float(np.nanmax(depth)), 3)}}
    return depth, (x0, y0), stats


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    tags = ["v2", "v3", "v31a"]
    if "--tags" in argv:
        tags = argv[argv.index("--tags") + 1].split(",")
    meas = json.loads((PROBE / "blender-measurements.json").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"schema": "unmatched.art004-k2-id-depth/1", "status": "measured_diagnostic_not_art_acceptance",
              "runner": f"Blender {bpy.app.version_string} --background --factory-startup (BVH ray casting, CPU)",
              "script": "tools/art/art004_k2_id_depth.py",
              "view": {"name": VIEW["name"], "camera_m": [round(v, 7) for v in VIEW["camera_m"]],
                       "target_m": list(VIEW["target_m"]), "hfov_deg": VIEW["hfov_deg"],
                       "resolution": list(VIEW["resolution"]),
                       "pixel": "ray through the pixel centre (i + 0.5, j + 0.5), row 0 = top",
                       "depth": "distance of the first front-facing hit along the camera axis, uu (Blender m x 100)"},
              "companionOf": "docs/game-design/evidence/ART-004/head-tilt-v31-probe-2026-09-28/idsplit-k2-front-d300-<tag>.png",
              "variants": {}}
    for tag in tags:
        fbx_sha = sha(FBX[tag])
        want = (meas.get("inputs_sha256") or {}).get(tag)
        assert fbx_sha == want, (tag, fbx_sha, want)
        split_path = PROBE / f"idsplit-k2-front-d300-{tag}.png"
        idsplit = read_png(split_path)
        px_sha = hashlib.sha256(np.ascontiguousarray(idsplit).tobytes()).hexdigest()
        want_px = meas["part_id_views"][tag]["idsplit-k2-front-d300"]["pixels_sha256"]
        assert px_sha == want_px, (tag, px_sha, want_px)
        depth, origin, stats = depth_for(tag, idsplit)
        out = OUT / f"id-depth-k2-front-d300-{tag}.npz"
        with open(out, "wb") as fh:  # depthSha256 below hashes the array bytes (content), sha256 the file
            np.savez_compressed(fh, depth_uu=depth, origin_xy=np.array(origin, dtype=np.int32))
        report["variants"][tag] = {"fbx": FBX[tag].relative_to(ROOT).as_posix(), "fbxSha256": fbx_sha,
                                   "idsplit": split_path.relative_to(ROOT).as_posix(), "idsplitPixelsSha256": px_sha,
                                   "file": rel(out), "sha256": sha(out),
                                   "depthSha256": hashlib.sha256(np.ascontiguousarray(depth).tobytes()).hexdigest(),
                                   "originXY": list(origin), "shape": list(depth.shape), **stats}
        print("ART004_K2_DEPTH", tag, json.dumps(stats))
    (OUT / "depth-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")
    print("ART004_K2_DEPTH_DONE", OUT)


main()
