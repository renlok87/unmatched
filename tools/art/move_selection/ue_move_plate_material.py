"""MS-T-08 (docs/game-design/move-selection 04 §6.1): build M_UM_MovePlate, the material of the move-selection plates.

  /Game/S08/MoveSelection/M_UM_MovePlate   unlit, translucent, used with instanced static meshes, no fog, responsive AA.
      Drawn on the engine plane (100 uu, normal +Z) of every plate instance (US08MoveHighlightComponent, four ISMs:
      PlateFill, PlateRing, PlateOutline, Glyphs - the "Channel" parameter of each ISM's MID). One Custom node draws the
      shapes of 03 §4.1 / §4.2 from:
        * the instance-local position (LocalPosition, instance origin) -> q in uu from the space centre (+X / +Y =
          world, the instances are never rotated);
        * the per-instance custom data 0..5 (S08MovePlateCpd: state, steps / candidate figure scale, chip, glyph index,
          flags, colour index), passed to the pixel shader through two VertexInterpolators (04 §6.1, R4 §5.1);
        * the style parameters (S08MovePlateSpec::Param*, from the profile "moveSelection" block).
      Channel 0 fill (V-01 18 %, V-07 dark 35 %, V-11 10 %), 1 ring (solid V-01, dashed V-02, double V-04, dashed outer
      V-04b, dashed double red V-09, dimmed V-10, 45 deg hatch V-07, dashed ally ring on hover V-06, long dashes
      V-11/V-12, the thin candidate ring V-17 under the figure), 2 outline (V-14/V-15 team circle - P2 with corner gaps -,
      V-16 corner brackets), 3 glyph (X of V-08, "!" of V-09). Every channel: nothing at r <= OccClear on an occupied
      space (except the candidate ring) and a cut of +-PipCutDeg around a hero's leader pip (+Y). Emissive through
      EyeAdaptationInverse (the game-layer rule: the on-screen value does not follow the exposure).

Run (the editor must be CLOSED - UnrealEditor-Cmd holds the project; never inside a GPU-measurement window):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/move_selection/ue_move_plate_material.py [--force]" -unattended -nosplash -nullrhi
Plain Python (no UE):
  python -B tools/art/move_selection/ue_move_plate_material.py --check
      the parameter names against unreal/Unmatched/Source/Unmatched/S08/S08MoveHighlight.h (S08MovePlateSpec)
Idempotent: rebuilt only when the MoveSelectionGraphVersion tag differs (or --force). The report line is
'MOVE-PLATE-MATERIAL-REPORT {...}', also written to <project>/Saved/MoveSelection/move-plate-material-report.json.
The asset lives under Content/ (gitignored): it is force-added like the other /Game/S08 assets.
Status: предложено (the look is accepted by the user, MS-Q-04 / MS-T-27).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
HEADER = REPO / "unreal/Unmatched/Source/Unmatched/S08/S08MoveHighlight.h"

ROOT = "/Game/S08/MoveSelection"
MATERIAL_NAME = "M_UM_MovePlate"
MATERIAL_PATH = f"{ROOT}/{MATERIAL_NAME}"
GRAPH_TAG = "MoveSelectionGraphVersion"
GRAPH_VERSION = "1"

# scalar parameters and their defaults (04 §4.7 numbers; the component overwrites them from the profile)
SCALARS = {
    "Channel": 1.0, "Shape": 0.0, "HalfUU": 44.0, "RingCenter": 36.0, "RingWidth": 3.5, "Keyline": 1.5,
    "OutlineInner": 39.6, "OutlineOuter": 41.0, "OccClear": 30.0, "PipCutDeg": 15.0, "FillAlpha": 0.18,
    "DashCount": 12.0, "DashDuty": 0.6, "CandRadius": 18.9, "CandWidth": 1.2, "CandAlpha": 0.7, "LastMoveAlpha": 0.6,
}
# vector parameters (linear; FLinearColor::FromSRGBColor of #F2E9D8, #111317, #D9483F, #DAC576, #5786A8)
VECTORS = {
    "PlateColor": (0.8879, 0.8148, 0.6867), "KeylineColor": (0.0056, 0.0065, 0.0086),
    "ErrorColor": (0.6939, 0.0648, 0.0497), "TeamP1Color": (0.7011, 0.5583, 0.1812),
    "TeamP2Color": (0.0953, 0.2384, 0.3916),
}
EXPOSURE_PARAM = "ExposureCompensationAlpha"
# Custom node inputs in this order (A, B = the interpolated per-instance data)
INPUTS = ["A", "B"] + list(SCALARS) + list(VECTORS)

PLATE_HLSL = r"""
// q: uu from the space centre (+X / +Y = world); A.zw / B = custom data 0..5 (S08MovePlateCpd)
float2 q = A.xy / 50.0 * HalfUU;
float st = round(A.z);
float aux = A.w;
float flags = round(B.z);
float colIdx = round(B.w);
bool hover = fmod(flags, 2.0) >= 1.0;
bool sent = fmod(floor(flags / 2.0), 2.0) >= 1.0;
bool occ = fmod(floor(flags / 8.0), 2.0) >= 1.0;
bool pip = fmod(floor(flags / 16.0), 2.0) >= 1.0;
float r = length(q);
float rho = r;
if (Shape > 0.5) {
  // a grid cell: rounded square, rho = 41 on its edge (0.82 of the cell)
  float2 dq = abs(q) - 31.0;
  rho = length(max(dq, 0.0)) + min(max(dq.x, dq.y), 0.0) + 31.0;
}
float w = max(fwidth(rho), 0.02);
float ringIn = RingCenter - 0.5 * RingWidth;
float ringOut = RingCenter + 0.5 * RingWidth;
float kIn = ringIn - Keyline;
float kOut = ringOut + Keyline;
float ang = degrees(atan2(abs(q.x), q.y));
float cut = pip ? saturate((ang - PipCutDeg) * 0.0174533 * max(r, 1.0) / w + 0.5) : 1.0;
float occM = occ ? saturate((rho - OccClear) / w + 0.5) : 1.0;
float phi = atan2(q.y, q.x) * 0.1591549 + 0.5;
float arc = 6.2831853 * max(r, 1.0);
float tA = frac(phi * DashCount);
float dA = (tA < DashDuty) ? min(tA, DashDuty - tA) : -min(tA - DashDuty, 1.0 - tA);
float dashA = saturate(dA * arc / max(DashCount, 1.0) / w + 0.5);
float t6 = frac(phi * 6.0);
float d6 = (t6 < 0.7) ? min(t6, 0.7 - t6) : -min(t6 - 0.7, 1.0 - t6);
float dash6 = saturate(d6 * arc / 6.0 / w + 0.5);
float t12 = frac(phi * 12.0);
float d12 = (t12 < 0.5) ? min(t12, 0.5 - t12) : -min(t12 - 0.5, 1.0 - t12);
float dash12 = saturate(d12 * arc / 12.0 / w + 0.5);
float bRing = saturate((rho - ringIn) / w + 0.5) * saturate((ringOut - rho) / w + 0.5);
float bKey = saturate((rho - kIn) / w + 0.5) * saturate((ringIn - rho) / w + 0.5)
           + saturate((rho - ringOut) / w + 0.5) * saturate((kOut - rho) / w + 0.5);
