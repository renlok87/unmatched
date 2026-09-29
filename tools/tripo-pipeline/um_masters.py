#!/usr/bin/env python3
"""UM master materials (wave 4, W4-B): M_UM_Figure, M_UM_BaseMarker, M_UM_GameLayer, built by script in the LIVE
UnrealEditor through the MCP MaterialTools (the same client and call contract as tripo_pipeline.py `ue-import`).

    python tools/tripo-pipeline/um_masters.py --backend mcp build  --report <report.json> [--force]
    python tools/tripo-pipeline/um_masters.py --backend mcp verify --report <report.json>
    python tools/tripo-pipeline/um_masters.py hex "#E8C06A"          # FLinearColor::FromSRGBColor, no editor

Data: art/um-materials/um-masters.json (paths, parameters and their neutral defaults, Custom Primitive Data layout,
default textures). The graphs are produced by the functions below from that data; `graph_signature` is the SHA-256 of
the canonical graph (nodes, properties, links, outputs, material settings) and is what `verify` compares with the
editor (get_expressions / get_properties / get_expression_inputs / get_property_input), node by node.

Rules (engine gate memo §1 item 4, W4-B):
  - one Opaque master per role, no Masked, no Translucent, no World Position Offset;
  - M_UM_Figure repeats the candidates' graph (BC, lerp(BC, BC x TeamColor, TeamMask.R), DirectX N, ORM R/G/B ->
    AO/Roughness/Metallic) when every knob has its neutral default, so a candidate moved onto it renders as before;
  - Custom Primitive Data: 0-3 TeamColor (rgb + a = weight of the CPD colour over the MI TeamColor), 4 InstanceIndex
    (0 = use the MI value), 5-8 FxFlash (rgb + intensity), 9 RimIntensity, 10 RimWidth, 11 Fade. A primitive that sets
    nothing reads 0 everywhere, and 0 is neutral in every slot;
  - colours are stored as sRGB hex in data and converted with FLinearColor::FromSRGBColor (hex_to_linear) only;
  - rebuild (--force) edits the graph in place (expressions deleted and re-added): the asset keeps its identity, so
    material instances that point at it keep their parent (deleting a referenced asset nulls the references, trap of
    ADDING-AN-ASSET §8).
Statuses: the masters are "технически импортировано" at most; knob values and the palette stay "предложено".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


class _LazyTripoPipeline:
    """tripo_pipeline is imported on first use: tripo_pipeline.py itself imports this module (ue-import route
    um-master), and the pure helpers below (colour rule, spec, graphs) must not load a second copy of it."""

    def __getattr__(self, name):
        import tripo_pipeline
        return getattr(tripo_pipeline, name)


tp = _LazyTripoPipeline()

REPO = HERE.parents[1]
SPEC_REL = "art/um-materials/um-masters.json"
SCHEMA = "unmatched.um-masters/1"
REPORT_SCHEMA = "unmatched.um-masters-report/1"
LOGIC = "um-masters/1"
LUMA = (0.2126, 0.7152, 0.0722)  # Rec.709, the same weights as qa010 and control_scene_analyze


# ------------------------------------------------------------------ colour rule (AD-OPEN-39)

def srgb_u8_to_linear(value: int) -> float:
    """FLinearColor::sRGBToLinearTable[value] (Color.h: c > 0.04045 ? pow(c / 1.055 + 0.0521327, 2.4) : c / 12.92),
    rounded to float32 like the engine table (max difference to the table 3.2e-8, checked 2026-09-29)."""
    import struct
    c = value / 255.0
    lin = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return struct.unpack("f", struct.pack("f", lin))[0]


def hex_to_linear(hex_color: str, alpha: float = 1.0) -> list:
    """'#E8C06A' -> [r, g, b, a] linear = FLinearColor::FromSRGBColor(FColor(0xE8, 0xC0, 0x6A)); alpha is linear."""
    text = hex_color.strip()
    h = text[1:]
    if not text.startswith("#") or len(h) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in h):
        raise ValueError("colour must be sRGB hex #RRGGBB: %r" % hex_color)
    return [round(srgb_u8_to_linear(int(h[i:i + 2], 16)), 6) for i in (0, 2, 4)] + [float(alpha)]


def colour_value(value) -> list:
    """Data colour -> linear RGBA: '#RRGGBB' (sRGB, FromSRGBColor) or an explicit {"linear": [r, g, b(, a)]}."""
    if isinstance(value, str):
        return hex_to_linear(value)
    if isinstance(value, dict) and "linear" in value:
        v = [float(x) for x in value["linear"]]
        return v + [1.0] * (4 - len(v))
    raise ValueError("colour must be '#RRGGBB' or {\"linear\": [...]}: %r" % (value,))


def luminance(lin_rgb) -> float:
    return sum(w * c for w, c in zip(LUMA, lin_rgb))


# ------------------------------------------------------------------ spec

def load_spec(repo: Path = REPO) -> tuple:
    path = repo / SPEC_REL
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema") != SCHEMA:
        raise ValueError("%s: schema must be %s" % (SPEC_REL, SCHEMA))
    return spec, path


def texture_path(spec: dict, key: str) -> str:
    return "%s/%s" % (spec["textures_folder"], spec["default_textures"][key]["asset"])


def master_path(spec: dict, role: str) -> str:
    return "%s/%s" % (spec["folder"], spec["masters"][role]["asset"])


# ------------------------------------------------------------------ graph description

class Graph:
    """Nodes in insertion order: id -> (expression class, properties); links (src, output, dst, input); outputs."""

    def __init__(self, name: str):
        self.name = name
        self.nodes = {}
        self.links = []
        self.outputs = {}
        self._col = {}

    def add(self, nid, cls, props=None, col=0):
        if nid in self.nodes:
            raise ValueError("duplicate node %s" % nid)
        row = self._col.get(col, 0)
        self._col[col] = row + 1
        self.nodes[nid] = {"class": cls, "props": dict(props or {}), "x": -1800 + 300 * col, "y": 160 * row}
        return nid

    def link(self, src, out, dst, inp):
        for n in (src, dst):
            if n not in self.nodes:
                raise ValueError("unknown node %s" % n)
        self.links.append((src, out, dst, inp))

    def output(self, prop, src, out=""):
        self.outputs[prop] = (src, out)

    def canonical(self, settings: dict) -> dict:
        nodes = []
        for nid, n in self.nodes.items():
            nodes.append({"id": nid, "class": n["class"], "props": {k: n["props"][k] for k in sorted(n["props"])}})
        return {"name": self.name, "settings": {k: settings[k] for k in sorted(settings)}, "nodes": nodes,
                "links": sorted([list(l) for l in self.links]),
                "outputs": {k: list(v) for k, v in sorted(self.outputs.items())}}


def rgba(values) -> dict:
    v = list(values) + [1.0] * (4 - len(values))
    return {"R": v[0], "G": v[1], "B": v[2], "A": v[3]}


def _param(g, nid, name, default, group, col=0, sort=0):
    return g.add(nid, "MaterialExpressionScalarParameter",
                 {"ParameterName": name, "DefaultValue": float(default), "Group": group, "SortPriority": sort}, col)


def _vparam(g, nid, name, default, group, col=0, sort=0):
    return g.add(nid, "MaterialExpressionVectorParameter",
                 {"ParameterName": name, "DefaultValue": rgba(default), "Group": group, "SortPriority": sort}, col)


def _cpd_scalar(g, nid, name, index, col=0):
    return g.add(nid, "MaterialExpressionScalarParameter",
                 {"ParameterName": name, "DefaultValue": 0.0, "Group": "CustomPrimitiveData",
                  "bUseCustomPrimitiveData": True, "PrimitiveDataIndex": index}, col)


def _cpd_vector(g, nid, name, index, col=0):
    return g.add(nid, "MaterialExpressionVectorParameter",
                 {"ParameterName": name, "DefaultValue": rgba([0, 0, 0, 0]), "Group": "CustomPrimitiveData",
                  "bUseCustomPrimitiveData": True, "PrimitiveDataIndex": index}, col)


def _tex(g, nid, name, texture, sampler, col=0, sort=0):
    return g.add(nid, "MaterialExpressionTextureSampleParameter2D",
                 {"ParameterName": name, "Texture": texture, "SamplerType": sampler, "Group": "Textures",
                  "SortPriority": sort}, col)


def _bin(g, nid, cls, a, b, col, a_out="", b_out="", props=None):
    """Binary node: a/b are (node, output) or None (use ConstA/ConstB of props)."""
    g.add(nid, cls, props, col)
    if a is not None:
        g.link(a, a_out, nid, "A")
    if b is not None:
        g.link(b, b_out, nid, "B")
    return nid


def _lerp(g, nid, a, b, alpha, col, a_out="", b_out="", alpha_out="", props=None):
    g.add(nid, "MaterialExpressionLinearInterpolate", props, col)
    if a is not None:
        g.link(a, a_out, nid, "A")
    if b is not None:
        g.link(b, b_out, nid, "B")
    if alpha is not None:
        g.link(alpha, alpha_out, nid, "Alpha")
    return nid


def _unary(g, nid, cls, src, col, src_out="", props=None, inp=""):
    g.add(nid, cls, props, col)
    g.link(src, src_out, nid, inp)
    return nid


def _lum3(g, nid, col):
    return g.add(nid, "MaterialExpressionConstant3Vector", {"Constant": rgba(list(LUMA) + [0.0])}, col)


def _team_chain(g, spec, col):
    """team = lerp(TeamColor (MI), CPD_TeamColor.rgb, CPD_TeamColor.a) -> node 'team'."""
    p = spec["parameters"]
    _vparam(g, "p_team", "TeamColor", p["TeamColor"]["default_linear"], "Team", col)
    _cpd_vector(g, "cpd_team", "CPD_TeamColor", spec["custom_primitive_data"]["TeamColor"]["index"], col)
    _lerp(g, "team", "p_team", "cpd_team", "cpd_team", col + 1, a_out="RGB", b_out="RGB", alpha_out="A")
    return "team"


def _cue_chain(g, spec, col, colour_node, extra_emissive=None):
    """FxFlash, Rim, Fade (CPD 5-11) on top of `colour_node` (float3 base colour). Returns (base, emissive) node ids."""
    cpd = spec["custom_primitive_data"]
    p = spec["parameters"]
    _cpd_vector(g, "cpd_flash", "CPD_FxFlash", cpd["FxFlash"]["index"], col)
    _cpd_scalar(g, "cpd_rim", "CPD_RimIntensity", cpd["RimIntensity"]["index"], col)
    _cpd_scalar(g, "cpd_rimw", "CPD_RimWidth", cpd["RimWidth"]["index"], col)
    _cpd_scalar(g, "cpd_fade", "CPD_Fade", cpd["Fade"]["index"], col)
    _vparam(g, "p_rimcol", "RimColor", p["RimColor"]["default_linear"], "Cue", col)
    _param(g, "p_emi", "EmissiveIntensity", p["EmissiveIntensity"]["default"], "Knobs", col)
    # flash = rgb x a
    _bin(g, "flash", "MaterialExpressionMultiply", "cpd_flash", "cpd_flash", col + 1, "RGB", "A")
    # rim = RimColor x fresnel(exponent lerp(8, 1, saturate(width))) x intensity
    _unary(g, "rimw_sat", "MaterialExpressionSaturate", "cpd_rimw", col + 1)
    _lerp(g, "rim_exp", None, None, "rimw_sat", col + 2, props={"ConstA": 8.0, "ConstB": 1.0})
    g.add("fresnel", "MaterialExpressionFresnel", {"BaseReflectFraction": 0.0, "Exponent": 5.0}, col + 3)
    g.link("rim_exp", "", "fresnel", "ExponentIn")
    _bin(g, "rim_c", "MaterialExpressionMultiply", "p_rimcol", "fresnel", col + 4, "RGB")
    _bin(g, "rim", "MaterialExpressionMultiply", "rim_c", "cpd_rim", col + 5)
    _bin(g, "em_sum", "MaterialExpressionAdd", "flash", "rim", col + 6)
    em = "em_sum"
    if extra_emissive:
        _bin(g, "em_sum2", "MaterialExpressionAdd", em, extra_emissive, col + 7)
        em = "em_sum2"
    _bin(g, "emissive", "MaterialExpressionMultiply", em, "p_emi", col + 8)
    # fade: lerp(colour, luminance(colour) x FadeValue, CPD_Fade)
    _lum3(g, "lum_fade", col + 5)
    _bin(g, "fade_l", "MaterialExpressionDotProduct", colour_node, "lum_fade", col + 6)
    _bin(g, "fade_t", "MaterialExpressionMultiply", "fade_l", None, col + 7,
         props={"ConstB": float(spec["fade"]["value"])})
    _lerp(g, "base_final", colour_node, "fade_t", "cpd_fade", col + 8)
    return "base_final", "emissive"


def _knob_chain(g, spec, col, colour_node, orm):
    """AOToBaseColor, Saturation, ValueLift on a float3 colour; returns the node id."""
    p = spec["parameters"]
    _param(g, "p_ao2bc", "AOToBaseColor", p["AOToBaseColor"]["default"], "Knobs", col)
    _param(g, "p_sat", "Saturation", p["Saturation"]["default"], "Knobs", col)
    _param(g, "p_lift", "ValueLift", p["ValueLift"]["default"], "Knobs", col)
    _lerp(g, "ao_mul", None, orm, "p_ao2bc", col + 1, b_out="R", props={"ConstA": 1.0})
    _bin(g, "c_ao", "MaterialExpressionMultiply", colour_node, "ao_mul", col + 2)
    _unary(g, "desat_f", "MaterialExpressionOneMinus", "p_sat", col + 1)
    g.add("desat", "MaterialExpressionDesaturation", {"LuminanceFactors": rgba(list(LUMA) + [0.0])}, col + 3)
    g.link("c_ao", "", "desat", "")
    g.link("desat_f", "", "desat", "Fraction")
    _lerp(g, "lift", "desat", None, "p_lift", col + 4, props={"ConstB": 1.0})
    return "lift"


def _surface_chain(g, spec, col, nrm, orm):
    """Normal strength and roughness range (neutral: N as sampled, roughness = ORM.G)."""
    p = spec["parameters"]
    _param(g, "p_nstr", "NormalStrength", p["NormalStrength"]["default"], "Knobs", col)
    _param(g, "p_rmin", "RoughnessMin", p["RoughnessMin"]["default"], "Knobs", col)
    _param(g, "p_rmax", "RoughnessMax", p["RoughnessMax"]["default"], "Knobs", col)
    g.add("flat_n", "MaterialExpressionConstant3Vector", {"Constant": rgba([0.0, 0.0, 1.0, 0.0])}, col)
    _lerp(g, "normal", "flat_n", nrm, "p_nstr", col + 1, b_out="RGB")
    _lerp(g, "rough", "p_rmin", "p_rmax", orm, col + 1, alpha_out="G")
    return "normal", "rough"


def figure_graph(spec: dict) -> Graph:
    g = Graph("M_UM_Figure")
    p = spec["parameters"]
    _tex(g, "t_bc", "BaseColorTexture", texture_path(spec, "BC"), "SAMPLERTYPE_Color", 0, 0)
    _tex(g, "t_n", "NormalTexture", texture_path(spec, "N"), "SAMPLERTYPE_Normal", 0, 1)
    _tex(g, "t_orm", "ORMTexture", texture_path(spec, "ORM"), "SAMPLERTYPE_Masks", 0, 2)
    _tex(g, "t_mask", "TeamMaskTexture", texture_path(spec, "TeamMask"), "SAMPLERTYPE_LinearGrayscale", 0, 3)
    team = _team_chain(g, spec, 0)
    _param(g, "p_dye", "TeamDye", p["TeamDye"]["default"], "Team", 1)
    _param(g, "p_dyegain", "TeamDyeGain", p["TeamDyeGain"]["default"], "Team", 1)
    # candidates' graph: lerp(BC, BC x TeamColor, TeamMask.R); TeamDye 1 swaps BC x TeamColor for a dye that keeps the
    # cloth's luminance: TeamColor x luminance(BC) x TeamDyeGain (for dark cloth, where a multiply shows no colour)
    _bin(g, "bc_team", "MaterialExpressionMultiply", "t_bc", team, 2, "RGB", "")
    _lum3(g, "lum_bc", 1)
    _bin(g, "bc_l", "MaterialExpressionDotProduct", "t_bc", "lum_bc", 2, "RGB", "")
    _bin(g, "dye_c", "MaterialExpressionMultiply", team, "bc_l", 3)
    _bin(g, "dye", "MaterialExpressionMultiply", "dye_c", "p_dyegain", 4)
    _lerp(g, "teamed", "bc_team", "dye", "p_dye", 5)
    _lerp(g, "dyed", "t_bc", "teamed", "t_mask", 6, a_out="RGB", alpha_out="R")
    colour = _knob_chain(g, spec, 7, "dyed", "t_orm")
    base, emissive = _cue_chain(g, spec, 12, colour)
    normal, rough = _surface_chain(g, spec, 2, "t_n", "t_orm")
    g.output("MP_BaseColor", base)
    g.output("MP_Normal", normal)
    g.output("MP_Roughness", rough)
    g.output("MP_Metallic", "t_orm", "B")
    g.output("MP_AmbientOcclusion", "t_orm", "R")
    g.output("MP_EmissiveColor", emissive)
    return g


def base_marker_graph(spec: dict) -> Graph:
    """Base of a figure: textured base (atlas BC/N/ORM) or flat BaseColor; team band from the vertex mask (R) and/or the
    side wall (local vertex normal |z| below SideBandNormalZMax); pips G/B lit by InstanceIndex (1: G, 2: B, 3: G+B)."""
    g = Graph("M_UM_BaseMarker")
    p = spec["parameters"]
    _tex(g, "t_bc", "BaseColorTexture", texture_path(spec, "BC"), "SAMPLERTYPE_Color", 0, 0)
    _tex(g, "t_n", "NormalTexture", texture_path(spec, "N"), "SAMPLERTYPE_Normal", 0, 1)
    _tex(g, "t_orm", "ORMTexture", texture_path(spec, "ORM"), "SAMPLERTYPE_Masks", 0, 2)
    _vparam(g, "p_basecol", "BaseColor", p["BaseColor"]["default_linear"], "Base", 0)
    _vparam(g, "p_pip", "PipColor", p["PipColor"]["default_linear"], "Base", 0)
    _param(g, "p_pipem", "PipEmissive", p["PipEmissive"]["default"], "Base", 0)
    _param(g, "p_vmw", "VertexMaskWeight", p["VertexMaskWeight"]["default"], "Base", 0)
    _param(g, "p_sbw", "SideBandWeight", p["SideBandWeight"]["default"], "Base", 0)
    _param(g, "p_snz", "SideBandNormalZMax", p["SideBandNormalZMax"]["default"], "Base", 0)
    _param(g, "p_bandtex", "BandKeepsTexture", p["BandKeepsTexture"]["default"], "Base", 0)
    _param(g, "p_index", "InstanceIndex", p["InstanceIndex"]["default"], "Base", 0)
    _cpd_scalar(g, "cpd_index", "CPD_InstanceIndex", spec["custom_primitive_data"]["InstanceIndex"]["index"], 0)
    g.add("vc", "MaterialExpressionVertexColor", {}, 0)
    team = _team_chain(g, spec, 1)
    _bin(g, "albedo", "MaterialExpressionMultiply", "t_bc", "p_basecol", 2, "RGB", "RGB")
    # band sources
    _bin(g, "band_vc", "MaterialExpressionMultiply", "vc", "p_vmw", 2, "R", "")
    g.add("n_ws", "MaterialExpressionVertexNormalWS", {}, 1)
    g.add("n_loc", "MaterialExpressionTransform",
          {"TransformSourceType": "TRANSFORMSOURCE_World", "TransformType": "TRANSFORM_Local"}, 2)
    g.link("n_ws", "", "n_loc", "")
    g.add("n_z", "MaterialExpressionComponentMask", {"R": False, "G": False, "B": True, "A": False}, 3)
    g.link("n_loc", "", "n_z", "")
    _unary(g, "n_zabs", "MaterialExpressionAbs", "n_z", 4)
    _bin(g, "side_raw", "MaterialExpressionSubtract", "p_snz", "n_zabs", 5)
    _bin(g, "side_k", "MaterialExpressionMultiply", "side_raw", None, 6, props={"ConstB": 40.0})
    _unary(g, "side_sat", "MaterialExpressionSaturate", "side_k", 7)
    _bin(g, "band_side", "MaterialExpressionMultiply", "side_sat", "p_sbw", 8)
    _bin(g, "band_sum", "MaterialExpressionAdd", "band_vc", "band_side", 9)
    _unary(g, "band", "MaterialExpressionSaturate", "band_sum", 10)
    _bin(g, "band_tex", "MaterialExpressionMultiply", "albedo", team, 3)
    _lerp(g, "band_col", team, "band_tex", "p_bandtex", 4)
    _lerp(g, "col_band", "albedo", "band_col", "band", 11)
    # instance index: CPD 4 when set (> 0), else the MI value; pips need index > 0.5
    _bin(g, "idx_k", "MaterialExpressionMultiply", "cpd_index", None, 1, props={"ConstB": 1000.0})
    _unary(g, "idx_use", "MaterialExpressionSaturate", "idx_k", 2)
    _lerp(g, "idx", "p_index", "cpd_index", "idx_use", 3)
    _bin(g, "any_off", "MaterialExpressionSubtract", "idx", None, 4, props={"ConstB": 0.5})
    _bin(g, "any_k", "MaterialExpressionMultiply", "any_off", None, 5, props={"ConstB": 1000.0})
    _unary(g, "any_on", "MaterialExpressionSaturate", "any_k", 6)
    _bin(g, "c_d2", "MaterialExpressionSubtract", "idx", None, 4, props={"ConstB": 2.0})
    _unary(g, "c_abs", "MaterialExpressionAbs", "c_d2", 5)
    _bin(g, "c_off", "MaterialExpressionSubtract", "c_abs", None, 6, props={"ConstB": 0.5})
    _bin(g, "c_k", "MaterialExpressionMultiply", "c_off", None, 7, props={"ConstB": 1000.0})
    _unary(g, "c_on", "MaterialExpressionSaturate", "c_k", 8)
    _bin(g, "o_off", "MaterialExpressionSubtract", "idx", None, 4, props={"ConstB": 1.5})
    _bin(g, "o_k", "MaterialExpressionMultiply", "o_off", None, 5, props={"ConstB": 1000.0})
    _unary(g, "o_on", "MaterialExpressionSaturate", "o_k", 6)
    _bin(g, "g_lit", "MaterialExpressionMultiply", "vc", "c_on", 9, "G", "")
    _bin(g, "b_lit", "MaterialExpressionMultiply", "vc", "o_on", 9, "B", "")
    _bin(g, "lit_sum", "MaterialExpressionAdd", "g_lit", "b_lit", 10)
    _bin(g, "lit_any", "MaterialExpressionMultiply", "lit_sum", "any_on", 11)
    _bin(g, "lit_w", "MaterialExpressionMultiply", "lit_any", "p_vmw", 12)
    _unary(g, "lit", "MaterialExpressionSaturate", "lit_w", 13)
    _lerp(g, "col_pip", "col_band", "p_pip", "lit", 14, b_out="RGB")
    _bin(g, "glow_c", "MaterialExpressionMultiply", "p_pip", "lit", 14, "RGB")
    _bin(g, "glow", "MaterialExpressionMultiply", "glow_c", "p_pipem", 15)
    colour = _knob_chain(g, spec, 15, "col_pip", "t_orm")
    base, emissive = _cue_chain(g, spec, 20, colour, extra_emissive="glow")
    normal, rough = _surface_chain(g, spec, 2, "t_n", "t_orm")
    g.output("MP_BaseColor", base)
    g.output("MP_Normal", normal)
    g.output("MP_Roughness", rough)
    g.output("MP_Metallic", "t_orm", "B")
    g.output("MP_AmbientOcclusion", "t_orm", "R")
    g.output("MP_EmissiveColor", emissive)
    return g


def game_layer_graph(spec: dict) -> Graph:
    """Game layer (rings, highlights, markers): Unlit, EyeAdaptationInverse so the on-screen value does not follow the
    exposure; LayerColor or the team colour (UseTeamColor); FxFlash adds, Fade darkens (CPD 11)."""
    g = Graph("M_UM_GameLayer")
    p = spec["parameters"]
    cpd = spec["custom_primitive_data"]
    _vparam(g, "p_layer", "LayerColor", p["LayerColor"]["default_linear"], "Layer", 0)
    _param(g, "p_useteam", "UseTeamColor", p["UseTeamColor"]["default"], "Layer", 0)
    _param(g, "p_emi", "EmissiveIntensity", p["EmissiveIntensity"]["default"], "Knobs", 0)
    _param(g, "p_eai", "ExposureCompensationAlpha", p["ExposureCompensationAlpha"]["default"], "Layer", 0)
    team = _team_chain(g, spec, 0)
    _cpd_vector(g, "cpd_flash", "CPD_FxFlash", cpd["FxFlash"]["index"], 0)
    _cpd_scalar(g, "cpd_fade", "CPD_Fade", cpd["Fade"]["index"], 0)
    _lerp(g, "col", "p_layer", team, "p_useteam", 2, a_out="RGB")
    _bin(g, "flash", "MaterialExpressionMultiply", "cpd_flash", "cpd_flash", 2, "RGB", "A")
    _bin(g, "col_flash", "MaterialExpressionAdd", "col", "flash", 3)
    _unary(g, "fade_keep", "MaterialExpressionOneMinus", "cpd_fade", 2)
    _bin(g, "col_fade", "MaterialExpressionMultiply", "col_flash", "fade_keep", 4)
    _bin(g, "light", "MaterialExpressionMultiply", "col_fade", "p_emi", 5)
    g.add("eai", "MaterialExpressionEyeAdaptationInverse", {}, 6)
    g.link("light", "", "eai", "LightValueInput")
    g.link("p_eai", "", "eai", "AlphaInput")
    g.output("MP_EmissiveColor", "eai")
    return g


GRAPHS = {"figure": figure_graph, "base_marker": base_marker_graph, "game_layer": game_layer_graph}


def settings_of(spec: dict, role: str) -> dict:
    m = spec["masters"][role]
    return {"BlendMode": "BLEND_Opaque", "ShadingModel": m["shading_model"], "TwoSided": False,
            "bUsedWithSkeletalMesh": bool(m.get("used_with_skeletal_mesh")),
            "bUsedWithInstancedStaticMeshes": bool(m.get("used_with_instanced_static_meshes"))}


def graph_signature(spec: dict, role: str) -> str:
    canon = GRAPHS[role](spec).canonical(settings_of(spec, role))
    return hashlib.sha256(json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def expected_parameters(spec: dict, role: str) -> dict:
    """Parameter name -> kind for the master (what list_parameters must return)."""
    kinds = {"MaterialExpressionScalarParameter": "scalar", "MaterialExpressionVectorParameter": "vector",
             "MaterialExpressionTextureSampleParameter2D": "texture"}
    out = {}
    for n in GRAPHS[role](spec).nodes.values():
        if n["class"] in kinds:
            out[n["props"]["ParameterName"]] = kinds[n["class"]]
    return out


# ------------------------------------------------------------------ editor side

def _ref(value):
    value = value.get("refPath") if isinstance(value, dict) else value
    return None if value in (None, "", "None") else value


def _canon_value(v):
    """Values read back by ObjectTools.get_properties -> comparable with the planned properties (colour structs come
    back with lower-case keys {"r": ...}; floats are float32 in the editor)."""
    if isinstance(v, dict) and "refPath" in v:
        return tp.ue_package(v["refPath"])
    if isinstance(v, dict):
        return {str(k).lower(): _canon_value(x) for k, x in v.items()}
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 5)
    return v


# Inputs of an expression in declaration order (MaterialEditingLibrary.get_material_expression_input_names; "" is the
# unnamed input the editor reports as "None"); binary nodes are A, B.
OUTPUT0 = {"MaterialExpressionVectorParameter": "RGB", "MaterialExpressionTextureSampleParameter2D": "RGB",
           "MaterialExpressionEyeAdaptationInverse": "EyeAdaptationInverse"}
NO_INPUTS = ("MaterialExpressionScalarParameter", "MaterialExpressionVectorParameter",
             "MaterialExpressionTextureSampleParameter2D",
             "MaterialExpressionConstant3Vector", "MaterialExpressionVertexColor", "MaterialExpressionVertexNormalWS")
INPUT_ORDER = {"MaterialExpressionLinearInterpolate": ["A", "B", "Alpha"],
               "MaterialExpressionDesaturation": ["", "Fraction"],
               "MaterialExpressionFresnel": ["ExponentIn", "BaseReflectFractionIn", "Normal"],
               "MaterialExpressionEyeAdaptationInverse": ["LightValueInput", "AlphaInput"]}
UNARY = ("MaterialExpressionOneMinus", "MaterialExpressionSaturate", "MaterialExpressionAbs",
         "MaterialExpressionComponentMask", "MaterialExpressionTransform")


def reported_links(g: "Graph") -> set:
    """The links as get_expression_inputs reports them. The toolset asks
    MaterialEditingLibrary.get_input_node_output_name_for_material_expression(expression, source), which returns the
    output of the FIRST input wired from that source: when one source feeds two inputs of the same node through
    different outputs (lerp(TeamColor, CPD.rgb, CPD.a)), both inputs read back with the first output name (measured
    2026-09-29 on a scratch material; the connection itself is right, only the read-back is ambiguous)."""
    out = set()
    by_dst = {}
    for src, o, dst, inp in g.links:
        by_dst.setdefault(dst, []).append((src, o, inp))
    for dst, items in by_dst.items():
        cls = g.nodes[dst]["class"]
        order = INPUT_ORDER.get(cls) or ([""] if cls in UNARY else ["A", "B"])
        items = sorted(items, key=lambda t: order.index(t[2]) if t[2] in order else 99)
        first = {}
        for src, o, inp in items:
            first.setdefault(src, o)
            out.add((src, first[src], dst, inp))
    return out


def _planned_value(key, v):
    if key == "Texture":
        return tp.ue_package(v)
    return _canon_value(v)


class MasterBuilder:
    def __init__(self, ue, spec):
        self.ue, self.spec = ue, spec

    def setp(self, ref, props):
        return self.ue.call("object", "set_properties", {"instance": ref, "values": json.dumps(props)})

    def getp(self, ref, props):
        raw = self.ue.call("object", "get_properties", {"instance": ref, "properties": props})
        return json.loads(raw) if isinstance(raw, str) else (raw or {})

    # -- default textures
    def ensure_textures(self, repo: Path, force: bool, write: bool = True) -> dict:
        """Default textures of the masters: imported when absent (write), properties set, saved; verify = read only."""
        out = {}
        for key, t in sorted(self.spec["default_textures"].items()):
            pkg = texture_path(self.spec, key)
            png = repo / t["file"]
            present = bool(self.ue.call("asset", "exists", {"path": pkg}))
            action = "kept"
            if not write:
                action = "verified" if present else "missing"
                if not present:
                    out[key] = {"asset": pkg, "file": t["file"], "action": action, "ok": False}
                    continue
            elif not present:
                self.ue.call("texture", "import_file", {"folder_path": self.spec["textures_folder"],
                                                        "asset_name": t["asset"], "source_file": str(png)})
                action = "imported"
            want = {"SRGB": t["srgb"], "CompressionSettings": t["compression"]}
            if write and (not present or force):
                self.setp(tp.ue_obj(pkg), want)
            if write and self.ue.call("asset", "is_dirty", {"asset_path": pkg}):
                self.ue.call("asset", "save_assets", {"asset_paths": [pkg]})
            got = self.getp(tp.ue_obj(pkg), ["SRGB", "CompressionSettings"])
            dirty = self.ue.call("asset", "is_dirty", {"asset_path": pkg})
            out[key] = {"asset": pkg, "file": t["file"], "file_sha256": tp.sha256_file(png), "action": action,
                        "properties": got, "dirty": bool(dirty),
                        "ok": all(got.get(k) == v for k, v in want.items()) and not dirty}
        return out

    # -- one master
    def build(self, role: str) -> dict:
        spec = self.spec
        g = GRAPHS[role](spec)
        pkg = master_path(spec, role)
        mat = tp.ue_obj(pkg)
        existed = bool(self.ue.call("asset", "exists", {"path": pkg}))
        cleared = 0
        if existed:
            for e in self.ue.call("material", "get_expressions", {"material_or_function": mat}) or []:
                self.ue.call("material", "delete_expression", {"material_or_function": mat, "expression": e})
                cleared += 1
        else:
            self.ue.call("material", "create_material", {"folder_path": spec["folder"],
                                                         "asset_name": spec["masters"][role]["asset"]})
        refs = {}
        for nid, n in g.nodes.items():
            ref = self.ue.call("material", "add_expression", {
                "material_or_function": mat, "x": n["x"], "y": n["y"],
                "expression_class": {"refPath": "/Script/Engine." + n["class"]}})
            refs[nid] = ref
            if n["props"]:
                props = dict(n["props"])
                if "Texture" in props:
                    props["Texture"] = tp.ue_object_path(props["Texture"])
                self.setp(ref, props)
        for src, out, dst, inp in g.links:
            self.ue.call("material", "connect_expressions", {"from_expression": refs[src], "from_output_name": out,
                                                             "to_expression": refs[dst], "to_input_name": inp})
        for prop, (src, out) in g.outputs.items():
            self.ue.call("material", "connect_to_output", {"expression": refs[src], "output_name": out,
                                                           "material_property": prop})
        self.setp(mat, settings_of(spec, role))
        self.ue.call("material", "recompile", {"material_or_function": mat})
        self.ue.call("asset", "save_assets", {"asset_paths": [pkg]})
        return {"asset": pkg, "existed_before": existed, "expressions_deleted_before_rebuild": cleared,
                "expressions": len(refs), "links": len(g.links), "outputs": sorted(g.outputs)}

    # -- verification against the editor
    def verify(self, role: str) -> dict:
        spec = self.spec
        g = GRAPHS[role](spec)
        pkg = master_path(spec, role)
        mat = tp.ue_obj(pkg)
        checks = {}

        def check(name, passed, measured=None, expected=None):
            checks[name] = {"passed": bool(passed), "measured": measured}
            if expected is not None:
                checks[name]["expected"] = expected

        present = bool(self.ue.call("asset", "exists", {"path": pkg}))
        check("exists", present, pkg)
        if not present:
            return {"asset": pkg, "checks": checks, "passed": False}
        cls = str(self.ue.call("asset", "get_asset_class", {"asset_path": pkg})).rsplit(".", 1)[-1]
        check("class_material", cls == "Material", cls, "Material")
        want_settings = settings_of(spec, role)
        got = self.getp(mat, sorted(want_settings))
        check("settings_opaque_one_sided_usage", all(got.get(k) == v for k, v in want_settings.items()), got,
              want_settings)
        # no World Position Offset and no opacity mask (engine gate: no WPO / Masked in the masters)
        forbidden = {}
        for prop in ("MP_WorldPositionOffset", "MP_OpacityMask", "MP_Opacity"):
            src = self.ue.call("material", "get_property_input", {"material": mat, "material_property": prop}) or {}
            forbidden[prop] = _ref(src.get("expression"))
        check("no_wpo_no_opacity", not any(forbidden.values()), forbidden)
        # graph: every editor expression is matched to the planned node with the same class (from the object name
        # "MaterialExpressionMultiply_12") and the same editor position (the plan gives each node its own x, y);
        # then the planned properties, the links and the outputs are compared through that matching
        exprs = [_ref(e) for e in (self.ue.call("material", "get_expressions", {"material_or_function": mat}) or [])]
        by_slot = {(n["class"], n["x"], n["y"]): nid for nid, n in g.nodes.items()}
        matched, extra, prop_diff = {}, [], {}
        for e in exprs:
            cls_e = re.sub(r"_\d+$", "", str(e).rsplit(":", 1)[-1].rsplit(".", 1)[-1])
            pos = self.getp({"refPath": e}, ["MaterialExpressionEditorX", "MaterialExpressionEditorY"])
            nid = by_slot.get((cls_e, pos.get("MaterialExpressionEditorX"), pos.get("MaterialExpressionEditorY")))
            if nid is None or nid in matched:
                extra.append(e)
                continue
            matched[nid] = e
            keys = sorted(g.nodes[nid]["props"])
            if keys:
                vals = self.getp({"refPath": e}, keys)
                diff = {k: {"editor": _canon_value(vals.get(k)), "plan": _planned_value(k, g.nodes[nid]["props"][k])}
                        for k in keys if _canon_value(vals.get(k)) != _planned_value(k, g.nodes[nid]["props"][k])}
                if diff:
                    prop_diff[nid] = diff
        unmatched = [nid for nid in g.nodes if nid not in matched]
        check("expressions_match_plan", not unmatched and not extra and len(exprs) == len(g.nodes),
              {"expressions": len(exprs), "unmatched_planned": unmatched, "extra_in_editor": extra[:20]}, len(g.nodes))
        check("expression_properties_match_plan", not prop_diff, {k: prop_diff[k] for k in sorted(prop_diff)[:20]})
        # links: read the inputs of every matched destination
        back = {v: k for k, v in matched.items()}
        found_links = set()
        for nid, e in matched.items():
            if g.nodes[nid]["class"] in NO_INPUTS:
                continue
            ins = self.ue.call("material", "get_expression_inputs", {"material_or_function": mat,
                                                                     "expression": {"refPath": e}}) or []
            for item in ins if isinstance(ins, list) else []:
                src = _ref(item.get("expression"))
                if not src:
                    continue
                inp = item.get("input_name") or ""
                found_links.add((back.get(src, "?" + str(src)), item.get("output_name") or "", nid,
                                 "" if inp == "None" else inp))
        planned = reported_links(g)
        check("links_match_plan", found_links == planned,
              {"missing": sorted(planned - found_links)[:20], "unexpected": sorted(found_links - planned)[:20],
               "found": len(found_links)}, len(planned))
        outs = {}
        for prop, (src, out) in g.outputs.items():
            s = self.ue.call("material", "get_property_input", {"material": mat, "material_property": prop}) or {}
            nid = back.get(_ref(s.get("expression")), _ref(s.get("expression")))
            got_out = s.get("output_name") or ""
            if nid in g.nodes and got_out == OUTPUT0.get(g.nodes[nid]["class"]):
                got_out = ""  # output 0 of this class carries a name ("RGB", "EyeAdaptationInverse")
            outs[prop] = {"expression": nid, "output": got_out}
        want_outs = {p: {"expression": s, "output": "" if o == OUTPUT0.get(g.nodes[s]["class"]) else o}
                     for p, (s, o) in g.outputs.items()}
        check("outputs_match_plan", outs == want_outs, outs, want_outs)
        # parameters and the Custom Primitive Data layout
        params = self.ue.call("instance", "list_parameters", {"material": mat}) or []
        have = {}
        for p in params if isinstance(params, list) else []:
            if isinstance(p, dict):
                have[p.get("name")] = str(p.get("type", "")).lower()
        want = expected_parameters(spec, role)
        missing = sorted(k for k in want if k not in have)
        check("parameters_present", not missing, {"listed": sorted(have), "missing": missing}, sorted(want))
        cpd = {}
        for nid, n in g.nodes.items():
            if n["props"].get("bUseCustomPrimitiveData") and nid in matched:
                vals = self.getp({"refPath": matched[nid]}, ["ParameterName", "bUseCustomPrimitiveData",
                                                             "PrimitiveDataIndex"])
                cpd[n["props"]["ParameterName"]] = vals
        want_cpd = {n["props"]["ParameterName"]: {"ParameterName": n["props"]["ParameterName"],
                                                  "bUseCustomPrimitiveData": True,
                                                  "PrimitiveDataIndex": n["props"]["PrimitiveDataIndex"]}
                    for n in g.nodes.values() if n["props"].get("bUseCustomPrimitiveData")}
        check("custom_primitive_data_layout", cpd == want_cpd, cpd, want_cpd)
        dirty = self.ue.call("asset", "is_dirty", {"asset_path": pkg})
        check("saved", not dirty, {"dirty": dirty})
        return {"asset": pkg, "graph_signature": graph_signature(spec, role), "checks": checks,
                "passed": all(c["passed"] for c in checks.values())}


def run(args) -> int:
    spec, spec_path = load_spec(Path(args.repo_root))
    backend = args.backend or os.environ.get("TRIPO_PIPELINE_BACKEND") or "headless"
    if backend != "mcp":
        raise tp.PipelineError("um_masters build/verify needs --backend mcp (live UnrealEditor)", tp.EXIT_USAGE)
    ue = tp.McpUnreal(tp.client_command("TRIPO_PIPELINE_UNREAL_MCP_CMD", args.unreal_mcp_client,
                                        tp.DEFAULT_MCP_CLIENTS / "unreal_mcp.py"))
    b = MasterBuilder(ue, spec)
    report_path = Path(args.report)
    previous = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    report = {"schema": REPORT_SCHEMA, "logic": LOGIC, "spec": SPEC_REL, "spec_sha256": tp.sha256_file(spec_path),
              "command": args.command, "force": bool(getattr(args, "force", False)),
              "status_legend": "masters: технически импортировано at most; knobs and palette: предложено",
              "masters": {}}
    report["default_textures"] = b.ensure_textures(Path(args.repo_root), getattr(args, "force", False),
                                                   write=args.command == "build")
    roles = args.role or list(spec["masters"])
    unknown = [r for r in roles if r not in spec["masters"]]
    if unknown:
        raise ValueError("unknown --role %s (roles: %s)" % (unknown, sorted(spec["masters"])))
    report["roles"] = roles
    for role in roles:
        sig = graph_signature(spec, role)
        prev = ((previous.get("masters") or {}).get(role) or {})
        entry = {}
        if args.command == "build":
            pre = b.verify(role)
            if pre["passed"] and not args.force:
                entry["action"] = "skipped: the editor graph already equals the plan (graph_signature %s)" % sig[:12]
            elif pre["checks"]["exists"]["passed"] and not args.force:
                raise tp.PipelineError("%s exists but differs from the plan (%s); rebuild in place with --force"
                                       % (pre["asset"], sorted(k for k, c in pre["checks"].items() if not c["passed"])),
                                       tp.EXIT_CONFLICT)
            else:
                entry["build"] = b.build(role)
                entry["action"] = "rebuilt in place" if pre["checks"]["exists"]["passed"] else "created"
            entry["previous_graph_signature"] = prev.get("verify", {}).get("graph_signature")
        entry["verify"] = b.verify(role)
        report["masters"][role] = entry
    report["passed"] = all(e["verify"]["passed"] for e in report["masters"].values()) and all(
        t["ok"] for t in (report.get("default_textures") or {}).values())
    report["tool_name_style"] = ue.tool_name_style
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(tp.dump_json(report), encoding="utf-8")
    for role, e in report["masters"].items():
        print("%-12s %-8s %s" % (role, "PASS" if e["verify"]["passed"] else "FAIL", e.get("action", "verify")))
    return tp.EXIT_OK if report["passed"] else tp.EXIT_FAILED


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="um_masters", description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo-root", default=str(REPO))
    ap.add_argument("--backend", choices=tp.BACKENDS, default=None)
    ap.add_argument("--unreal-mcp-client", default=None)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build")
    p.add_argument("--report", required=True)
    p.add_argument("--role", action="append", help="only this master (figure, base_marker, game_layer); repeatable")
    p.add_argument("--force", action="store_true", help="rebuild the graphs in place even if they match the plan")
    p = sub.add_parser("verify")
    p.add_argument("--report", required=True)
    p.add_argument("--role", action="append", help="only this master; repeatable")
    p = sub.add_parser("hex")
    p.add_argument("colours", nargs="+")
    p = sub.add_parser("signature")
    args = ap.parse_args(argv)
    try:
        if args.command == "hex":
            for c in args.colours:
                lin = hex_to_linear(c)
                print("%s -> linear %s  (luminance %.4f)" % (c, lin, luminance(lin[:3])))
            return tp.EXIT_OK
        if args.command == "signature":
            spec, _ = load_spec(Path(args.repo_root))
            for role in spec["masters"]:
                print(role, graph_signature(spec, role))
            return tp.EXIT_OK
        return run(args)
    except ValueError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 2
    except tp.PipelineError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
