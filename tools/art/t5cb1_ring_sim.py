#!/usr/bin/env python3
"""Wave 5c-B1 step B1-3: the two-tone team ring (dark keyline + light rim #F2ECDE) - geometry rules and an
anti-aliased synthetic re-paint of the rings on the W5b-R r3 K1 frames, read by the classifier and the ring metrics that
B1-0 registers (t53_readability: classify_shape_v2 = teamShape rev 2, rings_rev2 fraction / fill-vs-keyline,
ring_tile_reference_rev3). Checks a candidate geometry against its own gates BEFORE the UE build.

    python tools/art/t5cb1_ring_sim.py check
    python tools/art/t5cb1_ring_sim.py sweep --out C:/tmp/p0-review/5cb1-sim [--geometries r3,b1-thin,b1] [--blur 0,0.35]

check: the geometry rules (band order, fill start past the target arcs, outer keyline not thinner than r3, rim >= 1 uu,
outer edge + 1 uu <= the nearest zone-glyph piece) for every candidate.
sweep: every shown ring of the r3 K1 frames (3 boards x host / joiner) is re-painted with the candidate bands through
the frame's own projection (the real K1 camera: ~1.45 px per uu at the rings, foreshortened ~0.78 in depth):
ss x ss sub-samples per pixel averaged in linear light (box AA), optional Gaussian blur (TSR softness, sigma px),
screen bytes of the unlit game layer (fill / keyline from the r3 calibration, the rim through ue_filmic), background =
the frame moved to the proposed board light (t5cb1_exposure_sim: dEV -0.75 + key pitch fix, lit pixels only), the local
tile median under the old ring, occluders (wings / figure pixels over the old fill band, dilated 2 px) kept. The 'r3'
candidate at dEV 0 re-paints the frame's own ring and is the check of the renderer against the real metrics.

Everything here is «оценено по имеющимся кадрам» (synthetic paint over real frames), not a capture.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "qa010"))
import t53_team_ring as RING  # noqa: E402

RIM_HEX = "#F2ECDE"
LOOKS = {"P1": "p1", "P2": "p2"}

# Candidate band sets (uu, hero size; sidekicks x 0.78). 'r3' = RING_SPEC of W5b-R (frozen here: B1-3 moves RING_SPEC to 'b1'). 'b1-thin' = the first 5c-B1
# proposal (rejected 2026-09-30: outer keyline thinned to 1.0 / 0.75 uu - AA against the light rim leaves no keyline
# pixel on the helpers). 'b1' = the revised proposal: outer keyline as wide as r3, the rim paid for by the fill.
GEOMETRIES = {
    "r3": {"P1": {"keylineIn": (22.0, 23.5), "fill": (23.5, 26.5), "keylineOut": (26.5, 28.0)},
           "P2": {"keylineIn": (21.5, 23.0), "fill": (23.0, 26.0), "keylineOut": (26.0, 27.0)}},
    "b1-thin": {"P1": {"keylineIn": (22.0, 23.5), "fill": (23.5, 26.5), "keylineOut": (26.5, 27.5), "rimOut": (27.5, 28.5)},
                "P2": {"keylineIn": (21.5, 23.0), "fill": (23.0, 25.5), "keylineOut": (25.5, 26.25), "rimOut": (26.25, 27.25)}},
    "b1": {"P1": {"keylineIn": (22.0, 23.5), "fill": (23.5, 26.0), "keylineOut": (26.0, 27.5), "rimOut": (27.5, 28.5)},
           "P2": {"keylineIn": (21.5, 23.0), "fill": (23.0, 25.25), "keylineOut": (25.25, 26.25), "rimOut": (26.25, 27.25)}},
}
PROPOSAL = "b1"
ORDER = ("keylineIn", "fill", "keylineOut", "rimOut")
# rules (RING_SPEC['why'] of t53_team_ring + the 5c-B1 review): the nearest zone-glyph piece (bars3) is 29.73 uu from a
# P1 centre; a P2 flat at apothem A passes the bars3 corner at 28.32 - A uu
GLYPH_LIMIT_UU = {"P1": 29.73, "P2": 28.32}
MIN_CLEARANCE_UU = 1.0
FILL_START_MIN = {"P1": 23.5, "P2": 23.0}
KEYLINE_OUT_MIN = {"P1": 1.5, "P2": 1.0}  # = r3: the classifier bound, key_core and fill-vs-keyline were calibrated on it
RIM_MIN_UU = 1.0


def check_geometry(geo: dict) -> dict:
    """{look: {'problems': [...], 'clearanceUU', 'widths'}}; an empty problem list = the rules hold."""
    out = {}
    for look, bands in geo.items():
        probs = []
        names = [k for k in ORDER if k in bands]
        for a, b in zip(names, names[1:]):
            if abs(bands[a][1] - bands[b][0]) > 1e-9:
                probs.append(f"{a}/{b} not contiguous ({bands[a][1]} vs {bands[b][0]})")
        widths = {k: round(bands[k][1] - bands[k][0], 4) for k in names}
        if bands["fill"][0] < FILL_START_MIN[look] - 1e-9:
            probs.append(f"fill starts at {bands['fill'][0]} < {FILL_START_MIN[look]} (target arcs)")
        if widths["keylineOut"] < KEYLINE_OUT_MIN[look] - 1e-9:
            probs.append(f"outer keyline {widths['keylineOut']} uu < {KEYLINE_OUT_MIN[look]} (r3 width)")
        if "rimOut" in widths and widths["rimOut"] < RIM_MIN_UU - 1e-9:
            probs.append(f"rim {widths['rimOut']} uu < {RIM_MIN_UU}")
        outer = bands[names[-1]][1]
        clear = round(GLYPH_LIMIT_UU[look] - outer, 4)
        if clear < MIN_CLEARANCE_UU - 1e-9:
            probs.append(f"glyph clearance {clear} uu < {MIN_CLEARANCE_UU}")
        out[look] = {"problems": probs, "clearanceUU": clear, "widths": widths}
    return out


@contextlib.contextmanager
def ring_spec(geo: dict):
    """Temporarily set RING_SPEC bands to a candidate (the t53 metrics read the bands from RING_SPEC)."""
    old = {s: RING.RING_SPEC[s]["bands"] for s in LOOKS.values()}
    try:
        for lk, s in LOOKS.items():
            RING.RING_SPEC[s]["bands"] = {k: list(v) for k, v in geo[lk].items()}
        yield
    finally:
        for s, b in old.items():
            RING.RING_SPEC[s]["bands"] = b


def band_label(look: str, lx, ly, bands: dict, corner_gap: float):
    """Band index (ORDER) per local point (ring frame, hero size) or -1."""
    lab = np.full(lx.shape, -1, np.int8)
    if look == "P1":
        rad = np.hypot(lx, ly)
        for i, k in enumerate(ORDER):
            if k in bands:
                a0, a1 = bands[k]
                lab[(rad >= a0) & (rad < a1)] = i
        return lab
    ang = np.degrees(np.arctan2(ly, lx)) % 360.0
    rad = np.hypot(lx, ly)
    phi = (ang % 60.0) - 30.0  # angle to the nearest flat normal (flats at 30 + 60k, corners at 60k)
    apo = rad * np.cos(np.radians(phi))
    corner = np.round(ang / 60.0) * 60.0
    d_bis = np.abs(rad * np.sin(np.radians(ang - corner)))  # distance to the nearest corner bisector
    for i, k in enumerate(ORDER):
        if k in bands:
            a0, a1 = bands[k]
            lab[(apo >= a0) & (apo < a1) & (d_bis >= corner_gap * 0.5)] = i
    return lab


def paint_rings(shot, geo: dict, colours: dict, ss: int = 4, blur: float = 0.0, bg_rgb=None,
                keep_occluders: bool = True) -> np.ndarray:
    """New frame bytes: every shown ring re-painted with `geo` (see module doc). colours = {'fill': {'P1', 'P2'},
    'keyline', 'rim'} screen bytes. keep_occluders False = a synthetic frame without an old ring (flat tile)."""
    import t53_readability as T
    from qa010lib import color as C
    rgb = (shot.rgb if bg_rgb is None else bg_rgb).copy()
    lin = C.u8_to_linear(rgb)
    orig_lab = shot.lab
    cam = shot.proj.camera
    fwd, right, up = (np.asarray(v, float) for v in cam.axes())
    w, h = cam.viewport
    focal = (w * 0.5) / math.tan(math.radians(cam.hfov_deg) * 0.5)
    pos = np.asarray(cam.pos, float)
    gap = RING.RING_SPEC["p2"]["cornerGapUU"]
    r3 = GEOMETRIES["r3"]
    for fid, f in sorted(shot.fighters.items()):
        info = shot.rings.get(fid)
        if not info or not info["shown"]:
            continue
        look, fs = info["look"], T.fighter_scale(fid)
        cx, cy, z = f.world[0], f.world[1], f.world[2] + RING.RING_SPEC["zMax"]
        outer = max(b[1] for b in geo[look].values())
        edge = [cam.project((cx + (outer + 3) * fs * math.cos(t), cy + (outer + 3) * fs * math.sin(t), z))
                for t in np.linspace(0, 2 * math.pi, 73)]
        xs = [p[0] for p in edge if p]
        ys = [p[1] for p in edge if p]
        x0, x1 = max(int(min(xs)) - 2, 0), min(int(max(xs)) + 3, shot.w)
        y0, y1 = max(int(min(ys)) - 2, 0), min(int(max(ys)) + 3, shot.h)
        if x1 <= x0 or y1 <= y0:
            continue

        def local(px, py):
            d = fwd[None, None, :] + ((px - w * 0.5) / focal)[..., None] * right - ((py - h * 0.5) / focal)[..., None] * up
            t = (z - pos[2]) / d[..., 2]
            wx, wy = pos[0] + t * d[..., 0], pos[1] + t * d[..., 1]
            return (wx - cx) / fs, (wy - cy) / fs

        gy, gx = np.mgrid[y0:y1, x0:x1].astype(float)
        # pixel centres: old ring region, occluders over the old fill band, local tile median
        lxc, lyc = local(gx + 0.5, gy + 0.5)
        old = band_label(look, lxc, lyc, {k: (a - 0.6, b + 0.6) if k in ("keylineIn", "keylineOut") else (a, b)
                                          for k, (a, b) in r3[look].items()}, gap)
        rad = np.hypot(lxc, lyc)
        fill_scr = np.array(colours["fill"][look], np.uint8).reshape(1, 1, 3)
        de_fill = np.linalg.norm(orig_lab[y0:y1, x0:x1] - C.linear_to_lab(C.u8_to_linear(fill_scr))[0, 0], axis=-1)
        occ = (old == 1) & (de_fill > 30.0) & keep_occluders
        for _ in range(2):
            o2 = occ.copy()
            o2[1:] |= occ[:-1]
            o2[:-1] |= occ[1:]
            o2[:, 1:] |= occ[:, :-1]
            o2[:, :-1] |= occ[:, 1:]
            occ = o2 & (rad <= outer + 3.0)
        ring_old = (old >= 0) | ((rad >= r3[look]["keylineIn"][0] - 1.0) & (rad <= max(b[1] for b in r3[look].values()) + 1.0))
        tile_sel = (rad >= 29.5) & (rad <= 33.0) & ~occ
        bg = lin[y0:y1, x0:x1].copy()
        if tile_sel.any():
            bg[ring_old & ~occ] = np.median(lin[y0:y1, x0:x1][tile_sel], axis=0)
        # sub-samples
        acc = np.zeros(bg.shape, float)
        cols = {0: colours["keyline"], 1: colours["fill"][look], 2: colours["keyline"], 3: colours["rim"]}
        cols = {k: C.u8_to_linear(np.array(v, np.uint8).reshape(1, 3))[0] for k, v in cols.items()}
        for i in range(ss):
            for j in range(ss):
                lx, ly = local(gx + (i + 0.5) / ss, gy + (j + 0.5) / ss)
                lab = band_label(look, lx, ly, geo[look], gap)
                smp = bg.copy()
                for k, c in cols.items():
                    smp[lab == k] = c
                acc += smp
        acc /= ss * ss
        if blur > 0:
            from scipy.ndimage import gaussian_filter
            acc = np.stack([gaussian_filter(acc[..., c], blur, mode="nearest") for c in range(3)], -1)
        acc[occ] = lin[y0:y1, x0:x1][occ]
        lin[y0:y1, x0:x1] = acc
    return C.quantize_u8(C.linear_to_srgb(lin))


def rim_screen(hex_: str = RIM_HEX) -> list[int]:
    """Screen bytes of an unlit game-layer colour (ue_filmic model; B1-2 re-measures them on a flat slab)."""
    import ue_filmic as F
    return [int(x) for x in F.game_layer_screen_u8(hex_)]


# B1-2 zone colours rev 5 (plan 5c-B1): the r3 calibration still holds the rev 4 bytes; the tile reference excludes the
# zones of the fighter's own cell BY COLOUR, and the rev 4 gray (136,144,151) sits on the fixture tiles at the proposed
# light (Y' ~157) - the sweep can swap in the model bytes of the rev 5 colours
ZONES_REV5 = {"zone.red": "#EC6650", "zone.gray": "#6B727A"}


def measure(shot, geo_name: str, th: dict, calib: dict, cells, rim_rgb=None) -> list[dict]:
    """teamShape rev 2 with and without the rim bound, rings rev 2 fraction / fill-vs-keyline, rev 3 edge, pixel counts."""
    import t53_readability as T
    geo = GEOMETRIES[geo_name]
    pde = th["calibration"]["pixelDeltaE"]
    has_rim = "rimOut" in geo["P1"]
    rim = ({"screen": list(rim_rgb or rim_screen()), "bands": {lk: [geo[lk]["rimOut"]] for lk in LOOKS}}
           if has_rim else None)
    rows = []
    with ring_spec(geo):
        r2 = {r["fighter"]: r for r in T.rings_rev2(shot, th, calib, cells)["fighters"] if "look" in r}
        r3 = {r["fighter"]: r for r in T.rings_rev3(shot, calib, cells, pde, rim=rim)["fighters"]}
        for fid, row in r3.items():
            look = row["look"]
            f = shot.fighters[fid]
            fs = T.fighter_scale(fid)
            z = f.world[2] + RING.RING_SPEC["zMax"]
            masks = T.variant_masks(shot, look, calib, pde)
            no_rim = {vn: T.classify_shape_v2(shot, fid, tm, km, fs, z) for vn, (tm, km) in masks.items()}
            kb = geo[look]["keylineOut"]
            out_band = shot.mask_of(shot.pixels(T.band_samples(look, kb[0], kb[1], fs, f.world, z)))
            fill_band = shot.mask_of(shot.pixels(T.band_samples(look, *geo[look]["fill"], fs, f.world, z)))
            key_out_px = int((out_band & ~fill_band & (shot.de_to(calib["mark.keyline"]["screen"]) <= pde)).sum())
            o = r2[fid]
            ref = row["tileReference"]
            rows.append({
                "fighter": fid, "name": row["name"], "look": look, "scale": fs, "expectedShape": row["expectedShape"],
                "shape": row["shape"], "filled": {vn: d["filled"] for vn, d in row["shapeDetail"].items()},
                "shapeNoRimBound": {vn: s["shape"] for vn, s in no_rim.items()},
                "filledNoRimBound": {vn: s.get("filled") for vn, s in no_rim.items()},
                "shapePassAllVariants": row["shapePassAllVariants"],
                "fraction": o["fraction"], "minFraction": o["minFraction"], "fractionPass": o["fractionPass"],
                "fillVsKeyline": {vn: o["variants"][vn]["fillVsKeyline"] for vn in ("color", "gray", "deuteranopia")},
                "keylineCorePx": ref["keylinePx"], "outerKeylineCorePx": key_out_px, "rimPx": ref.get("rimPx"),
                "tilePx": ref["tilePx"],
                "edgeVsTile": {vn: ref[vn]["edgeVsTile"] for vn in ("color", "gray", "deuteranopia")},
                "keylineVsTile": {vn: ref[vn]["keylineVsTile"] for vn in ("color", "gray", "deuteranopia")},
                "rimVsTile": {vn: ref[vn].get("rimVsTile") for vn in ("color", "gray", "deuteranopia")},
                "edgeVsTilePass": row["edgeVsTilePass"]})
    return rows


def summary(rows: list[dict]) -> dict:
    vs = ("color", "gray", "deuteranopia")
    return {"rings": len(rows),
            "shapeAllVariants": sum(r["shapePassAllVariants"] for r in rows),
            "shapeAllVariantsNoRimBound": sum(all(r["shapeNoRimBound"][v] == r["expectedShape"] for v in vs) for r in rows),
            "minFilledRays": min(min(r["filled"].values()) for r in rows),
            "fractionPass": sum(r["fractionPass"] for r in rows),
            "fractionMinSidekick": min((r["fraction"] for r in rows if r["scale"] < 1), default=None),
            "fractionMinHero": min((r["fraction"] for r in rows if r["scale"] == 1), default=None),
            "fillVsKeylineMin": min(min(x for x in r["fillVsKeyline"].values() if x is not None) for r in rows),
            "edgeVsTilePass": sum(r["edgeVsTilePass"] for r in rows),
            "edgeVsTileMin": min(min(x for x in r["edgeVsTile"].values() if x is not None) for r in rows),
            "outerKeylineCorePxMin": min(r["outerKeylineCorePx"] for r in rows),
            "rimPxMin": min((r["rimPx"] for r in rows if r["rimPx"] is not None), default=None)}


def cmd_check(a) -> int:
    res = {name: check_geometry(g) for name, g in GEOMETRIES.items()}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if not any(res[PROPOSAL][lk]["problems"] for lk in LOOKS) else 1


def cmd_sweep(a) -> int:
    import t52_art3_live as T52
    import t53_readability as T
    import t5cb1_exposure_sim as S
    import ue_filmic as F
    out = Path(a.out)
    th = json.loads((S.E_R2 / "t53-thresholds.json").read_text(encoding="utf-8"))
    calib = th["calibration"]["bytes"]
    if a.zones_rev5:
        calib = dict(calib, **{k: {"hex": v, "screen": rim_screen(v)} for k, v in ZONES_REV5.items()})
        th = dict(th, calibration=dict(th["calibration"], bytes=calib))
    colours = {"fill": {"P1": calib["team.p1.fill"]["screen"], "P2": calib["team.p2.fill"]["screen"]},
               "keyline": calib["mark.keyline"]["screen"], "rim": rim_screen(a.rim_hex)}
    geos = a.geometries.split(",")
    blurs = [float(x) for x in a.blur.split(",")]
    doc = {"schema": "unmatched.t5cb1-ring-sim/1", "status": "оценено по имеющимся кадрам (синтетика поверх r3), не захват",
           "method": __doc__.split("\n\n")[2].strip(), "colours": colours, "rimHex": a.rim_hex,
           "zonesRev5": ZONES_REV5 if a.zones_rev5 else None, "exposureEv": a.ev,
           "cases": "'real r3 @0' = the frame as captured; 'r3 @0 blurS' = r3 bands re-painted on it (renderer check); "
                    "'<geometry> @light blurS' = re-painted on the frame moved to the proposed light (boardEv)",
           "geometries": {g: {"bands": GEOMETRIES[g], "rules": check_geometry(GEOMETRIES[g])} for g in geos},
           "boards": {}}
    for key, runp in S.R3_K1.items():
        if a.boards and key not in a.boards.split(","):
            continue
        run = S.E_R2 / runp
        cells = T52.board_cells(T.T52_EVIDENCE if key == "cobble-5x6" else S.E_R2, key)
        zone_keys = sorted({z for c in cells for z in c["zones"]})
        for side in a.sides.split(","):
            shot = T.Shot(run / f"phase2-board-{side}-1920x1080.png", run / f"phase2-client-{side}.trace.log")
            real = measure(shot, "r3", th, calib, cells)
            lit = ~S.unlit_mask(shot, calib, cells, zone_keys)
            ev_b = a.ev + S.key_fix_ev(key)
            moved = F.shift_display_u8(shot.rgb, ev_b, lit)
            rec = {"frame": T.L.rel(shot.png), "boardEv": round(ev_b, 3), "real r3 @0": real, "cases": {}}
            for blur in blurs:
                # renderer check: the r3 bands re-painted on the unshifted frame against the real metrics
                if not a.no_renderer_check:
                    s0 = S._reshade(shot, paint_rings(shot, GEOMETRIES["r3"], colours, blur=blur))
                    rec["cases"][f"r3 @0 blur{blur}"] = measure(s0, "r3", th, calib, cells)
                for g in geos:
                    sg = S._reshade(shot, paint_rings(shot, GEOMETRIES[g], colours, blur=blur, bg_rgb=moved))
                    rec["cases"][f"{g} @light blur{blur}"] = measure(sg, g, th, calib, cells, colours["rim"])
                    if a.save_crops and side == "joiner" and blur == blurs[-1]:
                        from PIL import Image
                        (out / "ring-crops").mkdir(parents=True, exist_ok=True)
                        for fid, f in sg.fighters.items():
                            p = sg.proj.camera.project(f.world)
                            if p:
                                x, y = int(p[0]), int(p[1])
                                Image.fromarray(sg.rgb[max(y - 40, 0):y + 60, max(x - 70, 0):x + 70]).resize((560, 400), 0).save(
                                    out / "ring-crops" / f"{key}-{g}-{T.FIGHTER_NAMES.get(fid, fid).replace(' ', '')}.png")
            rec["summary"] = {k: summary(v) for k, v in rec["cases"].items()}
            rec["summary"]["real r3 @0"] = summary(real)
            doc["boards"][f"{key}/{side}"] = rec
            print(key, side, json.dumps({k: [v["shapeAllVariants"], v["shapeAllVariantsNoRimBound"], v["minFilledRays"],
                                             v["fractionMinSidekick"], v["edgeVsTileMin"], v["outerKeylineCorePxMin"]]
                                         for k, v in rec["summary"].items()}, ensure_ascii=False), flush=True)
    tot = {}
    for rec in doc["boards"].values():
        for case, rows in list(rec["cases"].items()) + [("real r3 @0", rec["real r3 @0"])]:
            tot.setdefault(case, []).extend(rows)
    doc["total"] = {k: summary(v) for k, v in tot.items()}
    out.mkdir(parents=True, exist_ok=True)
    (out / a.name).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(doc["total"], ensure_ascii=False, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sw = sub.add_parser("sweep")
    sw.add_argument("--out", required=True)
    sw.add_argument("--geometries", default="r3,b1-thin,b1")
    sw.add_argument("--blur", default="0,0.35")
    sw.add_argument("--ev", type=float, default=-0.75)
    sw.add_argument("--sides", default="joiner,host")
    sw.add_argument("--save-crops", action="store_true")
    sw.add_argument("--name", default="ring-sim.json")
    sw.add_argument("--boards", default="", help="comma list of board keys (default: all three)")
    sw.add_argument("--rim-hex", default=RIM_HEX)
    sw.add_argument("--zones-rev5", action="store_true", help="tile reference with the rev 5 zone colours (B1-2)")
    sw.add_argument("--no-renderer-check", action="store_true")
    a = ap.parse_args(argv)
    return {"check": cmd_check, "sweep": cmd_sweep}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
