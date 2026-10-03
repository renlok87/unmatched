// Move selection (docs/game-design/move-selection) automation tests of the S09
// draft: 06 MS-AT-11..14, 20.
//   Unmatched.S09.MoveSel.SequentialDraft - MS-AT-13 (MS-T-05): moves in send
//       order on the positions after the previous moves, order changes,
//       overwrite / re-assign numbering, conflict reasons, the command against
//       the golden fixtures of backend/prisma/fixtures/movement.
//   Unmatched.S09.MoveSel.BoostRecompute  - MS-AT-12 (MS-T-05): boost change
//       re-evaluates statuses and tiers in the same call, NeedBoost by the
//       absolute RequiredBoost, card highlight, tiers by MS-E-80, null / +0 /
//       two copies.
//   Unmatched.S09.MoveSel.ZeroLengthNotSent - MS-AT-11 (MS-T-04): the own cell
//       never becomes a move, ConfirmManeuver and SubmitManeuver drop "stay".
//   Unmatched.S09.MoveSel.MovementParity  - MS-AT-14 (MS-T-04): raw movement,
//       immobilized gate, the two "alive" roles, MS-DATA dirtyDefeated.
//   Unmatched.S09.MoveSel.ReconnectAndRebuild - MS-AT-20, the MS-T-04 part:
//       the draft cache by maneuverId, re-evaluation on a new seq, a boost card
//       that left the hand, another id / closed maneuver / GAME_OVER. (Deadline,
//       auth refresh and why.syncing: MS-T-06; undo stack: MS-T-07.)
// Headless run:
//   UnrealEditor-Cmd.exe Unmatched.uproject
//     "-ExecCmds=Automation RunTests Unmatched.S09.MoveSel; Quit"
//     -unattended -nosplash -nullrhi
// Optional: -S08MoveFixtures=<dir> (golden fixtures).
#if WITH_AUTOMATION_TESTS

#include "S09ManeuverUi.h"
#include "../S08/S08BoardModel.h"
#include "../S08/S08Contracts.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// Named namespace (not anonymous): unity builds merge test files.
namespace S09MoveSelTest {

const TCHAR* const Me = TEXT("p1");
const TCHAR* const Opp = TEXT("p2");
const TCHAR* const ManeuverA = TEXT("maneuver:1:5");

/** W x H grid board decoded through the server boardState shape; Walls are
 *  'wall' cells. */
FS08BoardModel MsGrid(int32 W, int32 H, std::initializer_list<FIntPoint> Walls = {}) {
  TArray<TSharedPtr<FJsonValue>> Lines;
  for (int32 Y = 0; Y < H; ++Y) {
    TArray<TSharedPtr<FJsonValue>> Line;
    for (int32 X = 0; X < W; ++X) {
      TSharedRef<FJsonObject> Cell = MakeShared<FJsonObject>();
      Cell->SetNumberField(TEXT("x"), X);
      Cell->SetNumberField(TEXT("y"), Y);
      bool bWall = false;
      for (const FIntPoint& Wall : Walls) bWall |= Wall == FIntPoint(X, Y);
      Cell->SetStringField(TEXT("type"), bWall ? TEXT("wall") : TEXT("normal"));
      Line.Add(MakeShared<FJsonValueObject>(Cell));
    }
    Lines.Add(MakeShared<FJsonValueArray>(Line));
  }
  TSharedRef<FJsonObject> Board = MakeShared<FJsonObject>();
  Board->SetNumberField(TEXT("width"), W);
  Board->SetNumberField(TEXT("height"), H);
  Board->SetArrayField(TEXT("cells"), Lines);
  Board->SetObjectField(TEXT("doors"), MakeShared<FJsonObject>());
  FS08BoardModel Model;
  Model.Decode(MakeShared<FJsonValueObject>(Board));
  return Model;
}

FS08BoardFighter MsFighter(const FString& Id, const FString& Owner, int32 X, int32 Y, double Movement = 3.0,
                           int32 Health = 10) {
  FS08BoardFighter F;
  F.Id = Id;
  F.OwnerId = Owner;
  F.Name = Id;
  F.Label = Id;
  F.Health = Health;
  F.MaxHealth = FMath::Max(Health, 10);
  F.X = X;
  F.Y = Y;
  F.SetRawMovement(Movement);
  F.AttackType = TEXT("melee");
  return F;
}

struct FMsCard {
  FString Id;
  bool bHasBoost = true;
  int32 Boost = 0;
};

/** Viewer's ACTION_MANEUVER snapshot with metadata.pendingManeuver (id) and
 *  the own hand (boostValue null when !bHasBoost). */
FS08Snapshot MsSnapshot(const TArray<FMsCard>& Hand, const FString& ManeuverId = ManeuverA, int32 Seq = 5) {
  FS08Snapshot Snapshot;
  Snapshot.SequenceNumber = Seq;
  Snapshot.Phase = TEXT("ACTION_MANEUVER");
  Snapshot.TurnCount = 1;
  Snapshot.CurrentTurnPlayerId = Me;
  TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>();
  Meta->SetNumberField(TEXT("actionsRemaining"), 1);
  if (!ManeuverId.IsEmpty()) {
    TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
    Pending->SetStringField(TEXT("id"), ManeuverId);
    Pending->SetStringField(TEXT("playerId"), Me);
    Meta->SetObjectField(TEXT("pendingManeuver"), Pending);
  }
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
  TArray<TSharedPtr<FJsonValue>> Cards;
  for (const FMsCard& Card : Hand) {
    TSharedRef<FJsonObject> C = MakeShared<FJsonObject>();
    C->SetStringField(TEXT("id"), Card.Id);
    C->SetStringField(TEXT("cardId"), TEXT("cat-") + Card.Id);
    C->SetStringField(TEXT("name"), Card.Id);
    C->SetStringField(TEXT("nameRu"), Card.Id);
    C->SetStringField(TEXT("cardType"), TEXT("VERSATILE"));
    C->SetStringField(TEXT("bannerName"), TEXT("any"));
    C->SetStringField(TEXT("text"), TEXT(""));
    C->SetBoolField(TEXT("isVisible"), false);
    if (Card.bHasBoost) {
      C->SetNumberField(TEXT("boostValue"), Card.Boost);
    } else {
      C->SetField(TEXT("boostValue"), MakeShared<FJsonValueNull>());
    }
    Cards.Add(MakeShared<FJsonValueObject>(C));
  }
  TSharedRef<FJsonObject> OwnHand = MakeShared<FJsonObject>();
  OwnHand->SetArrayField(TEXT("cards"), Cards);
  TSharedRef<FJsonObject> Hands = MakeShared<FJsonObject>();
  Hands->SetObjectField(Me, OwnHand);
  Snapshot.HandZones = MakeShared<FJsonValueObject>(Hands);
  return Snapshot;
}

/** A draft UI opened on Snapshot (viewer p1). */
FS09CommandUi MsOpen(const FS08Snapshot& Snapshot, const FS08BoardModel& Board,
                     const TArray<FS08BoardFighter>& Fighters) {
  FS09CommandUi Ui;
  Ui.ViewerId = Me;
  Ui.OnSnapshot(Snapshot, Board, Fighters);
  return Ui;
}

const FS09DraftMove* MsMove(const FS09CommandUi& Ui, const FString& FighterId) {
  const int32 Index = Ui.MoveIndexOf(FighterId);
  return Index == INDEX_NONE ? nullptr : &Ui.Moves[Index];
}

FString MsStatus(const FS09DraftMove* Move) {
  if (!Move) return TEXT("-");
  switch (Move->Status) {
    case ES09DraftMoveStatus::Ok: return TEXT("ok");
    case ES09DraftMoveStatus::NeedBoost: return TEXT("needBoost");
    default: return TEXT("conflict");
  }
}

FString MsKey(const FS09Reason& Reason) { return Reason.Key.ToString(); }

bool MsSameCells(const TArray<FIntPoint>& A, std::initializer_list<FIntPoint> B) {
  return A == TArray<FIntPoint>(B);
}

/** Cells at exactly D steps / within (Lo, Hi] of Start in a list. */
bool MsAllWithin(const FS09ReachTiers& Tiers, const TArray<FIntPoint>& Cells, int32 Lo, int32 Hi) {
  for (const FIntPoint& Cell : Cells) {
    const int32 D = Tiers.Reach.DistanceTo(Cell);
    if (D <= Lo || D > Hi) return false;
  }
  return true;
}

// ---- golden fixtures (backend/prisma/fixtures/movement) -----------------------

FString MsFixtureDir() {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08MoveFixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(FPaths::ProjectDir(), TEXT("../.."), TEXT("backend/prisma/fixtures/movement")));
  }
  return Dir;
}

bool MsReadXY(const TSharedPtr<FJsonObject>& Object, const TCHAR* Field, FIntPoint& Out) {
  const TSharedPtr<FJsonObject>* XY = nullptr;
  double X = 0.0, Y = 0.0;
  if (!Object->TryGetObjectField(Field, XY) || !XY || !(*XY)->TryGetNumberField(TEXT("x"), X) ||
      !(*XY)->TryGetNumberField(TEXT("y"), Y)) {
    return false;
  }
  Out = FIntPoint(static_cast<int32>(X), static_cast<int32>(Y));
  return true;
}

/** A lattice-grid ("cobble-5x6") fixture: board, fighters, hand, draft. */
struct FMsFixture {
  FS08BoardModel Board;
  TArray<FS08BoardFighter> Fighters;
  TArray<FMsCard> Hand;
  TArray<FS09DraftMove> Draft;
  FString BoostCardId;
  TSharedPtr<FJsonObject> Expect;
};

