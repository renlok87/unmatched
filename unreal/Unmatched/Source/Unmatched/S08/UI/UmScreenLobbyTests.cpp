// VS-7 S2 automation tests (docs/game-design/visual/06-tasks/screens.csv SC-08...SC-13; 04-hud-spec.md §1.3):
//   Unmatched.S08.Hud.Screens.Lobby.Tree   LOBBY's parts from the code tree and from WBP_UI_SCR_LOBBY; RU texts; loading ->
//                                          list (pooled rows: a second answer builds none) -> a refused row explains
//                                          itself -> empty -> error («Повторить», no «Обновить»); create: Marmoreal by
//                                          default, Sarpedon, the AI note «Соперник — ИИ: AI Bot», busy «Создаём…», a double
//                                          press creates once; code: «Войти» disabled below six characters
//                                          (why.code.length), primary at six (Create normal), an error keeps the code;
//                                          class S stays inside the canvas; the SHOT line carries no code.
//   Unmatched.S08.Hud.Screens.Lobby.Poll   ВР-H20 / SC-13 timing: the first request, nothing before 15 s, the 15 s poll,
//                                          «Обновить» at once, the window focus regained, the 10 s timeout; the code
//                                          normalisation; the server answers -> the code / row reasons.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Screens" <abs log>
#if WITH_AUTOMATION_TESTS

#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "UmBoardChip.h"
#include "UmButton.h"
#include "UmScreenLobby.h"

namespace UmLobbyTest {
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

// rows shaped like the S09 stand capture of CX-29 (inputs/available-games.json): codes there, test copies here
FUmLobbyRowModel Row(const TCHAR* Id, const TCHAR* Code, const TCHAR* Board, bool bHero) {
  FUmLobbyRowModel M;
  M.GameId = Id;
  M.Code = Code;
  M.Mode = FText::FromString(TEXT("1×1"));
  M.Board = Board;
  M.Seats = 1;
  if (bHero) {
    M.HeroKeys.Add(FName(TEXT("king-arthur")));
    M.HeroNames.Add(TEXT("King Arthur"));
  }
  return M;
}
}  // namespace UmLobbyTest

