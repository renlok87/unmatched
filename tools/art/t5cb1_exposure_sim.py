#!/usr/bin/env python3
"""Wave 5c-B1 plan: what a board exposure / light change does to the heroes and to the board, estimated on EXISTING
frames (no editor, no new renders). The scene value of every lit pixel is recovered through the UE 5.8 Filmic tone
curve (tools/art/ue_filmic.py), scaled by 2^dEV and tone-mapped back; the unlit game layer (M_UM_GameLayer x
EyeAdaptationInverse: rings, zone marks, keylines) and UMG widgets do not follow the exposure and are kept.

    python tools/art/t5cb1_exposure_sim.py validate  --out C:/tmp/p0-review/5cb1-sim
    python tools/art/t5cb1_exposure_sim.py heroes    --out C:/tmp/p0-review/5cb1-sim [--evs -0.5,-0.75,-1,-1.25]
    python tools/art/t5cb1_exposure_sim.py board     --out C:/tmp/p0-review/5cb1-sim [--evs ...] [--key-fix]
    python tools/art/t5cb1_exposure_sim.py colours   --out C:/tmp/p0-review/5cb1-sim
    python tools/art/t5cb1_exposure_sim.py validate  --out <dir> --lookdev-tag b1
    python tools/art/t5cb1_exposure_sim.py packaged  --out <dir> --evidence <5c-B2 evidence dir> [--forecast board.json]

validate: (1) the model against the W5b-R calibration bytes of the game layer (hex -> screen, live editor);
(2) the sky series of T4.2 / W4-A (board K1 p50 luma at sky 8/12/16 must be linear in scene light after the inverse
curve); (3) look-dev C neutral (EV100 1.3) -> -1 EV against the real reading frames of the same camera (pixels of the
figure and zone medians through ue_hero_lookdev.cmd_measure).
heroes: zone verdicts of the four heroes (look-dev C final iterations) with the neutral frames moved by dEV.
board: W5b-R r3 K1 frames (joiner + host) with the lit pixels moved by dEV (+ the key pitch fix estimate): passable
luma, rings rev 2 keyline-vs-tile (registered + diagnostic + rev 3 reference), zones rev 2 per slot.
colours: candidate game-layer colours (Cobble red, two-tone ring rim) through the tone curve against measured keylines
and tiles.

Everything written here is «измерено/оценено по имеющимся кадрам», not an engine capture; the UE wave re-shoots.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import shutil
import sys
from argparse import Namespace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "qa010"))
sys.path.insert(0, str(HERE / "material_library"))
import ue_filmic as F  # noqa: E402

E_R2 = REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-r2-2026-09-29"
HEROES = {
    "KingArthur": ("art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2ld-ue", "i2"),
    "Merlin": ("art/pipeline-candidates/ASSET-MERLIN-001/20260930-h2ld-ldc-ue", "c3"),
    "Medusa": ("art/pipeline-candidates/ASSET-MEDUSA-001/20260930-h2ld-ldc-ue", "c3"),
    "Harpy": ("art/pipeline-candidates/ASSET-HARPY-001/20260929-h3ld-ue", "i3"),
}
R3_K1 = {
    "cobble-5x6": "k1/cobble-5x6/run-20260929-192438",
    "sherwood-forest-8x5": "k1/sherwood-forest-8x5/run-20260929-192952",
    "t-rex-paddock-7x5": "k1/t-rex-paddock-7x5/run-20260929-193528",
}
# T4.2 §3.4 (content-maps-t42-2026-09-29.md): the key at Pitch -55 instead of the parsed Pitch 0 adds this much K1
# board luma in the live editor at the final sky; the base is the editor K1 p50 at that sky (calibration notes of the
# profile: cobble 11.2 ~ interpolated 8->112.1 / 12->139.4, forest 11.8 -> 140.5 target, paddock 14.1 -> 144.1 @14.4)
KEY_FIX = {"cobble-5x6": (134.3, 9.3), "sherwood-forest-8x5": (139.3, 5.9), "t-rex-paddock-7x5": (142.3, 4.3)}
PROFILE_OF = {"cobble-5x6": "cobble-probe", "sherwood-forest-8x5": "forest-probe", "t-rex-paddock-7x5": "paddock-probe"}


def write_json(p: Path, doc) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).as_posix()


def luma709(u8) -> np.ndarray:
    a = np.asarray(u8, dtype=np.float64)
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def grey_scene_of_luma(y: float) -> float:
    """Scene grey value whose tone-mapped display luma is y (0..255)."""
    d = np.array([[y, y, y]]) / 255.0
    return float(F.display_to_scene(d)[0, 1])


def grey_luma_of_scene(s: float) -> float:
    return float(F.scene_to_display(np.array([[s, s, s]]))[0, 1] * 255.0)


def key_fix_ev(board: str) -> float:
    """Board-top exposure gain (EV) of the key pitch fix, from the T4.2 editor measurement."""
    base, add = KEY_FIX[board]
    return math.log2(grey_scene_of_luma(base + add) / grey_scene_of_luma(base))


# ------------------------------------------------------------------ validate
def validate_layer() -> dict:
    th = json.loads((E_R2 / "t53-thresholds.json").read_text(encoding="utf-8"))
    rows = []
    for k, v in th["calibration"]["bytes"].items():
        m = F.game_layer_screen_u8(v["hex"])
        rows.append({"id": k, "hex": v["hex"], "measuredScreen": v["screen"], "modelScreen": m,
                     "maxAbsLevel": int(np.abs(np.array(m) - np.array(v["screen"])).max()),
                     "lumaDelta": round(float(luma709(m) - luma709(v["screen"])), 2)})
    errs = [r["maxAbsLevel"] for r in rows]
    ld = [r["lumaDelta"] for r in rows]
    return {"what": "unlit game layer: model TM(FromSRGBColor(hex)) against the bytes measured in the live editor "
                    "(W5b-R diag/editor-diag.json, Epic viewport, flat plates)",
            "rows": rows, "maxAbsLevel": max(errs), "meanMaxAbsLevel": round(float(np.mean(errs)), 2),
            "lumaDeltaMedian": round(float(np.median(ld)), 2)}


def validate_sky() -> dict:
    """W4-A (Cobble, sky 8/12/16 -> K1 p50 112.1/139.4/159.5) and T4.2 forest/paddock series: after the inverse curve
    the board scene value must be affine in the sky intensity (a + b*sky; a = key/points/bounce, b > 0)."""
    series = {"cobble (W4-A, packaged)": [(8, 112.1), (12, 139.4), (16, 159.5)],
              "forest (T4.2, editor)": [(8, 114.7), (12, 140.6), (15.2, 156.4), (16, 159.9)],
              "paddock (T4.2, editor)": [(8, 102.9), (12, 130.9), (14.4, 144.1), (16, 151.7), (18.4, 161.6)]}
    out = {}
    for name, pts in series.items():
        sky = np.array([p[0] for p in pts], float)
        s = np.array([grey_scene_of_luma(p[1]) for p in pts])
        A = np.stack([np.ones_like(sky), sky], -1)
        coef, *_ = np.linalg.lstsq(A, s, rcond=None)
        pred = A @ coef
        pl = [grey_luma_of_scene(v) for v in pred]
        # the same with a pure display-gamma assumption (no tone curve), to show the curve matters
        g = (np.array([p[1] for p in pts]) / 255.0) ** 2.2
        cg, *_ = np.linalg.lstsq(A, g, rcond=None)
        plg = [255.0 * max(v, 0) ** (1 / 2.2) for v in A @ cg]
        out[name] = {"points": pts, "sceneGrey": [round(float(v), 5) for v in s],
                     "affine": {"a": round(float(coef[0]), 5), "b": round(float(coef[1]), 5)},
                     "offsetShareAtLastSky": round(float(coef[0] / pred[-1]), 3),
                     "lumaResidualMax": round(float(np.max(np.abs(np.array(pl) - [p[1] for p in pts]))), 2),
                     "lumaResidualMaxGamma22": round(float(np.max(np.abs(np.array(plg) - [p[1] for p in pts]))), 2)}
    return out


def _measure(run: Path, cfg: dict, tag: str, frames_src: Path, replace: dict, tmp: Path) -> dict:
    """Run ue_hero_lookdev.cmd_measure on a copy of the tag's frames with some variants replaced by arrays."""
    import ue_hero_lookdev as LD
    from PIL import Image
    work = tmp / ("%s-%s" % (cfg["hero"], tag))
    if work.exists():
        shutil.rmtree(work)
    (work / "frames").mkdir(parents=True)
    for p in frames_src.glob("*.png"):
        if p.name.endswith("-classmap.png"):
            continue
        shutil.copy2(p, work / "frames" / p.name)
    for name, arr in replace.items():
        Image.fromarray(arr).save(work / "frames" / name)
    with contextlib.redirect_stdout(io.StringIO()):
        res = LD.cmd_measure(Namespace(out=str(work), tag=tag), cfg)
    return res


