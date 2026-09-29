"""Convert editor-frame PNGs (with their <stem>.evidence.json sidecars) into the evidence format of PIPELINE.md
("Формат кадров"): JPEG 1200 px wide, quality 92, Pillow LANCZOS; the sidecar is rewritten for the JPEG
(frameSha256, frame, output_px, jpeg) and keeps the PNG's sha256/bytes/size under png_before_jpeg.

    python tools/tripo-pipeline/review/frames_to_jpeg.py --src <dir with PNG + sidecars> --out <evidence dir>
        [--png-kept-at <where the PNGs stay, outside git>] [--include <glob> ...] [--exclude <glob> ...]
"""

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path

from PIL import Image

WIDTH, QUALITY = 1200, 92


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--png-kept-at")
    ap.add_argument("--include", nargs="*", default=["*.png"])
    ap.add_argument("--exclude", nargs="*", default=[])
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    done = []
    for png in sorted(src.glob("*.png")):
        if not any(fnmatch.fnmatch(png.name, g) for g in a.include) or any(fnmatch.fnmatch(png.name, g) for g in a.exclude):
            continue
        side_path = png.with_name(png.stem + ".evidence.json")
        side = json.loads(side_path.read_text(encoding="utf-8")) if side_path.exists() else {}
        raw = png.read_bytes()
        im = Image.open(png).convert("RGB")
        w, h = im.size
        jpg = out / (png.stem + ".jpg")
        im.resize((WIDTH, round(h * WIDTH / w)), Image.LANCZOS).save(jpg, quality=QUALITY)
        side.update({"frame": jpg.name, "frameSha256": hashlib.sha256(jpg.read_bytes()).hexdigest(),
                     "output_px": [WIDTH, round(h * WIDTH / w)],
                     "jpeg": "Pillow LANCZOS %dx%d, quality %d (PIPELINE.md frame format)" % (WIDTH, round(h * WIDTH / w), QUALITY),
                     "png_before_jpeg": {"file": png.name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                                         "px": [w, h], "kept_outside_git": a.png_kept_at or str(src)}})
        (out / (png.stem + ".evidence.json")).write_text(json.dumps(side, indent=1, sort_keys=True) + "\n",
                                                         encoding="utf-8", newline="\n")
        done.append(jpg.name)
    print("%d frames -> %s" % (len(done), out))


if __name__ == "__main__":
    main()
