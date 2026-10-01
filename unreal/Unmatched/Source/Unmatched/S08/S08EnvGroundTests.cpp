// ENV-MAPS P2 track GROUND automation tests: the themed ground of the environment layouts (S08EnvGround.h).
//   GroundParse    the "ground" section: every field, defaults, 16 rejections, unknown fields ignored
//   GroundStrips   world-free geometry: tray top minus the frame as 4 disjoint strips (area, order, clipping, inset),
//                  the engine-plane transform and the GroundStrip / SplatRect parameter values
//   GroundSpawn    a fake map-image board through S08EnvLayout::Update: 4 plane strips (NoCollision, no shadow, MID
//                  parameters), keep / respawn / clear, a layout without ground, a missing material
//   GroundShipped  Config/ArtBoards/EnvLayouts ground sections against the map-image profiles, and the imported
//                  M_EnvGround / MI_EnvGround_<Map> (tools/art/env_kit/ue_import_env_ground.py; AddWarning if absent);
//                  P4: the shipped waterfalls at the near tray edge and the imported M_EnvWaterfall / MI_EnvWaterfall_<Map>
//   GroundWaterfallParse     P4 "waterfalls": every field, defaults, 17 rejections (the whole layout is invalid)
//   GroundWaterfallGeometry  P4 world-free card / spill transforms (corners, normal, v down the card), FallCard, trace
//   GroundWaterfallSpawn     P4 fake map-image board: strips + card + spill (MID FallCard, NoCollision, no shadow), a
//                            fall without spill, a missing waterfall material (skipped, strips stay)
// P5 track B (lane K meshes, Sarpedon):
//   GroundMeshParse     waterfalls[].mesh and the ground "sea": every field, defaults, rejections (the whole layout is
//                       invalid), null = none
//   GroundMeshGeometry  world-free: the piece transform (yaw 90: local +X -> board +Y), sheet / foam FallCard values, the
//                       trace tail only for a ground with mesh pieces (every older line unchanged)
//   GroundMeshSpawn     fake map-image board with engine meshes: sheet + foam + lip instead of the card, spill kept, sea
//                       ring; the card fallback without the sheet mesh, a lip without its material skipped, sea statuses
//   GroundShipped       (extended) the shipped Sarpedon mesh pieces / sea at the near tray edge / under the tray and the
//                       imported M_EnvSea / MI_EnvSea_<Map> / SM_Env_S_* (warnings while not imported)
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.EnvLayout; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08Diorama.h"
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

/** P4: one "waterfalls" entry (the shipped Sarpedon numbers by default). */
FString FallJson(const FString& Id, const FString& Material, const FString& Extra = FString()) {
  return FString::Printf(TEXT("{\"id\":\"%s\",\"material\":\"%s\",\"x0\":-241,\"x1\":-47,\"y\":457,"
                              "\"topZ\":2.5,\"dropUU\":230,\"spillUU\":60%s}"),
                         *Id, *Material, *Extra);
}

FString GroundWithFalls(const FString& Material, const FString& Falls) {
  return GroundJson(FullGroundBody(Material) + TEXT(",\"waterfalls\":[") + Falls + TEXT("]"));
}

/** P5 track B: a waterfall "mesh" object (engine shapes as the lane K pieces by default). */
FString FallMeshJson(const FString& Sheet = TEXT("/Engine/BasicShapes/Cube"),
                     const FString& LipMaterial = FString(EngineMaterial), const FString& Extra = FString()) {
  return FString::Printf(TEXT(",\"mesh\":{\"sheet\":\"%s\",\"foam\":\"/Engine/BasicShapes/Cylinder\","
                              "\"lip\":\"/Engine/BasicShapes/Cone\",\"lipMaterial\":\"%s\",\"loc\":[-144.1,425,0],"
                              "\"yawDeg\":90,\"sheetCard\":[193.8,185.231],\"foamCards\":[[261.34,70],[243.97,76]]%s}"),
                         *Sheet, *LipMaterial, *Extra);
}

