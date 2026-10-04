"""M_UM_Figure_v2 graph (host side): nodes, links, material settings, MI template and test MIs.

Used by ue_v2.py `master`; the editor side is ue/um_v2_master.py (creates/rebuilds the graph in place, compiles,
reads the statistics back). The graph signature (sha256 of the canonical graph) goes into the report, so a later
rebuild can be compared.

Layout of the graph:
  hero textures (TextureSampleParameter2D, v1 names and defaults) --+
  MatIDTexture / MatLUT (TextureObjectParameter, Load)             --+--> Custom "UM_V2_Core" (ue/um_v2_core.hlsl)
  DetailN / DetailRMH arrays (TextureObject, SampleGrad)          --+     -> base colour, roughness, metallic,
  PreSkinnedPosition / PreSkinnedNormal via VertexInterpolator    --+        specular, AO, normal, cloth, fuzz,
  UV0, UV1 (StaticSwitch UseUV1Metres), knobs, team colour (CPD)  --+        IsCloth, debug emissive
  dye mask: StaticSwitch UseTeamAccent (v2.1, default on) -> TeamAccentTexture.R | TeamMaskTexture.R (v2.0 path)
  cue chain of v1 (CPD FxFlash / Rim / Fade) on top of the core base colour; If(IsCloth) -> ShadingModel
  hit tint (v2.2, DE-010, CPD 12 CPD_HitTint): albedo lerp to HitTintColor by HitTint x HitTintStrength after the fade,
  plus HitTintColor x HitTint x HitTintEmissive (display units, EyeAdaptationInverse); 0 = exactly the v2.1 output
  dissolve (v2.3, DE-011, static switch UseDissolve, default OFF = exactly the v2.2 output and shaders): Custom
  "UM_V2_Dissolve" (ue/um_v2_dissolve.hlsl) on CPD 13 CPD_Dissolve (progress) / CPD 14 CPD_DissolveStyle (0 fade,
  1 ash) -> OpacityMask, ash albedo and a team-colour glow on the burning front; only the dissolve MICs (Masked
  override, /Game/UM/Materials/v2/Dissolve) turn it on
  everything -> MakeMaterialAttributes (ClearCoat pin = CustomData0 = Cloth, SubsurfaceColor = Fuzz Color)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
UM_SPEC = REPO / "art" / "um-materials" / "um-masters.json"
CORE_HLSL = HERE / "ue" / "um_v2_core.hlsl"
DISSOLVE_HLSL = HERE / "ue" / "um_v2_dissolve.hlsl"
ROOT = "/Game/UM/Materials/v2"
MASTER = ROOT + "/M_UM_Figure_v2"
TEMPLATE = ROOT + "/MI_UM_Figure_v2_Template"
TESTS = ROOT + "/Test"
V1TEX = "/Game/UM/Materials/Textures"
LUMA = (0.2126, 0.7152, 0.0722)

CORE_INPUTS = ["MatIDTex", "LUTTex", "DetN", "DetRMH", "UV0", "UV1", "UseUV1", "P", "N0", "LocalUnitM", "BCh", "Nh",
               "ORMh", "DyeMask", "Edge", "Team", "TeamDye", "TeamDyeGain", "RoughMin", "RoughMax", "DetailStrength",
               "WearStrength", "SheenStrength", "AOToBC", "Saturation", "ValueLift", "DebugView", "MatIDOverride",
               "BakeFromLUT", "UseAccent", "TeamDyeCeiling"]
CORE_OUTPUTS = [("Rough", "CMOT_FLOAT1"), ("Metal", "CMOT_FLOAT1"), ("Spec", "CMOT_FLOAT1"), ("AO", "CMOT_FLOAT1"),
                ("NormalTS", "CMOT_FLOAT3"), ("Cloth", "CMOT_FLOAT1"), ("Fuzz", "CMOT_FLOAT3"),
                ("IsCloth", "CMOT_FLOAT1"), ("DebugE", "CMOT_FLOAT3")]

# v2 knobs (name, default, group, note); the v1 knobs keep their names and neutral defaults (um-masters.json)
V2_SCALARS = [
    ("DetailStrength", 1.0, "Library", "detail normal and roughness variation of the class tiles (0 = off)"),
    ("WearStrength", 1.0, "Library", "edge wear of the classes (EdgeMaskTexture x class strength)"),
    ("SheenStrength", 1.0, "Library", "cloth sheen (Fuzz Color) scale over the preset"),
    ("MetresPerLocalUnit", 0.01, "Library", "pre-skinned local unit -> metres (figures imported x100: 1 uu = 1 cm)"),
    ("TeamDyeCeiling", 0.0, "Team", "v2.1, UseTeamAccent only: > 0 caps the gain per team colour, "
                                     "gain = min(TeamDyeGain, TeamDyeCeiling / maxChannel(team)) (0 = TeamDyeGain)"),
    ("DebugView", 0.0, "Debug", "0 off; 1 class, 2 roughness, 3 metallic, 4 detail normal, 5 wear, 6 final normal, "
                                "7 albedo, 8 fuzz, 9 tile RMH, 10 dye weight (emissive, surface black)"),
    ("DebugMatIDOverride", -1.0, "Debug", "-1 = MatID texture; 0..15 = whole material one class"),
    ("DebugBakeFromLUT", 0.0, "Debug", "1 = bake albedo replaced by the class typical colour (tests without a bake)"),
]


# v2-only Custom Primitive Data slots after the v1 layout 0-11 (art/um-materials/um-masters.json, unchanged: the v1
# masters and their tests keep it). Every slot is neutral at 0 (a primitive that sets nothing renders like its MI).
V2_CPD = {"HitTint": {"index": 12, "size": 1,
                      "meaning": "DE-010 / CUE-011: 0..1 red hit fill from the contact frame (0 = off)"},
          "Dissolve": {"index": 13, "size": 1,
                       "meaning": "DE-011 / CUE-013: 0..1 dissolve progress (UseDissolve permutation only; 0 = whole)"},
          "DissolveStyle": {"index": 14, "size": 1,
                            "meaning": "DE-011: 0 = simple fade (default, reduced motion), 1 = team-colour ash "
                                       "(candidate until the A/B sheet DE-028)"}}
# DE-010 hit tint knobs (Cue group, MI-overridable): colour linear, albedo weight at HitTint 1, emissive (display units)
HIT_TINT_COLOR = [0.85, 0.03, 0.02, 1.0]
HIT_TINT_STRENGTH = 0.7
HIT_TINT_EMISSIVE = 0.35
# DE-011 dissolve knobs (Cue group, MI-overridable). Proposal: the ash look is a candidate for the A/B sheet (DE-028)
DISSOLVE_SWITCH = "UseDissolve"
DISSOLVE_INPUTS = ["P", "LocalUnitM", "Progress", "Style", "Team", "EdgeWidth", "NoiseScale", "HeightBias",
                   "HeightUU"]
DISSOLVE_OUTPUTS = [("Edge", "CMOT_FLOAT1"), ("TeamHue", "CMOT_FLOAT3")]
DISSOLVE_KNOBS = [
    ("DissolveEdgeWidth", 0.12, "ash: width of the glowing front in field units (0..1)"),
    ("DissolveNoiseScale", 40.0, "ash: noise cells per metre of the pre-skinned figure (40 = 2.5 cm)"),
    ("DissolveHeightBias", 0.45, "ash: 0 = noise only, 1 = from the feet up by height only"),
    ("DissolveHeightUU", 60.0, "ash: figure height in pre-skinned units (the tallest v2 bounds top is 60.06)"),
    ("DissolveAshValue", 0.25, "ash: albedo of the front = team hue x value"),
    ("DissolveEdgeEmissive", 1.5, "ash: glow of the front = team hue x this (display units)"),
]


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

    def canonical(self, settings):
        return {"settings": settings, "nodes": {k: {"class": v["class"], "props": v["props"]}
                                                for k, v in sorted(self.nodes.items())},
                "links": sorted(self.links), "attributes": dict(sorted(self.attrs.items()))}


def rgba(v):
    v = list(v) + [1.0] * (4 - len(v))
    return {"r": float(v[0]), "g": float(v[1]), "b": float(v[2]), "a": float(v[3])}


def scalar(g, nid, name, default, group, col, sort=0, cpd=None):
    props = {"parameter_name": name, "default_value": float(default), "group": group, "sort_priority": sort}
    if cpd is not None:
        props.update(use_custom_primitive_data=True, primitive_data_index=cpd, group="CustomPrimitiveData")
    return g.add(nid, "ScalarParameter", props, col)


def vector(g, nid, name, default, group, col, sort=0, cpd=None):
    props = {"parameter_name": name, "default_value": rgba(default), "group": group, "sort_priority": sort}
    if cpd is not None:
        props.update(use_custom_primitive_data=True, primitive_data_index=cpd, group="CustomPrimitiveData")
    return g.add(nid, "VectorParameter", props, col)


def binop(g, nid, cls, a, b, col, a_out="", b_out="", props=None):
    g.add(nid, cls, props, col)
    if a:
        g.link(a, a_out, nid, "A")
    if b:
        g.link(b, b_out, nid, "B")
    return nid


def figure_v2_graph(spec: dict) -> Graph:
    p = spec["parameters"]
    cpd = spec["custom_primitive_data"]
    dt = spec["default_textures"]
    g = Graph()
    # ---- hero textures: v1 names, v1 defaults, + EdgeMask (v2, default black = no wear)
    for nid, name, key, sampler, sort in (("t_bc", "BaseColorTexture", "BC", "SAMPLERTYPE_COLOR", 0),
                                          ("t_n", "NormalTexture", "N", "SAMPLERTYPE_NORMAL", 1),
                                          ("t_orm", "ORMTexture", "ORM", "SAMPLERTYPE_MASKS", 2),
                                          ("t_mask", "TeamMaskTexture", "TeamMask", "SAMPLERTYPE_LINEAR_GRAYSCALE", 3),
                                          ("t_edge", "EdgeMaskTexture", "TeamMaskNone", "SAMPLERTYPE_LINEAR_GRAYSCALE", 4),
                                          ("t_accent", "TeamAccentTexture", "TeamMaskNone", "SAMPLERTYPE_LINEAR_GRAYSCALE",
                                           5)):
        g.add(nid, "TextureSampleParameter2D", {"parameter_name": name, "texture": "%s/%s" % (V1TEX, dt[key]["asset"]),
                                                "sampler_type": sampler, "group": "Textures", "sort_priority": sort}, 0)
    g.add("t_matid", "TextureObjectParameter", {"parameter_name": "MatIDTexture",
                                                "texture": ROOT + "/Textures/T_UM_MatID_Legacy",
                                                "sampler_type": "SAMPLERTYPE_LINEAR_GRAYSCALE", "group": "Library",
                                                "sort_priority": 0}, 0)
    g.add("t_lut", "TextureObjectParameter", {"parameter_name": "MatLUT", "texture": ROOT + "/Textures/T_UM_MatLUT_Global",
                                              "sampler_type": "SAMPLERTYPE_LINEAR_COLOR", "group": "Library",
                                              "sort_priority": 1}, 0)
    g.add("t_detn", "TextureObject", {"texture": ROOT + "/Textures/T_UM_DetailN_Array",
                                      "sampler_type": "SAMPLERTYPE_NORMAL"}, 0)
    g.add("t_detrmh", "TextureObject", {"texture": ROOT + "/Textures/T_UM_DetailRMH_Array",
                                        "sampler_type": "SAMPLERTYPE_LINEAR_COLOR"}, 0)
    # ---- geometry inputs
    g.add("uv0", "TextureCoordinate", {"coordinate_index": 0}, 1)
    g.add("uv1", "TextureCoordinate", {"coordinate_index": 1}, 1)
    g.add("uv1_off", "Constant2Vector", {"r": 0.0, "g": 0.0}, 1)
    g.add("sw_uv1", "StaticSwitchParameter", {"parameter_name": "UseUV1Metres", "default_value": False,
                                              "group": "Library", "sort_priority": 10}, 2)
    g.link("uv1", "", "sw_uv1", "True")
    g.link("uv1_off", "", "sw_uv1", "False")
    g.add("one", "Constant", {"r": 1.0}, 1)
    g.add("zero", "Constant", {"r": 0.0}, 1)
    g.add("sw_uv1f", "StaticSwitchParameter", {"parameter_name": "UseUV1Metres", "default_value": False,
                                               "group": "Library", "sort_priority": 10}, 2)
    g.link("one", "", "sw_uv1f", "True")
    g.link("zero", "", "sw_uv1f", "False")
    g.add("psp", "PreSkinnedPosition", {}, 1)
    g.add("psn", "PreSkinnedNormal", {}, 1)
    g.add("vi_p", "VertexInterpolator", {}, 2)
    g.add("vi_n", "VertexInterpolator", {}, 2)
    # v2.1 dye mask (LDV-12): UseTeamAccent on (default; new MIs) = TeamAccentTexture.R for every class; off = the
    # v2.0 path TeamMaskTexture.R x teamDyeAllowed. The switch prunes the unused texture, so each permutation keeps
    # one mask sampler
    g.add("sw_dye", "StaticSwitchParameter", {"parameter_name": "UseTeamAccent", "default_value": True,
                                              "group": "Team", "sort_priority": 0}, 2)
    g.link("t_accent", "R", "sw_dye", "True")
    g.link("t_mask", "R", "sw_dye", "False")
    g.add("sw_dyef", "StaticSwitchParameter", {"parameter_name": "UseTeamAccent", "default_value": True,
                                               "group": "Team", "sort_priority": 0}, 2)
    g.link("one", "", "sw_dyef", "True")
    g.link("zero", "", "sw_dyef", "False")
    g.link("psp", "", "vi_p", "VS")
    g.link("psn", "", "vi_n", "VS")
    # ---- knobs (v1 names/defaults) and v2 knobs
    col = 1
    for nid, name in (("p_dye", "TeamDye"), ("p_dyegain", "TeamDyeGain"), ("p_rmin", "RoughnessMin"),
                      ("p_rmax", "RoughnessMax"), ("p_nstr", "NormalStrength"), ("p_ao2bc", "AOToBaseColor"),
                      ("p_sat", "Saturation"), ("p_lift", "ValueLift"), ("p_emi", "EmissiveIntensity")):
        group = "Team" if name.startswith("Team") else "Knobs"
        scalar(g, nid, name, p[name]["default"], group, col)
    for name, default, group, _ in V2_SCALARS:
        scalar(g, "p_" + name, name, default, group, col)
    # hero normal strength (v1: lerp(flat, N, NormalStrength))
    g.add("flat_n", "Constant3Vector", {"constant": rgba([0.0, 0.0, 1.0, 0.0])}, 1)
    g.add("n_str", "LinearInterpolate", {}, 2)
    g.link("flat_n", "", "n_str", "A")
    g.link("t_n", "RGB", "n_str", "B")
    g.link("p_nstr", "", "n_str", "Alpha")
    # team colour: lerp(TeamColor (MI), CPD_TeamColor.rgb, CPD_TeamColor.a)
    vector(g, "p_team", "TeamColor", p["TeamColor"]["default_linear"], "Team", 1)
    vector(g, "cpd_team", "CPD_TeamColor", [0, 0, 0, 0], "", 1, cpd=cpd["TeamColor"]["index"])
    g.add("team", "LinearInterpolate", {}, 2)
    g.link("p_team", "RGB", "team", "A")
    g.link("cpd_team", "RGB", "team", "B")
    g.link("cpd_team", "A", "team", "Alpha")
    # ---- core
    g.add("core", "Custom", {"code": CORE_HLSL.read_text(encoding="utf-8"), "description": "UM_V2_Core",
                             "output_type": "CMOT_FLOAT3", "inputs": CORE_INPUTS,
                             "additional_outputs": [list(o) for o in CORE_OUTPUTS]}, 4)
    wires = {"MatIDTex": ("t_matid", ""), "LUTTex": ("t_lut", ""), "DetN": ("t_detn", ""), "DetRMH": ("t_detrmh", ""),
             "UV0": ("uv0", ""), "UV1": ("sw_uv1", ""), "UseUV1": ("sw_uv1f", ""), "P": ("vi_p", "PS"),
             "N0": ("vi_n", "PS"), "LocalUnitM": ("p_MetresPerLocalUnit", ""), "BCh": ("t_bc", "RGB"),
             "Nh": ("n_str", ""), "ORMh": ("t_orm", "RGB"), "DyeMask": ("sw_dye", ""), "Edge": ("t_edge", "R"),
             "Team": ("team", ""), "TeamDye": ("p_dye", ""), "TeamDyeGain": ("p_dyegain", ""),
             "RoughMin": ("p_rmin", ""), "RoughMax": ("p_rmax", ""), "DetailStrength": ("p_DetailStrength", ""),
             "WearStrength": ("p_WearStrength", ""), "SheenStrength": ("p_SheenStrength", ""),
             "AOToBC": ("p_ao2bc", ""), "Saturation": ("p_sat", ""), "ValueLift": ("p_lift", ""),
             "DebugView": ("p_DebugView", ""), "MatIDOverride": ("p_DebugMatIDOverride", ""),
             "BakeFromLUT": ("p_DebugBakeFromLUT", ""), "UseAccent": ("sw_dyef", ""),
             "TeamDyeCeiling": ("p_TeamDyeCeiling", "")}
    for inp in CORE_INPUTS:
        src, out = wires[inp]
        g.link(src, out, "core", inp)
    # ---- cue chain of v1 (CPD 5-11): flash, rim, fade
    vector(g, "cpd_flash", "CPD_FxFlash", [0, 0, 0, 0], "", 5, cpd=cpd["FxFlash"]["index"])
    scalar(g, "cpd_rim", "CPD_RimIntensity", 0.0, "", 5, cpd=cpd["RimIntensity"]["index"])
    scalar(g, "cpd_rimw", "CPD_RimWidth", 0.0, "", 5, cpd=cpd["RimWidth"]["index"])
    scalar(g, "cpd_fade", "CPD_Fade", 0.0, "", 5, cpd=cpd["Fade"]["index"])
    vector(g, "p_rimcol", "RimColor", p["RimColor"]["default_linear"], "Cue", 5)
    binop(g, "flash", "Multiply", "cpd_flash", "cpd_flash", 6, "RGB", "A")
    g.add("rimw_sat", "Saturate", {}, 6)
    g.link("cpd_rimw", "", "rimw_sat", "")
    g.add("rim_exp", "LinearInterpolate", {"const_a": 8.0, "const_b": 1.0}, 7)
    g.link("rimw_sat", "", "rim_exp", "Alpha")
    g.add("fresnel", "Fresnel", {"base_reflect_fraction": 0.0, "exponent": 5.0}, 8)
    g.link("rim_exp", "", "fresnel", "ExponentIn")
    binop(g, "rim_c", "Multiply", "p_rimcol", "fresnel", 9, "RGB", "")
    binop(g, "rim", "Multiply", "rim_c", "cpd_rim", 10)
    binop(g, "em_sum", "Add", "flash", "rim", 11)
    binop(g, "emissive", "Multiply", "em_sum", "p_emi", 12)
    g.add("dbg_alpha", "Constant", {"r": 1.0}, 11)
    g.add("dbg_eai", "EyeAdaptationInverse", {}, 12)
    g.link("core", "DebugE", "dbg_eai", "LightValueInput")
    g.link("dbg_alpha", "", "dbg_eai", "AlphaInput")
    binop(g, "em_total", "Add", "emissive", "dbg_eai", 13, "", "EyeAdaptationInverse")
    g.add("lum_fade", "Constant3Vector", {"constant": rgba(list(LUMA) + [0.0])}, 9)
    binop(g, "fade_l", "DotProduct", "core", "lum_fade", 10, "return", "")
    binop(g, "fade_t", "Multiply", "fade_l", None, 11, props={"const_b": float(spec["fade"]["value"])})
    g.add("base_final", "LinearInterpolate", {}, 12)
    g.link("core", "return", "base_final", "A")
    g.link("fade_t", "", "base_final", "B")
    g.link("cpd_fade", "", "base_final", "Alpha")
    # ---- hit tint (v2.2, DE-010): CPD 12, after the fade; HitTint 0 -> lerp(x, c, 0) = x and + 0 emissive
    scalar(g, "cpd_hit", "CPD_HitTint", 0.0, "", 5, cpd=V2_CPD["HitTint"]["index"])
    vector(g, "p_hitcol", "HitTintColor", HIT_TINT_COLOR, "Cue", 5, sort=10)
    scalar(g, "p_hitstr", "HitTintStrength", HIT_TINT_STRENGTH, "Cue", 5, sort=11)
    scalar(g, "p_hitemi", "HitTintEmissive", HIT_TINT_EMISSIVE, "Cue", 5, sort=12)
    binop(g, "hit_a", "Multiply", "cpd_hit", "p_hitstr", 12)
    g.add("base_hit", "LinearInterpolate", {}, 13)
    g.link("base_final", "", "base_hit", "A")
    g.link("p_hitcol", "RGB", "base_hit", "B")
    g.link("hit_a", "", "base_hit", "Alpha")
    binop(g, "hit_k", "Multiply", "cpd_hit", "p_hitemi", 12)
    binop(g, "hit_c", "Multiply", "p_hitcol", "hit_k", 13, "RGB", "")
    g.add("hit_alpha", "Constant", {"r": 1.0}, 13)
    g.add("hit_eai", "EyeAdaptationInverse", {}, 14)
    g.link("hit_c", "", "hit_eai", "LightValueInput")
    g.link("hit_alpha", "", "hit_eai", "AlphaInput")
    binop(g, "em_hit", "Add", "em_total", "hit_eai", 15, "", "EyeAdaptationInverse")
    # ---- dissolve (v2.3, DE-011): static switch UseDissolve, default off -> the attribute pins read base_hit / em_hit
    # exactly as in v2.2 (the Custom node is not compiled); on (dissolve MICs, Masked) -> UM_V2_Dissolve
    scalar(g, "cpd_dis", "CPD_Dissolve", 0.0, "", 5, cpd=V2_CPD["Dissolve"]["index"])
    scalar(g, "cpd_dstyle", "CPD_DissolveStyle", 0.0, "", 5, cpd=V2_CPD["DissolveStyle"]["index"])
    for i, (name, default, _) in enumerate(DISSOLVE_KNOBS):
        scalar(g, "p_" + name, name, default, "Cue", 5, sort=20 + i)
    g.add("dis", "Custom", {"code": DISSOLVE_HLSL.read_text(encoding="utf-8"), "description": "UM_V2_Dissolve",
                            "output_type": "CMOT_FLOAT1", "inputs": DISSOLVE_INPUTS,
                            "additional_outputs": [list(o) for o in DISSOLVE_OUTPUTS]}, 12)
    for inp, (src, out) in {"P": ("vi_p", "PS"), "LocalUnitM": ("p_MetresPerLocalUnit", ""),
                            "Progress": ("cpd_dis", ""), "Style": ("cpd_dstyle", ""), "Team": ("team", ""),
                            "EdgeWidth": ("p_DissolveEdgeWidth", ""), "NoiseScale": ("p_DissolveNoiseScale", ""),
                            "HeightBias": ("p_DissolveHeightBias", ""), "HeightUU": ("p_DissolveHeightUU", "")}.items():
        g.link(src, out, "dis", inp)
    binop(g, "dis_ash", "Multiply", "dis", "p_DissolveAshValue", 13, "TeamHue", "")
    g.add("base_dis", "LinearInterpolate", {}, 14)
    g.link("base_hit", "", "base_dis", "A")
    g.link("dis_ash", "", "base_dis", "B")
    g.link("dis", "Edge", "base_dis", "Alpha")
    binop(g, "dis_k", "Multiply", "dis", "p_DissolveEdgeEmissive", 13, "Edge", "")
    binop(g, "dis_c", "Multiply", "dis", "dis_k", 14, "TeamHue", "")
    g.add("dis_alpha", "Constant", {"r": 1.0}, 14)
    g.add("dis_eai", "EyeAdaptationInverse", {}, 15)
    g.link("dis_c", "", "dis_eai", "LightValueInput")
    g.link("dis_alpha", "", "dis_eai", "AlphaInput")
    binop(g, "em_dis", "Add", "em_hit", "dis_eai", 16, "", "EyeAdaptationInverse")
    for nid, on, off in (("sw_dis_base", ("base_dis", ""), ("base_hit", "")),
                         ("sw_dis_em", ("em_dis", ""), ("em_hit", "")),
                         ("sw_dis_mask", ("dis", ""), ("one", ""))):
        g.add(nid, "StaticSwitchParameter", {"parameter_name": DISSOLVE_SWITCH, "default_value": False,
                                             "group": "Cue", "sort_priority": 19}, 17)
        g.link(on[0], on[1], nid, "True")
        g.link(off[0], off[1], nid, "False")
    # ---- shading model per pixel: If(IsCloth > 0.5) Cloth else DefaultLit
    g.add("sm_cloth", "ShadingModel", {"shading_model": "MSM_CLOTH"}, 6)
    g.add("sm_lit", "ShadingModel", {"shading_model": "MSM_DEFAULT_LIT"}, 6)
    g.add("half", "Constant", {"r": 0.5}, 6)
    g.add("sm_if", "If", {}, 7)
    g.link("core", "IsCloth", "sm_if", "A")
    g.link("half", "", "sm_if", "B")
    g.link("sm_cloth", "", "sm_if", "A > B")
    g.link("sm_lit", "", "sm_if", "A == B")
    g.link("sm_lit", "", "sm_if", "A < B")
    # ---- attributes
    g.add("mma", "MakeMaterialAttributes", {}, 14)
    for pin, (src, out) in {"BaseColor": ("sw_dis_base", ""), "Metallic": ("core", "Metal"),
                            "Specular": ("core", "Spec"), "Roughness": ("core", "Rough"),
                            "AmbientOcclusion": ("core", "AO"), "Normal": ("core", "NormalTS"),
                            "EmissiveColor": ("sw_dis_em", ""), "ClearCoat": ("core", "Cloth"),
                            "SubsurfaceColor": ("core", "Fuzz"), "ShadingModel": ("sm_if", ""),
                            "OpacityMask": ("sw_dis_mask", "")}.items():
        g.link(src, out, "mma", pin)
    g.attr("MP_MATERIAL_ATTRIBUTES", "mma", "")
    return g


SETTINGS = {"blend_mode": "BLEND_OPAQUE", "shading_model": "MSM_FROM_MATERIAL_EXPRESSION", "two_sided": False,
            "use_material_attributes": True, "tangent_space_normal": True,
            "usages": ["MATUSAGE_SKELETAL_MESH", "MATUSAGE_INSTANCED_STATIC_MESHES"]}


def test_instances() -> list:
    """MIs of the control scene (README section 9 / task LD-master): one sphere per class (whole material one class,
    bake replaced by the class typical colour), the MatID checker sphere (real MatID Load + test bake), team spheres
    (TeamColor red on all pixels: must dye only teamDyeAllowed classes), debug views."""
    red = [0.8, 0.02, 0.02, 1.0]  # linear, the dye target of the team test (strong red, reads on any class)
    mis = [{"asset": TEMPLATE, "parent": MASTER, "scalars": {}, "vectors": {}, "textures": {}, "switches": {},
            "note": "template: v1 defaults, MatID legacy (whole hero = class 0 = v1 look) until the hero MatID exists"}]
    common = {"MetresPerLocalUnit": 0.002}   # test spheres: engine sphere (100 uu) at actor scale 0.2 -> 20 cm
    for i in range(16):
        mis.append({"asset": "%s/MI_UM_v2_Test_Class%02d" % (TESTS, i), "parent": MASTER,
                    "scalars": dict(common, DebugMatIDOverride=float(i), DebugBakeFromLUT=1.0), "vectors": {},
                    "textures": {"EdgeMaskTexture": TESTS + "/T_UM_Test_EdgeRamp"}, "switches": {}})
        mis.append({"asset": "%s/MI_UM_v2_Test_Class%02d_Red" % (TESTS, i), "parent": MASTER,
                    "scalars": dict(common, DebugMatIDOverride=float(i), DebugBakeFromLUT=1.0, TeamDye=1.0,
                                    TeamDyeGain=1.0), "vectors": {"TeamColor": red},
                    "textures": {"EdgeMaskTexture": TESTS + "/T_UM_Test_EdgeRamp"},
                    "switches": {"UseTeamAccent": False},
                    "note": "v2.0 dye path (UseTeamAccent off): TeamMask (default white) x teamDyeAllowed"})
        mis.append({"asset": "%s/MI_UM_v2_Test_Class%02d_Accent" % (TESTS, i), "parent": MASTER,
                    "scalars": dict(common, DebugMatIDOverride=float(i), DebugBakeFromLUT=1.0, TeamDye=1.0,
                                    TeamDyeGain=1.0), "vectors": {"TeamColor": red},
                    "textures": {"EdgeMaskTexture": TESTS + "/T_UM_Test_EdgeRamp",
                                 "TeamAccentTexture": TESTS + "/T_UM_Test_AccentHalf"},
                    "switches": {"UseTeamAccent": True},
                    "note": "v2.1: TeamAccent = 1 on v < 0.5 only; the dye must follow the mask on every class"})
    mis.append({"asset": TESTS + "/MI_UM_v2_Test_Checker", "parent": MASTER, "scalars": dict(common),
                "vectors": {}, "switches": {},
                "textures": {"MatIDTexture": TESTS + "/T_UM_Test_MatIDChecker",
                             "BaseColorTexture": TESTS + "/T_UM_Test_BCChecker",
                             "EdgeMaskTexture": TESTS + "/T_UM_Test_EdgeRamp"}})
    mis.append({"asset": TESTS + "/MI_UM_v2_Test_Checker_Debug", "parent": MASTER,
                "scalars": dict(common, DebugView=1.0), "vectors": {}, "switches": {},
                "textures": {"MatIDTexture": TESTS + "/T_UM_Test_MatIDChecker",
                             "BaseColorTexture": TESTS + "/T_UM_Test_BCChecker"}})
    mis.append({"asset": TESTS + "/MI_UM_v2_Test_Checker_UV1", "parent": MASTER, "scalars": dict(common),
                "vectors": {}, "switches": {"UseUV1Metres": True},
                "textures": {"MatIDTexture": TESTS + "/T_UM_Test_MatIDChecker",
                             "BaseColorTexture": TESTS + "/T_UM_Test_BCChecker"}})
    mis.append({"asset": TESTS + "/MI_UM_v2_Test_LegacyMerlin_Red", "parent": MASTER, "scalars": {}, "vectors": {},
                "textures": {}, "switches": {"UseTeamAccent": False},
                "copy_from": "/Game/PipelineCandidates/Merlin/H2/Materials/MI_Merlin_H2_Red",
                "note": "regression: Merlin H2 red-team MI values on the v2 master, MatID legacy = v1 path (v2.0 dye)"})
    mis += accent_test_instances(common, red)
    return mis


# v2.1 (UseTeamAccent) tests. Checker spheres: every class on one sphere, the dye weight (DebugView 10) with the
# accent (must follow the mask on every class) and with the v2.0 path (TeamMask white x teamDyeAllowed).
# Albedo spheres (DebugView 7: final albedo as emissive, independent of the sphere position and the lighting), class 7
# (dark, dyeable), TeamDye 1: the gain rule. Equal pairs must match within the capture noise, E must differ.
MERLIN_P1 = [0.807, 0.5271, 0.1441, 1.0]     # C-11 active palette, linear (ld-team-accent-ue.json of Merlin)
MERLIN_P2 = [0.1022, 0.2122, 0.3467, 1.0]
ALBEDO_TESTS = {
    # name: (switch UseTeamAccent or None = inherited, TeamColor, TeamDyeGain, TeamDyeCeiling, mask texture)
    "Neutral": (None, None, None, None, None),
    "AccentDefault_Red": (None, "red", 1.0, None, "TeamMask:white"),   # old mask white, no accent: nothing dyed
    "GainA": (True, "red", 20.0, None, "accent:white"),
    "GainB": (True, "red", 100.0, 16.0, "accent:white"),     # min(100, 16 / 0.8) = 20 = GainA
    "GainC": (True, "red", 20.0, 100.0, "accent:white"),     # ceiling not binding: 20 = GainA
    "GainD": (False, "red", 20.0, 4.0, "TeamMask:white"),    # v2.0 path ignores the ceiling: 20 = GainA
    "GainE": (True, "red", 10.0, None, "accent:white"),      # sensitivity: must differ from GainA
    "MerlinP1": (True, "p1", 27.12, 9.018, "accent:white"),  # min(27.12, 9.018 / 0.807) = 11.175
    "MerlinP1Ref": (True, "p1", 11.175, None, "accent:white"),
    "MerlinP2": (True, "p2", 27.12, 9.018, "accent:white"),  # min(27.12, 9.018 / 0.3467) = 26.01
    "MerlinP2Ref": (True, "p2", 26.01, None, "accent:white"),
}
ALBEDO_CLASS = 7
V1_WHITE = V1TEX + "/T_UM_Mask_White"


def accent_test_instances(common: dict, red: list) -> list:
    colours = {"red": red, "p1": MERLIN_P1, "p2": MERLIN_P2}
    checker = {"MatIDTexture": TESTS + "/T_UM_Test_MatIDChecker", "BaseColorTexture": TESTS + "/T_UM_Test_BCChecker"}
    mis = [{"asset": TESTS + "/MI_UM_v2_Test_Checker_Accent", "parent": MASTER,
            "scalars": dict(common, TeamDye=1.0, TeamDyeGain=1.0), "vectors": {"TeamColor": red},
            "textures": dict(checker, TeamAccentTexture=TESTS + "/T_UM_Test_AccentHalf"),
            "switches": {"UseTeamAccent": True}},
           {"asset": TESTS + "/MI_UM_v2_Test_Checker_AccentW", "parent": MASTER,
            "scalars": dict(common, DebugView=10.0), "vectors": {}, "switches": {"UseTeamAccent": True},
            "textures": dict(checker, TeamAccentTexture=TESTS + "/T_UM_Test_AccentHalf")},
           {"asset": TESTS + "/MI_UM_v2_Test_Checker_LegacyW", "parent": MASTER,
            "scalars": dict(common, DebugView=10.0), "vectors": {}, "switches": {"UseTeamAccent": False},
            "textures": dict(checker, TeamMaskTexture=V1_WHITE)}]
    for name, (switch, colour, gain, ceiling, mask) in ALBEDO_TESTS.items():
        sc = dict(common, DebugMatIDOverride=float(ALBEDO_CLASS), DebugBakeFromLUT=1.0, DebugView=7.0)
        vec, tex = {}, {}
        if colour:
            sc["TeamDye"] = 1.0
            vec["TeamColor"] = colours[colour]
        if gain is not None:
            sc["TeamDyeGain"] = gain
        if ceiling is not None:
            sc["TeamDyeCeiling"] = ceiling
        if mask:
            kind, _ = mask.split(":")
            tex["TeamAccentTexture" if kind == "accent" else "TeamMaskTexture"] = V1_WHITE
        mis.append({"asset": "%s/MI_UM_v2_Test_Alb_%s" % (TESTS, name), "parent": MASTER, "scalars": sc,
                    "vectors": vec, "textures": tex,
                    "switches": {} if switch is None else {"UseTeamAccent": bool(switch)}})
    return mis


def load_spec() -> dict:
    return json.loads(UM_SPEC.read_text(encoding="utf-8"))


def graph_signature(g: Graph) -> str:
    return hashlib.sha256(json.dumps(g.canonical(SETTINGS), sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def cmd_master(ue, out: Path, a, task) -> dict:
    spec = load_spec()
    g = figure_v2_graph(spec)
    sig = graph_signature(g)
    res = task(ue, "um_v2_master.py", out, timeout=1800, master=MASTER, settings=SETTINGS,
               nodes=g.nodes, links=g.links, attrs=g.attrs, instances=test_instances(), signature=sig)
    res["graph_signature"] = sig
    res["core_hlsl_sha256"] = hashlib.sha256(CORE_HLSL.read_bytes()).hexdigest()
    res["node_count"] = len(g.nodes)
    res["link_count"] = len(g.links)
    return res
