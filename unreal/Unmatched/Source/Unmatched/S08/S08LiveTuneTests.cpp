// ENV-MAPS live tune automation tests (S08LiveTune.h, tools/art/render/LIVE-TUNE.md):
//   Command      cmd-<seq>.json parsing: reload / shot / state / quit, the defaults, every refused field;
//   Files        the -Bench capture names, cmd / done file names and order, the atomic write, the done.json fields;
//   OffByDefault no -ArtLiveTune in this process: disabled, no trace journal, no tee;
//   Clock        the -Bench timeline arithmetic of the anim / world clocks;
//   Reload       AS08BoardActor::ReloadArtData: a valid document is swapped in and forces ONE full Rebuild (the normal
//                build path, fighters spawned again), an invalid profile document / env layout keeps the applied state and
//                forces nothing.
//   UnrealEditor-Cmd.exe Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.LiveTune; Quit" -unattended -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08FighterActor.h"
#include "S08LiveTune.h"
#include "S08TraceLog.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace S08LiveTuneTest {

FString TestDir(const TCHAR* Leaf) {
  return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("S08LiveTuneTest"), Leaf));
}

/** A minimal valid board-profile document (revision Rev, directional key intensity Key). */
FString Doc(int32 Rev, float Key) {
  return FString::Printf(TEXT(
      "{\"schema\":\"unmatched.s08-art-board-profiles/1\",\"revision\":%d,"
      "\"zoneStyles\":{\"a\":{\"stroke\":\"solid\",\"glyph\":\"diamond\",\"color\":\"#102030\"},"
      "\"b\":{\"stroke\":\"dash2\",\"glyph\":\"ring\",\"color\":\"#A0B0C0\"}},"
      "\"fallbackZoneStyle\":{\"stroke\":\"dots5\",\"glyph\":\"bar1\",\"color\":\"#FFFFFF\"},"
      "\"lightProfiles\":{\"L\":{\"directional\":{\"name\":\"key\",\"posUU\":[0,0,600],\"rotation\":[-55,30,0],"
      "\"intensity\":%g,\"castShadows\":true},\"points\":[{\"name\":\"p\",\"at\":[0.5,-0.5,200],\"intensity\":50,"
      "\"radiusUU\":300}]}},"
      "\"boards\":[{\"id\":\"one\",\"match\":{\"boardIds\":[\"cid1\"],\"width\":3,\"height\":2,\"zoneKeys\":[\"b\",\"a\"]},"
      "\"surface\":\"tiles\",\"light\":\"L\",\"expect\":{\"cells\":6,\"zoneCells\":6,\"multizoneCells\":1,\"obstacles\":0,"
      "\"zoneCellCounts\":{\"a\":3,\"b\":4}}}]}"),
      Rev, Key);
}

FS08BoardModel Grid(int32 W, int32 H) {
  FS08BoardModel Board;
  Board.Width = W;
  Board.Height = H;
  Board.Cells.Init(FS08Cell(), W * H);
  for (int32 Y = 0; Y < H; ++Y) {
    for (int32 X = 0; X < W; ++X) {
      FS08Cell& Cell = Board.Cells[Y * W + X];
      Cell.X = X;
      Cell.Y = Y;
      Cell.Type = ES08CellType::Normal;
    }
  }
  return Board;
}

