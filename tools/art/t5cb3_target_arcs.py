#!/usr/bin/env python3
"""Target arcs in grey (after 5c-B2 B1-8, act art3-live-3boards-r3 section 4.2): the orange target arcs of the attack target
(SM_Marker_TargetRing, M_S08_GameLayerUnlit MID with Tint (1.4, 0.18, 0.06), S08FighterActor::BeginPlay) are almost
as light as the P2 silver fill in grey (L* 64 vs 52.8, dE76 11 <= pixelDeltaE 15) and touch its inner edge on the
hexagon flats: in grey the classifier labels them fill, the fill centre line moves in and King Arthur's hexagon on K3
Cobble / T. Rex is 'unclassified' (52/54).

The fix is a darker target-arc colour of the same hue: in grey it has to leave the P1 fill, the P2 fill AND the
keyline by more than pixelDeltaE, in deuteranopia too. The registered thresholds (t5cb-thresholds.json) are only read.

    python tools/art/t5cb3_target_arcs.py palette --out <json>          # Filmic model: candidates, class distances
    python tools/art/t5cb3_target_arcs.py redraw --tint R,G,B --out <dir> [--screen R,G,B]
        # the three packaged K3 gate frames (5c-B2) with the arc pixels recoloured (linear-light, anti-aliased fringe
        # by its mix factor), measured by the REGISTERED classifier (t53_readability.rings_rev3, bands of the
        # thresholds file) and the icon rev 3 (qa010 icon): a FORECAST, not a capture
    python tools/art/t5cb3_target_arcs.py editor --board cobble|forest|paddock --tint R,G,B --out <dir>
        # live editor (MCP :8123, lock C:/tmp/ue-editor.lock): calibration plates old / new tint + a K3-distance frame
        # of a P1 and a P2 hero ring with the target arcs (old tint left, new tint right) on the board surface:
        # DIAGNOSTIC editor frames (Epic, class editor-mcp-viewport), not K3 acceptance
"""
from __future__ import annotations

import argparse
import colorsys
import datetime as dt
import json
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "qa010"))

import t53_readability as T53  # noqa: E402
import ue_filmic as F  # noqa: E402

EVID = REPO / "docs" / "game-design" / "evidence" / "ART-005" / "art3-live-3boards-r3-2026-09-30"
BOARDS3 = ["cobble-5x6", "sherwood-forest-8x5", "t-rex-paddock-7x5"]
ARC_OLD_TINT = (1.4, 0.18, 0.06)            # S08FighterActor.cpp (5c-B2 packaged build)
ARC_BAND_UU = (20.9, 23.0)                  # blender/ASSET-MARKERS-001/build_markers.py (inner .209, outer .23, x100)
ARC_TOP_Z_UU = 3.0                          # .022 + .008
PDE = 15.0
CLASSES = ("team.p1.fill", "team.p2.fill", "mark.keyline", "team.rim")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).as_posix()


def lab(u8):
    import numpy as np
    from qa010lib import color as C
    return C.linear_to_lab(C.u8_to_linear(np.asarray(u8, np.uint8).reshape(1, 1, 3)))[0, 0]


def variant(u8, vn: str):
    import numpy as np
    from qa010lib import color as C
    a = np.asarray(u8, np.uint8).reshape(1, 1, 3)
    return {"color": a, "gray": C.grayscale(a), "deuteranopia": C.deuteranopia(a)}[vn][0, 0]


def rel_lum(u8) -> float:
    import numpy as np
    from qa010lib import color as C
    return float(C.relative_luminance(np.asarray(u8, np.uint8).reshape(1, 1, 3))[0, 0])


def screen_of_tint(tint) -> list[int]:
    """Unlit game layer (emissive x EyeAdaptationInverse): scene value = Tint at any exposure -> Filmic (ue_filmic)."""
    import numpy as np
    d = F.scene_to_display(np.asarray(tint, float)[None, :])[0]
    return [int(v) for v in np.clip(np.rint(d * 255.0), 0, 255)]


def calib_bytes() -> dict:
    th = T53.thresholds(EVID)
    return {k: v["screen"] for k, v in th["calibration"]["bytes"].items()}


def class_distances(screen, calib) -> dict:
    """dE76 of the arc bytes to every ring class, per variant (the classifier's rule: a pixel of class X = within
    pixelDeltaE of the variant-transformed screen bytes of X)."""
    out = {}
    for vn in ("color", "gray", "deuteranopia"):
        a = lab(variant(screen, vn))
        out[vn] = {k: round(float(((a - lab(variant(calib[k], vn))) ** 2).sum() ** 0.5), 2) for k in CLASSES}
        out[vn]["L*"] = round(float(a[0]), 2)
    out["minOverClassesAndVariants"] = min(v for vn in ("color", "gray", "deuteranopia") for k, v in out[vn].items()
                                           if k != "L*")
    return out