bool MsLoadGridFixture(const FString& Name, FMsFixture& Out, FString& OutError) {
  const FString Path = FPaths::Combine(MsFixtureDir(), Name + TEXT(".move-fixture.json"));
  FString Text;
  TSharedPtr<FJsonObject> Fx;
  if (!FFileHelper::LoadFileToString(Text, *Path) ||
      !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Fx) || !Fx.IsValid()) {
    OutError = Path + TEXT(" not readable");
    return false;
  }
  const TSharedPtr<FJsonObject>* Board = nullptr;
  const TSharedPtr<FJsonObject>* Lattice = nullptr;
  double W = 0.0, H = 0.0;
  if (!Fx->TryGetObjectField(TEXT("board"), Board) || !(*Board)->TryGetObjectField(TEXT("lattice"), Lattice) ||
      !(*Lattice)->TryGetNumberField(TEXT("width"), W) || !(*Lattice)->TryGetNumberField(TEXT("height"), H) ||
      (*Lattice)->HasField(TEXT("walls")) || (*Lattice)->HasField(TEXT("edges"))) {
    OutError = TEXT("not a plain lattice grid fixture");
    return false;
  }
  Out.Board = MsGrid(static_cast<int32>(W), static_cast<int32>(H));
  const TArray<TSharedPtr<FJsonValue>>* Fighters = nullptr;
  if (!Fx->TryGetArrayField(TEXT("fighters"), Fighters)) {
    OutError = TEXT("no fighters");
    return false;
  }
  for (const TSharedPtr<FJsonValue>& Value : *Fighters) {
    const TSharedPtr<FJsonObject> F = Value->AsObject();
    FIntPoint Pos;
    if (!F.IsValid() || !MsReadXY(F, TEXT("position"), Pos)) {
      OutError = TEXT("a fighter without position");
      return false;
    }
    double Health = 10.0, Movement = 2.0;
    F->TryGetNumberField(TEXT("health"), Health);
    const bool bMovement = F->TryGetNumberField(TEXT("movement"), Movement);
    FS08BoardFighter Fighter =
        MsFighter(F->GetStringField(TEXT("id")), F->GetStringField(TEXT("ownerId")), Pos.X, Pos.Y, Movement,
                  static_cast<int32>(Health));
    if (!bMovement) {
      Fighter.bMovementPresent = false;
      Fighter.Movement = 0;
    }
    Out.Fighters.Add(Fighter);
  }
  const TArray<TSharedPtr<FJsonValue>>* Hand = nullptr;
  if (Fx->TryGetArrayField(TEXT("hand"), Hand)) {
    for (const TSharedPtr<FJsonValue>& Value : *Hand) {
      const TSharedPtr<FJsonObject> C = Value->AsObject();
      FMsCard Card;
      Card.Id = C->GetStringField(TEXT("id"));
      double Boost = 0.0;
      Card.bHasBoost = C->TryGetNumberField(TEXT("boostValue"), Boost);
      Card.Boost = static_cast<int32>(Boost);
      Out.Hand.Add(Card);
    }
  }
  const TSharedPtr<FJsonObject>* Draft = nullptr;
  const TArray<TSharedPtr<FJsonValue>>* Moves = nullptr;
  if (!Fx->TryGetObjectField(TEXT("draft"), Draft) || !(*Draft)->TryGetArrayField(TEXT("moves"), Moves)) {
    OutError = TEXT("no draft.moves");
    return false;
  }
  (*Draft)->TryGetStringField(TEXT("boostCardId"), Out.BoostCardId);
  for (const TSharedPtr<FJsonValue>& Value : *Moves) {
    const TSharedPtr<FJsonObject> M = Value->AsObject();
    FS09DraftMove& Move = Out.Draft.AddDefaulted_GetRef();
    Move.FighterId = M->GetStringField(TEXT("fighterId"));
    // draftInputOf: dest, else the last cell of a forced path.
    FIntPoint Dest;
    const TArray<TSharedPtr<FJsonValue>>* Forced = nullptr;
    if (!MsReadXY(M, TEXT("dest"), Dest)) {
      const TSharedPtr<FJsonObject> Last =
          M->TryGetArrayField(TEXT("path"), Forced) && Forced->Num() > 0 ? Forced->Last()->AsObject() : nullptr;
      double X = 0.0, Y = 0.0;
      if (!Last.IsValid() || !Last->TryGetNumberField(TEXT("x"), X) || !Last->TryGetNumberField(TEXT("y"), Y)) {
        OutError = TEXT("a draft move without dest / path");
        return false;
      }
      Dest = FIntPoint(static_cast<int32>(X), static_cast<int32>(Y));
    }
    Move.DestX = Dest.X;
    Move.DestY = Dest.Y;
  }
  const TSharedPtr<FJsonObject>* Expect = nullptr;
  if (!Fx->TryGetObjectField(TEXT("expect"), Expect)) {
    OutError = TEXT("no expect");
    return false;
  }
  Out.Expect = *Expect;
  return true;
}

} // namespace S09MoveSelTest

using namespace S09MoveSelTest;

