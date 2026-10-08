// FX-03 (VS-6 Z-2): see S08CueFxSpawner.h. Everything spawns on the CPU with the AutoRelease pool; the seed of
// FX-04 lives in the system assets themselves (fx_audit.py enforces RandomSeed = CRC32 of the name).
#include "S08CueFxSpawner.h"

#include "Engine/World.h"
#include "TimerManager.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"
#include "NiagaraWorldManager.h"
#include "S08CueFx.h"
#include "../S08TraceLog.h"

namespace {
// VS-6 FX-37 (ВР-VS6-48): a cue effect is a print on the scene - it casts no shadow and stays out of Lumen / distance
// fields (the vortex rings mesh of NS_FX_MedusaVortex put a Nanite shadow pass of ~0.25 ms into every frame).
void SceneNeutral(UNiagaraComponent* C) {
  if (!C) return;
  C->SetCastShadow(false);
  C->SetAffectDynamicIndirectLighting(false);
  C->SetAffectDistanceFieldLighting(false);
}
}  // namespace

bool US08CueFxSpawnerComponent::Prewarm() {
  UWorld* World = GetWorld();
  if (!World) return false;
  bPrewarmDone = true;
  const double T0 = FPlatformTime::Seconds();
  Prewarmed.Reset();
  if (!S08CueFx::FxEnabled()) {
    // -S08FxLegacy: nothing will show, so nothing is loaded or kept (FX-37: the rollback still primed 7 systems)
    FS08Trace::Write(TEXT("FX prewarm systems=0 ms=0 reason=legacy"));
    return true;
  }
  TSet<FString> Distinct;
  for (const S08CueFx::FEntry& E : S08CueFx::Registry()) {
    if (E.System.IsEmpty() || !E.bPrewarm || Distinct.Contains(E.System)) continue;
    Distinct.Add(E.System);
    UNiagaraSystem* System = LoadObject<UNiagaraSystem>(nullptr, *E.System);
    if (!System) continue;  // the combat systems arrive with FX-13..FX-32 (cue-table status: missing)
    Prewarmed.Add(System);
    // PoolPrimeSize comes from the system's effect type (fx_import writes the caps of ВР-25); the pool primes
    // through the world manager so the first real show takes a warmed component.
    if (FNiagaraWorldManager* Manager = FNiagaraWorldManager::Get(World)) {
      if (UNiagaraComponentPool* Pool = Manager->GetComponentPool()) Pool->PrimePool(System, World);
    }
  }
  // one invisible pass far below the board so the first real frame has the PSO of every renderer; the systems freeze
  // their quads by age (no completion), so the pass is ended explicitly after 0.5 s (FX-37: they stayed alive)
  TArray<TWeakObjectPtr<UNiagaraComponent>> Pass;
  for (const TObjectPtr<UNiagaraSystem>& System : Prewarmed) {
    UNiagaraComponent* C = UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, FVector(0.0f, 0.0f, -1000000.0f));
    SceneNeutral(C);
    if (C) Pass.Add(C);
  }
  if (Pass.Num() > 0) {
    FTimerHandle Handle;
    World->GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(this, [Pass]() {
      int32 N = 0;
      for (const TWeakObjectPtr<UNiagaraComponent>& C : Pass) {
        if (!C.IsValid()) continue;
        C->DeactivateImmediate();  // completes the system: an auto-destroy component is destroyed right here
        ++N;
        if (C.IsValid()) C->DestroyComponent();
      }
      FS08Trace::Write(FString::Printf(TEXT("FX prewarm pass ended components=%d"), N));
    }), 0.5f, false);
  }
  const int32 Ms = FMath::RoundToInt((FPlatformTime::Seconds() - T0) * 1000.0);
  FS08Trace::Write(FString::Printf(TEXT("FX prewarm systems=%d ms=%d"), Prewarmed.Num(), Ms));
  return true;
}

