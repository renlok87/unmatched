#include "S08MoveAnim.h"
#include "S08HeroesV2.h"
#include "Algo/StableSort.h"
#include "Misc/Parse.h"

namespace S08Motion {

double SpeedMul(ES08AnimSpeed Speed) {
  switch (Speed) {
    case ES08AnimSpeed::None: return 0.0;
    case ES08AnimSpeed::Fast: return 0.5;
    case ES08AnimSpeed::Slow: return 1.5;
    default: return 1.0;
  }
}

const TCHAR* SpeedName(ES08AnimSpeed Speed) {
  switch (Speed) {
    case ES08AnimSpeed::None: return TEXT("none");
    case ES08AnimSpeed::Fast: return TEXT("fast");
    case ES08AnimSpeed::Slow: return TEXT("slow");
    default: return TEXT("normal");
  }
}

bool ParseSpeed(const FString& Text, ES08AnimSpeed& Out) {
  const FString T = Text.TrimStartAndEnd();
  for (const ES08AnimSpeed Speed : {ES08AnimSpeed::None, ES08AnimSpeed::Fast, ES08AnimSpeed::Normal,
                                    ES08AnimSpeed::Slow}) {
    if (T.Equals(SpeedName(Speed), ESearchCase::IgnoreCase)) {
      Out = Speed;
      return true;
    }
  }
  return false;
}

FS08MotionSettings Resolve(const FS08MotionSettings& Saved, const TCHAR* CommandLine, bool bReducedCVar) {
  FS08MotionSettings Out = Saved;
  if (bReducedCVar || (CommandLine && FParse::Param(CommandLine, ReducedMotionFlag))) Out.bReducedMotion = true;
  FString SpeedText;
  ES08AnimSpeed Speed = Out.Speed;
  if (CommandLine && FParse::Value(CommandLine, AnimSpeedParam, SpeedText) && ParseSpeed(SpeedText, Speed)) {
    Out.Speed = Speed;
  }
  return Out;
}

bool SkipsMove(const FKey& Key) {
  if (!Key.IsValid() || Key.IsGamepadKey() || Key.IsTouch() || Key.IsAxis1D() || Key.IsAxis2D() || Key.IsAxis3D() ||
      Key.IsAnalog()) {
    return false;
  }
  if (Key == EKeys::SpaceBar || Key == EKeys::MouseScrollUp || Key == EKeys::MouseScrollDown ||
      Key == EKeys::MouseWheelAxis) {
    return false;
  }
  return Key.IsMouseButton() || Key.IsDigital();
}

const TArray<FKey>& MoveSkipKeys() {
  static const TArray<FKey> Keys = [] {
    TArray<FKey> All;
    EKeys::GetAllKeys(All);
    return All.FilterByPredicate([](const FKey& Key) { return SkipsMove(Key); });
  }();
  return Keys;
}

}  // namespace S08Motion

FS08MoveAnimParams FS08MoveAnimParams::FromCommandLine(const TCHAR* CommandLine) {
  FS08MoveAnimParams Out;
  if (!CommandLine) return Out;
  double Value = 0.0;
  if (FParse::Value(CommandLine, TEXT("S08MoveHop="), Value)) Out.HopHeightRel = FMath::Clamp(Value, 0.0, 0.5);
  if (FParse::Value(CommandLine, TEXT("S08MoveLean="), Value)) Out.TravelLeanDeg = FMath::Clamp(Value, 0.0, 45.0);
  // AN-21 (ВР-12): the ease is the default; -S08MoveEaseLegacy rolls back to the linear ends; -S08MoveEase keeps the
  // old A/B spelling as a no-op alias (recorded in the ARTLOOK aliases).
  if (FParse::Param(CommandLine, TEXT("S08MoveEaseLegacy"))) Out.bEaseEnds = false;
  return Out;
}

double FS08MovePlan::EndMs(const FS08MoveAnimParams& Params) const {
  if (bSnapped || Kind == ES08MoveKind::Place) return ArriveMs();
  return ArriveMs() + FMath::Max(0.0, Params.SettleMs);
}

