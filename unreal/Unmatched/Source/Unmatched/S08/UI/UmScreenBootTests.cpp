// VS-7 S1 automation tests (docs/game-design/visual/06-tasks/screens.csv SC-02...SC-05; 04-hud-spec.md §1, §1.1):
//   Unmatched.S08.Hud.Screens.Boot.Tree    BOOT's parts from the code tree and from WBP_UI_SCR_BOOT (+ the resume modal);
//                                          the RU texts of every stage (the wordmark, the captions, the heroes counter
//                                          after heroList, the build), the bar by stages done / 3, the error banner with
//                                          one primary «Повторить» (retrying: disabled, why.syncing), the resume modal
//                                          (the database names, nominative; one primary), the SHOT states
//                                          loading / error / resume, the presses (once each, only in their state).
//   Unmatched.S08.Hud.Screens.Boot.Timer   the model: every stage has its caption (a bar is never captionless for 2 s);
//                                          10 s without an answer -> the error (SC-04); the stamp commit.
//   Unmatched.S08.Hud.Screens.MenuBg       SC-02: the fixture board of the backdrop (Marmoreal original, no fighters
//                                          read), the SCREEN-BG line, the rollback keys (-S08SlateHud=menubg / all).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Screens" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../S08ArtLook.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "UmButton.h"
#include "UmGameHud.h"
#include "UmMenuBackdrop.h"
#include "UmScreenBoot.h"
#include "UmText.h"

namespace UmFlowScreensTest {
struct FWorld {
  UWorld* World = nullptr;
  explicit FWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
  }
  ~FWorld() {
    if (!World) return;
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  }
};

struct FRu {
  FInternationalization::FCultureStateSnapshot Snapshot;
  FRu() {
    FInternationalization::Get().BackupCultureState(Snapshot);
    FInternationalization::Get().SetCurrentLanguageAndLocale(TEXT("ru"));
#if WITH_EDITOR  // the preview API exists only WITH_EDITOR (the C2039 trap of the game target)
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(TEXT("ru"));
#endif
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FRu() { FInternationalization::Get().RestoreCultureState(Snapshot); }
};
}  // namespace UmFlowScreensTest

