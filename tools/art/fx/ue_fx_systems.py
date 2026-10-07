"""FX-03 / FX-04 / FX-02 (VS-6 Z-2, editor task): the effect types and the first FX system of /Game/S08/FX.

Run by tools/art/de010/de010.run_editor (or directly with -ExecutePythonScript):

  UnrealEditor-Cmd <uproject> -ExecutePythonScript=tools/art/fx/ue_fx_systems.py -unattended -nullrhi

1. The effect types of ВР-25: /Game/S08/FX/EffectTypes/NET_UM_Combat (MaxSystemInstances 3, the star / motes /
   embers / arc / vortex) and NET_UM_Board (6, the dust / chevrons / the placard) - cull reaction Deactivate,
   the age significance handler (the newer instance wins). Created once, updated in place.
2. NS_FX_PlacardStar under /Game/S08/FX/Systems/: the FX-02 test placard - a duplicate of the simplest EnvKit
   CPU deterministic sprite system (NS_Env_FallsSpray, one emitter), re-tuned through
   US08EnvFxAuthoringLibrary.TuneNiagaraSystem into a still, long-lived, single print sprite: the print
   material MI_FX_PlacardStar on the sprite renderer, the noise / sparkle modules zeroed (ВР-Z2-08: the Tune
   cannot delete a module of the donor, so the combat systems of FX-13+ will be built without them; here the
   strengths are 0 and the picture is still), the seed = CRC32 of the name (FX-04), the effect type
   NET_UM_Board, PoolPrimeSize 2.

Idempotent: the system is re-duplicated from the pristine donor and re-tuned on every run. Report:
C:/tmp/z2-fx/fx-systems.json (settings before / after, the tune report, the describe of the result).
"""
import json
import zlib

import unreal as u

EAL = u.EditorAssetLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
TUNE = u.S08EnvFxAuthoringLibrary
REPORT = r"C:/tmp/z2-fx/fx-systems.json"
FX = "/Game/S08/FX"
DONOR = "/Game/EnvKit/FX/NS_Env_FallsSpray"
PLACARD = FX + "/Systems/NS_FX_PlacardStar"
MI_PLACARD = FX + "/Materials/MI_FX_PlacardStar"


def crc_seed(name: str) -> int:
    return zlib.crc32(name.encode("utf-8")) & 0x7FFFFFFF


def obj(path):
    return path + "." + path.rsplit("/", 1)[-1]


def load(path):
    a = u.load_asset(obj(path))
    if a is None:
        raise RuntimeError("asset not found: %s" % path)
    return a


def set_first(asset, names, value):
    """The first python property spelling that exists (UPROPERTY names differ across UE python versions)."""
    for name in names:
        try:
            asset.set_editor_property(name, value)
            return name
        except Exception:  # noqa: BLE001
            continue
    return None


def tune_effect_type_caps(et, cap, out_entry):
    """ВР-FX17: the caps live in the per-platform SystemScalabilitySettings array (not flat properties).
    Best effort through python: read the array struct, set the fields of its Settings list, write back."""
    try:
        arr = et.get_editor_property("SystemScalabilitySettings")
        items = None
        for attr in ("settings", "Settings"):
            if hasattr(arr, attr):
                items = getattr(arr, attr)
                break
        if items is None:
            out_entry["scalabilityArray"] = "no settings list on the wrapper"
            return
        if len(items) == 0:
            items.append(u.NiagaraSystemScalabilitySettings())
        entry = items[0]
        for name, value in (("bCullPerSystemMaxInstanceCount", True), ("MaxSystemInstances", cap),
                            ("CullReaction", getattr(u.NiagaraCullReaction, "DEACTIVATE", None))):
            try:
                entry.set_editor_property(name, value)
                out_entry[name] = True
            except Exception:  # noqa: BLE001
                out_entry[name + "_python"] = "ERR"
        et.set_editor_property("SystemScalabilitySettings", arr)
    except Exception as exc:  # noqa: BLE001
        out_entry["scalabilityArray"] = str(exc)[:150]


