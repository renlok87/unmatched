// VS-3 automation tests of DECKS (docs/game-design/visual/06-tasks/hud.csv HB-27; 04-hud-spec.md §2.9, §1.6, §7.1):
//   Unmatched.S08.Hud.Decks.Counts  the chips follow the applied snapshot: «Колода 23» / «Сброс 2» (RU, class L), the
//                                   number only in class S, «≈» before a stale count, the top card of the pile (a
//                                   face-down entry - its back), the empty pile - the resource-card icon 32 su under
//                                   1 px per su, else 24 su; the chip rects of HB-26 (L RU 156 / 124, EN 144 / 136, S
//                                   64 / 64 su) on 1080p / 720p x 100 / 150 %; the flights' centres; the SHOT line
//                                   (idle | stale, counts only); the presses (deck / discard) through the arbiter;
//                                   the same snapshot = no work; ApplyModel p95 within the budget (0.02 ms GT).
//   Unmatched.S08.Hud.Decks.Tree    BuildDefaultTree, every BindWidget, the GAME slot takes the block,
//                                   WBP_UI_HUD_DECKS a child of the base.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Decks" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../../S09/S09HudPress.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/ScaleBox.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/Regex.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"
#include "UmButton.h"
#include "UmCardWidget.h"
#include "UmGameHud.h"
#include "UmHudDecks.h"
#include "UmHudLayout.h"
#include "../S08AnimatedIconWidget.h"

