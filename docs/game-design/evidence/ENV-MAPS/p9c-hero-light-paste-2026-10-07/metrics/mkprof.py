"""P9b: override profile variants (-ArtBoardProfiles=<abs path>) - the shipped S08ArtBoardProfiles.json with only the
heroLight blocks changed. Measurement aids / tuning iterations; frames rendered with an override carry reference=0.

python mkprof.py <name> <variant json file | builtin> [--base <profiles.json>]
builtins: p9idle (P9 values, activeMul 1), maskfig / maskbody (green coaxial key + green rim, litPedestal per name),
          idle-of:<profiles.json> (that file's heroLight blocks with activeMul 1)
A variant json file = {"<lightId>|*": {heroLight block}} (merged over the base block; "states" merged too).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

SHIPPED = Path("C:/tmp/wt-visual/unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json")
OUT = Path("C:/tmp/visual/E3/profiles")


def merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


GREEN_KEY = {"lux": 50.0, "colorSrgb": "#00FF00", "innerConeDeg": 40, "outerConeDeg": 60, "heightMul": 2.5,
             "azimuthDeg": 0, "elevationDeg": 55, "radiusMul": 3.0}
GREEN_RIM = {"lux": 30.0, "colorSrgb": "#00FF00", "innerConeDeg": 30, "outerConeDeg": 50, "heightMul": 1.3,
             "azimuthDeg": 180, "elevationDeg": 35, "radiusMul": 3.0}


def main():
    name, variant = sys.argv[1], sys.argv[2]
    base_path = Path(sys.argv[sys.argv.index("--base") + 1]) if "--base" in sys.argv else SHIPPED
    doc = json.loads(base_path.read_text(encoding="utf-8"))
    for lid, lp in doc["lightProfiles"].items():
        hl = lp.get("heroLight")
        if hl is None:
            continue
        if variant == "p9idle" or variant.startswith("idle-of"):
            hl = merge(hl, {"states": {"activeMul": 1.0}})
        elif variant in ("maskfig", "maskbody"):
            hl = merge(hl, {"key": None, "rim": None})
            hl["key"], hl["rim"] = dict(GREEN_KEY), dict(GREEN_RIM)
            hl["states"] = {"activeMul": 1.0, "breathHz": 0.0, "breathAmp": 0.0, "defeatedMul": 0.0}
            if variant == "maskbody":
                hl["litPedestal"] = False
            hl["note"] = f"P9b measurement mask ({variant}): green light, not a look"
        else:
            spec = json.loads(Path(variant).read_text(encoding="utf-8"))
            over = spec.get(lid, spec.get("*"))
            if over is None:
                continue
            if "*" in spec and lid in spec:
                over = merge(spec["*"], spec[lid])
            hl = merge(hl, over)
        lp["heroLight"] = hl
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{name}.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
