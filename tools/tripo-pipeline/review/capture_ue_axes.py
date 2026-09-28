"""Host driver: prove in the LIVE UnrealEditor which world axis a skeletal candidate faces.

    python tools/tripo-pipeline/review/capture_ue_axes.py --run-dir <run> --out <dir>
        [--level /Game/ArtTests/ART004/L_ART004_MedusaAnimationReview]
        [--reference /Game/ART004/Medusa/Meshes/SK_Medusa_Atlas --reference-base /Game/ART004/Medusa/Meshes/SM_Medusa_Base]
        [--spot -600,250]

Measurement (numbers, not only pictures): the candidate's face has its own material slot (profile
materials.face_slot). A temporary actor of the candidate (yaw 0, no rotation) is captured from the
four horizontal directions +X, -X, +Y, -Y, each time twice: with its normal team material and with
the face slot overridden (component OverrideMaterials, the asset is not touched) by a scratch
material instance whose TeamColor is black. The pixels that turn dark are the face pixels visible
from that direction. The face points to the direction with by far the most such pixels.
Frames: the candidate alone from the four directions (normal + face-probe), and pairs with the
read-only production asset: both yaw 0 from +X and from +Y, and the production asset at yaw -90
(the in-game compensation a +Y-facing mesh would need) from +X.

Isolation: refuses when the open level has unsaved changes or the scratch folder exists; works in
the review level without saving; the scratch folder /Game/PipelineCandidates/_<Run>AxesProbe holds
only the probe material instance and is deleted afterwards; temporary actors are removed and the
previously open level is loaded again. Frames are EDITOR frames (level viewport, FOV 90, review
level light, black void around the board): not packaged, no HUD, not art acceptance.
"""

import argparse
import base64
import io
import json
import time
from pathlib import Path

import capture_ue_review as cur
from capture_ue_review import call, look, xf

cur.TS.update({"instance": "editor_toolset.toolsets.material_instance.MaterialInstanceTools",
               "object": "editor_toolset.toolsets.object.ObjectTools"})

try:
    from PIL import Image
    import numpy as np
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow and numpy are required: %s" % exc)

NOANN = cur.NOANN
DIRECTIONS = {"+X": (1, 0), "-X": (-1, 0), "+Y": (0, 1), "-Y": (0, -1)}
FILE_TAG = {"+X": "plus-x", "-X": "minus-x", "+Y": "plus-y", "-Y": "minus-y"}
DARKEN_THRESHOLD = 40  # 0..255, mean-RGB drop of a pixel when the face slot turns black


def obj_path(package):
    return "%s.%s" % (package, package.rsplit("/", 1)[-1])


def capture(cam):
    call("app", "CaptureViewport", {"captureTransform": cam, "annotations": NOANN, "bShowUI": False})
    time.sleep(0.4)  # the first capture after a camera jump can be stale; keep the second
    res = call("app", "CaptureViewport", {"captureTransform": cam, "annotations": NOANN, "bShowUI": False})
    raw = base64.b64decode(res["image"]["data"])
    return raw, {k: v for k, v in res.items() if k != "image"}


def save_frame(raw, path, width):
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img.save(path, quality=92)
    return {"file": path.name, "bytes": path.stat().st_size, "size": list(img.size)}


def darkened(before, after):
    a = np.asarray(Image.open(io.BytesIO(before)).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(io.BytesIO(after)).convert("RGB"), dtype=np.int16)
    drop = a.mean(axis=2) - b.mean(axis=2)
    mask = drop > DARKEN_THRESHOLD
    ys, xs = np.nonzero(mask)
    box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
    return {"pixels": int(mask.sum()), "bbox_px": box, "frame_px": [int(a.shape[1]), int(a.shape[0])]}


def place(asset, label, x, y, yaw=0.0):
    actor = call("scene", "add_to_scene_from_asset", {"asset_path": asset, "name": label, "xform": xf(x, y, 0, yaw),
                                                      "parent": None, "snap_to_ground": False})
    call("actor", "set_label", {"actor": actor, "label": label})
    return actor