def _load(p: Path) -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.open(p).convert("RGB"))


def hero_frames(hero: str):
    run, tag = HEROES[hero]
    run = REPO / run
    cfg = json.loads((run / "review-config.json").read_text(encoding="utf-8"))
    return run, tag, cfg, run / "review" / tag / "frames"


def validate_lookdev(tmp: Path) -> dict:
    out = {}
    for hero in HEROES:
        run, tag, cfg, fr = hero_frames(hero)
        h = hero.lower()
        pix = {}
        replace = {}
        for view in ("front", "side", "back", "k2-5x"):
            n, r = fr / f"{h}-{tag}-{view}-neutral.png", fr / f"{h}-{tag}-{view}-reading.png"
            if not (n.is_file() and r.is_file()):
                continue
            a, b = _load(n), _load(r)
            sim = F.shift_display_u8(a, float(cfg.get("reading_bias_ev", -1.0)))
            replace[r.name] = sim
            plate = fr / f"{h}-{tag}-{view}-plate.png"
            if plate.is_file():
                m = np.abs(a.astype(np.int16) - _load(plate).astype(np.int16)).max(-1) > 18
            else:
                m = np.ones(a.shape[:2], bool)
            d = np.abs(sim.astype(np.int16) - b.astype(np.int16))[m]
            dl = (luma709(sim[m]) - luma709(b[m]))
            pix[view] = {"pixels": int(m.sum()), "absLevelMedian": float(np.median(d)),
                         "absLevelP90": float(np.percentile(d, 90)),
                         "lumaBiasMedian": round(float(np.median(dl)), 2),
                         "region": "figure (neutral vs plate > 18 levels)" if plate.is_file() else "whole frame"}
        real = json.loads((fr.parent / f"measure-{tag}.json").read_text(encoding="utf-8"))
        simres = _measure(run, cfg, tag, fr, replace, tmp)
        zones = {}
        for z in cfg.get("tolerance_zones") or []:
            a_ = (real.get("exposure", {}).get("reading", {}).get("deltas") or {}).get(z)
            b_ = (simres.get("exposure", {}).get("reading", {}).get("deltas") or {}).get(z)
            ra = (real["zones"].get(z) or {}).get("reading")
            rb = (simres["zones"].get(z) or {}).get("reading")
            zones[z] = {"real": {"Yk": a_ and a_["Y_ratio_exposure_normalised"], "within": a_ and a_["all_within"],
                                 "medianSrgb": ra and ra["median_srgb"]},
                        "sim": {"Yk": b_ and b_["Y_ratio_exposure_normalised"], "within": b_ and b_["all_within"],
                                "medianSrgb": rb and rb["median_srgb"]}}
        agree = sum(1 for v in zones.values() if v["real"]["within"] == v["sim"]["within"])
        dyk = [abs(v["real"]["Yk"] - v["sim"]["Yk"]) for v in zones.values() if v["real"]["Yk"] and v["sim"]["Yk"]]
        out[hero] = {"tag": tag, "pixels": pix, "zones": zones, "verdictAgreement": f"{agree}/{len(zones)}",
                     "maxAbsDeltaYk": round(max(dyk), 3) if dyk else None,
                     "kReal": real["exposure"]["reading"]["k_concept_over_ue_geomean_key_zones"],
                     "kSim": simres["exposure"]["reading"]["k_concept_over_ue_geomean_key_zones"]}
    return out


