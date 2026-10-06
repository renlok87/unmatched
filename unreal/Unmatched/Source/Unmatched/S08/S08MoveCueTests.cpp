// MS-T-15 (move selection, docs/game-design/move-selection/04 §4.6, §6.3, §9) automation tests:
//   Unmatched.S08.MoveAnim.CueSource (MS-AT-25, MS-R-48) - the path of a FighterMoved cue: the trail
//     metadata.lastMovement of the same seq; otherwise the canonical path on the positions BEFORE the
//     snapshot (no step limit); otherwise straight from -> to. Order in the seq, PLACE kind, trail
//     mismatch, a seq gap / barrier frame without cues, two maneuvers in a row, the turn indicator of a
//     same-seq turn pass. The animation half of MS-AT-25 (jump_to_final, Tomoe cascade, snap) is MS-T-16.
//   Unmatched.S08.MoveAnim.StartFrame (DE-021, SD-13, MS-R-22) - one ApplySnapshot gives the board sync, then the cues;
//     the own fighter's plan starts at 0 and leaves its start cell within one 60 FPS frame.
//   Unmatched.S08.MoveAnim.CueTrace (MS-AT-28 UE half, MS-R-60) - FS08MoveCueParams and the pose defaults
//     FS08MoveAnimParams == cue-table.json CUE-007 (DE-021 "code = cue-table"), the 04 §6.3 control values, the MS-CUE line format with map-space labels. Every MS-CUE
//     line is also logged (LogTemp Display), so `python tools/s08/cue_contract/cue_contract.py
//     check-trace <automation log>` re-checks steps, path and ms= against the table in Python.
// Headless: UnrealEditor-Cmd Unmatched.uproject -ExecCmds="Automation RunTests Unmatched.S08.MoveAnim"
#if WITH_AUTOMATION_TESTS

#include "S08BoardModel.h"
#include "S08Contracts.h"
#include "S08FlowController.h"
#include "S08MoveAnim.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace S08MoveCueTest {

const TCHAR* const Host = TEXT("p-host");
const TCHAR* const Guest = TEXT("p-guest");

TSharedPtr<FJsonValue> Json(const FString& Text) {
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  FS08Contracts::TryParseJsonValue(Text, Value, Problem);
  return Value;
}

FString Xy(const FIntPoint& Cell) { return FString::Printf(TEXT("{\"x\":%d,\"y\":%d}"), Cell.X, Cell.Y); }

/** W x H grid boardState (cells[y][x]); Obstacles are 'obstacle' cells. */
FString GridBoard(int32 W, int32 H, const TArray<FIntPoint>& Obstacles = {}) {
  TArray<FString> Rows;
  for (int32 Y = 0; Y < H; ++Y) {
    TArray<FString> Row;
    for (int32 X = 0; X < W; ++X) {
      Row.Add(FString::Printf(TEXT("{\"x\":%d,\"y\":%d,\"type\":\"%s\"}"), X, Y,
                              Obstacles.Contains(FIntPoint(X, Y)) ? TEXT("obstacle") : TEXT("normal")));
    }
    Rows.Add(TEXT("[") + FString::Join(Row, TEXT(",")) + TEXT("]"));
  }
  return FString::Printf(TEXT("{\"width\":%d,\"height\":%d,\"cells\":[%s]}"), W, H, *FString::Join(Rows, TEXT(",")));
}

/** A 3 x 1 lattice holding three map spaces A01 - A02 - A03 (links only
 *  between neighbours in that order; ENV-MAPS board-topology shape). */
FString ChainTopologyBoard() {
  TArray<FString> Cells;
  for (int32 X = 0; X < 3; ++X) {
    TArray<FString> Links;
    if (X > 0) Links.Add(Xy(FIntPoint(X - 1, 0)));
    if (X < 2) Links.Add(Xy(FIntPoint(X + 1, 0)));
    Cells.Add(FString::Printf(
        TEXT("{\"x\":%d,\"y\":0,\"type\":\"normal\",\"spaceId\":\"A0%d\",\"layout\":{\"x\":%d,\"y\":400},\"links\":[%s]}"),
        X, X + 1, 300 + X * 300, *FString::Join(Links, TEXT(","))));
  }
  return FString::Printf(TEXT("{\"width\":3,\"height\":1,\"cells\":[[%s]]}"), *FString::Join(Cells, TEXT(",")));
}

struct FF {
  FString Id;
  FString Owner;
  int32 X = -1;
  int32 Y = -1;
  int32 Hp = 5;
};

FString FightersJson(const TArray<FF>& Fighters) {
  TArray<FString> Items;
  for (const FF& F : Fighters) {
    Items.Add(FString::Printf(
        TEXT("{\"id\":\"%s\",\"ownerId\":\"%s\",\"name\":\"%s\",\"type\":\"HERO\",\"health\":%d,\"maxHealth\":5,")
        TEXT("\"movement\":2,\"position\":{\"x\":%d,\"y\":%d}}"),
        *F.Id, *F.Owner, *F.Id, F.Hp, F.X, F.Y));
  }
  return TEXT("[") + FString::Join(Items, TEXT(",")) + TEXT("]");
}

struct FTM {
  FString Id;
  FString Kind; // MOVE | PLACE
  FIntPoint From;
  TArray<FIntPoint> Path; // without the start
};

/** metadata with a lastMovement trail of TrailSeq (04 §4.3 shape). */
FString TrailMeta(int32 TrailSeq, const TArray<FTM>& Moves) {
  TArray<FString> Items;
  for (int32 I = 0; I < Moves.Num(); ++I) {
    TArray<FString> Cells;
    for (const FIntPoint& Cell : Moves[I].Path) Cells.Add(Xy(Cell));
    Items.Add(FString::Printf(TEXT("{\"order\":%d,\"fighterId\":\"%s\",\"kind\":\"%s\",\"from\":%s,\"path\":[%s]}"), I,
                              *Moves[I].Id, *Moves[I].Kind, *Xy(Moves[I].From), *FString::Join(Cells, TEXT(","))));
  }
  return FString::Printf(
      TEXT("{\"lastMovement\":{\"seq\":%d,\"playerId\":\"p-host\",\"source\":\"MANEUVER\",")
      TEXT("\"sourceRef\":\"maneuver:1:%d\",\"boost\":null,\"moves\":[%s]}}"),
      TrailSeq, TrailSeq - 1, *FString::Join(Items, TEXT(",")));
}

