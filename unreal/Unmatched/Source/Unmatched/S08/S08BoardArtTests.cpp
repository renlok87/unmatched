// ART-005 / stage 3 T3.2 automation tests: data-driven board art (S08BoardArt.h).
// Pure functions only (no world): the shipped profile data, the parser's
// budget/shape validation, profile selection (board id, then signature), the
// Cobble 5x6 legacy geometry and lights kept exact, multizone cells keeping
// every zone, and the committed art fixtures (backend/prisma/fixtures/
// art-boards) decoded through FS08BoardModel::Decode against their profiles.
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08.BoardArt; Quit" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardArt.h"
#include "S08BoardModel.h"
#include "S08Contracts.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "HAL/FileManager.h"
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
  }
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
  // Probe lights: key 4.5 at (-350,-150,600) rot (0,-55,30) with shadow; fill 700; warm 85.
  const FS08LightProfile* Light = Data.LightFor(*P);
  if (TestNotNull("cobble light profile", Light)) {
    const TArray<FS08PlacedLight> Placed = S08PlaceLights(*Light, Board);
    if (TestEqual("1 directional + 2 points", Placed.Num(), 3)) {
      TestTrue("key", Placed[0].Spec.bDirectional && Placed[0].Position.Equals(FVector(-350, -150, 600)) &&
                          Placed[0].Spec.Rotation.Equals(FRotator(0, -55, 30)) &&
                          FMath::IsNearlyEqual(Placed[0].Spec.Intensity, 4.5f) && Placed[0].Spec.bCastShadows &&
                          !Placed[0].Spec.bHasColor);
      TestTrue("fill", Placed[1].Position.Equals(FVector(0, -100, 550)) &&
                           FMath::IsNearlyEqual(Placed[1].Spec.Intensity, 700.0f) &&
                           FMath::IsNearlyEqual(Placed[1].Spec.RadiusUU, 1800.0f) && !Placed[1].Spec.bCastShadows);
      TestTrue("warm", Placed[2].Position.Equals(FVector(260, -300, 250)) &&
                           FMath::IsNearlyEqual(Placed[2].Spec.Intensity, 85.0f) &&
                           FMath::IsNearlyEqual(Placed[2].Spec.RadiusUU, 450.0f));
    }
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

#endif  // WITH_AUTOMATION_TESTS
