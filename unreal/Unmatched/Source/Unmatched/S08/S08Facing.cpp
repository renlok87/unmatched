// AN-23 (ВР-06): the facing rules - see S08Facing.h.
#include "S08Facing.h"

#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace S08Facing {

bool LegacyRequested() { return FParse::Param(FCommandLine::Get(), LegacyFlagName); }

double RestMaxOffDeg(const TCHAR* HeroKey) {
  if (!HeroKey || FCString::Stricmp(HeroKey, TEXT("Medusa")) != 0) return MaxIdleOffDeg;
  const TCHAR* Cmd = FCommandLine::Get();
  if (FParse::Param(Cmd, FaceCapLegacyFlagName)) return MaxIdleOffDeg;
  double Cap = MedusaRestMaxOffDeg;
  if (FParse::Value(Cmd, FaceCapMedusaParamName, Cap)) Cap = FMath::Clamp(Cap, 0.0, MaxIdleOffDeg);
  return Cap;
}

FString FaceCapLookField() {
  return FParse::Param(FCommandLine::Get(), FaceCapLegacyFlagName)
             ? FString::Printf(TEXT("legacy(-%s)"), FaceCapLegacyFlagName)
             : FString::Printf(TEXT("medusa%.0f"), RestMaxOffDeg(TEXT("Medusa")));
}

double YawToward(const FVector& From, const FVector& To) {
  const FVector2D D(To.X - From.X, To.Y - From.Y);
  if (D.IsNearlyZero()) return 0.0;
  return FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X));
}

double RestYaw(const FVector& FigurePos, const FVector& CameraPos, bool bHasEnemy,
               const FVector& NearestEnemyPos, double CurrentYawDeg, bool bApplyDeadBand, double MaxOffDeg) {
  if (!bHasEnemy) return CurrentYawDeg;  // ВР-06: no living enemy - the figure keeps its angle
  const double Axis = YawToward(FigurePos, CameraPos);
  const double ToEnemy = YawToward(FigurePos, NearestEnemyPos);
  const double Cap = FMath::Clamp(MaxOffDeg, 0.0, MaxIdleOffDeg);  // VC C1: the hero's cap (Medusa 10)
  const double Off = FMath::Clamp(FMath::FindDeltaAngleDegrees(Axis, ToEnemy), -Cap, Cap);
  const double Want = Axis + Off;
  // Dead band: a small change of the enemy side does not twitch a standing figure.
  return bApplyDeadBand && FMath::Abs(FMath::FindDeltaAngleDegrees(CurrentYawDeg, Want)) < DeadBandDeg
             ? CurrentYawDeg
             : Want;
}

double AttackYaw(const FVector& FigurePos, const FVector& TargetPos, const FVector& CameraPos) {
  const double Axis = YawToward(FigurePos, CameraPos);
  const double ToTarget = YawToward(FigurePos, TargetPos);
  const double Off = FMath::Clamp(FMath::FindDeltaAngleDegrees(Axis, ToTarget), -AttackMaxOffDeg, AttackMaxOffDeg);
  return Axis + Off;
}

double TurnYawAt(double FromYawDeg, double ToYawDeg, double Alpha) {
  return FromYawDeg + FMath::FindDeltaAngleDegrees(FromYawDeg, ToYawDeg) * FMath::Clamp(Alpha, 0.0, 1.0);
}

}  // namespace S08Facing
