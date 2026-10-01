"""ENV-MAPS P5c track W: compile the Custom-node HLSL of our generated materials with the Windows SDK DXC, outside UE.

UE wraps a Custom node's code into a function 'MaterialFloatN CustomExpressionK(FMaterialPixelParameters Parameters,
<inputs>) { <code> }' with one parameter per input pin, typed by what is wired into it. This mirror does the same with a
stub FMaterialPixelParameters (SvPosition) and calls every function from a pixel shader, so syntax / type / undeclared
identifier errors show up in a plain-Python test long before the editor compiles the material (the real UE compile
still happens in the import commandlet). DXC: shutil.which('dxc') or the newest Windows Kits x64 dxc.exe; none -> the
check reports 'skipped'.

  python -B tools/art/env_kit/hlsl_check.py            # all nodes of M_EnvSea / M_EnvWaterfall / M_MapBackdropMoon
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "map_surface"))

OUT_TYPES = {1: "float", 2: "float2", 3: "float3", 4: "float4"}


def find_dxc() -> str | None:
    exe = shutil.which("dxc")
    if exe:
        return exe
    kits = sorted(glob.glob(r"C:/Program Files (x86)/Windows Kits/10/bin/10.*/x64/dxc.exe"))
    return kits[-1] if kits else None


def node_source(name: str, out_dim: int, pins: list[tuple[str, str]], code: str) -> str:
    args = ", ".join(["FMaterialPixelParameters Parameters"] + [f"{t} {n}" for n, t in pins])
    return f"{OUT_TYPES[out_dim]} {name}({args})\n{{\n{code}\n}}\n"


def shader(nodes: list[tuple[str, int, list, str]]) -> str:
    src = ["struct FMaterialPixelParameters { float4 SvPosition; };", ""]
    calls = []
    for name, dim, pins, code in nodes:
        src.append(node_source(name, dim, pins, code))
        args = ["P"] + [{"float": "0.5", "float2": "float2(0.3, 0.6)", "float3": "float3(0.2, 0.4, 0.6)",
                         "float4": "float4(0.2, 0.4, 0.6, 0.8)"}[t] for _, t in pins]
        val = f"{name}({', '.join(args)})"
        calls.append(f"  acc += dot(float4({val}{', 0.0' * (4 - dim)}), float4(1.0, 1.0, 1.0, 1.0));")
    src.append("float4 main(float4 pos : SV_Position) : SV_Target\n{\n  FMaterialPixelParameters P;\n"
               "  P.SvPosition = pos;\n  float acc = 0.0;\n" + "\n".join(calls) + "\n  return float4(acc, 0.0, 0.0, 1.0);\n}\n")
    return "\n".join(src)


def compile_nodes(nodes, dxc: str | None = None) -> dict:
    dxc = dxc or find_dxc()
    if not dxc:
        return {"status": "skipped", "reason": "no dxc"}
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "nodes.hlsl"
        f.write_text(shader(nodes), encoding="utf-8")
        r = subprocess.run([dxc, "-T", "ps_6_0", "-E", "main", "-HV", "2021", str(f), "-Fo", os.devnull],
                           capture_output=True, text=True)
        return {"status": "ok" if r.returncode == 0 else "failed", "returncode": r.returncode,
                "log": (r.stdout + r.stderr)[-4000:]}


# ------------------------------------------------------------------------------------------------ our materials
def _types(pins, table: dict) -> list[tuple[str, str]]:
    return [(p, table[p]) for p in pins]


def sea_nodes() -> list:
    import ue_import_env_ground as IMP
    t = {"UV": "float2", "UV1": "float2", "Time": "float", "VC": "float3", "FoamA": "float4", "FoamB": "float4",
         "NA": "float3", "NB": "float3", "NightEV": "float", "NightSaturation": "float", "NightTint": "float3"}
    t.update({k: "float4" for k in IMP.SEA_VECTOR_DEFAULTS if k != "NightTint"})
    nodes = [("SeaAlbedo", 3, _types(IMP.SEA_CORE_INPUTS, t), IMP.HLSL_SEA_ALBEDO),
             ("SeaEmissive", 3, _types(IMP.SEA_CORE_INPUTS + ("SeaShade",), t), IMP.HLSL_SEA_EMISSIVE),
             ("SeaRoughness", 1, _types(IMP.SEA_CORE_INPUTS + ("SeaShade",), t), IMP.HLSL_SEA_ROUGH),
             ("SeaSpecular", 1, _types(IMP.SEA_CORE_INPUTS + ("SeaShade",), t), IMP.HLSL_SEA_SPECULAR),
             ("SeaNormal", 3, _types(("NA", "NB", "SeaShade", "VC"), t), IMP.HLSL_SEA_NORMAL)]
    for pin, _param, code, tile in IMP.SEA_UV_NODES:
        nodes.append((f"Sea{pin}UV", 2, _types(("UV", "Time", "SeaTile", "SeaFlow", tile), t), code))
    return nodes


def fall_nodes() -> list:
    import ue_import_env_ground as IMP
    t = {"UV": "float2", "Time": "float", "StreakA": "float4", "StreakB": "float4", "NightEV": "float",
         "NightSaturation": "float", "NightTint": "float3", "RippleTileUU": "float", "R": "float3"}
    t.update({k: "float4" for k in IMP.FALL_VECTOR_DEFAULTS if k != "NightTint"})
    core = IMP.FALL_CORE_INPUTS
    return [("FallAlbedo", 3, _types(core, t), IMP.HLSL_FALL_ALBEDO),
            ("FallEmissive", 3, _types(core + ("FallShade",), t), IMP.HLSL_FALL_EMISSIVE),
            ("FallOpacity", 1, _types(core, t), IMP.HLSL_FALL_OPACITY),
            ("FallOpacityMask", 1, _types(core, t), IMP.HLSL_FALL_OPACITY_MASK),
            ("FallRoughness", 1, _types(core + ("FallShade",), t), IMP.HLSL_FALL_ROUGH),
            ("FallRippleUV", 2, _types(("UV", "Time", "FallCard", "FallFlow", "RippleTileUU"), t),
             IMP.HLSL_FALL_RIPPLE_UV),
            ("FallStreakUV1", 2, _types(("UV", "Time", "FallCard", "FallFlow", "FallTex"), t), IMP.HLSL_FALL_STREAK_UV1),
            ("FallStreakUV2", 2, _types(("UV", "Time", "FallCard", "FallFlow", "FallTex"), t), IMP.HLSL_FALL_STREAK_UV2),
            ("FallNormal", 3, _types(("R", "FallShade"), t), IMP.HLSL_FALL_NORMAL),
            ("FallSpecular", 1, _types(("FallShade",), t), IMP.HLSL_FALL_SPECULAR)]


def moon_nodes() -> list:
    import backdrop as bd
    t = {"UV": "float2", "Tint": "float3"}
    t.update({k: "float" for k in bd.MOON_INPUTS[2:]})
    return [("MapBackdropMoon", 3, _types(bd.MOON_INPUTS, t), bd.MOON_HLSL)]


def main() -> int:
    dxc = find_dxc()
    ok = True
    for label, nodes in (("M_EnvSea", sea_nodes()), ("M_EnvWaterfall", fall_nodes()), ("M_MapBackdropMoon", moon_nodes())):
        r = compile_nodes(nodes, dxc)
        print(f"HLSL-CHECK {label} nodes={len(nodes)} {r['status']}" + ("" if r["status"] != "failed" else "\n" + r["log"]))
        ok = ok and r["status"] != "failed"
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
