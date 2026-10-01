#!/usr/bin/env python3
"""Validate the perimeter environment layouts of the original-map boards (ENV-MAPS track E, P1b).

Contract: unreal/Unmatched/Config/ArtBoards/EnvLayouts/<map>.layout.json, schema
`unmatched.env-layout/1` (map = marmoreal | sarpedon). CPU only (numpy; PIL for the optional debug
images) - no UE, Blender or GPU.

Board-actor space (uu): origin = map centre, +X right on the K1 screen, +Y towards the K1 camera
(near side), Z up, map plane Z ~ 0 (the image lies at Z = -0.5), stone tray top Z = -3.
The map is 1337 x 866 px at 2/3 uu per px (891.333 x 577.333 uu); the wooden frame adds 24 uu, so
the frame's outer rectangle is |X| <= 469.667, |Y| <= 312.667.

Prop convention (= the processed meshes of tools/art/env_kit/env_kit_build.py, UM_FBX_v1):
- pivot = base centre; the processed mesh already has its target size (KIT below): height unless
  the target says length / diameter (= the longest horizontal extent);
- mesh local axes: +X = FRONT (the Tripo 'front' reference view, glTF +Z), Y = width, Z = up;
- yawDeg = the UE actor yaw about +Z (+yaw turns +X towards +Y). yaw 90 turns the front to the K1
  camera (+Y, near side) with the width along X; 180 faces -X (west), 0 faces +X (east), -90 faces -Y
  (far side);
- scale multiplies the processed mesh uniformly.

Checks (every one is an error unless marked warn):
 1. schema: keys, types, map / boardId, mesh paths /Game/EnvKit/<Kit>/SM_Env_<Name> with Name from
    the fixed set and the kit folder that owns it, unique ids, <= 6 point lights without shadows;
 2. tray / apron: tray.halfX = frameHalfX + max(apron.w, apron.e), tray.halfY = frameHalfY +
    (apron.n + apron.s) / 2, tray.offsetY = (apron.s - apron.n) / 2 (tray centre Y; negative = shifted
    to the far side); the tray IS the one shared stone tray T2 of both maps (TRAY_T2: SM_TableBase_T2 at scale 1,
    ENV-U10 'единая каменная подложка'); every prop's base footprint lies on the tray (LIP_UU inside its edge),
    warn when it reaches into the rocky lip band (RIM_UU inside the edge, where T2 rocks rise up to Z +2);
 3. frame: no prop's full oriented footprint enters the frame rectangle (+ FRAME_GAP_UU), and the axis-aligned
    box of the rotated prop box stays off the map rectangle (= S08EnvLayout.cpp BoxOverlapsMap, the UE
    'intrusions' counter);
 4. near band (Y > frameHalfY, |X| < frameHalfX, i.e. between the map and the camera): props there
    are at most NEAR_MAX_H_UU tall;
 5. base footprints of props do not overlap (tree crowns may; two wall modules - MODULAR - may
    interpenetrate by <= JOINT_TOL_UU at a joint);
 6. occlusion: every prop's oriented bounding box (processed size x scale; tall tops included) is
    projected with the K1 camera model (tools/art/map_surface/k1_mock.py: HFOV 35, pitch -55,
    yaw -90, 1920 x 1080) at the K1 overview D0 = the fit s08_fit_distance(map half extents) (~1872 uu) x the
    board profile's k1DistanceMul (ENV-U9, S08ArtBoardProfiles.json: 1.25 -> ~2340 uu) and every distance the
    mouse wheel can settle on (wheel_zooms: notches of x1.25 clamped to [300 uu, fit / 0.65 = ~2880 uu], i.e. zoom
    0.8125x .. 7.80x of D0, FS08CameraZoomConfig defaults + FS08CameraZoom::MaxDistance) plus 1.2x / 1.6x of D0,
    looking at the board centre and - from 1.2x of D0 on (follow mode, focus = space centre + 28 uu Z, as
    AS08FlowGameMode::UpdateBoardCamera) - at every space. The convex hull of the projected box must
    stay MARGIN_PX (4 px at 1080p) away from every space circle's projected disk (radius =
    spaceRadiusPx + 0.5 px painted ring). A prop point above the ground whose projection falls inside a
    circle's disk is always in front of that circle, so screen overlap = occlusion;
 7. shadows: the key light of the art profiles (k1_mock.KEY_LIGHT_ROT = (-55, 30, 0), travelling
    towards +X / +Y) projects every castShadow prop's box onto Z = 0; the shadow must not touch any
    space circle (warn below SHADOW_WARN_UU);
 8. warn: 10..48 props (PROPS_RANGE); tall props (> TALL_H_UU) in the near half (Y > 0) whose footprint reaches the frame's X
    columns (+ TALL_SIDE_UU; a tall prop wholly beside the frame leans outwards in the K1 perspective and check 6
    measures it exactly); crowns overhanging the tray edge by > 60 uu; lights inside the frame rectangle or off the tray.
 9. ground (ENV-U10, optional section - warn when absent; validate_ground, = S08EnvGround.cpp): mode 'runtime',
    material /Game/EnvKit/Ground/MI_EnvGround_<Kit>, z in (-3, -0.5), frameOverlapUU in [0, 20], insetUU in
    [0, 200], splatRect [minX, minY, maxX, maxY] covering the tray top - inset, the tray top minus the frame hole =
    4 strips (S08EnvGround::Strips), and the splat PNG (tools/art/env_kit/ground_splat.py) present with the
    recorded splatSha256.
10. K1 framing (P4, concept review gap 4): every prop of K1_FRAMED[<map>] has its whole oriented box inside the K1
    overview frame (D0, 1920 x 1080, >= K1_FRAME_MARGIN_PX from the edge); every prop's in-frame share of its projected
    box is reported (column 'K1 in frame', * = K1_FRAMED).

Usage:
  python -B tools/art/env_kit/layout_check.py                       # both maps, text report
  python -B tools/art/env_kit/layout_check.py --maps sarpedon --images C:/tmp/envmaps-research/p1b/layout
  python -B tools/art/env_kit/layout_check.py --json report.json
  python -B tools/art/env_kit/layout_check.py --selftest            # synthetic cases (27)
Prop sizes come from the env kit build reports (--build-reports, reports/assets/SM_Env_<Name>.build.json:
UE X = depth, Y = width, Z = height; the P5 props from EXTRA_BUILD_REPORTS, the Blender back-wall modules from the
lane-K build report BACKWALL_REPORT) when present, else from the KIT table; the run prints whether they agree.
Debug images (--images DIR, CPU / PIL only): <map>-top.png (orthographic top view, footprints, lights,
K1 / zoom-out ground frusta) and <map>-k1.png (K1 overview, D0), plus <map>-out.png (the zoom-out limit
fit / 0.65) and <map>-wide.png (the concept camera, fit x 1.45). They draw the flat map illustration (out of git, ENV-U3:
--map-images) and, when the Tripo source GLBs are present (--glb-dir, out of git), flat-shaded
previews of the real meshes; otherwise shaded boxes. Exit code 1 on any error.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/art/map_surface"))
import k1_mock  # noqa: E402  (HFOV 35 / pitch -55 / yaw -90 pinhole, s08_fit_distance)

MAIN = Path("C:/Users/ren/WebstormProjects/unmached/unmached")  # main checkout (out-of-git inputs)
SCHEMA = "unmatched.env-layout/1"
MAPS = {"marmoreal": {"boardId": "c121b47f8d6eb28daccb76d05", "kit": "Marmoreal"},
        "sarpedon": {"boardId": "c7fa64a26c29a0835f2383e63", "kit": "Sarpedon"}}
SRC_W, SRC_H, UU_PER_PX = 1337, 866, 2.0 / 3.0
MAP_HX, MAP_HY = SRC_W * UU_PER_PX / 2, SRC_H * UU_PER_PX / 2  # 445.667 x 288.667
FRAME_UU = 24.0
FRAME_HX, FRAME_HY = MAP_HX + FRAME_UU, MAP_HY + FRAME_UU  # 469.667 x 312.667
TRAY_TOP_Z = -3.0
RING_EXTRA_PX = 0.5          # painted ring outer edge 63.43 px vs spaceRadiusPx 63
MARGIN_PX = 4.0              # clearance around every circle at 1080p
SCREEN = (1920, 1080)
# FS08CameraZoomConfig defaults (S08ArtHud.h): D0 = the K1 overview = fit x k1DistanceMul (ENV-U9, read from the board
# profile), farthest = max(D0, fit / OverviewOutRatio) (the far limit stays with the fit: 2880 uu = 0.8125x of the map
# boards' 2340 uu D0), nearest = MinDistanceUU (absolute), one wheel notch = x / WheelStepFactor, follow-selection
# from FollowFromZoom of D0. The wheel steps are computed in camera_set().
ZOOM_OUT = 0.65              # OverviewOutRatio (of the fit)
WHEEL_STEP = 1.25            # WheelStepFactor
MIN_DIST_UU = 300.0          # MinDistanceUU
FOLLOW_FROM = 1.2            # FollowFromZoom
ZOOMS_FIXED = (1.2, 1.6)     # the follow threshold and the 03 §2 K2 zoom (FocusZoom), besides the wheel steps
FOLLOW_Z = 28.0              # UpdateBoardCamera: focus = CellToWorld + (0, 0, 28)
NEAR_UU = 10.0               # UE near clip plane (GNearClippingPlane): nothing nearer to the camera is drawn
LIP_UU = 8.0                 # base footprint stays this far inside the tray edge
# ENV-U10 (track TRAY, 2026-10-01): the ONE shared stone tray of both map boards = the flat top of SM_TableBase_T2
# (art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2, placed at scale 1 at (0, offsetY); the ground
# track reads the same numbers from C:/tmp/envmaps-research/p2/tray-extents.json). Both layouts carry exactly this.
TRAY_T2 = {"halfX": 780.0, "halfY": 470.0, "offsetY": -45.0}
RIM_UU = 20.0                # rocky lip band of T2 inside the tray edge (rock tops up to Z +2 there): warn for props
FRAME_GAP_UU = 2.0
NEAR_MAX_H_UU = 25.0
TALL_H_UU = 120.0
TALL_SIDE_UU = 60.0          # 8.: a near-half tall prop warns only when its footprint reaches |X| < FRAME_HX + this
# 10. props whose whole box must lie in the K1 overview frame (concept review gap 4: the Sarpedon hull read as a sliver
# in the top-right corner of K1)
K1_FRAMED = {"sarpedon": ("hull-e1", "hull-e2")}
K1_FRAME_MARGIN_PX = 0.0
MAX_POINT_LIGHTS = 6
# P5 track A (2026-10-01): 28 -> 48 (WARN guide only; every error rule is unchanged). P5 dresses both maps with the new
# small props of concept-review gaps 4 / 6 / 7 / 12: Marmoreal 21 -> 41 (5 back-wall modules, 12 balustrade segments,
# 3 hedge beds), Sarpedon 24 -> 42 (8 barrels / crates, 3 lantern posts, 2 banners, 5 rock outcrops). The new meshes
# are 4.3k-7.8k triangles (back wall 9.4k-9.7k), no collision, no new light; the environment cost has to be re-measured
# with tools/art/render/render_bench.py at the next packaged run (not done in this CREATE stage).
# P4 (2026-10-01): 18 -> 28. The P3 packaged bench (docs/game-design/evidence/ENV-MAPS/p3-packaged-2026-10-01/bench)
# measured the whole environment at +0.4-0.46 ms GPU at K1, mostly the point lights and Lumen; the props are decor
# meshes of <= 12k triangles without collision, so a few more instances stay far inside the budget (perf was NOT
# re-measured in P4: re-measure with tools/art/render/render_bench.py at the next packaged run).
PROPS_RANGE = (10, 48)
CROWN_OVERHANG_WARN_UU = 60.0
SHADOW_WARN_UU = 10.0
MODULAR = {"ArcadeBay", "Portal", "Palisade", "Hull", "Balustrade",  # wall modules may interpenetrate at a joint
           "BackWall_BayDoor", "BackWall_BayWindows", "BackWall_Centre"}
JOINT_TOL_UU = 8.0

# name -> (kit folder, Tripo asset, GLB extent (x width, y up, z depth=front), target (kind, uu),
#          base footprint fraction of (w, d) or None = the whole box)
# Extents: POSITION min/max of art/pipeline-candidates/ASSET-ENV-KIT-001/20260930-tripo-h31/source/*.glb
# (base at y = 0, centred in x / z). Targets: the P1 proposal (uu = cm).
KIT = {
    "ArcadeBay": ("Marmoreal", "ENV-M-ARCADE-BAY", (0.7893, 0.9765, 0.2312), ("height", 130.0), None),
    "Portal": ("Marmoreal", "ENV-M-PORTAL", (0.8373, 0.9791, 0.3238), ("height", 150.0), None),
    "Cherry": ("Marmoreal", "ENV-M-CHERRY", (0.9779, 0.9588, 0.7559), ("height", 180.0), (0.40, 0.40)),
    "PlinthBall": ("Marmoreal", "ENV-M-PLINTH-BALL", (0.4190, 0.9778, 0.4190), ("height", 60.0), None),
    "LanternPlinth": ("Marmoreal", "ENV-M-LANTERN-PLINTH", (0.3515, 0.9816, 0.3515), ("height", 70.0), None),
    "Urn": ("Marmoreal", "ENV-M-URN", (0.9541, 0.9731, 0.6570), ("height", 35.0), (0.55, 0.60)),
    "Cypress": ("Marmoreal", "ENV-M-CYPRESS", (0.3122, 0.9787, 0.2816), ("height", 110.0), (0.60, 0.60)),
    "FortRuin": ("Sarpedon", "ENV-S-FORT-RUIN", (0.9787, 0.6569, 0.3045), ("height", 110.0), None),
    "Tree": ("Sarpedon", "ENV-S-TREE", (0.9773, 0.9353, 0.7134), ("height", 190.0), (0.40, 0.40)),
    "Hull": ("Sarpedon", "ENV-S-HULL", (0.9770, 0.8349, 0.2092), ("length", 300.0), None),
    "Cannon": ("Sarpedon", "ENV-S-CANNON", (0.6842, 0.5807, 0.9735), ("length", 45.0), None),
    "Campfire": ("Sarpedon", "ENV-S-CAMPFIRE", (0.9741, 0.4114, 0.9779), ("diameter", 40.0), None),
    "Palisade": ("Sarpedon", "ENV-S-PALISADE", (0.9770, 0.9426, 0.1969), ("height", 70.0), None),
    "Rope": ("Sarpedon", "ENV-S-ROPE", (0.9789, 0.4655, 0.9483), ("diameter", 22.0), None),
    # P5 (art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5/source/*.glb; ENV-M-CHERRY-V2 not used: ENV-U13)
    "Barrel": ("Sarpedon", "ENV-S-BARREL", (0.7480, 0.9776, 0.7480), ("height", 28.0), None),
    "CrateStack": ("Sarpedon", "ENV-S-CRATE-STACK", (0.9779, 0.8937, 0.4382), ("height", 45.0), None),
    "LanternPost": ("Sarpedon", "ENV-S-LANTERN-POST", (0.5832, 0.9771, 0.2581), ("height", 95.0), None),
    "Banner": ("Sarpedon", "ENV-S-BANNER", (0.4643, 0.9764, 0.1586), ("height", 120.0), None),
    "RockOutcrop": ("Sarpedon", "ENV-S-ROCK-OUTCROP", (0.9783, 0.8501, 0.7448), ("height", 70.0), None),
    "Balustrade": ("Marmoreal", "ENV-M-BALUSTRADE", (0.9795, 0.3009, 0.0939), ("length", 150.0), None),
    "HedgeBed": ("Marmoreal", "ENV-M-HEDGE-BED", (0.9782, 0.2967, 0.1742), ("length", 150.0), None),
    # Blender lane K (ASSET-ENV-M-BACKWALL-001, no GLB): extents = the module bounds in uu (width, height, depth), so the
    # target height gives scale 1; the pivot is the back face, see LOCAL_CENTRE_X
    "BackWall_BayDoor": ("Marmoreal", "ENV-M-BACKWALL", (152.3, 235.0, 30.792), ("height", 235.0), None),
    "BackWall_BayWindows": ("Marmoreal", "ENV-M-BACKWALL", (152.3, 235.0, 30.792), ("height", 235.0), None),
    "BackWall_Centre": ("Marmoreal", "ENV-M-BACKWALL", (186.0, 255.0, 25.345), ("height", 255.0), None),
}
# local X (depth, front = +X) of the bounds centre at scale 1 when the pivot is not the base centre: the back-wall
# modules span x -16 .. +14.792 (bays) / +9.345 (centre) (lane-K build report boundsUeLocalUU)
LOCAL_CENTRE_X = {"BackWall_BayDoor": -0.604, "BackWall_BayWindows": -0.604, "BackWall_Centre": -3.3275}
BUILD_REPORTS = ROOT / "art/pipeline-candidates/ASSET-ENV-KIT-001/20260930-tripo-h31/reports/assets"
P5_RUN = ROOT / "art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5"
EXTRA_BUILD_REPORTS = (P5_RUN / "reports/assets",)  # searched after --build-reports for SM_Env_<Name>.build.json
BACKWALL_REPORT = ROOT / "art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/20261001-backwall-v1/reports/build-report.json"
GLB_DIR_OF = {n: P5_RUN / "source" for n in ("Barrel", "CrateStack", "LanternPost", "Banner", "RockOutcrop",
                                             "Balustrade", "HedgeBed")}  # debug-image meshes (out of git)
PROCESSED: dict[str, tuple[float, float, float]] = {}  # name -> (w, d, h) at scale 1 from the build reports
TURNS: dict[str, float] = {}  # name -> yaw the processing track applied to the raw mesh (.blend +Z, deg)
MESH_RE = re.compile(r"^/Game/EnvKit/(Marmoreal|Sarpedon)/SM_Env_([A-Za-z]+(?:_[A-Za-z]+)?)$")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


# ------------------------------------------------------------------ geometry
def dims(name: str, scale: float = 1.0) -> tuple[float, float, float]:
    """Processed size (w = width along local Y, d = depth along local X = front, h) x scale, uu: from the
    processing track's build report when loaded (kit_crosscheck), else from the KIT table."""
    if name in PROCESSED:
        return tuple(v * scale for v in PROCESSED[name])
    _, _, (ex, ey, ez), (kind, val), _ = KIT[name]
    ref = ey if kind == "height" else max(ex, ez)
    k = val / ref * scale
    return ex * k, ez * k, ey * k


