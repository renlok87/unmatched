"""VS-6 F3 (visual chat): build the death and ability FX assets of FX-26 (embers), FX-30 (Medusa's vortex) and FX-32
(Arthur's arc).

    python tools/art/fx/fx_ability.py            # one headless editor run (the editor of THIS checkout must be closed)
    python tools/art/fx/fx_ability.py --check    # plain Python: the plan (tokens, grade, sources, the vortex mesh)

One UnrealEditor-Cmd process (tools/art/de010 run_editor) runs tools/art/fx/ue_fx_ability.py:
  * T_FX_MedusaVortex_4x4 (the accepted FX-29 mask) and T_FX_ArthurArc_4x4 (the accepted FX-31 mask): BC7, sRGB off,
    Effects group, mips, clamp (the hit-star recipe of F2);
  * SM_FX_VortexRings: two horizontal quads at 0.45 / 0.7 of a 100 uu figure (1.4 H and 1.12 H across; the upper
    one's UV shifted by +2 in U - the shader mirrors it, so the two rings turn against each other); imported from the
    OBJ this script writes (VORTEX_OBJ);
  * M_FX_AbilityPrint (no depth test; the arc) and M_FX_AbilityPrintDepth (depth test on; the vortex and the embers):
    one Custom HLSL, mode 0 the FX-31 arc around the cell pivot on a camera quad, tilted by the bound user parameter
    ArcTilt; mode 1 the FX-29 vortex flipbook on the mesh UV (16 x 37.5 ms by the particle age); mode 2 the FX-26
    embers - <= 40 rhomb chips drawn on a camera quad from the dissolve front (FrontHeight, DissolveMs, TeamScreenColor
    bound user parameters); the inverse tone curve of M_FX_Print with the profile grade baked;
  * MI_FX_Arc / MI_FX_Vortex / MI_FX_Ember re-parented onto them (fx_import.py no longer owns them, ВР-VS6-22);
  * NS_FX_ArthurArc (0.4 s), NS_FX_MedusaVortex (0.6 s), NS_FX_AshEmbers (0.6 s): the NS_FX_Dust recipe (DirectionalBurst
    duplicate, one still particle, CPU, deterministic, seed CRC32 of the name, fixed bounds, NET_UM_Combat, pool prime
    3, a local-space mesh carrier) + the user parameters bound to the material (US08FxAuthoringLibrary::
    BindUserMaterialParameters, ВР-VS6-23).
Colours: the linear values of docs/unreal/contracts/hud/hud-style-tokens.json (no literals). Report:
C:/tmp/visual/vs6-f3/fx-ability.json (+ the editor log next to it).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "art" / "de010"))
sys.path.insert(0, str(REPO / "tools" / "art" / "material_library"))

WORK = Path("C:/tmp/visual/vs6-f3")
VORTEX = REPO / "art/imagegen/fx-vortex-codex/vector/T_FX_MedusaVortex_4x4.png"
ARC = REPO / "art/imagegen/fx-arc-codex/vector/T_FX_ArthurArc_4x4.png"
VORTEX_OBJ = WORK / "SM_FX_VortexRings.obj"
TOKENS_USED = ("fx.gold", "card.glyph", "mark.keyline", "fx.stone", "fx.stone.2", "accent.warm", "team.p1.screen",
               "team.p2.screen")
# the vortex rings of a 100 uu figure (FX-30): the lower ring 1.4 H across at 0.45 H, the upper 1.12 H at 0.7 H
RINGS = ((45.0, 70.0, 0.0), (70.0, 56.0, 2.0))  # (height uu, half side uu, U offset)


def vortex_obj() -> str:
    """Two quads in the UE frame written as OBJ. The UE 5.8 OBJ import keeps the axes but flips Y (measured on the first
    import: OBJ (x, y, z) -> UE (x, -y, z)), so a UE point (X, Y, Z) is written as (X, -Y, Z). The texture is seen from
    above unmirrored: PNG right = UE +Y, PNG down = UE -X (S08AbilityFx.h)."""
    lines = ["# VS-6 F3 FX-30 SM_FX_VortexRings (tools/art/fx/fx_ability.py)", "o SM_FX_VortexRings"]
    vt = []
    n = 0
    faces = []
    for height, half, uoff in RINGS:
        corners = []
        for ux, vy in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)):
            # PNG (u right, v down) -> UE (X = -(v - 0.5) * 2h, Y = (u - 0.5) * 2h)
            x_ue = -(vy - 0.5) * 2.0 * half
            y_ue = (ux - 0.5) * 2.0 * half
            corners.append((x_ue, y_ue, height, ux + uoff, 1.0 - vy))
        for x_ue, y_ue, z_ue, u, v in corners:
            lines.append("v %.4f %.4f %.4f" % (x_ue, -y_ue, z_ue))
            vt.append("vt %.4f %.4f" % (u, v))
        faces.append((n + 1, n + 2, n + 3, n + 4))
        n += 4
    lines += vt
    lines.append("vn 0 1 0")
    lines.append("s off")
    for a, b, c, d in faces:
        lines.append("f %d/%d/1 %d/%d/1 %d/%d/1" % (a, a, c, c, b, b))
        lines.append("f %d/%d/1 %d/%d/1 %d/%d/1" % (a, a, d, d, c, c))
    return "\n".join(lines) + "\n"


def plan() -> dict:
    import fx_field
    import fx_import
    tok = fx_import.tokens()
    lin = {name: fx_import.linear_color(tok[name]) for name in TOKENS_USED}
    grade = fx_field.plan()["grade"]
    for png in (VORTEX, ARC):
        if not png.is_file():
            raise SystemExit("missing %s" % png)
    return {"tokens": lin, "grade": grade, "rings": RINGS,
            "vortex": {"png": str(VORTEX), "sha256": hashlib.sha256(VORTEX.read_bytes()).hexdigest()},
            "arc": {"png": str(ARC), "sha256": hashlib.sha256(ARC.read_bytes()).hexdigest()},
            "vortexObj": str(VORTEX_OBJ)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    p = plan()
    if not (HERE / "ue_fx_ability.py").is_file():
        raise SystemExit("missing ue_fx_ability.py")
    WORK.mkdir(parents=True, exist_ok=True)
    VORTEX_OBJ.write_text(vortex_obj(), encoding="utf-8", newline="\n")
    if a.check:
        print(json.dumps(p, indent=1))
        print("FX_ABILITY_CHECK PASS")
        return 0
    import de010
    out = WORK / "fx-ability.json"
    data = de010.run_editor(HERE / "ue_fx_ability.py", {"out": str(out), **p}, WORK, "fx-ability", timeout=1800)
    print(json.dumps({k: data.get(k) for k in ("ok", "textures", "mesh", "_editor")}, indent=1, default=str))
    print(json.dumps({k: (data.get("masters") or {}).get(k, {}).get("statistics") for k in ("nodepth", "depth")}))
    print(json.dumps({k: {x: v.get(x) for x in ("bind", "carrier")} for k, v in (data.get("systems") or {}).items()},
                     default=str)[:3000])
    print("FX_ABILITY", "PASS" if data.get("ok") else "FAIL")
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
