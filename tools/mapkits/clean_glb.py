"""Credit-free geometry clean-up of a Tripo map-kit prop GLB: drop small detached shells, turn inverted faces outward.

    python tools/mapkits/clean_glb.py <file.glb>                       # dry run: shell table + what would change
    python tools/mapkits/clean_glb.py <file.glb> --apply [--normals]   # rewrite the GLB in place
    python tools/mapkits/clean_glb.py <file.glb> --drop 9,12 --keep 3  # explicit shell ids (from the dry-run table)

Runs on <run>/source/<ID>.glb before tools/art/env_kit (which by policy never repairs geometry), like level_glb.py.
Through `tripo_intake.py clean <map> <key>...` it also backs the raw GLB up (source/<ID>.pre-clean.glb), re-hashes the
source in reports/tripo-run.json and notes the change in status.json.

Shells are found as env_kit's shell_hole_stats does: vertices welded at 1e-6 of the source unit, faces joined across a
shared welded edge. A shell other than the largest is dropped when its area is at most --max-area-frac of the whole
surface AND (its gap to the nearest other shell is at least --min-gap of the bounds diagonal, or it has at most
--tiny-tris triangles, off by default: hard-surface props have many small rivets and knobs). With --vs-main the gap
is measured to the largest shell only (a crown of separate foliage clumps). That catches a floating fragment ("висящий осколок", "loose part", "игла") and confetti of
leaf cards, and keeps branch stubs or bolts that sit in a small gap next to the body. --drop / --keep override it.

--normals turns inward faces outward. A face is inward by env_kit's facing_stats rule (7+7 rays in a 50 deg cone
around +/-normal from the face centre; inward = the back side escapes >= 2 more rays than the front and >= 2), here in
numpy. Its winding is reversed and its corner normals negated. Independently, corner normals (glTF NORMAL, imported
by Blender as custom split normals) that point against their face's winding are negated, so shading agrees with the
face ("custom split normals из исходника Tripo"). A vertex shared by a changed and an unchanged face is duplicated.

--orient <shells> makes the winding of an open card consistent across its edges (the ray test calls every face of a
card a 'sheet'); the side with more area keeps its winding and corner normals follow. --renormal <shells> replaces the Tripo corner normals of a shell with normals from its geometry (area-weighted,
split at folds over 60 deg): a two-layer card whose back triangles end on front vertices otherwise shades dark
wedges. --double <shells> gives a one-sided card (banner, cloth) a back layer with reversed winding and negated normals, so its
back is lit like its face. --drop-below <f> cuts a ragged skirt at the ground with a horizontal plane at f of the
height (vertices below are lifted onto it, faces left flat on it are dropped); env_kit then seats the prop on the cut.

Only the POSITION / NORMAL / TEXCOORD_0 / indices buffer views are rebuilt (unused vertices dropped); the textures
and the root node transform (level_glb rotation) stay byte-identical. The result goes into the GLB's
extras.mapkitClean. Texture repaint, sculpting, hole filling and re-meshing are out of scope.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from level_glb import read_glb, write_glb  # noqa: E402

WELD = 1e-6
DTYPES = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


# ----------------------------------------------------------------------------- GLB access
def _prim(j: dict) -> dict:
    prims = [pr for m in j["meshes"] for pr in m["primitives"]]
    if len(prims) != 1 or prims[0].get("mode", 4) != 4 or "indices" not in prims[0]:
        raise SystemExit("ERROR expected one indexed triangle primitive (Tripo Smart Mesh export)")
    if "extensions" in prims[0] or "targets" in prims[0]:
        raise SystemExit("ERROR primitive has extensions / morph targets: clean it by hand")
    return prims[0]


def _read(j: dict, binary: bytes, acc_i: int) -> np.ndarray:
    a = j["accessors"][acc_i]
    bv = j["bufferViews"][a["bufferView"]]
    if bv.get("byteStride"):
        raise SystemExit("ERROR interleaved buffer view: not supported")
    dt, n = DTYPES[a["componentType"]], NCOMP[a["type"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    arr = np.frombuffer(binary, dtype=dt, count=a["count"] * n, offset=off).copy()
    return arr.reshape(a["count"], n) if n > 1 else arr


def load(p: Path) -> tuple[dict, bytes, dict]:
    j, binary = read_glb(p)
    pr = _prim(j)
    attrs = {k: _read(j, binary, i) for k, i in pr["attributes"].items()}
    idx = _read(j, binary, pr["indices"]).astype(np.int64).reshape(-1, 3)
    return j, binary, {"attrs": attrs, "idx": idx}


def save(p: Path, j: dict, binary: bytes, attrs: dict, idx: np.ndarray, extras: dict) -> None:
    """Rebuild the binary chunk: every buffer view in order, the mesh ones replaced by the new arrays."""
    pr = _prim(j)
    new = {}
    for k, i in pr["attributes"].items():
        new[j["accessors"][i]["bufferView"]] = (i, np.ascontiguousarray(attrs[k], dtype=DTYPES[j["accessors"][i]["componentType"]]))
    ia = pr["indices"]
    j["accessors"][ia]["componentType"] = 5125
    new[j["accessors"][ia]["bufferView"]] = (ia, np.ascontiguousarray(idx.reshape(-1), dtype=np.uint32))
    out = bytearray()
    for bi, bv in enumerate(j["bufferViews"]):
        if bv.get("buffer", 0) != 0:
            raise SystemExit("ERROR external buffers not supported")
        out += b"\0" * ((4 - len(out) % 4) % 4)
        if bi in new:
            ai, arr = new[bi]
            data = arr.tobytes()
            a = j["accessors"][ai]
            a["byteOffset"] = 0
            a["count"] = int(arr.shape[0])
            if a["type"] != "SCALAR" or ai == ia:
                flat = arr.reshape(arr.shape[0], -1)
                a["min"] = [float(v) if arr.dtype.kind == "f" else int(v) for v in flat.min(0)]
                a["max"] = [float(v) if arr.dtype.kind == "f" else int(v) for v in flat.max(0)]
        else:
            o = bv.get("byteOffset", 0)
            data = binary[o:o + bv["byteLength"]]
        bv["byteOffset"] = len(out)
        bv["byteLength"] = len(data)
        out += data
    j["buffers"][0]["byteLength"] = len(out)
    j.setdefault("extras", {})["mapkitClean"] = extras
    write_glb(p, j, bytes(out))


# ----------------------------------------------------------------------------- shells
def weld(pos: np.ndarray) -> np.ndarray:
    """Welded vertex id per stored vertex (positions equal at WELD)."""
    q = np.round(pos / WELD).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    return inv.reshape(-1)


def shells(idx: np.ndarray, wid: np.ndarray) -> np.ndarray:
    """Shell id per face: faces joined across a shared welded edge (env_kit shell_hole_stats), 0 = most faces."""
    f = wid[idx]
    nf = len(f)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    e.sort(axis=1)
    fi = np.tile(np.arange(nf), 3)
    _, einv = np.unique(e, axis=0, return_inverse=True)
    einv = einv.reshape(-1)
    order = np.argsort(einv, kind="stable")
    es, fs = einv[order], fi[order]
    same = es[1:] == es[:-1]
    a, b = fs[:-1][same], fs[1:][same]
    g = coo_matrix((np.ones(len(a)), (a, b)), shape=(nf, nf))
    _, lab = connected_components(g, directed=False)
    counts = np.bincount(lab)
    rank = np.empty_like(counts)
    rank[np.argsort(-counts, kind="stable")] = np.arange(len(counts))
    return rank[lab]


def tri_area(v: np.ndarray) -> np.ndarray:
    return 0.5 * np.linalg.norm(np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1)


def shell_table(pos: np.ndarray, idx: np.ndarray, sh: np.ndarray) -> tuple[list[dict], float]:
    tv = pos[idx]
    area = tri_area(tv)
    total = float(area.sum()) or 1.0
    diag = float(np.linalg.norm(pos[idx.reshape(-1)].max(0) - pos[idx.reshape(-1)].min(0))) or 1.0
    ground = float(pos[idx.reshape(-1), 1].min())
    vs_of = [np.unique(idx[sh == s].reshape(-1)) for s in range(int(sh.max()) + 1)]
    main = cKDTree(pos[vs_of[0]])
    rows = []
    for s, vs in enumerate(vs_of):
        others = np.concatenate([v for k, v in enumerate(vs_of) if k != s]) if len(vs_of) > 1 else np.empty(0, int)
        gap = float(cKDTree(pos[others]).query(pos[vs])[0].min()) if len(others) else math.inf
        lo, hi = pos[vs].min(0), pos[vs].max(0)
        gm = main.query(pos[vs])[0] if s else np.zeros(1)
        fs = sh == s
        sv = float(np.einsum("ij,ij->i", tv[fs, 0], np.cross(tv[fs, 1], tv[fs, 2])).sum() / 6.0)
        rows.append({"shell": s, "triangles": int(fs.sum()), "area_frac": float(area[fs].sum() / total),
                     "gap_rel": gap / diag, "gap_main_rel": float(gm.min()) / diag,
                     "gap_main_mean_rel": float(gm.mean()) / diag, "off_ground_rel": float(lo[1] - ground) / diag,
                     "size_rel": float(np.linalg.norm(hi - lo)) / diag, "signed_volume": sv,
                     "centre": [round(float(c), 4) for c in (lo + hi) / 2]})
    return rows, diag


def pick_drop(rows: list[dict], max_area_frac: float, min_gap: float, tiny_tris: int,
              drop: set[int], keep: set[int], vs_main: bool = False) -> list[int]:
    out = []
    for r in rows:
        s = r["shell"]
        if s in keep or s == 0:
            continue
        gap = r["gap_main_rel"] if vs_main else r["gap_rel"]
        auto = r["area_frac"] <= max_area_frac and (gap >= min_gap or r["triangles"] <= tiny_tris)
        if s in drop or auto:
            out.append(s)
    return out


# ----------------------------------------------------------------------------- facing (numpy port of env_kit facing_stats)
def _any_hit(orig: np.ndarray, d: np.ndarray, v0: np.ndarray, e1: np.ndarray, e2: np.ndarray, chunk: int = 96) -> np.ndarray:
    """Möller-Trumbore: True where the ray hits any triangle at t > 0."""
    hit = np.zeros(len(orig), dtype=bool)
    for a in range(0, len(orig), chunk):
        o, dd = orig[a:a + chunk, None, :], d[a:a + chunk, None, :]
        pv = np.cross(dd, e2[None])
        det = np.einsum("rtk,tk->rt", pv, e1)
        ok = np.abs(det) > 1e-14
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = o - v0[None]
        u = np.einsum("rtk,rtk->rt", tv, pv) * inv
        qv = np.cross(tv, e1[None])
        v = np.einsum("rtk,rk->rt", qv, d[a:a + chunk]) * inv
        t = np.einsum("rtk,tk->rt", qv, e2) * inv
        h = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-12)
        hit[a:a + chunk] = h.any(1)
    return hit


def facing(pos: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Per face: 'outward' | 'inward' | 'sheet' | 'enclosed' | 'degenerate' (env_kit facing_stats rule)."""
    tv = pos[idx].astype(np.float64)
    v0, e1, e2 = tv[:, 0], tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0]
    n = np.cross(e1, e2)
    ln = np.linalg.norm(n, axis=1)
    good = ln > 1e-14
    n = n / np.where(good, ln, 1.0)[:, None]
    c = tv.mean(1)
    diag = float(np.linalg.norm(pos.max(0) - pos.min(0))) or 1.0
    eps = diag * 1e-5
    helper = np.where(np.abs(n[:, :1]) < 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]]))
    t = np.cross(n, helper)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    b = np.cross(n, t)
    ca, sa = math.cos(math.radians(50)), math.sin(math.radians(50))
    ring = [(math.cos(k * math.pi / 3), math.sin(k * math.pi / 3)) for k in range(6)]
    fi = np.nonzero(good)[0]
    esc = np.zeros((len(idx), 2), dtype=int)
    for si, sgn in enumerate((1.0, -1.0)):
        m = n[fi] * sgn
        dirs = [m] + [m * ca + (t[fi] * x + b[fi] * y) * sa for x, y in ring]
        for d in dirs:
            d = d / np.linalg.norm(d, axis=1, keepdims=True)
            esc[fi, si] += ~_any_hit(c[fi] + d * eps, d, v0, e1, e2)
    ep, em = esc[:, 0], esc[:, 1]
    cls = np.select([~good, (ep >= 4) & (em >= 4), (em - ep >= 2) & (em >= 2), (ep >= 2) & (ep >= em),
                     (ep < 2) & (em < 2), ep >= em],
                    ["degenerate", "sheet", "inward", "outward", "enclosed", "outward"], "inward")
    return cls.astype(object)