def _rot(yaw_deg: float) -> np.ndarray:
    a = math.radians(yaw_deg)
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


def footprint(p: dict, base: bool = False) -> np.ndarray:
    """Oriented footprint (4, 2) in board XY; base=True uses the base fraction (tree trunks)."""
    name = mesh_name(p)
    w, d, _ = dims(name, p["scale"])
    frac = KIT[name][4] if base else None
    if frac:
        w, d = w * frac[0], d * frac[1]
    loc = np.array(p["loc"][:2], float)
    c = np.array([[-d / 2, -w / 2], [d / 2, -w / 2], [d / 2, w / 2], [-d / 2, w / 2]])  # local X = depth
    c[:, 0] += LOCAL_CENTRE_X.get(name, 0.0) * p["scale"]  # pivot off the bounds centre (back-wall modules)
    return c @ _rot(p["yawDeg"]).T + loc


def box_corners(p: dict) -> np.ndarray:
    """8 corners (8, 3) of the prop's oriented bounding box in board space."""
    _, _, h = dims(mesh_name(p), p["scale"])
    fp = footprint(p)
    z0 = float(p["loc"][2])
    return np.vstack([np.c_[fp, np.full(4, z0)], np.c_[fp, np.full(4, z0 + h)]])


def mesh_name(p: dict) -> str:
    m = MESH_RE.match(p.get("mesh", ""))
    return m.group(2) if m else ""


def convex_hull(pts: np.ndarray) -> np.ndarray:
    """Monotone chain, CCW in a y-up sense (orientation is irrelevant for the tests below)."""
    P = sorted(set(map(tuple, np.round(pts, 6))))
    if len(P) <= 2:
        return np.array(P)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for q in P:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0:
            lo.pop()
        lo.append(q)
    for q in reversed(P):
        while len(up) >= 2 and cross(up[-2], up[-1], q) <= 0:
            up.pop()
        up.append(q)
    return np.array(lo[:-1] + up[:-1])


def _axes(poly: np.ndarray) -> np.ndarray:
    e = np.roll(poly, -1, axis=0) - poly
    n = np.c_[-e[:, 1], e[:, 0]]
    ln = np.linalg.norm(n, axis=1)
    return n[ln > 1e-9] / ln[ln > 1e-9, None]


def _seg_dist(pts: np.ndarray, poly: np.ndarray) -> float:
    a, b = poly, np.roll(poly, -1, axis=0)
    ab = b - a
    ap = pts[:, None, :] - a[None]
    t = np.clip((ap * ab[None]).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-12)[None], 0, 1)
    q = a[None] + t[..., None] * ab[None]
    return float(np.sqrt(((pts[:, None, :] - q) ** 2).sum(-1)).min())


