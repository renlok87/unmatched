// VS-7 S3 automation tests (docs/game-design/visual/06-tasks/screens.csv SC-14...SC-20; 04-hud-spec.md §1.4, §1.5):
//   Unmatched.S08.Hud.Screens.Room.Tree     ROOM's parts from the code tree and from WBP_UI_SCR_ROOM; RU texts; the host
//                                           waiting (Start disabled with why.room.no.hero, the deck row only the disabled
//                                           button) -> picked (Medusa: edge + «Выбрано», «Колода: 30 карт», Start disabled
//                                           with why.room.not.ready) -> ready (Start the one primary) ; the guest: Medusa
//                                           taken (no button, «Выбран соперником»), the ready toggle the primary, a toggle
//                                           that is on is never primary; VS_AI: slot 2 «ИИ-соперник · AI Bot»; the board
//                                           block (the room board marked + ✓, the other locked); the countdown 3 -> «Партия
//                                           начинается…»; class S stays inside the canvas; the SHOT lines carry no code.
//   Unmatched.S08.Hud.Screens.Room.Model    the pure rules: StateName, StartWhy, ReadyWhy, CountDigit (1000 ms steps),
//                                           ClampLines (3 lines + «…»), the sidekick line.
//   Unmatched.S08.Hud.Screens.Loading.Tree  LOADING's parts (code tree, WBP_UI_SCR_LOADING); connect / state / board captions,
//                                           the spinner slot, «против», the board name; error: the icon instead of the
//                                           spinner, «В лобби» normal + «Повторить» the one primary, the presses; the panel
//                                           inside every canvas (1080p, 720p, 720p 150 %).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Screens" <abs log>
#if WITH_AUTOMATION_TESTS

#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "UmBoardCard.h"
#include "UmButton.h"
#include "UmHeroCard.h"
#include "UmRoomSlot.h"
#include "UmScreenLoading.h"
#include "UmScreenRoom.h"

namespace UmRoomTest {
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

// the adminHero answers of the S09 stand (sc14-room-hero-codex inputs/heroes.json): the values, test copies here
FUmHeroCardModel Arthur() {
  FUmHeroCardModel C;
  C.HeroId = TEXT("h-arthur");
  C.Name = TEXT("King Arthur");
  C.Key = FName(TEXT("king-arthur"));
  C.bDetails = true;
  C.Hp = 18;
  C.Move = 2;
  C.AttackType = TEXT("melee");
  C.SidekickName = TEXT("Merlin");
  C.SidekickKey = FName(TEXT("king-arthur/merlin"));
  C.SidekickCount = 1;
  C.SidekickHp = 7;
  C.SidekickAttack = TEXT("range");
  C.Ability = TEXT("When King Arthur attacks, you may BOOST that attack, Play the BOOST card, face down, along with your attack card. ")
              TEXT("If your opponent cancels the effects on your attack card, the BOOST is discarded without effect.");
  return C;
}

FUmHeroCardModel Medusa() {
  FUmHeroCardModel C;
  C.HeroId = TEXT("h-medusa");
  C.Name = TEXT("Medusa");
  C.Key = FName(TEXT("medusa"));
  C.bDetails = true;
  C.Hp = 16;
  C.Move = 3;
  C.AttackType = TEXT("range");
  C.SidekickName = TEXT("Harpies");
  C.SidekickKey = FName(TEXT("medusa/harpies"));
  C.SidekickCount = 3;
  C.SidekickHp = 1;
  C.SidekickAttack = TEXT("melee");
  C.Ability = TEXT("At the start of your turn, you may deal 1 damage to an opposing fighter in Medusa's zone.");
  return C;
}

FUmRoomSlotModel Seat(const TCHAR* User, bool bHost, bool bReady, const TCHAR* Hero = nullptr) {
  FUmRoomSlotModel S;
  S.Seat = EUmRoomSeat::Player;
  S.Username = User;
  S.bHost = bHost;
  S.bReady = bReady;
  if (Hero) {
    S.HeroName = Hero;
    S.HeroKey = FName(*FString(Hero).ToLower().Replace(TEXT(" "), TEXT("-")));
    S.bDetails = true;
    S.Hp = FString(Hero) == TEXT("Medusa") ? 16 : 18;
    S.Move = FString(Hero) == TEXT("Medusa") ? 3 : 2;
    S.SidekickName = FString(Hero) == TEXT("Medusa") ? TEXT("Harpies") : TEXT("Merlin");
    S.SidekickCount = FString(Hero) == TEXT("Medusa") ? 3 : 1;
    S.SidekickHp = FString(Hero) == TEXT("Medusa") ? 1 : 7;
  }
  return S;
}

FUmRoomModel Base(bool bHost) {
  FUmRoomModel M;
  M.Code = TEXT("AB12CD");
  M.bHost = bHost;
  M.BoardId = UmLobby::MarmorealId;
  M.BoardNames[0] = UmLobby::MarmorealName;
  M.BoardNames[1] = UmLobby::SarpedonName;
  M.Slots[0] = Seat(TEXT("ProGamer"), true, false);
  M.Slots[1] = Seat(TEXT("Veteran"), false, false);
  M.Heroes = {Arthur(), Medusa()};
  M.bOppPresent = true;
  return M;
}
}  // namespace UmRoomTest

