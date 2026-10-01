// ART-004 stage 3 T2.2 automation tests: zoom config/rig (03 §2), plate
// placement and the qa010 overlap rule, QA-010 trace formats, input plan and
// icon-size parsing, exactly-once damage numbers, all-Medusa eligibility and
// the click capsule of the live candidate. Headless run (art worktree):
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.ArtHud; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08ArtHud.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08FighterActor.h"
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Internationalization/Regex.h"
#include "Misc/AutomationTest.h"

namespace {
constexpr float OverviewCobble = 1931.0f;  // CAMERA dist of the 5x6 Cobble board (traces)

// The qa010 fixture camera (tools/art/qa010/fixtures/new-trace-k2-plate.trace.txt,
// K2 1.6x: SHOT ctx cam=(0,642,1017) rot=(-55,-90,0), 1920x1080).
FS08PinholeCamera FixtureCamera() {
  FS08PinholeCamera Cam;
  Cam.Position = FVector(0.0, 642.0, 1017.0);
  Cam.Rotation = FRotator(-55.0, -90.0, 0.0);
  Cam.HorizontalFovDeg = 35.0f;
  Cam.Viewport = FVector2D(1920.0, 1080.0);
  return Cam;
}

FS08BoardModel CobbleBoard() {
  FS08BoardModel Board;
  Board.Width = 5;
  Board.Height = 6;
  return Board;
}

TArray<FS08CellQuad> ProjectFixtureCells(const TArray<FIntPoint>& Cells) {
  const FS08PinholeCamera Cam = FixtureCamera();
  const FS08BoardModel Board = CobbleBoard();
  TArray<FS08CellQuad> Out;
  for (const FIntPoint& Cell : Cells) {
    FS08CellQuad Quad;
    Quad.Cell = Cell;
    const FVector C = Board.CellToWorld(Cell.X, Cell.Y);
    for (const FVector2D& D : {FVector2D(-50, -50), FVector2D(50, -50), FVector2D(50, 50), FVector2D(-50, 50)}) {
      FVector2D S;
      if (Cam.Project(C + FVector(D.X, D.Y, 0.0), S)) Quad.Screen.Add(S);
    }
    Out.Add(Quad);
  }
  return Out;
}

// Reachable cells of f-0-hero in the qa010 fixture (14 destinations).
TArray<FIntPoint> FixtureReachable() {
  return {{1, 0}, {2, 0}, {3, 0}, {0, 1}, {1, 1}, {3, 1}, {4, 1}, {0, 2}, {4, 2}, {0, 3}, {1, 3}, {4, 3}, {1, 4}, {3, 4}};
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudZoomWheelTest,
    "Unmatched.S08.ArtHud.Zoom wheel steps, near/far clamps and the traced limit",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudZoomWheelTest::RunTest(const FString&) {
  FS08CameraZoom Zoom;
  Zoom.Reset(OverviewCobble);
  TestEqual("nearest = MinDistanceUU", Zoom.MinDistance(), 300.0f);
  TestTrue("farthest = overview / 0.65", FMath::IsNearlyEqual(Zoom.MaxDistance(), OverviewCobble / 0.65f, 0.01f));
  FS08ZoomStep Step = Zoom.Wheel(+1);
  TestTrue("one notch in = /1.25", FMath::IsNearlyEqual(Step.To, OverviewCobble / 1.25f, 0.01f));
  TestFalse("first notch not clamped", Step.bClamped);
  TestTrue("wheel animation 200 ms", FMath::IsNearlyEqual(Step.Seconds, 0.2f));
  int32 Unclamped = 1;
  for (int32 I = 0; I < 20; ++I) {
    Step = Zoom.Wheel(+1);
    if (Step.bClamped) break;
    ++Unclamped;
  }
  TestEqual("8 notches fit before the 300 uu limit (1931/1.25^8 = 323.9)", Unclamped, 8);
  TestTrue("9th notch clamps", Step.bClamped);
  TestEqual("clamped at the near limit", static_cast<int32>(Step.Limit), static_cast<int32>(ES08ZoomLimit::Near));
  TestEqual("clamped distance = 300", Step.To, 300.0f);
  Step = Zoom.Wheel(+1);
  TestTrue("notch at the limit is reported as clamp", Step.bClamped && Step.To == 300.0f &&
                                                       Step.Limit == ES08ZoomLimit::Near);
  Zoom.Reset(OverviewCobble);
  Step = Zoom.Wheel(-1);
  TestTrue("one notch out = x1.25", FMath::IsNearlyEqual(Step.To, OverviewCobble * 1.25f, 0.01f) && !Step.bClamped);
  Step = Zoom.Wheel(-1);
  TestTrue("second notch out clamps at overview/0.65", Step.bClamped && Step.Limit == ES08ZoomLimit::Far &&
                                                           FMath::IsNearlyEqual(Step.To, OverviewCobble / 0.65f, 0.01f));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudZoomMapOverviewTest,
    "Unmatched.S08.ArtHud.Zoom ENV-U9 map overview: fit x 1.25 = 2340, near 300 uu, far fit/0.65 = 0.8125x, follow one notch in",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudZoomMapOverviewTest::RunTest(const FString&) {
  // The map canvas of Marmoreal / Sarpedon (1337 x 866 px at 2/3 uu per px, halved) and its profile's k1DistanceMul.
  const FVector2D MapHalf(445.66667, 288.66667);
  const float Fit = S08K1FitDistanceUU(MapHalf);
  const float Overview = S08K1OverviewDistanceUU(Fit, 1.25f);
  TestTrue(FString::Printf(TEXT("map fit %.3f = 1872.156 +- 0.5"), Fit), FMath::Abs(Fit - 1872.156f) <= 0.5f);
  TestTrue(FString::Printf(TEXT("map overview %.3f = fit x 1.25 = 2340.195 +- 0.5"), Overview),
           FMath::IsNearlyEqual(Overview, Fit * 1.25f) && FMath::Abs(Overview - 2340.195f) <= 0.5f);
  FS08CameraZoom Zoom;
  Zoom.Reset(Overview, Fit);
  TestTrue("starts at the overview", Zoom.Current == Overview && Zoom.Target == Overview && Zoom.Fit == Fit);
  TestEqual("nearest = the absolute MinDistanceUU", Zoom.MinDistance(), 300.0f);
  TestTrue(FString::Printf(TEXT("farthest %.2f = fit / 0.65 = 2880.2 (as before ENV-U9)"), Zoom.MaxDistance()),
           FMath::IsNearlyEqual(Zoom.MaxDistance(), Fit / 0.65f, 0.01f) && FMath::Abs(Zoom.MaxDistance() - 2880.24f) <= 0.5f);
  TestTrue(FString::Printf(TEXT("far zoom %.4f = 0.65 x 1.25 = 0.8125 of the new overview"), Zoom.ZoomOf(Zoom.MaxDistance())),
           FMath::IsNearlyEqual(Zoom.ZoomOf(Zoom.MaxDistance()), 0.8125f, 1e-4f));
  TestTrue(FString::Printf(TEXT("near zoom %.3f = 2340.2 / 300 = 7.80"), Zoom.ZoomOf(Zoom.MinDistance())),
           FMath::IsNearlyEqual(Zoom.ZoomOf(Zoom.MinDistance()), Overview / 300.0f, 1e-4f));
  TestFalse("the overview does not follow", Zoom.WantsFollow());
  // Out: one notch (2925.2 requested) reaches the far limit, the next one is a clamp at it.
  FS08ZoomStep Step = Zoom.Wheel(-1);
  TestTrue(FString::Printf(TEXT("one notch out: requested %.1f -> %.1f clamped at the far limit"), Step.Requested, Step.To),
           Step.bClamped && Step.Limit == ES08ZoomLimit::Far && FMath::IsNearlyEqual(Step.To, Fit / 0.65f, 0.01f) &&
               FMath::IsNearlyEqual(Step.Requested, Overview * 1.25f, 0.01f));
  Step = Zoom.Wheel(-1);
  TestTrue("a second notch out stays at the far limit", Step.bClamped && Step.Limit == ES08ZoomLimit::Far &&
                                                            FMath::IsNearlyEqual(Step.To, Fit / 0.65f, 0.01f));
  // Space, then in: the first notch is the fit (the pre-ENV-U9 K1 framing) and already follows (1.25 >= 1.2).
  Step = Zoom.ReturnToOverview();
  TestTrue("Space -> the new overview", Step.To == Overview && !Step.bClamped);
  Step = Zoom.Wheel(+1);
  TestTrue(FString::Printf(TEXT("one notch in = the fit %.2f"), Step.To), FMath::IsNearlyEqual(Step.To, Fit, 0.01f) && !Step.bClamped);
  TestTrue("zoom 1.25 of the overview follows the selection", Zoom.WantsFollow());
  int32 Unclamped = 1;
  for (int32 I = 0; I < 20; ++I) {
    Step = Zoom.Wheel(+1);
    if (Step.bClamped) break;
    ++Unclamped;
  }
  TestEqual("9 notches fit before the 300 uu limit (2340.2/1.25^9 = 314.1)", Unclamped, 9);
  TestTrue("then the absolute near limit", Step.bClamped && Step.Limit == ES08ZoomLimit::Near && Step.To == 300.0f);
  // Flag / bench focus zoom: relative to the new overview (K2 1.6x = 1462.6 uu; the pre-ENV-U9 1170 uu is 2x).
  Zoom.Reset(Overview, Fit);
  FS08ZoomStep K2 = Zoom.FocusZoom(1.6f);
  TestTrue(FString::Printf(TEXT("K2 1.6x = %.1f = overview / 1.6"), K2.To),
           FMath::IsNearlyEqual(K2.To, Overview / 1.6f, 0.01f) && !K2.bClamped);
  K2 = Zoom.FocusZoom(2.0f);
  TestTrue(FString::Printf(TEXT("2x = %.1f = the pre-ENV-U9 K2 1.6x (fit / 1.6)"), K2.To),
           FMath::IsNearlyEqual(K2.To, Fit / 1.6f, 0.01f));
  K2 = Zoom.FocusZoom(0.5f);
  TestTrue("a focus zoom below 1 stays at the overview", FMath::IsNearlyEqual(K2.To, Overview, 0.01f));
  // Grids: the single-argument Reset (and Fit == Overview) is the historical rig, far limit bit for bit.
  FS08CameraZoom Grid;
  Grid.Reset(OverviewCobble);
  TestTrue("grid: fit = overview", Grid.Fit == OverviewCobble);
  TestTrue("grid: far limit = overview / 0.65", FMath::IsNearlyEqual(Grid.MaxDistance(), OverviewCobble / 0.65f, 0.01f));
  FS08CameraZoom GridExplicit;
  GridExplicit.Reset(OverviewCobble, OverviewCobble);
  TestTrue("grid: an explicit fit == overview gives the same far limit", GridExplicit.MaxDistance() == Grid.MaxDistance());
  FS08CameraZoom NoOut;
  NoOut.Config.OverviewOutRatio = 1.0f;
  NoOut.Reset(Overview, Fit);
  TestTrue("out ratio 1 on a map: the far limit never comes nearer than the overview", NoOut.MaxDistance() == Overview);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudZoomAnimationTest,
    "Unmatched.S08.ArtHud.Zoom animation lasts exactly the configured 150-250 ms and is monotonic",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudZoomAnimationTest::RunTest(const FString&) {
  FS08CameraZoom Zoom;
  TestTrue("default within 03 §2 range", Zoom.Config.ZoomAnimSeconds >= FS08CameraZoomConfig::MinAnimSeconds &&
                                            Zoom.Config.ZoomAnimSeconds <= FS08CameraZoomConfig::MaxAnimSeconds);
  Zoom.Reset(OverviewCobble);
  const FS08ZoomStep Step = Zoom.Wheel(+1);
  float Previous = Zoom.Current;
  float T = 0.0f;
  while (T < Step.Seconds - 0.021f) {
    Zoom.Tick(1.0f / 60.0f);
    T += 1.0f / 60.0f;
    TestTrue("distance decreases monotonically", Zoom.Current <= Previous + 0.001f);
    Previous = Zoom.Current;
  }
  TestFalse("not settled before the animation length", Zoom.IsSettled());
  Zoom.Tick(0.03f);
  TestTrue("settled exactly at the animation length", Zoom.IsSettled() && Zoom.Current == Zoom.Target);

  FS08CameraZoomConfig Cfg;
  Cfg.ZoomAnimSeconds = 0.5f;
  Cfg.MinDistanceUU = -1.0f;
  Cfg.Sanitize();
  TestEqual("too slow animation clamped to 250 ms", Cfg.ZoomAnimSeconds, 0.25f);
  TestEqual("negative min distance clamped", Cfg.MinDistanceUU, 50.0f);
  TestEqual("each correction recorded", Cfg.Issues.Num(), 2);

  FS08CameraZoomConfig Cli;
  Cli.ApplyCommandLine(TEXT("-S08CameraAnimMs=180 -S08CameraMinDist=250 -S08CameraFollowFrom=1.5"));
  Cli.Sanitize();
  TestTrue("cli anim", FMath::IsNearlyEqual(Cli.ZoomAnimSeconds, 0.18f));
  TestEqual("cli min distance", Cli.MinDistanceUU, 250.0f);
  TestTrue("cli follow", FMath::IsNearlyEqual(Cli.FollowFromZoom, 1.5f));
  TestTrue("source says cli", Cli.Source.Contains(TEXT("cli")));
  TestTrue("describe carries the values", Cli.Describe().Contains(TEXT("animMs=180")) &&
                                             Cli.Describe().Contains(TEXT("minDist=250.0")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudZoomSpaceFollowTest,
    "Unmatched.S08.ArtHud.Zoom Space returns to the overview, follow-selection starts at 1.2x, flag zoom clamps",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudZoomSpaceFollowTest::RunTest(const FString&) {
  FS08CameraZoom Zoom;
  Zoom.Reset(1000.0f);
  TestFalse("overview does not follow", Zoom.WantsFollow());
  Zoom.FocusZoom(1.19f);
  TestFalse("1.19x does not follow", Zoom.WantsFollow());
  Zoom.FocusZoom(1.2f);
  TestTrue("1.2x follows", Zoom.WantsFollow());
  Zoom.SetFocusTarget(FVector(0, -50, 28));
  Zoom.Tick(0.1f);
  TestTrue("focus moving", !Zoom.CurrentFocus.IsZero() && !Zoom.CurrentFocus.Equals(FVector(0, -50, 28), 0.01f));
  Zoom.Tick(0.2f);
  TestTrue("focus arrived", Zoom.CurrentFocus.Equals(FVector(0, -50, 28), 0.001f));
  const FS08ZoomStep Space = Zoom.ReturnToOverview();
  TestEqual("Space targets the overview", Space.To, 1000.0f);
  TestTrue("Space animation ~300 ms", FMath::IsNearlyEqual(Space.Seconds, 0.3f));
  TestFalse("no follow after Space", Zoom.WantsFollow());
  Zoom.SetFocusTarget(FVector::ZeroVector);
  Zoom.Tick(0.29f);
  TestFalse("not yet back", Zoom.IsSettled());
  Zoom.Tick(0.02f);
  TestTrue("back at the overview", Zoom.IsSettled() && Zoom.Current == 1000.0f && Zoom.CurrentFocus.IsZero());

  FS08CameraZoom Cobble;
  Cobble.Reset(OverviewCobble);
  FS08ZoomStep K2 = Cobble.FocusZoom(5.0f);
  TestTrue("5x = 386.2 uu, not clamped", FMath::IsNearlyEqual(K2.To, OverviewCobble / 5.0f, 0.01f) && !K2.bClamped);
  K2 = Cobble.FocusZoom(10.0f);
  TestTrue("10x clamps at 300 uu", K2.bClamped && K2.To == 300.0f && K2.Limit == ES08ZoomLimit::Near);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudOverlapRuleTest,
    "Unmatched.S08.ArtHud.Plate overlap rule equals qa010 on the fixture camera (clear 0, overlap 1 = cell (3,1))",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudOverlapRuleTest::RunTest(const FString&) {
  // Polygon basics.
  const TArray<FVector2D> Square = {FVector2D(0, 0), FVector2D(10, 0), FVector2D(10, 10), FVector2D(0, 10)};
  TestTrue("square area", FMath::IsNearlyEqual(S08ArtHud::PolygonArea(Square), 100.0));
  TestTrue("quarter overlap", FMath::IsNearlyEqual(
      S08ArtHud::PolygonArea(S08ArtHud::ClipPolygonToRect(Square, FS08ScreenRect(5, 5, 15, 15))), 25.0));
  TestTrue("disjoint", S08ArtHud::PolygonArea(S08ArtHud::ClipPolygonToRect(Square, FS08ScreenRect(20, 20, 30, 30))) == 0.0);
  const TArray<FVector2D> Triangle = {FVector2D(0, 0), FVector2D(10, 0), FVector2D(0, 10)};
  TestTrue("triangle clipped", FMath::IsNearlyEqual(
      S08ArtHud::PolygonArea(S08ArtHud::ClipPolygonToRect(Triangle, FS08ScreenRect(0, 0, 5, 5))), 25.0, 1e-6));

  // Fixture replay: the same projected full cells qa010 `plate` intersects.
  const FS08PinholeCamera Cam = FixtureCamera();
  FVector2D Hero;
  TestTrue("hero projects", Cam.Project(CobbleBoard().CellToWorld(2, 2), Hero));
  TestTrue("projection matches the traced SHOT fighter screen=(960,580) within 2 px",
           FVector2D::Distance(Hero, FVector2D(960, 580)) <= 2.0);
  const TArray<FS08CellQuad> Quads = ProjectFixtureCells(FixtureReachable());
  TArray<FIntPoint> Hit;
  double Area = 0.0;
  TestEqual("k2-plate-clear: overlapReachable=0",
            S08ArtHud::CountOverlaps(FS08ScreenRect(880, 400, 1040, 470), Quads, S08ArtHud::OverlapEpsilonPx2, &Hit), 0);
  TestEqual("k2-plate-overlap: overlapReachable=1",
            S08ArtHud::CountOverlaps(FS08ScreenRect(1000, 400, 1160, 470), Quads, S08ArtHud::OverlapEpsilonPx2, &Hit, &Area), 1);
  TestTrue("the overlapped cell is (3,1)", Hit.Num() == 1 && Hit[0] == FIntPoint(3, 1));
  TestTrue("overlap area equals qa010 (5623.84 px2)", FMath::IsNearlyEqual(Area, 5623.84, 1.0));
  TestEqual("zero-size plate never overlaps (qa010 flags it separately)",
            S08ArtHud::CountOverlaps(FS08ScreenRect(), Quads, S08ArtHud::OverlapEpsilonPx2), 0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudPlacementTest,
    "Unmatched.S08.ArtHud.Plate placement avoids destination cells and soft obstacles, reports the least bad fallback",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudPlacementTest::RunTest(const FString&) {
  // Real K2 1.6x geometry: fighter f-0-hero at (2,2), its 14 destinations.
  const FS08PinholeCamera Cam = FixtureCamera();
  const FS08BoardModel Board = CobbleBoard();
  TArray<FVector2D> Corners;
  for (const float Z : {0.0f, 55.0f}) {
    for (const float Dx : {-20.0f, 20.0f}) {
      for (const float Dy : {-20.0f, 20.0f}) {
        FVector2D S;
        Cam.Project(Board.CellToWorld(2, 2) + FVector(Dx, Dy, Z), S);
        Corners.Add(S);
      }
    }
  }
  S08ArtHud::FPlacementInput In;
  In.Viewport = FVector2D(1920, 1080);
  In.PlateSize = FVector2D(196, 66);
  In.Anchor = FS08ScreenRect::FromPoints(Corners);
  In.Forbidden = ProjectFixtureCells(FixtureReachable());
  In.Soft.Add(In.Anchor);
  const S08ArtHud::FPlacementResult R = S08ArtHud::ChoosePlateRect(In);
  TestTrue("a clean place exists at K2 1.6x", R.bClean);
  TestEqual("placed plate covers no destination (exact qa010 rule)",
            S08ArtHud::CountOverlaps(R.Rect, In.Forbidden, S08ArtHud::OverlapEpsilonPx2), 0);
  TestTrue("plate fully inside the viewport", FS08ScreenRect(0, 0, 1920, 1080).Contains(R.Rect));
  TestTrue("plate does not cover its own figure", R.Rect.IntersectionArea(In.Anchor) == 0.0);
  TestTrue("plate size kept", FMath::IsNearlyEqual(R.Rect.Width(), 196.0f) && FMath::IsNearlyEqual(R.Rect.Height(), 66.0f));

  // No room at all: the whole viewport is forbidden -> honest overlap count.
  S08ArtHud::FPlacementInput Full = In;
  FS08CellQuad Everything;
  Everything.Cell = FIntPoint(9, 9);
  Everything.Screen = {FVector2D(0, 0), FVector2D(1920, 0), FVector2D(1920, 1080), FVector2D(0, 1080)};
  Full.Forbidden = {Everything};
  const S08ArtHud::FPlacementResult Bad = S08ArtHud::ChoosePlateRect(Full);
  TestFalse("no clean place", Bad.bClean);
  TestEqual("fallback reports the overlap", Bad.ForbiddenOverlaps, 1);

  // Soft obstacle directly below the anchor pushes the plate elsewhere.
  S08ArtHud::FPlacementInput Soft;
  Soft.Viewport = FVector2D(1920, 1080);
  Soft.PlateSize = FVector2D(196, 66);
  Soft.Anchor = FS08ScreenRect(900, 500, 1020, 600);
  Soft.Soft.Add(FS08ScreenRect(700, 600, 1220, 800));
  const S08ArtHud::FPlacementResult Moved = S08ArtHud::ChoosePlateRect(Soft);
  TestTrue("clean", Moved.bClean);
  TestTrue("not below (soft obstacle)", Moved.Candidate != TEXT("below"));
  TestTrue("first clean candidate is above", Moved.Candidate == TEXT("above") && Moved.Ring == 0);

  // W5b-R binding (T5.2 errata "plate under King Arthur"): a neighbour figure right below the owner's slot.
  // Without binding the plate goes below both (clean of soft overlap); with binding it must stay nearer its owner.
  S08ArtHud::FPlacementInput Bind;
  Bind.Viewport = FVector2D(1920, 1080);
  Bind.PlateSize = FVector2D(172, 54);
  Bind.Anchor = FS08ScreenRect(915, 389, 1005, 512);                    // owner (Medusa)
  const FS08ScreenRect Neighbour(914, 517, 1006, 643);                   // King Arthur below the owner
  Bind.Soft = {Bind.Anchor, Neighbour, FS08ScreenRect(1081, 410, 1154, 504), FS08ScreenRect(766, 410, 839, 504)};
  Bind.BindTarget = Bind.Anchor;
  Bind.BindOthers = {Neighbour, FS08ScreenRect(1081, 410, 1154, 504), FS08ScreenRect(766, 410, 839, 504)};
  const S08ArtHud::FPlacementResult Bound = S08ArtHud::ChoosePlateRect(Bind);
  TestTrue("bound plate", Bound.bBound);
  TestTrue("nearer the owner than King Arthur",
           S08ArtHud::RectGap(Bound.Rect, Bind.Anchor) < S08ArtHud::RectGap(Bound.Rect, Neighbour));
  TestTrue("rect gap of touching rects is 0",
           S08ArtHud::RectGap(FS08ScreenRect(0, 0, 10, 10), FS08ScreenRect(10, 0, 20, 10)) == 0.0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudPlateOwnerTest,
    "Unmatched.S08.ArtHud.Plate stays nearest its owner on Cobble K1 (W7 on-owner fallback, GD-058 interim item 13)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudPlateOwnerTest::RunTest(const FString&) {
  // Packaged host trace k1/cobble-5x6/run-20260930-211621 (GD-058 interim 2026-09-30): SHOT ctx cam=(0,1107,1582)
  // rot=(-55,-90,0) 1920x1080; Medusa f-0-hero at (2,2) selected, 13 destinations; SHOT figure / SHOT panel boxes.
  FS08PinholeCamera Cam;
  Cam.Position = FVector(0.0, 1107.0, 1582.0);
  Cam.Rotation = FRotator(-55.0, -90.0, 0.0);
  const FS08BoardModel Board = CobbleBoard();
  const TArray<FIntPoint> Reach = {{1, 0}, {2, 0}, {3, 0}, {0, 1}, {1, 1}, {3, 1}, {4, 1},
                                   {0, 2}, {4, 2}, {0, 3}, {1, 3}, {4, 3}, {1, 4}};
  TArray<FS08CellQuad> Quads;
  for (const FIntPoint& Cell : Reach) {
    FS08CellQuad Quad;
    Quad.Cell = Cell;
    const FVector C = Board.CellToWorld(Cell.X, Cell.Y);
    for (const FVector2D& D : {FVector2D(-50, -50), FVector2D(50, -50), FVector2D(50, 50), FVector2D(-50, 50)}) {
      FVector2D S;
      if (Cam.Project(C + FVector(D.X, D.Y, 0.0), S)) Quad.Screen.Add(S);
    }
    Quads.Add(Quad);
  }
  FVector2D OwnScreen;
  TestTrue("Medusa's cell projects", Cam.Project(Board.CellToWorld(2, 2), OwnScreen));
  TestTrue("camera model matches the trace (SHOT fighter f-0-hero screen=(960,476))",
           FVector2D::Distance(OwnScreen, FVector2D(960, 476)) < 2.0);
  const FS08ScreenRect Medusa(914, 389, 1006, 512);
  const TArray<FS08ScreenRect> Others = {
      FS08ScreenRect(1080, 409, 1155, 504),   // Harpy 1
      FS08ScreenRect(926, 288, 994, 381),     // Harpy 2
      FS08ScreenRect(765, 409, 840, 504),     // Harpy 3
      FS08ScreenRect(913, 513, 1007, 644),    // King Arthur
      FS08ScreenRect(1084, 531, 1161, 635)};  // Merlin
  S08ArtHud::FPlacementInput In;
  In.Viewport = FVector2D(1920, 1080);
  In.PlateSize = FVector2D(172, 54);
  In.Anchor = Medusa;
  In.Forbidden = Quads;
  In.Soft = {Medusa};
  In.Soft.Append(Others);
  In.Soft.Append({FS08ScreenRect(0, 0, 601, 138), FS08ScreenRect(1432, 0, 1920, 121),
                  FS08ScreenRect(435, 985, 1486, 1080)});  // hud.command / hud.side / hud.hand
  In.BindTarget = Medusa;
  In.BindOthers = Others;
  auto NearestIsOwner = [&](const FS08ScreenRect& Plate) {
    const double Own = S08ArtHud::RectGap(Plate, Medusa);
    for (const FS08ScreenRect& O : Others) {
      if (S08ArtHud::RectGap(Plate, O) <= Own) return false;
    }
    return true;
  };

  // Pre-W7 behaviour (the defect): the least bad place is off the destination cells but next to a foreign figure.
  S08ArtHud::FPlacementInput Old = In;
  Old.bAllowOnOwner = false;
  const S08ArtHud::FPlacementResult Before = S08ArtHud::ChoosePlateRect(Old);
  TestFalse("pre-W7: no clean place on Cobble K1", Before.bClean);
  TestFalse("pre-W7: the plate is not bound (reads as Merlin's / King Arthur's)", Before.bBound);
  TestFalse("pre-W7: nearest figure is not the owner", NearestIsOwner(Before.Rect));

  const S08ArtHud::FPlacementResult R = S08ArtHud::ChoosePlateRect(In);
  TestEqual("on-owner candidate", R.Candidate, FString(TEXT("on-owner")));
  TestTrue("bound to the owner", R.bBound);
  TestTrue("nearest figure is the owner (rect gap, plate_owner_proximity rule)", NearestIsOwner(R.Rect));
  TestEqual("covers no destination cell (exact qa010 rule, K-2 gate kept)",
            S08ArtHud::CountOverlaps(R.Rect, In.Forbidden, S08ArtHud::OverlapEpsilonPx2), 0);
  TestEqual("covers no destination cell with the placement margin", R.ForbiddenOverlaps, 0);
  TestTrue("plate size kept", FMath::IsNearlyEqual(R.Rect.Width(), 172.0f) && FMath::IsNearlyEqual(R.Rect.Height(), 54.0f));
  TestTrue("plate fully inside the viewport", FS08ScreenRect(0, 0, 1920, 1080).Contains(R.Rect));
  TestTrue("centred under the owner (|dx| <= 4 px)", FMath::Abs(R.Rect.Center().X - Medusa.Center().X) <= 4.0);
  // Nameplate "above the head", slid down into the box only past the destination cells of row 1: the base and the
  // team ring (bottom quarter of the box) stay visible.
  TestTrue("the plate starts in the owner's upper half", R.Rect.Y0 < Medusa.Center().Y);
  TestTrue("the owner's base and team ring stay uncovered (bottom quarter of the box)",
           R.Rect.Y1 <= Medusa.Y1 - 0.25f * Medusa.Height());
  for (const FS08ScreenRect& O : Others) {
    TestTrue("no foreign figure touched", S08ArtHud::RectGap(R.Rect, O) > 0.0);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudTraceFormatTest,
    "Unmatched.S08.ArtHud.Trace SHOT reachable/plate/icon lines match the qa010 parser format",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudTraceFormatTest::RunTest(const FString&) {
  TestEqual("cells", S08ArtHud::FormatCells({FIntPoint(1, 0), FIntPoint(2, 0), FIntPoint(0, 1)}),
            FString(TEXT("(1,0)(2,0)(0,1)")));
  TestEqual("bbox rounding", S08ArtHud::FormatRect(FS08ScreenRect(880.4f, 399.6f, 1040.2f, 470.3f)),
            FString(TEXT("(880,400,1040,470)")));
  TestEqual("negative bbox", S08ArtHud::FormatRect(FS08ScreenRect(-3.2f, 0, 10, 10)), FString(TEXT("(-3,0,10,10)")));
  TSet<uint64> Legal;
  for (const FIntPoint& C : {FIntPoint(2, 2), FIntPoint(3, 1), FIntPoint(1, 0), FIntPoint(0, 1)}) {
    Legal.Add(FS08BoardModel::CellKey(C.X, C.Y));
  }
  const TArray<FIntPoint> Dest = S08ArtHud::DestinationCells(Legal, FIntPoint(2, 2));
  TestEqual("own cell excluded, row-major order", S08ArtHud::FormatCells(Dest), FString(TEXT("(1,0)(0,1)(3,1)")));

  // The exact regexes of tools/art/qa010/qa010lib/trace.py.
  const FString Reach = FString::Printf(TEXT("SHOT reachable fighter=f-0-hero n=%d cells=%s"), Dest.Num(),
                                        *S08ArtHud::FormatCells(Dest));
  FRegexMatcher ReachM(FRegexPattern(TEXT("^(?:SHOT reachable|REACHABLE) fighter=(\\S+) n=(\\d+) cells=(.*)$")), Reach);
  TestTrue("reachable line parses", ReachM.FindNext() && ReachM.GetCaptureGroup(2) == TEXT("3"));
  const FString Plate = FString::Printf(TEXT("SHOT plate fighter=f-0-hero bbox=%s overlapReachable=0 placement=below"),
                                        *S08ArtHud::FormatRect(FS08ScreenRect(880, 400, 1040, 470)));
  FRegexMatcher PlateM(FRegexPattern(TEXT("^(?:SHOT plate|PLATE) fighter=(\\S+) bbox=\\((-?\\d+(?:\\.\\d+)?),(-?\\d+(?:\\.\\d+)?),(-?\\d+(?:\\.\\d+)?),(-?\\d+(?:\\.\\d+)?)\\)(?: overlapReachable=(\\d+))?")), Plate);
  TestTrue("plate line parses with overlapReachable", PlateM.FindNext() && PlateM.GetCaptureGroup(6) == TEXT("0"));
  const FString Standalone = TEXT("PLATE fighter=f-0-hero bbox=(880,400,1040,470) overlapReachable=1 placement=left");
  FRegexMatcher StandaloneM(FRegexPattern(TEXT("^(?:SHOT plate|PLATE) fighter=(\\S+) bbox=\\((-?\\d+),(-?\\d+),(-?\\d+),(-?\\d+)\\)(?: overlapReachable=(\\d+))?")), Standalone);
  TestTrue("standalone PLATE parses", StandaloneM.FindNext() && StandaloneM.GetCaptureGroup(6) == TEXT("1"));
  const FString Icon = TEXT("SHOT icon fighter=f-1-hero bbox=(948,700,972,724) size=24 src=flag");
  FRegexMatcher IconM(FRegexPattern(TEXT("^(?:SHOT icon|ICON) fighter=(\\S+) bbox=\\((-?\\d+),(-?\\d+),(-?\\d+),(-?\\d+)\\)")), Icon);
  TestTrue("icon line parses", IconM.FindNext() && IconM.GetCaptureGroup(1) == TEXT("f-1-hero"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudFlagsTest,
    "Unmatched.S08.ArtHud.Flags input plan, icon size 24/32/48, all-Medusa eligibility, plate statuses",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudFlagsTest::RunTest(const FString&) {
  TArray<ES08InputStep> Steps;
  FString Error;
  TestTrue("plan parses", S08ParseInputPlan(TEXT("clickhero+clickabove+clickcell+wheelout*3+space+wheelin*9"), Steps, Error));
  TestEqual("16 steps", Steps.Num(), 16);
  TestTrue("order kept", Steps.Num() == 16 && Steps[0] == ES08InputStep::ClickHero &&
                             Steps[3] == ES08InputStep::WheelOut && Steps[6] == ES08InputStep::Space &&
                             Steps[15] == ES08InputStep::WheelIn);
  TestFalse("unknown token refused", S08ParseInputPlan(TEXT("wheelin+jump"), Steps, Error));
  TestTrue("error names the token", Error.Contains(TEXT("jump")) && Steps.Num() == 0);
  TestFalse("repeat > 20 refused", S08ParseInputPlan(TEXT("wheelin*21"), Steps, Error));
  TestFalse("empty refused", S08ParseInputPlan(TEXT(""), Steps, Error));
  TestFalse("> 40 steps refused", S08ParseInputPlan(TEXT("wheelin*20+wheelout*20+space"), Steps, Error));

  TestEqual("24", S08ParseIconSize(TEXT("24"), 32), 24);
  TestEqual("48", S08ParseIconSize(TEXT(" 48 "), 32), 48);
  TestEqual("empty = default", S08ParseIconSize(TEXT(""), 32), 32);
  TestEqual("40 invalid", S08ParseIconSize(TEXT("40"), 32), 0);
  TestEqual("text invalid", S08ParseIconSize(TEXT("big"), 32), 0);

  TestTrue("Medusa hero", S08IsMedusaCandidateFighter(true, false, true, TEXT("Medusa")));
  TestFalse("Harpy without the flag", S08IsMedusaCandidateFighter(true, false, false, TEXT("Harpies")));
  TestFalse("Arthur without the flag", S08IsMedusaCandidateFighter(true, false, true, TEXT("King Arthur")));
  TestTrue("Harpy with -ArtPreviewAllMedusa", S08IsMedusaCandidateFighter(true, true, false, TEXT("Harpies")));
  TestTrue("Arthur with -ArtPreviewAllMedusa", S08IsMedusaCandidateFighter(true, true, true, TEXT("King Arthur")));
  TestFalse("never outside -ArtPreview", S08IsMedusaCandidateFighter(false, true, true, TEXT("Medusa")));

  const TArray<FString> Statuses = S08PlateStatuses(true, true, TEXT("melee"), true, false, {TEXT("stunned"), TEXT(" ")});
  TestEqual("statuses", FString::Join(Statuses, TEXT("|")), FString(TEXT("HERO|MELEE|ATTACKER|STUNNED")));
  TestEqual("sidekick target", FString::Join(S08PlateStatuses(false, false, TEXT("ranged"), false, true, {}), TEXT("|")),
            FString(TEXT("SIDEKICK|RANGED|TARGET")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudDamageDedupeTest,
    "Unmatched.S08.ArtHud.Damage numbers are accepted once per (fighter, seq)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudDamageDedupeTest::RunTest(const FString&) {
  FS08SeqDedupe Dedupe;
  TestTrue("first cue", Dedupe.Accept(TEXT("f-1-hero"), 5));
  TestFalse("same seq again (reapply / reconnect replay)", Dedupe.Accept(TEXT("f-1-hero"), 5));
  TestTrue("next seq", Dedupe.Accept(TEXT("f-1-hero"), 6));
  TestTrue("other fighter, same seq", Dedupe.Accept(TEXT("f-0-sk1"), 5));
  TestEqual("three keys", Dedupe.Seen.Num(), 3);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtHudCapsuleTest,
    "Unmatched.S08.ArtHud.Capsule the live Medusa candidate is clickable on the sculpt, not above it",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtHudCapsuleTest::RunTest(const FString&) {
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08ArtHudCapsuleWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  FS08BoardFighter Medusa;
  Medusa.Id = TEXT("f-0-hero");
  Medusa.OwnerId = TEXT("owner");
  Medusa.Name = TEXT("Medusa");
  Medusa.Label = TEXT("Medusa");
  Medusa.bIsHero = true;
  Medusa.Health = 16;
  Medusa.MaxHealth = 16;
  Medusa.X = 2;
  Medusa.Y = 2;
  const FVector Cell(0.0, -50.0, 0.0);
  AS08FighterActor* Actor = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), Cell, FRotator::ZeroRotator);
  if (!Actor) {
    AddError(TEXT("fighter actor not spawned"));
  } else {
    Actor->ApplyFighter(Medusa, Cell, true, /*bArtPreview=*/true);
    TestTrue("candidate sculpt visible (art worktree /Game/ArtPreview/Medusa)", Actor->HasMedusaCandidate());
    const UCapsuleComponent* Capsule = Actor->FindComponentByClass<UCapsuleComponent>();
    TestNotNull("click capsule exists", Capsule);
    if (Capsule && Actor->HasMedusaCandidate()) {
      TestEqual("capsule is query-only", static_cast<int32>(Capsule->GetCollisionEnabled()),
                static_cast<int32>(ECollisionEnabled::QueryOnly));
      TestEqual("capsule blocks the click channel", static_cast<int32>(Capsule->GetCollisionResponseToChannel(ECC_Visibility)),
                static_cast<int32>(ECR_Block));
      const float Top = Actor->GetFigureHeightUU();
      TestTrue("figure height is the sculpt (40..80 uu), not the 120 uu grey box", Top > 40.0f && Top < 80.0f);
      // Component-level traces (no scene-query update needed in a non-ticking
      // test world): the capsule answers a camera-like ray through the
      // sculpt's middle and not one 35 uu above the head; the hidden grey
      // Body box no longer blocks at all.
      const FVector Dir = FRotator(-55.0, -90.0, 0.0).Vector();
      const FVector Mid = Cell + FVector(0, 0, Top * 0.5f);
      const FVector Above = Cell + FVector(0, 0, Top + 35.0f);
      FHitResult Hit;
      FCollisionQueryParams Params(TEXT("S08ArtHudCapsuleTest"), false);
      UCapsuleComponent* MutableCapsule = const_cast<UCapsuleComponent*>(Capsule);
      TestTrue("ray through the sculpt hits the capsule",
               MutableCapsule->LineTraceComponent(Hit, Mid - Dir * 500.0, Mid + Dir * 500.0, Params));
      TestFalse("ray 35 uu above the head misses the capsule",
                MutableCapsule->LineTraceComponent(Hit, Above - Dir * 500.0, Above + Dir * 500.0, Params));
      bool bBodyFound = false;
      TInlineComponentArray<UPrimitiveComponent*> Prims(Actor);
      for (const UPrimitiveComponent* Prim : Prims) {
        if (Prim->GetFName() == TEXT("Body")) {
          bBodyFound = true;
          TestEqual("hidden grey Body box does not collide", static_cast<int32>(Prim->GetCollisionEnabled()),
                    static_cast<int32>(ECollisionEnabled::NoCollision));
        }
      }
      TestTrue("grey Body component found", bBodyFound);
    }
    Actor->Destroy();
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