def poly_clearance(A: np.ndarray, B: np.ndarray) -> float:
    """Signed clearance between two convex polygons: distance if disjoint, else -penetration (SAT)."""
    best_pen = math.inf
    for ax in np.vstack([_axes(A), _axes(B)]):
        pa, pb = A @ ax, B @ ax
        gap = max(pb.min() - pa.max(), pa.min() - pb.max())
        if gap > 0:
            return min(_seg_dist(A, B), _seg_dist(B, A))
        best_pen = min(best_pen, -gap)
    return -best_pen


def rects_overlap(A: np.ndarray, B: np.ndarray, eps: float = 0.0) -> bool:
    return poly_clearance(A, B) < -eps


def kit_crosscheck(reports_dir: Path | None) -> list[str]:
    """Load the processed sizes (UE X = depth, Y = width, Z = height) and applied turns from
    reports/assets/SM_Env_<Name>.build.json of tools/art/env_kit/env_kit_build.py and compare with KIT."""
    PROCESSED.clear()
    TURNS.clear()
    if not reports_dir or not Path(reports_dir).exists():
        return [f"kit: no build reports at {reports_dir} - sizes from the KIT table (GLB bounds x target)"]
    msgs, ok = [], 0
    backwall = {}
    if BACKWALL_REPORT.is_file():  # the lane-K report: exports[].boundsUeLocalUU.size = (X depth, Y width, Z height)
        bw = json.loads(BACKWALL_REPORT.read_text(encoding="utf-8"))
        backwall = {ex["name"][len("SM_Env_"):]: ex["boundsUeLocalUU"]["size"] for ex in bw.get("exports", [])}
    for name in KIT:
        f = next((d / f"SM_Env_{name}.build.json" for d in (Path(reports_dir), *EXTRA_BUILD_REPORTS)
                  if (d / f"SM_Env_{name}.build.json").exists()), Path(reports_dir) / f"SM_Env_{name}.build.json")
        if name in backwall:
            b = {"scale_pivot": {"dimensions_uu_ue_xyz": backwall[name]}}
        elif not f.exists():
            msgs.append(f"kit: {f.name} missing - KIT table size used")
            continue
        else:
            b = json.loads(f.read_text(encoding="utf-8"))
        X, Y, Z = (float(v) for v in b["scale_pivot"]["dimensions_uu_ue_xyz"])
        want = dims(name, 1.0)
        PROCESSED[name] = (Y, X, Z)
        TURNS[name] = float(b.get("orientation", {}).get("yaw_deg_about_plus_z_applied", 0.0))
        bad = [f"{a} {got:.1f} vs KIT {exp:.1f}" for a, got, exp in (("width Y", Y, want[0]), ("depth X", X, want[1]),
                                                                     ("height Z", Z, want[2]))
               if abs(got - exp) > 0.01 * max(exp, 1.0)]
        if TURNS[name]:
            bad.append(f"raw mesh turned {TURNS[name]:+.0f} deg")
        if bad:
            msgs.append(f"kit: SM_Env_{name}: {'; '.join(bad)} (the build report wins)")
        else:
            ok += 1
    msgs.insert(0, f"kit: {ok}/{len(KIT)} build reports equal the KIT sizes (1 %) and keep the Tripo front "
                   f"({Path(reports_dir).as_posix()})")
    return msgs


# ------------------------------------------------------------------ cameras
def make_camera(distance: float, focus=(0.0, 0.0, 0.0), size=SCREEN) -> k1_mock.Camera:
    """k1_mock.Camera looking at `focus` (UpdateBoardCamera: location = focus + (0, D cos55, D sin55))."""
    cam = k1_mock.Camera(distance, *size)
    cam.pos = cam.pos + np.asarray(focus, float)
    return cam


def clip_front(cam: k1_mock.Camera, pts: np.ndarray, closed: bool = False) -> np.ndarray:
    """The part of a convex point set in front of the near plane (depth >= NEAR_UU), so that the pinhole projection
    stays valid at the close wheel zooms (D down to 300 uu: props and circles on the near side end up behind the
    camera). closed=True: `pts` is an ordered planar polygon (Sutherland-Hodgman, order kept); otherwise the vertices
    of a convex solid (front vertices + the crossing of every front / behind pair; their hull is the clipped solid).
    Returns (0, 3) when everything is behind the camera."""
    depth = (pts - cam.pos) @ cam.fwd - NEAR_UU
    if (depth >= 0).all():
        return pts
    if closed:
        out = []
        for i in range(len(pts)):
            j = (i + 1) % len(pts)
            if depth[i] >= 0:
                out.append(pts[i])
            if (depth[i] >= 0) != (depth[j] >= 0):
                out.append(pts[i] + (pts[j] - pts[i]) * (depth[i] / (depth[i] - depth[j])))
        return np.array(out, float).reshape(-1, 3)
    front, dfront = pts[depth >= 0], depth[depth >= 0]
    back, dback = pts[depth < 0], depth[depth < 0]
    cross = [f + (b - f) * (a / (a - c)) for f, a in zip(front, dfront) for b, c in zip(back, dback)]
    return np.vstack([front, *cross]) if cross else front.reshape(-1, 3)


def k1_rig(board_id: str) -> tuple[float, float, float]:
    """(fit, D0, far) of a map board's camera rig (AS08FlowGameMode::SetupCameraForBoard + FS08CameraZoom): the fit
    s08_fit_distance of the map canvas (~1872.2 uu), the K1 overview D0 = fit x the board profile's k1DistanceMul
    (ENV-U9, S08ArtBoardProfiles.json via k1_mock.k1_distance_mul: 1.25 -> ~2340.2 uu) and the far wheel limit
    max(D0, fit / ZOOM_OUT) (~2880.2 uu = 0.8125x of D0: the far limit stays with the fit)."""
    fit = k1_mock.s08_fit_distance(MAP_HX, MAP_HY)
    d0 = k1_mock.s08_overview_distance(MAP_HX, MAP_HY, k1_mock.k1_distance_mul(board_id))
    return fit, d0, max(d0, fit / ZOOM_OUT)


def layout_board_id(layout: dict) -> str:
    """The board id the game plays this layout on (MAPS; the layout's own boardId is checked by validate())."""
    return MAPS.get(layout.get("map"), {}).get("boardId") or layout.get("boardId", "")


def wheel_zooms(d0: float, far: float | None = None) -> list[float]:
    """Every zoom (D0 / D) the wheel can settle on. FS08CameraZoom::Wheel divides / multiplies the TARGET distance
    by WHEEL_STEP and clamps it to [min(MIN_DIST_UU, D0), far] (far = FS08CameraZoom::MaxDistance, default
    D0 / ZOOM_OUT = the rig with D0 = the fit), so the settled distances are the closure of D0 under those two moves:
    D0 * 1.25^k and, after hitting a limit, MinDistance * 1.25^m / far / 1.25^n (Marmoreal / Sarpedon, ENV-U9
    D0 = 2340.2, far = 2880.2: 1.25 (= the fit) .. 7.45 and 7.80 = D0 / 300 from the overview, 0.8125 out, plus both
    clamp lattices; the settle distances are the same set as before ENV-U9, only D0 moved one notch out)."""
    lo, hi = min(MIN_DIST_UU, d0), (d0 / ZOOM_OUT if far is None else far)
    seen: dict[float, float] = {}
    todo = [d0]
    while todo:
        d = todo.pop()
        if round(d, 3) in seen:
            continue
        seen[round(d, 3)] = d
        todo += [min(max(d / WHEEL_STEP, lo), hi), min(max(d * WHEEL_STEP, lo), hi)]
    return sorted({round(d0 / d, 4) for d in seen.values()})


def camera_set(spaces: list[dict], board_id: str) -> list[tuple[str, float, tuple]]:
    """K1 (D0 of k1_rig), every wheel zoom (centred) and ZOOMS_FIXED, all as zooms of D0; from FOLLOW_FROM x D0 on
    also following every space."""
    _, d0, far = k1_rig(board_id)
    out = []
    for z in sorted(set(wheel_zooms(d0, far)) | set(ZOOMS_FIXED)):
        if z == 1.0:
            out.append(("K1", d0, (0.0, 0.0, 0.0)))
            continue
        if z < 1.0:
            out.append((f"out{z:g}", d0 / z, (0.0, 0.0, 0.0)))
            continue
        out.append((f"in{z:g}@centre", d0 / z, (0.0, 0.0, 0.0)))
        if z < FOLLOW_FROM - 1e-6:
            continue
        for s in spaces:
            fx = min(max(s["X"], -MAP_HX), MAP_HX)
            fy = min(max(s["Y"], -MAP_HY), MAP_HY)
            out.append((f"in{z}@{s['id']}", d0 / z, (fx, fy, FOLLOW_Z)))
    return out


def load_spaces(topo: dict) -> list[dict]:
    uu = float(topo["uuPerPx"])
    r = (float(topo["spaceRadiusPx"]) + RING_EXTRA_PX) * uu
    out = []
    for s in topo["spaces"]:
        x, y = s["layout"]["x"], s["layout"]["y"]
        out.append({"id": s["id"], "X": (x / SRC_W - 0.5) * 2 * MAP_HX, "Y": (y / SRC_H - 0.5) * 2 * MAP_HY,
                    "R": r, "zones": s["zones"], "start": s.get("start")})
    return out


def circle_pts(s: dict, n: int = 48) -> np.ndarray:
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.c_[s["X"] + s["R"] * np.cos(a), s["Y"] + s["R"] * np.sin(a), np.zeros(n)]


def occlusion(layout: dict, spaces: list[dict]) -> dict:
    """Per prop: worst (minimum) screen clearance in px over all cameras and circles."""
    props = layout["props"]
    boxes = [box_corners(p) for p in props]
    circ = [circle_pts(s) for s in spaces]
    worst = {p["id"]: {"px": math.inf, "camera": "", "space": ""} for p in props}
    for label, dist, focus in camera_set(spaces, layout_board_id(layout)):
        cam = make_camera(dist, focus)
        vis, cpolys = [], []  # circles (partly) in front of the camera; the rest cannot be covered
        for i, c in enumerate(circ):
            f = clip_front(cam, c, closed=True)
            if len(f) >= 3:
                vis.append(i)
                cpolys.append(cam.project(f))
        if not vis:
            continue
        cbb = np.array([[c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()] for c in cpolys])
        for p, b in zip(props, boxes):
            f = clip_front(cam, b)
            if len(f) < 3:
                continue  # entirely behind the camera
            hull = convex_hull(cam.project(f))
            bb = np.array([hull[:, 0].min(), hull[:, 1].min(), hull[:, 0].max(), hull[:, 1].max()])
            gx = np.maximum(0, np.maximum(cbb[:, 0] - bb[2], bb[0] - cbb[:, 2]))
            gy = np.maximum(0, np.maximum(cbb[:, 1] - bb[3], bb[1] - cbb[:, 3]))
            gap = np.hypot(gx, gy)  # lower bound of the exact clearance
            w = worst[p["id"]]
            for k in np.argsort(gap):
                if gap[k] >= w["px"]:
                    break
                c = poly_clearance(hull, cpolys[k])
                if c < w["px"]:
                    w.update(px=c, camera=label, space=spaces[vis[k]]["id"])
    return worst