def cmd_validate(a) -> int:
    out = Path(a.out)
    if getattr(a, "lookdev_tag", None):
        # frames of another look-dev tag (e.g. b1 of 5c-B1: shot at the reading_bias_ev now in the configs); the
        # default tags (i2 / c3 / i3) were shot at -1.0 EV and no longer match the configs' -0.75
        for h in HEROES:
            HEROES[h] = (HEROES[h][0], a.lookdev_tag)
    doc = {"schema": "unmatched.t5cb1-sim-validate/1", "status": "оценено по имеющимся кадрам (модель, не захват)",
           "lookdevTags": {h: v[1] for h, v in HEROES.items()},
           "model": "tools/art/ue_filmic.py (UE 5.8 Filmic, defaults)", "layer": validate_layer(),
           "sky": validate_sky(), "lookdev": validate_lookdev(out / "tmp")}
    write_json(out / "validate.json", doc)
    print(json.dumps({"layer": {k: doc["layer"][k] for k in ("maxAbsLevel", "meanMaxAbsLevel", "lumaDeltaMedian")},
                      "sky": {k: {kk: v[kk] for kk in ("affine", "lumaResidualMax", "lumaResidualMaxGamma22")}
                              for k, v in doc["sky"].items()},
                      "lookdev": {k: {kk: v[kk] for kk in ("verdictAgreement", "maxAbsDeltaYk", "kReal", "kSim")}
                                  | {"pix": {vv: (p["absLevelMedian"], p["absLevelP90"], p["lumaBiasMedian"])
                                             for vv, p in v["pixels"].items()}}
                                  for k, v in doc["lookdev"].items()}}, ensure_ascii=False, indent=1))
    return 0


