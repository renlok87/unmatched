// ENV-U10 track TRAY automation tests: the shared rocky tray T2 of the map-image boards (S08Diorama.h FitTrayT2 /
// T2MinApronUU, S08EnvLayout::ApplyTrayT2, AS08BoardActor::PlaceDioramaTrayT2).
//   T2Fit      world-free: scale 1 / yaw 0 at (0, offsetY), mismatch reporting, the aprons, ApplyTrayT2 on a layout
//              tray, an apron-only layout, nothing applied and a refused tray;
//   T2Shipped  both shipped env layouts carry exactly the T2 tray (one shared tray, ENV-U10 "единая каменная подложка");
//   T2Assets   the imported SM_TableBase_T2 / MI_TableBase_T2 / T_TableBase_T2_* against the Blender build
//              (art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2); a warning when not imported yet
//              (tools/art/env_kit/ue_import_tray_t2.py);
//   T2Actor    the board actor shows T2 at scale 1 at the layout centre and swaps back to T1 for a grid board.
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.Diorama; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08Diorama.h"
#include "S08EnvLayout.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture2D.h"
#include "Engine/World.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInterface.h"
#include "Misc/AutomationTest.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/BodySetup.h"

namespace S08DioramaT2Test {
// The map plane (1337 x 866 px at 2/3 uu per px) + the 24 uu wooden frame, halved.
const FVector2D MapFrameHalf(445.66667 + 24.0, 288.66667 + 24.0);
const FVector2D T2Top(S08Diorama::T2TopHalfX, S08Diorama::T2TopHalfY);

FString LayoutJson(const FString& Tail) {
  return FString::Printf(TEXT("{\"schema\":\"unmatched.env-layout/1\",\"map\":\"marmoreal\","
                              "\"boardId\":\"c121b47f8d6eb28daccb76d05\",\"props\":[]%s}"),
                         *Tail);
}

/** An applied, valid runtime around a parsed layout document (what S08EnvLayout::Update leaves behind). */
bool AppliedRuntime(const FString& Json, FS08EnvLayoutRuntime& Out, TArray<FString>& Errors) {
  Out = FS08EnvLayoutRuntime();
  if (!Out.Layout.ParseJson(Json, Errors)) return false;
  Out.bApplied = true;
  Out.bLayoutValid = true;
  Out.MapKey = TEXT("marmoreal");
  Out.Status = TEXT("ok");
  return true;
}

FS08BoardModel GridBoard(int32 W, int32 H) {
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

struct FFlagScope {
  explicit FFlagScope(bool bOn) { S08Diorama::SetFlagOverrideForTest(bOn); }
  ~FFlagScope() { S08Diorama::ResetFlagOverrideForTest(); }
};
}  // namespace S08DioramaT2Test

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DioramaT2FitTest,
    "Unmatched.S08.Diorama.T2Fit the shared T2 tray sits at scale 1 on the layout tray and is never stretched",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DioramaT2FitTest::RunTest(const FString&) {
  using namespace S08Diorama;
  using namespace S08DioramaT2Test;
  float Mismatch = -1.0f;
  const FTrayFit Fit = FitTrayT2(T2Top, T2DefaultOffsetY, Mismatch);
  TestEqual("yaw 0", Fit.YawDeg, 0.0f);
  TestTrue(FString::Printf(TEXT("scale %s == 1"), *Fit.Scale.ToString()), Fit.Scale.Equals(FVector::OneVector, 0.0));
  TestTrue(FString::Printf(TEXT("anisotropy %.6f == 1 (no stretch, no waiver)"), Fit.Anisotropy()),
           Fit.Anisotropy() == 1.0);
  TestTrue(FString::Printf(TEXT("location %s == (0,-45)"), *Fit.Location.ToString()),
           Fit.Location.Equals(FVector2D(0.0, -45.0), 1e-6));
  TestTrue(FString::Printf(TEXT("world half %s == the T2 top 780 x 470"), *Fit.WorldHalf.ToString()),
           Fit.WorldHalf.Equals(FVector2D(780.0, 470.0), 1e-6));
  TestTrue(FString::Printf(TEXT("mismatch %.3f == 0"), Mismatch), FMath::IsNearlyZero(Mismatch));
  // A layout asking for another tray (the P1b Marmoreal one): T2 still at scale 1 on its centre, the mismatch reported.
  const FTrayFit Other = FitTrayT2(FVector2D(729.67, 442.67), -40.0f, Mismatch);
  TestTrue("other tray: still scale 1 and the T2 top",
           Other.Scale.Equals(FVector::OneVector, 0.0) && Other.WorldHalf.Equals(T2Top, 1e-6));
  TestTrue(FString::Printf(TEXT("other tray: mismatch %.2f == 50.33"), Mismatch), FMath::IsNearlyEqual(Mismatch, 50.33f, 0.01f));
  TestTrue(FString::Printf(TEXT("other tray: mismatch %.2f > tolerance"), Mismatch), Mismatch > T2MatchToleranceUU);
  TestTrue("other tray: centred on its offset", Other.Location.Equals(FVector2D(0.0, -40.0), 1e-6));
  // Aprons of the map frame inside the T2 top at the shared offset: sides 310.33, far 202.33, near 112.33 (narrowest).
  const float Apron = T2MinApronUU(MapFrameHalf, T2DefaultOffsetY);
  TestTrue(FString::Printf(TEXT("narrowest apron %.3f == 112.333 (near side)"), Apron), FMath::IsNearlyEqual(Apron, 112.333f, 0.01f));
  TestTrue("the frame stays out of the rocky lip band", Apron > T2RimUU);
  TestTrue("a frame wider than the T2 top -> negative apron", T2MinApronUU(FVector2D(800.0, 300.0), 0.0f) < 0.0f);
  // T1 is untouched: the Cobble 5x6 slab keeps yaw -90 / scale 1.
  const FTrayFit Cobble = FitTray(FVector2D(278.0, 328.0));
  TestTrue("T1 Cobble placement unchanged", Cobble.YawDeg == -90.0f && Cobble.Scale.Equals(FVector::OneVector, 1e-3));

  // ApplyTrayT2 on an applied layout with the shared tray (+ the apron it implies): outer half, offsetY, source=layout.
  TArray<FString> Errors;
  FS08EnvLayoutRuntime Rt;
  const FString Apron2 = TEXT(",\"apron\":{\"n\":202.333,\"s\":112.333,\"w\":310.333,\"e\":310.333}");
  TestTrue(TEXT("tray layout parses: ") + FString::Join(Errors, TEXT(" | ")),
           AppliedRuntime(LayoutJson(TEXT(",\"tray\":{\"halfX\":780,\"halfY\":470,\"offsetY\":-45}") + Apron2), Rt, Errors));
  FVector2D Half(1.0, 1.0);
  float OffsetY = 99.0f;
  FString Source = TEXT("default");
  TestTrue("ApplyTrayT2: layout tray accepted", S08EnvLayout::ApplyTrayT2(Rt, MapFrameHalf, Half, OffsetY, Source));
  TestTrue(FString::Printf(TEXT("outer half %s == 780 x 470"), *Half.ToString()), Half.Equals(T2Top, 0.01));
  TestTrue(FString::Printf(TEXT("offsetY %.3f == -45"), OffsetY), FMath::IsNearlyEqual(OffsetY, -45.0f, 0.01f));
  TestEqual("source layout", Source, FString(TEXT("layout")));
  // apron only: the implied tray is the same rectangle
  Errors.Reset();
  TestTrue("apron-only layout parses", AppliedRuntime(LayoutJson(Apron2), Rt, Errors));
  Half = FVector2D(1.0, 1.0);
  OffsetY = 99.0f;
  Source = TEXT("default");
  TestTrue("ApplyTrayT2: apron accepted", S08EnvLayout::ApplyTrayT2(Rt, MapFrameHalf, Half, OffsetY, Source));
  TestTrue(FString::Printf(TEXT("apron: outer half %s == 780 x 470"), *Half.ToString()), Half.Equals(T2Top, 0.01));
  TestTrue(FString::Printf(TEXT("apron: offsetY %.3f == -45"), OffsetY), FMath::IsNearlyEqual(OffsetY, -45.0f, 0.01f));
  TestEqual("source apron", Source, FString(TEXT("apron")));
  // nothing applied (-ArtPreviewNoEnv, no layout): the inputs (the T2 default) stay
  FS08EnvLayoutRuntime None;
  Half = T2Top;
  OffsetY = T2DefaultOffsetY;
  Source = TEXT("default");
  TestFalse("ApplyTrayT2: nothing applied", S08EnvLayout::ApplyTrayT2(None, MapFrameHalf, Half, OffsetY, Source));
  TestTrue("nothing applied: default kept",
           Half.Equals(T2Top, 0.0) && OffsetY == T2DefaultOffsetY && Source == TEXT("default"));
  // a layout tray narrower than the frame is refused: the default stays
  Errors.Reset();
  TestTrue("narrow tray parses", AppliedRuntime(LayoutJson(TEXT(",\"tray\":{\"halfX\":400,\"halfY\":470,\"offsetY\":-45}")),
                                                Rt, Errors));
  TestFalse("ApplyTrayT2: tray not covering the frame refused",
            S08EnvLayout::ApplyTrayT2(Rt, MapFrameHalf, Half, OffsetY, Source));
  TestTrue("refused: default kept", Half.Equals(T2Top, 0.0) && OffsetY == T2DefaultOffsetY && Source == TEXT("default"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DioramaT2ShippedTest,
    "Unmatched.S08.Diorama.T2Shipped both shipped env layouts carry exactly the one shared T2 tray",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DioramaT2ShippedTest::RunTest(const FString&) {
  using namespace S08Diorama;
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped board profiles", Data.LoadFile(FS08BoardArtData::DefaultPath(), Errors))) return false;
  int32 Checked = 0;
  for (const FS08BoardArtProfile& B : Data.Boards) {
    if (B.Surface != ES08BoardSurface::MapImage) continue;
    const FString Key = S08EnvLayout::MapKeyOf(B.Map.Name);
    const FString File = S08EnvLayout::FileFor(S08EnvLayout::DefaultDir(), Key);
    FS08EnvLayout L;
    Errors.Reset();
    if (!TestTrue(FString::Printf(TEXT("%s: layout %s valid (%s)"), *Key, *File, *FString::Join(Errors, TEXT(" | "))),
                  FPaths::FileExists(File) && L.LoadFile(File, Errors))) {
      continue;
    }
    ++Checked;
    const FVector2D Frame = B.Map.FrameHalfUU();
    TestTrue(FString::Printf(TEXT("%s: has a tray"), *Key), L.Tray.bSet);
    float Mismatch = -1.0f;
    FitTrayT2(FVector2D(L.Tray.HalfX, L.Tray.HalfY), L.Tray.OffsetY, Mismatch);
    TestTrue(FString::Printf(TEXT("%s: tray %.2f x %.2f == the T2 top %.0f x %.0f (mismatch %.3f)"), *Key, L.Tray.HalfX,
                             L.Tray.HalfY, T2TopHalfX, T2TopHalfY, Mismatch),
             Mismatch <= T2MatchToleranceUU);
    TestTrue(FString::Printf(TEXT("%s: offsetY %.2f == the shared %.0f"), *Key, L.Tray.OffsetY, T2DefaultOffsetY),
             FMath::IsNearlyEqual(L.Tray.OffsetY, T2DefaultOffsetY, T2MatchToleranceUU));
    if (L.Apron.bSet) {
      const FS08EnvTray Implied = L.Apron.ImpliedTray(Frame);
      TestTrue(FString::Printf(TEXT("%s: apron-implied %.2f x %.2f / %.2f == the T2 tray"), *Key, Implied.HalfX,
                               Implied.HalfY, Implied.OffsetY),
               FMath::IsNearlyEqual(Implied.HalfX, T2TopHalfX, T2MatchToleranceUU) &&
                   FMath::IsNearlyEqual(Implied.HalfY, T2TopHalfY, T2MatchToleranceUU) &&
                   FMath::IsNearlyEqual(Implied.OffsetY, T2DefaultOffsetY, T2MatchToleranceUU));
    }
    const float Apron = T2MinApronUU(Frame, L.Tray.OffsetY);
    TestTrue(FString::Printf(TEXT("%s: narrowest apron %.1f > the lip band %.0f"), *Key, Apron, T2RimUU), Apron > T2RimUU);
    // every prop pivot on the T2 top (the env layout's own outsideTray count uses the same rectangle)
    for (const FS08EnvProp& P : L.Props) {
      TestTrue(FString::Printf(TEXT("%s/%s: pivot %s on the T2 top"), *Key, *P.Id, *P.Loc.ToString()),
               FMath::Abs(P.Loc.X) < T2TopHalfX && FMath::Abs(P.Loc.Y - L.Tray.OffsetY) < T2TopHalfY);
    }
  }
  TestEqual("map-image layouts checked (Marmoreal, Sarpedon)", Checked, 2);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DioramaT2AssetsTest,
    "Unmatched.S08.Diorama.T2Assets imported SM_TableBase_T2 matches the Blender build (flat top, lip, depth, tiling MI)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DioramaT2AssetsTest::RunTest(const FString&) {
  using namespace S08Diorama;
  const FString MeshPkg(T2MeshPath);
  if (!FPackageName::DoesPackageExist(MeshPkg)) {
    AddWarning(FString::Printf(TEXT("%s not imported (tools/art/env_kit/ue_import_tray_t2.py): map-image boards fall back "
                                    "to the T1 placeholder"),
                               T2MeshPath));
    return true;
  }
  UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, T2MeshPath);
  UMaterialInstance* Mi = LoadObject<UMaterialInstance>(nullptr, T2MaterialPath);
  if (!TestTrue("SM_TableBase_T2 and MI_TableBase_T2 load", Mesh && Mi)) return true;
  const FBox Box = Mesh->GetBoundingBox();
  const int32 Tris = Mesh->GetNumTriangles(0);
  AddInfo(FString::Printf(TEXT("SM_TableBase_T2 bounds %s size %s triangles %d slots %d"), *Box.ToString(),
                          *Box.GetSize().ToString(), Tris, Mesh->GetStaticMaterials().Num()));
  // XY: covers the flat top, overhangs it by <= T2MaxOverhangUU, centred on the pivot
  TestTrue(FString::Printf(TEXT("covers the flat top +-%.0f x +-%.0f"), T2TopHalfX, T2TopHalfY),
           Box.Min.X <= -T2TopHalfX && Box.Max.X >= T2TopHalfX && Box.Min.Y <= -T2TopHalfY && Box.Max.Y >= T2TopHalfY);
  TestTrue(FString::Printf(TEXT("overhang <= %.0f uu"), T2MaxOverhangUU),
           Box.Max.X <= T2TopHalfX + T2MaxOverhangUU && Box.Max.Y <= T2TopHalfY + T2MaxOverhangUU &&
               Box.Min.X >= -T2TopHalfX - T2MaxOverhangUU && Box.Min.Y >= -T2TopHalfY - T2MaxOverhangUU);
  TestTrue("XY centred on the pivot (+-1 uu)",
           FMath::Abs(Box.Min.X + Box.Max.X) <= 1.0 && FMath::Abs(Box.Min.Y + Box.Max.Y) <= 1.0);
  // Z: the lip above the flat top stays low, the cliff hangs 120..180 uu below it
  TestTrue(FString::Printf(TEXT("lip top %.2f in [%.0f, %.1f]"), Box.Max.Z, TopZ, T2LipTopZMax + 0.5),
           Box.Max.Z >= TopZ && Box.Max.Z <= T2LipTopZMax + 0.5);
  const double Depth = TopZ - Box.Min.Z;
  TestTrue(FString::Printf(TEXT("depth below the top %.1f in [%.0f, %.0f]"), Depth, T2MinDepthUU, T2MaxDepthUU),
           Depth >= T2MinDepthUU - 0.5 && Depth <= T2MaxDepthUU + 0.5);
  TestTrue(FString::Printf(TEXT("triangles %d in (0, 30000]"), Tris), Tris > 0 && Tris <= 30000);
#if WITH_EDITORONLY_DATA
  TestFalse("Nanite off", Mesh->IsNaniteEnabled());
#endif
  const UBodySetup* Body = Mesh->GetBodySetup();
  TestTrue("no simple collision (decor)", !Body || Body->AggGeom.GetElementCount() == 0);
  const TArray<FStaticMaterial>& Slots = Mesh->GetStaticMaterials();
  TestEqual("one material slot", Slots.Num(), 1);
  TestTrue("slot = MI_TableBase_T2",
           Slots.Num() == 1 && Slots[0].MaterialInterface.Get() == static_cast<UMaterialInterface*>(Mi));
  TestTrue("MI parent M_UM_Figure",
           Mi->Parent && Mi->Parent->GetPathName() == TEXT("/Game/UM/Materials/M_UM_Figure.M_UM_Figure"));
  const TCHAR* const Params[] = {TEXT("BaseColorTexture"), TEXT("NormalTexture"), TEXT("ORMTexture")};
  for (const TCHAR* Param : Params) {
    UTexture* Bound = nullptr;
    const bool bBound = Mi->GetTextureParameterValue(FHashedMaterialParameterInfo(Param), Bound) && Bound &&
                        Bound->GetPathName().StartsWith(TEXT("/Game/PipelineCandidates/TableBase/T2/T_TableBase_T2_"));
    TestTrue(FString::Printf(TEXT("%s bound to a T_TableBase_T2 texture"), Param), bBound);
    // UV0 is a world box projection that tiles (180 uu per repeat): the textures must wrap
    const UTexture2D* Tex2D = Cast<UTexture2D>(Bound);
    TestTrue(FString::Printf(TEXT("%s wraps (tiling UVs)"), Param),
             Tex2D && Tex2D->AddressX == TA_Wrap && Tex2D->AddressY == TA_Wrap);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08DioramaT2ActorTest,
    "Unmatched.S08.Diorama.T2Actor the board actor shows T2 at scale 1 on a map tray and T1 again on a grid board",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08DioramaT2ActorTest::RunTest(const FString&) {
  using namespace S08Diorama;
  using namespace S08DioramaT2Test;
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, TEXT("S08DioramaT2ActorWorld"));
  if (!World) {
    AddError(TEXT("could not create a test world"));
    return true;
  }
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  {
    FFlagScope On(true);
    AS08BoardActor* Actor = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                              FRotator::ZeroRotator);
    if (TestNotNull("board actor spawned", Actor) && TestTrue("tray created", Actor->EnsureDioramaTray(true))) {
      const UStaticMeshComponent* Tray = Actor->GetDioramaTray();
      const bool bImported = FPackageName::DoesPackageExist(FString(T2MeshPath));
      const bool bPlaced = Actor->PlaceDioramaTrayT2(MapFrameHalf, T2Top, T2DefaultOffsetY, TEXT("layout"));
      if (!bImported) {
        AddWarning(FString::Printf(TEXT("%s not imported: PlaceDioramaTrayT2 must refuse and leave T1"), T2MeshPath));
        TestFalse("T2 absent: refused", bPlaced);
        TestTrue("T2 absent: still the T1 mesh",
                 Tray && Tray->GetStaticMesh() && Tray->GetStaticMesh()->GetPathName().StartsWith(MeshPath));
      } else if (TestTrue("T2 placed", bPlaced) && TestNotNull("tray component", Tray)) {
        TestTrue("tray mesh SM_TableBase_T2",
                 Tray->GetStaticMesh() && Tray->GetStaticMesh()->GetPathName().StartsWith(T2MeshPath));
        const UMaterialInterface* Mi = Tray->GetMaterial(0);
        TestTrue("tray MI_TableBase_T2", Mi && Mi->GetPathName().StartsWith(T2MaterialPath));
        TestTrue("visible", Tray->IsVisible());
        TestTrue(FString::Printf(TEXT("location %s == (0,-45,0)"), *Tray->GetComponentLocation().ToString()),
                 Tray->GetComponentLocation().Equals(FVector(0.0, -45.0, 0.0), 1e-3));
        TestTrue(FString::Printf(TEXT("yaw %.3f == 0"), Tray->GetComponentRotation().Yaw),
                 FMath::IsNearlyZero(FRotator::NormalizeAxis(Tray->GetComponentRotation().Yaw), 1e-3));
        TestTrue(FString::Printf(TEXT("scale %s == 1 (never stretched)"), *Tray->GetComponentScale().ToString()),
                 Tray->GetComponentScale().Equals(FVector::OneVector, 0.0));
        const FBox Box = Tray->GetStaticMesh()->GetBoundingBox().TransformBy(Tray->GetComponentTransform());
        AddInfo(FString::Printf(TEXT("T2 world bounds %s"), *Box.ToString()));
        TestTrue(FString::Printf(TEXT("world bounds %s cover the tray x +-780, y -515..425"), *Box.ToString()),
                 Box.Min.X <= -780.0 && Box.Max.X >= 780.0 && Box.Min.Y <= -515.0 && Box.Max.Y >= 425.0);
        TestTrue(FString::Printf(TEXT("the map frame sits inside the flat top (narrowest apron %.1f)"),
                                 T2MinApronUU(MapFrameHalf, T2DefaultOffsetY)),
                 T2MinApronUU(MapFrameHalf, T2DefaultOffsetY) > T2RimUU);
        // A grid art board afterwards: the FitTray placement shows T1 again (Cobble slab: yaw -90, scale 1).
        Actor->PlaceDioramaTray(true, FVector2D(278.0, 328.0), TEXT("cobble-5x6-mesh"));
        TestTrue("grid board: back to SM_TableBase",
                 Tray->GetStaticMesh() && Tray->GetStaticMesh()->GetPathName().StartsWith(MeshPath));
        const UMaterialInterface* T1Mi = Tray->GetMaterial(0);
        TestTrue("grid board: MI_TableBase_Candidate", T1Mi && T1Mi->GetPathName().StartsWith(MaterialPath));
        TestTrue("grid board: at the board centre", Tray->GetComponentLocation().Equals(FVector::ZeroVector, 1e-3));
        // And the map board again: T2 is reused (no second load) at the layout's centre.
        TestTrue("map board again: T2", Actor->PlaceDioramaTrayT2(MapFrameHalf, T2Top, -40.0f, TEXT("layout")) &&
                                            Tray->GetStaticMesh()->GetPathName().StartsWith(T2MeshPath) &&
                                            Tray->GetComponentLocation().Equals(FVector(0.0, -40.0, 0.0), 1e-3));
        Actor->PlaceDioramaTray(false, FVector2D::ZeroVector, TEXT("grey"));
        TestFalse("hidden on a grey board", Tray->IsVisible());
      }
      // A rebuild on a grey grid board keeps the tray hidden (no art data in a test world).
      Actor->Rebuild(GridBoard(5, 6));
      TestFalse("grey board after a rebuild: hidden", Tray && Tray->IsVisible());
      Actor->Destroy();
    }
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