# ------------------------------------------------------------------ validation
def validate(layout: dict, key: str, spaces: list[dict]) -> tuple[list[str], list[str], dict]:
    """Schema and geometry checks 1-5, 7. info['parsed'] is True when every prop parsed (occlusion can run)."""
    err, warn = [], []
    info: dict = {"props": {}, "lights": len(layout.get("lights", [])), "parsed": False}
    need = {"schema": str, "map": str, "boardId": str, "tray": dict, "apron": dict, "props": list,
            "lights": list, "notes": str}
    for k, t in need.items():
        if not isinstance(layout.get(k), t):
            err.append(f"key '{k}' missing or not {t.__name__}")
    extra = set(layout) - set(need) - {"ground"}  # 'ground' is optional (check 9, validate_ground)
    if extra:
        warn.append(f"unknown top-level keys {sorted(extra)}")
    if err:
        return err, warn, info
    if layout["schema"] != SCHEMA:
        err.append(f"schema {layout['schema']!r} != {SCHEMA!r}")
    if layout["map"] != key:
        err.append(f"map {layout['map']!r} != {key!r}")
    if layout["boardId"] != MAPS[key]["boardId"]:
        err.append(f"boardId {layout['boardId']!r} != {MAPS[key]['boardId']!r}")

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    tray, apron = layout["tray"], layout["apron"]
    for k in ("halfX", "halfY", "offsetY"):
        if not num(tray.get(k)):
            err.append(f"tray.{k} missing / not a number")
    for k in ("n", "s", "w", "e"):
        if not num(apron.get(k)) or apron.get(k) < 0:
            err.append(f"apron.{k} missing / negative")
    if err:
        return err, warn, info
    want = {"halfX": FRAME_HX + max(apron["w"], apron["e"]),
            "halfY": FRAME_HY + (apron["n"] + apron["s"]) / 2, "offsetY": (apron["s"] - apron["n"]) / 2}
    for k, v in want.items():
        if abs(tray[k] - v) > 0.5:
            err.append(f"tray.{k} = {tray[k]} but the apron gives {v:.2f}")
    if apron["w"] != apron["e"]:
        warn.append("apron w != e: the tray has no X offset, the narrower side gets the extra stone")
    off_t2 = {k: tray[k] for k, v in TRAY_T2.items() if abs(tray[k] - v) > 0.5}
    if off_t2:
        err.append(f"tray {off_t2} is not the shared T2 tray {TRAY_T2} (ENV-U10: one stone tray SM_TableBase_T2 "
                   f"for both maps, placed at scale 1 - a different tray would need a stretch)")
    t_x0, t_x1 = -tray["halfX"], tray["halfX"]
    t_y0, t_y1 = tray["offsetY"] - tray["halfY"], tray["offsetY"] + tray["halfY"]
    info["tray"] = {"x": [round(t_x0, 2), round(t_x1, 2)], "y": [round(t_y0, 2), round(t_y1, 2)]}

    ids, props = set(), layout["props"]
    gx, gy = FRAME_HX + FRAME_GAP_UU, FRAME_HY + FRAME_GAP_UU
    frame = np.array([[-gx, -gy], [gx, -gy], [gx, gy], [-gx, gy]])
    near = np.array([[-FRAME_HX, FRAME_HY], [FRAME_HX, FRAME_HY], [FRAME_HX, t_y1 + 1e3], [-FRAME_HX, t_y1 + 1e3]])
    ok_props = []
    for i, p in enumerate(props):
        pid = p.get("id", f"#{i}")
        if not isinstance(p.get("id"), str) or not p["id"]:
            err.append(f"prop #{i}: id missing")
        elif pid in ids:
            err.append(f"prop {pid}: duplicate id")
        ids.add(pid)
        m = MESH_RE.match(p.get("mesh", "") if isinstance(p.get("mesh"), str) else "")
        if not m or m.group(2) not in KIT:
            err.append(f"prop {pid}: mesh {p.get('mesh')!r} is not /Game/EnvKit/<Kit>/SM_Env_<Name> of the kit")
            continue
        if KIT[m.group(2)][0] != m.group(1):
            err.append(f"prop {pid}: SM_Env_{m.group(2)} lives in /Game/EnvKit/{KIT[m.group(2)][0]}/, not {m.group(1)}")
            continue
        if m.group(1) != MAPS[key]["kit"]:
            warn.append(f"prop {pid}: uses the {m.group(1)} kit on {key}")
        if not (isinstance(p.get("loc"), list) and len(p["loc"]) == 3 and all(num(v) for v in p["loc"])):
            err.append(f"prop {pid}: loc must be [x, y, z]")
            continue
        if not num(p.get("yawDeg")):
            err.append(f"prop {pid}: yawDeg missing")
            continue
        if not num(p.get("scale")) or not (0.2 <= p["scale"] <= 3.0):
            err.append(f"prop {pid}: scale must be a number in 0.2..3")
            continue
        if not isinstance(p.get("castShadow"), bool):
            err.append(f"prop {pid}: castShadow must be a bool")
        if abs(p["loc"][2] - TRAY_TOP_Z) > 0.01:
            warn.append(f"prop {pid}: z {p['loc'][2]} is not the tray top {TRAY_TOP_Z}")
        ok_props.append(p)
        w, d, h = dims(m.group(2), p["scale"])
        full, base = footprint(p), footprint(p, base=True)
        info["props"][pid] = {"mesh": m.group(2), "size_uu": [round(w, 1), round(d, 1), round(h, 1)]}
        # 2. on the tray
        bx0, by0 = base.min(0)
        bx1, by1 = base.max(0)
        edge_gap = min(bx0 - t_x0, t_x1 - bx1, by0 - t_y0, t_y1 - by1)
        info["props"][pid]["edge_gap_uu"] = round(edge_gap, 1)
        if edge_gap < LIP_UU:
            err.append(f"prop {pid}: base footprint x[{bx0:.0f},{bx1:.0f}] y[{by0:.0f},{by1:.0f}] leaves the tray "
                       f"x[{t_x0:.0f},{t_x1:.0f}] y[{t_y0:.0f},{t_y1:.0f}] (lip {LIP_UU})")
        elif edge_gap < RIM_UU:
            warn.append(f"prop {pid}: base footprint {edge_gap:.0f} uu from the tray edge, inside the T2 rocky lip "
                        f"band ({RIM_UU:.0f} uu: rock tops up to Z +2 there)")
        fx0, fy0 = full.min(0)
        fx1, fy1 = full.max(0)
        over = max(t_x0 - fx0, fx1 - t_x1, t_y0 - fy0, fy1 - t_y1)
        if over > CROWN_OVERHANG_WARN_UU:
            warn.append(f"prop {pid}: bounding box overhangs the tray edge by {over:.0f} uu")
        # 3. frame
        if rects_overlap(full, frame):
            err.append(f"prop {pid}: footprint enters the map frame "
                       f"(|X|<={FRAME_HX:.1f}, |Y|<={FRAME_HY:.1f} + {FRAME_GAP_UU})")
        elif fx0 < MAP_HX and fx1 > -MAP_HX and fy0 < MAP_HY and fy1 > -MAP_HY:
            err.append(f"prop {pid}: axis-aligned bounds overlap the map (UE S08EnvLayout counts an intrusion)")
        # 4. near band
        if rects_overlap(full, near) and h > NEAR_MAX_H_UU:
            err.append(f"prop {pid}: {h:.0f} uu tall in the near band (max {NEAR_MAX_H_UU})")
        # 8. tall props in the near half, in front of or at the corners of the map (not wholly beside the frame)
        x_gap = 0.0 if fx0 < 0.0 < fx1 else min(abs(fx0), abs(fx1))  # nearest |X| of the footprint
        if h > TALL_H_UU and float(p["loc"][1]) > 0 and x_gap < FRAME_HX + TALL_SIDE_UU:
            warn.append(f"prop {pid}: {h:.0f} uu tall in the near half (Y {p['loc'][1]:.0f} > 0) and within "
                        f"{TALL_SIDE_UU:.0f} uu of the frame's X columns")
    n = len(props)
    info["parsed"] = len(ok_props) == n
    if not PROPS_RANGE[0] <= n <= PROPS_RANGE[1]:
        warn.append(f"{n} props (guide {PROPS_RANGE[0]}..{PROPS_RANGE[1]})")
    # 5. base overlaps
    for i in range(len(ok_props)):
        for j in range(i + 1, len(ok_props)):
            a, b = ok_props[i], ok_props[j]
            tol = JOINT_TOL_UU if {mesh_name(a), mesh_name(b)} <= MODULAR else 0.5
            pen = -poly_clearance(footprint(a, True), footprint(b, True))
            if pen > tol:
                err.append(f"props {a['id']} / {b['id']}: base footprints overlap by {pen:.1f} uu (allowed {tol})")
    # lights
    lights = layout["lights"]
    pts = [lt for lt in lights if isinstance(lt, dict) and lt.get("type") == "point"]
    if len(pts) > MAX_POINT_LIGHTS:
        err.append(f"{len(pts)} point lights > {MAX_POINT_LIGHTS}")
    lid = set()
    for i, lt in enumerate(lights):
        tag = lt.get("id", f"#{i}") if isinstance(lt, dict) else f"#{i}"
        if not isinstance(lt, dict):
            err.append(f"light {tag}: not an object")
            continue
        if not isinstance(lt.get("id"), str) or lt["id"] in lid:
            err.append(f"light {tag}: id missing / duplicate")
        lid.add(lt.get("id"))
        if lt.get("type") != "point":
            err.append(f"light {tag}: type must be 'point' (the key light stays in the art profile)")
        if not (isinstance(lt.get("loc"), list) and len(lt["loc"]) == 3 and all(num(v) for v in lt["loc"])):
            err.append(f"light {tag}: loc must be [x, y, z]")
            continue
        if not isinstance(lt.get("colorSrgb"), str) or not HEX_RE.match(lt["colorSrgb"]):
            err.append(f"light {tag}: colorSrgb must be #RRGGBB")
        if not num(lt.get("intensityCd")) or not (0 < lt["intensityCd"] <= 500):
            err.append(f"light {tag}: intensityCd must be in (0, 500]")
        if not num(lt.get("radius")) or not (50 <= lt["radius"] <= 1500):
            err.append(f"light {tag}: radius must be in [50, 1500] uu")
        if lt.get("castShadow") is not False:
            err.append(f"light {tag}: point lights cast no shadows (castShadow false)")
        x, y, z = lt["loc"]
        if abs(x) < FRAME_HX and abs(y) < FRAME_HY:
            warn.append(f"light {tag}: above the map/frame - keep warm pools off the spaces")
        if not (t_x0 <= x <= t_x1 and t_y0 <= y <= t_y1) or not (0 < z <= 400):
            warn.append(f"light {tag}: off the tray or z outside (0, 400]")
    # 9. the themed ground (ENV-U10)
    g_err, g_warn, info["ground"] = validate_ground(layout, key, (t_x0, t_y0, t_x1, t_y1))
    err += g_err
    warn += g_warn
    return err, warn, info