def hue_sat(screen) -> dict:
    h, s, v = colorsys.rgb_to_hsv(*[x / 255.0 for x in screen])
    return {"hueDeg": round(h * 360.0, 1), "sat": round(s, 3), "val": round(v, 3)}


# ------------------------------------------------------------------ palette
def cmd_palette(a) -> int:
    import numpy as np
    calib = calib_bytes()
    old = screen_of_tint(ARC_OLD_TINT)
    rows = []
    hue0 = hue_sat(old)["hueDeg"]
    for s in (0.73, 0.8, 0.85):
        for v in np.arange(0.40, 0.76, 0.02):
            disp = [int(round(x * 255)) for x in colorsys.hsv_to_rgb(hue0 / 360.0, s, float(v))]
            tint = F.display_to_scene(np.asarray([disp], float) / 255.0)[0]
            scr = screen_of_tint(tint)
            rows.append({"hsv": [hue0, s, round(float(v), 2)], "tint": [round(float(x), 4) for x in tint], "screen": scr,
                         **hue_sat(scr), "distances": class_distances(scr, calib)})
    doc = {"schema": "unmatched.t5cb3-target-arcs-palette/1", "at": now(),
           "model": "tools/art/ue_filmic.py scene_to_display (unlit game layer: scene value = Tint), checked against the "
                    "5c-B2 packaged arc pixels (median 244-251, 130-137, 71-74 vs model %s)" % old,
           "old": {"tint": list(ARC_OLD_TINT), "screen": old, **hue_sat(old), "distances": class_distances(old, calib)},
           "pixelDeltaE": PDE, "calibration": {k: calib[k] for k in CLASSES}, "candidates": rows}
    write_json(Path(a.out), doc)
    print("old", old, doc["old"]["distances"]["gray"])
    for r in rows:
        d = r["distances"]
        print(r["hsv"], r["screen"], "L*g %.1f" % d["gray"]["L*"], "gray p2 %.1f key %.1f p1 %.1f" % (
            d["gray"]["team.p2.fill"], d["gray"]["mark.keyline"], d["gray"]["team.p1.fill"]), "min %.1f" % d["minOverClassesAndVariants"])
    return 0


# ------------------------------------------------------------------ redraw forecast
def gate_frame(board: str) -> Path:
    summ = json.loads((EVID / "analysis" / board / "summary.json").read_text(encoding="utf-8"))
    return REPO / summ["frames"]["K3"]


def annulus_mask(shot, f, fs: float, r0: float, r1: float, z: float, step: float = 0.15):
    import numpy as np
    th = np.radians(np.arange(0.0, 360.0, 0.25))
    rr = np.arange(r0 * fs, r1 * fs + 1e-6, step)
    T, R_ = np.meshgrid(th, rr)
    pts = np.stack([f.world[0] + R_ * np.cos(T), f.world[1] + R_ * np.sin(T), np.full(T.shape, z)], -1).reshape(-1, 3)
    scr = T53.project_many(shot.proj.camera, pts)
    ok = np.isfinite(scr).all(1)
    xs, ys = np.floor(scr[ok, 0]).astype(int), np.floor(scr[ok, 1]).astype(int)
    k = (xs >= 0) & (xs < shot.w) & (ys >= 0) & (ys < shot.h)
    m = np.zeros((shot.h, shot.w), bool)
    m[ys[k], xs[k]] = True
    return m


def dilate(m, it: int):
    out = m.copy()
    for _ in range(it):
        n = out.copy()
        n[1:] |= out[:-1]
        n[:-1] |= out[1:]
        n[:, 1:] |= out[:, :-1]
        n[:, :-1] |= out[:, 1:]
        out = n
    return out


def find_target(shot, old_screen):
    """-> (fid, arc core mask, region): the fighter whose arc annulus holds the most arc-coloured pixels."""
    near = shot.de_to(old_screen) <= 12.0
    best = None
    for fid, f in shot.fighters.items():
        fs = T53.fighter_scale(fid)
        reg = dilate(annulus_mask(shot, f, fs, ARC_BAND_UU[0], ARC_BAND_UU[1], f.world[2] + ARC_TOP_Z_UU * fs), 2)
        n = int((near & reg).sum())
        if best is None or n > best[1]:
            best = (fid, n, near & reg, reg)
    return best[0], best[2], best[3]


