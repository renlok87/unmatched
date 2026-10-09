// VS-6 F1 automation tests (S08FieldFx.h): the keyframes of the field / choice cards at their time stamps and the
// pure plate parts of FX-08 / FX-14.
//   Unmatched.S08.FieldFx.Timing    FX-07 / FX-09 / FX-10 / FX-13 / FX-15 / FX-16 curves (and reduced motion)
//   Unmatched.S08.FieldFx.LastPath  FX-14: the last move becomes dashes + arrow (not the MS-T-17 outlines); the
//                                   rollback -S08LastMoveLegacy keeps the outlines; the tracker holds 1500 ms
//   Unmatched.S08.FieldFx.Rows      CUE-002 / 003 / 004 / 007 rows of the dispatcher: local / server, durations, the
//                                   300 ms throttle of the refusal sound, the CUE-007 snap with reduced motion
//   Unmatched.S08.FieldFx.Fades     VC C3: the 80 ms chevron cut (ВР-VC-13), the bench chevron age under reduced
//                                   motion (ВР-VC-15), the 100 ms fade of a replaced last path (ВР-VC-14)
#if WITH_AUTOMATION_TESTS

#include "S08FieldFx.h"
#include "S08LastPathFade.h"
#include "../S08CueDispatcher.h"
#include "../S08MoveHighlight.h"
#include "../../S09/S09OpponentView.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FieldFxTimingTest, "Unmatched.S08.FieldFx.Timing",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FieldFxTimingTest::RunTest(const FString&) {
  using namespace S08FieldFx;
  // FX-07: 0 ms scale 0.85 / opacity 0, 120 ms -> 1.0 / 1, hold to 250; cancel 150 ms; reduced: no scale, 100 ms
  TestEqual("V-05 0 ms scale", SelectionAppear(0.0, false).Scale, 0.85f);
  TestEqual("V-05 0 ms opacity", SelectionAppear(0.0, false).Opacity, 0.0f);
  TestEqual("V-05 120 ms scale", SelectionAppear(120.0, false).Scale, 1.0f);
  TestEqual("V-05 120 ms opacity", SelectionAppear(120.0, false).Opacity, 1.0f);
  TestFalse("V-05 held until 250", SelectionAppear(200.0, false).bDone);
  TestTrue("V-05 done at 250", SelectionAppear(250.0, false).bDone);
  TestEqual("V-05 reduced keeps scale 1", SelectionAppear(10.0, true).Scale, 1.0f);
  TestTrue("V-05 reduced done by 100", SelectionAppear(100.0, true).bDone);
  TestEqual("V-05 cancel half", SelectionLeave(75.0, false).Opacity, 0.5f);
  TestTrue("V-05 cancel done at 150", SelectionLeave(150.0, false).bDone);
  // FX-15: 1.15 -> 1.0 over 150 ms, leave 120 ms
  TestEqual("arcs 0 ms scale", TargetAppear(0.0, false).Scale, 1.15f);
  TestEqual("arcs 150 ms scale", TargetAppear(150.0, false).Scale, 1.0f);
  TestTrue("arcs leave done at 120", TargetLeave(120.0, false).bDone);
  // FX-09: 1.06 -> 1.0 over 250 ms (ease-out), fill 1 -> 0, brightness 1 -> 0.7; reduced: no scale, <= 100 ms
  TestEqual("pulse 0 ms scale", ConfirmPulse(0.0, false).Scale, 1.06f);
  TestEqual("pulse 0 ms fill", ConfirmPulse(0.0, false).Fill, 1.0f);
  TestTrue("pulse 120 ms between", ConfirmPulse(120.0, false).Scale < 1.06f && ConfirmPulse(120.0, false).Scale > 1.0f);
  TestEqual("pulse 250 ms scale", ConfirmPulse(250.0, false).Scale, 1.0f);
  TestEqual("pulse 250 ms dim", ConfirmPulse(250.0, false).Dim, 0.7f);
  TestTrue("pulse done at 250", ConfirmPulse(250.0, false).bDone);
  TestEqual("pulse reduced scale", ConfirmPulse(30.0, true).Scale, 1.0f);
  TestTrue("pulse reduced done by 100", ConfirmPulse(100.0, true).bDone);
  // FX-10: 1.2 -> 1.0 in 80 ms, hold 80..230, out 230..350; reduced opacity only within 100
  TestEqual("X 0 ms scale", RefuseStamp(0.0, false).Scale, 1.2f);
  TestEqual("X 80 ms", RefuseStamp(80.0, false).Opacity, 1.0f);
  TestEqual("X 200 ms held", RefuseStamp(200.0, false).Opacity, 1.0f);
  TestTrue("X 290 ms fading", RefuseStamp(290.0, false).Opacity < 1.0f && RefuseStamp(290.0, false).Opacity > 0.0f);
  TestTrue("X done at 350", RefuseStamp(350.0, false).bDone);
  TestEqual("X reduced scale 1", RefuseStamp(10.0, true).Scale, 1.0f);
  TestTrue("X reduced done by 100", RefuseStamp(100.0, true).bDone);
  TestEqual("X badge floor 24 px", RefuseBadgePx(40.0f), 24.0f);
  TestEqual("X badge ceiling 32 px", RefuseBadgePx(200.0f), 32.0f);
  TestEqual("retrigger 300 ms", RefuseRetriggerMs, 300.0);
  // FX-13: 3..5 discs; 0 ms radius 6 at the pedestal edge, 180 ms out to the spread with radius 10, 300 ms gone
  for (uint32 Seed = 0; Seed < 9; ++Seed) {
    const int32 N = DustCount(Seed);
    TestTrue(FString::Printf(TEXT("dust seed %u count 3..5"), Seed), N >= 3 && N <= 5);
  }
  TestEqual("dust 0 ms radius", DustAt(0.0, 30.0f).RadiusUU, 6.0f);
  TestEqual("dust 0 ms opacity", DustAt(0.0, 30.0f).Opacity, 1.0f);
  TestEqual("dust 180 ms spread", DustAt(180.0, 30.0f).DistUU, 30.0f);
  TestEqual("dust 180 ms radius", DustAt(180.0, 30.0f).RadiusUU, 10.0f);
  TestEqual("dust 300 ms radius", DustAt(300.0, 30.0f).RadiusUU, 11.0f);
  TestEqual("dust 300 ms gone", DustAt(300.0, 30.0f).Opacity, 0.0f);
  TestEqual("dust lives 300 ms", DustMs, 300.0);
  // FX-16: chevron i from 120 x i, 0.6 -> 1 over 80 ms; all three lit 240..480; out 480..600
  TestEqual("chevron 1 at t0", ChevronAt(0, 0.0).Scale, 0.6f);
  TestEqual("chevron 1 shown at t0", ChevronAt(0, 0.0).Opacity, 1.0f);
  TestEqual("chevron 2 dark at +100", ChevronAt(1, 100.0).Opacity, 0.0f);
  TestEqual("chevron 2 at +200", ChevronAt(1, 200.0).Scale, 1.0f);
  TestEqual("chevron 3 lit at +480", ChevronAt(2, 479.0).Opacity, 1.0f);
  TestEqual("all out at +600", ChevronAt(0, 600.0).Opacity, 0.0f);
  TestEqual("t0 = event + 150", ChevronDelayMs, 150.0);
  TestTrue("chevron >= 0.35 R far", ChevronWidthUU(400.0f, 41.0f) >= 0.35f * 41.0f - 1e-3f);
  TestTrue("chevron >= 0.2 R near", ChevronWidthUU(60.0f, 41.0f) >= 0.2f * 41.0f - 1e-3f);
  TestTrue("chevron <= 0.6 R", ChevronWidthUU(4000.0f, 41.0f) <= 0.6f * 41.0f + 1e-3f);
  return true;
}

