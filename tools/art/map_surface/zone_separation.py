#!/usr/bin/env python3
"""Zone colour separation of an original-map board under the night light (ENV-MAPS P4, concept review 2026-10-01
'readability': Marmoreal pink vs lavender, Sarpedon light-blue vs pink). CPU only; the map textures are read (never
written) from the out-of-git derived maps (ENV-U3/U7), frames and traces are the S08 -Bench / live evidence.

  zone_separation.py measure <map> <frame.png> <trace.log> [--json out.json]
      per zone: the median CIELAB colour of its circle sectors on the ORIGINAL map (BC texture) and on the frame,
      then dE76 of every zone pair (adjacent = sharing a circle or a link; 'all' = every pair). The camera of the frame
      is the 'SHOT ctx' line before its 'SHOT captured file=' line (S08 pinhole, horizontal FOV 35).
  zone_separation.py fit <map> <frame.png> <trace.log> --out model.json
      fits a render model of the map plane on the frame: per-channel lit gain k_c, a smooth spatial light field
      (moon pool + key falloff), an emissive gain e, ACES-like tonemap; the grade in effect is read from the trace
      line 'ARTPREVIEW map grade ...' (profile values incl. the graph-v2 mask terms).
  zone_separation.py predict <map> --model model.json --measured measure.json [--grade-json g.json]
      predicts the frame dE of every pair under another grade (default: the current profile mapGrade,
      k1_mock.profile_map_grade) as measured dE x model(new) / model(fitted grade); also the model map luma and the
      circle-outline dL* change. A prediction, not a measurement: the Tune stage re-measures the new frames.

Zones per circle sector: the divider rays of <map>.vector-layer.json cut each circle into sectors; a sector takes the
zone of its space whose topology (SVG) colour is nearest to the sector's painted colour (each zone once per space).
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import k1_mock  # noqa: E402

MAIN_DERIVED = Path("C:/Users/ren/WebstormProjects/unmached/unmached/scraped-data/derived/maps")
SRC = (1337, 866)
UU_PER_PX = 2.0 / 3.0
LUMA = np.array([0.2126, 0.7152, 0.0722])
SECTOR_FRACS = (0.35, 0.45, 0.55, 0.65, 0.75)  # of the ring centre radius: inside the circle, clear of the rim
EDGE_FILL = (0.45, 0.55, 0.65, 0.75)
EDGE_LINE = (0.97, 1.0, 1.03)


# ------------------------------------------------------------------ colour
def srgb_to_lin(c):
    c = np.asarray(c, np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb8(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055) * 255


def lab(rgb8) -> np.ndarray:
    """sRGB 0..255 -> CIELAB (D65)."""
    xyz = srgb_to_lin(rgb8) @ np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]).T
    xyz = xyz / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def aces(x):
    x = np.maximum(x, 0)
    return np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)


def aces_inv(y):
    y = np.clip(y, 0, 0.999)
    a, b, c = 2.51 - 2.43 * y, 0.03 - 0.59 * y, -0.14 * y
    return (-b + np.sqrt(b * b - 4 * a * c)) / (2 * a)


# ------------------------------------------------------------------ camera / trace
class Cam:
    """S08 pinhole (horizontal FOV, FRotationMatrix axes, top-left origin) = measure.py / qa010 projection."""

    def __init__(self, pos, pitch, yaw, w=1920, h=1080, hfov=35.0):
        p, y = math.radians(pitch), math.radians(yaw)
        self.pos = np.array(pos, float)
        self.fwd = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
        self.right = np.array([-math.sin(y), math.cos(y), 0.0])
        self.up = np.array([-math.sin(p) * math.cos(y), -math.sin(p) * math.sin(y), math.cos(p)])
        self.tan_h = math.tan(math.radians(hfov / 2))
        self.tan_v = self.tan_h / (w / h)
        self.w, self.h = w, h

    def project(self, pts) -> np.ndarray:
        v = np.asarray(pts, float) - self.pos
        z = v @ self.fwd
        return np.c_[((v @ self.right) / z / self.tan_h + 1) / 2 * self.w,
                     (1 - (v @ self.up) / z / self.tan_v) / 2 * self.h]


def shot_camera(trace: Path, frame_name: str):
    ctx = None
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"SHOT ctx .*cam=\(([-\d.]+),([-\d.]+),([-\d.]+)\) rot=\(([-\d.]+),([-\d.]+),([-\d.]+)\)", line)
        if m:
            ctx = [float(x) for x in m.groups()]
            continue
        m = re.search(r"SHOT captured file=(\S+)", line)
        if m and ctx and m.group(1) == frame_name:
            return ctx[:3], ctx[3], ctx[4]
    raise SystemExit(f"{trace}: no 'SHOT ctx' + 'SHOT captured file={frame_name}'")


def trace_grade(trace: Path) -> dict:
    """The last 'ARTPREVIEW map grade' line -> the zone_separation grade dict (graph-v2 terms 1 when absent / v1)."""
    grade = None
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        if "ARTPREVIEW map grade profile=" not in line:
            continue
        kv = dict(re.findall(r"(\w+)=(\([^)]*\)|\S+)", line))

        def vec(s):
            return [float(x) for x in s.strip("()").split(",")]
        grade = {"ev": float(kv["nightEV"]), "saturation": float(kv["nightSaturation"]), "lift": float(kv["lift"]),
                 "tint_lin": vec(kv["nightTint"]), "mask_saturation": 1.0, "lift_saturation": 1.0,
                 "mask_inverse_tint_lin": [1.0, 1.0, 1.0]}
        if kv.get("graph") == "v2":
            grade.update(mask_saturation=float(kv["maskSaturation"]), lift_saturation=float(kv["liftSaturation"]),
                         mask_inverse_tint_lin=vec(kv["maskInverseTint"]))
    if grade is None:
        raise SystemExit(f"{trace}: no 'ARTPREVIEW map grade' line")
    return grade


# ------------------------------------------------------------------ map data
class MapData:
    def __init__(self, key: str, derived: Path | None = None):
        self.key = key
        self.topo = json.loads((REPO / f"backend/prisma/fixtures/boards/{key}.topology.json").read_text(encoding="utf-8"))
        self.vec = json.loads((HERE / f"{key}.vector-layer.json").read_text(encoding="utf-8"))
        root = Path(derived) if derived else MAIN_DERIVED
        name = key.capitalize()
        self.bc = np.asarray(Image.open(root / key / f"T_{name}_Map_BC_4K.png").convert("RGB")).astype(np.float64)
        self.mask = np.asarray(Image.open(root / key / f"T_{name}_Map_GameMask_4K.png").convert("L")).astype(np.float64) / 255

    @staticmethod
    def tex_xy(px):
        return np.c_[px[:, 0] / SRC[0] * 4096, px[:, 1] / SRC[1] * 4096]

    @staticmethod
    def world(px):
        return np.c_[(px[:, 0] / SRC[0] - 0.5) * SRC[0] * UU_PER_PX, (px[:, 1] / SRC[1] - 0.5) * SRC[1] * UU_PER_PX,
                     np.zeros(len(px))]

    def bc_at(self, px):
        return bilinear(self.bc, self.tex_xy(px))

    def mask_at(self, px):
        return bilinear(self.mask[..., None], self.tex_xy(px))[:, 0]

    def sectors(self):
        """[(space id, zone, sample px (n,2))] for every circle sector."""
        zone_lab = {z["key"]: lab(hex_rgb(z["color"])[None])[0] for z in self.topo["zones"]}
        r = self.vec["ring"]["r_center_px"]
        painted = {s["id"]: s["painted_px"] for s in self.vec["spaces"]}
        out = []
        for s in self.topo["spaces"]:
            cx, cy = painted[s["id"]]
            zones = s["zones"]
            angs = sorted(d["angle_deg"] % 360 for d in self.vec["dividers"].get(s["id"], []))
            if len(zones) == 1 or len(angs) < 2:
                bounds = [(0.0, 360.0)]
            else:
                bounds = [(angs[i], angs[(i + 1) % len(angs)] + (360 if i + 1 == len(angs) else 0))
                          for i in range(len(angs))]
            secs = []
            for a0, a1 in bounds:
                pad = 8.0 if len(bounds) > 1 else 0.0
                aa = np.radians(np.linspace(a0 + pad, a1 - pad, max(8, int((a1 - a0) / 3))))
                secs.append(np.array([[cx + f * r * math.cos(a), cy + f * r * math.sin(a)]
                                      for f in SECTOR_FRACS for a in aa]))
            cols = [np.median(lab(self.bc_at(p)), axis=0) for p in secs]
            if len(secs) == len(zones):
                best = min(itertools.permutations(zones),
                           key=lambda perm: sum(np.linalg.norm(cols[i] - zone_lab[z]) for i, z in enumerate(perm)))
            else:
                best = [min(zones, key=lambda z: np.linalg.norm(c - zone_lab[z])) for c in cols]
            out += [(s["id"], z, p) for z, p in zip(best, secs)]
        return out

    def adjacent_pairs(self):
        by_id = {s["id"]: s for s in self.topo["spaces"]}
        pairs = set()
        for s in self.topo["spaces"]:
            pairs.update(itertools.combinations(sorted(set(s["zones"])), 2))
            for ln in s["links"]:
                for a in s["zones"]:
                    for b in by_id[ln]["zones"]:
                        if a != b:
                            pairs.add(tuple(sorted((a, b))))
        return sorted(pairs)


def bilinear(img, xy):
    h, w = img.shape[:2]
    x = np.clip(xy[:, 0] - 0.5, 0, w - 1.001)
    y = np.clip(xy[:, 1] - 0.5, 0, h - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return ((img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx) * (1 - fy)
            + (img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx) * fy)


def pair_table(zones: dict, adjacent) -> dict:
    """{'adjacent': {a-b: dE}, 'all': {...}, 'minAdjacent': [pair, dE], 'minAll': [pair, dE]} (dE76)."""
    allp = {f"{a}-{b}": round(float(np.linalg.norm(zones[a] - zones[b])), 1)
            for a, b in itertools.combinations(sorted(zones), 2)}
    adj = {f"{a}-{b}": allp[f"{a}-{b}"] for a, b in adjacent if a in zones and b in zones}
    return {"adjacent": adj, "all": allp, "minAdjacent": list(min(adj.items(), key=lambda t: t[1])) if adj else None,
            "minAll": list(min(allp.items(), key=lambda t: t[1])) if allp else None}


# ------------------------------------------------------------------ measure
def measure(md: MapData, frame: Path, trace: Path) -> dict:
    img = np.asarray(Image.open(frame).convert("RGB")).astype(np.float64)
    pos, pitch, yaw = shot_camera(trace, frame.name)
    cam = Cam(pos, pitch, yaw, img.shape[1], img.shape[0])
    orig, shot = {}, {}
    for _, z, p in md.sectors():
        orig.setdefault(z, []).append(lab(md.bc_at(p)))
        xy = cam.project(md.world(p))
        ok = (xy[:, 0] > 2) & (xy[:, 0] < img.shape[1] - 3) & (xy[:, 1] > 2) & (xy[:, 1] < img.shape[0] - 3)
        if ok.sum() >= 5:
            shot.setdefault(z, []).append(lab(bilinear(img, xy[ok])))
    orig = {z: np.median(np.concatenate(v), axis=0) for z, v in orig.items()}
    shot = {z: np.median(np.concatenate(v), axis=0) for z, v in shot.items()}
    adjacent = md.adjacent_pairs()
    return {"schema": "unmatched.zone-separation/1", "map": md.key, "frameFile": frame.name, "metric": "CIELAB dE76",
            "original": {"zones": {z: [round(float(x), 1) for x in v] for z, v in orig.items()},
                         **pair_table(orig, adjacent)},
            "frame": {"zones": {z: [round(float(x), 1) for x in v] for z, v in shot.items()},
                      **pair_table(shot, adjacent)}}


# ------------------------------------------------------------------ model
def _sat(c, s):
    y = (c @ LUMA)[:, None]
    return np.maximum(y + (c - y) * s, 0)


def _field(w, q):
    X, Y = w[:, 0] / 450.0, w[:, 1] / 290.0
    return np.exp(q[0] * X + q[1] * Y + q[2] * X * X + q[3] * Y * Y + q[4] * X * Y)[:, None]


def model_x(bc_lin, m, g, k, e, w, q):
    """Pre-tonemap linear colour of the map plane (M_MapBoard graph v2 x fitted light)."""
    lit = bc_lin * (2.0 ** g["ev"]) * np.asarray(g["tint_lin"])
    outside = _sat(lit, g["saturation"])
    inside = _sat(lit * np.asarray(g.get("mask_inverse_tint_lin", (1, 1, 1))), g.get("mask_saturation", 1.0))
    base = outside * (1 - m[:, None]) + inside * m[:, None]
    em = e * g["lift"] * _sat(bc_lin, g.get("lift_saturation", 1.0)) * m[:, None]
    return base * np.asarray(k) * _field(w, q) + em


def fit(md: MapData, frame: Path, trace: Path, n=60000, seed=3) -> dict:
    from scipy import optimize
    grade = trace_grade(trace)
    img = np.asarray(Image.open(frame).convert("RGB")).astype(np.float64)
    pos, pitch, yaw = shot_camera(trace, frame.name)
    cam = Cam(pos, pitch, yaw, img.shape[1], img.shape[0])
    rng = np.random.default_rng(seed)
    px = np.c_[rng.uniform(4, SRC[0] - 4, n), rng.uniform(4, SRC[1] - 4, n)]
    w = md.world(px)
    xy = cam.project(w)
    ok = (xy[:, 0] > 2) & (xy[:, 0] < img.shape[1] - 3) & (xy[:, 1] > 2) & (xy[:, 1] < img.shape[0] - 3)
    m = md.mask_at(px)
    ok &= (m < 0.02) | (m > 0.98)
    b = srgb_to_lin(md.bc_at(px[ok]))
    m = np.round(m[ok])
    w = w[ok]
    f8 = bilinear(img, xy[ok])
    target = aces_inv(srgb_to_lin(f8))

    def resid(p):
        return (np.log(model_x(b, m, grade, p[:3], p[3], w, p[4:]) + 0.01) - np.log(target + 0.01)).ravel()
    r = optimize.least_squares(resid, x0=[0.5, 0.5, 0.6, 0.2, 0, 0, 0, 0, 0],
                               bounds=([0, 0, 0, 0, -3, -3, -3, -3, -3], [10, 10, 10, 10, 3, 3, 3, 3, 3]))
    pred = lin_to_srgb8(aces(model_x(b, m, grade, r.x[:3], r.x[3], w, r.x[4:])))
    err = lab(pred) - lab(f8)
    return {"schema": "unmatched.zone-separation-model/1", "map": md.key, "frame": frame.name, "grade": grade,
            "k": [float(x) for x in r.x[:3]], "e": float(r.x[3]), "q": [float(x) for x in r.x[4:]], "n": int(ok.sum()),
            "medianAbsErrLabInside": np.median(np.abs(err[m > 0.5]), 0).round(2).tolist(),
            "medianAbsErrLabOutside": np.median(np.abs(err[m < 0.5]), 0).round(2).tolist()}


def model_summary(md: MapData, model: dict, grade: dict, sectors=None) -> dict:
    """Model zone Lab / pair dE, map luma and circle-outline dL* (fill minus rim line) under a grade."""
    k, e, q = model["k"], model["e"], model["q"]

    def shade(px, m):
        return lab(lin_to_srgb8(aces(model_x(srgb_to_lin(md.bc_at(px)), m, grade, k, e, md.world(px), q))))
    zones = {}
    for _, z, p in sectors if sectors is not None else md.sectors():
        zones.setdefault(z, []).append(shade(p, np.ones(len(p))))
    zones = {z: np.median(np.concatenate(v), axis=0) for z, v in zones.items()}
    rng = np.random.default_rng(11)
    px = np.c_[rng.uniform(4, SRC[0] - 4, 40000), rng.uniform(4, SRC[1] - 4, 40000)]
    y = lin_to_srgb8(aces(model_x(srgb_to_lin(md.bc_at(px)), md.mask_at(px), grade, k, e, md.world(px), q))) @ LUMA
    r = md.vec["ring"]["r_center_px"]
    ang = np.linspace(0, 2 * np.pi, 48, endpoint=False)
    edges = []
    for s in md.vec["spaces"]:
        cx, cy = s["painted_px"]

        def ring(fr):
            p = np.array([[cx + f * r * math.cos(a), cy + f * r * math.sin(a)] for f in fr for a in ang])
            return shade(p, np.ones(len(p)))[:, 0].reshape(len(fr), len(ang))
        edges.append(float(np.median(ring(EDGE_FILL)) - np.median(ring(EDGE_LINE).min(0))))
    return {"zones": zones, "mapLuma": float(y.mean()), "edgeDeltaL": float(np.median(edges))}


def predict(md: MapData, model: dict, measured: dict, grade: dict) -> dict:
    sectors = md.sectors()
    base = model_summary(md, model, model["grade"], sectors)
    new = model_summary(md, model, grade, sectors)
    adjacent = md.adjacent_pairs()
    tb, tn = pair_table(base["zones"], adjacent), pair_table(new["zones"], adjacent)
    est = {p: round(measured["frame"]["all"][p] * tn["all"][p] / tb["all"][p], 1)
           for p in measured["frame"]["all"] if p in tb["all"] and tb["all"][p] > 0}
    adj = {p: est[p] for p in tn["adjacent"] if p in est}
    return {"schema": "unmatched.zone-separation-prediction/1", "map": md.key, "grade": grade,
            "fittedGrade": model["grade"], "estimate": est,
            "minAdjacent": list(min(adj.items(), key=lambda t: t[1])) if adj else None,
            "minAll": list(min(est.items(), key=lambda t: t[1])) if est else None,
            "measuredMinAdjacent": measured["frame"]["minAdjacent"], "measuredMinAll": measured["frame"]["minAll"],
            "mapLumaModelDelta": round(new["mapLuma"] - base["mapLuma"], 2),
            "edgeDeltaLModelDelta": round(new["edgeDeltaL"] - base["edgeDeltaL"], 2),
            "note": "estimate = measured frame dE x model(new grade) / model(fitted grade); a prediction to be measured"}


def profile_grade(key: str) -> dict:
    g = k1_mock.profile_map_grade(key)
    return {k: g[k] for k in ("ev", "saturation", "lift", "tint_lin", "mask_saturation", "lift_saturation",
                              "mask_inverse_tint_lin")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("measure", "fit"):
        s = sub.add_parser(name)
        s.add_argument("map", choices=("marmoreal", "sarpedon"))
        s.add_argument("frame")
        s.add_argument("trace")
        s.add_argument("--derived", default=None)
        s.add_argument("--json" if name == "measure" else "--out", dest="out", default=None)
    s = sub.add_parser("predict")
    s.add_argument("map", choices=("marmoreal", "sarpedon"))
    s.add_argument("--model", required=True)
    s.add_argument("--measured", required=True)
    s.add_argument("--grade-json", default=None, help="grade dict (zone_separation format); default: the profile")
    s.add_argument("--derived", default=None)
    s.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    md = MapData(a.map, a.derived)
    if a.cmd == "measure":
        res = measure(md, Path(a.frame), Path(a.trace))
        print(res["map"], res["frameFile"], "frame minAdjacent", res["frame"]["minAdjacent"],
              "minAll", res["frame"]["minAll"], "| original minAll", res["original"]["minAll"])
    elif a.cmd == "fit":
        res = fit(md, Path(a.frame), Path(a.trace))
        print(json.dumps({k: res[k] for k in ("map", "k", "e", "medianAbsErrLabInside", "medianAbsErrLabOutside")}))
    else:
        grade = json.loads(Path(a.grade_json).read_text(encoding="utf-8")) if a.grade_json else profile_grade(a.map)
        res = predict(md, json.loads(Path(a.model).read_text(encoding="utf-8")),
                      json.loads(Path(a.measured).read_text(encoding="utf-8")), grade)
        print(json.dumps({k: res[k] for k in ("map", "minAdjacent", "minAll", "measuredMinAll", "mapLumaModelDelta",
                                              "edgeDeltaLModelDelta")}))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
