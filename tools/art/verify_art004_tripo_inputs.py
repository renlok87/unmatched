"""Read-only preflight for the three recommended Medusa multiview images.

Checks both the isolated worktree and the user's original checkout so the
absolute upload paths in the handoff cannot silently point at stale files.
No image is edited and nothing is transmitted to Tripo by this script.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
OUT = ROOT / "docs/game-design/evidence/ART-004/tripo-medusa-inputs.json"
RELATIVE = Path("art/imagegen/mvp-v1/characters")
EXPECTED = {
    "front": "252f94b965aa049f5395534b066271d2ef9cfe6755a8c1ddf4bc9801187a78c9",
    "left": "6d27f4d2090ac660ebcb53810c8fade2d794c5f2fa614944415499ad88c4635c",
    "back": "3b328a54002b2ea953a1390d616ac14ac8498a155bcbfbd825d83c28afec5c1d",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    inputs = []
    for view in ("front", "left", "back"):
        relative = RELATIVE / f"ref-medusa-v5-{view}.png"
        source = ROOT / relative
        upload = ORIGINAL / relative
        source_sha = digest(source)
        if source_sha != EXPECTED[view] or digest(upload) != source_sha:
            raise RuntimeError(f"Medusa {view} changed or differs between checkouts")
        with Image.open(source) as image:
            rgb = image.convert("RGB")
            bbox = ImageChops.difference(rgb, Image.new("RGB", rgb.size, (128, 128, 128))).getbbox()
            if image.size != (1024, 1024) or image.mode != "RGB" or rgb.getpixel((0, 0)) != (128, 128, 128):
                raise RuntimeError(f"Unexpected image normalization: {relative}")
        if source.stat().st_size > 20_000_000 or bbox is None or bbox[3] > 930:
            raise RuntimeError(f"Invalid image size or baseline: {relative}")
        inputs.append({
            "view": view,
            "relative_path": relative.as_posix(),
            "absolute_upload_path": upload.as_posix(),
            "sha256": source_sha,
            "bytes": source.stat().st_size,
            "pixels": [1024, 1024],
            "background_rgb": [128, 128, 128],
            "non_background_bbox_xyxy": list(bbox),
        })
    payload = {
        "status": "ready_for_review; no upload or model generation performed",
        "model": "Tripo H3.1 multi-view",
        "ui_slots": ["front", "left", "right", "back"],
        "right": "leave empty; available v5/v6 right views are not recommended as stable 3D constraints",
        "inputs": inputs,
        "separate_from": "S05 technical Medusa rig/FBX prototype; not the final art model",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART004_TRIPO_PREFLIGHT_PASS", len(inputs))


if __name__ == "__main__":
    main()
