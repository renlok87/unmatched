// VS-6 F2: the world-free numbers of FX-21..FX-25 (S08CombatFx.h) and the FighterHealed cue of FS08FlowController.
//   Unmatched.S08.CombatFx.Star     - ВР-FX04 contact point, the quad side (star 0.8 H), the camera quad faces the camera
//   Unmatched.S08.CombatFx.Number   - FX-22 keyframes: 0.8 -> 1 in 80 ms, 24 su rise, last 150 ms fade, reduced 450
//   Unmatched.S08.CombatFx.Heal     - FX-25 (ВР-FX13): HealAmount + ComputeCues FighterHealed (no revive, after damage)
//   Unmatched.S08.CombatFx.Hold     - the capture hook: a held channel keeps its value and resumes where it stopped
#include "S08CombatFx.h"
#include "S08FigureFxChannels.h"
#include "../S08FlowController.h"

#if WITH_AUTOMATION_TESTS

#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CombatFxStarTest, "Unmatched.S08.CombatFx.Star",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CombatFxStarTest::RunTest(const FString&) {
  using namespace S08CombatFx;
  const FVector Base(100.0f, 200.0f, 10.0f);
  const FVector Attacker(100.0f, 300.0f, 10.0f);
  const FVector P = StarPoint(Base, 100.0f, 20.0f, &Attacker);
  TestTrue("0.6 of the height", FMath::IsNearlyEqual(P.Z, 70.0f, 0.01f));
  TestTrue("0.4 R towards the attacker", P.Equals(FVector(100.0f, 208.0f, 70.0f), 0.01f));
  const FVector P0 = StarPoint(Base, 100.0f, 20.0f, nullptr);
  TestTrue("no attacker: the centre", P0.Equals(FVector(100.0f, 200.0f, 70.0f), 0.01f));
  TestTrue("star diameter 0.8 H = 80 % of the quad side H", FMath::IsNearlyEqual(StarQuadSideUU(100.0f), 100.0f, 0.01f));
  TestTrue("quad side floor 20", FMath::IsNearlyEqual(StarQuadSideUU(5.0f), 20.0f, 0.01f));
  const FVector Cam(0.0f, -600.0f, 800.0f);
  const FTransform Q = CameraQuad(P, Cam, 100.0f);
  const FVector N = Q.GetRotation().GetUpVector();
  TestTrue("the plane's normal faces the camera", FVector::DotProduct(N, (Cam - P).GetSafeNormal()) > 0.999f);
  TestTrue("scale side / 100", FMath::IsNearlyEqual(Q.GetScale3D().X, 1.0f, 1e-4f));
  const FVector Up = CameraQuadUp(P, Cam);
  TestTrue("in-plane up is perpendicular to the view", FMath::Abs(FVector::DotProduct(Up, N)) < 1e-3f);
  TestTrue("in-plane up points up", Up.Z > 0.0f);
  // FX-24: the base 6 uu above the quad's bottom edge
  const float Side = HealQuadSideUU(100.0f);
  TestTrue("heal quad 0.8 H + 16", FMath::IsNearlyEqual(Side, 96.0f, 0.01f));
  const FVector C = HealQuadCentre(Base, Cam, Side);
  TestTrue("heal centre over the base", FMath::IsNearlyEqual(FVector::Dist(C, Base), 0.5f * Side - 6.0f, 0.01f));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CombatFxNumberTest, "Unmatched.S08.CombatFx.Number",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CombatFxNumberTest::RunTest(const FString&) {
  using namespace S08CombatFx;
  FNumberPose P = NumberPose(0.0, 900.0, false);
  TestTrue("0 ms: scale 0.8", FMath::IsNearlyEqual(P.Scale, 0.8f, 1e-4f));
  TestTrue("0 ms: opacity 1", FMath::IsNearlyEqual(P.Opacity, 1.0f, 1e-4f));
  TestTrue("0 ms: no rise", FMath::IsNearlyEqual(P.RiseSu, 0.0f, 1e-4f));
  P = NumberPose(80.0, 900.0, false);
  TestTrue("80 ms: scale 1", FMath::IsNearlyEqual(P.Scale, 1.0f, 1e-4f));
  P = NumberPose(750.0, 900.0, false);
  TestTrue("750 ms (= life - 150): opacity 1", FMath::IsNearlyEqual(P.Opacity, 1.0f, 1e-4f));
  P = NumberPose(825.0, 900.0, false);
  TestTrue("825 ms: half faded", FMath::IsNearlyEqual(P.Opacity, 0.5f, 1e-4f));
  TestTrue("825 ms: rise < 24 su and > 23", P.RiseSu < NumberRiseSu && P.RiseSu > 23.0f);
  TestTrue("at the life end: gone", NumberPose(900.0, 900.0, false).Opacity == 0.0f);
  // reduced motion (04 §3.5): no rise / scale, 450 ms, the last 100 ms opacity only
  P = NumberPose(200.0, 450.0, true);
  TestTrue("reduced: scale 1, no rise, opacity 1", P.Scale == 1.0f && P.RiseSu == 0.0f && P.Opacity == 1.0f);
  P = NumberPose(400.0, 450.0, true);
  TestTrue("reduced 400: opacity 0.5", FMath::IsNearlyEqual(P.Opacity, 0.5f, 1e-4f));
  TestEqual("heal life 700", NumberLifeMs(true, 900, false), 700);
  TestEqual("damage life = the given 900 x speed", NumberLifeMs(false, 1350, false), 1350);
  TestEqual("reduced life 450", NumberLifeMs(true, 900, true), 450);
  TestEqual("reduced damage life 450", NumberLifeMs(false, 900, true), 450);
  return true;
}

