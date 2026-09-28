#!/usr/bin/env python3
"""Store the review frames of a Harpy run compactly (Arthur store_preview_frames.py / Medusa T4 / P1.6 precedent).

    python art/pipeline-candidates/ASSET-HARPY-001/scripts/store_preview_frames_harpy.py \
        --run-dir art/pipeline-candidates/ASSET-HARPY-001/20260928-blender-um-fbx-v1

Run after the review scripts (review_harpy_candidate.py, pose_review_harpy.py, rig_deform_probe.py +
overlay_bones.py, analyse_instances.py), on the PNGs they wrote under <run>/preview:
  * PNG that are already single-channel grey (instances/*_gray.png, *_crop_<i>.png, sheet_*_gray_crops.png:
    the colour-free evidence of analyse_instances.py) -> kept byte-for-byte;
  * silhouette_*.png -> PNG L (lossless) when R = G = B and alpha is opaque everywhere, else PNG RGB(A) optimised;
  * deform/<prefix>-<pose>.png (single rig_deform_probe frames) -> removed after the sheets are built; sha256/bytes
    kept; the sheets deform/<prefix>-sheet.png stay (as JPEG);
  * every other *.png -> JPEG q92 at full resolution (only frames with opaque alpha; a frame with transparency
    is kept as PNG), the PNG removed.
Writes <run>/preview/frames-storage.json with the PNG sha256/bytes and pixel size of every frame. Numeric
comparisons (FBX vs .blend frame, game-scale pixel size, the instance analysis) are done on the PNGs before this
step; analyse_instances.py was re-run on a copy of the PNGs and reproduced all 39 of its outputs byte-for-byte.
Deterministic for the same PNGs (Pillow JPEG encoder, no metadata). Idempotent: a second run keeps the entries.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[4]
PROBE_FRAME = re.compile(r"^deform/[^/]+-(rest|head_turn|spine_bend_fwd|arm_l_raise|arm_r_raise|forearm_l_bend|"
                         r"thigh_l_flex|thigh_r_flex)\.png$")


def opaque(im):
    return "A" not in im.getbands() or im.getchannel("A").getextrema() == (255, 255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    run = (REPO / ap.parse_args().run_dir).resolve()
    preview = run / "preview"
    store = preview / "frames-storage.json"
    old = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    converted, removed = dict(old.get("converted", {})), dict(old.get("removed_probe_frames", {}))
    for png in sorted(preview.rglob("*.png")):
        rel = png.relative_to(preview).as_posix()
        data = png.read_bytes()
        info = {"png_sha256": hashlib.sha256(data).hexdigest(), "png_bytes": len(data)}
        if rel in converted and converted[rel].get("stored") == rel and \
                converted[rel].get("stored_sha256") == info["png_sha256"]:
            continue  # already stored in place by an earlier run
        with Image.open(png) as im:
            im.load()
            info["pixels"] = list(im.size)
            mode = im.mode
            if mode == "L":
                info.update(stored=rel, stored_as="PNG L (unchanged)", stored_sha256=info["png_sha256"])
                converted[rel] = info
                continue
            if PROBE_FRAME.match(rel):
                pass
            elif png.name.startswith("silhouette_"):
                rgb = np.asarray(im.convert("RGB"))
                grey = bool((rgb[..., 0] == rgb[..., 1]).all() and (rgb[..., 1] == rgb[..., 2]).all()) and opaque(im)
                out = im.convert("L") if grey else im
                out.save(png, optimize=True)
                info.update(stored=rel, stored_as="PNG L (lossless, grey)" if grey else "PNG %s (lossless)" % mode,
                            stored_sha256=hashlib.sha256(png.read_bytes()).hexdigest())
                converted[rel] = info
                continue
            elif not opaque(im):
                info.update(stored=rel, stored_as="PNG %s (unchanged: has transparency)" % mode,
                            stored_sha256=info["png_sha256"])
                converted[rel] = info
                continue
            else:
                rgb_im = im.convert("RGB")
        if PROBE_FRAME.match(rel):
            png.unlink()
            removed[rel] = {"bytes": info["png_bytes"], "sha256": info["png_sha256"]}
            continue
        jpg = png.with_suffix(".jpg")
        rgb_im.save(jpg, quality=92, optimize=True)
        png.unlink()
        info.update(stored=jpg.relative_to(preview).as_posix(), stored_as="JPEG q92",
                    stored_sha256=hashlib.sha256(jpg.read_bytes()).hexdigest())
        converted[rel] = info
    note = ("renders are written as PNG by the review scripts and stored here compactly (Arthur/Medusa T4 "
            "precedent): colour frames as JPEG q92 at full resolution, grey silhouettes as PNG L, the grey "
            "instance-analysis frames/crops/sheets unchanged; the PNG sha256/bytes are kept below. Numeric "
            "comparisons (FBX vs .blend frame, game-scale pixel size, instance distinguishability) were done on the "
            "PNGs before conversion. Individual rig_deform_probe frames were removed after building the sheets "
            "(P1.6 precedent); they are reproduced by the commands in docs/art-pipeline/harpy-candidate-report.md.")
    store.write_text(json.dumps({"converted": dict(sorted(converted.items())), "note": note,
                                 "removed_probe_frames": dict(sorted(removed.items()))}, indent=1, sort_keys=True)
                     + "\n", encoding="utf-8")
    print("STORE_OK", len(converted), "frames,", len(removed), "probe frames removed")


if __name__ == "__main__":
    main()
