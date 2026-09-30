"""UE editor Python task (LIVE editor, run by tools/art/material_library/ue_v2_scene.py): M_UM_Figure_v2 test scene.

ARGS {"op": ...}
  setup   {"level", "hide_label_prefixes", "keep_labels", "lights": {"off": [...], "key": {...}}, "sky": {...},
           "spheres": [{"label", "location", "scale", "material"}], "probe": {...} | null}
          on the already loaded P1.7 Cobble control level: hides its review figures, applies the Cobble light profile
          in memory (same as tools/tripo-pipeline/review/ue_py/h2_review_ue.py setup), spawns the test spheres
          (/Engine/BasicShapes/Sphere, Movable, no collision) with their MIs. `probe` builds an UNSAVED scratch
          material in /Game/UM/Materials/v2/_probe that compares the core's derivative tangent frame with the engine
          Transform(Local -> Tangent) (emissive R = |error| with +grad v as tangent Y, G = with -grad v) and puts it
          on one more sphere. Nothing is saved; the host reloads the previous level at the end.
  drop_probe  deletes /Game/UM/Materials/v2/_probe (never saved).
  accent_probe {"textures": {key: png}, "instances": [{"name", "parent", "scalars", "vectors", "textures", "switches"}]}
          (v2.1 test, ue_v2_accent.py) imports hero TeamAccent PNGs into /Game/UM/Materials/v2/_probe (TC_Grayscale,
          sRGB off, NeverStream) and creates UNSAVED child MIs of the hero MIs there (static switch UseTeamAccent needs
          a constant MI, not a MID); a texture value "probe:<key>" is the imported PNG. Deleted by drop_probe, never
          saved.
  figure  spawns a SkeletalMeshActor; the material goes on every slot of the mesh.
Camera / materials / cleanup: tools/tripo-pipeline/review/ue_py/control_scene_ue.py (ops by actor label).
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
actors_sub = u.get_editor_subsystem(u.EditorActorSubsystem)
MEL = u.MaterialEditingLibrary
EAL = u.EditorAssetLibrary
PROBE_DIR = "/Game/UM/Materials/v2/_probe"

PROBE_CODE = r"""
float3 Nn = normalize(N0);
float3 v = normalize(Nn + float3(0.3, -0.5, 0.4));
V = v;
float3 dPdx = ddx(P), dPdy = ddy(P);
float2 dU0x = ddx(UV0), dU0y = ddy(UV0);
float ps = 1.0 / max(max(length(dPdx), length(dPdy)), 1e-20);
float3 ex = dPdx * ps, ey = dPdy * ps;
float3 dp2perp = cross(ey, Nn);
float3 dp1perp = cross(Nn, ex);
float usc = 1.0 / max(max(max(abs(dU0x.x), abs(dU0x.y)), max(abs(dU0y.x), abs(dU0y.y))), 1e-20);
float3 T0 = dp2perp * (dU0x.x * usc) + dp1perp * (dU0y.x * usc);
float3 B0 = dp2perp * (dU0x.y * usc) + dp1perp * (dU0y.y * usc);
float3 tt = T0 - Nn * dot(Nn, T0);
float tl = dot(tt, tt);
float3 Ta = tl > 1e-30 ? tt * rsqrt(tl) : float3(1, 0, 0);
float3 Bc = cross(Nn, Ta);
float3 Ba = dot(Bc, B0) < 0.0 ? -Bc : Bc;
return float3(dot(v, Ta), dot(v, Ba), dot(v, Nn));
"""


def vec(v):
    return u.Vector(float(v[0]), float(v[1]), float(v[2]))


def by_label(label, required=True):
    hits = [a for a in actors_sub.get_all_level_actors() if a.get_actor_label() == label]
    if required and len(hits) != 1:
        raise RuntimeError("actor %r: %d matches" % (label, len(hits)))
    return hits[0] if hits else None


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    a = u.load_asset(obj(path))
    if a is None:
        raise RuntimeError("asset not found: %s" % path)
    return a


def current_level():
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    path = w.get_path_name().split(".")[0] if w else None
    del w
    return path


def spawn_sphere(spec, material):
    old = by_label(spec["label"], required=False)
    if old is not None:
        actors_sub.destroy_actor(old)
    a = actors_sub.spawn_actor_from_class(u.StaticMeshActor, vec(spec["location"]), u.Rotator(0, 0, 0))
    comp = a.static_mesh_component
    comp.set_mobility(u.ComponentMobility.MOVABLE)
    comp.set_static_mesh(load("/Engine/BasicShapes/Sphere"))
    comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    s = float(spec["scale"])
    a.set_actor_scale3d(u.Vector(s, s, s))
    r = spec.get("rotation", [0.0, 0.0, 0.0])
    a.set_actor_rotation(u.Rotator(roll=float(r[2]), pitch=float(r[0]), yaw=float(r[1])), False)
    comp.set_material(0, material)
    a.set_actor_label(spec["label"])
    return a


def build_probe(local_unit_m):
    at = u.AssetToolsHelpers.get_asset_tools()
    if EAL.does_directory_exist(PROBE_DIR):
        EAL.delete_directory(PROBE_DIR)
    m = at.create_asset("M_UM_v2_FrameProbe", PROBE_DIR, u.Material, u.MaterialFactoryNew())
    m.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    e = {}

    def add(nid, cls, x, y, **props):
        n = MEL.create_material_expression(m, getattr(u, "MaterialExpression" + cls), x, y)
        for k, v in props.items():
            n.set_editor_property(k, v)
        e[nid] = n
        return n

    def link(a, ao, b, bi):
        if not MEL.connect_material_expressions(e[a], ao, e[b], bi):
            raise RuntimeError("probe link %s -> %s.%s" % (a, b, bi))

    add("psp", "PreSkinnedPosition", -1400, 0)
    add("psn", "PreSkinnedNormal", -1400, 150)
    add("vi_p", "VertexInterpolator", -1200, 0)
    add("vi_n", "VertexInterpolator", -1200, 150)
    add("uv0", "TextureCoordinate", -1200, 300, coordinate_index=0)
    link("psp", "", "vi_p", "VS")
    link("psn", "", "vi_n", "VS")
    add("scale", "Multiply", -1000, 0, const_b=float(local_unit_m))
    link("vi_p", "PS", "scale", "A")
    c = add("core", "Custom", -800, 0, code=PROBE_CODE, output_type=u.CustomMaterialOutputType.CMOT_FLOAT3,
            description="FrameProbe")
    ins = []
    for name in ("P", "N0", "UV0"):
        ci = u.CustomInput()
        ci.set_editor_property("input_name", name)
        ins.append(ci)
    c.set_editor_property("inputs", ins)
    co = u.CustomOutput()
    co.set_editor_property("output_name", "V")
    co.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT3)
    c.set_editor_property("additional_outputs", [co])
    link("scale", "", "core", "P")
    link("vi_n", "PS", "core", "N0")
    link("uv0", "", "core", "UV0")
    add("xf", "Transform", -600, 200,
        transform_source_type=u.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_LOCAL,
        transform_type=u.MaterialVectorCoordTransform.TRANSFORM_TANGENT)
    link("core", "V", "xf", "")
    add("xfn", "Normalize", -450, 200)
    link("xf", "", "xfn", "")
    # error with +grad v (R) and with the Y axis flipped (G)
    add("d_plus", "Subtract", -300, 0)
    link("core", "return", "d_plus", "A")
    link("xfn", "", "d_plus", "B")
    add("l_plus", "Length", -150, 0)
    link("d_plus", "", "l_plus", "")
    add("flip", "Multiply", -450, 350, const_b=1.0)
    add("flipc", "Constant3Vector", -600, 350, constant=u.LinearColor(1.0, -1.0, 1.0, 0.0))
    link("core", "return", "flip", "A")
    link("flipc", "", "flip", "B")
    add("d_minus", "Subtract", -300, 350)
    link("flip", "", "d_minus", "A")
    link("xfn", "", "d_minus", "B")
    add("l_minus", "Length", -150, 350)
    link("d_minus", "", "l_minus", "")
    add("rg", "AppendVector", 0, 150)
    link("l_plus", "", "rg", "A")
    link("l_minus", "", "rg", "B")
    add("rgb", "AppendVector", 150, 150)
    add("zero", "Constant", 0, 300, r=0.0)
    link("rg", "", "rgb", "A")
    link("zero", "", "rgb", "B")
    add("half", "Multiply", 300, 150, const_b=0.5)
    link("rgb", "", "half", "A")
    add("eai", "EyeAdaptationInverse", 450, 150)
    add("one", "Constant", 300, 300, r=1.0)
    link("half", "", "eai", "LightValueInput")
    link("one", "", "eai", "AlphaInput")
    if not MEL.connect_material_property(e["eai"], "EyeAdaptationInverse", u.MaterialProperty.MP_EMISSIVE_COLOR):
        raise RuntimeError("probe emissive")
    errors = MEL.recompile_material(m)
    return m, [str(x) for x in (errors or [])]


out = {"op": args["op"]}
op = args["op"]
if op == "setup":
    level = current_level()
    if level != args["level"]:
        raise RuntimeError("review level %s is not open (current %s)" % (args["level"], level))
    hidden = []
    keep = set(args.get("keep_labels") or [])
    for a in actors_sub.get_all_level_actors():
        label = a.get_actor_label()
        if label in keep or not any(label.startswith(p) for p in args["hide_label_prefixes"]):
            continue
        if isinstance(a, (u.StaticMeshActor, u.SkeletalMeshActor)):
            a.set_is_temporarily_hidden_in_editor(True)
            hidden.append(label)
    out["hidden_review_actors"] = sorted(hidden)
    lc_cfg = args["lights"]
    for label in lc_cfg.get("off", []):
        a = by_label(label)
        a.light_component.set_editor_property("intensity", 0.0)
        a.set_is_temporarily_hidden_in_editor(True)
    key = by_label(lc_cfg["key"]["label"])
    kc = key.light_component
    kc.set_editor_property("intensity", float(lc_cfg["key"]["intensity_lux"]))
    kc.set_editor_property("dynamic_shadow_distance_movable_light", float(lc_cfg["key"]["shadow_distance_uu"]))
    kc.set_editor_property("dynamic_shadow_cascades", int(lc_cfg["key"]["cascades"]))
    kc.set_editor_property("contact_shadow_length", float(lc_cfg["key"].get("contact_shadow_length", 0.0)))
    r = lc_cfg["key"]["rotation_pitch_yaw_roll"]
    key.set_actor_rotation(u.Rotator(roll=float(r[2]), pitch=float(r[0]), yaw=float(r[1])), False)
    out["key"] = {"label": lc_cfg["key"]["label"], "intensity": float(kc.get_editor_property("intensity")),
                  "rotation": [round(key.get_actor_rotation().pitch, 3), round(key.get_actor_rotation().yaw, 3)]}
    sky_cfg = args["sky"]
    sky = by_label(sky_cfg["label"], required=False)
    if sky is None:
        sky = actors_sub.spawn_actor_from_class(u.SkyLight, u.Vector(0, 0, 300), u.Rotator(0, 0, 0))
        sky.set_actor_label(sky_cfg["label"])
    sc = sky.light_component
    sc.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    sc.set_editor_property("source_type", u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    sc.set_editor_property("cubemap", load(sky_cfg["cubemap"]))
    sc.set_editor_property("intensity", float(sky_cfg["intensity"]))
    sc.set_editor_property("lower_hemisphere_is_black", bool(sky_cfg["lower_hemisphere_is_black"]))
    sc.set_editor_property("real_time_capture", False)
    sc.set_light_color(u.LinearColor(*[float(c) for c in sky_cfg["color_linear"]], 1.0))
    sc.recapture_sky()
    out["sky"] = {"label": sky_cfg["label"], "intensity": float(sc.get_editor_property("intensity"))}
    out["spheres"] = []
    for spec in args["spheres"]:
        spawn_sphere(spec, load(spec["material"]))
        out["spheres"].append(spec["label"])
    if args.get("probe"):
        pm, errs = build_probe(args["probe"]["local_unit_m"])
        out["probe_compile_errors"] = errs
        spawn_sphere(args["probe"], pm)
        out["spheres"].append(args["probe"]["label"])
    out["level"] = level
elif op == "exposure":
    # exposure bias of the fixed-exposure volume (in memory; the host reloads the level at the end)
    ppv = by_label(args["label"])
    st = ppv.get_editor_property("settings")
    st.set_editor_property("override_auto_exposure_bias", True)
    st.set_editor_property("auto_exposure_bias", float(args["bias"]))
    ppv.set_editor_property("settings", st)
    back = ppv.get_editor_property("settings")
    out["exposure"] = {"label": args["label"], "auto_exposure_bias": float(back.get_editor_property("auto_exposure_bias")),
                       "method": str(back.get_editor_property("auto_exposure_method")),
                       "min_brightness": float(back.get_editor_property("auto_exposure_min_brightness")),
                       "max_brightness": float(back.get_editor_property("auto_exposure_max_brightness"))}
elif op == "figure":
    old = by_label(args["label"], required=False)
    if old is not None:
        actors_sub.destroy_actor(old)
    a = actors_sub.spawn_actor_from_class(u.SkeletalMeshActor, vec(args["location"]),
                                          u.Rotator(roll=0.0, pitch=0.0, yaw=float(args["yaw"])))
    comp = a.skeletal_mesh_component
    comp.set_skinned_asset_and_update(load(args["asset"]))
    comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    for i in range(max(1, comp.get_num_materials())):
        comp.set_material(i, load(args["material"]))
    a.set_actor_label(args["label"])
    out["slots"] = int(comp.get_num_materials())
    out["figure"] = {"label": args["label"], "materials": [m.get_path_name().split(".")[0] for m in comp.get_materials() if m]}
elif op == "accent_probe":
    at = u.AssetToolsHelpers.get_asset_tools()
    if EAL.does_directory_exist(PROBE_DIR):
        EAL.delete_directory(PROBE_DIR)
    texs = {}
    for key, png in sorted(args["textures"].items()):
        task = u.AssetImportTask()
        task.set_editor_property("filename", png)
        task.set_editor_property("destination_path", PROBE_DIR)
        task.set_editor_property("destination_name", "T_Probe_" + key)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", False)
        at.import_asset_tasks([task])
        paths = list(task.get_editor_property("imported_object_paths"))
        if len(paths) != 1:
            raise RuntimeError("probe import of %s gave %r" % (png, paths))
        t = u.load_asset(paths[0])
        t.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_GRAYSCALE)
        t.set_editor_property("srgb", False)
        # all mips resident: a freshly imported streaming texture starts at a low mip and streams in while the
        # frames are taken (2026-09-30: blurred dye weight around the accents in the first probe frames)
        t.set_editor_property("never_stream", True)
        texs[key] = t
    out["textures"] = {k: [t.get_path_name(), t.blueprint_get_size_x(), t.blueprint_get_size_y()] for k, t in texs.items()}
    out["instances"] = {}
    for spec in args["instances"]:
        mi = at.create_asset(spec["name"], PROBE_DIR, u.MaterialInstanceConstant,
                             u.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, load(spec["parent"]))
        for k, v in (spec.get("scalars") or {}).items():
            MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
        for k, v in (spec.get("vectors") or {}).items():
            MEL.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(*[float(x) for x in v]))
        for k, v in (spec.get("textures") or {}).items():
            MEL.set_material_instance_texture_parameter_value(mi, k, texs[v[6:]] if v.startswith("probe:") else load(v))
        for k, v in (spec.get("switches") or {}).items():
            MEL.set_material_instance_static_switch_parameter_value(mi, k, bool(v))
        MEL.update_material_instance(mi)
        out["instances"][spec["name"]] = mi.get_path_name().split(".")[0]
elif op == "drop_probe":
    if EAL.does_directory_exist(PROBE_DIR):
        EAL.delete_directory(PROBE_DIR)
        out["deleted"] = PROBE_DIR
else:
    raise RuntimeError("unknown op %s" % op)
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
