// FX-03 (VS-6 Z-2): the game-side FX adapter - prewarm, spawn and the honest trace of S08CueFx registry
// systems. A UActorComponent of AS08FlowGameMode (created there, one line); CUE-DISPATCHER's rules stay in the
// dispatcher - this class only shows what a plan asks, once, without hitching:
//   * prewarm at the match load: LoadSynchronous of every registry system that exists + FNiagaraWorldManager::
//     PrimePoolForAllWorlds (PoolPrimeSize = the effect type's instance cap) + one invisible spawn far below
//     the board for the PSO; traced "FX prewarm systems=<n> ms=<t>" (ВР-FX19: the FX service lines carry the
//     "FX " prefix, so the "CUE " gates never read them);
//   * spawn: SpawnSystemAtLocation / SpawnSystemAttached with ENCPoolMethod::AutoRelease, never from
//     Blueprint, never GPU (CUE-DISPATCHER §3); a missing asset traces the Warning of the fallback state and
//     returns nullptr (the combat systems arrive with FX-13..FX-32);
//   * grade: the inverse tone curve of M_FX_Print runs on GradeScale/GradePow (1,1,1) = the plain approximate
//     inverse ACES (ВР-Z2-06: a per-component material override is not possible for Niagara renderers; the
//     systems that need the profile's fitScale/fitPower expose them as the user vectors "GradeScale" /
//     "GradePow" and SetGrade writes those; the neutral default is what M_ConceptPaste shows without a fit).
#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "S08CueFxSpawner.generated.h"

class UNiagaraSystem;
class UNiagaraComponent;

UCLASS(ClassGroup = (S08), MinimalAPI)
class US08CueFxSpawnerComponent : public UActorComponent {
  GENERATED_BODY()

public:
  /** The systems of the registry that exist (loaded), with their pool primed; traced as one FX prewarm line. */
  bool Prewarm();

  /** Shows the registry entry of CueId: at the world location (attach "world") or on the component's socket.
   *  Null + a Warning trace when the asset is missing (fallback) or FX is rolled back (-S08FxLegacy). */
  UNiagaraComponent* Spawn(const FString& CueId, const FTransform& Transform, USceneComponent* AttachTo = nullptr,
                           const FString& HeroKey = FString());

  /** Spawns a system by path (the bench placard; CUE shows go through Spawn). Null when missing / rolled back. */
  UNiagaraComponent* SpawnSystem(const FString& SystemPath, const FTransform& Transform);
  /** The grade of the active board profile for the systems that expose GradeScale / GradePow (FX grade line). */
  void SetGrade(const FLinearColor& Scale, const FLinearColor& Pow, const TCHAR* Source);

  /** How many registry systems the prewarm loaded (the test's check). */
  int32 GetPrewarmedCount() const { return Prewarmed.Num(); }
  /** The grade of the active profile (FX-02: the quads of the bench placard take it as a MID override). */
  const FLinearColor& GetGradeScale() const { return GradeScale; }
  const FLinearColor& GetGradePow() const { return GradePow; }

private:
  UPROPERTY(Transient)
  TArray<TObjectPtr<UNiagaraSystem>> Prewarmed;
  FLinearColor GradeScale = FLinearColor(1.0f, 1.0f, 1.0f, 0.0f);
  FLinearColor GradePow = FLinearColor(1.0f, 1.0f, 1.0f, 0.0f);
};
