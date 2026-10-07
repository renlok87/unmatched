// VS-4 V4 (H13) automation tests (docs/game-design/visual/06-tasks/screens.csv SC-21, SC-22, SC-23;
// cards-portraits.csv CP-21, CP-22; 04-hud-spec.md §1.7, §2.6, §2.9, §7.1):
//   Unmatched.S08.Hud.Screens.Inspect.Tree     the code tree and WBP_UI_SCR_INSPECT: every BindWidget of SC-21 / SC-23
//                                              (Card, TitleText, TypeIcon, TypeText, ValueText, BoostText, BodyText,
//                                              CopiesText, LangToggle, CloseButton, DeckGrid, BackButton); a modal, hidden
//                                              until opened, no primary button (ВР-VS3-SC21-06); the frame 852 x 688 / S 784
//                                              x 600 inside the safe margins on every canvas of 04 §3.6.
//   Unmatched.S08.Hud.Inspector.Cap            CP-22: the RU scan 452 x 627 su at 1080p 100 % (scale <= 1.6, uncapped),
//                                              306 x 425 su = 459 x 637 px at 1080p 150 % (class S, capped, the frame hugs
//                                              the scan centred in the 400 x 555 slot), EN 400 x 558 in 408 x 566; the
//                                              widget's CARD-ART line says show=inspector|classS-inspector scale <= 1.6.
//   Unmatched.S08.Hud.Screens.Inspect.Paths    the six paths of 04 §1.7 (hand, discard, log, deck row, combat, slot) + the
//                                              key I + the opponent's backs build the right model (own / opponent card,
//                                              the copies of the own deck n = copies - hand - discard, hidden), the source
//                                              in the trace; the decks: King Arthur 16 / 30, Medusa 11 / 30, catalogue order.
//   Unmatched.S08.Hud.Screens.Inspect.Input    read-only (UI-INP-006): «×», Esc, I, a right click close it once each and
//                                              nothing but OnClose / OnPage is ever called; Tab switches RU / EN; the grid:
//                                              a card opens in the same modal with «×N» and «Назад», Backspace / «Назад»
//                                              return, the wheel moves whole rows; the 150 ms switch, reduced 100.
//   Unmatched.S08.Hud.Screens.Inspect.Privacy  SC-22 (QA-005): a hidden card keeps no name, type, value, text or copies -
//                                              in the model, the view and the SHOT / CARD-ART lines; the back of the owner.
//   Unmatched.S08.Hud.Card.PlayedFlash         CP-21: 500 ms x speed (0 = none), reduced 100; opacity 1 / 0.8 / 0.5 / 0 at
//                                              0 / 100 / 250 / 500 ms; the G-CUE lines of CUE-006 subject=card.
//   Unmatched.S08.Hud.DeckPanel.MarksFit       VS-3 item 11 (ВР-VS4-59): the mark chips hold their label line and end 2 su
//                                              over the row's bottom, under the name's descenders; «Весь состав» on the
//                                              filter row inside the panel in L and S.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Screens.Inspect+Unmatched.S08.Hud.Inspector" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../S08ArtLook.h"
#include "../S08IconMotion.h"
#include "UmButton.h"
#include "UmCardGallery.h"
#include "UmCardMedia.h"
#include "UmCardWidget.h"
#include "UmDeckRow.h"
#include "UmDecksGallery.h"
#include "UmGameHud.h"
#include "UmHudDeckPanel.h"
#include "UmHudScale.h"
#include "UmScreenInspect.h"
#include "UmText.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "InputCoreTypes.h"
#include "Misc/AutomationTest.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace UmInspectTest {
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

bool Near(double A, double B, double Tol = 0.6) { return FMath::Abs(A - B) <= Tol; }

/** The HB-26 run I moment of the sheets: own Medusa (Gaze of Stone x2 in hand; A Momentary Glance, Feint discarded),
 *  the opponent King Arthur (Swift Strike discarded, 5 in hand). */
struct FMatch {
  FS09DeckList Medusa;
  FS09DeckList Arthur;
  FS09PlayerPanel Own;
  FS09PlayerPanel Opp;
  TArray<FS09DeckList> Lists;
  FUmInspectContext C;
  static FS09CardView Of(const FS09DeckList& L, const TCHAR* Name, int32 Copy) {
    FS09CardView V;
    for (const FS09DeckListCard& X : L.Cards) {
      if (X.Name == Name) V = UmInspect::DeckCardView(X);
    }
    V.InstanceId = FString::Printf(TEXT("t::%s-%d"), Name, Copy);
    return V;
  }
  FMatch() {
    Medusa = UmDecksGallery::LoadList(TEXT("medusa"), TEXT("p-medusa"));
    Arthur = UmDecksGallery::LoadList(TEXT("king-arthur"), TEXT("p-arthur"));
    Own.PlayerId = TEXT("p-medusa");
    Own.bIsViewer = true;
    Own.Cards = {Of(Medusa, TEXT("Gaze of Stone"), 0), Of(Medusa, TEXT("Gaze of Stone"), 1), Of(Medusa, TEXT("Snipe"), 0)};
    Own.Discard = {Of(Medusa, TEXT("A Momentary Glance"), 0), Of(Medusa, TEXT("Feint"), 0)};
    Opp.PlayerId = TEXT("p-arthur");
    Opp.HandCount = 5;
    Opp.Discard = {Of(Arthur, TEXT("Swift Strike"), 0)};
    Lists = {Medusa, Arthur};
    C.Own = &Own;
    C.Opp = &Opp;
    C.OwnHero = TEXT("Medusa");
    C.OwnSlug = TEXT("medusa");
    C.OppHero = TEXT("King Arthur");
    C.OppSlug = TEXT("king-arthur");
    C.Lists = &Lists;
  }
};

