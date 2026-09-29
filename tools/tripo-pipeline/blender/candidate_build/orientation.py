"""Per-face orientation fix against a reference high-poly GLB (profile orientation.per_face_reference).

A part whose retopology winding is MIXED (Harpy's head: 123 of 2 847 manifold edges traversed the same way by
both faces) cannot be fixed by flipping the whole part: every face votes against the nearest triangle of the
correctly oriented Tripo high-poly, then iterated conditional modes smooth the votes toward consistent winding.
Moved unchanged from build_harpy_candidate.py (2026-09-28)."""

import json
import struct
from collections import defaultdict
from pathlib import Path

import numpy as np
from mathutils.bvhtree import BVHTree

from .core import r


def read_glb_node_triangles(path, node_names):
    """Positions (Blender frame: (x, -z, y) of glTF) and triangle indices of the named mesh nodes, numpy only."""
    data = Path(path).read_bytes()
    if data[:4] != b"glTF" or struct.unpack_from("<I", data, 8)[0] != len(data):
        raise RuntimeError("not a complete binary glTF: %s" % path)
    json_len = struct.unpack_from("<I", data, 12)[0]
    model = json.loads(data[20:20 + json_len])
    binary = 20 + json_len + 8
    comp = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
    ncomp = {"SCALAR": 1, "VEC3": 3}

    def accessor(index):
        acc = model["accessors"][index]
        view = model["bufferViews"][acc["bufferView"]]
        dtype = np.dtype(comp[acc["componentType"]])
        n = ncomp[acc["type"]]
        start = binary + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        stride = view.get("byteStride") or dtype.itemsize * n
        if stride == dtype.itemsize * n:
            arr = np.frombuffer(data, dtype=dtype, count=acc["count"] * n, offset=start).reshape(acc["count"], n)
        else:
            raw = np.frombuffer(data, dtype=np.uint8, count=stride * acc["count"], offset=start).reshape(acc["count"], stride)
            arr = raw[:, :dtype.itemsize * n].copy().view(dtype).reshape(acc["count"], n)
        return arr

    out = {}
    for node in model["nodes"]:
        if node.get("name") not in node_names or "mesh" not in node:
            continue
        if any(k in node for k in ("translation", "rotation", "scale", "matrix")):
            raise RuntimeError("reference node %s has a transform" % node["name"])
        prim = model["meshes"][node["mesh"]]["primitives"][0]
        if prim.get("mode", 4) != 4:
            raise RuntimeError("reference node %s is not triangles" % node["name"])
        pos = accessor(prim["attributes"]["POSITION"]).astype(np.float64)
        idx = accessor(prim["indices"]).reshape(-1, 3).astype(np.int64)
        out[node["name"]] = (np.stack([pos[:, 0], -pos[:, 2], pos[:, 1]], axis=1), idx)
    missing = sorted(set(node_names) - set(out))
    if missing:
        raise RuntimeError("reference nodes missing: %s" % missing)
    return out


def reference_votes(obj, ref_pos, ref_idx, max_dist):
    """Per face of `obj` (source frame): mean of sign(dot(face normal, nearest reference triangle normal)) over
    the face centre and its corners pulled 10 % toward the centre, in [-1, 1] (0 when nothing is in reach)."""
    bvh = BVHTree.FromPolygons([tuple(p) for p in ref_pos], [tuple(t) for t in ref_idx], all_triangles=True, epsilon=0.0)
    votes, unmatched = [], 0
    mesh = obj.data
    for p in mesh.polygons:
        c = p.center
        samples = [c] + [c + (mesh.vertices[v].co - c) * 0.9 for v in p.vertices]
        vote = matched = 0
        for s in samples:
            loc, nrm, _i, dist = bvh.find_nearest(s, max_dist)
            if loc is None:
                continue
            matched += 1
            vote += 1 if p.normal.dot(nrm) >= 0 else -1
        if not matched:
            unmatched += 1
        votes.append(vote / matched if matched else 0.0)
    conf = [abs(v) for v in votes]
    return votes, {"faces": len(mesh.polygons), "raw_vote_to_flip": sum(1 for v in votes if v < 0),
                   "unmatched_faces": unmatched,
                   "unanimous_share": r(sum(1 for c in conf if c == 1.0) / max(len(conf), 1), 4),
                   "reference_triangles": int(len(ref_idx))}


def smooth_orientation(mesh, votes, lam, iterations):
    """ICM over faces: o_f in {+1 keep, -1 flip} minimising sum_f |vote_f| [o_f disagrees with the vote] +
    lam * #inconsistent manifold edges; starts from the raw vote. Returns (faces to flip, stats)."""
    edge = defaultdict(list)
    for p in mesh.polygons:
        vs = list(p.vertices)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            edge[tuple(sorted((a, b)))].append((p.index, (a, b)))
    pairs = [(v[0][0], v[1][0], v[0][1] == v[1][1]) for v in edge.values() if len(v) == 2]
    nbr = defaultdict(list)
    for fa, fb, same in pairs:
        nbr[fa].append((fb, same))
        nbr[fb].append((fa, same))

    def inconsistent(o):
        return sum(1 for fa, fb, same in pairs if same != (o[fa] != o[fb]))

    raw = [-1 if v < 0 else 1 for v in votes]
    o = list(raw)
    sweeps = 0
    for sweeps in range(1, iterations + 1):
        changed = 0
        for f in range(len(o)):
            best = None
            for cand in (1, -1):
                data = abs(votes[f]) * (1 if (cand == -1) != (votes[f] < 0) else 0)
                smooth = sum(lam for g, same in nbr[f] if same != (cand != o[g]))
                energy = data + smooth
                if best is None or energy < best[0] - 1e-12:
                    best = (energy, cand)
            if best[1] != o[f]:
                o[f] = best[1]
                changed += 1
        if not changed:
            break
    return {i for i, v in enumerate(o) if v == -1}, {
        "lambda": lam, "sweeps": sweeps, "manifold_edges": len(pairs),
        "inconsistent_as_imported": inconsistent([1] * len(o)), "inconsistent_raw_vote": inconsistent(raw),
        "inconsistent_after_smoothing": inconsistent(o), "changed_vs_raw_vote": sum(1 for a, b in zip(o, raw) if a != b),
        "flipped": sum(1 for v in o if v == -1)}
