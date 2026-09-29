"""Ray-cast "cameras" for the close and seams stages (bpy / mathutils only, deterministic, no render engine).

An orthographic view = direction d (unit, camera looks along d) + pixel pitch; the pixel grid covers the projection
of the given bounds. Every pixel ray starts outside the bounds and returns the FIRST surface it meets:
  kind  0 = nothing, 1 = front face (geometric polygon normal . d < 0), 2 = back face (normal . d > 0: the ray sees
        the inside of an open shell — with UE one-sided materials that pixel shows whatever lies behind, i.e. a
        see-through hole)
  label per-polygon int label of the hit (callers pack part / cap ids into it)
Views: profile-driven lists of (name, azimuth_deg, elevation_deg); azimuth 0 = camera in front of the figure (-Y side,
looking +Y), 90 = camera on the +X side; elevation > 0 = camera above looking down."""

import math

import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

DEFAULT_VIEWS = [("front", 0, 0), ("front_l", 45, 0), ("left", 90, 0), ("back_l", 135, 0), ("back", 180, 0),
                 ("back_r", 225, 0), ("right", 270, 0), ("front_r", 315, 0),
                 ("front_hi", 0, 35), ("left_hi", 90, 35), ("back_hi", 180, 35), ("right_hi", 270, 35),
                 ("k2", 0, 55), ("front_lo", 0, -25), ("left_lo", 90, -25), ("back_lo", 180, -25), ("right_lo", 270, -25)]


def view_dir(az_deg, el_deg):
    """Direction the camera LOOKS along (from the camera towards the figure)."""
    az, el = math.radians(az_deg), math.radians(el_deg)
    cam = np.array([math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)])  # camera position dir
    return -cam


def basis(d):
    up = np.array([0.0, 0.0, 1.0])
    if abs(d @ up) > 0.99:
        up = np.array([0.0, 1.0, 0.0])
    right = np.cross(d, up)
    right /= np.linalg.norm(right)
    up2 = np.cross(right, d)
    return right, up2


def build(tris, labels):
    """tris: list of vertex-coordinate triples/ngons (sequences of 3D points); labels: int per polygon."""
    verts, polys = [], []
    for poly in tris:
        off = len(verts)
        verts.extend(Vector(tuple(p)) for p in poly)
        polys.append(list(range(off, off + len(poly))))
    return BVHTree.FromPolygons(verts, polys, all_triangles=False), np.asarray(labels, np.int64)


def mesh_polys(co, polygons):
    return [[co[i] for i in p] for p in polygons]


def render(bvh, labels, d, pts, pitch, pass_back=None):
    """pts: points whose projection the grid must cover (e.g. every vertex of the scene). Returns kind [H, W] uint8,
    label [H, W] int64 (-1 = none), row 0 = top of the view.
    pass_back: optional bool array per polygon label index — a BACK-face hit on such a polygon is passed through (a
    cap seen from behind is culled by a one-sided material, the pixel shows what lies behind it)."""
    d = np.asarray(d, np.float64)
    right, up = basis(d)
    pts = np.asarray(pts, np.float64)
    pr, pu, pd = pts @ right, pts @ up, pts @ d
    w = int(math.ceil((pr.max() - pr.min()) / pitch)) + 2
    h = int(math.ceil((pu.max() - pu.min()) / pitch)) + 2
    start = pd.min() - 0.01
    far = pd.max() - start + 0.02
    xs = pr.min() - pitch / 2 + np.arange(w) * pitch
    ys = pu.max() + pitch / 2 - np.arange(h) * pitch
    origins = (ys[:, None, None] * up[None, None, :] + xs[None, :, None] * right[None, None, :] + start * d).reshape(-1, 3)
    kind = np.zeros(h * w, np.uint8)
    lab = np.full(h * w, -1, np.int64)
    dv = Vector(tuple(d))
    cast = bvh.ray_cast
    for k, o in enumerate(origins.tolist()):
        origin, left = Vector(o), far
        for _skip in range(16):
            loc, nrm, idx, dist = cast(origin, dv, left)
            if loc is None:
                break
            back = nrm.dot(dv) > 0
            if back and pass_back is not None and pass_back[idx]:
                origin, left = loc + dv * 1e-6, left - dist - 1e-6
                continue
            kind[k] = 2 if back else 1
            lab[k] = labels[idx]
            break
    return kind.reshape(h, w), lab.reshape(h, w)
