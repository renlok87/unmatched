// ART-005 / stage 3 T3.2 automation tests: data-driven board art (S08BoardArt.h).
// Pure functions only (no world): the shipped profile data, the parser's
// budget/shape validation, profile selection (board id, then signature), the
// Cobble 5x6 legacy geometry and lights kept exact, multizone cells keeping
// every zone, and the committed art fixtures (backend/prisma/fixtures/
// art-boards) decoded through FS08BoardModel::Decode against their profiles.
// T4.2: the zone MI / glyph mesh fields of the data, the glyph anchors, and
// (ZoneContent, editor assets) the MIs and glyph meshes themselves.
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.BoardArt; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardArt.h"
#include "S08BoardModel.h"
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
  TestEqual("three board profiles (Cobble + 2 fixtures)", Data.Boards.Num(), 3);
  for (const TPair<FString, FS08LightProfile>& Light : Data.Lights) {
    FString Reason;
    TestTrue(FString::Printf(TEXT("light %s budget: %s"), *Light.Key, *Reason), Light.Value.BudgetOk(Reason));
    TestTrue(FString::Printf(TEXT("light %s <= 6 points"), *Light.Key), Light.Value.Points.Num() <= 6);
    // W4-A: candela/lux units, SkyLight instead of a point fill, fixed exposure.
    TestTrue(FString::Printf(TEXT("light %s units candelas/lux"), *Light.Key), Light.Value.HasPhysicalUnits());
    TestTrue(FString::Printf(TEXT("light %s has a SkyLight"), *Light.Key), Light.Value.Sky.bSet);
    TestTrue(FString::Printf(TEXT("light %s fixed exposure"), *Light.Key),
             Light.Value.Exposure.bSet && Light.Value.Exposure.MinBrightness == Light.Value.Exposure.MaxBrightness);
    for (const FS08LightSpec& Point : Light.Value.Points) {
      TestFalse(FString::Printf(TEXT("light %s: no point fill ambient"), *Light.Key), Point.Role == TEXT("fill"));
    }
  }
  TestEqual("profile sha256 recorded", Data.SourceSha256.Len(), 64);
  for (const FS08BoardArtProfile& B : Data.Boards) {
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
    TestNotNull(FString::Printf(TEXT("%s: light profile present"), *B.Id), Data.LightFor(B));
    TestEqual(FString::Printf(TEXT("%s: expect.cells = W*H"), *B.Id), B.Expect.Cells, B.MatchWidth * B.MatchHeight);
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
  // Exact legacy transforms (S08BoardActor before T3.2) for one blue and one red cell.
  const FVector BlueWorld = Board.CellToWorld(1, 0);
  const FS08ZoneMarkPiece* BlueStroke = L.Strokes.FindByPredicate(
      [](const FS08ZoneMarkPiece& M) { return M.Cell == FIntPoint(1, 0); });
  if (TestNotNull("blue stroke", BlueStroke)) {
    TestTrue("blue edge position", BlueStroke->Transform.GetTranslation().Equals(BlueWorld + FVector(0, 46, 0.28f), 0.0f));
    TestTrue("blue edge scale", BlueStroke->Transform.GetScale3D().Equals(FVector(0.96f, 0.04f, 0.004f), 0.0f));
  }
  const FVector RedWorld = Board.CellToWorld(3, 4);
  int32 RedPieces = 0;
  for (const FS08ZoneMarkPiece& M : L.Strokes) {
    if (M.Cell != FIntPoint(3, 4)) continue;
    const float Offset = -32.0f + 32.0f * RedPieces++;
    TestTrue("red stroke position", M.Transform.GetTranslation().Equals(RedWorld + FVector(Offset, 46, 0.28f), 0.0f));
    TestTrue("red stroke scale", M.Transform.GetScale3D().Equals(FVector(0.28f, 0.045f, 0.004f), 0.0f));
  }
  TestEqual("three red strokes", RedPieces, 3);
  const FS08ZoneMarkPiece* Diamond = L.Glyphs.FindByPredicate(
      [](const FS08ZoneMarkPiece& M) { return M.Cell == FIntPoint(1, 0); });
  if (TestNotNull("blue diamond", Diamond)) {
    TestTrue("diamond at the near-left slot", Diamond->Transform.GetTranslation().Equals(BlueWorld + FVector(-32, 32, 0.28f), 0.0f));
    TestTrue("diamond rotated 45", Diamond->Transform.Rotator().Equals(FRotator(0, 45, 0), 0.01f));
  }
  // Probe lights: key 4.5 lux at (-350,-150,600) rot (0,-55,30) with shadow;
  // warm 85 cd. W4-A: the point fill (700) became the SkyLight, units are
  // candelas/lux, exposure fixed at EV100 1.3, key CSM 3000 uu / 2 cascades.
  const FS08LightProfile* Light = Data.LightFor(*P);
  if (TestNotNull("cobble light profile", Light)) {
    const TArray<FS08PlacedLight> Placed = S08PlaceLights(*Light, Board);
    if (TestEqual("1 directional + 1 point", Placed.Num(), 2)) {
      TestTrue("key", Placed[0].Spec.bDirectional && Placed[0].Position.Equals(FVector(-350, -150, 600)) &&
                          Placed[0].Spec.Rotation.Equals(FRotator(0, -55, 30)) &&
                          FMath::IsNearlyEqual(Placed[0].Spec.Intensity, 4.5f) && Placed[0].Spec.bCastShadows &&
                          !Placed[0].Spec.bHasColor);
      TestTrue("warm", Placed[1].Position.Equals(FVector(260, -300, 250)) &&
                           FMath::IsNearlyEqual(Placed[1].Spec.Intensity, 85.0f) &&
                           FMath::IsNearlyEqual(Placed[1].Spec.RadiusUU, 450.0f));
    }
    TestTrue("candelas/lux", Light->HasPhysicalUnits());
    TestTrue("sky from the ambient dome", Light->Sky.bSet && Light->Sky.CubemapPath == TEXT("/Game/S08/Render/TC_S08_AmbientDome"));
    TestTrue("exposure EV100 1.3 fixed", Light->Exposure.bSet && FMath::IsNearlyEqual(Light->Exposure.MinBrightness, 2.46229f) &&
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

#endif  // WITH_AUTOMATION_TESTS
