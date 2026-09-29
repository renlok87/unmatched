#!/usr/bin/env python3
"""W5b-R «Исправление читаемости доски»: live re-shoot on three boards and the re-measurement by the methods
registered BEFORE the shots in <evidence>/t53-thresholds.json (rings rev 2 + rev 1, shape classifier, zones rev 2,
tags / damage rev 2, icon rev 3, K3 panel rule, SHOT captured).

    python tools/art/t53_readability.py k1       --board <key> --evidence <dir> --build-record .. --package-record ..
                                                  [--probe 24|48]
    python tools/art/t53_readability.py k3       --board <key> --evidence <dir> --build-record .. --package-record ..
    python tools/art/t53_readability.py analyze  --board <key> --evidence <dir> --k1-run .. --k3-run ..
                                                  --probe24-run .. --probe48-run .. [--derived-root ..]
    python tools/art/t53_readability.py sheets   --evidence <dir>
    python tools/art/t53_readability.py table    --evidence <dir> [--t52 <T5.2 evidence dir>]

k1 / k3 wrap tools/art/art004_live_k2.py run (run-phase2-demo) and tools/art/t52_art3_live.py k3 (run-combat-demo)
with -RequireRenderReference and -RequireShotCaptured; the clients run offscreen at -ClientFps 30 (the T5.2 method).
Statuses stay honest: «измерено», never «принято»; the art verdict is the agent's self-review.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "qa010"))
import t52_art3_live as T52  # noqa: E402
import t53_team_ring as RING  # noqa: E402

L = T52.L
REPO = T52.REPO
QA010 = T52.QA010
PROFILES = T52.PROFILES
TOKENS = REPO / "docs" / "unreal" / "contracts" / "hud" / "hud-style-tokens.json"
TOKEN_DIR = REPO / "art" / "imagegen" / "mvp-v1" / "ui" / "actions" / "sized"
T52_EVIDENCE = REPO / "docs" / "game-design" / "evidence" / "ART-005" / "art3-live-3boards-2026-09-29"
BOARDS = T52.BOARDS
FIGHTER_NAMES = T52.FIGHTER_NAMES
TEAM_RING = re.compile(r"ARTPREVIEW team ring fighter=(\S+) team=(P[12]) look=(P[12]) mode=(\w+) shape=(\w+) shown=(\d)")
COMBAT_MARKER = re.compile(r"ARTPREVIEW combat marker fighter=(.+?) attacker=(\d) target=(\d)")
CELL = 100.0
PERF_STATUS = "измерено; ЗАГРЯЗНЕНО фоном H2 (headless Blender/Cycles параллельной линии героев) — не для ACC-022"
CONCURRENT = ("живой UnrealEditor PID 31756 (главный checkout, MCP :8123), Blender MCP :9876/:9877 и headless-процессы "
              "линии героев H2 работали параллельно; см. perProcessSmPct")


# ------------------------------------------------------------------ small helpers
def load_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def lab_of(rgb_u8):
    from qa010lib import color as C
    import numpy as np
    a = np.asarray(rgb_u8, dtype=np.uint8)
    return C.linear_to_lab(C.u8_to_linear(a))


def wcag(l1: float, l2: float) -> float:
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def rect_area(r) -> float:
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def inter_area(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def rect_gap(a, b) -> float:
    dx = max(b[0] - a[2], 0.0, a[0] - b[2])
    dy = max(b[1] - a[3], 0.0, a[1] - b[3])
    return math.hypot(dx, dy)


def point_rect_dist(p, r) -> float:
    dx = max(r[0] - p[0], 0.0, p[0] - r[2])
    dy = max(r[1] - p[1], 0.0, p[1] - r[3])
    return math.hypot(dx, dy)


def thresholds(evidence: Path) -> dict:
    return load_json(evidence / "t53-thresholds.json")


class Shot:
    """One published frame + its SHOT block (request + late section + capture) of the same client trace."""

    def __init__(self, png: Path, trace: Path):
        import numpy as np
        from qa010lib import color as C
        from qa010lib.imageio import load_rgb
        from qa010lib.projection import build_projection
        from qa010lib.trace import parse_trace
        self.png, self.trace_path = Path(png), Path(trace)
        self.rgb = load_rgb(self.png)
        self.h, self.w = self.rgb.shape[:2]
        tr = parse_trace(self.trace_path)
        self.block = tr.find_shot(None, self.png.name)
        self.board = self.block.board or tr.board
        self.proj = build_projection(self.block, 35.0, 2.0, "auto")
        self.variants = {"color": self.rgb, "gray": C.grayscale(self.rgb), "deuteranopia": C.deuteranopia(self.rgb)}
        self.lum = {k: C.relative_luminance(v) for k, v in self.variants.items()}
        self.luma_gray = C.luma_u8(self.variants["gray"])
        self.lab = C.linear_to_lab(C.u8_to_linear(self.rgb))
        self.text = self.trace_path.read_text(encoding="utf-8", errors="replace")
        self.np = np
        self.fighters = {f.fighter_id: f for f in self.block.fighters if f.alive}
        self.rings = {m.group(1): {"team": m.group(2), "look": m.group(3), "mode": m.group(4), "shape": m.group(5),
                                   "shown": m.group(6) == "1"} for m in TEAM_RING.finditer(self.text)}

    # -- projection of world samples to a pixel set
    def pixels(self, pts):
        """Unique (y, x) integer pixels of the projected world points (inside the frame)."""
        cam = self.proj.camera
        out = set()
        for p in pts:
            s = cam.project(p)
            if s is None:
                continue
            x, y = int(math.floor(s[0])), int(math.floor(s[1]))
            if 0 <= x < self.w and 0 <= y < self.h:
                out.add((y, x))
        return out

    def mask_of(self, pix):
        m = self.np.zeros((self.h, self.w), dtype=bool)
        if pix:
            ys, xs = zip(*pix)
            m[list(ys), list(xs)] = True
        return m

    def de_to(self, rgb) -> "object":
        target = lab_of(self.np.array(rgb, dtype=self.np.uint8).reshape(1, 1, 3))[0, 0]
        return self.np.linalg.norm(self.lab - target, axis=-1)

    def med_lum(self, mask, variant="color"):
        v = self.lum[variant][mask]
        return float(self.np.median(v)) if v.size else None

    def med_rgb(self, mask):
        v = self.rgb[mask]
        return [float(x) for x in self.np.median(v.reshape(-1, 3), axis=0)] if v.size else None

    def widgets(self, wid: str):
        return [w for w in self.block.widgets if w.get("id") == wid]


# ------------------------------------------------------------------ rings rev 2 + shape classifier
def fighter_scale(fid: str) -> float:
    return 1.0 if fid.endswith("-hero") else 0.78


def in_sector(dx: float, dy: float, half_deg: float = 135.0) -> bool:
    return abs(math.degrees(math.atan2(dx, dy))) <= half_deg


def band_samples(look: str, r0: float, r1: float, fs: float, center, z: float, step: float = 0.25):
    """World points of a ring band (P1 annulus / P2 trimmed hexagon band) in the |theta| <= 135 deg sector."""
    cx, cy = center[0], center[1]
    pts = []
    if look == "P1":
        n_r = max(2, int(round((r1 - r0) * fs / step)) + 1)
        for i in range(0, 2160):
            t = 2 * math.pi * i / 2160
            dx, dy = math.cos(t), math.sin(t)
            if not in_sector(dx, dy):
                continue
            for k in range(n_r):
                r = (r0 + (r1 - r0) * (k + 0.5) / n_r) * fs
                pts.append((cx + r * dx, cy + r * dy, z))
        return pts
    for quad in RING.hex_band_quads(r0, r1, RING.RING_SPEC["p2"]["cornerGapUU"]):
        q = [(x * fs, y * fs) for (x, y) in quad]
        nu = 80
        nv = max(2, int(round((r1 - r0) * fs / step)) + 1)
        for i in range(nu):
            u = (i + 0.5) / nu
            a = (q[0][0] + (q[3][0] - q[0][0]) * u, q[0][1] + (q[3][1] - q[0][1]) * u)
            b = (q[1][0] + (q[2][0] - q[1][0]) * u, q[1][1] + (q[2][1] - q[1][1]) * u)
            for k in range(nv):
                v = (k + 0.5) / nv
                x, y = a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v
                if in_sector(x, y):
                    pts.append((cx + x, cy + y, z))
    return pts


def ring_bands(look: str) -> dict:
    spec = RING.RING_SPEC["p1" if look == "P1" else "p2"]["bands"]
    return {k: tuple(v) for k, v in spec.items()}


def classify_shape(shot: Shot, fid: str, team_mask, fs: float, z: float) -> dict:
    """72 samples of theta in [-135, 135] from +Y; per ray a radial profile 18..34 uu x FS (step 0.25) in the ring
    plane; 'fill' when >= 2 profile points are team pixels, r(theta) = their mean radius. Breaks = runs of 1..3 empty
    samples between filled ones; kinks = local maxima of r(theta) with prominence >= 0.06 * mean r (window +-15 deg)."""
    f = shot.fighters[fid]
    cx, cy = f.world[0], f.world[1]
    cam = shot.proj.camera
    thetas = [-135.0 + 270.0 * i / 71 for i in range(72)]
    rs = []
    for th in thetas:
        t = math.radians(th)
        dx, dy = math.sin(t), math.cos(t)  # theta measured from +Y
        hits = []
        rho = 18.0
        while rho <= 34.0 + 1e-6:
            p = cam.project((cx + rho * fs * dx, cy + rho * fs * dy, z))
            if p is not None:
                x, y = int(math.floor(p[0])), int(math.floor(p[1]))
                if 0 <= x < shot.w and 0 <= y < shot.h and team_mask[y, x]:
                    hits.append(rho)
            rho += 0.25
        rs.append(sum(hits) / len(hits) if len(hits) >= 2 else None)
    filled = [r is not None for r in rs]
    breaks, long_gaps = 0, 0
    i = 0
    while i < len(rs):
        if filled[i]:
            i += 1
            continue
        j = i
        while j < len(rs) and not filled[j]:
            j += 1
        run = j - i
        bounded = i > 0 and j < len(rs)
        if bounded and run <= 3:
            breaks += 1
        elif run >= 4:
            long_gaps += 1
        i = j
    vals = [r for r in rs if r is not None]
    rbar = sum(vals) / len(vals) if vals else 0.0
    kinks = 0
    win = 4  # +-15 deg
    for k, r in enumerate(rs):
        if r is None:
            continue
        nb = [rs[q] for q in range(max(0, k - win), min(len(rs), k + win + 1)) if q != k and rs[q] is not None]
        if len(nb) < 3:
            continue
        if r >= max(nb) and r - min(nb) >= 0.06 * rbar:
            kinks += 1
    spread = (max(vals) - min(vals)) if vals else 0.0
    if breaks == 0 and (kinks == 0 or spread <= 0.06 * rbar):
        shape = "circle"
    elif breaks >= 2 and kinks >= 2:
        shape = "hexagon"
    else:
        shape = "unclassified"
    return {"samples": 72, "filled": sum(filled), "breaks": breaks, "longGaps": long_gaps, "kinks": kinks,
            "meanR": round(rbar, 2), "spreadR": round(spread, 2), "shape": shape,
            "profile": [round(r, 2) if r is not None else None for r in rs]}


def rings_rev2(shot: Shot, th: dict, calib: dict, cells: list[dict] | None = None) -> dict:
    np = shot.np
    rt = th["rings"]
    pde = th["calibration"]["pixelDeltaE"]
    fill_bytes = {"P1": calib["team.p1.fill"]["screen"], "P2": calib["team.p2.fill"]["screen"]}
    key_bytes = calib["mark.keyline"]["screen"]
    team_masks = {s: shot.de_to(b) <= pde for s, b in fill_bytes.items()}
    key_mask = shot.de_to(key_bytes) <= pde
    # any zone/keyline colour (for the tile reference)
    marks = np.zeros((shot.h, shot.w), dtype=bool)
    for k, v in calib.items():
        if k.startswith("zone.") or k.startswith("mark."):
            marks |= shot.de_to(v["screen"]) <= 15.0
    rows = []
    for fid, f in sorted(shot.fighters.items()):
        info = shot.rings.get(fid)
        if not info or not info["shown"]:
            rows.append({"fighter": fid, "name": FIGHTER_NAMES.get(fid, fid), "ring": "not shown (trace)"})
            continue
        look = info["look"]
        fs = fighter_scale(fid)
        z = f.world[2] + RING.RING_SPEC["zMax"]
        bands = ring_bands(look)
        fill_pix = shot.pixels(band_samples(look, bands["fill"][0], bands["fill"][1], fs, f.world, z))
        key_pix = shot.pixels(band_samples(look, bands["keylineIn"][0], bands["keylineIn"][1], fs, f.world, z)) | \
            shot.pixels(band_samples(look, bands["keylineOut"][0], bands["keylineOut"][1], fs, f.world, z))
        fill_m = shot.mask_of(fill_pix)
        key_m = shot.mask_of(key_pix) & ~fill_m
        team = team_masks[look]
        n_zone = int(fill_m.sum())
        n_team = int((fill_m & team).sum())
        frac = n_team / n_zone if n_zone else 0.0
        need = rt["minFraction"]["hero" if fid.endswith("-hero") else "sidekick"]
        # tile reference: r 30*FS..36 in the sector, outside the glyph slot squares, not a mark colour
        tile_pts = []
        for i in range(720):
            t = 2 * math.pi * i / 720
            dx, dy = math.cos(t), math.sin(t)
            if not in_sector(dx, dy):
                continue
            for rr in np.linspace(30.0 * fs, 36.0, 13):
                x, y = rr * dx, rr * dy
                if any(abs(x - gx) <= 14 and abs(y - gy) <= 14 for gx in (-32, 32) for gy in (-32, 32)):
                    continue
                tile_pts.append((f.world[0] + x, f.world[1] + y, f.world[2]))
        tile_m = shot.mask_of(shot.pixels(tile_pts)) & ~marks & ~key_mask
        for tm in team_masks.values():
            tile_m &= ~tm
        # DIAGNOSTIC (after the shoot, NOT a gate): the registered tile reference drops every pixel within dE 15 of ANY
        # zone colour - on the light fixture tiles that is the tile itself (light-gray zone ~ tile), leaving 0..30 px of
        # shadow. The diagnostic reference drops only the keyline, the team fills and the zones of THIS cell.
        diag = None
        if cells is not None:
            own = next((c for c in cells if (c["x"], c["y"]) == tuple(f.cell)), None)
            dm = shot.mask_of(shot.pixels(tile_pts)) & ~key_mask
            for tm in team_masks.values():
                dm &= ~tm
            for zk in (own or {}).get("zones", []):
                if "zone." + zk in calib:
                    dm &= ~(shot.de_to(calib["zone." + zk]["screen"]) <= 15.0)
            diag = {"tilePx": int(dm.sum()), "status": "диагностика после съёмки, не гейт"}
            for vn in ("color", "gray", "deuteranopia"):
                lk_, lt_ = shot.med_lum(key_m & key_mask, vn), shot.med_lum(dm, vn)
                diag[vn] = round(wcag(lk_, lt_), 3) if lk_ is not None and lt_ is not None else None
        fill_core = fill_m & team
        key_core = key_m & key_mask
        variants = {}
        for vn in ("color", "gray", "deuteranopia"):
            lf, lk, lt = shot.med_lum(fill_core, vn), shot.med_lum(key_core, vn), shot.med_lum(tile_m, vn)
            variants[vn] = {"fillVsKeyline": round(wcag(lf, lk), 3) if lf is not None and lk is not None else None,
                            "keylineVsTile": round(wcag(lk, lt), 3) if lk is not None and lt is not None else None,
                            "fillRelLum": lf, "keylineRelLum": lk, "tileRelLum": lt}
        shape = classify_shape(shot, fid, team, fs, z)
        want_shape = "circle" if look == "P1" else "hexagon"
        kv_min = rt["keylineVsTile"]["minWcag"]
        fk_min = rt["fillVsKeyline"]["minWcag"]
        rows.append({
            "fighter": fid, "name": FIGHTER_NAMES.get(fid, fid), "cell": list(f.cell), "team": info["team"],
            "look": look, "mode": info["mode"], "scale": fs, "zonePx": n_zone, "teamPx": n_team,
            "fraction": round(frac, 4), "minFraction": need, "fractionPass": bool(frac >= need),
            "keylinePx": int(key_core.sum()), "tilePx": int(tile_m.sum()),
            "fillMedianRgb": shot.med_rgb(fill_core), "fillMedianGrayY": (float(np.median(shot.luma_gray[fill_core]))
                                                                          if fill_core.any() else None),
            "fillMedianLab": ([round(float(x), 2) for x in np.median(shot.lab[fill_core].reshape(-1, 3), axis=0)]
                              if fill_core.any() else None),
            "variants": variants,
            "keylineVsTilePass": all(v["keylineVsTile"] is not None and v["keylineVsTile"] >= kv_min
                                     for v in variants.values()) and int(key_core.sum()) >= 10,
            "fillVsKeylinePass": all(v["fillVsKeyline"] is not None and v["fillVsKeyline"] >= fk_min
                                     for v in variants.values()),
            "shape": shape, "expectedShape": want_shape, "shapePass": shape["shape"] == want_shape,
            "keylineVsTileDiag": diag})
    return {"frame": L.rel(shot.png), "trace": L.rel(shot.trace_path), "projection": shot.proj.to_dict().get("ok"),
            "fighters": rows}


def diag_range(rings: dict) -> list | None:
    vals = [v for tag in rings for r in rings[tag]["fighters"] if "fraction" in r and r.get("keylineVsTileDiag")
            for vn, v in r["keylineVsTileDiag"].items() if vn in ("color", "gray", "deuteranopia") and v is not None]
    return [min(vals), max(vals)] if vals else None


def shape_in_variants(shot: Shot, fid: str, look: str, calib: dict, pde: float) -> dict:
    """The classifier on the gray and deuteranopia derivatives: a team pixel there = within pixelDeltaE of the
    variant-transformed screen bytes of the fill."""
    from qa010lib import color as C
    np = shot.np
    out = {}
    f = shot.fighters[fid]
    fs = fighter_scale(fid)
    z = f.world[2] + RING.RING_SPEC["zMax"]
    fill = np.array(calib["team.p1.fill" if look == "P1" else "team.p2.fill"]["screen"], dtype=np.uint8).reshape(1, 1, 3)
    for vn, fn in (("gray", C.grayscale), ("deuteranopia", C.deuteranopia)):
        img = shot.variants[vn]
        lab = C.linear_to_lab(C.u8_to_linear(img))
        target = C.linear_to_lab(C.u8_to_linear(fn(fill)))[0, 0]
        mask = np.linalg.norm(lab - target, axis=-1) <= pde
        out[vn] = classify_shape(shot, fid, mask, fs, z)["shape"]
    return out


# ------------------------------------------------------------------ zones rev 2
GLYPH_SLOT = {0: (-32.0, 32.0), 1: (32.0, -32.0), 2: (-32.0, -32.0), 3: (32.0, 32.0)}


def slot_points(cx, cy, i, z=0.4, step=0.5):
    side = i % 4
    pts = []
    u = -46.0
    while u <= 46.0:
        d = 33.0
        while d <= 45.0:
            if side == 0:
                pts.append((cx + u, cy + d, z))
            elif side == 1:
                pts.append((cx - d, cy + u, z))
            elif side == 2:
                pts.append((cx + u, cy - d, z))
            else:
                pts.append((cx + d, cy + u, z))
            d += step
        u += step
    gx, gy = GLYPH_SLOT[side]
    a = -14.0
    while a <= 14.0:
        b = -14.0
        while b <= 14.0:
            pts.append((cx + gx + a, cy + gy + b, z))
            b += step
        a += step
    return pts


def zones_rev2(shot: Shot, cells: list[dict], th: dict, calib: dict) -> dict:
    np = shot.np
    pde = th["calibration"]["pixelDeltaE"]
    zt = th["zones"]
    key_mask = shot.de_to(calib["zone.keyline"]["screen"]) <= pde
    occupied = {tuple(f.cell) for f in shot.fighters.values()}
    excl_pts = []
    for (x, y) in occupied:
        c = shot.board.cell_center(x, y)
        for i in range(360):
            t = 2 * math.pi * i / 360
            for rr in np.linspace(0.0, 31.0, 32):
                excl_pts.append((c[0] + rr * math.cos(t), c[1] + rr * math.sin(t), 0.4))
    excl = shot.mask_of(shot.pixels(excl_pts))
    passable = {(c["x"], c["y"]): c for c in cells if not c["obstacle"]}
    zone_keys = sorted({z for c in cells for z in c["zones"]})
    fill_masks = {k: shot.de_to(calib["zone." + k]["screen"]) <= pde for k in zone_keys}

    def tile_mask(cl):
        pts = []
        for (x, y) in cl:
            c = shot.board.cell_center(x, y)
            a = -18.0
            while a <= 18.0:
                b = -18.0
                while b <= 18.0:
                    pts.append((c[0] + a, c[1] + b, 0.0))
                    b += 1.0
                a += 1.0
        return shot.mask_of(shot.pixels(pts))

    tiles = {}
    for k in zone_keys:
        free = [p for p, c in passable.items() if k in c["zones"] and p not in occupied]
        tiles[k] = tile_mask(free) & ~key_mask
    per_slot = []
    for (x, y), c in sorted(passable.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if not c["zones"]:
            continue
        cc = shot.board.cell_center(x, y)
        for i, k in enumerate(c["zones"]):
            sm = shot.mask_of(shot.pixels(slot_points(cc[0], cc[1], i))) & ~excl
            kmask = sm & key_mask
            fmask = sm & fill_masks[k]
            rec = {"cell": [x, y], "zone": k, "slot": i % 4, "occupied": (x, y) in occupied,
                   "multizone": len(c["zones"]) > 1, "keylinePx": int(kmask.sum()), "fillPx": int(fmask.sum()),
                   "variants": {}}
            ok_all = rec["keylinePx"] >= zt["minKeylinePxPerSlot"]
            for vn in ("color", "gray", "deuteranopia"):
                lk, lf, lt = shot.med_lum(kmask, vn), shot.med_lum(fmask, vn), shot.med_lum(tiles[k], vn)
                kv = round(wcag(lk, lt), 3) if lk is not None and lt is not None else None
                fk = round(wcag(lf, lk), 3) if lf is not None and lk is not None else None
                rec["variants"][vn] = {"keylineVsTile": kv, "fillVsKeyline": fk}
                ok_all &= kv is not None and kv >= zt["keylineVsTile"]["minWcag"]
                ok_all &= fk is not None and fk >= zt["fillVsKeyline"]["minWcag"]
            rec["pass"] = bool(ok_all)
            per_slot.append(rec)
    # per zone aggregate (free cells only) + multizone verdicts
    zones = {}
    for k in zone_keys:
        recs = [r for r in per_slot if r["zone"] == k and not r["occupied"]]
        zones[k] = {"slots": len(recs), "pass": sum(r["pass"] for r in recs),
                    "keylinePxMedian": float(np.median([r["keylinePx"] for r in recs])) if recs else None,
                    "variants": {vn: {m: (round(float(np.median(vals)), 3) if vals else None)
                                      for m, vals in (("keylineVsTile", [r["variants"][vn]["keylineVsTile"] for r in recs
                                                                         if r["variants"][vn]["keylineVsTile"]]),
                                                      ("fillVsKeyline", [r["variants"][vn]["fillVsKeyline"] for r in recs
                                                                         if r["variants"][vn]["fillVsKeyline"]]))}
                                 for vn in ("color", "gray", "deuteranopia")}}
    mz_cells = sorted({tuple(r["cell"]) for r in per_slot if r["multizone"]})
    mz = []
    for cell in mz_cells:
        recs = [r for r in per_slot if tuple(r["cell"]) == cell]
        mz.append({"cell": list(cell), "zones": [r["zone"] for r in recs], "pass": all(r["pass"] for r in recs),
                   "failing": [r["zone"] for r in recs if not r["pass"]]})
    return {"frame": L.rel(shot.png), "zones": zones, "slots": per_slot,
            "multizone": {"cells": len(mz), "pass": sum(m["pass"] for m in mz), "list": mz},
            "method": "t53-thresholds.json zones (rev 2)"}


def zone_pairs_by_shape(cells: list[dict], styles: dict) -> dict:
    out = []
    for c in cells:
        zs = c["zones"]
        for i in range(len(zs)):
            for j in range(i + 1, len(zs)):
                a, b = styles[zs[i]], styles[zs[j]]
                out.append({"cell": [c["x"], c["y"]], "pair": [zs[i], zs[j]],
                            "shapeDiffers": a["stroke"] != b["stroke"] or a["glyph"] != b["glyph"]})
    return {"pairs": len(out), "shapeDiffers": sum(p["shapeDiffers"] for p in out),
            "failing": [p for p in out if not p["shapeDiffers"]]}


# ------------------------------------------------------------------ tags, damage, icon, panels
def _bbox(w):
    b = w.get("bbox")
    return tuple(b) if isinstance(b, tuple) and len(b) == 4 else None


def text_contrast(shot: Shot, text_box, bg_box, text_rgb, bg_rgb, text_de=10.0, bg_de=6.0):
    np = shot.np
    tm = np.zeros((shot.h, shot.w), dtype=bool)
    bm = np.zeros((shot.h, shot.w), dtype=bool)
    x0, y0, x1, y1 = (int(round(v)) for v in text_box)
    tm[max(0, y0):y1, max(0, x0):x1] = True
    x0, y0, x1, y1 = (int(round(v)) for v in bg_box)
    bm[max(0, y0):y1, max(0, x0):x1] = True
    core = tm & (shot.de_to(text_rgb) <= text_de)
    bg = bm & (shot.de_to(bg_rgb) <= bg_de)
    out = {"textPx": int(core.sum()), "bgPx": int(bg.sum())}
    for vn in ("color", "gray", "deuteranopia"):
        lt, lb = shot.med_lum(core, vn), shot.med_lum(bg, vn)
        out[vn] = round(wcag(lt, lb), 3) if lt is not None and lb is not None and core.sum() >= 5 else None
    return out


def tags_damage(shot: Shot, th: dict, role: str) -> dict:
    np = shot.np
    tg = th["tags"]
    txt, bg = (242, 236, 222), (22, 26, 40)
    figs = {fid: tuple(v["bbox"]) for fid, v in shot.block.figures.items()}
    plate = [_bbox(w) for w in shot.widgets("plate") if w.get("geom") == "painted" and w.get("visible") == "1"]
    icon = shot.block.icon.value["bbox"] if shot.block.icon is not None else None
    panels = [tuple(p["bbox"]) for p in shot.block.panels if p["visible"] and p["geom"] == "painted"]
    dmg = [w for w in shot.widgets("board.damage") if w.get("geom") == "painted"]
    dmg_boxes = [_bbox(w) for w in dmg]
    tags = {}
    for w in shot.block.widgets:
        wid = w.get("id", "")
        if not wid.startswith("board.tag"):
            continue
        tags.setdefault(w.get("fighter"), {})[wid] = w
    plate_owner = next((w.get("fighter") for w in shot.widgets("plate") if w.get("visible") == "1"), None)
    # t53 revision 1 (tags.mode, tags.binding): the plate owner's tag is hidden only while the plate is bound to it;
    # every painted tag's centre is nearer its owner's figure than any other figure
    rev1 = threshold_revision(th, 1)
    p_bound = plate_state(shot.block.widgets, figs, shot.text, shot.png.name)["bound"] if rev1 else None
    rows = []
    for fid, parts in sorted(tags.items()):
        root = parts.get("board.tag") or {}
        box = _bbox(root)
        painted = root.get("geom") == "painted" and root.get("visible") == "1" and box is not None
        rec = {"fighter": fid, "name": FIGHTER_NAMES.get(fid, fid), "mode": root.get("mode"), "painted": painted,
               "bbox": list(box) if box else None, "placement": root.get("placement")}
        fig = shot.block.figures.get(fid, {})
        by_type = "compact" if fig.get("art") == "1" and fig.get("blockout") == "0" else "full"
        if fid == plate_owner:
            expect = "compact" if p_bound is False else "hidden"
            rec["plateBound"] = p_bound
        else:
            expect = by_type
        rec["expectedMode"] = expect
        rec["modePass"] = rec["mode"] == expect
        if not painted:
            # a hidden tag is correct only when the rule says hidden (the plate owner)
            rec["pass"] = rec["mode"] == "hidden" and expect == "hidden"
            rows.append(rec)
            continue
        lines = {}
        for pid in ("board.tag.name", "board.tag.hp"):
            p = parts.get(pid)
            if p and p.get("geom") == "painted" and _bbox(p):
                lines[pid] = {**text_contrast(shot, _bbox(p), box, txt, bg), "font": int(p.get("font", 0))}
        rec["lines"] = lines
        excl = [_bbox(parts[p]) for p in ("board.tag.name", "board.tag.hp", "board.tag.bar", "board.tag.chip")
                if p in parts and _bbox(parts[p])]
        m = np.zeros((shot.h, shot.w), dtype=bool)
        x0, y0, x1, y1 = (int(round(v)) for v in box)
        m[y0:y1, x0:x1] = True
        for e in excl:
            ex0, ey0, ex1, ey1 = (int(round(v)) for v in e)
            m[ey0:ey1, ex0:ex1] = False
        integ = float((shot.de_to(bg)[m] <= 6.0).mean()) if m.any() else None
        rec["backgroundIntegrity"] = round(integ, 4) if integ is not None else None
        others = [_bbox(v["board.tag"]) for k, v in tags.items() if k != fid
                  and v.get("board.tag", {}).get("geom") == "painted" and _bbox(v.get("board.tag", {}))]
        rec["overlaps"] = {"tag": sum(inter_area(box, o) for o in others),
                           "icon": inter_area(box, icon) if icon else 0.0,
                           "plate": sum(inter_area(box, p) for p in plate if p),
                           "damage": sum(inter_area(box, d) for d in dmg_boxes if d),
                           "panel": sum(inter_area(box, p) for p in panels)}
        rec["overlapOtherFigures"] = sum(inter_area(box, r) for k, r in figs.items() if k != fid)
        eps = tg["overlaps"]["epsilonPx2"]
        rec["overlapPass"] = all(v <= eps for v in rec["overlaps"].values())
        rec["textPass"] = all(all(v[vn] is not None and v[vn] >= tg["textVsBackground"]["minWcag"]
                                  for vn in ("color", "gray", "deuteranopia")) for v in lines.values()) and bool(lines)
        rec["heightPass"] = all(v["font"] >= tg["textHeight"]["minSu"] for v in lines.values())
        rec["integrityPass"] = integ is not None and integ >= tg["backgroundIntegrity"]["min"]
        rec["pass"] = rec["textPass"] and rec["heightPass"] and rec["integrityPass"] and rec["overlapPass"] and rec["modePass"]
        if rev1 is not None and fid in figs:
            cen = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            own = point_rect_dist(cen, figs[fid])
            dists = {k: point_rect_dist(cen, r) for k, r in figs.items() if k != fid}
            nearest = min(dists, key=dists.get) if dists else None
            rec["binding"] = {"centreToOwner": round(own, 1), "nearestOther": nearest,
                              "centreToNearestOther": round(dists[nearest], 1) if nearest else None,
                              "gapToOwner": round(rect_gap(box, figs[fid]), 1)}
            rec["bindingPass"] = all(d > own for d in dists.values())
            rec["pass"] = rec["pass"] and rec["bindingPass"]
        rows.append(rec)
    # the plate owner: no tag expected (hidden) - with revision 1 only while the plate is bound
    if plate_owner and plate_owner not in tags:
        ok = p_bound is not False
        rows.append({"fighter": plate_owner, "name": FIGHTER_NAMES.get(plate_owner, plate_owner), "mode": "hidden",
                     "expectedMode": "hidden" if ok else "compact", "modePass": ok, "painted": False, "pass": ok,
                     "note": "владелец плашки: тег скрыт (плашка показывает то же)"})
    damage = []
    for w in dmg:
        box = _bbox(w)
        tbox = next((_bbox(t) for t in shot.widgets("board.damage.text") if t.get("fighter") == w.get("fighter")), box)
        tc = text_contrast(shot, tbox, box, (255, 224, 175), (22, 26, 40))
        target = w.get("fighter")
        cen = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        dists = {k: point_rect_dist(cen, r) for k, r in figs.items()}
        nearest = min(dists, key=dists.get) if dists else None
        ov = {"tag": sum(inter_area(box, tuple(v["board.tag"]["bbox"])) for v in tags.values()
                         if v.get("board.tag", {}).get("geom") == "painted"),
              "icon": inter_area(box, icon) if icon else 0.0, "plate": sum(inter_area(box, p) for p in plate if p)}
        dmin = th["damage"]["textVsCapsule"]["minWcag"]
        damage.append({"fighter": target, "name": FIGHTER_NAMES.get(target, target), "bbox": list(box),
                       "amount": w.get("amount"), "seq": w.get("seq"), "placement": w.get("placement"),
                       "stableFrames": w.get("stableFrames"), "contrast": tc, "overlaps": ov,
                       "nearestFigure": nearest, "bindingPass": nearest == target or target not in figs,
                       "overlapPass": all(v <= 0.5 for v in ov.values()),
                       "textPass": all(tc[vn] is not None and tc[vn] >= dmin for vn in ("color", "gray", "deuteranopia"))})
    return {"frame": L.rel(shot.png), "client": role, "plateOwner": plate_owner, "tags": rows, "damage": damage}


def threshold_revision(th: dict, number: int) -> dict | None:
    """The registered revision `number` of t53-thresholds.json (None when not registered)."""
    return next((r for r in th.get("revisions") or [] if r.get("revision") == number), None)


def plate_bound(plate_box, owner: str | None, figs: dict) -> bool | None:
    """ChoosePlateRect / IsRectBoundTo: the plate's rect gap to its owner's figure is strictly smaller than to every
    other figure (None without a plate or an owner figure)."""
    if plate_box is None or owner not in figs:
        return None
    own = rect_gap(plate_box, figs[owner])
    return all(rect_gap(plate_box, r) > own for k, r in figs.items() if k != owner)


PLATE_LINE = re.compile(r"(?:^|\s)PLATE fighter=(\S+) bbox=\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)(.*)$")


def plate_line_before(text: str, frame_name: str, owner: str | None) -> dict | None:
    """The client's own plate placement for `owner` in force when the LAST late section of `frame_name` was written:
    the last standalone `PLATE fighter=<owner> bbox=(..) … bound=0|1` line before it (C++ ChoosePlateRect)."""
    if not text or not owner:
        return None
    idx = text.rfind(f"SHOT late begin file={frame_name} ")
    if idx < 0:
        return None
    for line in reversed(text[:idx].splitlines()):
        m = PLATE_LINE.search(line)
        if m and m.group(1) == owner and "SHOT plate" not in line:
            b = re.search(r"\bbound=(\d)", m.group(6))
            return {"bbox": tuple(float(m.group(i)) for i in range(2, 6)),
                    "bound": None if b is None else b.group(1) == "1"}
    return None


def plate_state(widgets, figs: dict, text: str | None, frame_name: str) -> dict:
    """Plate owner + bound for the mode rule: the painted plate (rect rule on the pixels' bbox), or - when the plate is
    logically visible but not painted yet (it appeared in the capture frame) - the client's PLATE line."""
    plate = next((w for w in widgets if w.get("id") == "plate" and w.get("visible") == "1"), None)
    owner = plate.get("fighter") if plate is not None else None
    box = _bbox(plate) if plate is not None and plate.get("geom") == "painted" else None
    line = plate_line_before(text or "", frame_name, owner) if owner else None
    if box is not None:
        return {"owner": owner, "bbox": list(box), "bound": plate_bound(box, owner, figs), "source": "painted",
                "traceBound": line["bound"] if line else None}
    if line is not None:
        rb = plate_bound(line["bbox"], owner, figs)
        return {"owner": owner, "bbox": list(line["bbox"]), "bound": line["bound"] if line["bound"] is not None else rb,
                "source": "PLATE line (plate not painted in this frame)", "rectBound": rb}
    return {"owner": owner, "bbox": None, "bound": None, "source": None}


def block_tag_binding(block, text: str | None = None) -> dict:
    """t53 revision 1 on one SHOT block (late section): every painted tag's centre is strictly nearer its owner's
    FigureScreenRect than any other figure's; the plate owner's tag is hidden only when the plate is bound."""
    figs = {fid: tuple(v["bbox"]) for fid, v in block.figures.items()}
    ps = plate_state(block.widgets, figs, text, block.name)
    plate_owner, p_bound = ps["owner"], ps["bound"]
    rows = []
    for w in block.widgets:
        if w.get("id") != "board.tag":
            continue
        fid = w.get("fighter")
        box = _bbox(w)
        painted = w.get("geom") == "painted" and w.get("visible") == "1" and box is not None and fid in figs
        rec = {"fighter": fid, "name": FIGHTER_NAMES.get(fid, fid), "mode": w.get("mode"), "painted": painted,
               "placement": w.get("placement"), "ring": w.get("ring"), "traceBound": w.get("bound"),
               "softPx2": w.get("softPx2")}
        if fid == plate_owner and p_bound is not None:
            rec["plateOwner"] = True
            rec["plateBound"] = p_bound
            rec["expectedPlateOwnerMode"] = "hidden" if p_bound else "compact"
            rec["plateOwnerModePass"] = rec["mode"] == rec["expectedPlateOwnerMode"]
        if painted:
            cen = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            own = point_rect_dist(cen, figs[fid])
            others = {k: point_rect_dist(cen, r) for k, r in figs.items() if k != fid}
            nearest = min(others, key=others.get) if others else None
            rec.update(bbox=list(box), centre=[round(cen[0], 1), round(cen[1], 1)], centreToOwner=round(own, 1),
                       nearestOther=nearest, centreToNearestOther=round(others[nearest], 1) if nearest else None,
                       gapToOwner=round(rect_gap(box, figs[fid]), 1),
                       overlapOtherFiguresPx2=round(sum(inter_area(box, r) for k, r in figs.items() if k != fid), 1),
                       bindingPass=all(d > own for d in others.values()))
        rows.append(rec)
    return {"plate": ps, "tags": rows}


def tag_binding_scan(traces: list[Path]) -> dict:
    """Every late SHOT section of the given client traces (all published frames), t53 revision 1."""
    from qa010lib.trace import parse_trace
    frames, painted, fails, mode_fails = [], 0, [], []
    for tp in traces:
        tr = parse_trace(tp)
        text = Path(tp).read_text(encoding="utf-8", errors="replace")
        # every captured frame counts (the gate is stricter than the published set: K3 publishes a subset of its
        # SHOTs into git); a re-shot name keeps only its LAST block (the file on disk). `published` marks the frames
        # present next to the trace (K1: <run>/phase2-board-<side>-*.png, K3: <run>/<side>/*.png).
        side = "host" if "client-host" in tp.name else "joiner"
        published = {p.name for p in tp.parent.rglob("*.png") if p.parent.name == side or f"-{side}-" in p.name}
        last = {}
        for blk in tr.shots:
            if blk.late:
                last[blk.name] = blk
        for blk in last.values():
            doc = block_tag_binding(blk, text)
            if not doc["tags"]:
                continue
            fr = {"trace": L.rel(tp), "frame": blk.name, "lateFrame": blk.late_frame,
                  "published": blk.name in published, **doc}
            frames.append(fr)
            for r in doc["tags"]:
                if r.get("painted"):
                    painted += 1
                    if not r.get("bindingPass"):
                        fails.append(f"{L.rel(tp)} {blk.name} {r['name']} centre→owner {r['centreToOwner']} "
                                     f"vs {FIGHTER_NAMES.get(r['nearestOther'], r['nearestOther'])} "
                                     f"{r['centreToNearestOther']}")
                if r.get("plateOwner") and not r.get("plateOwnerModePass"):
                    mode_fails.append(f"{L.rel(tp)} {blk.name} {r['name']} mode={r['mode']} "
                                      f"expected={r['expectedPlateOwnerMode']} (plate bound={r['plateBound']})")
    placements = {}
    for fr in frames:
        for r in fr["tags"]:
            if r.get("painted"):
                key = f"{r.get('placement')} ring {r.get('ring')}"
                placements[key] = placements.get(key, 0) + 1
    gaps = [r["gapToOwner"] for fr in frames for r in fr["tags"] if r.get("painted")]
    return {"sections": len(frames), "paintedTags": painted, "bindingFail": fails, "plateOwnerModeFail": mode_fails,
            "pass": painted > 0 and not fails and not mode_fails, "placements": placements,
            "gapToOwnerMax": max(gaps) if gaps else None, "frames": frames}


def icon_binding(shot: Shot) -> dict:
    ic = shot.block.icon
    if ic is None:
        return {"present": False, "iconHiddenLate": shot.block.icon_hidden_late}
    box = ic.value["bbox"]
    target = ic.value["fighter"]
    figs = {fid: tuple(v["bbox"]) for fid, v in shot.block.figures.items()}
    cen = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    d = {k: point_rect_dist(cen, r) for k, r in figs.items()}
    nearest = min(d, key=d.get) if d else None
    ov = {k: inter_area(box, r) for k, r in figs.items() if k != target}
    return {"present": True, "fighter": target, "bbox": list(box), "anchor": ic.value.get("anchor"),
            "fallback": ic.value.get("fallback"), "texture": ic.value.get("texture"), "geom": ic.value.get("geom"),
            "nearestFigure": nearest, "bindingPass": nearest == target, "overlapOtherFigures": ov,
            "overlapPass": all(v <= 0.5 for v in ov.values())}


def k3_panels(shot: Shot, th: dict) -> dict:
    from qa010lib.projection import cell_world_quad, project_polygon
    figs = {fid: tuple(v["bbox"]) for fid, v in shot.block.figures.items()}
    panels = [p for p in shot.block.panels if p["visible"] and p["geom"] == "painted"]
    names = {v: k for k, v in FIGHTER_NAMES.items()}
    attacker = target = None
    for m in COMBAT_MARKER.finditer(shot.text[:shot.text.find("SHOT late begin file=" + shot.png.name)]):
        nm = m.group(1).strip()
        if m.group(2) == "1":
            attacker = names.get(nm, nm)
        if m.group(3) == "1":
            target = names.get(nm, nm)
    if shot.block.icon is not None:
        target = shot.block.icon.value["fighter"]
    key_cells = set()
    for fid in (attacker, target):
        f = shot.fighters.get(fid) if fid else None
        if f:
            key_cells.add(tuple(f.cell))
    reach = set(tuple(c) for c in (shot.block.reachable.value["cells"] if shot.block.reachable else []))
    cam = shot.proj.camera
    gated, other = [], []

    def quad_rect(x, y):
        q = project_polygon(cam, cell_world_quad(shot.board, x, y))
        if q is None:
            return None
        xs, ys = [p[0] for p in q], [p[1] for p in q]
        return (min(xs), min(ys), max(xs), max(ys)), q

    from qa010lib.geometry import clip_polygon_to_rect, polygon_area
    for p in panels:
        pr = tuple(p["bbox"])
        for fid, r in figs.items():
            a = inter_area(pr, r)
            if a > th["k3Panels"]["epsilonPx2"]:
                gated.append({"panel": p["id"], "what": f"figure {fid}", "px2": round(a, 1)})
        for y in range(shot.board.height):
            for x in range(shot.board.width):
                qr = quad_rect(x, y)
                if qr is None:
                    continue
                a = polygon_area(clip_polygon_to_rect(qr[1], pr))
                if a <= 0.5:
                    continue
                entry = {"panel": p["id"], "cell": [x, y], "px2": round(a, 1)}
                if (x, y) in key_cells or (x, y) in reach:
                    gated.append({**entry, "what": "attacker/target cell" if (x, y) in key_cells else "reachable cell"})
                else:
                    other.append(entry)
    return {"frame": L.rel(shot.png), "panels": [{"id": p["id"], "bbox": list(p["bbox"])} for p in panels],
            "attacker": attacker, "target": target, "gatedOverlaps": gated, "pass": not gated,
            "otherCellOverlaps": other, "otherCellOverlapPx2": round(sum(o["px2"] for o in other), 1)}


def plate_vs_figures(shot: Shot) -> dict:
    owner = next((w.get("fighter") for w in shot.widgets("plate") if w.get("visible") == "1"), None)
    box = next((_bbox(w) for w in shot.widgets("plate") if w.get("visible") == "1" and w.get("geom") == "painted"), None)
    if box is None and shot.block.plate is not None:
        box = shot.block.plate.value["bbox"]
    if box is None:
        return {"plate": None}
    ov = {k: round(inter_area(box, tuple(v["bbox"])), 1) for k, v in shot.block.figures.items() if k != owner}
    # binding (recorded, NOT a registered gate): rect gap of the plate to its owner vs to every other figure
    gaps = {k: round(rect_gap(box, tuple(v["bbox"])), 1) for k, v in shot.block.figures.items()}
    own = gaps.get(owner)
    nearest_other = min((g for k, g in gaps.items() if k != owner), default=None)
    return {"plate": list(box), "owner": owner, "overlaps": ov, "pass": all(v <= 0.5 for v in ov.values()),
            "binding": {"gapToOwner": own, "nearestOtherGap": nearest_other, "gaps": gaps,
                        "bound": own is not None and (nearest_other is None or own < nearest_other),
                        "status": "записывается, не гейт (правило не регистрировалось до съёмки)"}}


def chip_vs_ring(shot: Shot, rings: dict, calib: dict) -> list[dict]:
    """Chip colour (tag chip / plate team shape pixels) against the ring fill median of the same fighter."""
    np = shot.np
    ring_by = {r["fighter"]: r for r in rings["fighters"] if r.get("fillMedianLab")}
    out = []
    chips = [(w, "tag") for w in shot.widgets("board.tag.chip") if w.get("geom") == "painted"]
    chips += [(w, "plate") for w in shot.widgets("plate.teamshape") if w.get("geom") == "painted"]
    for w, kind in chips:
        fid = w.get("fighter")
        box = _bbox(w)
        look = w.get("look") or (rings and next((r["look"] for r in rings["fighters"] if r["fighter"] == fid
                                                 and "look" in r), None))
        want = calib["team.p1.fill" if look == "P1" else "team.p2.fill"]["screen"]
        m = np.zeros((shot.h, shot.w), dtype=bool)
        x0, y0, x1, y1 = (int(round(v)) for v in box)
        m[y0:y1, x0:x1] = True
        m &= shot.de_to(want) <= 25.0
        rec = {"fighter": fid, "kind": kind, "bbox": list(box), "chipPx": int(m.sum()),
               "shapeTrace": w.get("shape") or ("circle" if look == "P1" else "hex")}
        r = ring_by.get(fid)
        if m.any() and r:
            chip_lab = np.median(shot.lab[m].reshape(-1, 3), axis=0)
            de = float(np.linalg.norm(chip_lab - np.array(r["fillMedianLab"])))
            rec.update(deltaE76=round(de, 2), ringShape=r["shape"]["shape"],
                       colourPass=de <= 6.0,
                       shapePass=(rec["shapeTrace"] in ("circle",) and r["shape"]["shape"] == "circle") or
                       (rec["shapeTrace"] in ("hex", "hexagon") and r["shape"]["shape"] == "hexagon"))
        out.append(rec)
    return out


# ------------------------------------------------------------------ analyze (one board)
def run_qa(args, json_out):
    return T52.qa(args, json_out)


def cmd_analyze(a) -> int:
    import numpy as np
    evidence = Path(a.evidence).resolve()
    th = thresholds(evidence)
    calib = th["calibration"]["bytes"]
    key = a.board
    spec = BOARDS[key]
    prof_doc = load_json(PROFILES)
    styles = prof_doc["zoneStyles"]
    cells = T52.board_cells(T52_EVIDENCE if key == "cobble-5x6" else evidence, key)
    out = evidence / "analysis" / key
    out.mkdir(parents=True, exist_ok=True)
    k1, k3 = Path(a.k1_run).resolve(), Path(a.k3_run).resolve()
    frames = {
        "K1_host": (k1 / "phase2-board-host-1920x1080.png", k1 / "phase2-client-host.trace.log", "host"),
        "K1_joiner": (k1 / "phase2-board-joiner-1920x1080.png", k1 / "phase2-client-joiner.trace.log", "joiner"),
    }
    k3_join_t, k3_host_t = k3 / "combat-client-joiner.trace.log", k3 / "combat-client-host.trace.log"
    k3_main = None
    for n in T52.K3_ORDER:
        p = k3 / "joiner" / n
        if p.is_file() and n != "s09-damage-number.png":
            s = Shot(p, k3_join_t)
            if s.block.icon is not None:
                k3_main = n
                break
    frames["K3"] = (k3 / "joiner" / (k3_main or "s09-combat-resolve-revealed.png"), k3_join_t, "joiner")
    dmg_frames = {}
    if (k3 / "joiner" / "s09-damage-number.png").is_file():
        dmg_frames["damage_first_joiner"] = (k3 / "joiner" / "s09-damage-number.png", k3_join_t, "joiner")
    for side, tp in (("host", k3_host_t), ("joiner", k3_join_t)):
        p = k3 / side / "s09-damage-combat.png"
        if p.is_file():
            dmg_frames[f"damage_combat_{side}"] = (p, tp, side)
    probes = {}
    for size, run in (("24", a.probe24_run), ("48", a.probe48_run)):
        if run:
            rr = Path(run).resolve()
            probes[size] = (rr / "phase2-board-host-1920x1080.png", rr / "phase2-client-host.trace.log", "host")
    summary = {"schema": "unmatched.t53-analysis/1", "board": key, "boardId": spec["boardId"],
               "status": "измерено (не приёмка)", "thresholds": L.rel(evidence / "t53-thresholds.json"),
               "frames": {k: L.rel(v[0]) for k, v in {**frames, **dmg_frames}.items()},
               "probes": {k: L.rel(v[0]) for k, v in probes.items()}, "k3Frame": k3_main}
    shots = {k: Shot(*v[:2]) for k, v in {**frames, **dmg_frames, **{f"probe{k}": v for k, v in probes.items()}}.items()}
    # ---- classify: strict + render reference + pixel provenance
    all_pngs = [str(v[0]) for v in {**frames, **dmg_frames, **probes}.values()]
    cl = subprocess.run([sys.executable, str(T52.CLASSIFY)] + all_pngs + ["--strict", "--render-reference",
                                                                          "--require-captured", "--require",
                                                                          "packaged-live"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=L.NO_WINDOW)
    (out / "classify-strict-render-captured.json").write_text(cl.stdout, encoding="utf-8", newline="\n")
    cls = json.loads(cl.stdout) if cl.stdout.strip().startswith("[") else []
    summary["classify"] = {"exit": cl.returncode, "frames": [
        {"frame": Path(r["frame"]).name, "dir": Path(r["frame"]).parent.name, "class": r["class"], "grade": r["grade"],
         "rejected": r["rejected"], "S6": (r.get("live") or {}).get("strict", {}).get("S6_shot_captured"),
         "missing": (r.get("live") or {}).get("missingStrict")} for r in cls]}
    # ---- derivatives (gray / deuteranopia, outside git) for the contact sheet + manifest
    derived = Path(a.derived_root) / key
    rc, dm = run_qa(["derive"] + [str(frames[k][0]) for k in ("K1_host", "K1_joiner", "K3")] +
                    [str(v[0]) for v in dmg_frames.values()] + ["--out", str(derived)], out / "derive-manifest.json")
    summary["derive"] = {"exit": rc, "entries": len((dm or {}).get("entries", []))}
    from PIL import Image
    ents = {Path(e["input"]).as_posix(): e for e in (dm or {}).get("entries", [])}
    rows_ = [L.rel(frames["K1_joiner"][0]), L.rel(frames["K3"][0])]
    sheet = Image.new("RGB", (640 * 3, 360 * len(rows_)), (0, 0, 0))
    for ri, rp in enumerate(rows_):
        e = ents.get(rp)
        srcs = [REPO / rp] + ([Path(e["gray"]["path"]), Path(e["deuteranopia"]["path"])] if e else [])
        for ci, sp in enumerate(srcs):
            with Image.open(sp) as im:
                sheet.paste(im.convert("RGB").resize((640, 360), Image.LANCZOS), (640 * ci, 360 * ri))
    sheet.save(out / "contact-k1-k3-color-gray-deuteranopia.jpg", quality=85)
    # ---- render fingerprints (qa010 render)
    summary["render"] = {}
    for tag, (png, tr, _r) in {**frames, **dmg_frames}.items():
        rc, doc = run_qa(["render", "--trace", str(tr), "--frame", str(png)], out / f"render-{tag}.json")
        summary["render"][tag] = {"exit": rc, "reference": (doc or {}).get("reference")}
    # ---- rings rev 2 (+ rev 1 for T5.2 continuity)
    rings = {}
    for tag in ("K1_host", "K1_joiner", "K3"):
        rings[tag] = rings_rev2(shots[tag], th, calib, cells)
        for r in rings[tag]["fighters"]:
            if "look" in r:
                r["shapeVariants"] = shape_in_variants(shots[tag], r["fighter"], r["look"], calib,
                                                       th["calibration"]["pixelDeltaE"])
                r["shapePassAllVariants"] = r["shapePass"] and all(v == r["expectedShape"]
                                                                   for v in r["shapeVariants"].values())
    rev1 = {tag: T52.ring_metrics(shots[tag].png, shots[tag].trace_path, frames[tag][2])
            for tag in ("K1_host", "K1_joiner", "K3")}
    # view independence + absolute colour (K1 host vs joiner, same fighter same cell)
    vi = []
    h_by = {r["fighter"]: r for r in rings["K1_host"]["fighters"] if "fraction" in r}
    for r in rings["K1_joiner"]["fighters"]:
        o = h_by.get(r["fighter"])
        if not o or "fraction" not in r or o["cell"] != r["cell"]:
            continue
        de = (float(np.linalg.norm(np.array(o["fillMedianLab"]) - np.array(r["fillMedianLab"])))
              if o.get("fillMedianLab") and r.get("fillMedianLab") else None)
        vi.append({"fighter": r["fighter"], "name": r["name"], "cell": r["cell"], "host": o["fraction"],
                   "joiner": r["fraction"], "absDelta": round(abs(o["fraction"] - r["fraction"]), 4),
                   "pass": abs(o["fraction"] - r["fraction"]) <= th["rings"]["viewIndependence"]["maxAbsDelta"],
                   "fillDeltaE76HostJoiner": round(de, 2) if de is not None else None,
                   "sameColourPass": de is not None and de <= th["teams"]["absoluteSameColour"]["maxDeltaE76"]})
    # team separation per frame
    teams = {}
    for tag, rr in rings.items():
        p1 = [r for r in rr["fighters"] if r.get("look") == "P1" and r.get("fillMedianGrayY") is not None]
        p2 = [r for r in rr["fighters"] if r.get("look") == "P2" and r.get("fillMedianGrayY") is not None]
        if not p1 or not p2:
            continue
        s = shots[tag]
        m1 = np.zeros((s.h, s.w), bool)
        m2 = np.zeros((s.h, s.w), bool)
        # medians over all team pixels of each look on this frame
        y1 = float(np.median([r["fillMedianGrayY"] for r in p1]))
        y2 = float(np.median([r["fillMedianGrayY"] for r in p2]))
        lab1 = np.median(np.array([r["fillMedianLab"] for r in p1]), axis=0)
        lab2 = np.median(np.array([r["fillMedianLab"] for r in p2]), axis=0)
        from qa010lib import color as C
        rgb1 = np.array([[np.median(np.array([r["fillMedianRgb"] for r in p1]), axis=0)]], dtype=np.uint8)
        rgb2 = np.array([[np.median(np.array([r["fillMedianRgb"] for r in p2]), axis=0)]], dtype=np.uint8)
        d1 = C.linear_to_lab(C.u8_to_linear(C.deuteranopia(rgb1)))[0, 0]
        d2 = C.linear_to_lab(C.u8_to_linear(C.deuteranopia(rgb2)))[0, 0]
        del m1, m2
        teams[tag] = {"grayY": [round(y1, 1), round(y2, 1)], "absDeltaY": round(abs(y1 - y2), 1),
                      "colorDeltaE76": round(float(np.linalg.norm(lab1 - lab2)), 2),
                      "deutDeltaE76": round(float(np.linalg.norm(d1 - d2)), 2)}
        teams[tag]["pass"] = (teams[tag]["absDeltaY"] >= th["teams"]["grayDeltaY"]["min"] and
                              teams[tag]["colorDeltaE76"] >= th["teams"]["colorDeltaE76"]["min"] and
                              teams[tag]["deutDeltaE76"] >= th["teams"]["deutDeltaE76"]["min"])
    chips = {tag: chip_vs_ring(shots[tag], rings[tag], calib) for tag in rings}
    L.write_json(out / "team-rings-r2.json", {"schema": "unmatched.t53-team-rings/2", "status": "измерено",
                                              "method": th["rings"]["method"], "frames": rings,
                                              "viewIndependence": vi, "teams": teams, "chips": chips})
    L.write_json(out / "team-rings-rev1.json", {"schema": "unmatched.t52-team-rings/1",
                                                "status": "rev 1 (T5.2) для сопоставления, не гейт",
                                                "method": T52.RING_METHOD, "frames": rev1})
    ring_rows = [r for tag in rings for r in rings[tag]["fighters"] if "fraction" in r]
    summary["rings"] = {
        "fighters": len(ring_rows),
        "fractionFail": [f"{r['name']} {tag} {r['fraction']}" for tag in rings for r in rings[tag]["fighters"]
                         if "fraction" in r and not r["fractionPass"]],
        "shapeFail": [f"{r['name']} {tag} {r['shape']['shape']}/{r['expectedShape']} "
                      f"(breaks {r['shape']['breaks']}, kinks {r['shape']['kinks']})"
                      for tag in rings for r in rings[tag]["fighters"] if "fraction" in r and not r["shapePass"]],
        "shapeVariantFail": [f"{r['name']} {tag} {r.get('shapeVariants')}" for tag in rings for r in rings[tag]["fighters"]
                             if "fraction" in r and r["shapePass"] and not r.get("shapePassAllVariants")],
        "keylineVsTileFail": [f"{r['name']} {tag}" for tag in rings for r in rings[tag]["fighters"]
                              if "fraction" in r and not r["keylineVsTilePass"]],
        "keylineVsTileThinReference": [f"{r['name']} {tag} tilePx={r['tilePx']}" for tag in rings
                                       for r in rings[tag]["fighters"] if "fraction" in r and r["tilePx"] < 50],
        "keylineVsTileDiagRange": diag_range(rings),
        "fillVsKeylineFail": [f"{r['name']} {tag}" for tag in rings for r in rings[tag]["fighters"]
                              if "fraction" in r and not r["fillVsKeylinePass"]],
        "fractionRange": [min(r["fraction"] for r in ring_rows), max(r["fraction"] for r in ring_rows)] if ring_rows else None,
        "viewIndependenceFail": [v for v in vi if not v["pass"]], "sameColourFail": [v for v in vi if not v["sameColourPass"]],
        "teams": teams,
        "chipFail": [c for tag in chips for c in chips[tag] if not (c.get("colourPass") and c.get("shapePass"))],
        "chips": sum(len(v) for v in chips.values()),
        "rev1": {tag: [{"name": r["name"], "fraction": r["fraction"], "visible": r["visible"]} for r in v["fighters"]]
                 for tag, v in rev1.items()}}
    # ---- zones rev 2 (K1 joiner main; host / K3 recorded)
    zones = {tag: zones_rev2(shots[tag], cells, th, calib) for tag in ("K1_joiner", "K1_host", "K3")}
    L.write_json(out / "zone-contrast-r2.json", {"schema": "unmatched.t53-zones/2", "status": "измерено",
                                                 "method": th["zones"]["method"], "frames": zones,
                                                 "pairsByShape": zone_pairs_by_shape(cells, styles)})
    zj = zones["K1_joiner"]
    summary["zones"] = {z: {"slots": v["slots"], "pass": v["pass"], **{vn: v["variants"][vn] for vn in v["variants"]}}
                        for z, v in zj["zones"].items()}
    summary["multizone"] = {tag: {"cells": zones[tag]["multizone"]["cells"], "pass": zones[tag]["multizone"]["pass"],
                                  "failing": [m for m in zones[tag]["multizone"]["list"] if not m["pass"]]}
                            for tag in zones}
    summary["zonePairs"] = zone_pairs_by_shape(cells, styles)
    # rev 1 zone metrics (T5.2 method, T5.2 thresholds) for the before/after table
    th52 = load_json(T52_EVIDENCE / "t52-thresholds.json")
    fr52 = T52.Frame(shots["K1_joiner"].png, shots["K1_joiner"].trace_path)
    z52 = T52.zone_metrics(fr52, cells, styles, th52)
    L.write_json(out / "zone-contrast-rev1.json", {"schema": "unmatched.t52-zone-contrast/1",
                                                   "status": "rev 1 (метод T5.2) для сопоставления", **z52})
    summary["zonesRev1"] = {k: {vn: v["variants"][vn].get("wcag") for vn in ("color", "gray", "deuteranopia")}
                            for k, v in z52["zones"].items()}
    # ---- tags / damage rev 2
    td = {tag: tags_damage(shots[tag], th, {**frames, **dmg_frames}[tag][2]) for tag in list(frames) + list(dmg_frames)}
    L.write_json(out / "tags-damage-r2.json", {"schema": "unmatched.t53-tags-damage/2", "status": "измерено",
                                               "method": {"tags": th["tags"], "damage": th["damage"]}, "frames": td})
    tag_rows = [(tag, r) for tag in td for r in td[tag]["tags"]]
    # t53 revision 1: tag binding + plate-owner mode over EVERY late SHOT section of every published frame of the board
    rev1 = threshold_revision(th, 1)
    if rev1 is not None:
        runs = [k1, k3] + [Path(r).resolve() for r in (a.probe24_run, a.probe48_run) if r]
        traces = sorted({p for run in runs for p in run.glob("*client-*.trace.log")})
        scan = tag_binding_scan(traces)
        L.write_json(out / "tag-binding.json", {"schema": "unmatched.t53-tag-binding/1", "status": "измерено",
                                                "thresholdsRevision": 1, "rule": rev1["tags"]["binding"],
                                                "modeRule": rev1["tags"]["mode"],
                                                "traces": [L.rel(t) for t in traces], **scan})
        summary["tagBinding"] = {k: scan[k] for k in ("sections", "paintedTags", "bindingFail", "plateOwnerModeFail",
                                                      "pass", "placements", "gapToOwnerMax")}
        summary["tagBinding"]["traces"] = len(traces)
    summary["tags"] = {"tags": len([1 for _, r in tag_rows if r.get("painted")]),
                       "fail": [f"{r['name']} {tag}: text={r.get('textPass')} integrity={r.get('backgroundIntegrity')} "
                                f"overlap={r.get('overlaps')} mode={r.get('mode')}/{r.get('expectedMode')} "
                                f"binding={r.get('bindingPass')}"
                                for tag, r in tag_rows if not r.get("pass")],
                       "minText": min([min(v[vn] for vn in ("color", "gray", "deuteranopia") if v[vn] is not None)
                                       for _, r in tag_rows for v in (r.get("lines") or {}).values()
                                       if any(v[vn] is not None for vn in ("color", "gray", "deuteranopia"))] or [None]),
                       "overlapFigures": {f"{r['name']} {tag}": r.get("overlapOtherFigures") for tag, r in tag_rows
                                          if r.get("overlapOtherFigures")}}
    dmg_rows = [(tag, d) for tag in td for d in td[tag]["damage"]]
    summary["damage"] = [{"frame": tag, **{k: d[k] for k in ("name", "amount", "seq", "contrast", "overlaps",
                                                             "bindingPass", "overlapPass", "textPass", "placement")}}
                         for tag, d in dmg_rows]
    # ---- icon rev 3: K3 (32) + probes (24 / 48)
    icon = {}
    for tag, sh in [("K3", shots["K3"])] + [(f"probe{k}", shots[f"probe{k}"]) for k in probes]:
        ib = icon_binding(sh)
        entry = {"frame": L.rel(sh.png), "binding": ib}
        if ib["present"]:
            n = int(round(ib["bbox"][2] - ib["bbox"][0]))
            rc, doc = run_qa(["icon", str(sh.png), "--trace", str(sh.trace_path), "--shot", sh.png.name,
                              "--mask-texture", str(TOKEN_DIR / f"ui-action-attack-token-{n}-glyphmask.png"),
                              "--token-texture", str(TOKEN_DIR / f"ui-action-attack-token-{n}.png")],
                             out / f"icon-{tag}.json")
            entry.update(size=n, exit=rc, result=(doc or {}).get("result"), variants=(doc or {}).get("variants"),
                         guard=(doc or {}).get("guard"), status=(doc or {}).get("status"))
        icon[tag] = entry
    L.write_json(out / "icon-r3.json", {"schema": "unmatched.t53-icon/3", "status": "измерено",
                                        "method": th["icon"]["method"], "frames": icon})
    summary["icon"] = {tag: {k: v.get(k) for k in ("size", "result", "status")} |
                       {"glyphVsBody": {vn: (v.get("variants") or {}).get(vn, {}).get("glyph_vs_body")
                                        for vn in ("color", "gray", "deuteranopia")},
                        "edge": {vn: (v.get("variants") or {}).get(vn, {}).get("edge") for vn in ("color", "gray", "deuteranopia")},
                        "guard": v.get("guard"), "anchor": v["binding"].get("anchor"),
                        "bindingPass": v["binding"].get("bindingPass"), "overlapPass": v["binding"].get("overlapPass"),
                        "present": v["binding"]["present"]}
                       for tag, v in icon.items()}
    # stale-icon check across every published K3 frame: a late icon line must mean an icon in the pixels
    stale = []
    for side, tp in (("joiner", k3_join_t), ("host", k3_host_t)):
        for png in sorted((k3 / side).glob("*.png")):
            try:
                sh = Shot(png, tp)
            except Exception as exc:  # noqa: BLE001
                stale.append({"frame": L.rel(png), "error": str(exc)[:200]})
                continue
            ib = icon_binding(sh)
            if not ib["present"]:
                stale.append({"frame": L.rel(png), "icon": "none (late: hidden)" if sh.block.icon_hidden_late else "none"})
                continue
            n = int(round(ib["bbox"][2] - ib["bbox"][0]))
            rc, doc = run_qa(["icon", str(png), "--trace", str(tp), "--shot", png.name,
                              "--mask-texture", str(TOKEN_DIR / f"ui-action-attack-token-{n}-glyphmask.png"),
                              "--token-texture", str(TOKEN_DIR / f"ui-action-attack-token-{n}.png")],
                             out / "icon-presence" / f"{side}-{png.stem}.json")
            stale.append({"frame": L.rel(png), "icon": "traced", "guard": (doc or {}).get("guard")})
    summary["iconPresence"] = {"frames": len(stale),
                               "traced": sum(1 for s in stale if s.get("icon") == "traced"),
                               "tracedButAbsent": [s["frame"] for s in stale if s.get("icon") == "traced"
                                                   and not ((s.get("guard") or {}).get("present"))]}
    L.write_json(out / "icon-presence.json", {"schema": "unmatched.t53-icon-presence/1", "frames": stale,
                                              "rule": th["icon"]["guard"]["rule"]})
    # ---- K3 panel rule (D-10) and the plate vs other figures (K1 host)
    panels = k3_panels(shots["K3"], th)
    L.write_json(out / "k3-panels.json", {"schema": "unmatched.t53-k3-panels/1", "rule": th["k3Panels"]["rule"], **panels})
    summary["k3Panels"] = {k: panels[k] for k in ("pass", "gatedOverlaps", "otherCellOverlapPx2", "attacker", "target")}
    pv = plate_vs_figures(shots["K1_host"])
    summary["plateVsFigures"] = pv
    rc, pdoc = run_qa(["plate", "--trace", str(frames["K1_host"][1]), "--shot", frames["K1_host"][0].name,
                       "--frame", str(frames["K1_host"][0])], out / "plate-k1-host.json")
    summary["plateVsReachable"] = {"exit": rc, "result": (pdoc or {}).get("result"),
                                   "cells": ((pdoc or {}).get("checked_cells") or {}).get("count"),
                                   "violations": len((pdoc or {}).get("violations") or [])}
    # ---- luma sections + C-9 proxy (continuity with T5.2; no thresholds)
    light = prof_doc["lightProfiles"][T52.board_profile(spec["boardId"])["light"]]
    sections = T52.light_sections(T52.board_profile(spec["boardId"]), light, cells)
    L.write_json(out / "luma-sections.json", {"schema": "unmatched.t52-luma-sections/1", "status": "измерено (порога нет)",
                                              "frames": {"K1_joiner": T52.luma_sections(fr52, cells, sections)}})
    passable = ";".join(f"{c['x']},{c['y']}" for c in cells if not c["obstacle"])
    summary["c9"] = {}
    for tag in ("K1_host", "K1_joiner", "K3"):
        png, tr, _r = frames[tag]
        for gname, gspec in (("all", "board=trace-cells:all"), ("passable", f"passable=trace-cells:{passable}")):
            args = ["c9", str(png), "--trace", str(tr), "--game", gspec, "--decor", "tray_proxy=trace-ring:0.05,0.35"]
            for ex in T52.HUD_EXCLUDE:
                args += ["--exclude", ex]
            rc, doc = run_qa(args, out / f"c9-{tag}-{gname}.json")
            d = doc or {}
            summary["c9"][f"{tag}/{gname}"] = {"exit": rc, "status": d.get("status"),
                                               "dEV": (d.get("delta_ev") or {}).get("used"),
                                               "resultOnProxy": d.get("result_on_proxy")}
    # ---- the medusa MI identity lines of this board (team slot)
    mis = sorted({m.group(0) for s in shots.values() for m in re.finditer(
        r"ARTPREVIEW medusa materials fighter=\S+ team=\w+ mesh=\S+ slots=\d+ mi=(\S+) .*?miSha256=([0-9a-f]{64})"
        r" teamSlot=(P[12]) look=(P[12])", s.text)})
    summary["medusaMi"] = mis
    # ---- luma (frame level) + projection of K1 host + the QA-010 checklist (K1 + K3; K2 is T5.1)
    run_qa(["luma", str(frames["K1_host"][0]), str(frames["K3"][0])], out / "luma-frames.json")
    run_qa(["project", "--trace", str(frames["K1_host"][1]), "--shot", frames["K1_host"][0].name,
            "--frame", str(frames["K1_host"][0])], out / "project-k1-host.json")
    summary["checklist"] = write_checklist(out, key, spec, frames, summary, th)
    L.write_json(out / "summary.json", summary)
    print(json.dumps({"board": key, "classifyExit": summary["classify"]["exit"], "rings": {
        k: summary["rings"][k] for k in ("fractionFail", "shapeFail", "keylineVsTileFail", "fractionRange")},
        "multizone": summary["multizone"]["K1_joiner"], "tagsFail": len(summary["tags"]["fail"]),
        "icon": {k: (v["result"], v["glyphVsBody"]["color"]) for k, v in summary["icon"].items()},
        "k3Panels": summary["k3Panels"]["pass"]}, ensure_ascii=False, default=str)[:3000])
    return 0


# ------------------------------------------------------------------ QA-010 checklist (qa010 checklist)
def _vr(d: dict | None) -> str:
    if not d:
        return "нет данных"
    return " / ".join(f"{d.get(vn)}" for vn in ("color", "gray", "deuteranopia"))


def write_checklist(out: Path, key: str, spec: dict, frames: dict, sm: dict, th: dict) -> dict:
    prov = ("packaged-live strict + render-reference + SHOT captured (tools/art/classify_evidence.py --strict "
            "--render-reference --require-captured)")
    rings, zones, tags, icon = sm["rings"], sm["zones"], sm["tags"], sm["icon"]
    mz = sm["multizone"]["K1_joiner"]
    teams = rings.get("teams", {})
    manual = {
        "K1.cells_all": {"note": "клетки целиком в кадре — project-k1-host.json; различимость — глазами (агент)"},
        "K1.multizone": {"note": (f"t53 zones rev 2 (кромка + заливка слота каждой зоны, K1 присоединившегося): "
                                  f"{mz['pass']}/{mz['cells']} мультизонных клеток — все зоны проходят кромка/плитка и "
                                  f"заливка/кромка ≥ 3 : 1 в цвете, сером и deuteranopia"
                                  + (f"; не проходят: {mz['failing']}" if mz['failing'] else ""))
                         if mz["cells"] else "мультизонных клеток на доске нет"},
        "K1.hero_helper": {"note": (f"экранные теги (UMG, подложка tag.background): {tags['tags']} тегов на кадрах, "
                                    f"мин. контраст текста {tags['minText']} : 1, провалов {len(tags['fail'])} "
                                    "(tags-damage-r2.json); фигуры: Medusa-кандидат + серые блок-ауты"
                                    + (f"; привязка тега к владельцу (t53 revision 1, все поздние секции SHOT): "
                                       f"{sm['tagBinding']['paintedTags'] - len(sm['tagBinding']['bindingFail'])}/"
                                       f"{sm['tagBinding']['paintedTags']} тегов, режим владельца плашки — "
                                       f"{'pass' if not sm['tagBinding']['plateOwnerModeFail'] else 'FAIL'} "
                                       "(tag-binding.json)" if sm.get("tagBinding") else ""))},
        "K1.teams_gray": {"note": ("кольца команды rev 2 (team-rings-r2.json): доля заливки "
                                   f"{rings['fractionRange']}, ниже порога {len(rings['fractionFail'])}; форма "
                                   f"(круг P1 / шестигранник P2) не распознана у {len(rings['shapeFail'])}; кромка/плитка "
                                   f"< 3 : 1 у {len(rings['keylineVsTileFail'])} (эталон плитки < 50 px у "
                                   f"{len(rings.get('keylineVsTileThinReference') or [])}: светлая плитка ≈ цвет зоны "
                                   f"light-gray исключается методом; диагностика после съёмки, не гейт: "
                                   f"{rings.get('keylineVsTileDiagRange')}); команды в сером |ΔY′| "
                                   + ", ".join(f"{k} {v['absDeltaY']}" for k, v in teams.items()))},
        "K1.selected": {"note": (f"плашка vs фигуры: {sm['plateVsFigures'].get('pass')} (перекрытий 0 px²), привязка к "
                                 f"владельцу (не гейт): {(sm['plateVsFigures'].get('binding') or {}).get('bound')}; "
                                 f"плашка vs достижимые: {sm['plateVsReachable']['result']}")},
        "K1.zones_deut": {"note": "t53 zones rev 2 по зонам (цвет / серый / deuteranopia, кромка/плитка): " + "; ".join(
            f"{z}: {_vr({vn: v[vn]['keylineVsTile'] for vn in ('color', 'gray', 'deuteranopia')})}"
            for z, v in zones.items()) + "; буквы зон — отложено"},
        "K3.attack_result": {"note": ("рамка/дуги цели и итог — кольцо атакующего, дуги цели, панель HUD; иконка — строка "
                                      f"K3.icon_sizes; HUD-панели K3 (D-10) против клеток атакующего/цели/достижимых: "
                                      f"{'pass' if sm['k3Panels']['pass'] else 'FAIL'}; числа урона: "
                                      + "; ".join(f"{d['frame']} {d['name']} текст {_vr(d['contrast'])} привязка "
                                                  f"{d['bindingPass']}" for d in sm["damage"]))},
        "K3.icon_sizes": {"note": "иконка rev 3 (жетон): " + "; ".join(
            f"{k} {v.get('size')} px: глиф/тело {_vr(v['glyphVsBody'])}, край {_vr(v['edge'])}, guard "
            f"{(v.get('guard') or {}).get('present')}" for k, v in icon.items())},
    }
    results = [{"k": "K1..K3", "path": "derive-manifest.json"}, {"k": "K1..K3", "path": "luma-frames.json"},
               {"k": "K1", "path": "c9-K1_host-all.json"}, {"k": "K3", "path": "icon-K3.json"},
               {"k": "K1", "path": "project-k1-host.json"}, {"k": "K1", "path": "plate-k1-host.json"},
               {"k": "K1", "path": "render-K1_host.json"}, {"k": "K3", "path": "render-K3.json"}]
    cfg = {"title": f"QA-010 чек-лист W5b-R — {key}: K1 + K3 (K2 — задача T5.1). Не приёмка",
           "run": {"задача": "W5b-R «Исправление читаемости доски»", "доска": f"{key} boardId={spec['boardId']}",
                   "K1_хост": L.rel(frames["K1_host"][0]), "K1_присоединившийся": L.rel(frames["K1_joiner"][0]),
                   "K3": L.rel(frames["K3"][0]), "пороги": "t53-thresholds.json (зарегистрированы до съёмки)"},
           "frames": {"K1": {"path": L.rel(frames["K1_host"][0]), "provenance": prov},
                      "K3": {"path": L.rel(frames["K3"][0]), "provenance": prov}},
           "results": [r for r in results if (out / r["path"]).is_file()],
           "manual": manual,
           "viewer": {"kind": "agent", "note": "самоприёмка агента W5b-R, требует взгляда пользователя"},
           "elements": [
               {"frame": "K1", "id": "facade", "status": "отложено", "reason": "фасадов в сцене нет"},
               {"frame": "K1", "id": "lantern", "status": "отложено", "reason": "фонаря в сцене нет"},
               {"frame": "K1", "id": "tray_darkness", "status": "есть", "reason": "рама и тёмный фон профиля доски"},
               {"frame": "K1", "id": "fog", "status": "отложено", "reason": "туман не задан"},
               {"frame": "K1", "id": "vignette", "status": "отложено", "reason": "виньетка не задана"},
               {"frame": "K1", "id": "zone_pictograms", "status": "отложено", "reason": "буквы/пиктограммы зон — отдельная волна (D-9)"},
               {"frame": "K1", "id": "hud", "status": "есть", "reason": "UMG-гибрид + экранные теги W5b-R"},
               {"frame": "K1", "id": "shadow_casters_1", "status": "есть", "reason": "RENDER shadowCasters=1"},
               {"frame": "K1", "id": "six_fighters", "status": "есть", "reason": "Medusa v2 + блок-ауты, кольца команды"},
               {"frame": "K2", "id": "facade_hidden", "status": "отложено", "reason": "K2 — T5.1"},
               {"frame": "K2", "id": "plate", "status": "отложено", "reason": "K2 — T5.1; плашка измерена на K1 хоста"},
               {"frame": "K2", "id": "base_profile", "status": "отложено", "reason": "K2 — T5.1"},
               {"frame": "K3", "id": "poses", "status": "отложено", "reason": "клипы боя не подключены"},
               {"frame": "K3", "id": "inspector_2d", "status": "отложено", "reason": "инспектор 2D не реализован (D-09)"},
               {"frame": "K3", "id": "target_frame_icon", "status": "есть", "reason": "дуги цели + жетон атаки (icon rev 3)"},
               {"frame": "K3", "id": "damage_result", "status": "есть",
                "reason": "экранное число урона (UMG-капсула) + панель итога"}]}
    L.write_json(out / "checklist-config.json", cfg)
    ck = subprocess.run([sys.executable, str(QA010), "checklist", "--config", L.rel(out / "checklist-config.json"),
                         "--out-md", L.rel(out / "qa010-checklist.md"), "--out-json", L.rel(out / "qa010-checklist.json")],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO),
                        creationflags=L.NO_WINDOW)
    counts = (json.loads((out / "qa010-checklist.json").read_text(encoding="utf-8")).get("status_counts")
              if (out / "qa010-checklist.json").is_file() else None)
    return {"exit": ck.returncode, "md": L.rel(out / "qa010-checklist.md"), "statusCounts": counts,
            "stderr": ck.stderr[-400:] if ck.returncode not in (0, 1) else None}


# ------------------------------------------------------------------ sheets + before/after table
def _crop(img, box, pad, scale):
    from PIL import Image
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    c = img.crop((max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad)))
    return c.resize((c.width * scale, c.height * scale), Image.NEAREST)