FS08Snapshot Snap(int32 Seq, const FString& Board, const TArray<FF>& Fighters, const FString& MetadataJson = FString(),
                  const TCHAR* TurnPlayer = Host) {
  FS08Snapshot S;
  S.SequenceNumber = Seq;
  S.Phase = TEXT("ACTION_MANEUVER");
  S.TurnCount = 1;
  S.CurrentTurnPlayerId = TurnPlayer;
  S.Players = Json(TEXT("[{\"userId\":\"p-host\"},{\"userId\":\"p-guest\"}]"));
  S.HandZones = Json(TEXT("{\"p-host\":[],\"p-guest\":[]}"));
  S.Fighters = Json(FightersJson(Fighters));
  if (!Board.IsEmpty()) S.BoardState = Json(Board);
  if (!MetadataJson.IsEmpty()) S.Metadata = Json(MetadataJson);
  return S;
}

/** graphql-transport-ws 'next' frame of gameStateUpdated (embedded JSON
 *  strings, no boardState: the applied board is kept by merge). */
FString WsFrame(int32 Seq, const TCHAR* TurnPlayer, const TArray<FF>& Fighters, const FString& MetadataJson) {
  TSharedRef<FJsonObject> Event = MakeShared<FJsonObject>();
  Event->SetNumberField(TEXT("sequenceNumber"), Seq);
  Event->SetStringField(TEXT("phase"), TEXT("ACTION_MANEUVER"));
  Event->SetNumberField(TEXT("turnCount"), 1);
  Event->SetStringField(TEXT("currentTurnPlayerId"), TurnPlayer);
  Event->SetStringField(TEXT("players"), TEXT("[{\"userId\":\"p-host\"},{\"userId\":\"p-guest\"}]"));
  Event->SetStringField(TEXT("fighters"), FightersJson(Fighters));
  Event->SetStringField(TEXT("handZones"), TEXT("{\"p-host\":[],\"p-guest\":[]}"));
  if (!MetadataJson.IsEmpty()) Event->SetStringField(TEXT("metadata"), MetadataJson);
  TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
  Data->SetObjectField(TEXT("gameStateUpdated"), Event);
  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  Payload->SetObjectField(TEXT("data"), Data);
  TSharedRef<FJsonObject> Frame = MakeShared<FJsonObject>();
  Frame->SetStringField(TEXT("type"), TEXT("next"));
  Frame->SetStringField(TEXT("id"), TEXT("s08-1"));
  Frame->SetObjectField(TEXT("payload"), Payload);
  FString Out;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Out);
  FJsonSerializer::Serialize(Frame, Writer);
  return Out;
}

/** Cue sets and MS-CUE lines of one controller; every MS-CUE line is also
 *  logged for the Python check-trace cross-check. */
struct FCueCapture {
  TArray<TArray<FS08Cue>> Sets;
  TArray<FString> CueLines;
  TArray<FString> Traces;
  void Bind(FS08FlowController& Flow) {
    Flow.OnCues.AddLambda([this](const TArray<FS08Cue>& Cues) { Sets.Add(Cues); });
    Flow.OnTrace.AddLambda([this](const FString& Line) {
      Traces.Add(Line);
      if (Line.StartsWith(TEXT("MS-CUE "))) {
        CueLines.Add(Line);
        UE_LOG(LogTemp, Display, TEXT("%s"), *Line);
      }
    });
  }
  bool SawTrace(const TCHAR* Needle) const {
    for (const FString& Line : Traces) {
      if (Line.Contains(Needle)) return true;
    }
    return false;
  }
};

const FS08Cue* MoveOf(const TArray<FS08Cue>& Set, const TCHAR* Id) {
  for (const FS08Cue& Cue : Set) {
    if (Cue.Type == ES08CueType::FighterMoved && Cue.FighterId == Id) return &Cue;
  }
  return nullptr;
}

int32 CountMoves(const TArray<FS08Cue>& Set) {
  int32 N = 0;
  for (const FS08Cue& Cue : Set) N += Cue.Type == ES08CueType::FighterMoved ? 1 : 0;
  return N;
}

FString CellsText(const TArray<FIntPoint>& Cells) {
  TArray<FString> Parts;
  for (const FIntPoint& Cell : Cells) Parts.Add(FString::Printf(TEXT("(%d,%d)"), Cell.X, Cell.Y));
  return FString::Join(Parts, TEXT(">"));
}

/** The canonical path WITH the start, on Board over the given fighters - the
 *  expectation is computed independently of the controller. */
bool ExpectCanonical(const FString& BoardJson, const TArray<FF>& Fighters, const TCHAR* Id, const FIntPoint& To,
                     TArray<FIntPoint>& Out) {
  FS08BoardModel Board;
  TArray<FS08BoardFighter> List;
  if (!Board.Decode(Json(BoardJson)) || !FS08BoardModel::DecodeFighters(Json(FightersJson(Fighters)), List)) {
    return false;
  }
  const FS08ReachMap Reach = FS08BoardModel::ComputeReachMap(Board, List, Id, MAX_int32);
  TArray<FIntPoint> Tail;
  if (!FS08BoardModel::BuildCanonicalPath(Board, List, Reach, To, Tail)) return false;
  Out = {Reach.Start};
  Out.Append(Tail);
  return true;
}

const FString* LineOf(const TArray<FString>& Lines, const TCHAR* FighterId) {
  const FString Needle = FString::Printf(TEXT(" fighter=%s "), FighterId);
  for (const FString& Line : Lines) {
    if (Line.Contains(Needle)) return &Line;
  }
  return nullptr;
}

} // namespace S08MoveCueTest

