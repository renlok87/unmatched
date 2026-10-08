"""VS-6 F2 (visual chat, editor task): the figure FX assets of FX-21, FX-24 and the Z-2 leftovers of FX-05 / FX-19.

Run by tools/art/fx/fx_figure.py (de010.run_editor, headless UnrealEditor-Cmd -ExecutePythonScript); the arguments come
from the JSON file in the env DE010_ARGS ({"out", "tokens", "grade", "fxGrade", "hitstar": {png, asset}}). Idempotent:
the masters are rebuilt (expressions cleared), the MIs re-parented and re-written, the systems re-tuned in place.

1. /Game/S08/FX/Textures/T_FX_HitStar_4x2 - the accepted FX-20 mask (R body / G inner edge / B keyline / A = max,
   straight alpha), BC7, sRGB off, TEXTUREGROUP_Effects, mips ON, clamp, no LOD bias (FX-21, ВР-VS2-FX20-06).
2. /Game/S08/FX/Materials/M_FX_FigurePrint - the print master of the figure FX quads (unlit, translucent, NO depth test,
   used with Niagara mesh particles, the inverse tone curve of M_FX_Print with the profile grade baked): the quad faces
   the camera (C++), the shader rebuilds the screen frame of the quad from the UV derivatives so the star's long ray is
   screen-up whatever the plane's UV layout; mode 0 the FX-20 flipbook - frame = min(7, floor(age_ms x 30 / 1000)) from
   ParticleRelativeTime (the template has no SubUV module and none can be added from script, ВР-VS6-13); mode 1 the
   FX-24 heal motes (SDF discs, fx.heal body, mark.keyline edge) rising from the base by the card's keyframes.
   MI_FX_HitStar (fx.impact / fx.rim / mark.keyline) and MI_FX_Heal (fx.heal / mark.keyline) are re-parented from
   M_FX_Print / M_FX_Print_Overlay onto it (fx_import.py no longer owns them).
3. /Game/S08/FX/Combat/NS_FX_HitStar (0.27 s) and NS_FX_HealMotes (0.6 s) - the NS_FX_Dust recipe of F1 (ВР-VS6-06):
   a duplicate of the engine template DirectionalBurst, one still particle, CPU, deterministic, RandomSeed = CRC32 of the
   name (FX-04), fixed bounds, NET_UM_Combat, pool prime 3, a local-space mesh renderer of the engine plane (the
   component's transform places, turns to the camera and sizes the quad).
4. /Game/S08/FX/Materials/M_FX_FigureCue - the figure cue OVERLAY (ВР-VS6-14, the Z-2 leftovers): the overlay material
   of the v2 figure's skeletal mesh (translucent, unlit, depth test on) draws the white flash (FX-19) and the cream rim as
   a DEPTH CONTOUR: a pixel of the figure is rim when a scene-depth sample RimPx away lies RimDepthUU or more behind it
   (the background or a part far behind) - inner folds no longer catch it (the fresnel of N.V did). It reads its own
   custom primitive data 15 / 16 / 17 (flash a, rim intensity, rim width), so the opaque master M_UM_Figure_v2 is not
   rebuilt (the AN-32 Fix group stays untouched; its CPD 5-10 path is the rollback -S08FigureCueLegacy). A translucent
   overlay is not in the Lumen scene - the field around the flash no longer receives the figure's emissive.
"""
import json
import os
import zlib

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
REPORT = ARGS["out"]
TOK = ARGS["tokens"]          # token -> [r, g, b, 1] linear
GRADE = ARGS["grade"]         # {"GradeScale": [..4], "GradePow": [..4]}
EAL = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
TUNE = u.S08EnvFxAuthoringLibrary
AUTH = u.S08FxAuthoringLibrary
FX = "/Game/S08/FX"
MAT = FX + "/Materials"
COMBAT = FX + "/Combat"
TEX = FX + "/Textures/T_FX_HitStar_4x2"
DONOR = "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst"
PLANE = "/Engine/BasicShapes/Plane"
GRAPH_TAG = "S08FigureFxGraphVersion"
GRAPH_VERSION = "2"

# the inverse tone curve of M_FX_Print (FX-02, ВР-Z2R-09 / ВР-Z2R-12): a token shows as its hex
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