def _trace_for(png: Path) -> Path | None:
    """The client trace of a published frame: K1 (same dir, phase2-client-<side>) or K3 (<run>/<side>/x.png ->
    <run>/combat-client-<side>)."""
    side = "host" if ("-host-" in png.name or png.parent.name == "host") else "joiner"
    for d in (png.parent, png.parent.parent):
        c = sorted(d.glob(f"*client-{side}.trace.log"))
        if c:
            return c[0]
    return None


def _context_tiles(png: Path, trace: Path, label: str) -> list:
    """t53 revision 1 sheet row: each painted tag with its owner's figure and the neighbours, 1:1 pixels."""
    from PIL import Image, ImageDraw
    from qa010lib.trace import parse_trace
    blk = parse_trace(trace).find_shot(None, png.name)
    doc = block_tag_binding(blk, Path(trace).read_text(encoding="utf-8", errors="replace"))
    figs = {fid: tuple(v["bbox"]) for fid, v in blk.figures.items()}
    tiles = []
    with Image.open(png) as im0:
        im = im0.convert("RGB")
        for r in doc["tags"]:
            if not r.get("painted"):
                continue
            box, own = r["bbox"], figs[r["fighter"]]
            u = (min(box[0], own[0]), min(box[1], own[1]), max(box[2], own[2]), max(box[3], own[3]))
            pad = 36
            extra = max(0, 340 - (int(u[2]) - int(u[0]) + 2 * pad)) // 2  # room for the label line
            x0, y0 = max(0, int(u[0]) - pad - extra), max(0, int(u[1]) - pad)
            x1, y1 = min(im.width, int(u[2]) + pad + extra), min(im.height, int(u[3]) + pad + 14)
            t = im.crop((x0, y0, x1, y1))
            d = ImageDraw.Draw(t)

            def sh(rc, grow=0):
                return (rc[0] - x0 - grow, rc[1] - y0 - grow, rc[2] - x0 + grow - 1, rc[3] - y0 + grow - 1)
            for k, rc in figs.items():
                if k != r["fighter"] and inter_area(rc, (x0, y0, x1, y1)) > 0:
                    d.rectangle(sh(rc), outline=(150, 150, 150))
            d.rectangle(sh(own), outline=(0, 230, 0))
            d.rectangle(sh(box, 1), outline=(255, 230, 0))
            other = FIGHTER_NAMES.get(r["nearestOther"], r["nearestOther"]) or "-"
            d.rectangle((0, t.height - 13, t.width, t.height), fill=(0, 0, 0))
            d.text((2, t.height - 12), f"{label} {r['name']} gap {r['gapToOwner']:.0f} c>own {r['centreToOwner']:.0f} "
                                       f"c>{other} {r['centreToNearestOther']:.0f} {'OK' if r['bindingPass'] else 'FAIL'}",
                   fill=(255, 255, 0) if r["bindingPass"] else (255, 80, 80))
            tiles.append(t)
    return tiles