# ------------------------------------------------------------------ heroes
def cmd_heroes(a) -> int:
    out = Path(a.out)
    evs = [float(x) for x in a.evs.split(",")]
    doc = {"schema": "unmatched.t5cb1-sim-heroes/1", "status": "оценено по имеющимся кадрам (модель, не захват)",
           "method": "neutral frames (EV100 1.3, Cobble light in P1.7, key Pitch -55) moved by dEV through the inverse "
                     "and forward Filmic curve; zones measured by ue_hero_lookdev.cmd_measure (same masks, concept, k, "
                     "tolerances); 'reading' = the REAL -1.0 EV frames", "evs": evs, "heroes": {}}
    for hero in HEROES:
        run, tag, cfg, fr = hero_frames(hero)
        h = hero.lower()
        tz = cfg.get("tolerance_zones") or []
        rows = {}
        real = json.loads((fr.parent / f"measure-{tag}.json").read_text(encoding="utf-8"))
        for label, var in (("nominal EV100 1.3 (real)", "neutral"), ("reading -1.0 EV (real)", "reading")):
            d = real["exposure"][var]["deltas"]
            rows[label] = {"pass": sum(1 for z in tz if d.get(z, {}).get("all_within")), "of": len(tz),
                           "zones": {z: [d[z]["Y_ratio_exposure_normalised"], d[z]["dHue_deg"], d[z]["dSat"],
                                         d[z]["all_within"]] for z in tz if z in d}}
        for ev in evs:
            # the simulated nominal goes into the 'reading' slot: the hue / value gates of gate_on_variant are computed
            # on the REAL neutral frame, as in the look-dev measurement
            rep = {}
            for view in ("front", "side", "back"):
                n = fr / f"{h}-{tag}-{view}-neutral.png"
                if n.is_file():
                    rep[f"{h}-{tag}-{view}-reading.png"] = F.shift_display_u8(_load(n), ev)
            res = _measure(run, cfg, tag, fr, rep, out / "tmp")
            d = res["exposure"]["reading"]["deltas"]
            rows[f"{ev:+.2f} EV (sim)"] = {"pass": sum(1 for z in tz if d.get(z, {}).get("all_within")), "of": len(tz),
                                           "k": res["exposure"]["reading"]["k_concept_over_ue_geomean_key_zones"],
                                           "zones": {z: [d[z]["Y_ratio_exposure_normalised"], d[z]["dHue_deg"],
                                                         d[z]["dSat"], d[z]["all_within"]] for z in tz if z in d}}
        doc["heroes"][hero] = {"tag": tag, "toleranceZones": tz, "rows": rows}
        print(hero, {k: "%d/%d" % (v["pass"], v["of"]) for k, v in rows.items()}, flush=True)
    write_json(out / "heroes.json", doc)
    return 0


# ------------------------------------------------------------------ board
def _reshade(shot, rgb):
    """A copy of a t53 Shot (or t52 Frame) with new pixels and recomputed derived variants."""
    import copy
    from qa010lib import color as C
    s = copy.copy(shot)
    s.rgb = rgb
    s.variants = {"color": rgb, "gray": C.grayscale(rgb), "deuteranopia": C.deuteranopia(rgb)}
    if hasattr(shot, "lum"):
        s.lum = {k: C.relative_luminance(v) for k, v in s.variants.items()}
        s.luma_gray = C.luma_u8(s.variants["gray"])
        s.lab = C.linear_to_lab(C.u8_to_linear(rgb))
    else:
        s.lab = {k: C.linear_to_lab(C.u8_to_linear(v)) for k, v in s.variants.items()}
    return s