TArray<FS08MoveCueTiming> FS08MoveAnim::Schedule(const TArray<FS08Cue>& Cues, const FS08MotionSettings& Motion,
                                                 TArray<const FS08Cue*>& OutMovesInOrder,
                                                 const FS08MoveCueParams& Params) {
  if (!Motion.SnapsMoves()) {
    return FS08MoveCueSchedule::ForCues(Cues, OutMovesInOrder, Params, S08Motion::SpeedMul(Motion.Speed));
  }
  // 04 §6.3: reduced motion or speed none - every move snaps at 0 (cue_contract move_schedule, same rule).
  OutMovesInOrder.Reset();
  for (const FS08Cue& Cue : Cues) {
    if (Cue.Type == ES08CueType::FighterMoved) OutMovesInOrder.Add(&Cue);
  }
  Algo::StableSortBy(OutMovesInOrder, [](const FS08Cue* Cue) { return Cue->OrderInSeq; });
  TArray<FS08MoveCueTiming> Out;
  for (const FS08Cue* Cue : OutMovesInOrder) {
    FS08MoveCueTiming Timing;
    Timing.Steps = Cue->Steps();
    Timing.bSnapped = true;
    Out.Add(Timing);
  }
  return Out;
}

double FS08MoveAnim::RestYawDeg(const FVector& CellWorld) { return S08HeroesV2::FigureYawDeg(CellWorld.Y); }

double FS08MoveAnim::TravelYawDeg(const FVector& From, const FVector& To) {
  const FVector2D D(To.X - From.X, To.Y - From.Y);
  if (D.IsNearlyZero()) return 0.0;
  return FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X));
}

TArray<FS08MovePlan> FS08MoveAnim::BuildPlans(const TArray<FS08Cue>& Cues, const FS08MotionSettings& Motion,
                                              TFunctionRef<FVector(const FIntPoint&)> CellToWorld,
                                              const FS08MoveCueParams& Params) {
  TArray<const FS08Cue*> Moves;
  const TArray<FS08MoveCueTiming> Timing = Schedule(Cues, Motion, Moves, Params);
  TArray<FS08MovePlan> Plans;
  for (int32 I = 0; I < Moves.Num(); ++I) {
    const FS08Cue& Cue = *Moves[I];
    FS08MovePlan Plan;
    Plan.FighterId = Cue.FighterId;
    Plan.Seq = Cue.SequenceNumber;
    Plan.Order = Cue.OrderInSeq;
    Plan.Of = Moves.Num();
    Plan.Kind = Cue.Kind;
    TArray<FIntPoint> Cells = Cue.Path;
    if (Cells.Num() < 2) Cells = {FIntPoint(Cue.FromX, Cue.FromY), FIntPoint(Cue.ToX, Cue.ToY)};
    if (Cue.Kind == ES08MoveKind::Place) Cells = {Cells[0], Cells.Last()};
    for (const FIntPoint& Cell : Cells) Plan.Points.Add(CellToWorld(Cell));
    Plan.Steps = Plan.Kind == ES08MoveKind::Place ? 1 : FMath::Max(1, Plan.Points.Num() - 1);
    Plan.StartMs = Timing[I].StartMs;
    Plan.StepMs = Timing[I].StepMs;
    Plan.bSnapped = Timing[I].bSnapped;
    Plan.StartRestYawDeg = RestYawDeg(Plan.Points[0]);
    Plan.EndRestYawDeg = RestYawDeg(Plan.Points.Last());
    Plans.Add(MoveTemp(Plan));
  }
  return Plans;
}