def cmd_sheets(a) -> int:
    from PIL import Image, ImageDraw
    evidence = Path(a.evidence).resolve()
    made = []
    for key in BOARDS:
        sp = evidence / "analysis" / key / "summary.json"
        if not sp.is_file():
            continue
        sm = load_json(sp)
        fr = {k: REPO / v for k, v in sm["frames"].items()}
        rows = []
        # row 1: rings of every fighter on K1 joiner (fighter base +- 70 px)
        rr = load_json(evidence / "analysis" / key / "team-rings-r2.json")["frames"]["K1_joiner"]["fighters"]
        sh = Shot(fr["K1_joiner"], Path(str(fr["K1_joiner"]).replace("phase2-board-joiner-1920x1080.png",
                                                                     "phase2-client-joiner.trace.log")))
        with Image.open(fr["K1_joiner"]) as im:
            im = im.convert("RGB")
            tiles = []
            for r in rr:
                f = sh.fighters.get(r["fighter"])
                p = sh.proj.camera.project(f.world) if f else None
                if not p:
                    continue
                t = _crop(im, (p[0] - 60, p[1] - 70, p[0] + 60, p[1] + 25), 0, 2)
                ImageDraw.Draw(t).text((4, 4), f"{r['name']} {r.get('look', '')} {r.get('fraction', '')} "
                                                f"{(r.get('shape') or {}).get('shape', '')}", fill=(255, 255, 0))
                tiles.append(t)
            rows.append(tiles)
            # row 2: tags on K1 joiner (x2, legibility)
            tiles = []
            for w in sh.block.widgets:
                if w.get("id") == "board.tag" and w.get("geom") == "painted":
                    tiles.append(_crop(im, w["bbox"], 6, 2))
            rows.append(tiles)
        # rows 3-5 (t53 revision 1): every painted tag IN CONTEXT - the tag (yellow), its owner's FigureScreenRect
        # (green) and the other figures (grey) on K1 joiner, K1 host and the K3 frame; the label gives the gap to the
        # owner and the centre distances (owner vs the nearest other figure)
        for tag_name in ("K1_joiner", "K1_host", "K3"):
            png = fr.get(tag_name)
            trace = _trace_for(png) if png is not None and png.is_file() else None
            if trace is not None:
                rows.append(_context_tiles(png, trace, tag_name))
        # row 3: icon crops (K3 32, probe 24, probe 48) at x3
        tiles = []
        for tag in ("K3", "probe24", "probe48"):
            ij = evidence / "analysis" / key / f"icon-{tag}.json"
            if not ij.is_file():
                continue
            d = load_json(ij)
            src = REPO / d["frame"]["path"] if "path" in (d.get("frame") or {}) else None
            if src is None or not src.is_file():
                src = fr.get("K3") if tag == "K3" else REPO / sm["probes"].get(tag.replace("probe", ""), "")
            with Image.open(src) as im:
                t = _crop(im.convert("RGB"), d["bbox"], 16, 3)
            ImageDraw.Draw(t).text((3, 3), f"{tag} {d.get('size_px')}px {d.get('result')}", fill=(255, 255, 0))
            tiles.append(t)
        rows.append(tiles)
        # row 4: damage numbers
        td = load_json(evidence / "analysis" / key / "tags-damage-r2.json")["frames"]
        tiles = []
        for tag, doc in td.items():
            for d in doc["damage"]:
                with Image.open(REPO / doc["frame"]) as im:
                    t = _crop(im.convert("RGB"), d["bbox"], 90, 2)
                ImageDraw.Draw(t).text((3, 3), f"{tag} {d['name']} -{d['amount']}", fill=(255, 255, 0))
                tiles.append(t)
        rows.append(tiles)
        W = max(sum(t.width for t in r) + 8 * len(r) for r in rows if r)
        H = sum(max((t.height for t in r), default=0) + 8 for r in rows)
        sheet = Image.new("RGB", (W, H), (40, 40, 40))
        y = 0
        for r in rows:
            x = 0
            for t in r:
                sheet.paste(t, (x, y))
                x += t.width + 8
            y += max((t.height for t in r), default=0) + 8
        outp = evidence / "analysis" / key / "readability-sheet.jpg"
        sheet.save(outp, quality=88)
        made.append(L.rel(outp))
    # before / after: T5.2 vs W5b-R, K1 joiner and K3 (downscaled 960x540)
    for kind, t52k in (("K1_joiner", "K1_joiner"), ("K3", "K3")):
        tiles = []
        for key in BOARDS:
            a_ = T52_EVIDENCE / "analysis" / key / "summary.json"
            b_ = evidence / "analysis" / key / "summary.json"
            if not (a_.is_file() and b_.is_file()):
                continue
            before = REPO / load_json(a_)["frames"][t52k]
            after = REPO / load_json(b_)["frames"][kind]
            pair = []
            for p_, label in ((before, "T5.2"), (after, "W5b-R")):
                with Image.open(p_) as im:
                    t = im.convert("RGB").resize((960, 540), Image.LANCZOS)
                ImageDraw.Draw(t).text((8, 520), f"{key} {kind} {label}", fill=(255, 255, 0))
                pair.append(t)
            tiles.append(pair)
        if tiles:
            sheet = Image.new("RGB", (1928, 548 * len(tiles)), (0, 0, 0))
            for i, (b1, b2) in enumerate(tiles):
                sheet.paste(b1, (0, 548 * i))
                sheet.paste(b2, (968, 548 * i))
            outp = evidence / "analysis" / f"before-after-{kind.lower()}.jpg"
            sheet.save(outp, quality=85)
            made.append(L.rel(outp))
    print(json.dumps(made, ensure_ascii=False, indent=1))
    return 0


