// ENV-MAPS track C automation tests: the environment layouts of the original-map boards (S08EnvLayout.h).
//   Parse     a valid document (every field), the apron -> tray math, a minimal document
//   Invalid   30 rejection cases (JSON, schema, keys, tray / apron, props, lights, budgets)
//   Tray      TrayFit / ApplyTray invert S08Diorama::FitTray exactly; apron-only; refusals; map / tray predicates
//   Resolve   <map>.layout.json by map key + board id, fallback by board id, absent / mismatch; the flag gate
//   Spawn     a fake map-image board: component counts and settings, missing-mesh and inside-map tolerance, Update
//             keeps / respawns / clears, absent and invalid layouts spawn nothing
//   Actor     the board actor: nothing without the flags, nothing on a grid board, nothing on a refused map profile;
//             the shipped Marmoreal board once the map, the kit and the layout exist (else AddWarning)
//   Shipped   Config/ArtBoards/EnvLayouts/{marmoreal,sarpedon}.layout.json against the contract (AddWarning if absent)
//   KitAssets the imported /Game/EnvKit kit against tools/art/env_kit/ue_import_env_kit.py (AddWarning if absent)
//   P5c track V:
//   FxParse   the optional "fx" section: fields, user parameters, seed / warmup, anchored transform; rejection table
//   Variant   -EnvLayoutVariant overlays: merge (remove / replace / add, fx dropped with their anchor), rejection
//             table, ApplyVariant none / absent / invalid fallback / ok, overlay files never resolve as a base
//   FxSpawn   a fake map-image board: Niagara components (transient system, not activated) - counts, settings,
//             anchored transform, skips (disabled / anchor / on the map / missing system), near band, -ArtPreviewNoFx,
//             Update with a variant overlay + fx (keep / respawn / fallback), board change and grid clear the fx
//   FxAssets  the derived /Game/EnvKit/FX systems of the shipped layouts: CPU, deterministic, no light / component
//             renderer (tools/art/env_kit/ue_import_fab_fx.py; AddWarning if absent)
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.EnvLayout; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08Contracts.h"
#include "S08Diorama.h"
#include "S08EnvLayout.h"
#include "Components/PointLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Engine.h"
#include "Engine/Scene.h"  // ELightUnits (LightComponent.h only forward-declares it)
#include "Engine/StaticMesh.h"
#include "Engine/Texture.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInterface.h"
#include "Misc/AutomationTest.h"
#include "Misc/Crc.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "NiagaraComponent.h"
#include "NiagaraComponentRendererProperties.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraLightRendererProperties.h"
#include "NiagaraRendererProperties.h"
#include "NiagaraSystem.h"
#include "PhysicsEngine/BodySetup.h"
#include "UObject/Package.h"

namespace S08EnvLayoutTest {
struct FGateScope {
  FGateScope(bool bDiorama, bool bOptOut) {
    S08Diorama::SetFlagOverrideForTest(bDiorama);
    S08EnvLayout::SetOptOutOverrideForTest(bOptOut);
  }
  ~FGateScope() {
    S08Diorama::ResetFlagOverrideForTest();
    S08EnvLayout::ResetOptOutOverrideForTest();
  }
};

const FVector2D MapHalf(445.66667, 288.66667);            // 1337 x 866 px at 2/3 uu per px, halved
const FVector2D FrameHalf(445.66667 + 24.0, 288.66667 + 24.0);  // + the 24 uu wooden frame
const TCHAR* const CubePath = TEXT("/Engine/BasicShapes/Cube");
const TCHAR* const MissingMeshPath = TEXT("/Game/EnvKit/NoSuchTest/SM_Env_NoSuchTest");

/** A valid layout: 2 props (cube, rotated / scaled / shadowless), 1 light, tray + a consistent apron. */
const TCHAR* const ValidJson = TEXT(
    "{\"schema\":\"unmatched.env-layout/1\",\"map\":\"marmoreal\",\"boardId\":\"c121b47f8d6eb28daccb76d05\","
    "\"tray\":{\"halfX\":619.667,\"halfY\":472.667,\"offsetY\":-10},"
    "\"apron\":{\"n\":170,\"s\":150,\"w\":150,\"e\":150},"
    "\"props\":["
    "{\"id\":\"cube-nw\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[-560,-400,-3],\"yawDeg\":30,\"scale\":0.5,"
    "\"castShadow\":false},"
    "{\"id\":\"cube-ne\",\"mesh\":\"/Engine/BasicShapes/Cube.Cube\",\"loc\":[560,-400,-3]}],"
    "\"lights\":[{\"id\":\"lamp-nw\",\"type\":\"point\",\"loc\":[-560,-400,120],\"colorSrgb\":\"#FFB870\","
    "\"intensityCd\":40,\"radius\":450,\"castShadow\":false}],"
    "\"notes\":\"test\",\"futureField\":{\"ignored\":true}}");

/** Prop / light entry fragments for the rejection table and the spawn layouts. */
FString PropJson(const FString& Id, const FString& Mesh, const FVector& Loc, const FString& Extra = FString()) {
  return FString::Printf(TEXT("{\"id\":\"%s\",\"mesh\":\"%s\",\"loc\":[%.3f,%.3f,%.3f]%s}"), *Id, *Mesh, Loc.X, Loc.Y,
                         Loc.Z, *Extra);
}

FString LightJson(const FString& Id, const FVector& Loc, const FString& Extra = FString()) {
  return FString::Printf(TEXT("{\"id\":\"%s\",\"type\":\"point\",\"loc\":[%.1f,%.1f,%.1f],\"colorSrgb\":\"#FFB870\","
                              "\"intensityCd\":40,\"radius\":450%s}"),
                         *Id, Loc.X, Loc.Y, Loc.Z, *Extra);
}

FString LayoutJson(const FString& Map, const FString& BoardId, const TArray<FString>& Props,
                   const TArray<FString>& Lights, const FString& Extra = FString()) {
  return FString::Printf(TEXT("{\"schema\":\"unmatched.env-layout/1\",\"map\":\"%s\",\"boardId\":\"%s\",\"props\":[%s],"
                              "\"lights\":[%s]%s}"),
                         *Map, *BoardId, *FString::Join(Props, TEXT(",")), *FString::Join(Lights, TEXT(",")), *Extra);
}

FString TempDir(const TCHAR* Leaf) {
  const FString Dir = FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::AutomationTransientDir(), TEXT("S08EnvLayout"), Leaf));
  IFileManager::Get().DeleteDirectory(*Dir, false, true);
  IFileManager::Get().MakeDirectory(*Dir, true);
  return Dir;
}

