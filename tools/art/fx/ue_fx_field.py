"""VS-6 F1 (visual chat, editor task): the field / choice FX assets of FX-07, FX-13, FX-15 and FX-16.

Run by tools/art/fx/fx_field.py (de010.run_editor, headless UnrealEditor-Cmd -ExecutePythonScript); the arguments come
from the JSON file in the env DE010_ARGS ({"out": <report>, "tokens": {...}, "grade": {...}}). Idempotent: the
masters are rebuilt (expressions cleared), the MIs re-parented and re-written, the systems re-duplicated from the
engine template and re-tuned on every run.

1. /Game/S08/FX/Materials/M_FX_FieldMark - the game-layer mark master (unlit, translucent, EyeAdaptationInverse like
   M_UM_MovePlate, so a token shows at one brightness under every light profile): the radial bands of a mark around
   its object position in world uu. Mode 0 draws the SDF ring on the engine plane (FX-07 V-05: RadiusIn..RadiusOut body,
   the outer KeylineUU band), mode 1 keeps a mesh's own shape and paints its outer KeylineUU band (FX-15: the arcs of
   SM_Marker_TargetRing). Opacity and Scale are animated by the MID (S08FieldFx FS08FieldMarks).
   MIs: MI_FX_SelectionRing (board.choice / board.keyline), MI_FX_TargetArc (board.target / mark.keyline).
2. /Game/S08/FX/Materials/M_FX_BoardPrint - the print master of the board quads (unlit, translucent, used with Niagara
   mesh particles, the inverse tone curve of M_FX_Print with the profile's baked grade): mode 0 the CUE-007 dust
   (3..5 discs: the quad's size, the pattern turned by its yaw, ВР-VS6-07), mode 1 the CUE-008 chevrons (three along the quad, sized from its world
   width); the keyframes read ParticleRelativeTime (the Niagara particle's normalized age) - no Time node.
   MI_FX_Dust (text.secondary body, card.cream edge, mark.keyline) and MI_FX_Chevron (card.cream, mark.keyline) are
   re-parented from M_FX_Print onto it (ВР-VS6-06).
3. /Game/S08/FX/Board/NS_FX_Dust and NS_FX_AttackChevrons - duplicates of the engine template DirectionalBurst (Unreal
   Engine content, the NS_FX_PlacardStar recipe of Z-2): one still particle (burst 1 at t 0, no velocity / gravity),
   lifetime 0.3 / 0.6 s, CPU, deterministic, RandomSeed = CRC32 of the name (FX-04), fixed bounds, NET_UM_Board,
   pool prime 2; US08FxAuthoringLibrary.MakeBoardQuadCarrier turns the emitter into a local-space mesh renderer of the
   engine plane with the MI as override material (the component's transform places / turns / stretches the quad).
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
BOARD = FX + "/Board"
DONOR = "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst"
PLANE = "/Engine/BasicShapes/Plane"
GRAPH_TAG = "S08FieldFxGraphVersion"
GRAPH_VERSION = "1"

FIELD_HLSL = r"""
// VS-6 F1 M_FX_FieldMark: D = pixel world position - object position (uu); radial bands around the mark's centre
float r = length(D.xy);
float w = max(fwidth(r), 0.02);
float s = max(Scale, 0.001);
float body = 0.0;
float key = 0.0;
if (Mode < 0.5) {
  // FX-07 V-05: the solid ring RadiusIn..RadiusOut and the outer keyline band (the plane only carries the shape)
  float ri = RadiusIn * s;
  float ro = RadiusOut * s;
  float k = KeylineUU * s;
  body = saturate((r - ri) / w + 0.5) * saturate((ro - r) / w + 0.5);
  key = saturate((r - ro) / w + 0.5) * saturate((ro + k - r) / w + 0.5);
} else if (Mode < 1.5) {
  // a mesh is the shape; its outer KeylineUU band is the dark keyline
  float ro = OuterUU * s;
  key = saturate((r - (ro - KeylineUU)) / w + 0.5);
  body = 1.0 - key;
} else {
  // FX-15 (ВР-30, ВР-VS6-02): four arcs RadiusIn..RadiusOut centred on the diagonals, ArcSpanDeg each, with the dark
  // KeylineUU edge all around (outer, inner, ends) - it carries the shape on the white spaces of Marmoreal
  float ri = RadiusIn * s;
  float ro = RadiusOut * s;
  float k = KeylineUU * s;
  float ang = degrees(atan2(D.y, D.x)) + 360.0;
  float q4 = fmod(ang, 90.0);
  float dAng = (0.5 * ArcSpanDeg - abs(q4 - 45.0)) * 0.0174533 * max(r, 1.0);
  float inArc = saturate(dAng / w + 0.5);
  float inArcK = saturate((dAng + k) / w + 0.5);
  body = saturate((r - ri) / w + 0.5) * saturate((ro - r) / w + 0.5) * inArc;
  float shape = saturate((r - (ri - k)) / w + 0.5) * saturate((ro + k - r) / w + 0.5) * inArcK;
  key = saturate(shape - body);
}
float sum = body + key;
float3 col = (body * ColorBody.rgb + key * ColorKeyline.rgb) / max(sum, 0.0001);
return float4(col, saturate(sum) * saturate(Opacity));
"""

TONE_HLSL = r"""
// the inverse tone curve of M_FX_Print (FX-02, ВР-Z2R-09 / ВР-Z2R-12): a token shows as its hex
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

