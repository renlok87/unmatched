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
// ENV-MAPS P5 track C: MapFrameLayout (frame-002 modules vs the committed frame-layout.json), FrameBackdropParser,
// BackdropGeometry (K1 camera model, moon / mist placement below the board), FrameBackdropActor (map-image only).
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.BoardArt; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08ArtHud.h"
#include "S08MapBackdrop.h"
#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08Diorama.h"
#include "S08EnvLayout.h"
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
  // ENV-MAPS P2 night calibration: the optional fog and map night grade blocks parse; broken ones reject the profile.
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue("render blocks without fog / mapGrade", Data.ParseJson(Render, Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    TestTrue("no fog and no map grade by default", L && !L->Fog.bSet && !L->MapGrade.bSet);
  }
  const FString NightBlocks = TEXT("\"fog\":{\"colorLinear\":[0.02,0.03,0.06],\"density\":0.05,\"heightFalloff\":0.5,")
      TEXT("\"heightZ\":-300,\"startDistanceUU\":2600,\"endDistanceUU\":30000,\"maxOpacity\":0.9},")
      TEXT("\"mapGrade\":{\"nightEV\":-0.4,\"nightSaturation\":0.8,\"lift\":1.5,\"nightTintLinear\":[0.9,1,1.1]},\"exposure\":{");
  FString Night = Render;
  Night.ReplaceInline(TEXT("\"exposure\":{"), *NightBlocks);
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue(TEXT("fog + mapGrade parse: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Night, Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    if (TestNotNull("light L with fog + mapGrade", L)) {
      TestTrue("fog", L->Fog.bSet && FMath::IsNearlyEqual(L->Fog.Density, 0.05f) &&
                          FMath::IsNearlyEqual(L->Fog.HeightFalloff, 0.5f) && FMath::IsNearlyEqual(L->Fog.HeightZ, -300.0f) &&
                          FMath::IsNearlyEqual(L->Fog.StartDistanceUU, 2600.0f) &&
                          FMath::IsNearlyEqual(L->Fog.EndDistanceUU, 30000.0f) &&
                          FMath::IsNearlyEqual(L->Fog.MaxOpacity, 0.9f) && FMath::IsNearlyEqual(L->Fog.Color.B, 0.06f));
      TestTrue("mapGrade", L->MapGrade.bSet && FMath::IsNearlyEqual(L->MapGrade.NightEV, -0.4f) &&
                               FMath::IsNearlyEqual(L->MapGrade.NightSaturation, 0.8f) &&
                               FMath::IsNearlyEqual(L->MapGrade.Lift, 1.5f) && L->MapGrade.bHasTint &&
                               FMath::IsNearlyEqual(L->MapGrade.NightTint.B, 1.1f));
    }
  }
  auto ExpectNight = [this, &Night](const FString& Name, const FString& From, const FString& To, const FString& ErrorPart) {
    FString Doc = Night;
    TestTrue(Name + TEXT(": patch applies"), Doc.Contains(From));
    Doc.ReplaceInline(*From, *To);
    FS08BoardArtData Data;
    TArray<FString> Errors;
    Data.ParseJson(Doc, Errors);
    TestFalse(Name + TEXT(": profile rejected"), Data.Lights.Contains(TEXT("L")));
    TestTrue(Name + TEXT(": reason '") + ErrorPart + TEXT("' in ") + FString::Join(Errors, TEXT(" | ")),
             FString::Join(Errors, TEXT(" | ")).Contains(ErrorPart));
  };
  ExpectNight(TEXT("fog density 0"), TEXT("\"density\":0.05"), TEXT("\"density\":0"), TEXT("fog needs"));
  ExpectNight(TEXT("fog without colour"), TEXT("\"colorLinear\":[0.02,0.03,0.06],"), TEXT(""), TEXT("fog needs"));
  ExpectNight(TEXT("fog end before start"), TEXT("\"endDistanceUU\":30000"), TEXT("\"endDistanceUU\":100"), TEXT("fog needs"));
  ExpectNight(TEXT("fog opacity > 1"), TEXT("\"maxOpacity\":0.9"), TEXT("\"maxOpacity\":1.5"), TEXT("fog needs"));
  ExpectNight(TEXT("map grade lift < 0"), TEXT("\"lift\":1.5"), TEXT("\"lift\":-1"), TEXT("mapGrade needs"));
  ExpectNight(TEXT("map grade without nightEV"), TEXT("\"nightEV\":-0.4,"), TEXT(""), TEXT("mapGrade needs"));
  ExpectNight(TEXT("map grade bad tint"), TEXT("[0.9,1,1.1]"), TEXT("[0.9,1]"), TEXT("mapGrade needs"));
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
  // 2) fill band vs the target arcs (5c-B3: 0.92 of the mesh, outer 21.16 uu) and the selection ring (outer 20 uu),
  //    both scaled like the ring
  TestTrue(FString::Printf(TEXT("target arcs outer %.2f = mesh outer %.1f x scale %.2f"), TargetArcOuterUU,
                           TargetArcMeshOuterUU, TargetArcScale),
           FMath::IsNearlyEqual(TargetArcOuterUU, TargetArcMeshOuterUU * TargetArcScale) && TargetArcScale < 1.0f);
  TestTrue(FString::Printf(TEXT("P1 fill inner %.1f > target arcs outer %.2f"), P1Fill0, TargetArcOuterUU),
           P1Fill0 > TargetArcOuterUU);
  TestTrue(FString::Printf(TEXT("P2 fill inner apothem %.1f > target arcs outer %.2f"), P2Fill0, TargetArcOuterUU),
           P2Fill0 > TargetArcOuterUU);
  // 5c-B3 (B1-8 FAIL, act art3-live-3boards-r3 4.2): >= 1 uu of the inner keyline stays visible between the arcs and
  // the fill (P2: on the flats; P1: everywhere), so the arcs never touch the fill in any colour variant
  TestTrue(FString::Printf(TEXT("visible inner keyline between the arcs and the fill: P1 %.2f, P2 %.2f uu >= 1.0"),
                           P1Fill0 - FMath::Max(TargetArcOuterUU, P1KeylineIn0),
                           P2Fill0 - FMath::Max(TargetArcOuterUU, P2KeylineIn0)),
           P1Fill0 - FMath::Max(TargetArcOuterUU, P1KeylineIn0) >= 1.0f &&
               P2Fill0 - FMath::Max(TargetArcOuterUU, P2KeylineIn0) >= 1.0f);
  TestTrue(FString::Printf(TEXT("target arcs inner %.2f outside the 30-uu pedestal (15)"), TargetArcInnerUU),
           TargetArcInnerUU > 15.0f);
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

/** The "map" board's light field: the anchor where the tests insert "k1DistanceMul" (the grid board has "tiles"). */
const TCHAR* const MapLightAnchor = TEXT("\"surface\":\"map-image\",\"light\":\"L\",");

/** MapDoc() with "k1DistanceMul": Mul on the map board (ENV-U9; the shipped map profiles carry 1.25). */
FString MapDocWithK1Mul(const TCHAR* Mul) {
  FString Doc = MapDoc();
  Doc.ReplaceInline(MapLightAnchor, *FString::Printf(TEXT("%s\"k1DistanceMul\":%s,"), MapLightAnchor, Mul));
  return Doc;
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
  // ENV-U9 "k1DistanceMul": optional (default 1 = the plain fit), [1, 2].
  TestTrue(FString::Printf(TEXT("k1DistanceMul absent -> 1 (%.3f)"), P->K1DistanceMul), P->K1DistanceMul == 1.0f);
  {
    FS08BoardArtData WithMul;
    TArray<FString> MulErrors;
    const bool bParsed = WithMul.ParseJson(MapDocWithK1Mul(TEXT("1.25")), MulErrors);
    TestTrue(TEXT("k1DistanceMul 1.25 parses: ") + FString::Join(MulErrors, TEXT(" | ")), bParsed);
    const FS08BoardArtProfile* MapMul =
        WithMul.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("map"); });
    const FS08BoardArtProfile* GridMul =
        WithMul.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("one"); });
    TestTrue("k1DistanceMul 1.25 kept", MapMul && MapMul->K1DistanceMul == 1.25f);
    TestTrue("the grid profile without the field keeps 1", GridMul && GridMul->K1DistanceMul == 1.0f);
  }
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
  const FString MulError = TEXT("k1DistanceMul must be a number in [1, 2]");
  for (const TCHAR* Bad : {TEXT("0.9"), TEXT("2.5"), TEXT("0"), TEXT("\"far\"")}) {
    Expect(FString::Printf(TEXT("k1DistanceMul %s"), Bad), MapLightAnchor,
           FString::Printf(TEXT("%s\"k1DistanceMul\":%s,"), MapLightAnchor, Bad), MulError);
  }
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
    TestTrue(FString::Printf(TEXT("%s: K1 fit %.2f = 1872 +- 1"), *Name, K1), FMath::Abs(K1 - 1872.0f) <= 1.0f);
    // ENV-U9: the profile moves the overview back to the fit x 1.25 (the env layout around the frame in K1).
    TestTrue(FString::Printf(TEXT("%s: k1DistanceMul %.3f = 1.25"), *Name, P->K1DistanceMul), P->K1DistanceMul == 1.25f);
    const float Overview = S08K1OverviewDistanceUU(K1, P->K1DistanceMul);
    TestTrue(FString::Printf(TEXT("%s: K1 overview %.2f = fit x 1.25 = 2340 +- 1"), *Name, Overview),
             FMath::Abs(Overview - 2340.0f) <= 1.0f && FMath::IsNearlyEqual(Overview, K1 * 1.25f));
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
      // S08ArtBoardProfiles rev 7 (ENV-MAPS P1b review): the warm lamp / fire pools moved from the night profile
      // to the map's env layout (Config/ArtBoards/EnvLayouts/<map>.layout.json, whose points S08EnvLayout adds to
      // these), so profile + layout stay within 1 key + <= 6 points. The profile keeps the cool fill; warm comes
      // from the layout (warm = sRGB red above blue).
      const FString EnvFile = S08EnvLayout::FileFor(S08EnvLayout::DefaultDir(), S08EnvLayout::MapKeyOf(M.Name));
      FS08EnvLayout Env;
      TArray<FString> EnvErrors;
      int32 EnvWarm = 0;
      if (TestTrue(Name + TEXT(": env layout ") + EnvFile, FPaths::FileExists(EnvFile) && Env.LoadFile(EnvFile, EnvErrors))) {
        for (const FS08EnvLight& L : Env.Lights) EnvWarm += L.Color.R > L.Color.B;
      }
      int32 Points = 0;
      for (const FS08PlacedLight& Pl : Placed) Points += !Pl.Spec.bDirectional;
      TestTrue(Name + TEXT(": cool spot in the profile"), Cool >= 1);
      TestTrue(FString::Printf(TEXT("%s: warm pools (profile %d + env layout %d)"), *Name, Warm, EnvWarm), Warm + EnvWarm >= 1);
      TestTrue(Name + TEXT(": budget"), Placed.Num() <= 7);
      TestTrue(FString::Printf(TEXT("%s: combined points %d + %d <= 6"), *Name, Points, Env.Lights.Num()),
               Points + Env.Lights.Num() <= 6);
      // Profile rev 9 (ENV-MAPS P2 night calibration): the night haze fog keeps the K1 board out of it (start beyond
      // the farthest K1 tray point, ~2800 uu) and the map grade keeps the readability lift inside the game mask.
      TestTrue(FString::Printf(TEXT("%s: night fog set, start %.0f >= 2800, no volumetric"), *Name, Light->Fog.StartDistanceUU),
               Light->Fog.bSet && Light->Fog.StartDistanceUU >= 2800.0f && Light->Fog.Density > 0.0f);
      TestTrue(FString::Printf(TEXT("%s: map grade set, lift %.2f > the MI 0.35"), *Name, Light->MapGrade.Lift),
               Light->MapGrade.bSet && Light->MapGrade.Lift > 0.35f);
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapCameraTest,
    "Unmatched.S08.BoardArt.MapCamera K1 distance: grids unchanged (Cobble 1931), map canvas fit 1872 x k1DistanceMul 1.25 = 2340",
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
    // ENV-U9: a multiplier of 1 (every grid profile) is the fit, bit for bit.
    const float GridFit = S08K1FitDistanceUU(Half);
    TestTrue(FString::Printf(TEXT("%dx%d grid overview (k1DistanceMul 1) == the fit exactly"), Size.X, Size.Y),
             S08K1OverviewDistanceUU(GridFit, 1.0f) == GridFit);
  }
  TestTrue(FString::Printf(TEXT("Cobble 5x6 K1 %.1f = 1931 +- 1"), S08K1FitDistanceUU(S08BoardHalfExtentUU(MakeBoard(5, 6)))),
           FMath::Abs(S08K1FitDistanceUU(S08BoardHalfExtentUU(MakeBoard(5, 6))) - 1931.0f) <= 1.0f);
  // ENV-U9 in the shipped data: the two map-image profiles carry 1.25, every grid profile (Cobble first) keeps 1.
  {
    FS08BoardArtData Shipped;
    TArray<FString> Errors;
    if (TestTrue("shipped data", LoadShipped(Shipped, Errors))) {
      int32 Maps = 0;
      for (const FS08BoardArtProfile& B : Shipped.Boards) {
        const bool bMap = B.Surface == ES08BoardSurface::MapImage;
        Maps += bMap ? 1 : 0;
        TestTrue(FString::Printf(TEXT("%s: k1DistanceMul %.3f = %s"), *B.Id, B.K1DistanceMul, bMap ? TEXT("1.25") : TEXT("1")),
                 B.K1DistanceMul == (bMap ? 1.25f : 1.0f));
      }
      TestEqual("two map-image profiles", Maps, 2);
      const FS08BoardArtProfile* Cobble =
          Shipped.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("cobble-city"); });
      if (TestNotNull("cobble-city profile", Cobble)) {
        const float CobbleFit = S08K1FitDistanceUU(S08BoardHalfExtentUU(MakeBoard(5, 6)));
        const float CobbleOverview = S08K1OverviewDistanceUU(CobbleFit, Cobble->K1DistanceMul);
        TestTrue(FString::Printf(TEXT("Cobble overview %.3f == its fit (1931 unchanged)"), CobbleOverview),
                 CobbleOverview == CobbleFit);
        TestEqual("Cobble overview = the pre-ENV-MAPS formula", CobbleOverview, Legacy(5, 6));
      }
    }
  }
  FS08BoardModel Topo;
  if (TestTrue("synthetic topology board", SyntheticTopology(Topo))) {
    const FVector2D Half = S08BoardHalfExtentUU(Topo);
    TestTrue(FString::Printf(TEXT("topology half %s = the map canvas 445.667 x 288.667 (not the 3x2 lattice)"), *Half.ToString()),
             Half.Equals(MapHalf, 0.01));
    const float K1 = S08K1FitDistanceUU(Half);
    // tools/art/map_surface/manifest.<key>.json k1.camera.distance_uu = 1872.156 (the same formula in Python)
    TestTrue(FString::Printf(TEXT("map K1 fit %.3f = 1872.156 +- 0.5 (manifest) and 1872 +- 1"), K1),
             FMath::Abs(K1 - 1872.156f) <= 0.5f && FMath::Abs(K1 - 1872.0f) <= 1.0f);
    // ENV-U9: the overview of a map-image board = the fit x 1.25 (tools/art/map_surface/k1_mock.s08_overview_distance
    // and tools/art/env_kit/layout_check.py use the same 2340.195 uu).
    const float Overview = S08K1OverviewDistanceUU(K1, 1.25f);
    TestTrue(FString::Printf(TEXT("map K1 overview %.3f = 2340.195 +- 0.5 and 2340 +- 1"), Overview),
             FMath::Abs(Overview - 2340.195f) <= 0.5f && FMath::Abs(Overview - 2340.0f) <= 1.0f);
    TestTrue(FString::Printf(TEXT("the far limit fit / 0.65 = %.1f = 0.8125x of the overview"), K1 / 0.65f),
             FMath::IsNearlyEqual(Overview / (K1 / 0.65f), 0.8125f, 1e-4f));
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
    TestTrue("grey: k1DistanceMul 1 (K1 = the plain fit)", Grey->GetK1DistanceMul() == 1.0f);
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
  // ENV-U9: the profile asks for k1DistanceMul 1.25, but a refused profile never moves the camera.
  if (TestTrue(TEXT("map doc parses: ") + FString::Join(Errors, TEXT(" | ")),
               Data.ParseJson(MapDocWithK1Mul(TEXT("1.25")), Errors))) {
    AS08BoardActor* Missing = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                                FRotator::ZeroRotator);
    if (TestNotNull("board actor (missing assets)", Missing)) {
      Missing->SetArtDataForTest(Data);
      Missing->SetRoomBoardId(TEXT("cidMap"));
      TestTrue("rebuild", Missing->Rebuild(Topo));
      TestFalse("map-image refused", Missing->IsArtActive() || Missing->IsMapImageActive());
      TestTrue("refused profile: k1DistanceMul 1 (K1 = the plain fit)", Missing->GetK1DistanceMul() == 1.0f);
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
          // Profile rev 9 (ENV-MAPS P2): the light profile's mapGrade is what the MID renders with.
          const FS08LightProfile* Night = Shipped.LightFor(*Marmoreal);
          float Lift = -1.0f, Ev = 0.0f;
          if (Mid && Night && Night->MapGrade.bSet) {
            Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamLift), Lift);
            Mid->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamNightEV), Ev);
          }
          TestTrue(FString::Printf(TEXT("MID map grade = the profile (Lift %.2f, NightEV %.2f)"), Lift, Ev),
                   Night && Night->MapGrade.bSet && FMath::IsNearlyEqual(Lift, Night->MapGrade.Lift) &&
                       FMath::IsNearlyEqual(Ev, Night->MapGrade.NightEV));
        }
        TestTrue("night fog spawned with the lights", Map->GetAppliedRender().bFog);
        TestEqual("no lattice", Map->GetLatticeInstanceCount(), 0);
        // ENV-MAPS P5 track C: the shipped profile asks for the frame-002 kit; without its import the bars + corners stay.
        if (Map->GetMapFrameKitSource() == TEXT("frame-002")) {
          TestEqual("frame-002: no cube bars", Map->GetArtSurfacePartCount(), 0);
          TestEqual("frame-002: no ART-005 corners", Map->GetArtCornerCount(), 0);
          TestEqual("frame-002: 20 modules", Map->GetMapFrameParts().Num(), 20);
        } else {
          TestEqual("frame kit not imported -> 'missing'", Map->GetMapFrameKitSource(), FString(TEXT("missing")));
          TestEqual("4 frame bars", Map->GetArtSurfacePartCount(), 4);
          TestEqual("4 iron corners", Map->GetArtCornerCount(), 4);
        }
        TestTrue("no grey discs", !Map->GetTopologyDiscs() || Map->GetTopologyDiscs()->GetInstanceCount() == 0);
        TestTrue("half extent = the map", Map->GetBoardHalfExtentUU().Equals(MapHalf, 0.01));
        // ENV-U9: what SetupCameraForBoard reads - the active profile's 1.25 -> K1 2340 uu.
        const float MapK1 = S08K1OverviewDistanceUU(S08K1FitDistanceUU(Map->GetBoardHalfExtentUU()), Map->GetK1DistanceMul());
        TestTrue(FString::Printf(TEXT("active map profile: k1DistanceMul %.3f = 1.25, K1 %.1f = 2340 +- 1"),
                                 Map->GetK1DistanceMul(), MapK1),
                 Map->GetK1DistanceMul() == 1.25f && FMath::Abs(MapK1 - 2340.0f) <= 1.0f);
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
    // ENV-MAPS P4: the MI carries the light profile's mapGrade (manifest k1.grade_b_c = k1_mock.profile_map_grade),
    // incl. the M_MapBoard graph-v2 zone-separation terms; the board actor sets the same values on its MID.
    const FS08LightProfile* Night = Data.LightFor(B);
    if (!TestTrue(B.Id + TEXT(": night light profile with a mapGrade"), Night && Night->MapGrade.bSet)) continue;
    const FS08MapGradeSpec& G = Night->MapGrade;
    auto Scalar = [&](const TCHAR* Name, float Want) {
      float Value = -1000.0f;
      const bool bFound = Mi->GetScalarParameterValue(FHashedMaterialParameterInfo(Name), Value);
      TestTrue(FString::Printf(TEXT("%s: MI %s %.3f == profile %.3f"), *B.Id, Name, Value, Want),
               bFound && FMath::IsNearlyEqual(Value, Want, 1e-4f));
    };
    Scalar(S08MapSurfaceSpec::ParamNightEV, G.NightEV);
    Scalar(S08MapSurfaceSpec::ParamNightSaturation, G.NightSaturation);
    Scalar(S08MapSurfaceSpec::ParamLift, G.Lift);
    Scalar(S08MapSurfaceSpec::ParamMaskSaturation, G.MaskSaturation);
    Scalar(S08MapSurfaceSpec::ParamLiftSaturation, G.LiftSaturation);
    FLinearColor Tint;
    TestTrue(B.Id + TEXT(": NightTint"), Mi->GetVectorParameterValue(FHashedMaterialParameterInfo(TEXT("NightTint")), Tint));
    FLinearColor Inverse(-1.0f, -1.0f, -1.0f);
    const bool bInverse =
        Mi->GetVectorParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamMaskInverseTint), Inverse);
    TestTrue(FString::Printf(TEXT("%s: MaskInverseTint %s == profile %s (graph v2)"), *B.Id, *Inverse.ToString(),
                             *G.MaskInverseTint.ToString()),
             bInverse && FVector3f(Inverse.R, Inverse.G, Inverse.B)
                             .Equals(FVector3f(G.MaskInverseTint.R, G.MaskInverseTint.G, G.MaskInverseTint.B), 1e-4f));
    const UMaterial* Base = Mi->GetMaterial();
    TestTrue(B.Id + TEXT(": lit surface material"), Base && Base->GetShadingModels().HasShadingModel(MSM_DefaultLit));
  }
  AddInfo(FString::Printf(TEXT("map-image profiles checked against imported assets: %d"), Checked));
  // ENV-MAPS P4 readability materials (same import script): the frame wood is lit, the contact shadow an unlit
  // modulate blob; both carry the parameters the board actor sets.
  if (Checked > 0) {
    const UMaterial* Wood = LoadObject<UMaterial>(nullptr, S08MapSurfaceSpec::FrameWoodMaterialPath, nullptr, LOAD_NoWarn);
    const UMaterial* Blob = LoadObject<UMaterial>(nullptr, S08MapSurfaceSpec::ContactShadowMaterialPath, nullptr, LOAD_NoWarn);
    float Probe = 0.0f;
    if (TestNotNull("M_MapFrameWood imported", Wood)) {
      TestTrue("M_MapFrameWood lit", Wood->GetShadingModels().HasShadingModel(MSM_DefaultLit));
      TestTrue("M_MapFrameWood FrameValueScale / FrameSaturation",
               Wood->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamFrameValueScale), Probe) &&
                   Wood->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamFrameSaturation), Probe));
    }
    if (TestNotNull("M_MapContactShadow imported", Blob)) {
      TestTrue("M_MapContactShadow unlit modulate", Blob->GetBlendMode() == BLEND_Modulate &&
                                                       Blob->GetShadingModels().HasShadingModel(MSM_Unlit));
      TestTrue("M_MapContactShadow Strength / Softness",
               Blob->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamShadowStrength), Probe) &&
                   Blob->GetScalarParameterValue(FHashedMaterialParameterInfo(S08MapSurfaceSpec::ParamShadowSoftness), Probe));
    }
  }
  return true;
}