def with_rgb(shot, rgb):
    import numpy as np  # noqa: F401 (Shot.np)
    from qa010lib import color as C
    s = T53.Shot.__new__(T53.Shot)
    s.__dict__.update(shot.__dict__)
    s.rgb = rgb
    s.variants = {"color": rgb, "gray": C.grayscale(rgb), "deuteranopia": C.deuteranopia(rgb)}
    s.lum = {k: C.relative_luminance(v) for k, v in s.variants.items()}
    s.luma_gray = C.luma_u8(s.variants["gray"])
    s.lab = C.linear_to_lab(C.u8_to_linear(rgb))
    s.np = np
    return s


def unproject(cam, xs, ys, z0: float):
    """Pixel positions -> world (x, y) on the plane z = z0 (inverse of qa010lib Camera.project)."""
    import numpy as np
    f, r, u = (np.asarray(v, dtype=np.float64) for v in cam.axes())
    w, h = cam.viewport
    focal = (w * 0.5) / math.tan(math.radians(cam.hfov_deg) * 0.5)
    dx = (np.asarray(xs, np.float64) - w * 0.5) / focal
    dy = (h * 0.5 - np.asarray(ys, np.float64)) / focal
    d = f[None, :] + dx[:, None] * r[None, :] + dy[:, None] * u[None, :]
    t = (z0 - cam.pos[2]) / d[:, 2]
    p = np.asarray(cam.pos, np.float64)[None, :] + t[:, None] * d
    return p[:, 0], p[:, 1]


def ring_band_of(look: str, x, y, fs: float):
    """Band name per point of the ring top face (hero-scale geometry of the registered bands / fs): keylineIn, fill,
    keylineOut, rimOut or '' (tile, P2 corner gaps included)."""
    import numpy as np
    b = T53.ring_bands(look)
    x, y = np.asarray(x) / fs, np.asarray(y) / fs
    if look == "P1":
        a = np.hypot(x, y)
        gap = np.zeros(a.shape, bool)
    else:
        proj = np.stack([x * math.cos(math.radians(60 * k + 30)) + y * math.sin(math.radians(60 * k + 30))
                         for k in range(6)], -1)
        k = proj.argmax(-1)
        a = proj.max(-1)
        phi = np.radians(60 * k + 30)
        tng = -x * np.sin(phi) + y * np.cos(phi)
        trim = (T53.RING.RING_SPEC["p2"]["cornerGapUU"] / 2.0) / math.sin(math.radians(60))
        gap = np.abs(tng) > a * math.tan(math.radians(30)) - trim
    out = np.full(a.shape, "", dtype=object)
    for name in ("keylineIn", "fill", "keylineOut", "rimOut"):
        if name in b:
            out[(a >= b[name][0]) & (a < b[name][1]) & ~gap] = name
    return out


