// VS-3 SC-01 automation tests (docs/game-design/visual/06-tasks/screens.csv SC-01; 04-hud-spec.md §1, §3.5, §3.6, §4.5):
//   Unmatched.S08.Hud.Screens.Base.Tree   the base parts (Veil, Frame, Body) and the confirm dialog's (Title, Message,
//                                         Confirm, Cancel) from the code tree and from WBP_UmConfirmDialog; one primary.
//   Unmatched.S08.Hud.Screens.Base.Shot   the SHOT line of a shown modal (04 §4.5: id of the owner, state=confirm, the
//                                         frame bbox, the WBP source); the answers (Confirm, Cancel, Esc, a click on the
//                                         veil) once each; the timing (show 250, modal hide 120, reduced 100, a screen
//                                         goes at once); the Esc route (modal -> selection -> PAUSE); the shot file name.
//   Unmatched.S08.Hud.Screens.Base.Scale  -S08UiScale=150 at 1280x720: 1138x640 su, class S, «HUD-LAYOUT class=S
//                                         canvas=1138x640»; the margins 24 / 16 su; the dialog inside the safe margins
//                                         on every canvas of 04 §3.6.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Screens" <abs log>
#if WITH_AUTOMATION_TESTS

#include "Components/TextBlock.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Internationalization/Internationalization.h"
#include "Internationalization/Regex.h"
#include "Internationalization/TextLocalizationManager.h"
#include "Misc/AutomationTest.h"
#include "UmButton.h"
#include "UmConfirmDialog.h"
#include "UmGameHud.h"
#include "UmHudLayout.h"
#include "UmHudScale.h"
#include "UmScreenBase.h"
#include "UmText.h"

namespace UmScreensTest {
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

FString Field(const FString& Line, const TCHAR* Key) {
  FString V;
  FParse::Value(*Line, *(FString(Key) + TEXT("=")), V);
  return V;
}
}  // namespace UmScreensTest

