// AN-23 / AN-24 (ВР-06, 02-visual-design.md §8.3) automation tests of the facing rules (S08Facing.h):
//   Unmatched.S08.Facing.Rest - the rest angle: the offset towards the nearest living enemy clamped to +-45 deg from
//     the camera axis, the 10 deg dead band, no enemy keeps the current angle, angles wrap through 0/360, and on
//     seeded random boards |off| <= MaxIdleOffDeg for every constellation.
//   Unmatched.S08.Facing.Attack - the attack angle: the direction to the target clamped to +-90 deg from the camera
//     axis (ВР-AN02: even the lunge never shows the back).
//   Unmatched.S08.Facing.Actor - a v2 figure: a later snapshot keeps the v1 angle on the mesh (Z-1 review F1), the
//     attack hold, the snap deferred to the Lunge frame (ВР-Z1R-05), the return, no turn under 0.5 deg.
//   Unmatched.S08.Facing.Board - the board's first snapshot faces both teams with their enemy offset (review F2).
// Headless: node tools/s08/run-ue-tests.cjs "Unmatched.S08.Facing" <abs log>
#if WITH_AUTOMATION_TESTS

#include "S08Facing.h"
#include "S08BoardActor.h"
#include "S08FighterActor.h"
#include "S08HeroesV2.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Math/RandomStream.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace {
bool Near(double A, double B, double Epsilon = 0.1) { return FMath::Abs(FMath::UnwindDegrees(A - B)) < Epsilon; }
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FacingRestTest,
    "Unmatched.S08.Facing.Rest three-quarter to the camera, +-45 to the enemy, dead band, wrap (AN-23, VR-06)",
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
  // VC C1 (ВР-VC-01): the per-hero cap - Medusa's rest offset at most MedusaRestMaxOffDeg, every other hero 45; the
  // cap never widens the table (clamped to 0..45). (A run started with -S08FaceCapLegacy / -S08FaceCapMedusa= skips.)
  if (!FParse::Param(FCommandLine::Get(), FaceCapLegacyFlagName) &&
      !FString(FCommandLine::Get()).Contains(FaceCapMedusaParamName)) {
    TestEqual("MedusaRestMaxOffDeg 10", static_cast<int32>(MedusaRestMaxOffDeg), 10);
    TestTrue("cap: Medusa", Near(RestMaxOffDeg(TEXT("Medusa")), MedusaRestMaxOffDeg));
    TestTrue("cap: Medusa, any case", Near(RestMaxOffDeg(TEXT("medusa")), MedusaRestMaxOffDeg));
    TestTrue("cap: Harpy 45", Near(RestMaxOffDeg(TEXT("Harpy")), MaxIdleOffDeg));
    TestTrue("cap: King Arthur 45", Near(RestMaxOffDeg(TEXT("KingArthur")), MaxIdleOffDeg));
    TestTrue("cap: no hero 45", Near(RestMaxOffDeg(nullptr), MaxIdleOffDeg));
    TestEqual("ARTLOOK token", FaceCapLookField(), FString(TEXT("medusa10")));
  }
  TestTrue("capped 20: enemy behind -> axis + 20",
           Near(RestYaw(Figure, Cam, true, FVector(-2000, -500, 0), 0.0, true, 20.0), 110.0));
  TestTrue("capped 20: the other side -> axis - 20",
           Near(RestYaw(Figure, Cam, true, FVector(2000, -500, 0), 0.0, true, 20.0), 70.0));
  TestTrue("capped 20: an enemy 10 deg off follows it", Near(RestYaw(Figure, Cam, true, FVector(-174, 985, 0), 0.0, true, 20.0), 100.0));
  TestTrue("a cap over 45 never widens the table",
           Near(RestYaw(Figure, Cam, true, FVector(-2000, -500, 0), 0.0, true, 80.0), 135.0));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FacingAttackTest,
    "Unmatched.S08.Facing.Attack to the target, clamped to +-90 from the camera axis (AN-24, VR-06)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FacingAttackTest::RunTest(const FString&) {
  using namespace S08Facing;
  const FVector Figure(0, 0, 0);
  const FVector Cam(0, 1000, 0);  // the axis yaw 90 (+Y)
  // A target in front: the attacker faces it exactly.
  TestTrue("target 25 deg off the axis: the attack angle is axis + 25",
           Near(AttackYaw(Figure, FVector(-423, 906, 0), Cam), 115.0));
  // A target behind the attacker (across the camera): clamped to +90 (ВР-AN02 - never the back).
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