TArray<FS08BoardFighter> TwoFighters() {
  TArray<FS08BoardFighter> Out;
  for (int32 I = 0; I < 2; ++I) {
    FS08BoardFighter F;
    F.Id = FString::Printf(TEXT("f-%d"), I);
    F.OwnerId = I == 0 ? TEXT("host") : TEXT("guest");
    F.Name = TEXT("Medusa");
    F.Label = F.Name;
    F.bIsHero = true;
    F.Health = F.MaxHealth = 7;
    F.X = I;
    F.Y = 0;
    Out.Add(F);
  }
  return Out;
}

}  // namespace S08LiveTuneTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LiveTuneCommandTest,
    "Unmatched.S08.LiveTune.Command cmd json: reload / shot / state / quit, defaults, refused fields",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LiveTuneCommandTest::RunTest(const FString&) {
  FS08LiveCommand C;
  TArray<FString> E;
  // reload (no paths = the startup sources)
  TestTrue("reload parses", FS08LiveCommand::Parse(TEXT("{\"seq\":3,\"action\":\"reload\"}"), 3, C, E));
  TestTrue("reload action", C.Action == ES08LiveAction::Reload && C.Seq == 3 && C.ProfilesPath.IsEmpty() && C.EnvDir.IsEmpty());
  E.Reset();
  TestTrue("reload with paths", FS08LiveCommand::Parse(
      TEXT("{\"action\":\"reload\",\"profiles\":\"C:/w/Config/ArtBoards/S08ArtBoardProfiles.json\",\"envDir\":\"C:\\\\w\\\\Env\\\\\"}"),
      4, C, E));
  TestEqual("reload profiles path", C.ProfilesPath, FString(TEXT("C:/w/Config/ArtBoards/S08ArtBoardProfiles.json")));
  TestEqual("reload env dir normalised", C.EnvDir, FString(TEXT("C:/w/Env")));
  E.Reset();
  TestFalse("relative profiles refused", FS08LiveCommand::Parse(TEXT("{\"action\":\"reload\",\"profiles\":\"rel.json\"}"), 1, C, E));
  // shot: defaults and fields
  E.Reset();
  TestTrue("shot parses", FS08LiveCommand::Parse(
      TEXT("{\"seq\":7,\"action\":\"shot\",\"views\":\"K1+K2x1.6+K2x2.5\",\"out\":\"C:/tmp/lt/a\",\"tag\":\"base\"}"), 7, C, E));
  TestTrue("shot fields", C.Action == ES08LiveAction::Shot && C.Views.Num() == 3 && C.Views[1] == TEXT("K2x1.6") &&
                              C.OutDir == TEXT("C:/tmp/lt/a") && C.Tag == TEXT("base"));
  TestTrue("shot defaults (session fills them): settle / measure / post / warmup unset, bench clock, frozen fx",
           C.Settle < 0.0f && C.Measure < 0.0f && C.Post < 0.0f && C.Warmup < 0.0f && C.bBenchClock && !C.bLive &&
               !C.bAppendTrace && C.BenchWarmup < 0.0f && C.bFresh);
  E.Reset();
  TestTrue("shot with every option", FS08LiveCommand::Parse(
      TEXT("{\"action\":\"shot\",\"views\":\"Fitx1.45\",\"out\":\"C:/o\",\"settle\":4,\"measure\":5,\"post\":3,\"warmup\":2,"
           "\"warmupFrames\":10,\"settleFrames\":120,\"clock\":\"free\",\"append\":true,\"fresh\":false,"
           "\"bench\":{\"warmup\":30,\"settle\":6,\"measure\":3,\"gap\":0.5,\"gapLater\":-1}}"),
      1, C, E));
  TestTrue("options read", C.Settle == 4.0f && C.Measure == 5.0f && C.Post == 3.0f && C.Warmup == 2.0f &&
                               C.WarmupFrames == 10 && C.SettleFrames == 120 && !C.bBenchClock && C.bAppendTrace && !C.bFresh &&
                               C.BenchWarmup == 30.0f && C.BenchSettle == 6.0f && C.BenchMeasure == 3.0f &&
                               C.BenchGap == 0.5f && C.BenchGapLater == -1.0f);
  E.Reset();
  TestTrue("live:true turns the bench clock off",
           FS08LiveCommand::Parse(TEXT("{\"action\":\"shot\",\"views\":\"K1\",\"out\":\"C:/o\",\"live\":true}"), 1, C, E) &&
               C.bLive && !C.bBenchClock);
  // state / quit
  E.Reset();
  TestTrue("state", FS08LiveCommand::Parse(TEXT("{\"action\":\"state\"}"), 2, C, E) && C.Action == ES08LiveAction::State);
  E.Reset();
  TestTrue("quit", FS08LiveCommand::Parse(TEXT("{\"action\":\"quit\"}"), 2, C, E) && C.Action == ES08LiveAction::Quit);
  // refused
  struct FBad {
    const TCHAR* Json;
    const TCHAR* Why;
  };
  const FBad Bad[] = {
      {TEXT("{\"action\":"), TEXT("invalid JSON")},
      {TEXT("[1,2]"), TEXT("not an object")},
      {TEXT("{\"seq\":2}"), TEXT("no action")},
      {TEXT("{\"action\":\"explode\"}"), TEXT("unknown action")},
      {TEXT("{\"seq\":9,\"action\":\"state\"}"), TEXT("seq != file seq")},
      {TEXT("{\"action\":\"shot\",\"out\":\"C:/o\"}"), TEXT("shot without views")},
      {TEXT("{\"action\":\"shot\",\"views\":\"K1\"}"), TEXT("shot without out")},
      {TEXT("{\"action\":\"shot\",\"views\":\"K1\",\"out\":\"rel/dir\"}"), TEXT("relative out")},
      {TEXT("{\"action\":\"shot\",\"views\":\"\",\"out\":\"C:/o\"}"), TEXT("empty views")},
      {TEXT("{\"action\":\"shot\",\"views\":\"K1+../x\",\"out\":\"C:/o\"}"), TEXT("bad view name")},
      {TEXT("{\"action\":\"shot\",\"views\":\"Top\",\"out\":\"C:/o\"}"), TEXT("not a bench view")},
      {TEXT("{\"action\":\"shot\",\"views\":\"K1\",\"out\":\"C:/o\",\"settle\":-1}"), TEXT("negative settle")},
      {TEXT("{\"action\":\"shot\",\"views\":\"K1\",\"out\":\"C:/o\",\"settle\":\"6\"}"), TEXT("string settle")},
      {TEXT("{\"action\":\"shot\",\"views\":\"K1\",\"out\":\"C:/o\",\"live\":\"yes\"}"), TEXT("string bool")},
      {TEXT("{\"action\":\"shot\",\"views\":\"K1\",\"out\":\"C:/o\",\"clock\":\"wall\"}"), TEXT("unknown clock")},
      {TEXT("{\"action\":\"shot\",\"views\":\"K1\",\"out\":\"C:/o\",\"settleFrames\":2.5}"), TEXT("fractional frames")},
      {TEXT("{\"action\":\"shot\",\"views\":\"K1\",\"out\":\"C:/o\",\"bench\":3}"), TEXT("bench not an object")},
  };
  for (const FBad& B : Bad) {
    TArray<FString> Errors;
    const bool bOk = FS08LiveCommand::Parse(B.Json, 2, C, Errors);
    TestTrue(FString::Printf(TEXT("refused: %s (%s)"), B.Why, *FString::Join(Errors, TEXT("; "))), !bOk && Errors.Num() > 0);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LiveTuneFilesTest,
    "Unmatched.S08.LiveTune.Files bench capture names, cmd / done files, atomic write, done.json fields",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LiveTuneFilesTest::RunTest(const FString&) {
  using namespace S08LiveTuneTest;
  // the same names RunRenderBench writes (gates.py / vsref.py / hero_light_metrics.py glob them)
  TestEqual("K1", S08LiveTune::ShotFileName(TEXT("K1")), FString(TEXT("bench-K1-1920x1080.png")));
  TestEqual("K2x1.6", S08LiveTune::ShotFileName(TEXT("K2x1.6")), FString(TEXT("bench-K2x1p6-1920x1080.png")));
  TestEqual("K2x2.5", S08LiveTune::ShotFileName(TEXT("K2x2.5")), FString(TEXT("bench-K2x2p5-1920x1080.png")));
  TestEqual("K1x0.65", S08LiveTune::ShotFileName(TEXT("K1x0.65")), FString(TEXT("bench-K1x0p65-1920x1080.png")));
  TestEqual("Fitx1.45", S08LiveTune::ShotFileName(TEXT("Fitx1.45")), FString(TEXT("bench-Fitx1p45-1920x1080.png")));
  TestEqual("seq of cmd-12.json", S08LiveTune::SeqOfFileName(TEXT("C:/x/cmd-12.json"), TEXT("cmd-")), 12);
  TestEqual("cmd-12.json.tmp is no command", S08LiveTune::SeqOfFileName(TEXT("cmd-12.json.tmp"), TEXT("cmd-")), INDEX_NONE);
  TestEqual("cmd-x.json is no command", S08LiveTune::SeqOfFileName(TEXT("cmd-x.json"), TEXT("cmd-")), INDEX_NONE);
  TestEqual("done-3.json is no command", S08LiveTune::SeqOfFileName(TEXT("done-3.json"), TEXT("cmd-")), INDEX_NONE);
  const FString Dir = TestDir(TEXT("files"));
  IFileManager::Get().DeleteDirectory(*Dir, false, true);
  IFileManager::Get().MakeDirectory(*Dir, true);
  int32 Seq = 0;
  FString Path;
  TestFalse("empty folder: no command", S08LiveTune::NextCommand(Dir, 0, Seq, Path));
  for (const int32 N : {3, 1, 2}) {
    TestTrue(FString::Printf(TEXT("atomic write cmd-%d"), N),
             S08LiveTune::WriteFileAtomic(S08LiveTune::CommandFile(Dir, N), TEXT("{\"action\":\"state\"}")));
  }
  TestFalse("no .tmp left behind", FPaths::FileExists(S08LiveTune::CommandFile(Dir, 1) + TEXT(".tmp")));
  TestTrue("lowest pending first", S08LiveTune::NextCommand(Dir, 0, Seq, Path) && Seq == 1 &&
                                       Path == S08LiveTune::CommandFile(Dir, 1));
  TestTrue("then the next", S08LiveTune::NextCommand(Dir, 1, Seq, Path) && Seq == 2);
  TestFalse("all done", S08LiveTune::NextCommand(Dir, 3, Seq, Path));
  // done.json
  FS08LiveResult R;
  R.Seq = 5;
  R.Action = TEXT("shot");
  R.bOk = true;
  R.Ms = 1234.56;
  R.Files = {TEXT("C:/o/bench-K1-1920x1080.png"), TEXT("C:/o/bench.trace.log")};
  R.Warnings = {TEXT("w")};
  R.Extra = MakeShared<FJsonObject>();
  R.Extra->SetStringField(TEXT("tag"), TEXT("base"));
  R.Extra->SetStringField(TEXT("seq"), TEXT("must not override"));
  TSharedPtr<FJsonObject> Done;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(R.ToJson());
  if (TestTrue("done.json parses", FJsonSerializer::Deserialize(Reader, Done) && Done.IsValid())) {
    TestEqual("seq", static_cast<int32>(Done->GetNumberField(TEXT("seq"))), 5);
    TestEqual("action", Done->GetStringField(TEXT("action")), FString(TEXT("shot")));
    TestTrue("ok", Done->GetBoolField(TEXT("ok")));
    TestTrue("ms", FMath::IsNearlyEqual(Done->GetNumberField(TEXT("ms")), 1234.6, 0.01));
    TestEqual("errors[]", Done->GetArrayField(TEXT("errors")).Num(), 0);
    TestEqual("files[]", Done->GetArrayField(TEXT("files")).Num(), 2);
    TestEqual("warnings[]", Done->GetArrayField(TEXT("warnings")).Num(), 1);
    TestEqual("extra field", Done->GetStringField(TEXT("tag")), FString(TEXT("base")));
  }
  IFileManager::Get().DeleteDirectory(*Dir, false, true);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LiveTuneOffByDefaultTest,
    "Unmatched.S08.LiveTune.OffByDefault without -ArtLiveTune: disabled, no journal, no tee, fx from the command line",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LiveTuneOffByDefaultTest::RunTest(const FString&) {
  TestTrue("no -ArtLiveTune in this process", S08LiveTune::DirFromCommandLine().IsEmpty() && !S08LiveTune::Enabled());
  TestFalse("the trace journal is off", FS08Trace::IsJournalOn());
  TestEqual("the journal is empty", FS08Trace::JournalNum(), 0);
  // a board actor without a reload: the fx options are the command line's (no override), the next Rebuild is not forced
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08LiveTuneOff")));
  if (!TestNotNull("test world", World)) return false;
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  if (AS08BoardActor* Board = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator)) {
    const FS08EnvFxOptions Cmd = FS08EnvFxOptions::FromCommandLine();
    TestEqual("fx mode = the command line's", Board->GetFxOptions().Mode(), Cmd.Mode());
    const FS08BoardModel Model = S08LiveTuneTest::Grid(3, 2);
    TestTrue("first rebuild", Board->Rebuild(Model));
    TestTrue("same geometry again", Board->Rebuild(Model));
    TestEqual("one full build (the same geometry is kept)", Board->GetBuildCount(), 1);
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LiveTuneClockTest,
    "Unmatched.S08.LiveTune.Clock the -Bench timeline of the anim and world clocks",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LiveTuneClockTest::RunTest(const FString&) {
  FS08LiveBenchClock C;
  C.BenchWarmup = 60.0f;
  C.BenchSettle = 6.0f;
  C.BenchMeasure = 5.0f;
  C.FrameSeconds = 1.0f / 60.0f;
  const float F = C.FrameSeconds;
  // RunRenderBench: init tick -> warmup (60 s) -> warmup done -> view setup -> settled = 60 s + 2.5 frames
  TestTrue("first anchor", FMath::IsNearlyEqual(C.FirstAnchor(), 60.0f + 2.5f * F, 1e-4f));
  // settled -> settle 6 -> measure 5 -> post 3 -> capture
  TestTrue("bench anchor -> shot", FMath::IsNearlyEqual(C.BenchAnchorToShot(), 14.0f + 1.5f * F, 1e-4f));
  TestTrue("live settle only", FMath::IsNearlyEqual(C.LiveAnchorToShot(6.0f, 0.0f, 0.0f), 6.0f + 0.5f * F, 1e-4f));
  TestTrue("live settle + measure + post = the bench's",
           FMath::IsNearlyEqual(C.LiveAnchorToShot(6.0f, 5.0f, 3.0f), C.BenchAnchorToShot(), 1e-4f));
  // view 0: the live capture lands on the bench capture's clock
  const float Live = C.LiveAnchorToShot(6.0f, 0.0f, 0.0f);
  const float A0 = C.AnchorClock(0, 0.0f, 123.0f, Live);
  TestTrue("view 0: anchor + live wait = bench capture", FMath::IsNearlyEqual(A0 + Live, C.FirstAnchor() + C.BenchAnchorToShot(), 1e-4f));
  // view 1 / 2: the modelled bench gaps (the first capture of a fresh run stalls longer), or the live gap with -1
  const float Shot0 = A0 + Live;
  TestTrue("default gaps 0.57 / 0.41", FMath::IsNearlyEqual(C.GapBefore(1), 0.57f) && FMath::IsNearlyEqual(C.GapBefore(2), 0.41f) &&
                                           FMath::IsNearlyEqual(C.GapBefore(3), 0.41f));
  const float A1 = C.AnchorClock(1, Shot0, 9.0f, Live);
  TestTrue("view 1: previous capture + modelled gap + bench wait",
           FMath::IsNearlyEqual(A1 + Live, Shot0 + 0.57f + C.BenchAnchorToShot(), 1e-4f));
  const float A2 = C.AnchorClock(2, A1 + Live, 9.0f, Live);
  TestTrue("view 2: the later gap", FMath::IsNearlyEqual(A2 + Live, A1 + Live + 0.41f + C.BenchAnchorToShot(), 1e-4f));
  C.BenchGap = -1.0f;
  C.BenchGapLater = -1.0f;
  const float Gap = 0.25f;
  const float L1 = C.AnchorClock(1, Shot0, Gap, Live);
  TestTrue("gap -1: the live gap", FMath::IsNearlyEqual(L1 + Live, Shot0 + Gap + C.BenchAnchorToShot(), 1e-4f));
  TestTrue("wrap inside", FMath::IsNearlyEqual(FS08LiveBenchClock::WrapClip(5.5f, 2.0f), 1.5f, 1e-5f));
  TestTrue("wrap negative", FMath::IsNearlyEqual(FS08LiveBenchClock::WrapClip(-0.5f, 2.0f), 1.5f, 1e-5f));
  TestEqual("wrap zero length", FS08LiveBenchClock::WrapClip(3.0f, 0.0f), 0.0f);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08LiveTuneReloadTest,
    "Unmatched.S08.LiveTune.Reload valid document -> one forced normal Rebuild; invalid profiles / env layout keep the state",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08LiveTuneReloadTest::RunTest(const FString&) {
  using namespace S08LiveTuneTest;
  const FString Dir = TestDir(TEXT("reload"));
  const FString EnvDir = Dir / TEXT("env");
  const FString Profiles = Dir / TEXT("profiles.json");
  IFileManager::Get().DeleteDirectory(*Dir, false, true);
  IFileManager::Get().MakeDirectory(*EnvDir, true);
  FS08BoardArtData Start;
  TArray<FString> StartErrors;
  if (!TestTrue("start document parses", Start.ParseJson(Doc(19, 3.0f), StartErrors))) return false;

  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08LiveTuneReload")));
  if (!TestNotNull("test world", World)) return false;
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  AS08BoardActor* Board = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
  if (TestNotNull("board actor", Board)) {
    const FS08BoardModel Model = Grid(3, 2);
    Board->SetArtDataForTest(Start);
    Board->SetRoomBoardId(TEXT("cid1"));
    TestTrue("first build", Board->Rebuild(Model));
    Board->SyncFighters(Model, TwoFighters(), TEXT("host"));
    TestEqual("one build", Board->GetBuildCount(), 1);
    const AS08FighterActor* FirstActor = Board->FindFighterActor(TEXT("f-0"));
    TestNotNull("fighter spawned", FirstActor);

    // 1) a valid document: swapped in, the next Rebuild is a full one (the normal path), the fighters come back
    FFileHelper::SaveStringToFile(Doc(20, 4.5f), *Profiles);
    TArray<FString> Errors, Warnings;
    TestTrue("valid reload accepted", Board->ReloadArtData(Profiles, true, EnvDir, Errors, Warnings));
    TestTrue(FString::Printf(TEXT("no errors (%s)"), *FString::Join(Errors, TEXT("; "))), Errors.IsEmpty());
    TestEqual("revision swapped", Board->GetArtData().Revision, 20);
    TestEqual("fingerprint source = override", Board->GetAppliedRender().ProfilesSource, FString(TEXT("override")));
    TestEqual("fingerprint sha = the new bytes", Board->GetAppliedRender().ProfilesSha256, Board->GetArtData().SourceSha256);
    TestFalse("sha256 set", Board->GetArtData().SourceSha256.IsEmpty());
    const FS08LightProfile* L = Board->GetArtData().Lights.Find(TEXT("L"));
    TestTrue("the new key intensity is in the applied data", L && FMath::IsNearlyEqual(L->Directional.Intensity, 4.5f));
    TestEqual("no build yet (the caller rebuilds)", Board->GetBuildCount(), 1);
    TestTrue("forced rebuild with the same geometry", Board->Rebuild(Model));
    TestEqual("the forced rebuild ran the full build", Board->GetBuildCount(), 2);
    TestNull("the full build cleared the fighters (ClearChildren)", Board->FindFighterActor(TEXT("f-0")));
    Board->SyncFighters(Model, TwoFighters(), TEXT("host"));
    TestNotNull("fighters spawned again by SyncFighters", Board->FindFighterActor(TEXT("f-0")));
    TestTrue("only one forced rebuild", Board->Rebuild(Model));
    TestEqual("the next same-geometry Rebuild keeps the tiles", Board->GetBuildCount(), 2);
    const FString AppliedSha = Board->GetArtData().SourceSha256;

    // 2) invalid JSON: refused, the applied document and the board stay, nothing is forced
    FFileHelper::SaveStringToFile(TEXT("{\"schema\": \"unmatched.s08-art-board-profiles/1\", \"revision\": "), *Profiles);
    Errors.Reset();
    TestFalse("invalid JSON refused", Board->ReloadArtData(Profiles, true, EnvDir, Errors, Warnings));
    TestTrue("the error is reported", Errors.Num() > 0 && Errors[0].StartsWith(TEXT("profiles:")));
    TestEqual("revision kept", Board->GetArtData().Revision, 20);
    TestEqual("sha kept", Board->GetAppliedRender().ProfilesSha256, AppliedSha);
    TestNotNull("fighters kept", Board->FindFighterActor(TEXT("f-0")));
    TestTrue("no forced rebuild", Board->Rebuild(Model));
    TestEqual("build count kept", Board->GetBuildCount(), 2);

    // 3) a document that parses but fails validation (a board pointing at a missing light profile)
    FString Broken = Doc(21, 3.0f);
    Broken.ReplaceInline(TEXT("\"light\":\"L\""), TEXT("\"light\":\"nope\""));
    FFileHelper::SaveStringToFile(Broken, *Profiles);
    Errors.Reset();
    TestFalse("invalid profile refused", Board->ReloadArtData(Profiles, true, EnvDir, Errors, Warnings));
    TestTrue("validation error reported", Errors.Num() > 0);
    TestEqual("revision kept after the validation error", Board->GetArtData().Revision, 20);

    // 4) a valid profile document but a broken env layout in the folder: refused as a whole (no half-applied board)
    FFileHelper::SaveStringToFile(Doc(22, 3.0f), *Profiles);
    FFileHelper::SaveStringToFile(TEXT("{\"schema\": \"unmatched.env-layout/1\""), *(EnvDir / TEXT("broken.layout.json")));
    Errors.Reset();
    TestFalse("broken env layout refused", Board->ReloadArtData(Profiles, true, EnvDir, Errors, Warnings));
    TestTrue(FString::Printf(TEXT("env layout error reported (%s)"), *FString::Join(Errors, TEXT("; "))),
             Errors.Num() > 0 && Errors[0].StartsWith(TEXT("envlayout broken.layout.json")));
    TestEqual("revision kept after the env layout error", Board->GetArtData().Revision, 20);
    TestTrue("still no forced rebuild", Board->Rebuild(Model));
    TestEqual("build count still kept", Board->GetBuildCount(), 2);

    // 5) the env folder fixed: accepted
    IFileManager::Get().Delete(*(EnvDir / TEXT("broken.layout.json")));
    Errors.Reset();
    TestTrue("accepted again", Board->ReloadArtData(Profiles, false, EnvDir, Errors, Warnings));
    TestEqual("revision 22", Board->GetArtData().Revision, 22);
    TestEqual("default path -> source pak", Board->GetAppliedRender().ProfilesSource, FString(TEXT("pak")));
    TestTrue("forced again", Board->Rebuild(Model));
    TestEqual("third full build", Board->GetBuildCount(), 3);

    // a board that started without art cannot be reloaded (BeginPlay loads the assets once)
    AS08BoardActor* Grey = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator);
    if (Grey) {
      Errors.Reset();
      TestFalse("grey board refuses a reload", Grey->ReloadArtData(Profiles, false, EnvDir, Errors, Warnings));
      TestTrue("relaunch reason", Errors.Num() == 1 && Errors[0].Contains(TEXT("relaunch")));
    }
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  IFileManager::Get().DeleteDirectory(*Dir, false, true);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
