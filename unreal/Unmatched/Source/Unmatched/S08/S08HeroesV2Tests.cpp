// Wave 5c-B automation tests of the heroes v2 (S08HeroesV2.h; the default figures since ART-DEFAULT 2026-10-04,
// rollback -S08HeroesLegacy): name -> asset mapping on an art board by default and none with the rollback or on the
// grey board, the +X -> +Y facing offset on both board sides, the height budget scale, the clip choice per combat
// event, the real look-dev C assets (bounds, skeletons, clip lengths) and the fighter actor end to end (mesh, MI by
// look, yaw, Idle / HitReact / LungeAttack / DeathSettle). The command-line default is S08ArtLookTests.cpp.
// Headless run:
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.HeroesV2; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08HeroesV2.h"
#include "S08BoardModel.h"
#include "S08ContactAnimNotify.h"
#include "S08FighterActor.h"
#include "UI/UmHudPanels.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/Skeleton.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/Font.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialExpressionScalarParameter.h"
#include "Materials/MaterialExpressionStaticSwitchParameter.h"
#include "Materials/MaterialExpressionVectorParameter.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"

namespace S08HeroesV2Test {

// Cyclic distance of two phases in [0, 1).
float PhaseGap(float A, float B) {
  const float D = FMath::Abs(A - B);
  return FMath::Min(D, 1.0f - D);
}

struct FFlagScope {
  explicit FFlagScope(bool bOn) { S08HeroesV2::SetFlagOverrideForTest(bOn); }
  ~FFlagScope() { S08HeroesV2::ResetFlagOverrideForTest(); }
};

FS08BoardFighter MakeFighter(const TCHAR* Id, const TCHAR* Name, bool bHero, int32 X, int32 Y) {
  FS08BoardFighter F;
  F.Id = Id;
  F.OwnerId = TEXT("owner");
  F.Name = Name;
  F.Label = Name;
  F.bIsHero = bHero;
  F.Health = 10;
  F.MaxHealth = 10;
  F.X = X;
  F.Y = Y;
  return F;
}

const USkeletalMeshComponent* ArtBodyOf(const AS08FighterActor* Actor) {
  TInlineComponentArray<USkeletalMeshComponent*> Skels(Actor);
  for (USkeletalMeshComponent* Skel : Skels) {
    if (Skel->GetFName() == TEXT("ArtBody")) return Skel;
  }
  return nullptr;
}

const UStaticMeshComponent* StaticComponentOf(const AS08FighterActor* Actor, const TCHAR* Name) {
  TInlineComponentArray<UStaticMeshComponent*> Meshes(Actor);
  for (UStaticMeshComponent* Mesh : Meshes) {
    if (Mesh->GetFName() == Name) return Mesh;
  }
  return nullptr;
}
}  // namespace S08HeroesV2Test

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2MappingTest,
    "Unmatched.S08.HeroesV2.Mapping fighter name to v2 assets on an art board by default, none with -S08HeroesLegacy or on the grey board",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2MappingTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  using namespace S08HeroesV2Test;
  TestEqual("no-op alias name", FString(FlagName), FString(TEXT("ArtPreviewHeroesV2")));
  TestEqual("rollback flag name", FString(LegacyFlagName), FString(TEXT("S08HeroesLegacy")));
  TestTrue("default: v2", Decide(false, false));
  TestFalse("-S08HeroesLegacy: legacy figures", Decide(true, false));
  TestFalse("-ArtPreview -ArtPreviewAllMedusa review: the Medusa candidate on every fighter", Decide(false, true));
  {
    FFlagScope Off(false);
    TestFalse("override off", FlagEnabled());
  }
  {
    FFlagScope On(true);
    TestTrue("override on", FlagEnabled());
  }
  for (const TCHAR* Name : {TEXT("King Arthur"), TEXT("Merlin"), TEXT("Medusa"), TEXT("Harpies")}) {
    TestNull(FString::Printf(TEXT("%s: no mapping with -S08HeroesLegacy"), Name), Find(true, false, Name));
    TestNull(FString::Printf(TEXT("%s: no mapping on the grey board"), Name), Find(false, true, Name));
    TestNotNull(FString::Printf(TEXT("%s: mapped on an art board (default)"), Name), Find(true, true, Name));
  }
  TestNull("unmapped hero stays legacy", Find(true, true, TEXT("Sinbad")));
  TestNull("a Harpy label is not a fighter name", Find(true, true, TEXT("Harpies 2")));
  TestNotNull("case-insensitive name", Find(true, true, TEXT("king arthur")));
  TestEqual("four heroes", Specs().Num(), 4);

  const FHeroSpec* Arthur = Find(true, true, TEXT("King Arthur"));
  const FHeroSpec* Merlin = Find(true, true, TEXT("Merlin"));
  const FHeroSpec* Medusa = Find(true, true, TEXT("Medusa"));
  const FHeroSpec* Harpy = Find(true, true, TEXT("Harpies"));
  if (!Arthur || !Merlin || !Medusa || !Harpy) return true;
  TestEqual("Arthur mesh", MeshPath(*Arthur),
            FString(TEXT("/Game/PipelineCandidates/KingArthur/H2LD/Meshes/SK_KingArthur_H2LD")));
  TestEqual("Arthur pedestal", PedestalPath(*Arthur),
            FString(TEXT("/Game/PipelineCandidates/KingArthur/H2LD/Meshes/SM_KingArthur_H2LD_Base")));
  TestEqual("Arthur P1 MI", BodyMaterialPath(*Arthur, ES08TeamSlot::P1),
            FString(TEXT("/Game/PipelineCandidates/KingArthur/H2LD/Materials/MI_KingArthur_H2LD_P1")));
  TestEqual("Arthur P2 MI", BodyMaterialPath(*Arthur, ES08TeamSlot::P2),
            FString(TEXT("/Game/PipelineCandidates/KingArthur/H2LD/Materials/MI_KingArthur_H2LD_P2")));
  TestEqual("Arthur P2 pedestal MI", PedestalMaterialPath(*Arthur, ES08TeamSlot::P2),
            FString(TEXT("/Game/PipelineCandidates/KingArthur/H2LD/Materials/MI_KingArthur_H2LD_Base_P2")));
  TestEqual("Arthur skeleton", SkeletonPath(*Arthur),
            FString(TEXT("/Game/PipelineCandidates/KingArthur/Rig/SK_KingArthur_Skeleton")));
  TestEqual("Arthur lunge clip", ClipPath(*Arthur, EClip::LungeAttack),
            FString(TEXT("/Game/PipelineCandidates/KingArthur/H2Anim/AM_KingArthur_LungeAttack")));
  TestEqual("Merlin P1 MI", BodyMaterialPath(*Merlin, ES08TeamSlot::P1),
            FString(TEXT("/Game/PipelineCandidates/Merlin/H2LD/Materials/MI_Merlin_H2LD_P1")));
  TestEqual("Medusa P2 pedestal MI", PedestalMaterialPath(*Medusa, ES08TeamSlot::P2),
            FString(TEXT("/Game/PipelineCandidates/Medusa/H2LD/Materials/MI_Medusa_H2LD_Base_P2")));
  TestEqual("Harpy mesh (H3LD)", MeshPath(*Harpy),
            FString(TEXT("/Game/PipelineCandidates/Harpy/H3LD/Meshes/SK_Harpy_H3LD")));
  TestEqual("Harpy P1 MI (H3LD)", BodyMaterialPath(*Harpy, ES08TeamSlot::P1),
            FString(TEXT("/Game/PipelineCandidates/Harpy/H3LD/Materials/MI_Harpy_H3LD_P1")));
  TestEqual("Harpy pedestal P1 MI", PedestalMaterialPath(*Harpy, ES08TeamSlot::P1),
            FString(TEXT("/Game/PipelineCandidates/Harpy/H3LD/Materials/MI_Harpy_H3LD_Base_P1")));
  TestEqual("Harpy death clip (H2Anim)", ClipPath(*Harpy, EClip::DeathSettle),
            FString(TEXT("/Game/PipelineCandidates/Harpy/H2Anim/AM_Harpy_DeathSettle")));
  TestTrue("no clip path for None", ClipPath(*Harpy, EClip::None).IsEmpty());
  TestTrue("Arthur / Medusa are heroes", Arthur->bHero && Medusa->bHero);
  TestFalse("Merlin is a sidekick", Merlin->bHero);
  TestFalse("Harpies are sidekicks", Harpy->bHero);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2FacingTest,
    "Unmatched.S08.HeroesV2.Facing rig v2 (+X) turned to the legacy +Y / -Y facing on both board sides",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2FacingTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  using namespace S08HeroesV2Test;
  TestEqual("offset is +90 deg", FacingYawOffsetDeg, 90.0f);
  // Cells of the 5x6 board (S04 control points): row y=2 -> world Y -50 (near side, faces +Y), row y=3 -> +50.
  for (const double CellY : {-250.0, -50.0, 50.0, 250.0}) {
    const FVector Legacy = FRotator(0.0, LegacyFigureYawDeg(CellY), 0.0).RotateVector(FVector::YAxisVector);
    const FVector V2 = FRotator(0.0, FigureYawDeg(CellY), 0.0).RotateVector(FVector::XAxisVector);
    TestTrue(FString::Printf(TEXT("cell Y=%.0f: v2 face == legacy face (%s vs %s)"), CellY, *V2.ToString(),
                             *Legacy.ToString()),
             V2.Equals(Legacy, 1e-4));
    // Both sides face the board centre line (Y = 0): the far half looks back toward it.
    TestTrue(FString::Printf(TEXT("cell Y=%.0f faces the centre line"), CellY), V2.Y * (-CellY) > 0.0);
  }
  TestEqual("near side yaw", FigureYawDeg(-50.0), 90.0f);
  TestEqual("far side yaw", FigureYawDeg(50.0), 270.0f);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2ScaleTest,
    "Unmatched.S08.HeroesV2.Scale visible figure height normalised to the per-hero budget",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2ScaleTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  using namespace S08HeroesV2Test;
  float HeroMin = TNumericLimits<float>::Max();
  float SidekickMax = 0.0f;
  for (const FHeroSpec& Spec : Specs()) {
    const float K = FigureScale(Spec);
    const float Visible = Spec.FigureTopUU * K;
    AddInfo(FString::Printf(TEXT("%s: budget %.1f uu (card %.0f..%.0f), measured figure top %.3f uu, bounds top %.2f uu -> scale %.4f, visible %.2f uu, with weapon %.2f uu"),
                            Spec.Key, Spec.BudgetUU, Spec.BudgetMinUU, Spec.BudgetMaxUU, Spec.FigureTopUU,
                            Spec.BoundsTopUU, K, Visible, Spec.BoundsTopUU * K));
    TestTrue(FString::Printf(TEXT("%s visible height == budget"), Spec.Key), FMath::IsNearlyEqual(Visible, Spec.BudgetUU, 0.01f));
    TestTrue(FString::Printf(TEXT("%s budget inside the 17 4.2 card"), Spec.Key),
             Spec.BudgetUU >= Spec.BudgetMinUU && Spec.BudgetUU <= Spec.BudgetMaxUU);
    TestTrue(FString::Printf(TEXT("%s scale is a normalisation, not a resize (|k-1| < 1%%)"), Spec.Key),
             FMath::Abs(K - 1.0f) < 0.01f);
    TestTrue(FString::Printf(TEXT("%s weapon/wing top not below the figure"), Spec.Key),
             Spec.BoundsTopUU + 0.01f >= Spec.FigureTopUU);
    if (Spec.bHero) HeroMin = FMath::Min(HeroMin, Visible);
    else SidekickMax = FMath::Max(SidekickMax, Visible);
  }
  TestTrue("every hero taller than every sidekick", HeroMin > SidekickMax);
  // The legacy candidate drew sidekicks at 0.78 of the hero; the v2 budgets keep that proportion (+-0.06).
  const FHeroSpec* Medusa = Find(true, true, TEXT("Medusa"));
  for (const TCHAR* Name : {TEXT("Merlin"), TEXT("Harpies")}) {
    const FHeroSpec* Side = Find(true, true, Name);
    if (!Medusa || !Side) continue;
    const float Ratio = Side->BudgetUU / Medusa->BudgetUU;
    AddInfo(FString::Printf(TEXT("%s / hero = %.3f (legacy sidekick scale 0.78)"), Name, Ratio));
    TestTrue(FString::Printf(TEXT("%s near the legacy 0.78 sidekick ratio"), Name), FMath::Abs(Ratio - 0.78f) <= 0.06f);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2ClipChoiceTest,
    "Unmatched.S08.HeroesV2.Clips chosen per combat event, Idle phase per fighter",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2ClipChoiceTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  using namespace S08HeroesV2Test;
  auto Check = [this](EClip Current, EEvent Event, EClip WantClip, bool bWantRestart) {
    const FClipChoice C = NextClip(Current, Event);
    const FString What = FString::Printf(TEXT("%s + %s"), ClipName(Current), EventName(Event));
    TestEqual(What + TEXT(" clip"), FString(ClipName(C.Clip)), FString(ClipName(WantClip)));
    TestEqual(What + TEXT(" restart"), C.bRestart, bWantRestart);
  };
  Check(EClip::None, EEvent::Spawn, EClip::Idle, true);
  Check(EClip::Idle, EEvent::Spawn, EClip::Idle, false);            // every board sync: no restart
  Check(EClip::LungeAttack, EEvent::Spawn, EClip::LungeAttack, false);  // a sync does not cut the lunge
  Check(EClip::Idle, EEvent::Attack, EClip::LungeAttack, true);
  Check(EClip::Idle, EEvent::Damaged, EClip::HitReact, true);
  Check(EClip::HitReact, EEvent::Damaged, EClip::HitReact, true);   // a second hit restarts
  Check(EClip::LungeAttack, EEvent::Damaged, EClip::HitReact, true);
  Check(EClip::HitReact, EEvent::Attack, EClip::LungeAttack, true);
  Check(EClip::LungeAttack, EEvent::ClipFinished, EClip::Idle, true);
  Check(EClip::HitReact, EEvent::ClipFinished, EClip::Idle, true);
  Check(EClip::Idle, EEvent::ClipFinished, EClip::Idle, false);
  Check(EClip::HitReact, EEvent::Defeated, EClip::DeathSettle, true);
  Check(EClip::Idle, EEvent::Defeated, EClip::DeathSettle, true);
  // The final pose holds: nothing after death restarts or leaves DeathSettle.
  for (const EEvent E : {EEvent::Spawn, EEvent::Attack, EEvent::Damaged, EEvent::Defeated, EEvent::ClipFinished}) {
    Check(EClip::DeathSettle, E, EClip::DeathSettle, false);
  }
  TestTrue("Idle loops", ClipLoops(EClip::Idle));
  TestFalse("LungeAttack is one-shot", ClipLoops(EClip::LungeAttack));
  TestFalse("HitReact is one-shot", ClipLoops(EClip::HitReact));
  TestFalse("DeathSettle is one-shot (holds)", ClipLoops(EClip::DeathSettle));

  // Idle phase: deterministic per id, three Harpies (either seat) well apart.
  TestEqual("phase is deterministic", IdlePhase(TEXT("f-1-sk0")), IdlePhase(TEXT("f-1-sk0")));
  for (const TCHAR* Seat : {TEXT("f-0-"), TEXT("f-1-")}) {
    const float A = IdlePhase(FString(Seat) + TEXT("sk0"));
    const float B = IdlePhase(FString(Seat) + TEXT("sk1"));
    const float C = IdlePhase(FString(Seat) + TEXT("sk2"));
    AddInfo(FString::Printf(TEXT("%ssk0..2 idle phases %.4f %.4f %.4f"), Seat, A, B, C));
    for (const float P : {A, B, C}) TestTrue(TEXT("phase in [0,1)"), P >= 0.0f && P < 1.0f);
    const float MinGap = FMath::Min3(PhaseGap(A, B), PhaseGap(B, C), PhaseGap(A, C));
    TestTrue(FString::Printf(TEXT("%s Harpies not in sync (min gap %.3f >= 0.2)"), Seat, MinGap), MinGap >= 0.2f);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2AssetsTest,
    "Unmatched.S08.HeroesV2.Assets look-dev C meshes, MIs, canonical skeletons and H2Anim clips load and match",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2AssetsTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  using namespace S08HeroesV2Test;
  for (const FHeroSpec& Spec : Specs()) {
    USkeletalMesh* Mesh = LoadObject<USkeletalMesh>(nullptr, *MeshPath(Spec));
    TestNotNull(FString::Printf(TEXT("%s mesh loads"), Spec.Key), Mesh);
    if (!Mesh) continue;
    const USkeleton* Skeleton = Mesh->GetSkeleton();
    TestNotNull(FString::Printf(TEXT("%s mesh has a skeleton"), Spec.Key), Skeleton);
    if (Skeleton) {
      TestEqual(FString::Printf(TEXT("%s canonical skeleton"), Spec.Key), Skeleton->GetPathName(),
                SkeletonPath(Spec) + TEXT(".") + FPaths::GetBaseFilename(SkeletonPath(Spec)));
    }
    const FBox Box = Mesh->GetBounds().GetBox();
    AddInfo(FString::Printf(TEXT("%s SK bounds (%.2f, %.2f, %.2f)..(%.2f, %.2f, %.2f) uu, top %.2f (report %.2f), figure top %.3f, scale %.4f"),
                            Spec.Key, Box.Min.X, Box.Min.Y, Box.Min.Z, Box.Max.X, Box.Max.Y, Box.Max.Z, Box.Max.Z,
                            Spec.BoundsTopUU, Spec.FigureTopUU, FigureScale(Spec)));
    TestTrue(FString::Printf(TEXT("%s bounds top %.2f == look-dev C report %.2f (+-0.5)"), Spec.Key, Box.Max.Z,
                             Spec.BoundsTopUU),
             FMath::IsNearlyEqual(static_cast<float>(Box.Max.Z), Spec.BoundsTopUU, 0.5f));
    TestTrue(FString::Printf(TEXT("%s stands on the cell (bounds min z %.2f in 0..8 uu: body above the pedestal)"),
                             Spec.Key, Box.Min.Z),
             Box.Min.Z >= -0.5 && Box.Min.Z <= 8.0);
    UStaticMesh* Pedestal = LoadObject<UStaticMesh>(nullptr, *PedestalPath(Spec));
    TestNotNull(FString::Printf(TEXT("%s pedestal loads"), Spec.Key), Pedestal);
    if (Pedestal) {
      const FBox PBox = Pedestal->GetBoundingBox();
      AddInfo(FString::Printf(TEXT("%s pedestal %.2f x %.2f x %.2f uu, z %.2f..%.2f"), Spec.Key, PBox.GetSize().X,
                              PBox.GetSize().Y, PBox.GetSize().Z, PBox.Min.Z, PBox.Max.Z));
    }
    for (const ES08TeamSlot Look : {ES08TeamSlot::P1, ES08TeamSlot::P2}) {
      UMaterialInterface* Body = LoadObject<UMaterialInterface>(nullptr, *BodyMaterialPath(Spec, Look));
      UMaterialInterface* Base = LoadObject<UMaterialInterface>(nullptr, *PedestalMaterialPath(Spec, Look));
      TestNotNull(FString::Printf(TEXT("%s body MI %s"), Spec.Key, S08TeamSlotName(Look)), Body);
      TestNotNull(FString::Printf(TEXT("%s pedestal MI %s"), Spec.Key, S08TeamSlotName(Look)), Base);
      if (Body) {
        const UMaterial* Master = Body->GetMaterial();
        TestTrue(FString::Printf(TEXT("%s body MI %s on M_UM_Figure_v2"), Spec.Key, S08TeamSlotName(Look)),
                 Master && Master->GetPathName().StartsWith(TEXT("/Game/UM/Materials/v2/M_UM_Figure_v2")));
      }
    }
    for (const EClip Clip : {EClip::Idle, EClip::LungeAttack, EClip::HitReact, EClip::DeathSettle}) {
      UAnimSequenceBase* Anim = LoadObject<UAnimSequenceBase>(nullptr, *ClipPath(Spec, Clip));
      TestNotNull(FString::Printf(TEXT("%s %s loads"), Spec.Key, ClipName(Clip)), Anim);
      if (!Anim) continue;
      TestTrue(FString::Printf(TEXT("%s %s on the mesh skeleton"), Spec.Key, ClipName(Clip)),
               Anim->GetSkeleton() == Skeleton);
      const float Len = Anim->GetPlayLength();
      AddInfo(FString::Printf(TEXT("%s %s len %.3f s (expected %.3f)"), Spec.Key, ClipName(Clip), Len,
                              ExpectedClipSeconds(Spec, Clip)));
      TestTrue(FString::Printf(TEXT("%s %s length %.3f == %.3f (+-0.02)"), Spec.Key, ClipName(Clip), Len,
                               ExpectedClipSeconds(Spec, Clip)),
               FMath::IsNearlyEqual(Len, ExpectedClipSeconds(Spec, Clip), 0.02f));
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2ActorTest,
    "Unmatched.S08.HeroesV2.Actor fighter actor shows v2 figures by default, legacy figures with -S08HeroesLegacy, and plays the clips",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2ActorTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  using namespace S08HeroesV2Test;
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08HeroesV2ActorWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  const FVector Near(0.0, -50.0, 0.0);  // cell (2,2)
  const FVector Far(0.0, 50.0, 0.0);    // cell (2,3)

  // --- -S08HeroesLegacy (override off): byte-for-byte the legacy mapping (ART-003 blockout, Medusa candidate)
  {
    FFlagScope Off(false);
    AS08FighterActor* Arthur = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), Near, FRotator::ZeroRotator);
    AS08FighterActor* Medusa = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), Far, FRotator::ZeroRotator);
    if (Arthur && Medusa) {
      Arthur->SetTeam(ES08TeamSlot::P1, ES08TeamSlot::P1, ES08TeamColorMode::Absolute);
      Arthur->ApplyFighter(MakeFighter(TEXT("f-0-hero"), TEXT("King Arthur"), true, 2, 2), Near, true, true);
      TestFalse("legacy: Arthur is not v2", Arthur->IsHeroV2());
      TestTrue("legacy: Arthur keeps the ART-003 blockout", Arthur->IsBlockout());
      Medusa->SetTeam(ES08TeamSlot::P2, ES08TeamSlot::P2, ES08TeamColorMode::Absolute);
      Medusa->ApplyFighter(MakeFighter(TEXT("f-1-hero"), TEXT("Medusa"), true, 2, 3), Far, false, true);
      TestFalse("legacy: Medusa is not v2", Medusa->IsHeroV2());
      TestTrue("legacy: Medusa keeps the isolated candidate", Medusa->HasMedusaCandidate());
      const USkeletalMeshComponent* Skel = ArtBodyOf(Medusa);
      TestTrue("legacy: candidate mesh", Skel && Skel->GetSkeletalMeshAsset() &&
                   Skel->GetSkeletalMeshAsset()->GetName().StartsWith(TEXT("SK_Medusa_FaceNeck_v2Candidate")));
      TestEqual("legacy: candidate yaw stays 180 on the far side",
                Skel ? static_cast<float>(Skel->GetRelativeRotation().Yaw) : -1.0f, 180.0f);
      TestTrue("legacy: no v2 clip", Medusa->GetHeroClip() == EClip::None);
      Medusa->NotifyHeroAnimEvent(EEvent::Damaged, 7);
      TestTrue("legacy: combat events are ignored", Medusa->GetHeroClip() == EClip::None);
    } else {
      AddError(TEXT("fighter actors not spawned"));
    }
    if (Arthur) Arthur->Destroy();
    if (Medusa) Medusa->Destroy();
  }

  // --- default (v2 on): v2 mesh, MI by look, pedestal, yaw, scale, Idle, combat clips, death hold
  {
    FFlagScope On(true);
    struct FCase {
      const TCHAR* Id;
      const TCHAR* Name;
      bool bHero;
      ES08TeamSlot Look;
      FVector Cell;
      int32 Y;
    };
    const FCase Cases[] = {
        {TEXT("f-0-hero"), TEXT("King Arthur"), true, ES08TeamSlot::P1, Near, 2},
        {TEXT("f-0-sk0"), TEXT("Merlin"), false, ES08TeamSlot::P1, Near, 2},
        {TEXT("f-1-hero"), TEXT("Medusa"), true, ES08TeamSlot::P2, Far, 3},
        {TEXT("f-1-sk0"), TEXT("Harpies"), false, ES08TeamSlot::P2, Far, 3},
    };
    for (const FCase& C : Cases) {
      AS08FighterActor* Actor = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), C.Cell, FRotator::ZeroRotator);
      if (!Actor) {
        AddError(TEXT("fighter actor not spawned"));
        continue;
      }
      const FHeroSpec* Spec = Find(true, true, C.Name);
      Actor->SetTeam(C.Look, C.Look, ES08TeamColorMode::Absolute);
      FS08BoardFighter F = MakeFighter(C.Id, C.Name, C.bHero, 2, C.Y);
      Actor->ApplyFighter(F, C.Cell, C.Look == ES08TeamSlot::P1, true);
      TestTrue(FString::Printf(TEXT("%s is a v2 figure"), C.Name), Actor->IsHeroV2());
      TestTrue(FString::Printf(TEXT("%s art sculpt (compact tag)"), C.Name), Actor->HasArtSculpt());
      TestFalse(FString::Printf(TEXT("%s is not the Medusa candidate"), C.Name), Actor->HasMedusaCandidate());
      TestFalse(FString::Printf(TEXT("%s is not a blockout"), C.Name), Actor->IsBlockout());
      const USkeletalMeshComponent* Skel = ArtBodyOf(Actor);
      if (!Spec || !Skel || !Actor->IsHeroV2()) {
        Actor->Destroy();
        continue;
      }
      TestTrue(FString::Printf(TEXT("%s ArtBody visible"), C.Name), Skel->IsVisible());
      TestEqual(FString::Printf(TEXT("%s mesh"), C.Name), Skel->GetSkeletalMeshAsset()->GetPathName(),
                MeshPath(*Spec) + TEXT(".") + FPaths::GetBaseFilename(MeshPath(*Spec)));
      const UMaterialInterface* Mi = Skel->GetMaterial(0);
      TestEqual(FString::Printf(TEXT("%s body MI by look %s"), C.Name, S08TeamSlotName(C.Look)),
                Mi ? Mi->GetPathName() : FString(),
                BodyMaterialPath(*Spec, C.Look) + TEXT(".") + FPaths::GetBaseFilename(BodyMaterialPath(*Spec, C.Look)));
      const UStaticMeshComponent* Base = StaticComponentOf(Actor, TEXT("ArtBase"));
      TestTrue(FString::Printf(TEXT("%s pedestal + pedestal MI %s"), C.Name, S08TeamSlotName(C.Look)),
               Base && Base->IsVisible() && Base->GetStaticMesh() &&
                   Base->GetStaticMesh()->GetPathName().StartsWith(PedestalPath(*Spec)) && Base->GetMaterial(0) &&
                   Base->GetMaterial(0)->GetPathName().StartsWith(PedestalMaterialPath(*Spec, C.Look)));
      const float Yaw = FRotator::NormalizeAxis(Skel->GetRelativeRotation().Yaw);
      const float WantYaw = FRotator::NormalizeAxis(FigureYawDeg(C.Cell.Y));
      TestTrue(FString::Printf(TEXT("%s yaw %.1f == %.1f"), C.Name, Yaw, WantYaw), FMath::IsNearlyEqual(Yaw, WantYaw, 0.01f));
      const FVector Face = Skel->GetComponentRotation().RotateVector(FVector::XAxisVector);
      TestTrue(FString::Printf(TEXT("%s faces the centre line (%s)"), C.Name, *Face.ToString()), Face.Y * (-C.Cell.Y) > 0.9 * FMath::Abs(C.Cell.Y));
      TestTrue(FString::Printf(TEXT("%s scale"), C.Name),
               Skel->GetRelativeScale3D().Equals(FVector(FigureScale(*Spec)), 1e-4));
      const float Top = Actor->GetFigureHeightUU();
      AddInfo(FString::Printf(TEXT("%s on the board: yaw %.1f, scale %.4f, figure height %.2f uu"), C.Name, Yaw,
                              Actor->GetHeroV2Scale(), Top));
      TestTrue(FString::Printf(TEXT("%s figure height %.2f = bounds top x scale"), C.Name, Top),
               FMath::IsNearlyEqual(Top, Spec->BoundsTopUU * FigureScale(*Spec), 0.6f));
      // Idle at spawn, then the combat clips; a board re-sync does not restart / cut them.
      TestEqual(FString::Printf(TEXT("%s Idle at spawn"), C.Name), FString(ClipName(Actor->GetHeroClip())), FString(TEXT("Idle")));
      Actor->ApplyFighter(F, C.Cell, C.Look == ES08TeamSlot::P1, true);
      TestEqual(FString::Printf(TEXT("%s Idle after re-sync"), C.Name), FString(ClipName(Actor->GetHeroClip())), FString(TEXT("Idle")));
      Actor->NotifyHeroAnimEvent(EEvent::Attack, 10);
      TestEqual(FString::Printf(TEXT("%s attack -> LungeAttack"), C.Name), FString(ClipName(Actor->GetHeroClip())), FString(TEXT("LungeAttack")));
      Actor->ApplyFighter(F, C.Cell, C.Look == ES08TeamSlot::P1, true);
      TestEqual(FString::Printf(TEXT("%s re-sync keeps the lunge"), C.Name), FString(ClipName(Actor->GetHeroClip())), FString(TEXT("LungeAttack")));
      TestEqual(FString::Printf(TEXT("%s lunge at rate 1 by default"), C.Name), Skel->GetPlayRate(), 1.0f);
      Actor->NotifyHeroAnimEvent(EEvent::ClipFinished, -1);
      TestEqual(FString::Printf(TEXT("%s back to Idle"), C.Name), FString(ClipName(Actor->GetHeroClip())), FString(TEXT("Idle")));
      // DE-025 (SD-49): the combat speed scales the lunge only (fast = rate 2); the next clip is back at rate 1.
      Actor->NotifyHeroAnimEvent(EEvent::Attack, 20, 2.0f);
      TestTrue(FString::Printf(TEXT("%s fast lunge at rate 2"), C.Name),
               Actor->GetHeroClip() == EClip::LungeAttack && FMath::IsNearlyEqual(Skel->GetPlayRate(), 2.0f));
      Actor->NotifyHeroAnimEvent(EEvent::ClipFinished, -1);
      TestEqual(FString::Printf(TEXT("%s Idle after the fast lunge at rate 1"), C.Name), Skel->GetPlayRate(), 1.0f);
      Actor->NotifyHeroAnimEvent(EEvent::Damaged, 11, 2.0f);
      TestEqual(FString::Printf(TEXT("%s damage -> HitReact"), C.Name), FString(ClipName(Actor->GetHeroClip())), FString(TEXT("HitReact")));
      TestEqual(FString::Printf(TEXT("%s HitReact never scaled"), C.Name), Skel->GetPlayRate(), 1.0f);
      TestTrue(FString::Printf(TEXT("%s single-node animation asset set"), C.Name),
               Skel->GetAnimationMode() == EAnimationMode::AnimationSingleNode);
      // Defeat: DeathSettle plays where the fighter stood, the figure is held (visible) and later cues change nothing.
      FS08BoardFighter Dead = F;
      Dead.Health = 0;
      Dead.X = -1;
      Dead.Y = -1;
      const FVector Before = Actor->GetActorLocation();
      Actor->ApplyFighter(Dead, FVector(-9999.0, -9999.0, 0.0), C.Look == ES08TeamSlot::P1, true);
      TestEqual(FString::Printf(TEXT("%s defeated -> DeathSettle"), C.Name), FString(ClipName(Actor->GetHeroClip())), FString(TEXT("DeathSettle")));
      TestTrue(FString::Printf(TEXT("%s death hold keeps the figure"), C.Name), Actor->IsInDeathHold() && !Actor->IsHidden());
      TestTrue(FString::Printf(TEXT("%s stays on its cell while settling"), C.Name), Actor->GetActorLocation().Equals(Before, 0.01));
      Actor->NotifyHeroAnimEvent(EEvent::Damaged, 12);
      Actor->ApplyFighter(Dead, FVector(-9999.0, -9999.0, 0.0), C.Look == ES08TeamSlot::P1, true);
      TestEqual(FString::Printf(TEXT("%s final pose holds"), C.Name), FString(ClipName(Actor->GetHeroClip())), FString(TEXT("DeathSettle")));
      // DE-019 (01 F-09): DeathSettle 875 -> still (hero 300, sidekick 0) -> dissolve (500 / 400) on the DE-011 MIC
      // -> hidden; the old grey-slice hold (DeathSettle + 2.0 s, instant hide) is gone.
      FDeathPlan Plan;
      FString Style;
      if (TestTrue(FString::Printf(TEXT("%s death plan while dying"), C.Name), Actor->GetDeathPlan(Plan, Style))) {
        TestEqual(FString::Printf(TEXT("%s settle = DeathSettle"), C.Name), FMath::RoundToInt(Plan.SettleSeconds * 1000.0f), 875);
        TestEqual(FString::Printf(TEXT("%s still"), C.Name), FMath::RoundToInt(Plan.StillSeconds * 1000.0f), Spec->bHero ? 300 : 0);
        TestEqual(FString::Printf(TEXT("%s dissolve"), C.Name), FMath::RoundToInt(Plan.DissolveSeconds * 1000.0f),
                  Spec->bHero ? 500 : 400);
        TestEqual(FString::Printf(TEXT("%s gone from the fall"), C.Name), FMath::RoundToInt(Plan.GoneSeconds() * 1000.0f),
                  Spec->bHero ? 1675 : 1275);
        TestEqual(FString::Printf(TEXT("%s default style fade"), C.Name), Style, FString(TEXT("fade")));
      }
      const float DissolveStart = Plan.DissolveStartSeconds();
      Actor->AdvanceDeathForTest(DissolveStart - 0.01f);
      TestTrue(FString::Printf(TEXT("%s still: no dissolve yet"), C.Name), !Actor->IsDissolving() && !Actor->IsHidden());
      Actor->AdvanceDeathForTest(DissolveStart + 0.5f * Plan.DissolveSeconds);
      TestTrue(FString::Printf(TEXT("%s dissolving half way"), C.Name),
               Actor->IsDissolving() && FMath::IsNearlyEqual(Actor->GetDissolveProgress(), 0.5f, 1e-3f) && !Actor->IsHidden());
      TestTrue(FString::Printf(TEXT("%s body on the dissolve MIC"), C.Name),
               Skel->GetMaterial(0) && Skel->GetMaterial(0)->GetPathName().StartsWith(DissolveMaterialPath(*Spec, C.Look)));
      Actor->AdvanceDeathForTest(Plan.GoneSeconds());
      TestTrue(FString::Printf(TEXT("%s gone: hidden, death over"), C.Name),
               Actor->IsHidden() && !Actor->IsInDeathHold() && !Actor->IsDissolving() && !Actor->GetDeathPlan(Plan, Style));
      Actor->Destroy();
    }
    // An unmapped hero keeps the legacy grey mannequin path.
    AS08FighterActor* Other = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), Near, FRotator::ZeroRotator);
    if (Other) {
      Other->ApplyFighter(MakeFighter(TEXT("f-0-hero"), TEXT("Sinbad"), true, 2, 2), Near, true, true);
      TestFalse("unmapped hero is not v2", Other->IsHeroV2());
      Other->Destroy();
    }
    // The grey board (-S08GreyBoard, or no registered art profile): v2 on changes nothing.
    AS08FighterActor* Grey = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), Near, FRotator::ZeroRotator);
    if (Grey) {
      Grey->ApplyFighter(MakeFighter(TEXT("f-0-hero"), TEXT("King Arthur"), true, 2, 2), Near, true, false);
      TestFalse("v2 on the grey board: grey slice", Grey->IsHeroV2() || Grey->HasArtFigure());
      Grey->Destroy();
    }
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

