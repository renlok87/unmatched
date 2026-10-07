// VS-4 automation tests of the choice and the source card (docs/game-design/visual/06-tasks/hud.csv HB-35, HB-36 forms,
// HB-37; 04-hud-spec.md §2.8, §3.1, §7.1; the accepted mockup HB-34, ВР-VS2-HB34-*) and the small VS-3 fixes of the step:
//   Unmatched.S08.Hud.Pending.Tree     BuildDefaultTree of UUmHudPending, UUmNumberPicker and UUmHudSourceSlot, every
//                                      BindWidget of 04 §4.3, the GAME slots take them, the WBPs (when generated) are
//                                      children of the bases.
//   Unmatched.S08.Hud.Pending.Modal    Prophecy (live fixtures gd035-deckpick / -deckorder, owner view): the modal 640 / 560,
//                                      4 cards (L 150 x 208, S 120 x 166), «Выбрано {k}/2», «Подтвердить» refused with
//                                      why.pick.count until 2 picked, the marked cards raised 16 su; the ORDER step with the
//                                      number chips 1 and 2; the body scrolls and the footer stays in the panel on all four
//                                      canvases; CHOOSE_ONE (synthesized from the server model, ВР-HB11) with full-width
//                                      options and «Назад»; the number ▲▼ (clamp, confirm / cancel); the budget.
//   Unmatched.S08.Hud.Pending.Keys     C collapses / expands through the presenter (the plate «{card}: выбор ждёт»), a
//                                      mandatory choice has no «Отказаться», an optional one has; «Назад» only with a
//                                      picked option (Esc: back, else why.choice.required - the game mode).
//   Unmatched.S08.Hud.Pending.Forms    the HB-36 forms the step builds: compact MOVE (L two rows 720, S one row in the
//                                      band), the hand-limit discard, King Arthur's BOOST (two buttons), the opponent's grey
//                                      choice (>= 320 su, no buttons, the line left to STATUS), after-combat, the toast;
//                                      a long name wraps (never cut); SHOT states of 04 §7.1, no card name in the line.
//   Unmatched.S08.Hud.Pending.Source   the source card from the effect id (catalog id prefix, discard-choice-, ability-),
//                                      the text fallback, '' when unknown.
//   Unmatched.S08.Hud.Slot.Timeline    own scheme fly 200 -> shown -> the 150 ms leave; the opponent's scheme fly 200 ->
//                                      hold 1500 (the bar at 50 % mid-hold) -> shown while its effect runs -> 150; the
//                                      opponent's boost >= 1000 then 150 (the widget's own fade, ВР-VS4-11).
//   Unmatched.S08.Hud.Slot.Ribbon      СХЕМА / BOOST / СБРОС: the IC-50...52 glyph, the plate and ink tokens, the owner on
//                                      the ribbon (wraps in S), the S BOOST ribbon 190 su with «+N», 32 su glyph below
//                                      1 px per su; the SHOT line has no card name.
//   Unmatched.S08.Hud.Fixes.Vs3        VS-3 open items of the step: the empty lowered hand writes visible=0 (item 2), the
//                                      right boost chip on the drawn card's corner (item 12), «Нет защиты» under the
//                                      no-defense stamp (item 13), the HUD sidekick number = the base digit (Z-1).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Pending+Unmatched.S08.Hud.Slot+Unmatched.S08.Hud.Fixes" <log>
#if WITH_AUTOMATION_TESTS

#include "../../S09/S09CardSlot.h"
#include "../../S09/S09ManeuverUi.h"
#include "../../S09/S09PendingPresent.h"
#include "../S08AnimatedIconWidget.h"
#include "../S08BoardModel.h"
#include "../S08Contracts.h"
#include "../S08HeroesV2.h"
#include "Components/Border.h"
#include "Components/Image.h"
#include "Components/Overlay.h"
#include "Components/OverlaySlot.h"
#include "Components/TextBlock.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UmButton.h"
#include "UmCardWidget.h"
#include "UmGameHud.h"
#include "UmHudCombatEdge.h"
#include "UmHudHand.h"
#include "UmHudLayout.h"
#include "UmHudPanels.h"
#include "UmHudPending.h"
#include "UmHudSourceSlot.h"
#include "UmNumberPicker.h"
#include "UmText.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace UmPendingTest {
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
#if WITH_EDITOR  // the preview API exists only WITH_EDITOR (the VS-1 / VS-2 C2039 trap of the game target)
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(TEXT("ru"));
#endif
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FRu() { FInternationalization::Get().RestoreCultureState(Snapshot); }
};

struct FPdCanvas {
  const TCHAR* Name;
  FVector2D Su;
  float Px;
};
const FPdCanvas Canvases[] = {{TEXT("1080p100"), FVector2D(1920.0, 1080.0), 1.0f},
                            {TEXT("720p100"), FVector2D(1280.0 / 0.75, 960.0), 0.75f},
                            {TEXT("1080p150"), FVector2D(1280.0, 720.0), 1.5f},
                            {TEXT("720p150"), FVector2D(1280.0 / 1.125, 640.0), 1.125f}};

/** The frame the game mode gives the block on a canvas (no STATUS / combat centre under it). */
FUmPendingFrame Frame(const FPdCanvas& C) {
  const FUmHudLayout L = FUmHudLayout::Compute(C.Su, C.Px, nullptr);
  FUmPendingFrame F;
  F.bClassS = L.bClassS;
  F.PxPerSu = C.Px;
  F.CanvasSu = L.CanvasSu;
  F.TopSu = static_cast<float>(L.Rect(EUmHudBlock::Center).Min.Y);
  F.ModalWidthSu = L.bClassS ? 560.0f : 640.0f;
  F.ModalCapSu = L.bClassS ? 360.0f : (L.bTall ? 420.0f : 380.0f);
  F.BandLeftSu = static_cast<float>(L.Rect(EUmHudBlock::SourceSlot).Max.X) + 8.0f;
  F.BandRightSu = static_cast<float>(FMath::Min(L.Rect(EUmHudBlock::PanelOpp).Min.X, L.Rect(EUmHudBlock::OppHand).Min.X)) - 8.0f;
  return F;
}

bool LoadFixture(const FString& Name, FS08Snapshot& Out) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S09Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/game-design/evidence/S09/fixtures"));
  }
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Dir, Name + TEXT(".json")))) return false;
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) return false;
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (!Value->TryGetObject(Root) || !Root->IsValid()) return false;
  FString Body;
  const TSharedPtr<FJsonObject>* RawObject = nullptr;
  if ((*Root)->TryGetStringField(TEXT("raw"), Body)) {
    if (!FS08Contracts::TryParseJsonValue(Body, Value, Problem)) return false;
  } else if ((*Root)->TryGetObjectField(TEXT("raw"), RawObject) && RawObject->IsValid()) {
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
  }
  FS08GraphQLError Error;
  return FS08Contracts::ParseGameStateQuery(Body, Out, Problem, Error);
}

/** The ids of the two seats (players[0], players[1]). */
bool Seats(const FS08Snapshot& Snapshot, FString& OutFirst, FString& OutSecond) {
  const TArray<TSharedPtr<FJsonValue>>* Players = nullptr;
  if (!Snapshot.Players.IsValid() || !Snapshot.Players->TryGetArray(Players) || !Players || Players->Num() < 2) return false;
  const TSharedPtr<FJsonObject>* P0 = nullptr;
  const TSharedPtr<FJsonObject>* P1 = nullptr;
  if (!(*Players)[0]->TryGetObject(P0) || !(*Players)[1]->TryGetObject(P1)) return false;
  OutFirst = (*P0)->GetStringField(TEXT("userId"));
  OutSecond = (*P1)->GetStringField(TEXT("userId"));
  return !OutFirst.IsEmpty() && !OutSecond.IsEmpty();
}

/** The viewer of a fixture whose own head is open: whichever seat the command state opens PendingChoice for. */
bool OpenOwnHead(const FS08Snapshot& Snap, FS09CommandUi& Ui, FS08BoardModel& Board, TArray<FS08BoardFighter>& Fighters) {
  FS08BoardModel::DecodeFighters(Snap.Fighters, Fighters);
  Board.Decode(Snap.BoardState);
  FString A, B;
  if (!Seats(Snap, A, B)) return false;
  for (const FString& Viewer : {A, B}) {
    Ui = FS09CommandUi();
    Ui.ViewerId = Viewer;
    Ui.OnSnapshot(Snap, Board, Fighters);
    if (Ui.Mode == ES09CommandMode::PendingChoice) return true;
  }
  return false;
}

