"""Look-dev v2 of Harpy (2026-09-29): the H3 texel state rebuilt from the H3 run (system python, no Blender).

The look-dev stages never rebake and never write into the H3 run. build() replays textures.py of this module (runpy,
unchanged) on a scratch run directory whose work/ holds hard links to the H3 bakes (work/bake/*.npy, uv-labels.npz,
uv-tris.npz): the replay's globals are the per-texel inputs the classes need (gutter-filled bakes, the gold mask of
metal_rule, the talon / skin / feather weights of materials, the W4-B team mask) and its 4K PNGs must equal the H3
4K masters byte for byte (sha256 of the H3 textures-report) -> the classes sit on exactly the texels H3 shipped.
texel_positions() adds the per-texel source-frame position (barycentric raster of work/uv-tris.npz).
Arrays: row 0 = v 0 (bottom), as textures.py.
"""

import os
import runpy
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def sha256(path):
    import hashlib
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def link_or_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def replay(src_profile, src_run, scratch):
    """Run textures.py of the H3 run on a scratch copy; returns (globals, reproduction check)."""
    src_run, scratch = Path(src_run), Path(scratch)
    if scratch.exists():
        shutil.rmtree(scratch)
    for rel in ("work/bake/normal.npy", "work/bake/ao.npy", "work/bake/bc.npy", "work/bake/rm.npy",
                "work/uv-labels.npz", "work/uv-tris.npz"):
        link_or_copy(src_run / rel, scratch / rel)
    (scratch / "reports").mkdir(parents=True, exist_ok=True)
    argv0 = sys.argv
    sys.argv = ["textures.py", str(src_profile), str(scratch)]
    sys.path.insert(0, str(HERE))
    try:
        g = runpy.run_path(str(HERE / "textures.py"), run_name="h3_textures_replay")
    finally:
        sys.argv = argv0
    import json
    ref = json.loads((src_run / "reports" / "textures-report.json").read_text(encoding="utf-8"))["outputs"]
    rep = {}
    for level in ("master", "runtime"):
        for k, o in ref[level].items():
            if k.startswith("_"):
                continue
            got = sha256(scratch / o["path"])
            rep["%s/%s" % (level, k)] = {"h3_sha256": o["sha256"], "replay_sha256": got, "equal": got == o["sha256"]}
    return g, rep


def texel_positions(uv_tris, n):
    """Source-frame position per texel (barycentric raster of the UV0 triangles; -1 label = empty, gutters by the
    nearest covered texel). Returns (pos [n, n, 3] float32, tri [n, n] int32)."""
    from scipy import ndimage
    uv, co = uv_tris["uv"], uv_tris["co"]
    pos = np.zeros((n, n, 3), np.float32)
    tri = np.full((n, n), -1, np.int32)
    pts = uv * n
    for t in range(len(pts)):
        (x0, y0), (x1, y1), (x2, y2) = pts[t]
        xmin = max(int(np.floor(min(x0, x1, x2) - 0.5)), 0)
        xmax = min(int(np.ceil(max(x0, x1, x2) - 0.5)), n - 1)
        ymin = max(int(np.floor(min(y0, y1, y2) - 0.5)), 0)
        ymax = min(int(np.ceil(max(y0, y1, y2) - 0.5)), n - 1)
        if xmax < xmin or ymax < ymin:
            continue
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-12:
            continue
        gx, gy = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
        w0 = ((x1 - gx) * (y2 - gy) - (x2 - gx) * (y1 - gy)) / area
        w1 = ((x2 - gx) * (y0 - gy) - (x0 - gx) * (y2 - gy)) / area
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
        if not inside.any():
            continue
        iy, ix = np.nonzero(inside)
        p = w0[inside, None] * co[t, 0] + w1[inside, None] * co[t, 1] + w2[inside, None] * co[t, 2]
        pos[iy + ymin, ix + xmin] = p
        tri[iy + ymin, ix + xmin] = t
    _d, (jy, jx) = ndimage.distance_transform_edt(tri < 0, return_indices=True)
    return pos[jy, jx], tri