def _rng(vals):
    vals = [v for v in vals if v is not None]
    return f"{min(vals):.2f}–{max(vals):.2f}".replace(".", ",") if vals else "—"


def cmd_table(a) -> int:
    evidence = Path(a.evidence).resolve()
    t52 = Path(a.t52).resolve() if a.t52 else T52_EVIDENCE
    rows = []
    doc = {"schema": "unmatched.t53-before-after/1", "status": "измерено (не приёмка)", "before": L.rel(t52),
           "after": L.rel(evidence), "boards": {}}
    for key in BOARDS:
        a_, b_ = t52 / "analysis" / key / "summary.json", evidence / "analysis" / key / "summary.json"
        if not (a_.is_file() and b_.is_file()):
            continue
        A, B = load_json(a_), load_json(b_)
        ra = [r["fraction"] for rows_ in A["rings"].values() for r in rows_]
        bad_a = sum(1 for rows_ in A["rings"].values() for r in rows_ if not r["visible"])
        rb1 = [r["fraction"] for rows_ in B["rings"]["rev1"].values() for r in rows_]
        zm = A["zoneMarks"]
        zb = B["zones"]
        ld = load_json(t52 / "analysis" / key / "labels-damage.json")["frames"]
        lab = [r.get("crWorst") for f_ in ld.values() for r in f_["items"] if r.get("kind") == "label"]
        dmg_items = [r for f_ in ld.values() for r in f_["items"] if r.get("kind") == "damage"]
        dmg_a = [r.get("crWorst") for r in dmg_items]
        dmg_share = [c.get("shareOfDamageBbox") for r in dmg_items for c in (r.get("collidesWithLabels") or [])]
        mza = A.get("multizone") or {}
        mzb = B["multizone"]["K1_joiner"]
        ic_a = {s_["size_px"]: s_["contrast_ratio"] for s_ in A["icon"]["sizes"]}
        ic_b = {v.get("size"): v["glyphVsBody"].get("color") for v in B["icon"].values() if v.get("size")}
        edge_b = {v.get("size"): v["edge"].get("color") for v in B["icon"].values() if v.get("size")}
        dm_b = B["damage"]
        teams = B["rings"]["teams"]
        entry = {
            "rings": {"before_rev1_fraction": _rng(ra), "before_invisible": bad_a,
                      "after_rev1_fraction_same_method": _rng(rb1),
                      "after_rev2_fraction": _rng(B["rings"]["fractionRange"] or []),
                      "after_rev2_below_threshold": len(B["rings"]["fractionFail"]),
                      "after_shape_unclassified": len(B["rings"]["shapeFail"]),
                      "after_keyline_vs_tile_fail": len(B["rings"]["keylineVsTileFail"]),
                      "after_keyline_vs_tile_thin_reference": len(B["rings"].get("keylineVsTileThinReference") or []),
                      "after_keyline_vs_tile_diag_range": B["rings"].get("keylineVsTileDiagRange"),
                      "after_fighters": B["rings"]["fighters"]},
            "teamsGray": {"before": "агент: не различаются (нет замера)",
                          "after_absDeltaY": {k: v["absDeltaY"] for k, v in teams.items()},
                          "after_pass": all(v["pass"] for v in teams.values())},
            "zones": {"before_mark_vs_tile": {z: _rng([v.get(vn) for vn in ("color", "gray", "deuteranopia")])
                                              for z, v in zm.items()},
                      "after_rev1_same_method": {z: _rng(list(v.values())) for z, v in B.get("zonesRev1", {}).items()},
                      "after_keyline_vs_tile": {z: _rng([v[vn]["keylineVsTile"] for vn in ("color", "gray", "deuteranopia")])
                                                for z, v in zb.items()},
                      "after_fill_vs_keyline": {z: _rng([v[vn]["fillVsKeyline"] for vn in ("color", "gray", "deuteranopia")])
                                                for z, v in zb.items()},
                      "after_slots_pass": {z: f"{v['pass']}/{v['slots']}" for z, v in zb.items()}},
            "multizone": {"before": (f"{mza.get('multizoneCells', 0) - len(mza.get('cellsWithUnreadableZone', []))}/"
                                     f"{mza.get('multizoneCells', 0)} читаемы") if mza.get("multizoneCells") else "нет",
                          "after": f"{mzb['pass']}/{mzb['cells']}" if mzb["cells"] else "нет"},
            "icon": {"before_rev2": ic_a, "after_rev3_glyph_vs_body": ic_b, "after_rev3_edge": edge_b},
            "labels": {"before_world_labels": _rng(lab), "after_tags_min_text": B["tags"]["minText"],
                       "after_tags_fail": len(B["tags"]["fail"]),
                       "after_tags_binding": (f"{B['tagBinding']['paintedTags'] - len(B['tagBinding']['bindingFail'])}/"
                                              f"{B['tagBinding']['paintedTags']}" if B.get("tagBinding") else None),
                       "after_plate_owner_mode_fail": (len(B["tagBinding"]["plateOwnerModeFail"])
                                                       if B.get("tagBinding") else None)},
            "damage": {"before": _rng(dmg_a) if dmg_a else "см. акт T5.2 §4.10",
                       "before_overlap_share_on_label": _rng(dmg_share) if dmg_share else "—",
                       "before_source": "урон способности (эррата W5b-R), кадр joiner/s09-damage-number.png",
                       "after": [{"frame": d["frame"], "name": d["name"], "text": d["contrast"].get("color"),
                                  "binding": d["bindingPass"], "overlapPass": d["overlapPass"]} for d in dm_b]},
            "plate": {"before_vs_reachable": A["plate"]["result"], "after_vs_reachable": B["plateVsReachable"]["result"],
                      "after_vs_figures": B["plateVsFigures"].get("pass"),
                      "after_bound": (B["plateVsFigures"].get("binding") or {}).get("bound")},
            "k3Panels": {"before": "не измерялось (строк SHOT panel нет)", "after": B["k3Panels"]["pass"]},
        }
        doc["boards"][key] = entry
        rows.append((key, entry))
    L.write_json(evidence / "analysis" / "qa010-before-after.json", doc)
    print(json.dumps(doc, ensure_ascii=False, indent=1)[:6000])
    return 0


