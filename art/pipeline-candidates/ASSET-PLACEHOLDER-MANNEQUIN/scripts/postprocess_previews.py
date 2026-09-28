"""Measure the preview PNGs and store them as JPEG <= 1200 px (system Python with Pillow + numpy).

python art/pipeline-candidates/ASSET-PLACEHOLDER-MANNEQUIN/scripts/postprocess_previews.py <run_dir> [--keep-png]

Measures on the PNGs before conversion:
  * silhouette_{k1,close}: bounding box of the black figure (luminance < 128), also scaled to 1920 x 1080;
  * fbx_roundtrip_front vs ortho_front: per-channel absolute difference (max, pixels > 8);
  * ortho_front: pixels of the background colour inside the figure's bounding box are not measured (open shapes).
Builds sheets: poses (7 solid rig_deform_probe rotations) and the two rig_deform_probe overlay sheets.
Writes <run_dir>/preview/*.jpg (quality 92, LANCZOS) and <run_dir>/reports/preview-report.json (sha256/bytes of each
PNG before conversion under png_before_jpeg); the PNGs in work/renders and
the single probe frames in work/deform are removed unless --keep-png (the probe JSONs move to reports/deform/).
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

MAX_PX = 1200
POSES = ["head_turn", "spine_bend_fwd", "arm_l_raise", "arm_r_raise", "forearm_l_bend", "thigh_l_flex", "thigh_r_flex"]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def to_jpeg(img, dst, png=None):
    before = {"sha256": sha256(png), "bytes": Path(png).stat().st_size, "size_px": list(img.size)} if png else None
    img = img.convert("RGB")
    if max(img.size) > MAX_PX:
        img.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, "JPEG", quality=92, optimize=True)
    out = {"file": dst.name, "size_px": list(img.size), "bytes": dst.stat().st_size, "sha256": sha256(dst)}
    if before:
        out["png_before_jpeg"] = before
    return out


def silhouette(path):
    a = np.asarray(Image.open(path).convert("L"), dtype=np.int32)
    ys, xs = np.nonzero(a < 128)
    h, w = a.shape
    box = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    sx = 1920 / w
    return {"frame_px": [w, h], "bbox_px": box, "width_px": box[2] - box[0] + 1, "height_px": box[3] - box[1] + 1,
            "height_px_at_1920x1080": round((box[3] - box[1] + 1) * sx, 1),
            "width_px_at_1920x1080": round((box[2] - box[0] + 1) * sx, 1), "dark_pixels": int(len(xs))}


def main():
    run_dir = Path(sys.argv[1]).resolve()
    keep = "--keep-png" in sys.argv
    ren, dfm, prev = run_dir / "work" / "renders", run_dir / "work" / "deform", run_dir / "preview"
    rep = {"method": __doc__.strip().splitlines()[0], "light": "neutral EEVEE preview light (key + fill sun), not the game light",
           "measurements": {}, "files": {}}
    m = rep["measurements"]
    m["silhouette_k1"] = silhouette(ren / "silhouette_k1.png")
    m["silhouette_close"] = silhouette(ren / "silhouette_close.png")
    m["silhouette_note"] = ("K-1: camera 12.18 m, horizontal FOV 35 deg, pitch -55 deg (cell 1 m ≈ 250 px at 1920 px); "
                            "04 §3 proposes a figure of ≈ 110-140 px on 1080p for this view (proposal, Q-312 / GD-058)")
    a = np.asarray(Image.open(ren / "ortho_front.png").convert("RGB"), dtype=np.int32)
    b = np.asarray(Image.open(ren / "fbx_roundtrip_front.png").convert("RGB"), dtype=np.int32)
    d = np.abs(a - b)
    m["fbx_vs_blend_ortho_front"] = {"max_channel_diff": int(d.max()), "pixels_diff_gt_8": int((d.max(axis=2) > 8).sum()),
                                     "pixels_diff_gt_2": int((d.max(axis=2) > 2).sum()), "pixels": int(d.shape[0] * d.shape[1])}
    for name in sorted(p.stem for p in ren.glob("*.png")):
        if name.startswith("pose_"):
            continue
        rep["files"][name] = to_jpeg(Image.open(ren / (name + ".png")), prev / (name + ".jpg"), ren / (name + ".png"))
    # pose sheet: rest (ortho_front is another view) -> use the 7 pose frames + a label strip
    tiles = [Image.open(ren / ("pose_%s.png" % p)).convert("RGB") for p in POSES]
    w, h = tiles[0].size
    sheet = Image.new("RGB", (w * 4, h * 2), (40, 40, 40))
    from PIL import ImageDraw
    for i, (t, p) in enumerate(zip(tiles, POSES)):
        dr = ImageDraw.Draw(t)
        dr.rectangle([0, 0, w, 26], fill=(0, 0, 0))
        dr.text((8, 7), p, fill=(255, 255, 255))
        sheet.paste(t, ((i % 4) * w, (i // 4) * h))
    rep["files"]["poses_sheet"] = to_jpeg(sheet, prev / "poses_sheet.jpg")
    for label in ("mannequin-blend", "mannequin-fbx"):
        rep["files"][label + "-sheet"] = to_jpeg(Image.open(dfm / (label + "-sheet.png")), prev / "deform" / (label + "-sheet.jpg"),
                                                 dfm / (label + "-sheet.png"))
    (run_dir / "reports" / "deform").mkdir(parents=True, exist_ok=True)
    for js in dfm.glob("*.json"):
        shutil.copy2(js, run_dir / "reports" / "deform" / js.name)
    if not keep:
        for p in list(ren.glob("*.png")) + list(dfm.glob("*.png")) + list(dfm.glob("*.json")):
            p.unlink()
        for dd in (ren, dfm):
            if dd.exists() and not any(dd.iterdir()):
                dd.rmdir()
    (run_dir / "reports" / "preview-report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n",
                                                            encoding="utf-8")
    print("MANNEQUIN_POSTPROCESS", json.dumps(m, ensure_ascii=False))


if __name__ == "__main__":
    main()