# ------------------------------------------------------------------ 9. ground (ENV-U10, S08EnvGround.h)
GROUND_Z = (-3.0, -0.5)          # exclusive: above the tray top, below the map plane (S08EnvGroundSpec)
GROUND_MAX_OVERLAP_UU = 20.0     # S08EnvGroundSpec::MaxFrameOverlapUU
GROUND_MAX_INSET_UU = 200.0      # S08EnvGroundSpec::MaxInsetUU
GROUND_MIN_STRIP_UU = 0.5        # S08EnvGroundSpec::MinStripUU


def ground_strips(outer: tuple, hole: tuple) -> list[tuple]:
    """S08EnvGround::Strips: outer minus the hole as <= 4 disjoint rectangles (x0, y0, x1, y1): N, S, W, E."""
    ox0, oy0, ox1, oy1 = outer
    if ox1 - ox0 <= GROUND_MIN_STRIP_UU or oy1 - oy0 <= GROUND_MIN_STRIP_UU:
        return []
    hx0, hy0, hx1, hy1 = hole
    if hx1 <= ox0 or hx0 >= ox1 or hy1 <= oy0 or hy0 >= oy1:
        return [outer]
    hx0, hx1, hy0, hy1 = max(hx0, ox0), min(hx1, ox1), max(hy0, oy0), min(hy1, oy1)
    cand = [(ox0, oy0, ox1, hy0), (ox0, hy1, ox1, oy1), (ox0, hy0, hx0, hy1), (hx1, hy0, ox1, hy1)]
    return [r for r in cand if r[2] - r[0] > GROUND_MIN_STRIP_UU and r[3] - r[1] > GROUND_MIN_STRIP_UU]


def validate_ground(layout: dict, key: str, tray_rect: tuple) -> tuple[list[str], list[str], dict]:
    err, warn, info = [], [], {}
    g = layout.get("ground")
    if g is None:
        return [], ["no 'ground' section (ENV-U10 themed ground: tools/art/env_kit/ground_splat.py --write-layouts)"], info
    if not isinstance(g, dict):
        return ["ground is not an object"], [], info

    def num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if g.get("mode") != "runtime":
        err.append(f"ground: mode {g.get('mode')!r} is not 'runtime' (S08EnvGround: four engine-plane strips)")
    want_mat = f"/Game/EnvKit/Ground/MI_EnvGround_{MAPS[key]['kit']}"
    if g.get("material") not in (want_mat, f"{want_mat}.MI_EnvGround_{MAPS[key]['kit']}"):
        err.append(f"ground: material {g.get('material')!r} is not {want_mat} (tools/art/env_kit/ue_import_env_ground.py)")
    z = g.get("z", -1.0)
    if not num(z) or not GROUND_Z[0] < z < GROUND_Z[1]:
        err.append(f"ground: z {z!r} not in ({GROUND_Z[0]}, {GROUND_Z[1]}) - above the tray top, below the map plane")
    ov = g.get("frameOverlapUU", 2.0)
    if not num(ov) or not 0.0 <= ov <= GROUND_MAX_OVERLAP_UU:
        err.append(f"ground: frameOverlapUU {ov!r} not in [0, {GROUND_MAX_OVERLAP_UU:g}]")
        ov = 2.0
    inset = g.get("insetUU", 0.0)
    if not num(inset) or not 0.0 <= inset <= GROUND_MAX_INSET_UU:
        err.append(f"ground: insetUU {inset!r} not in [0, {GROUND_MAX_INSET_UU:g}]")
        inset = 0.0
    tx0, ty0, tx1, ty1 = tray_rect
    outer = (tx0 + inset, ty0 + inset, tx1 - inset, ty1 - inset)
    strips = ground_strips(outer, (-FRAME_HX + ov, -FRAME_HY + ov, FRAME_HX - ov, FRAME_HY - ov))
    info["strips"] = len(strips)
    info["areaUU2"] = round(sum((r[2] - r[0]) * (r[3] - r[1]) for r in strips), 1)
    if len(strips) != 4:
        err.append(f"ground: the tray top {outer} minus the frame gives {len(strips)} strips, not 4")
    rect = g.get("splatRect")
    if rect is not None:
        if not (isinstance(rect, list) and len(rect) == 4 and all(num(v) for v in rect) and rect[2] > rect[0]
                and rect[3] > rect[1]):
            err.append("ground: splatRect must be [minX, minY, maxX, maxY] numbers with max > min")
        else:
            info["splatRect"] = rect
            if not (rect[0] <= outer[0] and rect[1] <= outer[1] and rect[2] >= outer[2] and rect[3] >= outer[3]):
                err.append(f"ground: splatRect {rect} does not cover the ground {outer} (re-run ground_splat.py)")
    else:
        warn.append("ground: no splatRect - the MI's SplatRect is used as is")
    png = g.get("splat")
    if isinstance(png, str):
        path = ROOT / png
        if not path.is_file():
            warn.append(f"ground: splat {png} missing (tools/art/env_kit/ground_splat.py)")
        else:
            import hashlib
            got = hashlib.sha256(path.read_bytes()).hexdigest()
            info["splatSha256"] = got
            if g.get("splatSha256") not in (None, got):
                err.append(f"ground: {png} sha256 {got[:12]} != splatSha256 {str(g.get('splatSha256'))[:12]} "
                           f"(ground_splat.py --write-layouts)")
    return err, warn, info


def shadows(layout: dict, spaces: list[dict]) -> dict:
    """Per castShadow prop: world clearance (uu) between its key-light shadow on Z = 0 and the nearest circle."""
    L = k1_mock._light_dir(k1_mock.KEY_LIGHT_ROT)  # travel direction (z < 0)
    disks = [circle_pts(s)[:, :2] for s in spaces]
    out = {}
    for p in layout["props"]:
        if not p.get("castShadow"):
            continue
        b = box_corners(p)
        t = -b[:, 2] / L[2]
        sh = convex_hull(b[:, :2] + t[:, None] * L[None, :2])
        best = (math.inf, "")
        for s, d in zip(spaces, disks):
            if np.hypot(*(sh.mean(0) - (s["X"], s["Y"]))) > best[0] + 1000:
                continue
            c = poly_clearance(sh, d)
            if c < best[0]:
                best = (c, s["id"])
        out[p["id"]] = {"uu": best[0], "space": best[1]}
    return out


def _clip_rect(poly: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    """Sutherland-Hodgman clip of a convex polygon (n, 2) to an axis-aligned rectangle."""
    out = [tuple(q) for q in poly]
    for axis, bound, keep_ge in ((0, x0, True), (0, x1, False), (1, y0, True), (1, y1, False)):
        src, out = out, []
        for i in range(len(src)):
            a, b = src[i], src[(i + 1) % len(src)]
            ina = a[axis] >= bound if keep_ge else a[axis] <= bound
            inb = b[axis] >= bound if keep_ge else b[axis] <= bound
            if ina:
                out.append(a)
            if ina != inb:
                t = (bound - a[axis]) / (b[axis] - a[axis])
                out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
        if not out:
            return np.zeros((0, 2))
    return np.array(out, float)


def _area(poly: np.ndarray) -> float:
    if len(poly) < 3:
        return 0.0
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def k1_framing(layout: dict, key: str, framed: tuple | None = None) -> tuple[list[str], dict]:
    """10. Per prop at the K1 overview (D0, looking at the centre): the share of its projected box hull inside the
    1920 x 1080 frame and the smallest distance of a box corner to the frame edge (px, < 0 = outside); K1_FRAMED props
    must be wholly inside (>= K1_FRAME_MARGIN_PX); `framed` overrides K1_FRAMED[key] (selftest)."""
    _, d0, _ = k1_rig(layout_board_id(layout))
    cam = make_camera(d0)
    W, H = SCREEN
    err, info = [], {}
    for p in layout["props"]:
        b = box_corners(p)
        if (((b - cam.pos) @ cam.fwd) < NEAR_UU).any():
            info[p["id"]] = {"inFrame": 0.0, "edgePx": -math.inf}
            continue
        scr = cam.project(b)
        hull = convex_hull(scr)
        full = _area(hull)
        share = _area(_clip_rect(hull, 0.0, 0.0, float(W), float(H))) / full if full > 0 else 0.0
        edge = float(min(scr[:, 0].min(), scr[:, 1].min(), W - scr[:, 0].max(), H - scr[:, 1].max()))
        info[p["id"]] = {"inFrame": round(share, 3), "edgePx": round(edge, 1)}
    for pid in (K1_FRAMED.get(key, ()) if framed is None else framed):
        got = info.get(pid)
        if got is None:
            err.append(f"prop {pid}: listed in K1_FRAMED but not in the layout")
        elif got["edgePx"] < K1_FRAME_MARGIN_PX:
            err.append(f"prop {pid}: box leaves the K1 frame ({-got['edgePx']:.0f} px past the edge, "
                       f"{got['inFrame']:.0%} in frame) - K1_FRAMED props must be wholly visible at the K1 overview")
    return err, info


def check(key: str, layout_path: Path, topo_path: Path) -> dict:
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    topo = json.loads(topo_path.read_text(encoding="utf-8"))
    spaces = load_spaces(topo)
    err, warn, info = validate(layout, key, spaces)
    occ = {}
    if info.get("parsed"):
        occ = occlusion(layout, spaces)
        for pid, w in occ.items():
            info["props"][pid]["clearance_px"] = round(w["px"], 1)
            info["props"][pid]["worst"] = f"{w['camera']} / {w['space']}"
            if w["px"] < MARGIN_PX:
                err.append(f"prop {pid}: covers / grazes space {w['space']} at camera {w['camera']} "
                           f"(clearance {w['px']:.1f} px < {MARGIN_PX} px)")
        for pid, sh in shadows(layout, spaces).items():
            info["props"][pid]["shadow_uu"] = round(sh["uu"], 1)
            if sh["uu"] < 0:
                err.append(f"prop {pid}: key-light shadow falls on space {sh['space']} ({-sh['uu']:.1f} uu deep) - "
                           f"move it out or set castShadow false")
            elif sh["uu"] < SHADOW_WARN_UU:
                warn.append(f"prop {pid}: key-light shadow {sh['uu']:.1f} uu from space {sh['space']}")
        k_err, k_info = k1_framing(layout, key)
        err += k_err
        for pid, k in k_info.items():
            info["props"][pid]["k1_in_frame"] = k["inFrame"]
            info["props"][pid]["k1_edge_px"] = k["edgePx"]
    return {"map": key, "layout": layout, "spaces": spaces, "errors": err, "warnings": warn, "info": info,
            "occlusion": occ,
            "cameras": len(camera_set(spaces, layout_board_id(layout))) if info.get("parsed") else 0}


# ------------------------------------------------------------------ debug images (CPU / PIL)
def _glb_preview(path: Path, cache_dir: Path | None, tex: int = 256):
    """Vertices (glTF axes), faces and per-face sRGB colour of a Tripo GLB (one primitive)."""
    st = path.stat()
    cache = cache_dir / f"{path.stem}-{st.st_size}-{int(st.st_mtime)}.npz" if cache_dir else None
    if cache and cache.exists():
        z = np.load(cache)
        return z["v"], z["f"], z["c"]
    from PIL import Image
    import io
    b = path.read_bytes()
    jl = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + jl])
    bin0 = 20 + jl + 8
    comp = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}
    ncomp = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}

    def acc(i):
        a = j["accessors"][i]
        bv = j["bufferViews"][a["bufferView"]]
        off = bin0 + bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        n = a["count"] * ncomp[a["type"]]
        return np.frombuffer(b, comp[a["componentType"]], n, off).reshape(a["count"], -1)
    prim = j["meshes"][0]["primitives"][0]
    v = acc(prim["attributes"]["POSITION"]).astype(np.float32)
    uv = acc(prim["attributes"]["TEXCOORD_0"]).astype(np.float32)
    f = acc(prim["indices"]).reshape(-1, 3).astype(np.int32)
    tex_i = j["materials"][prim["material"]]["pbrMetallicRoughness"]["baseColorTexture"]["index"]
    img = j["images"][j["textures"][tex_i]["source"]]
    bv = j["bufferViews"][img["bufferView"]]
    raw = b[bin0 + bv.get("byteOffset", 0): bin0 + bv.get("byteOffset", 0) + bv["byteLength"]]
    t = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB").resize((tex, tex), Image.BILINEAR), np.float32) / 255
    fuv = uv[f].mean(axis=1)
    ix = np.clip((fuv[:, 0] % 1.0) * tex, 0, tex - 1).astype(int)
    iy = np.clip((fuv[:, 1] % 1.0) * tex, 0, tex - 1).astype(int)  # glTF uv: v down from the image top
    c = t[iy, ix]
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, v=v, f=f, c=c)
    return v, f, c


