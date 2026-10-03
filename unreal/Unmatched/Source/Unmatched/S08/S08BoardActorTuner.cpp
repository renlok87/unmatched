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

bool AS08BoardActor::ApplyMaterialOverrides() { return true; }  // M4
