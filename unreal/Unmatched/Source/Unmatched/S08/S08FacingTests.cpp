// AN-23 / AN-24 (ВР-06, 02-visual-design.md §8.3) automation tests of the facing rules (S08Facing.h):
//   Unmatched.S08.Facing.Rest - the rest angle: the offset towards the nearest living enemy clamped to +-45 deg from
//     the camera axis, the 10 deg dead band, no enemy keeps the current angle, angles wrap through 0/360, and on
//     seeded random boards |off| <= MaxIdleOffDeg for every constellation.
//   Unmatched.S08.Facing.Attack - the attack angle: the direction to the target clamped to +-90 deg from the camera
//     axis (ВР-AN02: even the lunge never shows the back).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Facing" <abs log>
#if WITH_AUTOMATION_TESTS

#include "S08Facing.h"
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"

namespace {
bool Near(double A, double B, double Epsilon = 0.1) { return FMath::Abs(FMath::UnwindDegrees(A - B)) < Epsilon; }
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FacingRestTest,
    "Unmatched.S08.Facing.Rest three-quarter to the camera, +-45 to the enemy, dead band, wrap (AN-23, BP-06)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FacingRestTest::RunTest(const FString&) {
  using namespace S08Facing;
  // The constants of the table (02 §8.3 / the AN-23 card).
  TestEqual("MaxIdleOffDeg 45", static_cast<int32>(MaxIdleOffDeg), 45);
  TestEqual("DeadBandDeg 10", static_cast<int32>(DeadBandDeg), 10);
  TestEqual("AttackMaxOffDeg 90", static_cast<int32>(AttackMaxOffDeg), 90);
  TestEqual("AttackTurnMs 120", static_cast<int32>(AttackTurnMs), 120);
  TestEqual("ReturnMs 150", static_cast<int32>(ReturnMs), 150);

