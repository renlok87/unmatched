// Art Tuner M2: the board actor side of the panel (AS08BoardActor::ApplyTunedArtData, S08BoardActor.h). The tuned values
// go onto the components the first build spawned - no respawn, no Niagara warm-up, the figures keep their animation -
// except for the rebuild scope, which takes the normal live-tune path (RequestFullRebuild + the caller's rebuild).
#include "S08ArtTuner.h"
#include "S08BoardActor.h"
#include "S08Render.h"
#include "S08TraceLog.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/PointLight.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/SkyLight.h"
#include "Materials/MaterialInstanceDynamic.h"

bool AS08BoardActor::ApplyTunedArtData(const FS08BoardArtData& Data, uint8 Scopes, const FString& ProfilesSource,
                                       FString& OutNote) {
  const ES08TunerScope S = static_cast<ES08TunerScope>(Scopes);
  const FS08BoardArtProfile* Board =
      Data.Boards.FindByPredicate([&](const FS08BoardArtProfile& P) { return P.Id == ActiveProfile.Id; });
  if (!bArtActive || !Board) {
    OutNote = TEXT("no active art profile in the tuned document");
    return false;
  }
  const FString Sha = ArtData.SourceSha256;
  ArtData = Data;
  if (ArtData.SourceSha256.IsEmpty()) ArtData.SourceSha256 = Sha;
  // the board profile copy the build reads (the surface may have been downgraded at the build: keep it)
  const ES08BoardSurface Surface = ActiveProfile.Surface;
  ActiveProfile = *Board;
  ActiveProfile.Surface = Surface;
  AppliedRender.ProfilesSource = ProfilesSource;
  const FS08LightProfile* Light = ArtData.LightFor(ActiveProfile);
  bool bRebuild = EnumHasAnyFlags(S, ES08TunerScope::Rebuild);
  TArray<FString> Done;
  if (!bRebuild && Light) {
    if (EnumHasAnyFlags(S, ES08TunerScope::HeroLight)) {
      UpdateHeroLights();
      Done.Add(TEXT("heroLight"));
    }
    if (EnumHasAnyFlags(S, ES08TunerScope::ProfileLights)) {
      ApplyTunedLights(*Light);
      Done.Add(TEXT("profileLights"));
    }
    if (EnumHasAnyFlags(S, ES08TunerScope::MapGrade)) {
      ApplyMapGrade(*Light);
      Done.Add(TEXT("mapGrade"));
    }
    if (EnumHasAnyFlags(S, ES08TunerScope::ConceptLights)) {
      if (ApplyTunedConceptLights()) {
        Done.Add(TEXT("conceptLights"));
      } else {
        bRebuild = true;
      }
    }
    if (EnumHasAnyFlags(S, ES08TunerScope::Materials)) {
      if (ApplyMaterialOverrides()) {
        Done.Add(TEXT("materials"));
      } else {
        bRebuild = true;
      }
    }
  }
  if (bRebuild) {
    RequestFullRebuild();
    Done.Add(TEXT("rebuild"));
  }
  OutNote = FString::Join(Done, TEXT("+"));
  return bRebuild;
}

