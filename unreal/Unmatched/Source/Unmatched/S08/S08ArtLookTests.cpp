// ART-DEFAULT (2026-10-04) automation tests of S08ArtLook.h: the accepted art look, the look-dev heroes v2 and the
// diorama tray are the DEFAULT of a run without flags; -S08GreyBoard / -S08HeroesLegacy / -S08DioramaLegacy roll them
// back; -ArtPreviewHeroesV2 / -ArtPreviewDiorama are no-op aliases; -ArtPreview is the review tooling only. The flags are
// read from the real command line: each case appends them to the run's own command line and restores it after.
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.ArtLook; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08ArtLook.h"
#include "S08ArtPreviewMedusa.h"
#include "S08BoardActor.h"
#include "S08BoardModel.h"
#include "S08Diorama.h"
#include "S08EnvLayout.h"
#include "S08FighterActor.h"
#include "S08HeroesV2.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace S08ArtLookTest {
/** Every flag this file sets; a run started with one of them cannot test the no-flag default. */
const TCHAR* const Flags[] = {TEXT("S08GreyBoard"),        TEXT("S08HeroesLegacy"),     TEXT("S08DioramaLegacy"),
                              TEXT("ArtPreview"),          TEXT("ArtPreviewHeroesV2"),  TEXT("ArtPreviewDiorama"),
                              TEXT("ArtPreviewAllMedusa"), TEXT("ArtPreviewNoEnv")};

/** The run's command line plus Extra while in scope; every automation override reset (the real command line rules). */
struct FCommandLineScope {
  FString Saved;
  explicit FCommandLineScope(const TCHAR* Extra) : Saved(FCommandLine::Get()) {
    ResetOverrides();
    FCommandLine::Set(*(Saved + TEXT(" ") + Extra));
  }
  ~FCommandLineScope() {
    FCommandLine::Set(*Saved);
    ResetOverrides();
  }
  static void ResetOverrides() {
    S08ArtLook::ResetOverrideForTest();
    S08HeroesV2::ResetFlagOverrideForTest();
    S08Diorama::ResetFlagOverrideForTest();
    S08EnvLayout::ResetOptOutOverrideForTest();
  }
};

bool BaseHasFlag(FString& OutFlag) {
  for (const TCHAR* Flag : Flags) {
    if (FParse::Param(FCommandLine::Get(), Flag)) {
      OutFlag = Flag;
      return true;
    }
  }
  return false;
}