UNiagaraComponent* US08CueFxSpawnerComponent::Spawn(const FString& CueId, const FTransform& Transform,
                                                    USceneComponent* AttachTo, const FString& HeroKey) {
  UWorld* World = GetWorld();
  const S08CueFx::FEntry* E = S08CueFx::Find(CueId, HeroKey);
  if (!World || !E || !S08CueFx::FxEnabled()) return nullptr;
  UNiagaraSystem* System = LoadObject<UNiagaraSystem>(nullptr, *E->System);
  if (!System) {
    // the fallback state of the table (status: missing until FX-13..FX-32): nothing spawns, one Warning
    UE_LOG(LogTemp, Warning, TEXT("S08CueFx: %s system %s missing (fallback)"), *CueId, *E->System);
    return nullptr;
  }
  UNiagaraComponent* Component = nullptr;
  if (E->bSocket && AttachTo) {
    Component = UNiagaraFunctionLibrary::SpawnSystemAttached(System, AttachTo, *E->Socket, Transform.GetLocation(),
                                                             Transform.Rotator(), Transform.GetScale3D(),
                                                             EAttachLocation::KeepWorldPosition,
                                                             /*bAutoDestroy=*/true, ENCPoolMethod::AutoRelease);
  } else {
    Component = UNiagaraFunctionLibrary::SpawnSystemAtLocation(World, System, Transform.GetLocation(),
                                                               Transform.Rotator(), Transform.GetScale3D(),
                                                               /*bAutoDestroy=*/true, /*bAutoActivate=*/true,
                                                               ENCPoolMethod::AutoRelease);
  }
  if (Component) {
    Component->SetTranslucentSortPriority(S08CueFx::TranslucentSortPriority);
    SceneNeutral(Component);
    // FX-04: the seed lives in the system asset (RandomSeed = CRC32 of the name, fx_audit.py); a "RandomSeed" user
    // parameter would do nothing on a system without one, so none is written here (the Z-2 review, fix 8).
    // ВР-Z2-06: GradeScale / GradePow land as user-vector overrides - a system that does not read them runs
    // the neutral plain inverse ACES of M_FX_Print's defaults (what the paste shows without a fit)
    Component->SetColorParameter(TEXT("GradeScale"), GradeScale);
    Component->SetColorParameter(TEXT("GradePow"), GradePow);
    Track(Component);
  }
  return Component;
}

UNiagaraComponent* US08CueFxSpawnerComponent::SpawnSystem(const FString& SystemPath, const FTransform& Transform) {
  UWorld* World = GetWorld();
  if (!World || !S08CueFx::FxEnabled()) return nullptr;
  UNiagaraSystem* System = LoadObject<UNiagaraSystem>(nullptr, *SystemPath);
  if (!System) {
    UE_LOG(LogTemp, Warning, TEXT("S08CueFx: system %s missing"), *SystemPath);
    return nullptr;
  }
  UNiagaraComponent* Component = UNiagaraFunctionLibrary::SpawnSystemAtLocation(
      World, System, Transform.GetLocation(), Transform.Rotator(), Transform.GetScale3D(),
      /*bAutoDestroy=*/true, /*bAutoActivate=*/true, ENCPoolMethod::AutoRelease);
  if (Component) {
    Component->SetTranslucentSortPriority(S08CueFx::TranslucentSortPriority);
    SceneNeutral(Component);
    Component->SetColorParameter(TEXT("GradeScale"), GradeScale);
    Component->SetColorParameter(TEXT("GradePow"), GradePow);
    Track(Component);
  }
  return Component;
}

void US08CueFxSpawnerComponent::Track(UNiagaraComponent* Component) {
  // the finished / released ones go first (a pooled component comes back inactive)
  Live.RemoveAll([](const TWeakObjectPtr<UNiagaraComponent>& C) { return !C.IsValid() || !C->IsActive(); });
  Live.Add(Component);
}

int32 US08CueFxSpawnerComponent::NumLiveSystems() const {
  int32 N = 0;
  for (const TWeakObjectPtr<UNiagaraComponent>& C : Live) N += C.IsValid() && C->IsActive() ? 1 : 0;
  return N;
}

int32 US08CueFxSpawnerComponent::CutAllForReconnect(int32 InRecoveredSeq) {
  int32 N = 0;
  for (const TWeakObjectPtr<UNiagaraComponent>& C : Live) {
    if (!C.IsValid() || !C->IsActive()) continue;
    C->Deactivate();  // CUE-018 (FX-36): the system fades out by its particles' life, no new emission
    ++N;
  }
  Live.Reset();
  RecoveredSeq = FMath::Max(RecoveredSeq, InRecoveredSeq);
  FS08Trace::Write(FString::Printf(TEXT("FX cut reason=reconnect recovered_seq=%d systems=%d"), InRecoveredSeq, N));
  return N;
}

void US08CueFxSpawnerComponent::SetGrade(const FLinearColor& Scale, const FLinearColor& Pow, const TCHAR* Source) {
  GradeScale = Scale;
  GradePow = Pow;
  FS08Trace::Write(FString::Printf(TEXT("FX grade scale=(%.3f,%.3f,%.3f) pow=(%.3f,%.3f,%.3f) source=%s"),
                                   Scale.R, Scale.G, Scale.B, Pow.R, Pow.G, Pow.B, Source));
}
