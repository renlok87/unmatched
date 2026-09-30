// ART-005 / stage 3 T3.2 automation tests: data-driven board art (S08BoardArt.h).
// Pure functions only (no world): the shipped profile data, the parser's
// budget/shape validation, profile selection (board id, then signature), the
// Cobble 5x6 legacy geometry and lights kept exact, multizone cells keeping
// every zone, and the committed art fixtures (backend/prisma/fixtures/
// art-boards) decoded through FS08BoardModel::Decode against their profiles.
// T4.2: the zone MI / glyph mesh fields of the data, the glyph anchors, and
// (ZoneContent, editor assets) the MIs and glyph meshes themselves.
// ENV-MAPS track S: the 'map-image' surface (MapImageParser, MapProfiles on the committed topology fixtures
// backend/prisma/fixtures/boards, MapCamera K1 distance, MapGeometry, MapPlaneUV on the engine plane,
// MapActor grey topology view + missing-asset fallback, MapAssets once the out-of-git import ran).
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.BoardArt; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08Diorama.h"
#include "S08FighterActor.h"
#include "S08Team.h"
#include "Components/BoxComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Texture2D.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/PackageName.h"
#include "StaticMeshResources.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "S08Contracts.h"
#include "S08Render.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/FileManager.h"
#include "Engine/StaticMesh.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstance.h"
#include "Materials/MaterialInterface.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace {
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

FS08BoardModel CobbleBoard() {
  FS08BoardModel Board = MakeBoard(5, 6);
  for (FS08Cell& Cell : Board.Cells) Cell.Zones = {Cell.Y < 3 ? TEXT("blue") : TEXT("red")};
  return Board;
}

bool LoadShipped(FS08BoardArtData& Data, TArray<FString>& Errors) {
  return Data.LoadFile(FS08BoardArtData::DefaultPath(), Errors);
}

FString FixtureDir() {
  return FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../backend/prisma/fixtures/art-boards")));
}

/** Fixture JSON (flat cells, backend Board.cells format) -> the boardState
 *  projection that buildBoardState produces (rows cells[y][x]). */
