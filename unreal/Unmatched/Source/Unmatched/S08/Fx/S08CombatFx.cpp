// VS-6 F2: the world-free numbers of FX-21..FX-25 - see S08CombatFx.h.
#include "S08CombatFx.h"

#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "S08CueFx.h"

namespace S08CombatFx {

FVector StarPoint(const FVector& TargetBase, float FigureHeightUU, float RadiusUU, const FVector* AttackerBase) {
  FVector P = TargetBase + FVector(0.0f, 0.0f, StarHeightRel * FMath::Max(FigureHeightUU, 1.0f));
  if (AttackerBase) {
    const FVector D(AttackerBase->X - TargetBase.X, AttackerBase->Y - TargetBase.Y, 0.0f);
    if (D.SizeSquared() > 1.0f) P += D.GetSafeNormal() * (StarTowardRel * FMath::Max(RadiusUU, 0.0f));
  }
  return P;
}

float StarQuadSideUU(float FigureHeightUU) {
  return FMath::Max(20.0f, StarDiameterRel * FigureHeightUU / StarCellFill);
}

FVector CameraQuadUp(const FVector& Centre, const FVector& CameraLocation) {
  const FVector Z = (CameraLocation - Centre).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
  FVector Up = FVector::UpVector - Z * FVector::DotProduct(FVector::UpVector, Z);
  if (!Up.Normalize()) Up = FVector::ForwardVector;
  return Up;
}

FTransform CameraQuad(const FVector& Centre, const FVector& CameraLocation, float SideUU) {
  const FVector Z = (CameraLocation - Centre).GetSafeNormal(UE_SMALL_NUMBER, FVector::UpVector);
  const FVector Up = CameraQuadUp(Centre, CameraLocation);
  // the plane's +Z towards the camera, its +X along the in-plane up (the shader rebuilds the screen frame itself)
  const FRotator Rotation = FRotationMatrix::MakeFromZX(Z, Up).Rotator();
  const float S = FMath::Max(SideUU, 1.0f) / PlaneUU;
  return FTransform(Rotation, Centre, FVector(S, S, 1.0f));
}

float HealQuadSideUU(float FigureHeightUU) { return 0.8f * FMath::Max(FigureHeightUU, 10.0f) + 16.0f; }

FVector HealQuadCentre(const FVector& Base, const FVector& CameraLocation, float SideUU) {
  return Base + CameraQuadUp(Base, CameraLocation) * (0.5f * SideUU - 6.0f);
}

FNumberPose NumberPose(double Ms, double LifeMs, bool bReduced) {
  FNumberPose P;
  if (Ms < 0.0 || LifeMs <= 0.0 || Ms >= LifeMs) return P;
  if (bReduced) {
    // 04 §3.5: no rise, no scale; the last 100 ms opacity only
    P.Opacity = static_cast<float>(FMath::Clamp((LifeMs - Ms) / NumberReducedFadeMs, 0.0, 1.0));
    return P;
  }
  const double In = FMath::Clamp(Ms / NumberScaleInMs, 0.0, 1.0);
  P.Scale = FMath::Lerp(NumberScaleFrom, 1.0f, static_cast<float>(1.0 - (1.0 - In) * (1.0 - In)));
  const double X = FMath::Clamp(Ms / LifeMs, 0.0, 1.0);
  P.RiseSu = NumberRiseSu * static_cast<float>(1.0 - (1.0 - X) * (1.0 - X));
  P.Opacity = static_cast<float>(FMath::Clamp((LifeMs - Ms) / NumberFadeMs, 0.0, 1.0));
  return P;
}

int32 NumberLifeMs(bool bHeal, int32 DamageLifeMs, bool bReduced) {
  if (bReduced) return ReducedNumberMs;
  return bHeal ? HealNumberMs : FMath::Max(1, DamageLifeMs);
}

int32 HealAmount(int32 HpBefore, int32 HpAfter, bool bAliveBefore, bool bAliveAfter) {
  if (!bAliveBefore || !bAliveAfter || HpBefore <= 0) return 0;
  return FMath::Max(0, HpAfter - HpBefore);
}

bool FigureCueLegacy() { return FParse::Param(FCommandLine::Get(), FigureCueLegacyFlagName); }

bool FxShotsRequested() {
  return FParse::Param(FCommandLine::Get(), TEXT("S08FxShots")) || FParse::Param(FCommandLine::Get(), TEXT("S08ExitShots"));
}

FString LookField() {
  return FString::Printf(TEXT("combatFx=%s figureCue=%s"),
                         S08CueFx::FxEnabled() ? TEXT("on") : TEXT("legacy(-S08FxLegacy)"),
                         FigureCueLegacy() ? TEXT("legacy(-S08FigureCueLegacy)") : TEXT("overlay"));
}

}  // namespace S08CombatFx
