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
import math
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
    problems.extend(cloth_shell_problems(p))
    problems.extend(figure_top_part_problems(p))
    problems.extend(part_offsets_problems(p))
    return problems


# ------------------------------------------------------------------ part offsets (Ancient Leshen stage 5 r3, 2026-10-14)
PART_OFFSET_MAX_M = 0.05  # seats a detached rigid detail on its perch; not a tool to move limbs


def part_offsets(p):
    """Optional `prepare.part_offsets_m` = {tripo_part_N: [dx, dy, dz]}: the prepare stage translates the listed source
    parts (both GLB twins, HPG_* and HPT_*) by this vector right after the frame map, i.e. in the FINAL frame in metres
    (Blender axes of the profile: -Y front, +X the figure's left, +Z up — the frame of retopo.dense_regions, rig.bones and
    seams targets). The frame map itself (scale, base footprint, figure top) is computed before the offset, so the other
    parts keep their coordinates to the bit. Use: a rigid detail that Tripo generated off its perch (Ancient Leshen: the
    crow tripo_part_8 hung 2.9 cm in front of the right forearm). None when absent — every profile written before the
    key (Medusa, Arthur, Merlin, Harpy, Achilles, Angel, Leshen r1/r2) takes the old code path and keeps its bytes."""
    prep = p.get("prepare")
    return prep.get("part_offsets_m") if isinstance(prep, dict) else None


def part_offsets_problems(p):
    prep = p.get("prepare")
    if prep is None:
        return []
    if not isinstance(prep, dict):
        return ["prepare must be an object"]
    cfg = prep.get("part_offsets_m")
    if cfg is None:
        return []
    if not isinstance(cfg, dict) or not cfg:
        return ["prepare.part_offsets_m must be a non-empty object {tripo_part_N: [dx, dy, dz]}"]
    problems = []
    for name, d in cfg.items():
        if name not in p["parts"]:
            problems.append("prepare.part_offsets_m: unknown part %s" % name)
            continue
        if p["parts"][name].get("mesh") == "base":
            problems.append("prepare.part_offsets_m: %s is the base (normalised to the card-04 footprint)" % name)
            continue
        if not (isinstance(d, list) and len(d) == 3
                and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in d)):
            problems.append("prepare.part_offsets_m.%s must be [dx, dy, dz] in metres (got %r)" % (name, d))
            continue
        length = math.sqrt(sum(float(x) ** 2 for x in d))
        if length == 0.0:
            problems.append("prepare.part_offsets_m.%s is zero (drop the entry)" % name)
        elif length > PART_OFFSET_MAX_M:
            problems.append("prepare.part_offsets_m.%s: %.4f m > %s m" % (name, length, PART_OFFSET_MAX_M))
    return problems


# ------------------------------------------------------------------ figure top part (pilot 2026-10-13, NOTES F28/F58)
def figure_top_part(p):
    """Optional `scale.figure_top_part` (a tripo_part_N): the part whose highest source vertex is mapped to
    scale.figure_top_m. None when absent: the old rule, the highest vertex of any non-base part (weapon, antlers and
    raised blades included) — Medusa, Arthur, Merlin, Harpy and every profile written before the key."""
    return p.get("scale", {}).get("figure_top_part")


def figure_top_part_problems(p):
    name = figure_top_part(p)
    if name is None:
        return []
    if name not in p["parts"]:
        return ["scale.figure_top_part: unknown part %s" % name]
    if p["parts"][name].get("mesh") == "base":
        return ["scale.figure_top_part: %s is the base" % name]
    return []


def figure_top_source_z(p, part_top_z):
    """Source z mapped to scale.figure_top_m (prepare): part_top_z = {part: highest source z} of the non-base parts."""
    name = figure_top_part(p)
    if name is None:
        return max(part_top_z.values())
    return part_top_z[name]


def frame_top_m(p, run_dir):
    """Height in metres (from z = 0) that the concept framing spans (framing.cameras): the top of the whole figure
    silhouette, as the concept mask measures it. Without scale.figure_top_part that is scale.figure_top_m (the old
    value, byte for byte); with it, the figure bounds top of the run's reports/prepare-report.json
    (figure_bounds_final_m max z: a raised blade or antlers above the budget top)."""
    if figure_top_part(p) is None:
        return p["scale"]["figure_top_m"]
    rep = json.loads((Path(run_dir) / "reports" / "prepare-report.json").read_text(encoding="utf-8"))
    return float(rep["figure_bounds_final_m"][1][2])


# ------------------------------------------------------------------ seams ray grid (pilot 2026-10-13, NOTES F55 / F65)
SEAMS_MARGIN_M = 0.1
SEAMS_POSED_CLEARANCE_M = 0.005


