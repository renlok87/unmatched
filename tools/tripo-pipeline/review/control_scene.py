"""P1.7 control scene (stage 3, T3.1): build the isolated Cobble control level with the pipeline candidates and
capture EDITOR frames of it through the LIVE UnrealEditor (MCP 127.0.0.1:8123), one capture method for all frames.

    python tools/tripo-pipeline/review/control_scene.py --out <dir> --tag r1 [--barrel <SM asset>] [--skip-diagnostics]
        [--asset-set w4b|t31]

Idempotent: every run deletes /Game/ArtTests/P17ControlScene (only packages this script owns; anything else there makes
it refuse), duplicates the Cobble review level /Game/ArtTests/ART005H/L_ART005H_CornerReview into
/Game/ArtTests/P17ControlScene/L_P17ControlScene, removes the review figures, markers and camera of the copy, moves the
fill light, adds a fixed-exposure post-process volume, spawns the candidates on real board cells (5x6, 100 uu) and saves
only that folder. Everything after the save (camera, visibility, yaw, material swaps, animation poses) lives in memory;
at the end the previously open level is loaded again, so the control level stays as built and nothing else is saved.

Scene (cells of the S04 start fighters f-0 / f-1, as the grey figures of ART005H; facing rule of S08FighterActor:
a figure on the far half (cell Y < 0) faces the board camera, on the near half it faces away):
  Medusa  T4UmFbxV1 (UM_FBX_v1, face +X, the same FBX bytes as the CLI run 20260928-cli-um-fbx-v1)  cell 2:2 (0,-50)
  Harpy   CLI run 20260928-cli-um-fbx-v1 x3, base MI InstanceIndex 1/2/3 (Silver)  cells 3:2, 2:1, 1:2
  Arthur  CLI run 20260928-cli-um-fbx-v1 (Gold)                                     cell 2:3 (0,50)
  Merlin  CLI run 20260928-cli-um-fbx-v1 (Gold)                                     cell 3:3 (100,50)
  Barrel  static candidate 20260928-p15-barrel, decor on the right wooden rim (x 264, y -200), off the cells; its z is
          the top of the rim under its bottom footprint, measured by the build (place_on_surface in ue_py, 5.0 uu on
          the Cobble board) -- never a hard-coded 0 (review fix: at z 0 the barrel sank 5 uu into the rim)
Animation test: Medusa T4LocalPass (+Y rest pose, the skeleton the draft clips were imported on, T2.1) replaces the
static Medusa on its cell; AM_Medusa_LungeAttack_Draft at 0/25/50/75/100 %.
Masks (not evidence JPEGs): every subject alone without shadows against the empty board (K1, K2 1.6x silhouettes);
for figures also 5x base see-through masks (review fix): empty board / figure + base / base alone, then the same three
with the Cobble static meshes (BOARD_PREFIX) hidden, so holes in the top of a base show the editor void (0,0,0).
For figures also the base alone at K2 1.6x (mask-k2-1p6-base-<name>, W4-B review fix): review/team_contrast.py splits
the K2 1.6x silhouette into the visible figure and the base band with it.

Camera = UpdateBoardCamera of the packaged client (S08FlowGameMode.cpp): horizontal FOV 35 (temporary CameraActor piloted
by the level viewport, MaintainXFOV), pitch -55, yaw -90, location = focus + (0, D cos55, D sin55). K1 overview focus
(0,0,0) D 1931; K2 focus = cell + 28 uu, D 1207 (1.6x) and 386 (5x). Exposure: unbound post-process volume, histogram
clamped to EV100 1.3 (min = max brightness = 2^1.3, bias 0; calibrated against the viewport's fixed EV100 1.3, see
EXPOSURE_LUMINANCE), viewport exposure "Game settings". Editor grid, sprites and volume wireframes off (ShowFlag.Grid /
BillboardSprites / Volumes 0, restored with 2 = no override).
CaptureViewport returns the viewport size; the frame is the centred 16:9 crop resized to 1920x1080 (horizontal FOV kept).

EDITOR frames: *-ue-editor.png with a sidecar <stem>.evidence.json (unmatched.evidence-frame/1, class
editor-mcp-viewport): diagnostics and QA-009 rows, never K1/K2 acceptance.

Asset sets (--asset-set, W4-B 2026-09-29): "w4b" (default) = the CLI runs 20260929-w4b-um-master of Medusa, Arthur,
Merlin, Harpy and the barrel, all on MI of the UM masters (M_UM_Figure / M_UM_BaseMarker), team colour on the base band
and the clothing (TeamMask); "t31" = the stage-3 T3.1 assets (own atlas materials; Medusa T4UmFbxV1), kept so the
before frames of W4-B can be re-shot. In the w4b set the "team in grey" swap covers every figure slot and the base,
and a third frame per team subject shows the value-split palette proposal (team_palette.c11_value_split_proposal of
art/um-materials/um-masters.json: Silver #5A7F9F) through scene-owned MIs (TeamColor = FLinearColor::FromSRGBColor).
"""