FIGURE_HLSL = r"""
// VS-6 F2 M_FX_FigurePrint. UV = the plane's texcoord, T = ParticleRelativeTime (0..1 of the lifetime), P = the
// camera-relative world position. The quad faces the camera (C++): its screen frame comes from the UV derivatives -
// s = the pixel's offset from the quad centre in screen px (y down), whatever the plane's UV orientation.
float2 dx = ddx(UV);
float2 dy = ddy(UV);
float det = dx.x * dy.y - dx.y * dy.x;
det = abs(det) > 1e-12 ? det : 1e-12;
float2 d = UV - 0.5;
float2 s = float2((d.x * dy.y - d.y * dy.x) / det, (dx.x * d.y - dx.y * d.x) / det);
float sizePx = 1.0 / sqrt(abs(det));                 // the square quad's side in px
float uupp = max(length(ddx(P)), 1e-4);              // world uu per screen px on the quad
float3 col = ColorBody.rgb;
float a = 0.0;
if (Mode < 0.5) {
  // FX-21: the FX-20 flipbook 4 x 2, frame = min(7, floor(t_ms x 30 / 1000)), hidden from LifeMs (the particle dies)
  float ms = saturate(T) * LifeMs;
  float f = min(7.0, floor(ms * 0.03));
  float2 st = clamp(0.5 + s / sizePx, 0.5 / 256.0, 1.0 - 0.5 / 256.0);
  float inside = step(abs(s.x), 0.5 * sizePx) * step(abs(s.y), 0.5 * sizePx) * step(ms, LifeMs - 0.01);
  float2 cell = float2(fmod(f, 4.0), floor(f / 4.0));
  // one mip sharper than the screen footprint and the coverage threshold at 0.4: the 8 px outer keyline of the cell
  // (1.5..2 px at K1) survives the minification (the first K1 check frames lost it at bias 0 / threshold 0.5)
  float4 m = Texture2DSampleBias(Mask, MaskSampler, (st + cell) / float2(4.0, 2.0), -1.0);
  float w = max(m.r + m.g + m.b, 1e-4);
  col = (m.r * ColorBody.rgb + m.g * ColorEdge.rgb + m.b * ColorKeyline.rgb) / w;
  float aw = fwidth(m.a) + 1e-4;
  a = smoothstep(0.4 - aw, 0.4 + aw, m.a) * inside * saturate(Opacity);
} else {
  // FX-24: MoteCount discs (fx.heal body, mark.keyline edge) from the base ring (0.6 x BaseRadiusUU), launched at
  // 0 / 60 / 120 / 180 ms, rising 0.8 x the figure height (the quad: side = 0.8 H + 16, base 6 uu above its bottom
  // edge) with an ease-out to 450 ms and a +-6 uu sway; 300..600 ms opacity -> 0 and radius 3 -> 2 uu
  float2 q = s * uupp;                                // uu in the quad plane, y down
  float side = sizePx * uupp;
  float baseY = 0.5 * side - 6.0;                     // the base point (y down)
  float rise = max(side - 16.0, 8.0);                 // 0.8 x the figure height
  float ms = saturate(T) * LifeMs;
  float fade = 1.0 - saturate((ms - 300.0) / 300.0);
  float rad = ms < 300.0 ? 3.0 : lerp(3.0, 2.0, saturate((ms - 300.0) / 300.0));
  float aa = max(fwidth(length(q)), 0.05);
  float best = 0.0;
  float cover = 0.0;
  for (int k = 0; k < 5; ++k) {
    if (k >= (int)MoteCount) break;
    float st0 = 60.0 * k;
    if (ms < st0) continue;
    float e = saturate((ms - st0) / max(450.0 - st0, 1.0));
    e = 1.0 - (1.0 - e) * (1.0 - e);
    float ang = 6.2831853 * (k / MoteCount) + 0.6;
    float2 c0 = float2(0.6 * BaseRadiusUU * cos(ang), baseY - 2.0 - 0.3 * BaseRadiusUU * sin(ang));
    float sway = 6.0 * sin(2.4 * e + 1.7 * k) * e;
    float2 c = c0 + float2(sway, -rise * e);
    float dd = length(q - c);
    float body = saturate((rad - dd) / aa + 0.5);
    float key = saturate((rad + KeylineUU - dd) / aa + 0.5);
    float band = body > 0.5 ? 2.0 : (key > 0.5 ? 1.0 : 0.0);
    best = max(best, band);
    cover = max(cover, key);
  }
  col = best > 1.5 ? ColorBody.rgb : ColorKeyline.rgb;
  a = cover * fade * saturate(Opacity);
}
""" + TONE_HLSL