namespace S08FacingWorldTest {
FS08BoardFighter Fighter(const TCHAR* Id, const TCHAR* Owner, const TCHAR* Name, bool bHero, int32 X, int32 Y) {
  FS08BoardFighter F;
  F.Id = Id;
  F.OwnerId = Owner;
  F.Name = Name;
  F.Label = Name;
  F.bIsHero = bHero;
  F.Health = F.MaxHealth = 8;
  F.X = X;
  F.Y = Y;
  return F;
}
FS08BoardModel Grid(int32 W, int32 H) {
  FS08BoardModel Board;
  Board.Width = W;
  Board.Height = H;
  Board.Cells.Init(FS08Cell(), W * H);
  for (int32 Y = 0; Y < H; ++Y) {
    for (int32 X = 0; X < W; ++X) {
      FS08Cell& Cell = Board.Cells[Y * W + X];
      Cell.X = X;
      Cell.Y = Y;
      Cell.Type = ES08CellType::Normal;
    }
  }
  return Board;
}
struct FTestWorld {
  UWorld* World = nullptr;
  explicit FTestWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
  }
  ~FTestWorld() {
    if (!World) return;
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  }
};
}  // namespace S08FacingWorldTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FacingActorTest,
    "Unmatched.S08.Facing.Actor a snapshot keeps the v1 angle on the mesh; attack hold, Lunge snap, return (AN-23..25, Z-1 review F1)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FacingActorTest::RunTest(const FString&) {
  using namespace S08FacingWorldTest;
  FTestWorld W(TEXT("S08FacingActorWorld"));
  if (!W.World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  const FVector Cell(0, -400, 0);
  AS08FighterActor* Arthur = W.World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), Cell, FRotator::ZeroRotator);
  const FS08BoardFighter F = Fighter(TEXT("f-1-hero"), TEXT("guest"), TEXT("King Arthur"), true, 2, 1);
  Arthur->SetTeam(ES08TeamSlot::P2, ES08TeamSlot::P2, ES08TeamColorMode::Absolute);
  Arthur->ApplyFighter(F, Cell, false, true);
  if (!Arthur->IsHeroV2()) {
    AddWarning(TEXT("v2 Arthur assets missing in this checkout - the actor facing test is skipped"));
    Arthur->Destroy();
    return true;
  }
  auto ShownMatches = [this, Arthur](const TCHAR* What) {
    const double Delta = FMath::Abs(FMath::FindDeltaAngleDegrees(Arthur->GetShownFigureYawDeg(), Arthur->GetFigureYawDeg()));
    TestTrue(FString::Printf(TEXT("%s: the mesh shows the facing (shown %.1f, facing %.1f)"), What,
                             Arthur->GetShownFigureYawDeg(), Arthur->GetFigureYawDeg()),
             Delta < 0.1);
  };
  // Before any rest facing the mesh and the facing agree on the half-field angle (the turn starts from what shows).
  ShownMatches(TEXT("first apply"));
  const FVector Cam(0, 1342, 1917);  // the K1 camera of the map boards
  const FVector Enemy(300, 200, 0);
  Arthur->ApplyRestFacing(TEXT("snapshot"), false, Cam, true, Enemy, TEXT("f-0-sk0"));
  Arthur->AdvanceFacingTurn(0.2f);
  const double Rest = S08Facing::RestYaw(Cell, Cam, true, Enemy, 0.0, false);
  TestTrue(FString::Printf(TEXT("spawn: the v1 rest angle (%.1f, want %.1f)"), Arthur->GetFigureYawDeg(), Rest),
           Near(Arthur->GetFigureYawDeg(), Rest));
  TestFalse("spawn: not the half-field rule any more", Near(Arthur->GetFigureYawDeg(), S08HeroesV2::FigureYawDeg(Cell.Y), 1.0));
  ShownMatches(TEXT("after the spawn turn"));
  // F1: another snapshot on the same cell (ApplyHeroV2 resets the mesh to the half-field yaw) keeps the v1 angle.
  Arthur->ApplyFighter(F, Cell, false, true);
  ShownMatches(TEXT("second snapshot, same cell"));
  TestTrue("second snapshot: the facing itself unchanged", Near(Arthur->GetFigureYawDeg(), Rest));
  // A snapshot in the middle of a turn shows the blend, not the half-field angle.
  const FVector Enemy2(-400, 300, 0);
  Arthur->ApplyRestFacing(TEXT("snapshot"), false, Cam, true, Enemy2, TEXT("f-0-sk1"));
  Arthur->AdvanceFacingTurn(0.05f);
  Arthur->ApplyFighter(F, Cell, false, true);
  ShownMatches(TEXT("snapshot mid-turn"));
  Arthur->AdvanceFacingTurn(0.2f);
  const double Rest2 = S08Facing::RestYaw(Cell, Cam, true, Enemy2, 0.0, false);
  TestTrue("the interrupted turn still lands on the new rest angle", Near(Arthur->GetFigureYawDeg(), Rest2));
  // AN-24: the face turn holds the target angle - a snapshot in between does not take it back to rest.
  const FVector TargetPos(500, -300, 0);
  const FVector ViewCam = AS08BoardActor::ViewCameraLocation(W.World);
  const double Attack = S08Facing::AttackYaw(Cell, TargetPos, ViewCam);
  Arthur->PlayFaceTarget(TEXT("f-0-hero"), TargetPos, S08Facing::AttackTurnMs, 1000, /*bSnapAtLunge=*/false);
  TestTrue("face: the attacker holds", Arthur->IsHoldingAttackFacing());
  Arthur->ApplyRestFacing(TEXT("snapshot"), false, Cam, true, Enemy, TEXT("f-0-sk0"));  // ignored while holding
  Arthur->AdvanceFacingTurn(0.2f);
  TestTrue(FString::Printf(TEXT("face: the attack angle (%.1f, want %.1f)"), Arthur->GetFigureYawDeg(), Attack),
           Near(Arthur->GetFigureYawDeg(), Attack));
  ShownMatches(TEXT("attack angle"));
  // AN-25: the return reaches the rest angle (no dead band) and ends the hold.
  Arthur->ReturnToRestFacing(TEXT("attack-return"), Rest, S08Facing::ReturnMs, 1583);
  TestFalse("return: the hold ends", Arthur->IsHoldingAttackFacing());
  Arthur->AdvanceFacingTurn(0.2f);
  TestTrue("return: the rest angle", Near(Arthur->GetFigureYawDeg(), Rest));
  // F4: a return under 0.5 deg is no turn.
  Arthur->ReturnToRestFacing(TEXT("hit-return"), Rest + 0.3, S08Facing::ReturnMs, 2000);
  TestFalse("a 0.3 deg return starts no turn", Arthur->IsFacingTurning());
  // ВР-Z1R-05: reduced motion / speed "none" - no turn at the Face event, the snap in the Lunge frame.
  Arthur->PlayFaceTarget(TEXT("f-0-hero"), TargetPos, S08Facing::AttackTurnMs, 3000, /*bSnapAtLunge=*/true);
  Arthur->AdvanceFacingTurn(0.2f);
  TestTrue("deferred: still at rest before the Lunge", Near(Arthur->GetFigureYawDeg(), Rest));
  Arthur->CommitFaceTarget(3120);
  TestTrue("deferred: the attack angle in the Lunge frame", Near(Arthur->GetFigureYawDeg(), Attack));
  ShownMatches(TEXT("snap at the lunge"));
  Arthur->Destroy();
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FacingBoardTest,
    "Unmatched.S08.Facing.Board the first snapshot faces every figure with its enemy offset, both teams (AN-23, Z-1 review F2)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FacingBoardTest::RunTest(const FString&) {
  using namespace S08FacingWorldTest;
  FTestWorld W(TEXT("S08FacingBoardWorld"));
  if (!W.World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  AS08BoardActor* Board = W.World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                              FRotator::ZeroRotator);
  if (!TestNotNull("board actor", Board)) return true;
  const FS08BoardModel Model = Grid(7, 6);
  Board->Rebuild(Model);
  // The fixture order of the benches: the first team (f-0: Medusa + three harpies) comes first - it saw no enemy in
  // the old spawn loop and kept the legacy angle.
  const TArray<FS08BoardFighter> Roster = {
      Fighter(TEXT("f-0-hero"), TEXT("host"), TEXT("Medusa"), true, 1, 1),
      Fighter(TEXT("f-0-sk0"), TEXT("host"), TEXT("Harpies"), false, 0, 2),
      Fighter(TEXT("f-0-sk1"), TEXT("host"), TEXT("Harpies"), false, 2, 3),
      Fighter(TEXT("f-0-sk2"), TEXT("host"), TEXT("Harpies"), false, 1, 4),
      Fighter(TEXT("f-1-hero"), TEXT("guest"), TEXT("King Arthur"), true, 5, 2),
      Fighter(TEXT("f-1-sk0"), TEXT("guest"), TEXT("Merlin"), false, 6, 4)};
  Board->SyncFighters(Model, Roster, TEXT("host"));
  const FVector Cam = Board->LocalCameraLocation();
  for (const FS08BoardFighter& F : Roster) {
    AS08FighterActor* Actor = Board->FindFighterActor(F.Id);
    if (!TestNotNull(F.Id, Actor)) continue;
    Actor->AdvanceFacingTurn(1.0f);
    const double Want = Board->RestYawFor(Actor, Actor->GetActorLocation());
    TestTrue(FString::Printf(TEXT("%s: the rest angle with its enemy offset (%.1f, want %.1f)"), *F.Id,
                             Actor->GetFigureYawDeg(), Want),
             Near(Actor->GetFigureYawDeg(), Want));
    const double Off = FMath::Abs(FMath::FindDeltaAngleDegrees(S08Facing::YawToward(Actor->GetActorLocation(), Cam),
                                                               Actor->GetFigureYawDeg()));
    TestTrue(FString::Printf(TEXT("%s: |off| %.1f <= 45 (never the back)"), *F.Id, Off), Off <= S08Facing::MaxIdleOffDeg + 0.01);
    // VC C1: a v2 figure keeps its hero's cap (Medusa 10)
    TestTrue(FString::Printf(TEXT("%s: |off| %.1f <= its cap %.0f"), *F.Id, Off, Actor->RestCapDeg()),
             Off <= Actor->RestCapDeg() + 0.01);
  }
  // A second identical snapshot changes nothing (the dead band; no turn).
  Board->SyncFighters(Model, Roster, TEXT("host"));
  for (const FS08BoardFighter& F : Roster) {
    if (const AS08FighterActor* Actor = Board->FindFighterActor(F.Id)) {
      TestFalse(FString::Printf(TEXT("%s: the same snapshot starts no turn"), *F.Id), Actor->IsFacingTurning());
    }
  }
  Board->Destroy();
  return true;
}

#endif  // WITH_AUTOMATION_TESTS