import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ue_live import Ue  # noqa: E402

SCHEMA = "unmatched.p17-control-scene/1"
SIDECAR_SCHEMA = "unmatched.evidence-frame/1"
FOLDER = "/Game/ArtTests/P17ControlScene"
LEVEL = FOLDER + "/L_P17ControlScene"
SOURCE_LEVEL = "/Game/ArtTests/ART005H/L_ART005H_CornerReview"
MI_DIR = FOLDER + "/Materials"
PC = "/Game/PipelineCandidates"
MEDUSA_UM = PC + "/Medusa/T4UmFbxV1/Meshes/"
MEDUSA_LP = PC + "/Medusa/T4LocalPass/Meshes/"
CLIPS = PC + "/Medusa/DraftClips20260928/T4LocalPass"
HERO = {"arthur": PC + "/KingArthur/20260928-cli-um-fbx-v1", "merlin": PC + "/Merlin/20260928-cli-um-fbx-v1",
        "harpy": PC + "/Harpy/20260928-cli-um-fbx-v1"}
BARREL = PC + "/DecorBarrel/20260928-p15-barrel/Candidate/Meshes/SM_Decor_Barrel"

FOV, PITCH, YAW = 35.0, -55.0, -90.0
K1, K2_1P6, K2_5X, FOCUS_Z = 1931.0, 1207.0, 386.0, 28.0
EV100 = 1.3
# Histogram min = max brightness that reproduces the viewport's fixed "EV100 1.3" (head-tilt v3 A1 method): measured
# 2026-09-28 by bisection on the K1 frame of this level (mean RGB of the board ROI 124.03 vs 124.00 with the viewport
# fixed at EV100 1.3 and the volume disabled; evidence p17-control-scene-2026-09-28/exposure-calibration.json). The match
# is 2^EV100 = 2.4623 (ExtendDefaultLuminanceRange is off, so the brightness is a luminance); 1.2/LensAttenuation *
# 2^EV100 = 3.788 gave a frame 0.9 stop darker.
EXPOSURE_LUMINANCE = round(2 ** EV100, 5)
NOANN = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0, "classFilter": None, "maxLabels": 0}
# editor-only overlays hidden in the frames (console show-flag overrides; restored with value 2 = no override)
SHOW_FLAGS_OFF = ("Grid", "BillboardSprites", "Volumes")
BOARD_PREFIX = "ART005"  # static-mesh actors copied from the Cobble level (board, zones, glyphs, corners, click surfaces)
L_CAMERA = "P17 board camera FOV35 - temporary"
L_ANIM, L_ANIM_BASE = "P17 Medusa T4LocalPass anim - temporary", "P17 Medusa T4LocalPass anim base - temporary"
LUNGE = CLIPS + "/AM_Medusa_LungeAttack_Draft"
LUNGE_LENGTH_S = 0.5833333  # 14 frames at 24 fps (ue-anim-report.json of T2.1)
ANIM_POINTS = ["SKEL_Medusa", "root", "hand_L", "weapon", "head", "Weapon", "Head"]