  const FVector Figure(0, 0, 0);
  const FVector Cam(0, 1000, 0);  // straight in front: the axis is yaw 90 (+Y)
  // The enemy in front beside the camera axis: the offset follows it.
  TestTrue("enemy 30 deg off the axis: rest = axis + 30",
           Near(RestYaw(Figure, Cam, true, FVector(-500, 866, 0), 0.0), 120.0));
  // The enemy behind the camera (across): the offset clamps to +45.
  TestTrue("enemy behind: clamped to +45", Near(RestYaw(Figure, Cam, true, FVector(-2000, -500, 0), 0.0), 135.0));
  TestTrue("enemy behind the other side: clamped to -45",
           Near(RestYaw(Figure, Cam, true, FVector(2000, -500, 0), 0.0), 45.0));
  // Dead band: a wanted angle within 10 deg of the current one keeps it.
  TestTrue("dead band: 9 deg away keeps the current angle",
           Near(RestYaw(Figure, Cam, true, FVector(-326, 945, 0), 100.0), 100.0));  // want 109 - inside the band
  TestTrue("outside the band: the wanted angle wins",
           Near(RestYaw(Figure, Cam, true, FVector(-866, 500, 0), 0.0), 135.0));    // want 135, current 0 - 135 away
  // No living enemy: the current angle stays (ВР-06: one appearing faces the camera).
  TestTrue("no enemy: the current angle stays", Near(RestYaw(Figure, Cam, false, FVector::ZeroVector, 217.0), 217.0));
  // Wrap through 0/360: the camera at -X (axis 180), the enemy towards -10 deg (unwrapped 350).
  const FVector CamWest(-1000, 0, 0);
  TestTrue("wrap: axis 180, enemy at 350 -> shortest +45 = 225",
           Near(RestYaw(Figure, CamWest, true, FVector(985, -174, 0), 0.0), 225.0));
  TestTrue("wrap: the dead band across 0/360",
           Near(RestYaw(Figure, CamWest, true, FVector(-999, -35, 0), 174.0), 174.0));  // want 182 - inside the band
  // Seeded random constellations: a real rest angle (the dead band did not keep the current one) is never further
  // than MaxIdleOffDeg from the camera axis - the ВР-06 readability rule. A kept angle was within the band of the
  // wanted one, so it is at most DeadBandDeg wider - the standing figure stays put.
  FRandomStream Random(20261006);
  for (int32 I = 0; I < 200; ++I) {
    const FVector Pos(Random.FRand() * 2000.0 - 1000.0, Random.FRand() * 1600.0 - 800.0, 0.0);
    const FVector Camera(Random.FRand() * 2000.0 - 1000.0, Random.FRand() * 2400.0 + 200.0, Random.FRand() * 800.0 + 400.0);
    const FVector Enemy(Random.FRand() * 2000.0 - 1000.0, Random.FRand() * 1600.0 - 800.0, 0.0);
    const double Current = Random.FRand() * 360.0;
    const double Rest = RestYaw(Pos, Camera, true, Enemy, Current);
    if (FMath::Abs(FMath::FindDeltaAngleDegrees(Current, Rest)) < DeadBandDeg) continue;  // the band kept it
    const double Off = FMath::Abs(FMath::FindDeltaAngleDegrees(YawToward(Pos, Camera), Rest));
    TestTrue(FString::Printf(TEXT("random %d: |off| %.1f <= 45 (rest %.1f axis %.1f)"), I, Off, Rest,
                             YawToward(Pos, Camera)),
             Off <= MaxIdleOffDeg + 0.001);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FacingAttackTest,
    "Unmatched.S08.Facing.Attack to the target, clamped to +-90 from the camera axis (AN-24, BP-06)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FacingAttackTest::RunTest(const FString&) {
  using namespace S08Facing;
  const FVector Figure(0, 0, 0);
  const FVector Cam(0, 1000, 0);  // the axis yaw 90 (+Y)
  // A target in front: the attacker faces it exactly.
  TestTrue("target 25 deg off the axis: the attack angle is axis + 25",
           Near(AttackYaw(Figure, FVector(-423, 906, 0), Cam), 115.0));
  // A target behind the attacker (across the camera): clamped to +90 (VP-AN02 - never the back).
  TestTrue("target behind: clamped to +90", Near(AttackYaw(Figure, FVector(-1000, 0, 0), Cam), 180.0));
  TestTrue("target behind the other side: clamped to -90", Near(AttackYaw(Figure, FVector(1000, 0, 0), Cam), 0.0));
  // Seeded random constellations: |off from the camera axis| <= AttackMaxOffDeg always.
  FRandomStream Random(20261007);
  for (int32 I = 0; I < 200; ++I) {
    const FVector Pos(Random.FRand() * 2000.0 - 1000.0, Random.FRand() * 1600.0 - 800.0, 0.0);
    const FVector Camera(Random.FRand() * 2000.0 - 1000.0, Random.FRand() * 2400.0 + 200.0, Random.FRand() * 800.0 + 400.0);
    const FVector Target(Random.FRand() * 2000.0 - 1000.0, Random.FRand() * 1600.0 - 800.0, 0.0);
    const double Yaw = AttackYaw(Pos, Target, Camera);
    const double Off = FMath::Abs(FMath::FindDeltaAngleDegrees(YawToward(Pos, Camera), Yaw));
    TestTrue(FString::Printf(TEXT("random %d: attack |off| %.1f <= 90 (yaw %.1f)"), I, Off, Yaw),
             Off <= AttackMaxOffDeg + 0.001);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FacingReturnTest,
    "Unmatched.S08.Facing.Return 150 ms, shortest arc through 0/360, dead band off, interrupted by a new Face (AN-25)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FacingReturnTest::RunTest(const FString&) {
  using namespace S08Facing;
  // The return takes ReturnMs and always reaches the rest angle: the dead band does not apply (AN-25).
  const FVector Figure(0, 0, 0);
  const FVector Cam(0, 1000, 0);
  TestTrue("bypass of the dead band: 9 deg away still returns to the wanted angle",
           Near(RestYaw(Figure, Cam, true, FVector(-326, 945, 0), 100.0, /*bApplyDeadBand=*/false), 109.0));
  TestTrue("with the dead band the same input keeps the current angle",
           Near(RestYaw(Figure, Cam, true, FVector(-326, 945, 0), 100.0, /*bApplyDeadBand=*/true), 100.0));
  // The shortest arc: through 0/360, never the long way round.
  TestTrue("wrap 350 -> 10 through 0 at half: 360 (= 0)", Near(TurnYawAt(350.0, 10.0, 0.5), 360.0));
  TestTrue("wrap 10 -> 350 the other way at half: 0", Near(TurnYawAt(10.0, 350.0, 0.5), 0.0));
  TestTrue("quarter of 90 -> 180", Near(TurnYawAt(90.0, 180.0, 0.25), 112.5));
  TestTrue("the turn ends exactly at the target", Near(TurnYawAt(45.0, 315.0, 1.0), 315.0));
  // An interruption by a new Face restarts from wherever the return is: blending the CURRENT angle to the new target
  // stays on the new shortest arc (the actor takes FacingYawDeg as the new From).
  const double Mid = TurnYawAt(0.0, 90.0, 0.5);       // the return got to 45
  TestTrue("the interrupted turn continues from its current angle on the new shortest arc",
           Near(TurnYawAt(Mid, 270.0, 0.5), -22.5));  // 45 + 0.5 x (270 - 45 unwound to -135)
  return true;
}

#endif  // WITH_AUTOMATION_TESTS