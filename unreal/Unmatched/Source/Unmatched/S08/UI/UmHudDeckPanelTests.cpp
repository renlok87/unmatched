// VS-3 automation tests of the deck panel (docs/game-design/visual/06-tasks/hud.csv HB-28; 04-hud-spec.md §2.9, §1.6,
// §6.2, §7.1; HB-26 D3-D8):
//   Unmatched.S08.Hud.DeckPanel.Rows       the real decks (S01 content capture = the backend lists): Medusa 11 rows / 30
//                                          copies, King Arthur 16 / 30; rows by type (attack, defense, versatile,
//                                          scheme), then by name - never the list order; values «A2 B4» / «D0 B2» /
//                                          «V3 B1» / «B4» (ВР-HB14); the HB-26 moments: own marks sum to the summary
//                                          (Marmoreal hand 5 / discard 2 / left 23; Sarpedon 3 / 2 / 25), the opponent
//                                          rows only «В сбросе n» (F-05); the filter «Только сброс»; the row widget's
//                                          marks; the name budget 20 -> 16 -> «…» (D4) with nothing else cut; the SHOT
//                                          line without a card name; the pool after the warm-up; ApplyModel p95.
//   Unmatched.S08.Hud.DeckPanel.Layout     the HB-26 rects on 1080p / 720p x 100 / 150 %; the header formula (155.6 su
//                                          own, 221.2 su with a two-line title and the backs); whole rows in the
//                                          viewport, the scrollbar only for a longer list, -end shows the last row last;
//                                          the bottom over a 9-card fan at 1080p (ВР-VS3-37); the skeleton (6 rows).
//   Unmatched.S08.Hud.DeckPanel.AutoClose  S09DeckPanel::InputDemandKey closes an open panel at my turn start and in my
//                                          defense window; the UMG view: clicks only while open, the close fade lets
//                                          them through, collapsed at 0; reduced motion closes in 100 ms (ВР-VS3-40).
//   Unmatched.S08.Hud.DeckPanel.Tree       BuildDefaultTree, every BindWidget, the GAME slot, WBP_UI_HUD_DECKPANEL.
//   Unmatched.S08.Hud.DeckPanel.Blocks     FUmDeckBlocks (the game mode's side): both blocks in the GAME screen, the
//                                          rollback -S08SlateHud=decks / =deckpanel builds none, the chips follow the
//                                          snapshot, a fresh open drops the filter unless D / the chip asked, the model
//                                          line of the open side, the first open frame refreshes first.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.DeckPanel" <abs log>
#if WITH_AUTOMATION_TESTS

#include "Components/Border.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"
#include "UmButton.h"
#include "UmDecksGallery.h"
#include "UmDeckRow.h"
#include "UmGameHud.h"
#include "UmHudDeckBlocks.h"
#include "UmHudDeckPanel.h"
#include "UmHudDecks.h"
#include "UmHudLayout.h"
#include "UmSkeletonRows.h"

namespace UmDeckPanelTest {
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
#if WITH_EDITOR  // the preview API exists only WITH_EDITOR; the game target reads Culture=ru itself
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(TEXT("ru"));
#endif
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FRu() { FInternationalization::Get().RestoreCultureState(Snapshot); }
};

FS09CardView Card(const FS09DeckList& List, const TCHAR* Name, int32 Copy) {
  FS09CardView V;
  V.Name = Name;
  V.InstanceId = FString::Printf(TEXT("inst::%s-%d"), Name, Copy);
  for (const FS09DeckListCard& C : List.Cards) {
    if (C.Name == Name) V.CardId = C.CardId;
  }
  return V;
}

/** The HB-26 moments (ВР-VS2-HB26-02). */
struct FMoment {
  FS09DeckList OwnList;
  FS09DeckList OppList;
  FS09PlayerPanel Own;
  FS09PlayerPanel Opp;
};

FMoment Marmoreal() {
  FMoment M;
  M.OwnList = UmDecksGallery::LoadList(TEXT("medusa"), TEXT("own"));
  M.OppList = UmDecksGallery::LoadList(TEXT("king-arthur"), TEXT("opp"));
  M.Own.PlayerId = TEXT("own");
  M.Own.bIsViewer = true;
  M.Own.DeckCount = 23;
  M.Own.Cards = {Card(M.OwnList, TEXT("Gaze of Stone"), 0), Card(M.OwnList, TEXT("Gaze of Stone"), 1), Card(M.OwnList, TEXT("Snipe"), 0),
                 Card(M.OwnList, TEXT("Clutching Claws"), 0), Card(M.OwnList, TEXT("Dash"), 0)};
  M.Own.HandCount = 5;
  M.Own.Discard = {Card(M.OwnList, TEXT("A Momentary Glance"), 0), Card(M.OwnList, TEXT("Feint"), 0)};
  M.Opp.PlayerId = TEXT("opp");
  M.Opp.DeckCount = 24;
  M.Opp.HandCount = 5;
  M.Opp.Discard = {Card(M.OppList, TEXT("Swift Strike"), 0)};
  return M;
}