out = {"errors": []}
try:
    # ---- 1. the effect types of ВР-25
    out["effectTypes"] = {}
    for name, cap in (("NET_UM_Combat", 3), ("NET_UM_Board", 6)):
        path = FX + "/EffectTypes/" + name
        if not EAL.does_asset_exist(path):
            created = AT.create_asset(name, FX + "/EffectTypes", u.NiagaraEffectType,
                                      u.NiagaraEffectTypeFactoryNew())
            if created is None:
                raise RuntimeError("could not create %s" % path)
        et = load(path)
        et.modify()
        entry = {"cap": cap}
        tune_effect_type_caps(et, cap, entry)
        # the age significance handler (the newer instance wins); the class is not always python-exposed
        age_cls = getattr(u, "NiagaraSignificanceHandlerAge", None)
        if age_cls is not None:
            entry["significanceHandler"] = set_first(et, ("significanceHandler", "SignificanceHandler"),
                                                     u.new_object(age_cls, et))
        out["effectTypes"][name] = entry
        EAL.save_loaded_asset(et, False)
    # ---- 2. NS_FX_PlacardStar: duplicate the donor, tune into a still print sprite
    out["placard"] = {"donor": DONOR}
    if EAL.does_asset_exist(PLACARD):
        if not EAL.delete_asset(PLACARD):
            # a live reference keeps the package alive - tune the existing copy in place instead of duplicating
            out["placard"]["note"] = "existing asset kept (delete refused); tuned in place"
    if EAL.does_asset_exist(PLACARD):
        duplicate = load(PLACARD)
    else:
        duplicate = AT.duplicate_asset("NS_FX_PlacardStar", FX + "/Systems", load(DONOR))
    if duplicate is None:
        raise RuntimeError("duplicate %s -> %s failed" % (DONOR, PLACARD))
    seed = crc_seed("NS_FX_PlacardStar")
    duplicate.modify()
    duplicate.set_editor_property("determinism", True)
    duplicate.set_editor_property("random_seed", seed)
    duplicate.set_editor_property("warmup_time", 0.0)
    duplicate.set_editor_property("effect_type", load(FX + "/EffectTypes/NET_UM_Board"))
    # FX-04: fixed bounds (the system never asks the simulation for bounds; the audit checks them)
    out["placard"]["fixedBounds"] = set_first(
        duplicate, ("fixed_bounds", "FixedBounds"),
        u.Box(min=u.Vector(-30.0, -30.0, -30.0), max=u.Vector(30.0, 30.0, 30.0)))
    out["placard"]["poolPrimeSize"] = set_first(duplicate, ("pool_prime_size", "PoolPrimeSize"), 2)
    EAL.save_loaded_asset(duplicate, False)
    spec = {
        "simTarget": "cpu", "emitterDeterminism": True, "emitterSeedBase": seed,
        "spriteMaterials": {"HangingParticulates": MI_PLACARD},
        "user": {"SpawnRate": 0.25, "Lifetime Min": 20.0, "Lifetime Max": 20.0,
                 "User. Size Min": 22.0, "User.Size Max": 22.0, "Sphere Radius": 0.5, "Drag": 0.0,
                 "Noise Strength": 0.0, "Noise Frequency": 0.0, "ColorStrength_Sparkling": 0.0,
                 "Size_Sparkling": 0.0, "Sparkling_Speed_Min": 0.0, "Sparkling_Speed_Max": 0.0},
    }
    tune = TUNE.tune_niagara_system(PLACARD, json.dumps(spec))
    EAL.save_loaded_asset(load(PLACARD), False)
    out["tune"] = json.loads(tune)
    out["describe"] = json.loads(TUNE.describe_niagara_system(PLACARD))["describe"]
    out["ok"] = True
except Exception:  # noqa: BLE001
    import traceback
    out["ok"] = False
    out["error"] = traceback.format_exc()
with open(REPORT, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