using namespace UmFlowScreensTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensBootTreeTest, "Unmatched.S08.Hud.Screens.Boot.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensBootTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmBootTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    UClass* Class = Pass == 0 ? UUmScreenBoot::StaticClass() : UUmScreenBoot::WidgetClass();
    if (Pass == 1 && Class == UUmScreenBoot::StaticClass()) {
      AddInfo(TEXT("WBP_UI_SCR_BOOT not authored yet - the code tree only"));
      continue;
    }
    UUmScreenBoot* B = CreateWidget<UUmScreenBoot>(W.World, Class);
    FString Missing;
    TestTrue(FString::Printf(TEXT("pass %d: every part (%s)"), Pass, *Missing), B && B->HasAllParts(&Missing));
    if (!B) continue;
    B->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
    B->PlayShow();
    FUmBootModel M;
    M.BuildCommit = TEXT("6627333e");
    B->ApplyModel(M, 0.0);
    TestEqual(TEXT("the wordmark (ВР-H19)"), B->Wordmark->GetText().ToString(), FString(TEXT("UNMATCHED")));
    TestEqual(TEXT("session caption"), B->GetStageText(), FString(TEXT("Проверка сессии…")));
    TestEqual(TEXT("session 0/3"), B->GetBarPercent(), 0.0f);
    TestEqual(TEXT("the build"), B->GetBuildText(), FString(TEXT("сборка 6627333e")));
    TestEqual(TEXT("state loading"), B->GetScreenState(), FName(TEXT("loading")));
    M.Stage = EUmBootStage::Heroes;
    B->ApplyModel(M, 0.0);
    TestEqual(TEXT("heroes before the answer (ВР-VS4-SC03-05)"), B->GetStageText(), FString(TEXT("Загрузка героев…")));
    TestTrue(TEXT("heroes waiting 1/3"), FMath::IsNearlyEqual(B->GetBarPercent(), 1.0f / 3.0f, 1.0e-4f));
    M.bHeroesLoaded = true;
    M.Heroes = M.HeroesTotal = 84;
    B->ApplyModel(M, 0.0);
    TestEqual(TEXT("heroes after heroList"), B->GetStageText(), FString(TEXT("Загрузка героев… 84/84")));
    TestTrue(TEXT("heroes 2/3"), FMath::IsNearlyEqual(B->GetBarPercent(), 2.0f / 3.0f, 1.0e-4f));
    M.Stage = EUmBootStage::Boards;
    B->ApplyModel(M, 0.0);
    TestEqual(TEXT("boards caption"), B->GetStageText(), FString(TEXT("Загрузка досок…")));
    TestFalse(TEXT("no banner while loading"), B->IsErrorShown());
    // SC-04
    M.bError = true;
    B->ApplyModel(M, 0.0);
    TestTrue(TEXT("the error banner"), B->IsErrorShown());
    TestEqual(TEXT("state error"), B->GetScreenState(), FName(TEXT("error")));
    TestEqual(TEXT("«Сервер недоступен»"), B->ErrorText->GetText().ToString(), FString(TEXT("Сервер недоступен")));
    TestTrue(TEXT("«Повторить» the one primary, enabled"), B->RetryButton->GetModel().Variant == EUmButtonVariant::Primary &&
                                                             B->RetryButton->GetModel().bEnabled);
    TestEqual(TEXT("«ПОВТОРИТЬ» label"), B->RetryButton->GetModel().Label.ToString(), FString(TEXT("Повторить")));
    TestEqual(TEXT("the stage caption stays"), B->GetStageText(), FString(TEXT("Загрузка досок…")));
    int32 Retries = 0, Resumes = 0, Lobbies = 0;
    UUmScreenBoot::FInput In;
    In.OnRetry = [&Retries]() { ++Retries; };
    In.OnResume = [&Resumes]() { ++Resumes; };
    In.OnLobby = [&Lobbies]() { ++Lobbies; };
    B->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
    B->SimulatePress(FName(TEXT("screens.boot.retry")));
    TestEqual(TEXT("Retry once"), Retries, 1);
    M.bRetrying = true;
    B->ApplyModel(M, 0.0);
    TestTrue(TEXT("retrying: disabled with why.syncing"), !B->RetryButton->GetModel().bEnabled &&
                                                            B->RetryButton->GetModel().Reason.Key == FName(TEXT("why.syncing")));
    B->SimulatePress(FName(TEXT("screens.boot.retry")));
    TestEqual(TEXT("no second retry while one is in flight"), Retries, 1);
    TestEqual(TEXT("why.syncing text"), B->WhyText->GetText().ToString(), FString(TEXT("Синхронизация…")));
    // SC-05
    M.bError = M.bRetrying = false;
    M.Stage = EUmBootStage::Done;
    M.bResume = true;
    M.ResumeHero = TEXT("Medusa");
    M.ResumeOpponent = TEXT("King Arthur");
    M.ResumeBoard = TEXT("Marmoreal · original map");
    B->ApplyModel(M, 0.0);
    TestEqual(TEXT("state resume (ВР-SC11)"), B->GetScreenState(), FName(TEXT("resume")));
    TestEqual(TEXT("the resume line: database names, nominative"), B->GetResumeLineText(),
              FString(TEXT("Ваш герой: Medusa · соперник: King Arthur · Marmoreal · original map")));
    UUmBootResume* R = B->GetResume();
    TestTrue(TEXT("one primary: «Вернуться в партию»"), R && R->ResumeButton->GetModel().Variant == EUmButtonVariant::Primary &&
                                                         R->LobbyButton->GetModel().Variant == EUmButtonVariant::Normal);
    if (R) {
      TestEqual(TEXT("«Партия идёт»"), R->ResumeTitle->GetText().ToString(), FString(TEXT("Партия идёт")));
      TestEqual(TEXT("«В лобби»"), R->LobbyButton->GetModel().Label.ToString(), FString(TEXT("В лобби")));
      TestEqual(TEXT("«Вернуться в партию»"), R->ResumeButton->GetModel().Label.ToString(), FString(TEXT("Вернуться в партию")));
      TestTrue(TEXT("the modal is a modal (250 / 120 ms)"), R->IsModal() && R->IsShown());
    }
    B->SimulatePress(FName(TEXT("screens.boot.retry")));
    TestEqual(TEXT("Retry does nothing without the error"), Retries, 1);
    B->SimulatePress(FName(TEXT("screens.boot.resume")));
    TestEqual(TEXT("Return once"), Resumes, 1);
    M.bResuming = true;
    B->ApplyModel(M, 0.0);
    TestTrue(TEXT("resuming: the primary disabled with why.syncing (ВР-VS4-SC03-07)"),
             R && !R->ResumeButton->GetModel().bEnabled && R->ResumeButton->GetModel().Reason.Key == FName(TEXT("why.syncing")));
    B->SimulatePress(FName(TEXT("screens.boot.resume")));
    TestEqual(TEXT("no second return while resuming"), Resumes, 1);
    B->SimulatePress(FName(TEXT("screens.boot.lobby")));
    TestEqual(TEXT("«В лобби» once"), Lobbies, 1);
    TArray<FString> Lines;
    B->CollectShotLines(Lines);
    TestTrue(TEXT("SHOT line: UI-SCR-BOOT state=resume stage=done done=3/3"),
             Lines.Num() == 1 && Lines[0].Contains(TEXT("id=UI-SCR-BOOT")) && Lines[0].Contains(TEXT("state=resume")) &&
                 Lines[0].Contains(TEXT("stage=done")) && Lines[0].Contains(TEXT("done=3/3")) && Lines[0].Contains(TEXT("geom=painted")));
    if (Lines.Num()) AddInfo(Lines[0]);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensBootTimerTest, "Unmatched.S08.Hud.Screens.Boot.Timer",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensBootTimerTest::RunTest(const FString& Parameters) {
  FRu Ru;
  // a bar always has its caption: every stage / answer state names one (04 §1.1: > 2 s without one is a defect)
  for (EUmBootStage S : {EUmBootStage::Session, EUmBootStage::Heroes, EUmBootStage::Boards, EUmBootStage::Done}) {
    for (int32 Loaded = 0; Loaded < 2; ++Loaded) {
      for (int32 Err = 0; Err < 2; ++Err) {
        FUmBootModel M;
        M.Stage = S;
        M.bHeroesLoaded = Loaded != 0;
        M.Heroes = M.HeroesTotal = 84;
        M.bError = Err != 0;
        const FText Cap = UmBoot::Caption(M);
        TestFalse(FString::Printf(TEXT("stage %s loaded %d error %d: a caption"), UmBoot::StageName(S), Loaded, Err),
                  Cap.IsEmpty() || Cap.ToString().StartsWith(TEXT("?")));
      }
    }
  }
  TestEqual(TEXT("done: session 0"), UmBoot::DoneOf(FUmBootModel()), 0);
  FUmBootModel H;
  H.Stage = EUmBootStage::Heroes;
  TestEqual(TEXT("done: heroes waiting 1"), UmBoot::DoneOf(H), 1);
  H.bHeroesLoaded = true;
  TestEqual(TEXT("done: heroes answered 2"), UmBoot::DoneOf(H), 2);
  H.Stage = EUmBootStage::Boards;
  TestEqual(TEXT("done: boards 2"), UmBoot::DoneOf(H), 2);
  H.Stage = EUmBootStage::Done;
  TestEqual(TEXT("done: 3"), UmBoot::DoneOf(H), 3);
  // SC-04: 10 s without an answer -> the banner (04 §1.1)
  TestFalse(TEXT("9.999 s: still waiting"), UmBoot::TimedOut(1000.0, 1000.0 + 9999.0));
  TestTrue(TEXT("10 s: the error"), UmBoot::TimedOut(1000.0, 1000.0 + 10000.0));
  TestFalse(TEXT("no stage started: no timeout"), UmBoot::TimedOut(-1.0, 50000.0));
  TestTrue(TEXT("a stage passed keeps its caption >= 400 ms (ВР-VS7-03)"), UmBoot::MinStageMs >= 400.0 && UmBoot::MinStageMs < 2000.0);
  // the build commit of the staged stamp
  TestEqual(TEXT("stamp commit"), UmBoot::CommitFromStamp(TEXT("{\"schema\":\"unmatched.staged-build-stamp/1\",\"commit\":\"6627333e1234\"}")),
            FString(TEXT("6627333e")));
  TestEqual(TEXT("no commit"), UmBoot::CommitFromStamp(TEXT("{}")), FString());
  // the layout rows (04 §1.1 / ВР-VS4-SC03-03)
  TestTrue(TEXT("1080p rows"), UmBoot::WordmarkBar(FVector2D(1920.0, 1080.0), false).Equals(FVector2D(400.0, 500.0), 0.01));
  TestTrue(TEXT("720p rows"), UmBoot::WordmarkBar(FVector2D(1706.67, 960.0), false).Equals(FVector2D(356.0, 448.0), 0.01));
  TestTrue(TEXT("720p 150 %: the 1080p offsets"), UmBoot::WordmarkBar(FVector2D(1137.78, 640.0), true).Equals(FVector2D(180.0, 280.0), 0.01));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensMenuBgTest, "Unmatched.S08.Hud.Screens.MenuBg",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensMenuBgTest::RunTest(const FString& Parameters) {
  FS08BoardModel Board;
  FString BoardId, Problem;
  TestTrue(FString::Printf(TEXT("the backdrop fixture loads (%s)"), *Problem),
           UmMenuBackdrop::LoadBoard(UmMenuBackdrop::FixturePath(), Board, BoardId, &Problem));
  TestEqual(TEXT("Marmoreal · original map"), BoardId, FString(UmMenuBackdrop::BoardId));
  TestTrue(TEXT("a topology board (the map, not a grid)"), Board.bHasTopology && Board.Width > 0 && Board.Height > 0);
  const FString Line = UmMenuBackdrop::TraceLine(BoardId, TEXT("marmoreal-original"), 0, TEXT("paste(default)"), TEXT("Login"), TEXT("menu"));
  TestEqual(TEXT("SCREEN-BG line"), Line,
            FString(TEXT("SCREEN-BG board=marmoreal-original boardId=c121b47f8d6eb28daccb76d05 profile=marmoreal-original fighters=0 "
                         "veil=0.60 backdrop=paste stage=Login state=menu")));
  TestEqual(TEXT("p5c rollback short"), UmMenuBackdrop::BackdropShort(TEXT("p5c(flag-off)")), FString(TEXT("p5c")));
  TestTrue(TEXT("default: the scene"), UmMenuBackdrop::Wanted(S08ArtLook::ParseSlateHud(TEXT("-game"))));
  TestFalse(TEXT("-S08SlateHud=menubg: black"), UmMenuBackdrop::Wanted(S08ArtLook::ParseSlateHud(TEXT("-game -S08SlateHud=menubg"))));
  TestFalse(TEXT("-S08SlateHud: black"), UmMenuBackdrop::Wanted(S08ArtLook::ParseSlateHud(TEXT("-game -S08SlateHud"))));
  TestTrue(TEXT("another key keeps the scene"), UmMenuBackdrop::Wanted(S08ArtLook::ParseSlateHud(TEXT("-game -S08SlateHud=boot"))));
  return true;
}

#endif