void AS08BoardActor::ApplyTunedLights(const FS08LightProfile& Light) {
  const bool bLegacy = S08LegacyRender();
  int32 Point = 0;
  for (AActor* Actor : ArtLights) {
    if (ADirectionalLight* Dir = Cast<ADirectionalLight>(Actor)) {
      UDirectionalLightComponent* C = Cast<UDirectionalLightComponent>(Dir->GetLightComponent());
      if (!C || !Light.bHasDirectional) continue;
      C->SetIntensity(Light.Directional.Intensity);
      if (Light.Directional.bHasColor) C->SetLightColor(Light.Directional.Color);
      if (Light.KeyShadow.bSet && !bLegacy) {
        C->SetDynamicShadowDistanceMovableLight(Light.KeyShadow.DistanceUU);
        C->SetDynamicShadowCascades(Light.KeyShadow.Cascades);
        C->ContactShadowLength = Light.KeyShadow.ContactShadowLength;
        C->MarkRenderStateDirty();
        AppliedRender.KeyShadow = FString::Printf(TEXT("csm-%.0fuu-%dc-contact%.3f"), Light.KeyShadow.DistanceUU,
                                                  Light.KeyShadow.Cascades, Light.KeyShadow.ContactShadowLength);
      }
    } else if (APointLight* PointActor = Cast<APointLight>(Actor)) {
      UPointLightComponent* C = Cast<UPointLightComponent>(PointActor->GetLightComponent());
      if (C && Light.Points.IsValidIndex(Point)) {
        const FS08LightSpec& Spec = Light.Points[Point];
        C->SetIntensity(Spec.Intensity);
        C->SetAttenuationRadius(Spec.RadiusUU);
        if (Spec.bHasColor) C->SetLightColor(Spec.Color);
      }
      ++Point;
    } else if (ASkyLight* Sky = Cast<ASkyLight>(Actor)) {
      if (USkyLightComponent* C = Sky->GetLightComponent()) {
        C->SetIntensity(Light.Sky.Intensity);
        C->SetLightColor(Light.Sky.Color);
        AppliedRender.SkyIntensity = Light.Sky.Intensity;
      }
    } else if (AExponentialHeightFog* Fog = Cast<AExponentialHeightFog>(Actor)) {
      if (UExponentialHeightFogComponent* C = Fog->GetComponent()) {
        const FS08FogSpec& F = Light.Fog;
        Fog->SetActorLocation(FVector(0.0, 0.0, F.HeightZ));
        C->SetFogDensity(F.Density);
        C->SetFogHeightFalloff(F.HeightFalloff);
        C->SetFogInscatteringColor(F.Color);
        C->SetStartDistance(F.StartDistanceUU);
        C->SetEndDistance(F.EndDistanceUU);
        C->SetFogMaxOpacity(F.MaxOpacity);
      }
    } else if (APostProcessVolume* Volume = Cast<APostProcessVolume>(Actor)) {
      FPostProcessSettings& P = Volume->Settings;
      P.AutoExposureMinBrightness = Light.Exposure.MinBrightness;
      P.AutoExposureMaxBrightness = Light.Exposure.MaxBrightness;
      P.AutoExposureBias = Light.Exposure.Bias;
      AppliedRender.ExposureMin = Light.Exposure.MinBrightness;
      AppliedRender.ExposureMax = Light.Exposure.MaxBrightness;
      AppliedRender.ExposureBias = Light.Exposure.Bias;
      AppliedRender.Ev100 = Light.Exposure.Ev100;
    }
  }
}

bool AS08BoardActor::ApplyTunedConceptLights() {
  if (!IsConceptPasteOn()) return true;  // no lit3d lights on this board now: nothing to push
  const TArray<FS08ConceptLight>& Specs = ActiveProfile.ConceptPaste.LightsFor(ConceptMode.Kind);
  if (Specs.Num() != ConceptLights.Num()) return false;  // another light count: the build spawns them
  if (ConceptInputs.bLightsOff) return true;            // -ArtPreviewLightsOff keeps them zeroed
  const bool bFrozen = GetFxOptions().bFreeze;
  for (int32 I = 0; I < Specs.Num(); ++I) {
    UPointLightComponent* L = ConceptLights[I].Get();
    if (!L) continue;
    const FS08ConceptLight& Spec = Specs[I];
    L->SetIntensity(Spec.IntensityCd);
    L->SetAttenuationRadius(Spec.RadiusUU);
    L->SetLightFColor(Spec.Color);
    const bool bFlicker = Spec.FlickerAmp > 0.0f && Spec.FlickerHz > 0.0f;
    if (ConceptAnim) {
      ConceptAnim->UpdateFlicker(L, Spec);
    } else if (bFlicker && !bFrozen) {
      return false;  // live run without an anim component yet: the build creates it
    }
  }
  return true;
}

