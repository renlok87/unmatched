"""Editor frames K-1/K-2 of the barrel candidate and of the draft clip poses (stage 3 T2.1), LIVE editor.

    python tools/tripo-pipeline/review/p1_editor_frames.py --out <dir>

EDITOR frames (level-editor viewport through MCP EditorAppToolset.CaptureViewport), not the packaged
game: no HUD, no boardState, review-level light, not K1/K2 acceptance. Every PNG is named
*-ue-editor-*.png and has a sidecar <stem>.evidence.json (schema unmatched.evidence-frame/1,
class editor-mcp-viewport) for tools/art/classify_evidence.py.

Camera model = UpdateBoardCamera of the packaged client (S08FlowGameMode.cpp; stage-3 plan T3.1):
horizontal FOV 35 (a temporary CameraActor piloted by the viewport), pitch -55, yaw -90, distance
1931 uu (K-1) / 1207 uu (K-2, 1.6x), target = actor + 28 uu. The viewport image is cropped to 16:9
around its centre (horizontal FOV kept, like MaintainXFOV) and resized to 1920x1080. "close" frames
(300 uu, same angles) and the +X side view of the barrel are diagnostics only.

Nothing is saved: the refusal to start on a dirty level, temporary actors in the review level,
cleanup and reload of the previous level follow capture_ue_review.py.
"""

import argparse
import base64
import hashlib
import io
import json
import math
import sys
import time
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ue_live import Ue  # noqa: E402

REVIEW_LEVEL = "/Game/ArtTests/ART004/L_ART004_MedusaAnimationReview"
BARREL = "/Game/PipelineCandidates/DecorBarrel/20260928-p15-barrel/Candidate/Meshes/SM_Decor_Barrel"
MEDUSA = "/Game/PipelineCandidates/Medusa/T4LocalPass/Meshes/SK_Medusa_Candidate"
CLIPS = "/Game/PipelineCandidates/Medusa/DraftClips20260928/T4LocalPass"
NOANN = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0, "classFilter": None,
         "maxLabels": 0}
SIDECAR_SCHEMA = "unmatched.evidence-frame/1"
FOV, PITCH, YAW, K1, K2, FOCUS_Z, CLOSE = 35.0, -55.0, -90.0, 1931.0, 1207.0, 28.0, 300.0
L_BARREL, L_MEDUSA, L_CAMERA = "T21 barrel candidate - temporary", "T21 Medusa T4LocalPass - temporary", \
    "T21 board camera FOV35 - temporary"
POS_BARREL, POS_MEDUSA = (-200.0, 250.0, 0.0), (-100.0, 250.0, 0.0)


def board_cam(target, dist):
    p, y = math.radians(PITCH), math.radians(YAW)
    fwd = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))
    return [target[i] - fwd[i] * dist for i in range(3)], [PITCH, YAW, 0.0]