// DE-010 (W-26, 01 F-03): one "Contact" notify per LungeAttack at the frame of the clip build profile, none in the
// other clips, clip lengths unchanged (Assets above); without a notify the profile frame is the fallback.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2ContactTest,
    "Unmatched.S08.HeroesV2.Contact LungeAttack carries the Contact notify at the profile frame (DE-010)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2ContactTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  // Build profiles (*-h2anim.json, 24 fps): Arthur k.7 = 292 ms, Merlin k.8 = 333, Medusa k.8 = 333, Harpy k.7 = 292.
  const TMap<FString, float> WantMs = {{TEXT("KingArthur"), 291.667f}, {TEXT("Merlin"), 333.333f},
                                       {TEXT("Medusa"), 333.333f}, {TEXT("Harpy"), 291.667f}};
  const FName Contact(ContactNotifyName);
  for (const FHeroSpec& Spec : Specs()) {
    const float* Want = WantMs.Find(Spec.Key);
    TestNotNull(FString::Printf(TEXT("%s has a contact frame"), Spec.Key), Want);
    if (!Want) continue;
    TestTrue(FString::Printf(TEXT("%s profile contact %.1f ms == %.1f"), Spec.Key, ProfileContactSeconds(Spec) * 1000.0f, *Want),
             FMath::IsNearlyEqual(ProfileContactSeconds(Spec) * 1000.0f, *Want, 0.5f));
    TestEqual(FString::Printf(TEXT("%s fallback without a clip"), Spec.Key), ContactSeconds(Spec, nullptr),
              ProfileContactSeconds(Spec));
    for (const EClip Clip : {EClip::Idle, EClip::LungeAttack, EClip::HitReact, EClip::DeathSettle}) {
      const UAnimSequenceBase* Anim = LoadObject<UAnimSequenceBase>(nullptr, *ClipPath(Spec, Clip));
      TestNotNull(FString::Printf(TEXT("%s %s loads"), Spec.Key, ClipName(Clip)), Anim);
      if (!Anim) continue;
      int32 Count = 0;
      for (const FAnimNotifyEvent& Event : Anim->Notifies) {
        if (Event.NotifyName != Contact) continue;
        ++Count;
        TestTrue(FString::Printf(TEXT("%s %s Contact is a US08ContactAnimNotify"), Spec.Key, ClipName(Clip)),
                 Event.Notify && Event.Notify->IsA<US08ContactAnimNotify>());
      }
      if (Clip != EClip::LungeAttack) {
        TestEqual(FString::Printf(TEXT("%s %s has no Contact notify"), Spec.Key, ClipName(Clip)), Count, 0);
        continue;
      }
      TestEqual(FString::Printf(TEXT("%s LungeAttack has one Contact notify"), Spec.Key), Count, 1);
      const float At = NotifyContactSeconds(Anim);
      AddInfo(FString::Printf(TEXT("%s LungeAttack Contact at %.1f ms (profile %.1f), clip %.3f s"), Spec.Key,
                              At * 1000.0f, ProfileContactSeconds(Spec) * 1000.0f, Anim->GetPlayLength()));
      TestTrue(FString::Printf(TEXT("%s Contact %.1f ms == profile %.1f ms (+-half a frame)"), Spec.Key, At * 1000.0f,
                               ProfileContactSeconds(Spec) * 1000.0f),
               FMath::IsNearlyEqual(At, ProfileContactSeconds(Spec), 0.5f / ClipFps));
      TestTrue(FString::Printf(TEXT("%s Contact inside the clip"), Spec.Key), At > 0.0f && At < Anim->GetPlayLength());
      TestEqual(FString::Printf(TEXT("%s ContactSeconds reads the notify"), Spec.Key), ContactSeconds(Spec, Anim), At);
    }
  }
  return true;
}