bool WriteText(const FString& Path, const FString& Text) {
  return FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

FS08BoardModel EnvGridBoard(int32 W, int32 H) {
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

/** 3 x 2 lattice with three linked spaces (the S08BoardArtTests synthetic topology, own copy for unity builds). */
bool EnvTopologyBoard(FS08BoardModel& Out) {
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

/** Board-art data with one map-image profile ("envmap", Board row id cidEnv) whose map assets do not exist. */
const TCHAR* const MapDocJson = TEXT(
    "{\"schema\":\"unmatched.s08-art-board-profiles/1\",\"revision\":7,"
    "\"zoneStyles\":{\"a\":{\"stroke\":\"solid\",\"glyph\":\"diamond\",\"color\":\"#102030\"},"
    "\"b\":{\"stroke\":\"dash2\",\"glyph\":\"ring\",\"color\":\"#A0B0C0\"}},"
    "\"fallbackZoneStyle\":{\"stroke\":\"dots5\",\"glyph\":\"bar1\",\"color\":\"#FFFFFF\"},"
    "\"lightProfiles\":{\"L\":{\"directional\":{\"name\":\"key\",\"posUU\":[0,0,600],\"rotation\":[-50,-90,0],"
    "\"intensity\":3,\"castShadows\":true},\"points\":[{\"name\":\"p\",\"at\":[0.5,-0.5,200],\"intensity\":50,"
    "\"radiusUU\":300,\"colorLinear\":[1,0.5,0.25]}]}},"
    "\"boards\":[{\"id\":\"envmap\",\"match\":{\"boardIds\":[\"cidEnv\"]},\"surface\":\"map-image\",\"light\":\"L\","
    "\"mapImage\":{\"name\":\"NoSuchEnvTest\",\"bc\":\"/Game/EnvMaps/NoSuchEnvTest/T_NoSuchEnvTest_Map_BC_4K\","
    "\"mask\":\"/Game/EnvMaps/NoSuchEnvTest/T_NoSuchEnvTest_Map_GameMask_4K\","
    "\"sdf\":\"/Game/EnvMaps/NoSuchEnvTest/T_NoSuchEnvTest_Map_GameSDF_4K\","
    "\"id\":\"/Game/EnvMaps/NoSuchEnvTest/T_NoSuchEnvTest_Map_SpaceID_4K\","
    "\"materialInstance\":\"/Game/EnvMaps/NoSuchEnvTest/MI_NoSuchEnvTest_MapBoard\","
    "\"srcSize\":[1337,866],\"uuPerPx\":0.6666667,\"frameUU\":24}}]}");

/** The fixed kit contract (S08EnvLayout.h / ue_import_env_kit.py): map folder -> SM_Env_<Name> names. */
const TMap<FString, TArray<FString>>& KitNames() {
  static const TMap<FString, TArray<FString>> Names = {
      // P5 (ENV-MAPS track A): + Balustrade, HedgeBed and the three lane K back-wall modules (Marmoreal); + Barrel,
      // CrateStack, LanternPost, Banner, RockOutcrop (Sarpedon) - tools/art/env_kit/ue_import_env_kit.py / layout_check.py KIT
      {TEXT("Marmoreal"), {TEXT("ArcadeBay"), TEXT("Portal"), TEXT("Cherry"), TEXT("PlinthBall"), TEXT("LanternPlinth"),
                           TEXT("Urn"), TEXT("Cypress"), TEXT("Balustrade"), TEXT("HedgeBed"), TEXT("BackWall_BayDoor"),
                           TEXT("BackWall_BayWindows"), TEXT("BackWall_Centre")}},
      {TEXT("Sarpedon"), {TEXT("FortRuin"), TEXT("Tree"), TEXT("Hull"), TEXT("Cannon"), TEXT("Campfire"), TEXT("Palisade"),
                          TEXT("Rope"), TEXT("Barrel"), TEXT("CrateStack"), TEXT("LanternPost"), TEXT("Banner"),
                          TEXT("RockOutcrop")}}};
  return Names;
}

/** The material set of a kit mesh (ue_import_env_kit.py MATERIAL_OF): the back-wall modules share MI_Env_BackWall and
 *  T_Env_BackWall_*; every other mesh has its own. */
FString KitMaterialSetOf(const FString& Name) {
  return Name.StartsWith(TEXT("BackWall_")) ? FString(TEXT("BackWall")) : Name;
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
}  // namespace S08EnvLayoutTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutParseTest,
    "Unmatched.S08.EnvLayout.Parse a valid layout keeps every field; the apron implies the tray; a minimal layout parses",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutParseTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  FS08EnvLayout L;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("valid layout parses: ") + FString::Join(Errors, TEXT(" | ")), L.ParseJson(ValidJson, Errors))) {
    return false;
  }
  TestEqual("no errors", Errors.Num(), 0);
  TestEqual("map", L.Map, FString(TEXT("marmoreal")));
  TestEqual("boardId", L.BoardId, FString(TEXT("c121b47f8d6eb28daccb76d05")));
  TestTrue("tray", L.Tray.bSet && FMath::IsNearlyEqual(L.Tray.HalfX, 619.667f, 1e-3f) &&
                       FMath::IsNearlyEqual(L.Tray.HalfY, 472.667f, 1e-3f) && FMath::IsNearlyEqual(L.Tray.OffsetY, -10.0f));
  TestTrue("apron", L.Apron.bSet && L.Apron.N == 170.0f && L.Apron.S == 150.0f && L.Apron.W == 150.0f &&
                        L.Apron.E == 150.0f);
  if (TestEqual("2 props", L.Props.Num(), 2)) {
    const FS08EnvProp& A = L.Props[0];
    TestEqual("prop 0 id", A.Id, FString(TEXT("cube-nw")));
    TestEqual("prop 0 mesh", A.Mesh, FString(CubePath));
    TestTrue("prop 0 loc", A.Loc.Equals(FVector(-560.0, -400.0, -3.0), 1e-6));
    TestTrue("prop 0 yaw / scale / shadow", A.YawDeg == 30.0f && A.Scale == 0.5f && !A.bCastShadow);
    const FTransform T = A.Transform();
    TestTrue("prop 0 transform", T.GetTranslation().Equals(A.Loc, 1e-6) &&
                                     FMath::IsNearlyEqual(T.Rotator().Yaw, 30.0, 1e-3) &&
                                     T.GetScale3D().Equals(FVector(0.5), 1e-6));
    const FS08EnvProp& B = L.Props[1];
    TestTrue("prop 1 defaults: yaw 0, scale 1, shadow on", B.YawDeg == 0.0f && B.Scale == 1.0f && B.bCastShadow);
    TestEqual("'Pkg.Obj' mesh form kept", B.Mesh, FString(TEXT("/Engine/BasicShapes/Cube.Cube")));
  }
  if (TestEqual("1 light", L.Lights.Num(), 1)) {
    const FS08EnvLight& Lamp = L.Lights[0];
    TestTrue("light fields", Lamp.Id == TEXT("lamp-nw") && Lamp.Loc.Equals(FVector(-560.0, -400.0, 120.0)) &&
                                 Lamp.IntensityCd == 40.0f && Lamp.RadiusUU == 450.0f);
    TestTrue("light colour sRGB bytes", Lamp.Color == FColor(0xFF, 0xB8, 0x70, 0xFF));
    TestEqual("light colour hex", Lamp.ColorHex(), FString(TEXT("#FFB870")));
  }
  TestEqual("notes", L.Notes, FString(TEXT("test")));
  TestEqual("unique meshes", L.UniqueMeshPaths().Num(), 2);
  // apron -> tray: X symmetric max(w, e); far edge -(frame + n), near edge frame + s.
  const FS08EnvTray Implied = L.Apron.ImpliedTray(FrameHalf);
  AddInfo(FString::Printf(TEXT("apron-implied tray %.3f x %.3f offsetY %.3f"), Implied.HalfX, Implied.HalfY, Implied.OffsetY));
  TestTrue("implied halfX = frame + 150", FMath::IsNearlyEqual(Implied.HalfX, 619.667f, 1e-2f));
  TestTrue("implied halfY = frame + (170 + 150) / 2", FMath::IsNearlyEqual(Implied.HalfY, 472.667f, 1e-2f));
  TestTrue("implied offsetY = (150 - 170) / 2 = -10 (far side)", FMath::IsNearlyEqual(Implied.OffsetY, -10.0f, 1e-4f));
  TestTrue("implied far edge = -(frame + n)",
           FMath::IsNearlyEqual(Implied.OffsetY - Implied.HalfY, -(FrameHalf.Y + 170.0), 1e-2));
  TestTrue("implied near edge = frame + s",
           FMath::IsNearlyEqual(Implied.OffsetY + Implied.HalfY, FrameHalf.Y + 150.0, 1e-2));
  // minimal: no tray / apron / lights / notes, empty props
  FS08EnvLayout Min;
  Errors.Reset();
  TestTrue(TEXT("minimal layout parses: ") + FString::Join(Errors, TEXT(" | ")),
           Min.ParseJson(TEXT("{\"schema\":\"unmatched.env-layout/1\",\"map\":\"sarpedon\",\"boardId\":\"c7fa64a26c29a0835f2383e63\",\"props\":[]}"),
                         Errors));
  TestTrue("minimal: nothing set", !Min.Tray.bSet && !Min.Apron.bSet && Min.Props.Num() == 0 && Min.Lights.Num() == 0);
  // a re-parse resets the previous content
  Errors.Reset();
  TestFalse("broken re-parse", L.ParseJson(TEXT("{}"), Errors));
  TestTrue("re-parse reset the props", L.Props.Num() == 0 && L.Map.IsEmpty());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutInvalidTest,
    "Unmatched.S08.EnvLayout.Invalid every structural error rejects the whole layout",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutInvalidTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  const FString Board = TEXT("c121b47f8d6eb28daccb76d05");
  const FString P = PropJson(TEXT("p"), CubePath, FVector(-600, 0, -3));
  const FString Lamp = LightJson(TEXT("l"), FVector(-600, 0, 100));
  TArray<FString> SevenLights;
  for (int32 I = 0; I < 7; ++I) SevenLights.Add(LightJson(FString::Printf(TEXT("l%d"), I), FVector(-600, 0, 100)));
  struct FCase {
    const TCHAR* Name;
    FString Json;
    const TCHAR* Expect;  // substring of one error
  };
  const FCase Cases[] = {
      {TEXT("not JSON"), TEXT("not json"), TEXT("invalid JSON")},
      {TEXT("truncated JSON"), TEXT("{\"schema\":\"unmatched.env-layout/1\",\"map\":\"marm"), TEXT("invalid JSON")},
      {TEXT("wrong schema"), TEXT("{\"schema\":\"unmatched.env-layout/2\",\"map\":\"marmoreal\",\"boardId\":\"x\",\"props\":[]}"),
       TEXT("schema")},
      {TEXT("map missing"), TEXT("{\"schema\":\"unmatched.env-layout/1\",\"boardId\":\"x\",\"props\":[]}"), TEXT("map")},
      {TEXT("map upper-case"), LayoutJson(TEXT("Marmoreal"), Board, {P}, {}), TEXT("map")},
      {TEXT("boardId missing"), TEXT("{\"schema\":\"unmatched.env-layout/1\",\"map\":\"marmoreal\",\"props\":[]}"), TEXT("boardId")},
      {TEXT("boardId with a space"), LayoutJson(TEXT("marmoreal"), TEXT("c12 1"), {P}, {}), TEXT("boardId")},
      {TEXT("props missing"), TEXT("{\"schema\":\"unmatched.env-layout/1\",\"map\":\"marmoreal\",\"boardId\":\"x\"}"),
       TEXT("props array missing")},
      {TEXT("tray halfX 0"), LayoutJson(TEXT("marmoreal"), Board, {P}, {}, TEXT(",\"tray\":{\"halfX\":0,\"halfY\":400}")),
       TEXT("tray")},
      {TEXT("tray halfY missing"), LayoutJson(TEXT("marmoreal"), Board, {P}, {}, TEXT(",\"tray\":{\"halfX\":600}")),
       TEXT("tray")},
      {TEXT("tray offsetY string"),
       LayoutJson(TEXT("marmoreal"), Board, {P}, {}, TEXT(",\"tray\":{\"halfX\":600,\"halfY\":400,\"offsetY\":\"-10\"}")),
       TEXT("tray")},
      {TEXT("apron negative"),
       LayoutJson(TEXT("marmoreal"), Board, {P}, {}, TEXT(",\"apron\":{\"n\":-1,\"s\":10,\"w\":10,\"e\":10}")), TEXT("apron")},
      {TEXT("apron side missing"), LayoutJson(TEXT("marmoreal"), Board, {P}, {}, TEXT(",\"apron\":{\"n\":1,\"s\":10,\"w\":10}")),
       TEXT("apron")},
      {TEXT("prop not an object"), LayoutJson(TEXT("marmoreal"), Board, {TEXT("3")}, {}), TEXT("not an object")},
      {TEXT("prop id missing"), LayoutJson(TEXT("marmoreal"), Board, {TEXT("{\"mesh\":\"/Game/EnvKit/M/SM_Env_Urn\",\"loc\":[600,0,0]}")}, {}),
       TEXT("id missing")},
      {TEXT("duplicate prop id"), LayoutJson(TEXT("marmoreal"), Board, {P, P}, {}), TEXT("duplicate id")},
      {TEXT("mesh without a root"), LayoutJson(TEXT("marmoreal"), Board, {PropJson(TEXT("p"), TEXT("Game/EnvKit/X"), FVector(600, 0, 0))}, {}),
       TEXT("package path")},
      {TEXT("mesh under another root"), LayoutJson(TEXT("marmoreal"), Board, {PropJson(TEXT("p"), TEXT("/Other/SM_X"), FVector(600, 0, 0))}, {}),
       TEXT("package path")},
      {TEXT("mesh with a space"), LayoutJson(TEXT("marmoreal"), Board, {PropJson(TEXT("p"), TEXT("/Game/Env Kit/SM_X"), FVector(600, 0, 0))}, {}),
       TEXT("package path")},
      {TEXT("mesh with two dots"), LayoutJson(TEXT("marmoreal"), Board, {PropJson(TEXT("p"), TEXT("/Game/A/SM_X.SM_X.Y"), FVector(600, 0, 0))}, {}),
       TEXT("package path")},
      {TEXT("loc with 2 numbers"), LayoutJson(TEXT("marmoreal"), Board, {TEXT("{\"id\":\"p\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[1,2]}")}, {}),
       TEXT("loc")},
      {TEXT("loc with strings"), LayoutJson(TEXT("marmoreal"), Board, {TEXT("{\"id\":\"p\",\"mesh\":\"/Engine/BasicShapes/Cube\",\"loc\":[\"1\",\"2\",\"3\"]}")}, {}),
       TEXT("loc")},
      {TEXT("scale 0"), LayoutJson(TEXT("marmoreal"), Board, {PropJson(TEXT("p"), CubePath, FVector(600, 0, 0), TEXT(",\"scale\":0"))}, {}),
       TEXT("scale")},
      {TEXT("scale 25"), LayoutJson(TEXT("marmoreal"), Board, {PropJson(TEXT("p"), CubePath, FVector(600, 0, 0), TEXT(",\"scale\":25"))}, {}),
       TEXT("scale")},
      {TEXT("castShadow not a bool"),
       LayoutJson(TEXT("marmoreal"), Board, {PropJson(TEXT("p"), CubePath, FVector(600, 0, 0), TEXT(",\"castShadow\":\"yes\""))}, {}),
       TEXT("castShadow")},
      {TEXT("7 point lights"), LayoutJson(TEXT("marmoreal"), Board, {P}, SevenLights), TEXT("point lights")},
      {TEXT("light type spot"), LayoutJson(TEXT("marmoreal"), Board, {P}, {LightJson(TEXT("l"), FVector(0, -400, 100)).Replace(TEXT("\"point\""), TEXT("\"spot\""))}),
       TEXT("type")},
      {TEXT("light colour not hex"), LayoutJson(TEXT("marmoreal"), Board, {P}, {Lamp.Replace(TEXT("#FFB870"), TEXT("orange"))}),
       TEXT("colorSrgb")},
      {TEXT("light intensity 0"), LayoutJson(TEXT("marmoreal"), Board, {P}, {Lamp.Replace(TEXT("\"intensityCd\":40"), TEXT("\"intensityCd\":0"))}),
       TEXT("intensityCd")},
      {TEXT("light radius missing"), LayoutJson(TEXT("marmoreal"), Board, {P}, {Lamp.Replace(TEXT(",\"radius\":450"), TEXT(""))}),
       TEXT("radius")},
      {TEXT("light shadowed"), LayoutJson(TEXT("marmoreal"), Board, {P}, {LightJson(TEXT("l"), FVector(0, -400, 100), TEXT(",\"castShadow\":true"))}),
       TEXT("never cast shadows")},
      {TEXT("duplicate light id"), LayoutJson(TEXT("marmoreal"), Board, {P}, {Lamp, Lamp}), TEXT("duplicate id")},
      {TEXT("lights not an array"),
       FString::Printf(TEXT("{\"schema\":\"unmatched.env-layout/1\",\"map\":\"marmoreal\",\"boardId\":\"%s\",\"props\":[],\"lights\":{}}"), *Board),
       TEXT("lights is not an array")},
  };
  // the building blocks themselves are valid
  {
    FS08EnvLayout Ok;
    TArray<FString> Errors;
    TestTrue(TEXT("control: one prop + one light parses: ") + FString::Join(Errors, TEXT(" | ")),
             Ok.ParseJson(LayoutJson(TEXT("marmoreal"), Board, {P}, {Lamp}), Errors));
    TArray<FString> SixLights = SevenLights;
    SixLights.RemoveAt(SixLights.Num() - 1);
    Errors.Reset();
    TestTrue(TEXT("control: exactly 6 point lights parse: ") + FString::Join(Errors, TEXT(" | ")),
             Ok.ParseJson(LayoutJson(TEXT("marmoreal"), Board, {P}, SixLights), Errors));
  }
  for (const FCase& C : Cases) {
    FS08EnvLayout L;
    TArray<FString> Errors;
    const bool bOk = L.ParseJson(C.Json, Errors);
    TestFalse(FString::Printf(TEXT("%s: rejected"), C.Name), bOk);
    const FString All = FString::Join(Errors, TEXT(" | "));
    TestTrue(FString::Printf(TEXT("%s: error mentions '%s' (%s)"), C.Name, C.Expect, *All), All.Contains(C.Expect));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutTrayTest,
    "Unmatched.S08.EnvLayout.Tray the layout tray drives S08Diorama::FitTray exactly; refused trays keep the placeholder",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutTrayTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  FS08EnvLayout L;
  TArray<FString> Errors;
  if (!TestTrue("valid layout", L.ParseJson(ValidJson, Errors))) return false;
  FVector2D BoardHalf, Offset;
  FString Source, Reason;
  TestTrue("tray accepted", S08EnvLayout::TrayFit(L, FrameHalf, BoardHalf, Offset, Source, Reason));
  TestEqual("source layout", Source, FString(TEXT("layout")));
  const S08Diorama::FTrayFit Fit = S08Diorama::FitTray(BoardHalf, Offset);
  AddInfo(FString::Printf(TEXT("layout tray: fit half %s offset %s -> outer %s at %s, yaw %.0f, scale %s, anisotropy %.3f"),
                          *BoardHalf.ToString(), *Offset.ToString(), *Fit.WorldHalf.ToString(), *Fit.Location.ToString(),
                          Fit.YawDeg, *Fit.Scale.ToString(), Fit.Anisotropy()));
  TestTrue("outer half = the layout tray", Fit.WorldHalf.Equals(FVector2D(619.667, 472.667), 1e-3));
  TestTrue("tray centre = (0, offsetY)", Fit.Location.Equals(FVector2D(0.0, -10.0), 1e-6));
  TestEqual("map tray yaw 0", Fit.YawDeg, 0.0f);
  const FBox Box = FBox(FVector(-S08Diorama::MeshHalfX, -S08Diorama::MeshHalfY, S08Diorama::BottomZ),
                        FVector(S08Diorama::MeshHalfX, S08Diorama::MeshHalfY, S08Diorama::TopZ))
                       .TransformBy(FTransform(FRotator(0.0f, Fit.YawDeg, 0.0f), FVector(Fit.Location.X, Fit.Location.Y, 0.0),
                                               Fit.Scale));
  TestTrue(FString::Printf(TEXT("tray mesh bounds %s span far -482.7 .. near 462.7, x +-619.7"), *Box.ToString()),
           FMath::IsNearlyEqual(Box.Min.Y, -482.667, 0.01) && FMath::IsNearlyEqual(Box.Max.Y, 462.667, 0.01) &&
               FMath::IsNearlyEqual(Box.Max.X, 619.667, 0.01) && FMath::IsNearlyEqual(Box.Max.Z, S08Diorama::TopZ, 0.01));
  const FBox2D Top = S08EnvLayout::TrayTopRect(&L, FrameHalf, FVector2D::ZeroVector);
  TestTrue(FString::Printf(TEXT("tray top rect %s"), *Top.ToString()),
           Top.bIsValid && Top.Min.Equals(FVector2D(-619.667, -482.667), 0.01) && Top.Max.Equals(FVector2D(619.667, 462.667), 0.01));
  // ApplyTray: only for an applied valid layout; the in/out values become the layout fit.
  FS08EnvLayoutRuntime Runtime;
  FVector2D Half = FrameHalf, Off(5.0, 7.0);
  TestFalse("ApplyTray: nothing applied -> inputs unchanged", S08EnvLayout::ApplyTray(Runtime, FrameHalf, Half, Off));
  TestTrue("inputs unchanged", Half.Equals(FrameHalf) && Off.Equals(FVector2D(5.0, 7.0)));
  Runtime.bApplied = true;
  Runtime.bLayoutValid = true;
  Runtime.MapKey = TEXT("marmoreal");
  Runtime.Layout = L;
  TestTrue("ApplyTray: layout tray", S08EnvLayout::ApplyTray(Runtime, FrameHalf, Half, Off));
  TestTrue("ApplyTray = TrayFit", Half.Equals(BoardHalf, 1e-6) && Off.Equals(Offset, 1e-6));
  // apron only: the implied tray
  FS08EnvLayout ApronOnly = L;
  ApronOnly.Tray = FS08EnvTray();
  TestTrue("apron only accepted", S08EnvLayout::TrayFit(ApronOnly, FrameHalf, BoardHalf, Offset, Source, Reason));
  TestEqual("source apron", Source, FString(TEXT("apron")));
  TestTrue("apron fit = layout fit (consistent test data)",
           S08Diorama::FitTray(BoardHalf, Offset).WorldHalf.Equals(FVector2D(619.667, 472.667), 1e-2));
  // neither: the placeholder of the profile
  FS08EnvLayout Neither = ApronOnly;
  Neither.Apron = FS08EnvApron();
  TestFalse("neither tray nor apron", S08EnvLayout::TrayFit(Neither, FrameHalf, BoardHalf, Offset, Source, Reason));
  TestEqual("source profile", Source, FString(TEXT("profile")));
  const FBox2D Placeholder = S08EnvLayout::TrayTopRect(&Neither, FrameHalf, FVector2D(0.0, 40.0));
  const S08Diorama::FTrayFit PlaceholderFit = S08Diorama::FitTray(FrameHalf, FVector2D(0.0, 40.0));
  TestTrue("placeholder rect = FitTray(frame, profile offset)",
           Placeholder.Min.Equals(PlaceholderFit.Location - PlaceholderFit.WorldHalf, 1e-6) &&
               Placeholder.Max.Equals(PlaceholderFit.Location + PlaceholderFit.WorldHalf, 1e-6));
  // a tray that misses the frame on the near side (offset too far back) and one smaller than the rim
  FS08EnvLayout Short = L;
  Short.Tray.OffsetY = -200.0f;
  TestFalse("tray not covering the near frame edge", S08EnvLayout::TrayFit(Short, FrameHalf, BoardHalf, Offset, Source, Reason));
  AddInfo(TEXT("refusal: ") + Reason);
  TestTrue("refusal names the frame", Reason.Contains(TEXT("frame")));
  Short.Tray.OffsetY = 0.0f;
  Short.Tray.HalfX = 400.0f;
  TestFalse("tray narrower than the frame", S08EnvLayout::TrayFit(Short, FrameHalf, BoardHalf, Offset, Source, Reason));
  Runtime.Layout = Short;
  Half = FrameHalf;
  Off = FVector2D::ZeroVector;
  TestFalse("ApplyTray: refused layout tray -> placeholder", S08EnvLayout::ApplyTray(Runtime, FrameHalf, Half, Off));
  TestTrue("placeholder inputs kept", Half.Equals(FrameHalf) && Off.IsZero());
  // map / tray predicates
  TestTrue("pivot on the map", S08EnvLayout::PivotInsideMap(FVector(100.0, -100.0, 0.0), MapHalf));
  TestFalse("pivot on the frame band (outside the painted map)", S08EnvLayout::PivotInsideMap(FVector(455.0, 0.0, 0.0), MapHalf));
  TestFalse("pivot beyond the frame", S08EnvLayout::PivotInsideMap(FVector(-600.0, -400.0, 0.0), MapHalf));
  TestTrue("box reaching over the map edge", S08EnvLayout::BoxOverlapsMap(FBox(FVector(430, -10, 0), FVector(500, 10, 100)), MapHalf));
  TestFalse("box beside the map", S08EnvLayout::BoxOverlapsMap(FBox(FVector(450, -10, 0), FVector(500, 10, 100)), MapHalf));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutResolveTest,
    "Unmatched.S08.EnvLayout.Resolve <map>.layout.json by map key and board id, fallback by board id, absent / mismatch; flag gate",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutResolveTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  // gate: -ArtPreview AND -ArtPreviewDiorama AND NOT -ArtPreviewNoEnv
  {
    FGateScope Gate(true, false);
    TestTrue("diorama + ArtPreview: enabled", S08EnvLayout::Enabled(true));
    TestFalse("no ArtPreview: disabled", S08EnvLayout::Enabled(false));
  }
  {
    FGateScope Gate(false, false);
    TestFalse("no diorama flag: disabled", S08EnvLayout::Enabled(true));
  }
  {
    FGateScope Gate(true, true);
    TestFalse("-ArtPreviewNoEnv: disabled", S08EnvLayout::Enabled(true));
    TestFalse("-ArtPreviewNoEnv: Arm false", S08EnvLayout::Arm(true));
  }
  TestEqual("map key", S08EnvLayout::MapKeyOf(TEXT("Marmoreal")), FString(TEXT("marmoreal")));
  TestTrue("default dir under Config/ArtBoards/EnvLayouts",
           S08EnvLayout::DefaultDir().EndsWith(TEXT("ArtBoards/EnvLayouts")));
  TestTrue("file name", S08EnvLayout::FileFor(TEXT("D:/x"), TEXT("sarpedon")).EndsWith(TEXT("/sarpedon.layout.json")));

  const FString Dir = TempDir(TEXT("Resolve"));
  const FString Marm = TEXT("c121b47f8d6eb28daccb76d05");
  const FString Prop = PropJson(TEXT("p"), CubePath, FVector(-600, 0, -3));
  TestTrue("write marmoreal", WriteText(S08EnvLayout::FileFor(Dir, TEXT("marmoreal")),
                                        LayoutJson(TEXT("marmoreal"), Marm, {Prop}, {})));
  FS08EnvLayout L;
  TArray<FString> Errors;
  bool bAbsent = true;
  TestTrue(TEXT("primary file by map key + board id: ") + FString::Join(Errors, TEXT(" | ")),
           S08EnvLayout::Resolve(Dir, TEXT("marmoreal"), {Marm}, L, Errors, bAbsent));
  TestFalse("not absent", bAbsent);
  TestTrue("source path + sha256", L.SourcePath.EndsWith(TEXT("marmoreal.layout.json")) && L.SourceSha256.Len() == 64);
  Errors.Reset();
  TestTrue("no board ids: map key only", S08EnvLayout::Resolve(Dir, TEXT("marmoreal"), {}, L, Errors, bAbsent));
  Errors.Reset();
  TestFalse("board id mismatch refused", S08EnvLayout::Resolve(Dir, TEXT("marmoreal"), {TEXT("cOther")}, L, Errors, bAbsent));
  TestTrue(TEXT("mismatch reported: ") + FString::Join(Errors, TEXT(" | ")), FString::Join(Errors, TEXT(" ")).Contains(TEXT("boardId")));
  TestFalse("mismatch is not 'absent'", bAbsent);
  // a file named <map> but describing another map
  TestTrue("write wrong-map file", WriteText(S08EnvLayout::FileFor(Dir, TEXT("sarpedon")),
                                             LayoutJson(TEXT("marmoreal"), Marm, {Prop}, {})));
  Errors.Reset();
  TestFalse("map mismatch refused", S08EnvLayout::Resolve(Dir, TEXT("sarpedon"), {}, L, Errors, bAbsent));
  // an invalid file
  TestTrue("write invalid file", WriteText(S08EnvLayout::FileFor(Dir, TEXT("broken")), TEXT("{\"schema\":1")));
  Errors.Reset();
  TestFalse("invalid file refused", S08EnvLayout::Resolve(Dir, TEXT("broken"), {}, L, Errors, bAbsent));
  TestFalse("invalid is not 'absent'", bAbsent);
  // fallback: no <map>.layout.json, a file named by board id carries the layout
  const FString Other = TempDir(TEXT("ResolveFallback"));
  const FString Sarp = TEXT("c7fa64a26c29a0835f2383e63");
  TestTrue("write board-id file", WriteText(FPaths::Combine(Other, Sarp + TEXT(".layout.json")),
                                            LayoutJson(TEXT("sarpedon"), Sarp, {Prop}, {})));
  Errors.Reset();
  TestTrue(TEXT("fallback by board id: ") + FString::Join(Errors, TEXT(" | ")),
           S08EnvLayout::Resolve(Other, TEXT("sarpedon"), {Sarp}, L, Errors, bAbsent));
  TestEqual("fallback board id", L.BoardId, Sarp);
  Errors.Reset();
  TestFalse("absent map", S08EnvLayout::Resolve(Other, TEXT("marmoreal"), {Marm}, L, Errors, bAbsent));
  TestTrue("absent flagged", bAbsent);
  const FString Empty = TempDir(TEXT("ResolveEmpty"));
  Errors.Reset();
  TestFalse("empty folder", S08EnvLayout::Resolve(Empty, TEXT("marmoreal"), {Marm}, L, Errors, bAbsent));
  TestTrue("empty folder: absent", bAbsent);
  IFileManager::Get().DeleteDirectory(*FPaths::Combine(FPaths::AutomationTransientDir(), TEXT("S08EnvLayout")), false, true);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutSpawnTest,
    "Unmatched.S08.EnvLayout.Spawn fake map-image board: counts, component settings, missing-mesh / inside-map tolerance, keep / respawn / clear",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutSpawnTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  FTestWorld W(TEXT("S08EnvLayoutSpawn"));
  if (!TestNotNull("test world", W.World)) return false;
  AS08BoardActor* Actor = W.SpawnBoard();
  if (!TestNotNull("board actor", Actor)) return false;
  USceneComponent* Root = Actor->GetRootComponent();
  const FString Board = TEXT("cidEnv");
  // 3 cubes around the map (one shadowless, rotated, scaled), 2 props on a missing mesh, 1 prop on the painted map,
  // 2 lights.
  const TArray<FString> Props = {
      PropJson(TEXT("west"), CubePath, FVector(-600.0, 0.0, -3.0), TEXT(",\"yawDeg\":45,\"scale\":0.5,\"castShadow\":false")),
      PropJson(TEXT("east"), CubePath, FVector(600.0, 0.0, -3.0)),
      PropJson(TEXT("far"), TEXT("/Engine/BasicShapes/Cube.Cube"), FVector(0.0, -420.0, -3.0)),
      PropJson(TEXT("gone-1"), MissingMeshPath, FVector(-600.0, -380.0, -3.0)),
      PropJson(TEXT("gone-2"), MissingMeshPath, FVector(600.0, -380.0, -3.0)),
      PropJson(TEXT("on-map"), CubePath, FVector(100.0, 50.0, -3.0))};
  const TArray<FString> Lights = {LightJson(TEXT("lamp-w"), FVector(-600.0, 0.0, 150.0)),
                                  LightJson(TEXT("lamp-e"), FVector(600.0, 0.0, 150.0))};
  FS08EnvLayout L;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("layout parses: ") + FString::Join(Errors, TEXT(" | ")),
                L.ParseJson(LayoutJson(TEXT("envtest"), Board, Props, Lights,
                                       TEXT(",\"tray\":{\"halfX\":640,\"halfY\":470,\"offsetY\":-20}")),
                            Errors))) {
    return false;
  }
  // 1) Spawn directly
  TArray<TObjectPtr<UStaticMeshComponent>> PropComps;
  TArray<TObjectPtr<UPointLightComponent>> LightComps;
  const FBox2D TrayTop = S08EnvLayout::TrayTopRect(&L, FrameHalf, FVector2D::ZeroVector);
  const FS08EnvSpawnStats S = S08EnvLayout::Spawn(L, *Actor, Root, MapHalf, TrayTop, PropComps, LightComps);
  AddInfo(FString::Printf(TEXT("spawn: props %d lights %d missing %d skippedMissing %d insideMap %d intrusions %d outsideTray %d outsideKit %d shadowCasters %d"),
                          S.Props, S.Lights, S.MissingMeshes, S.SkippedMissing, S.SkippedInsideMap, S.Intrusions,
                          S.OutsideTray, S.OutsideKit, S.ShadowCasters));
  TestEqual("layout props", S.LayoutProps, 6);
  TestEqual("3 prop components", S.Props, 3);
  TestEqual("3 in the array", PropComps.Num(), 3);
  TestEqual("1 missing mesh path", S.MissingMeshes, 1);
  TestTrue("missing path reported", S.MissingPaths.Num() == 1 && S.MissingPaths[0] == MissingMeshPath);
  TestEqual("2 props skipped for the missing mesh", S.SkippedMissing, 2);
  TestEqual("1 prop skipped on the painted map", S.SkippedInsideMap, 1);
  TestEqual("2 lights", S.Lights, 2);
  TestEqual("2 light components", LightComps.Num(), 2);
  TestEqual("shadow casters", S.ShadowCasters, 2);
  TestEqual("the 3 engine cubes are outside /Game/EnvKit (the missing kit mesh is inside, on-map never counted)",
            S.OutsideKit, 3);
  TestEqual("no intrusion (100 uu cubes beside the map)", S.Intrusions, 0);
  TestEqual("all on the tray", S.OutsideTray, 0);
  for (UStaticMeshComponent* C : PropComps) {
    if (!TestNotNull("prop component", C)) continue;
    TestTrue(C->GetName() + TEXT(": registered, under the board root"), C->IsRegistered() && C->GetAttachParent() == Root);
    TestTrue(C->GetName() + TEXT(": owned by the board actor"), C->GetOwner() == Actor);
    TestTrue(C->GetName() + TEXT(": NoCollision"), C->GetCollisionEnabled() == ECollisionEnabled::NoCollision);
    TestFalse(C->GetName() + TEXT(": no navigation"), C->CanEverAffectNavigation());
    TestTrue(C->GetName() + TEXT(": cube mesh"), C->GetStaticMesh() && C->GetStaticMesh()->GetName() == TEXT("Cube"));
    TestFalse(C->GetName() + TEXT(": no overlap events"), C->GetGenerateOverlapEvents());
  }
  if (PropComps.Num() == 3) {
    const UStaticMeshComponent* West = PropComps[0];
    TestTrue("west: location / yaw / scale", West->GetRelativeLocation().Equals(FVector(-600.0, 0.0, -3.0), 1e-3) &&
                                                 FMath::IsNearlyEqual(West->GetRelativeRotation().Yaw, 45.0, 1e-3) &&
                                                 West->GetRelativeScale3D().Equals(FVector(0.5), 1e-6));
    TestFalse("west: castShadow false", static_cast<bool>(West->CastShadow));
    TestTrue("east: castShadow true (default)", static_cast<bool>(PropComps[1]->CastShadow));
    TestTrue("far: 'Pkg.Obj' path loads the same cube", PropComps[2]->GetStaticMesh() == PropComps[1]->GetStaticMesh());
  }
  if (LightComps.Num() == 2) {
    const UPointLightComponent* Lamp = LightComps[0];
    TestTrue("light: registered under the root", Lamp->IsRegistered() && Lamp->GetAttachParent() == Root);
    TestTrue("light: Movable", Lamp->Mobility == EComponentMobility::Movable);
    TestTrue("light: candelas", Lamp->IntensityUnits == ELightUnits::Candelas);
    TestTrue("light: intensity 40 cd", FMath::IsNearlyEqual(Lamp->Intensity, 40.0f));
    TestTrue("light: attenuation radius 450", FMath::IsNearlyEqual(Lamp->AttenuationRadius, 450.0f));
    TestFalse("light: no shadows", static_cast<bool>(Lamp->CastShadows));
    TestTrue(FString::Printf(TEXT("light: colour bytes %s == #FFB870"), *Lamp->LightColor.ToHex()),
             Lamp->LightColor == FColor(0xFF, 0xB8, 0x70, 0xFF));
    TestTrue("light: location", Lamp->GetRelativeLocation().Equals(FVector(-600.0, 0.0, 150.0), 1e-3));
  }
  // intrusion: a big cube next to the map reaches over it
  {
    FS08EnvLayout Big;
    Errors.Reset();
    TestTrue("big layout", Big.ParseJson(LayoutJson(TEXT("envtest"), Board, {PropJson(TEXT("big"), CubePath, FVector(-470.0, 0.0, -3.0), TEXT(",\"scale\":1.5"))}, {}), Errors));
    TArray<TObjectPtr<UStaticMeshComponent>> BigComps;
    TArray<TObjectPtr<UPointLightComponent>> NoLights;
    const FS08EnvSpawnStats BigS = S08EnvLayout::Spawn(Big, *Actor, Root, MapHalf, FBox2D(ForceInit), BigComps, NoLights);
    TestEqual("a 150 uu cube at x -470 overlaps the painted map (traced, not refused)", BigS.Intrusions, 1);
    TestEqual("it still spawns", BigS.Props, 1);
    S08EnvLayout::Clear(BigComps, NoLights);
  }
  // Clear
  TArray<UActorComponent*> Before;
  for (UStaticMeshComponent* C : PropComps) Before.Add(C);
  for (UPointLightComponent* C : LightComps) Before.Add(C);
  TestEqual("Clear destroys 5 components", S08EnvLayout::Clear(PropComps, LightComps), 5);
  TestTrue("arrays empty", PropComps.Num() == 0 && LightComps.Num() == 0);
  for (UActorComponent* C : Before) TestTrue("component destroyed", Destroyed(C));

  // 2) Update: the board-actor hook on a fake map-image board (layout read from a folder)
  const FString Dir = TempDir(TEXT("Spawn"));
  const FString File = S08EnvLayout::FileFor(Dir, TEXT("envtest"));
  TestTrue("write layout", WriteText(File, LayoutJson(TEXT("envtest"), Board, Props, Lights)));
  FS08EnvLayoutRequest Req;
  Req.bEnabled = true;
  Req.bMapImageActive = true;
  Req.ProfileId = TEXT("envmap");
  Req.MapKey = TEXT("envtest");
  Req.RoomBoardId = Board;
  Req.ProfileBoardIds = {Board};
  Req.MapHalf = MapHalf;
  Req.FrameHalf = FrameHalf;
  Req.ProfilePointLights = 4;
  Req.Dir = Dir;
  FS08EnvLayoutRuntime Rt;
  TArray<TObjectPtr<UStaticMeshComponent>> EnvProps;
  TArray<TObjectPtr<UPointLightComponent>> EnvLights;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("update: applied, valid, ok", Rt.bApplied && Rt.bLayoutValid && Rt.Status == TEXT("ok"));
  TestTrue("update: 3 props + 2 lights", EnvProps.Num() == 3 && EnvLights.Num() == 2);
  TestTrue("update: stats kept", Rt.Stats.Props == 3 && Rt.Stats.MissingMeshes == 1 && Rt.Stats.SkippedInsideMap == 1);
  TestEqual("summary line", S08EnvLayout::SummaryLine(TEXT("envtest"), Rt.Stats, FString()),
            FString(TEXT("ARTPREVIEW envlayout map=envtest props=3 lights=2 missingMeshes=1")));
  UStaticMeshComponent* First = EnvProps.Num() ? EnvProps[0].Get() : nullptr;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("same layout again: the same components (no respawn)", EnvProps.Num() == 3 && EnvProps[0].Get() == First &&
                                                                       !Destroyed(First));
  // changed bytes -> respawn
  TestTrue("rewrite layout (1 prop)", WriteText(File, LayoutJson(TEXT("envtest"), Board, {Props[1]}, {})));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("changed layout: respawned 1 prop, 0 lights", EnvProps.Num() == 1 && EnvLights.Num() == 0);
  TestTrue("old components destroyed", Destroyed(First));
  // board change: not a map-image board any more -> everything goes
  UStaticMeshComponent* Last = EnvProps.Num() ? EnvProps[0].Get() : nullptr;
  Req.bMapImageActive = false;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("grid / grey board: cleared", EnvProps.Num() == 0 && EnvLights.Num() == 0 && Destroyed(Last));
  TestFalse("runtime reset", Rt.bApplied || Rt.bLayoutValid);
  // gate off
  Req.bMapImageActive = true;
  Req.bEnabled = false;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("gate off: nothing", EnvProps.Num() == 0 && EnvLights.Num() == 0 && !Rt.bApplied);
  // absent / invalid layouts spawn nothing
  Req.bEnabled = true;
  Req.MapKey = TEXT("nosuchmap");
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("absent: applied, not valid, nothing spawned",
           Rt.bApplied && !Rt.bLayoutValid && Rt.Status == TEXT("absent") && EnvProps.Num() == 0);
  TestTrue("write invalid", WriteText(S08EnvLayout::FileFor(Dir, TEXT("broken")),
                                      LayoutJson(TEXT("broken"), Board, {PropJson(TEXT("p"), CubePath, FVector(-600, 0, 0), TEXT(",\"scale\":-1"))}, {})));
  Req.MapKey = TEXT("broken");
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("invalid: nothing spawned", Rt.Status == TEXT("invalid") && EnvProps.Num() == 0 && EnvLights.Num() == 0);
  // a wrong board id is refused (the layout of another board)
  Req.MapKey = TEXT("envtest");
  Req.RoomBoardId = TEXT("cidOther");
  Req.ProfileBoardIds = {TEXT("cidOther")};
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("other board id: nothing spawned", Rt.Status == TEXT("invalid") && EnvProps.Num() == 0);
  Actor->Destroy();
  IFileManager::Get().DeleteDirectory(*FPaths::Combine(FPaths::AutomationTransientDir(), TEXT("S08EnvLayout")), false, true);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutActorTest,
    "Unmatched.S08.EnvLayout.Actor board actor: no environment without the flags, on grid boards or a refused map profile",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutActorTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  FS08BoardModel Topo;
  if (!TestTrue("synthetic topology board", EnvTopologyBoard(Topo))) return false;
  FTestWorld W(TEXT("S08EnvLayoutActor"));
  if (!TestNotNull("test world", W.World)) return false;
  auto NoEnv = [this](const AS08BoardActor* A, const TCHAR* What) {
    TestTrue(FString::Printf(TEXT("%s: no env components"), What), A->GetEnvProps().Num() == 0 && A->GetEnvLights().Num() == 0);
    TestEqual(FString::Printf(TEXT("%s: no env fx (P5c)"), What), A->GetEnvLayoutRuntime().Fx.Num(), 0);
    TestFalse(FString::Printf(TEXT("%s: env never applied"), What), A->GetEnvLayoutRuntime().bApplied);
  };
  // 1) no -ArtPreviewDiorama: the gate stays shut; grid and topology boards alike
  {
    FGateScope Gate(false, false);
    AS08BoardActor* A = W.SpawnBoard();
    if (TestNotNull("actor (no flag)", A)) {
      TestFalse("no flag: EnsureEnvLayout false", A->EnsureEnvLayout(true));
      TestTrue("rebuild grid", A->Rebuild(EnvGridBoard(5, 6)));
      NoEnv(A, TEXT("no flag, grid"));
      TestTrue("rebuild topology", A->Rebuild(Topo));
      NoEnv(A, TEXT("no flag, topology"));
      A->Destroy();
    }
  }
  // 2) -ArtPreviewNoEnv opts out while the diorama stays
  {
    FGateScope Gate(true, true);
    AS08BoardActor* A = W.SpawnBoard();
    if (TestNotNull("actor (opt-out)", A)) {
      TestFalse("-ArtPreviewNoEnv: EnsureEnvLayout false", A->EnsureEnvLayout(true));
      TestTrue("-ArtPreviewNoEnv leaves the diorama gate on", S08Diorama::Enabled(true));
      A->Destroy();
    }
  }
  // 3) flags on: a grid board and a refused map-image profile get nothing
  {
    FGateScope Gate(true, false);
    AS08BoardActor* A = W.SpawnBoard();
    if (TestNotNull("actor (flags)", A)) {
      TestFalse("flags without -ArtPreview: false", A->EnsureEnvLayout(false));
      TestTrue("flags with -ArtPreview: armed", A->EnsureEnvLayout(true));
      TestTrue("rebuild grid 5x6", A->Rebuild(EnvGridBoard(5, 6)));
      NoEnv(A, TEXT("flags, grid 5x6 (no art data)"));
      FS08BoardArtData Data;
      TArray<FString> Errors;
      if (TestTrue(TEXT("map doc parses: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(MapDocJson, Errors))) {
        A->SetArtDataForTest(Data);
        A->SetRoomBoardId(TEXT("cidEnv"));
        TestTrue("rebuild topology (map assets missing)", A->Rebuild(Topo));
        TestFalse("map-image refused", A->IsMapImageActive());
        NoEnv(A, TEXT("flags, refused map-image profile"));
        A->SetRoomBoardId(FString());
        TestTrue("rebuild grid 7x5 with art data", A->Rebuild(EnvGridBoard(7, 5)));
        NoEnv(A, TEXT("flags, grid 7x5"));
      }
      A->Destroy();
    }
  }
  // 4) the shipped Marmoreal board once the map import, the kit import and the layout exist
  {
    FGateScope Gate(true, false);
    FS08BoardArtData Shipped;
    TArray<FString> Errors;
    const FS08BoardArtProfile* Marm = nullptr;
    if (Shipped.LoadFile(FS08BoardArtData::DefaultPath(), Errors)) {
      Marm = Shipped.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("marmoreal-original"); });
    }
    const FString LayoutFile = S08EnvLayout::FileFor(S08EnvLayout::DefaultDir(), TEXT("marmoreal"));
    FS08BoardModel Board;
    FString BoardId;
    {
      // the committed topology fixture -> boardState rows (the fields the actor needs: layout / links / start / zones)
      FString Text;
      TSharedPtr<FJsonObject> Root;
      FString Problem;
      const FString Fixture = FPaths::ConvertRelativePathToFull(
          FPaths::Combine(FPaths::ProjectDir(), TEXT("../../backend/prisma/fixtures/boards/marmoreal.topology.json")));
      if (FFileHelper::LoadFileToString(Text, *Fixture) && FS08Contracts::TryParseJsonObject(Text, Root, Problem) &&
          Root.IsValid()) {
        BoardId = Root->GetStringField(TEXT("boardId"));
        const TSharedPtr<FJsonObject> Lattice = Root->GetObjectField(TEXT("lattice"));
        const int32 Wd = static_cast<int32>(Lattice->GetNumberField(TEXT("width")));
        const int32 Ht = static_cast<int32>(Lattice->GetNumberField(TEXT("height")));
        TArray<TArray<TSharedPtr<FJsonValue>>> Rows;
        Rows.SetNum(Ht);
        for (TArray<TSharedPtr<FJsonValue>>& Row : Rows) Row.SetNum(Wd);
        bool bCellsOk = true;
        for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("cells"))) {
          const TSharedPtr<FJsonObject> C = V->AsObject();
          const int32 X = static_cast<int32>(C->GetNumberField(TEXT("x")));
          const int32 Y = static_cast<int32>(C->GetNumberField(TEXT("y")));
          if (X < 0 || Y < 0 || X >= Wd || Y >= Ht) {
            bCellsOk = false;
            break;
          }
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
        if (bCellsOk) {
          TArray<TSharedPtr<FJsonValue>> RowValues;
          for (const TArray<TSharedPtr<FJsonValue>>& Row : Rows) RowValues.Add(MakeShared<FJsonValueArray>(Row));
          TSharedRef<FJsonObject> State = MakeShared<FJsonObject>();
          State->SetNumberField(TEXT("width"), Wd);
          State->SetNumberField(TEXT("height"), Ht);
          State->SetArrayField(TEXT("cells"), RowValues);
          State->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
          Board.Decode(MakeShared<FJsonValueObject>(State));
        }
      }
    }
    FS08EnvLayout ShippedLayout;
    TArray<FString> LayoutErrors;
    const bool bLayout = FPaths::FileExists(LayoutFile) && ShippedLayout.LoadFile(LayoutFile, LayoutErrors);
    int32 KitMeshes = 0;
    if (bLayout) {
      for (const FString& Mesh : ShippedLayout.UniqueMeshPaths()) {
        int32 Dot = INDEX_NONE;
        const FString Pkg = Mesh.FindChar(TEXT('.'), Dot) ? Mesh.Left(Dot) : Mesh;
        KitMeshes += FPackageName::DoesPackageExist(Pkg) ? 1 : 0;
      }
    }
    if (!Marm || !Board.bHasTopology) {
      AddWarning(TEXT("marmoreal-original profile or topology fixture missing: the shipped map-image path was NOT exercised"));
    } else if (!FPackageName::DoesPackageExist(Marm->Map.MaterialInstancePath)) {
      AddWarning(FString::Printf(TEXT("map assets not imported (%s): run tools/art/map_surface/ue_import_map_surface.py; the "
                                      "shipped environment path was NOT exercised"),
                                 *Marm->Map.MaterialInstancePath));
    } else if (!bLayout) {
      AddWarning(FString::Printf(TEXT("no valid shipped layout %s (%s): the shipped environment path was NOT exercised"),
                                 *LayoutFile, *FString::Join(LayoutErrors, TEXT(" | "))));
    } else {
      AS08BoardActor* A = W.SpawnBoard();
      if (TestNotNull("actor (shipped)", A)) {
        TestTrue("armed", A->EnsureEnvLayout(true));
        A->EnsureDioramaTray(true);
        A->SetArtDataForTest(Shipped);
        A->SetRoomBoardId(BoardId);
        TestTrue("rebuild Marmoreal", A->Rebuild(Board));
        TestTrue("map-image active", A->IsMapImageActive());
        const FS08EnvLayoutRuntime& Rt = A->GetEnvLayoutRuntime();
        AddInfo(FString::Printf(TEXT("shipped Marmoreal: props %d/%d lights %d missing meshes %d (kit meshes present %d) intrusions %d outsideTray %d"),
                                Rt.Stats.Props, Rt.Stats.LayoutProps, Rt.Stats.Lights, Rt.Stats.MissingMeshes, KitMeshes,
                                Rt.Stats.Intrusions, Rt.Stats.OutsideTray));
        TestTrue("layout applied and valid", Rt.bApplied && Rt.bLayoutValid);
        TestEqual("lights = the layout's", A->GetEnvLights().Num(), ShippedLayout.Lights.Num());
        if (ShippedLayout.Ground.bSet) {
          // ENV-U10 themed ground (S08EnvGround.h): 4 strips once tools/art/env_kit/ue_import_env_ground.py ran.
          int32 GroundLive = 0;
          for (const TWeakObjectPtr<UStaticMeshComponent>& G : Rt.Ground) GroundLive += G.IsValid() ? 1 : 0;
          AddInfo(FString::Printf(TEXT("shipped Marmoreal ground: status %s strips %d area %.0f uu2"),
                                  *Rt.GroundStats.Status, GroundLive, Rt.GroundStats.AreaUU2));
          int32 GroundDot = INDEX_NONE;
          const FString& GroundMat = ShippedLayout.Ground.Material;
          const FString GroundPkg = GroundMat.FindChar(TEXT('.'), GroundDot) ? GroundMat.Left(GroundDot) : GroundMat;
          if (FPackageName::DoesPackageExist(GroundPkg)) {
            TestTrue("ground: 4 strips", Rt.GroundStats.Status == TEXT("ok") && GroundLive == 4);
          } else {
            AddWarning(FString::Printf(TEXT("%s not imported (tools/art/env_kit/ue_import_env_ground.py): no ground strips"),
                                       *GroundPkg));
          }
        }
        if (KitMeshes == 0) {
          AddWarning(TEXT("env kit not imported (tools/art/env_kit/ue_import_env_kit.py): every prop skipped as missing"));
        } else {
          TestTrue("props spawned", A->GetEnvProps().Num() > 0);
        }
        if (const UStaticMeshComponent* Tray = A->GetDioramaTray()) {
          FVector2D Half, Offset;
          FString Source, Reason;
          if (S08EnvLayout::TrayFit(ShippedLayout, Marm->Map.FrameHalfUU(), Half, Offset, Source, Reason)) {
            TestTrue("tray moved to the layout centre", FMath::IsNearlyEqual(Tray->GetRelativeLocation().Y, Offset.Y, 0.01));
          }
        }
        TestTrue("rebuild grid 5x6", A->Rebuild(EnvGridBoard(5, 6)));
        TestTrue("board change clears the environment", A->GetEnvProps().Num() == 0 && A->GetEnvLights().Num() == 0 &&
                                                            A->GetEnvLayoutRuntime().Ground.Num() == 0);
        TestEqual("board change clears the fx (grid board: none)", A->GetEnvLayoutRuntime().Fx.Num(), 0);
        A->Destroy();
      }
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutShippedTest,
    "Unmatched.S08.EnvLayout.Shipped Config/ArtBoards/EnvLayouts layouts match the map-image profiles and the kit contract",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutShippedTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped board profiles", Data.LoadFile(FS08BoardArtData::DefaultPath(), Errors))) return false;
  int32 Checked = 0;
  for (const FS08BoardArtProfile& B : Data.Boards) {
    if (B.Surface != ES08BoardSurface::MapImage) continue;
    const FString Key = S08EnvLayout::MapKeyOf(B.Map.Name);
    const FString File = S08EnvLayout::FileFor(S08EnvLayout::DefaultDir(), Key);
    if (!FPaths::FileExists(File)) {
      AddWarning(FString::Printf(TEXT("%s: no environment layout %s yet"), *B.Id, *File));
      continue;
    }
    ++Checked;
    FS08EnvLayout L;
    Errors.Reset();
    if (!TestTrue(FString::Printf(TEXT("%s: layout valid (%s)"), *Key, *FString::Join(Errors, TEXT(" | "))),
                  L.LoadFile(File, Errors))) {
      continue;
    }
    TestEqual(Key + TEXT(": map key = file name"), L.Map, Key);
    TestTrue(Key + TEXT(": boardId = the profile's"), B.MatchBoardIds.Contains(L.BoardId));
    const FVector2D Half = B.Map.HalfUU();
    const FVector2D Frame = B.Map.FrameHalfUU();
    const TArray<FString>* Names = KitNames().Find(B.Map.Name);
    for (const FS08EnvProp& P : L.Props) {
      TestFalse(FString::Printf(TEXT("%s/%s: pivot off the painted map %s"), *Key, *P.Id, *P.Loc.ToString()),
                S08EnvLayout::PivotInsideMap(P.Loc, Half));
      FString Leaf = FPackageName::GetShortName(P.Mesh);
      int32 Dot = INDEX_NONE;
      if (Leaf.FindChar(TEXT('.'), Dot)) Leaf = Leaf.Left(Dot);
      const FString Folder = FString(S08EnvLayoutSpec::KitRoot) + B.Map.Name + TEXT("/");
      const bool bKit = P.Mesh.StartsWith(Folder) && Leaf.StartsWith(TEXT("SM_Env_")) && Names &&
                        Names->Contains(Leaf.RightChop(7));
      // P5c: the AI-allowed Fab duplicates (tools/art/env_kit/ue_import_fab_picks.py) live in /Game/EnvKit/Fab/<Map>/
      const FString FabFolder = FString(S08EnvLayoutSpec::KitRoot) + TEXT("Fab/") + B.Map.Name + TEXT("/");
      const bool bFab = P.Mesh.StartsWith(FabFolder);
      TestTrue(FString::Printf(TEXT("%s/%s: mesh %s is a %sSM_Env_<kit name> of this map or a %s duplicate"), *Key, *P.Id,
                               *P.Mesh, *Folder, *FabFolder),
               bKit || bFab);
    }
    // P5c fx: derived systems under /Game/EnvKit/FX/, emitters beside the painted map, anchors on props of this layout
    for (const FS08EnvFx& F : L.Fx) {
      TestTrue(FString::Printf(TEXT("%s/%s: fx system %s under /Game/EnvKit/FX/"), *Key, *F.Id, *F.System),
               F.System.StartsWith(TEXT("/Game/EnvKit/FX/")));
      const FTransform T = F.Transform(F.Anchor.IsEmpty() ? nullptr : L.FindProp(F.Anchor));
      TestFalse(FString::Printf(TEXT("%s/%s: fx pivot %s off the painted map"), *Key, *F.Id, *T.GetTranslation().ToString()),
                S08EnvLayout::PivotInsideMap(T.GetTranslation(), Half));
    }
    // P5c variants: every overlay of this map in the folder merges into a valid layout
    TArray<FString> OverlayNames;
    IFileManager::Get().FindFiles(OverlayNames, *FPaths::Combine(S08EnvLayout::DefaultDir(), Key + TEXT(".*.layout.json")),
                                  true, false);
    for (const FString& Name : OverlayNames) {
      const FString Variant = FPaths::GetBaseFilename(Name).LeftChop(7).RightChop(Key.Len() + 1);  // <map>.<v>.layout
      FS08EnvLayout Merged = L;
      const FS08EnvVariantResult R = S08EnvLayout::ApplyVariant(S08EnvLayout::DefaultDir(), Key, Variant, Merged);
      TestEqual(FString::Printf(TEXT("%s: overlay %s merges (%s)"), *Key, *Name, *FString::Join(R.Errors, TEXT(" | "))),
                R.Status, FString(TEXT("ok")));
      AddInfo(R.TraceLine(Key));
    }
    TestTrue(Key + TEXT(": <= 6 point lights"), L.Lights.Num() <= S08EnvLayoutSpec::MaxPointLights);
    if (L.Tray.bSet || L.Apron.bSet) {
      FVector2D FitHalf, Offset;
      FString Source, Reason;
      TestTrue(FString::Printf(TEXT("%s: tray covers the frame (%s)"), *Key, *Reason),
               S08EnvLayout::TrayFit(L, Frame, FitHalf, Offset, Source, Reason));
    }
    if (L.Tray.bSet && L.Apron.bSet) {
      const FS08EnvTray Implied = L.Apron.ImpliedTray(Frame);
      const float Tol = S08EnvLayoutSpec::TrayApronToleranceUU;
      TestTrue(FString::Printf(TEXT("%s: tray %.1fx%.1f/%.1f == apron-implied %.1fx%.1f/%.1f"), *Key, L.Tray.HalfX,
                               L.Tray.HalfY, L.Tray.OffsetY, Implied.HalfX, Implied.HalfY, Implied.OffsetY),
               FMath::IsNearlyEqual(Implied.HalfX, L.Tray.HalfX, Tol) && FMath::IsNearlyEqual(Implied.HalfY, L.Tray.HalfY, Tol) &&
                   FMath::IsNearlyEqual(Implied.OffsetY, L.Tray.OffsetY, Tol));
    }
    const FS08LightProfile* Light = Data.LightFor(B);
    const int32 Combined = (Light ? Light->Points.Num() : 0) + L.Lights.Num();
    AddInfo(FString::Printf(TEXT("%s: %d props, %d lights; art profile points %d -> combined %d (budget %d)%s"), *Key,
                            L.Props.Num(), L.Lights.Num(), Light ? Light->Points.Num() : 0, Combined,
                            S08EnvLayoutSpec::CombinedPointBudget,
                            Combined > S08EnvLayoutSpec::CombinedPointBudget ? TEXT(" OVER BUDGET (open decision)") : TEXT("")));
  }
  AddInfo(FString::Printf(TEXT("shipped layouts checked: %d"), Checked));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutKitAssetsTest,
    "Unmatched.S08.EnvLayout.KitAssets imported /Game/EnvKit meshes, MIs and textures match the import contract",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutKitAssetsTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  int32 Checked = 0;
  for (const TPair<FString, TArray<FString>>& Map : KitNames()) {
    for (const FString& Name : Map.Value) {
      const FString Folder = FString(S08EnvLayoutSpec::KitRoot) + Map.Key + TEXT("/");
      const FString MeshPath = Folder + TEXT("SM_Env_") + Name;
      if (!FPackageName::DoesPackageExist(MeshPath)) {
        AddWarning(FString::Printf(TEXT("%s not imported (tools/art/env_kit/ue_import_env_kit.py)"), *MeshPath));
        continue;
      }
      ++Checked;
      UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *MeshPath);
      const FString Set = KitMaterialSetOf(Name);
      UMaterialInstance* Mi = LoadObject<UMaterialInstance>(nullptr, *(Folder + TEXT("MI_Env_") + Set));
      UTexture* Bc = LoadObject<UTexture>(nullptr, *(Folder + TEXT("T_Env_") + Set + TEXT("_BC")));
      UTexture* N = LoadObject<UTexture>(nullptr, *(Folder + TEXT("T_Env_") + Set + TEXT("_N")));
      UTexture* Orm = LoadObject<UTexture>(nullptr, *(Folder + TEXT("T_Env_") + Set + TEXT("_ORM")));
      if (!TestTrue(Name + TEXT(": mesh, MI and three textures load"), Mesh && Mi && Bc && N && Orm)) continue;
#if WITH_EDITORONLY_DATA
      TestFalse(Name + TEXT(": Nanite off"), Mesh->IsNaniteEnabled());
#endif
      const UBodySetup* Body = Mesh->GetBodySetup();
      TestTrue(Name + TEXT(": no simple collision"), !Body || Body->AggGeom.GetElementCount() == 0);
      const TArray<FStaticMaterial>& Slots = Mesh->GetStaticMaterials();
      bool bSlots = Slots.Num() > 0;
      for (const FStaticMaterial& Slot : Slots) {
        bSlots = bSlots && Slot.MaterialInterface.Get() == static_cast<UMaterialInterface*>(Mi);
      }
      TestTrue(Name + TEXT(": every slot = MI_Env_") + Set, bSlots);
      // P4 look (env-prop-look.json): these MIs are children of the kit master M_EnvProp (HSV window recolour +
      // emissive window); the rest stay on M_UM_Figure. P5: every new prop and the back wall have a look too.
      const bool bP5 = Name == TEXT("Balustrade") || Name == TEXT("HedgeBed") || Set == TEXT("BackWall") ||
                       Name == TEXT("Barrel") || Name == TEXT("CrateStack") || Name == TEXT("LanternPost") ||
                       Name == TEXT("Banner") || Name == TEXT("RockOutcrop");
      const bool bLook = bP5 || Name == TEXT("Cherry") || Name == TEXT("Cypress") || Name == TEXT("Tree") ||
                         Name == TEXT("LanternPlinth") || Name == TEXT("Campfire") || Name == TEXT("Portal");
      const FString WantParent = bLook ? TEXT("/Game/EnvKit/Shared/M_EnvProp.M_EnvProp")
                                       : TEXT("/Game/UM/Materials/M_UM_Figure.M_UM_Figure");
      TestTrue(Name + TEXT(": MI parent ") + WantParent, Mi->Parent && Mi->Parent->GetPathName() == WantParent);
      if (Name == TEXT("LanternPlinth") || Name == TEXT("Campfire") || Name == TEXT("Portal") ||
          Name == TEXT("LanternPost") || Set == TEXT("BackWall")) {
        float Emissive = 0.f;
        TestTrue(Name + TEXT(": EmissiveIntensity > 0 (env-prop-look.json)"),
                 Mi->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("EmissiveIntensity")), Emissive) &&
                     Emissive > 0.f);
      }
      UTexture* Bound = nullptr;
      TestTrue(Name + TEXT(": BaseColorTexture bound"),
               Mi->GetTextureParameterValue(FHashedMaterialParameterInfo(TEXT("BaseColorTexture")), Bound) && Bound == Bc);
      TestTrue(Name + TEXT(": NormalTexture bound"),
               Mi->GetTextureParameterValue(FHashedMaterialParameterInfo(TEXT("NormalTexture")), Bound) && Bound == N);
      TestTrue(Name + TEXT(": ORMTexture bound"),
               Mi->GetTextureParameterValue(FHashedMaterialParameterInfo(TEXT("ORMTexture")), Bound) && Bound == Orm);
      // P1b review: meshes with inward-wound faces get a TwoSided MI override (ue_import_env_kit.py TWO_SIDED).
      const bool bWantTwoSided = Name == TEXT("Cypress") || Name == TEXT("Rope") || Name == TEXT("Tree") ||
                                 Name == TEXT("Cherry") || Name == TEXT("Urn") || Name == TEXT("Banner") ||
                                 Name == TEXT("Balustrade");
      const bool bTwoSided = Mi->BasePropertyOverrides.bOverride_TwoSided && Mi->BasePropertyOverrides.TwoSided;
      TestTrue(FString::Printf(TEXT("%s: MI TwoSided override %d, expected %d (ue_import_env_kit.py TWO_SIDED)"), *Name,
                               bTwoSided ? 1 : 0, bWantTwoSided ? 1 : 0),
               bTwoSided == bWantTwoSided);
      TestTrue(Name + TEXT(": BC sRGB default"), Bc->SRGB && Bc->CompressionSettings == TC_Default);
      TestTrue(Name + TEXT(": N linear normal map"), !N->SRGB && N->CompressionSettings == TC_Normalmap);
      TestTrue(Name + TEXT(": ORM linear masks"), !Orm->SRGB && Orm->CompressionSettings == TC_Masks);
      const FBox Box = Mesh->GetBoundingBox();
      AddInfo(FString::Printf(TEXT("%s: bounds %s size %s"), *Name, *Box.ToString(), *Box.GetSize().ToString()));
      TestTrue(Name + TEXT(": pivot at the base (min Z ~ 0)"), FMath::Abs(Box.Min.Z) < 1.0);
    }
  }
  int32 Total = 0;
  for (const TPair<FString, TArray<FString>>& Map : KitNames()) Total += Map.Value.Num();
  AddInfo(FString::Printf(TEXT("env kit meshes checked: %d / %d"), Checked, Total));
  return true;
}

