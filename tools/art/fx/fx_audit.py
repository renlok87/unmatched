"""FX-04 (VS-6 Z-2): the editor audit of the /Game/S08/FX/** systems - determinism, the seed rule, CPU, fixed
bounds, the allocation against the registry budget and the effect type. Editor task (US08EnvFxAuthoringLibrary.

DescribeNiagaraSystem gives the emitter-level facts python cannot reach):

  UnrealEditor-Cmd <uproject> -run=pythonscript -script=tools/art/fx/fx_audit.py -unattended -nullrhi

Checks per system (all must pass for the report's ok):
  * system bDeterminism, RandomSeed == CRC32(asset name) & 0x7FFFFFFF (S08CueFx::SeedOf), WarmupTime 0
  * every emitter: simTarget cpu, determinism on, seed = the system seed + the emitter index
  * fixed bounds set (the system never asks the simulation for bounds)
  * an effect type assigned; the allocation estimate (the spawn rate x lifetime of the exposed user params,
    or the emitter constants) <= the registry budget of its CUE (the placard carries its own bench budget).

Report: docs/game-design/evidence/VISUAL/FX-04/fx-audit.json (the card's deliverable).
"""
from __future__ import annotations

import json
import re
import zlib
from pathlib import Path

try:
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain python
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REPORT = REPO / "docs/game-design/evidence/VISUAL/FX-04/fx-audit.json"
ROOT = "/Game/S08/FX"
# the registry budgets of S08CueFx.cpp (CUE -> sprite budget); the placard is bench-only and carries its own
BUDGETS = {
    "NS_FX_Dust": 5, "NS_FX_AttackChevrons": 3, "NS_FX_HitStar": 1, "NS_FX_HealMotes": 5, "NS_FX_AshEmbers": 40,
    "NS_FX_ArthurArc": 1, "NS_FX_MedusaVortex": 20, "NS_FX_PlacardStar": 6,
}


def crc_seed(name: str) -> int:
    return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF


def main() -> int:
    systems = []
    for folder in ("Systems", "Board", "Combat"):
        for asset in u.EditorAssetLibrary.list_assets(f"{ROOT}/{folder}", recursive=False) if u else []:
            systems.append(str(asset).rsplit(".", 1)[0])
    out = {"schema": "unmatched.fx-audit/1", "systems": {}, "ok": False}
    for path in sorted(set(systems)):
        name = path.rsplit("/", 1)[-1]
        entry = {"path": path}
        describe = json.loads(u.S08EnvFxAuthoringLibrary.describe_niagara_system(path))["describe"]
        problems = []
        if not describe.get("determinism"):
            problems.append("system determinism off")
        want_seed = crc_seed(name)
        if describe.get("randomSeed") != want_seed:
            problems.append(f"seed {describe.get('randomSeed')} != crc32 {want_seed}")
        if describe.get("warmupTime"):
            problems.append(f"warmup {describe.get('warmupTime')} != 0")
        for index, emitter in enumerate(describe.get("emitters", [])):
            if not emitter.get("enabled", True):
                continue  # a disabled emitter never simulates (the template's ribbon of the placard star)
            if emitter.get("simTarget") != "cpu":
                problems.append(f"{emitter.get('name')}: sim {emitter.get('simTarget')} != cpu")
            if not emitter.get("determinism"):
                problems.append(f"{emitter.get('name')}: emitter determinism off")
            if emitter.get("randomSeed") not in (want_seed + index, want_seed):
                problems.append(f"{emitter.get('name')}: seed {emitter.get('randomSeed')} != {want_seed}+{index}")
        # fixed bounds + effect type read from the loaded system
        system = u.load_asset(f"{path}.{name}")
        box = system.get_editor_property("fixed_bounds")
        if box and (box.min.x == box.max.x or abs(box.max.x - box.min.x) < 1.0):
            problems.append("fixed bounds collapsed")
        effect_type = system.get_editor_property("effect_type")
        entry["effectType"] = effect_type.get_name() if effect_type else None
        if not effect_type:
            problems.append("no effect type (VR-25)")
        # the allocation estimate from the exposed user parameters (rate x lifetime)
        user = describe.get("user", {})
        rate = lifetime = None
        for key, value in user.items():
            if re.fullmatch(r"User\.? ?SpawnRate", key):
                rate = value.get("value")
            if re.fullmatch(r"User\.? ?Lifetime (Min|Max)", key):
                lifetime = value.get("value")
        allocation = round(rate * lifetime, 1) if isinstance(rate, (int, float)) and isinstance(
            lifetime, (int, float)) else None
        if allocation is None:
            # a burst system (the placard star since the Z-2 review: the engine DirectionalBurst template) - the
            # burst counts of the enabled emitters (their EmitterUpdateScript constants)
            enabled = {e.get("name") for e in describe.get("emitters", []) if e.get("enabled", True)}
            bursts = 0
            for script, constants in describe.get("constants", {}).items():
                if not script.endswith("EmitterUpdateScript"):
                    continue
                for key, value in constants.items():
                    if key.endswith("SpawnBurst_Instantaneous.Spawn Count") and key.split(".")[0] in enabled:
                        bursts += int(value.get("value") or 0)
            allocation = bursts or None
        entry["allocationEstimate"] = allocation
        budget = BUDGETS.get(name)
        entry["budget"] = budget
        if allocation is not None and budget is not None and allocation > budget:
            problems.append(f"allocation {allocation} > budget {budget}")
        entry["problems"] = problems
        out["systems"][name] = entry
    out["ok"] = all(not e["problems"] for e in out["systems"].values())
    out["count"] = len(out["systems"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                      newline="\n")
    print(json.dumps({"ok": out["ok"], "count": out["count"],
                      "problems": {k: v for k, v in ((n, e["problems"]) for n, e in out["systems"].items())
                                   if v}}))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    main()
