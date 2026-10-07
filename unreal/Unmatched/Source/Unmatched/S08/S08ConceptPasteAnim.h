// VS-5 EN-06 (ENV-U16, docs/game-design/visual/06-tasks/env.csv EN-06, ВР-55 / ВР-EN.4): the animation channels of the
// concept paste (flicker, wind, mist) - the "anim" object of a paste block (S08ConceptPaste.h file comment), its MID
// values and its trace. World-free except SetParams / AttachMids (Unmatched.S08.ConceptPaste.Anim).
//
// The material (tools/art/concept_paste/ue_concept_material.py, graph 4, static switch UseAnim) per sheet pixel:
//   lanterns  colour x (1 + R x sum_i w_i (Flicker_i - 1) / max(sum_i w_i, 1)), w_i = soft disc (rim 20 %) of slot i in C0 px
//   wind      the plate is sampled at c + (dx, 0.35 dx), dx = G x ampPx x (sin(2 pi (hz t + x / wavePx)) +
//             gustAmp x sin(2 pi (gustHz t + y / wavePx + 0.37)))
//   mist      lerp(colour, MistColor, B x opacity x (0.4 + 0.6 noise((c0 + pan t) / noisePx)))
// with t = AnimTime. Frozen (-Bench, -EnvFxFreeze, reduced motion): AnimTime 0, every flicker 1, ampPx 0 - the mist stays
// (still), so two frozen frames are equal.
#pragma once

#include "CoreMinimal.h"
#include "S08ConceptPaste.h"

class FJsonObject;
class UMaterialInstanceDynamic;
struct FS08EnvFxOptions;

/** The MID values of the anim channels. */
struct UNMATCHED_API FS08ConceptAnimParams {
  float AnimTime = 0.0f;
  FLinearColor LanternC0[S08ConceptPasteSpec::MaxAnimLanterns];  // (x, y, radius, 0); radius 0 = unused slot
  float LanternFlicker[S08ConceptPasteSpec::MaxAnimLanterns];
  FLinearColor Wind = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);     // (ampPx, hz, gustHz, gustAmp)
  float WindWavePx = 400.0f;
  FLinearColor MistColor = FLinearColor(0.0f, 0.0f, 0.0f, 0.0f);  // linear
  FLinearColor MistParams = FLinearColor(0.0f, 0.0f, 0.0f, 220.0f);  // (opacity, panX, panY, noisePx)
  FS08ConceptAnimParams();
};

namespace S08ConceptPasteAnim {
/** Parses the "anim" object (Lights = the block's parsed "lights": a slot's "light" must name one); Fail gets
 *  'anim.<field> ...' messages. Out.bSet only when nothing failed. */
UNMATCHED_API void ParseJson(const TSharedPtr<FJsonObject>& Anim, const TArray<FS08ConceptLight>& Lights,
                             FS08ConceptPasteAnimSpec& Out, TFunctionRef<void(const FString&)> Fail);
/** LanternC0_<i> / LanternFlicker_<i>. */
UNMATCHED_API FName LanternC0Name(int32 Index);
UNMATCHED_API FName LanternFlickerName(int32 Index);
/** The linked light of a slot (nullptr: own amp / hz). */
UNMATCHED_API const FS08ConceptLight* LinkedLight(const FS08ConceptAnimLantern& Slot, const TArray<FS08ConceptLight>& Lights);
/** The slot's flicker at TimeS: S08ConceptPaste::FlickerScale of its linked light (synced) or of its own pair. */
UNMATCHED_API float LanternFlicker(const FS08ConceptAnimLantern& Slot, const TArray<FS08ConceptLight>& Lights, double TimeS);
/** Slots whose "light" names a light of Lights. */
UNMATCHED_API int32 SyncedCount(const FS08ConceptPasteAnimSpec& Anim, const TArray<FS08ConceptLight>& Lights);
/** All MID values; bFrozen: AnimTime 0, flicker 1, wind amplitude 0 (TimeS ignored). */
UNMATCHED_API FS08ConceptAnimParams Params(const FS08ConceptPasteAnimSpec& Anim, const TArray<FS08ConceptLight>& Lights,
                                           bool bFrozen, double TimeS);
/** ok | no-block | mask-missing | material-missing (UseAnim 1 only for ok). */
UNMATCHED_API FString Status(const FS08ConceptPasteAnimSpec& Anim, bool bMaskLoaded, bool bMaterialLoaded);
/** live | reduced | bench | flag: why the environment animation runs or stands (FS08EnvFxOptions, -ArtPreviewNoFx ignored). */
UNMATCHED_API FString FreezeReason(const FS08EnvFxOptions& Options);
/** 'ARTPREVIEW concept-paste anim profile=.. mask=.. lanterns=N synced=K wind=<amp>@<hz> mist=<opacity> frozen=0|1
 *  reason=.. use=0|1 status=..' */
UNMATCHED_API FString TraceLine(const FString& ProfileId, const FS08ConceptPasteAnimSpec& Anim,
                                const TArray<FS08ConceptLight>& Lights, const FString& MaskName, bool bUseAnim,
                                const FString& Status, bool bFrozen, const FString& Reason);
/** Writes the values into a MID of MI_ConceptPaste_Anim (bStatic: also the circles / wind / mist, else only AnimTime and
 *  the flickers - the per-tick part). */
UNMATCHED_API void SetParams(UMaterialInstanceDynamic& Mid, const FS08ConceptAnimParams& P, bool bStatic);
/** Live runs: the paste MIDs that need AnimTime (the sheet with the anim channels or flow regions, the sea layer with a
 *  sea flow) join the anim component; returns how many. */
UNMATCHED_API int32 AttachMids(US08ConceptPasteAnimComponent& Component, const FS08ConceptPasteSpec& Spec,
                               const FS08ConceptPasteRuntime& Runtime);
}  // namespace S08ConceptPasteAnim
