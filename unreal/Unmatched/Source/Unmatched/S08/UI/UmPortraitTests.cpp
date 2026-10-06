// VS-2 CP-08 tests (docs/game-design/visual/06-tasks/cards-portraits.csv CP-08):
//   Unmatched.S08.Hud.Portrait.Tree      US08TurnPortraitWidget: BuildDefaultTree, every BindWidget (code tree and
//                                        WBP_UmPortrait), nothing takes the mouse.
//   Unmatched.S08.Hud.Portrait.Fallback  the registry PNG in the circle (M_UmPortraitDisc MID, UV rect of the disc, no team
//                                        colour); no key / no PNG -> the monogram on a card.navy disc; a harpy -> its
//                                        number, never "H"; -S08PortraitLegacy -> the team disc + monogram; fallen / loser.
//   Unmatched.S08.Hud.Portrait.Cap       ВР-CP04: px shown <= 1.6 x the source circle - 1440p at 150 % (2 px per su) and
//                                        4K at 200 %; the PORTRAIT trace (scale <= 1.6).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Hud.Portrait" <abs log>
#if WITH_AUTOMATION_TESTS

#include "UmCardMedia.h"
#include "UmHudTheme.h"
#include "UmPortrait.h"
#include "../S08TurnPortraitWidget.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"