def look(eye, target):
    dx, dy, dz = (target[i] - eye[i] for i in range(3))
    return list(eye), [math.degrees(math.atan2(dz, math.hypot(dx, dy))), math.degrees(math.atan2(dy, dx)), 0.0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_task.json"
    ue = Ue()
    task = HERE / "ue_py" / "frames_scene.py"

    def scene(op, **kw):
        return ue.run_task(str(task), str(tmp), timeout=300, op=op, **kw)

    original = ue.call("scene", "get_current_level", record=False)
    if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
    meta = {"kind": "editor viewport frames (live UnrealEditor via MCP CaptureViewport); NOT packaged, no HUD, "
                    "no boardState, not K1/K2 acceptance",
            "level": REVIEW_LEVEL, "original_level": original,
            "camera_model": {"fov_horizontal_deg": FOV, "pitch": PITCH, "yaw": YAW, "k1_uu": K1, "k2_1p6_uu": K2,
                             "focus_offset_z_uu": FOCUS_Z, "source": "UpdateBoardCamera (S08FlowGameMode.cpp), "
                             "via a piloted CameraActor; crop 16:9 keeps the horizontal FOV"},
            "actors": {"barrel": {"asset": BARREL, "location": POS_BARREL, "yaw": 0},
                       "medusa": {"asset": MEDUSA, "location": POS_MEDUSA, "yaw": 0,
                                  "note": "T4LocalPass faces +Y (towards the board camera at yaw -90)"}},
            "frames": {}}
    labels = [L_BARREL, L_MEDUSA, L_CAMERA]
    try:
        ue.call("scene", "load_level", {"level_path": REVIEW_LEVEL})
        time.sleep(2.0)
        meta["setup"] = scene("setup", actors=[
            {"label": L_BARREL, "kind": "static", "asset": BARREL, "location": POS_BARREL, "yaw": 0},
            {"label": L_MEDUSA, "kind": "skeletal", "asset": MEDUSA, "location": POS_MEDUSA, "yaw": 0},
            {"label": L_CAMERA, "kind": "camera", "location": [0, 0, 500], "yaw": 0, "fov": FOV}])
        time.sleep(3.0)  # texture streaming / shader compile

        def shot(name, eye, rot, extra):
            cam = scene("camera", label=L_CAMERA, location=eye, rotation=rot)
            time.sleep(0.6)
            xform = {"location": dict(zip("xyz", eye)), "rotation": dict(zip(("pitch", "yaw", "roll"), rot)),
                     "scale": {"x": 1, "y": 1, "z": 1}}
            cap = {"captureTransform": xform, "annotations": NOANN, "bShowUI": False}
            ue.call("app", "CaptureViewport", cap, record=False)
            time.sleep(0.4)  # the first capture after a camera jump can be stale; keep the second
            res = ue.call("app", "CaptureViewport", cap, record=False)
            if isinstance(res, dict) and "value" in res and "images" in res:
                v = res["value"]
                img = v["image"] if isinstance(v, dict) and "image" in v else res["images"][0]
            else:
                img = res["image"]
            raw = base64.b64decode(img["data"])
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            w, h = im.size
            ch = round(w * 9 / 16)
            if ch <= h:
                box = (0, (h - ch) // 2, w, (h - ch) // 2 + ch)
            else:
                cw = round(h * 16 / 9)
                box = ((w - cw) // 2, 0, (w - cw) // 2 + cw, h)
            im = im.crop(box).resize((1920, 1080), Image.LANCZOS)
            path = out / ("%s.png" % name)
            im.save(path, optimize=False)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            info = {"camera": cam["camera"], "viewport_px": [w, h], "crop_px": list(box), "output_px": [1920, 1080],
                    "capture": "EditorAppToolset.CaptureViewport via MCP 127.0.0.1:8123 (piloted CameraActor)",
                    **extra}
            side = {"schema": SIDECAR_SCHEMA, "class": "editor-mcp-viewport", "frameSha256": digest,
                    "frame": path.name, "label": "EDITOR frame, diagnostic; not K1/K2 acceptance", **info}
            path.with_name(path.stem + ".evidence.json").write_text(json.dumps(side, indent=1, sort_keys=True) + "\n",
                                                                  encoding="utf-8", newline="\n")
            meta["frames"][path.name] = dict(info, sha256=digest)
            print(path.name, digest[:12])

        tb = [POS_BARREL[0], POS_BARREL[1], FOCUS_Z]
        for tag, dist in (("k1", K1), ("k2-1p6", K2), ("close300", CLOSE)):
            eye, rot = board_cam(tb, dist)
            shot("barrel-%s-ue-editor-cobble" % tag, eye, rot, {"subject": "barrel", "distance_uu": dist})
        eye, rot = look((POS_BARREL[0] + 60, POS_BARREL[1], 30), (POS_BARREL[0], POS_BARREL[1], 13))
        shot("barrel-side-plusX-close-ue-editor", eye, rot, {"subject": "barrel", "note": "looks from +X at the "
             "barrel: the bung faces the camera if the front is +X"})
        tm = [POS_MEDUSA[0], POS_MEDUSA[1], FOCUS_Z]
        for clip, frames in (("LungeAttack", (0, 6, 14)), ("HitReact", (0, 3, 9))):
            for f in frames:
                t = f / 24.0
                scene("pose", label=L_MEDUSA, anim="%s/AM_Medusa_%s_Draft" % (CLIPS, clip), time=t)
                time.sleep(0.8)
                pose = scene("sockets", label=L_MEDUSA)["pose"]
                for tag, dist in (("k2-1p6", K2), ("close300", CLOSE)):
                    eye, rot = board_cam(tm, dist)
                    shot("clip-%s-f%02d-%s-ue-editor" % (clip.lower(), f, tag), eye, rot,
                         {"subject": "AM_Medusa_%s_Draft frame %d (%.4f s)" % (clip, f, t), "pose": pose,
                          "distance_uu": dist})
    finally:
        try:
            meta["cleanup"] = scene("cleanup", labels=labels)
        except Exception as exc:  # noqa: BLE001 - report and continue restoring the level
            meta["cleanup_error"] = str(exc)
        ue.call("scene", "load_level", {"level_path": original})
        time.sleep(2.0)
        meta["restored_level"] = ue.call("scene", "get_current_level", record=False)
        meta["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": meta["restored_level"]}, record=False)
        meta["review_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": REVIEW_LEVEL}, record=False)
        if tmp.exists():
            tmp.unlink()
        (out / "editor-frames.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                                                newline="\n")
        print("restored:", meta["restored_level"], "dirty:", meta["restored_level_dirty"],
              "review level dirty:", meta["review_level_dirty_after_reload"])


if __name__ == "__main__":
    main()