// ---- ENV-MAPS P4 readability (concept review 2026-10-01): map-image boards only, grids bit for bit -------------

namespace S08ReadabilityTest {
/** The map board's readability block of the tests (the shipped Marmoreal values). */
const TCHAR* const Block = TEXT(
    "\"readability\":{\"labelPlates\":true,\"leaderPip\":true,"
    "\"reach\":{\"colorSrgb\":\"#FFC857\",\"strokeSrgb\":\"#14110C\",\"segments\":48,\"widthUU\":3.5,\"strokeUU\":1.0},"
    "\"contactShadow\":{\"diameterUU\":64,\"strength\":0.5,\"softness\":0.55},"
    "\"frameWood\":{\"valueScaleSrgb\":0.7,\"saturation\":0.75}},");

FString MapDocWithReadability(const FString& Readability) {
  FString Doc = S08MapTest::MapDoc();
  Doc.ReplaceInline(S08MapTest::MapLightAnchor, *(FString(S08MapTest::MapLightAnchor) + Readability));
  return Doc;
}

const UStaticMeshComponent* FindPart(const AActor* Actor, const TCHAR* Name) {
  if (!Actor) return nullptr;
  TInlineComponentArray<UStaticMeshComponent*> Parts(Actor);
  for (const UStaticMeshComponent* Part : Parts) {
    if (Part && Part->GetFName() == FName(Name)) return Part;
  }
  return nullptr;
}
}  // namespace S08ReadabilityTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtReadabilityParserTest,
    "Unmatched.S08.BoardArt.ReadabilityParser map-image readability block: parsed, optional, map-image only, ranges",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtReadabilityParserTest::RunTest(const FString&) {
  using namespace S08ReadabilityTest;
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    if (!TestTrue(TEXT("map doc with readability parses: ") + FString::Join(Errors, TEXT(" | ")),
                  Data.ParseJson(MapDocWithReadability(Block), Errors))) {
      return false;
    }
    const FS08BoardArtProfile* Map = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("map"); });
    const FS08BoardArtProfile* Grid = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("one"); });
    if (TestNotNull("map profile", Map)) {
      const FS08BoardReadabilitySpec& R = Map->Readability;
      TestTrue("block set", R.bSet);
      TestTrue("label plates + leader pip", R.bLabelPlates && R.bLeaderPip);
      TestTrue("reach colour / stroke as sRGB bytes", R.bReach && S08ColorHex(R.ReachColor) == TEXT("#FFC857") &&
                                                          S08ColorHex(R.ReachStroke) == TEXT("#14110C"));
      TestTrue("reach 48 segments, width 3.5, stroke 1", R.ReachSegments == 48 &&
                                                            FMath::IsNearlyEqual(R.ReachWidthUU, 3.5f) &&
                                                            FMath::IsNearlyEqual(R.ReachStrokeUU, 1.0f));
      TestTrue("contact shadow", R.bContactShadow && FMath::IsNearlyEqual(R.ShadowDiameterUU, 64.0f) &&
                                     FMath::IsNearlyEqual(R.ShadowStrength, 0.5f) &&
                                     FMath::IsNearlyEqual(R.ShadowSoftness, 0.55f));
      TestTrue(FString::Printf(TEXT("frame wood V 0.7 -> linear %.4f (0.7^2.2 = 0.4563)"), R.FrameValueScaleLinear()),
               R.bFrameWood && FMath::IsNearlyEqual(R.FrameValueScaleLinear(), 0.4563f, 1e-3f) &&
                   FMath::IsNearlyEqual(R.FrameSaturation, 0.75f));
    }
    TestTrue("the grid profile has no readability block", Grid && !Grid->Readability.bSet && !Grid->Readability.bLabelPlates);
  }
  {
    // absent block = all off; a partial block switches on only what it names
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue("map doc without readability parses", Data.ParseJson(S08MapTest::MapDoc(), Errors));
    const FS08BoardArtProfile* Map = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("map"); });
    TestTrue("absent block: off", Map && !Map->Readability.bSet && !Map->Readability.bReach &&
                                      !Map->Readability.bContactShadow && !Map->Readability.bLeaderPip &&
                                      !Map->Readability.bFrameWood && !Map->Readability.bLabelPlates);
    FS08BoardArtData Partial;
    TestTrue("partial block parses",
             Partial.ParseJson(MapDocWithReadability(TEXT("\"readability\":{\"labelPlates\":true},")), Errors));
    const FS08BoardArtProfile* P = Partial.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("map"); });
    TestTrue("partial: only the label plates", P && P->Readability.bSet && P->Readability.bLabelPlates &&
                                                   !P->Readability.bReach && !P->Readability.bContactShadow &&
                                                   !P->Readability.bLeaderPip && !P->Readability.bFrameWood);
  }
  auto Expect = [this](const FString& Name, const FString& Doc, const FString& ErrorPart) {
    FS08BoardArtData Broken;
    TArray<FString> Errs;
    TestFalse(Name + TEXT(": rejected"), Broken.ParseJson(Doc, Errs));
    TestTrue(Name + TEXT(": reason '") + ErrorPart + TEXT("' in ") + FString::Join(Errs, TEXT(" | ")),
             FString::Join(Errs, TEXT(" | ")).Contains(ErrorPart));
  };
  {
    // grids never carry it (Cobble and the art fixtures stay bit for bit)
    FString OnGrid = S08MapTest::MapDoc();
    TestTrue("grid anchor present", OnGrid.Contains(TEXT("\"surface\":\"tiles\",")));
    OnGrid.ReplaceInline(TEXT("\"surface\":\"tiles\","), TEXT("\"surface\":\"tiles\",\"readability\":{\"labelPlates\":true},"));
    Expect(TEXT("readability on a grid"), OnGrid, TEXT("readability is for map-image boards only"));
  }
  auto Bad = [&](const FString& Name, const TCHAR* From, const TCHAR* To, const TCHAR* ErrorPart) {
    FString B = Block;
    TestTrue(Name + TEXT(": patch applies"), B.Contains(From));
    B.ReplaceInline(From, To);
    Expect(Name, MapDocWithReadability(B), ErrorPart);
  };
  Bad(TEXT("segments 8"), TEXT("\"segments\":48"), TEXT("\"segments\":8"), TEXT("readability.reach"));
  Bad(TEXT("segments 47.5"), TEXT("\"segments\":48"), TEXT("\"segments\":47.5"), TEXT("readability.reach"));
  Bad(TEXT("colour name"), TEXT("\"colorSrgb\":\"#FFC857\""), TEXT("\"colorSrgb\":\"gold\""), TEXT("readability.reach"));
  Bad(TEXT("ring off the circle"), TEXT("\"widthUU\":3.5,\"strokeUU\":1.0"), TEXT("\"widthUU\":6,\"strokeUU\":3"),
      TEXT("between r 30 and r 40"));
  Bad(TEXT("shadow diameter 500"), TEXT("\"diameterUU\":64"), TEXT("\"diameterUU\":500"), TEXT("readability.contactShadow"));
  Bad(TEXT("shadow strength 1.5"), TEXT("\"strength\":0.5"), TEXT("\"strength\":1.5"), TEXT("readability.contactShadow"));
  Bad(TEXT("frame V 0.1"), TEXT("\"valueScaleSrgb\":0.7"), TEXT("\"valueScaleSrgb\":0.1"), TEXT("readability.frameWood"));
  Bad(TEXT("label plates not a bool"), TEXT("\"labelPlates\":true"), TEXT("\"labelPlates\":\"yes\""),
      TEXT("readability.labelPlates"));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapGradeMaskTermsTest,
    "Unmatched.S08.BoardArt.MapGradeMaskTerms mapGrade maskSaturation / liftSaturation / maskInverseTintLinear (identity default, ranges)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMapGradeMaskTermsTest::RunTest(const FString&) {
  auto Doc = [](const FString& Grade) {
    FString D = MinimalDoc;
    D.ReplaceInline(TEXT("\"L\":{"), *(TEXT("\"L\":{\"mapGrade\":{") + Grade + TEXT("},")));
    return D;
  };
  const FString Base = TEXT("\"nightEV\":-0.35,\"nightSaturation\":0.75,\"lift\":1.65");
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue(TEXT("grade without mask terms: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Doc(Base), Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    TestTrue("identity mask terms by default", L && L->MapGrade.bSet && !L->MapGrade.HasMaskTerms() &&
                                                   L->MapGrade.MaskSaturation == 1.0f && L->MapGrade.LiftSaturation == 1.0f &&
                                                   L->MapGrade.MaskInverseTint == FLinearColor::White);
  }
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    const FString Terms =
        Base + TEXT(",\"maskSaturation\":1.5,\"liftSaturation\":1.6,\"maskInverseTintLinear\":[0.983,1.01,0.947]");
    TestTrue(TEXT("grade with mask terms: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(Doc(Terms), Errors));
    const FS08LightProfile* L = Data.Lights.Find(TEXT("L"));
    TestTrue("mask terms parsed", L && L->MapGrade.HasMaskTerms() && FMath::IsNearlyEqual(L->MapGrade.MaskSaturation, 1.5f) &&
                                      FMath::IsNearlyEqual(L->MapGrade.LiftSaturation, 1.6f) &&
                                      FMath::IsNearlyEqual(L->MapGrade.MaskInverseTint.B, 0.947f) &&
                                      FMath::IsNearlyEqual(L->MapGrade.Lift, 1.65f));
  }
  for (const TCHAR* BadTerm : {TEXT(",\"maskSaturation\":4"), TEXT(",\"liftSaturation\":-1"),
                               TEXT(",\"maskInverseTintLinear\":[1,1]"), TEXT(",\"maskSaturation\":\"high\"")}) {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    Data.ParseJson(Doc(Base + BadTerm), Errors);
    TestFalse(FString::Printf(TEXT("%s: profile rejected"), BadTerm), Data.Lights.Contains(TEXT("L")));
    TestTrue(FString::Printf(TEXT("%s: reason in %s"), BadTerm, *FString::Join(Errors, TEXT(" | "))),
             FString::Join(Errors, TEXT(" | ")).Contains(TEXT("mapGrade optional")));
  }
  // The shipped night profiles carry the P4 zone-separation terms (maskSaturation > 1 inside the game mask).
  FS08BoardArtData Shipped;
  TArray<FString> Errors;
  if (TestTrue("shipped data", LoadShipped(Shipped, Errors))) {
    for (const TCHAR* Id : {TEXT("marmoreal-night"), TEXT("sarpedon-night")}) {
      const FS08LightProfile* L = Shipped.Lights.Find(Id);
      TestTrue(FString::Printf(TEXT("%s: mask terms set (maskSaturation %.2f > 1, liftSaturation %.2f >= 1)"), Id,
                               L ? L->MapGrade.MaskSaturation : 0.0f, L ? L->MapGrade.LiftSaturation : 0.0f),
               L && L->MapGrade.bSet && L->MapGrade.HasMaskTerms() && L->MapGrade.MaskSaturation > 1.0f &&
                   L->MapGrade.LiftSaturation >= 1.0f);
    }
    for (const TPair<FString, FS08LightProfile>& Light : Shipped.Lights) {
      if (Light.Key.EndsWith(TEXT("-night"))) continue;
      TestFalse(Light.Key + TEXT(": grid light profiles carry no map grade"), Light.Value.MapGrade.bSet);
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtReadabilityGeometryTest,
    "Unmatched.S08.BoardArt.ReadabilityGeometry reach ring + stroke, leader pip and contact shadow stay between the team ring and the painted rim",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtReadabilityGeometryTest::RunTest(const FString&) {
  using namespace S08MapSurfaceSpec;
  // 1) without a reach block: exactly the 12-piece default ring, no stroke (the pre-P4 map ring, bit for bit)
  {
    FS08BoardReadabilitySpec Off;
    TArray<FTransform> Fill, Stroke, Legacy;
    S08ReachRingPieces(Off, Fill, Stroke);
    S08RingPieces(RingRadiusUU, RingWidthUU, RingSegments, RingZ, RingDepth, Legacy);
    bool bSame = Fill.Num() == Legacy.Num();
    for (int32 I = 0; bSame && I < Fill.Num(); ++I) bSame = Fill[I].Equals(Legacy[I], 0.0);
    TestTrue("no reach block: the default 12-piece ring exactly", bSame && Fill.Num() == 12);
    TestEqual("no reach block: no stroke", Stroke.Num(), 0);
  }
  // 2) the readability ring: 48 fill + 48 stroke pieces, between the team ring and the painted rim, stroke under fill
  FS08BoardReadabilitySpec On;
  On.bSet = On.bReach = true;
  TArray<FTransform> Fill, Stroke;
  S08ReachRingPieces(On, Fill, Stroke);
  TestEqual("48 fill pieces", Fill.Num(), 48);
  TestEqual("48 stroke pieces", Stroke.Num(), 48);
  auto Reach = [](const TArray<FTransform>& Pieces, double& OutInner, double& OutOuter, double& OutTop, double& OutBottom) {
    OutInner = TNumericLimits<double>::Max();
    OutOuter = 0.0;
    OutTop = -TNumericLimits<double>::Max();
    OutBottom = TNumericLimits<double>::Max();
    for (const FTransform& Piece : Pieces) {
      for (const FVector& C : {FVector(-50, -50, 50), FVector(50, -50, 50), FVector(50, 50, -50), FVector(-50, 50, -50)}) {
        const FVector P = Piece.TransformPosition(C);
        OutOuter = FMath::Max(OutOuter, FVector2D(P).Size());
        OutTop = FMath::Max(OutTop, P.Z);
        OutBottom = FMath::Min(OutBottom, P.Z);
      }
      OutInner = FMath::Min(OutInner, FVector2D(Piece.TransformPosition(FVector(0, -50, 0))).Size());
      OutInner = FMath::Min(OutInner, FVector2D(Piece.TransformPosition(FVector(0, 50, 0))).Size());
    }
  };
  double FillIn = 0.0, FillOut = 0.0, FillTop = 0.0, FillBottom = 0.0;
  double StrokeIn = 0.0, StrokeOut = 0.0, StrokeTop = 0.0, StrokeBottom = 0.0;
  Reach(Fill, FillIn, FillOut, FillTop, FillBottom);
  Reach(Stroke, StrokeIn, StrokeOut, StrokeTop, StrokeBottom);
  TestTrue(FString::Printf(TEXT("stroke outer %.2f < painted rim 41.6 - 1"), StrokeOut), StrokeOut < 40.6);
  TestTrue(FString::Printf(TEXT("stroke inner %.2f > team ring outer %.1f + 1"), StrokeIn, S08TeamRingSpec::P1RimOut1),
           StrokeIn > S08TeamRingSpec::P1RimOut1 + 1.0);
  TestTrue(FString::Printf(TEXT("stroke wider than the fill on both sides (%.2f..%.2f vs %.2f..%.2f)"), StrokeIn, StrokeOut,
                           FillIn, FillOut),
           StrokeIn < FillIn - 0.5 && StrokeOut > FillOut + 0.5);
  TestTrue(FString::Printf(TEXT("stroke top %.2f under the fill top %.2f, bottom %.2f above the team ring %.1f"), StrokeTop,
                           FillTop, StrokeBottom, S08TeamRingSpec::ZMax),
           StrokeTop < FillTop && StrokeBottom > S08TeamRingSpec::ZMax);
  // 3) leader pip: near side (+Y), just outside the team ring, inside the painted rim, keyline under the fill
  for (const float Scale : {1.0f, S08TeamRingSpec::SidekickScale}) {
    FTransform Pip, Key;
    S08LeaderPipTransforms(S08TeamRingSpec::P1RimOut1, Scale, Pip, Key);
    const double Radius = Pip.GetTranslation().Y;
    TestTrue(FString::Printf(TEXT("scale %.2f: pip on the near side, centre r %.2f = ring %.2f + gap"), Scale, Radius,
                             S08TeamRingSpec::P1RimOut1 * Scale),
             FMath::IsNearlyZero(Pip.GetTranslation().X) &&
                 FMath::IsNearlyEqual(Radius, S08TeamRingSpec::P1RimOut1 * Scale + LeaderPipGapUU, 1e-3));
    const double KeyHalfDiag = Key.GetScale3D().X * 50.0 * UE_SQRT_2;
    TestTrue(FString::Printf(TEXT("scale %.2f: pip reach %.2f inside the painted rim 41.6"), Scale, Radius + KeyHalfDiag),
             Radius + KeyHalfDiag < 41.6);
    TestTrue(FString::Printf(TEXT("scale %.2f: pip inner edge %.2f clear of the team ring %.2f"), Scale,
                             Radius - KeyHalfDiag, S08TeamRingSpec::P1RimOut1 * Scale),
             Radius - KeyHalfDiag > S08TeamRingSpec::P1RimOut1 * Scale - 0.01);
    const double PipTop = Pip.GetTranslation().Z + Pip.GetScale3D().Z * 50.0;
    const double KeyTop = Key.GetTranslation().Z + Key.GetScale3D().Z * 50.0;
    TestTrue("pip fill above its keyline", PipTop > KeyTop && Key.GetScale3D().X > Pip.GetScale3D().X);
    TestTrue("pip turned 45 deg (diamond)", FMath::IsNearlyEqual(Pip.Rotator().Yaw, 45.0, 1e-3));
  }
  // 4) contact shadow: between the map plane and the team ring, shifted along the key light, scaled with the ring
  FS08BoardReadabilitySpec Shadow;
  Shadow.bContactShadow = true;
  const FTransform Hero = S08ContactShadowTransform(Shadow, 1.0f);
  const FTransform Side = S08ContactShadowTransform(Shadow, S08TeamRingSpec::SidekickScale);
  TestTrue(FString::Printf(TEXT("blob z %.2f between the map plane %.1f and the team ring %.1f"), Hero.GetTranslation().Z,
                           PlaneZ, S08TeamRingSpec::ZMin),
           Hero.GetTranslation().Z > PlaneZ && Hero.GetTranslation().Z < S08TeamRingSpec::ZMin);
  TestTrue("blob 64 uu at ring scale 1", FMath::IsNearlyEqual(Hero.GetScale3D().X, 0.64, 1e-4));
  TestTrue("blob shifted to +X / +Y (the key light falls from W-NW)", Hero.GetTranslation().X > 0.0 && Hero.GetTranslation().Y > 0.0);
  TestTrue("sidekick blob scaled 0.78", FMath::IsNearlyEqual(Side.GetScale3D().X, 0.64 * S08TeamRingSpec::SidekickScale, 1e-4));
  // 5) the shipped data: only the two map-image boards carry the block, warm reach colour, darker frame
  FS08BoardArtData Shipped;
  TArray<FString> Errors;
  if (TestTrue("shipped data", LoadShipped(Shipped, Errors))) {
    int32 Maps = 0;
    for (const FS08BoardArtProfile& B : Shipped.Boards) {
      if (B.Surface != ES08BoardSurface::MapImage) {
        TestFalse(B.Id + TEXT(": grids carry no readability block"), B.Readability.bSet);
        continue;
      }
      ++Maps;
      const FS08BoardReadabilitySpec& R = B.Readability;
      TestTrue(B.Id + TEXT(": readability block with label plates, reach, contact shadow, leader pip, frame wood"),
               R.bSet && R.bLabelPlates && R.bReach && R.bContactShadow && R.bLeaderPip && R.bFrameWood);
      TestTrue(FString::Printf(TEXT("%s: reach >= 48 segments (%d)"), *B.Id, R.ReachSegments), R.ReachSegments >= 48);
      // not the mint green of the default ring: a warm colour (R > G > B) with a dark stroke
      TestTrue(FString::Printf(TEXT("%s: warm reach colour %s, dark stroke %s"), *B.Id, *S08ColorHex(R.ReachColor),
                               *S08ColorHex(R.ReachStroke)),
               R.ReachColor.R > R.ReachColor.G && R.ReachColor.G > R.ReachColor.B &&
                   R.ReachStroke.R + R.ReachStroke.G + R.ReachStroke.B < 120);
      TestTrue(FString::Printf(TEXT("%s: frame darker (V x %.2f, about -30 %%)"), *B.Id, R.FrameValueScaleSrgb),
               R.FrameValueScaleSrgb >= 0.6f && R.FrameValueScaleSrgb <= 0.8f && R.FrameSaturation < 1.0f);
    }
    TestEqual("two map-image profiles with readability", Maps, 2);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtReadabilityActorTest,
    "Unmatched.S08.BoardArt.ReadabilityActor map-image board: blob + leader pip on the fighters, label plates, frame wood; grey / grid boards none",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtReadabilityActorTest::RunTest(const FString&) {
  using namespace S08MapTest;
  using namespace S08ReadabilityTest;
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08BoardArtReadabilityActor")));
  if (!TestNotNull("test world", World)) return false;
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  auto Fighters = [](const FS08BoardModel& Board) {
    TArray<FS08BoardFighter> Out;
    for (int32 Y = 0; Y < Board.Height && Out.Num() < 2; ++Y) {
      for (int32 X = 0; X < Board.Width && Out.Num() < 2; ++X) {
        if (!Board.IsBoardSpace(X, Y)) continue;
        FS08BoardFighter F;
        F.Id = Out.Num() == 0 ? TEXT("f-0-hero") : TEXT("f-0-sk0");
        F.OwnerId = TEXT("host");
        F.Name = Out.Num() == 0 ? TEXT("Medusa") : TEXT("Harpies");
        F.Label = F.Name;
        F.bIsHero = Out.Num() == 0;
        F.Health = F.MaxHealth = 7;
        F.X = X;
        F.Y = Y;
        Out.Add(F);
      }
    }
    return Out;
  };
  // 1) grey topology view (no art data), a grid, and a refused map-image profile: no readability, no parts
  FS08BoardModel Topo;
  if (TestTrue("synthetic topology board", SyntheticTopology(Topo))) {
    AS08BoardActor* Grey = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                             FRotator::ZeroRotator);
    if (TestNotNull("board actor (grey)", Grey)) {
      TestTrue("rebuild", Grey->Rebuild(Topo));
      TestNull("grey: no active readability", Grey->GetActiveReadability());
      TestFalse("grey: no label plates", Grey->UsesLabelPlates());
      Grey->SyncFighters(Topo, Fighters(Topo), TEXT("host"));
      const AS08FighterActor* Hero = Grey->FindFighterActor(TEXT("f-0-hero"));
      TestTrue("grey: no blob / pip on the hero",
               Hero && !FindPart(Hero, TEXT("MapContactShadow")) && !FindPart(Hero, TEXT("MapLeaderPip")));
      FS08BoardArtData Data;
      TArray<FString> Errors;
      if (TestTrue("readability doc", Data.ParseJson(MapDocWithReadability(Block), Errors))) {
        Grey->SetArtDataForTest(Data);
        // a 3x2 grid matching the grid profile "one": the readability block of the map board never applies
        FS08BoardModel Grid = MakeBoard(3, 2);
        for (FS08Cell& Cell : Grid.Cells) Cell.Zones = {Cell.X == 0 ? TEXT("a") : TEXT("b")};
        TestTrue("rebuild grid", Grey->Rebuild(Grid));
        TestNull("grid: no active readability", Grey->GetActiveReadability());
        TestFalse("grid: no label plates", Grey->UsesLabelPlates());
        // the map profile refused (assets missing): no readability either
        Grey->SetRoomBoardId(TEXT("cidMap"));
        TestTrue("rebuild topology (assets missing)", Grey->Rebuild(Topo));
        TestFalse("refused map-image", Grey->IsMapImageActive());
        TestNull("refused map-image: no active readability", Grey->GetActiveReadability());
      }
      Grey->Destroy();
    }
  }
  // 2) the shipped Marmoreal profile once the map import ran: the block is active on the board and on the fighters
  FS08BoardArtData Shipped;
  TArray<FString> Errors;
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
      AddWarning(TEXT("map assets not imported: run tools/art/map_surface/ue_import_map_surface.py (ENV-U3: out of git); ")
                 TEXT("the map-image readability path of this test was NOT exercised"));
    } else {
      AS08BoardActor* Map = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                              FRotator::ZeroRotator);
      if (TestNotNull("board actor (map-image)", Map)) {
        Map->SetArtDataForTest(Shipped);
        Map->SetRoomBoardId(BoardId);
        TestTrue("rebuild Marmoreal", Map->Rebuild(Board));
        const FS08BoardReadabilitySpec* R = Map->GetActiveReadability();
        TestTrue("active readability = the profile block", R && R->bLabelPlates && R->bReach && R->bLeaderPip);
        TestTrue("label plates on", Map->UsesLabelPlates());
        const bool bWood = FPackageName::DoesPackageExist(TEXT("/Game/EnvMaps/M_MapFrameWood"));
        TestEqual("frame wood source", Map->GetMapFrameWoodSource(), FString(bWood ? TEXT("frame-wood") : TEXT("missing")));
        Map->SyncFighters(Board, Fighters(Board), TEXT("host"));
        const AS08FighterActor* Hero = Map->FindFighterActor(TEXT("f-0-hero"));
        const AS08FighterActor* Side = Map->FindFighterActor(TEXT("f-0-sk0"));
        TestTrue("the hero has the leader pip + keyline", Hero && FindPart(Hero, TEXT("MapLeaderPip")) &&
                                                             FindPart(Hero, TEXT("MapLeaderPipKeyline")));
        TestTrue("the sidekick has no leader pip", Side && !FindPart(Side, TEXT("MapLeaderPip")));
        if (FPackageName::DoesPackageExist(TEXT("/Game/EnvMaps/M_MapContactShadow"))) {
          TestTrue("hero and sidekick stand on a contact shadow",
                   FindPart(Hero, TEXT("MapContactShadow")) && FindPart(Side, TEXT("MapContactShadow")));
        } else {
          AddWarning(TEXT("M_MapContactShadow not imported (ue_import_map_surface.py): the blob part was NOT checked"));
        }
        // a second sync keeps one part each (no duplicates)
        Map->SyncFighters(Board, Fighters(Board), TEXT("host"));
        int32 Pips = 0;
        if (Hero) {
          TInlineComponentArray<UStaticMeshComponent*> Parts(Hero);
          for (const UStaticMeshComponent* Part : Parts) Pips += (Part && Part->GetFName() == FName(TEXT("MapLeaderPip"))) ? 1 : 0;
        }
        TestEqual("one leader pip after a resync", Pips, 1);
        // reachable readability rings around the sidekick's space: no crash, traced
        if (Side) Map->SetSelectedFighter(TEXT("f-0-hero"), {FS08BoardModel::CellKey(Side->GetFighter().X, Side->GetFighter().Y)});
        Map->Destroy();
      }
    }
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

// ---- ENV-MAPS P5 track C: heavy modular frame ASSET-MAP-FRAME-002 (gap 9 full) and the night backdrop (gap 8) ----
namespace S08FrameBackdropTest {
/** -ArtPreviewDiorama on / -ArtPreviewNoEnv off for the scope (the backdrop uses the env gate). */
struct FGate {
  FGate(bool bDiorama, bool bOptOut) {
    S08Diorama::SetFlagOverrideForTest(bDiorama);
    S08EnvLayout::SetOptOutOverrideForTest(bOptOut);
  }
  ~FGate() {
    S08Diorama::ResetFlagOverrideForTest();
    S08EnvLayout::ResetOptOutOverrideForTest();
  }
};

/** The map board's frame + backdrop blocks of the tests (the shipped Marmoreal values, the 2nd mist with defaults). */
const TCHAR* const Blocks = TEXT(
    "\"mapFrame\":{\"kit\":\"frame-002\",\"note\":\"test\"},"
    "\"backdrop\":{\"mist\":[{\"zUU\":-400,\"centerUU\":[0,-400],\"halfUU\":[2400,1600],\"colorLinear\":[0.7,0.8,1.15],"
    "\"opacity\":0.3,\"noiseScaleUU\":650,\"panUUPerSec\":[7,-2.5],\"edgeFade\":0.3,\"coverage\":0.42,\"seed\":3},"
    "{\"zUU\":-900,\"halfUU\":[2900,2100],\"opacity\":0.5}],"
    "\"moon\":{\"screenAnchor\":[-0.9,0.82],\"depthUU\":5200,\"diameterUU\":1800,\"colorLinear\":[0.72,0.8,1.0],"
    "\"intensity\":1.2,\"softness\":0.4,\"discRadius\":0.06,\"discIntensity\":2.5}},");

FString MapDocWith(const FString& Extra) {
  FString Doc = S08MapTest::MapDoc();
  Doc.ReplaceInline(S08MapTest::MapLightAnchor, *(FString(S08MapTest::MapLightAnchor) + Extra));
  return Doc;
}

FString FrameLayoutFile() {
  return FPaths::ConvertRelativePathToFull(FPaths::Combine(
      FPaths::ProjectDir(),
      TEXT("../../art/pipeline-candidates/ASSET-MAP-FRAME-002/20261001-frame-v1/reports/frame-layout.json")));
}

FString FramePackageOf(const TCHAR* ObjectPath) {
  FString Path(ObjectPath);
  int32 Dot = INDEX_NONE;
  return Path.FindLastChar(TEXT('.'), Dot) ? Path.Left(Dot) : Path;
}

bool FrameKitImported() {
  for (const ES08FrameModule M : {ES08FrameModule::Corner, ES08FrameModule::SegA, ES08FrameModule::SegB,
                                  ES08FrameModule::SegMid}) {
    if (!FPackageName::DoesPackageExist(FramePackageOf(S08FrameModulePath(M)))) return false;
  }
  return true;
}
}  // namespace S08FrameBackdropTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtMapFrameLayoutTest,
    "Unmatched.S08.BoardArt.MapFrameLayout frame-002: 20 modules, exact fit on the map, equal to the committed frame-layout.json",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtMapFrameLayoutTest::RunTest(const FString&) {
  using namespace S08MapTest;
  const FS08FrameLayout L = S08MapFrame002Layout(MapHalf);
  TestEqual("20 modules", L.Pieces.Num(), 20);
  TestTrue(FString::Printf(TEXT("5 x 157 along X, 3 x 157 along Y (got %d x %d)"), L.SegmentsX, L.SegmentsY),
           L.SegmentsX == 5 && L.SegmentsY == 3);
  TestTrue(FString::Printf(TEXT("exact fit (stretch %.8f x %.8f)"), L.StretchX, L.StretchY),
           L.bExactFit && FMath::Abs(L.StretchX - 1.0) < 1e-5 && FMath::Abs(L.StretchY - 1.0) < 1e-5);
  TMap<FString, int32> Counts;
  for (const FS08FramePiece& P : L.Pieces) Counts.FindOrAdd(S08FrameModuleName(P.Module)) += 1;
  TestTrue("4 corners, 4 A, 8 B, 4 Mid", Counts.FindRef(TEXT("Corner")) == 4 && Counts.FindRef(TEXT("A")) == 4 &&
                                             Counts.FindRef(TEXT("B")) == 8 && Counts.FindRef(TEXT("Mid")) == 4);
  // the corners sit on the inner map corners (pivot = the inner corner), yaw 0 / 90 / 180 / -90
  TestTrue("corner-near-east on (+X, +Y), yaw 0",
           L.Pieces[0].Id == TEXT("corner-near-east") && L.Pieces[0].Location.Equals(FVector(MapHalf.X, MapHalf.Y, 0.0), 1e-3) &&
               L.Pieces[0].YawDeg == 0.0f);
  TestTrue("corner-far-west on (-X, -Y), yaw 180",
           L.Pieces[2].Location.Equals(FVector(-MapHalf.X, -MapHalf.Y, 0.0), 1e-3) && L.Pieces[2].YawDeg == 180.0f);
  // each side: the segments run from the corner leg to the opposite leg without a gap, Mid in the middle
  const FS08FramePiece* Near0 = L.Pieces.FindByPredicate([](const FS08FramePiece& P) { return P.Id == TEXT("near-0"); });
  const FS08FramePiece* Near2 = L.Pieces.FindByPredicate([](const FS08FramePiece& P) { return P.Id == TEXT("near-2"); });
  const FS08FramePiece* East1 = L.Pieces.FindByPredicate([](const FS08FramePiece& P) { return P.Id == TEXT("east-1"); });
  TestTrue("near-0 = A at x -392.5 (the corner leg 53.1667 from -445.667)",
           Near0 && Near0->Module == ES08FrameModule::SegA && FMath::IsNearlyEqual(Near0->Location.X, -392.5, 1e-3));
  TestTrue("near-2 = Mid", Near2 && Near2->Module == ES08FrameModule::SegMid);
  TestTrue("east-1 = Mid at yaw -90", East1 && East1->Module == ES08FrameModule::SegMid && East1->YawDeg == -90.0f);
  // another map size: the nearest count and a stretch (the caller decides; the shipped maps never need it)
  const FS08FrameLayout Other = S08MapFrame002Layout(FVector2D(500.0, 300.0));
  TestTrue(FString::Printf(TEXT("another size: not exact, stretch %.4f x %.4f"), Other.StretchX, Other.StretchY),
           !Other.bExactFit && Other.StretchX > 0.8 && Other.StretchX < 1.2 && Other.StretchY > 0.8 && Other.StretchY < 1.2);
  // the C++ mirror == the committed layout of lane K (frame_layout.py placements())
  FString Text;
  const FString File = S08FrameBackdropTest::FrameLayoutFile();
  if (!FFileHelper::LoadFileToString(Text, *File)) {
    AddWarning(TEXT("frame-layout.json not found (") + File + TEXT("): the cross-check was NOT run"));
    return true;
  }
  TSharedPtr<FJsonObject> Root;
  FString Problem;
  if (!TestTrue(TEXT("frame-layout.json parses"), FS08Contracts::TryParseJsonObject(Text, Root, Problem) && Root.IsValid())) {
    return false;
  }
  const TArray<TSharedPtr<FJsonValue>>& Instances = Root->GetArrayField(TEXT("instances"));
  TestEqual("json: 20 instances", Instances.Num(), L.Pieces.Num());
  int32 Matched = 0;
  for (const TSharedPtr<FJsonValue>& V : Instances) {
    const TSharedPtr<FJsonObject> I = V->AsObject();
    const FString Id = I->GetStringField(TEXT("id"));
    const FS08FramePiece* P = L.Pieces.FindByPredicate([&Id](const FS08FramePiece& X) { return X.Id == Id; });
    const TArray<TSharedPtr<FJsonValue>>& Loc = I->GetArrayField(TEXT("loc"));
    const FVector JsonLoc(Loc[0]->AsNumber(), Loc[1]->AsNumber(), Loc[2]->AsNumber());
    const bool bOk = P && I->GetStringField(TEXT("module")) == S08FrameModuleName(P->Module) &&
                     P->Location.Equals(JsonLoc, 1e-3) &&
                     FMath::IsNearlyEqual(P->YawDeg, static_cast<float>(I->GetNumberField(TEXT("yawDeg"))), 1e-4f) &&
                     FMath::IsNearlyEqual(P->ScaleX, static_cast<float>(I->GetNumberField(TEXT("scaleX"))), 1e-6f);
    if (!bOk) {
      AddError(FString::Printf(TEXT("%s: C++ %s %s yaw %.1f != json %s %s yaw %.1f"), *Id,
                               P ? S08FrameModuleName(P->Module) : TEXT("-"), P ? *P->Location.ToString() : TEXT("-"),
                               P ? P->YawDeg : 0.0f, *I->GetStringField(TEXT("module")), *JsonLoc.ToString(),
                               I->GetNumberField(TEXT("yawDeg"))));
    }
    Matched += bOk ? 1 : 0;
  }
  TestEqual("every instance equal to the json", Matched, 20);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtFrameBackdropParserTest,
    "Unmatched.S08.BoardArt.FrameBackdropParser mapFrame / backdrop blocks: parsed, optional, map-image only, ranges, below the board",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtFrameBackdropParserTest::RunTest(const FString&) {
  using namespace S08FrameBackdropTest;
  using namespace S08MapSurfaceSpec;
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    if (!TestTrue(TEXT("map doc with frame + backdrop parses: ") + FString::Join(Errors, TEXT(" | ")),
                  Data.ParseJson(MapDocWith(Blocks), Errors))) {
      return false;
    }
    const FS08BoardArtProfile* Map = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("map"); });
    const FS08BoardArtProfile* Grid = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("one"); });
    if (TestNotNull("map profile", Map)) {
      TestTrue("mapFrame kit frame-002", Map->MapFrame.bSet && Map->MapFrame.Kit == Frame002Kit);
      const FS08BackdropSpec& B = Map->Backdrop;
      TestTrue("backdrop: 2 mist planes + moon", B.bSet && B.Mist.Num() == 2 && B.Moon.bSet);
      if (B.Mist.Num() == 2) {
        TestTrue("mist[0] values", B.Mist[0].ZUU == -400.0f && B.Mist[0].CenterUU.Equals(FVector2D(0.0, -400.0)) &&
                                       B.Mist[0].HalfUU.Equals(FVector2D(2400.0, 1600.0)) &&
                                       FMath::IsNearlyEqual(B.Mist[0].Opacity, 0.3f) &&
                                       B.Mist[0].PanUUPerSec.Equals(FVector2D(7.0, -2.5)) &&
                                       FMath::IsNearlyEqual(B.Mist[0].Coverage, 0.42f) && B.Mist[0].Seed == 3.0f);
        const FS08BackdropMistSpec Defaults;
        TestTrue("mist[1]: absent fields keep the defaults", B.Mist[1].ZUU == -900.0f &&
                                                                B.Mist[1].NoiseScaleUU == Defaults.NoiseScaleUU &&
                                                                B.Mist[1].CenterUU.Equals(Defaults.CenterUU) &&
                                                                FMath::IsNearlyEqual(B.Mist[1].Opacity, 0.5f));
      }
      TestTrue("moon values", B.Moon.ScreenAnchor.Equals(FVector2D(-0.9, 0.82), 1e-6) && B.Moon.DepthUU == 5200.0f &&
                                  B.Moon.DiameterUU == 1800.0f && FMath::IsNearlyEqual(B.Moon.Intensity, 1.2f) &&
                                  FMath::IsNearlyEqual(B.Moon.DiscIntensity, 2.5f));
    }
    TestTrue("the grid profile has neither block", Grid && !Grid->MapFrame.bSet && !Grid->Backdrop.bSet);
  }
  {
    FS08BoardArtData Data;
    TArray<FString> Errors;
    TestTrue("map doc without the blocks parses", Data.ParseJson(S08MapTest::MapDoc(), Errors));
    const FS08BoardArtProfile* Map = Data.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("map"); });
    TestTrue("absent blocks: off (bars + corners, no backdrop)", Map && !Map->MapFrame.bSet && !Map->Backdrop.bSet);
    FS08BoardArtData MoonOnly;
    TestTrue("moon-only backdrop parses",
             MoonOnly.ParseJson(MapDocWith(TEXT("\"backdrop\":{\"moon\":{}},")), Errors));
    const FS08BoardArtProfile* M = MoonOnly.Boards.FindByPredicate([](const FS08BoardArtProfile& B) { return B.Id == TEXT("map"); });
    TestTrue("moon only: no mist, default moon", M && M->Backdrop.bSet && M->Backdrop.Mist.IsEmpty() && M->Backdrop.Moon.bSet &&
                                                     M->Backdrop.Moon.DepthUU == FS08BackdropMoonSpec().DepthUU);
  }
  auto Expect = [this](const FString& Name, const FString& Doc, const FString& ErrorPart) {
    FS08BoardArtData Broken;
    TArray<FString> Errs;
    TestFalse(Name + TEXT(": rejected"), Broken.ParseJson(Doc, Errs));
    TestTrue(Name + TEXT(": reason '") + ErrorPart + TEXT("' in ") + FString::Join(Errs, TEXT(" | ")),
             FString::Join(Errs, TEXT(" | ")).Contains(ErrorPart));
  };
  {
    // grids never carry them (Cobble and the art fixtures stay bit for bit)
    for (const TCHAR* Block : {TEXT("\"mapFrame\":{\"kit\":\"frame-002\"},"), TEXT("\"backdrop\":{\"moon\":{}},")}) {
      FString OnGrid = S08MapTest::MapDoc();
      OnGrid.ReplaceInline(TEXT("\"surface\":\"tiles\","), *(FString(TEXT("\"surface\":\"tiles\",")) + Block));
      Expect(FString(TEXT("on a grid: ")) + Block, OnGrid, TEXT("is for map-image boards only"));
    }
  }
  auto Bad = [&](const FString& Name, const TCHAR* From, const TCHAR* To, const TCHAR* ErrorPart) {
    FString B = Blocks;
    TestTrue(Name + TEXT(": patch applies"), B.Contains(From));
    B.ReplaceInline(From, To);
    Expect(Name, MapDocWith(B), ErrorPart);
  };
  Bad(TEXT("unknown kit"), TEXT("\"kit\":\"frame-002\""), TEXT("\"kit\":\"frame-003\""), TEXT("mapFrame.kit"));
  Bad(TEXT("unknown mapFrame field"), TEXT("\"note\":\"test\""), TEXT("\"scale\":2"), TEXT("mapFrame.scale is not a field"));
  Bad(TEXT("mist above the tray"), TEXT("\"zUU\":-400"), TEXT("\"zUU\":-100"), TEXT("backdrop.mist[0]"));
  Bad(TEXT("mist zUU missing"), TEXT("\"zUU\":-900,"), TEXT(""), TEXT("backdrop.mist[1]"));
  Bad(TEXT("mist layers 50 uu apart"), TEXT("\"zUU\":-900"), TEXT("\"zUU\":-450"), TEXT("closer than 100"));
  Bad(TEXT("mist opacity 0"), TEXT("\"opacity\":0.3"), TEXT("\"opacity\":0"), TEXT("backdrop.mist[0]"));
  Bad(TEXT("mist opacity 0.9"), TEXT("\"opacity\":0.3"), TEXT("\"opacity\":0.9"), TEXT("backdrop.mist[0]"));
  Bad(TEXT("fast pan"), TEXT("\"panUUPerSec\":[7,-2.5]"), TEXT("\"panUUPerSec\":[700,-2.5]"), TEXT("backdrop.mist[0]"));
  Bad(TEXT("three mist planes"), TEXT("{\"zUU\":-900,"), TEXT("{\"zUU\":-1500},{\"zUU\":-900,"), TEXT("at most 2"));
  Bad(TEXT("moon too shallow (would reach over the board)"), TEXT("\"depthUU\":5200"), TEXT("\"depthUU\":1500"),
      TEXT("moon card reaches Z"));
  Bad(TEXT("moon anchor off screen"), TEXT("\"screenAnchor\":[-0.9,0.82]"), TEXT("\"screenAnchor\":[-1.5,0.82]"),
      TEXT("backdrop.moon"));
  Bad(TEXT("moon colour negative"), TEXT("\"colorLinear\":[0.72,0.8,1.0]"), TEXT("\"colorLinear\":[-1,0.8,1.0]"),
      TEXT("backdrop.moon"));
  Expect(TEXT("empty backdrop"), MapDocWith(TEXT("\"backdrop\":{},")), TEXT("at least one mist plane or the moon"));
  {
    // the modules are 24 uu wide: another frameUU is refused with the kit
    FString Doc = MapDocWith(TEXT("\"mapFrame\":{\"kit\":\"frame-002\"},"));
    TestTrue("frameUU anchor", Doc.Contains(TEXT("\"frameUU\":24")));
    Doc.ReplaceInline(TEXT("\"frameUU\":24"), TEXT("\"frameUU\":30"));
    Expect(TEXT("kit with frameUU 30"), Doc, TEXT("needs mapImage.frameUU 24"));
  }
  // the shipped data: both map-image boards ask for the kit; Marmoreal mist + moon; Sarpedon no backdrop (P5b tune: Track
  // B's opaque sea ring at z -172 hides everything below the island, the moon card was invisible)
  FS08BoardArtData Shipped;
  TArray<FString> Errors;
  if (TestTrue("shipped data", LoadShipped(Shipped, Errors))) {
    int32 Maps = 0;
    for (const FS08BoardArtProfile& B : Shipped.Boards) {
      if (B.Surface != ES08BoardSurface::MapImage) {
        TestFalse(B.Id + TEXT(": grids carry no mapFrame / backdrop"), B.MapFrame.bSet || B.Backdrop.bSet);
        continue;
      }
      ++Maps;
      TestTrue(B.Id + TEXT(": mapFrame frame-002"), B.MapFrame.bSet && B.MapFrame.Kit == Frame002Kit);
      if (B.Id == TEXT("sarpedon-original")) {
        TestFalse("sarpedon: no backdrop (the sea ring is under the island)", B.Backdrop.bSet);
        continue;
      }
      TestTrue(B.Id + TEXT(": backdrop with the moon"), B.Backdrop.bSet && B.Backdrop.Moon.bSet);
      TestTrue(B.Id + TEXT(": placement ok (everything below the board)"),
               S08BackdropPlacementProblem(B.Backdrop, B.Map.HalfUU()).IsEmpty());
      if (B.Id == TEXT("marmoreal-original")) TestEqual("marmoreal: 2 mist planes", B.Backdrop.Mist.Num(), 2);
    }
    TestEqual("two map-image profiles", Maps, 2);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtBackdropGeometryTest,
    "Unmatched.S08.BoardArt.BackdropGeometry K1 camera model, moon card in the upper-left of the far view and below the board, mist planes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtBackdropGeometryTest::RunTest(const FString&) {
  using namespace S08MapTest;
  using namespace S08MapSurfaceSpec;
  // the camera model = SetupCameraForBoard: looks at the origin, screen right = +X, screen up = the far side (-Y)
  const double K1 = S08K1OverviewDistanceUU(S08K1FitDistanceUU(MapHalf), 1.25f);
  const FS08BoardView View = FS08BoardView::AtDistance(K1);
  FVector2D Ndc;
  TestTrue("origin at the screen centre", View.Project(FVector::ZeroVector, Ndc) && Ndc.Equals(FVector2D::ZeroVector, 1e-6));
  TestTrue("+X is screen right", View.Project(FVector(300.0, 0.0, 0.0), Ndc) && Ndc.X > 0.1 && FMath::Abs(Ndc.Y) < 1e-6);
  TestTrue("-Y (far) is screen up", View.Project(FVector(0.0, -300.0, 0.0), Ndc) && Ndc.Y > 0.1);
  TestTrue("camera location (0, D cos 55, D sin 55)",
           View.Location.Equals(FVector(0.0, K1 * FMath::Cos(FMath::DegreesToRadians(55.0)), K1 * FMath::Sin(FMath::DegreesToRadians(55.0))), 0.01));
  // the map frame's far corners at K1 fit inside the screen (the K1 fit of S08K1FitDistanceUU)
  TestTrue("far-left frame corner on screen at K1", View.Project(FVector(-469.67, -312.67, 0.0), Ndc) &&
                                                         FMath::Abs(Ndc.X) < 1.0 && FMath::Abs(Ndc.Y) < 1.0);
  for (const FVector2D Anchor : {FVector2D(-0.9, 0.82), FVector2D(0.3, -0.4)}) {
    TestTrue(TEXT("ray / project round trip ") + Anchor.ToString(),
             View.Project(View.Location + View.Ray(Anchor) * 3000.0, Ndc) && Ndc.Equals(Anchor, 1e-6));
  }
  // the far zoom = fit / 0.65 = FS08CameraZoomConfig::OverviewOutRatio (2880.2 uu on the maps)
  const double Far = S08BackdropFarViewDistanceUU(MapHalf);
  TestTrue(FString::Printf(TEXT("far view %.2f = 2880.2 +- 0.5"), Far), FMath::Abs(Far - 2880.24) <= 0.5);
  TestEqual("BackdropFarViewRatio == the zoom's OverviewOutRatio", BackdropFarViewRatio, FS08CameraZoomConfig().OverviewOutRatio);
  // the shipped moon: on its anchor in the far view, facing the camera, round, below the board
  FS08BackdropMoonSpec Moon;
  Moon.bSet = true;
  double TopZ = 0.0;
  const FTransform Card = S08BackdropMoonTransform(Moon, MapHalf, &TopZ);
  const FS08BoardView FarView = FS08BoardView::AtDistance(Far);
  TestTrue(TEXT("moon centre on its anchor in the far view ") + Moon.ScreenAnchor.ToString(),
           FarView.Project(Card.GetTranslation(), Ndc) && Ndc.Equals(Moon.ScreenAnchor, 1e-4));
  TestTrue("moon anchor in the upper-left quadrant", Moon.ScreenAnchor.X < 0.0 && Moon.ScreenAnchor.Y > 0.0);
  TestTrue("card normal towards the camera (parallel to the screen)",
           Card.GetRotation().RotateVector(FVector::UpVector).Equals(-FarView.Forward, 1e-4));
  TestTrue("card local X = screen right (a round disc on screen)",
           Card.GetRotation().RotateVector(FVector::ForwardVector).Equals(FarView.Right, 1e-4));
  TestTrue("card scale = diameter / 100", Card.GetScale3D().Equals(FVector(Moon.DiameterUU / 100.0, Moon.DiameterUU / 100.0, 1.0), 1e-4));
  TestTrue(FString::Printf(TEXT("moon card top Z %.0f below %.0f (the board is always in front of it)"), TopZ, BackdropMaxZ),
           TopZ <= BackdropMaxZ);
  // the same card seen from K1 is behind the tray plane's far-left corner region: never in front of the frame
  TestTrue("moon centre farther from the K1 camera than the far frame corner",
           FVector::Dist(View.Location, Card.GetTranslation()) > FVector::Dist(View.Location, FVector(-469.67, -312.67, 0.0)));
  FS08BackdropSpec Spec;
  Spec.bSet = true;
  Spec.Moon = Moon;
  TestTrue("shipped-like moon: no placement problem", S08BackdropPlacementProblem(Spec, MapHalf).IsEmpty());
  Spec.Moon.DepthUU = 1500.0f;
  TestTrue("a shallow moon is refused", S08BackdropPlacementProblem(Spec, MapHalf).Contains(TEXT("moon card reaches Z")));
  // mist plane: the engine plane (100 uu) scaled to the size, flat, at its height
  FS08BackdropMistSpec Mist;
  Mist.ZUU = -400.0f;
  Mist.CenterUU = FVector2D(10.0, -400.0);
  Mist.HalfUU = FVector2D(2400.0, 1600.0);
  const FTransform Plane = S08BackdropMistTransform(Mist);
  TestTrue("mist plane at (cx, cy, z), flat", Plane.GetTranslation().Equals(FVector(10.0, -400.0, -400.0), 1e-6) &&
                                                Plane.GetRotation().Equals(FQuat::Identity, 1e-6));
  TestTrue("mist plane scale = half / 50", Plane.GetScale3D().Equals(FVector(48.0, 32.0, 1.0), 1e-6));
  Spec = FS08BackdropSpec();
  Spec.Mist = {Mist, Mist};
  Spec.Mist[1].ZUU = -470.0f;
  TestTrue("two mist planes 70 uu apart are refused", S08BackdropPlacementProblem(Spec, MapHalf).Contains(TEXT("closer than")));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardArtFrameBackdropActorTest,
    "Unmatched.S08.BoardArt.FrameBackdropActor frame-002 modules + backdrop parts on the map-image board only; grids / grey / refused none",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardArtFrameBackdropActorTest::RunTest(const FString&) {
  using namespace S08MapTest;
  using namespace S08FrameBackdropTest;
  FGate Gate(true, false);
  UWorld* World = UWorld::CreateWorld(EWorldType::Game, false, FName(TEXT("S08BoardArtFrameBackdropActor")));
  if (!TestNotNull("test world", World)) return false;
  FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
  Context.SetCurrentWorld(World);
  auto NoParts = [this](const AS08BoardActor* A, const TCHAR* What) {
    TestTrue(FString(What) + TEXT(": no frame modules, no backdrop parts"),
             A->GetMapFrameParts().IsEmpty() && A->GetBackdropParts().IsEmpty() && A->GetBackdropRuntime().MistPlanes == 0 &&
                 !A->GetBackdropRuntime().bMoon);
  };
  // 1) grids (Cobble-size, no art data) and the refused map-image profile: nothing, and a grid-only run traces nothing
  FS08BoardModel Topo;
  if (TestTrue("synthetic topology board", SyntheticTopology(Topo))) {
    AS08BoardActor* A = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                          FRotator::ZeroRotator);
    if (TestNotNull("board actor", A)) {
      TestTrue("env gate armed", A->EnsureEnvLayout(true));
      TestTrue("rebuild grid 5x6", A->Rebuild(MakeBoard(5, 6)));
      NoParts(A, TEXT("grid 5x6"));
      TestFalse("grid-only run: no backdrop line", A->GetBackdropRuntime().bTraced);
      TestTrue("grid: the frame kit source untouched (empty)", A->GetMapFrameKitSource().IsEmpty());
      FS08BoardArtData Data;
      TArray<FString> Errors;
      if (TestTrue(TEXT("doc with the blocks: ") + FString::Join(Errors, TEXT(" | ")), Data.ParseJson(MapDocWith(Blocks), Errors))) {
        A->SetArtDataForTest(Data);
        FS08BoardModel Grid = MakeBoard(3, 2);
        for (FS08Cell& Cell : Grid.Cells) Cell.Zones = {Cell.X == 0 ? TEXT("a") : TEXT("b")};
        TestTrue("rebuild the 3x2 grid profile", A->Rebuild(Grid));
        TestFalse("3x2 grid: not map-image", A->IsMapImageActive());
        NoParts(A, TEXT("grid 3x2 with the data"));
        A->SetRoomBoardId(TEXT("cidMap"));
        TestTrue("rebuild topology (map assets missing)", A->Rebuild(Topo));
        TestFalse("refused map-image", A->IsMapImageActive());
        NoParts(A, TEXT("refused map-image"));
      }
      A->Destroy();
    }
  }
  // 2) the shipped Marmoreal profile once the map import ran (out of git): kit + backdrop, then back to a grid
  FS08BoardArtData Shipped;
  TArray<FString> Errors;
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
      AddWarning(TEXT("map assets not imported: run tools/art/map_surface/ue_import_map_surface.py (ENV-U3: out of git); ")
                 TEXT("the frame-002 / backdrop actor path was NOT exercised"));
    } else {
      AS08BoardActor* A = World->SpawnActor<AS08BoardActor>(AS08BoardActor::StaticClass(), FVector::ZeroVector,
                                                            FRotator::ZeroRotator);
      if (TestNotNull("board actor (map-image)", A)) {
        TestTrue("env gate armed", A->EnsureEnvLayout(true));
        A->SetArtDataForTest(Shipped);
        A->SetRoomBoardId(BoardId);
        TestTrue("rebuild Marmoreal", A->Rebuild(Board));
        TestTrue("map-image active", A->IsMapImageActive());
        if (FrameKitImported()) {
          TestEqual("frame kit source", A->GetMapFrameKitSource(), FString(TEXT("frame-002")));
          TestEqual("20 modules", A->GetMapFrameParts().Num(), 20);
          TestEqual("no cube bars", A->GetArtSurfacePartCount(), 0);
          TestEqual("no ART-005 corners", A->GetArtCornerCount(), 0);
          const FS08FrameLayout Layout = S08MapFrame002Layout(Marmoreal->Map.HalfUU());
          int32 Placed = 0, WoodOnFrameWood = 0;
          for (int32 I = 0; I < A->GetMapFrameParts().Num() && I < Layout.Pieces.Num(); ++I) {
            const UStaticMeshComponent* Part = A->GetMapFrameParts()[I];
            if (!Part) continue;
            Placed += Part->GetRelativeLocation().Equals(Layout.Pieces[I].Location, 1e-3) &&
                              FMath::IsNearlyZero(FRotator::NormalizeAxis(Part->GetRelativeRotation().Yaw - Layout.Pieces[I].YawDeg), 1e-3) &&
                              Part->GetCollisionEnabled() == ECollisionEnabled::NoCollision
                          ? 1 : 0;
            const int32 WoodIndex = Part->GetMaterialIndex(FName(S08MapSurfaceSpec::Frame002WoodSlot));
            const UMaterialInterface* Wood = Part->GetMaterial(WoodIndex != INDEX_NONE ? WoodIndex : 0);
            WoodOnFrameWood += Wood && A->GetMapFrameWoodSource() == TEXT("frame-wood") &&
                                       Wood->GetMaterial() && Wood->GetMaterial()->GetName() == TEXT("M_MapFrameWood")
                                   ? 1 : 0;
          }
          TestEqual("every module at its layout transform, no collision", Placed, 20);
          if (A->GetMapFrameWoodSource() == TEXT("frame-wood")) {
            TestEqual("the wood slot of every module on the frameWood MID", WoodOnFrameWood, 20);
          }
        } else {
          AddWarning(TEXT("frame-002 not imported (tools/art/env_kit/ue_import_map_frame.py): the bars fallback was checked"));
          TestEqual("frame kit source 'missing'", A->GetMapFrameKitSource(), FString(TEXT("missing")));
          TestTrue("bars + corners kept", A->GetArtSurfacePartCount() == 4 && A->GetArtCornerCount() == 4 &&
                                              A->GetMapFrameParts().IsEmpty());
        }
        const bool bMaterials = FPackageName::DoesPackageExist(FramePackageOf(S08MapSurfaceSpec::BackdropMistMaterialPath)) &&
                                FPackageName::DoesPackageExist(FramePackageOf(S08MapSurfaceSpec::BackdropMoonMaterialPath));
        const FS08BackdropRuntime& Rt = A->GetBackdropRuntime();
        if (bMaterials) {
          TestEqual("backdrop status ok", Rt.Status, FString(TEXT("ok")));
          TestTrue("2 mist planes + the moon", A->GetBackdropParts().Num() == 3 && Rt.MistPlanes == 2 && Rt.bMoon);
          for (const UStaticMeshComponent* Part : A->GetBackdropParts()) {
            if (!Part) continue;
            const FBox Box = Part->Bounds.GetBox();
            TestTrue(FString::Printf(TEXT("%s below the board (max Z %.0f)"), *Part->GetName(), Box.Max.Z),
                     Box.Max.Z <= S08MapSurfaceSpec::BackdropMaxZ + 0.5);
            TestTrue(Part->GetName() + TEXT(": lights nothing (no shadow, no GI / DF), no collision"),
                     !Part->CastShadow && !Part->bAffectDynamicIndirectLighting && !Part->bAffectDistanceFieldLighting &&
                         Part->GetCollisionEnabled() == ECollisionEnabled::NoCollision);
            const UMaterialInterface* Mi = Part->GetMaterial(0);
            const UMaterial* Base = Mi ? Mi->GetMaterial() : nullptr;
            TestTrue(Part->GetName() + TEXT(": unlit, translucent / additive, Apply Fogging off"),
                     Base && Base->GetShadingModels().HasOnlyShadingModel(MSM_Unlit) &&
                         (Base->GetBlendMode() == BLEND_Translucent || Base->GetBlendMode() == BLEND_Additive) &&
                         !Base->bUseTranslucencyVertexFog);
          }
        } else {
          AddWarning(TEXT("backdrop materials not imported (ue_import_map_surface.py): the 'missing-material' path was checked"));
          TestEqual("backdrop status missing-material", Rt.Status, FString(TEXT("missing-material")));
          TestTrue("no backdrop part", A->GetBackdropParts().IsEmpty());
        }
        // the same board again keeps the parts; a grid afterwards clears everything
        const int32 Parts = A->GetBackdropParts().Num();
        TestTrue("rebuild a 5x6 grid", A->Rebuild(MakeBoard(5, 6)));
        NoParts(A, TEXT("grid after the map"));
        TestEqual("bars gone with the map", A->GetArtCornerCount(), 0);
        AddInfo(FString::Printf(TEXT("Marmoreal: frame %s, backdrop %s (%d parts)"), *A->GetMapFrameKitSource(), *Rt.Status, Parts));
        A->Destroy();
      }
    }
  }
  GEngine->DestroyWorldContext(World);
  World->DestroyWorld(false);
  return true;
}

#endif  // WITH_AUTOMATION_TESTS
