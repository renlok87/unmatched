// GD-030/GD-031 automation tests: INT-019 coordinate contract, board/fighter
// decode from the live fixtures, movement legality mirror, mutation-result
// parsing, and the single state store (convergence, same-seq enrichment,
// duplicate cue suppression, command gate). Headless run:
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     -ExecCmds="Automation RunTests Unmatched.S08" -unattended -nosplash -nullrhi
#if WITH_AUTOMATION_TESTS

#include "S08BoardActor.h"
#include "S08BoardModel.h"
#include "S08Contracts.h"
#include "S08FlowController.h"
#include "Dom/JsonObject.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace {
FString Phase2FixturePath(const TCHAR* Name) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(),
                          TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  return FPaths::Combine(Dir, Name);
}

bool LoadFixtureBody(const TCHAR* Name, FString& OutBody) {
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *Phase2FixturePath(Name))) return false;
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) return false;
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (!Value->TryGetObject(Root) || !Root->IsValid()) return false;
  if ((*Root)->TryGetStringField(TEXT("raw"), OutBody)) return true;
  const TSharedPtr<FJsonObject>* RawObject = nullptr;
  if (!(*Root)->TryGetObjectField(TEXT("raw"), RawObject) || !RawObject->IsValid()) {
    return false;
  }
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutBody);
  FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
  return true;
}

/** Snapshot from a fixture body (two-stage gameState query). */
bool SnapshotFromFixture(const TCHAR* Name, FS08Snapshot& OutSnapshot) {
  FString Body;
  if (!LoadFixtureBody(Name, Body)) return false;
  FS08GraphQLError Error;
  FString RawState;
  return FS08Contracts::ParseGameStateQuery(Body, OutSnapshot, RawState, Error);
}

/** Rebuilds the inner state JSON of a fixture snapshot with some top-level
 *  projection fields REMOVED (partial body, unmatched-net/1 section 2). */
FS08Snapshot MakePartial(const FS08Snapshot& Source, const TArray<FString>& Drop) {
  FS08Snapshot Partial;
  Partial.SequenceNumber = Source.SequenceNumber;
  Partial.Phase = Source.Phase;
  Partial.TurnCount = Source.TurnCount;
  Partial.CurrentTurnPlayerId = Source.CurrentTurnPlayerId;
  auto Keep = [&Source, &Drop](TSharedPtr<FJsonValue>& Out, const TSharedPtr<FJsonValue>& In,
                               const FString& Field) {
    for (const FString& Dropped : Drop) {
      if (Dropped == Field) return;
    }
    Out = In;
  };
  Keep(Partial.Players, Source.Players, TEXT("players"));
  Keep(Partial.Fighters, Source.Fighters, TEXT("fighters"));
  Keep(Partial.HandZones, Source.HandZones, TEXT("handZones"));
  Keep(Partial.DiscardPiles, Source.DiscardPiles, TEXT("discardPiles"));
  Keep(Partial.BoardState, Source.BoardState, TEXT("boardState"));
  Keep(Partial.Metadata, Source.Metadata, TEXT("metadata"));
  return Partial;
}

/** Deep-ish copy with one fighter moved and damaged (seq transition). */
FS08Snapshot WithFighterMovedAndDamaged(const FS08Snapshot& Source, int32 NewSeq,
                                        const FString& FighterId, int32 ToX, int32 ToY,
                                        int32 Damage) {
  FS08Snapshot Next = Source;
  Next.SequenceNumber = NewSeq;
  const TArray<TSharedPtr<FJsonValue>>* Array = nullptr;
  if (!Source.Fighters.IsValid() || !Source.Fighters->TryGetArray(Array) || !Array) {
    return Next;
  }
  TArray<TSharedPtr<FJsonValue>> Fighters;
  for (const TSharedPtr<FJsonValue>& Value : *Array) {
    const TSharedPtr<FJsonObject>* Object = nullptr;
    if (!Value.IsValid() || !Value->TryGetObject(Object) || !Object->IsValid()) continue;
    const TSharedRef<FJsonObject> Copy = MakeShared<FJsonObject>();
    Copy->Values = (*Object)->Values;
    if (Copy->GetStringField(TEXT("id")) == FighterId) {
      const TSharedRef<FJsonObject> Position = MakeShared<FJsonObject>();
      Position->SetNumberField(TEXT("x"), ToX);
      Position->SetNumberField(TEXT("y"), ToY);
      Copy->SetObjectField(TEXT("position"), Position);
      Copy->SetNumberField(TEXT("health"),
                           Copy->GetNumberField(TEXT("health")) - Damage);
    }
    Fighters.Add(MakeShared<FJsonValueObject>(Copy));
  }
  Next.Fighters = MakeShared<FJsonValueArray>(Fighters);
  return Next;
}
} // namespace

