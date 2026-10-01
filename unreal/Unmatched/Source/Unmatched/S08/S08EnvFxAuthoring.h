// ENV-MAPS P5c track V: editor-only tuning of the DERIVED Niagara systems of the environment fx (/Game/EnvKit/FX/,
// duplicated from the AI-allowed Fab packs by tools/art/env_kit/ue_import_fab_fx.py under UnrealEditor-Cmd).
// Why C++ and not pure Python: the emitter data (FVersionedNiagaraEmitterData: SimTarget, determinism, renderers),
// the module input constants (UNiagaraScript::RapidIterationParameters) and the exposed user parameter store are not
// reachable from editor Python (no BlueprintVisible properties, the NiagaraToolset classes expose no methods - P5c
// scout). System-level fields (bDeterminism, RandomSeed, WarmupTime) are EditAnywhere and set by the Python script.
// Editor only; the game build has the functions but they return an error report. Never call Tune on a pack asset:
// it refuses every path outside /Game/EnvKit/ (the pack folders stay pristine).
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "S08EnvFxAuthoring.generated.h"

UCLASS()
class UNMATCHED_API US08EnvFxAuthoringLibrary : public UBlueprintFunctionLibrary {
  GENERATED_BODY()

public:
  /** JSON description of a Niagara system (read only): system determinism / seed / warmup, per emitter handle the
   *  name, enabled, sim target (cpu | gpu), determinism, seed, local space and the renderers (class, enabled), the
   *  user parameters (name, type, value) and the rapid-iteration constants of every script (name, type, value). */
  UFUNCTION(BlueprintCallable, Category = "S08|Env FX")
  static FString DescribeNiagaraSystem(const FString& SystemPath);

  /** Applies a tune spec to a derived system under /Game/EnvKit/ and recompiles it (the caller saves the package):
   *  { "simTarget": "cpu", "emitterDeterminism": true, "emitterSeedBase": 1000,
   *    "disableLightRenderers": true, "disableComponentRenderers": true,
   *    "emitters": { "<handle name>": {"enabled": false} },
   *    "constants": [ {"match": "*.InitializeParticle.Uniform Sprite Size*", "emitter": "<optional handle name>",
   *                    "mul": 0.3 | "set": <number | [n..]>} ],     // names without the "Constants." prefix
   *    "user": { "<name without User.>": <number | [n..]> } }       // exposed parameter defaults
   *  Returns a JSON report (changes with old / new values, rules that matched nothing, compile result, errors). */
  UFUNCTION(BlueprintCallable, Category = "S08|Env FX")
  static FString TuneNiagaraSystem(const FString& SystemPath, const FString& SpecJson);
};
