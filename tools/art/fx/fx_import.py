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
    # the FX-02 test placard: the star flipbook + the three SDF shapes. ВР-Z2R-07 (по делегированию, the Z-2 review):
    # every placard body differs from its card.glyph edge by >= 20 grey levels (the card's readability rule) - the
    # cream disk / chevron of Z-2 sat 12 levels under the white edge and the edge vanished; the outer keyline
    # mark.keyline separates the shape from the board (body : keyline >= 3 : 1 for every light body)
    ("MI_FX_PlacardStar", "overlay", False, -1, "fx.impact", "card.glyph", "mark.keyline"),
    ("MI_FX_PlacardDisk", "", True, 0, "fx.gold", "card.glyph", "mark.keyline"),
    ("MI_FX_PlacardDiamond", "", True, 1, "fx.heal", "card.glyph", "mark.keyline"),
    ("MI_FX_PlacardChevron", "", True, 2, "fx.dust", "card.glyph", "mark.keyline"),
]
# the placard band widths (fractions of the shape radius): the edge and the keyline >= 1 px at 720p on K1 for the
# 96 uu placard quads of -BenchFx=placard (the Z-2 32 uu quads with 0.14 / 0.07 gave a sub-pixel keyline)
PLACARD_EDGE_WIDTH = 0.16
PLACARD_KEYLINE_WIDTH = 0.08

FLIPBOOK_HLSL = """// FX-02 print flipbook: the mask's R body / G edge / B keyline / A = max (ВР-FX03), straight alpha,
// the hard 0.5 threshold smoothed 1 px, then the inverse tone curve of M_ConceptPaste (graph 3). M is the SubUV
// sample of the Niagara sprite (TextureSampleParameterSubUV "Mask", the renderer's SubImageSize, no frame blend).
float4 m = M;
float3 col = m.r * ColorBody.rgb + m.g * ColorEdge.rgb + m.b * ColorKeyline.rgb;
float a = m.a * saturate(ParticleAlpha) * saturate(Opacity);
float aw = fwidth(a) + 1e-4;
a = smoothstep(0.5 - aw, 0.5 + aw, a);
// ВР-Z2R-09 (по делегированию): the inverse runs per AP1 channel - the engine's filmic curve works on AP1, so the
// per-sRGB-channel inverse of the paste over-saturated the tokens (fx.gold read (255,199,100) instead of
// (242,193,78), dE76 7.9); grey tokens are unchanged (the two matrices cancel on the grey axis)
const float3x3 S2A = float3x3(0.613097, 0.339523, 0.047379, 0.070194, 0.916354, 0.013452, 0.020616, 0.109570, 0.869815);
const float3x3 A2S = float3x3(1.704859, -0.621715, -0.083299, -0.130078, 1.140734, -0.010560, -0.023964, -0.128975, 1.153013);
// ВР-Z2R-12 (по делегированию): the residual of the engine chain (gamut expansion, the film curve's desaturation)
// measured on the placard (Sarpedon K1, 5 tokens fx.heal / fx.gold / fx.dust / fx.impact / card.glyph): the
// display-linear map obs = A x target was fitted, its inverse pre-corrects the target here
const float3x3 FIX = float3x3(0.9100, 0.2545, -0.1580, 0.0266, 0.9584, 0.0321, 0.0036, -0.0773, 1.0647);
float3 tl = max(mul(S2A, saturate(mul(FIX, saturate(col)))), 0.0);
float3 y = min(pow(tl, GradePow.rgb), 0.98);
float3 qa = 2.51 - y * 2.43;
float3 qb = 0.03 - y * 0.59;
float3 qc = -y * 0.14;
float3 x = (-qb + sqrt(max(qb * qb - 4.0 * qa * qc, 0.0))) / (2.0 * qa);
return float4(max(mul(A2S, x / 0.6 * GradeScale.rgb), 0.0), a);"""

