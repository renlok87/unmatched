#!/usr/bin/env python3
"""Map-surface textures for the original-map boards (ENV-MAPS, track S-prep). CPU only.

For every map (Marmoreal, Sarpedon) from the original illustration (1337x866 WebP, kept OUT of
git, ENV-U3) and the committed topology numbers:

  1. BC    - logo 'UNMATCHED <MAP>' painted out (exemplar fill + Poisson seam stitching),
             Lanczos resize to 4096x4096 (x3.06 / x4.73, UV = whole image) + light unsharp.
  2. SDF   - RGBA16 4096^2, same UV: R ring discs (signed), G zone dividers, B connection
             centre-lines, A union of the game layer (signed); 512 codes per source px.
  3. ID    - R16 4096^2 space index (0 = none, 1..N = topology id order); game-layer mask L8
             (circles + lines + start diamonds dilated by 6 px).
  4. K1    - perspective mocks 1920x1080 (numpy pinhole, S08 K1 camera) a/b/c + measurements.

Textures go to <main checkout>/scraped-data/derived/maps/<key>/ (gitignored), mocks to
C:/tmp/envmaps-research/k1-mocks/ (out of git). Only numbers are written next to this script:
<key>.vector-layer.json (measured vector layer) and manifest.<key>.json (hashes/sizes/params).
The manifest names outputs by canonical roots (ROOTS), not by the --derived / --mocks used.

Usage:  python -B tools/art/map_surface/build_map_textures.py [--maps marmoreal sarpedon]
        python -B tools/art/map_surface/build_map_textures.py --refresh-k1 [--maps ...] [--derived <dir>]
The K1 night grade (mocks b / c, manifest k1.grade_b_c) is the ENGINE grade: the light profile's "mapGrade" of the
map-image board in unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json (k1_mock.profile_map_grade, ENV-MAPS
P4). --refresh-k1 re-renders only the K1 mocks with that grade from the already built BC / mask (sha256 checked against
the manifest, read only) and updates k1.grade_b_c / k1.mocks / k1.measurement.grade_b_vs_a_ev; every other manifest
field and every texture stays as it is.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
import PIL
from PIL import Image, ImageDraw, features
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import inpaint  # noqa: E402
import k1_mock  # noqa: E402
import png16  # noqa: E402
import raster  # noqa: E402
import vector_layer as vl  # noqa: E402
from art_board_fixtures import decode_devalue_maps  # noqa: E402  (read-only reuse)

REPO = HERE.parents[2]
MAIN = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
GENERATOR = "tools/art/map_surface/build_map_textures.py"
# the manifest names outputs by these canonical roots, not by where a build wrote them, so a build
# with --derived / --mocks elsewhere records the same manifest (the sha256 identify the bytes)
DERIVED_REL = "scraped-data/derived/maps"
MOCKS = "<mocks>"
ROOTS = {
    DERIVED_REL: "main checkout, gitignored (ENV-U3); textures imported into UE by script",
    MOCKS: "K1 review artefacts (mocks, a|b split, EV map, logo before/after, SDF overlay crops), out "
           "of git, not imported anywhere; default --mocks C:/tmp/envmaps-research/k1-mocks",
}
SRC_W, SRC_H = 1337, 866
UU_PER_PX = 2.0 / 3.0
TEX = 4096

MAPS = {
    "marmoreal": {
        "name": "Marmoreal",
        # logo box incl. anti-aliasing, [x0, y0, x1, y1) source px
        "logo_rect": [22, 807, 193, 856],
        "inpaint": {"data_term_floor": 0.02, "protect_disc_r_px": 72.0, "protect_line_w_px": 18,
                    "source_exclude": [], "class_rule": None, "band_refill_px": 0},
    },
    "sarpedon": {
        "name": "Sarpedon",
        "logo_rect": [22, 807, 182, 856],
        # the logo sits on the foliage/grass border under the palisade: palisade (warm) and its
        # grey ground shadow are not used as exemplars; fill guided by a foliage/grass class
        # map (blue > red) extended harmonically from the hole border, then the class seam band
        # is re-filled once so the foliage edge is copied from real foliage edges
        "inpaint": {"data_term_floor": 0.3, "protect_disc_r_px": 67.0, "protect_line_w_px": 12,
                    "source_exclude": ["warm", "lowsat:0.25"], "class_rule": "b_gt_r",
                    "class_noise": [0.25, 4.0], "band_refill_px": 6},
    },
}

BC = {"resample": "PIL LANCZOS (float32 per channel), 1337x866 -> 4096x4096 in one step",
      "unsharp_sigma_src_px": 0.7, "unsharp_amount": 0.35}
SDF = {"codes_per_src_px": 512.0, "clamp_src_px": 64.0, "zero_code": 32768}
MASK = {"dilate_src_px": 6.0, "soft_src_px": 1.0}
# Pre-P4 mock grade (S-prep; the MI defaults of graph v1). Since ENV-MAPS P4 the mocks use the profile mapGrade
# (k1_mock.profile_map_grade); this stays only as the documented origin of the M_MapBoard parameter defaults.
GRADE_SPREP = {"ev": -0.7, "saturation": 0.7, "tint_srgb_mul": [0.90, 0.97, 1.12], "lift": 0.35}
GRADE_FORMULA = ("lit = albedo * 2^ev * tint_lin; outside = desaturate(lit, saturation); inside = saturate(lit * "
                 "mask_inverse_tint_lin, mask_saturation) + lift * saturate(albedo, lift_saturation) (unlit / emissive "
                 "share); mix by GameMask (= M_MapBoard graph v2, tools/art/map_surface/ue_import_map_surface.py)")
K1 = {"width": 1920, "height": 1080, "ss": 3, "tray_rim_uu": 60.0, "tray_height_uu": 150.0,
      "rock_srgb": [0.235, 0.225, 0.215], "bg_top_srgb": [0.055, 0.066, 0.105],
      "bg_bottom_srgb": [0.012, 0.015, 0.026],
      "ring": {"outer_r_uu": 28.5, "inner_r_uu": 23.0, "rim_uu": 1.2, "intensity": 0.95,
               "gold_srgb": [0.95, 0.74, 0.28], "silver_blue_srgb": [0.66, 0.78, 0.93]},
      "hero": {"height_uu": 50.0, "base_diameter_uu": 40.0, "albedo_lin": 0.30}}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text_lf(p: Path) -> str:
    """sha256 of a committed text file with CRLF -> LF, i.e. of its git content: core.autocrlf
    checks the ENV-MAPS evidence out as CRLF on Windows and LF elsewhere."""
    return sha256_bytes(p.read_bytes().replace(b"\r\n", b"\n"))


def write_bytes(p: Path, data: bytes) -> dict:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return {"bytes": len(data), "sha256": sha256_bytes(data)}


def pil_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=6)
    return buf.getvalue()


def rel_main(p: Path) -> str:
    try:
        return p.resolve().relative_to(MAIN.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def dump_json(p: Path, doc) -> str:
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    p.write_text(text, encoding="utf-8", newline="\n")
    return sha256_bytes(text.encode("utf-8"))


# ------------------------------------------------------------------ 1. vector layer
def build_vector_layer(key: str, rgb: np.ndarray, topo: dict, map_rec: dict) -> dict:
    spaces = topo["spaces"]
    dk = vl.darkness(rgb)
    ring0 = vl.measure_ring(dk, spaces)
    fits = vl.fit_ring_centres(dk, spaces, ring0["r_center_px"])
    painted = [dict(s, px=[s["px"][0] + f["dx"], s["px"][1] + f["dy"]]) for s, f in zip(spaces, fits)]
    ring = vl.measure_ring(dk, painted)
    r = ring["r_center_px"]
    rays = vl.dividers_from_svg(map_rec, spaces, r)
    dcheck = vl.measure_dividers(rgb, spaces, rays, r)
    byid_t = {s["id"]: s for s in spaces}
    byid_p = {s["id"]: s for s in painted}
    dividers = {}
    for sid, angs in rays.items():
        A = np.array(byid_t[sid]["px"])
        C = np.array(byid_p[sid]["px"])
        per = []
        for a, chk in zip(angs, dcheck["per_space"][sid]):
            u = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
            # A + t u on the painted ring (the apex is the SVG centre, the ring the painted one)
            dd = A - C
            b = float(u @ dd)
            t = -b + math.sqrt(b * b - (float(dd @ dd) - r * r))
            e = A + t * u
            per.append({"angle_deg": a, "apex_px": [round(float(A[0]), 3), round(float(A[1]), 3)],
                        "end_px": [round(float(e[0]), 3), round(float(e[1]), 3)],
                        "painted_offset_px": chk["offset_px"], "painted_fwhm_px": chk["fwhm_px"]})
        dividers[sid] = per
    conns = vl.trace_edges(rgb, painted, topo["edges"], r)
    lw = vl.measure_line_width(rgb, conns)
    dia = vl.find_diamonds(rgb, painted, r)
    arcs = sorted(k for k, v in conns.items() if v["kind"] == "arc")
    interrupted = sorted(k for k, v in conns.items() if v["method"] != "geodesic-fit")
    return {
        "schema": "unmatched.map-vector-layer/1",
        "map": key,
        "generator": GENERATOR,
        "status": "measured (vector game layer of the original illustration; not game rules)",
        "coords": "continuous source px of the 1337x866 illustration (pixel (i,j) covers [j,j+1]x[i,i+1]); "
                  "y down; angles = atan2(dy, dx) in degrees",
        "uu_per_px": round(UU_PER_PX, 6),
        "world_mapping": "X = (x/1337 - 0.5) * 891.333, Y = (y/866 - 0.5) * 577.333 uu (UE, board centre = origin, "
                         "image top = far/-Y, as S08 CellToWorld with the K1 camera at yaw -90)",
        "ring": ring,
        "ring_initial_topology_centres": ring0,
        "spaces": [{"id": s["id"], "topology_px": s["px"], "painted_px": [round(p["px"][0], 3), round(p["px"][1], 3)],
                    "dx": f["dx"], "dy": f["dy"], "own_best_r_px": f["own_best_r_px"],
                    "ring_contrast_topology": f["contrast_topology"], "ring_contrast_painted": f["contrast_fitted"]}
                   for s, p, f in zip(spaces, painted, fits)],
        "dividers": dividers,
        "divider_check": {"abs_offset_px_median": dcheck["abs_offset_px_median"],
                          "abs_offset_px_max": dcheck["abs_offset_px_max"],
                          "note": "perpendicular offset of the painted divider stroke from the SVG ray, "
                                  "measured on the image; apex = SVG/topology centre"},
        "connections": conns,
        "connection_summary": {"count": len(conns), "arcs": arcs,
                               "straight": sum(1 for v in conns.values() if v["kind"] == "straight"),
                               "interrupted_stroke": interrupted,
                               "min_coverage_geodesic": min(v["coverage"] for v in conns.values()
                                                            if v["method"] == "geodesic-fit")},
        "line_width": lw,
        "start_diamonds": dia,
        "params": {"vector_layer": vl.PARAMS},
    }


# ------------------------------------------------------------------ 2. logo paint-out
def paint_out_logo(key: str, rgb: np.ndarray, vec: dict, cfg: dict) -> tuple[np.ndarray, dict]:
    ic = cfg["inpaint"]
    H, W = rgb.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W] + 0.5
    prot = np.zeros((H, W), bool)
    for s in vec["spaces"]:
        cx, cy = s["painted_px"]
        prot |= (xx - cx) ** 2 + (yy - cy) ** 2 < ic["protect_disc_r_px"] ** 2
    im = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(im)
    for rec in vec["connections"].values():
        dr.line([tuple(p) for p in rec["polyline_px"]], fill=255, width=ic["protect_line_w_px"])
    prot |= np.asarray(im) > 0
    prot_src = prot.copy()
    for rule in ic["source_exclude"]:
        if rule == "warm":
            prot_src |= ndimage.binary_dilation(rgb[..., 0] > rgb[..., 1] + 0.02, iterations=2)
        elif rule.startswith("lowsat:"):
            mx, mn = rgb.max(2), rgb.min(2)
            sat = (mx - mn) / np.maximum(mx, 1e-6)
            prot_src |= ndimage.binary_dilation(ndimage.uniform_filter(sat, 5) < float(rule.split(":")[1]),
                                                iterations=2)
        else:
            raise ValueError(rule)
    x0, y0, x1, y1 = cfg["logo_rect"]
    hole = np.zeros((H, W), bool)
    hole[y0:y1, x0:x1] = True
    inpaint.PARAMS["data_term_floor"] = ic["data_term_floor"]
    cls = None
    if ic["class_rule"]:
        cls = inpaint.class_map(rgb, hole, ic["class_rule"], noise_amp=ic["class_noise"][0],
                                noise_sigma=ic["class_noise"][1])
    out, st = inpaint.inpaint(rgb, hole, prot_src, cls=cls)
    stats = {"pass1": st}
    if ic["band_refill_px"]:
        m = ndimage.uniform_filter(out, size=(5, 5, 1))
        rc = m[..., 2] > m[..., 0]
        edge = hole & (ndimage.binary_dilation(rc) != ndimage.binary_erosion(rc))
        rng = np.random.default_rng(1)
        nz = ndimage.gaussian_filter(rng.standard_normal((H, W)), 3.0)
        nz /= nz.std()
        band = ndimage.binary_dilation(edge, iterations=ic["band_refill_px"]) & hole
        band &= ~((nz < -1.0) & ~edge)
        out, st2 = inpaint.inpaint(out, band, prot)
        stats["band_refill"] = st2
    stats["params"] = {**ic, "rect_src_px": cfg["logo_rect"], "patch_px": inpaint.PARAMS["patch_px"],
                       "search_px": inpaint.PARAMS["search_px"], "poisson_seams": inpaint.PARAMS["poisson_seams"]}
    return out, stats


# ------------------------------------------------------------------ 3. BC
def make_bc(rgb: np.ndarray) -> np.ndarray:
    chans = []
    sx = BC["unsharp_sigma_src_px"] * TEX / SRC_W
    sy = BC["unsharp_sigma_src_px"] * TEX / SRC_H
    for c in range(3):
        ch = Image.fromarray(rgb[..., c].astype(np.float32), mode="F").resize((TEX, TEX), Image.LANCZOS)
        a = np.asarray(ch, np.float32)
        blur = ndimage.gaussian_filter(a, sigma=(sy, sx), mode="nearest")
        a = a + BC["unsharp_amount"] * (a - blur)
        chans.append(np.clip(np.round(a * 255.0), 0, 255).astype(np.uint8))
    return np.stack(chans, axis=-1)


# ------------------------------------------------------------------ 4. SDF / ID / mask
def make_layers(vec: dict) -> dict:
    g = raster.Grid(TEX, SRC_W, SRC_H, SDF["clamp_src_px"])
    ring = vec["ring"]
    r = ring["r_center_px"]
    centres = [tuple(s["painted_px"]) for s in vec["spaces"]]
    R = raster.discs_sdf(g, centres, r)
    divs = [(tuple(d["apex_px"]), tuple(d["end_px"])) for per in vec["dividers"].values() for d in per]
    G = raster.segments_dist(g, divs)
    straight = [(tuple(c["polyline_px"][0]), tuple(c["polyline_px"][-1]))
                for c in vec["connections"].values() if c["kind"] == "straight"]
    B = raster.segments_dist(g, straight)
    arcs = [(c["arc_center_px"][0], c["arc_center_px"][1], c["arc_radius_px"],
             math.radians(c["arc_start_deg"]), math.radians(c["arc_sweep_deg"]))
            for c in vec["connections"].values() if c["kind"] == "arc"]
    raster.arcs_dist(g, arcs, B)
    ring_hw = ring["width_fwhm_px"] / 2.0
    line_hw = vec["line_width"]["core_fwhm_px"] / 2.0
    A = np.minimum(R - ring_hw, B - line_hw)
    dia = [(d["center_px"][0], d["center_px"][1], d["half_diagonal_px"]) for d in vec["start_diamonds"]]
    raster.diamonds_sdf(g, dia, A)
    sc = SDF["codes_per_src_px"]
    sdf16 = np.stack([raster.encode_sdf16(x, sc) for x in (R, G, B, A)], axis=-1)
    r_id = ring["r_outer_px"]
    ids = raster.id_map(g, centres, r_id)
    m = np.clip((MASK["dilate_src_px"] - A) / MASK["soft_src_px"] + 0.5, 0.0, 1.0)
    mask8 = np.round(m * 255).astype(np.uint8)
    return {"sdf16": sdf16, "ids": ids, "mask8": mask8, "A": A, "R": R, "B": B, "G": G,
            "r_id": r_id, "ring_hw": ring_hw, "line_hw": line_hw}


# ------------------------------------------------------------------ 5. K1
def k1_grade(key: str) -> dict:
    """The engine night grade of a map (the profile mapGrade, k1_mock.profile_map_grade) in the k1_mock format."""
    return k1_mock.profile_map_grade(key)


def grade_record(grade: dict) -> dict:
    """manifest k1.grade_b_c: the profile grade the mocks b / c were rendered with (ue_import_map_surface.py writes
    the same values into MI_<Name>_MapBoard). tint_lin_luma_normalised keeps the import contract's key: the profile
    tint is used verbatim (it is linear and already ~luma 1)."""
    return {"source": grade["source"], "ev": grade["ev"], "saturation": grade["saturation"], "lift": grade["lift"],
            "tint_lin": grade["tint_lin"], "tint_lin_luma_normalised": grade["tint_lin"],
            "mask_saturation": grade["mask_saturation"], "lift_saturation": grade["lift_saturation"],
            "mask_inverse_tint_lin": grade["mask_inverse_tint_lin"], "formula": GRADE_FORMULA,
            "note": "the mock lights the map with 2^ev * tint only (no key / moon-pool / sky lights, no tonemapper): "
                    "same grade parameters as the engine, not the engine render"}


def k1_layout(vec: dict, topo: dict, grade: dict) -> dict:
    mx, my = SRC_W * UU_PER_PX / 2, SRC_H * UU_PER_PX / 2
    starts = {s["start"]: s for s in topo["spaces"] if s.get("start")}
    painted = {s["id"]: s["painted_px"] for s in vec["spaces"]}

    def world(px):
        return ((px[0] / SRC_W - 0.5) * 2 * mx, (px[1] / SRC_H - 0.5) * 2 * my)

    rg = K1["ring"]
    heroes, rings = [], []
    for k, colr in ((1, rg["gold_srgb"]), (2, rg["silver_blue_srgb"])):
        x, y = world(painted[starts[k]["id"]])
        rings.append({"x": x, "y": y, "r_in": rg["inner_r_uu"], "r_out": rg["outer_r_uu"], "rim": rg["rim_uu"],
                      "srgb": colr, "intensity": rg["intensity"], "space": starts[k]["id"], "start": k})
        heroes.append({"x": x, "y": y, "albedo_lin": K1["hero"]["albedo_lin"], "space": starts[k]["id"]})
    return {"map_half_uu": (mx, my), "tray_rim_uu": K1["tray_rim_uu"], "tray_height_uu": K1["tray_height_uu"],
            "rock_srgb": K1["rock_srgb"], "bg_top_srgb": K1["bg_top_srgb"], "bg_bottom_srgb": K1["bg_bottom_srgb"],
            "grade": {k: grade[k] for k in ("ev", "saturation", "tint_lin", "lift", "mask_saturation",
                                            "lift_saturation", "mask_inverse_tint_lin")},
            "heroes": heroes, "rings": rings}


def k1_measure(cam: k1_mock.Camera, ids: np.ndarray, vec: dict, layout: dict) -> dict:
    """Render the ID map through the K1 camera (1 sample per pixel, nearest) and measure every
    space's on-screen extent -> screen px per source px (horizontal = width / diameter,
    vertical = height / diameter, the latter foreshortened by the 55 deg pitch)."""
    mx, my = layout["map_half_uu"]
    on, u, v = k1_mock.screen_uv(cam, layout, TEX)
    scr = np.where(on, ids[v, u], 0)
    diam = 2 * vec_r_id(vec)
    per = []
    for k, s in enumerate(vec["spaces"], start=1):
        ys, xs = np.nonzero(scr == k)
        if len(xs) == 0:
            per.append({"id": s["id"], "visible": False})
            continue
        w = xs.max() - xs.min() + 1
        h = ys.max() - ys.min() + 1
        per.append({"id": s["id"], "screen_centre": [round(float(xs.mean()), 1), round(float(ys.mean()), 1)],
                    "w_px": int(w), "h_px": int(h), "h_per_src_px": round(w / diam, 3),
                    "v_per_src_px": round(h / diam, 3)})
    vis = [p for p in per if p.get("visible", True)]
    hs = np.array([p["h_per_src_px"] for p in vis])
    vs = np.array([p["v_per_src_px"] for p in vis])
    cy = np.array([p["screen_centre"][1] for p in vis])
    far = [p for p in vis if p["screen_centre"][1] <= np.percentile(cy, 20)]
    near = [p for p in vis if p["screen_centre"][1] >= np.percentile(cy, 80)]
    corners = {name: [round(float(c), 1) for c in cam.project([[sx * mx, sy * my, 0.0]])[0]]
               for name, (sx, sy) in {"far_left": (-1, -1), "far_right": (1, -1),
                                      "near_left": (-1, 1), "near_right": (1, 1)}.items()}
    tx, ty = mx + K1["tray_rim_uu"], my + K1["tray_rim_uu"]
    tray = {name: [round(float(c), 1) for c in cam.project([[sx * tx, sy * ty, z]])[0]]
            for name, (sx, sy, z) in {"far_left": (-1, -1, 0), "far_right": (1, -1, 0),
                                      "near_left_top": (-1, 1, 0), "near_right_top": (1, 1, 0),
                                      "near_left_bottom": (-1, 1, -K1["tray_height_uu"]),
                                      "near_right_bottom": (1, 1, -K1["tray_height_uu"])}.items()}

    def analytic(px_x, px_y):
        wx, wy = (px_x / SRC_W - 0.5) * 2 * mx, (px_y / SRC_H - 0.5) * 2 * my
        p0 = cam.project([[wx, wy, 0.0]])[0]
        ph = cam.project([[wx + UU_PER_PX, wy, 0.0]])[0]
        pv = cam.project([[wx, wy + UU_PER_PX, 0.0]])[0]
        return {"h": round(float(np.linalg.norm(ph - p0)), 3), "v": round(float(np.linalg.norm(pv - p0)), 3)}

    return {
        "method": "space ID map rendered through the K1 camera at 1920x1080 (nearest), bbox of each disc / "
                  f"diameter {diam:.2f} src px",
        "h_per_src_px": {"min": round(float(hs.min()), 3), "median": round(float(np.median(hs)), 3),
                         "max": round(float(hs.max()), 3)},
        "v_per_src_px": {"min": round(float(vs.min()), 3), "median": round(float(np.median(vs)), 3),
                         "max": round(float(vs.max()), 3)},
        "far_row_h_v": [round(float(np.median([p["h_per_src_px"] for p in far])), 3),
                        round(float(np.median([p["v_per_src_px"] for p in far])), 3)],
        "near_row_h_v": [round(float(np.median([p["h_per_src_px"] for p in near])), 3),
                         round(float(np.median([p["v_per_src_px"] for p in near])), 3)],
        "analytic_check": {"centre": analytic(SRC_W / 2, SRC_H / 2), "far_edge_mid": analytic(SRC_W / 2, 0.0),
                           "near_edge_mid": analytic(SRC_W / 2, SRC_H)},
        "map_corners_screen_px": corners,
        "tray_corners_screen_px": tray,
        "per_space": per,
    }


def vec_r_id(vec: dict) -> float:
    return vec["ring"]["r_outer_px"]


# ------------------------------------------------------------------ checks / previews (out of git)
def overlay_checks(key: str, bc: np.ndarray, layers: dict, vec: dict, out_dir: Path) -> list[str]:
    """1:1 texel crops of the BC with the SDF strokes drawn on top (cyan ring, red lines,
    magenta dividers, yellow diamonds) to eyeball the alignment."""
    out_dir.mkdir(parents=True, exist_ok=True)
    R, B, G, A = layers["R"], layers["B"], layers["G"], layers["A"]
    files = []
    picks = []
    conns = vec["connections"]
    arcs = vec["connection_summary"]["arcs"]
    interrupted = vec["connection_summary"]["interrupted_stroke"]
    for e in arcs[:4] + interrupted[:2]:
        pts = np.array(conns[e]["polyline_px"])
        picks.append((e, pts.mean(0)))
    for d in vec["start_diamonds"][:2]:
        picks.append((f"start{d['start']}", np.array(d["center_px"])))
    half = 300
    for name, (cx, cy) in picks:
        j = int(cx / SRC_W * TEX)
        i = int(cy / SRC_H * TEX)
        i0, j0 = max(0, i - half), max(0, j - half)
        i1, j1 = min(TEX, i0 + 2 * half), min(TEX, j0 + 2 * half)
        img = bc[i0:i1, j0:j1].astype(np.float32).copy()
        ring = np.abs(R[i0:i1, j0:j1]) < 0.35
        line = (np.abs(B[i0:i1, j0:j1] - layers["line_hw"]) < 0.3) & (R[i0:i1, j0:j1] > 0)
        div = (G[i0:i1, j0:j1] < 0.3) & (R[i0:i1, j0:j1] < 0)
        dia = (np.abs(A[i0:i1, j0:j1]) < 0.3) & (R[i0:i1, j0:j1] > 1.5) & (B[i0:i1, j0:j1] > layers["line_hw"] + 1)
        for msk, colr in ((ring, (0, 255, 255)), (line, (255, 40, 40)), (div, (255, 0, 255)), (dia, (255, 255, 0))):
            img[msk] = colr
        p = out_dir / f"{key}-sdf-{name}.png"
        Image.fromarray(img.astype(np.uint8)).save(p)
        files.append(f"{MOCKS}/{out_dir.name}/{p.name}")
    return files


def logo_before_after(key: str, before: np.ndarray, after: np.ndarray, rect, out: Path) -> str:
    x0, y0, x1, y1 = rect
    bx0, by0 = max(0, x0 - 22), max(0, y0 - 70)
    bx1, by1 = min(SRC_W, x1 + 110), SRC_H
    s = 4
    a = Image.fromarray((np.clip(before, 0, 1) * 255 + 0.5).astype(np.uint8)).crop((bx0, by0, bx1, by1))
    b = Image.fromarray((np.clip(after, 0, 1) * 255 + 0.5).astype(np.uint8)).crop((bx0, by0, bx1, by1))
    a = a.resize((a.width * s, a.height * s), Image.NEAREST)
    b = b.resize((b.width * s, b.height * s), Image.NEAREST)
    c = Image.new("RGB", (a.width, a.height * 2 + 8), (200, 30, 30))
    c.paste(a, (0, 0))
    c.paste(b, (0, a.height + 8))
    c.save(out)
    return f"{MOCKS}/{out.name}"


# ------------------------------------------------------------------ main
def k1_mocks(key: str, cam: "k1_mock.Camera", layout: dict, bc: np.ndarray, mask8: np.ndarray, mocks: Path):
    """K1 mocks a / b / c, the a|b split and the b/a EV map of one map (written to <mocks>); returns the manifest
    k1.mocks block and k1.measurement.grade_b_vs_a_ev."""
    mocks.mkdir(parents=True, exist_ok=True)
    lin = k1_mock.srgb_to_lin(bc.astype(np.float32) / 255.0)
    maps = {"mips": k1_mock.build_mips(lin), "mask_mips": k1_mock.build_mips(mask8.astype(np.float32) / 255.0)}
    del lin
    mock_info = {}
    frames = {}
    for variant in ("a", "b", "c"):
        fr = k1_mock.render(cam, maps, layout, variant, ss=K1["ss"])
        frames[variant] = fr
        p = mocks / f"{key}-{variant}.png"
        info = write_bytes(p, pil_png(Image.fromarray(fr, "RGB")))
        mock_info[variant] = {"path": f"{MOCKS}/{p.name}", **info, "width": K1["width"], "height": K1["height"]}
    # a | b split for the difference (left half a, right half b) + luminance ratio b/a map
    split = frames["a"].copy()
    split[:, K1["width"] // 2:] = frames["b"][:, K1["width"] // 2:]
    split[:, K1["width"] // 2 - 1:K1["width"] // 2 + 1] = (255, 255, 255)
    p = mocks / f"{key}-ab-split.png"
    mock_info["ab_split"] = {"path": f"{MOCKS}/{p.name}", **write_bytes(p, pil_png(Image.fromarray(split, "RGB")))}
    la = k1_mock.srgb_to_lin(frames["a"] / 255.0) @ k1_mock.LUMA
    lb = k1_mock.srgb_to_lin(frames["b"] / 255.0) @ k1_mock.LUMA
    ev = np.log2(np.maximum(lb, 1e-4) / np.maximum(la, 1e-4))
    evn = np.clip((ev + 1.0) / 1.2, 0, 1)
    heat = np.stack([evn, evn ** 0.5 * 0.2 + 0.1, 1 - evn], axis=-1)
    p = mocks / f"{key}-ab-ev.png"
    mock_info["ab_ev"] = {"path": f"{MOCKS}/{p.name}", "legend": "log2(b/a) luminance: blue = -1 EV, red = +0.2 EV",
                          **write_bytes(p, pil_png(Image.fromarray((heat * 255).astype(np.uint8), "RGB")))}
    # EV of b vs a inside / outside the game layer, measured on the map pixels of the mocks
    on, us, vs_ = k1_mock.screen_uv(cam, layout, TEX)
    msc = np.where(on, mask8[vs_, us], 0)
    ins, outs = on & (msc >= 250), on & (msc <= 5)
    grade_ev = {"inside_mask_median": round(float(np.median(ev[ins])), 3),
                "outside_mask_median": round(float(np.median(ev[outs])), 3),
                "inside_minus_outside": round(float(np.median(ev[ins]) - np.median(ev[outs])), 3),
                "screen_px_inside": int(ins.sum()), "screen_px_outside": int(outs.sum())}
    return mock_info, grade_ev


def refresh_k1(key: str, a) -> dict:
    """ENV-MAPS P4: re-render the K1 mocks with the profile grade from the built BC / mask (sha256 = manifest) and
    update only k1.grade_b_c, k1.mocks and k1.measurement.grade_b_vs_a_ev of manifest.<key>.json."""
    name = MAPS[key]["name"]
    path = HERE / f"manifest.{key}.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    src = {}
    for layer in ("bc", "mask"):
        p = Path(a.derived) / key / Path(manifest["outputs"][layer]["path"]).name
        if not p.is_file() or sha256_file(p) != manifest["outputs"][layer]["sha256"]:
            raise SystemExit(f"{key}: {p} missing or its sha256 differs from {path.name} (rebuild without --refresh-k1)")
        src[layer] = p
    bc = np.asarray(Image.open(src["bc"]).convert("RGB"))
    mask8 = np.asarray(Image.open(src["mask"]).convert("L"))
    vec = json.loads((HERE / f"{key}.vector-layer.json").read_text(encoding="utf-8"))
    topo = json.loads((REPO / manifest["inputs"]["topology"]["path"]).read_text(encoding="utf-8"))
    grade = k1_grade(key)
    mx, my = SRC_W * UU_PER_PX / 2, SRC_H * UU_PER_PX / 2
    cam = k1_mock.Camera(k1_mock.s08_fit_distance(mx, my), K1["width"], K1["height"])
    layout = k1_layout(vec, topo, grade)
    print(f"[{key}] K1 mocks (refresh, {name}, grade: {grade['source']})", flush=True)
    mock_info, grade_ev = k1_mocks(key, cam, layout, bc, mask8, Path(a.mocks))
    manifest["k1"]["grade_b_c"] = grade_record(grade)
    manifest["k1"]["mocks"] = mock_info
    manifest["k1"]["measurement"]["grade_b_vs_a_ev"] = grade_ev
    dump_json(path, manifest)
    return manifest


def build(key: str, a) -> dict:
    cfg = MAPS[key]
    name = cfg["name"]
    img_path = Path(a.images) / f"{key}.webp"
    topo_path = Path(a.topology) / f"{key}.topology.json"
    topo = json.loads(topo_path.read_text(encoding="utf-8"))
    img_sha = sha256_file(img_path)
    if img_sha != topo["source"]["sha256"]:
        raise SystemExit(f"{key}: image sha256 {img_sha} != topology source {topo['source']['sha256']}")
    maps_doc = json.loads(Path(a.maps_json).read_text(encoding="utf-8"))
    map_rec = next(m for m in decode_devalue_maps(maps_doc) if m.get("key") == key)
    src = Image.open(img_path).convert("RGB")
    if src.size != (SRC_W, SRC_H):
        raise SystemExit(f"{key}: unexpected size {src.size}")
    rgb = np.asarray(src).astype(np.float64) / 255.0
    print(f"[{key}] vector layer", flush=True)
    vec = build_vector_layer(key, rgb, topo, map_rec)
    print(f"[{key}] logo paint-out", flush=True)
    clean, logo_stats = paint_out_logo(key, rgb, vec, cfg)
    mocks = Path(a.mocks)
    mocks.mkdir(parents=True, exist_ok=True)
    ba = logo_before_after(key, rgb, clean, cfg["logo_rect"], mocks / f"{key}-logo-before-after.png")
    print(f"[{key}] BC", flush=True)
    bc = make_bc(clean)
    print(f"[{key}] SDF / ID / mask", flush=True)
    layers = make_layers(vec)
    out_dir = Path(a.derived) / key
    outputs = {}
    files = {
        "bc": (out_dir / f"T_{name}_Map_BC_4K.png", pil_png(Image.fromarray(bc, "RGB")),
               {"width": TEX, "height": TEX, "format": "PNG RGB8 sRGB"}),
        "sdf": (out_dir / f"T_{name}_Map_GameSDF_4K.png", png16.encode_png(layers["sdf16"]),
                {"width": TEX, "height": TEX, "format": "PNG RGBA16 linear",
                 "channels": {"R": "signed distance to the union of ring discs (radius = ring centre-line); "
                                   "negative inside",
                              "G": "distance to the nearest zone-divider ray (apex -> painted ring); use where R < 0",
                              "B": "distance to the nearest connection centre-line (ring to ring)",
                              "A": "signed distance to the game-layer union: discs to the ring outer edge, "
                                   "connection strokes (core width), start diamonds"}}),
        "id": (out_dir / f"T_{name}_Map_SpaceID_4K.png", png16.encode_png(layers["ids"]),
               {"width": TEX, "height": TEX, "format": "PNG Gray16, no filtering",
                "values": "0 = none, k = k-th space of the topology in id order (M01 = 1 ...)"}),
        "mask": (out_dir / f"T_{name}_Map_GameMask_4K.png", pil_png(Image.fromarray(layers["mask8"], "L")),
                 {"width": TEX, "height": TEX, "format": "PNG Gray8 linear",
                  "values": "255 inside the game layer dilated by 6 src px (1 px soft edge)"}),
    }
    for k, (p, data, meta) in files.items():
        info = write_bytes(p, data)
        outputs[k] = {"path": f"{DERIVED_REL}/{key}/{p.name}", **info, **meta}
    # self-check: 16-bit files decode back bit-exactly
    assert np.array_equal(png16.decode_png((out_dir / f"T_{name}_Map_GameSDF_4K.png").read_bytes()), layers["sdf16"])
    assert np.array_equal(png16.decode_png((out_dir / f"T_{name}_Map_SpaceID_4K.png").read_bytes()), layers["ids"])
    checks_dir = mocks / "checks"
    check_files = overlay_checks(key, bc, layers, vec, checks_dir)
    print(f"[{key}] K1 mocks", flush=True)
    mx, my = SRC_W * UU_PER_PX / 2, SRC_H * UU_PER_PX / 2
    dist = k1_mock.s08_fit_distance(mx, my)
    cam = k1_mock.Camera(dist, K1["width"], K1["height"])
    layout = k1_layout(vec, topo, k1_grade(key))
    mock_info, grade_ev = k1_mocks(key, cam, layout, bc, layers["mask8"], mocks)
    meas = k1_measure(cam, layers["ids"], vec, layout)
    meas["grade_b_vs_a_ev"] = grade_ev
    vec_path = HERE / f"{key}.vector-layer.json"
    vec_sha = dump_json(vec_path, vec)
    manifest = {
        "schema": "unmatched.map-surface-manifest/1",
        "map": key,
        "generator": GENERATOR,
        "status": "technical candidate (no art acceptance); textures and mocks are OUT of git (ENV-U3)",
        "roots": ROOTS,
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "scipy": __import__("scipy").__version__, "pillow": PIL.__version__,
                        "libwebp": features.version("webp")},
        "inputs": {
            "image": {"path": rel_main(img_path), "sha256": img_sha, "bytes": img_path.stat().st_size,
                      "size": [SRC_W, SRC_H]},
            "topology": {"path": topo_path.resolve().relative_to(REPO.resolve()).as_posix()
                         if str(topo_path.resolve()).startswith(str(REPO.resolve())) else topo_path.as_posix(),
                         "sha256": sha256_text_lf(topo_path), "sha256_of": "text with LF line ends (git content)"},
            "maps_json": {"path": rel_main(Path(a.maps_json)), "sha256": sha256_file(Path(a.maps_json))},
        },
        "uv": {
            "texture_size": [TEX, TEX],
            "mapping": "UV (0,0)-(1,1) = the whole 1337x866 illustration (stretched to the square); texel (i,j) "
                       "centre = source px ((j+0.5)*1337/4096, (i+0.5)*866/4096)",
            "texels_per_src_px": [round(TEX / SRC_W, 6), round(TEX / SRC_H, 6)],
            "src_px_per_texel": [round(SRC_W / TEX, 6), round(SRC_H / TEX, 6)],
            "board_uu": [round(SRC_W * UU_PER_PX, 3), round(SRC_H * UU_PER_PX, 3)],
            "uu_per_src_px": round(UU_PER_PX, 6),
            "texels_per_uu": [round(TEX / (SRC_W * UU_PER_PX), 4), round(TEX / (SRC_H * UU_PER_PX), 4)],
            "world": "UE: X = (u - 0.5) * 891.333, Y = (v - 0.5) * 577.333, Z = 0 (u right, v down = towards "
                     "the K1 camera)",
        },
        "params": {"bc": BC, "sdf": {**SDF, "ring_center_r_px": vec["ring"]["r_center_px"],
                                     "ring_half_width_px": round(layers["ring_hw"], 4),
                                     "line_half_width_px": round(layers["line_hw"], 4),
                                     "decode": "d_src_px = (code - 32768) / 512"},
                   "id": {"r_id_px": round(layers["r_id"], 4), "centres": "painted ring centres"},
                   "mask": MASK},
        "logo_paint_out": {**logo_stats, "before_after": ba},
        "outputs": outputs,
        "vector_layer": {"path": vec_path.relative_to(REPO).as_posix(), "sha256": vec_sha},
        "k1": {
            "camera": {**k1_mock.CAM, "distance_uu": round(dist, 3),
                       "location_uu": [round(float(c), 3) for c in cam.pos],
                       "formula": "SetupCameraForBoard with extents 445.67 x 288.67 uu (891.33 x 577.33 board)",
                       "orientation": "yaw -90 as S08: image upright, long side horizontal, north (image top) far; "
                                      "starts 1/2 end up left/right, not bottom/top as on S08 grids"},
            "scene": {"tray_rim_uu": K1["tray_rim_uu"], "tray_height_uu": K1["tray_height_uu"],
                      "rock_srgb": K1["rock_srgb"], "key_light_rot": list(k1_mock.KEY_LIGHT_ROT),
                      "ring": K1["ring"], "hero": K1["hero"],
                      "rings_on": [{"space": r["space"], "start": r["start"]} for r in layout["rings"]]},
            "grade_b_c": grade_record(k1_grade(key)),
            "render": {"supersampling": K1["ss"], "texture_filter": "trilinear, lod = log2(sqrt(|dUV/dx| |dUV/dy|))"},
            "mocks": mock_info,
            "measurement": meas,
        },
        "checks": {"overlays": check_files, "png16_roundtrip": True},
    }
    dump_json(HERE / f"manifest.{key}.json", manifest)
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", nargs="+", default=list(MAPS))
    ap.add_argument("--images", default=str(MAIN / "scraped-data/images/maps"))
    ap.add_argument("--maps-json", default=str(MAIN / "scraped-data/api/maps.json"))
    ap.add_argument("--topology", default=str(REPO / "docs/game-design/evidence/ENV-MAPS/2026-09-30-research"))
    ap.add_argument("--derived", default=str(MAIN / "scraped-data/derived/maps"))
    ap.add_argument("--mocks", default="C:/tmp/envmaps-research/k1-mocks")
    ap.add_argument("--refresh-k1", action="store_true",
                    help="only re-render the K1 mocks with the profile mapGrade (BC / mask read from --derived)")
    a = ap.parse_args(argv)
    if a.refresh_k1:
        for key in a.maps:
            m = refresh_k1(key, a)
            print(json.dumps({"map": key, "grade_b_c": m["k1"]["grade_b_c"],
                              "grade_b_vs_a_ev": m["k1"]["measurement"]["grade_b_vs_a_ev"]}, indent=1))
        return 0
    for key in a.maps:
        m = build(key, a)
        print(json.dumps({"map": key, "outputs": {k: (v["path"], v["bytes"], v["sha256"][:16])
                                                   for k, v in m["outputs"].items()},
                          "k1_h_per_src_px": m["k1"]["measurement"]["h_per_src_px"],
                          "k1_v_per_src_px": m["k1"]["measurement"]["v_per_src_px"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