// ---- MS-AT-25: the source of the cue path ------------------------------------------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveCueSourceTest, "Unmatched.S08.MoveAnim.CueSource",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveCueSourceTest::RunTest(const FString&) {
  using namespace S08MoveCueTest;

  // (1) Trail of the same seq: the author's path as sent (not the canonical one), the trail order
  //     (PLACE first, then MOVE - not the fighters[] order), PLACE = one jump, damage after the moves.
  {
    const FString Board = GridBoard(5, 4);
    FS08FlowController Flow(TEXT("http://invalid"), TEXT("ws://invalid"), Guest);
    FCueCapture Cap;
    Cap.Bind(Flow);
    Flow.ApplySnapshot(Snap(10, Board,
                            {{TEXT("h1"), Host, 0, 0}, {TEXT("s1"), Host, 4, 0}, {TEXT("s2"), Host, 0, 3},
                             {TEXT("g1"), Guest, 4, 3}}));
    const TArray<FIntPoint> AuthorPath = {{1, 0}, {1, 1}, {2, 1}}; // canonical (K = (y,x)) passes (2,0) instead
    Flow.ApplySnapshot(Snap(11, Board,
                            {{TEXT("h1"), Host, 2, 1}, {TEXT("s1"), Host, 4, 2}, {TEXT("s2"), Host, 0, 3},
                             {TEXT("g1"), Guest, 4, 3, 3}},
                            TrailMeta(11, {{TEXT("s1"), TEXT("PLACE"), {4, 0}, {{4, 2}}},
                                           {TEXT("h1"), TEXT("MOVE"), {0, 0}, AuthorPath}})));
    TestEqual("(1) one cue set", Cap.Sets.Num(), 1);
    if (Cap.Sets.Num() == 1) {
      const TArray<FS08Cue>& Set = Cap.Sets[0];
      TestEqual("(1) two moves + one damage", Set.Num(), 3);
      const FS08Cue* H1 = MoveOf(Set, TEXT("h1"));
      const FS08Cue* S1 = MoveOf(Set, TEXT("s1"));
      TestTrue("(1) both moves present", H1 && S1);
      if (H1 && S1) {
        TestEqual("(1) h1 source trail", static_cast<uint8>(H1->PathSource), static_cast<uint8>(ES08PathSource::Trail));
        TestEqual("(1) h1 path = author's path with the start", CellsText(H1->Path),
                  TEXT("(0,0)>(1,0)>(1,1)>(2,1)"));
        TestEqual("(1) h1 steps", H1->Steps(), 3);
        TestEqual("(1) h1 order from the trail", H1->OrderInSeq, 1);
        TestEqual("(1) s1 kind place", static_cast<uint8>(S1->Kind), static_cast<uint8>(ES08MoveKind::Place));
        TestEqual("(1) s1 path [from, to]", CellsText(S1->Path), TEXT("(4,0)>(4,2)"));
        TestEqual("(1) s1 steps 1", S1->Steps(), 1);
        TestEqual("(1) s1 order 0", S1->OrderInSeq, 0);
        TestTrue("(1) moves come first in order", Set[0].FighterId == TEXT("s1") && Set[1].FighterId == TEXT("h1"));
        TestTrue("(1) damage last", Set[2].Type == ES08CueType::FighterDamaged && Set[2].FighterId == TEXT("g1"));
        TestEqual("(1) legacy from/to kept", FString::Printf(TEXT("(%d,%d)->(%d,%d)"), H1->FromX, H1->FromY, H1->ToX,
                                                             H1->ToY),
                  TEXT("(0,0)->(2,1)"));
      }
    }
    TestEqual("(1) one MS-CUE line per move", Cap.CueLines.Num(), 2);
    const FString* H1Line = LineOf(Cap.CueLines, TEXT("h1"));
    const FString* S1Line = LineOf(Cap.CueLines, TEXT("s1"));
    TestTrue("(1) h1 MS-CUE line", H1Line && H1Line->Contains(TEXT("order=1 of=2 kind=move steps=3 source=trail")) &&
                                       H1Line->Contains(TEXT("start=168 ms=840 snapped=0 path=(0,0)>(1,0)>(1,1)>(2,1)")));
    TestTrue("(1) s1 MS-CUE line", S1Line && S1Line->Contains(TEXT("seq=11 fighter=s1 order=0 of=2 kind=place steps=1")) &&
                                       S1Line->Contains(TEXT("source=trail start=0 ms=240 snapped=0 path=(4,0)>(4,2)")));
    // HTTP echo + WS of the same seq: one cue set (QA-007).
    Flow.ApplySnapshot(Snap(11, Board,
                            {{TEXT("h1"), Host, 2, 1}, {TEXT("s1"), Host, 4, 2}, {TEXT("s2"), Host, 0, 3},
                             {TEXT("g1"), Guest, 4, 3, 3}}));
    TestEqual("(1) same-seq duplicate fires nothing", Cap.Sets.Num(), 1);
    TestEqual("(1) and writes no MS-CUE", Cap.CueLines.Num(), 2);
  }

  // (2) No trail of this seq (an ability / reaction / admin move; the trail is seq 20's) -> canonical on the
  //     positions BEFORE the snapshot, with no step limit (6 steps > movement 2). The enemy e1 stood on
  //     (2,1) before and moved away in the same seq: the path goes around (2,1); on the NEW positions the
  //     canonical path would cross it.
  {
    const FString Board = GridBoard(5, 3);
    const TArray<FF> Old = {{TEXT("m1"), Host, 0, 1}, {TEXT("e1"), Guest, 2, 1}};
    const TArray<FF> New = {{TEXT("m1"), Host, 4, 1}, {TEXT("e1"), Guest, 2, 0}};
    FS08FlowController Flow(TEXT("http://invalid"), TEXT("ws://invalid"), Guest);
    FCueCapture Cap;
    Cap.Bind(Flow);
    Flow.ApplySnapshot(Snap(20, Board, Old));
    Flow.ApplySnapshot(Snap(21, Board, New, TrailMeta(20, {{TEXT("m1"), TEXT("MOVE"), {0, 0}, {{0, 1}}}})));
    TArray<FIntPoint> Expected, OnNew;
    TestTrue("(2) expectation computable", ExpectCanonical(Board, Old, TEXT("m1"), {4, 1}, Expected));
    TArray<FF> NewWithM1AtStart = New;
    NewWithM1AtStart[0].X = 0;
    NewWithM1AtStart[0].Y = 1;
    TestTrue("(2) new-position path computable", ExpectCanonical(Board, NewWithM1AtStart, TEXT("m1"), {4, 1}, OnNew));
    const FS08Cue* M1 = Cap.Sets.Num() == 1 ? MoveOf(Cap.Sets[0], TEXT("m1")) : nullptr;
    const FS08Cue* E1 = Cap.Sets.Num() == 1 ? MoveOf(Cap.Sets[0], TEXT("e1")) : nullptr;
    TestTrue("(2) both moves", M1 && E1);
    if (M1 && E1) {
      TestEqual("(2) m1 canonical", static_cast<uint8>(M1->PathSource), static_cast<uint8>(ES08PathSource::Canonical));
      TestFalse("(2) a trail of another seq is no mismatch", M1->bTrailMismatch);
      TestEqual("(2) m1 path = canonical on the old positions", CellsText(M1->Path), CellsText(Expected));
      TestEqual("(2) six steps (no step limit)", M1->Steps(), 6);
      TestFalse("(2) path avoids the old enemy cell", M1->Path.Contains(FIntPoint(2, 1)));
      TestTrue("(2) the new positions would give another path", CellsText(OnNew) != CellsText(M1->Path));
      TestEqual("(2) e1 canonical one step", CellsText(E1->Path), TEXT("(2,1)>(2,0)"));
      TestEqual("(2) untracked fighters in fighters[] order", M1->OrderInSeq, 0);
      TestEqual("(2) e1 second", E1->OrderInSeq, 1);
    }
    TestTrue("(2) MS-CUE canonical traced", Cap.CueLines.Num() == 2 && Cap.CueLines[0].Contains(TEXT("source=canonical")));
  }

  // (3) A save without lastMovement (MS-E-108) / metadata without the field -> canonical.
  {
    const FString Board = GridBoard(5, 3);
    const TArray<FF> Old = {{TEXT("m1"), Host, 0, 0}};
    FS08FlowController Flow(TEXT("http://invalid"), TEXT("ws://invalid"), Guest);
    FCueCapture Cap;
    Cap.Bind(Flow);
    Flow.ApplySnapshot(Snap(30, Board, Old, TEXT("{}")));
    Flow.ApplySnapshot(Snap(31, Board, {{TEXT("m1"), Host, 1, 1}}, TEXT("{\"pendingManeuver\":null}")));
    TArray<FIntPoint> Expected;
    ExpectCanonical(Board, Old, TEXT("m1"), {1, 1}, Expected);
    const FS08Cue* M1 = Cap.Sets.Num() == 1 ? MoveOf(Cap.Sets[0], TEXT("m1")) : nullptr;
    TestTrue("(3) cue", M1 != nullptr);
    if (M1) {
      TestEqual("(3) canonical", static_cast<uint8>(M1->PathSource), static_cast<uint8>(ES08PathSource::Canonical));
      TestEqual("(3) path", CellsText(M1->Path), CellsText(Expected));
      TestEqual("(3) K tie-break (y, x): through (1,0)", CellsText(M1->Path), TEXT("(0,0)>(1,0)>(1,1)"));
    }
    // A body without metadata at all (partial) is "no trail" too, even though the store keeps older metadata.
    Flow.ApplySnapshot(Snap(32, Board, {{TEXT("m1"), Host, 2, 1}}));
    const FS08Cue* M2 = Cap.Sets.Num() == 2 ? MoveOf(Cap.Sets[1], TEXT("m1")) : nullptr;
    TestTrue("(3) partial body cue canonical",
             M2 && M2->PathSource == ES08PathSource::Canonical && CellsText(M2->Path) == TEXT("(1,1)>(2,1)"));
  }

  // (4) No path at all on the old positions (a wall column between from and to) -> straight from -> to.
  {
    const FString Board = GridBoard(5, 3, {{2, 0}, {2, 1}, {2, 2}});
    FS08FlowController Flow(TEXT("http://invalid"), TEXT("ws://invalid"), Guest);
    FCueCapture Cap;
    Cap.Bind(Flow);
    Flow.ApplySnapshot(Snap(40, Board, {{TEXT("m1"), Host, 0, 1}}));
    Flow.ApplySnapshot(Snap(41, Board, {{TEXT("m1"), Host, 4, 1}}));
    const FS08Cue* M1 = Cap.Sets.Num() == 1 ? MoveOf(Cap.Sets[0], TEXT("m1")) : nullptr;
    TestTrue("(4) cue", M1 != nullptr);
    if (M1) {
      TestEqual("(4) straight", static_cast<uint8>(M1->PathSource), static_cast<uint8>(ES08PathSource::Straight));
      TestEqual("(4) path from -> to", CellsText(M1->Path), TEXT("(0,1)>(4,1)"));
      TestEqual("(4) one step", M1->Steps(), 1);
    }
    TestTrue("(4) MS-CUE straight", Cap.CueLines.Num() == 1 &&
                                        Cap.CueLines[0].Contains(TEXT("steps=1 source=straight start=0 ms=280")));
  }

  // (5) The trail of this seq lists another fighter only -> that one from the trail (first), the other
  //     canonical (after it); (6) a trail entry that does not end where the snapshot puts the fighter
  //     (an ability moved it further in the same seq) -> canonical, trail order kept, trace trail=mismatch.
  {
    const FString Board = GridBoard(5, 3);
    FS08FlowController Flow(TEXT("http://invalid"), TEXT("ws://invalid"), Guest);
    FCueCapture Cap;
    Cap.Bind(Flow);
    Flow.ApplySnapshot(Snap(50, Board, {{TEXT("m1"), Host, 0, 0}, {TEXT("m2"), Host, 0, 2}}));
    Flow.ApplySnapshot(Snap(51, Board, {{TEXT("m1"), Host, 1, 0}, {TEXT("m2"), Host, 1, 2}},
                            TrailMeta(51, {{TEXT("m2"), TEXT("MOVE"), {0, 2}, {{1, 2}}}})));
    const FS08Cue* M1 = Cap.Sets.Num() == 1 ? MoveOf(Cap.Sets[0], TEXT("m1")) : nullptr;
    const FS08Cue* M2 = Cap.Sets.Num() == 1 ? MoveOf(Cap.Sets[0], TEXT("m2")) : nullptr;
    TestTrue("(5) both", M1 && M2);
    if (M1 && M2) {
      TestEqual("(5) listed fighter from the trail", static_cast<uint8>(M2->PathSource),
                static_cast<uint8>(ES08PathSource::Trail));
      TestEqual("(5) unlisted fighter canonical", static_cast<uint8>(M1->PathSource),
                static_cast<uint8>(ES08PathSource::Canonical));
      TestEqual("(5) trail entry first", M2->OrderInSeq, 0);
      TestEqual("(5) untracked after", M1->OrderInSeq, 1);
    }
    Flow.ApplySnapshot(Snap(52, Board, {{TEXT("m1"), Host, 4, 0}, {TEXT("m2"), Host, 1, 2}},
                            TrailMeta(52, {{TEXT("m1"), TEXT("MOVE"), {1, 0}, {{2, 0}, {3, 0}}}})));
    const FS08Cue* Mis = Cap.Sets.Num() == 2 ? MoveOf(Cap.Sets[1], TEXT("m1")) : nullptr;
    TestTrue("(6) cue", Mis != nullptr);
    if (Mis) {
      TestEqual("(6) mismatch -> canonical", static_cast<uint8>(Mis->PathSource),
                static_cast<uint8>(ES08PathSource::Canonical));
      TestTrue("(6) flagged", Mis->bTrailMismatch);
      TestEqual("(6) canonical to the snapshot cell", CellsText(Mis->Path), TEXT("(1,0)>(2,0)>(3,0)>(4,0)"));
    }
    TestTrue("(6) trace", Cap.CueLines.Num() == 3 && Cap.CueLines[2].EndsWith(TEXT(" trail=mismatch")));
  }

  // (7) Seq gap / barrier frame: no cue, no MS-CUE (snap - MS-E-71); then live frames with trails: two
  //     opponent maneuvers in a row (each its own trail, MS-E-72); the next seq without a fresh trail is
  //     canonical; a same-seq turn pass switches the turn indicator BEFORE the cues fire (MS-E-45).
  {
    const FString Board = GridBoard(5, 3);
    FS08FlowController Flow(TEXT("http://invalid"), TEXT("ws://test.invalid"), Guest);
    FCueCapture Cap;
    Cap.Bind(Flow);
    FString TurnAtCue;
    bool bMyTurnAtCue = true;
    Flow.OnCues.AddLambda([&](const TArray<FS08Cue>&) {
      TurnAtCue = Flow.GetAppliedSnapshot().CurrentTurnPlayerId;
      bMyTurnAtCue = Flow.IsMyTurn();
    });
    Flow.ApplySnapshot(Snap(60, Board, {{TEXT("m1"), Host, 0, 0}}));
    Flow.ApplySnapshot(Snap(62, Board, {{TEXT("m1"), Host, 1, 0}}, TrailMeta(62, {{TEXT("m1"), TEXT("MOVE"), {0, 0}, {{1, 0}}}})));
    TestEqual("(7) gap: no cue", Cap.Sets.Num(), 0);
    TestEqual("(7) gap: no MS-CUE", Cap.CueLines.Num(), 0);
    TestTrue("(7) gap traced", Cap.SawTrace(TEXT("gap from 60")));

    Flow.AttachStreamHarnessForTest(TEXT("g1")); // the next WS frame is the subscription's barrier
    Flow.InjectWsFrameForTest(WsFrame(63, Host, {{TEXT("m1"), Host, 2, 0}},
                                      TrailMeta(63, {{TEXT("m1"), TEXT("MOVE"), {1, 0}, {{2, 0}}}})));
    TestEqual("(7) barrier applied", Flow.GetAppliedSnapshot().SequenceNumber, 63);
    TestEqual("(7) barrier frame: no cue", Cap.Sets.Num(), 0);
    TestEqual("(7) barrier frame: no MS-CUE", Cap.CueLines.Num(), 0);

    // Maneuver 1 of the opponent (host) - a live frame; the board comes from the applied store.
    Flow.InjectWsFrameForTest(WsFrame(64, Host, {{TEXT("m1"), Host, 2, 2}},
                                      TrailMeta(64, {{TEXT("m1"), TEXT("MOVE"), {2, 0}, {{3, 0}, {3, 1}, {3, 2}, {2, 2}}}})));
    // Maneuver 2 replaces the trail; it is the host's last action: the turn passes in the same seq.
    Flow.InjectWsFrameForTest(WsFrame(65, Guest, {{TEXT("m1"), Host, 0, 2}},
                                      TrailMeta(65, {{TEXT("m1"), TEXT("MOVE"), {2, 2}, {{1, 2}, {0, 2}}}})));
    TestEqual("(7) two live sets", Cap.Sets.Num(), 2);
    const FS08Cue* First = Cap.Sets.Num() >= 1 ? MoveOf(Cap.Sets[0], TEXT("m1")) : nullptr;
    const FS08Cue* Second = Cap.Sets.Num() >= 2 ? MoveOf(Cap.Sets[1], TEXT("m1")) : nullptr;
    TestTrue("(7) maneuver 1 = its trail (detour, not canonical)",
             First && First->PathSource == ES08PathSource::Trail &&
                 CellsText(First->Path) == TEXT("(2,0)>(3,0)>(3,1)>(3,2)>(2,2)"));
    TestTrue("(7) maneuver 2 = its own trail",
             Second && Second->PathSource == ES08PathSource::Trail && CellsText(Second->Path) == TEXT("(2,2)>(1,2)>(0,2)"));
    TestEqual("(7) turn indicator already switched at the cue", TurnAtCue, FString(Guest));
    TestTrue("(7) viewer's turn by the snapshot at the cue", bMyTurnAtCue);
    // An ability moves the fighter in seq 66; lastMovement is still seq 65's -> canonical.
    Flow.InjectWsFrameForTest(WsFrame(66, Guest, {{TEXT("m1"), Host, 0, 1}},
                                      TrailMeta(65, {{TEXT("m1"), TEXT("MOVE"), {2, 2}, {{1, 2}, {0, 2}}}})));
    const FS08Cue* Third = Cap.Sets.Num() >= 3 ? MoveOf(Cap.Sets[2], TEXT("m1")) : nullptr;
    TestTrue("(7) stale trail -> canonical", Third && Third->PathSource == ES08PathSource::Canonical &&
                                                 CellsText(Third->Path) == TEXT("(0,2)>(0,1)"));
    TestEqual("(7) one MS-CUE per live move", Cap.CueLines.Num(), 3);
  }
  return true;
}

