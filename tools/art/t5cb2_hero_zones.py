#!/usr/bin/env python3
"""Wave 5c-B2, B1-8 «свет под фигуры»: zones of the v2 heroes on the PACKAGED-LIVE frames (board light rev 5,
EV100 2.05) against the concept, next to the look-dev b1 of the same heroes.

Why a proxy. The registered method (tools/art/material_library/ue_hero_lookdev.py measure) takes the zone of a pixel
from the MatID class of a DebugView-1 frame (debug MI) shot on the same camera as a plate frame. A packaged client
renders the game MIs only: there is no debug frame and no plate of a live board. So on the live frames the zone of a
pixel is taken by COLOUR: kNN (Lab) against prototypes = the pixels of each zone of the look-dev b1 frames of the same
hero (true MatID masks, eroded 1 px, the render gates of the config), the team MI frame of the side the fighter plays
(P1 / P2) moved to the reading exposure by the validated Filmic model (tools/art/ue_filmic.py shift_display_u8,
reading_bias_ev of the config = EV100 2.05). Extra classes: «other» (figure / base pixels outside the tolerance zones),
«board» (on the live frame: the tile annulus of the fighter's own cell, r 30..45 uu, sector towards the camera; on the
look-dev frame: the plate), «ring» (the calibrated screen bytes of the team ring: fill, keyline, rim). A pixel is kept
for a zone when its kNN vote is that zone and its nearest prototype is within --max-de; the zone masks are eroded 1 px
(as the method). Zone statistics, k (geometric mean over key zones) and the verdict (|Y/k - 1| <= 0.15,
|dHue| <= 12, |dSat| <= 0.10) are the method's (ue_hero_lookdev.cmd_measure formulas).

The proxy is validated on the look-dev b1 frames themselves (leave-one-view-out: prototypes of two views classify the
third) against the method on the same frames; the agreement is written next to every game number.

Attribution per zone (the look-dev C rule, extended to the board): within on the live frame -> «в допуске»; off on
the live frame but within on the look-dev b1 (same exposure, control scene with the Cobble light rev 5) -> «свет
доски / ракурс» (the board light, the camera pitch and the figure yaw differ, the material is the same); off on both
-> «материал» (the zone is off already under the control light at the same exposure).

    python tools/art/t5cb2_hero_zones.py run --out <dir> [--max-de 12] [--k 7]

Statuses: «измерено (прокси)», not an acceptance; frames: packaged-live strict only (classified in the RUNS stage).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "qa010"))
sys.path.insert(0, str(HERE / "material_library"))
import ue_filmic as F  # noqa: E402
import ue_hero_lookdev as LD  # noqa: E402

EVID = REPO / "docs/game-design/evidence"
TH = EVID / "ART-005/art3-live-3boards-r3-2026-09-30/t5cb-thresholds.json"
TAG = "b1"
HEROES = {
    "KingArthur": {"run": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2ld-ue", "mesh": "SK_KingArthur_H2LD"},
    "Merlin": {"run": "art/pipeline-candidates/ASSET-MERLIN-001/20260930-h2ld-ldc-ue", "mesh": "SK_Merlin_H2LD"},
    "Medusa": {"run": "art/pipeline-candidates/ASSET-MEDUSA-001/20260930-h2ld-ldc-ue", "mesh": "SK_Medusa_H2LD"},
    "Harpy": {"run": "art/pipeline-candidates/ASSET-HARPY-001/20260929-h3ld-ue", "mesh": "SK_Harpy_H3LD"},
}
VIEWS = ("front", "side", "back")
NL = chr(10)
BASE_TOP_UU = 5.5  # plinth top above the cell, uu (profiles: base_top_z 5.0-6.0)
# live frames (packaged-live strict, RUNS stage 5c-B2): (label, png, trace, board)
A12 = EVID / "ART-012/heroes-v2-live-2026-09-30"
A18 = EVID / "ART-018/long-k2-2026-09-30"


def live_frames() -> list[tuple[str, Path, Path, str]]:
    out = []
    for board in ("cobble-5x6", "sherwood-forest-8x5", "t-rex-paddock-7x5"):
        run = sorted((A12 / "k1" / board).glob("run-*"))[-1]
        for side in ("host", "joiner"):
            out.append((f"K1 {board} {side}", run / f"phase2-board-{side}-1920x1080.png",
                        run / f"phase2-client-{side}.trace.log", board))
    for z in ("1.6", "2.5", "3.5", "5"):
        run = sorted((A18 / f"k2-zoom-{z}" / "cobble-5x6").glob("run-*"))[-1]
        out.append((f"K2 {z}x cobble host", run / "phase2-board-host-1920x1080.png",
                    run / "phase2-client-host.trace.log", "cobble-5x6"))
    run = sorted((A18 / "k2-long-245s" / "cobble-5x6").glob("run-*"))[-1]
    out.append(("K2 5x @245s cobble host", run / "phase2-board-host-1920x1080.png", run / "phase2-client-host.trace.log",
                "cobble-5x6"))
    return out


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).as_posix()


def lab(u8: np.ndarray) -> np.ndarray:
    from qa010lib import color as C
    a = np.asarray(u8, np.uint8)
    shp = a.shape
    return C.linear_to_lab(C.u8_to_linear(a.reshape(-1, 1, 3)))[:, 0, :].reshape(shp[:-1] + (3,))


# ------------------------------------------------------------------ look-dev b1: masks, prototypes, method numbers
class Hero:
    def __init__(self, name: str):
        self.name = name
        self.run = REPO / HEROES[name]["run"]
        self.cfg = json.loads((self.run / "review-config.json").read_text(encoding="utf-8"))
        self.out = self.run / "review" / TAG
        self.bias = float(self.cfg.get("reading_bias_ev", -1.0))
        presets = json.loads((REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json").read_text(encoding="utf-8"))
        ids = {c["id"]: c["index"] for c in presets["classes"]}
        zc = self.cfg.get("zone_class") or {}
        self.zones = list(self.cfg["zones"])
        self.cls_of = {z: ids[zc.get(z, z)] for z in self.zones}
        self.classes = sorted(set(self.cls_of.values()) | {ids[c] for c in self.cfg.get("decode_classes") or []} | {0})
        self.concept = json.loads((REPO / self.cfg["concept_zones"]).read_text(encoding="utf-8"))["zones"]

    def frame(self, view: str, var: str):
        return LD.load_frame(self.out, self.cfg["hero"], TAG, f"{view}-{var}")

    def team_frame(self, view: str, team: str) -> np.ndarray:
        """The team MI frame (look-dev board exposure EV100 1.3) moved to the reading exposure (EV100 2.05)."""
        return F.shift_display_u8(self.frame(view, team.lower()), self.bias)

    def masks(self, view: str, team: str):
        """{zone: mask} of the method (MatID decode, erode 1, render regions, gates) + the figure mask (changed)."""
        dbg, plate = self.frame(view, "debug"), self.frame(view, "plate")
        cls, changed = LD.decode_debug(dbg, plate, self.classes, self.cfg.get("debug_calibration"))
        gates = self.cfg.get("render_gates") or {}
        gate_on = self.cfg.get("gate_on_variant")
        ref = self.frame(view, gate_on.lower()) if gate_on else self.team_frame(view, team)
        out = {}
        for z in self.zones:
            m = LD.erode(cls == self.cls_of[z], 1)
            reg = LD.zone_region(self.cfg, z, view, cls)
            if reg is not None:
                m &= reg
            if z in gates:
                g = np.zeros_like(m)
                g[m] = LD.gate(ref[m], gates[z])
                m = g
            out[z] = m
        return out, changed, cls


def zone_verdicts(stats: dict, cfg: dict, concept: dict) -> dict:
    """ue_hero_lookdev.cmd_measure formulas: k over the key zones, Y/k, dHue, dSat, within."""
    tol = cfg["tolerance"]
    key = [z for z in cfg["key_zones"] if z in stats and concept.get(z, {}).get("concept")]
    if not key:
        return {"k": None, "deltas": {}}
    lr = [math.log(concept[z]["concept"]["luma_Y_linear"] / max(stats[z]["luma_Y_linear"], 1e-5)) for z in key]
    k = math.exp(sum(lr) / len(lr))
    deltas = {}
    for z, u in stats.items():
        c = (concept.get(z) or {}).get("concept")
        if not c:
            continue
        yr = u["luma_Y_linear"] / max(c["luma_Y_linear"] / k, 1e-6)
        dh = ((u["hue_deg"] - c["hue_deg"] + 180.0) % 360.0) - 180.0
        ds = u["sat"] - c["sat"]
        hue_defined = c["sat"] >= float(tol.get("hue_min_sat", 0.0))
        ok = {"luma": abs(yr - 1.0) <= tol["luma_ratio"], "hue": (abs(dh) <= tol["hue_deg"]) if hue_defined else True,
              "sat": abs(ds) <= tol["sat"]}
        deltas[z] = {"Yk": round(yr, 3), "dHue": round(dh, 1), "dSat": round(ds, 3), "within": ok,
                     "all_within": all(ok.values()), "pixels": u.get("pixels"),
                     "tolerance_zone": z in (cfg.get("tolerance_zones") or [])}
    return {"k": round(k, 4), "key_zones": key, "deltas": deltas}


def pooled_stats(pix_by_zone: dict, min_px: int) -> dict:
    out = {}
    for z, arrs in pix_by_zone.items():
        arrs = [a for a in arrs if len(a)]
        if not arrs:
            continue
        px = np.concatenate(arrs, 0)
        if len(px) < min_px:
            continue
        out[z] = dict(LD.hsv_stats(px), pixels=int(len(px)))
    return out


def n_within(v: dict, zones: list[str]) -> tuple[int, int]:
    d = v.get("deltas") or {}
    meas = [z for z in zones if z in d]
    return sum(1 for z in meas if d[z]["all_within"]), len(meas)


class Proto:
    """kNN prototypes in Lab: zone pixels (+ other, board, ring)."""

    def __init__(self, per_class: dict, k: int, cap: int = 4000, seed: int = 7):
        from sklearn.neighbors import KNeighborsClassifier
        rng = np.random.default_rng(seed)
        xs, ys, self.labels = [], [], sorted(per_class)
        for i, name in enumerate(self.labels):
            a = per_class[name]
            if len(a) > cap:
                a = a[rng.choice(len(a), cap, replace=False)]
            xs.append(a)
            ys.append(np.full(len(a), i))
        self.x = np.concatenate(xs).astype(np.float32)
        self.y = np.concatenate(ys)
        self.knn = KNeighborsClassifier(n_neighbors=k).fit(self.x, self.y)

    def classify(self, lab_px: np.ndarray, max_de: float) -> np.ndarray:
        if not len(lab_px):
            return np.zeros(0, object)
        dist, _ = self.knn.kneighbors(lab_px.astype(np.float32), n_neighbors=1)
        lab_ = self.knn.predict(lab_px.astype(np.float32))
        names = np.array(self.labels, object)[lab_]
        names[dist[:, 0] > max_de] = "unknown"
        return names


def lookdev_protos(hero: Hero, team: str, views=VIEWS):
    """{class: Lab array} from the given views of the team-shift frames; zone pixels by the method masks."""
    per = {}
    for v in views:
        img = hero.team_frame(v, team)
        masks, changed, _cls = hero.masks(v, team)
        taken = np.zeros(changed.shape, bool)
        L = lab(img)
        for z, m in masks.items():
            per.setdefault(z, []).append(L[m])
            taken |= m
        per.setdefault("other", []).append(L[changed & ~taken & LD.erode(changed, 1)])
        per.setdefault("board", []).append(L[~changed][::17])
    return {k: np.concatenate(v, 0) for k, v in per.items() if sum(len(a) for a in v)}


def classify_to_zones(names: np.ndarray, coords: tuple, shape, zones: list[str]) -> dict:
    """{zone: mask} from per-pixel names, eroded 1 px (the method's erosion)."""
    out = {}
    for z in zones:
        m = np.zeros(shape, bool)
        sel = names == z
        m[coords[0][sel], coords[1][sel]] = True
        out[z] = LD.erode(m, 1)
    return out


def validate_hero(hero: Hero, team: str, k: int, max_de: float) -> dict:
    """Method vs proxy on the look-dev b1 team-shift frames (leave-one-view-out)."""
    method_px, proxy_px = {}, {}
    for v in VIEWS:
        img = hero.team_frame(v, team)
        masks, changed, _ = hero.masks(v, team)
        for z, m in masks.items():
            method_px.setdefault(z, []).append(img[m])
        protos = lookdev_protos(hero, team, [w for w in VIEWS if w != v])
        P = Proto(protos, k)
        ys, xs = np.nonzero(changed)
        names = P.classify(lab(img)[ys, xs], max_de)
        zm = classify_to_zones(names, (ys, xs), changed.shape, hero.zones)
        for z, m in zm.items():
            proxy_px.setdefault(z, []).append(img[m])
    mp = int(hero.cfg.get("min_px", 150))
    ms, ps = pooled_stats(method_px, mp), pooled_stats(proxy_px, mp)
    mv, pv = zone_verdicts(ms, hero.cfg, hero.concept), zone_verdicts(ps, hero.cfg, hero.concept)
    tz = hero.cfg.get("tolerance_zones") or []
    agree = [z for z in tz if z in mv["deltas"] and z in pv["deltas"]
             and mv["deltas"][z]["all_within"] == pv["deltas"][z]["all_within"]]
    dyk = [abs(mv["deltas"][z]["Yk"] - pv["deltas"][z]["Yk"]) for z in tz if z in mv["deltas"] and z in pv["deltas"]]
    dsat = [abs(mv["deltas"][z]["dSat"] - pv["deltas"][z]["dSat"]) for z in tz if z in mv["deltas"] and z in pv["deltas"]]
    return {"team": team, "method": mv, "proxy": pv, "methodWithin": n_within(mv, tz), "proxyWithin": n_within(pv, tz),
            "verdictAgreement": f"{len(agree)}/{len([z for z in tz if z in mv['deltas'] and z in pv['deltas']])}",
            "maxAbsDeltaYk": round(max(dyk), 3) if dyk else None, "maxAbsDeltaSat": round(max(dsat), 3) if dsat else None}


# ------------------------------------------------------------------ live frames
FIG = re.compile(r"SHOT figure fighter=(\S+) bbox=\(([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)\) ringR=([\d.]+) art=(\d) "
                 r"blockout=(\d) team=(P[12]) look=(P[12])")
V2 = re.compile(r"ARTPREVIEW heroesV2 fighter=(\S+) mesh=\S+/(SK_\w+)\s")
HEAD = re.compile(r"SHOT head fighter=(\S+) socket=\S+ mesh=(\S+) .*?headPx=([\d.]+)")
REQ = re.compile(r"SHOT request file=(\S+) frame=(\d+)")


def shot_lines(trace_text: str, png_name: str) -> list[str]:
    """The request-block lines of this frame (from the previous 'SHOT ctx' up to the request)."""
    lines = trace_text.splitlines()
    idx = [i for i, ln in enumerate(lines) if f"SHOT request file={png_name} " in ln]
    if not idx:
        return []
    end = idx[-1]
    start = max(i for i in range(end + 1) if "SHOT ctx " in lines[i])
    return lines[start:end + 1]


def live_measure(label: str, png: Path, trace: Path, board: str, heroes: dict, protos: dict, calib: dict, k: int,
                 max_de: float, min_px: int, crops_dir: Path | None) -> dict:
    sys.path.insert(0, str(HERE))
    import t53_readability as T53
    shot = T53.Shot(png, trace)
    text = trace.read_text(encoding="utf-8", errors="replace")
    block = shot_lines(text, png.name)
    mesh_of = {m.group(1): m.group(2) for m in V2.finditer(text)}
    heads = {m.group(1): (m.group(2), float(m.group(3))) for ln in block for m in [HEAD.search(ln)] if m}
    figs = {m.group(1): m for ln in block for m in [FIG.search(ln)] if m}
    rgb = shot.rgb
    H, W = rgb.shape[:2]
    L = shot.lab
    umg = np.zeros((H, W), bool)
    for r in T53.umg_rects(shot):
        x0, y0, x1, y1 = (int(round(v)) for v in r)
        umg[max(y0, 0):max(min(y1, H), 0), max(x0, 0):max(min(x1, W), 0)] = True
    ring_bytes = [calib[n]["screen"] for n in ("team.p1.fill", "team.p2.fill", "mark.keyline", "team.rim") if n in calib]
    ring_lab = lab(np.array(ring_bytes, np.uint8).reshape(-1, 1, 3))[:, 0, :]
    rng = np.random.default_rng(3)
    ring_proto = np.concatenate([ring_lab + rng.normal(0, 2.0, (400, 3)) for _ in range(1)]) if False else \
        np.concatenate([rl + rng.normal(0, 2.0, (400, 3)) for rl in ring_lab])
    rows = []
    for fid, f in sorted(shot.fighters.items()):
        mesh = mesh_of.get(fid) or (heads.get(fid) or ("", 0))[0]
        hero = next((h for h, spec in HEROES.items() if spec["mesh"] == mesh), None)
        fm = figs.get(fid)
        if hero is None or fm is None:
            rows.append({"fighter": fid, "mesh": mesh, "skip": "no v2 mesh / no SHOT figure"})
            continue
        team = fm.group(10)
        x0, y0, x1, y1 = (float(fm.group(i)) for i in range(2, 6))
        xi0, yi0, xi1, yi1 = max(int(x0), 0), max(int(y0), 0), min(int(math.ceil(x1)), W), min(int(math.ceil(y1)), H)
        if xi1 - xi0 < 8 or yi1 - yi0 < 8:
            rows.append({"fighter": fid, "hero": hero, "skip": "figure rect off-screen"})
            continue
        # local classes sampled by geometry on THIS frame, in the sector facing the camera (nothing of the figure in
        # front of it there): board = tiles r 30..95 uu around the fighter (sector 120 deg towards the camera); ring = the team ring bands
        # (r 16 x FS .. rimOut x FS, z 1.2: selection ring, shadowed tile, keylines, fill, rim); base = the plinth top r 10..14 uu x FS at z BASE_TOP_UU x FS and its side r 13..17 x FS
        fs = T53.fighter_scale(fid)
        cam = shot.proj.camera
        cdir = math.atan2(cam.pos[1] - f.world[1], cam.pos[0] - f.world[0])

        def ring_pts(r0, r1, z, half_deg, nr=8):
            pts_ = []
            for i in range(720):
                t = 2 * math.pi * i / 720
                if abs(((t - cdir + math.pi) % (2 * math.pi)) - math.pi) > math.radians(half_deg):
                    continue
                for rr in np.linspace(r0, r1, nr):
                    pts_.append((f.world[0] + rr * math.cos(t), f.world[1] + rr * math.sin(t), f.world[2] + z))
            return pts_

        bm = shot.mask_of(shot.pixels(ring_pts(30.0, 95.0, 0.0, 120.0, 24))) & ~umg
        rb = T53.ring_bands(fm.group(10))
        rin = min(v[0] for v in rb.values()) * fs
        rout = max(v[1] for v in rb.values()) * fs
        # from r 16 x FS: the selection ring (r 17.8-20), the shadowed tile inside the ring and the keyline go with it
        rm = shot.mask_of(shot.pixels(ring_pts(min(16.0 * fs, rin), rout, 1.2, 70.0, 28))) & ~umg
        base_pts = ring_pts(10.0 * fs, 14.0 * fs, BASE_TOP_UU * fs, 50.0, 6)
        for zz in np.linspace(1.0, BASE_TOP_UU - 0.5, 5):
            base_pts += ring_pts(13.0 * fs, 17.0 * fs, zz * fs, 60.0, 5)
        basem = shot.mask_of(shot.pixels(base_pts)) & ~umg & ~rm
        board_px = L[bm]
        per = {kk: vv for kk, vv in protos[(hero, team)].items() if kk != "board"}
        per["board"] = board_px if len(board_px) else protos[(hero, team)]["board"]
        per["ring"] = np.concatenate([ring_proto, L[rm]]) if rm.any() else ring_proto
        if basem.any():
            per["base"] = L[basem]
        reg = np.zeros((H, W), bool)
        reg[yi0:yi1, xi0:xi1] = True
        reg &= ~umg
        P = Proto(per, k)
        ys, xs = np.nonzero(reg)
        names = P.classify(L[ys, xs], max_de)
        cfg = heroes[hero].cfg
        # silhouette clean-up: (1) the front rim of the plinth top (r 8..15 x FS, z BASE_TOP, sector towards the camera)
        # carries the figure's shadow, as dark as dark cloth -> excluded by geometry; (2) figure-class pixels (zones +
        # other) are kept only in the connected components of the figure (8-connected after a 1 px closing; the
        # component under the head point and every component >= 5 % of it) - isolated specks on shadowed tiles go
        from scipy import ndimage as ndi
        rim_top = shot.mask_of(shot.pixels(ring_pts(8.0 * fs, 15.0 * fs, BASE_TOP_UU * fs, 80.0, 10)))
        figcls = set(heroes[hero].zones) | {"other"}
        fmask = np.zeros((H, W), bool)
        keep = np.array([n in figcls for n in names], bool)
        fmask[ys[keep], xs[keep]] = True
        fmask &= ~rim_top
        lab_, nlab = ndi.label(ndi.binary_closing(fmask, iterations=1), structure=np.ones((3, 3)))
        if nlab:
            sizes = ndi.sum(np.ones_like(lab_), lab_, index=np.arange(1, nlab + 1))
            core = None
            hm = re.search(r"SHOT head fighter=%s .*?screen=\(([-\d.]+),([-\d.]+)\)" % re.escape(fid), NL.join(block))
            if hm:
                hx, hy = int(float(hm.group(1))), int(float(hm.group(2)))
                if 0 <= hx < W and 0 <= hy < H and lab_[hy, hx]:
                    core = lab_[hy, hx]
            ref_size = sizes[core - 1] if core else sizes.max()
            good = {i + 1 for i, sz in enumerate(sizes) if sz >= 0.05 * ref_size}
            fmask &= np.isin(lab_, list(good))
        names = np.where(fmask[ys, xs], names, np.where(keep, "dropped", names))
        zm = classify_to_zones(names, (ys, xs), (H, W), heroes[hero].zones)
        stats = pooled_stats({z: [rgb[m]] for z, m in zm.items()}, min_px)
        ver = zone_verdicts(stats, cfg, heroes[hero].concept)
        counts = {n: int((names == n).sum()) for n in sorted(set(names.tolist()))}
        row = {"fighter": fid, "hero": hero, "team": team, "mesh": mesh, "rect": [x0, y0, x1, y1],
               "headPx": (heads.get(fid) or (None, None))[1], "classCounts": counts, "boardSamples": int(len(board_px)),
               "ringSamples": int(rm.sum()), "baseSamples": int(basem.sum()),
               "zonesMeasured": sorted(stats), "verdicts": ver,
               "within": n_within(ver, cfg.get("tolerance_zones") or [])}
        if crops_dir is not None:
            crops_dir.mkdir(parents=True, exist_ok=True)
            vis = rgb[yi0:yi1, xi0:xi1].copy()
            pal = {}
            for zi, z in enumerate(heroes[hero].zones):
                h_ = (zi * 0.618034) % 1.0
                import colorsys
                pal[z] = (np.array(colorsys.hsv_to_rgb(h_, 0.9, 1.0)) * 255).astype(np.uint8)
            over = vis.copy()
            for z, m in zm.items():
                mm = m[yi0:yi1, xi0:xi1]
                over[mm] = (0.35 * over[mm] + 0.65 * pal[z]).astype(np.uint8)
            both = np.concatenate([vis, over], 1)
            name = re.sub(r"[^\w.-]+", "-", f"{label}-{fid}-{hero}")
            Image.fromarray(both).save(crops_dir / f"{name}.jpg", quality=88)
            row["crop"] = rel(crops_dir / f"{name}.jpg")
        rows.append(row)
    return {"label": label, "frame": rel(png), "trace": rel(trace), "board": board,
            "render": {"expMin": re.search(r"expMin=([\d.]+)", "\n".join(block)).group(1)
                       if re.search(r"expMin=([\d.]+)", "\n".join(block)) else None},
            "fighters": rows}


def attribute(game: dict, lookdev: dict, reliable: bool = True) -> str:
    if game is None:
        return "не измерено"
    if not reliable:
        return "прокси ненадёжен для зоны (не атрибутируется)"
    if game["all_within"]:
        return ("в допуске (в look-dev вне: свет доски / ракурс помогают)"
                if lookdev is not None and not lookdev["all_within"] else "в допуске")
    if lookdev is not None and lookdev["all_within"]:
        return "свет доски / ракурс"
    return "материал" if lookdev is not None else "вне допуска (look-dev не измерен)"


def cmd_run(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    th = json.loads(TH.read_text(encoding="utf-8"))
    calib = th["calibration"]["bytes"]
    heroes = {h: Hero(h) for h in HEROES}
    teams = {"KingArthur": "P2", "Merlin": "P2", "Medusa": "P1", "Harpy": "P1"}
    doc = {"schema": "unmatched.t5cb2-hero-zones/1", "status": "измерено (прокси цветовой классификации, не метод MatID)",
           "method": __doc__.strip().split("\n\n")[1].replace("\n", " "),
           "tolerance": th["heroes"]["tolerance"], "b15Criteria": th["heroes"]["minZones"],
           "params": {"k": a.k, "maxDeltaE": a.max_de, "minPxLive": a.min_px, "lookdevTag": TAG,
                      "readingBiasEv": {h: heroes[h].bias for h in heroes}},
           "validation": {}, "lookdevOfficial": {}, "live": []}
    # look-dev b1: official measure (reading = neutral MI) + method/proxy on the team-shift frames
    for h, hero in heroes.items():
        m = json.loads((hero.out / f"measure-{TAG}.json").read_text(encoding="utf-8"))
        rd = (m.get("exposure") or {}).get("reading") or {}
        tz = hero.cfg.get("tolerance_zones") or []
        doc["lookdevOfficial"][h] = {
            "file": rel(hero.out / f"measure-{TAG}.json"), "k": rd.get("k_concept_over_ue_geomean_key_zones"),
            "within": [sum(1 for z in tz if (rd.get("deltas") or {}).get(z, {}).get("all_within")),
                       sum(1 for z in tz if z in (rd.get("deltas") or {}))],
            "verdicts": (m.get("verdicts") or {}).get("zones"),
            "deltas": {z: {kk: d.get(kk) for kk in ("Y_ratio_exposure_normalised", "dHue_deg", "dSat", "all_within")}
                       for z, d in (rd.get("deltas") or {}).items()}}
        doc["validation"][h] = validate_hero(hero, teams[h], a.k, a.max_de)
        print(h, "official", doc["lookdevOfficial"][h]["within"], "team-shift method", doc["validation"][h]["methodWithin"],
              "proxy", doc["validation"][h]["proxyWithin"], "agree", doc["validation"][h]["verdictAgreement"],
              "dYk", doc["validation"][h]["maxAbsDeltaYk"], flush=True)
    protos = {(h, teams[h]): lookdev_protos(heroes[h], teams[h]) for h in heroes}
    crops = out / "crops" if a.crops else None
    for label, png, trace, board in live_frames():
        r = live_measure(label, png, trace, board, heroes, protos, calib, a.k, a.max_de, a.min_px, crops)
        for row in r["fighters"]:
            if "verdicts" not in row:
                continue
            v = doc["validation"][row["hero"]]
            ref, refm = v["proxy"]["deltas"], v["method"]["deltas"]
            # the same classifier on both sides: game vs look-dev b1 (team MI at EV100 2.05), per zone
            row["vsLookdev"] = {z: {"Yratio": round(d["Yk"] / ref[z]["Yk"], 3) if ref.get(z) else None,
                                    "dSat": round(d["dSat"] - ref[z]["dSat"], 3) if ref.get(z) else None,
                                    "dHue": round(d["dHue"] - ref[z]["dHue"], 1) if ref.get(z) else None,
                                    "proxyReliable": bool(ref.get(z) and refm.get(z) and
                                                          ref[z]["all_within"] == refm[z]["all_within"] and
                                                          abs(ref[z]["Yk"] - refm[z]["Yk"]) <= 0.10 and
                                                          abs(ref[z]["dSat"] - refm[z]["dSat"]) <= 0.05)}
                                for z, d in row["verdicts"]["deltas"].items() if d["tolerance_zone"]}
            row["attribution"] = {z: attribute(d, ref.get(z), row["vsLookdev"][z]["proxyReliable"])
                                  for z, d in row["verdicts"]["deltas"].items() if d["tolerance_zone"]}
        doc["live"].append(r)
        print(label, [(x.get("hero"), x.get("within"), x.get("skip")) for x in r["fighters"]], flush=True)
    # per hero, per frame kind: best-sampled figure (most zone pixels) - summary table
    summ = {}
    for r in doc["live"]:
        for row in r["fighters"]:
            if "verdicts" not in row:
                continue
            key = (row["hero"], r["label"])
            px = sum(d.get("pixels") or 0 for d in row["verdicts"]["deltas"].values())
            if key not in summ or px > summ[key]["px"]:
                summ[key] = {"px": px, "within": row["within"], "fighter": row["fighter"], "k": row["verdicts"]["k"],
                             "attribution": row.get("attribution")}
    doc["summary"] = [{"hero": h, "frame": lbl, **v} for (h, lbl), v in sorted(summ.items())]
    (out / "hero-zones-live.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print("written", out / "hero-zones-live.json")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--k", type=int, default=7)
    r.add_argument("--max-de", type=float, default=12.0)
    r.add_argument("--min-px", type=int, default=60)
    r.add_argument("--crops", action="store_true")
    a = ap.parse_args(argv)
    return {"run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
