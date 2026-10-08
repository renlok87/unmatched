// VS-7 S5 automation tests (docs/game-design/visual/06-tasks/screens.csv SC-31...SC-38; 04-hud-spec.md §1.9-§1.11):
//   Unmatched.S08.Hud.Screens.Reconnect.Tree   RECONNECT's parts (code tree, WBP_UI_SCR_RECONNECT); auto «Соединение
//                                              потеряно», «Переподключение… попытка 1 из 5», «Пропущено событий: 0»,
//                                              the ↻ icon, «Выйти в лобби» normal and no primary; manual: the X icon, no
//                                              attempt line, «Переподключить» the one primary; expired: «Сессия истекла —
//                                              войдите снова», «Ко входу» the one primary, no retry / lobby; restoring: the
//                                              spinner slot and «Загрузка состояния…», no buttons; the card heights 330 /
//                                              298 / 218 / 146 su; the presses; the card inside 1080p, 720p, 720p 150 %.
//   Unmatched.S08.Hud.Screens.Reconnect.Model  Decide (expired > restoring > manual at 50 s > auto; a GD-037 recovery after
//                                              300 ms), AttemptAt (1..5 by 10 s), ExitAlpha (200 ms, reduced 100 ms).
//   Unmatched.S08.Hud.Screens.GameOver.Tree    GAMEOVER's parts (code tree, WBP_UI_SCR_GAMEOVER); the run I data: victory
//                                              «ПОБЕДА», «MEDUSA ПОБЕЖДАЕТ», «King Arthur: HP достигли 0», «Ход 11 · 0:27»,
//                                              captions «Вы · HP 11/16 · Победитель» / «Соперник · HP 0/18 · Повержен»;
//                                              defeat «ПОРАЖЕНИЕ» (run I Sarpedon); draw (no headline / reason / turn); one
//                                              primary everywhere; VS_AI: «Сыграть ещё» + busy «Создаём партию…» (state
//                                              again), 1x1 without it; board: the strip «ХОД 11 · ПОБЕДА», state board, the
//                                              strip x FIELD 0 px²; the presses; the modal inside every canvas.
//   Unmatched.S08.Hud.Screens.GameOver.Model   NextAgainStep (leave -> create -> select -> ready -> start -> done, an error
//                                              or a timeout -> failed), Duration (m:ss, h:mm:ss), StateName, ModalSize.
//   Unmatched.S08.Hud.Screens.Aborted.Tree     ABORTED's parts (code tree, WBP_UI_SCR_ABORTED); «Партия прервана»,
//                                              «Соперник покинул партию» (no leaver from the server), «Игрок Veteran
//                                              покинул партию» (named), «Ход 1»; «В лобби» the one primary; no victory /
//                                              defeat word; the press.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Screens" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../S08AnimatedIconWidget.h"
#include "Components/Border.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "UmButton.h"
#include "UmReconnectOverlay.h"
#include "UmScreenAborted.h"
#include "UmScreenGameOver.h"

namespace UmEndTest {
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
#if WITH_EDITOR
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(TEXT("ru"));
#endif
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FRu() { FInternationalization::Get().RestoreCultureState(Snapshot); }
};

const FVector2D Canvases[3] = {FVector2D(1920.0, 1080.0), FVector2D(1706.67, 960.0), FVector2D(1137.78, 640.0)};
const bool ClassS[3] = {false, false, true};

bool Inside(const FBox2D& R, const FVector2D& Canvas) {
  return R.Min.X >= 0.0 && R.Min.Y >= 0.0 && R.Max.X <= Canvas.X + 0.01 && R.Max.Y <= Canvas.Y + 0.01;
}