using namespace UmScreensTest;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensBaseTreeTest, "Unmatched.S08.Hud.Screens.Base.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensBaseTreeTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmScreensTree"));
  if (!TestNotNull(TEXT("world"), W.World)) return false;
  UUmConfirmDialog* D = CreateWidget<UUmConfirmDialog>(W.World, UUmConfirmDialog::StaticClass());
  FString Missing;
  TestTrue(FString::Printf(TEXT("the code tree: base + dialog parts (%s)"), *Missing), D && D->UsesCodeDefaultTree() && D->HasAllParts(&Missing));
  TestTrue(TEXT("a modal"), D && D->IsModal());
  TestTrue(TEXT("abstract bases (no WBP of their own)"), UUmScreenBase::StaticClass()->HasAnyClassFlags(CLASS_Abstract) &&
                                                             UUmModalBase::StaticClass()->HasAnyClassFlags(CLASS_Abstract));
  if (D) {
    TestTrue(TEXT("one primary in the window: «Да» primary, «Отмена» normal"),
             D->Confirm->GetModel().Variant == EUmButtonVariant::Primary && D->Cancel->GetModel().Variant == EUmButtonVariant::Normal);
    TestEqual(TEXT("«ДА» (common.confirm.yes)"), D->Confirm->GetModel().Label.ToString(), FString(TEXT("Да")));
    TestEqual(TEXT("«ОТМЕНА» (common.confirm.cancel)"), D->Cancel->GetModel().Label.ToString(), FString(TEXT("Отмена")));
    TestTrue(TEXT("hidden until opened"), !D->IsShown() && D->GetVisibility() == ESlateVisibility::Collapsed);
  }
  UClass* Cls = UmGameHudSlots::WbpOrNative(UUmConfirmDialog::StaticClass(), UUmConfirmDialog::WidgetBlueprintPath);
  if (Cls != UUmConfirmDialog::StaticClass()) {
    UUmConfirmDialog* Wbp = CreateWidget<UUmConfirmDialog>(W.World, Cls);
    Missing.Reset();
    TestTrue(FString::Printf(TEXT("WBP_UmConfirmDialog: every part (%s)"), *Missing), Wbp && !Wbp->UsesCodeDefaultTree() && Wbp->HasAllParts(&Missing));
  } else {
    AddInfo(TEXT("WBP_UmConfirmDialog not generated yet (the code tree)"));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensBaseShotTest, "Unmatched.S08.Hud.Screens.Base.Shot",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensBaseShotTest::RunTest(const FString& Parameters) {
  FRu Ru;
  FWorld W(TEXT("UmScreensShot"));
  // the timing (04 §1, ВР-SC05)
  TestEqual(TEXT("show 250"), UmScreens::ShowLenMs(false), 250.0f);
  TestEqual(TEXT("show reduced 100"), UmScreens::ShowLenMs(true), 100.0f);
  TestEqual(TEXT("a modal goes in 120"), UmScreens::HideLenMs(true, false), 120.0f);
  TestEqual(TEXT("a modal goes reduced in 100"), UmScreens::HideLenMs(true, true), 100.0f);
  TestEqual(TEXT("a screen goes at once"), UmScreens::HideLenMs(false, false), 0.0f);
  TestEqual(TEXT("half of the show"), UmScreens::AlphaAt(true, 125.0f, 250.0f), 0.5f);
  // Esc (04 §1)
  TestEqual(TEXT("Esc: the modal first"), UmScreens::RouteEscape(1, true), UmScreens::EEscape::CloseModal);
  TestEqual(TEXT("Esc: then the selection"), UmScreens::RouteEscape(0, true), UmScreens::EEscape::ClearSelection);
  TestEqual(TEXT("Esc: then PAUSE"), UmScreens::RouteEscape(0, false), UmScreens::EEscape::OpenPause);
  TestEqual(TEXT("-S08ScreenShots file"), UmScreens::ShotFileName(TEXT("UI-SCR-PAUSE"), TEXT("confirm")), FString(TEXT("UI-SCR-PAUSE-confirm.png")));
  UUmConfirmDialog* D = CreateWidget<UUmConfirmDialog>(W.World, UmGameHudSlots::WbpOrNative(UUmConfirmDialog::StaticClass(), UUmConfirmDialog::WidgetBlueprintPath));
  if (!TestNotNull(TEXT("dialog"), D)) return false;
  D->SetCanvas(FVector2D(1920.0, 1080.0), false, 1.0f);
  D->SetClockOverrideMs(1000.0);
  D->SetReducedForTest(0);
  int32 Confirmed = 0, Cancelled = 0;
  UUmConfirmDialog::FRequest R;
  R.OwnerUiId = TEXT("UI-SCR-PAUSE");
  R.Title = UmText::Get(EUmTable::Screens, TEXT("screens.pause.leave"));
  R.Message = UmText::Get(EUmTable::Screens, TEXT("screens.pause.leave.confirm"));
  R.OnConfirm = [&Confirmed]() { ++Confirmed; };
  R.OnCancel = [&Cancelled]() { ++Cancelled; };
  D->Open(R);
  TestEqual(TEXT("t 0: transparent"), D->GetAlpha(), 0.0f);
  D->SetClockOverrideMs(1125.0);
  D->Step();
  TestTrue(TEXT("t 125: half"), FMath::IsNearlyEqual(D->GetAlpha(), 0.5f, 0.01f));
  D->SetClockOverrideMs(1250.0);
  D->Step();
  TestEqual(TEXT("t 250: shown"), D->GetAlpha(), 1.0f);
  TArray<FString> Lines;
  D->CollectShotLines(Lines);
  if (TestEqual(TEXT("one SHOT line"), Lines.Num(), 1)) {
    FRegexMatcher M(FRegexPattern(TEXT("^SHOT widget id=UI-SCR-PAUSE impl=umg state=confirm fighter=none bbox=\\((\\d+),(\\d+),(\\d+),(\\d+)\\) "
                                       "geom=painted visible=1 twin=0 source=\\S+ modal=1")),
                    Lines[0]);
    TestTrue(FString::Printf(TEXT("04 §4.5 line: %s"), *Lines[0]), M.FindNext());
    const FBox2D Frame = D->FrameRectSu();
    TestTrue(TEXT("the frame 640 x 360 centred at 1080p (640,360)"), FMath::IsNearlyEqual(Frame.Min.X, 640.0) && FMath::IsNearlyEqual(Frame.Min.Y, 360.0) &&
                                                                        FMath::IsNearlyEqual(Frame.GetSize().X, 640.0) && FMath::IsNearlyEqual(Frame.GetSize().Y, 360.0));
  }
  TestEqual(TEXT("the title from ST_Screens"), D->Title->GetText().ToString(), FString(TEXT("Покинуть партию")));
  // Esc = Cancel, once; the dialog goes in 120 ms
  TestTrue(TEXT("Esc answers"), D->HandleEscape());
  TestTrue(TEXT("Cancel once"), Cancelled == 1 && Confirmed == 0);
  D->Answer(true);
  TestEqual(TEXT("no second answer"), Confirmed, 0);
  D->SetClockOverrideMs(1250.0 + 60.0);
  D->Step();
  TestTrue(TEXT("t 60 of the hide: half"), FMath::IsNearlyEqual(D->GetAlpha(), 0.5f, 0.01f));
  D->SetClockOverrideMs(1250.0 + 121.0);
  D->Step();
  TestTrue(TEXT("t 120: gone (collapsed)"), D->GetAlpha() == 0.0f && D->GetVisibility() == ESlateVisibility::Collapsed);
  Lines.Reset();
  D->CollectShotLines(Lines);
  TestEqual(TEXT("no SHOT line once gone"), Lines.Num(), 0);
  // reopen and confirm
  D->SetClockOverrideMs(2000.0);
  D->Open(R);
  D->Answer(true);
  TestTrue(TEXT("Confirm once"), Confirmed == 1 && Cancelled == 1);
  // reduced motion: 100 ms
  D->SetReducedForTest(1);
  D->SetClockOverrideMs(3000.0);
  D->Open(R);
  D->SetClockOverrideMs(3050.0);
  D->Step();
  TestTrue(TEXT("reduced: half at 50 ms"), FMath::IsNearlyEqual(D->GetAlpha(), 0.5f, 0.01f));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmScreensBaseScaleTest, "Unmatched.S08.Hud.Screens.Base.Scale",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FUmScreensBaseScaleTest::RunTest(const FString& Parameters) {
  FWorld W(TEXT("UmScreensScale"));
  // -S08UiScale=150 at 1280x720: the project DPI curve 0.75 x 1.5 = 1.125 px per su -> 1138 x 640 su, class S
  const FUmHudScaleState S = UmHudScale::Compute(FIntPoint(1280, 720), UmHudScale::ProjectDpi(720), 150, false);
  TestTrue(FString::Printf(TEXT("1280x720 at 150 %%: canvas %dx%d class %s"), S.CanvasSu.X, S.CanvasSu.Y, S.bClassS ? TEXT("S") : TEXT("L")),
           S.CanvasSu == FIntPoint(1138, 640) && S.bClassS && FMath::IsNearlyEqual(S.PxPerSu(), 1.125f, 1.0e-3f));
  const FUmHudLayout L = FUmHudLayout::Compute(FVector2D(1280.0, 720.0) / S.PxPerSu(), S.PxPerSu(), nullptr);
  const FString Line = L.TraceLine(FIntPoint(1280, 720));
  TestTrue(FString::Printf(TEXT("HUD-LAYOUT class=S canvas=1138x640 (%s)"), *Line), Line.StartsWith(TEXT("HUD-LAYOUT class=S canvas=1138x640")));
  TestEqual(TEXT("margin L 24"), UmScreens::SafeMarginSu(false), 24.0f);
  TestEqual(TEXT("margin S 16"), UmScreens::SafeMarginSu(true), 16.0f);
  // the dialog inside the safe margins on every canvas of 04 §3.6
  UUmConfirmDialog* D = CreateWidget<UUmConfirmDialog>(W.World, UUmConfirmDialog::StaticClass());
  if (!TestNotNull(TEXT("dialog"), D)) return false;
  struct FCase {
    FIntPoint Window;
    int32 Percent;
  };
  for (const FCase& C : {FCase{{1920, 1080}, 75}, FCase{{1920, 1080}, 100}, FCase{{1920, 1080}, 150}, FCase{{1280, 720}, 100}, FCase{{1280, 720}, 150}}) {
    const FUmHudScaleState St = UmHudScale::Compute(C.Window, UmHudScale::ProjectDpi(FMath::Min(C.Window.X, C.Window.Y)), C.Percent, false);
    const FVector2D Canvas = FVector2D(C.Window) / St.PxPerSu();
    D->SetCanvas(Canvas, St.bClassS, St.PxPerSu());
    const FBox2D F = D->FrameRectSu();
    const float M = D->GetSafeMarginSu();
    TestTrue(FString::Printf(TEXT("%dx%d %d %%: the frame (%.0f,%.0f)-(%.0f,%.0f) inside the %.0f su margins"), C.Window.X, C.Window.Y, C.Percent,
                             F.Min.X, F.Min.Y, F.Max.X, F.Max.Y, M),
             F.Min.X >= M - 0.01 && F.Min.Y >= M - 0.01 && F.Max.X <= Canvas.X - M + 0.01 && F.Max.Y <= Canvas.Y - M + 0.01);
    TestEqual(FString::Printf(TEXT("%dx%d %d %%: the margin of the class"), C.Window.X, C.Window.Y, C.Percent), M, St.bClassS ? 16.0f : 24.0f);
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
