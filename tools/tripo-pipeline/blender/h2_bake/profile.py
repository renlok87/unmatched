"""H2 bake profile (schema unmatched.h2-bake-profile/1): loading, validation and the source -> final frame map.
No bpy: used by the driver (plain Python) and by the Blender stages.

Weapon side and presence (task D-1, 2026-10-09). The stages no longer assume the Medusa layout (one `weapon` part,
bone weapon.L under hand.L):
- a weapon mesh exists only when a part has `"mesh": "weapon"` (has_weapon); without it the figure is body + base
  (figure_roles / figure_mesh_names / skinned_roles), and the stages skip every weapon branch;
- the weapon bone (weapon_bone) is, in this order: optional `rig.weapon_bone` ("weapon.L" | "weapon.R" | null), the
  rig contract docs/art-pipeline/rig/rig-contract.json -> skeletons.<rig.skeleton>.characters.<rig.character>
  .weapon_bone (the key every v2 profile already has), and, for a character missing from the contract, the one
  weapon.L / weapon.R bone of rig.bones. An explicit value that contradicts the contract is an error.
Old profiles (Medusa: one weapon part, contract Medusa -> weapon.L) resolve to exactly the previous behaviour."""

import hashlib
import json
import re
from pathlib import Path

SCHEMA = "unmatched.h2-bake-profile/1"
CONTRACT_REL = "docs/art-pipeline/rig/rig-contract.json"
WEAPON_BONES = ("weapon.L", "weapon.R")
LEGACY_WEAPON_BONE = "weapon"  # v1 name; never valid in a v2 export
ROLES = ("body", "weapon", "base")  # mesh roles in the order every stage builds tuples (Medusa bytes depend on it)


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
    if not roles.get("body"):
        problems.append("at least one body part required")
    if len(roles.get("weapon", [])) > 1:
        problems.append("at most one weapon part (found %s)" % sorted(roles["weapon"]))
    for role in ("body", "base") + (("weapon",) if roles.get("weapon") else ()):
        if role not in p["meshes"]:
            problems.append("meshes.%s missing" % role)
    bones = [b[0] for b in p["rig"]["bones"]]
    for name, rule in p["rig"]["weights"].items():
        for bone in rule_bones(rule):
            if bone not in bones:
                problems.append("weights %s: unknown bone %s" % (name, bone))
    if "weapon_bone" in p["rig"]:
        wb = p["rig"]["weapon_bone"]
        if wb is not None and wb not in WEAPON_BONES:
            problems.append("rig.weapon_bone must be weapon.L, weapon.R or null (got %r)" % (wb,))
        elif wb is not None and wb not in bones:
            problems.append("rig.weapon_bone %s is not in rig.bones" % wb)
    side_bones = [b for b in bones if b in WEAPON_BONES]
    if len(side_bones) > 1:
        problems.append("rig.bones: at most one weapon bone (found %s)" % side_bones)
    return problems


# ------------------------------------------------------------------ weapon side and presence (D-1)
def has_weapon(p):
    """True when a part is the weapon mesh (`"mesh": "weapon"`)."""
    return any(cfg.get("mesh") == "weapon" for cfg in p["parts"].values())


def figure_roles(p):
    """Mesh roles of the figure in build order: ("body", "weapon", "base") or ("body", "base")."""
    return tuple(r for r in ROLES if r != "weapon" or has_weapon(p))


def skinned_roles(p):
    """Roles of the skeletal FBX (armature-deformed): ("body", "weapon") or ("body",)."""
    return tuple(r for r in figure_roles(p) if r != "base")


def figure_mesh_names(p):
    """Object names of the figure meshes (profile meshes.<role>) in build order."""
    return tuple(p["meshes"][r] for r in figure_roles(p))