CUE_HLSL = r"""
// VS-6 F2 M_FX_FigureCue (overlay of the v2 figure, ВР-VS6-14): F = flash a (CPD 15), I = rim intensity (CPD 16),
// W = rim width (CPD 17). The rim is a depth contour: this pixel of the figure is rim when a scene-depth sample r px away
// lies RimDepthUU or more behind it (16 directions at r and r / 2) - the silhouette and the parts far in front of
// others, never the folds of one surface. The intensity narrows the band (ВР-Z2R-08); below 0.25 it fades out.
float pd = PD;
float scale = VS.y / 1080.0;
float r = lerp(RimNarrowPx, RimWidePx, saturate(W)) * lerp(0.5, 1.0, saturate(I)) * scale;
float edge = 0.0;
if (I > 0.001) {
  for (int k = 0; k < 8; ++k) {
    float ang = 0.785398 * k;
    float2 dir = float2(cos(ang), sin(ang));
    for (int j = 1; j <= 2; ++j) {
      float2 o = dir * r * (j * 0.5) / VS;
      float sd = CalcSceneDepth(ViewportUVToBufferUV(saturate(SP + o)));
      edge = max(edge, saturate((sd - pd - RimDepthUU) / RimDepthUU));
    }
  }
}
float rimA = edge * saturate(I * 4.0);
float flashA = saturate(F) * FlashCover;
float3 col = flashA > 0.0 ? FlashColor.rgb * FlashGain : RimColor.rgb;
float a = max(flashA, rimA);
const float3x3 S2A = float3x3(0.613097, 0.339523, 0.047379, 0.070194, 0.916354, 0.013452, 0.020616, 0.109570, 0.869815);
const float3x3 A2S = float3x3(1.704859, -0.621715, -0.083299, -0.130078, 1.140734, -0.010560, -0.023964, -0.128975, 1.153013);
float3 tl = max(mul(S2A, saturate(col)), 0.0);
float3 y = min(pow(tl, GradePow.rgb), 0.98);
float3 qa = 2.51 - y * 2.43;
float3 qb = 0.03 - y * 0.59;
float3 qc = -y * 0.14;
float3 x = (-qb + sqrt(max(qb * qb - 4.0 * qa * qc, 0.0))) / (2.0 * qa);
return float4(max(mul(A2S, x / 0.6 * GradeScale.rgb), 0.0), saturate(a));
"""


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


def master(path, inputs, code, scalars, vectors, wire, niagara=False, skeletal=False, depth_test=True,
           two_sided=True):
    folder, name = path.rsplit("/", 1)
    m = u.load_asset(obj(path)) if EAL.does_asset_exist(path) else None
    action = "rebuilt" if m else "created"
    if m is None:
        m = AT.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    MEL.delete_all_material_expressions(m)
    m.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", two_sided)
    m.set_editor_property("disable_depth_test", not depth_test)
    settings = {"fogOff": try_set(m, "use_translucency_vertex_fog", False), "depthTest": depth_test}
    # the usage flags as properties (set_material_usage answers "needs a recompile", not the flag); read back below
    if niagara:
        try_set(m, "used_with_niagara_mesh_particles", True)
        MEL.set_material_usage(m, u.MaterialUsage.MATUSAGE_NIAGARA_MESH_PARTICLES)
    if skeletal:
        try_set(m, "used_with_skeletal_mesh", True)
        MEL.set_material_usage(m, u.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    for flag in ("used_with_niagara_mesh_particles", "used_with_skeletal_mesh"):
        try:
            settings[flag] = bool(m.get_editor_property(flag))
        except Exception:  # noqa: BLE001
            settings[flag] = "n/a"
    custom = expr(m, u.MaterialExpressionCustom, -500, 0)
    custom.set_editor_property("description", name)
    custom.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT4)
    pins = []
    for n in inputs:
        ci = u.CustomInput()
        ci.set_editor_property("input_name", n)
        pins.append(ci)
    custom.set_editor_property("inputs", pins)
    custom.set_editor_property("code", code)
    wire(m, custom)
    y = 200
    for n, v in scalars.items():
        p = expr(m, u.MaterialExpressionScalarParameter, -1100, y)
        if isinstance(v, dict):  # {"cpd": index, "default": value}
            p.set_editor_property("parameter_name", n)
            p.set_editor_property("default_value", float(v["default"]))
            p.set_editor_property("use_custom_primitive_data", True)
            p.set_editor_property("primitive_data_index", int(v["cpd"]))
        else:
            p.set_editor_property("parameter_name", n)
            p.set_editor_property("default_value", float(v))
        link(p, "", custom, n)
        y += 70
    for n, v in vectors.items():
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