def skeletal_component(actor):
    for comp in call("actor", "get_components", {"actor": actor}) or []:
        cls = str(call("object", "get_class", {"instance": comp}))
        if "SkeletalMeshComponent" in cls:
            return comp
    raise RuntimeError("no SkeletalMeshComponent on %s" % actor)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--level", default="/Game/ArtTests/ART004/L_ART004_MedusaAnimationReview")
    ap.add_argument("--reference", default="/Game/ART004/Medusa/Meshes/SK_Medusa_Atlas")
    ap.add_argument("--reference-base", default="/Game/ART004/Medusa/Meshes/SM_Medusa_Base")
    ap.add_argument("--spot", default="-600,250", help="x,y of the candidate: off the board, black void around")
    ap.add_argument("--width", type=int, default=1200, help="saved frame width (metrics use the full capture)")
    args = ap.parse_args()
    run = Path(args.run_dir).resolve()
    report = json.loads((run / "reports/ue-import-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    build = json.loads((run / "reports/build-report.json").read_text(encoding="utf-8"))
    names = report["destination"]["assets"]
    face_slot = build["materials"]["face_slot"]["material"]
    slots = report["checks"]["skeletal_material_slots"]["measured"]["slots"]
    blue = next(v for k, v in names.items() if k.startswith("instance:") and k.endswith("_Blue"))
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    x0, y0 = (float(v) for v in args.spot.split(","))
    probe_folder = "/Game/PipelineCandidates/_%sAxesProbe" % "".join(p.title() for p in manifest["run_id"].split("-")[1:])
    probe_mi = probe_folder + "/MI_FaceProbe_Black"

    original_level = call("scene", "get_current_level")
    if call("asset", "is_dirty", {"asset_path": original_level}):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original_level)
    if call("asset", "exists", {"path": probe_folder}):
        raise SystemExit("scratch folder %s exists; refusing" % probe_folder)
    meta = {"kind": "editor viewport frames + face-slot darkening measurement (live UnrealEditor, unreal-mcp "
                    "CaptureViewport); not packaged, no HUD/boardState, not art acceptance",
            "level": args.level, "original_level": original_level, "candidate": names["skeletal"],
            "reference": args.reference, "face_slot": face_slot, "slots": slots,
            "darken_threshold_mean_rgb": DARKEN_THRESHOLD, "spot": [x0, y0], "frames": {}, "face_probe": {}}
    placed = []
    try:
        call("scene", "load_level", {"level_path": args.level})
        time.sleep(2.0)
        call("instance", "create", {"folder_path": probe_folder, "asset_name": "MI_FaceProbe_Black",
                                    "parent": {"refPath": obj_path(names["material"])}})
        call("instance", "set_vector_parameter", {"instance": {"refPath": obj_path(probe_mi)}, "name": "TeamColor",
                                                  "value": {"r": 0, "g": 0, "b": 0, "a": 1}})
        # ---- pass 1: the candidate alone, yaw 0, four directions, normal vs face slot black
        cand = place(names["skeletal"], "axes probe candidate - temporary", x0, y0)
        placed.append(cand)
        placed.append(place(names["base"], "axes probe candidate base - temporary", x0, y0))
        comp = skeletal_component(cand)
        normal = [obj_path(blue)] * len(slots)
        probe = [obj_path(probe_mi) if s == face_slot else obj_path(blue) for s in slots]
        time.sleep(3.0)  # shader/texture streaming
        for tag, (dx, dy) in DIRECTIONS.items():
            cam = look((x0 + dx * 52, y0 + dy * 52, 34), (x0, y0, 29))
            call("object", "set_properties", {"instance": comp, "values": json.dumps({"OverrideMaterials": normal})})
            time.sleep(0.5)
            raw_n, info_n = capture(cam)
            call("object", "set_properties", {"instance": comp, "values": json.dumps({"OverrideMaterials": probe})})
            time.sleep(0.8)
            raw_p, _ = capture(cam)
            name = FILE_TAG[tag]
            meta["face_probe"][tag] = darkened(raw_n, raw_p)
            meta["frames"]["ue-axes-candidate-from-%s.jpg" % name] = dict(
                save_frame(raw_n, out / ("ue-axes-candidate-from-%s.jpg" % name), args.width), camera=cam, **info_n)
            meta["frames"]["ue-axes-candidate-faceprobe-from-%s.jpg" % name] = dict(
                save_frame(raw_p, out / ("ue-axes-candidate-faceprobe-from-%s.jpg" % name), args.width), camera=cam)
            print(tag, meta["face_probe"][tag])
        call("object", "set_properties", {"instance": comp, "values": json.dumps({"OverrideMaterials": normal})})
        meta["candidate_actor_transform"] = call("actor", "get_actor_transform", {"actor": cand})
        # ---- pass 2: pairs with the read-only production asset
        ref = place(args.reference, "axes probe production - temporary", x0, y0 + 100)
        ref_base = place(args.reference_base, "axes probe production base - temporary", x0, y0 + 100)
        placed += [ref, ref_base]
        time.sleep(3.0)
        pairs = [("ue-axes-pair-from-plus-x.jpg", look((x0 + 140, y0 + 50, 36), (x0, y0 + 50, 28)),
                  "production (left, y=%g) and candidate (right, y=%g), both yaw 0, camera on +X looking -X "
                  "(image right = world -Y)" % (y0 + 100, y0))]
        for frame, cam, note in pairs:
            raw, info = capture(cam)
            meta["frames"][frame] = dict(save_frame(raw, out / frame, args.width), camera=cam, note=note, **info)
        for actor in (ref, ref_base):
            call("actor", "set_actor_transform", {"actor": actor, "xform": xf(x0 - 100, y0, 0)})
        time.sleep(1.0)
        cam = look((x0 - 50, y0 + 140, 36), (x0 - 50, y0, 28))
        raw, info = capture(cam)
        meta["frames"]["ue-axes-pair-from-plus-y.jpg"] = dict(
            save_frame(raw, out / "ue-axes-pair-from-plus-y.jpg", args.width), camera=cam,
            note="production (left, x=%g) and candidate (right, x=%g), both yaw 0, camera on +Y looking -Y "
                 "(image right = world +X)" % (x0 - 100, x0), **info)
        for actor in (ref, ref_base):
            call("actor", "set_actor_transform", {"actor": actor, "xform": xf(x0, y0 + 100, 0, -90.0)})
        time.sleep(1.0)
        cam = look((x0 + 140, y0 + 50, 36), (x0, y0 + 50, 28))
        raw, info = capture(cam)
        meta["frames"]["ue-axes-pair-from-plus-x-production-yaw-minus-90.jpg"] = dict(
            save_frame(raw, out / "ue-axes-pair-from-plus-x-production-yaw-minus-90.jpg", args.width), camera=cam,
            note="production yaw -90 (left) and candidate yaw 0 (right), camera on +X: the rotation a +Y-facing "
                 "mesh needs to face +X", **info)
        meta["production_actor_transform_last"] = call("actor", "get_actor_transform", {"actor": ref})
    finally:
        for actor in placed:
            try:
                call("scene", "remove_from_scene", {"actor": actor})
            except RuntimeError as exc:
                print("remove failed:", exc)
        for path in (probe_mi, probe_folder):
            try:
                if call("asset", "exists", {"path": path}):
                    call("asset", "delete", {"path": path})
            except RuntimeError as exc:
                print("delete failed:", path, exc)
        call("scene", "load_level", {"level_path": original_level})
        time.sleep(2.0)
        meta["probe_folder_removed"] = not call("asset", "exists", {"path": probe_folder})
        meta["restored_level"] = call("scene", "get_current_level")
        meta["restored_level_dirty"] = call("asset", "is_dirty", {"asset_path": meta["restored_level"]})
        meta["review_level_dirty_after_reload"] = call("asset", "is_dirty", {"asset_path": args.level})
        meta["candidate_assets_dirty"] = {a: call("asset", "is_dirty", {"asset_path": a}) for a in
                                          sorted(v for v in names.values())}
    fp = meta["face_probe"]
    if len(fp) == 4:
        ranked = sorted(fp, key=lambda k: fp[k]["pixels"], reverse=True)
        top, second = fp[ranked[0]]["pixels"], fp[ranked[1]]["pixels"]
        opposite = {"+X": "-X", "-X": "+X", "+Y": "-Y", "-Y": "+Y"}[ranked[0]]
        meta["result"] = {"face_visible_most_from": ranked[0], "pixels_by_direction": {k: fp[k]["pixels"] for k in fp},
                          "ratio_top_to_second": round(top / second, 2) if second else None,
                          "opposite_direction_pixels": fp[opposite]["pixels"],
                          "reading": "most face-slot pixels are seen from %s and (almost) none from %s; the side "
                                     "views see the face in profile. The candidate faces %s in UE"
                                     % (ranked[0], opposite, ranked[0])}
    (out / "ue-axes-frames.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(meta.get("result"), indent=1))
    print("restored:", meta["restored_level"], "dirty:", meta["restored_level_dirty"],
          "review level dirty:", meta["review_level_dirty_after_reload"], "probe folder removed:",
          meta["probe_folder_removed"])


if __name__ == "__main__":
    main()