def _prop_tris(p: dict, glb_dir: Path | None, cache_dir: Path | None):
    """World triangles (F, 3, 3) and sRGB colours (F, 3) of a prop (real mesh or its box)."""
    name = mesh_name(p)
    kit, src, (ex, ey, ez), (kind, val), _ = KIT[name]
    ref = ey if kind == "height" else max(ex, ez)
    k = val / ref * p["scale"]
    R = _rot(p["yawDeg"])
    loc = np.asarray(p["loc"], float)
    glb = (GLB_DIR_OF.get(name, glb_dir) / f"{src}.glb") if glb_dir else None
    if glb and glb.exists():
        v, f, c = _glb_preview(glb, cache_dir)
        # glTF -> .blend (x, -z, y), the processing turn about .blend +Z, then .blend -> UM_FBX_v1 local
        # (front .blend -Y -> UE +X): UE = (-by, -bx, bz); with no turn this is (gz, -gx, gy)
        b = np.c_[v[:, 0], -v[:, 2], v[:, 1]].astype(np.float64)
        t = math.radians(TURNS.get(name, 0.0))
        b = np.c_[b[:, 0] * math.cos(t) - b[:, 1] * math.sin(t), b[:, 0] * math.sin(t) + b[:, 1] * math.cos(t), b[:, 2]]
        if name in PROCESSED:  # scale to the processed height exactly
            k = PROCESSED[name][2] * p["scale"] / max(float(b[:, 2].max() - b[:, 2].min()), 1e-9)
        loc_v = np.c_[-b[:, 1], -b[:, 0], b[:, 2]] * k
        xy = loc_v[:, :2] @ R.T
        w = np.c_[xy, loc_v[:, 2]] + loc
        return w[f], c, True
    corners = box_corners(p)
    quads = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for q in quads:
        tris += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    tri = corners[np.array(tris)]
    col = np.tile(np.array(_KIND_COL.get(name, (0.7, 0.7, 0.7))), (len(tri), 1))
    return tri, col, False


_KIND_COL = {"ArcadeBay": (0.85, 0.83, 0.80), "Portal": (0.9, 0.85, 0.75), "Cherry": (0.95, 0.55, 0.75),
             "PlinthBall": (0.8, 0.8, 0.82), "LanternPlinth": (1.0, 0.8, 0.5), "Urn": (0.85, 0.7, 0.75),
             "Cypress": (0.25, 0.5, 0.3), "FortRuin": (0.6, 0.6, 0.55), "Tree": (0.3, 0.55, 0.3),
             "Hull": (0.55, 0.25, 0.2), "Cannon": (0.3, 0.3, 0.3), "Campfire": (1.0, 0.5, 0.2),
             "Palisade": (0.5, 0.35, 0.2), "Rope": (0.8, 0.7, 0.45), "Barrel": (0.6, 0.4, 0.22),
             "CrateStack": (0.55, 0.42, 0.28), "LanternPost": (1.0, 0.75, 0.4), "Banner": (0.75, 0.12, 0.15),
             "RockOutcrop": (0.5, 0.5, 0.47), "Balustrade": (0.88, 0.86, 0.82), "HedgeBed": (0.25, 0.45, 0.25),
             "BackWall_BayDoor": (0.9, 0.87, 0.8), "BackWall_BayWindows": (0.9, 0.87, 0.8),
             "BackWall_Centre": (0.9, 0.87, 0.8)}


def _shade(tri: np.ndarray, col: np.ndarray, view_from=None):
    # glTF (right-handed) -> UE local (left-handed) has det -1: the glTF winding's cross product points inwards
    n = -np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    n[ok] /= ln[ok, None]
    L = -k1_mock._light_dir(k1_mock.KEY_LIGHT_ROT)
    lam = np.clip(n @ L, 0, 1)
    sh = col * (0.42 + 0.58 * lam)[:, None]
    vis = ok.copy()
    if view_from is not None:
        cen = tri.mean(axis=1)
        vis &= ((view_from - cen) * n).sum(1) > 0
    return np.clip(sh, 0, 1), vis


def _font(size):
    from PIL import ImageFont
    for f in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _homography(src: np.ndarray, dst: np.ndarray) -> list[float]:
    """Coefficients for PIL PERSPECTIVE: maps output (dst) to input (src)."""
    A, bb = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y]); bb.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y]); bb.append(v)
    return list(np.linalg.solve(np.array(A, float), np.array(bb, float)))


def _find_map_image(key: str, map_dir: Path | None):
    """The logo-free 4K BC of the map surface track if present, else the source illustration."""
    name = key.capitalize()
    cands = [d / f"{key}{ext}" for d in ([map_dir] if map_dir else []) for ext in (".png", ".webp")]
    for base in (ROOT, MAIN):
        cands.append(base / f"scraped-data/derived/maps/{key}/T_{name}_Map_BC_4K.png")
        cands += [base / f"scraped-data/images/maps/{key}{ext}" for ext in (".png", ".webp")]
    return next((p for p in cands if p.exists()), None)


