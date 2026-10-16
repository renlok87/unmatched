"""SEL: drop parts of a Tripo H2 high-poly GLB (phantoms and the Tripo base) without touching the binary chunk.

The phantom list of King Arthur is the measured one of docs/art-pipeline/king-arthur-h2-report.md «Главная находка»
(parts 11, 13, 18 - the second sword with fist and pommel; 14, 19 - the second lowered right arm; 16 - the dragon
knee pad behind the thigh; 20 - the lion medallion behind the shoulder); the in-game H2LD dropped the same parts.
The Tripo base (Arthur 4, Medusa 2) goes too: the showcase stands the figure on the game pedestal with the team ring.
Prints the feet height (min Y of the kept parts, metres) used to seat the figure on the pedestal.

    python tools/art/showcase/clean_hipoly.py
"""
import json
import struct
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
JOBS = {
    "KingArthur": ("art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-tripo/source/king-arthur-h2-tripo-c24eeff0-tex8k-pbr.glb",
                   {4, 11, 13, 14, 16, 18, 19, 20}),
    "Medusa": ("art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-tripo/source/medusa-h2-tripo-40c4d1cd-tex8k-pbr.glb", {2}),
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
    clean(k, r, d)
