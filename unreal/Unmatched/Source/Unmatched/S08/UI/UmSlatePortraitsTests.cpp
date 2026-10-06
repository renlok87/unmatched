// VS-3 (the VS-2 review remark, docs/game-design/evidence/VISUAL/VS-2/README.md «Ревью VS-2»): the portraits never vanish.
//   Unmatched.S08.Hud.Portrait.SlateFallback  UmSlatePortraits::Wanted (ВР-VS3-01: the art look and either the panels on
//                                             Slate or no UMG root) and Build (the Slate column of before on a canvas).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Portrait.SlateFallback" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../S08TurnPortraitWidget.h"
#include "UmSlatePortraits.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Widgets/Layout/SConstraintCanvas.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace UmSlatePortraitsTest {
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
}  // namespace UmSlatePortraitsTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmSlatePortraitsTest,
    "Unmatched.S08.Hud.Portrait.SlateFallback the Slate portrait column when the UMG root is not created",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmSlatePortraitsTest::RunTest(const FString&) {
  // ВР-VS3-01: the art look + (panels on Slate or no UMG root)
  TestTrue(TEXT("UMG root failed, no flag: the column"), UmSlatePortraits::Wanted(true, false, false));
  TestFalse(TEXT("UMG root up: the panels own the portraits"), UmSlatePortraits::Wanted(true, false, true));
  TestTrue(TEXT("-S08SlateHud=panels: the column"), UmSlatePortraits::Wanted(true, true, true));
  TestFalse(TEXT("grey board: none"), UmSlatePortraits::Wanted(false, false, false));
  UmSlatePortraitsTest::FWorld W(TEXT("UmSlatePortraits"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  TSharedRef<SConstraintCanvas> Canvas = SNew(SConstraintCanvas);
  UmSlatePortraits::FColumn Column;
  const FS08TurnHudLook Look = FS08TurnHudLook::FromCommandLine(TEXT(""));
  TestTrue(TEXT("the column is built"), UmSlatePortraits::Build(W.World, Canvas, Look, Column));
  TestTrue(TEXT("both portraits and the column"), Column.IsValid());
  TestEqual(TEXT("one slot on the canvas"), Canvas->GetChildren()->Num(), 1);
  if (Column.IsValid()) {
    TestTrue(TEXT("the opponent above is the opponent"), Column.Opponent->IsOpponent() && !Column.Own->IsOpponent());
    TestEqual(TEXT("collapsed until the match HUD shows them"), Column.Own->GetVisibility(), ESlateVisibility::Collapsed);
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
