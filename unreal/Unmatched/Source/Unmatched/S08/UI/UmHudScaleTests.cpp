// VS-1 HB-09 automation test of UI/UmHudScale.h (no world):
//   Hud.Scale.Curve  the project DPI curve ВР-62 (720 -> 0.75, 1080 -> 1.0, 1440 -> 1.333, 2160 -> 2.0) is what the
//                    engine applies (DefaultEngine.ini), the UI scale UI-ACC-001 is 75..150 % in steps of 5 and at least
//                    100 % under 1080, the canvas / class of the acceptance windows (1280x720 at 150 % -> 1138x640 su,
//                    class S), the -S08DpiLegacy rollback (engine curve / project curve: the old size) and the trace.
//   node tools/s08/run-ue-tests.cjs Unmatched.S08.Hud.Scale <log>
#if WITH_AUTOMATION_TESTS

#include "UmHudScale.h"
#include "../S08ArtLook.h"
#include "../S08UserSettings.h"
#include "Engine/UserInterfaceSettings.h"
#include "Misc/AutomationTest.h"
#include "UObject/Package.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmHudScaleCurveTest, "Unmatched.S08.Hud.Scale.Curve",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmHudScaleCurveTest::RunTest(const FString&) {
  // 1) the curve ВР-62 and the engine curve it replaces
  TestEqual("project 720 -> 0.75", UmHudScale::ProjectDpi(720), 0.75f);
  TestEqual("project 1080 -> 1.0", UmHudScale::ProjectDpi(1080), 1.0f);
  TestEqual("project 1440 -> 1.333", UmHudScale::ProjectDpi(1440), 1.333f);
  TestEqual("project 2160 -> 2.0", UmHudScale::ProjectDpi(2160), 2.0f);
  TestEqual("project 900 -> 0.875 (linear)", UmHudScale::ProjectDpi(900), 0.875f);
  TestEqual("project below 720 stays 0.75", UmHudScale::ProjectDpi(600), 0.75f);
  TestEqual("engine 720 -> 0.666", UmHudScale::EngineDpi(720), 0.666f);
  TestEqual("engine 1080 -> 1.0", UmHudScale::EngineDpi(1080), 1.0f);
  // 2) DefaultEngine.ini carries that curve: the engine evaluates the same values (UIScaleRule ShortestSide)
  for (const FIntPoint Window : {FIntPoint(1280, 720), FIntPoint(1920, 1080), FIntPoint(2560, 1440), FIntPoint(3840, 2160),
                                 FIntPoint(720, 1280)}) {
    const int32 Short = FMath::Min(Window.X, Window.Y);
    TestTrue(FString::Printf(TEXT("engine curve at %dx%d = project %.3f (got %.4f)"), Window.X, Window.Y,
                             UmHudScale::ProjectDpi(Short), UmHudScale::CurveDpi(Window)),
             FMath::IsNearlyEqual(UmHudScale::CurveDpi(Window), UmHudScale::ProjectDpi(Short), 1.0e-3f));
  }
  TestEqual("UIScaleRule ShortestSide", static_cast<int32>(GetDefault<UUserInterfaceSettings>()->UIScaleRule),
            static_cast<int32>(EUIScalingRule::ShortestSide));
  // 3) UI-ACC-001: 75..150 % in steps of 5; under 1080 at least 100 % (ВР-62)
  TestEqual("clamp 60 -> 75", US08UserSettings::ClampUiScalePercent(60), 75);
  TestEqual("clamp 170 -> 150", US08UserSettings::ClampUiScalePercent(170), 150);
  TestEqual("step 102 -> 100", US08UserSettings::ClampUiScalePercent(102), 100);
  TestEqual("step 103 -> 105", US08UserSettings::ClampUiScalePercent(103), 105);
  TestEqual("720p: 75 % reads 100 %", UmHudScale::EffectivePercent(75, 720), 100);
  TestEqual("720p: 150 % stays", UmHudScale::EffectivePercent(150, 720), 150);
  TestEqual("1080p: 75 % stays", UmHudScale::EffectivePercent(75, 1080), 75);
  US08UserSettings* Temp = NewObject<US08UserSettings>(GetTransientPackage());
  FString Error;
  TestEqual("default 100 %", Temp->UiScalePercent, 100);
  TestTrue("uiScale=150", Temp->ApplySetting(TEXT("uiScale"), TEXT("150"), Error) && Temp->UiScalePercent == 150);
  TestFalse("uiScale=152 refused (step 5)", Temp->ApplySetting(TEXT("uiScale"), TEXT("152"), Error));
  TestFalse("uiScale=70 refused", Temp->ApplySetting(TEXT("uiScale"), TEXT("70"), Error));
  TestFalse("uiScale=1.5 refused", Temp->ApplySetting(TEXT("uiScale"), TEXT("1.5"), Error));
  TestEqual("a refused value changes nothing", Temp->UiScalePercent, 150);
  TestEqual("DescribeUi", Temp->DescribeUi(), FString(TEXT("uiScale=150")));
  Temp->SetToDefaults();
  TestEqual("SetToDefaults -> 100 %", Temp->UiScalePercent, 100);
  Temp->MarkAsGarbage();
  // 4) the acceptance windows (04 §3.6, §7.2): canvas = window / (DPI x UI scale), class L >= 1500 su (ВР-H01)
  struct FCase {
    FIntPoint Window;
    int32 Percent;
    float App;
    FIntPoint Canvas;
    bool bClassS;
  };
  const FCase Cases[] = {
      {{1920, 1080}, 75, 0.75f, {2560, 1440}, false},
      {{1920, 1080}, 100, 1.0f, {1920, 1080}, false},
      {{1920, 1080}, 150, 1.5f, {1280, 720}, true},
      {{1280, 720}, 100, 1.0f, {1707, 960}, false},
      {{1280, 720}, 150, 1.5f, {1138, 640}, true},
      {{1280, 720}, 75, 1.0f, {1707, 960}, false},  // the slider floor at 720p is 100 %
  };
  for (const FCase& C : Cases) {
    const FUmHudScaleState S =
        UmHudScale::Compute(C.Window, UmHudScale::ProjectDpi(FMath::Min(C.Window.X, C.Window.Y)), C.Percent, false);
    const FString P = FString::Printf(TEXT("%dx%d %d %%: "), C.Window.X, C.Window.Y, C.Percent);
    TestTrue(P + TEXT("app"), FMath::IsNearlyEqual(S.AppScale, C.App, 1.0e-4f));
    TestEqual(P + TEXT("canvas"), S.CanvasSu, C.Canvas);
    TestEqual(P + TEXT("class S"), S.bClassS, C.bClassS);
  }
  // type.caption 14 su at 720p 100 % is 10.5 px (ВР-62); the icon 24 su is 18 px
  {
    const FUmHudScaleState S = UmHudScale::Compute({1280, 720}, UmHudScale::ProjectDpi(720), 100, false);
    TestTrue("caption 14 su = 10.5 px at 720p", FMath::IsNearlyEqual(14.0f * S.PxPerSu(), 10.5f, 1.0e-4f));
    TestTrue("icon 24 su = 18 px at 720p", FMath::IsNearlyEqual(24.0f * S.PxPerSu(), 18.0f, 1.0e-4f));
    TestEqual("trace", UmHudScale::TraceLine(S),
              FString(TEXT("HUD-SCALE dpi=0.750 app=1.000 canvas=1707x960 window=1280x720 ui=100 uiSet=100 class=L "
                           "legacy=0")));
  }
  {
    const FUmHudScaleState S = UmHudScale::Compute({1280, 720}, UmHudScale::ProjectDpi(720), 150, false);
    TestEqual("trace 720p 150 %", UmHudScale::TraceLine(S),
              FString(TEXT("HUD-SCALE dpi=0.750 app=1.500 canvas=1138x640 window=1280x720 ui=150 uiSet=150 class=S "
                           "legacy=0")));
  }
  // 5) -S08DpiLegacy: the application scale carries engine / project, the total is the engine curve (the old size)
  {
    const FUmHudScaleState S = UmHudScale::Compute({1280, 720}, UmHudScale::ProjectDpi(720), 100, true);
    TestTrue("legacy 720p app = 0.666 / 0.75", FMath::IsNearlyEqual(S.AppScale, 0.666f / 0.75f, 1.0e-4f));
    TestTrue("legacy 720p px per su = 0.666", FMath::IsNearlyEqual(S.PxPerSu(), 0.666f, 1.0e-4f));
    TestEqual("legacy 720p canvas (the pre-HB-09 size)", S.CanvasSu, FIntPoint(1922, 1081));
    TestTrue("legacy traced", UmHudScale::TraceLine(S).EndsWith(TEXT(" legacy=1")));
    const FUmHudScaleState Hd = UmHudScale::Compute({1920, 1080}, UmHudScale::ProjectDpi(1080), 150, true);
    TestTrue("legacy 1080p: the curves agree, UI scale stays", FMath::IsNearlyEqual(Hd.AppScale, 1.5f, 1.0e-4f));
  }
  TestTrue("flag -S08DpiLegacy", UmHudScale::LegacyRequested(TEXT("-game -S08DpiLegacy -log")));
  TestFalse("no flag", UmHudScale::LegacyRequested(TEXT("-game -log")));
  TestEqual("ARTLOOK field default", UmHudScale::ArtLookField(TEXT("")), FString(TEXT("dpi=project")));
  TestEqual("ARTLOOK field rollback", UmHudScale::ArtLookField(TEXT("-S08DpiLegacy")),
            FString(TEXT("dpi=legacy(-S08DpiLegacy)")));
  TestTrue("ARTLOOK carries the dpi field", S08ArtLook::TraceLine().Contains(TEXT(" dpi=")));
  // 6) the editor process never applies a scale (the CDO stays untouched by the rule)
  UmHudScale::Refresh();
  TestEqual("editor: Refresh applies nothing", UmHudScale::Current().Window, FIntPoint::ZeroValue);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