/** The gather input of an open own head (the bits the game mode reads from the snapshot). */
UmHudPending::FUmPendingInput Input(const FS09CommandUi& Ui, const FS08Snapshot& Snap, const FS09PendingPresenter* Presenter) {
  UmHudPending::FUmPendingInput In;
  In.bLive = true;
  In.ViewerId = Ui.ViewerId;
  In.Ui = &Ui;
  In.Presenter = Presenter;
  In.OwnHeroSlug = TEXT("king-arthur");
  In.HeroNames.Add(Ui.ViewerId, TEXT("King Arthur"));
  TArray<FString> Pool;
  int32 Need = 0;
  if (Ui.PendingCardPickPlan(Snap, Pool, Need)) In.PickNeed = Need;
  Ui.PendingRevealedCards(In.Revealed);
  // Prophecy's catalog id is the prefix of its effect id (game-initialization.service: effects of card.id)
  FS09CardView Prophecy;
  int32 Dash = Ui.PendingChoice.Id.Find(TEXT("-"));
  Prophecy.CardId = Dash > 0 ? Ui.PendingChoice.Id.Left(Dash) : FString();
  Prophecy.Name = TEXT("Prophecy");
  Prophecy.NameRu = TEXT("Prophecy");
  Prophecy.Text = TEXT("Look at the top 4 cards of your deck. Add 2 of them to your hand and put the other 2 back on top of your deck, in any order.");
  In.Known.Add(Prophecy);
  return In;
}

float Measure(const FString& Text, float SizeSu, FName) { return 0.5f * SizeSu * Text.Len(); }

/** The key-chip labels of the toast / collapsed plans (Enter, X, C). */
TMap<FName, FString> KeyLabels(bool bAll) {
  TMap<FName, FString> M;
  M.Add(FName(TEXT("KeyC")), TEXT("C"));
  if (bAll) {
    M.Add(FName(TEXT("KeyEnter")), TEXT("Enter"));
    M.Add(FName(TEXT("KeyX")), TEXT("X"));
  }
  return M;
}

FString ShotOf(UUmHudPending* P) {
  TArray<FString> Lines;
  P->CollectShotLines(Lines);
  return Lines.Num() ? Lines[0] : FString();
}
}  // namespace UmPendingTest

// ------------------------------------------------------------------------------------------------------------- Tree

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPendingTreeTest,
    "Unmatched.S08.Hud.Pending.Tree UUmHudPending UUmNumberPicker UUmHudSourceSlot default trees, BindWidget, GAME slots, WBPs",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPendingTreeTest::RunTest(const FString&) {
  using namespace UmPendingTest;
  FWorld W(TEXT("UmPendingTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  UUmHudPending* P = CreateWidget<UUmHudPending>(W.World, UUmHudPending::StaticClass());
  UUmHudSourceSlot* S = CreateWidget<UUmHudSourceSlot>(W.World, UUmHudSourceSlot::StaticClass());
  UUmNumberPicker* N = CreateWidget<UUmNumberPicker>(W.World, UUmNumberPicker::StaticClass());
  if (!TestNotNull(TEXT("pending"), P) || !TestNotNull(TEXT("slot"), S) || !TestNotNull(TEXT("picker"), N)) return false;
  FString Missing;
  TestTrue(FString::Printf(TEXT("pending parts (04 §4.3) missing=%s"), *Missing), P->HasAllParts(&Missing));
  TestTrue(TEXT("pending code tree"), P->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("slot parts missing=%s"), *Missing), S->HasAllParts(&Missing));
  TestTrue(FString::Printf(TEXT("picker parts missing=%s"), *Missing), N->HasAllParts(&Missing));
  TestNotNull(TEXT("the picker inside the pending body"), P->Picker.Get());
  TestNotNull(TEXT("option pool 0"), P->GetOption(0));
  TestNotNull(TEXT("option pool 5"), P->GetOption(UmHudPending::MaxOptions - 1));
  TestNotNull(TEXT("card pool 3"), P->GetCard(UmHudPending::MaxCards - 1));
  // hidden until a model shows something; the slot never takes the pointer (the hold skip is a click on the field)
  TestEqual(TEXT("pending collapsed at rest"), P->GetVisibility(), ESlateVisibility::Collapsed);
  TestEqual(TEXT("slot collapsed at rest"), S->GetVisibility(), ESlateVisibility::Collapsed);
  UUmGameHud* Game = CreateWidget<UUmGameHud>(W.World, UUmGameHud::StaticClass());
  if (TestNotNull(TEXT("game"), Game)) {
    TestTrue(TEXT("GAME slot Pending takes the block"), Game->SetBlock(EUmGameSlot::Pending, P));
    TestTrue(TEXT("GAME slot SourceSlot takes the block"), Game->SetBlock(EUmGameSlot::SourceSlot, S));
    const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1920.0, 1080.0), 1.0f, nullptr);
    const FBox2D PR = UmGameHudSlots::SlotRect(L, EUmGameSlot::Pending);
    TestTrue(TEXT("the pending slot is the whole canvas (the block places its forms)"), PR.Min.IsZero() && PR.Max == FVector2D(1920.0, 1080.0));
    const FBox2D SR = UmGameHudSlots::SlotRect(L, EUmGameSlot::SourceSlot);
    TestTrue(TEXT("the slot's GAME slot holds the card and its ribbon"), SR.Min == FVector2D(24.0, 84.0) && SR.Max.Y >= 84.0 + 264.0 + 4.0 + 40.0);
  }
  // the generated WBPs, when they exist, are children of the bases with every part
  for (UClass* Cls : {UUmHudPending::WidgetClass(), UUmHudSourceSlot::WidgetClass()}) {
    if (!Cls) continue;
    if (Cls == UUmHudPending::StaticClass() || Cls == UUmHudSourceSlot::StaticClass()) {
      AddInfo(FString::Printf(TEXT("%s: no WBP yet (code tree)"), *Cls->GetName()));
      continue;
    }
    UUserWidget* Wbp = CreateWidget<UUserWidget>(W.World, Cls);
    if (UUmHudPending* WP = Cast<UUmHudPending>(Wbp)) {
      TestTrue(FString::Printf(TEXT("WBP_UI_HUD_PENDING parts missing=%s"), *Missing), WP->HasAllParts(&Missing));
    } else if (UUmHudSourceSlot* WS = Cast<UUmHudSourceSlot>(Wbp)) {
      TestTrue(FString::Printf(TEXT("WBP_UI_HUD_SLOT parts missing=%s"), *Missing), WS->HasAllParts(&Missing));
    } else {
      AddError(FString::Printf(TEXT("%s is not a child of its base"), *Cls->GetPathName()));
    }
  }
  return true;
}

