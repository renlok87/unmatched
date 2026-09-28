"""ASSET-DECOR-KIT-001.FACADES, step 1 of 3 (system Python 3 + numpy + Pillow + scipy; no Blender).

    python art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/facades_trace.py \
        art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/facades_params.json

Concept collage (front view) -> composite strip -> object mask -> silhouette polygon (uu) -> shared 1K atlas
(BC sRGB, N DirectX linear, ORM linear) + UV layout for facades_build.py (step 2, Blender headless).

Silhouette: the background of the collages is a smooth blue-grey gradient; it is estimated by normalised
convolution over pixels with low local contrast, an object pixel differs from it in colour or has local
texture. Per column the silhouette is one run: top = first object pixel, bottom = ground (base row) when the
column reaches it, otherwise the end of the first run (eave overhang). The outline is simplified with
Douglas-Peucker (tolerance in uu) and checked to be a simple polygon.

Outputs (out_dir):
  work/trace/*.png                       composite, mask, overlay (diagnostics, transient)
  reports/trace.json                     polygons, glow rects, atlas rects, measurements
  textures/T_Decor_Facades_{BC,N,ORM}.png
  preview/atlas-layout.jpg               atlas with island rects (<=1200 px)
Nothing here is an art decision beyond the composition recorded in params; numbers are measurements.
"""
import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[4]  # <repo>/art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/<file>
LUMA = np.array([0.2126, 0.7152, 0.0722])


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rnd(v, n=4):
    return round(float(v), n)


# ----------------------------------------------------------------------------- mask
def local_std(l, r):
    k = 2 * r + 1
    m = ndi.uniform_filter(l, k)
    m2 = ndi.uniform_filter(l * l, k)
    return np.sqrt(np.maximum(m2 - m * m, 0))


def background_model(a, cfg):
    """Normalised convolution of low-contrast pixels -> smooth background estimate (per channel)."""
    l = a @ LUMA
    sd = local_std(l, cfg["std_radius_px"])
    cand = sd < 2.0
    sig = cfg["bg_sigma_px"]
    for _ in range(3):
        w = ndi.gaussian_filter(cand.astype(np.float64), sig)
        bg = np.stack([ndi.gaussian_filter(a[..., c] * cand, sig) for c in range(3)], -1) / np.maximum(w, 1e-6)[..., None]
        diff = np.abs(a - bg).max(-1)
        cand = (sd < 2.5) & (diff < cfg["color_threshold"] * 0.6)
    return bg, sd, cand


def object_mask(a, cfg):
    bg, sd, cand = background_model(a, cfg)
    diff = np.abs(a - bg).max(-1)
    # texture alone would add a halo of ~std_radius px of background around every edge (the window straddles the
    # edge), so a textured pixel must also differ from the background by a fraction of the colour threshold
    # and a colour difference alone must come with some texture: the floor/backdrop transition and soft contact
    # shadows are smooth (local std ~1) and are not part of the wall (enclosed smooth plaster is refilled later)
    obj = (((diff > cfg["color_threshold"]) & (sd > cfg["color_needs_std"]))
           | ((sd > cfg["std_threshold"]) & (diff > cfg["color_threshold"] * cfg["std_needs_color_fraction"])))
    stats = {"bg_candidate_fraction": rnd(cand.mean()),
             "bg_residual_p50_p99_on_candidates": [rnd(np.percentile(diff[cand], q), 2) for q in (50, 99)],
             "local_std_p50_p99_on_candidates": [rnd(np.percentile(sd[cand], q), 2) for q in (50, 99)]}
    return obj, bg, stats


