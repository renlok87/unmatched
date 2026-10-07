"""FX-02 (VS-6 Z-2): the print sprite material M_FX_Print (+ the overlay twin) and its MIs.

    python tools/art/fx/fx_import.py            # build / rebuild the masters, the MIs and the star flipbook
    python tools/art/fx/fx_import.py --check    # plain Python: validate the plan (tokens, MI map, sizes)

The print look (ВР-19, 02-visual-design.md §2.6 / §9.1): flat shapes, hard edges, two or three token tones, no
gradients / fresnel glow / emissive > 1 / noise / distortion / time in the graph. One master

    /Game/S08/FX/Materials/M_FX_Print          Unlit, Translucent, two-sided, no fog, UsedWithNiagaraSprites

with the inverse tone curve of M_ConceptPaste (grade.fitScale / grade.fitPower, S08ConceptPaste.h graph 3:
display = sRGB(ACES(k x E)^p), GradeScale = 1/k, GradePow = 1/p; (1,1,1) = the plain approximate inverse ACES)
so a token colour shows on screen as its hex at both maps' exposures. Inputs: Mask texture object (BC7, sRGB off),
SubUV UV, ColorBody / ColorEdge / ColorKeyline, Opacity, static switch UseSdf + SdfShape (0 disk, 1 diamond,
2 chevron) + EdgeWidth / KeylineWidth (fractions of the radius). Colour = R x Body + G x Edge + B x Keyline,
alpha = A x ParticleAlpha x Opacity with a 0.5 threshold smoothed 1 px (fwidth).

ВР-Z2-02 (по делегированию): "NoDepthTest" of the card is a material property (bDisableDepthTest), not a static
switch - two twin masters with the identical generated graph: M_FX_Print (depth test on) and
M_FX_Print_Overlay (depth test off, the star / the arc per the card). The MI chooses the master; the graph itself
carries no NoDepthTest switch.

ВР-Z2-03 (по делегированию): the star flipbook texture T_FX_HitStar (8 frames, R body / G edge / B keyline /
A = max) is a procedural placeholder drawn by this script - the artistic star is FX-21 (VS-6 of the visual chat);
without any texture the flipbook mode of the material has nothing to show on the FX-02 placard.

The 7 MIs of the card + 4 placard MIs (FX-02 test placard) take their colours from
docs/unreal/contracts/hud/hud-style-tokens.json (no hex literals in the graph, G-TOKENS). The editor task
tools/art/fx/ue_fx_import_ue.py (de010.run_editor, headless) imports the texture, builds / rebuilds both masters,
creates the MIs, compiles and reports the statistics (the card budget: <= 40 pixel instructions).

VFX assets are their own /Game/S08/FX/** tree (ВР-FX01): committed with `git add -f` like the UM masters.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "art" / "material_library"))
sys.path.insert(0, str(REPO / "tools" / "art" / "de010"))
import de010  # noqa: E402

TOKENS = REPO / "docs/unreal/contracts/hud/hud-style-tokens.json"
FX_ROOT = "/Game/S08/FX"
MATERIALS = FX_ROOT + "/Materials"
STAR_PNG = "fx-star-flipbook.png"  # written to the work dir, imported by the editor task
WORK = Path("C:/tmp/z2-fx")
TOOL_VERSION = "1"

# ---- the tone bands of the placard / the 7 MIs (body, edge, keyline token ids; ВР-Z2-04: edge = card.glyph,
# keyline = mark.keyline everywhere, body = the effect's own token - the card names the MIs, not the channel map)
MI_PLAN = [
    # asset, master ("" = M_FX_Print, "overlay" = M_FX_Print_Overlay), use_sdf, sdf_shape, body, edge, keyline
    ("MI_FX_HitStar", "overlay", False, -1, "fx.impact", "card.glyph", "mark.keyline"),
    ("MI_FX_Dust", "", False, -1, "fx.dust", "fx.dust.2", "mark.keyline"),
    ("MI_FX_Heal", "", False, -1, "fx.heal", "card.glyph", "mark.keyline"),
    ("MI_FX_Ember", "", False, -1, "fx.ash", "fx.ash.p1", "mark.keyline"),
    ("MI_FX_Vortex", "", False, -1, "fx.gold", "card.glyph", "mark.keyline"),
    ("MI_FX_Arc", "overlay", False, -1, "fx.gold", "card.glyph", "mark.keyline"),
    ("MI_FX_Chevron", "", True, 2, "fx.stone", "card.glyph", "mark.keyline"),
    # the FX-02 test placard: the star flipbook + the three SDF shapes (readability: body card.cream on keyline)
    ("MI_FX_PlacardStar", "overlay", False, -1, "fx.impact", "card.glyph", "mark.keyline"),
    ("MI_FX_PlacardDisk", "", True, 0, "card.cream", "card.glyph", "mark.keyline"),
    ("MI_FX_PlacardDiamond", "", True, 1, "fx.heal", "card.glyph", "mark.keyline"),
    ("MI_FX_PlacardChevron", "", True, 2, "fx.stone", "card.glyph", "mark.keyline"),
]

FLIPBOOK_HLSL = """// FX-02 print flipbook: the mask's R body / G edge / B keyline / A = max (ВР-FX03), straight alpha,
// the hard 0.5 threshold smoothed 1 px, then the inverse tone curve of M_ConceptPaste (graph 3).
float4 m = Texture2DSample(Mask, MaskSampler, UV);
float3 col = m.r * ColorBody.rgb + m.g * ColorEdge.rgb + m.b * ColorKeyline.rgb;
float a = m.a * saturate(ParticleAlpha) * saturate(Opacity);
float aw = fwidth(a) + 1e-4;
a = smoothstep(0.5 - aw, 0.5 + aw, a);
float3 t = saturate(col);
float3 y = min(pow(t, GradePow.rgb), 0.98);
float3 qa = 2.51 - y * 2.43;
float3 qb = 0.03 - y * 0.59;
float3 qc = -y * 0.14;
float3 x = (-qb + sqrt(max(qb * qb - 4.0 * qa * qc, 0.0))) / (2.0 * qa);
return float4(x / 0.6 * GradeScale.rgb, a);"""

SDF_HLSL = """// FX-02 print SDF shapes (0 disk, 1 diamond, 2 chevron): t = 0 at the shape centre / stroke centre line,
// 1 at the shape edge; body inside, the edge band at the rim, the keyline ring just outside (fractions of the
// radius), then the same inverse tone curve and the 0.5 alpha threshold as the flipbook branch.
float2 p = UV - 0.5;
float t;
if (SdfShape < 0.5) {
  t = length(p) * 2.0;
} else if (SdfShape < 1.5) {
  t = (abs(p.x) + abs(p.y)) * 2.0;
} else {
  // chevron: the signed distance to the V centre line y = 0.25 - 0.9|x| (opening up), band-normalized
  float line = p.y + 0.25 - 0.9 * abs(p.x);
  t = abs(line) * (1.0 / sqrt(1.0 + 0.81)) * 4.0;
}
float ew = max(EdgeWidth, 1e-3);
float kw = max(KeylineWidth, 1e-3);
float wb = 1.0 - saturate((t - (1.0 - 2.0 * ew)) / ew);
float we = 1.0 - saturate(abs(t - (1.0 - ew)) / ew);
float wk = 1.0 - saturate(abs(t - (1.0 + kw)) / kw);
float3 col = wb * ColorBody.rgb + we * ColorEdge.rgb + wk * ColorKeyline.rgb;
float a = max(max(wb, we), wk) * saturate(ParticleAlpha) * saturate(Opacity);
float aw = fwidth(a) + 1e-4;
a = smoothstep(0.5 - aw, 0.5 + aw, a);
float3 tc = saturate(col);
float3 y = min(pow(tc, GradePow.rgb), 0.98);
float3 qa = 2.51 - y * 2.43;
float3 qb = 0.03 - y * 0.59;
float3 qc = -y * 0.14;
float3 x = (-qb + sqrt(max(qb * qb - 4.0 * qa * qc, 0.0))) / (2.0 * qa);
return float4(x / 0.6 * GradeScale.rgb, a);"""


def srgb_to_linear(channel: int) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_color(hexstr: str):
    h = hexstr.lstrip("#")
    return [round(srgb_to_linear(int(h[i:i + 2], 16)), 6) for i in (0, 2, 4)] + [1.0]


def tokens() -> dict:
    data = json.loads(TOKENS.read_text(encoding="utf-8"))["colors"]
    return {k: v["hex"] for k, v in data.items() if isinstance(v, dict) and "hex" in v}


class Graph:
    def __init__(self):
        self.nodes, self.links, self.attrs = {}, [], {}
        self._rows = {}

    def add(self, nid, cls, props=None, col=0):
        if nid in self.nodes:
            raise ValueError("duplicate node " + nid)
        row = self._rows.get(col, 0)
        self._rows[col] = row + 1
        self.nodes[nid] = {"class": "MaterialExpression" + cls, "props": dict(props or {}),
                           "x": -2400 + 320 * col, "y": -600 + 150 * row}
        return nid

    def link(self, src, out, dst, inp):
        for n in (src, dst):
            if n not in self.nodes:
                raise ValueError("unknown node " + n)
        self.links.append([src, out, dst, inp])

    def attr(self, pin, src, out=""):
        self.attrs[pin] = [src, out]


def print_graph(tok: dict, star_texture: str) -> Graph:
    """The shared graph of both masters: the two Custom nodes behind the UseSdf switch."""
    g = Graph()
    g.add("uv", "TextureCoordinate", {"coordinate_index": 0}, 0)
    g.add("vcol", "VertexColor", {}, 0)
    g.add("mask", "TextureObjectParameter", {"parameter_name": "Mask", "texture": star_texture,
                                             "sampler_type": "SAMPLERTYPE_MASKS", "group": "Print",
                                             "sort_priority": 0}, 0)
    for nid, name, default, group, sort in (
            ("p_op", "Opacity", 1.0, "Print", 1),
            ("p_shape", "SdfShape", 0.0, "Print", 2),
            ("p_edgew", "EdgeWidth", 0.14, "Print", 3),
            ("p_keyw", "KeylineWidth", 0.07, "Print", 4)):
        g.add(nid, "ScalarParameter", {"parameter_name": name, "default_value": default, "group": group,
                                       "sort_priority": sort}, 1)
    g.add("p_body", "VectorParameter", {"parameter_name": "ColorBody",
                                        "default_value": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0},
                                        "group": "Print", "sort_priority": 5}, 1)
    g.add("p_edge", "VectorParameter", {"parameter_name": "ColorEdge",
                                        "default_value": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0},
                                        "group": "Print", "sort_priority": 6}, 1)
    g.add("p_key", "VectorParameter", {"parameter_name": "ColorKeyline",
                                       "default_value": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0},
                                       "group": "Print", "sort_priority": 7}, 1)
    # the grade of the active board profile (FX grade trace); (1,1,1) = the plain approximate inverse ACES
    g.add("p_gscale", "VectorParameter", {"parameter_name": "GradeScale",
                                          "default_value": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
                                          "group": "Grade", "sort_priority": 0}, 1)
    g.add("p_gpow", "VectorParameter", {"parameter_name": "GradePow",
                                        "default_value": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0},
                                        "group": "Grade", "sort_priority": 1}, 1)
    flip_inputs = ["Mask", "UV", "ParticleAlpha", "Opacity", "ColorBody", "ColorEdge", "ColorKeyline",
                   "GradeScale", "GradePow"]
    g.add("flip", "Custom", {"code": FLIPBOOK_HLSL, "description": "UM_FX_Print_Flipbook",
                             "output_type": "CMOT_FLOAT4", "inputs": flip_inputs}, 2)
    sdf_inputs = ["UV", "ParticleAlpha", "Opacity", "SdfShape", "EdgeWidth", "KeylineWidth", "ColorBody",
                  "ColorEdge", "ColorKeyline", "GradeScale", "GradePow"]
    g.add("sdf", "Custom", {"code": SDF_HLSL, "description": "UM_FX_Print_Sdf",
                            "output_type": "CMOT_FLOAT4", "inputs": sdf_inputs}, 2)
    for inp, (src, out) in {"Mask": ("mask", ""), "UV": ("uv", ""), "ParticleAlpha": ("vcol", "A"),
                            "Opacity": ("p_op", ""), "SdfShape": ("p_shape", ""), "EdgeWidth": ("p_edgew", ""),
                            "KeylineWidth": ("p_keyw", ""), "ColorBody": ("p_body", ""),
                            "ColorEdge": ("p_edge", ""), "ColorKeyline": ("p_key", ""),
                            "GradeScale": ("p_gscale", ""), "GradePow": ("p_gpow", "")}.items():
        g.link(src, out, "flip", inp) if inp in flip_inputs else None
        g.link(src, out, "sdf", inp) if inp in sdf_inputs else None
    g.add("sw_sdf", "StaticSwitchParameter", {"parameter_name": "UseSdf", "default_value": False,
                                              "group": "Print", "sort_priority": 8}, 3)
    g.link("flip", "", "sw_sdf", "False")
    g.link("sdf", "", "sw_sdf", "True")
    g.add("rgb", "ComponentMask", {"r": True, "g": True, "b": True}, 4)
    g.add("alp", "ComponentMask", {"a": True}, 4)
    g.link("sw_sdf", "", "rgb", "")
    g.link("sw_sdf", "", "alp", "")
    g.attr("MP_EMISSIVE_COLOR", "rgb", "")
    g.attr("MP_OPACITY", "alp", "")
    return g


def star_flipbook_png(path: Path, frames: int = 8, px: int = 128) -> dict:
    """The placeholder 8-frame hit-star strip (ВР-Z2-03): a 4-point burst star, R body / G edge / B keyline,
    A = max(R, G, B), hard edges (the material owns the AA)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise SystemExit("PIL required for the placeholder star: %s" % exc)

    def star_points(cx, cy, radius, inner_ratio, rot_deg):
        pts = []
        for i in range(8):
            ang = math.radians(rot_deg + i * 45.0)
            r = radius if i % 2 == 0 else radius * inner_ratio
            pts.append((cx + r * math.sin(ang), cy - r * math.cos(ang)))
        return pts

    strip = Image.new("RGBA", (px * frames, px), (0, 0, 0, 0))
    for f in range(frames):
        im = Image.new("RGBA", (px * 4, px * 4), (0, 0, 0, 0))  # 4x supersample, NEAREST down for hard edges
        d = ImageDraw.Draw(im)
        cx = cy = px * 2
        k = f / (frames - 1.0)
        radius = (0.34 + 0.42 * k) * px * 4
        rot = -6.0 + 12.0 * k
        # keyline (B) - the same star 16% larger, then edge (G) 6% larger, then the body (R) on top
        d.polygon(star_points(cx, cy, radius * 1.16, 0.30, rot), fill=(0, 0, 255, 255))
        d.polygon(star_points(cx, cy, radius * 1.06, 0.29, rot), fill=(0, 255, 0, 255))
        d.polygon(star_points(cx, cy, radius, 0.28, rot), fill=(255, 0, 0, 255))
        frame = im.resize((px, px), Image.NEAREST)
        strip.paste(frame, (f * px, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(path)
    return {"frames": frames, "px": px, "w": px * frames, "h": px}


def mi_specs(tok: dict) -> list:
    specs = []
    for asset, master, use_sdf, shape, body, edge, key in MI_PLAN:
        specs.append({
            "asset": "%s/%s" % (MATERIALS, asset),
            "parent": "%s/M_FX_Print" % MATERIALS if not master else "%s/M_FX_Print_Overlay" % MATERIALS,
            "scalars": {"Opacity": 1.0, "SdfShape": float(shape), "EdgeWidth": 0.14, "KeylineWidth": 0.07},
            "vectors": {"ColorBody": linear_color(tok[body]), "ColorEdge": linear_color(tok[edge]),
                        "ColorKeyline": linear_color(tok[key])},
            "textures": {"Mask": "%s/Textures/T_FX_HitStar" % FX_ROOT},
            "switches": {"UseSdf": use_sdf},
            "tokens": {"body": body, "edge": edge, "keyline": key},
        })
    return specs


def check(tok: dict) -> list:
    problems = []
    for asset, _, _, _, body, edge, key in MI_PLAN:
        for t in (body, edge, key):
            if t not in tok:
                problems.append("%s: token %s missing" % (asset, t))
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    tok = tokens()
    problems = check(tok)
    if a.check or problems:
        print(json.dumps({"selfTest": "PASS" if not problems else "FAIL", "problems": problems,
                          "mis": [m[0] for m in MI_PLAN], "tokens": len(tok)}, indent=1))
        return 1 if problems else 0

    WORK.mkdir(parents=True, exist_ok=True)
    star = star_flipbook_png(WORK / STAR_PNG)
    g = print_graph(tok, FX_ROOT + "/Textures/T_FX_HitStar")
    masters = []
    for name, overlay in (("M_FX_Print", False), ("M_FX_Print_Overlay", True)):
        masters.append({"master": "%s/%s" % (MATERIALS, name), "settings": {
            "blend_mode": "BLEND_TRANSLUCENT", "shading_model": "MSM_UNLIT", "two_sided": True,
            "use_material_attributes": False, "tangent_space_normal": False,
            "usages": ["MATUSAGE_NIAGARA_SPRITES"], "disable_depth_test": overlay},
            "nodes": g.nodes, "links": g.links, "attrs": g.attrs, "instances": [],
            "signature": "%s-v%s-overlay%d" % (name, TOOL_VERSION, int(overlay))})
    res = de010.run_editor(REPO / "tools" / "art" / "fx" / "ue_fx_import_ue.py",
                           {"out": str(WORK / "fx-import.json"), "masters": masters,
                            "texture": {"png": str(WORK / STAR_PNG), "asset": "%s/Textures/T_FX_HitStar" % FX_ROOT,
                                        "subUV": [star["frames"], 1]},
                            "mis": mi_specs(tok)}, WORK, "fx-import")
    de010.write(WORK / "fx-import.json", res)
    stats = {m["master"].rsplit("/", 1)[-1]: m.get("statistics", {}).get("num_pixel_shader_instructions")
             for m in res.get("masters", [])}
    ok = not any(m.get("compile_errors") for m in res.get("masters", [])) and res.get("texture", {}).get("ok")
    print(json.dumps({"ok": ok, "pixelInstructions": stats, "mis": sorted(res.get("mis", {})),
                      "errors": [e for m in res.get("masters", []) for e in m.get("compile_errors", [])][:5]},
                     indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
