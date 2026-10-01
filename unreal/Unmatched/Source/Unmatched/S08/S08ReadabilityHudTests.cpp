// ENV-MAPS P4 track C (concept review 2026-10-01 'readability', HIGH: HUD name/HP labels): automation tests of the
// map-image board plate of the screen tags - the hard padding between stacked tags (S08ArtHud::ChooseLabelRect,
// FLabelPlacementInput::HardPadPx) and the tag widget's board plate brush (US08ArtTagWidget::SetBoardPlate). Grid
// boards keep HardPadPx 0 and the flat opaque tag: both regressions are checked here too.
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.Readability; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08ArtHud.h"
#include "S08ArtHudStyle.h"
#include "S08ArtHudText.h"
#include "S08ArtHudWidgets.h"
#include "Blueprint/UserWidget.h"
#include "Components/Border.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ReadabilityTagPadTest,
    "Unmatched.S08.Readability.TagPad board-plate tags keep a hard gap to placed tags; grids keep the touching rule",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ReadabilityTagPadTest::RunTest(const FString&) {
  using namespace S08ArtHud;
  const FVector2D Viewport(1920.0, 1080.0);
  const FVector2D Size(60.0, 18.0);
  const FS08ScreenRect Owner(100.0f, 100.0f, 140.0f, 160.0f);
  // The ring-0 "above" candidate of the owner is (90,80)..(150,98); a tag already placed right of it touches it.
  const FS08ScreenRect Placed(150.0f, 80.0f, 210.0f, 98.0f);
  const TArray<FS08ScreenRect> Others;  // no other figures
  const TArray<FS08ScreenRect> Hard = {Placed};

  const FLabelPlacementInput Grid = MakeTagPlacementInput(Viewport, Size, Owner, Others, Hard);
  TestEqual("grid / default: no hard padding", Grid.HardPadPx, 0.0f);
  const FLabelPlacementResult Touching = ChooseLabelRect(Grid);
  TestTrue(FString::Printf(TEXT("grid: the touching ring-0 'above' candidate wins (%s %s)"), *Touching.Candidate,
                           *FormatRect(Touching.Rect)),
           Touching.bClean && Touching.Candidate == TEXT("above") && Touching.Ring == 0 &&
               FMath::IsNearlyEqual(Touching.Rect.X1, Placed.X0) && RectGap(Touching.Rect, Placed) < 0.5);

  const FLabelPlacementInput Board =
      MakeTagPlacementInput(Viewport, Size, Owner, Others, Hard, S08ArtHudBoardPlate::TagHardPadPx);
  TestEqual("board plate: 3 px hard padding", Board.HardPadPx, S08ArtHudBoardPlate::TagHardPadPx);
  const FLabelPlacementResult Gapped = ChooseLabelRect(Board);
  TestTrue(FString::Printf(TEXT("board plate: hard-clean and bound (%s %s ring %d)"), *Gapped.Candidate,
                           *FormatRect(Gapped.Rect), Gapped.Ring),
           Gapped.bHardClean && Gapped.bBound && !Gapped.Rect.IsEmpty());
  TestTrue(FString::Printf(TEXT("board plate: gap to the placed tag %.1f >= 3 px"), RectGap(Gapped.Rect, Placed)),
           RectGap(Gapped.Rect, Placed) >= S08ArtHudBoardPlate::TagHardPadPx - 1e-3);
  TestTrue("board plate: still next to its owner (within the first two rings)", Gapped.Ring <= 1);
  TestEqual("deterministic", ChooseLabelRect(Board).Rect.X0, Gapped.Rect.X0);
  // A negative pad is clamped (never a looser rule than the grid one).
  TestEqual("negative pad clamped to 0", MakeTagPlacementInput(Viewport, Size, Owner, Others, Hard, -5.0f).HardPadPx, 0.0f);

  // Three stacked figures (the Marmoreal left-edge column Harpies / Medusa / Harpies at K1): placed far to near like
  // the game mode, every board-plate tag keeps >= 3 px to every other one.
  const TArray<FS08ScreenRect> Figures = {FS08ScreenRect(480.0f, 300.0f, 530.0f, 350.0f),
                                          FS08ScreenRect(482.0f, 355.0f, 532.0f, 410.0f),
                                          FS08ScreenRect(478.0f, 415.0f, 528.0f, 465.0f)};
  TArray<FS08ScreenRect> Tags;
  for (int32 I = 0; I < Figures.Num(); ++I) {
    TArray<FS08ScreenRect> Rest;
    for (int32 J = 0; J < Figures.Num(); ++J) {
      if (J != I) Rest.Add(Figures[J]);
    }
    const FLabelPlacementResult R = ChooseLabelRect(
        MakeTagPlacementInput(Viewport, FVector2D(52.0, 16.0), Figures[I], Rest, Tags, S08ArtHudBoardPlate::TagHardPadPx));
    TestTrue(FString::Printf(TEXT("stacked tag %d placed (%s, %s)"), I, *R.Candidate, *FormatRect(R.Rect)),
             !R.Rect.IsEmpty() && R.bHardClean);
    for (const FS08ScreenRect& Other : Tags) {
      TestTrue(FString::Printf(TEXT("stacked tag %d: gap %.1f >= 3 px to %s"), I, RectGap(R.Rect, Other), *FormatRect(Other)),
               RectGap(R.Rect, Other) >= S08ArtHudBoardPlate::TagHardPadPx - 1e-3);
    }
    Tags.Add(R.Rect);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ReadabilityTagPlateTest,
    "Unmatched.S08.Readability.TagPlate board plate: semi-opaque rounded fill + 1 su team outline; off = the flat grid tag",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ReadabilityTagPlateTest::RunTest(const FString&) {
  const FS08ArtHudTagStyle Style;
  const FS08ArtHudPlateStyle Plate;
  // tokens: dark, semi-opaque (not fully opaque, not see-through), 1 su outline, rounded
  TestTrue(FString::Printf(TEXT("plate alpha %d in 160..240"), Style.BoardPlateBackground.A),
           Style.BoardPlateBackground.A >= 160 && Style.BoardPlateBackground.A <= 240);
  TestTrue("plate dark", Style.BoardPlateBackground.R + Style.BoardPlateBackground.G + Style.BoardPlateBackground.B < 120);
  TestEqual("outline 1 su", Style.BoardPlateOutlineSu, 1.0f);
  TestTrue("rounded corners", Style.BoardPlateCornerSu >= 2.0f);
  for (const uint8 Slot : {static_cast<uint8>(0), static_cast<uint8>(1)}) {
    const FSlateBrush Brush = US08ArtTagWidget::MakeBoardPlateBrush(Style, Slot);
    const FColor Accent = Slot ? Plate.TeamChipP2 : Plate.TeamChipP1;
    TestTrue(FString::Printf(TEXT("slot %d: rounded box"), Slot), Brush.DrawAs == ESlateBrushDrawType::RoundedBox);
    TestTrue(FString::Printf(TEXT("slot %d: fill = the plate colour with its alpha"), Slot),
             Brush.TintColor.GetSpecifiedColor().Equals(Style.BoardPlateFill(), 1e-5f));
    TestTrue(FString::Printf(TEXT("slot %d: outline = the team chip colour (accent)"), Slot),
             Brush.OutlineSettings.Color.GetSpecifiedColor().Equals(Style.BoardPlateOutline(Accent), 1e-5f) &&
                 FMath::IsNearlyEqual(Brush.OutlineSettings.Width, Style.BoardPlateOutlineSu));
  }
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08ReadabilityTagPlate")));
  if (!TestNotNull("test world", World)) return false;
  GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
  US08ArtTagWidget* Tag = CreateWidget<US08ArtTagWidget>(World, US08ArtTagWidget::StaticClass());
  if (TestNotNull("tag created", Tag) && TestNotNull("tag background", Tag->TagBackground.Get())) {
    Tag->TakeWidget();
    FS08TagTexts T;
    T.Name = FText::FromString(TEXT("Medusa"));
    T.Hp = S08ArtHudText::HpLabel(16, 16);
    T.HpFraction = 1.0f;
    T.TeamSlot = 0;
    T.Mode = ES08TagMode::Compact;
    Tag->ApplyModel(T);
    // a grid tag (never switched): the flat opaque background, untouched
    TestFalse("grid tag: no board plate", Tag->IsBoardPlate());
    TestTrue("grid tag: not a rounded box", Tag->TagBackground->Background.DrawAs != ESlateBrushDrawType::RoundedBox);
    TestTrue("grid tag: opaque background colour",
             Tag->TagBackground->GetBrushColor().Equals(FS08ArtHudPlateStyle::Linear(Tag->Style.Background), 1e-5f));
    Tag->SetBoardPlate(true);
    TestTrue("board plate on", Tag->IsBoardPlate());
    TestTrue("board plate: rounded box", Tag->TagBackground->Background.DrawAs == ESlateBrushDrawType::RoundedBox);
    TestTrue("board plate: border tint white (the brush carries the colours)",
             Tag->TagBackground->GetBrushColor() == FLinearColor::White);
    TestTrue("board plate: P1 outline",
             Tag->TagBackground->Background.OutlineSettings.Color.GetSpecifiedColor().Equals(
                 Tag->Style.BoardPlateOutline(Plate.TeamChipP1), 1e-5f));
    // the team slot follows the model (outline colour = the new team)
    T.TeamSlot = 1;
    Tag->ApplyModel(T);
    TestTrue("board plate: P2 outline after a model change",
             Tag->TagBackground->Background.OutlineSettings.Color.GetSpecifiedColor().Equals(
                 Tag->Style.BoardPlateOutline(Plate.TeamChipP2), 1e-5f));
    Tag->SetBoardPlate(false);
    TestFalse("board plate off", Tag->IsBoardPlate());
    TestTrue("off: back to the flat background", Tag->TagBackground->Background.DrawAs != ESlateBrushDrawType::RoundedBox &&
                                                     Tag->TagBackground->GetBrushColor().Equals(
                                                         FS08ArtHudPlateStyle::Linear(Tag->Style.Background), 1e-5f));
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
