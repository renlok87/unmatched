// AN-23 (ВР-06): the facing rules - see S08Facing.h.
#include "S08Facing.h"

#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace S08Facing {

bool LegacyRequested() { return FParse::Param(FCommandLine::Get(), LegacyFlagName); }

double YawToward(const FVector& From, const FVector& To) {
  const FVector2D D(To.X - From.X, To.Y - From.Y);
  if (D.IsNearlyZero()) return 0.0;
  return FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X));
}

double RestYaw(const FVector& FigurePos, const FVector& CameraPos, bool bHasEnemy,
               const FVector& NearestEnemyPos, double CurrentYawDeg, bool bApplyDeadBand) {
  if (!bHasEnemy) return CurrentYawDeg;  // ВР-06: no living enemy - the figure keeps its angle
  const double Axis = YawToward(FigurePos, CameraPos);
  const double ToEnemy = YawToward(FigurePos, NearestEnemyPos);
  const double Off = FMath::Clamp(FMath::FindDeltaAngleDegrees(Axis, ToEnemy), -MaxIdleOffDeg, MaxIdleOffDeg);
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