def split_normals(pos: np.ndarray, faces: np.ndarray, cos_split: float = 0.5) -> np.ndarray:
    """Corner normals (n_faces, 3, 3) recomputed from the geometry: the area-weighted sum of the normals of the faces
    around the corner's welded vertex that point within acos(cos_split) of this face (a split at sharper folds)."""
    tv = pos[faces]
    fn = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])  # length = 2 * area
    fu = fn / (np.linalg.norm(fn, axis=1, keepdims=True) + 1e-30)
    wid = weld(pos)[faces]
    around: dict[int, list[int]] = {}
    for fi, tri in enumerate(wid):
        for w in tri:
            around.setdefault(int(w), []).append(fi)
    out = np.empty((len(faces), 3, 3))
    for fi, tri in enumerate(wid):
        for c, w in enumerate(tri):
            g = np.array(around[int(w)])
            g = g[fu[g] @ fu[fi] > cos_split]
            n = fn[g].sum(0)
            out[fi, c] = n / (np.linalg.norm(n) + 1e-30)
    return out


def orient_flips(idx: np.ndarray, wid: np.ndarray, area: np.ndarray) -> np.ndarray:
    """Faces to flip so that winding is consistent across shared manifold edges (BFS per edge-connected region); in
    each region the orientation with more area keeps its winding. For open cards (banners), where the ray test calls
    every face a 'sheet' and cannot tell front from back."""
    f = wid[idx]
    nf = len(f)
    de = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    fi = np.tile(np.arange(nf), 3)
    key = np.sort(de, axis=1)
    _, einv = np.unique(key, axis=0, return_inverse=True)
    einv = einv.reshape(-1)
    fwd = de[:, 0] < de[:, 1]
    order = np.argsort(einv, kind="stable")
    cnt = np.bincount(einv)
    nbr = [[] for _ in range(nf)]
    start = np.concatenate([[0], np.cumsum(cnt)])
    for e in np.nonzero(cnt == 2)[0]:
        a, b = order[start[e]], order[start[e] + 1]
        same = fwd[a] == fwd[b]  # both faces walk the edge the same way: windings disagree
        nbr[fi[a]].append((fi[b], same))
        nbr[fi[b]].append((fi[a], same))
    par = np.full(nf, -1, dtype=np.int8)
    out = np.zeros(nf, dtype=bool)
    for s0 in range(nf):
        if par[s0] >= 0:
            continue
        par[s0] = 0
        comp, stack = [s0], [s0]
        while stack:
            x = stack.pop()
            for y, same in nbr[x]:
                if par[y] < 0:
                    par[y] = par[x] ^ int(same)
                    comp.append(y)
                    stack.append(y)
        comp = np.array(comp)
        p1 = par[comp] == 1
        out[comp] = p1 if area[comp][p1].sum() <= area[comp][~p1].sum() else ~p1
    return out