// DE-010: the hit tint of M_UM_Figure_v2 (v2.2) is CPD 12, neutral at 0 (a figure without it renders as before).
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2HitTintTest,
    "Unmatched.S08.HeroesV2.HitTint M_UM_Figure_v2 has the CPD hit tint slot, neutral by default (DE-010)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2HitTintTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  const UMaterial* Master = LoadObject<UMaterial>(nullptr, TEXT("/Game/UM/Materials/v2/M_UM_Figure_v2.M_UM_Figure_v2"));
  TestNotNull("M_UM_Figure_v2 loads", Master);
  if (!Master) return false;
#if WITH_EDITORONLY_DATA
  int32 HitTint = 0, OtherOnSlot = 0, Colour = 0;
  for (const UMaterialExpression* Expr : Master->GetExpressions()) {
    if (const UMaterialExpressionScalarParameter* P = Cast<UMaterialExpressionScalarParameter>(Expr)) {
      if (P->ParameterName == FName(HitTintParamName)) {
        ++HitTint;
        TestTrue("CPD_HitTint reads Custom Primitive Data", P->bUseCustomPrimitiveData);
        TestEqual("CPD_HitTint slot", static_cast<int32>(P->PrimitiveDataIndex), HitTintCpdIndex);
        TestEqual("CPD_HitTint default 0 (neutral)", P->DefaultValue, 0.0f);
      } else if (P->bUseCustomPrimitiveData && P->PrimitiveDataIndex == HitTintCpdIndex) {
        ++OtherOnSlot;
      }
    } else if (const UMaterialExpressionVectorParameter* V = Cast<UMaterialExpressionVectorParameter>(Expr)) {
      if (V->ParameterName == TEXT("HitTintColor")) ++Colour;
      if (V->bUseCustomPrimitiveData && V->PrimitiveDataIndex <= HitTintCpdIndex && V->PrimitiveDataIndex + 3 >= HitTintCpdIndex) {
        ++OtherOnSlot;
      }
    }
  }
  TestEqual("one CPD_HitTint parameter", HitTint, 1);
  TestEqual("one HitTintColor parameter", Colour, 1);
  TestEqual("no other CPD parameter on slot 12", OtherOnSlot, 0);