def render_view(res: dict, dist: float, focus, out: Path, title: str, glb_dir, cache_dir, map_img, ss: int = 2):
    from PIL import Image, ImageDraw
    lay, spaces = res["layout"], res["spaces"]
    cam = make_camera(dist, focus)
    W, H = cam.w, cam.h
    big = make_camera(dist, focus, (W * ss, H * ss))
    img = Image.new("RGB", (W * ss, H * ss), (12, 15, 26))
    dr = ImageDraw.Draw(img)
    tr = lay["tray"]
    ty0, ty1 = tr["offsetY"] - tr["halfY"], tr["offsetY"] + tr["halfY"]
    tx = tr["halfX"]
    th = 150.0

    def P(pts):
        return [tuple(q) for q in big.project(np.asarray(pts, float))]
    z0, z1 = TRAY_TOP_Z, TRAY_TOP_Z - th
    dr.polygon(P([[-tx, ty1, z0], [tx, ty1, z0], [tx, ty1, z1], [-tx, ty1, z1]]), fill=(38, 36, 36))  # near wall
    dr.polygon(P([[-tx, ty0, z0], [tx, ty0, z0], [tx, ty1, z0], [-tx, ty1, z0]]), fill=(62, 60, 58))  # tray top
    # apron / walkway hint (frame + 60 uu)
    dr.polygon(P([[-FRAME_HX - 60, -FRAME_HY - 60, TRAY_TOP_Z], [FRAME_HX + 60, -FRAME_HY - 60, TRAY_TOP_Z],
                  [FRAME_HX + 60, FRAME_HY + 60, TRAY_TOP_Z], [-FRAME_HX - 60, FRAME_HY + 60, TRAY_TOP_Z]]),
               fill=(74, 72, 70))
    dr.polygon(P([[-FRAME_HX, -FRAME_HY, 0], [FRAME_HX, -FRAME_HY, 0], [FRAME_HX, FRAME_HY, 0], [-FRAME_HX, FRAME_HY, 0]]),
               fill=(58, 38, 24))
    corners = np.array([[-MAP_HX, -MAP_HY, 0], [MAP_HX, -MAP_HY, 0], [MAP_HX, MAP_HY, 0], [-MAP_HX, MAP_HY, 0]])
    scr = big.project(corners)
    if map_img is not None:
        m = Image.open(map_img).convert("RGB").resize((2 * SRC_W, 2 * SRC_H), Image.LANCZOS)
        sw, sh_ = m.size
        coef = _homography(np.array([[0, 0], [sw, 0], [sw, sh_], [0, sh_]], float), scr)
        warped = m.transform(img.size, Image.PERSPECTIVE, coef, Image.BILINEAR)
        mask = Image.new("L", img.size, 0)
        ImageDraw.Draw(mask).polygon([tuple(q) for q in scr], fill=255)
        img.paste(warped, (0, 0), mask)
    else:
        dr.polygon([tuple(q) for q in scr], fill=(70, 90, 70))
    bad = {e.split("space ")[1].split(" ")[0] for e in res["errors"] if "covers / grazes space" in e}
    for s in spaces:
        pts = big.project(circle_pts(s, 64))
        colr = (255, 60, 60) if s["id"] in bad else (0, 230, 255)
        dr.line([tuple(q) for q in pts] + [tuple(pts[0])], fill=colr, width=ss)
    # props: painter's algorithm over every triangle
    T, C = [], []
    for p in lay["props"]:
        tri, col, _ = _prop_tris(p, glb_dir, cache_dir)
        sh, vis = _shade(tri, col, big.pos)
        T.append(tri[vis]); C.append(sh[vis])
    if T:
        T = np.concatenate(T); C = np.concatenate(C)
        depth = np.linalg.norm(T.mean(axis=1) - big.pos, axis=1)
        order = np.argsort(-depth)
        S = big.project(T.reshape(-1, 3)).reshape(-1, 3, 2)
        cols = (np.round(C * 255)).astype(int)
        for i in order:
            dr.polygon([tuple(S[i, 0]), tuple(S[i, 1]), tuple(S[i, 2])], fill=tuple(cols[i]))
    img = img.resize((W, H), Image.LANCZOS)
    dr = ImageDraw.Draw(img)
    f = _font(13)
    occ = res["occlusion"]
    for p in lay["props"]:
        b = cam.project(box_corners(p))
        hull = convex_hull(b)
        ok = occ.get(p["id"], {}).get("px", math.inf) >= MARGIN_PX
        dr.line([tuple(q) for q in hull] + [tuple(hull[0])], fill=(90, 255, 120) if ok else (255, 40, 40), width=1)
        top = b[4:].mean(0)
        dr.text((top[0] - 20, top[1] - 16), p["id"], fill=(255, 255, 160), font=f)
    for lt in lay["lights"]:
        q = cam.project([lt["loc"]])[0]
        dr.ellipse([q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5], outline=(255, 200, 80), width=2)
    dr.text((10, 8), title, fill=(255, 255, 255), font=_font(18))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def render_top(res: dict, out: Path, glb_dir, cache_dir, map_img, px_per_uu: float = 1.0):
    from PIL import Image, ImageDraw
    lay, spaces = res["layout"], res["spaces"]
    tr = lay["tray"]
    ty0, ty1 = tr["offsetY"] - tr["halfY"], tr["offsetY"] + tr["halfY"]
    tx = tr["halfX"]
    pad = 90
    x0, y0 = -tx - pad, ty0 - pad
    Wp, Hp = int((2 * tx + 2 * pad) * px_per_uu), int((ty1 - ty0 + 2 * pad) * px_per_uu)
    img = Image.new("RGB", (Wp, Hp), (14, 16, 24))
    dr = ImageDraw.Draw(img)

    def Q(pts):
        pts = np.asarray(pts, float)
        return [((x - x0) * px_per_uu, (y - y0) * px_per_uu) for x, y in pts[:, :2]]
    dr.rectangle(Q([[-tx, ty0], [tx, ty1]]), fill=(60, 58, 56))
    ap = lay["apron"]
    dr.rectangle(Q([[-FRAME_HX - ap["w"], -FRAME_HY - ap["n"]], [FRAME_HX + ap["e"], FRAME_HY + ap["s"]]]),
                 outline=(150, 150, 150))
    dr.rectangle(Q([[-FRAME_HX - 60, -FRAME_HY - 60], [FRAME_HX + 60, FRAME_HY + 60]]), fill=(72, 70, 68))
    dr.rectangle(Q([[-FRAME_HX, -FRAME_HY], [FRAME_HX, FRAME_HY]]), fill=(58, 38, 24))
    box = Q([[-MAP_HX, -MAP_HY], [MAP_HX, MAP_HY]])
    if map_img is not None:
        size = (int(box[1][0] - box[0][0]), int(box[1][1] - box[0][1]))
        m = Image.open(map_img).convert("RGB").resize(size, Image.LANCZOS)
        img.paste(m, (int(box[0][0]), int(box[0][1])))
    f = _font(12)
    for s in spaces:
        c = Q([[s["X"] - s["R"], s["Y"] - s["R"]], [s["X"] + s["R"], s["Y"] + s["R"]]])
        dr.ellipse(c, outline=(0, 230, 255), width=2)
        cx, cy = Q([[s["X"], s["Y"]]])[0]
        dr.text((cx - 11, cy - 7), s["id"], fill=(255, 255, 255), font=f)
    # ground footprints of the K1 (D0) and zoom-out limit frusta
    _, d0, far = k1_rig(layout_board_id(lay))
    for dist, colr in ((d0, (255, 255, 255)), (far, (140, 140, 255))):
        cam = make_camera(dist)
        r = cam.rays(0, cam.h)
        cr = np.array([r[0, 0], r[0, -1], r[-1, -1], r[-1, 0]])
        t = -cam.pos[2] / cr[:, 2]
        g = cam.pos[None, :2] + t[:, None] * cr[:, :2]
        pts = Q(g)
        dr.line(pts + [pts[0]], fill=colr, width=1)
    T, C = [], []
    top = np.array([0.0, 0.0, 1e5])
    for p in lay["props"]:
        tri, col, _ = _prop_tris(p, glb_dir, cache_dir)
        sh, vis = _shade(tri, col, None)
        n = -np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        vis &= n[:, 2] > 0
        T.append(tri[vis]); C.append(sh[vis])
    if T:
        T = np.concatenate(T); C = np.concatenate(C)
        order = np.argsort(T[:, :, 2].mean(1))
        cols = (np.round(C * 255)).astype(int)
        for i in order:
            dr.polygon(Q(T[i]), fill=tuple(cols[i]))
    occ = res["occlusion"]
    for p in lay["props"]:
        ok = occ.get(p["id"], {}).get("px", math.inf) >= MARGIN_PX
        full, base = Q(footprint(p)), Q(footprint(p, base=True))
        dr.line(full + [full[0]], fill=(90, 255, 120) if ok else (255, 40, 40), width=1)
        dr.line(base + [base[0]], fill=(255, 255, 0), width=1)
        _, _, h = dims(mesh_name(p), p["scale"])
        cx, cy = Q([p["loc"][:2]])[0]
        dr.text((cx + 4, cy + 2), f"{p['id']} h{h:.0f}", fill=(255, 255, 160), font=f)
    for lt in lay["lights"]:
        x, y, z = lt["loc"]
        rg = math.sqrt(max(lt["radius"] ** 2 - z ** 2, 0))
        c = Q([[x - rg, y - rg], [x + rg, y + rg]])
        dr.ellipse(c, outline=(255, 190, 90), width=1)
        cx, cy = Q([[x, y]])[0]
        dr.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 200, 90))
        dr.text((cx + 6, cy - 14), f"{lt['id']} {lt['intensityCd']}cd", fill=(255, 210, 120), font=f)
    dr.text((8, 6), f"{res['map']} top view - tray x[{-tx:.0f},{tx:.0f}] y[{ty0:.0f},{ty1:.0f}]  "
                    f"apron n{ap['n']} s{ap['s']} w{ap['w']} e{ap['e']}  "
                    f"(white = K1 ground frustum D0 {d0:.0f}, blue = zoom-out limit {far:.0f} = {d0 / far:.4g}x; "
                    f"yellow = base footprint)",
            fill=(255, 255, 255), font=_font(15))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def write_images(res: dict, out_dir: Path, glb_dir, map_dir):
    key = res["map"]
    cache = out_dir / "_mesh_cache"
    map_img = _find_map_image(key, map_dir)
    render_top(res, out_dir / f"{key}-top.png", glb_dir, cache, map_img)
    fit, d0, far = k1_rig(layout_board_id(res["layout"]))
    for tag, dist, title in (("k1", d0, f"K1 overview (fit x{d0 / fit:.3g})"),
                             ("out", far, f"zoom-out limit {d0 / far:.4g}x (fit / {ZOOM_OUT:g})"),
                             ("wide", fit * 1.45, "concept camera (fit x1.45)")):
        render_view(res, dist, (0.0, 0.0, 0.0), out_dir / f"{key}-{tag}.png", f"{key} {title}  D={dist:.0f}",
                    glb_dir, cache, map_img)
    return map_img


