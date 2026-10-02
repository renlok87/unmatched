#include "S08HeroLight.h"
#include "Dom/JsonValue.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace {
bool HlKnownFields(const TSharedPtr<FJsonObject>& Object, const TArray<const TCHAR*>& Known, FString& OutUnknown) {
  for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : Object->Values) {
    bool bKnown = false;
    for (const TCHAR* K : Known) bKnown = bKnown || Pair.Key.Equals(K, ESearchCase::CaseSensitive);
    if (!bKnown) {
      OutUnknown = Pair.Key;
      return false;
    }
  }
  return true;
}

/** Optional number in [Min, Max] (absent = keeps Out). */
bool HlOptNumber(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, double Min, double Max, float& Out) {
  if (!Object->HasField(Field)) return true;
  double V = 0.0;
  if (!Object->TryGetNumberField(Field, V) || !FMath::IsFinite(V) || V < Min || V > Max) return false;
  Out = static_cast<float>(V);
  return true;
}

bool HlHexColor(const FString& Hex, FColor& Out) {
  if (Hex.Len() != 7 || Hex[0] != TEXT('#')) return false;
  for (int32 I = 1; I < 7; ++I) {
    if (!FChar::IsHexDigit(Hex[I])) return false;
  }
  Out = FColor::FromHex(Hex);
  Out.A = 255;
  return true;
}

bool ParseLayer(const FString& Ctx, const TSharedPtr<FJsonObject>& Object, FS08HeroLightLayer& Out, TArray<FString>& Errors) {
  FString Unknown;
  if (!HlKnownFields(Object, {TEXT("lux"), TEXT("colorSrgb"), TEXT("innerConeDeg"), TEXT("outerConeDeg"), TEXT("heightMul"),
                              TEXT("azimuthDeg"), TEXT("elevationDeg"), TEXT("radiusMul"), TEXT("note")},
                     Unknown)) {
    Errors.Add(FString::Printf(TEXT("%s: unknown field '%s'"), *Ctx, *Unknown));
    return false;
  }
  double Lux = 0.0;
  FString Color;
  if (!Object->TryGetNumberField(TEXT("lux"), Lux) || !FMath::IsFinite(Lux) || Lux <= 0.0 || Lux > 50.0 ||
      !Object->TryGetStringField(TEXT("colorSrgb"), Color) || !HlHexColor(Color, Out.ColorSrgb) ||
      !HlOptNumber(Object, TEXT("innerConeDeg"), 0.0, 80.0, Out.InnerConeDeg) ||
      !HlOptNumber(Object, TEXT("outerConeDeg"), 1.0, 80.0, Out.OuterConeDeg) ||
      !HlOptNumber(Object, TEXT("heightMul"), 0.3, 6.0, Out.HeightMul) ||
      !HlOptNumber(Object, TEXT("azimuthDeg"), -360.0, 360.0, Out.AzimuthDeg) ||
      !HlOptNumber(Object, TEXT("elevationDeg"), 5.0, 89.0, Out.ElevationDeg) ||
      !HlOptNumber(Object, TEXT("radiusMul"), 1.05, 4.0, Out.RadiusMul) || Out.InnerConeDeg > Out.OuterConeDeg) {
    Errors.Add(FString::Printf(TEXT("%s needs lux 0..50, colorSrgb #RRGGBB and optional innerConeDeg 0..80 <= outerConeDeg 1..80, heightMul 0.3..6, azimuthDeg -360..360, elevationDeg 5..89, radiusMul 1.05..4"),
                               *Ctx));
    return false;
  }
  Out.Lux = static_cast<float>(Lux);
  Out.bSet = true;
  return true;
}
}  // namespace

const TCHAR* S08HeroLightStateName(ES08HeroLightState State) {
  switch (State) {
    case ES08HeroLightState::Idle: return TEXT("idle");
    case ES08HeroLightState::Active: return TEXT("active");
    case ES08HeroLightState::Defeated: return TEXT("defeated");
    default: return TEXT("off");
  }
}

