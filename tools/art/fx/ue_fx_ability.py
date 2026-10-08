"""VS-6 F3 (visual chat, editor task): the death and ability FX assets of FX-26, FX-30 and FX-32.

Run by tools/art/fx/fx_ability.py (de010.run_editor, headless UnrealEditor-Cmd -ExecutePythonScript); the arguments come
from the JSON file in the env DE010_ARGS ({"out", "tokens", "grade", "vortex", "arc", "vortexObj"}). Idempotent: the
masters are rebuilt (expressions cleared), the MIs re-parented and re-written, the systems re-tuned in place.
See fx_ability.py for the asset list; the shader modes:
  0  FX-32 arc      camera quad of side QuadCells cells centred on the Weapon socket; the screen frame comes from the UV
                    derivatives (the F2 FigurePrint recipe), the cell pixel = PivotUV + rotate(s, ArcTilt) / cellPx;
                    frame = min(11, floor(ms x 30 / 1000)), gone at LifeMs (400; the component time dilation = 1 / speed)
  1  FX-30 vortex   SM_FX_VortexRings, the mesh UV (the upper ring U in [2, 3]: mirrored -> the rings turn against
                    each other); frame = min(15, floor(ms / 37.5)), gone at 600
  2  FX-26 embers   camera quad over the figure: H = side - margins; ember k < N = round(0.08 x DissolveMs) (<= 40) is
                    born at t_k = 12.5 k ms (once the front FrontHeight x DissolveMs has passed it) at the front height
                    t_k / DissolveMs x H on a 0.35 H cylinder (projected), rises 40..80 uu/s with a +-10 uu drift, spins
                    90..180 deg/s, shrinks 2..4 -> 1 uu (half diagonal), fades over the last 40 % of its life
                    (250..400 ms, never past the 600 ms of the system); a rhomb: body TeamScreenColor, edge accent.warm,
                    outer keyline mark.keyline
Colours = (R x Body + G x Edge + B x Keyline) / max(R+G+B, eps), opacity = A thresholded at 0.4 with the mip bias -1
(the FX-20 star recipe, ВР-VS6-15); no light, no glow, no noise.
"""
import json
import os
import zlib

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
REPORT = ARGS["out"]
TOK = ARGS["tokens"]
GRADE = ARGS["grade"]
EAL = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
TUNE = u.S08EnvFxAuthoringLibrary
AUTH = u.S08FxAuthoringLibrary
FX = "/Game/S08/FX"
MAT = FX + "/Materials"
COMBAT = FX + "/Combat"
TEXTURES = FX + "/Textures"
MESHES = FX + "/Meshes"
TEX_VORTEX = TEXTURES + "/T_FX_MedusaVortex_4x4"
TEX_ARC = TEXTURES + "/T_FX_ArthurArc_4x4"
MESH_VORTEX = MESHES + "/SM_FX_VortexRings"
DONOR = "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst"
PLANE = "/Engine/BasicShapes/Plane"
GRAPH_TAG = "S08AbilityFxGraphVersion"
GRAPH_VERSION = "1"

TONE_HLSL = r"""
const float3x3 S2A = float3x3(0.613097, 0.339523, 0.047379, 0.070194, 0.916354, 0.013452, 0.020616, 0.109570, 0.869815);
const float3x3 A2S = float3x3(1.704859, -0.621715, -0.083299, -0.130078, 1.140734, -0.010560, -0.023964, -0.128975, 1.153013);
const float3x3 FIX = float3x3(0.9100, 0.2545, -0.1580, 0.0266, 0.9584, 0.0321, 0.0036, -0.0773, 1.0647);
float3 tl = max(mul(S2A, saturate(mul(FIX, saturate(col)))), 0.0);
float3 y = min(pow(tl, GradePow.rgb), 0.98);
float3 qa = 2.51 - y * 2.43;
float3 qb = 0.03 - y * 0.59;
float3 qc = -y * 0.14;
float3 x = (-qb + sqrt(max(qb * qb - 4.0 * qa * qc, 0.0))) / (2.0 * qa);
return float4(max(mul(A2S, x / 0.6 * GradeScale.rgb), 0.0), saturate(a));
"""