// ---- P5c track V: fx section + layout variants ------------------------------------------------------------------

namespace S08EnvLayoutFxTest {
const TCHAR* const TestSystemPath = TEXT("/Game/EnvKit/FX/NS_S08EnvFxTest");
const TCHAR* const MissingSystemPath = TEXT("/Game/EnvKit/FX/NS_NoSuchFxTest");

FString FxJson(const FString& Id, const FString& System, const FVector& Loc, const FString& Extra = FString()) {
  return FString::Printf(TEXT("{\"id\":\"%s\",\"system\":\"%s\",\"loc\":[%.3f,%.3f,%.3f]%s}"), *Id, *System, Loc.X, Loc.Y,
                         Loc.Z, *Extra);
}

FString WithFx(const TArray<FString>& Fx) { return TEXT(",\"fx\":[") + FString::Join(Fx, TEXT(",")) + TEXT("]"); }

FString OverlayJson(const FString& Map, const FString& Variant, const FString& Body) {
  return FString::Printf(TEXT("{\"schema\":\"unmatched.env-layout-overlay/1\",\"map\":\"%s\",\"variant\":\"%s\"%s}"), *Map,
                         *Variant, *Body);
}

/** A transient, empty Niagara system: components can be created and configured, never activated (automation). */
UNiagaraSystem* TransientSystem() {
  return NewObject<UNiagaraSystem>(GetTransientPackage(), MakeUniqueObjectName(GetTransientPackage(),
                                                                               UNiagaraSystem::StaticClass(),
                                                                               FName(TEXT("NS_S08EnvFxTest"))),
                                   RF_Transient);
}

FS08EnvFxOptions InactiveOptions(UNiagaraSystem* System) {
  FS08EnvFxOptions O;
  O.bActivate = false;
  if (System) {
    O.Preloaded.Add(TestSystemPath, System);
    O.Preloaded.Add(FString(TestSystemPath) + TEXT(".NS_S08EnvFxTest"), System);
  }
  return O;
}
}  // namespace S08EnvLayoutFxTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutFxParseTest,
    "Unmatched.S08.EnvLayout.FxParse the fx section keeps every field, anchors turn with their prop; every structural error rejects the layout",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutFxParseTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  using namespace S08EnvLayoutFxTest;
  const FString Board = TEXT("c121b47f8d6eb28daccb76d05");
  const FString Camp = PropJson(TEXT("camp"), CubePath, FVector(-560, -400, -3), TEXT(",\"yawDeg\":90"));
  const FString Fire = FxJson(TEXT("fire"), TestSystemPath, FVector(10, 0, 6),
                              TEXT(",\"anchor\":\"camp\",\"yawDeg\":15,\"scale\":0.5,\"seed\":77,\"warmupS\":1.5,"
                                   "\"user\":{\"User.SpawnRate\":8,\"Color\":[1.6,0.8,1,1],\"Sprite Size Min\":[3,3],\"On\":true}"));
  const FString Flies = FxJson(TEXT("flies"), TEXT("/Game/EnvKit/FX/NS_Env_Fireflies.NS_Env_Fireflies"),
                               FVector(-650, 100, 40), TEXT(",\"enabled\":false"));
  FS08EnvLayout L;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("layout with fx parses: ") + FString::Join(Errors, TEXT(" | ")),
                L.ParseJson(LayoutJson(TEXT("marmoreal"), Board, {Camp}, {}, WithFx({Fire, Flies})), Errors))) {
    return false;
  }
  if (!TestEqual("2 fx", L.Fx.Num(), 2)) return false;
  const FS08EnvFx& A = L.Fx[0];
  TestTrue("fire: id / system / anchor", A.Id == TEXT("fire") && A.System == TestSystemPath && A.Anchor == TEXT("camp"));
  TestTrue("fire: loc / yaw / scale", A.Loc.Equals(FVector(10, 0, 6)) && A.YawDeg == 15.0f && A.Scale == 0.5f);
  TestTrue("fire: seed 77 kept", A.bSeedSet && A.Seed == 77 && A.EffectiveSeed() == 77);
  TestEqual("fire: warmup 1.5 s = 45 fixed ticks of 1/30 s", A.WarmupTicks(), 45);
  TestTrue("fire: enabled by default", A.bEnabled);
  if (TestEqual("fire: 4 user parameters", A.User.Num(), 4)) {
    // sorted by the raw key: Color, On, Sprite Size Min, User.SpawnRate (-> SpawnRate)
    TestTrue("user[0] Color = 4 numbers", A.User[0].Name == TEXT("Color") && A.User[0].Num == 4 &&
                                              A.User[0].Value.Equals(FVector4(1.6, 0.8, 1.0, 1.0)));
    TestEqual("user[0] value string", A.User[0].ValueString(), FString(TEXT("(1.6,0.8,1,1)")));
    TestTrue("user[1] On = bool 1", A.User[1].Name == TEXT("On") && A.User[1].Num == 1 && A.User[1].Value.X == 1.0);
    TestTrue("user[2] Sprite Size Min = 2 numbers", A.User[2].Name == TEXT("Sprite Size Min") && A.User[2].Num == 2);
    TestTrue("user[3] 'User.' prefix stripped", A.User[3].Name == TEXT("SpawnRate") && A.User[3].Value.X == 8.0);
  }
  const FS08EnvFx& B = L.Fx[1];
  TestFalse("flies: disabled", B.bEnabled);
  TestFalse("flies: no explicit seed", B.bSeedSet);
  TestEqual("flies: seed = CRC of the id (stable)", B.EffectiveSeed(),
            static_cast<int32>(FCrc::StrCrc32(TEXT("flies")) & 0x7FFFFFFFu));
  TestEqual("flies: default warmup 2 s = 60 ticks", B.WarmupTicks(), 60);
  TestEqual("2 unique systems", L.UniqueFxSystemPaths().Num(), 2);
  // anchored transform: the offset turns with the prop (yaw 90: +X -> +Y), not scaled; yaws add up
  const FS08EnvProp* CampProp = L.FindProp(TEXT("camp"));
  if (TestNotNull("anchor prop", CampProp)) {
    const FTransform T = A.Transform(CampProp);
    AddInfo(FString::Printf(TEXT("anchored fire at %s yaw %.1f"), *T.GetTranslation().ToString(), T.Rotator().Yaw));
    TestTrue("anchored location = prop pivot + yawed offset", T.GetTranslation().Equals(FVector(-560, -390, 3), 1e-3));
    TestTrue("anchored yaw = 90 + 15", FMath::IsNearlyEqual(T.Rotator().Yaw, 105.0, 1e-3));
    TestTrue("fx scale", T.GetScale3D().Equals(FVector(0.5), 1e-6));
  }
  TestTrue("board-space transform", B.Transform(nullptr).GetTranslation().Equals(FVector(-650, 100, 40)));
  // a layout without "fx" has none
  Errors.Reset();
  FS08EnvLayout NoFx;
  TestTrue("layout without fx parses", NoFx.ParseJson(LayoutJson(TEXT("marmoreal"), Board, {Camp}, {}), Errors));
  TestEqual("no fx", NoFx.Fx.Num(), 0);

  // rejection table
  TArray<FString> TooMany;
  for (int32 I = 0; I <= S08EnvLayoutSpec::MaxFx; ++I) {
    TooMany.Add(FxJson(FString::Printf(TEXT("f%d"), I), TestSystemPath, FVector(-600, 0, 10)));
  }
  FString SeventeenParams = TEXT(",\"user\":{");
  for (int32 I = 0; I <= S08EnvLayoutSpec::MaxFxUserParams; ++I) {
    SeventeenParams += FString::Printf(TEXT("%s\"P%d\":1"), I ? TEXT(",") : TEXT(""), I);
  }
  SeventeenParams += TEXT("}");
  const FString Ok = FxJson(TEXT("f"), TestSystemPath, FVector(-600, 0, 10));
  struct FCase {
    const TCHAR* Name;
    FString Fx;  // the ",\"fx\":..." fragment
    const TCHAR* Expect;
  };
  auto One = [](const FString& Extra) { return WithFx({FxJson(TEXT("f"), TestSystemPath, FVector(-600, 0, 10), Extra)}); };
  const FCase Cases[] = {
      {TEXT("fx not an array"), TEXT(",\"fx\":{}"), TEXT("fx is not an array")},
      {TEXT("49 fx"), WithFx(TooMany), TEXT("fx >")},
      {TEXT("fx entry not an object"), TEXT(",\"fx\":[3]"), TEXT("is not an object")},
      {TEXT("fx id missing"), TEXT(",\"fx\":[{\"system\":\"/Game/EnvKit/FX/NS_A\",\"loc\":[-600,0,0]}]"), TEXT("id missing")},
      {TEXT("duplicate fx id"), WithFx({Ok, Ok}), TEXT("duplicate id")},
      {TEXT("system in a pack folder"),
       WithFx({FxJson(TEXT("f"), TEXT("/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_2"), FVector(-600, 0, 10))}),
       TEXT("is not under /Game/EnvKit/")},
      {TEXT("system without a root"), WithFx({FxJson(TEXT("f"), TEXT("Game/EnvKit/FX/NS_A"), FVector(-600, 0, 10))}),
       TEXT("package path")},
      {TEXT("anchor not a prop"), One(TEXT(",\"anchor\":\"nosuch\"")), TEXT("is not a prop id")},
      {TEXT("anchor empty"), One(TEXT(",\"anchor\":\"\"")), TEXT("anchor is not")},
      {TEXT("loc with 2 numbers"), TEXT(",\"fx\":[{\"id\":\"f\",\"system\":\"/Game/EnvKit/FX/NS_A\",\"loc\":[1,2]}]"), TEXT("loc")},
      {TEXT("scale 0"), One(TEXT(",\"scale\":0")), TEXT("scale")},
      {TEXT("scale 11"), One(TEXT(",\"scale\":11")), TEXT("scale")},
      {TEXT("warmupS 11"), One(TEXT(",\"warmupS\":11")), TEXT("warmupS")},
      {TEXT("warmupS negative"), One(TEXT(",\"warmupS\":-1")), TEXT("warmupS")},
      {TEXT("seed negative"), One(TEXT(",\"seed\":-1")), TEXT("seed")},
      {TEXT("seed fractional"), One(TEXT(",\"seed\":1.5")), TEXT("seed")},
      {TEXT("seed string"), One(TEXT(",\"seed\":\"7\"")), TEXT("seed")},
      {TEXT("enabled not a bool"), One(TEXT(",\"enabled\":\"yes\"")), TEXT("enabled")},
      {TEXT("user not an object"), One(TEXT(",\"user\":[1]")), TEXT("user is not an object")},
      {TEXT("user value string"), One(TEXT(",\"user\":{\"Color\":\"pink\"}")), TEXT("needs a number")},
      {TEXT("user value 5 numbers"), One(TEXT(",\"user\":{\"Color\":[1,2,3,4,5]}")), TEXT("needs a number")},
      {TEXT("17 user parameters"), One(SeventeenParams), TEXT("user parameters >")},
      {TEXT("user name with a slash"), One(TEXT(",\"user\":{\"a/b\":1}")), TEXT("invalid or duplicated")},
      {TEXT("user name twice (prefix)"), One(TEXT(",\"user\":{\"User.A\":1,\"A\":2}")), TEXT("invalid or duplicated")},
  };
  {
    FS08EnvLayout Control;
    TArray<FString> E;
    TestTrue(TEXT("control: one plain fx parses: ") + FString::Join(E, TEXT(" | ")),
             Control.ParseJson(LayoutJson(TEXT("marmoreal"), Board, {Camp}, {}, WithFx({Ok})), E));
    TArray<FString> MaxFx = TooMany;
    MaxFx.RemoveAt(MaxFx.Num() - 1);
    E.Reset();
    TestTrue(TEXT("control: exactly 48 fx parse: ") + FString::Join(E, TEXT(" | ")),
             Control.ParseJson(LayoutJson(TEXT("marmoreal"), Board, {Camp}, {}, WithFx(MaxFx)), E));
  }
  for (const FCase& C : Cases) {
    FS08EnvLayout Bad;
    TArray<FString> E;
    TestFalse(FString::Printf(TEXT("%s: rejected"), C.Name),
              Bad.ParseJson(LayoutJson(TEXT("marmoreal"), Board, {Camp}, {}, C.Fx), E));
    const FString All = FString::Join(E, TEXT(" | "));
    TestTrue(FString::Printf(TEXT("%s: error mentions '%s' (%s)"), C.Name, C.Expect, *All), All.Contains(C.Expect));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutVariantTest,
    "Unmatched.S08.EnvLayout.Variant overlays merge props / fx (remove, replace, add), invalid or missing overlays fall back to the base",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutVariantTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  using namespace S08EnvLayoutFxTest;
  const FString Board = TEXT("cidEnv");
  const TArray<FString> Props = {PropJson(TEXT("west"), CubePath, FVector(-600, 0, -3), TEXT(",\"yawDeg\":90")),
                                 PropJson(TEXT("east"), CubePath, FVector(600, 0, -3)),
                                 PropJson(TEXT("far"), CubePath, FVector(0, -420, -3))};
  const TArray<FString> Fx = {FxJson(TEXT("fx-w"), TestSystemPath, FVector(0, 0, 20), TEXT(",\"anchor\":\"west\"")),
                              FxJson(TEXT("fx-e"), TestSystemPath, FVector(0, 0, 20), TEXT(",\"anchor\":\"east\"")),
                              FxJson(TEXT("fx-free"), TestSystemPath, FVector(-650, 200, 40))};
  const FString BaseText = LayoutJson(TEXT("envtest"), Board, Props, {LightJson(TEXT("lamp"), FVector(-600, 0, 150))},
                                      WithFx(Fx));
  {
    FS08EnvLayout Base;
    TArray<FString> E;
    if (!TestTrue(TEXT("base parses: ") + FString::Join(E, TEXT(" | ")), Base.ParseJson(BaseText, E))) return false;
  }
  // 1) a full overlay
  const FString Body = FString::Printf(
      TEXT(",\"boardId\":\"cidEnv\",\"notes\":\"t\","
           "\"props\":{\"remove\":[\"east\"],\"replace\":[{\"id\":\"west\",\"mesh\":\"/Engine/BasicShapes/Sphere\",\"scale\":0.25}],"
           "\"add\":[{\"id\":\"extra\",\"mesh\":\"%s\",\"loc\":[0,-460,-3]}]},"
           "\"fx\":{\"remove\":[\"fx-e\"],\"replace\":[{\"id\":\"fx-free\",\"enabled\":false,\"user\":{\"SpawnRate\":2}}],"
           "\"add\":[{\"id\":\"fx-new\",\"system\":\"%s\",\"anchor\":\"extra\",\"loc\":[0,0,10]}]}"),
      CubePath, TestSystemPath);
  FS08EnvLayout Merged;
  FS08EnvVariantResult R;
  if (!TestTrue(TEXT("overlay merges: ") + FString::Join(R.Errors, TEXT(" | ")),
                S08EnvLayout::MergeOverlay(BaseText, OverlayJson(TEXT("envtest"), TEXT("user"), Body), TEXT("envtest"),
                                           TEXT("user"), Merged, R))) {
    return false;
  }
  TestTrue("counts: props -1 ~1 +1", R.PropsRemoved == 1 && R.PropsReplaced == 1 && R.PropsAdded == 1);
  TestTrue("counts: fx-e went with its anchor (its explicit remove is tolerated), ~1 +1",
           R.FxRemovedWithAnchor == 1 && R.FxRemoved == 0 && R.FxReplaced == 1 && R.FxAdded == 1);
  TestEqual("3 props", Merged.Props.Num(), 3);
  const FS08EnvProp* West = Merged.FindProp(TEXT("west"));
  TestTrue("west: mesh + scale replaced, loc / yaw kept",
           West && West->Mesh == TEXT("/Engine/BasicShapes/Sphere") && West->Scale == 0.25f &&
               West->Loc.Equals(FVector(-600, 0, -3)) && West->YawDeg == 90.0f);
  TestNull("east removed", Merged.FindProp(TEXT("east")));
  TestNotNull("extra added", Merged.FindProp(TEXT("extra")));
  TestEqual("lights untouched", Merged.Lights.Num(), 1);
  if (TestEqual("3 fx", Merged.Fx.Num(), 3)) {
    const FS08EnvFx* Free = Merged.Fx.FindByPredicate([](const FS08EnvFx& F) { return F.Id == TEXT("fx-free"); });
    TestTrue("fx-free: disabled with a user override, loc kept",
             Free && !Free->bEnabled && Free->User.Num() == 1 && Free->User[0].Name == TEXT("SpawnRate") &&
                 Free->Loc.Equals(FVector(-650, 200, 40)));
    TestTrue("fx-e gone", !Merged.Fx.ContainsByPredicate([](const FS08EnvFx& F) { return F.Id == TEXT("fx-e"); }));
    TestTrue("fx-new on the added prop",
             Merged.Fx.ContainsByPredicate([](const FS08EnvFx& F) { return F.Id == TEXT("fx-new") && F.Anchor == TEXT("extra"); }));
  }
  // 2) rejection table (the base stays the caller's)
  struct FCase {
    const TCHAR* Name;
    FString Overlay;
    const TCHAR* Expect;
  };
  const FCase Cases[] = {
      {TEXT("not JSON"), TEXT("nope"), TEXT("overlay: invalid JSON")},
      {TEXT("base layout schema"), BaseText, TEXT("overlay schema")},
      {TEXT("other map"), OverlayJson(TEXT("other"), TEXT("user"), FString()), TEXT("overlay map")},
      {TEXT("other variant"), OverlayJson(TEXT("envtest"), TEXT("night"), FString()), TEXT("overlay variant")},
      {TEXT("other board"), OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"boardId\":\"cidOther\"")), TEXT("overlay boardId")},
      {TEXT("lights"), OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"lights\":[]")), TEXT("cannot change 'lights'")},
      {TEXT("ground"), OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"ground\":{}")), TEXT("cannot change 'ground'")},
      {TEXT("props not an object"), OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"props\":[]")), TEXT("is not an object")},
      {TEXT("unknown operation"), OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"props\":{\"move\":[]}")),
       TEXT("unknown operation")},
      {TEXT("remove unknown id"), OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"props\":{\"remove\":[\"nosuch\"]}")),
       TEXT("is not in the base layout")},
      {TEXT("replace unknown id"),
       OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"props\":{\"replace\":[{\"id\":\"nosuch\",\"scale\":1}]}")),
       TEXT("use add")},
      {TEXT("replace a field that is not replaceable"),
       OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"props\":{\"replace\":[{\"id\":\"west\",\"colour\":1}]}")),
       TEXT("cannot be replaced")},
      {TEXT("add an existing id"),
       OverlayJson(TEXT("envtest"), TEXT("user"),
                   FString::Printf(TEXT(",\"props\":{\"add\":[{\"id\":\"far\",\"mesh\":\"%s\",\"loc\":[0,-460,-3]}]}"), CubePath)),
       TEXT("already exists")},
      {TEXT("add without an id"), OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"fx\":{\"add\":[{\"loc\":[0,0,0]}]}")),
       TEXT("with an id")},
      {TEXT("merged prop invalid"),
       OverlayJson(TEXT("envtest"), TEXT("user"), TEXT(",\"props\":{\"replace\":[{\"id\":\"west\",\"scale\":0}]}")),
       TEXT("merged layout")},
      {TEXT("fx anchored on a prop the overlay removed"),
       OverlayJson(TEXT("envtest"), TEXT("user"),
                   FString::Printf(TEXT(",\"props\":{\"remove\":[\"far\"]},\"fx\":{\"add\":[{\"id\":\"x\",\"system\":\"%s\","
                                        "\"anchor\":\"far\",\"loc\":[0,0,0]}]}"),
                                   TestSystemPath)),
       TEXT("merged layout")},
  };
  for (const FCase& C : Cases) {
    FS08EnvLayout Out;
    FS08EnvVariantResult Bad;
    TestFalse(FString::Printf(TEXT("%s: rejected"), C.Name),
              S08EnvLayout::MergeOverlay(BaseText, C.Overlay, TEXT("envtest"), TEXT("user"), Out, Bad));
    const FString All = FString::Join(Bad.Errors, TEXT(" | "));
    TestTrue(FString::Printf(TEXT("%s: error mentions '%s' (%s)"), C.Name, C.Expect, *All), All.Contains(C.Expect));
  }
  // 3) files: ApplyVariant none / invalid name / absent / ok / invalid document; overlays never resolve as a base
  TestTrue("variant names", S08EnvLayout::IsVariantName(TEXT("user")) && S08EnvLayout::IsVariantName(TEXT("night-2")) &&
                                !S08EnvLayout::IsVariantName(TEXT("User")) && !S08EnvLayout::IsVariantName(TEXT("a.b")) &&
                                !S08EnvLayout::IsVariantName(FString()));
  TestTrue("overlay file names", S08EnvLayout::IsOverlayFileName(TEXT("marmoreal.user.layout.json")) &&
                                     !S08EnvLayout::IsOverlayFileName(TEXT("marmoreal.layout.json")) &&
                                     !S08EnvLayout::IsOverlayFileName(TEXT("c7fa64a26c29a0835f2383e63.layout.json")));
  TestTrue("overlay file", S08EnvLayout::OverlayFileFor(TEXT("D:/x"), TEXT("sarpedon"), TEXT("user"))
                               .EndsWith(TEXT("/sarpedon.user.layout.json")));
  const FString Dir = TempDir(TEXT("Variant"));
  TestTrue("write base", WriteText(S08EnvLayout::FileFor(Dir, TEXT("envtest")), BaseText));
  FS08EnvLayout L;
  TArray<FString> Errors;
  bool bAbsent = false;
  if (!TestTrue("resolve base", S08EnvLayout::Resolve(Dir, TEXT("envtest"), {Board}, L, Errors, bAbsent))) return false;
  const FString BaseSha = L.SourceSha256;
  FS08EnvVariantResult NoVariant = S08EnvLayout::ApplyVariant(Dir, TEXT("envtest"), FString(), L);
  TestTrue("no variant: none, base kept", NoVariant.Status == TEXT("none") && L.Props.Num() == 3 && L.Variant.IsEmpty());
  TestEqual("none trace", NoVariant.TraceLine(TEXT("envtest")), FString(TEXT("ARTPREVIEW envlayout variant=none map=envtest")));
  FS08EnvVariantResult BadName = S08EnvLayout::ApplyVariant(Dir, TEXT("envtest"), TEXT("Bad_Name"), L);
  TestTrue("bad name: invalid, base kept", BadName.Status == TEXT("invalid") && L.Props.Num() == 3);
  FS08EnvVariantResult Absent = S08EnvLayout::ApplyVariant(Dir, TEXT("envtest"), TEXT("absentv"), L);
  TestTrue("missing overlay: absent, base kept (clean fallback)", Absent.Status == TEXT("absent") && L.Props.Num() == 3 &&
                                                                     L.Fx.Num() == 3 && L.Variant.IsEmpty());
  TestTrue(TEXT("absent trace: ") + Absent.TraceLine(TEXT("envtest")),
           Absent.TraceLine(TEXT("envtest")).Contains(TEXT("variant=absentv map=envtest status=absent")) &&
               Absent.TraceLine(TEXT("envtest")).EndsWith(TEXT("fallback=base")));
  TestTrue("write broken overlay", WriteText(S08EnvLayout::OverlayFileFor(Dir, TEXT("envtest"), TEXT("broken")),
                                             OverlayJson(TEXT("envtest"), TEXT("broken"), TEXT(",\"lights\":[]"))));
  FS08EnvVariantResult Broken = S08EnvLayout::ApplyVariant(Dir, TEXT("envtest"), TEXT("broken"), L);
  TestTrue("invalid overlay: invalid, base kept", Broken.Status == TEXT("invalid") && L.Props.Num() == 3 &&
                                                      Broken.Sha256.Len() == 64 && Broken.Errors.Num() > 0);
  TestTrue("write user overlay", WriteText(S08EnvLayout::OverlayFileFor(Dir, TEXT("envtest"), TEXT("user")),
                                           OverlayJson(TEXT("envtest"), TEXT("user"), Body)));
  FS08EnvVariantResult Ok = S08EnvLayout::ApplyVariant(Dir, TEXT("envtest"), TEXT("user"), L);
  TestTrue(TEXT("user overlay: ok ") + FString::Join(Ok.Errors, TEXT(" | ")), Ok.Status == TEXT("ok"));
  TestTrue("merged layout in place", L.Props.Num() == 3 && L.FindProp(TEXT("extra")) && !L.FindProp(TEXT("east")));
  TestTrue("variant fields", L.Variant == TEXT("user") && L.OverlaySha256.Len() == 64 && L.OverlayPath.EndsWith(TEXT("envtest.user.layout.json")));
  TestEqual("base sha256 kept", L.SourceSha256, BaseSha);
  AddInfo(Ok.TraceLine(TEXT("envtest")));
  TestTrue("ok trace", Ok.TraceLine(TEXT("envtest")).Contains(TEXT("variant=user map=envtest status=ok file=envtest.user.layout.json")) &&
                           !Ok.TraceLine(TEXT("envtest")).Contains(TEXT("fallback")));
  // an overlay-shaped file name never resolves as a base layout (fallback scan by board id)
  const FString Only = TempDir(TEXT("VariantOnlyOverlay"));
  TestTrue("write a layout under an overlay name", WriteText(FPaths::Combine(Only, TEXT("envtest.user.layout.json")), BaseText));
  Errors.Reset();
  FS08EnvLayout Nothing;
  TestFalse("overlay name is not a base", S08EnvLayout::Resolve(Only, TEXT("envtest"), {Board}, Nothing, Errors, bAbsent));
  TestTrue("-> absent", bAbsent);
  IFileManager::Get().DeleteDirectory(*FPaths::Combine(FPaths::AutomationTransientDir(), TEXT("S08EnvLayout")), false, true);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutFxSpawnTest,
    "Unmatched.S08.EnvLayout.FxSpawn fake map-image board: Niagara components, skips, -ArtPreviewNoFx, Update with a variant, board change / grid clear",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutFxSpawnTest::RunTest(const FString&) {
  using namespace S08EnvLayoutTest;
  using namespace S08EnvLayoutFxTest;
  FTestWorld W(TEXT("S08EnvLayoutFxSpawn"));
  if (!TestNotNull("test world", W.World)) return false;
  AS08BoardActor* Actor = W.SpawnBoard();
  if (!TestNotNull("board actor", Actor)) return false;
  USceneComponent* Root = Actor->GetRootComponent();
  UNiagaraSystem* System = TransientSystem();
  if (!TestNotNull("transient Niagara system", System)) return false;
  const FString Board = TEXT("cidEnv");
  const TArray<FString> Props = {PropJson(TEXT("west"), CubePath, FVector(-600, 0, -3), TEXT(",\"yawDeg\":90")),
                                 PropJson(TEXT("far"), CubePath, FVector(0, -420, -3)),
                                 PropJson(TEXT("gone"), MissingMeshPath, FVector(600, -380, -3))};
  const TArray<FString> Fx = {
      FxJson(TEXT("a"), TestSystemPath, FVector(10, 0, 20), TEXT(",\"anchor\":\"west\",\"seed\":5,\"user\":{\"SpawnRate\":3}")),
      FxJson(TEXT("b"), TestSystemPath, FVector(650, 100, 40)),
      FxJson(TEXT("c"), TestSystemPath, FVector(0, 0, 20), TEXT(",\"anchor\":\"gone\"")),
      FxJson(TEXT("d"), TestSystemPath, FVector(100, 50, 30)),
      FxJson(TEXT("e"), TestSystemPath, FVector(-650, 0, 30), TEXT(",\"enabled\":false")),
      FxJson(TEXT("f"), MissingSystemPath, FVector(-650, 50, 30)),
      FxJson(TEXT("g"), TestSystemPath, FVector(0, 400, 20))};
  FS08EnvLayout L;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("layout parses: ") + FString::Join(Errors, TEXT(" | ")),
                L.ParseJson(LayoutJson(TEXT("envtest"), Board, Props, {}, WithFx(Fx)), Errors))) {
    return false;
  }
  // 1) SpawnFx directly (after the props: anchors need spawned props)
  TArray<TObjectPtr<UStaticMeshComponent>> PropComps;
  TArray<TObjectPtr<UPointLightComponent>> LightComps;
  const FS08EnvSpawnStats PS = S08EnvLayout::Spawn(L, *Actor, Root, MapHalf, FBox2D(ForceInit), PropComps, LightComps);
  TestTrue("spawned prop ids: west + far (gone is missing)",
           PS.SpawnedPropIds.Num() == 2 && PS.SpawnedPropIds.Contains(TEXT("west")) && !PS.SpawnedPropIds.Contains(TEXT("gone")));
  TArray<TWeakObjectPtr<UNiagaraComponent>> FxComps;
  const FS08EnvFxStats S = S08EnvLayout::SpawnFx(L, *Actor, Root, MapHalf, FrameHalf, PS.SpawnedPropIds,
                                                 InactiveOptions(System), FxComps);
  AddInfo(S08EnvLayout::FxSummaryLine(TEXT("envtest"), S));
  TestEqual("layout fx", S.LayoutFx, 7);
  TestEqual("3 fx components (a, b, g)", S.Fx, 3);
  TestEqual("3 in the array", FxComps.Num(), 3);
  TestEqual("c: anchor not spawned", S.SkippedAnchor, 1);
  TestEqual("d: on the painted map", S.SkippedInsideMap, 1);
  TestEqual("e: disabled", S.SkippedDisabled, 1);
  TestTrue("f: missing system", S.SkippedMissing == 1 && S.MissingSystems == 1 && S.MissingPaths.Num() == 1 &&
                                         S.MissingPaths[0] == MissingSystemPath);
  TestEqual("g: in the near band (traced, not refused)", S.NearBand, 1);
  TestTrue("a: SpawnRate not exposed by the empty system -> counted missing", S.UserMissing == 1 && S.UserSet == 0);
  TestTrue("not activated: no particles, mode inactive", S.Particles == 0 && S.Mode == TEXT("inactive"));
  TestEqual("the empty system has no determinism: 3 non-deterministic", S.NonDeterministic, 3);
  for (const TWeakObjectPtr<UNiagaraComponent>& Weak : FxComps) {
    UNiagaraComponent* C = Weak.Get();
    if (!TestNotNull("fx component", C)) continue;
    TestTrue(C->GetName() + TEXT(": registered under the board root, owned by the actor"),
             C->IsRegistered() && C->GetAttachParent() == Root && C->GetOwner() == Actor);
    TestTrue(C->GetName() + TEXT(": the system"), C->GetAsset() == System);
    TestFalse(C->GetName() + TEXT(": not active (bActivate false)"), C->IsActive());
    TestFalse(C->GetName() + TEXT(": no shadow"), static_cast<bool>(C->CastShadow));
    TestTrue(C->GetName() + TEXT(": NoCollision"), C->GetCollisionEnabled() == ECollisionEnabled::NoCollision);
  }
  if (FxComps.Num() == 3 && FxComps[0].IsValid() && FxComps[1].IsValid()) {
    const UNiagaraComponent* A = FxComps[0].Get();
    TestTrue(FString::Printf(TEXT("a: anchored location %s"), *A->GetRelativeLocation().ToString()),
             A->GetRelativeLocation().Equals(FVector(-600, 10, 17), 1e-3));
    TestTrue("a: yaw of the anchor", FMath::IsNearlyEqual(A->GetRelativeRotation().Yaw, 90.0, 1e-3));
    TestEqual("a: explicit seed", A->GetRandomSeedOffset(), 5);
    TestEqual("b: CRC seed", FxComps[1]->GetRandomSeedOffset(), static_cast<int32>(FCrc::StrCrc32(TEXT("b")) & 0x7FFFFFFFu));
  }
  TArray<UNiagaraComponent*> Before;
  for (const TWeakObjectPtr<UNiagaraComponent>& Weak : FxComps) Before.Add(Weak.Get());
  TestEqual("ClearFx destroys 3", S08EnvLayout::ClearFx(FxComps), 3);
  for (UNiagaraComponent* C : Before) TestTrue("fx destroyed", Destroyed(C));
  // -ArtPreviewNoFx (bSpawn false): nothing
  {
    FS08EnvFxOptions Off = InactiveOptions(System);
    Off.bSpawn = false;
    TArray<TWeakObjectPtr<UNiagaraComponent>> NoFxComps;
    const FS08EnvFxStats SO = S08EnvLayout::SpawnFx(L, *Actor, Root, MapHalf, FrameHalf, PS.SpawnedPropIds, Off, NoFxComps);
    TestTrue("-ArtPreviewNoFx: no component, mode off", NoFxComps.Num() == 0 && SO.Fx == 0 && SO.Mode == TEXT("off"));
  }
  S08EnvLayout::Clear(PropComps, LightComps);
  {
    FS08EnvFxOptions Bench;
    Bench.bBench = true;
    Bench.bFreeze = true;
    TestEqual("bench options: frozen", Bench.Mode(), FString(TEXT("frozen")));
    TestEqual("default options: live", FS08EnvFxOptions().Mode(), FString(TEXT("live")));
  }

  // 2) Update: base + variant overlay, keep / respawn / fallback, board change and grid clear
  const FString Dir = TempDir(TEXT("FxUpdate"));
  const TArray<FString> UpdProps = {Props[0], Props[1]};
  const TArray<FString> UpdFx = {Fx[0], Fx[1]};
  TestTrue("write base", WriteText(S08EnvLayout::FileFor(Dir, TEXT("envtest")),
                                   LayoutJson(TEXT("envtest"), Board, UpdProps, {}, WithFx(UpdFx))));
  TestTrue("write user overlay",
           WriteText(S08EnvLayout::OverlayFileFor(Dir, TEXT("envtest"), TEXT("user")),
                     OverlayJson(TEXT("envtest"), TEXT("user"),
                                 FString::Printf(TEXT(",\"props\":{\"remove\":[\"west\"]},\"fx\":{\"add\":[%s]}"),
                                                 *FxJson(TEXT("h"), TestSystemPath, FVector(0, 0, 30), TEXT(",\"anchor\":\"far\""))))));
  TestTrue("write invalid overlay", WriteText(S08EnvLayout::OverlayFileFor(Dir, TEXT("envtest"), TEXT("bad")),
                                             OverlayJson(TEXT("envtest"), TEXT("bad"), TEXT(",\"ground\":{}"))));
  FS08EnvLayoutRequest Req;
  Req.bEnabled = true;
  Req.bMapImageActive = true;
  Req.ProfileId = TEXT("envmap");
  Req.MapKey = TEXT("envtest");
  Req.RoomBoardId = Board;
  Req.ProfileBoardIds = {Board};
  Req.MapHalf = MapHalf;
  Req.FrameHalf = FrameHalf;
  Req.Dir = Dir;
  Req.Variant = FString();
  Req.FxOptions = InactiveOptions(System);
  FS08EnvLayoutRuntime Rt;
  TArray<TObjectPtr<UStaticMeshComponent>> EnvProps;
  TArray<TObjectPtr<UPointLightComponent>> EnvLights;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("base: ok, no variant", Rt.Status == TEXT("ok") && Rt.Variant.Status == TEXT("none"));
  TestTrue("base: 2 props, 2 fx", EnvProps.Num() == 2 && Rt.Fx.Num() == 2 && Rt.FxStats.Fx == 2);
  UNiagaraComponent* FirstFx = Rt.Fx.Num() ? Rt.Fx[0].Get() : nullptr;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("same layout again: the same fx (no respawn)", Rt.Fx.Num() == 2 && Rt.Fx[0].Get() == FirstFx && !Destroyed(FirstFx));
  Req.Variant = FString(TEXT("user"));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue(TEXT("variant user: ok ") + FString::Join(Rt.Variant.Errors, TEXT(" | ")), Rt.Variant.Status == TEXT("ok"));
  TestTrue("variant user: west removed (1 prop), a dropped with it, b + h", EnvProps.Num() == 1 && Rt.Fx.Num() == 2 &&
                                                                               Rt.Variant.FxRemovedWithAnchor == 1);
  TestTrue("variant: old fx destroyed", Destroyed(FirstFx));
  TestEqual("variant: the layout says so", Rt.Layout.Variant, FString(TEXT("user")));
  Req.Variant = FString(TEXT("missing"));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("missing overlay: absent -> the base (2 props, 2 fx)",
           Rt.Variant.Status == TEXT("absent") && EnvProps.Num() == 2 && Rt.Fx.Num() == 2 && Rt.Layout.Variant.IsEmpty());
  Req.Variant = FString(TEXT("bad"));
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("invalid overlay: invalid -> the base", Rt.Variant.Status == TEXT("invalid") && Rt.Status == TEXT("ok") &&
                                                       EnvProps.Num() == 2 && Rt.Fx.Num() == 2);
  // fx options are part of the key: -ArtPreviewNoFx respawns without fx
  FS08EnvFxOptions NoFx = InactiveOptions(System);
  NoFx.bSpawn = false;
  Req.FxOptions = NoFx;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("-ArtPreviewNoFx: props stay, no fx", EnvProps.Num() == 2 && Rt.Fx.Num() == 0 && Rt.FxStats.Mode == TEXT("off"));
  Req.FxOptions = InactiveOptions(System);
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TArray<UNiagaraComponent*> Live;
  for (const TWeakObjectPtr<UNiagaraComponent>& Weak : Rt.Fx) Live.Add(Weak.Get());
  TestEqual("fx back", Live.Num(), 2);
  // board change: a grid / grey board clears everything incl. the fx
  Req.bMapImageActive = false;
  S08EnvLayout::Update(Req, *Actor, Root, Rt, EnvProps, EnvLights);
  TestTrue("board change: nothing left", EnvProps.Num() == 0 && Rt.Fx.Num() == 0 && !Rt.bApplied);
  for (UNiagaraComponent* C : Live) TestTrue("fx destroyed on the board change", Destroyed(C));
  // grid regression: a fresh runtime on a non-map-image board never spawns, never applies
  FS08EnvLayoutRuntime GridRt;
  TArray<TObjectPtr<UStaticMeshComponent>> GridProps;
  TArray<TObjectPtr<UPointLightComponent>> GridLights;
  S08EnvLayout::Update(Req, *Actor, Root, GridRt, GridProps, GridLights);
  TestTrue("grid board: no env, no fx, not applied", GridProps.Num() == 0 && GridLights.Num() == 0 && GridRt.Fx.Num() == 0 &&
                                                       !GridRt.bApplied);
  Actor->Destroy();
  IFileManager::Get().DeleteDirectory(*FPaths::Combine(FPaths::AutomationTransientDir(), TEXT("S08EnvLayout")), false, true);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08EnvLayoutFxAssetsTest,
    "Unmatched.S08.EnvLayout.FxAssets derived /Game/EnvKit/FX systems of the shipped layouts: CPU, deterministic, no light renderer",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08EnvLayoutFxAssetsTest::RunTest(const FString&) {
  TSet<FString> Systems;
  for (const TCHAR* Key : {TEXT("marmoreal"), TEXT("sarpedon")}) {
    FS08EnvLayout L;
    TArray<FString> Errors;
    const FString File = S08EnvLayout::FileFor(S08EnvLayout::DefaultDir(), Key);
    if (!FPaths::FileExists(File) || !L.LoadFile(File, Errors)) continue;
    for (const FString& Path : L.UniqueFxSystemPaths()) Systems.Add(Path);
  }
  int32 Checked = 0;
  for (const FString& Path : Systems) {
    int32 Dot = INDEX_NONE;
    const FString Pkg = Path.FindChar(TEXT('.'), Dot) ? Path.Left(Dot) : Path;
    if (!FPackageName::DoesPackageExist(Pkg)) {
      AddWarning(FString::Printf(TEXT("%s not imported (tools/art/env_kit/ue_import_fab_fx.py)"), *Pkg));
      continue;
    }
    UNiagaraSystem* System = LoadObject<UNiagaraSystem>(nullptr, *Path);
    if (!TestNotNull(Path + TEXT(": loads as a Niagara system"), System)) continue;
    ++Checked;
    int32 Emitters = 0, Gpu = 0, LightRenderers = 0, ComponentRenderers = 0;
    for (const FNiagaraEmitterHandle& H : System->GetEmitterHandles()) {
      if (!H.GetIsEnabled()) continue;
      ++Emitters;
      const FVersionedNiagaraEmitterData* D = H.GetEmitterData();
      if (!D) continue;
      Gpu += D->SimTarget == ENiagaraSimTarget::GPUComputeSim ? 1 : 0;
      for (const UNiagaraRendererProperties* R : D->GetRenderers()) {
        if (!R || !R->GetIsEnabled()) continue;
        LightRenderers += R->IsA<UNiagaraLightRendererProperties>() ? 1 : 0;
        ComponentRenderers += R->IsA<UNiagaraComponentRendererProperties>() ? 1 : 0;
      }
    }
    AddInfo(FString::Printf(TEXT("%s: emitters %d gpu %d light renderers %d component renderers %d determinism %d"), *Pkg,
                            Emitters, Gpu, LightRenderers, ComponentRenderers, System->NeedsDeterminism() ? 1 : 0));
    TestTrue(Pkg + TEXT(": at least one enabled emitter"), Emitters > 0);
    TestEqual(Pkg + TEXT(": CPU simulation only (ue_import_fab_fx.py simTarget cpu)"), Gpu, 0);
    TestEqual(Pkg + TEXT(": no Light renderer (light budget)"), LightRenderers, 0);
    TestEqual(Pkg + TEXT(": no Component renderer"), ComponentRenderers, 0);
    TestTrue(Pkg + TEXT(": system determinism (fixed seed)"), System->NeedsDeterminism());
  }
  AddInfo(FString::Printf(TEXT("fx systems checked: %d / %d"), Checked, Systems.Num()));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
