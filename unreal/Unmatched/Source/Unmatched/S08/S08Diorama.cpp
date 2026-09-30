#include "S08Diorama.h"

#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace S08Diorama {
namespace {
// -1 = read the command line, 0/1 = automation override.
int32 GFlagOverride = -1;
}  // namespace

bool FlagEnabled() {
  if (GFlagOverride >= 0) return GFlagOverride == 1;
  return FParse::Param(FCommandLine::Get(), FlagName);
}

void SetFlagOverrideForTest(bool bEnabled) { GFlagOverride = bEnabled ? 1 : 0; }

void ResetFlagOverrideForTest() { GFlagOverride = -1; }

FTrayFit FitTray(const FVector2D& BoardHalf) {
  FTrayFit Fit;
  const FVector2D Want(BoardHalf.X + RimUU, BoardHalf.Y + RimUU);
  if (BoardHalf.Y >= BoardHalf.X) {
    // yaw -90: mesh X -> world -Y, mesh Y -> world +X.
    Fit.YawDeg = -90.0f;
    Fit.Scale = FVector(Want.Y / MeshHalfX, Want.X / MeshHalfY, 1.0f);
  } else {
    Fit.YawDeg = 0.0f;
    Fit.Scale = FVector(Want.X / MeshHalfX, Want.Y / MeshHalfY, 1.0f);
  }
  Fit.WorldHalf = Want;
  return Fit;
}

FTrayFit FitTray(const FVector2D& BoardHalf, const FVector2D& Offset) {
  // Grow the fitted half extent by |offset| per axis, then move the pivot by the offset: the board frame stays
  // inside the tray with at least RimUU on every side (ENV-O8 T1 placeholder; a zero offset = FitTray(BoardHalf)).
  FTrayFit Fit = FitTray(FVector2D(BoardHalf.X + FMath::Abs(Offset.X), BoardHalf.Y + FMath::Abs(Offset.Y)));
  Fit.Location = Offset;
  return Fit;
}

}  // namespace S08Diorama