bool AS08BoardActor::ApplyMaterialOverrides() {
  const bool bLit3d = IsConceptPasteOn() && ConceptMode.Kind == ES08ConceptKind::Lit3d;
  const TArray<FS08ConceptMaterialOverride> None;
  const TArray<FS08ConceptMaterialOverride>& Overrides = bLit3d ? ActiveProfile.ConceptPaste.Lit3d.MaterialOverrides : None;
  if (Overrides.IsEmpty() && TunedMaterialMids.IsEmpty()) return true;
  // 1) every MID written before gets its parent's values back (a look that left the block is undone)
  auto RestoreFromParent = [](UMaterialInstanceDynamic* Mid) {
    const UMaterialInterface* Parent = Mid ? Mid->Parent.Get() : nullptr;
    if (!Parent) return;
    for (const TCHAR* Name : S08ConceptPasteSpec::TintParamNames) {
      FLinearColor V;
      if (Parent->GetVectorParameterValue(FHashedMaterialParameterInfo(Name), V)) Mid->SetVectorParameterValue(Name, V);
    }
    for (const S08ConceptPaste::FS08MaterialScalarSpec& S : S08ConceptPaste::MaterialScalarSpecs()) {
      float V = 0.0f;
      if (Parent->GetScalarParameterValue(FHashedMaterialParameterInfo(S.Param), V)) Mid->SetScalarParameterValue(S.Param, V);
    }
  };
  for (const TWeakObjectPtr<UMaterialInstanceDynamic>& W : TunedMaterialMids) RestoreFromParent(W.Get());
  TunedMaterialMids.Reset();
  // 2) the overrides, per slot of every env prop whose material chain names a look of the block
  TMap<FString, int32> Slots;
  int32 Params = 0;
  for (UStaticMeshComponent* Prop : EnvProps) {
    if (!Prop) continue;
    for (int32 Slot = 0; Slot < Prop->GetNumMaterials(); ++Slot) {
      UMaterialInterface* Material = Prop->GetMaterial(Slot);
      const FString Look = S08ConceptPaste::LookOfMaterial(Material);
      const FS08ConceptMaterialOverride* O =
          Look.IsEmpty() ? nullptr : Overrides.FindByPredicate([&](const FS08ConceptMaterialOverride& X) { return X.Look == Look; });
      if (!O) continue;
      UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(Material);
      if (!Mid) Mid = Prop->CreateDynamicMaterialInstance(Slot, Material);
      const UMaterialInterface* Parent = Mid ? Mid->Parent.Get() : nullptr;
      if (!Parent) continue;
      for (const TCHAR* Name : S08ConceptPasteSpec::TintParamNames) {
        FLinearColor V;
        if (!Parent->GetVectorParameterValue(FHashedMaterialParameterInfo(Name), V)) continue;
        const FLinearColor Tint = O->bTint ? O->Tint : FLinearColor::White;
        Mid->SetVectorParameterValue(Name, FLinearColor(V.R * O->TintGain * Tint.R, V.G * O->TintGain * Tint.G,
                                                        V.B * O->TintGain * Tint.B, V.A));
        ++Params;
      }
      for (const TPair<FName, float>& S : O->Scalars) {
        float Base = 0.0f;
        if (!Parent->GetScalarParameterValue(FHashedMaterialParameterInfo(S.Key), Base)) continue;
        Mid->SetScalarParameterValue(S.Key, S.Value);
        ++Params;
      }
      TunedMaterialMids.AddUnique(Mid);
      ++Slots.FindOrAdd(Look);
    }
  }
  TArray<FString> Parts, Missing;
  for (const FS08ConceptMaterialOverride& O : Overrides) {
    const int32* N = Slots.Find(O.Look);
    if (!N) Missing.Add(O.Look);
    Parts.Add(FString::Printf(TEXT("%s:%d(gain %.2f%s%s)"), *O.Look, N ? *N : 0, O.TintGain,
                              O.bTint ? *FString::Printf(TEXT(", tint %.2f/%.2f/%.2f"), O.Tint.R, O.Tint.G, O.Tint.B) : TEXT(""),
                              O.Scalars.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(", %d scalars"), O.Scalars.Num())));
  }
  const FString Key = FString::Join(Parts, TEXT(" ")) + TEXT("|") + FString::Join(Missing, TEXT(","));
  if (Key != MaterialOverridesTraceKey) {
    // one line per distinct result (a slider drag does not flood the trace)
    MaterialOverridesTraceKey = Key;
    FS08Trace::Write(FString::Printf(TEXT("ARTPREVIEW concept-scene materials looks=%d mids=%d params=%d %s missing=%s"),
                                     Overrides.Num(), TunedMaterialMids.Num(), Params, Parts.IsEmpty() ? TEXT("-") : *FString::Join(Parts, TEXT(" ")),
                                     Missing.IsEmpty() ? TEXT("-") : *FString::Join(Missing, TEXT(","))));
  }
  return true;
}