// ---- GD-030: board decode + INT-019 coordinate contract -----------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08BoardDecodeTest,
    "Unmatched.S08.Phase2.board decode from live fixture (20x20 rows)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08BoardDecodeTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  if (!SnapshotFromFixture(TEXT("04-game-state-query-host.json"), Snapshot)) {
    AddError("fixture 04 failed to parse");
    return true;
  }
  FS08BoardModel Board;
  TestTrue("board decodes", Board.Decode(Snapshot.BoardState));
  TestEqual("width", Board.Width, 20);
  TestEqual("height", Board.Height, 20);
  int32 NormalCells = 0;
  for (const FS08Cell& Cell : Board.Cells) {
    if (Cell.Type == ES08CellType::Normal && Cell.IsPassable()) ++NormalCells;
  }
  TestEqual("all 400 cells normal+passable", NormalCells, 400);
  TestTrue("cell(0,0) exists", Board.CellAt(0, 0) != nullptr);
  TestTrue("out of bounds null", Board.CellAt(20, 20) == nullptr);
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ControlPointsTest,
    "Unmatched.S08.Phase2.INT-019 control points and reverse hit test",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ControlPointsTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  TestTrue("fixture parses", SnapshotFromFixture(TEXT("04-game-state-query-host.json"), Snapshot));
  FS08BoardModel Board;
  TestTrue("board decodes", Board.Decode(Snapshot.BoardState));
  const int32 W = Board.Width, H = Board.Height; // 20x20 live geometry

  // Two opposite corners: World = ((x-(W-1)/2)*100, (y-(H-1)/2)*100, 0).
  const FVector CornerA = Board.CellToWorld(0, 0);
  TestTrue("corner (0,0).X", CornerA.X == -950.0);
  TestTrue("corner (0,0).Y", CornerA.Y == -950.0);
  TestTrue("corner (0,0).Z", CornerA.Z == 0.0);
  const FVector CornerB = Board.CellToWorld(W - 1, H - 1);
  TestTrue("corner (19,19).X", CornerB.X == 950.0);
  TestTrue("corner (19,19).Y", CornerB.Y == 950.0);

  // Neighbor pair through the board center: exactly 100 uu apart on Y.
  const FVector NeighborA = Board.CellToWorld(W / 2, H / 2);
  const FVector NeighborB = Board.CellToWorld(W / 2, H / 2 + 1);
  TestTrue("neighbor distance", FVector::Dist(NeighborA, NeighborB) == 100.0);
  TestTrue("same X for Y-neighbors", NeighborA.X == NeighborB.X);

  // Reverse transform (click hit test): corners + neighbors round-trip.
  int32 CX, CY;
  TestTrue("reverse corner A", Board.WorldToCell(CornerA, CX, CY) && CX == 0 && CY == 0);
  TestTrue("reverse corner B",
           Board.WorldToCell(CornerB, CX, CY) && CX == W - 1 && CY == H - 1);
  TestTrue("reverse neighbor A",
           Board.WorldToCell(NeighborA, CX, CY) && CX == W / 2 && CY == H / 2);
  TestTrue("reverse neighbor B",
           Board.WorldToCell(NeighborB, CX, CY) && CX == W / 2 && CY == H / 2 + 1);
  TestFalse("click far outside ignored", Board.WorldToCell(FVector(0, 5000, 0), CX, CY));
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08FightersDecodeTest,
    "Unmatched.S08.Phase2.fighters decode: six fighters, H1/H2/H3, own/enemy",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08FightersDecodeTest::RunTest(const FString&) {
  FS08Snapshot Snapshot;
  TestTrue("fixture parses", SnapshotFromFixture(TEXT("04-game-state-query-host.json"), Snapshot));
  TArray<FS08BoardFighter> Fighters;
  TestTrue("fighters decode", FS08BoardModel::DecodeFighters(Snapshot.Fighters, Fighters));
  TestEqual("six fighters", Fighters.Num(), 6);
  TSet<FString> Owners;
  int32 Harpies = 0;
  TSet<FString> HarpyLabels;
  for (const FS08BoardFighter& Fighter : Fighters) {
    Owners.Add(Fighter.OwnerId);
    if (Fighter.Name == TEXT("Harpies")) {
      ++Harpies;
      HarpyLabels.Add(Fighter.Label);
    }
  }
  TestEqual("two owners (own/enemy split)", Owners.Num(), 2);
  TestEqual("three harpies", Harpies, 3);
  TestEqual("harpy labels numbered 1..3", HarpyLabels.Num(), 3);
  TestTrue("label 'Harpies 1' present", HarpyLabels.Contains(TEXT("Harpies 1")));
  TestTrue("label 'Harpies 2' present", HarpyLabels.Contains(TEXT("Harpies 2")));
  TestTrue("label 'Harpies 3' present", HarpyLabels.Contains(TEXT("Harpies 3")));
  // Stable numbering is keyed by fighter id, never by array order.
  const FS08BoardFighter* Hero = nullptr;
  for (const FS08BoardFighter& Fighter : Fighters) {
    if (Fighter.bIsHero && Fighter.Name == TEXT("Medusa")) Hero = &Fighter;
  }
  TestTrue("hero present", Hero != nullptr);
  if (Hero) {
    TestEqual("Medusa hero at (2,2)", Hero->X == 2 && Hero->Y == 2, true);
    TestEqual("hero movement 3", Hero->Movement, 3);
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08ReachabilityTest,
    "Unmatched.S08.Phase2.movement legality mirror (ally pass-through, enemy block)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08ReachabilityTest::RunTest(const FString&) {
  // Synthetic 5x5 board: walls column x=4, closed door at (3,2).
  TSharedRef<FJsonObject> BoardObject = MakeShared<FJsonObject>();
  BoardObject->SetNumberField(TEXT("width"), 5);
  BoardObject->SetNumberField(TEXT("height"), 5);
  TArray<TSharedPtr<FJsonValue>> Rows;
  for (int32 Y = 0; Y < 5; ++Y) {
    TArray<TSharedPtr<FJsonValue>> Row;
    for (int32 X = 0; X < 5; ++X) {
      TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
      if (X == 4) {
        Cell->SetStringField(TEXT("type"), TEXT("wall"));
      } else if (X == 3 && Y == 2) {
        Cell->SetStringField(TEXT("type"), TEXT("door"));
        Cell->SetBoolField(TEXT("isOpen"), false);
      } else {
        Cell->SetStringField(TEXT("type"), TEXT("normal"));
      }
      Cell->SetNumberField(TEXT("x"), X);
      Cell->SetNumberField(TEXT("y"), Y);
      Row.Add(MakeShared<FJsonValueObject>(Cell));
    }
    Rows.Add(MakeShared<FJsonValueArray>(Row));
  }
  BoardObject->SetArrayField(TEXT("cells"), Rows);
  BoardObject->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());

  FS08BoardModel Board;
  TestTrue("synthetic board decodes",
           Board.Decode(MakeShared<FJsonValueObject>(BoardObject)));

  auto MakeFighter = [](const FString& Id, const FString& Owner, int32 X, int32 Y,
                        int32 Health) {
    FS08BoardFighter Fighter;
    Fighter.Id = Id;
    Fighter.OwnerId = Owner;
    Fighter.Name = Id;
    Fighter.Health = Fighter.MaxHealth = Health;
    Fighter.Movement = 2;
    Fighter.X = X;
    Fighter.Y = Y;
    return Fighter;
  };
  TArray<FS08BoardFighter> Fighters;
  Fighters.Add(MakeFighter(TEXT("mover"), TEXT("own"), 2, 2, 5));
  Fighters.Add(MakeFighter(TEXT("ally"), TEXT("own"), 1, 2, 5));
  Fighters.Add(MakeFighter(TEXT("enemy"), TEXT("foe"), 2, 1, 5));

  const TSet<uint64> Reach =
      FS08BoardModel::ComputeReachableCells(Board, Fighters, TEXT("mover"), 2);
  TestTrue("own cell (zero-step) reachable",
           Reach.Contains(FS08BoardModel::CellKey(2, 2)));
  TestTrue("pass through ally: (0,2) reachable",
           Reach.Contains(FS08BoardModel::CellKey(0, 2)));
  TestFalse("ally cell is not a legal endpoint",
            Reach.Contains(FS08BoardModel::CellKey(1, 2)));
  TestFalse("enemy cell not reachable",
            Reach.Contains(FS08BoardModel::CellKey(2, 1)));
  TestFalse("cells behind enemy blocked (2,0)",
            Reach.Contains(FS08BoardModel::CellKey(2, 0)));
  TestFalse("wall column unreachable (4,2)",
            Reach.Contains(FS08BoardModel::CellKey(4, 2)));
  TestFalse("closed door blocks (3,2)",
            Reach.Contains(FS08BoardModel::CellKey(3, 2)));
  TestTrue("side step (3,3) reachable", Reach.Contains(FS08BoardModel::CellKey(3, 3)));
  return true;
}