FS08BoardFighter MakeFighter(const TCHAR* Id, const TCHAR* Name, bool bHero) {
  FS08BoardFighter F;
  F.Id = Id;
  F.OwnerId = TEXT("owner");
  F.Name = Name;
  F.Label = Name;
  F.bIsHero = bHero;
  F.Health = 10;
  F.MaxHealth = 10;
  F.X = 2;
  F.Y = 2;
  return F;
}
}  // namespace S08ArtLookTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtLookDefaultTest,
    "Unmatched.S08.ArtLook.Default art look, heroes v2 and tray on without flags; rollback flags and no-op aliases",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtLookDefaultTest::RunTest(const FString&) {
  using namespace S08ArtLookTest;
  FString Present;
  if (BaseHasFlag(Present)) {
    AddError(FString::Printf(TEXT("the test run itself carries -%s: start it without art flags"), *Present));
    return true;
  }
  TestEqual("grey-board rollback flag", FString(S08ArtLook::GreyBoardFlagName), FString(TEXT("S08GreyBoard")));
  TestEqual("review flag", FString(S08ArtLook::ReviewFlagName), FString(TEXT("ArtPreview")));
  TestEqual("heroes rollback flag", FString(S08HeroesV2::LegacyFlagName), FString(TEXT("S08HeroesLegacy")));
  TestEqual("tray rollback flag", FString(S08Diorama::LegacyFlagName), FString(TEXT("S08DioramaLegacy")));
  TestTrue("rule: art look without the rollback", S08ArtLook::Decide(false));
  TestFalse("rule: grey board with -S08GreyBoard", S08ArtLook::Decide(true));
  TestTrue("rule: tray without the rollback", S08Diorama::Decide(false));
  TestFalse("rule: no tray with -S08DioramaLegacy", S08Diorama::Decide(true));

  // 1) no flags at all: the accepted look (GD-058 final, dx12-lumen-high-v2) is what a plain client shows
  {
    FCommandLineScope Cmd(TEXT(""));
    TestTrue("default: art look", S08ArtLook::Enabled());
    TestFalse("default: no review tooling", S08ArtLook::ReviewTooling());
    TestTrue("default: heroes v2", S08HeroesV2::FlagEnabled());
    TestTrue("default: tray", S08Diorama::FlagEnabled());
    TestTrue("default: tray on the art look", S08Diorama::Enabled(S08ArtLook::Enabled()));
    TestTrue("default: environment of the map boards", S08EnvLayout::Enabled(S08ArtLook::Enabled()));
    const FString Line = S08ArtLook::TraceLine();
    AddInfo(Line);
    TestTrue(FString::Printf(TEXT("default trace line: %s"), *Line),
             Line.StartsWith(TEXT("ARTLOOK art=1 source=default heroes=v2 tray=on env=on review=0 ")) &&
                 Line.Contains(TEXT(" aliases=-")) && !Line.Contains(TEXT("grey board")));
    // run I (AB-5..AB-8, 2026-10-05): the accepted turn HUD look is in the line
    TestTrue(FString::Printf(TEXT("default hud look traced: %s"), *Line),
             Line.Contains(TEXT(" hud=ring:marker-turn-ring,glow:on,tracker:de,cross:on")));
  }
  // 2) the former opt-in flags are accepted and change nothing
  {
    FCommandLineScope Cmd(TEXT("-ArtPreviewHeroesV2 -ArtPreviewDiorama"));
    TestTrue("aliases: art look", S08ArtLook::Enabled());
    TestTrue("aliases: heroes v2", S08HeroesV2::FlagEnabled());
    TestTrue("aliases: tray", S08Diorama::FlagEnabled());
    const FString Line = S08ArtLook::TraceLine();
    TestTrue(FString::Printf(TEXT("aliases traced: %s"), *Line),
             Line.Contains(TEXT("heroes=v2 tray=on")) &&
                 Line.Contains(TEXT("aliases=-ArtPreviewHeroesV2,-ArtPreviewDiorama")));
  }
  // 2b) run I: the turn HUD rollbacks are traced by their flags, the former -S08HeartGlow is a no-op alias
  {
    FCommandLineScope Cmd(TEXT("-S08TrackerLegacy -S08CrossLegacy -S08HeartGlow"));
    const FString Line = S08ArtLook::TraceLine();
    TestTrue(FString::Printf(TEXT("hud rollbacks traced: %s"), *Line),
             Line.Contains(TEXT(" aliases=-S08HeartGlow ")) &&
                 Line.Contains(TEXT(" hud=ring:marker-turn-ring,glow:on,tracker:legacy(-S08TrackerLegacy),")
                                   TEXT("cross:legacy(-S08CrossLegacy)")));
  }
  // 3) -S08HeroesLegacy: the pre-default figures, the rest of the look stays
  {
    FCommandLineScope Cmd(TEXT("-S08HeroesLegacy"));
    TestTrue("-S08HeroesLegacy: art look stays", S08ArtLook::Enabled());
    TestFalse("-S08HeroesLegacy: no v2", S08HeroesV2::FlagEnabled());
    TestTrue("-S08HeroesLegacy: requested", S08HeroesV2::LegacyRequested());
    TestTrue("-S08HeroesLegacy: tray stays", S08Diorama::FlagEnabled());
    TestTrue("-S08HeroesLegacy traced", S08ArtLook::TraceLine().Contains(TEXT("heroes=legacy(-S08HeroesLegacy) tray=on")));
  }
  // ... and the rollback wins over the no-op alias
  {
    FCommandLineScope Cmd(TEXT("-ArtPreviewHeroesV2 -S08HeroesLegacy"));
    TestFalse("alias + rollback: legacy", S08HeroesV2::FlagEnabled());
  }
  // 4) -S08DioramaLegacy: no tray and no environment, v2 figures stay
  {
    FCommandLineScope Cmd(TEXT("-S08DioramaLegacy"));
    TestFalse("-S08DioramaLegacy: no tray", S08Diorama::FlagEnabled());
    TestFalse("-S08DioramaLegacy: no tray on the art look", S08Diorama::Enabled(true));
    TestFalse("-S08DioramaLegacy: no environment", S08EnvLayout::Enabled(true));
    TestTrue("-S08DioramaLegacy: v2 stays", S08HeroesV2::FlagEnabled());
    TestTrue("-S08DioramaLegacy traced",
             S08ArtLook::TraceLine().Contains(TEXT("heroes=v2 tray=legacy(-S08DioramaLegacy) env=off(no tray)")));
  }
  // 5) -S08GreyBoard: the whole art look off
  {
    FCommandLineScope Cmd(TEXT("-S08GreyBoard"));
    TestFalse("-S08GreyBoard: grey board", S08ArtLook::Enabled());
    TestFalse("-S08GreyBoard: no tray", S08Diorama::Enabled(S08ArtLook::Enabled()));
    TestFalse("-S08GreyBoard: no environment", S08EnvLayout::Enabled(S08ArtLook::Enabled()));
    TestNull("-S08GreyBoard: no v2 mapping (no art board)",
             S08HeroesV2::Find(S08ArtLook::Enabled(), S08HeroesV2::FlagEnabled(), TEXT("King Arthur")));
    const FString Line = S08ArtLook::TraceLine();
    TestTrue(FString::Printf(TEXT("-S08GreyBoard traced: %s"), *Line),
             Line.StartsWith(TEXT("ARTLOOK art=0 source=S08GreyBoard ")) && Line.Contains(TEXT("grey board")));
  }
  // 6) -ArtPreview is the review tooling: the look does not change with it
  {
    FCommandLineScope Cmd(TEXT("-ArtPreview"));
    TestTrue("-ArtPreview: review tooling", S08ArtLook::ReviewTooling());
    TestTrue("-ArtPreview: same art look", S08ArtLook::Enabled() && S08HeroesV2::FlagEnabled() && S08Diorama::FlagEnabled());
    TestTrue("-ArtPreview traced", S08ArtLook::TraceLine().Contains(TEXT(" review=1 ")));
  }
  // 7) the six-Medusa review is tooling: it needs -ArtPreview, and then the v2 figures yield to it
  {
    FCommandLineScope Cmd(TEXT("-ArtPreviewAllMedusa"));
    TestFalse("-ArtPreviewAllMedusa without -ArtPreview: no review", S08ArtPreviewAllMedusa());
    TestTrue("-ArtPreviewAllMedusa without -ArtPreview: v2 stays", S08HeroesV2::FlagEnabled());
  }
  {
    FCommandLineScope Cmd(TEXT("-ArtPreview -ArtPreviewAllMedusa"));
    TestTrue("-ArtPreview -ArtPreviewAllMedusa: review", S08ArtPreviewAllMedusa());
    TestFalse("-ArtPreview -ArtPreviewAllMedusa: v2 yields", S08HeroesV2::FlagEnabled());
    TestTrue("all-Medusa traced", S08ArtLook::TraceLine().Contains(TEXT("heroes=legacy(-ArtPreviewAllMedusa)")));
  }
  // 8) the automation override
  {
    FCommandLineScope Cmd(TEXT(""));
    S08ArtLook::SetOverrideForTest(false);
    TestFalse("override off", S08ArtLook::Enabled());
    TestTrue("override traced", S08ArtLook::TraceLine().StartsWith(TEXT("ARTLOOK art=0 source=override ")));
    S08ArtLook::SetOverrideForTest(true);
    TestTrue("override on", S08ArtLook::Enabled());
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ArtLookActorTest,
    "Unmatched.S08.ArtLook.Actor without flags the board gets the tray and King Arthur the v2 figure; rollbacks restore the old ones",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ArtLookActorTest::RunTest(const FString&) {
  using namespace S08ArtLookTest;
  FString Present;
  if (BaseHasFlag(Present)) {
    AddError(FString::Printf(TEXT("the test run itself carries -%s: start it without art flags"), *Present));
    return true;
  }
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08ArtLookActorWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  const FVector Near(0.0, -50.0, 0.0);
  // The board actor's BeginPlay gate, called the way BeginPlay calls it (a test world runs no BeginPlay).
  auto TrayFor = [&](const TCHAR* What) {
    AS08BoardActor* Board = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                              FRotator::ZeroRotator);
    if (!Board) {
      AddError(FString::Printf(TEXT("%s: board actor not spawned"), What));
      return false;
    }
    const bool bTray = S08ArtLook::Enabled() && Board->EnsureDioramaTray(true) && Board->GetDioramaTray() != nullptr;
    Board->Destroy();
    return bTray;
  };
  // A fighter on an art board (bArtActive = true, as AS08BoardActor::SyncFighters passes it).
  auto ArthurFor = [&](const TCHAR* What, bool& bOutV2, bool& bOutBlockout) {
    AS08FighterActor* Arthur = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), Near,
                                                                   FRotator::ZeroRotator);
    bOutV2 = bOutBlockout = false;
    if (!Arthur) {
      AddError(FString::Printf(TEXT("%s: fighter actor not spawned"), What));
      return;
    }
    Arthur->SetTeam(ES08TeamSlot::P1, ES08TeamSlot::P1, ES08TeamColorMode::Absolute);
    Arthur->ApplyFighter(MakeFighter(TEXT("f-0-hero"), TEXT("King Arthur"), true), Near, true, S08ArtLook::Enabled());
    bOutV2 = Arthur->IsHeroV2();
    bOutBlockout = Arthur->IsBlockout();
    Arthur->Destroy();
  };
  bool bV2 = false, bBlockout = false;
  {
    FCommandLineScope Cmd(TEXT(""));
    TestTrue("no flags: the tray component is created", TrayFor(TEXT("default")));
    ArthurFor(TEXT("default"), bV2, bBlockout);
    TestTrue("no flags: King Arthur is the v2 figure (SK_KingArthur_H2LD)", bV2 && !bBlockout);
  }
  {
    FCommandLineScope Cmd(TEXT("-S08HeroesLegacy"));
    ArthurFor(TEXT("-S08HeroesLegacy"), bV2, bBlockout);
    TestTrue("-S08HeroesLegacy: King Arthur is the ART-003 blockout again", !bV2 && bBlockout);
    TestTrue("-S08HeroesLegacy: the tray stays", TrayFor(TEXT("-S08HeroesLegacy")));
  }
  {
    FCommandLineScope Cmd(TEXT("-S08DioramaLegacy"));
    TestFalse("-S08DioramaLegacy: no tray component", TrayFor(TEXT("-S08DioramaLegacy")));
    ArthurFor(TEXT("-S08DioramaLegacy"), bV2, bBlockout);
    TestTrue("-S08DioramaLegacy: v2 stays", bV2);
  }
  {
    FCommandLineScope Cmd(TEXT("-S08GreyBoard"));
    TestFalse("-S08GreyBoard: no tray", TrayFor(TEXT("-S08GreyBoard")));
    ArthurFor(TEXT("-S08GreyBoard"), bV2, bBlockout);
    TestTrue("-S08GreyBoard: grey mannequin (no art figure)", !bV2 && !bBlockout);
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