def unlit_mask(shot, calib: dict, cells: list[dict], zone_keys: list[str]) -> np.ndarray:
    """Pixels that do not follow the exposure: UMG rects of the SHOT block and game-layer colours inside the ring bands
    and the zone mark slots (geometry from the trace projection)."""
    import t53_readability as T
    import t53_team_ring as RING
    m = np.zeros((shot.h, shot.w), bool)
    b = shot.block
    rects = [w.get("bbox") for w in b.widgets if isinstance(w.get("bbox"), tuple)]
    rects += [p["bbox"] for p in getattr(b, "panels", []) or []]
    rects += [d["bbox"] for d in getattr(b, "damage", []) or []]
    for t in (b.plate, b.icon):
        if t is not None and isinstance(getattr(t, "value", None), dict) and t.value.get("bbox"):
            rects.append(t.value["bbox"])
    for r in rects:
        x0, y0, x1, y1 = [int(round(v)) for v in r]
        m[max(y0, 0):max(y1, 0), max(x0, 0):max(x1, 0)] = True
    geo = np.zeros_like(m)
    for fid, f in shot.fighters.items():
        info = shot.rings.get(fid)
        if not info or not info["shown"]:
            continue
        fs = T.fighter_scale(fid)
        z = f.world[2] + RING.RING_SPEC["zMax"]
        for band, (r0, r1) in T.ring_bands(info["look"]).items():
            geo |= shot.mask_of(shot.pixels(T.band_samples(info["look"], r0 - 1.0, r1 + 1.0, fs, f.world, z, step=0.5)))
    for c in cells:
        if c["obstacle"]:
            continue
        cc = shot.board.cell_center(c["x"], c["y"])
        for i, _k in enumerate(c["zones"]):
            geo |= shot.mask_of(shot.pixels(T.slot_points(cc[0], cc[1], i, step=0.75)))
    # dilate geometry by 1 px
    g2 = geo.copy()
    g2[1:] |= geo[:-1]
    g2[:-1] |= geo[1:]
    g2[:, 1:] |= geo[:, :-1]
    g2[:, :-1] |= geo[:, 1:]
    col = np.zeros_like(m)
    keys = ["team.p1.fill", "team.p2.fill", "mark.keyline", "zone.keyline"] + ["zone." + k for k in zone_keys]
    for k in keys:
        if k in calib:
            col |= shot.de_to(calib[k]["screen"]) <= 15.0
    return m | (g2 & col)


def board_metrics(shot, fr52, th, calib, cells, key: str) -> dict:
    import t53_readability as T
    rings = T.rings_rev2(shot, th, calib, cells)
    zones = T.zones_rev2(shot, cells, th, calib)
    rev3 = {r["fighter"]: T.ring_tile_reference_rev3(shot, r["fighter"], calib, cells)
            for r in rings["fighters"] if "look" in r}
    passable = [(c["x"], c["y"]) for c in cells if not c["obstacle"]]
    pm = fr52.mask(passable)
    ly = luma709(fr52.rgb[pm])
    out = {"passableLuma": {"p50": round(float(np.percentile(ly, 50)), 1), "p90": round(float(np.percentile(ly, 90)), 1)},
           "rings": [], "zones": {}}
    for r in rings["fighters"]:
        if "look" not in r:
            continue
        v = r["variants"]
        diag = r.get("keylineVsTileDiag") or {}
        r3 = rev3.get(r["fighter"]) or {}
        out["rings"].append({"name": r["name"], "look": r["look"], "tilePx": r["tilePx"],
                             "keylineVsTile": [v[x]["keylineVsTile"] for x in ("color", "gray", "deuteranopia")],
                             "diag": [diag.get(x) for x in ("color", "gray", "deuteranopia")],
                             "rev3": [r3.get(x, {}).get("keylineVsTile") for x in ("color", "gray", "deuteranopia")],
                             "rev3TilePx": r3.get("tilePx"),
                             "rev3TileRelLum": [r3.get(x, {}).get("tileRelLum") for x in ("color", "gray", "deuteranopia")],
                             "keylineRelLum": [v[x]["keylineRelLum"] for x in ("color", "gray", "deuteranopia")],
                             "fillVsKeyline": [v[x]["fillVsKeyline"] for x in ("color", "gray", "deuteranopia")],
                             "pass": r["keylineVsTilePass"]})
    for k, z in zones["zones"].items():
        out["zones"][k] = {"slots": z["slots"], "pass": z["pass"],
                           "keylineVsTile": {vn: z["variants"][vn]["keylineVsTile"] for vn in ("color", "gray", "deuteranopia")},
                           "fillVsKeyline": {vn: z["variants"][vn]["fillVsKeyline"] for vn in ("color", "gray", "deuteranopia")}}
    out["multizone"] = {"cells": zones["multizone"]["cells"], "pass": zones["multizone"]["pass"]}
    return out


