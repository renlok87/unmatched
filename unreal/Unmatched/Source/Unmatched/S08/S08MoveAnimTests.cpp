// MS-T-16 (move selection, docs/game-design/move-selection/04 §6.3; DE footage 01 F-02) automation tests:
//   Unmatched.S08.MoveAnim.Schedule (MS-AT-24) - the seq schedule with the motion settings: the 04 §6.3 control values
//     at every speed, reduced motion / speed none snap at 0, the plans (world points, rest facings), the MS-CUE line
//     with speed= / reduced=, the skip keys (any key or mouse button but Space and the wheel).
//   Unmatched.S08.MoveAnim.Pose (F-02, SD-20/50; AN-21 ВР-12) - the pose of a figure along its plan: the same time on
//     every edge whatever its length, linear inside an edge (-S08MoveEaseLegacy), the ease profile of the ends by
//     default (80 ms, trapezoid speed, ВР-AN05: s(40) = 1/24, s(80) = 1/6, k = 1/240 / 1/200, arrival unchanged), no
//     hop by default (the hop is a parameter), lean 10 deg in 60 ms, start turn <= 50 ms, turn at a vertex 120 ms on
//     the move, back to Idle in 150 ms, Place fade out / in, a later fighter waits on its start cell, a snapped plan
//     lands at its slot; the -BenchMovePose review approach (DE-021).
//   Unmatched.S08.MoveAnim.Settings (MS-AT-33) - US08UserSettings is a config object in GameUserSettings.ini and leaves
//     the engine's GameUserSettings class alone (FrameRateLimit 60 kept), the flags override the saved values, the A/B
//     review parameters.
//   Unmatched.S08.MoveAnim.Actor (MS-R-53, MS-AT-24 world half) - a fighter actor plays a plan: it starts on the start
//     cell in the snapshot frame while the click volume stays on the snapshot cell, keeps travelling through another
//     snapshot with the same cell, jumps to the final pose on a new cell (jump_to_final) or a skip, restores the click
//     contract after the move; a v2 figure leans and faces the travel direction, then settles to the half-field facing.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.MoveAnim" <abs log>
#if WITH_AUTOMATION_TESTS

#include "S08BoardModel.h"
#include "S08FighterActor.h"
#include "S08FlowController.h"
#include "S08HeroesV2.h"
#include "S08MoveAnim.h"
#include "S08UserSettings.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "GameFramework/GameUserSettings.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace S08MoveAnimTest {

FS08Cue MoveCue(const FString& Id, int32 Order, const TArray<FIntPoint>& Path, ES08MoveKind Kind = ES08MoveKind::Move,
                int32 Seq = 40) {
  FS08Cue Cue;
  Cue.Type = ES08CueType::FighterMoved;
  Cue.SequenceNumber = Seq;
  Cue.FighterId = Id;
  Cue.Path = Path;
  Cue.FromX = Path[0].X;
  Cue.FromY = Path[0].Y;
  Cue.ToX = Path.Last().X;
  Cue.ToY = Path.Last().Y;
  Cue.OrderInSeq = Order;
  Cue.Kind = Kind;
  Cue.PathSource = ES08PathSource::Trail;
  return Cue;
}

/** N fighters, each walking Steps cells along its own row. */
TArray<FS08Cue> Rows(int32 N, int32 Steps, ES08MoveKind Kind = ES08MoveKind::Move) {
  TArray<FS08Cue> Out;
  for (int32 I = 0; I < N; ++I) {
    TArray<FIntPoint> Path;
    for (int32 S = 0; S <= Steps; ++S) Path.Add(FIntPoint(S, I));
    Out.Add(MoveCue(FString::Printf(TEXT("f%d"), I), I, Path, Kind));
  }
  return Out;
}

FVector GridWorld(const FIntPoint& Cell) { return FVector(Cell.X * 100.0, Cell.Y * 100.0, 0.0); }

FS08MotionSettings MotionOf(ES08AnimSpeed Speed, bool bReduced = false) {
  FS08MotionSettings M;
  M.Speed = Speed;
  M.bReducedMotion = bReduced;
  return M;
}

/** A plan along world points with a fixed step (no schedule), starting at StartMs. */
FS08MovePlan Plan(const TArray<FVector>& Points, double StepMs, double StartMs = 0.0,
                  ES08MoveKind Kind = ES08MoveKind::Move) {
  FS08MovePlan P;
  P.FighterId = TEXT("f");
  P.Kind = Kind;
  P.Points = Points;
  P.Steps = Kind == ES08MoveKind::Place ? 1 : Points.Num() - 1;
  P.StepMs = StepMs;
  P.StartMs = StartMs;
  P.StartRestYawDeg = FS08MoveAnim::RestYawDeg(Points[0]);
  P.EndRestYawDeg = FS08MoveAnim::RestYawDeg(Points.Last());
  return P;
}