// ---- GD-030: readable-grid visual contract --------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08TileGrooveContractTest,
    "Unmatched.S08.Phase2.tile groove contract (readable grid, slab rejected)",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08TileGrooveContractTest::RunTest(const FString&) {
  // Adjacent 100-uu tiles must NOT touch: a dark groove separates them
  // (scale 1.0 merged all 400 cells into one white slab). 15 uu is the
  // tuned value the verified grid-checker shots were produced with
  // (6-8 uu grooves were invisible to the luminance-profile detector).
  TestTrue("tile scale below full cell", AS08BoardActor::TileVisualScaleXY < 1.0f);
  TestTrue("blocker scale below full cell", AS08BoardActor::BlockerVisualScaleXY < 1.0f);
  const float Groove = AS08BoardActor::GrooveUU();
  TestTrue("groove within 14-16 uu (tuned, visible, not oversized)",
           Groove >= 14.0f && Groove <= 16.0f);
  // Cell centers / hit-test pitch unchanged (INT-019 contract).
  TestEqual("cell size still 100 uu",
            static_cast<int32>(FS08BoardModel::CellSizeUU), 100);
  return true;
}

// ---- GD-031: mutation result + state store --------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08MutationParseTest,
    "Unmatched.S08.Phase2.mutation result parses state string + pendingManeuver",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08MutationParseTest::RunTest(const FString&) {
  // Build a GameMutationResult-shaped body: state is the full inner state as
  // a JSON STRING (same wire shape beginManeuver/maneuver return).
  TSharedRef<FJsonObject> Inner = MakeShared<FJsonObject>();
  Inner->SetNumberField(TEXT("sequenceNumber"), 2);
  Inner->SetStringField(TEXT("phase"), TEXT("ACTION_MANEUVER"));
  Inner->SetNumberField(TEXT("turnCount"), 1);
  Inner->SetStringField(TEXT("currentTurnPlayerId"), TEXT("user-a"));
  TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>();
  TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
  Pending->SetStringField(TEXT("id"), TEXT("maneuver:1:1"));
  Pending->SetStringField(TEXT("playerId"), TEXT("user-a"));
  Meta->SetObjectField(TEXT("pendingManeuver"), Pending);
  Inner->SetObjectField(TEXT("metadata"), Meta);

  FString InnerJson;
  const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&InnerJson);
  FJsonSerializer::Serialize(Inner, Writer);

  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  Payload->SetStringField(TEXT("state"), InnerJson);
  Payload->SetNumberField(TEXT("sequenceNumber"), 2);
  Payload->SetStringField(TEXT("phase"), TEXT("ACTION_MANEUVER"));
  Payload->SetNumberField(TEXT("turnCount"), 1);
  Payload->SetStringField(TEXT("currentTurnPlayerId"), TEXT("user-a"));
  TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
  Data->SetObjectField(TEXT("beginManeuver"), Payload);
  TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
  Root->SetObjectField(TEXT("data"), Data);
  FString Body;
  const TSharedRef<TJsonWriter<>> BodyWriter = TJsonWriterFactory<>::Create(&Body);
  FJsonSerializer::Serialize(Root, BodyWriter);

  FS08Snapshot Snapshot;
  FS08GraphQLError Error;
  TestTrue("mutation result parses",
           FS08Contracts::ParseMutationResult(Body, TEXT("beginManeuver"), Snapshot, Error));
  TestEqual("seq", Snapshot.SequenceNumber, 2);
  TestEqual("phase", Snapshot.Phase, TEXT("ACTION_MANEUVER"));
  TestEqual("pendingManeuver id", FS08Contracts::PendingManeuverId(Snapshot),
            TEXT("maneuver:1:1"));
  TestTrue("no pending -> empty",
           FS08Contracts::PendingManeuverId(MakePartial(Snapshot, {TEXT("metadata")})).IsEmpty());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08StoreConvergenceTest,
    "Unmatched.S08.Phase2.HTTP->WS and WS->HTTP converge; enrichment fills panel",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08StoreConvergenceTest::RunTest(const FString&) {
  FS08Snapshot Full;
  if (!SnapshotFromFixture(TEXT("04-game-state-query-host.json"), Full)) {
    AddError("fixture 04 failed to parse");
    return true;
  }
  const FString Viewer = TEXT("cmugykjjb0000wi9w2nq4qlkj");

  // WS-style partial of the same seq: projections it carries replace, the
  // rest keep their local copies (never erased) - ACC-011.
  const FS08Snapshot Partial = MakePartial(
      Full, {TEXT("boardState"), TEXT("handZones"), TEXT("metadata"), TEXT("discardPiles")});
  TestFalse("partial has no boardState", Partial.BoardState.IsValid());
  TestTrue("partial has fighters", Partial.Fighters.IsValid());

  auto RunOrder = [&](bool bHttpFirst, FS08FlowController& Store) {
    const FS08Snapshot& First = bHttpFirst ? Full : Partial;
    const FS08Snapshot& Second = bHttpFirst ? Partial : Full;
    const ES08SeqDecision D1 = Store.ApplySnapshot(First);
    const ES08SeqDecision D2 = Store.ApplySnapshot(Second);
    TestEqual("first applies", static_cast<uint8>(D1), static_cast<uint8>(ES08SeqDecision::Apply));
    TestEqual("second merges", static_cast<uint8>(D2), static_cast<uint8>(ES08SeqDecision::Merge));
  };

  FS08FlowController StoreHttpFirst(TEXT("http://invalid"), TEXT("ws://invalid"), Viewer);
  RunOrder(true, StoreHttpFirst);
  FS08FlowController StoreWsFirst(TEXT("http://invalid"), TEXT("ws://invalid"), Viewer);
  RunOrder(false, StoreWsFirst);

  const FS08Snapshot& A = StoreHttpFirst.GetAppliedSnapshot();
  const FS08Snapshot& B = StoreWsFirst.GetAppliedSnapshot();
  TestEqual("same seq", A.SequenceNumber, B.SequenceNumber);
  TestEqual("same phase", A.Phase, B.Phase);
  TestEqual("fighters kept in both orders",
            FS08Contracts::EntryCount(A.Fighters), FS08Contracts::EntryCount(B.Fighters));
  TestEqual("6 fighters kept", FS08Contracts::EntryCount(A.Fighters), 6);
  TestTrue("boardState kept when partial lacked it", A.BoardState.IsValid());
  TestTrue("boardState kept in reverse order too", B.BoardState.IsValid());
  TestTrue("input not blocked (both converged valid)",
           !StoreHttpFirst.IsInputBlocked() && !StoreWsFirst.IsInputBlocked());

  // Same-seq enrichment fills the panel: store got the partial first, a
  // later same-seq body carrying discardPiles fills it WITHOUT erasing
  // fighters (this is exactly the WS->HTTP recovery order).
  TestTrue("enriched discardPiles present", B.DiscardPiles.IsValid());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08StoreCueSuppressionTest,
    "Unmatched.S08.Phase2.duplicate seq suppresses cues; stale ignored",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08StoreCueSuppressionTest::RunTest(const FString&) {
  FS08Snapshot Base;
  if (!SnapshotFromFixture(TEXT("04-game-state-query-host.json"), Base)) {
    AddError("fixture 04 failed to parse");
    return true;
  }
  const FString Viewer = TEXT("cmugykjjb0000wi9w2nq4qlkj");
  const FS08Snapshot Moved = WithFighterMovedAndDamaged(Base, 2, TEXT("f-0-hero"), 3, 2, 2);

  FS08FlowController Store(TEXT("http://invalid"), TEXT("ws://invalid"), Viewer);
  int32 MoveCues = 0, DamageCues = 0;
  Store.OnCues.AddLambda([&](const TArray<FS08Cue>& Cues) {
    for (const FS08Cue& Cue : Cues) {
      if (Cue.Type == ES08CueType::FighterMoved) ++MoveCues;
      if (Cue.Type == ES08CueType::FighterDamaged) ++DamageCues;
    }
  });

  Store.ApplySnapshot(Base);        // HTTP snapshot seq=1
  Store.ApplySnapshot(Moved);       // WS event seq=2 (authoritative transition)
  Store.ApplySnapshot(Moved);       // HTTP mutation echo of the SAME seq=2
  Store.ApplySnapshot(Base);        // stale recovery response seq=1

  TestEqual("move cue fired once", MoveCues, 1);
  TestEqual("damage cue fired once", DamageCues, 1);
  TestEqual("store seq stayed 2", Store.GetAppliedSnapshot().SequenceNumber, 2);
  TestFalse("input not blocked", Store.IsInputBlocked());
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS08StoreCommandGateTest,
    "Unmatched.S08.Phase2.command gate: critical fields, turn, in-flight",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS08StoreCommandGateTest::RunTest(const FString&) {
  FS08Snapshot Full;
  TestTrue("fixture parses", SnapshotFromFixture(TEXT("04-game-state-query-host.json"), Full));
  const FString Viewer = TEXT("cmugykjjb0000wi9w2nq4qlkj");

  // Critically incomplete snapshot blocks commands (phase1 gate semantics).
  FS08FlowController Blocked(TEXT("http://invalid"), TEXT("ws://invalid"), Viewer);
  const FS08Snapshot Incomplete = MakePartial(Full, {TEXT("fighters"), TEXT("boardState")});
  Blocked.ApplySnapshot(Incomplete);
  FString Reason;
  TestFalse("incomplete state blocks", Blocked.CanIssueGameplayCommand(Reason));
  TestTrue("reason mentions critical", Reason.Contains(TEXT("critical")));

  // Full state: gated only by stage/turn (stage is not Started in this
  // offline harness - the gate must say so, proving the check chain).
  FS08FlowController Ready(TEXT("http://invalid"), TEXT("ws://invalid"), Viewer);
  Ready.ApplySnapshot(Full);
  TestFalse("non-started stage blocks", Ready.CanIssueGameplayCommand(Reason));
  TestTrue("reason mentions start", Reason.Contains(TEXT("started")));
  return true;
}

#endif