def wire_figure(m, custom):
    uv = expr(m, u.MaterialExpressionTextureCoordinate, -1500, -260)
    link(uv, "", custom, "UV")
    t = expr(m, u.MaterialExpressionParticleRelativeTime, -1500, -160)
    link(t, "", custom, "T")
    wp = expr(m, u.MaterialExpressionWorldPosition, -1500, -60)
    offs = getattr(u, "WorldPositionIncludedOffsets", None)
    rel = None
    if offs is not None:
        for name in ("WPT_CAMERA_RELATIVE", "WPT_CameraRelative"):
            if hasattr(offs, name):
                rel = try_set(wp, "world_position_shader_offset", getattr(offs, name))
                if rel:
                    break
    if not rel:
        raise RuntimeError("camera-relative world position not available")
    link(wp, "", custom, "P")
    tex = expr(m, u.MaterialExpressionTextureObjectParameter, -1500, 60)
    tex.set_editor_property("parameter_name", "Mask")
    tex.set_editor_property("texture", load(TEX))
    tex.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_MASKS)
    link(tex, "", custom, "Mask")


def wire_cue(m, custom):
    sp = expr(m, u.MaterialExpressionScreenPosition, -1500, -260)
    link(sp, "ViewportUV", custom, "SP")
    pd = expr(m, u.MaterialExpressionPixelDepth, -1500, -160)
    link(pd, "", custom, "PD")
    vs = expr(m, u.MaterialExpressionViewSize, -1500, -60)
    link(vs, "", custom, "VS")
    # the scene depth node binds the depth texture for CalcSceneDepth (its value itself is not read)
    sd = expr(m, u.MaterialExpressionSceneDepth, -1500, 40)
    link(sd, "", custom, "SD")


def mi(path, parent, scalars, vectors):
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
    MEL.update_material_instance(inst)
    if not EAL.save_loaded_asset(inst, False):
        raise RuntimeError("could not save %s" % path)
    return {"parent": parent.get_path_name(), "scalars": scalars, "vectors": vectors, "statistics": stats(inst)}


def crc_seed(name):
    return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF


def import_hitstar(spec):
    task = u.AssetImportTask()
    task.filename = spec["png"]
    task.destination_path = TEX.rsplit("/", 1)[0]
    task.destination_name = TEX.rsplit("/", 1)[-1]
    task.automated = True
    task.replace_existing = True
    task.save = False
    AT.import_asset_tasks([task])
    tex = load(TEX)
    tex.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_BC7)
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("lod_group", u.TextureGroup.TEXTUREGROUP_EFFECTS)
    tex.set_editor_property("mip_gen_settings", u.TextureMipGenSettings.TMGS_SIMPLE_AVERAGE)
    tex.set_editor_property("address_x", u.TextureAddress.TA_CLAMP)
    tex.set_editor_property("address_y", u.TextureAddress.TA_CLAMP)
    tex.set_editor_property("lod_bias", 0)
    tex.set_editor_property("never_stream", True)
    if not EAL.save_loaded_asset(tex, False):
        raise RuntimeError("could not save %s" % TEX)
    return {"asset": TEX, "size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()],
            "compression": str(tex.get_editor_property("compression_settings")),
            "srgb": bool(tex.get_editor_property("srgb")), "lodGroup": str(tex.get_editor_property("lod_group")),
            "mips": str(tex.get_editor_property("mip_gen_settings"))}