// ---------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelSequentialDraftTest, "Unmatched.S09.MoveSel.SequentialDraft",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelSequentialDraftTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(5, 5);
  const FS08Snapshot Snap = MsSnapshot({});
  FString Reason;

  // ---- MS-E-33 / MS-E-85: A leaves X, B ends on X (order A -> B) ----
  {
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 2), MsFighter(TEXT("b"), Me, 0, 2),
                                               MsFighter(TEXT("c"), Me, 4, 4), MsFighter(TEXT("e"), Opp, 4, 0)};
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("A drafted to (2,2)"), Ui.SetDestination(TEXT("a"), 2, 2, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("B drafted onto A's cell - A leaves it first (MS-E-85)"),
             Ui.SetDestination(TEXT("b"), 1, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("A then B"), Ui.Moves.Num(), 2);
    TestEqual(TEXT("A order 0"), Ui.MoveIndexOf(TEXT("a")), 0);
    TestEqual(TEXT("B order 1"), MsMove(Ui, TEXT("b")) ? MsMove(Ui, TEXT("b"))->Order : -1, 1);
    TestEqual(TEXT("A ok"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("ok")));
    TestEqual(TEXT("B ok"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("ok")));
    TestTrue(TEXT("draft confirmable"), Ui.Eval.IsConfirmable());
    FS09ManeuverCommand Command;
    TestTrue(TEXT("A -> B confirm legal"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestEqual(TEXT("two moves sent"), Command.Moves.Num(), 2);
    if (Command.Moves.Num() == 2) {
      TestEqual(TEXT("A sent first"), Command.Moves[0].FighterId, FString(TEXT("a")));
      TestTrue(TEXT("A path [(2,2)]"), MsSameCells(Command.Moves[0].Path, {FIntPoint(2, 2)}));
      TestTrue(TEXT("B path [(1,2)]"), MsSameCells(Command.Moves[1].Path, {FIntPoint(1, 2)}));
    }

    // ---- MS-E-34: B before A -> B is a Conflict (ally), A stays Ok ----
    const uint32 RevBefore = Ui.DraftRevision;
    TestTrue(TEXT("Ctrl+Up on B"), Ui.MoveOrder(TEXT("b"), -1, Snap, Board, Fighters));
    TestTrue(TEXT("order change re-evaluates (revision)"), Ui.DraftRevision != RevBefore);
    TestEqual(TEXT("B now first"), Ui.MoveIndexOf(TEXT("b")), 0);
    const FS09DraftMove* B = MsMove(Ui, TEXT("b"));
    TestEqual(TEXT("B conflict"), MsStatus(B), FString(TEXT("conflict")));
    if (B) {
      TestEqual(TEXT("B why.cell.ally"), MsKey(B->Reason), FString(TEXT("why.cell.ally")));
      TestTrue(TEXT("B carries the order hint"), B->Reason.Args.Contains(TEXT("orderHint")));
      TestTrue(TEXT("Conflict has no path"), B->Path.IsEmpty());
      TestEqual(TEXT("Conflict needs no boost"), B->RequiredBoost, 0);
    }
    TestEqual(TEXT("A still ok"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("ok")));
    TestFalse(TEXT("confirm blocked by the Conflict"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestTrue(TEXT("confirm reason names the conflict key"), Reason.Contains(TEXT("why.cell.ally")));
    TestTrue(TEXT("LastReason is the conflict reason"), MsKey(Ui.LastReason) == TEXT("why.cell.ally"));

    // ---- MS-E-96: no-op order changes ----
    const uint32 RevNoOp = Ui.DraftRevision;
    TestFalse(TEXT("Ctrl+Up on the first move"), Ui.MoveOrder(TEXT("b"), -1, Snap, Board, Fighters));
    TestFalse(TEXT("Ctrl+Down on the last move"), Ui.MoveOrder(TEXT("a"), +1, Snap, Board, Fighters));
    TestFalse(TEXT("Ctrl+Up on a fighter without a move"), Ui.MoveOrder(TEXT("c"), -1, Snap, Board, Fighters));
    TestEqual(TEXT("no-op order changes do nothing"), Ui.DraftRevision, RevNoOp);
    TestTrue(TEXT("Ctrl+Down on B restores A -> B"), Ui.MoveOrder(TEXT("b"), +1, Snap, Board, Fighters));
    TestEqual(TEXT("B ok again"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("ok")));

    // ---- MS-E-38: an overwrite keeps the number ----
    TestTrue(TEXT("A overwritten to (2,1)"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("A keeps order 0"), Ui.MoveIndexOf(TEXT("a")), 0);
    TestEqual(TEXT("still two moves"), Ui.Moves.Num(), 2);

    // ---- MS-E-114: clear frees the number, a re-assign goes last ----
    Ui.ClearMove(TEXT("a"));
    TestEqual(TEXT("A cleared"), Ui.MoveIndexOf(TEXT("a")), INDEX_NONE);
    TestEqual(TEXT("B moved up to 0"), MsMove(Ui, TEXT("b")) ? MsMove(Ui, TEXT("b"))->Order : -1, 0);
    TestEqual(TEXT("B conflicts once A stays on (1,2)"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("conflict")));
    TestTrue(TEXT("A re-assigned"), Ui.SetDestination(TEXT("a"), 2, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("A re-assigned goes last"), Ui.MoveIndexOf(TEXT("a")), 1);
    TestEqual(TEXT("B still before A: conflict"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("conflict")));
    TestTrue(TEXT("Ctrl+Up on A fixes the order"), Ui.MoveOrder(TEXT("a"), -1, Snap, Board, Fighters));
    TestTrue(TEXT("all ok after the reorder"), Ui.Eval.IsConfirmable() && Ui.Eval.NumOk == 2);

    // ---- refusals with reasons (MS-E-21 enemy, MS-E-36 same target) ----
    TestFalse(TEXT("enemy cell refused"), Ui.SetDestination(TEXT("c"), 4, 0, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.cell.enemy"), MsKey(Ui.LastReason), FString(TEXT("why.cell.enemy")));
    TestFalse(TEXT("a second fighter on A's target refused"),
              Ui.SetDestination(TEXT("c"), 2, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.cell.ally"), MsKey(Ui.LastReason), FString(TEXT("why.cell.ally")));
    TestEqual(TEXT("the refused cells left the draft unchanged"), Ui.Moves.Num(), 2);
  }

  // ---- MS-E-36 on a raw draft: two targets in one cell -> second Conflict ----
  {
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 2), MsFighter(TEXT("b"), Me, 0, 2)};
    TArray<FS09DraftMove> Draft;
    Draft.AddDefaulted(2);
    Draft[0].FighterId = TEXT("a");
    Draft[0].DestX = 2;
    Draft[0].DestY = 2;
    Draft[1].FighterId = TEXT("b");
    Draft[1].DestX = 2;
    Draft[1].DestY = 2;
    const FS09DraftEval Eval = FS09DraftEval::Evaluate(Board, Fighters, Draft, {}, FString(), Me);
    TestEqual(TEXT("first target ok"), MsStatus(&Draft[0]), FString(TEXT("ok")));
    TestEqual(TEXT("second target conflict"), MsStatus(&Draft[1]), FString(TEXT("conflict")));
    TestEqual(TEXT("second: why.cell.ally"), MsKey(Draft[1].Reason), FString(TEXT("why.cell.ally")));
    TestTrue(TEXT("not confirmable"), !Eval.IsConfirmable() && Eval.NumConflict == 1);
  }

  // ---- MS-E-35: a swap is impossible in any order ----
  {
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 2), MsFighter(TEXT("b"), Me, 0, 2)};
    for (int32 First = 0; First < 2; ++First) {
      TArray<FS09DraftMove> Draft;
      Draft.AddDefaulted(2);
      Draft[First].FighterId = TEXT("a");
      Draft[First].DestX = 0;
      Draft[First].DestY = 2;
      Draft[1 - First].FighterId = TEXT("b");
      Draft[1 - First].DestX = 1;
      Draft[1 - First].DestY = 2;
      FS09DraftEval::Evaluate(Board, Fighters, Draft, {}, FString(), Me);
      for (const FS09DraftMove& Move : Draft) {
        TestEqual(FString::Printf(TEXT("swap (A %s): %s conflict"), First == 0 ? TEXT("first") : TEXT("second"),
                                  *Move.FighterId),
                  MsStatus(&Move), FString(TEXT("conflict")));
        TestEqual(FString::Printf(TEXT("swap: %s why.swap.impossible"), *Move.FighterId), MsKey(Move.Reason),
                  FString(TEXT("why.swap.impossible")));
      }
    }
    // Through the draft operations: B leaves, A takes B's cell, then B tries A's.
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("B leaves to (0,1)"), Ui.SetDestination(TEXT("b"), 0, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("A takes B's cell"), Ui.SetDestination(TEXT("a"), 0, 2, Snap, Board, Fighters, Reason));
    TestFalse(TEXT("B onto A's cell refused"), Ui.SetDestination(TEXT("b"), 1, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.swap.impossible"), MsKey(Ui.LastReason), FString(TEXT("why.swap.impossible")));
    TestTrue(TEXT("B keeps (0,1)"), MsMove(Ui, TEXT("b")) && MsMove(Ui, TEXT("b"))->DestY == 1);
  }

  // ---- MS-E-37: a later path through the already moved ally ----
  {
    // Corridor y = 1 of a 6 x 3 board.
    const FS08BoardModel Corridor =
        MsGrid(6, 3, {FIntPoint(0, 0), FIntPoint(1, 0), FIntPoint(2, 0), FIntPoint(3, 0), FIntPoint(4, 0),
                      FIntPoint(5, 0), FIntPoint(0, 2), FIntPoint(1, 2), FIntPoint(2, 2), FIntPoint(3, 2),
                      FIntPoint(4, 2), FIntPoint(5, 2)});
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 1), MsFighter(TEXT("b"), Me, 0, 1, 4.0)};
    FS09CommandUi Ui = MsOpen(Snap, Corridor, Fighters);
    TestTrue(TEXT("A to (3,1)"), Ui.SetDestination(TEXT("a"), 3, 1, Snap, Corridor, Fighters, Reason));
    TestTrue(TEXT("B through A's new cell to (4,1)"),
             Ui.SetDestination(TEXT("b"), 4, 1, Snap, Corridor, Fighters, Reason));
    const FS09DraftMove* B = MsMove(Ui, TEXT("b"));
    TestEqual(TEXT("B ok"), MsStatus(B), FString(TEXT("ok")));
    TestTrue(TEXT("B path passes the moved ally"),
             B && MsSameCells(B->Path, {FIntPoint(1, 1), FIntPoint(2, 1), FIntPoint(3, 1), FIntPoint(4, 1)}));
    // No path at all (the corridor is walled): why.cell.no.path.
    TestFalse(TEXT("a wall refused"), Ui.SetDestination(TEXT("a"), 3, 0, Snap, Corridor, Fighters, Reason));
    TestEqual(TEXT("why.cell.no.path"), MsKey(Ui.LastReason), FString(TEXT("why.cell.no.path")));
  }

  // ---- MS-E-05: different movements per fighter (Leshen 1 / Wolves 3) ----
  {
    const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("leshen"), Me, 0, 0, 1.0),
                                               MsFighter(TEXT("wolf"), Me, 4, 4, 3.0)};
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("Leshen selectable"), Ui.SelectFighter(TEXT("leshen"), Snap, Board, Fighters));
    TestEqual(TEXT("Leshen base 1"), Ui.SelectedTiers.Base, 1);
    TestTrue(TEXT("Leshen base tier = 1 step"), MsAllWithin(Ui.SelectedTiers, Ui.SelectedTiers.BaseTier, 0, 1) &&
                                                    Ui.SelectedTiers.BaseTier.Num() == 2 &&
                                                    Ui.SelectedTiers.BoostTier.Num() == 0);
    TestEqual(TEXT("legacy reach = start + base tier"), Ui.ReachableCells.Num(), 3);
    TestFalse(TEXT("Leshen 2 steps without a boost refused"),
              Ui.SetDestination(TEXT("leshen"), 2, 0, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.cell.unreachable"), MsKey(Ui.LastReason), FString(TEXT("why.cell.unreachable")));
    TestEqual(TEXT("need 2"), Ui.LastReason.Args.FindRef(TEXT("need")), FString(TEXT("2")));
    TestEqual(TEXT("have 1"), Ui.LastReason.Args.FindRef(TEXT("have")), FString(TEXT("1")));
    TestTrue(TEXT("Wolf 3 steps ok"), Ui.SetDestination(TEXT("wolf"), 1, 4, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("Wolf base 3, ok"), MsMove(Ui, TEXT("wolf")) ? MsMove(Ui, TEXT("wolf"))->Base : -1, 3);
  }

  // ---- the command matches the golden fixtures (MS-AT-02 drafts) ----
  for (const TCHAR* Name : {TEXT("multi-cobble-free-then-occupy"), TEXT("multi-cobble-occupy-before-free")}) {
    FMsFixture Fx;
    FString Error;
    if (!MsLoadGridFixture(Name, Fx, Error)) {
      AddError(FString::Printf(TEXT("%s: %s"), Name, *Error));
      continue;
    }
    const FS08Snapshot FxSnap = MsSnapshot(Fx.Hand);
    FS09CommandUi Ui = MsOpen(FxSnap, Fx.Board, Fx.Fighters);
    Ui.Moves = Fx.Draft;
    Ui.BoostCardId = Fx.BoostCardId;
    FS09ManeuverCommand Command;
    const bool bConfirmed = Ui.ConfirmManeuver(FxSnap, Fx.Board, Fx.Fighters, Command, Reason);
    FString ServerOutcome;
    Fx.Expect->TryGetStringField(TEXT("server"), ServerOutcome);
    TestEqual(FString::Printf(TEXT("%s: confirm iff the server accepts"), Name), bConfirmed, ServerOutcome == TEXT("ok"));
    const TSharedPtr<FJsonObject>* Status = nullptr;
    const TSharedPtr<FJsonObject>* Paths = nullptr;
    Fx.Expect->TryGetObjectField(TEXT("status"), Status);
    Fx.Expect->TryGetObjectField(TEXT("paths"), Paths);
    for (const FS09DraftMove& Move : Ui.Moves) {
      FString Want;
      if (Status && (*Status)->TryGetStringField(Move.FighterId, Want)) {
        TestEqual(FString::Printf(TEXT("%s: status of %s"), Name, *Move.FighterId), MsStatus(&Move), Want);
      }
    }
    if (bConfirmed && Paths) {
      for (const FS08ManeuverMove& Sent : Command.Moves) {
        const TArray<TSharedPtr<FJsonValue>>* WantPath = nullptr;
        TArray<FIntPoint> Want;
        if ((*Paths)->TryGetArrayField(Sent.FighterId, WantPath)) {
          for (const TSharedPtr<FJsonValue>& Cell : *WantPath) {
            const TArray<TSharedPtr<FJsonValue>>& XY = Cell->AsArray();
            if (XY.Num() == 2) Want.Add(FIntPoint(static_cast<int32>(XY[0]->AsNumber()), static_cast<int32>(XY[1]->AsNumber())));
          }
        }
        TestTrue(FString::Printf(TEXT("%s: sent path of %s equals the fixture"), Name, *Sent.FighterId),
                 Sent.Path == Want);
      }
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelBoostRecomputeTest, "Unmatched.S09.MoveSel.BoostRecompute",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelBoostRecomputeTest::RunTest(const FString&) {
  // Open 10 x 3 grid: distances are manhattan.
  const FS08BoardModel Board = MsGrid(10, 3);
  const TArray<FMsCard> Hand = {{TEXT("c2"), true, 2},  {TEXT("c4"), true, 4},  {TEXT("c0"), true, 0},
                                {TEXT("cn"), false, 0}, {TEXT("c4b"), true, 4}};
  const FS08Snapshot Snap = MsSnapshot(Hand);
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 0), MsFighter(TEXT("b"), Me, 0, 2),
                                             MsFighter(TEXT("e"), Opp, 9, 1)};
  FString Reason;

  // ---- MS-E-07 / MS-E-08: offers, null never, +0 labelled ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TArray<FString> Offered;
    for (const FS09BoostCard& Card : Ui.BoostOffers()) Offered.Add(Card.InstanceId + Card.Label());
    TestEqual(TEXT("null BOOST never offered; +0 offered as '+0'"), FString::Join(Offered, TEXT(",")),
              FString(TEXT("c2+2,c4+4,c0+0,c4b+4")));
    TestFalse(TEXT("null BOOST card refused"), Ui.ToggleBoostCard(TEXT("cn"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.boost.no.value"), MsKey(Ui.LastReason), FString(TEXT("why.boost.no.value")));
    TestTrue(TEXT("no boost after the refusal"), Ui.BoostCardId.IsEmpty());
    TestEqual(TEXT("max hand BOOST ignores null"), Ui.Eval.MaxBoost, 4);
  }

  // ---- MS-E-14 / MS-E-13 / MS-E-78: one move, boost swapped and removed ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("A selected"), Ui.SelectFighter(TEXT("a"), Snap, Board, Fighters));
    // MS-E-80 without a card: base <= 3, boost tier 4..7, chip = dist - movement.
    TestEqual(TEXT("base steps 3"), Ui.SelectedTiers.BaseSteps, 3);
    TestEqual(TEXT("boost steps 3 + 4"), Ui.SelectedTiers.BoostSteps, 7);
    TestTrue(TEXT("base tier within 1..3"), MsAllWithin(Ui.SelectedTiers, Ui.SelectedTiers.BaseTier, 0, 3) &&
                                               Ui.SelectedTiers.BaseTier.Contains(FIntPoint(3, 0)));
    TestTrue(TEXT("boost tier within 4..7"), MsAllWithin(Ui.SelectedTiers, Ui.SelectedTiers.BoostTier, 3, 7) &&
                                                Ui.SelectedTiers.BoostTier.Contains(FIntPoint(4, 0)) &&
                                                Ui.SelectedTiers.BoostTier.Contains(FIntPoint(7, 0)));
    TestEqual(TEXT("chip at 6 steps = +3"), Ui.SelectedTiers.ChipAt(FIntPoint(6, 0)), 3);
    TestEqual(TEXT("no chip on the base tier"), Ui.SelectedTiers.ChipAt(FIntPoint(2, 0)), 0);

    // Beyond the best boost: need 8, have 3 + 4.
    TestFalse(TEXT("8 steps refused"), Ui.SetDestination(TEXT("a"), 8, 0, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("why.cell.unreachable"), MsKey(Ui.LastReason), FString(TEXT("why.cell.unreachable")));
    TestTrue(TEXT("need 8 have 7"), Ui.LastReason.Args.FindRef(TEXT("need")) == TEXT("8") &&
                                        Ui.LastReason.Args.FindRef(TEXT("have")) == TEXT("7"));

    // MS-E-14: boost-tier cell without a card -> NeedBoost(3), cards >= 3 lit.
    TestTrue(TEXT("6 steps accepted as NeedBoost"), Ui.SetDestination(TEXT("a"), 6, 0, Snap, Board, Fighters, Reason));
    const FS09DraftMove* A = MsMove(Ui, TEXT("a"));
    TestEqual(TEXT("NeedBoost"), MsStatus(A), FString(TEXT("needBoost")));
    TestEqual(TEXT("RequiredBoost 3"), A ? A->RequiredBoost : -1, 3);
    TestEqual(TEXT("why.cell.needs.boost"), A ? MsKey(A->Reason) : FString(), FString(TEXT("why.cell.needs.boost")));
    TestEqual(TEXT("badge 6/3 need +3"), A ? A->BadgeText() : FString(), FString(TEXT("6/3 \u00B7 need +3")));
    TestEqual(TEXT("highlight BOOST >= 3"), Ui.Eval.HighlightMinBoost, 3);
    TestEqual(TEXT("lit cards c4, c4b"), FString::Join(Ui.Eval.HighlightCardIds, TEXT(",")),
              FString(TEXT("c4,c4b")));
    FS09ManeuverCommand Command;
    TestFalse(TEXT("NeedBoost blocks the confirm"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestTrue(TEXT("confirm reason: needs boost"), Reason.Contains(TEXT("why.cell.needs.boost")));

    // MS-E-78: +2 selected, movement 3, 6 steps -> NeedBoost(3), badge "6/5 need +3".
    const uint32 Rev = Ui.DraftRevision;
    TestTrue(TEXT("+2 selected"), Ui.ToggleBoostCard(TEXT("c2"), Snap, Board, Fighters, Reason));
    TestTrue(TEXT("re-evaluated in the same call"), Ui.DraftRevision != Rev);
    A = MsMove(Ui, TEXT("a"));
    TestEqual(TEXT("still NeedBoost(3), not 1"), A ? A->RequiredBoost : -1, 3);
    TestEqual(TEXT("badge 6/5 need +3"), A ? A->BadgeText() : FString(), FString(TEXT("6/5 \u00B7 need +3")));
    TestEqual(TEXT("lit cards still c4, c4b"), FString::Join(Ui.Eval.HighlightCardIds, TEXT(",")),
              FString(TEXT("c4,c4b")));
    // MS-E-80 with +2: base <= 5, boost tier 6..7.
    TestEqual(TEXT("base steps 5 with +2"), Ui.SelectedTiers.BaseSteps, 5);
    TestTrue(TEXT("boost tier 6..7 with +2"), MsAllWithin(Ui.SelectedTiers, Ui.SelectedTiers.BoostTier, 5, 7) &&
                                                 Ui.SelectedTiers.BoostTier.Contains(FIntPoint(6, 0)) &&
                                                 Ui.SelectedTiers.BaseTier.Contains(FIntPoint(5, 0)));
    TestTrue(TEXT("legacy reach follows the boost (5 steps)"), Ui.ReachableCells.Contains(FS08BoardModel::CellKey(5, 0)) &&
                                                                  !Ui.ReachableCells.Contains(FS08BoardModel::CellKey(6, 0)));

    // +4 replaces +2: Ok, nothing lit, boost tier empty (s = M).
    TestTrue(TEXT("+4 replaces +2"), Ui.ToggleBoostCard(TEXT("c4"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("one card per maneuver"), Ui.BoostCardId, FString(TEXT("c4")));
    TestEqual(TEXT("Ok with +4"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("ok")));
    TestEqual(TEXT("badge 6/7"), MsMove(Ui, TEXT("a")) ? MsMove(Ui, TEXT("a"))->BadgeText() : FString(),
              FString(TEXT("6/7")));
    TestEqual(TEXT("nothing lit"), Ui.Eval.HighlightCardIds.Num(), 0);
    TestEqual(TEXT("boost tier empty at s = M"), Ui.SelectedTiers.BoostTier.Num(), 0);
    TestTrue(TEXT("confirm legal with +4"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestEqual(TEXT("boost card sent"), Command.BoostCardId, FString(TEXT("c4")));

    // MS-E-12: the second copy is a different exact instance.
    TestTrue(TEXT("copy c4b replaces c4"), Ui.ToggleBoostCard(TEXT("c4b"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("exact copy selected"), Ui.BoostCardId, FString(TEXT("c4b")));

    // MS-E-13: boost removed -> NeedBoost (not Conflict), the move stays.
    TestTrue(TEXT("boost toggled off"), Ui.ToggleBoostCard(TEXT("c4b"), Snap, Reason));
    TestTrue(TEXT("no boost"), Ui.BoostCardId.IsEmpty());
    TestEqual(TEXT("NeedBoost after removal"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("needBoost")));
    TestEqual(TEXT("the move stays"), Ui.Moves.Num(), 1);

    // MS-E-08: +0 is a legal pick that changes nothing.
    TestTrue(TEXT("+0 selected"), Ui.ToggleBoostCard(TEXT("c0"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("selected BOOST 0"), Ui.Eval.SelectedBoost, 0);
    TestEqual(TEXT("NeedBoost(3) with +0"), MsMove(Ui, TEXT("a")) ? MsMove(Ui, TEXT("a"))->RequiredBoost : -1, 3);
    TestEqual(TEXT("base steps unchanged by +0"), Ui.SelectedTiers.BaseSteps, 3);

    // Deselect drops the tiers with the id; a local reset keeps the hand data.
    Ui.DeselectFighter();
    TestTrue(TEXT("deselect clears tiers and reach"),
             Ui.SelectedFighterId.IsEmpty() && !Ui.SelectedTiers.bValid && Ui.ReachableCells.Num() == 0);
    Ui.CancelDraft();
    TestTrue(TEXT("reset empties the draft"), Ui.Moves.Num() == 0 && Ui.BoostCardId.IsEmpty());
    TestEqual(TEXT("reset keeps the hand's max BOOST"), Ui.Eval.MaxBoost, 4);
    TestEqual(TEXT("reset keeps the offers"), Ui.BoostOffers().Num(), 4);
  }

  // ---- MS-E-79: two moves needing 2 and 4 ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("A needs +2"), Ui.SetDestination(TEXT("a"), 5, 0, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("B needs +4"), Ui.SetDestination(TEXT("b"), 7, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("A required 2"), MsMove(Ui, TEXT("a")) ? MsMove(Ui, TEXT("a"))->RequiredBoost : -1, 2);
    TestEqual(TEXT("B required 4"), MsMove(Ui, TEXT("b")) ? MsMove(Ui, TEXT("b"))->RequiredBoost : -1, 4);
    TestEqual(TEXT("highlight BOOST >= 4"), Ui.Eval.HighlightMinBoost, 4);
    TestEqual(TEXT("lit c4, c4b"), FString::Join(Ui.Eval.HighlightCardIds, TEXT(",")), FString(TEXT("c4,c4b")));
    TestTrue(TEXT("+2 selected"), Ui.ToggleBoostCard(TEXT("c2"), Snap, Board, Fighters, Reason));
    TestEqual(TEXT("+2 solves A"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("ok")));
    TestEqual(TEXT("+2 leaves B NeedBoost(4)"), MsStatus(MsMove(Ui, TEXT("b"))), FString(TEXT("needBoost")));
    TestTrue(TEXT("+4 selected"), Ui.ToggleBoostCard(TEXT("c4"), Snap, Board, Fighters, Reason));
    TestTrue(TEXT("+4 solves both"), Ui.Eval.IsConfirmable() && Ui.Eval.NumOk == 2);
  }

  // ---- a raw move beyond the best boost is a Conflict (no path within
  // base + max hand BOOST), never NeedBoost ----
  {
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    Ui.Moves.AddDefaulted(1);
    Ui.Moves[0].FighterId = TEXT("a");
    Ui.Moves[0].DestX = 9;
    Ui.Moves[0].DestY = 2; // 11 steps: beyond 3 + 4
    FS09ManeuverCommand Command;
    TestFalse(TEXT("a raw move beyond the best boost does not confirm"),
              Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
    TestEqual(TEXT("it is a Conflict, not NeedBoost"), MsStatus(MsMove(Ui, TEXT("a"))), FString(TEXT("conflict")));
    TestEqual(TEXT("why.cell.unreachable"), MsKey(Ui.Moves[0].Reason), FString(TEXT("why.cell.unreachable")));
  }
  return true;
}

// ---- MS-T-04 ------------------------------------------------------------------

namespace S09MoveSelTest {

/** Fighter projection entry (the shape DecodeFighters reads); Movement is
 *  set raw (number, string, null) unless absent. */
TSharedRef<FJsonObject> MsFighterJson(const FString& Id, const FString& Owner, int32 X, int32 Y, int32 Health,
                                      TSharedPtr<FJsonValue> Movement, bool bDefeated = false,
                                      const FString& Effect = FString()) {
  TSharedRef<FJsonObject> F = MakeShared<FJsonObject>();
  F->SetStringField(TEXT("id"), Id);
  F->SetStringField(TEXT("ownerId"), Owner);
  F->SetStringField(TEXT("heroId"), TEXT("hero-") + Owner);
  F->SetStringField(TEXT("name"), Id);
  F->SetStringField(TEXT("type"), TEXT("MINION"));
  F->SetNumberField(TEXT("health"), Health);
  F->SetNumberField(TEXT("maxHealth"), 10);
  TSharedRef<FJsonObject> Pos = MakeShared<FJsonObject>();
  Pos->SetNumberField(TEXT("x"), X);
  Pos->SetNumberField(TEXT("y"), Y);
  F->SetObjectField(TEXT("position"), Pos);
  F->SetStringField(TEXT("attackType"), TEXT("melee"));
  F->SetBoolField(TEXT("isDefeated"), bDefeated);
  TArray<TSharedPtr<FJsonValue>> Effects;
  if (!Effect.IsEmpty()) {
    TSharedRef<FJsonObject> E = MakeShared<FJsonObject>();
    E->SetStringField(TEXT("type"), Effect);
    Effects.Add(MakeShared<FJsonValueObject>(E));
  }
  F->SetArrayField(TEXT("effects"), Effects);
  if (Movement.IsValid()) F->SetField(TEXT("movement"), Movement);
  return F;
}

TArray<FS08BoardFighter> MsDecode(const TArray<TSharedRef<FJsonObject>>& Entries) {
  TArray<TSharedPtr<FJsonValue>> Values;
  for (const TSharedRef<FJsonObject>& Entry : Entries) Values.Add(MakeShared<FJsonValueObject>(Entry));
  TArray<FS08BoardFighter> Out;
  FS08BoardModel::DecodeFighters(MakeShared<FJsonValueArray>(Values), Out);
  return Out;
}

TSharedPtr<FJsonValue> MsNum(double V) { return MakeShared<FJsonValueNumber>(V); }
TSharedPtr<FJsonValue> MsStr(const TCHAR* V) { return MakeShared<FJsonValueString>(V); }

/** Snapshot with metadata.pendingEffects = [one head of the viewer]: Type
 *  MOVE / PLACE; Value < 0 = no `value` field (MOVE allowance 1). */
FS08Snapshot MsPendingMoveSnapshot(int32 Value, const TCHAR* Type = TEXT("MOVE"), bool bPassThrough = false,
                                   bool bRevive = false) {
  FS08Snapshot Snapshot = MsSnapshot({}, FString());
  const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*Snapshot.Metadata->AsObject());
  TSharedRef<FJsonObject> Head = MakeShared<FJsonObject>();
  Head->SetStringField(TEXT("id"), TEXT("effect-1"));
  Head->SetStringField(TEXT("playerId"), Me);
  Head->SetStringField(TEXT("type"), Type);
  if (Value >= 0) Head->SetNumberField(TEXT("value"), Value);
  if (bPassThrough) Head->SetBoolField(TEXT("canPassThroughEnemies"), true);
  if (bRevive) Head->SetBoolField(TEXT("restoreFullHealth"), true);
  Head->SetStringField(TEXT("fighterName"), TEXT(""));
  Head->SetStringField(TEXT("zoneFighterName"), TEXT(""));
  Head->SetStringField(TEXT("mode"), TEXT(""));
  Head->SetStringField(TEXT("text"), TEXT("Move up to 2 spaces"));
  TArray<TSharedPtr<FJsonValue>> Effects = {MakeShared<FJsonValueObject>(Head)};
  Meta->SetArrayField(TEXT("pendingEffects"), Effects);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
  return Snapshot;
}

/** The viewer's snapshot with metadata.pendingHandDiscard (no pendingManeuver). */
FS08Snapshot MsDiscardSnapshot(const TArray<FMsCard>& Hand, int32 Seq) {
  FS08Snapshot Snapshot = MsSnapshot(Hand, FString(), Seq);
  Snapshot.Phase = TEXT("TURN_END");
  const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*Snapshot.Metadata->AsObject());
  TSharedRef<FJsonObject> Discard = MakeShared<FJsonObject>();
  Discard->SetStringField(TEXT("id"), TEXT("discard:1:30"));
  Discard->SetStringField(TEXT("playerId"), Me);
  Discard->SetNumberField(TEXT("count"), 1);
  Meta->SetObjectField(TEXT("pendingHandDiscard"), Discard);
  Snapshot.Metadata = MakeShared<FJsonValueObject>(Meta);
  return Snapshot;
}

bool MsTraced(const FS09CommandUi& Ui, const FString& Needle, int32& OutCount) {
  OutCount = 0;
  for (const FString& Line : Ui.DraftTrace) OutCount += Line.Contains(Needle) ? 1 : 0;
  return OutCount > 0;
}

void MsBindCache(FS09CommandUi& Ui, FS08FlowController& Flow) {
  Ui.StoreDraftHook = [&Flow](const FS08ManeuverDraftCache& Draft) { Flow.StoreManeuverDraft(Draft); };
  Ui.RecallDraftHook = [&Flow](const FString& Id, FS08ManeuverDraftCache& Out) {
    return Flow.RecallManeuverDraft(Id, Out);
  };
}

// The live fixture 04 (S08 evidence) - a full snapshot the controller's
// critical-field gate accepts (the SubmitManeuver leg needs one).
const TCHAR* const LiveHost = TEXT("cmugykjjb0000wi9w2nq4qlkj");

bool MsLoadLiveSnapshot(FS08Snapshot& Out) {
  FString Dir;
  if (!FParse::Value(FCommandLine::Get(), TEXT("S08Fixtures="), Dir) || Dir.IsEmpty()) {
    Dir = FPaths::Combine(FPaths::ProjectDir(), TEXT("../../docs/game-design/evidence/S08/fixtures"));
  }
  FString Text;
  if (!FFileHelper::LoadFileToString(Text, *FPaths::Combine(Dir, TEXT("04-game-state-query-host.json")))) return false;
  TSharedPtr<FJsonValue> Value;
  FString Problem;
  if (!FS08Contracts::TryParseJsonValue(Text, Value, Problem)) return false;
  const TSharedPtr<FJsonObject>* Root = nullptr;
  if (!Value->TryGetObject(Root) || !Root->IsValid()) return false;
  FString Body;
  const TSharedPtr<FJsonObject>* RawObject = nullptr;
  if ((*Root)->TryGetStringField(TEXT("raw"), Body)) {
    // raw is the response text
  } else if ((*Root)->TryGetObjectField(TEXT("raw"), RawObject) && RawObject->IsValid()) {
    const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(RawObject->ToSharedRef(), Writer);
  }
  FString RawState;
  FS08GraphQLError Error;
  if (!FS08Contracts::ParseGameStateQuery(Body, Out, RawState, Error)) return false;
  const TSharedRef<FJsonObject> Meta = MakeShared<FJsonObject>(*(Out.Metadata->AsObject()));
  TSharedRef<FJsonObject> Pending = MakeShared<FJsonObject>();
  Pending->SetStringField(TEXT("id"), TEXT("maneuver:1:5"));
  Pending->SetStringField(TEXT("playerId"), LiveHost);
  Meta->SetObjectField(TEXT("pendingManeuver"), Pending);
  Out.Metadata = MakeShared<FJsonValueObject>(Meta);
  return true;
}

/** graphql-transport-ws 'next' for the harness op s08-1 at the baseline seq
 *  (proves the operation live; the equal seq merges). */
FString MsBarrierFrame(const FS08Snapshot& Baseline) {
  TSharedRef<FJsonObject> Event = MakeShared<FJsonObject>();
  Event->SetNumberField(TEXT("sequenceNumber"), Baseline.SequenceNumber);
  Event->SetStringField(TEXT("phase"), Baseline.Phase);
  Event->SetNumberField(TEXT("turnCount"), Baseline.TurnCount);
  Event->SetStringField(TEXT("currentTurnPlayerId"), Baseline.CurrentTurnPlayerId);
  TSharedRef<FJsonObject> Data = MakeShared<FJsonObject>();
  Data->SetObjectField(TEXT("gameStateUpdated"), Event);
  TSharedRef<FJsonObject> Payload = MakeShared<FJsonObject>();
  Payload->SetObjectField(TEXT("data"), Data);
  TSharedRef<FJsonObject> Frame = MakeShared<FJsonObject>();
  Frame->SetStringField(TEXT("type"), TEXT("next"));
  Frame->SetStringField(TEXT("id"), TEXT("s08-1"));
  Frame->SetObjectField(TEXT("payload"), Payload);
  FString Out;
  FJsonSerializer::Serialize(Frame, TJsonWriterFactory<>::Create(&Out));
  return Out;
}

} // namespace S09MoveSelTest

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelZeroLengthNotSentTest, "Unmatched.S09.MoveSel.ZeroLengthNotSent",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelZeroLengthNotSentTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(5, 5);
  const FS08Snapshot Snap = MsSnapshot({{TEXT("c2"), true, 2}});
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 1, 1), MsFighter(TEXT("b"), Me, 3, 3)};
  FString Reason;
  FS09ManeuverCommand Command;

  // ---- MS-E-16: the own cell never becomes a move ----
  FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
  TestTrue(TEXT("own cell without a move: accepted"), Ui.SetDestination(TEXT("a"), 1, 1, Snap, Board, Fighters, Reason));
  TestEqual(TEXT("no zero-length move recorded"), Ui.Moves.Num(), 0);
  TestTrue(TEXT("A drafted"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
  TestTrue(TEXT("B drafted"), Ui.SetDestination(TEXT("b"), 4, 3, Snap, Board, Fighters, Reason));
  TestTrue(TEXT("own cell clears A's move (MS-R-11)"), Ui.SetDestination(TEXT("a"), 1, 1, Snap, Board, Fighters, Reason));
  TestEqual(TEXT("A's move gone, B's kept"), Ui.Moves.Num(), 1);
  TestEqual(TEXT("B moved up to 0"), Ui.MoveIndexOf(TEXT("b")), 0);
  int32 Clears = 0;
  MsTraced(Ui, TEXT("MS-DRAFT op=clear"), Clears);
  TestEqual(TEXT("one MS-DRAFT op=clear"), Clears, 1);

  // ---- a stay entry that slipped into the draft is never sent ----
  Ui.Moves.AddDefaulted_GetRef().FighterId = TEXT("a");
  Ui.Moves.Last().DestX = 1;
  Ui.Moves.Last().DestY = 1;
  TestTrue(TEXT("confirm with a stay entry"), Ui.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
  TestEqual(TEXT("only B in the command"), Command.Moves.Num(), 1);
  bool bEmptyPath = false;
  for (const FS08ManeuverMove& Move : Command.Moves) bEmptyPath |= Move.Path.IsEmpty();
  TestFalse(TEXT("no empty path in the command (MS-R-44)"), bEmptyPath);

  // ---- MS-E-09: no moves + a boost is a legal maneuver ----
  FS09CommandUi Boosted = MsOpen(Snap, Board, Fighters);
  TestTrue(TEXT("boost selected"), Boosted.ToggleBoostCard(TEXT("c2"), Snap, Board, Fighters, Reason));
  TestTrue(TEXT("boost without moves confirms"), Boosted.ConfirmManeuver(Snap, Board, Fighters, Command, Reason));
  TestEqual(TEXT("zero moves"), Command.Moves.Num(), 0);
  TestEqual(TEXT("boost card sent"), Command.BoostCardId, FString(TEXT("c2")));

  // ---- SubmitManeuver drops an empty path before the wire (MS-R-44) ----
  FS08Snapshot Live;
  if (!MsLoadLiveSnapshot(Live)) {
    AddError(TEXT("fixture 04 not loaded"));
    return true;
  }
  FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), LiveHost);
  TArray<FString> Traces;
  Flow.OnTrace.AddLambda([&Traces](const FString& Line) { Traces.Add(Line); });
  Flow.AttachStreamHarnessForTest(TEXT("ms-zero-game"));
  Flow.ApplySnapshot(Live);
  Flow.InjectWsFrameForTest(MsBarrierFrame(Flow.GetAppliedSnapshot()));
  TestTrue(TEXT("stream live"), Flow.IsStreamReady());
  Flow.QueueHttpResultForTest(false, {}, /*bDeferDelivery=*/true); // no real POST
  TArray<FS08ManeuverMove> Moves;
  Moves.AddDefaulted_GetRef().FighterId = TEXT("f-0-hero"); // stay: empty path
  FS08ManeuverMove& Step = Moves.AddDefaulted_GetRef();
  Step.FighterId = TEXT("f-0-sk0");
  Step.Path = {FIntPoint(0, 2)};
  TestTrue(TEXT("submit dispatched"), Flow.SubmitManeuver(TEXT("maneuver:1:5"), Moves));
  TestEqual(TEXT("one HTTP leg"), Flow.GetTestHttpSendCountForTest(), 1);
  bool bDropped = false;
  for (const FString& Line : Traces) bDropped |= Line.Contains(TEXT("MANEUVER zero-length moves dropped=1 sent=1"));
  TestTrue(TEXT("the stay entry is dropped before the wire (trace)"), bDropped);
  const TSharedPtr<FJsonObject> Sent = Flow.GetLastHttpVariablesForTest();
  const TArray<TSharedPtr<FJsonValue>>* WireMoves = nullptr;
  TestTrue(TEXT("maneuver variables captured"), Sent.IsValid() && Sent->TryGetArrayField(TEXT("moves"), WireMoves));
  if (WireMoves) {
    TestEqual(TEXT("one move on the wire"), WireMoves->Num(), 1);
    for (const TSharedPtr<FJsonValue>& Move : *WireMoves) {
      const TArray<TSharedPtr<FJsonValue>>* Path = nullptr;
      TestTrue(TEXT("the wire move has a non-empty path"),
               Move->AsObject()->TryGetArrayField(TEXT("path"), Path) && Path->Num() == 1);
      TestEqual(TEXT("the wire move is the sidekick's"), Move->AsObject()->GetStringField(TEXT("fighterId")),
                FString(TEXT("f-0-sk0")));
    }
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelMovementParityTest, "Unmatched.S09.MoveSel.MovementParity",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelMovementParityTest::RunTest(const FString&) {
  const FS08BoardModel Board = MsGrid(9, 9);
  const FS08Snapshot Snap = MsSnapshot({});
  FString Reason;

  // ---- MS-E-04 / MS-E-107: getFighterMovement on the raw value ----
  {
    struct FCase {
      const TCHAR* Id;
      TSharedPtr<FJsonValue> Raw; // invalid = absent
      int32 Base;
    };
    const TArray<FCase> Cases = {{TEXT("m0"), MsNum(0), 2},        {TEXT("mabsent"), nullptr, 2},
                                 {TEXT("mnull"), MakeShared<FJsonValueNull>(), 2},
                                 {TEXT("m25"), MsNum(2.5), 2},     {TEXT("m35"), MsNum(3.5), 2},
                                 {TEXT("ms3"), MsStr(TEXT("3")), 3}, {TEXT("ms35"), MsStr(TEXT("3.5")), 2},
                                 {TEXT("m4"), MsNum(4), 4}};
    const FS08BoardModel Open = MsGrid(13, 13);
    for (const FCase& Case : Cases) {
      const TArray<FS08BoardFighter> Fighters = MsDecode({MsFighterJson(Case.Id, Me, 6, 6, 5, Case.Raw)});
      FS09CommandUi Ui = MsOpen(Snap, Open, Fighters);
      TestTrue(FString::Printf(TEXT("%s selectable"), Case.Id), Ui.SelectFighter(Case.Id, Snap, Open, Fighters));
      TestEqual(FString::Printf(TEXT("%s base"), Case.Id), Ui.SelectedTiers.Base, Case.Base);
      TestTrue(FString::Printf(TEXT("%s: base steps reachable"), Case.Id),
               Ui.SetDestination(Case.Id, 6 + Case.Base, 6, Snap, Open, Fighters, Reason));
      TestFalse(FString::Printf(TEXT("%s: base + 1 refused without a boost"), Case.Id),
                Ui.SetDestination(Case.Id, 6, 6 + Case.Base + 1, Snap, Open, Fighters, Reason));
      TestEqual(FString::Printf(TEXT("%s: have = base"), Case.Id), Ui.LastReason.Args.FindRef(TEXT("have")),
                FString::FromInt(Case.Base));
    }
  }

  // ---- MS-E-40 / MS-R-05: an immobilized fighter is greyed, others move ----
  {
    const TArray<FS08BoardFighter> Fighters =
        MsDecode({MsFighterJson(TEXT("imm"), Me, 1, 1, 5, MsNum(3), false, TEXT("immobilized")),
                  MsFighterJson(TEXT("free"), Me, 6, 6, 5, MsNum(3))});
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    FS09Reason Why;
    TestFalse(TEXT("CanMoveFighter refuses the immobilized"), Ui.CanMoveFighter(TEXT("imm"), Fighters, Why));
    TestEqual(TEXT("why.immobilized"), MsKey(Why), FString(TEXT("why.immobilized")));
    TestEqual(TEXT("reason names the fighter"), Why.Args.FindRef(TEXT("fighterName")), FString(TEXT("imm")));
    TestFalse(TEXT("immobilized not selectable"), Ui.SelectFighter(TEXT("imm"), Snap, Board, Fighters));
    TestEqual(TEXT("select reason why.immobilized"), MsKey(Ui.LastReason), FString(TEXT("why.immobilized")));
    TestFalse(TEXT("no target for the immobilized"), Ui.SetDestination(TEXT("imm"), 2, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("refusal reason names the key"), Reason.Contains(TEXT("why.immobilized")));
    TestEqual(TEXT("nothing drafted"), Ui.Moves.Num(), 0);
    TestTrue(TEXT("the other fighter moves"), Ui.SetDestination(TEXT("free"), 6, 4, Snap, Board, Fighters, Reason));

    // A drafted move whose fighter becomes immobilized stays as a Conflict.
    const TArray<FS08BoardFighter> Before = MsDecode({MsFighterJson(TEXT("x"), Me, 1, 1, 5, MsNum(3))});
    FS09CommandUi Later = MsOpen(Snap, Board, Before);
    TestTrue(TEXT("x drafted"), Later.SetDestination(TEXT("x"), 3, 1, Snap, Board, Before, Reason));
    const TArray<FS08BoardFighter> After =
        MsDecode({MsFighterJson(TEXT("x"), Me, 1, 1, 5, MsNum(3), false, TEXT("immobilized"))});
    Later.OnSnapshot(MsSnapshot({}, ManeuverA, 6), Board, After);
    TestEqual(TEXT("the move is kept"), Later.Moves.Num(), 1);
    TestEqual(TEXT("as a Conflict"), MsStatus(MsMove(Later, TEXT("x"))), FString(TEXT("conflict")));
    TestEqual(TEXT("why.immobilized"), MsMove(Later, TEXT("x")) ? MsKey(MsMove(Later, TEXT("x"))->Reason) : FString(),
              FString(TEXT("why.immobilized")));
    TestTrue(TEXT("own-cell click still clears it"), Later.SetDestination(TEXT("x"), 1, 1, Snap, Board, After, Reason));
    TestEqual(TEXT("cleared"), Later.Moves.Num(), 0);
  }

  // ---- MS-E-23 / MS-E-24: defeated blockers and occupants ----
  {
    // Corridor y = 1 (rows 0 and 2 walled), 6 wide.
    const FS08BoardModel Corridor =
        MsGrid(6, 3, {FIntPoint(0, 0), FIntPoint(1, 0), FIntPoint(2, 0), FIntPoint(3, 0), FIntPoint(4, 0),
                      FIntPoint(5, 0), FIntPoint(0, 2), FIntPoint(1, 2), FIntPoint(2, 2), FIntPoint(3, 2),
                      FIntPoint(4, 2), FIntPoint(5, 2)});
    const TArray<FS08BoardFighter> Fighters =
        MsDecode({MsFighterJson(TEXT("m"), Me, 0, 1, 5, MsNum(4)),
                  MsFighterJson(TEXT("dirty-enemy"), Opp, 1, 1, 5, MsNum(2), /*bDefeated=*/true),
                  MsFighterJson(TEXT("dead-enemy"), Opp, 2, 1, 0, MsNum(2)),
                  MsFighterJson(TEXT("dirty-ally"), Me, 3, 1, 5, MsNum(2), /*bDefeated=*/true)});
    FS09CommandUi Ui = MsOpen(Snap, Corridor, Fighters);
    TestTrue(TEXT("through a dirty-defeated and a dead enemy onto a dirty-defeated ally's cell"),
             Ui.SetDestination(TEXT("m"), 3, 1, Snap, Corridor, Fighters, Reason));
    const FS09DraftMove* M = MsMove(Ui, TEXT("m"));
    TestTrue(TEXT("path (1,1) (2,1) (3,1)"),
             M && MsSameCells(M->Path, {FIntPoint(1, 1), FIntPoint(2, 1), FIntPoint(3, 1)}));
    TestEqual(TEXT("ok"), MsStatus(M), FString(TEXT("ok")));
  }

  // ---- MS-E-77: a dirty-defeated MOVER moves (as the server), MS-DATA ----
  {
    const TArray<FS08BoardFighter> Fighters =
        MsDecode({MsFighterJson(TEXT("dirty"), Me, 2, 2, 3, MsNum(3), /*bDefeated=*/true),
                  MsFighterJson(TEXT("dead"), Me, 5, 5, 0, MsNum(3))});
    FS09CommandUi Ui = MsOpen(Snap, Board, Fighters);
    TestTrue(TEXT("dirty-defeated mover selectable"), Ui.SelectFighter(TEXT("dirty"), Snap, Board, Fighters));
    TestTrue(TEXT("dirty-defeated mover drafted"), Ui.SetDestination(TEXT("dirty"), 4, 2, Snap, Board, Fighters, Reason));
    TestEqual(TEXT("ok"), MsStatus(MsMove(Ui, TEXT("dirty"))), FString(TEXT("ok")));
    int32 Count = 0;
    MsTraced(Ui, TEXT("MS-DATA dirtyDefeated fighter=dirty"), Count);
    TestEqual(TEXT("MS-DATA dirtyDefeated once per maneuver"), Count, 1);
    TestFalse(TEXT("health 0 is not a mover"), Ui.SelectFighter(TEXT("dead"), Snap, Board, Fighters));
    TestEqual(TEXT("why.fighter.defeated"), MsKey(Ui.LastReason), FString(TEXT("why.fighter.defeated")));
    TArray<FS08BoardFighter> WithEnemy = Fighters;
    WithEnemy.Add(MsFighter(TEXT("enemy"), Opp, 7, 7));
    FS09Reason Why;
    TestFalse(TEXT("an enemy fighter is no mover"), Ui.CanMoveFighter(TEXT("enemy"), WithEnemy, Why));
    TestEqual(TEXT("why.fighter.not.yours"), MsKey(Why), FString(TEXT("why.fighter.not.yours")));
    TestFalse(TEXT("an unknown id is no mover"), Ui.CanMoveFighter(TEXT("ghost"), WithEnemy, Why));
    TestEqual(TEXT("why.client.desync"), MsKey(Why), FString(TEXT("why.client.desync")));
  }

  // ---- pending MOVE: the moved fighter and the blockers use isLivingFighter ----
  {
    const TArray<FS08BoardFighter> Fighters =
        MsDecode({MsFighterJson(TEXT("p"), Me, 0, 4, 5, MsNum(3)),
                  MsFighterJson(TEXT("dirty-own"), Me, 8, 8, 5, MsNum(3), /*bDefeated=*/true),
                  MsFighterJson(TEXT("dirty-enemy"), Opp, 1, 4, 5, MsNum(3), /*bDefeated=*/true)});
    const FS08Snapshot Pending = MsPendingMoveSnapshot(2);
    FS09CommandUi Ui = MsOpen(Pending, Board, Fighters);
    TestTrue(TEXT("pending choice open"), Ui.Mode == ES09CommandMode::PendingChoice);
    TArray<FString> Legal;
    Ui.PendingLegalFighters(Fighters, Legal);
    TestTrue(TEXT("living own fighter is a legal MOVE target"), Legal.Contains(TEXT("p")));
    TestFalse(TEXT("dirty-defeated fighter is not (server isLivingFighter)"), Legal.Contains(TEXT("dirty-own")));
    TestTrue(TEXT("pick p"), Ui.SelectPendingFighter(TEXT("p"), Pending, Fighters, Reason));
    const TSet<uint64> Cells = Ui.ComputePendingCells(Pending, Board, Fighters);
    TestTrue(TEXT("stay is legal"), Cells.Contains(FS08BoardModel::CellKey(0, 4)));
    TestTrue(TEXT("a dirty-defeated enemy does not block"), Cells.Contains(FS08BoardModel::CellKey(2, 4)));
    TestTrue(TEXT("its cell is free"), Cells.Contains(FS08BoardModel::CellKey(1, 4)));
    TestFalse(TEXT("3 steps exceed value 2"), Cells.Contains(FS08BoardModel::CellKey(3, 4)));

    // value 0 -> only "stay" (MS-E-76); absent -> 1 step (MS-E-57).
    const FS08Snapshot Zero = MsPendingMoveSnapshot(0);
    FS09CommandUi ZeroUi = MsOpen(Zero, Board, Fighters);
    ZeroUi.SelectPendingFighter(TEXT("p"), Zero, Fighters, Reason);
    const TSet<uint64> ZeroCells = ZeroUi.ComputePendingCells(Zero, Board, Fighters);
    TestTrue(TEXT("value 0: only the own cell"), ZeroCells.Num() == 1 && ZeroCells.Contains(FS08BoardModel::CellKey(0, 4)));
    const FS08Snapshot Absent = MsPendingMoveSnapshot(-1);
    FS09CommandUi AbsentUi = MsOpen(Absent, Board, Fighters);
    AbsentUi.SelectPendingFighter(TEXT("p"), Absent, Fighters, Reason);
    const TSet<uint64> OneCells = AbsentUi.ComputePendingCells(Absent, Board, Fighters);
    TestTrue(TEXT("no value: 1 step"), OneCells.Contains(FS08BoardModel::CellKey(0, 3)) &&
                                          !OneCells.Contains(FS08BoardModel::CellKey(0, 2)));

    // A LIVING enemy blocks unless the effect passes through enemies (MS-E-60).
    TArray<FS08BoardFighter> Walled = Fighters;
    Walled.Add(MsFighter(TEXT("wall-n"), Opp, 0, 3));
    Walled.Add(MsFighter(TEXT("wall-e"), Opp, 1, 3));
    Walled.Add(MsFighter(TEXT("wall-s"), Opp, 0, 5));
    Walled.Add(MsFighter(TEXT("wall-se"), Opp, 1, 5));
    Walled.Add(MsFighter(TEXT("wall-ee"), Opp, 2, 4));
    // p at (0,4): (1,4) is free (the dirty-defeated enemy), (2,4) a living enemy.
    FS09CommandUi Blocked = MsOpen(Pending, Board, Walled);
    Blocked.SelectPendingFighter(TEXT("p"), Pending, Walled, Reason);
    const TSet<uint64> BlockedCells = Blocked.ComputePendingCells(Pending, Board, Walled);
    TestTrue(TEXT("boxed in: own cell and (1,4) only"),
             BlockedCells.Num() == 2 && BlockedCells.Contains(FS08BoardModel::CellKey(1, 4)));
    const FS08Snapshot Through = MsPendingMoveSnapshot(2, TEXT("MOVE"), /*bPassThrough=*/true);
    FS09CommandUi ThroughUi = MsOpen(Through, Board, Walled);
    ThroughUi.SelectPendingFighter(TEXT("p"), Through, Walled, Reason);
    const TSet<uint64> ThroughCells = ThroughUi.ComputePendingCells(Through, Board, Walled);
    TestTrue(TEXT("pass-through: beyond the enemies, never onto them"),
             ThroughCells.Contains(FS08BoardModel::CellKey(0, 2)) && !ThroughCells.Contains(FS08BoardModel::CellKey(0, 3)));

    // Revive PLACE may pick a defeated fighter (restoreFullHealth); a plain PLACE may not.
    TArray<FS08BoardFighter> WithDead = Fighters;
    WithDead.Add(MsFighter(TEXT("fallen"), Me, 5, 5, 3.0, 0));
    const FS08Snapshot Revive = MsPendingMoveSnapshot(-1, TEXT("PLACE"), false, /*bRevive=*/true);
    FS09CommandUi ReviveUi = MsOpen(Revive, Board, WithDead);
    TArray<FString> ReviveLegal;
    ReviveUi.PendingLegalFighters(WithDead, ReviveLegal);
    TestTrue(TEXT("revive PLACE: the fallen fighter is legal"), ReviveLegal.Contains(TEXT("fallen")));
    const FS08Snapshot Place = MsPendingMoveSnapshot(-1, TEXT("PLACE"));
    FS09CommandUi PlaceUi = MsOpen(Place, Board, WithDead);
    TArray<FString> PlaceLegal;
    PlaceUi.PendingLegalFighters(WithDead, PlaceLegal);
    TestFalse(TEXT("plain PLACE: the fallen fighter is not"), PlaceLegal.Contains(TEXT("fallen")));
    TestFalse(TEXT("plain PLACE: nor the dirty-defeated one"), PlaceLegal.Contains(TEXT("dirty-own")));
  }
  return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FS09MoveSelReconnectAndRebuildTest, "Unmatched.S09.MoveSel.ReconnectAndRebuild",
                                 EAutomationTestFlags::EditorContext | EAutomationTestFlags::ProductFilter)
bool FS09MoveSelReconnectAndRebuildTest::RunTest(const FString&) {
  // Open 6 x 3 board: row 1 is the straight line, rows 0 and 2 the detours.
  const FS08BoardModel Board = MsGrid(6, 3);
  const TArray<FMsCard> Hand = {{TEXT("c2"), true, 2}, {TEXT("c1"), true, 1}};
  const FS08Snapshot Snap = MsSnapshot(Hand, ManeuverA, 5);
  const TArray<FS08BoardFighter> Fighters = {MsFighter(TEXT("a"), Me, 0, 1), MsFighter(TEXT("b"), Me, 5, 2)};
  FString Reason;
  FS08FlowController Flow(TEXT("http://127.0.0.1:9/graphql"), TEXT("ws://127.0.0.1:9/graphql"), Me);
  Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Started);

  // ---- MS-R-55: the draft survives a gameplay-HUD reset (same id) ----
  FS09CommandUi First;
  First.ViewerId = Me;
  MsBindCache(First, Flow);
  First.OnSnapshot(Snap, Board, Fighters);
  TestTrue(TEXT("a drafted"), First.SetDestination(TEXT("a"), 3, 1, Snap, Board, Fighters, Reason));
  TestTrue(TEXT("b drafted"), First.SetDestination(TEXT("b"), 5, 0, Snap, Board, Fighters, Reason));
  TestTrue(TEXT("boost c2"), First.ToggleBoostCard(TEXT("c2"), Snap, Board, Fighters, Reason));
  FS08ManeuverDraftCache Cached;
  TestTrue(TEXT("the controller holds the draft"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  TestEqual(TEXT("cached moves in order"), FString::Join(Cached.FighterIds, TEXT(",")), FString(TEXT("a,b")));
  TestEqual(TEXT("cached boost"), Cached.BoostCardId, FString(TEXT("c2")));
  TestFalse(TEXT("another maneuver id never recalls it"), Flow.RecallManeuverDraft(TEXT("maneuver:2:9"), Cached));

  FS09CommandUi Second; // ClearGameplayHud: a fresh command UI, same controller
  Second.ViewerId = Me;
  MsBindCache(Second, Flow);
  Second.OnSnapshot(Snap, Board, Fighters);
  TestEqual(TEXT("restored: two moves"), Second.Moves.Num(), 2);
  TestTrue(TEXT("restored in order with the destinations"),
           Second.Moves.Num() == 2 && Second.Moves[0].FighterId == TEXT("a") && Second.Moves[0].DestX == 3 &&
               Second.Moves[1].FighterId == TEXT("b") && Second.Moves[1].DestY == 0);
  TestEqual(TEXT("restored boost"), Second.BoostCardId, FString(TEXT("c2")));
  TestTrue(TEXT("restored moves re-evaluated"), Second.Eval.IsConfirmable() && Second.Eval.NumOk == 2);
  int32 Restores = 0;
  TestTrue(TEXT("MS-DRAFT op=restore"), MsTraced(Second, TEXT("MS-DRAFT op=restore"), Restores));

  // Another match never restores this draft.
  Flow.SetRoomForTest(TEXT("g2"), ES08Stage::Started);
  TestFalse(TEXT("other match: no recall"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  Flow.SetRoomForTest(TEXT("g1"), ES08Stage::Started);
  TestTrue(TEXT("back in the match: recall"), Flow.RecallManeuverDraft(ManeuverA, Cached));

  // ---- MS-E-53: a new seq with changed positions re-evaluates, never deletes ----
  {
    TestTrue(TEXT("+1 replaces +2"), Second.ToggleBoostCard(TEXT("c1"), Snap, Board, Fighters, Reason));
    // An enemy now stands on a's straight line: the detour is 5 steps -> NeedBoost.
    TArray<FS08BoardFighter> Moved = Fighters;
    Moved.Add(MsFighter(TEXT("e"), Opp, 1, 1));
    Second.OnSnapshot(MsSnapshot(Hand, ManeuverA, 6), Board, Moved);
    TestEqual(TEXT("both moves kept"), Second.Moves.Num(), 2);
    const FS09DraftMove* A = MsMove(Second, TEXT("a"));
    TestEqual(TEXT("longer path: NeedBoost, not Conflict"), MsStatus(A), FString(TEXT("needBoost")));
    TestEqual(TEXT("needs +2 (5 steps, movement 3, +1 selected)"), A ? A->RequiredBoost : -1, 2);
    TestEqual(TEXT("c1 still selected"), Second.BoostCardId, FString(TEXT("c1")));
    // An enemy now stands on a's destination: Conflict, kept.
    TArray<FS08BoardFighter> Blocked = Fighters;
    Blocked.Add(MsFighter(TEXT("e"), Opp, 3, 1));
    Second.OnSnapshot(MsSnapshot(Hand, ManeuverA, 7), Board, Blocked);
    TestEqual(TEXT("still two moves"), Second.Moves.Num(), 2);
    TestEqual(TEXT("enemy on the target: Conflict"), MsStatus(MsMove(Second, TEXT("a"))), FString(TEXT("conflict")));
    TestEqual(TEXT("why.cell.enemy"), MsMove(Second, TEXT("a")) ? MsKey(MsMove(Second, TEXT("a"))->Reason) : FString(),
              FString(TEXT("why.cell.enemy")));
  }

  // ---- MS-E-15: the boost card left the hand ----
  {
    Second.OnSnapshot(MsSnapshot({{TEXT("c2"), true, 2}}, ManeuverA, 8), Board, Fighters);
    TestTrue(TEXT("boost dropped"), Second.BoostCardId.IsEmpty());
    TestEqual(TEXT("why.boost.card.gone"), MsKey(Second.LastReason), FString(TEXT("why.boost.card.gone")));
    TestEqual(TEXT("moves kept"), Second.Moves.Num(), 2);
    TestTrue(TEXT("the cache follows (no boost)"), Flow.RecallManeuverDraft(ManeuverA, Cached) && Cached.BoostCardId.IsEmpty());
  }

  // ---- MS-E-41: a fighter that died leaves the draft ----
  {
    TArray<FS08BoardFighter> Dead = Fighters;
    Dead[1].Health = 0;
    Second.OnSnapshot(MsSnapshot(Hand, ManeuverA, 9), Board, Dead);
    TestEqual(TEXT("b's move dropped"), Second.MoveIndexOf(TEXT("b")), INDEX_NONE);
    TestEqual(TEXT("a's move kept"), Second.Moves.Num(), 1);
  }

  // ---- another maneuver id: the old draft never carries over ----
  {
    Second.OnSnapshot(MsSnapshot(Hand, TEXT("maneuver:2:12"), 12), Board, Fighters);
    TestEqual(TEXT("new id: empty draft"), Second.Moves.Num(), 0);
    TestTrue(TEXT("new id: no boost"), Second.BoostCardId.IsEmpty());
    TestEqual(TEXT("pending id switched"), Second.PendingManeuverId, FString(TEXT("maneuver:2:12")));
    TestFalse(TEXT("the old id is no longer cached"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  }

  // ---- the maneuver closes / GAME_OVER: draft and cache gone ----
  {
    TestTrue(TEXT("draft on the new id"),
             Second.SetDestination(TEXT("a"), 1, 1, MsSnapshot(Hand, TEXT("maneuver:2:12"), 12), Board, Fighters, Reason));
    TestTrue(TEXT("cached"), Flow.RecallManeuverDraft(TEXT("maneuver:2:12"), Cached));
    Second.OnSnapshot(MsSnapshot(Hand, FString(), 13), Board, Fighters);
    TestTrue(TEXT("closed pending: mode none"), Second.Mode == ES09CommandMode::None);
    TestEqual(TEXT("closed pending: no moves"), Second.Moves.Num(), 0);
    TestFalse(TEXT("closed pending: cache cleared"), Flow.RecallManeuverDraft(TEXT("maneuver:2:12"), Cached));

    FS09CommandUi Third;
    Third.ViewerId = Me;
    MsBindCache(Third, Flow);
    Third.OnSnapshot(Snap, Board, Fighters);
    TestTrue(TEXT("third draft"), Third.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    FS08Snapshot Over = MsSnapshot(Hand, ManeuverA, 20);
    Over.Phase = TEXT("GAME_OVER");
    Third.OnSnapshot(Over, Board, Fighters);
    TestTrue(TEXT("GAME_OVER closes the draft"), Third.Mode == ES09CommandMode::None && Third.Moves.Num() == 0);
    TestFalse(TEXT("GAME_OVER clears the cache"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  }

  // ---- MS-E-46: the maneuver ends into a discard (hand > 7) or a pending
  // choice: the draft is gone in that mode too, so is the cache ----
  for (int32 Kind = 0; Kind < 2; ++Kind) {
    FS09CommandUi Ui;
    Ui.ViewerId = Me;
    MsBindCache(Ui, Flow);
    Ui.OnSnapshot(Snap, Board, Fighters);
    TestTrue(TEXT("draft held"), Ui.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("draft cached"), Flow.RecallManeuverDraft(ManeuverA, Cached));
    const FS08Snapshot Next = Kind == 0 ? MsDiscardSnapshot(Hand, 31) : MsPendingMoveSnapshot(2);
    Ui.OnSnapshot(Next, Board, Fighters);
    const TCHAR* Name = Kind == 0 ? TEXT("discard") : TEXT("pending choice");
    TestTrue(FString::Printf(TEXT("%s mode opens"), Name),
             Ui.Mode == (Kind == 0 ? ES09CommandMode::DiscardDraft : ES09CommandMode::PendingChoice));
    TestTrue(FString::Printf(TEXT("%s: no maneuver draft left"), Name),
             Ui.Moves.Num() == 0 && Ui.PendingManeuverId.IsEmpty() && Ui.BoostCardId.IsEmpty());
    TestFalse(FString::Printf(TEXT("%s: cache cleared"), Name), Flow.RecallManeuverDraft(ManeuverA, Cached));
  }

  // ---- a fresh UI whose first snapshot has no maneuver clears a stale cache ----
  {
    FS09CommandUi Old;
    Old.ViewerId = Me;
    MsBindCache(Old, Flow);
    Old.OnSnapshot(Snap, Board, Fighters);
    TestTrue(TEXT("old draft"), Old.SetDestination(TEXT("a"), 2, 1, Snap, Board, Fighters, Reason));
    TestTrue(TEXT("old draft cached"), Flow.RecallManeuverDraft(ManeuverA, Cached));
    FS09CommandUi Fresh;
    Fresh.ViewerId = Me;
    MsBindCache(Fresh, Flow);
    Fresh.OnSnapshot(MsSnapshot(Hand, FString(), 40), Board, Fighters);
    TestFalse(TEXT("closed maneuver seen by a fresh UI: cache cleared"), Flow.RecallManeuverDraft(ManeuverA, Cached));
  }
  return true;
}

#endif // WITH_AUTOMATION_TESTS