using namespace UmRoomTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensRoomModelTest, "Unmatched.S08.Hud.Screens.Room.Model",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensRoomModelTest::RunTest(const FString& Parameters) {
  FUmRoomModel M = Base(true);
  TestEqual(TEXT("no hero: waiting"), FString(UmRoom::StateName(EUmRoomPhase::Room, M)), FString(TEXT("waiting")));
  TestEqual(TEXT("no hero: Start why.room.no.hero"), UmRoom::StartWhy(M), FName(TEXT("why.room.no.hero")));
  TestEqual(TEXT("no hero: Ready why.room.no.hero"), UmRoom::ReadyWhy(M), FName(TEXT("why.room.no.hero")));
  M.OwnHeroId = TEXT("h-medusa");
  TestEqual(TEXT("hero: picked"), FString(UmRoom::StateName(EUmRoomPhase::Room, M)), FString(TEXT("picked")));
  TestEqual(TEXT("hero, not ready: why.room.not.ready"), UmRoom::StartWhy(M), FName(TEXT("why.room.not.ready")));
  TestTrue(TEXT("hero: Ready open"), UmRoom::ReadyWhy(M).IsNone());
  M.bOwnReady = true;
  M.bOppHero = true;
  TestEqual(TEXT("opponent not ready: why.room.not.ready"), UmRoom::StartWhy(M), FName(TEXT("why.room.not.ready")));
  M.bOppReady = true;
  TestTrue(TEXT("both ready: Start open"), UmRoom::StartWhy(M).IsNone());
  TestEqual(TEXT("both ready: ready"), FString(UmRoom::StateName(EUmRoomPhase::Room, M)), FString(TEXT("ready")));
  TestEqual(TEXT("countdown wins"), FString(UmRoom::StateName(EUmRoomPhase::Countdown, M)), FString(TEXT("countdown")));
  FUmRoomModel Ai = Base(true);
  Ai.bVsAi = true;
  Ai.OwnHeroId = TEXT("h-arthur");
  TestEqual(TEXT("VS_AI before the own ready: why.room.not.ready"), UmRoom::StartWhy(Ai), FName(TEXT("why.room.not.ready")));
  Ai.bOwnReady = true;
  TestTrue(TEXT("VS_AI: Start after the own ready"), UmRoom::StartWhy(Ai).IsNone());
  // SC-18: 3-2-1 by 1000 ms
  TestEqual(TEXT("0 ms -> 3"), UmRoom::CountDigit(0.0), 3);
  TestEqual(TEXT("999 ms -> 3"), UmRoom::CountDigit(999.0), 3);
  TestEqual(TEXT("1000 ms -> 2"), UmRoom::CountDigit(1000.0), 2);
  TestEqual(TEXT("2500 ms -> 1"), UmRoom::CountDigit(2500.0), 1);
  TestEqual(TEXT("3000 ms -> over"), UmRoom::CountDigit(3000.0), 0);
  // the ability: at most 3 lines and «…»
  const FString Long = Arthur().Ability;
  const FString Three = UmRoomUi::ClampLines(Long, TEXT("type.caption"), 200.0f, 3);
  TArray<FString> Lines;
  Three.ParseIntoArray(Lines, TEXT("\n"));
  TestTrue(TEXT("<= 3 lines"), Lines.Num() <= 3 && Lines.Num() > 0);
  TestTrue(TEXT("ends with «…»"), Three.EndsWith(TEXT("…")));
  TestEqual(TEXT("short text unchanged"), UmRoomUi::ClampLines(TEXT("a b"), TEXT("type.caption"), 500.0f, 3), FString(TEXT("a b")));
  TestEqual(TEXT("sidekick line ×3"), UmRoomUi::SidekickLine(TEXT("Harpies"), 3, 1, FString(), false), FString(TEXT("Harpies ×3 · HP 1")));
  TestEqual(TEXT("sidekick line single"), UmRoomUi::SidekickLine(TEXT("Merlin"), 1, 7, FString(), false), FString(TEXT("Merlin · HP 7")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensRoomTreeTest, "Unmatched.S08.Hud.Screens.Room.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensRoomTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmRoomTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    UClass* Class = Pass == 0 ? UUmScreenRoom::StaticClass() : UUmScreenRoom::WidgetClass();
    if (Pass == 1 && Class == UUmScreenRoom::StaticClass()) {
      AddInfo(TEXT("WBP_UI_SCR_ROOM not authored yet - the code tree only"));
      continue;
    }
    UUmScreenRoom* R = CreateWidget<UUmScreenRoom>(W.World, Class);
    FString Missing;
    TestTrue(FString::Printf(TEXT("pass %d: every part (%s)"), Pass, *Missing), R && R->HasAllParts(&Missing));
    if (!R) continue;
    FString Picked;
    int32 Readies = 0, Starts = 0, Leaves = 0, Decks = 0;
    UUmScreenRoom::FInput In;
    In.OnPick = [&](const FString& Id) { Picked = Id; };
    In.OnReady = [&]() { ++Readies; };
    In.OnStart = [&]() { ++Starts; };
    In.OnLeave = [&]() { ++Leaves; };
    In.OnDeck = [&]() { ++Decks; };
    R->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
    R->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
    R->PlayShow();
    // ---- SC-14 waiting (host)
    FUmRoomModel M = Base(true);
    R->ApplyModel(M);
    TestEqual(TEXT("waiting"), R->GetScreenState(), FName(TEXT("waiting")));
    TestTrue(TEXT("title «Комната · код …»"), R->GetTitleText().StartsWith(TEXT("Комната · код ")));
    TestEqual(TEXT("two hero cards"), R->GetHeroCount(), 2);
    UUmHeroCard* A = R->GetHeroCard(0);
    UUmHeroCard* Md = R->GetHeroCard(1);
    if (TestNotNull(TEXT("King Arthur card"), A)) {
      TestEqual(TEXT("«HP 18 · ход 2»"), A->GetStatsText(), FString(TEXT("HP 18 · ход 2")));
      TestEqual(TEXT("«ближний бой»"), A->GetAttackText(), FString(TEXT("ближний бой")));
      TestEqual(TEXT("Merlin line"), A->GetSidekickText(), FString(TEXT("Merlin · HP 7 · дальний\u00A0бой")));
      TestTrue(TEXT("ability clamped"), A->GetAbilityText().Len() > 0 && A->GetAbilityText().Len() <= Arthur().Ability.Len() + 3);
    }
    if (TestNotNull(TEXT("Medusa card"), Md)) {
      TestEqual(TEXT("«HP 16 · ход 3»"), Md->GetStatsText(), FString(TEXT("HP 16 · ход 3")));
      TestEqual(TEXT("«дальний бой»"), Md->GetAttackText(), FString(TEXT("дальний бой")));
      TestEqual(TEXT("Harpies ×3"), Md->GetSidekickText(), FString(TEXT("Harpies ×3 · HP 1 · ближний\u00A0бой")));
    }
    TestFalse(TEXT("Start disabled"), R->IsStartEnabled());
    TestTrue(TEXT("Start the host's primary"), R->IsStartPrimary());
    TestEqual(TEXT("one primary"), R->PrimaryCount(), 1);
    TestEqual(TEXT("why «Выберите героя»"), R->GetWhyText(), FString(TEXT("Выберите героя")));
    TestTrue(TEXT("no deck count without a hero"), R->GetDeckText().IsEmpty());
    TestFalse(TEXT("deck button disabled"), R->IsDeckEnabled());
    TestEqual(TEXT("deck why"), R->GetDeckWhyText(), FString(TEXT("Выберите героя")));
    // pick Medusa
    R->SimulatePress(FName(TEXT("screens.room.hero.pick.1")));
    TestEqual(TEXT("pick sends Medusa"), Picked, FString(TEXT("h-medusa")));
    // ---- picked (the server answered)
    M.OwnHeroId = TEXT("h-medusa");
    M.Heroes[1].State = EUmHeroCardState::Picked;
    M.Slots[0] = Seat(TEXT("ProGamer"), true, false, TEXT("Medusa"));
    M.DeckCount = 30;
    R->ApplyModel(M);
    TestEqual(TEXT("picked"), R->GetScreenState(), FName(TEXT("picked")));
    TestEqual(TEXT("«Колода: 30 карт»"), R->GetDeckText(), FString(TEXT("Колода: 30 карт")));
    TestTrue(TEXT("deck button enabled"), R->IsDeckEnabled());
    R->SimulatePress(FName(TEXT("screens.room.deck.view")));
    TestEqual(TEXT("deck pressed"), Decks, 1);
    TestEqual(TEXT("why «Соперник не готов»"), R->GetWhyText(), FString(TEXT("Соперник не готов")));
    if (UUmRoomSlot* S0 = R->GetSlot(0)) {
      TestEqual(TEXT("slot 1 name"), S0->GetNameText(), FString(TEXT("ProGamer")));
      TestEqual(TEXT("slot 1 hero line"), S0->GetHeroLine(), FString(TEXT("Medusa · HP 16 · ход 3")));
      TestEqual(TEXT("slot 1 sidekick line"), S0->GetSidekickLine(), FString(TEXT("+ Harpies ×3 · HP 1")));
      TestEqual(TEXT("slot 1 «Не готов»"), S0->GetReadyText(), FString(TEXT("Не готов")));
      TestFalse(TEXT("no ✓ when not ready"), S0->IsReadyGlyphShown());
    }
    if (UUmRoomSlot* S1 = R->GetSlot(1)) TestEqual(TEXT("slot 2 «Герой не выбран»"), S1->GetHeroLine(), FString(TEXT("Герой не выбран")));
    // ---- ready (both)
    M.bOwnReady = true;
    M.bOppHero = true;
    M.bOppReady = true;
    M.Slots[0].bReady = true;
    M.Slots[1] = Seat(TEXT("Veteran"), false, true, TEXT("King Arthur"));
    R->ApplyModel(M);
    TestEqual(TEXT("ready"), R->GetScreenState(), FName(TEXT("ready")));
    TestTrue(TEXT("Start enabled"), R->IsStartEnabled());
    TestEqual(TEXT("«Все готовы»"), R->GetStatusText(), FString(TEXT("Все готовы")));
    TestTrue(TEXT("the ready toggle on"), R->IsReadyOn());
    TestEqual(TEXT("one primary when ready"), R->PrimaryCount(), 1);
    if (UUmRoomSlot* S0 = R->GetSlot(0)) {
      TestEqual(TEXT("slot «ГОТОВ»"), S0->GetReadyText(), FString(TEXT("ГОТОВ")));
      TestTrue(TEXT("✓ glyph when ready"), S0->IsReadyGlyphShown());
    }
    R->SimulatePress(FName(TEXT("screens.room.start")));
    TestEqual(TEXT("start pressed once"), Starts, 1);
    // ---- SC-15 the board block
    UUmBoardCard* B0 = R->GetBoardCard(0);
    UUmBoardCard* B1 = R->GetBoardCard(1);
    if (TestNotNull(TEXT("Marmoreal card"), B0) && TestNotNull(TEXT("Sarpedon card"), B1)) {
      TestTrue(TEXT("Marmoreal is the room board"), B0->IsRoomBoard() && B0->IsCheckShown());
      TestFalse(TEXT("Sarpedon locked"), B1->IsRoomBoard() || B1->IsCheckShown());
      TestEqual(TEXT("names from the model"), B1->GetNameText(), FString(UmLobby::SarpedonName));
    }
    TestEqual(TEXT("locked why"), R->GetBoardWhyText(), FString(TEXT("Доску выбирают при создании комнаты")));
    // ---- SHOT lines: the main + board + deck, no code
    TArray<FString> Lines;
    R->CollectShotLines(Lines);
    TestEqual(TEXT("three SHOT lines"), Lines.Num(), 3);
    for (const FString& L : Lines) TestFalse(TEXT("no room code in a line"), L.Contains(TEXT("AB12CD")));
    TestTrue(TEXT("state=board line"), Lines.Num() == 3 && Lines[1].Contains(TEXT("state=board")) && Lines[1].Contains(TEXT("board=marmoreal")));
    TestTrue(TEXT("state=deck line"), Lines.Num() == 3 && Lines[2].Contains(TEXT("state=deck")) && Lines[2].Contains(TEXT("deck=30")));
    // ---- SC-18 the countdown
    R->SetPhase(EUmRoomPhase::Countdown, 3);
    TestEqual(TEXT("countdown"), R->GetScreenState(), FName(TEXT("countdown")));
    TestEqual(TEXT("digit 3"), R->GetCountText(), FString(TEXT("3")));
    R->SimulatePress(FName(TEXT("screens.room.leave")));
    TestEqual(TEXT("input closed in the countdown"), Leaves, 0);
    R->SetPhase(EUmRoomPhase::Starting);
    TestEqual(TEXT("«Партия начинается…»"), R->GetCountText(), FString(TEXT("Партия начинается…")));
    R->SetPhase(EUmRoomPhase::Room);
    TestFalse(TEXT("countdown gone"), R->IsCountShown());
    // ---- the guest: Medusa taken by the host
    FUmRoomModel G = Base(false);
    G.Heroes[1].State = EUmHeroCardState::Taken;
    G.Slots[0] = Seat(TEXT("ProGamer"), true, false, TEXT("Medusa"));
    G.bOppHero = true;
    R->ApplyModel(G);
    TestFalse(TEXT("guest: no Start"), R->IsStartShown());
    TestTrue(TEXT("guest: the ready toggle is the primary"), R->IsReadyPrimary());
    TestFalse(TEXT("guest without a hero: ready disabled"), R->IsReadyEnabled());
    TestEqual(TEXT("guest: one primary"), R->PrimaryCount(), 1);
    if (UUmHeroCard* T = R->GetHeroCard(1)) {
      TestFalse(TEXT("taken: no button"), T->IsPickShown());
      TestEqual(TEXT("taken: «Выбран соперником»"), T->GetTakenText(), FString(TEXT("Выбран соперником")));
    }
    Picked.Reset();
    R->SimulatePress(FName(TEXT("screens.room.hero.pick.1")));
    TestTrue(TEXT("a taken card sends nothing"), Picked.IsEmpty());
    G.OwnHeroId = TEXT("h-arthur");
    G.bOwnReady = true;
    G.Heroes[0].State = EUmHeroCardState::Picked;
    R->ApplyModel(G);
    TestTrue(TEXT("guest ready: the toggle on"), R->IsReadyOn());
    TestEqual(TEXT("guest ready: no primary (a toggle that is on)"), R->PrimaryCount(), 0);
    // ---- VS_AI
    FUmRoomModel Ai = Base(true);
    Ai.bVsAi = true;
    Ai.Slots[1] = FUmRoomSlotModel();
    Ai.Slots[1].Seat = EUmRoomSeat::Ai;
    Ai.Slots[1].bReady = true;
    Ai.bOppPresent = Ai.bOppHero = Ai.bOppReady = true;
    R->ApplyModel(Ai);
    if (UUmRoomSlot* S1 = R->GetSlot(1)) {
      TestEqual(TEXT("AI seat «AI Bot»"), S1->GetNameText(), FString(TEXT("AI Bot")));
      TestEqual(TEXT("AI hero line"), S1->GetHeroLine(), FString(TEXT("Герой ИИ — при старте")));
    }
    // ---- class S (720p 150 %: 1138 x 640 su) stays inside the canvas
    R->ApplyCanvas(FVector2D(1138.0, 640.0), true, 1.125f);
    const FUmRoomLayout L = UmRoom::Layout(FVector2D(1138.0, 640.0), true);
    for (const FUmRectSu* Rc : {&L.Header, &L.Slot0, &L.Slot1, &L.Grid, &L.Board, &L.Deck, &L.Bottom}) {
      TestTrue(TEXT("S rect inside"), Rc->X >= 16.0f && Rc->Y >= 16.0f && Rc->X + Rc->W <= 1138.0f - 15.9f && Rc->Y + Rc->H <= 640.0f - 15.9f);
    }
    TestTrue(TEXT("S: two compact cards fit"), L.Columns >= 2);
    const FUmRoomLayout L7 = UmRoom::Layout(FVector2D(1707.0, 960.0), false);
    TestEqual(TEXT("720p grid (548, 112)"), FVector2D(L7.Grid.X, L7.Grid.Y), FVector2D(548.0, 112.0));
    TestEqual(TEXT("720p bottom (24, 848)"), FVector2D(L7.Bottom.X, L7.Bottom.Y), FVector2D(24.0, 848.0));
    const FUmRoomLayout L10 = UmRoom::Layout(FVector2D(1920.0, 1080.0), false);
    TestEqual(TEXT("1080p board (608, 688, 1288, 160)"), FVector4(L10.Board.X, L10.Board.Y, L10.Board.W, L10.Board.H), FVector4(608.0, 688.0, 1288.0, 160.0));
    TestEqual(TEXT("1080p: four columns"), L10.Columns, 4);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensLoadingTreeTest, "Unmatched.S08.Hud.Screens.Loading.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensLoadingTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmLoadingTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  for (int32 Pass = 0; Pass < 2; ++Pass) {
    UClass* Class = Pass == 0 ? UUmScreenLoading::StaticClass() : UUmScreenLoading::WidgetClass();
    if (Pass == 1 && Class == UUmScreenLoading::StaticClass()) {
      AddInfo(TEXT("WBP_UI_SCR_LOADING not authored yet - the code tree only"));
      continue;
    }
    UUmScreenLoading* L = CreateWidget<UUmScreenLoading>(W.World, Class);
    FString Missing;
    TestTrue(FString::Printf(TEXT("pass %d: every part (%s)"), Pass, *Missing), L && L->HasAllParts(&Missing));
    if (!L) continue;
    int32 Retries = 0, Lobbies = 0;
    UUmScreenLoading::FInput In;
    In.OnRetry = [&]() { ++Retries; };
    In.OnLobby = [&]() { ++Lobbies; };
    L->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
    L->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
    L->PlayShow();
    FUmLoadingSide Own{TEXT("Medusa"), FName(TEXT("medusa")), TEXT("ProGamer")};
    FUmLoadingSide Opp{TEXT("King Arthur"), FName(TEXT("king-arthur")), TEXT("Veteran")};
    L->SetSides(Own, Opp, UmLobby::MarmorealId, UmLobby::MarmorealName);
    TestEqual(TEXT("connect"), L->GetScreenState(), FName(TEXT("connect")));
    TestEqual(TEXT("«Подключение к партии…»"), L->GetStageText(), FString(TEXT("Подключение к партии…")));
    TestEqual(TEXT("own hero left"), L->GetLeftName(), FString(TEXT("Medusa")));
    TestEqual(TEXT("opponent right"), L->GetRightName(), FString(TEXT("King Arthur")));
    TestEqual(TEXT("board name"), L->GetBoardText(), FString(UmLobby::MarmorealName));
    TestEqual(TEXT("«против»"), L->VersusText->GetText().ToString(), FString(TEXT("против")));
    TestTrue(TEXT("spinner slot"), L->IsSpinnerSlotSpinner() && !L->IsErrorIconShown());
    TestFalse(TEXT("no buttons while loading"), L->AreButtonsShown());
    L->SetStage(EUmLoadingStage::State);
    TestEqual(TEXT("«Загрузка состояния…»"), L->GetStageText(), FString(TEXT("Загрузка состояния…")));
    L->SetStage(EUmLoadingStage::Board);
    TestEqual(TEXT("«Подготовка поля…»"), L->GetStageText(), FString(TEXT("Подготовка поля…")));
    L->SimulatePress(FName(TEXT("common.btn.retry")));
    TestEqual(TEXT("no retry outside the error"), Retries, 0);
    // ---- SC-20
    L->SetStage(EUmLoadingStage::Error);
    TestEqual(TEXT("error"), L->GetScreenState(), FName(TEXT("error")));
    TestEqual(TEXT("«Не удаётся подключиться»"), L->GetStageText(), FString(TEXT("Не удаётся подключиться")));
    TestTrue(TEXT("the icon replaces the spinner"), L->IsErrorIconShown() && !L->IsSpinnerSlotSpinner());
    TestTrue(TEXT("«Повторить» the one primary"), L->IsRetryPrimary() && !L->IsLobbyPrimary());
    TestTrue(TEXT("the shot says primary=retry"), L->ShotExtra().Contains(TEXT("primary=retry")) && L->ShotExtra().Contains(TEXT("board=marmoreal")));
    L->SimulatePress(FName(TEXT("common.btn.retry")));
    L->SimulatePress(FName(TEXT("common.btn.lobby")));
    TestEqual(TEXT("retry pressed"), Retries, 1);
    TestEqual(TEXT("lobby pressed"), Lobbies, 1);
    // ---- the panel fits every canvas
    for (const FVector2D& C : {FVector2D(1920.0, 1080.0), FVector2D(1707.0, 960.0), FVector2D(1138.0, 640.0)}) {
      L->ApplyCanvas(C, C.Y < 700.0, C.Y < 700.0 ? 1.125f : 1.0f);
      const FBox2D P = L->PanelRectSu();
      TestTrue(FString::Printf(TEXT("panel inside %.0fx%.0f"), C.X, C.Y), P.Min.X >= 16.0 && P.Min.Y >= 16.0 && P.Max.X <= C.X - 16.0 && P.Max.Y <= C.Y - 16.0);
    }
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