#endif
  float Default = -1.0f;
  TestTrue("CPD_HitTint is a scalar parameter of the master",
           Master->GetScalarParameterDefaultValue(FHashedMaterialParameterInfo(FName(HitTintParamName)), Default));
  TestEqual("CPD_HitTint parameter default 0", Default, 0.0f);
  return true;
}

// DE-011 (W-27, 01 F-09): the death dissolve. M_UM_Figure_v2 stays Opaque with the dissolve behind the static switch
// UseDissolve (off by default, CPD 13 / 14 neutral at 0); every body MI has a Masked dissolve MIC that inherits it and
// only switches the dissolve on; 500 / 400 ms; the fade is the default, the ash candidate only on request.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2DissolveTest,
    "Unmatched.S08.HeroesV2.Dissolve Masked dissolve MICs over the Opaque master, fade by default (DE-011)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2DissolveTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  const UMaterial* Master = LoadObject<UMaterial>(nullptr, TEXT("/Game/UM/Materials/v2/M_UM_Figure_v2.M_UM_Figure_v2"));
  TestNotNull("M_UM_Figure_v2 loads", Master);
  if (!Master) return false;
  TestEqual("the master stays Opaque", static_cast<int32>(Master->BlendMode), static_cast<int32>(BLEND_Opaque));
