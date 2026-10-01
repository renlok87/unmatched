#!/usr/bin/env python3
"""ENV-MAPS P5c track V: the Niagara fx of the two env layouts - writes ONLY the 'fx' sections.

  python -B art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/p5c_layout_fx.py [--check]
         [--layouts DIR] [--out DIR] [--report]

Idempotent: the 'fx' section of each layout is rebuilt from the layout's CURRENT props (run it after
p5c_layout_props.py of track F: the fx follow the props by id) and replaced in place (inserted before 'notes' the first
time); props, lights, tray, apron, 'ground' and 'notes' are never touched. --check exits 1 when a layout differs from
what this script writes. --out DIR writes the results there instead of over the layouts (scratch validation).
--report writes reports/p5c-fx-layout-report.json (placements, per-board particle estimates).

What goes where (S08EnvLayout.h "fx": anchored entries follow their prop - offset in the prop frame, turned with its
yaw, not scaled, so this script multiplies the measured local offsets by the prop scale):
  Sarpedon   fire-<id>      NS_Env_Campfire      on every SM_Env_Campfire prop (campfire-nw, the W fire basket
                                                 campfire-w) at the ember centroid (p5c_fx_anchor_probe.py)
             flame-<id>     NS_Env_LanternFlame  in every SM_Env_LanternPost glass (lantern-*; emissive-only lanterns,
                                                 no new point light)
             fireflies-*    NS_Env_Fireflies     W forest (2 clusters) and the far beach (river mouth, kept free of
                                                 props), asset colour (warm yellow-green)
  Marmoreal  flame-<id>     NS_Env_LanternFlame  in every lit SM_Env_LanternPlinth (a layout light with the same id)
             petals-<id>    NS_Env_CherryPetals  under the crown of every cherry-* prop (kit SM_Env_Cherry or the Fab
                                                 sakura of track F: crown = mesh bounds centre, lower crown height)
             fireflies-*    NS_Env_Fireflies     the W / E garden beds, warm white override
Rules (checked here, again by S08EnvLayout at spawn): every emitter pivot and its spawn disc (the system's sphere
radius) stay off the painted map (circles / labels readable), nothing in the near band between the map and the K1
camera, anchors are props of the layout, systems are the /Game/EnvKit/FX derivatives of ue_import_fab_fx.py, the
estimated particles per board <= BOARD_PARTICLE_BUDGET (target: a few hundred), fixed seeds (crc32 of map:id) and
fixed warmups -> reproducible -Bench frames. No NoAI pack anywhere (main variant).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
REPO = HERE.parents[4]
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
ANCHORS = RUN / "reports/p5c-fx-anchors.json"
FAB_PICKS = HERE / "fab-picks.json"  # track F (optional): dest path -> pack bounds of the Fab duplicates
REPORT = RUN / "reports/p5c-fx-layout-report.json"
MAP_HALF = (445.66667, 288.66667)  # painted map half extent (1337 x 866 px at 2/3 uu)
FRAME_HALF = (469.66667, 312.66667)  # + the 24 uu wooden frame
CROWN_Z_FRAC = 0.55  # petals start in the lower crown (fraction of the mesh height above its base)
FIRE_WARMUP_S = 1.5  # ~1.5 lifetimes of the 0.8..1.0 s flame particles
PETAL_WARMUP_S = 6.0  # one 4..6 s petal lifetime: the fall column is full
FIREFLY_WARMUP_S = 3.5
NOAI_MARKERS = ("Megaplant_Library", "StyleHex_Studio", "Megaplant", "StyleHex", "Yoshino")

_spec = importlib.util.spec_from_file_location("ue_import_fab_fx", REPO / "tools/art/env_kit/ue_import_fab_fx.py")
FX = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FX)  # type: ignore[union-attr]

# measured by p5c_fx_anchor_probe.py (reports/p5c-fx-anchors.json, UE mesh frame, uu at scale 1); used when the report
# is absent. LanternPost: the glass hangs off the post along local -Y (UE Y = -Blender Y; verify on a K2 frame).
ANCHOR_DEFAULTS = {"SM_Env_LanternPost": [-2.76, -17.49, 48.47], "SM_Env_LanternPlinth": [-0.05, -0.02, 49.41],
                   "SM_Env_Campfire": [3.99, -0.49, 9.07]}
# kit crown meshes (envkit bounds, UE): min / max at scale 1
KIT_BOUNDS = {"SM_Env_Cherry": ([-71.0, -91.8, 0.0], [71.0, 91.8, 180.0]),
              "SM_Env_Tree": ([-72.5, -99.3, 0.0], [72.5, 99.3, 190.0])}
DEFAULT_CROWN_BOUNDS = ([-50.0, -50.0, 0.0], [50.0, 50.0, 150.0])
# fireflies (board space, uu); radius override keeps the spawn disc off the map / frame
FIREFLIES = {
    "sarpedon": [("fireflies-forest-n", (-662.0, -150.0, 50.0), {}),
                 ("fireflies-forest-s", (-650.0, 170.0, 45.0), {}),
                 ("fireflies-beach", (120.0, -425.0, 30.0), {"Sphere Radius": 80.0, "SpawnRate": 4.0})],
    "marmoreal": [("fireflies-garden-w", (-640.0, 150.0, 40.0), {"Color": [4.0, 3.5, 2.0], "SpawnRate": 4.0}),
                  ("fireflies-garden-e", (648.0, 110.0, 40.0), {"Color": [4.0, 3.5, 2.0], "SpawnRate": 4.0})],
}


def leaf(mesh: str) -> str:
    return mesh.rsplit("/", 1)[-1].split(".", 1)[0]


def load_anchors() -> dict:
    if ANCHORS.is_file():
        data = json.loads(ANCHORS.read_text(encoding="utf-8"))
        got = {k: v["glowCentroidUU"] for k, v in data.get("meshes", {}).items() if v.get("glowCentroidUU")}
        return {**ANCHOR_DEFAULTS, **got}
    return dict(ANCHOR_DEFAULTS)


def load_fab_bounds() -> dict:
    """dest leaf name -> (min, max) pack bounds of track F's Fab duplicates (scripts/fab-picks.json)."""
    if not FAB_PICKS.is_file():
        return {}
    meshes = json.loads(FAB_PICKS.read_text(encoding="utf-8")).get("meshes", {})
    return {leaf(e["dest"]): (e["bboxMin"], e["bboxMax"]) for e in meshes.values()
            if e.get("dest") and e.get("bboxMin") and e.get("bboxMax")}


