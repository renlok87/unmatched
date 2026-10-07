"""VS-3 CP-14 (docs/game-design/visual/06-tasks/cards-portraits.csv CP-14; 02-visual-design.md §6.1, §6.3; 04-hud-spec.md
§4.1): build M_UmCardFace, the material of the card face and back (UUmCardWidget, WBP_UmCard).

  /Game/S08/UI/Common/M_UmCardFace   domain User Interface, translucent. One Custom node with ONE texture sample:
      * Face (texture object) sampled at lerp(UVRect.xy, UVRect.zw, UV) - UVRect is the drawn source rectangle of the
        registry (Config/Cards/S08CardMedia.json: cards (0, 0, src / pad), backs without the 5 px side crop); the padding
        of the power-of-two texture never shows; the sampler is the texture's own (mips, trilinear - ВР-CP03), so the
        scan stays clean at 0.52 x (hand) and 0.11 x (the deck chip);
      * Desaturation 0..1 towards the Rec.709 luminance (0.2126, 0.7152, 0.0722) - "unplayable" is 0.6 (CP-16);
      * Opacity multiplies the alpha - "unplayable" 0.7: the card.navy underlay of the widget shows through
        (ВР-VS2-CP-07); the reduced-motion flip cross-fades through it.
      No light, no highlight, no frame in the material (the frame is the CP-13 skin, CP-14 'dont').

Run (worktree project; UnrealEditor-Cmd holds it):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/cards/ue_card_face_material.py [--force]" -unattended -nosplash -nullrhi
Plain Python (no UE):
  python -B tools/art/cards/ue_card_face_material.py --check   the parameter names against UmCardWidget.h
Idempotent: rebuilt only when the CardFaceGraphVersion tag differs (or --force). Report 'CARD-FACE-MATERIAL {...}' and
art/cards-v1/card-face-material-report.json (budget <= 25 pixel shader instructions, 1 texture sample).
The asset lives under Content/ (gitignored): force-added like the other /Game/S08 assets (HUD-RULES П9).
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
HEADER = REPO / "unreal/Unmatched/Source/Unmatched/S08/UI/UmCardWidget.h"
REPORT = REPO / "art/cards-v1/card-face-material-report.json"

ROOT = "/Game/S08/UI/Common"
MATERIAL_NAME = "M_UmCardFace"
MATERIAL_PATH = f"{ROOT}/{MATERIAL_NAME}"
GRAPH_TAG = "CardFaceGraphVersion"
GRAPH_VERSION = "1"
BUDGET_PS_INSTRUCTIONS = 25
DEFAULT_TEXTURE = "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture"

SCALARS = {"Desaturation": 0.0, "Opacity": 1.0}
VECTORS = {"UVRect": (0.0, 0.0, 1.0, 1.0)}
TEXTURE_PARAM = "Face"
INPUTS = ["UV", TEXTURE_PARAM] + list(SCALARS) + list(VECTORS)

FACE_HLSL = r"""
// one sample of the scan / back: the drawn source rectangle of the padded texture, the texture's own sampler (mips)
float4 t = Texture2DSample(Face, FaceSampler, lerp(UVRect.xy, UVRect.zw, UV));
// Rec.709 luminance (linear): "unplayable" desaturates by 0.6 (CP-16)
float3 c = lerp(t.rgb, dot(t.rgb, float3(0.2126, 0.7152, 0.0722)).xxx, Desaturation);
return float4(c, t.a * Opacity);
"""


def header_params() -> set[str]:
    text = HEADER.read_text(encoding="utf-8")
    return set(re.findall(r'Param\w*\s*=\s*TEXT\("(\w+)"\)', text))


def check() -> tuple[dict, list[str]]:
    errors = []
    names = header_params()
    want = set(SCALARS) | set(VECTORS) | {TEXTURE_PARAM}
    for n in sorted(want - names):
        errors.append(f"material parameter {n} has no Param* in {HEADER.name}")
    for n in sorted(names - want):
        errors.append(f"header parameter {n} is not built by this script")
    text = HEADER.read_text(encoding="utf-8")
    if f"{MATERIAL_PATH}.{MATERIAL_NAME}" not in text:
        errors.append(f"UmCardWidget::MaterialPath is not {MATERIAL_PATH}.{MATERIAL_NAME}")
    if FACE_HLSL.count("Texture2DSample") != 1:
        errors.append("the face material must sample its texture once (CP-14 budget)")
    if "0.2126" not in FACE_HLSL or "0.7152" not in FACE_HLSL or "0.0722" not in FACE_HLSL:
        errors.append("the desaturation must use the Rec.709 weights")
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


def _stats(material) -> dict:
    """Pixel / vertex shader instructions of the current shader platform (0 under -nullrhi: run with a RHI)."""
    try:
        st = u.MaterialEditingLibrary.get_statistics(material)
        return {"psInstructions": int(st.num_pixel_shader_instructions),
                "vsInstructions": int(st.num_vertex_shader_instructions), "samplers": int(st.num_samplers)}
    except Exception as exc:  # noqa: BLE001 - reported, not fatal
        return {"error": str(exc)}


def build_material(force: bool) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    material = u.load_asset(MATERIAL_PATH) if eal.does_asset_exist(MATERIAL_PATH) else None
    if material is not None and not force and eal.get_metadata_tag(material, GRAPH_TAG) == GRAPH_VERSION:
        return {"action": "unchanged", "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION, "stats": _stats(material),
                "budgetPs": BUDGET_PS_INSTRUCTIONS}
    action = "rebuilt" if material is not None else "created"
    if material is None:
        if not eal.does_directory_exist(ROOT):
            eal.make_directory(ROOT)
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(MATERIAL_NAME, ROOT, u.Material,
                                                                      u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {MATERIAL_PATH}")
    mel.delete_all_material_expressions(material)
    material.set_editor_property("material_domain", u.MaterialDomain.MD_UI)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)
    custom = _expr(material, u.MaterialExpressionCustom, -400, 0)
    custom.set_editor_property("description", "CardFace")
    custom.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT4)
    pins = []
    for name in INPUTS:
        ci = u.CustomInput()
        ci.set_editor_property("input_name", name)
        pins.append(ci)
    custom.set_editor_property("inputs", pins)
    custom.set_editor_property("code", FACE_HLSL)
    uv = _expr(material, u.MaterialExpressionTextureCoordinate, -900, -300)
    _connect(uv, "", custom, "UV")
    tex = _expr(material, u.MaterialExpressionTextureObjectParameter, -900, -180)
    tex.set_editor_property("parameter_name", TEXTURE_PARAM)
    tex.set_editor_property("texture", u.load_asset(DEFAULT_TEXTURE))
    tex.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_COLOR)
    _connect(tex, "", custom, TEXTURE_PARAM)
    y = -40
    for name, value in SCALARS.items():
        node = _expr(material, u.MaterialExpressionScalarParameter, -900, y)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", float(value))
        _connect(node, "", custom, name)
        y += 80
    for name, value in VECTORS.items():
        node = _expr(material, u.MaterialExpressionVectorParameter, -900, y)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", u.LinearColor(*[float(v) for v in value]))
        if not u.MaterialEditingLibrary.connect_material_expressions(node, "RGBA", custom, name):
            app = _expr(material, u.MaterialExpressionAppendVector, -700, y)
            _connect(node, "", app, "A")
            _connect(node, "A", app, "B")
            _connect(app, "", custom, name)
        y += 100
    rgb = _expr(material, u.MaterialExpressionComponentMask, -150, -60)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        rgb.set_editor_property(ch, on)
    _connect(custom, "", rgb, "")
    alpha = _expr(material, u.MaterialExpressionComponentMask, -150, 80)
    for ch, on in (("r", False), ("g", False), ("b", False), ("a", True)):
        alpha.set_editor_property(ch, on)
    _connect(custom, "", alpha, "")
    mel.connect_material_property(rgb, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(alpha, "", u.MaterialProperty.MP_OPACITY)
    mel.layout_material_expressions(material)
    mel.recompile_material(material)
    eal.set_metadata_tag(material, GRAPH_TAG, GRAPH_VERSION)
    if not eal.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {MATERIAL_PATH}")
    got = {"vector": sorted(str(n) for n in mel.get_vector_parameter_names(material)),
           "scalar": sorted(str(n) for n in mel.get_scalar_parameter_names(material)),
           "texture": sorted(str(n) for n in mel.get_texture_parameter_names(material))}
    missing = ([n for n in VECTORS if n not in got["vector"]] + [n for n in SCALARS if n not in got["scalar"]]
               + ([TEXTURE_PARAM] if TEXTURE_PARAM not in got["texture"] else []))
    if missing:
        raise RuntimeError(f"{MATERIAL_PATH}: parameters missing after the build: {missing}")
    return {"action": action, "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION, "params": got, "domain": "UI",
            "blend": "translucent", "samples": FACE_HLSL.count("Texture2DSample"), "stats": _stats(material),
            "budgetPs": BUDGET_PS_INSTRUCTIONS}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="plain-Python contract checks (no UE)")
    parser.add_argument("--force", action="store_true", help="rebuild even when the tag is current")
    args = parser.parse_args(argv)
    started = time.time()
    report: dict = {"schema": "unmatched.card-face-material/1", "tool": "tools/art/cards/ue_card_face_material.py",
                    "card": "CP-14", "material": MATERIAL_PATH, "graphVersion": GRAPH_VERSION}
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
    if report["mode"] == "build":
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(text + "\n", encoding="utf-8", newline="\n")
    line = "CARD-FACE-MATERIAL " + json.dumps(report, ensure_ascii=False)
    if u is not None:
        (u.log if ok else u.log_error)(line)
    else:
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