/** P5 track B: a ground "sea" object. */
FString SeaJson(const FString& Mesh = TEXT("/Engine/BasicShapes/Plane"), const FString& Material = FString(EngineMaterial),
                const FString& Loc = TEXT("[0,-45,-172]")) {
  return FString::Printf(TEXT(",\"sea\":{\"mesh\":\"%s\",\"material\":\"%s\",\"loc\":%s,\"yawDeg\":0}"), *Mesh,
                         *Material, *Loc);
}
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
                             Line.EndsWith(TEXT("falls=0/0 fallCards=0 status=missing-material")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundWaterfallParseTest,
    "Unmatched.S08.EnvLayout.GroundWaterfallParse the waterfalls of the ground section keep every field, default topZ / spillUU and reject bad entries",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundWaterfallParseTest::RunTest(const FString&) {
  using namespace S08EnvGroundTest;
  const FString Mat = TEXT("/Game/EnvKit/Ground/MI_EnvWaterfall_Sarpedon");
  FS08EnvLayout L;
  TArray<FString> Errors;
  const FString Two = FallJson(TEXT("fall-s"), Mat, TEXT(",\"futureField\":[1]")) + TEXT(",") +
                      TEXT("{\"id\":\"fall-2\",\"material\":\"/Engine/BasicShapes/BasicShapeMaterial\",\"x0\":10,"
                           "\"x1\":30.5,\"y\":440,\"dropUU\":120}");
  if (!TestTrue(TEXT("two waterfalls parse: ") + FString::Join(Errors, TEXT(" | ")),
                L.ParseJson(LayoutJson(TEXT("sarpedon"), GroundWithFalls(EngineMaterial, Two)), Errors))) {
    return false;
  }
  if (!TestEqual("two entries", L.Ground.Waterfalls.Num(), 2)) return false;
  const FS08EnvWaterfall& A = L.Ground.Waterfalls[0];
  TestTrue("entry 0: id / material", A.Id == TEXT("fall-s") && A.Material == Mat);
  TestTrue("entry 0: numbers", A.X0 == -241.0f && A.X1 == -47.0f && A.Y == 457.0f && A.TopZ == 2.5f &&
                                   A.DropUU == 230.0f && A.SpillUU == 60.0f);
  const FS08EnvWaterfall& B = L.Ground.Waterfalls[1];
  TestTrue("entry 1: defaults topZ 2.5, spill 0", B.TopZ == S08EnvGroundSpec::DefaultFallTopZ && B.SpillUU == 0.0f &&
                                                      B.X1 == 30.5f && B.DropUU == 120.0f);
  TestTrue("the strips' fields still parse", L.Ground.bSet && L.Ground.bSplatRect);
  Errors.Reset();
  TestTrue("null waterfalls = none",
           L.ParseJson(LayoutJson(TEXT("sarpedon"), GroundJson(FullGroundBody(EngineMaterial) + TEXT(",\"waterfalls\":null"))),
                       Errors) &&
               L.Ground.Waterfalls.Num() == 0);
  Errors.Reset();
  TestTrue("empty waterfalls = none",
           L.ParseJson(LayoutJson(TEXT("sarpedon"), GroundWithFalls(EngineMaterial, FString())), Errors) &&
               L.Ground.Waterfalls.Num() == 0);
  Errors.Reset();
  TestTrue("a re-parse without waterfalls forgets them",
           L.ParseJson(LayoutJson(TEXT("sarpedon"), GroundJson(FullGroundBody(EngineMaterial))), Errors) &&
               L.Ground.Waterfalls.Num() == 0);

  struct FCase {
    const TCHAR* Name;
    FString Falls;        // the array body, or the whole value when bRaw
    bool bRaw;
    const TCHAR* Expect;  // substring of one error
  };
  const FString F = FallJson(TEXT("f"), Mat);
  const FCase Cases[] = {
      {TEXT("not an array"), TEXT("{\"id\":\"f\"}"), true, TEXT("ground: waterfalls is not an array")},
      {TEXT("five entries"), FString::Join(TArray<FString>{FallJson(TEXT("a"), Mat), FallJson(TEXT("b"), Mat),
                                                             FallJson(TEXT("c"), Mat), FallJson(TEXT("d"), Mat),
                                                             FallJson(TEXT("e"), Mat)},
                                           TEXT(",")),
       false, TEXT("entries (max 4)")},
      {TEXT("entry a number"), TEXT("3"), false, TEXT("waterfalls[0] is not an object")},
      {TEXT("id missing"), TEXT("{\"material\":\"/Game/X\",\"x0\":0,\"x1\":1,\"y\":0,\"dropUU\":5}"), false,
       TEXT(": id")},
      {TEXT("duplicate id"), F + TEXT(",") + F, false, TEXT("waterfalls[1]: id")},
      {TEXT("material without a root"), FallJson(TEXT("f"), TEXT("Game/X")), false, TEXT(": material")},
      {TEXT("x0 a string"), TEXT("{\"id\":\"f\",\"material\":\"/Game/X\",\"x0\":\"0\",\"x1\":1,\"y\":0,\"dropUU\":5}"),
       false, TEXT("x0 / x1 / y must be numbers")},
      {TEXT("y missing"), TEXT("{\"id\":\"f\",\"material\":\"/Game/X\",\"x0\":0,\"x1\":1,\"dropUU\":5}"), false,
       TEXT("x0 / x1 / y must be numbers")},
      {TEXT("x1 <= x0"), TEXT("{\"id\":\"f\",\"material\":\"/Game/X\",\"x0\":5,\"x1\":5,\"y\":0,\"dropUU\":5}"),
       false, TEXT("x1 - x0")},
      {TEXT("width 2500"), TEXT("{\"id\":\"f\",\"material\":\"/Game/X\",\"x0\":-1250,\"x1\":1250,\"y\":0,\"dropUU\":5}"),
       false, TEXT("x1 - x0")},
      {TEXT("y 6000"), TEXT("{\"id\":\"f\",\"material\":\"/Game/X\",\"x0\":0,\"x1\":1,\"y\":6000,\"dropUU\":5}"),
       false, TEXT("x1 - x0")},
      {TEXT("dropUU missing"), TEXT("{\"id\":\"f\",\"material\":\"/Game/X\",\"x0\":0,\"x1\":1,\"y\":0}"), false,
       TEXT("dropUU")},
      {TEXT("dropUU 0"), TEXT("{\"id\":\"f\",\"material\":\"/Game/X\",\"x0\":0,\"x1\":1,\"y\":0,\"dropUU\":0}"),
       false, TEXT("dropUU")},
      {TEXT("dropUU 1500"), TEXT("{\"id\":\"f\",\"material\":\"/Game/X\",\"x0\":0,\"x1\":1,\"y\":0,\"dropUU\":1500}"),
       false, TEXT("dropUU")},
      {TEXT("topZ 25"), FallJson(TEXT("f"), Mat, TEXT(",\"topZ\":25")), false, TEXT("topZ")},
      {TEXT("spillUU negative"), FallJson(TEXT("f"), Mat, TEXT(",\"spillUU\":-1")), false, TEXT("spillUU")},
      {TEXT("spillUU 250"), FallJson(TEXT("f"), Mat, TEXT(",\"spillUU\":250")), false, TEXT("spillUU")},
  };
  for (const FCase& C : Cases) {
    const FString Ground = C.bRaw ? GroundJson(FullGroundBody(EngineMaterial) + TEXT(",\"waterfalls\":") + C.Falls)
                                  : GroundWithFalls(EngineMaterial, C.Falls);
    FS08EnvLayout Bad;
    TArray<FString> CaseErrors;
    const bool bOk = Bad.ParseJson(LayoutJson(TEXT("sarpedon"), Ground), CaseErrors);
    TestFalse(FString::Printf(TEXT("%s: the whole layout is rejected"), C.Name), bOk);
    const FString All = FString::Join(CaseErrors, TEXT(" | "));
    TestTrue(FString::Printf(TEXT("%s: error mentions '%s' (%s)"), C.Name, C.Expect, *All), All.Contains(C.Expect));
    TestFalse(FString::Printf(TEXT("%s: ground not set"), C.Name), Bad.Ground.bSet);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundWaterfallGeometryTest,
    "Unmatched.S08.EnvLayout.GroundWaterfallGeometry the waterfall card hangs from topZ facing the K1 camera, the spill lies on the lip; FallCard values",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundWaterfallGeometryTest::RunTest(const FString&) {
  FS08EnvWaterfall Fall;
  Fall.Id = TEXT("fall-s");
  Fall.X0 = -241.0f;
  Fall.X1 = -47.0f;
  Fall.Y = 457.0f;
  Fall.TopZ = 2.5f;
  Fall.DropUU = 230.0f;
  Fall.SpillUU = 60.0f;
  // the engine plane: 100 x 100 at scale 1, normal +Z, UV (0,0) at local (-50,-50), u along +X, v along +Y
  const FTransform Card = S08EnvGround::FallCardTransform(Fall);
  const FVector TopLeft = Card.TransformPosition(FVector(-50.0, -50.0, 0.0));
  const FVector BottomRight = Card.TransformPosition(FVector(50.0, 50.0, 0.0));
  TestTrue(TEXT("card UV (0,0) = (x0, y, topZ) ") + TopLeft.ToString(), TopLeft.Equals(FVector(-241.0, 457.0, 2.5), 1e-3));
  TestTrue(TEXT("card UV (1,1) = (x1, y, topZ - drop) ") + BottomRight.ToString(),
           BottomRight.Equals(FVector(-47.0, 457.0, 2.5 - 230.0), 1e-3));
  const FVector Normal = Card.TransformVectorNoScale(FVector::UpVector);
  TestTrue(TEXT("card faces +Y (the K1 camera) ") + Normal.ToString(), Normal.Equals(FVector(0.0, 1.0, 0.0), 1e-6));
  TestTrue("card: v runs down (local +Y -> -Z)",
           Card.TransformVectorNoScale(FVector(0.0, 1.0, 0.0)).Equals(FVector(0.0, 0.0, -1.0), 1e-6));
  TestTrue("card: u runs +X", Card.TransformVectorNoScale(FVector(1.0, 0.0, 0.0)).Equals(FVector(1.0, 0.0, 0.0), 1e-6));
  TestTrue("card: a proper rotation (u x v = the normal)",
           (Card.TransformVectorNoScale(FVector(1.0, 0.0, 0.0)) ^ Card.TransformVectorNoScale(FVector(0.0, 1.0, 0.0)))
               .Equals(Normal, 1e-6));
  const FTransform Spill = S08EnvGround::FallSpillTransform(Fall);
  TestTrue("spill UV (0,0) = (x0, y - spill, topZ)",
           Spill.TransformPosition(FVector(-50.0, -50.0, 0.0)).Equals(FVector(-241.0, 397.0, 2.5), 1e-3));
  TestTrue("spill UV (1,1) = (x1, y, topZ): it meets the card's top edge",
           Spill.TransformPosition(FVector(50.0, 50.0, 0.0)).Equals(FVector(-47.0, 457.0, 2.5), 1e-3));
  TestTrue("spill: flat, facing up", Spill.TransformVectorNoScale(FVector::UpVector).Equals(FVector::UpVector, 1e-6));
  const FLinearColor CardParam = S08EnvGround::FallCardParam(Fall, false);
  const FLinearColor SpillParam = S08EnvGround::FallCardParam(Fall, true);
  TestTrue(TEXT("FallCard (card) = (194, 230, 0, 0) ") + CardParam.ToString(),
           CardParam.Equals(FLinearColor(194.0f, 230.0f, S08EnvGroundSpec::FallKindCard, 0.0f), 1e-3f));
  TestTrue(TEXT("FallCard (spill) = (194, 60, 1, 0) ") + SpillParam.ToString(),
           SpillParam.Equals(FLinearColor(194.0f, 60.0f, S08EnvGroundSpec::FallKindSpill, 0.0f), 1e-3f));
  TestTrue("the T2 lip stays under the spill", Fall.TopZ > S08Diorama::T2LipTopZMax);
  // trace: falls spawned / declared, cards
  FS08EnvGround G;
  G.bSet = true;
  G.Mode = S08EnvGroundSpec::RuntimeMode;
  G.Material = TEXT("/Game/EnvKit/Ground/MI_EnvGround_Sarpedon");
  G.Waterfalls.Add(Fall);
  FS08EnvGroundStats St;
  St.Status = TEXT("ok");
  St.Strips = 4;
  St.Falls = 1;
  St.FallCards = 2;
  const FString Line = S08EnvGround::TraceLine(TEXT("sarpedon"), G, St);
  AddInfo(Line);
  TestTrue("trace line carries falls=1/1 fallCards=2", Line.Contains(TEXT(" falls=1/1 fallCards=2 status=ok")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundWaterfallSpawnTest,
    "Unmatched.S08.EnvLayout.GroundWaterfallSpawn fake map-image board: strips plus waterfall card and spill planes, a fall without spill, a missing waterfall material",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundWaterfallSpawnTest::RunTest(const FString&) {
  using namespace S08EnvGroundTest;
  FTestWorld W(TEXT("S08EnvGroundWaterfallSpawn"));
  if (!TestNotNull("test world", W.World)) return false;
  AS08BoardActor* Actor = W.SpawnBoard();
  if (!TestNotNull("board actor", Actor)) return false;
  USceneComponent* Root = Actor->GetRootComponent();
  UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, S08EnvGroundSpec::PlaneMeshPath);
  UMaterialInterface* Parent = LoadObject<UMaterialInterface>(nullptr, EngineMaterial);
  if (!TestNotNull("engine plane", Plane) || !TestNotNull("engine material", Parent)) return false;
  const FString Dir = TempDir(TEXT("Waterfall"));
  const FString File = S08EnvLayout::FileFor(Dir, TEXT("envwater"));
  TestTrue("write layout", WriteText(File, LayoutJson(TEXT("envwater"),
                                                       GroundWithFalls(EngineMaterial, FallJson(TEXT("fall-s"), EngineMaterial)))));
  FS08EnvLayoutRequest Req;
  Req.bEnabled = true;
  Req.bMapImageActive = true;
  Req.ProfileId = TEXT("envmap");
  Req.MapKey = TEXT("envwater");
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
  AddInfo(S08EnvGround::TraceLine(Req.MapKey, Rt.Layout.Ground, Rt.GroundStats));
  TestEqual("ground status ok", Rt.GroundStats.Status, FString(TEXT("ok")));
  TestTrue("4 strips, 1 fall, 2 cards, none missing", Rt.GroundStats.Strips == 4 && Rt.GroundStats.Falls == 1 &&
                                                          Rt.GroundStats.FallCards == 2 && Rt.GroundStats.FallsMissing == 0);
  if (!TestEqual("6 ground components (4 strips + card + spill)", Rt.Ground.Num(), 6)) return false;
  const FS08EnvWaterfall& Fall = Rt.Layout.Ground.Waterfalls[0];
  for (int32 I = 4; I < 6; ++I) {
    const bool bSpill = I == 5;
    UStaticMeshComponent* C = Rt.Ground[I].Get();
    if (!TestNotNull(FString::Printf(TEXT("fall part %d alive"), I), C)) continue;
    const FString N = C->GetName();
    TestTrue(N + TEXT(": named after the fall"), N.StartsWith(bSpill ? TEXT("EnvWaterfall_fall_s_Spill")
                                                                      : TEXT("EnvWaterfall_fall_s_Card")));
    TestTrue(N + TEXT(": registered under the board root"), C->IsRegistered() && C->GetAttachParent() == Root);
    TestTrue(N + TEXT(": the engine plane"), C->GetStaticMesh() == Plane);
    TestTrue(N + TEXT(": NoCollision, no shadow, no navigation"),
             C->GetCollisionEnabled() == ECollisionEnabled::NoCollision && !C->CastShadow &&
                 !C->CanEverAffectNavigation());
    const FTransform Want = bSpill ? S08EnvGround::FallSpillTransform(Fall) : S08EnvGround::FallCardTransform(Fall);
    TestTrue(N + TEXT(": relative transform ") + C->GetRelativeTransform().ToString(),
             C->GetRelativeTransform().Equals(Want, 1e-3));
    UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(C->GetMaterial(0));
    if (TestNotNull(N + TEXT(": MID"), Mid)) {
      TestTrue(N + TEXT(": MID parent = the fall material"), Mid->Parent == Parent);
      const FVectorParameterValue* Card = FindVector(Mid, S08EnvGroundSpec::ParamFallCard);
      TestTrue(N + TEXT(": FallCard"), Card && Card->ParameterValue.Equals(S08EnvGround::FallCardParam(Fall, bSpill), 1e-3f));
    }
  }
  // a fall without spill: one card
  TestTrue("rewrite: no spill",
           WriteText(File, LayoutJson(TEXT("envwater"),
                                      GroundWithFalls(EngineMaterial, FallJson(TEXT("fall-s"), EngineMaterial,
                                                                               TEXT(",\"spillUU\":0"))))));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("no spill: 4 strips + 1 card", Rt.Ground.Num() == 5 && Rt.GroundStats.FallCards == 1 && Rt.GroundStats.Falls == 1);
  // a waterfall material that was never imported: the fall is skipped, the strips stay
  TestTrue("rewrite: missing waterfall material",
           WriteText(File, LayoutJson(TEXT("envwater"),
                                      GroundWithFalls(EngineMaterial,
                                                      FallJson(TEXT("fall-s"), TEXT("/Game/EnvKit/Ground/MI_EnvWaterfall_NoSuchTest"))))));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("missing fall material: strips only, counted", Rt.Ground.Num() == 4 && Rt.GroundStats.Falls == 0 &&
                                                               Rt.GroundStats.FallsMissing == 1 &&
                                                               Rt.GroundStats.Status == TEXT("ok"));
  // a grid / grey board clears everything
  Req.bMapImageActive = false;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestEqual("grid / grey board: no ground, no fall", Rt.Ground.Num(), 0);
  Actor->Destroy();
  IFileManager::Get().DeleteDirectory(*FPaths::Combine(FPaths::AutomationTransientDir(), TEXT("S08EnvGround")), false, true);
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
    // P4 waterfalls: in front of the near tray edge (within the T2 overhang + 40 uu), over the tray width, the spill
    // starting on the tray top, above the T2 lip; their MI imported -> parent M_EnvWaterfall with the ripple bound
    for (const FS08EnvWaterfall& Fall : G.Waterfalls) {
      const FString Id = Key + TEXT(" waterfall ") + Fall.Id;
      AddInfo(FString::Printf(TEXT("%s: x %.1f..%.1f y %.1f topZ %.1f drop %.0f spill %.0f"), *Id, Fall.X0, Fall.X1,
                              Fall.Y, Fall.TopZ, Fall.DropUU, Fall.SpillUU));
      TestEqual(Id + TEXT(": material MI_EnvWaterfall_<Map>"), PackageOf(Fall.Material),
                FString(S08EnvGroundSpec::MaterialRoot) + TEXT("MI_EnvWaterfall_") + B.Map.Name);
      TestTrue(Id + TEXT(": at the near tray edge"), Fall.Y >= Top.Max.Y && Fall.Y <= Top.Max.Y + 40.0);
      TestTrue(Id + TEXT(": within the tray width"), Fall.X0 >= Top.Min.X && Fall.X1 <= Top.Max.X);
      TestTrue(Id + TEXT(": the spill starts on the tray top"),
               Fall.SpillUU > 0.0f && Fall.Y - Fall.SpillUU < Top.Max.Y && Fall.Y - Fall.SpillUU > Top.Max.Y - 120.0);
      TestTrue(Id + TEXT(": above the T2 lip"), Fall.TopZ > S08Diorama::T2LipTopZMax);
      if (Fall.Mesh.bSet) {
        // P5 track B: the lane K pieces at (fall centre, near tray edge, 0), out of the tray (yaw 90), the lip in the
        // map's T2b MI; the sheet as wide as the fall
        const FS08EnvWaterfallMesh& M = Fall.Mesh;
        const FString Folder = FString(S08EnvGroundSpec::MaterialRoot) + B.Map.Name + TEXT("/");
        TestTrue(Id + TEXT(": mesh paths under /Game/EnvKit/Ground/<Map>/"),
                 M.Sheet == Folder + TEXT("SM_Env_S_Waterfall") && M.Foam == Folder + TEXT("SM_Env_S_WaterfallFoam") &&
                     (M.Lip.IsEmpty() || M.Lip == Folder + TEXT("SM_Env_S_WaterfallLip")));
        TestTrue(Id + TEXT(": lip material = MI_TableBase_T2b_<Map>"),
                 M.Lip.IsEmpty() || M.LipMaterial == S08Diorama::T2bMapMaterialPath(B.Map.Name));
        TestTrue(Id + TEXT(": pieces at the near tray edge, under the fall centre ") + M.Loc.ToString(),
                 FMath::IsNearlyEqual(M.Loc.Y, Top.Max.Y, 0.05) &&
                     FMath::IsNearlyEqual(M.Loc.X, (Fall.X0 + Fall.X1) * 0.5, 0.05) && M.Loc.Z == 0.0);
        TestTrue(Id + TEXT(": yaw 90 (local +X out of the tray)"), FMath::IsNearlyEqual(M.YawDeg, 90.0f));
        TestTrue(Id + TEXT(": the sheet is as wide as the fall"),
                 FMath::IsNearlyEqual(M.SheetCard.X, static_cast<double>(Fall.X1 - Fall.X0), 0.05));
        for (const FString& Mesh : {M.Sheet, M.Foam, M.Lip}) {
          if (!Mesh.IsEmpty() && !FPackageName::DoesPackageExist(PackageOf(Mesh))) {
            AddWarning(FString::Printf(TEXT("%s not imported (tools/art/env_kit/ue_import_env_ground.py): %s"), *Mesh,
                                       Mesh == M.Sheet ? TEXT("the plane card stays") : TEXT("the piece is skipped")));
          }
        }
      }
      if (!FPackageName::DoesPackageExist(PackageOf(Fall.Material))) {
        AddWarning(FString::Printf(TEXT("%s not imported (tools/art/env_kit/ue_import_env_ground.py): the fall stays off"),
                                   *PackageOf(Fall.Material)));
        continue;
      }
      UMaterialInstance* FallMi = LoadObject<UMaterialInstance>(nullptr, *Fall.Material);
      if (!TestNotNull(Id + TEXT(": MI loads"), FallMi)) continue;
      TestTrue(Id + TEXT(": MI parent M_EnvWaterfall"),
               FallMi->Parent && FallMi->Parent->GetPathName() == TEXT("/Game/EnvKit/Ground/M_EnvWaterfall.M_EnvWaterfall"));
      UTexture* Ripple = nullptr;
      TestTrue(Id + TEXT(": WaterRippleN bound"),
               FallMi->GetTextureParameterValue(FHashedMaterialParameterInfo(TEXT("WaterRippleN")), Ripple) && Ripple);
    }
    if (G.Sea.bSet) {
      // P5 track B: the sea ring under the tray centre, below the tray top and above the bottom of either shared tray
      // (T2 / T2b), so its inner edge (40 uu inside the tray outline) hides under the cliff
      const FS08EnvSea& Sea = G.Sea;
      AddInfo(FString::Printf(TEXT("%s sea: %s at %s"), *Key, *Sea.Mesh, *Sea.Loc.ToString()));
      TestEqual(Key + TEXT(": sea material MI_EnvSea_<Map>"), PackageOf(Sea.Material),
                FString(S08EnvGroundSpec::MaterialRoot) + TEXT("MI_EnvSea_") + B.Map.Name);
      TestTrue(Key + TEXT(": sea under the tray centre"),
               FMath::IsNearlyEqual(Sea.Loc.X, Top.GetCenter().X, 0.05) &&
                   FMath::IsNearlyEqual(Sea.Loc.Y, Top.GetCenter().Y, 0.05));
      TestTrue(Key + TEXT(": sea below the tray top, above the T2 cliff bottom"),
               Sea.Loc.Z < S08Diorama::TopZ && Sea.Loc.Z > S08Diorama::TopZ - S08Diorama::T2MaxDepthUU);
      if (!FPackageName::DoesPackageExist(PackageOf(Sea.Material)) || !FPackageName::DoesPackageExist(PackageOf(Sea.Mesh))) {
        AddWarning(FString::Printf(TEXT("%s / %s not imported (tools/art/env_kit/ue_import_env_ground.py): no sea ring"),
                                   *Sea.Mesh, *Sea.Material));
      } else {
        UMaterialInstance* SeaMi = LoadObject<UMaterialInstance>(nullptr, *Sea.Material);
        TestTrue(Key + TEXT(": MI_EnvSea parent M_EnvSea"),
                 SeaMi && SeaMi->Parent && SeaMi->Parent->GetPathName() == TEXT("/Game/EnvKit/Ground/M_EnvSea.M_EnvSea"));
      }
    }
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
    TArray<FString> TextureParams = {TEXT("Splat"), TEXT("Aux"), TEXT("WaterRippleN")};
    for (int32 I = 0; I < 4; ++I) {
      for (const TCHAR* K : {TEXT("BC"), TEXT("N"), TEXT("ORMH")}) TextureParams.Add(FString::Printf(TEXT("L%d_%s"), I, K));
    }
    for (const FString& Name : TextureParams) {
      UTexture* Bound = nullptr;
      TestTrue(FString::Printf(TEXT("%s: %s bound"), *Key, *Name),
               Mi->GetTextureParameterValue(FHashedMaterialParameterInfo(*Name), Bound) && Bound != nullptr);
      if ((Name == TEXT("Splat") || Name == TEXT("Aux")) && Bound) {
        TestTrue(Key + TEXT(": ") + Name + TEXT(" linear RGBA8 (TC_VectorDisplacementmap)"),
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundMeshParseTest,
    "Unmatched.S08.EnvLayout.GroundMeshParse P5 waterfall meshes and the sea of the ground section keep every field and reject bad entries",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundMeshParseTest::RunTest(const FString&) {
  using namespace S08EnvGroundTest;
  const FString Mat = TEXT("/Game/EnvKit/Ground/MI_EnvWaterfall_Sarpedon");
  FS08EnvLayout L;
  TArray<FString> Errors;
  const FString Full = GroundJson(FullGroundBody(EngineMaterial) + TEXT(",\"waterfalls\":[") +
                                  FallJson(TEXT("fall-s"), Mat, FallMeshJson()) + TEXT("]") + SeaJson());
  if (!TestTrue(TEXT("mesh + sea parse: ") + FString::Join(Errors, TEXT(" | ")),
                L.ParseJson(LayoutJson(TEXT("sarpedon"), Full), Errors))) {
    return false;
  }
  if (!TestEqual("one waterfall", L.Ground.Waterfalls.Num(), 1)) return false;
  const FS08EnvWaterfallMesh& M = L.Ground.Waterfalls[0].Mesh;
  TestTrue("mesh set", M.bSet);
  TestTrue("mesh paths", M.Sheet == TEXT("/Engine/BasicShapes/Cube") && M.Foam == TEXT("/Engine/BasicShapes/Cylinder") &&
                             M.Lip == TEXT("/Engine/BasicShapes/Cone") && M.LipMaterial == EngineMaterial);
  TestTrue(TEXT("mesh loc / yaw ") + M.Loc.ToString(),
           M.Loc.Equals(FVector(-144.1, 425.0, 0.0), 1e-4) && FMath::IsNearlyEqual(M.YawDeg, 90.0f));
  TestTrue("sheetCard", M.SheetCard.Equals(FVector2D(193.8, 185.231), 1e-4));
  TestTrue("foamCards", M.FoamCards.Num() == 2 && M.FoamCards[0].Equals(FVector2D(261.34, 70.0), 1e-4) &&
                            M.FoamCards[1].Equals(FVector2D(243.97, 76.0), 1e-4));
  TestTrue("the P4 fields still parse", L.Ground.Waterfalls[0].X0 == -241.0f && L.Ground.Waterfalls[0].SpillUU == 60.0f);
  const FS08EnvSea& Sea = L.Ground.Sea;
  TestTrue("sea set", Sea.bSet && Sea.Mesh == TEXT("/Engine/BasicShapes/Plane") && Sea.Material == EngineMaterial);
  TestTrue(TEXT("sea loc ") + Sea.Loc.ToString(), Sea.Loc.Equals(FVector(0.0, -45.0, -172.0), 1e-4) && Sea.YawDeg == 0.0f);
  TestTrue("HasMeshPieces", L.Ground.HasMeshPieces());
  // optional parts: no foam / lip / foamCards / yaw
  Errors.Reset();
  const FString Minimal = TEXT(",\"mesh\":{\"sheet\":\"/Game/EnvKit/Ground/Sarpedon/SM_Env_S_Waterfall\","
                               "\"loc\":[0,0,0],\"sheetCard\":[10,20]}");
  TestTrue(TEXT("minimal mesh parses: ") + FString::Join(Errors, TEXT(" | ")),
           L.ParseJson(LayoutJson(TEXT("sarpedon"), GroundWithFalls(EngineMaterial, FallJson(TEXT("f"), Mat, Minimal))),
                       Errors) &&
               L.Ground.Waterfalls[0].Mesh.bSet && L.Ground.Waterfalls[0].Mesh.Foam.IsEmpty() &&
               L.Ground.Waterfalls[0].Mesh.Lip.IsEmpty() && L.Ground.Waterfalls[0].Mesh.FoamCards.Num() == 0 &&
               L.Ground.Waterfalls[0].Mesh.YawDeg == 0.0f && !L.Ground.Sea.bSet);
  Errors.Reset();
  TestTrue("null mesh / null sea = none",
           L.ParseJson(LayoutJson(TEXT("sarpedon"),
                                  GroundJson(FullGroundBody(EngineMaterial) + TEXT(",\"waterfalls\":[") +
                                             FallJson(TEXT("f"), Mat, TEXT(",\"mesh\":null")) + TEXT("],\"sea\":null"))),
                       Errors) &&
               !L.Ground.Waterfalls[0].Mesh.bSet && !L.Ground.Sea.bSet && !L.Ground.HasMeshPieces());

  struct FCase {
    const TCHAR* Name;
    FString Extra;        // appended to the ground body after a valid waterfalls array (bFall: inside the fall entry)
    bool bFall;
    const TCHAR* Expect;  // substring of one error
  };
  const TCHAR* const Cube = TEXT("/Engine/BasicShapes/Cube");
  const FString Loc = TEXT("\"loc\":[0,0,0]");
  const FString Card = TEXT("\"sheetCard\":[10,20]");
  auto MeshObj = [](const FString& Body) { return FString::Printf(TEXT(",\"mesh\":{%s}"), *Body); };
  const FString S = FString::Printf(TEXT("\"sheet\":\"%s\""), Cube);
  const FCase Cases[] = {
      {TEXT("mesh a string"), TEXT(",\"mesh\":\"x\""), true, TEXT("mesh is not an object")},
      {TEXT("sheet missing"), MeshObj(Loc + TEXT(",") + Card), true, TEXT("mesh.sheet")},
      {TEXT("sheet not a package"), MeshObj(TEXT("\"sheet\":\"Engine/X\",") + Loc + TEXT(",") + Card), true,
       TEXT("mesh.sheet")},
      {TEXT("foam not a package"), MeshObj(S + TEXT(",\"foam\":\"C:/x\",") + Loc + TEXT(",") + Card), true,
       TEXT("mesh.foam")},
      {TEXT("lip without material"), MeshObj(S + TEXT(",\"lip\":\"/Engine/BasicShapes/Cone\",") + Loc + TEXT(",") + Card),
       true, TEXT("lipMaterial")},
      {TEXT("loc missing"), MeshObj(S + TEXT(",") + Card), true, TEXT("mesh.loc")},
      {TEXT("loc two numbers"), MeshObj(S + TEXT(",\"loc\":[0,0],") + Card), true, TEXT("mesh.loc")},
      {TEXT("loc z 60"), MeshObj(S + TEXT(",\"loc\":[0,0,60],") + Card), true, TEXT("mesh.loc")},
      {TEXT("loc x 6000"), MeshObj(S + TEXT(",\"loc\":[6000,0,0],") + Card), true, TEXT("mesh.loc")},
      {TEXT("yaw 400"), MeshObj(S + TEXT(",") + Loc + TEXT(",\"yawDeg\":400,") + Card), true, TEXT("mesh.yawDeg")},
      {TEXT("sheetCard missing"), MeshObj(S + TEXT(",") + Loc), true, TEXT("mesh.sheetCard")},
      {TEXT("sheetCard zero"), MeshObj(S + TEXT(",") + Loc + TEXT(",\"sheetCard\":[0,20]")), true, TEXT("mesh.sheetCard")},
      {TEXT("three foamCards"),
       MeshObj(S + TEXT(",") + Loc + TEXT(",") + Card + TEXT(",\"foamCards\":[[1,1],[1,1],[1,1]]")), true,
       TEXT("mesh.foamCards")},
      {TEXT("foamCard of strings"), MeshObj(S + TEXT(",") + Loc + TEXT(",") + Card + TEXT(",\"foamCards\":[[\"1\",1]]")),
       true, TEXT("mesh.foamCards")},
      {TEXT("sea a number"), TEXT(",\"sea\":3"), false, TEXT("ground: sea is not an object")},
      {TEXT("sea mesh missing"), FString::Printf(TEXT(",\"sea\":{\"material\":\"%s\",\"loc\":[0,-45,-172]}"), EngineMaterial),
       false, TEXT("sea.mesh")},
      {TEXT("sea material bad"), SeaJson(TEXT("/Engine/BasicShapes/Plane"), TEXT("MI_X")), false, TEXT("sea.material")},
      {TEXT("sea at the tray top"), SeaJson(TEXT("/Engine/BasicShapes/Plane"), EngineMaterial, TEXT("[0,-45,-3]")), false,
       TEXT("sea.loc")},
      {TEXT("sea above the board"), SeaJson(TEXT("/Engine/BasicShapes/Plane"), EngineMaterial, TEXT("[0,-45,10]")), false,
       TEXT("sea.loc")},
      {TEXT("sea too deep"), SeaJson(TEXT("/Engine/BasicShapes/Plane"), EngineMaterial, TEXT("[0,-45,-2000]")), false,
       TEXT("sea.loc")},
      {TEXT("sea far off"), SeaJson(TEXT("/Engine/BasicShapes/Plane"), EngineMaterial, TEXT("[0,9000,-172]")), false,
       TEXT("sea.loc")},
  };
  for (const FCase& C : Cases) {
    const FString Falls = FallJson(TEXT("f"), Mat, C.bFall ? C.Extra : FString());
    const FString Ground = GroundJson(FullGroundBody(EngineMaterial) + TEXT(",\"waterfalls\":[") + Falls + TEXT("]") +
                                      (C.bFall ? FString() : C.Extra));
    FS08EnvLayout Bad;
    TArray<FString> CaseErrors;
    const bool bOk = Bad.ParseJson(LayoutJson(TEXT("sarpedon"), Ground), CaseErrors);
    TestFalse(FString::Printf(TEXT("%s: the whole layout is rejected"), C.Name), bOk);
    const FString All = FString::Join(CaseErrors, TEXT(" | "));
    TestTrue(FString::Printf(TEXT("%s: error mentions '%s' (%s)"), C.Name, C.Expect, *All), All.Contains(C.Expect));
    TestFalse(FString::Printf(TEXT("%s: ground not set"), C.Name), Bad.Ground.bSet);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundMeshGeometryTest,
    "Unmatched.S08.EnvLayout.GroundMeshGeometry P5 lane K pieces sit at loc with yaw 90 out of the tray; sheet / foam FallCard; trace tail",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundMeshGeometryTest::RunTest(const FString&) {
  FS08EnvWaterfallMesh M;
  M.bSet = true;
  M.Loc = FVector(-144.1, 425.0, 0.0);
  M.YawDeg = 90.0f;
  M.SheetCard = FVector2D(193.8, 185.231);
  M.FoamCards = {FVector2D(261.34, 70.0), FVector2D(243.97, 76.0)};
  const FTransform T = S08EnvGround::MeshPieceTransform(M.Loc, M.YawDeg);
  // lane K local frame: +X out of the tray (board +Y at yaw 90), Y across the fall (board -X), z 0 = the play plane
  TestTrue("local +X -> board +Y", T.TransformVectorNoScale(FVector(1.0, 0.0, 0.0)).Equals(FVector(0.0, 1.0, 0.0), 1e-6));
  TestTrue("local +Y -> board -X", T.TransformVectorNoScale(FVector(0.0, 1.0, 0.0)).Equals(FVector(-1.0, 0.0, 0.0), 1e-6));
  TestTrue("scale 1", T.GetScale3D().Equals(FVector::OneVector, 0.0));
  // the sheet starts at local (26.04, 0, 2): just in front of the T2b lip (23 uu) of the near tray edge (y 425)
  const FVector Top = T.TransformPosition(FVector(26.04, 0.0, 2.0));
  TestTrue(TEXT("sheet top at the near tray edge ") + Top.ToString(), Top.Equals(FVector(-144.1, 451.04, 2.0), 1e-3));
  TestTrue("the sheet starts beyond the T2b side overhang (23 uu)", Top.Y - 425.0 > 23.0);
  TestTrue("SheetCard = (193.8, 185.231, card)",
           S08EnvGround::SheetCardParam(M).Equals(FLinearColor(193.8f, 185.231f, S08EnvGroundSpec::FallKindCard, S08EnvGroundSpec::FallFlipMesh), 1e-3f));
  TestTrue("foam slot 0 (kind 1)",
           S08EnvGround::FoamCardParam(M, 0).Equals(FLinearColor(261.34f, 70.0f, S08EnvGroundSpec::FallKindSpill, S08EnvGroundSpec::FallFlipMesh), 1e-3f));
  TestTrue("mist slot 1", S08EnvGround::FoamCardParam(M, 1).Equals(FLinearColor(243.97f, 76.0f, 1.0f, 1.0f), 1e-3f));
  TestTrue("a third slot repeats the last card", S08EnvGround::FoamCardParam(M, 5) == S08EnvGround::FoamCardParam(M, 1));
  FS08EnvWaterfallMesh NoCards = M;
  NoCards.FoamCards.Reset();
  TestTrue("no foamCards: the sheet width x 70", S08EnvGround::FoamCardParam(NoCards, 0).Equals(FLinearColor(193.8f, 70.0f, 1.0f, 1.0f), 1e-3f));
  // trace: the P5 tail only for a ground with mesh pieces
  FS08EnvWaterfall Fall;
  Fall.Id = TEXT("fall-s");
  Fall.X0 = -241.0f;
  Fall.X1 = -47.2f;
  Fall.Y = 457.0f;
  Fall.DropUU = 120.0f;
  Fall.SpillUU = 60.0f;
  FS08EnvGround G;
  G.bSet = true;
  G.Mode = S08EnvGroundSpec::RuntimeMode;
  G.Material = TEXT("/Game/EnvKit/Ground/MI_EnvGround_Sarpedon");
  G.Waterfalls.Add(Fall);
  FS08EnvGroundStats St;
  St.Status = TEXT("ok");
  St.Strips = 4;
  St.Falls = 1;
  St.FallCards = 2;
  const FString Old = S08EnvGround::TraceLine(TEXT("sarpedon"), G, St);
  TestTrue("no mesh pieces: the P4 line ends with status", Old.EndsWith(TEXT(" falls=1/1 fallCards=2 status=ok")));
  G.Waterfalls[0].Mesh = M;
  G.Sea.bSet = true;
  St.FallCards = 1;
  St.FallMeshes = 1;
  St.FallMeshParts = 3;
  St.SeaStatus = TEXT("ok");
  const FString New = S08EnvGround::TraceLine(TEXT("sarpedon"), G, St);
  AddInfo(New);
  TestTrue("mesh pieces: the P5 tail after status",
           New.EndsWith(TEXT(" falls=1/1 fallCards=1 status=ok fallMeshes=1 fallMeshParts=3 sea=ok")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvGroundMeshSpawnTest,
    "Unmatched.S08.EnvLayout.GroundMeshSpawn fake map-image board: sheet, foam and lip meshes instead of the card, the spill kept, the sea ring; fallbacks",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvGroundMeshSpawnTest::RunTest(const FString&) {
  using namespace S08EnvGroundTest;
  FTestWorld W(TEXT("S08EnvGroundMeshSpawn"));
  if (!TestNotNull("test world", W.World)) return false;
  AS08BoardActor* Actor = W.SpawnBoard();
  if (!TestNotNull("board actor", Actor)) return false;
  USceneComponent* Root = Actor->GetRootComponent();
  UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, S08EnvGroundSpec::PlaneMeshPath);
  UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
  UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
  UStaticMesh* Cone = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cone.Cone"));
  UMaterialInterface* Parent = LoadObject<UMaterialInterface>(nullptr, EngineMaterial);
  if (!TestTrue("engine shapes and material", Plane && Cube && Cylinder && Cone && Parent)) return false;
  const FString Dir = TempDir(TEXT("Mesh"));
  const FString File = S08EnvLayout::FileFor(Dir, TEXT("envmesh"));
  auto Write = [&](const FString& FallExtra, const FString& Sea) {
    return WriteText(File, LayoutJson(TEXT("envmesh"),
                                      GroundJson(FullGroundBody(EngineMaterial) + TEXT(",\"waterfalls\":[") +
                                                 FallJson(TEXT("fall-s"), EngineMaterial, FallExtra) + TEXT("]") + Sea)));
  };
  TestTrue("write layout", Write(FallMeshJson(), SeaJson()));
  FS08EnvLayoutRequest Req;
  Req.bEnabled = true;
  Req.bMapImageActive = true;
  Req.ProfileId = TEXT("envmap");
  Req.MapKey = TEXT("envmesh");
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
  const FString Line = S08EnvGround::TraceLine(Req.MapKey, Rt.Layout.Ground, Rt.GroundStats);
  AddInfo(Line);
  const FS08EnvGroundStats& St = Rt.GroundStats;
  TestTrue("4 strips, 1 fall as meshes (sheet + foam + lip), the spill plane, the sea",
           St.Status == TEXT("ok") && St.Strips == 4 && St.Falls == 1 && St.FallMeshes == 1 && St.FallMeshParts == 3 &&
               St.FallCards == 1 && St.SeaStatus == TEXT("ok"));
  TestTrue("trace tail", Line.EndsWith(TEXT("fallMeshes=1 fallMeshParts=3 sea=ok")));
  if (!TestEqual("9 ground components (4 strips + sheet + foam + lip + spill + sea)", Rt.Ground.Num(), 9)) return false;
  const FS08EnvWaterfall& Fall = Rt.Layout.Ground.Waterfalls[0];
  const FTransform Piece = S08EnvGround::MeshPieceTransform(Fall.Mesh.Loc, Fall.Mesh.YawDeg);
  struct FWant {
    const TCHAR* Name;
    UStaticMesh* Mesh;
    bool bShadow;
  };
  const FWant Want[] = {{TEXT("EnvWaterfall_fall_s_Sheet"), Cube, false},
                        {TEXT("EnvWaterfall_fall_s_Foam"), Cylinder, false},
                        {TEXT("EnvWaterfall_fall_s_Lip"), Cone, true},
                        {TEXT("EnvWaterfall_fall_s_Spill"), Plane, false},
                        {TEXT("EnvSea"), Plane, false}};
  for (int32 I = 0; I < 5; ++I) {
    UStaticMeshComponent* C = Rt.Ground[4 + I].Get();
    if (!TestNotNull(FString::Printf(TEXT("piece %d alive"), I), C)) continue;
    const FString N = C->GetName();
    TestTrue(N + TEXT(": named ") + Want[I].Name, N.StartsWith(Want[I].Name));
    TestTrue(N + TEXT(": mesh"), C->GetStaticMesh() == Want[I].Mesh);
    TestTrue(N + TEXT(": registered under the board root"), C->IsRegistered() && C->GetAttachParent() == Root);
    TestTrue(N + TEXT(": NoCollision, no navigation"),
             C->GetCollisionEnabled() == ECollisionEnabled::NoCollision && !C->CanEverAffectNavigation());
    TestTrue(N + TEXT(": casts a shadow only for the rock lip"), static_cast<bool>(C->CastShadow) == Want[I].bShadow);
    const FTransform Rel = C->GetRelativeTransform();
    if (I < 3) {
      TestTrue(N + TEXT(": at the lane K piece transform ") + Rel.ToString(), Rel.Equals(Piece, 1e-3));
    } else if (I == 3) {
      TestTrue(N + TEXT(": the P4 spill transform"), Rel.Equals(S08EnvGround::FallSpillTransform(Fall), 1e-3));
    } else {
      TestTrue(N + TEXT(": at the sea loc ") + Rel.ToString(),
               Rel.Equals(S08EnvGround::MeshPieceTransform(FVector(0.0, -45.0, -172.0), 0.0f), 1e-3));
    }
  }
  // materials: sheet / foam = MIDs of the fall material with their FallCard, spill as in P4, lip / sea = the MI as is
  auto MidCard = [&](int32 Index, int32 Slot) -> const FVectorParameterValue* {
    UStaticMeshComponent* C = Rt.Ground[Index].Get();
    UMaterialInstanceDynamic* Mid = C ? Cast<UMaterialInstanceDynamic>(C->GetMaterial(Slot)) : nullptr;
    return Mid && Mid->Parent == Parent ? FindVector(Mid, S08EnvGroundSpec::ParamFallCard) : nullptr;
  };
  const FVectorParameterValue* SheetCard = MidCard(4, 0);
  TestTrue("sheet MID FallCard = sheetCard (kind 0)",
           SheetCard && SheetCard->ParameterValue.Equals(S08EnvGround::SheetCardParam(Fall.Mesh), 1e-3f));
  const FVectorParameterValue* FoamCard = MidCard(5, 0);
  TestTrue("foam MID FallCard = foamCards[0] (kind 1)",
           FoamCard && FoamCard->ParameterValue.Equals(S08EnvGround::FoamCardParam(Fall.Mesh, 0), 1e-3f));
  const FVectorParameterValue* SpillCard = MidCard(7, 0);
  TestTrue("spill MID FallCard as in P4",
           SpillCard && SpillCard->ParameterValue.Equals(S08EnvGround::FallCardParam(Fall, true), 1e-3f));
  TestTrue("lip: the lipMaterial itself", Rt.Ground[6].Get() && Rt.Ground[6]->GetMaterial(0) == Parent);
  TestTrue("sea: the sea material itself", Rt.Ground[8].Get() && Rt.Ground[8]->GetMaterial(0) == Parent);
  // the sheet mesh is not in the build: the P4 plane card comes back (foam / lip are not shown without the sheet)
  TestTrue("rewrite: missing sheet", Write(FallMeshJson(TEXT("/Game/EnvKit/Ground/Sarpedon/SM_NoSuchSheetTest")), SeaJson()));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("missing sheet: card + spill + sea", Rt.Ground.Num() == 7 && Rt.GroundStats.FallMeshes == 0 &&
                                                   Rt.GroundStats.FallMeshParts == 0 && Rt.GroundStats.FallCards == 2 &&
                                                   Rt.GroundStats.SeaStatus == TEXT("ok"));
  TestTrue("missing sheet: the card is the P4 plane",
           Rt.Ground.Num() > 4 && Rt.Ground[4].Get() && Rt.Ground[4]->GetName().StartsWith(TEXT("EnvWaterfall_fall_s_Card")) &&
               Rt.Ground[4]->GetStaticMesh() == Plane);
  // a lip whose tray material is not in the build is skipped (sheet + foam stay)
  TestTrue("rewrite: missing lip material",
           Write(FallMeshJson(TEXT("/Engine/BasicShapes/Cube"), TEXT("/Game/PipelineCandidates/TableBase/T2b/MI_NoSuchTest")),
                 SeaJson()));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("missing lip material: sheet + foam + spill + sea",
           Rt.Ground.Num() == 8 && Rt.GroundStats.FallMeshes == 1 && Rt.GroundStats.FallMeshParts == 2);
  // sea statuses
  TestTrue("rewrite: missing sea mesh", Write(FallMeshJson(), SeaJson(TEXT("/Game/EnvKit/Ground/Sarpedon/SM_NoSuchSeaTest"))));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("missing sea mesh: no ring, traced", Rt.Ground.Num() == 8 && Rt.GroundStats.SeaStatus == TEXT("missing-mesh"));
  TestTrue("rewrite: missing sea material",
           Write(FallMeshJson(), SeaJson(TEXT("/Engine/BasicShapes/Plane"), TEXT("/Game/EnvKit/Ground/MI_EnvSea_NoSuchTest"))));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestTrue("missing sea material: no ring, traced",
           Rt.Ground.Num() == 8 && Rt.GroundStats.SeaStatus == TEXT("missing-material"));
  // a grid / grey board clears everything
  Req.bMapImageActive = false;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, Props, Lights);
  TestEqual("grid / grey board: no ground, no fall, no sea", Rt.Ground.Num(), 0);
  Actor->Destroy();
  IFileManager::Get().DeleteDirectory(*FPaths::Combine(FPaths::AutomationTransientDir(), TEXT("S08EnvGround")), false, true);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