def cmd_board(a) -> int:
    import t52_art3_live as T52
    import t53_readability as T
    out = Path(a.out)
    evs = [float(x) for x in a.evs.split(",")]
    th = json.loads((E_R2 / "t53-thresholds.json").read_text(encoding="utf-8"))
    calib = th["calibration"]["bytes"]
    prof = json.loads(T52.PROFILES.read_text(encoding="utf-8"))
    doc = {"schema": "unmatched.t5cb1-sim-board/1", "status": "оценено по имеющимся кадрам (модель, не захват)",
           "method": "W5b-R r3 K1 frames (G4/P3, packaged-live strict); lit pixels (everything but UMG rects and game-layer "
                     "colours inside ring bands / zone slots) moved by dEV_board = dEV_exposure + keyFix (T4.2 §3.4 editor "
                     "delta of the key at Pitch -55, converted through the inverse curve); metrics = t53 rings rev 2 "
                     "(+ diagnostic and rev 3 reference) and zones rev 2 on the moved frame",
           "keyFixEv": {k: round(key_fix_ev(k), 3) for k in KEY_FIX}, "boards": {}}
    for key, runp in R3_K1.items():
        run = E_R2 / runp
        cells = T52.board_cells(T.T52_EVIDENCE if key == "cobble-5x6" else E_R2, key)
        zone_keys = sorted({z for c in cells for z in c["zones"]})
        res = {}
        for side in a.sides.split(","):
            png, tr = run / f"phase2-board-{side}-1920x1080.png", run / f"phase2-client-{side}.trace.log"
            shot = T.Shot(png, tr)
            fr52 = T52.Frame(png, tr)
            lit = ~unlit_mask(shot, calib, cells, zone_keys)
            rows = {"base": board_metrics(shot, fr52, th, calib, cells, key)}
            for ev in evs:
                for fix in ((False, True) if a.key_fix else (False,)):
                    evb = ev + (key_fix_ev(key) if fix else 0.0)
                    rgb = F.shift_display_u8(shot.rgb, evb, lit)
                    lab = f"{ev:+.2f} EV" + (" + key fix" if fix else "")
                    rows[lab] = board_metrics(_reshade(shot, rgb), _reshade(fr52, rgb), th, calib, cells, key)
                    rows[lab]["boardEv"] = round(evb, 3)
                    if side == "joiner" and a.save_frames:
                        from PIL import Image
                        (out / "frames").mkdir(parents=True, exist_ok=True)
                        Image.fromarray(rgb).resize((960, 540)).save(
                            out / "frames" / f"{key}-{side}-{lab.replace(' ', '').replace('+', 'p').replace('-', 'm')}.jpg",
                            quality=88)
            res[side] = {"frame": rel(png), "litShare": round(float(lit.mean()), 4), "rows": rows}
            print(key, side, {k: (v["passableLuma"]["p50"], min((min(x for x in r["rev3"] if x) for r in v["rings"]
                                                                   if any(r["rev3"])), default=None))
                              for k, v in rows.items()}, flush=True)
        doc["boards"][key] = {"profile": PROFILE_OF[key], "light": prof["lightProfiles"][PROFILE_OF[key]], "sides": res}
    write_json(out / "board.json", doc)
    return 0


# ------------------------------------------------------------------ colours
def wcag(a: float, b: float) -> float:
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def rel_lum_u8(u8, variant="color") -> float:
    from qa010lib import color as C
    a = np.array(u8, dtype=np.uint8).reshape(1, 1, 3)
    if variant == "gray":
        a = C.grayscale(a)
    elif variant == "deuteranopia":
        a = C.deuteranopia(a)
    return float(C.relative_luminance(a)[0, 0])


def de76(a_u8, b_u8) -> float:
    from qa010lib import color as C
    la = C.linear_to_lab(C.u8_to_linear(np.array(a_u8, np.uint8).reshape(1, 1, 3)))[0, 0]
    lb = C.linear_to_lab(C.u8_to_linear(np.array(b_u8, np.uint8).reshape(1, 1, 3)))[0, 0]
    return float(np.linalg.norm(la - lb))


