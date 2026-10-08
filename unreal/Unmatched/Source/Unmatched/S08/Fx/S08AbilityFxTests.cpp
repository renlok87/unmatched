// VS-6 F3 automation tests (FX-26 / FX-27 / FX-28 / FX-32): the AbilityTriggered rule of ComputeCues, the numbers of
// the death and ability FX and the hero socket of the CUE-014 show line.
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "../S08BoardModel.h"
#include "../S08CueDispatcher.h"
#include "../S08FlowController.h"
#include "S08AbilityCues.h"
#include "S08AbilityFx.h"

#if WITH_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

namespace {
TSharedPtr<FJsonValue> ParseValue(const FString& Text) {
  TSharedPtr<FJsonValue> Out;
  const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
  FJsonSerializer::Deserialize(Reader, Out);
  return Out;
}

FString Fighters(int32 MerlinHp, int32 HarpyHp) {
  return FString::Printf(
      TEXT("[{\"id\":\"f-0-hero\",\"ownerId\":\"p0\",\"name\":\"Medusa\",\"type\":\"HERO\",\"health\":16,\"maxHealth\":16,")
      TEXT("\"position\":{\"x\":1,\"y\":1}},")
      TEXT("{\"id\":\"f-0-sk0\",\"ownerId\":\"p0\",\"name\":\"Harpies\",\"type\":\"SIDEKICK\",\"health\":%d,\"maxHealth\":1,")
      TEXT("\"position\":{\"x\":2,\"y\":1}},")
      TEXT("{\"id\":\"f-1-sk0\",\"ownerId\":\"p1\",\"name\":\"Merlin\",\"type\":\"SIDEKICK\",\"health\":%d,\"maxHealth\":7,")
      TEXT("\"position\":{\"x\":1,\"y\":2}}]"),
      HarpyHp, MerlinHp);
}

const TCHAR* const GazePending =
    TEXT("{\"pendingEffects\":[{\"id\":\"ability-medusa-target-p0\",\"type\":\"TARGET_FIGHTER\",\"playerId\":\"p0\",")
    TEXT("\"targetFighterIds\":[\"f-1-sk0\"],\"damage\":1,\"optional\":true,")
    TEXT("\"text\":\"deal 1 damage to an opposing fighter in Medusa's zone\"}]}");
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08AbilityCuesTest,
    "Unmatched.S08.CueFx.AbilityCues Medusa's resolved pending gives CUE-014 before the damage; decline / open / none give no cue (FX-28)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08AbilityCuesTest::RunTest(const FString&) {
  const FS08BoardModel Board;
  const TSharedPtr<FJsonValue> Old = ParseValue(Fighters(6, 1));
  const TSharedPtr<FJsonValue> Hit = ParseValue(Fighters(5, 1));
  const TSharedPtr<FJsonValue> OldMeta = ParseValue(GazePending);
  const TSharedPtr<FJsonValue> Resolved = ParseValue(TEXT("{\"pendingEffects\":[]}"));
  TArray<FS08Cue> Cues;
  // resolved: the pending gone, Merlin lost 1 HP -> AbilityTriggered (Medusa -> Merlin) before the damage cue
  FS08FlowController::ComputeCues(12, Old, Hit, Board, Resolved, OldMeta, Cues);
  TestEqual("ability + damage cues", Cues.Num(), 2);
  if (Cues.Num() == 2) {
    TestTrue("the ability cue first", Cues[0].Type == ES08CueType::AbilityTriggered);
    TestEqual("subject = Medusa's fighter", Cues[0].FighterId, FString(TEXT("f-0-hero")));
    TestEqual("target", Cues[0].TargetId, FString(TEXT("f-1-sk0")));
    TestEqual("hero key", Cues[0].HeroKey, FString(TEXT("Medusa")));
    TestEqual("damage", Cues[0].Damage, 1);
    TestEqual("target HP before", Cues[0].TargetHpBefore, 6);
    TestEqual("target cell before", FIntPoint(Cues[0].FromX, Cues[0].FromY), FIntPoint(1, 2));
    TestEqual("seq", Cues[0].SequenceNumber, 12);
    TestTrue("then the damage", Cues[1].Type == ES08CueType::FighterDamaged && Cues[1].FighterId == TEXT("f-1-sk0"));
  }
  // the metadata of the resolving body omits pendingEffects: absent counts as resolved
  FS08FlowController::ComputeCues(12, Old, Hit, Board, ParseValue(TEXT("{}")), OldMeta, Cues);
  TestTrue("absent queue = resolved", Cues.Num() == 2 && Cues[0].Type == ES08CueType::AbilityTriggered);
  // declined: the pending gone, nobody lost HP -> no cue at all
  FS08FlowController::ComputeCues(12, Old, Old, Board, Resolved, OldMeta, Cues);
  TestEqual("decline gives no cue", Cues.Num(), 0);
  // still open (the damage came from elsewhere): no ability cue
  FS08FlowController::ComputeCues(12, Old, Hit, Board, OldMeta, OldMeta, Cues);
  TestTrue("open pending: damage only", Cues.Num() == 1 && Cues[0].Type == ES08CueType::FighterDamaged);
  // no pending at all (the card Gaze of Stone, a combat): damage only
  FS08FlowController::ComputeCues(12, Old, Hit, Board, Resolved, Resolved, Cues);
  TestTrue("no pending: damage only", Cues.Num() == 1 && Cues[0].Type == ES08CueType::FighterDamaged);
  // the legacy overload (no old metadata) never gives an ability cue
  FS08FlowController::ComputeCues(12, Old, Hit, Board, Resolved, Cues);
  TestTrue("legacy overload: damage only", Cues.Num() == 1 && Cues[0].Type == ES08CueType::FighterDamaged);
  // another hero's pending id is not Medusa's ability
  TestEqual("pending prefix", S08AbilityCues::HeroKeyOfPending(TEXT("ability-medusa-target-p3")), FString(TEXT("Medusa")));
  TestEqual("other id", S08AbilityCues::HeroKeyOfPending(TEXT("card-gaze-of-stone-p0")), FString());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08AbilityFxNumbersTest,
    "Unmatched.S08.CueFx.AbilityFx embers count / states, arc tilt / speed, hero keys, the hero socket of CUE-014 (FX-26..FX-32)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08AbilityFxNumbersTest::RunTest(const FString&) {
  using namespace S08AbilityFx;
  using S08HeroesV2::EDissolveStyle;
  // FX-26: 8 per 100 ms of the dissolve, at most 40
  TestEqual("hero 500 ms -> 40 embers", EmberCount(0.5f), 40);
  TestEqual("sidekick 400 ms -> 32 embers", EmberCount(0.4f), 32);
  TestEqual("never above 40", EmberCount(2.0f), 40);
  TestEqual("no dissolve -> none", EmberCount(0.0f), 0);
  TestTrue("ash + MIC + fx on -> spawn", EmbersDecision(EDissolveStyle::Ash, true, true, false) == EEmbersSkip::None);
  TestTrue("fade (rollback) -> none", EmbersDecision(EDissolveStyle::Fade, true, true, false) == EEmbersSkip::Fade);
  TestTrue("reduced motion -> none", EmbersDecision(EDissolveStyle::Fade, true, true, true) == EEmbersSkip::Reduced);
  TestTrue("-S08FxLegacy -> none", EmbersDecision(EDissolveStyle::Ash, true, false, false) == EEmbersSkip::Legacy);
  TestTrue("no MIC (style none) -> none", EmbersDecision(EDissolveStyle::Ash, false, true, false) == EEmbersSkip::NoMaterial);
  TestEqual("embers quad side", EmbersQuadSideUU(60.0f), 60.0f + EmbersTopMarginUU + EmbersBaseMarginUU);
  TestTrue("P1 / P2 chips differ", !EmberTeamColor(ES08TeamSlot::P1).Equals(EmberTeamColor(ES08TeamSlot::P2)));
  // FX-28
  TestEqual("King Arthur key", HeroKeyOfName(TEXT("king arthur")), FString(TEXT("KingArthur")));
  TestEqual("Medusa key", HeroKeyOfName(TEXT("Medusa")), FString(TEXT("Medusa")));
  TestTrue("Arthur with a boost", IsArthurAbilityBoost(TEXT("King Arthur"), 1));
  TestFalse("Arthur without a boost", IsArthurAbilityBoost(TEXT("King Arthur"), 0));
  TestFalse("Merlin with a boost", IsArthurAbilityBoost(TEXT("Merlin"), 1));
  // FX-32: 400 ms x speed; "none" plays nothing
  TestEqual("normal speed", ArcTimeDilation(1.0f), 1.0f);
  TestEqual("fast x0.5 -> dilation 2", ArcTimeDilation(0.5f), 2.0f);
  TestEqual("speed none -> 0", ArcTimeDilation(0.0f), 0.0f);
  const FVector Cam(0.0f, 600.0f, 900.0f);
  const FVector Hand(0.0f, 0.0f, 40.0f);
  TestTrue("an upright blade has no tilt", FMath::IsNearlyZero(ArcTiltDeg(Hand, FVector::UpVector, Cam), 0.5f));
  TestTrue("an axis is folded up (a blade pointing down = upright)",
           FMath::IsNearlyZero(ArcTiltDeg(Hand, -FVector::UpVector, Cam), 0.5f));
  TestEqual("a flat blade is clamped to 45", FMath::Abs(ArcTiltDeg(Hand, FVector(1.0f, 0.0f, 0.05f), Cam)), ArcMaxTiltDeg);
  TestTrue("arc quad is centred on the socket", ArcQuad(Hand, 69.0f, Cam).GetLocation().Equals(Hand));
  TestTrue("arc cell 1.4457 H (ВР-VS2-FX31-01)", FMath::IsNearlyEqual(ArcCellRel, 1.4457f, 0.001f));
  // FX-30: the yaw turns the flash sector to the camera; the scale is H / 100
  const FTransform V = VortexTransform(FVector::ZeroVector, 55.0f, FVector(600.0f, 0.0f, 900.0f));
  TestTrue("vortex scale H / 100", V.GetScale3D().Equals(FVector(0.55f), 1e-4f));
  TestTrue("vortex yaw = camera yaw - 30", FMath::IsNearlyEqual(V.Rotator().Yaw, -VortexFlashLocalYawDeg, 0.01f));
  // FX-28: the CUE-014 show line names the hero's socket (SocketResolver), the row's Weapon otherwise
  FS08CueDispatcher Cues;
  Cues.SocketResolver = [](const FString& CueId, const FString& Subject) {
    return CueId == TEXT("CUE-014") && Subject == TEXT("medusa") ? FString(TEXT("Root")) : FString();
  };
  TArray<FString> Lines;
  Cues.Feed(TEXT("CUE-014"), TEXT("medusa"), 5, 0, Lines);
  Cues.Feed(TEXT("CUE-014"), TEXT("arthur"), 6, 10, Lines);
  TestTrue("Medusa socket=Root", Lines.ContainsByPredicate([](const FString& L) {
    return L.Contains(TEXT("subject=medusa")) && L.Contains(TEXT("socket=Root"));
  }));
  TestTrue("Arthur socket=Weapon", Lines.ContainsByPredicate([](const FString& L) {
    return L.Contains(TEXT("subject=arthur")) && L.Contains(TEXT("socket=Weapon"));
  }));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
