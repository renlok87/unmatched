// Art Tuner M1 automation tests (S08ArtView.h, docs/art-pipeline/ART-TUNER-PLAN.md §6):
//   OffByDefault no -ArtView in this process: disabled; an explicit command line enables it and names the map;
//   Fixtures     map -> Config/Bench fixture file (the three shipped ones exist), unknown maps refused;
//   Camera       the default pose IS the game camera (pitch 55, yaw -90), orbit clamps the pitch and wraps the yaw, the
//                pan follows the cursor and stays bounded, Reset goes back to the game camera;
//   Fighters     Tab order: living fighters only, wraps both ways, starts at the first / last without a selection;
//   Views        the keys 1..5 are the -Bench views.
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.ArtView; Quit" -unattended -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08ArtView.h"
#include "S08BoardModel.h"
#include "Misc/AutomationTest.h"
#include "Misc/Paths.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtViewOffByDefaultTest,
    "Unmatched.S08.ArtView.OffByDefault without -ArtView: disabled; the flag names the map",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtViewOffByDefaultTest::RunTest(const FString&) {
  TestFalse("no -ArtView in this process", S08ArtView::Enabled());
  TestTrue("no map", S08ArtView::MapFromCommandLine().IsEmpty());
  TestFalse("an empty command line", S08ArtView::Enabled(TEXT("")));
  TestFalse("-ArtViewer is not -ArtView=", S08ArtView::Enabled(TEXT("-ArtViewer")));
  TestTrue("-ArtView=Sarpedon", S08ArtView::Enabled(TEXT("-windowed -ArtView=Sarpedon -ArtTuner")));
  TestEqual("lower-case map", S08ArtView::MapFromCommandLine(TEXT("-ArtView=Sarpedon")), FString(TEXT("sarpedon")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtViewFixturesTest,
    "Unmatched.S08.ArtView.Fixtures map names -> the -Bench fixtures of Config/Bench",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtViewFixturesTest::RunTest(const FString&) {
  for (const FString& Map : S08ArtView::Maps()) {
    FString File;
    if (!TestTrue(FString::Printf(TEXT("%s has a fixture"), *Map), S08ArtView::FixtureFileFor(Map, File))) continue;
    TestTrue(FString::Printf(TEXT("%s exists"), *File),
             FPaths::FileExists(FPaths::Combine(FPaths::ProjectConfigDir(), TEXT("Bench"), File)));
  }
  FString File;
  TestTrue("sarpedon", S08ArtView::FixtureFileFor(TEXT("sarpedon"), File) && File == TEXT("S08BenchSarpedon.json"));
  TestTrue("cobble", S08ArtView::FixtureFileFor(TEXT("cobble"), File) && File == TEXT("S08BenchCobble.json"));
  TestFalse("unknown map", S08ArtView::FixtureFileFor(TEXT("sherwood"), File));
  TestTrue("any case -> the shipped file name",
           S08ArtView::FixtureFileFor(TEXT("SARPEDON"), File) && File == TEXT("S08BenchSarpedon.json"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtViewCameraTest,
    "Unmatched.S08.ArtView.Camera default = the game camera; orbit / pan bounds; reset",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtViewCameraTest::RunTest(const FString&) {
  FS08ArtViewCamera Cam;
  TestTrue("default", Cam.IsDefault());
  const FVector Focus(12.0, -30.0, 28.0);
  const float D = 2340.195f;
  FVector Loc;
  FRotator Rot;
  Cam.Pose(Focus, D, Loc, Rot);
  // AS08FlowGameMode::UpdateBoardCamera: CurrentFocus + (0, D cos 55, D sin 55), FRotator(-55, -90, 0)
  const float Pitch = FMath::DegreesToRadians(55.0f);
  const FVector Game = Focus + FVector(0.0f, D * FMath::Cos(Pitch), D * FMath::Sin(Pitch));
  TestTrue(FString::Printf(TEXT("location %s == game %s"), *Loc.ToString(), *Game.ToString()), Loc.Equals(Game, 0.01));
  TestTrue("rotation", Rot.Equals(FRotator(-55.0f, -90.0f, 0.0f), 0.001f));
  // the camera looks at the focus
  TestTrue("looks at the focus", Rot.Vector().Equals((Focus - Loc).GetSafeNormal(), 1e-4));

  Cam.Orbit(FVector2D(40.0, 0.0));
  TestEqual("yaw +10", Cam.YawDeg, -80.0f, 0.001f);
  TestFalse("not default", Cam.IsDefault());
  Cam.Orbit(FVector2D(0.0, 10000.0));
  TestEqual("pitch clamped high", Cam.PitchDeg, S08ArtViewSpec::MaxPitchDeg);
  Cam.Orbit(FVector2D(0.0, -10000.0));
  TestEqual("pitch clamped low", Cam.PitchDeg, S08ArtViewSpec::MinPitchDeg);
  Cam.Orbit(FVector2D(4000.0, 0.0));  // +1000 deg
  TestTrue("yaw wrapped", Cam.YawDeg >= -180.0f && Cam.YawDeg <= 180.0f);
  Cam.Pose(Focus, D, Loc, Rot);
  TestTrue("orbited still looks at the focus", Rot.Vector().Equals((Focus - Loc).GetSafeNormal(), 1e-4));
  TestEqual("orbit keeps the distance", static_cast<float>(FVector::Dist(Loc, Focus)), D, 0.05f);

  Cam.Reset();
  TestTrue("reset", Cam.IsDefault());
  // default yaw -90: screen right = world +X, ground forward = world -Y; dragging right moves the board right with the
  // cursor, so the focus goes to -X (grab)
  Cam.Pan(FVector2D(100.0, 0.0), D, 1920.0f);
  TestTrue(FString::Printf(TEXT("drag right -> focus -X (%s)"), *Cam.PanUU.ToString()), Cam.PanUU.X < 0.0 && FMath::Abs(Cam.PanUU.Y) < 1e-3);
  const double UuPerPx = 2.0 * D * FMath::Tan(FMath::DegreesToRadians(17.5)) / 1920.0;
  TestEqual("pan scale = visible width per px", Cam.PanUU.X, -100.0 * UuPerPx, 0.01);
  Cam.Pose(Focus, D, Loc, Rot);
  TestTrue("screen right of the default camera = +X", FRotationMatrix(Rot).GetScaledAxis(EAxis::Y).Equals(FVector(1.0, 0.0, 0.0), 1e-4));
  Cam.Reset();
  Cam.Pan(FVector2D(0.0, 50.0), D, 1920.0f);
  TestTrue(FString::Printf(TEXT("drag down -> focus -Y, the far side (%s)"), *Cam.PanUU.ToString()), Cam.PanUU.Y < 0.0);
  Cam.Pan(FVector2D(1.0e6, 1.0e6), D, 1920.0f);
  TestTrue("pan bounded", Cam.PanUU.Size() <= S08ArtViewSpec::MaxPanUU + 0.01);
  Cam.Pose(Focus, D, Loc, Rot);
  const FVector Target = Focus + FVector(Cam.PanUU.X, Cam.PanUU.Y, 0.0);
  TestTrue("panned looks at focus + pan", Rot.Vector().Equals((Target - Loc).GetSafeNormal(), 1e-4));
  const FVector2D Before = Cam.PanUU;
  Cam.Pan(FVector2D(10.0, 0.0), D, 0.0f);
  TestTrue("no viewport: no pan", Cam.PanUU == Before);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtViewFightersTest,
    "Unmatched.S08.ArtView.Fighters Tab order: living fighters, wraps both ways",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtViewFightersTest::RunTest(const FString&) {
  TArray<FS08BoardFighter> F;
  for (int32 I = 0; I < 4; ++I) {
    FS08BoardFighter& A = F.AddDefaulted_GetRef();
    A.Id = FString::Printf(TEXT("f%d"), I);
    A.Health = 5;
    A.X = I;
    A.Y = 0;
  }
  F[2].Health = 0;  // dead: skipped
  TestEqual("none selected -> first", S08ArtView::NextFighterIndex(F, FString(), 1), 0);
  TestEqual("none selected, back -> last", S08ArtView::NextFighterIndex(F, FString(), -1), 3);
  TestEqual("f1 -> f3 (f2 dead)", S08ArtView::NextFighterIndex(F, TEXT("f1"), 1), 3);
  TestEqual("f3 -> wraps to f0", S08ArtView::NextFighterIndex(F, TEXT("f3"), 1), 0);
  TestEqual("f0 back -> f3", S08ArtView::NextFighterIndex(F, TEXT("f0"), -1), 3);
  TestEqual("f3 back -> f1", S08ArtView::NextFighterIndex(F, TEXT("f3"), -1), 1);
  TestEqual("unknown -> first", S08ArtView::NextFighterIndex(F, TEXT("zz"), 1), 0);
  for (FS08BoardFighter& A : F) A.Health = 0;
  TestEqual("all dead", S08ArtView::NextFighterIndex(F, TEXT("f0"), 1), INDEX_NONE);
  TestEqual("empty", S08ArtView::NextFighterIndex(TArray<FS08BoardFighter>(), FString(), 1), INDEX_NONE);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtViewViewsTest,
    "Unmatched.S08.ArtView.Views keys 1..5 = K1 / K1x0.65 / K2x1.6 / K2x2.5 / Fitx1.45; help names every key",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtViewViewsTest::RunTest(const FString&) {
  const TArray<FString> Want = {TEXT("K1"), TEXT("K1x0.65"), TEXT("K2x1.6"), TEXT("K2x2.5"), TEXT("Fitx1.45")};
  TestTrue("views", S08ArtView::Views() == Want);
  const FString Help = S08ArtView::HelpText(true);
  for (const TCHAR* Key : {TEXT("Tab"), TEXT("H —"), TEXT("P —"), TEXT("F1"), TEXT("F10"), TEXT("Ctrl+S"), TEXT("1–5")}) {
    TestTrue(FString::Printf(TEXT("help names %s"), Key), Help.Contains(Key));
  }
  TestFalse("no tuner keys without -ArtTuner", S08ArtView::HelpText(false).Contains(TEXT("F10")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