def regeometry(shot, fid: str, core, calib: dict, arc_screen, scale: float, sub: int = 4):
    """Forecast of the target arcs scaled by `scale` about the fighter (inner 20.9 s, outer 23 s): every pixel of the
    arc annulus is re-rendered from 4 x 4 subsamples: new arc -> the arc colour; formerly arc, now uncovered -> what lies
    beneath (the ring band from the registered geometry at the ring plane: keyline / fill / rim screen bytes, else the
    median tile just inside the arcs); untouched otherwise. Only angles where the arcs are visible in the frame (the
    visible arc core, 1 deg bins, +-1 bin) are edited, so a figure in front of the arcs stays as it is."""
    import numpy as np
    from qa010lib import color as C
    f = shot.fighters[fid]
    fs = T53.fighter_scale(fid)
    look = (shot.rings.get(fid) or {}).get("look") or "P2"
    cam = shot.proj.camera
    z_arc, z_ring = f.world[2] + ARC_TOP_Z_UU * fs, f.world[2] + T53.RING.RING_SPEC["zMax"]
    ys, xs = np.nonzero(core)
    wx, wy = unproject(cam, xs + 0.5, ys + 0.5, z_arc)
    th = (np.degrees(np.arctan2(wy - f.world[1], wx - f.world[0])) + 360.0) % 360.0
    vis = np.zeros(360, bool)
    vis[np.floor(th).astype(int) % 360] = True
    vis = vis | np.roll(vis, 1) | np.roll(vis, -1)
    region = dilate(annulus_mask(shot, f, fs, ARC_BAND_UU[0] * min(scale, 1.0) - 0.8, ARC_BAND_UU[1] * max(scale, 1.0) + 0.8,
                                 z_arc), 2)
    ry, rx = np.nonzero(region)
    lin = C.u8_to_linear(shot.rgb)
    out = lin.copy()
    inner = annulus_mask(shot, f, fs, 18.6, 20.4, z_arc) & ~dilate(core, 2)
    tile = np.median(lin[inner], axis=0) if inner.any() else np.array([0.1, 0.1, 0.1])
    colours = {"keylineIn": calib["mark.keyline"], "keylineOut": calib["mark.keyline"], "rimOut": calib["team.rim"],
               "fill": calib["team.p1.fill" if look == "P1" else "team.p2.fill"]}
    col_lin = {k: C.u8_to_linear(np.asarray(v, np.uint8)) for k, v in colours.items()}
    arc_lin = C.u8_to_linear(np.asarray(arc_screen, np.uint8))
    offs = (np.arange(sub) + 0.5) / sub
    oy, ox = np.meshgrid(offs, offs, indexing="ij")
    oy, ox = oy.ravel(), ox.ravel()
    n_new = n_old = 0
    changed = 0
    for y, x in zip(ry, rx):
        sx, sy = x + ox, y + oy
        ax, ay = unproject(cam, sx, sy, z_arc)
        ar = np.hypot(ax - f.world[0], ay - f.world[1]) / fs
        at = (np.degrees(np.arctan2(ay - f.world[1], ax - f.world[0])) + 360.0) % 360.0
        in_vis = vis[np.floor(at).astype(int) % 360]
        old = in_vis & (ar >= ARC_BAND_UU[0]) & (ar <= ARC_BAND_UU[1])
        new = in_vis & (ar >= ARC_BAND_UU[0] * scale) & (ar <= ARC_BAND_UU[1] * scale)
        if not (old.any() or new.any()):
            continue
        if old.any() and not core[max(0, y - 2):y + 3, max(0, x - 2):x + 3].any():
            continue          # arcs hidden here (figure in front): leave the pixel
        gx, gy = unproject(cam, sx, sy, z_ring)
        bands = ring_band_of(look, gx - f.world[0], gy - f.world[1], fs)
        acc = np.zeros(3)
        for i in range(len(ox)):
            if new[i]:
                acc += arc_lin
            elif old[i]:
                acc += col_lin[bands[i]] if bands[i] else tile
            else:
                acc += lin[y, x] if not old.any() else (col_lin[bands[i]] if bands[i] else tile)
        out[y, x] = acc / len(ox)
        n_new += int(new.any())
        n_old += int(old.any())
        changed += 1
    rgb = C.quantize_u8(C.linear_to_srgb(out))
    return rgb, {"changedPx": changed, "pxWithOldArc": n_old, "pxWithNewArc": n_new, "visibleArcDeg": int(vis.sum()),
                 "tileInsideMedianRgb": [int(v) for v in C.quantize_u8(C.linear_to_srgb(tile))], "look": look,
                 "scale": scale, "newArcBandUU": [round(ARC_BAND_UU[0] * scale * fs, 3), round(ARC_BAND_UU[1] * scale * fs, 3)]}


def recolour(shot, core, region, old_lin, new_lin):
    """Linear-light recolour: core pixels scaled channel-wise by new / old (keeps their small variation); fringe pixels
    (2 px around the core, inside the dilated arc region) get + alpha x (new - old), alpha = their mix factor between
    the old arc colour and the median of their non-arc neighbours (7 x 7)."""
    import numpy as np
    from qa010lib import color as C
    lin = C.u8_to_linear(shot.rgb).copy()
    out = lin.copy()
    ratio = new_lin / np.maximum(old_lin, 1e-6)
    out[core] = np.clip(lin[core] * ratio, 0.0, 1.0)
    fringe = dilate(core, 2) & dilate(region, 2) & ~core
    other = ~dilate(core, 2)
    ys, xs = np.nonzero(fringe)
    alphas = []
    for y, x in zip(ys, xs):
        y0, y1, x0, x1 = max(0, y - 3), min(shot.h, y + 4), max(0, x - 3), min(shot.w, x + 4)
        nb = lin[y0:y1, x0:x1][other[y0:y1, x0:x1]]
        if not len(nb):
            continue
        b = np.median(nb, axis=0)
        d = old_lin - b
        al = float(np.clip(np.dot(lin[y, x] - b, d) / max(float(np.dot(d, d)), 1e-9), 0.0, 1.0))
        alphas.append(al)
        out[y, x] = np.clip(lin[y, x] + al * (new_lin - old_lin), 0.0, 1.0)
    rgb = C.quantize_u8(C.linear_to_srgb(out))
    return rgb, {"corePx": int(core.sum()), "fringePx": int(fringe.sum()),
                 "fringeAlphaP50": round(float(np.median(alphas)), 3) if alphas else None}