# subject -> figure/base actors, cell, facing rule, team material swap for the "team in grey" frame
SUBJECTS = {
    "medusa": {"cell": [2, 2], "yaw": 90, "figure": MEDUSA_UM + "SK_Medusa_Candidate",
               "base": MEDUSA_UM + "SM_Medusa_Base_Candidate",
               "team_alt": {"figure": {"0": PC + "/Medusa/T4UmFbxV1/Materials/MI_Medusa_Candidate_Red"},
                            "base": {"0": PC + "/Medusa/T4UmFbxV1/Materials/MI_Medusa_Candidate_Red"}}},
    "harpy1": {"cell": [3, 2], "yaw": 90, "figure": HERO["harpy"] + "/Meshes/SK_Harpy_Candidate",
               "base": HERO["harpy"] + "/Meshes/SM_Harpy_Base_Candidate", "base_materials": {"0": MI_DIR + "/MI_P17_Harpy_Base_H1"}},
    "harpy2": {"cell": [2, 1], "yaw": 90, "figure": HERO["harpy"] + "/Meshes/SK_Harpy_Candidate",
               "base": HERO["harpy"] + "/Meshes/SM_Harpy_Base_Candidate", "base_materials": {"0": MI_DIR + "/MI_P17_Harpy_Base_H2"},
               "team_alt": {"base": {"0": MI_DIR + "/MI_P17_Harpy_Base_H2_Gold"}}},
    "harpy3": {"cell": [1, 2], "yaw": 90, "figure": HERO["harpy"] + "/Meshes/SK_Harpy_Candidate",
               "base": HERO["harpy"] + "/Meshes/SM_Harpy_Base_Candidate", "base_materials": {"0": MI_DIR + "/MI_P17_Harpy_Base_H3"}},
    "arthur": {"cell": [2, 3], "yaw": -90, "figure": HERO["arthur"] + "/Meshes/SK_KingArthur_Candidate",
               "base": HERO["arthur"] + "/Meshes/SM_KingArthur_Base_Candidate",
               "team_alt": {"figure": {"0": HERO["arthur"] + "/Materials/MI_KingArthur_Candidate_Silver"},
                            "base": {"0": HERO["arthur"] + "/Materials/MI_KingArthur_Candidate_Silver"}}},
    "merlin": {"cell": [3, 3], "yaw": -90, "figure": HERO["merlin"] + "/Meshes/SK_Merlin_Candidate",
               "base": HERO["merlin"] + "/Meshes/SM_Merlin_Base_Candidate",
               "team_alt": {"figure": {"0": HERO["merlin"] + "/Materials/MI_Merlin_Candidate_Silver"},
                            "base": {"0": HERO["merlin"] + "/Materials/MI_Merlin_Candidate_Silver"}}},
    "barrel": {"location": [264.0, -200.0, None], "yaw": 0, "static": BARREL, "place_on_surface": True,
               "placement": "decor on the right wooden rim (board 556 x 656 uu, cells 500 x 600), off the cells; "
                            "03 §4.4 / ART-009: decor does not cover cells; z = top of the rim under the bottom "
                            "footprint (measured by the build, decor_support)"},
}
MATERIAL_INSTANCES = [
    {"path": MI_DIR + "/MI_P17_Harpy_Base_H%d" % i, "parent": HERO["harpy"] + "/Materials/MI_Harpy_Candidate_Silver",
     "scalars": {"InstanceIndex": i}} for i in (1, 2, 3)] + [
    {"path": MI_DIR + "/MI_P17_Harpy_Base_H2_Gold", "parent": HERO["harpy"] + "/Materials/MI_Harpy_Candidate_Gold",
     "scalars": {"InstanceIndex": 2}}]
ASSET_SETS = {"t31": {"subjects": SUBJECTS, "material_instances": MATERIAL_INSTANCES, "barrel": BARREL}}

# ---- W4-B asset set: CLI runs 20260929-w4b-um-master on the UM masters
W4B_RUN = "20260929-w4b-um-master"
W4B = {"medusa": PC + "/Medusa/" + W4B_RUN, "arthur": PC + "/KingArthur/" + W4B_RUN, "merlin": PC + "/Merlin/" + W4B_RUN,
       "harpy": PC + "/Harpy/" + W4B_RUN}
W4B_SHORT = {"medusa": "Medusa", "arthur": "KingArthur", "merlin": "Merlin", "harpy": "Harpy"}
W4B_BARREL = PC + "/DecorBarrel/" + W4B_RUN + "/Candidate/Meshes/SM_Decor_Barrel"
UM_SPEC = Path(__file__).resolve().parents[3] / "art" / "um-materials" / "um-masters.json"


def srgb_hex_linear(hex_color):
    """FLinearColor::FromSRGBColor of '#RRGGBB' (the rule of art/um-materials/um-masters.json, AD-OPEN-39)."""
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(round(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4, 6))
    return out + [1.0]