ABILITY_HLSL = r"""
// VS-6 F3 M_FX_AbilityPrint(Depth). UV = the mesh texcoord, T = ParticleRelativeTime (0..1 of the lifetime), P = the
// camera-relative world position.
float ms = saturate(T) * LifeMs;
float3 col = ColorBody.rgb;
float a = 0.0;
// the camera quad's screen frame from the UV derivatives (the F2 FigurePrint recipe): s = px from the centre, y down;
// computed outside the branches (gradients in uniform control flow only)
float2 dx = ddx(UV);
float2 dy = ddy(UV);
float det = dx.x * dy.y - dx.y * dy.x;
det = abs(det) > 1e-12 ? det : 1e-12;
float2 d = UV - 0.5;
float2 s = float2((d.x * dy.y - d.y * dy.x) / det, (dx.x * d.y - dx.y * d.x) / det);
float sizePx = 1.0 / sqrt(abs(det));
float uupp = max(length(ddx(P)), 1e-4);
if (Mode > 0.5 && Mode < 1.5) {
  // ---- FX-30 vortex: the mesh UV; the upper ring (U in [2, 3]) mirrored
  float2 uv = UV;
  if (uv.x > 1.5) uv.x = 3.0 - uv.x;
  uv = clamp(uv, 0.5 / 256.0, 1.0 - 0.5 / 256.0);
  float f = min(15.0, floor(ms / 37.5));
  float2 cell = float2(fmod(f, 4.0), floor(f / 4.0));
  float4 m = Texture2DSampleBias(Mask, MaskSampler, (uv + cell) / 4.0, -1.0);
  float w = max(m.r + m.g + m.b, 1e-4);
  col = (m.r * ColorBody.rgb + m.g * ColorEdge.rgb + m.b * ColorKeyline.rgb) / w;
  float aw = fwidth(m.a) + 1e-4;
  a = smoothstep(0.4 - aw, 0.4 + aw, m.a) * step(ms, LifeMs - 0.01) * saturate(Opacity);
} else {
  if (Mode < 0.5) {
    // ---- FX-32 arc: the cell pivot on the hand, tilted with the blade (deg, clockwise)
    float th = radians(ArcTilt);
    float c = cos(th);
    float sn = sin(th);
    float2 sr = float2(c * s.x + sn * s.y, -sn * s.x + c * s.y);
    float cellPx = sizePx / max(QuadCells, 1.0);
    float2 st = float2(PivotU, PivotV) + sr / cellPx;
    float inside = step(0.0, st.x) * step(st.x, 1.0) * step(0.0, st.y) * step(st.y, 1.0) * step(ms, LifeMs - 0.01);
    st = clamp(st, 0.5 / 256.0, 1.0 - 0.5 / 256.0);
    float f = min(11.0, floor(ms * 0.03));
    float2 cell = float2(fmod(f, 4.0), floor(f / 4.0));
    float4 m = Texture2DSampleBias(Mask, MaskSampler, (st + cell) / 4.0, -1.0);
    float w = max(m.r + m.g + m.b, 1e-4);
    col = (m.r * ColorBody.rgb + m.g * ColorEdge.rgb + m.b * ColorKeyline.rgb) / w;
    float aw = fwidth(m.a) + 1e-4;
    a = smoothstep(0.4 - aw, 0.4 + aw, m.a) * inside * saturate(Opacity);
  } else {
    // ---- FX-26 embers
    float2 q = s * uupp;                              // uu in the quad plane, y down
    float side = sizePx * uupp;
    float H = max(side - MarginTopUU - MarginBaseUU, 10.0);
    float baseY = 0.5 * side - MarginBaseUU;          // the base point (y down)
    float D = max(DissolveMs, 1.0);
    float N = min(40.0, floor(D * 0.08 + 0.5));
    float R = 0.35 * H;
    float aa = max(fwidth(q.x) + fwidth(q.y), 0.05);
    float bestA = 0.0;
    float bestBand = 0.0;
    for (int k = 0; k < 40; ++k) {
      float fk = (float)k;
      if (fk >= N) break;
      float tk = fk * 12.5;
      if (tk > saturate(FrontHeight) * D + 1.0) continue;   // the front has not reached this ember yet
      float h1 = frac(sin(fk * 12.9898 + 1.0) * 43758.5453);
      float h2 = frac(sin(fk * 78.233 + 2.0) * 43758.5453);
      float h3 = frac(sin(fk * 39.346 + 3.0) * 43758.5453);
      float h4 = frac(sin(fk * 11.135 + 4.0) * 43758.5453);
      float h5 = frac(sin(fk * 53.719 + 5.0) * 43758.5453);
      float h6 = frac(sin(fk * 27.551 + 6.0) * 43758.5453);
      float life = clamp(250.0 + 150.0 * h1, 100.0, LifeMs - tk);
      float age = ms - tk;
      if (age < 0.0 || age > life) continue;
      float x01 = age / life;
      float ex = R * cos(6.2831853 * h2) + 10.0 * (2.0 * h3 - 1.0) * x01;
      float ey = (tk / D) * H + (40.0 + 40.0 * h4) * age / 1000.0;
      float size = lerp(2.0 + 2.0 * h5, 1.0, x01);      // the half diagonal, uu
      float ang = radians((90.0 + 90.0 * h6) * (h6 > 0.5 ? 1.0 : -1.0) * age / 1000.0);
      float2 p = q - float2(ex, baseY - ey);
      float ca = cos(ang);
      float sa = sin(ang);
      p = float2(ca * p.x - sa * p.y, sa * p.x + ca * p.y);
      float dd = abs(p.x) + abs(p.y);                   // the rhomb (L1) distance
      float key = saturate((size - dd) / aa + 0.5);
      if (key <= 0.0) continue;
      float band = dd < 0.6 * size ? 2.0 : (dd < 0.8 * size ? 1.0 : 0.0);  // body 60 %: the team colour reads
      float fade = x01 < 0.6 ? 1.0 : 1.0 - (x01 - 0.6) / 0.4;
      float ea = key * fade;
      if (ea > bestA) {
        bestA = ea;
        bestBand = band;
      }
    }
    col = bestBand > 1.5 ? TeamScreenColor.rgb : (bestBand > 0.5 ? ColorEdge.rgb : ColorKeyline.rgb);
    a = bestA * saturate(Opacity);
  }
}
""" + TONE_HLSL