def disk(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def compose(img, obj, segs, trim_frac):
    """Concatenate segments left to right, aligned at base_y.
    A segment side listed in "trim" (composite orientation, i.e. after mirroring) is cut to the first column whose
    object pixels cover >= trim_frac of the segment height, so two views cut with a margin abut without the
    background gap between them (a contact-shadow line on the floor does not count as object).
    Returns rgb, mask, seam columns and per-segment placement (offset, effective source x0/x1, mirror)."""
    hmax = max(s["base_y"] - s["y0"] for s in segs)
    cols_rgb, cols_m, seams, place, x = [], [], [], [], 0
    for s in segs:
        h = s["base_y"] - s["y0"]
        x0, x1 = s["x0"], s["x1"]
        trim = set(s.get("trim", []))
        if trim:
            full = obj[s["y0"]:s["base_y"], x0:x1].sum(0) >= trim_frac * h
            used = np.nonzero(full)[0]
            lo, hi = s["x0"] + int(used.min()), s["x0"] + int(used.max()) + 1
            # composite left = source left unless mirrored
            if ("left" in trim and not s.get("mirror")) or ("right" in trim and s.get("mirror")):
                x0 = lo
            if ("right" in trim and not s.get("mirror")) or ("left" in trim and s.get("mirror")):
                x1 = hi
        rgb = img[s["y0"]:s["base_y"], x0:x1]
        m = obj[s["y0"]:s["base_y"], x0:x1]
        if s.get("mirror"):
            rgb, m = rgb[:, ::-1], m[:, ::-1]
        prgb = np.zeros((hmax, rgb.shape[1], 3))
        pm = np.zeros((hmax, rgb.shape[1]), dtype=bool)
        prgb[hmax - h:] = rgb
        prgb[:hmax - h] = rgb[:1]  # top padding: first row (background), masked out anyway
        pm[hmax - h:] = m
        cols_rgb.append(prgb)
        cols_m.append(pm)
        place.append({"offset": x, "x0": x0, "x1": x1, "mirror": bool(s.get("mirror")), "base_y": s["base_y"]})
        x += rgb.shape[1]
        seams.append(x)
    return np.concatenate(cols_rgb, 1), np.concatenate(cols_m, 1), seams[:-1], place


def clean_mask(m):
    m = ndi.binary_closing(m, structure=disk(2))
    m = ndi.binary_fill_holes(m)
    m = ndi.binary_opening(m, structure=disk(1))
    lab, n = ndi.label(m)
    if n == 0:
        raise RuntimeError("empty mask")
    sizes = ndi.sum(m, lab, range(1, n + 1))
    keep = int(np.argmax(sizes)) + 1
    dropped = sorted(int(s) for i, s in enumerate(sizes) if i + 1 != keep)
    m = ndi.binary_fill_holes(lab == keep)
    return m, {"components": int(n), "dropped_component_pixels": dropped[-8:], "dropped_total_px": int(sum(dropped))}


def profiles(m, snap, min_ground_run):
    """A column stands on the ground when its lowest run ends within `snap` px of the base row and is at least
    `min_ground_run` px tall (a 2-4 px contact-shadow line next to the wall does not count)."""
    h, w = m.shape
    cols = np.nonzero(m.any(0))[0]
    c0, c1 = int(cols.min()), int(cols.max()) + 1
    if len(cols) != c1 - c0:
        raise RuntimeError("silhouette has empty columns inside")
    top, bot, multi_run = [], [], 0
    for c in range(c0, c1):
        col = m[:, c]
        t = int(np.argmax(col))
        rows = np.nonzero(col)[0]
        low = int(rows.max())
        above = np.nonzero(~col[:low + 1])[0]
        low_run = low - (int(above.max()) if len(above) else -1)
        if low >= h - 1 - snap and low_run >= min_ground_run:
            b = h
        else:
            gap = np.nonzero(~col[t:])[0]
            b = t + int(gap[0]) if len(gap) else h
        runs = int(np.sum(np.diff(np.concatenate([[0], col.astype(np.int8), [0]])) == 1))
        multi_run += runs > 1
        top.append(t)
        bot.append(b)
    return c0, c1, np.array(top), np.array(bot), multi_run


def close_top(top, k):
    """Grey closing of the silhouette height (H - top) over k columns: removes cracks/notches narrower than k px
    (a hairline gap between two abutting views would otherwise become a sliver spike in the mesh)."""
    if k <= 1:
        return top, 0
    h = -top.astype(np.int64)
    closed = ndi.minimum_filter1d(ndi.maximum_filter1d(h, k, mode="nearest"), k, mode="nearest")
    return -closed, int((closed != h).sum())


def outline(c0, top, bot):
    """Staircase outline (pixel-edge coordinates) split in two chains sharing the end points."""
    n = len(top)
    upper = [(c0, bot[0]), (c0, top[0])]
    for i in range(n):
        upper += [(c0 + i, top[i]), (c0 + i + 1, top[i])]
    upper.append((c0 + n, bot[-1]))
    lower = [(c0 + n, bot[-1])]
    for i in range(n - 1, -1, -1):
        lower += [(c0 + i + 1, bot[i]), (c0 + i, bot[i])]
    lower.append((c0, bot[0]))

    def dedup(ch):
        out = [ch[0]]
        for p in ch[1:]:
            if p != out[-1]:
                out.append(p)
        return out
    return dedup(upper), dedup(lower)


def dp(points, tol):
    pts = np.asarray(points, dtype=np.float64)
    keep = np.zeros(len(pts), dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = pts[i], pts[j]
        ab = b - a
        L = np.hypot(*ab)
        seg = pts[i + 1:j] - a
        d = np.abs(ab[0] * seg[:, 1] - ab[1] * seg[:, 0]) / L if L > 1e-12 else np.hypot(seg[:, 0], seg[:, 1])
        k = int(np.argmax(d))
        if d[k] > tol:
            keep[i + 1 + k] = True
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return [tuple(p) for p in pts[keep]]


def dp_forced(points, tol, forced):
    """Douglas-Peucker that always keeps the points at `forced` indices (chain split there)."""
    cuts = sorted({0, len(points) - 1, *forced})
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        part = dp(points[a:b + 1], tol)
        out += part if not out else part[1:]
    return out


def seg_intersect(p1, p2, p3, p4):
    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
    d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
    return (d1 * d2 < 0) and (d3 * d4 < 0)


def is_simple(poly):
    n = len(poly)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if seg_intersect(poly[i], poly[(i + 1) % n], poly[j], poly[(j + 1) % n]):
                return False
    return len({tuple(p) for p in poly}) == n


def signed_area(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


# ----------------------------------------------------------------------------- textures
def fill_nearest(arr, valid):
    idx = ndi.distance_transform_edt(~valid, return_distances=False, return_indices=True)
    return arr[tuple(idx)]


def resize(arr, size, resample=Image.LANCZOS):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return np.asarray(im.resize(size, resample)).astype(np.float64)


def srgb_to_lin(x):
    x = x / 255.0
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def write_png_rgb(path, arr8, srgb):
    """Plain RGB8 PNG. N/ORM carry no sRGB/gAMA/cHRM chunk (Linear is an import setting); BC gets an sRGB chunk."""
    h, w, _ = arr8.shape
    raw = b"".join(b"\x00" + arr8[y].astype(np.uint8).tobytes() for y in range(h))

    def chunk(t, data):
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    if srgb:
        png += chunk(b"sRGB", b"\x00")
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


# ----------------------------------------------------------------------------- packing
def shelf_pack(items, free_rects, gap):
    """items: [(key, w, h)] -> {key: (x, y)}; free_rects: [(x0, y0, x1, y1)]; simple shelves, tallest first."""
    placed = {}
    shelves = []  # [rect_index, y, height, x_cursor]
    for key, w, h in sorted(items, key=lambda t: (-t[2], -t[1])):
        ok = False
        for sh in shelves:
            ri, y, hh, xc = sh
            x0, y0, x1, y1 = free_rects[ri]
            if h <= hh and xc + w <= x1:
                placed[key] = (xc, y)
                sh[3] = xc + w + gap
                ok = True
                break
        if ok:
            continue
        for ri, (x0, y0, x1, y1) in enumerate(free_rects):
            used = max([s[1] + s[2] + gap for s in shelves if s[0] == ri], default=y0)
            if used + h <= y1 and x0 + w <= x1:
                shelves.append([ri, used, h, x0 + w + gap])
                placed[key] = (x0, used)
                ok = True
                break
        if not ok:
            raise RuntimeError("atlas full: cannot place %s (%dx%d)" % (key, w, h))
    return placed


# ----------------------------------------------------------------------------- main
def main():
    params_path = Path(sys.argv[1]).resolve()
    P = json.loads(params_path.read_text(encoding="utf-8"))
    out = ROOT / P["out_dir"]
    for sub in ("work/trace", "reports", "textures", "preview"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    S, pad, d = P["atlas_px"], P["pad_px"], P["density_px_per_uu"]
    q = d * P["back_side_density_scale"]
    T = P["thickness_uu"]
    cfg = P["mask"]
    report = {"schema": "unmatched.decor-facades.trace/1", "status": "measured",
              "script": Path(__file__).resolve().relative_to(ROOT).as_posix(),
              "script_sha256_lf": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
              "params": params_path.relative_to(ROOT).as_posix(),
              "params_sha256_lf": hashlib.sha256(params_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
              "atlas_px": S, "density_px_per_uu": d, "back_side_density_px_per_uu": q, "thickness_uu": T,
              "facades": []}
    facades = []
    for F in P["facades"]:
        src = ROOT / F["source"]
        got = sha256(src)
        if got != F["sha256"]:
            raise RuntimeError("%s sha256 %s != %s" % (src, got, F["sha256"]))
        img = np.asarray(Image.open(src).convert("RGB")).astype(np.float64)
        obj, bg, bgstats = object_mask(img, cfg)
        rgb, m_raw, seams, place = compose(img, obj, F["segments"], cfg["trim_min_column_fraction"])
        m, comp = clean_mask(m_raw)
        H = m.shape[0]
        c0, c1, top, bot, multi = profiles(m, cfg["base_snap_px"], cfg["min_ground_run_px"])
        top, closed_cols = close_top(top, cfg["top_close_px"])
        if (top >= bot).any():
            raise RuntimeError("top closing crossed the bottom profile")
        tmin = int(top.min())
        hpx = H - tmin
        s = F["height_uu"] / hpx  # uu per composite pixel
        wpx = c1 - c0
        L = wpx * s
        upper, lower = outline(c0, top, bot)
        tol_px = P["dp_tolerance_uu"] / s
        # keep the highest point (height = height_uu exactly) and the first/last ground points (base at z = 0)
        top_i = min(range(len(upper)), key=lambda i: upper[i][1])
        ground = [i for i, pnt in enumerate(lower) if pnt[1] == H]
        forced_low = [ground[0], ground[-1]] if ground else []
        poly_px = dp_forced(upper, tol_px, [top_i])[:-1] + dp_forced(lower, tol_px, forced_low)[:-1]
        if not is_simple(poly_px):
            raise RuntimeError("facade %s: simplified outline is not simple" % F["key"])
        # composite px -> uu: x centred, z up from ground
        poly = [(rnd((x - c0 - wpx / 2) * s, 4), rnd((H - y) * s, 4)) for x, y in poly_px]
        if signed_area(poly) < 0:  # CCW in (x, z) => normal -Y (front) in Blender
            poly = poly[::-1]
        # mask area vs polygon area (how much the simplification adds/removes)
        poly_img = Image.new("L", (m.shape[1], m.shape[0]), 0)
        ImageDraw.Draw(poly_img).polygon([(x, y) for x, y in poly_px], fill=1)
        pm = np.asarray(poly_img).astype(bool)
        prof = np.zeros_like(m)
        for i, c in enumerate(range(c0, c1)):
            prof[top[i]:bot[i], c] = True
        glow = []
        for g in F["glow"]:
            # x: pixel-edge coordinates; a source edge X lands at off + (X - x0), or off + (x1 - X) when mirrored
            if "seam" in g:
                xc = seams[g["seam"] - 1]
                seg = place[g["seam"]]
            else:
                seg = place[g["segment"]]
                xc = seg["offset"] + ((seg["x1"] - g["x_center"]) if seg["mirror"] else (g["x_center"] - seg["x0"]))
            r0 = H - (seg["base_y"] - g["y0"])  # rows: source y -> composite row (segments aligned at base_y)
            r1 = H - (seg["base_y"] - g["y1"])
            x_uu = (xc - c0 - wpx / 2) * s
            rect = [rnd(x_uu - g["width_uu"] / 2), rnd((H - r1) * s), rnd(x_uu + g["width_uu"] / 2), rnd((H - r0) * s)]
            glow.append({"rect_uu_x0_z0_x1_z1": rect, "why": g["why"]})
        facades.append(dict(F=F, rgb=rgb, m=m, m_raw=m_raw, pm=pm, prof=prof, tmin=tmin, H=H, c0=c0, c1=c1, s=s, L=L,
                            poly=poly, poly_px=poly_px, glow=glow, seams=seams))
        perim = sum(math.dist(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))
        report["facades"].append({
            "key": F["key"], "asset_name": F["asset_name"], "source": F["source"], "source_sha256": got,
            "segments": F["segments"], "segments_trimmed_to_object": place, "seam_columns": seams,
            "composition_note": F["composition_note"],
            "background_model": bgstats, "mask_components": comp,
            "composite_px": [int(m.shape[1]), int(H)], "silhouette_cols": [c0, c1], "columns_with_several_runs_filled": multi,
            "top_profile_columns_raised_by_closing": closed_cols,
            "uu_per_px": rnd(s, 6), "length_uu": rnd(L, 3), "height_uu": F["height_uu"],
            "polygon_vertices": len(poly), "polygon_uu": poly, "perimeter_uu": rnd(perim, 3),
            "polygon_area_uu2": rnd(abs(signed_area(poly)), 2),
            "polygon_vs_profile_mask_px": {"profile_px": int(prof.sum()), "polygon_px": int(pm.sum()),
                                           "in_polygon_not_object": int((pm & ~prof).sum()),
                                           "object_not_in_polygon": int((prof & ~pm).sum())},
            "glow": glow,
        })

    # ---------------------------------------------------------------- atlas layout
    rects = {}
    y = pad
    for fc in facades:
        w, h = int(round(fc["L"] * d)), int(round(fc["F"]["height_uu"] * d))
        if w > S - 2 * pad:
            raise RuntimeError("front strip %s wider than atlas" % fc["F"]["key"])
        rects["front_" + fc["F"]["key"]] = (pad, y, w, h)
        y += h + pad
    y_end = y
    widest_below_first = max(rects["front_" + fc["F"]["key"]][2] for fc in facades[1:])
    first = rects["front_" + facades[0]["F"]["key"]]
    free = [(pad + widest_below_first + pad, first[1] + first[3] + pad, S - pad, y_end - pad),
            (pad, y_end, S - pad, S - pad)]
    items = []
    for fc in facades:
        k = fc["F"]["key"]
        perim = sum(math.dist(fc["poly"][i], fc["poly"][(i + 1) % len(fc["poly"])]) for i in range(len(fc["poly"])))
        items.append(("back_" + k, int(math.ceil(fc["L"] * q)) + 2, int(math.ceil(fc["F"]["height_uu"] * q)) + 2))
        items.append(("side_" + k, int(math.ceil(perim * q)) + 2, int(math.ceil(T * q)) + 2))
    placed = shelf_pack(items, free, gap=pad // 2 + 2)
    for key, w, h in items:
        rects[key] = (placed[key][0], placed[key][1], w, h)

    # ---------------------------------------------------------------- textures
    fill = np.array(P["free_fill_srgb"], dtype=np.float64)
    BC = np.tile(fill, (S, S, 1))
    NRM = np.tile(np.array([128.0, 128.0, 255.0]), (S, S, 1))
    ORM = np.tile(np.array([255.0, 255 * P["roughness"]["back_side"], 0.0]), (S, S, 1))
    glow_rgb = np.array(P["glow_rgb_srgb"], dtype=np.float64)
    tex_report = {}
    for fc in facades:
        k = fc["F"]["key"]
        x0, y0, w, h = rects["front_" + k]
        sub = fc["rgb"][fc["tmin"]:, fc["c0"]:fc["c1"]]
        msub = fc["prof"][fc["tmin"]:, fc["c0"]:fc["c1"]]
        # colour source = object pixels inside the silhouette; background pixels that the one-run-per-column
        # silhouette encloses (and the gutter) take the colour of the nearest object pixel
        vsub = msub & fc["m"][fc["tmin"]:, fc["c0"]:fc["c1"]]
        filled = fill_nearest(sub, vsub)
        bc = resize(filled, (w, h))
        mk = resize(msub.astype(np.float64) * 255, (w, h), Image.BILINEAR) > 127
        # normal from luminance (height ~ brightness: mortar/cracks dark = low)
        l = bc @ LUMA
        hgt = ndi.gaussian_filter(l, 0.8) - ndi.gaussian_filter(l, 6.0)
        hgt /= max(hgt[mk].std(), 1e-6)
        gy, gx = np.gradient(hgt)  # gy along rows (down)
        gmag = np.hypot(gx, gy)
        kk = math.tan(math.radians(P["normal_max_tilt_deg_p95"])) / max(np.percentile(gmag[mk], 95), 1e-6)
        nx, ny_gl, nz = -kk * gx, kk * gy, np.ones_like(gx)  # OpenGL: +Y = up (v up = rows up)
        nn = np.sqrt(nx * nx + ny_gl * ny_gl + nz * nz)
        n_dx = np.stack([nx / nn, -ny_gl / nn, nz / nn], -1)  # DirectX: green flipped
        nrm = (n_dx * 0.5 + 0.5) * 255
        hsv = np.asarray(Image.fromarray(bc.astype(np.uint8)).convert("HSV")).astype(np.float64)
        wood = ((bc[..., 0] - bc[..., 2]) > 14) & (hsv[..., 1] > 40)
        rough = np.where(wood, P["roughness"]["wood"], P["roughness"]["stone"]) * 255
        orm = np.stack([np.full_like(rough, 255.0), rough, np.zeros_like(rough)], -1)
        # glow slits: painted into BC (texels of the glow faces), flat normal
        gl_mask = np.zeros((h, w), dtype=bool)
        for g in fc["glow"]:
            gx0, gz0, gx1, gz1 = g["rect_uu_x0_z0_x1_z1"]
            px0 = int(math.floor((gx0 + fc["L"] / 2) * d)) - 1
            px1 = int(math.ceil((gx1 + fc["L"] / 2) * d)) + 1
            py0 = int(math.floor((fc["F"]["height_uu"] - gz1) * d)) - 1
            py1 = int(math.ceil((fc["F"]["height_uu"] - gz0) * d)) + 1
            gl_mask[max(py0, 0):py1, max(px0, 0):px1] = True
        bc[gl_mask] = glow_rgb
        nrm[gl_mask] = (128, 128, 255)
        orm[gl_mask, 1] = P["roughness"]["glow"] * 255
        BC[y0:y0 + h, x0:x0 + w] = bc
        NRM[y0:y0 + h, x0:x0 + w] = nrm
        ORM[y0:y0 + h, x0:x0 + w] = orm
        # gutter: extend strip edge texels by pad//2 (bake-margin style) so mips do not pull in the fill colour
        g2 = pad // 2
        ys0, ys1, xs0, xs1 = max(y0 - g2, 0), min(y0 + h + g2, S), max(x0 - g2, 0), min(x0 + w + g2, S)
        valid = np.zeros((ys1 - ys0, xs1 - xs0), dtype=bool)
        valid[y0 - ys0:y0 - ys0 + h, x0 - xs0:x0 - xs0 + w] = True
        for A in (BC, NRM, ORM):
            A[ys0:ys1, xs0:xs1] = fill_nearest(A[ys0:ys1, xs0:xs1], valid)
        # back / side colour: median of this facade's front object texels, darkened
        med = np.median(bc[mk & ~gl_mask], axis=0) * P["back_side_colour_scale"]
        for kind in ("back_", "side_"):
            bx, by, bw, bh = rects[kind + k]
            BC[by - 1:by + bh + 1, bx - 1:bx + bw + 1] = med
        lin = srgb_to_lin(bc[mk & ~gl_mask]) @ LUMA
        tilt = np.degrees(np.arccos(np.clip(n_dx[..., 2][mk], -1, 1)))
        tex_report[k] = {"front_rect_px": rects["front_" + k], "back_rect_px": rects["back_" + k],
                         "side_rect_px": rects["side_" + k],
                         "front_object_texels": int(mk.sum()), "glow_texels": int(gl_mask.sum()),
                         "wood_texels_fraction": rnd((wood & mk).sum() / max(mk.sum(), 1)),
                         "bc_front_median_srgb": [int(v) for v in np.median(bc[mk & ~gl_mask], axis=0)],
                         "bc_front_mean_linear_luminance": rnd(lin.mean()),
                         "back_side_srgb": [int(v) for v in med],
                         "normal_gain": rnd(kk, 4),
                         "normal_tilt_deg_p50_p95_max_in_mask": [rnd(np.percentile(tilt, q_), 2) for q_ in (50, 95, 100)]}

    tex_dir = out / "textures"
    pre = P["texture_prefix"]
    paths = {"BC": tex_dir / (pre + "_BC.png"), "N": tex_dir / (pre + "_N.png"), "ORM": tex_dir / (pre + "_ORM.png")}
    write_png_rgb(paths["BC"], np.clip(np.round(BC), 0, 255).astype(np.uint8), srgb=True)
    write_png_rgb(paths["N"], np.clip(np.round(NRM), 0, 255).astype(np.uint8), srgb=False)
    write_png_rgb(paths["ORM"], np.clip(np.round(ORM), 0, 255).astype(np.uint8), srgb=False)
    report["textures"] = {k: {"path": v.relative_to(ROOT).as_posix(), "sha256": sha256(v), "bytes": v.stat().st_size,
                              "size_px": [S, S],
                              "colour_space": "sRGB" if k == "BC" else "Linear (no sRGB/gAMA/cHRM chunk)"}
                          for k, v in paths.items()}
    report["textures"]["N"]["convention"] = "tangent space, DirectX (green = -Y), height ~ luminance high-pass"
    report["textures"]["ORM"]["channels"] = ("R = AO 1.0 (concept render already contains its shading; not baked twice), "
                                              "G = roughness (stone %.2f / wood %.2f / glow %.2f / back+sides %.2f), B = metallic 0"
                                              % (P["roughness"]["stone"], P["roughness"]["wood"], P["roughness"]["glow"],
                                                 P["roughness"]["back_side"]))
    report["texture_measurements"] = tex_report
    report["atlas_rects_px_x_y_w_h_top_left_origin"] = {k: list(v) for k, v in rects.items()}
    report["atlas_free_rects"] = free

    # ---------------------------------------------------------------- diagnostics
    for fc in facades:
        k = fc["F"]["key"]
        base = Image.fromarray(np.clip(fc["rgb"], 0, 255).astype(np.uint8))
        base.save(out / "work/trace" / ("composite-%s.png" % k))
        ov = np.clip(fc["rgb"], 0, 255).astype(np.uint8).copy()
        ov[fc["m_raw"] & ~fc["m"]] = (255, 0, 255)
        ov[~fc["m"]] = (ov[~fc["m"]] * 0.45).astype(np.uint8)
        im = Image.fromarray(ov)
        dr = ImageDraw.Draw(im)
        dr.line([(x, y) for x, y in fc["poly_px"]] + [fc["poly_px"][0]], fill=(0, 255, 0), width=2)
        for sx in fc["seams"]:
            dr.line([(sx, 0), (sx, 12)], fill=(255, 255, 0), width=2)
        for g in fc["glow"]:
            x0, z0, x1, z1 = g["rect_uu_x0_z0_x1_z1"]
            X = lambda xu: fc["c0"] + fc["L"] / fc["s"] / 2 + xu / fc["s"]
            Z = lambda zu: fc["H"] - zu / fc["s"]
            dr.rectangle([X(x0), Z(z1), X(x1), Z(z0)], outline=(255, 160, 0), width=2)
        im.save(out / "work/trace" / ("overlay-%s.png" % k))
        im.thumbnail((1200, 1200))
        im.convert("RGB").save(out / "preview" / ("trace-overlay-%s.jpg" % k), quality=88)
    lay = Image.fromarray(np.clip(np.round(BC), 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(lay)
    for key, (x, y, w, h) in rects.items():
        dr.rectangle([x, y, x + w - 1, y + h - 1], outline=(255, 230, 30))
        dr.text((x + 3, y + 1), key, fill=(255, 230, 30))
    lay.save(out / "preview" / "atlas-layout.jpg", quality=88)
    (out / "reports" / "trace.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("TRACE_OK", json.dumps({f["key"]: [f["length_uu"], f["height_uu"], f["polygon_vertices"]] for f in report["facades"]}))


if __name__ == "__main__":
    main()
