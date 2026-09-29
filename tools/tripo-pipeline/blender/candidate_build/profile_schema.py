"""Validation of skeletal-candidate build profiles (pure Python, stdlib only).

Used by blender/build_candidate.py before any Blender work and by tripo_pipeline.py (preflight
build_profile_valid) so a profile error stops the run before the atlas stage. validate(profile) returns a
list of problems (empty = valid); every problem names the profile key.
"""

FLOW_DEFAULT = "whole-figure"
FLOWS = ("whole-figure", "seated-parts")
BASE_MODES = ("normalise-part", "parametric")
WEAPON_MODES = ("split-from-part", "parts", "part")
FRAMES = ("final", "source")
SIDES = ("+X", "-X", "+Y", "-Y")
TOE_METHODS = ("low_band", "front_quartile")
SOCKET_TARGETS = ("bone_head", "part_bbox_centre", "foot_tip")
GROUP_KINDS = ("rigid", "heat", "wing_span", "axis_blend")
EXPORT_AXES = ("front", "left", "right", "weapon_side")
TEAM_MASK_METHODS = ("hsv-hard-gaussian", "hsv-smooth-box")


def flow_of(profile):
    return ((profile.get("build") or {}).get("flow")) or FLOW_DEFAULT


def _get(profile, path):
    node = profile
    for key in path.split("."):
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _require(profile, problems, *paths):
    for path in paths:
        if _get(profile, path) is None:
            problems.append("missing %s" % path)


def _part_name(value):
    return isinstance(value, str) and value.startswith("tripo_part_") and value[len("tripo_part_"):].isdigit()


def _bones(profile, problems):
    bones = _get(profile, "armature.bones") or []
    names = set()
    for i, spec in enumerate(bones):
        if not isinstance(spec, list) or len(spec) not in (4, 5):
            problems.append("armature.bones[%d]: [name, parent, head, tail(, frame)] expected" % i)
            continue
        name, parent = spec[0], spec[1]
        if parent is not None and parent not in names:
            problems.append("armature.bones[%d] %s: parent %s must come earlier" % (i, name, parent))
        if len(spec) == 5 and spec[4] not in FRAMES:
            problems.append("armature.bones[%d] %s: frame must be one of %s" % (i, name, FRAMES))
        for key, point in (("head", spec[2]), ("tail", spec[3])):
            if not (isinstance(point, list) and len(point) == 3 and all(isinstance(c, (int, float)) for c in point)):
                problems.append("armature.bones[%d] %s: %s must be [x, y, z]" % (i, name, key))
        names.add(name)
    return names


def _common(profile, problems):
    if profile.get("builder"):
        problems.append("builder: external builders are not run by the CLI (tool >= 0.5.0); the build profile must "
                        "describe the build for blender/build_candidate.py (flow %s)" % "|".join(FLOWS))
    _require(profile, problems, "schema", "profile_id", "asset_id", "source_role", "fbx_preset", "expected_part_count",
             "atlas.size", "atlas.gutter_px", "atlas.texture_prefix", "scale.figure_height_m", "meshes.body.object",
             "meshes.body.mesh", "meshes.body.active_part", "meshes.base.object", "meshes.base.footprint_m",
             "materials.atlas", "orientation.flip_below_score", "orientation.expected_inside_out_parts",
             "orientation.min_score_after_fix", "armature.object", "armature.max_influences", "armature.bones",
             "exports.skeletal_fbx", "exports.base_fbx", "expectations.triangles", "expectations.bones",
             "expectations.skeletal_material_slots", "expectations.base_material_slots")
    fp = _get(profile, "meshes.base.footprint_m")
    if fp is not None and not (isinstance(fp, list) and len(fp) == 3 and all(v > 0 for v in fp)):
        problems.append("meshes.base.footprint_m: three positive numbers expected")
    names = _bones(profile, problems)
    for i, sock in enumerate(profile.get("sockets") or []):
        if sock.get("bone") not in names:
            problems.append("sockets[%d] %s: bone %s is not in armature.bones" % (i, sock.get("name"), sock.get("bone")))
        loc = sock.get("location_uu")
        if loc is not None and not (isinstance(loc, list) and len(loc) == 3):
            problems.append("sockets[%d] %s: location_uu must be [x, y, z] or null (null: predicted by the build)"
                            % (i, sock.get("name")))
        target = sock.get("target")
        if target is not None and not isinstance(target, dict):
            problems.append("sockets[%d] %s: target must be an object {kind, ...} (a description goes to target_note)"
                            % (i, sock.get("name")))
            continue
        kind = (target or {}).get("kind")
        if kind is not None and kind not in SOCKET_TARGETS:
            problems.append("sockets[%d] %s: target.kind must be one of %s" % (i, sock.get("name"), SOCKET_TARGETS))
    mask = _get(profile, "team_color.mask")
    if mask is not None:
        if mask.get("method") not in TEAM_MASK_METHODS:
            problems.append("team_color.mask.method must be one of %s" % (TEAM_MASK_METHODS,))
        if not mask.get("texture"):
            problems.append("team_color.mask.texture (atlas output file name) is required")
    for key, tex in ((_get(profile, "ue.textures") or {}).items()):
        if not tex.get("file_key"):
            problems.append("ue.textures.%s: file_key (atlas output key) is required" % key)
    return names