namespace {
double BlendYaw(double From, double To, double Alpha) {
  return From + FMath::FindDeltaAngleDegrees(From, To) * FMath::Clamp(Alpha, 0.0, 1.0);
}
/** AN-21 (ВР-12, ВР-AN05): a trapezoid speed profile over one edge - a quadratic ease-in for the first EinU of it, a
 *  linear run between, a quadratic ease-out for the last EoutU (EinU / EoutU are fractions of the edge, 0 = off).
 *  The speed is continuous at both joins, the covered fraction is exactly 0..1, so the edge duration and the arrival
 *  time do not change. k normalises the area: k = 1 / (1 - EinU/2 - EoutU/2). */
double EaseProfile(double U, double EinU, double EoutU) {
  const double Uc = FMath::Clamp(U, 0.0, 1.0);
  if (EinU <= 0.0 && EoutU <= 0.0) return Uc;
  const double A = FMath::Clamp(EinU, 0.0, 0.5);
  const double B = FMath::Clamp(EoutU, 0.0, 0.5);
  const double k = 1.0 / FMath::Max(1e-9, 1.0 - 0.5 * A - 0.5 * B);
  if (A > 0.0 && Uc < A) return k * Uc * Uc / (2.0 * A);
  if (B > 0.0 && Uc > 1.0 - B) return 1.0 - k * (1.0 - Uc) * (1.0 - Uc) / (2.0 * B);
  return k * (Uc - 0.5 * A);
}
}  // namespace

FS08MovePose FS08MoveAnim::Sample(const FS08MovePlan& Plan, const FS08MoveAnimParams& Params, double SeqMs,
                                  double FigureHeightUU) {
  FS08MovePose Pose;
  if (Plan.Points.Num() == 0) {
    Pose.bDone = Pose.bArrived = Pose.bStarted = true;
    return Pose;
  }
  const double T = SeqMs - Plan.StartMs;
  const FVector& Start = Plan.Points[0];
  const FVector& End = Plan.Points.Last();
  auto Rest = [&](bool bAtEnd) {
    Pose.Location = bAtEnd ? End : Start;
    Pose.YawDeg = bAtEnd ? Plan.EndRestYawDeg : Plan.StartRestYawDeg;
  };
  if (T < 0.0) {  // waiting for its slot of the seq (a later fighter stays on its start cell)
    Rest(false);
    return Pose;
  }
  Pose.bStarted = true;
  const double Duration = Plan.DurationMs();
  if (Plan.bSnapped || Duration <= 0.0) {
    Rest(true);
    Pose.bArrived = Pose.bDone = true;
    return Pose;
  }
  if (Plan.Kind == ES08MoveKind::Place) {
    // Transfer without a path: fade out on the old cell, fade in on the new one (half of place_ms each).
    const double Half = 0.5 * Duration;
    if (T < Half) {
      Rest(false);
      Pose.Fade = T / Half;
    } else if (T < Duration) {
      Rest(true);
      Pose.Fade = 1.0 - (T - Half) / Half;
      Pose.bArrived = true;
    } else {
      Rest(true);
      Pose.bArrived = Pose.bDone = true;
    }
    return Pose;
  }
  const int32 Edges = FMath::Max(1, Plan.Points.Num() - 1);
  TArray<double> EdgeYaw;
  EdgeYaw.SetNum(Edges);
  for (int32 E = 0; E < Edges; ++E) {
    const FVector& A = Plan.Points[FMath::Min(E, Plan.Points.Num() - 1)];
    const FVector& B = Plan.Points[FMath::Min(E + 1, Plan.Points.Num() - 1)];
    // A zero-length edge keeps the previous direction (the start facing for the first edge).
    EdgeYaw[E] = FVector2D(B - A).IsNearlyZero() ? (E > 0 ? EdgeYaw[E - 1] : Plan.StartRestYawDeg)
                                                  : TravelYawDeg(A, B);
  }
  const double Step = Duration / Edges;
  const double Lean = FMath::Max(0.0, Params.TravelLeanDeg);
  if (T < Duration) {
    const int32 E = FMath::Clamp(FMath::FloorToInt32(T / Step), 0, Edges - 1);
    const double Local = T - E * Step;
    const double U = FMath::Clamp(Local / Step, 0.0, 1.0);
    // AN-21 (ВР-12): ease only the ends of the whole path - an ease-in on the first edge, an ease-out on the last
    // one; every middle edge stays linear. The window scales with the edge: E = min(EaseMs x T / 280, T / 2).
    double UPos = U;
    if (Params.bEaseEnds) {
      const double EaseWinMs = FMath::Clamp(FMath::Max(0.0, Params.EaseMs) * Step / 280.0, 0.0, 0.5 * Step);
      UPos = EaseProfile(U, E == 0 ? EaseWinMs / Step : 0.0, E == Edges - 1 ? EaseWinMs / Step : 0.0);
    }
    const FVector& A = Plan.Points[FMath::Min(E, Plan.Points.Num() - 1)];
    const FVector& B = Plan.Points[FMath::Min(E + 1, Plan.Points.Num() - 1)];
    Pose.Location = FMath::Lerp(A, B, UPos);
    Pose.HopUU = FMath::Max(0.0, Params.HopHeightRel) * FMath::Max(0.0, FigureHeightUU) * FMath::Sin(UE_DOUBLE_PI * U);
    Pose.Location.Z += Pose.HopUU;
    if (E == 0) {
      const double TurnMs = FMath::Min(FMath::Max(0.0, Params.StartTurnMs), Step);
      Pose.YawDeg = BlendYaw(Plan.StartRestYawDeg, EdgeYaw[0], TurnMs > 0.0 ? Local / TurnMs : 1.0);
    } else {
      const double TurnMs = FMath::Min(FMath::Max(0.0, Params.TurnMs), Step);
      Pose.YawDeg = BlendYaw(EdgeYaw[E - 1], EdgeYaw[E], TurnMs > 0.0 ? Local / TurnMs : 1.0);
    }
    Pose.LeanDeg = Lean * (Params.LeanInMs > 0.0 ? FMath::Clamp(T / Params.LeanInMs, 0.0, 1.0) : 1.0);
    Pose.Edge = E;
    return Pose;
  }
  Pose.bArrived = true;
  Pose.Location = End;
  const double Settle = FMath::Max(0.0, Params.SettleMs);
  const double S = T - Duration;
  if (Settle > 0.0 && S < Settle) {
    const double A = S / Settle;
    Pose.YawDeg = BlendYaw(EdgeYaw.Last(), Plan.EndRestYawDeg, A);
    Pose.LeanDeg = Lean * (1.0 - A);
    return Pose;
  }
  Pose.YawDeg = Plan.EndRestYawDeg;
  Pose.bDone = true;
  return Pose;
}