UUmScreenInspect* Make(UWorld* World, bool bWbp = true) {
  UClass* Cls = bWbp ? UUmScreenInspect::WidgetClass() : UUmScreenInspect::StaticClass();
  UUmScreenInspect* S = CreateWidget<UUmScreenInspect>(World, Cls);
  if (S) {
    S->SetSyncLoadForSheet(true);
    S->SetSheetClockMs(1000.0);
    S->SetReducedForTest(0);
  }
  return S;
}
}  // namespace UmInspectTest

using namespace UmInspectTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmInspectTreeTest, "Unmatched.S08.Hud.Screens.Inspect.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmInspectTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmInspectTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  UUmScreenInspect* S = Make(W.World, false);
  FString Missing;
  TestTrue(FString::Printf(TEXT("the code tree: every part (%s)"), *Missing), S && S->UsesCodeDefaultTree() && S->HasAllParts(&Missing));
  if (!S) return false;
  TestTrue(TEXT("a modal, UI-SCR-INSPECT, hidden until opened"),
           S->IsModal() && S->GetUiId() == TEXT("UI-SCR-INSPECT") && !S->IsShown() && S->GetVisibility() == ESlateVisibility::Collapsed);
  TestTrue(TEXT("no primary button (ВР-VS3-SC21-06): «×» and «Назад» are normal"),
           S->CloseButton->GetModel().Variant != EUmButtonVariant::Primary && S->BackButton->GetModel().Variant == EUmButtonVariant::Normal);
  TestTrue(TEXT("«×» is the ui-close glyph 32 su with «Закрыть» as its tooltip"),
           S->CloseButton->GetModel().IconName == FName(TEXT("ui-close")) && S->CloseButton->GetModel().HeightSu == 32.0f &&
               S->CloseButton->GetToolTipText().ToString() == TEXT("Закрыть"));
  TestEqual(TEXT("«Назад» (hud.inspect.back)"), S->BackButton->GetModel().Label.ToString(), FString(TEXT("Назад")));
  UClass* Cls = UUmScreenInspect::WidgetClass();
  if (Cls != UUmScreenInspect::StaticClass()) {
    UUmScreenInspect* Wbp = CreateWidget<UUmScreenInspect>(W.World, Cls);
    Missing.Reset();
    TestTrue(FString::Printf(TEXT("WBP_UI_SCR_INSPECT: every part (%s)"), *Missing), Wbp && !Wbp->UsesCodeDefaultTree() && Wbp->HasAllParts(&Missing));
  } else {
    AddInfo(TEXT("WBP_UI_SCR_INSPECT not generated yet (the code tree)"));
  }
  // the frame on every canvas of 04 §3.6: 852 x 688 (S 784 x 600), centred, inside the safe margins
  FMatch M;
  struct FCase {
    FIntPoint Window;
    int32 Percent;
  };
  for (const FCase& C : {FCase{{1920, 1080}, 75}, FCase{{1920, 1080}, 100}, FCase{{1920, 1080}, 150}, FCase{{1280, 720}, 100}, FCase{{1280, 720}, 150}}) {
    const FUmHudScaleState St = UmHudScale::Compute(C.Window, UmHudScale::ProjectDpi(FMath::Min(C.Window.X, C.Window.Y)), C.Percent, false);
    const FVector2D Canvas = FVector2D(C.Window) / St.PxPerSu();
    S->ApplyCanvas(Canvas, St.bClassS, St.PxPerSu());
    S->Open(UmInspect::FromCard(M.Own.Cards[0], EUmInspectSource::Hand, M.C));
    const FBox2D F = S->FrameRectSu();
    const FVector2D Want = UmInspect::ModalSize(St.bClassS);
    const float Mg = S->GetSafeMarginSu();
    TestTrue(FString::Printf(TEXT("%dx%d %d %%: the frame %.0fx%.0f (want %.0fx%.0f) inside the margins"), C.Window.X, C.Window.Y, C.Percent,
                             F.GetSize().X, F.GetSize().Y, Want.X, Want.Y),
             Near(F.GetSize().X, Want.X, 0.01) && Near(F.GetSize().Y, Want.Y, 0.01) && F.Min.X >= Mg - 0.01 && F.Min.Y >= Mg - 0.01 &&
                 F.Max.X <= Canvas.X - Mg + 0.01 && F.Max.Y <= Canvas.Y - Mg + 0.01);
    S->Close(TEXT("owner"));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmInspectorCapTest, "Unmatched.S08.Hud.Inspector.Cap",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmInspectorCapTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmInspectorCap"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  // the fit itself (02 §6.2, ВР-48 / ВР-CP04): RU 287 x 398, EN 250 x 349
  const FUmCardFit Ru100 = UmCardWidget::Fit(UmCardWidget::ShowSize(EUmCardShow::Inspector), UmCardWidget::BandSu, FIntPoint(287, 398), 1.0f);
  TestTrue(FString::Printf(TEXT("1080p 100 %%: RU 452 x 627 su in the 452 x 632 window, uncapped, scale %.3f <= 1.6"), Ru100.Scale),
           Near(Ru100.ScanSu.X, 452.0) && Near(Ru100.ScanSu.Y, 627.0) && Near(Ru100.WindowSu.X, 452.0) && Near(Ru100.WindowSu.Y, 632.0) &&
               !Ru100.bCapped && Ru100.Scale <= 1.6f);
  const FUmCardFit Ru150 = UmCardWidget::Fit(UmCardWidget::ShowSize(EUmCardShow::ClassSInspector), UmCardWidget::BandSu, FIntPoint(287, 398), 1.5f);
  TestTrue(FString::Printf(TEXT("1080p 150 %% (class S slot 400 x 555): 306 x 425 su = 459 x 637 px, capped, scale %.3f; got %.1f x %.1f"),
                           Ru150.Scale, Ru150.ScanSu.X, Ru150.ScanSu.Y),
           Near(Ru150.ScanSu.X, 306.0) && Near(Ru150.ScanSu.Y, 425.0) && Near(Ru150.ScanSu.X * 1.5, 459.0, 1.0) &&
               Near(Ru150.ScanSu.Y * 1.5, 637.0, 1.0) && Ru150.bCapped && Ru150.Scale <= 1.6f + 1.0e-4f);
  TestTrue(TEXT("the capped frame hugs the scan (band 4 su a side, ВР-VS3-SC21-07)"),
           Near(Ru150.CardSu.X, Ru150.ScanSu.X + 8.0, 1.0) && Ru150.CardSu.Y <= 555.0);
  const FUmCardFit En = UmCardWidget::Fit(UmCardWidget::ShowSize(EUmCardShow::Inspector, true), UmCardWidget::BandSu, FIntPoint(250, 349), 1.0f);
  TestTrue(FString::Printf(TEXT("EN 400 x 558 in the 408 x 566 frame (got %.1f x %.1f)"), En.ScanSu.X, En.ScanSu.Y),
           Near(En.ScanSu.X, 400.0) && Near(En.ScanSu.Y, 558.0) && En.Scale <= 1.6f);
  TestEqual(TEXT("classS-inspector 400 x 555"), UmCardWidget::ShowSize(EUmCardShow::ClassSInspector), FVector2D(400.0, 555.0));
  // the widget in the modal: the registry's scan, the CARD-ART line
  FMatch M;
  UUmScreenInspect* S = Make(W.World);
  if (!TestNotNull(TEXT("inspector"), S)) return false;
  S->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
  S->Open(UmInspect::FromCard(M.Own.Cards[0], EUmInspectSource::Hand, M.C));
  const FUmCardFit& Fit = S->Card->GetFit();
  const FString Line = S->Card->ArtLine();
  TestTrue(FString::Printf(TEXT("the modal's card: RU scan, show=inspector, scale <= 1.6 (%s)"), *Line),
           S->Card->GetFace() == EUmCardFace::Ru && Line.Contains(TEXT("show=inspector")) && Fit.Scale <= 1.6f && Near(Fit.ScanSu.X, 452.0));
  const FBox2D Box = S->CardBoxSu();
  TestTrue(TEXT("the card at (24, 24) in the 460 x 640 slot"), Near(Box.Min.X, 24.0, 0.01) && Near(Box.Min.Y, 24.0, 0.01));
  S->ApplyCanvas(FVector2D(1280.0, 720.0), true, 1.5f);
  const FString LineS = S->Card->ArtLine();
  const FBox2D BoxS = S->CardBoxSu();
  TestTrue(FString::Printf(TEXT("class S: show=classS-inspector capped=1 scale <= 1.6, centred in the slot (%s)"), *LineS),
           LineS.Contains(TEXT("show=classS-inspector")) && LineS.Contains(TEXT("capped=1")) && S->Card->GetFit().Scale <= 1.6f + 1.0e-4f &&
               Near(BoxS.Min.X, 24.0, 0.01) && Near(BoxS.GetSize().X, 400.0, 0.01));
  // Tab: the EN scan 408 x 566 (both scans in the registry)
  S->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
  TestTrue(TEXT("both scans: the language toggle is shown"), S->CanToggleLang());
  S->HandleKey(EKeys::Tab);
  TestTrue(FString::Printf(TEXT("Tab: EN scan 400 x 558, the EN name (%s)"), *S->GetTitle()),
           S->IsEnglish() && S->Card->GetFace() == EUmCardFace::En && Near(S->Card->GetFit().ScanSu.X, 400.0) &&
               S->GetTitle() == TEXT("Gaze of Stone"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmInspectPathsTest, "Unmatched.S08.Hud.Screens.Inspect.Paths",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmInspectPathsTest::RunTest(const FString& Parameters) {
  FMatch M;
  TestTrue(TEXT("S01 decks loaded"), M.Medusa.Cards.Num() > 0 && M.Arthur.Cards.Num() > 0);
  // the decks (SC-23 acceptance): King Arthur 16 unique / 30, Medusa 11 / 30, the catalogue order of the list
  const FUmInspectModel DeckOwn = UmInspect::FromDeck(true, EUmInspectSource::DeckAll, M.C);
  const FUmInspectModel DeckOpp = UmInspect::FromDeck(false, EUmInspectSource::DeckAll, M.C);
  TestTrue(FString::Printf(TEXT("Medusa 11 / %d"), UmInspect::CopiesSum(DeckOwn.Deck)), DeckOwn.Mode == EUmInspectMode::Deck &&
                                                                                          DeckOwn.Deck.Num() == 11 && UmInspect::CopiesSum(DeckOwn.Deck) == 30);
  TestTrue(FString::Printf(TEXT("King Arthur 16 / %d"), UmInspect::CopiesSum(DeckOpp.Deck)), DeckOpp.Mode == EUmInspectMode::Deck &&
                                                                                               DeckOpp.Deck.Num() == 16 && UmInspect::CopiesSum(DeckOpp.Deck) == 30);
  bool bOrder = DeckOwn.Deck.Num() == M.Medusa.Cards.Num();
  for (int32 I = 0; bOrder && I < DeckOwn.Deck.Num(); ++I) bOrder &= DeckOwn.Deck[I].CardId == M.Medusa.Cards[I].CardId;
  TestTrue(TEXT("the grid keeps the list's catalogue order (F-05)"), bOrder);
  TestTrue(TEXT("no list - no grid"), UmInspect::FromDeck(true, EUmInspectSource::DeckAll, FUmInspectContext()).Mode != EUmInspectMode::Deck);
  // 1 hand: own, the copies of the own deck n = 3 - 2 - 0
  const FUmInspectModel Hand = UmInspect::FromCard(M.Own.Cards[0], EUmInspectSource::Hand, M.C);
  TestTrue(FString::Printf(TEXT("hand: own Medusa, copies 1 / 2 / 0 (%d / %d / %d)"), Hand.Copies.Deck, Hand.Copies.Hand, Hand.Copies.Discard),
           Hand.Mode == EUmInspectMode::Own && Hand.HeroSlug == TEXT("medusa") && Hand.Copies.bKnown && Hand.Copies.Deck == 1 &&
               Hand.Copies.Hand == 2 && Hand.Copies.Discard == 0);
  // 2 discard: own (Feint, 1 in discard) and the opponent's (no copies line)
  const FUmInspectModel OwnDiscard = UmInspect::FromCard(M.Own.Discard[1], EUmInspectSource::Discard, M.C);
  TestTrue(TEXT("own discard: copies with d = 1"), OwnDiscard.Copies.bKnown && OwnDiscard.Copies.Discard == 1 && OwnDiscard.HeroSlug == TEXT("medusa"));
  const FUmInspectModel OppDiscard = UmInspect::FromCard(M.Opp.Discard[0], EUmInspectSource::Discard, M.C);
  TestTrue(TEXT("opponent discard: his hero's scan, no copies"), OppDiscard.Mode == EUmInspectMode::Own &&
                                                                     OppDiscard.HeroSlug == TEXT("king-arthur") && !OppDiscard.Copies.bKnown);
  // 3 log / 4 deck row: a catalogue card (no instance id) - the owner by its list
  const FUmInspectModel Log = UmInspect::FromCard(UmInspect::DeckCardView(M.Arthur.Cards[0]), EUmInspectSource::Log, M.C);
  TestTrue(TEXT("log: a King Arthur catalogue card -> his deck"), Log.HeroSlug == TEXT("king-arthur") && !Log.Copies.bKnown);
  const FUmInspectModel Row = UmInspect::FromCard(UmInspect::DeckCardView(M.Medusa.Cards[0]), EUmInspectSource::DeckRow, M.C);
  TestTrue(TEXT("deck row: an own catalogue card -> the copies line"), Row.HeroSlug == TEXT("medusa") && Row.Copies.bKnown);
  // 5 combat: a revealed opponent card; a back -> hidden
  FS09CardView Back;
  Back.bHidden = true;
  const FUmInspectModel Combat = UmInspect::FromCard(Back, EUmInspectSource::Combat, M.C);
  TestTrue(TEXT("combat back: hidden, the opponent's hero"), Combat.Mode == EUmInspectMode::Hidden && Combat.HeroSlug == TEXT("king-arthur") &&
                                                                 Combat.HeroName == TEXT("King Arthur"));
  // 6 slot: a played scheme (public face)
  const FUmInspectModel Slot = UmInspect::FromCard(M.Own.Discard[0], EUmInspectSource::Slot, M.C);
  TestTrue(TEXT("slot: the played scheme, own"), Slot.Mode == EUmInspectMode::Own && Slot.Source == EUmInspectSource::Slot);
  // the key I and the opponent's hand
  const FUmInspectModel Key = UmInspect::FromCard(M.Own.Cards[2], EUmInspectSource::Key, M.C);
  const FUmInspectModel OppHand = UmInspect::Hidden(M.C.OppSlug, M.C.OppHero, EUmInspectSource::OppHand);
  TestTrue(TEXT("key I: the hand card; OPP-HAND: hidden"), Key.Mode == EUmInspectMode::Own && OppHand.Mode == EUmInspectMode::Hidden);
  // the trace: the source, counts only
  const FString Open = UmInspect::OpenLine(Slot);
  TestTrue(FString::Printf(TEXT("INSPECT open line, no name (%s)"), *Open),
           Open.StartsWith(TEXT("INSPECT open source=slot mode=own")) && !Open.Contains(M.Own.Discard[0].Name));
  for (const EUmInspectSource Src : {EUmInspectSource::Hand, EUmInspectSource::Discard, EUmInspectSource::Log, EUmInspectSource::DeckRow,
                                     EUmInspectSource::Combat, EUmInspectSource::Slot, EUmInspectSource::Key}) {
    TestTrue(FString::Printf(TEXT("source %s named"), UmInspect::SourceName(Src)), FCString::Strlen(UmInspect::SourceName(Src)) > 2);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmInspectInputTest, "Unmatched.S08.Hud.Screens.Inspect.Input",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmInspectInputTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmInspectInput"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FMatch M;
  UUmScreenInspect* S = Make(W.World);
  if (!TestNotNull(TEXT("inspector"), S)) return false;
  TArray<FString> Closes;
  TArray<int32> Pages;
  UUmScreenInspect::FInput In;
  In.OnClose = [&Closes](const TCHAR* Why) { Closes.Add(Why); };
  In.OnPage = [&Pages](int32 I) { Pages.Add(I); };
  S->SetInput(MakeShared<FS09HudPressArbiter>(), MoveTemp(In));
  S->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
  const FUmInspectModel Own = UmInspect::FromCard(M.Own.Cards[0], EUmInspectSource::Hand, M.C);
  // the own view: the column of SC-21
  S->Open(Own);
  TestTrue(TEXT("own: shown, state own"), S->IsShown() && S->GetScreenState() == FName(TEXT("own")));
  TestEqual(TEXT("type word «Атака»"), S->GetTypeText(), FString(TEXT("Атака")));
  TestEqual(TEXT("value «Значение 2»"), S->GetValueText(), FString(TEXT("Значение 2")));
  TestEqual(TEXT("«BOOST 4»"), S->GetBoostText(), FString(TEXT("BOOST 4")));
  TestEqual(TEXT("copies «В колоде: 1 · в руке: 2 · в сбросе: 0»"), S->GetCopiesText(), FString(TEXT("В колоде: 1 · в руке: 2 · в сбросе: 0")));
  TestTrue(TEXT("the effect text from the data"), !S->GetBodyText().IsEmpty());
  // the four ways out, once each; nothing else is ever called (UI-INP-006: no command)
  S->SimulatePressForTest(FName(TEXT("hud.inspect.close")));
  S->Close(TEXT("again"));
  TestTrue(TEXT("«×» closes once"), Closes.Num() == 1 && Closes[0] == TEXT("button") && !S->IsShown());
  S->SetSheetClockMs(2000.0);
  S->Open(Own);
  TestTrue(TEXT("Esc closes"), S->HandleKey(EKeys::Escape) && Closes.Last() == TEXT("esc"));
  S->Open(Own);
  TestTrue(TEXT("I closes"), S->HandleKey(EKeys::I) && Closes.Last() == TEXT("key-i"));
  S->Open(Own);
  TestTrue(TEXT("any other key is the modal's (Enter, Space, N)"), S->HandleKey(EKeys::Enter) && S->HandleKey(EKeys::SpaceBar) &&
                                                                       S->HandleKey(EKeys::N) && S->IsShown());
  S->Close(TEXT("rmb"));
  TestTrue(TEXT("four closes, no page"), Closes.Num() == 4 && Pages.Num() == 0);
  TestFalse(TEXT("a closed modal takes no key"), S->HandleKey(EKeys::Escape));
  // the deck grid (SC-23)
  const FUmInspectModel Deck = UmInspect::FromDeck(true, EUmInspectSource::DeckAll, M.C);
  S->Open(Deck);
  TestTrue(TEXT("deck: state deck, 11 cells, «Колода · Medusa»"), S->GetScreenState() == FName(TEXT("deck")) &&
                                                                       S->GetGridCellCount() >= 11 && S->GetTitle() == TEXT("Колода · Medusa"));
  int32 Sum = 0;
  bool bChips = true;
  for (int32 I = 0; I < Deck.Deck.Num(); ++I) {
    bChips &= S->GetGridChipText(I) == FString::Printf(TEXT("×%d"), Deck.Deck[I].Count);
    Sum += Deck.Deck[I].Count;
  }
  TestTrue(FString::Printf(TEXT("the chips «×N» next to each card, sum %d"), Sum), bChips && Sum == 30);
  TestTrue(TEXT("the wheel: two rows down to the end (4 rows, 2 shown), then no more"),
           S->WheelStep(false) && S->WheelStep(false) && !S->WheelStep(false) && S->GetFirstRow() == 2);
  const int32 Hiss = Deck.Deck.IndexOfByPredicate([](const FS09DeckListCard& C) { return C.Name == TEXT("Hiss and Slither"); });
  S->SimulatePressForTest(FName(*FString::Printf(TEXT("hud.inspect.grid.%d"), Hiss)));
  TestTrue(TEXT("a grid card opens in the same modal (the page called); the gate state waits for the fade"),
           S->GetModel().Mode == EUmInspectMode::DeckCard && S->GetScreenState() == FName(TEXT("deck")) && Pages.Num() == 1 && Pages[0] == Hiss);
  TestTrue(TEXT("the switch fades in 150 ms"), FMath::IsNearlyEqual(S->GetContentAlpha(), 0.0f));
  S->SetSheetClockMs(2075.0);
  S->StepInspect();
  TestTrue(TEXT("half at 75 ms"), FMath::IsNearlyEqual(S->GetContentAlpha(), 0.5f, 0.02f));
  S->SetSheetClockMs(2151.0);
  S->StepInspect();
  TestTrue(TEXT("faded in: alpha 1, state own"), S->GetContentAlpha() == 1.0f && S->GetScreenState() == FName(TEXT("own")));
  TestTrue(TEXT("«Назад» shown, the deck card has no copies line"), S->BackButton->GetVisibility() == ESlateVisibility::Visible && S->GetCopiesText().IsEmpty());
  TestTrue(TEXT("Backspace: back to the grid"), S->HandleKey(EKeys::BackSpace) && S->GetModel().Mode == EUmInspectMode::Deck && Pages.Last() == INDEX_NONE);
  S->SimulatePressForTest(FName(TEXT("hud.inspect.grid.0")));
  S->SimulatePressForTest(FName(TEXT("hud.inspect.back")));
  TestTrue(TEXT("«Назад» returns too"), S->GetModel().Mode == EUmInspectMode::Deck);
  S->Close(TEXT("owner"));
  TestTrue(TEXT("only OnClose / OnPage were called"), Closes.Num() == 5 && Pages.Num() == 4);
  // reduced motion: the switch in 100 ms
  S->SetReducedForTest(1);
  S->SetSheetClockMs(3000.0);
  S->Open(Deck);
  S->OpenDeckCard(0);
  S->SetSheetClockMs(3050.0);
  S->StepInspect();
  TestTrue(TEXT("reduced: half at 50 ms"), FMath::IsNearlyEqual(S->GetContentAlpha(), 0.5f, 0.02f));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmInspectPrivacyTest, "Unmatched.S08.Hud.Screens.Inspect.Privacy",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmInspectPrivacyTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmInspectPrivacy"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FMatch M;
  UUmScreenInspect* S = Make(W.World);
  if (!TestNotNull(TEXT("inspector"), S)) return false;
  S->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
  // a hidden model that still carries a face (a wrong caller): ApplyModel drops it
  FUmInspectModel Leak = UmInspect::Hidden(TEXT("medusa"), TEXT("Medusa"), EUmInspectSource::Combat);
  Leak.Card = M.Own.Cards[0];
  Leak.Copies.bKnown = true;
  Leak.Copies.Copies = 3;
  S->Open(Leak);
  const FUmInspectModel& Kept = S->GetModel();
  TestTrue(TEXT("the model keeps nothing of the card (QA-005)"), Kept.Card.bHidden && Kept.Card.Name.IsEmpty() && Kept.Card.NameRu.IsEmpty() &&
                                                                     Kept.Card.CardType.IsEmpty() && Kept.Card.Text.IsEmpty() &&
                                                                     Kept.Card.AttackValue == 0 && Kept.Card.BoostValue == 0 && !Kept.Copies.bKnown);
  TestEqual(TEXT("«Скрытая информация»"), S->GetTitle(), FString(TEXT("Скрытая информация")));
  TestEqual(TEXT("the owner"), S->GetTypeText(), FString(TEXT("Medusa")));
  TestTrue(TEXT("no value, BOOST, text, copies, language"), S->GetValueText().IsEmpty() && S->GetBoostText().IsEmpty() &&
                                                                S->GetBodyText().IsEmpty() && S->GetCopiesText().IsEmpty() && !S->CanToggleLang());
  TestTrue(TEXT("the widget shows the owner's back and holds no face"), S->Card->GetFace() == EUmCardFace::Back &&
                                                                          S->Card->GetFaceKey() == TEXT("back:medusa") &&
                                                                          S->Card->GetCard().Name.IsEmpty());
  TestEqual(TEXT("state hidden"), S->GetScreenState(), FName(TEXT("hidden")));
  TArray<FString> Lines;
  S->CollectShotLines(Lines);
  bool bClean = Lines.Num() >= 2;
  for (const FString& L : Lines) {
    bClean &= !L.Contains(TEXT("Gaze")) && !L.Contains(TEXT("gaze-of-stone")) && !L.Contains(TEXT("Убийственный"));
  }
  TestTrue(FString::Printf(TEXT("SHOT state=hidden and CARD-ART lang=back, no name (%s)"), Lines.Num() ? *Lines[0] : TEXT("-")),
           bClean && Lines[0].Contains(TEXT("id=UI-SCR-INSPECT")) && Lines[0].Contains(TEXT("state=hidden")) && Lines[1].Contains(TEXT("lang=back")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmCardPlayedFlashTest, "Unmatched.S08.Hud.Card.PlayedFlash",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmCardPlayedFlashTest::RunTest(const FString& Parameters) {
  FWorld W(TEXT("UmCardFlash"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  TestEqual(TEXT("500 ms at speed 1"), UmCardWidget::PlayedFlashMs(1.0f, false), 500.0f);
  TestEqual(TEXT("250 ms at speed 0.5 (fast)"), UmCardWidget::PlayedFlashMs(0.5f, false), 250.0f);
  TestEqual(TEXT("750 ms at speed 1.5 (slow)"), UmCardWidget::PlayedFlashMs(1.5f, false), 750.0f);
  TestEqual(TEXT("none at speed 0 («Нет»)"), UmCardWidget::PlayedFlashMs(0.0f, false), 0.0f);
  TestEqual(TEXT("reduced motion 100 ms"), UmCardWidget::PlayedFlashMs(1.0f, true), 100.0f);
  const float Keys[4][2] = {{0.0f, 1.0f}, {100.0f, 0.8f}, {250.0f, 0.5f}, {500.0f, 0.0f}};
  for (const auto& K : Keys) {
    TestTrue(FString::Printf(TEXT("keyframe %.0f ms -> %.1f"), K[0], K[1]), FMath::IsNearlyEqual(UmCardWidget::FlashOpacity(K[0], 500.0f), K[1], 1.0e-4f));
  }
  UUmCardWidget* C = CreateWidget<UUmCardWidget>(W.World, UUmCardWidget::StaticClass());
  if (!TestNotNull(TEXT("card"), C)) return false;
  C->SetSyncLoad(true);
  C->SetReducedForTest(0);
  C->SetClockOverrideMs(1000.0);
  FUmCardState St;
  St.HeroSlug = TEXT("medusa");
  St.Lang = TEXT("ru");
  St.PxPerSu = 1.0f;
  FS09CardView V;
  V.Name = TEXT("Gaze of Stone");
  V.CardType = TEXT("ATTACK");
  C->ApplyModel(V, St);
  C->PlayPlayedFlash(1.0f);
  TestTrue(TEXT("t 0: the flash layer at 1, state flash"), FMath::IsNearlyEqual(C->GetFlashOpacity(), 1.0f) && C->StateText().Contains(TEXT("flash")));
  C->SetClockOverrideMs(1250.0);
  C->Step();
  TestTrue(TEXT("t 250: 0.5"), FMath::IsNearlyEqual(C->GetFlashOpacity(), 0.5f, 1.0e-3f));
  C->SetClockOverrideMs(1501.0);
  C->Step();
  TestTrue(TEXT("t 500: gone (idle frame only)"), C->GetFlashOpacity() == 0.0f && !C->StateText().Contains(TEXT("flash")));
  C->SetReducedForTest(1);
  C->SetClockOverrideMs(2000.0);
  C->PlayPlayedFlash(1.0f);
  C->SetClockOverrideMs(2050.0);
  C->Step();
  TestTrue(TEXT("reduced: 100 ms, half at 50"), C->GetFlashMs() == 100.0f && FMath::IsNearlyEqual(C->GetFlashOpacity(), 0.5f, 1.0e-3f));
  C->SetReducedForTest(0);
  C->PlayPlayedFlash(0.0f);
  TestTrue(TEXT("speed «Нет»: no flash"), C->GetFlashOpacity() == 0.0f);
  // the G-CUE lines (cue_contract.py check-trace: one show per seq, done = start + ms)
  const FString Show = UmCardWidget::FlashCueLine(12, 40000, false);
  const FString Done = UmCardWidget::FlashDoneLine(12, 40500, 500);
  TestTrue(FString::Printf(TEXT("show line (%s)"), *Show),
           Show == TEXT("CUE fx id=CUE-006 subject=card seq=12 t=40000 vfx=none sfx=none clip=none mat=none socket=- reduced=0 result=spawned"));
  TestEqual(TEXT("done line"), Done, FString(TEXT("CUE fx done id=CUE-006 subject=card seq=12 t=40500 ms=500 cut=0")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmDeckRowMarksFitTest, "Unmatched.S08.Hud.DeckPanel.MarksFit",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmDeckRowMarksFitTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmDeckMarks"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  const float Line = UmDeckRow::MarkLineSu();
  const float Chip = UmDeckRow::MarkChipSu();
  const float Top = UmDeckRow::MarksTopSu();
  TestTrue(FString::Printf(TEXT("the chip (%.2f su) holds the label line (%.2f su) + 1 su a side"), Chip, Line), Chip >= Line + 2.0f - 1.0e-3f);
  TestTrue(FString::Printf(TEXT("the chips end 2 su over the row's bottom (%.2f + %.2f = %.2f <= 46)"), Top, Chip, Top + Chip),
           Top + Chip <= UmDeckRow::HeightSu - 2.0f + 1.0e-3f);
  // under the name's descenders: the 20 su line from the cap top 3 su (its baseline + Roboto's descender 500 / 2048 em)
  const float NameBottom = UmDeckRow::CapTopSu + UmDeckRow::CapEm * UmDeckRow::TextSu + 500.0f / 2048.0f * UmDeckRow::TextSu;
  TestTrue(FString::Printf(TEXT("below the name's descenders (%.2f >= %.2f)"), Top, NameBottom), Top >= NameBottom);
  UUmDeckRow* R = CreateWidget<UUmDeckRow>(W.World, UUmDeckRow::StaticClass());
  if (!TestNotNull(TEXT("row"), R)) return false;
  FUmDeckRowModel Mo;
  Mo.CardId = TEXT("x");
  Mo.Name = TEXT("Gaze of Stone");
  Mo.CardType = TEXT("ATTACK");
  Mo.Copies = 3;
  Mo.Values = TEXT("A2 B4");
  Mo.InHand = 2;
  Mo.Left = 1;
  R->ApplyModel(Mo, 290.0f);
  TestTrue(TEXT("the marks «В руке 2», «Осталось 1»"), R->MarkTexts() == TArray<FString>({TEXT("В руке 2"), TEXT("Осталось 1")}));
  // «Весь состав» on the filter row, inside the panel (L 1080p and the S panel 300 su)
  UUmHudDeckPanel* P = CreateWidget<UUmHudDeckPanel>(W.World, UUmHudDeckPanel::WidgetClass());
  if (!TestNotNull(TEXT("panel"), P)) return false;
  TestNotNull(TEXT("AllButton (made at run time for an older WBP)"), P->AllButton.Get());
  return true;
}

// ------------------------------------------------------------------- VS-5 E4: the inspector's «×», n 24 clicks

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmInspectCloseClicksTest, "Unmatched.S08.Hud.Screens.Inspect.CloseClicks",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmInspectCloseClicksTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmInspectCloseClicks"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  FMatch M;
  UUmScreenInspect* S = Make(W.World);
  if (!TestNotNull(TEXT("inspector"), S)) return false;
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  uint64 Frame = 3000;
  Arbiter->SetFrameClock([&Frame]() { return Frame; });
  TArray<FString> Closes;
  UUmScreenInspect::FInput In;
  In.OnClose = [&Closes](const TCHAR* Why) { Closes.Add(Why); };
  S->SetInput(Arbiter, MoveTemp(In));
  S->ApplyCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
  const FUmInspectModel Own = UmInspect::FromCard(M.Own.Cards[0], EUmInspectSource::Hand, M.C);
  const FGeometry Geo = FGeometry::MakeRoot(FVector2D(32.0, 32.0), FSlateLayoutTransform());
  const FVector2D Centre(16.0, 16.0);
  auto Left = [](const FVector2D& At, bool bDown) {
    TSet<FKey> Pressed;
    if (bDown) Pressed.Add(EKeys::LeftMouseButton);
    return FPointerEvent(0, At, At, Pressed, EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
  };
  const int32 N = 24;
  int32 Lost = 0;
  for (int32 I = 0; I < N; ++I) {
    S->SetSheetClockMs(10000.0 + 1000.0 * I);
    S->Open(Own);
    if (!S->IsShown()) {
      ++Lost;
      continue;
    }
    const int32 Before = Closes.Num();
    // holds of 0 and 3 frames; a snapshot re-applies the model while «×» is held
    const int32 Hold = (I % 2) ? 3 : 0;
    S->CloseButton->NativeOnMouseButtonDown(Geo, Left(Centre, true));
    for (int32 F = 0; F < Hold; ++F) {
      ++Frame;
      Arbiter->NoteRebuild();
      S->ApplyModel(Own);
    }
    S->CloseButton->NativeOnMouseButtonUp(Geo, Left(Centre, false));
    ++Frame;
    if (Closes.Num() != Before + 1 || Closes.Last() != TEXT("button") || S->IsShown()) ++Lost;
  }
  TestEqual(TEXT("n 24: every click closes once, 0 lost"), Lost, 0);
  TestEqual(TEXT("24 closes, all by the button"), Closes.Num(), N);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