def seams_grid_bounds(rest_lo, rest_hi, posed_lo, posed_hi, rcfg):
    """(lo, hi, extended) of the one see-through ray grid of every pose (st_seams.see_through): the rest bounds +
    seams.raycast.margin_m, each side pushed out to the posed bounds + seams.raycast.posed_clearance_m where a probe pose
    leaves it. A raised arm or a swung spear that left rest + margin made the rays start inside the hand (false blobs
    295 / 92 / 37 px in the pilot). Elementwise min / max: a side that no pose leaves keeps the old float exactly, so a
    figure whose poses stay inside (Medusa: 92.8 mm of the 100 mm margin) keeps its grid, pixel phases and report.
    extended = [[lo by], [hi by]] in metres (rounded 1e-4), or None when nothing moved."""
    import numpy as np

    margin = float(rcfg.get("margin_m", SEAMS_MARGIN_M))
    clearance = float(rcfg.get("posed_clearance_m", SEAMS_POSED_CLEARANCE_M))
    lo0, hi0 = np.asarray(rest_lo) - margin, np.asarray(rest_hi) + margin
    lo = np.minimum(lo0, np.asarray(posed_lo) - clearance)
    hi = np.maximum(hi0, np.asarray(posed_hi) + clearance)
    if np.array_equal(lo, lo0) and np.array_equal(hi, hi0):
        return lo0, hi0, None
    return lo, hi, [[round(float(x), 4) for x in lo0 - lo], [round(float(x), 4) for x in hi - hi0]]


# ------------------------------------------------------------------ cloth shell (decision П3-3, Achilles pilot 2026-10-13)
CLOTH_SHELL_MAX_OFFSET_MM = 1.0  # "offset inward by a fraction of a millimetre" (decision П3-3)


def cloth_shell(p):
    """Optional `rig.cloth_shell` = {"parts": [tripo_part_N, ...], "offset_mm": float}: the listed single-sheet cloth parts
    become a thin closed shell in the rig stage (st_rig.add_cloth_shell). None when the key is absent — every profile
    written before the key (Medusa, Arthur, Merlin, Harpy) takes the old code path unchanged."""
    return p.get("rig", {}).get("cloth_shell")


def cloth_shell_problems(p):
    cfg = cloth_shell(p)
    if cfg is None:
        return []
    problems = []
    parts = cfg.get("parts") if isinstance(cfg, dict) else None
    if not parts or not isinstance(parts, list):
        return ["rig.cloth_shell.parts must be a non-empty list of parts"]
    for name in parts:
        if name not in p["parts"]:
            problems.append("rig.cloth_shell: unknown part %s" % name)
        elif p["parts"][name].get("mesh") == "base":
            problems.append("rig.cloth_shell: %s is the base (not skinned)" % name)
    if len(set(parts)) != len(parts):
        problems.append("rig.cloth_shell.parts: duplicates")
    off = cfg.get("offset_mm")
    if not isinstance(off, (int, float)) or isinstance(off, bool) or not 0 < off <= CLOTH_SHELL_MAX_OFFSET_MM:
        problems.append("rig.cloth_shell.offset_mm must be in (0, %s] mm (got %r)" % (CLOTH_SHELL_MAX_OFFSET_MM, off))
    return problems


# ------------------------------------------------------------------ weapon side and presence (D-1)
def has_weapon(p):
    """True when a part is the weapon mesh (`"mesh": "weapon"`)."""
    return any(cfg.get("mesh") == "weapon" for cfg in p["parts"].values())


def face_part_key(p):
    """Integer N of the tripo_part_N that carries the face: the `part` of retopo.dense_regions `face`.

    The rig and look-dev stages measure the face normal on this part. Medusa's face is tripo_part_1, which was
    hard-coded until the Achilles pilot (2026-10-13: Achilles' part 1 is the base, the head is part 5). A profile
    without a face region keeps the old value 1."""
    face = next((d for d in p["retopo"].get("dense_regions", []) if d.get("name") == "face"), None)
    m = re.search(r"tripo_part_(\d+)", (face or {}).get("part") or "")
    return int(m.group(1)) if m else 1


def uv_density_reference_part(p):
    """The body part the face texel density is compared with (check priority_face_denser_than_body of the uv stage):
    optional `uv.density_reference_part`, default tripo_part_0 (Medusa's dress, the old hard-coded value)."""
    return p.get("uv", {}).get("density_reference_part", "tripo_part_0")


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

    base_bounds: ((x0, y0, z0), (x1, y1, z1)) of the base part; figure_top_z: highest source vertex of the non-base
    parts, or of scale.figure_top_part when the profile names one (figure_top_source_z).
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