def r2(v: float) -> float:
    return round(float(v), 2)


def seed_of(key: str, fid: str) -> int:
    return zlib.crc32(f"{key}:{fid}".encode("utf-8")) & 0x7FFFFFFF


def fx(key: str, fid: str, system: str, loc, warmup: float, anchor: str | None = None, user: dict | None = None) -> dict:
    e = {"id": fid, "system": f"{FX.FX_ROOT}/{system}"}
    if anchor:
        e["anchor"] = anchor
    e.update({"loc": [r2(loc[0]), r2(loc[1]), r2(loc[2])], "yawDeg": 0.0, "scale": 1.0, "seed": seed_of(key, fid),
              "warmupS": float(warmup)})
    if user:
        e["user"] = user
    return e


def scaled(offset, scale: float) -> list[float]:
    return [offset[0] * scale, offset[1] * scale, offset[2] * scale]


def crown_offset(prop: dict, fab_bounds: dict) -> list[float]:
    name = leaf(prop["mesh"])
    lo, hi = fab_bounds.get(name) or KIT_BOUNDS.get(name) or DEFAULT_CROWN_BOUNDS
    s = float(prop.get("scale", 1.0))
    return [(lo[0] + hi[0]) / 2 * s, (lo[1] + hi[1]) / 2 * s, (lo[2] + CROWN_Z_FRAC * (hi[2] - lo[2])) * s]


def board_xy(prop: dict, offset) -> tuple[float, float, float]:
    """Board-space position of an anchored offset (the C++ FS08EnvFx::Transform)."""
    a = math.radians(float(prop.get("yawDeg", 0.0)))
    x, y, z = offset
    px, py, pz = prop["loc"]
    return px + x * math.cos(a) - y * math.sin(a), py + x * math.sin(a) + y * math.cos(a), pz + z


def build(key: str, layout: dict, anchors: dict, fab_bounds: dict) -> list[dict]:
    props = layout.get("props", [])
    light_ids = {lt.get("id") for lt in layout.get("lights", [])}
    out: list[dict] = []
    for p in props:
        name = leaf(p["mesh"])
        s = float(p.get("scale", 1.0))
        if key == "sarpedon" and name == "SM_Env_Campfire":
            out.append(fx(key, f"fire-{p['id']}", "NS_Env_Campfire", scaled(anchors["SM_Env_Campfire"], s),
                          FIRE_WARMUP_S, p["id"]))
        elif key == "sarpedon" and name == "SM_Env_LanternPost":
            out.append(fx(key, f"flame-{p['id']}", "NS_Env_LanternFlame", scaled(anchors["SM_Env_LanternPost"], s),
                          FIRE_WARMUP_S, p["id"]))
        elif key == "marmoreal" and name == "SM_Env_LanternPlinth" and p["id"] in light_ids:
            out.append(fx(key, f"flame-{p['id']}", "NS_Env_LanternFlame", scaled(anchors["SM_Env_LanternPlinth"], s),
                          FIRE_WARMUP_S, p["id"]))
        elif key == "marmoreal" and p["id"].startswith("cherry"):
            out.append(fx(key, f"petals-{p['id']}", "NS_Env_CherryPetals", crown_offset(p, fab_bounds),
                          PETAL_WARMUP_S, p["id"]))
    for fid, loc, user in FIREFLIES.get(key, []):
        out.append(fx(key, fid, "NS_Env_Fireflies", loc, FIREFLY_WARMUP_S, None, dict(user) or None))
    return out


