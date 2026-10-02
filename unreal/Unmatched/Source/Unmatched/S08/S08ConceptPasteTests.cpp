// ENV-MAPS P7 (ENV-U15) automation tests: the concept paste around the real map field (S08ConceptPaste.h).
//   Camera     the concept camera C0 = the k1_mock / cp_common pinhole: the P7a design details back on their pixels,
//              ray / project round trip, the same model as FS08BoardView (SetupCameraForBoard) at K1
//   Parser     the "conceptPaste" block: every field, map-image only, the light budget with the profile, rejection table
//   Mode       the decision table (-ConceptPaste / -NoConceptPaste / -EnvLayoutVariant / the block default / the gate),
//              command-line parsing, the fallback after missing assets / overlay
//   Shipped    S08ArtBoardProfiles.json: Sarpedon ON by default (P5c = -EnvLayoutVariant=p5c), Marmoreal present but
//              OFF (accepted look unchanged), no grid profile has the block, budget 1 key + 6 points
//   Geometry   sea plane + sky cylinder transforms, the shader mirror (cut under the frame, plate rectangles, feather,
//              behind the camera), grade fallbacks, inverse ACES, flicker / sway
//   EnvIds     what the board actor hides by: overlay-added / replaced ids (MergeOverlay), the spawned component ids
//   ApplyFailure  P7c: Apply != ok with the assets loaded -> the full P5c look (base layout, backdrop, tray, fog)
//   Actor      the board actor: nothing on grids or a refused map profile (no line), the shipped Sarpedon / Marmoreal
//              once the map import ran (P8: the lit 3D island on or the traced P5c fallback; -EnvLayoutVariant=p5c;
//              Marmoreal off)
//   ENV-MAPS P8 (lit3d, docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md):
//   PasteKind  -ConceptPaste=paste on the shipped Sarpedon: the P7 paste or the traced P5c fallback
//   Lit3dScene ApplyLit3d (no sheet, lights in the budget, missing / failed), the lit3d hide list, ApplyScene (casters,
//              giOff, the sea ring to -300, the falls stretched), idempotent, RestoreHides
//   MaterialOverride  the env-layout prop "material" (every slot / per slot, rejections, overlay, spawn, missing kept)
//   LightsOff  -ArtPreviewLightsOff (gate G1): the engine lights at 0, the fog hidden, the lit3d sky hidden
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.ConceptPaste; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08ConceptPaste.h"
#include "S08Contracts.h"
#include "S08Diorama.h"
#include "S08EnvLayout.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace S08ConceptPasteTest {
/** The 3D frame-002 outer foot of the shipped maps (map half + 24 uu). */
const FVector2D FrameHalf(445.66667 + 24.0, 288.66667 + 24.0);

/** P7a design (design.json 5_elements.keep_3D_animated): world position -> C0 pixel. */
struct FDetail {
  const TCHAR* Id;
  FVector World;
  FVector2D Px;
};
const FDetail Details[] = {
    {TEXT("lantern-bay"), FVector(-129.7, -397.7, 196.6), FVector2D(818, 60)},
    {TEXT("lantern-left"), FVector(-565.9, -46.1, 154.3), FVector2D(301, 393)},
    {TEXT("lantern-deck-se"), FVector(622.9, 228.1, 104.0), FVector2D(1719, 695)},
    {TEXT("fire-fort"), FVector(-492.3, -427.3, -3.0), FVector2D(454, 182)},
    {TEXT("fire-brazier"), FVector(-555.1, 194.3, 112.1), FVector2D(287, 655)},
    {TEXT("cannon-3"), FVector(721.5, -34.7, 19.0), FVector2D(1768, 496)},
    {TEXT("banner-ship"), FVector(831.2, -133.3, 49.1), FVector2D(1880, 388)},
};

/** A minimal valid block (Sarpedon-like) and the document around it: light profile L with one point, the map board
 *  'cpmap' (Board row id cidCp, map assets that do not exist) carrying Block, and a 3 x 2 grid board 'cpgrid'. */
const TCHAR* const ValidBlock = TEXT(
    "{\"note\":\"t\",\"default\":\"on\",\"variant\":\"concept\",\"offVariant\":\"p5c\",\"spec\":\"s.json\","
    "\"manifest\":\"m.json\",\"material\":\"/Game/EnvMaps/ConceptPaste/M_ConceptPaste\","
    "\"sheetMesh\":\"/Game/EnvMaps/NoSuchCp/ConceptPaste/SM_NoSuchCp_ConceptSheet\","
    "\"plateA\":\"/Game/EnvMaps/NoSuchCp/ConceptPaste/T_A\",\"plateB\":\"/Game/EnvMaps/NoSuchCp/ConceptPaste/T_B\","
    "\"seaPlate\":\"/Game/EnvMaps/NoSuchCp/ConceptPaste/T_Sea\",\"lut\":\"/Game/EnvMaps/ConceptPaste/T_NoSuchLut\","
    "\"camera\":{\"distanceUU\":2714.626,\"focus\":[0,0,0],\"pitch\":-55,\"yaw\":-90,\"hfov\":35,\"sizePx\":[1920,1080]},"
    "\"homography\":[[1.004216994,0.001544779,-2.393861127],[0.000580243,1.003243632,-1.438038288],[1.137e-06,1.225e-06,1.0]],"
    "\"rectA\":[0,0,1920,1080],\"rectB\":[-383.5407,-215.7705,2687.0813,1511.5409],\"featherPx\":24,\"outside\":\"clip\","
    "\"cut\":{\"underFrameUU\":2,\"minZ\":-60},\"grade\":{\"mode\":\"lut\",\"gainLinear\":0.9638},"
    "\"sea\":{\"zUU\":-300,\"centreUU\":[0,-45],\"radiusUU\":1900,\"skyTopZUU\":600,\"skySegments\":48},"
    "\"hide\":[\"tray\",\"ground\",\"sea\",\"waterfalls\",\"backdrop\",\"fog\",\"baseProps\",\"baseFx\",\"layoutLights\"],"
    "\"lights\":[{\"id\":\"fire-fort\",\"loc\":[-492.3,-427.3,35],\"colorSrgb\":\"#FF8A3D\",\"intensityCd\":65,\"radius\":460,"
    "\"flicker\":{\"amp\":0.18,\"hz\":6}},{\"id\":\"lantern-left\",\"loc\":[-565.9,-46.1,154.3],\"colorSrgb\":\"#FFA552\","
    "\"intensityCd\":80,\"radius\":400}],"
    "\"anims\":[{\"prop\":\"lantern-rail\",\"swayDeg\":4,\"swayHz\":0.4,\"axis\":\"y\"}],"
    "\"shadowBlobs\":[{\"id\":\"cannon-1\",\"loc\":[587.6,-333.2,-3],\"diameterUU\":70,\"strength\":0.35,\"softness\":0.6}],"
    "\"flow\":{\"regions\":[{\"id\":\"waterfall\",\"rectPx\":[640,885,361,411],\"velocityPx\":[0,28],\"ampPx\":1.5}],"
    "\"sea\":{\"velocityPx\":[7,2],\"ampPx\":1.2}}}");

FString Doc(const FString& MapBlock, const FString& GridBlock = FString()) {
  const FString MapExtra = MapBlock.IsEmpty() ? FString() : TEXT("\"conceptPaste\":") + MapBlock + TEXT(",");
  const FString GridExtra = GridBlock.IsEmpty() ? FString() : TEXT("\"conceptPaste\":") + GridBlock + TEXT(",");
  return FString::Printf(TEXT(
      "{\"schema\":\"unmatched.s08-art-board-profiles/1\",\"revision\":15,"
      "\"zoneStyles\":{\"a\":{\"stroke\":\"solid\",\"glyph\":\"diamond\",\"color\":\"#102030\"},"
      "\"b\":{\"stroke\":\"dash2\",\"glyph\":\"ring\",\"color\":\"#A0B0C0\"}},"
      "\"fallbackZoneStyle\":{\"stroke\":\"dots5\",\"glyph\":\"bar1\",\"color\":\"#FFFFFF\"},"
      "\"lightProfiles\":{\"L\":{\"directional\":{\"name\":\"key\",\"posUU\":[0,0,600],\"rotation\":[-55,30,0],"
      "\"intensity\":3,\"castShadows\":true},\"points\":[{\"name\":\"p\",\"at\":[0,0,750],\"intensity\":50,"
      "\"radiusUU\":300,\"colorLinear\":[1,0.5,0.25]}]}},"
      "\"boards\":[{\"id\":\"cpgrid\",\"match\":{\"width\":3,\"height\":2,\"zoneKeys\":[\"a\",\"b\"]},\"surface\":\"tiles\","
      "\"light\":\"L\",%s\"expect\":{\"cells\":6}},"
      "{\"id\":\"cpmap\",\"match\":{\"boardIds\":[\"cidCp\"]},\"surface\":\"map-image\",\"light\":\"L\",%s"
      "\"mapImage\":{\"name\":\"NoSuchCpTest\",\"bc\":\"/Game/EnvMaps/NoSuchCpTest/T_NoSuchCpTest_Map_BC_4K\","
      "\"mask\":\"/Game/EnvMaps/NoSuchCpTest/T_NoSuchCpTest_Map_GameMask_4K\","
      "\"sdf\":\"/Game/EnvMaps/NoSuchCpTest/T_NoSuchCpTest_Map_GameSDF_4K\","
      "\"id\":\"/Game/EnvMaps/NoSuchCpTest/T_NoSuchCpTest_Map_SpaceID_4K\","
      "\"materialInstance\":\"/Game/EnvMaps/NoSuchCpTest/MI_NoSuchCpTest_MapBoard\","
      "\"srcSize\":[1337,866],\"uuPerPx\":0.6666667,\"frameUU\":24}}]}"),
      *GridExtra, *MapExtra);
}

/** Block with one field replaced / added (Field "" = no change) or removed (Value "" with bRemove). */
FString BlockWithOn(const FString& Block, const FString& Field, const FString& Value, bool bRemove = false) {
  TSharedPtr<FJsonObject> Obj;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Block, Obj, Problem) || !Obj.IsValid()) return FString();
  if (bRemove) {
    Obj->RemoveField(Field);
  } else if (!Field.IsEmpty()) {
    TSharedPtr<FJsonObject> Wrapper;
    if (!FS08Contracts::TryParseJsonObject(TEXT("{\"v\":") + Value + TEXT("}"), Wrapper, Problem) || !Wrapper.IsValid()) {
      return FString();
    }
    Obj->SetField(Field, Wrapper->TryGetField(TEXT("v")));
  }
  FString Out;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Obj.ToSharedRef(), Writer);
  return Out;
}

/** ValidBlock with one field replaced / added / removed. */
FString BlockWith(const FString& Field, const FString& Value, bool bRemove = false) {
  return BlockWithOn(ValidBlock, Field, Value, bRemove);
}

/** ENV-MAPS P8: a valid "lit3d" object (no sky: the test assets have no sky plate) and ValidBlock with it as the default
 *  kind ("mode": "lit3d"). */
const TCHAR* const ValidLit3d = TEXT(
    "{\"note\":\"t\",\"variant\":\"scene\",\"manifest\":\"tools/art/concept_scene/manifest.t.json\","
    "\"required\":[\"/Game/EnvMaps/Scene/M_EnvScene\",\"/Game/EnvMaps/NoSuchCp/Scene/SM_Env_S_Island\"],"
    "\"sky\":false,\"seaZUU\":-300,\"waterfallScaleZ\":2,"
    "\"hide\":[\"tray\",\"ground\",\"backdrop\",\"fog\",\"baseProps\",\"baseFx\",\"layoutLights\"],"
    "\"lights\":[{\"id\":\"fire-fort\",\"loc\":[-492.3,-427.3,54],\"colorSrgb\":\"#FF8A3D\",\"intensityCd\":65,\"radius\":460,"
    "\"flicker\":{\"amp\":0.18,\"hz\":6}},{\"id\":\"lantern-deck-n\",\"loc\":[522.4,-157.4,82.4],\"colorSrgb\":\"#FFA552\","
    "\"intensityCd\":95,\"radius\":420}],"
    "\"anims\":[{\"prop\":\"lantern-rail\",\"swayDeg\":4,\"swayHz\":0.4}],"
    "\"winds\":[\"banner-ship\",\"tree-*\"],\"casters\":[\"island\",\"ship*\",\"tree-*\"],\"giOff\":[\"island\"]}");

FString Lit3dBlock() { return BlockWithOn(BlockWith(TEXT("lit3d"), ValidLit3d), TEXT("mode"), TEXT("\"lit3d\"")); }

/** Lit3dBlock with one field of its "lit3d" object replaced / added / removed. */
FString Lit3dWith(const FString& Field, const FString& Value, bool bRemove = false) {
  return BlockWithOn(BlockWith(TEXT("lit3d"), BlockWithOn(ValidLit3d, Field, Value, bRemove)), TEXT("mode"), TEXT("\"lit3d\""));
}

const FS08BoardArtProfile* Find(const FS08BoardArtData& Data, const TCHAR* Id) {
  return Data.Boards.FindByPredicate([Id](const FS08BoardArtProfile& B) { return B.Id == Id; });
}

FS08ConceptPasteInputs Inputs(const TCHAR* CommandLine) { return S08ConceptPaste::InputsFromCommandLine(CommandLine); }

/** -ArtPreviewDiorama on, -ArtPreviewNoEnv off, and a fake command line for the concept-paste inputs. */
struct FScope {
  explicit FScope(const TCHAR* FakeCommandLine) {
    S08Diorama::SetFlagOverrideForTest(true);
    S08EnvLayout::SetOptOutOverrideForTest(false);
    S08ConceptPaste::SetCommandLineOverrideForTest(FakeCommandLine);
  }
  ~FScope() {
    S08Diorama::ResetFlagOverrideForTest();
    S08EnvLayout::ResetOptOutOverrideForTest();
    S08ConceptPaste::ResetCommandLineOverrideForTest();
  }
};

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
      Cell.Zones = {X == 0 ? TEXT("a") : TEXT("b")};
    }
  }
  return Board;
}

bool SyntheticTopology(FS08BoardModel& Out) {
  const TCHAR* Json = TEXT(
      "{\"width\":3,\"height\":2,\"doors\":{},\"cells\":["
      "[{\"type\":\"normal\",\"x\":0,\"y\":0,\"zones\":[\"a\"],\"zone\":\"a\",\"spaceId\":\"T01\",\"layout\":{\"x\":200,\"y\":200},"
      "\"start\":1,\"links\":[{\"x\":1,\"y\":0}]},"
      "{\"type\":\"normal\",\"x\":1,\"y\":0,\"zones\":[\"a\",\"b\"],\"zone\":\"a\",\"spaceId\":\"T02\",\"layout\":{\"x\":500,\"y\":200},"
      "\"links\":[{\"x\":0,\"y\":0},{\"x\":2,\"y\":1}]},"
      "{\"type\":\"obstacle\",\"x\":2,\"y\":0}],"
      "[{\"type\":\"obstacle\",\"x\":0,\"y\":1},{\"type\":\"obstacle\",\"x\":1,\"y\":1},"
      "{\"type\":\"normal\",\"x\":2,\"y\":1,\"zones\":[\"b\"],\"zone\":\"b\",\"spaceId\":\"T03\",\"layout\":{\"x\":800,\"y\":500},"
      "\"start\":2,\"links\":[{\"x\":1,\"y\":0}]}]]}");
  TSharedPtr<FJsonObject> Obj;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Json, Obj, Problem) || !Obj.IsValid()) return false;
  return Out.Decode(MakeShared<FJsonValueObject>(Obj));
}

/** backend/prisma/fixtures/boards/<file> (unmatched.board-topology/1) -> the boardState projection (own copy of the
 *  S08BoardArtTests helper for non-unity builds). */
bool TopologyBoard(const TCHAR* File, FS08BoardModel& OutBoard, FString& OutBoardId) {
  const FString Path = FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../backend/prisma/fixtures/boards"), File));
  FString Text;
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FFileHelper::LoadFileToString(Text, *Path) || !FS08Contracts::TryParseJsonObject(Text, Root, Problem) ||
      !Root.IsValid()) {
    return false;
  }
  OutBoardId = Root->GetStringField(TEXT("boardId"));
  const TSharedPtr<FJsonObject> Lattice = Root->GetObjectField(TEXT("lattice"));
  const int32 W = static_cast<int32>(Lattice->GetNumberField(TEXT("width")));
  const int32 H = static_cast<int32>(Lattice->GetNumberField(TEXT("height")));
  TArray<TArray<TSharedPtr<FJsonValue>>> Rows;
  Rows.SetNum(H);
  for (int32 Y = 0; Y < H; ++Y) Rows[Y].SetNum(W);
  for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("cells"))) {
    const TSharedPtr<FJsonObject> C = V->AsObject();
    const int32 X = static_cast<int32>(C->GetNumberField(TEXT("x")));
    const int32 Y = static_cast<int32>(C->GetNumberField(TEXT("y")));
    if (X < 0 || Y < 0 || X >= W || Y >= H) return false;
    TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
    bool bObstacle = false;
    C->TryGetBoolField(TEXT("isObstacle"), bObstacle);
    Cell->SetStringField(TEXT("type"), bObstacle ? TEXT("obstacle") : TEXT("normal"));
    Cell->SetNumberField(TEXT("x"), X);
    Cell->SetNumberField(TEXT("y"), Y);
    const TArray<TSharedPtr<FJsonValue>>* Zones = nullptr;
    if (C->TryGetArrayField(TEXT("zones"), Zones) && Zones && Zones->Num() > 0) {
      Cell->SetArrayField(TEXT("zones"), *Zones);
      Cell->SetStringField(TEXT("zone"), (*Zones)[0]->AsString());
    }
    for (const TCHAR* Field : {TEXT("spaceId"), TEXT("layout"), TEXT("start"), TEXT("links")}) {
      if (C->HasField(Field)) Cell->SetField(Field, C->TryGetField(Field));
    }
    Rows[Y][X] = MakeShared<FJsonValueObject>(Cell);
  }
  TArray<TSharedPtr<FJsonValue>> RowValues;
  for (const TArray<TSharedPtr<FJsonValue>>& Row : Rows) RowValues.Add(MakeShared<FJsonValueArray>(Row));
  TSharedRef<FJsonObject> State = MakeShared<FJsonObject>();
  State->SetNumberField(TEXT("width"), W);
  State->SetNumberField(TEXT("height"), H);
  State->SetArrayField(TEXT("cells"), RowValues);
  State->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
  return OutBoard.Decode(MakeShared<FJsonValueObject>(State));
}