FMoment Sarpedon() {
  FMoment M;
  M.OwnList = UmDecksGallery::LoadList(TEXT("king-arthur"), TEXT("own"));
  M.OppList = UmDecksGallery::LoadList(TEXT("medusa"), TEXT("opp"));
  M.Own.PlayerId = TEXT("own");
  M.Own.bIsViewer = true;
  M.Own.DeckCount = 25;
  M.Own.Cards = {Card(M.OwnList, TEXT("Noble Sacrifice"), 0), Card(M.OwnList, TEXT("Swift Strike"), 0),
                 Card(M.OwnList, TEXT("The Holy Grail"), 0)};
  M.Own.HandCount = 3;
  M.Own.Discard = {Card(M.OwnList, TEXT("Momentous Shift"), 0), Card(M.OwnList, TEXT("Swift Strike"), 1)};
  M.Opp.PlayerId = TEXT("opp");
  M.Opp.DeckCount = 22;
  M.Opp.HandCount = 6;
  M.Opp.Discard = {Card(M.OppList, TEXT("Dash"), 0), Card(M.OppList, TEXT("Regroup"), 0)};
  return M;
}

FUmDeckPanelModel Model(const FMoment& M, bool bOpp, bool bFilter = false, const TCHAR* Hero = nullptr) {
  const FS09DeckPanelModel S09 = FS09DeckPanelModel::Build(bOpp ? ES09DeckSide::Opponent : ES09DeckSide::Own, bOpp ? M.Opp : M.Own,
                                                           bOpp ? &M.OppList : &M.OwnList);
  const FString Name = Hero ? FString(Hero) : FString(TEXT("Hero"));
  return UmHudDeckPanel::Gather(S09, Name, TEXT("medusa"), EUmDeckListState::Loaded, bFilter, true);
}

struct FPanelCanvas {
  const TCHAR* Name;
  FVector2D Su;
  float Px;
};
const FPanelCanvas Canvases[] = {{TEXT("1080p100"), FVector2D(1920.0, 1080.0), 1.0f},
                            {TEXT("720p100"), FVector2D(1280.0 / 0.75, 960.0), 0.75f},
                            {TEXT("1080p150"), FVector2D(1280.0, 720.0), 1.5f},
                            {TEXT("720p150"), FVector2D(1280.0 / 1.125, 640.0), 1.125f}};

FUmDeckPanelFrame Frame(const FPanelCanvas& C) {
  const FUmHudLayout L = FUmHudLayout::Compute(C.Su, C.Px, nullptr);
  FUmDeckPanelFrame F;
  F.bClassS = L.bClassS;
  F.PxPerSu = C.Px;
  F.SlotSu = L.Rect(EUmHudBlock::DeckPanel);
  F.BottomSu = static_cast<float>(F.SlotSu.Max.Y);
  return F;
}