def cmd_colours(a) -> int:
    """Cobble red candidates and the two-tone ring rim candidates, on the calibrated/model screen bytes; the keyline and
    tile luminances are the measured medians of the r3 frames (board.json of this tool, base rows)."""
    out = Path(a.out)
    th = json.loads((E_R2 / "t53-thresholds.json").read_text(encoding="utf-8"))
    calib = th["calibration"]["bytes"]
    board = json.loads((out / "board.json").read_text(encoding="utf-8"))
    # measured Cobble red slot keyline (median of slots) from zone-contrast-r2.json
    zc = json.loads((E_R2 / "analysis/cobble-5x6/zone-contrast-r2.json").read_text(encoding="utf-8"))
    red_slots = [s for s in zc["frames"]["K1_joiner"]["slots"] if s["zone"] == "red" and not s["occupied"]]
    others = {k[5:]: v["screen"] for k, v in calib.items() if k.startswith("zone.") and k not in ("zone.keyline", "zone.red")}
    # the measured fill/keyline of the current red gives the effective keyline luminance per variant
    cur = calib["zone.red"]["screen"]
    eff_key = {}
    for vn in ("color", "gray", "deuteranopia"):
        vals = [s["variants"][vn]["fillVsKeyline"] for s in red_slots if s["variants"][vn]["fillVsKeyline"]]
        fk = float(np.median(vals))
        lf = rel_lum_u8(cur, vn)
        eff_key[vn] = (lf + 0.05) / fk - 0.05
    cands = ["#D8453B", "#E0503F", "#E45A44", "#E8604A", "#EC6650", "#E85A4F", "#F06A55", "#E4504A"]
    reds = []
    for hx in cands:
        scr = F.game_layer_screen_u8(hx) if hx != "#D8453B" else cur
        rec = {"hex": hx, "screen": scr, "hueDeg": None,
               "fillVsKeyline": {vn: round(wcag(rel_lum_u8(scr, vn), eff_key[vn]), 2) for vn in eff_key},
               "minDE76ToOtherZones": None}
        import colorsys
        h, s, v = colorsys.rgb_to_hsv(*[c / 255.0 for c in scr])
        rec["hueDeg"] = round(h * 360.0, 1)
        dists = {k: round(de76(scr, v_), 1) for k, v_ in others.items()}
        near = min(dists, key=dists.get)
        rec["minDE76ToOtherZones"] = [near, dists[near]]
        rec["dE76ToOrange"] = dists.get("orange")
        rec["dE76ToBrown"] = dists.get("brown")
        rec["dE76ToCurrentRed"] = round(de76(scr, cur), 1)
        rec["dE76ToBlue"] = dists.get("blue")
        rec["grayDeltaYprimeToBlue"] = round(float(luma709(scr) - luma709(calib["zone.blue"]["screen"])), 1)
        reds.append(rec)
    # rim candidates vs the tile (rev 3 reference) of every ring in board.json rows and vs the fills
    rims = []
    for hx in ("#F2ECDE", "#E6E0D2", "#D8D2C4", "#FFFFFF"):
        scr = F.game_layer_screen_u8(hx)
        rec = {"hex": hx, "screen": scr, "vsFill": {
            "P1": round(wcag(rel_lum_u8(scr), rel_lum_u8(calib["team.p1.fill"]["screen"])), 2),
            "P2": round(wcag(rel_lum_u8(scr), rel_lum_u8(calib["team.p2.fill"]["screen"])), 2)},
            "vsKeyline": round(wcag(rel_lum_u8(scr), rel_lum_u8(calib["mark.keyline"]["screen"])), 2), "boards": {}}
        for key, b in board["boards"].items():
            for side, sd in b["sides"].items():
                for lab, row in sd["rows"].items():
                    edge = []
                    for r in row["rings"]:
                        for i, vn in enumerate(("color", "gray", "deuteranopia")):
                            lt = r["rev3TileRelLum"][i]
                            lk = r["keylineRelLum"][i]
                            if lt is None or lk is None:
                                continue
                            lr = rel_lum_u8(scr, vn)
                            edge.append(max(wcag(lk, lt), wcag(lr, lt)))
                    if edge:
                        rec["boards"].setdefault(key, {})[f"{side} {lab}"] = {"twoToneEdgeMin": round(min(edge), 2),
                                                                              "n": len(edge)}
        rims.append(rec)
    doc = {"schema": "unmatched.t5cb1-sim-colours/1", "status": "оценено (модель экранных байтов + замеры r3)",
           "effectiveKeylineRelLumCobbleRed": {k: round(v, 5) for k, v in eff_key.items()},
           "note": "fill/keyline of a candidate = its model screen bytes (ue_filmic, game layer) against the effective "
                   "keyline luminance of the Cobble red slots (median fill/keyline of r3 solved for the keyline), so the "
                   "antialiased keyline of the real frames is kept; min dE76 to the other zone screen colours",
           "reds": reds, "rims": rims}
    write_json(out / "colours.json", doc)
    for r in reds:
        print(r["hex"], r["screen"], r["hueDeg"], r["fillVsKeyline"], r["minDE76ToOtherZones"], r["dE76ToCurrentRed"])
    for r in rims:
        print(r["hex"], r["screen"], r["vsFill"], r["vsKeyline"],
              {k: min(x["twoToneEdgeMin"] for x in v.values()) for k, v in r["boards"].items()})
    return 0