// ---- MS-AT-28 (UE half): CUE-007 timing contract and the MS-CUE line ---------------------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveCueTraceTest, "Unmatched.S08.MoveAnim.CueTrace",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveCueTraceTest::RunTest(const FString&) {
  using namespace S08MoveCueTest;

  // ---- the code defaults ARE cue-table.json CUE-007 ----
  {
    const FString Path = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/unreal/contracts/cue-dispatcher/cue-table.json")));
    FString Text;
    TSharedPtr<FJsonObject> Table;
    TestTrue("cue-table.json read", FFileHelper::LoadFileToString(Text, *Path));
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    TestTrue("cue-table.json parses", FJsonSerializer::Deserialize(Reader, Table) && Table.IsValid());
    const TArray<TSharedPtr<FJsonValue>>* Cues = nullptr;
    TSharedPtr<FJsonObject> Row;
    if (Table.IsValid() && Table->TryGetArrayField(TEXT("cues"), Cues)) {
      for (const TSharedPtr<FJsonValue>& Value : *Cues) {
        const TSharedPtr<FJsonObject> Candidate = Value.IsValid() ? Value->AsObject() : nullptr;
        if (Candidate.IsValid() && Candidate->GetStringField(TEXT("id")) == TEXT("CUE-007")) Row = Candidate;
      }
    }
    TestTrue("CUE-007 row", Row.IsValid());
    if (Row.IsValid()) {
      const FS08MoveCueParams P;
      auto Field = [&Row](const TCHAR* Name) {
        double V = -1.0;
        Row->TryGetNumberField(Name, V);
        return V;
      };
      TestEqual("duration_per_step_ms", Field(TEXT("duration_per_step_ms")), P.StepMs);
      TestEqual("cap_subject_ms", Field(TEXT("cap_subject_ms")), P.CapSubjectMs);
      TestEqual("cap_seq_ms", Field(TEXT("cap_seq_ms")), P.CapSeqMs);
      TestEqual("min_step_ms", Field(TEXT("min_step_ms")), P.MinStepMs);
      TestEqual("overlap", Field(TEXT("overlap")), P.Overlap);
      TestEqual("place_ms", Field(TEXT("place_ms")), P.PlaceMs);
      // DE-021 (W-12; 01 F-02, D-DE-02): the pose defaults of the move ARE the table's CUE-007 pose
      const TSharedPtr<FJsonObject>* Pose = nullptr;
      TestTrue("pose block", Row->TryGetObjectField(TEXT("pose"), Pose));
      if (Pose) {
        const FS08MoveAnimParams A;
        auto PoseField = [&Pose](const TCHAR* Name) {
          double V = -1.0;
          (*Pose)->TryGetNumberField(Name, V);
          return V;
        };
        bool bEase = true;
        (*Pose)->TryGetBoolField(TEXT("ease_ends"), bEase);
        TestEqual("pose.hop_height_rel (D-DE-02: 0)", PoseField(TEXT("hop_height_rel")), A.HopHeightRel);
        TestEqual("pose.travel_lean_deg", PoseField(TEXT("travel_lean_deg")), A.TravelLeanDeg);
        TestEqual("pose.lean_in_ms", PoseField(TEXT("lean_in_ms")), A.LeanInMs);
        TestEqual("pose.start_turn_ms", PoseField(TEXT("start_turn_ms")), A.StartTurnMs);
        TestEqual("pose.turn_ms", PoseField(TEXT("turn_ms")), A.TurnMs);
        TestEqual("pose.settle_ms", PoseField(TEXT("settle_ms")), A.SettleMs);
        TestEqual("pose.ease_ends", bEase, A.bEaseEnds);
        TestEqual("D-DE-02: no hop by default", A.HopHeightRel, 0.0);
      }
      const TSharedPtr<FJsonObject>* Params = nullptr;
      TestTrue("params.path and order_in_seq documented",
               Row->TryGetObjectField(TEXT("params"), Params) && (*Params)->HasField(TEXT("path")) &&
                   (*Params)->HasField(TEXT("order_in_seq")));
    }
  }

  // ---- 04 §6.3 control values (±1 ms) ----
  auto Moves = [](int32 Count, int32 Steps, ES08MoveKind Kind = ES08MoveKind::Move) {
    TArray<FS08MoveCueInput> Out;
    for (int32 I = 0; I < Count; ++I) {
      FS08MoveCueInput Input;
      Input.Kind = Kind;
      Input.Steps = Steps;
      Out.Add(Input);
    }
    return Out;
  };
  auto End = [](const FS08MoveCueTiming& T) { return T.StartMs + T.DurationMs; };
  {
    const TArray<FS08MoveCueTiming> One = FS08MoveCueSchedule::Compute(Moves(1, 1));
    TestTrue("1 step = 280", FMath::IsNearlyEqual(One[0].DurationMs, 280.0, 1.0));
    const TArray<FS08MoveCueTiming> Nine = FS08MoveCueSchedule::Compute(Moves(1, 9));
    TestTrue("9 steps = 1400", FMath::IsNearlyEqual(Nine[0].DurationMs, 1400.0, 1.0));
    TestTrue("9 steps: 155.6 per step", FMath::IsNearlyEqual(Nine[0].StepMs, 155.6, 0.1));
    const TArray<FS08MoveCueTiming> Four = FS08MoveCueSchedule::Compute(Moves(4, 7));
    TestTrue("4x7 Normal ends at 2400", FMath::IsNearlyEqual(End(Four[3]), 2400.0, 1.0));
    TestTrue("4x7 Normal 110.6 per step", FMath::IsNearlyEqual(Four[0].StepMs, 110.6, 0.1));
    TestTrue("4x7 Normal: nobody snaps", !Four[0].bSnapped && !Four[3].bSnapped);
    const TArray<FS08MoveCueTiming> Slow = FS08MoveCueSchedule::Compute(Moves(4, 7), FS08MoveCueParams(), 1.5);
    TestTrue("4x7 Slow ends at 3600", FMath::IsNearlyEqual(End(Slow[3]), 3600.0, 1.0));
    TestTrue("4x7 Slow 165.9 per step", FMath::IsNearlyEqual(Slow[0].StepMs, 165.9, 0.1));
    const TArray<FS08MoveCueTiming> NineNine = FS08MoveCueSchedule::Compute(Moves(9, 9));
    TestTrue("9x9 Normal ends 810 / 1377 / 1944",
             FMath::IsNearlyEqual(End(NineNine[0]), 810.0, 1.0) && FMath::IsNearlyEqual(End(NineNine[1]), 1377.0, 1.0) &&
                 FMath::IsNearlyEqual(End(NineNine[2]), 1944.0, 1.0));
    int32 Snapped = 0;
    bool bSnapAt1944 = true;
    for (int32 I = 3; I < 9; ++I) {
      Snapped += NineNine[I].bSnapped ? 1 : 0;
      bSnapAt1944 &= FMath::IsNearlyEqual(NineNine[I].StartMs, 1944.0, 1.0) && NineNine[I].DurationMs == 0.0;
    }
    TestTrue("9x9 Normal: 3 animated", !NineNine[0].bSnapped && !NineNine[1].bSnapped && !NineNine[2].bSnapped);
    TestEqual("9x9 Normal: 6 snap", Snapped, 6);
    TestTrue("9x9 Normal: snap at 1944", bSnapAt1944);
    const TArray<FS08MoveCueTiming> Fast = FS08MoveCueSchedule::Compute(Moves(9, 9), FS08MoveCueParams(), 0.5);
    int32 FastSnapped = 0;
    for (const FS08MoveCueTiming& T : Fast) FastSnapped += T.bSnapped ? 1 : 0;
    TestTrue("9x9 Fast: 1 animated, ends 810 (min step 90 unscaled)",
             !Fast[0].bSnapped && FMath::IsNearlyEqual(End(Fast[0]), 810.0, 1.0));
    TestEqual("9x9 Fast: 8 snap", FastSnapped, 8);
    TestTrue("9x9 Fast: snap at 810", FMath::IsNearlyEqual(Fast[8].StartMs, 810.0, 1.0));
    const TArray<FS08MoveCueTiming> Place = FS08MoveCueSchedule::Compute(Moves(1, 5, ES08MoveKind::Place));
    TestTrue("PLACE = 240, one step", FMath::IsNearlyEqual(Place[0].DurationMs, 240.0, 1.0) && Place[0].Steps == 1);
    const TArray<FS08MoveCueTiming> FastPlace =
        FS08MoveCueSchedule::Compute(Moves(1, 1, ES08MoveKind::Place), FS08MoveCueParams(), 0.5);
    TestTrue("PLACE Fast = 120", FMath::IsNearlyEqual(FastPlace[0].DurationMs, 120.0, 1.0));
    const TArray<FS08MoveCueTiming> Overlap = FS08MoveCueSchedule::Compute(Moves(2, 1));
    TestTrue("overlap 30 %: second starts at 196", FMath::IsNearlyEqual(Overlap[1].StartMs, 196.0, 1.0));
  }

  // ---- the MS-CUE line on a map board: space labels, of=, start/ms by the schedule ----
  {
    const FString Board = ChainTopologyBoard();
    FS08FlowController Flow(TEXT("http://invalid"), TEXT("ws://invalid"), Guest);
    FCueCapture Cap;
    Cap.Bind(Flow);
    Flow.ApplySnapshot(Snap(70, Board, {{TEXT("a"), Host, 0, 0}, {TEXT("b"), Host, 1, 0}}));
    // a: A01 -> A03 can only pass A02 if b left it first: the trail order b, a.
    Flow.ApplySnapshot(Snap(71, Board, {{TEXT("a"), Host, 1, 0}, {TEXT("b"), Host, 2, 0}},
                            TrailMeta(71, {{TEXT("b"), TEXT("MOVE"), {1, 0}, {{2, 0}}},
                                           {TEXT("a"), TEXT("MOVE"), {0, 0}, {{1, 0}}}})));
    TestEqual("two MS-CUE lines", Cap.CueLines.Num(), 2);
    if (Cap.CueLines.Num() == 2) {
      TestEqual("first line", Cap.CueLines[0],
                TEXT("MS-CUE move seq=71 fighter=b order=0 of=2 kind=move steps=1 source=trail start=0 ms=280 snapped=0 path=A02>A03"));
      TestEqual("second line", Cap.CueLines[1],
                TEXT("MS-CUE move seq=71 fighter=a order=1 of=2 kind=move steps=1 source=trail start=196 ms=280 snapped=0 path=A01>A02"));
    }
    // Canonical on the map graph: the link chain, labelled by space.
    Flow.ApplySnapshot(Snap(72, Board, {{TEXT("a"), Host, 0, 0}, {TEXT("b"), Host, 2, 0}}));
    TestTrue("canonical over links", Cap.CueLines.Num() == 3 &&
                                         Cap.CueLines[2].Contains(TEXT("source=canonical start=0 ms=280 snapped=0 path=A02>A01")));
  }

  // ---- a seq that overflows the cap: snapped moves are traced snapped=1 ms=0 at the snap time ----
  {
    const FString Board = GridBoard(10, 10);
    TArray<FF> Old, New;
    TArray<FTM> Trail;
    for (int32 I = 0; I < 9; ++I) {
      const FString Id = FString::Printf(TEXT("f%d"), I);
      Old.Add({Id, Host, 0, I});
      New.Add({Id, Host, 9, I});
      TArray<FIntPoint> Path;
      for (int32 X = 1; X <= 9; ++X) Path.Add(FIntPoint(X, I));
      Trail.Add({Id, TEXT("MOVE"), FIntPoint(0, I), Path});
    }
    FS08FlowController Flow(TEXT("http://invalid"), TEXT("ws://invalid"), Guest);
    FCueCapture Cap;
    Cap.Bind(Flow);
    Flow.ApplySnapshot(Snap(80, Board, Old));
    Flow.ApplySnapshot(Snap(81, Board, New, TrailMeta(81, Trail)));
    TestEqual("nine MS-CUE lines", Cap.CueLines.Num(), 9);
    if (Cap.CueLines.Num() == 9) {
      TestTrue("third animated, ends 1944", Cap.CueLines[2].Contains(TEXT("order=2 of=9 kind=move steps=9 source=trail start=1134 ms=810 snapped=0")));
      TestTrue("fourth snapped at 1944", Cap.CueLines[3].Contains(TEXT("order=3 of=9 kind=move steps=9 source=trail start=1944 ms=0 snapped=1")));
      TestTrue("last snapped at 1944", Cap.CueLines[8].Contains(TEXT("order=8 of=9 kind=move steps=9 source=trail start=1944 ms=0 snapped=1")));
    }
  }
  return true;
}


