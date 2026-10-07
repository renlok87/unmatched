// VS-4 automation tests of the H12 world layer (docs/game-design/visual/06-tasks/hud.csv HB-45, HB-46; 04 §2.15):
//   Unmatched.S08.ArtHudUmg.TagTokens       the H12 tag in WBP_S08ArtTag / the code tree: no name (ВР-07), «{hp}/{max}»
//                                           type.tag 14 su (ВР-63), the capsule card.navy (ВР-61) 40 su high, the chip 24 su
//                                           (ВР-78) tinted team.p1 / team.p2.screen, the HP bar 40 x 4 hp.fill / hp.back,
//                                           the harpy digit 1-3 on a 16 su disc (card.cream text) only for the harpies (the
//                                           sidekicks[] number of the label), the traced parts; -S08SlateHud=tag the tree of
//                                           before (12 / 11 su, #161A28).
//   Unmatched.S08.ArtHudUmg.PlateHoverOnly  the H12 plate 268 x 144 su: the RU name from the data (Медуза, Король Артур,
//                                           Мерлин, Гарпия 1-3), the role from the data (hero / sidekick x ranged / melee),
//                                           ВАШ / СОПЕРНИК, «ЦЕЛЬ» only as the target; the fade in over hover.ms and out
//                                           over icon.leave.ms, then collapsed, reduced <= 100 ms; -S08SlateHud=plate the
//                                           plate of before.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.ArtHudUmg.TagTokens+Unmatched.S08.ArtHudUmg.PlateHoverOnly" <log>
#if WITH_AUTOMATION_TESTS

#include "../S08ArtHudWidgets.h"
#include "../S08ArtLook.h"
#include "../S08BoardModel.h"
#include "Components/Border.h"
#include "Components/Image.h"
#include "Components/SizeBox.h"
#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "UmCardMedia.h"
#include "UmHudTheme.h"
#include "UmText.h"
#include "UmWorldLayer.h"

