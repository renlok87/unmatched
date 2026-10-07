// FX-03 (VS-6 Z-2 review fix 8, ВР-25): editor-only authoring of the FX effect types. The instance caps of an
// effect type live in its SystemScalabilitySettings array (FNiagaraSystemScalabilitySettings per platform set) and
// the cull reaction on the type itself - neither is reachable from editor Python (ВР-Z2-09), so the editor script
// tools/art/fx/ue_fx_systems.py calls this. Refuses every path outside /Game/S08/FX/.
#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "S08FxAuthoring.generated.h"

UCLASS()
class UNMATCHED_API US08FxAuthoringLibrary : public UBlueprintFunctionLibrary {
  GENERATED_BODY()

public:
  /** Sets the ВР-25 cap of an effect type: every scalability entry culls by the effect-type instance count and by
   *  the per-system instance count at MaxInstances, the cull reaction is Deactivate (Kill: particles die
   *  naturally, no auto-reactivation). The caller saves the package. Returns a JSON report (ok, values). */
  UFUNCTION(BlueprintCallable, Category = "S08|FX")
  static FString SetEffectTypeCaps(const FString& EffectTypePath, int32 MaxInstances);

  /** FX-04: fixed bounds ON (bFixedBounds is not reachable from python - its name collides with FixedBounds) with a
   *  cube of HalfExtent around the system origin. The caller saves the package. JSON report. */
  UFUNCTION(BlueprintCallable, Category = "S08|FX")
  static FString SetSystemFixedBounds(const FString& SystemPath, float HalfExtent);

  /** FX-02: the SubUV grid of an emitter's sprite renderers (SubImageSize X x Y) - the print flipbook samples the
   *  frame through TextureSampleParameterSubUV. The caller saves the package. JSON report. */
  UFUNCTION(BlueprintCallable, Category = "S08|FX")
  static FString SetSpriteSubImage(const FString& SystemPath, const FString& EmitterName, int32 X, int32 Y);
};