def spawn_radius(entry: dict) -> float:
    """Spawn disc radius of an fx (the system's Sphere Radius user parameter, else a small flame)."""
    name = entry["system"].rsplit("/", 1)[-1]
    spec = FX.spec_by_name(name) or {}
    user = {**(spec.get("tune", {}).get("user") or {}), **(entry.get("user") or {})}
    return float(user.get("Sphere Radius", 10.0))


def check_fx(key: str, layout: dict, fx_list: list[dict]) -> tuple[list[str], list[str], dict]:
    """(errors, warnings, info) of an fx section against the rules of the docstring."""
    err, warn = [], []
    props = {p["id"]: p for p in layout.get("props", [])}
    ids = set()
    total = 0.0
    per = {}
    for e in fx_list:
        fid = e["id"]
        if fid in ids:
            err.append(f"{key}/{fid}: duplicate fx id")
        ids.add(fid)
        name = e["system"].rsplit("/", 1)[-1]
        if not e["system"].startswith(FX.FX_ROOT + "/") or FX.spec_by_name(name) is None:
            err.append(f"{key}/{fid}: system {e['system']} is not a ue_import_fab_fx.py derivative")
            continue
        if any(m in json.dumps(e) for m in NOAI_MARKERS):
            err.append(f"{key}/{fid}: references a NoAI pack (main variant)")
        if "anchor" in e:
            if e["anchor"] not in props:
                err.append(f"{key}/{fid}: anchor {e['anchor']} is not a prop")
                continue
            x, y, z = board_xy(props[e["anchor"]], e["loc"])
        else:
            x, y, z = e["loc"]
        rad = spawn_radius(e)
        if abs(x) - rad < MAP_HALF[0] and abs(y) - rad < MAP_HALF[1]:
            err.append(f"{key}/{fid}: spawn disc r {rad:.0f} at ({x:.0f}, {y:.0f}) reaches the painted map")
        elif abs(x) - rad < FRAME_HALF[0] and abs(y) - rad < FRAME_HALF[1]:
            warn.append(f"{key}/{fid}: spawn disc r {rad:.0f} at ({x:.0f}, {y:.0f}) reaches the frame band")
        if y > FRAME_HALF[1] and abs(x) < FRAME_HALF[0]:
            err.append(f"{key}/{fid}: in the near band between the map and the K1 camera")
        est = FX.estimate_particles(name, e.get("user"))
        per[fid] = {"system": name, "at": [r2(x), r2(y), r2(z)], "spawnRadius": rad, "particles": round(est, 1)}
        total += est
    if total > FX.BOARD_PARTICLE_BUDGET:
        err.append(f"{key}: ~{total:.0f} particles > {FX.BOARD_PARTICLE_BUDGET} per board")
    elif total > 800:
        warn.append(f"{key}: ~{total:.0f} particles (target a few hundred)")
    return err, warn, {"fx": len(fx_list), "particlesEstimate": round(total, 1), "placements": per}


def apply(key: str, layout: dict, anchors: dict | None = None, fab_bounds: dict | None = None) -> dict:
    new_fx = build(key, layout, anchors if anchors is not None else load_anchors(),
                   fab_bounds if fab_bounds is not None else load_fab_bounds())
    if "fx" in layout:
        out = dict(layout)
        out["fx"] = new_fx
        return out
    out = {}
    for k, v in layout.items():
        if k == "notes":
            out["fx"] = new_fx
        out[k] = v
    if "fx" not in out:
        out["fx"] = new_fx
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--layouts", default=str(LAYOUTS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    anchors, fab_bounds = load_anchors(), load_fab_bounds()
    bad = 0
    report = {"schema": "unmatched.env-fx-layout-report/1", "tool": "p5c_layout_fx.py", "status": "proposed",
              "anchors": {k: v for k, v in anchors.items()}, "boards": {}}
    for key in ("marmoreal", "sarpedon"):
        path = Path(a.layouts) / f"{key}.layout.json"
        old_text = path.read_text(encoding="utf-8")
        layout = json.loads(old_text)
        new = apply(key, layout, anchors, fab_bounds)
        err, warn, info = check_fx(key, new, new["fx"])
        report["boards"][key] = {**info, "errors": err, "warnings": warn}
        for w in warn:
            print(f"  WARN  {w}")
        for e in err:
            print(f"  ERROR {e}")
        bad += 1 if err else 0
        new_text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
        print(f"{key}: {info['fx']} fx, ~{info['particlesEstimate']:.0f} particles")
        if old_text.replace("\r\n", "\n") == new_text:
            print(f"{key}: unchanged")
            if a.check or not a.out:
                continue  # --out still gets a copy, so a scratch run is complete on already-integrated layouts
        if a.check:
            print(f"{key}: differs from p5c_layout_fx.py")
            bad += 1
            continue
        dest = Path(a.out) / f"{key}.layout.json" if a.out else path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(new_text.encode("utf-8"))
        print(f"{key}: written {dest}")
    if a.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_bytes((json.dumps(report, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
