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
Old profiles (Medusa: one weapon part, contract Medusa -> weapon.L) resolve to exactly the previous behaviour.

New-hero rules (W1-d 2026-10-14, RB-15; new_hero_problems): a profile of any asset outside LEGACY_ASSETS (the MVP
Medusa and the pilot Achilles, Angel, Ancient Leshen), or with `profile_version` >= 2, must name
uv.density_reference_part (a body part), textures.team_mask.base_band.part (the base part) and preview.frame (with
`side`); a named part of any profile must have that role."""

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
    problems.extend(new_hero_problems(p))
    problems.extend(probe_skip_problems(p))
    problems.extend(w2c_problems(p))
    return problems


# ------------------------------------------------------------------ new-hero profile rules (W1-d 2026-10-14, RB-15, F29)
# The Medusa defaults that a copied profile silently inherits (uv.density_reference_part = Medusa's dress tripo_part_0,
# team_mask.base_band.part = tripo_part_2: Angel's trouser leg, F29; no preview.frame = the Medusa canon 1021 x 1540)
# are allowed only for the profiles written before this rule: the MVP (Medusa) and the skill pilot (Achilles, Angel,
# Ancient Leshen). Every other asset is a new hero (profile_version 2) and must name them; the roles of named parts are
# checked for every profile (all MVP and pilot profiles already name a body / base part there).
LEGACY_ASSETS = ("ASSET-MEDUSA-001", "ASSET-ACHILLES-001", "ASSET-ANGEL-001", "ASSET-ANCIENT-LESHEN-001")
NEW_HERO_PROFILE_VERSION = 2
PROFILE_RULES_DOC = "HANDBOOK §4.2 «Новый герой»"


def profile_version(p):
    """Rules version of the profile: optional top-level `profile_version` (int >= 1); absent -> 1 for LEGACY_ASSETS (the
    MVP and the pilot, old defaults allowed), 2 for every other asset_id (a new hero copied from Medusa without the key
    is still a new hero)."""
    v = p.get("profile_version")
    if v is None:
        return 1 if p.get("asset_id") in LEGACY_ASSETS else NEW_HERO_PROFILE_VERSION
    return v


def is_new_hero_profile(p):
    v = profile_version(p)
    return isinstance(v, int) and not isinstance(v, bool) and v >= NEW_HERO_PROFILE_VERSION


def _part_role_problem(p, where, name, role):
    if not isinstance(name, str) or name not in p["parts"]:
        return "%s: unknown part %r" % (where, name)
    if p["parts"][name].get("mesh") != role:
        return "%s: %s is a %s part, must be a %s part" % (where, name, p["parts"][name].get("mesh"), role)
    return None


def new_hero_problems(p):
    problems = []
    v = p.get("profile_version")
    if v is not None:
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            return ["profile_version must be an integer >= 1 (got %r)" % (v,)]
        if v < NEW_HERO_PROFILE_VERSION and p.get("asset_id") not in LEGACY_ASSETS:
            problems.append("profile_version %d is only for the MVP and pilot assets %s; a new hero is profile_version %d"
                            % (v, ", ".join(LEGACY_ASSETS), NEW_HERO_PROFILE_VERSION))
    uv_ref = p["uv"].get("density_reference_part")
    tm = p["textures"].get("team_mask")
    band = tm.get("base_band") if isinstance(tm, dict) else None
    band_part = band.get("part") if isinstance(band, dict) else None
    # roles: every profile that names the part (MVP and pilot included)
    if uv_ref is not None:
        msg = _part_role_problem(p, "uv.density_reference_part", uv_ref, "body")
        if msg:
            problems.append(msg)
    if band_part is not None:
        msg = _part_role_problem(p, "textures.team_mask.base_band.part", band_part, "base")
        if msg:
            problems.append(msg + " (Medusa's tripo_part_2 is Angel's trouser leg, F29)")
    if not is_new_hero_profile(p):
        return problems
    base = next((n for n, c in p["parts"].items() if c.get("mesh") == "base"), "<base part>")
    if uv_ref is None:
        problems.append("new hero (profile_version %d): uv.density_reference_part missing — name the large body part "
                        "the face texel density is compared with (the default tripo_part_0 is Medusa's dress; %s)"
                        % (profile_version(p), PROFILE_RULES_DOC))
    if band_part is None:
        problems.append("new hero (profile_version %d): textures.team_mask.base_band.part missing — name the base part "
                        "(%s here; Medusa's tripo_part_2 is another hero's trouser leg, F29; %s)"
                        % (profile_version(p), base, PROFILE_RULES_DOC))
    frame = p.get("preview", {}).get("frame") if isinstance(p.get("preview"), dict) else None
    hint = ('{"checks_report": "art/imagegen/concept-<key>-codex/checks-report.json", "side": "<SIDE_VIEW>"}')
    if frame is None:
        problems.append("new hero (profile_version %d): preview.frame missing — the ortho frames would use the Medusa "
                        "canon 1021 x 1540; set %s (framing.py; %s)" % (profile_version(p), hint, PROFILE_RULES_DOC))
    elif not isinstance(frame, dict) or not (isinstance(frame.get("checks_report"), str) and frame["checks_report"]
                                             or "px" in frame):
        problems.append("new hero: preview.frame must be %s or explicit numbers {\"px\": [W, H], ...} (framing.py)" % hint)
    elif frame.get("side") not in ("left", "right"):
        problems.append("new hero: preview.frame.side must be SIDE_VIEW of the asset card, left or right (got %r; the "
                        "default left is Medusa's)" % (frame.get("side"),))
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


# ------------------------------------------------------------------ rig probe skip list (W1-d integration of W1-e, RB-08)
# Names of tools/tripo-pipeline/anim/rig_deform_probe.py (EXT_TESTS, HAND_TWIST, "weapon_turn_" + weapon bone): only the
# extended probes may be skipped; the 7 legacy probes are the contract (the probe refuses to skip them as well).
PROBE_LEGACY = ("head_turn", "spine_bend_fwd", "arm_l_raise", "arm_r_raise", "forearm_l_bend", "thigh_l_flex",
                "thigh_r_flex")
PROBE_EXTENDED = ("forearm_r_bend", "shin_l_bend", "shin_r_bend", "foot_l_flex", "foot_r_flex", "hand_l_twist",
                  "hand_r_twist")
PROBE_WEAPON_TURN = "weapon_turn_"


def probe_skip(p):
    """Optional `rig.probe_skip` = [probe names]: extended probes the probes stage passes to rig_deform_probe.py as
    --skip (status skipped, out of N). [] when absent — the probe command line of every older profile is unchanged.
    Use: a figure without the probed limb (Ancient Leshen, legless trunk F53: shin_l_bend, shin_r_bend, foot_l_flex,
    foot_r_flex)."""
    return list(p.get("rig", {}).get("probe_skip") or [])


def probe_skip_problems(p):
    cfg = p.get("rig", {}).get("probe_skip")
    if cfg is None:
        return []
    if not isinstance(cfg, list) or not all(isinstance(n, str) and n for n in cfg):
        return ["rig.probe_skip must be a list of probe names (got %r)" % (cfg,)]
    problems = []
    weapon_turns = {PROBE_WEAPON_TURN + b[0] for b in p["rig"].get("bones", []) if str(b[0]).lower().startswith("weapon")}
    for name in cfg:
        if name in PROBE_LEGACY:
            problems.append("rig.probe_skip: %s is one of the 7 legacy probes (the rig contract), it cannot be skipped"
                            % name)
        elif name not in PROBE_EXTENDED and name not in weapon_turns:
            problems.append("rig.probe_skip: unknown probe %s (extended probes: %s)"
                            % (name, ", ".join(PROBE_EXTENDED + tuple(sorted(weapon_turns)))))
    if len(set(cfg)) != len(cfg):
        problems.append("rig.probe_skip: duplicates")
    return problems


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


# ------------------------------------------------------------------ W2-c opt-in options (skill pilot F83, F104, F107, F150)
# base.flatten_bottom (prepare), base.rim_smooth (retopo), textures.team_mask.base_band.height_m (uv: TeamMask.G and the
# base vertex mask UM_Mask.R), textures.band_repaint (textures). Absent key = the old code path, byte-identical outputs.
# Numbers and rules: base_ops.py (the bpy-free helpers); validation here (no import: the driver loads this file by path).
BASE_KEYS = ("flatten_bottom", "rim_smooth", "note")
FLATTEN_KEYS = ("floor_quantile", "band_m", "falloff_m", "down_normal_z", "note")
RIM_SMOOTH_KEYS = ("z_band_m", "parts", "window_m", "max_shift_m", "min_perimeter_cm", "ring_weight", "note")
BAND_REPAINT_KEYS = ("name", "part", "near", "band_m", "ring_m", "feather_m", "keep_hsv", "keys", "detail", "k",
                     "include_boxes_m", "exclude_boxes_m", "note")
BAND_REPAINT_MAPS = ("BC", "RM", "AO")


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _pair(x):
    return isinstance(x, list) and len(x) == 2 and all(_num(v) for v in x) and x[0] < x[1]


def base_flatten(p):
    """Optional `base.flatten_bottom` (object, {} = defaults of base_ops.FLATTEN_DEFAULTS): the prepare stage flattens the
    underside of the base part (both GLB twins) to a plane at z = 0 (pilot F83: ragged Tripo underside). None when absent."""
    b = p.get("base")
    return b.get("flatten_bottom") if isinstance(b, dict) else None


def base_rim_smooth(p):
    """Optional `base.rim_smooth` = {"z_band_m": [z0, z1], ...}: the retopo stage smooths the z of the boundary loops that
    lie inside the band (the base-top holes and the sole rims standing in them: pilot F104, teeth of 1-2.4 mm). None
    when absent."""
    b = p.get("base")
    return b.get("rim_smooth") if isinstance(b, dict) else None


def base_band_height(p):
    """Optional `textures.team_mask.base_band.height_m` = [z0, z1] (metres above the base bottom): the team band of the base
    is the base faces whose centroid lies in that slab (not facing down) instead of |n_z| <= normal_z_abs_max; the uv
    stage also writes it as the base vertex mask UM_Mask.R (pilot F143, F150). None when absent."""
    tm = p.get("textures", {}).get("team_mask")
    band = tm.get("base_band") if isinstance(tm, dict) else None
    return band.get("height_m") if isinstance(band, dict) else None


def band_repaint(p):
    """Optional `textures.band_repaint` = [{name, part, near, band_m, ...}]: the textures stage repaints the texels of
    `part` within band_m (3D, rest pose) of the `near` parts from the ring just outside the band (pilot F107: collar
    smears of the Tripo texture). [] when absent."""
    return list(p.get("textures", {}).get("band_repaint") or [])


def _boxes_problems(where, boxes):
    if not isinstance(boxes, list) or not boxes:
        return ["%s must be a non-empty list of {min_m: [x, y, z], max_m: [x, y, z]}" % where]
    for i, b in enumerate(boxes):
        if not (isinstance(b, dict) and all(isinstance(b.get(k), list) and len(b[k]) == 3 and all(_num(v) for v in b[k])
                                            for k in ("min_m", "max_m"))
                and all(lo < hi for lo, hi in zip(b["min_m"], b["max_m"]))):
            return ["%s[%d] must be {min_m: [x, y, z], max_m: [x, y, z]} with min < max" % (where, i)]
    return []


def _rim_smooth_problems(rs, parts):
    if not isinstance(rs, dict):
        return ["base.rim_smooth must be an object {z_band_m: [z0, z1], ...}"]
    problems = ["base.rim_smooth: unknown key %s" % k for k in rs if k not in RIM_SMOOTH_KEYS]
    if not _pair(rs.get("z_band_m")):
        problems.append("base.rim_smooth.z_band_m must be [z0, z1] in metres, z0 < z1 (got %r)" % (rs.get("z_band_m"),))
    names = rs.get("parts")
    if names is not None:
        if not isinstance(names, list) or not names:
            problems.append("base.rim_smooth.parts must be a non-empty list of parts (absent = every part)")
        else:
            problems += ["base.rim_smooth.parts: unknown part %s" % n for n in names if n not in parts]
    for key, hi, dflt in (("window_m", 0.03, 0.006), ("max_shift_m", 0.004, 0.002)):
        v = rs.get(key, dflt)
        if not (_num(v) and 0.0 < v <= hi):
            problems.append("base.rim_smooth.%s must be in (0, %s] m (got %r)" % (key, hi, v))
    mp = rs.get("min_perimeter_cm", 1.0)
    if not (_num(mp) and mp >= 0):
        problems.append("base.rim_smooth.min_perimeter_cm must be >= 0 (got %r)" % (mp,))
    rw = rs.get("ring_weight", 0.5)
    if not (_num(rw) and 0.0 <= rw <= 1.0):
        problems.append("base.rim_smooth.ring_weight must be in [0, 1] (got %r)" % (rw,))
    return problems


def _flatten_problems(fl):
    if not isinstance(fl, dict):
        return ["base.flatten_bottom must be an object ({} = defaults)"]
    problems = ["base.flatten_bottom: unknown key %s" % k for k in fl if k not in FLATTEN_KEYS]
    q = fl.get("floor_quantile", 0.5)
    if not (_num(q) and 0.0 <= q <= 1.0):
        problems.append("base.flatten_bottom.floor_quantile must be in [0, 1] (got %r)" % (q,))
    band = fl.get("band_m", 0.008)
    if not (_num(band) and 0.0 <= band <= 0.015):
        problems.append("base.flatten_bottom.band_m must be in [0, 0.015] m (got %r)" % (band,))
    fo = fl.get("falloff_m", 0.012)
    if not (_num(fo) and 0.0 <= fo <= 0.03):
        problems.append("base.flatten_bottom.falloff_m must be in [0, 0.03] m (got %r)" % (fo,))
    dz = fl.get("down_normal_z", -0.5)
    if not (_num(dz) and -1.0 < dz < 0.0):
        problems.append("base.flatten_bottom.down_normal_z must be in (-1, 0) (got %r)" % (dz,))
    return problems


def _band_repaint_problems(br, parts):
    if not isinstance(br, list) or not br:
        return ["textures.band_repaint must be a non-empty list of bands"]
    problems, seen = [], set()
    for i, b in enumerate(br):
        w = "textures.band_repaint[%d]" % i
        if not isinstance(b, dict):
            problems.append("%s must be an object" % w)
            continue
        problems += ["%s: unknown key %s" % (w, k) for k in b if k not in BAND_REPAINT_KEYS]
        if not isinstance(b.get("name"), str) or not b["name"] or b["name"] in seen:
            problems.append("%s.name must be a unique non-empty string" % w)
        seen.add(b.get("name"))
        if b.get("part") not in parts:
            problems.append("%s.part: unknown part %r" % (w, b.get("part")))
        near = b.get("near")
        if not isinstance(near, list) or not near or any(n not in parts for n in near) or b.get("part") in near:
            problems.append("%s.near must be a non-empty list of other parts (got %r)" % (w, near))
        for key, dflt in (("band_m", None), ("ring_m", 0.006)):
            v = b.get(key, dflt)
            if not (_num(v) and 0.0 < v <= 0.05):
                problems.append("%s.%s must be in (0, 0.05] m (got %r)" % (w, key, v))
        fe = b.get("feather_m", 0.002)
        if not (_num(fe) and 0.0 <= fe <= (b["band_m"] if _num(b.get("band_m")) else 0.0)):
            problems.append("%s.feather_m must be in [0, band_m] (got %r)" % (w, fe))
        keys = b.get("keys", ["BC"])
        if not (isinstance(keys, list) and keys and all(k in BAND_REPAINT_MAPS for k in keys) and len(set(keys)) == len(keys)):
            problems.append("%s.keys must be a non-empty subset of %s (got %r)" % (w, list(BAND_REPAINT_MAPS), keys))
        det = b.get("detail")
        if det is not None and not (_pair(det) and 0.0 < det[0] <= 1.0 <= det[1]):
            problems.append("%s.detail must be [lo, hi] with 0 < lo <= 1 <= hi (got %r)" % (w, det))
        k = b.get("k", 8)
        if not (isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= 64):
            problems.append("%s.k must be an integer in [1, 64] (got %r)" % (w, k))
        kh = b.get("keep_hsv")
        if kh is not None and not (isinstance(kh, dict) and kh and all(
                key in ("v_min", "v_max", "s_min", "s_max") and _num(v) and 0.0 <= v <= 1.0 for key, v in kh.items())):
            problems.append("%s.keep_hsv must be an object of v_min / v_max / s_min / s_max in [0, 1] (got %r)" % (w, kh))
        for key in ("include_boxes_m", "exclude_boxes_m"):
            if key in b:
                problems += _boxes_problems("%s.%s" % (w, key), b[key])
    return problems


def w2c_problems(p):
    problems = []
    base = p.get("base")
    if base is not None:
        if not isinstance(base, dict):
            return ["base must be an object {flatten_bottom, rim_smooth}"]
        problems += ["base: unknown key %s (allowed: %s)" % (k, ", ".join(BASE_KEYS)) for k in base if k not in BASE_KEYS]
        if base.get("flatten_bottom") is not None:
            problems += _flatten_problems(base["flatten_bottom"])
        if base.get("rim_smooth") is not None:
            problems += _rim_smooth_problems(base["rim_smooth"], p["parts"])
    hm = base_band_height(p)
    if hm is not None:
        top = float(p.get("scale", {}).get("base_height_m", 0.06))
        if not (_pair(hm) and hm[0] >= 0.0 and hm[1] <= top + 0.01):
            problems.append("textures.team_mask.base_band.height_m must be [z0, z1] with 0 <= z0 < z1 <= base_height_m + "
                            "0.01 (metres above the base bottom; got %r)" % (hm,))
    br = p.get("textures", {}).get("band_repaint")
    if br is not None:
        problems += _band_repaint_problems(br, p["parts"])
    return problems