bool Near(double A, double B, double Tol = 0.01) { return FMath::Abs(A - B) <= Tol; }
bool NearYaw(double A, double B, double Tol = 0.5) { return FMath::Abs(FMath::FindDeltaAngleDegrees(A, B)) <= Tol; }

}  // namespace S08MoveAnimTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveAnimScheduleTest, "Unmatched.S08.MoveAnim.Schedule",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveAnimScheduleTest::RunTest(const FString&) {
  using namespace S08MoveAnimTest;
  auto Sched = [](const TArray<FS08Cue>& Cues, const FS08MotionSettings& M) {
    TArray<const FS08Cue*> Moves;
    return FS08MoveAnim::Schedule(Cues, M, Moves);
  };
  auto End = [](const FS08MoveCueTiming& T) { return T.StartMs + T.DurationMs; };
  const FS08MotionSettings Normal = MotionOf(ES08AnimSpeed::Normal);
  // ---- 04 §6.3 control values through the settings (±1 ms) ----
  TestTrue("1 step = 280", Near(Sched(Rows(1, 1), Normal)[0].DurationMs, 280.0, 1.0));
  TestTrue("9 steps = 1400", Near(Sched(Rows(1, 9), Normal)[0].DurationMs, 1400.0, 1.0));
  const TArray<FS08MoveCueTiming> Four = Sched(Rows(4, 7), Normal);
  TestTrue("4x7 Normal ends at 2400, 110.6 per step", Near(End(Four[3]), 2400.0, 1.0) && Near(Four[0].StepMs, 110.6, 0.1));
  TestTrue("4x7 Slow ends at 3600", Near(End(Sched(Rows(4, 7), MotionOf(ES08AnimSpeed::Slow))[3]), 3600.0, 1.0));
  const TArray<FS08MoveCueTiming> Fast = Sched(Rows(9, 9), MotionOf(ES08AnimSpeed::Fast));
  int32 FastSnapped = 0;
  for (const FS08MoveCueTiming& T : Fast) FastSnapped += T.bSnapped ? 1 : 0;
  TestTrue("9x9 Fast: 1 animated ending at 810 (min step 90 not scaled), 8 snap at 810",
           !Fast[0].bSnapped && Near(End(Fast[0]), 810.0, 1.0) && FastSnapped == 8 && Near(Fast[8].StartMs, 810.0, 1.0));
  TestTrue("PLACE Slow = 360", Near(Sched(Rows(1, 3, ES08MoveKind::Place), MotionOf(ES08AnimSpeed::Slow))[0].DurationMs,
                                    360.0, 1.0));
  // ---- reduced motion and speed "none": every move snaps at 0 ----
  for (const FS08MotionSettings& M : {MotionOf(ES08AnimSpeed::Normal, true), MotionOf(ES08AnimSpeed::None),
                                      MotionOf(ES08AnimSpeed::Slow, true)}) {
    const TArray<FS08MoveCueTiming> Snap = Sched(Rows(3, 4), M);
    bool bAllSnap = Snap.Num() == 3;
    for (const FS08MoveCueTiming& T : Snap) bAllSnap &= T.bSnapped && T.StartMs == 0.0 && T.DurationMs == 0.0 && T.Steps == 4;
    TestTrue(FString::Printf(TEXT("snap at 0 (reduced=%d speed=%s)"), M.bReducedMotion ? 1 : 0,
                             S08Motion::SpeedName(M.Speed)), bAllSnap);
  }
  // ---- plans: OrderInSeq order, world points with the start, rest facings by the half-field rule ----
  {
    TArray<FS08Cue> Cues = {MoveCue(TEXT("late"), 1, {{0, 2}, {1, 2}}),
                            MoveCue(TEXT("first"), 0, {{0, -3}, {1, -3}, {1, -2}})};
    FS08Cue Damage;
    Damage.Type = ES08CueType::FighterDamaged;
    Damage.FighterId = TEXT("late");
    Damage.Damage = 2;
    Cues.Add(Damage);
    const TArray<FS08MovePlan> Plans = FS08MoveAnim::BuildPlans(Cues, Normal, GridWorld);
    TestEqual("one plan per move cue", Plans.Num(), 2);
    if (Plans.Num() == 2) {
      TestEqual("order: first", Plans[0].FighterId, FString(TEXT("first")));
      TestTrue("first: 3 points, 2 steps of 280", Plans[0].Points.Num() == 3 && Plans[0].Steps == 2 &&
                                                       Near(Plans[0].StepMs, 280.0, 0.5) && Plans[0].Of == 2);
      TestTrue("first: world points", Plans[0].Points[1].Equals(FVector(100.0, -300.0, 0.0)));
      TestTrue("late starts at 70 % of the first's 560 ms", Near(Plans[1].StartMs, 392.0, 1.0));
      TestTrue("rest facing: negative-Y half faces +Y (yaw 90), positive half -Y (270)",
               NearYaw(Plans[0].StartRestYawDeg, 90.0) && NearYaw(Plans[1].EndRestYawDeg, 270.0));
      TestTrue("arrival = start + duration", Near(Plans[1].ArriveMs(), 392.0 + 280.0, 1.0));
      FS08MoveAnimParams P;
      TestTrue("end includes the Idle settle 150", Near(Plans[1].EndMs(P), 392.0 + 280.0 + 150.0, 1.0));
    }
    const TArray<FS08Cue> Place = {MoveCue(TEXT("p"), 0, {{0, 0}, {4, 1}}, ES08MoveKind::Place)};
    const TArray<FS08MovePlan> PlacePlans = FS08MoveAnim::BuildPlans(Place, Normal, GridWorld);
    TestTrue("PLACE plan: [from, to], one step of 240",
             PlacePlans.Num() == 1 && PlacePlans[0].Points.Num() == 2 && PlacePlans[0].Steps == 1 &&
                 Near(PlacePlans[0].DurationMs(), 240.0, 0.5));
  }
  // ---- MS-CUE line with the motion fields (check-trace reads speed= / reduced=) ----
  {
    FS08BoardModel Board;
    Board.Width = 5;
    Board.Height = 5;
    Board.Cells.Init(FS08Cell(), 25);
    for (int32 I = 0; I < 25; ++I) {
      Board.Cells[I].X = I % 5;
      Board.Cells[I].Y = I / 5;
      Board.Cells[I].Type = ES08CellType::Normal;
    }
    TArray<FString> Lines;
    const FS08MotionSettings Reduced = MotionOf(ES08AnimSpeed::Slow, true);
    FS08FlowController::MoveCueTraceLines(Rows(1, 2), Board, Lines, &Reduced);
    TestEqual("one MS-CUE line", Lines.Num(), 1);
    if (Lines.Num() == 1) {
      TestTrue("reduced: snapped at 0", Lines[0].Contains(TEXT(" start=0 ms=0 snapped=1 ")));
      TestTrue("tail speed=slow reduced=1", Lines[0].EndsWith(TEXT(" speed=slow reduced=1")));
      UE_LOG(LogTemp, Display, TEXT("%s"), *Lines[0]);
    }
    const FS08MotionSettings Slow = MotionOf(ES08AnimSpeed::Slow);
    FS08FlowController::MoveCueTraceLines(Rows(1, 2), Board, Lines, &Slow);
    TestTrue("slow: 2 steps = 840", Lines.Num() == 1 && Lines[0].Contains(TEXT(" ms=840 snapped=0 ")) &&
                                       Lines[0].EndsWith(TEXT(" speed=slow reduced=0")));
    if (Lines.Num() == 1) UE_LOG(LogTemp, Display, TEXT("%s"), *Lines[0]);
    FS08FlowController::MoveCueTraceLines(Rows(1, 2), Board, Lines);
    TestTrue("without motion: the MS-T-15 line (no speed=)", Lines.Num() == 1 && !Lines[0].Contains(TEXT("speed=")));
  }
  // ---- skip keys (MS-E-70 / MS-E-110) ----
  TestTrue("left / right mouse button skip", S08Motion::SkipsMove(EKeys::LeftMouseButton) &&
                                                 S08Motion::SkipsMove(EKeys::RightMouseButton));
  TestTrue("Escape, Enter, A, Tab skip", S08Motion::SkipsMove(EKeys::Escape) && S08Motion::SkipsMove(EKeys::Enter) &&
                                             S08Motion::SkipsMove(EKeys::A) && S08Motion::SkipsMove(EKeys::Tab));
  TestFalse("Space does not skip (camera)", S08Motion::SkipsMove(EKeys::SpaceBar));
  TestFalse("the wheel does not skip (camera)", S08Motion::SkipsMove(EKeys::MouseScrollUp) ||
                                                    S08Motion::SkipsMove(EKeys::MouseScrollDown) ||
                                                    S08Motion::SkipsMove(EKeys::MouseWheelAxis));
  TestFalse("mouse move / gamepad do not skip", S08Motion::SkipsMove(EKeys::MouseX) ||
                                                    S08Motion::SkipsMove(EKeys::Gamepad_FaceButton_Bottom));
  TestTrue("skip key list has the mouse button, not Space",
           S08Motion::MoveSkipKeys().Contains(EKeys::LeftMouseButton) && !S08Motion::MoveSkipKeys().Contains(EKeys::SpaceBar));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveAnimPoseTest, "Unmatched.S08.MoveAnim.Pose",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveAnimPoseTest::RunTest(const FString&) {
  using namespace S08MoveAnimTest;
  const FS08MoveAnimParams Default;
  TestTrue("defaults = 01 F-02 + AN-21: hop 0, lean 10 in 60, start turn 50, turn 120, settle 150, ease 80 on",
           Default.HopHeightRel == 0.0 && Default.TravelLeanDeg == 10.0 && Default.LeanInMs == 60.0 &&
               Default.StartTurnMs == 50.0 && Default.TurnMs == 120.0 && Default.SettleMs == 150.0 &&
               Default.bEaseEnds && Near(Default.EaseMs, 80.0, 1e-9));
  FS08MoveAnimParams Linear = Default;
  Linear.bEaseEnds = false;  // -S08MoveEaseLegacy: the pose before ВР-12
  // A short edge (100 uu along +X) then a long one (300 uu along +Y): the same 280 ms each (SD-50 p. 1).
  const FS08MovePlan P = Plan({FVector(0, -400, 0), FVector(100, -400, 0), FVector(100, -100, 0)}, 280.0);
  const double H = 55.0;
  const FS08MovePose AtVertex = FS08MoveAnim::Sample(P, Default, 280.0, H);
  TestTrue("t = 280: on the vertex after the short edge", AtVertex.Location.Equals(FVector(100, -400, 0), 0.01));
  const FS08MovePose MidShort = FS08MoveAnim::Sample(P, Linear, 140.0, H);
  const FS08MovePose MidLong = FS08MoveAnim::Sample(P, Linear, 420.0, H);
  TestTrue("linear inside an edge (legacy): half of each edge at half its time",
           MidShort.Location.Equals(FVector(50, -400, 0), 0.01) && MidLong.Location.Equals(FVector(100, -250, 0), 0.01));
  TestTrue("no hop by default (D-DE-02): z = 0 mid-edge", Near(MidShort.Location.Z, 0.0) && Near(MidShort.HopUU, 0.0));
  TestTrue("arrives at 560 on the destination (ease changes no timing)",
           FS08MoveAnim::Sample(P, Default, 560.0, H).Location.Equals(FVector(100, -100, 0), 0.01));
  // AN-21 (ВР-12): the ease of the ends. The first edge eases in over E = min(80 x 280/280, 280/2) = 80 ms with
  // k = 1 / (1 - 80/280 / 2) = 1/240 of the edge per ms: s(40) = 40^2 / (480 x 40)... = 1/24 of the edge,
  // s(80) = 1/6, then the linear 1/240 per ms; the speed is continuous at 80 (ВР-AN05 profile).
  TestTrue("ease: s(40) = 1/24 of the first edge (linear was 1/7)",
           Near(FS08MoveAnim::Sample(P, Default, 40.0, H).Location.X, 100.0 / 24.0, 0.01));
  TestTrue("ease: s(80) = 1/6 of the first edge",
           Near(FS08MoveAnim::Sample(P, Default, 80.0, H).Location.X, 100.0 / 6.0, 0.01));
  const double EaseBefore = FS08MoveAnim::Sample(P, Default, 79.9, H).Location.X;
  const double EaseAt = FS08MoveAnim::Sample(P, Default, 80.0, H).Location.X;
  const double EaseAfter = FS08MoveAnim::Sample(P, Default, 80.1, H).Location.X;
  TestTrue("ease: the speed is continuous at the end of the ease-in (the same step over +-0.1 ms)",
           Near(EaseAt - EaseBefore, EaseAfter - EaseAt, 0.005));
  TestTrue("ease: the linear run is 1/240 of the edge per ms (100 -> 200 ms)",
           Near(FS08MoveAnim::Sample(P, Default, 200.0, H).Location.X - FS08MoveAnim::Sample(P, Default, 100.0, H).Location.X,
                100.0 * 100.0 / 240.0, 0.01));
  // One edge: E in = E out = 80 -> k = 1 / (280 - 80) = 1/200 of the edge per ms in the middle.
  const FS08MovePlan One = Plan({FVector(0, -400, 0), FVector(100, -400, 0)}, 280.0);
  TestTrue("one edge: the linear run is 1/200 of the edge per ms (130 -> 150 ms)",
           Near(FS08MoveAnim::Sample(One, Default, 150.0, H).Location.X - FS08MoveAnim::Sample(One, Default, 130.0, H).Location.X,
                100.0 * 20.0 / 200.0, 0.01));
  TestTrue("one edge: eases out to exactly the destination at 280",
           FS08MoveAnim::Sample(One, Default, 280.0, H).Location.Equals(FVector(100, -400, 0), 0.01));
  // The legacy flag of the A/B command line: the linear pose again.
  const FS08MoveAnimParams LegacyCmd = FS08MoveAnimParams::FromCommandLine(TEXT("-S08MoveEaseLegacy"));
  TestTrue("legacy flag: the linear pose (1/7 of the edge at 40 ms)",
           !LegacyCmd.bEaseEnds &&
               Near(FS08MoveAnim::Sample(P, LegacyCmd, 40.0, H).Location.X, 100.0 * 40.0 / 280.0, 0.01));
  // Hop is a parameter (A/B 0.08 of the figure height): sin(pi t) per edge.
  FS08MoveAnimParams Hop = Default;
  Hop.HopHeightRel = 0.08;
  TestTrue("hop 0.08: 0.08 * H at mid-edge", Near(FS08MoveAnim::Sample(P, Hop, 140.0, H).Location.Z, 0.08 * H, 0.01));
  TestTrue("hop 0.08: back on the board at a vertex", Near(FS08MoveAnim::Sample(P, Hop, 280.0, H).Location.Z, 0.0, 0.01));
  // Lean 10 deg in over 60 ms; the start facing (+Y, yaw 90) turns to the first edge (+X, yaw 0) within 50 ms.
  TestTrue("lean 5 deg at 30 ms, 10 at 60 and on",
           Near(FS08MoveAnim::Sample(P, Default, 30.0, H).LeanDeg, 5.0) &&
               Near(FS08MoveAnim::Sample(P, Default, 60.0, H).LeanDeg, 10.0) &&
               Near(FS08MoveAnim::Sample(P, Default, 400.0, H).LeanDeg, 10.0));
  TestTrue("start facing = rest (yaw 90) at 0", NearYaw(FS08MoveAnim::Sample(P, Default, 0.0, H).YawDeg, 90.0));
  TestTrue("half-turned at 25 ms", NearYaw(FS08MoveAnim::Sample(P, Default, 25.0, H).YawDeg, 45.0));
  TestTrue("faces the first edge by 50 ms", NearYaw(FS08MoveAnim::Sample(P, Default, 50.0, H).YawDeg, 0.0));
  // At the vertex (280) the facing turns to the second edge (+Y, yaw 90) in 120 ms without stopping.
  TestTrue("turn at the vertex: half at +60, done at +120",
           NearYaw(FS08MoveAnim::Sample(P, Default, 340.0, H).YawDeg, 45.0) &&
               NearYaw(FS08MoveAnim::Sample(P, Default, 400.0, H).YawDeg, 90.0));
  TestTrue("no stop at the vertex: moving 10 ms after it",
           FS08MoveAnim::Sample(P, Default, 290.0, H).Location.Y > -400.0 + 5.0);
  // After the arrival back to Idle in 150 ms: lean -> 0, facing -> the half-field rule of the destination (+Y side
  // y < 0: yaw 90 - the last edge already faces it).
  const FS08MovePose Settling = FS08MoveAnim::Sample(P, Default, 560.0 + 75.0, H);
  TestTrue("settling: lean 5 at +75, arrived, not done", Near(Settling.LeanDeg, 5.0) && Settling.bArrived && !Settling.bDone);
  const FS08MovePose Done = FS08MoveAnim::Sample(P, Default, 560.0 + 150.0, H);
  TestTrue("Idle at +150: lean 0, rest facing, done", Near(Done.LeanDeg, 0.0) && NearYaw(Done.YawDeg, 90.0) && Done.bDone);
  // Settle to the half-field facing when the last edge points elsewhere: walking +X on the far side (y > 0, rest 270).
  const FS08MovePlan Far = Plan({FVector(0, 200, 0), FVector(100, 200, 0)}, 280.0);
  TestTrue("settle turns to the far side's rest facing (270)",
           NearYaw(FS08MoveAnim::Sample(Far, Default, 280.0 + 75.0, H).YawDeg, -45.0) &&
               NearYaw(FS08MoveAnim::Sample(Far, Default, 280.0 + 150.0, H).YawDeg, 270.0));
  // Ease vs legacy: the eased first edge starts slower than the linear one.
  TestTrue("ease on: slower start on the first edge than the legacy linear pose",
           FS08MoveAnim::Sample(P, Default, 70.0, H).Location.X < FS08MoveAnim::Sample(P, Linear, 70.0, H).Location.X - 1.0);
  // A later fighter waits on its start cell; a snapped plan lands at its slot.
  const FS08MovePlan Later = Plan({FVector(0, -400, 0), FVector(100, -400, 0)}, 280.0, 392.0);
  const FS08MovePose Waiting = FS08MoveAnim::Sample(Later, Default, 200.0, H);
  TestTrue("before its slot: on the start cell, not started", Waiting.Location.Equals(FVector(0, -400, 0)) && !Waiting.bStarted);
  FS08MovePlan Snapped = Later;
  Snapped.bSnapped = true;
  Snapped.StepMs = 0.0;
  TestTrue("snapped: start cell before the slot, destination from the slot on",
           FS08MoveAnim::Sample(Snapped, Default, 391.0, H).Location.Equals(FVector(0, -400, 0)) &&
               FS08MoveAnim::Sample(Snapped, Default, 392.0, H).Location.Equals(FVector(100, -400, 0)) &&
               FS08MoveAnim::Sample(Snapped, Default, 392.0, H).bDone);
  // PLACE: fade out on the old cell, fade in on the new one (120 + 120).
  const FS08MovePlan Place = Plan({FVector(0, -400, 0), FVector(300, -100, 0)}, 240.0, 0.0, ES08MoveKind::Place);
  const FS08MovePose Out = FS08MoveAnim::Sample(Place, Default, 60.0, H);
  const FS08MovePose In = FS08MoveAnim::Sample(Place, Default, 180.0, H);
  TestTrue("PLACE fade-out on the old cell", Out.Location.Equals(FVector(0, -400, 0)) && Near(Out.Fade, 0.5) && Out.LeanDeg == 0.0);
  TestTrue("PLACE fade-in on the new cell", In.Location.Equals(FVector(300, -100, 0)) && Near(In.Fade, 0.5));
  TestTrue("PLACE done at 240, fully visible", FS08MoveAnim::Sample(Place, Default, 240.0, H).bDone &&
                                                   Near(FS08MoveAnim::Sample(Place, Default, 240.0, H).Fade, 0.0));
  // The lean tilts the figure's top along its facing (both mesh conventions).
  for (const double Yaw : {0.0, 90.0, 215.0}) {
    const double Rad = FMath::DegreesToRadians(Yaw);
    const FVector Facing(FMath::Cos(Rad), FMath::Sin(Rad), 0.0);
    const FVector UpV2 = FS08MoveAnim::FigureRotation(Yaw, 10.0, 0.0).RotateVector(FVector::UpVector);
    const FVector UpLegacy = FS08MoveAnim::FigureRotation(Yaw, 10.0, -90.0).RotateVector(FVector::UpVector);
    TestTrue(FString::Printf(TEXT("lean 10 deg tilts the top along the facing (yaw %.0f)"), Yaw),
             Near(FVector::DotProduct(UpV2, Facing), FMath::Sin(FMath::DegreesToRadians(10.0)), 0.001) &&
                 Near(FVector::DotProduct(UpLegacy, Facing), FMath::Sin(FMath::DegreesToRadians(10.0)), 0.001));
    const FVector ForwardV2 = FS08MoveAnim::FigureRotation(Yaw, 0.0, 0.0).RotateVector(FVector::ForwardVector);
    const FVector ForwardLegacy = FS08MoveAnim::FigureRotation(Yaw, 0.0, -90.0).RotateVector(FVector::RightVector);
    TestTrue(FString::Printf(TEXT("v2 +X and legacy +Y face the yaw %.0f"), Yaw),
             ForwardV2.Equals(Facing, 0.001) && ForwardLegacy.Equals(Facing, 0.001));
  }
  // DE-021 -BenchMovePose: the review approach on a 5 x 5 grid ends on the destination over two free edges, the last
  // one sideways (+-X) to the board camera, the first continuing it; occupied cells are never on it.
  {
    auto Grid = [](const FIntPoint& C) {
      TArray<FIntPoint> Out;
      for (const FIntPoint& D : {FIntPoint(1, 0), FIntPoint(-1, 0), FIntPoint(0, 1), FIntPoint(0, -1)}) {
        const FIntPoint N = C + D;
        if (N.X >= 0 && N.X < 5 && N.Y >= 0 && N.Y < 5) Out.Add(N);
      }
      return Out;
    };
    const TArray<FIntPoint> Free = FS08MoveAnim::ReviewPath(FIntPoint(2, 2), Grid, [](const FIntPoint&) { return true; },
                                                            GridWorld);
    TestTrue("review path: [N2, N1, dest], straight along X",
             Free.Num() == 3 && Free[2] == FIntPoint(2, 2) && Free[1].Y == 2 && Free[0].Y == 2 &&
                 FMath::Abs(Free[0].X - 2) == 2);
    const TArray<FIntPoint> Blocked = FS08MoveAnim::ReviewPath(
        FIntPoint(2, 2), Grid,
        [](const FIntPoint& C) { return C != FIntPoint(1, 2) && C != FIntPoint(3, 2) && C != FIntPoint(4, 2); }, GridWorld);
    TestTrue("review path avoids occupied cells (sideways edges blocked -> a Y edge)",
             Blocked.Num() == 3 && Blocked[1].X == 2 && Blocked[1] != FIntPoint(2, 2) &&
                 !Blocked.Contains(FIntPoint(1, 2)) && !Blocked.Contains(FIntPoint(3, 2)));
    TestEqual("review path: none when boxed in",
              FS08MoveAnim::ReviewPath(FIntPoint(0, 0), Grid, [](const FIntPoint&) { return false; }, GridWorld).Num(), 0);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveAnimSettingsTest, "Unmatched.S08.MoveAnim.Settings",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveAnimSettingsTest::RunTest(const FString&) {
  using namespace S08MoveAnimTest;
  // The settings object lives in GameUserSettings.ini next to the engine's settings; the engine class is untouched
  // (a UGameUserSettings subclass would lose [/Script/Engine.GameUserSettings] FrameRateLimit=60 - see S08UserSettings.h).
  TestTrue("US08UserSettings::Get() is the class default object", US08UserSettings::Get() == GetMutableDefault<US08UserSettings>());
  TestEqual("its config file is GameUserSettings", US08UserSettings::StaticClass()->ClassConfigName, FName(TEXT("GameUserSettings")));
  const US08UserSettings* Cdo = GetDefault<US08UserSettings>();
  TestTrue("saved defaults: no reduced motion, normal speed, shake on",
           !Cdo->bReducedMotion && Cdo->AnimSpeed == TEXT("normal") && Cdo->bScreenShake);
  if (GEngine && GEngine->GetGameUserSettings()) {
    TestTrue("the engine's GameUserSettings class is not replaced",
             GEngine->GetGameUserSettings()->GetClass() == UGameUserSettings::StaticClass());
  }
  TestEqual("the engine default FrameRateLimit stays 60 (ACC-022)",
            GetMutableDefault<UGameUserSettings>()->GetFrameRateLimit(), 60.0f);
  // Saved values <-> settings.
  {
    US08UserSettings* Temp = NewObject<US08UserSettings>(GetTransientPackage());
    FS08MotionSettings Want;
    Want.bReducedMotion = true;
    Want.Speed = ES08AnimSpeed::Slow;
    Want.bScreenShake = false;
    Temp->SetSavedMotion(Want);
    TestTrue("saved motion round trip", Temp->GetSavedMotion() == Want && Temp->AnimSpeed == TEXT("slow"));
    Temp->AnimSpeed = TEXT("warp");
    TestTrue("an unknown saved speed reads as normal", Temp->GetSavedMotion().Speed == ES08AnimSpeed::Normal);
    Temp->SetToDefaults();
    TestTrue("SetToDefaults resets the motion", Temp->GetSavedMotion() == FS08MotionSettings());
    Temp->MarkAsGarbage();
  }
  // Flags win over the saved values (04 §6.3).
  FS08MotionSettings Saved;
  Saved.Speed = ES08AnimSpeed::Slow;
  TestTrue("no flags: saved", S08Motion::Resolve(Saved, TEXT("-game"), false) == Saved);
  TestTrue("-S08ReducedMotion forces reduced", S08Motion::Resolve(Saved, TEXT("-S08ReducedMotion"), false).bReducedMotion);
  TestTrue("s08.ReducedMotion forces reduced", S08Motion::Resolve(Saved, TEXT(""), true).bReducedMotion);
  TestTrue("-S08AnimSpeed=fast replaces the speed",
           S08Motion::Resolve(Saved, TEXT("-S08AnimSpeed=fast"), false).Speed == ES08AnimSpeed::Fast);
  TestTrue("-S08AnimSpeed=None (any case) = none",
           S08Motion::Resolve(Saved, TEXT("-S08AnimSpeed=None"), false).Speed == ES08AnimSpeed::None);
  TestTrue("-S08AnimSpeed=bogus keeps the saved speed",
           S08Motion::Resolve(Saved, TEXT("-S08AnimSpeed=bogus"), false).Speed == ES08AnimSpeed::Slow);
  TestTrue("speed none and reduced motion snap moves",
           MotionOf(ES08AnimSpeed::None).SnapsMoves() && MotionOf(ES08AnimSpeed::Fast, true).SnapsMoves() &&
               !MotionOf(ES08AnimSpeed::Fast).SnapsMoves());
  TestTrue("multipliers 0 / 0.5 / 1 / 1.5",
           S08Motion::SpeedMul(ES08AnimSpeed::None) == 0.0 && S08Motion::SpeedMul(ES08AnimSpeed::Fast) == 0.5 &&
               S08Motion::SpeedMul(ES08AnimSpeed::Normal) == 1.0 && S08Motion::SpeedMul(ES08AnimSpeed::Slow) == 1.5);
  // A/B review parameters (DE-028): hop 0 / 0.08, lean 0 / 10, ease on (AN-21 ВР-12: the default, -S08MoveEase an alias).
  const FS08MoveAnimParams AB = FS08MoveAnimParams::FromCommandLine(TEXT("-S08MoveHop=0.08 -S08MoveLean=0 -S08MoveEase"));
  TestTrue("A/B flags: hop 0.08, lean 0, ease on",
           Near(AB.HopHeightRel, 0.08, 1e-6) && AB.TravelLeanDeg == 0.0 && AB.bEaseEnds && Near(AB.EaseMs, 80.0, 1e-9));
  const FS08MoveAnimParams None = FS08MoveAnimParams::FromCommandLine(TEXT("-game"));
  TestTrue("no A/B flags: the accepted defaults (ease on since AN-21 ВР-12)",
           None.HopHeightRel == 0.0 && None.TravelLeanDeg == 10.0 && None.bEaseEnds && Near(None.EaseMs, 80.0, 1e-9));
  TestFalse("-S08MoveEaseLegacy: the linear ends of before ВР-12",
            FS08MoveAnimParams::FromCommandLine(TEXT("-S08MoveEaseLegacy")).bEaseEnds);
  // Reduced motion takes the hop and the lean away with the whole move: a snapped plan has no travelling pose.
  FS08MoveAnimParams HopLean = AB;
  HopLean.TravelLeanDeg = 10.0;
  TArray<FS08Cue> One = {MoveCue(TEXT("f"), 0, {{0, 0}, {1, 0}, {2, 0}})};
  const TArray<FS08MovePlan> Reduced = FS08MoveAnim::BuildPlans(One, MotionOf(ES08AnimSpeed::Normal, true), GridWorld);
  const FS08MovePose Pose = FS08MoveAnim::Sample(Reduced[0], HopLean, 0.0, 55.0);
  TestTrue("reduced motion: lands at 0 with no hop and no lean",
           Pose.bDone && Pose.Location.Equals(FVector(200, 0, 0)) && Pose.LeanDeg == 0.0 && Pose.HopUU == 0.0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveAnimSettingsStoreTest, "Unmatched.S08.MoveAnim.SettingsStore",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveAnimSettingsStoreTest::RunTest(const FString&) {
  // DE-025 (W-24; 02 SD-49, SD-55): the volumes "master" / "ambience" + mutes are stored next to UI-ACC-012/013;
  // a saved change reaches a running client without a restart (OnChanged -> S08Motion::Current).
  const US08UserSettings* Cdo = GetDefault<US08UserSettings>();
  TestTrue("saved volume defaults: master 100, ambience 60, no mute",
           Cdo->MasterVolume == 100 && Cdo->AmbienceVolume == 60 && !Cdo->bMasterMuted && !Cdo->bAmbienceMuted);
  US08UserSettings* Temp = NewObject<US08UserSettings>(GetTransientPackage());
  FString Error;
  TestTrue("speed=fast", Temp->ApplySetting(TEXT("speed"), TEXT("fast"), Error) && Temp->AnimSpeed == TEXT("fast"));
  TestTrue("master=80", Temp->ApplySetting(TEXT("master"), TEXT("80"), Error) && Temp->MasterVolume == 80);
  TestTrue("Ambience=25 (any case)", Temp->ApplySetting(TEXT("Ambience"), TEXT("25"), Error) && Temp->AmbienceVolume == 25);
  TestTrue("ambienceMute=on", Temp->ApplySetting(TEXT("ambienceMute"), TEXT("on"), Error) && Temp->bAmbienceMuted);
  TestTrue("ruleHints=0", Temp->ApplySetting(TEXT("ruleHints"), TEXT("0"), Error) && !Temp->bRuleHints);
  TestFalse("master=101 refused", Temp->ApplySetting(TEXT("master"), TEXT("101"), Error));
  TestFalse("master=4.5 refused", Temp->ApplySetting(TEXT("master"), TEXT("4.5"), Error));
  TestFalse("speed=warp refused", Temp->ApplySetting(TEXT("speed"), TEXT("warp"), Error));
  TestFalse("unknown name refused", Temp->ApplySetting(TEXT("gamma"), TEXT("50"), Error));
  TestTrue("a refused value changes nothing", Temp->MasterVolume == 80 && Temp->AnimSpeed == TEXT("fast"));
  // AU-S4: the bus volumes and the subtitle switches follow the DE-025 ones (S08AudioTests.cpp covers them)
  TestEqual("Describe", Temp->Describe(),
            FString(TEXT("speed=fast reduced=0 shake=1 ruleHints=0 master=80 masterMute=0 ambience=25 ambienceMute=1 "
                         "music=60 sfx=80 ui=80 vo=80 subtitles=1 describeSounds=0")));
  // Gains: the ambience goes through the master volume and both mutes; the ini values are clamped on read.
  FS08AudioSettings Audio = Temp->GetSavedAudio();
  TestTrue("ambience muted -> gain 0", Audio.AmbienceGain() == 0.0f && FMath::IsNearlyEqual(Audio.MasterGain(), 0.8f));
  Audio.bAmbienceMuted = false;
  TestTrue("ambience 25 % of master 80 % = 0.2", FMath::IsNearlyEqual(Audio.AmbienceGain(), 0.2f));
  Audio.bMasterMuted = true;
  TestTrue("master mute silences the ambience", Audio.AmbienceGain() == 0.0f && Audio.MasterGain() == 0.0f);
  Temp->MasterVolume = 250;
  Temp->AmbienceVolume = -3;
  TestTrue("out-of-range ini values clamp", Temp->GetSavedAudio().MasterPercent == 100 && Temp->GetSavedAudio().AmbiencePercent == 0);
  Temp->SetToDefaults();
  TestTrue("SetToDefaults resets the volumes", Temp->GetSavedAudio() == FS08AudioSettings());
  Temp->MarkAsGarbage();
  // Applied without a restart: a change of the saved speed is what S08Motion::Current reads next, and OnChanged
  // tells the running game mode to re-read it (the CDO is restored; nothing is written to the ini here).
  US08UserSettings* Live = US08UserSettings::Get();
  const FString SavedSpeed = Live->AnimSpeed;
  int32 Fired = 0;
  const FDelegateHandle Handle = US08UserSettings::OnChanged.AddLambda([&Fired] { ++Fired; });
  const bool bSpeedFlag = FString(FCommandLine::Get()).Contains(TEXT("S08AnimSpeed="));
  Live->AnimSpeed = TEXT("slow");
  US08UserSettings::NotifyChanged();
  TestEqual("OnChanged fires once", Fired, 1);
  if (!bSpeedFlag) {
    TestTrue("the next read sees slow", S08Motion::Current().Speed == ES08AnimSpeed::Slow);
    TestEqual("combat multiplier 1.5", S08Motion::SpeedMul(S08Motion::Current().Speed), 1.5);
  }
  Live->AnimSpeed = SavedSpeed;
  US08UserSettings::OnChanged.Remove(Handle);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveAnimActorTest, "Unmatched.S08.MoveAnim.Actor",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveAnimActorTest::RunTest(const FString&) {
  using namespace S08MoveAnimTest;
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08MoveAnimActorWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  auto Fighter = [](const TCHAR* Name, int32 X, int32 Y) {
    FS08BoardFighter F;
    F.Id = FString::Printf(TEXT("f-%s"), Name);
    F.OwnerId = TEXT("owner");
    F.Name = Name;
    F.Label = Name;
    F.bIsHero = true;
    F.Health = 10;
    F.MaxHealth = 10;
    F.X = X;
    F.Y = Y;
    return F;
  };
  const FS08MoveAnimParams Params;
  const FVector From(0, -400, 0), Mid(100, -400, 0), To(100, -300, 0), Elsewhere(300, -100, 0);
  for (const bool bArt : {false, true}) {
    AS08FighterActor* Actor = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), From, FRotator::ZeroRotator);
    if (!Actor) {
      AddError(TEXT("fighter actor not spawned"));
      continue;
    }
    const FString Tag = bArt ? TEXT("v2 Medusa") : TEXT("grey");
    // The snapshot puts the fighter on its destination first (SyncFighters), then the cue starts the move.
    const FS08BoardFighter AtTo = Fighter(TEXT("Medusa"), 1, 1);
    Actor->ApplyFighter(AtTo, To, true, bArt);
    if (bArt && !Actor->IsHeroV2()) {
      AddWarning(TEXT("v2 Medusa assets missing in this checkout - the art half of the test is skipped"));
      Actor->Destroy();
      continue;
    }
    const FS08MovePlan P = Plan({From, Mid, To}, 280.0);
    Actor->PlayMove(P, Params, 1000);
    TestTrue(Tag + TEXT(": moving"), Actor->IsMoving());
    TestTrue(Tag + TEXT(": starts on the start cell in the snapshot frame (SD-13)"),
             Actor->GetActorLocation().Equals(From, 0.01));
    TestTrue(Tag + TEXT(": the click volume stays on the snapshot cell (MS-R-53)"),
             FVector2D(Actor->GetClickVolumeLocation()).Equals(FVector2D(To), 0.01));
    Actor->TickMove(1000 + 140);
    // AN-21 (ВР-12): the first edge eases in - s(140) = 5/12 of it (the linear pose was 1/2).
    TestTrue(Tag + TEXT(": eased s(140) = 5/12 of the first edge"),
             Actor->GetActorLocation().Equals(FVector(100.0 * 5.0 / 12.0, -400, 0), 0.01));
    if (bArt) {
      TestTrue(Tag + TEXT(": faces the travel direction (+X, yaw 0) and leans 10 deg"),
               NearYaw(Actor->GetFigureYawDeg(), 0.0) && Near(Actor->GetFigureLeanDeg(), 10.0));
      const USkeletalMeshComponent* Body = Actor->FindComponentByClass<USkeletalMeshComponent>();
      if (Body) {
        const FVector Up = Body->GetRelativeRotation().RotateVector(FVector::UpVector);
        TestTrue(Tag + TEXT(": the body mesh leans forward along +X"), Up.X > 0.15 && Up.Z < 0.99);
      }
    }
    // Another snapshot keeps the fighter on the same cell: the move goes on.
    Actor->ApplyFighter(AtTo, To, true, bArt);
    TestTrue(Tag + TEXT(": re-application with the same cell keeps the travelling pose"),
             Actor->IsMoving() && Actor->GetActorLocation().Equals(FVector(100.0 * 5.0 / 12.0, -400, 0), 0.01));
    Actor->TickMove(1000 + 560 + 150);
    TestFalse(Tag + TEXT(": done after the arrival + Idle settle"), Actor->IsMoving());
    TestTrue(Tag + TEXT(": on the destination"), Actor->GetActorLocation().Equals(To, 0.01));
    TestTrue(Tag + TEXT(": rest facing of the destination (yaw 90), no lean"),
             NearYaw(Actor->GetFigureYawDeg(), FS08MoveAnim::RestYawDeg(To)) && Near(Actor->GetFigureLeanDeg(), 0.0));
    const UCapsuleComponent* Capsule = Actor->FindComponentByClass<UCapsuleComponent>();
    if (Capsule) {
      TestTrue(Tag + TEXT(": click volume back on the figure"), !Capsule->IsUsingAbsoluteLocation() &&
                                                                    FVector2D(Capsule->GetComponentLocation()).Equals(FVector2D(To), 0.01));
      TestEqual(Tag + TEXT(": click contract restored (art capsule / grey box)"),
                static_cast<int32>(Capsule->GetCollisionEnabled()),
                static_cast<int32>(bArt ? ECollisionEnabled::QueryOnly : ECollisionEnabled::NoCollision));
    }
    // jump_to_final: a new snapshot cell during the move lands the old move and takes the new cell.
    Actor->ApplyFighter(Fighter(TEXT("Medusa"), 2, 1), Mid, true, bArt);
    Actor->PlayMove(Plan({To, Mid}, 280.0), Params, 5000);
    Actor->TickMove(5000 + 100);
    Actor->ApplyFighter(Fighter(TEXT("Medusa"), 3, 3), Elsewhere, true, bArt);
    TestTrue(Tag + TEXT(": jump_to_final on a new cell"), !Actor->IsMoving() && Actor->GetActorLocation().Equals(Elsewhere, 0.01));
    // Skip (any key): the whole move lands in one call.
    Actor->ApplyFighter(Fighter(TEXT("Medusa"), 1, 1), To, true, bArt);
    Actor->PlayMove(Plan({Elsewhere, Mid, To}, 280.0), Params, 9000);
    TestTrue(Tag + TEXT(": skip lands the move at once"),
             Actor->FinishMove() && !Actor->IsMoving() && Actor->GetActorLocation().Equals(To, 0.01));
    TestFalse(Tag + TEXT(": a second skip has nothing to land"), Actor->FinishMove());
    if (bArt) {
      // PLACE on a v2 figure: the body carries the dissolve MIC while it fades, the body MI comes back after.
      const USkeletalMeshComponent* Body = Actor->FindComponentByClass<USkeletalMeshComponent>();
      const UMaterialInterface* Before = Body ? Body->GetMaterial(0) : nullptr;
      Actor->ApplyFighter(Fighter(TEXT("Medusa"), 3, 3), Elsewhere, true, bArt);
      Actor->PlayMove(Plan({To, Elsewhere}, 240.0, 0.0, ES08MoveKind::Place), Params, 20000);
      Actor->TickMove(20000 + 60);
      const UMaterialInterface* During = Body ? Body->GetMaterial(0) : nullptr;
      TestTrue(Tag + TEXT(": PLACE fades out on the old cell"),
               Actor->GetActorLocation().Equals(To, 0.01) && Near(Actor->GetMovePose().Fade, 0.5));
      if (During == Before) AddWarning(TEXT("PLACE: dissolve MIC missing - the transfer has no fade (fallback)"));
      Actor->TickMove(20000 + 240);
      TestTrue(Tag + TEXT(": PLACE lands with the body MI back"),
               !Actor->IsMoving() && Actor->GetActorLocation().Equals(Elsewhere, 0.01) &&
                   (Body ? Body->GetMaterial(0) == Before : true));
    }
    Actor->Destroy();
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