namespace UmDecksTest {
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

/** RU for the test (the game default), the editor culture back at the end. */
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

bool ShotLineOk(const FString& Line) {
  FRegexMatcher M(FRegexPattern(TEXT("^SHOT widget id=(\\S+) impl=(umg|slate) state=(\\S+) fighter=(\\S+) "
                                     "bbox=\\((-?\\d+),(-?\\d+),(-?\\d+),(-?\\d+)\\) geom=(painted|unpainted) visible=([01]) "
                                     "twin=([01]) source=(\\S+)( .*)?$")),
                  Line);
  return M.FindNext();
}

FS09CardView Card(const TCHAR* Name, const TCHAR* Id, bool bHidden = false) {
  FS09CardView C;
  C.Name = Name;
  C.CardId = Id;
  C.InstanceId = FString::Printf(TEXT("inst::%s"), Id);
  C.CardType = TEXT("VERSATILE");
  C.bHidden = bHidden;
  return C;
}

/** Marmoreal, run I host seq 12 (HB-26 D2): own Medusa - deck 23, discard 2 (A Momentary Glance, then Feint), hand 5. */
FS09PlayerPanel Own() {
  FS09PlayerPanel P;
  P.PlayerId = TEXT("own");
  P.bIsViewer = true;
  P.DeckCount = 23;
  P.HandCount = 5;
  P.Discard.Add(Card(TEXT("A Momentary Glance"), TEXT("c-glance")));
  P.Discard.Add(Card(TEXT("Feint"), TEXT("c-feint")));
  return P;
}

struct FDecksCanvas {
  const TCHAR* Name;
  FVector2D Su;
  float Px;
};
const FDecksCanvas Canvases[] = {{TEXT("1080p100"), FVector2D(1920.0, 1080.0), 1.0f},
                            {TEXT("720p100"), FVector2D(1280.0 / 0.75, 960.0), 0.75f},
                            {TEXT("1080p150"), FVector2D(1280.0, 720.0), 1.5f},
                            {TEXT("720p150"), FVector2D(1280.0 / 1.125, 640.0), 1.125f}};

FUmDecksFrame Frame(const FDecksCanvas& C, bool bEnglish = false) {
  const FUmHudLayout L = FUmHudLayout::Compute(C.Su, C.Px, nullptr);
  FUmDecksFrame F;
  F.bClassS = L.bClassS;
  F.PxPerSu = C.Px;
  F.RectSu = L.Rect(EUmHudBlock::Decks);
  F.bEnglish = bEnglish;
  return F;
}

FVector2D PosOf(const UWidget* W) {
  const UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  return S ? S->GetPosition() : FVector2D(-1.0, -1.0);
}

FVector2D SizeOf(const UWidget* W) {
  const UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  return S ? S->GetSize() : FVector2D(-1.0, -1.0);
}
}  // namespace UmDecksTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmDecksCountsTest,
    "Unmatched.S08.Hud.Decks.Counts the chips follow the snapshot - labels, stale, top card, empty pile, rects, SHOT, presses",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmDecksCountsTest::RunTest(const FString&) {
  using namespace UmDecksTest;
  FRu Ru;
  FWorld W(TEXT("UmDecksCounts"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudDecks* D = CreateWidget<UUmHudDecks>(W.World, UUmHudDecks::StaticClass());
  if (!TestNotNull(TEXT("decks"), D)) return false;
  D->SetSyncLoad(true);
  D->SetLegacyForTest(0);
  // ---- the model of the snapshot ----
  FS09PlayerPanel P = Own();
  FUmDecksModel M = UmHudDecks::Gather(&P, TEXT("medusa"));
  TestTrue(TEXT("gather: deck 23, discard 2, fresh, top = the last entry"),
           M.bShow && M.DeckCount == 23 && M.DiscardCount == 2 && !M.bDeckStale && M.bHasTop && M.Top.Name == TEXT("Feint"));
  TestFalse(TEXT("no own panel: hidden"), UmHudDecks::Gather(nullptr, TEXT("medusa")).bShow);
  // ---- class L 1080p 100 %, RU ----
  D->SetFrame(Frame(Canvases[0]));
  D->ApplyModel(M);
  TestEqual(TEXT("L: «Колода 23»"), D->DeckCount->GetText().ToString(), FString(TEXT("Колода 23")));
  TestEqual(TEXT("L: «Сброс 2»"), D->DiscardCount->GetText().ToString(), FString(TEXT("Сброс 2")));
  TestTrue(TEXT("L: the deck chip is the own back face down"), D->DeckMini && D->DeckMini->GetState().bFaceDown &&
                                                                   D->DeckMini->GetState().HeroSlug == TEXT("medusa") &&
                                                                   D->DeckMini->GetState().Show == EUmCardShow::MiniChip);
  TestTrue(TEXT("L: the discard chip shows the top card face up"),
           D->DiscardMini && !D->DiscardMini->GetState().bFaceDown && D->DiscardMini->GetCard().Name == TEXT("Feint"));
  TestEqual(TEXT("L: the resource-card icon hides while the pile has a top"), D->DiscardIcon->GetVisibility(), ESlateVisibility::Collapsed);
  // the chip rects (HB-26 delta 04): [1608, 920, 156, 56] / [1772, 920, 124, 56]; the mini card 9 su in, the text 50 su
  TestTrue(FString::Printf(TEXT("L RU: deck chip 156 x 56 at x 0 of DECKS (%s)"), *SizeOf(D->DeckChip).ToString()),
           PosOf(D->DeckChip).Equals(FVector2D(0.0, 0.0)) && SizeOf(D->DeckChip).Equals(FVector2D(156.0, 56.0)));
  TestTrue(FString::Printf(TEXT("L RU: discard chip 124 x 56 at x 164 (%s)"), *PosOf(D->DiscardChip).ToString()),
           PosOf(D->DiscardChip).Equals(FVector2D(164.0, 0.0)) && SizeOf(D->DiscardChip).Equals(FVector2D(124.0, 56.0)));
  TestTrue(TEXT("L: the mini card 32 x 45 at (9, 5.5)"), D->DeckMiniBox && PosOf(D->DeckMiniBox).Equals(FVector2D(9.0, 5.5)) &&
                                                             SizeOf(D->DeckMiniBox).Equals(FVector2D(32.0, 45.0)));
  TestTrue(TEXT("L: the label 50 su in, centred on the chip"), PosOf(D->DeckCount).Equals(FVector2D(50.0, 28.0)));
  // ---- stale (HB-26 chips-stale: Marmoreal host seq 10 «≈24») ----
  P.DeckCount = 24;
  P.bDeckCountStale = true;
  D->ApplyModel(UmHudDecks::Gather(&P, TEXT("medusa")));
  TestEqual(TEXT("stale: «Колода ≈24»"), D->DeckCount->GetText().ToString(), FString(TEXT("Колода ≈24")));
  TestEqual(TEXT("stale: state=stale"), FString(UmHudDecks::StateName(D->GetModel())), FString(TEXT("stale")));
  P.bDiscardStale = true;
  D->ApplyModel(UmHudDecks::Gather(&P, TEXT("medusa")));
  TestEqual(TEXT("stale discard: «Сброс ≈2»"), D->DiscardCount->GetText().ToString(), FString(TEXT("Сброс ≈2")));
  // ---- the same snapshot = no work ----
  const int32 Applies = D->GetApplyCount();
  D->ApplyModel(UmHudDecks::Gather(&P, TEXT("medusa")));
  TestEqual(TEXT("the same snapshot: no work"), D->GetApplyCount(), Applies);
  // ---- a face-down top (a combat card before its reveal): its back ----
  P = Own();
  P.Discard.Add(Card(TEXT(""), TEXT("hidden"), true));
  D->ApplyModel(UmHudDecks::Gather(&P, TEXT("medusa")));
  TestTrue(TEXT("a face-down top shows the back"), D->DiscardMini->GetState().bFaceDown);
  // ---- the empty pile: the resource-card icon (IC-34 П-1: 32 su under 1 px per su, else 24) ----
  P = Own();
  P.Discard.Reset();
  D->SetFrame(Frame(Canvases[1]));  // 720p 100 %: 0.75 px per su
  D->ApplyModel(UmHudDecks::Gather(&P, TEXT("medusa")));
  TestTrue(TEXT("empty pile: the icon instead of the mini card"), D->DiscardIcon->GetVisibility() == ESlateVisibility::HitTestInvisible &&
                                                                     D->DiscardMiniBox->GetVisibility() == ESlateVisibility::Collapsed);
  TestEqual(TEXT("720p 100 %: the icon 32 su (24 px)"), D->DiscardIcon->GetDisplaySizeSu(), 32.0f);
  TestEqual(TEXT("«Сброс 0»"), D->DiscardCount->GetText().ToString(), FString(TEXT("Сброс 0")));
  D->SetFrame(Frame(Canvases[0]));
  TestEqual(TEXT("1080p 100 %: the icon 24 su"), D->DiscardIcon->GetDisplaySizeSu(), 24.0f);
  // ---- class S: two 64 x 48 chips, the number only, the mini card 18 x 25.3 ----
  P = Own();
  D->SetFrame(Frame(Canvases[2]));
  D->ApplyModel(UmHudDecks::Gather(&P, TEXT("medusa")));
  TestEqual(TEXT("S: «23»"), D->DeckCount->GetText().ToString(), FString(TEXT("23")));
  TestEqual(TEXT("S: «2»"), D->DiscardCount->GetText().ToString(), FString(TEXT("2")));
  TestTrue(TEXT("S: chips 64 x 48, 8 su apart"), SizeOf(D->DeckChip).Equals(FVector2D(64.0, 48.0)) &&
                                                     PosOf(D->DiscardChip).Equals(FVector2D(72.0, 0.0)) &&
                                                     SizeOf(D->DiscardChip).Equals(FVector2D(64.0, 48.0)));
  TestTrue(FString::Printf(TEXT("S: the mini card 18 x 25.3 at x 5 (%s)"), *SizeOf(D->DeckMiniBox).ToString()),
           FMath::IsNearlyEqual(PosOf(D->DeckMiniBox).X, 5.0, 0.01) && SizeOf(D->DeckMiniBox).Equals(FVector2D(18.0, 25.3125), 0.01));
  TestTrue(TEXT("S: the number 28 su in"), FMath::IsNearlyEqual(PosOf(D->DeckCount).X, 28.0, 0.01));
  // ---- every canvas: the chips inside DECKS, the flight centres on them ----
  for (const FDecksCanvas& C : Canvases) {
    for (const bool bEn : {false, true}) {
      FUmHudLayout L = FUmHudLayout::Compute(C.Su, C.Px, nullptr);
      L.bEnglishChips = bEn;
      const FBox2D Decks = L.Rect(EUmHudBlock::Decks);
      const FBox2D A = UmHudLayout::DeckChipRect(Decks, L.bClassS, bEn, 0);
      const FBox2D B = UmHudLayout::DeckChipRect(Decks, L.bClassS, bEn, 1);
      const FString T = FString::Printf(TEXT("%s %s"), C.Name, bEn ? TEXT("en") : TEXT("ru"));
      TestTrue(T + TEXT(": both chips inside DECKS, 8 su apart"),
               A.Min.X >= Decks.Min.X - 0.01 && B.Max.X <= Decks.Max.X + 0.01 && FMath::IsNearlyEqual(B.Min.X - A.Max.X, 8.0, 0.01) &&
                   A.Max.Y <= Decks.Max.Y + 0.01);
      TestTrue(T + TEXT(": the draw flies from the deck chip"), L.DeckChipCentreSu().Equals(A.GetCenter(), 0.01));
      TestTrue(T + TEXT(": the combat cards go to the discard chip"), L.DiscardChipCentreSu().Equals(B.GetCenter(), 0.01));
    }
  }
  // ---- the SHOT line (counts only) ----
  P = Own();
  D->SetFrame(Frame(Canvases[0]));
  D->ApplyModel(UmHudDecks::Gather(&P, TEXT("medusa")));
  D->SetVisibility(ESlateVisibility::SelfHitTestInvisible);
  TArray<FString> Lines;
  D->CollectShotLines(Lines);
  TestEqual(TEXT("one SHOT line"), Lines.Num(), 1);
  if (Lines.Num() == 1) {
    TestTrue(FString::Printf(TEXT("SHOT format (%s)"), *Lines[0]), ShotLineOk(Lines[0]));
    TestTrue(TEXT("SHOT: idle, the DECKS bbox, counts"),
             Lines[0].Contains(TEXT("id=UI-HUD-DECKS impl=umg state=idle")) && Lines[0].Contains(TEXT("bbox=(1608,920,1896,976)")) &&
                 Lines[0].Contains(TEXT("deck=23 discard=2")) && Lines[0].Contains(TEXT("chips=156x56,124x56")));
    TestFalse(TEXT("SHOT: no card name"), Lines[0].Contains(TEXT("Feint")));
  }
  // ---- the presses: the deck chip and the discard chip through the arbiter ----
  TSharedPtr<FS09HudPressArbiter> Arbiter = MakeShared<FS09HudPressArbiter>();
  int32 DeckPresses = 0, DiscardPresses = 0;
  D->SetInput(Arbiter, [&DeckPresses, &DiscardPresses](const FS09HudPressOutcome& O, bool bDiscard) {
    if (O.Result == ES09HudPressResult::Act) ++(bDiscard ? DiscardPresses : DeckPresses);
  });
  TestEqual(TEXT("press id of the deck chip"), D->DeckChip->GetPressId(), FName(TEXT("hud.decks.deck")));
  TestEqual(TEXT("press id of the discard chip"), D->DiscardChip->GetPressId(), FName(TEXT("hud.decks.discard")));
  const FVector2D At(10.0, 10.0);
  const FGeometry Geo = FGeometry::MakeRoot(FVector2D(156.0, 56.0), FSlateLayoutTransform());
  for (UUmButton* B : {D->DeckChip.Get(), D->DiscardChip.Get()}) {
    const FPointerEvent Down(0, At, At, TSet<FKey>{EKeys::LeftMouseButton}, EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
    const FPointerEvent Up(0, At, At, TSet<FKey>(), EKeys::LeftMouseButton, 0.0f, FModifierKeysState());
    B->NativeOnMouseButtonDown(Geo, Down);
    B->NativeOnMouseButtonUp(Geo, Up);
  }
  TestTrue(FString::Printf(TEXT("one press each (deck %d, discard %d)"), DeckPresses, DiscardPresses), DeckPresses == 1 && DiscardPresses == 1);
  // ---- the budget: a changing snapshot p95 (HB-27: <= 0.02 ms GT) ----
  TArray<double> Ms;
  for (int32 I = 0; I < 200; ++I) {
    P.DeckCount = 23 - (I % 20);
    P.bDeckCountStale = (I % 3) == 0;
    const double T0 = FPlatformTime::Seconds();
    D->ApplyModel(UmHudDecks::Gather(&P, TEXT("medusa")));
    Ms.Add((FPlatformTime::Seconds() - T0) * 1000.0);
  }
  Ms.Sort();
  const double P95 = Ms[FMath::CeilToInt(0.95 * Ms.Num()) - 1];
  AddInfo(FString::Printf(TEXT("DECKS ApplyModel p50 %.4f p95 %.4f ms (200 snapshots)"), Ms[Ms.Num() / 2], P95));
  TestTrue(FString::Printf(TEXT("ApplyModel p95 %.4f ms <= 0.05 ms (budget 0.02 ms GT p95, editor build)"), P95), P95 <= 0.05);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmDecksTreeTest,
    "Unmatched.S08.Hud.Decks.Tree UUmHudDecks default tree, every BindWidget, the GAME slot, WBP_UI_HUD_DECKS",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmDecksTreeTest::RunTest(const FString&) {
  using namespace UmDecksTest;
  FWorld W(TEXT("UmDecksTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  UUmHudDecks* D = CreateWidget<UUmHudDecks>(W.World, UUmHudDecks::StaticClass());
  if (!TestNotNull(TEXT("decks"), D)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), D->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("every BindWidget (missing: %s)"), *Missing), D->HasAllParts(&Missing));
  TestEqual(TEXT("the block only hears the pointer"), D->GetVisibility(), ESlateVisibility::SelfHitTestInvisible);
  TestEqual(TEXT("the counts never take it"), D->DeckCount->GetVisibility(), ESlateVisibility::HitTestInvisible);
  TestEqual(TEXT("the mini cards never take it"), D->DeckMiniBox->GetVisibility(), ESlateVisibility::HitTestInvisible);
  UUmGameHud* Game = CreateWidget<UUmGameHud>(W.World, UUmGameHud::StaticClass());
  TestTrue(TEXT("GAME slot Decks takes the block"), Game && Game->SetBlock(EUmGameSlot::Decks, D));
  if (FPackageName::DoesPackageExist(UUmHudDecks::WidgetBlueprintPath)) {
    UClass* Wbp = UUmHudDecks::WidgetClass();
    TestTrue(TEXT("WBP_UI_HUD_DECKS is a child of UUmHudDecks"), Wbp && Wbp != UUmHudDecks::StaticClass() && Wbp->IsChildOf(UUmHudDecks::StaticClass()));
    UUmHudDecks* FromWbp = Wbp ? CreateWidget<UUmHudDecks>(W.World, Wbp) : nullptr;
    TestTrue(TEXT("the WBP has every BindWidget"), FromWbp && FromWbp->HasAllParts() && !FromWbp->UsesCodeDefaultTree());
  } else {
    AddWarning(TEXT("WBP_UI_HUD_DECKS not generated in this checkout (the code tree is tested)"));
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
