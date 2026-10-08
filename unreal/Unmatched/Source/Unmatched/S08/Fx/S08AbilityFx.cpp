// VS-6 F3: the world-free numbers of FX-26 / FX-27 / FX-28 / FX-30 / FX-32 - see S08AbilityFx.h.
#include "S08AbilityFx.h"

#include "../S08HudTokens.generated.h"
#include "S08CombatFx.h"
#include "S08CueFx.h"

namespace S08AbilityFx {

int32 EmberCount(float DissolveSeconds) {
  const int32 N = FMath::RoundToInt(FMath::Max(0.0f, DissolveSeconds) * 1000.0f * EmbersPer100Ms / 100.0f);
  return FMath::Clamp(N, 0, MaxEmbers);
}

float EmbersQuadSideUU(float FigureHeightUU) {
  return FMath::Max(FigureHeightUU, 10.0f) + EmbersTopMarginUU + EmbersBaseMarginUU;
}

FTransform EmbersQuad(const FVector& Base, float FigureHeightUU, float RadiusUU, const FVector& Camera) {
  const float Side = EmbersQuadSideUU(FigureHeightUU);
  FVector Centre = Base + S08CombatFx::CameraQuadUp(Base, Camera) * (0.5f * Side - EmbersBaseMarginUU);
  FVector Toward(Camera.X - Base.X, Camera.Y - Base.Y, 0.0f);
  if (Toward.Normalize()) Centre += Toward * FMath::Max(RadiusUU, 0.0f);
  return S08CombatFx::CameraQuad(Centre, Camera, Side);
}

EEmbersSkip EmbersDecision(S08HeroesV2::EDissolveStyle Style, bool bHasDissolveMic, bool bFxEnabled,
                           bool bReducedMotion) {
  if (!bFxEnabled) return EEmbersSkip::Legacy;
  if (bReducedMotion) return EEmbersSkip::Reduced;
  if (Style != S08HeroesV2::EDissolveStyle::Ash) return EEmbersSkip::Fade;
  if (!bHasDissolveMic) return EEmbersSkip::NoMaterial;
  return EEmbersSkip::None;
}

const TCHAR* EmbersSkipName(EEmbersSkip Skip) {
  switch (Skip) {
    case EEmbersSkip::Fade: return TEXT("fade");
    case EEmbersSkip::Reduced: return TEXT("reduced");
    case EEmbersSkip::Legacy: return TEXT("legacy");
    case EEmbersSkip::NoMaterial: return TEXT("none");
    default: return TEXT("-");
  }
}

FLinearColor EmberTeamColor(ES08TeamSlot Look) {
  return FLinearColor::FromSRGBColor(Look == ES08TeamSlot::P1 ? S08HudTokens::Color_TeamP1Screen
                                                              : S08HudTokens::Color_TeamP2Screen);
}

FString HeroKeyOfName(const FString& FighterName) {
  for (const S08HeroesV2::FHeroSpec& Spec : S08HeroesV2::Specs()) {
    if (FighterName.Equals(Spec.FighterName, ESearchCase::IgnoreCase)) return Spec.Key;
  }
  return FString();
}

bool IsArthurAbilityBoost(const FString& AttackerName, int32 BoostCount) {
  return BoostCount > 0 && HeroKeyOfName(AttackerName) == TEXT("KingArthur");
}

float ArcTiltDeg(const FVector& SocketLocation, const FVector& BladeAxis, const FVector& Camera) {
  const FVector Z = (Camera - SocketLocation).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
  const FVector Up = S08CombatFx::CameraQuadUp(SocketLocation, Camera);
  const FVector Right = FVector::CrossProduct(Z, Up);  // screen right (UE: Y = Z ^ X with X forward = -Z)
  double U = FVector::DotProduct(BladeAxis, Up);
  double R = FVector::DotProduct(BladeAxis, Right);
  if (U < 0.0) {
    U = -U;
    R = -R;
  }
  if (FMath::Abs(U) < 1e-6 && FMath::Abs(R) < 1e-6) return 0.0f;
  const float Deg = FMath::RadiansToDegrees(static_cast<float>(FMath::Atan2(R, U)));
  return FMath::Clamp(Deg, -ArcMaxTiltDeg, ArcMaxTiltDeg);
}

FTransform ArcQuad(const FVector& SocketLocation, float FigureHeightUU, const FVector& Camera) {
  const float Side = ArcQuadCells * ArcCellRel * FMath::Max(FigureHeightUU, 10.0f);
  return S08CombatFx::CameraQuad(SocketLocation, Camera, Side);
}

float ArcTimeDilation(float SpeedMul) { return SpeedMul <= 0.0f ? 0.0f : 1.0f / SpeedMul; }

FTransform VortexTransform(const FVector& Base, float FigureHeightUU, const FVector& Camera) {
  const FVector Toward(Camera.X - Base.X, Camera.Y - Base.Y, 0.0f);
  const float CamYaw = Toward.SizeSquared() > 1.0f ? FMath::RadiansToDegrees(FMath::Atan2(Toward.Y, Toward.X)) : 0.0f;
  const float S = FMath::Max(FigureHeightUU, 10.0f) / VortexMeshHeightUU;
  return FTransform(FRotator(0.0f, CamYaw - VortexFlashLocalYawDeg, 0.0f), Base, FVector(S));
}

FString LookField() {
  return FString::Printf(TEXT("abilityFx=%s"), S08CueFx::FxEnabled() ? TEXT("on") : TEXT("legacy(-S08FxLegacy)"));
}

}  // namespace S08AbilityFx
