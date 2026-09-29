"""Compact storage of the H2 review frames for git (system Python, Pillow), after every analysis ran on the PNGs.

    python store_preview.py <run_dir>

* colour renders (review/*, k2/*, colour instance frames, cmp_* sheets, deform sheets) -> JPEG q92, full resolution;
  RGBA renders are flattened on the concepts' charcoal (46, 47, 51);
* kept lossless: grayscale analysis frames (instances *_gray, *_crop_*, sheet_*), crop_* (nearest enlargements),
  uv_layout_parts.png, the see-through masks (see-through/*, before_after_see_through*: single red pixels);
* the single rig_deform_probe frames are removed (their sheets stay), as in the T3.3 candidates; so are the single
  close-ups review/closeup_*.png once their cmp_closeup_<name> sheet (high-poly | game mesh) exists;
* preview/frames-storage.json records sha256, bytes and size of every original PNG and of the stored file.
Idempotent: a second run finds no PNG to convert and keeps the manifest.
"""

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

run = Path(sys.argv[1]).resolve()
prev = run / "preview"
manifest_path = prev / "frames-storage.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"frames": {}}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def keep_png(p):
    n = p.name
    return (n.endswith("_gray.png") or "_crop_" in n or n.startswith("sheet_") and "gray" in n or n.startswith("crop_")
            or n == "uv_layout_parts.png" or p.parent.name == "see-through" or n.startswith("before_after_see_through"))


for p in sorted(prev.rglob("*.png")):
    rel = p.relative_to(prev).as_posix()
    sheet = prev / ("cmp_closeup_%s.png" % p.stem[len("closeup_"):].replace("_highpoly", "")) if p.name.startswith("closeup_") else None
    if p.parent.name == "review" and sheet is not None and (sheet.exists() or sheet.with_suffix(".jpg").exists()):
        # single close-ups: both halves are in the cmp_closeup_<name> sheet (compose_review.py)
        manifest["frames"][rel] = {"png_sha256": sha(p), "png_bytes": p.stat().st_size, "stored": None,
                                   "note": "single close-up removed; high-poly | game mesh pair is in %s" % sheet.stem}
        p.unlink()
        continue
    if p.parent.name == "deform" and not p.name.endswith("-sheet.png"):
        manifest["frames"][rel] = {"png_sha256": sha(p), "png_bytes": p.stat().st_size, "stored": None,
                                   "note": "single rig_deform_probe frame removed; the sheet and the deform JSON stay"}
        p.unlink()
        continue
    if keep_png(p):
        manifest["frames"].setdefault(rel, {"png_sha256": sha(p), "png_bytes": p.stat().st_size, "stored": rel})
        continue
    im = Image.open(p)
    info = {"png_sha256": sha(p), "png_bytes": p.stat().st_size, "size": list(im.size), "mode": im.mode}
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGBA", im.size, (46, 47, 51, 255))
        bg.alpha_composite(im.convert("RGBA"))
        im = bg
    out = p.with_suffix(".jpg")
    im.convert("RGB").save(out, quality=92, optimize=True, subsampling=0)
    info.update({"stored": out.relative_to(prev).as_posix(), "stored_sha256": sha(out), "stored_bytes": out.stat().st_size,
                 "format": "JPEG q92 4:4:4"})
    manifest["frames"][rel] = info
    p.unlink()
manifest["note"] = ("frames are Blender renders (label blender), analysed as PNG before storage; colour frames stored as "
                    "JPEG q92, grayscale analysis frames and nearest crops stay PNG")
manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("STORE_OK", len(manifest["frames"]))