def arc_contrast(shot, core, f, fs: float, calib) -> dict:
    """Arc core against its neighbours in each variant (WCAG of the medians): the tile / pedestal band just inside the
    arcs (r 18.6-20.6 uu x FS, not the arc) and the ring keyline."""
    import numpy as np
    z = f.world[2] + ARC_TOP_Z_UU * fs
    inner = annulus_mask(shot, f, fs, 18.6, 20.6, z) & ~dilate(core, 1)
    key = (shot.de_to(calib["mark.keyline"]) <= PDE) & dilate(annulus_mask(shot, f, fs, 20.0, 24.0, f.world[2] + 1.2), 1)
    out = {"innerPx": int(inner.sum()), "keylinePx": int(key.sum())}
    for vn in ("color", "gray", "deuteranopia"):
        la, li, lk = shot.med_lum(core, vn), shot.med_lum(inner, vn), shot.med_lum(key, vn)
        out[vn] = {"arcRelLum": round(la, 4) if la is not None else None,
                   "arcVsInner": round(T53.wcag(la, li), 3) if la is not None and li is not None else None,
                   "arcVsKeyline": round(T53.wcag(la, lk), 3) if la is not None and lk is not None else None}
    out["arcMedianRgb"] = [round(v, 1) for v in np.median(shot.rgb[core].reshape(-1, 3), axis=0)] if core.any() else None
    out["innerMedianRgb"] = shot.med_rgb(inner)
    return out


def icon_row(shot, png: Path, trace: Path, out_json: Path) -> dict:
    ib = T53.icon_binding(shot)
    if not ib["present"]:
        return {"present": False}
    n = int(round(ib["bbox"][2] - ib["bbox"][0]))
    rc, doc = T53.run_qa(["icon", str(png), "--trace", str(trace), "--shot", png.name,
                          "--mask-texture", str(T53.TOKEN_DIR / f"ui-action-attack-token-{n}-glyphmask.png"),
                          "--token-texture", str(T53.TOKEN_DIR / f"ui-action-attack-token-{n}.png")], out_json)
    v = (doc or {}).get("variants") or {}
    return {"present": True, "size": n, "exit": rc, "result": (doc or {}).get("result"),
            "edge": {vn: (v.get(vn) or {}).get("edge") for vn in ("color", "gray", "deuteranopia")},
            "glyphVsBody": {vn: (v.get(vn) or {}).get("glyph_vs_body") for vn in ("color", "gray", "deuteranopia")}}


def ring_rows(shot, calib_full, cells) -> list:
    rr = T53.rings_rev3(shot, calib_full, cells, PDE)
    return [{"fighter": r["fighter"], "name": r["name"], "look": r["look"], "expected": r["expectedShape"],
             "shape": r["shape"], "passAll": r["shapePassAllVariants"],
             "hexOverCircle": {vn: r["shapeDetail"][vn].get("hexOverCircle") for vn in r["shapeDetail"]},
             "otherGaps": {vn: r["shapeDetail"][vn].get("otherGaps") for vn in r["shapeDetail"]},
             "filled": {vn: r["shapeDetail"][vn].get("filled") for vn in r["shapeDetail"]},
             "edgeVsTilePass": r["edgeVsTilePass"]} for r in rr["fighters"]]