SDF_HLSL = """// FX-02 print SDF shapes (0 disk, 1 diamond, 2 chevron): t = 0 at the shape centre / the stroke centre line,
// 1 at the shape edge. HARD bands (the Z-2 review: the overlapping triangle weights blended the tones and the
// keyline ring of the disk / diamond fell outside the quad): body t < 1 - EdgeWidth, edge up to t = 1, keyline up
// to t = 1 + KeylineWidth, each boundary anti-aliased over 1 px (fwidth); the shape is scaled so that its keyline
// stays inside the quad. Then the same inverse tone curve and the 0.5 alpha threshold as the flipbook branch.
float2 p = UV - 0.5;
float ew = max(EdgeWidth, 1e-3);
float kw = max(KeylineWidth, 1e-3);
float t;
if (SdfShape < 0.5) {
  t = length(p) * 2.0 * (1.0 + kw);
} else if (SdfShape < 1.5) {
  t = (abs(p.x) + abs(p.y)) * 2.0 * (1.0 + kw);
} else {
  // chevron: the distance to the V centre line y = 0.2 - 0.8|x| (opening up), half width hw, the arms capped at
  // |x| = 0.3 ("line" is a modifier keyword in SM6 HLSL - the local is "vline")
  float hw = 0.17 / (1.0 + kw);
  float vline = p.y + 0.2 - 0.8 * abs(p.x);
  t = max(abs(vline) * (1.0 / sqrt(1.64)) / hw, 1.0 + (abs(p.x) - 0.3) / hw);
}
float aa = max(fwidth(t), 1e-4);
float inBody = 1.0 - smoothstep(1.0 - ew - aa, 1.0 - ew + aa, t);
float inShape = 1.0 - smoothstep(1.0 - aa, 1.0 + aa, t);
float inKey = 1.0 - smoothstep(1.0 + kw - aa, 1.0 + kw + aa, t);
float3 col = inBody * ColorBody.rgb + (inShape - inBody) * ColorEdge.rgb + (inKey - inShape) * ColorKeyline.rgb;
col /= max(inKey, 1e-4);
float a = inKey * saturate(ParticleAlpha) * saturate(Opacity);
float aw = fwidth(a) + 1e-4;
a = smoothstep(0.5 - aw, 0.5 + aw, a);
// ВР-Z2R-09 (по делегированию): the inverse runs per AP1 channel - the engine's filmic curve works on AP1, so the
// per-sRGB-channel inverse of the paste over-saturated the tokens (fx.gold read (255,199,100) instead of
// (242,193,78), dE76 7.9); grey tokens are unchanged (the two matrices cancel on the grey axis)
const float3x3 S2A = float3x3(0.613097, 0.339523, 0.047379, 0.070194, 0.916354, 0.013452, 0.020616, 0.109570, 0.869815);
const float3x3 A2S = float3x3(1.704859, -0.621715, -0.083299, -0.130078, 1.140734, -0.010560, -0.023964, -0.128975, 1.153013);
// ВР-Z2R-12 (по делегированию): the residual of the engine chain (gamut expansion, the film curve's desaturation)
// measured on the placard (Sarpedon K1, 5 tokens fx.heal / fx.gold / fx.dust / fx.impact / card.glyph): the
// display-linear map obs = A x target was fitted, its inverse pre-corrects the target here
const float3x3 FIX = float3x3(0.9100, 0.2545, -0.1580, 0.0266, 0.9584, 0.0321, 0.0036, -0.0773, 1.0647);
float3 tl = max(mul(S2A, saturate(mul(FIX, saturate(col)))), 0.0);
float3 y = min(pow(tl, GradePow.rgb), 0.98);
float3 qa = 2.51 - y * 2.43;
float3 qb = 0.03 - y * 0.59;
float3 qc = -y * 0.14;
float3 x = (-qb + sqrt(max(qb * qb - 4.0 * qa * qc, 0.0))) / (2.0 * qa);
return float4(max(mul(A2S, x / 0.6 * GradeScale.rgb), 0.0), a);"""


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
    # the SubUV sample of the Niagara sprite (the renderer's SubImageSize picks the frame; no frame blend - print)
    g.add("mask", "TextureSampleParameterSubUV", {"parameter_name": "Mask", "texture": star_texture,
                                                  "sampler_type": "SAMPLERTYPE_MASKS", "blend": False,
                                                  "group": "Print", "sort_priority": 0}, 0)
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
    flip_inputs = ["M", "ParticleAlpha", "Opacity", "ColorBody", "ColorEdge", "ColorKeyline",
                   "GradeScale", "GradePow"]
    g.add("flip", "Custom", {"code": FLIPBOOK_HLSL, "description": "UM_FX_Print_Flipbook",
                             "output_type": "CMOT_FLOAT4", "inputs": flip_inputs}, 2)
    sdf_inputs = ["UV", "ParticleAlpha", "Opacity", "SdfShape", "EdgeWidth", "KeylineWidth", "ColorBody",
                  "ColorEdge", "ColorKeyline", "GradeScale", "GradePow"]
    g.add("sdf", "Custom", {"code": SDF_HLSL, "description": "UM_FX_Print_Sdf",
                            "output_type": "CMOT_FLOAT4", "inputs": sdf_inputs}, 2)
    for inp, (src, out) in {"M": ("mask", "RGBA"), "UV": ("uv", ""), "ParticleAlpha": ("vcol", "A"),
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
    # every channel flag explicit (the Z-2 review: the "alp" mask kept the default R flag, so the Opacity pin read
    # the RED emissive - dark keylines and the green diamond rendered see-through)
    g.add("rgb", "ComponentMask", {"r": True, "g": True, "b": True, "a": False}, 4)
    g.add("alp", "ComponentMask", {"r": False, "g": False, "b": False, "a": True}, 4)
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


def profile_grade_fit():
    """The measured inverse-tone fit of the engine (conceptPaste.grade of the board profiles, identical on both
    maps: ВР-Z2-06 - a Niagara renderer material cannot take a runtime override, so the 4 PLACARD MIs bake it;
    the 7 combat MIs stay neutral and take the runtime grade when their systems expose the user vectors)."""
    profiles = json.loads((REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json").read_text(
        encoding="utf-8"))
    for board in profiles.get("boards", []):
        grade = (board.get("conceptPaste") or {}).get("grade") or {}
        if "fitScale" in grade:
            scale = grade["fitScale"]
            powr = grade["fitPower"]
            # the paste convention (S08ConceptPaste.cpp): GradeScale = fitScale, GradePow = 1 / fitPower
            return {"GradeScale": [round(k, 6) for k in scale] + [0.0],
                    "GradePow": [round(1.0 / k, 6) for k in powr] + [0.0]}
    return None


def mi_specs(tok: dict) -> list:
    fit = profile_grade_fit()
    specs = []
    for asset, master, use_sdf, shape, body, edge, key in MI_PLAN:
        vectors = {"ColorBody": linear_color(tok[body]), "ColorEdge": linear_color(tok[edge]),
                   "ColorKeyline": linear_color(tok[key])}
        if asset.startswith("MI_FX_Placard") and fit:
            vectors.update(fit)
        specs.append({
            "asset": "%s/%s" % (MATERIALS, asset),
            "parent": "%s/M_FX_Print" % MATERIALS if not master else "%s/M_FX_Print_Overlay" % MATERIALS,
            "scalars": {"Opacity": 1.0, "SdfShape": float(shape),
                        "EdgeWidth": PLACARD_EDGE_WIDTH if asset.startswith("MI_FX_Placard") else 0.14,
                        "KeylineWidth": PLACARD_KEYLINE_WIDTH if asset.startswith("MI_FX_Placard") else 0.07},
            "vectors": vectors,
            "textures": {"Mask": "%s/Textures/T_FX_HitStar" % FX_ROOT},
            "switches": {"UseSdf": use_sdf},
            "tokens": {"body": body, "edge": edge, "keyline": key},
        })
    return specs


def grey(hexstr: str) -> float:
    """Rec.709 luma of the sRGB-encoded colour, 0..255 (the "в сером" of the card)."""
    h = hexstr.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    def lum(hexstr):
        h = hexstr.lstrip("#")
        c = [srgb_to_linear(int(h[i:i + 2], 16)) for i in (0, 2, 4)]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def check(tok: dict) -> list:
    problems = []
    for asset, _, _, _, body, edge, key in MI_PLAN:
        for t in (body, edge, key):
            if t not in tok:
                problems.append("%s: token %s missing" % (asset, t))
        if problems or not asset.startswith("MI_FX_Placard"):
            continue
        # FX-02 readability (ВР-Z2R-07): body / edge >= 20 grey levels, body : keyline >= 3 : 1
        if abs(grey(tok[body]) - grey(tok[edge])) < 20:
            problems.append("%s: body %s / edge %s differ by < 20 grey levels" % (asset, body, edge))
        if contrast(tok[body], tok[key]) < 3.0:
            problems.append("%s: body %s : keyline %s < 3 : 1" % (asset, body, key))
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
            "usages": ["MATUSAGE_NIAGARA_SPRITES"], "disable_depth_test": overlay,
            "translucency_pass": "MTP_AFTER_DOF"},
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
    mi_ps = {k.rsplit("/", 1)[-1]: (v.get("statistics") or {}).get("num_pixel_shader_instructions")
             for k, v in res.get("mis", {}).items()}
    ok = not any(m.get("compile_errors") for m in res.get("masters", [])) and res.get("texture", {}).get("ok")         and all(isinstance(n, int) and n > 0 for n in mi_ps.values())
    print(json.dumps({"ok": ok, "pixelInstructions": stats, "miPixelInstructions": mi_ps,
                      "errors": [e for m in res.get("masters", []) for e in m.get("compile_errors", [])][:5]},
                     indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
