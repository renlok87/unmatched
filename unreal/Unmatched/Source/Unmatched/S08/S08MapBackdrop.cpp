#include "S08MapBackdrop.h"
#include "S08TraceLog.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"

namespace S08MapBackdrop {
namespace {
UStaticMeshComponent* SpawnPart(AActor& Owner, USceneComponent* Root, UStaticMesh* Plane, const FName Name,
                                UMaterialInterface* Material, const FTransform& Relative) {
  // Unique names: a board shown again must not reuse a destroyed part's name (MistComponentName is the base).
  UStaticMeshComponent* Part =
      NewObject<UStaticMeshComponent>(&Owner, MakeUniqueObjectName(&Owner, UStaticMeshComponent::StaticClass(), Name));
  Part->SetupAttachment(Root);
  Part->SetStaticMesh(Plane);
  Part->SetCollisionEnabled(ECollisionEnabled::NoCollision);
  Part->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
  Part->SetGenerateOverlapEvents(false);
  Part->SetCanEverAffectNavigation(false);
  // Lights nothing and is seen only by the main view: unlit material, and no shadow / GI / DF / capture / RT presence.
  Part->SetCastShadow(false);
  Part->SetAffectDynamicIndirectLighting(false);
  Part->SetAffectIndirectLightingWhileHidden(false);
  Part->SetAffectDistanceFieldLighting(false);
  Part->SetVisibleInRayTracing(false);
  Part->bVisibleInReflectionCaptures = false;
  Part->bVisibleInRealTimeSkyCaptures = false;
  Part->SetReceivesDecals(false);
  Part->SetTranslucentSortPriority(S08MapSurfaceSpec::BackdropTranslucencySortPriority);
  Part->SetRelativeTransform(Relative);
  Part->SetMaterial(0, Material);
  Part->RegisterComponent();
  return Part;
}

UMaterialInterface* LoadBase(const TCHAR* Path) {
  return LoadObject<UMaterialInterface>(nullptr, Path, nullptr, LOAD_NoWarn);
}
}  // namespace

FName MistComponentName(int32 Index) { return FName(*FString::Printf(TEXT("MapBackdropMist%d"), Index)); }

FName MoonComponentName() { return FName(TEXT("MapBackdropMoon")); }

void Clear(TArray<TObjectPtr<UStaticMeshComponent>>& Parts, FS08BackdropRuntime& Runtime) {
  for (UStaticMeshComponent* Part : Parts) {
    if (Part) Part->DestroyComponent();
  }
  Parts.Reset();
  Runtime.ProfileId.Reset();
  Runtime.MistPlanes = 0;
  Runtime.bMoon = false;
  Runtime.Status = TEXT("off");
}

void Update(bool bActive, const FString& ProfileId, const FS08BackdropSpec& Spec, const FVector2D& MapHalf,
            AActor& Owner, USceneComponent* Root, UStaticMesh* Plane, TArray<TObjectPtr<UStaticMeshComponent>>& Parts,
            FS08BackdropRuntime& Runtime) {
  using namespace S08MapSurfaceSpec;
  if (!bActive || !Spec.bSet) {
    // A grid-only run never applied anything: no component, no line (grids stay bit for bit).
    if (!Runtime.bTraced && Parts.IsEmpty()) return;
    const bool bHad = !Parts.IsEmpty();
    Clear(Parts, Runtime);
    if (bHad) FS08Trace::Write(TEXT("ARTPREVIEW backdrop cleared (no map-image backdrop on this board)"));
    return;
  }
  if (Runtime.ProfileId == ProfileId && Runtime.Status == TEXT("ok") && !Parts.IsEmpty()) return;  // same board again
  Clear(Parts, Runtime);
  Runtime.bTraced = true;
  Runtime.ProfileId = ProfileId;
  if (!Plane) {
    Runtime.Status = TEXT("missing-plane");
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW backdrop profile=%s status=missing-plane (no part)"), *ProfileId));
    return;
  }
  UMaterialInterface* MistBase = Spec.Mist.IsEmpty() ? nullptr : LoadBase(BackdropMistMaterialPath);
  UMaterialInterface* MoonBase = Spec.Moon.bSet ? LoadBase(BackdropMoonMaterialPath) : nullptr;
  if ((!Spec.Mist.IsEmpty() && !MistBase) || (Spec.Moon.bSet && !MoonBase)) {
    Runtime.Status = TEXT("missing-material");
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW backdrop profile=%s status=missing-material mist=%s moon=%s (run tools/art/map_surface/ue_import_map_surface.py) -> no backdrop"),
        *ProfileId, Spec.Mist.IsEmpty() ? TEXT("-") : (MistBase ? TEXT("ok") : BackdropMistMaterialPath),
        !Spec.Moon.bSet ? TEXT("-") : (MoonBase ? TEXT("ok") : BackdropMoonMaterialPath)));
    return;
  }
  for (int32 I = 0; I < Spec.Mist.Num(); ++I) {
    const FS08BackdropMistSpec& M = Spec.Mist[I];
    UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(MistBase, &Owner);
    Mid->SetVectorParameterValue(FName(ParamBackdropTint), M.Color);
    Mid->SetScalarParameterValue(FName(ParamBackdropOpacity), M.Opacity);
    Mid->SetVectorParameterValue(FName(ParamBackdropSize), FLinearColor(static_cast<float>(M.HalfUU.X * 2.0), static_cast<float>(M.HalfUU.Y * 2.0), 0.0f, 0.0f));
    Mid->SetVectorParameterValue(FName(ParamBackdropPan), FLinearColor(static_cast<float>(M.PanUUPerSec.X), static_cast<float>(M.PanUUPerSec.Y), 0.0f, 0.0f));
    Mid->SetScalarParameterValue(FName(ParamBackdropNoiseScale), M.NoiseScaleUU);
    Mid->SetScalarParameterValue(FName(ParamBackdropEdgeFade), M.EdgeFade);
    Mid->SetScalarParameterValue(FName(ParamBackdropCoverage), M.Coverage);
    Mid->SetScalarParameterValue(FName(ParamBackdropSeed), M.Seed);
    Parts.Add(SpawnPart(Owner, Root, Plane, MistComponentName(I), Mid, S08BackdropMistTransform(M)));
    ++Runtime.MistPlanes;
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW backdrop mist profile=%s index=%d z=%.0f center=(%.0f,%.0f) half=(%.0f,%.0f) color=(%.3f,%.3f,%.3f) opacity=%.2f noiseUU=%.0f pan=(%.1f,%.1f) edgeFade=%.2f coverage=%.2f seed=%.0f fog=0 lit=0"),
        *ProfileId, I, M.ZUU, M.CenterUU.X, M.CenterUU.Y, M.HalfUU.X, M.HalfUU.Y, M.Color.R, M.Color.G, M.Color.B,
        M.Opacity, M.NoiseScaleUU, M.PanUUPerSec.X, M.PanUUPerSec.Y, M.EdgeFade, M.Coverage, M.Seed));
  }
  if (Spec.Moon.bSet) {
    const FS08BackdropMoonSpec& M = Spec.Moon;
    UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(MoonBase, &Owner);
    Mid->SetVectorParameterValue(FName(ParamBackdropTint), M.Color);
    Mid->SetScalarParameterValue(FName(ParamBackdropIntensity), M.Intensity);
    Mid->SetScalarParameterValue(FName(ParamBackdropSoftness), M.Softness);
    Mid->SetScalarParameterValue(FName(ParamBackdropDiscRadius), M.DiscRadius);
    Mid->SetScalarParameterValue(FName(ParamBackdropDiscIntensity), M.DiscIntensity);
    double TopZ = 0.0;
    const FTransform Card = S08BackdropMoonTransform(M, MapHalf, &TopZ);
    Parts.Add(SpawnPart(Owner, Root, Plane, MoonComponentName(), Mid, Card));
    Runtime.bMoon = true;
    const FVector C = Card.GetTranslation();
    FS08Trace::Write(FString::Printf(
        TEXT("ARTPREVIEW backdrop moon profile=%s anchor=(%.2f,%.2f) farViewUU=%.1f depthUU=%.0f at=(%.0f,%.0f,%.0f) topZ=%.0f diameterUU=%.0f color=(%.3f,%.3f,%.3f) intensity=%.2f softness=%.2f disc=%.2f/%.2f fog=0 lit=0"),
        *ProfileId, M.ScreenAnchor.X, M.ScreenAnchor.Y, S08BackdropFarViewDistanceUU(MapHalf), M.DepthUU, C.X, C.Y, C.Z,
        TopZ, M.DiameterUU, M.Color.R, M.Color.G, M.Color.B, M.Intensity, M.Softness, M.DiscRadius, M.DiscIntensity));
  }
  Runtime.Status = TEXT("ok");
  FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW backdrop profile=%s status=ok mist=%d moon=%d maxZ=%.0f sortPriority=%d"),
                                   *ProfileId, Runtime.MistPlanes, Runtime.bMoon ? 1 : 0, BackdropMaxZ,
                                   BackdropTranslucencySortPriority));
}
}  // namespace S08MapBackdrop