def cmd_redraw(a) -> int:
    import numpy as np
    from PIL import Image
    from qa010lib import color as C
    th = T53.thresholds(EVID)
    calib_full = th["calibration"]["bytes"]
    calib = {k: v["screen"] for k, v in calib_full.items()}
    tint = [float(x) for x in a.tint.split(",")] if a.tint else list(ARC_OLD_TINT)
    new_screen = [int(x) for x in a.screen.split(",")] if a.screen else (screen_of_tint(tint) if a.tint else None)
    out = Path(a.out).resolve()
    doc = {"schema": "unmatched.t5cb3-target-arcs-redraw/1", "at": now(),
           "status": "ПРОГНОЗ на перерисовке packaged-кадров 5c-B2 (не съёмка); финальная проверка — packaged, волна 6B",
           "thresholds": rel(EVID / "t5cb-thresholds.json"), "thresholdsUnchanged": True,
           "oldTint": list(ARC_OLD_TINT), "newTint": tint, "newScreen": new_screen, "arcScale": a.scale,
           "newScreenSource": ("--screen (editor calibration)" if a.screen else
                               "ue_filmic model of the tint" if a.tint else "unchanged (the measured arc bytes)"),
           "classDistancesNew": class_distances(new_screen, calib) if new_screen else None, "boards": {}}
    with T53.RING.using_bands(T53.evidence_ring_bands(th)):
        for board in BOARDS3:
            png = gate_frame(board)
            trace = T53._trace_for(png)
            shot = T53.Shot(png, trace)
            cells = T53.T52.board_cells(T53.T52_EVIDENCE if board == "cobble-5x6" else EVID, board)
            fid, core, region = find_target(shot, screen_of_tint(ARC_OLD_TINT))
            old_screen = [int(v) for v in np.median(shot.rgb[core].reshape(-1, 3), axis=0)]
            arc_new = new_screen or old_screen
            if a.scale != 1.0:
                rgb, info = regeometry(shot, fid, core, calib, arc_new, a.scale)
            else:
                rgb, info = recolour(shot, core, region, C.u8_to_linear(np.asarray(old_screen, np.uint8)),
                                     C.u8_to_linear(np.asarray(arc_new, np.uint8)))
            red = with_rgb(shot, rgb)
            dst = out / board / png.parent.name / png.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(rgb).save(dst)
            f = shot.fighters[fid]
            fs = T53.fighter_scale(fid)
            new_core = (red.de_to(arc_new) <= 12.0) & dilate(region, 3) if a.scale != 1.0 else core.copy()
            b = {"frame": rel(png), "trace": rel(trace), "redrawn": dst.as_posix(), "target": fid,
                 "targetName": T53.FIGHTER_NAMES.get(fid, fid), "targetLook": (shot.rings.get(fid) or {}).get("look"),
                 "arcScreenMeasured": old_screen, "arcClassDistancesOld": class_distances(old_screen, calib), **info,
                 "ringsBefore": ring_rows(shot, calib_full, cells), "ringsAfter": ring_rows(red, calib_full, cells),
                 "arcContrastBefore": arc_contrast(shot, core, f, fs, calib),
                 "arcContrastAfter": arc_contrast(red, new_core, f, fs, calib)}
            b["iconBefore"] = icon_row(shot, png, trace, out / board / "icon-before.json")
            b["iconAfter"] = icon_row(red, dst, trace, out / board / "icon-after.json")
            # crops: colour | grey, before | after
            bb = np.argwhere(dilate(region, 6))
            y0, x0 = bb.min(0) - 20
            y1, x1 = bb.max(0) + 20
            y0, x0 = max(0, y0), max(0, x0)
            tiles = [shot.rgb, shot.variants["gray"], rgb, red.variants["gray"]]
            crop = [Image.fromarray(t[y0:y1, x0:x1]).resize(((x1 - x0) * 3, (y1 - y0) * 3), Image.NEAREST) for t in tiles]
            sheet = Image.new("RGB", (sum(c.width for c in crop) + 30, crop[0].height), (20, 20, 20))
            x = 0
            for c in crop:
                sheet.paste(c, (x, 0))
                x += c.width + 10
            sheet.save(out / f"k3-target-arcs-{board}.jpg", quality=90)
            b["crop"] = (out / f"k3-target-arcs-{board}.jpg").as_posix()
            doc["boards"][board] = b
            tgt_b = next(r for r in b["ringsBefore"] if r["fighter"] == fid)
            tgt_a = next(r for r in b["ringsAfter"] if r["fighter"] == fid)
            print(board, fid, "arc", old_screen, "->", arc_new, "scale", a.scale, "shape before", tgt_b["shape"], "after", tgt_a["shape"],
                  "all rings after %d/%d" % (sum(r["passAll"] for r in b["ringsAfter"]), len(b["ringsAfter"])))
    rows = [r for b in doc["boards"].values() for r in b["ringsAfter"]]
    rows0 = [r for b in doc["boards"].values() for r in b["ringsBefore"]]
    doc["summary"] = {"k3RingsBefore": "%d/%d" % (sum(r["passAll"] for r in rows0), len(rows0)),
                      "k3RingsAfter": "%d/%d" % (sum(r["passAll"] for r in rows), len(rows)),
                      "targetShapeAfter": {bd: next(r["shape"] for r in b["ringsAfter"] if r["fighter"] == b["target"])
                                           for bd, b in doc["boards"].items()}}
    write_json(out / "redraw.json", doc)
    print(json.dumps(doc["summary"], ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ editor diagnostics
def cmd_editor(a) -> int:
    """K3-distance editor frame on the board surface of t5cb1_editor (rev 5 light of the board): four hero rings with
    the Arthur blockout and the target arcs - P1 / P2 with the 5c-B2 arcs (tint (1.4, 0.18, 0.06), scale 1.0) on the
    left, P1 / P2 with the new arcs (--tint, --scale) on the right; + calibration plates of both tints. Measured with
    the registered classifier (rings_rev3) on a synthetic SHOT of the capture camera."""
    import numpy as np
    import t5cb1_editor as E
    import t53_diag_editor as D
    out = Path(a.out).resolve()
    tint = [float(x) for x in a.tint.split(",")] if a.tint else list(ARC_OLD_TINT)
    th = T53.thresholds(EVID)
    calib_full = th["calibration"]["bytes"]
    calib = {k: {"screen": v["screen"], "hex": v["hex"]} for k, v in calib_full.items()}
    spec = E.BOARDS[a.board]
    if a.scratch_level:  # the shared scratch level can stay dirty in memory after a run (load_level then refuses it)
        D.LEVEL = a.scratch_level
    sc = E.Scene(out / "frames")
    rep = {"schema": "unmatched.t5cb3-target-arcs-editor/1", "board": a.board, "startedUtc": now(),
           "status": "диагностика (кадры редактора :8123, Epic, editor-mcp-viewport); не K3-приёмка",
           "oldTint": list(ARC_OLD_TINT), "newTint": tint, "oldScale": 1.0, "newScale": a.scale}
    rep["scene"] = sc.open()
    try:
        rep["light"] = sc.rig(spec["light"])
        mi_old = sc.scratch_mi("MI_T5CB3_ArcOld", D.GAME_LAYER_OLD, {"Tint": list(ARC_OLD_TINT) + [1.0]})
        mi_new = sc.scratch_mi("MI_T5CB3_ArcNew", D.GAME_LAYER_OLD, {"Tint": tint + [1.0]})
        hexes = E.R.team_hex()
        silver = sc.scratch_mi("MI_T5CB1_FillP2", D.MASTER, {"LayerColor": D.lin_hex(hexes["p2"])})
        # calibration plates (off the board, the unlit layer does not depend on light / exposure)
        plates = [("arc.old", mi_old, -500.0), ("arc.new", mi_new, -440.0)]
        for label, mi, x in plates:
            sc.mesh_actor(f"T5CB3 plate {label}", D.CUBE, (x, -600.0, 0.0), (0.5, 0.5, 0.01), mi)
        W, H = spec["size"]
        if spec["surface"] == "cobble":
            slots = sc.slot_names(E.COBBLE_SLAB)
            mats = [E.COBBLE_WOOD if "wood" in s.lower() else E.COBBLE_STONE for s in slots]
            sc.mesh_actor("T5CB3 cobble slab", E.COBBLE_SLAB, (0.0, 0.0, 0.0), (1.0, 1.0, 1.0), mats, rot=(0.0, -90.0, 0.0))
        else:
            n = 0
            for cx in range(-2, 3):
                for cy in range(-1, 2):
                    sc.tile(f"T5CB3 tile {n}", cx * E.CELL, cy * E.CELL)
                    n += 1
        # four hero fighters in one row: P1 old, P2 old, P1 new, P2 new
        layout = [("f-0-hero", "P1", -150.0, mi_old), ("f-1-hero", "P2", -50.0, mi_old),
                  ("f-2-hero", "P1", 50.0, mi_new), ("f-3-hero", "P2", 150.0, mi_new)]
        scales = {mi_old: 1.0, mi_new: a.scale}
        fighters, rings, figures = {}, {}, {}
        for fid, look, x, mi in layout:
            w = (x, 0.0, 0.0)
            fill = E.R.MI_FILL if look == "P1" else silver
            sc.mesh_actor(f"T5CB3 ring {fid}", E.R.ring_package(look.lower()), w, (1.0, 1.0, 1.0),
                          [E.R.MI_KEYLINE, fill, E.R.MI_RIM])
            sc.mesh_actor(f"T5CB3 arcs {fid}", "/Game/ArtTests/ARTMarkers/Meshes/SM_Marker_TargetRing", w,
                          (scales[mi], scales[mi], 1.0), mi)
            sc.mesh_actor(f"T5CB3 fig {fid}", E.BLOCKOUT["Arthur"], w, (1, 1, 1), None, rot=(0.0, 180.0, 0.0))
            fighters[fid] = SimpleNamespace(fighter_id=fid, world=w, cell=(0, 0), alive=True)
            rings[fid] = {"look": look, "shown": True, "team": look}
            figures[fid] = 60.0
        time.sleep(2.0)
        # calibration frame
        x_cal = sc.camera((-470.0, -600.0, 0.0), 300.0, pitch=-89.9, yaw=-90.0)
        arr, cam, meta = sc.grab_geo(f"calib-{a.board}", x_cal)
        cal = {}
        for label, mi, x in plates:
            s = cam.project((x, -600.0, 0.5))
            x0, y0 = int(s[0]) - 6, int(s[1]) - 6
            patch = arr[max(0, y0):y0 + 13, max(0, x0):x0 + 13].reshape(-1, 3).astype(int)
            cal[label] = {"screen": [int(v) for v in np.median(patch, axis=0)], "patchSpread": int(np.ptp(patch, axis=0).max())}
        cal["arc.old"]["model"] = screen_of_tint(ARC_OLD_TINT)
        cal["arc.new"]["model"] = screen_of_tint(tint)
        rep["calibration"] = cal
        # K3 distance: the 5c-B2 K3 gate frames see the target at ~2.3 px/uu; pitch -55, yaw -90 like the game camera
        dist = a.dist
        xf = sc.camera((0.0, 0.0, 0.0), dist)
        rgb, cam, meta = sc.grab_geo(f"k3dist-{a.board}", xf)
        rects = {fid: E.figure_rect(cam, f.world, 1.0, figures[fid]) for fid, f in fighters.items()}
        shot = E.make_shot(rgb, cam, fighters, rings, rects)
        ppu = []
        for fid, f in fighters.items():
            p0, p1 = cam.project(f.world), cam.project((f.world[0] + 10.0, f.world[1], f.world[2]))
            ppu.append(round(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 10.0, 3))
        with T53.RING.using_bands(T53.evidence_ring_bands(th)):
            rows = ring_rows(shot, calib_full, None)
        rep["frame"] = {"file": f"frames/k3dist-{a.board}.png", "camera": xf, "meta": meta, "pxPerUU": ppu}
        rep["rings"] = rows
        for r in rows:
            r["arcs"] = "old" if r["fighter"] in ("f-0-hero", "f-1-hero") else "new"
        # arc contrast per fighter (arc pixels by the calibrated screen bytes of its tint)
        con = {}
        for fid, look, x, mi in layout:
            f = fighters[fid]
            which = "arc.old" if mi == mi_old else "arc.new"
            s_ = scales[mi]
            reg = dilate(annulus_mask(shot, f, 1.0, ARC_BAND_UU[0] * s_, ARC_BAND_UU[1] * s_, ARC_TOP_Z_UU), 2)
            core = reg & (shot.de_to(cal[which]["screen"]) <= 12.0)
            con[fid] = dict(arc_contrast(shot, core, f, 1.0, {k: v["screen"] for k, v in calib.items()}), arcs=which,
                            corePx=int(core.sum()))
        rep["arcContrast"] = con
        rep["classDistances"] = {k: class_distances(v["screen"], {kk: vv["screen"] for kk, vv in calib.items()})
                                 for k, v in cal.items()}
    finally:
        sc.cleanup()
        rep["restore"] = E.restore(sc.ed)
        rep["finishedUtc"] = now()
        write_json(out / f"editor-{a.board}.json", rep)
    print(json.dumps({"cal": rep.get("calibration"), "rings": [(r["fighter"], r["arcs"], r["shape"]) for r in rep.get("rings", [])],
                      "ppu": rep.get("frame", {}).get("pxPerUU")}, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("palette")
    p.add_argument("--out", required=True)
    r = sub.add_parser("redraw")
    r.add_argument("--tint", help="new Tint (linear); default: the colour stays")
    r.add_argument("--scale", type=float, default=1.0, help="arcs scaled about the fighter (0.95: outer 21.85 uu)")
    r.add_argument("--screen")
    r.add_argument("--out", required=True)
    e = sub.add_parser("editor")
    e.add_argument("--board", required=True, choices=["cobble", "forest", "paddock"])
    e.add_argument("--tint", help="new Tint (linear); default: the 5c-B2 tint")
    e.add_argument("--scale", type=float, default=1.0, help="XY scale of the new arcs about the fighter")
    e.add_argument("--dist", type=float, default=600.0, help="editor camera distance (600: ~1.6 px/uu like K3 Cobble)")
    e.add_argument("--scratch-level", help="scratch copy of the arena (default t53_diag_editor.LEVEL)")
    e.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    return {"palette": cmd_palette, "redraw": cmd_redraw, "editor": cmd_editor}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