namespace UmPortraitTest {
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

float Scalar(UMaterialInstanceDynamic* Mid, const TCHAR* Name) {
  float V = -1.0f;
  if (Mid) Mid->GetScalarParameterValue(FMaterialParameterInfo(FName(Name)), V);
  return V;
}

bool Visible(const UWidget* W) { return W && W->GetVisibility() != ESlateVisibility::Collapsed; }
}  // namespace UmPortraitTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPortraitTreeTest, "Unmatched.S08.Hud.Portrait.Tree",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPortraitTreeTest::RunTest(const FString&) {
  using namespace UmPortraitTest;
  FWorld W(TEXT("UmPortraitTree"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  US08TurnPortraitWidget* Code = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  if (!TestNotNull(TEXT("portrait"), Code)) return false;
  FString Missing;
  TestTrue(TEXT("code default tree"), Code->UsesCodeDefaultTree());
  TestTrue(FString::Printf(TEXT("every part bound (missing %s)"), *Missing), Code->HasAllParts(&Missing));
  TestTrue(TEXT("the panel never takes a click"), Code->Panel && Code->Panel->GetVisibility() == ESlateVisibility::HitTestInvisible);
  TestNotNull(TEXT("heart icon added in code"), Code->GetHeartIcon());
  const FString Package(UmPortrait::WidgetBlueprintPath);
  if (FPackageName::DoesPackageExist(Package)) {
    FString Source;
    US08TurnPortraitWidget* FromWbp = US08TurnPortraitWidget::Create(W.World, &Source);
    TestEqual(TEXT("Create takes WBP_UmPortrait"), Source, Package);
    TestTrue(TEXT("WBP_UmPortrait: every part"), FromWbp && FromWbp->HasAllParts(&Missing));
    TestTrue(TEXT("WBP_UmPortrait: heart icon added in code"), FromWbp && FromWbp->GetHeartIcon() != nullptr);
  } else {
    AddError(TEXT("WBP_UmPortrait missing - run tools/s08/hud_contract/ue_author_um_hud.py"));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPortraitFallbackTest, "Unmatched.S08.Hud.Portrait.Fallback",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPortraitFallbackTest::RunTest(const FString&) {
  using namespace UmPortraitTest;
  // the keys of the registry (CP-02) and the slug of a server name
  TestEqual(TEXT("slug of King Arthur"), UmPortrait::SlugOf(TEXT("King Arthur")), FString(TEXT("king-arthur")));
  TestNotNull(TEXT("registry: king-arthur"), UmPortrait::Find(TEXT("king-arthur")));
  TestNotNull(TEXT("registry: medusa"), UmPortrait::Find(TEXT("medusa")));
  TestNotNull(TEXT("registry: king-arthur/merlin"), UmPortrait::Find(TEXT("king-arthur/merlin")));
  TestNotNull(TEXT("registry: medusa/harpies"), UmPortrait::Find(TEXT("medusa/harpies")));
  TestNull(TEXT("registry: no such hero"), UmPortrait::Find(TEXT("nobody")));
  // ВР-CP09: a harpy is its number, never the "H" of the monogram
  for (int32 N = 1; N <= 3; ++N) {
    TestEqual(*FString::Printf(TEXT("harpy %d fallback"), N), UmPortrait::FallbackText(TEXT("medusa/harpies"), TEXT("Harpies"), N),
              FString::FromInt(N));
  }
  TestEqual(TEXT("hero fallback = monogram"), UmPortrait::FallbackText(TEXT("king-arthur"), TEXT("King Arthur")), FString(TEXT("KA")));
  if (const FUmCardMediaEntry* Ka = UmPortrait::Find(TEXT("king-arthur"))) {
    // disc (0.49, 0.43, 0.60) of 800 px in a 1024 pad: uv 0.78125
    const FVector4 R = UmPortrait::UvRect(*Ka);
    TestTrue(FString::Printf(TEXT("king-arthur UV rect (%.4f, %.4f, %.4f, %.4f)"), R.X, R.Y, R.Z, R.W),
             FMath::IsNearlyEqual(R.X, 0.19 * 0.78125, 1e-4) && FMath::IsNearlyEqual(R.Y, 0.13 * 0.78125, 1e-4) &&
                 FMath::IsNearlyEqual(R.Z, 0.79 * 0.78125, 1e-4) && FMath::IsNearlyEqual(R.W, 0.73 * 0.78125, 1e-4));
    TestEqual(TEXT("king-arthur source circle 480 px"), UmPortrait::SourceCirclePx(*Ka), 480.0f);
  }

  FWorld W(TEXT("UmPortraitFallback"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  const UUmHudTheme& Theme = UUmHudTheme::Get();
  US08TurnPortraitWidget* P = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  if (!TestNotNull(TEXT("portrait"), P)) return false;
  P->SetPortraitLegacyForTest(0);
  P->Setup(false, FS08TurnHudLook(), FLinearColor::Red);
  // the name picks the portrait while no key was given (gallery / bench); the avatar in the circle
  P->SetHeroName(TEXT("King Arthur"));
  TestEqual(TEXT("key from the name"), P->GetPortraitKey(), FName(TEXT("king-arthur")));
  TestTrue(TEXT("king-arthur avatar shown"), P->IsAvatarShown());
  TestTrue(TEXT("avatar image visible"), Visible(P->AvatarImage));
  TestFalse(TEXT("team disc hidden under the avatar"), Visible(P->Disc));
  TestFalse(TEXT("no monogram over the avatar"), Visible(P->MonogramText));
  TestTrue(TEXT("T_Portrait_king_arthur"), P->GetAvatarTexture() && P->GetAvatarTexture()->GetName() == TEXT("T_Portrait_king_arthur"));
  UMaterialInstanceDynamic* Mid = P->GetAvatarMaterial();
  TestTrue(TEXT("MID of M_UmPortraitDisc"), Mid && Mid->Parent && Mid->Parent->GetName() == TEXT("M_UmPortraitDisc"));
  TestEqual(TEXT("desaturation 0"), Scalar(Mid, UmPortrait::ParamDesaturation), 0.0f);
  TestEqual(TEXT("opacity 1"), Scalar(Mid, UmPortrait::ParamOpacity), 1.0f);
  TestTrue(TEXT("rim: keyline fraction 1 / 42"), FMath::IsNearlyEqual(Scalar(Mid, UmPortrait::ParamKeylineFrac), 1.0f / 42.0f, 1e-4f));
  // fallen / loser (04 §1.10, §2.2)
  P->SetPortraitState(EUmPortraitState::Fallen, false);
  TestEqual(TEXT("fallen: saturation 0"), Scalar(Mid, UmPortrait::ParamDesaturation), 1.0f);
  TestEqual(TEXT("fallen: opacity 1"), Scalar(Mid, UmPortrait::ParamOpacity), 1.0f);
  P->SetPortraitState(EUmPortraitState::Loser, false);
  TestEqual(TEXT("loser: opacity 0.6"), Scalar(Mid, UmPortrait::ParamOpacity), UmPortrait::LoserOpacity);
  P->SetPortraitState(EUmPortraitState::Avatar, false);
  // an explicit key the registry lacks: the monogram on card.navy, text.primary
  P->SetPortrait(TEXT("nobody"));
  TestFalse(TEXT("no PNG: no avatar"), P->IsAvatarShown());
  TestTrue(TEXT("no PNG: disc visible"), Visible(P->Disc));
  TestTrue(TEXT("no PNG: monogram visible"), Visible(P->MonogramText));
  TestEqual(TEXT("no PNG: monogram KA"), P->MonogramText ? P->MonogramText->GetText().ToString() : FString(), FString(TEXT("KA")));
  TestTrue(TEXT("no PNG: disc card.navy, not the team colour"),
           P->Disc && P->Disc->GetColorAndOpacity().Equals(Theme.Color(TEXT("card.navy")), 1e-3f));
  TestTrue(TEXT("no PNG: monogram text.primary"),
           P->MonogramText && P->MonogramText->GetColorAndOpacity().GetSpecifiedColor().Equals(Theme.Color(TEXT("text.primary")), 1e-3f));
  TestTrue(TEXT("trace tex=monogram"), P->PortraitShotLine().Contains(TEXT("tex=monogram")));
  // a harpy without its PNG: the digit
  P->SetHeroName(TEXT("Harpies"));
  P->SetPortrait(TEXT("medusa/harpies"), 2);
  TestTrue(TEXT("harpies avatar shown"), P->IsAvatarShown());
  TestEqual(TEXT("harpy fallback text is its number"), P->GetMonogram(), FString(TEXT("2")));
  // the rollback: the team disc + monogram as before
  US08TurnPortraitWidget* L = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  if (!TestNotNull(TEXT("legacy portrait"), L)) return false;
  L->SetPortraitLegacyForTest(1);
  L->Setup(true, FS08TurnHudLook(), FLinearColor::Green);
  L->SetHeroName(TEXT("Medusa"));
  L->SetPortrait(TEXT("medusa"));
  TestFalse(TEXT("legacy: no avatar"), L->IsAvatarShown());
  TestTrue(TEXT("legacy: team disc"), L->Disc && L->Disc->GetColorAndOpacity().Equals(FLinearColor::Green, 1e-3f));
  TestEqual(TEXT("legacy: monogram M"), L->MonogramText ? L->MonogramText->GetText().ToString() : FString(), FString(TEXT("M")));
  TestTrue(TEXT("legacy trace"), L->PortraitShotLine().Contains(TEXT("tex=legacy")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FUmPortraitCapTest, "Unmatched.S08.Hud.Portrait.Cap",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FUmPortraitCapTest::RunTest(const FString&) {
  using namespace UmPortraitTest;
  // ВР-CP04 at 1440p 150 % (DPI 1.333 x 1.5 = 2 px per su): Merlin's circle is 0.75 x 128 = 96 px
  TestEqual(TEXT("panel 42 su of Merlin at 2 px/su: no cap"), UmPortrait::CappedSu(42.0f, 96.0f, 2.0f), 42.0f);
  TestTrue(TEXT("loading 160 su of Merlin at 2 px/su: 1.6 x 96 / 2 = 76.8 su"),
           FMath::IsNearlyEqual(UmPortrait::CappedSu(160.0f, 96.0f, 2.0f), 76.8f, 1e-3f));
  TestEqual(TEXT("loading 160 su of King Arthur (480 px): no cap"), UmPortrait::CappedSu(160.0f, 480.0f, 2.0f), 160.0f);
  FWorld W(TEXT("UmPortraitCap"));
  if (!TestNotNull(TEXT("test world"), W.World)) return false;
  US08TurnPortraitWidget* P = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  if (!TestNotNull(TEXT("portrait"), P)) return false;
  P->SetPortraitLegacyForTest(0);
  P->SetPxPerSuForTest(2.0f);
  P->SetHeroName(TEXT("Merlin"));
  P->SetPortrait(TEXT("king-arthur/merlin"));
  TestTrue(TEXT("merlin avatar"), P->IsAvatarShown());
  TestEqual(TEXT("1440p 150 %: 42 su"), P->GetCircleSu(), 42.0f);
  const FString Line = P->PortraitShotLine();
  TestTrue(FString::Printf(TEXT("trace scale 0.875 (%s)"), *Line), Line.Contains(TEXT("scale=0.875")));
  // 4K at 200 % (4 px per su): 1.6 x 96 / 4 = 38.4 su, the rest is padding
  US08TurnPortraitWidget* Q = CreateWidget<US08TurnPortraitWidget>(W.World, US08TurnPortraitWidget::StaticClass());
  if (!TestNotNull(TEXT("portrait 4K"), Q)) return false;
  Q->SetPortraitLegacyForTest(0);
  Q->SetPxPerSuForTest(4.0f);
  Q->SetPortrait(TEXT("king-arthur/merlin"));
  TestTrue(FString::Printf(TEXT("4K 200 %%: capped to 38.4 su (got %.2f)"), Q->GetCircleSu()),
           FMath::IsNearlyEqual(Q->GetCircleSu(), 38.4f, 1e-3f));
  TestTrue(TEXT("4K trace scale 1.600"), Q->PortraitShotLine().Contains(TEXT("scale=1.600")));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