BOARD_HLSL = r"""
// VS-6 F1 M_FX_BoardPrint. P = camera-relative world position, UV = the plane's texcoord, T = particle relative time
// (0..1 of the lifetime). The world frame of the quad from the derivatives: dPdu / dPdv = world uu per uv unit.
float3 dpx = ddx(P);
float3 dpy = ddy(P);
float2 dux = ddx(UV);
float2 duy = ddy(UV);
float det = dux.x * duy.y - dux.y * duy.x;
float3 dPdu = (dpx * duy.y - dpy * dux.y) / (abs(det) > 1e-12 ? det : 1e-12);
float3 dPdv = (dpy * dux.x - dpx * duy.x) / (abs(det) > 1e-12 ? det : 1e-12);
float Lu = max(length(dPdu.xy), 1.0);
float Lv = max(length(dPdv.xy), 1.0);
float2 q = float2((UV.x - 0.5) * Lu, (UV.y - 0.5) * Lv);   // uu in the quad's own frame
float aa = max(length(fwidth(q)), 0.02);
float3 col = ColorBody.rgb;
float a = 0.0;
if (Mode < 0.5) {
  // FX-13 dust (300 ms): N = 3..5 discs - the quad's size carries N (C++: 100 x (1 + 0.04 (N - 3)) uu, ВР-VS6-07),
  // its yaw (the CRC of the cell) turns the pattern
  // the seed must not follow the derivative noise: whole degrees (C++ yaws are whole) and the rounded size
  float yaw = round(degrees(atan2(dPdu.y, dPdu.x)) + 360.0);
  yaw = fmod(yaw, 360.0);
  float n = 3.0 + clamp(round((Lu - 100.0) / 4.0), 0.0, 2.0);
  float seed = yaw + 1000.0 * n;
  float ms = saturate(T) * 300.0;
  float e = saturate(ms / 180.0);
  e = 1.0 - (1.0 - e) * (1.0 - e);
  float fade = 1.0 - saturate((ms - 180.0) / 120.0);
  float rad = ms < 180.0 ? lerp(6.0, 10.0, e) : lerp(10.0, 11.0, saturate((ms - 180.0) / 120.0));
  float best = 0.0;   // 3 body, 2 edge, 1 keyline (the strongest band of the discs at this pixel)
  float cover = 0.0;
  for (int k = 0; k < 5; ++k) {
    if (k >= (int)n) break;
    float h = frac(sin(seed * 0.1031 + k * 12.9898) * 43758.5453);
    float ang = 6.2831853 * (k / n) + (h - 0.5) * 0.9;
    float spread = 20.0 + 15.0 * h;
    float dist = lerp(16.0, spread, e);
    float2 c = float2(cos(ang), sin(ang)) * dist;
    float d = length(q - c);
    float b = saturate((rad - EdgeUU - d) / aa + 0.5);
    float g = saturate((rad - d) / aa + 0.5);
    float kk = saturate((rad + KeylineUU - d) / aa + 0.5);
    float band = b > 0.5 ? 3.0 : (g > 0.5 ? 2.0 : (kk > 0.5 ? 1.0 : 0.0));
    best = max(best, band);
    cover = max(cover, kk);
  }
  col = best > 2.5 ? ColorBody.rgb : (best > 1.5 ? ColorEdge.rgb : ColorKeyline.rgb);
  a = cover * fade * saturate(Opacity);
} else {
  // FX-16 chevrons (600 ms): three V shapes at 30 / 50 / 70 % of the attack, pointing from the attacker (u = 0) to
  // the target (u = 1); chevron i appears at 120 x i ms (0.6 -> 1.0 over 80 ms), all three fade 480 -> 600
  float ms = saturate(T) * 600.0;
  float W = max(Lv - 4.0, 4.0);        // the chevron's width across (the C++ quad is W + 4)
  float hd = 0.32 * W;                  // half depth along the attack
  float th = 0.26 * W;                  // stroke thickness
  float bestD = 1e6;
  float alpha = 0.0;
  for (int i = 0; i < 3; ++i) {
    float st = 120.0 * i;
    float on = ms >= st ? 1.0 : 0.0;   // the chevron is there from its start, the scale carries the appear
    float sc = lerp(0.6, 1.0, 1.0 - (1.0 - saturate((ms - st) / 80.0)) * (1.0 - saturate((ms - st) / 80.0)));
    float op = on * (1.0 - saturate((ms - 480.0) / 120.0));
    if (op <= 0.0) continue;
    float cx = (0.3 + 0.2 * i - 0.5) * Lu;
    float2 p = (q - float2(cx, 0.0)) / sc;
    // the polyline (-hd, +W/2) -> (+hd, 0) -> (-hd, -W/2): the distance to its two arms
    float2 tip = float2(hd, 0.0);
    float2 a0 = float2(-hd, 0.5 * W);
    float2 a1 = float2(-hd, -0.5 * W);
    float2 pa = p - tip;
    float2 ba0 = a0 - tip;
    float2 ba1 = a1 - tip;
    float d0 = length(pa - ba0 * saturate(dot(pa, ba0) / dot(ba0, ba0)));
    float d1 = length(pa - ba1 * saturate(dot(pa, ba1) / dot(ba1, ba1)));
    float d = (min(d0, d1) - 0.5 * th) * sc;
    if (d < bestD) { bestD = d; alpha = op; }
  }
  float body = saturate(-bestD / aa + 0.5);
  float keyc = saturate((KeylineUU - bestD) / aa + 0.5);
  col = body > 0.5 ? ColorBody.rgb : ColorKeyline.rgb;
  a = keyc * alpha * saturate(Opacity);
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


def master(path, inputs, code, scalars, vectors, wire, niagara=False, eai=True):
    """A Custom-node master: inputs = Custom pin names in order; wire(m, custom) connects the non-parameter pins."""
    folder, name = path.rsplit("/", 1)
    m = u.load_asset(obj(path)) if EAL.does_asset_exist(path) else None
    action = "rebuilt" if m else "created"
    if m is None:
        m = AT.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    MEL.delete_all_material_expressions(m)
    m.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    m.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property("two_sided", True)
    settings = {"fogOff": try_set(m, "use_translucency_vertex_fog", False)}
    if niagara:
        settings["niagaraMesh"] = try_set(m, "used_with_niagara_mesh_particles", True)
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
    if eai:
        # the game-layer rule (M_UM_MovePlate): the on-screen value does not follow the exposure
        one = expr(m, u.MaterialExpressionConstant, -250, 200)
        one.set_editor_property("r", 1.0)
        inv = expr(m, u.MaterialExpressionEyeAdaptationInverse, -80, -60)
        link(rgb, "", inv, "LightValueInput")
        link(one, "", inv, "AlphaInput")
        MEL.connect_material_property(inv, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    else:
        MEL.connect_material_property(rgb, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.connect_material_property(alpha, "", u.MaterialProperty.MP_OPACITY)
    MEL.layout_material_expressions(m)
    MEL.recompile_material(m)
    EAL.set_metadata_tag(m, GRAPH_TAG, GRAPH_VERSION)
    if not EAL.save_loaded_asset(m, False):
        raise RuntimeError("could not save %s" % path)
    return m, {"action": action, "settings": settings, "expressions": int(MEL.get_num_material_expressions(m))}


def wire_field(m, custom):
    wp = expr(m, u.MaterialExpressionWorldPosition, -1500, -200)
    op = expr(m, u.MaterialExpressionObjectPositionWS, -1500, -60)
    sub = expr(m, u.MaterialExpressionSubtract, -1250, -120)
    link(wp, "", sub, "A")
    link(op, "", sub, "B")
    link(sub, "", custom, "D")


def wire_board(m, custom):
    wp = expr(m, u.MaterialExpressionWorldPosition, -1500, -260)
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
    uv = expr(m, u.MaterialExpressionTextureCoordinate, -1500, -140)
    link(uv, "", custom, "UV")
    t = expr(m, u.MaterialExpressionParticleRelativeTime, -1500, -40)
    link(t, "", custom, "T")


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
    return {"parent": parent.get_path_name(), "scalars": scalars, "vectors": vectors}


def crc_seed(name):
    return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF


def system(name, lifetime, material):
    path = BOARD + "/" + name
    if not EAL.does_directory_exist(BOARD):
        EAL.make_directory(BOARD)
    # created once from the engine template; a later run re-applies every setting in place (the tune constants, the
    # quad carrier and the bounds are idempotent; a delete + duplicate in one editor process is refused by the engine)
    action = "retuned"
    if EAL.does_asset_exist(path):
        dup = load(path)
    else:
        dup = AT.duplicate_asset(name, BOARD, load(DONOR))
        action = "duplicated"
    if dup is None:
        raise RuntimeError("duplicate %s failed" % name)
    seed = crc_seed(name)
    dup.modify()
    dup.set_editor_property("determinism", True)
    dup.set_editor_property("random_seed", seed)
    dup.set_editor_property("warmup_time", 0.0)
    dup.set_editor_property("effect_type", load(FX + "/EffectTypes/NET_UM_Board"))
    for names, value in ((("pool_prime_size", "PoolPrimeSize"), 2),):
        for n in names:
            if try_set(dup, n, value):
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
    bounds = json.loads(AUTH.set_system_fixed_bounds(path, 120.0))
    EAL.save_loaded_asset(load(path), False)
    describe = json.loads(TUNE.describe_niagara_system(path)).get("describe", {})
    return {"path": path, "action": action, "seed": seed, "lifetime": lifetime, "tune": tune, "carrier": carrier,
            "bounds": bounds,
            "emitters": describe.get("emitters")}


out = {"errors": []}
try:
    # ---- 1. M_FX_FieldMark + MIs
    field_scalars = {"Mode": 0.0, "RadiusIn": 17.7, "RadiusOut": 20.1, "OuterUU": 20.0, "KeylineUU": 1.0,
                     "Opacity": 1.0, "Scale": 1.0, "ArcSpanDeg": 56.0}
    field_vectors = {"ColorBody": TOK["board.choice"], "ColorKeyline": TOK["board.keyline"]}
    fm, info = master(MAT + "/M_FX_FieldMark", ["D"] + list(field_scalars) + list(field_vectors), FIELD_HLSL,
                      field_scalars, field_vectors, wire_field)
    out["fieldMark"] = info
    out["mi"] = {
        "MI_FX_SelectionRing": mi(MAT + "/MI_FX_SelectionRing", fm, {"Mode": 0.0, "RadiusIn": 17.7, "RadiusOut": 20.1,
                                                                      "KeylineUU": 1.0},
                                  {"ColorBody": TOK["board.choice"], "ColorKeyline": TOK["board.keyline"]}),
        "MI_FX_TargetArc": mi(MAT + "/MI_FX_TargetArc", fm, {"Mode": 2.0, "RadiusIn": 30.0, "RadiusOut": 35.0,
                                                              "KeylineUU": 1.5, "ArcSpanDeg": 56.0},
                              {"ColorBody": TOK["board.target"], "ColorKeyline": TOK["mark.keyline"]}),
    }
    # ---- 2. M_FX_BoardPrint + MI_FX_Dust / MI_FX_Chevron (re-parented from M_FX_Print)
    board_scalars = {"Mode": 0.0, "EdgeUU": 1.6, "KeylineUU": 1.0, "Opacity": 1.0}
    board_vectors = {"ColorBody": TOK["text.secondary"], "ColorEdge": TOK["card.cream"],
                     "ColorKeyline": TOK["mark.keyline"], "GradeScale": GRADE["GradeScale"],
                     "GradePow": GRADE["GradePow"]}
    bp, info = master(MAT + "/M_FX_BoardPrint", ["P", "UV", "T"] + list(board_scalars) + list(board_vectors),
                      BOARD_HLSL, board_scalars, board_vectors, wire_board, niagara=True, eai=False)
    out["boardPrint"] = info
    out["mi"]["MI_FX_Dust"] = mi(MAT + "/MI_FX_Dust", bp, {"Mode": 0.0, "EdgeUU": 1.6, "KeylineUU": 1.0},
                                 {"ColorBody": TOK["text.secondary"], "ColorEdge": TOK["card.cream"],
                                  "ColorKeyline": TOK["mark.keyline"], "GradeScale": GRADE["GradeScale"],
                                  "GradePow": GRADE["GradePow"]})
    out["mi"]["MI_FX_Chevron"] = mi(MAT + "/MI_FX_Chevron", bp, {"Mode": 1.0, "KeylineUU": 2.0},
                                    {"ColorBody": TOK["card.cream"], "ColorEdge": TOK["card.cream"],
                                     "ColorKeyline": TOK["mark.keyline"], "GradeScale": GRADE["GradeScale"],
                                     "GradePow": GRADE["GradePow"]})
    # ---- 3. the two board systems
    out["systems"] = {
        "NS_FX_Dust": system("NS_FX_Dust", 0.3, MAT + "/MI_FX_Dust"),
        "NS_FX_AttackChevrons": system("NS_FX_AttackChevrons", 0.6, MAT + "/MI_FX_Chevron"),
    }
    out["ok"] = True
except Exception:  # noqa: BLE001
    import traceback
    out["ok"] = False
    out["error"] = traceback.format_exc()
with open(REPORT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