def w4b_asset_set():
    proposal = json.loads(UM_SPEC.read_text(encoding="utf-8"))["team_palette"]["c11_value_split_proposal"]["Silver"]
    prop_lin = srgb_hex_linear(proposal)

    def mats(hero, kind, team):
        short = W4B_SHORT[hero]
        return W4B[hero] + "/Materials/MI_%s%s_Candidate_%s" % (short, "_Base" if kind == "base" else "", team)

    def fig(hero, name):
        return W4B[hero] + "/Meshes/%s_%s_Candidate" % (name, W4B_SHORT[hero])

    subjects = {
        # far half: Silver (default team of Medusa and the Harpies), near half: Gold (Arthur, Merlin)
        "medusa": {"cell": [2, 2], "yaw": 90, "figure": fig("medusa", "SK"),
                   "base": W4B["medusa"] + "/Meshes/SM_Medusa_Base_Candidate", "team": "Silver",
                   "team_alt": {"figure": {"0": mats("medusa", "figure", "Gold"), "1": mats("medusa", "figure", "Gold")},
                                "base": {"0": mats("medusa", "base", "Gold")}},
                   "team_prop": {"figure": {"0": MI_DIR + "/MI_P17_medusa_Figure_Prop", "1": MI_DIR + "/MI_P17_medusa_Figure_Prop"},
                                 "base": {"0": MI_DIR + "/MI_P17_medusa_Base_Prop"}}},
        "harpy1": {"cell": [3, 2], "yaw": 90, "figure": fig("harpy", "SK"),
                   "base": W4B["harpy"] + "/Meshes/SM_Harpy_Base_Candidate", "team": "Silver",
                   "base_materials": {"0": MI_DIR + "/MI_P17_Harpy_Base_H1"}},
        "harpy2": {"cell": [2, 1], "yaw": 90, "figure": fig("harpy", "SK"),
                   "base": W4B["harpy"] + "/Meshes/SM_Harpy_Base_Candidate", "team": "Silver",
                   "base_materials": {"0": MI_DIR + "/MI_P17_Harpy_Base_H2"},
                   "team_alt": {"figure": {"0": mats("harpy", "figure", "Gold")},
                                "base": {"0": MI_DIR + "/MI_P17_Harpy_Base_H2_Gold"}},
                   "team_prop": {"figure": {"0": MI_DIR + "/MI_P17_harpy2_Figure_Prop"},
                                 "base": {"0": MI_DIR + "/MI_P17_harpy2_Base_Prop"}}},
        "harpy3": {"cell": [1, 2], "yaw": 90, "figure": fig("harpy", "SK"),
                   "base": W4B["harpy"] + "/Meshes/SM_Harpy_Base_Candidate", "team": "Silver",
                   "base_materials": {"0": MI_DIR + "/MI_P17_Harpy_Base_H3"}},
        "arthur": {"cell": [2, 3], "yaw": -90, "figure": fig("arthur", "SK"),
                   "base": W4B["arthur"] + "/Meshes/SM_KingArthur_Base_Candidate", "team": "Gold",
                   "team_alt": {"figure": {"0": mats("arthur", "figure", "Silver")},
                                "base": {"0": mats("arthur", "base", "Silver")}},
                   "team_prop": {"figure": {"0": MI_DIR + "/MI_P17_arthur_Figure_Prop"},
                                 "base": {"0": MI_DIR + "/MI_P17_arthur_Base_Prop"}}},
        "merlin": {"cell": [3, 3], "yaw": -90, "figure": fig("merlin", "SK"),
                   "base": W4B["merlin"] + "/Meshes/SM_Merlin_Base_Candidate", "team": "Gold",
                   "team_alt": {"figure": {"0": mats("merlin", "figure", "Silver")},
                                "base": {"0": mats("merlin", "base", "Silver")}},
                   "team_prop": {"figure": {"0": MI_DIR + "/MI_P17_merlin_Figure_Prop"},
                                 "base": {"0": MI_DIR + "/MI_P17_merlin_Base_Prop"}}},
        "barrel": dict(ASSET_SETS["t31"]["subjects"]["barrel"], static=W4B_BARREL),
    }
    instances = [{"path": MI_DIR + "/MI_P17_Harpy_Base_H%d" % i, "parent": mats("harpy", "base", "Silver"),
                  "scalars": {"InstanceIndex": i}} for i in (1, 2, 3)]
    instances.append({"path": MI_DIR + "/MI_P17_Harpy_Base_H2_Gold", "parent": mats("harpy", "base", "Gold"),
                      "scalars": {"InstanceIndex": 2}})
    for name, hero in (("medusa", "medusa"), ("harpy2", "harpy"), ("arthur", "arthur"), ("merlin", "merlin")):
        short = W4B_SHORT[hero]
        instances.append({"path": MI_DIR + "/MI_P17_%s_Figure_Prop" % name,
                          "parent": W4B[hero] + "/Materials/MI_%s_Candidate" % short,
                          "vectors": {"TeamColor": prop_lin}, "team_hex": proposal})
        base_mi = {"path": MI_DIR + "/MI_P17_%s_Base_Prop" % name,
                   "parent": W4B[hero] + "/Materials/MI_%s_Base_Candidate" % short,
                   "vectors": {"TeamColor": prop_lin}, "team_hex": proposal}
        if name == "harpy2":
            base_mi["scalars"] = {"InstanceIndex": 2}
        instances.append(base_mi)
    return {"subjects": subjects, "material_instances": instances, "barrel": W4B_BARREL,
            "team_proposal": {"Silver": proposal, "linear": prop_lin}}


def use_asset_set(name):
    """Point SUBJECTS / MATERIAL_INSTANCES / BARREL at an asset set (module globals used by the build and shots)."""
    global SUBJECTS, MATERIAL_INSTANCES, BARREL, FIGURES
    chosen = w4b_asset_set() if name == "w4b" else ASSET_SETS[name]
    SUBJECTS, MATERIAL_INSTANCES, BARREL = chosen["subjects"], chosen["material_instances"], chosen["barrel"]
    FIGURES = [k for k in SUBJECTS if k != "barrel"]
    return chosen


ASSET_SET = "w4b"
use_asset_set(ASSET_SET)


def cell_world(cell):
    """S08 FS08BoardModel::CellToWorld for a 5 x 6 board, cell 100 uu (ART005 HIT i:j = the same centres)."""
    return [cell[0] * 100.0 - 200.0, cell[1] * 100.0 - 250.0, 0.0]