float bInner = saturate((rho - 24.75) / w + 0.5) * saturate((27.25 - rho) / w + 0.5);
float bInnerKey = saturate((rho - 23.75) / w + 0.5) * saturate((24.75 - rho) / w + 0.5)
                + saturate((rho - 27.25) / w + 0.5) * saturate((28.25 - rho) / w + 0.5);
float3 col = PlateColor;
float a = 0.0;
if (Channel < 0.5) {
  // fill: V-01 / V-04 / V-04b at FillAlpha, V-10 dimmed, V-07 dark 35 % out to the ring band, V-11 10 %
  float fa = 0.0;
  float3 fc = PlateColor;
  float edge = ringIn;
  if (st == 7.0 || st == 3.0 || st == 2.0) fa = FillAlpha;
  else if (st == 4.0) fa = FillAlpha * 0.7;
  else if (st == 5.0) { fa = 0.35; fc = KeylineColor; edge = kOut; }
  else if (st == 9.0) fa = 0.10;
  col = fc;
  a = fa * saturate((edge - rho) / w + 0.5) * occM * cut;
} else if (Channel < 1.5) {
  float3 c1 = PlateColor;
  float ringM = 0.0;
  float keyM = 0.0;
  bool useOcc = true;
  if (st == 7.0) { ringM = bRing; keyM = bKey; }
  else if (st == 8.0) { ringM = bRing * dashA; keyM = bKey * dashA; }
  else if (st == 3.0 || st == 4.0) { ringM = bRing + bInner; keyM = bKey + bInnerKey; }
  else if (st == 2.0) { ringM = bRing * dashA + bInner; keyM = bKey * dashA + bInnerKey; }
  else if (st == 1.0) { ringM = (bRing + bInner) * dashA; keyM = (bKey + bInnerKey) * dashA; c1 = ErrorColor; }
  else if (st == 5.0) {
    float s = (q.x + q.y) * 0.7071068;
    float ws = max(fwidth(s), 0.02);
    float th = frac(s / 6.0);
    float dh = (th < 0.42) ? min(th, 0.42 - th) : -min(th - 0.42, 1.0 - th);
    float zone = saturate((rho - OccClear) / w + 0.5) * saturate((kOut - rho) / w + 0.5);
    keyM = saturate(dh * 6.0 / ws + 0.5) * zone * 0.85;
  }
  else if (st == 6.0) {
    if (hover) {
      float hb = saturate((rho - (RingCenter - 0.75)) / w + 0.5) * saturate((RingCenter + 0.75 - rho) / w + 0.5);
      ringM = hb * dash12 * 0.6;
    }
  }
  else if (st == 9.0 || st == 10.0) { ringM = bRing * dash6; keyM = bKey * dash6; }
  else if (st == 11.0) {
    float sc = aux > 0.05 ? aux : 1.0;
    float cIn = CandRadius * sc - 0.5 * CandWidth * sc;
    float cOut = CandRadius * sc + 0.5 * CandWidth * sc;
    float ck = 0.6 * sc;
    ringM = saturate((r - cIn) / w + 0.5) * saturate((cOut - r) / w + 0.5);
    keyM = saturate((r - (cIn - ck)) / w + 0.5) * saturate((cIn - r) / w + 0.5)
         + saturate((r - cOut) / w + 0.5) * saturate((cOut + ck - r) / w + 0.5);
    float ca = hover ? 1.0 : CandAlpha;
    ringM *= ca;
    keyM *= ca;
    useOcc = false;
  }
  float sum = ringM + keyM;
  col = (ringM * c1 + keyM * KeylineColor) / max(sum, 0.0001);
  a = saturate(sum) * (useOcc ? occM : 1.0) * cut;
  if (sent || st == 4.0) col *= 0.7;
} else if (Channel < 2.5) {
  // outline: V-14 / V-15 (P1 circle, P2 with six gaps), V-16 four corner brackets
  float3 tc = colIdx > 2.5 ? ErrorColor : (colIdx > 1.5 ? TeamP2Color : (colIdx > 0.5 ? TeamP1Color : PlateColor));
  float bo = saturate((rho - OutlineInner) / w + 0.5) * saturate((OutlineOuter - rho) / w + 0.5);
  float m = 0.0;
  if (st == 2.0 || st == 3.0) {
    m = bo * (st == 3.0 ? LastMoveAlpha : 1.0);
    if (colIdx > 1.5 && colIdx < 2.5) {
      float tg = frac(phi * 6.0);
      float dg = min(tg, 1.0 - tg);
      m *= saturate((dg - 0.04) * arc / 6.0 / w + 0.5);
    }
  } else if (st == 1.0) {
    float t4 = frac(phi * 4.0 - 0.5);
    float dist = min(t4, 1.0 - t4);
    m = bo * saturate((0.1333 - dist) * arc / 4.0 / w + 0.5);
  }
  col = tc;
  a = m * cut;
} else {
  // glyph: X (V-08) and "!" (V-09: the bar towards the top of the K1 screen = -Y, the dot below)
  float wq = max(length(fwidth(q)), 0.02);
  float dd = 10000.0;
  if (st == 1.0) {
    float uu = (q.x + q.y) * 0.7071068;
    float vv = (q.x - q.y) * 0.7071068;
    dd = min(max(abs(vv) - 2.5, abs(uu) - 16.0), max(abs(uu) - 2.5, abs(vv) - 16.0));
  } else if (st == 2.0) {
    float bar = max(abs(q.x) - 2.6, abs(q.y + 6.0) - 9.0);
    float dotD = length(q - float2(0.0, 9.0)) - 3.2;
    dd = min(bar, dotD);
  }
  float fillM = saturate(-dd / wq + 0.5);
  float keyG = saturate(-(dd - 1.4) / wq + 0.5) - fillM;
  col = (fillM * ErrorColor + keyG * KeylineColor) / max(fillM + keyG, 0.0001);
  a = saturate(fillM + keyG);
}
return float4(col, saturate(a));
"""


def header_params() -> dict:
    text = HEADER.read_text(encoding="utf-8")
    names = dict(re.findall(r'Param(\w+)\s*=\s*TEXT\("(\w+)"\)', text))
    return names


def check() -> tuple[dict, list[str]]:
    errors = []
    names = set(header_params().values())
    want = set(SCALARS) | set(VECTORS)
    for n in sorted(want - names):
        errors.append(f"material parameter {n} has no S08MovePlateSpec::Param* in {HEADER.name}")
    for n in sorted(names - want):
        errors.append(f"header parameter {n} is not built by this script")
    if f"{MATERIAL_PATH}.{MATERIAL_NAME}" not in HEADER.read_text(encoding="utf-8"):
        errors.append(f"S08MovePlateSpec::MaterialPath is not {MATERIAL_PATH}.{MATERIAL_NAME}")
    return {"parameters": sorted(want), "header": sorted(names)}, errors


# ---------------------------------------------------------------------------------------------------- UE
def _expr(material, cls, x, y):
    node = u.MaterialEditingLibrary.create_material_expression(material, cls, x, y)
    if node is None:
        raise RuntimeError(f"could not create {cls}")
    return node


def _connect(src, out, dst, inp):
    if not u.MaterialEditingLibrary.connect_material_expressions(src, out, dst, inp):
        raise RuntimeError(f"could not connect {src.get_name()}.{out or '<0>'} -> {dst.get_name()}.{inp}")


def _set(obj, name, value) -> bool:
    try:
        obj.set_editor_property(name, value)
        return True
    except Exception:  # an engine without the property: reported, not fatal
        return False


def build_material(force: bool) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    material = u.load_asset(MATERIAL_PATH) if eal.does_asset_exist(MATERIAL_PATH) else None
    if material is not None and not force and eal.get_metadata_tag(material, GRAPH_TAG) == GRAPH_VERSION:
        return {"action": "unchanged", "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION}
    action = "rebuilt" if material is not None else "created"
    if material is None:
        if not eal.does_directory_exist(ROOT):
            eal.make_directory(ROOT)
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(MATERIAL_NAME, ROOT, u.Material, u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {MATERIAL_PATH}")
    mel.delete_all_material_expressions(material)
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)
    material.set_editor_property("two_sided", False)
    material.set_editor_property("used_with_instanced_static_meshes", True)
    settings = {"fogOff": _set(material, "use_translucency_vertex_fog", False),
                "responsiveAA": _set(material, "enable_responsive_aa", True)}
    custom = _expr(material, u.MaterialExpressionCustom, -500, 0)
    custom.set_editor_property("description", "MovePlate")
    custom.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT4)
    pins = []
    for name in INPUTS:
        ci = u.CustomInput()
        ci.set_editor_property("input_name", name)
        pins.append(ci)
    custom.set_editor_property("inputs", pins)
    custom.set_editor_property("code", PLATE_HLSL)
    # vertex side: instance-local xy + custom data 0..5 -> two interpolators
    local = _expr(material, u.MaterialExpressionLocalPosition, -1900, -500)
    xy = _expr(material, u.MaterialExpressionComponentMask, -1700, -500)
    for ch, on in (("r", True), ("g", True), ("b", False), ("a", False)):
        xy.set_editor_property(ch, on)
    _connect(local, "", xy, "")
    cpd = []
    for i in range(6):
        node = _expr(material, u.MaterialExpressionPerInstanceCustomData, -1900, -380 + i * 90)
        node.set_editor_property("data_index", i)
        node.set_editor_property("const_default_value", 0.0)
        cpd.append(node)

    def append(a, b, x, y):
        node = _expr(material, u.MaterialExpressionAppendVector, x, y)
        _connect(a, "", node, "A")
        _connect(b, "", node, "B")
        return node

    a_xy01 = append(append(xy, cpd[0], -1550, -480), cpd[1], -1400, -480)
    b_2345 = append(append(cpd[2], cpd[3], -1550, -200), append(cpd[4], cpd[5], -1550, -100), -1400, -150)
    vi_a = _expr(material, u.MaterialExpressionVertexInterpolator, -1200, -480)
    _connect(a_xy01, "", vi_a, "VS")
    vi_b = _expr(material, u.MaterialExpressionVertexInterpolator, -1200, -150)
    _connect(b_2345, "", vi_b, "VS")
    _connect(vi_a, "", custom, "A")
    _connect(vi_b, "", custom, "B")
    y = 0
    for name, value in SCALARS.items():
        node = _expr(material, u.MaterialExpressionScalarParameter, -1200, y)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", float(value))
        _connect(node, "", custom, name)
        y += 80
    for name, value in VECTORS.items():
        node = _expr(material, u.MaterialExpressionVectorParameter, -1200, y)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", u.LinearColor(*[float(v) for v in value], 1.0))
        _connect(node, "", custom, name)  # first output: RGB (float3)
        y += 100
    rgb = _expr(material, u.MaterialExpressionComponentMask, -250, -60)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        rgb.set_editor_property(ch, on)
    _connect(custom, "", rgb, "")
    alpha = _expr(material, u.MaterialExpressionComponentMask, -250, 80)
    for ch, on in (("r", False), ("g", False), ("b", False), ("a", True)):
        alpha.set_editor_property(ch, on)
    _connect(custom, "", alpha, "")
    eai_alpha = _expr(material, u.MaterialExpressionScalarParameter, -250, 200)
    eai_alpha.set_editor_property("parameter_name", EXPOSURE_PARAM)
    eai_alpha.set_editor_property("default_value", 1.0)
    eai = _expr(material, u.MaterialExpressionEyeAdaptationInverse, -80, -60)
    _connect(rgb, "", eai, "LightValueInput")
    _connect(eai_alpha, "", eai, "AlphaInput")
    mel.connect_material_property(eai, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(alpha, "", u.MaterialProperty.MP_OPACITY)
    mel.layout_material_expressions(material)
    mel.recompile_material(material)
    eal.set_metadata_tag(material, GRAPH_TAG, GRAPH_VERSION)
    if not eal.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {MATERIAL_PATH}")
    got = {"vector": sorted(str(n) for n in mel.get_vector_parameter_names(material)),
           "scalar": sorted(str(n) for n in mel.get_scalar_parameter_names(material))}
    missing = [n for n in VECTORS if n not in got["vector"]] + [n for n in SCALARS if n not in got["scalar"]]
    if missing:
        raise RuntimeError(f"{MATERIAL_PATH}: parameters missing after the build: {missing}")
    return {"action": action, "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION, "params": got,
            "expressions": int(mel.get_num_material_expressions(material)), "blend": "translucent", "shading": "unlit",
            "ismUsage": bool(material.get_editor_property("used_with_instanced_static_meshes")), "settings": settings}


# ---------------------------------------------------------------------------------------------------- entry
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="plain-Python contract checks (no UE)")
    parser.add_argument("--report", default=None, help="report JSON path")
    parser.add_argument("--force", action="store_true", help="rebuild even when the tag is current")
    args = parser.parse_args(argv)
    started = time.time()
    report: dict = {"schema": "unmatched.move-plate-material/1", "tool": "tools/art/move_selection/ue_move_plate_material.py",
                    "material": MATERIAL_PATH, "graphVersion": GRAPH_VERSION}
    ok = True
    if args.check or u is None:
        report["mode"] = "check"
        report["check"], errors = check()
        report["errors"] = errors
        ok = not errors
    else:
        report["mode"] = "build"
        try:
            report["build"] = build_material(args.force)
        except Exception as exc:  # reported; the commandlet logs the failure below
            report["build"] = {"action": "failed", "error": str(exc)}
            ok = False
        report["engine"] = str(u.SystemLibrary.get_engine_version())
    report["ok"] = ok
    report["seconds"] = round(time.time() - started, 2)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    report_path = Path(args.report) if args.report else (
        Path(u.Paths.project_saved_dir()) / "MoveSelection" / "move-plate-material-report.json" if u is not None else None)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text + "\n", encoding="utf-8")
    print("MOVE-PLATE-MATERIAL-REPORT " + json.dumps(report, ensure_ascii=False))
    print(f"MOVE-PLATE-MATERIAL-RESULT {'ok' if ok else 'failed'} mode={report['mode']}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        u.log_error(f"ue_move_plate_material.py failed (code {code}); see the MOVE-PLATE-MATERIAL-REPORT line")