# ------------------------------------------------------------------ live runs
def cmd_k1(a) -> int:
    evidence = Path(a.evidence).resolve()
    spec = BOARDS[a.board]
    sub = "k1" if not a.probe else f"k1-probe{a.probe}"
    ev = evidence / sub / a.board
    ev.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(HERE / "art004_live_k2.py"), "run", "--label", f"K1-{a.board}" + (f"-probe{a.probe}" if a.probe else ""),
           "--evidence-dir", str(ev), "--work", str(Path(a.work) / "k1"), "--board-id", spec["boardId"],
           "--variant", "face-neck-v2", "--shot-after", "36", "--run-seconds", "50", "--client-fps", "30",
           "--csv-frames", "1200", "--build-record", a.build_record, "--package-record", a.package_record,
           "--demo-arg=-RequireRenderReference", "--demo-arg=-RequireShotCaptured",
           "--perf-status", PERF_STATUS, "--concurrent-gpu-users", CONCURRENT]
    if a.probe:
        cmd += ["--demo-arg=-ArtPreviewIconProbe", "--demo-arg=-ArtPreviewIconSize", f"--demo-arg={a.probe}"]
    print(" ".join(cmd))
    r = subprocess.run(cmd, cwd=str(REPO), creationflags=L.NO_WINDOW)
    return r.returncode


