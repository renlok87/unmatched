"""ENV-MAPS P5c track V: the environment fx - derived, tuned copies of AI-allowed Fab Niagara systems in /Game/EnvKit/FX.

Every entry of FX_SPECS is duplicated from its pack system (never edited in place: the pack folders stay pristine and
are not cooked as a whole) into /Game/EnvKit/FX/<name> (cooked through DirectoriesToAlwaysCook /Game/EnvKit; the
cooker follows the hard references into the pack folders for materials / textures) and tuned for the night boards:
  * system  (EditAnywhere, set from Python): bDeterminism on + a fixed RandomSeed (the layout adds a per-fx
            RandomSeedOffset; S08EnvLayout.cpp warms every fx up in fixed 1/30 s ticks and holds it still in -Bench
            (P7c: time dilation 0), so the -Bench frames are reproducible), WarmupTime 0 (the warmup is per component)
  * tune    (C++ US08EnvFxAuthoringLibrary.TuneNiagaraSystem, S08EnvFxAuthoring.cpp - the emitter data and the module
            constants are not reachable from editor Python): every emitter CPU sim + emitter determinism / seed, Light
            and Component renderers disabled (no dynamic light from VFX; budget 1 key + <= 6 points per map), the
            rapid-iteration constants scaled for the diorama (the Stylish fire sprites are 80-150 uu and do not follow
            the actor scale), exposed user-parameter defaults for the night palette
Particle budget: estimate_particles() per system (pack spawn rates x lifetimes x the tune factors / the user
overrides of the layout); p5c_layout_fx.py sums them per board (budget BOARD_PARTICLE_BUDGET).

Modes (one file):
  --check  (plain Python, no UE) validates FX_SPECS: sources in AI-allowed pack folders only (NoAI packs refused),
           pack files present in this checkout, targets under /Game/EnvKit/FX/, CPU + determinism + no light renderers,
           well-formed constant rules, estimates within FX_PARTICLE_BUDGET; prints the plan and the spec sha256s.
  (UE)     UnrealEditor-Cmd <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
               -script="<repo>/tools/art/env_kit/ue_import_fab_fx.py [--force] [--only NS_Env_Campfire,...]"
               -unattended -nosplash -nullrhi
           Idempotent: the derived asset carries the metadata tag EnvFxSpecSha256 (spec + tool version); it is rebuilt
           (deleted, duplicated again from the pristine pack system, tuned, saved) only when that sha changes or with
           --force, so the 'mul' rules always apply to the pack values. Report: 'ENVFX-IMPORT-REPORT {...}' /
           'ENVFX-IMPORT-RESULT ok|failed' and <project>/Saved/EnvKit/ue-fx-import-report.json (or --report).
Needs the UnmatchedEditor build with S08EnvFxAuthoring.cpp (Unmatched.Build.cs: Niagara). Licences: Stylish Fire VFX =
Fab Standard (personal); Free Niagara Particles (SoftTofuVFX) = CC BY 4.0, attribution in docs/art-pipeline/CREDITS-fab.md.
Statuses: proposed / measured / technically imported; artistic acceptance is the user's decision only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only; --check runs in plain Python
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CONTENT = REPO / "unreal/Unmatched/Content"
TOOL_VERSION = "1"
FX_ROOT = "/Game/EnvKit/FX"
SHA_TAG = "EnvFxSpecSha256"
FX_PARTICLE_BUDGET = 300  # per system instance (estimate after the tune)
BOARD_PARTICLE_BUDGET = 1500  # per board (p5c_layout_fx.py); target "a few hundred"
AI_ALLOWED_PACKS = ("StylizedForest", "Fantasy_Forest", "Vine_Plants", "Flowers_Pots", "Stylish_Fire_VFX",
                    "FreeParticle_SoftTofu", "Particles_Wind_Control_System", "WaterMaterials")
NOAI_PACKS = ("Megaplant_Library", "StyleHex_Studio")  # asset paths / technical data only - never in the main variant
SYSTEM_PROPS = ("determinism", "random_seed", "warmup_time")

# Fire: the Stylish Fire 2 / 3 module constants (P5c scout vfx_inventory.json, decoded RI constants): 3 sprite
# emitters Fire_1 / Fire / Fire001, spawn 50 / 25 / 25 per s, lifetime 0.8..1.0 s, uniform sprite size 80 / 100 / 150
# uu, shape sphere 10 uu, gravity -980, curl noise 599 (Fire_1), speed limit 1000. A spatial factor k scales every
# length-type constant (sizes, radius, velocity scale, gravity, noise, speed limit) so the flame keeps its shape.
_FIRE_EMITTERS = {"Fire_1": {"spawnRate": 50.0, "lifetime": (0.8, 1.0)},
                  "Fire": {"spawnRate": 25.0, "lifetime": (0.8, 1.0)},
                  "Fire001": {"spawnRate": 25.0, "lifetime": (0.8, 1.0)}}


def _fire_rules(k: float, spawn_mul: float, color_mul: float = 1.0) -> list[dict]:
    """color_mul (P5c tune): x the emitters' Color.Scale Color (1, 1, 1) - the flames read as a faint wisp inside the
    warm light pool of their own campfire / lantern point light."""
    extra = [{"match": "*.Color.Scale Color", "mul": color_mul}] if color_mul != 1.0 else []
    return extra + [
        {"match": "*.InitializeParticle.Uniform Sprite Size*", "mul": k},
        {"match": "*.ShapeLocation.Sphere Radius", "mul": k},
        {"match": "*.AddVelocity.Velocity Speed Scale", "mul": k},
        {"match": "*.GravityForce.Gravity", "mul": k},
        {"match": "*.CurlNoiseForce.Noise Strength", "mul": k},
        {"match": "*.SolveForcesAndVelocity.Speed Limit", "mul": k},
        {"match": "*.SpawnRate.SpawnRate", "mul": spawn_mul},
    ]


FX_SPECS: list[dict] = [
    {
        "name": "NS_Env_Campfire",
        "source": "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_2",
        "pack": "Stylish_Fire_VFX",
        "licence": "Fab Standard (personal)",
        "role": "Sarpedon campfires (campfire-nw, campfire-w): a ~30-45 uu stylised flame on the logs",
        "system": {"determinism": True, "random_seed": 52011, "warmup_time": 0.0},
        "tune": {"simTarget": "cpu", "emitterDeterminism": True, "emitterSeedBase": 52100,
                 "disableLightRenderers": True, "disableComponentRenderers": True,
                 "constants": _fire_rules(0.4, 0.8, 3.0), "user": {}},  # P5c tune t1: k 0.3 -> 0.4, colour x3
        "estimate": {"kind": "emitters", "emitters": _FIRE_EMITTERS, "spawnMul": 0.8},
    },
    {
        "name": "NS_Env_ConceptFire",
        "source": "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_2",
        "pack": "Stylish_Fire_VFX",
        "licence": "Fab Standard (personal)",
        "role": "ENV-MAPS P7 concept paste (sarpedon.concept.layout.json fire-fort / fire-brazier): the painted fires of the "
                "concept are tall yellow-cored flames; NS_Env_Campfire (colour x3) read as a red blob over the clean "
                "plate's embers at C0 / K1 (P7 tune) - a larger, less saturated copy; NS_Env_Campfire (P5c) unchanged",
        "system": {"determinism": True, "random_seed": 52014, "warmup_time": 0.0},
        "tune": {"simTarget": "cpu", "emitterDeterminism": True, "emitterSeedBase": 52400,
                 "disableLightRenderers": True, "disableComponentRenderers": True,
                 "constants": _fire_rules(0.5, 0.8, 5.0), "user": {}},
        "estimate": {"kind": "emitters", "emitters": _FIRE_EMITTERS, "spawnMul": 0.8},
    },
    {
        "name": "NS_Env_LanternFlame",
        "source": "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_3",
        "pack": "Stylish_Fire_VFX",
        "licence": "Fab Standard (personal)",
        "role": "the lit lanterns (Marmoreal LanternPlinth lamp-*, Sarpedon LanternPost lantern-*): a ~6-12 uu flame",
        "system": {"determinism": True, "random_seed": 52012, "warmup_time": 0.0},
        "tune": {"simTarget": "cpu", "emitterDeterminism": True, "emitterSeedBase": 52200,
                 "disableLightRenderers": True, "disableComponentRenderers": True,
                 "constants": _fire_rules(0.08, 0.5, 2.5), "user": {}},  # P5c tune t1: colour x2.5
        "estimate": {"kind": "emitters", "emitters": _FIRE_EMITTERS, "spawnMul": 0.5},
    },
    {
        "name": "NS_Env_CherryPetals",
        "source": "/Game/FreeParticle_SoftTofu/Niagara/NS_leaf",
        "pack": "FreeParticle_SoftTofu",
        "licence": "CC BY 4.0 (SoftTofuVFX; attribution in CREDITS-fab.md)",
        "role": "petals drifting from the Marmoreal cherry crowns (cherry-*), muted night pink",
        # pack: GPU sim, User.SpawnRate 35, Lifetime 2..3 s, Sphere Radius 40, Sprite Size (9..16), Gravity -42.6
        "system": {"determinism": True, "random_seed": 52013, "warmup_time": 0.0},
        "tune": {"simTarget": "cpu", "emitterDeterminism": True, "emitterSeedBase": 52300,
                 "disableLightRenderers": True, "disableComponentRenderers": True,
                 "constants": [{"match": "*.InitializeParticle.Uniform Sprite Size*", "mul": 0.4}],
                 "user": {"SpawnRate": 6.0, "Sphere Radius": 70.0, "Sprite Size Min": [3.0, 3.0],
                          "Sprite Size Max": [5.0, 5.0], "Lifetime Min": 4.0, "Lifetime Max": 6.0,
                          "Gravity": [0.0, 0.0, -18.0], "Color": [1.6, 0.85, 1.05]}},
        "estimate": {"kind": "user", "spawnRate": "SpawnRate", "lifetime": ("Lifetime Min", "Lifetime Max")},
    },
    {
        "name": "NS_Env_Fireflies",
        "source": "/Game/FreeParticle_SoftTofu/Niagara/NS_Sparkling_Animate_2",
        "pack": "FreeParticle_SoftTofu",
        "licence": "CC BY 4.0 (SoftTofuVFX; attribution in CREDITS-fab.md)",
        "role": "fireflies over the Sarpedon west forest / beach and the Marmoreal garden (colour per map in the layout)",
        # pack: GPU sim, User.SpawnRate 5, Lifetime 1.8..3.2 s, Sphere Radius 88, Uniform Sprite Size 62..102 (user) /
        # 7..14 (constant), Color (244, 344, 34) HDR
        "system": {"determinism": True, "random_seed": 52014, "warmup_time": 0.0},
        "tune": {"simTarget": "cpu", "emitterDeterminism": True, "emitterSeedBase": 52400,
                 "disableLightRenderers": True, "disableComponentRenderers": True,
                 # P5c tune t1: the constant rule matched nothing (the pack sprite size is the user parameter only)
                 "constants": [],
                 "user": {"SpawnRate": 5.0, "Sphere Radius": 120.0, "Uniform Sprite Size Min": 8.0,
                          "Uniform Sprite Size Max": 14.0, "Lifetime Min": 2.0, "Lifetime Max": 3.5,
                          "Color": [6.0, 5.0, 1.2]}},
        "estimate": {"kind": "user", "spawnRate": "SpawnRate", "lifetime": ("Lifetime Min", "Lifetime Max")},
    },
]
# Not built (P5c scout): a waterfall mist - no fitting Niagara system in the AI-allowed packs (WaterMaterials foam /
# splash are deprecated Cascade); Particles_Wind_Control_System fireflies / candle add PointLightComponents.


def spec_by_name(name: str) -> dict | None:
    return next((s for s in FX_SPECS if s["name"] == name), None)


def target_path(spec: dict) -> str:
    return f"{FX_ROOT}/{spec['name']}"


def spec_sha256(spec: dict) -> str:
    body = {k: spec[k] for k in ("name", "source", "system", "tune")}
    body["toolVersion"] = TOOL_VERSION
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _num(v) -> float:
    return float(v[0]) if isinstance(v, (list, tuple)) else float(v)


def estimate_particles(name: str, user: dict | None = None) -> float:
    """Live particles of one instance after the warmup (steady state: spawn rate x mean lifetime)."""
    spec = spec_by_name(name)
    if spec is None:
        raise KeyError(name)
    est = spec["estimate"]
    if est["kind"] == "emitters":
        return sum(e["spawnRate"] * est["spawnMul"] * (e["lifetime"][0] + e["lifetime"][1]) / 2.0
                   for e in est["emitters"].values())
    params = dict(spec["tune"].get("user") or {})
    for k, v in (user or {}).items():
        params[k[5:] if k.startswith("User.") else k] = v
    rate = _num(params[est["spawnRate"]])
    lo, hi = (_num(params[k]) for k in est["lifetime"])
    return rate * (lo + hi) / 2.0


def pack_file(asset_path: str) -> Path:
    """/Game/<Pack>/X/NS_Y -> <Content>/<Pack>/X/NS_Y.uasset"""
    return CONTENT / (asset_path[len("/Game/"):] + ".uasset")


def validate(specs: list[dict], content: Path | None = CONTENT) -> tuple[list[str], list[str]]:
    """(errors, warnings) of the spec list. content=None skips the pack-file presence check."""
    err, warn = [], []
    names = set()
    for s in specs:
        n = s.get("name", "?")
        ctx = f"{n}:"
        if n in names:
            err.append(f"{ctx} duplicate name")
        names.add(n)
        if not n.startswith("NS_Env_") or not n.replace("_", "").isalnum():
            err.append(f"{ctx} name must be NS_Env_<Alnum>")
        src = s.get("source", "")
        parts = src.split("/")
        pack = parts[2] if len(parts) > 3 and src.startswith("/Game/") else ""
        if pack in NOAI_PACKS or any(p in src for p in NOAI_PACKS):
            err.append(f"{ctx} source {src} is in a NoAI pack (technical data only, never the main variant)")
        elif pack not in AI_ALLOWED_PACKS:
            err.append(f"{ctx} source {src} is not in an AI-allowed pack folder {AI_ALLOWED_PACKS}")
        if pack != s.get("pack"):
            err.append(f"{ctx} pack '{s.get('pack')}' != source folder '{pack}'")
        if not target_path(s).startswith(FX_ROOT + "/"):
            err.append(f"{ctx} target outside {FX_ROOT}")
        sysp = s.get("system") or {}
        if set(sysp) - set(SYSTEM_PROPS):
            err.append(f"{ctx} unknown system properties {sorted(set(sysp) - set(SYSTEM_PROPS))}")
        if sysp.get("determinism") is not True or not isinstance(sysp.get("random_seed"), int):
            err.append(f"{ctx} system determinism with a fixed integer random_seed is required (-Bench frames)")
        t = s.get("tune") or {}
        if t.get("simTarget") != "cpu":
            err.append(f"{ctx} simTarget must be 'cpu' (task rule: CPU sim)")
        if t.get("emitterDeterminism") is not True or not isinstance(t.get("emitterSeedBase"), int):
            err.append(f"{ctx} emitterDeterminism true + an integer emitterSeedBase are required")
        if t.get("disableLightRenderers") is not True or t.get("disableComponentRenderers") is not True:
            err.append(f"{ctx} Light and Component renderers must be disabled (no dynamic lights from VFX)")
        for i, r in enumerate(t.get("constants") or []):
            if not isinstance(r.get("match"), str) or not r["match"]:
                err.append(f"{ctx} constants[{i}] without a match pattern")
            if ("mul" in r) == ("set" in r):
                err.append(f"{ctx} constants[{i}] needs exactly one of mul / set")
            hi = 6.0 if ".Color." in str(r.get("match")) else 2.0  # a colour scale may brighten more than a size
            if "mul" in r and not (0.0 < float(r["mul"]) <= hi):
                err.append(f"{ctx} constants[{i}] mul {r['mul']} outside (0, {hi:g}]")
        for k, v in (t.get("user") or {}).items():
            vals = v if isinstance(v, list) else [v]
            if k.startswith("User.") or not (1 <= len(vals) <= 4) or not all(isinstance(x, (int, float)) for x in vals):
                err.append(f"{ctx} user '{k}' must be a name without 'User.' and 1..4 numbers")
        try:
            est = estimate_particles(n) if spec_by_name(n) is s else None
        except (KeyError, TypeError, ValueError) as exc:
            err.append(f"{ctx} particle estimate failed ({type(exc).__name__}: {exc})")
            est = None
        if est is not None and est > FX_PARTICLE_BUDGET:
            err.append(f"{ctx} ~{est:.0f} particles > {FX_PARTICLE_BUDGET} per instance")
        if content is not None and pack and not pack_file(src).is_file():
            warn.append(f"{ctx} pack file {pack_file(src).relative_to(REPO).as_posix()} not in this checkout "
                        "(the orchestrator copies the Fab Content; the UE run will fail for this entry)")
    return err, warn


def plan(specs: list[dict]) -> dict:
    return {s["name"]: {"source": s["source"], "target": target_path(s), "pack": s["pack"], "licence": s["licence"],
                        "role": s["role"], "specSha256": spec_sha256(s),
                        "particlesEstimate": round(estimate_particles(s["name"]), 1)} for s in specs}


# ================================================================================================ UE
def _describe(path: str) -> dict:
    return json.loads(u.S08EnvFxAuthoringLibrary.describe_niagara_system(path))


def _verify(describe: dict) -> list[str]:
    """The tuned system against the task rules (CPU, determinism, no light / component renderer)."""
    bad = []
    d = describe.get("describe") or {}
    if not d:
        return [f"describe failed: {describe.get('error')}"]
    if not d.get("determinism"):
        bad.append("system determinism off")
    for e in d.get("emitters", []):
        if not e.get("enabled"):
            continue
        if e.get("simTarget") != "cpu":
            bad.append(f"emitter {e.get('name')}: simTarget {e.get('simTarget')}")
        for r in e.get("renderers", []):
            if r.get("enabled") and (r.get("light") or r.get("component")):
                bad.append(f"emitter {e.get('name')}: enabled {r.get('class')}")
    return bad


def run_import(specs: list[dict], force: bool) -> tuple[dict, bool]:
    lib = u.EditorAssetLibrary
    if not hasattr(u, "S08EnvFxAuthoringLibrary"):
        return {"error": "US08EnvFxAuthoringLibrary missing: build UnmatchedEditor with S08EnvFxAuthoring.cpp"}, False
    out, ok = {}, True
    for s in specs:
        dst, src, sha = target_path(s), s["source"], spec_sha256(s)
        entry: dict = {"source": src, "target": dst, "specSha256": sha}
        out[s["name"]] = entry
        try:
            if not lib.does_asset_exist(src):
                raise RuntimeError(f"pack system {src} not in this checkout")
            if lib.does_asset_exist(dst) and not force:
                cur = lib.load_asset(dst)
                if cur is not None and lib.get_metadata_tag(cur, SHA_TAG) == sha:
                    entry["action"] = "unchanged"
                    entry["verify"] = _verify(_describe(dst))
                    ok = ok and not entry["verify"]
                    continue
            if lib.does_asset_exist(dst):
                # our own derived asset (never a pack asset): re-derived from the pristine pack system so every
                # 'mul' rule applies to the pack values exactly once
                if not lib.delete_asset(dst):
                    raise RuntimeError(f"cannot replace {dst}")
            if lib.duplicate_asset(src, dst) is None:
                raise RuntimeError(f"duplicate {src} -> {dst} failed")
            system = lib.load_asset(dst)
            for key, value in s["system"].items():
                system.set_editor_property(key, value)
            tune = json.loads(u.S08EnvFxAuthoringLibrary.tune_niagara_system(dst, json.dumps(s["tune"])))
            entry["tune"] = {k: tune.get(k) for k in ("ok", "compiled", "errors", "unmatchedRules", "emitters",
                                                      "lightRenderersDisabled", "componentRenderersDisabled",
                                                      "constants", "user")}
            lib.set_metadata_tag(system, SHA_TAG, sha)
            if not lib.save_loaded_asset(system, False):
                raise RuntimeError(f"save {dst} failed")
            entry["verify"] = _verify(_describe(dst))
            entry["action"] = "built"
            entry["ok"] = bool(tune.get("ok")) and bool(tune.get("compiled")) and not entry["verify"]
            ok = ok and entry["ok"]
        except Exception as exc:  # noqa: BLE001 - one entry fails, the report says why
            entry["action"] = "failed"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            ok = False
    return out, ok


# ================================================================================================ entry
def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true", help="plain Python: validate the specs (no UE)")
    ap.add_argument("--force", action="store_true", help="UE: rebuild every derived system")
    ap.add_argument("--only", default="", help="comma-separated NS_Env_* names")
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)
    started = time.time()
    only = [n.strip() for n in args.only.split(",") if n.strip()]
    unknown = [n for n in only if spec_by_name(n) is None]
    if unknown:
        print(f"unknown fx {unknown}; known: {[s['name'] for s in FX_SPECS]}")
        return 2
    specs = [s for s in FX_SPECS if not only or s["name"] in only]
    mode = "check" if (args.check or u is None) else "import"
    errors, warnings = validate(specs)
    report = {"schema": "unmatched.env-fx-import/1", "tool": "tools/art/env_kit/ue_import_fab_fx.py", "mode": mode,
              "toolVersion": TOOL_VERSION, "root": FX_ROOT, "plan": plan(specs), "errors": errors,
              "warnings": warnings, "status": "proposed" if mode == "check" else "technically imported"}
    ok = not errors
    if mode == "import" and ok:
        imported, import_ok = run_import(specs, args.force)
        report["ue"] = imported
        report["engine"] = str(u.SystemLibrary.get_engine_version())
        ok = ok and import_ok
    report["ok"] = ok
    report["seconds"] = round(time.time() - started, 1)
    text = json.dumps(report, ensure_ascii=False, indent=1, default=str)
    report_path = Path(args.report) if args.report else (
        Path(u.Paths.project_saved_dir()) / "EnvKit" / "ue-fx-import-report.json" if u is not None else None)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes((text + "\n").encode("utf-8"))
    for w in warnings:
        print("  WARN  " + w)
    for e in errors:
        print("  ERROR " + e)
    for name, p in report["plan"].items():
        print(f"  {name:22s} <- {p['source']}  ~{p['particlesEstimate']:.0f} particles  sha {p['specSha256'][:12]}")
    print("ENVFX-IMPORT-REPORT " + json.dumps(report, ensure_ascii=False, default=str))
    print(f"ENVFX-IMPORT-RESULT {'ok' if ok else 'failed'} mode={mode} systems={len(specs)}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        raise RuntimeError("ENVFX import failed - see ENVFX-IMPORT-REPORT")