def subject_location(name):
    """x, y of the subject (z of a decor subject = None until the build measures the surface it stands on)."""
    s = SUBJECTS[name]
    return list(s["location"]) if "location" in s else cell_world(s["cell"])


def labels(name):
    if name == "barrel":
        return ["P17 barrel"]
    return ["P17 %s figure" % name, "P17 %s base" % name]


def scene_spec(barrel_asset):
    actors = []
    for name, s in SUBJECTS.items():
        loc = subject_location(name)
        if name == "barrel":
            actors.append({"label": "P17 barrel", "kind": "static", "asset": barrel_asset, "location": loc, "yaw": s["yaw"],
                           "place_on_surface": {"exclude_label_prefixes": ["P17 "]}})
            continue
        actors.append({"label": "P17 %s figure" % name, "kind": "skeletal", "asset": s["figure"], "location": loc,
                       "yaw": s["yaw"], "materials": s.get("figure_materials")})
        actors.append({"label": "P17 %s base" % name, "kind": "static", "asset": s["base"], "location": loc,
                       "yaw": s["yaw"], "materials": s.get("base_materials")})
    return {"folder": FOLDER, "level": LEVEL, "source_level": SOURCE_LEVEL,
            "owned_packages": [LEVEL, LEVEL + "_BuiltData"] + [m["path"] for m in MATERIAL_INSTANCES],
            "material_instances": MATERIAL_INSTANCES,
            "remove_label_prefixes": ["ART004 Medusa", "ART005 gray ", "ART005C ", "ART005 K1 review camera"],
            "light_changes": [{"label": "ART005 neutral readability fill - review only", "location": [0, 100, 500],
                               "why": "stage-3 plan T3.1 Cobble stand: fill 700 at (0,100,500) (head-tilt v3 A1 act)"}],
            "exposure": {"label": "P17 exposure EV100 1.3 - fixed", "method": "AEM_HISTOGRAM", "bias": 0.0,
                         "min_max_brightness": EXPOSURE_LUMINANCE},
            "actors": actors}


def board_cam(focus, dist):
    p = math.radians(-PITCH)
    return [focus[0], focus[1] + dist * math.cos(p), focus[2] + dist * math.sin(p)], [PITCH, YAW, 0.0]


def focus_of(name):
    loc = subject_location(name)
    return [loc[0], loc[1], FOCUS_Z]