// ---- DE-021 (W-12, SD-13, MS-R-22): the own figure starts in the frame the snapshot is applied ---------------------
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MoveStartFrameTest, "Unmatched.S08.MoveAnim.StartFrame",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MoveStartFrameTest::RunTest(const FString&) {
  using namespace S08MoveCueTest;
  // The game mode syncs the board on OnApplied and starts the moves on OnCues (HandleCues -> PlayFighterMoves ->
  // PlayMove samples t = 0 at once). Both must come out of ONE ApplySnapshot call, applied first; the plan of the own
  // fighter (alone in its seq) starts at 0 and is already off its start cell one 60 FPS frame later.
  const FString Board = GridBoard(5, 3);
  FS08FlowController Flow(TEXT("http://invalid"), TEXT("ws://invalid"), Host);
  TArray<FString> Events;
  TArray<FS08MovePlan> Plans;
  auto World = [](const FIntPoint& Cell) { return FVector(Cell.X * 100.0, Cell.Y * 100.0, 0.0); };
  Flow.OnApplied.AddLambda([&Events](const FS08Snapshot& Applied, ES08SeqDecision) {
    Events.Add(FString::Printf(TEXT("applied:%d"), Applied.SequenceNumber));
  });
  Flow.OnCues.AddLambda([&](const TArray<FS08Cue>& Cues) {
    Events.Add(FString::Printf(TEXT("cues:%d"), Cues.Num() > 0 ? Cues[0].SequenceNumber : -1));
    Plans = FS08MoveAnim::BuildPlans(Cues, FS08MotionSettings(), World);
  });
  Flow.ApplySnapshot(Snap(10, Board, {{TEXT("h1"), Host, 0, 1}, {TEXT("g1"), Guest, 4, 1}}));
  Events.Reset();
  Flow.ApplySnapshot(Snap(11, Board, {{TEXT("h1"), Host, 2, 1}, {TEXT("g1"), Guest, 4, 1}},
                          TrailMeta(11, {{TEXT("h1"), TEXT("MOVE"), {0, 1}, {{1, 1}, {2, 1}}}})));
  TestEqual("one apply -> board sync, then the cues (same call, same frame)", FString::Join(Events, TEXT(" ")),
            TEXT("applied:11 cues:11"));
  TestEqual("one plan", Plans.Num(), 1);
  if (Plans.Num() == 1) {
    const FS08MovePlan& P = Plans[0];
    const FS08MoveAnimParams A;
    TestEqual("own fighter", P.FighterId, FString(TEXT("h1")));
    TestEqual("starts at the snapshot frame (StartMs 0)", P.StartMs, 0.0);
    TestTrue("280 ms per edge, 2 edges", FMath::IsNearlyEqual(P.StepMs, 280.0, 0.01) && P.Steps == 2);
    const FS08MovePose At0 = FS08MoveAnim::Sample(P, A, 0.0, 150.0);
    TestTrue("t = 0: started on the start cell", At0.bStarted && At0.Location.Equals(World({0, 1}), 0.01));
    const double Frame = 1000.0 / 60.0;
    const FS08MovePose At1 = FS08MoveAnim::Sample(P, A, Frame, 150.0);
    // AN-21 (ВР-12): the first edge eases in - one 60 FPS frame covers s(16.7) = 0.72 uu of the 100 uu edge
    // (the linear pose moved 5.95); the move still starts in the snapshot frame (SD-13).
    TestTrue("one 60 FPS frame later: off the start cell on edge 0 (<= 1 frame, SD-13)",
             At1.Edge == 0 && At1.Location.X > World({0, 1}).X + 0.5);
    TestTrue("one frame: slide only, no hop (D-DE-02)", FMath::IsNearlyZero(At1.HopUU) && FMath::IsNearlyZero(At1.Location.Z));
  }
  return true;
}

#endif
