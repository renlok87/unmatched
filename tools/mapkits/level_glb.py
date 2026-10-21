"""Level a tilted Tripo prop: rotate the GLB root node so the prop stands on its support.

    python tools/mapkits/level_glb.py <file.glb> [--max 25] [--apply]

Tripo reconstructs the camera elevation of a single 3/4 image into the mesh, so props made from views "from slightly
above" come out tipped forward by 6-20 deg (acceptance cards of rope-coil, milk-churns, mooring-pilings,
produce-crates, NOTES F8). The fix searches small rotations about the two horizontal axes (glTF X and Z, Y is up) and
keeps the one with the largest support polygon: the convex hull area of the vertices in the lowest 1.5 % of the height.
A prop on a flat base or on legs touches the ground with all of it only when it stands level.

The vertex data is not touched: --apply writes the rotation as the root node's glTF "rotation" quaternion, so the raw
Tripo geometry stays as it is and env_kit (Blender glTF import) applies the node transform. Hanging props (wall lamps,
signs, awnings) have no support: level them only when the search gain is clear.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path

import numpy as np

try:
    from scipy.spatial import ConvexHull
except ImportError:  # pragma: no cover
    ConvexHull = None


def read_glb(p: Path) -> tuple[dict, bytes]:
    b = p.read_bytes()
    if b[:4] != b"glTF":
        raise SystemExit(f"ERROR {p} is not a GLB")
    jl = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + jl])
    rest = b[20 + jl:]
    bl = struct.unpack("<I", rest[:4])[0]
    return j, rest[8:8 + bl]


def write_glb(p: Path, j: dict, binary: bytes) -> None:
    js = json.dumps(j, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    binary += b"\0" * ((4 - len(binary) % 4) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    out = struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(js), b"JSON") + js + \
        struct.pack("<I4s", len(binary), b"BIN\0") + binary
    p.write_bytes(out)


def positions(j: dict, binary: bytes) -> np.ndarray:
    out = []
    for m in j["meshes"]:
        for pr in m["primitives"]:
            a = j["accessors"][pr["attributes"]["POSITION"]]
            bv = j["bufferViews"][a["bufferView"]]
            off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
            stride = bv.get("byteStride", 12)
            raw = np.frombuffer(binary, dtype=np.uint8, count=stride * a["count"], offset=off)
            out.append(raw.reshape(a["count"], stride)[:, :12].copy().view(np.float32).reshape(-1, 3))
    return np.concatenate(out).astype(np.float64)


def rot(rx: float, rz: float) -> np.ndarray:
    cx, sx, cz, sz = math.cos(rx), math.sin(rx), math.cos(rz), math.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ mx


def support_area(v: np.ndarray, slab: float = 0.015) -> float:
    y = v[:, 1]
    lo, h = y.min(), y.max() - y.min()
    pts = v[y <= lo + slab * h][:, [0, 2]]
    if len(pts) < 3:
        return 0.0
    if ConvexHull is not None:
        try:
            return float(ConvexHull(pts).volume)
        except Exception:
            return 0.0
    return float(np.ptp(pts[:, 0]) * np.ptp(pts[:, 1]))


def search(v: np.ndarray, max_deg: float = 25.0) -> dict:
    v = v - v.mean(axis=0)
    base = support_area(v)
    best = (base, 0.0, 0.0)
    for step, span, c in ((1.0, max_deg, (0.0, 0.0)), (0.25, 1.5, None)):
        cx, cz = (best[1], best[2]) if c is None else c
        for ax in np.arange(cx - span, cx + span + 1e-9, step):
            for az in np.arange(cz - span, cz + span + 1e-9, step):
                a = support_area(v @ rot(math.radians(ax), math.radians(az)).T)
                if a > best[0]:
                    best = (a, float(ax), float(az))
    a, ax, az = best
    return {"rx_deg": round(ax, 2), "rz_deg": round(az, 2), "tilt_deg": round(math.hypot(ax, az), 2),
            "support_area_before": round(base, 6), "support_area_after": round(a, 6),
            "gain": round(a / base, 2) if base > 0 else None}


def quat_from_matrix(m: np.ndarray) -> list[float]:
    t = m.trace()
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w, x, y, z = 0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s
    else:
        i = int(np.argmax(np.diag(m)))
        if i == 0:
            s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
            w, x, y, z = (m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s
        elif i == 1:
            s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
            w, x, y, z = (m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s
        else:
            s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
            w, x, y, z = (m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s
    return [x, y, z, w]


def apply(p: Path, res: dict) -> None:
    j, binary = read_glb(p)
    roots = j["scenes"][j.get("scene", 0)]["nodes"]
    for n in roots:
        node = j["nodes"][n]
        if any(k in node for k in ("matrix", "rotation")):
            raise SystemExit(f"ERROR node {n} already has a transform: level it by hand")
        node["rotation"] = quat_from_matrix(rot(math.radians(res["rx_deg"]), math.radians(res["rz_deg"])))
    j.setdefault("extras", {})["mapkitLevel"] = res
    write_glb(p, j, binary)


def level(p: Path, max_deg: float = 25.0, do_apply: bool = False, min_tilt: float = 2.0) -> dict:
    j, binary = read_glb(p)
    if j.get("extras", {}).get("mapkitLevel"):
        return {**j["extras"]["mapkitLevel"], "applied": True, "note": "already levelled"}
    res = search(positions(j, binary), max_deg)
    res["applied"] = bool(do_apply and res["tilt_deg"] >= min_tilt and (res["gain"] or 0) >= 1.2)
    if res["applied"]:
        apply(p, res)
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("glb", type=Path)
    ap.add_argument("--max", type=float, default=25.0)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    print(json.dumps(level(a.glb, a.max, a.apply), ensure_ascii=False))


if __name__ == "__main__":
    main()