class Capture:
    def __init__(self, ue, out_dir, tag):
        self.ue, self.dir, self.tag = ue, out_dir, tag
        self.frames = {}

    def task(self, op, timeout=600, **kw):
        return self.ue.run_task(str(HERE / "ue_py" / "control_scene_ue.py"), str(self.dir / "_task.json"),
                                timeout=timeout, op=op, **kw)

    def grab(self, xform):
        cap = {"captureTransform": xform, "annotations": NOANN, "bShowUI": False}
        res = self.ue.call("app", "CaptureViewport", cap, record=False)
        v = res["value"] if isinstance(res, dict) and "value" in res else res
        img = v["image"] if isinstance(v, dict) and "image" in v else res["images"][0]
        return Image.open(io.BytesIO(base64.b64decode(img["data"]))).convert("RGB")

    def shot(self, name, focus, dist, meta):
        eye, rot = board_cam(focus, dist)
        cam = self.task("camera", label=L_CAMERA, location=eye, rotation=rot, fov=FOV)["camera"]
        xform = {"location": dict(zip("xyz", eye)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
                 "scale": {"x": 1, "y": 1, "z": 1}}
        time.sleep(0.5)
        # the first capture after a camera jump can be stale (T2.1): three captures 0.5 s apart, the third is kept;
        # the mean |dRGB| between consecutive captures is recorded (temporal AA/shadow noise of the live viewport)
        prev, settle = None, []
        for attempt in range(3):
            im = self.grab(xform)
            if prev is not None:
                settle.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
            prev = im
            if attempt < 2:
                time.sleep(0.5)
        w, h = im.size
        ch = round(w * 9 / 16)
        box = (0, (h - ch) // 2, w, (h - ch) // 2 + ch) if ch <= h else ((w - round(h * 16 / 9)) // 2, 0,
                                                                          (w + round(h * 16 / 9)) // 2, h)
        frame = im.crop(box).resize((1920, 1080), Image.LANCZOS)
        fname = "p17-%s-ue-editor.png" % name
        path = self.dir / fname
        frame.save(path, optimize=False)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        info = {"camera": cam, "focus": [round(v, 3) for v in focus], "distance_uu": dist, "viewport_px": [w, h],
                "crop_px": list(box), "output_px": [1920, 1080], "settle_mean_abs_diff": settle,
                "capture": "EditorAppToolset.CaptureViewport via MCP 127.0.0.1:8123 (piloted CameraActor, FOV 35 "
                           "horizontal, centred 16:9 crop resized to 1920x1080)",
                "exposure": "post-process volume, histogram clamped to EV100 %.1f (luminance %.5f), bias 0" % (EV100, EXPOSURE_LUMINANCE),
                **meta}
        side = {"schema": SIDECAR_SCHEMA, "class": "editor-mcp-viewport", "frameSha256": digest, "frame": fname,
                "label": "EDITOR frame (P1.7 control scene), diagnostic; not K1/K2 acceptance", "run_tag": self.tag, **info}
        path.with_name(path.stem + ".evidence.json").write_text(json.dumps(side, indent=1, sort_keys=True) + "\n",
                                                              encoding="utf-8", newline="\n")
        self.frames[fname] = dict(info, sha256=digest)
        print(" ", fname, digest[:12], "settle", settle)
        return fname


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--barrel", default=None, help="barrel static mesh (the repro run swaps in its own import)")
    ap.add_argument("--asset-set", choices=["w4b", "t31"], default="w4b",
                    help="w4b: CLI runs 20260929-w4b-um-master on the UM masters; t31: the stage-3 T3.1 assets")
    ap.add_argument("--skip-diagnostics", action="store_true")
    ap.add_argument("--only", choices=["main", "barrel"], default=None,
                    help="barrel: build + K1 and the barrel frames only (repro comparison)")
    a = ap.parse_args()
    chosen = use_asset_set(a.asset_set)
    a.barrel = a.barrel or BARREL
    out = (Path(a.out).resolve() / a.tag)
    out.mkdir(parents=True, exist_ok=True)
    ue = Ue()
    cap = Capture(ue, out, a.tag)
    started = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    original = ue.call("scene", "get_current_level", record=False)
    if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
    if original.split(".")[0] == LEVEL:
        raise SystemExit("the control level itself is open; open another level first")
    spec = scene_spec(a.barrel)
    report = {"schema": SCHEMA, "tag": a.tag, "started_at": started, "tool": "tools/tripo-pipeline/review/control_scene.py",
              "kind": "EDITOR control scene (live UnrealEditor via MCP); not packaged, no HUD, no boardState, not K1/K2 "
                      "acceptance", "original_level": original, "scene_spec": spec,
              "camera_model": {"fov_horizontal_deg": FOV, "pitch": PITCH, "yaw": YAW, "k1_uu": K1, "k2_1p6_uu": K2_1P6,
                               "k2_5x_uu": K2_5X, "focus_offset_z_uu": FOCUS_Z,
                               "source": "UpdateBoardCamera / SetupCameraForBoard (S08FlowGameMode.cpp)"},
              "exposure": {"ev100": EV100, "luminance": EXPOSURE_LUMINANCE,
                           "calibration": "equals the viewport fixed EV100 1.3 (exposure-calibration.json)"},
              "console": [], "asset_set": a.asset_set, "team_proposal": chosen.get("team_proposal"),
              "subject_teams": {n: s["team"] for n, s in SUBJECTS.items() if s.get("team")}}
    temp = [L_CAMERA, L_ANIM, L_ANIM_BASE]
    try:
        report["build"] = cap.task("build", timeout=900, scene=spec)
        for flag in SHOW_FLAGS_OFF:
            ue.console("ShowFlag.%s 0" % flag)
            report["console"].append("ShowFlag.%s 0" % flag)
        time.sleep(8.0)  # shader compile / texture streaming after the level load
        # warm-up: repeat the overview until it is stable (streaming), not kept
        eye, rot = board_cam([0, 0, 0], K1)
        cap.task("camera", label=L_CAMERA, location=eye, rotation=rot, fov=FOV)
        xform = {"location": dict(zip("xyz", eye)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
                 "scale": {"x": 1, "y": 1, "z": 1}}
        prev, warm = None, []
        for _ in range(20):
            im = cap.grab(xform)
            if prev is not None:
                d = float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean())
                warm.append(round(d, 4))
                if d < 0.02 and len(warm) >= 3:
                    break
            prev = im
            time.sleep(1.5)
        report["warmup_mean_abs_diff"] = warm

        main_frames = {}
        main_frames["k1-overview"] = cap.shot("k1-overview", [0.0, 0.0, 0.0], K1, {"subject": "overview", "set": "main"})
        subjects = ["barrel"] if a.only == "barrel" else list(SUBJECTS)
        for name in subjects:
            for tag, dist in (("k2-1p6", K2_1P6), ("k2-5x", K2_5X)):
                main_frames["%s-%s" % (tag, name)] = cap.shot("%s-%s" % (tag, name), focus_of(name), dist,
                                                               {"subject": name, "set": "main"})
        report["main_frames"] = main_frames
        diag = {}
        if not a.skip_diagnostics and a.only is None:
            # front / back at 5x: the subject faces the board camera (+Y, yaw 90 for a +X mesh) or away (yaw -90)
            for name in SUBJECTS:
                if name in ("harpy1", "harpy3"):
                    continue
                orig = SUBJECTS[name]["yaw"]
                for side, yaw in (("front", 90), ("back", -90)):
                    cap.task("set", changes=[{"label": lb, "yaw": yaw} for lb in labels(name)])
                    diag["%s-%s" % (side, name)] = cap.shot("%s-5x-%s" % (side, name), focus_of(name), K2_5X,
                                                            {"subject": name, "set": side, "yaw": yaw})
                cap.task("set", changes=[{"label": lb, "yaw": orig} for lb in labels(name)])
            # silhouettes: every subject alone, shadows off, against the empty board (K1 and its K2 1.6x)
            all_labels = [lb for n in SUBJECTS for lb in labels(n)]
            cap.task("set", changes=[{"label": lb, "visible": False} for lb in all_labels])
            diag["mask-k1-empty"] = cap.shot("mask-k1-empty", [0.0, 0.0, 0.0], K1, {"subject": "none", "set": "mask"})
            # base see-through (review fix): at 5x the empty board, the figure + base and the base alone (figure
            # hidden) as visual references; then the same three with the board actors hidden (the editor void renders
            # (0,0,0)): void pixels inside the projected top disc of the base = holes (control_scene_analyze.py)
            for name in SUBJECTS:
                diag["mask-k2-1p6-empty-%s" % name] = cap.shot("mask-k2-1p6-empty-%s" % name, focus_of(name), K2_1P6,
                                                               {"subject": "none", "set": "mask"})
                if name in FIGURES:
                    diag["mask-k2-5x-empty-%s" % name] = cap.shot("mask-k2-5x-empty-%s" % name, focus_of(name), K2_5X,
                                                                  {"subject": "none", "set": "mask"})
                cap.task("set", changes=[{"label": lb, "visible": True, "cast_shadow": False} for lb in labels(name)])
                diag["mask-k1-%s" % name] = cap.shot("mask-k1-%s" % name, [0.0, 0.0, 0.0], K1,
                                                     {"subject": name, "set": "mask", "cast_shadow": False})
                diag["mask-k2-1p6-%s" % name] = cap.shot("mask-k2-1p6-%s" % name, focus_of(name), K2_1P6,
                                                         {"subject": name, "set": "mask", "cast_shadow": False})
                if name in FIGURES:
                    diag["mask-k2-5x-%s" % name] = cap.shot("mask-k2-5x-%s" % name, focus_of(name), K2_5X,
                                                            {"subject": name, "set": "mask", "cast_shadow": False})
                    cap.task("set", changes=[{"label": "P17 %s figure" % name, "visible": False}])
                    diag["mask-k2-5x-base-%s" % name] = cap.shot("mask-k2-5x-base-%s" % name, focus_of(name), K2_5X,
                                                                 {"subject": name + " base", "set": "mask",
                                                                  "cast_shadow": False})
                    # base alone at K2 1.6x (W4-B review fix): team_contrast.py splits the silhouette into the figure
                    # (visible figure pixels) and the base band, so a team change of the base cannot hide an
                    # unchanged figure
                    diag["mask-k2-1p6-base-%s" % name] = cap.shot("mask-k2-1p6-base-%s" % name, focus_of(name),
                                                                  K2_1P6, {"subject": name + " base", "set": "mask",
                                                                           "cast_shadow": False})
                    cap.task("set", changes=[{"label_prefix": BOARD_PREFIX, "visible": False}])
                    try:
                        diag["mask-k2-5x-void-base-%s" % name] = cap.shot(
                            "mask-k2-5x-void-base-%s" % name, focus_of(name), K2_5X,
                            {"subject": name + " base", "set": "mask-void", "cast_shadow": False, "board": "hidden"})
                        cap.task("set", changes=[{"label": "P17 %s figure" % name, "visible": True}])
                        diag["mask-k2-5x-void-%s" % name] = cap.shot(
                            "mask-k2-5x-void-%s" % name, focus_of(name), K2_5X,
                            {"subject": name, "set": "mask-void", "cast_shadow": False, "board": "hidden"})
                        cap.task("set", changes=[{"label": lb, "visible": False} for lb in labels(name)])
                        diag["mask-k2-5x-void-empty-%s" % name] = cap.shot(
                            "mask-k2-5x-void-empty-%s" % name, focus_of(name), K2_5X,
                            {"subject": "none", "set": "mask-void", "board": "hidden"})
                    finally:
                        cap.task("set", changes=[{"label_prefix": BOARD_PREFIX, "visible": True}])
                cap.task("set", changes=[{"label": lb, "visible": False, "cast_shadow": True} for lb in labels(name)])
            cap.task("set", changes=[{"label": lb, "visible": True} for lb in all_labels])
            # team colour swapped (the "team in grey" check compares these with the main K2 1.6x frames)
            for name in SUBJECTS:
                alt = SUBJECTS[name].get("team_alt")
                if not alt:
                    continue
                ch = []
                if "figure" in alt:
                    ch.append({"label": "P17 %s figure" % name, "materials": alt["figure"]})
                if "base" in alt:
                    ch.append({"label": "P17 %s base" % name, "materials": alt["base"]})
                cap.task("set", changes=ch)
                diag["team-alt-%s" % name] = cap.shot("team-alt-k2-1p6-%s" % name, focus_of(name), K2_1P6,
                                                      {"subject": name, "set": "team-alt", "materials": alt})
                back = []
                for part in ("figure", "base"):
                    if part in alt:
                        mats = SUBJECTS[name].get(part + "_materials") or {}
                        back.append({"label": "P17 %s %s" % (name, part),
                                     "materials": {k: mats.get(k, report["build"]["actors"]["P17 %s %s" % (name, part)]
                                                                ["materials"][int(k)]["path"]) for k in alt[part]}})
                cap.task("set", changes=back)
            # value-split palette proposal (W4-B): the subject in the proposed Silver, compared with its Gold frame
            for name in SUBJECTS:
                prop = SUBJECTS[name].get("team_prop")
                if not prop:
                    continue
                ch = [{"label": "P17 %s %s" % (name, part), "materials": prop[part]} for part in ("figure", "base")
                      if part in prop]
                cap.task("set", changes=ch)
                diag["team-prop-%s" % name] = cap.shot("team-prop-k2-1p6-%s" % name, focus_of(name), K2_1P6,
                                                       {"subject": name, "set": "team-prop", "materials": prop,
                                                        "team_hex": (chosen.get("team_proposal") or {}).get("Silver")})
                back = []
                for part in ("figure", "base"):
                    if part in prop:
                        mats = SUBJECTS[name].get(part + "_materials") or {}
                        back.append({"label": "P17 %s %s" % (name, part),
                                     "materials": {k: mats.get(k, report["build"]["actors"]["P17 %s %s" % (name, part)]
                                                                ["materials"][int(k)]["path"]) for k in prop[part]}})
                cap.task("set", changes=back)
            # animation test: T4LocalPass (rest pose +Y) on Medusa's cell with LungeAttack
            loc = subject_location("medusa")
            cap.task("set", changes=[{"label": lb, "visible": False} for lb in labels("medusa")])
            ue.run_task(str(HERE / "ue_py" / "frames_scene.py"), str(out / "_task.json"), timeout=300, op="setup",
                        actors=[{"label": L_ANIM, "kind": "skeletal", "asset": MEDUSA_LP + "SK_Medusa_Candidate",
                                 "location": loc, "yaw": 0},
                                {"label": L_ANIM_BASE, "kind": "static", "asset": MEDUSA_LP + "SM_Medusa_Base_Candidate",
                                 "location": loc, "yaw": 0}])
            anim = {"clip": LUNGE, "length_s": LUNGE_LENGTH_S, "actor_location": loc, "poses": []}
            for pct in (0, 25, 50, 75, 100):
                t = round(LUNGE_LENGTH_S * pct / 100.0, 6)
                cap.task("pose", label=L_ANIM, anim=LUNGE, time=t)
                time.sleep(0.8)
                pts = cap.task("bones", label=L_ANIM, names=ANIM_POINTS)
                frames = {}
                for tag, dist in (("k2-1p6", K2_1P6), ("k2-5x", K2_5X)):
                    frames[tag] = cap.shot("anim-lunge-p%03d-%s" % (pct, tag), focus_of("medusa"), dist,
                                           {"subject": "medusa T4LocalPass + %s" % LUNGE, "set": "anim",
                                            "percent": pct, "time_s": t})
                anim["poses"].append({"percent": pct, "time_s": t, "points": pts, "frames": frames})
            report["anim_test"] = anim
            cap.task("set", changes=[{"label": lb, "visible": True} for lb in labels("medusa")])
        report["diagnostic_frames"] = diag
    finally:
        try:
            report["cleanup"] = cap.task("cleanup", labels=temp)
        except Exception as exc:  # noqa: BLE001 - keep restoring
            report["cleanup_error"] = str(exc)
        try:
            for flag in SHOW_FLAGS_OFF:
                ue.console("ShowFlag.%s 2" % flag)  # 2 = no override (editor default)
                report["console"].append("ShowFlag.%s 2" % flag)
        except Exception as exc:  # noqa: BLE001
            report["console_error"] = str(exc)
        ue.call("scene", "load_level", {"level_path": original.split(".")[0]})
        time.sleep(2.0)
        report["restored_level"] = ue.call("scene", "get_current_level", record=False)
        report["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": report["restored_level"]}, record=False)
        report["control_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False)
        report["frames"] = cap.frames
        report["finished_at"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        tmp = out / "_task.json"
        if tmp.exists():
            tmp.unlink()
        (out / "control-scene-report.json").write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
                                                       + "\n", encoding="utf-8", newline="\n")
        print("restored:", report["restored_level"], "dirty:", report["restored_level_dirty"])


if __name__ == "__main__":
    main()
