#!/usr/bin/env python3
"""Store the review frames of an Arthur run compactly (Medusa T4 / P1.6 precedent).

    python art/pipeline-candidates/ASSET-KING-ARTHUR-001/scripts/store_preview_frames.py \
        --run-dir art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260928-blender-um-fbx-v1

Run after the review scripts, on the PNGs they wrote under <run>/preview:
  * silhouette_*.png            -> PNG L (lossless grey), same name;
  * deform/<prefix>-<pose>.png  -> removed after the sheets are built (overlay_bones.py); sha256/bytes kept;
  * every other *.png           -> JPEG q92 at full resolution, the PNG removed.
Writes <run>/preview/frames-storage.json with the PNG sha256/bytes and pixel size of every frame. Numeric
comparisons (FBX vs .blend frame, game-scale pixel size, background pixels in the base disc) are done on the
PNGs before this step. Deterministic for the same PNGs (Pillow JPEG encoder, no metadata).
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[4]
PROBE_FRAME = re.compile(r"^deform/[^/]+-(rest|head_turn|spine_bend_fwd|arm_l_raise|arm_r_raise|forearm_l_bend|"
                         r"thigh_l_flex|thigh_r_flex)\.png$")


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
        if png.name.startswith("silhouette_"):
            with Image.open(png) as im:
                info["pixels"] = list(im.size)
                if im.mode == "L" and rel in converted:
                    continue  # already stored
                grey = im.convert("L")
            grey.save(png, optimize=True)
            info.update(stored=rel, stored_as="PNG L (lossless, grey)")
            converted[rel] = info
        elif PROBE_FRAME.match(rel):
            png.unlink()
            removed[rel] = {"bytes": info["png_bytes"], "sha256": info["png_sha256"]}
        else:
            with Image.open(png) as im:
                info["pixels"] = list(im.size)
                rgb = im.convert("RGB")
            jpg = png.with_suffix(".jpg")
            rgb.save(jpg, quality=92, optimize=True)
            png.unlink()
            info.update(stored=jpg.relative_to(preview).as_posix(), stored_as="JPEG q92")
            converted[rel] = info
    note = ("renders are written as PNG by the scripts and stored here as JPEG q92 at full resolution (Medusa T4 "
            "precedent); the PNG sha256/bytes are kept below. Numeric comparisons (FBX vs .blend frame, game-scale "
            "pixel size, background pixels inside the base-top disc in base-closure/) were done on the PNGs before "
            "conversion. Individual rig_deform_probe frames were removed after building the sheets (P1.6 precedent); "
            "they are reproduced by the commands in docs/art-pipeline/king-arthur-candidate-report.md.")
    store.write_text(json.dumps({"converted": dict(sorted(converted.items())), "note": note,
                                 "removed_probe_frames": dict(sorted(removed.items()))}, indent=1, sort_keys=True)
                     + "\n", encoding="utf-8")
    print("STORE_OK", len(converted), "frames,", len(removed), "probe frames removed")


if __name__ == "__main__":
    main()