bool FixtureBoardState(const FString& File, TSharedPtr<FJsonValue>& OutState, FString& OutBoardId,
                       FS08BoardExpect& OutSummary) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *File)) return false;
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem)) return false;
  OutBoardId = Root->GetStringField(TEXT("boardId"));
  const TSharedPtr<FJsonObject> Grid = Root->GetObjectField(TEXT("grid"));
  const int32 W = static_cast<int32>(Grid->GetNumberField(TEXT("width")));
  const int32 H = static_cast<int32>(Grid->GetNumberField(TEXT("height")));
  const TSharedPtr<FJsonObject> Summary = Root->GetObjectField(TEXT("summary"));
  OutSummary.Cells = static_cast<int32>(Summary->GetNumberField(TEXT("cells")));
  OutSummary.ZoneCells = static_cast<int32>(Summary->GetNumberField(TEXT("zoneCells")));
  OutSummary.MultizoneCells = static_cast<int32>(Summary->GetNumberField(TEXT("multizoneCells")));
  OutSummary.Obstacles = static_cast<int32>(Summary->GetNumberField(TEXT("obstacleCells")));
  TArray<TArray<TSharedPtr<FJsonValue>>> Rows;
  Rows.SetNum(H);
  for (int32 Y = 0; Y < H; ++Y) Rows[Y].SetNum(W);
  for (const TSharedPtr<FJsonValue>& V : Root->GetArrayField(TEXT("cells"))) {
    const TSharedPtr<FJsonObject> C = V->AsObject();
    const int32 X = static_cast<int32>(C->GetNumberField(TEXT("x")));
    const int32 Y = static_cast<int32>(C->GetNumberField(TEXT("y")));
    TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
    bool bObstacle = false;
    C->TryGetBoolField(TEXT("isObstacle"), bObstacle);
    Cell->SetStringField(TEXT("type"), bObstacle ? TEXT("obstacle") : TEXT("normal"));
    Cell->SetNumberField(TEXT("x"), X);
    Cell->SetNumberField(TEXT("y"), Y);
    const TArray<TSharedPtr<FJsonValue>>* Zones = nullptr;
    if (C->TryGetArrayField(TEXT("zones"), Zones) && Zones) {
      Cell->SetArrayField(TEXT("zones"), *Zones);
      Cell->SetStringField(TEXT("zone"), (*Zones)[0]->AsString());
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
  OutState = MakeShared<FJsonValueObject>(State);
  return true;
}

const TCHAR* MinimalDoc = TEXT(
    "{\"schema\":\"unmatched.s08-art-board-profiles/1\",\"revision\":7,"
    "\"zoneStyles\":{\"a\":{\"stroke\":\"solid\",\"glyph\":\"diamond\",\"color\":\"#102030\"},"
    "\"b\":{\"stroke\":\"dash2\",\"glyph\":\"ring\",\"color\":\"#A0B0C0\"},"
    "\"c\":{\"stroke\":\"dots5\",\"glyph\":\"x\",\"color\":\"#FFFFFF\"}},"
    "\"fallbackZoneStyle\":{\"stroke\":\"dots5\",\"glyph\":\"bar1\",\"color\":\"#FFFFFF\"},"
    "\"lightProfiles\":{\"L\":{\"directional\":{\"name\":\"key\",\"posUU\":[0,0,600],\"rotation\":[-50,-90,0],"
    "\"intensity\":3,\"castShadows\":true},\"points\":[{\"name\":\"p\",\"at\":[0.5,-0.5,200],\"intensity\":50,"
    "\"radiusUU\":300,\"colorLinear\":[1,0.5,0.25]}]}},"
    "\"boards\":[{\"id\":\"one\",\"match\":{\"boardIds\":[\"cid1\"],\"width\":3,\"height\":2,\"zoneKeys\":[\"b\",\"a\"]},"
    "\"surface\":\"tiles\",\"light\":\"L\",\"expect\":{\"cells\":6,\"zoneCells\":6,\"multizoneCells\":1,\"obstacles\":0,"
    "\"zoneCellCounts\":{\"a\":3,\"b\":4}}}]}");
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtShippedTest,
    "Unmatched.S08.BoardArt.Shipped profiles parse with budgets and per-board unique zone shapes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtShippedTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  const bool bOk = LoadShipped(Data, Errors);
  for (const FString& E : Errors) AddError(E);
  TestTrue("shipped Config/ArtBoards/S08ArtBoardProfiles.json parses without errors", bOk);
  TestTrue("revision >= 1", Data.Revision >= 1);
  // ENV-MAPS (profile rev 6): + the map-image profiles of Marmoreal and Sarpedon.
  TestEqual("five board profiles (Cobble + 2 fixtures + 2 original maps)", Data.Boards.Num(), 5);
  for (const TPair<FString, FS08LightProfile>& Light : Data.Lights) {
    FString Reason;
    TestTrue(FString::Printf(TEXT("light %s budget: %s"), *Light.Key, *Reason), Light.Value.BudgetOk(Reason));
    TestTrue(FString::Printf(TEXT("light %s <= 6 points"), *Light.Key), Light.Value.Points.Num() <= 6);
    // W4-A: candela/lux units, SkyLight instead of a point fill, fixed exposure.
    TestTrue(FString::Printf(TEXT("light %s units candelas/lux"), *Light.Key), Light.Value.HasPhysicalUnits());
    TestTrue(FString::Printf(TEXT("light %s has a SkyLight"), *Light.Key), Light.Value.Sky.bSet);
    TestTrue(FString::Printf(TEXT("light %s fixed exposure"), *Light.Key),
             Light.Value.Exposure.bSet && Light.Value.Exposure.MinBrightness == Light.Value.Exposure.MaxBrightness);
    // 5c-B1 (profile rev 5): every key is FRotator(Pitch -55, Yaw 30, Roll 0) and every exposure is EV100 2.05
    // (min = max brightness 2^2.05 = 4.14106, bias 0); plan C:/tmp/p0-review/5cb1-plan.md rev 2, B1-1.
    TestTrue(FString::Printf(TEXT("light %s key rotation (-55,30,0)"), *Light.Key),
             Light.Value.bHasDirectional && Light.Value.Directional.Rotation.Equals(FRotator(-55, 30, 0)));
    TestTrue(FString::Printf(TEXT("light %s exposure EV100 2.05 fixed"), *Light.Key),
             FMath::IsNearlyEqual(Light.Value.Exposure.MinBrightness, 4.14106f) &&
                 FMath::IsNearlyEqual(Light.Value.Exposure.Ev100, 2.05f) && FMath::IsNearlyEqual(Light.Value.Exposure.Bias, 0.0f));
    for (const FS08LightSpec& Point : Light.Value.Points) {
      TestFalse(FString::Printf(TEXT("light %s: no point fill ambient"), *Light.Key), Point.Role == TEXT("fill"));
    }
  }
  TestEqual("profile sha256 recorded", Data.SourceSha256.Len(), 64);
  int32 MapProfiles = 0;
  for (const FS08BoardArtProfile& B : Data.Boards) {
    TestNotNull(FString::Printf(TEXT("%s: light profile present"), *B.Id), Data.LightFor(B));
    if (B.Surface == ES08BoardSurface::MapImage) {
      // ENV-MAPS map-image schema: matched by id only, the source size / scale of the client's layout frame,
      // /Game/EnvMaps/<Name>/ asset paths (the assets are out of git: no uasset / zone MI required here), the
      // space graph in expect instead of W x H cells. The zone keys are the painted ones (no zone styles needed).
      ++MapProfiles;
      const FS08MapImageSpec& M = B.Map;
      TestTrue(FString::Printf(TEXT("%s: mapImage block parsed"), *B.Id), M.bSet);
      TestTrue(FString::Printf(TEXT("%s: matched by Board row id only"), *B.Id),
               B.MatchBoardIds.Num() == 1 && B.MatchWidth == 0 && B.MatchHeight == 0 && B.MatchZoneKeys.Num() == 0);
      TestTrue(FString::Printf(TEXT("%s: srcSize 1337x866"), *B.Id), M.SrcSizePx == FIntPoint(1337, 866));
      TestTrue(FString::Printf(TEXT("%s: uuPerPx 2/3 (ENV-O1)"), *B.Id), FMath::IsNearlyEqual(M.UuPerPx, 2.0f / 3.0f, 1e-6f));
      TestTrue(FString::Printf(TEXT("%s: map frame == FS08LayoutFrame defaults (CellToWorld)"), *B.Id),
               M.MatchesDefaultLayoutFrame());
      TestTrue(FString::Printf(TEXT("%s: map 891.333 x 577.333 uu"), *B.Id),
               M.SizeUU().Equals(FVector2D(891.3333, 577.3333), 0.01));
      TestTrue(FString::Printf(TEXT("%s: frameUU 24 (the 'tiles' frame look)"), *B.Id),
               FMath::IsNearlyEqual(M.FrameUU, S08MapSurfaceSpec::DefaultFrameUU));
      const FString Folder = FString(S08MapSurfaceSpec::AssetRoot) + M.Name + TEXT("/");
      // SDF / space ID (not sampled yet) under the never-cooked data root (DefaultGame.ini DirectoriesToNeverCook)
      const FString DataFolder = FString(S08MapSurfaceSpec::DataRoot) + M.Name + TEXT("/");
      TArray<TPair<FString, FString>> Expected;
      Expected.Add(TPair<FString, FString>(M.BaseColorPath, Folder + FString::Printf(TEXT("T_%s_Map_BC_4K"), *M.Name)));
      Expected.Add(TPair<FString, FString>(M.MaskPath, Folder + FString::Printf(TEXT("T_%s_Map_GameMask_4K"), *M.Name)));
      Expected.Add(TPair<FString, FString>(M.SdfPath, DataFolder + FString::Printf(TEXT("T_%s_Map_GameSDF_4K"), *M.Name)));
      Expected.Add(TPair<FString, FString>(M.SpaceIdPath, DataFolder + FString::Printf(TEXT("T_%s_Map_SpaceID_4K"), *M.Name)));
      Expected.Add(TPair<FString, FString>(M.MaterialInstancePath, Folder + FString::Printf(TEXT("MI_%s_MapBoard"), *M.Name)));
      for (const TPair<FString, FString>& Path : Expected) {
        TestEqual(FString::Printf(TEXT("%s: asset path %s"), *B.Id, *Path.Key), Path.Key, Path.Value);
      }
      TestTrue(FString::Printf(TEXT("%s: manifest %s"), *B.Id, *M.ManifestPath),
               M.ManifestPath.StartsWith(TEXT("tools/art/map_surface/manifest.")) && M.ManifestPath.EndsWith(TEXT(".json")) &&
                   FPaths::FileExists(FPaths::Combine(FPaths::ProjectDir(), TEXT("../.."), M.ManifestPath)));
      TestTrue(FString::Printf(TEXT("%s: expect spaces / links / zones / multizone"), *B.Id),
               B.Expect.Spaces > 0 && B.Expect.Links >= B.Expect.Spaces - 1 && B.Expect.Zones.Num() > 0 &&
                   B.Expect.MultizoneCells >= 0);
      TestTrue(FString::Printf(TEXT("%s: no W x H expect (cells / obstacles)"), *B.Id),
               B.Expect.Cells < 0 && B.Expect.Obstacles < 0);
      TestFalse(FString::Printf(TEXT("%s: no legacy Cobble trace"), *B.Id), B.bLegacyCobbleTrace);
      continue;
    }
    TSet<ES08ZoneStroke> Strokes;
    TSet<ES08ZoneGlyph> Glyphs;
    for (const FString& Key : B.MatchZoneKeys) {
      const FS08ZoneStyle Style = Data.StyleFor(Key);
      TestFalse(FString::Printf(TEXT("%s: zone key %s has an authored style"), *B.Id, *Key), Style.bFallback);
      Strokes.Add(Style.Stroke);
      Glyphs.Add(Style.Glyph);
    }
    TestEqual(FString::Printf(TEXT("%s: strokes unique per board"), *B.Id), Strokes.Num(), B.MatchZoneKeys.Num());
    TestEqual(FString::Printf(TEXT("%s: glyphs unique per board"), *B.Id), Glyphs.Num(), B.MatchZoneKeys.Num());
    TestEqual(FString::Printf(TEXT("%s: expect.cells = W*H"), *B.Id), B.Expect.Cells, B.MatchWidth * B.MatchHeight);
  }
  TestEqual("two map-image profiles", MapProfiles, 2);
  struct FMapProfileId {
    const TCHAR* Profile;
    const TCHAR* BoardId;  // backend/prisma/fixtures/boards/<key>.topology.json boardId
  };
  for (const FMapProfileId& Map : {FMapProfileId{TEXT("marmoreal-original"), TEXT("c121b47f8d6eb28daccb76d05")},
                                   FMapProfileId{TEXT("sarpedon-original"), TEXT("c7fa64a26c29a0835f2383e63")}}) {
    const FS08BoardArtProfile* P = Data.Boards.FindByPredicate([&](const FS08BoardArtProfile& B) { return B.Id == Map.Profile; });
    if (TestNotNull(FString(Map.Profile) + TEXT(" profile"), P)) {
      TestTrue(FString(Map.Profile) + TEXT(": map-image surface matched by the topology fixture's board id"),
               P->Surface == ES08BoardSurface::MapImage && P->MatchBoardIds.Contains(Map.BoardId));
    }
  }
  const FS08BoardArtProfile* Cobble = Data.Boards.FindByPredicate(
      [](const FS08BoardArtProfile& B) { return B.Id == TEXT("cobble-city"); });
  if (TestNotNull("cobble-city profile", Cobble)) {
    TestTrue("Cobble keeps the ART-005 slab", Cobble->Surface == ES08BoardSurface::Cobble5x6Mesh);
    TestTrue("Cobble keeps the legacy trace lines", Cobble->bLegacyCobbleTrace);
    TestFalse("Cobble keeps the ART-005 review glyph material", Cobble->bZoneColorGlyphs);
  }
  // A key never listed falls back visibly (drawn + traced, never dropped).
  TestTrue("unknown key -> fallback style", Data.StyleFor(TEXT("no-such-zone")).bFallback);
  // T4.2: every zone key and the fallback have a zone MI under /Game/ArtTests/ART005/Zones, every glyph a mesh.
  for (const TPair<FString, FS08ZoneStyle>& Style : Data.ZoneStyles) {
    TestTrue(FString::Printf(TEXT("zone %s has a T4.2 MI: '%s'"), *Style.Key, *Style.Value.MaterialInstancePath),
             Style.Value.MaterialInstancePath.StartsWith(TEXT("/Game/ArtTests/ART005/Zones/MI_ART005_Zone_")));
  }
  TestTrue(TEXT("fallback style has a T4.2 MI: ") + Data.FallbackStyle.MaterialInstancePath,
           Data.FallbackStyle.MaterialInstancePath.StartsWith(TEXT("/Game/ArtTests/ART005/Zones/MI_ART005_Zone_")));
  for (const ES08ZoneGlyph G : {ES08ZoneGlyph::Diamond, ES08ZoneGlyph::Bar1, ES08ZoneGlyph::Bars2, ES08ZoneGlyph::Bars3,
                                ES08ZoneGlyph::HBars2, ES08ZoneGlyph::Square, ES08ZoneGlyph::Cross, ES08ZoneGlyph::X,
                                ES08ZoneGlyph::Tee, ES08ZoneGlyph::Chevron, ES08ZoneGlyph::Ring}) {
    const FString* Path = Data.GlyphMeshPaths.Find(S08ZoneGlyphName(G));
    TestTrue(FString::Printf(TEXT("glyph %s has a T4.2 mesh"), S08ZoneGlyphName(G)),
             Path && Path->StartsWith(TEXT("/Game/ArtTests/ART005/Zones/SM_ART005_ZoneGlyph_")));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtParserTest,
    "Unmatched.S08.BoardArt.Parser validates light budgets, shapes and colours",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtParserTest::RunTest(const FString&) {
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue("minimal document parses", Data.ParseJson(MinimalDoc, Errors));
    TestEqual("revision", Data.Revision, 7);
    TestEqual("colour #A0B0C0 kept as sRGB bytes", Data.StyleFor(TEXT("b")).ColorHex(), FString(TEXT("#A0B0C0")));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    if (TestNotNull("light L", L)) {
      TestTrue("point colour is linear", L->Points[0].bHasColor && FMath::IsNearlyEqual(L->Points[0].Color.G, 0.5f));
      TestFalse("points do not cast shadows by default", L->Points[0].bCastShadows);
    }
  }
  auto Expect = [this](const FString& Name, const FString& From, const FString& To, const FString& ErrorPart) {
    FString Doc = MinimalDoc;
    TestTrue(Name + TEXT(": patch applies"), Doc.Contains(From));
    Doc.ReplaceInline(*From, *To);
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestFalse(Name + TEXT(": rejected"), Data.ParseJson(Doc, Errors));
    TestTrue(Name + TEXT(": reason '") + ErrorPart + TEXT("' in ") + FString::Join(Errors, TEXT(" | ")),
             FString::Join(Errors, TEXT(" | ")).Contains(ErrorPart));
  };
  Expect(TEXT("directional without shadow"), TEXT("\"castShadows\":true"), TEXT("\"castShadows\":false"),
         TEXT("directional light without shadow"));
  Expect(TEXT("point with shadow"), TEXT("\"radiusUU\":300,"), TEXT("\"radiusUU\":300,\"castShadows\":true,"),
         TEXT("casts shadows"));
  const FString P = TEXT("{\"name\":\"q\",\"at\":[0,0,100],\"intensity\":1,\"radiusUU\":100}");
  Expect(TEXT("seven points"), TEXT("\"points\":[{"),
         TEXT("\"points\":[") + FString::Join(TArray<FString>{P, P, P, P, P, P}, TEXT(",")) + TEXT(",{"),
         TEXT("7 point lights > 6"));
  Expect(TEXT("unknown stroke"), TEXT("\"stroke\":\"dash2\""), TEXT("\"stroke\":\"wavy\""), TEXT("unknown stroke"));
  Expect(TEXT("unknown glyph"), TEXT("\"glyph\":\"ring\""), TEXT("\"glyph\":\"star\""), TEXT("unknown glyph"));
  Expect(TEXT("bad colour"), TEXT("\"color\":\"#102030\""), TEXT("\"color\":\"blue\""), TEXT("is not #RRGGBB"));
  Expect(TEXT("missing light profile"), TEXT("\"light\":\"L\""), TEXT("\"light\":\"nope\""), TEXT("missing or invalid"));
  Expect(TEXT("unknown glyph material"), TEXT("\"surface\":\"tiles\","), TEXT("\"surface\":\"tiles\",\"glyphs\":\"neon\","),
         TEXT("is not zone|review"));
    Expect(TEXT("wrong schema"), TEXT("s08-art-board-profiles/1"), TEXT("s08-art-board-profiles/9"), TEXT("schema"));
  // T4.2 content fields: valid ones parse, broken ones reject the document.
  {
    FString Doc = MinimalDoc;
    Doc.ReplaceInline(TEXT("\"color\":\"#102030\"}"),
                      TEXT("\"color\":\"#102030\",\"materialInstance\":\"/Game/Z/MI_A\"}"));
    Doc.ReplaceInline(TEXT("\"lightProfiles\":"), TEXT("\"glyphMeshes\":{\"ring\":\"/Game/Z/SM_Ring\"},\"lightProfiles\":"));
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue(TEXT("T4.2 fields parse: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Doc, Errors));
    TestEqual("zone MI path kept", Data.StyleFor(TEXT("a")).MaterialInstancePath, FString(TEXT("/Game/Z/MI_A")));
    TestTrue("a style without an MI keeps the tint", Data.StyleFor(TEXT("b")).MaterialInstancePath.IsEmpty());
    TestEqual("glyph mesh path kept", Data.GlyphMeshPaths.FindRef(TEXT("ring")), FString(TEXT("/Game/Z/SM_Ring")));
  }
  Expect(TEXT("zone MI outside /Game"), TEXT("\"color\":\"#102030\"}"),
         TEXT("\"color\":\"#102030\",\"materialInstance\":\"/Engine/X\"}"), TEXT("materialInstance"));
  Expect(TEXT("glyph mesh for an unknown glyph"), TEXT("\"lightProfiles\":"),
         TEXT("\"glyphMeshes\":{\"star\":\"/Game/Z/SM_Star\"},\"lightProfiles\":"), TEXT("unknown glyph 'star'"));
  Expect(TEXT("glyph mesh outside /Game"), TEXT("\"lightProfiles\":"),
         TEXT("\"glyphMeshes\":{\"ring\":\"SM_Ring\"},\"lightProfiles\":"), TEXT("glyphMeshes ring"));
  // W4-A render blocks: valid ones parse, broken ones reject the profile.
  const FString Blocks = TEXT("\"L\":{\"units\":{\"point\":\"candelas\",\"directional\":\"lux\"},")
      TEXT("\"sky\":{\"source\":\"cubemap\",\"cubemap\":\"/Game/S08/Render/TC_S08_AmbientDome\",\"intensity\":8,")
      TEXT("\"colorLinear\":[1,0.9,0.8]},\"exposure\":{\"method\":\"histogram-fixed\",\"ev100\":1.3,")
      TEXT("\"minBrightness\":2.46229,\"maxBrightness\":2.46229,\"bias\":0},");
  const FString Shadow = TEXT("\"castShadows\":true,\"shadow\":{\"distanceUU\":3000,\"cascades\":2,\"contactShadowLength\":0.02}");
  FString Render = MinimalDoc;
  Render.ReplaceInline(TEXT("\"L\":{"), *Blocks);
  Render.ReplaceInline(TEXT("\"castShadows\":true"), *Shadow);
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue(TEXT("render blocks parse: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Render, Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    if (TestNotNull("light L with render blocks", L)) {
      TestTrue("units", L->HasPhysicalUnits());
      TestTrue("sky", L->Sky.bSet && FMath::IsNearlyEqual(L->Sky.Intensity, 8.0f) &&
                          FMath::IsNearlyEqual(L->Sky.Color.B, 0.8f));
      TestTrue("exposure", L->Exposure.bSet && FMath::IsNearlyEqual(L->Exposure.MinBrightness, 2.46229f) &&
                               FMath::IsNearlyEqual(L->Exposure.Ev100, 1.3f));
      TestTrue("key csm", L->KeyShadow.bSet && L->KeyShadow.Cascades == 2 &&
                              FMath::IsNearlyEqual(L->KeyShadow.DistanceUU, 3000.0f));
    }
    FS08BoardArtData Legacy;
    TestTrue("a profile without units still parses (pre-W4 data, legacy)", Legacy.ParseJson(MinimalDoc, Errors));
    const FS08LightProfile* LegacyLight = Legacy.Lights.Find(TEXT("L"));
    TestTrue("legacy profile has no physical units", LegacyLight && !LegacyLight->HasPhysicalUnits());
  }
  auto ExpectRender = [this, &Render](const FString& Name, const FString& From, const FString& To, const FString& ErrorPart) {
    FString Doc = Render;
    TestTrue(Name + TEXT(": patch applies"), Doc.Contains(From));
    Doc.ReplaceInline(*From, *To);
    FS08BoardArtData Data;
    TArray<FString> Errors;
    Data.ParseJson(Doc, Errors);
    TestFalse(Name + TEXT(": profile rejected"), Data.Lights.Contains(TEXT("L")));
    TestTrue(Name + TEXT(": reason '") + ErrorPart + TEXT("' in ") + FString::Join(Errors, TEXT(" | ")),
             FString::Join(Errors, TEXT(" | ")).Contains(ErrorPart));
  };
  ExpectRender(TEXT("unitless points"), TEXT("\"point\":\"candelas\""), TEXT("\"point\":\"unitless\""), TEXT("units must be"));
  ExpectRender(TEXT("engine cubemap"), TEXT("/Game/S08/Render/TC_S08_AmbientDome"), TEXT("/Engine/X"), TEXT("sky needs"));
  ExpectRender(TEXT("exposure range"), TEXT("\"maxBrightness\":2.46229"), TEXT("\"maxBrightness\":8"), TEXT("exposure needs"));
  ExpectRender(TEXT("too many cascades"), TEXT("\"cascades\":2"), TEXT("\"cascades\":9"), TEXT("directional.shadow needs"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08RenderSha256Test,
    "Unmatched.S08.Render.Sha256 of the profile bytes matches the FIPS 180-2 vectors",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08RenderSha256Test::RunTest(const FString&) {
  auto Hash = [](const char* Text) {
    return S08Sha256Hex(reinterpret_cast<const uint8*>(Text), static_cast<int64>(FCStringAnsi::Strlen(Text)));
  };
  TestEqual("empty", Hash(""), FString(TEXT("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")));
  TestEqual("abc", Hash("abc"), FString(TEXT("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")));
  TestEqual("56-byte message (two padding blocks)",
            Hash("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
            FString(TEXT("248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtSelectTest,
    "Unmatched.S08.BoardArt.Profile selection by board id then by W x H and zone keys",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtSelectTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  TestTrue("minimal document parses", Data.ParseJson(MinimalDoc, Errors));
  FS08BoardModel Board = MakeBoard(3, 2);
  for (FS08Cell& Cell : Board.Cells) Cell.Zones = {Cell.X == 0 ? TEXT("a") : TEXT("b")};
  Board.Cells[1].Zones = {TEXT("a"), TEXT("b")};
  ES08ProfileMatch Match;
  const FS08BoardArtProfile* P = Data.Select(Board, TEXT("cid1"), Match);
  TestTrue("board id match", P && P->Id == TEXT("one") && Match == ES08ProfileMatch::BoardId);
  P = Data.Select(Board, FString(), Match);
  TestTrue("signature match (3x2, zone keys {a,b})", P && Match == ES08ProfileMatch::Signature);
  TestEqual("expect met", S08ExpectMismatch(*P, S08SummarizeBoard(Board)), FString());
  P = Data.Select(Board, TEXT("other-id"), Match);
  TestTrue("unknown id falls back to the signature", P && Match == ES08ProfileMatch::Signature);
  FS08BoardModel Bigger = MakeBoard(20, 20);
  P = Data.Select(Bigger, FString(), Match);
  TestTrue("20x20 fallback grid gets no art", !P && Match == ES08ProfileMatch::None);
  FS08BoardModel ThirdKey = Board;
  ThirdKey.Cells[5].Zones = {TEXT("c")};
  P = Data.Select(ThirdKey, FString(), Match);
  TestNull("an extra zone key breaks the signature", P);
  P = Data.Select(ThirdKey, TEXT("cid1"), Match);
  if (TestNotNull("id still selects", P)) {
    TestTrue("but the expect check reports the difference",
             S08ExpectMismatch(*P, S08SummarizeBoard(ThirdKey)).Contains(TEXT("c 1!=0")));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtCobbleLegacyTest,
    "Unmatched.S08.BoardArt.Cobble 5x6 keeps the ART-005 marks, counts and probe lights",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtCobbleLegacyTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", LoadShipped(Data, Errors))) return false;
  const FS08BoardModel Board = CobbleBoard();
  ES08ProfileMatch Match;
  const FS08BoardArtProfile* P = Data.Select(Board, TEXT("cmuhgs4b2001mwik4f2b2xtf8"), Match);
  if (!TestTrue("Cobble row id -> cobble-city", P && P->Id == TEXT("cobble-city"))) return false;
  P = Data.Select(Board, FString(), Match);
  TestTrue("Cobble signature -> cobble-city", P && P->Id == TEXT("cobble-city") && Match == ES08ProfileMatch::Signature);
  TestEqual("Cobble expect met", S08ExpectMismatch(*P, S08SummarizeBoard(Board)), FString());
  const FS08ZoneMarkLayout L = S08BuildZoneMarks(Board, Data);
  // 'ARTPREVIEW Cobble active 5x6 zones=30 blue=15 red=15 blueMarks=15 redMarks=45'
  TestEqual("blue cells", L.CellsByKey.FindRef(TEXT("blue")), 15);
  TestEqual("red cells", L.CellsByKey.FindRef(TEXT("red")), 15);
  TestEqual("blueMarks", L.StrokePiecesByKey.FindRef(TEXT("blue")), 15);
  TestEqual("redMarks", L.StrokePiecesByKey.FindRef(TEXT("red")), 45);
  TestEqual("glyph pieces 15 diamonds + 30 bars", L.Glyphs.Num(), 45);
  // Legacy counts above stay exact; W5b-R D-4 moved the strokes inside the slab (Solid centre 41.5, Dash3 41.25:
  // fill + 1.5-uu keyline <= 45 uu) and the glyphs above the strokes (z 0.38). The scales are the legacy ones.
  const FVector BlueWorld = Board.CellToWorld(1, 0);
  const FS08ZoneMarkPiece* BlueStroke = L.Strokes.FindByPredicate(
      [](const FS08ZoneMarkPiece& M) { return M.Cell == FIntPoint(1, 0); });
  if (TestNotNull("blue stroke", BlueStroke)) {
    TestTrue("blue edge position", BlueStroke->Transform.GetTranslation().Equals(BlueWorld + FVector(0, 41.5f, 0.28f), 1e-4f));
    TestTrue("blue edge scale", BlueStroke->Transform.GetScale3D().Equals(FVector(0.96f, 0.04f, 0.004f), 0.0f));
  }
  const FVector RedWorld = Board.CellToWorld(3, 4);
  int32 RedPieces = 0;
  for (const FS08ZoneMarkPiece& M : L.Strokes) {
    if (M.Cell != FIntPoint(3, 4)) continue;
    const float Offset = -32.0f + 32.0f * RedPieces++;
    TestTrue("red stroke position", M.Transform.GetTranslation().Equals(RedWorld + FVector(Offset, 41.25f, 0.28f), 1e-4f));
    TestTrue("red stroke scale", M.Transform.GetScale3D().Equals(FVector(0.28f, 0.045f, 0.004f), 0.0f));
  }
  TestEqual("three red strokes", RedPieces, 3);
  const FS08ZoneMarkPiece* Diamond = L.Glyphs.FindByPredicate(
      [](const FS08ZoneMarkPiece& M) { return M.Cell == FIntPoint(1, 0); });
  if (TestNotNull("blue diamond", Diamond)) {
    TestTrue("diamond at the near-left slot", Diamond->Transform.GetTranslation().Equals(BlueWorld + FVector(-32, 32, 0.38f), 1e-4f));
    TestTrue("diamond rotated 45", Diamond->Transform.Rotator().Equals(FRotator(0, 45, 0), 0.01f));
  }
  // Probe lights: key 4.5 lux at (-350,-150,600) rot (-55,30,0) with shadow (5c-B1 rev 5: Pitch -55;
  // rev 4 had (0,-55,30) = a horizontal key); warm 85 cd. W4-A: the point fill (700) became the SkyLight,
  // units are candelas/lux, exposure fixed (5c-B1 rev 5: EV100 2.05, was 1.3), key CSM 3000 uu / 2 cascades.
  const FS08LightProfile* Light = Data.LightFor(*P);
  if (TestNotNull("cobble light profile", Light)) {
    const TArray<FS08PlacedLight> Placed = S08PlaceLights(*Light, Board);
    if (TestEqual("1 directional + 1 point", Placed.Num(), 2)) {
      TestTrue("key", Placed[0].Spec.bDirectional && Placed[0].Position.Equals(FVector(-350, -150, 600)) &&
                          Placed[0].Spec.Rotation.Equals(FRotator(-55, 30, 0)) &&
                          FMath::IsNearlyEqual(Placed[0].Spec.Intensity, 4.5f) && Placed[0].Spec.bCastShadows &&
                          !Placed[0].Spec.bHasColor);
      TestTrue("warm", Placed[1].Position.Equals(FVector(260, -300, 250)) &&
                           FMath::IsNearlyEqual(Placed[1].Spec.Intensity, 85.0f) &&
                           FMath::IsNearlyEqual(Placed[1].Spec.RadiusUU, 450.0f));
    }
    TestTrue("candelas/lux", Light->HasPhysicalUnits());
    TestTrue("sky from the ambient dome", Light->Sky.bSet && Light->Sky.CubemapPath == TEXT("/Game/S08/Render/TC_S08_AmbientDome"));
    TestTrue("exposure EV100 2.05 fixed", Light->Exposure.bSet && FMath::IsNearlyEqual(Light->Exposure.MinBrightness, 4.14106f) &&
                                             FMath::IsNearlyEqual(Light->Exposure.Bias, 0.0f));
    TestTrue("key csm", Light->KeyShadow.bSet && Light->KeyShadow.Cascades == 2);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMultizoneTest,
    "Unmatched.S08.BoardArt.Multizone cells keep every zone on its own side and glyph slot",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMultizoneTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", LoadShipped(Data, Errors))) return false;
  FS08BoardModel Board = MakeBoard(3, 1);
  Board.Cells[0].Zones = {TEXT("gray"), TEXT("orange")};
  Board.Cells[1].Zones = {TEXT("gray"), TEXT("brown"), TEXT("yellow")};
  Board.Cells[2].Zones = {TEXT("a"), TEXT("b"), TEXT("c"), TEXT("d"), TEXT("e")};  // unknown keys, 5 zones
  const FS08ZoneMarkLayout L = S08BuildZoneMarks(Board, Data);
  TestEqual("three multizone cells", L.MultizoneCells, 3);
  TestEqual("zones listed", L.MultizoneZonesListed, 10);
  TestEqual("every listed zone marked (stroke + glyph)", L.MultizoneZonesMarked, 10);
  TestEqual("unknown keys reported as fallback", L.FallbackKeys.Num(), 5);
  // The triple cell: one stroke side and one glyph slot per zone.
  for (int32 Slot = 0; Slot < 3; ++Slot) {
    TSet<FString> Keys;
    for (const FS08ZoneMarkPiece& M : L.Strokes) {
      if (M.Cell == FIntPoint(1, 0) && M.Slot == Slot) Keys.Add(M.Key);
    }
    TestEqual(FString::Printf(TEXT("triple cell side %d has exactly one zone"), Slot), Keys.Num(), 1);
  }
  const FVector C = Board.CellToWorld(1, 0);
  bool bNear = false, bLeft = false, bFar = false;
  for (const FS08ZoneMarkPiece& M : L.Strokes) {
    if (M.Cell != FIntPoint(1, 0)) continue;
    const FVector D = M.Transform.GetTranslation() - C;
    bNear |= M.Key == TEXT("gray") && D.Y > 40.0;
    bLeft |= M.Key == TEXT("brown") && D.X < -40.0;
    bFar |= M.Key == TEXT("yellow") && D.Y < -40.0;
  }
  TestTrue("zone 0 near side, zone 1 left side, zone 2 far side", bNear && bLeft && bFar);
  TestTrue("per-cell line lists all zones",
           L.MultizoneLines.ContainsByPredicate([](const FString& S) { return S.StartsWith(TEXT("(1,0) gray+brown+yellow")) && S.EndsWith(TEXT("marked=3/3")); }));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtFixtureTest,
    "Unmatched.S08.BoardArt.Committed Sherwood and T. Rex fixtures decode to their profiles",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtFixtureTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", LoadShipped(Data, Errors))) return false;
  TArray<FString> Files;
  IFileManager::Get().FindFiles(Files, *FPaths::Combine(FixtureDir(), TEXT("*.art-fixture.json")), true, false);
  Files.Sort();
  if (!TestEqual(TEXT("two fixtures in ") + FixtureDir(), Files.Num(), 2)) return false;
  for (const FString& Name : Files) {
    TSharedPtr<FJsonValue> State;
    FString BoardId;
    FS08BoardExpect FromFixture;
    if (!TestTrue(Name + TEXT(": fixture -> boardState"),
                  FixtureBoardState(FPaths::Combine(FixtureDir(), Name), State, BoardId, FromFixture))) continue;
    FS08BoardModel Board;
    if (!TestTrue(Name + TEXT(": FS08BoardModel::Decode"), Board.Decode(State))) continue;
    ES08ProfileMatch Match;
    const FS08BoardArtProfile* P = Data.Select(Board, BoardId, Match);
    if (!TestTrue(Name + TEXT(": profile by board id"), P && Match == ES08ProfileMatch::BoardId)) continue;
    const FS08BoardSummary S = S08SummarizeBoard(Board);
    TestEqual(Name + TEXT(": expect met"), S08ExpectMismatch(*P, S), FString());
    TestEqual(Name + TEXT(": cells = fixture"), S.Cells, FromFixture.Cells);
    TestEqual(Name + TEXT(": multizone = fixture"), S.MultizoneCells, FromFixture.MultizoneCells);
    TestEqual(Name + TEXT(": obstacles = fixture"), S.Obstacles, FromFixture.Obstacles);
    TestTrue(Name + TEXT(": >= 2 multizone cells"), S.MultizoneCells >= 2);
    ES08ProfileMatch BySignature;
    TestTrue(Name + TEXT(": the signature alone selects the same profile"),
             Data.Select(Board, FString(), BySignature) == P && BySignature == ES08ProfileMatch::Signature);
    TestTrue(Name + TEXT(": 'tiles' surface, zone-colour glyphs"),
             P->Surface == ES08BoardSurface::Tiles && P->bArtFixture && P->bZoneColorGlyphs);
    const FS08ZoneMarkLayout L = S08BuildZoneMarks(Board, Data);
    TestEqual(Name + TEXT(": all multizone zones marked"), L.MultizoneZonesMarked, L.MultizoneZonesListed);
    TestEqual(Name + TEXT(": no fallback zone style"), L.FallbackKeys.Num(), 0);
    const FS08LightProfile* Light = Data.LightFor(*P);
    if (TestNotNull(Name + TEXT(": light profile"), Light)) {
      const TArray<FS08PlacedLight> Placed = S08PlaceLights(*Light, Board);
      int32 Warm = 0, Cool = 0;
      for (const FS08PlacedLight& Pl : Placed) {
        Warm += Pl.Spec.Role == TEXT("warm");
        Cool += Pl.Spec.Role == TEXT("cool");
        if (!Pl.Spec.bDirectional && !Pl.Spec.bHasPosUU) {
          TestTrue(Name + TEXT(": board-relative spot inside the board footprint"),
                   FMath::Abs(Pl.Position.X) <= Board.Width * 50.0 && FMath::Abs(Pl.Position.Y) <= Board.Height * 50.0);
        }
      }
      TestTrue(Name + TEXT(": separate warm and cool spots"), Warm >= 1 && Cool >= 1);
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtGlyphAnchorTest,
    "Unmatched.S08.BoardArt.GlyphAnchors one per zone slot, pieces are the slot-0 glyph moved",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtGlyphAnchorTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", LoadShipped(Data, Errors))) return false;
  FS08BoardModel Board = MakeBoard(3, 1);
  Board.Cells[0].Zones = {TEXT("gray")};
  Board.Cells[1].Zones = {TEXT("gray"), TEXT("brown"), TEXT("yellow")};
  Board.Cells[2].Zones = {TEXT("a"), TEXT("b"), TEXT("c"), TEXT("d"), TEXT("e")};
  const FS08ZoneMarkLayout L = S08BuildZoneMarks(Board, Data);
  TestEqual("one anchor per zone of every cell", L.GlyphAnchors.Num(), 9);
  for (const FS08ZoneMarkPiece& A : L.GlyphAnchors) {
    const FVector Want = Board.CellToWorld(A.Cell.X, A.Cell.Y) + S08GlyphAnchor(A.Slot);
    TestTrue(FString::Printf(TEXT("anchor (%d,%d) slot %d at the slot centre"), A.Cell.X, A.Cell.Y, A.Slot),
             A.Transform.GetTranslation().Equals(Want, 1e-3) && A.Transform.GetRotation().IsIdentity(1e-6) &&
                 A.Transform.GetScale3D().Equals(FVector::OneVector, 1e-6));
  }
  TestTrue("a fifth zone reuses slot 0 (i % 4)", S08GlyphAnchor(4).Equals(S08GlyphAnchor(0), 1e-6));
  // A glyph mesh instance at the anchor draws exactly the cube pieces: slot pieces == slot-0 pieces + anchor delta.
  for (const ES08ZoneGlyph G : {ES08ZoneGlyph::Diamond, ES08ZoneGlyph::Tee, ES08ZoneGlyph::Chevron, ES08ZoneGlyph::Ring}) {
    TArray<FTransform> P0, P2;
    S08GlyphPieces(G, 0, P0);
    S08GlyphPieces(G, 2, P2);
    const FVector Delta = S08GlyphAnchor(2) - S08GlyphAnchor(0);
    bool bSame = P0.Num() == P2.Num();
    for (int32 I = 0; bSame && I < P0.Num(); ++I) {
      bSame = P2[I].GetTranslation().Equals(P0[I].GetTranslation() + Delta, 1e-3) &&
              P2[I].GetRotation().Equals(P0[I].GetRotation(), 1e-6) &&
              P2[I].GetScale3D().Equals(P0[I].GetScale3D(), 1e-6);
    }
    TestTrue(FString::Printf(TEXT("glyph %s: slot pieces are a translation of slot 0"), S08ZoneGlyphName(G)), bSame);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtZoneContentTest,
    "Unmatched.S08.BoardArt.ZoneContent T4.2 zone MIs and glyph meshes match the data and the cube pieces",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtZoneContentTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", LoadShipped(Data, Errors))) return false;
  TArray<FS08ZoneStyle> Styles;
  Data.ZoneStyles.GenerateValueArray(Styles);
  Styles.Add(Data.FallbackStyle);
  for (const FS08ZoneStyle& Style : Styles) {
    const FString Name = Style.bFallback ? FString(TEXT("(fallback)")) : Style.Key;
    UMaterialInstance* MI = LoadObject<UMaterialInstance>(nullptr, *Style.MaterialInstancePath);
    if (!TestNotNull(Name + TEXT(": MI loads ") + Style.MaterialInstancePath, MI)) continue;
    TestTrue(Name + TEXT(": parent is the game-layer master M_UM_GameLayer"),
             MI->Parent && MI->Parent->GetPathName() == TEXT("/Game/UM/Materials/M_UM_GameLayer.M_UM_GameLayer"));
    FLinearColor Got;
    const bool bHas = MI->GetVectorParameterValue(FHashedMaterialParameterInfo(TEXT("LayerColor")), Got);
    const FLinearColor Want(Style.Color);  // = the pre-T4.2 runtime tint (FLinearColor(FColor), memory trap 9)
    TestTrue(FString::Printf(TEXT("%s: LayerColor %s == FLinearColor(%s) %s"), *Name, *Got.ToString(),
                             *Style.ColorHex(), *Want.ToString()),
             bHas && Got.Equals(Want, 1e-5f));
    const UMaterial* Base = MI->GetMaterial();
    TestTrue(Name + TEXT(": base material has ISM usage"), Base && Base->GetUsageByFlag(MATUSAGE_InstancedStaticMeshes));
  }
  for (const TPair<FString, FString>& Glyph : Data.GlyphMeshPaths) {
    ES08ZoneGlyph G;
    if (!TestTrue(Glyph.Key + TEXT(": glyph name"), S08ParseZoneGlyph(Glyph.Key, G))) continue;
    UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *Glyph.Value);
    if (!TestNotNull(Glyph.Key + TEXT(": mesh loads ") + Glyph.Value, Mesh)) continue;
    TArray<FTransform> Pieces;
    S08GlyphPieces(G, 0, Pieces);
    FBox Want(ForceInit);
    for (const FTransform& T : Pieces) {
      for (int32 C = 0; C < 8; ++C) {
        const FVector Corner((C & 1) ? 50.0 : -50.0, (C & 2) ? 50.0 : -50.0, (C & 4) ? 50.0 : -50.0);
        Want += T.TransformPosition(Corner) - S08GlyphAnchor(0);
      }
    }
    const FBox Got = Mesh->GetBoundingBox();
    TestTrue(FString::Printf(TEXT("%s: mesh bounds %s == cube pieces %s"), *Glyph.Key, *Got.ToString(), *Want.ToString()),
             Got.Min.Equals(Want.Min, 0.01) && Got.Max.Equals(Want.Max, 0.01));
#if WITH_EDITOR
    TestFalse(Glyph.Key + TEXT(": Nanite off"), Mesh->IsNaniteEnabled());  // editor-only API
#endif
  }
  return true;
}

// Stage 3 T5.2: K3 on the art fixtures needs the S09AUTO driver to reach melee
// range. The T3.2 attempt on T. Rex parked Medusa on (2,2) for the whole game:
// obstacle (3,2) and her three Harpies on the other neighbours, and the old
// driver only tried one-cell steps. PickApproachDestination (multi-step, allies
// pass-through, terrain distance to the nearest enemy) must get her out and
// into melee range within a few maneuvers; the start layout is the one the
// backend placed in that run (host trace SHOT fighter lines).
namespace {
FS08BoardFighter ApproachFighter(const TCHAR* Id, const TCHAR* Owner, bool bHero, int32 X, int32 Y,
                                 int32 Movement) {
  FS08BoardFighter F;
  F.Id = Id;
  F.OwnerId = Owner;
  F.Name = Id;
  F.bIsHero = bHero;
  F.Health = F.MaxHealth = 5;
  F.X = X;
  F.Y = Y;
  F.Movement = Movement;
  return F;
}

int32 NearestEnemyManhattan(const TArray<FS08BoardFighter>& Fighters, const FS08BoardFighter& Mover) {
  int32 Best = MAX_int32;
  for (const FS08BoardFighter& E : Fighters) {
    if (E.OwnerId == Mover.OwnerId || !E.IsAlive()) continue;
    Best = FMath::Min(Best, FMath::Abs(E.X - Mover.X) + FMath::Abs(E.Y - Mover.Y));
  }
  return Best;
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtAutoApproachTest,
    "Unmatched.S08.BoardArt.AutoApproach S09AUTO multi-step approach leaves a boxed-in start and reaches melee range",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtAutoApproachTest::RunTest(const FString&) {
  // 1. T. Rex art fixture, the T3.2 attempt layout.
  TSharedPtr<FJsonValue> State;
  FString BoardId;
  FS08BoardExpect Summary;
  if (!TestTrue(TEXT("T. Rex fixture -> boardState"),
                FixtureBoardState(FPaths::Combine(FixtureDir(), TEXT("t-rex-paddock.art-fixture.json")), State,
                                  BoardId, Summary))) {
    return false;
  }
  FS08BoardModel Board;
  if (!TestTrue(TEXT("T. Rex decode"), Board.Decode(State))) return false;
  TestTrue(TEXT("(3,2) is the obstacle next to Medusa"), Board.CellAt(3, 2) && !Board.CellAt(3, 2)->IsPassable());
  TArray<FS08BoardFighter> Fighters = {
      ApproachFighter(TEXT("f-0-hero"), TEXT("A"), true, 2, 2, 3),
      ApproachFighter(TEXT("f-0-sk0"), TEXT("A"), false, 2, 3, 3),
      ApproachFighter(TEXT("f-0-sk1"), TEXT("A"), false, 2, 1, 3),
      ApproachFighter(TEXT("f-0-sk2"), TEXT("A"), false, 1, 2, 3),
      ApproachFighter(TEXT("f-1-hero"), TEXT("B"), true, 4, 2, 3),
      ApproachFighter(TEXT("f-1-sk0"), TEXT("B"), false, 5, 2, 3)};
  // The old one-cell driver's dead end: no orthogonal neighbour is a legal endpoint.
  const TSet<uint64> Reach1 = FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("f-0-hero"), 1);
  TestEqual(TEXT("one-step reach = own cell only (old greedy dead end)"), Reach1.Num(), 1);
  int32 Maneuvers = 0;
  int32 LastDist = MAX_int32;
  for (; Maneuvers < 4; ++Maneuvers) {
    FS08BoardFighter& Hero = Fighters[0];
    if (NearestEnemyManhattan(Fighters, Hero) == 1) break;
    FIntPoint Dest;
    int32 From = 0, To = 0, Steps = 0;
    if (!TestTrue(FString::Printf(TEXT("maneuver %d picks an improving destination"), Maneuvers + 1),
                  FS08BoardModel::PickApproachDestination(Board, Fighters, Hero.Id, Hero.Movement, Dest, From,
                                                          To, Steps))) {
      return false;
    }
    TestTrue(TEXT("strictly closer"), To < From);
    TestTrue(TEXT("never farther than the previous maneuver"), From <= LastDist);
    TestTrue(TEXT("within movement"), Steps >= 1 && Steps <= Hero.Movement);
    TestTrue(TEXT("a legal endpoint (the draft's SetDestination rule)"),
             FS08BoardModel::ComputeReachableCells(Board, Fighters, Hero.Id, Hero.Movement)
                 .Contains(FS08BoardModel::CellKey(Dest.X, Dest.Y)));
    TArray<FIntPoint> Path;
    TestTrue(TEXT("a legal route exists"),
             FS08BoardModel::BuildManeuverPath(Board, Fighters, Hero.Id, Hero.Movement, Dest.X, Dest.Y, Path) &&
                 Path.Num() == Steps);
    LastDist = To;
    Hero.X = Dest.X;
    Hero.Y = Dest.Y;
  }
  TestEqual(TEXT("Medusa reaches melee range of an enemy (static enemies)"),
            NearestEnemyManhattan(Fighters, Fighters[0]), 1);
  TestTrue(TEXT("within 3 maneuvers"), Maneuvers <= 3);
  {
    FIntPoint Dest;
    int32 From = 0, To = 0, Steps = 0;
    TestFalse(TEXT("already adjacent: no improving step, the hero stays"),
              FS08BoardModel::PickApproachDestination(Board, Fighters, TEXT("f-0-hero"), 3, Dest, From, To, Steps));
    TestEqual(TEXT("adjacent = terrain distance 1"), From, 1);
  }

  // 2. Open 5x6 board: deterministic tie-break (lower steps, then Y, then X).
  FS08BoardModel Open = MakeBoard(5, 6);
  TArray<FS08BoardFighter> Duel = {ApproachFighter(TEXT("h"), TEXT("A"), true, 0, 0, 2),
                                   ApproachFighter(TEXT("e"), TEXT("B"), true, 4, 5, 2)};
  FIntPoint Dest;
  int32 From = 0, To = 0, Steps = 0;
  TestTrue(TEXT("open board picks"),
           FS08BoardModel::PickApproachDestination(Open, Duel, TEXT("h"), 2, Dest, From, To, Steps));
  TestEqual(TEXT("open board: from 9"), From, 9);
  TestEqual(TEXT("open board: to 7"), To, 7);
  TestEqual(TEXT("open board: two steps"), Steps, 2);
  TestTrue(FString::Printf(TEXT("open board: (2,0), (1,1), (0,2) tie at 7 in 2 steps -> lowest Y = (2,0), got (%d,%d)"), Dest.X, Dest.Y),
           Dest == FIntPoint(2, 0));

  // 3. No enemy reachable through terrain (wall column) -> false.
  FS08BoardModel Walled = MakeBoard(5, 6);
  for (int32 Y = 0; Y < 6; ++Y) Walled.Cells[Y * 5 + 2].Type = ES08CellType::Wall;
  TestFalse(TEXT("walled off: nothing improves"),
            FS08BoardModel::PickApproachDestination(Walled, Duel, TEXT("h"), 2, Dest, From, To, Steps));
  return true;
}


// ---- W5b-R (advisor decisions D-2/D-3/D-4, docs/game-design/decisions/2026-09-29-board-readability-decisions.md)
namespace {
/** The four corners (XY, uu) of one cube piece: the engine cube (+-50) scaled, yawed, translated. */
TArray<FVector2D> PieceCorners(const FTransform& T) {
  TArray<FVector2D> Out;
  for (const FVector& C : {FVector(-50, -50, 0), FVector(50, -50, 0), FVector(50, 50, 0), FVector(-50, 50, 0)}) {
    const FVector W = T.TransformPosition(C);
    Out.Add(FVector2D(W.X, W.Y));
  }
  return Out;
}

double PointSegmentDistance(const FVector2D& P, const FVector2D& A, const FVector2D& B) {
  const FVector2D AB = B - A;
  const double Len2 = AB.SizeSquared();
  const double T = Len2 > 0.0 ? FMath::Clamp(FVector2D::DotProduct(P - A, AB) / Len2, 0.0, 1.0) : 0.0;
  return FVector2D::Distance(P, A + AB * T);
}

bool SegmentsIntersect(const FVector2D& A, const FVector2D& B, const FVector2D& C, const FVector2D& D) {
  auto Cross = [](const FVector2D& O, const FVector2D& X, const FVector2D& Y) {
    return (X.X - O.X) * (Y.Y - O.Y) - (X.Y - O.Y) * (Y.X - O.X);
  };
  const double D1 = Cross(C, D, A), D2 = Cross(C, D, B), D3 = Cross(A, B, C), D4 = Cross(A, B, D);
  return ((D1 > 0) != (D2 > 0)) && ((D3 > 0) != (D4 > 0));
}

/** Min distance between a convex quad and a segment (0 when they touch or cross). */
double QuadSegmentDistance(const TArray<FVector2D>& Q, const FVector2D& A, const FVector2D& B) {
  double Best = TNumericLimits<double>::Max();
  for (int32 I = 0; I < Q.Num(); ++I) {
    const FVector2D& P0 = Q[I];
    const FVector2D& P1 = Q[(I + 1) % Q.Num()];
    if (SegmentsIntersect(P0, P1, A, B)) return 0.0;
    Best = FMath::Min(Best, FMath::Min(PointSegmentDistance(P0, A, B), PointSegmentDistance(P1, A, B)));
    Best = FMath::Min(Best, FMath::Min(PointSegmentDistance(A, P0, P1), PointSegmentDistance(B, P0, P1)));
  }
  return Best;
}

const ES08ZoneGlyph AllGlyphs[] = {ES08ZoneGlyph::Diamond, ES08ZoneGlyph::Bar1,  ES08ZoneGlyph::Bars2,
                                   ES08ZoneGlyph::Bars3,   ES08ZoneGlyph::HBars2, ES08ZoneGlyph::Square,
                                   ES08ZoneGlyph::Cross,   ES08ZoneGlyph::X,      ES08ZoneGlyph::Tee,
                                   ES08ZoneGlyph::Chevron, ES08ZoneGlyph::Ring};
const ES08ZoneStroke AllStrokes[] = {ES08ZoneStroke::Solid, ES08ZoneStroke::Dash2, ES08ZoneStroke::Dash3,
                                     ES08ZoneStroke::Dash4, ES08ZoneStroke::Dots5, ES08ZoneStroke::Double,
                                     ES08ZoneStroke::DashDot};

double MaxRadialExtent(const FTransform& T) {
  double Out = 0.0;
  for (const FVector2D& C : PieceCorners(T)) Out = FMath::Max(Out, FMath::Max(FMath::Abs(C.X), FMath::Abs(C.Y)));
  return Out;
}
}  // namespace

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtTeamRingTest,
    "Unmatched.S08.BoardArt.TeamRing W5b-R team ring: above the marks, clear of the target arcs and the zone glyphs, meshes = spec",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtTeamRingTest::RunTest(const FString&) {
  using namespace S08TeamRingSpec;
  // 1) height: above every zone mark (glyph fill top 0.58) and the tile top z = 0 (T5.2 z-fighting)
  const float GlyphTop = S08ZoneMarkSpec::GlyphZ + S08ZoneMarkSpec::GlyphDepth * 50.0f;
  TestTrue(FString::Printf(TEXT("ring zMin %.2f >= 0.5"), ZMin), ZMin >= 0.5f);
  TestTrue(FString::Printf(TEXT("ring zMin %.2f above the glyph fill top %.2f"), ZMin, GlyphTop), ZMin > GlyphTop);
  TestTrue("ring zMax 1.2 below the L-corners (1.8) and the selection/target rings (2.2)", ZMax < 1.8f);
  // 2) fill band vs the target arcs (outer 23 uu) and the selection ring (outer 20 uu), both scaled like the ring
  TestTrue(FString::Printf(TEXT("P1 fill inner %.1f > target arcs outer %.1f"), P1Fill0, TargetArcOuterUU),
           P1Fill0 > TargetArcOuterUU);
  TestTrue(FString::Printf(TEXT("P2 fill inner apothem %.1f >= target arcs outer %.1f (touch at the flats only)"), P2Fill0,
                           TargetArcOuterUU),
           P2Fill0 >= TargetArcOuterUU);
  TestTrue("selection ring outer inside the keyline", SelectionRingOuterUU < FMath::Min(P1KeylineIn0, P2KeylineIn0));
  // 5c-B1 B1-3 (plan rev 2): outer keyline as wide as r3 (P1 1.5, P2 1.0), rim 1.0, the fill pays for the rim
  // (P1 2.5, P2 2.25); tools/art/t5cb1_ring_sim.py check holds the same rules
  TestTrue("band widths: keyline in 1.5, fill 2.5 / 2.25, keyline out 1.5 / 1.0 (r3), rim 1.0",
           FMath::IsNearlyEqual(P1Fill0 - P1KeylineIn0, 1.5f) && FMath::IsNearlyEqual(P1Fill1 - P1Fill0, 2.5f) &&
               FMath::IsNearlyEqual(P1KeylineOut1 - P1Fill1, 1.5f) && FMath::IsNearlyEqual(P1RimOut1 - P1KeylineOut1, 1.0f) &&
               FMath::IsNearlyEqual(P2Fill0 - P2KeylineIn0, 1.5f) && FMath::IsNearlyEqual(P2Fill1 - P2Fill0, 2.25f) &&
               FMath::IsNearlyEqual(P2KeylineOut1 - P2Fill1, 1.0f) && FMath::IsNearlyEqual(P2RimOut1 - P2KeylineOut1, 1.0f));
  TestTrue("FigureScreenRect radius = the outer ring edge (rim)", FMath::IsNearlyEqual(HeroRectRadiusUU, P1RimOut1));
  // 3) clearance to the zone glyphs: outer ring edge + 1 uu <= the nearest glyph FILL piece (exact rotated rects of
  //    S08GlyphPieces in all four slots; the glyph AABB would over-count the diamond), for heroes and sidekicks
  for (const ES08TeamSlot Slot : {ES08TeamSlot::P1, ES08TeamSlot::P2}) {
    TArray<TPair<FVector2D, FVector2D>> Edges;
    OuterEdges(Slot, Edges);
    for (const float Scale : {1.0f, SidekickScale}) {
      double Nearest = TNumericLimits<double>::Max();
      FString Where;
      for (const ES08ZoneGlyph G : AllGlyphs) {
        for (int32 GlyphSlot = 0; GlyphSlot < 4; ++GlyphSlot) {
          TArray<FTransform> Pieces;
          S08GlyphPieces(G, GlyphSlot, Pieces);
          for (const FTransform& Piece : Pieces) {
            const TArray<FVector2D> Q = PieceCorners(Piece);
            for (const TPair<FVector2D, FVector2D>& E : Edges) {
              const double D = QuadSegmentDistance(Q, E.Key * Scale, E.Value * Scale);
              if (D < Nearest) {
                Nearest = D;
                Where = FString::Printf(TEXT("%s slot %d"), S08ZoneGlyphName(G), GlyphSlot);
              }
            }
          }
        }
      }
      AddInfo(FString::Printf(TEXT("%s scale %.2f: nearest glyph %s at %.2f uu"), S08TeamSlotName(Slot), Scale, *Where,
                              Nearest));
      TestTrue(FString::Printf(TEXT("%s scale %.2f: >= 1 uu to the nearest glyph (%s, %.2f)"), S08TeamSlotName(Slot),
                               Scale, *Where, Nearest),
               Nearest >= 1.0);
    }
  }
  // 4) the imported meshes = the spec (bounds, slots) and the MIs = the palette on the game-layer master
  for (const ES08TeamSlot Slot : {ES08TeamSlot::P1, ES08TeamSlot::P2}) {
    UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, MeshPath(Slot));
    if (!TestNotNull(FString(TEXT("mesh ")) + MeshPath(Slot), Mesh)) continue;
    const FBox B = Mesh->GetBoundingBox();
    TestTrue(FString::Printf(TEXT("%s z %.2f..%.2f"), S08TeamSlotName(Slot), B.Min.Z, B.Max.Z),
             FMath::IsNearlyEqual(B.Min.Z, ZMin, 0.01) && FMath::IsNearlyEqual(B.Max.Z, ZMax, 0.01));
    const double Reach = Slot == ES08TeamSlot::P1 ? P1RimOut1 : P2RimOut1;
    TestTrue(FString::Printf(TEXT("%s XY reach %.2f / %.2f"), S08TeamSlotName(Slot), B.Max.Y, Reach),
             FMath::IsNearlyEqual(B.Max.Y, Reach, 0.02) && FMath::IsNearlyEqual(-B.Min.Y, Reach, 0.02));
    const TArray<FStaticMaterial>& Slots = Mesh->GetStaticMaterials();
    if (TestEqual(FString(S08TeamSlotName(Slot)) + TEXT(": three material slots"), Slots.Num(), 3)) {
      TestTrue(FString(S08TeamSlotName(Slot)) + TEXT(": slots Keyline / Fill / Rim in this order"),
               Slots[0].MaterialSlotName == FName(TEXT("Keyline")) && Slots[1].MaterialSlotName == FName(TEXT("Fill")) &&
                   Slots[2].MaterialSlotName == FName(TEXT("Rim")));
      TestTrue(FString(S08TeamSlotName(Slot)) + TEXT(": slot 2 = MI_Marker_TeamRing_Rim"),
               Slots[2].MaterialInterface && Slots[2].MaterialInterface->GetName() == TEXT("MI_Marker_TeamRing_Rim"));
    }
#if WITH_EDITOR
    TestFalse(FString(S08TeamSlotName(Slot)) + TEXT(": Nanite off"), Mesh->IsNaniteEnabled());
#endif
  }
  for (const TCHAR* Path : {KeylineMaterialPath, FillMaterialPath, RimMaterialPath}) {
    UMaterialInstance* MI = LoadObject<UMaterialInstance>(nullptr, Path);
    if (!TestNotNull(FString(TEXT("MI ")) + Path, MI)) continue;
    TestTrue(FString(Path) + TEXT(": parent M_UM_GameLayer"),
             MI->Parent && MI->Parent->GetPathName() == TEXT("/Game/UM/Materials/M_UM_GameLayer.M_UM_GameLayer"));
    FLinearColor Got;
    MI->GetVectorParameterValue(FHashedMaterialParameterInfo(TEXT("LayerColor")), Got);
    const FLinearColor Want = Path == KeylineMaterialPath ? S08TeamPalette::Keyline()
                              : Path == RimMaterialPath     ? S08TeamPalette::Rim()
                                                            : S08TeamPalette::RingFill(ES08TeamSlot::P1);
    TestTrue(FString::Printf(TEXT("%s LayerColor %s == %s"), Path, *Got.ToString(), *Want.ToString()),
             Got.Equals(Want, 1e-5f));
  }
  // 5) an art figure (the grey blockout of Arthur) shows the team ring and hides the grey base disc; P2 = hexagon
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08BoardArtTeamRing")));
  if (TestNotNull("test world", World)) {
    FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
    Context.SetCurrentWorld(World);
    AS08FighterActor* Actor = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass());
    if (TestNotNull("fighter actor", Actor)) {
      TestTrue("team ring assets load", Actor->LoadTeamRingAssets());
      FS08BoardFighter F;
      F.Id = TEXT("f-1-hero");
      F.OwnerId = TEXT("guest");
      F.Name = TEXT("King Arthur");
      F.Label = TEXT("King Arthur");
      F.bIsHero = true;
      F.Health = F.MaxHealth = 18;
      F.X = 1;
      F.Y = 1;
      Actor->SetTeam(ES08TeamSlot::P2, ES08TeamSlot::P2, ES08TeamColorMode::Absolute);
      Actor->ApplyFighter(F, FVector::ZeroVector, false, true);
      TestTrue("blockout = art figure", Actor->HasArtFigure() && Actor->IsBlockout());
      TestTrue("team ring shown", Actor->HasTeamRing() && Actor->IsTeamRingVisible());
      TestFalse("grey base disc hidden under an art figure", Actor->IsBaseVisible());
      TestTrue("P2 look = hexagon mesh", Actor->GetTeamRingMesh() &&
                                             Actor->GetTeamRingMesh()->GetName() == TEXT("SM_Marker_TeamRing_P2"));
      F.Id = TEXT("f-0-sk0");
      F.Name = TEXT("Harpies");
      F.bIsHero = false;
      AS08FighterActor* Side = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass());
      Side->LoadTeamRingAssets();
      Side->SetTeam(ES08TeamSlot::P1, ES08TeamSlot::P1, ES08TeamColorMode::Absolute);
      Side->ApplyFighter(F, FVector::ZeroVector, true, true);
      TestTrue("sidekick ring scaled 0.78 in XY only",
               Side->GetTeamRingScale().Equals(FVector(SidekickScale, SidekickScale, 1.0f), 1e-4));
      TestTrue("P1 look = circle mesh", Side->GetTeamRingMesh() &&
                                            Side->GetTeamRingMesh()->GetName() == TEXT("SM_Marker_TeamRing_P1"));
      // the grey path (no -ArtPreview board) keeps the disc
      AS08FighterActor* Grey = World->SpawnActor<AS08FighterActor>(AS08FighterActor::StaticClass());
      Grey->LoadTeamRingAssets();
      Grey->ApplyFighter(F, FVector::ZeroVector, true, false);
      TestTrue("grey path: base disc kept, no team ring", Grey->IsBaseVisible() && !Grey->IsTeamRingVisible());
    }
    GEngine->DestroyWorldContext(World);
    World->DestroyWorld(false);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtKeylineTest,
    "Unmatched.S08.BoardArt.Keylines W5b-R zone keylines: strokes + keylines <= 45 uu, layering, double gap, data, content",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtKeylineTest::RunTest(const FString&) {
  using namespace S08ZoneMarkSpec;
  // 1) every stroke type on every side: fill and keyline stay within MaxOuterUU (1 uu inside the 46-uu slab edge)
  for (const ES08ZoneStroke Stroke : AllStrokes) {
    for (int32 Side = 0; Side < 4; ++Side) {
      TArray<FTransform> Fill, Key;
      S08StrokePieces(Stroke, Side, Fill);
      S08StrokeKeylinePieces(Stroke, Side, Key);
      if (!TestEqual(FString::Printf(TEXT("%s side %d: one keyline piece per fill piece"), S08ZoneStrokeName(Stroke), Side),
                     Key.Num(), Fill.Num())) {
        continue;
      }
      double Outer = 0.0, KeyOuter = 0.0;
      for (int32 I = 0; I < Fill.Num(); ++I) {
        Outer = FMath::Max(Outer, MaxRadialExtent(Fill[I]));
        KeyOuter = FMath::Max(KeyOuter, MaxRadialExtent(Key[I]));
        const FVector Grow = Key[I].GetScale3D() - Fill[I].GetScale3D();
        TestTrue(FString::Printf(TEXT("%s: keyline grown 1.5 uu per side"), S08ZoneStrokeName(Stroke)),
                 FMath::IsNearlyEqual(Grow.X, 0.03, 1e-5) && FMath::IsNearlyEqual(Grow.Y, 0.03, 1e-5));
        TestTrue(FString::Printf(TEXT("%s: keyline under the fill"), S08ZoneStrokeName(Stroke)),
                 Key[I].GetTranslation().Z + Key[I].GetScale3D().Z * 50.0 <
                     Fill[I].GetTranslation().Z + Fill[I].GetScale3D().Z * 50.0 - 0.1);
      }
      // the across-extent of a side (distance from the centre perpendicular to the side) must be <= 45
      double Across = 0.0;
      for (const FTransform& K : Key) {
        for (const FVector2D& C : PieceCorners(K)) Across = FMath::Max(Across, Side % 2 ? FMath::Abs(C.X) : FMath::Abs(C.Y));
      }
      TestTrue(FString::Printf(TEXT("%s side %d: keyline across-extent %.2f <= %.1f"), S08ZoneStrokeName(Stroke), Side,
                               Across, MaxOuterUU),
               Across <= MaxOuterUU + 1e-3);
      TestTrue(FString::Printf(TEXT("%s: centre line <= 42"), S08ZoneStrokeName(Stroke)),
               S08ZoneStrokeCenterUU(Stroke) <= EdgeUU + 1e-4);
      (void)Outer;
      (void)KeyOuter;
    }
  }
  // 2) the double stroke: two 3-uu lines, a 3-uu gap exactly filled by the two keylines (1.5 + 1.5)
  {
    TArray<FTransform> Fill, Key;
    S08StrokePieces(ES08ZoneStroke::Double, 0, Fill);
    S08StrokeKeylinePieces(ES08ZoneStroke::Double, 0, Key);
    if (TestEqual("double: two lines", Fill.Num(), 2)) {
      const double Y0 = Fill[0].GetTranslation().Y, Y1 = Fill[1].GetTranslation().Y;
      const double Thick = Fill[0].GetScale3D().Y * 100.0;
      TestTrue("double: 3-uu lines", FMath::IsNearlyEqual(Thick, 3.0, 1e-3));
      TestTrue("double: 3-uu gap", FMath::IsNearlyEqual(FMath::Abs(Y1 - Y0) - Thick, 3.0, 1e-3));
      const double KeyInner0 = FMath::Min(Y0, Y1) + Key[0].GetScale3D().Y * 50.0;
      const double KeyInner1 = FMath::Max(Y0, Y1) - Key[1].GetScale3D().Y * 50.0;
      TestTrue("double: the keylines meet in the gap", KeyInner0 >= KeyInner1 - 1e-3);
    }
  }
  // 3) layering of the top faces: stroke keyline < stroke fill < glyph keyline < glyph fill < team ring
  const float StrokeKeyTop = StrokeKeylineZ + KeylineDepth * 50.0f, StrokeTop = StrokeZ + StrokeDepth * 50.0f;
  const float GlyphKeyTop = GlyphZ + KeylineDepth * 50.0f, GlyphTop = GlyphZ + GlyphDepth * 50.0f;
  TestTrue(FString::Printf(TEXT("layering %.2f < %.2f < %.2f < %.2f < %.2f"), StrokeKeyTop, StrokeTop, GlyphKeyTop,
                           GlyphTop, S08TeamRingSpec::ZMin),
           StrokeKeyTop + 0.05f <= StrokeTop + 1e-4f && StrokeTop + 0.05f <= GlyphKeyTop + 1e-4f &&
               GlyphKeyTop + 0.05f <= GlyphTop + 1e-4f && GlyphTop < S08TeamRingSpec::ZMin);
  // 4) glyph FILL stays on the slab (<= 46 uu); glyph keylines may reach into the dark groove (dark on dark)
  for (const ES08ZoneGlyph G : AllGlyphs) {
    for (int32 Slot = 0; Slot < 4; ++Slot) {
      TArray<FTransform> Fill;
      S08GlyphPieces(G, Slot, Fill);
      double Outer = 0.0;
      for (const FTransform& T : Fill) Outer = FMath::Max(Outer, MaxRadialExtent(T));
      TestTrue(FString::Printf(TEXT("glyph %s slot %d fill %.2f <= slab %.0f"), S08ZoneGlyphName(G), Slot, Outer,
                               SlabHalfUU),
               Outer <= SlabHalfUU + 1e-3);
    }
  }
  // 5) the layout: keylines are never part of the zone counts (legacy Cobble trace byte-compatible)
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", LoadShipped(Data, Errors))) return false;
  const FS08BoardModel Board = CobbleBoard();
  const FS08ZoneMarkLayout L = S08BuildZoneMarks(Board, Data);
  TestEqual("stroke keylines = stroke pieces", L.StrokeKeylines.Num(), L.Strokes.Num());
  TestEqual("glyph keylines = glyph pieces", L.GlyphKeylines.Num(), L.Glyphs.Num());
  TestEqual("blueMarks unchanged", L.StrokePiecesByKey.FindRef(TEXT("blue")), 15);
  TestEqual("redMarks unchanged", L.StrokePiecesByKey.FindRef(TEXT("red")), 45);
  // 6) the data (profile rev 4; rev 5 = 5c-B1 zone colours) and the content
  TestTrue("revision >= 5", Data.Revision >= 5);
  TestTrue("zoneKeyline block", Data.Keyline.bSet && Data.Keyline.Color == FColor(17, 19, 23, 255));
  TestEqual("gray -> #6B727A (5c-B1 rev 5; rev 4 #7F868E, D-4)", Data.StyleFor(TEXT("gray")).ColorHex(), FString(TEXT("#6B727A")));
  TestEqual("red -> #EC6650 (5c-B1 rev 5; rev 4 #D8453B)", Data.StyleFor(TEXT("red")).ColorHex(), FString(TEXT("#EC6650")));
  TestEqual("keyline mesh per glyph", Data.Keyline.GlyphMeshPaths.Num(), 11);
  UMaterialInstance* KeyMI = LoadObject<UMaterialInstance>(nullptr, *Data.Keyline.MaterialInstancePath);
  if (TestNotNull(TEXT("keyline MI ") + Data.Keyline.MaterialInstancePath, KeyMI)) {
    FLinearColor Got;
    KeyMI->GetVectorParameterValue(FHashedMaterialParameterInfo(TEXT("LayerColor")), Got);
    TestTrue(FString::Printf(TEXT("keyline LayerColor %s = FromSRGBColor(#111317)"), *Got.ToString()),
             Got.Equals(FLinearColor::FromSRGBColor(FColor(17, 19, 23)), 1e-5f));
  }
  for (const TPair<FString, FString>& Path : Data.Keyline.GlyphMeshPaths) {
    ES08ZoneGlyph G;
    if (!TestTrue(Path.Key + TEXT(": glyph name"), S08ParseZoneGlyph(Path.Key, G))) continue;
    UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, *Path.Value);
    if (!TestNotNull(Path.Key + TEXT(": keyline mesh ") + Path.Value, Mesh)) continue;
    TArray<FTransform> Pieces;
    S08GlyphKeylinePieces(G, 0, Pieces);
    FBox Want(ForceInit);
    for (const FTransform& T : Pieces) {
      for (int32 C = 0; C < 8; ++C) {
        const FVector Corner((C & 1) ? 50.0 : -50.0, (C & 2) ? 50.0 : -50.0, (C & 4) ? 50.0 : -50.0);
        Want += T.TransformPosition(Corner) - S08GlyphAnchor(0);
      }
    }
    const FBox Got = Mesh->GetBoundingBox();
    TestTrue(FString::Printf(TEXT("%s: keyline mesh bounds %s == pieces %s"), *Path.Key, *Got.ToString(), *Want.ToString()),
             Got.Min.Equals(Want.Min, 0.01) && Got.Max.Equals(Want.Max, 0.01));
  }
  return true;
}

// ---- ENV-MAPS track S: the 'map-image' surface of the original maps (docs/art-pipeline/ENV-MAPS-PLAN.md) --------
namespace S08MapTest {
FString TopologyFixtureDir() {
  return FPaths::ConvertRelativePathToFull(
      FPaths::Combine(FPaths::ProjectDir(), TEXT("../../backend/prisma/fixtures/boards")));
}

/** Topology fixture (unmatched.board-topology/1, flat backend Board.cells) -> the boardState projection that
 *  buildBoardState sends: rows cells[y][x] with type normal/obstacle, zones + zone, and the space fields
 *  spaceId / layout / start / links copied as they are. */
bool TopologyBoardState(const FString& File, TSharedPtr<FJsonValue>& OutState, FString& OutBoardId,
                        TSharedPtr<FJsonObject>& OutRoot) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *File)) return false;
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(Text, Root, Problem) || !Root.IsValid()) return false;
  OutRoot = Root;
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
  OutState = MakeShared<FJsonValueObject>(State);
  return true;
}

/** 3 x 2 lattice: spaces T01 (0,0) / T02 (1,0) / T03 (2,1) at map px (200,200) / (500,200) / (800,500), linked
 *  T01-T02-T03 (T01 and T03 are lattice-far, T02-T03 is a diagonal link), zones a / a+b / b, starts 1 and 2;
 *  the other three cells are obstacles. */
const TCHAR* SyntheticTopologyJson = TEXT(
    "{\"width\":3,\"height\":2,\"doors\":{},\"cells\":["
    "[{\"type\":\"normal\",\"x\":0,\"y\":0,\"zones\":[\"a\"],\"zone\":\"a\",\"spaceId\":\"T01\",\"layout\":{\"x\":200,\"y\":200},"
    "\"start\":1,\"links\":[{\"x\":1,\"y\":0}]},"
    "{\"type\":\"normal\",\"x\":1,\"y\":0,\"zones\":[\"a\",\"b\"],\"zone\":\"a\",\"spaceId\":\"T02\",\"layout\":{\"x\":500,\"y\":200},"
    "\"links\":[{\"x\":0,\"y\":0},{\"x\":2,\"y\":1}]},"
    "{\"type\":\"obstacle\",\"x\":2,\"y\":0}],"
    "[{\"type\":\"obstacle\",\"x\":0,\"y\":1},{\"type\":\"obstacle\",\"x\":1,\"y\":1},"
    "{\"type\":\"normal\",\"x\":2,\"y\":1,\"zones\":[\"b\"],\"zone\":\"b\",\"spaceId\":\"T03\",\"layout\":{\"x\":800,\"y\":500},"
    "\"start\":2,\"links\":[{\"x\":1,\"y\":0}]}]]}");

bool SyntheticTopology(FS08BoardModel& Out) {
  TSharedPtr<FJsonObject> Obj;
  FString Problem;
  if (!FS08Contracts::TryParseJsonObject(SyntheticTopologyJson, Obj, Problem) || !Obj.IsValid()) return false;
  return Out.Decode(MakeShared<FJsonValueObject>(Obj));
}

/** MinimalDoc + one map-image board ("map", Board row id cidMap) whose assets do not exist. */
const TCHAR* MapBoardJson = TEXT(
    ",{\"id\":\"map\",\"match\":{\"boardIds\":[\"cidMap\"]},\"surface\":\"map-image\",\"light\":\"L\","
    "\"mapImage\":{\"name\":\"NoSuchTest\",\"bc\":\"/Game/EnvMaps/NoSuchTest/T_NoSuchTest_Map_BC_4K\","
    "\"mask\":\"/Game/EnvMaps/NoSuchTest/T_NoSuchTest_Map_GameMask_4K\",\"sdf\":\"/Game/EnvMaps/NoSuchTest/T_NoSuchTest_Map_GameSDF_4K\","
    "\"id\":\"/Game/EnvMaps/NoSuchTest/T_NoSuchTest_Map_SpaceID_4K\",\"materialInstance\":\"/Game/EnvMaps/NoSuchTest/MI_NoSuchTest_MapBoard\","
    "\"srcSize\":[1337,866],\"uuPerPx\":0.6666667,\"frameUU\":24,\"trayOffsetUU\":[10,-20]},"
    "\"expect\":{\"spaces\":3,\"links\":2,\"zones\":[\"b\",\"a\"],\"multizoneCells\":1}}");

FString MapDoc() {
  FString Doc = MinimalDoc;
  Doc.RemoveFromEnd(TEXT("]}"));
  return Doc + MapBoardJson + TEXT("]}");
}

const FVector2D MapHalf(445.66667, 288.66667);  // 1337 x 866 px at 2/3 uu per px, halved
}  // namespace S08MapTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapImageParserTest,
    "Unmatched.S08.BoardArt.MapImageParser map-image surface: the mapImage block, id-only match, space-graph expect",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMapImageParserTest::RunTest(const FString&) {
  using namespace S08MapTest;
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue(TEXT("map doc parses: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(MapDoc(), Errors))) {
    return false;
  }
  const FS08BoardArtProfile* P = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("map"); });
  if (!TestNotNull("map profile", P)) return false;
  TestTrue("surface map-image", P->Surface == ES08BoardSurface::MapImage);
  TestEqual("surface name", FString(S08BoardSurfaceName(P->Surface)), FString(TEXT("map-image")));
  const FS08MapImageSpec& M = P->Map;
  TestTrue("mapImage parsed", M.bSet && M.Name == TEXT("NoSuchTest"));
  TestEqual("bc path", M.BaseColorPath, FString(TEXT("/Game/EnvMaps/NoSuchTest/T_NoSuchTest_Map_BC_4K")));
  TestEqual("mi path", M.MaterialInstancePath, FString(TEXT("/Game/EnvMaps/NoSuchTest/MI_NoSuchTest_MapBoard")));
  TestEqual("five asset paths", M.AssetPaths().Num(), 5);
  TestTrue("srcSize", M.SrcSizePx == FIntPoint(1337, 866));
  TestTrue("uuPerPx = the layout frame default", M.MatchesDefaultLayoutFrame());
  TestTrue(FString::Printf(TEXT("size %s = 891.333 x 577.333"), *M.SizeUU().ToString()),
           M.SizeUU().Equals(FVector2D(891.3333, 577.3333), 0.01));
  TestTrue("frame half = map half + 24", M.FrameHalfUU().Equals(MapHalf + FVector2D(24.0, 24.0), 0.01));
  TestTrue("tray offset", M.TrayOffsetUU.Equals(FVector2D(10.0, -20.0), 1e-6));
  TestTrue("expect spaces/links", P->Expect.Spaces == 3 && P->Expect.Links == 2);
  TestTrue("expect zones sorted", P->Expect.Zones == TArray<FString>({TEXT("a"), TEXT("b")}));
  TestTrue("no W x H expect", P->Expect.Cells < 0);
  // Selection: the topology board by id only; the grid profile "one" (3x2, {a,b}) never signature-matches it.
  FS08BoardModel Topo;
  if (TestTrue("synthetic topology board decodes", SyntheticTopology(Topo))) {
    TestTrue("synthetic board has topology", Topo.bHasTopology);
    ES08ProfileMatch Match;
    const FS08BoardArtProfile* ById = Data.Select(Topo, TEXT("cidMap"), Match);
    TestTrue("topology board by id -> map", ById && ById->Id == TEXT("map") && Match == ES08ProfileMatch::BoardId);
    TestNull("topology board without id -> no profile (no signature)", Data.Select(Topo, FString(), Match));
    TestNull("topology board, unknown id -> no profile", Data.Select(Topo, TEXT("other"), Match));
    if (ById) {
      const FS08BoardSummary S = S08SummarizeBoard(Topo);
      TestTrue(FString::Printf(TEXT("summary spaces=%d links=%d starts=%d"), S.Spaces, S.Links, S.Starts),
               S.bTopology && S.Spaces == 3 && S.Links == 2 && S.Starts == 2);
      TestEqual("expect met", S08ExpectMismatch(*ById, S), FString());
      FS08BoardArtProfile Wrong = *ById;
      Wrong.Expect.Links = 3;
      Wrong.Expect.Zones = {TEXT("a"), TEXT("c")};
      const FString Mismatch = S08ExpectMismatch(Wrong, S);
      TestTrue(TEXT("links / zones mismatch reported: ") + Mismatch,
               Mismatch.Contains(TEXT("links 2!=3")) && Mismatch.Contains(TEXT("zones a+b!=a+c")));
    }
  }
  FS08BoardModel Grid = MakeBoard(3, 2);
  for (FS08Cell& Cell : Grid.Cells) Cell.Zones = {Cell.X == 0 ? TEXT("a") : TEXT("b")};
  ES08ProfileMatch GridMatch;
  const FS08BoardArtProfile* GridProfile = Data.Select(Grid, FString(), GridMatch);
  TestTrue("a 3x2 grid still signature-matches the grid profile", GridProfile && GridProfile->Id == TEXT("one"));
  const FS08BoardArtProfile* GridById = Data.Select(Grid, TEXT("cidMap"), GridMatch);
  TestTrue("a grid carrying the map's row id still selects it by id (the board actor refuses: no topology)",
           GridById && GridById->Id == TEXT("map") && GridMatch == ES08ProfileMatch::BoardId);
  // Broken map-image boards reject the document.
  auto Expect = [this](const FString& Name, const FString& From, const FString& To, const FString& ErrorPart) {
    FString Doc = MapDoc();
    TestTrue(Name + TEXT(": patch applies"), Doc.Contains(From));
    Doc.ReplaceInline(*From, *To);
    FS08BoardArtData Broken;
    TArray<FString> Errs;
    TestFalse(Name + TEXT(": rejected"), Broken.ParseJson(Doc, Errs));
    TestTrue(Name + TEXT(": reason '") + ErrorPart + TEXT("' in ") + FString::Join(Errs, TEXT(" | ")),
             FString::Join(Errs, TEXT(" | ")).Contains(ErrorPart));
  };
  Expect(TEXT("no mapImage block"), TEXT("\"mapImage\":{"), TEXT("\"mapImageX\":{"), TEXT("needs a mapImage block"));
  Expect(TEXT("no board id"), TEXT("\"boardIds\":[\"cidMap\"]"), TEXT("\"boardIds\":[]"), TEXT("selected by id only"));
  Expect(TEXT("signature on a map"), TEXT("\"boardIds\":[\"cidMap\"]"), TEXT("\"boardIds\":[\"cidMap\"],\"width\":3,\"height\":2"),
         TEXT("no width/height/zoneKeys signature"));
  Expect(TEXT("asset outside /Game/EnvMaps"), TEXT("/Game/EnvMaps/NoSuchTest/T_NoSuchTest_Map_BC_4K"),
         TEXT("/Game/Other/T_BC"), TEXT("mapImage.bc"));
  Expect(TEXT("asset path with an object suffix"), TEXT("MI_NoSuchTest_MapBoard\""),
         TEXT("MI_NoSuchTest_MapBoard.MI_NoSuchTest_MapBoard\""), TEXT("mapImage.materialInstance"));
  Expect(TEXT("srcSize not whole px"), TEXT("\"srcSize\":[1337,866]"), TEXT("\"srcSize\":[1337.5,866]"), TEXT("mapImage.srcSize"));
  Expect(TEXT("uuPerPx 0"), TEXT("\"uuPerPx\":0.6666667"), TEXT("\"uuPerPx\":0"), TEXT("mapImage.uuPerPx"));
  Expect(TEXT("tray offset not a pair"), TEXT("\"trayOffsetUU\":[10,-20]"), TEXT("\"trayOffsetUU\":[10]"),
         TEXT("mapImage.trayOffsetUU"));
  Expect(TEXT("unknown surface"), TEXT("\"surface\":\"map-image\""), TEXT("\"surface\":\"map-photo\""), TEXT("unknown surface"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapProfilesTest,
    "Unmatched.S08.BoardArt.MapProfiles Marmoreal and Sarpedon topology fixtures decode to their map-image profiles",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMapProfilesTest::RunTest(const FString&) {
  using namespace S08MapTest;
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", LoadShipped(Data, Errors))) return false;
  TArray<FString> Files;
  IFileManager::Get().FindFiles(Files, *FPaths::Combine(TopologyFixtureDir(), TEXT("*.topology.json")), true, false);
  Files.Sort();
  if (!TestEqual(TEXT("two topology fixtures in ") + TopologyFixtureDir(), Files.Num(), 2)) return false;
  for (const FString& Name : Files) {
    TSharedPtr<FJsonValue> State;
    TSharedPtr<FJsonObject> Root;
    FString BoardId;
    if (!TestTrue(Name + TEXT(": fixture -> boardState"),
                  TopologyBoardState(FPaths::Combine(TopologyFixtureDir(), Name), State, BoardId, Root))) {
      continue;
    }
    FS08BoardModel Board;
    if (!TestTrue(Name + TEXT(": FS08BoardModel::Decode"), Board.Decode(State))) continue;
    TestTrue(Name + TEXT(": topology board"), Board.bHasTopology);
    ES08ProfileMatch Match;
    const FS08BoardArtProfile* P = Data.Select(Board, BoardId, Match);
    if (!TestTrue(Name + TEXT(": map-image profile by board id"),
                  P && Match == ES08ProfileMatch::BoardId && P->Surface == ES08BoardSurface::MapImage)) {
      continue;
    }
    TestNull(Name + TEXT(": no profile without the id"), Data.Select(Board, FString(), Match));
    const FS08BoardSummary S = S08SummarizeBoard(Board);
    TestEqual(Name + TEXT(": expect met"), S08ExpectMismatch(*P, S), FString());
    const TSharedPtr<FJsonObject> FixtureSummary = Root->GetObjectField(TEXT("summary"));
    TestEqual(Name + TEXT(": spaces = fixture"), S.Spaces, static_cast<int32>(FixtureSummary->GetNumberField(TEXT("spaces"))));
    TestEqual(Name + TEXT(": links = fixture edges"), S.Links, static_cast<int32>(FixtureSummary->GetNumberField(TEXT("edges"))));
    TestEqual(Name + TEXT(": four start spaces"), S.Starts, 4);
    // The figures stand on the painted circles: the client's CellToWorld (FS08LayoutFrame) == the map plane's
    // px -> world for every space, and every space lies on the map plane.
    const FS08MapImageSpec& M = P->Map;
    double Drift = 0.0;
    int32 Outside = 0, Hits = 0, Spaces = 0;
    for (int32 Y = 0; Y < Board.Height; ++Y) {
      for (int32 X = 0; X < Board.Width; ++X) {
        const FS08Cell* Cell = Board.CellAt(X, Y);
        if (!Cell || !Cell->bHasLayout) continue;
        ++Spaces;
        const FVector World = Board.CellToWorld(X, Y);
        Drift = FMath::Max(Drift, FVector::Dist(World, M.PxToWorld(Cell->Layout)));
        Outside += (FMath::Abs(World.X) > M.HalfUU().X || FMath::Abs(World.Y) > M.HalfUU().Y) ? 1 : 0;
        int32 HX = -1, HY = -1;
        Hits += (Board.WorldToCell(World + FVector(5.0, -5.0, 0.0), HX, HY) && HX == X && HY == Y) ? 1 : 0;
      }
    }
    TestTrue(FString::Printf(TEXT("%s: layout drift %.4f uu <= 0.01 (CellToWorld vs the map plane)"), *Name, Drift), Drift <= 0.01);
    TestEqual(Name + TEXT(": every space on the map plane"), Outside, 0);
    TestEqual(Name + TEXT(": a click 7 uu off a space centre picks that space (pick box -> WorldToCell)"), Hits, Spaces);
    // K1 fitted to the map (ENV-O10), not to the lattice.
    const FVector2D Half = S08BoardHalfExtentUU(Board);
    TestTrue(FString::Printf(TEXT("%s: board half extent %s = the map half"), *Name, *Half.ToString()), Half.Equals(M.HalfUU(), 0.01));
    const float K1 = S08K1FitDistanceUU(Half);
    TestTrue(FString::Printf(TEXT("%s: K1 distance %.2f = 1872 +- 1"), *Name, K1), FMath::Abs(K1 - 1872.0f) <= 1.0f);
    // Night light placeholder: spots scale by the MAP size and sit on / around the map, warm and cool present.
    const FS08LightProfile* Light = Data.LightFor(*P);
    if (TestNotNull(Name + TEXT(": light profile"), Light)) {
      const TArray<FS08PlacedLight> Placed = S08PlaceLights(*Light, M.SizeUU());
      int32 Warm = 0, Cool = 0;
      for (const FS08PlacedLight& Pl : Placed) {
        Warm += Pl.Spec.Role == TEXT("warm");
        Cool += Pl.Spec.Role == TEXT("cool");
        if (Pl.Spec.bDirectional || Pl.Spec.bHasPosUU) continue;
        TestTrue(FString::Printf(TEXT("%s: spot %s (%.0f,%.0f) within 1.2 x the map half"), *Name, *Pl.Spec.Name,
                                 Pl.Position.X, Pl.Position.Y),
                 FMath::Abs(Pl.Position.X) <= Half.X * 1.2 && FMath::Abs(Pl.Position.Y) <= Half.Y * 1.2);
      }
      TestTrue(Name + TEXT(": warm and cool spots"), Warm >= 1 && Cool >= 1);
      TestTrue(Name + TEXT(": budget"), Placed.Num() <= 7);
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapCameraTest,
    "Unmatched.S08.BoardArt.MapCamera K1 distance: grids unchanged (Cobble 1931), map canvas 1872",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMapCameraTest::RunTest(const FString&) {
  using namespace S08MapTest;
  // The pre-ENV-MAPS SetupCameraForBoard formula, verbatim: grids must keep the exact float.
  auto Legacy = [](int32 W, int32 H) {
    const float Hfov = 35.0f;
    const float Aspect = 16.0f / 9.0f;
    const float HalfH = FMath::Tan(FMath::DegreesToRadians(Hfov * 0.5f));
    const float HalfV = HalfH / Aspect;
    const float ExtentY = H * FS08BoardModel::CellSizeUU * 0.5f;
    const float ExtentX = W * FS08BoardModel::CellSizeUU * 0.5f;
    const float SinPitch = FMath::Sin(FMath::DegreesToRadians(55.0f));
    const float NeedV = (ExtentY * SinPitch + 60.0f) / HalfV;
    const float NeedH = (ExtentX + 60.0f) / HalfH;
    return FMath::Max(NeedV, NeedH) * 1.12f;
  };
  for (const FIntPoint Size : {FIntPoint(5, 6), FIntPoint(7, 6), FIntPoint(9, 6), FIntPoint(8, 5), FIntPoint(20, 20)}) {
    const FS08BoardModel Grid = MakeBoard(Size.X, Size.Y);
    const FVector2D Half = S08BoardHalfExtentUU(Grid);
    TestTrue(FString::Printf(TEXT("%dx%d grid half = W x H x 50"), Size.X, Size.Y),
             Half.Equals(FVector2D(Size.X * 50.0, Size.Y * 50.0), 1e-6));
    TestEqual(FString::Printf(TEXT("%dx%d grid K1 = the pre-ENV-MAPS formula"), Size.X, Size.Y), S08K1FitDistanceUU(Half),
              Legacy(Size.X, Size.Y));
  }
  TestTrue(FString::Printf(TEXT("Cobble 5x6 K1 %.1f = 1931 +- 1"), S08K1FitDistanceUU(S08BoardHalfExtentUU(MakeBoard(5, 6)))),
           FMath::Abs(S08K1FitDistanceUU(S08BoardHalfExtentUU(MakeBoard(5, 6))) - 1931.0f) <= 1.0f);
  FS08BoardModel Topo;
  if (TestTrue("synthetic topology board", SyntheticTopology(Topo))) {
    const FVector2D Half = S08BoardHalfExtentUU(Topo);
    TestTrue(FString::Printf(TEXT("topology half %s = the map canvas 445.667 x 288.667 (not the 3x2 lattice)"), *Half.ToString()),
             Half.Equals(MapHalf, 0.01));
    const float K1 = S08K1FitDistanceUU(Half);
    // tools/art/map_surface/manifest.<key>.json k1.camera.distance_uu = 1872.156 (the same formula in Python)
    TestTrue(FString::Printf(TEXT("map K1 %.3f = 1872.156 +- 0.5 (manifest) and 1872 +- 1"), K1),
             FMath::Abs(K1 - 1872.156f) <= 0.5f && FMath::Abs(K1 - 1872.0f) <= 1.0f);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapGeometryTest,
    "Unmatched.S08.BoardArt.MapGeometry map plane, reachable ring, grey discs / link bars and layering",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMapGeometryTest::RunTest(const FString&) {
  using namespace S08MapSurfaceSpec;
  using namespace S08MapTest;
  // Map plane: the engine plane (+-50 uu) stretched to the map, on PlaneZ; its corners are the map corners.
  const FVector2D Size = MapHalf * 2.0;
  const FTransform Plane = S08MapPlaneTransform(Size, PlaneZ);
  const FVector Far = Plane.TransformPosition(FVector(-50.0, -50.0, 0.0));
  const FVector Near = Plane.TransformPosition(FVector(50.0, 50.0, 0.0));
  TestTrue(FString::Printf(TEXT("plane corners %s .. %s = the map"), *Far.ToString(), *Near.ToString()),
           FVector2D(FMath::Min(Far.X, Near.X), FMath::Min(Far.Y, Near.Y)).Equals(-MapHalf, 0.01) &&
               FVector2D(FMath::Max(Far.X, Near.X), FMath::Max(Far.Y, Near.Y)).Equals(MapHalf, 0.01));
  TestTrue("plane on z -0.5", FMath::IsNearlyEqual(Plane.GetTranslation().Z, -0.5, 1e-6));
  // Px -> world = FS08LayoutFrame::ToWorld (the figures' CellToWorld).
  FS08MapImageSpec Spec;
  const FS08LayoutFrame Frame;
  for (const FVector2D Px : {FVector2D(0, 0), FVector2D(668.5, 433.0), FVector2D(1337, 866), FVector2D(190.4, 90.5)}) {
    TestTrue(FString::Printf(TEXT("px %s -> %s == layout frame %s"), *Px.ToString(), *Spec.PxToWorld(Px).ToString(),
                             *Frame.ToWorld(Px).ToString()),
             Spec.PxToWorld(Px).Equals(Frame.ToWorld(Px), 0.001));
  }
  TestTrue("px (0,0) = far-left map corner", Spec.PxToWorld(FVector2D(0, 0)).Equals(FVector(-MapHalf.X, -MapHalf.Y, 0.0), 0.01));
  TestTrue("default spec = layout frame", Spec.MatchesDefaultLayoutFrame());
  // Rebuild compares the profile with the board model's own frame (FS08BoardModel::SetLayoutFrame), not the
  // static defaults: a changed model frame refuses the default profile, a profile of that frame matches it.
  FS08BoardModel Custom;
  TestTrue("custom model frame set", Custom.SetLayoutFrame(FVector2D(1000.0, 500.0), 0.5f));
  TestTrue("default spec = default model frame", Spec.MatchesLayoutFrame(FS08BoardModel().LayoutFrame));
  TestFalse("default spec != a changed model frame", Spec.MatchesLayoutFrame(Custom.LayoutFrame));
  FS08MapImageSpec CustomSpec;
  CustomSpec.SrcSizePx = FIntPoint(1000, 500);
  CustomSpec.UuPerPx = 0.5f;
  TestTrue("spec of the changed frame matches it", CustomSpec.MatchesLayoutFrame(Custom.LayoutFrame));
  TestFalse("spec of the changed frame != defaults", CustomSpec.MatchesDefaultLayoutFrame());
  // Layering: tray top (-3) < map plane < grey link bar top < disc / play plane (0) < team ring < reachable ring.
  const float LinkTop = GreyLinkZ + GreyLinkDepth * 50.0f;
  const float LinkBottom = GreyLinkZ - GreyLinkDepth * 50.0f;
  TestTrue(FString::Printf(TEXT("layering tray %.1f < plane %.1f < link %.2f..%.2f < disc top 0 < team ring %.1f..%.1f < ring %.2f"),
                           S08Diorama::TopZ, PlaneZ, LinkBottom, LinkTop, S08TeamRingSpec::ZMin, S08TeamRingSpec::ZMax,
                           RingZ - RingDepth * 50.0f),
           S08Diorama::TopZ < PlaneZ && PlaneZ < LinkBottom && LinkTop < 0.0f &&
               S08TeamRingSpec::ZMax < RingZ - RingDepth * 50.0f);
  // Reachable ring: 12 tangent pieces on r = 36, inside the painted rim (41.6 uu) and outside the team ring (28.5).
  TArray<FTransform> Ring;
  S08RingPieces(RingRadiusUU, RingWidthUU, RingSegments, RingZ, RingDepth, Ring);
  if (TestEqual("12 ring pieces", Ring.Num(), RingSegments)) {
    double MinInner = TNumericLimits<double>::Max(), MaxOuter = 0.0;
    for (const FTransform& Piece : Ring) {
      TestTrue("piece centre on r 36", FMath::IsNearlyEqual(FVector2D(Piece.GetTranslation()).Size(), RingRadiusUU, 1e-3));
      for (const FVector& C : {FVector(-50, -50, 0), FVector(50, -50, 0), FVector(50, 50, 0), FVector(-50, 50, 0)}) {
        MaxOuter = FMath::Max(MaxOuter, FVector2D(Piece.TransformPosition(C)).Size());
      }
      // the inner edge midpoint (radial distance of the inner face)
      const FVector Inward = Piece.TransformPosition(FVector(0, -50, 0));
      const FVector Outward = Piece.TransformPosition(FVector(0, 50, 0));
      MinInner = FMath::Min(MinInner, FMath::Min(FVector2D(Inward).Size(), FVector2D(Outward).Size()));
    }
    TestTrue(FString::Printf(TEXT("ring outer reach %.2f < painted rim 41.6 - 1"), MaxOuter), MaxOuter < 40.6);
    TestTrue(FString::Printf(TEXT("ring inner %.2f > team ring outer %.2f + 1"), MinInner, S08TeamRingSpec::P1RimOut1),
             MinInner > S08TeamRingSpec::P1RimOut1 + 1.0);
  }
  // Grey link bar: trimmed to the disc edges; overlapping discs give no bar.
  FTransform Bar;
  if (TestTrue("bar between discs 200 uu apart", S08LinkBarTransform(FVector(0, 0, 0), FVector(200, 0, 0), 42.0f, 5.0f,
                                                                     GreyLinkZ, GreyLinkDepth, Bar))) {
    TestTrue("bar length 116, centre (100,0)", FMath::IsNearlyEqual(Bar.GetScale3D().X, 1.16, 1e-4) &&
                                                   Bar.GetTranslation().Equals(FVector(100, 0, GreyLinkZ), 1e-3));
  }
  TestTrue("diagonal bar yaw 45", S08LinkBarTransform(FVector(0, 0, 0), FVector(200, 200, 0), 42.0f, 5.0f, GreyLinkZ,
                                                      GreyLinkDepth, Bar) &&
                                      FMath::IsNearlyEqual(Bar.Rotator().Yaw, 45.0, 1e-3));
  TestFalse("touching discs: no bar", S08LinkBarTransform(FVector(0, 0, 0), FVector(84, 0, 0), 42.0f, 5.0f, GreyLinkZ,
                                                          GreyLinkDepth, Bar));
  // The fallback trace line.
  TestEqual("missing line", S08MapImageMissingLine(TEXT("/Game/EnvMaps/X/T_X")),
            FString(TEXT("ARTPREVIEW map-image missing /Game/EnvMaps/X/T_X")));
  // Link pairs of the synthetic board: T01-T02 and T02-T03 once each (symmetrised), grids none.
  FS08BoardModel Topo;
  if (TestTrue("synthetic topology board", SyntheticTopology(Topo))) {
    const TArray<TPair<FIntPoint, FIntPoint>> Links = S08BoardLinkPairs(Topo);
    TestTrue("two links (0,0)-(1,0) and (1,0)-(2,1)",
             Links.Num() == 2 && Links[0].Key == FIntPoint(0, 0) && Links[0].Value == FIntPoint(1, 0) &&
                 Links[1].Key == FIntPoint(1, 0) && Links[1].Value == FIntPoint(2, 1));
  }
  TestEqual("a grid has no link pairs", S08BoardLinkPairs(MakeBoard(5, 6)).Num(), 0);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapPlaneUvTest,
    "Unmatched.S08.BoardArt.MapPlaneUV the engine plane under S08MapPlaneTransform puts UV (0,0) on the far-left corner, u along +X, v along +Y",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMapPlaneUvTest::RunTest(const FString&) {
  UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, S08MapSurfaceSpec::PlaneMeshPath);
  if (!TestNotNull("engine plane /Engine/BasicShapes/Plane", Plane)) return false;
  // LOD0 render data (the editor keeps the CPU copy of the engine basic shapes; without it the check is skipped
  // with a warning, never passed silently).
  FStaticMeshRenderData* Render = Plane->GetRenderData();
  if (!Render || Render->LODResources.Num() == 0) {
    AddWarning(TEXT("engine plane has no render data here: UV orientation NOT checked"));
    return true;
  }
  FStaticMeshLODResources& Lod = Render->LODResources[0];
  FPositionVertexBuffer& Positions = Lod.VertexBuffers.PositionVertexBuffer;
  FStaticMeshVertexBuffer& Uvs = Lod.VertexBuffers.StaticMeshVertexBuffer;
  if (Positions.GetNumVertices() == 0 || !Positions.GetVertexData() || !Uvs.GetTexCoordData()) {
    AddWarning(TEXT("engine plane vertex buffers have no CPU copy: UV orientation NOT checked"));
    return true;
  }
  const FVector2D Size = S08MapTest::MapHalf * 2.0;
  // For every vertex: world = S08MapPlaneTransform(local), and the manifest mapping X = (u - 0.5) * W,
  // Y = (v - 0.5) * H must hold. The observed mapping is reported so a failing build can fix the transform.
  const FTransform T = S08MapPlaneTransform(Size, S08MapSurfaceSpec::PlaneZ);
  double Worst = 0.0;
  FString Observed;
  const uint32 Count = Positions.GetNumVertices();
  for (uint32 I = 0; I < Count; ++I) {
    const FVector3f Local = Positions.VertexPosition(I);
    const FVector2f UV = Uvs.GetVertexUV(I, 0);
    const FVector World = T.TransformPosition(FVector(Local));
    const FVector2D Want((UV.X - 0.5) * Size.X, (UV.Y - 0.5) * Size.Y);
    Worst = FMath::Max(Worst, FVector2D::Distance(FVector2D(World.X, World.Y), Want));
    if (I < 4) Observed += FString::Printf(TEXT(" local(%.0f,%.0f)->uv(%.2f,%.2f)"), Local.X, Local.Y, UV.X, UV.Y);
  }
  AddInfo(TEXT("engine plane UV:") + Observed);
  TestTrue("plane has vertices", Count >= 4);
  TestTrue(FString::Printf(TEXT("map UV orientation: worst %.3f uu <= 0.5 (observed%s)"), Worst, *Observed), Worst <= 0.5);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapActorTest,
    "Unmatched.S08.BoardArt.MapActor topology board: grey discs / links + pick box, no lattice; missing map assets fall back",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMapActorTest::RunTest(const FString&) {
  using namespace S08MapTest;
  FS08BoardModel Topo;
  if (!TestTrue("synthetic topology board", SyntheticTopology(Topo))) return false;
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08BoardArtMapActor")));
  if (!TestNotNull("test world", World)) return false;
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  // 1) Grey topology view (no art data): one disc per space, one bar per link, the dark canvas of the map size,
  //    the invisible QueryOnly pick box - and no lattice instance at all (their collision would pick squares).
  AS08BoardActor* Grey = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                           FRotator::ZeroRotator);
  if (TestNotNull("board actor", Grey)) {
    TestTrue("rebuild topology", Grey->Rebuild(Topo));
    TestTrue("topology board", Grey->IsTopologyBoard());
    TestFalse("no art (grey)", Grey->IsArtActive() || Grey->IsMapImageActive());
    TestEqual("no lattice instances", Grey->GetLatticeInstanceCount(), 0);
    const UInstancedStaticMeshComponent* Discs = Grey->GetTopologyDiscs();
    const UInstancedStaticMeshComponent* Bars = Grey->GetTopologyLinkBars();
    TestTrue("3 discs", Discs && Discs->GetInstanceCount() == 3 && Discs->IsVisible());
    TestTrue("2 link bars", Bars && Bars->GetInstanceCount() == 2 && Bars->IsVisible());
    if (Discs && Discs->GetInstanceCount() == 3) {
      FTransform First;
      Discs->GetInstanceTransform(0, First, true);
      TestTrue(FString::Printf(TEXT("disc 0 at T01 %s"), *First.GetTranslation().ToString()),
               FVector2D(First.GetTranslation()).Equals(FVector2D(Topo.CellToWorld(0, 0)), 0.01));
    }
    const UStaticMeshComponent* Canvas = Grey->GetMapPlane();
    TestTrue("dark canvas plane visible, map sized",
             Canvas && Canvas->IsVisible() &&
                 Canvas->GetRelativeScale3D().Equals(FVector(MapHalf.X / 50.0, MapHalf.Y / 50.0, 1.0), 0.01));
    const UBoxComponent* Pick = Grey->GetMapPickBox();
    if (TestNotNull("pick box", Pick)) {
      TestTrue("pick box QueryOnly", Pick->GetCollisionEnabled() == ECollisionEnabled::QueryOnly);
      TestTrue("pick box blocks Visibility only", Pick->GetCollisionResponseToChannel(ECC_Visibility) == ECR_Block &&
                                                      Pick->GetCollisionResponseToChannel(ECC_Camera) == ECR_Ignore &&
                                                      Pick->GetCollisionResponseToChannel(ECC_WorldStatic) == ECR_Ignore);
      TestTrue(FString::Printf(TEXT("pick box extent %s = the map half"), *Pick->GetUnscaledBoxExtent().ToString()),
               FVector2D(Pick->GetUnscaledBoxExtent()).Equals(MapHalf, 0.01) &&
                   FMath::IsNearlyEqual(Pick->GetRelativeLocation().Z + Pick->GetUnscaledBoxExtent().Z, 0.0, 1e-3));
    }
    TestTrue("half extent = the map canvas", Grey->GetBoardHalfExtentUU().Equals(MapHalf, 0.01));
    int32 X = -1, Y = -1;
    TestTrue("the actor's WorldToCell picks T02 in its circle",
             Grey->WorldToCell(Topo.CellToWorld(1, 0) + FVector(20, 10, 0), X, Y) && X == 1 && Y == 0);
    TestFalse("between the circles: no cell", Grey->WorldToCell(FVector(0.0, 250.0, 0.0), X, Y));
    // Reachable / illegal marks on a topology board: discs on the spaces (no square corners).
    Grey->SetSelectedFighter(TEXT("nobody"), {FS08BoardModel::CellKey(1, 0), FS08BoardModel::CellKey(2, 1),
                                              FS08BoardModel::CellKey(2, 0)});  // (2,0) is an obstacle: skipped
    // A grid after the topology board: lattice back, topology components off.
    TestTrue("rebuild 5x6 grid", Grey->Rebuild(MakeBoard(5, 6)));
    TestFalse("grid: not topology", Grey->IsTopologyBoard());
    TestEqual("grid: 30 tiles + 1 underlay", Grey->GetLatticeInstanceCount(), 31);
    TestTrue("grid: canvas hidden, discs cleared", Canvas && !Canvas->IsVisible() && Discs && Discs->GetInstanceCount() == 0);
    TestTrue("grid: pick box off", Pick && Pick->GetCollisionEnabled() == ECollisionEnabled::NoCollision);
    TestTrue("grid half extent unchanged", Grey->GetBoardHalfExtentUU().Equals(FVector2D(250.0, 300.0), 1e-6));
    Grey->Destroy();
  }
  // 2) Missing map assets (a checkout without the import): the map-image profile is refused, the board keeps the
  //    grey topology view and every missing package is reported ('ARTPREVIEW map-image missing <path>').
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (TestTrue(TEXT("map doc parses: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(MapDoc(), Errors))) {
    AS08BoardActor* Missing = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                                FRotator::ZeroRotator);
    if (TestNotNull("board actor (missing assets)", Missing)) {
      Missing->SetArtDataForTest(Data);
      Missing->SetRoomBoardId(TEXT("cidMap"));
      TestTrue("rebuild", Missing->Rebuild(Topo));
      TestFalse("map-image refused", Missing->IsArtActive() || Missing->IsMapImageActive());
      TestTrue("grey topology view instead", Missing->GetTopologyDiscs() && Missing->GetTopologyDiscs()->GetInstanceCount() == 3);
      TestEqual("no lattice", Missing->GetLatticeInstanceCount(), 0);
      const FS08BoardArtProfile* P = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("map"); });
      if (P) {
        TestEqual("all five packages reported missing", Missing->GetMapImageMissing().Num(), 5);
        for (const FString& Path : P->Map.AssetPaths()) {
          TestTrue(TEXT("missing: ") + S08MapImageMissingLine(Path), Missing->GetMapImageMissing().Contains(Path));
        }
      }
      TestTrue("half extent = the map canvas (grey)", Missing->GetBoardHalfExtentUU().Equals(MapHalf, 0.01));
      Missing->Destroy();
    }
  }
  // 3) The shipped Marmoreal profile once tools/art/map_surface/ue_import_map_surface.py ran (assets out of git).
  FS08BoardArtData Shipped;
  Errors.Reset();
  if (TestTrue("shipped data", LoadShipped(Shipped, Errors))) {
    const FS08BoardArtProfile* Marmoreal =
        Shipped.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("marmoreal-original"); });
    TSharedPtr<FJsonValue> State;
    TSharedPtr<FJsonObject> Root;
    FString BoardId;
    FS08BoardModel Board;
    const bool bBoard = TopologyBoardState(FPaths::Combine(TopologyFixtureDir(), TEXT("marmoreal.topology.json")), State,
                                           BoardId, Root) &&
                        Board.Decode(State);
    if (!Marmoreal || !bBoard) {
      AddError(TEXT("marmoreal-original profile or fixture missing"));
    } else if (!FPackageName::DoesPackageExist(Marmoreal->Map.MaterialInstancePath)) {
      AddWarning(FString::Printf(TEXT("map assets not imported (%s): run tools/art/map_surface/ue_import_map_surface.py "
                                      "(ENV-U3: out of git); the map-image path of this test was NOT exercised"),
                                 *Marmoreal->Map.MaterialInstancePath));
    } else {
      AS08BoardActor* Map = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                              FRotator::ZeroRotator);
      if (TestNotNull("board actor (map-image)", Map)) {
        Map->SetArtDataForTest(Shipped);
        Map->SetRoomBoardId(BoardId);
        TestTrue("rebuild Marmoreal", Map->Rebuild(Board));
        TestTrue("map-image active", Map->IsArtActive() && Map->IsMapImageActive());
        TestEqual("nothing missing", Map->GetMapImageMissing().Num(), 0);
        const UStaticMeshComponent* PlaneComp = Map->GetMapPlane();
        TestTrue("map plane visible with the MI", PlaneComp && PlaneComp->IsVisible() && PlaneComp->GetMaterial(0) &&
                                                      PlaneComp->GetMaterial(0)->GetMaterial());
        if (PlaneComp) {
          const UMaterialInstanceDynamic* Mid = Cast<UMaterialInstanceDynamic>(PlaneComp->GetMaterial(0));
          TestTrue("plane material = MID of MI_Marmoreal_MapBoard",
                   Mid && Mid->Parent && Mid->Parent->GetName() == TEXT("MI_Marmoreal_MapBoard"));
          TestTrue("plane sized to the map", PlaneComp->GetRelativeScale3D().Equals(FVector(MapHalf.X / 50.0, MapHalf.Y / 50.0, 1.0), 0.01));
        }
        TestEqual("no lattice", Map->GetLatticeInstanceCount(), 0);
        TestEqual("4 frame bars", Map->GetArtSurfacePartCount(), 4);
        TestEqual("4 iron corners", Map->GetArtCornerCount(), 4);
        TestTrue("no grey discs", !Map->GetTopologyDiscs() || Map->GetTopologyDiscs()->GetInstanceCount() == 0);
        TestTrue("half extent = the map", Map->GetBoardHalfExtentUU().Equals(MapHalf, 0.01));
        TestTrue("pick box on the map", Map->GetMapPickBox() &&
                                            Map->GetMapPickBox()->GetCollisionEnabled() == ECollisionEnabled::QueryOnly);
        // reachable rings (art): no crash, rings only on spaces
        Map->SetSelectedFighter(TEXT("nobody"), {FS08BoardModel::CellKey(0, 0)});
        Map->Destroy();
      }
    }
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapAssetsTest,
    "Unmatched.S08.BoardArt.MapAssets imported map textures / M_MapBoard / MI per map match the import contract (out of git)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMapAssetsTest::RunTest(const FString&) {
  FS08BoardArtData Data;
  TArray<FString> Errors;
  if (!TestTrue("shipped data", LoadShipped(Data, Errors))) return false;
  int32 Checked = 0;
  for (const FS08BoardArtProfile& B : Data.Boards) {
    if (B.Surface != ES08BoardSurface::MapImage) continue;
    const FS08MapImageSpec& M = B.Map;
    if (!FPackageName::DoesPackageExist(M.MaterialInstancePath)) {
      AddWarning(FString::Printf(TEXT("%s: map assets not imported (%s) - run tools/art/map_surface/ue_import_map_surface.py"),
                                 *B.Id, *M.MaterialInstancePath));
      continue;
    }
    ++Checked;
    UTexture2D* Bc = LoadObject<UTexture2D>(nullptr, *M.BaseColorPath);
    UTexture2D* Mask = LoadObject<UTexture2D>(nullptr, *M.MaskPath);
    UTexture2D* Sdf = LoadObject<UTexture2D>(nullptr, *M.SdfPath);
    UTexture2D* Id = LoadObject<UTexture2D>(nullptr, *M.SpaceIdPath);
    UMaterialInstance* Mi = LoadObject<UMaterialInstance>(nullptr, *M.MaterialInstancePath);
    if (!TestTrue(B.Id + TEXT(": four textures and the MI load"), Bc && Mask && Sdf && Id && Mi)) continue;
    TestTrue(B.Id + TEXT(": BC sRGB, default compression"), Bc->SRGB && Bc->CompressionSettings == TC_Default);
    TestTrue(B.Id + TEXT(": mask linear grayscale"), !Mask->SRGB && Mask->CompressionSettings == TC_Grayscale);
    TestTrue(B.Id + TEXT(": SDF linear HDR (RGBA16F, 16-bit codes kept)"), !Sdf->SRGB && Sdf->CompressionSettings == TC_HDR);
    TestTrue(B.Id + TEXT(": space ID linear half float, nearest"), !Id->SRGB && Id->CompressionSettings == TC_HalfFloat &&
                                                                       Id->Filter == TF_Nearest);
#if WITH_EDITORONLY_DATA
    TestTrue(B.Id + TEXT(": space ID without mips"), Id->MipGenSettings == TMGS_NoMipmaps);
    TestTrue(B.Id + TEXT(": 4096 source"), Bc->Source.GetSizeX() == 4096 && Bc->Source.GetSizeY() == 4096);
#endif
    TestTrue(B.Id + TEXT(": parent /Game/EnvMaps/M_MapBoard"),
             Mi->Parent && Mi->Parent->GetPathName() == TEXT("/Game/EnvMaps/M_MapBoard.M_MapBoard"));
    UTexture* Bound = nullptr;
    TestTrue(B.Id + TEXT(": BaseColor bound"), Mi->GetTextureParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamBaseColor), Bound) && Bound == Bc);
    TestTrue(B.Id + TEXT(": GameMask bound"), Mi->GetTextureParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamGameMask), Bound) && Bound == Mask);
    float Value = 0.0f;
    TestTrue(B.Id + TEXT(": NightEV -0.7"), Mi->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("NightEV")), Value) && FMath::IsNearlyEqual(Value, -0.7f, 1e-4f));
    TestTrue(B.Id + TEXT(": NightSaturation 0.7"), Mi->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("NightSaturation")), Value) && FMath::IsNearlyEqual(Value, 0.7f, 1e-4f));
    TestTrue(B.Id + TEXT(": Lift 0.35"), Mi->GetScalarParameterValue(FHashedMaterialParameterInfo(TEXT("Lift")), Value) && FMath::IsNearlyEqual(Value, 0.35f, 1e-4f));
    FLinearColor Tint;
    TestTrue(B.Id + TEXT(": NightTint"), Mi->GetVectorParameterValue(FHashedMaterialParameterInfo(TEXT("NightTint")), Tint));
    const UMaterial* Base = Mi->GetMaterial();
    TestTrue(B.Id + TEXT(": lit surface material"), Base && Base->GetShadingModels().HasShadingModel(MSM_DefaultLit));
  }
  AddInfo(FString::Printf(TEXT("map-image profiles checked against imported assets: %d"), Checked));
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