namespace S08FieldFxTest {
FS08BoardModel Grid() {
  FS08BoardModel Board;
  Board.Width = 4;
  Board.Height = 3;
  Board.Cells.SetNum(Board.Width * Board.Height);
  for (int32 I = 0; I < Board.Cells.Num(); ++I) {
    Board.Cells[I].Type = ES08CellType::Normal;
    Board.Cells[I].X = I % Board.Width;
    Board.Cells[I].Y = I / Board.Width;
  }
  return Board;
}
}  // namespace S08FieldFxTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FieldFxLastPathTest, "Unmatched.S08.FieldFx.LastPath",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FieldFxLastPathTest::RunTest(const FString&) {
  const FS08BoardModel Board = S08FieldFxTest::Grid();
  TArray<FS08BoardFighter> Fighters;
  FS08MoveDraftInput In;
  In.LastMove.From = {FIntPoint(0, 0)};
  In.LastMove.To = {FIntPoint(2, 0)};
  In.LastMove.Dots = {FIntPoint(1, 0)};
  In.LastMove.Paths = {{FIntPoint(0, 0), FIntPoint(1, 0), FIntPoint(2, 0)}};
  In.LastMove.Places = {false};
  In.LastMove.Color = ES08PlateColor::TeamP2;
  S08FieldFx::SetLegacyOverrideForTest(0);
  {
    const FS08MoveDraftView View = S08MoveHighlight::BuildDraftView(Board, Fighters, In);
    TestEqual("one dashed path", View.LastPaths.Num(), 1);
    TestEqual("path has the start + 2 cells", View.LastPaths.Num() ? View.LastPaths[0].Cells.Num() : 0, 3);
    TestTrue("path in the mover's colour", View.LastPaths.Num() && View.LastPaths[0].Color == ES08PlateColor::TeamP2);
    const FS08PlateView* End = View.Find(2, 0);
    TestTrue("no outline at the end (the contour is the rollback)", !End || End->Outline == ES08OutlineState::None);
  }
  S08FieldFx::SetLegacyOverrideForTest(S08FieldFx::LastMove);
  {
    const FS08MoveDraftView View = S08MoveHighlight::BuildDraftView(Board, Fighters, In);
    TestEqual("legacy: no dashed path", View.LastPaths.Num(), 0);
    const FS08PlateView* End = View.Find(2, 0);
    TestTrue("legacy: the MS-T-17 outline", End && End->Outline == ES08OutlineState::LastTo);
  }
  S08FieldFx::ResetLegacyOverrideForTest();
  // ВР-29: shown -> hold 1500 -> fade 300 -> off; appear 150
  FS09LastMoveTracker Tracker;
  Tracker.HoldMs = 1500.0;
  Tracker.InMs = 150.0;
  FS09LastMovement Trail;
  Trail.bValid = true;
  Trail.Seq = 10;
  Trail.PlayerId = TEXT("p2");
  FS09LastMovement::FMove Move;
  Move.FighterId = TEXT("f");
  Move.From = FIntPoint(0, 0);
  Move.Path = {FIntPoint(1, 0)};
  Trail.Moves.Add(Move);
  FS09BoardStamp Stamp;
  Stamp.bSet = true;
  Tracker.OnApplied(10, Trail, Stamp, 0.0, false);
  Tracker.Tick(0.0, false);
  TestTrue("shown at reveal", Tracker.GetState() == ES09LastMoveState::Shown);
  TestEqual("appear: 0 at the reveal", Tracker.Alpha(0.0), 0.0f);
  TestEqual("appear: 1 after 150 ms", Tracker.Alpha(150.0), 1.0f);
  Tracker.Tick(1600.0, false);
  TestTrue("still shown at +1600 (150 + 1500 not reached)", Tracker.GetState() == ES09LastMoveState::Shown);
  Tracker.Tick(1650.0, false);
  TestTrue("fading at +1650", Tracker.GetState() == ES09LastMoveState::Fading);
  Tracker.Tick(1950.0, false);
  TestTrue("off at +1950 (the trail never lives longer)", Tracker.GetState() == ES09LastMoveState::None);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FieldFxRowsTest, "Unmatched.S08.FieldFx.Rows",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FieldFxRowsTest::RunTest(const FString&) {
  FS08CueDispatcher Cues;
  Cues.AssetResolver = [](const FString& CueId, const FString& Channel, const FString&) -> FString {
    if (Channel == TEXT("sfx")) return TEXT("SW_Test_Ui");
    if (Channel == TEXT("vfx") && CueId == TEXT("CUE-007")) return TEXT("NS_FX_Dust");
    return FString();
  };
  TArray<FString> Lines;
  Cues.Feed(TEXT("CUE-002"), TEXT("f-0-hero"), -1, 0, Lines);
  TestEqual("CUE-002 local line", Lines.Last(),
            FString(TEXT("CUE fx id=CUE-002 subject=f-0-hero seq=- t=0 vfx=none sfx=SW_Test_Ui clip=none mat=none "
                         "socket=- reduced=0 result=spawned")));
  Cues.Feed(TEXT("CUE-004"), TEXT("cell-1-1"), -1, 300, Lines);
  Cues.Feed(TEXT("CUE-004"), TEXT("cell-1-1"), -1, 450, Lines);
  TestTrue("CUE-004 repeat within 300 ms: the sound throttled", Lines.Last().Contains(TEXT("sfx=throttled")));
  Cues.Feed(TEXT("CUE-007"), TEXT("f-0-sk0"), 41, 1000, Lines, 0, 560, true);
  TestTrue("CUE-007 names NS_FX_Dust", Lines.Last().Contains(TEXT("vfx=NS_FX_Dust")));
  Cues.Advance(1560, Lines);
  TestEqual("CUE-007 lasts its plan", Lines.Last(),
            FString(TEXT("CUE fx done id=CUE-007 subject=f-0-sk0 seq=41 t=1560 ms=560 cut=0")));
  Cues.SetReducedMotion(true, 1600, Lines);
  Cues.Feed(TEXT("CUE-007"), TEXT("f-0-sk0"), 42, 1600, Lines, 0, 560, true);
  TestEqual("CUE-007 reduced = snap", Lines.Last(),
            FString(TEXT("CUE fx done id=CUE-007 subject=f-0-sk0 seq=42 t=1600 ms=0 cut=0")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FieldFxFadesTest, "Unmatched.S08.FieldFx.Fades",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FieldFxFadesTest::RunTest(const FString&) {
  using namespace S08FieldFx;
  // FX-16 «прерывание (гаснут за 80 мс)»
  TestEqual("cut 0 ms: 1", ChevronCutOpacity(0.0), 1.0f);
  TestEqual("cut 40 ms: 0.5", ChevronCutOpacity(40.0), 0.5f, 0.001f);
  TestEqual("cut 80 ms: 0", ChevronCutOpacity(80.0), 0.0f);
  TestEqual("cut 200 ms: 0", ChevronCutOpacity(200.0), 0.0f);
  TestEqual("bench chevrons normal: as given", BenchChevronMs(240.0, false), 240.0);
  TestEqual("bench chevrons reduced: x6", BenchChevronMs(40.0, true), 240.0);
  TestEqual("bench chevrons reduced: all three held before the fade", BenchChevronMs(240.0, true), 470.0);
  // FX-14 «новый ход до угасания (старый гаснет за 100 мс)»
  FS08MoveDraftInput::FLastMove A;
  A.From.Add(FIntPoint(1, 1));
  A.To.Add(FIntPoint(2, 1));
  A.Paths.Add({FIntPoint(1, 1), FIntPoint(2, 1)});
  A.Places.Add(false);
  FS08OldPathFade Fade;
  TestTrue("drawn: nothing to say", Fade.Observe(true, 10, &A, 1.0f, 1000.0).IsEmpty());
  TestTrue("drawn: the tracker draws", Fade.Shown(true, 10) == nullptr);
  // the tracker replaced seq 10 by seq 12 (Waiting): before the tick observes it, the plates keep the old path
  const FS08MoveDraftInput::FLastMove* Pending = Fade.Shown(false, 12);
  TestTrue("replace seen before the tick: the old path stays", Pending && Pending->To.Num() == 1);
  const FString Start = Fade.Observe(false, 12, nullptr, 0.0f, 1020.0);
  TestTrue("fade starts", Start.StartsWith(TEXT("MS-LAST old-fade start seq=10 by=12")));
  TestTrue("fading", Fade.IsFading());
  TestEqual("old alpha at +50: 0.5", Fade.Alpha(1070.0), 0.5f, 0.001f);
  TestTrue("the fading path is drawn", Fade.Shown(false, 12) != nullptr);
  const uint32 Rev = Fade.GetRevision();
  const FString End = Fade.Observe(false, 12, nullptr, 0.0f, 1120.0);
  TestTrue("fade ends at +100", End.StartsWith(TEXT("MS-LAST old-fade end seq=10")));
  TestTrue("revision moved", Fade.GetRevision() != Rev);
  TestTrue("after the fade: nothing", Fade.Shown(false, 12) == nullptr);
  // a fade from a fading tracker (alpha 0.4) starts at 0.4; the new path revealed ends the fade at once
  FS08OldPathFade F2;
  F2.Observe(true, 20, &A, 0.4f, 0.0);
  F2.Observe(false, 21, nullptr, 0.0f, 10.0);
  TestEqual("from the tracker's alpha", F2.Alpha(10.0), 0.4f, 0.001f);
  TestTrue("revealed new path ends it", F2.Observe(true, 21, &A, 0.0f, 40.0).Contains(TEXT("reason=shown")));
  TestFalse("not fading", F2.IsFading());
  // the tracker's own end (same seq goes to none): no extra fade
  FS08OldPathFade F3;
  F3.Observe(true, 30, &A, 0.2f, 0.0);
  TestTrue("same seq off: no old fade", F3.Observe(false, 30, nullptr, 0.0f, 10.0).IsEmpty());
  TestFalse("same seq off: not fading", F3.IsFading());
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
