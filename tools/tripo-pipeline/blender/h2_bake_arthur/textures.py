"""Stage textures (system python: numpy, Pillow, scipy): baked passes -> BC / N / N_OpenGL / ORM / TeamMask, 4K + 2K.

    python textures.py <profile.json> <run_dir>

Inputs: work/bake/{NORMAL,AO,BC,MR,HIT,POS}.npy (stage bake), work/uv-part-id.npy + work/uv-triangles.npz (uvcheck),
work/phantom-points.npy (stage lowpoly).
  valid texel   HIT > 0.5 (ray found the high part; the bake margin already extended it 8 px)
  misses        covered texels (UV raster) without a hit, counted per part and split in two:
                  phantom misses: 8-connected miss clusters of a repaint part whose nearest texel lies within
                    phantom_repaint.miss_clusters.max_phantom_dist_m of a phantom vertex (the filled holes and the
                    smoothed strip: there is no high-poly surface, the bake has nothing to give) -> repainted, weight 1
                  other misses: take the nearest valid texel of their OWN UV island (EDT per island; an island
                    without a hit takes the nearest valid texel of the same part in 3D, POS) - never another island
  repaint       phantom zone (mirror donor), phantom misses + feather ring and boxes (mirror_cloth or plain donor)
  cleanup       (H2.1, phantom_repaint.cloth_cleanup) residue boxes of the cloak: non-band texels take the clean
                cloth chromaticity with their own luminance clamped to the clean cloth range (cloth_cleanup)
  fill          gutters and the empty atlas take the nearest covered texel (full dilation: clean mips, no black seams)
  materials     (H2.1, textures.materials; materials.py) metal mask by part group + colour rules + regions; metal
                texels get a PBR base colour (steel neutral grey, gold) and steel/gold roughness, non-metal keeps the
                painted colour with the Tripo roughness clamped per class; the TeamMask colour rule and the residue
                check read the painted colour (before this pass)
  BC            linear -> sRGB 8-bit
  N_OpenGL      decode 2c-1, renormalise, encode (Blender/OpenGL, +Y up); N = DirectX for UE (green inverted)
  ORM           R = AO, G = roughness, B = metallic (material pass; without it Tripo MR.G / MR.B), linear 8-bit
  TeamMask      RGBA 8-bit linear: R = cloth (cloth parts AND the cloth colour rule; soft edge = normalised Gaussian
                convolution inside the cloth parts' coverage, gauss(cloth * cov) / gauss(cov), then the same atlas
                fill as BC, so an island edge keeps its own value in every mip), G = base band (side wall of the base,
                |normal z| < normal_z_max, same fill), B = 0, A = 255
  2K runtime    2x2 box average of the float 4K data (normals renormalised), then the same encoding
Measured checks (reports/textures-report.json): the miss fill never crosses an island; TeamMask R of the edge row of
the cloth islands vs their interior on the 2K runtime mask, mip0-mip3; colour residue (grey/dark, gold) of the cloak
in the phantom misses and near the phantoms vs the mirrored clean side.
Deterministic: numpy + PIL PNG (compress_level fixed, no metadata).
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import materials as M  # noqa: E402
import pure as P  # noqa: E402
import uvcheck  # noqa: E402


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def q8(x):
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def save_png(arr, path, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, mode).save(path, format="PNG", compress_level=6)
    return {"file": P.rel(path), "sha256": P.sha256(path), "bytes": path.stat().st_size,
            "px": [int(arr.shape[1]), int(arr.shape[0])]}


def nearest_fill(arr, valid):
    """Every invalid texel takes the value of the nearest valid texel (EDT indices; ties resolved by scipy)."""
    _d, (iy, ix) = ndimage.distance_transform_edt(~valid, return_indices=True)
    return arr[iy, ix]


def box2(x):
    h, w = x.shape[:2]
    return x.reshape(h // 2, 2, w // 2, 2, *x.shape[2:]).mean(axis=(1, 3))


def normals_encode(n):
    v = n * 2.0 - 1.0
    ln = np.linalg.norm(v, axis=-1, keepdims=True)
    v = v / np.maximum(ln, 1e-8)
    return v * 0.5 + 0.5


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rm = m & (mx == r)
    gm = m & (mx == g) & ~rm
    bm = m & ~rm & ~gm
    h[rm] = ((g[rm] - b[rm]) / d[rm]) % 6
    h[gm] = (b[gm] - r[gm]) / d[gm] + 2
    h[bm] = (r[bm] - g[bm]) / d[bm] + 4
    h = h * 60.0
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    return h, s, mx


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def colour_classes(bc_lin, rule):
    """sRGB HSV classes of linear BC texels: cloth (the TeamMask colour rule), gold, grey/dark (steel, black)."""
    h, s, v = rgb_to_hsv(srgb(bc_lin))
    hue_ok = (h >= float(rule["hue_min_deg"])) | (h <= float(rule["hue_max_deg"]))
    cloth = hue_ok & (s >= float(rule["s_min"])) & (v >= float(rule["v_min"])) & (v <= float(rule["v_max"]))
    gold = (h >= 20.0) & (h <= 60.0) & (s >= 0.3) & (v >= 0.25)
    grey_dark = (s < 0.35) | (v < 0.08)
    return cloth, gold, grey_dark


def island_fill(maps, valid, targets, isl, pid, pos):
    """Every target texel takes the nearest valid texel of its own UV island (EDT inside the island's bounding box,
    sources restricted to the island); an island without any valid texel takes the nearest valid texel of the same
    part in 3D (POS). No texel is ever taken from another island or part."""
    slices = ndimage.find_objects(isl)
    fallback = np.zeros(isl.shape, dtype=bool)
    dists, n_island = [], 0
    for k, sl in enumerate(slices):
        if sl is None:
            continue
        own = isl[sl] == k + 1
        need = targets[sl] & own
        if not need.any():
            continue
        src = valid[sl] & own
        if not src.any():
            fallback[sl] |= need
            continue
        d, (iy, ix) = ndimage.distance_transform_edt(~src, return_indices=True)
        yy, xx = np.nonzero(need)
        ty, tx = yy + sl[0].start, xx + sl[1].start
        sy, sx = iy[yy, xx] + sl[0].start, ix[yy, xx] + sl[1].start
        for a in maps.values():
            a[ty, tx] = a[sy, sx]
        dists.append(d[yy, xx])
        n_island += len(yy)
    n_3d = 0
    for part_index in np.unique(pid[fallback]):
        need = fallback & (pid == part_index)
        src = valid & (pid == part_index)
        _dd, j = cKDTree(pos[src]).query(pos[need], k=1)
        sy, sx = np.nonzero(src)
        ty, tx = np.nonzero(need)
        for a in maps.values():
            a[ty, tx] = a[sy[j], sx[j]]
        n_3d += len(ty)
    d = np.concatenate(dists) if dists else np.zeros(1)
    return {"texels": int(targets.sum()), "from_own_island": n_island, "from_same_part_3d": n_3d,
            "uv_distance_px": {"median": P.r(np.median(d), 2), "p95": P.r(np.percentile(d, 95), 2),
                               "max": P.r(d.max(), 2)}}


def phantom_miss_mask(miss, pid, names, pos, phantom, parts, max_dist):
    """8-connected miss clusters (per repaint part) whose nearest texel is within max_dist of a phantom vertex."""
    tree = cKDTree(phantom)
    out = np.zeros(miss.shape, dtype=bool)
    log = {}
    for part in parts:
        m = miss & (pid == names.index(part) + 1)
        if not m.any():
            continue
        lab, n = ndimage.label(m, structure=np.ones((3, 3), dtype=bool))
        dist = np.full(m.shape, np.inf, dtype=np.float64)
        dist[m] = tree.query(pos[m], k=1)[0]
        idx = np.arange(1, n + 1)
        mins = np.asarray(ndimage.minimum(dist, lab, index=idx))
        sizes = np.asarray(ndimage.sum(m, lab, index=idx))
        keep = idx[mins <= max_dist]
        sel = np.isin(lab, keep)
        out |= sel
        log[part] = {"clusters": int(n), "phantom_clusters": int(len(keep)), "phantom_texels": int(sel.sum()),
                     "other_miss_texels": int((m & ~sel).sum()),
                     "largest_phantom_clusters": sorted((int(sizes[k - 1]) for k in keep), reverse=True)[:6]}
    return out, log


def pos_frames(pos):
    """Tangent frame (T, B, N) of the low surface per texel from the POS bake. N = cross(dP/drow, dP/dcol) is the
    outward normal (the islands are not mirrored in UV: 0 flipped triangles, pack without mirroring; the low parts
    are wound outward, stage inspect ray-escape), T = dP/du (= dP/dcol) orthogonalised, B = N x T (= +v). The gutter
    POS comes from the bake margin (adjacent faces). Checked against the baked tangent normals: object-space normals
    of the same surface point seen from two UV islands agree best with this convention (median 12.0 deg vs 15.1 /
    16.1 deg with B or T flipped; review 2026-09-29)."""
    dr = np.gradient(pos, axis=0)
    dc = np.gradient(pos, axis=1)
    n = np.cross(dr, dc)
    n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
    t = dc - (dc * n).sum(axis=-1, keepdims=True) * n
    t = t / np.maximum(np.linalg.norm(t, axis=-1, keepdims=True), 1e-12)
    b = np.cross(n, t)
    return t.astype(np.float32), b.astype(np.float32), n.astype(np.float32)


def transfer_detail_normal(nrm_enc, frames, src, tgt, plane_mirror=True, min_dot=0.2):
    """Tangent normal of the donor texels `src` moved onto the target texels `tgt` as surface detail: donor
    tangent -> object space (donor frame), mirrored in x (the donor lies on the other side of the figure), rotated by
    the minimal rotation that takes the mirrored donor normal onto the target normal (so only the weave / detail
    relief moves, not the donor's fold tilt), -> target tangent space. Texels whose normals disagree
    (dot < min_dot) get the flat normal. Returns encoded [0, 1] normals and the flat-fallback mask."""
    tf, bf, nf = frames
    t = nrm_enc[src] * 2.0 - 1.0
    d = t[:, :1] * tf[src] + t[:, 1:2] * bf[src] + t[:, 2:3] * nf[src]
    nm = nf[src].copy()
    if plane_mirror:
        d[:, 0] = -d[:, 0]
        nm[:, 0] = -nm[:, 0]
    nt = nf[tgt]
    c = np.clip((nm * nt).sum(axis=1), -1.0, 1.0)
    axis = np.cross(nm, nt)
    sn = np.linalg.norm(axis, axis=1)
    k = axis / np.maximum(sn, 1e-12)[:, None]
    # Rodrigues: d cos + (k x d) sin + k (k . d)(1 - cos)
    d = (d * c[:, None] + np.cross(k, d) * sn[:, None] + k * (k * d).sum(axis=1, keepdims=True) * (1 - c)[:, None])
    out = np.stack([(d * tf[tgt]).sum(axis=1), (d * bf[tgt]).sum(axis=1), (d * nt).sum(axis=1)], axis=1)
    out = out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-8)
    bad = (c < min_dot) | (out[:, 2] <= 0)
    out[bad] = (0.0, 0.0, 1.0)
    return (out * 0.5 + 0.5).astype(np.float32), bad


class Donors:
    """Clean donor texels of one part for the mirrored lookup. Metric: Tripo-frame position scaled per axis
    (metric_scale; a small Y weight maps back-facing cloth by its (x, z) projection, so a target whose surface was
    smoothed inward or hangs differently still finds the texel at the same height and width). The scaled metric is
    used only where the target faces along the scaled axis (|n . axis| >= aniso_min_dot): on a fold wall facing
    sideways it would collapse the wall onto a few donors (vertical streaks), so such targets use the plain 3D
    metric. Among the k nearest, the first whose normal faces the mirrored target normal (dot >= facing_min) wins
    (no inner/outer layer swap)."""

    def __init__(self, mask, pos, nrm, scale, facing_min, k=8, aniso_min_dot=0.5):
        self.dy, self.dx = np.nonzero(mask)
        self.scale = np.asarray(scale, dtype=np.float64)
        self.aniso = bool(np.any(self.scale != 1.0))
        self.axis = np.eye(3)[int(np.argmin(self.scale))]
        self.aniso_min_dot = float(aniso_min_dot)
        self.tree = cKDTree(pos[mask] * self.scale)
        self.tree_iso = cKDTree(pos[mask]) if self.aniso else self.tree
        self.nrm = nrm[mask]
        self.facing_min, self.k = float(facing_min), int(min(k, max(1, mask.sum())))
        self.count = int(mask.sum())
        self.last_iso = 0

    def _query(self, tree, q, qn, scale):
        d, j = tree.query(q * scale, k=self.k)
        if self.k == 1:
            d, j = d[:, None], j[:, None]
        facing = (self.nrm[j] * qn[:, None, :]).sum(axis=-1) >= self.facing_min
        first = np.where(facing.any(axis=1), facing.argmax(axis=1), 0)
        rows = np.arange(len(q))
        return d[rows, first], j[rows, first], facing.any(axis=1)

    def query(self, q, qn):
        if not self.aniso:
            self.last_iso = len(q)
            return self._query(self.tree, q, qn, 1.0)
        iso = np.abs(qn @ self.axis) < self.aniso_min_dot
        self.last_iso = int(iso.sum())
        d = np.zeros(len(q))
        j = np.zeros(len(q), dtype=np.int64)
        f = np.zeros(len(q), dtype=bool)
        for rows, tree, sc in ((~iso, self.tree, self.scale), (iso, self.tree_iso, 1.0)):
            if rows.any():
                d[rows], j[rows], f[rows] = self._query(tree, q[rows], qn[rows], sc)
        return d, j, f


def cloth_offset_search(q, qn, any_donors, cloth_flag, search):
    """Shift of the mirrored query along one axis (smallest |shift| first) until the unrestricted donor there is cloth:
    the mirror of the figure is not exact (the left border band lies ~2 cm more central than the right one), so a
    cloth-only donor would otherwise smear the band's edge texel over the column where the mirror lands on the band."""
    axis, step, steps = int(search["axis"]), float(search["step_m"]), int(round(float(search["max_m"]) / float(search["step_m"])))
    offs = [0.0] + [s * step * sign for s in range(1, steps + 1) for sign in (-1, 1)]
    chosen = np.full(len(q), np.nan)
    for o in offs:
        todo = np.isnan(chosen)
        if not todo.any():
            break
        qq = q[todo].copy()
        qq[:, axis] += o
        _d, j, _f = any_donors.query(qq, qn[todo])
        ok = cloth_flag[any_donors.dy[j], any_donors.dx[j]]
        chosen[np.nonzero(todo)[0][ok]] = o
    found = ~np.isnan(chosen)
    shifted = q.copy()
    shifted[:, axis] += np.nan_to_num(chosen, nan=0.0)
    hist = {("%+.0f mm" % (o * 1000)): int((chosen == o).sum()) for o in offs if (chosen == o).any()}
    return shifted, {"shift_histogram": hist, "no_cloth_within_search": int((~found).sum())}


def repaint(raw, pid, names, valid, pos, phantom, rp, cloth_ok, gold_ok, miss_phantom, frames):
    """Phantom repaint (profile textures.phantom_repaint). Three kinds of zones per listed part:
      phantom_zone  covered texels within zone_m of a phantom vertex (Tripo frame), smoothstep over feather_m;
                    donor "mirror": nearest clean texel of the donor part at the mirrored point x' = 2 * plane - x
      phantom_miss  texels of the phantom miss clusters (no high-poly surface), weight 1, plus a smoothstep ring of
                    miss_clusters.feather_m around them (3D); donor miss_clusters.modes[part]
      box_k         manual boxes (Tripo frame), smoothstep over feather_m outside the box; donor box["mode"];
                    box["keep_band"]: hit texels of large gold components keep the Tripo paint (as below)
    Donors: "mirror" (any clean texel of the donor part), "mirror_cloth" (clean texels of the donor part that pass the
    cloth colour rule: the region is red cloth in the concept, and the mirror is not exact, so an unrestricted donor
    brings the border band or the gold tabs of the other side into it), "plain" (median of a clean shell around the
    box). Clean = valid and outside every zone. Mirror lookup: class Donors (per-part metric_scale, facing check);
    mirror_cloth additionally shifts the query off the mirrored border band (cloth_offset_search);
    mirror_cloth_keep_band (phantom zone of the cloak): hit texels of a large gold component of the part (a border
    band crossing the zone, >= band_component_min_texels, dilated 2 px) keep the Tripo paint (weight 0), all other
    zone texels take cloth donors: the other side's band lies ~2 cm off in the mirror and would be stamped next to
    this side's band. The explicit regions (phantom misses, boxes) take precedence over the phantom zone:
    donor = w_e * D_explicit + (1 - w_e) * D_zone, applied with the maximum weight. Normal: with normal_transfer
    "detail" the tangent normal of the mirror donors is moved as surface detail (transfer_detail_normal: the weave
    relief comes along, the donor's fold tilt and the target's phantom imprint do not); plain boxes, disagreeing
    normals and normal_transfer "flat" get the flat normal (the baked one carries the phantom imprint or is missing)."""
    tree = cKDTree(phantom)
    zone, feather, plane = float(rp["zone_m"]), float(rp["feather_m"]), float(rp["mirror_plane_x_m"])
    mc = rp.get("miss_clusters", {})
    miss_feather = float(mc.get("feather_m", feather))
    # large gold components (border bands) of each repaint part, on hit texels, dilated 2 px inside the part
    gold_band = np.zeros(pid.shape, dtype=bool)
    band_min = int(rp.get("band_component_min_texels", 2000))
    for part in rp["parts"]:
        pm_ = pid == names.index(part) + 1
        gl, _n = ndimage.label(pm_ & gold_ok & valid, structure=np.ones((3, 3), dtype=bool))
        sizes = np.bincount(gl.ravel())
        sizes[0] = 0
        gold_band |= ndimage.binary_dilation(sizes[gl] >= band_min, iterations=2) & pm_ & valid
    per_part = {}
    kept_band = {}
    for part in rp["parts"]:
        m = pid == names.index(part) + 1
        pm = pos[m]
        d = tree.query(pm, k=1)[0]
        pz_mode = rp.get("phantom_zone_modes", {}).get(part, "mirror")
        wz = smoothstep((zone - d) / feather)
        if pz_mode == "mirror_cloth_keep_band":
            keep = gold_band[m] & (wz > 0)
            kept_band[part] = int(keep.sum())
            wz = np.where(keep, 0.0, wz)
            pz_mode = "mirror_cloth"
        kinds = {"phantom_zone": (pz_mode, wz, None, None)}
        mm = miss_phantom[m]
        if mm.any():
            dm = cKDTree(pm[mm]).query(pm, k=1, distance_upper_bound=miss_feather * 1.5)[0]
            wm = smoothstep((miss_feather - np.minimum(dm, 1.0)) / miss_feather)
            wm[mm] = 1.0
            kinds["phantom_miss"] = (mc.get("modes", {}).get(part, "mirror"), wm, None, None)
        for k, box in enumerate(b for b in rp.get("boxes", []) if b["part"] == part):
            lo, hi = np.array(box["min_m"]), np.array(box["max_m"])
            out = np.linalg.norm(np.maximum(np.maximum(lo - pm, pm - hi), 0.0), axis=1)
            wb = smoothstep((feather - out) / feather)
            if box.get("keep_band"):
                keep = gold_band[m] & (wb > 0)
                kept_band["%s/box_%d" % (part, k)] = int(keep.sum())
                wb = np.where(keep, 0.0, wb)
            kinds["box_%d" % k] = (box.get("mode", "plain"), wb, box, out)
        per_part[part] = (m, kinds)
    in_zone = np.zeros(pid.shape, dtype=bool)
    for m, kinds in per_part.values():
        wmax = np.zeros(int(m.sum()), dtype=np.float32)
        for kd in kinds.values():
            wmax = np.maximum(wmax, kd[1])
        z = np.zeros(pid.shape, dtype=bool)
        z[m] = wmax > 0
        in_zone |= z
    flat = np.array([0.5, 0.5, 1.0], dtype=np.float32)
    nrm = frames[2]
    detail = rp.get("normal_transfer", "flat") == "detail"
    facing_min = float(rp.get("donor_facing_min_dot", -2.0))
    log = {}
    for part, (m, kinds) in per_part.items():
        donor = rp["donor_parts"][part]
        dmask = (pid == names.index(donor) + 1) & ~in_zone & valid
        scale = rp.get("donor_metric_scale", {}).get(part, [1.0, 1.0, 1.0])
        q = pos[m].copy()
        q[:, 0] = 2 * plane - q[:, 0]
        qn = nrm[m].copy()
        qn[:, 0] = -qn[:, 0]
        n = int(m.sum())
        # explicit regions (phantom misses, boxes) override the generic phantom zone where they reach weight 1:
        # donor = w_e * D_explicit + (1 - w_e) * D_zone (each D a weight-normalised mix of its kinds)
        keys = ("BC", "AO", "MR", "NORMAL")
        acc = {grp: {key: np.zeros((n, raw[key].shape[-1]), dtype=np.float32) for key in keys}
               for grp in ("zone", "explicit")}
        mrows, mcols = np.nonzero(m)
        wsum = {grp: np.zeros(n, dtype=np.float32) for grp in acc}
        wgrp = {grp: np.zeros(n, dtype=np.float32) for grp in acc}
        wmax = np.zeros(n, dtype=np.float32)
        plog, donors = {}, {}
        for kname, (mode, w, box, out) in kinds.items():
            grp = "zone" if kname == "phantom_zone" else "explicit"
            sel = w > 0
            entry = {"mode": mode, "texels": int(sel.sum()), "full_weight_texels": int((w >= 1).sum())}
            if sel.any():
                if mode in ("mirror", "mirror_cloth"):
                    for dmode in ("mirror", mode):
                        if dmode not in donors:
                            dm = dmask & cloth_ok if dmode == "mirror_cloth" else dmask
                            donors[dmode] = Donors(dm, pos, nrm, scale, facing_min)
                    qs, qns = q[sel], qn[sel]
                    if mode == "mirror_cloth" and rp.get("cloth_offset_search"):
                        qs, entry["offset_search"] = cloth_offset_search(qs, qns, donors["mirror"], cloth_ok,
                                                                         rp["cloth_offset_search"])
                    dd = donors[mode]
                    dist, jj, facing = dd.query(qs, qns)
                    entry["isotropic_metric_texels"] = dd.last_iso
                    src_y, src_x = dd.dy[jj], dd.dx[jj]
                    vals = {key: raw[key][(src_y, src_x)] for key in ("BC", "AO", "MR")}
                    if detail:
                        tgt = (mrows[sel], mcols[sel])
                        vals["NORMAL"], nflat = transfer_detail_normal(raw["NORMAL"], frames, (src_y, src_x), tgt)
                        # a far donor (poor correspondence: a fold with no counterpart on the mirrored side) smears
                        # its relief into streaks that read as a dark line under light: flat normal there
                        far = dist > float(rp.get("normal_transfer_max_dist_m", 1.0))
                        vals["NORMAL"][far] = flat
                        entry["normal"] = {"transfer": "detail (donor tangent -> object, mirror, rotate onto the target normal)",
                                           "flat_fallback_texels": int((nflat | far).sum()),
                                           "flat_far_donor_texels": int((far & ~nflat).sum())}
                    else:
                        vals["NORMAL"] = np.broadcast_to(flat, (int(sel.sum()), 3))
                        entry["normal"] = {"transfer": "flat"}
                    flat_idx = src_y * pid.shape[1] + src_x
                    if kname == "phantom_zone" and part in kept_band:
                        entry["band_texels_kept"] = kept_band[part]
                    if "%s/%s" % (part, kname) in kept_band:
                        entry["band_texels_kept"] = kept_band["%s/%s" % (part, kname)]
                    entry.update({"donor_part": donor, "metric_scale": list(scale),
                                  "donor_texels": {k: v.count for k, v in donors.items()},
                                  "not_facing_fallback": int((~facing).sum()),
                                  "distinct_donor_share": P.r(len(np.unique(flat_idx)) / max(len(flat_idx), 1), 3),
                                  "donor_distance_mm_scaled_metric": {
                                      "median": P.r(np.median(dist) * 1000, 2),
                                      "p95": P.r(np.percentile(dist, 95) * 1000, 2)}})
                elif mode == "plain":
                    shell = np.zeros(pid.shape, dtype=bool)
                    shell[m] = (out > feather) & (out < float(box["shell_m"]))
                    clean = shell & ~in_zone
                    med = {key: np.median(raw[key][clean], axis=0) for key in ("BC", "AO", "MR")}
                    vals = {key: np.broadcast_to(med[key], (int(sel.sum()), raw[key].shape[-1])) for key in ("BC", "AO", "MR")}
                    vals["NORMAL"] = np.broadcast_to(flat, (int(sel.sum()), 3))
                    entry.update({"shell_texels": int(clean.sum()),
                                  "median_bc_linear": [P.r(x, 4) for x in med["BC"]]})
                else:
                    raise ValueError("unknown repaint donor mode %s" % mode)
                ws = w[sel][:, None]
                for key in acc[grp]:
                    acc[grp][key][sel] += vals[key] * ws
                wsum[grp][sel] += w[sel]
                wgrp[grp] = np.maximum(wgrp[grp], w)
                wmax = np.maximum(wmax, w)
            plog[kname] = entry
        sel = wmax > 0
        ws = wmax[sel][:, None]
        we = np.where(wgrp["zone"][sel] > 0, wgrp["explicit"][sel], (wgrp["explicit"][sel] > 0).astype(np.float32))
        we = we[:, None]
        for key in keys:
            cur = raw[key][m]
            mix = np.zeros(cur[sel].shape, dtype=np.float32)
            for grp, coef in (("explicit", we), ("zone", 1 - we)):
                ok = wsum[grp][sel] > 0
                part_mix = np.zeros_like(mix)
                part_mix[ok] = acc[grp][key][sel][ok] / wsum[grp][sel][ok][:, None]
                mix += part_mix * coef
            cur[sel] = cur[sel] * (1 - ws) + mix * ws
            raw[key][m] = cur
        z = np.zeros(pid.shape, dtype=bool)
        z[m] = sel
        valid |= z
        plog["total"] = {"texels": int(sel.sum()), "full_weight_texels": int((wmax >= 1).sum())}
        log[part] = plog
    return log, in_zone


def cloth_cleanup(raw, pid, names, pos, valid, in_zone, cfg, rule):
    """H2.1 residue cleanup of the repainted cloak (profile textures.phantom_repaint.cloth_cleanup): inside a
    Tripo-frame box (smoothstep over feather_m) the texels of the part that are not part of a border band take the
    colour of the part's clean red cloth around the box: chromaticity = median chromaticity of the reference, luminance
    = the texel's own luminance clamped to the reference percentiles lum_clamp_pct. Nothing moves (no donor lookup,
    so no stretched weave): gold/brown smudges and the phantom tab turn red, dark dashes and bright smears are clamped
    into the cloth range, the weave variation inside that range stays; the normal is not touched (the dark dashes
    left on the strip fold are geometry slits, not paint). Band = large gold components of the painted colour
    (>= band_component_min_texels) dilated band_dilate_px (their dark outlines too): weight 0, the band keeps its
    paint. Reference = valid texels of the part that pass the cloth colour rule, outside every repaint zone and the
    band, farther than feather_m and nearer than shell_m from the box."""
    lumw = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    log = {}
    cloth_ok, gold_ok, _g = colour_classes(raw["BC"], rule)     # painted colour before the cleanup
    for c in cfg:
        part_m = pid == names.index(c["part"]) + 1
        gl, _n = ndimage.label(part_m & gold_ok, structure=np.ones((3, 3), dtype=bool))
        sizes = np.bincount(gl.ravel())
        sizes[0] = 0
        band = ndimage.binary_dilation(sizes[gl] >= int(c.get("band_component_min_texels", 2000)),
                                       iterations=int(c.get("band_dilate_px", 6))) & part_m
        lo, hi = np.array(c["min_m"]), np.array(c["max_m"])
        f = float(c["feather_m"])
        out = np.full(pid.shape, np.inf, dtype=np.float32)
        out[part_m] = np.linalg.norm(np.maximum(np.maximum(lo - pos[part_m], pos[part_m] - hi), 0.0), axis=1)
        w = np.where(part_m & ~band, smoothstep((f - out) / f), 0.0).astype(np.float32)
        ref = part_m & cloth_ok & valid & ~in_zone & ~band & (out > f) & (out < float(c["shell_m"]))
        bc = raw["BC"]
        lum = bc @ lumw
        plo, phi = np.percentile(lum[ref], c["lum_clamp_pct"])
        chroma = np.median(bc[ref] / np.maximum(lum[ref], 1e-6)[:, None], axis=0)
        tgt = w > 0
        wt = w[tgt][:, None]
        before = bc[tgt].copy()
        full = (w >= 1)
        r2, r98 = np.percentile(lum[ref], [2, 98])
        cv_ref = float(lum[ref].std() / max(lum[ref].mean(), 1e-6))

        def residue(sel):
            cl = colour_classes(bc[sel][None], rule)[0][0]
            lm = bc[sel] @ lumw
            return {"not_cloth_colour_share": P.r(1.0 - cl.mean(), 4),
                    "lum_outside_ref_p2_p98_share": P.r(((lm < r2) | (lm > r98)).mean(), 4),
                    "lum_cv": P.r(lm.std() / max(lm.mean(), 1e-6), 4)}
        res_before = residue(full)
        new = chroma[None, :] * np.clip(lum[tgt], plo, phi)[:, None]
        bc[tgt] = before * (1 - wt) + new * wt
        entry = {"box_min_m": c["min_m"], "box_max_m": c["max_m"], "texels": int(tgt.sum()),
                 "full_weight_texels": int((w >= 1).sum()), "band_texels_kept": int((band & (out <= f)).sum()),
                 "reference_texels": int(ref.sum()), "lum_clamp_linear": [P.r(plo, 5), P.r(phi, 5)],
                 "chroma_linear": [P.r(x, 4) for x in chroma],
                 "changed_texels_gt_1pct": int((np.abs(bc[tgt] - before).max(axis=1) > 0.01 * np.maximum(before.max(axis=1), 1e-3)).sum()),
                 "residue_full_weight_texels": {"before": res_before, "after": residue(full),
                                                "reference": {"lum_cv": P.r(cv_ref, 4), "lum_p2_p98": [P.r(r2, 5), P.r(r98, 5)]}},
                 "why": c.get("why", "")}
        log[c["name"]] = entry
    return log


def mip_chain(x, levels):
    out = [x]
    for _ in range(levels):
        out.append(box2(out[-1]))
    return out


def sample_bilinear(img, rows, cols, atlas_px):
    """img (S x S); rows/cols = atlas-size texel indices -> bilinear value at the same UV on this mip."""
    s = img.shape[0] / float(atlas_px)
    return ndimage.map_coordinates(img, [(rows + 0.5) * s - 0.5, (cols + 0.5) * s - 0.5], order=1, mode="nearest")


def team_edge_check(team_r_2k, pid, names, cloth_parts, cloth_hard, atlas_px, threshold, levels=3):
    """Edge row of the cloth islands (atlas texels of the part with a 4-neighbour outside the part) vs the interior
    (>= 3 px inside), both sampled bilinearly at the same UV on the 2K runtime mask and its box mips 1..levels.
    ratio_all: every texel of the part (a legit gold hem on an island edge also lowers it);
    ratio_cloth: only texels whose hard colour rule is cloth (isolates bleeding from outside the island)."""
    mips = mip_chain(team_r_2k, levels)
    out, passed = {}, True
    for part in cloth_parts:
        m = pid == names.index(part) + 1
        if not m.any():
            continue
        edge = m & ~ndimage.binary_erosion(m)
        inner = ndimage.binary_erosion(m, iterations=3)
        entry = {"edge_texels": int(edge.sum()), "interior_texels": int(inner.sum())}
        for tag, sel_e, sel_i in (("all", edge, inner), ("cloth", edge & cloth_hard, inner & cloth_hard)):
            ey, ex = np.nonzero(sel_e)
            iy, ix = np.nonzero(sel_i)
            rows = []
            for lv, img in enumerate(mips):
                re_ = float(sample_bilinear(img, ey, ex, atlas_px).mean()) if len(ey) else 0.0
                ri = float(sample_bilinear(img, iy, ix, atlas_px).mean()) if len(iy) else 0.0
                ratio = re_ / ri if ri > 0 else None
                rows.append({"mip": lv, "px": int(img.shape[0]), "edge_mean": P.r(re_, 4),
                             "interior_mean": P.r(ri, 4), "ratio": P.r(ratio, 4) if ratio is not None else None})
                if tag == "cloth" and ratio is not None and ratio < threshold:
                    passed = False
            entry["ratio_" + tag] = rows
        out[part] = entry
    return {"threshold": threshold, "passed_cloth": passed, "parts": out,
            "method": "2K runtime TeamMask.R and its 2x2 box mips 1-%d; sample points = atlas texel centres (same UV)"
                      % levels}


def residue_check(bc_lin, pid, names, pos, phantom, rule, plane, miss_phantom, part, radius):
    """Colour residue of the phantom paint on one part (the cloak): shares of grey/dark (s < 0.35 or v < 0.08) and
    gold texels in (A) the phantom miss clusters, (B) the other texels within `radius` of a phantom vertex, and
    (C) the mirrored clean side (texels whose mirrored position is within `radius` of a phantom vertex, outside A, B)."""
    m = pid == names.index(part) + 1
    cloth, gold, grey = colour_classes(bc_lin, rule)
    tree = cKDTree(phantom)
    d = np.full(pid.shape, np.inf)
    d[m] = tree.query(pos[m], k=1)[0]
    q = pos[m].copy()
    q[:, 0] = 2 * plane - q[:, 0]
    dmir = np.full(pid.shape, np.inf)
    dmir[m] = tree.query(q, k=1)[0]
    a = m & miss_phantom
    b = m & ~miss_phantom & (d <= radius)
    c = m & ~a & ~b & (dmir <= radius)
    out = {"radius_m": radius, "part": part,
           "classes": "sRGB HSV: grey/dark s < 0.35 or v < 0.08; gold hue 20-60, s >= 0.3, v >= 0.25; cloth = TeamMask rule"}
    for tag, sel in (("A_phantom_misses", a), ("B_near_phantoms", b), ("C_mirrored_clean_side", c)):
        n = int(sel.sum())
        out[tag] = {"texels": n, "grey_dark_share": P.r(grey[sel].mean() if n else 0, 4),
                    "gold_share": P.r(gold[sel].mean() if n else 0, 4),
                    "cloth_share": P.r(cloth[sel].mean() if n else 0, 4)}
    return out


def main():
    profile = P.load_json(sys.argv[1])
    paths = P.run_paths(sys.argv[2])
    tcfg = profile["textures"]
    bake = paths["work"] / "bake"
    size = int(profile["uv"]["atlas_px"])
    pid = np.load(paths["work"] / "uv-part-id.npy").astype(np.int32)
    tri = np.load(paths["work"] / "uv-triangles.npz")
    names = [str(n) for n in tri["names"]]
    isl = uvcheck.rasterise(tri["uv"], tri["island"], size)
    covered = pid > 0
    if not np.array_equal(isl > 0, covered):
        raise RuntimeError("island raster and part raster cover different texels")
    hit = np.load(bake / "HIT.npy").astype(np.float32)[..., 0] > 0.5
    pos = np.load(bake / "POS.npy")
    phantom = np.load(paths["work"] / "phantom-points.npy")
    rep = {"schema": "unmatched.h2-bake.textures/2", "atlas_px": size, "misses": {}}
    # ------------------------------------------------ misses
    for i, n in enumerate(names):
        m = pid == i + 1
        miss = m & ~hit
        rep["misses"][n] = {"texels": int(m.sum()), "missed": int(miss.sum()),
                            "missed_share": P.r(miss.sum() / max(m.sum(), 1), 6)}
    miss = covered & ~hit
    total_cov = int(covered.sum())
    rep["misses_total"] = {"covered_texels": total_cov, "missed": int(miss.sum()),
                           "missed_share": P.r(miss.sum() / max(total_cov, 1), 6)}
    raw = {key: np.load(bake / ("%s.npy" % key)).astype(np.float32) for key in ("BC", "NORMAL", "AO", "MR")}
    rp = tcfg.get("phantom_repaint")
    rule = tcfg["team_mask"]
    miss_phantom = np.zeros(pid.shape, dtype=bool)
    if rp and rp.get("miss_clusters"):
        miss_phantom, rep["phantom_miss_clusters"] = phantom_miss_mask(
            miss, pid, names, pos, phantom, rp["parts"], float(rp["miss_clusters"]["max_phantom_dist_m"]))
    # ------------------------------------------------ fill: other misses from their own island
    valid = hit.copy()
    rep["miss_fill"] = island_fill(raw, valid, miss & ~miss_phantom, isl, pid, pos)
    rep["miss_fill"]["method"] = ("nearest valid texel of the same UV island (EDT restricted to the island); islands "
                                  "without a hit: nearest valid texel of the same part in 3D (POS)")
    valid |= miss & ~miss_phantom
    # the phantom misses get a provisional value (every one of them is repainted with weight 1 below)
    for key in raw:
        raw[key] = nearest_fill(raw[key], valid)
    # ------------------------------------------------ phantom repaint, then gutters from the covered texels
    in_zone = np.zeros(pid.shape, dtype=bool)
    if rp:
        cloth_ok, gold_ok, _grey = colour_classes(raw["BC"], rule)
        frames = pos_frames(pos)
        nrm = frames[2]
        # sign check of the POS normals: the back of the cloak (Tripo +Y) must face +Y
        cloak = pid == names.index(rp["parts"][0]) + 1
        back = cloak & (pos[..., 1] > 0.04) & (np.abs(pos[..., 0]) < 0.08) & (pos[..., 2] > 0.3) & (pos[..., 2] < 0.6)
        rep["pos_normals_sign_check"] = {"cloak_back_texels": int(back.sum()),
                                         "share_facing_plus_y": P.r((nrm[back][:, 1] > 0).mean(), 4)}
        rep["phantom_repaint"], in_zone = repaint(raw, pid, names, valid, pos, phantom, rp, cloth_ok, gold_ok, miss_phantom, frames)
        left = int((miss_phantom & ~in_zone).sum())
        rep["phantom_repaint"]["phantom_miss_texels_outside_repaint"] = left
        if left:
            raise RuntimeError("%d phantom miss texels were not repainted" % left)
        if rp.get("cloth_cleanup"):
            rep["cloth_cleanup"] = cloth_cleanup(raw, pid, names, pos, valid, in_zone, rp["cloth_cleanup"], rule)
    maps = {key: nearest_fill(raw[key], covered) for key in raw}
    maps["NORMAL"] = normals_encode(maps["NORMAL"])
    # painted colour (Tripo + repaint): the TeamMask colour rule and the residue check read it, not the material BC
    bc_paint = maps["BC"]
    # ------------------------------------------------ H2.1 material pass (metal mask, PBR BC / roughness / metallic)
    mcfg = tcfg.get("materials")
    classes = None
    if mcfg:
        maps["BC"], maps["MR"], rep["materials"], classes = M.apply_materials(
            bc_paint, maps["MR"], pid, names, pos, covered, mcfg)
        maps["BC"] = nearest_fill(maps["BC"], covered)
        maps["MR"] = nearest_fill(maps["MR"], covered)
    # ------------------------------------------------ TeamMask
    cloth_idx = [names.index(p) + 1 for p in rule["cloth_parts"] if p in names]
    in_cloth = np.isin(pid, cloth_idx)
    colour_ok = colour_classes(bc_paint, rule)[0]
    cloth_hard = in_cloth & colour_ok
    sigma = float(rule["blur_sigma_px"])
    # normalised convolution inside the cloth parts' coverage: an island edge is not pulled down by the empty
    # gutter; then the gutters and the empty atlas take the nearest covered texel, exactly like BC
    num = ndimage.gaussian_filter(cloth_hard.astype(np.float32), sigma)
    den = ndimage.gaussian_filter(in_cloth.astype(np.float32), sigma)
    soft = np.where(in_cloth, num / np.maximum(den, 1e-6), 0.0).astype(np.float32)
    cloth = nearest_fill(soft, covered)
    # base band: triangles of the base with |nz| below the limit, rasterised, same atlas fill
    band_cfg = rule["base_band"]
    base_i = names.index(band_cfg["part"])
    band = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(band)
    sel = (tri["obj"] == base_i) & (np.abs(tri["nz"]) < float(band_cfg["normal_z_max"]))
    for t in tri["uv"][sel]:
        draw.polygon([(float(u * size - 0.5), float((1.0 - vv) * size - 0.5)) for u, vv in t], fill=255)
    band = ((np.array(band) > 127) & covered).astype(np.float32)
    band = nearest_fill(band, covered)
    team = np.zeros((size, size, 4), dtype=np.float32)
    team[..., 0] = cloth
    team[..., 1] = band
    team[..., 3] = 1.0
    rep["team_mask"] = {"rule": rule, "per_part_cloth_share": {}, "base_band_texels": int((band[covered] > 0.5).sum()),
                        "edge": "normalised Gaussian inside the cloth parts' coverage + nearest covered texel fill"}
    for i, n in enumerate(names):
        m = pid == i + 1
        if m.any():
            rep["team_mask"]["per_part_cloth_share"][n] = P.r((cloth[m] > 0.5).mean(), 4)
    rep["team_mask"]["edge_check"] = team_edge_check(box2(team[..., 0]), pid, names, rule["cloth_parts"], cloth_hard,
                                                     size, float(rule.get("edge_ratio_min", 0.9)))
    # ------------------------------------------------ residue of the phantom paint on the cloak
    if rp and rp.get("residue_check"):
        rc = rp["residue_check"]
        rep["residue_check"] = residue_check(bc_paint, pid, names, pos, phantom, rule, float(rp["mirror_plane_x_m"]),
                                             miss_phantom, rc["part"], float(rc["radius_m"]))
    # ------------------------------------------------ encode + save 4K and 2K
    prefix = tcfg["prefix"]
    outputs = {}
    for level, scale_dir in (("master_4k", 1), ("runtime_2k", 2)):
        d = paths["textures"] / level
        bc = maps["BC"] if scale_dir == 1 else box2(maps["BC"])
        nrm = maps["NORMAL"] if scale_dir == 1 else normals_encode(box2(maps["NORMAL"]))
        ao = maps["AO"] if scale_dir == 1 else box2(maps["AO"])
        mr = maps["MR"] if scale_dir == 1 else box2(maps["MR"])
        tm = team if scale_dir == 1 else box2(team)
        files = {}
        files["BC"] = save_png(q8(srgb(bc)), d / (prefix + "_BC.png"), "RGB") | {"colour": "sRGB 8-bit"}
        n_gl = q8(nrm)
        files["N_OpenGL"] = save_png(n_gl, d / (prefix + "_N_OpenGL.png"), "RGB") | {"colour": "linear, OpenGL/Blender (+Y)"}
        n_dx = n_gl.copy()
        n_dx[..., 1] = 255 - n_dx[..., 1]
        files["N"] = save_png(n_dx, d / (prefix + "_N.png"), "RGB") | {"colour": "linear, DirectX for UE (green inverted), UE: TC_Normalmap, flip_green false"}
        orm = np.stack([ao[..., 0], mr[..., 1], mr[..., 2]], axis=-1)
        files["ORM"] = save_png(q8(orm), d / (prefix + "_ORM.png"), "RGB") | {"colour": "linear: R AO, G roughness, B metallic; UE: sRGB off, TC_Masks"}
        files["TeamMask"] = save_png(q8(tm), d / (prefix + "_TeamMask.png"), "RGBA") | {"colour": "linear: R cloth, G base band, B 0, A 255; UE: sRGB off (M_UM_Figure reads R)"}
        outputs[level] = files
    rep["outputs"] = outputs
    rep["stats"] = {
        "ao_mean_covered": P.r(maps["AO"][covered].mean(), 4),
        "roughness_mean_covered": P.r(maps["MR"][..., 1][covered].mean(), 4),
        "metallic_mean_covered": P.r(maps["MR"][..., 2][covered].mean(), 4),
        "metallic_share_above_0.5": P.r((maps["MR"][..., 2][covered] > 0.5).mean(), 4),
    }
    # inspection raster (work/, not committed): repaint zones blue, phantom misses magenta, over the BC
    dbg = q8(srgb(maps["BC"]))
    dbg[in_zone] = (dbg[in_zone] * 0.5 + np.array([0, 160, 255]) * 0.5).astype(np.uint8)
    dbg[miss_phantom] = (dbg[miss_phantom] * 0.4 + np.array([255, 0, 255]) * 0.6).astype(np.uint8)
    Image.fromarray(dbg).save(paths["work"] / "repaint-zones-4k.png", format="PNG", compress_level=1)
    if classes is not None:
        # material class raster (inspection, work/): rendered flat on the mesh by stage compare (class-map frames)
        ras = nearest_fill(M.class_raster(classes, covered), covered)
        Image.fromarray(ras).save(paths["work"] / "materials-classes-4k.png", format="PNG", compress_level=1)
        Image.fromarray(q8(box2(ras.astype(np.float32) / 255.0))).save(paths["work"] / "materials-classes-2k.png",
                                                                       format="PNG", compress_level=6)
        # TeamMask vs metal: a texel painted as team cloth must not be metal
        tm2 = box2(team[..., 0])
        met2 = box2(maps["MR"][..., 2])
        rep["materials"]["teammask_metal_overlap_2k"] = {
            "texels_teammask_gt_0.5_and_metallic_gt_0.5": int(((tm2 > 0.5) & (met2 > 0.5)).sum()),
            "texels_teammask_gt_0.5": int((tm2 > 0.5).sum())}
    P.write_json(paths["reports"] / "textures-report.json", rep)
    print(P.STAGE_MARKER, "textures", rep["misses_total"], rep["stats"], "team edge passed:",
          rep["team_mask"]["edge_check"]["passed_cloth"])


if __name__ == "__main__":
    main()