namespace UmWorldTest {
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

/** The UI language RU with the game localization (as the combat / decks tests): the editor shows the EN source else. */
struct FRu {
  FInternationalization::FCultureStateSnapshot Snapshot;
  FRu() {
    FInternationalization::Get().BackupCultureState(Snapshot);
    FInternationalization::Get().SetCurrentLanguageAndLocale(TEXT("ru"));
#if WITH_EDITOR  // the preview API exists only WITH_EDITOR (the game target trap)
    FTextLocalizationManager::Get().EnableGameLocalizationPreview(TEXT("ru"));
#endif
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
  ~FRu() {
#if WITH_EDITOR  // never leak the preview into the next test (Hud.Actions measures the EN tooltip)
    FTextLocalizationManager::Get().DisableGameLocalizationPreview();
    FTextLocalizationManager::Get().WaitForAsyncTasks();  // as UmTextTests: the preview reload ends before the restore
#endif
    FInternationalization::Get().RestoreCultureState(Snapshot);
    FTextLocalizationManager::Get().WaitForAsyncTasks();
  }
};

FS08BoardFighter Fighter(const TCHAR* Slug, bool bHero, const TCHAR* Label, int32 Hp, int32 Max, const TCHAR* Attack) {
  FS08BoardFighter F;
  F.Id = FString::Printf(TEXT("f-%s"), Label);
  F.HeroSlug = Slug;
  F.bIsHero = bHero;
  F.Label = Label;
  F.Name = Label;
  F.Health = Hp;
  F.MaxHealth = Max;
  F.AttackType = Attack;
  F.X = 1;
  F.Y = 1;
  return F;
}
}  // namespace UmWorldTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmWorldTagTokensTest,
    "Unmatched.S08.ArtHudUmg.TagTokens H12 tag: no name, type.tag 14, card.navy capsule, chip 24, HP bar 40x4, harpy digits 1-3",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmWorldTagTokensTest::RunTest(const FString&) {
  using namespace UmWorldTest;
  S08ArtLook::SetSlateHudOverrideForTest(TEXT(""));
  FWorld W(TEXT("UmWorldTag"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  TestTrue(TEXT("no rollback: the H12 tag"), UmWorldLayer::TagV2());
  US08ArtTagWidget* Tag = CreateWidget<US08ArtTagWidget>(W.World, US08ArtTagWidget::StaticClass());
  if (!TestNotNull(TEXT("tag"), Tag)) return false;
  UmWorldLayer::SetupTag(*Tag);
  TestTrue(TEXT("SetupTag switched to V2"), Tag->IsV2() && Tag->GetV2() != nullptr);
  UUmWorldTag* V2 = Tag->GetV2();
  if (!V2) return false;
  // the six v2 figures: Medusa, the three harpies (labels 'Harpies 1..3' = sidekicks[] order), King Arthur, Merlin
  struct FCase {
    FS08BoardFighter F;
    int32 Digit;
  } Cases[] = {{Fighter(TEXT("medusa"), true, TEXT("Medusa"), 14, 16, TEXT("RANGED")), 0},
               {Fighter(TEXT("medusa"), false, TEXT("Harpies 1"), 1, 1, TEXT("MELEE")), 1},
               {Fighter(TEXT("medusa"), false, TEXT("Harpies 2"), 1, 1, TEXT("MELEE")), 2},
               {Fighter(TEXT("medusa"), false, TEXT("Harpies 3"), 1, 1, TEXT("MELEE")), 3},
               {Fighter(TEXT("king-arthur"), true, TEXT("King Arthur"), 17, 18, TEXT("MELEE")), 0},
               {Fighter(TEXT("king-arthur"), false, TEXT("Merlin"), 7, 7, TEXT("RANGED")), 0}};
  for (const FCase& C : Cases) {
    FS08TagTexts T;
    T.Name = FText::FromString(C.F.Label);
    T.Hp = UmWorldLayer::HpText(C.F.Health, C.F.MaxHealth);
    T.Mode = ES08TagMode::Full;  // even the full mode of before shows no name now (ВР-07)
    UmWorldLayer::FillTagTexts(T, C.F);
    Tag->ApplyModel(T);
    TestEqual(FString::Printf(TEXT("%s: digit"), *C.F.Label), Tag->GetHarpyDigit(), C.Digit);
    TestEqual(FString::Printf(TEXT("%s: digit disc shown only for a harpy"), *C.F.Label),
              V2->DigitBox->GetVisibility() != ESlateVisibility::Collapsed, C.Digit > 0);
    if (C.Digit > 0) TestEqual(FString::Printf(TEXT("%s: the digit text"), *C.F.Label), V2->DigitText->GetText().ToString(), FString::FromInt(C.Digit));
    TestEqual(FString::Printf(TEXT("%s: «{hp}/{max}»"), *C.F.Label), V2->HpLabel->GetText().ToString(),
              FString::Printf(TEXT("%d/%d"), C.F.Health, C.F.MaxHealth));
    TArray<FS08WidgetPart> Parts;
    Tag->CollectParts(Parts);
    bool bName = false;
    for (const FS08WidgetPart& P : Parts) bName |= P.Id == S08ArtHudIds::TagName;
    TestFalse(FString::Printf(TEXT("%s: no name part (ВР-07)"), *C.F.Label), bName);
    TestEqual(FString::Printf(TEXT("%s: parts tag, hp, bar, chip"), *C.F.Label), Parts.Num(), 4);
  }
  TestEqual(TEXT("HP text type.tag 14 su (ВР-63)"), Tag->HpFontSize(), 14);
  TestTrue(TEXT("HP text text.primary"), V2->HpLabel->GetColorAndOpacity().GetSpecifiedColor().Equals(Theme.Color(TEXT("text.primary"))));
  TestTrue(TEXT("digit text card.cream"), V2->DigitText->GetColorAndOpacity().GetSpecifiedColor().Equals(Theme.Color(TEXT("card.cream"))));
  TestTrue(TEXT("the tag background of before carries no #161A28 body (the V2 capsule paints it)"),
           Tag->TagBackground && Tag->TagBackground->GetContent() == V2);
  TestEqual(TEXT("chip 24 su (ВР-78)"), V2->ChipBox->GetWidthOverride(), 24.0f);
  TestEqual(TEXT("digit disc 16 su"), V2->DigitBox->GetWidthOverride(), 16.0f);
  TestTrue(TEXT("HP bar 40 x 4"), V2->BarBox->GetWidthOverride() == 40.0f && V2->BarBox->GetHeightOverride() == 4.0f);
  TestTrue(TEXT("hp.fill / hp.back"), V2->BarFillImage->GetColorAndOpacity().Equals(Theme.Color(TEXT("hp.fill"))) &&
                                          V2->BarBack->GetColorAndOpacity().Equals(Theme.Color(TEXT("hp.back"))));
  {
    FS08TagTexts T;
    T.TeamSlot = 1;
    UmWorldLayer::FillTagTexts(T, Cases[4].F);
    Tag->ApplyModel(T);
    TestTrue(TEXT("P2 chip team.p2.screen"), V2->Chip->GetColorAndOpacity().Equals(Theme.Color(TEXT("team.p2.screen"))));
  }
  // the rollback: the tree of before
  S08ArtLook::SetSlateHudOverrideForTest(TEXT("tag"));
  TestFalse(TEXT("-S08SlateHud=tag: no H12 tag"), UmWorldLayer::TagV2());
  US08ArtTagWidget* Old = CreateWidget<US08ArtTagWidget>(W.World, US08ArtTagWidget::StaticClass());
  UmWorldLayer::SetupTag(*Old);
  TestFalse(TEXT("-S08SlateHud=tag: the legacy tree"), Old->IsV2());
  TestEqual(TEXT("-S08SlateHud=tag: the HP text of before (11)"), Old->HpFontSize(), 11);
  S08ArtLook::ResetSlateHudOverrideForTest();
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmWorldPlateHoverOnlyTest,
    "Unmatched.S08.ArtHudUmg.PlateHoverOnly H12 plate: data name and role, side, target chip, fade 150 / 120 ms, rollback",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmWorldPlateHoverOnlyTest::RunTest(const FString&) {
  using namespace UmWorldTest;
  S08ArtLook::SetSlateHudOverrideForTest(TEXT(""));
  FRu Ru;
  FWorld W(TEXT("UmWorldPlate"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  US08ArtPlateWidget* Plate = CreateWidget<US08ArtPlateWidget>(W.World, US08ArtPlateWidget::StaticClass());
  if (!TestNotNull(TEXT("plate"), Plate)) return false;
  UmWorldLayer::SetupPlate(*Plate);
  TestTrue(TEXT("SetupPlate switched to V2"), Plate->IsV2() && Plate->GetV2() != nullptr);
  UUmWorldPlate* V2 = Plate->GetV2();
  if (!V2) return false;
  TestEqual(TEXT("the placement takes 268 x 144 su"), Plate->GetPlateSizeSu(), FVector2D(268.0, 144.0));
  const bool bRu = UmCardMedia::PreferredLang() != TEXT("en");
  struct FCase {
    FS08BoardFighter F;
    bool bOwn;
    const TCHAR* Ru;
    const TCHAR* RoleKey;
  } Cases[] = {{Fighter(TEXT("medusa"), true, TEXT("Medusa"), 14, 16, TEXT("RANGED")), true, TEXT("Медуза"), TEXT("hud.plate.role.hero_ranged")},
               {Fighter(TEXT("medusa"), false, TEXT("Harpies 2"), 1, 1, TEXT("MELEE")), true, TEXT("Гарпия 2"), TEXT("hud.plate.role.sidekick_melee")},
               {Fighter(TEXT("king-arthur"), true, TEXT("King Arthur"), 17, 18, TEXT("MELEE")), false, TEXT("Король Артур"), TEXT("hud.plate.role.hero_melee")},
               {Fighter(TEXT("king-arthur"), false, TEXT("Merlin"), 7, 7, TEXT("RANGED")), false, TEXT("Мерлин"), TEXT("hud.plate.role.sidekick_ranged")}};
  for (const FCase& C : Cases) {
    FS08PlateTexts T;
    T.bOwn = C.bOwn;
    UmWorldLayer::FillPlateTexts(T, C.F, C.bOwn, /*bTarget=*/false);
    Plate->ApplyTexts(T);
    if (bRu) TestEqual(FString::Printf(TEXT("%s: the RU name from the data"), *C.F.Label), V2->NameLabel->GetText().ToString(), FString(C.Ru));
    TestEqual(FString::Printf(TEXT("%s: the role"), *C.F.Label), V2->RoleLabel->GetText().ToString(),
              UmText::Get(EUmTable::Hud, C.RoleKey).ToString());
    TestEqual(FString::Printf(TEXT("%s: the side"), *C.F.Label), V2->SideLabel->GetText().ToString(),
              UmText::Get(EUmTable::Hud, C.bOwn ? TEXT("hud.plate.side.own") : TEXT("hud.plate.side.opponent")).ToString());
    TestFalse(FString::Printf(TEXT("%s: no «ЦЕЛЬ» outside the attack"), *C.F.Label), V2->IsTargetShown());
  }
  {
    FS08PlateTexts T;
    UmWorldLayer::FillPlateTexts(T, Cases[0].F, true, /*bTarget=*/true);
    Plate->ApplyTexts(T);
    TestTrue(TEXT("the attack target: «ЦЕЛЬ» shown"), V2->IsTargetShown());
    TestEqual(TEXT("«ЦЕЛЬ» from hud.plate.target"), V2->TargetLabel->GetText().ToString(), UmText::Get(EUmTable::Hud, TEXT("hud.plate.target")).ToString());
  }
  // the fade: hidden by default, in over hover.ms 150, out over icon.leave.ms 120, then collapsed
  double Clock = 50.0;
  V2->SetClockForTest([&Clock]() { return Clock; });
  V2->SetReducedForTest(0);
  Plate->SetVisibility(ESlateVisibility::Collapsed);
  Plate->SetShownAnimated(true);
  TestEqual(TEXT("shown: visible at once"), Plate->GetVisibility(), ESlateVisibility::HitTestInvisible);
  Clock += 0.075;
  V2->TickForTest();
  TestTrue(FString::Printf(TEXT("half way in (%.2f)"), V2->GetOpacityNow()), FMath::IsNearlyEqual(V2->GetOpacityNow(), 0.5f, 0.02f));
  Plate->SetShownAnimated(true);  // the views call it every frame: the running fade keeps its start
  TestTrue(TEXT("a repeated show does not restart the fade"), FMath::IsNearlyEqual(V2->GetOpacityNow(), 0.5f, 0.02f));
  Clock += 0.08;
  V2->TickForTest();
  TestEqual(TEXT("in after 150 ms"), V2->GetOpacityNow(), 1.0f);
  Plate->SetShownAnimated(false);
  Clock += 0.06;
  V2->TickForTest();
  TestTrue(TEXT("half way out, still visible"), V2->GetOpacityNow() > 0.4f && V2->GetOpacityNow() < 0.6f &&
                                                    Plate->GetVisibility() != ESlateVisibility::Collapsed);
  Clock += 0.07;
  V2->TickForTest();
  TestEqual(TEXT("out after 120 ms: collapsed (no permanent plate, ВР-07)"), Plate->GetVisibility(), ESlateVisibility::Collapsed);
  V2->SetReducedForTest(1);
  Plate->SetShownAnimated(true);
  Clock += 0.101;
  V2->TickForTest();
  TestEqual(TEXT("reduced motion: in within 100 ms"), V2->GetOpacityNow(), 1.0f);
  // the rollback: the plate of before
  S08ArtLook::SetSlateHudOverrideForTest(TEXT("plate"));
  US08ArtPlateWidget* Old = CreateWidget<US08ArtPlateWidget>(W.World, US08ArtPlateWidget::StaticClass());
  UmWorldLayer::SetupPlate(*Old);
  TestFalse(TEXT("-S08SlateHud=plate: the legacy plate"), Old->IsV2());
  TestEqual(TEXT("-S08SlateHud=plate: the size of before (172 x 54)"), Old->GetPlateSizeSu(), FVector2D(172.0, 54.0));
  S08ArtLook::ResetSlateHudOverrideForTest();
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