# ------------------------------------------------------------------ packaged (5c-B2): forecast vs measurement
def cmd_packaged(a) -> int:
    """The board forecast of the plan (board.json row '<ev> EV + key fix', W5b-R r3 K1 frames moved by the model)
    against the packaged 5c-B2 K1 frames analysed by t53_readability analyze / rings-rev3 (<evidence>/analysis/<board>):
    passable luma p50 / p90 of K1 joiner, zone medians (keyline vs tile, fill vs keyline) and the ring tile reference
    rev 3 (tile relative luminance). Zones whose colour changed in B1-2 (red, gray) are compared for keyline vs tile
    only (the tile side of the forecast is valid, the fill side is not)."""
    out = Path(a.out)
    ev_dir = Path(a.evidence)
    fc = json.loads(Path(a.forecast).read_text(encoding="utf-8"))
    row_key = f"{float(a.ev):+.2f} EV + key fix"
    doc = {"schema": "unmatched.t5cb1-sim-packaged/1", "status": "измерено (прогноз плана против packaged-кадров 5c-B2)",
           "forecast": rel(Path(a.forecast)), "forecastRow": row_key, "evidence": rel(ev_dir), "boards": {}}
    for key in R3_K1:
        an = ev_dir / "analysis" / key
        lum = json.loads((an / "luma-sections.json").read_text(encoding="utf-8"))["frames"]["K1_joiner"]["passable"]["color"]
        zr = json.loads((an / "zone-contrast-r2.json").read_text(encoding="utf-8"))["frames"]["K1_joiner"]["zones"]
        r3 = json.loads((an / "rings-rev3.json").read_text(encoding="utf-8"))["frames"]["K1_joiner"]["fighters"]
        f = fc["boards"][key]["sides"]["joiner"]["rows"].get(row_key)
        base = fc["boards"][key]["sides"]["joiner"]["rows"]["base"]
        if f is None:
            continue
        zones = {}
        for z, v in zr.items():
            fz = (f.get("zones") or {}).get(z)
            if not fz:
                continue
            changed = z in ("red", "gray")
            zones[z] = {"keylineVsTile": {"forecast": fz["keylineVsTile"]["color"], "packaged": v["variants"]["color"]["keylineVsTile"]},
                        "fillVsKeyline": {"forecast": None if changed else fz["fillVsKeyline"]["color"],
                                          "packaged": v["variants"]["color"]["fillVsKeyline"]},
                        "colourChangedInB1_2": changed}
        tile_f = {r["name"]: r["rev3TileRelLum"][0] for r in f["rings"] if r.get("rev3TileRelLum")}
        tile_b = {r["name"]: r["rev3TileRelLum"][0] for r in base["rings"] if r.get("rev3TileRelLum")}
        tiles = []
        for r in r3:
            tr = (r.get("tileReference") or {}).get("color") or {}
            if r["name"] in tile_f and tr.get("tileRelLum"):
                tiles.append({"name": r["name"], "r3": round(tile_b.get(r["name"]), 4) if tile_b.get(r["name"]) else None,
                              "forecast": round(tile_f[r["name"]], 4), "packaged": round(tr["tileRelLum"], 4),
                              "ratioPackagedOverForecast": round(tr["tileRelLum"] / tile_f[r["name"]], 3)})
        rat = [t["ratioPackagedOverForecast"] for t in tiles]
        doc["boards"][key] = {
            "passableLumaK1Joiner": {"r3": base["passableLuma"], "forecast": f["passableLuma"],
                                     "packaged": {"p50": round(lum["luma_p50"], 1), "p90": round(lum["luma_p90"], 1)},
                                     "deltaP50": round(lum["luma_p50"] - f["passableLuma"]["p50"], 1)},
            "boardEv": f.get("boardEv"), "zones": zones, "ringTileRev3": tiles,
            "ringTileRatioMedian": round(float(np.median(rat)), 3) if rat else None,
            "ringTileEvError": round(float(np.log2(np.median(rat))), 3) if rat else None}
        print(key, doc["boards"][key]["passableLumaK1Joiner"], doc["boards"][key]["ringTileRatioMedian"], flush=True)
    write_json(out / "packaged-vs-forecast.json", doc)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["validate", "heroes", "board", "colours", "packaged"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--evs", default="-0.5,-0.75,-1.0,-1.25")
    ap.add_argument("--key-fix", action="store_true")
    ap.add_argument("--save-frames", action="store_true")
    ap.add_argument("--sides", default="joiner,host")
    ap.add_argument("--lookdev-tag", help="validate: look-dev tag of the frames (default: i2 / c3 / c3 / i3)")
    ap.add_argument("--evidence", help="packaged: evidence dir with analysis/<board> (t53 analyze + rings-rev3)")
    ap.add_argument("--forecast", default="C:/tmp/p0-review/5cb1-sim/board.json", help="packaged: board.json of the plan")
    ap.add_argument("--ev", default="-0.75", help="packaged: the exposure row of the forecast")
    a = ap.parse_args(argv)
    return {"validate": cmd_validate, "heroes": cmd_heroes, "board": cmd_board, "colours": cmd_colours,
            "packaged": cmd_packaged}[a.command](a)


if __name__ == "__main__":
    sys.exit(main())