# ------------------------------------------------------------------ self-test
def selftest() -> int:
    """Synthetic cases on the Marmoreal topology: every rule must fire where it should and stay quiet where
    the geometry says it cannot matter (far / side giants never occlude a circle)."""
    topo = json.loads((ROOT / "backend/prisma/fixtures/boards/marmoreal.topology.json").read_text(encoding="utf-8"))
    spaces = load_spaces(topo)
    tray = dict(TRAY_T2)  # the shared T2 tray and the apron it implies
    ap = {"n": -(tray["offsetY"] - tray["halfY"]) - FRAME_HY, "s": tray["offsetY"] + tray["halfY"] - FRAME_HY,
          "w": tray["halfX"] - FRAME_HX, "e": tray["halfX"] - FRAME_HX}

    def P(pid, name, x, y, yaw=90.0, scale=1.0, shadow=False):
        return {"id": pid, "mesh": f"/Game/EnvKit/{KIT[name][0]}/SM_Env_{name}", "loc": [x, y, TRAY_TOP_Z],
                "yawDeg": yaw, "scale": scale, "castShadow": shadow}

    def Lt(lid, x=-520.0, y=-365.0, z=70.0, shadow=False):
        return {"id": lid, "type": "point", "loc": [x, y, z], "colorSrgb": "#FFB870", "intensityCd": 45,
                "radius": 320, "castShadow": shadow}
    cases = [
        ("tall prop in the near band covers the near spaces", [P("t", "Cypress", 0, 345)], [],
         ["near band", "covers / grazes"], ["frame"]),
        ("25-uu prop in the near band is legal", [P("t", "Urn", 0, 335, scale=0.7)], [], [], ["covers", "near band"]),
        ("prop on the frame", [P("t", "PlinthBall", 460, 0)], [], ["enters the map frame"], []),
        ("prop off the tray", [P("t", "PlinthBall", 900, 0)], [], ["leaves the tray"], []),
        ("far giant never occludes", [P("t", "Portal", 0, -430, 90, 1.6)], [], [], ["covers"]),
        ("side giant never occludes", [P("t", "Cherry", -680, 0, 180, 2.0)], [], [], ["covers", "frame", "near band"]),
        ("W tree shadow falls on the W spaces", [P("t", "Cherry", -600, -80, 180, 1.4, shadow=True)], [],
         ["shadow falls"], ["frame", "covers"]),
        ("wrong kit folder", [dict(P("t", "Urn", 0, -372), mesh="/Game/EnvKit/Sarpedon/SM_Env_Urn")], [],
         ["lives in"], []),
        ("unknown mesh", [dict(P("t", "Urn", 0, -372), mesh="/Game/EnvKit/Marmoreal/SM_Env_Lantern")], [],
         ["is not /Game/EnvKit"], []),
        ("base footprints overlap", [P("a", "Urn", 0, -372), P("b", "Urn", 10, -372)], [],
         ["base footprints overlap"], []),
        ("abutting wall modules are fine",
         [P("a", "ArcadeBay", -76.1, -425, 90, 1.45), P("b", "ArcadeBay", 76.1, -425, 90, 1.45)], [], [], ["overlap"]),
        # P5: modules with an underscore name (lane-K back wall) parse; abutting balustrade segments are a joint, two
        # segments on top of each other are not; the back-wall module box sits on its back-face pivot (LOCAL_CENTRE_X)
        ("back-wall modules abut behind the arcade",
         [P("a", "BackWall_BayWindows", -169.2, -465.866), P("b", "BackWall_Centre", 0.0, -465.866)], [], [],
         ["overlap", "is not /Game/EnvKit"]),
        ("balustrade segments abut, stacked ones overlap",
         [P("a", "Balustrade", -752, -121, 0), P("b", "Balustrade", -752, 29, 0), P("c", "Balustrade", -752, 60, 0)], [],
         ["props b / c: base footprints overlap"], ["props a / b"]),
        ("point light with shadows", [], [Lt("a", shadow=True)], ["cast no shadows"], []),
        ("seven point lights", [], [Lt(f"l{i}", x=-520.0 + 40 * i) for i in range(7)], ["point lights >"], []),
        ("near-corner post behind the close wheel cameras is clipped, not projected",
         [P("t", "PlinthBall", -525, 368)], [], [], ["covers"]),
        ("a tray other than the shared T2 tray", [P("t", "PlinthBall", -525, 368)], [], ["not the shared T2 tray"],
         [], {"halfX": FRAME_HX + 260.0, "halfY": FRAME_HY + 130.0, "offsetY": -40.0},
         {"n": 170.0, "s": 90.0, "w": 260.0, "e": 260.0}),
    ]
    fails = 0
    for name, props, lights, must, must_not, *own in cases:
        lay = {"schema": SCHEMA, "map": "marmoreal", "boardId": MAPS["marmoreal"]["boardId"],
               "tray": own[0] if own else tray, "apron": own[1] if own else ap, "props": props, "lights": lights,
               "notes": "selftest"}
        err, _, info = validate(lay, "marmoreal", spaces)
        if info.get("parsed") and props:
            for pid, w in occlusion(lay, spaces).items():
                if w["px"] < MARGIN_PX:
                    err.append(f"prop {pid}: covers / grazes space {w['space']} ({w['px']:.1f} px)")
            for pid, sh in shadows(lay, spaces).items():
                if sh["uu"] < 0:
                    err.append(f"prop {pid}: key-light shadow falls on space {sh['space']}")
        text = " | ".join(err)
        ok = all(m in text for m in must) and not any(m in text for m in must_not)
        fails += not ok
        print(f"   {'ok  ' if ok else 'FAIL'} {name}: {text or 'no errors'}")
    # 9. the ground section (validate_ground on the shared tray top)
    t_rect = (-tray["halfX"], tray["offsetY"] - tray["halfY"], tray["halfX"], tray["offsetY"] + tray["halfY"])
    good = {"mode": "runtime", "material": "/Game/EnvKit/Ground/MI_EnvGround_Marmoreal", "z": -1.0,
            "frameOverlapUU": 2.0, "insetUU": 0.0, "splatRect": [-820.0, -560.0, 820.0, 470.0]}
    g_cases = [
        ("valid ground: 4 strips round the frame", good, [], ["ground"]),
        ("ground with a mesh mode", dict(good, mode="mesh"), ["ground: mode"], []),
        ("ground material of the other map", dict(good, material="/Game/EnvKit/Ground/MI_EnvGround_Sarpedon"),
         ["ground: material"], []),
        ("ground under the tray top", dict(good, z=-3.5), ["ground: z"], []),
        ("splat rect short of the tray", dict(good, splatRect=[-700.0, -560.0, 820.0, 470.0]), ["does not cover"], []),
        ("inset swallowing the near band", dict(good, insetUU=150.0), ["strips, not 4"], []),
    ]
    for name, ground, must, must_not in g_cases:
        err, _, _ = validate_ground({"ground": ground}, "marmoreal", t_rect)
        text = " | ".join(err)
        ok = all(m in text for m in must) and not any(m in text for m in must_not)
        fails += not ok
        print(f"   {'ok  ' if ok else 'FAIL'} {name}: {text or 'no errors'}")
    # 8. / 10. (P4): near-half tall props warn only at the frame's X columns; K1_FRAMED boxes stay in the K1 frame
    w_cases = [
        ("tall tree beside the frame in the near half is quiet", [P("t", "Cherry", -680, 150, 0, 1.0)], "near half",
         False),
        ("tall cypress at the near corner warns", [P("t", "Cypress", -505, 200, 90, 1.3)], "near half", True),
    ]
    for name, props, needle, want in w_cases:
        lay = {"schema": SCHEMA, "map": "marmoreal", "boardId": MAPS["marmoreal"]["boardId"], "tray": tray,
               "apron": ap, "props": props, "lights": [], "notes": "selftest"}
        _, warns, _ = validate(lay, "marmoreal", spaces)
        text = " | ".join(warns)
        ok = (needle in text) == want
        fails += not ok
        print(f"   {'ok  ' if ok else 'FAIL'} {name}: {text or 'no warnings'}")
    hull = "/Game/EnvKit/Sarpedon/SM_Env_Hull"
    f_cases = [
        ("hull in the far-right corner leaves the K1 frame", [700.0, -370.0], 152.0, True),
        ("hull along the E frame edge stays in the K1 frame", [590.0, -125.0], 178.0, False),
    ]
    for name, xy, yaw, want in f_cases:
        lay = {"boardId": MAPS["sarpedon"]["boardId"], "map": "sarpedon",
               "props": [{"id": "h", "mesh": hull, "loc": [*xy, TRAY_TOP_Z], "yawDeg": yaw, "scale": 0.85}]}
        err, info = k1_framing(lay, "sarpedon", framed=("h",))
        text = " | ".join(err)
        ok = ("leaves the K1 frame" in text) == want and 0.0 <= info["h"]["inFrame"] <= 1.0
        fails += not ok
        print(f"   {'ok  ' if ok else 'FAIL'} {name}: {text or 'in frame'} (share {info['h']['inFrame']:.0%})")
    total = len(cases) + len(g_cases) + len(w_cases) + len(f_cases)
    print(f"   -> selftest {'FAIL' if fails else 'OK'} ({total - fails}/{total})")
    return 1 if fails else 0


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", nargs="+", default=list(MAPS), choices=list(MAPS))
    ap.add_argument("--layouts", default=str(ROOT / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"))
    ap.add_argument("--topology", default=str(ROOT / "backend/prisma/fixtures/boards"))
    ap.add_argument("--images", default=None, help="write debug images to this directory (out of git)")
    ap.add_argument("--glb-dir", default=str(BUILD_REPORTS.parents[1] / "source"),
                    help="Tripo source GLBs for the mesh previews (out of git; boxes without them)")
    ap.add_argument("--map-images", default=None, help="directory with <map>.png / .webp (default: scraped-data)")
    ap.add_argument("--build-reports", default=str(BUILD_REPORTS),
                    help="reports/assets of the env kit build (processed sizes); '' = KIT table only")
    ap.add_argument("--json", default=None, help="write the machine-readable report here")
    ap.add_argument("--selftest", action="store_true", help="run the synthetic negative cases and exit")
    a = ap.parse_args(argv)
    kit_msgs = kit_crosscheck(Path(a.build_reports) if a.build_reports else None)
    if a.selftest:
        return selftest()
    for m in kit_msgs:
        print(m)
    failed = False
    report = {"kit": kit_msgs}
    for key in a.maps:
        res = check(key, Path(a.layouts) / f"{key}.layout.json", Path(a.topology) / f"{key}.topology.json")
        lay = res["layout"]
        print(f"== {key}: {len(lay.get('props', []))} props, {len(lay.get('lights', []))} lights, "
              f"{len(res['spaces'])} spaces, {res['cameras']} camera poses, "
              f"margin {MARGIN_PX} px @ {SCREEN[0]}x{SCREEN[1]}")
        fit, d0, far = k1_rig(layout_board_id(lay) or MAPS[key]["boardId"])
        rig = {"fitUU": round(fit, 3), "k1DistanceMul": round(d0 / fit, 4), "k1UU": round(d0, 3),
               "farUU": round(far, 3), "nearUU": min(MIN_DIST_UU, d0), "zoomRange": [round(d0 / far, 4),
                                                                                    round(d0 / min(MIN_DIST_UU, d0), 4)]}
        print(f"   camera: K1 D0 {d0:.1f} uu = fit {fit:.1f} x k1DistanceMul {d0 / fit:g} (ENV-U9); wheel "
              f"{rig['nearUU']:.0f} .. {far:.1f} uu = zoom {rig['zoomRange'][0]:g}x .. {rig['zoomRange'][1]:g}x of D0; "
              f"follow from {FOLLOW_FROM:g}x = {d0 / FOLLOW_FROM:.1f} uu")
        if "tray" in res["info"]:
            print(f"   tray x{res['info']['tray']['x']} y{res['info']['tray']['y']}  apron {lay['apron']}")
        if res["info"].get("ground"):
            gi = res["info"]["ground"]
            print(f"   ground: {gi.get('strips')} strips, {gi.get('areaUU2', 0):.0f} uu2, splatRect {gi.get('splatRect')}, "
                  f"splat sha256 {str(gi.get('splatSha256', '-'))[:12]}")
        print(f"   {'prop':<16} {'mesh':<14} {'w x d x h (uu)':<16} {'clear px':>8}  "
              f"{'worst camera / space':<22} {'shadow uu':>9} {'K1 in frame':>11}")
        for pid, inf in res["info"]["props"].items():
            s = "x".join(f"{v:.0f}" for v in inf["size_uu"])
            sh = inf.get("shadow_uu")
            k1 = inf.get("k1_in_frame")
            framed = "*" if pid in K1_FRAMED.get(key, ()) else " "
            print(f"   {pid:<16} {inf['mesh']:<14} {s:<16} {inf.get('clearance_px', float('nan')):>8.1f}  "
                  f"{inf.get('worst', ''):<22} {'-' if sh is None else f'{sh:.1f}':>9} "
                  f"{'-' if k1 is None else f'{k1:.0%}':>10}{framed}")
        for w in res["warnings"]:
            print(f"   WARN  {w}")
        for e in res["errors"]:
            print(f"   ERROR {e}")
        print(f"   -> {'FAIL' if res['errors'] else 'OK'}")
        failed |= bool(res["errors"])
        if a.images:
            glb = Path(a.glb_dir) if a.glb_dir and Path(a.glb_dir).exists() else None
            mi = write_images(res, Path(a.images), glb, Path(a.map_images) if a.map_images else None)
            print(f"   images -> {a.images} ({'meshes' if glb else 'boxes'}, map {'yes' if mi else 'missing'})")
        report[key] = {"errors": res["errors"], "warnings": res["warnings"], "info": res["info"],
                       "cameras": res["cameras"], "camera": rig, "marginPx": MARGIN_PX}
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
