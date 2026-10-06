"""VS-2 CP-08 (docs/game-design/visual/06-tasks/cards-portraits.csv CP-08; 02-visual-design.md §6.4; 04-hud-spec.md §4.3):
build M_UmPortraitDisc, the material of the portrait circle (US08TurnPortraitWidget, WBP_UmPortrait).

  /Game/S08/UI/Common/M_UmPortraitDisc   domain User Interface, translucent. One Custom node draws, from the widget UV:
      * the avatar: Avatar (texture object) sampled at lerp(UVRect.xy, UVRect.zw, UV) - UVRect is the disc of the
        registry (Config/Cards/S08CardMedia.json portraits.*.disc, the source sits in the top-left of the padded
        texture: uv = src / pad) - over FillColor (card.navy) where the PNG is transparent; Desaturation 0..1 with the
        Rec.709 weights (fallen / loser states);
      * the rim: KeylineColor (mark.keyline) outside, EdgeColor (panel.edge, its alpha kept) inside it, widths
        KeylineFrac / EdgeFrac in fractions of the diameter; the circle and both band edges antialiased over 1 px
        (fwidth);
      * Opacity multiplies the result (the loser 0.6).
      No colour literal in the widget code (G-TOKENS): the defaults below are the token values (hud-style-tokens.json),
      the widget sets every colour from DA_UmHudTheme.

Run (worktree project; UnrealEditor-Cmd holds it):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/cards/ue_portrait_disc_material.py [--force]" -unattended -nosplash -nullrhi
Plain Python (no UE):
  python -B tools/art/cards/ue_portrait_disc_material.py --check   the parameter names against UmPortrait.h
Idempotent: rebuilt only when the PortraitDiscGraphVersion tag differs (or --force). Report 'PORTRAIT-DISC-MATERIAL
{...}' and art/cards-v1/portrait-disc-material-report.json (pixel shader instruction count, budget <= 30).
The asset lives under Content/ (gitignored): force-added like the other /Game/S08 assets.
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
HEADER = REPO / "unreal/Unmatched/Source/Unmatched/S08/UI/UmPortrait.h"
TOKENS = REPO / "docs/unreal/contracts/hud/hud-style-tokens.json"
REPORT = REPO / "art/cards-v1/portrait-disc-material-report.json"

ROOT = "/Game/S08/UI/Common"
MATERIAL_NAME = "M_UmPortraitDisc"
MATERIAL_PATH = f"{ROOT}/{MATERIAL_NAME}"
GRAPH_TAG = "PortraitDiscGraphVersion"
GRAPH_VERSION = "1"
BUDGET_PS_INSTRUCTIONS = 30
DEFAULT_TEXTURE = "/Engine/EngineResources/WhiteSquareTexture.WhiteSquareTexture"

SCALARS = {"Desaturation": 0.0, "Opacity": 1.0, "EdgeFrac": 1.5 / 42.0, "KeylineFrac": 1.0 / 42.0}
VECTOR_TOKENS = {"EdgeColor": "panel.edge", "KeylineColor": "mark.keyline", "FillColor": "card.navy"}
VECTORS_EXTRA = {"UVRect": (0.0, 0.0, 1.0, 1.0)}
TEXTURE_PARAM = "Avatar"
INPUTS = ["UV", TEXTURE_PARAM] + list(SCALARS) + list(VECTOR_TOKENS) + list(VECTORS_EXTRA)

DISC_HLSL = r"""
// UV 0..1 over the square widget; d = 1 on the circle (radius-normalised)
float d = length(UV - 0.5) * 2.0;
float aa = max(fwidth(d), 0.0001);
float rk = 1.0 - 2.0 * KeylineFrac;
float re = rk - 2.0 * EdgeFrac;
float4 t = Texture2DSample(Avatar, AvatarSampler, lerp(UVRect.xy, UVRect.zw, UV));
float3 c = lerp(FillColor.rgb, t.rgb, t.a);
c = lerp(c, dot(c, float3(0.2126, 0.7152, 0.0722)).xxx, Desaturation);
float wA = saturate((re - d) / aa + 0.5);
float wK = 1.0 - saturate((rk - d) / aa + 0.5);
float wE = 1.0 - wA - wK;
float a = wA + wE * EdgeColor.a + wK;
float3 col = (wA * c + wE * EdgeColor.a * EdgeColor.rgb + wK * KeylineColor.rgb) / max(a, 0.0001);
return float4(col, a * saturate((1.0 - d) / aa + 0.5) * Opacity);
"""


def srgb_to_linear(c8: int) -> float:
    c = c8 / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def token_linear(name: str) -> tuple[float, float, float, float]:
    """The linear colour + alpha of a token (an alias without its own hex takes the target's), as
    FLinearColor::FromSRGBColor."""
    colors = json.loads(TOKENS.read_text(encoding="utf-8"))["colors"]
    alpha = float(colors[name].get("alpha", 1.0))
    entry, hops = colors[name], 0
    while "hex" not in entry:
        entry, hops = colors[entry["alias"]], hops + 1
        if hops > 8:
            raise KeyError(f"{name}: alias loop")
    hexv = entry["hex"].lstrip("#")
    r, g, b = (srgb_to_linear(int(hexv[i:i + 2], 16)) for i in (0, 2, 4))
    return round(r, 6), round(g, 6), round(b, 6), alpha


def header_params() -> set[str]:
    text = HEADER.read_text(encoding="utf-8")
    return set(re.findall(r'Param\w*\s*=\s*TEXT\("(\w+)"\)', text))


def check() -> tuple[dict, list[str]]:
    errors = []
    names = header_params()
    want = set(SCALARS) | set(VECTOR_TOKENS) | set(VECTORS_EXTRA) | {TEXTURE_PARAM}
    for n in sorted(want - names):
        errors.append(f"material parameter {n} has no Param* in {HEADER.name}")
    for n in sorted(names - want):
        errors.append(f"header parameter {n} is not built by this script")
    text = HEADER.read_text(encoding="utf-8")
    if f"{MATERIAL_PATH}.{MATERIAL_NAME}" not in text:
        errors.append(f"UmPortrait::MaterialPath is not {MATERIAL_PATH}.{MATERIAL_NAME}")
    for k, tok in VECTOR_TOKENS.items():
        try:
            token_linear(tok)
        except KeyError:
            errors.append(f"token {tok} ({k}) missing from hud-style-tokens.json")
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
    custom.set_editor_property("description", "PortraitDisc")
    custom.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT4)
    pins = []
    for name in INPUTS:
        ci = u.CustomInput()
        ci.set_editor_property("input_name", name)
        pins.append(ci)
    custom.set_editor_property("inputs", pins)
    custom.set_editor_property("code", DISC_HLSL)
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
    vectors = {k: token_linear(t) for k, t in VECTOR_TOKENS.items()}
    vectors.update(VECTORS_EXTRA)
    for name, value in vectors.items():
        node = _expr(material, u.MaterialExpressionVectorParameter, -900, y)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", u.LinearColor(*[float(v) for v in value]))
        # the RGBA output of a vector parameter (UE 5: "RGBA"); else RGB + A appended
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
    missing = ([n for n in vectors if n not in got["vector"]] + [n for n in SCALARS if n not in got["scalar"]]
               + ([TEXTURE_PARAM] if TEXTURE_PARAM not in got["texture"] else []))
    if missing:
        raise RuntimeError(f"{MATERIAL_PATH}: parameters missing after the build: {missing}")
    stats = _stats(material)
    return {"action": action, "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION, "params": got,
            "domain": "UI", "blend": "translucent", "stats": stats, "budgetPs": BUDGET_PS_INSTRUCTIONS,
            "defaults": {k: list(v) for k, v in vectors.items()}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="plain-Python contract checks (no UE)")
    parser.add_argument("--force", action="store_true", help="rebuild even when the tag is current")
    args = parser.parse_args(argv)
    started = time.time()
    report: dict = {"schema": "unmatched.portrait-disc-material/1", "tool": "tools/art/cards/ue_portrait_disc_material.py",
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
    if report["mode"] == "build":
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(text + "\n", encoding="utf-8", newline="\n")
    line = "PORTRAIT-DISC-MATERIAL " + json.dumps(report, ensure_ascii=False)
    if u is not None:
        (u.log if ok else u.log_error)(line)
    else:
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
