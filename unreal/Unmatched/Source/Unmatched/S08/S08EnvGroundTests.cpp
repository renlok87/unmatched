// ENV-MAPS P2 track GROUND automation tests: the themed ground of the environment layouts (S08EnvGround.h).
//   GroundParse    the "ground" section: every field, defaults, 16 rejections, unknown fields ignored
//   GroundStrips   world-free geometry: tray top minus the frame as 4 disjoint strips (area, order, clipping, inset),
//                  the engine-plane transform and the GroundStrip / SplatRect parameter values
//   GroundSpawn    a fake map-image board through S08EnvLayout::Update: 4 plane strips (NoCollision, no shadow, MID
//                  parameters), keep / respawn / clear, a layout without ground, a missing material
//   GroundShipped  Config/ArtBoards/EnvLayouts ground sections against the map-image profiles, and the imported
//                  M_EnvGround / MI_EnvGround_<Map> (tools/art/env_kit/ue_import_env_ground.py; AddWarning if absent)
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.EnvLayout; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08EnvGround.h"
#include "S08EnvLayout.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"

namespace S08EnvGroundTest {
const FVector2D MapHalf(445.66667, 288.66667);                  // 1337 x 866 px at 2/3 uu per px, halved
const FVector2D FrameHalf(445.66667 + 24.0, 288.66667 + 24.0);  // + the 24 uu wooden frame
const TCHAR* const EngineMaterial = TEXT("/Engine/BasicShapes/BasicShapeMaterial");
const TCHAR* const BoardId = TEXT("cidEnvGround");
/** The shared T2 tray of both maps (ENV-U10): halfX 780, halfY 470, offsetY -45 -> x +-780, y -515 .. 425. */
const FBox2D SharedTray(FVector2D(-780.0, -515.0), FVector2D(780.0, 425.0));
const FBox2D SplatRect(FVector2D(-820.0, -560.0), FVector2D(820.0, 470.0));

FString GroundJson(const FString& Body) { return FString::Printf(TEXT(",\"ground\":{%s}"), *Body); }

FString FullGroundBody(const FString& Material) {
  return FString::Printf(TEXT("\"mode\":\"runtime\",\"material\":\"%s\",\"z\":-1,\"frameOverlapUU\":2,\"insetUU\":0,"
                              "\"splatRect\":[-820,-560,820,470],\"splat\":\"art/x.splat.png\",\"splatSha256\":\"00\","
                              "\"notes\":\"test\""),
                         *Material);
}

/** A valid layout on the shared tray: one engine cube west of the frame, no lights, plus Extra (e.g. a ground). */
FString LayoutJson(const FString& Map, const FString& Extra) {
  return FString::Printf(TEXT("{\"schema\":\"unmatched.env-layout/1\",\"map\":\"%s\",\"boardId\":\"%s\","
                              "\"tray\":{\"halfX\":780,\"halfY\":470,\"offsetY\":-45},"
                              "\"props\":[{\"id\":\"cube\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[-600,0,-3]}],"
                              "\"lights\":[]%s}"),
                         *Map, BoardId, *Extra);
}

FString TempDir(const TCHAR* Leaf) {
  const FString Dir = FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::AutomationTransientDir(), TEXT("S08EnvGround"), Leaf));
  IFileManager::Get().DeleteDirectory(*Dir, false, true);
  IFileManager::Get().MakeDirectory(*Dir, true);
  return Dir;
}

