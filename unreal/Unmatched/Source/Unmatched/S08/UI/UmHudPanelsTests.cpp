// VS-2 HB-18...HB-21 tests (docs/game-design/visual/06-tasks/hud.csv HB-18, HB-19, HB-20, HB-21; 04-hud-spec.md §2.2,
// §2.3, §7.1; CX-09 mockup):
//   Unmatched.S08.Hud.PlayerPanel.Tree       UUmHudPlayerPanel: code tree and WBP_UI_HUD_PANEL_LOC / _OPP, every
//                                            BindWidget, the portrait as the circle (panel mode), the class places of
//                                            CX-09 (L 104 / 80 / 32, S 80 / 64 / 24), RU status words, HP «14/16»,
//                                            the name size rule, theme colours, the SHOT line.
//   Unmatched.S08.Hud.PlayerPanel.Sidekicks  the gatherer: Merlin - one named sidekick, the harpies - three numbered
//                                            1-3 (ВР-72); a fallen one stays (cross or gone); L row items, S tooltip rows.
//   Unmatched.S08.Hud.PlayerPanel.Monogram   no registry key - the monogram circle (CP-08 fallback); sidekick keys and
//                                            numbers from labels.
//   Unmatched.S08.Hud.PlayerPanel.TurnLook   AB-5...AB-8 in the panel: ring, tracker into TrackerRow, heart glow, the
//                                            cross; the rollback flags; ring.smoulder L 0.35 / S 0.55 (ВР-43).
//   Unmatched.S08.Hud.PlayerPanel.OppMirror  PANEL-OPP right-top (ВР-01), mirrored places, «ИИ думает» pulse (1 Hz,
//                                            reduced static), their turn without a status word, the state rules.
//   Unmatched.S08.Hud.OppHand.Fan            the step of 0 / 5 / 10 / 12 backs (width <= 300 su), caption RU with «≈»,
//                                            the slide in / fade out, the back texture of each hero, the SHOT count.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud" <abs log>
#if WITH_AUTOMATION_TESTS

#include "UmGameHud.h"
#include "UmHudLayout.h"
#include "UmHudOppHand.h"
#include "UmHudPanels.h"
#include "UmHudPlayerPanel.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "../S08AnimatedIconWidget.h"
#include "../S08TurnPortraitWidget.h"
#include "Blueprint/WidgetTree.h"
#include "Components/Border.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/Regex.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"

namespace UmPanelsTest {
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

bool ShotLineOk(const FString& Line) {
  FRegexMatcher M(FRegexPattern(TEXT("^SHOT widget id=(\\S+) impl=(umg|slate) state=(\\S+) fighter=(\\S+) "
                                     "bbox=\\((-?\\d+),(-?\\d+),(-?\\d+),(-?\\d+)\\) geom=(painted|unpainted) visible=([01]) "
                                     "twin=([01]) source=(\\S+)( .*)?$")),
                  Line);
  return M.FindNext();
}

FVector2D PosOf(const UWidget* W) {
  const UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  return S ? S->GetPosition() : FVector2D(-1.0, -1.0);
}

FVector2D AlignOf(const UWidget* W) {
  const UCanvasPanelSlot* S = W ? Cast<UCanvasPanelSlot>(W->Slot) : nullptr;
  return S ? S->GetAlignment() : FVector2D(-1.0, -1.0);
}

FUmPlayerPanelModel Model(const TCHAR* Name, int32 Hp, int32 Max, EUmPanelState State, bool bClassS = false) {
  FUmPlayerPanelModel M;
  M.HeroName = Name;
  M.bHasHp = true;
  M.Hp = Hp;
  M.MaxHp = Max;
  M.State = State;
  M.bClassS = bClassS;
  M.PxPerSu = bClassS ? 1.5f : 1.0f;
  return M;
}

UUmHudPlayerPanel* Make(UWorld* World, EUmPanelSide Side, const TCHAR* Flags = TEXT(""), bool bWbp = false) {
  UClass* Class = bWbp ? UUmHudPlayerPanel::WidgetClass(Side) : UUmHudPlayerPanel::StaticClass();
  UUmHudPlayerPanel* P = CreateWidget<UUmHudPlayerPanel>(World, Class);
  if (P) P->Setup(Side, FS08TurnHudLook::FromCommandLine(Flags), FLinearColor::Green);
  return P;
}

FS08BoardFighter Fighter(const TCHAR* Id, const TCHAR* Owner, const TCHAR* Label, bool bHero, int32 Hp, int32 Max,
                         const TCHAR* Slug) {
  FS08BoardFighter F;
  F.Id = Id;
  F.OwnerId = Owner;
  F.Name = Label;
  F.Label = Label;
  F.bIsHero = bHero;
  F.Health = Hp;
  F.MaxHealth = Max;
  F.X = 1;
  F.Y = 1;
  F.HeroSlug = Slug;
  return F;
}
}  // namespace UmPanelsTest

