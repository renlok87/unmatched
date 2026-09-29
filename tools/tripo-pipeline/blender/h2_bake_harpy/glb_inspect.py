"""Structure of a Tripo GLB without Blender (plain Python + numpy): container check, meshes / nodes / accessor bounds,
materials, embedded image sizes (PNG / JPEG headers) per part. Used for the tripo-run evidence of H3.

    python glb_inspect.py <file.glb> [--out report.json]
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


def sha256(path):
    d = hashlib.sha256()
    with open(path, "rb") as h:
        for chunk in iter(lambda: h.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def image_size(buf):
    if buf[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", buf[16:24])
        return "png", w, h
    if buf[:2] == b"\xff\xd8":
        i = 2
        while i < len(buf) - 9:
            if buf[i] != 0xFF:
                i += 1
                continue
            marker = buf[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", buf[i + 5:i + 9])
                return "jpeg", w, h
            seg = struct.unpack(">H", buf[i + 2:i + 4])[0]
            i += 2 + seg
        return "jpeg", None, None
    return "unknown", None, None


def inspect(path):
    path = Path(path)
    data = path.read_bytes()
    magic, version, length = struct.unpack("<4sII", data[:12])
    out = {"file": path.name, "bytes": len(data), "sha256": sha256(path)}
    chunks, off = [], 12
    while off < len(data):
        clen, ctype = struct.unpack("<I4s", data[off:off + 8])
        chunks.append((ctype, data[off + 8:off + 8 + clen]))
        off += 8 + clen
    out["container_check"] = {"magic": magic.decode(), "version": version, "header_length_equals_file": length == len(data),
                              "chunk_walk_ends_at_file_end": off == len(data),
                              "chunks": [c[0].decode(errors="replace").strip("\x00") for c in chunks]}
    js = json.loads(chunks[0][1].decode("utf-8"))
    binchunk = chunks[1][1] if len(chunks) > 1 else b""
    acc, bvs = js.get("accessors", []), js.get("bufferViews", [])
    images = []
    for im in js.get("images", []):
        entry = {"name": im.get("name"), "mimeType": im.get("mimeType")}
        if "bufferView" in im:
            bv = bvs[im["bufferView"]]
            b = binchunk[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
            fmt, w, h = image_size(b)
            entry.update(format=fmt, px=[w, h], bytes=bv["byteLength"])
        images.append(entry)
    textures = js.get("textures", [])

    def tex_px(info):
        if not info:
            return None
        src = textures[info["index"]].get("source")
        return images[src]["px"][0] if src is not None and "px" in images[src] else None

    mats = []
    for m in js.get("materials", []):
        pbr = m.get("pbrMetallicRoughness", {})
        mats.append({"name": m.get("name"),
                     "basecolor_px": tex_px(pbr.get("baseColorTexture")),
                     "metal_rough_px": tex_px(pbr.get("metallicRoughnessTexture")),
                     "normal_px": tex_px(m.get("normalTexture")),
                     "metallicFactor": pbr.get("metallicFactor"), "roughnessFactor": pbr.get("roughnessFactor"),
                     "extensions": sorted(m.get("extensions", {}).keys())})
    parts, tri_total, vert_total, attrs = [], 0, 0, set()
    for ni, node in enumerate(js.get("nodes", [])):
        if "mesh" not in node:
            continue
        mesh = js["meshes"][node["mesh"]]
        tris = verts = 0
        mn, mx, mat_ids = [1e9] * 3, [-1e9] * 3, []
        for prim in mesh["primitives"]:
            attrs |= set(prim["attributes"])
            pa = acc[prim["attributes"]["POSITION"]]
            verts += pa["count"]
            mn = [min(a, b) for a, b in zip(mn, pa["min"])]
            mx = [max(a, b) for a, b in zip(mx, pa["max"])]
            tris += (acc[prim["indices"]]["count"] if "indices" in prim else pa["count"]) // 3
            if "material" in prim:
                mat_ids.append(prim["material"])
        tri_total += tris
        vert_total += verts
        entry = {"node": node.get("name"), "mesh_index": node["mesh"], "triangles": tris, "vertices": verts,
                 "accessor_min": [round(v, 4) for v in mn], "accessor_max": [round(v, 4) for v in mx],
                 "transform": {k: node[k] for k in ("translation", "rotation", "scale", "matrix") if k in node}}
        if mat_ids:
            m = mats[mat_ids[0]]
            entry["texture_px"] = {"basecolor": m["basecolor_px"], "metal_rough": m["metal_rough_px"],
                                   "normal": m["normal_px"]}
        parts.append(entry)
    parts.sort(key=lambda p: -p["triangles"])
    hist = {}
    area = 0
    for m in mats:
        if m["basecolor_px"]:
            hist[str(m["basecolor_px"])] = hist.get(str(m["basecolor_px"]), 0) + 1
            area += m["basecolor_px"] ** 2
    gmin = [min(p["accessor_min"][i] for p in parts) for i in range(3)]
    gmax = [max(p["accessor_max"][i] for p in parts) for i in range(3)]
    out["glb"] = {"meshes": len(js.get("meshes", [])), "nodes": len(js.get("nodes", [])),
                  "nodes_named": [n.get("name") for n in js.get("nodes", [])],
                  "triangles": tri_total, "vertices": vert_total, "materials": len(mats), "images": len(images),
                  "skins": len(js.get("skins", [])), "generator": js.get("asset", {}).get("generator"),
                  "extensionsUsed": js.get("extensionsUsed", []), "attributes": sorted(attrs),
                  "bounds_accessor_gltf_m": {"min": gmin, "max": gmax,
                                             "dimensions_xyz": [round(b - a, 4) for a, b in zip(gmin, gmax)],
                                             "note": "accessor min/max, glTF axes (Y up, +Z forward), Tripo units"},
                  "basecolor_size_histogram": hist, "basecolor_texel_area": area,
                  "embedded_image_bytes": sum(i.get("bytes", 0) for i in images),
                  "material_list": mats}
    out["parts"] = parts
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("glb")
    ap.add_argument("--out")
    a = ap.parse_args()
    rep = inspect(a.glb)
    text = json.dumps(rep, indent=1, ensure_ascii=False)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
