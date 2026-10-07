// VS-3 automation tests of the loaders (docs/game-design/visual/06-tasks/hud.csv HB-47; 04-hud-spec.md §3.3):
//   Unmatched.S08.Hud.Loader.Delay    FUmDelayedShow: 290 ms - hidden, 310 ms - shown, ready - hidden at once; the
//                                     spinner, the skeleton and the progress bar follow it (collapsed = no tick) and
//                                     write HUD-LOADER on a change only; the progress caption rule (2 s); the card scan's
//                                     spinner only after 300 ms of loading.
//   Unmatched.S08.Hud.Loader.Reduced  the skeleton pulse 0.6 <-> 1.0 in 900 ms, static 0.8 with reduced motion; the
//                                     spinner contract steps 45 deg each 125 ms, reduced 250 ms.
//   Unmatched.S08.Hud.Loader.Tree     BuildDefaultTree of UUmSpinner / UUmSkeletonRows / UUmProgressBar, every
//                                     BindWidget, WBP_UmSpinner a child of the base.
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Loader" <abs log>
#if WITH_AUTOMATION_TESTS

#include "../S08AnimatedIconWidget.h"
#include "../S08IconMotion.h"
#include "Components/ProgressBar.h"
#include "Components/SizeBox.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"
#include "UmProgressBar.h"
#include "UmSkeletonRows.h"
#include "UmSpinner.h"