bool WriteText(const FString& Path, const FString& Text) {
  return FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

/** Area of the intersection of two rectangles (0 when they only touch). */
double OverlapArea(const FBox2D& A, const FBox2D& B) {
  const double Dx = FMath::Min(A.Max.X, B.Max.X) - FMath::Max(A.Min.X, B.Min.X);
  const double Dy = FMath::Min(A.Max.Y, B.Max.Y) - FMath::Max(A.Min.Y, B.Min.Y);
  return (Dx > 0.0 && Dy > 0.0) ? Dx * Dy : 0.0;
}

bool BoxEquals(const FBox2D& A, const FBox2D& B, double Tol) {
  return A.Min.Equals(B.Min, Tol) && A.Max.Equals(B.Max, Tol);
}

bool Covers(const FBox2D& Outer, const FBox2D& Inner) {
  return Outer.IsInsideOrOn(Inner.Min) && Outer.IsInsideOrOn(Inner.Max);
}

const FVectorParameterValue* FindVector(const UMaterialInstance* Mi, const TCHAR* Name) {
  if (!Mi) return nullptr;
  for (const FVectorParameterValue& V : Mi->VectorParameterValues) {
    if (V.ParameterInfo.Name == FName(Name)) return &V;
  }
  return nullptr;
}

FString PackageOf(const FString& Path) {
  int32 Dot = INDEX_NONE;
  return Path.FindChar(TEXT('.'), Dot) ? Path.Left(Dot) : Path;
}

struct FTestWorld {
  UWorld* World = nullptr;
  explicit FTestWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) {
      FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
      Context.SetCurrentWorld(World);
    }
  }
  ~FTestWorld() {
    if (World) {
      GEngine->DestroyWorldContext(World);
      World->DestroyWorld(false);
    }
  }
  AS08BoardActor* SpawnBoard() const {
    return World ? World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                     FRotator::ZeroRotator)
                 : nullptr;
  }
};