def obj(path):
    return path + "." + path.rsplit("/", 1)[-1]


def load(path):
    a = u.load_asset(obj(path))
    if a is None:
        raise RuntimeError("asset not found: %s" % path)
    return a


def expr(m, cls, x, y):
    n = MEL.create_material_expression(m, cls, x, y)
    if n is None:
        raise RuntimeError("could not create %s" % cls)
    return n


def link(src, out, dst, inp):
    if not MEL.connect_material_expressions(src, out, dst, inp):
        raise RuntimeError("connect %s.%s -> %s.%s failed" % (src.get_name(), out, dst.get_name(), inp))


def try_set(o, name, value):
    try:
        o.set_editor_property(name, value)
        return True
    except Exception:  # noqa: BLE001
        return False


def stats(m):
    st = MEL.get_statistics(m)
    res = {}
    for k in ("num_vertex_shader_instructions", "num_pixel_shader_instructions", "num_samplers"):
        try:
            res[k] = int(st.get_editor_property(k))
        except Exception as exc:  # noqa: BLE001
            res[k] = "ERR %s" % exc
    return res


def ensure_dir(path):
    if not EAL.does_directory_exist(path):
        EAL.make_directory(path)


SCALARS = {"Mode": 0.0, "LifeMs": 400.0, "Opacity": 1.0, "ArcTilt": 0.0, "PivotU": 147.2 / 256.0,
           "PivotV": 164.0 / 256.0, "QuadCells": 1.75, "FrontHeight": 0.0, "DissolveMs": 500.0, "MarginTopUU": 44.0,
           "MarginBaseUU": 6.0}
VECTORS = {"ColorBody": TOK["fx.gold"], "ColorEdge": TOK["card.glyph"], "ColorKeyline": TOK["mark.keyline"],
           "TeamScreenColor": TOK["team.p1.screen"], "GradeScale": GRADE["GradeScale"], "GradePow": GRADE["GradePow"]}


