"""FX-03 / FX-04 / FX-02 (VS-6 Z-2, editor task): the effect types and the first FX system of /Game/S08/FX.

Run by tools/art/de010/de010.run_editor (or directly with -ExecutePythonScript):

  UnrealEditor-Cmd <uproject> -ExecutePythonScript=tools/art/fx/ue_fx_systems.py -unattended -nullrhi

1. The effect types of ВР-25: /Game/S08/FX/EffectTypes/NET_UM_Combat (MaxSystemInstances 3, the star / motes /
   embers / arc / vortex) and NET_UM_Board (6, the dust / chevrons / the placard) - cull reaction Deactivate,
   the age significance handler (the newer instance wins). Created once, updated in place.
2. NS_FX_PlacardStar under /Game/S08/FX/Systems/: the FX-02 test placard - since the Z-2 review (ВР-Z2R-06) a
   duplicate of the ENGINE template system /Niagara/DefaultAssets/Templates/Systems/DirectionalBurst (Unreal
   Engine content: no third-party licence, no attribution), re-tuned through
   US08EnvFxAuthoringLibrary.TuneNiagaraSystem into ONE still print sprite shown at once: the burst of 1 at t=0,
   no velocity / gravity, the size-by-speed factors 1, a life far longer than any shot, the ribbon emitter off,
   the print material MI_FX_PlacardStar on the sprite renderer, the seed = CRC32 of the name (FX-04), fixed
   bounds, the effect type NET_UM_Board, PoolPrimeSize 2. The former donor (the EnvKit copy of SoftTofu's
   NS_Env_FallsSpray, CC BY 4.0) spawned its first particle only after 4 s at sprite size 0 (the sparkle size
   multiplier was zeroed) - the star of the Z-2 frames never drew.

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
DONOR = "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst"
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


def tune_effect_type_caps(path, cap, out_entry):
    """ВР-25 caps (Z-2 review fix 8; ВР-Z2-09 closed): the caps live in the per-platform SystemScalabilitySettings
    array and the cull reaction on the type - not reachable from python, so the C++ editor library
    US08FxAuthoringLibrary.SetEffectTypeCaps writes them (both instance counts = cap, CullReaction Deactivate)."""
    report = json.loads(u.S08FxAuthoringLibrary.set_effect_type_caps(path, cap))
    out_entry.update(report)
    if not report.get("ok"):
        raise RuntimeError("effect type caps of %s: %s" % (path, report))


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
        tune_effect_type_caps(path, cap, entry)
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
            # the system is rebuilt from the pristine template on every run - never tune a stale copy in place
            raise RuntimeError("delete of %s refused (a live reference?)" % PLACARD)
    if EAL.does_asset_exist(PLACARD):
        # the editor kept the deleted package in memory: delete the .uasset on disk before the run instead
        raise RuntimeError("%s still exists after the delete - remove its .uasset and rerun" % PLACARD)
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
        "emitters": {"LocationBasedRibbon": {"enabled": False}},
        "spriteMaterials": {"DirectionalBurst": MI_PLACARD},
        "constants": [
            {"match": "*SpawnBurst_Instantaneous.Spawn Count", "set": 1},
            {"match": "*SpawnBurst_Instantaneous.Spawn Time", "set": 0},
            {"match": "*InitializeParticle.Lifetime Min", "set": 100000.0},
            {"match": "*InitializeParticle.Lifetime Max", "set": 100000.0},
            {"match": "*InitializeParticle.Sprite Size Min", "set": [96.0, 96.0]},
            {"match": "*InitializeParticle.Sprite Size Max", "set": [96.0, 96.0]},
            {"match": "*ScaleSpriteSizeBySpeed.Min Scale Factor", "set": [1.0, 1.0]},
            {"match": "*ScaleSpriteSizeBySpeed.Max Scale Factor", "set": [1.0, 1.0]},
            {"match": "*RandomRangeFloat002.Minimum", "set": 0.0},
            {"match": "*RandomRangeFloat002.Maximum", "set": 0.0},
            {"match": "*GravityForce.Gravity", "set": [0.0, 0.0, 0.0]},
            {"match": "*EmitterState.MaxDistance", "set": 1000000.0},
        ],
    }
    tune = TUNE.tune_niagara_system(PLACARD, json.dumps(spec))
    # FX-04 (the Z-2 review): bFixedBounds itself is not reachable from python (its name collides with FixedBounds)
    out["placard"]["fixedBoundsOn"] = json.loads(u.S08FxAuthoringLibrary.set_system_fixed_bounds(PLACARD, 60.0))
    # FX-02: the print flipbook samples its frame through the renderer's SubUV grid (T_FX_HitStar: 8 x 1)
    out["placard"]["subImage"] = json.loads(
        u.S08FxAuthoringLibrary.set_sprite_sub_image(PLACARD, "DirectionalBurst", 8, 1))
    if not out["placard"]["subImage"].get("ok"):
        raise RuntimeError("SubImageSize: %s" % out["placard"]["subImage"])
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