def load_contract(repo_root):
    """The rig contract of the repository, or None when the file is not there (synthetic tests)."""
    path = Path(repo_root) / CONTRACT_REL
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def contract_weapon_bone(p, contract):
    """(known, bone): the weapon bone of rig.character in skeletons.<rig.skeleton>.characters of the contract."""
    if not contract:
        return False, None
    rig = p["rig"]
    skel = (contract.get("skeletons") or {}).get(rig.get("skeleton")) or {}
    chars = skel.get("characters") or {}
    ch = rig.get("character")
    if ch in chars:
        return True, chars[ch].get("weapon_bone")
    return False, None


def weapon_bone(p, contract=None):
    """"weapon.L" | "weapon.R" | None for the profile (resolution order: module docstring)."""
    rig = p["rig"]
    known, from_contract = contract_weapon_bone(p, contract)
    if "weapon_bone" in rig:
        bone = rig["weapon_bone"]
        if bone is not None and bone not in WEAPON_BONES:
            raise ValueError("rig.weapon_bone must be weapon.L, weapon.R or null (got %r)" % (bone,))
        if known and bone != from_contract:
            raise ValueError("rig.weapon_bone %r contradicts the rig contract (%s -> %r)"
                             % (bone, rig.get("character"), from_contract))
        return bone
    if known:
        return from_contract
    present = [b[0] for b in rig["bones"] if b[0] in WEAPON_BONES]
    if len(present) > 1:
        raise ValueError("rig.bones: at most one weapon bone (found %s)" % present)
    return present[0] if present else None


def weapon_side(bone):
    """"L" | "R" | None."""
    if bone is None:
        return None
    if bone not in WEAPON_BONES:
        raise ValueError("not a weapon bone: %r" % (bone,))
    return bone.rsplit(".", 1)[1]


def weapon_hand(bone):
    """Parent bone of the weapon bone: hand.L / hand.R (None without a weapon)."""
    side = weapon_side(bone)
    return None if side is None else "hand.%s" % side


def weapon_side_sign(bone):
    """+1.0 for .L, -1.0 for .R: the weapon side along authored +X (.L = +X, the front looks along -Y)."""
    side = weapon_side(bone)
    return None if side is None else (1.0 if side == "L" else -1.0)


def weapon_bone_verdict(bones, bone):
    """Rig check weapon_bone_by_side_v2 on the read-back bones {name: parent}: (passed, measured, expected).

    With a weapon bone: it is present under hand.<side>, and neither the other side nor the v1 name `weapon` is
    (Medusa: measured "hand.L", expected "hand.L", as before). Without one: no weapon bone at all."""
    others = [b for b in WEAPON_BONES + (LEGACY_WEAPON_BONE,) if b != bone]
    if bone is not None:
        hand = weapon_hand(bone)
        passed = bone in bones and not any(b in bones for b in others) and bones.get(bone) == hand
        return passed, bones.get(bone), hand
    present = sorted(b for b in others if b in bones)
    return not present, present, "no weapon bone (character without a weapon)"


def weapon_side_check(bone):
    """(check name, expected text) of the export-frame side check of the weapon mesh, None without a weapon bone.
    The weapon centroid must lie along rot @ (sign, 0, 0) (weapon_side_sign); .L keeps the Medusa name and text."""
    sign = weapon_side_sign(bone)
    if sign is None:
        return None
    if sign > 0:
        return "export_frame_bow_on_rotated_left", "bow on +Y of the export frame (UE -Y)"
    return "export_frame_bow_on_rotated_right", "weapon on -Y of the export frame (UE +Y)"


def content_key(p):
    """Lower-case hero key from asset_id (ASSET-MEDUSA-001 -> medusa, ASSET-KING-ARTHUR-001 -> king-arthur): the
    prefix of the probe labels (<key>-h2-blend / <key>-h2-fbx)."""
    key = re.sub(r"^ASSET-", "", str(p["asset_id"]), flags=re.I)
    key = re.sub(r"-\d+$", "", key)
    return key.lower()


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