# ----------------------------------------------------------------------------- clean
def clean(p: Path, apply: bool = False, normals: bool = False, max_area_frac: float = 0.002, min_gap: float = 0.02,
          tiny_tris: int = 0, drop: set[int] | None = None, keep: set[int] | None = None,
          vs_main: bool = False, double: set[int] | None = None, drop_below: float = 0.0,
          orient: set[int] | None = None, renormal: set[int] | None = None) -> dict:
    j, binary, m = load(p)
    if j.get("extras", {}).get("mapkitClean"):
        return {**j["extras"]["mapkitClean"], "note": "already cleaned (restore the .pre-clean.glb to redo)"}
    attrs, idx = m["attrs"], m["idx"]
    pos = attrs["POSITION"].astype(np.float64)
    sh = shells(idx, weld(pos))
    rows, diag = shell_table(pos, idx, sh)
    gone = pick_drop(rows, max_area_frac, min_gap, tiny_tris, drop or set(), keep or set(), vs_main)
    keep_f = ~np.isin(sh, gone)
    res_low = lifted = 0
    if drop_below > 0:
        # ragged skirt at the ground: cut with a horizontal plane at drop_below of the height (vertices below it are
        # lifted onto it, faces left flat on the plane are dropped). env_kit puts the pivot at the new min Z, so the
        # prop is re-seated on the straight cut edge
        used = idx[keep_f].reshape(-1)
        lo_y = float(pos[used, 1].min())
        cut = lo_y + drop_below * (float(pos[used, 1].max()) - lo_y)
        lifted = int((pos[np.unique(used), 1] < cut).sum())
        pos = pos.copy()
        pos[:, 1] = np.maximum(pos[:, 1], cut)
        attrs["POSITION"] = pos.astype(attrs["POSITION"].dtype)
        flat = (pos[idx][:, :, 1] <= cut).all(1)
        res_low = int((flat & keep_f).sum())
        keep_f &= ~flat
    res = {"rule": {"max_area_frac": max_area_frac, "min_gap_rel_diag": min_gap, "tiny_tris": tiny_tris, "orient": sorted(orient or []), "renormal": sorted(renormal or []),
                    "gap_to": "main shell" if vs_main else "nearest other shell", "drop": sorted(drop or []), "keep": sorted(keep or []), "weld": WELD},
           "triangles_before": int(len(idx)), "shells_before": len(rows),
           "dropped_shells": [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in rows[s].items()} for s in gone],
           "dropped_triangles": int((~keep_f).sum()),  # shells and --drop-below together
           "dropped_area_frac": round(float(sum(rows[s]["area_frac"] for s in gone)), 6),
           "drop_below_rel_height": drop_below, "dropped_triangles_below": res_low,
           "cut_vertices_lifted": lifted}
    idx2 = idx[keep_f].copy()
    flip = np.zeros(len(idx2), dtype=bool)
    nflip_corner = np.zeros(len(idx2), dtype=bool)
    if normals:
        cls = facing(pos, idx2)
        flip = cls == "inward"
        res["facing_before"] = {k: int((cls == k).sum()) for k in ("outward", "inward", "sheet", "enclosed", "degenerate")}
    if orient:
        sel = np.isin(sh[keep_f], sorted(orient))
        fl = np.zeros(len(idx2), dtype=bool)
        fl[sel] = orient_flips(idx2[sel], weld(pos), tri_area(pos[idx2[sel]]))
        flip ^= fl
        res["faces_flipped_to_consistent_winding"] = int(fl.sum())
    if "NORMAL" in attrs and (normals or orient):
        # corner normals against the face winding (after the flips above)
        tv = pos[idx2]
        fn = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])
        fn[flip] *= -1
        cn = attrs["NORMAL"][idx2].astype(np.float64).sum(1)
        cn[flip] *= -1
        nflip_corner = np.einsum("ij,ij->i", fn, cn) < 0
    neg = flip ^ nflip_corner  # faces whose corner normals end up negated
    res.update({"faces_flipped_inward_to_outward": int(flip.sum()),
                "faces_corner_normals_negated_to_match_winding": int(nflip_corner.sum()),
                "normals": normals})
    # vertex table: (old vertex, negated?) -> new vertex
    key = idx2 * 2 + neg[:, None].astype(np.int64)
    uk, inv = np.unique(key.reshape(-1), return_inverse=True)
    src_v, src_neg = uk // 2, (uk % 2).astype(bool)
    new_attrs = {}
    for k, a in attrs.items():
        na = a[src_v].copy()
        if k == "NORMAL":
            na[src_neg] *= -1
        new_attrs[k] = na
    new_idx = inv.reshape(-1, 3)
    new_idx[flip] = new_idx[flip][:, [0, 2, 1]]
    if renormal:
        # Tripo custom normals across a two-layer card: a back-layer triangle that ends on a front-layer vertex
        # interpolates its normal from back to front and shades a dark wedge. Every corner of these shells gets its
        # own vertex with a normal from the geometry, split at folds sharper than 60 deg
        sel = np.nonzero(np.isin(sh[keep_f], sorted(renormal)))[0]
        cn = split_normals(new_attrs["POSITION"].astype(np.float64), new_idx[sel])
        base = len(src_v)
        corners = new_idx[sel].reshape(-1)
        for k in new_attrs:
            extra = new_attrs[k][corners].copy()
            if k == "NORMAL":
                extra = cn.reshape(-1, 3).astype(extra.dtype)
            new_attrs[k] = np.concatenate([new_attrs[k], extra])
        new_idx[sel] = (base + np.arange(len(corners))).reshape(-1, 3)
        src_v = np.concatenate([src_v, src_v[corners]])
        res["faces_renormalled"] = int(len(sel))
    dbl = sorted(double or [])
    if dbl:
        # a one-sided card (banner, sheet) seen from behind shades dark: add a back layer, reversed winding and
        # negated corner normals, same UVs (the back shows the front's paint)
        sel = np.isin(sh[keep_f], dbl)
        base = len(src_v)
        bv = np.unique(new_idx[sel].reshape(-1))
        remap = np.full(base, -1, dtype=np.int64)
        remap[bv] = base + np.arange(len(bv))
        for k in new_attrs:
            extra = new_attrs[k][bv].copy()
            if k == "NORMAL":
                extra *= -1
            new_attrs[k] = np.concatenate([new_attrs[k], extra])
        back = remap[new_idx[sel]][:, [0, 2, 1]]
        new_idx = np.concatenate([new_idx, back])
        src_v = np.concatenate([src_v, src_v[bv]])
    res.update({"doubled_shells": dbl, "doubled_triangles": int(len(new_idx) - int(keep_f.sum()))})
    res.update({"triangles_after": int(len(new_idx)), "vertices_before": int(len(pos)),
                "vertices_after": int(len(src_v)), "applied": bool(apply)})
    if apply and (gone or res_low or dbl or orient or renormal or flip.any() or nflip_corner.any()):
        save(p, j, binary, new_attrs, new_idx, res)
    elif apply:
        res["applied"] = False
        res["note"] = "nothing to change"
    res["shells"] = [{k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]
    return res


def _ids(s: str | None) -> set[int]:
    return {int(x) for x in s.split(",") if x.strip()} if s else set()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("glb", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--normals", action="store_true")
    ap.add_argument("--max-area-frac", type=float, default=0.002)
    ap.add_argument("--min-gap", type=float, default=0.02)
    ap.add_argument("--tiny-tris", type=int, default=0)
    ap.add_argument("--vs-main", action="store_true", help="measure the gap to the largest shell, not to any other")
    ap.add_argument("--orient", help="shell ids whose winding is made consistent across edges (open cards)")
    ap.add_argument("--renormal", help="shell ids whose corner normals are recomputed from the geometry")
    ap.add_argument("--double", help="shell ids to give a reversed back layer (one-sided cards)")
    ap.add_argument("--drop-below", type=float, default=0.0, help="cut the bottom with a plane at this fraction of the height")
    ap.add_argument("--drop"); ap.add_argument("--keep")
    a = ap.parse_args()
    print(json.dumps(clean(a.glb, a.apply, a.normals, a.max_area_frac, a.min_gap, a.tiny_tris, _ids(a.drop), _ids(a.keep),
                           a.vs_main, _ids(a.double), a.drop_below, _ids(a.orient), _ids(a.renormal)),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