// run I Marmoreal host: RESULT summary outcome=VICTORY winnerHero=Medusa loserHero=King_Arthur reason=hp0 turn=11
// duration=27, Medusa 11/16, King Arthur 0/18 (ВР-VS5-SC34-02) - test copies of the real values
FUmGameOverModel RunIVictory() {
  FUmGameOverModel M;
  M.Outcome = EUmGameOverOutcome::Victory;
  M.WinnerHero = TEXT("Medusa");
  M.LoserHero = TEXT("King Arthur");
  M.Turn = 11;
  M.DurationSec = 27;
  M.Left.HeroName = TEXT("Medusa");
  M.Left.HeroKey = FName(TEXT("medusa"));
  M.Left.Role = TEXT("Вы");
  M.Left.Hp = 11;
  M.Left.MaxHp = 16;
  M.Left.bWinner = true;
  M.Right.HeroName = TEXT("King Arthur");
  M.Right.HeroKey = FName(TEXT("king-arthur"));
  M.Right.Role = TEXT("Соперник");
  M.Right.Hp = 0;
  M.Right.MaxHp = 18;
  M.Right.bFallen = true;
  return M;
}
}  // namespace UmEndTest

using namespace UmEndTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensReconnectModelTest, "Unmatched.S08.Hud.Screens.Reconnect.Model",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensReconnectModelTest::RunTest(const FString& Parameters) {
  FUmReconnectInput In;
  TestEqual(TEXT("not started: hidden"), UmReconnect::Decide(In), EUmReconnectState::Hidden);
  In.bStarted = true;
  TestEqual(TEXT("live: hidden"), UmReconnect::Decide(In), EUmReconnectState::Hidden);
  In.bLost = true;
  In.LostForMs = 0.0;
  TestEqual(TEXT("lost: auto"), UmReconnect::Decide(In), EUmReconnectState::Auto);
  In.LostForMs = 49999.0;
  TestEqual(TEXT("49.9 s: auto"), UmReconnect::Decide(In), EUmReconnectState::Auto);
  In.LostForMs = 50000.0;
  TestEqual(TEXT("50 s (5 x 10 s): manual"), UmReconnect::Decide(In), EUmReconnectState::Manual);
  In.bAcked = true;
  TestEqual(TEXT("the transport back: restoring"), UmReconnect::Decide(In), EUmReconnectState::Restoring);
  In.bExpiredInMatch = true;
  TestEqual(TEXT("expired wins"), UmReconnect::Decide(In), EUmReconnectState::Expired);
  FUmReconnectInput Rec;
  Rec.bStarted = true;
  Rec.bAwaitingRecovery = true;
  Rec.RecoveryForMs = 299.0;
  TestEqual(TEXT("GD-037 recovery < 300 ms: hidden"), UmReconnect::Decide(Rec), EUmReconnectState::Hidden);
  Rec.RecoveryForMs = 300.0;
  TestEqual(TEXT("GD-037 recovery >= 300 ms: restoring"), UmReconnect::Decide(Rec), EUmReconnectState::Restoring);
  TestEqual(TEXT("attempt at 0 s"), UmReconnect::AttemptAt(0.0), 1);
  TestEqual(TEXT("attempt at 10 s"), UmReconnect::AttemptAt(10000.0), 2);
  TestEqual(TEXT("attempt at 45 s"), UmReconnect::AttemptAt(45000.0), 5);
  TestEqual(TEXT("attempt capped at 5"), UmReconnect::AttemptAt(120000.0), 5);
  TestEqual(TEXT("exit 0 ms"), UmReconnect::ExitAlpha(0.0, false), 1.0f);
  TestEqual(TEXT("exit 100 ms"), UmReconnect::ExitAlpha(100.0, false), 0.5f);
  TestEqual(TEXT("exit 200 ms"), UmReconnect::ExitAlpha(200.0, false), 0.0f);
  TestEqual(TEXT("exit reduced 100 ms"), UmReconnect::ExitAlpha(100.0, true), 0.0f);
  TestEqual(TEXT("auto height (two Running lines) 330"), UmReconnect::CardHeightSu(EUmReconnectState::Auto, true), 330.0f);
  TestEqual(TEXT("expired height 218"), UmReconnect::CardHeightSu(EUmReconnectState::Expired, false), 218.0f);
  TestEqual(TEXT("restoring height 146"), UmReconnect::CardHeightSu(EUmReconnectState::Restoring, false), 146.0f);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensReconnectTreeTest, "Unmatched.S08.Hud.Screens.Reconnect.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensReconnectTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmReconnectTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    UClass* Class = Pass == 0 ? UUmReconnectOverlay::StaticClass() : UUmReconnectOverlay::WidgetClass();
    if (Pass == 1 && Class == UUmReconnectOverlay::StaticClass()) {
      AddInfo(TEXT("WBP_UI_SCR_RECONNECT not authored yet - the code tree only"));
      continue;
    }
    UUmReconnectOverlay* O = CreateWidget<UUmReconnectOverlay>(W.World, Class);
    FString Missing;
    TestTrue(FString::Printf(TEXT("pass %d: every part (%s)"), Pass, *Missing), O && O->HasAllParts(&Missing));
    if (!O) continue;
    int32 Leaves = 0, Retries = 0, Logins = 0;
    UUmReconnectOverlay::FInput In;
    In.OnLeave = [&]() { ++Leaves; };
    In.OnRetry = [&]() { ++Retries; };
    In.OnToLogin = [&]() { ++Logins; };
    O->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
    O->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
    O->PlayShow();
    // auto: run E (ВР-VS5-SC31-01) - attempt 1 of 5, missed 0
    FUmReconnectModel M;
    M.State = EUmReconnectState::Auto;
    M.Attempt = 1;
    M.Missed = 0;
    O->ApplyModel(M);
    TestEqual(TEXT("auto state"), O->GetScreenState(), FName(TEXT("auto")));
    TestEqual(TEXT("«Соединение потеряно»"), O->GetTitleText(), FString(TEXT("Соединение потеряно")));
    TestEqual(TEXT("«попытка 1 из 5»"), O->GetAttemptText(), FString(TEXT("Переподключение… попытка 1 из 5")));
    TestEqual(TEXT("«Пропущено событий: 0»"), O->GetMissedText(), FString(TEXT("Пропущено событий: 0")));
    TestTrue(TEXT("Running"), O->GetRunningText().Replace(TEXT("\n"), TEXT(" ")) == TEXT("Партия продолжается на сервере. Не закрывайте приложение."));
    TestEqual(TEXT("auto icon ↻"), O->GetIconId(), FName(TEXT("resource-connection-reconnecting")));
    TestTrue(TEXT("auto: Leave shown"), O->IsShownPart(O->Leave));
    TestFalse(TEXT("auto: Retry hidden until the 5th attempt"), O->IsShownPart(O->Retry));
    TestEqual(TEXT("auto: no primary (ВР-VS5-SC31-04)"), O->PrimaryName(), FString(TEXT("none")));
    TestTrue(TEXT("auto card <= 340 su"), O->CardHeight() <= 340.0f);
    O->SimulatePress(FName(TEXT("screens.reconnect.leave")));
    TestEqual(TEXT("leave press"), Leaves, 1);
    O->SimulatePress(FName(TEXT("screens.reconnect.retry")));
    TestEqual(TEXT("retry refused in auto"), Retries, 0);
    // manual: the X, no attempt line, Retry the one primary
    M.State = EUmReconnectState::Manual;
    M.Attempt = 5;
    O->ApplyModel(M);
    TestEqual(TEXT("manual state"), O->GetScreenState(), FName(TEXT("manual")));
    TestEqual(TEXT("manual icon X"), O->GetIconId(), FName(TEXT("resource-connection-lost")));
    TestFalse(TEXT("manual: no attempt line"), O->IsShownPart(O->Attempt));
    TestTrue(TEXT("manual: Missed"), O->IsShownPart(O->Missed));
    TestEqual(TEXT("manual: Retry the one primary"), O->PrimaryName(), FString(TEXT("retry")));
    O->SimulatePress(FName(TEXT("screens.reconnect.retry")));
    TestEqual(TEXT("retry press"), Retries, 1);
    // expired: one primary «Ко входу», no retry, no lobby
    M.State = EUmReconnectState::Expired;
    O->ApplyModel(M);
    TestEqual(TEXT("expired state"), O->GetScreenState(), FName(TEXT("expired")));
    TestEqual(TEXT("expired title"), O->GetTitleText(), FString(TEXT("Сессия истекла — войдите снова")));
    TestFalse(TEXT("expired: no Retry"), O->IsShownPart(O->Retry));
    TestFalse(TEXT("expired: no Leave"), O->IsShownPart(O->Leave));
    TestEqual(TEXT("expired: «Ко входу» the one primary"), O->PrimaryName(), FString(TEXT("login")));
    TestEqual(TEXT("expired card 218 su"), O->CardHeight(), 218.0f);
    O->SimulatePress(FName(TEXT("screens.reconnect.to.login")));
    TestEqual(TEXT("to-login press"), Logins, 1);
    // restoring: the spinner and «Загрузка состояния…», no buttons
    M.State = EUmReconnectState::Restoring;
    O->ApplyModel(M);
    TestEqual(TEXT("restoring state"), O->GetScreenState(), FName(TEXT("restoring")));
    TestEqual(TEXT("restoring title"), O->GetTitleText(), FString(TEXT("Загрузка состояния…")));
    TestFalse(TEXT("restoring: no icon"), O->IsShownPart(O->Icon));
    TestFalse(TEXT("restoring: no buttons"), O->IsShownPart(O->Leave) || O->IsShownPart(O->Retry) || O->IsShownPart(O->ToLogin));
    TestEqual(TEXT("restoring card 146 su"), O->CardHeight(), 146.0f);
    // every canvas: the card inside
    for (int32 C = 0; C < 3; ++C) {
      M.State = EUmReconnectState::Auto;
      O->ApplyModel(M);
      O->ApplyCanvas(Canvases[C], ClassS[C], 1.0f);
      TestTrue(FString::Printf(TEXT("card inside canvas %d"), C), Inside(O->FrameRectSu(), Canvases[C]));
    }
    TArray<FString> Lines;
    O->CollectShotLines(Lines);
    TestTrue(TEXT("SHOT line UI-SCR-RECONNECT"), Lines.Num() == 1 && Lines[0].Contains(TEXT("id=UI-SCR-RECONNECT")) && Lines[0].Contains(TEXT("state=auto")));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensGameOverModelTest, "Unmatched.S08.Hud.Screens.GameOver.Model",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensGameOverModelTest::RunTest(const FString& Parameters) {
  using namespace UmGameOver;
  FUmAgainInput In;
  TestEqual(TEXT("idle stays"), NextAgainStep(EUmAgainStep::Idle, In), EUmAgainStep::Idle);
  TestEqual(TEXT("leave waits"), NextAgainStep(EUmAgainStep::Leave, In), EUmAgainStep::Leave);
  In.bLobby = true;
  TestEqual(TEXT("leave -> create in the lobby"), NextAgainStep(EUmAgainStep::Leave, In), EUmAgainStep::Create);
  In.bLobby = false;
  In.bRoom = true;
  TestEqual(TEXT("create -> select in the new room"), NextAgainStep(EUmAgainStep::Create, In), EUmAgainStep::Select);
  TestEqual(TEXT("select waits for the hero"), NextAgainStep(EUmAgainStep::Select, In), EUmAgainStep::Select);
  In.bHeroPicked = true;
  TestEqual(TEXT("select -> ready"), NextAgainStep(EUmAgainStep::Select, In), EUmAgainStep::Ready);
  In.bReady = true;
  TestEqual(TEXT("ready -> start"), NextAgainStep(EUmAgainStep::Ready, In), EUmAgainStep::Start);
  In.bNewMatch = true;
  TestEqual(TEXT("start -> done"), NextAgainStep(EUmAgainStep::Start, In), EUmAgainStep::Done);
  FUmAgainInput Err;
  Err.bError = true;
  TestEqual(TEXT("an error fails"), NextAgainStep(EUmAgainStep::Create, Err), EUmAgainStep::Failed);
  FUmAgainInput Late;
  Late.bTimedOut = true;
  TestEqual(TEXT("a timeout fails"), NextAgainStep(EUmAgainStep::Ready, Late), EUmAgainStep::Failed);
  TestEqual(TEXT("0:27"), Duration(27), FString(TEXT("0:27")));
  TestEqual(TEXT("0:13"), Duration(13), FString(TEXT("0:13")));
  TestEqual(TEXT("1:02:03"), Duration(3723), FString(TEXT("1:02:03")));
  FUmGameOverModel M = RunIVictory();
  TestEqual(TEXT("victory"), FString(StateName(M)), FString(TEXT("victory")));
  M.bBoard = true;
  TestEqual(TEXT("board"), FString(StateName(M)), FString(TEXT("board")));
  M.bAgainBusy = true;
  TestEqual(TEXT("again"), FString(StateName(M)), FString(TEXT("again")));
  TestEqual(TEXT("L 760x580"), ModalSize(false, false), FVector2D(760.0, 580.0));
  TestEqual(TEXT("S 680x560"), ModalSize(true, false), FVector2D(680.0, 560.0));
  TestEqual(TEXT("S VS_AI 760x560 (ВР-VS5-SC37-06)"), ModalSize(true, true), FVector2D(760.0, 560.0));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensGameOverTreeTest, "Unmatched.S08.Hud.Screens.GameOver.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensGameOverTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmGameOverTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    UClass* Class = Pass == 0 ? UUmScreenGameOver::StaticClass() : UUmScreenGameOver::WidgetClass();
    if (Pass == 1 && Class == UUmScreenGameOver::StaticClass()) {
      AddInfo(TEXT("WBP_UI_SCR_GAMEOVER not authored yet - the code tree only"));
      continue;
    }
    UUmScreenGameOver* G = CreateWidget<UUmScreenGameOver>(W.World, Class);
    FString Missing;
    TestTrue(FString::Printf(TEXT("pass %d: every part (%s)"), Pass, *Missing), G && G->HasAllParts(&Missing));
    if (!G) continue;
    int32 Boards = 0, Lobbies = 0, Agains = 0;
    UUmScreenGameOver::FInput In;
    In.OnViewBoard = [&]() { ++Boards; };
    In.OnLobby = [&]() { ++Lobbies; };
    In.OnAgain = [&]() { ++Agains; };
    G->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
    G->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
    FUmGameOverModel M = RunIVictory();
    G->ApplyModel(M);
    G->SetViewAlphas(1.0f, 0.0f);
    TestEqual(TEXT("victory state"), G->GetScreenState(), FName(TEXT("victory")));
    TestEqual(TEXT("«ПОБЕДА»"), G->GetOutcomeText(), FString(TEXT("ПОБЕДА")));
    TestEqual(TEXT("headline by the winning hero"), G->GetHeadlineText(), FString(TEXT("MEDUSA ПОБЕЖДАЕТ")));
    TestEqual(TEXT("reason"), G->GetReasonText(), FString(TEXT("King Arthur: HP достигли 0")));
    TestEqual(TEXT("«Ход 11 · 0:27»"), G->GetTurnText(), FString(TEXT("Ход 11 · 0:27")));
    TestEqual(TEXT("left caption"), G->GetCaption(true), FString(TEXT("Вы · HP 11/16 · Победитель")));
    TestEqual(TEXT("right caption"), G->GetCaption(false), FString(TEXT("Соперник · HP 0/18 · Повержен")));
    TestTrue(TEXT("the fallen heart on the loser"), G->IsShownPart(G->RightHeart) && !G->IsShownPart(G->LeftHeart));
    TestFalse(TEXT("1x1: no «Сыграть ещё» (DE-039)"), G->IsShownPart(G->AgainButton));
    TestEqual(TEXT("one primary"), G->PrimaryCount(), 1);
    G->SimulatePress(FName(TEXT("screens.result.view.board")));
    G->SimulatePress(FName(TEXT("screens.result.lobby")));
    TestEqual(TEXT("view board press"), Boards, 1);
    TestEqual(TEXT("lobby press"), Lobbies, 1);
    // defeat: run I Sarpedon joiner (ВР-VS5-SC35-01)
    FUmGameOverModel D = RunIVictory();
    D.Outcome = EUmGameOverOutcome::Defeat;
    D.Turn = 5;
    D.DurationSec = 13;
    D.Left.Role = TEXT("Соперник");
    D.Left.Hp = 14;
    D.Right.Role = TEXT("Вы");
    G->ApplyModel(D);
    TestEqual(TEXT("defeat state"), G->GetScreenState(), FName(TEXT("defeat")));
    TestEqual(TEXT("«ПОРАЖЕНИЕ»"), G->GetOutcomeText(), FString(TEXT("ПОРАЖЕНИЕ")));
    TestEqual(TEXT("defeat turn"), G->GetTurnText(), FString(TEXT("Ход 5 · 0:13")));
    TestEqual(TEXT("defeat: the winner left"), G->GetCaption(true), FString(TEXT("Соперник · HP 14/16 · Победитель")));
    // draw: no headline, reason or turn; both fallen
    FUmGameOverModel Dr = RunIVictory();
    Dr.Outcome = EUmGameOverOutcome::Draw;
    Dr.Left.bWinner = false;
    Dr.Left.bFallen = true;
    Dr.Left.Hp = Dr.Right.Hp = -1;
    G->ApplyModel(Dr);
    TestEqual(TEXT("draw state"), G->GetScreenState(), FName(TEXT("draw")));
    TestEqual(TEXT("«ВЗАИМНОЕ УНИЧТОЖЕНИЕ»"), G->GetOutcomeText(), FString(TEXT("ВЗАИМНОЕ УНИЧТОЖЕНИЕ")));
    TestTrue(TEXT("draw: no headline / reason / turn"), G->GetHeadlineText().IsEmpty() && G->GetReasonText().IsEmpty() && G->GetTurnText().IsEmpty());
    TestEqual(TEXT("draw caption"), G->GetCaption(true), FString(TEXT("Вы · Повержен")));
    // VS_AI: «Сыграть ещё», busy
    FUmGameOverModel A = RunIVictory();
    A.bVsAi = true;
    A.Right.HeroName = TEXT("T. Rex");
    A.Right.HeroKey = FName(TEXT("t-rex"));
    A.Right.Role = TEXT("AI Bot");
    G->ApplyModel(A);
    TestTrue(TEXT("VS_AI: «Сыграть ещё»"), G->IsShownPart(G->AgainButton));
    TestEqual(TEXT("VS_AI: one primary («В лобби»)"), G->PrimaryCount(), 1);
    G->SimulatePress(FName(TEXT("screens.result.again")));
    TestEqual(TEXT("again press"), Agains, 1);
    A.bAgainBusy = true;
    G->ApplyModel(A);
    TestEqual(TEXT("again state"), G->GetScreenState(), FName(TEXT("again")));
    TestTrue(TEXT("busy label"), G->AgainButton->GetModel().Label.ToString() == TEXT("Создаём партию…"));
    G->SimulatePress(FName(TEXT("screens.result.again")));
    TestEqual(TEXT("busy: no second press"), Agains, 1);
    // board view: the strip, state board, x FIELD 0
    FUmGameOverModel B = RunIVictory();
    B.bBoard = true;
    const FBox2D Field(FVector2D(410.0, 255.0), FVector2D(1440.0, 850.0));  // 04 §1.6 Marmoreal FIELD at 1080p
    G->SetFieldSu(&Field);
    G->ApplyModel(B);
    G->SetViewAlphas(0.0f, 1.0f);
    TestEqual(TEXT("board state"), G->GetScreenState(), FName(TEXT("board")));
    TestEqual(TEXT("strip text"), G->GetStripText(), FString(TEXT("ХОД 11 · ПОБЕДА")));
    TestTrue(TEXT("strip shown, modal gone"), G->IsShownPart(G->BoardStrip) && !G->IsShownPart(G->ResultModal));
    TestEqual(TEXT("board: one primary"), G->PrimaryCount(), 1);
    TestEqual(TEXT("strip x FIELD 0 px²"), G->StripOverlapFieldPx2(), 0.0);
    G->SimulatePress(FName(TEXT("screens.result.view.results")));
    TestEqual(TEXT("back to the results"), Boards, 2);
    TArray<FString> Lines;
    G->CollectShotLines(Lines);
    TestTrue(TEXT("SHOT line state=board"), Lines.Num() == 1 && Lines[0].Contains(TEXT("id=UI-SCR-GAMEOVER")) && Lines[0].Contains(TEXT("state=board")));
    // every canvas: the modal and the strip inside
    for (int32 C = 0; C < 3; ++C) {
      G->ApplyCanvas(Canvases[C], ClassS[C], 1.0f);
      G->ApplyModel(A);
      TestTrue(FString::Printf(TEXT("modal inside canvas %d"), C), Inside(G->ModalRectSu(), Canvases[C]));
      TestTrue(FString::Printf(TEXT("strip inside canvas %d"), C), Inside(G->StripRectSu(), Canvases[C]));
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensAbortedTreeTest, "Unmatched.S08.Hud.Screens.Aborted.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensAbortedTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmAbortedTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    UClass* Class = Pass == 0 ? UUmScreenAborted::StaticClass() : UUmScreenAborted::WidgetClass();
    if (Pass == 1 && Class == UUmScreenAborted::StaticClass()) {
      AddInfo(TEXT("WBP_UI_SCR_ABORTED not authored yet - the code tree only"));
      continue;
    }
    UUmScreenAborted* A = CreateWidget<UUmScreenAborted>(W.World, Class);
    FString Missing;
    TestTrue(FString::Printf(TEXT("pass %d: every part (%s)"), Pass, *Missing), A && A->HasAllParts(&Missing));
    if (!A) continue;
    int32 Lobbies = 0;
    UUmScreenAborted::FInput In;
    In.OnLobby = [&]() { ++Lobbies; };
    A->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
    A->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
    A->PlayShow();
    FUmAbortedModel M;
    M.Turn = 1;  // ВР-VS5-SC38-01: the real ONE_V_ONE row, turnCount 1
    A->ApplyModel(M);
    TestEqual(TEXT("state shown"), A->GetScreenState(), FName(TEXT("shown")));
    TestEqual(TEXT("«Партия прервана»"), A->GetTitleText(), FString(TEXT("Партия прервана")));
    TestEqual(TEXT("no leaver: «Соперник покинул партию» (ВР-SC13)"), A->GetWhoText(), FString(TEXT("Соперник покинул партию")));
    TestEqual(TEXT("«Ход 1»"), A->GetTurnText(), FString(TEXT("Ход 1")));
    TestTrue(TEXT("«В лобби» the one primary"), A->IsLobbyPrimary());
    TestFalse(TEXT("no victory word"), A->GetTitleText().Contains(TEXT("ПОБЕДА")) || A->GetTitleText().Contains(TEXT("ПОРАЖЕНИЕ")));
    M.Leaver = TEXT("Veteran");
    A->ApplyModel(M);
    TestEqual(TEXT("named leaver"), A->GetWhoText(), FString(TEXT("Игрок Veteran покинул партию")));
    A->SimulatePress(FName(TEXT("screens.aborted.lobby")));
    TestEqual(TEXT("lobby press"), Lobbies, 1);
    for (int32 C = 0; C < 3; ++C) {
      A->ApplyCanvas(Canvases[C], ClassS[C], 1.0f);
      TestTrue(FString::Printf(TEXT("modal inside canvas %d"), C), Inside(A->FrameRectSu(), Canvases[C]));
    }
    TArray<FString> Lines;
    A->CollectShotLines(Lines);
    TestTrue(TEXT("SHOT line UI-SCR-ABORTED state=shown"), Lines.Num() == 1 && Lines[0].Contains(TEXT("id=UI-SCR-ABORTED")) && Lines[0].Contains(TEXT("state=shown")));
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