using namespace UmLobbyTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensLobbyTreeTest, "Unmatched.S08.Hud.Screens.Lobby.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensLobbyTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmLobbyTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    UClass* Class = Pass == 0 ? UUmScreenLobby::StaticClass() : UUmScreenLobby::WidgetClass();
    if (Pass == 1 && Class == UUmScreenLobby::StaticClass()) {
      AddInfo(TEXT("WBP_UI_SCR_LOBBY not authored yet - the code tree only"));
      continue;
    }
    UUmScreenLobby* L = CreateWidget<UUmScreenLobby>(W.World, Class);
    FString Missing;
    TestTrue(FString::Printf(TEXT("pass %d: every part (%s)"), Pass, *Missing), L && L->HasAllParts(&Missing));
    if (!L) continue;
    int32 Creates = 0, Joins = 0, CodeJoins = 0, Refreshes = 0;
    FString LastBoard, LastGame;
    EUmLobbyMode LastMode = EUmLobbyMode::OneVOne;
    UUmScreenLobby::FInput In;
    In.OnCreate = [&](EUmLobbyMode M, const FString& B) {
      ++Creates;
      LastMode = M;
      LastBoard = B;
    };
    In.OnJoinRow = [&](const FString& G) {
      ++Joins;
      LastGame = G;
    };
    In.OnJoinCode = [&](const FString&) { ++CodeJoins; };
    In.OnRefresh = [&]() { ++Refreshes; };
    L->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
    L->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
    L->PlayShow();
    L->OnShown();
    // ---- SC-08 loading -> list
    L->SetList(EUmLobbyList::Loading, {});
    TestEqual(TEXT("loading"), L->GetScreenState(), FName(TEXT("loading")));
    TestEqual(TEXT("«Список игр»"), L->ListTitle->GetText().ToString(), FString(TEXT("Список игр")));
    TArray<FUmLobbyRowModel> Rows = {Row(TEXT("g1"), TEXT("AB12CD"), TEXT("Marmoreal · original map"), true),
                                     Row(TEXT("g2"), TEXT("EF34GH"), TEXT("Sarpedon · original map"), false)};
    L->SetList(EUmLobbyList::List, Rows);
    TestEqual(TEXT("list"), L->GetScreenState(), FName(TEXT("list")));
    TestEqual(TEXT("two rows"), L->GetRowCount(), 2);
    TestEqual(TEXT("row 1 code"), L->GetRow(0) ? L->GetRow(0)->Code->GetText().ToString() : FString(), FString(TEXT("AB12CD")));
    TestEqual(TEXT("row 1 seats «1/2»"), L->GetRow(0) ? L->GetRow(0)->Seats->GetText().ToString() : FString(), FString(TEXT("1/2")));
    TestEqual(TEXT("row 1: one hero disc"), L->GetRow(0) ? L->GetRow(0)->GetDiscCount() : -1, 1);
    TestEqual(TEXT("row 2: no disc without a hero"), L->GetRow(1) ? L->GetRow(1)->GetDiscCount() : -1, 0);
    const int32 Built = L->GetRowsBuilt();
    L->SetList(EUmLobbyList::List, Rows);  // the next 15 s answer: same rows
    TestEqual(TEXT("a poll recreates no row (pool)"), L->GetRowsBuilt(), Built);
    // a joinGame of a row
    L->SimulatePress(FName(TEXT("screens.lobby.row.join.1")));
    TestTrue(TEXT("row 2 join -> its game id"), Joins == 1 && LastGame == TEXT("g2"));
    L->MarkRowUnavailable(TEXT("g2"), FName(TEXT("why.room.full")));
    TestTrue(TEXT("refused row: no button, the why text"),
             L->GetRow(1) && !L->GetRow(1)->IsAvailable() && L->GetRow(1)->WhyText->GetText().ToString() == TEXT("Комната заполнена") &&
                 L->GetRow(1)->JoinButton->GetVisibility() == ESlateVisibility::Collapsed);
    L->SetList(EUmLobbyList::List, Rows);
    TestTrue(TEXT("the why stays while the row is listed"), L->GetRow(1) && !L->GetRow(1)->IsAvailable());
    L->SetList(EUmLobbyList::List, {Rows[0]});
    TestEqual(TEXT("the next poll drops the row"), L->GetRowCount(), 1);
    // ---- SC-12 / SC-13
    L->SetList(EUmLobbyList::Empty, {});
    TestEqual(TEXT("empty"), L->GetScreenState(), FName(TEXT("empty")));
    TestEqual(TEXT("empty text"), L->GetEmptyText(), FString(TEXT("Сейчас открытых игр нет. Создайте комнату и передайте код другу")));
    L->SetList(EUmLobbyList::Error, {});
    TestEqual(TEXT("error"), L->GetScreenState(), FName(TEXT("error")));
    TestEqual(TEXT("error text"), L->GetListErrorText(), FString(TEXT("Не удалось загрузить список игр")));
    TestTrue(TEXT("error: «Повторить» shown, «Обновить» hidden"),
             L->RetryButton->GetVisibility() != ESlateVisibility::Collapsed && L->RefreshButton->GetVisibility() == ESlateVisibility::Collapsed);
    TestTrue(TEXT("error: «Создать» is the only primary"), L->IsCreatePrimary() && !L->IsCodeJoinPrimary());
    L->SimulatePress(FName(TEXT("common.btn.retry")));
    TestEqual(TEXT("«Повторить» asks again"), Refreshes, 1);
    // ---- SC-09 / SC-10 create
    TestEqual(TEXT("Marmoreal by default"), L->GetBoardId(), FString(UmLobby::MarmorealId));
    TestTrue(TEXT("exactly two boards, Marmoreal selected"),
             L->GetBoardChip(0) && L->GetBoardChip(1) && !L->GetBoardChip(2) && L->GetBoardChip(0)->IsSelected() && !L->GetBoardChip(1)->IsSelected());
    TestEqual(TEXT("board names"), L->GetBoardChip(1) ? L->GetBoardChip(1)->GetNameText() : FString(), FString(UmLobby::SarpedonName));
    L->SimulatePress(FName(TEXT("screens.lobby.board.1")));
    TestTrue(TEXT("Sarpedon selected"), L->GetBoardId() == UmLobby::SarpedonId && L->GetBoardChip(1)->IsSelected());
    TestEqual(TEXT("create"), L->GetScreenState(), FName(TEXT("create")));
    TestEqual(TEXT("no AI note in 1v1"), L->GetNoteText(), FString());
    L->SimulatePress(FName(TEXT("screens.lobby.create.mode.ai")));
    TestEqual(TEXT("AI note (seed-ai.ts:24)"), L->GetNoteText(), FString(TEXT("Соперник — ИИ: AI Bot")));
    L->SimulatePress(FName(TEXT("screens.lobby.create.submit")));
    L->SimulatePress(FName(TEXT("screens.lobby.create.submit")));  // a double click
    TestTrue(TEXT("one create, VS_AI on Sarpedon"), Creates == 1 && LastMode == EUmLobbyMode::VsAi && LastBoard == UmLobby::SarpedonId);
    TestTrue(TEXT("busy «Создаём…», disabled with why.syncing"),
             L->IsCreateBusy() && L->GetCreateLabel() == TEXT("Создаём…") && !L->CreateButton->GetModel().bEnabled &&
                 L->CreateButton->GetModel().Reason.Key == FName(TEXT("why.syncing")));
    L->SimulatePress(FName(TEXT("screens.lobby.board.0")));  // a tile press while busy waits
    TestTrue(TEXT("busy keeps the mode and the board look (ВР-VS4-SC09-01)"),
             L->GetBoardId() == UmLobby::SarpedonId && L->GetBoardChip(1)->Button->GetModel().bSelected &&
                 L->GetBoardChip(1)->Button->GetModel().bEnabled && L->ModeChipAi->GetModel().bSelected && L->ModeChipAi->GetModel().bEnabled);
    L->ShowCreateError();
    TestTrue(TEXT("create error ends busy"), !L->IsCreateBusy());
    L->SimulatePress(FName(TEXT("screens.lobby.create.mode.1v1")));
    // ---- SC-11 code
    L->SetCodeText(TEXT("ab1"), true);
    TestEqual(TEXT("upper case"), L->GetCode(), FString(TEXT("AB1")));
    TestTrue(TEXT("3 chars: «Войти» disabled with why.code.length"),
             !L->IsCodeJoinEnabled() && L->CodeJoinButton->GetModel().Reason.Key == FName(TEXT("why.code.length")));
    TestTrue(TEXT("3 chars: «Создать» primary"), L->IsCreatePrimary() && !L->IsCodeJoinPrimary());
    TestEqual(TEXT("code"), L->GetScreenState(), FName(TEXT("code")));
    L->SetCodeText(TEXT("ab12-cd9"), true);
    TestEqual(TEXT("six of A-Z 0-9"), L->GetCode(), FString(TEXT("AB12CD")));
    TestTrue(TEXT("6 chars: «Войти» primary, «Создать» normal"), L->IsCodeJoinEnabled() && L->IsCodeJoinPrimary() && !L->IsCreatePrimary());
    L->SimulatePress(FName(TEXT("screens.lobby.code.submit")));
    TestEqual(TEXT("one code join"), CodeJoins, 1);
    L->ShowCodeError(EUmCodeError::NotFound);
    TestEqual(TEXT("code-error"), L->GetScreenState(), FName(TEXT("code-error")));
    TestEqual(TEXT("«Игра не найдена»"), L->GetCodeErrorText(), FString(TEXT("Игра не найдена")));
    TestEqual(TEXT("the code is kept"), L->GetCode(), FString(TEXT("AB12CD")));
    L->ShowCodeError(EUmCodeError::Full);
    TestEqual(TEXT("«Комната заполнена»"), L->GetCodeErrorText(), FString(TEXT("Комната заполнена")));
    // the SHOT line never carries the code
    TArray<FString> Lines;
    L->CollectShotLines(Lines);
    TestTrue(TEXT("SHOT UI-SCR-LOBBY state=code-error"), Lines.Num() == 1 && Lines[0].Contains(TEXT("id=UI-SCR-LOBBY")) &&
                                                            Lines[0].Contains(TEXT("state=code-error")) && Lines[0].Contains(TEXT("code=6")));
    TestTrue(TEXT("no code in the line"), Lines.Num() == 1 && !Lines[0].Contains(TEXT("AB12CD")));
    // class S (720p 150 %): the panels stay inside the canvas
    L->ApplyCanvas(FVector2D(1137.78, 640.0), true, 0.75f * 1.5f);
    const FUmLobbyLayout S = UmLobby::Layout(FVector2D(1137.78, 640.0), true);
    TestTrue(TEXT("class S inside the canvas"), S.Code.Y + S.Code.H <= 640.0f - 15.9f && S.Create.X + S.Create.W <= 1137.78f - 15.9f &&
                                                    S.List.X + S.List.W < S.Create.X);
    const FUmLobbyLayout Lw = UmLobby::Layout(FVector2D(1920.0, 1080.0), false);
    TestTrue(TEXT("04 §1.3 rects at 1080p"), Lw.List.W == 1176.0f && Lw.List.H == 944.0f && Lw.Create.X == 1224.0f && Lw.Code.Y == 648.0f);
    const FUmLobbyLayout L7 = UmLobby::Layout(FVector2D(1706.67, 960.0), false);
    TestTrue(TEXT("04 §1.3 rects at 720p"), FMath::IsNearlyEqual(L7.Create.W, 568.0f) && FMath::IsNearlyEqual(L7.Code.Y, 628.0f) &&
                                                FMath::IsNearlyEqual(L7.List.H, 824.0f));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensLobbyPollTest, "Unmatched.S08.Hud.Screens.Lobby.Poll",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensLobbyPollTest::RunTest(const FString& Parameters) {
  UmLobby::FUmLobbyPoll P;
  TestTrue(TEXT("entry: ask at once"), P.Due(0.0, true));
  P.Sent(0.0);
  TestFalse(TEXT("in flight: no second request"), P.Due(500.0, true));
  P.Answered();
  TestFalse(TEXT("5 s: no request"), P.Due(5000.0, true));
  TestTrue(TEXT("15 s: the poll (a room created by another client shows within 15 s)"), P.Due(15000.0, true));
  P.Sent(15000.0);
  P.Answered();
  P.bForce = true;
  TestTrue(TEXT("«Обновить»: at once"), P.Due(16000.0, true));
  P.Sent(16000.0);
  P.Answered();
  TestFalse(TEXT("focus lost: nothing"), P.Due(17000.0, false));
  TestTrue(TEXT("focus regained: at once (ВР-H20)"), P.Due(18000.0, true));
  P.Sent(18000.0);
  TestFalse(TEXT("9.9 s without an answer: no error yet"), P.TimedOut(27900.0));
  TestTrue(TEXT("10 s without an answer: the error (SC-13)"), P.TimedOut(28000.0));
  TestFalse(TEXT("after the timeout the next poll waits for its 15 s"), P.Due(29000.0, true));
  TestTrue(TEXT("... and goes at 15 s"), P.Due(33000.0, true));
  // the code and the server answers
  TestEqual(TEXT("normalised"), UmLobby::NormalizeCode(TEXT(" vz-sj ft9")), FString(TEXT("VZSJFT")));
  TestTrue(TEXT("NOT_FOUND -> notfound"),
           UmLobby::ClassifyCodeError(TEXT("NOT_FOUND"), TEXT("Room code not found or no longer joinable")) == EUmCodeError::NotFound);
  TestTrue(TEXT("«Игра уже заполнена» -> full"), UmLobby::ClassifyCodeError(TEXT("BAD_REQUEST"), TEXT("Игра уже заполнена")) == EUmCodeError::Full);
  TestEqual(TEXT("row: full"), UmLobby::RowWhy(TEXT("BAD_REQUEST"), TEXT("Игра уже заполнена")), FName(TEXT("why.room.full")));
  TestEqual(TEXT("row: started"),
            UmLobby::RowWhy(TEXT("BAD_REQUEST"), TEXT("Нельзя присоединиться к игре, которая уже началась или завершилась")),
            FName(TEXT("why.room.started")));
  TestEqual(TEXT("state order"), FString(UmLobby::StateName(EUmLobbyList::List, true, 3, EUmCodeError::None)), FString(TEXT("code")));
  // the board tile keeps the map's aspect
  const FBox2D Img = UmBoardChip::ImageRect(FVector2D(312.0, 232.0), FVector2D(1337.0, 866.0));
  TestTrue(TEXT("thumbnail aspect kept, inside the tile"),
           FMath::IsNearlyEqual(Img.GetSize().X / Img.GetSize().Y, 1337.0 / 866.0, 0.01) && Img.Min.X >= 8.0 && Img.Max.Y <= 232.0 - 8.0 - 28.0 + 0.01);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