// ------------------------------------------------------------------------------------------------------------- Tree

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPlayerPanelTreeTest, "Unmatched.S08.Hud.PlayerPanel.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPlayerPanelTreeTest::RunTest(const FString&) {
  using namespace UmPanelsTest;
  FWorld W(TEXT("UmHudPanelTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FRu Ru;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  UUmHudPlayerPanel* P = Make(W.World, EUmPanelSide::Own);
  if (!TestNotNull(TEXT("panel"), P)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), P->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("every part bound (missing %s)"), *Missing), P->HasAllParts(&Missing));
  for (const EUmPanelSide Side : {EUmPanelSide::Own, EUmPanelSide::Opp}) {
    UClass* Wbp = UUmHudPlayerPanel::WidgetClass(Side);
    const FString Name = Side == EUmPanelSide::Own ? TEXT("WBP_UI_HUD_PANEL_LOC") : TEXT("WBP_UI_HUD_PANEL_OPP");
    if (Wbp == UUmHudPlayerPanel::StaticClass()) {
      AddWarning(Name + TEXT(" not authored yet: only the code tree checked"));
      continue;
    }
    UUmHudPlayerPanel* FromWbp = Make(W.World, Side, TEXT(""), true);
    TestTrue(Name + TEXT(": authored tree"), FromWbp && !FromWbp->UsesCodeDefaultTree());
    TestTrue(Name + TEXT(": every part bound"), FromWbp && FromWbp->HasAllParts(&Missing));
    TestTrue(Name + TEXT(": the circle is WBP_UmPortrait"),
             FromWbp && FromWbp->Portrait && !FromWbp->Portrait->UsesCodeDefaultTree());
    TestTrue(Name + TEXT(": the name has a real font"), FromWbp && FromWbp->NameText->GetFont().HasValidFont());
  }
  // the portrait is the circle: panel mode, the heart is the panel's HeartIcon, the tracker goes into its TrackerRow
  TestTrue(TEXT("portrait in panel mode"), P->Portrait->IsPanelMode());
  TestTrue(TEXT("the heart is the panel's HeartIcon"), P->Portrait->GetHeartIcon() == P->HeartIcon.Get());
  TestEqual(TEXT("the heart icon"), P->HeartIcon->GetIconId(), FName(TEXT("resource-hp-full")));
  P->Portrait->ApplyTracker(2, 0, true);
  TestEqual(TEXT("the tracker icons are in the panel's TrackerRow"), P->TrackerRow->GetChildrenCount(), 2);
  // L places (CX-09); the status words switch at once with reduced motion (the 120 ms fade is checked below)
  P->SetReducedForTest(1);
  P->ApplyModel(Model(TEXT("Medusa"), 14, 16, EUmPanelState::Own));
  TestEqual(TEXT("L: ring window 104 su"), P->Portrait->GetRingWindowSu(), 104.0f);
  TestEqual(TEXT("L: tracker slots 32 su"), P->Portrait->GetTrackerSlotSu(), 32.0f);
  TestTrue(TEXT("L: ring at (4, 12)"), PosOf(P->Portrait).Equals(FVector2D(4.0, 12.0)));
  TestTrue(TEXT("L: text column at x 128"), FMath::IsNearlyEqual(PosOf(P->NameText).X, 128.0));
  TestTrue(TEXT("L: HP row at y 54"), FMath::IsNearlyEqual(PosOf(P->HpRow).Y, 54.0));
  TestTrue(TEXT("L: tracker right edge 328 (alignment 1)"),
           FMath::IsNearlyEqual(PosOf(P->TrackerRow).X, 328.0) && FMath::IsNearlyEqual(AlignOf(P->TrackerRow).X, 1.0));
  TestTrue(TEXT("L: the circle 80 su (avatar or monogram)"), FMath::IsNearlyEqual(P->Portrait->GetCircleSu(), 80.0f, 0.5f) ||
                                                                 P->Portrait->GetCircleSu() <= 80.0f);
  TestEqual(TEXT("own: «ВАШ ХОД»"), P->StatusText->GetText().ToString(), FString(TEXT("ВАШ ХОД")));
  TestTrue(TEXT("own: turn.flash.yellow"),
           P->StatusText->GetColorAndOpacity().GetSpecifiedColor().Equals(Theme.Color(TEXT("turn.flash.yellow")), 1e-3f));
  TestEqual(TEXT("HP «14/16»"), P->HpText->GetText().ToString(), FString(TEXT("14/16")));
  TestEqual(TEXT("name"), P->NameText->GetText().ToString(), FString(TEXT("Medusa")));
  P->ApplyModel(Model(TEXT("Medusa"), 14, 16, EUmPanelState::Wait));
  TestEqual(TEXT("wait: «ЖДЁТ»"), P->StatusText->GetText().ToString(), FString(TEXT("ЖДЁТ")));
  TestTrue(TEXT("wait: text.secondary"),
           P->StatusText->GetColorAndOpacity().GetSpecifiedColor().Equals(Theme.Color(TEXT("text.secondary")), 1e-3f));
  P->ApplyModel(Model(TEXT("Medusa"), 0, 16, EUmPanelState::Fallen));
  TestEqual(TEXT("fallen: «ВНЕ ИГРЫ»"), P->StatusText->GetText().ToString(), FString(TEXT("ВНЕ ИГРЫ")));
  TestTrue(TEXT("fallen: the circle loses its colour"), P->Portrait->GetPortraitState() == EUmPortraitState::Fallen);
  TestEqual(TEXT("fallen: «0/16»"), P->HpText->GetText().ToString(), FString(TEXT("0/16")));
  // 04 §2.2: type.heading up to 14 characters, else type.button
  TestEqual(TEXT("name 14 chars: type.heading"), UmHudPanel::NameFontToken(TEXT("King Arthur")), FName(TEXT("type.heading")));
  TestEqual(TEXT("name 15+ chars: type.button"), UmHudPanel::NameFontToken(TEXT("Sherlock Holmes!")), FName(TEXT("type.button")));
  // hud.csv HB-18: the status word of the turn fades out over 120 ms (icon.leave.ms), then the new one
  double Clock = 100.0;
  P->SetClockForTest([&Clock]() { return Clock; });
  P->ApplyModel(Model(TEXT("Medusa"), 14, 16, EUmPanelState::Own));
  P->SetReducedForTest(0);
  P->ApplyModel(Model(TEXT("Medusa"), 14, 16, EUmPanelState::Wait));
  TestTrue(TEXT("own -> wait: fading"), P->IsStatusFading());
  Clock += 0.06;
  P->StepMotion();
  TestTrue(TEXT("+60 ms: the old word half faded"), P->StatusText->GetText().ToString() == TEXT("ВАШ ХОД") &&
                                                       FMath::IsNearlyEqual(P->StatusText->GetRenderOpacity(), 0.5f, 0.05f));
  Clock += 0.07;
  P->StepMotion();
  TestTrue(TEXT("+130 ms: «ЖДЁТ» at full"), P->StatusText->GetText().ToString() == TEXT("ЖДЁТ") &&
                                               FMath::IsNearlyEqual(P->StatusText->GetRenderOpacity(), 1.0f));
  P->SetReducedForTest(1);
  // S places
  P->ApplyModel(Model(TEXT("Medusa"), 14, 16, EUmPanelState::Own, true));
  TestEqual(TEXT("S: ring window 80 su"), P->Portrait->GetRingWindowSu(), 80.0f);
  TestEqual(TEXT("S: tracker slots 24 su"), P->Portrait->GetTrackerSlotSu(), 24.0f);
  TestTrue(TEXT("S: text at x 92"), FMath::IsNearlyEqual(PosOf(P->NameText).X, 92.0));
  TestTrue(TEXT("S: tracker right edge 228"), FMath::IsNearlyEqual(PosOf(P->TrackerRow).X, 228.0));
  TestTrue(TEXT("S: no sidekick row"), P->SidekickRow->GetVisibility() == ESlateVisibility::Collapsed);
  // the plate never takes the mouse itself; the root does (the click opens the deck panel)
  TestTrue(TEXT("the plate is hit-test invisible"), P->Panel->GetVisibility() == ESlateVisibility::HitTestInvisible);
  // SHOT
  P->SetVisibility(ESlateVisibility::Visible);
  TArray<FString> Lines;
  P->CollectShotLines(Lines, FS08ScreenRect(24.0f, 920.0f, 364.0f, 1056.0f));
  TestTrue(TEXT("SHOT: one line"), Lines.Num() == 1);
  if (Lines.Num()) {
    TestTrue(TEXT("SHOT: format"), ShotLineOk(Lines[0]));
    TestTrue(TEXT("SHOT: UI-HUD-PANEL-LOC state=own"), Lines[0].StartsWith(TEXT("SHOT widget id=UI-HUD-PANEL-LOC impl=umg state=own ")));
    TestTrue(TEXT("SHOT: painted"), Lines[0].Contains(TEXT("geom=painted visible=1")));
  }
  return true;
}