bool Destroyed(const UActorComponent* C) { return !IsValid(C) || C->IsBeingDestroyed() || !C->IsRegistered(); }
}  // namespace S08EnvGroundTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundParseTest,
    "Unmatched.S08.EnvLayout.GroundParse the ground section keeps every field, defaults the optional ones and rejects bad values",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundParseTest::RunTest(const FString&) {
  using namespace S08EnvGroundTest;
  FS08EnvLayout L;
  TArray<FString> Errors;
  const FString Full = GroundJson(
      TEXT("\"mode\":\"runtime\",\"material\":\"/Game/EnvKit/Ground/MI_EnvGround_Marmoreal\",\"z\":-1.5,"
           "\"frameOverlapUU\":3,\"insetUU\":6,\"splatRect\":[-820,-560,820,470],\"splat\":\"x.png\","
           "\"splatSha256\":\"ab\",\"notes\":\"n\",\"futureField\":{\"x\":1}"));
  if (!TestTrue(TEXT("full ground parses: ") + FString::Join(Errors, TEXT(" | ")),
                L.ParseJson(LayoutJson(TEXT("marmoreal"), Full), Errors))) {
    return false;
  }
  const FS08EnvGround& G = L.Ground;
  TestTrue("ground set", G.bSet);
  TestEqual("mode", G.Mode, FString(S08EnvGroundSpec::RuntimeMode));
  TestEqual("material", G.Material, FString(TEXT("/Game/EnvKit/Ground/MI_EnvGround_Marmoreal")));
  TestTrue("z / overlap / inset", G.Z == -1.5f && G.FrameOverlapUU == 3.0f && G.InsetUU == 6.0f);
  TestTrue("splatRect", G.bSplatRect && BoxEquals(G.SplatRect, SplatRect, 1e-9));
  TestEqual("the props of the same layout still parse", L.Props.Num(), 1);
  // minimal: the optional fields take their defaults
  Errors.Reset();
  TestTrue(TEXT("minimal ground parses: ") + FString::Join(Errors, TEXT(" | ")),
           L.ParseJson(LayoutJson(TEXT("sarpedon"),
                                  GroundJson(TEXT("\"mode\":\"runtime\",\"material\":\"/Game/EnvKit/Ground/MI_X.MI_X\""))),
                       Errors));
  TestTrue("defaults: z -1, overlap 2, inset 0, no splat rect",
           L.Ground.bSet && L.Ground.Z == S08EnvGroundSpec::DefaultZ &&
               L.Ground.FrameOverlapUU == S08EnvGroundSpec::DefaultFrameOverlapUU && L.Ground.InsetUU == 0.0f &&
               !L.Ground.bSplatRect);
  // absent: no ground; a re-parse resets a previous one
  Errors.Reset();
  TestTrue("layout without ground parses", L.ParseJson(LayoutJson(TEXT("marmoreal"), FString()), Errors));
  TestFalse("no ground section -> not set", L.Ground.bSet);

  const FString Mode = TEXT("\"mode\":\"runtime\",");
  const FString Mat = TEXT("\"material\":\"/Game/EnvKit/Ground/MI_X\"");
  struct FCase {
    const TCHAR* Name;
    FString Extra;
    const TCHAR* Expect;  // substring of one error
  };
  const FCase Cases[] = {
      {TEXT("ground a number"), TEXT(",\"ground\":3"), TEXT("ground is not an object")},
      {TEXT("ground an array"), TEXT(",\"ground\":[]"), TEXT("ground is not an object")},
      {TEXT("mode missing"), GroundJson(Mat), TEXT("ground: mode")},
      {TEXT("mode mesh"), GroundJson(TEXT("\"mode\":\"mesh\",") + Mat), TEXT("ground: mode")},
      {TEXT("material missing"), GroundJson(TEXT("\"mode\":\"runtime\"")), TEXT("ground: material")},
      {TEXT("material without a root"), GroundJson(Mode + TEXT("\"material\":\"Game/EnvKit/MI_X\"")),
       TEXT("ground: material")},
      {TEXT("material with a space"), GroundJson(Mode + TEXT("\"material\":\"/Game/Env Kit/MI_X\"")),
       TEXT("ground: material")},
      {TEXT("z at the tray top"), GroundJson(Mode + Mat + TEXT(",\"z\":-3")), TEXT("ground: z")},
      {TEXT("z at the map plane"), GroundJson(Mode + Mat + TEXT(",\"z\":-0.5")), TEXT("ground: z")},
      {TEXT("z a string"), GroundJson(Mode + Mat + TEXT(",\"z\":\"-1\"")), TEXT("ground: z")},
      {TEXT("frameOverlapUU negative"), GroundJson(Mode + Mat + TEXT(",\"frameOverlapUU\":-1")),
       TEXT("ground: frameOverlapUU")},
      {TEXT("frameOverlapUU 25"), GroundJson(Mode + Mat + TEXT(",\"frameOverlapUU\":25")),
       TEXT("ground: frameOverlapUU")},
      {TEXT("insetUU negative"), GroundJson(Mode + Mat + TEXT(",\"insetUU\":-2")), TEXT("ground: insetUU")},
      {TEXT("splatRect with 3 numbers"), GroundJson(Mode + Mat + TEXT(",\"splatRect\":[0,0,1]")),
       TEXT("ground: splatRect")},
      {TEXT("splatRect inverted"), GroundJson(Mode + Mat + TEXT(",\"splatRect\":[10,0,-10,5]")),
       TEXT("ground: splatRect")},
      {TEXT("splatRect with a string"), GroundJson(Mode + Mat + TEXT(",\"splatRect\":[\"0\",0,1,1]")),
       TEXT("ground: splatRect")},
  };
  for (const FCase& C : Cases) {
    FS08EnvLayout Bad;
    TArray<FString> CaseErrors;
    const bool bOk = Bad.ParseJson(LayoutJson(TEXT("marmoreal"), C.Extra), CaseErrors);
    TestFalse(FString::Printf(TEXT("%s: the whole layout is rejected"), C.Name), bOk);
    const FString All = FString::Join(CaseErrors, TEXT(" | "));
    TestTrue(FString::Printf(TEXT("%s: error mentions '%s' (%s)"), C.Name, C.Expect, *All), All.Contains(C.Expect));
    TestFalse(FString::Printf(TEXT("%s: ground not set"), C.Name), Bad.Ground.bSet);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundStripsTest,
    "Unmatched.S08.EnvLayout.GroundStrips tray top minus the frame as 4 disjoint strips; plane transform and MID parameters",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundStripsTest::RunTest(const FString&) {
  using namespace S08EnvGroundTest;
  const FBox2D Outer = S08EnvGround::OuterRect(SharedTray, 0.0f);
  TestTrue("inset 0: outer = tray top", BoxEquals(Outer, SharedTray, 1e-9));
  const FBox2D Hole = S08EnvGround::HoleRect(FrameHalf, 2.0f);
  TestTrue(FString::Printf(TEXT("hole = frame - 2 uu %s"), *Hole.ToString()),
           BoxEquals(Hole, FBox2D(FVector2D(-467.66667, -310.66667), FVector2D(467.66667, 310.66667)), 1e-3));
  const TArray<FBox2D> S = S08EnvGround::Strips(Outer, Hole);
  if (!TestEqual("4 strips", S.Num(), 4)) return false;
  TestTrue(TEXT("N: far side, full width ") + S[0].ToString(),
           BoxEquals(S[0], FBox2D(FVector2D(-780.0, -515.0), FVector2D(780.0, -310.66667)), 1e-3));
  TestTrue(TEXT("S: near side, full width ") + S[1].ToString(),
           BoxEquals(S[1], FBox2D(FVector2D(-780.0, 310.66667), FVector2D(780.0, 425.0)), 1e-3));
  TestTrue(TEXT("W: between N and S ") + S[2].ToString(),
           BoxEquals(S[2], FBox2D(FVector2D(-780.0, -310.66667), FVector2D(-467.66667, 310.66667)), 1e-3));
  TestTrue(TEXT("E: between N and S ") + S[3].ToString(),
           BoxEquals(S[3], FBox2D(FVector2D(467.66667, -310.66667), FVector2D(780.0, 310.66667)), 1e-3));
  double Sum = 0.0;
  for (int32 I = 0; I < S.Num(); ++I) {
    Sum += S[I].GetArea();
    TestTrue(FString::Printf(TEXT("strip %d inside the tray top"), I), Covers(Outer, S[I]));
    TestEqual(FString::Printf(TEXT("strip %d stays out of the hole"), I), OverlapArea(S[I], Hole), 0.0);
    for (int32 J = I + 1; J < S.Num(); ++J) {
      TestEqual(FString::Printf(TEXT("strips %d / %d disjoint"), I, J), OverlapArea(S[I], S[J]), 0.0);
    }
  }
  const double Want = Outer.GetArea() - Hole.GetArea();
  AddInfo(FString::Printf(TEXT("ground area %.0f uu2 = tray %.0f - hole %.0f"), Sum, Outer.GetArea(), Hole.GetArea()));
  TestTrue("strips cover exactly tray - hole", FMath::IsNearlyEqual(Sum, Want, Want * 1e-9));
  // inset shrinks the outer rectangle only
  const FBox2D Inset = S08EnvGround::OuterRect(SharedTray, 10.0f);
  TestTrue("inset 10", BoxEquals(Inset, FBox2D(FVector2D(-770.0, -505.0), FVector2D(770.0, 415.0)), 1e-9));
  const TArray<FBox2D> SI = S08EnvGround::Strips(Inset, Hole);
  TestTrue("inset: 4 strips, N starts at -505", SI.Num() == 4 && FMath::IsNearlyEqual(SI[0].Min.Y, -505.0));
  // degenerate cases
  TestEqual("hole covering the tray: no strip",
            S08EnvGround::Strips(Outer, FBox2D(FVector2D(-1000.0, -1000.0), FVector2D(1000.0, 1000.0))).Num(), 0);
  const TArray<FBox2D> NoCut = S08EnvGround::Strips(Outer, FBox2D(FVector2D(2000.0, 2000.0), FVector2D(2100.0, 2100.0)));
  TestTrue("hole outside the tray: the tray itself", NoCut.Num() == 1 && BoxEquals(NoCut[0], Outer, 1e-9));
  TestEqual("invalid tray: no strip", S08EnvGround::Strips(FBox2D(ForceInit), Hole).Num(), 0);
  const TArray<FBox2D> Short =
      S08EnvGround::Strips(FBox2D(FVector2D(-780.0, -515.0), FVector2D(780.0, 300.0)), Hole);
  TestEqual("tray short of the near frame edge: N, W, E only (hole clipped)", Short.Num(), 3);
  // the engine plane (100 x 100, local (-50,-50) = UV (0,0)) on a strip
  const FTransform T = S08EnvGround::StripTransform(S[2], -1.0f);
  TestTrue(TEXT("plane corner (-50,-50) -> strip min at z -1 ") + T.TransformPosition(FVector(-50.0, -50.0, 0.0)).ToString(),
           T.TransformPosition(FVector(-50.0, -50.0, 0.0)).Equals(FVector(S[2].Min.X, S[2].Min.Y, -1.0), 1e-3));
  TestTrue("plane corner (50,50) -> strip max",
           T.TransformPosition(FVector(50.0, 50.0, 0.0)).Equals(FVector(S[2].Max.X, S[2].Max.Y, -1.0), 1e-3));
  TestTrue("no rotation, z scale 1", T.GetRotation().Equals(FQuat::Identity) && FMath::IsNearlyEqual(T.GetScale3D().Z, 1.0));
  // GroundStrip = (min, size): M_EnvGround's P = GroundStrip.xy + UV * GroundStrip.zw hits the strip corners
  const FLinearColor P = S08EnvGround::RectParam(S[0]);
  TestTrue(TEXT("GroundStrip of N ") + P.ToString(),
           FMath::IsNearlyEqual(P.R, -780.0f, 1e-3f) && FMath::IsNearlyEqual(P.G, -515.0f, 1e-3f) &&
               FMath::IsNearlyEqual(P.B, 1560.0f, 1e-3f) && FMath::IsNearlyEqual(P.A, 204.33333f, 1e-2f));
  TestTrue("UV (1,1) -> strip max", FMath::IsNearlyEqual(P.R + P.B, static_cast<float>(S[0].Max.X), 1e-3f) &&
                                        FMath::IsNearlyEqual(P.G + P.A, static_cast<float>(S[0].Max.Y), 1e-2f));
  // the trace line
  FS08EnvGround G;
  G.bSet = true;
  G.Mode = S08EnvGroundSpec::RuntimeMode;
  G.Material = TEXT("/Game/EnvKit/Ground/MI_EnvGround_Marmoreal");
  FS08EnvGroundStats St;
  St.Status = TEXT("missing-material");
  St.Outer = Outer;
  St.Hole = Hole;
  const FString Line = S08EnvGround::TraceLine(TEXT("marmoreal"), G, St);
  AddInfo(Line);
  TestTrue("trace line", Line.StartsWith(TEXT("ARTPREVIEW envlayout ground map=marmoreal mode=runtime strips=0 material=/Game/EnvKit/Ground/MI_EnvGround_Marmoreal")) &&
                             Line.EndsWith(TEXT("status=missing-material")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundSpawnTest,
    "Unmatched.S08.EnvLayout.GroundSpawn fake map-image board: 4 plane strips with MID parameters, keep / respawn / clear, missing material",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundSpawnTest::RunTest(const FString&) {
  using namespace S08EnvGroundTest;
  FTestWorld W(TEXT("S08EnvGroundSpawn"));
  if (!TestNotNull("test world", W.World)) return false;
  AS08BoardActor* Actor = W.SpawnBoard();
  if (!TestNotNull("board actor", Actor)) return false;
  USceneComponent* Root = Actor->GetRootComponent();
  UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, S08EnvGroundSpec::PlaneMeshPath);
  UMaterialInterface* Parent = LoadObject<UMaterialInterface>(nullptr, EngineMaterial);
  if (!TestNotNull("engine plane", Plane) || !TestNotNull("engine material", Parent)) return false;
  const FString Dir = TempDir(TEXT("Spawn"));
  const FString File = S08EnvLayout::FileFor(Dir, TEXT("envground"));
  const FString WithGround = LayoutJson(TEXT("envground"), GroundJson(FullGroundBody(EngineMaterial)));
  TestTrue("write layout", WriteText(File, WithGround));
  FS08EnvLayoutRequest Req;
  Req.bEnabled = true;
  Req.bMapImageActive = true;
  Req.ProfileId = TEXT("envmap");
  Req.MapKey = TEXT("envground");
  Req.RoomBoardId = BoardId;
  Req.ProfileBoardIds = {FString(BoardId)};
  Req.MapHalf = MapHalf;
  Req.FrameHalf = FrameHalf;
  Req.Dir = Dir;
  FS08EnvLayoutRuntime Rt;
  TArray<TObjectPtr<UStaticMeshComponent>> Props;
  TArray<TObjectPtr<UPointLightComponent>> Lights;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  if (!TestTrue("layout applied and valid", Rt.bApplied && Rt.bLayoutValid && Rt.Status == TEXT("ok"))) return false;
  TestEqual("the prop still spawns (ground components are not props)", Props.Num(), 1);
  const FBox2D Top = S08EnvLayout::TrayTopRect(&Rt.Layout, FrameHalf, FVector2D::ZeroVector);
  TestTrue(TEXT("tray top = the shared tray ") + Top.ToString(), BoxEquals(Top, SharedTray, 0.01));
  const TArray<FBox2D> Want = S08EnvGround::Strips(S08EnvGround::OuterRect(Top, 0.0f), S08EnvGround::HoleRect(FrameHalf, 2.0f));
  AddInfo(S08EnvGround::TraceLine(Req.MapKey, Rt.Layout.Ground, Rt.GroundStats));
  TestEqual("ground status ok", Rt.GroundStats.Status, FString(TEXT("ok")));
  TestEqual("4 strips (stats)", Rt.GroundStats.Strips, 4);
  TestTrue("splat rect covers the tray", Rt.GroundStats.bSplatCoversOuter);
  if (!TestEqual("4 ground components", Rt.Ground.Num(), 4) || Want.Num() != 4) return false;
  double Area = 0.0;
  for (int32 I = 0; I < Rt.Ground.Num(); ++I) {
    UStaticMeshComponent* C = Rt.Ground[I].Get();
    if (!TestNotNull(FString::Printf(TEXT("strip %d alive"), I), C)) continue;
    const FString N = C->GetName();
    TestTrue(N + TEXT(": registered under the board root, owned by the actor"),
             C->IsRegistered() && C->GetAttachParent() == Root && C->GetOwner() == Actor);
    TestTrue(N + TEXT(": the engine plane"), C->GetStaticMesh() == Plane);
    TestTrue(N + TEXT(": NoCollision"), C->GetCollisionEnabled() == ECollisionEnabled::NoCollision);
    TestFalse(N + TEXT(": no navigation"), C->CanEverAffectNavigation());
    TestFalse(N + TEXT(": no overlap events"), C->GetGenerateOverlapEvents());
    TestFalse(N + TEXT(": casts no shadow"), static_cast<bool>(C->CastShadow));
    TestFalse(N + TEXT(": not in the props array"), Props.Contains(C));
    const FTransform T = S08EnvGround::StripTransform(Want[I], -1.0f);
    TestTrue(N + TEXT(": relative location ") + C->GetRelativeLocation().ToString(),
             C->GetRelativeLocation().Equals(T.GetLocation(), 1e-3));
    TestTrue(N + TEXT(": relative scale ") + C->GetRelativeScale3D().ToString(),
             C->GetRelativeScale3D().Equals(T.GetScale3D(), 1e-5));
    TestTrue(N + TEXT(": z -1 (between the tray top -3 and the map plane -0.5)"),
             FMath::IsNearlyEqual(C->GetRelativeLocation().Z, -1.0, 1e-6));
    UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(C->GetMaterial(0));
    if (TestNotNull(N + TEXT(": MID"), Mid)) {
      TestTrue(N + TEXT(": MID parent = the layout material"), Mid->Parent == Parent);
      const FVectorParameterValue* Strip = FindVector(Mid, S08EnvGroundSpec::ParamGroundStrip);
      TestTrue(N + TEXT(": GroundStrip = the strip (min, size)"),
               Strip && Strip->ParameterValue.Equals(S08EnvGround::RectParam(Want[I]), 1e-3f));
      const FVectorParameterValue* Rect = FindVector(Mid, S08EnvGroundSpec::ParamSplatRect);
      TestTrue(N + TEXT(": SplatRect = the layout splatRect (min, size)"),
               Rect && Rect->ParameterValue.Equals(FLinearColor(-820.0f, -560.0f, 1640.0f, 1030.0f), 1e-3f));
    }
    Area += Want[I].GetArea();
  }
  TestTrue("area in the stats", FMath::IsNearlyEqual(Rt.GroundStats.AreaUU2, Area, 1e-6 * Area));
  // the same layout again: the same components
  UStaticMeshComponent* First = Rt.Ground[0].Get();
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("same layout again: the same ground (no respawn)", Rt.Ground.Num() == 4 && Rt.Ground[0].Get() == First &&
                                                                  !Destroyed(First));
  // the ground section removed: the strips go, the prop stays
  TestTrue("rewrite without ground", WriteText(File, LayoutJson(TEXT("envground"), FString())));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("no ground section: strips cleared", Rt.Ground.Num() == 0 && Destroyed(First));
  TestEqual("no ground section: status off", Rt.GroundStats.Status, FString(TEXT("off")));
  TestEqual("no ground section: the prop respawned", Props.Num(), 1);
  // a material that was never imported: no strip, the layout itself is fine
  TestTrue("rewrite with a missing material",
           WriteText(File, LayoutJson(TEXT("envground"),
                                      GroundJson(FullGroundBody(TEXT("/Game/EnvKit/Ground/MI_EnvGround_NoSuchTest"))))));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("missing material: layout valid, prop spawned", Rt.bLayoutValid && Props.Num() == 1);
  TestTrue("missing material: no strip", Rt.Ground.Num() == 0 && Rt.GroundStats.Strips == 0);
  TestEqual("missing material: status", Rt.GroundStats.Status, FString(TEXT("missing-material")));
  // back to the ground, then a board change clears it
  TestTrue("rewrite with ground", WriteText(File, WithGround));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  UStaticMeshComponent* Last = Rt.Ground.Num() ? Rt.Ground[0].Get() : nullptr;
  TestTrue("ground back", Rt.Ground.Num() == 4 && Last != nullptr);
  Req.bMapImageActive = false;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("grid / grey board: ground cleared", Rt.Ground.Num() == 0 && Destroyed(Last) && Props.Num() == 0);
  Actor->Destroy();
  IFileManager::Get().DeleteDirectory(*FPaths::Combine(FPaths::AutomationTransientDir(), TEXT("S08EnvGround")), false, true);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundShippedTest,
    "Unmatched.S08.EnvLayout.GroundShipped shipped ground sections cover the tray round the frame; imported M_EnvGround and MI_EnvGround_Map",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundShippedTest::RunTest(const FString&) {
  using namespace S08EnvGroundTest;
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped board profiles", Data.LoadFile(FS08BoardArtData::DefaultPath(), Errors))) return false;
  int32 Checked = 0, Imported = 0;
  for (const FS08BoardArtProfile& B : Data.Boards) {
    if (B.Surface != ES08BoardSurface::MapImage) continue;
    const FString Key = S08EnvLayout::MapKeyOf(B.Map.Name);
    const FString File = S08EnvLayout::FileFor(S08EnvLayout::DefaultDir(), Key);
    FS08EnvLayout L;
    Errors.Reset();
    if (!FPaths::FileExists(File) || !L.LoadFile(File, Errors)) {
      AddWarning(FString::Printf(TEXT("%s: no valid layout %s (%s)"), *Key, *File, *FString::Join(Errors, TEXT(" | "))));
      continue;
    }
    if (!L.Ground.bSet) {
      AddWarning(FString::Printf(TEXT("%s: the layout has no ground section yet (tools/art/env_kit/ground_splat.py --write-layouts)"), *Key));
      continue;
    }
    ++Checked;
    const FS08EnvGround& G = L.Ground;
    TestEqual(Key + TEXT(": mode runtime"), G.Mode, FString(S08EnvGroundSpec::RuntimeMode));
    TestEqual(Key + TEXT(": material MI_EnvGround_<Map>"), PackageOf(G.Material),
              FString(S08EnvGroundSpec::MaterialRoot) + TEXT("MI_EnvGround_") + B.Map.Name);
    TestTrue(Key + TEXT(": z between the tray top and the map plane"),
             G.Z > S08EnvGroundSpec::MinZ && G.Z < S08EnvGroundSpec::MaxZ);
    const FBox2D Top = S08EnvLayout::TrayTopRect(&L, B.Map.FrameHalfUU(), B.Map.TrayOffsetUU);
    const FBox2D Outer = S08EnvGround::OuterRect(Top, G.InsetUU);
    const TArray<FBox2D> S = S08EnvGround::Strips(Outer, S08EnvGround::HoleRect(B.Map.FrameHalfUU(), G.FrameOverlapUU));
    AddInfo(FString::Printf(TEXT("%s: tray top %s -> %d strips; splatRect %s"), *Key, *Top.ToString(), S.Num(),
                            *G.SplatRect.ToString()));
    TestEqual(Key + TEXT(": 4 strips round the frame"), S.Num(), 4);
    TestTrue(Key + TEXT(": splatRect set and covering the tray top"), G.bSplatRect && Covers(G.SplatRect, Outer));
    const FString Pkg = PackageOf(G.Material);
    if (!FPackageName::DoesPackageExist(Pkg)) {
      AddWarning(FString::Printf(TEXT("%s not imported (tools/art/env_kit/ue_import_env_ground.py): the map's ground stays off"), *Pkg));
      continue;
    }
    ++Imported;
    UMaterialInstance* Mi = LoadObject<UMaterialInstance>(nullptr, *G.Material);
    if (!TestNotNull(Key + TEXT(": MI loads"), Mi)) continue;
    TestTrue(Key + TEXT(": MI parent M_EnvGround"),
             Mi->Parent && Mi->Parent->GetPathName() == TEXT("/Game/EnvKit/Ground/M_EnvGround.M_EnvGround"));
    TArray<FString> TextureParams = {TEXT("Splat")};
    for (int32 I = 0; I < 4; ++I) {
      for (const TCHAR* K : {TEXT("BC"), TEXT("N"), TEXT("ORMH")}) TextureParams.Add(FString::Printf(TEXT("L%d_%s"), I, K));
    }
    for (const FString& Name : TextureParams) {
      UTexture* Bound = nullptr;
      TestTrue(FString::Printf(TEXT("%s: %s bound"), *Key, *Name),
               Mi->GetTextureParameterValue(FHashedMaterialParameterInfo(*Name), Bound) && Bound != nullptr);
      if (Name == TEXT("Splat") && Bound) {
        TestTrue(Key + TEXT(": splat linear RGBA8 (TC_VectorDisplacementmap)"),
                 !Bound->SRGB && Bound->CompressionSettings == TC_VectorDisplacementmap);
      }
    }
    FLinearColor Rect;
    TestTrue(Key + TEXT(": MI SplatRect = the layout splatRect"),
             Mi->GetVectorParameterValue(FHashedMaterialParameterInfo(S08EnvGroundSpec::ParamSplatRect), Rect) &&
                 Rect.Equals(S08EnvGround::RectParam(G.SplatRect), 0.01f));
  }
  AddInfo(FString::Printf(TEXT("shipped ground sections checked: %d, imported materials: %d"), Checked, Imported));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