def master(path, depth_test):
    folder, name = path.rsplit("/", 1)
    m = u.load_asset(obj(path)) if EAL.does_asset_exist(path) else None
    action = "rebuilt" if m else "created"
    if m is None:
        m = AT.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    MEL.delete_all_material_expressions(m)
    m.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    m.set_editor_property("disable_depth_test", not depth_test)
    settings = {"fogOff": try_set(m, "use_translucency_vertex_fog", False), "depthTest": depth_test}
    try_set(m, "used_with_niagara_mesh_particles", True)
    MEL.set_material_usage(m, u.MaterialUsage.MATUSAGE_NIAGARA_MESH_PARTICLES)
    settings["used_with_niagara_mesh_particles"] = bool(m.get_editor_property("used_with_niagara_mesh_particles"))
    custom = expr(m, u.MaterialExpressionCustom, -500, 0)
    custom.set_editor_property("description", name)
    custom.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT4)
    pins = []
    for n in ["UV", "T", "P", "Mask"] + list(SCALARS) + list(VECTORS):
        ci = u.CustomInput()
        ci.set_editor_property("input_name", n)
        pins.append(ci)
    custom.set_editor_property("inputs", pins)
    custom.set_editor_property("code", ABILITY_HLSL)
    uv = expr(m, u.MaterialExpressionTextureCoordinate, -1500, -260)
    link(uv, "", custom, "UV")
    t = expr(m, u.MaterialExpressionParticleRelativeTime, -1500, -160)
    link(t, "", custom, "T")
    wp = expr(m, u.MaterialExpressionWorldPosition, -1500, -60)
    offs = getattr(u, "WorldPositionIncludedOffsets", None)
    rel = None
    if offs is not None:
        for nm in ("WPT_CAMERA_RELATIVE", "WPT_CameraRelative"):
            if hasattr(offs, nm):
                rel = try_set(wp, "world_position_shader_offset", getattr(offs, nm))
                if rel:
                    break
    if not rel:
        raise RuntimeError("camera-relative world position not available")
    link(wp, "", custom, "P")
    tex = expr(m, u.MaterialExpressionTextureObjectParameter, -1500, 60)
    tex.set_editor_property("parameter_name", "Mask")
    tex.set_editor_property("texture", load(TEX_ARC))
    tex.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_MASKS)
    link(tex, "", custom, "Mask")
    y = 200
    for n, v in SCALARS.items():
        p = expr(m, u.MaterialExpressionScalarParameter, -1100, y)
        p.set_editor_property("parameter_name", n)
        p.set_editor_property("default_value", float(v))
        link(p, "", custom, n)
        y += 70
    for n, v in VECTORS.items():
        p = expr(m, u.MaterialExpressionVectorParameter, -1100, y)
        p.set_editor_property("parameter_name", n)
        p.set_editor_property("default_value", u.LinearColor(*[float(c) for c in v[:3]], float(v[3]) if len(v) > 3 else 1.0))
        link(p, "", custom, n)
        y += 90
    rgb = expr(m, u.MaterialExpressionComponentMask, -250, -60)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        rgb.set_editor_property(ch, on)
    link(custom, "", rgb, "")
    alpha = expr(m, u.MaterialExpressionComponentMask, -250, 80)
    for ch, on in (("r", False), ("g", False), ("b", False), ("a", True)):
        alpha.set_editor_property(ch, on)
    link(custom, "", alpha, "")
    MEL.connect_material_property(rgb, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(alpha, "", u.MaterialProperty.MP_OPACITY)
    MEL.layout_material_expressions(m)
    errors = MEL.recompile_material(m)
    EAL.set_metadata_tag(m, GRAPH_TAG, GRAPH_VERSION)
    if not EAL.save_loaded_asset(m, False):
        raise RuntimeError("could not save %s" % path)
    return m, {"action": action, "settings": settings, "expressions": int(MEL.get_num_material_expressions(m)),
               "compileErrors": [str(e) for e in (errors or [])], "statistics": stats(m)}


def mi(path, parent, scalars, vectors, texture=None):
    folder, name = path.rsplit("/", 1)
    inst = u.load_asset(obj(path)) if EAL.does_asset_exist(path) else None
    if inst is None:
        inst = AT.create_asset(name, folder, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    MEL.set_material_instance_parent(inst, parent)
    MEL.clear_all_material_instance_parameters(inst)
    for n, v in scalars.items():
        MEL.set_material_instance_scalar_parameter_value(inst, n, float(v))
    for n, v in vectors.items():
        MEL.set_material_instance_vector_parameter_value(inst, n, u.LinearColor(*[float(c) for c in v[:3]],
                                                                                   float(v[3]) if len(v) > 3 else 1.0))
    if texture:
        MEL.set_material_instance_texture_parameter_value(inst, "Mask", load(texture))
    MEL.update_material_instance(inst)
    if not EAL.save_loaded_asset(inst, False):
        raise RuntimeError("could not save %s" % path)
    return {"parent": parent.get_path_name(), "scalars": scalars, "texture": texture, "statistics": stats(inst)}


def import_mask(spec, dest):
    ensure_dir(TEXTURES)
    task = u.AssetImportTask()
    task.filename = spec["png"]
    task.destination_path = dest.rsplit("/", 1)[0]
    task.destination_name = dest.rsplit("/", 1)[-1]
    task.automated = True
    task.replace_existing = True
    task.save = False
    AT.import_asset_tasks([task])
    tex = load(dest)
    tex.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_BC7)
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("lod_group", u.TextureGroup.TEXTUREGROUP_EFFECTS)
    tex.set_editor_property("mip_gen_settings", u.TextureMipGenSettings.TMGS_SIMPLE_AVERAGE)
    tex.set_editor_property("address_x", u.TextureAddress.TA_CLAMP)
    tex.set_editor_property("address_y", u.TextureAddress.TA_CLAMP)
    tex.set_editor_property("lod_bias", 0)
    tex.set_editor_property("never_stream", True)
    if not EAL.save_loaded_asset(tex, False):
        raise RuntimeError("could not save %s" % dest)
    return {"asset": dest, "sha256": spec["sha256"], "size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()],
            "compression": str(tex.get_editor_property("compression_settings")),
            "srgb": bool(tex.get_editor_property("srgb"))}


def import_mesh(obj_path):
    ensure_dir(MESHES)
    task = u.AssetImportTask()
    task.filename = obj_path
    task.destination_path = MESHES
    task.destination_name = MESH_VORTEX.rsplit("/", 1)[-1]
    task.automated = True
    task.replace_existing = True
    task.save = False
    AT.import_asset_tasks([task])
    imported = [str(p) for p in (task.get_editor_property("imported_object_paths") or [])]
    mesh = u.load_asset(obj(MESH_VORTEX))
    if mesh is None:
        # Interchange may name the mesh after the OBJ object - take the static mesh it imported
        for p in imported:
            a = u.load_asset(p)
            if isinstance(a, u.StaticMesh):
                mesh = a
                break
    if mesh is None:
        raise RuntimeError("vortex mesh not imported: %s" % imported)
    box = mesh.get_bounding_box()
    # a stray material the importer may create next to the mesh is not used (the Niagara override material draws)
    for p in imported:
        a = u.load_asset(p)
        if a is not None and not isinstance(a, u.StaticMesh) and EAL.does_asset_exist(p.rsplit(".", 1)[0]):
            EAL.delete_asset(p.rsplit(".", 1)[0])
    if not EAL.save_loaded_asset(mesh, False):
        raise RuntimeError("could not save the vortex mesh")
    return {"asset": mesh.get_path_name(), "imported": imported,
            "min": [box.min.x, box.min.y, box.min.z], "max": [box.max.x, box.max.y, box.max.z],
            "triangles": mesh.get_num_triangles(0) if hasattr(mesh, "get_num_triangles") else None}


def crc_seed(name):
    return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF


def system(name, lifetime, mesh, material, user, bounds=200.0):
    path = COMBAT + "/" + name
    ensure_dir(COMBAT)
    action = "retuned"
    if EAL.does_asset_exist(path):
        dup = load(path)
    else:
        dup = AT.duplicate_asset(name, COMBAT, load(DONOR))
        action = "duplicated"
    if dup is None:
        raise RuntimeError("duplicate %s failed" % name)
    seed = crc_seed(name)
    dup.modify()
    dup.set_editor_property("determinism", True)
    dup.set_editor_property("random_seed", seed)
    dup.set_editor_property("warmup_time", 0.0)
    dup.set_editor_property("effect_type", load(FX + "/EffectTypes/NET_UM_Combat"))
    for n in ("pool_prime_size", "PoolPrimeSize"):
        if try_set(dup, n, 3):
            break
    EAL.save_loaded_asset(dup, False)
    spec = {
        "simTarget": "cpu", "emitterDeterminism": True, "emitterSeedBase": seed,
        "emitters": {"LocationBasedRibbon": {"enabled": False}},
        "constants": [
            {"match": "*SpawnBurst_Instantaneous.Spawn Count", "set": 1},
            {"match": "*SpawnBurst_Instantaneous.Spawn Time", "set": 0},
            {"match": "*InitializeParticle.Lifetime Min", "set": lifetime},
            {"match": "*InitializeParticle.Lifetime Max", "set": lifetime},
            {"match": "*ScaleSpriteSizeBySpeed.Min Scale Factor", "set": [1.0, 1.0]},
            {"match": "*ScaleSpriteSizeBySpeed.Max Scale Factor", "set": [1.0, 1.0]},
            {"match": "*RandomRangeFloat002.Minimum", "set": 0.0},
            {"match": "*RandomRangeFloat002.Maximum", "set": 0.0},
            {"match": "*GravityForce.Gravity", "set": [0.0, 0.0, 0.0]},
            {"match": "*EmitterState.MaxDistance", "set": 1000000.0},
            {"match": "*EmitterState.Loop Duration", "set": max(lifetime, 1.0)},
        ],
    }
    tune = json.loads(TUNE.tune_niagara_system(path, json.dumps(spec)))
    carrier = json.loads(AUTH.make_board_quad_carrier(path, "DirectionalBurst", mesh, material))
    if not carrier.get("ok"):
        raise RuntimeError("quad carrier %s: %s" % (name, carrier))
    bind = json.loads(AUTH.bind_user_material_parameters(path, "DirectionalBurst", json.dumps(user))) if user else None
    if user and not bind.get("ok"):
        raise RuntimeError("bind %s: %s" % (name, bind))
    fixed = json.loads(AUTH.set_system_fixed_bounds(path, bounds))
    EAL.save_loaded_asset(load(path), False)
    describe = json.loads(TUNE.describe_niagara_system(path)).get("describe", {})
    return {"path": path, "action": action, "seed": seed, "lifetime": lifetime, "tune": tune, "carrier": carrier,
            "bind": bind, "bounds": fixed, "emitters": describe.get("emitters"), "user": describe.get("user")}


out = {"errors": []}
try:
    out["textures"] = {"vortex": import_mask(ARGS["vortex"], TEX_VORTEX), "arc": import_mask(ARGS["arc"], TEX_ARC)}
    out["mesh"] = import_mesh(ARGS["vortexObj"])
    nodepth, info_n = master(MAT + "/M_FX_AbilityPrint", depth_test=False)
    depth, info_d = master(MAT + "/M_FX_AbilityPrintDepth", depth_test=True)
    out["masters"] = {"nodepth": info_n, "depth": info_d}
    grade = {"GradeScale": GRADE["GradeScale"], "GradePow": GRADE["GradePow"]}
    out["mi"] = {
        "MI_FX_Arc": mi(MAT + "/MI_FX_Arc", nodepth,
                        {"Mode": 0.0, "LifeMs": 400.0, "PivotU": 147.2 / 256.0, "PivotV": 164.0 / 256.0,
                         "QuadCells": 1.75},
                        dict(grade, ColorBody=TOK["fx.gold"], ColorEdge=TOK["card.glyph"], ColorKeyline=TOK["mark.keyline"]),
                        TEX_ARC),
        "MI_FX_Vortex": mi(MAT + "/MI_FX_Vortex", depth, {"Mode": 1.0, "LifeMs": 600.0},
                           dict(grade, ColorBody=TOK["fx.stone.2"], ColorEdge=TOK["fx.stone"],
                                ColorKeyline=TOK["mark.keyline"]), TEX_VORTEX),
        "MI_FX_Ember": mi(MAT + "/MI_FX_Ember", depth,
                          {"Mode": 2.0, "LifeMs": 600.0, "DissolveMs": 500.0, "MarginTopUU": 44.0, "MarginBaseUU": 6.0},
                          dict(grade, ColorBody=TOK["team.p1.screen"], ColorEdge=TOK["accent.warm"],
                               ColorKeyline=TOK["mark.keyline"], TeamScreenColor=TOK["team.p1.screen"])),
    }
    out["systems"] = {
        "NS_FX_ArthurArc": system("NS_FX_ArthurArc", 0.4, PLANE, MAT + "/MI_FX_Arc",
                                  [{"name": "ArcTilt", "type": "float", "default": 0.0}]),
        "NS_FX_MedusaVortex": system("NS_FX_MedusaVortex", 0.6, out["mesh"]["asset"].rsplit(".", 1)[0],
                                     MAT + "/MI_FX_Vortex", None),
        "NS_FX_AshEmbers": system("NS_FX_AshEmbers", 0.6, PLANE, MAT + "/MI_FX_Ember",
                                  [{"name": "FrontHeight", "type": "float", "default": 0.0},
                                   {"name": "DissolveMs", "type": "float", "default": 500.0},
                                   {"name": "TeamScreenColor", "type": "color", "default": TOK["team.p1.screen"]}]),
    }
    out["ok"] = not info_n["compileErrors"] and not info_d["compileErrors"]
except Exception:  # noqa: BLE001
    import traceback
    out["ok"] = False
    out["error"] = traceback.format_exc()
with open(REPORT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