namespace {
TSharedPtr<FJsonValue> S08CombatFxJson(const TCHAR* Text) {
  TSharedPtr<FJsonValue> V;
  FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), V);
  return V;
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CombatFxHealTest, "Unmatched.S08.CombatFx.Heal",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CombatFxHealTest::RunTest(const FString&) {
  using namespace S08CombatFx;
  TestEqual("The Holy Grail 3 -> 8: +5", HealAmount(3, 8, true, true), 5);
  TestEqual("a revive is no heal", HealAmount(0, 3, false, true), 0);
  TestEqual("HP 0 before is no heal", HealAmount(0, 3, true, true), 0);
  TestEqual("a decrease is no heal", HealAmount(8, 3, true, true), 0);
  // ComputeCues: Arthur 3 -> 8 (heal), Medusa 5 -> 3 (damage), a harpy 0 -> 1 (defeated before: no heal)
  const TSharedPtr<FJsonValue> Old = S08CombatFxJson(
      TEXT("[{\"id\":\"arthur\",\"health\":3,\"position\":{\"x\":1,\"y\":1}},")
      TEXT("{\"id\":\"medusa\",\"health\":5,\"position\":{\"x\":2,\"y\":1}},")
      TEXT("{\"id\":\"harpy1\",\"health\":0,\"isDefeated\":true,\"position\":{\"x\":3,\"y\":1}}]"));
  const TSharedPtr<FJsonValue> New = S08CombatFxJson(
      TEXT("[{\"id\":\"arthur\",\"health\":8,\"position\":{\"x\":1,\"y\":1}},")
      TEXT("{\"id\":\"medusa\",\"health\":3,\"position\":{\"x\":2,\"y\":1}},")
      TEXT("{\"id\":\"harpy1\",\"health\":1,\"isDefeated\":false,\"position\":{\"x\":3,\"y\":1}}]"));
  FS08BoardModel Board;
  TArray<FS08Cue> Cues;
  FS08FlowController::ComputeCues(50, Old, New, Board, nullptr, Cues);
  TestEqual("two cues (the damage, then the heal)", Cues.Num(), 2);
  if (Cues.Num() == 2) {
    TestTrue("damage first", Cues[0].Type == ES08CueType::FighterDamaged && Cues[0].FighterId == TEXT("medusa"));
    TestTrue("heal after the damage", Cues[1].Type == ES08CueType::FighterHealed && Cues[1].FighterId == TEXT("arthur"));
    TestEqual("heal amount +5", Cues[1].Damage, 5);
    TestEqual("heal seq", Cues[1].SequenceNumber, 50);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08CombatFxHoldTest, "Unmatched.S08.CombatFx.Hold",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08CombatFxHoldTest::RunTest(const FString&) {
  // the world-free part: the hold is a clock freeze - Advance at the held moment gives the held values
  FS08FigureFxChannels Ch;
  const double C = 5.0;
  Ch.StartHit(C, true, false);
  Ch.Advance(C + 0.020);
  TestEqual("flash at C+20", Ch.GetFlash(), 1.0f);
  TestFalse("not held by default", Ch.IsHeld());
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