def cmd_k3(a) -> int:
    evidence = Path(a.evidence).resolve()
    spec = BOARDS[a.board]
    cmd = [sys.executable, str(HERE / "t52_art3_live.py"), "k3", "--label", f"K3-{a.board}",
           "--evidence-dir", str(evidence / "k3" / a.board), "--work", str(Path(a.work) / "k3"),
           "--board-id", spec["boardId"], "--run-seconds", "240", "--client-fps", "30",
           "--build-record", a.build_record, "--package-record", a.package_record, "--extra-demo-arg=-RequireShotCaptured"]
    print(" ".join(cmd))
    r = subprocess.run(cmd, cwd=str(REPO), creationflags=L.NO_WINDOW)
    return r.returncode


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("k1", "k3"):
        s = sub.add_parser(name)
        s.add_argument("--board", required=True, choices=sorted(BOARDS))
        s.add_argument("--evidence", required=True)
        s.add_argument("--work", default=r"C:\tmp\w5br\runs")
        s.add_argument("--build-record", required=True)
        s.add_argument("--package-record", required=True)
        if name == "k1":
            s.add_argument("--probe", choices=["24", "48"])
    an = sub.add_parser("analyze")
    an.add_argument("--board", required=True, choices=sorted(BOARDS))
    an.add_argument("--evidence", required=True)
    an.add_argument("--k1-run", required=True)
    an.add_argument("--k3-run", required=True)
    an.add_argument("--probe24-run")
    an.add_argument("--probe48-run")
    an.add_argument("--derived-root", default=r"C:\tmp\w5br\derived")
    sh = sub.add_parser("sheets")
    sh.add_argument("--evidence", required=True)
    tb = sub.add_parser("table")
    tb.add_argument("--evidence", required=True)
    tb.add_argument("--t52")
    a = ap.parse_args(argv)
    return {"k1": cmd_k1, "k3": cmd_k3, "analyze": cmd_analyze, "sheets": cmd_sheets, "table": cmd_table}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
