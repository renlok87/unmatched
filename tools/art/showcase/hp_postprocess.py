"""SEL showcase: post-process the maps baked by hp_lookdev_bake.py before the UE import.

- MatID, EdgeMask, TeamAccent -> single channel L8 (the master reads one channel);
- MatID snapped to the class codes index*16+8 (the master reads it with Load(), an off-by-one value is another class;
  the bake samples it Closest with 1 sample, the snap removes the colour-management rounding).

    python tools/art/showcase/hp_postprocess.py
"""
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
DIRS = [REPO / "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20261016-hp-showcase/textures",
        REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/20261016-hp-showcase/textures"]

for d in DIRS:
    if not d.is_dir():
        continue
    stats = {"MatID": 0, "EdgeMask": 0, "TeamAccent": 0, "moved": 0}
    for kind in ("MatID", "EdgeMask", "TeamAccent"):
        for f in sorted(d.glob(f"*_{kind}.png")):
            a = np.asarray(Image.open(f).convert("RGB"))[..., 0].astype(np.int32)
            if kind == "MatID":
                snapped = np.clip(np.round((a - 8) / 16.0), 0, 15).astype(np.int32) * 16 + 8
                stats["moved"] += int((snapped != a).sum())
                a = snapped
            Image.fromarray(a.astype(np.uint8), "L").save(f)
            stats[kind] += 1
    print(d.parent.parent.name, stats)