FQuat FS08MoveAnim::FigureRotation(double YawDeg, double LeanDeg, double MeshYawOffsetDeg) {
  const FQuat Yaw = FRotator(0.0, YawDeg + MeshYawOffsetDeg, 0.0).Quaternion();
  if (FMath::IsNearlyZero(LeanDeg)) return Yaw;
  const double Rad = FMath::DegreesToRadians(YawDeg);
  const FVector Forward(FMath::Cos(Rad), FMath::Sin(Rad), 0.0);
  // Rotating about Up x Forward by a positive angle moves the top of the figure along Forward.
  const FVector Axis = FVector::CrossProduct(FVector::UpVector, Forward).GetSafeNormal();
  return FQuat(Axis, FMath::DegreesToRadians(LeanDeg)) * Yaw;
}

TArray<FIntPoint> FS08MoveAnim::ReviewPath(const FIntPoint& Dest,
                                           TFunctionRef<TArray<FIntPoint>(const FIntPoint&)> Neighbours,
                                           TFunctionRef<bool(const FIntPoint&)> IsFree,
                                           TFunctionRef<FVector(const FIntPoint&)> CellToWorld) {
  const FVector DestW = CellToWorld(Dest);
  TArray<FIntPoint> Best;
  double BestScore = -1.0;
  for (const FIntPoint& N1 : Neighbours(Dest)) {
    if (N1 == Dest || !IsFree(N1)) continue;
    const FVector Last = (DestW - CellToWorld(N1)).GetSafeNormal2D();
    if (Last.IsNearlyZero()) continue;
    // Sideways share of the last edge (the board camera looks along -Y), then how well N2 -> N1 continues it.
    const double Side = FMath::Abs(Last.X);
    for (const FIntPoint& N2 : Neighbours(N1)) {
      if (N2 == Dest || N2 == N1 || !IsFree(N2)) continue;
      const FVector First = (CellToWorld(N1) - CellToWorld(N2)).GetSafeNormal2D();
      if (First.IsNearlyZero()) continue;
      const double Score = Side * 2.0 + FVector::DotProduct(First, Last);
      if (Score > BestScore + 1e-6) {
        BestScore = Score;
        Best = {N2, N1, Dest};
      }
    }
  }
  return Best;
}