def system(name, lifetime, material):
    path = COMBAT + "/" + name
    if not EAL.does_directory_exist(COMBAT):
        EAL.make_directory(COMBAT)
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
    carrier = json.loads(AUTH.make_board_quad_carrier(path, "DirectionalBurst", PLANE, material))
    if not carrier.get("ok"):
        raise RuntimeError("quad carrier %s: %s" % (name, carrier))
    bounds = json.loads(AUTH.set_system_fixed_bounds(path, 200.0))
    EAL.save_loaded_asset(load(path), False)
    describe = json.loads(TUNE.describe_niagara_system(path)).get("describe", {})
    return {"path": path, "action": action, "seed": seed, "lifetime": lifetime, "tune": tune, "carrier": carrier,
            "bounds": bounds, "emitters": describe.get("emitters")}


out = {"errors": []}
try:
    out["texture"] = import_hitstar(ARGS["hitstar"])
    # ---- M_FX_FigurePrint + MI_FX_HitStar / MI_FX_Heal
    fig_scalars = {"Mode": 0.0, "LifeMs": 270.0, "Opacity": 1.0, "MoteCount": 4.0, "BaseRadiusUU": 20.0,
                   "KeylineUU": 1.2}
    fig_vectors = {"ColorBody": TOK["fx.impact"], "ColorEdge": TOK["fx.rim"], "ColorKeyline": TOK["mark.keyline"],
                   "GradeScale": GRADE["GradeScale"], "GradePow": GRADE["GradePow"]}
    fp, info = master(MAT + "/M_FX_FigurePrint", ["UV", "T", "P", "Mask"] + list(fig_scalars) + list(fig_vectors),
                      FIGURE_HLSL, fig_scalars, fig_vectors, wire_figure, niagara=True, depth_test=False)
    out["figurePrint"] = info
    out["mi"] = {
        "MI_FX_HitStar": mi(MAT + "/MI_FX_HitStar", fp, {"Mode": 0.0, "LifeMs": 270.0},
                            {"ColorBody": TOK["fx.impact"], "ColorEdge": TOK["fx.rim"],
                             "ColorKeyline": TOK["mark.keyline"], "GradeScale": GRADE["GradeScale"],
                             "GradePow": GRADE["GradePow"]}),
        "MI_FX_Heal": mi(MAT + "/MI_FX_Heal", fp, {"Mode": 1.0, "LifeMs": 600.0, "MoteCount": 4.0,
                                                   "BaseRadiusUU": 20.0, "KeylineUU": 1.2},
                         {"ColorBody": TOK["fx.heal"], "ColorEdge": TOK["fx.heal"], "ColorKeyline": TOK["mark.keyline"],
                          "GradeScale": GRADE["GradeScale"], "GradePow": GRADE["GradePow"]}),
    }
    # ---- the two combat systems
    out["systems"] = {
        "NS_FX_HitStar": system("NS_FX_HitStar", 0.27, MAT + "/MI_FX_HitStar"),
        "NS_FX_HealMotes": system("NS_FX_HealMotes", 0.6, MAT + "/MI_FX_Heal"),
    }
    # ---- M_FX_FigureCue: the overlay of the v2 figures (flash + depth-contour rim, CPD 15-17)
    cue_scalars = {"F": {"cpd": 15, "default": 0.0}, "I": {"cpd": 16, "default": 0.0}, "W": {"cpd": 17, "default": 0.0},
                   "RimNarrowPx": 1.5, "RimWidePx": 5.0, "RimDepthUU": 12.0, "FlashGain": 0.82, "FlashCover": 1.0}
    cue_vectors = {"FlashColor": TOK["fx.flash"], "RimColor": TOK["fx.rim"],
                   "GradeScale": ARGS["fxGrade"]["GradeScale"], "GradePow": ARGS["fxGrade"]["GradePow"]}
    cm, info = master(MAT + "/M_FX_FigureCue", ["SP", "PD", "VS", "SD"] + list(cue_scalars) + list(cue_vectors),
                      CUE_HLSL, cue_scalars, cue_vectors, wire_cue, skeletal=True, depth_test=True, two_sided=False)
    out["figureCue"] = info
    out["ok"] = not out["figurePrint"]["compileErrors"] and not out["figureCue"]["compileErrors"]
except Exception:  # noqa: BLE001
    import traceback
    out["ok"] = False
    out["error"] = traceback.format_exc()
with open(REPORT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
