// Wave 5c-B automation tests: the -ArtPreviewDiorama tray (S08Diorama.h, AS08BoardActor::EnsureDioramaTray /
// PlaceDioramaTray). Fit = pure yaw/scale math on the three art boards; Assets = SM_TableBase / MI_TableBase_Candidate
// against docs/art-pipeline/table-base-report.md; Actor = the board actor creates the tray only with -ArtPreview and
// the flag, NoCollision, hidden on a grey board, placed at (0,0,0) yaw -90 scale 1 under the Cobble 5x6 slab.
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.Diorama; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardModel.h"
#include "S08Diorama.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/MaterialInterface.h"
#include "Misc/AutomationTest.h"

namespace S08DioramaTest {
struct FFlagScope {
  explicit FFlagScope(bool bOn) { S08Diorama::SetFlagOverrideForTest(bOn); }
  ~FFlagScope() { S08Diorama::ResetFlagOverrideForTest(); }
};

FS08BoardModel MakeBoard(int32 W, int32 H) {
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

// World half extent of the ART-005 Cobble slab frame (report: +-278 x +-328 at yaw -90).
const FVector2D CobbleHalf(278.0, 328.0);
constexpr float TilesFrameUU = 24.0f;  // S08BoardActor.cpp ArtFrameUU
}  // namespace S08DioramaTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DioramaFitTest,
    "Unmatched.S08.Diorama.Fit tray yaw and scale keep a 50 uu rim around the three art boards",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DioramaFitTest::RunTest(const FString&) {
  using namespace S08Diorama;
  using namespace S08DioramaTest;
  {
    FFlagScope On(true);
    TestFalse("flag without -ArtPreview: no tray", Enabled(false));
    TestTrue("flag with -ArtPreview: tray", Enabled(true));
  }
  {
    FFlagScope Off(false);
    TestFalse("-ArtPreview without the flag: no tray (previous board)", Enabled(true));
  }
  // Cobble 5x6 mesh: exactly the report placement (yaw -90, scale 1).
  const FTrayFit Cobble = FitTray(CobbleHalf);
  TestEqual("cobble yaw -90 (as the ART005 board)", Cobble.YawDeg, -90.0f);
  TestTrue(FString::Printf(TEXT("cobble scale 1 (%s)"), *Cobble.Scale.ToString()),
           Cobble.Scale.Equals(FVector::OneVector, 1e-4));
  TestTrue("cobble tray half 328 x 378", Cobble.WorldHalf.Equals(FVector2D(328.0, 378.0), 1e-3));
  // Rotation check: mesh half (378, 328) at yaw -90 covers world (328, 378).
  const FBox Rotated = FBox(FVector(-MeshHalfX, -MeshHalfY, BottomZ), FVector(MeshHalfX, MeshHalfY, TopZ))
                           .TransformBy(FTransform(FRotator(0.0f, Cobble.YawDeg, 0.0f)));
  TestTrue(FString::Printf(TEXT("cobble rotated tray %s"), *Rotated.ToString()),
           FMath::IsNearlyEqual(Rotated.Max.X, 328.0, 0.01) && FMath::IsNearlyEqual(Rotated.Max.Y, 378.0, 0.01));
  // 'tiles' art fixtures: sherwood-forest 8x5, t-rex-paddock 7x5.
  struct FCase {
    int32 W, H;
    FVector2D Half;
    float Yaw;
  };
  const FCase Cases[] = {{8, 5, FVector2D(424.0, 274.0), 0.0f}, {7, 5, FVector2D(374.0, 274.0), 0.0f},
                         {5, 6, FVector2D(274.0, 324.0), -90.0f}};
  for (const FCase& C : Cases) {
    const FVector2D Half = TilesFrameHalf(C.W, C.H, FS08BoardModel::CellSizeUU, TilesFrameUU);
    TestTrue(FString::Printf(TEXT("%dx%d tiles frame half %s"), C.W, C.H, *Half.ToString()), Half.Equals(C.Half, 1e-3));
    const FTrayFit Fit = FitTray(Half);
    TestEqual(FString::Printf(TEXT("%dx%d yaw"), C.W, C.H), Fit.YawDeg, C.Yaw);
    const FBox Box = FBox(FVector(-MeshHalfX, -MeshHalfY, BottomZ), FVector(MeshHalfX, MeshHalfY, TopZ))
                         .TransformBy(FTransform(FRotator(0.0f, Fit.YawDeg, 0.0f), FVector::ZeroVector, Fit.Scale));
    AddInfo(FString::Printf(TEXT("%dx%d tiles: yaw %.0f scale %.4f x %.4f, tray %s"), C.W, C.H, Fit.YawDeg, Fit.Scale.X,
                            Fit.Scale.Y, *Box.ToString()));
    TestTrue(FString::Printf(TEXT("%dx%d rim 50 uu on X and Y"), C.W, C.H),
             FMath::IsNearlyEqual(Box.Max.X - Half.X, RimUU, 0.01) && FMath::IsNearlyEqual(Box.Max.Y - Half.Y, RimUU, 0.01));
    TestTrue(FString::Printf(TEXT("%dx%d top stays on Z -3, Z scale 1"), C.W, C.H),
             FMath::IsNearlyEqual(Box.Max.Z, TopZ, 0.01) && Fit.Scale.Z == 1.0);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DioramaAssetsTest,
    "Unmatched.S08.Diorama.Assets SM_TableBase 756x656x150 with top on Z -3 and its candidate MI load",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DioramaAssetsTest::RunTest(const FString&) {
  using namespace S08Diorama;
  UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, MeshPath);
  UMaterialInterface* Mi = LoadObject<UMaterialInterface>(nullptr, MaterialPath);
  TestNotNull("SM_TableBase loads", Mesh);
  TestNotNull("MI_TableBase_Candidate loads", Mi);
  if (!Mesh) return true;
  const FBox Box = Mesh->GetBoundingBox();
  AddInfo(FString::Printf(TEXT("SM_TableBase bounds %s, size %s, slots %d"), *Box.ToString(), *Box.GetSize().ToString(),
                          Mesh->GetStaticMaterials().Num()));
  TestTrue(FString::Printf(TEXT("bounds %s == (-378,-328,-153)..(378,328,-3) +-0.5"), *Box.ToString()),
           Box.Min.Equals(FVector(-MeshHalfX, -MeshHalfY, BottomZ), 0.5) &&
               Box.Max.Equals(FVector(MeshHalfX, MeshHalfY, TopZ), 0.5));
  TestEqual("one material slot", Mesh->GetStaticMaterials().Num(), 1);
  // ART-005 Cobble slab frame at the in-game yaw -90 (S08BoardActor): the tray rim is 50 uu on every side.
  UStaticMesh* Board = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/ArtTests/ART005F/Meshes/SM_ART005_BoardStoneV4_WoodUV"));
  TestNotNull("ART-005 Cobble slab loads", Board);
  if (Board) {
    const FBox B = Board->GetBoundingBox().TransformBy(FTransform(FRotator(0.0f, -90.0f, 0.0f)));
    const FVector2D Half(FMath::Max(-B.Min.X, B.Max.X), FMath::Max(-B.Min.Y, B.Max.Y));
    const FTrayFit Fit = FitTray(Half);
    AddInfo(FString::Printf(TEXT("Cobble slab world %s half %s -> tray yaw %.0f scale %s"), *B.ToString(), *Half.ToString(),
                            Fit.YawDeg, *Fit.Scale.ToString()));
    TestEqual("Cobble slab -> yaw -90", Fit.YawDeg, -90.0f);
    TestTrue(FString::Printf(TEXT("Cobble slab -> scale 1 +-0.01 (%s)"), *Fit.Scale.ToString()),
             Fit.Scale.Equals(FVector::OneVector, 0.01));
    TestTrue(FString::Printf(TEXT("board top %.2f above the tray top -3"), B.Max.Z), B.Max.Z > TopZ);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DioramaActorTest,
    "Unmatched.S08.Diorama.Actor board actor creates the tray only with the flag, NoCollision, under the Cobble slab",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DioramaActorTest::RunTest(const FString&) {
  using namespace S08Diorama;
  using namespace S08DioramaTest;
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08DioramaActorWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  {
    FFlagScope Off(false);
    AS08BoardActor* Actor = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                              FRotator::ZeroRotator);
    TestNotNull("board actor spawned", Actor);
    if (Actor) {
      TestFalse("no flag: EnsureDioramaTray is a no-op", Actor->EnsureDioramaTray(true));
      TestNull("no flag: no tray component", Actor->GetDioramaTray());
      Actor->Destroy();
    }
  }
  {
    FFlagScope On(true);
    AS08BoardActor* Actor = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                              FRotator::ZeroRotator);
    if (Actor) {
      TestFalse("flag without -ArtPreview: no tray", Actor->EnsureDioramaTray(false));
      TestNull("flag without -ArtPreview: no tray component", Actor->GetDioramaTray());
      TestTrue("flag with -ArtPreview: tray created", Actor->EnsureDioramaTray(true));
      const UStaticMeshComponent* Tray = Actor->GetDioramaTray();
      TestNotNull("tray component", Tray);
      if (Tray) {
        TestFalse("tray hidden until an art board is active", Tray->IsVisible());
        TestTrue("tray NoCollision", Tray->GetCollisionEnabled() == ECollisionEnabled::NoCollision);
        TestTrue("tray mesh SM_TableBase", Tray->GetStaticMesh() &&
                                               Tray->GetStaticMesh()->GetPathName().StartsWith(MeshPath));
        const UMaterialInterface* Mi = Tray->GetMaterial(0);
        TestTrue("tray MI_TableBase_Candidate", Mi && Mi->GetPathName().StartsWith(MaterialPath));
        // Grey board (no art data in a test world): Rebuild keeps the tray hidden.
        Actor->Rebuild(MakeBoard(5, 6));
        TestFalse("grey board: tray hidden", Tray->IsVisible());
        // Cobble 5x6 slab placement: (0,0,0), yaw -90, scale 1, top on Z -3, 50 uu rim.
        Actor->PlaceDioramaTray(true, CobbleHalf, TEXT("cobble-5x6-mesh"));
        TestTrue("tray visible on an art board", Tray->IsVisible());
        TestTrue("tray at the board centre", Tray->GetComponentLocation().Equals(FVector::ZeroVector, 1e-3));
        TestTrue(FString::Printf(TEXT("tray yaw %.2f == -90"), Tray->GetComponentRotation().Yaw),
                 FMath::IsNearlyEqual(FRotator::NormalizeAxis(Tray->GetComponentRotation().Yaw), -90.0, 0.01));
        TestTrue("tray scale 1", Tray->GetComponentScale().Equals(FVector::OneVector, 1e-4));
        const FBox Box = Tray->GetStaticMesh()->GetBoundingBox().TransformBy(Tray->GetComponentTransform());
        AddInfo(FString::Printf(TEXT("cobble tray world bounds %s"), *Box.ToString()));
        TestTrue(FString::Printf(TEXT("world bounds %s == (-328,-378,-153)..(328,378,-3) +-0.5"), *Box.ToString()),
                 Box.Min.Equals(FVector(-328.0, -378.0, -153.0), 0.5) && Box.Max.Equals(FVector(328.0, 378.0, -3.0), 0.5));
        // An 8x5 tiles board: yaw 0, the rim follows the wider frame.
        Actor->PlaceDioramaTray(true, TilesFrameHalf(8, 5, FS08BoardModel::CellSizeUU, TilesFrameUU), TEXT("tiles"));
        const FBox Wide = Tray->GetStaticMesh()->GetBoundingBox().TransformBy(Tray->GetComponentTransform());
        AddInfo(FString::Printf(TEXT("8x5 tray world bounds %s"), *Wide.ToString()));
        TestTrue(FString::Printf(TEXT("8x5 bounds %s == (-474,-324,-153)..(474,324,-3) +-0.5"), *Wide.ToString()),
                 Wide.Min.Equals(FVector(-474.0, -324.0, -153.0), 0.5) && Wide.Max.Equals(FVector(474.0, 324.0, -3.0), 0.5));
        Actor->PlaceDioramaTray(false, FVector2D::ZeroVector, TEXT("grey"));
        TestFalse("hidden again", Tray->IsVisible());
      }
      Actor->Destroy();
    } else {
      AddError(TEXT("board actor not spawned"));
    }
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
