"""SEL: drop parts of a Tripo H2 high-poly GLB (phantoms and the Tripo base) without touching the binary chunk.

The phantom list of King Arthur is the measured one of docs/art-pipeline/king-arthur-h2-report.md «Главная находка»
(parts 11, 13, 18 - the second sword with fist and pommel; 14, 19 - the second lowered right arm; 16 - the dragon
knee pad behind the thigh; 20 - the lion medallion behind the shoulder); the in-game H2LD dropped the same parts.
The Tripo base (Arthur 4, Medusa 2) goes too: the showcase stands the figure on the game pedestal with the team ring.
Prints the feet height (min Y of the kept parts, metres) used to seat the figure on the pedestal.

    python tools/art/showcase/clean_hipoly.py [<Key> ...]    # no key: every job

Wave A of the 2026-10-20 batch (Bruce Lee, Sherlock Holmes, Dr. Watson): the H2 sources passed stage 2 without phantoms,
only the Tripo base goes ("auto-base").
"""
import json
import struct
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
JOBS = {
    # 2026-10-16: the regenerated H2 4f059621 (side in the LEFT slot) has no phantoms - only its Tripo base goes (the
    # base part is found by its bounds: the widest part with its top under 12 % of the figure height)
    "KingArthur": ("art/pipeline-candidates/ASSET-KING-ARTHUR-001/20261016-h2-tripo/source/king-arthur-h2-tripo-4f059621-tex8k-pbr.glb",
                   "auto-base"),
    "Medusa": ("art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-tripo/source/medusa-h2-tripo-40c4d1cd-tex8k-pbr.glb", {2}),
    "BruceLee": ("art/pipeline-candidates/ASSET-BRUCE-LEE-001/20261021-h2-tripo/source/bruce-lee-h2-tripo-14235c8d-tex8k-pbr.glb",
                 "auto-base"),
    # 2026-10-21: the regenerated H2 a5faa31f (pipe restored) replaced 734b9954
    "SherlockHolmes": ("art/pipeline-candidates/ASSET-SHERLOCK-HOLMES-001/20261021-h2-tripo/source/"
                       "sherlock-holmes-h2-tripo-a5faa31f-tex8k-pbr.glb", "auto-base"),
    "DrWatson": ("art/pipeline-candidates/ASSET-DR-WATSON-001/20261020-h2-tripo/source/dr-watson-h2-tripo-5458aaff-tex8k-pbr.glb",
                 "auto-base"),
}


def positions(blob, j, bin0, mesh):
    out = []
    for p in mesh["primitives"]:
        a = j["accessors"][p["attributes"]["POSITION"]]
        bv = j["bufferViews"][a["bufferView"]]
        stride = bv.get("byteStride", 12)
        off = bin0 + bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        raw = np.frombuffer(blob, dtype=np.uint8, count=a["count"] * stride, offset=off).reshape(-1, stride)[:, :12]
        out.append(raw.copy().view(np.float32).reshape(-1, 3))
    return np.concatenate(out)


def clean(key, rel, drop):
    src = REPO / rel
    blob = src.read_bytes()
    jlen = struct.unpack("<I", blob[12:16])[0]
    j = json.loads(blob[20:20 + jlen])
    bin_chunk = blob[20 + jlen:]
    bin0 = 20 + jlen + 8
    if drop == "auto-base":
        boxes = []
        for i, m in enumerate(j["meshes"]):
            pts = positions(blob, j, bin0, m)
            boxes.append((i, float(pts[:, 1].max()), float(np.ptp(pts[:, 0]) * np.ptp(pts[:, 2]))))
        top = max(b[1] for b in boxes)
        low = [b for b in boxes if b[1] < 0.12 * top]
        drop = {max(low, key=lambda b: b[2])[0]} if low else set()
    drop_nodes = {i for i, n in enumerate(j["nodes"]) if n.get("mesh") is not None and n["mesh"] in drop}
    for n in j["nodes"]:
        if "children" in n:
            n["children"] = [c for c in n["children"] if c not in drop_nodes]
    for s in j.get("scenes", []):
        s["nodes"] = [c for c in s["nodes"] if c not in drop_nodes]
    kept = [m for i, m in enumerate(j["meshes"]) if i not in drop]
    pts = np.concatenate([positions(blob, j, bin0, m) for m in kept])
    feet, top = float(pts[:, 1].min()), float(pts[:, 1].max())
    tris = sum(j["accessors"][p["indices"]]["count"] // 3 for m in kept for p in m["primitives"])
    js = json.dumps(j, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    out = src.with_name(src.stem + "-clean.glb")
    total = 12 + 8 + len(js) + len(bin_chunk)
    out.write_bytes(b"glTF" + struct.pack("<II", 2, total) + struct.pack("<I", len(js)) + b"JSON" + js + bin_chunk)
    print(f"{key}: dropped parts {sorted(drop)} -> {out.name} tris={tris} feetY={feet:.4f} topY={top:.4f}")


for k, (r, d) in JOBS.items():
    if len(sys.argv) > 1 and k not in sys.argv[1:]:
        continue
    clean(k, r, d)