#if WITH_EDITORONLY_DATA
  TMap<int32, int32> OnSlot;
  int32 Progress = 0, Style = 0, Switches = 0;
  for (const UMaterialExpression* Expr : Master->GetExpressions()) {
    if (const UMaterialExpressionScalarParameter* P = Cast<UMaterialExpressionScalarParameter>(Expr)) {
      if (P->bUseCustomPrimitiveData) OnSlot.FindOrAdd(P->PrimitiveDataIndex)++;
      if (P->ParameterName == FName(DissolveParamName)) {
        ++Progress;
        TestTrue("CPD_Dissolve reads Custom Primitive Data", P->bUseCustomPrimitiveData);
        TestEqual("CPD_Dissolve slot", static_cast<int32>(P->PrimitiveDataIndex), DissolveCpdIndex);
        TestEqual("CPD_Dissolve default 0", P->DefaultValue, 0.0f);
      } else if (P->ParameterName == FName(DissolveStyleParamName)) {
        ++Style;
        TestTrue("CPD_DissolveStyle reads Custom Primitive Data", P->bUseCustomPrimitiveData);
        TestEqual("CPD_DissolveStyle slot", static_cast<int32>(P->PrimitiveDataIndex), DissolveStyleCpdIndex);
        TestEqual("CPD_DissolveStyle default 0 (fade)", P->DefaultValue, 0.0f);
      }
    } else if (const UMaterialExpressionVectorParameter* V = Cast<UMaterialExpressionVectorParameter>(Expr)) {
      if (V->bUseCustomPrimitiveData) {
        for (int32 I = 0; I < 4; ++I) OnSlot.FindOrAdd(V->PrimitiveDataIndex + I)++;
      }
    } else if (const UMaterialExpressionStaticSwitchParameter* W = Cast<UMaterialExpressionStaticSwitchParameter>(Expr)) {
      if (W->ParameterName == FName(DissolveSwitchName)) {
        ++Switches;
        TestFalse("UseDissolve is off by default", W->DefaultValue);
      }
    }
  }
  TestEqual("one CPD_Dissolve parameter", Progress, 1);
  TestEqual("one CPD_DissolveStyle parameter", Style, 1);
  TestTrue("UseDissolve switch nodes (base colour, emissive, opacity mask)", Switches >= 3);
  TestEqual("slot 13 has only CPD_Dissolve", OnSlot.FindRef(DissolveCpdIndex), 1);
  TestEqual("slot 14 has only CPD_DissolveStyle", OnSlot.FindRef(DissolveStyleCpdIndex), 1);