// ------------------------------------------------------------------------------------------------------- Sidekicks

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPlayerPanelSidekicksTest, "Unmatched.S08.Hud.PlayerPanel.Sidekicks",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPlayerPanelSidekicksTest::RunTest(const FString&) {
  using namespace UmPanelsTest;
  FWorld W(TEXT("UmHudPanelSidekicks"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FRu Ru;
  TArray<FS08BoardFighter> Fighters = {
      Fighter(TEXT("f-0-h"), TEXT("p0"), TEXT("King Arthur"), true, 17, 18, TEXT("king-arthur")),
      Fighter(TEXT("f-0-sk0"), TEXT("p0"), TEXT("Merlin"), false, 7, 7, TEXT("king-arthur")),
      Fighter(TEXT("f-1-h"), TEXT("p1"), TEXT("Medusa"), true, 14, 16, TEXT("medusa")),
      Fighter(TEXT("f-1-sk2"), TEXT("p1"), TEXT("Harpies 3"), false, 1, 1, TEXT("medusa")),
      Fighter(TEXT("f-1-sk0"), TEXT("p1"), TEXT("Harpies 1"), false, 1, 1, TEXT("medusa")),
      Fighter(TEXT("f-1-sk1"), TEXT("p1"), TEXT("Harpies 2"), false, 1, 1, TEXT("medusa")),
  };
  TSet<FString> Crossed;
  auto IsFallen = [&Crossed](const FString& Id) { return Crossed.Contains(Id); };
  UmHudPanel::FSideMemory Arthur, Medusa;
  FUmPlayerPanelModel A = UmHudPanel::Gather(EUmPanelSide::Own, TEXT("p0"), FString(), Fighters, true, false, false, IsFallen, Arthur);
  TestEqual(TEXT("Merlin: one sidekick"), A.Sidekicks.Num(), 1);
  if (A.Sidekicks.Num() == 1) {
    TestEqual(TEXT("Merlin: named (no number)"), A.Sidekicks[0].Number, 0);
    TestEqual(TEXT("Merlin: key king-arthur/merlin"), A.Sidekicks[0].Key, FName(TEXT("king-arthur/merlin")));
    TestEqual(TEXT("Merlin: 7/7"), A.Sidekicks[0].Hp * 10 + A.Sidekicks[0].MaxHp, 77);
  }
  TestEqual(TEXT("own turn: own"), UmHudPanel::StateName(A.State), TEXT("own"));
  TestEqual(TEXT("hero name from the fighter"), A.HeroName, FString(TEXT("King Arthur")));
  FUmPlayerPanelModel M = UmHudPanel::Gather(EUmPanelSide::Own, TEXT("p1"), TEXT("Medusa"), Fighters, false, false, false, IsFallen, Medusa);
  TestEqual(TEXT("harpies: three sidekicks"), M.Sidekicks.Num(), 3);
  for (int32 I = 0; I < M.Sidekicks.Num(); ++I) {
    TestEqual(FString::Printf(TEXT("harpy %d: number in order (ВР-72)"), I + 1), M.Sidekicks[I].Number, I + 1);
    TestEqual(TEXT("harpy key medusa/harpies"), M.Sidekicks[I].Key, FName(TEXT("medusa/harpies")));
  }
  TestEqual(TEXT("not their turn: wait"), UmHudPanel::StateName(M.State), TEXT("wait"));
  // a fallen harpy: the cross of the death stage, then gone from the projection - the plate stays
  Crossed.Add(TEXT("f-1-sk0"));
  M = UmHudPanel::Gather(EUmPanelSide::Own, TEXT("p1"), TEXT("Medusa"), Fighters, false, false, false, IsFallen, Medusa);
  TestTrue(TEXT("harpy 1 fallen at the cross"), M.Sidekicks.Num() == 3 && M.Sidekicks[0].bFallen);
  Fighters.RemoveAll([](const FS08BoardFighter& F) { return F.Id == TEXT("f-1-sk0"); });
  Crossed.Reset();
  M = UmHudPanel::Gather(EUmPanelSide::Own, TEXT("p1"), TEXT("Medusa"), Fighters, false, false, false, IsFallen, Medusa);
  TestTrue(TEXT("harpy 1 gone: still three, fallen, 0 HP"),
           M.Sidekicks.Num() == 3 && M.Sidekicks[0].bFallen && M.Sidekicks[0].Hp == 0 && M.Sidekicks[0].Number == 1);
  // the panel: L row items, S tooltip rows
  UUmHudPlayerPanel* P = Make(W.World, EUmPanelSide::Own);
  if (!TestNotNull(TEXT("panel"), P)) return false;
  M.bClassS = false;
  P->ApplyModel(M);
  TestEqual(TEXT("L: three items in the sidekick row"), P->GetSidekickItems(), 3);
  TestEqual(TEXT("L: SidekickRow children"), P->SidekickRow->GetChildrenCount(), 3);
  TestNull(TEXT("L: no tooltip"), P->GetSidekickTooltip());
  M.bClassS = true;
  M.PxPerSu = 1.5f;
  P->ApplyModel(M);
  TestEqual(TEXT("S: three tooltip rows (ВР-VS2-CX09-06)"), P->GetTooltipRows(), 3);
  TestNotNull(TEXT("S: the tooltip is set"), P->GetSidekickTooltip());
  TestEqual(TEXT("S: the row is empty"), P->SidekickRow->GetChildrenCount(), 0);
  TestEqual(TEXT("hud.panel.sidekick «Harpies 1 0/1»"), UmHudPanel::SidekickLine(M.Sidekicks[0]).ToString(),
            FString(TEXT("Harpies 1 0/1")));
  UUmHudPlayerPanel* Q = Make(W.World, EUmPanelSide::Own);
  A.bClassS = false;
  Q->ApplyModel(A);
  TestEqual(TEXT("Merlin: one item"), Q->GetSidekickItems(), 1);
  // a new hero id = a new game: the memory starts again
  TArray<FS08BoardFighter> NewGame = {Fighter(TEXT("g-1-h"), TEXT("p1"), TEXT("Medusa"), true, 16, 16, TEXT("medusa"))};
  M = UmHudPanel::Gather(EUmPanelSide::Own, TEXT("p1"), TEXT("Medusa"), NewGame, false, false, false, IsFallen, Medusa);
  TestEqual(TEXT("new game: no sidekick kept"), M.Sidekicks.Num(), 0);
  return true;
}

// -------------------------------------------------------------------------------------------------------- Monogram

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPlayerPanelMonogramTest, "Unmatched.S08.Hud.PlayerPanel.Monogram",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPlayerPanelMonogramTest::RunTest(const FString&) {
  using namespace UmPanelsTest;
  FWorld W(TEXT("UmHudPanelMonogram"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  TestEqual(TEXT("«Harpies 2» -> 2"), UmHudPanel::SidekickNumber(TEXT("Harpies 2")), 2);
  TestEqual(TEXT("«Merlin» -> 0"), UmHudPanel::SidekickNumber(TEXT("Merlin")), 0);
  TestEqual(TEXT("«12» alone -> 0 (no name)"), UmHudPanel::SidekickNumber(TEXT("12")), 0);
  TestEqual(TEXT("key medusa/harpies"), UmHudPanel::SidekickKey(TEXT("medusa"), TEXT("Harpies 3")), FName(TEXT("medusa/harpies")));
  TestEqual(TEXT("no slug - no key"), UmHudPanel::SidekickKey(TEXT(""), TEXT("Merlin")), FName(NAME_None));
  UUmHudPlayerPanel* P = Make(W.World, EUmPanelSide::Own);
  if (!TestNotNull(TEXT("panel"), P)) return false;
  P->Portrait->SetPortraitLegacyForTest(0);
  P->Portrait->SetPortrait(FName(TEXT("no-such-hero")));
  P->Portrait->SetHeroName(TEXT("King Arthur"));
  P->ApplyModel(Model(TEXT("King Arthur"), 18, 18, EUmPanelState::Own));
  TestFalse(TEXT("unknown key: no avatar"), P->Portrait->IsAvatarShown());
  TestEqual(TEXT("unknown key: the monogram «KA»"), P->Portrait->GetMonogram(), FString(TEXT("KA")));
  TestTrue(TEXT("monogram: the 80 su circle of the panel"), FMath::IsNearlyEqual(P->Portrait->GetCircleSu(), 80.0f));
  P->Portrait->SetPortrait(FName(TEXT("king-arthur")));
  TestTrue(TEXT("king-arthur: the avatar of the registry (CP-09)"), P->Portrait->IsAvatarShown());
  // a sidekick without a registry entry draws its monogram in the row (the panel builds it, a Warning in the log)
  FUmPlayerPanelModel M = Model(TEXT("King Arthur"), 18, 18, EUmPanelState::Own);
  FUmSidekickView S;
  S.Id = TEXT("x");
  S.Name = TEXT("Zeus");
  S.Key = FName(TEXT("king-arthur/zeus"));
  S.Hp = 3;
  S.MaxHp = 3;
  M.Sidekicks.Add(S);
  AddExpectedMessagePlain(TEXT("PORTRAIT fallback id=king-arthur/zeus"), ELogVerbosity::Warning,
                          EAutomationExpectedMessageFlags::Contains, 0);
  P->ApplyModel(M);
  TestEqual(TEXT("unknown sidekick: still one item"), P->GetSidekickItems(), 1);
  return true;
}

// -------------------------------------------------------------------------------------------------------- TurnLook

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPlayerPanelTurnLookTest, "Unmatched.S08.Hud.PlayerPanel.TurnLook",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPlayerPanelTurnLookTest::RunTest(const FString&) {
  using namespace UmPanelsTest;
  FWorld W(TEXT("UmHudPanelTurnLook"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  // the accepted look AB-5...AB-8 by default
  UUmHudPlayerPanel* P = Make(W.World, EUmPanelSide::Own);
  if (!TestNotNull(TEXT("panel"), P)) return false;
  P->ApplyModel(Model(TEXT("Medusa"), 14, 16, EUmPanelState::Own));
  US08TurnPortraitWidget* Portrait = P->Portrait;
  TestTrue(TEXT("AB-5: the ring marker-turn-ring"), Portrait->HasRingIcon() &&
                                                      Portrait->GetRingIcon()->GetIconId() == FName(TEXT("marker-turn-ring")));
  TestTrue(TEXT("ring window 104 su"), FMath::IsNearlyEqual(Portrait->GetRingIcon()->GetCanvasSizeSu().X, 104.0));
  TestTrue(TEXT("ВР-43: L smoulder 0.35 = the contract"),
           FMath::IsNearlyEqual(Portrait->GetRingIcon()->GetLayerOpacityScale(TEXT("rim")), 1.0f, 1e-3f));
  TestTrue(TEXT("theme ring.smoulder 0.35"), FMath::IsNearlyEqual(UmHudPanel::RingSmoulder(false), 0.35f, 1e-3f));
  Portrait->PlayRing(true);
  TestTrue(TEXT("ring shown"), Portrait->IsRingShown());
  Portrait->StopRing();
  TestFalse(TEXT("ring off in the opponent's turn"), Portrait->IsRingShown());
  P->ApplyModel(Model(TEXT("Medusa"), 14, 16, EUmPanelState::Own, true));
  TestTrue(TEXT("ВР-43: S smoulder 0.55 (rim x 0.55 / 0.35)"),
           FMath::IsNearlyEqual(Portrait->GetRingIcon()->GetLayerOpacityScale(TEXT("rim")), 0.55f / 0.35f, 1e-3f));
  // AB-7: the DE tracker into the panel's row, filled with the action type
  Portrait->ApplyTracker(2, 0, true);
  TestEqual(TEXT("AB-7: two DE slots in TrackerRow"), P->TrackerRow->GetChildrenCount(), 2);
  TestEqual(TEXT("AB-7: marker-action-slot-de"), Portrait->GetTrackerIcon(0)->GetIconId(), FName(TEXT("marker-action-slot-de")));
  TestEqual(TEXT("spend"), Portrait->ApplyTracker(2, 1, false, {FName(TEXT("attack"))}), FString(TEXT("spend")));
  TestEqual(TEXT("AB-7: the slot fills with attack"), Portrait->GetTrackerFill(0), FString(TEXT("attack")));
  TestTrue(TEXT("S: the slot 24 su"), FMath::IsNearlyEqual(Portrait->GetTrackerIcon(0)->GetCanvasSizeSu().X, 24.0));
  // AB-6: the heart's glow layer on, damage plays on the panel's heart
  TestFalse(TEXT("AB-6: glow layer shown"), P->HeartIcon->IsLayerHidden(TEXT("glow")));
  TestTrue(TEXT("damage plays"), Portrait->PlayHeart(TEXT("damage")));
  // AB-8: the cross
  TestTrue(TEXT("AB-8: the fallen heart"), Portrait->SetHeartFallen(true, true));
  TestEqual(TEXT("AB-8: resource-hp-fallen on the panel's heart"), P->HeartIcon->GetIconId(), FName(TEXT("resource-hp-fallen")));
  // the rollback flags work in the panel too
  UUmHudPlayerPanel* Legacy = Make(W.World, EUmPanelSide::Own,
                                   TEXT("-S08TurnRingLegacy -S08HeartGlowLegacy -S08TrackerLegacy -S08CrossLegacy"));
  Legacy->ApplyModel(Model(TEXT("Medusa"), 14, 16, EUmPanelState::Own));
  TestFalse(TEXT("-S08TurnRingLegacy: no ring"), Legacy->Portrait->HasRingIcon());
  TestTrue(TEXT("-S08HeartGlowLegacy: glow hidden"), Legacy->HeartIcon->IsLayerHidden(TEXT("glow")));
  Legacy->Portrait->ApplyTracker(2, 0, true);
  TestEqual(TEXT("-S08TrackerLegacy: the v3 slot"), Legacy->Portrait->GetTrackerIcon(0)->GetIconId(),
            FName(TEXT("resource-action-full")));
  TestFalse(TEXT("-S08CrossLegacy: no cross"), Legacy->Portrait->SetHeartFallen(true, true));
  // the look of the rollback column (-S08SlateHud=panels) keeps the constants
  US08TurnPortraitWidget* Column = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  Column->Setup(false, FS08TurnHudLook::FromCommandLine(TEXT("")), FLinearColor::Green);
  TestFalse(TEXT("column: not panel mode"), Column->IsPanelMode());
  TestEqual(TEXT("column: ring 64 su as before"), Column->GetRingWindowSu(), US08TurnPortraitWidget::RingSu);
  TestTrue(TEXT("column: the plate panel.bg (theme, no literal)"),
           Column->Panel->GetBrushColor().Equals(UUmHudTheme::Get().Color(TEXT("panel.bg")), 1e-3f));
  return true;
}

// ------------------------------------------------------------------------------------------------------- OppMirror

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudPlayerPanelOppMirrorTest, "Unmatched.S08.Hud.PlayerPanel.OppMirror",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudPlayerPanelOppMirrorTest::RunTest(const FString&) {
  using namespace UmPanelsTest;
  FWorld W(TEXT("UmHudPanelOpp"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FRu Ru;
  // ВР-01: the opponent top-right, diagonal to mine
  const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1920.0, 1080.0), 1.0f, nullptr);
  const FBox2D Opp = L.Rect(EUmHudBlock::PanelOpp);
  const FBox2D Loc = L.Rect(EUmHudBlock::PanelLoc);
  TestTrue(TEXT("1080p: PANEL-OPP (1556, 24, 340, 136)"), Opp.Min.Equals(FVector2D(1556.0, 24.0)) && Opp.Max.Equals(FVector2D(1896.0, 160.0)));
  TestTrue(TEXT("diagonal: LOC left-bottom, OPP right-top"), Loc.Min.X < Opp.Min.X && Loc.Min.Y > Opp.Max.Y);
  const FUmHudLayout S = FUmHudLayout::Compute(FVector2D(1137.78, 640.0), 1.6875f, nullptr);
  TestTrue(TEXT("720p 150 %: PANEL-OPP right-top 240 x 96"),
           FMath::IsNearlyEqual(S.Rect(EUmHudBlock::PanelOpp).Max.X, 1137.78 - 16.0, 0.1) &&
               FMath::IsNearlyEqual(S.Rect(EUmHudBlock::PanelOpp).Min.Y, 16.0));
  TestTrue(TEXT("720p 150 %: OPP-HAND 104 su high (CX-09)"),
           FMath::IsNearlyEqual(S.Rect(EUmHudBlock::OppHand).Max.Y - S.Rect(EUmHudBlock::OppHand).Min.Y, 104.0));
  // the mirrored places
  UUmHudPlayerPanel* P = Make(W.World, EUmPanelSide::Opp);
  if (!TestNotNull(TEXT("panel"), P)) return false;
  P->SetClockForTest([]() { return 0.0; });
  P->SetReducedForTest(1);  // the status words switch at once here
  P->ApplyModel(Model(TEXT("King Arthur"), 17, 18, EUmPanelState::Wait));
  TestTrue(TEXT("opp side"), P->GetSide() == EUmPanelSide::Opp);
  TestTrue(TEXT("L: the ring on the right (232, 12)"), PosOf(P->Portrait).Equals(FVector2D(232.0, 12.0)));
  TestTrue(TEXT("L: the text right edge 212, right-aligned"),
           FMath::IsNearlyEqual(PosOf(P->NameText).X, 212.0) && FMath::IsNearlyEqual(AlignOf(P->NameText).X, 1.0));
  TestTrue(TEXT("L: the HP group right-aligned"), FMath::IsNearlyEqual(AlignOf(P->HpRow).X, 1.0));
  TestTrue(TEXT("L: the tracker outside left (12, 46)"),
           PosOf(P->TrackerRow).Equals(FVector2D(12.0, 46.0)) && FMath::IsNearlyEqual(AlignOf(P->TrackerRow).X, 0.0));
  // their turn: no status word (ВР-VS2-CX09-07), the row keeps its place
  P->ApplyModel(Model(TEXT("King Arthur"), 17, 18, EUmPanelState::Opp));
  TestTrue(TEXT("opp: the status hidden, not collapsed"), P->StatusText->GetVisibility() == ESlateVisibility::Hidden);
  TestTrue(TEXT("opp: no dot"), P->PulseDot->GetVisibility() == ESlateVisibility::Collapsed);
  // VS_AI: «ИИ ДУМАЕТ» with the dot, 1 Hz 1 -> 0.35 -> 1; reduced static
  double Clock = 0.0;
  P->SetClockForTest([&Clock]() { return Clock; });
  P->ApplyModel(Model(TEXT("King Arthur"), 17, 18, EUmPanelState::Ai));
  P->SetReducedForTest(0);
  TestEqual(TEXT("ai: «ИИ ДУМАЕТ»"), P->StatusText->GetText().ToString(), FString(TEXT("ИИ ДУМАЕТ")));
  TestTrue(TEXT("ai: the dot shown"), P->PulseDot->GetVisibility() == ESlateVisibility::HitTestInvisible);
  P->StepMotion();
  const float A0 = P->GetDotOpacity();
  Clock = 0.5;
  P->StepMotion();
  const float A1 = P->GetDotOpacity();
  TestTrue(FString::Printf(TEXT("ai: pulse 1 -> 0.35 at 500 ms (%.2f -> %.2f)"), A0, A1),
           FMath::IsNearlyEqual(A0, 1.0f, 0.02f) && FMath::IsNearlyEqual(A1, 0.35f, 0.02f));
  P->SetReducedForTest(1);
  Clock = 0.25;
  P->StepMotion();
  TestTrue(TEXT("ai reduced: static 1"), FMath::IsNearlyEqual(P->GetDotOpacity(), 1.0f, 1e-3f));
  // the state rules of the opponent's side
  TArray<FS08BoardFighter> Fighters = {Fighter(TEXT("o-h"), TEXT("p1"), TEXT("King Arthur"), true, 17, 18, TEXT("king-arthur"))};
  UmHudPanel::FSideMemory Mem;
  auto Never = [](const FString&) { return false; };
  TestEqual(TEXT("their turn: opp"), UmHudPanel::StateName(UmHudPanel::Gather(EUmPanelSide::Opp, TEXT("p1"), FString(), Fighters,
                                                                             true, false, false, Never, Mem).State),
            TEXT("opp"));
  TestEqual(TEXT("their turn, VS_AI bot acting: ai"),
            UmHudPanel::StateName(UmHudPanel::Gather(EUmPanelSide::Opp, TEXT("p1"), FString(), Fighters, true, true, false, Never, Mem).State),
            TEXT("ai"));
  TestEqual(TEXT("my turn: wait"),
            UmHudPanel::StateName(UmHudPanel::Gather(EUmPanelSide::Opp, TEXT("p1"), FString(), Fighters, false, false, false, Never, Mem).State),
            TEXT("wait"));
  auto Always = [](const FString&) { return true; };
  TestEqual(TEXT("the hero's cross: fallen"),
            UmHudPanel::StateName(UmHudPanel::Gather(EUmPanelSide::Opp, TEXT("p1"), FString(), Fighters, true, true, false, Always, Mem).State),
            TEXT("fallen"));
  TArray<FString> Lines;
  P->SetVisibility(ESlateVisibility::Visible);
  P->CollectShotLines(Lines, FS08ScreenRect(1556.0f, 24.0f, 1896.0f, 160.0f));
  TestTrue(TEXT("SHOT: UI-HUD-PANEL-OPP state=ai"),
           Lines.Num() == 1 && Lines[0].StartsWith(TEXT("SHOT widget id=UI-HUD-PANEL-OPP impl=umg state=ai ")) && ShotLineOk(Lines[0]));
  return true;
}

// ------------------------------------------------------------------------------------------------------- OppHand.Fan

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudOppHandFanTest, "Unmatched.S08.Hud.OppHand.Fan",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudOppHandFanTest::RunTest(const FString&) {
  using namespace UmPanelsTest;
  FWorld W(TEXT("UmHudOppHandFan"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FRu Ru;
  // the step and the width: 0 / 5 / 10 / 12 backs in 300 su (and the S 220 su), never wider than the slot
  for (const float Width : {300.0f, 220.0f, 201.0f}) {
    for (const int32 N : {0, 5, 10, 12}) {
      const float Fan = UmHudOppHand::FanWidth(N, Width);
      TestTrue(FString::Printf(TEXT("%d backs in %.0f su: fan %.1f + pads <= the slot"), N, Width, Fan),
               Fan + 2.0f * UmHudOppHand::PadSu <= Width + 0.01f);
    }
  }
  TestEqual(TEXT("5 backs: step 28"), UmHudOppHand::Step(5, 300.0f), 28.0f);
  TestTrue(TEXT("10 backs in 300: step 25.3 (CX-09)"), FMath::IsNearlyEqual(UmHudOppHand::Step(10, 300.0f), 25.333f, 0.01f));
  TestTrue(TEXT("10 backs in 220: step 16.4 (CX-09)"), FMath::IsNearlyEqual(UmHudOppHand::Step(10, 220.0f), 16.444f, 0.01f));
  TestEqual(TEXT("0 backs: no fan"), UmHudOppHand::FanWidth(0, 300.0f), 0.0f);
  // the widget
  UUmHudOppHand* Code = CreateWidget<UUmHudOppHand>(W.World, UUmHudOppHand::StaticClass());
  if (!TestNotNull(TEXT("opp hand"), Code)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), Code->UsesCodeDefaultTree() && Code->HasAllParts(&Missing));
  if (UUmHudOppHand::WidgetClass() != UUmHudOppHand::StaticClass()) {
    UUmHudOppHand* FromWbp = CreateWidget<UUmHudOppHand>(W.World, UUmHudOppHand::WidgetClass());
    TestTrue(TEXT("WBP_UI_HUD_OPP_HAND: authored, every part"), FromWbp && !FromWbp->UsesCodeDefaultTree() && FromWbp->HasAllParts(&Missing));
    TestTrue(TEXT("WBP_UI_HUD_OPP_HAND: the caption has a real font"), FromWbp && FromWbp->Caption->GetFont().HasValidFont());
  } else {
    AddWarning(TEXT("WBP_UI_HUD_OPP_HAND not authored yet: only the code tree checked"));
  }
  double Clock = 10.0;
  Code->SetClockForTest([&Clock]() { return Clock; });
  Code->SetReducedForTest(0);
  FUmOppHandModel M;
  M.HandCount = 5;
  M.DeckCount = 24;
  M.DiscardCount = 1;
  M.HeroSlug = TEXT("king-arthur");
  Code->ApplyModel(M);
  TestEqual(TEXT("5 backs shown"), Code->GetBacksShown(), 5);
  TestEqual(TEXT("caption"), Code->Caption->GetText().ToString(), FString(TEXT("Рука 5 · колода 24 · сброс 1")));
  TestTrue(TEXT("the first model: at rest (a join shows the hand)"), FMath::IsNearlyEqual(Code->GetBackOpacity(4), 1.0f));
  TestTrue(TEXT("CP-05: the back of King Arthur"), Code->HasBackTexture());
  // a new card slides in over 180 ms
  M.HandCount = 6;
  Code->ApplyModel(M);
  TestEqual(TEXT("6 backs"), Code->GetBacksShown(), 6);
  TestTrue(TEXT("the new back starts faint"), Code->GetBackOpacity(5) < 0.5f);
  Clock += 0.2;
  Code->Step();
  TestTrue(TEXT("+200 ms: in place"), FMath::IsNearlyEqual(Code->GetBackOpacity(5), 1.0f));
  // a card leaves: fades over 120 ms, then the row has 5
  M.HandCount = 5;
  Code->ApplyModel(M);
  TestEqual(TEXT("leaving: still drawn"), Code->GetBacksShown(), 6);
  Clock += 0.15;
  Code->Step();
  TestEqual(TEXT("+150 ms: gone"), Code->GetBacksShown(), 5);
  // stale deck
  M.bDeckStale = true;
  Code->ApplyModel(M);
  TestEqual(TEXT("stale: «≈24»"), Code->Caption->GetText().ToString(), FString(TEXT("Рука 5 · колода ≈24 · сброс 1")));
  // Medusa's back (CP-06) and the fallback
  M.HeroSlug = TEXT("medusa");
  Code->ApplyModel(M);
  TestTrue(TEXT("CP-06: the back of Medusa"), Code->HasBackTexture());
  AddExpectedMessagePlain(TEXT("OPPHAND back fallback"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 0);
  M.HeroSlug = TEXT("no-such-hero");
  Code->ApplyModel(M);
  TestFalse(TEXT("no back: the flat fallback"), Code->HasBackTexture());
  TestEqual(TEXT("fallback: still 5 backs"), Code->GetBacksShown(), 5);
  // 12 backs in 300: the step shrinks
  M.HandCount = 12;
  M.HeroSlug = TEXT("medusa");
  Code->ApplyModel(M);
  TestTrue(TEXT("12 backs: step < 28"), Code->GetStepSu() < 28.0f);
  Code->SetVisibility(ESlateVisibility::Visible);
  TArray<FString> Lines;
  Code->CollectShotLines(Lines, FS08ScreenRect(1596.0f, 168.0f, 1896.0f, 260.0f));
  TestTrue(TEXT("SHOT: UI-HUD-OPP-HAND state=count=12"),
           Lines.Num() == 1 && Lines[0].StartsWith(TEXT("SHOT widget id=UI-HUD-OPP-HAND impl=umg state=count=12 ")) &&
               ShotLineOk(Lines[0]));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