struct FWorld {
  UWorld* World = nullptr;
  explicit FWorld(const TCHAR* Name) {
    World = UWorld::CreateWorld(EWorldType::Game, false, FName(Name));
    if (World) {
      FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
      Context.SetCurrentWorld(World);
    }
  }
  ~FWorld() {
    if (World) {
      GEngine->DestroyWorldContext(World);
      World->DestroyWorld(false);
    }
  }
  AS08BoardActor* Spawn() const {
    return World ? World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator)
                 : nullptr;
  }
};

FString PackageOf(const FString& Path) {
  int32 Dot = INDEX_NONE;
  return Path.FindLastChar(TEXT('.'), Dot) ? Path.Left(Dot) : Path;
}
}  // namespace S08ConceptPasteTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteCameraTest,
    "Unmatched.S08.ConceptPaste.Camera C0 = the k1_mock pinhole: design details on their pixels, round trip, FS08BoardView at K1",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteCameraTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  const FS08ConceptCamera C0;  // the defaults are the P7a concept camera
  TestTrue(TEXT("C0 at (0, 1557.046, 2223.692): ") + C0.Location().ToString(),
           C0.Location().Equals(FVector(0.0, 1557.046, 2223.692), 0.01));
  TestTrue(FString::Printf(TEXT("forward / right / up = the S08 rig (looks along -Y, screen right +X, screen up = far): %s / %s / %s"), *C0.Forward().ToString(), *C0.Right().ToString(), *C0.Up().ToString()),
           C0.Forward().Equals(FVector(0.0, -0.573576, -0.819152), 1e-5) && C0.Right().Equals(FVector(1.0, 0.0, 0.0), 1e-6) &&
               C0.Up().Equals(FVector(0.0, -0.819152, 0.573576), 1e-5));
  FVector2D Px;
  TestTrue("the map centre on the frame centre", C0.Project(FVector::ZeroVector, Px) && Px.Equals(FVector2D(960, 540), 1e-6));
  for (const FDetail& D : Details) {
    TestTrue(FString::Printf(TEXT("%s: C0 px %s within 0.15 px of the design %s"), D.Id, *Px.ToString(), *D.Px.ToString()),
             C0.Project(D.World, Px) && FVector2D::Distance(Px, D.Px) <= 0.15);
  }
  for (const FVector2D P : {FVector2D(0, 0), FVector2D(1919.5, 3.0), FVector2D(-383.5, 1295.8), FVector2D(700.25, 333.5)}) {
    TestTrue(TEXT("ray / project round trip ") + P.ToString(),
             C0.Project(C0.Location() + C0.Ray(P) * 2600.0, Px) && Px.Equals(P, 1e-6));
  }
  TestFalse("behind C0: no pixel", C0.Project(C0.Location() - C0.Forward() * 10.0, Px));
  // the same camera model as SetupCameraForBoard (FS08BoardView) at the K1 overview
  FS08ConceptCamera K1;
  K1.DistanceUU = 2340.195;
  const FS08BoardView View = FS08BoardView::AtDistance(2340.195);
  for (const FVector W : {FVector(300, -200, 10), FVector(-700, 400, -3), FVector(820, -130, 50)}) {
    FVector2D Ndc(0.0, 0.0);
    const bool bBoth = K1.Project(W, Px) && View.Project(W, Ndc);
    const FVector2D FromNdc((Ndc.X + 1.0) * 0.5 * 1920.0, (1.0 - Ndc.Y) * 0.5 * 1080.0);
    TestTrue(TEXT("K1: the concept camera = FS08BoardView at ") + W.ToString(), bBoth && Px.Equals(FromNdc, 1e-4));
  }
  // the P7a registration: a homography that moves the concept by about a pixel, never by a frame
  FS08ConceptHomography H;
  TestTrue("identity by default", H.IsIdentity());
  const double M[3][3] = {{1.004216994, 0.001544779, -2.393861127}, {0.000580243, 1.003243632, -1.438038288}, {1.137e-06, 1.225e-06, 1.0}};
  FMemory::Memcpy(H.M, M, sizeof(M));
  const FVector2D Centre = H.Apply(FVector2D(960, 540));
  TestTrue(TEXT("sarpedon registration keeps the centre within 3 px: ") + Centre.ToString(),
           FVector2D::Distance(Centre, FVector2D(960, 540)) < 3.0 && !H.IsIdentity());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteParserTest,
    "Unmatched.S08.ConceptPaste.Parser conceptPaste block: every field, map-image only, light budget with the profile, rejections",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteParserTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    if (!TestTrue(TEXT("valid block parses: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Doc(ValidBlock), Errors))) {
      return false;
    }
    const FS08BoardArtProfile* Map = Find(Data, TEXT("cpmap"));
    const FS08BoardArtProfile* Grid = Find(Data, TEXT("cpgrid"));
    if (!TestNotNull("map profile", Map) || !TestNotNull("grid profile", Grid)) return false;
    TestFalse("a grid without the block: none", Grid->ConceptPaste.bSet);
    const FS08ConceptPasteSpec& S = Map->ConceptPaste;
    TestTrue("set, default on, variants", S.bSet && S.bDefaultOn && S.Variant == TEXT("concept") && S.OffVariant == TEXT("p5c"));
    TestTrue("informational paths", S.SpecPath == TEXT("s.json") && S.ManifestPath == TEXT("m.json"));
    TestTrue("assets", S.MaterialPath == TEXT("/Game/EnvMaps/ConceptPaste/M_ConceptPaste") &&
                           S.SheetMeshPath.EndsWith(TEXT("SM_NoSuchCp_ConceptSheet")) && S.PlateAPath.EndsWith(TEXT("T_A")) &&
                           S.PlateBPath.EndsWith(TEXT("T_B")) && S.SeaPlatePath.EndsWith(TEXT("T_Sea")) &&
                           S.MaskPath.IsEmpty() && S.LutPath.EndsWith(TEXT("T_NoSuchLut")));
    TestEqual("asset list (6, no mask)", S.AssetPaths().Num(), 6);
    TestTrue("camera", FMath::IsNearlyEqual(S.Camera.DistanceUU, 2714.626, 1e-6) && S.Camera.PitchDeg == -55.0 &&
                           S.Camera.YawDeg == -90.0 && S.Camera.HFovDeg == 35.0 && S.Camera.SizePx == FIntPoint(1920, 1080));
    TestTrue("homography", !S.Homography.IsIdentity() && FMath::IsNearlyEqual(S.Homography.M[0][2], -2.393861127, 1e-12) &&
                               FMath::IsNearlyEqual(S.Homography.M[2][1], 1.225e-06, 1e-15));
    TestTrue("rects / feather / outside", S.RectA == FVector4(0, 0, 1920, 1080) &&
                                              FMath::IsNearlyEqual(S.RectB.X, -383.5407, 1e-9) &&
                                              FMath::IsNearlyEqual(S.RectB.W, 1511.5409, 1e-9) && S.FeatherPx == 24.0f &&
                                              !S.bClampOutside);
    TestTrue("cut 2 uu under the frame foot", S.CutUnderFrameUU == 2.0f && S.CutMinZ == -60.0f &&
                                                  S.CutHalf(FrameHalf).Equals(FVector2D(467.66667, 310.66667), 1e-4));
    TestTrue("grade lut 0.9638, no explicit emissive scale",
             S.Grade == ES08ConceptGrade::Lut && FMath::IsNearlyEqual(S.GainLinear, 0.9638f) && !S.bHasEmissiveScale);
    TestTrue("sea", S.Sea.bSet && S.Sea.ZUU == -300.0f && S.Sea.CentreUU == FVector2D(0, -45) && S.Sea.RadiusUU == 1900.0f &&
                        S.Sea.SkyTopZUU == 600.0f && S.Sea.SkySegments == 48);
    const FS08ConceptHide& H = S.Hide;
    TestTrue("hide: all nine", H.bTray && H.bGround && H.bSea && H.bWaterfalls && H.bBackdrop && H.bFog && H.bBaseProps &&
                                   H.bBaseFx && H.bLayoutLights);
    TestEqual("hide names", H.Names(), FString(TEXT("tray+ground+sea+waterfalls+backdrop+fog+baseProps+baseFx+layoutLights")));
    if (TestEqual("2 lights", S.Lights.Num(), 2)) {
      TestTrue("light 0", S.Lights[0].Id == TEXT("fire-fort") && S.Lights[0].Loc.Equals(FVector(-492.3, -427.3, 35)) &&
                              S.Lights[0].Color == FColor(0xFF, 0x8A, 0x3D) && S.Lights[0].IntensityCd == 65.0f &&
                              S.Lights[0].RadiusUU == 460.0f && FMath::IsNearlyEqual(S.Lights[0].FlickerAmp, 0.18f) &&
                              S.Lights[0].FlickerHz == 6.0f);
      TestTrue("light 1 steady", S.Lights[1].FlickerAmp == 0.0f && S.Lights[1].FlickerHz == 0.0f);
    }
    TestTrue("anim", S.Anims.Num() == 1 && S.Anims[0].Prop == TEXT("lantern-rail") && S.Anims[0].SwayDeg == 4.0f &&
                         FMath::IsNearlyEqual(S.Anims[0].SwayHz, 0.4f) && S.Anims[0].bAxisY);
    TestTrue("blob", S.ShadowBlobs.Num() == 1 && S.ShadowBlobs[0].Id == TEXT("cannon-1") && S.ShadowBlobs[0].DiameterUU == 70.0f);
    TestTrue("flow: the waterfall region + the sea", S.Flows.Num() == 1 && S.Flows[0].Id == TEXT("waterfall") &&
                                                         S.Flows[0].RectPx == FVector4(640, 885, 361, 411) &&
                                                         S.Flows[0].VelocityPx == FVector2D(0, 28) && S.Flows[0].AmpPx == 1.5f &&
                                                         S.SeaFlow.bSet && S.SeaFlow.VelocityPx == FVector2D(7, 2) &&
                                                         FMath::IsNearlyEqual(S.SeaFlow.AmpPx, 1.2f));
  }
  {
    // minimal: only the required fields; everything else keeps its default
    FS08BoardArtData Data;
    TArray<FString> Errors;
    const FString Minimal = TEXT("{\"default\":\"off\",\"sheetMesh\":\"/Game/EnvMaps/X/SM_S\",\"plateB\":\"/Game/EnvMaps/X/T_B\"}");
    if (TestTrue(TEXT("minimal block parses: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Doc(Minimal), Errors))) {
      const FS08ConceptPasteSpec& S = Find(Data, TEXT("cpmap"))->ConceptPaste;
      TestTrue("minimal: off, concept variant, no off variant, default material / camera, identity, no sea, nothing hidden",
               S.bSet && !S.bDefaultOn && S.Variant == TEXT("concept") && S.OffVariant.IsEmpty() &&
                   S.MaterialPath == S08ConceptPasteSpec::DefaultMaterialPath && S.Homography.IsIdentity() &&
                   !S.Sea.bSet && S.Hide.Names() == TEXT("-") && S.Lights.IsEmpty());
    }
  }
  {
    // ENV-MAPS P8: the lit3d object and "mode"; the paste fields stay as they were
    FS08BoardArtData Data;
    TArray<FString> Errors;
    if (TestTrue(TEXT("lit3d block parses: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Doc(Lit3dBlock()), Errors))) {
      const FS08ConceptPasteSpec& S = Find(Data, TEXT("cpmap"))->ConceptPaste;
      const FS08ConceptLit3dSpec& L = S.Lit3d;
      TestTrue("lit3d: set, default kind lit3d, the paste kept", S.bSet && L.bSet && S.DefaultKind == ES08ConceptKind::Lit3d &&
                                                                     S.Variant == TEXT("concept") && S.Lights.Num() == 2);
      TestTrue("lit3d: variant / manifest / required", L.Variant == TEXT("scene") && L.ManifestPath.EndsWith(TEXT("manifest.t.json")) &&
                                                          L.Required.Num() == 2 && L.Required[0] == S08ConceptPasteSpec::SceneMaterialPath);
      TestTrue("lit3d: no sky, sea ring z -300, falls x2", !L.bSky && L.bSeaZ && L.SeaZUU == -300.0f && L.WaterfallScaleZ == 2.0f);
      TestEqual("lit3d: hide (sea and waterfalls come back)", L.Hide.Names(),
                FString(TEXT("tray+ground+backdrop+fog+baseProps+baseFx+layoutLights")));
      TestTrue("lit3d: lights / anim / winds / casters / giOff",
               L.Lights.Num() == 2 && L.Lights[0].Id == TEXT("fire-fort") && FMath::IsNearlyEqual(L.Lights[0].FlickerAmp, 0.18f) &&
                   L.Anims.Num() == 1 && L.WindProps == TArray<FString>({TEXT("banner-ship"), TEXT("tree-*")}) &&
                   L.Casters.Num() == 3 && L.GiOff == TArray<FString>({TEXT("island")}));
      TestTrue("per-kind accessors", &S.HideFor(ES08ConceptKind::Lit3d) == &L.Hide && &S.HideFor(ES08ConceptKind::Paste) == &S.Hide &&
                                         S.LightsFor(ES08ConceptKind::Lit3d).Num() == 2 && S.VariantFor(ES08ConceptKind::Lit3d) == TEXT("scene") &&
                                         S.VariantFor(ES08ConceptKind::Paste) == TEXT("concept") && S.MaxModeLights() == 2);
      TestEqual("asset list: the paste's 6 + the 2 required", S.AssetPaths().Num(), 8);
    }
    // a lit3d object with the paste as the default kind (no "mode")
    FS08BoardArtData Data2;
    TArray<FString> Errors2;
    if (TestTrue(TEXT("lit3d without mode parses: ") + FString::Join(Errors2, TEXT(" | ")),
                 Data2.ParseJson(Doc(BlockWith(TEXT("lit3d"), ValidLit3d)), Errors2))) {
      const FS08ConceptPasteSpec& S = Find(Data2, TEXT("cpmap"))->ConceptPaste;
      TestTrue("no mode: the paste is the default kind", S.Lit3d.bSet && S.DefaultKind == ES08ConceptKind::Paste);
    }
    FS08ConceptLit3dSpec Defaults;
    TestTrue("lit3d defaults: scene, sky on, sea kept, falls x1", Defaults.Variant == TEXT("scene") && Defaults.bSky && !Defaults.bSeaZ &&
                                                                  Defaults.WaterfallScaleZ == 1.0f && !Defaults.bSet);
  }
  struct FCase {
    const TCHAR* Name;
    FString MapBlock;
    FString GridBlock;
    const TCHAR* Expect;
  };
  const FString Six = TEXT(
      "[{\"id\":\"l1\",\"loc\":[600,0,100],\"colorSrgb\":\"#FFA552\",\"intensityCd\":50,\"radius\":300},"
      "{\"id\":\"l2\",\"loc\":[600,50,100],\"colorSrgb\":\"#FFA552\",\"intensityCd\":50,\"radius\":300},"
      "{\"id\":\"l3\",\"loc\":[600,100,100],\"colorSrgb\":\"#FFA552\",\"intensityCd\":50,\"radius\":300},"
      "{\"id\":\"l4\",\"loc\":[600,150,100],\"colorSrgb\":\"#FFA552\",\"intensityCd\":50,\"radius\":300},"
      "{\"id\":\"l5\",\"loc\":[600,200,100],\"colorSrgb\":\"#FFA552\",\"intensityCd\":50,\"radius\":300},"
      "{\"id\":\"l6\",\"loc\":[600,250,100],\"colorSrgb\":\"#FFA552\",\"intensityCd\":50,\"radius\":300}]");
  const FCase Cases[] = {
      {TEXT("grid board"), FString(), FString(ValidBlock), TEXT("conceptPaste is for map-image boards only")},
      {TEXT("not an object"), TEXT("[1]"), FString(), TEXT("conceptPaste must be an object")},
      {TEXT("no default"), BlockWith(TEXT("default"), FString(), true), FString(), TEXT("default must be")},
      {TEXT("default yes"), BlockWith(TEXT("default"), TEXT("\"yes\"")), FString(), TEXT("default must be")},
      {TEXT("unknown field"), BlockWith(TEXT("sheetMeshes"), TEXT("\"x\"")), FString(), TEXT("sheetMeshes is not a field")},
      {TEXT("no sheet"), BlockWith(TEXT("sheetMesh"), FString(), true), FString(), TEXT("sheetMesh is required")},
      {TEXT("no plate B"), BlockWith(TEXT("plateB"), FString(), true), FString(), TEXT("plateB is required")},
      {TEXT("never-cooked plate"), BlockWith(TEXT("plateB"), TEXT("\"/Game/EnvMaps/Data/X/T_B\"")), FString(), TEXT("plateB '/Game/EnvMaps/Data/X/T_B'")},
      {TEXT("object path"), BlockWith(TEXT("sheetMesh"), TEXT("\"/Game/EnvMaps/X/SM_S.SM_S\"")), FString(), TEXT("sheetMesh '")},
      {TEXT("bad variant"), BlockWith(TEXT("variant"), TEXT("\"Concept!\"")), FString(), TEXT("variant must be")},
      {TEXT("off = variant"), BlockWith(TEXT("offVariant"), TEXT("\"concept\"")), FString(), TEXT("offVariant must be")},
      {TEXT("camera pitch"), BlockWith(TEXT("camera"), TEXT("{\"pitch\":10}")), FString(), TEXT("camera needs")},
      {TEXT("camera field"), BlockWith(TEXT("camera"), TEXT("{\"fov\":35}")), FString(), TEXT("camera needs")},
      {TEXT("homography shape"), BlockWith(TEXT("homography"), TEXT("[[1,0,0],[0,1,0]]")), FString(), TEXT("homography needs")},
      {TEXT("homography far"), BlockWith(TEXT("homography"), TEXT("[[1,0,500],[0,1,0],[0,0,1]]")), FString(), TEXT("homography needs")},
      {TEXT("rect"), BlockWith(TEXT("rectB"), TEXT("[0,0,0,1080]")), FString(), TEXT("rectB needs")},
      {TEXT("feather"), BlockWith(TEXT("featherPx"), TEXT("500")), FString(), TEXT("featherPx must be")},
      {TEXT("outside"), BlockWith(TEXT("outside"), TEXT("\"wrap\"")), FString(), TEXT("outside must be")},
      {TEXT("cut"), BlockWith(TEXT("cut"), TEXT("{\"underFrameUU\":30}")), FString(), TEXT("cut needs")},
      {TEXT("grade mode"), BlockWith(TEXT("grade"), TEXT("{\"mode\":\"filmic\"}")), FString(), TEXT("grade needs")},
      {TEXT("grade fitScale count"), BlockWith(TEXT("grade"), TEXT("{\"fitScale\":[3,3]}")), FString(), TEXT("grade needs")},
      {TEXT("grade fitPower range"), BlockWith(TEXT("grade"), TEXT("{\"fitPower\":[1,1,3]}")), FString(), TEXT("grade needs")},
      {TEXT("grade devignette range"), BlockWith(TEXT("grade"), TEXT("{\"devignette\":1.5}")), FString(), TEXT("grade needs")},
      {TEXT("sea sky below"), BlockWith(TEXT("sea"), TEXT("{\"zUU\":-300,\"skyTopZUU\":-400}")), FString(), TEXT("sea needs")},
      {TEXT("sea segments"), BlockWith(TEXT("sea"), TEXT("{\"skySegments\":7}")), FString(), TEXT("sea needs")},
      {TEXT("hide name"), BlockWith(TEXT("hide"), TEXT("[\"tray\",\"props\"]")), FString(), TEXT("hide 'props'")},
      {TEXT("lights keep layout lights"), BlockWith(TEXT("hide"), TEXT("[\"tray\"]")), FString(), TEXT("hide needs \"layoutLights\"")},
      {TEXT("light colour"), BlockWith(TEXT("lights"), TEXT("[{\"id\":\"l\",\"loc\":[0,0,0],\"colorSrgb\":\"orange\",\"intensityCd\":5,\"radius\":9}]")), FString(), TEXT("lights[0] needs")},
      {TEXT("light duplicate"), BlockWith(TEXT("lights"), TEXT("[{\"id\":\"l\",\"loc\":[0,0,0],\"colorSrgb\":\"#FFFFFF\",\"intensityCd\":5,\"radius\":9},{\"id\":\"l\",\"loc\":[0,0,0],\"colorSrgb\":\"#FFFFFF\",\"intensityCd\":5,\"radius\":9}]")), FString(), TEXT("lights[1] needs")},
      {TEXT("light flicker"), BlockWith(TEXT("lights"), TEXT("[{\"id\":\"l\",\"loc\":[0,0,0],\"colorSrgb\":\"#FFFFFF\",\"intensityCd\":5,\"radius\":9,\"flicker\":{\"amp\":0.9}}]")), FString(), TEXT("lights[0] needs")},
      {TEXT("budget with the profile"), BlockWith(TEXT("lights"), Six), FString(), TEXT("conceptPaste lights 6 + light profile L points 1 > 6")},
      {TEXT("anim"), BlockWith(TEXT("anims"), TEXT("[{\"prop\":\"x\",\"swayDeg\":40,\"swayHz\":1}]")), FString(), TEXT("anims[0] needs")},
      {TEXT("wind id"), BlockWith(TEXT("winds"), TEXT("[\"banner ship\"]")), FString(), TEXT("winds[0] must be")},
      {TEXT("wind duplicate"), BlockWith(TEXT("winds"), TEXT("[\"b\",\"b\"]")), FString(), TEXT("winds[1] must be")},
      {TEXT("winds not a list"), BlockWith(TEXT("winds"), TEXT("{\"b\":1}")), FString(), TEXT("winds must be")},
      {TEXT("blob"), BlockWith(TEXT("shadowBlobs"), TEXT("[{\"id\":\"b\",\"loc\":[0,0],\"diameterUU\":70}]")), FString(), TEXT("shadowBlobs[0] needs")},
      {TEXT("flow amplitude"), BlockWith(TEXT("flow"), TEXT("{\"regions\":[{\"id\":\"w\",\"rectPx\":[0,0,10,10],\"velocityPx\":[0,1],\"ampPx\":9}]}")), FString(), TEXT("flow.regions[0] needs")},
      {TEXT("flow regions"), BlockWith(TEXT("flow"), TEXT("{\"regions\":[{},{},{}]}")), FString(), TEXT("flow.regions must be")},
      {TEXT("flow field"), BlockWith(TEXT("flow"), TEXT("{\"river\":{}}")), FString(), TEXT("flow must be an object")},
      {TEXT("sea flow without the sea"), BlockWith(TEXT("sea"), FString(), true), FString(), TEXT("flow.sea needs the sea layer")},
      // ENV-MAPS P8 lit3d
      {TEXT("lit3d on a grid"), FString(), Lit3dBlock(), TEXT("conceptPaste is for map-image boards only")},
      {TEXT("mode name"), BlockWith(TEXT("mode"), TEXT("\"sheet\"")), FString(), TEXT("mode must be")},
      {TEXT("mode lit3d without the object"), BlockWith(TEXT("mode"), TEXT("\"lit3d\"")), FString(), TEXT("mode \"lit3d\" needs the lit3d object")},
      {TEXT("lit3d not an object"), BlockWith(TEXT("lit3d"), TEXT("[1]")), FString(), TEXT("lit3d must be an object")},
      {TEXT("lit3d unknown field"), Lit3dWith(TEXT("meshes"), TEXT("[]")), FString(), TEXT("lit3d.meshes is not a field")},
      {TEXT("lit3d no required"), Lit3dWith(TEXT("required"), FString(), true), FString(), TEXT("lit3d.required must be")},
      {TEXT("lit3d required outside EnvMaps"), Lit3dWith(TEXT("required"), TEXT("[\"/Game/EnvKit/X/SM_X\"]")), FString(), TEXT("lit3d.required[0]")},
      {TEXT("lit3d required never-cooked"), Lit3dWith(TEXT("required"), TEXT("[\"/Game/EnvMaps/Data/SM_X\"]")), FString(), TEXT("lit3d.required[0]")},
      {TEXT("lit3d variant = the paste's"), Lit3dWith(TEXT("variant"), TEXT("\"concept\"")), FString(), TEXT("lit3d.variant must differ")},
      {TEXT("lit3d variant = the off variant"), Lit3dWith(TEXT("variant"), TEXT("\"p5c\"")), FString(), TEXT("lit3d.variant must differ")},
      {TEXT("lit3d sky"), Lit3dWith(TEXT("sky"), TEXT("1")), FString(), TEXT("lit3d.sky must be a bool")},
      {TEXT("lit3d sea above the tray"), Lit3dWith(TEXT("seaZUU"), TEXT("0")), FString(), TEXT("lit3d.seaZUU must be")},
      {TEXT("lit3d falls"), Lit3dWith(TEXT("waterfallScaleZ"), TEXT("9")), FString(), TEXT("lit3d.waterfallScaleZ must be")},
      {TEXT("lit3d hide name"), Lit3dWith(TEXT("hide"), TEXT("[\"island\"]")), FString(), TEXT("lit3d.hide 'island'")},
      {TEXT("lit3d lights keep layout lights"), Lit3dWith(TEXT("hide"), TEXT("[\"tray\"]")), FString(), TEXT("lit3d.lights replace the env-layout lights")},
      {TEXT("lit3d light"), Lit3dWith(TEXT("lights"), TEXT("[{\"id\":\"l\"}]")), FString(), TEXT("lit3d.lights[0] needs")},
      {TEXT("lit3d budget with the profile"), Lit3dWith(TEXT("lights"), Six), FString(), TEXT("conceptPaste lights 6 + light profile L points 1 > 6")},
      {TEXT("lit3d anim"), Lit3dWith(TEXT("anims"), TEXT("[{\"prop\":\"x\"}]")), FString(), TEXT("lit3d.anims[0] needs")},
      {TEXT("lit3d caster pattern"), Lit3dWith(TEXT("casters"), TEXT("[\"is*land\"]")), FString(), TEXT("lit3d.casters[0] must be")},
      {TEXT("lit3d giOff duplicate"), Lit3dWith(TEXT("giOff"), TEXT("[\"a\",\"a\"]")), FString(), TEXT("lit3d.giOff[1] must be")},
      {TEXT("lit3d winds not a list"), Lit3dWith(TEXT("winds"), TEXT("\"tree-*\"")), FString(), TEXT("lit3d.winds must be")},
  };
  for (const FCase& C : Cases) {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    const bool bParsed = Data.ParseJson(Doc(C.MapBlock, C.GridBlock), Errors);
    const FString All = FString::Join(Errors, TEXT(" | "));
    TestTrue(FString::Printf(TEXT("%s: rejected with '%s' (got: %s)"), C.Name, C.Expect, *All), !bParsed && All.Contains(C.Expect));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteModeTest,
    "Unmatched.S08.ConceptPaste.Mode decision table: flags, variants, the block default, the gate; command line; fallback",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteModeTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  FS08ConceptPasteSpec On;
  On.bSet = true;
  On.bDefaultOn = true;
  On.OffVariant = TEXT("p5c");
  FS08ConceptPasteSpec Off;
  Off.bSet = true;
  struct FCase {
    const TCHAR* Name;
    const FS08ConceptPasteSpec* Spec;
    const TCHAR* Cmd;
    bool bGate;
    bool bOn;
    const TCHAR* Reason;
    bool bOverride;
    const TCHAR* Variant;
  };
  const FS08ConceptPasteSpec NoBlock;
  const FCase Cases[] = {
      {TEXT("on by default"), &On, TEXT(""), true, true, TEXT("default"), true, TEXT("concept")},
      {TEXT("off by default (Marmoreal: the command line decides the layout, as before)"), &Off, TEXT(""), true, false, TEXT("default"), false, TEXT("")},
      {TEXT("gate closed"), &On, TEXT(""), false, false, TEXT("gate"), false, TEXT("")},
      {TEXT("no block"), &NoBlock, TEXT("-ConceptPaste"), true, false, TEXT("no-block"), false, TEXT("")},
      {TEXT("-ConceptPaste=0"), &On, TEXT("-ConceptPaste=0"), true, false, TEXT("flag-off"), false, TEXT("")},
      {TEXT("-NoConceptPaste with the concept variant -> base"), &On, TEXT("-NoConceptPaste -EnvLayoutVariant=concept"), true, false, TEXT("flag-off"), true, TEXT("")},
      {TEXT("-ConceptPaste=off with the off variant -> base"), &On, TEXT("-ConceptPaste=off -EnvLayoutVariant=p5c"), true, false, TEXT("flag-off"), true, TEXT("")},
      {TEXT("-ConceptPaste on an off block"), &Off, TEXT("-ConceptPaste"), true, true, TEXT("flag-on"), true, TEXT("concept")},
      {TEXT("-ConceptPaste=TRUE wins over another variant"), &Off, TEXT("-ConceptPaste=TRUE -EnvLayoutVariant=user"), true, true, TEXT("flag-on"), true, TEXT("concept")},
      {TEXT("-EnvLayoutVariant=concept"), &Off, TEXT("-EnvLayoutVariant=concept"), true, true, TEXT("variant"), true, TEXT("concept")},
      {TEXT("-EnvLayoutVariant=p5c -> off + the base layout"), &On, TEXT("-EnvLayoutVariant=p5c"), true, false, TEXT("variant-off"), true, TEXT("")},
      {TEXT("-EnvLayoutVariant=user -> off, that overlay applies"), &On, TEXT("-EnvLayoutVariant=user"), true, false, TEXT("variant-other"), false, TEXT("")},
      {TEXT("p5c on a block without an off variant = another variant"), &Off, TEXT("-EnvLayoutVariant=p5c"), true, false, TEXT("variant-other"), false, TEXT("")},
      {TEXT("the calibration flag is not the paste flag"), &Off, TEXT("-ConceptPasteCalib"), true, false, TEXT("default"), false, TEXT("")},
  };
  for (const FCase& C : Cases) {
    const FS08ConceptPasteMode M = S08ConceptPaste::ResolveMode(*C.Spec, Inputs(C.Cmd), C.bGate);
    TestTrue(FString::Printf(TEXT("%s: on=%d reason=%s override=%d variant='%s'"), C.Name, M.bOn ? 1 : 0, *M.Reason,
                             M.bOverrideVariant ? 1 : 0, *M.Variant),
             M.bOn == C.bOn && M.Reason == C.Reason && M.bOverrideVariant == C.bOverride && M.Variant == C.Variant);
  }
  // ENV-MAPS P8: the kinds - Sarpedon-like (lit3d default, paste selectable) and a paste default with a lit3d object
  FS08ConceptPasteSpec Lit;
  Lit.bSet = true;
  Lit.bDefaultOn = true;
  Lit.OffVariant = TEXT("p5c");
  Lit.DefaultKind = ES08ConceptKind::Lit3d;
  Lit.Lit3d.bSet = true;
  FS08ConceptPasteSpec PasteFirst = Lit;
  PasteFirst.DefaultKind = ES08ConceptKind::Paste;
  PasteFirst.bDefaultOn = false;
  struct FKindCase {
    const TCHAR* Name;
    const FS08ConceptPasteSpec* Spec;
    const TCHAR* Cmd;
    bool bOn;
    const TCHAR* Reason;
    ES08ConceptKind Kind;
    bool bOverride;
    const TCHAR* Variant;
  };
  const ES08ConceptKind P = ES08ConceptKind::Paste, L3 = ES08ConceptKind::Lit3d;
  const FKindCase KindCases[] = {
      {TEXT("lit3d by default -> the scene overlay"), &Lit, TEXT(""), true, TEXT("default"), L3, true, TEXT("scene")},
      {TEXT("a bare -ConceptPaste = the default kind"), &Lit, TEXT("-ConceptPaste"), true, TEXT("flag-on"), L3, true, TEXT("scene")},
      {TEXT("-ConceptPaste=paste -> the P7 look"), &Lit, TEXT("-ConceptPaste=paste"), true, TEXT("flag-on"), P, true, TEXT("concept")},
      {TEXT("-ConceptPaste=LIT3D on a paste-default block"), &PasteFirst, TEXT("-ConceptPaste=LIT3D"), true, TEXT("flag-on"), L3, true, TEXT("scene")},
      {TEXT("-ConceptPaste=lit3d on a paste-only block -> the paste"), &On, TEXT("-ConceptPaste=lit3d"), true, TEXT("flag-on"), P, true, TEXT("concept")},
      {TEXT("-EnvLayoutVariant=scene -> lit3d"), &PasteFirst, TEXT("-EnvLayoutVariant=scene"), true, TEXT("variant"), L3, true, TEXT("scene")},
      {TEXT("-EnvLayoutVariant=concept -> paste"), &Lit, TEXT("-EnvLayoutVariant=concept"), true, TEXT("variant"), P, true, TEXT("concept")},
      {TEXT("-ConceptPaste with the scene variant -> lit3d"), &PasteFirst, TEXT("-ConceptPaste -EnvLayoutVariant=scene"), true, TEXT("flag-on"), L3, true, TEXT("scene")},
      {TEXT("-ConceptPaste=0 -> off, the command line decides"), &Lit, TEXT("-ConceptPaste=0"), false, TEXT("flag-off"), P, false, TEXT("")},
      {TEXT("-NoConceptPaste with the scene variant -> base"), &Lit, TEXT("-NoConceptPaste -EnvLayoutVariant=scene"), false, TEXT("flag-off"), P, true, TEXT("")},
      {TEXT("-EnvLayoutVariant=p5c -> off + base"), &Lit, TEXT("-EnvLayoutVariant=p5c"), false, TEXT("variant-off"), P, true, TEXT("")},
      {TEXT("-EnvLayoutVariant=user -> off, that overlay"), &Lit, TEXT("-EnvLayoutVariant=user"), false, TEXT("variant-other"), P, false, TEXT("")},
      {TEXT("scene variant on a paste-only block = another variant"), &On, TEXT("-EnvLayoutVariant=scene"), false, TEXT("variant-other"), P, false, TEXT("")},
  };
  for (const FKindCase& C : KindCases) {
    const FS08ConceptPasteMode M = S08ConceptPaste::ResolveMode(*C.Spec, Inputs(C.Cmd), true);
    TestTrue(FString::Printf(TEXT("%s: on=%d reason=%s kind=%s override=%d variant='%s'"), C.Name, M.bOn ? 1 : 0, *M.Reason,
                             S08ConceptKindName(M.Kind), M.bOverrideVariant ? 1 : 0, *M.Variant),
             M.bOn == C.bOn && M.Reason == C.Reason && (!M.bOn || M.Kind == C.Kind) && M.bOverrideVariant == C.bOverride &&
                 M.Variant == C.Variant);
  }
  {
    const FS08ConceptPasteInputs K = Inputs(TEXT("-ConceptPaste=Lit3D -ArtPreviewLightsOff"));
    TestTrue("inputs: -ConceptPaste=<kind> is on with the kind, case-insensitive", K.bFlagOn && K.bKindSet &&
                                                                               K.Kind == ES08ConceptKind::Lit3d && K.FlagText == TEXT("lit3d"));
    TestTrue("inputs: -ArtPreviewLightsOff", K.bLightsOff && !Inputs(TEXT("-ConceptPaste")).bLightsOff);
    TestTrue("inputs: a later =1 drops the kind", !Inputs(TEXT("-ConceptPaste=paste -ConceptPaste=1")).bKindSet);
    const FS08ConceptPasteMode F = S08ConceptPaste::FallbackOff(Lit, Inputs(TEXT("-EnvLayoutVariant=scene")), TEXT("missing-assets"));
    TestTrue("fallback, asked for the scene overlay: the base (P5c)", !F.bOn && F.bOverrideVariant && F.Variant.IsEmpty());
    ES08ConceptKind Kind = ES08ConceptKind::Paste;
    TestTrue("kind names", S08ConceptPaste::KindFromName(TEXT("lit3d"), Kind) && Kind == ES08ConceptKind::Lit3d &&
                               S08ConceptPaste::KindFromName(TEXT("PASTE"), Kind) && Kind == ES08ConceptKind::Paste &&
                               !S08ConceptPaste::KindFromName(TEXT("3d"), Kind) &&
                               FString(S08ConceptKindName(ES08ConceptKind::Lit3d)) == TEXT("lit3d"));
    // prop patterns (winds / casters / giOff)
    const TArray<FString> Ids = {TEXT("island"), TEXT("tree-1"), TEXT("ship-hull"), TEXT("tree-2"), TEXT("treeline")};
    TArray<FString> Unmatched;
    const TArray<int32> Got = S08ConceptPaste::MatchProps({TEXT("tree-*"), TEXT("island"), TEXT("tree-1"), TEXT("fort*"), TEXT("ship")},
                                                          Ids, &Unmatched);
    TestTrue("MatchProps: prefixes, exact ids, each index once, ascending", Got == TArray<int32>({0, 1, 3}));
    TestTrue("MatchProps: the patterns that named nothing", Unmatched == TArray<FString>({TEXT("fort*"), TEXT("ship")}));
  }
  const FS08ConceptPasteInputs In = Inputs(TEXT("game -log -ConceptPasteCalib -EnvLayoutVariant=\"p5c\" -conceptpaste=1"));
  TestTrue("inputs: calib, quoted variant, case-insensitive flag",
           In.bCalib && In.Variant == TEXT("p5c") && In.bFlagOn && !In.bFlagOff && In.FlagText == TEXT("1"));
  TestTrue("inputs: an unknown flag value is neither on nor off", !Inputs(TEXT("-ConceptPaste=maybe")).bFlagOn &&
                                                                     !Inputs(TEXT("-ConceptPaste=maybe")).bFlagOff);
  TestTrue("inputs: -NoConceptPaste wins (last)", Inputs(TEXT("-ConceptPaste -NoConceptPaste")).bFlagOff);
  // the fallback after the decision: off, and the base layout only when the command line asked for the concept overlay
  FS08ConceptPasteMode F = S08ConceptPaste::FallbackOff(On, Inputs(TEXT("")), TEXT("missing-assets"));
  TestTrue("fallback, default on: off, the command line decides (no variant)", !F.bOn && F.Reason == TEXT("missing-assets") && !F.bOverrideVariant);
  F = S08ConceptPaste::FallbackOff(Off, Inputs(TEXT("-EnvLayoutVariant=concept")), TEXT("overlay-absent"));
  TestTrue("fallback, asked for the concept overlay: the base", !F.bOn && F.bOverrideVariant && F.Variant.IsEmpty());
  {
    FScope Scope(TEXT("-ConceptPaste=0 -EnvLayoutVariant=user"));
    const FS08ConceptPasteInputs Fake = FS08ConceptPasteInputs::FromCommandLine();
    TestTrue("the test override replaces the command line", Fake.bFlagOff && Fake.Variant == TEXT("user"));
  }
  TestFalse("override reset", FS08ConceptPasteInputs::FromCommandLine().FlagText == TEXT("0") &&
                                  FS08ConceptPasteInputs::FromCommandLine().Variant == TEXT("user"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteShippedTest,
    "Unmatched.S08.ConceptPaste.Shipped Sarpedon ON by default, Marmoreal present but OFF, no grid block, 1 key + 6 points",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteShippedTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("shipped profiles parse: ") + FString::Join(Errors, TEXT(" | ")),
                Data.LoadFile(FS08BoardArtData::DefaultPath(), Errors))) {
    return false;
  }
  TestTrue("revision >= 15", Data.Revision >= 15);
  const FS08BoardArtProfile* Sarpedon = Find(Data, TEXT("sarpedon-original"));
  const FS08BoardArtProfile* Marmoreal = Find(Data, TEXT("marmoreal-original"));
  if (!TestNotNull("sarpedon-original", Sarpedon) || !TestNotNull("marmoreal-original", Marmoreal)) return false;
  for (const FS08BoardArtProfile& B : Data.Boards) {
    if (B.Surface != ES08BoardSurface::MapImage) TestFalse(B.Id + TEXT(": a grid profile has no concept paste"), B.ConceptPaste.bSet);
    for (const FString& Path : B.ConceptPaste.AssetPaths()) {
      TestTrue(B.Id + TEXT(": cooked asset root ") + Path,
               Path.StartsWith(S08ConceptPasteSpec::AssetRoot) && !Path.StartsWith(S08ConceptPasteSpec::NeverCookRoot));
    }
  }
  const FS08ConceptPasteSpec& S = Sarpedon->ConceptPaste;
  TestTrue("sarpedon: block, ON by default, concept overlay, p5c = off", S.bSet && S.bDefaultOn &&
                                                                            S.Variant == TEXT("concept") && S.OffVariant == TEXT("p5c"));
  TestTrue("sarpedon: centre + outskirts plates, sea layer", !S.PlateAPath.IsEmpty() && !S.PlateBPath.IsEmpty() &&
                                                               !S.SeaPlatePath.IsEmpty() && S.Sea.bSet && !S.bClampOutside);
  // P7 tune: the measured fit of the engine tone curve (selfcal at C0) + the vignette undone on the painted layer
  TestTrue("sarpedon: measured tone fit grade (aces-inverse x fitScale ^ 1 / fitPower, emissiveScale 1, devignette 0.4)",
           S.Grade == ES08ConceptGrade::AcesInverse && S.bHasEmissiveScale && S.EmissiveScale == 1.0f &&
               S.FitScale.GetMin() > 2.0 && S.FitScale.GetMax() < 4.0 && S.FitPower.GetMin() > 0.9 && S.FitPower.GetMax() < 1.2 &&
               FMath::IsNearlyEqual(S.Devignette, 0.4f));
  {
    const FS08ConceptMaterialParams Mp = S08ConceptPaste::MaterialParams(S, Sarpedon->Map.FrameHalfUU(), false, true,
                                                                        S.Grade, S.EmissiveScale, false);
    TestTrue("sarpedon: MID GradeScale = fitScale, GradePow = 1 / fitPower, Devignette, grade mode 2",
             FMath::IsNearlyEqual(Mp.GradeScale.R, static_cast<float>(S.FitScale.X)) &&
                 FMath::IsNearlyEqual(Mp.GradeScale.B, static_cast<float>(S.FitScale.Z)) &&
                 FMath::IsNearlyEqual(Mp.GradePow.G, static_cast<float>(1.0 / S.FitPower.Y), 1e-6f) &&
                 FMath::IsNearlyEqual(Mp.Devignette, 0.4f) && Mp.GradeMode == 2.0f);
  }
  TestTrue("sarpedon: hides the painted-over parts", S.Hide.bTray && S.Hide.bGround && S.Hide.bSea && S.Hide.bWaterfalls &&
                                                         S.Hide.bBackdrop && S.Hide.bFog && S.Hide.bBaseProps && S.Hide.bBaseFx &&
                                                         S.Hide.bLayoutLights);
  TestTrue("sarpedon: the cut under the 3D frame-002 foot", S.CutHalf(Sarpedon->Map.FrameHalfUU()).Equals(FVector2D(467.66667, 310.66667), 1e-3));
  const FS08LightProfile* Night = Data.LightFor(*Sarpedon);
  TestTrue(FString::Printf(TEXT("sarpedon: profile points %d + concept lights %d = 6 (1 key + <= 6)"), Night ? Night->Points.Num() : -1,
                           S.Lights.Num()),
           Night && Night->Points.Num() + S.Lights.Num() <= S08ConceptPasteSpec::CombinedPointBudget && S.Lights.Num() >= 1);
  TestTrue("sarpedon: the key light untouched (-55, 30, 0)", Night && Night->Directional.Rotation.Equals(FRotator(-55, 30, 0), 1e-4));
  FVector2D Px;
  const FS08ConceptCamera& C0 = S.Camera;
  TestTrue("sarpedon: the block's C0 puts lantern-left on its design pixel",
           C0.Project(FVector(-565.9, -46.1, 154.3), Px) && FVector2D::Distance(Px, FVector2D(301, 393)) <= 0.15);
  // tools/art/concept_paste/cp_bake.py bakes the registration into the texels: identity here, its rects (the contract)
  TestTrue("sarpedon: rectified plates (identity homography)", S.Homography.IsIdentity());
  TestTrue("sarpedon: plate A = the concept frame, plate B / sea / water = the outpainted range",
           S.RectA == FVector4(0, 0, 1920, 1080) && S.RectB == FVector4(-384, -216, 2688, 1512) && !S.WaterMaskPath.IsEmpty());
  TestTrue("sarpedon: the waterfall + bay surf flow regions and the sea flow", S.Flows.Num() == 2 && S.SeaFlow.bSet);
  for (const FS08ConceptLight& L : S.Lights) {
    const FDetail* D = nullptr;
    for (const FDetail& Candidate : Details) {
      if (L.Id == Candidate.Id) D = &Candidate;
    }
    if (D) {
      TestTrue(L.Id + TEXT(": the light stands on its detail (XY)"), FVector2D(L.Loc.X, L.Loc.Y).Equals(FVector2D(D->World.X, D->World.Y), 0.11));
    }
    TestTrue(L.Id + TEXT(": outside the painted map"), FMath::Abs(L.Loc.X) > Sarpedon->Map.HalfUU().X ||
                                                           FMath::Abs(L.Loc.Y) > Sarpedon->Map.HalfUU().Y);
  }
  TestTrue("sarpedon: the banner cloth's material wind (P7c, live runs only)",
           S.WindProps.Num() == 1 && S.WindProps[0] == TEXT("banner-ship"));
  // ENV-MAPS P8: Sarpedon's lit3d object (task doc section 4 P8.2)
  const FS08ConceptLit3dSpec& L3 = S.Lit3d;
  TestTrue("sarpedon: mode lit3d, the scene overlay, a manifest", L3.bSet && S.DefaultKind == ES08ConceptKind::Lit3d &&
                                                                     L3.Variant == TEXT("scene") && !L3.ManifestPath.IsEmpty());
  TestTrue("sarpedon lit3d: M_EnvScene and the island are required",
           L3.Required.Contains(S08ConceptPasteSpec::SceneMaterialPath) &&
               L3.Required.Contains(TEXT("/Game/EnvMaps/Sarpedon/Scene/SM_Env_S_Island")));
  TestEqual("sarpedon lit3d: hide (the sea ring and the waterfalls come back)", L3.Hide.Names(),
            FString(TEXT("tray+ground+backdrop+fog+baseProps+baseFx+layoutLights")));
  TestTrue("sarpedon lit3d: the sky cylinder stays, the sea ring at -300 under the cliffs (R3)",
           L3.bSky && S.Sea.bSet && L3.bSeaZ && L3.SeaZUU == -300.0f && L3.WaterfallScaleZ >= 1.0f);
  TestTrue(FString::Printf(TEXT("sarpedon lit3d: profile points %d + 5 lights <= 6"), Night ? Night->Points.Num() : -1),
           Night && L3.Lights.Num() == 5 && Night->Points.Num() + L3.Lights.Num() <= S08ConceptPasteSpec::CombinedPointBudget);
  {
    // P8.3 tune: lantern-deck-n's point moved to lantern-bay (the painted warm pool on the beach; the dock was over-lit)
    TSet<FString> Want = {TEXT("fire-fort"), TEXT("fire-brazier"), TEXT("lantern-left"), TEXT("lantern-bay"), TEXT("lantern-deck-se")};
    for (const FS08ConceptLight& L : L3.Lights) {
      Want.Remove(L.Id);
      TestTrue(L.Id + TEXT(": flickers"), L.FlickerAmp > 0.0f && L.FlickerHz > 0.0f);
      for (const FDetail& D : Details) {
        if (L.Id == D.Id) {
          TestTrue(L.Id + TEXT(": on its design detail (XY)"),
                   FVector2D(L.Loc.X, L.Loc.Y).Equals(FVector2D(D.World.X, D.World.Y), 0.11));
        }
      }
    }
    TestEqual("sarpedon lit3d: the five design lights", Want.Num(), 0);
  }
  TestTrue("sarpedon lit3d: banner wind, casters for the island masses",
           L3.WindProps.Contains(TEXT("banner-ship")) && L3.Casters.Num() > 0);
  {
    // the scene overlay (track A, EnvLayouts/sarpedon.scene.layout.json) once it exists: every caster / wind pattern names
    // one of its props and the required island mesh is placed
    const FString Overlay = S08EnvLayout::OverlayFileFor(S08EnvLayout::DefaultDir(), TEXT("sarpedon"), L3.Variant);
    FString Text;
    TSharedPtr<FJsonObject> Root;
    FString Problem;
    if (FFileHelper::LoadFileToString(Text, *Overlay) && FS08Contracts::TryParseJsonObject(Text, Root, Problem) && Root.IsValid()) {
      TArray<FString> Ids, Meshes;
      const TSharedPtr<FJsonObject>* Props = nullptr;
      const TArray<TSharedPtr<FJsonValue>>* Added = nullptr;
      if (Root->TryGetObjectField(TEXT("props"), Props) && Props && (*Props)->TryGetArrayField(TEXT("add"), Added) && Added) {
        for (const TSharedPtr<FJsonValue>& V : *Added) {
          const TSharedPtr<FJsonObject>* P = nullptr;
          FString Id, Mesh;
          if (V.IsValid() && V->TryGetObject(P) && P && (*P)->TryGetStringField(TEXT("id"), Id)) Ids.Add(Id);
          if (V.IsValid() && V->TryGetObject(P) && P && (*P)->TryGetStringField(TEXT("mesh"), Mesh)) Meshes.Add(PackageOf(Mesh));
        }
      }
      for (const FString& Pattern : L3.Casters) {
        TArray<FString> Unmatched;
        S08ConceptPaste::MatchProps({Pattern}, Ids, &Unmatched);
        TestTrue(TEXT("scene overlay: caster pattern ") + Pattern + TEXT(" names a prop"), Unmatched.IsEmpty());
      }
      TestTrue("scene overlay: the island is placed", Meshes.Contains(TEXT("/Game/EnvMaps/Sarpedon/Scene/SM_Env_S_Island")));
    } else {
      AddWarning(TEXT("EnvLayouts/sarpedon.scene.layout.json not there yet (track A): the caster patterns were not checked against it"));
    }
  }
  const FS08ConceptPasteSpec& M = Marmoreal->ConceptPaste;
  TestTrue("marmoreal: no lit3d (the accepted look, paste comparison only)", !M.Lit3d.bSet && M.DefaultKind == ES08ConceptKind::Paste);
  TestTrue("marmoreal: no material wind", M.WindProps.IsEmpty());
  TestTrue("marmoreal: block present, OFF by default (the accepted look)", M.bSet && !M.bDefaultOn && M.Variant == TEXT("concept"));
  TestTrue("marmoreal: no lights of its own, the layout lights stay, no sea", M.Lights.IsEmpty() && !M.Hide.bLayoutLights && !M.Sea.bSet);
  TestTrue("marmoreal: rectified plates A + B, edge clamp", M.Homography.IsIdentity() && !M.PlateAPath.IsEmpty() &&
                                                                M.RectB == FVector4(-384, -216, 2688, 1512) && M.bClampOutside);
  // what the board actor decides without any flag
  const FS08ConceptPasteInputs NoFlags = Inputs(TEXT("Unmatched -game -ArtPreview -ArtPreviewDiorama"));
  const FS08ConceptPasteMode SarMode = S08ConceptPaste::ResolveMode(S, NoFlags, true);
  const FS08ConceptPasteMode MarMode = S08ConceptPaste::ResolveMode(M, NoFlags, true);
  // ENV-MAPS P8: the default is the lit 3D island (the scene overlay); the P7 paste stays selectable
  TestTrue("sarpedon default: on, lit3d, the scene overlay", SarMode.bOn && SarMode.Reason == TEXT("default") &&
                                                                 SarMode.Kind == ES08ConceptKind::Lit3d && SarMode.bOverrideVariant &&
                                                                 SarMode.Variant == TEXT("scene"));
  const FS08ConceptPasteMode SarPaste = S08ConceptPaste::ResolveMode(S, Inputs(TEXT("-ConceptPaste=paste")), true);
  TestTrue("sarpedon -ConceptPaste=paste: the P7 look (concept overlay)", SarPaste.bOn && SarPaste.Kind == ES08ConceptKind::Paste &&
                                                                         SarPaste.Variant == TEXT("concept"));
  const FS08ConceptPasteMode SarOff = S08ConceptPaste::ResolveMode(S, Inputs(TEXT("-ConceptPaste=0")), true);
  TestTrue("sarpedon -ConceptPaste=0: off, the command line (no variant) = the base layout", !SarOff.bOn && !SarOff.bOverrideVariant);
  TestTrue("marmoreal default: off, the env layout reads the command line exactly as before",
           !MarMode.bOn && MarMode.Reason == TEXT("default") && !MarMode.bOverrideVariant);
  const FS08ConceptPasteMode P5c = S08ConceptPaste::ResolveMode(S, Inputs(TEXT("-EnvLayoutVariant=p5c")), true);
  TestTrue("sarpedon -EnvLayoutVariant=p5c: off, the base layout (P5c)", !P5c.bOn && P5c.bOverrideVariant && P5c.Variant.IsEmpty());
  const FS08ConceptPasteMode MarOn = S08ConceptPaste::ResolveMode(M, Inputs(TEXT("-ConceptPaste")), true);
  TestTrue("marmoreal -ConceptPaste: on for the comparison", MarOn.bOn && MarOn.Variant == TEXT("concept"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteGeometryTest,
    "Unmatched.S08.ConceptPaste.Geometry sea plane + sky cylinder, shader mirror (cut, plates, feather), grade, flicker / sway",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteGeometryTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  FS08ConceptSeaSpec Sea;
  Sea.bSet = true;
  Sea.SkyTopZUU = 600.0f;
  const FTransform Plane = S08ConceptPaste::SeaPlaneTransform(Sea);
  TestTrue("sea plane: 2 R square at the sea level around the centre",
           Plane.GetTranslation().Equals(FVector(0, -45, -300), 1e-6) && Plane.GetScale3D().Equals(FVector(38, 38, 1), 1e-6) &&
               Plane.GetRotation().Equals(FQuat::Identity, 1e-9));
  const TArray<FTransform> Sky = S08ConceptPaste::SkySegmentTransforms(Sea);
  if (TestEqual("48 sky segments", Sky.Num(), 48)) {
    int32 Ok = 0;
    for (int32 I = 0; I < Sky.Num(); ++I) {
      const FTransform& T = Sky[I];
      const FVector C = T.GetTranslation();
      const FVector ToAxis = (FVector(0, -45, C.Z) - C).GetSafeNormal();
      const FVector LocalZ = T.GetRotation().RotateVector(FVector::UpVector);
      const FVector LocalY = T.GetRotation().RotateVector(FVector::RightVector);
      // the engine plane spans local X / Y +-50 (scaled): bottom corners on the circle, Z sea .. sky top
      const FVector BL = T.TransformPosition(FVector(-50, -50, 0)), BR = T.TransformPosition(FVector(50, -50, 0));
      const FVector TL = T.TransformPosition(FVector(-50, 50, 0));
      // local +X runs towards the lower angle: this segment's left corner is the next one's right corner
      const FVector NextBR = Sky[(I + 1) % Sky.Num()].TransformPosition(FVector(50, -50, 0));
      const double RL = FVector2D::Distance(FVector2D(BL.X, BL.Y), FVector2D(0, -45));
      const double RR = FVector2D::Distance(FVector2D(BR.X, BR.Y), FVector2D(0, -45));
      const bool bSegment = LocalZ.Equals(ToAxis, 1e-6) && LocalY.Equals(FVector::UpVector, 1e-6) &&
                            FMath::IsNearlyEqual(RL, 1900.0, 0.01) && FMath::IsNearlyEqual(RR, 1900.0, 0.01) &&
                            FMath::IsNearlyEqual(BL.Z, -300.0, 1e-6) && FMath::IsNearlyEqual(TL.Z, 600.0, 1e-6) &&
                            BL.Equals(NextBR, 0.01);  // contiguous: no gap between the chords
      Ok += bSegment ? 1 : 0;
    }
    TestEqual("every segment: inward normal, up, corners on the circle, sea .. sky top, contiguous", Ok, 48);
  }
  // the shader mirror on a Sarpedon-like block
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("valid block", Data.ParseJson(Doc(ValidBlock), Errors))) return false;
  FS08ConceptPasteSpec S = Find(Data, TEXT("cpmap"))->ConceptPaste;
  const FS08ConceptMaterialParams P =
      S08ConceptPaste::MaterialParams(S, FrameHalf, false, true, ES08ConceptGrade::AcesInverse, 4.14106f, false);
  const FS08ConceptMaterialParams PSea =
      S08ConceptPaste::MaterialParams(S, FrameHalf, true, true, ES08ConceptGrade::AcesInverse, 4.14106f, false);
  TestTrue("sheet MID: plate A, alpha, clip outside, cut on, grade 2", P.UseA == 1.0f && P.AlphaWeight == 1.0f && P.OutsideKeep == 0.0f &&
                                                                         P.Cut.A == 1.0f && P.GradeMode == 2.0f && P.EmissiveScale == 4.14106f &&
                                                                         FMath::IsNearlyEqual(P.GainLinear, 0.9638f));
  TestTrue("sea MID: no plate A, opaque, edge clamp, no cut", PSea.UseA == 0.0f && PSea.AlphaWeight == 0.0f && PSea.OutsideKeep == 1.0f &&
                                                                  PSea.Cut.A == 0.0f);
  TestTrue("sheet flow: the region, its velocity and amplitude; no Z gate",
           P.FlowRect0 == FLinearColor(640.0f, 885.0f, 361.0f, 411.0f) && P.FlowVel0 == FLinearColor(0.0f, 28.0f, 1.5f, 0.0f) &&
               P.FlowRect1.B == 0.0f && P.FlowMaxZ > 1.0e5f);
  TestTrue("sea flow: the whole plate B below the sea level + 1", PSea.FlowRect0 == PSea.RectB && PSea.FlowVel0.B == 1.2f &&
                                                                      PSea.FlowMaxZ == -299.0f && PSea.FlowRect1.B == 0.0f);
  TestTrue("frozen runs: no flow amplitude", S08ConceptPaste::MaterialParams(S, FrameHalf, false, true, ES08ConceptGrade::Lut, 1.0f,
                                                                             false, true).FlowVel0.B == 0.0f);
  TestTrue("camera parameters = C0", FVector(P.CamPos.R, P.CamPos.G, P.CamPos.B).Equals(S.Camera.Location(), 0.01) &&
                                         FMath::IsNearlyEqual(P.CamTan.B, 1920.0f) && FMath::IsNearlyEqual(P.CamTan.A, 1080.0f));
  FS08ConceptShaderSample Smp = S08ConceptPaste::ShaderSample(P, FVector::ZeroVector);
  TestTrue("the map centre: in front, under the map -> cut", Smp.bInFront && Smp.bCut && Smp.C0Px.Equals(FVector2D(960, 540), 1e-2));
  TestTrue("the map centre: concept px = the homography of C0 px", Smp.ConceptPx.Equals(S.Homography.Apply(Smp.C0Px), 1e-2));
  TestFalse("the sea layer is never cut", S08ConceptPaste::ShaderSample(PSea, FVector(0, 0, -300)).bCut);
  TestTrue("the cut ends 2 uu under the frame foot (X)", S08ConceptPaste::ShaderSample(P, FVector(467.0, 0, -3)).bCut &&
                                                            !S08ConceptPaste::ShaderSample(P, FVector(468.5, 0, -3)).bCut);
  TestTrue("the cut ends 2 uu under the frame foot (Y)", S08ConceptPaste::ShaderSample(P, FVector(0, 310.0, -3)).bCut &&
                                                            !S08ConceptPaste::ShaderSample(P, FVector(0, 311.5, -3)).bCut);
  TestFalse("below minZ (the cliff face under the frame) is not cut", S08ConceptPaste::ShaderSample(P, FVector(0, 300, -100)).bCut);
  TestFalse("behind C0: not in front", S08ConceptPaste::ShaderSample(P, S.Camera.Location() - S.Camera.Forward() * 50.0).bInFront);
  // plate rectangles and the plate-A feather (identity registration: concept px = C0 px)
  S.Homography = FS08ConceptHomography();
  const FS08ConceptMaterialParams ParamsI = S08ConceptPaste::MaterialParams(S, FrameHalf, false, true, ES08ConceptGrade::Lut, 1.0f, false);
  auto At = [&S](const FVector2D& C0Px) { return S.Camera.Location() + S.Camera.Ray(C0Px) * 2700.0; };
  Smp = S08ConceptPaste::ShaderSample(ParamsI, At(FVector2D(960, 540)));
  TestTrue("centre: uvA (0.5, 0.5), weight A 1, inside B", Smp.UvA.Equals(FVector2D(0.5, 0.5), 1e-4) && Smp.WeightA == 1.0f && Smp.bInsideB);
  Smp = S08ConceptPaste::ShaderSample(ParamsI, At(FVector2D(12, 540)));
  TestTrue(FString::Printf(TEXT("12 px inside plate A: weight %.4f = 0.5 (feather 24)"), Smp.WeightA), FMath::IsNearlyEqual(Smp.WeightA, 0.5f, 1e-3f));
  Smp = S08ConceptPaste::ShaderSample(ParamsI, At(FVector2D(-100, 540)));
  TestTrue("outside plate A: plate B only, still inside B", Smp.WeightA == 0.0f && Smp.bInsideB &&
                                                                FMath::IsNearlyEqual(Smp.UvB.X, (-100.0 + 383.5407) / 2687.0813, 1e-5));
  TestFalse("beyond the outpainted canvas: outside B", S08ConceptPaste::ShaderSample(ParamsI, At(FVector2D(-500, 540))).bInsideB);
  TestEqual("waterfall region: full flow inside", S08ConceptPaste::ShaderSample(ParamsI, At(FVector2D(820, 1090))).FlowWeight0, 1.0f);
  TestEqual("waterfall region: none outside", S08ConceptPaste::ShaderSample(ParamsI, At(FVector2D(500, 1090))).FlowWeight0, 0.0f);
  TestTrue("waterfall region: feathered edge (4 px in = 0.5)",
           FMath::IsNearlyEqual(S08ConceptPaste::ShaderSample(ParamsI, At(FVector2D(644, 1090))).FlowWeight0, 0.5f, 1e-3f));
  const FS08ConceptMaterialParams PISea = S08ConceptPaste::MaterialParams(S, FrameHalf, true, true, ES08ConceptGrade::Lut, 1.0f, false);
  TestEqual("sea flow on the sea plane", S08ConceptPaste::ShaderSample(PISea, FVector(-300, -900, -300)).FlowWeight0, 1.0f);
  TestEqual("no sea flow on the sky segments", S08ConceptPaste::ShaderSample(PISea, FVector(-1200, -1500, 100)).FlowWeight0, 0.0f);
  // grade
  TestTrue("lut without a LUT -> inverse ACES", S08ConceptPaste::EffectiveGrade(S, false) == ES08ConceptGrade::AcesInverse);
  TestTrue("lut with the LUT", S08ConceptPaste::EffectiveGrade(S, true) == ES08ConceptGrade::Lut);
  FS08ConceptPasteSpec Linear = S;
  Linear.Grade = ES08ConceptGrade::Linear;
  TestTrue("linear stays linear", S08ConceptPaste::EffectiveGrade(Linear, false) == ES08ConceptGrade::Linear);
  FString Source;
  TestTrue("emissive scale: the fixed exposure brightness", S08ConceptPaste::EffectiveEmissiveScale(S, true, 4.14106f, Source) == 4.14106f &&
                                                                Source == TEXT("exposure"));
  TestTrue("emissive scale: 1 without an exposure", S08ConceptPaste::EffectiveEmissiveScale(S, false, 0.0f, Source) == 1.0f &&
                                                       Source == TEXT("default"));
  S.bHasEmissiveScale = true;
  S.EmissiveScale = 2.5f;
  TestTrue("emissive scale: the block wins", S08ConceptPaste::EffectiveEmissiveScale(S, true, 4.0f, Source) == 2.5f && Source == TEXT("block"));
  float Worst = 0.0f;
  for (int32 I = 0; I <= 97; ++I) {
    const float Y = I / 100.0f;
    Worst = FMath::Max(Worst, FMath::Abs(S08ConceptPaste::AcesApprox(S08ConceptPaste::InverseAcesApprox(Y)) - Y));
  }
  TestTrue(FString::Printf(TEXT("inverse ACES round trip %.6f <= 1e-4"), Worst), Worst <= 1e-4f);
  // flicker / sway: bounded, deterministic, steady without amplitude
  FS08ConceptLight L;
  L.Id = TEXT("fire-fort");
  TestEqual("steady light", S08ConceptPaste::FlickerScale(L, 12.3), 1.0f);
  L.FlickerAmp = 0.2f;
  L.FlickerHz = 6.0f;
  float Lo = 2.0f, Hi = 0.0f;
  for (int32 I = 0; I < 400; ++I) {
    const float V = S08ConceptPaste::FlickerScale(L, I * 0.0137);
    Lo = FMath::Min(Lo, V);
    Hi = FMath::Max(Hi, V);
  }
  TestTrue(FString::Printf(TEXT("flicker in [0.8, 1.2] and moving (%.3f .. %.3f)"), Lo, Hi), Lo >= 0.8f - 1e-5f && Hi <= 1.2f + 1e-5f && Hi - Lo > 0.1f);
  TestEqual("flicker deterministic", S08ConceptPaste::FlickerScale(L, 3.25), S08ConceptPaste::FlickerScale(L, 3.25));
  FS08ConceptAnim A;
  A.Prop = TEXT("lantern-rail");
  A.SwayDeg = 4.0f;
  A.SwayHz = 0.4f;
  float SwayMax = 0.0f;
  for (int32 I = 0; I < 200; ++I) SwayMax = FMath::Max(SwayMax, FMath::Abs(S08ConceptPaste::SwayAngleDeg(A, I * 0.05)));
  TestTrue("sway within +-4 deg and moving", SwayMax <= 4.0f + 1e-4f && SwayMax > 3.0f);
  TestTrue("ground kinds by component name", S08ConceptPaste::GroundKindOf(TEXT("EnvGround_2")) == TEXT("ground") &&
                                                  S08ConceptPaste::GroundKindOf(TEXT("EnvSea_1")) == TEXT("sea") &&
                                                  S08ConceptPaste::GroundKindOf(TEXT("EnvWaterfall_fall_s_Lip")) == TEXT("waterfalls") &&
                                                  S08ConceptPaste::GroundKindOf(TEXT("EnvProp_rock")).IsEmpty());
  TestEqual("missing line", S08ConceptPaste::MissingLine(TEXT("/Game/EnvMaps/X")), FString(TEXT("ARTPREVIEW concept-paste missing /Game/EnvMaps/X")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteEnvIdsTest,
    "Unmatched.S08.ConceptPaste.EnvIds overlay-added / replaced ids (MergeOverlay) and the spawned component ids",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteEnvIdsTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  const FString Base = TEXT(
      "{\"schema\":\"unmatched.env-layout/1\",\"map\":\"cptest\",\"boardId\":\"cidCp\",\"props\":["
      "{\"id\":\"fort\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[-600,-400,-3]},"
      "{\"id\":\"hull\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[600,0,-3]},"
      "{\"id\":\"tree\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[-700,0,-3]},"
      "{\"id\":\"on-map\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[0,0,0]}],"
      "\"lights\":[{\"id\":\"lamp\",\"type\":\"point\",\"loc\":[-600,0,150],\"colorSrgb\":\"#FFB870\",\"intensityCd\":40,\"radius\":450}],"
      "\"fx\":[{\"id\":\"flies\",\"system\":\"/Game/EnvKit/FX/NS_S08CpTest\",\"loc\":[-650,200,40]}]}");
  const FString Overlay = TEXT(
      "{\"schema\":\"unmatched.env-layout-overlay/1\",\"map\":\"cptest\",\"variant\":\"concept\",\"boardId\":\"cidCp\","
      "\"props\":{\"remove\":[\"fort\"],\"replace\":[{\"id\":\"hull\",\"scale\":0.5}],"
      "\"add\":[{\"id\":\"lantern-rail\",\"mesh\":\"/Engine/BasicShapes/Sphere\",\"loc\":[737,-221.7,120]}]},"
      "\"fx\":{\"add\":[{\"id\":\"flame-rail\",\"system\":\"/Game/EnvKit/FX/NS_S08CpTest\",\"anchor\":\"lantern-rail\",\"loc\":[0,0,10]}]}}");
  FS08EnvLayout Merged;
  FS08EnvVariantResult R;
  if (!TestTrue(TEXT("overlay merges: ") + FString::Join(R.Errors, TEXT(" | ")),
                S08EnvLayout::MergeOverlay(Base, Overlay, TEXT("cptest"), TEXT("concept"), Merged, R))) {
    return false;
  }
  TestTrue("overlay props = replaced + added (removed ones are gone, base ones are not listed)",
           Merged.OverlayPropIds.Num() == 2 && Merged.OverlayPropIds.Contains(TEXT("hull")) &&
               Merged.OverlayPropIds.Contains(TEXT("lantern-rail")) && !Merged.OverlayPropIds.Contains(TEXT("tree")));
  TestTrue("overlay fx = added", Merged.OverlayFxIds.Num() == 1 && Merged.OverlayFxIds.Contains(TEXT("flame-rail")));
  FS08EnvLayout Plain;
  TArray<FString> Errors;
  TestTrue("a base layout has no overlay ids", Plain.ParseJson(Base, Errors) && Plain.OverlayPropIds.IsEmpty() && Plain.OverlayFxIds.IsEmpty());
  // the component ids of Spawn, in the order of the component arrays (the hide list maps them back)
  FWorld W(TEXT("S08ConceptPasteEnvIds"));
  AActor* Owner = W.World ? W.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity) : nullptr;
  if (TestNotNull("owner actor", Owner)) {
    USceneComponent* Root = NewObject<USceneComponent>(Owner, TEXT("Root"));
    Owner->SetRootComponent(Root);
    Root->RegisterComponent();
    TArray<TObjectPtr<UStaticMeshComponent>> Props;
    TArray<TObjectPtr<UPointLightComponent>> Lights;
    const FS08EnvSpawnStats Stats = S08EnvLayout::Spawn(Merged, *Owner, Root, FVector2D(445.66667, 288.66667),
                                                        FBox2D(ForceInit), Props, Lights);
    TestTrue("props spawned except the one on the map", Props.Num() == 3 && Stats.PropComponentIds.Num() == Props.Num());
    TestTrue("component ids in spawn order", Stats.PropComponentIds == TArray<FString>({TEXT("hull"), TEXT("tree"), TEXT("lantern-rail")}));
    TestTrue("light component ids", Lights.Num() == 1 && Stats.LightComponentIds == TArray<FString>({TEXT("lamp")}));
    // ApplyHides on that environment: base props, the layout lights and the ground parts by name; RestoreHides undoes it
    FS08EnvLayoutRuntime Env;
    Env.Layout = Merged;
    Env.Stats = Stats;
    TArray<UStaticMeshComponent*> GroundParts;
    for (const TCHAR* Name : {TEXT("EnvGround_0"), TEXT("EnvSea"), TEXT("EnvWaterfall_fall_s_Sheet")}) {
      UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(Owner, FName(Name));
      C->SetupAttachment(Root);
      C->RegisterComponent();
      GroundParts.Add(C);
      Env.Ground.Add(C);
    }
    FS08ConceptHide Hide;
    Hide.bBaseProps = Hide.bLayoutLights = Hide.bGround = Hide.bSea = true;  // waterfalls kept
    FS08ConceptPasteRuntime Rt;
    S08ConceptPaste::ApplyHides(Hide, Env, Props, Lights, nullptr, Rt);
    TestTrue("base props hidden, the overlay's kept", Props.Num() == 3 && Props[0]->IsVisible() && !Props[1]->IsVisible() &&
                                                         Props[2]->IsVisible() && Rt.HiddenProps == 1);
    TestTrue("layout light hidden", !Lights[0]->IsVisible() && Rt.HiddenLights == 1);
    TestTrue("ground + sea hidden, waterfall kept", !GroundParts[0]->IsVisible() && !GroundParts[1]->IsVisible() &&
                                                       GroundParts[2]->IsVisible() && Rt.HiddenGround == 1 && Rt.HiddenSea == 1 &&
                                                       Rt.HiddenWaterfalls == 0);
    S08ConceptPaste::ApplyHides(Hide, Env, Props, Lights, nullptr, Rt);
    TestEqual("idempotent: the same components once", Rt.Hidden.Num(), 4);
    TestEqual("restore shows them again", S08ConceptPaste::RestoreHides(Rt), 4);
    TestTrue("all visible again", Props[1]->IsVisible() && Lights[0]->IsVisible() && GroundParts[0]->IsVisible() &&
                                      GroundParts[1]->IsVisible() && Rt.Hidden.IsEmpty());
    for (UStaticMeshComponent* C : GroundParts) C->DestroyComponent();
    S08EnvLayout::Clear(Props, Lights);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteActorTest,
    "Unmatched.S08.ConceptPaste.Actor nothing on grids / refused maps; shipped Sarpedon paste or traced P5c fallback, p5c variant, Marmoreal off",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteActorTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  FScope Scope(TEXT(""));
  FWorld W(TEXT("S08ConceptPasteActor"));
  if (!TestNotNull("test world", W.World)) return false;
  auto NoPaste = [this](const AS08BoardActor* A, const TCHAR* What) {
    TestTrue(FString(What) + TEXT(": no concept part, light or hide"),
             A->GetConceptPasteParts().IsEmpty() && A->GetConceptPasteLights().IsEmpty() && !A->IsConceptPasteOn() &&
                 A->GetConceptPasteRuntime().Hidden.IsEmpty() && A->GetConceptPasteAnim() == nullptr);
  };
  // 1) grids and a refused map-image profile: nothing, and no concept line at all (grids bit for bit)
  {
    AS08BoardActor* A = W.Spawn();
    if (TestNotNull("board actor", A)) {
      TestTrue("env gate armed", A->EnsureEnvLayout(true));
      TestTrue("rebuild grid 5x6 (no art data)", A->Rebuild(GridBoard(5, 6)));
      NoPaste(A, TEXT("grid 5x6"));
      TestFalse("grid-only run: never traced", A->GetConceptPasteRuntime().bTraced);
      FS08BoardArtData Data;
      TArray<FString> Errors;
      if (TestTrue("doc with the block", Data.ParseJson(Doc(ValidBlock), Errors))) {
        A->SetArtDataForTest(Data);
        TestTrue("rebuild the 3x2 grid profile", A->Rebuild(GridBoard(3, 2)));
        TestFalse("3x2 grid: not map-image", A->IsMapImageActive());
        NoPaste(A, TEXT("grid 3x2 with the data"));
        TestFalse("grid with the data: never traced", A->GetConceptPasteRuntime().bTraced);
        FS08BoardModel Topo;
        if (TestTrue("synthetic topology", SyntheticTopology(Topo))) {
          A->SetRoomBoardId(TEXT("cidCp"));
          TestTrue("rebuild the topology (map assets missing)", A->Rebuild(Topo));
          TestFalse("refused map-image", A->IsMapImageActive());
          NoPaste(A, TEXT("refused map-image"));
          TestFalse("refused map-image: the mode is off", A->GetConceptPasteMode().bOn);
        }
      }
      // ENV-MAPS P8: a lit3d block changes nothing on a grid either (Cobble bit for bit)
      FS08BoardArtData Lit3dData;
      TArray<FString> Lit3dErrors;
      if (TestTrue("doc with a lit3d block", Lit3dData.ParseJson(Doc(Lit3dBlock()), Lit3dErrors))) {
        A->SetArtDataForTest(Lit3dData);
        TestTrue("rebuild the 3x2 grid profile (lit3d data)", A->Rebuild(GridBoard(3, 2)));
        NoPaste(A, TEXT("grid 3x2 with lit3d data"));
        TestTrue("grid with lit3d data: no scene tweak", A->GetConceptPasteRuntime().Tweaks.IsEmpty());
      }
      A->Destroy();
    }
  }
  // 2) the shipped profiles once the map import ran (out of git)
  FS08BoardArtData Shipped;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", Shipped.LoadFile(FS08BoardArtData::DefaultPath(), Errors))) return false;
  const FS08BoardArtProfile* Sarpedon = Find(Shipped, TEXT("sarpedon-original"));
  const FS08BoardArtProfile* Marmoreal = Find(Shipped, TEXT("marmoreal-original"));
  FS08BoardModel SarBoard, MarBoard;
  FString SarId, MarId;
  if (!Sarpedon || !Marmoreal || !TopologyBoard(TEXT("sarpedon.topology.json"), SarBoard, SarId) ||
      !TopologyBoard(TEXT("marmoreal.topology.json"), MarBoard, MarId)) {
    AddError(TEXT("shipped map profiles or topology fixtures missing"));
    return false;
  }
  if (!FPackageName::DoesPackageExist(Sarpedon->Map.MaterialInstancePath) ||
      !FPackageName::DoesPackageExist(Marmoreal->Map.MaterialInstancePath)) {
    AddWarning(TEXT("map assets not imported (tools/art/map_surface/ue_import_map_surface.py, ENV-U3: out of git): the shipped concept-paste path was NOT exercised"));
    return true;
  }
  const FS08ConceptPasteSpec& S = Sarpedon->ConceptPaste;
  // ENV-MAPS P8: the default is lit3d - its required packages (out of git: tools/art/concept_scene) and the scene overlay
  // (track A); the P7 paste has its own test (Unmatched.S08.ConceptPaste.PasteKind)
  bool bAssets = S.Lit3d.bSet;
  for (const FString& Path : S.Lit3d.Required) bAssets = bAssets && FPackageName::DoesPackageExist(Path);
  const bool bOverlay =
      FPaths::FileExists(S08EnvLayout::OverlayFileFor(S08EnvLayout::DefaultDir(), TEXT("sarpedon"), S.Lit3d.Variant));
  {
    AS08BoardActor* A = W.Spawn();
    if (TestNotNull("board actor (sarpedon)", A)) {
      A->EnsureDioramaTray(true);
      TestTrue("env gate armed", A->EnsureEnvLayout(true));
      A->SetArtDataForTest(Shipped);
      A->SetRoomBoardId(SarId);
      TestTrue("rebuild Sarpedon", A->Rebuild(SarBoard));
      TestTrue("map-image active", A->IsMapImageActive());
      const FS08ConceptPasteRuntime& Rt = A->GetConceptPasteRuntime();
      if (bAssets && bOverlay) {
        TestTrue(TEXT("sarpedon default: the lit 3D island is on (") + A->GetConceptPasteMode().Reason + TEXT(")"),
                 A->IsConceptPasteOn() && A->GetConceptPasteMode().Kind == ES08ConceptKind::Lit3d);
        TestEqual("env variant = the scene overlay", A->GetEnvLayoutRuntime().Variant.Name, S.Lit3d.Variant);
        TestTrue("no sheet, no sea plane: at most the sky cylinder",
                 Rt.SheetParts == 0 && (Rt.SeaParts == 0 || Rt.SeaParts == S.Sea.SkySegments));
        TestEqual("the lit3d lights", A->GetConceptPasteLights().Num(), S.Lit3d.Lights.Num());
        int32 Clean = 0;
        for (const UStaticMeshComponent* Part : A->GetConceptPasteParts()) {
          Clean += Part && !Part->CastShadow && !Part->bAffectDynamicIndirectLighting && Part->GetCollisionEnabled() == ECollisionEnabled::NoCollision
                       ? 1 : 0;
        }
        TestEqual("the sky parts: no shadow, no Lumen GI, no collision", Clean, A->GetConceptPasteParts().Num());
        TestTrue(FString::Printf(TEXT("the island masses cast shadows (shadowsOn=%d casters=%d overlayProps=%d)"), Rt.SceneShadows,
                                 Rt.SceneCasters, Rt.SceneProps),
                 Rt.SceneShadows > 0 && Rt.SceneCasters > 0 && Rt.SceneProps > 0);
        const UStaticMeshComponent* Island = nullptr;
        for (const UStaticMeshComponent* C : A->GetEnvProps()) {
          if (C && C->GetStaticMesh() && C->GetStaticMesh()->GetName() == TEXT("SM_Env_S_Island")) Island = C;
        }
        if (TestNotNull("the island spawned", Island)) {
          TestTrue("island: visible, casts, no collision",
                   Island->IsVisible() && Island->CastShadow && Island->GetCollisionEnabled() == ECollisionEnabled::NoCollision);
          const UMaterial* Base = Island->GetMaterial(0) ? Island->GetMaterial(0)->GetMaterial() : nullptr;
          TestTrue("island: lit (never unlit for layer B)", Base && !Base->GetShadingModels().HasOnlyShadingModel(MSM_Unlit));
        }
        int32 Seas = 0;
        for (const TWeakObjectPtr<UStaticMeshComponent>& G : A->GetEnvLayoutRuntime().Ground) {
          const UStaticMeshComponent* C = G.Get();
          if (!C || S08ConceptPaste::GroundKindOf(C->GetName()) != TEXT("sea")) continue;
          ++Seas;
          TestTrue(TEXT("the sea ring is back, under the cliffs: ") + C->GetRelativeLocation().ToString(),
                   C->IsVisible() && (!S.Lit3d.bSeaZ || FMath::IsNearlyEqual(C->GetRelativeLocation().Z, S.Lit3d.SeaZUU, 0.01)));
        }
        if (Seas == 0) AddWarning(TEXT("no sea ring in the ground section (P5 ground assets not imported)"));
        TestFalse("the fog hidden", A->GetAppliedRender().bFog);
        if (A->GetDioramaTray()) TestFalse("the tray hidden (the island replaces it)", A->GetDioramaTray()->IsVisible());
        int32 VisibleLayoutLights = 0;
        for (const UPointLightComponent* L : A->GetEnvLights()) VisibleLayoutLights += L && L->IsVisible() ? 1 : 0;
        TestEqual("layout lights hidden (the block's lights replace them)", VisibleLayoutLights, 0);
        const FS08LightProfile* Night = Shipped.LightFor(*Sarpedon);
        TestTrue("1 key + <= 6 points", Night && Night->Points.Num() + A->GetConceptPasteLights().Num() <= 6);
        for (const UPointLightComponent* L : A->GetConceptPasteLights()) {
          TestTrue("a block light casts no shadow", L && !L->CastShadows);
        }
      } else {
        AddWarning(FString::Printf(TEXT("lit3d assets %s / scene overlay %s not there (tools/art/concept_scene/ue_scene_material.py, ue_import_concept_scene.py, EnvLayouts/sarpedon.%s.layout.json): the P5c fallback was checked"),
                                   bAssets ? TEXT("ok") : TEXT("missing"), bOverlay ? TEXT("ok") : TEXT("missing"), *S.Lit3d.Variant));
        TestFalse("fallback: the island is off", A->IsConceptPasteOn());
        TestTrue(TEXT("fallback reason: ") + A->GetConceptPasteMode().Reason,
                 A->GetConceptPasteMode().Reason == TEXT("missing-assets") || A->GetConceptPasteMode().Reason == TEXT("overlay-absent"));
        NoPaste(A, TEXT("sarpedon fallback"));
        TestTrue("fallback traced", Rt.bTraced);
        TestTrue("fallback: the night fog stays (P5c)", A->GetAppliedRender().bFog);
        if (A->GetDioramaTray()) TestTrue("fallback: the tray stays", A->GetDioramaTray()->IsVisible());
        TestTrue("fallback: the base layout (no scene overlay)", A->GetEnvLayoutRuntime().Variant.Name.IsEmpty());
      }
      // a grid afterwards clears everything
      TestTrue("rebuild a 5x6 grid", A->Rebuild(GridBoard(5, 6)));
      NoPaste(A, TEXT("grid after Sarpedon"));
      A->Destroy();
    }
  }
  {
    AS08BoardActor* A = W.Spawn();
    if (TestNotNull("board actor (marmoreal)", A)) {
      TestTrue("env gate armed", A->EnsureEnvLayout(true));
      A->SetArtDataForTest(Shipped);
      A->SetRoomBoardId(MarId);
      TestTrue("rebuild Marmoreal", A->Rebuild(MarBoard));
      TestTrue("marmoreal default: off (default)", !A->GetConceptPasteMode().bOn && A->GetConceptPasteMode().Reason == TEXT("default") &&
                                                      !A->GetConceptPasteMode().bOverrideVariant);
      NoPaste(A, TEXT("marmoreal default"));
      TestTrue("marmoreal default: the fog of the light profile stays", A->GetAppliedRender().bFog);
      TestFalse("marmoreal default: no backdrop hide", A->GetConceptPasteRuntime().bHidBackdrop);
      A->Destroy();
    }
  }
  // last: the nested scope resets the test overrides when it ends
  {
    FScope P5c(TEXT("-EnvLayoutVariant=p5c"));
    AS08BoardActor* A = W.Spawn();
    if (TestNotNull("board actor (p5c)", A)) {
      TestTrue("env gate armed", A->EnsureEnvLayout(true));
      A->SetArtDataForTest(Shipped);
      A->SetRoomBoardId(SarId);
      TestTrue("rebuild Sarpedon", A->Rebuild(SarBoard));
      TestTrue("-EnvLayoutVariant=p5c: off (variant-off)", !A->GetConceptPasteMode().bOn && A->GetConceptPasteMode().Reason == TEXT("variant-off"));
      TestTrue("-EnvLayoutVariant=p5c: the base layout, no overlay", A->GetEnvLayoutRuntime().Variant.Name.IsEmpty());
      NoPaste(A, TEXT("p5c"));
      A->Destroy();
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteApplyFailureTest,
    "Unmatched.S08.ConceptPaste.ApplyFailure Apply != ok with the assets loaded: the full P5c look (base layout, backdrop, tray, fog, layout lights), no flip-flop",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteApplyFailureTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  // one FScope at a time: its destructor resets the overrides (a nested scope would end the outer one's)
  FWorld W(TEXT("S08ConceptPasteApplyFailure"));
  if (!TestNotNull("test world", W.World)) return false;
  FS08BoardArtData Shipped;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", Shipped.LoadFile(FS08BoardArtData::DefaultPath(), Errors))) return false;
  const FS08BoardArtProfile* Sarpedon = Find(Shipped, TEXT("sarpedon-original"));
  FS08BoardModel SarBoard;
  FString SarId;
  if (!Sarpedon || !TopologyBoard(TEXT("sarpedon.topology.json"), SarBoard, SarId)) {
    AddError(TEXT("shipped Sarpedon profile or topology fixture missing"));
    return false;
  }
  const FS08ConceptPasteSpec& S = Sarpedon->ConceptPaste;
  const bool bMap = FPackageName::DoesPackageExist(Sarpedon->Map.MaterialInstancePath);
  // ENV-MAPS P8: the default kind is lit3d - its required packages and the scene overlay
  bool bAssets = S.Lit3d.bSet;
  for (const FString& Path : S.Lit3d.Required) bAssets = bAssets && FPackageName::DoesPackageExist(Path);
  const bool bOverlay =
      FPaths::FileExists(S08EnvLayout::OverlayFileFor(S08EnvLayout::DefaultDir(), TEXT("sarpedon"), S.Lit3d.Variant));
  if (!bMap || !bAssets || !bOverlay) {
    AddWarning(TEXT("map / concept assets or the concept overlay not there (out of git): the Apply-failure fallback was NOT exercised"));
    return true;
  }
  struct FLook {
    int32 Props = 0, VisibleProps = 0, Lights = 0, VisibleLights = 0, BackdropParts = 0;
    FString Variant, Backdrop;
    bool bFog = false, bTray = false;
  };
  auto LookOf = [](const AS08BoardActor* A) {
    FLook L;
    for (const UStaticMeshComponent* C : A->GetEnvProps()) {
      L.Props += C ? 1 : 0;
      L.VisibleProps += C && C->IsVisible() ? 1 : 0;
    }
    for (const UPointLightComponent* C : A->GetEnvLights()) {
      L.Lights += C ? 1 : 0;
      L.VisibleLights += C && C->IsVisible() ? 1 : 0;
    }
    L.BackdropParts = A->GetBackdropParts().Num();
    L.Variant = A->GetEnvLayoutRuntime().Variant.Name;
    L.Backdrop = A->GetBackdropRuntime().Status;
    L.bFog = A->GetAppliedRender().bFog;
    L.bTray = A->GetDioramaTray() && A->GetDioramaTray()->IsVisible();
    return L;
  };
  // the reference: the P5c composition of the same board (-EnvLayoutVariant=p5c)
  FLook P5c;
  {
    FScope Off(TEXT("-EnvLayoutVariant=p5c"));
    AS08BoardActor* A = W.Spawn();
    if (!TestNotNull("board actor (p5c reference)", A)) return false;
    A->EnsureDioramaTray(true);
    TestTrue("env gate armed", A->EnsureEnvLayout(true));
    A->SetArtDataForTest(Shipped);
    A->SetRoomBoardId(SarId);
    TestTrue("rebuild Sarpedon (p5c)", A->Rebuild(SarBoard));
    P5c = LookOf(A);
    A->Destroy();
  }
  TestTrue(FString::Printf(TEXT("P5c reference has props (%d) and layout lights (%d)"), P5c.Props, P5c.Lights),
           P5c.Props > 0 && P5c.Lights > 0);
  {
    struct FHook {
      FHook() { S08ConceptPaste::SetForceApplyFailureForTest(true); }
      ~FHook() { S08ConceptPaste::SetForceApplyFailureForTest(false); }
    } Hook;
    FScope Default(TEXT(""));
    AS08BoardActor* A = W.Spawn();
    if (!TestNotNull("board actor (forced Apply failure)", A)) return false;
    A->EnsureDioramaTray(true);
    TestTrue("env gate armed", A->EnsureEnvLayout(true));
    A->SetArtDataForTest(Shipped);
    A->SetRoomBoardId(SarId);
    TestTrue("rebuild Sarpedon (Apply fails)", A->Rebuild(SarBoard));
    const FS08ConceptPasteMode& M = A->GetConceptPasteMode();
    TestTrue(TEXT("mode off, reason apply-failed: ") + M.Reason, !M.bOn && M.Reason == TEXT("apply-failed"));
    TestFalse("the paste is off", A->IsConceptPasteOn());
    TestTrue("no concept part / light / hide / anim",
             A->GetConceptPasteParts().IsEmpty() && A->GetConceptPasteLights().IsEmpty() &&
                 A->GetConceptPasteRuntime().Hidden.IsEmpty() && A->GetConceptPasteAnim() == nullptr);
    const FLook L = LookOf(A);
    TestTrue(TEXT("env layout re-run without the concept overlay (variant: ") + L.Variant + TEXT(")"), L.Variant.IsEmpty());
    TestEqual("the P5c props are back", L.Props, P5c.Props);
    TestEqual("... all visible", L.VisibleProps, P5c.VisibleProps);
    TestEqual("the P5c layout lights", L.Lights, P5c.Lights);
    TestEqual("... all visible", L.VisibleLights, P5c.VisibleLights);
    TestEqual(TEXT("the backdrop as in P5c"), L.Backdrop, P5c.Backdrop);
    TestEqual("backdrop parts as in P5c", L.BackdropParts, P5c.BackdropParts);
    TestEqual("the fog as in P5c", L.bFog, P5c.bFog);
    TestEqual("the tray as in P5c", L.bTray, P5c.bTray);
    // the same board again: remembered per profile, straight to P5c (the env layout is not respawned)
    const FString EnvKey = A->GetEnvLayoutRuntime().Key;
    TestTrue("rebuild Sarpedon again", A->Rebuild(SarBoard));
    TestTrue("still apply-failed", !A->GetConceptPasteMode().bOn && A->GetConceptPasteMode().Reason == TEXT("apply-failed"));
    TestEqual("the env layout kept (no flip-flop)", A->GetEnvLayoutRuntime().Key, EnvKey);
    TestEqual("props unchanged", LookOf(A).VisibleProps, P5c.VisibleProps);
    A->Destroy();
  }
  return true;
}

// ---- ENV-MAPS P8 (lit3d, docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md section 4 P8.2) -----------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPastePasteKindTest,
    "Unmatched.S08.ConceptPaste.PasteKind -ConceptPaste=paste on the shipped Sarpedon: the P7 paste (sheet, sea, lights) or the traced P5c fallback",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPastePasteKindTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  FScope Scope(TEXT("-ConceptPaste=paste"));
  FWorld W(TEXT("S08ConceptPastePasteKind"));
  if (!TestNotNull("test world", W.World)) return false;
  FS08BoardArtData Shipped;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", Shipped.LoadFile(FS08BoardArtData::DefaultPath(), Errors))) return false;
  const FS08BoardArtProfile* Sarpedon = Find(Shipped, TEXT("sarpedon-original"));
  FS08BoardModel SarBoard;
  FString SarId;
  if (!Sarpedon || !TopologyBoard(TEXT("sarpedon.topology.json"), SarBoard, SarId)) {
    AddError(TEXT("shipped Sarpedon profile or topology fixture missing"));
    return false;
  }
  if (!FPackageName::DoesPackageExist(Sarpedon->Map.MaterialInstancePath)) {
    AddWarning(TEXT("map assets not imported (ENV-U3: out of git): the paste kind was NOT exercised"));
    return true;
  }
  const FS08ConceptPasteSpec& S = Sarpedon->ConceptPaste;
  const bool bAssets = FPackageName::DoesPackageExist(S.SheetMeshPath) && FPackageName::DoesPackageExist(S.PlateBPath) &&
                       FPackageName::DoesPackageExist(PackageOf(S.MaterialPath));
  const bool bOverlay = FPaths::FileExists(S08EnvLayout::OverlayFileFor(S08EnvLayout::DefaultDir(), TEXT("sarpedon"), S.Variant));
  AS08BoardActor* A = W.Spawn();
  if (!TestNotNull("board actor (sarpedon, paste)", A)) return false;
  A->EnsureDioramaTray(true);
  TestTrue("env gate armed", A->EnsureEnvLayout(true));
  A->SetArtDataForTest(Shipped);
  A->SetRoomBoardId(SarId);
  TestTrue("rebuild Sarpedon", A->Rebuild(SarBoard));
  const FS08ConceptPasteRuntime& Rt = A->GetConceptPasteRuntime();
  if (bAssets && bOverlay) {
    TestTrue(TEXT("-ConceptPaste=paste: the P7 paste is on (") + A->GetConceptPasteMode().Reason + TEXT(")"),
             A->IsConceptPasteOn() && A->GetConceptPasteMode().Kind == ES08ConceptKind::Paste);
    TestEqual("env variant = the concept overlay", A->GetEnvLayoutRuntime().Variant.Name, S.Variant);
    TestTrue("sheet + sea plane + sky segments", Rt.SheetParts == 1 && Rt.SeaParts == 1 + S.Sea.SkySegments);
    TestEqual("the paste's lights", A->GetConceptPasteLights().Num(), S.Lights.Num());
    int32 Clean = 0;
    for (const UStaticMeshComponent* Part : A->GetConceptPasteParts()) {
      Clean += Part && !Part->CastShadow && !Part->bAffectDynamicIndirectLighting && !Part->bAffectDistanceFieldLighting &&
                       Part->GetCollisionEnabled() == ECollisionEnabled::NoCollision
                   ? 1 : 0;
    }
    TestEqual("every part: no shadow, no Lumen GI / DF, no collision", Clean, A->GetConceptPasteParts().Num());
    const UStaticMeshComponent* Sheet = A->GetConceptPasteParts().Num() ? A->GetConceptPasteParts()[0].Get() : nullptr;
    const UMaterial* Base = Sheet && Sheet->GetMaterial(0) ? Sheet->GetMaterial(0)->GetMaterial() : nullptr;
    TestTrue("sheet on M_ConceptPaste: unlit, masked", Base && Base->GetName() == TEXT("M_ConceptPaste") &&
                                                           Base->GetShadingModels().HasOnlyShadingModel(MSM_Unlit) &&
                                                           Base->GetBlendMode() == BLEND_Masked);
    TestFalse("the fog hidden (the plate has its own haze)", A->GetAppliedRender().bFog);
    if (A->GetDioramaTray()) TestFalse("the tray hidden (the painted island replaces it)", A->GetDioramaTray()->IsVisible());
    TestTrue("paste: no lit3d scene tweak", Rt.Tweaks.IsEmpty() && Rt.Kind == ES08ConceptKind::Paste);
  } else {
    AddWarning(FString::Printf(TEXT("concept assets %s / overlay %s not there (ue_import_concept_paste.py, ue_concept_material.py): the P5c fallback was checked"),
                               bAssets ? TEXT("ok") : TEXT("missing"), bOverlay ? TEXT("ok") : TEXT("missing")));
    TestFalse("fallback: the paste is off", A->IsConceptPasteOn());
    TestTrue(TEXT("fallback reason: ") + A->GetConceptPasteMode().Reason,
             A->GetConceptPasteMode().Reason == TEXT("missing-assets") || A->GetConceptPasteMode().Reason == TEXT("overlay-absent"));
    TestTrue("fallback: the night fog stays (P5c)", A->GetAppliedRender().bFog);
  }
  A->Destroy();
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteLit3dSceneTest,
    "Unmatched.S08.ConceptPaste.Lit3dScene lit3d: no sheet, lights within the budget, hides, casters / GI / sea ring / falls, restore, missing / failed",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteLit3dSceneTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("lit3d doc parses: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Doc(Lit3dBlock()), Errors))) {
    return false;
  }
  const FS08BoardArtProfile* Profile = Find(Data, TEXT("cpmap"));
  const FS08ConceptPasteSpec& Spec = Profile->ConceptPaste;
  const FS08LightProfile* Light = Data.LightFor(*Profile);
  // the base layout + the scene overlay (the island masses with castShadow false: the casters switch them on)
  const FString Base = TEXT(
      "{\"schema\":\"unmatched.env-layout/1\",\"map\":\"cptest\",\"boardId\":\"cidCp\",\"props\":["
      "{\"id\":\"fort\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[-600,-400,-3]}],"
      "\"lights\":[{\"id\":\"lamp\",\"type\":\"point\",\"loc\":[-600,0,150],\"colorSrgb\":\"#FFB870\",\"intensityCd\":40,\"radius\":450}]}");
  const FString Overlay = TEXT(
      "{\"schema\":\"unmatched.env-layout-overlay/1\",\"map\":\"cptest\",\"variant\":\"scene\",\"boardId\":\"cidCp\","
      "\"props\":{\"add\":["
      "{\"id\":\"island\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[-700,350,-3],\"castShadow\":false},"
      "{\"id\":\"ship-hull\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[700,0,-3],\"castShadow\":false},"
      "{\"id\":\"tree-1\",\"mesh\":\"/Engine/BasicShapes/Cone\",\"loc\":[-650,-100,-3],\"castShadow\":false},"
      "{\"id\":\"tree-2\",\"mesh\":\"/Engine/BasicShapes/Cone\",\"loc\":[-650,100,-3],\"castShadow\":false},"
      "{\"id\":\"banner-ship\",\"mesh\":\"/Engine/BasicShapes/Plane\",\"loc\":[831,-133,49],\"castShadow\":false}]}}");
  FS08EnvLayout Merged;
  FS08EnvVariantResult R;
  if (!TestTrue(TEXT("scene overlay merges: ") + FString::Join(R.Errors, TEXT(" | ")),
                S08EnvLayout::MergeOverlay(Base, Overlay, TEXT("cptest"), TEXT("scene"), Merged, R))) {
    return false;
  }
  FWorld W(TEXT("S08ConceptPasteLit3dScene"));
  AActor* Owner = W.World ? W.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity) : nullptr;
  if (!TestNotNull("owner actor", Owner)) return false;
  USceneComponent* Root = NewObject<USceneComponent>(Owner, TEXT("Root"));
  Owner->SetRootComponent(Root);
  Root->RegisterComponent();
  TArray<TObjectPtr<UStaticMeshComponent>> Props;
  TArray<TObjectPtr<UPointLightComponent>> EnvLights;
  FS08EnvLayoutRuntime Env;
  Env.Layout = Merged;
  Env.Stats = S08EnvLayout::Spawn(Merged, *Owner, Root, FVector2D(445.66667, 288.66667), FBox2D(ForceInit), Props, EnvLights);
  TestEqual("6 props spawned", Props.Num(), 6);
  // the ground section's parts by their S08EnvGround names (meshless: bounds = the component location)
  TMap<FString, UStaticMeshComponent*> Ground;
  struct FGroundPart {
    const TCHAR* Name;
    FVector Loc;
  };
  const FGroundPart GroundParts[] = {
      {TEXT("EnvGround_0"), FVector(0, 0, -1)},          {TEXT("EnvSea"), FVector(0, -45, -172)},
      {TEXT("EnvWaterfall_fall_s_Sheet"), FVector(-144, 425, 0)}, {TEXT("EnvWaterfall_fall_s_Foam"), FVector(-144, 425, -120)},
      {TEXT("EnvWaterfall_fall_s_Lip"), FVector(-144, 425, 0)}};
  for (const FGroundPart& G : GroundParts) {
    UStaticMeshComponent* C = NewObject<UStaticMeshComponent>(Owner, FName(G.Name));
    C->SetupAttachment(Root);
    C->SetRelativeLocation(G.Loc);
    C->RegisterComponent();
    Ground.Add(G.Name, C);
    Env.Ground.Add(C);
  }
  TArray<TObjectPtr<UStaticMeshComponent>> Parts;
  TArray<TObjectPtr<UPointLightComponent>> Lights;
  FS08ConceptPasteRuntime Rt;
  Rt.ProfileId = TEXT("cpmap");
  // a required package missing -> nothing spawned (the board actor falls back to P5c)
  FS08ConceptPasteAssets Assets;
  Assets.Kind = ES08ConceptKind::Lit3d;
  TestFalse("lit3d assets: required not loaded", Assets.RequiredOk());
  S08ConceptPaste::ApplyLit3d(Spec, Assets, FrameHalf, ES08ConceptGrade::AcesInverse, 1.0f, true, *Owner, Root, Parts, Lights, Rt);
  TestTrue("missing: status missing, nothing spawned", Rt.Status == TEXT("missing") && Parts.IsEmpty() && Lights.IsEmpty());
  // the automation hook: failed (the board actor's full P5c fallback)
  Assets.bSceneOk = true;
  S08ConceptPaste::SetForceApplyFailureForTest(true);
  S08ConceptPaste::ApplyLit3d(Spec, Assets, FrameHalf, ES08ConceptGrade::AcesInverse, 1.0f, true, *Owner, Root, Parts, Lights, Rt);
  S08ConceptPaste::SetForceApplyFailureForTest(false);
  TestTrue("forced failure: status failed, nothing spawned", Rt.Status == TEXT("failed") && Parts.IsEmpty() && Lights.IsEmpty());
  // ok: no sheet, no sea plane (the test block has no sky), the lit3d lights
  S08ConceptPaste::ApplyLit3d(Spec, Assets, FrameHalf, ES08ConceptGrade::AcesInverse, 1.0f, true, *Owner, Root, Parts, Lights, Rt);
  TestTrue("ok: lit3d, no sheet / sea / sky parts", Rt.Status == TEXT("ok") && Rt.Kind == ES08ConceptKind::Lit3d && Parts.IsEmpty() &&
                                                        Rt.SheetParts == 0 && Rt.SeaParts == 0);
  TestEqual("the lit3d lights", Lights.Num(), Spec.Lit3d.Lights.Num());
  for (const UPointLightComponent* L : Lights) TestTrue("a block light casts no shadow", L && !L->CastShadows && L->IsRegistered());
  TestTrue("light budget: profile points + block lights <= 6",
           Light && Light->Points.Num() + Lights.Num() <= S08ConceptPasteSpec::CombinedPointBudget);
  // hides: the lit3d list keeps the sea ring and the falls
  S08ConceptPaste::ApplyHides(Spec.HideFor(ES08ConceptKind::Lit3d), Env, Props, EnvLights, nullptr, Rt);
  const int32 Fort = Env.Stats.PropComponentIds.IndexOfByKey(TEXT("fort"));
  const int32 Island = Env.Stats.PropComponentIds.IndexOfByKey(TEXT("island"));
  const int32 Hull = Env.Stats.PropComponentIds.IndexOfByKey(TEXT("ship-hull"));
  const int32 Tree = Env.Stats.PropComponentIds.IndexOfByKey(TEXT("tree-1"));
  const int32 Banner = Env.Stats.PropComponentIds.IndexOfByKey(TEXT("banner-ship"));
  if (!TestTrue("prop ids", Fort != INDEX_NONE && Island != INDEX_NONE && Hull != INDEX_NONE && Tree != INDEX_NONE && Banner != INDEX_NONE)) {
    return false;
  }
  TestTrue("base prop hidden, the scene's kept", !Props[Fort]->IsVisible() && Props[Island]->IsVisible() && Props[Hull]->IsVisible());
  TestTrue("layout light hidden", !EnvLights[0]->IsVisible());
  TestTrue("ground strips hidden, the sea ring and the falls back", !Ground[TEXT("EnvGround_0")]->IsVisible() &&
                                                                       Ground[TEXT("EnvSea")]->IsVisible() &&
                                                                       Ground[TEXT("EnvWaterfall_fall_s_Sheet")]->IsVisible() &&
                                                                       Ground[TEXT("EnvWaterfall_fall_s_Foam")]->IsVisible());
  // the scene tweaks
  S08ConceptPaste::ApplyScene(Spec.Lit3d, Env, Props, Rt);
  TestTrue("casters: island / ship-hull / trees cast", Props[Island]->CastShadow && Props[Hull]->CastShadow && Props[Tree]->CastShadow);
  TestTrue("casters feed Lumen GI, giOff takes the island out", Props[Hull]->bAffectDynamicIndirectLighting &&
                                                                    Props[Tree]->bAffectDynamicIndirectLighting &&
                                                                    !Props[Island]->bAffectDynamicIndirectLighting);
  TestFalse("not a caster: the banner keeps its layout flag", Props[Banner]->CastShadow);
  TestTrue(FString::Printf(TEXT("counts: casters %d (4), giOff %d (1), overlay props %d (5), shadowsOn %d (4 visible)"), Rt.SceneCasters,
                           Rt.SceneGiOff, Rt.SceneProps, Rt.SceneShadows),
           Rt.SceneCasters == 4 && Rt.SceneGiOff == 1 && Rt.SceneProps == 5 && Rt.SceneShadows == 4);
  TestTrue(TEXT("the sea ring under the cliffs: ") + Ground[TEXT("EnvSea")]->GetRelativeLocation().ToString(),
           Ground[TEXT("EnvSea")]->GetRelativeLocation().Equals(FVector(0, -45, -300), 1e-3) && Rt.SceneSeaMoved == 1);
  TestTrue("the fall sheet x2 in Z from the lip", FMath::IsNearlyEqual(Ground[TEXT("EnvWaterfall_fall_s_Sheet")]->GetRelativeScale3D().Z, 2.0) &&
                                                      FMath::IsNearlyEqual(Ground[TEXT("EnvWaterfall_fall_s_Sheet")]->GetRelativeLocation().Z, 0.0));
  TestTrue(TEXT("the foam keeps its size and follows the drop: ") + Ground[TEXT("EnvWaterfall_fall_s_Foam")]->GetRelativeLocation().ToString(),
           FMath::IsNearlyEqual(Ground[TEXT("EnvWaterfall_fall_s_Foam")]->GetRelativeLocation().Z, -240.0, 0.01) &&
               FMath::IsNearlyEqual(Ground[TEXT("EnvWaterfall_fall_s_Foam")]->GetRelativeScale3D().Z, 1.0));
  TestTrue("the lip stays", Ground[TEXT("EnvWaterfall_fall_s_Lip")]->GetRelativeScale3D().Equals(FVector::OneVector) &&
                                FMath::IsNearlyEqual(Ground[TEXT("EnvWaterfall_fall_s_Lip")]->GetRelativeLocation().Z, 0.0) &&
                                Rt.SceneFallsScaled == 2);
  S08ConceptPaste::ApplyScene(Spec.Lit3d, Env, Props, Rt);
  TestEqual("idempotent: each component remembered once", Rt.Tweaks.Num(), 7);
  TestTrue("idempotent: a second call computes from the originals",
           FMath::IsNearlyEqual(Ground[TEXT("EnvWaterfall_fall_s_Sheet")]->GetRelativeScale3D().Z, 2.0) &&
               FMath::IsNearlyEqual(Ground[TEXT("EnvWaterfall_fall_s_Foam")]->GetRelativeLocation().Z, -240.0, 0.01) &&
               FMath::IsNearlyEqual(Ground[TEXT("EnvSea")]->GetRelativeLocation().Z, -300.0, 0.01));
  // restore: everything as the layout spawned it
  S08ConceptPaste::RestoreHides(Rt);
  TestTrue("restore: shadows / GI back", !Props[Island]->CastShadow && Props[Island]->bAffectDynamicIndirectLighting &&
                                             !Props[Hull]->CastShadow && !Props[Tree]->CastShadow);
  TestTrue("restore: the sea ring and the falls back", Ground[TEXT("EnvSea")]->GetRelativeLocation().Equals(FVector(0, -45, -172), 1e-3) &&
                                                          FMath::IsNearlyEqual(Ground[TEXT("EnvWaterfall_fall_s_Sheet")]->GetRelativeScale3D().Z, 1.0) &&
                                                          FMath::IsNearlyEqual(Ground[TEXT("EnvWaterfall_fall_s_Foam")]->GetRelativeLocation().Z, -120.0, 0.01));
  TestTrue("restore: hidden parts visible, no tweak left", Props[Fort]->IsVisible() && EnvLights[0]->IsVisible() &&
                                                              Ground[TEXT("EnvGround_0")]->IsVisible() && Rt.Tweaks.IsEmpty());
  S08ConceptPaste::Clear(Parts, Lights, Rt);
  TestTrue("clear: no light left", Lights.IsEmpty() && Rt.Lights == 0);
  for (TPair<FString, UStaticMeshComponent*>& G : Ground) G.Value->DestroyComponent();
  S08EnvLayout::Clear(Props, EnvLights);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteMaterialOverrideTest,
    "Unmatched.S08.ConceptPaste.MaterialOverride env-layout prop \"material\": every slot / per slot, rejections, overlay replace, spawn, missing kept",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteMaterialOverrideTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  const FString Grid = TEXT("/Engine/EngineDebugMaterials/VertexColorMaterial");
  auto Layout = [](const FString& Props) {
    return TEXT("{\"schema\":\"unmatched.env-layout/1\",\"map\":\"cptest\",\"boardId\":\"cidCp\",\"props\":[") + Props + TEXT("]}");
  };
  const FString Good = Layout(
      TEXT("{\"id\":\"a\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[600,0,-3],\"material\":\"/Engine/EngineDebugMaterials/VertexColorMaterial\"},"
           "{\"id\":\"b\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[650,0,-3],\"material\":[null,\"/Engine/EngineDebugMaterials/VertexColorMaterial\"]},"
           "{\"id\":\"c\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[700,0,-3],\"material\":[\"/Engine/EngineDebugMaterials/VertexColorMaterial\"]},"
           "{\"id\":\"d\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[750,0,-3],\"material\":\"/Game/EnvMaps/NoSuchScene/MI_NoSuchScene\"},"
           "{\"id\":\"e\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[800,0,-3]}"));
  FS08EnvLayout L;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("layout with overrides parses: ") + FString::Join(Errors, TEXT(" | ")), L.ParseJson(Good, Errors))) return false;
  const FS08EnvProp* A = L.FindProp(TEXT("a"));
  const FS08EnvProp* B = L.FindProp(TEXT("b"));
  const FS08EnvProp* E = L.FindProp(TEXT("e"));
  TestTrue("a: one path for every slot", A && A->bMaterialAllSlots && A->Materials.Num() == 1 && A->MaterialForSlot(0) == Grid &&
                                             A->MaterialForSlot(3) == Grid);
  TestTrue("b: per slot, null = the mesh's own", B && !B->bMaterialAllSlots && B->Materials.Num() == 2 &&
                                                     B->MaterialForSlot(0).IsEmpty() && B->MaterialForSlot(1) == Grid &&
                                                     B->MaterialForSlot(2).IsEmpty());
  TestTrue("e: no override", E && E->Materials.IsEmpty() && E->MaterialForSlot(0).IsEmpty());
  FString Seventeen = TEXT("[");
  for (int32 I = 0; I < 17; ++I) Seventeen += I ? TEXT(",\"\"") : TEXT("\"\"");
  Seventeen += TEXT("]");
  for (const FString& Bad : {FString(TEXT("5")), FString(TEXT("\"Game/X/MI_X\"")), FString(TEXT("[]")), FString(TEXT("[5]")),
                             FString(TEXT("[\"/Game/X MI\"]")), Seventeen}) {
    FS08EnvLayout Rejected;
    TArray<FString> E2;
    const bool bOk = Rejected.ParseJson(
        Layout(TEXT("{\"id\":\"x\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[600,0,-3],\"material\":") + Bad + TEXT("}")), E2);
    TestTrue(TEXT("rejected material ") + Bad, !bOk && FString::Join(E2, TEXT(" | ")).Contains(TEXT("material must be")));
  }
  // an overlay may replace / add the field (the scene overlay puts projected MIs on pack meshes)
  const FString Overlay = TEXT(
      "{\"schema\":\"unmatched.env-layout-overlay/1\",\"map\":\"cptest\",\"variant\":\"scene\","
      "\"props\":{\"replace\":[{\"id\":\"e\",\"material\":\"/Engine/EngineDebugMaterials/VertexColorMaterial\"}],"
      "\"add\":[{\"id\":\"f\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[850,0,-3],\"material\":[\"\"]}]}}");
  FS08EnvLayout Merged;
  FS08EnvVariantResult R;
  if (TestTrue(TEXT("overlay with material merges: ") + FString::Join(R.Errors, TEXT(" | ")),
               S08EnvLayout::MergeOverlay(Good, Overlay, TEXT("cptest"), TEXT("scene"), Merged, R))) {
    const FS08EnvProp* Replaced = Merged.FindProp(TEXT("e"));
    TestTrue("replace: e gets the material", Replaced && Replaced->MaterialForSlot(0) == Grid);
  }
  // spawn: the override on the component, the mesh's own where none / missing
  FWorld W(TEXT("S08ConceptPasteMaterialOverride"));
  AActor* Owner = W.World ? W.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity) : nullptr;
  if (!TestNotNull("owner actor", Owner)) return false;
  USceneComponent* Root = NewObject<USceneComponent>(Owner, TEXT("Root"));
  Owner->SetRootComponent(Root);
  Root->RegisterComponent();
  TArray<TObjectPtr<UStaticMeshComponent>> Props;
  TArray<TObjectPtr<UPointLightComponent>> Lights;
  const FS08EnvSpawnStats S = S08EnvLayout::Spawn(L, *Owner, Root, FVector2D(445.66667, 288.66667), FBox2D(ForceInit), Props, Lights);
  if (!TestEqual("5 props", Props.Num(), 5)) return false;
  auto MatName = [](const UStaticMeshComponent* C) {
    return C && C->GetMaterial(0) ? C->GetMaterial(0)->GetName() : FString(TEXT("-"));
  };
  const FString Own = MatName(Props[4]);  // e: the cube's own material
  TestNotEqual(TEXT("the cube's own material is not the override"), Own, FString(TEXT("VertexColorMaterial")));
  TestEqual("a: every slot", MatName(Props[0]), FString(TEXT("VertexColorMaterial")));
  TestEqual("b: slot 0 kept (null), the extra slot ignored", MatName(Props[1]), Own);
  TestEqual("c: per slot 0", MatName(Props[2]), FString(TEXT("VertexColorMaterial")));
  TestEqual("d: missing material -> the mesh's own", MatName(Props[3]), Own);
  TestTrue(FString::Printf(TEXT("stats: overrides %d (2), missing materials %d (1)"), S.MaterialOverrides, S.MissingMaterials),
           S.MaterialOverrides == 2 && S.MissingMaterials == 1);
  S08EnvLayout::Clear(Props, Lights);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ConceptPasteLightsOffTest,
    "Unmatched.S08.ConceptPaste.LightsOff -ArtPreviewLightsOff (gate G1): key / points / sky light at 0, fog hidden, block lights at 0, lit3d sky hidden",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ConceptPasteLightsOffTest::RunTest(const FString&) {
  using namespace S08ConceptPasteTest;
  FWorld W(TEXT("S08ConceptPasteLightsOff"));
  if (!TestNotNull("test world", W.World)) return false;
  AActor* LightActor = W.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity);
  AActor* Owner = W.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity);
  if (!TestNotNull("actors", LightActor) || !TestNotNull("owner", Owner)) return false;
  USceneComponent* Root = NewObject<USceneComponent>(Owner, TEXT("Root"));
  Owner->SetRootComponent(Root);
  Root->RegisterComponent();
  USceneComponent* LightRoot = NewObject<USceneComponent>(LightActor, TEXT("LightRoot"));
  LightActor->SetRootComponent(LightRoot);
  LightRoot->RegisterComponent();
  UDirectionalLightComponent* Key = NewObject<UDirectionalLightComponent>(LightActor, TEXT("Key"));
  Key->SetupAttachment(LightRoot);
  Key->SetMobility(EComponentMobility::Movable);
  Key->RegisterComponent();
  Key->SetIntensity(3.0f);
  UPointLightComponent* MoonPool = NewObject<UPointLightComponent>(LightActor, TEXT("MoonPool"));
  MoonPool->SetupAttachment(LightRoot);
  MoonPool->SetMobility(EComponentMobility::Movable);
  MoonPool->RegisterComponent();
  MoonPool->SetIntensity(260.0f);
  USkyLightComponent* Sky = NewObject<USkyLightComponent>(LightActor, TEXT("Sky"));  // not registered: no capture
  Sky->SetMobility(EComponentMobility::Movable);
  Sky->Intensity = 3.0f;
  UExponentialHeightFogComponent* Fog = NewObject<UExponentialHeightFogComponent>(LightActor, TEXT("Fog"));
  Fog->SetupAttachment(LightRoot);
  Fog->RegisterComponent();
  auto Point = [Owner, Root](const TCHAR* Name, float Cd) {
    UPointLightComponent* L = NewObject<UPointLightComponent>(Owner, FName(Name));
    L->SetupAttachment(Root);
    L->SetMobility(EComponentMobility::Movable);
    L->RegisterComponent();
    L->SetIntensity(Cd);
    return L;
  };
  TArray<TObjectPtr<UPointLightComponent>> EnvLights = {Point(TEXT("EnvLamp"), 40.0f)};
  TArray<TObjectPtr<UPointLightComponent>> BlockLights = {Point(TEXT("FireFort"), 65.0f), Point(TEXT("DeckN"), 95.0f)};
  UStaticMeshComponent* SkyPart = NewObject<UStaticMeshComponent>(Owner, TEXT("ConceptSceneSky"));
  SkyPart->SetupAttachment(Root);
  SkyPart->RegisterComponent();
  TArray<TObjectPtr<UStaticMeshComponent>> BlockParts = {SkyPart};
  TArray<TObjectPtr<UStaticMeshComponent>> EnvProps;
  FS08EnvLayoutRuntime Env;
  const TArray<TObjectPtr<AActor>> SceneActors = {LightActor};
  // the paste keeps its painted layer (the P7c reference of G1)
  FS08LightsOffStats S = S08ConceptPaste::ApplyLightsOff(SceneActors, EnvLights, BlockLights, EnvProps, Env, BlockParts, false,
                                                         W.World, nullptr, TEXT("cpmap"));
  TestTrue("paste: the block's parts stay", SkyPart->IsVisible() && S.SkyParts == 0);
  TestTrue(FString::Printf(TEXT("key %g, moon-pool %g, sky %g at 0"), Key->Intensity, MoonPool->Intensity, Sky->Intensity),
           Key->Intensity == 0.0f && MoonPool->Intensity == 0.0f && Sky->Intensity == 0.0f);
  TestTrue("env + block points at 0", EnvLights[0]->Intensity == 0.0f && BlockLights[0]->Intensity == 0.0f && BlockLights[1]->Intensity == 0.0f);
  TestTrue("fog hidden", !Fog->IsVisible() && S.bFogHidden);
  TestTrue(FString::Printf(TEXT("counts: directional %d, points %d, sky %d, env %d, block %d"), S.Directional, S.ProfilePoints,
                           S.SkyLights, S.EnvLights, S.ConceptLights),
           S.Directional == 1 && S.ProfilePoints == 1 && S.SkyLights == 1 && S.EnvLights == 1 && S.ConceptLights == 2);
  TestFalse("no MPC without the collection", S.bCollection);
  // lit3d: the unlit sky cylinder goes too (the environment must be dark without engine light)
  S = S08ConceptPaste::ApplyLightsOff(SceneActors, EnvLights, BlockLights, EnvProps, Env, BlockParts, true, W.World, nullptr,
                                      TEXT("cpmap"));
  TestTrue("lit3d: the sky cylinder hidden, idempotent", !SkyPart->IsVisible() && S.SkyParts == 1 && Key->Intensity == 0.0f);
  TestTrue("the emissive scalars it zeroes", S08ConceptPaste::LightsOffEmissiveParams().Contains(FName(TEXT("EmissiveIntensity"))) &&
                                                  S08ConceptPaste::LightsOffEmissiveParams().Contains(FName(TEXT("EmissiveStrength"))));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