FString FS08HeroLightSpec::Signature() const {
  auto LayerText = [](const FS08HeroLightLayer& L) {
    return L.bSet ? FString::Printf(TEXT("%g/%s/%g/%g/%g/%g/%g/%g"), L.Lux, *L.ColorSrgb.ToHex(), L.InnerConeDeg, L.OuterConeDeg,
                                    L.HeightMul, L.AzimuthDeg, L.ElevationDeg, L.RadiusMul)
                  : FString(TEXT("-"));
  };
  return FString::Printf(TEXT("%d%d|%g|%g|%s|%s|%g|%g|%g|%g"), bSet ? 1 : 0, bEnabled ? 1 : 0, CameraAzimuthDeg, AimHeight,
                         *LayerText(Key), *LayerText(Rim), ActiveMul, BreathHz, BreathAmp, DefeatedMul);
}

namespace S08HeroLight {

bool Parse(const FString& ProfileId, const TSharedPtr<FJsonObject>& LightProfile, FS08HeroLightSpec& Out,
           TArray<FString>& Errors) {
  Out = FS08HeroLightSpec();
  const TSharedPtr<FJsonObject>* Block = nullptr;
  if (!LightProfile.IsValid() || !LightProfile->HasField(TEXT("heroLight"))) return true;
  const FString Ctx = FString::Printf(TEXT("light profile %s: heroLight"), *ProfileId);
  if (!LightProfile->TryGetObjectField(TEXT("heroLight"), Block) || !Block || !Block->IsValid()) {
    Errors.Add(Ctx + TEXT(" must be an object"));
    return false;
  }
  const TSharedPtr<FJsonObject>& B = *Block;
  FString Unknown;
  if (!HlKnownFields(B, {TEXT("enabled"), TEXT("note"), TEXT("cameraAzimuthDeg"), TEXT("aimHeight"), TEXT("key"), TEXT("rim"),
                         TEXT("states")},
                     Unknown)) {
    Errors.Add(FString::Printf(TEXT("%s: unknown field '%s'"), *Ctx, *Unknown));
    return false;
  }
  bool bEnabled = false;
  if (!B->TryGetBoolField(TEXT("enabled"), bEnabled)) {
    Errors.Add(Ctx + TEXT(" needs \"enabled\": true | false"));
    return false;
  }
  if (!HlOptNumber(B, TEXT("cameraAzimuthDeg"), -360.0, 360.0, Out.CameraAzimuthDeg) ||
      !HlOptNumber(B, TEXT("aimHeight"), 0.0, 1.5, Out.AimHeight)) {
    Errors.Add(Ctx + TEXT(": cameraAzimuthDeg -360..360, aimHeight 0..1.5"));
    return false;
  }
  const TSharedPtr<FJsonObject>* KeyObj = nullptr;
  if (!B->TryGetObjectField(TEXT("key"), KeyObj) || !KeyObj || !ParseLayer(Ctx + TEXT(".key"), *KeyObj, Out.Key, Errors)) {
    if (!KeyObj) Errors.Add(Ctx + TEXT(" needs a \"key\" layer"));
    return false;
  }
  const TSharedPtr<FJsonObject>* RimObj = nullptr;
  if (B->HasField(TEXT("rim")) &&
      (!B->TryGetObjectField(TEXT("rim"), RimObj) || !RimObj || !ParseLayer(Ctx + TEXT(".rim"), *RimObj, Out.Rim, Errors))) {
    if (!RimObj) Errors.Add(Ctx + TEXT(".rim must be an object"));
    return false;
  }
  for (const FS08HeroLightLayer* L : {&Out.Key, &Out.Rim}) {
    if (L->bSet && L->HeightMul < Out.AimHeight + 0.2f) {
      Errors.Add(FString::Printf(TEXT("%s: a layer heightMul %g must be >= aimHeight + 0.2 (%g): the light stands above the aim point"),
                                 *Ctx, L->HeightMul, Out.AimHeight + 0.2f));
      return false;
    }
  }
  const TSharedPtr<FJsonObject>* States = nullptr;
  if (B->HasField(TEXT("states"))) {
    if (!B->TryGetObjectField(TEXT("states"), States) || !States ||
        !HlKnownFields(*States, {TEXT("activeMul"), TEXT("breathHz"), TEXT("breathAmp"), TEXT("defeatedMul"), TEXT("note")}, Unknown) ||
        !HlOptNumber(*States, TEXT("activeMul"), 1.0, 3.0, Out.ActiveMul) ||
        !HlOptNumber(*States, TEXT("breathHz"), 0.0, 3.0, Out.BreathHz) ||
        !HlOptNumber(*States, TEXT("breathAmp"), 0.0, 0.5, Out.BreathAmp) ||
        !HlOptNumber(*States, TEXT("defeatedMul"), 0.0, 1.0, Out.DefeatedMul)) {
      Errors.Add(Ctx + TEXT(".states: activeMul 1..3, breathHz 0..3, breathAmp 0..0.5, defeatedMul 0..1 (no other fields)"));
      return false;
    }
  }
  Out.bEnabled = bEnabled;
  Out.bSet = true;
  return true;
}

FS08HeroLightPlacement Place(const FS08HeroLightSpec& Spec, const FS08HeroLightLayer& Layer, float FigureHeightUU) {
  FS08HeroLightPlacement P;
  const float H = FigureHeightUU > 1.0f ? FigureHeightUU : S08HeroLightSpec::DefaultFigureHeightUU;
  P.Aim = FVector(0.0, 0.0, Spec.AimHeight * H);
  const double Dz = FMath::Max(1.0, static_cast<double>(Layer.HeightMul - Spec.AimHeight) * H);
  const double Horizontal = Dz / FMath::Tan(FMath::DegreesToRadians(static_cast<double>(Layer.ElevationDeg)));
  const double Yaw = FMath::DegreesToRadians(static_cast<double>(Spec.CameraAzimuthDeg + Layer.AzimuthDeg));
  P.Location = P.Aim + FVector(FMath::Cos(Yaw) * Horizontal, FMath::Sin(Yaw) * Horizontal, Dz);
  P.Rotation = (P.Aim - P.Location).Rotation();
  P.DistanceUU = static_cast<float>(FVector::Dist(P.Aim, P.Location));
  // inverse-square: E (lux) = I (cd) / d (m)^2
  P.Candelas = Layer.Lux * FMath::Square(P.DistanceUU / 100.0f);
  P.AttenuationRadiusUU = P.DistanceUU * Layer.RadiusMul;
  return P;
}

float StateMultiplier(const FS08HeroLightSpec& Spec, ES08HeroLightState State, double TimeS, bool bFrozen, float Phase) {
  switch (State) {
    case ES08HeroLightState::Idle: return 1.0f;
    case ES08HeroLightState::Defeated: return Spec.DefeatedMul;
    case ES08HeroLightState::Active: {
      if (bFrozen || Spec.BreathHz <= 0.0f || Spec.BreathAmp <= 0.0f) return Spec.ActiveMul;
      const double W = 2.0 * UE_DOUBLE_PI * Spec.BreathHz * TimeS + Phase;
      return static_cast<float>(Spec.ActiveMul * (1.0 + Spec.BreathAmp * FMath::Sin(W)));
    }
    default: return 0.0f;
  }
}

int32 LayersForBoard(const FS08HeroLightSpec& Spec, int32 LitFigures) {
  const int32 Layers = FMath::Min(Spec.Layers(), S08HeroLightSpec::MaxLightsPerFigure);
  if (Layers <= 0 || LitFigures <= 0) return Layers;
  if (LitFigures * Layers <= S08HeroLightSpec::MaxLightsPerBoard) return Layers;
  return 1;  // the key only; the caller lights at most MaxLightsPerBoard figures
}

bool OptOut() { return FParse::Param(FCommandLine::Get(), S08HeroLightSpec::OptOutFlagName); }

}  // namespace S08HeroLight