#endif
  // 01 F-09: hero 500 ms, sidekick 400 ms.
  const TMap<FString, float> WantSeconds = {{TEXT("KingArthur"), 0.5f}, {TEXT("Merlin"), 0.4f},
                                            {TEXT("Medusa"), 0.5f}, {TEXT("Harpy"), 0.4f}};
  for (const FHeroSpec& Spec : Specs()) {
    const float* Want = WantSeconds.Find(Spec.Key);
    TestNotNull(FString::Printf(TEXT("%s has a dissolve length"), Spec.Key), Want);
    if (Want) TestEqual(FString::Printf(TEXT("%s dissolve seconds"), Spec.Key), DissolveSeconds(Spec), *Want);
    for (const ES08TeamSlot Look : {ES08TeamSlot::P1, ES08TeamSlot::P2}) {
      const FString BodyPath = BodyMaterialPath(Spec, Look);
      const FString MicPath = DissolveMaterialPath(Spec, Look);
      UMaterialInterface* Body = LoadObject<UMaterialInterface>(nullptr, *BodyPath);
      UMaterialInstanceConstant* Mic = LoadObject<UMaterialInstanceConstant>(nullptr, *MicPath);
      TestNotNull(FString::Printf(TEXT("%s loads"), *BodyPath), Body);
      TestNotNull(FString::Printf(TEXT("%s loads"), *MicPath), Mic);
      if (!Body || !Mic) continue;
      TestTrue(FString::Printf(TEXT("%s is a child of %s"), *MicPath, *BodyPath), Mic->Parent == Body);
      TestEqual(FString::Printf(TEXT("%s body MI stays Opaque"), Spec.Key), static_cast<int32>(Body->GetBlendMode()),
                static_cast<int32>(BLEND_Opaque));
      TestEqual(FString::Printf(TEXT("%s dissolve MIC is Masked"), Spec.Key), static_cast<int32>(Mic->GetBlendMode()),
                static_cast<int32>(BLEND_Masked));
#if WITH_EDITORONLY_DATA
      for (const TCHAR* Name : {DissolveSwitchName, TEXT("UseTeamAccent"), TEXT("UseUV1Metres")}) {
        bool bBody = false, bMic = false;
        FGuid Guid;
        const FHashedMaterialParameterInfo Info{FName(Name)};
        TestTrue(FString::Printf(TEXT("%s %s on the body MI"), Spec.Key, Name),
                 Body->GetStaticSwitchParameterValue(Info, bBody, Guid));
        TestTrue(FString::Printf(TEXT("%s %s on the dissolve MIC"), Spec.Key, Name),
                 Mic->GetStaticSwitchParameterValue(Info, bMic, Guid));
        const bool bDissolveSwitch = FCString::Strcmp(Name, DissolveSwitchName) == 0;
        TestEqual(FString::Printf(TEXT("%s %s: dissolve MIC %d, body %d"), Spec.Key, Name, bMic ? 1 : 0, bBody ? 1 : 0),
                  bMic, bDissolveSwitch ? true : bBody);
        if (bDissolveSwitch) TestFalse(FString::Printf(TEXT("%s body MI keeps the dissolve off"), Spec.Key), bBody);
      }
#endif
    }
  }
  // Style: the fade by default and under reduced motion; the ash candidate only on request.
  TestTrue("default fade", DecideDissolveStyle(false, false) == EDissolveStyle::Fade);
  TestTrue("reduced motion fade", DecideDissolveStyle(false, true) == EDissolveStyle::Fade);
  TestTrue("ash on request", DecideDissolveStyle(true, false) == EDissolveStyle::Ash);
  TestTrue("reduced motion wins over the ash request", DecideDissolveStyle(true, true) == EDissolveStyle::Fade);
  TestEqual("style names", FString(DissolveStyleName(EDissolveStyle::Ash)), FString(TEXT("ash")));
  // One frame: progress clamped, style, pedestal CPD_Fade.
  USkeletalMeshComponent* BodyComp = NewObject<USkeletalMeshComponent>();
  UStaticMeshComponent* BaseComp = NewObject<UStaticMeshComponent>();
  SetDissolve(BodyComp, BaseComp, 1.7f, EDissolveStyle::Ash);
  const TArray<float>& BodyData = BodyComp->GetCustomPrimitiveData().Data;
  const TArray<float>& BaseData = BaseComp->GetCustomPrimitiveData().Data;
  TestTrue("body CPD reaches the style slot", BodyData.Num() > DissolveStyleCpdIndex);
  TestTrue("pedestal CPD reaches the fade slot", BaseData.Num() > PedestalFadeCpdIndex);
  if (BodyData.Num() > DissolveStyleCpdIndex && BaseData.Num() > PedestalFadeCpdIndex) {
    TestEqual("progress clamped to 1", BodyData[DissolveCpdIndex], 1.0f);
    TestEqual("style ash = 1", BodyData[DissolveStyleCpdIndex], 1.0f);
    TestEqual("pedestal fade follows the progress", BaseData[PedestalFadeCpdIndex], 1.0f);
    TestEqual("hit tint untouched", BodyData[HitTintCpdIndex], 0.0f);
  }
  SetDissolve(BodyComp, nullptr, 0.25f, EDissolveStyle::Fade);
  TestEqual("progress 0.25", BodyComp->GetCustomPrimitiveData().Data[DissolveCpdIndex], 0.25f);
  TestEqual("style fade = 0", BodyComp->GetCustomPrimitiveData().Data[DissolveStyleCpdIndex], 0.0f);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2BenchClipPoseTest,
    "Unmatched.S08.HeroesV2.BenchClipPose -BenchClipPose list parser and q resolution (AN-17, VR-17)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2BenchClipPoseTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  // The AN-18 list: the Idle quarters, the LungeAttack / HitReact / DeathSettle key frames.
  const FString Good = TEXT("Idle@q0,q25,q50,q75;LungeAttack@0,2,3,4,5,6,7,8,9,10,11,12,14;HitReact@0,2,4,5,7,8,10;")
                       TEXT("DeathSettle@0,3,6,7,8,9,12,13,16,17,21");
  TArray<FBenchClipPoseSpec> Poses;
  FString Error;
  TestTrue("the AN-18 pose list parses", ParseBenchClipPoses(Good, Poses, Error));
  TestEqual("35 poses", Poses.Num(), 35);
  if (Poses.Num() == 35) {
    TestEqual("pose 0 = Idle q0", static_cast<int32>(Poses[0].Clip), static_cast<int32>(EClip::Idle));
    TestTrue("pose 1 is a quarter", Poses[1].bQuarter);
    TestEqual("pose 1 = q25", Poses[1].Value, 25);
    TestEqual("pose 4 = LungeAttack", static_cast<int32>(Poses[4].Clip), static_cast<int32>(EClip::LungeAttack));
    TestFalse("pose 4 is a frame number", Poses[4].bQuarter);
    TestEqual("LungeAttack k.7", Poses[10].Value, 7);
    TestEqual("the last pose = DeathSettle k.21", Poses[34].Value, 21);
  }
  // Clip names are case-insensitive; one pose per clip block is fine.
  TArray<FBenchClipPoseSpec> One;
  TestTrue("case-insensitive clip", ParseBenchClipPoses(TEXT("lungeattack@7"), One, Error));
  TestEqual("one pose", One.Num(), 1);
  // Errors: every one empties the list (the bench then runs without poses).
  auto Bad = [&](const TCHAR* Text, const TCHAR* What) {
    TArray<FBenchClipPoseSpec> Out;
    FString Err;
    TestFalse(FString::Printf(TEXT("rejected: %s"), What), ParseBenchClipPoses(Text, Out, Err));
    TestTrue(FString::Printf(TEXT("error text of %s"), What), !Err.IsEmpty());
    TestEqual(FString::Printf(TEXT("empty after %s"), What), Out.Num(), 0);
  };
  Bad(TEXT(""), TEXT("empty"));
  Bad(TEXT("Idle@"), TEXT("no frames"));
  Bad(TEXT("Teleport@1"), TEXT("unknown clip"));
  Bad(TEXT("Idle@q101"), TEXT("q over 100"));
  Bad(TEXT("Idle@-2"), TEXT("negative frame"));
  Bad(TEXT("Idle@2,x"), TEXT("bad frame token"));
  Bad(TEXT("Idle@1;Nope@2"), TEXT("bad second block"));
  Bad(TEXT("Idle"), TEXT("no @"));
  // q resolves against the hero's clip length: the Idle lengths 2.0 / 2.333 / 2.5 / 3.0 s (frames 48 / 56 / 60 / 72).
  FBenchClipPoseSpec Q;
  Q.Clip = EClip::Idle;
  Q.bQuarter = true;
  Q.Value = 25;
  const double Epsilon = 1e-4;
  struct FLen { double Seconds; int32 Frame25; };
  const TArray<FLen> Lengths = {{2.0, 12}, {56.0 / 24.0, 14}, {2.5, 15}, {3.0, 18}};
  for (const FLen& L : Lengths) {
    const double T = BenchClipPoseSeconds(Q, L.Seconds);
    TestTrue(FString::Printf(TEXT("q25 of %.3f s = a quarter"), L.Seconds),
             FMath::Abs(T - 0.25 * L.Seconds) < Epsilon);
    TestEqual(FString::Printf(TEXT("q25 frame of %.3f s"), L.Seconds), FMath::RoundToInt(T * ClipFps), L.Frame25);
  }
  // A plain frame is frame / 24; beyond the clip it clamps to the clip end (a pose never loops).
  FBenchClipPoseSpec F;
  F.Clip = EClip::LungeAttack;
  F.Value = 7;
  TestTrue("frame 7 = 7/24 s", FMath::Abs(BenchClipPoseSeconds(F, 14.0 / 24.0) - 7.0 / 24.0) < Epsilon);
  F.Value = 99;
  TestTrue("frame 99 of a 21-frame clip clamps to its length",
           FMath::Abs(BenchClipPoseSeconds(F, 21.0 / 24.0) - 21.0 / 24.0) < Epsilon);
  return true;
}