def _whole_figure(profile, problems, bones):
    _require(profile, problems, "meshes.bow.object", "meshes.bow.part", "meshes.bow.bone", "meshes.base.part",
             "weights", "expectations.face_slot_polygons")
    face = _get(profile, "anatomy.face") or _get(profile, "materials.face_slot.part")
    if not face:
        problems.append("anatomy.face (or materials.face_slot.part) must name the face part")
    if _get(profile, "expectations.neck_polygons") is not None and not _get(profile, "anatomy.neck"):
        problems.append("expectations.neck_polygons needs anatomy.neck (the neck part)")
    if not isinstance(profile.get("weights"), list):
        problems.append("weights: a list of part rules (bone | split_z | blend) expected in flow whole-figure")
    side = _get(profile, "axes.blender_bow_side")
    if side is not None and side not in SIDES:
        problems.append("axes.blender_bow_side must be one of %s" % (SIDES,))


def _seated(profile, problems, bones):
    _require(profile, problems, "scale.top_part", "meshes.base.mode", "meshes.base.mesh", "weld.distance_m",
             "weights.clean_below", "weights.groups", "orientation.corner_normal_opposed_max_fraction")
    base_mode = _get(profile, "meshes.base.mode")
    drops = _get(profile, "meshes.drop_parts") or {}
    if base_mode not in BASE_MODES:
        problems.append("meshes.base.mode must be one of %s" % (BASE_MODES,))
    elif base_mode == "normalise-part":
        _require(profile, problems, "meshes.base.part")
    else:
        _require(profile, problems, "meshes.base.source_part", "base_parametric.radius_bottom_m",
                 "base_parametric.height_m", "base_parametric.pips", "base_parametric.mask.attribute",
                 "base_parametric.material", "base_parametric.preview_colours_linear")
        if _get(profile, "meshes.base.source_part") not in drops:
            problems.append("meshes.base.source_part must be listed in meshes.drop_parts (replaced by the parametric base)")
        if _get(profile, "closure.base_top"):
            problems.append("closure.base_top needs meshes.base.mode normalise-part")
    weapon = _get(profile, "meshes.weapon")
    if weapon is not None:
        mode = weapon.get("mode")
        if mode not in WEAPON_MODES:
            problems.append("meshes.weapon.mode must be one of %s (or meshes.weapon null)" % (WEAPON_MODES,))
        for key in ("object", "mesh", "bone"):
            if not weapon.get(key):
                problems.append("meshes.weapon.%s is required" % key)
        if weapon.get("bone") and weapon["bone"] not in bones:
            problems.append("meshes.weapon.bone %s is not in armature.bones" % weapon["bone"])
        if mode == "split-from-part":
            if not _part_name(weapon.get("split_from")):
                problems.append("meshes.weapon.split_from must name a tripo_part_N")
            _require(profile, problems, "weapon_split.axis_fit", "weapon_split.sword_if_z_at_least",
                     "weapon_split.sword_if_z_below", "weapon_split.saturation_min", "weapon_split.value_min",
                     "weapon_split.grip_radius_m", "weapon_split.min_island_polygons")
        elif mode == "parts":
            if not (isinstance(weapon.get("parts"), list) and weapon["parts"] and all(_part_name(p) for p in weapon["parts"])):
                problems.append("meshes.weapon.parts must list tripo_part_N names")
            _require(profile, problems, "weapon_assembly.grip_bridge")
        elif mode == "part" and not _part_name(weapon.get("part")):
            problems.append("meshes.weapon.part must name a tripo_part_N")
        if _get(profile, "armature.weapon_axis_tolerance_m") is None:
            problems.append("missing armature.weapon_axis_tolerance_m (weapon bone check)")
        if _get(profile, "axes.blender_weapon_side") not in SIDES:
            problems.append("axes.blender_weapon_side must be one of %s when there is a weapon" % (SIDES,))
    frame = _get(profile, "weights.coordinates_frame") or "final"
    if frame not in FRAMES:
        problems.append("weights.coordinates_frame must be one of %s" % (FRAMES,))
    for i, group in enumerate(_get(profile, "weights.groups") or []):
        kinds = [k for k in GROUP_KINDS if k in group]
        if len(kinds) != 1:
            problems.append("weights.groups[%d]: exactly one of %s expected" % (i, GROUP_KINDS))
        if not group.get("parts"):
            problems.append("weights.groups[%d]: parts required" % i)
        for ramp in group.get("height_ramps") or []:
            keys = set(ramp)
            if not ({"zero_above_z", "full_below_z"} <= keys or {"zero_below_z", "full_above_z"} <= keys or
                    ("axis" in ramp and ({"zero_above", "full_below"} <= keys or {"zero_below", "full_above"} <= keys))):
                problems.append("weights.groups[%d].height_ramps: zero_above_z/full_below_z, zero_below_z/full_above_z "
                                "or axis + zero_above/full_below|zero_below/full_above" % i)
    ref = _get(profile, "orientation.per_face_reference")
    if ref is not None:
        for key in ("parts", "source_id", "role", "max_reference_distance_m", "smoothing_lambda",
                    "smoothing_max_sweeps", "max_inconsistent_after"):
            if ref.get(key) is None:
                problems.append("missing orientation.per_face_reference.%s" % key)
    for name, cap in (profile.get("open_loop_caps") or {}).items():
        if not _part_name(name):
            problems.append("open_loop_caps: key %s must be a tripo_part_N" % name)
        for key in ("loops_source_centres", "tolerance_m", "min_vertices"):
            if cap.get(key) is None:
                problems.append("missing open_loop_caps.%s.%s" % (name, key))
    closure = profile.get("closure") or {}
    if closure and closure.get("diagnostic_weld_m") is None:
        problems.append("missing closure.diagnostic_weld_m")
    feet = _get(profile, "anatomy.feet")
    if feet is not None and not (isinstance(feet, dict) and sorted(feet) == ["L", "R"] and all(_part_name(p) for p in feet.values())):
        problems.append("anatomy.feet must be {\"L\": tripo_part_N, \"R\": tripo_part_N}")
    method = _get(profile, "anatomy.front.feet.method")
    if method is not None and method not in TOE_METHODS:
        problems.append("anatomy.front.feet.method must be one of %s" % (TOE_METHODS,))
    for i, ind in enumerate(_get(profile, "anatomy.export_frame_indicators") or []):
        if ind.get("axis") not in EXPORT_AXES:
            problems.append("anatomy.export_frame_indicators[%d].axis must be one of %s" % (i, EXPORT_AXES))
        if ind.get("what") != "weapon" and not str(ind.get("what", "")).startswith("part:"):
            problems.append("anatomy.export_frame_indicators[%d].what must be weapon or part:<name>" % i)
        if ind.get("axis") == "weapon_side" and not _get(profile, "axes.blender_weapon_side"):
            problems.append("anatomy.export_frame_indicators[%d]: axis weapon_side needs axes.blender_weapon_side" % i)
    sink = _get(profile, "anatomy.feet_sink_m")
    if sink is not None and not (isinstance(sink, list) and len(sink) == 2 and sink[0] <= sink[1]):
        problems.append("anatomy.feet_sink_m must be [low, high] metres")


def validate(profile):
    problems = []
    if not isinstance(profile, dict):
        return ["profile is not a JSON object"]
    flow = flow_of(profile)
    if flow not in FLOWS:
        return ["build.flow must be one of %s" % (FLOWS,)]
    bones = _common(profile, problems)
    if flow == "whole-figure":
        _whole_figure(profile, problems, bones)
    else:
        _seated(profile, problems, bones)
    return problems
