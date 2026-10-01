"""ENV-MAPS P7 track B (ENV-U15): build M_ConceptPaste, the projection material of the concept paste (out of git).

The concept paste (unreal/Unmatched/Source/Unmatched/S08/S08ConceptPaste.h, profile block "conceptPaste" of
Config/ArtBoards/S08ArtBoardProfiles.json) projects the registered concept plates from the concept camera C0 onto the
depth sheet, the sea plane and the sky cylinder. One shared material does it per pixel:

  /Game/EnvMaps/ConceptPaste/M_ConceptPaste   unlit, BLEND_MASKED (clip 0.5), two-sided; one Custom node (HLSL below):
      world position -> C0 pixel (CamPos / CamRight / CamUp / CamForward / CamTan)
                     -> concept pixel (registration homography rows HRow0..2)
                     -> plate UV (RectA / RectB, concept px [x0, y0, w, h])
      flow    = the sample position moves by a Time-panned value noise (FlowVel.xy px / s, amplitude FlowVel.z px) inside
                the feathered regions FlowRect0 / FlowRect1 (concept px; the painted waterfall and bay surf on the sheet,
                the whole sea plane below FlowMaxZ on the sea layer, never the sky), x the Water masks when UseWater
                (region 0: R waterfall, or B open sea with FlowSea; region 1: G bay surf); amplitude 0 in frozen -Bench
      colour  = lerp(PlateB, PlateA, UseA x feather(FeatherPx) x Mask.g)  (the plates are rectified by cp_bake.py:
                identity homography; RectA [0, 0, 1920, 1080], RectB = the outpainted range [-384, -216, 2688, 1512])
      opacity = lerp(1, lerp(PlateB.a, PlateA.a, the same weight) x Mask.r, AlphaWeight), x OutsideKeep outside plate B, 0 under the cut (Cut = half X,
                half Y, min Z, enabled) and behind C0
      emissive by GradeMode: 0 = colour x GainLinear x EmissiveScale; 1 = Lut(sRGB(colour x GainLinear)) (the inverse
                tonemap LUT measured in the bench: 256 x 1, linear HDR, exposure included); 2 = approximate inverse ACES
                (Narkowicz fit, x 0.6) x EmissiveScale. Calib 1 = the ramp card (-ConceptPasteCalib): a 32 x 18 cell grid
                in viewport UV, cell i -> channel i % 4 (grey, R, G, B), level (i / 4) % 64, emissive CalibMax x (level /
                63)^3 - read back with --lut-from-calib to build the LUT.
  /Game/EnvMaps/ConceptPaste/T_ConceptPaste_InvTonemapLUT   (only with --import-lut <hdr>) the measured LUT
The parameter names are the contract of S08ConceptPasteSpec::Param* (--check compares them with the header) and the
C++ mirror of the projection is S08ConceptPaste::ShaderSample (keep both in step with CONCEPT_HLSL).

Run (the editor must be CLOSED - UnrealEditor-Cmd holds the project; never inside a GPU-measurement window):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/concept_paste/ue_concept_material.py [--import-lut <file.hdr>] [--force]"
      -unattended -nosplash -nullrhi
Plain Python (no UE):
  python -B tools/art/concept_paste/ue_concept_material.py --check
      parameter names vs the header, the shipped conceptPaste blocks (Sarpedon on / Marmoreal off by default, asset
      paths, light budget), the projection mirror vs the P7a design (detail px through C0), grade round trips
  python -B tools/art/concept_paste/ue_concept_material.py --lut-from-calib <frame.png> [--view K1] --out <dir>
      reads a -ConceptPasteCalib bench frame (1 key + profile, concept mode on) and writes lut-table.json +
      T_ConceptPaste_InvTonemapLUT.hdr (cells over the map field are skipped; never tuned by eye)
Idempotent: the material is rebuilt only when its EnvMapsGraphVersion tag differs (or --force). A JSON report is printed
('CONCEPT-MATERIAL-REPORT {...}') and written to <project>/Saved/EnvMaps/concept-material-report.json (or --report).
Status: предложено (the look is measured in UE frames, not here).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
import sys
import time
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
HEADER = REPO / "unreal/Unmatched/Source/Unmatched/S08/S08ConceptPaste.h"
PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
DESIGN = Path("C:/tmp/envmaps-research/p7/proto/design.json")  # P7a stage contract (out of git; optional for --check)

ROOT = "/Game/EnvMaps/ConceptPaste"
MATERIAL_NAME = "M_ConceptPaste"
MATERIAL_PATH = f"{ROOT}/{MATERIAL_NAME}"
LUT_NAME = "T_ConceptPaste_InvTonemapLUT"
LUT_PATH = f"{ROOT}/{LUT_NAME}"
GRAPH_TAG = "EnvMapsGraphVersion"
GRAPH_VERSION = "3"
LUT_SHA_TAG = "EnvMapsSourceSha256"
LUT_SIZE = 256
CALIB_GRID = (32, 18)
CALIB_LEVELS = 64
CALIB_MAX = 16.0  # S08ConceptPasteSpec::DefaultCalibMax

# texture object parameters (the Custom node samples them; the sampler type only matters for the editor's validation of
# the default texture: plates are sRGB colour, the mask / LUT are bound at runtime by the board actor's MIDs)
TEXTURES = ("PlateA", "PlateB", "Mask", "Lut", "Water")
DEFAULT_TEXTURE = "/Engine/EngineResources/WhiteSquareTexture"
VECTORS = {
    "CamPos": (0.0, 1557.046, 2223.692, 0.0), "CamRight": (1.0, 0.0, 0.0, 0.0),
    "CamUp": (0.0, -0.819152, 0.573576, 0.0), "CamForward": (0.0, -0.573576, -0.819152, 0.0),
    "CamTan": (0.315299, 0.177356, 1920.0, 1080.0),
    "HRow0": (1.0, 0.0, 0.0, 0.0), "HRow1": (0.0, 1.0, 0.0, 0.0), "HRow2": (0.0, 0.0, 1.0, 0.0),
    "RectA": (0.0, 0.0, 1920.0, 1080.0), "RectB": (0.0, 0.0, 1920.0, 1080.0), "Cut": (0.0, 0.0, -60.0, 0.0),
    "FlowRect0": (0.0, 0.0, 0.0, 0.0), "FlowRect1": (0.0, 0.0, 0.0, 0.0),
    "FlowVel0": (0.0, 0.0, 0.0, 0.0), "FlowVel1": (0.0, 0.0, 0.0, 0.0),
    "GradeScale": (1.0, 1.0, 1.0, 0.0), "GradePow": (1.0, 1.0, 1.0, 0.0),
}
SCALARS = {"UseA": 0.0, "FeatherPx": 24.0, "AlphaWeight": 1.0, "OutsideKeep": 0.0, "GradeMode": 2.0, "GainLinear": 1.0,
           "EmissiveScale": 1.0, "Calib": 0.0, "CalibMax": CALIB_MAX, "FlowMaxZ": 1.0e6, "UseWater": 0.0, "FlowSea": 0.0,
           "Devignette": 0.0}
FLOW_FEATHER_PX = 8.0  # S08ConceptPasteSpec::FlowFeatherPx
FLOW_NOISE_PX = 16.0   # value-noise cell of the flow offset (concept px)
# Custom node pins in order (WP = absolute world position, VUV = viewport UV, Time = the material time, VSZ = view size)
INPUTS = ("WP", "VUV", "Time", "VSZ") + TEXTURES + tuple(VECTORS) + tuple(SCALARS)

CONCEPT_HLSL = """// ENV-MAPS P7 M_ConceptPaste graph 1 (tools/art/concept_paste/ue_concept_material.py).
// C++ mirror: S08ConceptPaste::ShaderSample (S08ConceptPaste.cpp) - keep both in step.
float3 d = WP - CamPos.xyz;
float z = dot(d, CamForward.xyz);
float zs = max(z, 1e-3);
float sx = dot(d, CamRight.xyz) / zs / CamTan.x;
float sy = dot(d, CamUp.xyz) / zs / CamTan.y;
float2 c0 = float2((sx + 1.0) * 0.5 * CamTan.z, (1.0 - sy) * 0.5 * CamTan.w);
float3 p = float3(c0, 1.0);
float hw = dot(HRow2.xyz, p);
float2 c = float2(dot(HRow0.xyz, p), dot(HRow1.xyz, p)) / hw;
float4 wm = Texture2DSample(Water, WaterSampler, saturate((c - RectB.xy) / RectB.zw));
// painted-water flow (waterfall, bay surf, sea plane): a time-panned value-noise offset of the sample position inside
// the feathered regions (FlowVel.z = amplitude px; 0 in frozen -Bench runs), never above FlowMaxZ (the sky segments)
float2 flow = float2(0.0, 0.0);
[unroll] for (int k = 0; k < 2; ++k) {
  float4 R = (k == 0) ? FlowRect0 : FlowRect1;
  float4 V = (k == 0) ? FlowVel0 : FlowVel1;
  float2 inR = min(c - R.xy, R.xy + R.zw - c);
  float w = saturate(min(inR.x, inR.y) / 8.0) * step(0.5, R.z) * step(WP.z, FlowMaxZ);
  float mk = (k == 0) ? lerp(wm.r, wm.b, FlowSea) : wm.g;
  w *= lerp(1.0, mk, UseWater);
  float2 q = (c - V.xy * Time) / 16.0;
  float2 qi = floor(q);
  float2 qf = frac(q);
  float2 qs = qf * qf * (3.0 - 2.0 * qf);
  float2 n = float2(0.0, 0.0);
  [unroll] for (int ax = 0; ax < 2; ++ax) {
    float2 o = qi + float2(37.0 * ax + 101.0 * k, 59.0 * ax);
    float h00 = frac(sin(dot(o, float2(127.1, 311.7))) * 43758.5453);
    float h10 = frac(sin(dot(o + float2(1.0, 0.0), float2(127.1, 311.7))) * 43758.5453);
    float h01 = frac(sin(dot(o + float2(0.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
    float h11 = frac(sin(dot(o + float2(1.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
    float v = lerp(lerp(h00, h10, qs.x), lerp(h01, h11, qs.x), qs.y);
    n = (ax == 0) ? float2(v, n.y) : float2(n.x, v);
  }
  flow += w * V.z * (n * 2.0 - 1.0);
}
c += flow;
float2 uvA = (c - RectA.xy) / RectA.zw;
float2 uvB = (c - RectB.xy) / RectB.zw;
float2 inA = min(c - RectA.xy, RectA.xy + RectA.zw - c);
float insideB = step(0.0, min(uvB.x, uvB.y)) * step(max(uvB.x, uvB.y), 1.0);
float4 b = Texture2DSample(PlateB, PlateBSampler, saturate(uvB));
float4 a = Texture2DSample(PlateA, PlateASampler, saturate(uvA));
float4 m = Texture2DSample(Mask, MaskSampler, saturate(uvB));
float wA = UseA * saturate(min(inA.x, inA.y) / max(FeatherPx, 1e-3)) * m.g;
float3 col = lerp(b.rgb, a.rgb, wA);
float alpha = lerp(1.0, lerp(b.a, a.a, wA) * m.r, AlphaWeight);
alpha *= lerp(OutsideKeep, 1.0, insideB);
float cut = Cut.w * step(abs(WP.x), Cut.x) * step(abs(WP.y), Cut.y) * step(Cut.z, WP.z);
alpha *= (1.0 - saturate(cut)) * step(1e-3, z);
float3 t = max(col * GainLinear, 0.0);
float3 e = t * EmissiveScale;
if (Calib > 0.5) {
  float2 cell = min(floor(saturate(VUV) * float2(32.0, 18.0)), float2(31.0, 17.0));
  float idx = cell.y * 32.0 + cell.x;
  float ch = fmod(idx, 4.0);
  float lvl = fmod(floor(idx / 4.0), 64.0);
  float v = CalibMax * pow(lvl / 63.0, 3.0);
  e = (ch < 0.5) ? float3(v, v, v) : ((ch < 1.5) ? float3(v, 0.0, 0.0) : ((ch < 2.5) ? float3(0.0, v, 0.0) : float3(0.0, 0.0, v)));
} else if (GradeMode > 0.5 && GradeMode < 1.5) {
  float3 tc = saturate(t);
  float3 s = lerp(tc * 12.92, 1.055 * pow(max(tc, 1e-6), 1.0 / 2.4) - 0.055, step(0.0031308, tc));
  float3 lu = (s * 255.0 + 0.5) / 256.0;
  e = float3(Texture2DSampleLevel(Lut, LutSampler, float2(lu.r, 0.5), 0).r,
             Texture2DSampleLevel(Lut, LutSampler, float2(lu.g, 0.5), 0).g,
             Texture2DSampleLevel(Lut, LutSampler, float2(lu.b, 0.5), 0).b);
} else if (GradeMode > 1.5) {
  // graph 3: the measured fit of the engine's tone curve (P7 tune selfcal: display = sRGB(ACES(k x E)^p) per channel):
  // GradeScale = 1 / k, GradePow = 1 / p; (1, 1, 1) = the plain approximate inverse ACES
  float3 y = min(pow(max(t, 0.0), GradePow.rgb), 0.98);
  float3 qa = 2.51 - y * 2.43;
  float3 qb = 0.03 - y * 0.59;
  float3 qc = -y * 0.14;
  float3 x = (-qb + sqrt(max(qb * qb - 4.0 * qa * qc, 0.0))) / (2.0 * qa);
  e = x / 0.6 * EmissiveScale * GradeScale.rgb;
}
// graph 2 (P7 tune): undo the engine's cosine-fourth vignette (PostProcessCommon.ush ComputeVignetteMask / VignetteSpace,
// intensity Devignette = the view's VignetteIntensity) so the painted layer displays the plate in the screen corners too
// (measured at C0: -19 % .. -31 % display at r 0.9 .. 1.2 without it); the ramp card stays raw
if (Devignette > 0.0 && Calib < 0.5) {
  float asp = VSZ.y / max(VSZ.x, 1.0);
  float2 vp = (saturate(VUV) * 2.0 - 1.0) * float2(1.0, asp) * (sqrt(2.0) / sqrt(1.0 + asp * asp)) * Devignette;
  float t2 = dot(vp, vp);
  e *= (t2 + 1.0) * (t2 + 1.0);
}
return float4(e, alpha);
"""


# ---------------------------------------------------------------------------------------------------- plain-Python mirror
def _rot_axes(pitch_deg: float, yaw_deg: float):
    """FRotationMatrix(FRotator(pitch, yaw, 0)) axes X (forward), Y (right), Z (up)."""
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    cp, sp, cy, sy = math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    fwd = (cp * cy, cp * sy, sp)
    right = (-sy, cy, 0.0)
    up = (-sp * cy, -sp * sy, cp)
    return fwd, right, up


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


class Camera:
    """FS08ConceptCamera (S08ConceptPaste.h): looks at focus from distance along FRotator(pitch, yaw, 0)."""

    def __init__(self, block: dict | None = None):
        c = (block or {}).get("camera", {})
        self.dist = float(c.get("distanceUU", 2714.626))
        self.focus = tuple(float(v) for v in c.get("focus", (0, 0, 0)))
        self.pitch = float(c.get("pitch", -55))
        self.yaw = float(c.get("yaw", -90))
        self.hfov = float(c.get("hfov", 35))
        self.w, self.h = (int(v) for v in c.get("sizePx", (1920, 1080)))
        self.fwd, self.right, self.up = _rot_axes(self.pitch, self.yaw)
        self.pos = tuple(f - d * self.dist for f, d in zip(self.focus, self.fwd))
        self.tan_h = math.tan(math.radians(self.hfov / 2))
        self.tan_v = self.tan_h * self.h / self.w

    def project(self, world):
        d = tuple(w - p for w, p in zip(world, self.pos))
        z = _dot(d, self.fwd)
        if z <= 1e-6:
            return None
        sx = _dot(d, self.right) / z / self.tan_h
        sy = _dot(d, self.up) / z / self.tan_v
        return ((sx + 1) * 0.5 * self.w, (1 - sy) * 0.5 * self.h)


def homography_apply(h, px):
    w = h[2][0] * px[0] + h[2][1] * px[1] + h[2][2]
    return ((h[0][0] * px[0] + h[0][1] * px[1] + h[0][2]) / w, (h[1][0] * px[0] + h[1][1] * px[1] + h[1][2]) / w)


def shader_sample(block: dict, frame_half, world, sea: bool = False):
    """The projection / opacity part of CONCEPT_HLSL for one world point (S08ConceptPaste::ShaderSample)."""
    cam = Camera(block)
    h = block.get("homography", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    rect_a = block.get("rectA", [0, 0, 1920, 1080])
    rect_b = block.get("rectB", [0, 0, 1920, 1080])
    under = float(block.get("cut", {}).get("underFrameUU", 2.0))
    min_z = float(block.get("cut", {}).get("minZ", -60.0))
    c0 = cam.project(world)
    if c0 is None:
        return {"inFront": False}
    c = homography_apply(h, c0)
    uv_a = ((c[0] - rect_a[0]) / rect_a[2], (c[1] - rect_a[1]) / rect_a[3])
    uv_b = ((c[0] - rect_b[0]) / rect_b[2], (c[1] - rect_b[1]) / rect_b[3])
    in_a = min(c[0] - rect_a[0], rect_a[0] + rect_a[2] - c[0], c[1] - rect_a[1], rect_a[1] + rect_a[3] - c[1])
    cut_x, cut_y = frame_half[0] - under, frame_half[1] - under
    cut = (not sea) and abs(world[0]) < cut_x and abs(world[1]) < cut_y and world[2] > min_z
    flow_w = []
    regions = ([{"rectPx": rect_b}] if block.get("flow", {}).get("sea") else []) if sea else block.get("flow", {}).get("regions", [])
    for reg in regions:
        r = reg["rectPx"]
        inside = min(c[0] - r[0], r[0] + r[2] - c[0], c[1] - r[1], r[1] + r[3] - c[1])
        gate = (world[2] <= float(block.get("sea", {}).get("zUU", -300)) + 1.0) if sea else True
        flow_w.append(max(0.0, min(1.0, inside / FLOW_FEATHER_PX)) if gate else 0.0)
    return {"flowWeights": flow_w,"inFront": True, "c0": c0, "concept": c, "uvA": uv_a, "uvB": uv_b,
            "weightA": 0.0 if sea else max(0.0, min(1.0, in_a / max(float(block.get("featherPx", 24)), 1e-3))),
            "insideB": 0 <= uv_b[0] <= 1 and 0 <= uv_b[1] <= 1, "cut": cut}


def aces(x: float) -> float:
    l = x * 0.6
    return max(0.0, min(1.0, (l * (2.51 * l + 0.03)) / (l * (2.43 * l + 0.59) + 0.14)))


def inverse_aces(y: float) -> float:
    y = max(0.0, min(0.98, y))
    a, b, c = 2.51 - y * 2.43, 0.03 - y * 0.59, -y * 0.14
    return (-b + math.sqrt(max(b * b - 4 * a * c, 0.0))) / (2 * a) / 0.6


def srgb_encode(v: float) -> float:
    v = max(0.0, min(1.0, v))
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def srgb_decode(s: float) -> float:
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def calib_cell(cx: int, cy: int):
    """(channel 0 grey / 1 R / 2 G / 3 B, emissive value) of a ramp cell (CONCEPT_HLSL Calib branch)."""
    idx = cy * CALIB_GRID[0] + cx
    level = (idx // 4) % CALIB_LEVELS
    return idx % 4, CALIB_MAX * (level / (CALIB_LEVELS - 1)) ** 3


# ---------------------------------------------------------------------------------------------------- LUT
def lut_from_samples(samples: list[tuple[int, float, float]]) -> list[list[float]]:
    """Inverse tonemap per channel from measured (channel 1..3 or 0 = grey, emissive, display sRGB 0..1) samples:
    for every display level k / 255 the emissive that renders it (monotone piecewise-linear interpolation; a grey sample
    counts for all three channels). Returns LUT_SIZE rows of [r, g, b] emissive."""
    per = {0: [], 1: [], 2: []}
    for ch, emissive, display in samples:
        for c in ((0, 1, 2) if ch == 0 else (ch - 1,)):
            per[c].append((display, emissive))
    out = [[0.0, 0.0, 0.0] for _ in range(LUT_SIZE)]
    for c, pts in per.items():
        pts = sorted(pts)
        mono, best = [], -1.0
        for d, e in pts:  # keep a monotone curve (display and emissive both non-decreasing)
            if e >= best:
                mono.append((d, e))
                best = e
        if len(mono) < 2:
            raise ValueError(f"channel {c}: fewer than 2 usable samples")
        for k in range(LUT_SIZE):
            t = k / (LUT_SIZE - 1)
            if t <= mono[0][0]:
                v = mono[0][1] * (t / mono[0][0] if mono[0][0] > 0 else 0.0)
            elif t >= mono[-1][0]:
                v = mono[-1][1]
            else:
                for (d0, e0), (d1, e1) in zip(mono, mono[1:]):
                    if d0 <= t <= d1:
                        v = e0 if d1 <= d0 else e0 + (e1 - e0) * (t - d0) / (d1 - d0)
                        break
            out[k][c] = max(0.0, v)
    return out


def write_hdr(path: Path, rows: list[list[float]]) -> None:
    """Radiance RGBE, 1 x N (flat scanline), the LUT texture source."""
    data = bytearray()
    for r, g, b in rows:
        v = max(r, g, b)
        if v < 1e-32:
            data += bytes(4)
        else:
            m, e = math.frexp(v)
            s = m * 256.0 / v
            data += bytes((int(r * s), int(g * s), int(b * s), e + 128))
    header = f"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X {len(rows)}\n".encode("ascii")
    path.write_bytes(header + bytes(data))


def frame_field_box(view: str, width: int, height: int, profiles: dict) -> tuple[float, float, float, float]:
    """Screen box (px) of the map field + frame-002 (+ 30 uu margin, 12.4 uu frame top) in a standard view."""
    board = next(b for b in profiles["boards"] if b["id"] == "sarpedon-original")
    m = board["mapImage"]
    hx = m["srcSize"][0] * m["uuPerPx"] / 2 + m.get("frameUU", 24) + 30
    hy = m["srcSize"][1] * m["uuPerPx"] / 2 + m.get("frameUU", 24) + 30
    fit = 1872.156
    dist = {"K1": fit * board.get("k1DistanceMul", 1.0), "K1x0.65": fit / 0.65, "C0": 2714.626}[view]
    cam = Camera({"camera": {"distanceUU": dist, "sizePx": [width, height]}})
    pts = [cam.project((sx * hx, sy * hy, z)) for sx in (-1, 1) for sy in (-1, 1) for z in (-10.0, 12.4)]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def lut_from_calib(frame: Path, view: str, out_dir: Path) -> dict:
    import numpy as np  # plain Python only
    from PIL import Image

    img = np.asarray(Image.open(frame).convert("RGB")).astype(np.float64) / 255.0
    h, w = img.shape[:2]
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    x0, y0, x1, y1 = frame_field_box(view, w, h, profiles)
    gx, gy = CALIB_GRID
    samples, used, skipped = [], 0, 0
    for cy in range(gy):
        for cx in range(gx):
            a0, a1 = int((cx + 0.25) * w / gx), int((cx + 0.75) * w / gx)
            b0, b1 = int((cy + 0.25) * h / gy), int((cy + 0.75) * h / gy)
            if a1 > x0 and a0 < x1 and b1 > y0 and b0 < y1:
                skipped += 1  # the map field / frame / figures: never a ramp pixel
                continue
            patch = img[b0:b1, a0:a1].reshape(-1, 3)
            med = np.median(patch, axis=0)
            spread = np.percentile(patch, 90, axis=0) - np.percentile(patch, 10, axis=0)
            ch, emissive = calib_cell(cx, cy)
            others = [i for i in range(3) if ch != 0 and i != ch - 1]
            consistent = spread.max() < 0.03 and (
                (ch == 0 and med.max() - med.min() < 0.03) or (ch != 0 and all(med[i] < 0.03 for i in others)))
            if not consistent:  # a 3D detail / fx / label over the cell
                skipped += 1
                continue
            display = float(med.mean()) if ch == 0 else float(med[ch - 1])
            samples.append((ch, emissive, display))
            used += 1
    rows = lut_from_samples(samples)
    out_dir.mkdir(parents=True, exist_ok=True)
    table = {"schema": "unmatched.concept-paste.lut/1", "frame": str(frame), "view": view, "size": [w, h],
             "fieldBoxPx": [round(v, 1) for v in (x0, y0, x1, y1)], "cellsUsed": used, "cellsSkipped": skipped,
             "calibMax": CALIB_MAX, "samples": [[c, round(e, 6), round(d, 5)] for c, e, d in samples],
             "lut": [[round(v, 6) for v in row] for row in rows]}
    (out_dir / "lut-table.json").write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
    write_hdr(out_dir / f"{LUT_NAME}.hdr", rows)
    return {"cellsUsed": used, "cellsSkipped": skipped, "hdr": str(out_dir / f"{LUT_NAME}.hdr")}


# ---------------------------------------------------------------------------------------------------- --check
def header_params() -> dict:
    text = HEADER.read_text(encoding="utf-8")
    return dict(re.findall(r'inline const TCHAR\* const Param(\w+) = TEXT\("(\w+)"\);', text))


def check() -> tuple[dict, list[str]]:
    errors: list[str] = []
    report: dict = {}
    params = header_params()
    want = set(TEXTURES) | set(VECTORS) | set(SCALARS)
    got = set(params.values())
    if got != want:
        errors.append(f"parameter names differ from S08ConceptPaste.h: missing in header {sorted(want - got)}, "
                      f"missing here {sorted(got - want)}")
    report["params"] = sorted(got)
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    lights = profiles["lightProfiles"]
    blocks = {}
    for b in profiles["boards"]:
        cp = b.get("conceptPaste")
        if cp is None:
            continue
        if b.get("surface") != "map-image":
            errors.append(f"{b['id']}: conceptPaste on a {b.get('surface')} board")
        blocks[b["id"]] = cp
        for key in ("material", "sheetMesh", "plateA", "plateB", "seaPlate", "mask", "lut"):
            path = cp.get(key)
            if path and (not path.startswith("/Game/EnvMaps/") or path.startswith("/Game/EnvMaps/Data/") or "." in path):
                errors.append(f"{b['id']}: conceptPaste.{key} {path} is not a cooked /Game/EnvMaps package path")
        points = len(lights[b["light"]].get("points", [])) + len(cp.get("lights", []))
        if points > 6:
            errors.append(f"{b['id']}: profile points + concept lights = {points} > 6")
        if cp.get("lights") and "layoutLights" not in cp.get("hide", []):
            errors.append(f"{b['id']}: concept lights without hiding the layout lights")
    if blocks.get("sarpedon-original", {}).get("default") != "on":
        errors.append("sarpedon-original: conceptPaste must be ON by default (ENV-U15)")
    if blocks.get("marmoreal-original", {}).get("default") != "off":
        errors.append("marmoreal-original: conceptPaste must be present and OFF by default (accepted look)")
    for b in profiles["boards"]:
        if b.get("surface") != "map-image" and "conceptPaste" in b:
            errors.append(f"{b['id']}: grid profile with conceptPaste")
    report["blocks"] = {k: {"default": v.get("default"), "variant": v.get("variant"), "offVariant": v.get("offVariant"),
                            "lights": len(v.get("lights", [])), "hide": v.get("hide", [])} for k, v in blocks.items()}
    # the projection mirror: the C0 centre, the cut, and every P7a detail back on its design pixel
    sar = blocks.get("sarpedon-original")
    if sar:
        frame_half = (445.6667 + 24, 288.6667 + 24)
        identity = dict(sar, homography=[[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        centre = shader_sample(identity, frame_half, (0.0, 0.0, 0.0))
        if abs(centre["c0"][0] - 960) > 1e-6 or abs(centre["c0"][1] - 540) > 1e-6:
            errors.append(f"C0 centre projects to {centre['c0']}")
        if not centre["cut"] or shader_sample(sar, frame_half, (0.0, 0.0, -300.0), sea=True)["cut"]:
            errors.append("cut: the map centre must be cut on the sheet and never on the sea layer")
        edge = shader_sample(sar, frame_half, (467.0, 0.0, -3.0))
        out = shader_sample(sar, frame_half, (468.5, 0.0, -3.0))
        if not edge["cut"] or out["cut"]:
            errors.append("cut: must end 2 uu under the frame-002 outer foot (469.67)")
        if DESIGN.exists():
            design = json.loads(DESIGN.read_text(encoding="utf-8"))
            worst = 0.0
            for e in design["5_elements"]["keep_3D_animated"]:
                px = Camera(sar).project(e["world"])
                worst = max(worst, math.hypot(px[0] - e["px"][0], px[1] - e["px"][1]))
            report["designDetailsMaxPx"] = round(worst, 3)
            if worst > 0.1:
                errors.append(f"C0 of the block puts a design detail {worst:.3f} px off its design pixel")
            # the registration homography is baked into the texels by cp_bake.py: the block keeps identity
            h = sar.get("homography", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
            if any(abs(h[r][c] - (1.0 if r == c else 0.0)) > 1e-12 for r in range(3) for c in range(3)):
                errors.append("sarpedon homography must be identity (cp_bake.py bakes the registration)")
        else:
            report["designDetailsMaxPx"] = "design.json not found (out of git): skipped"
        corner = shader_sample(sar, frame_half, Camera(sar).pos[:2] + (-300.0,))  # straight below C0: in front
        report["belowC0InFront"] = corner.get("inFront")
    # grade round trips
    worst = max(abs(aces(inverse_aces(y)) - y) for y in [i / 100 for i in range(0, 98)])
    report["acesRoundTripMax"] = round(worst, 6)
    if worst > 1e-4:
        errors.append(f"inverse ACES round trip {worst}")
    synthetic = [(ch, e, srgb_encode(aces(e))) for cy in range(18) for cx in range(32)
                 for ch, e in [calib_cell(cx, cy)]]
    lut = lut_from_samples(synthetic)
    lut_err = max(abs(srgb_encode(aces(lut[k][0])) - k / 255) for k in range(5, 240))
    report["lutRoundTripMax"] = round(lut_err, 5)
    if lut_err > 0.01:
        errors.append(f"LUT from a synthetic ACES ramp misses by {lut_err:.4f} (display)")
    return report, errors


# ---------------------------------------------------------------------------------------------------- UE
def _expr(material, cls, x, y):
    node = u.MaterialEditingLibrary.create_material_expression(material, cls, x, y)
    if node is None:
        raise RuntimeError(f"could not create {cls}")
    return node


def _connect(src, out, dst, inp):
    if not u.MaterialEditingLibrary.connect_material_expressions(src, out, dst, inp):
        raise RuntimeError(f"could not connect {src.get_name()}.{out or '<0>'} -> {dst.get_name()}.{inp}")


def _connect_float4(material, vector_param, custom, pin: str, y: int) -> None:
    """The Custom node reads .w / .zw of the vector parameters: connect all four channels. The first output of a
    VectorParameter is RGB (float3); an engine with the RGBA output takes it directly, else Append(RGB, A)."""
    if u.MaterialEditingLibrary.connect_material_expressions(vector_param, "RGBA", custom, pin):
        return
    append = _expr(material, u.MaterialExpressionAppendVector, -1100, y)
    _connect(vector_param, "RGB", append, "A")
    _connect(vector_param, "A", append, "B")
    _connect(append, "", custom, pin)


def build_material(force: bool) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    material = u.load_asset(MATERIAL_PATH) if eal.does_asset_exist(MATERIAL_PATH) else None
    if material is not None and not force and eal.get_metadata_tag(material, GRAPH_TAG) == GRAPH_VERSION:
        return {"action": "unchanged", "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION}
    action = "rebuilt" if material is not None else "created"
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(MATERIAL_NAME, ROOT, u.Material, u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {MATERIAL_PATH}")
    mel.delete_all_material_expressions(material)
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_MASKED)
    material.set_editor_property("two_sided", True)
    material.set_editor_property("opacity_mask_clip_value", 0.5)
    custom = _expr(material, u.MaterialExpressionCustom, -400, 0)
    custom.set_editor_property("description", "ConceptPaste")
    custom.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT4)
    pins = []
    for name in INPUTS:
        ci = u.CustomInput()
        ci.set_editor_property("input_name", name)
        pins.append(ci)
    custom.set_editor_property("inputs", pins)
    custom.set_editor_property("code", CONCEPT_HLSL)
    wp = _expr(material, u.MaterialExpressionWorldPosition, -1400, -600)
    _connect(wp, "", custom, "WP")
    time_node = _expr(material, u.MaterialExpressionTime, -1400, -700)
    _connect(time_node, "", custom, "Time")
    screen = _expr(material, u.MaterialExpressionScreenPosition, -1400, -500)
    _connect(screen, "ViewportUV", custom, "VUV")
    view_size = _expr(material, u.MaterialExpressionViewSize, -1400, -800)
    _connect(view_size, "", custom, "VSZ")
    white = u.load_asset(DEFAULT_TEXTURE)
    y = -400
    for name in TEXTURES:
        node = _expr(material, u.MaterialExpressionTextureObjectParameter, -1400, y)
        node.set_editor_property("parameter_name", name)
        if white is not None:
            node.set_editor_property("texture", white)
        _connect(node, "", custom, name)
        y += 120
    for name, value in VECTORS.items():
        node = _expr(material, u.MaterialExpressionVectorParameter, -1400, y)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", u.LinearColor(*[float(v) for v in value]))
        _connect_float4(material, node, custom, name, y)
        y += 110
    for name, value in SCALARS.items():
        node = _expr(material, u.MaterialExpressionScalarParameter, -1400, y)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", float(value))
        _connect(node, "", custom, name)
        y += 90
    rgb = _expr(material, u.MaterialExpressionComponentMask, -150, -60)
    for ch, on in (("r", True), ("g", True), ("b", True), ("a", False)):
        rgb.set_editor_property(ch, on)
    _connect(custom, "", rgb, "")
    alpha = _expr(material, u.MaterialExpressionComponentMask, -150, 80)
    for ch, on in (("r", False), ("g", False), ("b", False), ("a", True)):
        alpha.set_editor_property(ch, on)
    _connect(custom, "", alpha, "")
    mel.connect_material_property(rgb, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(alpha, "", u.MaterialProperty.MP_OPACITY_MASK)
    mel.layout_material_expressions(material)
    mel.recompile_material(material)
    eal.set_metadata_tag(material, GRAPH_TAG, GRAPH_VERSION)
    if not eal.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {MATERIAL_PATH}")
    got = {"vector": sorted(str(n) for n in mel.get_vector_parameter_names(material)),
           "scalar": sorted(str(n) for n in mel.get_scalar_parameter_names(material)),
           "texture": sorted(str(n) for n in mel.get_texture_parameter_names(material))}
    missing = [n for n in VECTORS if n not in got["vector"]] + [n for n in SCALARS if n not in got["scalar"]] + \
              [n for n in TEXTURES if n not in got["texture"]]
    if missing:
        raise RuntimeError(f"{MATERIAL_PATH}: parameters missing after the build: {missing}")
    return {"action": action, "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION, "params": got,
            "expressions": int(mel.get_num_material_expressions(material)), "blend": "masked", "shading": "unlit",
            "twoSided": True}


def import_lut(hdr: Path, force: bool) -> dict:
    import hashlib

    eal = u.EditorAssetLibrary
    sha = hashlib.sha256(hdr.read_bytes()).hexdigest()
    texture = u.load_asset(LUT_PATH) if eal.does_asset_exist(LUT_PATH) else None
    if texture is not None and not force and eal.get_metadata_tag(texture, LUT_SHA_TAG) == sha:
        return {"action": "unchanged", "path": LUT_PATH, "sha256": sha}
    task = u.AssetImportTask()
    task.filename = str(hdr)
    task.destination_path = ROOT
    task.destination_name = LUT_NAME
    task.automated = True
    task.replace_existing = True
    task.save = False
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = u.load_asset(LUT_PATH)
    if texture is None:
        raise RuntimeError(f"import of {hdr} did not produce {LUT_PATH}")
    for key, value in (("compression_settings", u.TextureCompressionSettings.TC_HDR), ("srgb", False),
                       ("mip_gen_settings", u.TextureMipGenSettings.TMGS_NO_MIPMAPS),
                       ("filter", u.TextureFilter.TF_BILINEAR), ("address_x", u.TextureAddress.TA_CLAMP),
                       ("address_y", u.TextureAddress.TA_CLAMP), ("never_stream", True)):
        texture.set_editor_property(key, value)
    eal.set_metadata_tag(texture, LUT_SHA_TAG, sha)
    if not eal.save_loaded_asset(texture, False):
        raise RuntimeError(f"could not save {LUT_PATH}")
    return {"action": "imported", "path": LUT_PATH, "sha256": sha, "sizeX": int(texture.blueprint_get_size_x())}


# ---------------------------------------------------------------------------------------------------- entry
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="plain-Python contract checks (no UE)")
    parser.add_argument("--lut-from-calib", default=None, help="a -ConceptPasteCalib frame (png) -> LUT table + .hdr")
    parser.add_argument("--view", default="K1", choices=("K1", "K1x0.65", "C0"), help="view of the calibration frame")
    parser.add_argument("--out", default=None, help="output directory of --lut-from-calib")
    parser.add_argument("--import-lut", default=None, help="(UE) import this .hdr as the LUT texture")
    parser.add_argument("--report", default=None, help="report JSON path")
    parser.add_argument("--force", action="store_true", help="rebuild / re-import even when the tags are current")
    args = parser.parse_args(argv)
    started = time.time()
    report: dict = {"schema": "unmatched.concept-paste-material/1", "tool": "tools/art/concept_paste/ue_concept_material.py",
                    "material": MATERIAL_PATH, "graphVersion": GRAPH_VERSION}
    ok = True
    if args.lut_from_calib:
        out = Path(args.out) if args.out else Path("C:/tmp/envmaps-research/p7/lut")
        report["mode"] = "lut-from-calib"
        report["lut"] = lut_from_calib(Path(args.lut_from_calib), args.view, out)
    elif args.check or u is None:
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
        if args.import_lut:
            try:
                report["lut"] = import_lut(Path(args.import_lut), args.force)
            except Exception as exc:
                report["lut"] = {"action": "failed", "error": str(exc)}
                ok = False
        report["engine"] = str(u.SystemLibrary.get_engine_version())
    report["ok"] = ok
    report["seconds"] = round(time.time() - started, 2)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    report_path = Path(args.report) if args.report else (
        Path(u.Paths.project_saved_dir()) / "EnvMaps" / "concept-material-report.json" if u is not None else None)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text + "\n", encoding="utf-8")
    print("CONCEPT-MATERIAL-REPORT " + json.dumps(report, ensure_ascii=False))
    print(f"CONCEPT-MATERIAL-RESULT {'ok' if ok else 'failed'} mode={report['mode']}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        u.log_error(f"ue_concept_material.py failed (code {code}); see the CONCEPT-MATERIAL-REPORT line")