namespace {
/** AN-31: a fighter row with a label. */
FS08BoardFighter LabeledFighter(const TCHAR* Name, const TCHAR* Label) {
  FS08BoardFighter F;
  F.Id = FString(TEXT("f-")) + Label;
  F.OwnerId = TEXT("owner");
  F.Name = Name;
  F.Label = Label;
  F.bIsHero = false;
  F.Health = 8;
  F.MaxHealth = 8;
  F.X = 1;
  F.Y = 1;
  return F;
}
/** The run's command line plus Extra while in scope (a local copy of the ArtLook test helper). */
struct FCommandLineScope {
  FString Saved;
  explicit FCommandLineScope(const TCHAR* Extra) : Saved(FCommandLine::Get()) {
    FCommandLine::Set(*(Saved + TEXT(" ") + Extra));
  }
  ~FCommandLineScope() { FCommandLine::Set(*Saved); }
};
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2HarpyNumberTest,
    "Unmatched.S08.HeroesV2.HarpyNumber the harpy digit 1..3 - the last label digit, 1 without one (AN-31, VR-07/72)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2HarpyNumberTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  // The number: the last digit of the label, 1 without one, clamped to 1..3 (GD-030, Р-09).
  TestEqual("Harpies 1", HarpyNumber(LabeledFighter(TEXT("Harpies"), TEXT("Harpies 1"))), 1);
  TestEqual("Harpies 2", HarpyNumber(LabeledFighter(TEXT("Harpies"), TEXT("Harpies 2"))), 2);
  TestEqual("Harpies 3", HarpyNumber(LabeledFighter(TEXT("Harpies"), TEXT("Harpies 3"))), 3);
  TestEqual("no digit: 1", HarpyNumber(LabeledFighter(TEXT("Harpies"), TEXT("Harpies"))), 1);
  TestEqual("a digit past 3 clamps to 3", HarpyNumber(LabeledFighter(TEXT("Harpies"), TEXT("Harpies 7"))), 3);
  TestEqual("a 0 digit clamps to 1", HarpyNumber(LabeledFighter(TEXT("Harpies"), TEXT("Harpies 0"))), 1);
  TestEqual("the FIRST digit does not matter - the LAST one wins",
            HarpyNumber(LabeledFighter(TEXT("Harpies"), TEXT("3rd harpy of 2"))), 2);
  TestEqual("a non-harpy also resolves (the caller decides)", HarpyNumber(LabeledFighter(TEXT("Medusa"), TEXT("Medusa"))), 1);
  // The base digit and the HUD portrait badge (VS-2 CP-12, UmHudPanel::SidekickNumber) give the same number to the
  // three harpies (ВР-07: one number in the tag, the badge, the base and the audio key). Without a digit they differ
  // by design (the badge shows none: 0; the base falls back to 1) - a label always carries it in a game.
  for (const TCHAR* Label : {TEXT("Harpies 1"), TEXT("Harpies 2"), TEXT("Harpies 3")}) {
    TestEqual(FString::Printf(TEXT("%s: base digit = HUD badge"), Label),
              HarpyNumber(LabeledFighter(TEXT("Harpies"), Label)), UmHudPanel::SidekickNumber(Label));
  }
  // The actor: the digit components show on a living v2 harpy only, hidden with the rollback flag and on other
  // figures (the text carries the number).
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08HarpyNumberWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  auto Apply = [&](const FS08BoardFighter& F, AS08FighterActor*& OutActor) {
    OutActor = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), FVector(0, -400, 0),
                                                   FRotator::ZeroRotator);
    OutActor->SetTeam(ES08TeamSlot::P1, ES08TeamSlot::P1, ES08TeamColorMode::Absolute);
    OutActor->ApplyFighter(F, FVector(0, -400, 0), true, true);
  };
  AS08FighterActor* Harpy = nullptr;
  Apply(LabeledFighter(TEXT("Harpies"), TEXT("Harpies 2")), Harpy);
  if (Harpy && !Harpy->IsHeroV2()) {
    AddWarning(TEXT("v2 harpy assets missing in this checkout - the actor half of the test is skipped"));
  } else if (Harpy) {
    TestTrue("the disc shows on a living v2 harpy", Harpy->GetBaseDigitDisc()->IsVisible());
    TestTrue("the digit shows", Harpy->GetBaseDigitText()->IsVisible());
    TestEqual("the digit text is the label number", Harpy->GetBaseDigitText()->Text.ToString(), FString(TEXT("2")));
    const FCommandLineScope Legacy(TEXT("-S08BaseDigitLegacy"));
    Harpy->UpdateBaseDigit();
    TestTrue("the rollback flag hides both components",
             !Harpy->GetBaseDigitDisc()->IsVisible() && !Harpy->GetBaseDigitText()->IsVisible());
  }
  AS08FighterActor* Arthur = nullptr;
  Apply(LabeledFighter(TEXT("King Arthur"), TEXT("King Arthur")), Arthur);
  if (Arthur && Arthur->IsHeroV2()) {
    TestTrue("no disc on a non-harpy", !Arthur->GetBaseDigitDisc()->IsVisible());
    TestTrue("no digit on a non-harpy", !Arthur->GetBaseDigitText()->IsVisible());
  }
  if (Harpy) Harpy->Destroy();
  if (Arthur) Arthur->Destroy();
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2BaseDigitPlacementTest,
    "Unmatched.S08.HeroesV2.BaseDigitPlacement flat upright digit on the camera side inside the pedestal top (AN-31, VR-Z1R-03)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2BaseDigitPlacementTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  // The harpy pedestal: top radius 11 uu (the v2 pedestal x the sidekick scale), its top at z 4.
  const float R = 11.0f;
  const float TopZ = 4.0f;
  struct FCase {
    FVector Pedestal;
    FVector Camera;
    double RestOffDeg;  // the figure's rest facing relative to the camera axis
  };
  const TArray<FCase> Cases = {
      {FVector(0, 0, 0), FVector(0, 1342, 1917), 30.0},        // K1 camera, the rest turned +30 to an enemy
      {FVector(-340, -34, 0), FVector(0, 1342, 1917), -45.0},  // left of the board, the rest at -45
      {FVector(300, 250, 0), FVector(-340, 870, 1200), 0.0},   // a K2 focus camera, the rest on the axis
      {FVector(120, -280, 0), FVector(120, 600, 800), 12.0}};
  for (int32 I = 0; I < Cases.Num(); ++I) {
    const FCase& C = Cases[I];
    FVector Axis(C.Camera.X - C.Pedestal.X, C.Camera.Y - C.Pedestal.Y, 0.0);
    Axis.Normalize();
    const double AxisYaw = FMath::RadiansToDegrees(FMath::Atan2(Axis.Y, Axis.X));
    const FBaseDigitPlacement P = BaseDigitPlacement(C.Pedestal, TopZ, R, C.Camera, AxisYaw + C.RestOffDeg);
    const FString Tag = FString::Printf(TEXT("case %d"), I);
    // Sizes: the disc 0.5 x the top diameter (= R), the digit em 0.9 x the disc (cap 0.721 em).
    TestTrue(Tag + TEXT(": disc diameter = 0.5 x the top diameter"), FMath::IsNearlyEqual(P.DiscDiameterUU, R, 1e-3f));
    TestTrue(Tag + TEXT(": cap = 0.9 x disc x the Roboto digit height"),
             FMath::IsNearlyEqual(P.CapUU, 0.9f * R * RobotoDigitPerEm, 1e-3f));
    TestTrue(Tag + TEXT(": the cap reads at K2x1.6 (>= 7 uu)"), P.CapUU >= 7.0f);
    // The disc stays inside the pedestal top: centre distance + disc radius <= R.
    const double Reach = FVector2D(P.DiscCenter - C.Pedestal).Size() + 0.5 * P.DiscDiameterUU;
    TestTrue(FString::Printf(TEXT("%s: the disc inside the top (%.2f <= %.2f)"), *Tag, Reach, R), Reach <= R + 1e-3);
    // On the camera side, 60 deg off the axis, on the side the signed turn names (ВР-Z1R-03: -60 = towards the rest
    // offset - the mirrored side of the wing rule).
    FVector Dir = P.DiscCenter - C.Pedestal;
    Dir.Z = 0.0;
    Dir.Normalize();
    TestTrue(Tag + TEXT(": the disc on the camera side (60 deg off the axis)"),
             FMath::IsNearlyEqual(FVector::DotProduct(Dir, Axis), 0.5, 1e-3));
    const double DiscYawOff = FMath::FindDeltaAngleDegrees(AxisYaw, FMath::RadiansToDegrees(FMath::Atan2(Dir.Y, Dir.X)));
    const double WantOff = (C.RestOffDeg >= 0.0 ? -1.0 : 1.0) * BaseDigitSideTurnDeg;
    TestTrue(FString::Printf(TEXT("%s: the disc on the signed side (%.1f, want %.1f, rest offset %.1f)"), *Tag,
                             DiscYawOff, WantOff, C.RestOffDeg),
             FMath::IsNearlyEqual(DiscYawOff, WantOff, 0.1));
    TestTrue(Tag + TEXT(": -60 = towards the rest offset"), C.RestOffDeg >= 0.0 ? DiscYawOff > 0.0 : DiscYawOff < 0.0);
    // The plate: flat, its bottom 0.1 above the top; the text 0.3 above the plate's top (no z-fight).
    TestTrue(Tag + TEXT(": plate bottom above the top"),
             P.DiscCenter.Z - 0.5 * BaseDigitDiscThicknessUU >= TopZ + 0.1 - 1e-3);
    TestTrue(Tag + TEXT(": the text >= 0.3 uu above the plate"),
             P.TextLocation.Z >= P.DiscCenter.Z + 0.5 * BaseDigitDiscThicknessUU + 0.3 - 1e-3);
    TestTrue(Tag + TEXT(": the text centred on the disc"), FVector2D(P.TextLocation - P.DiscCenter).Size() < 1e-3);
    // The text lies flat (its normal - local X - is +Z) with the glyph top (local Z) away from the camera, and it is
    // not mirrored: the text runs along local -Y, which must be the camera's screen right (Up ^ forward).
    const FRotationMatrix M(P.TextRotation);
    const FVector Normal = M.GetUnitAxis(EAxis::X);
    const FVector GlyphUp = M.GetUnitAxis(EAxis::Z);
    const FVector TextRight = -M.GetUnitAxis(EAxis::Y);
    const FVector CameraRight = FVector::CrossProduct(FVector::UpVector, -Axis).GetSafeNormal();
    TestTrue(FString::Printf(TEXT("%s: the text face normal . Z = %.4f > 0.99"), *Tag, Normal.Z), Normal.Z > 0.99);
    TestTrue(Tag + TEXT(": the glyph top away from the camera"), FVector::DotProduct(GlyphUp, -Axis) > 0.99);
    TestTrue(Tag + TEXT(": not mirrored (the text runs to the camera's right)"),
             FVector::DotProduct(TextRight, CameraRight) > 0.99);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08HeroesV2BaseDigitStatesTest,
    "Unmatched.S08.HeroesV2.BaseDigitStates the digit hides for a Place transfer and from the death dissolve (AN-31, VR-Z1R-03)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08HeroesV2BaseDigitStatesTest::RunTest(const FString&) {
  using namespace S08HeroesV2;
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08BaseDigitStatesWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  const FVector Cell(0, -400, 0);
  AS08FighterActor* Harpy = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass(), Cell, FRotator::ZeroRotator);
  FS08BoardFighter F = LabeledFighter(TEXT("Harpies"), TEXT("Harpies 3"));
  Harpy->SetTeam(ES08TeamSlot::P1, ES08TeamSlot::P1, ES08TeamColorMode::Absolute);
  Harpy->ApplyFighter(F, Cell, true, true);
  if (!Harpy->IsHeroV2()) {
    AddWarning(TEXT("v2 harpy assets missing in this checkout - the digit states test is skipped"));
  } else {
    auto Shown = [Harpy]() { return Harpy->GetBaseDigitDisc()->IsVisible() && Harpy->GetBaseDigitText()->IsVisible(); };
    auto Hidden = [Harpy]() { return !Harpy->GetBaseDigitDisc()->IsVisible() && !Harpy->GetBaseDigitText()->IsVisible(); };
    TestTrue("a living harpy shows the disc and the digit", Shown());
    TestTrue("the digit is drawable (the offline font and the digit material are in this build)",
             Harpy->IsBaseDigitDrawable());
    TestEqual("the digit is the label number", Harpy->GetBaseDigitText()->Text.ToString(), FString(TEXT("3")));
    TestTrue("the digit face is flat (normal . Z > 0.99)",
             Harpy->GetBaseDigitText()->GetComponentTransform().GetUnitAxis(EAxis::X).Z > 0.99);
    const UFont* Font = Harpy->GetBaseDigitText()->Font;
    TestTrue("the digit font is offline (TextRender draws no runtime font)",
             Font && Font->FontCacheType == EFontCacheType::Offline);
    // A Place transfer hides it for the whole transfer; the arrival shows it again.
    FS08MovePlan Place;
    Place.FighterId = F.Id;
    Place.Kind = ES08MoveKind::Place;
    Place.Points = {Cell, Cell + FVector(200, 0, 0)};
    Place.StepMs = 500.0;
    Place.Steps = 1;
    Harpy->PlayMove(Place, FS08MoveAnimParams(), 0);
    TestTrue("Place: moving", Harpy->IsMoving());
    TestTrue("Place: the digit hidden from the start of the transfer", Hidden());
    Harpy->TickMove(250);
    TestTrue("Place: still hidden half way", Hidden());
    Harpy->FinishMove();
    TestTrue("Place: shown again on arrival", Shown());
    // The death: still shown while DeathSettle plays, hidden from the start of the dissolve (sidekick: right after
    // DeathSettle, 01 F-09).
    FS08BoardFighter Dead = F;
    Dead.Health = 0;
    Harpy->ApplyFighter(Dead, Cell + FVector(200, 0, 0), true, true);
    FDeathPlan Plan;
    FString Style;
    if (TestTrue("the harpy dies", Harpy->GetDeathPlan(Plan, Style))) {
      Harpy->AdvanceDeathForTest(Plan.DissolveStartSeconds() + 0.01f);
      TestTrue("death: the dissolve runs", Harpy->IsDissolving());
      TestTrue("death: the digit hidden from the dissolve on", Hidden());
    }
  }
  Harpy->Destroy();
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
