"""H2 bake profile (schema unmatched.h2-bake-profile/1): loading, validation and the source -> final frame map.
No bpy: used by the driver (plain Python) and by the Blender stages."""

import hashlib
import json
from pathlib import Path

SCHEMA = "unmatched.h2-bake-profile/1"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path):
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = validate(profile)
    if problems:
        raise ValueError("h2 profile %s: %s" % (path, "; ".join(problems)))
    return profile


def validate(p):
    problems = []
    if p.get("schema") != SCHEMA:
        problems.append("schema must be %s" % SCHEMA)
    for key in ("asset_id", "sources", "parts", "scale", "retopo", "uv", "bake", "textures", "rig", "exports",
                "meshes", "materials"):
        if key not in p:
            problems.append("missing key %s" % key)
    if problems:
        return problems
    parts = p["parts"]
    if len(parts) != p.get("expected_part_count", len(parts)):
        problems.append("parts: %d entries, expected_part_count %s" % (len(parts), p.get("expected_part_count")))
    roles = {}
    for name, cfg in parts.items():
        roles.setdefault(cfg.get("mesh"), []).append(name)
        if cfg.get("mesh") not in ("body", "weapon", "base"):
            problems.append("part %s: mesh must be body|weapon|base" % name)
        if name not in p["retopo"]["target_tris"]:
            problems.append("part %s: no retopo.target_tris" % name)
        if cfg.get("mesh") != "base" and name not in p["rig"]["weights"]:
            problems.append("part %s: no rig.weights rule" % name)
    if len(roles.get("base", [])) != 1:
        problems.append("exactly one base part required")
    bones = [b[0] for b in p["rig"]["bones"]]
    for name, rule in p["rig"]["weights"].items():
        for bone in rule_bones(rule):
            if bone not in bones:
                problems.append("weights %s: unknown bone %s" % (name, bone))
    return problems


def rule_bones(rule):
    kind = rule["kind"]
    if kind == "rigid":
        return [rule["bone"]]
    if kind == "chain":
        return list(rule["chain"])
    if kind == "zblend":
        return [b for b, _z in rule["stops"]]
    if kind == "cloth":
        return [rule["base_bone"]] + list(rule["legs"].values()) + ([rule["top_bone"]] if rule.get("top_bone") else [])
    raise ValueError("unknown weight rule kind %r" % kind)


def frame_map(base_bounds, figure_top_z, cfg):
    """Source (Tripo GLB metres, Blender axes after glTF import) -> final (candidate metres) map.

    base_bounds: ((x0, y0, z0), (x1, y1, z1)) of the base part; figure_top_z: highest source vertex.
    The base is normalised to the card-04 footprint (diameter x diameter x height); every other part is scaled
    uniformly by s about the base centre, and the source contact «feet on the base top» is kept:
    z' = H + (z - base_top) * s, with s = (figure_top - H) / (figure_top_src - base_top_src)."""
    (x0, y0, z0), (x1, y1, z1) = base_bounds
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    diameter, height = float(cfg["base_diameter_m"]), float(cfg["base_height_m"])
    s = (float(cfg["figure_top_m"]) - height) / (figure_top_z - z1)
    return {"centre_xy_src": [cx, cy], "base_top_src": z1, "base_bottom_src": z0, "figure_top_src": figure_top_z,
            "figure_scale": s, "base_scale": [diameter / (x1 - x0), diameter / (y1 - y0), height / (z1 - z0)],
            "base_height_m": height, "figure_top_m": float(cfg["figure_top_m"])}


def map_point(m, p, is_base):
    cx, cy = m["centre_xy_src"]
    if is_base:
        sx, sy, sz = m["base_scale"]
        return ((p[0] - cx) * sx, (p[1] - cy) * sy, (p[2] - m["base_bottom_src"]) * sz)
    s = m["figure_scale"]
    return ((p[0] - cx) * s, (p[1] - cy) * s, m["base_height_m"] + (p[2] - m["base_top_src"]) * s)


def rel(path, repo):
    try:
        return Path(path).resolve().relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()