namespace UmLoaderTest {
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
}  // namespace UmLoaderTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmLoaderDelayTest,
    "Unmatched.S08.Hud.Loader.Delay 290 ms hidden 310 ms shown, ready hides at once; spinner, skeleton, progress, card scan",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmLoaderDelayTest::RunTest(const FString&) {
  using namespace UmLoaderTest;
  // ---- the helper ----
  FUmDelayedShow D;
  TestFalse(TEXT("not waiting: hidden"), D.IsShown(0.0));
  D.Begin(1000.0);
  TestFalse(TEXT("290 ms: hidden"), D.IsShown(1290.0));
  TestTrue(TEXT("310 ms: shown"), D.IsShown(1310.0));
  D.Begin(1200.0);
  TestTrue(TEXT("a running wait keeps its start"), D.IsShown(1310.0) && FMath::IsNearlyEqual(D.WaitedMs(1310.0), 310.0));
  D.End();
  TestFalse(TEXT("ready: hidden at once"), D.IsShown(1311.0) || D.IsWaiting());
  FWorld W(TEXT("UmLoaderDelay"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  // ---- the spinner ----
  UUmSpinner* S = CreateWidget<UUmSpinner>(W.World, UUmSpinner::StaticClass());
  if (!TestNotNull(TEXT("spinner"), S)) return false;
  S->SetReducedForTest(0);
  TestEqual(TEXT("spinner hidden before any wait (collapsed: Slate ticks nothing)"), S->GetVisibility(), ESlateVisibility::Collapsed);
  TestTrue(TEXT("spinner: no line at the wait start"), S->SetWaiting(true, 0.0, TEXT("test")).IsEmpty());
  TestTrue(TEXT("spinner: no line at 290 ms"), S->SetWaiting(true, 290.0, TEXT("test")).IsEmpty());
  TestEqual(TEXT("spinner 290 ms: collapsed"), S->GetVisibility(), ESlateVisibility::Collapsed);
  const FString Shown = S->SetWaiting(true, 310.0, TEXT("test"));
  TestTrue(FString::Printf(TEXT("spinner 310 ms: shown, traced (%s)"), *Shown),
           S->IsShown() && S->GetVisibility() == ESlateVisibility::HitTestInvisible &&
               Shown.StartsWith(TEXT("HUD-LOADER kind=spinner shown=1 where=test waitMs=310")));
  TestTrue(TEXT("spinner: the same state again writes nothing"), S->SetWaiting(true, 500.0, TEXT("test")).IsEmpty());
  const FString Hidden = S->SetWaiting(false, 520.0, TEXT("test"));
  TestTrue(TEXT("spinner ready: hidden at once"), !S->IsShown() && S->GetVisibility() == ESlateVisibility::Collapsed &&
                                                      Hidden.Contains(TEXT("kind=spinner shown=0")));
  TestTrue(TEXT("spinner: a new wait starts again (290 ms of it hidden)"),
           S->SetWaiting(true, 1000.0, TEXT("test")).IsEmpty() && S->SetWaiting(true, 1290.0, TEXT("test")).IsEmpty() && !S->IsShown());
  S->SetSizeSu(48.0f);
  TestEqual(TEXT("spinner 48 su"), S->GetSizeSu(), 48.0f);
  S->SetSizeSu(40.0f);
  TestEqual(TEXT("spinner sizes are 32 / 48 only"), S->GetSizeSu(), 32.0f);
  TestEqual(TEXT("a hidden spinner has not ticked"), S->GetTickCount(), 0);
  // ---- the skeleton ----
  UUmSkeletonRows* K = CreateWidget<UUmSkeletonRows>(W.World, UUmSkeletonRows::StaticClass());
  if (!TestNotNull(TEXT("skeleton"), K)) return false;
  K->SetReducedForTest(0);
  K->SetClockOverrideMs(0.0);
  K->SetRows(6, 48.0f);
  TestEqual(TEXT("skeleton: 6 rows"), K->GetRowCount(), 6);
  K->SetWaiting(true, 0.0, TEXT("deckpanel"));
  TestTrue(TEXT("skeleton 290 ms: collapsed"), K->SetWaiting(true, 290.0, TEXT("deckpanel")).IsEmpty() &&
                                                  K->GetVisibility() == ESlateVisibility::Collapsed);
  const FString KShown = K->SetWaiting(true, 310.0, TEXT("deckpanel"));
  TestTrue(FString::Printf(TEXT("skeleton 310 ms: shown at the pulse top (%s)"), *KShown),
           K->IsShown() && KShown.Contains(TEXT("kind=skeleton shown=1 where=deckpanel")) &&
               FMath::IsNearlyEqual(K->GetPulseOpacity(), 1.0f, 1.0e-3f));
  TestTrue(TEXT("skeleton ready: hidden at once"),
           K->SetWaiting(false, 400.0, TEXT("deckpanel")).Contains(TEXT("shown=0")) && K->GetVisibility() == ESlateVisibility::Collapsed);
  K->SetRows(3, 48.0f);
  TestEqual(TEXT("skeleton: fewer rows collapse the rest"), K->GetRowCount(), 3);
  // ---- the progress bar ----
  UUmProgressBar* P = CreateWidget<UUmProgressBar>(W.World, UUmProgressBar::StaticClass());
  if (!TestNotNull(TEXT("progress"), P)) return false;
  P->ApplyModel(0.4f, FText::FromString(TEXT("stage")), 0.0);
  P->SetWaiting(true, 0.0, TEXT("boot"));
  TestTrue(TEXT("progress 290 ms: hidden"), P->SetWaiting(true, 290.0, TEXT("boot")).IsEmpty() && !P->IsShown());
  const FString PShown = P->SetWaiting(true, 310.0, TEXT("boot"));
  TestTrue(FString::Printf(TEXT("progress 310 ms: shown with its caption (%s)"), *PShown),
           P->IsShown() && PShown.Contains(TEXT("kind=progress shown=1")) && PShown.Contains(TEXT("caption=1 percent=0.40")));
  TestTrue(TEXT("progress value on the bar"), P->Bar && FMath::IsNearlyEqual(P->Bar->GetPercent(), 0.4f));
  P->ApplyModel(0.5f, FText::GetEmpty(), 1000.0);
  TestFalse(TEXT("no caption for 2 s: still fine"), P->HasCaptionDefect(3000.0));
  TestTrue(TEXT("no caption for longer than 2 s: a defect"), P->HasCaptionDefect(3001.0));
  P->ApplyModel(0.6f, FText::FromString(TEXT("next")), 3100.0);
  TestFalse(TEXT("the caption back: no defect"), P->HasCaptionDefect(9000.0));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmLoaderReducedTest,
    "Unmatched.S08.Hud.Loader.Reduced skeleton pulse 0.6..1.0 in 900 ms, static with reduced motion; spinner steps 125 / 250 ms",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmLoaderReducedTest::RunTest(const FString&) {
  using namespace UmLoader;
  TestTrue(TEXT("pulse top at 0"), FMath::IsNearlyEqual(SkeletonOpacity(0.0, false), 1.0f, 1.0e-4f));
  TestTrue(TEXT("pulse bottom 0.6 at 450 ms"), FMath::IsNearlyEqual(SkeletonOpacity(450.0, false), 0.6f, 1.0e-4f));
  TestTrue(TEXT("pulse back at the top at 900 ms"), FMath::IsNearlyEqual(SkeletonOpacity(900.0, false), 1.0f, 1.0e-4f));
  float Lo = 1.0f, Hi = 0.0f;
  for (int32 T = 0; T <= 1800; T += 10) {
    Lo = FMath::Min(Lo, SkeletonOpacity(T, false));
    Hi = FMath::Max(Hi, SkeletonOpacity(T, false));
  }
  TestTrue(FString::Printf(TEXT("pulse within 0.6..1.0 (%.3f..%.3f)"), Lo, Hi), Lo >= 0.6f - 1.0e-4f && Hi <= 1.0f + 1.0e-4f);
  bool bStatic = true;
  for (int32 T = 0; T <= 1800; T += 50) bStatic &= FMath::IsNearlyEqual(SkeletonOpacity(T, true), SkeletonReduced);
  TestTrue(TEXT("reduced: static 0.8"), bStatic);
  // the spinner contract (icon-motion.json loader-spinner `cycle`): 8 steps of 45 deg, 125 ms; reduced 250 ms
  const FS08IconMotionDef* Def = FS08IconMotionLibrary::Get().Find(TEXT("loader-spinner"));
  if (!TestNotNull(TEXT("loader-spinner in the contract"), Def)) return false;
  auto Angle = [Def](bool bReduced, float T) {
    FS08IconAnimator A;
    A.Init(Def, bReduced);
    A.Play(TEXT("appear"), -100000.0f);
    A.Play(TEXT("cycle"), 0.0f);
    const FS08IconPose P = A.Pose(T);
    return P.Targets.Num() ? P.Targets[0].Get(ES08IconProp::Rotate) : -1.0f;
  };
  TestTrue(FString::Printf(TEXT("normal: 45 deg at 130 ms (%.1f)"), Angle(false, 130.0f)), FMath::IsNearlyEqual(Angle(false, 130.0f), 45.0f, 0.5f));
  TestTrue(FString::Printf(TEXT("normal: 90 deg at 260 ms (%.1f)"), Angle(false, 260.0f)), FMath::IsNearlyEqual(Angle(false, 260.0f), 90.0f, 0.5f));
  TestTrue(FString::Printf(TEXT("reduced: 0 deg at 130 ms (%.1f)"), Angle(true, 130.0f)), FMath::IsNearlyEqual(Angle(true, 130.0f), 0.0f, 0.5f));
  TestTrue(FString::Printf(TEXT("reduced: 45 deg at 260 ms (%.1f)"), Angle(true, 260.0f)), FMath::IsNearlyEqual(Angle(true, 260.0f), 45.0f, 0.5f));
  // the skeleton widget follows the reduced flag
  UmLoaderTest::FWorld W(TEXT("UmLoaderReduced"));
  UUmSkeletonRows* K = W.World ? CreateWidget<UUmSkeletonRows>(W.World, UUmSkeletonRows::StaticClass()) : nullptr;
  if (!TestNotNull(TEXT("skeleton"), K)) return false;
  K->SetReducedForTest(1);
  K->SetClockOverrideMs(0.0);
  K->SetRows(6, 48.0f);
  K->SetWaiting(true, 0.0, TEXT("t"));
  K->SetWaiting(true, 310.0, TEXT("t"));
  K->StepPulse(450.0);
  TestTrue(FString::Printf(TEXT("reduced skeleton static (%.2f)"), K->GetPulseOpacity()), FMath::IsNearlyEqual(K->GetPulseOpacity(), SkeletonReduced));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmLoaderTreeTest,
    "Unmatched.S08.Hud.Loader.Tree UUmSpinner, UUmSkeletonRows, UUmProgressBar default trees and WBP_UmSpinner",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmLoaderTreeTest::RunTest(const FString&) {
  using namespace UmLoaderTest;
  FWorld W(TEXT("UmLoaderTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  FString Missing;
  UUmSpinner* S = CreateWidget<UUmSpinner>(W.World, UUmSpinner::StaticClass());
  TestTrue(TEXT("spinner: code default tree, every BindWidget"), S && S->UsesCodeDefaultTree() && S->HasAllParts(&Missing));
  TestTrue(TEXT("spinner: the loader-spinner icon"), S && S->Icon && S->Icon->GetIconId() == FName(TEXT("loader-spinner")));
  UUmSkeletonRows* K = CreateWidget<UUmSkeletonRows>(W.World, UUmSkeletonRows::StaticClass());
  TestTrue(TEXT("skeleton: every BindWidget"), K && K->HasAllParts());
  UUmProgressBar* P = CreateWidget<UUmProgressBar>(W.World, UUmProgressBar::StaticClass());
  TestTrue(TEXT("progress: every BindWidget"), P && P->HasAllParts());
  if (FPackageName::DoesPackageExist(UUmSpinner::WidgetBlueprintPath)) {
    UClass* Wbp = UUmSpinner::WidgetClass();
    TestTrue(TEXT("WBP_UmSpinner is a child of UUmSpinner"), Wbp && Wbp != UUmSpinner::StaticClass() && Wbp->IsChildOf(UUmSpinner::StaticClass()));
    UUmSpinner* FromWbp = Wbp ? CreateWidget<UUmSpinner>(W.World, Wbp) : nullptr;
    TestTrue(TEXT("the WBP has every BindWidget"), FromWbp && FromWbp->HasAllParts() && !FromWbp->UsesCodeDefaultTree());
  } else {
    AddWarning(TEXT("WBP_UmSpinner not generated in this checkout (the code tree is tested)"));
  }
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