UUmHudDeckPanel* Make(UWorld* World, const FUmDeckPanelFrame& F) {
  UUmHudDeckPanel* P = CreateWidget<UUmHudDeckPanel>(World, UUmHudDeckPanel::StaticClass());
  if (P) P->SetFrame(F);
  return P;
}
}  // namespace UmDeckPanelTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmDeckPanelRowsTest,
    "Unmatched.S08.Hud.DeckPanel.Rows Medusa 11 / 30, King Arthur 16 / 30, type then name, marks sum to the summary, privacy",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmDeckPanelRowsTest::RunTest(const FString&) {
  using namespace UmDeckPanelTest;
  FRu Ru;
  // ---- the lists ----
  const FS09DeckList Medusa = UmDecksGallery::LoadList(TEXT("medusa"), TEXT("m"));
  const FS09DeckList Arthur = UmDecksGallery::LoadList(TEXT("king-arthur"), TEXT("k"));
  TestTrue(FString::Printf(TEXT("Medusa: 11 kinds / 30 copies (%d / %d)"), Medusa.Cards.Num(), Medusa.Total), Medusa.Cards.Num() == 11 && Medusa.Total == 30);
  TestTrue(FString::Printf(TEXT("King Arthur: 16 kinds / 30 copies (%d / %d)"), Arthur.Cards.Num(), Arthur.Total), Arthur.Cards.Num() == 16 && Arthur.Total == 30);
  // ---- Marmoreal own Medusa: the rows, the order, the marks ----
  const FMoment Marm = Marmoreal();
  const FUmDeckPanelModel Own = Model(Marm, false, false, TEXT("Medusa"));
  TestEqual(TEXT("own Medusa: 11 rows"), Own.Rows.Num(), 11);
  int32 Copies = 0, SumHand = 0, SumDiscard = 0, SumLeft = 0;
  bool bOrdered = true;
  for (int32 I = 0; I < Own.Rows.Num(); ++I) {
    const FUmDeckRowModel& R = Own.Rows[I];
    Copies += R.Copies;
    SumHand += R.InHand;
    SumDiscard += R.InDiscard;
    SumLeft += R.Left;
    TestEqual(FString::Printf(TEXT("row %s: copies = hand + discard + left"), *R.Name), R.Copies, R.InHand + R.InDiscard + R.Left);
    if (I > 0) {
      const FUmDeckRowModel& P = Own.Rows[I - 1];
      const int32 TP = UmDeckRow::TypeOrder(P.CardType), TR = UmDeckRow::TypeOrder(R.CardType);
      bOrdered &= TP < TR || (TP == TR && P.Name.ToLower().Compare(R.Name.ToLower(), ESearchCase::CaseSensitive) <= 0);
    }
  }
  TestEqual(TEXT("own Medusa: 30 copies"), Copies, 30);
  TestTrue(TEXT("rows by type (attack, defense, versatile, scheme), then by name"), bOrdered);
  TestTrue(FString::Printf(TEXT("marks sum to the summary: hand %d = 5, discard %d = 2, left %d = 23"), SumHand, SumDiscard, SumLeft),
           SumHand == 5 && SumDiscard == 2 && SumLeft == Own.DeckCount);
  TestEqual(TEXT("the first row is an attack (Gaze of Stone)"), Own.Rows[0].Name, FString(TEXT("Gaze of Stone")));
  TestEqual(TEXT("ВР-HB14: «A2 B4»"), Own.Rows[0].Values, FString(TEXT("A2 B4")));
  const FUmDeckRowModel* Glance = Own.Rows.FindByPredicate([](const FUmDeckRowModel& R) { return R.Name == TEXT("A Momentary Glance"); });
  TestTrue(TEXT("a scheme: «B4» only (boostValue 4 in the data), last group"), Glance && Glance->Values == TEXT("B4") && UmDeckRow::TypeOrder(Glance->CardType) == 3);
  const FUmDeckRowModel* Dash = Own.Rows.FindByPredicate([](const FUmDeckRowModel& R) { return R.Name == TEXT("Dash"); });
  TestTrue(TEXT("a versatile: «V3 B1»"), Dash && Dash->Values == TEXT("V3 B1"));
  // ---- the filter «Только сброс» ----
  const FUmDeckPanelModel OwnD = Model(Marm, false, true, TEXT("Medusa"));
  TestEqual(TEXT("filter: the two rows with a discard"), OwnD.ShownRows().Num(), 2);
  TestEqual(TEXT("filter: the model keeps every row"), OwnD.Rows.Num(), 11);
  // ---- the opponent: only «В сбросе n» (F-05) ----
  const FUmDeckPanelModel Opp = Model(Marm, true, false, TEXT("King Arthur"));
  TestEqual(TEXT("opp King Arthur: 16 rows"), Opp.Rows.Num(), 16);
  int32 OppDiscard = 0;
  bool bPrivate = true;
  for (const FUmDeckRowModel& R : Opp.Rows) {
    OppDiscard += R.InDiscard;
    bPrivate &= !R.bOwn && R.InHand == 0 && R.Left == 0;
  }
  TestTrue(TEXT("opp: no hand, no left on the rows"), bPrivate);
  TestEqual(TEXT("opp: the public discard (Swift Strike) only"), OppDiscard, 1);
  const FUmDeckRowModel* Bew = Opp.Rows.FindByPredicate([](const FUmDeckRowModel& R) { return R.Name == TEXT("Bewilderment"); });
  TestTrue(TEXT("Bewilderment «D0 B2» (as in the data)"), Bew && Bew->Values == TEXT("D0 B2"));
  // ---- Sarpedon own King Arthur: the run I panel marks ----
  const FMoment Sarp = Sarpedon();
  const FUmDeckPanelModel KA = Model(Sarp, false, false, TEXT("King Arthur"));
  int32 KH = 0, KD = 0, KL = 0;
  for (const FUmDeckRowModel& R : KA.Rows) {
    KH += R.InHand;
    KD += R.InDiscard;
    KL += R.Left;
  }
  TestTrue(FString::Printf(TEXT("Sarpedon own: hand %d = 3, discard %d = 2, left %d = 25"), KH, KD, KL), KH == 3 && KD == 2 && KL == 25);
  const FUmDeckRowModel* Swift = KA.Rows.FindByPredicate([](const FUmDeckRowModel& R) { return R.Name == TEXT("Swift Strike"); });
  TestTrue(TEXT("Swift Strike: in hand 1, in discard 1, left 0"), Swift && Swift->InHand == 1 && Swift->InDiscard == 1 && Swift->Left == 0);
  // ---- the widget: rows, marks, the name budget, the SHOT line ----
  FWorld W(TEXT("UmDeckPanelRows"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudDeckPanel* P = Make(W.World, Frame(Canvases[0]));
  if (!TestNotNull(TEXT("panel"), P)) return false;
  P->ApplyModel(KA);
  P->ApplyView(1.0f, true, 0.0);
  TestEqual(TEXT("widget: 16 rows shown"), P->GetShownRowCount(), 16);
  int32 SwiftRow = INDEX_NONE;
  for (int32 I = 0; I < P->GetShownRowCount(); ++I) {
    if (P->GetRowWidget(I) && P->GetRowWidget(I)->GetModel().Name == TEXT("Swift Strike")) SwiftRow = I;
  }
  if (TestTrue(TEXT("Swift Strike has a row"), SwiftRow != INDEX_NONE)) {
    const TArray<FString> Marks = P->GetRowWidget(SwiftRow)->MarkTexts();
    TestTrue(FString::Printf(TEXT("own row marks: «В руке 1», «В сбросе 1», «Осталось 0» (%s)"), *FString::Join(Marks, TEXT(" | "))),
             Marks == TArray<FString>({TEXT("В руке 1"), TEXT("В сбросе 1"), TEXT("Осталось 0")}));
  }
  P->ApplyModel(Model(Sarp, true, false, TEXT("Medusa")));
  bool bOppMarks = true;
  for (int32 I = 0; I < P->GetShownRowCount(); ++I) {
    for (const FString& Mark : P->GetRowWidget(I)->MarkTexts()) bOppMarks &= Mark.StartsWith(TEXT("В сбросе "));
  }
  TestTrue(TEXT("opponent rows: only «В сбросе n»"), bOppMarks);
  // D4: the name budget - 20 su, then 16, then «…»; the rest is never cut
  const auto Measure = [](const FString& T, float Su) { return 0.5f * Su * T.Len(); };
  const FUmNameFit Fit20 = UmDeckRow::FitName(TEXT("Dash"), 200.0f, Measure);
  TestTrue(TEXT("a short name keeps 20 su"), Fit20.SizeSu == 20.0f && !Fit20.bEllipsis && Fit20.Shown == TEXT("Dash"));
  const FUmNameFit Fit16 = UmDeckRow::FitName(TEXT("The Hounds of Mighty Zeus"), 220.0f, Measure);  // 250 at 20, 200 at 16
  TestTrue(TEXT("a long name steps down to 16 su whole"), Fit16.SizeSu == 16.0f && !Fit16.bEllipsis);
  const FUmNameFit FitE = UmDeckRow::FitName(TEXT("The Hounds of Mighty Zeus"), 150.0f, Measure);
  TestTrue(FString::Printf(TEXT("too long at 16 su: «…» within the column (%s, %.1f <= 150)"), *FitE.Shown, FitE.WidthSu),
           FitE.SizeSu == 16.0f && FitE.bEllipsis && FitE.Shown.EndsWith(TEXT("…")) && FitE.WidthSu <= 150.0f);
  // the live measure: every row name fits its column (or carries «…»), values are never cut
  for (int32 I = 0; I < P->GetShownRowCount(); ++I) {
    const FUmNameFit& F = P->GetRowWidget(I)->GetNameFit();
    TestTrue(FString::Printf(TEXT("row %d: %s %.1f su in %.1f"), I, *F.Shown, F.WidthSu, F.ColumnSu), F.WidthSu <= F.ColumnSu + 0.5f || F.bEllipsis);
  }
  TArray<FString> Lines;
  P->CollectShotLines(Lines);
  if (TestEqual(TEXT("one SHOT line"), Lines.Num(), 1)) {
    TestTrue(FString::Printf(TEXT("SHOT opp, counts (%s)"), *Lines[0]),
             Lines[0].Contains(TEXT("id=UI-HUD-DECKPANEL impl=umg state=opp")) && Lines[0].Contains(TEXT("rows=11")) &&
                 Lines[0].Contains(TEXT("sumHand=0")) && Lines[0].Contains(TEXT("sumDiscard=2")) && Lines[0].Contains(TEXT("sumLeft=0")));
    TestFalse(TEXT("SHOT: no card name"), Lines[0].Contains(TEXT("Dash")) || Lines[0].Contains(TEXT("Regroup")));
  }
  // ---- the pool and the budget ----
  const int32 Pool = P->RowPoolSize();
  TArray<double> Ms;
  for (int32 I = 0; I < 60; ++I) {
    FMoment X = I % 2 ? Marmoreal() : Sarpedon();
    X.Own.DeckCount -= I % 5;
    const FUmDeckPanelModel M = Model(X, (I % 4) >= 2, (I % 3) == 0, TEXT("Hero"));
    const double T0 = FPlatformTime::Seconds();
    P->ApplyModel(M);
    Ms.Add((FPlatformTime::Seconds() - T0) * 1000.0);
  }
  Ms.Sort();
  const double P95 = Ms[FMath::CeilToInt(0.95 * Ms.Num()) - 1];
  AddInfo(FString::Printf(TEXT("DECKPANEL ApplyModel p50 %.3f p95 %.3f ms (60 models, the open frame budget 2 ms)"), Ms[Ms.Num() / 2], P95));
  TestTrue(TEXT("0 new rows after the warm-up (the 16 of King Arthur)"), P->RowPoolSize() == FMath::Max(Pool, 16));
  TestTrue(FString::Printf(TEXT("a full rebuild p95 %.3f ms <= 2 ms (the open frame)"), P95), P95 <= 2.0);
  // the open panel per frame: the same snapshot (no work) and the view (HB-28: <= 0.05 ms GT p95)
  const FUmDeckPanelModel Still = Model(Sarpedon(), false, false, TEXT("King Arthur"));
  P->ApplyModel(Still);
  TArray<double> Frame;
  for (int32 I = 0; I < 300; ++I) {
    const double T0 = FPlatformTime::Seconds();
    P->ApplyModel(Still);
    P->ApplyView(1.0f, true, 1000.0 + I * 16.0);
    Frame.Add((FPlatformTime::Seconds() - T0) * 1000.0);
  }
  Frame.Sort();
  const double FrameP95 = Frame[FMath::CeilToInt(0.95 * Frame.Num()) - 1];
  AddInfo(FString::Printf(TEXT("DECKPANEL open frame p50 %.4f p95 %.4f ms (300 frames)"), Frame[Frame.Num() / 2], FrameP95));
  TestTrue(FString::Printf(TEXT("the open panel per frame p95 %.4f ms <= 0.05 ms"), FrameP95), FrameP95 <= 0.05);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmDeckPanelLayoutTest,
    "Unmatched.S08.Hud.DeckPanel.Layout HB-26 rects, header, whole rows, scrollbar, -end, bottom over the hand, skeleton",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmDeckPanelLayoutTest::RunTest(const FString&) {
  using namespace UmDeckPanelTest;
  using namespace UmHudDeckPanel;
  FRu Ru;
  // the header formula of the HB-26 package (panel_geometry: own 155.6 su, a two-line title with the backs 221.2 su)
  TestTrue(TEXT("header own, one title line: 155.6 su"), FMath::IsNearlyEqual(HeaderSu(28.0f, 1, 1, false), 155.6f, 0.01f));
  TestTrue(TEXT("header opp, two title lines + backs: 221.2 su"), FMath::IsNearlyEqual(HeaderSu(28.0f, 2, 1, true), 221.2f, 0.01f));
  TestEqual(TEXT("1080p own: 9 rows (432 su)"), Capacity(644.0f, 155.6f), 9);
  TestEqual(TEXT("1080p opp, two lines: 8 rows (384 su)"), Capacity(644.0f, 221.2f), 8);
  TestEqual(TEXT("720p 150 % opp: 3 rows (144 su)"), Capacity(392.0f, 221.2f), 3);
  // the title: one line, or broken only after « · » (the hero whole), then 24 su
  {
    float Size = 0.0f;
    TArray<FString> TitleLines;
    const auto M = [](const FString& T, float Su) { return 0.5f * Su * T.Len(); };
    FitTitle(TEXT("Ваша колода · Medusa"), 400.0f, M, Size, TitleLines);
    TestTrue(TEXT("a short title: one line at 28 su"), Size == 28.0f && TitleLines.Num() == 1);
    FitTitle(TEXT("Колода соперника · King Arthur"), 300.0f, M, Size, TitleLines);
    TestTrue(FString::Printf(TEXT("a long title: «Колода соперника ·» / «King Arthur» (%s)"), *FString::Join(TitleLines, TEXT(" / "))),
             TitleLines.Num() == 2 && TitleLines[0] == TEXT("Колода соперника ·") && TitleLines[1] == TEXT("King Arthur"));
  }
  FWorld W(TEXT("UmDeckPanelLayout"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  const FMoment Marm = Marmoreal();
  const FBox2D Want[] = {FBox2D(FVector2D(1516.0, 268.0), FVector2D(1896.0, 912.0)),
                         FBox2D(FVector2D(1346.667, 268.0), FVector2D(1682.667, 792.0)),
                         FBox2D(FVector2D(964.0, 120.0), FVector2D(1264.0, 592.0)),
                         FBox2D(FVector2D(821.778, 120.0), FVector2D(1121.778, 512.0))};
  for (int32 C = 0; C < UE_ARRAY_COUNT(Canvases); ++C) {
    UUmHudDeckPanel* P = Make(W.World, Frame(Canvases[C]));
    if (!P) continue;
    for (const bool bOpp : {false, true}) {
      const FString T = FString::Printf(TEXT("%s %s"), Canvases[C].Name, bOpp ? TEXT("opp") : TEXT("own"));
      P->ApplyModel(Model(Marm, bOpp, false, bOpp ? TEXT("King Arthur") : TEXT("Medusa")));
      P->ApplyView(1.0f, true, 0.0);
      const FBox2D R = P->PanelRectSu();
      TestTrue(FString::Printf(TEXT("%s: the HB-26 rect (%s)"), *T, *R.ToString()), R.Min.Equals(Want[C].Min, 0.01) && R.Max.Equals(Want[C].Max, 0.01));
      const float H = static_cast<float>(R.Max.Y - R.Min.Y);
      TestTrue(FString::Printf(TEXT("%s: header = the formula (%.1f)"), *T, P->GetHeaderSu()),
               FMath::IsNearlyEqual(P->GetHeaderSu(), HeaderSu(P->GetTitleSizeSu(), P->GetTitleLines(), 1, bOpp), 0.01f));
      TestTrue(FString::Printf(TEXT("%s: the viewport holds whole rows only (%d)"), *T, P->GetCapacity()),
               P->GetCapacity() == Capacity(H, P->GetHeaderSu()) && P->GetCapacity() >= 3 &&
                   P->GetHeaderSu() + P->GetCapacity() * RowSu + PadSu <= H + 0.01f);
      TestTrue(T + TEXT(": the scrollbar only for a longer list"), P->IsScrollbarShown() == (P->GetShownRowCount() > P->GetCapacity()));
      P->ScrollToRow(TNumericLimits<int32>::Max());
      TestTrue(T + TEXT(": -end shows the last row last"), P->GetFirstRow() + P->GetVisibleRows() == P->GetShownRowCount());
      TestTrue(T + TEXT(": a wheel notch moves one row"), P->WheelStep(true) && P->GetFirstRow() == P->GetShownRowCount() - P->GetCapacity() - 1);
    }
  }
  // ВР-VS3-37: a 9-card fan at 1080p reaches x 1540 under the panel - the bottom rises 8 su over its caption
  {
    const FUmDeckPanelFrame F = Frame(Canvases[0]);
    const FBox2D Fan(FVector2D(376.0, 874.0), FVector2D(1540.0, 1080.0));
    const float Bottom = BottomOver(F.SlotSu, Fan);
    TestTrue(FString::Printf(TEXT("the bottom over the fan: 866 (%.1f)"), Bottom), FMath::IsNearlyEqual(Bottom, 866.0f, 0.01f));
    const FBox2D Five(FVector2D(567.0, 885.0), FVector2D(1349.0, 1080.0));
    TestTrue(TEXT("a centred 5-card row stays clear: the slot's bottom"), FMath::IsNearlyEqual(BottomOver(F.SlotSu, Five), 912.0f, 0.01f));
  }
  // HB-47: the skeleton (6 rows) before the list answers, after 300 ms
  {
    UUmHudDeckPanel* P = Make(W.World, Frame(Canvases[0]));
    FUmDeckPanelModel M = Model(Marm, false, false, TEXT("Medusa"));
    M.List = EUmDeckListState::Loading;
    M.Rows.Reset();
    P->ApplyModel(M);
    if (P->Skeleton) P->Skeleton->SetClockOverrideMs(0.0);
    TestTrue(TEXT("loading: nothing at the open"), P->ApplyView(1.0f, true, 1000.0).IsEmpty() && !P->IsSkeletonShown());
    TestTrue(TEXT("loading 290 ms: nothing"), P->ApplyView(1.0f, true, 1290.0).IsEmpty() && !P->IsSkeletonShown());
    const FString Line = P->ApplyView(1.0f, true, 1310.0);
    TestTrue(FString::Printf(TEXT("loading 310 ms: the skeleton (%s)"), *Line), P->IsSkeletonShown() && Line.Contains(TEXT("kind=skeleton shown=1 where=deckpanel")));
    TestEqual(TEXT("the skeleton: 6 rows"), P->Skeleton ? P->Skeleton->GetRowCount() : 0, SkeletonRows);
    M = Model(Marm, false, false, TEXT("Medusa"));
    P->ApplyModel(M);
    TestTrue(TEXT("the answer: the skeleton goes at once"), P->ApplyView(1.0f, true, 1400.0).Contains(TEXT("shown=0")) && !P->IsSkeletonShown());
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmDeckPanelAutoCloseTest,
    "Unmatched.S08.Hud.DeckPanel.AutoClose my turn and my defense close the panel; the view's clicks and fades; reduced 100 ms",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmDeckPanelAutoCloseTest::RunTest(const FString&) {
  using namespace UmDeckPanelTest;
  // the demand of the applied state (S09DeckPanel::InputDemandKey): opened in the opponent's turn, closed by my turn
  FS09DeckPanelView V;
  FS09DeckDemandInput In;
  In.bViewerTurn = false;
  In.TurnCount = 4;
  TestTrue(TEXT("open in the opponent's turn"), V.Open(ES09DeckSide::Own, 0, S09DeckPanel::InputDemandKey(In)));
  In.bViewerTurn = true;
  In.TurnCount = 5;
  TestTrue(TEXT("my turn starts: the panel closes by itself"), V.NoteDemand(S09DeckPanel::InputDemandKey(In), 1000) && !V.IsOpen());
  TestEqual(TEXT("the demand kind is the turn"), S09DeckPanel::DemandKind(V.LastDemand()), FString(TEXT("turn")));
  // opened in my turn it stays until a NEW demand: my defense window
  TestTrue(TEXT("open again in my turn"), V.Open(ES09DeckSide::Opponent, 2000, S09DeckPanel::InputDemandKey(In)));
  TestFalse(TEXT("the same demand does not close it"), V.NoteDemand(S09DeckPanel::InputDemandKey(In), 2100));
  In.bViewerTurn = false;
  In.bViewerDefends = true;
  In.CombatKey = TEXT("a>b");
  TestTrue(TEXT("my defense window: closed"), V.NoteDemand(S09DeckPanel::InputDemandKey(In), 3000) && !V.IsOpen());
  // the UMG view of the alpha: clicks only while open, the close fade lets them through, collapsed at 0
  FWorld W(TEXT("UmDeckPanelAutoClose"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudDeckPanel* P = Make(W.World, Frame(Canvases[0]));
  if (!TestNotNull(TEXT("panel"), P)) return false;
  P->ApplyModel(Model(Marmoreal(), false, false, TEXT("Medusa")));
  P->ApplyView(V.Opacity(3000), V.IsOpen(), 3000.0);
  TestEqual(TEXT("the close fade at its start: drawn, clicks through"), P->GetVisibility(), ESlateVisibility::HitTestInvisible);
  P->ApplyView(V.Opacity(3150), V.IsOpen(), 3150.0);
  TestEqual(TEXT("150 ms later: collapsed"), P->GetVisibility(), ESlateVisibility::Collapsed);
  TestTrue(TEXT("open 80 ms: half way at 40 ms"), V.Open(ES09DeckSide::Own, 4000, FString()) && FMath::IsNearlyEqual(V.Opacity(4040), 0.5f, 0.02f));
  P->ApplyView(V.Opacity(4080), V.IsOpen(), 4080.0);
  TestEqual(TEXT("open: the body takes clicks"), P->GetVisibility(), ESlateVisibility::SelfHitTestInvisible);
  TestTrue(TEXT("open: the pointer over the body is HUD"), P->ContainsSu(FVector2D(1600.0, 400.0)) && !P->ContainsSu(FVector2D(1000.0, 400.0)));
  // ВР-VS3-40: reduced motion closes in 100 ms (the view's 150 ms close mapped)
  V.Close(5000);
  TestTrue(TEXT("reduced: 1 at the close start"), FMath::IsNearlyEqual(UmHudDeckPanel::ReducedAlpha(V.Opacity(5000), false), 1.0f, 0.01f));
  TestTrue(TEXT("reduced: half at 50 ms"), FMath::IsNearlyEqual(UmHudDeckPanel::ReducedAlpha(V.Opacity(5050), false), 0.5f, 0.02f));
  TestTrue(TEXT("reduced: 0 at 100 ms"), UmHudDeckPanel::ReducedAlpha(V.Opacity(5100), false) <= 0.0f);
  TestTrue(TEXT("reduced: the open ramp unchanged (80 ms)"), FMath::IsNearlyEqual(UmHudDeckPanel::ReducedAlpha(0.5f, true), 0.5f));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmDeckPanelTreeTest,
    "Unmatched.S08.Hud.DeckPanel.Tree UUmHudDeckPanel default tree, every BindWidget, the GAME slot, WBP_UI_HUD_DECKPANEL",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmDeckPanelTreeTest::RunTest(const FString&) {
  using namespace UmDeckPanelTest;
  FWorld W(TEXT("UmDeckPanelTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudDeckPanel* P = CreateWidget<UUmHudDeckPanel>(W.World, UUmHudDeckPanel::StaticClass());
  if (!TestNotNull(TEXT("panel"), P)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), P->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("every BindWidget (missing: %s)"), *Missing), P->HasAllParts(&Missing));
  TestEqual(TEXT("closed until the owner's view opens it"), P->GetVisibility(), ESlateVisibility::Collapsed);
  TestEqual(TEXT("the body takes a click (never the board)"), P->Panel->GetVisibility(), ESlateVisibility::Visible);
  TestTrue(TEXT("the close glyph ui-close"), P->CloseButton && P->CloseButton->GetModel().IconName == FName(TEXT("ui-close")));
  UUmGameHud* Game = CreateWidget<UUmGameHud>(W.World, UUmGameHud::StaticClass());
  TestTrue(TEXT("GAME slot DeckPanel takes the block"), Game && Game->SetBlock(EUmGameSlot::DeckPanel, P));
  if (FPackageName::DoesPackageExist(UUmHudDeckPanel::WidgetBlueprintPath)) {
    UClass* Wbp = UUmHudDeckPanel::WidgetClass();
    TestTrue(TEXT("WBP_UI_HUD_DECKPANEL is a child of UUmHudDeckPanel"),
             Wbp && Wbp != UUmHudDeckPanel::StaticClass() && Wbp->IsChildOf(UUmHudDeckPanel::StaticClass()));
    UUmHudDeckPanel* FromWbp = Wbp ? CreateWidget<UUmHudDeckPanel>(W.World, Wbp) : nullptr;
    TestTrue(TEXT("the WBP has every BindWidget"), FromWbp && FromWbp->HasAllParts() && !FromWbp->UsesCodeDefaultTree());
  } else {
    AddWarning(TEXT("WBP_UI_HUD_DECKPANEL not generated in this checkout (the code tree is tested)"));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmDeckPanelBlocksTest,
    "Unmatched.S08.Hud.DeckPanel.Blocks the game mode side - build, rollback, refresh, the filter on open, the first frame",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmDeckPanelBlocksTest::RunTest(const FString&) {
  using namespace UmDeckPanelTest;
  FRu Ru;
  FWorld W(TEXT("UmDeckPanelBlocks"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  // the rollback: neither block
  {
    UUmGameHud* Game = CreateWidget<UUmGameHud>(W.World, UUmGameHud::StaticClass());
    FUmDeckBlocks B;
    const TArray<FString> Lines = B.Build(*Game, S08ArtLook::ParseSlateHud(TEXT("-S08SlateHud=decks,deckpanel")), Arbiter, {});
    TestTrue(TEXT("rollback: no UMG block"), !B.DecksOnUmg() && !B.PanelOnUmg());
    TestTrue(TEXT("rollback traced"), Lines.Num() == 2 && Lines[0].Contains(TEXT("impl=slate")) && Lines[1].Contains(TEXT("impl=slate")));
  }
  UUmGameHud* Game = CreateWidget<UUmGameHud>(W.World, UUmGameHud::StaticClass());
  FUmDeckBlocks B;
  const TArray<FString> Lines = B.Build(*Game, S08ArtLook::ParseSlateHud(TEXT("")), Arbiter, {});
  TestTrue(TEXT("both blocks built into the GAME slots"), B.DecksOnUmg() && B.PanelOnUmg() && Game->Decks->GetContent() == B.GetDecks() &&
                                                              Game->DeckPanel->GetContent() == B.GetPanel());
  TestTrue(TEXT("built traced"), Lines.Num() == 2 && Lines[0].Contains(TEXT("HUD-DECKS-UMG impl=umg created=1")));
  const FMoment M = Marmoreal();
  const TArray<FS09DeckList> Lists = {M.OwnList, M.OppList};
  const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1920.0, 1080.0), 1.0f, nullptr);
  FUmDeckBlocksInput In;
  In.Layout = &L;
  In.bLive = true;
  In.Own = &M.Own;
  In.Opp = &M.Opp;
  In.OwnHero = TEXT("Medusa");
  In.OwnSlug = TEXT("medusa");
  In.OppHero = TEXT("King Arthur");
  In.OppSlug = TEXT("king-arthur");
  In.Lists = &Lists;
  In.ListState = EUmDeckListState::Loaded;
  TestTrue(TEXT("closed: no model line"), B.Refresh(In).IsEmpty());
  TestTrue(TEXT("the chips follow the snapshot"), B.GetDecks()->GetModel().bShow && B.GetDecks()->GetModel().DeckCount == 23);
  // D / the discard chip: the next fresh open shows «Только сброс»
  B.RequestFilterOnOpen();
  In.bPanelOpen = true;
  In.bPanelVisible = true;
  const FString Line = B.Refresh(In);
  TestTrue(FString::Printf(TEXT("open: the DE-030 model line of the own side (%s)"), *Line), Line.StartsWith(TEXT("DECK model side=own list=1 kinds=11")));
  TestTrue(TEXT("opened by D: the filter is on"), B.GetFilter() && B.GetPanel()->GetModel().bFilterDiscard);
  In.bPanelOpen = false;
  In.bPanelVisible = false;
  B.Refresh(In);
  In.bPanelOpen = true;
  In.bPanelVisible = true;
  In.Side = ES09DeckSide::Opponent;
  B.Refresh(In);
  TestFalse(TEXT("a fresh open by K: the filter is off"), B.GetFilter());
  TestTrue(TEXT("the opponent's side, his hero"), B.GetPanel()->GetModel().Side == ES09DeckSide::Opponent &&
                                                     B.GetPanel()->GetModel().HeroName == TEXT("King Arthur"));
  // the first drawn frame of an open refreshes before it draws; later frames do not
  int32 Refreshes = 0;
  B.GetPanel()->ApplyView(0.0f, false, 0.0);
  B.TickPanel(0.5f, true, 40.0, false, [&Refreshes]() { ++Refreshes; });
  B.TickPanel(1.0f, true, 80.0, false, [&Refreshes]() { ++Refreshes; });
  TestEqual(TEXT("one refresh on the first frame"), Refreshes, 1);
  // reduced motion: the close is over by 100 ms of the 150 ms view
  B.TickPanel(1.0f - 100.0f / 150.0f, false, 200.0, true, [&Refreshes]() { ++Refreshes; });
  TestEqual(TEXT("reduced: closed at 100 ms"), B.GetPanel()->GetVisibility(), ESlateVisibility::Collapsed);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