// ------------------------------------------------------------------------------------------------------------ Modal

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPendingModalTest,
    "Unmatched.S08.Hud.Pending.Modal Prophecy 4 of which 2 then the order, CHOOSE_ONE options, the number picker, fit on 4 canvases",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPendingModalTest::RunTest(const FString&) {
  using namespace UmPendingTest;
  FRu Ru;
  FWorld W(TEXT("UmPendingModal"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FS08Snapshot Pick, Order;
  if (!LoadFixture(TEXT("gd035-deckpick-owner-view"), Pick) || !LoadFixture(TEXT("gd035-deckorder-owner-view"), Order)) {
    AddError(TEXT("fixtures not loaded (docs/game-design/evidence/S09/fixtures)"));
    return true;
  }
  FS09CommandUi Ui;
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  if (!TestTrue(TEXT("PICK: the owner's head opens"), OpenOwnHead(Pick, Ui, Board, Fighters))) return true;
  TestEqual(TEXT("the head is DECK_TOP_PICK"), Ui.PendingChoice.Type, FString(TEXT("DECK_TOP_PICK")));
  UmHudPending::FUmPendingInput In = Input(Ui, Pick, nullptr);
  FUmPendingModel M = UmHudPending::Gather(In);
  TestEqual(TEXT("modal"), M.View, EUmPendingView::Modal);
  TestEqual(TEXT("PICK body"), M.Body, EUmPendingBody::Pick);
  TestEqual(TEXT("the source card names the modal"), M.Title, FString(TEXT("Prophecy")));
  TestTrue(TEXT("4 revealed cards (or the fixture's)"), M.Cards.Num() >= 2 && M.Cards.Num() <= UmHudPending::MaxCards);
  TestEqual(TEXT("pick 2"), M.PickNeed, 2);
  TestEqual(TEXT("«Подтвердить» refused before the pick: why.pick.count"), M.ConfirmWhy.Key, FName(TEXT("why.pick.count")));
  TestTrue(TEXT("collapse offered"), M.bCollapse);
  TestFalse(TEXT("no «Отказаться»: Prophecy is mandatory"), M.bDecline);
  TestFalse(TEXT("no «Назад» on a card pick (a click unmarks)"), M.bBack);
  // pick two: the counter and the enabled primary
  FString Reason;
  for (int32 I = 0; I < 2 && I < In.Revealed.Num(); ++I) TestTrue(TEXT("toggle"), Ui.TogglePendingCard(In.Revealed[I].InstanceId, Pick, Reason));
  In = Input(Ui, Pick, nullptr);
  M = UmHudPending::Gather(In);
  TestEqual(TEXT("2 picked"), M.PickHave, 2);
  TestFalse(TEXT("«Подтвердить» enabled at 2/2"), M.ConfirmWhy.IsSet());
  TestTrue(TEXT("the picked are marked"), M.Cards[0].bMarked && M.Cards[1].bMarked);
  UUmHudPending* P = CreateWidget<UUmHudPending>(W.World, UUmHudPending::StaticClass());
  if (!TestNotNull(TEXT("pending"), P)) return false;
  P->SetSyncLoad(true);
  for (const FPdCanvas& C : Canvases) {
    const FUmPendingFrame F = Frame(C);
    P->SetFrame(F);
    P->ApplyModel(M);
    const FUmPendingPlan& Plan = P->GetPlan();
    const FString Tag(C.Name);
    TestEqual(Tag + TEXT(": modal width 640 / S 560"), static_cast<float>(Plan.Panel.GetSize().X), F.ModalWidthSu);
    TestTrue(Tag + TEXT(": height <= cap"), Plan.Panel.GetSize().Y <= F.ModalCapSu + 0.01);
    TestTrue(Tag + TEXT(": at CENTER y"), FMath::IsNearlyEqual(static_cast<float>(Plan.Panel.Min.Y), F.TopSu));
    const FBox2D Confirm = Plan.Find(FName(TEXT("Confirm")));
    const FBox2D Collapse = Plan.Find(FName(TEXT("Collapse")));
    TestTrue(Tag + TEXT(": «Подтвердить» and «Свернуть (C)» in the panel, footer visible"),
             Confirm.bIsValid && Collapse.bIsValid && Plan.Panel.IsInside(Confirm.Min) && Collapse.Max.Y <= Plan.Panel.Max.Y + 0.01 &&
                 Collapse.Max.X <= Plan.Panel.Max.X + 0.01);
    TestTrue(Tag + TEXT(": the counter left of the buttons"), Plan.Counter.bIsValid && Plan.Counter.Max.X <= Confirm.Min.X);
    TestTrue(Tag + TEXT(": the body view above the footer, scroll >= 0"), Plan.BodyView.bIsValid && Plan.BodyView.Max.Y <= Confirm.Min.Y && Plan.ScrollSu >= 0.0f);
    const FVector2D CardSize = F.bClassS ? FVector2D(120.0, 166.0) : FVector2D(150.0, 208.0);
    TestTrue(Tag + TEXT(": card 150 x 208 / S 120 x 166"), Plan.Cards.Num() == M.Cards.Num() && Plan.Cards[0].GetSize() == CardSize);
    TestTrue(Tag + TEXT(": the marked card raised 16 su"), Plan.Cards.Num() > 2 && FMath::IsNearlyEqual(Plan.Cards[2].Min.Y - Plan.Cards[0].Min.Y, 16.0, 0.01));
    TestTrue(Tag + TEXT(": the cards inside the body width"), Plan.Cards.Last().Max.X <= Plan.BodyView.GetSize().X + 0.01 && Plan.Cards[0].Min.X >= -0.01);
    AddInfo(FString::Printf(TEXT("%s modal %.0fx%.0f content %.0f view %.0f scroll %.0f"), C.Name, Plan.Panel.GetSize().X, Plan.Panel.GetSize().Y,
                            Plan.ContentSu, Plan.BodyView.GetSize().Y, Plan.ScrollSu));
  }
  TestEqual(TEXT("RU counter «Выбрано 2/2»"), P->GetLabels().FindRef(FName(TEXT("Counter"))), FString(TEXT("Выбрано 2/2")));
  TestTrue(TEXT("the marked card shows CP-17 selected"), P->GetCard(0) && P->GetCard(0)->IsSelected());
  const FString Shot = ShotOf(P);
  TestTrue(TEXT("SHOT state=modal body=pick pick=2/2"), Shot.Contains(TEXT("id=UI-HUD-PENDING")) && Shot.Contains(TEXT("state=modal")) &&
                                                          Shot.Contains(TEXT("body=pick")) && Shot.Contains(TEXT("pick=2/2")));
  TestFalse(TEXT("no card name in the SHOT line"), Shot.Contains(TEXT("Prophecy")));
  // ---- ORDER: the two cards left, numbered by the pick sequence ----
  FS09CommandUi OrderUi;
  if (TestTrue(TEXT("ORDER: the owner's head opens"), OpenOwnHead(Order, OrderUi, Board, Fighters))) {
    UmHudPending::FUmPendingInput OIn = Input(OrderUi, Order, nullptr);
    FUmPendingModel OM = UmHudPending::Gather(OIn);
    TestEqual(TEXT("ORDER body"), OM.Body, EUmPendingBody::Order);
    TestEqual(TEXT("ORDER: every card is ordered"), OM.PickNeed, OM.Cards.Num());
    for (int32 I = OIn.Revealed.Num() - 1; I >= 0; --I) OrderUi.TogglePendingCard(OIn.Revealed[I].InstanceId, Order, Reason);
    OIn = Input(OrderUi, Order, nullptr);
    OM = UmHudPending::Gather(OIn);
    TestTrue(TEXT("ORDER: the last card got number 1"), OM.Cards.Num() >= 2 && OM.Cards.Last().Order == 1 && OM.Cards[0].Order == OM.Cards.Num());
    TestFalse(TEXT("ORDER: «Подтвердить» enabled when all are ordered"), OM.ConfirmWhy.IsSet());
    P->SetFrame(Frame(Canvases[0]));
    P->ApplyModel(OM);
    const FUmPendingPlan& Plan = P->GetPlan();
    TestEqual(TEXT("ORDER: a chip per card"), Plan.Chips.Num(), OM.Cards.Num());
    TestTrue(TEXT("ORDER: the chip 28 su over the card"), Plan.Chips.Num() > 0 && FMath::IsNearlyEqual(Plan.Cards[0].Min.Y - Plan.Chips[0].Min.Y, 28.0, 0.01));
    TestFalse(TEXT("ORDER: no counter (ВР-VS2-HB34-19)"), Plan.Counter.bIsValid);
  }
  // ---- CHOOSE_ONE: no MVP card (ВР-HB11) - the head as the server model makes it ----
  FS09CommandUi One;
  One.Mode = ES09CommandMode::PendingChoice;
  One.bHasPendingChoice = true;
  One.ViewerId = TEXT("p1");
  One.PendingChoice.Id = TEXT("cat-skirmish-after-0-p0");
  One.PendingChoice.PlayerId = TEXT("p1");
  One.PendingChoice.Type = TEXT("CHOOSE_ONE");
  One.PendingChoice.Text = TEXT("Choose one:");
  for (int32 I = 0; I < 3; ++I) {
    FS08PendingOption O;
    O.Index = I;
    O.Label = FString::Printf(TEXT("Option %d - a long option label that tests the full width of the button"), I + 1);
    One.PendingChoice.Options.Add(O);
  }
  One.PendingQueue.Add(One.PendingChoice);
  UmHudPending::FUmPendingInput OneIn;
  OneIn.bLive = true;
  OneIn.ViewerId = TEXT("p1");
  OneIn.Ui = &One;
  FUmPendingModel OneM = UmHudPending::Gather(OneIn);
  TestEqual(TEXT("CHOOSE_ONE: modal options"), OneM.Body, EUmPendingBody::Options);
  TestEqual(TEXT("CHOOSE_ONE: 3 options"), OneM.Options.Num(), 3);
  TestEqual(TEXT("CHOOSE_ONE: refused without an option"), OneM.ConfirmWhy.Key, FName(TEXT("why.pick.count")));
  TestFalse(TEXT("CHOOSE_ONE: no «Назад» before a pick"), OneM.bBack);
  One.PendingOptionIndex = 1;
  OneM = UmHudPending::Gather(OneIn);
  TestTrue(TEXT("CHOOSE_ONE: «Назад» after a pick, primary enabled"), OneM.bBack && !OneM.ConfirmWhy.IsSet());
  P->SetFrame(Frame(Canvases[3]));
  P->ApplyModel(OneM);
  {
    const FUmPendingPlan& Plan = P->GetPlan();
    TestTrue(TEXT("CHOOSE_ONE S: footer with «Назад», «Подтвердить», «Свернуть» in the panel"),
             Plan.Find(FName(TEXT("Back"))).bIsValid && Plan.Find(FName(TEXT("Confirm"))).bIsValid &&
                 Plan.Find(FName(TEXT("Collapse"))).Max.X <= Plan.Panel.Max.X + 0.01);
    UUmButton* Opt = P->GetOption(1);
    TestTrue(TEXT("CHOOSE_ONE: the picked option is selected"), Opt && Opt->GetModel().bSelected);
    TestTrue(TEXT("CHOOSE_ONE: full-width option buttons"), Opt && FMath::IsNearlyEqual(Opt->GetModel().MinWidthSu, static_cast<float>(Plan.BodyView.GetSize().X) - 8.0f));
    TestTrue(TEXT("CHOOSE_ONE: option 4..6 unused, hidden"), P->GetOption(3) && P->GetOption(3)->GetVisibility() == ESlateVisibility::Collapsed);
  }
  // ---- the number ▲▼ ----
  FUmNumberModel NM;
  NM.Min = 1;
  NM.Max = 3;
  NM.Value = 3;
  TestEqual(TEXT("▲ at max stays"), UmNumberPicker::Stepped(NM, 1), 3);
  TestEqual(TEXT("▼ steps"), UmNumberPicker::Stepped(NM, -1), 2);
  NM.Value = 1;
  TestEqual(TEXT("▼ at min stays"), UmNumberPicker::Stepped(NM, -1), 1);
  FUmPendingModel Num;
  Num.View = EUmPendingView::Modal;
  Num.Body = EUmPendingBody::Number;
  Num.Kind = TEXT("NUMBER");
  Num.Title = TEXT("Test");
  Num.Text = TEXT("Choose a number.");
  Num.Number = NM;
  Num.Number.Result = TEXT("Result plate");
  Num.bCollapse = true;
  Num.bBack = true;
  P->SetFrame(Frame(Canvases[0]));
  P->ApplyModel(Num);
  TestTrue(TEXT("number: the picker shown with its value"), P->Picker && P->Picker->GetVisibility() != ESlateVisibility::Collapsed &&
                                                            P->Picker->Describe().Contains(TEXT("value=1")));
  TestTrue(TEXT("number: content holds the picker"), P->GetPlan().ContentSu >= UmNumberPicker::HeightSu(true));
  // ---- budget: the same model again is free; a new step rebuilds in <= 2 ms ----
  TArray<double> Same, Step;
  for (int32 I = 0; I < 60; ++I) {
    const double T0 = FPlatformTime::Seconds();
    P->ApplyModel(Num);
    Same.Add((FPlatformTime::Seconds() - T0) * 1000.0);
    FUmPendingModel Next = (I % 2) ? M : OneM;
    const double T1 = FPlatformTime::Seconds();
    P->ApplyModel(Next);
    Step.Add((FPlatformTime::Seconds() - T1) * 1000.0);
    P->ApplyModel(Num);
  }
  Same.Sort();
  Step.Sort();
  const double SameP95 = Same[FMath::FloorToInt(0.95 * (Same.Num() - 1))];
  const double StepP95 = Step[FMath::FloorToInt(0.95 * (Step.Num() - 1))];
  AddInfo(FString::Printf(TEXT("budget: same model p95 %.4f ms (<= 0.05), step change p95 %.3f ms (<= 2)"), SameP95, StepP95));
  TestTrue(TEXT("open modal, same model <= 0.05 ms p95"), SameP95 <= 0.05);
  TestTrue(TEXT("a new step <= 2 ms p95"), StepP95 <= 2.0);
  return true;
}

// ------------------------------------------------------------------------------------------------------------- Keys

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPendingKeysTest,
    "Unmatched.S08.Hud.Pending.Keys C collapses and expands through the presenter, decline only when optional, back only after a pick",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPendingKeysTest::RunTest(const FString&) {
  using namespace UmPendingTest;
  FS09CommandUi Ui;
  Ui.Mode = ES09CommandMode::PendingChoice;
  Ui.bHasPendingChoice = true;
  Ui.ViewerId = TEXT("p1");
  Ui.PendingChoice.Id = TEXT("cat-prophecy-immediately-0-p0");
  Ui.PendingChoice.PlayerId = TEXT("p1");
  Ui.PendingChoice.Type = TEXT("DECK_TOP_PICK");
  Ui.PendingChoice.Mode = TEXT("PICK");
  Ui.PendingChoice.Value = 2;
  Ui.PendingChoice.bHasValue = true;
  Ui.PendingQueue.Add(Ui.PendingChoice);
  FS09PendingPresenter Presenter;
  TestTrue(TEXT("first open"), Presenter.Observe(Ui.PendingChoice, 3));
  UmHudPending::FUmPendingInput In;
  In.bLive = true;
  In.ViewerId = TEXT("p1");
  In.Ui = &Ui;
  In.Presenter = &Presenter;
  FS09CardView Prophecy;
  Prophecy.CardId = TEXT("cat-prophecy");
  Prophecy.Name = TEXT("Prophecy");
  In.Known.Add(Prophecy);
  TestEqual(TEXT("first open = modal"), UmHudPending::Gather(In).View, EUmPendingView::Modal);
  // C (or «Свернуть»): the plate; the choice stays
  TestTrue(TEXT("C collapses"), Presenter.Toggle());
  FUmPendingModel M = UmHudPending::Gather(In);
  TestEqual(TEXT("collapsed plate"), M.View, EUmPendingView::Collapsed);
  TestTrue(TEXT("«{card}: выбор ждёт» names the card"), M.Text.Contains(TEXT("Prophecy")));
  FUmPendingPlan Plan = UmHudPending::Plan(M, Frame(Canvases[0]), KeyLabels(false), &Measure);
  TestTrue(TEXT("plate 320 x 44 at least"), Plan.Panel.GetSize().X >= 320.0 && FMath::IsNearlyEqual(Plan.Panel.GetSize().Y, 44.0));
  TestTrue(TEXT("the plate is the expand button"), Plan.Find(FName(TEXT("Expand"))) == Plan.Panel);
  TestEqual(TEXT("one key chip C"), Plan.Keys.Num(), 1);
  TestTrue(TEXT("C expands"), Presenter.Toggle());
  TestEqual(TEXT("back to the modal"), UmHudPending::Gather(In).View, EUmPendingView::Modal);
  // decline: never on a mandatory choice, always on an optional one
  TestFalse(TEXT("mandatory: no «Отказаться»"), UmHudPending::Gather(In).bDecline);
  Ui.PendingChoice.bOptional = true;
  TestTrue(TEXT("optional: «Отказаться (X)»"), UmHudPending::Gather(In).bDecline);
  // a command in flight refuses every button with its reason (the busy cursor of 04 §3.2)
  In.BusyWhy = FS09Reason::Make(TEXT("why.syncing"));
  TestEqual(TEXT("busy: the primary refuses with why.syncing"), UmHudPending::Gather(In).ConfirmWhy.Key, FName(TEXT("why.syncing")));
  // the slot holds the opponent's scheme: my choice it opened waits hidden (F-10)
  In.BusyWhy.Reset();
  In.bHeldBySlot = true;
  TestEqual(TEXT("held by the slot: hidden"), UmHudPending::Gather(In).View, EUmPendingView::Hidden);
  return true;
}

// ------------------------------------------------------------------------------------------------------------ Forms

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPendingFormsTest,
    "Unmatched.S08.Hud.Pending.Forms compact L two rows S one row, limit discard, Arthur BOOST, opponent grey, after combat, toast",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPendingFormsTest::RunTest(const FString&) {
  using namespace UmPendingTest;
  FWorld W(TEXT("UmPendingForms"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  // ---- compact MOVE: the Hounds of Mighty Zeus, the first Harpy of three (HB-34 compact-move) ----
  FS09CommandUi Ui;
  Ui.Mode = ES09CommandMode::PendingChoice;
  Ui.bHasPendingChoice = true;
  Ui.ViewerId = TEXT("p1");
  FS08PendingEffect Move;
  Move.Id = TEXT("cat-hounds-after-0-p0");
  Move.PlayerId = TEXT("p1");
  Move.Type = TEXT("MOVE");
  Move.Value = 3;
  Move.bHasValue = true;
  Ui.PendingChoice = Move;
  for (int32 I = 0; I < 3; ++I) {
    FS08PendingEffect Q = Move;
    Q.Id = FString::Printf(TEXT("cat-hounds-after-0-p%d"), I);
    Ui.PendingQueue.Add(Q);
  }
  UmHudPending::FUmPendingInput In;
  In.bLive = true;
  In.ViewerId = TEXT("p1");
  In.Ui = &Ui;
  In.MovePrompt = FS09Reason::Make(TEXT("ms.pending.move")).Arg(TEXT("fighterName"), TEXT("Harpies")).Arg(TEXT("n"), 3);
  In.bCanStay = true;
  FS09CardView Hounds;
  Hounds.CardId = TEXT("cat-hounds");
  Hounds.Name = TEXT("The Hounds of Mighty Zeus");
  In.Known.Add(Hounds);
  FUmPendingModel M = UmHudPending::Gather(In);
  TestEqual(TEXT("MOVE: compact"), M.View, EUmPendingView::Compact);
  TestEqual(TEXT("MOVE: the move glyph"), M.Icon, FName(TEXT("state-pending-move")));
  TestEqual(TEXT("MOVE: «ещё 2»"), M.QueueMore, 2);
  TestTrue(TEXT("MOVE: «Оставить на месте», «Свернуть», no «Отказаться» (up to - not «you may»)"), M.bStay && M.bCollapse && !M.bDecline);
  TestFalse(TEXT("MOVE: no confirm button (the space is the answer)"), M.bConfirm);
  UUmHudPending* P = CreateWidget<UUmHudPending>(W.World, UUmHudPending::StaticClass());
  if (!TestNotNull(TEXT("pending"), P)) return false;
  P->SetFrame(Frame(Canvases[0]));
  P->ApplyModel(M);
  FUmPendingPlan Plan = P->GetPlan();
  TestTrue(TEXT("L: 720 su, >= 56 su, two rows"), FMath::IsNearlyEqual(Plan.Panel.GetSize().X, 720.0) && Plan.Panel.GetSize().Y >= 56.0 &&
                                                     Plan.Title.bIsValid && Plan.Hint.bIsValid && Plan.Hint.Min.Y > Plan.Title.Min.Y);
  TestTrue(TEXT("L: the queue chip right of the name"), Plan.Queue.bIsValid && Plan.Queue.Min.X >= Plan.Title.Max.X);
  TestTrue(TEXT("L: the buttons right, inside"), Plan.Find(FName(TEXT("Collapse"))).Max.X <= Plan.Panel.Max.X + 0.01 &&
                                                    Plan.Find(FName(TEXT("Stay"))).Min.X >= Plan.Hint.Max.X - 0.01);
  P->SetFrame(Frame(Canvases[2]));
  P->ApplyModel(M);
  Plan = P->GetPlan();
  const FUmPendingFrame FS = Frame(Canvases[2]);
  TestFalse(TEXT("S: the hint stays in STATUS (ВР-VS2-HB34-13)"), Plan.Hint.bIsValid);
  TestTrue(TEXT("S: one row of 56 su, or the long name wraps and the plate grows (never cut)"),
           Plan.Panel.GetSize().Y <= 56.01 || Plan.TitleRows > 1);
  TestTrue(TEXT("S: >= 560 and <= 720 su"), Plan.Panel.GetSize().X >= 559.99 && Plan.Panel.GetSize().X <= 720.01);
  TestTrue(TEXT("S: inside the band SLOT + 8 ... PANEL-OPP - 8"), Plan.Panel.Min.X >= FS.BandLeftSu - 0.01 && Plan.Panel.Max.X <= FS.BandRightSu + 0.01);
  const FString Shot = ShotOf(P);
  TestTrue(TEXT("SHOT compact kind=MOVE queue=2 tone=own"), Shot.Contains(TEXT("state=compact")) && Shot.Contains(TEXT("kind=MOVE")) &&
                                                               Shot.Contains(TEXT("queue=2")) && Shot.Contains(TEXT("tone=own")));
  TestFalse(TEXT("no card name in SHOT"), Shot.Contains(TEXT("Hounds")));
  // a name that does not fit wraps - the plate grows, nothing is cut
  FUmPendingModel Long = M;
  Long.Title = TEXT("An Extraordinarily Long Card Name That Never Fits One Row Of The Compact Plate At All");
  const FUmPendingPlan LongPlan = UmHudPending::Plan(Long, Frame(Canvases[0]), TMap<FName, FString>(), &Measure);
  TestTrue(TEXT("long name: more rows, a taller plate"), LongPlan.TitleRows > 1 && LongPlan.Panel.GetSize().Y > 60.0);
  // ---- the hand-limit discard: «Сбросьте {n}: выбрано {h}/{n}», no cancel ----
  FS09CommandUi Limit;
  Limit.Mode = ES09CommandMode::DiscardDraft;
  Limit.PendingDiscard.Count = 2;
  Limit.DiscardSelection.Add(TEXT("a"));
  UmHudPending::FUmPendingInput LIn;
  LIn.bLive = true;
  LIn.Ui = &Limit;
  M = UmHudPending::Gather(LIn);
  TestTrue(TEXT("limit: compact discard"), M.View == EUmPendingView::Compact && M.Compact == EUmPendingCompact::Discard && M.Kind == TEXT("LIMIT"));
  TestEqual(TEXT("limit: refused with why.discard.count"), M.ConfirmWhy.Key, FName(TEXT("why.discard.count")));
  TestTrue(TEXT("limit: no cancel, no collapse"), !M.bDecline && !M.bCollapse && !M.bBack);
  // ---- King Arthur's ability (SD-56): two buttons, the question in STATUS ----
  FS09CommandUi Ability;
  Ability.Mode = ES09CommandMode::AttackDraft;
  Ability.OpenAttackAbilityPrompt();
  UmHudPending::FUmPendingInput AIn;
  AIn.bLive = true;
  AIn.Ui = &Ability;
  M = UmHudPending::Gather(AIn);
  if (Ability.IsAttackAbilityPromptOpen()) {
    TestTrue(TEXT("ability: compact boost, two buttons"), M.Compact == EUmPendingCompact::Boost && M.bConfirm && M.bSecondary && M.Title.IsEmpty());
    TestEqual(TEXT("ability: «Атаковать с BOOST» refused until a card is picked"), M.ConfirmWhy.Key, FName(TEXT("why.pick.count")));
    const FUmPendingPlan BP = UmHudPending::Plan(M, Frame(Canvases[0]), TMap<FName, FString>(), &Measure);
    TestEqual(TEXT("ability: only the two buttons"), BP.Buttons.Num(), 2);
  } else {
    AddInfo(TEXT("ability prompt needs an attack draft state - covered live"));
  }
  // ---- the opponent's choice: grey, the source card; the line only when STATUS does not say it ----
  FS09CommandUi Opp;
  Opp.ViewerId = TEXT("p1");
  FS08PendingEffect Hiss;
  Hiss.Id = TEXT("discard-choice-cat-hiss-after-0-21");
  Hiss.PlayerId = TEXT("p2");
  Hiss.Type = TEXT("DISCARD_CARDS");
  Opp.PendingQueue.Add(Hiss);
  Opp.bHasPendingChoice = true;
  UmHudPending::FUmPendingInput OIn;
  OIn.bLive = true;
  OIn.ViewerId = TEXT("p1");
  OIn.Ui = &Opp;
  FS09CardView HissCard;
  HissCard.CardId = TEXT("cat-hiss");
  HissCard.Name = TEXT("Hiss and Slither");
  OIn.Known.Add(HissCard);
  OIn.bStatusSaysOpp = false;
  M = UmHudPending::Gather(OIn);
  TestTrue(TEXT("opp: grey, the source card and the line"), M.View == EUmPendingView::Opp && M.Title == TEXT("Hiss and Slither") && !M.Text.IsEmpty());
  FUmPendingPlan OP = UmHudPending::Plan(M, Frame(Canvases[0]), TMap<FName, FString>(), &Measure);
  TestTrue(TEXT("opp: >= 320 su, no buttons"), OP.Panel.GetSize().X >= 320.0 && OP.Buttons.Num() == 0);
  OIn.bStatusSaysOpp = true;
  M = UmHudPending::Gather(OIn);
  TestTrue(TEXT("opp: STATUS says it - only the card (one text once)"), M.View == EUmPendingView::Opp && M.Text.IsEmpty());
  OIn.Known.Reset();
  TestEqual(TEXT("opp: nothing to add - hidden"), UmHudPending::Gather(OIn).View, EUmPendingView::Hidden);
  P->SetFrame(Frame(Canvases[0]));
  OIn.Known.Add(HissCard);
  P->ApplyModel(UmHudPending::Gather(OIn));
  TestTrue(TEXT("opp SHOT state=opp tone=grey"), ShotOf(P).Contains(TEXT("state=opp")) && ShotOf(P).Contains(TEXT("tone=grey")));
  // ---- after the combat: my choice waits grey ----
  In.bCombatStaging = true;
  M = UmHudPending::Gather(In);
  TestTrue(TEXT("after-combat: grey with «Выполните после боя»"), M.View == EUmPendingView::AfterCombat && !M.Text.IsEmpty() && !M.bCollapse);
  P->ApplyModel(M);
  TestTrue(TEXT("after-combat SHOT state=compact wait=combat"), ShotOf(P).Contains(TEXT("state=compact")) && ShotOf(P).Contains(TEXT("wait=combat")));
  // ---- the toast of a repeating optional trigger ----
  In.bCombatStaging = false;
  FS09PendingPresenter Presenter;
  Ui.PendingChoice.bOptional = true;
  Presenter.Observe(Ui.PendingChoice, 1);
  FS09PendingChoiceCommand Cmd;
  Cmd.EffectId = Ui.PendingChoice.Id;
  Cmd.FighterId = TEXT("f-h1");
  Presenter.Remember(Ui.PendingChoice, FS09PendingVariant::FromCommand(Cmd));
  Presenter.Clear();
  FS08PendingEffect Again = Ui.PendingChoice;
  Again.Id = TEXT("cat-hounds-after-0-p9");
  Ui.PendingChoice = Again;
  Presenter.Observe(Again, 3);
  In.Presenter = &Presenter;
  In.RememberedChoice = TEXT("Harpies 1");
  M = UmHudPending::Gather(In);
  if (Presenter.Present == ES09PendingPresent::Toast) {
    TestEqual(TEXT("toast"), M.View, EUmPendingView::Toast);
    TestTrue(TEXT("toast: «В прошлый раз: Harpies 1»"), M.Text.Contains(TEXT("Harpies 1")));
    FUmPendingFrame TF = Frame(Canvases[0]);
    TF.ToastSu = FBox2D(FVector2D(680.0, 800.0), FVector2D(1240.0, 848.0));
    const FUmPendingPlan TP = UmHudPending::Plan(M, TF, KeyLabels(true), &Measure);
    TestTrue(TEXT("toast: 560 x 48 at its place, three key chips"), FMath::IsNearlyEqual(TP.Panel.GetSize().X, 560.0) && TP.Panel.GetSize().Y >= 48.0 &&
                                                                       FMath::IsNearlyEqual(TP.Panel.Max.Y, 848.0) && TP.Keys.Num() == 3);
  } else {
    AddInfo(TEXT("the presenter chose a non-toast form for this signature"));
  }
  return true;
}

// ----------------------------------------------------------------------------------------------------------- Source

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPendingSourceTest,
    "Unmatched.S08.Hud.Pending.Source the source card from the effect id, discard-choice, ability, text fallback, unknown",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPendingSourceTest::RunTest(const FString&) {
  TArray<FS09CardView> Known;
  FS09CardView A;
  A.CardId = TEXT("cmq7d7b1c00o1wi74sjfulnr0");
  A.Name = TEXT("Swift Strike");
  A.NameRu = TEXT("Swift Strike");
  Known.Add(A);
  FS09CardView B;
  B.CardId = TEXT("cmq7d7b4500riwi74bl62p4i9");
  B.Name = TEXT("Hiss and Slither");
  B.NameRu = TEXT("Шипение и извивание");
  B.Text = TEXT("Your opponent discards 1 card.");
  Known.Add(B);
  TMap<FString, FString> Heroes;
  Heroes.Add(TEXT("p0"), TEXT("Medusa"));
  FS08PendingEffect H;
  H.PlayerId = TEXT("p1");
  H.Id = TEXT("cmq7d7b1c00o1wi74sjfulnr0-after-0-p0");  // run I Sarpedon joiner: Swift Strike's after-combat MOVE
  TestEqual(TEXT("catalog id prefix"), UmHudPending::SourceName(H, Known, Heroes, {}, true), FString(TEXT("Swift Strike")));
  H.Id = TEXT("discard-choice-cmq7d7b4500riwi74bl62p4i9-after-0-21");  // run I: Hiss and Slither's DISCARD_CARDS
  TestEqual(TEXT("discard-choice: RU name"), UmHudPending::SourceName(H, Known, Heroes, {}, true), FString(TEXT("Шипение и извивание")));
  TestEqual(TEXT("discard-choice: EN name"), UmHudPending::SourceName(H, Known, Heroes, {}, false), FString(TEXT("Hiss and Slither")));
  H.Id = TEXT("ability-medusa-target-p0");
  H.PlayerId = TEXT("p0");
  TestEqual(TEXT("a hero ability: the hero"), UmHudPending::SourceName(H, Known, Heroes, {}, true), FString(TEXT("Medusa")));
  H.Id = TEXT("unknown-effect-p0");
  H.Text = TEXT("discards 1 card");
  TestEqual(TEXT("the text fallback in the owner's discard"), UmHudPending::SourceName(H, {}, Heroes, Known, false), FString(TEXT("Hiss and Slither")));
  H.Text = TEXT("nothing like it");
  TestEqual(TEXT("unknown: ''"), UmHudPending::SourceName(H, {}, Heroes, Known, false), FString());
  TestEqual(TEXT("first sentence"), UmHudPending::FirstSentence(TEXT("Choose any space in Merlin's zone. Deal 2 damage.")),
            FString(TEXT("Choose any space in Merlin's zone.")));
  return true;
}

// ------------------------------------------------------------------------------------------------------------- Slot

namespace UmPendingTest {
FS09SlotCard SlotCard(ES09SlotRibbon Ribbon, bool bOpp, int32 Seq) {
  FS09SlotCard C;
  C.Card.InstanceId = FString::Printf(TEXT("cat-x::%d"), Seq);
  C.Card.CardId = TEXT("cat-x");
  C.Card.Name = Ribbon == ES09SlotRibbon::Boosted ? TEXT("Noble Sacrifice") : TEXT("Restless Spirits");
  C.Card.BoostValue = 3;
  C.Card.bHasBoostValue = true;
  C.OwnerId = bOpp ? TEXT("p2") : TEXT("p1");
  C.bOpponent = bOpp;
  C.Ribbon = Ribbon;
  C.Seq = Seq;
  return C;
}

/** One frame: the S09 model at Now, the widget fed as TickUmSourceSlot does. */
void Feed(FS09SourceSlot& Model, UUmHudSourceSlot* W, int64 Now, bool bBusy, const FVector2D& From = FVector2D(1700.0, 200.0)) {
  TArray<FString> Lines;
  bool bReleased = false;
  Model.Tick(Now, bBusy, Lines, bReleased);
  W->SetClockOverrideMs(static_cast<double>(Now));
  FUmSlotModel M;
  M.bShow = Model.IsVisible();
  M.Revision = Model.GetRevision();
  M.Phase = UmHudSourceSlot::PhaseOf(Model.GetState());
  M.Card = Model.GetCard().Card;
  M.Ribbon = Model.GetCard().Ribbon;
  M.bOpponent = Model.GetCard().bOpponent;
  M.OwnerName = M.bOpponent ? TEXT("King Arthur") : TEXT("Medusa");
  M.HeroSlug = M.bOpponent ? TEXT("king-arthur") : TEXT("medusa");
  M.Seq = Model.GetCard().Seq;
  M.Boost = M.Ribbon == ES09SlotRibbon::Boosted ? 3 : UmCardWidget::NoBoostChip;
  M.FlyT = Model.FlyT(Now);
  if (Model.HoldsEffect() && Model.GetState() == ES09SlotState::Hold) {
    M.HoldFrac = FMath::Clamp(1.0f - static_cast<float>(Model.ReleaseAtMs() - Now) / FS09SourceSlot::OppSchemeHoldMs, 0.0f, 1.0f);
  }
  M.FlyFromSu = From;
  W->ApplyModel(M);
}

FUmSlotFrame SlotFrame(bool bClassS, float Px) {
  FUmSlotFrame F;
  F.bClassS = bClassS;
  F.PxPerSu = Px;
  F.CardSu = bClassS ? FBox2D(FVector2D(16.0, 64.0), FVector2D(136.0, 230.0)) : FBox2D(FVector2D(24.0, 84.0), FVector2D(214.0, 348.0));
  F.OriginSu = F.CardSu.Min;
  return F;
}
}  // namespace UmPendingTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmSlotTimelineTest,
    "Unmatched.S08.Hud.Slot.Timeline own scheme fly 200 then 150 leave, opponent scheme 200 then hold 1500 then 150, boost at least 1000",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmSlotTimelineTest::RunTest(const FString&) {
  using namespace UmPendingTest;
  FWorld World(TEXT("UmSlotTimeline"));
  if (!TestNotNull(TEXT("world"), World.World)) return false;
  UUmHudSourceSlot* W = CreateWidget<UUmHudSourceSlot>(World.World, UUmHudSourceSlot::StaticClass());
  if (!TestNotNull(TEXT("slot"), W)) return false;
  W->SetReducedForTest(0);
  W->SetSyncLoad(true);
  W->SetFrame(SlotFrame(false, 1.0f));
  TArray<FString> Lines;
  bool bReleased = false;
  // ---- own scheme: fly 200, the effect at once, 500 ms after arrival, then the widget's 150 ms leave ----
  FS09SourceSlot Own;
  Own.Show(SlotCard(ES09SlotRibbon::Scheme, false, 10), 0, false, Lines, bReleased);
  Feed(Own, W, 100, false, FVector2D(700.0, 960.0));
  TestEqual(TEXT("own: fly at 100"), W->GetPhase(), EUmSlotPhase::Fly);
  TestFalse(TEXT("own: the card in flight is off its slot"), W->Card->GetRenderTransform().Translation.IsNearlyZero());
  TestTrue(TEXT("own: no ribbon in flight"), W->Ribbon->GetVisibility() == ESlateVisibility::Collapsed);
  Feed(Own, W, 250, false);
  TestEqual(TEXT("own: shown on arrival"), W->GetPhase(), EUmSlotPhase::Show);
  TestTrue(TEXT("own: at rest in SLOT"), W->Card->GetRenderTransform().Translation.IsNearlyZero());
  TestTrue(TEXT("own: the ribbon on arrival"), W->Ribbon->GetVisibility() != ESlateVisibility::Collapsed);
  Feed(Own, W, 690, false);
  TestEqual(TEXT("own: still shown before 200 + 500"), W->GetPhase(), EUmSlotPhase::Show);
  Feed(Own, W, 700, false);
  TestEqual(TEXT("own: the leave starts with the model's end"), W->GetPhase(), EUmSlotPhase::Fade);
  Feed(Own, W, 775, false);
  TestTrue(TEXT("own: half way at 75 ms"), FMath::IsNearlyEqual(W->GetLeaveAlpha(), 0.5f, 0.02f));
  Feed(Own, W, 851, false);
  TestEqual(TEXT("own: gone after 150 ms (04 §2.8)"), W->GetPhase(), EUmSlotPhase::Hidden);
  // ---- the opponent's scheme: fly 200 -> hold 1500 (the bar) -> the effect -> while busy -> 150 ----
  FS09SourceSlot Opp;
  Opp.Show(SlotCard(ES09SlotRibbon::Scheme, true, 20), 1000, false, Lines, bReleased);
  Feed(Opp, W, 1100, false);
  TestEqual(TEXT("opp: fly"), W->GetPhase(), EUmSlotPhase::Fly);
  Feed(Opp, W, 1950, false);
  TestEqual(TEXT("opp: hold"), W->GetPhase(), EUmSlotPhase::Hold);
  TestTrue(TEXT("opp: the hold bar shown"), W->HoldFill && W->HoldFill->GetVisibility() != ESlateVisibility::Collapsed);
  TestTrue(TEXT("opp: half of the 1500 ms hold"), FMath::IsNearlyEqual(W->GetModel().HoldFrac, 0.5f, 0.01f));
  {
    TArray<FString> Shot;
    W->CollectShotLines(Shot);
    TestTrue(TEXT("opp SHOT state=hold fighter=opp ribbon=scheme hold=0.50"), Shot.Num() == 1 && Shot[0].Contains(TEXT("state=hold")) &&
                                                                               Shot[0].Contains(TEXT("fighter=opp")) && Shot[0].Contains(TEXT("hold=0.50")));
    TestFalse(TEXT("no card name in the SHOT line"), Shot.Num() == 1 && Shot[0].Contains(TEXT("Restless")));
  }
  Feed(Opp, W, 2700, true);  // released at 1000 + 200 + 1500 = 2700
  Feed(Opp, W, 2710, true);
  TestEqual(TEXT("opp: shown while its effect runs"), W->GetPhase(), EUmSlotPhase::Show);
  Feed(Opp, W, 3500, true);
  TestEqual(TEXT("opp: still shown, busy"), W->GetPhase(), EUmSlotPhase::Show);
  Feed(Opp, W, 3600, false);
  TestEqual(TEXT("opp: the effect ended - the leave"), W->GetPhase(), EUmSlotPhase::Fade);
  Feed(Opp, W, 3751, false);
  TestEqual(TEXT("opp: gone after 150"), W->GetPhase(), EUmSlotPhase::Hidden);
  // ---- the opponent's maneuver boost: at least 1000 ms, then 150 (the model fades 250 - the widget leaves at 150) ----
  FS09SourceSlot Boost;
  Boost.Show(SlotCard(ES09SlotRibbon::Boosted, true, 30), 5000, false, Lines, bReleased);
  Feed(Boost, W, 5999, false);
  TestNotEqual(TEXT("boost: shown before 1000"), W->GetPhase(), EUmSlotPhase::Hidden);
  TestFalse(TEXT("boost: not leaving before 1000"), W->IsLeaving());
  Feed(Boost, W, 6000, false);
  TestEqual(TEXT("boost: the leave at 1000"), W->GetPhase(), EUmSlotPhase::Fade);
  Feed(Boost, W, 6151, false);
  TestEqual(TEXT("boost: gone after 150 (the model still fades)"), W->GetPhase(), EUmSlotPhase::Hidden);
  // ---- a new card replaces a leaving one at once (CUE-006 replace) ----
  FS09SourceSlot Replace;
  Replace.Show(SlotCard(ES09SlotRibbon::Boosted, true, 40), 7000, false, Lines, bReleased);
  Feed(Replace, W, 7100, false);
  Feed(Replace, W, 8000, false);
  TestTrue(TEXT("replace: leaving"), W->IsLeaving());
  Replace.Show(SlotCard(ES09SlotRibbon::Scheme, true, 41), 8010, false, Lines, bReleased);
  Feed(Replace, W, 8020, false);
  TestTrue(TEXT("replace: the new card, no leave"), !W->IsLeaving() && W->GetModel().Seq == 41 && W->GetPhase() == EUmSlotPhase::Fly);
  // reduced motion: no fly, the leave 100 ms
  TestTrue(TEXT("reduced: the leave is 100 ms"), FMath::IsNearlyEqual(UmHudSourceSlot::LeaveAlpha(50.0f, true), 0.5f, 0.01f));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmSlotRibbonTest,
    "Unmatched.S08.Hud.Slot.Ribbon scheme boost discard glyphs, plate and ink tokens, owner on the ribbon, S boost 190 su, 32 su glyph",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmSlotRibbonTest::RunTest(const FString&) {
  using namespace UmPendingTest;
  FRu Ru;
  FWorld World(TEXT("UmSlotRibbon"));
  if (!TestNotNull(TEXT("world"), World.World)) return false;
  TestEqual(TEXT("IC-50"), UmHudSourceSlot::RibbonIcon(ES09SlotRibbon::Scheme), FName(TEXT("marker-slot-scheme")));
  TestEqual(TEXT("IC-51"), UmHudSourceSlot::RibbonIcon(ES09SlotRibbon::Boosted), FName(TEXT("marker-slot-boost")));
  TestEqual(TEXT("IC-52"), UmHudSourceSlot::RibbonIcon(ES09SlotRibbon::Discarded), FName(TEXT("marker-slot-discard")));
  TestEqual(TEXT("СХЕМА plate card.type.scheme"), UmHudSourceSlot::RibbonFill(ES09SlotRibbon::Scheme), FName(TEXT("card.type.scheme")));
  TestEqual(TEXT("СХЕМА ink card.navy"), UmHudSourceSlot::RibbonInk(ES09SlotRibbon::Scheme), FName(TEXT("card.navy")));
  TestEqual(TEXT("BOOST ink card.glyph"), UmHudSourceSlot::RibbonInk(ES09SlotRibbon::Boosted), FName(TEXT("card.glyph")));
  TestEqual(TEXT("СБРОС ink text.secondary"), UmHudSourceSlot::RibbonInk(ES09SlotRibbon::Discarded), FName(TEXT("text.secondary")));
  TestEqual(TEXT("glyph 24 su at 1 px / su"), UmHudSourceSlot::GlyphSu(1.0f), 24.0f);
  TestEqual(TEXT("glyph 32 su below 1 px / su (IC-34 П-2)"), UmHudSourceSlot::GlyphSu(0.75f), 32.0f);
  TestEqual(TEXT("one row 28 su"), UmHudSourceSlot::RibbonHeightSu(1, 24.0f), 28.0f);
  TestEqual(TEXT("two rows 46 su"), UmHudSourceSlot::RibbonHeightSu(2, 24.0f), 46.0f);
  TestEqual(TEXT("S BOOST ribbon 190 su"), UmHudSourceSlot::RibbonWidthSu(true, 120.0f, ES09SlotRibbon::Boosted), 190.0f);
  TestEqual(TEXT("S СХЕМА ribbon = the card"), UmHudSourceSlot::RibbonWidthSu(true, 120.0f, ES09SlotRibbon::Scheme), 120.0f);
  UUmHudSourceSlot* W = CreateWidget<UUmHudSourceSlot>(World.World, UUmHudSourceSlot::StaticClass());
  if (!TestNotNull(TEXT("slot"), W)) return false;
  W->SetSyncLoad(true);
  for (const bool bS : {false, true}) {
    W->SetFrame(SlotFrame(bS, bS ? 1.5f : 1.0f));
    FS09SourceSlot Model;
    TArray<FString> Lines;
    bool bReleased = false;
    Model.Show(SlotCard(ES09SlotRibbon::Scheme, true, bS ? 51 : 50), 0, true, Lines, bReleased);  // reduced: at rest at once
    Feed(Model, W, 0, true);
    const FString Text = W->RibbonText ? W->RibbonText->GetText().ToString() : FString();
    TestTrue(FString::Printf(TEXT("%s: «СХЕМА · King Arthur»"), bS ? TEXT("S") : TEXT("L")), Text.Contains(TEXT("King Arthur")) && Text.Contains(TEXT("·")));
    if (bS) {
      TestTrue(TEXT("S: the owner wraps (120 su), the ribbon grows - never cut"), W->GetRibbonRows() >= 2 && W->RibbonRectSu().GetSize().Y > 28.0);
    } else {
      TestEqual(TEXT("L: one row 28 su"), static_cast<float>(W->RibbonRectSu().GetSize().Y), 28.0f);
    }
    TestTrue(TEXT("the ribbon 4 su under the card"), FMath::IsNearlyEqual(W->RibbonRectSu().Min.Y - SlotFrame(bS, 1.0f).CardSu.Max.Y, 4.0, 0.01));
    TestEqual(TEXT("the IC-50 glyph"), W->RibbonIcon ? W->RibbonIcon->GetIconId() : FName(), FName(TEXT("marker-slot-scheme")));
    TArray<FString> Shot;
    W->CollectShotLines(Shot);
    TestTrue(TEXT("SHOT ribbon=scheme face=1"), Shot.Num() == 1 && Shot[0].Contains(TEXT("ribbon=scheme")) && Shot[0].Contains(TEXT("face=1")));
    TestFalse(TEXT("no card name in SHOT"), Shot.Num() == 1 && Shot[0].Contains(TEXT("Restless")));
  }
  // BOOST: «+3» inside the ribbon, the S ribbon 190 su; the opponent's boost face (public after the maneuver, SD-54)
  W->SetFrame(SlotFrame(true, 0.9f));
  FS09SourceSlot Boost;
  TArray<FString> Lines;
  bool bReleased = false;
  Boost.Show(SlotCard(ES09SlotRibbon::Boosted, true, 60), 0, true, Lines, bReleased);
  Feed(Boost, W, 0, true);
  TestTrue(TEXT("BOOST: the chip shown"), W->BoostChip && W->BoostChip->GetVisibility() != ESlateVisibility::Collapsed);
  TestEqual(TEXT("BOOST: «+3»"), W->BoostText ? W->BoostText->GetText().ToString() : FString(), FString(TEXT("+3")));
  TestEqual(TEXT("BOOST S: 190 su ribbon"), static_cast<float>(W->RibbonRectSu().GetSize().X), 190.0f);
  TestEqual(TEXT("below 1 px / su: the 32 su glyph"), W->RibbonIcon ? W->RibbonIcon->GetDisplaySizeSu() : 0.0f, 32.0f);
  TestTrue(TEXT("the slot card is not the boost chip's owner"), W->Card && W->Card->GetBoost() == UmCardWidget::NoBoostChip);
  return true;
}

// ------------------------------------------------------------------------------------------------- VS-3 small fixes

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudFixesVs3Test,
    "Unmatched.S08.Hud.Fixes.Vs3 empty lowered hand visible 0, the right boost chip on the card corner, no-defense text, sidekick number",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudFixesVs3Test::RunTest(const FString&) {
  using namespace UmPendingTest;
  FRu Ru;
  FWorld World(TEXT("UmFixesVs3"));
  if (!TestNotNull(TEXT("world"), World.World)) return false;
  // item 2: the empty lowered hand writes visible=0, not 'geom=unpainted visible=1'
  UUmHudHand* Hand = CreateWidget<UUmHudHand>(World.World, UUmHudHand::StaticClass());
  if (TestNotNull(TEXT("hand"), Hand)) {
    const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1920.0, 1080.0), 1.0f, nullptr);
    Hand->SetFrame(FUmHandFrame::FromLayout(L, 1.0f));
    FUmHandModel M;
    M.bLowered = true;
    M.HeroSlug = TEXT("medusa");
    Hand->ApplyModel(M);
    TArray<FString> Shot;
    Hand->CollectShotLines(Shot);
    TestTrue(TEXT("item 2: a line"), Shot.Num() >= 1);
    if (Shot.Num() >= 1) {
      TestFalse(TEXT("item 2: never 'unpainted visible=1'"), Shot[0].Contains(TEXT("geom=unpainted visible=1")));
    }
  }
  // item 12: the right chip sits on the drawn card's corner - 8 su of it on the frame, 4 su in from the right edge
  UUmCardWidget* Card = CreateWidget<UUmCardWidget>(World.World, UUmCardWidget::StaticClass());
  if (TestNotNull(TEXT("card"), Card)) {
    Card->SetSyncLoad(true);
    FS09CardView V;
    V.InstanceId = TEXT("x::0");
    V.Name = TEXT("Noble Sacrifice");
    FUmCardState S;
    S.Show = EUmCardShow::ClassSCombat;
    S.HeroSlug = TEXT("king-arthur");
    S.bFaceDown = true;
    S.PxPerSu = 1.125f;
    Card->ApplyModel(V, S);
    Card->SetBoostChip(2);
    Card->SetChipRightAbove(true);
    const UOverlaySlot* Slot = Card->BoostChip ? Cast<UOverlaySlot>(Card->BoostChip->Slot) : nullptr;
    if (TestNotNull(TEXT("chip slot"), Slot)) {
      const float Chip = Card->GetChipSu();
      TestEqual(TEXT("item 12: right aligned"), Slot->GetHorizontalAlignment(), HAlign_Right);
      TestTrue(TEXT("item 12: 8 su of it on the frame (not 4 su over the edge)"),
               FMath::IsNearlyEqual(Slot->GetPadding().Top, -(Chip - UmCardWidget::ChipOnFrameSu)));
      TestTrue(TEXT("item 12: 4 su in from the right edge"), FMath::IsNearlyEqual(Slot->GetPadding().Right, UmCardWidget::ChipCornerInsetSu));
    }
  }
  // item 13: «Нет защиты» under the stamp (04 §3.8)
  UUmHudCombatEdge* Edge = CreateWidget<UUmHudCombatEdge>(World.World, UUmHudCombatEdge::StaticClass());
  if (TestNotNull(TEXT("edge"), Edge)) {
    FUmCombatEdgeFrame F;
    F.CardSu = FBox2D(FVector2D(1666.0, 360.0), FVector2D(1896.0, 679.0));
    F.OriginSu = FVector2D(1666.0, 332.0);
    Edge->SetSide(EUmEdgeSide::Opp);
    Edge->SetFrame(F);
    FUmCombatEdgeModel M;
    M.bShow = true;
    M.Role = EUmEdgeRole::Defense;
    M.State = EUmEdgeState::NoDefense;
    M.CombatKey = TEXT("c1");
    M.FighterName = TEXT("King Arthur");
    Edge->ApplyModel(M);
    TestTrue(TEXT("item 13: the label shown"), Edge->SlotText && Edge->SlotText->GetVisibility() != ESlateVisibility::Collapsed);
    TestTrue(TEXT("item 13: «Нет защиты»"), Edge->SlotText && Edge->SlotText->GetText().EqualTo(UmText::Get(EUmTable::Hud, TEXT("hud.combat.nodefense"))));
    TArray<FString> Shot;
    Edge->CollectShotLines(Shot);
    TestTrue(TEXT("item 13: SHOT stampText=1"), Shot.Num() >= 1 && Shot.Last().Contains(TEXT("stampText=1")));
  }
  // Z-1 leftover: the HUD badge number is the base digit's rule
  for (const TCHAR* Label : {TEXT("Harpies 1"), TEXT("Harpies 2"), TEXT("Harpies 3")}) {
    FS08BoardFighter F;
    F.Label = Label;
    TestEqual(FString::Printf(TEXT("%s: badge = base digit"), Label), UmHudPanel::SidekickNumber(Label), S08HeroesV2::HarpyNumber(F));
  }
  TestEqual(TEXT("«Merlin» -> 0 (no badge)"), UmHudPanel::SidekickNumber(TEXT("Merlin")), 0);
  TestEqual(TEXT("«Harpies 7» clamps like the base digit"), UmHudPanel::SidekickNumber(TEXT("Harpies 7")), 3);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
